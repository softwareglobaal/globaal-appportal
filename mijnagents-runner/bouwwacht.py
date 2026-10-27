#!/usr/bin/env python3
"""De Bouwwacht (regie): ziet of de diensten op de VM de code draaien die er na een git pull staat.

Waarom (K5, uitrol van PR #103, 27-10-2026): van 26-10 rond 19:00 tot 27-10 07:56 UTC faalde elke bouw van het bord.
`docker compose up -d --build` stopt dan voor de container vervangen wordt, dus het bord draaide een oude bouw, deploy.sh
probeerde het elke 2 minuten opnieuw, en niemand zag het.

Per dienst schrijft deploy.sh de boom van zijn map (`git rev-parse HEAD:<map>`) pas in `<map>-data/.built` na een
geslaagde bouw. De VM haalt main niet zelf binnen, dus een verschil ontstaat alleen na een `git pull` die nog niet
gebouwd is. Duurt dat verschil DREMPEL_MIN minuten of langer, dan zet ik een nood met een vaste tekst (N10); zijn ze
weer gelijk, dan staat de nood niet meer in mijn lijst en sluit het bord hem. Per storing gaat er ook een keer een
signaal naar Mehdi, via De Bode (zijn ja van 27-10-2026), want een nood voor claude-code heeft geen vaste lezer.

Sinds wanneer het verschil bestaat (driehoeksoverleg 27-10-2026, X2 en K2; Codex-resultaattoets 3.1):
- toont de reflog van HEAD de laatste stap waarop de boom gelijk was aan de markering, dan begon het verschil bij de stap
  erna. Dat is de echte pull-tijd, ook in mijn eerste ronde, en het is bewijs: ook een anker van voor die gelijkheid
  begint dan opnieuw, want tussen twee rondes kan de code even terug gelijk geweest zijn;
- staat de markering niet in een reflog die wel stappen heeft (ouder dan de reflog, of opgeschoond), of ontbreekt de
  markering, dan geldt het verschil als ouder dan de drempel: liever een nood te vroeg dan een bouw die stil achterloopt.
  Dat blijft zo tot gelijkheid of een nieuwe markering, ook als de reflog daarna wegvalt;
- is de reflog leeg of onleesbaar, dan is mijn eigen stand (STAND) de klok: per dienst de markering en het moment dat
  ik het verschil voor het eerst zag. Verandert de markering of zijn ze gelijk, dan begint dat opnieuw. Kan ik die
  stand niet bewaren, dan telt zo'n verschil als ouder dan de drempel.

Leest alleen wat deploy.sh maakt: git, de markeringen en de laatste regel van het deploylog. Schrijft alleen mijn eigen
stand en haar slot (een ronde tegelijk). Bouwt nooit, schrijft nooit een markering, haalt nooit binnen.

    bouwwacht.py            een ronde
    bouwwacht.py --droog    meten en tonen, niets naar het bord en niets in de stand

Cron (oneven minuten, tussen de tikken van deploy.sh):
    1-59/2 * * * * ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/bouwwacht.py >> ~/agents/bouwwacht.log 2>&1
"""
import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402

NAAM = "bouwwacht"
ag = bord.Agent(NAAM)

REPO = os.environ.get("BOUWWACHT_REPO", os.path.expanduser("~/appportal"))
# waar <map>-data/.built staat; standaard dezelfde map als in deploy.sh ($HOME/appportal)
MARKERINGEN = os.environ.get("BOUWWACHT_DATA", REPO)
LOGS = os.environ.get("BOUWWACHT_LOGS", os.path.expanduser("~"))
STAND = os.environ.get("BOUWWACHT_STAND", os.path.expanduser("~/appportal/mijnagents-data/bouwwacht.json"))
# De diensten in deze repo met hetzelfde deploypatroon (HEAD:<map> tegenover <map>-data/.built) en zonder eigen
# bewaking. Niet werfverslag: eigen repo, eigen bewaking (.mislukt, door werfverslag-dashboard gemeld).
DIENSTEN = ("mijnagents", "agents", "siyanagents")
DREMPEL_MIN = 10
REFLOG_MAX = 200
OUD = 0     # ouder dan de drempel, hoe oud precies is onbekend


STANDNOOD = "Bouwwacht kan zijn stand niet bewaren"
SIGNAALNOOD = "Bouwwacht kan het signaal voor Mehdi niet klaarzetten"


def noodtekst(dienst):
    return f"Bouw loopt achter op de code: {dienst}"


def onbekendtekst(dienst):
    return f"Bouwwacht kan {dienst} niet nakijken"


def signaal(m):
    """Een keer per storing een signaal voor Mehdi, via De Bode (zijn ja van 27-10-2026: een nood voor claude-code had
    geen vaste lezer). De `uniek` draagt het nummer van de storing (`storing_anker`): het bord maakt een item met dezelfde
    `uniek` nooit een tweede keer, ook niet bij een tweede pull tijdens de storing, en een nieuwe storing heeft een nieuw
    nummer. Dat nummer is geen teller maar het begin van de storing, vast zolang ze duurt (N10). De inhoud draagt geen
    minuten; de titel draagt nooit het woord dat De Bode als alarm leest en hem doet bellen (AGENTNORM.md 6)."""
    duur = (f"de bouw loopt {DREMPEL_MIN} minuten of langer achter" if m["minuten"] is not None else
            "de bouw loopt achter sinds een onbekende tijd: de markering ontbreekt of staat niet meer in de reflog")
    return {"voor": "mehdi", "soort": "signaal", "sleutel": m["dienst"],
            "titel": f"Bouw van {m['dienst']} loopt achter op de code",
            "uniek": f"bouwwacht-achter-{m['dienst']}-{m['storing']}",
            "inhoud": f"De VM draait voor {m['dienst']} niet de code die er na de laatste git pull staat: {duur} "
                      f"(laatste geslaagde bouw {m['gebouwd']}). De nood staat op het bord voor claude-code; wat de bouw "
                      f"zegt, staat in ~/deploy-{m['dienst']}.log op de VM."}


class Onleesbaar(RuntimeError):
    """git gaf geen antwoord over deze dienst. Onbekend is niet gelijk."""


def git(*args):
    """De uitvoer, of None als git een fout gaf. Alleen lezende commando's."""
    try:
        r = subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        raise Onleesbaar(f"git {args[0]}: {type(e).__name__}") from e
    return r.stdout.strip() if r.returncode == 0 else None


def boom(rev, dienst):
    return git("rev-parse", "--verify", "-q", f"{rev}:{dienst}")


def reflog():
    """De stappen van HEAD, van nieuw naar oud, als (commit, unix-tijd); leeg als er geen reflog te lezen is."""
    stappen = []
    for regel in (git("log", "-g", f"-n{REFLOG_MAX}", "--format=%H %gd", "--date=unix", "HEAD") or "").splitlines():
        m = re.fullmatch(r"([0-9a-f]{40}) \S*@\{(\d+)\}", regel.strip())
        if m:
            stappen.append((m.group(1), int(m.group(2))))
    return stappen


def begin_volgens_reflog(dienst, gebouwd):
    """Het tijdstip waarop HEAD wegging van de gebouwde boom; OUD als die niet in de reflog staat; None zonder reflog."""
    stappen = reflog()
    if not stappen:
        return None
    sinds = OUD
    for commit, ts in stappen:
        if boom(commit, dienst) == gebouwd:
            return sinds
        sinds = ts
    return OUD


def markering(dienst):
    """De gebouwde boom; leeg als er geen markering is. Een markering die er is maar niet te lezen valt, is onbekend,
    geen ontbrekende markering (Codex-resultaattoets 5)."""
    try:
        with open(os.path.join(MARKERINGEN, f"{dienst}-data", ".built"), encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""
    except (OSError, UnicodeDecodeError) as e:
        raise Onleesbaar(f"markering niet leesbaar: {type(e).__name__}") from e


def laatste_logregel(dienst):
    try:
        with open(os.path.join(LOGS, f"deploy-{dienst}.log"), "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 4096))
            regels = [r.strip() for r in f.read().decode("utf-8", "replace").splitlines() if r.strip()]
    except OSError:
        return ""
    return regels[-1][:160] if regels else ""


def lees_stand():
    try:
        with open(STAND, encoding="utf-8") as f:
            stand = json.load(f)
    except (OSError, ValueError):
        return {}
    return stand if isinstance(stand, dict) else {}


def bewaar_stand(stand):
    tijdelijk = f"{STAND}.{os.getpid()}.tmp"
    try:
        os.makedirs(os.path.dirname(STAND) or ".", exist_ok=True)
        with open(tijdelijk, "w", encoding="utf-8") as f:
            json.dump(stand, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tijdelijk, STAND)
    except OSError:
        try:
            os.remove(tijdelijk)
        except OSError:
            pass
        raise


def neem_slot():
    """Een ronde tegelijk (Codex-resultaattoets 3): anders kan een oude ronde na herstel nog haar verouderde alarm zetten,
    of een nieuw alarm sluiten met een lege lijst. Het slot geldt voor de hele ronde, tot en met de eindhartslag.
    Geeft het open slotbestand, of None als een andere ronde het heeft. Elke andere fout (geen slotbestand, een andere
    flock-fout) gaat door als OSError: dan draait er geen ronde zonder slot (Codex-resultaattoets 2.2)."""
    os.makedirs(os.path.dirname(STAND) or ".", exist_ok=True)
    f = open(f"{STAND}.slot", "a", encoding="utf-8")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return None
    except OSError:
        f.close()
        raise
    return f


def storing_anker(stand, dienst, gebouwd, begin, nu):
    """Het anker van de storing van deze dienst: {"sinds", "storing", "markering"}, en of zijn nummer los staat (pas
    gemaakt zonder reflog, dus alleen vast als de stand bewaard wordt).

    Een storing loopt van het eerste verschil tot de wacht weer gelijkheid ziet; zo lang blijft haar nummer (`storing`)
    hetzelfde, en daarmee de `uniek` van haar signaal. Een nieuwe storing begint ook als er intussen een andere bouw
    slaagde (een andere markering), of als de reflog toont dat de code na het begin van het anker nog gelijk was aan de
    gebouwde (Codex-resultaattoets 3.1 en 6.1). Een markering die even ontbreekt en terugkomt, is geen nieuwe storing (6.2).
    """
    a = stand.get(dienst)
    nieuw = not (isinstance(a, dict) and isinstance(a.get("sinds"), int) and isinstance(a.get("storing"), int)
                 and isinstance(a.get("markering"), str))
    if not nieuw and gebouwd and a["markering"] and gebouwd != a["markering"]:
        nieuw = True
    if not nieuw and begin not in (None, OUD) and a["sinds"] != OUD and begin > a["sinds"]:
        nieuw = True
    if nieuw:
        uit_reflog = begin not in (None, OUD)
        stand[dienst] = {"sinds": int(nu) if begin is None else begin, "storing": begin if uit_reflog else int(nu),
                         "markering": gebouwd}
        return stand[dienst], not uit_reflog
    if gebouwd:
        a["markering"] = gebouwd
    return a, False


def meet_dienst(dienst, stand, nu):
    gebouwd = markering(dienst)
    nu_boom = boom("HEAD", dienst)
    if nu_boom is None:
        raise Onleesbaar(f"{dienst} niet gevonden in HEAD")
    if gebouwd == nu_boom:
        stand.pop(dienst, None)
        return {"dienst": dienst, "stand": "gelijk"}
    # zonder markering is het begin onbekend: ouder dan de drempel
    begin = begin_volgens_reflog(dienst, gebouwd) if gebouwd else OUD
    anker, los = storing_anker(stand, dienst, gebouwd, begin, nu)
    if begin is None:
        sinds, bron = anker["sinds"], "anker"
    else:
        # Wat de reflog vaststelt, volgt het anker: het begin, of OUD, dat zo blijft tot gelijkheid of een nieuwe
        # storing, ook als de reflog later wegvalt (Codex-resultaattoets 3.1 en 4.3).
        sinds, bron = begin, "reflog" if gebouwd else "markering"
        anker["sinds"] = begin
    minuten = None if sinds == OUD else max(0, int((nu - sinds) // 60))
    achter = minuten is None or minuten >= DREMPEL_MIN
    return {"dienst": dienst, "stand": "achter" if achter else "bezig", "minuten": minuten,
            "gebouwd": gebouwd[:7] or "geen", "nieuw": nu_boom[:7], "log": laatste_logregel(dienst) if achter else "",
            "bron": bron, "storing": anker["storing"], "storing_los": los}


def meet(stand, nu=None):
    """Per dienst: gelijk, bezig (verschil korter dan de drempel), achter, of onbekend. Een dienst die faalt, houdt de
    andere niet tegen. Werkt `stand` bij; bewaren doet de ronde."""
    nu = time.time() if nu is None else nu
    uit = []
    for dienst in DIENSTEN:
        try:
            uit.append(meet_dienst(dienst, stand, nu))
        except Exception as e:  # noqa: BLE001  onbekend is niet gelijk, en de volgende dienst gaat door
            uit.append({"dienst": dienst, "stand": "onbekend", "reden": str(e)[:160] or type(e).__name__})
    return uit


def regel(m):
    if m["stand"] == "gelijk":
        return f"{m['dienst']} gelijk"
    if m["stand"] == "onbekend":
        return f"{m['dienst']} onbekend ({m['reden']})"
    duur = "ouder dan de drempel" if m["minuten"] is None else f"{m['minuten']} min"
    wat = "wordt gebouwd" if m["stand"] == "bezig" else "loopt achter"
    tekst = f"{m['dienst']} {wat}, {duur} ({m['gebouwd']} gebouwd, {m['nieuw']} in HEAD)"
    return tekst + (f"; deploylog: {m['log']}" if m.get("log") else "")


def werk(r, nu=None):
    nooit, mehdi_beslist = bord.grenzen(r.werkwijze)
    if not nooit or not mehdi_beslist:
        # Zonder grenzen geen werk (N2), zoals het sjabloon: de vaste vorm staat in AGENTNORM.md 8. Er is niet gemeten,
        # dus een bouwnood die openstaat blijft open: het bord sluit niets (Codex-resultaattoets 2).
        r.noden_onbekend = True
        r.nood("Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist", wie="mehdi")
        r.detail = "geen werk gedaan, grenzen ontbreken in de werkwijze"
        return []
    stand = lees_stand()
    vorig = json.dumps(stand, sort_keys=True)
    uitslag = meet(stand, nu)
    # Een stand die niet te bewaren is, houdt geen bouwnood tegen (Codex-resultaattoets 1). Zonder reflog is die stand
    # wel de enige klok: dan begint ze elke ronde opnieuw, dus een verschil dat alleen daarop steunt, telt als ouder
    # dan de drempel (Codex-resultaattoets 2.1).
    niet_bewaard = None
    if json.dumps(stand, sort_keys=True) != vorig:
        try:
            bewaar_stand(stand)
        except OSError as e:
            niet_bewaard = type(e).__name__
    if niet_bewaard:
        for m in uitslag:
            if m["stand"] == "bezig" and m.get("bron") == "anker":
                m.update(stand="achter", minuten=None, log=laatste_logregel(m["dienst"]))
            if m.get("storing_los"):
                # een nummer dat elke ronde nieuw zou zijn, gaf elke ronde een signaal: dan de laatste geslaagde bouw
                m["storing"] = f"markering-{m['gebouwd']}"
    noden = [(m, {"achter": noodtekst, "onbekend": onbekendtekst}[m["stand"]](m["dienst"]))
             for m in uitslag if m["stand"] in ("achter", "onbekend")]
    open_ = ag.open_noden() if noden else None
    for m, tekst in noden:
        r.nood(tekst, wie="claude-code")
        # een regel in het werkverslag als de nood nieuw is, niet elke 2 minuten dezelfde; weet het bord niet wat
        # open staat, dan geen regel (de nood zelf gaat wel mee)
        if open_ is not None and tekst not in {n["tekst"] for n in open_}:
            ag.log(m["dienst"], "fout", regel(m))
    r.detail = "; ".join(regel(m) for m in uitslag)
    signalen = [signaal(m) for m in uitslag if m["stand"] == "achter"]
    if signalen:
        # elke ronde zolang de storing duurt: het bord maakt het maar een keer (zelfde uniek), en lukte het een keer
        # niet, dan probeert de volgende ronde het vanzelf opnieuw
        try:
            ag.klaarzet(signalen)
        except Exception as e:  # noqa: BLE001  een signaal dat niet lukt, houdt de bouwnood niet tegen
            r.nood(SIGNAALNOOD, wie="claude-code")
            r.detail += f"; signaal niet klaargezet ({type(e).__name__})"
    if niet_bewaard:
        r.nood(STANDNOOD, wie="claude-code")
        r.detail += f"; stand niet bewaard ({niet_bewaard})"
    return uitslag


def in_cronlog(reden):
    """V8: wat niet op het bord kan, staat hier, in het cronlog, met de meting erbij, en de exitcode is 1."""
    print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {reden}", file=sys.stderr)
    for m in meet(lees_stand()):
        print(f"  {regel(m)}", file=sys.stderr)
    return 1


def main(argv=None):
    p = argparse.ArgumentParser(description="Ziet of de diensten op de VM de code draaien die er na een git pull staat.")
    p.add_argument("--droog", action="store_true", help="meten en tonen, niets naar het bord en niets in de stand")
    if p.parse_args(argv).droog:
        uitslag = meet(lees_stand())
        for m in uitslag:
            print(regel(m))
        return 1 if any(m["stand"] in ("achter", "onbekend") for m in uitslag) else 0
    try:
        slot = neem_slot()
    except OSError as e:
        return in_cronlog(f"geen slot voor de ronde ({type(e).__name__}: {e}); ronde niet gedraaid")
    if slot is None:
        print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} een vorige ronde loopt nog; deze slaat over",
              file=sys.stderr)
        return 0
    try:
        try:
            with ag.ronde("bouw van de diensten nakijken") as r:
                werk(r)
        except bord.RondeGestopt as e:
            return in_cronlog(f"ronde gestopt: {e}")
        if not ag.hartslag_ok:
            # Codex-resultaattoets 4: het bord gaf de werkwijze, maar de eindhartslag met de noden kwam niet aan
            return in_cronlog("eindhartslag niet aangekomen; de noden staan niet op het bord")
        return 0
    finally:
        slot.close()


if __name__ == "__main__":
    sys.exit(main())

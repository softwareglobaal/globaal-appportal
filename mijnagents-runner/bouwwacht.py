#!/usr/bin/env python3
"""De Bouwwacht (regie): ziet of de diensten op de VM de code draaien die er na een git pull staat.

Waarom (K5, uitrol van PR #103, 27-10-2026): van 26-10 rond 19:00 tot 27-10 07:56 UTC faalde elke bouw van het bord.
`docker compose up -d --build` stopt dan voor de container vervangen wordt, dus het bord draaide een oude bouw, deploy.sh
probeerde het elke 2 minuten opnieuw, en niemand zag het.

Per dienst schrijft deploy.sh de boom van zijn map (`git rev-parse HEAD:<map>`) pas in `<map>-data/.built` na een
geslaagde bouw. De VM haalt main niet zelf binnen, dus een verschil ontstaat alleen na een `git pull` die nog niet
gebouwd is. Duurt dat verschil DREMPEL_MIN minuten of langer, dan zet ik een nood met een vaste tekst (N10); zijn ze
weer gelijk, of loopt er weer een gewone bouw, dan staat de nood niet meer in mijn lijst en sluit het bord hem.

Sinds wanneer het verschil bestaat, zegt alleen de reflog van HEAD (driehoeksoverleg 27-10-2026, X2):
- toont ze de laatste stap waarop de boom gelijk was aan de markering, dan begon het verschil bij de stap erna. Dat is
  de echte pull-tijd, ook in mijn eerste ronde, en een gelijkheid tussen twee rondes zet de klok terecht opnieuw;
- staat de markering niet in een reflog die wel stappen heeft (ouder dan de reflog, of opgeschoond), of ontbreekt de
  markering, dan geldt het verschil als ouder dan de drempel: liever een nood te vroeg dan een bouw die stil achterloopt;
- is de reflog leeg of onleesbaar, dan ook, met de nood REFLOGNOOD, die zegt waarom er dan na elke pull meteen een nood
  komt.
Een eigen stand als klok (K2) is er niet meer: hij gaf in zes Codex-toetsen telkens nieuwe randgevallen (een stand die
niet te bewaren, beschadigd of hersteld was), en de duurzame stand van een storing staat al op het bord.

Een storing is de tijd dat mijn bouwnood voor een dienst op het bord openstaat. Het bord geeft die nood een nummer en
sluit hem pas als ik hem niet meer meld; een nieuwe storing is een nieuwe nood met een nieuw nummer. Per storing gaat er
een keer een signaal naar Mehdi, via De Bode (zijn ja van 27-10-2026, want een nood voor claude-code heeft geen vaste
lezer), met dat nummer in de `uniek`: het bord maakt een item met dezelfde `uniek` nooit een tweede keer. Het signaal
komt de ronde nadat de nood openging, en elke open bouwnood krijgt het voor de ronde hem kan sluiten, ook als de bouw
intussen herstelde (dan als terugblik). Een dienst die even niet na te kijken is, of open noden die het bord niet geeft,
sluiten geen storing (tweede driehoeksoverleg 27-10-2026, X2 en K2).

Leest alleen wat deploy.sh maakt: git, de markeringen en de laatste regel van het deploylog. Schrijft alleen een
slotbestand (een ronde tegelijk). Bouwt nooit, schrijft nooit een markering, haalt nooit binnen.

    bouwwacht.py            een ronde
    bouwwacht.py --droog    meten en tonen, niets naar het bord

Cron (oneven minuten, tussen de tikken van deploy.sh):
    1-59/2 * * * * ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/bouwwacht.py >> ~/agents/bouwwacht.log 2>&1
"""
import argparse
import fcntl
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
SLOT = os.environ.get("BOUWWACHT_SLOT", os.path.expanduser("~/appportal/mijnagents-data/bouwwacht.slot"))
# De diensten in deze repo met hetzelfde deploypatroon (HEAD:<map> tegenover <map>-data/.built) en zonder eigen
# bewaking. Niet werfverslag: eigen repo, eigen bewaking (.mislukt, door werfverslag-dashboard gemeld).
DIENSTEN = ("mijnagents", "agents", "siyanagents")
DREMPEL_MIN = 10
REFLOG_MAX = 200
OUD = 0     # ouder dan de drempel, hoe oud precies is onbekend

REFLOGNOOD = "Bouwwacht kan de reflog van de VM niet lezen"
SIGNAALNOOD = "Bouwwacht kan het signaal voor Mehdi niet klaarzetten"


def noodtekst(dienst):
    return f"Bouw loopt achter op de code: {dienst}"


def onbekendtekst(dienst):
    return f"Bouwwacht kan {dienst} niet nakijken"


def signaal(m, nood_id):
    """Het signaal voor Mehdi bij de storing met bouwnood `nood_id`, met wat de meting van deze ronde zegt (`m`). Dat
    nummer is geen teller maar de nood van deze storing, vast zolang ze duurt (N10). De inhoud draagt geen minuten; de
    titel draagt nooit het woord dat De Bode als alarm leest en hem doet bellen (AGENTNORM.md 6)."""
    dienst = m["dienst"]
    hersteld = m["stand"] in ("gelijk", "bezig")
    if hersteld:
        # tweede overleg X2: de storing herstelde voor dit signaal kon vertrekken; ze krijgt het toch, als terugblik
        stand = ("de bouw liep " + str(DREMPEL_MIN) + " minuten of langer achter en is intussen " +
                 ("weer gelijk met de code" if m["stand"] == "gelijk" else "opnieuw aan het bouwen na een nieuwe pull"))
    elif m["stand"] == "onbekend":
        stand = "de bouw loopt achter; deze ronde kon ik de dienst niet nakijken"
    elif m["minuten"] is not None:
        stand = f"de bouw loopt {DREMPEL_MIN} minuten of langer achter (laatste geslaagde bouw {m['gebouwd']})"
    else:
        stand = ("de bouw loopt achter sinds een onbekende tijd: de markering ontbreekt, staat niet meer in de reflog, "
                 f"of de reflog is niet te lezen (laatste geslaagde bouw {m['gebouwd']})")
    # De Bode stuurt de titel: die zegt dus zelf of de storing nog loopt (Codex-resultaattoets 9.2)
    return {"voor": "mehdi", "soort": "signaal", "sleutel": dienst,
            "titel": f"Bouw van {dienst} {'liep' if hersteld else 'loopt'} achter op de code",
            "uniek": f"bouwwacht-achter-{dienst}-{nood_id}",
            "inhoud": f"De VM draait voor {dienst} niet de code die er na de laatste git pull staat: {stand}. De nood "
                      f"staat op het bord voor claude-code; wat de bouw zegt, staat in ~/deploy-{dienst}.log op de VM."}


class Onleesbaar(RuntimeError):
    """git of de markering gaf geen antwoord over deze dienst. Onbekend is niet gelijk."""


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


def neem_slot():
    """Een ronde tegelijk (Codex-resultaattoets 3): anders kan een oude ronde na herstel nog haar verouderde alarm zetten,
    of een nieuw alarm sluiten met een lege lijst. Het slot geldt voor de hele ronde, tot en met de eindhartslag.
    Geeft het open slotbestand, of None als een andere ronde het heeft. Elke andere fout (geen slotbestand, een andere
    flock-fout) gaat door als OSError: dan draait er geen ronde zonder slot (Codex-resultaattoets 2.2)."""
    os.makedirs(os.path.dirname(SLOT) or ".", exist_ok=True)
    f = open(SLOT, "a", encoding="utf-8")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return None
    except OSError:
        f.close()
        raise
    return f


def meet_dienst(dienst, nu):
    gebouwd = markering(dienst)
    nu_boom = boom("HEAD", dienst)
    if nu_boom is None:
        raise Onleesbaar(f"{dienst} niet gevonden in HEAD")
    if gebouwd == nu_boom:
        return {"dienst": dienst, "stand": "gelijk"}
    # zonder markering is het begin onbekend: ouder dan de drempel
    begin = begin_volgens_reflog(dienst, gebouwd) if gebouwd else OUD
    sinds = OUD if begin is None else begin
    minuten = None if sinds == OUD else max(0, int((nu - sinds) // 60))
    achter = minuten is None or minuten >= DREMPEL_MIN
    return {"dienst": dienst, "stand": "achter" if achter else "bezig", "minuten": minuten,
            "gebouwd": gebouwd[:7] or "geen", "nieuw": nu_boom[:7], "log": laatste_logregel(dienst) if achter else "",
            "zonder_reflog": begin is None}


def meet(nu=None):
    """Per dienst: gelijk, bezig (verschil korter dan de drempel), achter, of onbekend. Een dienst die faalt, houdt de
    andere niet tegen."""
    nu = time.time() if nu is None else nu
    uit = []
    for dienst in DIENSTEN:
        try:
            uit.append(meet_dienst(dienst, nu))
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


def open_noden():
    """Mijn open noden op het bord als {tekst: nummer}, of None als dat onbekend is. Het nummer is de rij van de nood:
    het bord geeft een nood die opnieuw opengaat een nieuw nummer, en dat maakt er een storing van."""
    try:
        antwoord = bord.call("/api/nood")
    except Exception:  # noqa: BLE001
        return None
    rijen = antwoord.get("nood") if isinstance(antwoord, dict) else None
    if not isinstance(rijen, list) or not all(isinstance(r, dict) for r in rijen):
        return None
    mijn = [r for r in rijen if r.get("naam") == NAAM]
    if not all(isinstance(r.get("tekst"), str) and isinstance(r.get("id"), int) for r in mijn):
        return None
    return {r["tekst"]: r["id"] for r in mijn}


def werk(r, nu=None):
    nooit, mehdi_beslist = bord.grenzen(r.werkwijze)
    if not nooit or not mehdi_beslist:
        # Zonder grenzen geen werk (N2), zoals het sjabloon: de vaste vorm staat in AGENTNORM.md 8. Er is niet gemeten,
        # dus een bouwnood die openstaat blijft open: het bord sluit niets (Codex-resultaattoets 2).
        r.noden_onbekend = True
        r.nood("Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist", wie="mehdi")
        r.detail = "geen werk gedaan, grenzen ontbreken in de werkwijze"
        return []
    uitslag = meet(nu)
    open_ = open_noden()
    if open_ is None:
        # Zonder de open noden ken ik de nummers van de storingen niet. Dan sluit deze ronde niets, zodat geen storing
        # verdwijnt voor haar signaal vertrok (tweede overleg X2); nieuwe noden komen er wel bij.
        r.noden_onbekend = True
    for m in uitslag:
        dienst = m["dienst"]
        tekst = {"achter": noodtekst, "onbekend": onbekendtekst}.get(m["stand"], lambda d: None)(dienst)
        if tekst is None:
            continue
        r.nood(tekst, wie="claude-code")
        # een regel in het werkverslag als de nood nieuw is, niet elke 2 minuten dezelfde; weet het bord niet wat
        # open staat, dan geen regel (de nood zelf gaat wel mee)
        if open_ is not None and tekst not in open_:
            ag.log(dienst, "fout", regel(m))
        # een dienst die deze ronde niet na te kijken is, sluit zijn storing niet (tweede overleg K2)
        if m["stand"] == "onbekend" and open_ and noodtekst(dienst) in open_:
            r.nood(noodtekst(dienst), wie="claude-code")
    if any(m.get("zonder_reflog") for m in uitslag):
        r.nood(REFLOGNOOD, wie="claude-code")
    r.detail = "; ".join(regel(m) for m in uitslag)
    if open_ is None:
        if any(m["stand"] == "achter" for m in uitslag):
            r.nood(SIGNAALNOOD, wie="claude-code")
            r.detail += "; signaal wacht: open noden onbekend"
        return uitslag
    # Elke storing waarvan de bouwnood openstaat, krijgt haar signaal, voor de eindhartslag van deze ronde die nood kan
    # sluiten: ook als de bouw intussen herstelde, dan als terugblik (tweede overleg X2). Het vertrekt dus de ronde nadat
    # de nood openging, en elke ronde opnieuw zolang ze openstaat: het bord maakt het maar een keer (zelfde uniek), en
    # lukte het een keer niet, dan probeert de volgende ronde het vanzelf opnieuw.
    per_dienst = {m["dienst"]: m for m in uitslag}
    signalen = [signaal(per_dienst[d], open_[noodtekst(d)]) for d in DIENSTEN if noodtekst(d) in open_]
    if signalen:
        try:
            ag.klaarzet(signalen)
        except Exception as e:  # noqa: BLE001  een signaal dat niet lukt, houdt de bouwnood niet tegen
            r.nood(SIGNAALNOOD, wie="claude-code")
            r.detail += f"; signaal niet klaargezet ({type(e).__name__})"
            # De bouwnoden van die signalen blijven open, ook na herstel: anders sluit het bord ze, is hun nummer weg en
            # kan de volgende ronde het signaal niet meer opnieuw proberen (Codex-resultaattoets 9.1).
            for d in DIENSTEN:
                if noodtekst(d) in open_:
                    r.nood(noodtekst(d), wie="claude-code")
    return uitslag


def in_cronlog(reden):
    """V8: wat niet op het bord kan, staat hier, in het cronlog, met de meting erbij, en de exitcode is 1."""
    print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {reden}", file=sys.stderr)
    for m in meet():
        print(f"  {regel(m)}", file=sys.stderr)
    return 1


def main(argv=None):
    p = argparse.ArgumentParser(description="Ziet of de diensten op de VM de code draaien die er na een git pull staat.")
    p.add_argument("--droog", action="store_true", help="meten en tonen, niets naar het bord")
    if p.parse_args(argv).droog:
        uitslag = meet()
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

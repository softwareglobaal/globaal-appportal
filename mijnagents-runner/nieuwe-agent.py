#!/usr/bin/env python3
"""nieuwe-agent.py: de generator van Mehdi's agent-omgeving. Zie AGENTNORM.md, hoofdstuk 8.

Twee stappen, met een controle voor en na (Codex NA08, 16-10-2026):

1. Aanmaken. Eerst wordt alles gecontroleerd, en pas als alles klopt komt er iets
   op schijf of op het bord: naam, label, rol, mandaat, cadans, minstens een mag
   en een grens, en een werkwijze die de norm haalt (N1 minstens 500 tekens; N2 een
   kop over wat hij nooit doet en een over wat Mehdi beslist, met punten eronder;
   N8 geen geheim; N9 geen gedachtestreepjes). De naam mag nog niet op het bord
   staan en geen eigen runner hebben. Dan schrijft hij het runner-skelet,
   registreert hij de agent, zet hij de werkwijze op het bord en leest hij die terug.

    python3 nieuwe-agent.py --naam post-wacht --label "De Postwacht" --type h-architects \\
        --rol "sorteert nieuwe post op info@" --mandaat "lezen en labelen, nooit verwijderen" \\
        --cadans "elk uur" --mag "post labelen" --grens "nooit verwijderen" \\
        --werkwijze werkwijze/post-wacht.md

   Breekt een stap nadat de kaart op het bord kwam, dan zegt hij hoe je de
   werkwijze zet (werkwijze_naar_bord.py). Zelf hervat hij nooit: een kaart zonder
   werkwijze is niet vanzelf de zijne.

2. De eerste ronde, als werk() is ingevuld. De runner draait een keer en de agent
   wordt getoetst aan de norm (controle_agenten.py). Pas als dat slaagt, krijg je
   de cron-regel; de agent gaat pas op de cron na een gecontroleerde eerste ronde.

    python3 nieuwe-agent.py --eerste-ronde post-wacht --cron "0 * * * *"

Zonder --naam vraagt hij alles interactief op. Het token komt uit
~/appportal/mijnagents-data/.env (AGENTS_TOKEN), nooit uit een argument.
"""
import argparse
import os
import re
import shlex
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
sys.path.insert(0, HIER)
import bord  # noqa: E402
import controle_agenten  # noqa: E402

SJABLOON = os.path.join(HIER, "_sjabloon_agent.py")
RUNNERMAP = HIER                       # waar de runner komt; een test zet hier een tijdelijke map
SKELET = "werk() nog in te vullen"     # staat in het skelet tot iemand werk() invult
NAAMVORM = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VENV = "~/agents/.venv/bin/python"


def vraag(tekst, verplicht=True):
    while True:
        a = input(tekst).strip()
        if a or not verplicht:
            return a
        print("  (verplicht)")


def vraag_lijst(tekst):
    print(tekst + " (leeg = klaar)")
    uit = []
    while True:
        a = input("  - ").strip()
        if not a:
            return uit
        uit.append(a)


def runnerpad(naam):
    return os.path.join(RUNNERMAP, f"{naam.replace('-', '_')}.py")


def skelet(naam):
    with open(SJABLOON, encoding="utf-8") as f:
        sjab = f.read()
    # %%LABEL%% wordt de naam: het echte label staat op het bord, een kopie hier zou verouderen.
    return sjab.replace("%%NAAM%%", naam).replace("%%LABEL%%", naam)


def lees_werkwijze(pad):
    """(tekst, None) of (None, wat er mis is)."""
    if not pad:
        return None, "geen werkwijze meegegeven (--werkwijze): zonder regelboek komt er geen agent (N1)"
    try:
        with open(os.path.expanduser(pad), encoding="utf-8") as f:
            return f.read(), None
    except (OSError, UnicodeDecodeError) as e:
        return None, f"werkwijze niet leesbaar: {pad} ({type(e).__name__})"


def controleer(agent, werkwijze):
    """Wat er ontbreekt voor er iets op schijf of op het bord mag komen; leeg als alles klopt.
    Dezelfde toetsen als controle_agenten.py, zodat een nieuwe agent meteen slaagt."""
    fouten = []
    if not NAAMVORM.match(agent.get("naam") or ""):
        fouten.append("naam: kleine letters, cijfers en koppeltekens, bijvoorbeeld post-wacht")
    for veld in ("label", "rol", "mandaat", "cadans"):
        if not (agent.get(veld) or "").strip():
            fouten.append(f"{veld} ontbreekt (N3)")
    if not [m for m in agent.get("mag") or [] if m.strip()]:
        fouten.append("mag: minstens een ding dat hij zelf mag doen (N3)")
    if not [g for g in agent.get("grenzen") or [] if g.strip()]:
        fouten.append("grens: minstens een grens, iets wat hij nooit doet (N3)")
    if werkwijze is not None:
        rij = {"werkwijze": werkwijze}
        for code, norm in (("N1", controle_agenten.n1_werkwijze), ("N2", controle_agenten.n2_grenzen_in_werkwijze),
                           ("N8", controle_agenten.n8_geen_geheim), ("N9", controle_agenten.n9_stijl)):
            ok, uitleg = norm(rij, None)
            if ok is False:
                fouten.append(f"werkwijze {code}: {uitleg}")
        nooit, mehdi_beslist = bord.grenzen(werkwijze)
        if not nooit:
            fouten.append('werkwijze: de kop "## Wat ik nooit doe" met punten ("- ...", op kolom 0) eronder')
        if not mehdi_beslist:
            fouten.append('werkwijze: de kop "## Wat Mehdi beslist" met punten ("- ...", op kolom 0) eronder')
    return fouten


def stand_op_bord(naam):
    """vrij (de naam is nog niet in gebruik), onaf (een kaart zonder werkwijze) of bestaat. Kan het bord het
    niet zeggen, dan WerkwijzeOnbekend: onbekend is niet vrij."""
    try:
        tekst = bord.Agent(naam).werkwijze_lezen()
    except bord.WerkwijzeOnbekend as e:
        if e.soort == "agent staat niet op het bord":
            return "vrij"
        raise
    return "bestaat" if tekst.strip() else "onaf"


def _lees(pad):
    try:
        with open(pad, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def herstel(naam, pad=None, werkwijze=None):
    """Hoe je de werkwijze op een kaart zonder (de juiste) werkwijze zet: een handeling, na nakijken van die
    kaart. Alleen de tekst die deze generator net goedkeurde, mag op het bord. Codex NA26: het zaad in
    werkwijze/ is niet vanzelf die tekst; wijkt het af, dan eerst de goedgekeurde tekst erin. Codex NA30: is de
    bron intussen veranderd, dan geen herstel, maar opnieuw controleren (hetzelfde commando; het hervat nooit)."""
    try:
        op_bord = bord.Agent(naam).werkwijze_lezen().strip()
        print(f"Op het bord staat nu: {f'een werkwijze van {len(op_bord)} tekens' if op_bord else 'geen werkwijze'}.")
    except bord.WerkwijzeOnbekend as e:
        print(f"Wat er nu op het bord staat, is onbekend ({e}).")
    zaad = os.path.join(RUNNERMAP, "werkwijze", f"{naam}.md")
    if werkwijze is None or not pad:
        print("Zet de werkwijze pas als ze door de generator gecontroleerd is: draai hem met --werkwijze <bestand>.")
        print("Is het de kaart van een andere agent, kies dan een andere naam.")
        return
    bron = os.path.abspath(os.path.expanduser(pad))
    bron_nu = _lees(bron)
    if bron_nu is None or bron_nu.strip() != werkwijze.strip():
        print(f"De werkwijze in {bron} is veranderd sinds de controle. Geen herstel met een tekst die niemand nakeek:")
        print("draai hetzelfde commando opnieuw; het controleert de nieuwe tekst en zegt dan hoe je ze zet.")
        return
    print("Is dat de kaart van deze aanmaak, zet de werkwijze dan zelf, na het verschil te bekijken:")
    zaad_tekst = _lees(zaad)
    if os.path.realpath(bron) != os.path.realpath(zaad) and (zaad_tekst is None or zaad_tekst.strip() != werkwijze.strip()):
        if zaad_tekst is not None:
            print(f"  LET OP: {zaad} is niet de werkwijze die je meegaf; zonder de stap hieronder zet --zet die tekst.")
        print(f"  cp {shlex.quote(bron)} {shlex.quote(zaad)}")
    print(f"  {VENV} {os.path.join(HIER, 'werkwijze_naar_bord.py')} {naam}          (toont het verschil)")
    print(f"  {VENV} {os.path.join(HIER, 'werkwijze_naar_bord.py')} {naam} --zet    (zet de werkwijze)")
    print("Is het de kaart van een andere agent, kies dan een andere naam.")


def maak(agent, werkwijze, cron, pad=None):
    naam = agent.get("naam") or ""
    fouten = controleer(agent, werkwijze)
    if fouten:
        print("Niet aangemaakt; er staat niets op schijf of op het bord. Wat ontbreekt:")
        for f in fouten:
            print(f"  - {f}")
        return 2
    if not bord.TOKEN:
        print("Niet aangemaakt: geen AGENTS_TOKEN in ~/appportal/mijnagents-data/.env.")
        return 1
    try:
        stand = stand_op_bord(naam)
    except bord.WerkwijzeOnbekend as e:
        print(f"Niet aangemaakt: het bord kon niet zeggen of {naam} al bestaat ({e}).")
        return 1
    if stand == "bestaat":
        print(f"Niet aangemaakt: {naam} staat al op het bord, met een werkwijze. Een bestaande agent breid je uit.")
        return 2
    doel, code = runnerpad(naam), skelet(naam)
    runner_er = os.path.exists(doel)
    if runner_er:
        with open(doel, encoding="utf-8") as f:
            if f.read() != code:
                print(f"Niet aangemaakt: {doel} bestaat al, met eigen code.")
                return 2
    if stand == "onaf":
        # Codex NA13 en NA20: een kaart zonder werkwijze is niet vanzelf een eigen afgebroken aanmaak, en het bord
        # toont te weinig om dat te herkennen. De generator hervat dus nooit zelf; hij zegt hoe je de werkwijze zet.
        print(f"Niet aangemaakt: {naam} staat al op het bord, zonder werkwijze.")
        herstel(naam, pad, werkwijze)
        return 2
    if not runner_er:
        with open(doel, "w", encoding="utf-8") as f:
            f.write(code)
        os.chmod(doel, 0o755)

    # Vanaf hier komt er iets op het bord. Breekt een stap, dan staat de kaart er zonder (de juiste) werkwijze;
    # de generator zegt dan hoe je ze zet, want zelf hervatten kan hij niet veilig (Codex NA20).
    try:
        bord.call("/api/agent", agent)
        uit = bord.call(f"/api/agent/{naam}/werkwijze", {"werkwijze": werkwijze})
        if not uit.get("ok"):
            raise RuntimeError(uit.get("reden") or "het bord weigerde de werkwijze")
        terug = bord.Agent(naam).werkwijze_lezen()
    except Exception as e:  # noqa: BLE001  elke fout hier laat een kaart zonder werkwijze achter
        print(f"LET OP: {naam} staat op het bord, maar zonder werkwijze ({type(e).__name__}: {e}).")
        herstel(naam, pad, werkwijze)
        return 1
    if terug.strip() != werkwijze.strip():
        print(f"LET OP: de werkwijze die op het bord staat voor {naam}, is niet de tekst die je meegaf.")
        herstel(naam, pad, werkwijze)
        return 1

    print(f"Aangemaakt: {naam} staat op het bord met zijn werkwijze ({len(terug.strip())} tekens).")
    print(f"Runner-skelet: {doel}")
    print("Volgende stap: vul werk() in. Dan de eerste ronde; pas als die gecontroleerd is, gaat hij op de cron:")
    print(f'  {VENV} {os.path.join(HIER, "nieuwe-agent.py")} --eerste-ronde {naam} --cron "{cron}"')
    return 0


def draai(pad):
    """Een ronde van de runner, zoals de cron hem zou draaien. Geeft de exitcode."""
    try:
        return subprocess.run([sys.executable, pad], cwd=RUNNERMAP, timeout=3600).returncode
    except subprocess.TimeoutExpired:
        print("De eerste ronde liep langer dan een uur.")
        return 124


def toets(naam):
    """De uitslag van controle_agenten voor deze ene agent, of None als het bord niet te lezen is."""
    if not os.path.exists(controle_agenten.DB):
        return None
    controle_agenten.RUNNER = RUNNERMAP      # de controle kijkt naar dezelfde runner als de generator
    con = sqlite3.connect(f"file:{controle_agenten.DB}?mode=ro", uri=True)
    try:
        return controle_agenten.toets(con, naam)
    finally:
        con.close()


def _tijd(ts):
    try:
        d = datetime.fromisoformat(str(ts).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def vers_na(naam, begin):
    """Codex NA14: hoort wat het bord over deze agent weet bij de ronde die net draaide? Zijn hartslag en zijn
    gemelde kennis moeten van na het begin zijn, en de ronde moet afgelopen zijn. (vers, waarom niet)."""
    con = sqlite3.connect(f"file:{controle_agenten.DB}?mode=ro", uri=True)
    try:
        st = con.execute("select status, ts from status where naam=?", (naam,)).fetchone()
        ke = con.execute("select kennis_ts from agent where naam=?", (naam,)).fetchone()
    finally:
        con.close()
    grens = begin   # Codex NA21: geen marge; het bord en de generator lopen op dezelfde klok (de VM)

    def van_deze_ronde(ts):
        t = _tijd(ts)
        return t is not None and t >= grens

    if not st or not van_deze_ronde(st[1]):
        return False, "geen hartslag van deze ronde op het bord"
    if st[0] not in ("klaar", "waakt"):
        return False, f"de ronde eindigde op '{st[0]}', niet op klaar of waakt"
    if not ke or not van_deze_ronde(ke[0]):
        return False, "deze ronde meldde niet welk regelboek ze las (N4)"
    return True, ""


def eerste_ronde(naam, cron):
    doel = runnerpad(naam)
    if not os.path.exists(doel):
        print(f"Geen runner: {doel}. Maak de agent eerst aan.")
        return 2
    with open(doel, encoding="utf-8") as f:
        if SKELET in f.read():
            print("werk() is nog het skelet. Vul het eerst in: een agent die niets doet, gaat niet op de cron.")
            return 2
    try:
        if not bord.Agent(naam).werkwijze_lezen().strip():
            print(f"De werkwijze van {naam} is leeg op het bord; de ronde zou meteen stoppen.")
            return 2
    except bord.WerkwijzeOnbekend as e:
        print(f"De werkwijze van {naam} is niet gelezen ({e}); de ronde zou meteen stoppen.")
        return 1

    print(f"Eerste ronde van {naam}:")
    begin = datetime.now(timezone.utc)
    code = draai(doel)
    if code != 0:
        print(f"De eerste ronde eindigde met code {code}. Niet op de cron; kijk de noden en het werkverslag na.")
        return 1
    uitslag = toets(naam)
    if not uitslag or len(uitslag) != 1:
        print(f"Niet op de cron: de controle vond {naam} niet als actieve agent op het bord.")
        return 1
    vers, waarom = vers_na(naam, begin)
    if not vers:
        print(f"Niet op de cron: {waarom}. Wat het bord toont, is van een eerdere ronde.")
        return 1
    gezakt = [t for t in uitslag[0]["toetsen"] if t["ok"] is False]
    for t in uitslag[0]["toetsen"]:
        merk = {True: "  ok", None: " nvt", False: " ZAK"}[t["ok"]]
        print(f"{merk} {t['norm']} {t['eis']}: {t['uitleg']}")
    if gezakt:
        print(f"Niet op de cron: {len(gezakt)} norm(en) gezakt na de eerste ronde.")
        return 1
    print("\nDe eerste ronde is gecontroleerd. Lees nu zijn werkverslag op het bord en leg het naast de")
    print("voorbeelden van Mehdi (AGENTNORM.md 8). Klopt het, zet hem dan op de cron (crontab -e):")
    print(f"  {cron} {VENV} {doel} >> ~/agents/{naam}.log 2>&1")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Maakt een nieuwe agent, of draait en controleert zijn eerste ronde.")
    p.add_argument("--naam"); p.add_argument("--label"); p.add_argument("--type", default="")
    p.add_argument("--rol", default=""); p.add_argument("--mandaat", default="")
    p.add_argument("--cadans", default=""); p.add_argument("--eigenaar", default="mehdi")
    p.add_argument("--mag", action="append", default=[])
    p.add_argument("--grens", action="append", default=[])
    p.add_argument("--tool", action="append", default=[])
    p.add_argument("--cron", default="0 * * * *", help="cron-schema voor de runner")
    p.add_argument("--werkwijze", help="markdown-bestand met het volledige proces (komt op het bord, daar bewerkbaar)")
    p.add_argument("--prive", action="store_true", help="alleen zichtbaar voor beheer (Mehdi), niet voor de groep agents")
    p.add_argument("--levert-aan", action="append", default=[], help="agent of afdeling waaraan deze agent klaarzet")
    p.add_argument("--draait-op", default="VM")
    p.add_argument("--eerste-ronde", metavar="NAAM", help="draai en controleer de eerste ronde van een aangemaakte agent")
    a = p.parse_args(argv)

    if a.eerste_ronde:
        return eerste_ronde(a.eerste_ronde, a.cron)

    if a.naam:
        agent = dict(naam=a.naam, label=a.label or "", type=a.type, rol=a.rol, mandaat=a.mandaat, mag=a.mag,
                     grenzen=a.grens, cadans=a.cadans, tools=a.tool, eigenaar=a.eigenaar, prive=a.prive,
                     levert_aan=a.levert_aan, draait_op=a.draait_op)
        cron, pad = a.cron, a.werkwijze
    else:
        print("== Nieuwe agent ==")
        naam = re.sub(r"[^a-z0-9-]", "-", vraag("naam (kort, kleine letters, met koppelteken): ").lower()).strip("-")
        agent = dict(
            naam=naam,
            label=vraag("label (weergavenaam): "),
            type=vraag("type (afdeling op het bord, bv. h-architects): ", False),
            rol=vraag("rol (een regel: wat doet hij): "),
            mandaat=vraag("mandaat (wat doet hij en voor wie): "),
            mag=vraag_lijst("mag zelfstandig"),
            grenzen=vraag_lijst("grenzen (doet nooit)"),
            cadans=vraag("cadans (hoe vaak, wanneer): "),
            tools=vraag_lijst("gereedschap (de echte tools)"),
            eigenaar="mehdi",
        )
        pad = vraag("werkwijze (pad naar het markdown-bestand): ")
        cron = vraag("cron-schema voor de runner [0 * * * *]: ", False) or "0 * * * *"

    werkwijze, fout = lees_werkwijze(pad)
    if fout:
        print("Niet aangemaakt; er staat niets op schijf of op het bord. Wat ontbreekt:")
        for f in [fout] + controleer(agent, None):
            print(f"  - {f}")
        return 2
    return maak(agent, werkwijze, cron, pad)


if __name__ == "__main__":
    sys.exit(main())

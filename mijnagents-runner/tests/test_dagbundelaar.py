"""Grendels op De Dagbundelaar en de Zoom-dagregel (ontwerp regie-zoom v1.2: Z14, J14, I2; T31 tot T33).

Gemeten op 21-10-2026: 31 bundels voor h-architects hadden een datum als dossier (22 met de Zoom-dagregel, de rest met
gezondheid, coaching en mail), en de dagregels van vrijdag en zaterdag bleven liggen omdat De Dagbundelaar alleen op
werkdagen 'gisteren' bundelt. Deze test legt vast:

- T31: een item voor mehdi of met een datum als sleutel komt nooit in een bundel voor h-architects; de bundel 2531 voor
  h-architects bevat alleen zijn eigen transcript; het privétranscript voor mehdi krijgt een eigen bundel (J14, uniek
  bundel:<dag>:<sleutel>:mehdi); de dagregel staat als "Zoom: ..." in het Dagverslag; zoom-tekst en het ochtendbericht
  zitten nergens in;
- T32: op maandag komen de dagregels van vrijdag, zaterdag en een herziene van dinsdag mee onder "Nagekomen of herzien"
  en worden opgepakt; een van acht dagen oud niet;
- T33: zonder dagregel zegt het Dagverslag dat ze ontbreekt;
- RZ2-01 (bouwcontrole RZ2): van een privé-item staat alleen "privégesprek, N min" in de bundel, het Dagverslag en het
  werkverslag, ook voor een item van voor 21-10-2026 met naam en onderwerp in de titel (de hele keten met De
  Fathomwacht en de export: test_bord_lees.py);
- RZ2-03 en RZ4-04: De Dagbundelaar draait binnen het slot van de gesprekkenketen, sinds RZ4-04 als laatste stap van
  keten.py (test_keten.py), zonder eigen cronregel. Het zetscript zet het nieuwe blok, ook over het vorige blok met de
  losse regel van De Dagbundelaar heen;
- RZ3-01: een item met inhoud.afdeling prive is privé, ook bij prive=false;
- RZ3-02: het zetscript aanvaardt alleen precies de drie oude regels of het beheerde blok; elke andere vorm weigert het;
- RZ4-06: het beheerde blok vervangt het alleen als zijn inhoud precies een bekende vorm is (het huidige blok of het
  vorige uit deze branch); een onbekende regel in het blok weigert het, zonder die opdracht te tonen.

Geen netwerk: het bord is nagebootst (bord.call, bord.opgepakt) en de agent vangt zijn klaarzet en hartslag op. De
cronregel draait met /bin/sh, met een nagebootste flock en python.
Draaien: python3 mijnagents-runner/tests/test_dagbundelaar.py
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
_argv, sys.argv = sys.argv, [sys.argv[0]]
import bord  # noqa: E402
import dagbundelaar as D  # noqa: E402
sys.argv = _argv


class NepBord:
    """Wat De Dagbundelaar leest (de hele bak, en apart de Zoom-dagregels op klaar) en wat hij schrijft."""

    def __init__(self, alle, zoom=None):
        self.alle = alle
        self.zoom = [it for it in (zoom if zoom is not None else alle) if it["soort"] == "zoom" and it["status"] == "klaar"]
        self.gelezen, self.opgepakt, self.bundels, self.harten, self.logs = [], [], [], [], []

    def call(self, pad, payload=None, method=None):
        self.gelezen.append(pad)
        if pad.startswith("/api/klaarzet?") and "soort=zoom" in pad:
            assert "status=klaar" in pad, "de dagregels per soort lezen, op klaar"
            return {"items": [dict(it) for it in self.zoom]}
        if pad.startswith("/api/klaarzet?"):
            return {"items": [dict(it) for it in self.alle]}
        raise AssertionError("onverwachte bordoproep " + pad)


class NepRonde:
    """De gedeelde ronde (N12) zonder bord: de noden en het detail komen als laatste hartslag in nb.harten."""

    def __init__(self, nb, taak):
        self.nb, self.taak, self.noden, self.detail = nb, taak, [], ""

    def __enter__(self):
        return self

    def nood(self, tekst, wie="mehdi"):
        self.noden.append({"tekst": tekst, "wie": wie})

    def bron(self, naam, inhoud):
        pass

    def __exit__(self, *fout):
        self.nb.harten.append({"taak": self.taak, "nood": self.noden, "detail": self.detail, "fout": fout[0]})
        return False


def bundelen(dag, nb, nacht=False, gepland=False):
    """De ochtendronde van De Dagbundelaar met een nagebootst bord; de dagvaststelling heeft eigen tests
    (test_dagbundelaar_vaststelling.py) en is hier een lege stap. gepland: de ronde uit de keten (zonder --dag)."""
    oud = (bord.call, bord.opgepakt, D.DAG, D.DAG_GEGEVEN, D.NACHT, D.vastleggen)
    bord.call = nb.call
    bord.opgepakt = lambda kid, door: nb.opgepakt.append(kid)
    D.DAG, D.DAG_GEGEVEN, D.NACHT = dag, not gepland, nacht
    D.vastleggen = lambda r, dagen, **k: nb.logs.append(("vastleggen", dagen)) or "vastgelegd"
    D.ag.ronde = lambda taak, **k: NepRonde(nb, taak)
    D.ag.klaarzet = lambda items: nb.bundels.extend(items) or {"nieuw": len(items)}
    D.ag.hartslag = lambda *a, **k: nb.harten.append(k)
    D.ag.log = lambda *a, **k: nb.logs.append(a)
    D.ag.log_verstuur = lambda: None
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            D.main()
    finally:
        bord.call, bord.opgepakt, D.DAG, D.DAG_GEGEVEN, D.NACHT, D.vastleggen = oud
        for naam in ("ronde", "klaarzet", "hartslag", "log", "log_verstuur"):
            D.ag.__dict__.pop(naam, None)
    return nb


def item(kid, van, voor, soort, titel, sleutel="", inhoud=None, status="klaar", uniek=""):
    return {"id": kid, "van": van, "voor": voor, "soort": soort, "sleutel": sleutel, "titel": titel, "status": status,
            "uniek": uniek, "verwijzing": "", "inhoud": json.dumps(inhoud, ensure_ascii=False) if isinstance(inhoud, dict) else (inhoud or "")}


def dagregel(kid, dag, status="klaar", titel=None):
    return item(kid, "zoom-wacht", "mehdi", "zoom", titel or f"Zoom {dag[8:10]}-{dag[5:7]}: 3 gesprekken (2 met Fathom, 1 alleen in Zoom), 61 min; 4 chatgesprekken",
                inhoud={"datum": dag, "telling": "volledig"}, status=status, uniek=f"zoom:dag:{dag}")


DAG = "2026-10-20"
GEZONDHEID = item(1, "gezondheid-wacht", "mehdi", "gezondheid", "Gezondheid: hartslag en slaap", sleutel=DAG)
PRIVE = item(2, "fathom-wacht", "mehdi", "transcript", "2026-10-20T10:00 Fathom: Proefpersoon Zeta · persoonlijk · PRIVÉ", sleutel="2531",
             inhoud={"datum": DAG, "start": "10:00", "minuten": 35, "prive": True}, uniek="fathom:2")
WERK = item(3, "fathom-wacht", "h-architects", "transcript", "2026-10-20T11:00 Fathom: klant 2531 · werfoverleg", sleutel="2531",
            inhoud={"datum": DAG, "start": "11:00", "prive": False}, uniek="fathom:3")
ZOOMDAG = dagregel(4, DAG)
ZOOMTEKST = item(5, "zoom-wacht", "regisseur", "zoom-tekst", "2026-10-20 14:00 Zoom-gesprek, 12 min, alleen in Zoom",
                 inhoud={"datum": DAG, "start": "14:00", "stand": "tekst bewaard"}, uniek="zoom-tekst:u5")
OCHTEND = item(6, "regisseur", "mehdi", "ochtendbericht", "Ochtendbericht: drie beslissingen", inhoud={"datum": DAG, "punten": []},
               uniek=f"ochtendbericht:{DAG}")


def tekst_van(b):
    return b["titel"] + "\n" + b["inhoud"]


def test_t31_geen_lek_naar_de_afdeling():
    nb = bundelen(DAG, NepBord([GEZONDHEID, PRIVE, WERK, ZOOMDAG, ZOOMTEKST, OCHTEND]))
    per_uniek = {b["uniek"]: b for b in nb.bundels}
    afdeling = [b for b in nb.bundels if b["voor"] == "h-architects"]
    for b in afdeling:
        for weg in (GEZONDHEID, PRIVE, ZOOMDAG):
            assert weg["titel"] not in tekst_van(b), f"{weg['soort']} lekte naar h-architects: {b['uniek']}"
        assert b["sleutel"] and not D.DAG == b["sleutel"], "een bundel voor de afdeling heeft een dossier, geen datum"
    assert [b["uniek"] for b in afdeling] == [f"bundel:{DAG}:2531"], [b["uniek"] for b in afdeling]
    assert WERK["titel"] in per_uniek[f"bundel:{DAG}:2531"]["inhoud"] and PRIVE["titel"] not in per_uniek[f"bundel:{DAG}:2531"]["inhoud"]
    voor_mehdi = per_uniek[f"bundel:{DAG}:2531:mehdi"]
    assert voor_mehdi["voor"] == "mehdi" and voor_mehdi["sleutel"] == "2531", voor_mehdi
    # RZ2-01: het privétranscript staat in zijn bundel als privégesprek met de duur, zonder met wie of waarover
    assert "- transcript: privégesprek, 35 min" in voor_mehdi["inhoud"] and PRIVE["titel"] not in voor_mehdi["inhoud"], voor_mehdi
    zonder = per_uniek[f"bundel:{DAG}:(zonder dossier)"]
    assert zonder["voor"] == "mehdi" and GEZONDHEID["titel"] in zonder["inhoud"], "een datum als sleutel is geen dossier"
    verslag = per_uniek[f"dagverslag:{DAG}"]["inhoud"]
    assert f"Zoom: {ZOOMDAG['titel']}" in verslag, verslag
    for b in nb.bundels:
        assert ZOOMTEKST["titel"] not in tekst_van(b) and OCHTEND["titel"] not in tekst_van(b), b["uniek"]
        if b["uniek"] != f"dagverslag:{DAG}":
            assert ZOOMDAG["titel"] not in tekst_van(b), "de dagregel is een regel in het Dagverslag, geen bundel"
    assert sorted(nb.opgepakt) == [1, 2, 3, 4], nb.opgepakt
    assert any("soort=zoom" in p for p in nb.gelezen), "de dagregels worden apart gelezen (n=500 dekt geen week)"


def test_t32_maandag_neemt_het_weekend_en_herzieningen_mee():
    zondag = "2026-10-25"
    vrijdag, zaterdag = dagregel(11, "2026-10-23"), dagregel(12, "2026-10-24")
    dinsdag = dagregel(13, "2026-10-20", titel="Zoom 20-10: 4 gesprekken (3 met Fathom, 1 alleen in Zoom), 80 min; 4 chatgesprekken")
    oud = dagregel(14, "2026-10-18")
    vandaag = dagregel(15, zondag)
    opgepakt_al = dagregel(16, "2026-10-22", status="opgepakt")
    # De hele bak (n=500) bevat ze niet meer: alleen de lezing per soort vindt ze.
    nb = bundelen(zondag, NepBord([vandaag], zoom=[vrijdag, zaterdag, dinsdag, oud, vandaag, opgepakt_al]))
    verslag = next(b for b in nb.bundels if b["uniek"] == f"dagverslag:{zondag}")["inhoud"]
    assert f"Zoom: {vandaag['titel']}" in verslag
    blok = verslag.split("Nagekomen of herzien:", 1)
    assert len(blok) == 2, verslag
    for it in (vrijdag, zaterdag, dinsdag):
        assert f"- Zoom: {it['titel']}" in blok[1], it["titel"]
    assert oud["titel"] not in verslag and "18-10" not in verslag, "acht dagen oud valt buiten de terugblik"
    assert sorted(nb.opgepakt) == [11, 12, 13, 15], nb.opgepakt
    assert not any(b["voor"] == "h-architects" for b in nb.bundels)


def test_t33_geen_dagregel():
    nb = bundelen(DAG, NepBord([WERK]))
    verslag = next(b for b in nb.bundels if b["uniek"] == f"dagverslag:{DAG}")["inhoud"]
    assert "Zoom: dagregel ontbreekt (Zoomwacht niet klaar)" in verslag, verslag
    assert "Nagekomen of herzien" not in verslag


def test_oude_dagregel_met_datum_als_sleutel():
    """Een dagregel van voor versie 2 heeft de datum als sleutel. Ook die gaat naar het Dagverslag, nooit naar een bundel."""
    oud = dict(dagregel(21, DAG), sleutel=DAG)
    nb = bundelen(DAG, NepBord([oud, WERK]))
    assert not any(b["voor"] == "h-architects" and oud["titel"] in tekst_van(b) for b in nb.bundels)
    assert f"Zoom: {oud['titel']}" in next(b for b in nb.bundels if b["uniek"] == f"dagverslag:{DAG}")["inhoud"]


def test_rz2_01_oud_prive_item_zonder_dossier():
    """RZ2-01: een privé-item van voor 21-10-2026 staat nog op het bord met naam en onderwerp in de titel en de
    verwijzing, en zonder dossier. Tot dan kwam die titel in de bundel, onder 'Toe te wijzen' in het Dagverslag en in het
    detail van het werkverslag. Nu staat er alleen 'privégesprek, N min'; zonder minuten 'duur onbekend', nooit 0."""
    oud = item(31, "fathom-wacht", "mehdi", "transcript", "2026-10-20T21:00 Fathom: Proefpersoon Zeta · Proefonderwerp Omega · PRIVÉ",
               inhoud={"datum": DAG, "start": "21:00", "minuten": 25, "personen": "Proefpersoon Zeta", "prive": True}, uniek="fathom:31")
    oud["verwijzing"] = "/home/ubuntu/appportal/mijnagents-data/fathom-data/2026-10-20 2100 Avond met Proefpersoon Zeta"
    plaud = item(32, "plaud-wacht", "mehdi", "transcript", "2026-10-20 22:00 Plaud: Proefpersoon Zeta · Proefonderwerp Omega · PRIVÉ",
                 inhoud={"datum": DAG, "start": "22:00", "prive": True, "thema": "Proefonderwerp Omega"}, uniek="plaud:32")
    nb = bundelen(DAG, NepBord([oud, plaud, WERK]))
    verslag = next(b for b in nb.bundels if b["uniek"] == f"dagverslag:{DAG}")["inhoud"]
    assert "- transcript: privégesprek, 25 min" in verslag and "- transcript: privégesprek, duur onbekend" in verslag, verslag
    assert "Toe te wijzen: privégesprek, 25 min; privégesprek, duur onbekend" in verslag, verslag
    assert WERK["titel"] in verslag, "een werkgesprek blijft zoals het was"
    for tekst in [json.dumps(b, ensure_ascii=False) for b in nb.bundels] + [json.dumps(a, ensure_ascii=False) for a in nb.logs]:
        assert "Zeta" not in tekst and "Omega" not in tekst and "Avond met" not in tekst, tekst
    assert sorted(nb.opgepakt) == [3, 31, 32], "ook een privé-item is verwerkt"


def test_rz3_01_afdeling_prive_is_prive():
    """RZ3-01 (besluit van de regie, 22-10-2026: de veilige kant): de dossierbeslissing noemt een gesprek met afdeling
    prive privé, ook bij prive=false. Een item van voor de herstelling met die inhoud droeg naam en onderwerp in titel en
    verwijzing, zonder PRIVÉ en zonder prive=true, en kwam zo voluit in de bundel en het Dagverslag. Nu is het voor De
    Dagbundelaar privé (ook met een hoofdletter): 'privégesprek, N min', geen verwijzing, en nooit in een bundel voor een
    afdeling, ook niet als het item voor een afdeling klaarstond. De hele route met De Fathomwacht en de export:
    test_bord_lees.py; met De Plaudwacht: test_plaud_wacht.py."""
    fathom = item(41, "fathom-wacht", "mehdi", "transcript", "2026-10-20T21:00 Fathom: Proefpersoon Zeta · Proefonderwerp Omega",
                  sleutel="2531", uniek="fathom:41",
                  inhoud={"datum": DAG, "start": "21:00", "minuten": 25, "afdeling": "prive", "prive": False, "personen": "Proefpersoon Zeta"})
    fathom["verwijzing"] = "/home/ubuntu/appportal/mijnagents-data/fathom-data/2026-10-20 2100 Avond met Proefpersoon Zeta"
    plaud = item(42, "plaud-wacht", "h-architects", "transcript", "2026-10-20 22:00 Plaud: Proefpersoon Zeta · Proefonderwerp Omega",
                 sleutel="2531", uniek="plaud:42", inhoud={"datum": DAG, "start": "22:00", "afdeling": "Prive", "prive": False})
    nb = bundelen(DAG, NepBord([fathom, plaud, WERK]))
    per_uniek = {b["uniek"]: b for b in nb.bundels}
    assert [b["uniek"] for b in nb.bundels if b["voor"] == "h-architects"] == [f"bundel:{DAG}:2531"], [b["uniek"] for b in nb.bundels]
    afdeling = per_uniek[f"bundel:{DAG}:2531"]["inhoud"]
    assert WERK["titel"] in afdeling and "privégesprek" not in afdeling and "Proefpersoon" not in afdeling, afdeling
    voor_mehdi = per_uniek[f"bundel:{DAG}:2531:mehdi"]["inhoud"]
    assert "- transcript: privégesprek, 25 min" in voor_mehdi and "- transcript: privégesprek, duur onbekend" in voor_mehdi, voor_mehdi
    for tekst in [json.dumps(b, ensure_ascii=False) for b in nb.bundels] + [json.dumps(a, ensure_ascii=False) for a in nb.logs]:
        assert "Zeta" not in tekst and "Omega" not in tekst and "Avond met" not in tekst, tekst
    assert sorted(nb.opgepakt) == [3, 41, 42], nb.opgepakt


# ------------------------------------------------------------------------------------------------- RZ2-03 ---
PLANNING = os.path.join(RUNNER, "planning")
VM = {"flock": "/usr/bin/flock", "python": "/home/ubuntu/agents/.venv/bin/python", "slot": "/tmp/gesprekken.lock",
      "logmap": "/home/ubuntu/agents/", "runner": "/home/ubuntu/appportal/mijnagents-runner/"}
# Een nagebootste flock: -w <s> [-E <code>] <slot> <opdracht ...>. FLOCK_PROEF=vrij voert de opdracht uit terwijl het
# slot vastzit; bezet eindigt zoals flock na de wachttijd (de code van -E, anders 1).
NEP_FLOCK = """#!/bin/sh
code=1
while [ $# -gt 0 ]; do
  case "$1" in
    -w) shift 2 ;;
    -E) code="$2"; shift 2 ;;
    *) break ;;
  esac
done
shift
echo "slot genomen: $FLOCK_PROEF" >> "$CRON_SPOOR"
if [ "$FLOCK_PROEF" = bezet ]; then exit "$code"; fi
"$@"
uit=$?
echo "slot vrij" >> "$CRON_SPOOR"
exit $uit
"""
NEP_PYTHON = """#!/bin/sh
echo "python $*" >> "$CRON_SPOOR"
exit "${NEP_EXIT:-0}"
"""


def cronregel(script):
    """De regel van dit script; 'keten.py' is de ochtend- en middagketen, 'keten.py --nacht' de nachtketen."""
    regels = [r for r in open(os.path.join(PLANNING, "gesprekken.cron"), encoding="utf-8").read().splitlines()
              if r.strip() and not r.startswith("#")]
    gevonden = [r for r in regels if script in r and (script.endswith("--nacht") or "keten.py --nacht" not in r)]
    assert len(gevonden) == 1, gevonden
    return gevonden[0]


def cron_draaien(proef, script="keten.py", exit_python=0):
    """De echte regel van dit script uit planning/gesprekken.cron, zoals cron ze draait (/bin/sh -c, zonder de vijf
    tijdvelden), met de paden van de VM vervangen door een tijdelijke map. Geeft (spoor, logboek)."""
    map_ = tempfile.mkdtemp(prefix="cron-")
    for naam, tekst in (("flock", NEP_FLOCK), ("python", NEP_PYTHON)):
        with open(os.path.join(map_, naam), "w", encoding="utf-8") as f:
            f.write(tekst)
        os.chmod(os.path.join(map_, naam), 0o755)
    regel = cronregel(script).split(None, 5)[5]
    for sleutel, pad in (("flock", os.path.join(map_, "flock")), ("python", os.path.join(map_, "python")),
                         ("slot", os.path.join(map_, "gesprekken.lock")), ("logmap", map_ + os.sep), ("runner", "/runner/")):
        assert VM[sleutel] in regel, (sleutel, regel)
        regel = regel.replace(VM[sleutel], pad)
    spoor = os.path.join(map_, "spoor.txt")
    subprocess.run(["/bin/sh", "-c", regel], check=False, timeout=30,
                   env=dict(os.environ, FLOCK_PROEF=proef, CRON_SPOOR=spoor, NEP_EXIT=str(exit_python)))
    lees = lambda p: open(p, encoding="utf-8").read() if os.path.exists(p) else ""  # noqa: E731
    return lees(spoor).splitlines(), lees(os.path.join(map_, script.replace(".py", ".log")))


def test_rz4_04_dagbundelaar_zonder_eigen_cronregel_binnen_het_slot_van_de_keten():
    """RZ2-03 (bouwcontrole RZ2, 21-10-2026): De Dagbundelaar startte na een wachttime-out toch, terwijl de keten nog
    liep. RZ3-03 gaf hem een eigen regel die 5400 s op het slot wachtte. RZ4-04 (herstelcontrole van Codex, besluit van
    de regie 22-10-2026): een handmatige ronde kan het slot 1800 s vasthouden, en dan kon hij te vroeg of te laat lopen.
    Nu heeft hij geen eigen regel meer: hij is de laatste stap van keten.py (test_keten.py), en die regel draait binnen
    het slot; krijgt de keten het slot niet, dan start ze niet."""
    regels = [r for r in open(os.path.join(PLANNING, "gesprekken.cron"), encoding="utf-8").read().splitlines()
              if r.strip() and not r.startswith("#")]
    assert not [r for r in regels if "dagbundelaar" in r], "geen eigen cronregel meer voor De Dagbundelaar"
    regel = cronregel("keten.py")
    assert regel.startswith("0 7,13 * * * /usr/bin/flock -w 1800 -E 75 /tmp/gesprekken.lock ") and "/bin/true" not in regel, regel
    spoor, log = cron_draaien("vrij")
    assert spoor == ["slot genomen: vrij", "python /runner/keten.py", "slot vrij"], spoor
    assert "niet gestart" not in log, log
    spoor, log = cron_draaien("bezet")
    assert spoor == ["slot genomen: bezet"], f"zonder slot start de keten niet: {spoor}"
    # tegenproef op RZ4-04 (22-10-2026): zonder -E schreef een keten die het slot niet kreeg niets in keten.log
    assert "gesprekken.lock na 1800 s niet vrij: keten niet gestart" in log, log
    spoor, log = cron_draaien("vrij", exit_python=1)
    assert "niet gestart" not in log, "een keten die liep en faalde, is geen keten die niet startte"
    assert "%" not in regel, "cron leest een % als einde van de opdracht"
    assert "\N{EM DASH}" not in regel and "\N{EN DASH}" not in regel


# Het vorige beheerde blok uit deze branch (be314cc, 22-10-2026), letterlijk: met de losse regel van De Dagbundelaar.
PY, RN, LG = VM["python"], VM["runner"].rstrip("/"), VM["logmap"].rstrip("/")
TIJDEN = "# 07:00 UTC is 09:00 Brussel tot en met 24-10-2026, vanaf 25-10 08:00; 13:00 UTC is 15:00, vanaf 25-10 14:00."
# De ketenregel van nu (tegenproef op RZ4-04: met -E 75 en een regel in keten.log) en die van het vorige blok.
KETEN = (f"0 7,13 * * * /usr/bin/flock -w 1800 -E 75 /tmp/gesprekken.lock {PY} {RN}/keten.py >> {LG}/keten.log 2>&1;"
         f' if [ $? -eq 75 ]; then echo "$(date -u -Iseconds) slot /tmp/gesprekken.lock na 1800 s niet vrij: keten niet'
         f' gestart" >> {LG}/keten.log; fi')
NACHTKETEN = (f"30 23 * * * /usr/bin/flock -w 1800 -E 75 /tmp/gesprekken.lock {PY} {RN}/keten.py --nacht >> {LG}/keten.log "
              f"2>&1; if [ $? -eq 75 ]; then echo \"$(date -u -Iseconds) slot /tmp/gesprekken.lock na 1800 s niet vrij: "
              f"nachtketen niet gestart\" >> {LG}/keten.log; fi")
KETEN_VORIG = f"0 7,13 * * * /usr/bin/flock -w 1800 /tmp/gesprekken.lock {PY} {RN}/keten.py >> {LG}/keten.log 2>&1"
VORIG_BUNDEL =(f"5 7 * * 1-5 /usr/bin/flock -w 5400 -E 75 /tmp/gesprekken.lock {PY} {RN}/dagbundelaar.py >> {LG}/dagbundelaar.log 2>&1;"
                f' if [ $? -eq 75 ]; then echo "$(date -u -Iseconds) slot /tmp/gesprekken.lock na 5400 s niet vrij: De Dagbundelaar'
                f' niet gestart" >> {LG}/dagbundelaar.log; fi')
LOS = [f"0 7 * * 1-5 {PY} {RN}/dagbundelaar.py >> {LG}/dagbundelaar.log 2>&1",
       f"0 7,13 * * * {PY} {RN}/fathom_wacht.py >> {LG}/fathom_wacht.log 2>&1",
       f"15 7,13 * * * {PY} {RN}/zoom_wacht.py >> {LG}/zoom_wacht.log 2>&1"]


def test_rz4_04_zetscript_vervangt_het_vorige_blok_en_de_losse_regels():
    """Het zetscript (samenvoegen) zet het nieuwe blok, met alleen de regel van de keten: over het vorige blok uit deze
    branch heen (met de losse regel van De Dagbundelaar, ook met spaties achteraan) en over de drie oude losse regels.
    Twee keer samenvoegen geeft hetzelfde; elke andere regel blijft staan."""
    M = _zetscript()
    cron = open(os.path.join(PLANNING, "gesprekken.cron"), encoding="utf-8").read().splitlines()
    bode = f"* * * * * {PY} {RN}/bode.py >> {LG}/bode.log 2>&1"
    vorig = [M.BEGIN, TIJDEN, KETEN_VORIG, VORIG_BUNDEL, M.EINDE]
    for huidig, oude_regels in ((["MAILTO=''", bode, ""] + vorig, 0),
                                (["MAILTO=''", bode, ""] + [r + "  " if r.startswith(("#", "0", "5")) and r not in (M.BEGIN, M.EINDE) else r
                                                            for r in vorig], 0),
                                (["MAILTO=''", bode] + LOS, 3)):
        doel, oud = M.samenvoegen(huidig, cron)
        assert oud == oude_regels, (oud, huidig)
        assert doel[doel.index(M.BEGIN):] == [M.BEGIN, TIJDEN, KETEN, NACHTKETEN, M.EINDE], doel
        assert not any("dagbundelaar" in r for r in doel), doel
        assert "MAILTO=''" in doel and bode in doel and M.samenvoegen(doel, cron) == (doel, 0), "twee keer samenvoegen geeft hetzelfde"


def _weigering(M, huidig, cron):
    try:
        M.samenvoegen(huidig, cron)
    except ValueError as e:
        return str(e)
    raise AssertionError(f"aanvaard: {huidig}")


def test_rz4_06_zetscript_weigert_een_blok_met_onbekende_inhoud():
    """RZ4-06 (herstelcontrole van Codex, 22-10-2026): binnen een bestaand beheerd blok verving het zetscript alles, ook
    een opdracht die er niet van ons is; die verdween dan stil uit de crontab. Nu vervangt het een blok alleen als zijn
    inhoud precies een bekende vorm is: het huidige blok of het vorige uit deze branch. Anders weigert het, met de
    gevonden regels: een regel van een gesprekkenrunner zoals voordien (een toewijzing wordt '<waarde>'), de tijden van
    het blok voluit, en van een onbekende opdracht alleen haar tijdvelden, want de opdracht zelf kan een geheim
    bevatten. Ook het blok van voor RZ2-03 (met /bin/true) en dat van de eerste bouw (3600 s) zijn geen bekende vorm:
    deze branch stond nooit op de VM."""
    M = _zetscript()
    cron = open(os.path.join(PLANNING, "gesprekken.cron"), encoding="utf-8").read().splitlines()
    nieuw = M.samenvoegen(["MAILTO=''"] + LOS, cron)[0]
    blok = nieuw[nieuw.index(M.BEGIN):]
    vreemd = f"30 6 * * * GEHEIM_PROEF=x {PY} /home/ubuntu/eigen/opruimen.sh --sleutel proefgeheim"
    gevallen = {
        "een vreemde opdracht in het huidige blok": blok[:3] + [vreemd] + blok[3:],
        "een vreemde opdracht in het vorige blok": [M.BEGIN, TIJDEN, KETEN_VORIG, VORIG_BUNDEL, vreemd, M.EINDE],
        "het vorige blok zonder de regel van De Dagbundelaar": [M.BEGIN, TIJDEN, KETEN_VORIG, M.EINDE],
        "een andere wachttijd van de keten": [M.BEGIN, TIJDEN, KETEN.replace("-w 1800", "-w 900"), M.EINDE],
        "zonder de regel met de tijden": [M.BEGIN, KETEN, M.EINDE],
        "een leeg blok": [M.BEGIN, M.EINDE],
        "een lege regel in het blok": [M.BEGIN, TIJDEN, "", KETEN, M.EINDE],
        "ander commentaar in het blok": [M.BEGIN, TIJDEN, "# MAILTO=proefgeheim", KETEN, M.EINDE],
        "het blok van voor RZ2-03": [M.BEGIN, TIJDEN, KETEN_VORIG, f"5 7 * * 1-5 /usr/bin/flock -w 3600 /tmp/gesprekken.lock /bin/true; "
                                                               f"{PY} {RN}/dagbundelaar.py >> {LG}/dagbundelaar.log 2>&1", M.EINDE],
        "het blok van de eerste bouw": [M.BEGIN, TIJDEN, KETEN_VORIG, VORIG_BUNDEL.replace("5400", "3600"), M.EINDE],
    }
    for naam, inhoud in gevallen.items():
        melding = _weigering(M, ["MAILTO=''", ""] + inhoud, cron)
        assert "onbekende inhoud in het beheerde blok" in melding, (naam, melding)
        for geheim in ("GEHEIM_PROEF", "proefgeheim", "opruimen.sh", "MAILTO=", "/home/ubuntu/eigen"):
            assert geheim not in melding, (naam, geheim, melding)
        for r in inhoud[1:-1]:
            if any(f"mijnagents-runner/{x}" in r for x in M.RUNNERS):
                assert r.strip() in melding, (naam, r, melding)
        if vreemd in inhoud:
            assert "30 6 * * * <onbekende opdracht, niet getoond>" in melding, (naam, melding)
    melding = _weigering(M, ["MAILTO=''", ""] + gevallen["ander commentaar in het blok"], cron)
    assert TIJDEN in melding and "# (ander commentaar, niet getoond)" in melding, melding


def _zetscript():
    spec = importlib.util.spec_from_file_location("gesprekken_cron_zetten", os.path.join(PLANNING, "gesprekken_cron_zetten.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    return M


def test_rz3_02_zetscript_weigert_elke_andere_vorm():
    """RZ3-02 (herstelcontrole van Codex, 22-10-2026): het zetscript eiste niet dat het precies de drie oude regels
    vervangt. Twee van de drie, een dubbele, of het blok met daarnaast nog een oude regel werden stil aanvaard, en dan
    liep er na --zet nog een losse ronde naast de keten, of ontbrak er een. Nu aanvaardt het alleen precies de drie
    verwachte oude regels (De Fathomwacht om 7 en 13, De Zoomwacht om 7:15 en 13:15, De Dagbundelaar om 7:00 op werkdagen),
    of al het beheerde blok zonder oude regels. Elke andere vorm weigert het, met de gevonden regels van de
    gesprekkenrunners in de melding; andere regels (die geheimen kunnen dragen) noemt het nooit."""
    M = _zetscript()
    cron = open(os.path.join(PLANNING, "gesprekken.cron"), encoding="utf-8").read().splitlines()
    py, rn, lg = VM["python"], VM["runner"].rstrip("/"), VM["logmap"].rstrip("/")
    bode = f"* * * * * GEHEIM_PROEF=x {py} {rn}/bode.py >> {lg}/bode.log 2>&1"
    los = [f"0 7 * * 1-5 {py} {rn}/dagbundelaar.py >> {lg}/dagbundelaar.log 2>&1",
           f"0 7,13 * * * {py} {rn}/fathom_wacht.py >> {lg}/fathom_wacht.log 2>&1",
           f"15 7,13 * * * {py} {rn}/zoom_wacht.py >> {lg}/zoom_wacht.log 2>&1"]
    # tegenproef van 22-10-2026: een runnerregel met een toewijzing (een sleutel in de omgeving) kwam voluit in de melding
    met_sleutel = f"0 7,13 * * * GEHEIM_PROEF=x FATHOM_TOKEN='a b' {py} {rn}/fathom_wacht.py >> {lg}/fathom_wacht.log 2>&1"
    doel, oud = M.samenvoegen(["MAILTO=''", bode] + los, cron)
    assert oud == 3 and M.samenvoegen(doel, cron) == (doel, 0), "precies de drie oude regels, daarna het blok"
    blok = doel[doel.index(M.BEGIN):doel.index(M.EINDE) + 1]
    gevallen = {
        "twee van de drie": ["MAILTO=''", bode] + los[1:],
        "een van de drie": ["MAILTO=''", bode, los[1]],
        "een dubbele": ["MAILTO=''", bode] + los + [los[2]],
        "geen enkele en geen blok": ["MAILTO=''", bode],
        "het blok en nog een oude regel": doel + [los[1]],
        "twee blokken": doel + [""] + blok,
        "een andere tijd": ["MAILTO=''", bode, los[0], los[1], los[2].replace("15 7,13", "20 7,13")],
        "met timeout": ["MAILTO=''", bode, los[0], f"0 7,13 * * * /usr/bin/timeout 2700 {py} {rn}/fathom_wacht.py", los[2]],
        "met een sleutel in de regel": ["MAILTO=''", bode, los[0], met_sleutel, los[2]],
    }
    for naam, huidig in gevallen.items():
        try:
            M.samenvoegen(huidig, cron)
        except ValueError as e:
            melding = str(e)
        else:
            raise AssertionError(f"{naam}: aanvaard")
        eigen = [r.strip() for r in huidig if r.strip() and not r.lstrip().startswith("#")
                 and any(f"mijnagents-runner/{x}" in r for x in M.RUNNERS)]
        for r in eigen:
            r = r.replace("GEHEIM_PROEF=x FATHOM_TOKEN='a b'", "<waarde> <waarde>")
            assert r in melding, (naam, r, melding)
        assert "GEHEIM_PROEF" not in melding and "bode.py" not in melding and "MAILTO" not in melding, (naam, melding)
        assert "FATHOM_TOKEN" not in melding and "a b'" not in melding, (naam, melding)
        if not eigen:
            assert "Gevonden regels: geen" in melding, (naam, melding)


# Een nagebootste crontab: -l leest het bestand CRON_PROEF ("no crontab" als het er niet is), - schrijft het.
NEP_CRONTAB = """#!/bin/sh
if [ "$1" = "-l" ]; then
  if [ -f "$CRON_PROEF" ]; then cat "$CRON_PROEF"; else echo "no crontab for proef" >&2; exit 1; fi
else
  cat > "$CRON_PROEF"
fi
"""


def test_rz3_02_zetten_alleen_als_het_bord_herbouwd_is():
    """RZ3-02, derde deel (tegenproef op de herstelcontrole, 22-10-2026): mislukt de build van het bord in deploy.sh, dan
    blijft de oude bordcontainer draaien terwijl de runnercode al nieuw is, en .built houdt de vorige boom. Het zetscript
    zette de nieuwe planning toch. Nu zet --zet alleen als ~/appportal/mijnagents-data/.built gelijk is aan
    HEAD:mijnagents (zoals deploy.sh het schrijft); anders 'geweigerd: bord nog niet herbouwd', exit 2, en de crontab
    blijft zoals ze was. Zonder --zet toont het de waarschuwing en zet het niets. Een echte git-boom in een tijdelijke map,
    een nagebootste crontab; geen netwerk."""
    M = _zetscript()
    map_ = tempfile.mkdtemp(prefix="built-")
    repo = os.path.join(map_, "appportal")
    os.makedirs(os.path.join(repo, "mijnagents"))
    with open(os.path.join(repo, "mijnagents", "app.py"), "w", encoding="utf-8") as f:
        f.write("# proef\n")
    git = ["git", "-C", repo, "-c", "user.name=Proefpersoon Zeta", "-c", "user.email=zeta@proef.test",
           "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
    subprocess.run(["git", "init", "-q", repo], check=True, capture_output=True)
    subprocess.run(git + ["add", "-A"], check=True, capture_output=True)
    subprocess.run(git + ["commit", "-qm", "proef"], check=True, capture_output=True)
    boom = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD:mijnagents"], check=True, capture_output=True, text=True).stdout.strip()
    built = os.path.join(repo, "mijnagents-data", ".built")
    os.makedirs(os.path.dirname(built))
    bin_ = os.path.join(map_, "bin")
    os.makedirs(bin_)
    with open(os.path.join(bin_, "crontab"), "w", encoding="utf-8") as f:
        f.write(NEP_CRONTAB)
    os.chmod(os.path.join(bin_, "crontab"), 0o755)
    py, rn, lg = VM["python"], VM["runner"].rstrip("/"), VM["logmap"].rstrip("/")
    los = [f"0 7 * * 1-5 {py} {rn}/dagbundelaar.py >> {lg}/dagbundelaar.log 2>&1",
           f"0 7,13 * * * {py} {rn}/fathom_wacht.py >> {lg}/fathom_wacht.log 2>&1",
           f"15 7,13 * * * {py} {rn}/zoom_wacht.py >> {lg}/zoom_wacht.log 2>&1"]
    cron = os.path.join(map_, "crontab.txt")
    oud_env = {k: os.environ.get(k) for k in ("PATH", "CRON_PROEF")}
    os.environ["PATH"], os.environ["CRON_PROEF"] = bin_ + os.pathsep + os.environ.get("PATH", ""), cron
    M.REPO, M.BUILT = repo, built
    try:
        for naam, gebouwd, argv, code in (("afwijkend, --zet", "ander\n", ["--zet"], 2), ("ontbreekt, --zet", None, ["--zet"], 2),
                                          ("afwijkend, tonen", "ander\n", [], 0), ("gelijk, --zet", boom + "\n", ["--zet"], 0)):
            with open(cron, "w", encoding="utf-8") as f:
                f.write("MAILTO=''\n" + "\n".join(los) + "\n")
            if gebouwd is None:
                if os.path.exists(built):
                    os.remove(built)
            else:
                with open(built, "w", encoding="utf-8") as f:
                    f.write(gebouwd)
            with redirect_stdout(io.StringIO()) as uit, redirect_stderr(io.StringIO()) as fout:
                assert M.main(argv) == code, (naam, uit.getvalue(), fout.getvalue())
            na = open(cron, encoding="utf-8").read()
            if naam == "gelijk, --zet":
                assert M.BEGIN in na and "fathom_wacht.py >>" not in na and "gezet en nagelezen" in uit.getvalue(), (naam, na)
                assert "niet herbouwd" not in fout.getvalue(), fout.getvalue()
            else:
                assert M.BEGIN not in na and na.count("fathom_wacht.py") == 1, (naam, na)
                assert "bord nog niet herbouwd" in fout.getvalue(), (naam, fout.getvalue())
                if code == 2:
                    assert "geweigerd: bord nog niet herbouwd" in fout.getvalue(), (naam, fout.getvalue())
            assert boom not in uit.getvalue() + fout.getvalue(), "geen boom-hash op het scherm"
    finally:
        for k, v in oud_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_vaststelling_ochtend_en_nacht():
    """Ontwerp dagvaststelling v1.2 (Codex D1, D2): de ochtendronde bundelt en stelt gisteren vast in een ronde met taak
    'bundels en dagvaststelling'; de nachtronde bundelt niet en heet 'dagvaststelling' (ochtend.NACHTTAAK). Een item
    dagvaststelling komt nooit in een bundel en wordt nooit opgepakt; de oude noden over WhatsApp-exports en Xelion zijn
    weg (die meldt de dagvaststelling zelf, naar de hartslag van hun wacht)."""
    vast = item(31, "dagbundelaar", "mehdi", "dagvaststelling", f"Dag {DAG} vastgesteld", sleutel=DAG,
                inhoud="# Dag vastgesteld", uniek=f"vaststelling:{DAG}")
    nb = bundelen(DAG, NepBord([WERK, vast]))
    assert nb.harten[-1]["taak"] == "bundels en dagvaststelling" and nb.harten[-1]["fout"] is None, nb.harten
    assert ("vastleggen", [DAG]) in nb.logs, nb.logs
    assert 31 not in nb.opgepakt and all(vast["titel"] not in tekst_van(b) for b in nb.bundels), "vaststelling gebundeld"
    noden = " ".join(n["tekst"] for n in nb.harten[-1]["nood"])
    assert "chat-export" not in noden and "Xelion" not in noden, noden
    nb = bundelen(DAG, NepBord([WERK, vast]), nacht=True)
    import ochtend
    assert nb.harten[-1]["taak"] == ochtend.NACHTTAAK and not nb.bundels and not nb.opgepakt, nb.harten


def test_nachtketen_in_het_beheerde_blok():
    """Codex F9: de nachtketen staat in het beheerde blok (anders weigert het zetscript haar als onbekende planning van
    keten.py). Het zetscript aanvaardt het blok zoals het tot 26-10-2026 op de VM stond (BLOK_VOOR_NACHT) en vervangt
    het door het blok met de nachtketen; een losse nachtregel buiten het blok weigert het."""
    M = _zetscript()
    cron = open(os.path.join(PLANNING, "gesprekken.cron"), encoding="utf-8").read().splitlines()
    assert cronregel("keten.py --nacht") == NACHTKETEN and cronregel("keten.py") == KETEN
    bode = f"* * * * * {PY} {RN}/bode.py >> {LG}/bode.log 2>&1"
    voor = ["MAILTO=''", bode, "", M.BEGIN, TIJDEN, KETEN, M.EINDE]
    assert list(M.BLOK_VOOR_NACHT) == [TIJDEN, KETEN]
    doel, oud = M.samenvoegen(voor, cron)
    assert oud == 0 and doel[doel.index(M.BEGIN):] == [M.BEGIN, TIJDEN, KETEN, NACHTKETEN, M.EINDE], doel
    try:
        M.samenvoegen(voor + [NACHTKETEN], cron)
        raise AssertionError("een losse nachtregel buiten het blok moet geweigerd worden")
    except ValueError as e:
        assert "keten.py buiten het blok" in str(e), e


class GroteBak(NepBord):
    """Een bord zoals het echte: hoogstens n (500) items per lezing, nieuwste eerst, en terugbladeren met tot_id."""

    def call(self, pad, payload=None, method=None):
        if pad.startswith("/api/klaarzet?") and "soort=zoom" not in pad:
            self.gelezen.append(pad)
            q = dict(x.split("=", 1) for x in pad.split("?", 1)[1].split("&"))
            lijst = sorted((it for it in self.alle if "tot_id" not in q or it["id"] < int(q["tot_id"])),
                           key=lambda it: it["id"], reverse=True)
            return {"items": [dict(it) for it in lijst[:min(int(q.get("n", 100)), 500)]]}
        return super().call(pad, payload, method)


def test_db7_ochtendronde_bladert_terug():
    """DB-7 (T-0120): het bord geeft hoogstens 500 items per lezing. Een afspraak die De Agendawacht dagen vooraf
    klaarzette, viel buiten de laatste 500 (gemeten: 19-10 12 afspraken gemist). Nu bladert de ochtendronde terug met
    tot_id, tot een item dat meer dan twee weken voor de dag gemaakt werd: de afspraak staat in de bundel en gaat op
    opgepakt."""
    afspraak = dict(item(900, "agenda-wacht", "h-architects", "afspraak", "2026-10-20 10:00 werfbezoek 2531", sleutel="2531",
                         inhoud={"datum": DAG, "start": f"{DAG}T10:00:00+02:00"}, uniek="agenda:werk:a5"), ts="2026-10-15T07:00:00")
    oud = dict(item(1, "agenda-wacht", "h-architects", "afspraak", "2026-10-20 08:00 te oud", sleutel="2531",
                    inhoud={"datum": DAG}, uniek="agenda:werk:a1"), ts="2026-09-01T07:00:00")
    # nieuwste eerst: 700 en 600 nieuwere items, de afspraak, 500 items van voor de grens, en een heel oude afspraak
    bak = [dict(item(2000 + i, "mail-mch", "mehdi", "mail", f"mail {i}", sleutel="2026-10-21"), ts="2026-10-21T08:00:00")
           for i in range(700)]
    bak += [dict(item(1000 + i, "mail-mch", "mehdi", "mail", f"mail {i}", sleutel="2026-10-16"), ts="2026-10-16T08:00:00")
            for i in range(600)]
    bak += [dict(item(300 + i, "mail-mch", "mehdi", "mail", f"oude mail {i}", sleutel="2026-09-20"), ts="2026-09-20T08:00:00")
            for i in range(500)]
    nb = bundelen(DAG, GroteBak(bak + [afspraak, oud]))
    bundel = next(b for b in nb.bundels if b["uniek"] == f"bundel:{DAG}:2531")
    assert afspraak["titel"] in bundel["inhoud"] and 900 in nb.opgepakt, (bundel, nb.opgepakt)
    lezingen = [p for p in nb.gelezen if p.startswith("/api/klaarzet?status=alle")]
    assert len(lezingen) == 3 and "tot_id=" in lezingen[1], lezingen
    assert oud["titel"] not in bundel["inhoud"] and 1 not in nb.opgepakt, "voor de grens leest ze niet verder"
    noden = [n["tekst"] for n in nb.harten[-1]["nood"]]
    assert not [t for t in noden if "klaarzetbak" in t], noden
    # na 40 bladzijden nog niet aan de grens: een nood, geen stille gaten
    vol = [dict(item(30000 - i, "mail-mch", "mehdi", "mail", "m", sleutel="2026-10-21"), ts="2026-10-21T08:00:00")
           for i in range(40 * 500 + 1)]
    nb = bundelen(DAG, GroteBak(vol))
    noden = [n["tekst"] for n in nb.harten[-1]["nood"]]
    assert [t for t in noden if t.startswith("Ochtendronde las de klaarzetbak niet tot de grens")], noden


def test_db3_maandag_bundelt_het_weekend():
    """DB-3 (T-0120): de ochtendronde draait alleen op werkdagen (keten.py) en bundelde alleen gisteren, dus vrijdag en
    zaterdag kregen nooit een Dagverslag (oktober: 10 van de 31 dagen) en hun items bleven op klaar. Nu bundelt ze gisteren
    en elke dag ervoor zonder Dagverslag, tot de vorige geslaagde ochtendronde, oplopend. Een dinsdag geeft er een."""
    donderdag = item(60, "dagbundelaar", "mehdi", "dagbundel", "Dagverslag 2026-10-22", sleutel="2026-10-22",
                     uniek="dagverslag:2026-10-22", status="klaar")
    werk = {d: item(61 + i, "fathom-wacht", "h-architects", "transcript", f"{d}T11:00 Fathom: klant 2531 · overleg", sleutel="2531",
                    inhoud={"datum": d, "start": "11:00"}, uniek=f"fathom:{d}")
            for i, d in enumerate(("2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25"))}
    oud = (D.V.gisteren, D.DAG_GEGEVEN)
    try:
        D.V.gisteren = lambda nu: "2026-10-25"
        nb = NepBord([donderdag] + list(werk.values()))
        bundelen("2026-10-25", nb, gepland=True)
        verslagen = [b["uniek"] for b in nb.bundels if b["uniek"].startswith("dagverslag:")]
        assert verslagen == ["dagverslag:2026-10-23", "dagverslag:2026-10-24", "dagverslag:2026-10-25"], verslagen
        assert sorted(nb.opgepakt) == [62, 63, 64], nb.opgepakt
        assert all(f"bundel:{d}:2531" in {b["uniek"] for b in nb.bundels} for d in ("2026-10-23", "2026-10-24", "2026-10-25"))
        assert nb.harten[-1]["fout"] is None and "2026-10-24:" in nb.harten[-1]["detail"], nb.harten[-1]
        # dinsdag: zondag heeft zijn Dagverslag, dus alleen gisteren
        D.V.gisteren = lambda nu: "2026-10-26"
        zondag = item(70, "dagbundelaar", "mehdi", "dagbundel", "Dagverslag 2026-10-25", sleutel="2026-10-25",
                      uniek="dagverslag:2026-10-25", status="klaar")
        nb = NepBord([zondag, item(71, "fathom-wacht", "h-architects", "transcript", "2026-10-26T11:00 Fathom: klant 2531",
                                   sleutel="2531", inhoud={"datum": "2026-10-26"}, uniek="fathom:26")])
        bundelen("2026-10-26", nb, gepland=True)
        verslagen = [b["uniek"] for b in nb.bundels if b["uniek"].startswith("dagverslag:")]
        assert verslagen == ["dagverslag:2026-10-26"], verslagen
        # na een week zonder geslaagde ochtend: hoogstens BUNDEL_INHAAL dagen
        nb = NepBord([])
        bundelen("2026-10-26", nb, gepland=True)
        verslagen = [b["uniek"] for b in nb.bundels if b["uniek"].startswith("dagverslag:")]
        assert len(verslagen) == D.BUNDEL_INHAAL and verslagen[-1] == "dagverslag:2026-10-26", verslagen
    finally:
        D.V.gisteren, D.DAG_GEGEVEN = oud


DAGBRONSOORTEN = ("afspraak", "transcript", "zoom", "foto", "gezondheid")


def agentnamen_uit_de_code():
    """{naam: [bestanden]} van elke agent in de runner en op de Mac (NAAM = "..." of bord.Agent("..."))."""
    import glob
    import re
    uit = {}
    for pad in sorted(glob.glob(os.path.join(RUNNER, "*.py")) + glob.glob(os.path.join(RUNNER, "mac", "*.py"))):
        bron = open(pad, encoding="utf-8").read()
        for naam in re.findall(r'^NAAM = "([a-z0-9-]+)"', bron, re.M) + re.findall(r'bord\.Agent\("([a-z0-9-]+)"\)', bron):
            uit.setdefault(naam, []).append(pad)
    return uit


def test_vol6_alleen_de_bronnen_van_de_dag():
    """VOL-6 (T-0120): bundelen() bundelde elk item van de dag van elke agent en zette het op opgepakt, ook van agents
    buiten de groep (werfverslag-voorbereider, archivaris, wagenpark-wacht, contracten-agent, ...): die verdwenen zonder
    tegel. Tellen per van op het bord kon niet (de lezing van de bord-databank werd geweigerd); de witte lijst komt dus
    uit de code: de agents die een bron van de dag klaarzetten (afspraak, transcript, Zoom-dagregel, foto, gezondheid),
    plus het Commandocentrum, waarvan de barsten-en-scheurenketen ongewijzigd blijft (test_commandocentrum.py)."""
    import re
    namen = agentnamen_uit_de_code()
    bron = {pad: open(pad, encoding="utf-8").read() for paden in namen.values() for pad in paden}
    makers = {n for n, paden in namen.items() for pad in paden for s in DAGBRONSOORTEN
              if f'"soort": "{s}"' in bron[pad] and re.search(rf'^NAAM = "{n}"', bron[pad], re.M)}
    assert makers == {"agenda-wacht", "fathom-wacht", "plaud-wacht", "zoom-wacht", "icloud-wacht", "gezondheid-wacht"}, makers
    assert "wagenpark-wacht" in namen and "werfverslag-voorbereider" in namen, "de afleiding vindt ook de anderen"
    alle = [item(100 + i, n, "mehdi", "proef", f"proefitem van {n}", sleutel=DAG, uniek=f"proef:{n}")
            for i, n in enumerate(sorted(namen))]
    nb = bundelen(DAG, NepBord(alle))
    opgepakt = {alle[kid - 100]["van"] for kid in nb.opgepakt}
    assert opgepakt == makers | {"commandocentrum"}, sorted(opgepakt ^ (makers | {"commandocentrum"}))
    tekst = "\n".join(b["inhoud"] for b in nb.bundels)
    assert "proefitem van wagenpark-wacht" not in tekst and "proefitem van agenda-wacht" in tekst, tekst
    # het geval van de meting: een item van De Wagenparkwacht met een datum als sleutel
    wagen = item(1, "wagenpark-wacht", "mehdi", "liters", "Tankbeurt proefwagen", sleutel=DAG, inhoud={"datum": DAG})
    nb = bundelen(DAG, NepBord([wagen, WERK]))
    assert 1 not in nb.opgepakt and 3 in nb.opgepakt, nb.opgepakt
    # B&S: een taak van het Commandocentrum en een afspraak met dossier gaan zoals voor VOL-6 mee; een cc-taak blijft open
    bs = [item(11, "commandocentrum", "andere-agent", "taak", "Gewone taak", sleutel="47035", inhoud={"datum": DAG},
               uniek="zelfstandige-taak"),
          item(12, "agenda-wacht", "tkn", "afspraak", "Fictief bezoek", sleutel="47035", inhoud={"datum": DAG}, uniek="afspraak:test"),
          item(13, "commandocentrum", "tkn", "impuls", "Voorbereiding", sleutel="47035", inhoud={"datum": DAG},
               uniek="cc:afspraak:bs1:voorbereiding")]
    nb = bundelen(DAG, NepBord(bs))
    assert sorted(nb.opgepakt) == [11, 12], nb.opgepakt


def test_db2_geen_vaste_plaudmelding():
    """DB-2 (T-0120): tot 01-11-2026 zette elke ochtendronde zonder meting de nood 'Plaud-opnames komen pas als de
    Plaud-routine op claude.ai draait' (wie mehdi). Die zei niets over de echte stand; De Plaudwacht meldt die zelf. Een
    Plaud-transcript wordt nog gewoon gebundeld."""
    plaud = item(51, "plaud-wacht", "h-architects", "transcript", "2026-10-20 09:00 Plaud: werfoverleg", sleutel="2531",
                 inhoud={"datum": DAG, "start": "09:00", "minuten": 20}, uniek="plaud:51")
    for alle in ([WERK], [WERK, plaud]):
        nb = bundelen(DAG, NepBord(alle))
        noden = [n["tekst"] for n in nb.harten[-1]["nood"]]
        assert not [t for t in noden if "Plaud" in t], noden
    assert any(plaud["titel"] in b["inhoud"] for b in nb.bundels if b["uniek"] == f"bundel:{DAG}:2531"), nb.bundels


def test_bron_houdt_de_bestaande_grendels():
    """test_postvak.py en test_locatielezers.py lezen de bron van De Dagbundelaar; hun grendels blijven staan."""
    bron = open(os.path.join(RUNNER, "dagbundelaar.py"), encoding="utf-8").read()
    assert '"mail-regisseur" in (it.get("van"), it.get("voor"))' in bron
    assert "LC.dag_heeft_dagboek(DAG, items)" in bron and 'or it.get("soort") == "locatie"' not in bron
    assert "laatste stap van de ochtendketen" in bron and "keten.py" in bron and "gesprekken.lock" in bron, \
        "Z14 punt 6 en RZ4-04: de docstring zegt wanneer hij draait"
    assert "07:05" not in bron and "90 minuten" not in bron, "de eigen cronregel van voor RZ4-04 bestaat niet meer"
    assert "\N{EM DASH}" not in bron and "\N{EN DASH}" not in bron


if __name__ == "__main__":
    import traceback
    goed = fout = 0
    for naam, f in sorted(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                f()
                goed += 1
                print(f"   geslaagd  {naam}")
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"   GEFAALD   {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)

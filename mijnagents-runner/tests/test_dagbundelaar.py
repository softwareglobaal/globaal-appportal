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
- RZ2-03: De Dagbundelaar draait binnen het slot van de gesprekkenketen; krijgt hij het slot niet binnen 90 minuten
  (RZ3-03, tot 22-10-2026 60), dan start hij niet en staat dat in zijn logboek. Het zetscript zet die regel, ook over
  het oude blok heen;
- RZ3-01: een item met inhoud.afdeling prive is privé, ook bij prive=false;
- RZ3-02: het zetscript aanvaardt alleen precies de drie oude regels of het beheerde blok; elke andere vorm weigert het.

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


def bundelen(dag, nb):
    oud = (bord.call, bord.opgepakt, D.DAG)
    bord.call = nb.call
    bord.opgepakt = lambda kid, door: nb.opgepakt.append(kid)
    D.DAG = dag
    D.ag.klaarzet = lambda items: nb.bundels.extend(items) or {"nieuw": len(items)}
    D.ag.hartslag = lambda *a, **k: nb.harten.append(k)
    D.ag.log = lambda *a, **k: nb.logs.append(a)
    D.ag.log_verstuur = lambda: None
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            D.main()
    finally:
        bord.call, bord.opgepakt, D.DAG = oud
        for naam in ("klaarzet", "hartslag", "log", "log_verstuur"):
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
    regels = [r for r in open(os.path.join(PLANNING, "gesprekken.cron"), encoding="utf-8").read().splitlines()
              if r.strip() and not r.startswith("#")]
    gevonden = [r for r in regels if script in r]
    assert len(gevonden) == 1, gevonden
    return gevonden[0]


def cron_draaien(proef, exit_python=0):
    """De echte regel van De Dagbundelaar uit planning/gesprekken.cron, zoals cron ze draait (/bin/sh -c, zonder de vijf
    tijdvelden), met de paden van de VM vervangen door een tijdelijke map. Geeft (spoor, logboek)."""
    map_ = tempfile.mkdtemp(prefix="cron-")
    for naam, tekst in (("flock", NEP_FLOCK), ("python", NEP_PYTHON)):
        with open(os.path.join(map_, naam), "w", encoding="utf-8") as f:
            f.write(tekst)
        os.chmod(os.path.join(map_, naam), 0o755)
    regel = cronregel("dagbundelaar.py").split(None, 5)[5]
    for sleutel, pad in (("flock", os.path.join(map_, "flock")), ("python", os.path.join(map_, "python")),
                         ("slot", os.path.join(map_, "gesprekken.lock")), ("logmap", map_ + os.sep), ("runner", "/runner/")):
        assert VM[sleutel] in regel, (sleutel, regel)
        regel = regel.replace(VM[sleutel], pad)
    spoor = os.path.join(map_, "spoor.txt")
    subprocess.run(["/bin/sh", "-c", regel], check=False, timeout=30,
                   env=dict(os.environ, FLOCK_PROEF=proef, CRON_SPOOR=spoor, NEP_EXIT=str(exit_python)))
    lees = lambda p: open(p, encoding="utf-8").read() if os.path.exists(p) else ""  # noqa: E731
    return lees(spoor).splitlines(), lees(os.path.join(map_, "dagbundelaar.log"))


def test_rz2_03_dagbundelaar_draait_binnen_het_slot():
    """RZ2-03 (bouwcontrole RZ2, 21-10-2026): de regel was 'flock -w 3600 /tmp/gesprekken.lock /bin/true; python
    dagbundelaar.py'. Het slot ging na /bin/true weer open, en na een wachttime-out startte De Dagbundelaar toch, terwijl
    de keten nog liep. Nu draait hij binnen het slot; bij een time-out start hij niet en staat dat in dagbundelaar.log.
    RZ3-03: hij wacht 5400 seconden, langer dan de keten kan duren (test_keten.py rekent het na)."""
    regel = cronregel("dagbundelaar.py")
    assert regel.startswith("5 7 * * 1-5 /usr/bin/flock -w 5400 ") and "/bin/true" not in regel, regel
    assert "na 5400 s niet vrij" in regel, "de melding in het logboek noemt dezelfde wachttijd"
    spoor, log = cron_draaien("vrij")
    assert spoor == ["slot genomen: vrij", "python /runner/dagbundelaar.py", "slot vrij"], spoor
    assert "niet gestart" not in log, log
    spoor, log = cron_draaien("bezet")
    assert spoor == ["slot genomen: bezet"], f"na een time-out start De Dagbundelaar niet: {spoor}"
    assert "De Dagbundelaar niet gestart" in log and "/gesprekken.lock" in log, log
    spoor, log = cron_draaien("vrij", exit_python=1)
    assert spoor == ["slot genomen: vrij", "python /runner/dagbundelaar.py", "slot vrij"] and "niet gestart" not in log, \
        "een fout van De Dagbundelaar zelf is geen time-out"
    assert "%" not in regel, "cron leest een % als einde van de opdracht"
    assert "\N{EM DASH}" not in regel and "\N{EN DASH}" not in regel


def test_rz2_03_zetscript_zet_de_nieuwe_regel():
    """Het zetscript (samenvoegen) zet de nieuwe regel, ook over het beheerde blok van voor RZ2-03 heen, en twee keer
    samenvoegen geeft hetzelfde."""
    spec = importlib.util.spec_from_file_location("gesprekken_cron_zetten", os.path.join(PLANNING, "gesprekken_cron_zetten.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    cron = open(os.path.join(PLANNING, "gesprekken.cron"), encoding="utf-8").read().splitlines()
    py, rn, lg = VM["python"], VM["runner"].rstrip("/"), VM["logmap"].rstrip("/")
    oud_blok = [M.BEGIN, "# 07:00 UTC is 09:00 Brussel tot en met 24-10-2026, vanaf 25-10 08:00; 13:00 UTC is 15:00, vanaf 25-10 14:00",
                f"0 7,13 * * * /usr/bin/flock -w 1800 /tmp/gesprekken.lock {py} {rn}/keten.py >> {lg}/keten.log 2>&1",
                f"5 7 * * 1-5 /usr/bin/flock -w 3600 /tmp/gesprekken.lock /bin/true; {py} {rn}/dagbundelaar.py >> {lg}/dagbundelaar.log 2>&1",
                M.EINDE]
    los = [f"0 7 * * 1-5 {py} {rn}/dagbundelaar.py >> {lg}/dagbundelaar.log 2>&1",
           f"0 7,13 * * * {py} {rn}/fathom_wacht.py >> {lg}/fathom_wacht.log 2>&1",
           f"15 7,13 * * * {py} {rn}/zoom_wacht.py >> {lg}/zoom_wacht.log 2>&1"]
    for huidig, oude_regels in ((["MAILTO=''", f"* * * * * {py} {rn}/bode.py >> {lg}/bode.log 2>&1", ""] + oud_blok, 0),
                                (["MAILTO=''"] + los, 3)):
        doel, oud = M.samenvoegen(huidig, cron)
        assert oud == oude_regels, (oud, huidig)
        bundel = [r for r in doel if "dagbundelaar.py" in r and not r.startswith("#")]
        assert bundel == [cronregel("dagbundelaar.py")], bundel
        assert not any("/bin/true" in r for r in doel) and doel.count(M.BEGIN) == 1, doel
        assert "MAILTO=''" in doel and M.samenvoegen(doel, cron) == (doel, 0), "twee keer samenvoegen geeft hetzelfde"


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


def test_bron_houdt_de_bestaande_grendels():
    """test_postvak.py en test_locatielezers.py lezen de bron van De Dagbundelaar; hun grendels blijven staan."""
    bron = open(os.path.join(RUNNER, "dagbundelaar.py"), encoding="utf-8").read()
    assert '"mail-regisseur" in (it.get("van"), it.get("voor"))' in bron
    assert "LC.dag_heeft_dagboek(DAG, items)" in bron and 'or it.get("soort") == "locatie"' not in bron
    assert "07:05 UTC" in bron and "gesprekken.lock" in bron, "Z14 punt 6: de docstring zegt wanneer hij draait"
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

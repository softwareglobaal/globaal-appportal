"""Grendels op de gesprekkenketen (ontwerp regie-zoom v1.2, 13.5 X3): keten.py en keten.json.

Een rij in de tabel status bewaart maar een hartslag; daarmee kon een mislukte of handmatige ronde na 07:00 als een
geslaagde ochtendketen tellen. keten.json is het bewijs. Deze test legt vast:

- geslaagd: De Fathomwacht en daarna De Zoomwacht, elk met exit 0; keten_id is de start, elke stap heeft exit en
  einde, en geslaagd is waar;
- een stap met exit 1 maakt de keten niet geslaagd, maar houdt de volgende stap niet tegen;
- een time-out: de stap krijgt SIGTERM (zodat De Fathomwacht zijn hartslag afsluit), daarna geldt exit 124;
- atomisch schrijven: elke versie komt via een tijdelijk bestand en os.replace; tijdens een stap staat er een volledige
  versie met einde null en geslaagd false; er blijft geen tijdelijk bestand achter;
- stopt iemand de keten zelf (SIGTERM), dan stopt de lopende stap mee en zegt keten.json: niet geslaagd;
- RZ2-02: de echte fathom_wacht.py zonder Fathom-sleutel, of met een sleutel die faalt, maakt de keten niet geslaagd;
- RZ4-04: De Dagbundelaar is de laatste stap van de ochtendketen zelf (eerste geplande uur, werkdagen in Brusselse
  tijd), na De Fathomwacht en De Zoomwacht, ook als een van die faalde, met een eigen time-out; zijn stap staat in
  keten.json, geslaagd blijft bij Fathom en Zoom, en De Regisseur (ochtend.py) leest die stap. Er is geen eigen
  cronregel meer die op het slot wacht.

Geen netwerk: de stappen zijn kleine nepscripts in een tijdelijke map, met een vaste klok. Voor RZ2-02 start het
nepscript de echte fathom_wacht.py, met een bord dat alleen afdrukt en zonder echte .env-bestanden.
Draaien: python3 mijnagents-runner/tests/test_keten.py
"""
import io
import itertools
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, RUNNER)
import keten as K  # noqa: E402

NEP = r"""
import json, os, signal, sys, time
naam = os.path.basename(__file__)
gedrag = json.load(open(os.environ["KETEN_PROEF"])).get(naam, {})
with open(os.environ["KETEN_SPOOR"], "a") as f:
    f.write(naam + " start\n")
if gedrag.get("zie"):
    with open(os.environ["KETEN_ZAG"], "w") as f:
        f.write(open(gedrag["zie"]).read())
if gedrag.get("slaap"):
    def stop(signum, frame):
        with open(os.environ["KETEN_SPOOR"], "a") as f:
            f.write(naam + " sigterm\n")
        sys.exit(128 + signum)
    signal.signal(signal.SIGTERM, stop)
    time.sleep(gedrag["slaap"])
print("uitvoer van " + naam, flush=True)
sys.exit(gedrag.get("exit", 0))
"""


UTC = timezone.utc
# Een vaste klok: elke keten start op een gekozen moment, elke volgende vraag naar de tijd is een seconde later. Zonder
# start een donderdag om 13:00 UTC, de middagketen: zo hangt een proef niet af van het uur waarop ze draait.
MIDDAG = datetime(2026, 10, 22, 13, 0, 5, tzinfo=UTC)
OCHTEND = datetime(2026, 10, 22, 7, 0, 5, tzinfo=UTC)        # donderdag, de ochtendketen
CRON_ECHT = os.path.join(RUNNER, "planning", "gesprekken.cron")


def klok(start):
    teller = itertools.count()
    return lambda: start + timedelta(seconds=next(teller))


class Proef:
    def __init__(self, gedrag):
        self.map = tempfile.mkdtemp(prefix="keten-")
        self.runners = os.path.join(self.map, "runners")
        os.makedirs(self.runners)
        for runner in ("fathom_wacht.py", "zoom_wacht.py", "dagbundelaar.py"):
            with open(os.path.join(self.runners, runner), "w", encoding="utf-8") as f:
                f.write(NEP)
        self.proef = os.path.join(self.map, "gedrag.json")
        self.spoor = os.path.join(self.map, "spoor.txt")
        self.zag = os.path.join(self.map, "zag.json")
        self.keten = os.path.join(self.map, "data", "keten.json")
        self.logmap = os.path.join(self.map, "logs")
        with open(self.proef, "w", encoding="utf-8") as f:
            json.dump(gedrag, f)
        os.environ.update(KETEN_PROEF=self.proef, KETEN_SPOOR=self.spoor, KETEN_ZAG=self.zag)

    def draai(self, stappen=None, nadruk=5, start=MIDDAG, cron=CRON_ECHT, dagbundelaar=None):
        oud = (K.HIER, K.KETEN, K.LOGMAP, K.PYTHON, K.STAPPEN, K.NADRUK, os.replace, K.nu,
               getattr(K, "CRON", None), getattr(K, "DAGBUNDELAAR", None))
        self.vervangen = []

        def vervang(a, b):
            self.vervangen.append((a, b))
            oud[6](a, b)
            json.load(open(b, encoding="utf-8"))   # na elke vervanging een hele versie
        K.HIER, K.KETEN, K.LOGMAP, K.PYTHON, K.NADRUK = self.runners, self.keten, self.logmap, sys.executable, nadruk
        K.nu, K.CRON = klok(start), cron
        if stappen:
            K.STAPPEN = stappen
        if dagbundelaar:
            K.DAGBUNDELAAR = dagbundelaar
        os.replace = vervang
        try:
            with redirect_stdout(io.StringIO()) as self.scherm:
                code = K.main()
        finally:
            K.HIER, K.KETEN, K.LOGMAP, K.PYTHON, K.STAPPEN, K.NADRUK, os.replace, K.nu, K.CRON, K.DAGBUNDELAAR = oud
        return code, json.load(open(self.keten, encoding="utf-8"))

    def spoorregels(self):
        return open(self.spoor, encoding="utf-8").read().splitlines() if os.path.exists(self.spoor) else []


def test_geslaagde_keten():
    p = Proef({})
    code, k = p.draai()
    assert code == 0 and k["geslaagd"] is True, k
    assert set(k) == {"keten_id", "start", "einde", "stappen", "geslaagd"}, k
    assert k["keten_id"] == k["start"] and k["einde"] >= k["start"], k
    assert list(k["stappen"]) == ["fathom-wacht", "zoom-wacht"] and all(s["exit"] == 0 and s["einde"] for s in k["stappen"].values()), k
    assert p.spoorregels() == ["fathom_wacht.py start", "zoom_wacht.py start"], "Fathom eerst, dan Zoom"
    assert "uitvoer van fathom_wacht.py" in open(os.path.join(p.logmap, "fathom_wacht.log"), encoding="utf-8").read()
    assert "uitvoer van zoom_wacht.py" in open(os.path.join(p.logmap, "zoom_wacht.log"), encoding="utf-8").read()


def test_een_stap_met_exit_1():
    for falend in ("zoom_wacht.py", "fathom_wacht.py"):
        p = Proef({falend: {"exit": 1}})
        code, k = p.draai()
        assert code == 1 and k["geslaagd"] is False, k
        verwacht = {"fathom-wacht": 1 if falend == "fathom_wacht.py" else 0, "zoom-wacht": 1 if falend == "zoom_wacht.py" else 0}
        assert {n: s["exit"] for n, s in k["stappen"].items()} == verwacht, k
        assert p.spoorregels() == ["fathom_wacht.py start", "zoom_wacht.py start"], "een falende stap houdt de volgende niet tegen"


def test_time_out():
    p = Proef({"fathom_wacht.py": {"slaap": 60}})
    begin = time.monotonic()
    code, k = p.draai(stappen=(("fathom-wacht", "fathom_wacht.py", 1, "fathom_wacht.log"), ("zoom-wacht", "zoom_wacht.py", 30, "zoom_wacht.log")))
    assert time.monotonic() - begin < 20, "de time-out hield de stap niet tegen"
    assert code == 1 and k["geslaagd"] is False and k["stappen"]["fathom-wacht"]["exit"] == K.TIJDSLIMIET == 124, k
    assert k["stappen"]["zoom-wacht"]["exit"] == 0, k
    assert "fathom_wacht.py sigterm" in p.spoorregels(), "eerst SIGTERM, zodat De Fathomwacht zijn hartslag afsluit (J1)"


def test_atomisch_en_tussenstand():
    p = Proef({})
    gedrag = {"fathom_wacht.py": {"zie": None}}
    p2 = Proef(gedrag)
    gedrag["fathom_wacht.py"]["zie"] = p2.keten
    with open(p2.proef, "w", encoding="utf-8") as f:
        json.dump(gedrag, f)
    code, k = p2.draai()
    tussen = json.load(open(p2.zag, encoding="utf-8"))
    assert tussen["geslaagd"] is False and tussen["einde"] is None and tussen["stappen"] == {}, tussen
    assert tussen["keten_id"] == k["keten_id"], "dezelfde keten"
    assert len(p2.vervangen) == 4, f"start, twee stappen en het einde: {len(p2.vervangen)}"
    for a, b in p2.vervangen:
        assert b == p2.keten and os.path.dirname(a) == os.path.dirname(p2.keten) and a != b, (a, b)
    assert os.listdir(os.path.dirname(p2.keten)) == ["keten.json"], "geen tijdelijk bestand achtergelaten"
    assert code == 0 and p.map != p2.map


STUUR = r"""
import importlib.util, signal, sys
spec = importlib.util.spec_from_file_location("keten", sys.argv[1])
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)
K.HIER, K.KETEN, K.LOGMAP, K.NADRUK = sys.argv[2], sys.argv[3], sys.argv[4], 5
signal.signal(signal.SIGTERM, K.stop_bij_sigterm)
sys.exit(K.main())
"""


def test_keten_zelf_gestopt():
    p = Proef({"fathom_wacht.py": {"slaap": 60}})
    proc = subprocess.Popen([sys.executable, "-B", "-c", STUUR, os.path.join(RUNNER, "keten.py"), p.runners, p.keten, p.logmap],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=dict(os.environ))
    try:
        einde = time.monotonic() + 20
        while time.monotonic() < einde and "fathom_wacht.py start" not in p.spoorregels():
            time.sleep(0.1)
        proc.send_signal(signal.SIGTERM)
        uit, fout = proc.communicate(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 128 + signal.SIGTERM, (proc.returncode, fout)
    k = json.load(open(p.keten, encoding="utf-8"))
    assert k["geslaagd"] is False and k["einde"], k
    assert "fathom_wacht.py sigterm" in p.spoorregels(), "de lopende stap stopt mee"
    assert "zoom_wacht.py start" not in p.spoorregels(), "na een stopsignaal begint geen volgende stap"


def test_contract_met_de_regisseur():
    """keten.json zoals keten.py het echt schrijft, gelezen met de code van De Regisseur (koppelingen/ochtend.py, X3):
    een geslaagde keten telt, een keten met een falende stap niet, en de tussenstand (einde null) heet 'loopt nog'. Het
    startmoment komt uit het echte planning/gesprekken.cron. Tot 21-10-2026 toetste De Regisseur alleen tegen een
    keten.json die hij zelf met de hand maakte."""
    sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
    import ochtend as O  # noqa: PLC0415
    from datetime import timedelta  # noqa: PLC0415
    assert O.ketenstart(O.lees_cron()) == (7, 0), "07:00 UTC, de regel met keten.py"
    p = Proef({})
    p.draai()
    k = O.lees_keten(p.keten)
    start = O.tijdstip(k["start"])
    assert start is not None and start.utcoffset() == timedelta(0), k["start"]
    assert O.keten_geslaagd(k, start - timedelta(seconds=1)) == (True, ""), k
    assert O.keten_geslaagd(k, start + timedelta(seconds=1))[0] is False, "een keten van voor het startmoment telt niet"
    p = Proef({"zoom_wacht.py": {"exit": 1}})
    p.draai()
    k = O.lees_keten(p.keten)
    assert O.keten_geslaagd(k, O.tijdstip(k["start"]) - timedelta(seconds=1)) == (False, "gesprekkenketen niet geslaagd"), k
    p2 = Proef({"fathom_wacht.py": {"zie": None}})
    with open(p2.proef, "w", encoding="utf-8") as f:
        json.dump({"fathom_wacht.py": {"zie": p2.keten}}, f)
    p2.draai()
    tussen = O.lees_keten(p2.zag)
    assert O.keten_geslaagd(tussen, O.tijdstip(tussen["start"]) - timedelta(seconds=1)) == (False, "gesprekkenketen loopt nog"), tussen


# De echte fathom_wacht.py als stap van de keten: een bord dat alleen afdrukt (in het logboek van de stap), geen echte
# .env-bestanden, geen sleutel; met sleutel_faalt een sleutel die Fathom weigert (401).
ECHTE_FATHOMWACHT = r"""
import json, os, runpy, sys, tempfile
sys.dont_write_bytecode = True
os.environ["HOME"] = tempfile.mkdtemp(prefix="thuis-")
os.environ.pop("FATHOM_API_KEYS", None)
RUNNER = os.environ["KETEN_ECHTE_RUNNER"]
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import bord, fathom
bord.call = lambda pad, payload=None, method=None: print("BORD " + json.dumps([pad, payload]), flush=True) or {}
if json.load(open(os.environ["KETEN_PROEF"])).get("fathom_wacht.py", {}).get("sleutel_faalt"):
    import urllib.error
    os.environ["FATHOM_API_KEYS"] = "proefsleutel"

    def geweigerd(sinds, met_transcript=False):
        raise urllib.error.HTTPError("https://api.fathom.ai/external/v1/meetings", 401, "Unauthorized", None, None)

    fathom.gesprekken = geweigerd
    bord.Agent.werkwijze = lambda self, *a, **k: "# Fathomwacht\n\nGeen personentabel."
runpy.run_path(os.path.join(RUNNER, "fathom_wacht.py"), run_name="__main__")
"""


def test_rz2_02_fathom_niet_gelezen_is_geen_geslaagde_keten():
    """RZ2-02 (bouwcontrole RZ2, 21-10-2026): zonder Fathom-sleutel eindigde fathom_wacht.py met exit 0. Werkte Zoom, dan
    schreef keten.py 'geslaagd' en kon het ochtendbericht voor 10:30 vertrekken zonder Fathom-lezing. Nu eindigt een ronde
    die Fathom niet kon lezen niet op 0, en is de keten niet geslaagd; de hartslag (fout, zonder noodlijst) blijft zoals
    voordien. Een sleutel die faalt, gaf al een fout (exit 1); dat blijft zo. Sinds NA09-rest (01-11-2026) zet de gedeelde
    ronde die fout, met haar eigen taak en de fout in het detail."""
    for gedrag, taak in (({}, "geen Fathom-sleutel"), ({"sleutel_faalt": True}, "Fathom ophalen")):
        p = Proef({"fathom_wacht.py": gedrag})
        with open(os.path.join(p.runners, "fathom_wacht.py"), "w", encoding="utf-8") as f:
            f.write(ECHTE_FATHOMWACHT)
        os.environ["KETEN_ECHTE_RUNNER"] = RUNNER
        code, k = p.draai()
        log = open(os.path.join(p.logmap, "fathom_wacht.log"), encoding="utf-8").read()
        statussen = [json.loads(r[5:])[1] for r in log.splitlines() if r.startswith("BORD ") and json.loads(r[5:])[0] == "/agent-status"]
        assert statussen and statussen[-1]["status"] == "fout" and statussen[-1]["taak"] == taak, (gedrag, statussen, log[-2000:])
        assert "nood" not in statussen[-1], f"de hartslag blijft zoals voordien, zonder noodlijst: {statussen[-1]}"
        assert k["stappen"]["fathom-wacht"]["exit"] != 0, (gedrag, k, log[-2000:])
        assert k["stappen"]["zoom-wacht"]["exit"] == 0, "Zoom werkte"
        assert code == 1 and k["geslaagd"] is False, (gedrag, k)


def test_rz4_04_dagbundelaar_als_laatste_stap_van_de_ochtendketen():
    """RZ4-04 (herstelcontrole van Codex, besluit van de regie 22-10-2026): De Dagbundelaar had een eigen cronregel die
    op het slot van de keten wachtte. Een handmatige ronde kan dat slot 1800 s vasthouden; dan wachtte ook de keten, en
    kon De Dagbundelaar het slot vóór de keten krijgen (een dagverslag zonder de gesprekken van die ochtend) of na zijn
    wachttijd afhaken. Nu is hij de laatste stap van keten.py zelf, in de ochtendketen op een werkdag: na De Fathomwacht en
    De Zoomwacht, met zijn eigen logboek, en zijn stap staat in keten.json met exit en einde."""
    p = Proef({})
    code, k = p.draai(start=OCHTEND)
    assert code == 0 and k["geslaagd"] is True, k
    assert list(k["stappen"]) == ["fathom-wacht", "zoom-wacht", "dagbundelaar"], k
    assert p.spoorregels() == ["fathom_wacht.py start", "zoom_wacht.py start", "dagbundelaar.py start"], p.spoorregels()
    stap = k["stappen"]["dagbundelaar"]
    assert set(stap) == {"exit", "einde"} and stap["exit"] == 0, stap
    assert k["stappen"]["zoom-wacht"]["einde"] <= stap["einde"] <= k["einde"], "na Zoom, en de keten eindigt pas na hem"
    assert "uitvoer van dagbundelaar.py" in open(os.path.join(p.logmap, "dagbundelaar.log"), encoding="utf-8").read()


def test_rz4_04_dagbundelaar_ook_na_een_falende_stap():
    """Een eerdere stap die faalt of te lang loopt, houdt De Dagbundelaar niet tegen: hij meldt zelf wat ontbreekt
    (Zoom-dagregel ontbreekt). Faalt hij zelf, dan blijft 'geslaagd' bij De Fathomwacht en De Zoomwacht: het
    ochtendbericht leest zijn stap apart (ochtend.py)."""
    for gedrag in ({"fathom_wacht.py": {"exit": 1}}, {"zoom_wacht.py": {"exit": 2}}):
        p = Proef(gedrag)
        code, k = p.draai(start=OCHTEND)
        assert code == 1 and k["geslaagd"] is False, (gedrag, k)
        assert p.spoorregels()[-1] == "dagbundelaar.py start" and k["stappen"]["dagbundelaar"]["exit"] == 0, (gedrag, k)
    p = Proef({"zoom_wacht.py": {"slaap": 60}})
    code, k = p.draai(start=OCHTEND, stappen=(("fathom-wacht", "fathom_wacht.py", 30, "fathom_wacht.log"),
                                              ("zoom-wacht", "zoom_wacht.py", 1, "zoom_wacht.log")))
    assert k["stappen"]["zoom-wacht"]["exit"] == K.TIJDSLIMIET and k["stappen"]["dagbundelaar"]["exit"] == 0, k
    p = Proef({"dagbundelaar.py": {"exit": 1}})
    code, k = p.draai(start=OCHTEND)
    assert code == 0 and k["geslaagd"] is True and k["stappen"]["dagbundelaar"]["exit"] == 1, k


def test_rz4_04_dagbundelaar_alleen_in_de_ochtendketen_op_werkdagen():
    """Alleen de keten van het eerste geplande uur (07:00 UTC uit planning/gesprekken.cron) draait De Dagbundelaar, ook
    als ze tot 1800 s op het slot wachtte, en alleen van maandag tot vrijdag in Brusselse tijd. De middagketen, het
    weekend, een keten met de hand buiten dat uur, of een planning die niet te lezen is: geen Dagbundelaar."""
    gevallen = {
        OCHTEND: True,
        datetime(2026, 10, 22, 7, 30, 0, tzinfo=UTC): True,     # 1800 s gewacht op een handmatige ronde
        datetime(2026, 10, 23, 7, 0, 5, tzinfo=UTC): True,      # vrijdag
        datetime(2026, 10, 26, 7, 0, 5, tzinfo=UTC): True,      # maandag, de eerste dag van de wintertijd
        MIDDAG: False,
        datetime(2026, 10, 24, 7, 0, 5, tzinfo=UTC): False,     # zaterdag
        datetime(2026, 10, 25, 7, 0, 5, tzinfo=UTC): False,     # zondag
        datetime(2026, 10, 22, 6, 59, 0, tzinfo=UTC): False,    # met de hand, voor het geplande uur
        datetime(2026, 10, 22, 8, 0, 5, tzinfo=UTC): False,     # met de hand, na het eerste geplande uur
    }
    for start, verwacht in gevallen.items():
        p = Proef({})
        code, k = p.draai(start=start)
        assert code == 0 and ("dagbundelaar" in k["stappen"]) is verwacht, (start, k)
        assert ("dagbundelaar.py start" in p.spoorregels()) is verwacht, (start, p.spoorregels())
    p = Proef({})
    code, k = p.draai(start=OCHTEND, cron=os.path.join(p.map, "bestaat-niet.cron"))
    assert code == 0 and k["geslaagd"] is True and "dagbundelaar" not in k["stappen"], k
    assert "dagbundelaar: niet in deze keten" in p.scherm.getvalue(), "de keten zegt in keten.log waarom niet"


WOENSDAG_MIDDAG = datetime(2026, 10, 21, 13, 0, 5, tzinfo=UTC)


def test_rz4_04_inhalen_als_de_ochtendketen_hem_niet_draaide():
    """Tegenproef op RZ4-04 (22-10-2026): krijgt de ochtendketen het slot niet binnen 1800 s (een handmatige ronde die
    langer loopt), dan start keten.py die ochtend niet, en de keten van 13:00 sloeg De Dagbundelaar over ('niet de
    ochtendketen'): die dag draaide hij nergens. Nu haalt een latere keten op dezelfde Brusselse werkdag hem in als de
    vorige keten (keten.json zoals het voor deze start stond) niet van vandaag is, of geen stap dagbundelaar met exit 0
    heeft. Zonder leesbare vorige keten niet: dan is onbekend of hij al liep. Een tweede ronde op dezelfde dag is veilig:
    De Dagbundelaar zet zijn bundels klaar op een vaste uniek."""
    # 1. de ochtendketen van donderdag startte niet: de vorige keten is die van woensdag 13:00
    p = Proef({})
    code, k = p.draai(start=WOENSDAG_MIDDAG)
    assert code == 0 and "dagbundelaar" not in k["stappen"], k
    code, k = p.draai(start=MIDDAG)
    assert code == 0 and list(k["stappen"]) == ["fathom-wacht", "zoom-wacht", "dagbundelaar"], k
    assert k["stappen"]["dagbundelaar"]["exit"] == 0 and p.spoorregels()[-1] == "dagbundelaar.py start", p.spoorregels()
    assert "dagbundelaar: inhaalronde" in p.scherm.getvalue(), p.scherm.getvalue()
    # 2. de ochtendketen draaide hem met exit 0: de middagketen niet
    p = Proef({})
    p.draai(start=OCHTEND)
    code, k = p.draai(start=MIDDAG)
    assert "dagbundelaar" not in k["stappen"] and p.spoorregels().count("dagbundelaar.py start") == 1, (k, p.spoorregels())
    assert "dagbundelaar: niet in deze keten (liep vandaag al in een keten)" in p.scherm.getvalue(), p.scherm.getvalue()
    # 3. hij faalde in de ochtendketen: de middagketen draait hem opnieuw
    p = Proef({"dagbundelaar.py": {"exit": 1}})
    code, k = p.draai(start=OCHTEND)
    assert k["stappen"]["dagbundelaar"]["exit"] == 1, k
    with open(p.proef, "w", encoding="utf-8") as f:
        json.dump({}, f)
    code, k = p.draai(start=MIDDAG)
    assert k["stappen"]["dagbundelaar"]["exit"] == 0 and p.spoorregels().count("dagbundelaar.py start") == 2, k
    # 4. de ochtendketen stopte halverwege (zonder stap dagbundelaar): inhalen
    p = Proef({})
    p.draai(start=WOENSDAG_MIDDAG)
    with open(p.keten, encoding="utf-8") as f:
        half = json.load(f)
    half.update(keten_id="2026-10-22T07:00:05+00:00", start="2026-10-22T07:00:05+00:00", einde=None, geslaagd=False,
                stappen={"fathom-wacht": {"exit": 124, "einde": "2026-10-22T07:45:05+00:00"}})
    with open(p.keten, "w", encoding="utf-8") as f:
        json.dump(half, f)
    code, k = p.draai(start=MIDDAG)
    assert k["stappen"]["dagbundelaar"]["exit"] == 0, k
    # 5. geen of een onleesbare vorige keten.json: niet, want onbekend
    for inhoud in (None, "{half"):
        p = Proef({})
        if inhoud is not None:
            os.makedirs(os.path.dirname(p.keten))
            with open(p.keten, "w", encoding="utf-8") as f:
                f.write(inhoud)
        code, k = p.draai(start=MIDDAG)
        assert "dagbundelaar" not in k["stappen"], (inhoud, k)
        assert "geen leesbare vorige keten" in p.scherm.getvalue(), p.scherm.getvalue()
    # 6. niet in het weekend, en niet voor het eerste geplande uur
    for vorige, start in ((datetime(2026, 10, 23, 13, 0, 5, tzinfo=UTC), datetime(2026, 10, 24, 13, 0, 5, tzinfo=UTC)),
                          (WOENSDAG_MIDDAG, datetime(2026, 10, 22, 6, 59, 0, tzinfo=UTC))):
        p = Proef({})
        p.draai(start=vorige)
        code, k = p.draai(start=start)
        assert "dagbundelaar" not in k["stappen"] and "dagbundelaar.py start" not in p.spoorregels(), (start, k)


def test_rz4_04_dagbundelaar_met_eigen_time_out():
    p = Proef({"dagbundelaar.py": {"slaap": 60}})
    begin = time.monotonic()
    code, k = p.draai(start=OCHTEND, dagbundelaar=("dagbundelaar", "dagbundelaar.py", 1, "dagbundelaar.log"))
    assert time.monotonic() - begin < 20, "de time-out hield De Dagbundelaar niet tegen"
    assert k["stappen"]["dagbundelaar"]["exit"] == K.TIJDSLIMIET and k["geslaagd"] is True and code == 0, k
    assert "dagbundelaar.py sigterm" in p.spoorregels(), "eerst SIGTERM, zodat hij zijn hartslag kan afsluiten"
    assert K.DAGBUNDELAAR[:3] == ("dagbundelaar", "dagbundelaar.py", 900) and K.DAGBUNDELAAR[3] == "dagbundelaar.log"


def test_rz4_04_contract_met_de_regisseur():
    """keten.json met de stap dagbundelaar, gelezen met de code van De Regisseur (koppelingen/ochtend.py). Tot RZ4-04
    eiste ochtend.py een afgeronde hartslag van De Dagbundelaar na het einde van de keten. Nu De Dagbundelaar in de keten
    loopt, valt zijn hartslag altijd vóór dat einde: het ochtendbericht kwam dan pas om 10:30, met De Dagbundelaar onder
    Onbekend. Nu leest ochtend.py zijn stap: exit 0 is een afgeronde ronde, ook zonder hartslag; een andere exit staat
    onder wat ontbreekt."""
    sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
    import ochtend as O  # noqa: PLC0415
    cron = O.lees_cron()
    p = Proef({})
    p.draai(start=OCHTEND)
    k = O.lees_keten(p.keten)
    nu = O.tijdstip(k["einde"]) + timedelta(minutes=1)
    tijdens = {"dagbundelaar": {"status": "klaar", "ts": O.tijdstip(k["stappen"]["dagbundelaar"]["einde"]) - timedelta(seconds=1)}}
    for statussen in (tijdens, {}, None):
        stand = O.aan_de_beurt(nu, statussen, k, cron, False)
        assert stand["beurt"] and stand["ontbreekt"] == [] and stand["onbekend"] == [], (statussen, stand)
    p = Proef({"dagbundelaar.py": {"exit": 1}})
    p.draai(start=OCHTEND)
    k = O.lees_keten(p.keten)
    stand = O.aan_de_beurt(O.tijdstip(k["einde"]) + timedelta(minutes=1), tijdens, k, cron, False)
    assert not stand["beurt"] and stand["ontbreekt"] == ["De Dagbundelaar eindigde in de gesprekkenketen met exit 1"], stand
    laat = O.aan_de_beurt(datetime(2026, 10, 22, 8, 31, tzinfo=UTC), tijdens, k, cron, False)
    assert laat["beurt"] and laat["onbekend"] == ["De Dagbundelaar eindigde in de gesprekkenketen met exit 1"], laat
    # een ronde met de hand na die keten (De Regisseur, onder het slot) telt wel, zoals voordien
    later = {"dagbundelaar": {"status": "klaar", "ts": O.tijdstip(k["einde"]) + timedelta(minutes=5)}}
    assert O.aan_de_beurt(O.tijdstip(k["einde"]) + timedelta(minutes=6), later, k, cron, False)["beurt"]


def test_rz4_04_planning_zonder_eigen_regel_voor_de_dagbundelaar():
    """De planning heeft een regel voor de keten en geen voor De Dagbundelaar. Wacht de keten op een handmatige ronde, dan
    start ze uiterlijk na de wachttijd van haar flock; die blijft binnen het eerste geplande uur, zodat de ochtendketen
    De Dagbundelaar dan nog draait. De langste keten: de drie time-outs plus de nadruk per stap."""
    import re  # noqa: PLC0415
    regels = [r for r in open(CRON_ECHT, encoding="utf-8").read().splitlines() if r.strip() and not r.startswith("#")]
    assert not [r for r in regels if "dagbundelaar" in r], regels
    keten = [r for r in regels if "keten.py" in r and "--nacht" not in r]
    assert len(keten) == 1 and keten[0].startswith("0 7,13 * * * /usr/bin/flock -w ") and "/tmp/gesprekken.lock" in keten[0], keten
    # tegenproef op RZ4-04: een keten die het slot niet kreeg, staat in keten.log (flock -E 75 en een regel)
    assert " -E 75 /tmp/gesprekken.lock " in keten[0] and "; if [ $? -eq 75 ]; then " in keten[0], keten
    wacht = int(re.findall(r"flock -w (\d+) ", keten[0])[0])
    assert wacht < K.OCHTENDVENSTER.total_seconds() == 3600, (wacht, K.OCHTENDVENSTER)
    langste = sum(s[2] for s in K.STAPPEN + (K.DAGBUNDELAAR,)) + (len(K.STAPPEN) + 1) * K.NADRUK
    assert langste == 4890, langste


def test_nachtketen():
    """Codex F9 (ontwerp dagvaststelling v1.2): keten.py --nacht draait De Zoomwacht en daarna De Dagbundelaar --nacht,
    ook als De Zoomwacht faalt; ze schrijft nacht.json (met einde null tot het einde, zodat De Dagbundelaar ziet dat hij
    in een lopende nachtketen draait) en raakt keten.json nooit aan. Het startuur van de keten slaat de nachtregel over."""
    import sys as _sys  # noqa: PLC0415
    _sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
    import ochtend  # noqa: PLC0415
    for gedrag, verwacht in (({}, 0), ({"zoom_wacht.py": {"exit": 3}}, 1)):
        p = Proef(gedrag)
        nachtpad = os.path.join(p.map, "data", "nacht.json")
        zie = ("import json as _j; _d = _j.load(open(os.environ['KETEN_NACHT']))\n"
               "open(os.environ['KETEN_ZAG'], 'w').write(_j.dumps({'argv': sys.argv[1:], 'nacht': _d}))\n")
        with open(os.path.join(p.runners, "dagbundelaar.py"), "w", encoding="utf-8") as f:
            f.write(NEP.replace('print("uitvoer van "', zie + 'print("uitvoer van "'))
        os.environ["KETEN_NACHT"] = nachtpad
        oud = (K.HIER, K.KETEN, K.NACHT, K.LOGMAP, K.PYTHON, K.NADRUK, K.nu)
        K.HIER, K.KETEN, K.NACHT, K.LOGMAP, K.PYTHON, K.NADRUK = p.runners, p.keten, nachtpad, p.logmap, sys.executable, 5
        K.nu = klok(datetime(2026, 10, 26, 23, 30, 5, tzinfo=UTC))
        try:
            with redirect_stdout(io.StringIO()):
                code = K.nachtketen()
        finally:
            K.HIER, K.KETEN, K.NACHT, K.LOGMAP, K.PYTHON, K.NADRUK, K.nu = oud
        assert code == verwacht, (gedrag, code)
        assert p.spoorregels() == ["zoom_wacht.py start", "dagbundelaar.py start"], p.spoorregels()
        assert not os.path.exists(p.keten), "de nachtketen schrijft geen keten.json"
        zag = json.load(open(p.zag, encoding="utf-8"))
        assert zag["argv"] == ["--nacht"] and zag["nacht"]["einde"] is None, zag
        assert zag["nacht"]["stappen"]["zoom-wacht"]["exit"] == gedrag.get("zoom_wacht.py", {}).get("exit", 0), zag
        n = json.load(open(nachtpad, encoding="utf-8"))
        assert n["einde"] and list(n["stappen"]) == ["zoom-wacht", "dagbundelaar"], n
    cron = open(CRON_ECHT, encoding="utf-8").read()
    assert "keten.py --nacht" in cron and ochtend.ketenstart(cron) == (7, 0), "het startuur blijft 07:00"
    assert ochtend.ketenstart("30 23 * * * x keten.py --nacht\n0 7,13 * * * x keten.py\n") == (7, 0), "ook als de nacht eerst staat"


def test_bron():
    bron = open(os.path.join(RUNNER, "keten.py"), encoding="utf-8").read()
    assert [s[:3] for s in K.STAPPEN] == [("fathom-wacht", "fathom_wacht.py", 2700), ("zoom-wacht", "zoom_wacht.py", 1200)]
    assert "\N{EM DASH}" not in bron and "\N{EN DASH}" not in bron
    cron = open(os.path.join(RUNNER, "planning", "gesprekken.cron"), encoding="utf-8").read()
    assert "/tmp/gesprekken.lock" in cron and "keten.py" in cron


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

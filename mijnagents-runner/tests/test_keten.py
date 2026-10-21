"""Grendels op de gesprekkenketen (ontwerp regie-zoom v1.2, 13.5 X3): keten.py en keten.json.

Een rij in de tabel status bewaart maar een hartslag; daarmee kon een mislukte of handmatige ronde na 07:00 als een
geslaagde ochtendketen tellen. keten.json is het bewijs. Deze test legt vast:

- geslaagd: De Fathomwacht en daarna De Zoomwacht, elk met exit 0; keten_id is de start, elke stap heeft exit en
  einde, en geslaagd is waar;
- een stap met exit 1 maakt de keten niet geslaagd, maar houdt de volgende stap niet tegen;
- een time-out: de stap krijgt SIGTERM (zodat De Fathomwacht zijn hartslag afsluit), daarna geldt exit 124;
- atomisch schrijven: elke versie komt via een tijdelijk bestand en os.replace; tijdens een stap staat er een volledige
  versie met einde null en geslaagd false; er blijft geen tijdelijk bestand achter;
- stopt iemand de keten zelf (SIGTERM), dan stopt de lopende stap mee en zegt keten.json: niet geslaagd.

Geen netwerk en geen echte runners: de stappen zijn kleine nepscripts in een tijdelijke map.
Draaien: python3 mijnagents-runner/tests/test_keten.py
"""
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stdout

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


class Proef:
    def __init__(self, gedrag):
        self.map = tempfile.mkdtemp(prefix="keten-")
        self.runners = os.path.join(self.map, "runners")
        os.makedirs(self.runners)
        for runner in ("fathom_wacht.py", "zoom_wacht.py"):
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

    def draai(self, stappen=None, nadruk=5):
        oud = (K.HIER, K.KETEN, K.LOGMAP, K.PYTHON, K.STAPPEN, K.NADRUK, os.replace)
        self.vervangen = []

        def vervang(a, b):
            self.vervangen.append((a, b))
            oud[6](a, b)
            json.load(open(b, encoding="utf-8"))   # na elke vervanging een hele versie
        K.HIER, K.KETEN, K.LOGMAP, K.PYTHON, K.NADRUK = self.runners, self.keten, self.logmap, sys.executable, nadruk
        if stappen:
            K.STAPPEN = stappen
        os.replace = vervang
        try:
            with redirect_stdout(io.StringIO()):
                code = K.main()
        finally:
            K.HIER, K.KETEN, K.LOGMAP, K.PYTHON, K.STAPPEN, K.NADRUK, os.replace = oud
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

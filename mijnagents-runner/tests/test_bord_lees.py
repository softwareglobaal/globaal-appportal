"""Grendels op de gedeelde basis voor De Zoomwacht, De Regisseur en De Bode (ontwerp regie-zoom v1.2).

- G1, G2, T36: bord.db_lees is de enige leesweg naar de databank van het bord. Alleen lezen (mode=ro, query_only),
  alleen SELECT of WITH, en een fout geeft BordOnbekend, nooit een lege lijst. Onbekend is niet leeg (L29, L38).
- X4, T99: bord.Ronde neemt begin_noden mee, ook als de ronde stopt omdat het regelboek ontbreekt (zonder_regelboek).
  De Bode geeft zo de noden van het bellen en het alarm door, die voor zijn ronde lopen.
- J1, K3, Z13: een ronde van De Fathomwacht die met SIGTERM stopt (timeout), blijft niet op actief staan (N11), en zijn
  rijen in de gesprekkentabel dragen de bron fathom zelf, niet de stille standaard van het bord.
- BAS-01 (M3, aan de bron): De Fathomwacht schrijft van een privégesprek geen personen, thema of reden in zijn
  werkverslag, niet in de bevinding, niet in de bronregel en niet op het scherm (de cron-logboeken). Het werkverslag gaat
  naar een taalmodel (het dossier en agent_verslag van De Regisseur, De Ontwikkelaar).
- BAS-04 (J1): een kort venster (FATHOM_WACHT_DAGEN=1, een echte ronde van De Regisseur) opent geen nood over Mehdi's
  eigen sleutel en herschrijft geen dagelijks logboek van een dag die het maar voor een deel ziet.

Geen netwerk: het bord is nagebootst met BordNabootsing uit test_agentnorm.py, de databank is tijdelijk en komt uit
init_db van mijnagents/app.py als Flask er is (in de CI altijd).
Draaien: python3 mijnagents-runner/tests/test_bord_lees.py
"""
import io
import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
REPO = os.path.dirname(RUNNER)
sys.path.insert(0, HIER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import bord  # noqa: E402
from test_agentnorm import BordNabootsing, _http  # noqa: E402

MAP = tempfile.mkdtemp(prefix="bord-lees-")


# ------------------------------------------------------------------------------------------- de databank ---
def bord_db(naam):
    """Een tijdelijke BORD_DB zoals het bord ze maakt (init_db van mijnagents/app.py), met een paar rijen."""
    pad = os.path.join(MAP, naam + ".db")
    try:
        os.environ.setdefault("AGENTS_DB", os.path.join(MAP, "app-start.db"))
        sys.path.insert(0, os.path.join(REPO, "mijnagents"))
        import app  # noqa: PLC0415
        app.DB_PAD = pad
        app.init_db()
    except ImportError:
        # Lokaal zonder Flask: dezelfde tabel met de hand. In de CI is Flask er altijd (regie-grendels.yml).
        assert not os.environ.get("CI"), "Flask ontbreekt in de CI: deze toets hoort de databank uit init_db te bouwen"
        c = sqlite3.connect(pad)
        c.execute("CREATE TABLE gesprek_log (uniek TEXT PRIMARY KEY, datum TEXT, bron TEXT DEFAULT 'fathom', ts TEXT NOT NULL, "
                  "sessie TEXT DEFAULT '', dubbel_van TEXT DEFAULT '')")
        c.commit()
        c.close()
    c = sqlite3.connect(pad)
    c.executemany("INSERT INTO gesprek_log(uniek, datum, bron, ts, sessie, dubbel_van) VALUES(?,?,?,?,?,?)",
                  [("fathom:1", "2026-10-20", "fathom", "2026-10-20T08:00:00+00:00", "zoom:meeting:u1", ""),
                   ("zoom:meeting:u1", "2026-10-20", "zoom", "2026-10-20T08:05:00+00:00", "zoom:meeting:u1", "fathom:1")])
    c.commit()
    c.close()
    return pad


def met_db(pad, doe):
    echt, bord.BORD_DB = bord.BORD_DB, pad
    try:
        return doe()
    finally:
        bord.BORD_DB = echt


def onbekend(doe):
    """De reden als doe() BordOnbekend gooit; None als er een antwoord kwam."""
    try:
        doe()
    except bord.BordOnbekend as e:
        return e.reden or "(geen reden)"
    return None


def aantal(pad):
    c = sqlite3.connect(pad)
    try:
        return c.execute("SELECT count(*) FROM gesprek_log").fetchone()[0]
    finally:
        c.close()


# ------------------------------------------------------------------------------------------------- T36 ---
def test_t36_db_lees_geeft_rijen_als_dicts():
    pad = bord_db("t36-goed")
    rijen = met_db(pad, lambda: bord.db_lees("SELECT uniek, sessie, dubbel_van FROM gesprek_log WHERE uniek IN (?, ?) ORDER BY uniek",
                                             ("fathom:1", "zoom:meeting:u1")))
    assert rijen == [{"uniek": "fathom:1", "sessie": "zoom:meeting:u1", "dubbel_van": ""},
                     {"uniek": "zoom:meeting:u1", "sessie": "zoom:meeting:u1", "dubbel_van": "fathom:1"}], rijen
    leeg = met_db(pad, lambda: bord.db_lees("select uniek from gesprek_log where uniek = ?", ("fathom:999",)))
    assert leeg == [], "een vraag zonder treffers is een antwoord: een lege lijst, geen fout"
    cte = met_db(pad, lambda: bord.db_lees("  WITH t AS (SELECT uniek FROM gesprek_log) SELECT count(*) AS n FROM t"))
    assert cte == [{"n": 2}], cte
    # J18 en L3: bewijs over het schema als SELECT op pragma_table_info, niet als PRAGMA
    kol = met_db(pad, lambda: bord.db_lees("SELECT name FROM pragma_table_info('gesprek_log')"))
    assert {"sessie", "dubbel_van"} <= {k["name"] for k in kol}, kol


def test_t36_geen_bestand_is_onbekend():
    pad = os.path.join(MAP, "bestaat-niet.db")
    reden = onbekend(lambda: met_db(pad, lambda: bord.db_lees("SELECT 1")))
    assert reden and "ontbreekt" in reden, f"geen bestand hoort BordOnbekend te geven, niet een lege lijst: {reden!r}"
    assert not os.path.exists(pad), "db_lees mag de databank nooit aanmaken"


def test_t36_alleen_select_of_with():
    pad = bord_db("t36-weigert")
    voor = aantal(pad)
    for sql in ("DELETE FROM gesprek_log", "UPDATE gesprek_log SET bron='x'", "INSERT INTO gesprek_log(uniek, ts) VALUES('x','y')",
                "PRAGMA table_info(gesprek_log)", "DROP TABLE gesprek_log", "", "  ", "-- uitleg\nSELECT 1",
                "ATTACH DATABASE 'x.db' AS x", None):
        reden = onbekend(lambda: met_db(pad, lambda: bord.db_lees(sql)))
        assert reden and "SELECT of WITH" in reden, f"{sql!r} hoort geweigerd te worden: {reden!r}"
    assert aantal(pad) == voor, "na een weigering is er niets veranderd"


def test_t36_schrijven_via_with_of_een_tweede_opdracht_lukt_nooit():
    """G2: ook wat wel met WITH of SELECT begint, kan niet schrijven: mode=ro en query_only."""
    pad = bord_db("t36-ro")
    voor = aantal(pad)
    for sql in ("WITH x AS (SELECT 1) INSERT INTO gesprek_log(uniek, ts) SELECT 'nieuw', 'nu' FROM x",
                "WITH x AS (SELECT 1) DELETE FROM gesprek_log",
                "SELECT 1; DELETE FROM gesprek_log"):
        reden = onbekend(lambda: met_db(pad, lambda: bord.db_lees(sql)))
        assert reden and "niet leesbaar" in reden, f"{sql!r} hoort als onbekend te eindigen: {reden!r}"
    assert aantal(pad) == voor, "db_lees heeft geschreven"


def test_t36_sqlite_fout_is_onbekend_nooit_leeg():
    pad = bord_db("t36-fout")
    reden = onbekend(lambda: met_db(pad, lambda: bord.db_lees("SELECT * FROM bestaat_niet")))
    assert reden and "niet leesbaar" in reden and "OperationalError" in reden, reden
    reden = onbekend(lambda: met_db(pad, lambda: bord.db_lees("SELECT * FROM gesprek_log WHERE uniek=?", ("a", "b"))))
    assert reden and "niet leesbaar" in reden, f"verkeerd aantal parameters hoort onbekend te zijn: {reden!r}"
    kapot = os.path.join(MAP, "kapot.db")
    with open(kapot, "wb") as f:
        f.write(b"dit is geen databank" * 50)
    reden = onbekend(lambda: met_db(kapot, lambda: bord.db_lees("SELECT 1 FROM gesprek_log")))
    assert reden and "niet leesbaar" in reden, f"een onleesbaar bestand hoort onbekend te zijn: {reden!r}"


def test_t36_leest_naast_een_schrijvend_bord():
    """Het bord draait in WAL en schrijft elke minuut. De leesweg wacht daar niet op en ziet alleen wat vastligt."""
    pad = bord_db("t36-wal")
    schrijver = sqlite3.connect(pad, isolation_level=None)
    schrijver.execute("PRAGMA journal_mode=WAL")
    schrijver.execute("BEGIN IMMEDIATE")
    schrijver.execute("INSERT INTO gesprek_log(uniek, ts) VALUES('fathom:onaf', 'nu')")
    try:
        begin = time.monotonic()
        rijen = met_db(pad, lambda: bord.db_lees("SELECT uniek FROM gesprek_log ORDER BY uniek"))
        assert time.monotonic() - begin < 5, "de leesweg wachtte op de schrijver"
        assert [r["uniek"] for r in rijen] == ["fathom:1", "zoom:meeting:u1"], rijen
    finally:
        schrijver.execute("ROLLBACK")
        schrijver.close()


def test_t36_bord_db_zelfde_variabele_als_de_regisseur():
    """Een plek voor het pad: dezelfde variabele en standaard als regisseur.py (I3)."""
    bron = open(os.path.join(RUNNER, "regisseur.py"), encoding="utf-8").read()
    assert 'os.environ.get("BORD_DB", os.path.expanduser("~/appportal/mijnagents-data/mijnagents.db"))' in bron
    eigen = open(os.path.join(RUNNER, "koppelingen", "bord.py"), encoding="utf-8").read()
    assert 'BORD_DB = os.environ.get("BORD_DB", os.path.expanduser("~/appportal/mijnagents-data/mijnagents.db"))' in eigen
    assert "mode=ro" in eigen and "PRAGMA query_only = 1" in eigen and "timeout=10" in eigen, "G2 hoort in de code te staan"


# ------------------------------------------------------------------------------------------------- T99 ---
BEGIN = [{"tekst": "Bellen lukte niet", "wie": "claude-code"}, {"tekst": "3 alarmen niet verstuurd", "wie": "mehdi"}]


def ronde(nb, begin_noden=None, doe=None):
    """(laatste hartslag, fout) voor een ronde met begin_noden op deze nabootsing."""
    echt, bord.call = bord.call, nb.call
    try:
        with redirect_stderr(io.StringIO()):
            try:
                with bord.Agent("proefagent").ronde("proef", begin_noden=begin_noden) as r:
                    if doe:
                        doe(r)
            except Exception as e:  # noqa: BLE001
                return nb.statussen()[-1], e
        return nb.statussen()[-1], None
    finally:
        bord.call = echt


def test_t99_begin_noden_gaan_mee_in_een_gewone_ronde():
    laatste, fout = ronde(BordNabootsing(open_noden=[]), BEGIN, lambda r: [r.nood("Bellen lukte niet", "claude-code"),
                                                                           r.nood("Iets uit de ronde")])
    assert fout is None, fout
    assert laatste["status"] == "waakt", laatste
    assert laatste["nood"] == [{"tekst": "Bellen lukte niet", "wie": "claude-code"},
                               {"tekst": "Alarmen niet verstuurd", "wie": "mehdi"},
                               {"tekst": "Iets uit de ronde", "wie": "mehdi"}], \
        f"begin_noden horen erin te staan, zonder teller (N10) en zonder dubbel: {laatste['nood']}"


def test_t99_begin_noden_gaan_mee_als_de_werkwijze_onbekend_is():
    """X4: RondeGestopt door zonder_regelboek, met de begin_noden, de open noden en de nieuwe nood."""
    nb = BordNabootsing(werkwijze=_http(500), open_noden=[{"naam": "proefagent", "tekst": "Oude nood", "wie": "mehdi"},
                                                          {"naam": "proefagent", "tekst": "Bellen lukte niet", "wie": "claude-code"}])
    laatste, fout = ronde(nb, BEGIN)
    assert isinstance(fout, bord.RondeGestopt), fout
    assert laatste["status"] == "fout", laatste
    assert [n["tekst"] for n in laatste["nood"]] == ["Oude nood", "Bellen lukte niet", "Alarmen niet verstuurd",
                                                     "Werkwijze niet gelezen: bordfout"], laatste["nood"]
    assert not nb.kennis(), "een ronde die niets las, meldt geen kennis"


def test_t99_begin_noden_gaan_mee_als_de_werkwijze_leeg_is():
    laatste, fout = ronde(BordNabootsing(werkwijze="", open_noden=[]), BEGIN)
    assert isinstance(fout, bord.RondeGestopt), fout
    assert laatste["nood"] == [{"tekst": "Bellen lukte niet", "wie": "claude-code"},
                               {"tekst": "Alarmen niet verstuurd", "wie": "mehdi"},
                               {"tekst": "Werkwijze leeg op het bord", "wie": "mehdi"}], laatste["nood"]


def test_t99_open_noden_onbekend_dan_in_het_detail():
    """Weet de ronde de open noden niet, dan stuurt ze geen lijst (die zou alles sluiten); de begin_noden staan dan in
    het detail, zodat ze niet stil verdwijnen."""
    laatste, fout = ronde(BordNabootsing(werkwijze=_http(404)), BEGIN)
    assert isinstance(fout, bord.RondeGestopt), fout
    assert "nood" not in laatste, laatste
    assert "Bellen lukte niet" in laatste["detail"] and "Alarmen niet verstuurd" in laatste["detail"], laatste["detail"]
    assert "Werkwijze niet gelezen: agent staat niet op het bord" in laatste["detail"], laatste["detail"]


def test_t99_begin_nood_gelijk_aan_de_stopnood_staat_er_een_keer():
    laatste, _ = ronde(BordNabootsing(werkwijze="", open_noden=[]), [{"tekst": "Werkwijze leeg op het bord", "wie": "mehdi"}])
    assert laatste["nood"] == [{"tekst": "Werkwijze leeg op het bord", "wie": "mehdi"}], laatste["nood"]


def test_t99_ronde_die_halverwege_breekt_houdt_de_begin_noden():
    def breek(r):
        raise ValueError("halverwege stuk")
    laatste, fout = ronde(BordNabootsing(open_noden=[]), BEGIN, breek)
    assert isinstance(fout, ValueError) and laatste["status"] == "fout", (fout, laatste)
    assert [n["tekst"] for n in laatste["nood"]] == ["Bellen lukte niet", "Alarmen niet verstuurd"], laatste["nood"]


def test_t99_zonder_begin_noden_niets_veranderd():
    laatste, fout = ronde(BordNabootsing(open_noden=[]))
    assert fout is None and laatste["status"] == "klaar" and laatste["nood"] == [], laatste


def test_j1_onderbreking_in_de_startfase_blijft_niet_op_actief():
    """N11, J1: SIGTERM (zo komt het binnen als SystemExit, keten.py en de timeout van De Regisseur) of Ctrl-C terwijl de
    ronde nog de werkwijze, de lessen of de collega's leest: de laatste hartslag is fout, nooit actief. Tot 21-10-2026 ving
    Ronde.__enter__ alleen Exception op, en dan bleef elke agent op actief staan."""
    for onderbreking in (SystemExit(143), KeyboardInterrupt()):
        nb = BordNabootsing(open_noden=[])
        agent = bord.Agent("proefagent")

        def stop(*a, **k):
            raise onderbreking

        agent.werkwijze = stop
        echt, bord.call = bord.call, nb.call
        try:
            with redirect_stderr(io.StringIO()):
                try:
                    with agent.ronde("proef"):
                        pass
                    gestopt = None
                except BaseException as e:  # noqa: BLE001
                    gestopt = e
        finally:
            bord.call = echt
        assert gestopt is onderbreking, f"de onderbreking hoort door te gaan, niet opgeslokt te worden: {gestopt!r}"
        statussen = nb.statussen()
        assert statussen[0]["status"] == "actief" and statussen[-1]["status"] == "fout", statussen


# ------------------------------------------------------------------------------------- J1, K3 en Z13 ---
def _fathom_wacht():
    import fathom_wacht  # noqa: PLC0415
    return fathom_wacht


def test_k3_fathom_wacht_afgebroken_blijft_niet_op_actief():
    """J1, K3: SystemExit (zo komt SIGTERM binnen) of Ctrl-C midden in de ronde: de laatste hartslag is fout."""
    fw = _fathom_wacht()
    for onderbreking in (SystemExit(143), KeyboardInterrupt()):
        nb = BordNabootsing()
        echt = (bord.call, fw.fathom.beschikbaar)
        bord.call, fw.fathom.beschikbaar = nb.call, (lambda: True)

        def stop(*a, **k):
            raise onderbreking

        fw.ag.werkwijze = stop
        try:
            try:
                fw.main()
                gestopt = False
            except BaseException:  # noqa: BLE001
                gestopt = True
        finally:
            bord.call, fw.fathom.beschikbaar = echt
            del fw.ag.werkwijze          # terug naar Agent.werkwijze
        assert gestopt, "de onderbreking hoort door te gaan, niet opgeslokt te worden"
        statussen = nb.statussen()
        assert statussen[0]["status"] == "actief" and statussen[-1]["status"] == "fout", statussen
        assert statussen[-1]["taak"] == "ronde afgebroken" and "nood" not in statussen[-1], \
            "een afgebroken ronde sluit geen noden die ze niet meer kon nakijken"


def test_k3_fathom_wacht_gewone_uitgangen_onveranderd():
    """Een gewone fout en een ontbrekende sleutel melden zoals voordien, zonder extra hartslag erachter."""
    fw = _fathom_wacht()
    nb = BordNabootsing()
    echt = (bord.call, fw.fathom.beschikbaar)
    bord.call, fw.fathom.beschikbaar = nb.call, (lambda: False)
    try:
        fw.main()
    finally:
        bord.call, fw.fathom.beschikbaar = echt
    assert [s["status"] for s in nb.statussen()] == ["actief", "fout"] and nb.statussen()[-1]["taak"] == "geen Fathom-sleutel"

    nb = BordNabootsing(werkwijze=_http(500), open_noden=[])
    bord.call, fw.fathom.beschikbaar = nb.call, (lambda: True)
    try:
        with redirect_stderr(io.StringIO()):
            try:
                fw.main()
            except bord.RondeGestopt:
                pass
    finally:
        bord.call, fw.fathom.beschikbaar = echt
    assert nb.statussen()[-1]["taak"] == "ronde mislukt", nb.statussen()
    assert "ronde afgebroken" not in [s["taak"] for s in nb.statussen()]


STUURPROGRAMMA = r"""
import json, os, runpy, sys, time
RUNNER = sys.argv[1]
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import bord, fathom
bord.call = lambda pad, payload=None, method=None: print("BORD " + json.dumps([pad, payload]), flush=True) or {}
fathom.beschikbaar = lambda: True

def traag(self, taak="werkwijze lezen", noden=()):
    print("WERK", flush=True)
    time.sleep(60)

bord.Agent.werkwijze = traag
runpy.run_path(os.path.join(RUNNER, "fathom_wacht.py"), run_name="__main__")
"""


def test_k3_fathom_wacht_sigterm_als_proces():
    """Zoals timeout het doet: het echte script, gestart als __main__, krijgt SIGTERM midden in de ronde."""
    thuis = tempfile.mkdtemp(prefix="thuis-")      # geen echte .env-bestanden lezen
    p = subprocess.Popen([sys.executable, "-B", "-c", STUURPROGRAMMA, RUNNER], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, env=dict(os.environ, HOME=thuis, PYTHONDONTWRITEBYTECODE="1"))
    regels, einde = [], time.monotonic() + 60
    try:
        while time.monotonic() < einde:
            regel = p.stdout.readline()
            if not regel:
                break
            regels.append(regel.strip())
            if regel.strip() == "WERK":
                p.send_signal(signal.SIGTERM)
                break
        uit, fout = p.communicate(timeout=30)
    finally:
        if p.poll() is None:
            p.kill()
    regels += uit.splitlines()
    statussen = [json.loads(r[5:])[1] for r in regels if r.startswith("BORD ") and json.loads(r[5:])[0] == "/agent-status"]
    assert "WERK" in regels, f"de ronde kwam niet aan het werk: {regels} {fout}"
    assert p.returncode == 128 + signal.SIGTERM, f"exitcode {p.returncode}, verwacht {128 + signal.SIGTERM}: {fout}"
    assert statussen and statussen[0]["status"] == "actief" and statussen[-1]["status"] == "fout", statussen
    assert statussen[-1]["taak"] == "ronde afgebroken", statussen


def test_z13_fathom_wacht_zet_de_bron_zelf():
    """Z13: elke rij die De Fathomwacht naar de gesprekkentabel stuurt, draagt bron fathom; het klaarzet-item blijft
    zoals het was (geen extra sleutel in de inhoud)."""
    fw = _fathom_wacht()
    import nummerlezer  # noqa: PLC0415
    nummerlezer._standaard["codes"], nummerlezer._standaard["ts"] = nummerlezer._bouw_codes([]), time.time()   # geen register
    archief = tempfile.mkdtemp(prefix="fathom-data-")
    map_ = os.path.join(archief, "2026-10-20 0910 Proefgesprek")
    os.makedirs(map_)
    herkenning = {"personen": ["Jan Proef"], "hoofdpersoon": "Jan Proef", "bedrijf": "", "afdeling": "regie", "thema": "proef",
                  "project": "", "prive": False, "zekerheid": "hoog", "waarom": "proef"}
    g = {"recording_id": 4242, "title": "Proefgesprek", "url": "https://fathom.video/calls/4242",
         "recording_start_time": "2026-10-20T07:10:00Z", "recording_end_time": "2026-10-20T07:41:00Z",
         "recorded_by": {"name": "Mehdi", "email": "zoomafspraken@gmail.com"}}
    with open(os.path.join(map_, "gesprek.json"), "w", encoding="utf-8") as f:
        json.dump(dict(g, herkenning=herkenning), f)
    nb, gezet = BordNabootsing(werkwijze="# Fathomwacht\n\nGeen personentabel."), {}
    echt_call = nb.call

    def call(pad, payload=None, method=None):
        if pad == "/api/gesprekken":
            gezet["rijen"] = payload["rijen"]
        if pad == "/api/klaarzet":
            gezet["items"] = payload["items"]
        return echt_call(pad, payload, method)

    oud = {"call": bord.call, "ARCHIEF": fw.ARCHIEF, "_INDEX": fw._INDEX, "beschikbaar": fw.fathom.beschikbaar,
           "gesprekken": fw.fathom.gesprekken, "sleutels": fw.fathom.sleutels, "deals": fw.deals_index,
           "spiegel": fw.dropbox_prive.spiegel_map, "dnood": fw.dropbox_prive.nood}
    bord.call, fw.ARCHIEF, fw._INDEX = call, archief, None
    fw.fathom.beschikbaar, fw.fathom.gesprekken, fw.fathom.sleutels = (lambda: True), (lambda sinds, met_transcript=False: [g]), (lambda: ["proef"])
    fw.deals_index = lambda: []
    fw.dropbox_prive.spiegel_map = lambda lokaal, extern: {"verstuurd": 0, "fout": "", "rest": 0}
    fw.dropbox_prive.nood = lambda wie="mehdi", wat="": []
    try:
        fw.main()
    finally:
        bord.call, fw.ARCHIEF, fw._INDEX = oud["call"], oud["ARCHIEF"], oud["_INDEX"]
        fw.fathom.beschikbaar, fw.fathom.gesprekken, fw.fathom.sleutels = oud["beschikbaar"], oud["gesprekken"], oud["sleutels"]
        fw.deals_index, fw.dropbox_prive.spiegel_map, fw.dropbox_prive.nood = oud["deals"], oud["spiegel"], oud["dnood"]
    assert gezet.get("rijen") and all(r.get("bron") == "fathom" for r in gezet["rijen"]), gezet.get("rijen")
    assert gezet["rijen"][0]["uniek"] == "fathom:4242", gezet["rijen"]
    inhoud = gezet["items"][0]["inhoud"]
    assert "bron" not in inhoud and inhoud["uniek"] == "fathom:4242", "het klaarzet-item verandert niet door Z13"
    assert nb.statussen()[-1]["status"] == "waakt", nb.statussen()[-1]


# ----------------------------------------------------------------------------------------- BAS-01 en BAS-04 ---
WW_FATHOM = "# Fathomwacht\n\nGeen personentabel."
SLEUTEL_NOOD = "Mehdi's eigen Fathom-sleutel ontbreekt op de VM (FATHOM_API_KEYS is nu van Shaniel); ik zie zijn gesprekken niet"
SHANIEL = {"name": "Shaniel", "email": "shaniel@hdssr.com"}
MEHDI = {"name": "Mehdi", "email": "zoomafspraken@gmail.com"}
ZATERDAG = datetime(2026, 10, 24, 8, 0, tzinfo=timezone.utc)        # zaterdag 10:00 in Brussel


def gesprek(rid, start, eind, door=MEHDI, titel="Proefgesprek"):
    return {"recording_id": rid, "title": titel, "url": f"https://fathom.video/calls/{rid}",
            "recording_start_time": start, "recording_end_time": eind, "recorded_by": door}


def herkenning(personen, thema, prive=False, afdeling="regie", waarom="proef", hoofdpersoon=None):
    return {"personen": personen, "hoofdpersoon": personen[0] if hoofdpersoon is None else hoofdpersoon, "bedrijf": "",
            "afdeling": afdeling, "thema": thema, "project": "", "prive": prive, "zekerheid": "hoog", "waarom": waarom}


def fathom_ronde(nb, gesprekken, archief=None, nu=None, dagen=None):
    """Een ronde van De Fathomwacht op deze nabootsing, zonder netwerk en zonder taalmodel: elk gesprek staat al in het
    archief met zijn herkenning, dus herkent de ronde niets opnieuw. gesprekken: [(g, herkenning)]; nu: de klok van de
    ronde; dagen: FATHOM_WACHT_DAGEN. Geeft (wat naar het bord ging, per pad een lijst; de schermregels; de gevraagde
    sinds)."""
    fw = _fathom_wacht()
    import nummerlezer  # noqa: PLC0415
    nummerlezer._standaard["codes"], nummerlezer._standaard["ts"] = nummerlezer._bouw_codes([]), time.time()   # geen register
    archief = archief or tempfile.mkdtemp(prefix="fathom-data-")
    for g, herk in gesprekken:
        map_ = os.path.join(archief, f"gesprek {g['recording_id']}")
        os.makedirs(map_, exist_ok=True)
        with open(os.path.join(map_, "gesprek.json"), "w", encoding="utf-8") as f:
            json.dump(dict(g, herkenning=herk), f)
    gezet, gevraagd = {}, []
    echt_call = nb.call

    def call(pad, payload=None, method=None):
        gezet.setdefault(pad, []).append(payload)
        return echt_call(pad, payload, method)

    def haal(sinds, met_transcript=False):
        gevraagd.append(sinds)
        return [g for g, _ in gesprekken]

    oud = {"call": bord.call, "ARCHIEF": fw.ARCHIEF, "_INDEX": fw._INDEX, "DAGEN": fw.DAGEN, "nu_utc": fw.__dict__.get("nu_utc"),
           "beschikbaar": fw.fathom.beschikbaar, "gesprekken": fw.fathom.gesprekken, "sleutels": fw.fathom.sleutels,
           "deals": fw.deals_index, "spiegel": fw.dropbox_prive.spiegel_map, "dnood": fw.dropbox_prive.nood}
    bord.call, fw.ARCHIEF, fw._INDEX = call, archief, None
    if dagen is not None:
        fw.DAGEN = dagen
    if nu is not None:
        fw.nu_utc = lambda: nu
    fw.fathom.beschikbaar, fw.fathom.gesprekken, fw.fathom.sleutels = (lambda: True), haal, (lambda: ["proef"])
    fw.deals_index = lambda: []
    fw.dropbox_prive.spiegel_map = lambda lokaal, extern: {"verstuurd": 0, "fout": "", "rest": 0}
    fw.dropbox_prive.nood = lambda wie="mehdi", wat="": []
    scherm = io.StringIO()
    try:
        with redirect_stdout(scherm):
            fw.main()
    finally:
        bord.call, fw.ARCHIEF, fw._INDEX, fw.DAGEN = oud["call"], oud["ARCHIEF"], oud["_INDEX"], oud["DAGEN"]
        if oud["nu_utc"] is None:
            fw.__dict__.pop("nu_utc", None)
        else:
            fw.nu_utc = oud["nu_utc"]
        fw.fathom.beschikbaar, fw.fathom.gesprekken, fw.fathom.sleutels = oud["beschikbaar"], oud["gesprekken"], oud["sleutels"]
        fw.deals_index, fw.dropbox_prive.spiegel_map, fw.dropbox_prive.nood = oud["deals"], oud["spiegel"], oud["dnood"]
    return gezet, scherm.getvalue(), gevraagd


def test_bas01_fathom_wacht_schrijft_geen_prive_in_het_werkverslag():
    """BAS-01, M3 (ontwerp 13.2: met wie valt weg bij privégesprekken), aan de bron. Tot 21-10-2026 schreef De Fathomwacht
    van elk gesprek de hoofdpersoon (of de titel), de afdeling, het thema en de reden van het model in de bevinding, en in
    de bronregel per rij personen | afdeling | thema, ook van een privégesprek. Dat werkverslag gaat ongefilterd naar een
    taalmodel. Nu staat van een privégesprek alleen het tijdstip en 'privé' in het werkverslag; een werkgesprek blijft."""
    prive = gesprek(7001, "2026-10-20T18:00:00Z", "2026-10-20T18:40:00Z", titel="Avond met Lara")
    zonder_hoofd = gesprek(7002, "2026-10-20T19:00:00Z", "2026-10-20T19:20:00Z", titel="Notaris Verbeke over het testament")
    werk = gesprek(7003, "2026-10-20T08:00:00Z", "2026-10-20T08:30:00Z", titel="Werfoverleg")
    gezet, scherm, _ = fathom_ronde(BordNabootsing(werkwijze=WW_FATHOM), [
        (prive, herkenning(["Lara Peeters", "Mehdi"], "Echtscheidingsadvocaat bespreken", prive=True, afdeling="prive",
                           waarom="Lara en Mehdi over de scheiding")),
        (zonder_hoofd, herkenning(["Mehdi"], "Testament opstellen", prive=True, afdeling="prive", waarom="erfenis",
                                  hoofdpersoon="")),
        (werk, herkenning(["Jan Klant"], "Dakkapel nakijken"))])
    regels = [r for p in gezet.get("/api/logboek", []) for r in p["regels"]]
    alles = "\n".join(f"{r['onderwerp']} {r['tekst']} {r['detail']}" for r in regels)
    for geheim in ("Lara", "Echtscheiding", "scheiding", "Notaris Verbeke", "estament", "erfenis", "Avond met"):
        assert geheim not in alles, f"{geheim!r} staat in het werkverslag: {alles}"
        assert geheim not in scherm, f"{geheim!r} staat op het scherm (de cron-logboeken): {scherm}"
    bevindingen = [r for r in regels if r["stap"] == "bevinding"]
    assert len(bevindingen) == 3, f"elk gesprek houdt zijn bevinding, ook een privégesprek: {bevindingen}"
    stil = [r for r in bevindingen if "privé" in r["tekst"]]
    assert len(stil) == 2 and not any(r["detail"] for r in stil), stil
    assert any("Jan Klant" in r["tekst"] and "Dakkapel nakijken" in r["tekst"] for r in bevindingen), \
        f"een werkgesprek blijft zoals het was: {bevindingen}"
    bron = [r for r in regels if r["stap"] == "bron"]
    assert len(bron) == 1 and "Jan Klant" in bron[0]["detail"] and bron[0]["detail"].count("(privé)") == 2, bron
    # de gesprekkentabel blijft gelijk: daar staat privé als vlag, alleen beheer ziet ze
    rijen = {r["uniek"]: r["prive"] for r in gezet["/api/gesprekken"][0]["rijen"]}
    assert rijen == {"fathom:7001": True, "fathom:7002": True, "fathom:7003": False}, rijen


def test_bas04_kort_venster_herschrijft_geen_onvolledig_dagboek():
    """BAS-04, J1: een ronde met FATHOM_WACHT_DAGEN=1 zag vrijdag pas vanaf 10:00 en overschreef logboek/<vrijdag>.md met
    alleen die gesprekken; spiegel_map stuurde het ingekorte bestand ook naar Dropbox. Nu schrijft de ronde alleen het
    logboek van een dag die volledig in het venster valt. Dat geldt ook voor de oudste dag van het gewone venster."""
    archief = tempfile.mkdtemp(prefix="fathom-data-")
    os.makedirs(os.path.join(archief, "logboek"))
    for dag in ("2026-10-10", "2026-10-23"):
        with open(os.path.join(archief, "logboek", f"{dag}.md"), "w", encoding="utf-8") as f:
            f.write("ORIGINEEL\n")

    def lees(dag):
        with open(os.path.join(archief, "logboek", f"{dag}.md"), encoding="utf-8") as f:
            return f.read()

    vrijdag = gesprek(8001, "2026-10-23T10:00:00Z", "2026-10-23T10:30:00Z", door=SHANIEL)     # 12:00 in Brussel
    zaterdag = gesprek(8002, "2026-10-24T07:00:00Z", "2026-10-24T07:20:00Z")                  # 09:00 in Brussel
    oudste = gesprek(8003, "2026-10-10T09:00:00Z", "2026-10-10T09:30:00Z")                    # 11:00, het venster begint om 10:00
    gesprekken = [(vrijdag, herkenning(["Jan Klant"], "Werf")), (zaterdag, herkenning(["Piet Klant"], "Offerte"))]
    _, _, gevraagd = fathom_ronde(BordNabootsing(werkwijze=WW_FATHOM, open_noden=[]), gesprekken, archief=archief,
                                  nu=ZATERDAG, dagen=1)
    assert lees("2026-10-23") == "ORIGINEEL\n", f"vrijdag zag deze ronde maar vanaf 10:00, het logboek blijft: {lees('2026-10-23')}"
    assert "| 09:00 |" in lees("2026-10-24") and "Piet Klant" in lees("2026-10-24"), "zaterdag valt volledig in het venster"
    assert gevraagd == ["2026-10-23T08:00:00Z"], gevraagd

    # het gewone venster van 14 dagen: de oudste dag ook maar voor een deel, vrijdag wel volledig
    _, _, gevraagd = fathom_ronde(BordNabootsing(werkwijze=WW_FATHOM, open_noden=[]),
                                  gesprekken + [(oudste, herkenning(["Kees Klant"], "Dak"))], archief=archief,
                                  nu=ZATERDAG, dagen=14)
    assert gevraagd == ["2026-10-10T08:00:00Z"], gevraagd
    assert lees("2026-10-10") == "ORIGINEEL\n", f"de oudste dag van het venster is onvolledig: {lees('2026-10-10')}"
    assert "| 12:00 |" in lees("2026-10-23") and "Jan Klant" in lees("2026-10-23"), "in het volle venster wordt vrijdag geschreven"


def test_bas04_kort_venster_opent_geen_nood_over_de_eigen_sleutel():
    """BAS-04, J1: zonder opname van Mehdi's account in de laatste 24 uur opende een korte ronde de nood dat zijn sleutel
    ontbreekt, tot de keten van 13:00. Een kort venster bewijst dat niet: de vorige stand van die nood blijft. Het volle
    venster en een eigen opname werken zoals voordien."""
    van_shaniel = [(gesprek(8101, "2026-10-24T07:00:00Z", "2026-10-24T07:20:00Z", door=SHANIEL), herkenning(["Jan Klant"], "Werf"))]
    van_mehdi = [(gesprek(8102, "2026-10-24T07:00:00Z", "2026-10-24T07:20:00Z"), herkenning(["Jan Klant"], "Werf"))]
    open_ = [{"naam": "fathom-wacht", "tekst": SLEUTEL_NOOD, "wie": "mehdi"}]

    def laatste(open_noden, gesprekken, dagen):
        nb = BordNabootsing(werkwijze=WW_FATHOM, open_noden=open_noden)
        fathom_ronde(nb, gesprekken, nu=ZATERDAG, dagen=dagen)
        return nb.statussen()[-1]

    h = laatste([], van_shaniel, 1)
    assert h["status"] == "waakt" and not any("eigen Fathom-sleutel" in n["tekst"] for n in h["nood"]), \
        f"een kort venster opent de nood over de sleutel niet: {h}"
    h = laatste(open_, van_shaniel, 1)
    assert {"tekst": SLEUTEL_NOOD, "wie": "mehdi"} in h["nood"], f"stond ze open, dan blijft ze open: {h}"
    h = laatste(None, van_shaniel, 1)
    assert h["status"] == "waakt" and "nood" not in h, f"open noden onbekend: geen lijst, zodat het bord niets sluit: {h}"
    assert "Betrokken personen" in h["detail"], f"wat de ronde vond, staat dan in het detail: {h['detail']}"
    h = laatste(open_, van_mehdi, 1)
    assert not any("eigen Fathom-sleutel" in n["tekst"] for n in h["nood"]), f"een eigen opname bewijst de sleutel: {h}"
    h = laatste([], van_shaniel, 14)
    assert {"tekst": SLEUTEL_NOOD, "wie": "mehdi"} in h["nood"], f"het volle venster meldt zoals voordien, dezelfde tekst (N10): {h}"


if __name__ == "__main__":
    import traceback
    goed = fout = 0
    for naam, f in sorted(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                with redirect_stderr(io.StringIO()):
                    f()
                goed += 1
                print(f"   geslaagd  {naam}")
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"   GEFAALD   {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)

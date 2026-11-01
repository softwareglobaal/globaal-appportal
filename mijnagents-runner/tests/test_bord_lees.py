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
- RZ2-01 (bouwcontrole RZ2): een privé-item van De Fathomwacht draagt in titel, inhoud en verwijzing geen persoon,
  onderwerp of toelichting. Samen getoetst met De Dagbundelaar en bord_export: een herkenbare naam en een herkenbaar
  onderwerp staan nergens in de bundel, het Dagverslag, de werkverslagen of de export.
- RZ2-02: zonder Fathom-sleutel geeft main() 1, zodat het script niet met exit 0 eindigt (zie ook test_keten.py).
- RZ4-01 (deel release 1) en K4: het exportmasker herkent de privémarkering in elke schrijfwijze en toont van een oude
  Zoom-dagregel geen namen; een nieuw privé-Zoomgesprek zet via De Levenscoach (bronnen_van) en de export geen naam of
  onderwerp in Data uit Mehdi.

Geen netwerk: het bord is nagebootst met BordNabootsing uit test_agentnorm.py, de databank is tijdelijk en komt uit
init_db van mijnagents/app.py als Flask er is (in de CI altijd).
Draaien: python3 mijnagents-runner/tests/test_bord_lees.py
"""
import io
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
REPO = os.path.dirname(RUNNER)
# Mehdi's eigen Fathom-account in de proef: een verzonnen adres via de omgeving, nooit de echte standaard uit
# koppelingen/fathom.py; een opname van een ander account draagt ook een verzonnen adres.
EIGEN_ADRES, ANDER_ADRES = "eigen@mehdi.test", "ander@shaniel.test"
os.environ["FATHOM_MEHDI_ADRESSEN"] = f"{EIGEN_ADRES},mch@kantoor.test"
sys.path.insert(0, HIER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import bord  # noqa: E402
from test_agentnorm import BordNabootsing, _http  # noqa: E402

MAP = tempfile.mkdtemp(prefix="bord-lees-")


# ------------------------------------------------------------------------------------------- de databank ---
RUNNER_MAP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
    """J1, K3: SystemExit (zo komt SIGTERM binnen) of Ctrl-C midden in de ronde: de laatste hartslag is fout. Sinds
    NA09-rest (01-11-2026) loopt De Fathomwacht door de gedeelde ronde: die zet de fout, met de onderbreking in het
    detail, en houdt open wat al open stond (open noden onbekend: geen lijst; bekend: dezelfde lijst)."""
    fw = _fathom_wacht()
    oud = [{"naam": "fathom-wacht", "tekst": "Oude nood", "wie": "mehdi"}]
    for onderbreking, open_noden in ((SystemExit(143), None), (KeyboardInterrupt(), None), (SystemExit(143), oud)):
        nb = BordNabootsing(open_noden=open_noden)
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
        assert type(onderbreking).__name__ in statussen[-1]["detail"], statussen[-1]
        if open_noden is None:
            assert "nood" not in statussen[-1], "een afgebroken ronde sluit geen noden die ze niet meer kon nakijken"
        else:
            assert statussen[-1]["nood"] == [{"tekst": "Oude nood", "wie": "mehdi"}], statussen[-1]


def test_k3_fathom_wacht_gewone_uitgangen_onveranderd():
    """Een ontbrekende sleutel meldt zoals voordien. RZ2-02: zonder sleutel geeft main() 1, zodat het script niet met
    exit 0 eindigt. Een werkwijze die niet te lezen is, stopt de ronde met precies een fouthartslag, met de nood erin;
    tot 01-11-2026 kwam daar een tweede fouthartslag 'ronde mislukt' achter, die de reden uit het detail duwde."""
    fw = _fathom_wacht()
    nb = BordNabootsing()
    echt = (bord.call, fw.fathom.beschikbaar)
    bord.call, fw.fathom.beschikbaar = nb.call, (lambda: False)
    try:
        code = fw.main()
    finally:
        bord.call, fw.fathom.beschikbaar = echt
    assert [s["status"] for s in nb.statussen()] == ["actief", "fout"] and nb.statussen()[-1]["taak"] == "geen Fathom-sleutel"
    assert "nood" not in nb.statussen()[-1], "de hartslag blijft zoals voordien, zonder noodlijst"
    assert code == 1, f"RZ2-02: een ronde die Fathom niet kon lezen, eindigt niet op 0: {code!r}"

    nb = BordNabootsing(werkwijze=_http(500), open_noden=[])
    bord.call, fw.fathom.beschikbaar = nb.call, (lambda: True)
    try:
        with redirect_stderr(io.StringIO()):
            code = fw.main()
    finally:
        bord.call, fw.fathom.beschikbaar = echt
    statussen = nb.statussen()
    assert code == 1 and [s["status"] for s in statussen] == ["actief", "fout"], (code, statussen)
    assert "Werkwijze niet gelezen: bordfout" in statussen[-1]["detail"], statussen[-1]
    assert {"tekst": "Werkwijze niet gelezen: bordfout", "wie": "claude-code"} in statussen[-1]["nood"], statussen[-1]



def test_f3_fathom_wacht_vangnet_als_de_ronde_haar_fout_niet_meer_kon_melden():
    """Overleg 15, F3: op main ving De Fathomwacht een signaal op elk moment met een eigen finally. Sinds ze door de ronde
    gaat, kon een signaal terwijl de ronde haar fout meldde de hartslag op actief laten. Nu zet het vangnet van main dan
    nog een fouthartslag ("ronde afgebroken", zonder noodlijst); het signaal gaat door. Meldde de ronde haar fout wel,
    dan doet het vangnet niets."""
    fw = _fathom_wacht()

    def kapot(*a, **k):
        raise ValueError("Fathom kapot (proef)")

    def signaal_tijdens_melden(*a, **k):
        raise SystemExit(143)

    for vangnet_nodig in (True, False):
        nb = BordNabootsing(werkwijze=WW_FATHOM, open_noden=[])
        echt = (bord.call, fw.fathom.beschikbaar, fw.fathom.gesprekken)
        bord.call, fw.fathom.beschikbaar, fw.fathom.gesprekken = nb.call, (lambda: True), kapot
        if vangnet_nodig:
            fw.ag.fout_melden = signaal_tijdens_melden
        try:
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                try:
                    fw.main()
                    uit = None
                except BaseException as e:  # noqa: BLE001
                    uit = e
        finally:
            bord.call, fw.fathom.beschikbaar, fw.fathom.gesprekken = echt
            fw.ag.__dict__.pop("fout_melden", None)
        statussen = nb.statussen()
        assert statussen[-1]["status"] == "fout", (vangnet_nodig, statussen)
        if vangnet_nodig:
            assert isinstance(uit, SystemExit) and uit.code == 143, repr(uit)
            assert statussen[-1]["taak"] == "ronde afgebroken" and "nood" not in statussen[-1], statussen[-1]
        else:
            assert isinstance(uit, ValueError) and statussen[-1]["taak"] == "Fathom ophalen", (repr(uit), statussen)
            assert [s["status"] for s in statussen].count("fout") == 1, "het vangnet stuurde een tweede fouthartslag"


def test_na74_fathom_wacht_zonder_sleutel_valt_ook_onder_het_vangnet():
    """Codex NA74: zonder Fathom-sleutel stonden actief en fout buiten het vangnet. Kwam een SIGTERM (als SystemExit)
    terwijl de fouthartslag vertrok, dan bleef ze op actief; main probeerde het via zijn finally opnieuw."""
    fw = _fathom_wacht()
    nb = BordNabootsing(open_noden=[])
    gestuurd = []

    def call(pad, payload=None, method=None):
        if pad == "/agent-status" and payload.get("taak") == "geen Fathom-sleutel" and not gestuurd:
            gestuurd.append(True)
            raise SystemExit(143)
        return nb.call(pad, payload, method)

    echt = (bord.call, fw.fathom.beschikbaar)
    bord.call, fw.fathom.beschikbaar = call, (lambda: False)
    try:
        try:
            fw.main()
            uit = None
        except SystemExit as e:
            uit = e
    finally:
        bord.call, fw.fathom.beschikbaar = echt
    statussen = nb.statussen()
    assert isinstance(uit, SystemExit) and uit.code == 143, repr(uit)
    assert [s["status"] for s in statussen] == ["actief", "fout"] and statussen[-1]["taak"] == "ronde afgebroken", statussen

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
    assert "SystemExit" in statussen[-1]["detail"] and "nood" not in statussen[-1], statussen


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
         "recorded_by": {"name": "Mehdi", "email": EIGEN_ADRES}}
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
    oud["samenvattingen"], fw.fathom.samenvattingen = fw.fathom.samenvattingen, (lambda sinds: [])   # FATHOM-1: geen netwerk
    oud["dekking"], fw.bekende_dekking = fw.bekende_dekking, (lambda eerste, laatste: None)        # FATHOM-4: onbekend
    fw.deals_index = lambda: []
    fw.dropbox_prive.spiegel_map = lambda lokaal, extern: {"verstuurd": 0, "fout": "", "rest": 0}
    fw.dropbox_prive.nood = lambda wie="mehdi", wat="": []
    try:
        fw.main()
    finally:
        bord.call, fw.ARCHIEF, fw._INDEX = oud["call"], oud["ARCHIEF"], oud["_INDEX"]
        fw.fathom.beschikbaar, fw.fathom.gesprekken, fw.fathom.sleutels = oud["beschikbaar"], oud["gesprekken"], oud["sleutels"]
        fw.fathom.samenvattingen, fw.bekende_dekking = oud["samenvattingen"], oud["dekking"]
        fw.deals_index, fw.dropbox_prive.spiegel_map, fw.dropbox_prive.nood = oud["deals"], oud["spiegel"], oud["dnood"]
    assert gezet.get("rijen") and all(r.get("bron") == "fathom" for r in gezet["rijen"]), gezet.get("rijen")
    assert gezet["rijen"][0]["uniek"] == "fathom:4242", gezet["rijen"]
    inhoud = gezet["items"][0]["inhoud"]
    assert "bron" not in inhoud and inhoud["uniek"] == "fathom:4242", "het klaarzet-item verandert niet door Z13"
    assert nb.statussen()[-1]["status"] == "waakt", nb.statussen()[-1]


# ----------------------------------------------------------------------------------------- BAS-01 en BAS-04 ---
WW_FATHOM = "# Fathomwacht\n\nGeen personentabel."
SLEUTEL_NOOD = "Mehdi's eigen Fathom-sleutel ontbreekt op de VM (FATHOM_API_KEYS is nu van Shaniel); ik zie zijn gesprekken niet"
SHANIEL = {"name": "Shaniel", "email": ANDER_ADRES}
MEHDI = {"name": "Mehdi", "email": EIGEN_ADRES}
ZATERDAG = datetime(2026, 10, 24, 8, 0, tzinfo=timezone.utc)        # zaterdag 10:00 in Brussel


def gesprek(rid, start, eind, door=MEHDI, titel="Proefgesprek"):
    return {"recording_id": rid, "title": titel, "url": f"https://fathom.video/calls/{rid}",
            "recording_start_time": start, "recording_end_time": eind, "recorded_by": door}


def herkenning(personen, thema, prive=False, afdeling="regie", waarom="proef", hoofdpersoon=None):
    return {"personen": personen, "hoofdpersoon": personen[0] if hoofdpersoon is None else hoofdpersoon, "bedrijf": "",
            "afdeling": afdeling, "thema": thema, "project": "", "prive": prive, "zekerheid": "hoog", "waarom": waarom}


def fathom_ronde(nb, gesprekken, archief=None, nu=None, dagen=None, samenvattingen=None, dekking=None):
    """Een ronde van De Fathomwacht op deze nabootsing, zonder netwerk en zonder taalmodel: elk gesprek staat al in het
    archief met zijn herkenning, dus herkent de ronde niets opnieuw. gesprekken: [(g, herkenning)]; nu: de klok van de
    ronde; dagen: FATHOM_WACHT_DAGEN; samenvattingen: de nagebootste aanvulvraag van FATHOM-1 (standaard: niets);
    dekking: de nagebootste bekende_dekking van FATHOM-4 (standaard: onbekend, dan schrijft de ronde geen dekking). Geeft
    (wat naar het bord ging, per pad een lijst; de schermregels; de gevraagde sinds)."""
    fw = _fathom_wacht()
    import nummerlezer  # noqa: PLC0415
    nummerlezer._standaard["codes"], nummerlezer._standaard["ts"] = nummerlezer._bouw_codes([]), time.time()   # geen register
    archief = archief or tempfile.mkdtemp(prefix="fathom-data-")
    for g, herk in gesprekken:
        map_ = os.path.join(archief, fw.archiefmap(g))     # de echte mapnaam: datum, uur en de titel in Fathom
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
    oud["samenvattingen"], fw.fathom.samenvattingen = fw.fathom.samenvattingen, (samenvattingen or (lambda sinds: []))
    oud["dekking"], fw.bekende_dekking = fw.bekende_dekking, (dekking or (lambda eerste, laatste: None))
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
        fw.fathom.samenvattingen, fw.bekende_dekking = oud["samenvattingen"], oud["dekking"]
        fw.deals_index, fw.dropbox_prive.spiegel_map, fw.dropbox_prive.nood = oud["deals"], oud["spiegel"], oud["dnood"]
    return gezet, scherm.getvalue(), gevraagd


def test_bas01_fathom_wacht_schrijft_geen_prive_in_het_werkverslag():
    """BAS-01, M3 (ontwerp 13.2: met wie valt weg bij privégesprekken), aan de bron. Tot 21-10-2026 schreef De Fathomwacht
    van elk gesprek de hoofdpersoon (of de titel), de afdeling, het thema en de reden van het model in de bevinding, en in
    de bronregel per rij personen | afdeling | thema, ook van een privégesprek. Dat werkverslag gaat ongefilterd naar een
    taalmodel. Nu staat van een privégesprek alleen het tijdstip en 'privé' in het werkverslag; een werkgesprek blijft."""
    prive = gesprek(7001, "2026-10-20T18:00:00Z", "2026-10-20T18:40:00Z", titel="Avond met Proefpersoon Zeta")
    zonder_hoofd = gesprek(7002, "2026-10-20T19:00:00Z", "2026-10-20T19:20:00Z", titel="Proefnotaris over het proefdossier")
    werk = gesprek(7003, "2026-10-20T08:00:00Z", "2026-10-20T08:30:00Z", titel="Werfoverleg")
    gezet, scherm, _ = fathom_ronde(BordNabootsing(werkwijze=WW_FATHOM), [
        (prive, herkenning(["Proefpersoon Zeta", "Mehdi"], "Proefonderwerp Omega bespreken", prive=True, afdeling="prive",
                           waarom="Zeta en Mehdi over het Privéproefonderwerp")),
        (zonder_hoofd, herkenning(["Mehdi"], "Proefdossier opstellen", prive=True, afdeling="prive", waarom="proefdossier",
                                  hoofdpersoon="")),
        (werk, herkenning(["Jan Klant"], "Dakkapel nakijken"))])
    regels = [r for p in gezet.get("/api/logboek", []) for r in p["regels"]]
    alles = "\n".join(f"{r['onderwerp']} {r['tekst']} {r['detail']}" for r in regels)
    for geheim in ("Zeta", "Omega", "Privéproefonderwerp", "Proefnotaris", "roefdossier", "Avond met"):
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


def test_na09_rest_fathom_wacht_gaat_door_de_ronde():
    """N4, N12-N14 (NA09-rest, 01-11-2026): De Fathomwacht las haar werkwijze streng, maar buiten de ronde, en meldde
    nooit welke regels ze las. Nu staan de werkwijze, de gedeelde lessen en de collega's in haar kennis, en eindigt ze
    met een hartslag van de ronde."""
    nb = BordNabootsing(werkwijze=WW_FATHOM, open_noden=[])
    fathom_ronde(nb, [(gesprek(8201, "2026-10-24T07:00:00Z", "2026-10-24T07:20:00Z"), herkenning(["Jan Klant"], "Werf"))],
                 nu=ZATERDAG, dagen=1)
    kennis = nb.kennis()
    assert kennis, "De Fathomwacht meldde geen kennis: de gedeelde ronde liep niet (N4, N12)"
    for stuk in ("werkwijze op het bord", "gedeelde lessen", "collega's op het bord"):
        assert stuk in kennis[-1]["bron"], f"'{stuk}' ontbreekt in de kennis: {kennis[-1]['bron']}"
    assert [s["status"] for s in nb.statussen()] == ["actief", "waakt"], nb.statussen()


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
    # open noden onbekend: sinds NA09-rest (overleg 12, X6) gaat wat de ronde vond mee met nood_sluiten false, zodat het
    # bord niets sluit; de sleutelnood, waarvan de stand onbekend is, gaat niet mee en blijft zoals ze stond
    assert h["status"] == "waakt" and h.get("nood_sluiten") is False, f"open noden onbekend: het bord sluit niets: {h}"
    assert any("Betrokken personen" in n["tekst"] for n in h["nood"]), f"wat de ronde vond, gaat mee: {h}"
    assert not any("eigen Fathom-sleutel" in n["tekst"] for n in h["nood"]), f"de sleutelnood is onbekend: {h}"
    h = laatste(open_, van_mehdi, 1)
    assert not any("eigen Fathom-sleutel" in n["tekst"] for n in h["nood"]), f"een eigen opname bewijst de sleutel: {h}"
    h = laatste([], van_shaniel, 14)
    assert {"tekst": SLEUTEL_NOOD, "wie": "mehdi"} in h["nood"], f"het volle venster meldt zoals voordien, dezelfde tekst (N10): {h}"


# ------------------------------------------------------------------------------------------------- RZ2-01 ---
GEHEIM = ("Zeta", "Omega")          # een herkenbare naam en een herkenbaar onderwerp, beide verzonnen
DAG_RZ2 = "2026-10-20"


def _dagbundelaar():
    _argv, sys.argv = sys.argv, [sys.argv[0]]      # dagbundelaar.py leest --dag bij het importeren
    try:
        import dagbundelaar  # noqa: PLC0415
    finally:
        sys.argv = _argv
    return dagbundelaar


def dagbundel_ronde(items, dag):
    """Een ronde van De Dagbundelaar op deze items, zoals het bord ze teruggeeft (inhoud als json-tekst), zonder netwerk.
    Geeft (wat naar het bord ging, per pad een lijst; de schermregels)."""
    D = _dagbundelaar()
    gezet = {}

    def call(pad, payload=None, method=None):
        if pad.startswith("/api/klaarzet?"):
            return {"items": [dict(it) for it in items if "soort=zoom" not in pad or it["soort"] == "zoom"]}
        # De Dagbundelaar gaat sinds 26-10-2026 door de gedeelde ronde (N12): ze leest haar werkwijze en de collega's
        if pad == "/api/agent/dagbundelaar/werkwijze" and payload is None:
            return {"werkwijze": open(os.path.join(RUNNER_MAP, "werkwijze", "dagbundelaar.md"), encoding="utf-8").read()}
        if pad == "/api/agents":
            return []
        gezet.setdefault(pad, []).append(payload)
        return {"nieuw": len((payload or {}).get("items") or [])}

    oud = (bord.call, bord.opgepakt, D.DAG, D.DAG_GEGEVEN, D.NACHT, D.vastleggen)
    bord.call, bord.opgepakt, D.DAG, D.DAG_GEGEVEN, D.NACHT = call, (lambda kid, door: None), dag, True, False
    D.vastleggen = lambda r, dagen, **k: ""          # de dagvaststelling heeft eigen tests (test_dagbundelaar_vaststelling.py)
    try:
        with redirect_stdout(io.StringIO()) as scherm:
            D.main()
    finally:
        bord.call, bord.opgepakt, D.DAG, D.DAG_GEGEVEN, D.NACHT, D.vastleggen = oud
    return gezet, scherm.getvalue()


def export_db(naam):
    """Een tijdelijke databank met het volle schema van het bord (init_db van mijnagents/app.py), voor bord_export."""
    pad = os.path.join(MAP, naam + ".db")
    try:
        os.environ.setdefault("AGENTS_DB", os.path.join(MAP, "app-start.db"))
        sys.path.insert(0, os.path.join(REPO, "mijnagents"))
        import app  # noqa: PLC0415
        app.DB_PAD = pad
        with redirect_stdout(io.StringIO()):
            app.init_db()
    except ImportError:
        # Lokaal zonder Flask: het schema uit de tekst van init_db, zoals test_bode_regie.py. In de CI is Flask er altijd.
        assert not os.environ.get("CI"), "Flask ontbreekt in de CI: deze toets hoort de databank uit init_db te bouwen"
        bron = open(os.path.join(REPO, "mijnagents", "app.py"), encoding="utf-8").read()
        sql = re.search(r'def init_db\(\):.*?executescript\(\s*"""(.*?)"""', bron, re.S).group(1)
        c = sqlite3.connect(pad)
        c.executescript(sql)
        c.execute("ALTER TABLE agent ADD COLUMN werkwijze TEXT DEFAULT ''")
        c.commit()
        c.close()
    return pad


def export(pad, klaarzet, logboek):
    """bord_export.main() op een databank met deze klaarzet-items en werkverslagregels. Geeft {pad: tekst} van de export."""
    import bord_export as E  # noqa: PLC0415
    nu_ = datetime.now(timezone.utc).isoformat()
    c = sqlite3.connect(pad)
    c.executemany("INSERT INTO klaarzet(van, voor, soort, sleutel, titel, inhoud, verwijzing, uniek, status, ts) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  [(it["van"], it["voor"], it["soort"], it.get("sleutel") or "", it["titel"],
                    it["inhoud"] if isinstance(it.get("inhoud"), str) else json.dumps(it.get("inhoud"), ensure_ascii=False),
                    it.get("verwijzing") or "", it.get("uniek") or "", it.get("status") or "klaar", nu_) for it in klaarzet])
    c.executemany("INSERT INTO logboek(naam, onderwerp, stap, tekst, detail, ts) VALUES(?,?,?,?,?,?)",
                  [(r["naam"], r["onderwerp"], r["stap"], r["tekst"], r["detail"], nu_) for r in logboek])
    c.commit()
    c.close()
    data = tempfile.mkdtemp(prefix="export-")
    oud = (E.DB, E.DATA, E.UIT)
    E.DB, E.DATA, E.UIT = pad, data, os.path.join(data, "export")
    try:
        with redirect_stdout(io.StringIO()):
            E.main()
    finally:
        E.DB, E.DATA, E.UIT = oud
    gelezen = {}
    for wortel, _, bestanden in os.walk(os.path.join(data, "export")):
        for b in bestanden:
            gelezen[os.path.relpath(os.path.join(wortel, b), data)] = open(os.path.join(wortel, b), encoding="utf-8").read()
    return gelezen


def test_rz2_01_prive_nergens_in_bundel_werkverslag_of_export():
    """RZ2-01 (bouwcontrole RZ2, 21-10-2026), aan de bron. Een privé-opname droeg persoon, onderwerp en toelichting in het
    klaarzet-item van De Fathomwacht (titel, inhoud, en de verwijzing: de archiefmap heet naar de titel in Fathom). De
    Dagbundelaar nam de titel over in het Dagverslag en zijn werkverslag, en bord_export schreef de iteminhoud uit. Nu:
    een privé-item draagt alleen datum, start, minuten, privé en een verwijzing naar het archief op de VM; De Dagbundelaar
    zet er 'privégesprek, N min' van in; de export schrijft geen inhoud van een privé-item. Ook een item van voor de
    herstelling (titel met naam en onderwerp, nog op het bord) lekt niet meer. Een werkgesprek blijft zoals het was: De
    Contractmaker en de werfverslagagents lezen Fathom-items."""
    prive = gesprek(7101, "2026-10-20T18:00:00Z", "2026-10-20T18:40:00Z", titel="Avond met Proefpersoon Zeta")
    werk = gesprek(7102, "2026-10-20T08:00:00Z", "2026-10-20T08:30:00Z", titel="Werfoverleg")
    gezet, scherm, _ = fathom_ronde(BordNabootsing(werkwijze=WW_FATHOM), [
        (prive, herkenning(["Proefpersoon Zeta", "Mehdi"], "Proefonderwerp Omega bespreken", prive=True, afdeling="prive",
                           waarom="Proefpersoon Zeta en Mehdi over het Proefonderwerp Omega")),
        (werk, herkenning(["Jan Klant"], "Dakkapel nakijken"))])
    archief = os.path.dirname(gezet["/api/gesprekken"][0]["rijen"][0]["archief"])
    assert "Zeta" in json.dumps(gezet["/api/gesprekken"], ensure_ascii=False), \
        "de gesprekkentabel (alleen beheer) houdt wie en waarover: de proef draagt de naam echt"
    items = {it["uniek"]: it for it in gezet["/api/klaarzet"][0]["items"]}

    # het privé-item zelf: alleen datum, start, minuten, privé en de verwijzing naar het archief op de VM
    p = items["fathom:7101"]
    verwijzing = os.path.join(archief, "2026-10-20 2000 (privé) [7101]")
    assert p["titel"] == "2026-10-20T20:00 Fathom: privégesprek, 40 min · PRIVÉ", p["titel"]
    assert p["inhoud"] == {"datum": "2026-10-20", "start": "20:00", "minuten": 40, "prive": True, "archief": verwijzing}, p["inhoud"]
    assert p["verwijzing"] == verwijzing and p["voor"] == "mehdi" and p["soort"] == "transcript", p
    assert os.path.isdir(os.path.join(archief, "2026-10-20 2000 Avond met Proefpersoon Zeta")), "de map op de VM houdt haar naam"

    # een werkgesprek blijft zoals het was
    w = items["fathom:7102"]
    assert w["titel"] == "2026-10-20T10:00 Fathom: Jan Klant · Dakkapel nakijken", w["titel"]
    assert w["verwijzing"] == os.path.join(archief, "2026-10-20 1000 Werfoverleg"), w["verwijzing"]
    assert set(w["inhoud"]) == {"uniek", "datum", "start", "minuten", "personen", "bedrijf", "afdeling", "thema", "project", "prive",
                                "zekerheid", "archief", "link", "opgenomen_door", "waarom", "transcript_pad", "dossier", "firma",
                                "projectnummer", "deal_id", "zekerheid_dossier", "conflict", "redenen"}, sorted(w["inhoud"])
    assert w["inhoud"]["personen"] == "Jan Klant" and w["inhoud"]["thema"] == "Dakkapel nakijken" and w["inhoud"]["prive"] is False

    # De Dagbundelaar, met daarnaast een privé-item van voor de herstelling dat nog op het bord staat
    oud_prive = {"id": 1, "van": "fathom-wacht", "voor": "mehdi", "soort": "transcript", "sleutel": "", "status": "klaar",
                 "titel": "2026-10-20T21:00 Fathom: Proefpersoon Zeta · Proefonderwerp Omega regelen · PRIVÉ", "uniek": "fathom:7000",
                 "verwijzing": "/home/ubuntu/appportal/mijnagents-data/fathom-data/2026-10-20 2100 Avond met Proefpersoon Zeta",
                 "inhoud": json.dumps({"uniek": "fathom:7000", "datum": DAG_RZ2, "start": "21:00", "minuten": 25,
                                       "personen": "Proefpersoon Zeta, Mehdi", "thema": "Proefonderwerp Omega regelen", "prive": True,
                                       "waarom": "Proefpersoon Zeta over het Proefonderwerp Omega"}, ensure_ascii=False)}
    bak = [oud_prive] + [dict(it, id=i, status="klaar", inhoud=json.dumps(it["inhoud"], ensure_ascii=False))
                         for i, it in enumerate(gezet["/api/klaarzet"][0]["items"], start=2)]
    bundel, bundel_scherm = dagbundel_ronde(bak, DAG_RZ2)
    bundels = {b["uniek"]: b for b in bundel["/api/klaarzet"][0]["items"]}
    verslag = bundels[f"dagverslag:{DAG_RZ2}"]["inhoud"]
    assert "- transcript: privégesprek, 40 min" in verslag and "- transcript: privégesprek, 25 min" in verslag, verslag
    assert "Jan Klant" in verslag, "een werkgesprek staat er zoals voordien in"
    regels = bundel["/api/logboek"][0]["regels"]
    assert any("privégesprek, 25 min" in r["detail"] for r in regels), "het werkverslag zegt alleen privégesprek, N min"

    # de export van het bord: klaargezet, werkverslagen en de dagverslagen voluit
    gelezen = export(export_db("rz2-01"), [dict(it, van="fathom-wacht") for it in [oud_prive] + list(items.values())]
                     + [dict(b, van="dagbundelaar") for b in bundels.values()],
                     gezet["/api/logboek"][0]["regels"] + regels)
    fathom_export = "".join(t for pad, t in gelezen.items() if pad.startswith(os.path.join("export", "Fathom", "klaargezet")))
    assert fathom_export.count("): (privé)") == 2 and "Jan Klant" in fathom_export and "Dakkapel nakijken" in fathom_export, fathom_export
    assert any("privégesprek, 40 min" in t for pad, t in gelezen.items() if "dagverslagen" in pad), list(gelezen)

    # nergens de naam of het onderwerp: niet in wat naar het bord ging (behalve de gesprekkentabel), niet op het scherm
    # (de cron-logboeken), niet in de bundels, het Dagverslag of de werkverslagen, en niet in de export
    nagaan = {f"fathom {pad}": json.dumps(p, ensure_ascii=False) for pad, lijst in gezet.items() if pad != "/api/gesprekken" for p in lijst}
    nagaan.update({f"dagbundelaar {pad}": json.dumps(p, ensure_ascii=False) for pad, lijst in bundel.items() for p in lijst})
    nagaan.update({"fathom scherm": scherm, "dagbundelaar scherm": bundel_scherm})
    nagaan.update({f"export {pad}": t for pad, t in gelezen.items()})
    for waar, tekst in nagaan.items():
        for geheim in GEHEIM:
            assert geheim not in tekst, f"{geheim!r} staat in {waar}: {tekst[:2000]}"


def test_rz2_01_oude_bundels_en_werkverslagregels_lekken_niet_in_de_export():
    """RZ2-01, tegenproef van 22-10-2026. Wat van voor de herstelling nog in het venster van de export staat (14 dagen),
    droeg de naam en het onderwerp van een privégesprek op drie plaatsen buiten de dagverslagen/: een bundel en het
    Dagverslag als klaarzet-item (export/Dagbundelaar/klaargezet/), de werkverslagregel van De Dagbundelaar met 'Toe te
    wijzen' in het detail, en de bevinding van De Plaudwacht met de hoofdpersoon (export/<Agent>/werkverslag/). Alleen
    dagverslagen/ ging door zonder_prive_regels. Nu wordt elke regel met PRIVÉ '(privé)' in klaargezet/ en in het
    werkverslag, en ook een bevinding in de oude vorm van De Plaudwacht en De Fathomwacht (met ' · privé'), waarvan dan
    ook het detail (de reden) wegvalt, en een oude bronregel van De Fathomwacht met afdeling prive. Wat geen privé
    draagt, blijft staan."""
    oud = "2026-10-20T21:00 Fathom: Proefpersoon Zeta · Proefonderwerp Omega regelen · PRIVÉ"
    kaart = "/home/ubuntu/appportal/mijnagents-data/fathom-data/2026-10-20 2100 Avond met Proefpersoon Zeta"
    bundel = (f"Dossier (zonder dossier) op {DAG_RZ2}: 2 transcript\n- transcript: {oud} ({kaart})\n"
              f"- transcript: 2026-10-20T10:00 Fathom: Jan Klant · Dakkapel nakijken\nOntbreekt: bronnen zonder dossier: Mehdi wijst ze toe")
    verslag = (f"Dagverslag {DAG_RZ2}: 2 bronnen in 1 bundel(s).\nZoom: dagregel ontbreekt (Zoomwacht niet klaar)\n"
               f"Toe te wijzen: {oud}; 2026-10-20T10:00 Fathom: Jan Klant · Dakkapel nakijken\n\n{bundel}")
    klaarzet = [{"van": "dagbundelaar", "voor": "mehdi", "soort": "dagbundel", "sleutel": DAG_RZ2, "titel": f"Bundel {DAG_RZ2} · (zonder dossier)",
                 "uniek": f"bundel:{DAG_RZ2}:(zonder dossier)", "inhoud": bundel},
                {"van": "dagbundelaar", "voor": "mehdi", "soort": "dagbundel", "sleutel": DAG_RZ2, "titel": f"Dagverslag {DAG_RZ2}",
                 "uniek": f"dagverslag:{DAG_RZ2}", "inhoud": verslag}]
    logboek = [{"naam": "dagbundelaar", "onderwerp": f"dag {DAG_RZ2}", "stap": "bevinding",
                "tekst": "2 klaargezette bronnen, 1 bundel(s), 2 toe te wijzen; Zoom-dagregel ontbreekt, 0 nagekomen of herzien", "detail": verslag},
               {"naam": "plaud-wacht", "onderwerp": "opname 2026-10-20T22:00", "stap": "bevinding",
                "tekst": "Proefpersoon Zeta · dossier geen (laag) · privé · voor mehdi · 2 publicatie(s), 0 fout", "detail": "afdeling onbekend; privé"},
               {"naam": "plaud-wacht", "onderwerp": "opname 2026-10-20T09:00", "stap": "bevinding",
                "tekst": "Jan Klant · dossier HARC:2531 (hoog) · voor h-architects · 3 publicatie(s), 0 fout", "detail": ""},
               # De Fathomwacht van voor BAS-01 (21-10-2026): de bevinding met ' · privé' en de reden in het detail, en de
               # bronregel met per gesprek personen | afdeling | thema
               {"naam": "fathom-wacht", "onderwerp": "gesprek 2026-10-20T20:00", "stap": "bevinding",
                "tekst": "Proefpersoon Zeta · prive · Proefonderwerp Omega bespreken · privé · zekerheid hoog",
                "detail": "Proefpersoon Zeta en Mehdi over het Proefonderwerp Omega"},
               {"naam": "fathom-wacht", "onderwerp": "Fathom", "stap": "bron", "tekst": "2 gesprekken sinds 2026-10-06; 1 privé",
                "detail": "2026-10-20 20:00 Proefpersoon Zeta, Mehdi | prive | Proefonderwerp Omega bespreken\n"
                          "2026-10-20 10:00 Jan Klant | regie | Dakkapel nakijken"}]
    gelezen = export(export_db("rz2-01-oud"), klaarzet, logboek)
    for pad, tekst in gelezen.items():
        for geheim in GEHEIM:
            assert geheim not in tekst, f"{geheim!r} staat in export {pad}: {tekst[:2000]}"
    bundelaar = "".join(t for pad, t in gelezen.items() if pad.startswith(os.path.join("export", "Dagbundelaar", "klaargezet")))
    assert "(privé)" in bundelaar and "Jan Klant · Dakkapel nakijken" in bundelaar, bundelaar
    werk = "".join(t for pad, t in gelezen.items() if pad.startswith(os.path.join("export", "Dagbundelaar", "werkverslag")))
    assert "(privé)" in werk and "2 klaargezette bronnen" in werk, werk
    plaud = "".join(t for pad, t in gelezen.items() if pad.startswith(os.path.join("export", "Plaud", "werkverslag")))
    assert "Jan Klant · dossier HARC:2531 (hoog)" in plaud and "(privé)" in plaud, plaud
    fathom = "".join(t for pad, t in gelezen.items() if pad.startswith(os.path.join("export", "Fathom", "werkverslag")))
    assert "Jan Klant | regie | Dakkapel nakijken" in fathom and "2 gesprekken sinds" in fathom, fathom


# ------------------------------------------------------------------------------------------------- RZ3-01 ---
def test_rz3_01_afdeling_prive_is_prive_over_de_hele_route():
    """RZ3-01 (herstelcontrole van Codex, besluit van de regie 22-10-2026: de veilige kant). De dossierbeslissing
    (plaud/dossier.py:113) noemt een gesprek met afdeling prive privé, ook als de herkenning prive=false zegt. De
    Fathomwacht gebruikte voor klaarzet, titel, verwijzing en werkverslag alleen het veld prive, zodat naam en onderwerp
    in de bundel, het Dagverslag en de export kwamen. Nu is zo'n gesprek privé aan de bron, ook in de gesprekkentabel.
    De Dagbundelaar en de export behandelen een item met inhoud.afdeling prive ook als privé: zo lekt ook niet wat van
    voor de herstelling nog op het bord en in het venster van de export staat (een item van De Fathomwacht en van De
    Plaudwacht, een bundel en een Dagverslag die zo'n item bij zijn titel noemen, een bevinding in de oude vorm met
    ' · prive · '). Een werkgesprek blijft zoals het was."""
    prive = gesprek(7301, "2026-10-20T18:00:00Z", "2026-10-20T18:40:00Z", titel="Avond met Proefpersoon Zeta")
    werk = gesprek(7302, "2026-10-20T08:00:00Z", "2026-10-20T08:30:00Z", titel="Werfoverleg")
    gezet, scherm, _ = fathom_ronde(BordNabootsing(werkwijze=WW_FATHOM), [
        (prive, herkenning(["Proefpersoon Zeta", "Mehdi"], "Proefonderwerp Omega bespreken", prive=False, afdeling="prive",
                           waarom="Proefpersoon Zeta en Mehdi over het Proefonderwerp Omega")),
        (werk, herkenning(["Jan Klant"], "Dakkapel nakijken"))])
    archief = os.path.dirname(gezet["/api/gesprekken"][0]["rijen"][0]["archief"])
    rijen = {r["uniek"]: r["prive"] for r in gezet["/api/gesprekken"][0]["rijen"]}
    assert rijen == {"fathom:7301": True, "fathom:7302": False}, rijen

    # de bron: het item zoals elk privé-item, het werkverslag zonder naam of onderwerp
    items = {it["uniek"]: it for it in gezet["/api/klaarzet"][0]["items"]}
    p = items["fathom:7301"]
    verwijzing = os.path.join(archief, "2026-10-20 2000 (privé) [7301]")
    assert p["titel"] == "2026-10-20T20:00 Fathom: privégesprek, 40 min · PRIVÉ", p["titel"]
    assert p["inhoud"] == {"datum": "2026-10-20", "start": "20:00", "minuten": 40, "prive": True, "archief": verwijzing}, p["inhoud"]
    assert p["verwijzing"] == verwijzing and p["voor"] == "mehdi", p
    assert items["fathom:7302"]["titel"] == "2026-10-20T10:00 Fathom: Jan Klant · Dakkapel nakijken", items["fathom:7302"]
    regels = [r for lijst in gezet.get("/api/logboek", []) for r in lijst["regels"]]
    assert any(r["stap"] == "bevinding" and r["tekst"].startswith("privégesprek · 40 min") and not r["detail"] for r in regels), regels
    bron = [r for r in regels if r["stap"] == "bron"]
    assert len(bron) == 1 and bron[0]["detail"].count("(privé)") == 1 and "Jan Klant" in bron[0]["detail"], bron

    # van voor de herstelling, nog op het bord: afdeling prive, prive=false, naam en onderwerp in titel, inhoud en verwijzing
    oud_titel = "2026-10-20T21:00 Fathom: Proefpersoon Zeta · Proefonderwerp Omega regelen"
    oud_kaart = "/home/ubuntu/appportal/mijnagents-data/fathom-data/2026-10-20 2100 Avond met Proefpersoon Zeta"
    oud_fathom = {"id": 1, "van": "fathom-wacht", "voor": "mehdi", "soort": "transcript", "sleutel": "", "status": "klaar",
                  "titel": oud_titel, "uniek": "fathom:7300", "verwijzing": oud_kaart,
                  "inhoud": json.dumps({"uniek": "fathom:7300", "datum": DAG_RZ2, "start": "21:00", "minuten": 25,
                                        "personen": "Proefpersoon Zeta, Mehdi", "afdeling": "prive", "thema": "Proefonderwerp Omega regelen",
                                        "prive": False, "waarom": "Proefpersoon Zeta over het Proefonderwerp Omega"}, ensure_ascii=False)}
    oud_plaud = {"id": 2, "van": "plaud-wacht", "voor": "mehdi", "soort": "transcript", "sleutel": "", "status": "klaar",
                 "titel": "2026-10-20 22:00 Plaud: Proefpersoon Zeta · Proefonderwerp Omega", "uniek": "plaud:of_rz3",
                 "verwijzing": "Data uit Mehdi/Plaud/2026-10-20 2200 Proefpersoon Zeta/transcript.md",
                 "inhoud": json.dumps({"plaud_id": "of_rz3", "datum": DAG_RZ2, "start": "22:00", "afdeling": "Prive", "prive": False,
                                       "personen": ["Proefpersoon Zeta"], "thema": "Proefonderwerp Omega"}, ensure_ascii=False)}
    bak = [oud_fathom, oud_plaud] + [dict(it, id=i, status="klaar", inhoud=json.dumps(it["inhoud"], ensure_ascii=False))
                                     for i, it in enumerate(gezet["/api/klaarzet"][0]["items"], start=3)]
    bundel, bundel_scherm = dagbundel_ronde(bak, DAG_RZ2)
    bundels = {b["uniek"]: b for b in bundel["/api/klaarzet"][0]["items"]}
    verslag = bundels[f"dagverslag:{DAG_RZ2}"]["inhoud"]
    for regel in ("- transcript: privégesprek, 40 min", "- transcript: privégesprek, 25 min", "- transcript: privégesprek, duur onbekend"):
        assert regel in verslag, (regel, verslag)
    assert "Jan Klant" in verslag, "een werkgesprek staat er zoals voordien in"
    bundellog = bundel["/api/logboek"][0]["regels"]

    # een bundel, een Dagverslag en werkverslagregels van voor de herstelling (19-10), nog in het venster van de export
    oud_bundel = (f"Dossier (zonder dossier) op 2026-10-19: 2 transcript\n- transcript: {oud_titel} ({oud_kaart})\n"
                  "- transcript: 2026-10-19T10:00 Fathom: Jan Klant · Dakkapel nakijken\nOntbreekt: bronnen zonder dossier: Mehdi wijst ze toe")
    oud_verslag = (f"Dagverslag 2026-10-19: 2 bronnen in 1 bundel(s).\nZoom: dagregel ontbreekt (Zoomwacht niet klaar)\n"
                   f"Toe te wijzen: {oud_titel}; 2026-10-19T10:00 Fathom: Jan Klant · Dakkapel nakijken\n\n{oud_bundel}")
    oude_bundels = [{"van": "dagbundelaar", "voor": "mehdi", "soort": "dagbundel", "sleutel": "2026-10-19", "uniek": "bundel:2026-10-19:(zonder dossier)",
                     "titel": "Bundel 2026-10-19 · (zonder dossier)", "inhoud": oud_bundel},
                    {"van": "dagbundelaar", "voor": "mehdi", "soort": "dagbundel", "sleutel": "2026-10-19", "uniek": "dagverslag:2026-10-19",
                     "titel": "Dagverslag 2026-10-19", "inhoud": oud_verslag}]
    oude_regels = [{"naam": "dagbundelaar", "onderwerp": "dag 2026-10-19", "stap": "bevinding",
                    "tekst": "2 klaargezette bronnen, 1 bundel(s), 2 toe te wijzen; Zoom-dagregel ontbreekt, 0 nagekomen of herzien",
                    "detail": oud_verslag},
                   {"naam": "fathom-wacht", "onderwerp": "gesprek 2026-10-19T21:00", "stap": "bevinding",
                    "tekst": "Proefpersoon Zeta · prive · Proefonderwerp Omega regelen · zekerheid hoog",
                    "detail": "Proefpersoon Zeta over het Proefonderwerp Omega"}]

    gelezen = export(export_db("rz3-01"), [oud_fathom, oud_plaud] + [dict(it, van="fathom-wacht") for it in items.values()]
                     + [dict(b, van="dagbundelaar") for b in bundels.values()] + oude_bundels,
                     regels + bundellog + oude_regels)
    deel = lambda *paden: "".join(t for pad, t in gelezen.items() if pad.startswith(os.path.join("export", *paden)))  # noqa: E731
    assert deel("Fathom", "klaargezet").count("): (privé)") == 2 and "Jan Klant · Dakkapel nakijken" in deel("Fathom", "klaargezet")
    assert deel("Plaud", "klaargezet").count("): (privé)") == 1, deel("Plaud", "klaargezet")
    assert "(privé)" in deel("Dagbundelaar", "klaargezet") and "Jan Klant · Dakkapel nakijken" in deel("Dagbundelaar", "klaargezet")
    assert "(privé)" in deel("Dagbundelaar", "werkverslag") and "2 klaargezette bronnen" in deel("Dagbundelaar", "werkverslag")
    assert "Jan Klant · regie · Dakkapel nakijken" in deel("Fathom", "werkverslag"), "een werkgesprek blijft in het werkverslag"

    nagaan = {f"fathom {pad}": json.dumps(lijst, ensure_ascii=False) for pad, lijst in gezet.items() if pad != "/api/gesprekken"}
    nagaan.update({f"dagbundelaar {pad}": json.dumps(lijst, ensure_ascii=False) for pad, lijst in bundel.items()})
    nagaan.update({"fathom scherm": scherm, "dagbundelaar scherm": bundel_scherm})
    nagaan.update({f"export {pad}": t for pad, t in gelezen.items()})
    for waar, tekst in nagaan.items():
        for geheim in GEHEIM:
            assert geheim not in tekst, f"{geheim!r} staat in {waar}: {tekst[:2000]}"


# ------------------------------------------------------------------------------------------------- RZ4-01 ---
# Regels die een privé-item noemen, in elke schrijfwijze van de markering, en regels die moeten blijven staan.
PRIVE_REGELS = [
    "2026-10-20 22:00 Plaud: Proefpersoon Zeta · Proefonderwerp Omega · Prive",
    "2026-10-20 22:00 Plaud: Proefpersoon Zeta · Proefonderwerp Omega · PRIVE",
    "- transcript: 2026-10-20 22:00 Plaud: Proefpersoon Zeta · Proefonderwerp Omega · prive (Data uit Mehdi/Plaud/proef.md)",
    "Toe te wijzen: 2026-10-20 22:00 Plaud: Proefpersoon Zeta · Privé; 2026-10-20T10:00 Fathom: Jan Klant · Dakkapel nakijken",
    "Proefpersoon Zeta · Prive · Proefonderwerp Omega · zekerheid hoog",
    "Proefpersoon Zeta · dossier geen (laag) · PRIVE · voor mehdi",
    "Proefpersoon Zeta · dossier geen (laag) · Privé · voor mehdi",
    "2026-10-20 20:00 Proefpersoon Zeta, Mehdi | Prive | Proefonderwerp Omega",
    "2026-10-20 20:00 Proefpersoon Zeta, Mehdi | PRIVÉ | Proefonderwerp Omega",
]
GEWONE_REGELS = [
    "- transcript: privégesprek, 25 min",
    "Toe te wijzen: privégesprek, 25 min; privégesprek, duur onbekend",
    "privégesprek · 40 min · voor mehdi",
    "Zoom 20-10: 1 gesprekken (0 met Fathom, 1 alleen in Zoom), 40 min",
    "Zoom 2026-10-19: 6 berichten in 2 gesprek(ken) (1 privé), 2 meeting(s), 75 min",
    "Mailwacht prive: 3 mails gelezen",
    "2026-10-20T10:00 Fathom: Jan Klant · Dakkapel nakijken",
    "2026-10-20 10:00 Jan Klant | regie | Dakkapel nakijken",
]


def test_rz4_01_prive_in_elke_schrijfwijze():
    """RZ4-01, deel release 1 (herstelcontrole van Codex, 22-10-2026): het exportmasker herkende alleen 'PRIVÉ' in
    hoofdletters en ' · privé', ' | prive | ' en ' · prive · ' in kleine letters. Een titel of regel met 'Prive', 'PRIVE'
    of 'Privé' als veld (De Plaudwacht schreef de afdeling met een hoofdletter) ging voluit naar Data uit Mehdi. Nu
    herkent het de markering in elke schrijfwijze, als woord in hoofdletters of als eigen veld tussen ' · ' of ' | ', ook
    voor een verwijzing tussen haakjes of een volgende titel na een puntkomma. De veilige vorm 'privégesprek, N min', een
    telling '(1 privé)' en een agentnaam blijven staan."""
    import bord_export as E  # noqa: PLC0415
    uit = E.zonder_prive_regels("\n".join(PRIVE_REGELS + GEWONE_REGELS)).split("\n")
    assert uit == ["(privé)"] * len(PRIVE_REGELS) + GEWONE_REGELS, list(zip(PRIVE_REGELS + GEWONE_REGELS, uit))
    for titel in PRIVE_REGELS[:2]:
        assert E.is_prive(titel, json.dumps({"datum": DAG_RZ2, "prive": False})), titel
    for titel in GEWONE_REGELS[3:5]:
        assert not E.is_prive(titel, json.dumps({"datum": DAG_RZ2, "telling": "volledig"})), titel
    assert E.is_prive("titel", json.dumps({"afdeling": "PRIVÉ"})) and E.is_prive("titel", json.dumps({"afdeling": "Prive"}))


def _zoom_prive():
    """Een nieuw privé-Zoomgesprek zoals De Zoomwacht het nu klaarzet, met haar eigen functies: het zoom-tekst-item voor
    De Regisseur (tekst_item) en de dagregel voor Mehdi (dag_inhoud en dag_titel). Het gesprek heeft een herkenbare naam
    en een herkenbaar onderwerp; het archief op de VM houdt het onderwerp in zijn naam."""
    import zoom_wacht as ZW  # noqa: PLC0415
    start = datetime(2026, 10, 20, 18, 0, tzinfo=timezone.utc)
    ik = {"id": "u-mehdi", "email": EIGEN_ADRES, "pmi": "900000001"}
    s = {"uuid": "proefsessie-zeta==", "start": start, "einde": start + timedelta(minutes=40),
         "deelnemers": [{"naam": "Proefpersoon Zeta", "email": "zeta@proef.test"}, {"naam": "Mehdi", "id": "u-mehdi"}],
         "onderwerp": "Proefonderwerp Omega", "nummer": "900000002", "host_id": "u-mehdi"}
    archief = os.path.join(MAP, "zoom-data", "2026-10-20 2000 Zoom Proefonderwerp Omega [ab12cd34]")
    x = {"s": s, "toestand": "vangnet: tekst bewaard", "prive": True, "archief": archief, "gesprek": True, "reden": "",
         "leider": None}
    tekst = dict(ZW.tekst_item(x, ik), van="zoom-wacht")
    w = {"koppeling": {"gezien": []}, "onleesbaar": [], "chat_dag": {}, "ik": ik,
         "bronnen": {b: "ok" for b in ZW.ZOOM_BRONNEN + ("fathom-archief", "fathom-api", "chat")}}
    inhoud = ZW.dag_inhoud("2026-10-20", w, [x], "volledig", [])
    dag = {"van": "zoom-wacht", "voor": "mehdi", "soort": "zoom", "sleutel": "", "titel": ZW.dag_titel(inhoud),
           "uniek": "zoom:dag:2026-10-20", "inhoud": inhoud}
    return tekst, dag


# Een dagregel van De Zoomwacht van voor 21-10-2026 (de oude vorm: met meetings, zonder telling). Haar lijst werk noemde
# mensen en onderwerp van elk gesprek dat de oude regel geen privé vond: een meeting was werk tenzij elke andere deelnemer
# een privénaam had.
OUDE_ZOOMREGEL = {"van": "zoom-wacht", "voor": "mehdi", "soort": "zoom", "sleutel": "2026-10-19", "uniek": "zoom:dag:2026-10-19",
                  "titel": "Zoom 2026-10-19: 6 berichten in 2 gesprek(ken) (1 privé), 2 meeting(s), 75 min",
                  "inhoud": {"datum": "2026-10-19", "berichten": 6, "gesprekken": 2, "prive_gesprekken": 1, "meetings": 2,
                             "meeting_minuten": 75, "werk": ["Proefpersoon Zeta, Mehdi (Proefonderwerp Omega)",
                                                             "Jan Klant (Dakkapel nakijken)"]}}


def test_rz4_01_k4_zoom_prive_door_bronnen_van_en_de_export():
    """K4 (ontwerpronde RZ5, voorwaarde voor release 1): een nieuw privé-Zoomgesprek zet via De Levenscoach (bronnen_van,
    wat naar het taalmodel gaat) en via de export (zonder_prive_regels, is_prive) geen naam of onderwerp in Data uit
    Mehdi. RZ4-01: ook een oude Zoom-dagregel niet, en geen item of regel met 'Prive' in een andere schrijfwijze. Van een
    oude dagregel toont de export de aantallen, en van werk alleen hoeveel. Een werkgesprek in een nieuwe dagregel en
    een gewone regel blijven staan. Oude items van andere agents langs De Levenscoach horen bij het privacyproject."""
    tekst, dag = _zoom_prive()
    for veld in ("titel", "verwijzing", "inhoud"):
        for geheim in GEHEIM:
            assert geheim not in json.dumps(tekst[veld], ensure_ascii=False), (veld, tekst)
            assert geheim not in json.dumps(dag.get(veld) or "", ensure_ascii=False), (veld, dag)
    assert tekst["titel"].endswith(" · PRIVÉ") and tekst["voor"] == "regisseur" and dag["voor"] == "mehdi", (tekst, dag)

    # De Levenscoach: bronnen_van leest alles wat voor Mehdi klaarstaat (het bord filtert op voor=mehdi)
    bak = [dict(it, id=i, status="klaar", inhoud=json.dumps(it["inhoud"], ensure_ascii=False)) for i, it in enumerate((tekst, dag), start=1)]
    thuis, os.environ["HOME"] = os.environ.get("HOME"), tempfile.mkdtemp(prefix="thuis-")   # geen echte ~/agents/.env
    try:
        import levenscoach as L  # noqa: PLC0415
    finally:
        os.environ["HOME"] = thuis
    gevraagd, echt = [], bord.call
    bord.call = lambda pad, *a, **k: gevraagd.append(pad) or {"items": [it for it in bak if "voor=mehdi" not in pad or it["voor"] == "mehdi"]}
    try:
        bronnen = L.bronnen_van(["2026-10-20"])
    finally:
        bord.call = echt
    assert gevraagd and all("voor=mehdi" in p for p in gevraagd), gevraagd
    assert [it["soort"] for it in bronnen["2026-10-20"]] == ["zoom"], bronnen
    for geheim in GEHEIM:
        assert geheim not in json.dumps(bronnen, ensure_ascii=False), (geheim, bronnen)

    # zonder_prive_regels: een bundel of Dagverslag die het zoom-tekst-item bij titel en verwijzing noemt
    import bord_export as E  # noqa: PLC0415
    regels = [f"- zoom-tekst: {tekst['titel']} ({tekst['verwijzing']})", f"Zoom: {dag['titel']}", f"Zoom: {OUDE_ZOOMREGEL['titel']}"]
    assert E.zonder_prive_regels("\n".join(regels)).split("\n") == ["(privé)", regels[1], regels[2]]

    # de export: de Zoom-items, een oude dagregel, een item met ' · Prive' en een Dagverslag en werkverslag die ze noemen
    plaud = {"van": "plaud-wacht", "voor": "mehdi", "soort": "transcript", "sleutel": "", "uniek": "plaud:rz4",
             "titel": PRIVE_REGELS[0], "verwijzing": "Data uit Mehdi/Plaud/2026-10-20 2200 Proefpersoon Zeta/transcript.md",
             "inhoud": {"datum": DAG_RZ2, "start": "22:00", "prive": False, "personen": ["Proefpersoon Zeta"], "thema": "Proefonderwerp Omega"}}
    verslag = "\n".join([f"Dagverslag {DAG_RZ2}: 3 bronnen in 1 bundel(s).", f"Zoom: {dag['titel']}", PRIVE_REGELS[3],
                         "", f"Dossier (zonder dossier) op {DAG_RZ2}: 1 transcript", PRIVE_REGELS[2], GEWONE_REGELS[6]])
    klaarzet = [tekst, dag, OUDE_ZOOMREGEL, plaud,
                {"van": "dagbundelaar", "voor": "mehdi", "soort": "dagbundel", "sleutel": DAG_RZ2, "titel": f"Dagverslag {DAG_RZ2}",
                 "uniek": f"dagverslag:{DAG_RZ2}", "inhoud": verslag}]
    logboek = [{"naam": "plaud-wacht", "onderwerp": "opname 2026-10-20T22:00", "stap": "bevinding", "tekst": PRIVE_REGELS[4],
                "detail": "afdeling Prive; Proefpersoon Zeta over het Proefonderwerp Omega"},
               {"naam": "fathom-wacht", "onderwerp": "Fathom", "stap": "bron", "tekst": "2 gesprekken sinds 2026-10-06",
                "detail": PRIVE_REGELS[7] + "\n" + GEWONE_REGELS[7]},
               {"naam": "dagbundelaar", "onderwerp": f"dag {DAG_RZ2}", "stap": "bevinding", "tekst": "3 klaargezette bronnen",
                "detail": verslag}]
    gelezen = export(export_db("rz4-01"), klaarzet, logboek)
    for pad, inhoud in gelezen.items():
        for geheim in GEHEIM:
            assert geheim not in inhoud, f"{geheim!r} staat in export {pad}: {inhoud[:2000]}"
    deel = lambda *paden: "".join(t for pad, t in gelezen.items() if pad.startswith(os.path.join("export", *paden)))  # noqa: E731
    zoom = deel("Zoomwacht", "klaargezet")
    assert zoom.count("): (privé)") == 1 and dag["titel"] in zoom, zoom
    assert OUDE_ZOOMREGEL["titel"] in zoom and "werk: 2 stuks (namen en onderwerpen niet in de export)" in zoom, zoom
    assert "meetings: 2" in zoom and "Jan Klant" not in zoom, "van een oude dagregel de aantallen, van werk alleen hoeveel"
    assert deel("Plaud", "klaargezet").count("): (privé)") == 1, deel("Plaud", "klaargezet")
    assert "Jan Klant | regie | Dakkapel nakijken" in deel("Fathom", "werkverslag"), "een gewone regel blijft"
    assert "Jan Klant · Dakkapel nakijken" in deel("Dagbundelaar", "dagverslagen"), deel("Dagbundelaar", "dagverslagen")


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

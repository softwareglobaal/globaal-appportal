"""De generator, vastgezet (Codex NA08, 16-10-2026; AGENTNORM.md 8).

Tot 16-10-2026 registreerde nieuwe-agent.py een agent op het bord voor hij de werkwijze las of de runner
schreef, en waren rol, mandaat en werkwijze niet verplicht. Een fout liet een halve kaart achter. Nu wordt
alles eerst gecontroleerd, en gaat een agent pas op de cron na een gecontroleerde eerste ronde.

Het bord wordt nagebootst op het niveau van urllib.request.urlopen, zodat elke route naar het bord hier
uitkomt en niets het echte bord raakt. De runner komt in een tijdelijke map: testagents nooit op echte data.
"""
import importlib.util
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
sys.path.insert(0, RUNNER)
import bord  # noqa: E402

WERKWIJZE = """# De Postwacht

Versie 1.0. Hij leest nieuwe post op info@ en zet voor elk bericht een label klaar als voorstel. Hij werkt
elk uur, alleen lezend, en meldt wat hij niet kan plaatsen. Deze tekst is lang genoeg om de norm te halen,
want een werkwijze van een paar regels zegt niet genoeg om na te kijken of hij zich eraan hield.

## Wat ik doe
- elk uur de nieuwe post lezen
- per bericht een label voorstellen

## Wat ik nooit doe
- nooit een bericht verwijderen
- nooit iets versturen namens iemand

## Wat Mehdi beslist
- welke labels er bestaan
- wat er met twijfelgevallen gebeurt

## Bronnen
- het postvak info@, alleen lezend
"""

KAART = ["--naam", "post-wacht", "--label", "De Postwacht", "--type", "h-architects",
         "--rol", "sorteert nieuwe post op info@", "--mandaat", "lezen en labelen, nooit verwijderen",
         "--cadans", "elk uur", "--mag", "post labelen", "--grens", "nooit verwijderen"]


class Antwoord:
    def __init__(self, data):
        self.data = json.dumps(data).encode()

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class NepBord:
    """Wat er op het bord staat, en elke oproep die binnenkwam."""

    def __init__(self, agents=None, faal_werkwijze_zetten=False):
        self.agents = agents or {}          # naam -> {"kaart": dict, "werkwijze": str}
        self.oproepen = []
        self.faal_werkwijze_zetten = faal_werkwijze_zetten

    def urlopen(self, req, timeout=None):
        pad = urllib.parse.urlsplit(req.full_url).path
        data = json.loads(req.data.decode()) if req.data else None
        self.oproepen.append((req.get_method(), pad, data))
        if pad == "/api/agent" and req.get_method() == "POST":
            self.agents.setdefault(data["naam"], {"werkwijze": ""})["kaart"] = data
            return Antwoord({"ok": True, "naam": data["naam"]})
        if pad == "/api/agents":
            return Antwoord([{"naam": n, "actief": 1, **{v: (a.get("kaart") or {}).get(v, "")
                                                      for v in ("label", "type", "rol", "cadans")}}
                             for n, a in self.agents.items()])
        if pad.startswith("/api/agent/") and pad.endswith("/werkwijze"):
            naam = pad.split("/")[3]
            if naam not in self.agents:
                raise urllib.error.HTTPError(req.full_url, 404, "niet gevonden", None, None)
            if req.get_method() == "GET":
                return Antwoord({"naam": naam, "werkwijze": self.agents[naam]["werkwijze"]})
            if self.faal_werkwijze_zetten:
                self.faal_werkwijze_zetten = False
                raise urllib.error.URLError("verbinding verbroken")
            if self.agents[naam]["werkwijze"].strip() and not data.get("overschrijf"):
                return Antwoord({"ok": False, "reden": "werkwijze bestaat al op het bord; niet overschreven"})
            self.agents[naam]["werkwijze"] = (data.get("werkwijze") or "").strip()
            return Antwoord({"ok": True})
        raise AssertionError(f"onverwachte bordoproep {req.get_method()} {pad}")

    def registraties(self):
        return [o for o in self.oproepen if o[0] == "POST"]


class Proef:
    """De generator in een tijdelijke map, tegen een nagebootst bord."""

    def __init__(self, bord_=None):
        self.map = tempfile.mkdtemp(prefix="nieuwe-agent-")
        self.bord = bord_ or NepBord()
        self.ww = os.path.join(self.map, "post-wacht.md")
        with open(self.ww, "w", encoding="utf-8") as f:
            f.write(WERKWIJZE)
        spec = importlib.util.spec_from_file_location("nieuwe_agent_proef", os.path.join(RUNNER, "nieuwe-agent.py"))
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        if hasattr(self.mod, "RUNNERMAP"):
            self.mod.RUNNERMAP = self.map
        self._omgeving = {k: os.environ.get(k) for k in ("AGENTS_TOKEN", "PROEF_DB", "PROEF_STATUS", "PROEF_KENNIS")}
        self._ca = getattr(self.mod, "controle_agenten", None)
        self._ca_db = self._ca.DB if self._ca is not None else None
        self._ca_runner = self._ca.RUNNER if self._ca is not None else None

    def draai(self, *argv):
        echt_urlopen, echt_token = urllib.request.urlopen, bord.TOKEN
        urllib.request.urlopen, bord.TOKEN = self.bord.urlopen, "proeftoken"
        os.environ["AGENTS_TOKEN"] = "proeftoken"
        uit = io.StringIO()
        try:
            with redirect_stdout(uit), redirect_stderr(io.StringIO()):
                try:
                    code = self.mod.main(list(argv)) if self.mod.main.__code__.co_argcount else self._oud(argv)
                except SystemExit as e:
                    code = e.code
                except Exception as e:  # noqa: BLE001  de oude generator brak hier soms
                    code = f"brak: {type(e).__name__}"
        finally:
            urllib.request.urlopen, bord.TOKEN = echt_urlopen, echt_token
        self.uitvoer = uit.getvalue()
        return code

    def _oud(self, argv):
        echt = sys.argv
        sys.argv = ["nieuwe-agent.py"] + list(argv)
        try:
            return self.mod.main()
        finally:
            sys.argv = echt

    def runner(self):
        return os.path.join(self.map, "post_wacht.py")

    def weg(self):
        """Opruimen en de omgeving terugzetten zoals ze was (Codex NA25)."""
        for k, v in self._omgeving.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if self._ca is not None:
            self._ca.DB, self._ca.RUNNER = self._ca_db, self._ca_runner   # Codex NA29
        shutil.rmtree(self.map, ignore_errors=True)


def _niets_geschreven(p):
    assert not p.bord.registraties(), f"er kwam iets op het bord voor de controle klaar was: {p.bord.registraties()}"
    assert "post-wacht" not in p.bord.agents, "er staat een halve kaart op het bord"
    assert not os.path.exists(p.runner()), "er staat een runner op schijf terwijl de agent niet aangemaakt is"


def test_zonder_mandaat_komt_er_niets_op_het_bord():
    p = Proef()
    try:
        argv = [a for a in KAART]
        i = argv.index("--mandaat")
        del argv[i:i + 2]
        code = p.draai(*argv, "--werkwijze", p.ww)
        assert code not in (0, None), f"exitcode {code}: zonder mandaat hoort de generator te weigeren"
        _niets_geschreven(p)
        assert "mandaat" in p.uitvoer
    finally:
        p.weg()


def test_zonder_werkwijze_komt_er_niets_op_het_bord():
    p = Proef()
    try:
        code = p.draai(*KAART)
        assert code not in (0, None), f"exitcode {code}: zonder werkwijze hoort de generator te weigeren"
        _niets_geschreven(p)
    finally:
        p.weg()


def test_werkwijze_die_niet_bestaat_laat_geen_halve_kaart_achter():
    p = Proef()
    try:
        code = p.draai(*KAART, "--werkwijze", os.path.join(p.map, "bestaat-niet.md"))
        assert code not in (0, None)
        _niets_geschreven(p)
    finally:
        p.weg()


def test_werkwijze_zonder_de_koppen_van_n2_wordt_geweigerd():
    """Het woord nooit ergens in de tekst is niet genoeg: er hoort een kop met punten onder (AGENTNORM 8)."""
    p = Proef()
    try:
        tekst = WERKWIJZE.replace("## Wat ik nooit doe", "## Wat ik laat").replace("## Wat Mehdi beslist", "## Overig")
        with open(p.ww, "w", encoding="utf-8") as f:
            f.write(tekst)
        code = p.draai(*KAART, "--werkwijze", p.ww)
        assert code not in (0, None)
        _niets_geschreven(p)
        assert "Wat ik nooit doe" in p.uitvoer and "Wat Mehdi beslist" in p.uitvoer, p.uitvoer
    finally:
        p.weg()


def test_kop_over_wat_een_ander_nooit_doet_wordt_geweigerd():
    """Codex NA27: "Wat ik weet over wat de klant nooit doet" is geen grens van de agent."""
    p = Proef()
    try:
        with open(p.ww, "w", encoding="utf-8") as f:
            f.write(WERKWIJZE.replace("## Wat ik nooit doe", "## Wat ik weet over wat de klant nooit doet"))
        code = p.draai(*KAART, "--werkwijze", p.ww)
        assert code not in (0, None)
        _niets_geschreven(p)
        assert "Wat ik nooit doe" in p.uitvoer, p.uitvoer
    finally:
        p.weg()


def test_herstel_zet_nooit_een_ander_zaad_dan_de_goedgekeurde_tekst():
    """Codex NA26: breekt het zetten van de werkwijze en staat er in werkwijze/ een oudere versie, dan zou het
    herstel die oudere regels zetten. Het herstel zegt dat, en zet eerst de goedgekeurde tekst erin."""
    nb = NepBord(faal_werkwijze_zetten=True)
    p = Proef(nb)
    try:
        os.makedirs(os.path.join(p.map, "werkwijze"))
        zaad = os.path.join(p.map, "werkwijze", "post-wacht.md")
        with open(zaad, "w", encoding="utf-8") as f:
            f.write("# Oude versie\n\n## Wat ik nooit doe\n- iets anders\n")
        code = p.draai(*KAART, "--werkwijze", p.ww)
        assert code not in (0, None)
        uit = p.uitvoer
        assert "is niet de werkwijze die je meegaf" in uit, uit
        cp = uit.index(f"cp '{p.ww}' '{zaad}'")
        assert cp < uit.index("werkwijze_naar_bord.py post-wacht --zet"), "eerst de goedgekeurde tekst in het zaad, dan zetten"
        assert "geen werkwijze" in uit, "het herstel toont wat er nu op het bord staat"
    finally:
        p.weg()


def test_te_korte_werkwijze_wordt_geweigerd():
    p = Proef()
    try:
        with open(p.ww, "w", encoding="utf-8") as f:
            f.write("## Wat ik nooit doe\n- verwijderen\n\n## Wat Mehdi beslist\n- alles\n")
        code = p.draai(*KAART, "--werkwijze", p.ww)
        assert code not in (0, None)
        _niets_geschreven(p)
        assert "N1" in p.uitvoer
    finally:
        p.weg()


def test_bestaande_agent_wordt_niet_overschreven():
    """Een bestaande agent breid je uit; de generator overschrijft zijn kaart niet."""
    nb = NepBord(agents={"post-wacht": {"kaart": {"naam": "post-wacht", "rol": "de echte rol"},
                                        "werkwijze": "# Bestaande werkwijze"}})
    p = Proef(nb)
    try:
        code = p.draai(*KAART, "--werkwijze", p.ww)
        assert code not in (0, None)
        assert not nb.registraties(), "de kaart van een bestaande agent werd overschreven"
        assert nb.agents["post-wacht"]["kaart"]["rol"] == "de echte rol"
    finally:
        p.weg()


def test_bestaande_runner_met_eigen_code_wordt_niet_geraakt():
    p = Proef()
    try:
        with open(p.runner(), "w", encoding="utf-8") as f:
            f.write("# eigen code\n")
        code = p.draai(*KAART, "--werkwijze", p.ww)
        assert code not in (0, None)
        assert not p.bord.registraties(), "geregistreerd terwijl de runner al eigen code had"
        assert open(p.runner(), encoding="utf-8").read() == "# eigen code\n"
    finally:
        p.weg()


def test_volledige_kaart_wordt_aangemaakt_en_teruggelezen_zonder_cron():
    """Alles klopt: runner, kaart en werkwijze staan er, de werkwijze is teruggelezen, en de cron-regel
    komt pas na de eerste ronde, niet nu."""
    p = Proef()
    try:
        code = p.draai(*KAART, "--werkwijze", p.ww)
        assert code == 0, p.uitvoer
        assert p.bord.agents["post-wacht"]["werkwijze"] == WERKWIJZE.strip()
        kaart = p.bord.agents["post-wacht"]["kaart"]
        assert kaart["mandaat"] and kaart["grenzen"] == ["nooit verwijderen"] and kaart["mag"] == ["post labelen"]
        assert os.path.exists(p.runner())
        stappen = [(m, pad) for m, pad, _ in p.bord.oproepen]
        assert stappen == [("GET", "/api/agent/post-wacht/werkwijze"), ("POST", "/api/agent"),
                           ("POST", "/api/agent/post-wacht/werkwijze"), ("GET", "/api/agent/post-wacht/werkwijze")], stappen
        assert ">> ~/agents/" not in p.uitvoer, "de cron-regel hoort pas na een gecontroleerde eerste ronde"
        assert "--eerste-ronde post-wacht" in p.uitvoer
    finally:
        p.weg()


def test_breuk_na_registratie_zegt_hoe_je_de_werkwijze_zet():
    """Valt het bord weg net na de registratie, dan zegt de generator dat, met het commando om de werkwijze te
    zetten. Hetzelfde commando opnieuw hervat niet: het herkent de kaart niet als de zijne (Codex NA20)."""
    nb = NepBord(faal_werkwijze_zetten=True)
    p = Proef(nb)
    try:
        code = p.draai(*KAART, "--werkwijze", p.ww)
        assert code not in (0, None), "een kaart zonder werkwijze is geen geslaagde aanmaak"
        assert "werkwijze_naar_bord.py post-wacht" in p.uitvoer and "--zet" in p.uitvoer, p.uitvoer
        assert nb.agents["post-wacht"]["werkwijze"] == ""
        registraties = len([o for o in nb.oproepen if o[1] == "/api/agent"])
        code = p.draai(*KAART, "--werkwijze", p.ww)
        assert code not in (0, None), "de generator hervat niet zelf"
        assert len([o for o in nb.oproepen if o[1] == "/api/agent"]) == registraties, "de kaart werd opnieuw geregistreerd"
        assert "werkwijze_naar_bord.py post-wacht" in p.uitvoer, p.uitvoer
    finally:
        p.weg()


def test_lege_kaart_van_een_ander_wordt_niet_overgenomen():
    """Codex NA13: een kaart zonder werkwijze is niet vanzelf de eigen afgebroken poging. Zonder het skelet van
    die poging hier, of met een andere kaart op het bord, raakt de generator ze niet."""
    for runner_er, kaart in ((False, {"naam": "post-wacht", "label": "De Postwacht", "type": "h-architects",
                                      "rol": "sorteert nieuwe post op info@", "cadans": "elk uur"}),
                             (True, {"naam": "post-wacht", "label": "Iets anders", "type": "regie",
                                     "rol": "een andere agent", "cadans": "elke dag"}),
                             # Codex NA20: dezelfde zichtbare velden, het skelet hier, maar een ander mandaat
                             (True, {"naam": "post-wacht", "label": "De Postwacht", "type": "h-architects",
                                     "rol": "sorteert nieuwe post op info@", "cadans": "elk uur",
                                     "mandaat": "iets heel anders"})):
        nb = NepBord(agents={"post-wacht": {"kaart": dict(kaart), "werkwijze": ""}})
        p = Proef(nb)
        try:
            if runner_er:
                with open(os.path.join(RUNNER, "_sjabloon_agent.py"), encoding="utf-8") as f:
                    skelet = f.read().replace("%%NAAM%%", "post-wacht").replace("%%LABEL%%", "post-wacht")
                with open(p.runner(), "w", encoding="utf-8") as f:
                    f.write(skelet)
            code = p.draai(*KAART, "--werkwijze", p.ww)
            assert code not in (0, None), f"exitcode {code}: een lege kaart van een ander hoort niet overgenomen"
            assert not nb.registraties(), f"de kaart werd overschreven: {nb.registraties()}"
            assert nb.agents["post-wacht"]["kaart"] == kaart and nb.agents["post-wacht"]["werkwijze"] == ""
        finally:
            p.weg()


def test_bord_dat_niet_antwoordt_is_geen_vrije_naam():
    """Onbekend is niet vrij: weet het bord niet of de naam bestaat, dan wordt er niets aangemaakt."""
    class WegBord(NepBord):
        def urlopen(self, req, timeout=None):
            self.oproepen.append((req.get_method(), urllib.parse.urlsplit(req.full_url).path, None))
            raise urllib.error.URLError("verbinding geweigerd")

    p = Proef(WegBord())
    try:
        code = p.draai(*KAART, "--werkwijze", p.ww)
        assert code not in (0, None)
        assert not p.bord.registraties()
        assert not os.path.exists(p.runner())
    finally:
        p.weg()


# --- de eerste ronde --------------------------------------------------------------------------------------
# Codex NA14 en NA19: de runner draait echt (een proefrunner als los proces), en wat het bord toont moet van
# die ronde zijn. De opstelling hangt niet af van de generator zelf, zodat ze ook tegen een oudere versie draait.

KENNIS = ("werkwijze op het bord: 900 tekens, abcdef12\ngedeelde lessen: 10 tekens, abcdef12\n"
          "collega's op het bord: 10 tekens, abcdef12")

# Doet wat een echte ronde op het bord achterlaat: hartslag en gemelde kennis, nu. (ag.ronde( staat hier voor N12.)
RUNNER_VERS = """import os, sqlite3  # ag.ronde(
from datetime import datetime, timedelta, timezone
nu = datetime.now(timezone.utc).isoformat()
con = sqlite3.connect(os.environ["PROEF_DB"])
con.execute("update status set status=?, ts=? where naam='post-wacht'", (os.environ.get("PROEF_STATUS", "klaar"), nu))
con.execute("update agent set kennis=?, kennis_ts=? where naam='post-wacht'", (os.environ.get("PROEF_KENNIS", %r), nu))
con.commit()
""" % KENNIS

# Eindigt met code 0 en doet niets: wat het bord toont, is van een eerdere ronde. (ag.ronde( in commentaar.)
RUNNER_LUI = "print('niets gedaan')  # ag.ronde(\n"

RUNNER_FAALT = "raise SystemExit(1)  # ag.ronde(\n"


def _toen(uren):
    return (datetime.now(timezone.utc) - timedelta(hours=uren)).isoformat()


def _bord_db(map_):
    """Het bord zoals het er voor de eerste ronde uitziet: de kaart, en hartslag en kennis van twee uur geleden.
    Op zich halen die alle normen; alleen een verse ronde maakt het verschil."""
    db = os.path.join(map_, "mijnagents.db")
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE agent (naam TEXT PRIMARY KEY, label TEXT, type TEXT, rol TEXT, mandaat TEXT, mag TEXT,
            grenzen TEXT, cadans TEXT, tools TEXT, eigenaar TEXT, actief INTEGER, aangemaakt TEXT, werkwijze TEXT,
            kennis TEXT, kennis_ts TEXT, kennis_bron TEXT, draait_op TEXT);
        CREATE TABLE status (naam TEXT PRIMARY KEY, status TEXT, taak TEXT, detail TEXT, tokens INTEGER, ts TEXT);
        CREATE TABLE nood (id INTEGER PRIMARY KEY, naam TEXT, tekst TEXT, wie TEXT, open INTEGER, ts TEXT,
            opgelost_ts TEXT);
    """)
    con.execute("INSERT INTO agent VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?,?,?,?,?)",
                ("post-wacht", "De Postwacht", "h-architects", "sorteert post", "lezen en labelen",
                 '["post labelen"]', '["nooit verwijderen"]', "elk uur", "[]", "mehdi", _toen(3), WERKWIJZE.strip(),
                 KENNIS, _toen(2), "werkwijze op het bord", "VM"))
    con.execute("INSERT INTO status VALUES(?,?,?,?,?,?)", ("post-wacht", "klaar", "ronde", "", None, _toen(2)))
    con.commit()
    con.close()
    return db


def _eerste_ronde_proef(runner_code, met_agent=True):
    p = Proef(NepBord(agents={"post-wacht": {"kaart": {}, "werkwijze": WERKWIJZE.strip()}}))
    with open(p.runner(), "w", encoding="utf-8") as f:
        f.write(runner_code)
    os.makedirs(os.path.join(p.map, "werkwijze"))
    shutil.copy(os.path.join(RUNNER, "werkwijze", "lessen.json"), os.path.join(p.map, "werkwijze", "lessen.json"))
    db = _bord_db(p.map)
    if not met_agent:
        con = sqlite3.connect(db)
        con.execute("DELETE FROM agent")
        con.commit()
        con.close()
    os.environ["PROEF_DB"] = db
    os.environ.pop("PROEF_STATUS", None)
    os.environ.pop("PROEF_KENNIS", None)
    ca = getattr(p.mod, "controle_agenten", None)
    if ca is not None:
        ca.DB = db
    return p


def test_eerste_ronde_geeft_de_cron_pas_als_de_controle_slaagt():
    p = _eerste_ronde_proef(RUNNER_VERS)
    try:
        code = p.draai("--eerste-ronde", "post-wacht", "--cron", "5 * * * *")
        assert code == 0, p.uitvoer
        assert "5 * * * *" in p.uitvoer and ">> ~/agents/post-wacht.log" in p.uitvoer, p.uitvoer
    finally:
        p.weg()


def test_eerste_ronde_die_niets_deed_gaat_niet_op_de_cron():
    """Codex NA14: een runner die met code 0 niets doet, haalde de controle op de hartslag en de kennis van een
    eerdere ronde. Nu moet wat het bord toont van deze ronde zijn."""
    p = _eerste_ronde_proef(RUNNER_LUI)
    try:
        code = p.draai("--eerste-ronde", "post-wacht")
        assert code not in (0, None)
        assert "van deze ronde" in p.uitvoer and ">> ~/agents/" not in p.uitvoer, p.uitvoer
    finally:
        p.weg()


def test_eerste_ronde_aanvaardt_geen_hartslag_van_net_voor_de_start():
    """Codex NA21: met een marge van een seconde haalde een runner die niets deed de controle op een hartslag van
    een fractie voor de start. Nu telt alleen wat na de start op het bord kwam."""
    p = _eerste_ronde_proef(RUNNER_LUI)
    try:
        nu = datetime.now(timezone.utc).isoformat()
        con = sqlite3.connect(os.environ["PROEF_DB"])
        con.execute("update status set ts=? where naam='post-wacht'", (nu,))
        con.execute("update agent set kennis_ts=? where naam='post-wacht'", (nu,))
        con.commit()
        con.close()
        code = p.draai("--eerste-ronde", "post-wacht")
        assert code not in (0, None)
        assert "van deze ronde" in p.uitvoer and ">> ~/agents/" not in p.uitvoer, p.uitvoer
    finally:
        p.weg()


def test_eerste_ronde_weigert_het_skelet():
    with open(os.path.join(RUNNER, "_sjabloon_agent.py"), encoding="utf-8") as f:
        skelet = f.read().replace("%%NAAM%%", "post-wacht").replace("%%LABEL%%", "post-wacht")
    p = _eerste_ronde_proef(skelet)
    try:
        code = p.draai("--eerste-ronde", "post-wacht")
        assert code not in (0, None)
        assert "skelet" in p.uitvoer and ">> ~/agents/" not in p.uitvoer, p.uitvoer
    finally:
        p.weg()


def test_eerste_ronde_die_faalt_gaat_niet_op_de_cron():
    p = _eerste_ronde_proef(RUNNER_FAALT)
    try:
        code = p.draai("--eerste-ronde", "post-wacht")
        assert code not in (0, None)
        assert "code 1" in p.uitvoer and ">> ~/agents/" not in p.uitvoer, p.uitvoer
    finally:
        p.weg()


def test_eerste_ronde_die_op_fout_eindigt_gaat_niet_op_de_cron():
    p = _eerste_ronde_proef(RUNNER_VERS)
    os.environ["PROEF_STATUS"] = "fout"
    try:
        code = p.draai("--eerste-ronde", "post-wacht")
        assert code not in (0, None)
        assert "fout" in p.uitvoer and ">> ~/agents/" not in p.uitvoer, p.uitvoer
    finally:
        os.environ.pop("PROEF_STATUS", None)
        p.weg()


def test_eerste_ronde_met_gezakte_norm_gaat_niet_op_de_cron():
    """De ronde liep en is vers, maar ze las de gedeelde lessen niet (N13): niet op de cron."""
    p = _eerste_ronde_proef(RUNNER_VERS)
    os.environ["PROEF_KENNIS"] = "werkwijze op het bord: 900 tekens, abcdef12\ncollega's op het bord: 10 tekens, abcdef12"
    try:
        code = p.draai("--eerste-ronde", "post-wacht")
        assert code not in (0, None)
        assert "N13" in p.uitvoer and ">> ~/agents/" not in p.uitvoer, p.uitvoer
    finally:
        os.environ.pop("PROEF_KENNIS", None)
        p.weg()


def test_eerste_ronde_zonder_agent_in_de_controle_is_geen_groen_licht():
    """'0 agents getoetst, 0 gezakt' is geen geslaagde controle."""
    p = _eerste_ronde_proef(RUNNER_VERS, met_agent=False)
    try:
        code = p.draai("--eerste-ronde", "post-wacht")
        assert code not in (0, None)
        assert "niet als actieve agent" in p.uitvoer and ">> ~/agents/" not in p.uitvoer, p.uitvoer
    finally:
        p.weg()


if __name__ == "__main__":
    import traceback
    goed = fout = 0
    for naam, f in sorted(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                f()
                goed += 1
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"FOUT {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)

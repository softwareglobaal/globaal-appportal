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
from datetime import datetime, timezone

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
        assert "nooit doet" in p.uitvoer and "Mehdi beslist" in p.uitvoer, p.uitvoer
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


def test_breuk_na_registratie_maakt_hetzelfde_commando_af():
    """Valt het bord weg net na de registratie, dan zegt de generator dat, en maakt hetzelfde commando het af."""
    nb = NepBord(faal_werkwijze_zetten=True)
    p = Proef(nb)
    try:
        code = p.draai(*KAART, "--werkwijze", p.ww)
        assert code not in (0, None), "een kaart zonder werkwijze is geen geslaagde aanmaak"
        assert "opnieuw" in p.uitvoer, p.uitvoer
        assert nb.agents["post-wacht"]["werkwijze"] == ""
        code = p.draai(*KAART, "--werkwijze", p.ww)
        assert code == 0, p.uitvoer
        assert nb.agents["post-wacht"]["werkwijze"] == WERKWIJZE.strip()
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

def _nu():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _bord_db(map_, status="klaar"):
    """Een bord-databank met de nieuwe agent zoals hij er na een geslaagde eerste ronde hoort te staan."""
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
                 '["post labelen"]', '["nooit verwijderen"]', "elk uur", "[]", "mehdi", _nu(), WERKWIJZE.strip(),
                 "werkwijze op het bord: 900 tekens, abcdef12\ngedeelde lessen: 10 tekens, abcdef12\n"
                 "collega's op het bord: 10 tekens, abcdef12", _nu(), "werkwijze op het bord", "VM"))
    con.execute("INSERT INTO status VALUES(?,?,?,?,?,?)", ("post-wacht", status, "ronde", "", None, _nu()))
    con.commit()
    con.close()
    return db


def _eerste_ronde_proef(werk_ingevuld=True, ronde_code=0, status="klaar", met_agent=True):
    nb = NepBord(agents={"post-wacht": {"kaart": {}, "werkwijze": WERKWIJZE.strip()}})
    p = Proef(nb)
    code = p.mod.skelet("post-wacht")
    if werk_ingevuld:
        code = code.replace(p.mod.SKELET, "werk() ingevuld")
    with open(p.runner(), "w", encoding="utf-8") as f:
        f.write(code)
    os.makedirs(os.path.join(p.map, "werkwijze"))
    shutil.copy(os.path.join(RUNNER, "werkwijze", "lessen.json"), os.path.join(p.map, "werkwijze", "lessen.json"))
    db = _bord_db(p.map, status)
    if not met_agent:
        con = sqlite3.connect(db)
        con.execute("DELETE FROM agent")
        con.commit()
        con.close()
    p.gedraaid = []
    p.mod.draai = lambda pad: (p.gedraaid.append(pad), ronde_code)[1]
    p.mod.controle_agenten.DB = db
    return p


def test_eerste_ronde_geeft_de_cron_pas_als_de_controle_slaagt():
    p = _eerste_ronde_proef()
    try:
        code = p.draai("--eerste-ronde", "post-wacht", "--cron", "5 * * * *")
        assert code == 0, p.uitvoer
        assert p.gedraaid == [p.runner()], "de eerste ronde hoort de runner zelf te draaien"
        assert "5 * * * *" in p.uitvoer and ">> ~/agents/post-wacht.log" in p.uitvoer, p.uitvoer
    finally:
        p.weg()


def test_eerste_ronde_weigert_het_skelet():
    p = _eerste_ronde_proef(werk_ingevuld=False)
    try:
        code = p.draai("--eerste-ronde", "post-wacht")
        assert code not in (0, None)
        assert not p.gedraaid, "een skelet hoort niet te draaien"
        assert ">> ~/agents/" not in p.uitvoer
    finally:
        p.weg()


def test_eerste_ronde_die_faalt_gaat_niet_op_de_cron():
    p = _eerste_ronde_proef(ronde_code=1)
    try:
        code = p.draai("--eerste-ronde", "post-wacht")
        assert code not in (0, None)
        assert ">> ~/agents/" not in p.uitvoer
    finally:
        p.weg()


def test_eerste_ronde_met_gezakte_norm_gaat_niet_op_de_cron():
    """De ronde liep, maar de agent staat op fout (N11): niet op de cron."""
    p = _eerste_ronde_proef(status="fout")
    try:
        code = p.draai("--eerste-ronde", "post-wacht")
        assert code not in (0, None)
        assert "N11" in p.uitvoer and ">> ~/agents/" not in p.uitvoer, p.uitvoer
    finally:
        p.weg()


def test_eerste_ronde_zonder_agent_in_de_controle_is_geen_groen_licht():
    """'0 agents getoetst, 0 gezakt' is geen geslaagde controle."""
    p = _eerste_ronde_proef(met_agent=False)
    try:
        code = p.draai("--eerste-ronde", "post-wacht")
        assert code not in (0, None)
        assert ">> ~/agents/" not in p.uitvoer
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

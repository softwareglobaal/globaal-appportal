"""Grendels op WhatsApp als kanaal naar Mehdi (30-09-2026).

Afspraak: de meldingen van de agents gaan via WhatsApp, niet meer via Telegram; Telegram
is alleen het vangnet. Meta laat een bedrijfsnummer vrij schrijven binnen 24 uur na een
bericht van Mehdi, daarbuiten alleen met een sjabloon, en een sjabloonparameter mag geen
regeleinden bevatten. Geen netwerk, geen database: alles wordt nagebootst.

Draaien, zonder pytest:   python3 mijnagents-runner/tests/test_whatsapp.py
"""
import os
os.environ.setdefault("AGENDA_WHATSAPP_WACHTRIJ", os.path.join(__import__("tempfile").mkdtemp(prefix="aw-test-"), "agenda-whatsapp.json"))  # nooit de echte wachtrij
import sys

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import whatsapp as W  # noqa: E402
import tempfile  # noqa: E402

W.TELLER = os.path.join(tempfile.mkdtemp(), "wa_sjablonen.json")   # nooit de echte teller van de VM

INS = {"pnid": "123", "afzender": "+32470000000", "firma": "QQQQ", "mehdi": "+32470111111",
       "sjabloon": "", "taal": "nl", "versie": "v26.0", "heeft_token": True}


def met(venster_open, sjabloon=""):
    """Een stuur() met nagebootst venster; geeft (kanaal of fout, verstuurde bodies)."""
    verstuurd = []
    oud = (W.instellingen, W.venster, W._post)
    W.instellingen = lambda: dict(INS, sjabloon=sjabloon)
    W.venster = lambda ins=None: (venster_open, None)
    W._post = lambda ins, body: verstuurd.append(body) or "wamid.proef"
    try:
        return W.stuur("Mehdi Agents, 09:00:\n- signaal: proef\n- verslag: proef"), verstuurd
    except W.NietBeschikbaar as e:
        return f"niet: {e}", verstuurd
    finally:
        W.instellingen, W.venster, W._post = oud


def test_nummer_naar_e164():
    assert W.e164("0486 33 35 21") == "+32486333521"
    assert W.e164("+32486333521") == "+32486333521"
    assert W.e164("0032486333521") == "+32486333521"


def test_venster_open_geeft_vrije_tekst():
    kanaal, bodies = met(True)
    assert kanaal == "whatsapp" and bodies[0]["type"] == "text", (kanaal, bodies)
    assert bodies[0]["to"] == "32470111111"


def test_venster_dicht_met_sjabloon():
    kanaal, bodies = met(False, "agent_melding")
    assert kanaal == "whatsapp-sjabloon", kanaal
    param = bodies[0]["template"]["components"][0]["parameters"][1]["text"]
    assert "\n" not in param and "\t" not in param, param


def test_venster_dicht_zonder_sjabloon_stuurt_niets():
    kanaal, bodies = met(False)
    assert kanaal.startswith("niet: ") and "venster" in kanaal and not bodies, (kanaal, bodies)


def test_dagplafond_stopt_betaalde_sjablonen():
    """Kostenrem (01-10-2026): na WA_SJABLOON_MAX_PER_DAG sjablonen op een dag gaat er niets meer
    via een betaald sjabloon; vrije tekst binnen het venster blijft gratis en telt niet mee."""
    import tempfile
    oud_teller, oud_env = W.TELLER, W._env
    W.TELLER = os.path.join(tempfile.mkdtemp(), "teller.json")
    # zonder reserve: deze grendel toetst het plafond zelf; de reserve heeft T78 (B9, ontwerp regie-zoom v1.2)
    W._env = lambda: {"WA_SJABLOON_MAX_PER_DAG": "2", "WA_SJABLOON_RESERVE": "0"}
    try:
        uitslagen = [met(False, "agent_melding")[0] for _ in range(3)]
        assert uitslagen[:2] == ["whatsapp-sjabloon"] * 2, uitslagen
        assert uitslagen[2].startswith("niet: ") and "dagplafond" in uitslagen[2], uitslagen
        assert met(True)[0] == "whatsapp", "vrije tekst binnen het venster mag niet geblokkeerd worden"
        assert W.sjablonen_vandaag() == 2
    finally:
        W.TELLER, W._env = oud_teller, oud_env


def met_voorrang(venster_open, sjabloon, voorrang, kop="je agents"):
    """Zoals met(), maar met voorrang en kop: (kanaal of fout, verstuurde bodies)."""
    verstuurd = []
    oud = (W.instellingen, W.venster, W._post)
    W.instellingen = lambda: dict(INS, sjabloon=sjabloon)
    W.venster = lambda ins=None: (venster_open, None)
    W._post = lambda ins, body: verstuurd.append(body) or "wamid.proef"
    try:
        return W.stuur("1. proefpunt\nVolgende stap: op het bord", kop=kop, voorrang=voorrang), verstuurd
    except W.NietBeschikbaar as e:
        return f"niet: {e}", verstuurd
    finally:
        W.instellingen, W.venster, W._post = oud


def test_t78_reserve_voor_de_vaste_momenten():
    """T78 (B7): plafond 4, reserve 2. Een gewoon sjabloonbericht stopt bij het plafond min de reserve, een bericht met
    voorrang (ochtendbericht, avondbundel) pas bij het plafond."""
    import tempfile
    oud_teller, oud_env = W.TELLER, W._env
    W.TELLER = os.path.join(tempfile.mkdtemp(), "teller.json")
    W._env = lambda: {"WA_SJABLOON_MAX_PER_DAG": "4", "WA_SJABLOON_RESERVE": "2"}
    try:
        gewoon = [met_voorrang(False, "agent_melding", False)[0] for _ in range(3)]
        assert gewoon[:2] == ["whatsapp-sjabloon"] * 2, gewoon
        assert gewoon[2].startswith("niet: ") and "dagplafond" in gewoon[2] and "venster" not in gewoon[2], gewoon
        voorrang = [met_voorrang(False, "agent_melding", True)[0] for _ in range(3)]
        assert voorrang[:2] == ["whatsapp-sjabloon"] * 2, voorrang
        assert voorrang[2].startswith("niet: ") and "dagplafond" in voorrang[2], voorrang
        assert W.sjablonen_vandaag() == 4, W.sjablonen_vandaag()
        assert met_voorrang(True, "agent_melding", False)[0] == "whatsapp", "binnen het venster verandert er niets"
    finally:
        W.TELLER, W._env = oud_teller, oud_env


def test_t78_zonder_reserve_in_de_omgeving_is_ze_twee():
    oud_env = W._env
    W._env = lambda: {}
    try:
        assert W.reserve() == 2 and W.max_sjablonen() == 10
        W._env = lambda: {"WA_SJABLOON_RESERVE": "geen getal"}
        assert W.reserve() == 2
    finally:
        W._env = oud_env


def test_t79_de_teller_telt_per_brusselse_dag():
    """T79 (B7): de VM draait op UTC. Om 2026-10-21T22:30Z is het in Brussel al 22-10 (00:30); de teller schrijft die
    datum, en een teller van 21-10 telt dan niet meer mee."""
    import json
    import tempfile
    from datetime import datetime, timezone

    class Klok(datetime):
        @classmethod
        def now(cls, tz=None):
            vast = datetime(2026, 10, 21, 22, 30, tzinfo=timezone.utc)
            return vast.astimezone(tz) if tz else vast.replace(tzinfo=None)

    oud_teller, oud_env, oud_dt = W.TELLER, W._env, W.datetime
    W.TELLER = os.path.join(tempfile.mkdtemp(), "teller.json")
    with open(W.TELLER, "w", encoding="utf-8") as f:
        json.dump({"datum": "2026-10-21", "n": 10}, f)
    W._env = lambda: {"WA_SJABLOON_MAX_PER_DAG": "10", "WA_SJABLOON_RESERVE": "2"}
    W.datetime = Klok
    try:
        assert W.vandaag() == "2026-10-22", W.vandaag()
        kanaal, _ = met_voorrang(False, "agent_melding", False)
        assert kanaal == "whatsapp-sjabloon", f"de teller van 21-10 hoort niet meer te tellen: {kanaal}"
        with open(W.TELLER, encoding="utf-8") as f:
            assert json.load(f) == {"datum": "2026-10-22", "n": 1}
    finally:
        W.TELLER, W._env, W.datetime = oud_teller, oud_env, oud_dt


def test_eigen_kop_in_vrije_tekst_en_als_sjabloonparameter():
    """B2 en B7: een eigen kop (het ochtendbericht) is de eerste sjabloonparameter; in vrije tekst de eerste regel, een
    keer. De gewone kop verandert niets aan de vrije tekst."""
    import tempfile
    oud_teller = W.TELLER
    W.TELLER = os.path.join(tempfile.mkdtemp(), "teller.json")
    try:
        _, bodies = met_voorrang(False, "agent_melding", True, kop="Ochtendbericht do 22-10, 1 beslissing")
        params = bodies[0]["template"]["components"][0]["parameters"]
        assert params[0]["text"] == "Ochtendbericht do 22-10, 1 beslissing" and params[1]["text"].startswith("1. proefpunt"), params
        _, bodies = met_voorrang(True, "", True, kop="Ochtendbericht do 22-10, 1 beslissing")
        assert bodies[0]["text"]["body"].startswith("Ochtendbericht do 22-10, 1 beslissing\n\n1. proefpunt"), bodies
        _, bodies = met_voorrang(True, "", False)
        assert bodies[0]["text"]["body"].startswith("1. proefpunt"), bodies
    finally:
        W.TELLER = oud_teller


def test_plat_zonder_regeleinden_en_kort_genoeg():
    uit = W.plat("a\nb\t c" + "x" * 2000)
    assert "\n" not in uit and "\t" not in uit and len(uit) <= W.MAX_PARAM
    assert len(W.plat("a\nb\t c" + "x" * 2000, None)) > W.MAX_PARAM, "zonder grens knipt plat niet af (meten)"


def test_bode_stuurt_eerst_whatsapp():
    with open(os.path.join(HIER, "bode.py"), encoding="utf-8") as f:
        bron = f.read()
    stuk = bron[bron.index("def stuur(tekst, nood"):bron.index("def platte_tekst")]
    assert stuk.index("whatsapp.stuur") < stuk.index("stuur_telegram"), "Telegram staat weer voor WhatsApp"


if __name__ == "__main__":
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("   geslaagd  %s" % naam)
            except AssertionError as e:
                fouten += 1
                print("   MISLUKT   %s: %s" % (naam, e))
    print("%d van de %d grendels mislukt" % (fouten, sum(1 for n in globals() if n.startswith("test_"))))
    sys.exit(1 if fouten else 0)

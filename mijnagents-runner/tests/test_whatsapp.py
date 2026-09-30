"""Grendels op WhatsApp als kanaal naar Mehdi (30-09-2026).

Afspraak: de meldingen van de agents gaan via WhatsApp, niet meer via Telegram; Telegram
is alleen het vangnet. Meta laat een bedrijfsnummer vrij schrijven binnen 24 uur na een
bericht van Mehdi, daarbuiten alleen met een sjabloon, en een sjabloonparameter mag geen
regeleinden bevatten. Geen netwerk, geen database: alles wordt nagebootst.

Draaien, zonder pytest:   python3 mijnagents-runner/tests/test_whatsapp.py
"""
import os
import sys

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import whatsapp as W  # noqa: E402

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


def test_plat_zonder_regeleinden_en_kort_genoeg():
    uit = W.plat("a\nb\t c" + "x" * 2000)
    assert "\n" not in uit and "\t" not in uit and len(uit) <= W.MAX_PARAM


def test_bode_stuurt_eerst_whatsapp():
    with open(os.path.join(HIER, "bode.py"), encoding="utf-8") as f:
        bron = f.read()
    stuk = bron[bron.index("def stuur(tekst, nood):"):bron.index("def platte_tekst")]
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

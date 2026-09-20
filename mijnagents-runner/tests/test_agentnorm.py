"""De Agentnorm, vastgezet. Zie AGENTNORM.md.

Deze test bewaakt het minimum waar elke agent doorheen gaat: de ronde in
`koppelingen/bord.py`. Wie die doorgang weghaalt of uitholt, laat deze test
falen in plaats van het stilletjes kapot te maken.

Gemeten op 20-09-2026, en de reden dat dit bestaat: van de 39 runners haalden er
vier hun werkwijze van het bord op, en meldde er een enkele welk regelboek hij
las. De werkwijze was voor de rest decoratie.
"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import bord  # noqa: E402


class BordNabootsing:
    """Vangt op wat een ronde naar het bord stuurt, zonder netwerk."""

    def __init__(self, werkwijze="# Werkwijze\n\nWat ik nooit doe: niets.\nWat Mehdi beslist: alles."):
        self.werkwijze = werkwijze
        self.gestuurd = []

    def call(self, pad, payload=None, method=None):
        self.gestuurd.append((pad, payload))
        if "werkwijze" in pad:
            return {"werkwijze": self.werkwijze}
        return {"nieuw": 0}

    def statussen(self):
        return [p for pad, p in self.gestuurd if pad == "/agent-status"]

    def kennis(self):
        return [p for pad, p in self.gestuurd if pad.endswith("/kennis")]


def ronde_met(nabootsing, doe=None, taak="proef"):
    echt, bord.call = bord.call, nabootsing.call
    try:
        ag = bord.Agent("proefagent")
        with ag.ronde(taak) as r:
            if doe:
                doe(r)
        return r
    finally:
        bord.call = echt


def test_n4_kennis_wordt_gemeld_met_vingerafdruk():
    """Elke ronde meldt welk regelboek hij las, met een vingerafdruk per bron."""
    nb = BordNabootsing()
    ronde_met(nb, lambda r: r.bron("taken.json", '{"a": 1}'))
    gemeld = nb.kennis()
    assert len(gemeld) == 1, "geen kennis gemeld: norm N4 faalt voor elke agent die de ronde gebruikt"
    tekst = gemeld[0]["kennis"]
    assert "werkwijze op het bord" in tekst, "de werkwijze van het bord hoort in de kennis"
    assert "taken.json" in tekst, "een bron die de agent las hoort in de kennis"
    # een vingerafdruk van acht tekens per regel, anders weet je niet welke versie hij las
    for regel in tekst.splitlines():
        assert len(regel.rsplit(", ", 1)[-1]) == 8, f"geen vingerafdruk in: {regel}"


def test_n4_werkwijze_wordt_opgehaald():
    """De werkwijze van het bord is de bron; de ronde haalt hem op en geeft hem door."""
    nb = BordNabootsing(werkwijze="# Mijn regels\n\nRegel een.")
    r = ronde_met(nb)
    assert "Regel een." in r.werkwijze, "de ronde geeft de werkwijze van het bord niet door aan de agent"


def test_n10_nood_zonder_teller():
    """Een aantal vooraan in een noodtekst maakt van elke ronde een nieuwe nood."""
    nb = BordNabootsing()
    ronde_met(nb, lambda r: r.nood("11 afspraken zonder code"))
    noden = nb.statussen()[-1]["nood"]
    assert noden[0]["tekst"] == "Afspraken zonder code", f"teller niet weggehaald: {noden[0]['tekst']}"


def test_n10_dezelfde_nood_maar_een_keer():
    nb = BordNabootsing()
    ronde_met(nb, lambda r: [r.nood("Geen adres"), r.nood("Geen adres")])
    assert len(nb.statussen()[-1]["nood"]) == 1, "dezelfde nood hoort maar een keer op het bord te staan"


def test_n11_ronde_die_breekt_meldt_fout():
    """Nooit blijven hangen op actief: daar zag niemand 18 uur lang iets van."""
    nb = BordNabootsing()

    def stuk(r):
        raise ValueError("iets liep mis")

    echt, bord.call = bord.call, nb.call
    try:
        ag = bord.Agent("proefagent")
        gebroken = False
        try:
            with ag.ronde("stukke ronde"):
                stuk(None)
        except ValueError:
            gebroken = True
        assert gebroken, "de ronde hoort de fout door te laten, niet op te slokken"
    finally:
        bord.call = echt
    laatste = nb.statussen()[-1]
    assert laatste["status"] == "fout", f"status na een gebroken ronde is {laatste['status']}, hoort fout te zijn"
    assert "ValueError" in laatste["detail"], "de fout hoort in het detail te staan"


def test_n11_geslaagde_ronde_blijft_niet_op_actief():
    nb = BordNabootsing()
    ronde_met(nb)
    assert nb.statussen()[0]["status"] == "actief", "een ronde begint op actief"
    assert nb.statussen()[-1]["status"] in ("klaar", "waakt"), "een ronde eindigt niet op actief"


def test_sjabloon_gebruikt_de_ronde():
    """Elke nieuwe agent erft het minimum. Wie het sjabloon uitholt, breekt dit."""
    sjabloon = open(os.path.join(RUNNER, "_sjabloon_agent.py"), encoding="utf-8").read()
    assert "import bord" in sjabloon, "het sjabloon hoort de gedeelde bord-module te gebruiken"
    assert "ag.ronde(" in sjabloon, "het sjabloon hoort de ronde te gebruiken, anders haalt een nieuwe agent N4 en N11 niet"


def test_de_norm_staat_beschreven():
    """Code zonder het document is een regel die niemand kan nalezen."""
    norm = open(os.path.join(RUNNER, "AGENTNORM.md"), encoding="utf-8").read()
    for code in ("N4", "N10", "N11"):
        assert code in norm, f"{code} wordt hier getoetst maar staat niet in AGENTNORM.md"

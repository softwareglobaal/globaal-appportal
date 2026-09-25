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
        if pad == "/api/agents":
            return [{"naam": "proefagent", "label": "De Proefagent", "type": "regie", "rol": "ik zelf", "actief": 1},
                    {"naam": "bode", "label": "De Bode", "type": "regie", "rol": "brengt wat telt naar Mehdi", "actief": 1},
                    {"naam": "oud", "label": "Oude agent", "type": "regie", "rol": "uit dienst", "actief": 0}]
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
    for code in ("N4", "N10", "N11", "N13", "N14"):
        assert code in norm, f"{code} wordt hier getoetst maar staat niet in AGENTNORM.md"


def test_n13_gedeelde_lessen_bestaan_en_zijn_geldig():
    """Wat een agent leert, hoort elke agent te weten. Het lessenboek moet er zijn
    en elke les moet zeggen waar ze vandaan komt, anders is het een mening."""
    import json
    pad = os.path.join(RUNNER, "werkwijze", "lessen.json")
    assert os.path.exists(pad), "werkwijze/lessen.json ontbreekt: dan leest geen enkele agent nog lessen"
    d = json.load(open(pad, encoding="utf-8"))
    lessen = d.get("lessen") or []
    assert lessen, "het lessenboek is leeg"
    ids = [l["id"] for l in lessen]
    assert len(ids) == len(set(ids)), "twee lessen met hetzelfde nummer"
    for l in lessen:
        for veld in ("id", "les", "bron", "geldt_voor"):
            assert l.get(veld), f"les {l.get('id')} mist het veld {veld}"
    assert any(l["id"] == "L15" for l in lessen), "L15 (zeg eerst wat blijft) is de les van 24-09-2026 en hoort erin"


def test_n13_ronde_leest_de_gedeelde_lessen():
    """De ronde leest het lessenboek mee als bron, zodat het in de kennis staat en
    de Normwacht kan zien dat een agent het echt las."""
    nb = BordNabootsing()
    r = ronde_met(nb)
    assert r.lessen, "de ronde geeft de lessen niet door aan de agent (r.lessen is leeg)"
    gemeld = nb.kennis()
    assert gemeld and "gedeelde lessen" in gemeld[0]["kennis"], "de gedeelde lessen staan niet in de gemelde kennis: N13 kan dan nooit slagen"


def test_n14_ronde_kent_de_collegas():
    """Mehdi, 25-09-2026: "zorg ervoor dat alle agents van elkaar op de hoogte zijn". De ronde
    haalt de actieve agents levend van het bord, zonder zichzelf en zonder wie uit dienst is,
    en meldt die lijst als bron, zodat de Normwacht kan zien dat hij ze kende."""
    nb = BordNabootsing()
    r = ronde_met(nb)
    namen = [c["naam"] for c in r.collegas]
    assert namen == ["bode"], f"de ronde hoort alleen actieve collega's te geven, zonder zichzelf: {namen}"
    gemeld = nb.kennis()
    assert gemeld and "collega's op het bord" in gemeld[0]["kennis"], "de collega's staan niet in de gemelde kennis: N14 kan dan nooit slagen"
    assert "De Bode (bode, regie)" in bord.collega_tekst(r.collegas), "de collega-tekst noemt label, naam en afdeling"


def test_n14_bord_dat_niet_antwoordt_breekt_de_ronde_niet():
    """Antwoordt het bord niet, dan loopt de ronde door; de Normwacht meldt het gat."""
    nb = BordNabootsing()
    echt_call = nb.call

    def zonder_agents(pad, payload=None, method=None):
        if pad == "/api/agents":
            raise OSError("bord weg")
        return echt_call(pad, payload, method)

    nb.call = zonder_agents
    r = ronde_met(nb)
    assert r.collegas == [], "zonder bord hoort de lijst leeg te zijn"
    assert nb.statussen()[-1]["status"] in ("klaar", "waakt"), "een ontbrekende collega-lijst mag de ronde niet breken"

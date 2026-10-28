"""Grendels voor het driehoeksoverleg van 28-10-2026: de werfverslagketen als één geheel
(docs/overleg-werfketen-eenheid/verslag.md)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "koppelingen"))
import werfverslag_voorbereider as V  # noqa: E402
import werfapp  # noqa: E402
import contracten_mcp  # noqa: E402


def controles(**afwijkend):
    """Alle nodige posten ok, met afwijkende posten als code=(stand, extra velden)."""
    rij = []
    for code in V.NODIGE_POSTEN + ("W7",):
        stand, extra = afwijkend.get(code, ("ontbreekt" if code == "W7" else "ok", {}))
        rij.append({"code": code, "naam": code, "stand": stand, "toelichting": "", **extra})
    return rij


def test_werfstart_bekend_maakt_klaar_voor_verslag():
    # Een bekende werfstart schrijft geen WERFSTART-post; vroeger blokkeerde juist dat elk bezoek.
    assert V.stand_van(controles()) == "klaar voor verslag"
    assert V.ontbrekende_posten(controles()) == []
    ontbreekt = controles() + [{"code": "WERFSTART", "naam": "werfstart", "stand": "onbekend"}]
    assert V.stand_van(ontbreekt) == "te verzamelen"


def test_w12_alleen_voor_het_contractsysteem_blokkeert_niet():
    assert V.stand_van(controles(W12=("onbekend", {"voor_contractsysteem": True}))) == "klaar voor verslag"
    assert V.stand_van(controles(W12=("onbekend", {}))) == "te verzamelen"          # onbereikbaar of niet toetsbaar
    assert V.stand_van(controles(W12=("ontbreekt", {"voor_contractsysteem": True}))) == "te verzamelen"
    assert V.stand_van(controles(W12=("ok", {}))) == "klaar voor verslag"


def test_w2_voor_de_meetreeks_telt_alleen_met_agenda():
    w2 = ("onbekend", {"voor_meetreeks": True})
    assert V.stand_van(controles(W2=w2)) == "klaar voor verslag"
    assert V.stand_van(controles(W2=w2, W1=("let_op", {}))) == "te verzamelen"
    assert V.stand_van(controles(W2=w2, W1=("ontbreekt", {}))) == "te verzamelen"
    assert V.stand_van(controles(W2=("onbekend", {}))) == "te verzamelen"          # na de meetreeks: GPS verplicht
    assert V.stand_van(controles(W2=("ontbreekt", {"voor_meetreeks": True}))) == "te verzamelen"


def test_meetreeksgrens_staat_op_één_plaats():
    # Geen eigen datum in de voorbereider: de grens komt uit het bronbeleid van de locatiecontext.
    assert not re.search(r"2026-10-0[23]", (ROOT / "werfverslag_voorbereider.py").read_text())
    assert not V.LC.bronbeleid.dag_toegestaan("2026-10-02")
    assert V.LC.bronbeleid.dag_toegestaan("2026-10-03")
    assert V.LC.bronbeleid.dag_toegestaan("2026-10-04")


def test_stand_en_nog_te_verzamelen_lopen_nooit_uiteen():
    for code in V.NODIGE_POSTEN:
        for stand in ("ok", "let_op", "onbekend", "ontbreekt"):
            for extra in ({}, {"voor_meetreeks": True}, {"voor_contractsysteem": True}):
                rij = controles(**{code: (stand, extra)})
                klaar = V.stand_van(rij) == "klaar voor verslag"
                assert klaar == (V.ontbrekende_posten(rij) == []), (code, stand, extra)


def test_w7_aanwezig_volgt_dezelfde_regel():
    w7 = ("ok", {})
    assert V.stand_van(controles(W7=w7, W12=("onbekend", {"voor_contractsysteem": True}))) == "verslag aanwezig"
    assert V.stand_van(controles(W7=w7, W4=("let_op", {}))) == "verslag aanwezig, bronnen onvolledig"


def test_contract_van_voor_het_systeem_blijft_zo_na_een_geopend_werfdossier(monkeypatch):
    def geen_dossier(*a, **k):
        raise contracten_mcp.ToolFout("Geen dossier gevonden voor 2145")
    monkeypatch.setattr(V.contracten_mcp, "call", geen_dossier)
    monkeypatch.setattr(V.werfapp, "call", lambda pad, *a, **k: {"nummer": "2145", "betrokkenen": []})
    assert V.contractbewijs("2145") == ("onbekend", V.VOOR_CONTRACTSYSTEEM)

    def weg(*a, **k):
        raise werfapp.WerfappFout(0, "niet bereikbaar")
    monkeypatch.setattr(V.werfapp, "call", weg)
    assert V.contractbewijs("2145") == ("onbekend", V.VOOR_CONTRACTSYSTEEM)

    def kapot(*a, **k):
        raise RuntimeError("time-out")
    monkeypatch.setattr(V.contracten_mcp, "call", kapot)
    assert V.contractbewijs("2145") != ("onbekend", V.VOOR_CONTRACTSYSTEEM)       # onbereikbaar blijft blokkeren


def test_werfdossier_openen_alleen_uit_ha_en_nooit_fataal(monkeypatch):
    gezien = []

    def antwoord(status):
        def call(pad, payload=None, method=None):
            gezien.append((pad, payload))
            if status is not None:
                raise werfapp.WerfappFout(status, "x")
            return {"ok": True}
        return call
    monkeypatch.setattr(V.ag, "log", lambda *a, **k: None)
    monkeypatch.setattr(V.werfapp, "call", antwoord(None))
    assert V.werfdossier_openen(2145) == "geopend"
    assert gezien[-1] == ("/projecten", {"nummer": "2145", "alleen_ha": True})
    monkeypatch.setattr(V.werfapp, "call", antwoord(409))
    assert V.werfdossier_openen(2145) == "bestaat"
    for status in (404, 503, 0):
        monkeypatch.setattr(V.werfapp, "call", antwoord(status))
        assert V.werfdossier_openen(2145) == "fout"


def test_voorbereider_start_nooit_een_betaalde_stap():
    bron = (ROOT / "werfverslag_voorbereider.py").read_text()
    for verboden in ("import anthropic", "werfverslag_proef", "werfopdrachten", "messages.create"):
        assert verboden not in bron, verboden


def test_drie_werkwijzen_spreken_dezelfde_taal():
    teksten = {n: (ROOT / "werkwijze" / f"werfverslag-{n}.md").read_text()
               for n in ("voorbereider", "schrijver", "dashboard")}
    for naam, tekst in teksten.items():
        assert "H-A vaste afspraken v1.10" in tekst, naam
        assert "v1.9`" not in tekst, naam
        assert "auto bij het project telt als aanwezigheid (E1b)" in tekst, naam
        assert "auto alleen" not in tekst.lower(), naam
    assert "Later: elke afspraak" not in teksten["voorbereider"]

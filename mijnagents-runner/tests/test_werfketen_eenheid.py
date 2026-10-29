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


def test_werfdossier_in_de_prullenbak_blokkeert():
    rij = controles() + [{"code": "WERFDOSSIER", "naam": "werfdossier in de werfapp", "stand": "ontbreekt"}]
    assert V.stand_van(rij) == "te verzamelen"
    assert any(x.startswith("WERFDOSSIER ") for x in V.ontbrekende_posten(rij))


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
    assert V.contractbewijs("5513") == ("onbekend", V.VOOR_CONTRACTSYSTEEM)              # 5-reeks: 2025
    # een project van 2026 of later zonder contractdossier is geen bewijs van ouderdom en blokkeert
    for jong in ("2601", "5601", "2701"):
        stand, toel = V.contractbewijs(jong)
        assert stand == "onbekend" and toel != V.VOOR_CONTRACTSYSTEEM

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

    def prullenbak(pad, payload=None, method=None):
        raise werfapp.WerfappFout(409, "bestaat al in de prullenbak; herstel het in het dashboard (Herstel en audit)")
    monkeypatch.setattr(V.werfapp, "call", prullenbak)
    assert V.werfdossier_openen(2145) == "prullenbak"
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
        assert "auto bij het project = let_op" not in tekst, naam
    assert "Later: elke afspraak" not in teksten["voorbereider"]


OUDE_LIJST = """# Foto's 2145 2026-06-06

3 foto's van de iPhone binnen 300 m van Vertommensberg 9, 3010 Kessel-Lo; geëxporteerd door de iCloud-wacht op 2026-09-14.

| tijd | bestand | lat, lon | afstand |
|---|---|---|---|
| 10:42 | 1042 756DF67C.HEIC | 50.86792, 4.7496 | 51 m |
| 11:03 | 1103 C0C4A1FD.HEIC | 50.8677, 4.74957 | 71 m |
"""


def _fotobezoek(monkeypatch, inhoud, datum="2026-06-06"):
    m = "/w/2145/_00. Communication/2026-06-06 bezoek"
    monkeypatch.setattr(V.bronnen, "download", lambda pad, maximum=0: inhoud.encode())
    return {"map": m, "datum": datum, "foto_manifest": m + "/fotos/00 fotos.md", "foto_manifest_versies": [],
            "foto_bestanden": [m + "/fotos/1042 756DF67C.jpg", m + "/fotos/1103 C0C4A1FD.jpg"]}


VENSTER = {"start": "2026-06-06T10:30:00+02:00", "einde": "2026-06-06T12:30:00+02:00"}


def test_oude_fotolijst_van_de_icloud_wacht_is_tijdsbewijs(monkeypatch):
    # Overleg 29-10-2026: de tabel van vóór 21-10 draagt de Brusselse opnametijd per foto.
    assert V.fotobewijs(_fotobezoek(monkeypatch, OUDE_LIJST), VENSTER, "2145") == "ok"


def test_oude_fotolijst_blijft_streng(monkeypatch):
    buiten = OUDE_LIJST.replace("| 11:03 |", "| 12:33 |")
    assert V.fotobewijs(_fotobezoek(monkeypatch, buiten), VENSTER, "2145") == "let_op"            # foto na het venster
    ver = OUDE_LIJST.replace("| 71 m |", "| 450 m |")
    assert V.fotobewijs(_fotobezoek(monkeypatch, ver), VENSTER, "2145") == "let_op"               # buiten 300 m: geen tijd
    andere_dag = OUDE_LIJST.replace("2145 2026-06-06", "2145 2026-06-07")
    assert V.fotobewijs(_fotobezoek(monkeypatch, andere_dag), VENSTER, "2145") == "let_op"        # lijst van een andere dag
    assert V.fotobewijs(_fotobezoek(monkeypatch, OUDE_LIJST), None, "2145") == "let_op"           # zonder venster nooit ok
    zonder_tabel = OUDE_LIJST.split("| tijd |")[0]
    assert V.fotobewijs(_fotobezoek(monkeypatch, zonder_tabel), VENSTER, "2145") == "let_op"


def test_oude_fotolijst_gebruikt_brusselse_tijd():
    t = V.oude_fototabel(OUDE_LIJST, "2026-06-06", "2145")["1042 756DF67C.HEIC"]
    assert t.isoformat() == "2026-06-06T10:42:00+02:00"


def test_oude_fotolijst_op_de_vensterrand(monkeypatch):
    # Minuten zonder seconden: de start telt mee, het einde niet (in_venster: start <= t < einde).
    op_start = OUDE_LIJST.replace("| 10:42 |", "| 10:30 |")
    assert V.fotobewijs(_fotobezoek(monkeypatch, op_start), VENSTER, "2145") == "ok"
    op_einde = OUDE_LIJST.replace("| 11:03 |", "| 12:30 |")
    assert V.fotobewijs(_fotobezoek(monkeypatch, op_einde), VENSTER, "2145") == "let_op"
    assert V.oude_fototabel(OUDE_LIJST, "2026-06-07", "2145") == {}


def test_oude_fotolijst_van_een_andere_werf_of_zonder_dossier(monkeypatch):
    # Codex 29-10: een tabel met een ander dossier in de titel is geen bewijs voor dit bezoek.
    andere_werf = OUDE_LIJST.replace("# Foto's 2145", "# Foto's 9999")
    assert V.fotobewijs(_fotobezoek(monkeypatch, andere_werf), VENSTER, "2145") == "let_op"
    assert V.fotobewijs(_fotobezoek(monkeypatch, OUDE_LIJST), VENSTER) == "let_op"          # dossier onbekend


def test_oude_fotolijst_ongeldig_of_dubbelzinnig_uur():
    wissel = OUDE_LIJST.replace("2026-06-06", "2026-10-25")
    assert V.oude_fototabel(wissel.replace("| 10:42 |", "| 02:30 |"), "2026-10-25", "2145") == {}   # dubbelzinnig
    assert V.oude_fototabel(wissel.replace("| 11:03 |", "| 25:99 |"), "2026-10-25", "2145") == {}   # ongeldig: hele lijst
    assert len(V.oude_fototabel(wissel, "2026-10-25", "2145")) == 2


def test_oude_fotolijst_met_twee_titels_telt_niet(monkeypatch):
    # Codex 29-10 ronde 2: regels onder een tweede kop (andere werf of dag) mogen niet meetellen.
    for tweede in ("# Foto's 9999 2026-06-06", "# Foto's 2145 2026-06-07"):
        dubbel = OUDE_LIJST + "\n" + tweede + "\n\n| tijd | bestand | lat, lon | afstand |\n|---|---|---|---|\n" \
            "| 11:00 | 1103 C0C4A1FD.HEIC | 50.8677, 4.74957 | 10 m |\n"
        assert V.fotobewijs(_fotobezoek(monkeypatch, dubbel), VENSTER, "2145") == "let_op"
        assert V.fotobewijs(_fotobezoek(monkeypatch, tweede + "\n" + OUDE_LIJST), VENSTER, "2145") == "let_op"


def test_oude_fotolijst_strikt_formaat(monkeypatch):
    # Codex 29-10 ronde 3: een ingesprongen tweede titel of een tegenstrijdige dubbele rij maakt de lijst ongeldig.
    for afwijkend in (OUDE_LIJST + "   # Foto's 9999 2026-06-06\n| 11:00 | 1103 C0C4A1FD.HEIC | 50.8, 4.7 | 10 m |\n",
                      OUDE_LIJST + "| 11:03 | 1103 C0C4A1FD.HEIC | 50.8677, 4.74957 | 450 m |\n",
                      OUDE_LIJST + "| 11:03 | 1103 C0C4A1FD.HEIC | 50.8677, 4.74957 | 71 m |\n",
                      OUDE_LIJST + "  | 11:00 | 1042 756DF67C.HEIC | 50.8, 4.7 | 10 m |\n",
                      OUDE_LIJST + "| rommel |\n",
                      "Inleiding\n" + OUDE_LIJST):
        assert V.oude_fototabel(afwijkend, "2026-06-06", "2145") == {}
        assert V.fotobewijs(_fotobezoek(monkeypatch, afwijkend), VENSTER, "2145") == "let_op"


def test_oude_fotolijst_gemengd_of_met_losse_regel(monkeypatch):
    # Codex 29-10 ronde 4: nieuwe tijdregels in een oude lijst, of een losse regel ertussen, maken de lijst ongeldig.
    nieuw_erbij = OUDE_LIJST.replace("# Foto's 2145", "# Foto's 9999") + "- 2026-06-06T08:42:00+00:00 | 1042 756DF67C.HEIC\n"
    assert V.fotobewijs(_fotobezoek(monkeypatch, nieuw_erbij), VENSTER, "2145") == "let_op"
    for afwijkend in (OUDE_LIJST + "Nog een regel\n", OUDE_LIJST.replace("|---|---|---|---|\n", "|---|---|---|---|\nTussenregel\n")):
        assert V.oude_fototabel(afwijkend, "2026-06-06", "2145") == {}
        assert V.fotobewijs(_fotobezoek(monkeypatch, afwijkend), VENSTER, "2145") == "let_op"


def test_oude_titel_met_geldige_nieuwe_regels_telt_niet(monkeypatch):
    gemengd = OUDE_LIJST.replace("# Foto's 2145", "# Foto's 9999") + (
        "- 2026-06-06T08:42:00+00:00 | 1042 756DF67C.HEIC\n- 2026-06-06T09:03:00+00:00 | 1103 C0C4A1FD.HEIC\n")
    assert V.fotobewijs(_fotobezoek(monkeypatch, gemengd), VENSTER, "2145") == "let_op"
    alleen_nieuw = "# Fotoaanvoer volledig\n\n" + gemengd.split("| tijd |")[0].split("\n", 1)[1] + (
        "- 2026-06-06T08:42:00+00:00 | 1042 756DF67C.HEIC\n- 2026-06-06T09:03:00+00:00 | 1103 C0C4A1FD.HEIC\n")
    assert V.fotobewijs(_fotobezoek(monkeypatch, alleen_nieuw), VENSTER, "2145") == "ok"   # nieuw formaat ongewijzigd


def test_gemengde_lijst_met_bom_of_andere_titel_telt_niet(monkeypatch):
    # Codex 29-10 ronde 5: een BOM of afwijkende oude titel mag nieuwe tijdregels niet laten meetellen.
    nieuw = "- 2026-06-06T08:42:00+00:00 | 1042 756DF67C.HEIC\n- 2026-06-06T09:03:00+00:00 | 1103 C0C4A1FD.HEIC\n"
    slecht = OUDE_LIJST.replace("# Foto's 2145", "# Foto's 9999").replace("| 71 m |", "| 450 m |")
    for gemengd in ("﻿" + slecht + nieuw, slecht.replace("# Foto's", "#  FOTO'S") + nieuw,
                    slecht.split("\n", 1)[1] + nieuw):
        assert V.fotobewijs(_fotobezoek(monkeypatch, gemengd), VENSTER, "2145") == "let_op"
    assert V.fotobewijs(_fotobezoek(monkeypatch, "﻿" + OUDE_LIJST), VENSTER, "2145") == "ok"   # BOM alleen: oud geldig


def test_oude_fotolijst_dezelfde_foto_met_andere_extensie(monkeypatch):
    # Codex 29-10 ronde 6: .HEIC en .heic (of .jpg) van dezelfde foto zijn één foto; een tweede rij maakt de lijst ongeldig.
    for rij in ("| 12:33 | 1103 C0C4A1FD.heic | 50.8677, 4.74957 | 71 m |\n",
                "| 11:03 | 1103 c0c4a1fd.HEIC | 50.8677, 4.74957 | 450 m |\n",
                "| 11:03 | 1103 C0C4A1FD.jpg | 50.8677, 4.74957 | 71 m |\n"):
        assert V.oude_fototabel(OUDE_LIJST + rij, "2026-06-06", "2145") == {}
        assert V.fotobewijs(_fotobezoek(monkeypatch, OUDE_LIJST + rij), VENSTER, "2145") == "let_op"


def test_oude_fotolijst_toetst_ook_heic_zonder_jpg(monkeypatch):
    # Codex 29-10 ronde 7: een aanwezige HEIC buiten venster of straal maakt W4 niet ok.
    for rij in ("| 12:45 | 1245 AAAA0001.HEIC | 50.8677, 4.74957 | 71 m |\n",
                "| 11:10 | 1110 AAAA0002.HEIC | 50.8677, 4.74957 | 450 m |\n"):
        b = _fotobezoek(monkeypatch, OUDE_LIJST + rij)
        b["foto_bestanden"].append(b["map"] + "/fotos/" + rij.split(" | ")[1])
        assert V.fotobewijs(b, VENSTER, "2145") == "let_op"
    b = _fotobezoek(monkeypatch, OUDE_LIJST)
    b["foto_bestanden"] += [b["map"] + "/fotos/1042 756DF67C.HEIC", b["map"] + "/fotos/1103 C0C4A1FD.HEIC"]
    assert V.fotobewijs(b, VENSTER, "2145") == "ok"                                     # HEIC met eigen geldige rij

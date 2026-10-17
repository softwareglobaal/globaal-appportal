"""H1-2, driehoeksoverleg C2, 17-10-2026: dossierbewijs op firma plus nummer.

Alle titels en deals zijn verzonnen. Draaien: python3 mijnagents-runner/tests/test_dossierbewijs_zeker.py
Voor de regressieproef kunnen kopieën uit git show HEAD:... via H1_DOSSIER_OUD worden geladen.
"""
import os
import sys
import time
from pathlib import Path

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
sys.path.insert(0, str(HIER / "plaud"))

# De wachters lezen bij import optionele .env-bestanden. Deze proef gebruikt geen echte gegevens.
_home = os.environ.get("HOME")
os.environ["HOME"] = os.environ.get("TMPDIR", "/tmp")
import nummerlezer as N  # noqa: E402
import benaming as B  # noqa: E402
import archivaris as A  # noqa: E402
import fathom_wacht as F  # noqa: E402
import dossier as D  # noqa: E402

if os.environ.get("H1_DOSSIER_OUD"):
    oud = Path(os.environ["H1_DOSSIER_OUD"])
    for module, pad in ((N, "koppelingen/nummerlezer.py"), (B, "benaming.py"),
                        (A, "archivaris.py"), (F, "fathom_wacht.py"), (D, "plaud/dossier.py")):
        bron = (oud / pad).read_text(encoding="utf-8")
        exec(compile(bron, str(oud / pad), "exec"), module.__dict__)
if _home is None:
    del os.environ["HOME"]
else:
    os.environ["HOME"] = _home

N._standaard["codes"], N._standaard["ts"] = N._bouw_codes([]), time.time()
HERK = {"afdeling": "h-architects", "zekerheid": "hoog", "prive": False}
VALSE_TITELS = (("Overleg 3012 Wilsele", "3012"),
                ("Zoom Klant 3000 Leuven ontwerp", "3000"),
                ("Stabiliteit 4437 overleg", "4437"))


def deal(nummer):
    return {"id": 1, "nummer": nummer, "titel": f"{nummer} Testklant", "mails": set(), "delen": set()}


def test_onzekere_titels_maken_nergens_een_h_a_dossier():
    for titel, nummer in VALSE_TITELS:
        assert N.ha_nummer(titel, "vergadertitel", 2026) == "", titel
        assert N.ha_nummer(titel, "vergadertitel", 2026, bekend={nummer}) == "", titel
        b = B.benoem({"title": titel})
        assert (b["firma"], b["dossier"]) != ("HARC", nummer), (titel, b)
        b = B.benoem({"title": titel}, bekend={nummer})
        assert (b["firma"], b["dossier"]) != ("HARC", nummer), (titel, b)
        assert A.ha_projectnummer({"titel": titel}, "") == "", titel
        assert A.ha_projectnummer({"titel": titel}, "", bekend={nummer}) == "", titel
        bewijzen = D.uit_tekst("titel", titel)
        for bekend in (set(), {nummer}, {("TKNB", nummer)}):
            besluit = D.beslis(bewijzen, HERK, bekend=bekend)
            assert besluit["dossier"] is None and not besluit["kopie_toegestaan"], (titel, bekend, besluit)
        assert F.koppel_deal({"title": titel}, [deal("2611")])[0] is None, titel


def test_bestaande_h_a_deal_bevestigt_maar_andere_firma_niet():
    titel = "Testklant 2611"
    kandidaat = N.lees(titel, "vergadertitel", 2026)
    assert len(kandidaat) == 1 and (kandidaat[0].firma, kandidaat[0].nummer, kandidaat[0].zeker) == ("HARC", "2611", False)
    assert N.ha_nummer(titel, "vergadertitel", 2026) == ""
    assert N.ha_nummer(titel, "vergadertitel", 2026, bekend={"2611"}) == ""
    assert N.ha_nummer(titel, "vergadertitel", 2026, bekend={("TKNB", "2611")}) == ""
    g = {"title": "Impromptu Zoom Meeting", "herkenning": {"afdeling": "h-architects", "project": titel}}
    assert B.benoem(g)["dossier"] == ""
    bekend = {("HARC", "2611")}
    assert N.ha_nummer(titel, "vergadertitel", 2026, bekend=bekend) == "2611"
    assert B.benoem({"title": titel}, bekend=bekend)["dossier"] == "2611"
    assert B.benoem(g, bekend=bekend)["dossier"] == "2611"
    ander = {"title": "[TK-KB] ST 4437 - Testklant", "herkenning": {"afdeling": "tkn", "project": "HA2611"}}
    assert B.benoem(ander)["dossier"] != "2611"
    assert A.ha_projectnummer({"titel": ander["title"]}, "HA2611") == ""
    assert A.ha_projectnummer({"titel": titel}, "", bekend=bekend) == "2611"
    assert F.koppel_deal({"title": titel}, [deal("2611")])[0]["nummer"] == "2611"
    assert D.beslis(D.uit_tekst("titel", titel), HERK, bekend=bekend)["dossier"] == "HARC:2611"
    assert D.beslis(D.uit_tekst("titel", titel), HERK, bekend=set())["dossier"] is None


def test_zekere_bron_en_meervoudige_kandidaat():
    for titel in ("[HA-KB] WB 2611 - Testklant", "HA2611"):
        assert N.ha_nummer(titel, "vergadertitel", 2026) == "2611", titel
        assert B.benoem({"title": titel})["dossier"] == "2611", titel
        assert A.ha_projectnummer({"titel": titel}, "") == "2611", titel
        assert D.beslis(D.uit_tekst("titel", titel), HERK, bekend=set())["dossier"] == "HARC:2611", titel
    assert N.ha_nummer("HA2611 en HA2612", "vergadertitel", 2026, bekend={("HARC", "2611")}) == ""


def test_onbevestigd_gespreksnummer_krijgt_geen_andere_rol():
    titel = "Meeting 2145 Online Sophie en Nico"
    kaal = B.benoem({"title": titel})
    assert kaal["dossier"] == "" and kaal["met_wie"] == "Sophie en Nico", kaal
    g = {"title": titel, "herkenning": HERK}
    zonder = B.benoem(g)
    assert zonder["dossier"] == "", zonder
    assert zonder["met_wie"] == "Sophie en Nico", zonder
    assert "dossier" in zonder["ontbreekt"] and "projectnummer niet bevestigd" in zonder["ontbreekt"], zonder
    met = B.benoem(g, bekend={("HARC", "2145")})
    assert (met["firma"], met["dossier"], met["met_wie"]) == ("HARC", "2145", "Sophie en Nico"), met
    project = B.benoem({"title": "Impromptu Zoom Meeting", "herkenning": {
        **HERK, "project": "Testklant 2611", "personen": ["Sophie"]}})
    assert project["dossier"] == "" and project["onderwerp"] == "Testklant", project


def test_dubbel_gelijk_nummer_telt_eenmaal():
    # H1-2b, driehoeksoverleg C3, 17-10-2026: herstel het gedrag van vóór H1 voor dubbele gelijke nummers.
    assert N.ha_nummer("HA2611 en HA2611", "vergadertitel", 2026) == "2611"
    assert N.ha_nummer("HA2611 en HA2612", "vergadertitel", 2026) == ""


if __name__ == "__main__":
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("geslaagd", naam)
            except Exception as e:  # noqa: BLE001
                fouten += 1
                print("GEFAALD", naam, repr(e))
    print(f"{fouten} gefaald" if fouten else "alles geslaagd")
    sys.exit(1 if fouten else 0)

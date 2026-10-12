"""Grendels op de dossierbeslissing (nacontrole Plaud-agent v1.1, 12-10-2026, P1-2 en P1-4).

De nacontrole vond: titel "Renovatieplan vrijstaande woning 1933" en opening "Deze woning is gebouwd in
1933" gaven samen HARC:1933, zekerheid hoog en een zakelijke kopie, terwijl 1933 een bouwjaar is en geen
bekend dossier. De nummerlezer noemt zulke getallen onzeker; die zekerheid ging verloren, en titel en
openingszin telden als twee onafhankelijke bronnen.

Regels: een onzeker getal telt alleen bij een bekend dossier (firma plus nummer) of als een gecontroleerde
bron (agenda met firma en nummer, zoektaak, dossierveld, deelnemer) het bevestigt. Titel en openingszin
zijn samen één bron. Het model bewijst niets. Tegenstrijdige modelvelden (afdeling prive, prive false)
gaan naar Mehdi.

Draaien: python3 mijnagents-runner/tests/test_plaud_dossier.py   (Python 3.10 of nieuwer, zoals de VM)
"""
import os
import sys
import time

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
sys.path.insert(0, os.path.join(HIER, "plaud"))
import nummerlezer  # noqa: E402
nummerlezer._standaard["codes"], nummerlezer._standaard["ts"] = nummerlezer._bouw_codes([]), time.time()
import dossier as D  # noqa: E402

HERK = {"afdeling": "h-architects", "zekerheid": "hoog", "prive": False}
BEKEND = {("HARC", "2531"), ("HARC", "2612")}


def test_herhaald_bouwjaar_in_titel_en_opening_is_geen_dossier():
    b = D.uit_tekst("titel", "Renovatieplan vrijstaande woning 1933") + D.uit_tekst("openingszin", "Deze woning is gebouwd in 1933")
    assert b and all(x["zeker"] is False for x in b), b
    r = D.beslis(b, HERK, D.uit_tekst("model", "Renovatie woning 1933"), bekend=BEKEND)
    assert r["dossier"] is None and not r["kopie_toegestaan"] and r["voor"] == "mehdi", r


def test_postcode_is_geen_dossier():
    r = D.beslis(D.uit_tekst("titel", "Vergadering Kessel-Lo 3010"), HERK, bekend=BEKEND)
    assert r["dossier"] is None and not r["kopie_toegestaan"], r


def test_werkelijk_dossiernummer_met_bekend_dossier():
    b = D.uit_tekst("titel", "Werfbezoek 2531 Spleesters") + D.uit_tekst("openingszin", "Werfbezoek 2531 met de aannemer")
    r = D.beslis(b, HERK, D.uit_tekst("model", "2531 Spleesters"), bekend=BEKEND)
    assert r["dossier"] == "HARC:2531" and r["zekerheid"] == "middel" and r["kopie_toegestaan"], r
    assert r["voor"] == "h-architects"


def test_titel_en_opening_zijn_samen_een_bron():
    b = D.uit_tekst("titel", "Werfbezoek 2531") + D.uit_tekst("openingszin", "Werfbezoek 2531")
    r = D.beslis(b, HERK, bekend=BEKEND)
    assert r["zekerheid"] == "middel", "titel en openingszin zijn niet onafhankelijk"


def test_gecontroleerde_bron_bevestigt_een_onbekend_nummer():
    b = D.uit_tekst("titel", "Werfbezoek 2701") + [D.bewijs("agenda", "HARC", "2701", "HA 2701 werfbezoek", zeker=True)]
    r = D.beslis(b, HERK, bekend=BEKEND)
    assert r["dossier"] == "HARC:2701" and r["zekerheid"] == "hoog" and r["kopie_toegestaan"], r


def test_alleen_model_is_geen_bewijs():
    r = D.beslis([], HERK, D.uit_tekst("model", "2531 Spleesters"), bekend=BEKEND)
    assert r["dossier"] is None and not r["kopie_toegestaan"] and r["voor"] == "mehdi", r


def test_nummer_van_een_andere_firma_is_conflict():
    b = D.uit_tekst("titel", "Werfbezoek 2531") + [D.bewijs("agenda", "UNAB", "2531", "UB 2531 VC", zeker=True)]
    r = D.beslis(b, HERK, bekend=BEKEND)
    assert r["conflict"] and not r["kopie_toegestaan"] and r["voor"] == "mehdi", r


def test_conflict_tussen_harde_bronnen():
    b = [D.bewijs("agenda", "HARC", "2531", "", zeker=True), D.bewijs("kop", "HARC", "2612", "", zeker=True)]
    r = D.beslis(b, HERK, bekend=BEKEND)
    assert r["conflict"] and r["dossier"] is None and r["voor"] == "mehdi", r


def test_tegenstrijdige_privevelden_gaan_naar_mehdi():
    b = [D.bewijs("zoektaak", "HARC", "2531", "", zeker=True)]
    r = D.beslis(b, {"afdeling": "prive", "zekerheid": "hoog", "prive": False}, bekend=BEKEND)
    assert r["prive"] and not r["kopie_toegestaan"] and r["voor"] == "mehdi", r


def test_onbekende_afdeling_of_lage_zekerheid_mag_niet_publiceren():
    b = [D.bewijs("zoektaak", "HARC", "2531", "", zeker=True)]
    for herk in ({"afdeling": "onbekend", "zekerheid": "hoog"}, {"afdeling": "h-architects", "zekerheid": "laag"}):
        r = D.beslis(b, herk, bekend=BEKEND)
        assert not r["kopie_toegestaan"] and r["voor"] == "mehdi", (herk, r)


def test_bronuitval_is_onvolledig_bewijs():
    b = D.uit_tekst("titel", "Werfbezoek 2531")
    r = D.beslis(b, HERK, bekend=None)
    assert r["dossier"] is None and r["bewijs_onvolledig"] and not r["kopie_toegestaan"], r


if __name__ == "__main__":
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("   geslaagd  %s" % naam)
            except Exception as e:  # noqa: BLE001
                fouten += 1
                print("   GEFAALD   %s: %s" % (naam, e))
    print("%d gefaald" % fouten if fouten else "alles geslaagd")
    sys.exit(1 if fouten else 0)

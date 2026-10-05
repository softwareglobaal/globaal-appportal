"""Grendels op de gedeelde nummerlezer (codering WP1, 05-10-2026).

Een dossiernummer komt uit zijn bron, nooit uit een los getal; H-A volgt de bevestigde regel (D9, P11):
JJNN en (JJ+30)NN, zonder ondergrens; firmacodes komen uit het register en de aliasbron, een onbekende
code blijft onbekend. Verzonnen titels en een verzonnen register; geen netwerk, geen databank.

Draaien, zonder pytest:   python3 mijnagents-runner/tests/test_nummerlezer.py
"""
import os
import re
import sys

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import nummerlezer as N  # noqa: E402

# Zoals organisatie.firmas() het teruggeeft (kern.firma, migraties 175 en 183). Verzonnen namen niet nodig.
REGISTER = [
    {"code": "HARC", "code_agenda": "HA", "code_contact": "HA"},
    {"code": "UNAB", "code_agenda": "UB", "code_contact": "UN"},
    {"code": "TKNB", "code_agenda": "TK", "code_contact": "TK"},
    {"code": "ENEF", "code_agenda": "EE", "code_contact": "EE"},
    {"code": "HARM", "code_agenda": "HB", "code_contact": "HB"},
    {"code": "CONT", "code_agenda": "CX", "code_contact": "CX"},
    {"code": "HINV", "code_agenda": "HI", "code_contact": None},
]
OUD_PATROON = re.compile(r"^\s*((?:26|56)\d\d)\b")      # wat vijf routes tot 05-10-2026 gebruikten


def lees(tekst, bron, jaar_nu=2026, **kw):
    return [(k.firma, k.nummer, k.jaar, k.reeks) for k in N.lees(tekst, bron, jaar_nu, register=REGISTER, **kw)]


def test_h_a_nummers_historisch_en_toekomstig():
    for jaar_nu in (2026, 2027):
        assert lees("2503 Testklant", "pipedrive_titel", jaar_nu) == [("HARC", "2503", 2025, "architectuur")]
        assert lees("2603 Testklant", "pipedrive_titel", jaar_nu) == [("HARC", "2603", 2026, "architectuur")]
        assert lees("5603 Testklant", "pipedrive_titel", jaar_nu) == [("HARC", "5603", 2026, "regularisatie")]
        assert lees("2703 Testklant", "pipedrive_titel", jaar_nu) == [("HARC", "2703", 2027, "architectuur")]
        assert lees("5703 Testklant", "pipedrive_titel", jaar_nu) == [("HARC", "5703", 2027, "regularisatie")]
    assert lees("2803 Testklant", "pipedrive_titel", 2026) == []          # meer dan een jaar vooruit


def test_het_oude_patroon_miste_2503_2703_en_5703():
    gevonden = [n for n in ("2503", "2603", "5603", "2703", "5703") if OUD_PATROON.match(n + " x")]
    assert gevonden == ["2603", "5603"]


def test_verschoven_kalender_tot_2030_volgt_de_regel_niet_het_eerste_cijfer():
    assert N.ha_lezingen("6003", 2030) == ((2030, "regularisatie"),)     # JJ+30, begint met 6
    assert N.ha_lezingen("6003", 2026) == ()                              # in 2026 nog toekomst
    assert N.ha_lezingen("3003", 2030) == ((2030, "architectuur"), (2000, "regularisatie"))
    k = N.lees("3003 Testklant", "pipedrive_titel", 2030, register=REGISTER)[0]
    assert k.jaar is None and "jaar onbepaald" in k.reden                 # de context moet beslissen
    assert N.ha_voorvoegsel("architectuur", 2030) == "30" and N.ha_voorvoegsel("regularisatie", 2030) == "60"
    assert N.ha_voorvoegsel("regularisatie", 2027) == "57" and N.ha_voorvoegsel("addendum", 2027) == "27"


def test_geen_onbevestigde_ondergrens():
    assert lees("1503 Testklant", "pipedrive_titel", 2026) == [("HARC", "1503", 2015, "architectuur")]
    assert lees("2040 Testklant - Lage Kaart", "pipedrive_titel", 2026) == [("HARC", "2040", 2020, "architectuur")]


def test_agendatitels_lezen_het_nummer_op_zijn_plaats():
    assert lees("!! Mehdi: [HA-KB] WB 2603 - Testklant, Teststraat 1, 2800 Mechelen", "agenda_titel") == [
        ("HARC", "2603", 2026, "architectuur")]
    assert lees("Mehdi: [UB-KB] BS 46118 - Testklant, Teststraat 5, 3620 Lanaken", "agenda_titel") == [
        ("UNAB", "46118", None, None)]
    assert lees("[TK-KB] ST 4437 - Testklant, Proefstraat 7", "agenda_titel") == [("TKNB", "4437", None, None)]
    assert lees("[HA-KB] WB 46125 - Testklant", "agenda_titel") == []     # past niet bij de H-A-regel
    k = N.lees("[UB-KB] BS 46118 - x", "agenda_titel", 2026, register=REGISTER)[0]
    assert k.rol == "agendafirma" and not k.zeker                        # agendafirma is geen dossierhouder


def test_oude_agendacodes_via_de_aliasbron():
    assert lees("!! Mehdi: [HARC-KB] 2601 Proefklant", "agenda_titel") == [("HARC", "2601", 2026, "architectuur")]
    assert lees("!! Mehdi: [UNABO-KB] PLB 46073 Proefklant", "agenda_titel") == [("UNAB", "46073", None, None)]
    assert lees("[HARMONIEBOUW-KB] WB 2603 - Testklant", "agenda_titel") == [("HARM", "2603", None, None)]
    assert lees("[CTX-KO] 1411 - Testklant", "agenda_titel") == [("CONT", "1411", None, None)]


def test_onbekende_code_blijft_onbekend():
    k = N.lees("[ZZ-KB] WB 2603 - Testklant", "agenda_titel", 2026, register=REGISTER)
    assert [(x.firma, x.code, x.zeker) for x in k] == [(None, "ZZ", False)]
    assert N.firma_van_code("ZZ", register=REGISTER) is None
    assert N.lees("[PR-KB] 2603 privé", "agenda_titel", 2026, register=REGISTER) == []   # geen firma


def test_h_i_uit_het_register_zonder_nummerregel():
    k = N.lees("HI260034 krediet", "vrije_tekst", 2026, register=REGISTER)
    assert [(x.firma, x.nummer, x.lezingen, x.zeker) for x in k] == [("HINV", "260034", (), False)]
    assert "geen bevestigde nummerregel" in k[0].reden


def test_postcode_huisnummer_datum_en_jaartal_worden_geen_dossier():
    for tekst in ("Teststraat 2603, 3000 Leuven", "We bouwen in 2026 aan de Teststraat", "postcode 2800 Mechelen",
                  "afspraak 17-09-2026", "plannen 2026-09-17"):
        assert lees(tekst, "vrije_tekst") == [], tekst
        assert lees(tekst, "vergadertitel") == [], tekst
    assert lees("zie dossier 2603", "vrije_tekst") == [(None, "2603", None, None)]
    assert lees("Kim Venken 2611", "vergadertitel") == [("HARC", "2611", 2026, "architectuur")]
    assert lees("Meeting 2145 Online Sophie en Nico", "vergadertitel") == [("HARC", "2145", 2021, "architectuur")]
    for tekst in ("Kim Venken, Teststraat 1, 2500 Lier", "Plaatsbezoek Teststraat 1 2500 Lier",
                  "postcode 2500 Lier", "Teststraat 2503", "2026-09-17 bespreking", "2026 jaarplanning"):
        assert lees(tekst, "vergadertitel") == [], tekst


def test_kale_engineeringnummers():
    assert lees("46118", "vrije_tekst") == []                             # kaal: niets
    assert lees("46118_Barsten & Scheuren_Teststraat 206, 3620 Lanaken", "mapnaam_tkn", jaarmap=2026) == [
        (None, "46118", 2026, "engineering")]
    assert lees("4437_STA_RO_PS_Proefstraat 7", "mapnaam_tkn") == [(None, "4437", None, None)]   # niet 2044
    assert lees("46118 STA Teststraat 206, 3620 Lanaken", "factuur", administratie="TKNB") == [
        ("TKNB", "46118", None, None)]
    k = N.lees("46118 STA x", "factuur", 2026, register=REGISTER, administratie="TK")[0]
    assert k.rol == "facturerende_firma" and k.firma == "TKNB"
    assert lees("EE-26168 EPB Teststraat 1", "factuur", administratie="ENEF") == []   # factuurnummer


def test_contactnaam_en_meer_kandidaten_zonder_keuze():
    k = N.lees("K HA5609 UN3782 SCN Proef", "contactnaam", 2026, register=REGISTER)
    assert [(x.firma, x.nummer, x.rol) for x in k] == [("HARC", "5609", "contactfirma"), ("UNAB", "3782", "contactfirma")]
    assert N.enig(k) is None                                               # twee firma's: geen keuze
    assert N.enig(k, firma="HARC").nummer == "5609"
    assert N.ha_nummer("HA2603 en HA2612", "vrije_tekst", 2026, register=REGISTER) == ""   # twee H-A-nummers
    assert N.ha_nummer("2603 Testklant", "pipedrive_titel", 2026, register=REGISTER) == "2603"


def test_mapnamen_h_a():
    assert lees("2603 Teststraat 12, 2800 Mechelen (stan)", "mapnaam_ha") == [("HARC", "2603", 2026, "architectuur")]
    assert lees("2534(2414) Proefkaai 15", "mapnaam_ha") == [("HARC", "2534", 2025, "architectuur")]
    assert lees("2026-09-17 1434 HA2145 - klant - offerte", "mapnaam_ha") == []


def test_onbekende_bron_is_een_fout():
    try:
        N.lees("2603", "onbekend")
    except ValueError:
        return
    raise AssertionError("onbekende bron gaf geen fout")


def test_geen_eigen_firmalijst_in_de_lezer():
    bron = open(os.path.join(HIER, "koppelingen", "nummerlezer.py"), encoding="utf-8").read()
    for naam in ("H-Architects\"", "\"UnaBo", "Harmoniebouw\"", "\"HINV\"", "\"HB\":"):
        assert naam not in bron, f"eigen firmalijst in de lezer: {naam}"


def test_terugval_op_de_aliasbron_als_het_register_leeg_is():
    c = N.codes([])
    assert c["bron"].startswith("aliasbron")
    assert c["agenda"].get("HA") == "HARC" and c["agenda"].get("UB") == "UNAB"


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

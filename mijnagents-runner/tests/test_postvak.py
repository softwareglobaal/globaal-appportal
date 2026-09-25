"""Grendel op de mailwachten en De Wagenparkwacht (25-09-2026).

Mehdi: "geen spam, geen rommelinformatie". Deze test faalt zodra een regelwijziging reclame, koude
verkoop of phishing weer op de lijst van De Mailregisseur laat komen, of zodra het wagenpark een
mail aan de verkeerde wagen hangt. Draait zonder netwerk en zonder postbus.
"""
import os
import sys
from datetime import date, datetime

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
sys.path.insert(0, HIER)
import postvak  # noqa: E402
import wagenpark_wacht as W  # noqa: E402

EIGEN = ("h-architects.be", "h-invest.be")


def kop(van, onderwerp, naam=""):
    return {"van": van, "van_naam": naam, "onderwerp": onderwerp}


def test_rommel_koud_en_phishing_komen_nooit_op_de_lijst():
    assert postvak.trieer(kop("info@lamella-mail.com", "Word dealer van Lamella"), EIGEN)[0] == "rommel"
    assert postvak.trieer(kop("tom@oakproperties.be", "Hebt u interessante projecten?"), EIGEN)[0] == "rommel"
    assert postvak.trieer(kop("info@wooniot.nl", "Een vrijblijvende prijsindicatie voor uw project"), EIGEN)[0] == "koud"
    assert postvak.trieer(kop("anonymusss279@gmail.com", "Action requise", "My MINFIN"), EIGEN)[0] == "verdacht"


def test_afwezigheid_en_pakjes_zijn_meldingen():
    assert postvak.trieer(kop("vincent@verz.kbc.be", "Automatisch antwoord: schorsing"), EIGEN)[0] == "melding"
    assert postvak.trieer(kop("noreply@communication.bpost.be", "Je pakje van DHL werd geleverd"), EIGEN)[0] == "melding"


def test_wat_gevolg_heeft_komt_erdoor():
    assert postvak.trieer(kop("no-reply@txn.dropbox.com", "Your team's Dropbox account is paused"), EIGEN)[0] == "actie"
    assert postvak.trieer(kop("vincent@verz.kbc.be", "H-INVEST BV RENAULT Kangoo 1WKT459 - schorsing"), EIGEN)[0] == "hoog"
    assert postvak.trieer(kop("info@decolux-projects.be", "Offerteaanvraag renovatie woning"), EIGEN)[0] == "midden"
    bekend = frozenset({"daniel@lucvandewiel.be"})
    assert postvak.trieer(kop("daniel@lucvandewiel.be", "Schoten, Laaglandlei 3A"), EIGEN, bekend)[0] == "midden"


def test_antwoord_en_afwezigheid_tellen_als_beantwoord():
    na = datetime.fromisoformat("2026-09-14T10:00:00+02:00")
    verzonden = [{"datum": "2026-09-15T09:00:00+02:00", "aan": ["Vincent <vincent@verz.kbc.be>"], "cc": []}]
    assert postvak.beantwoord("vincent@verz.kbc.be", na, verzonden)
    assert not postvak.beantwoord("iemand@anders.be", na, verzonden)
    afwezig = {"x@kbc.be": [datetime.fromisoformat("2026-09-23T22:00:00+00:00")]}
    assert postvak.beantwoord("x@kbc.be", na, [], afwezig)


def test_een_domein_op_ing_be_is_nog_geen_bank():
    """25-09-2026: VALO projectontwikkeling kreeg 'rol bank' omdat valoprojectontwikkeling.be op ing.be eindigt."""
    soort, waarom = postvak.trieer(kop("info@valoprojectontwikkeling.be", "Re: 8288-002 Predallen"), EIGEN)
    assert "bank" not in waarom
    assert postvak.trieer(kop("klant@ing.be", "Uw rekening"), EIGEN)[1].startswith("rol bank")


GEKOZEN = {"mail-hinv": ["info@h-invest.be"], "mail-mch": ["mch@h-architects.be"],
           "mail-prive": ["mehdichegini@hotmail.com"], "mail-melo": ["melodiebvba@gmail.com"]}


def test_de_vier_postvakken_die_mehdi_koos_elk_met_een_eigen_runner():
    """Mehdi, 25-09-2026: 'elk e-mailadres een agent', alleen deze vier; 'de andere mogen weg'.
    Wie een postvak toevoegt of weghaalt, past deze lijst bewust aan."""
    cfg = postvak.wachten()
    wachten = {k: v for k, v in cfg.items() if isinstance(v, dict) and "postvakken" in v}
    assert {k: v["postvakken"] for k, v in wachten.items()} == GEKOZEN
    for naam in wachten:
        pad = os.path.join(HIER, naam.replace("-", "_") + ".py")
        assert os.path.exists(pad), f"geen runner voor {naam}"
        assert f'NAAM = "{naam}"' in open(pad).read()
    runners = {f[:-3].replace("_", "-") for f in os.listdir(HIER) if f.startswith("mail_") and f.endswith(".py")}
    assert runners - set(wachten) == {"mail-regisseur"}, f"runner zonder wacht: {runners - set(wachten)}"


def test_hotmail_uit_het_bestand_van_de_mac(tmp_path=None):
    """De hotmail-wacht leest een bestand van de Mac: eigen verzonden post telt niet, een bank zonder antwoord
    komt op de lijst, en een kopie die niet vers is, wordt gemeld."""
    import json
    import tempfile
    d = tempfile.mkdtemp()
    nu = datetime.fromisoformat("2026-09-25T10:00:00+02:00")
    koppen = {"gemaakt": "2026-09-25T02:00:00+02:00", "berichten": [
        {"map": "INBOX", "uid": 1, "datum": "2026-09-24T09:00:00+02:00", "van": "info@kbc.be", "van_naam": "KBC",
         "onderwerp": "Herinnering betaling", "message_id": "<a@kbc>", "aan": [], "cc": []},
        {"map": "INBOX", "uid": 2, "datum": "2026-09-24T09:30:00+02:00", "van": "mehdichegini@hotmail.com",
         "van_naam": "Mehdi", "onderwerp": "Factuur voor mezelf", "message_id": "<b@x>", "aan": [], "cc": []},
        {"map": "Sent", "uid": 3, "datum": "2026-09-01T09:00:00+02:00", "van": "mehdichegini@hotmail.com",
         "van_naam": "", "onderwerp": "x", "message_id": "<c@x>", "aan": ["iemand@ander.be"], "cc": []}]}
    json.dump(koppen, open(os.path.join(d, "koppen.json"), "w"))
    cfg = {"bronnen": {"mehdichegini@hotmail.com": os.path.join(d, "koppen.json")},
           "mail-prive": {"firma": "PRIV", "postvakken": ["mehdichegini@hotmail.com"], "antwoord_vanuit": [], "eigen_domeinen": []}}
    json.dump(cfg, open(os.path.join(d, "mailwachten.json"), "w"))
    oud = postvak.WACHTEN
    postvak.WACHTEN = os.path.join(d, "mailwachten.json")
    try:
        r = postvak._Droog()
        items, tel, _ = postvak.ronde("mail-prive", postvak._DroogAgent(), r, nu)
    finally:
        postvak.WACHTEN = oud
    assert [i["inhoud"]["van"] for i in items] == ["info@kbc.be"]
    assert tel["bekende_contacten"] == 1
    assert any("niet vers" in t for t, _w in r.noden), r.noden


def test_wat_op_25_september_ten_onrechte_doorkwam():
    """De droge ronde van 25-09-2026 op mch@, Melodie en hotmail: dit mag niet op de lijst."""
    t = lambda van, ond, naam="", **k: postvak.trieer(dict(kop(van, ond, naam), **k), EIGEN)  # noqa: E731
    assert t("x@audit.frequentflyer.com", "Réponse automatique : URGENT - Hacked and blocked Flying Blue account")[0] == "melding"
    assert t("contactcenter@dsb.sr", "[##1455335##] Bedankt voor uw e-mail aan het Customer Contact Center")[0] == "melding"
    assert t("postmaster@one.com", "Delivery delayed: URGENT - Hacked and blocked Flying Blue account", "Postmaster")[0] == "melding"
    assert t("postmaster@one.com", "Undeliverable: Factuur 2026-12", "Postmaster")[0] == "actie"
    assert t("bounce@send.one.com", "Delivery delayed: URGENT - Flying Blue", "Postmaster")[0] == "melding"
    assert t("no-reply@email.claude.com", "[No Action Required:] Text watermarking begins September 30", "Claude Team")[0] == "melding"
    assert "advocaat" not in t("support@twilio.com", "Request# 29703128 | Regulatory Bundle", "Stevenson Lawrence Lim (Support)")[1]
    assert t("support@octopus.be", "Import rapport")[0] == "melding"
    assert t("info@cluboase.sr", "75 jaar Oase – sport, vriendschap en mooie herinneringen!", automatisch=True)[0] == "melding"
    assert t("info@kineplusleuven.be", "HERINNERING - Uw afspraak bij KINEPLUSLEUVEN - woensdag 23/09", automatisch=True)[0] == "melding"
    assert t("alle.ouders@sk.sgarchipel.be", "Nieuwsbrief kinderkuren", lijst=True)[0] in ("melding", "rommel")


def test_wat_op_25_september_terecht_doorkwam_blijft():
    t = lambda van, ond, naam="", **k: postvak.trieer(dict(kop(van, ond, naam), **k), EIGEN)  # noqa: E731
    assert t("info-kbc@mail-kbc.be", "Je hebt info over een achterstal/overschrijding ontvangen voor H-INVEST BV",
             automatisch=True)[0] == "actie"
    assert t("daniel.renard@verz.kbc.be", "72971400 - PATRIMONIUMPOLIS HANDEL - herinnering premiebetaling")[0] == "hoog"
    assert t("an.berghmans@notaris.be", "RE: Verkoop Plantin en Moretuslei 6", "Notaris An BERGHMANS")[0] == "hoog"
    assert t("dussart@dinconsulting.be", "Afstemming intercompany Qoppa/H-Architects", "Nadine Dussart - Din Consulting")[0] == "hoog"


def test_werkdagen_tellen_het_weekend_niet():
    vr = datetime.fromisoformat("2026-09-25T10:00:00+02:00")
    ma = datetime.fromisoformat("2026-09-28T10:00:00+02:00")
    assert postvak.werkdagen_tussen(vr, ma) == 1


def test_wagenpark_herkent_de_juiste_wagen():
    reg = {"voertuigen": [
        {"plaat": "2BAS423", "platen_oud": [], "merk_model": "Ford Transit Custom", "chassis": "WF0FXXTTRFMA13765"},
        {"plaat": "2ACH377", "platen_oud": [], "merk_model": "Ford Transit Custom", "chassis": "WF0ZXXTTGZLS08891",
         "verzekering": {"polis": "C14904878747"}},
        {"plaat": "2HGD163", "platen_oud": ["1YLT748"], "merk_model": "Ford Fiesta", "chassis": "WF0GXXGAHGKT46507"},
        {"plaat": "2JCR831", "platen_oud": [], "merk_model": "Citroën Berlingo", "chassis": "VR7EDYHZ4SJ858741"}]}
    assert W.welke_wagen("Inschrijving nieuwe nummerplaat - Ford Transit (huidige plaat 2-BAS-423)", reg)[0]["plaat"] == "2BAS423"
    assert W.welke_wagen("C14904878747 H-INVEST BV - lichte vrachtauto", reg)[0]["plaat"] == "2ACH377"
    assert W.welke_wagen("keuring 1YLT748", reg)[0]["plaat"] == "2HGD163"
    assert W.welke_wagen("Renting contract CITROËN BERLINGO", reg)[0]["plaat"] == "2JCR831"
    assert W.welke_wagen("Offerte Ford Transit", reg)[0] is None, "twee Transits: nooit gokken"


def test_wagenpark_een_signaal_per_trede_zonder_alarmwoord():
    v = {"plaat": "2BAS423", "merk_model": "Ford Transit Custom", "gebruik": "Vlad", "mappen": ["/x"]}
    lijst = [(v, "keuring", date(2026, 9, 17), -8), (v, "groene kaart", date(2026, 10, 1), 6), (v, "onderhoud", date(2027, 1, 1), 98)]
    s = W.signalen(lijst, date(2026, 9, 25))
    assert [x["uniek"].rsplit(":", 1)[1] for x in s] == ["verlopen", "14"]
    assert all("stil" not in x["titel"].lower() for x in s)


def test_verzekering_geeft_vervaldag_en_opzegdatum():
    """Mehdi, 25-09-2026: op tijd opzeggen om bij een nieuwe verzekeraar de eerstejaarskorting te nemen."""
    v = {"plaat": "2JCR831", "merk_model": "Citroën Berlingo", "status": "in gebruik", "gebruik": "Harmoniebouw", "mappen": ["/x"],
         "verzekering": {"tot": "2027-03-31"}}
    vz = [{"object": "2-JCR-831", "verzekeraar": "AXA", "einddatum": "2027-03-31", "opzegtermijn_maanden": 3}]
    lijst, _ = W.termijnen({"voertuigen": [v]}, date(2026, 12, 1), vz)
    wat = {x[1]: x[2] for x in lijst}
    assert wat["opzeggen verzekering AXA"] == date(2026, 12, 31), wat
    assert wat["vervaldag verzekering AXA"] == date(2027, 3, 31)
    assert "verzekering" not in wat, "met een polis in vermogen telt de datum uit het register niet dubbel"
    s = W.signalen(lijst, date(2026, 12, 1))
    opz = [x for x in s if "opzeggen" in x["titel"]]
    assert opz and opz[0]["uniek"].endswith(":30") and "offertes" in opz[0]["inhoud"]["voorstel"]


def test_vooruitblik_volgt_de_fabrikant_en_de_eigen_facturen():
    reg = {"voertuigen": [{"plaat": "2BAS423", "merk_model": "Ford Transit Custom", "status": "in gebruik", "eerste_inschrijving": "2021-09-10",
                           "fabrikant": {"interval_km": 60000, "interval_maanden": 24, "riem_km": 160000, "riem_maanden": 72},
                           "km": [{"datum": "2025-05-26", "km": 120000}, {"datum": "2026-05-26", "km": 147858}],
                           "onderhoud": [{"datum": "2025-04-10", "soort": "onderhoud", "km": 118000, "omschrijving": "onderhoud olie en filters", "bedrag": "400,00"},
                                         {"datum": "2024-01-10", "soort": "herstelling", "km": 100000, "werken": [{"onderdeel": "remblokken voor", "bedrag": "250,00"}]}]}]}
    b = {x["onderdeel"]: x for x in W.vooruitblik(reg, date(2026, 9, 25))["2BAS423"]["vooruitblik"]}
    assert b["distributieriem"]["herkomst"] == "fabrikant" and b["distributieriem"]["laatst"] is None
    assert b["onderhoudsbeurt (olie en filters)"]["verwacht"] == "2027-04-10"
    assert b["onderhoudsbeurt (olie en filters)"]["kost_eigen_facturen"] is None, "een factuurtotaal zonder aparte lijn is geen prijs"
    assert b["remblokken"]["kost_eigen_facturen"] == 250


if __name__ == "__main__":
    fout = 0
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            try:
                f()
                print("  ok  ", n)
            except AssertionError as e:
                fout += 1
                print("  FOUT", n, e)
    sys.exit(1 if fout else 0)

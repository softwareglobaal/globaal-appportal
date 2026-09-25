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

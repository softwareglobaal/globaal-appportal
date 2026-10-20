"""Grendel op de mailwachten en De Wagenparkwacht (25-09-2026).

Mehdi: "geen spam, geen rommelinformatie". Deze test faalt zodra een regelwijziging reclame, koude
verkoop of phishing weer op de lijst van De Mailregisseur laat komen, of zodra het wagenpark een
mail aan de verkeerde wagen hangt. Draait zonder netwerk en zonder postbus.
"""
import os
import sys
from datetime import date, datetime, timedelta

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


def _verzonden(van, aan, onderwerp, datum, in_reply_to="", refs=()):
    return {"van": van, "aan": [aan], "cc": [], "onderwerp": onderwerp, "datum": datum, "in_antwoord_op": in_reply_to,
            "verwijzingen": list(refs)}


def test_beantwoord_alleen_via_de_draad():
    """19-10-2026 (driehoeksoverleg, 3-0): tot dan sloot elk bericht naar dezelfde afzender het punt, ook over iets anders.
    Een belangrijke mail verdween zo van de lijst zodra Mehdi die persoon om een andere reden mailde."""
    na = datetime.fromisoformat("2026-10-14T10:00:00+02:00")
    b = {"van": "vincent@verz.kbc.be", "onderwerp": "Schorsing polis Kangoo", "message_id": "<vraag@kbc>"}
    idx = postvak.antwoord_index([_verzonden("mch@h-architects.be", "Vincent <vincent@verz.kbc.be>",
                                             "Andere vraag over de bestelwagen", "2026-10-15T09:00:00+02:00")])
    assert postvak.antwoord(b, na, idx)[0] == "open", "een ander onderwerp naar dezelfde afzender sluit het punt niet"
    idx = postvak.antwoord_index([_verzonden("info@h-invest.be", "vincent@verz.kbc.be", "Re: Schorsing polis Kangoo",
                                             "2026-10-15T09:00:00+02:00", "<vraag@kbc>")])
    st, door, wanneer, _ = postvak.antwoord(b, na, idx)
    assert (st, door) == ("beantwoord", "info@h-invest.be") and wanneer.startswith("2026-10-15"), \
        "een antwoord vanuit een ander postvak sluit het wel, met wie en wanneer"
    idx = postvak.antwoord_index([_verzonden("mch@h-architects.be", "boekhouding@h-invest.be", "Fwd: Schorsing polis Kangoo",
                                             "2026-10-15T09:00:00+02:00", "<vraag@kbc>")])
    assert postvak.antwoord(b, na, idx)[0::3] == ("doorgezet", "boekhouding@h-invest.be")
    idx = postvak.antwoord_index([_verzonden("mch@h-architects.be", "vincent@verz.kbc.be", "Re: Schorsing polis Kangoo",
                                             "2026-10-16T09:00:00+02:00", "<later@kbc>", ["<vraag@kbc>", "<later@kbc>"])])
    assert postvak.antwoord(b, na, idx)[0] == "onzeker", "alleen in References: een antwoord op een later bericht in de draad"
    idx = postvak.antwoord_index([_verzonden("mch@h-architects.be", "vincent@verz.kbc.be", "RE: schorsing  polis Kangoo",
                                             "2026-10-15T09:00:00+02:00")])
    assert postvak.antwoord(b, na, idx)[:2] == ("onzeker", "mch@h-architects.be"), "zelfde onderwerp zonder draad: nakijken"
    assert postvak.antwoord(b, datetime.fromisoformat("2026-10-16T10:00:00+02:00"), idx)[0] == "open", "verstuurd voor de vraag"
    afwezig = {"vincent@verz.kbc.be": [(datetime.fromisoformat("2026-10-15T09:00:00+02:00"),
                                        "Automatisch antwoord: RE: Schorsing polis Kangoo")]}
    assert postvak.antwoord(b, na, postvak.antwoord_index([]), afwezig)[0] == "onzeker"
    assert postvak.antwoord(b, na, postvak.antwoord_index([]), {"vincent@verz.kbc.be": [
        (datetime.fromisoformat("2026-10-15T09:00:00+02:00"), "Automatisch antwoord: offerte")]})[0] == "open"


def test_hotmail_draad_met_de_hashes_van_de_mac():
    """Mail op de Mac geeft de draad als hashes (message_references); de laatste is het bericht waarop geantwoord wordt."""
    na = datetime.fromisoformat("2026-10-14T10:00:00+02:00")
    b = {"van": "x@kbc.be", "onderwerp": "Herinnering", "draad": "123"}
    s = {"van": "mehdichegini@hotmail.com", "aan": ["x@kbc.be"], "cc": [], "onderwerp": "Re: Herinnering",
         "datum": "2026-10-15T09:00:00+00:00", "verwijst": ["99", "123"]}
    assert postvak.antwoord(b, na, postvak.antwoord_index([s]))[0] == "beantwoord"
    assert postvak.antwoord(b, na, postvak.antwoord_index([dict(s, verwijst=["123", "456"])]))[0] == "onzeker"


def test_een_domein_op_ing_be_is_nog_geen_bank():
    """25-09-2026: VALO projectontwikkeling kreeg 'rol bank' omdat valoprojectontwikkeling.be op ing.be eindigt."""
    soort, waarom = postvak.trieer(kop("info@valoprojectontwikkeling.be", "Re: 8288-002 Predallen"), EIGEN)
    assert "bank" not in waarom
    assert postvak.trieer(kop("klant@ing.be", "Uw rekening"), EIGEN)[1].startswith("rol bank")


GEKOZEN = {"mail-info-harc": ["info@h-architects.be"], "mail-hinv": ["info@h-invest.be"], "mail-mch": ["mch@h-architects.be"],
           "mail-prive": ["mehdichegini@hotmail.com"], "mail-melo": ["melodiebvba@gmail.com"]}


def test_de_postvakken_die_mehdi_koos_elk_met_een_eigen_runner():
    """Mehdi, 25-09-2026: 'elk e-mailadres een agent', alleen deze vier; 'de andere mogen weg'. 26-09-2026: info@ H-A erbij.
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
        items, tel, _, alle = postvak.ronde("mail-prive", postvak._DroogAgent(), r, nu)
    finally:
        postvak.WACHTEN = oud
    assert [i["van"] for i in items] == ["info@kbc.be"]
    assert tel["bekende_contacten"] == 1
    assert any("niet vers" in t for t, _w in r.noden), r.noden
    assert [a["van"] for a in alle] == ["info@kbc.be"], "elk beoordeeld bericht gaat naar het dashboard, eigen post niet"
    assert alle[0]["soort"] == "hoog" and alle[0]["beantwoord"] == 0 and alle[0]["uniek"] == "mehdichegini@hotmail.com:<a@kbc>"
    assert alle[0]["opvolging"] == "open" and alle[0]["message_id"] == "<a@kbc>" and "mailinglijst" in alle[0]


def _ronde(berichten, nu, eigen=("h-architects.be", "harmoniebouw.be", "globaal.be"), oude=None, veilig=frozenset()):
    """Een ronde van een wacht op een bestand (zoals hotmail van de Mac): zonder postbus en zonder netwerk."""
    import json
    import tempfile
    d = tempfile.mkdtemp()
    json.dump({"gemaakt": nu.isoformat(), "berichten": berichten}, open(os.path.join(d, "koppen.json"), "w"))
    cfg = {"bronnen": {"proef@h-architects.be": os.path.join(d, "koppen.json")},
           "mail-proef": {"firma": "MCH", "postvakken": ["proef@h-architects.be"], "antwoord_vanuit": [], "eigen_domeinen": list(eigen)}}
    json.dump(cfg, open(os.path.join(d, "mailwachten.json"), "w"))
    oud = postvak.WACHTEN
    postvak.WACHTEN = os.path.join(d, "mailwachten.json")
    try:
        r = postvak._Droog()
        items, tel, _, alle = postvak.ronde("mail-proef", postvak._DroogAgent(), r, nu, None, oude, veilig)
    finally:
        postvak.WACHTEN = oud
    return {a["onderwerp"]: a for a in alle}, items, tel, r


def _in(uid, van, onderwerp, datum, mid=None, **k):
    return dict({"map": "INBOX", "uid": uid, "datum": datum, "van": van, "van_naam": van.split("@")[0], "onderwerp": onderwerp,
                 "message_id": mid or f"<{uid}@proef>", "aan": [], "cc": []}, **k)


def _uit(uid, aan, onderwerp, datum, antwoord_op=None):
    return {"map": "Sent", "uid": uid, "datum": datum, "van": "proef@h-architects.be", "van_naam": "", "onderwerp": onderwerp,
            "message_id": f"<s{uid}@proef>", "aan": [aan], "cc": [], "verwijst": [], "in_antwoord_op": antwoord_op or ""}


def test_drempels_eigen_domein_en_kopieermachine():
    """19-10-2026: gewone mail na een werkdag; eigen domein alleen uit bij een automatisch bericht; de kopieermachine is
    automatisch (op het exacte adres), een collega die een scan doorstuurt niet."""
    nu = datetime.fromisoformat("2026-10-19T15:00:00+02:00")          # maandag
    alle, items, tel, _ = _ronde([
        _uit(90, "klant@bouwheer.be", "Offerte", "2026-09-01T09:00:00+02:00"),
        _in(1, "klant@bouwheer.be", "Vraag over de offerte", "2026-10-16T10:00:00+02:00"),       # vrijdag: 1 werkdag
        _in(2, "klant@bouwheer.be", "Nog een vraag", "2026-10-19T09:00:00+02:00"),               # vandaag
        _in(3, "shaniel@h-architects.be", "Vraag over dossier 2145", "2026-10-16T10:00:00+02:00"),
        _in(4, "scan@harmoniebouw.be", "Message from KM_C258", "2026-10-16T10:00:00+02:00"),
        _in(5, "angela@globaal.be", "Fwd: Message from KM_C258", "2026-10-16T10:00:00+02:00"),
        _in(6, "noreply@h-architects.be", "Uw bestelling", "2026-10-16T10:00:00+02:00"),
        _in(7, "iemand@vreemd.be", "Message from KM_C258", "2026-10-16T10:00:00+02:00"),
    ], nu)
    assert alle["Vraag over de offerte"]["opvolging"] == "open", "gewone mail van vrijdag staat maandag op de lijst"
    assert alle["Nog een vraag"]["opvolging"] == "wacht", "van vandaag nog niet"
    assert alle["Vraag over dossier 2145"]["opvolging"] == "open", "een collega die iets vraagt, is een opvolgpunt"
    assert alle["Message from KM_C258"]["soort"] in ("melding", "koud") and alle["Message from KM_C258"]["opvolging"] == "geen"
    assert postvak.automatisch({"van": "scan@harmoniebouw.be", "onderwerp": "Message from KM_C258"})
    assert not postvak.automatisch({"van": "iemand@vreemd.be", "onderwerp": "Message from KM_C258"}), "het onderwerp alleen niet"
    assert alle["Fwd: Message from KM_C258"]["opvolging"] == "open", "Angela die een scan doorstuurt"
    assert alle["Uw bestelling"]["opvolging"] == "geen"
    assert postvak.OPVOLGEN_NA_WERKDAGEN == 1
    assert tel["open"] == len(items) == 3


def test_beantwoord_in_de_ronde_en_oude_punten():
    """De ronde gebruikt de draad; een open punt ouder dan het venster sluit ook nog als er laat een antwoord komt."""
    nu = datetime.fromisoformat("2026-10-19T15:00:00+02:00")
    alle, items, tel, _ = _ronde([
        _in(1, "x@kbc.be", "Schorsing polis", "2026-10-14T10:00:00+02:00", "<v1@kbc>"),
        _in(2, "x@kbc.be", "Herinnering premie", "2026-10-14T11:00:00+02:00", "<v2@kbc>"),
        _uit(91, "x@kbc.be", "Re: Schorsing polis", "2026-10-15T09:00:00+02:00", "<v1@kbc>"),
        _uit(92, "x@kbc.be", "Iets anders", "2026-10-15T09:30:00+02:00"),
        _uit(93, "notaris@notaris.be", "Re: Akte", "2026-10-18T09:00:00+02:00", "<oud@notaris>"),
    ], nu, oude=[{"uniek": "proef@h-architects.be:<oud@notaris>", "postvak": "proef@h-architects.be", "van": "notaris@notaris.be",
                  "onderwerp": "Akte", "datum_iso": "2026-09-01T10:00:00+02:00", "soort": "hoog", "message_id": "<oud@notaris>"}])
    assert alle["Schorsing polis"]["opvolging"] == "beantwoord" and alle["Schorsing polis"]["antwoord_door"] == "proef@h-architects.be"
    assert alle["Herinnering premie"]["opvolging"] == "open", "Iets anders naar KBC sluit de herinnering niet"
    assert alle["Akte"]["opvolging"] == "beantwoord" and alle["Akte"]["uniek"] == "proef@h-architects.be:<oud@notaris>"
    assert tel["verzonden_volledig"]


def test_verdwenen_en_zonder_sleutel():
    """Resultaattoets 19-10-2026: een open punt binnen het venster dat niet meer in het volledig gelezen postvak staat, wordt
    'verdwenen' (K4); een bericht zonder Message-ID en zonder uid wordt overgeslagen (K5)."""
    nu = datetime.fromisoformat("2026-10-19T15:00:00+02:00")
    weg = {"uniek": "proef@h-architects.be:<weg@x>", "postvak": "proef@h-architects.be", "van": "klant@bouwheer.be",
           "onderwerp": "Verplaatst door Mehdi", "datum_iso": "2026-10-14T10:00:00+02:00", "soort": "midden",
           "message_id": "<weg@x>"}
    alle, items, tel, _ = _ronde([_in(1, "klant@bouwheer.be", "Nog hier", "2026-10-14T10:00:00+02:00"),
                                  dict(_in(2, "x@kbc.be", "Zonder sleutel", "2026-10-14T10:00:00+02:00"), uid=None, message_id="")],
                                 nu, oude=[weg])
    assert alle["Verplaatst door Mehdi"]["opvolging"] == "verdwenen"
    assert "Zonder sleutel" not in alle
    assert "Verplaatst door Mehdi" not in [i["onderwerp"] for i in items], "verdwenen telt niet als open"


def test_een_kapotte_verzonden_map_is_onvolledig():
    """Resultaattoets K2: een map Verzonden die bestaat maar niet te lezen is, maakt de lezing onvolledig."""
    oud_koppen, oud_postvak, oud_namen = postvak.koppen, postvak.postvak, postvak.mapnamen
    def koppen(adres, m, sinds=None, plafond=1000):
        if m == "INBOX.Sent":
            raise OSError("time-out")
        return []
    postvak.koppen = koppen
    postvak.postvak = lambda a: {"adres": a}
    postvak.mapnamen = lambda mb: {"inbox", "inbox.sent"}
    try:
        import json
        import tempfile
        d = tempfile.mkdtemp()
        json.dump({"mail-proef": {"postvakken": ["p@h-architects.be"], "antwoord_vanuit": [], "eigen_domeinen": []}},
                  open(os.path.join(d, "mailwachten.json"), "w"))
        oud = postvak.WACHTEN
        postvak.WACHTEN = os.path.join(d, "mailwachten.json")
        r = postvak._Droog()
        _, tel, _, _ = postvak.ronde("mail-proef", postvak._DroogAgent(), r, datetime.fromisoformat("2026-10-19T15:00:00+02:00"))
    finally:
        postvak.koppen, postvak.postvak, postvak.mapnamen, postvak.WACHTEN = oud_koppen, oud_postvak, oud_namen, oud
    assert not tel["verzonden_volledig"] and any("niet volledig" in t for t, _ in r.noden)


# --- Uitschrijven via de officiele knop (Mehdi, 20-10-2026; ontwerptoets C1-C9, G1-G5, K1-K8) ---

AR_ONE = ("mx3.cst.mailpod8-cph3.one.com; spf=pass smtp.mailfrom=x; dkim=pass header.d=brand.be header.s=s1 "
          "header.a=rsa-sha256 header.b=AbCdEfGh")
DKIM_BRAND = "v=1; a=rsa-sha256; d=brand.be; s=s1; h=from:to:subject:list-unsubscribe:list-unsubscribe-post; bh=x; b=AbCdEfGh IjKl"


def _nieuwsbrief(van="news@brand.be", knop="https://unsub.brand.be/u?t=GEHEIM", post="List-Unsubscribe=One-Click",
                 onderwerp="Nieuw: onze najaarsactie met korting", **k):
    import uitschrijven as U  # noqa: F401
    return dict({"van": van, "van_naam": "Brand", "onderwerp": onderwerp, "map": "INBOX.Opgeruimd", "message_id": "<n1@brand.be>",
                 "datum": datetime.fromisoformat("2026-10-15T10:00:00+02:00"),
                 "list_unsubscribe": f"<mailto:unsub@brand.be>, <{knop}>", "list_unsubscribe_post": post,
                 "authentication_results": [AR_ONE], "dkim_signatures": [DKIM_BRAND], "uitschrijfkoppen": (1, 1)}, **k)


def test_uitschrijven_alleen_de_officiele_knop():
    import uitschrijven as U
    assert U.knop("<mailto:a@b.be>, <https://x.be/u>", "List-Unsubscribe=One-Click") == "https://x.be/u"
    assert U.knop("<mailto:a@b.be>", "List-Unsubscribe=One-Click") is None, "mailto is versturen: nooit"
    assert U.knop("<http://x.be/u>", "List-Unsubscribe=One-Click") is None, "geen https"
    assert U.knop("<https://x.be/u>", "") is None, "zonder List-Unsubscribe-Post is het geen one-click-knop"
    assert U.knop("<https://x.be/u>", "List-Unsubscribe=Maybe") is None
    bron = open(os.path.join(HIER, "koppelingen", "uitschrijven.py"), encoding="utf-8").read()
    assert 'c.request("POST"' in bron and '"GET"' not in bron and "urlopen" not in bron, "alleen een POST, nooit een GET"
    assert "BODY.PEEK" in bron and "smtplib" not in bron and "\\Seen" not in bron


def test_uitschrijven_post_zonder_doorverwijzing_en_zonder_cookies():
    import uitschrijven as U
    gezien = []

    class Antw:
        def __init__(self, status):
            self.status = status

        def read(self, n):
            return b""

    def maak(status):
        class Verbinding:
            def __init__(self, host, ip, timeout):
                gezien.append(("verbind", host, ip, timeout))

            def request(self, methode, pad, body, headers):
                gezien.append((methode, pad, body, dict(headers)))

            def getresponse(self):
                return Antw(status)

            def close(self):
                pass
        return Verbinding
    assert U.post("https://unsub.brand.be/u?t=1", "93.184.216.34", maak(200)) == ("aanvaard", 200)
    assert gezien[0] == ("verbind", "unsub.brand.be", "93.184.216.34", U.TIJDSLIMIET), "verbinden met het gecontroleerde IP"
    methode, pad, body, kop = gezien[1]
    assert (methode, pad, body) == ("POST", "/u?t=1", b"List-Unsubscribe=One-Click")
    assert kop["Content-Type"] == "application/x-www-form-urlencoded" and not {"Cookie", "Authorization"} & set(kop)
    gezien.clear()
    assert U.post("https://unsub.brand.be/u", "93.184.216.34", maak(302)) == ("geweigerd", 302)
    assert [g[0] for g in gezien] == ["verbind", "POST"], "een doorverwijzing wordt niet gevolgd"

    def kapot(*a, **k):
        raise OSError("time-out")
    assert U.post("https://unsub.brand.be/u", "93.184.216.34", kapot) == ("fout", 0)


def test_uitschrijven_raakt_nooit_de_vm_of_het_netwerk():
    import socket
    import uitschrijven as U

    def dns(*ips):
        return lambda host, poort, proto=None: [(socket.AF_INET, 1, 6, "", (i, 443)) for i in ips]
    assert U.adres_ok("https://unsub.brand.be/u", dns("93.184.216.34"))[1:] == ("93.184.216.34", "")
    for ips in (("127.0.0.1",), ("10.0.0.5",), ("192.168.1.2",), ("169.254.169.254",), ("::1",), ("93.184.216.34", "10.0.0.1")):
        assert U.adres_ok("https://unsub.brand.be/u", dns(*ips))[1] is None, ips
    for url in ("http://unsub.brand.be/u", "https://93.184.216.34/u", "https://unsub.brand.be:8443/u", "https://a:b@unsub.brand.be/u",
                "https://localhost/u"):
        assert U.adres_ok(url, dns("93.184.216.34"))[1] is None, url


def test_uitschrijven_alleen_een_ondertekende_knop_van_de_afzender():
    import uitschrijven as U
    assert U.ondertekend([AR_ONE], [DKIM_BRAND]) == {"brand.be"}
    gmail = "mx.google.com; dkim=pass header.i=@brand.be header.s=s1 header.b=AbCdEfGh; spf=pass (google.com: domain of x)"
    assert U.ondertekend([gmail], [DKIM_BRAND]) == {"brand.be"}, "Gmail schrijft header.i=@domein (gezien 20-10-2026)"
    assert not U.ondertekend(["mx.evil.com; dkim=pass header.d=brand.be", AR_ONE], [DKIM_BRAND]), "alleen onze eigen server, bovenaan"
    assert not U.ondertekend([AR_ONE.replace("dkim=pass", "dkim=fail")], [DKIM_BRAND])
    assert not U.ondertekend([AR_ONE], [DKIM_BRAND.replace(":list-unsubscribe-post", "")]), "de handtekening dekt de knop niet"
    assert not U.ondertekend([AR_ONE.replace(" header.b=AbCdEfGh", "")], [DKIM_BRAND]), "zonder header.b niet te koppelen"
    # X1: de echte handtekening dekt de knop niet; een tussenpersoon voegt een vervalste tweede toe die dat wel beweert.
    echt = DKIM_BRAND.replace(":list-unsubscribe:list-unsubscribe-post", "")
    vals_zelfde_begin = DKIM_BRAND.replace("b=AbCdEfGh IjKl", "b=AbCdEfGhVALS")
    ar_twee = AR_ONE + "; dkim=fail header.d=brand.be header.s=s1 header.b=AbCdEfGh"
    assert not U.ondertekend([ar_twee], [echt, vals_zelfde_begin]), "X1: dezelfde sleutel faalde ook"
    assert not U.ondertekend([AR_ONE], [echt, vals_zelfde_begin]), "X1: twee handtekeningen bij een resultaat"
    vals_ander_begin = DKIM_BRAND.replace("b=AbCdEfGh IjKl", "b=ZzZzZzZz")
    assert not U.ondertekend([AR_ONE], [echt, vals_ander_begin]), "X1: de geslaagde handtekening is niet die van de knop"
    assert not U.ondertekend([AR_ONE], [DKIM_BRAND.replace("s=s1", "s=s2")]), "andere selector"
    eigen, bekend, veilig = ("h-architects.be",), frozenset(), frozenset()
    assert U.beoordeel(_nieuwsbrief(), "rommel", "", eigen, bekend, veilig, True)[0] == "https://unsub.brand.be/u?t=GEHEIM"
    andere = _nieuwsbrief(van="news@ander.be")
    assert U.beoordeel(andere, "rommel", "", eigen, bekend, veilig, True) == (None, "de afzender ondertekende de knop niet zelf")
    # Mehdi, 20-10-2026: de knop mag bij een verzendbedrijf staan, als de afzender zelf ondertekende en er een knop is
    esp = _nieuwsbrief(knop="https://us1.list-manage.com/unsubscribe/post?u=GEHEIM")
    assert U.beoordeel(esp, "rommel", "", eigen, bekend, veilig, True)[0] == "https://us1.list-manage.com/unsubscribe/post?u=GEHEIM"
    assert U.beoordeel(dict(esp, uitschrijfkoppen=(2, 1)), "rommel", "", eigen, bekend, veilig, True)[0] is None, \
        "maar nooit met twee uitschrijfkoppen"
    ar_esp = "mx3.cst.mailpod8-cph3.one.com; dkim=pass header.d=mcsv.net header.s=k2 header.b=QrStUvWx"
    dkim_esp = "v=1; d=mcsv.net; s=k2; h=from:subject:list-unsubscribe:list-unsubscribe-post; bh=x; b=QrStUvWxYz"
    alleen_esp = dict(esp, authentication_results=[ar_esp], dkim_signatures=[dkim_esp])
    assert U.beoordeel(alleen_esp, "rommel", "", eigen, bekend, veilig, True) == (None, "de afzender ondertekende de knop niet zelf"), \
        "een handtekening van alleen het verzendbedrijf telt niet"
    beide = dict(esp, authentication_results=[AR_ONE + "; " + ar_esp.split("; ", 1)[1]],
                 dkim_signatures=[DKIM_BRAND.replace(":list-unsubscribe:list-unsubscribe-post", ""), dkim_esp])
    assert U.beoordeel(beide, "rommel", "", eigen, bekend, veilig, True)[0] is None, \
        "de afzender ondertekende wel, maar niet de knop; alleen het verzendbedrijf dekte hem"
    # derde toets X1: een knop bij een willekeurig ander domein niet, ook niet als de afzender hem ondertekende
    assert U.beoordeel(_nieuwsbrief(knop="https://unsub.ander-bedrijf.be/u"), "rommel", "", eigen, bekend, veilig, True) == \
        (None, "knop niet bij de afzender of een bekend verzendbedrijf")
    assert U.beoordeel(_nieuwsbrief(knop="https://x.sendgrid.net/u"), "rommel", "", eigen, bekend, veilig, True)[0], "SendGrid wel"
    for host in ("a.klaviyo.kmail-lists.com", "x.mjt.lu", "t.hubspotemail-eu1.net"):
        assert U.beoordeel(_nieuwsbrief(knop=f"https://{host}/u"), "rommel", "", eigen, bekend, veilig, True)[0], host
    assert U.beoordeel(_nieuwsbrief(knop="https://www.flyingblue.com/u"), "rommel", "", eigen, bekend, veilig, True)[0] is None, \
        "een ander domein van hetzelfde bedrijf is geen verzendbedrijf"
    zonder_telling = {k: v for k, v in _nieuwsbrief().items() if k != "uitschrijfkoppen"}
    assert U.beoordeel(zonder_telling, "rommel", "", eigen, bekend, veilig, True)[0] is None, "zonder telling: weigeren (K3)"
    platform = dict(alleen_esp, van="nieuws@klant.mcsv.net")
    assert U.beoordeel(platform, "rommel", "", eigen, bekend, veilig, True) == (None, "afzender op een domein van een verzendbedrijf")
    assert U.beoordeel(_nieuwsbrief(knop="https://unsub.mybank-mail.com/u"), "rommel", "", eigen, bekend, veilig, True)[0] is None, \
        "een knop bij een verzendbedrijf van een bank blijft beschermd"
    assert U.hoofddomein("nieuws.kmoinsider.be") == "kmoinsider.be" and U.hoofddomein("mail.bedrijf.co.uk") == "bedrijf.co.uk"
    assert U.hoofddomein("mail.bedrijf.com.pl") == "bedrijf.com.pl" and U.hoofddomein("x.firma.co.th") == "firma.co.th", "K5"


def test_helemaal_weg_gaat_voor_de_automatische_voorwaarden_maar_niet_voor_de_knop():
    """Mehdi, 20-10-2026: "een knop die meer is dan ruis ... helemaal uitschrijven, zodat het effectief gedaan is". Een
    afzender op Helemaal weg (regel 'uitschrijven'): geen eis van soort, terugkeer, rol of klantenlijst, want iemand koos
    zelf; wel eigen domein, gratis maildienst en elke controle op de knop. De wacht ruimt hem op zoals Opruimen."""
    import uitschrijven as U
    eigen, bekend, veilig = ("h-architects.be",), frozenset({"news@brand.be"}), frozenset({"brand.be"})
    b = _nieuwsbrief(onderwerp="Re: uw vraag")
    assert U.beoordeel(b, "hoog", "", eigen, bekend, veilig, False)[0] is None, "automatisch nooit (klant, eerste keer)"
    assert U.beoordeel(b, "hoog", "uitschrijven", eigen, bekend, veilig, False)[0] == "https://unsub.brand.be/u?t=GEHEIM"
    assert U.beoordeel(dict(b, uitschrijfkoppen=(2, 1)), "rommel", "uitschrijven", eigen, bekend, veilig, True)[0] is None
    assert U.beoordeel(_nieuwsbrief(van="news@ander.be"), "rommel", "uitschrijven", eigen, bekend, veilig, True)[0] is None, \
        "ook op vraag nooit een knop die de afzender niet zelf ondertekende"
    assert U.beoordeel(_nieuwsbrief(knop="https://unsub.ander-bedrijf.be/u"), "rommel", "uitschrijven", eigen, bekend, veilig,
                       True)[0] is None
    assert U.beoordeel(_nieuwsbrief(van="x@h-architects.be"), "rommel", "uitschrijven", eigen, bekend, veilig, True) == \
        (None, "eigen domein")
    assert postvak.trieer(kop("news@brand.be", "Nieuwsbrief"), EIGEN, frozenset(), "uitschrijven")[0] == "rommel"
    # Codex-toets e70f5a4, 1: Helemaal weg laat nooit dringende mail verdwijnen (Ruis en Opruimen gaan voor alles, 26-09)
    assert postvak.trieer(kop("info-kbc@mail-kbc.be", "Laatste aanmaning: achterstal H-INVEST BV"), EIGEN, frozenset(),
                          "uitschrijven")[0] != "rommel"
    bron = open(os.path.join(HIER, "koppelingen", "postvak.py"), encoding="utf-8").read()
    assert 'actie in ("opruimen", "uitschrijven")' in bron, "Helemaal weg ruimt op zoals Opruimen"
    assert 'spaar_dringend=actie == "uitschrijven"' in bron and "spaar_dringend and DRINGEND.search(" in bron, \
        "Helemaal weg laat dringende mail in de inbox"
    ronde = open(os.path.join(HIER, "koppelingen", "uitschrijven.py"), encoding="utf-8").read()
    assert 'key=lambda x: (expliciet(x[0], x[2])' in ronde, "Helemaal weg gaat voor in de beurt"


def test_uitschrijven_nooit_bij_bank_overheid_verzekeraar_notaris_of_klant():
    import uitschrijven as U
    eigen = ("h-architects.be",)

    def nee(b, soort="rommel", regel="", bekend=frozenset(), veilig=frozenset(), terug=True):
        return U.beoordeel(b, soort, regel, eigen, bekend, veilig, terug)[0] is None
    assert not nee(_nieuwsbrief()), "een gewone nieuwsbrief van een terugkerende verzender mag (anders test hieronder niets)"
    assert nee(_nieuwsbrief(van="nieuws@kbc.be")), "bank, ook als het reclame is"
    # X2, K1: banken, verzekeraars en overheid met een naam die niet in postvak.ROLLEN staat
    for van, naam in (("news@keytrade.be", "Keytrade"), ("promo@brand.be", "Beobank"), ("info@brand.be", "Allianz Benelux"),
                      ("news@brand.be", "AP Assurances"), ("info@mobilit.fgov.be", "Mobilit"), ("news@brand.be", "Triodos"),
                      ("news@brand.be", "Partena ziekenfonds"), ("news@brand.be", "Notaire Dupont")):
        assert nee(_nieuwsbrief(van=van, van_naam=naam)), (van, naam)
    assert nee(_nieuwsbrief(knop="https://unsub.mybank.be/u")), "ook de knop van een bank via een verzendbedrijf"
    # X3, K2: een klant
    assert nee(_nieuwsbrief(), terug=False), "ook rommel alleen van een terugkerende verzender: een klant mailt een eerste keer"
    assert nee(_nieuwsbrief(onderwerp="Re: uw offerte met korting")), "een antwoord"
    assert nee(_nieuwsbrief(onderwerp="TR: gratis plaatsbezoek")), "doorgestuurd"
    assert nee(_nieuwsbrief(onderwerp="Offerteaanvraag renovatie: ontdek ons voorstel")), "een aanvraag"
    # tweede toets: DKIM dekt alleen de onderste van twee gelijke koppen; een tussenpersoon zet er een boven
    assert nee(_nieuwsbrief(uitschrijfkoppen=(2, 1))) and nee(_nieuwsbrief(uitschrijfkoppen=(1, 2))), "precies een uitschrijfkop"
    assert not nee(_nieuwsbrief(uitschrijfkoppen=(1, 1)))
    assert nee(_nieuwsbrief(van="info@brand.be", van_naam="Brand Verzekeringen")), "verzekering in de naam"
    assert nee(_nieuwsbrief(onderwerp="Uw notaris informeert")), "notaris in het onderwerp"
    assert nee(_nieuwsbrief(van="news@fod.belgium.be")), "overheid"
    assert nee(_nieuwsbrief(), veilig=frozenset({"brand.be"})), "klant: ooit belangrijk of beantwoord"
    assert nee(_nieuwsbrief(), bekend=frozenset({"jan@brand.be"})), "klant: we mailden het domein"
    assert nee(_nieuwsbrief(van="news@nieuws.brand.be"), bekend=frozenset({"jan@brand.be"})), "ook een subdomein"
    assert nee(_nieuwsbrief(), regel="houden"), "Niet opruimen of Terugzetten op /mail"
    assert nee(_nieuwsbrief(), regel="belangrijk")
    assert nee(_nieuwsbrief(van="news@h-architects.be")), "eigen domein"
    assert nee(_nieuwsbrief(van="iemand@gmail.com")), "gratis maildienst"
    for soort in ("hoog", "midden", "actie", "melding", "verdacht"):
        assert nee(_nieuwsbrief(), soort=soort), soort
    assert nee(_nieuwsbrief(), soort="koud", terug=False), "koud alleen van een terugkerende verzender (K4)"
    assert not nee(_nieuwsbrief(), soort="koud", terug=True)
    ikea = _nieuwsbrief(van="noreply@order.email.ikea.com", onderwerp="Je bestelling is verzonden")
    assert postvak.trieer(ikea, eigen)[0] == "melding" and nee(ikea, soort="melding"), "een bestelling nooit (K7)"
    nu = datetime.fromisoformat("2026-10-20T10:00:00+02:00")
    oud, nieuw = {"datum": nu - timedelta(days=10)}, {"datum": nu - timedelta(days=1)}
    assert U.terugkerend([oud, nieuw], nu) and not U.terugkerend([nieuw, nieuw], nu) and not U.terugkerend([oud], nu)


def test_uitschrijven_een_keer_per_afzender_en_knop():
    import uitschrijven as U
    nu = datetime.fromisoformat("2026-10-20T10:00:00+02:00")
    ts = lambda uur: (nu - timedelta(hours=uur)).isoformat()  # noqa: E731
    staat = U.staat_per_sleutel([
        {"gebeurtenis": "a", "van": "a@x.be", "knop_domein": "x.be", "uitslag": "aanvaard", "ts": ts(100)},
        {"gebeurtenis": "b", "van": "b@x.be", "knop_domein": "x.be", "uitslag": "geweigerd", "ts": ts(100)},
        {"gebeurtenis": "c", "van": "c@x.be", "knop_domein": "x.be", "uitslag": "fout", "ts": ts(30)},
        {"gebeurtenis": "d", "van": "d@x.be", "knop_domein": "x.be", "uitslag": "fout", "ts": ts(2)},
        {"gebeurtenis": "e", "van": "e@x.be", "knop_domein": "x.be", "uitslag": "bezig", "ts": ts(2)},
        {"gebeurtenis": "f1", "van": "f@x.be", "knop_domein": "x.be", "uitslag": "fout", "ts": ts(90)},
        {"gebeurtenis": "f2", "van": "f@x.be", "knop_domein": "x.be", "uitslag": "fout", "ts": ts(60)},
        {"gebeurtenis": "f3", "van": "f@x.be", "knop_domein": "x.be", "uitslag": "fout", "ts": ts(30)},
        {"gebeurtenis": "g", "van": "g@x.be", "knop_domein": "x.be", "uitslag": "bezig", "ts": ts(3)},
        {"gebeurtenis": "g", "van": "g@x.be", "knop_domein": "x.be", "uitslag": "aanvaard", "ts": ts(3)}])
    assert not U.mag_poging("a@x.be", "x.be", staat, nu) and not U.mag_poging("b@x.be", "x.be", staat, nu)
    assert U.mag_poging("c@x.be", "x.be", staat, nu), "een fout mag na 24 uur opnieuw"
    assert not U.mag_poging("d@x.be", "x.be", staat, nu), "maar niet binnen 24 uur"
    assert not U.mag_poging("e@x.be", "x.be", staat, nu), "een poging zonder uitslag telt als fout (K5)"
    assert not U.mag_poging("f@x.be", "x.be", staat, nu), "hoogstens drie fouten"
    assert not U.mag_poging("g@x.be", "x.be", staat, nu)
    assert U.mag_poging("a@x.be", "ander.be", staat, nu), "een andere knop van dezelfde afzender is een andere lijst (C5)"


def test_uitschrijven_klant_is_wie_we_in_twee_jaar_mailden_vanuit_elk_postvak():
    import json
    import tempfile
    import uitschrijven as U
    nu = datetime.fromisoformat("2026-10-20T10:00:00+02:00")
    cfg_alles = {"_uitleg": "x", "uitschrijven": {"aan": True},
                 "mail-a": {"postvakken": ["a@h-architects.be"], "antwoord_vanuit": ["mch@h-architects.be"]},
                 "mail-b": {"postvakken": ["b@h-invest.be"], "antwoord_vanuit": []},
                 "mail-prive": {"postvakken": ["p@hotmail.com"]}}
    gevraagd = []

    def koppen(adres, m, sinds=None, maximaal=200, plafond=1000):
        gevraagd.append((adres, m, sinds, plafond))
        return [{"aan": [f"Klant <klant@{adres.split('@')[1]}>"], "cc": []}]
    mac = os.path.join(tempfile.mkdtemp(), "koppen.json")

    def hotmail(dagen=730, gemaakt=nu):
        json.dump({"gemaakt": gemaakt.isoformat(), "verzonden_dagen": dagen, "berichten": [
            {"map": "Sent", "aan": ["Vriend <klant@prive.be>"], "cc": []}, {"map": "INBOX", "aan": ["x@reclame.be"]}]},
            open(mac, "w"))
    hotmail()
    oud_pv, oud_mn = postvak.postvak, postvak.mapnamen
    postvak.postvak = lambda a: {"adres": a, "bron": mac} if "hotmail" in a else {"adres": a}
    postvak.mapnamen = lambda mb: {"inbox", "inbox.sent"}
    try:
        pad = os.path.join(tempfile.mkdtemp(), "ooit.json")
        ooit = U.ooit_gemaild(nu, cfg_alles, koppen, pad)
        assert ooit == {"klant@h-architects.be", "klant@h-invest.be", "klant@prive.be"}, \
            "tweede toets X1: wie Mehdi alleen vanuit hotmail mailde, is ook een klant"
        assert {a for a, *_ in gevraagd} == {"a@h-architects.be", "mch@h-architects.be", "b@h-invest.be"}, \
            "elk postvak van elke wacht en de antwoordpostvakken via de postbus; hotmail uit het bestand van de Mac"
        for kort_of_oud in (dict(dagen=180), dict(gemaakt=nu - timedelta(days=8))):
            hotmail(**kort_of_oud)
            assert U.ooit_gemaild(nu, cfg_alles, koppen, os.path.join(tempfile.mkdtemp(), "h.json")) is None, \
                ("hotmail-bestand zonder twee jaar verzonden post of ouder dan een week: niemand uitschrijven", kort_of_oud)
        hotmail()
        assert all(s == "2024-10-20" and p == U.KLANT_PLAFOND for _, _, s, p in gevraagd), "twee jaar terug"
        gevraagd.clear()
        assert U.ooit_gemaild(nu, cfg_alles, koppen, pad) == ooit and not gevraagd, "een keer per dag gelezen"
        assert json.load(open(pad))["dag"] == "2026-10-20"
        vol = lambda adres, m, sinds=None, maximaal=200, plafond=1000: [{"aan": ["x@y.be"]}] * plafond  # noqa: E731
        assert U.ooit_gemaild(nu, cfg_alles, vol, os.path.join(tempfile.mkdtemp(), "v.json")) is None, "plafond: niet volledig"

        def kapot(*a, **k):
            raise OSError("imap")
        assert U.ooit_gemaild(nu, cfg_alles, kapot, os.path.join(tempfile.mkdtemp(), "k.json")) is None
        postvak.mapnamen = lambda mb: {"inbox"}
        assert U.ooit_gemaild(nu, cfg_alles, koppen, os.path.join(tempfile.mkdtemp(), "g.json")) is None, \
            "geen map Verzonden: niet volledig"
    finally:
        postvak.postvak, postvak.mapnamen = oud_pv, oud_mn


def test_uitschrijven_ronde_logboek_plafond_en_grendels():
    import json
    import socket
    import tempfile
    import uitschrijven as U
    nu = datetime.fromisoformat("2026-10-20T10:00:00+02:00")
    log = os.path.join(tempfile.mkdtemp(), "uit.jsonl")
    # terugkerend: per afzender twee nieuwsbrieven, de eerste ouder dan zeven dagen
    brieven = [_nieuwsbrief(van=f"news{i}@brand.be", message_id=f"<n{i}@brand.be>") for i in range(7)]
    brieven += [_nieuwsbrief(van=f"news{i}@brand.be", message_id=f"<o{i}@brand.be>",
                             datum=datetime.fromisoformat("2026-10-01T10:00:00+02:00")) for i in range(7)]
    gepost, naar_bord = [], []

    class Bord:
        def call(self, pad, data=None):
            if data is None:
                return {"uitschrijvingen": []}
            naar_bord.append(data)
            return {"ok": True}

    def posten(url, ip):
        regels = [json.loads(x) for x in open(log)]
        assert any(r["uitslag"] == "bezig" for r in regels), "de poging staat in het logboek voor de POST"
        gepost.append(url)
        return "aanvaard", 200

    dns = lambda host, poort, proto=None: [(socket.AF_INET, 1, 6, "", ("93.184.216.34", 443))]  # noqa: E731
    cfg = {"postvakken": ["p@h-architects.be"], "eigen_domeinen": ["h-architects.be"]}
    oud_pv, oud_inst = postvak.postvak, U.instellingen
    postvak.postvak = lambda a: {"adres": a, "imap_host": "imap.one.com"}
    U.instellingen = lambda cfg_alles=None: {"aan": True, "per_ronde": 5, "extra_mappen": ["INBOX.Opgeruimd"]}
    try:
        r = postvak._Droog()
        args = dict(lezen=lambda mb, mappen, sinds: brieven, posten=posten, opzoeken=dns, logpad=log,
                    klanten=lambda nu: frozenset())
        geen_klantenlijst = dict(args, klanten=lambda nu: None, logpad=os.path.join(tempfile.mkdtemp(), "k.jsonl"))
        assert U.ronde("mail-proef", cfg, postvak._DroogAgent(), r, nu, frozenset(), frozenset(), {}, True, Bord(),
                       **geen_klantenlijst) == [] and not gepost, "X3: zonder volledige klantenlijst van twee jaar niemand"
        assert U.ronde("mail-proef", cfg, postvak._DroogAgent(), r, nu, frozenset(), frozenset(), {}, True, Bord(),
                       **dict(args, klanten=lambda nu: frozenset({"jan@brand.be"}),
                              logpad=os.path.join(tempfile.mkdtemp(), "j.jsonl"))) == [] and not gepost, \
            "X3: een domein dat we ooit (binnen twee jaar, vanuit elk postvak) mailden, is een klant"
        gedaan = U.ronde("mail-proef", cfg, postvak._DroogAgent(), r, nu, frozenset(), frozenset(), {}, True, Bord(), **args)
        assert len(gedaan) == 5 and len(gepost) == 5, "hoogstens vijf per ronde"
        assert all(g["uitslag"] == "aanvaard" and g["knop_domein"] == "brand.be" for g in gedaan)
        alles = json.dumps(naar_bord) + open(log).read()
        assert "GEHEIM" not in alles and "https://" not in alles, "nooit de URL van de knop, alleen het domein"
        U.ronde("mail-proef", cfg, postvak._DroogAgent(), r, nu, frozenset(), frozenset(), {}, True, Bord(), **args)
        assert len(gepost) == 7, "de volgende ronde de laatste twee, de eerste vijf nooit opnieuw"
        U.ronde("mail-proef", cfg, postvak._DroogAgent(), r, nu, frozenset(), frozenset(), {}, True, Bord(), **args)
        assert len(gepost) == 7
        U.ronde("mail-proef", cfg, postvak._DroogAgent(), r, nu, frozenset(), frozenset(), {}, False, Bord(),
                **dict(args, logpad=os.path.join(tempfile.mkdtemp(), "x.jsonl")))
        assert len(gepost) == 7, "zonder volledig gelezen verzonden post en bord: niets"
        kapot = os.path.join(tempfile.mkdtemp(), "kapot.jsonl")
        open(kapot, "w").write("{niet leesbaar\n")
        U.ronde("mail-proef", cfg, postvak._DroogAgent(), r, nu, frozenset(), frozenset(), {}, True, Bord(), **dict(args, logpad=kapot))
        assert len(gepost) == 7 and any("onleesbaar" in t for t, _ in r.noden), "onleesbaar logboek: stilstaan en melden (K5)"
        # X4, K3: de wacht stopte tussen POST en uitslag; de volgende ronde zet dat als fout 'onderbroken' op het bord
        stop = os.path.join(tempfile.mkdtemp(), "stop.jsonl")
        open(stop, "w").write(json.dumps({"gebeurtenis": "g-stop", "ts": (nu - timedelta(hours=1)).isoformat(), "wacht": "mail-proef",
                                          "van": "x@brand.be", "knop_domein": "brand.be", "uitslag": "bezig"}) + "\n"
                              + json.dumps({"gebeurtenis": "g-nu", "ts": (nu - timedelta(minutes=1)).isoformat(),
                                            "wacht": "mail-proef", "van": "y@brand.be", "knop_domein": "brand.be",
                                            "uitslag": "bezig"}) + "\n")
        naar_bord.clear()
        U.ronde("mail-proef", cfg, postvak._DroogAgent(), r, nu, frozenset(), frozenset(), {}, True, Bord(),
                **dict(args, logpad=stop, klanten=lambda nu: None))
        verstuurd = [x for d in naar_bord for x in d["regels"]]
        assert [(x["gebeurtenis"], x["uitslag"]) for x in verstuurd] == [("g-stop", "fout")] and "onderbroken" in verstuurd[0]["reden"], \
            "een onderbroken poging komt op /mail, ook als er deze ronde niemand uitgeschreven wordt; een poging van net niet"
        assert not U.mag_poging("x@brand.be", "brand.be", U.staat_per_sleutel(U.lees_log(stop)), nu), "en telt als een fout"
        U.instellingen = lambda cfg_alles=None: {"aan": False, "per_ronde": 5, "extra_mappen": []}
        assert U.ronde("mail-proef", cfg, postvak._DroogAgent(), r, nu, frozenset(), frozenset(), {}, True, Bord(),
                       **dict(args, logpad=os.path.join(tempfile.mkdtemp(), "y.jsonl"))) == []
    finally:
        postvak.postvak, U.instellingen = oud_pv, oud_inst
    cfg_echt = U.instellingen(postvak.wachten())
    assert isinstance(cfg_echt["aan"], bool) and cfg_echt["per_ronde"] <= 5, "een schakelaar en een klein plafond"
    assert U.mappen_voor("melodiebvba@gmail.com", {"imap_host": "imap.gmail.com"}, cfg_echt)[-2:] == ["Opgeruimd", "Nieuwsbrieven"]


def test_rommel_naar_opgeruimd_alleen_met_exacte_domeinen():
    """19-10-2026: alleen rommel, met een exacte domeinvergelijking; 'ing.be' zat ooit in valoprojectontwikkeling.be."""
    def r(van, mid, soort="rommel", **k):
        return dict({"van": van, "soort": soort, "map": "INBOX", "message_id": mid, "regel": ""}, **k)
    alle = [r("promo@winkel.be", "<1@w>"), r("promo@winkel.be", "<2@w>"),
            r("news@valoprojectontwikkeling.be", "<3@v>"), r("news@valoprojectontwikkeling.be", "<4@v>"),
            r("news@ing.be", "<5@i>"), r("news@ing.be", "<6@i>"),
            r("eens@alleen.be", "<7@a>"),
            r("deals@bank.be", "<8@b>"), r("deals@bank.be", "<9@b>"), r("x@bank.be", "<10@b>", soort="hoog"),
            r("a@gmail.com", "<11@g>"), r("b@gmail.com", "<12@g>"),
            r("x@h-architects.be", "<13@h>"), r("y@h-architects.be", "<14@h>"),
            r("promo@ander.be", "<15@a>", map="INBOX.Nieuwsbrieven"), r("promo@ander.be", "<16@a>"),
            r("ruis@lijst.be", "<17@l>", regel="ruis"), r("ruis@lijst.be", "<18@l>", regel="ruis"),
            r("nieuws.kbc.be@mail.kbc.be", "<19@k>"), r("info@mail.kbc.be", "<20@k>"),
            r("promo@geenid.be", ""), r("promo@geenid.be", "x")]
    bekend = frozenset({"klant@ing.be"})
    uit = {a["message_id"] for a in postvak.rommel_kandidaten(alle, ("h-architects.be",), bekend, frozenset({"kbc.be"}))}
    assert uit == {"<1@w>", "<2@w>", "<3@v>", "<4@v>", "<16@a>"}, uit  # <15@a> staat al in Nieuwsbrieven, maar telt mee als tweede
    assert postvak.zelfde_domein("mail.kbc.be", ["kbc.be"]) and not postvak.zelfde_domein("mail-kbc.be", ["kbc.be"])
    assert not postvak.zelfde_domein("valoprojectontwikkeling.be", ["ing.be"])
    assert postvak.zelfde_domein("kbc.be", ["news.kbc.be"], beide=True)


def test_rommel_proefweek_en_nooit_verwijderen():
    """De eerste week alleen tonen (tot echt_vanaf), daarna echt; de pagina noemt dezelfde dag. Nooit EXPUNGE of \\Deleted."""
    import re
    cfg = postvak.wachten()
    vanaf = cfg["rommel_opruimen"]["echt_vanaf"]
    assert vanaf >= "2026-10-26", "de proefweek begon op 19-10-2026 en duurt een week"
    assert not postvak.rommel_echt(datetime.fromisoformat("2026-10-25T20:00:00+02:00"), cfg)
    assert postvak.rommel_echt(datetime.fromisoformat(vanaf + "T07:00:00+02:00"), cfg)
    html = open(os.path.join(os.path.dirname(HIER), "mijnagents", "templates", "mail.html"), encoding="utf-8").read()
    d = date.fromisoformat(vanaf)
    assert f"set echt_vanaf = '{d.strftime('%d-%m-%Y')}'" in html, "/mail noemt een andere dag dan mailwachten.json"
    bron = open(os.path.join(HIER, "koppelingen", "postvak.py"), encoding="utf-8").read()
    assert not re.search(r"EXPUNGE|\\\\Deleted|\+FLAGS|\"STORE\"|smtplib", bron), "verplaatsen, nooit verwijderen of markeren"
    assert postvak.verplaats_op_id({"adres": "x@y.be", "schrijven": False}, ["<a@b>"], "INBOX", "INBOX.Opgeruimd") == []
    assert postvak.verplaats_op_id({"adres": "h@hotmail.com", "bron": "/x", "schrijven": True}, ["<a@b>"], "INBOX", "X") == []


def test_mch_antwoordt_ook_vanuit_andere_postvakken():
    """19-10-2026: antwoord_vanuit voor mch@ was leeg; met de draad kan een extra postvak alleen sluiten wat echt beantwoord is."""
    cfg = postvak.wachten()
    assert {"info@h-architects.be", "info@h-invest.be"} <= set(cfg["mail-mch"]["antwoord_vanuit"])


def test_de_mailregisseur_leest_dezelfde_lijst():
    """De Mailregisseur telt wat het bord als open geeft; het 08:00-bericht noemt hetzelfde getal; een oproep houdt zijn
    oude sleutel; bellen alleen op een vast moment; een oproep voor mail die niet meer openstaat, gaat weg."""
    import mail_regisseur as M
    cfg = {"mail-mch": {"firma": "MCH"}, "mail-hinv": {"firma": "HINV"}}
    open_punten = [{"uniek": "mch@h-architects.be:<a>", "wacht": "mail-mch", "soort": "midden", "werkdagen": 3, "stap": "x",
                    "datum_iso": "2026-10-14T10:00:00+02:00", "klaarzet_id": None, "dringend": False},
                   {"uniek": "info@h-invest.be:<b>", "wacht": "mail-hinv", "soort": "hoog", "werkdagen": 1, "stap": "y",
                    "datum_iso": "2026-10-16T10:00:00+02:00", "klaarzet_id": 812, "dringend": True}]
    lijst = M.punten(open_punten, cfg)
    assert [i["firma"] for i in lijst] == ["HINV", "MCH"]
    assert lijst[0]["oproep"] == "mailoproep:812" and lijst[1]["oproep"] == "mailoproep:mch@h-architects.be:<a>"
    klaar = [{"id": 1, "soort": "oproep", "uniek": "mailoproep:812"}, {"id": 2, "soort": "oproep", "uniek": "mailoproep:999"},
             {"id": 3, "soort": "oproep", "uniek": "afspraak:5"}, {"id": 4, "soort": "signaal", "uniek": "mailoproep:7"}]
    assert [i["id"] for i in M.oude_oproepen(lijst, klaar)] == [2]
    assert M.moment(datetime.fromisoformat("2026-10-19T22:00:00+02:00"), {}) == "", "een ronde om 22:00 is geen moment"
    assert M.moment(datetime.fromisoformat("2026-10-19T08:05:00+02:00"), {}) == "08:00"
    assert M.moment(datetime.fromisoformat("2026-10-18T08:05:00+02:00"), {}) == "08:00", "zondag: de update van 08:00"
    assert M.moment(datetime.fromisoformat("2026-10-18T12:35:00+02:00"), {"2026-10-18": {"08:00": "x"}}) == "", "zondag geen 12:30"
    # een gemiste update haal ik in, tot de volgende update of 21:00, en een late ronde belt nooit (Codex-toets 20-10-2026, 1)
    assert M.moment(datetime.fromisoformat("2026-10-19T10:00:00+02:00"), {}) == "08:00"
    assert M.moment(datetime.fromisoformat("2026-10-19T13:00:00+02:00"), {"2026-10-19": {"12:30": "x"}}) == "08:00"
    assert M.moment(datetime.fromisoformat("2026-10-19T20:30:00+02:00"), {"2026-10-19": {"08:00": "x"}}) == "17:00"
    assert M.moment(datetime.fromisoformat("2026-10-19T21:30:00+02:00"), {}) == ""
    assert not M.mag_bellen(datetime.fromisoformat("2026-10-19T10:00:00+02:00"), {}), "een ingehaalde update belt niet"
    assert not M.mag_bellen(datetime.fromisoformat("2026-10-18T08:05:00+02:00"), {}), "in het weekend belt de regisseur niet"
    assert M.mag_bellen(datetime.fromisoformat("2026-10-19T08:05:00+02:00"), {})
    assert not M.mag_bellen(datetime.fromisoformat("2026-10-19T08:05:00+02:00"), {}, forceer=True), "--nu belt nooit"
    assert not M.mag_bellen(datetime.fromisoformat("2026-10-19T18:29:00+02:00"), {}), "18:29 hoort bij 17:00 maar belt niet"
    assert not M.mag_bellen(datetime.fromisoformat("2026-10-19T22:00:00+02:00"), {}, forceer=True)
    bron = open(os.path.join(HIER, "mail_regisseur.py"), encoding="utf-8").read()
    assert 'x.get("dringend") and echt' in bron and "klaargezet_voor(NAAM" not in bron
    dag = open(os.path.join(HIER, "dagbundelaar.py"), encoding="utf-8").read()
    assert '"mail-regisseur" in (it.get("van"), it.get("voor"))' in dag, "de Dagbundelaar laat mail liggen"


def test_de_update_twee_keer_per_dag():
    """Mehdi, 20-10-2026: "ik wil update 2 keer per dag ... de systeem en niet elke individuele mails ... we focusen nu op
    mch, mehdichegini@hotmail.com, melodie". Om 08:00 en 17:00, elke dag; de cijfers van de focus uit /api/mail/stand;
    een wacht die niet werkt, staat erin; de sleutel heeft geen aantal (N10); nooit het woord stil (dat belt)."""
    import mail_regisseur as M
    assert M.UPDATES == ("08:00", "17:00")
    za = datetime.fromisoformat("2026-10-24T17:05:00+02:00")
    assert M.vorige_update(za, "17:00") == datetime.fromisoformat("2026-10-24T08:00:00+02:00")
    assert M.vorige_update(datetime.fromisoformat("2026-10-26T08:05:00+01:00"), "08:00").strftime("%d %H:%M") == "25 17:00"
    nu = datetime.fromisoformat("2026-10-20T17:05:00+02:00")
    focus = ["mch@h-architects.be", "mehdichegini@hotmail.com", "melodiebvba@gmail.com"]
    tel = lambda w, n, o: {"wacht": w, "binnen": n, "belangrijk": 1, "ruis": 2, "gesorteerd": 1, "uitgeschreven": 0,  # noqa: E731
                           "open": o, "open_belangrijk": 0, "lang": 0, "loopt": 1, "vast": 1 if w == "mail-mch" else 0}
    stand = {"focus": focus, "postvakken": {"mch@h-architects.be": tel("mail-mch", 10, 4),
                                            "mehdichegini@hotmail.com": tel("mail-prive", 3, 2),
                                            "melodiebvba@gmail.com": tel("mail-melo", 2, 1),
                                            "info@h-invest.be": tel("mail-hinv", 5, 7)},
             "wachten": {"mail-mch": {"status": "klaar", "laatste_ronde": "2026-10-20T15:00:00+00:00", "noden": []},
                         "mail-prive": {"status": "waakt", "laatste_ronde": "2026-10-20T15:00:00+00:00",
                                        "noden": ["De kopie van hotmail van de Mac is niet vers"]},
                         "mail-melo": {"status": "klaar", "laatste_ronde": "2026-10-20T09:00:00+00:00", "noden": []}}}
    storing = M.storingen(stand, nu)
    assert set(storing) == {"mehdichegini@hotmail.com", "melodiebvba@gmail.com"}, storing
    titel = M.titel_update("17:00", stand, storing)
    assert titel.startswith("Mail 17:00: open mch@ 4, hotmail 2, Melodie 1; loopt 3 (1 vast); storing hotmail, Melodie"), titel
    lang = M.titel_update("17:00", dict(stand, postvakken={a: dict(x, open=123, loopt=99) for a, x in stand["postvakken"].items()}),
                          {a: ["x"] for a in focus})
    assert len(lang) <= 110 and "; storing mch@, hotmail, Melodie" in lang, "grote getallen: de storing valt nooit weg"
    assert len(titel) <= 110 and "stil" not in titel.lower()
    inhoud = M.inhoud_update("17:00", stand, storing, M.vorige_update(nu, "17:00"))
    assert "info@ H-Invest 7 op te volgen" in inhoud and "niet vers" in inhoud and "stil" not in inhoud.lower()
    assert "1 lopen nog tot iemand Opgelost klikt" in inhoud, "opgevolgd tot opgelost (20-10-2026)"
    bron = open(os.path.join(HIER, "mail_regisseur.py"), encoding="utf-8").read()
    assert '"uniek": f"mailupdate:{vandaag}:{m}"' in bron and "if m in UPDATES:" in bron
    assert 'staat["_laatste_update"] = nu.isoformat()' in bron, "de volgende update telt vanaf de vorige geslaagde"
    # Codex-toets f750f0c: dezelfde grens voor telling en bewaring (7), geen limiet van drie dagen (8), een mislukte update
    # wordt een keer gemeld en later ingehaald (10), een weer open verlopen bericht belt nooit (6)
    assert '"tot": nu.isoformat()' in bron and "timedelta(days=3) < sinds" not in bron
    assert ':fout"' in bron and "if not update_mislukt:" in bron
    assert 'x.get("opvolging") != "verlopen"' in bron
    assert "onderwerp" not in bron[bron.index("def inhoud_update"):bron.index("def oude_oproepen")], "geen losse mails in de update"
    stand["wachten"]["mail-mch"]["actief"] = 0
    assert "de wacht staat uit" in M.storingen(stand, nu)["mch@h-architects.be"]


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
    assert t("info@kine-voorbeeld.test", "HERINNERING - Uw afspraak bij KINEVOORBEELD - woensdag 23/09", automatisch=True)[0] == "melding"
    assert t("alle.ouders@sk.sgarchipel.be", "Nieuwsbrief kinderkuren", lijst=True)[0] in ("melding", "rommel")
    bekend = frozenset({"klm_royal_dutch_airlines@infos-klm.com", "stadsarchief@antwerpen.be"})
    for van, ond in (("klm_royal_dutch_airlines@infos-klm.com", "Uw boeking is bevestigd"),
                     ("klm_royal_dutch_airlines@infos-klm.com", "Check-in is begonnen!"),
                     ("stadsarchief@antwerpen.be", "Uw download van inventarisnummer 956#595 staat klaar")):
        assert postvak.trieer(kop(van, ond), EIGEN, bekend)[0] == "melding", (van, ond)  # 19-10-2026, droge ronde mch@


def test_wat_op_25_september_terecht_doorkwam_blijft():
    t = lambda van, ond, naam="", **k: postvak.trieer(dict(kop(van, ond, naam), **k), EIGEN)  # noqa: E731
    assert t("info-kbc@mail-kbc.be", "Je hebt info over een achterstal/overschrijding ontvangen voor H-INVEST BV",
             automatisch=True)[0] == "actie"
    assert t("daniel.renard@verz.kbc.be", "72971400 - PATRIMONIUMPOLIS HANDEL - herinnering premiebetaling")[0] == "hoog"
    assert t("an.berghmans@notaris.be", "RE: Verkoop Plantin en Moretuslei 6", "Notaris An BERGHMANS")[0] == "hoog"
    assert t("dussart@dinconsulting.be", "Afstemming intercompany Qoppa/H-Architects", "Nadine Dussart - Din Consulting")[0] == "hoog"


def test_de_beslissing_van_mehdi_gaat_voor_de_regels():
    """26-09-2026: per afzender belangrijk, ruis of opruimen op het maildashboard."""
    regels = {("info@h-architects.be", "@oase.sr"): "ruis", ("*", "nadine@dinconsulting.be"): "belangrijk",
              ("info@h-architects.be", "nadine@dinconsulting.be"): "ruis"}
    assert postvak.regel_voor(regels, "info@h-architects.be", "info@oase.sr") == "ruis"
    assert postvak.regel_voor(regels, "mch@h-architects.be", "info@oase.sr") == ""
    assert postvak.regel_voor(regels, "mch@h-architects.be", "Nadine@DinConsulting.be") == "belangrijk"
    assert postvak.regel_voor(regels, "info@h-architects.be", "nadine@dinconsulting.be") == "ruis", "dit postvak gaat voor *"
    assert postvak.trieer(kop("info@lamella-mail.com", "Word dealer"), EIGEN, regel="belangrijk")[0] == "hoog"
    assert postvak.trieer(kop("vincent@verz.kbc.be", "Schorsing"), EIGEN, regel="opruimen")[0] == "rommel"
    assert postvak.trieer(kop("x@gmail.com", "Action requise", "My MINFIN"), EIGEN, regel="belangrijk")[0] == "verdacht"


def test_opruimen_raakt_alleen_de_juiste_afzender():
    assert postvak.past("info@kbc.be", "@kbc.be") and postvak.past("x@mail.kbc.be", "@kbc.be")
    assert not postvak.past("x@mail-kbc.be", "@kbc.be"), "een ander domein dat op kbc.be eindigt"
    assert postvak.past("Info@Oase.sr", "info@oase.sr") and not postvak.past("info2@oase.sr", "info@oase.sr")
    assert postvak.opruimen({"adres": "x@y.be", "schrijven": False}, "@kbc.be") == [], "alleen-lezen: niets verplaatsen"
    assert postvak.opruimen({"adres": "h@hotmail.com", "bron": "/x", "schrijven": True}, "@kbc.be") == [], "hotmail: kan niet"
    assert postvak.opruimmap({"imap_host": "imap.gmail.com"}) == "Opgeruimd"
    assert postvak.opruimmap({"imap_host": "imap.one.com"}) == "INBOX.Opgeruimd"


def test_dringend_is_smal():
    """26-09-2026: bij dringende mail laat De Mailregisseur De Bode bellen. Alleen dit, anders wordt bellen ruis."""
    d = postvak.DRINGEND.search
    for ja in ("Ingebrekestelling dossier 46025", "Dossier 2601E6129 - Gerechtsdeurwaarders", "Laatste aanmaning factuur 12",
               "Schorsing polis Kangoo", "Fwd: 28255 Mehdi Chegini / Orde van Architecten (tuchtprocedure 2)",
               "Your team's Dropbox account is paused", "Contrat 154011294: Mise en demeure"):
        assert d(ja), ja
    assert d("Aankondiging afsluiting elektriciteit Fluvius")
    for nee in ("Herinnering premiebetaling", "Factuur 2026-12", "Openstaande bijdragenota 2026", "Re: Offerte koppeling",
                "H-architects - jaarafsluiting 31/12/2025"):
        assert not d(nee), nee


def test_sorteren_door_de_wacht():
    """26-09-2026: de wacht sorteert zijn postvak elke ronde volgens mailregels/regels_<alias>.txt."""
    for adres in ("info@h-invest.be", "info@h-architects.be", "mch@h-architects.be", "melodiebvba@gmail.com"):
        pad = postvak.sorteerregels_van(adres)
        assert pad and os.path.exists(pad), adres
    assert postvak.sorteer({"adres": "x@y.be", "schrijven": False}, postvak.sorteerregels_van("info@h-invest.be"),
                           datetime.now(postvak.BRUSSEL)) == [], "zonder schrijfrecht verplaatst de wacht niets"
    werk = open(os.path.join(HIER, "koppelingen", "postvak.py"), encoding="utf-8").read()
    assert 'any(past(rij["addr"], h) for h in houden)' in werk and "sorteer(mb, pad, nu, houden=houden)" in werk, \
        "wat Mehdi terugzette, zet de sortering niet opnieuw in Opgeruimd"
    assert postvak.gmailnaam({"imap_host": "imap.gmail.com"}, "INBOX.Bank en verzekering") == "Bank en verzekering"
    assert postvak.gmailnaam({"imap_host": "imap.gmail.com"}, "INBOX.Archief.2025") == "Archief/2025"
    assert postvak.gmailnaam({"imap_host": "imap.one.com"}, "INBOX.Opgeruimd") == "INBOX.Opgeruimd"
    bode = open(os.path.join(HIER, "bode.py"), encoding="utf-8").read()
    assert '"oproep")' in bode and 'it["soort"] == "oproep"' in bode, "De Bode belt bij een oproep"
    regisseur = open(os.path.join(HIER, "mail_regisseur.py"), encoding="utf-8").read()
    assert '"soort": "oproep"' in regisseur and '"uniek": i["oproep"]' in regisseur, "een oproep per bericht"


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
    assert wat["opzeggen verzekering AXA"] == date(2026, 12, 30), wat
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


def test_onderhoudstermijn_komt_uit_de_laatste_factuur():
    """25-09-2026: 'onderhoud 2HHE117 verlopen' bleef staan uit een vaste datum, terwijl Auto 5 hem op 12-08-2026 onderhield."""
    v = {"plaat": "2HHE117", "merk_model": "Opel Astra", "status": "in gebruik", "gebruik": "Mehdi", "mappen": ["/x"],
         "onderhoud_volgend": "2025-07-10", "keuring_tot": "2027-01-01", "verzekering": {"tot": "2027-07-16"},
         "fabrikant": {"interval_km": 30000, "interval_maanden": 12},
         "onderhoud": [{"datum": "2026-08-12", "soort": "onderhoud", "km": 147788, "omschrijving": "olie en filters"}]}
    reg = {"voertuigen": [v]}
    lijst, _ = W.termijnen(reg, date(2026, 9, 25), [], W.vooruitblik(reg, date(2026, 9, 25)))
    ond = [x for x in lijst if x[1] == "onderhoud"]
    assert ond and ond[0][2] == date(2027, 8, 12), ond


def test_suriname_krijgt_geen_belgische_keuring():
    v = {"plaat": "1YLG530", "merk_model": "Suzuki Swift", "status": "in gebruik", "land": "Suriname", "mappen": ["/x"]}
    lijst, onbekend = W.termijnen({"voertuigen": [v]}, date(2026, 9, 25), [])
    assert not [x for x in lijst if x[1] in ("keuring", "groene kaart")] and not onbekend


def test_bouwjaar_uit_het_chassisnummer():
    assert W.bouwjaar_uit_vin("WF0FXXTTRFMA13765") == 2021   # 2BAS423, ingeschreven 10-09-2021
    assert W.bouwjaar_uit_vin("WF0ZXXTTGZLS08891") == 2020   # 2ACH377, gebouwd 2020, ingeschreven 02-2021
    assert W.bouwjaar_uit_vin("W0VBF8EG3H8101077") == 2017   # 2HHE117, Astra modeljaar 2017
    assert W.bouwjaar_uit_vin("VR7EDYHZ4SJ858741") is None   # Citroën codeert het jaar niet vast: nooit gokken


def test_kosten_per_jaar_en_per_km():
    v = {"plaat": "X", "status": "in gebruik", "leasing": {"maandbedrag": "414,57 excl. btw = 501,63 incl. btw", "start": "2025-11-21", "einde": "2026-02-21"},
         "onderhoud": [{"datum": "2026-01-10", "soort": "herstelling", "bedrag": "1.000,00"}, {"datum": "2026-02-01", "soort": "onderhoud", "bedrag": "2.000 SRD"}],
         "km": [{"datum": "2025-12-01", "km": 100000}, {"datum": "2026-12-31", "km": 130000}]}
    k = W.kosten({"voertuigen": [v]}, [], date(2026, 12, 31))["X"]
    assert k["2025"]["munt"]["EUR"]["financiering"] == round(501.63 * 2)
    assert k["2026"]["munt"]["EUR"] == {"onderhoud en herstel": 1000, "financiering": round(501.63 * 2)}
    assert k["2026"]["munt"]["SRD"] == {"onderhoud en herstel": 2000}, "SRD nooit bij EUR"
    assert k["2026"]["km_zeker"] and 27000 < k["2026"]["km"] < 28000, k["2026"]  # vanaf 1 januari, niet vanaf de eerste stand
    v["onderhoud"].append({"datum": "2026-03-01", "soort": "offerte", "bedrag": "899,34"})
    assert "andere" not in W.kosten({"voertuigen": [v]}, [], date(2026, 12, 31))["X"]["2026"]["munt"]["EUR"], "een offerte is geen kost"


def test_bedragen_lezen():
    assert W._bedrag("3036,49") == 3036.49, "zonder duizendtalpunt werd dit 303"
    assert W._bedrag("1.379,60") == 1379.60 and W._bedrag("2.000 SRD") == 2000 and W._bedrag("414,57 excl.") == 414.57
    assert W._incl("414,57 excl. btw = 501,63 incl. btw") == 501.63
    v = {"plaat": "S", "status": "in gebruik", "onderhoud": [{"datum": "2026-09-11", "soort": "herstelling", "bedrag": "OFFERTE: 626,57 excl. btw; niet besteld"}]}
    assert W.kosten({"voertuigen": [v]}, [], date(2026, 12, 31))["S"] == {}, "een offerte als herstelling telt ook niet"


def test_boekhouding_gaat_voor_en_telt_niet_dubbel():
    v = {"plaat": "B", "status": "in gebruik", "leasing": {"maandbedrag": "100,00 incl.", "start": "2025-01-01", "einde": "2025-12-31"},
         "boekingen": [{"datum": "2025-03-01", "soort": "leasing", "excl": "1000.00"}, {"datum": "2025-05-01", "soort": "andere", "excl": "53.00", "omschrijving": "GAS-boete"},
                       {"datum": "2025-06-01", "soort": "aankoop", "excl": "15000.00"}],
         "onderhoud": [{"datum": "2025-04-01", "soort": "onderhoud", "bedrag": "300,00"}]}
    k = W.kosten({"voertuigen": [v]}, [], date(2025, 12, 31))["B"]["2025"]
    e = k["munt"]["EUR"]
    assert e["financiering"] == 1000, "de boekhouding gaat voor op maandbedrag maal maanden"
    assert e["boetes"] == 53 and e["onderhoud en herstel"] == 300
    assert k["totaal_eur"] == 1353, "een aankoop telt niet als jaarkost"


def test_interne_huur_en_dubbele_factuur_tellen_niet():
    v = {"plaat": "I", "status": "in gebruik", "boekingen": [
        {"datum": "2024-02-05", "soort": "leasing", "excl": "363.69", "leverancier": "KBC Bank", "factuurnummer": "A1"},
        {"datum": "2024-02-06", "soort": "leasing", "excl": "650.00", "leverancier": "H-Invest BV", "factuurnummer": "26001"},
        {"datum": "2024-03-01", "soort": "onderhoud", "excl": "400.49", "leverancier": "Hac Driessen", "factuurnummer": "F9"},
        {"datum": "2024-03-01", "soort": "onderhoud", "excl": "400.49", "leverancier": "Hac Driessen", "factuurnummer": "F9"}]}
    e = W.kosten({"voertuigen": [v]}, [], date(2024, 12, 31))["I"]["2024"]["munt"]["EUR"]
    assert e == {"financiering": 364, "onderhoud en herstel": 400}, e


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

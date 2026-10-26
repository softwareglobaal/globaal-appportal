"""Grendel op de serverroute van de hotmail-koppen (driehoeksoverleg 26-10-2026, 3-0: route B, X1-X5).

Tot 26-10-2026 maakte de Mac koppen.json uit de index van Mail; onder launchd viel dat sinds 26-09 stil op 'authorization
denied'. Nu leest koppelingen/hotmail_lezer.py hotmail in de postcontainer en zet koppelingen/hotmail_server.py het
bestand. Deze test faalt zodra de lezer andere mappen leest dan de Mac (X2), automatisch of lijst anders bepaalt (X3),
de termijnen wijzigt (X4), iets anders dan BODY.PEEK vraagt, een bericht van Outlook stil laat vallen, of het vorige
bestand overschrijft na een onvolledige lezing (X5). Draait zonder netwerk en zonder postbus.
"""
import json
import os
import re
import sys
import tempfile
import types
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "post"))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
# post/config.py leest het mailboxenbestand (en vraagt yaml): de test geeft een eigen postbus met alleen hotmail.
sys.modules["config"] = types.SimpleNamespace(alles=lambda: ([{"adres": "proef@hotmail.test"}], []))
import hotmail_lezer as L  # noqa: E402
import hotmail_server as S  # noqa: E402
import postvak  # noqa: E402

NU = datetime(2026, 10, 26, 18, 0, tzinfo=timezone.utc)
ADRES = "proef@hotmail.test"


def kop(van, onderwerp, datum, mid, extra=""):
    return (f"From: {van}\r\nTo: Mehdi <{ADRES}>\r\nSubject: {onderwerp}\r\nDate: {datum}\r\nMessage-ID: <{mid}>\r\n"
            f"{extra}\r\n").encode()


# De mappen zoals Outlook.com ze over IMAP geeft: (attributen, naam, {uid: koppen}).
MAPPEN = [
    (("\\HasNoChildren",), "Inbox", {7: (kop("Klant <k@klant.test>", "Offerte", "Mon, 19 Oct 2026 10:00:00 +0200", "a@k"),
                                          "19-Oct-2026 08:01:30 +0000")}),
    (("\\HasChildren",), "Projecten", {3: kop("Aannemer <a@bouw.test>", "Planning", "Tue, 20 Oct 2026 09:00:00 +0200", "b@b",
                                               "Auto-Submitted: auto-generated\r\n")}),
    (("\\HasNoChildren",), "Nieuws", {9: kop("Blad <nieuws@blad.test>", "Deze week", "Thu, 22 Oct 2026 07:00:00 +0000", "g@b",
                                             "Precedence: Bulk \r\nList-Unsubscribe: <https://b/u>\r\n")}),
    (("\\HasNoChildren", "\\Sent"), "Sent", {5: kop(f"Mehdi <{ADRES}>", "Re: Offerte", "Wed, 21 Oct 2026 08:00:00 +0200",
                                                     "c@h", "In-Reply-To: <a@k>\r\nReferences: <x@y> <a@k>\r\n"
                                                     + "Cc: " + ", ".join(f"Lid {i} <lid{i}@groep.test>" for i in range(21))
                                                     + "\r\nBcc: Stil <stil@klant.test>\r\n")}),
    (("\\HasNoChildren", "\\Trash"), "Deleted", {1: kop("x@x.test", "weg", "Mon, 19 Oct 2026 10:00:00 +0200", "d@x")}),
    (("\\HasNoChildren", "\\Junk"), "Junk", {1: kop("x@x.test", "spam", "Mon, 19 Oct 2026 10:00:00 +0200", "e@x")}),
    (("\\HasNoChildren",), "Drafts", {1: kop("x@x.test", "concept", "Mon, 19 Oct 2026 10:00:00 +0200", "h@x")}),
    (("\\HasNoChildren",), "Archive/2025", {1: kop("x@x.test", "oud", "Mon, 19 Oct 2026 10:00:00 +0200", "f@x")}),
    (("\\HasNoChildren",), "Conversation History", {1: kop("x@x.test", "chat", "Mon, 19 Oct 2026 10:00:00 +0200", "i@x")}),
    (("\\Noselect", "\\HasChildren"), "Groep", {}),
]


class NepImap:
    """Een IMAP-sessie zonder netwerk. Houdt elke opdracht bij; Outlook-stijl: de UID staat NA het letterlijke blok."""

    def __init__(self, mappen, faal=None):
        self.mappen = {naam: (attr, berichten) for attr, naam, berichten in mappen}
        self.faal, self.huidig, self.opdrachten = faal, None, []

    def list(self):
        return "OK", [f'({" ".join(attr)}) "/" "{naam}"'.encode() for naam, (attr, _) in self.mappen.items()]

    def select(self, naam, readonly=False):
        self.opdrachten.append(("SELECT", naam, readonly))
        self.huidig = naam.strip('"')
        return "OK", [str(len(self.mappen[self.huidig][1])).encode()]

    def uid(self, opdracht, *args):
        self.opdrachten.append((opdracht,) + args)
        berichten = self.mappen[self.huidig][1]
        if opdracht == "SEARCH":
            return "OK", [" ".join(str(u) for u in berichten).encode()]
        if opdracht == "FETCH":
            if self.faal == self.huidig:
                return "NO", [b"server weigert"]
            uit = []
            for u in args[0].split(","):
                ruw, ontvangen = berichten[int(u)] if isinstance(berichten[int(u)], tuple) else (berichten[int(u)], None)
                na = f' INTERNALDATE "{ontvangen}"' if ontvangen else ""
                uit += [(b"1 (BODY[HEADER.FIELDS (...)] {100}", ruw), f"{na} UID {u})".encode()]
            return "OK", uit
        raise AssertionError(f"onverwachte opdracht {opdracht}")


def lees_met(nep):
    class Sessie:
        def __init__(self, mb):
            pass

        def __enter__(self):
            return nep

        def __exit__(self, *a):
            return False
    oud = L.imapbron._Sessie
    L.imapbron._Sessie = Sessie
    os.environ["LEES"] = json.dumps({"adres": ADRES, "vandaag": "2026-10-26", "binnen_dagen": 30, "verzonden_dagen": 730})
    try:
        return L.main()
    finally:
        L.imapbron._Sessie = oud


def test_mappen_zoals_de_mac():
    nep = NepImap(MAPPEN)
    d = lees_met(nep)
    assert d["fouten"] == [], d["fouten"]
    assert {n: m["soort"] for n, m in d["mappen"].items()} == \
        {"Inbox": "INBOX", "Projecten": "INBOX", "Nieuws": "INBOX", "Sent": "Sent"}, d["mappen"]
    assert [b["uid"] for b in d["berichten"] if b["map"] == "Sent"] == ["Sent/5"]


def test_termijnen_30_en_730_dagen():
    nep = NepImap(MAPPEN)
    lees_met(nep)
    sinds = {}
    for o in nep.opdrachten:
        if o[0] == "SELECT":
            huidig = o[1].strip('"')
        elif o[0] == "SEARCH":
            sinds[huidig] = o[o.index(b"SINCE") + 1]
    assert sinds["Inbox"] == sinds["Projecten"] == b"26-Sep-2026", sinds
    assert sinds["Sent"] == b"26-Oct-2024", sinds


def test_alleen_lezen_en_peek():
    nep = NepImap(MAPPEN)
    lees_met(nep)
    assert all(o[2] is True for o in nep.opdrachten if o[0] == "SELECT"), "elke map read-only geselecteerd"
    assert {o[0] for o in nep.opdrachten} == {"SELECT", "SEARCH", "FETCH"}, "nooit STORE, MOVE, COPY of EXPUNGE"
    for o in nep.opdrachten:
        if o[0] == "FETCH":
            assert "BODY.PEEK[HEADER.FIELDS" in o[2] and "BODY[" not in o[2].replace("BODY.PEEK[", ""), o[2]
            for veld in ("AUTO-SUBMITTED", "PRECEDENCE", "LIST-ID", "LIST-UNSUBSCRIBE", "IN-REPLY-TO", "REFERENCES"):
                assert veld in o[2], veld


def test_outlook_uid_na_het_blok_valt_niet_weg():
    d = lees_met(NepImap(MAPPEN))
    assert len(d["berichten"]) == 4 and not any(b["uid"].endswith("/?") for b in d["berichten"]), d["berichten"]


def test_automatisch_lijst_en_draad():
    b = {x["onderwerp"]: x for x in lees_met(NepImap(MAPPEN))["berichten"]}
    assert not b["Offerte"]["automatisch"] and not b["Offerte"]["lijst"]
    assert b["Planning"]["automatisch"] and not b["Planning"]["lijst"], "Auto-Submitted anders dan no"
    assert b["Deze week"]["automatisch"] and b["Deze week"]["lijst"], "Precedence bulk (hoofdletters, spatie) en List-Unsubscribe"
    s = b["Re: Offerte"]
    assert s["in_antwoord_op"] == "<a@k>" and s["verwijzingen"] == ["<x@y>", "<a@k>"] and s["message_id"] == "<c@h>"
    assert b["Offerte"]["datum"] == "2026-10-19T08:01:30+00:00", "de ontvangsttijd (INTERNALDATE), zoals de Mac"
    assert b["Planning"]["datum"] == "2026-10-20T07:00:00+00:00", "zonder INTERNALDATE de Date-kop, in UTC"
    assert len(s["cc"]) == 21 and "Stil <stil@klant.test>" in s["aan"], "alle ontvangers, ook voorbij twintig, en de Bcc"
    assert b["Offerte"]["van"] == "k@klant.test" and b["Offerte"]["van_naam"] == "Klant"


def test_postvak_leest_het_bestand_en_ziet_het_antwoord():
    doel = os.path.join(tempfile.mkdtemp(), "hotmail", "koppen.json")
    nep = NepImap(MAPPEN)
    regel = S.ververs(ADRES, doel, NU, voer=lambda *a, **k: _uitvoer(lees_met(nep)))
    assert "3 binnen" in regel and "1 verzonden" in regel, regel
    d = json.load(open(doel))
    assert d["verzonden_dagen"] == 730 and d["adres"] == ADRES and d["bron"] == "server"
    mb = {"adres": ADRES, "bron": doel}
    assert 0 <= postvak.bron_uren_oud(mb, NU) < 0.01
    binnen, verzonden = postvak.uit_bestand(doel, "INBOX"), postvak.uit_bestand(doel, "Sent")
    assert [b["onderwerp"] for b in binnen] == ["Deze week", "Planning", "Offerte"], "nieuwste eerst"
    assert postvak.wie_is(binnen[-1]) & postvak.antwoordt_op(verzonden[0]), "het antwoord sluit de offerte via de draad"
    assert postvak.wie_is(binnen[-1]) <= postvak.in_draad(verzonden[0])


def test_bericht_zonder_uid_of_datum_maakt_de_map_onvolledig():
    zonder_datum = [(("\\HasNoChildren",), "Inbox", {7: b"From: x@x.test\r\nSubject: geen datum\r\n\r\n"})]
    d = lees_met(NepImap(MAPPEN[3:4] + zonder_datum))
    assert d["fouten"] and "Inbox" in d["fouten"][0], d["fouten"]


def test_klantenlijst_alleen_uit_een_verse_kopie():
    import uitschrijven as U
    doel = os.path.join(tempfile.mkdtemp(), "koppen.json")
    nep = NepImap(MAPPEN)
    S.ververs(ADRES, doel, NU, voer=lambda *a, **k: _uitvoer(lees_met(nep)))
    oud_pv = postvak.postvak
    postvak.postvak = lambda a: {"adres": a, "bron": doel}
    try:
        cfg = {"mail-prive": {"postvakken": [ADRES]}}
        klanten = U.ooit_gemaild(NU, cfg, None, os.path.join(tempfile.mkdtemp(), "k.json"))
        assert {"stil@klant.test", "lid0@groep.test", "lid20@groep.test"} <= klanten, klanten
        laat = NU.replace(hour=22)
        assert U.ooit_gemaild(laat, cfg, None, os.path.join(tempfile.mkdtemp(), "k.json")) is None, \
            "vier uur oud: niemand uitschrijven"
    finally:
        postvak.postvak = oud_pv


def test_vorig_bestand_blijft_bij_een_fout():
    doel = os.path.join(tempfile.mkdtemp(), "koppen.json")
    json.dump({"gemaakt": "2026-10-26T15:00:00+00:00", "berichten": []}, open(doel, "w"))
    for d, reden in ((lees_met(NepImap(MAPPEN, faal="Projecten")), "een map faalt"),
                     ({"berichten": [{"map": "INBOX"}], "fouten": [], "mappen": {}}, "geen verzonden post"),
                     (None, "docker exec faalt (bv. verlopen token)")):
        try:
            S.ververs(ADRES, doel, NU, voer=lambda *a, **k: _uitvoer(d))
            raise AssertionError(f"geen fout bij: {reden}")
        except RuntimeError:
            pass
        assert json.load(open(doel))["gemaakt"] == "2026-10-26T15:00:00+00:00", reden
        assert os.listdir(os.path.dirname(doel)) == ["koppen.json"], (reden, "geen tijdelijk bestand achtergelaten")


def test_het_adres_staat_alleen_in_mailwachten_json():
    adres, pad = S.bron()
    assert postvak.wachten()["bronnen"][adres] == S.BESTAND and pad == os.path.join(postvak.DATA, S.BESTAND)


def test_mailwacht_schrijft_nooit_in_een_postvak_met_bron():
    mb = {"adres": ADRES, "bron": "/tmp/koppen.json", "schrijven": True}
    assert postvak.mapnamen(mb) is None


class _uitvoer:
    def __init__(self, d):
        self.returncode = 1 if d is None else 0
        self.stdout = b"" if d is None else json.dumps(d).encode()
        self.stderr = b"Error: token verlopen" if d is None else b""


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

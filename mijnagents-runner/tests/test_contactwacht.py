"""Grendels op De Contactwacht: de contactcodes komen uit organisatie.globaal.be.

Afspraak van 29-09-2026 (Mehdi): een firma heeft twee codes, de firmacode van vier
letters en de contactcode van twee, en beide staan in kern.firma (migratie 175). De
Contactwacht houdt zelf geen lijst bij. Deze tests laten het falen als iemand de codes
toch weer in de agent zet, of als de agent een regel die nog niet bevestigd is stil
laat vallen. Verzonnen namen en codes; geen netwerk, geen database.

Draaien, zonder pytest:   python3 mijnagents-runner/tests/test_contactwacht.py
"""
import json
import os
import sqlite3
import sys
import tempfile
import time

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import contactwacht as C  # noqa: E402
import organisatie as O  # noqa: E402


def index(namen):
    """Een nagebootste index van de contactsync: (naam, status)."""
    pad = os.path.join(tempfile.mkdtemp(), "sync.db")
    con = sqlite3.connect(pad)
    con.execute("create table contact_details (display_name text, status text)")
    con.executemany("insert into contact_details values (?, ?)", namen)
    con.commit()
    con.close()
    return pad


class Ronde:
    """Vervangt de ronde van het bord: onthoudt bronnen, noden en het detail."""
    def __init__(self):
        self.bronnen, self.noden, self.detail = {}, [], ""

    def bron(self, naam, inhoud):
        self.bronnen[naam] = inhoud

    def nood(self, tekst, wie="mehdi"):
        self.noden.append((tekst, wie))


def met(codes, regel, pad):
    """Een ronde met nagebootste codes uit organisatie en een nagebootste bronregel."""
    oud = (O.contactcodes, O.bronregel, C.SYNC_DB)
    O.contactcodes = lambda maximum_uren=24: dict(codes)
    O.bronregel = lambda sleutel: regel
    C.SYNC_DB = pad
    try:
        r = Ronde()
        C.werk(r)
        return r
    finally:
        O.contactcodes, O.bronregel, C.SYNC_DB = oud


def test_geen_eigen_lijst_met_codes_in_de_agent():
    assert "|" not in C.DOSSIER.pattern, "de dossierregex draagt weer een eigen lijst met firmacodes"
    with open(os.path.join(HIER, "contactwacht.py"), encoding="utf-8") as f:
        bron = f.read()
    assert '"HA"' not in bron and "'HA'" not in bron, "contactwacht.py noemt zelf een contactcode"


def test_codes_komen_uit_organisatie():
    pad = index([("K QQ1234 Jan Proef", "actief"), ("P HA5609 Sarah Proef", "actief")])
    r = met({"QQ": "QQQQ"}, {"status": "besloten"}, pad)
    assert r.bronnen["organisatie-contactcodes"] == {"QQ": "QQQQ"}
    assert "1 in de nieuwe vorm" in r.detail, r.detail
    assert "1 met een dossiercode van een firma die niet" in r.detail, r.detail
    assert any("niet in organisatie.globaal.be staat" in t for t, _ in r.noden)


def test_archief_telt_niet_mee():
    t = C.meet(index([("K QQ1234 Jan Proef", "actief"), ("[ARCHIEF] K QQ1111 Weg", "actief"),
                      ("K QQ2222 Oud", "gearchiveerd"), ("KL H-A Piet Proef", None)]), {"QQ": "QQQQ"})
    assert t == {"actief": 2, "nieuwe_vorm": 1, "onbekende_code": 0, "met_h_a": 1, "met_kl": 1}, t


def test_zonder_codes_geen_oordeel_wel_een_nood():
    pad = index([("P HA5609 Sarah Proef", "actief")])
    r = met({}, {"status": "besloten"}, pad)
    assert "0 met een dossiercode" in r.detail, r.detail
    assert ("De contactcodes zijn niet leesbaar uit organisatie.globaal.be", "claude-code") in r.noden


def test_nood_blijft_tot_de_regel_besloten_is():
    pad = index([("K QQ1234 Jan Proef", "actief")])
    open_ = met({"QQ": "QQQQ"}, {"status": "voorstel"}, pad)
    dicht = met({"QQ": "QQQQ"}, {"status": "besloten"}, pad)
    zoek = "regel Firma op Besloten zetten"
    assert any(zoek in t and w == "mehdi" for t, w in open_.noden), open_.noden
    assert not any(zoek in t for t, _ in dicht.noden), dicht.noden


def test_organisatie_valt_terug_voor_migratie_175():
    vragen = []

    def psql(sql):
        vragen.append(sql)
        if "code_contact" in sql:
            raise RuntimeError('ERROR:  column f.code_contact does not exist')
        return [{"code": "QQQQ", "naam": "Proef", "land": "BE", "actief": True}]

    oud = O._psql
    O._psql = psql
    try:
        assert O._lees_firmas() == [{"code": "QQQQ", "naam": "Proef", "land": "BE", "actief": True}]
        assert len(vragen) == 2
    finally:
        O._psql = oud


def test_bewaarde_lijst_zonder_contactcode_is_verouderd():
    pad = os.path.join(tempfile.mkdtemp(), "firmas.json")
    with open(pad, "w", encoding="utf-8") as f:
        json.dump({"ts": time.time(), "firmas": [{"code": "QQQQ", "naam": "Proef"}]}, f)
    oud = (O.CACHE_FIRMA, O._lees_firmas)
    O.CACHE_FIRMA = pad
    O._lees_firmas = lambda: [{"code": "QQQQ", "code_contact": "QQ", "naam": "Proef"}]
    try:
        assert O.contactcodes() == {"QQ": "QQQQ"}
    finally:
        O.CACHE_FIRMA, O._lees_firmas = oud


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

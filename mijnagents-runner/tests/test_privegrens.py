"""Grendel op de privéregel van de gesprekkentabel op één plek (T-0120 DB-8 en VOL-2, koppelingen/privegrens.py).

- P01: de twee exemplaren (koppelingen/privegrens.py voor de runners, mijnagents/privegrens.py voor de image van het
  bord) zijn gelijk;
- P02 (pariteit): dezelfde rij is privé bij De Dagbundelaar (dagvaststelling.is_prive), bij De Communicatiebundelaar
  (communicatie_bundelaar.is_prive) en op de wachtenpagina (wachten_dag), of bij alle drie niet. De enige bewuste
  uitzondering: een Mac-kanaal (WhatsApp, telefoon, sms, Xelion) zonder afdeling privé houdt op de wachtenpagina, die
  alleen Mehdi ziet, naam en aantal;
- P03 (DB-8): een Zoom-, Fathom- of Plaud-rij met prive=1 en afdeling onbekend toont op de wachtenpagina alleen
  'privégesprek, N min', zonder naam of onderwerp; een WhatsApp-rij met prive=1 toont nog naam en aantal;
- P04: tegenover de regels van voor 01-11-2026 verandert alleen wat moest: de wachtenpagina verbergt een niet-Mac-rij
  met prive=1, en De Communicatiebundelaar neemt een Mac-rij ook zonder vlag als privé (elke Mac-rij draagt de vlag al);
  De Dagbundelaar blijft bij elke rij gelijk;
- P05 (B&S): een Plaud-opname van een plaatsbezoek barsten en scheuren, geen privé, blijft bij alle drie werk, met naam
  en onderwerp zoals voorheen.

Geen netwerk, geen bord: de wachtenpagina leest uit een tijdelijke sqlite-databank. Alle namen zijn verzonnen.
Draaien: python3 mijnagents-runner/tests/test_privegrens.py
"""
import io
import os
import sqlite3
import sys
from contextlib import redirect_stderr

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
REPO = os.path.dirname(RUNNER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
sys.path.append(os.path.join(REPO, "mijnagents"))
import communicatie_bundelaar as C  # noqa: E402
import dagvaststelling as V  # noqa: E402
import wachten_dag as W  # noqa: E402

DAG = "2026-10-31"
MAC = ("whatsapp", "telefoon", "sms", "xelion")
# Per bron een uniek zoals de wacht het schrijft (koppelingen/mac_gesprekken.py, xelion_wacht.py, zoom_wacht.py).
UNIEK = {"zoom": "zoom:meeting:p1", "zoom-chat": "zoom:chat:zeta@voorbeeld.test:" + DAG, "fathom": "fathom:71",
         "plaud": "plaud:72", "mail": "mail:<p1@voorbeeld.test>", "whatsapp": "whatsapp:abc:" + DAG,
         "whatsapp-oproep": "whatsapp-oproep:abc-1", "telefoon": "telefoon:proef-1", "sms": "sms:abc:" + DAG,
         "xelion": "xelion:73"}
AFDELINGEN = ("", "onbekend", "regie", "bouw", "prive", "Privé", " PRIVE ")


def rijen():
    """Elke bron met en zonder vlag, met elke soort afdeling."""
    for soort, uniek in UNIEK.items():
        bron = soort.split("-")[0]
        for prive in (0, 1):
            for afdeling in AFDELINGEN:
                yield {"uniek": uniek, "bron": bron, "datum": DAG, "start": "10:00", "minuten": 12,
                       "personen": "Mehdi, Proefpersoon Zeta", "thema": "Proefonderwerp Omega", "prive": prive,
                       "afdeling": afdeling, "dubbel_van": ""}


def op_de_wachtenpagina(rij):
    """De rij zoals de wachtenpagina ze toont: (privé, items), via de echte lees_gesprekken op een sqlite-databank."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE gesprek_log (uniek TEXT, datum TEXT, start TEXT, minuten INTEGER, personen TEXT, "
                 "thema TEXT, bron TEXT, dubbel_van TEXT, afdeling TEXT, prive INTEGER)")
    conn.execute("INSERT INTO gesprek_log VALUES (:uniek, :datum, :start, :minuten, :personen, :thema, :bron, "
                 ":dubbel_van, :afdeling, :prive)", rij)
    items, _ = W.lees_gesprekken(conn, rij["bron"], DAG)
    assert len(items) == 1, items
    return items[0]["wie"] == "privégesprek", items


def zonder_bron(rij):
    """De Communicatiebundelaar leest de kolom bron niet (communicatie_bundelaar.SQL)."""
    return {k: v for k, v in rij.items() if k != "bron"}


def afdeling_prive(rij):
    return rij["afdeling"].strip().casefold() in ("prive", "privé")


# De regels zoals ze op 6babd78 in de drie bestanden stonden, als maat voor P04.
def oud_dagvaststelling(g):
    return bool(g.get("prive") or afdeling_prive(g) or g.get("bron") in MAC)


def oud_communicatie(r):
    return bool(r.get("prive")) or afdeling_prive(r)


def oud_wachten(r):
    return afdeling_prive(r)


def test_p01_twee_exemplaren_gelijk():
    a = open(os.path.join(RUNNER, "koppelingen", "privegrens.py"), encoding="utf-8").read()
    b = open(os.path.join(REPO, "mijnagents", "privegrens.py"), encoding="utf-8").read()
    assert a == b, "mijnagents/privegrens.py wijkt af van mijnagents-runner/koppelingen/privegrens.py: kopieer het"


def test_p02_pariteit_over_de_drie_lezers():
    for rij in rijen():
        dv, cb = V.is_prive(rij), C.is_prive(zonder_bron(rij))
        wd, items = op_de_wachtenpagina(rij)
        assert dv == cb, (rij, dv, cb)
        # buiten Mehdi: elke Mac-rij is privé; elke andere rij als de vlag of de afdeling het zegt
        assert dv == (rij["bron"] in MAC or bool(rij["prive"]) or afdeling_prive(rij)), rij
        if rij["bron"] in MAC and not afdeling_prive(rij):
            # de bewuste uitzondering: alleen de wachtenpagina, die alleen Mehdi ziet
            assert dv and not wd, (rij, items)
        else:
            assert wd == dv, (rij, wd, dv, items)


def test_p03_db8_vlag_zonder_afdeling_is_prive_op_de_wachtenpagina():
    for bron in ("zoom", "fathom", "plaud"):
        rij = dict(next(r for r in rijen() if r["bron"] == bron), prive=1, afdeling="onbekend")
        wd, items = op_de_wachtenpagina(rij)
        assert wd and items[0]["wat"] == "12 min", items
        assert "Zeta" not in str(items) and "Omega" not in str(items), items
    wa = dict(next(r for r in rijen() if r["bron"] == "whatsapp"), prive=1, afdeling="", personen="Proefpersoon Zeta",
              thema="3 berichten")
    wd, items = op_de_wachtenpagina(wa)
    assert not wd and items[0]["wie"] == "Proefpersoon Zeta", items


def test_p04_alleen_wat_moest_veranderde():
    for rij in rijen():
        assert V.is_prive(rij) == oud_dagvaststelling(rij), rij
        if C.is_prive(zonder_bron(rij)) != oud_communicatie(rij):
            assert rij["bron"] in MAC and not rij["prive"] and not afdeling_prive(rij), rij
        wd, _ = op_de_wachtenpagina(rij)
        if wd != oud_wachten(rij):
            assert rij["bron"] not in MAC and rij["prive"] and not afdeling_prive(rij), rij


def test_p05_bs_plaatsbezoek_blijft_werk():
    rij = {"uniek": "plaud:bs-1", "bron": "plaud", "datum": DAG, "start": "14:00", "minuten": 95,
           "personen": "Mehdi, Klant Omega", "thema": "bezoek klant - barsten en scheuren", "prive": 0,
           "afdeling": "bouw", "dubbel_van": ""}
    assert not V.is_prive(rij) and not oud_dagvaststelling(rij)
    assert not C.is_prive(zonder_bron(rij)) and not oud_communicatie(rij)
    wd, items = op_de_wachtenpagina(rij)
    assert not wd and items[0]["wie"] == "Mehdi, Klant Omega" and "barsten en scheuren" in items[0]["wat"], items
    assert V.gesprek_tekst(rij).endswith("Plaud, 95 min, Mehdi, Klant Omega"), V.gesprek_tekst(rij)


if __name__ == "__main__":
    import traceback
    goed = fout = 0
    for naam, f in sorted(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                with redirect_stderr(io.StringIO()):
                    f()
                goed += 1
                print(f"   geslaagd  {naam}")
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"   GEFAALD   {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)

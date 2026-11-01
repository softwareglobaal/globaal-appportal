"""De WhatsApp-wacht en De Belwacht op de Mac (ontwerp docs/ontwerp-dagvaststelling.md v2.0, fase 2).

Legt vast, zonder netwerk, zonder bord en zonder de echte databanken (alles in een tijdelijke map):
- alleen toegelaten kolommen: geen vraag en geen helper leest ZTEXT, voorbeeldtekst, media of status (Codex P1);
- WhatsApp: per gesprek per dag een rij met berichten in en uit; groeps-, systeem- en oproepmeldingen tellen niet; een
  groep heet 'groep: naam'; uitzendlijsten en status tellen niet;
- WhatsApp-oproepen: met wie (deelnemer, oproepmelding of beller), een gemiste oproep met buiten:gemist, dezelfde
  oproep-ID kort na elkaar is een oproep, ver uit elkaar twee (P6);
- iPhone: naam via het adresboek in elk nummerformaat, een onbekend nummer als nummer, WhatsApp en andere apps
  overgeslagen, FaceTime telt;
- dekking alleen voor een dag die voorbij is, zelf gegevens toont en waarna de bron nog iets kreeg (P4);
- het uur dat bij de wintertijd twee keer voorkomt, krijgt de UTC-afstand en De Dagbundelaar leest het juist (P5);
- na een lange slaap leest een ronde tot zestig dagen terug (P7), en De Dagbundelaar haalt zulke dagen in;
- schrijven en teruglezen: een verschil is een fout, een verdwenen rij wordt vervallen, te veel verdwenen stopt (P9);
- de kopie hoort bij de eigen aanvraag (P9), een weigering van macOS is een nood voor Mehdi;
- het contract met De Dagbundelaar: het overzicht toont 'WhatsApp: N berichten ... gezien' en 'telefoon: ... gezien',
  zonder een naam; zonder dekking 'onbekend';
- de runners: door de gedeelde ronde (N12), geen naam of nummer in hartslag of werkverslag, de ronde-ID in kennis en
  hartslag, N4 vergelijkt die ID bij elke cadans (P8);
- de helper zelf (alleen op een Mac met cc): leest de WAL mee (P2), schrijft geen tekstkolom, weigert een symlink en
  meldt een ander schema als onverwacht.
Draaien: python3 mijnagents-runner/tests/test_mac_gesprekken.py
"""
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent
RUNNER = HIER.parent
sys.path.insert(0, str(RUNNER))
sys.path.insert(0, str(RUNNER / "koppelingen"))
_argv, sys.argv = sys.argv, [sys.argv[0]]
import bord  # noqa: E402
import bordstand  # noqa: E402
import controle_agenten as CONTROLE  # noqa: E402
import dagbundelaar as D  # noqa: E402
import dagvaststelling as V  # noqa: E402
import mac_gesprekken as M  # noqa: E402
import belwacht as BEL  # noqa: E402
import whatsapp_wacht as WA  # noqa: E402
import sms_wacht as SMS  # noqa: E402
sys.argv = _argv

BRUSSEL = M.BRUSSEL
HELPER_C = RUNNER / "mac" / "kopie" / "macgesprekken_kopie.c"
VERBODEN = ("ZTEXT", "ZLASTMESSAGETEXT", "ZMEDIA", "ZTHUMBNAIL", "ZVCARD", "ZABOUTTEXT", "ZSAVEDINPUT", "ZCONTENT",
            "ZTITLE", "ZSUMMARY", "ZMATCHEDTEXT", "ZPUSHNAME", "ZNOTES", "ZMETADATA")
JAN, PIET, GROEP = "Jan Proef", "Piet Proef", "Werfgroep Proef"


def bxl(*args):
    return datetime(*args, tzinfo=BRUSSEL)


def a(t):
    return M.apple(t)


def maak_whatsapp(pad, berichten=(), sessies=(), oproepen=(), aggregaten=(), deelnemers=(), contacten=(), nieuwste=None):
    """Een uitvoer van de helper voor de set whatsapp, met dezelfde tabellen en kolommen."""
    con = sqlite3.connect(pad)
    con.executescript("""
        CREATE TABLE ZWAMESSAGE(ZCHATSESSION, ZMESSAGEDATE, ZISFROMME, ZMESSAGETYPE, ZSTANZAID);
        CREATE TABLE ZWACHATSESSION(Z_PK, ZCONTACTJID, ZPARTNERNAME, ZSESSIONTYPE);
        CREATE TABLE ZWACDCALLEVENT(Z_PK, ZCALLIDSTRING, ZDATE, ZDURATION, Z1CALLEVENTS, ZGROUPCALLCREATORUSERJIDSTRING,
                                    ZGROUPJIDSTRING);
        CREATE TABLE ZWAAGGREGATECALLEVENT(Z_PK, ZINCOMING, ZMISSED, ZVIDEO);
        CREATE TABLE ZWACDCALLEVENTPARTICIPANT(Z_PK, Z1PARTICIPANTS, ZJIDSTRING);
        CREATE TABLE ZWAADDRESSBOOKCONTACT(Z_PK, ZFULLNAME, ZWHATSAPPID, ZLID, ZPHONENUMBER);
        CREATE TABLE META(sleutel, waarde);""")
    con.executemany("INSERT INTO ZWAMESSAGE VALUES(?,?,?,?,?)", berichten)
    con.executemany("INSERT INTO ZWACHATSESSION VALUES(?,?,?,?)", sessies)
    con.executemany("INSERT INTO ZWACDCALLEVENT VALUES(?,?,?,?,?,?,?)", oproepen)
    con.executemany("INSERT INTO ZWAAGGREGATECALLEVENT VALUES(?,?,?,?)", aggregaten)
    con.executemany("INSERT INTO ZWACDCALLEVENTPARTICIPANT VALUES(?,?,?)", deelnemers)
    con.executemany("INSERT INTO ZWAADDRESSBOOKCONTACT VALUES(?,?,?,?,?)", contacten)
    con.execute("INSERT INTO META VALUES('nieuwste', ?)", (nieuwste,))
    con.commit()
    con.close()
    return pad


def maak_telefoon(pad, oproepen=(), contacten=(), nieuwste=None):
    con = sqlite3.connect(pad)
    con.executescript("""
        CREATE TABLE ZCALLRECORD(ZUNIQUE_ID, ZDATE, ZDURATION, ZORIGINATED, ZANSWERED, ZADDRESS, ZSERVICE_PROVIDER);
        CREATE TABLE ZWAADDRESSBOOKCONTACT(Z_PK, ZFULLNAME, ZWHATSAPPID, ZLID, ZPHONENUMBER);
        CREATE TABLE META(sleutel, waarde);""")
    con.executemany("INSERT INTO ZCALLRECORD VALUES(?,?,?,?,?,?,?)", oproepen)
    con.executemany("INSERT INTO ZWAADDRESSBOOKCONTACT VALUES(?,?,?,?,?)", contacten)
    con.execute("INSERT INTO META VALUES('nieuwste', ?)", (nieuwste,))
    con.commit()
    con.close()
    return pad


DAG = "2026-10-22"
DAGEN = ["2026-10-21", DAG, "2026-10-23"]


def maak_sms(pad, berichten=(), gesprekken=(), deelnemers=(), contacten=(), nieuwste=None):
    """Een uitvoer van de helper voor de set sms (31-10-2026)."""
    con = sqlite3.connect(pad)
    con.executescript("""
        CREATE TABLE BERICHT(gesprek, datum, van_mij, dienst);
        CREATE TABLE GESPREK(pk, ident, soort, naam);
        CREATE TABLE DEELNEMER(gesprek, adres);
        CREATE TABLE ZWAADDRESSBOOKCONTACT(Z_PK, ZFULLNAME, ZWHATSAPPID, ZLID, ZPHONENUMBER);
        CREATE TABLE META(sleutel, waarde);""")
    con.executemany("INSERT INTO BERICHT VALUES(?,?,?,?)", berichten)
    con.executemany("INSERT INTO GESPREK VALUES(?,?,?,?)", gesprekken)
    con.executemany("INSERT INTO DEELNEMER VALUES(?,?)", deelnemers)
    con.executemany("INSERT INTO ZWAADDRESSBOOKCONTACT VALUES(?,?,?,?,?)", contacten)
    con.execute("INSERT INTO META VALUES('nieuwste', ?)", (nieuwste,))
    con.commit()
    con.close()
    return pad


def sms_wereld(map_):
    """Een dag met een sms-gesprek, een iMessage via mailadres en een groep."""
    gesprekken = [(1, "+32470000001", 45, ""), (2, "kees@proef.be", 45, ""), (3, "chat99", 43, GROEP)]
    deelnemers = [(1, "+32470000001"), (2, "kees@proef.be"), (3, "+32470000001"), (3, "+32470000099")]
    berichten = [(1, a(bxl(2026, 10, 22, 9, 0)), 0, "SMS"), (1, a(bxl(2026, 10, 22, 9, 5)), 1, "SMS"),
                 (1, a(bxl(2026, 10, 22, 9, 6)), 1, "iMessage"), (2, a(bxl(2026, 10, 22, 15, 0)), 0, "iMessage"),
                 (3, a(bxl(2026, 10, 22, 20, 0)), 1, "iMessage"), (3, a(bxl(2026, 10, 21, 23, 59)), 0, "iMessage")]
    contacten = [(1, JAN, "", "", "0470 00 00 01")]
    return maak_sms(os.path.join(map_, "sms.sqlite"), berichten, gesprekken, deelnemers, contacten,
                    nieuwste=a(bxl(2026, 10, 23, 8, 0)))


def test_sms_per_gesprek_per_dag_zonder_tekst():
    with tempfile.TemporaryDirectory() as map_:
        rijen, info = M.sms_rijen(sms_wereld(map_), DAGEN)
    op = {(r["personen"], r["datum"]): r for r in rijen}
    jan = op[(JAN, DAG)]
    assert jan["thema"].startswith("3 berichten (1 in, 2 uit; iMessage 1, sms 2)"), jan
    assert re.fullmatch(r"sms:[0-9a-f]{40}:" + DAG, jan["uniek"]) and jan["bron"] == "sms" and jan["prive"] == 1
    assert op[("kees@proef.be", DAG)]["thema"].startswith("1 berichten (1 in, 0 uit; iMessage 1)")
    assert ("groep: " + GROEP, DAG) in op and ("groep: " + GROEP, "2026-10-21") in op
    assert info["aanwezig"] == {"2026-10-21", DAG}
    s = M.samenvatting(rijen, DAG)
    assert s["berichten"] == 5 and s["gesprekken"] == 3 and s["oproepen"] == 0, s
    assert V.soort({"uniek": jan["uniek"], "bron": "sms"}) == "chat" and V.is_prive({"bron": "sms"})


def whatsapp_wereld(map_):
    """Een dag met twee gesprekken, een groep, een uitzendlijst, meldingen en vier oproepen."""
    sessies = [(1, "32470000001@s.whatsapp.net", JAN, 0), (2, "123-456@g.us", GROEP, 1),
               (3, "status@broadcast", "Status", 3), (4, "900000000000001@lid", "", 0)]
    berichten = [
        (1, a(bxl(2026, 10, 22, 9, 14)), 0, 0, None), (1, a(bxl(2026, 10, 22, 9, 20)), 1, 0, None),
        (1, a(bxl(2026, 10, 22, 18, 2)), 1, 1, None),
        (1, a(bxl(2026, 10, 22, 12, 0)), 0, 59, "OPROEP2"),          # melding van een oproep: geen bericht
        (1, a(bxl(2026, 10, 22, 12, 1)), 0, 10, None),               # systeemmelding: geen bericht
        (2, a(bxl(2026, 10, 22, 10, 0)), 0, 0, None), (2, a(bxl(2026, 10, 22, 10, 5)), 0, 6, None),
        (3, a(bxl(2026, 10, 22, 11, 0)), 0, 0, None),                # status telt niet
        (4, a(bxl(2026, 10, 21, 23, 59)), 0, 0, None),               # andere dag (Brussel)
        (4, a(bxl(2026, 10, 22, 0, 1)), 1, 0, None),
    ]
    oproepen = [
        (11, "OPROEP1", a(bxl(2026, 10, 22, 11, 0)), 300.0, 21, None, None),      # deelnemer, beantwoord
        (12, "OPROEP2", a(bxl(2026, 10, 22, 12, 0)), 0.0, 22, None, None),        # gemist, via de melding
        (13, "OPROEP3", a(bxl(2026, 10, 22, 13, 0)), 50.0, 23, "900000000000002@lid", None),   # inkomend, beller
        (14, "OPROEP3", a(bxl(2026, 10, 22, 13, 5)), 70.0, 23, "900000000000002@lid", None),   # opnieuw verbonden
        (15, "OPROEP3", a(bxl(2026, 10, 23, 9, 0)), 60.0, 24, "900000000000002@lid", None),    # dezelfde ID, later
        (16, "OPROEP4", a(bxl(2026, 10, 22, 14, 0)), 600.0, 25, None, "123-456@g.us"),        # groepsoproep
        (10, "OPROEP0", a(bxl(2026, 8, 23, 12, 0)), 30.0, 20, None, None),      # WA-2: geschiedenis vanaf het venster
    ]
    aggregaten = [(20, 0, 0, 0), (21, 0, 0, 0), (22, 1, 1, 0), (23, 1, 0, 1), (24, 1, 0, 0), (25, 0, 0, 0)]
    deelnemers = [(31, 11, "900000000000003@lid")]
    contacten = [(41, PIET, "32470000003@s.whatsapp.net", "900000000000003@lid", "+32470000003"),
                 (42, "Kees Proef", "32470000002@s.whatsapp.net", "900000000000002@lid", "+32470000002")]
    return maak_whatsapp(os.path.join(map_, "wa.sqlite"), berichten, sessies, oproepen, aggregaten, deelnemers,
                         contacten, nieuwste=a(bxl(2026, 10, 23, 20, 0)))


def telefoon_wereld(map_):
    oproepen = [
        ("U1", a(bxl(2026, 10, 22, 8, 0)), 125.0, 1, 0, "0470000001", "com.apple.Telephony"),
        ("U2", a(bxl(2026, 10, 22, 9, 0)), 0.0, 0, 0, "+32 470 00 00 02", "com.apple.Telephony"),
        ("U3", a(bxl(2026, 10, 22, 10, 0)), 60.0, 0, 1, "+32470000099", "com.apple.Telephony"),
        ("U4", a(bxl(2026, 10, 22, 11, 0)), 300.0, 0, 1, "+32470000001", "net.whatsapp.WhatsApp"),
        ("U5", a(bxl(2026, 10, 22, 12, 0)), 30.0, 1, 0, "470000002", "com.apple.FaceTime"),
        ("U6", a(bxl(2026, 10, 22, 13, 0)), 0.0, 1, 0, "", "com.apple.Telephony"),
    ]
    contacten = [(1, JAN, "", "", "+32470000001"), (2, PIET, "", "", "+32470000002")]
    return maak_telefoon(os.path.join(map_, "tel.sqlite"), oproepen, contacten, nieuwste=a(bxl(2026, 10, 23, 7, 0)))


# ------------------------------------------------------------------------------------------- kolommen ---
def test_geen_tekstkolom_in_vragen_of_helper():
    alles = " ".join(M.SQL)
    for kolom in VERBODEN:
        assert kolom not in alles, kolom
    bron = HELPER_C.read_text(encoding="utf-8")
    vragen = re.findall(r'"([^"\n]*(?:SELECT|CREATE)[^"\n]*)"', bron)
    assert vragen, "geen vragen gevonden in de helper"
    for kolom in VERBODEN:
        assert not any(kolom in v for v in vragen), kolom
    # ZSTANZAID alleen van de oproepmelding
    assert "CASE WHEN ZMESSAGETYPE = 59 THEN ZSTANZAID END" in bron
    try:
        M.lees(":memory:", "SELECT ZTEXT FROM ZWAMESSAGE")
    except ValueError:
        pass
    else:
        raise AssertionError("een vreemde vraag werd aanvaard")


# ------------------------------------------------------------------------------------------- WhatsApp ---
def test_whatsapp_berichten_per_gesprek_per_dag():
    with tempfile.TemporaryDirectory() as map_:
        rijen, info = M.whatsapp_rijen(whatsapp_wereld(map_), DAGEN)
    chats = {r["uniek"]: r for r in rijen if r["uniek"].startswith("whatsapp:")}
    jan = chats["whatsapp:" + hashlib.sha1(b"32470000001@s.whatsapp.net").hexdigest() + ":" + DAG]
    assert jan["thema"] == "3 berichten (1 in, 2 uit), 09:14 tot 18:02", jan
    assert jan["personen"] == JAN and jan["start"] == "09:14" and jan["minuten"] == 0 and jan["prive"] == 1
    assert jan["bron"] == "whatsapp" and jan["dubbel_van"] == ""
    assert V._berichten(jan) == 3 and V.soort(jan) == "chat"
    groep = [r for r in chats.values() if r["personen"] == "groep: " + GROEP]
    assert len(groep) == 1 and groep[0]["thema"].startswith("1 berichten (1 in, 0 uit)"), groep
    assert not any("Status" in r["personen"] for r in rijen)
    lid = [r for r in chats.values() if r["uniek"].startswith("whatsapp:" + hashlib.sha1(b"900000000000001@lid").hexdigest())]
    assert sorted(r["datum"] for r in lid) == ["2026-10-21", DAG], lid
    assert {r["personen"] for r in lid} == {"onbekend"}, lid
    assert info["aanwezig"] == {"2026-10-21", DAG, "2026-10-23"}, info


def test_whatsapp_oproepen():
    with tempfile.TemporaryDirectory() as map_:
        rijen, _ = M.whatsapp_rijen(whatsapp_wereld(map_), DAGEN)
    op = {r["uniek"]: r for r in rijen if r["uniek"].startswith("whatsapp-oproep:")}

    def sleutel(ident, *begin):
        return f"whatsapp-oproep:{ident}-{int(a(bxl(*begin)))}"
    een = op[sleutel("OPROEP1", 2026, 10, 22, 11, 0)]
    assert een["personen"] == PIET and een["minuten"] == 5 and een["dubbel_van"] == "" and V.soort(een) == "oproep"
    assert een["thema"] == "WhatsApp-oproep, uitgaand", een
    twee = op[sleutel("OPROEP2", 2026, 10, 22, 12, 0)]
    assert twee["personen"] == JAN and twee["dubbel_van"] == M.GEMIST and twee["thema"].endswith("gemist"), twee
    drie = op[sleutel("OPROEP3", 2026, 10, 22, 13, 0)]
    assert drie["personen"] == "Kees Proef" and drie["minuten"] == 2 and drie["start"] == "13:00", drie
    assert "video" in drie["thema"]
    later = op[sleutel("OPROEP3", 2026, 10, 23, 9, 0)]
    assert later["datum"] == "2026-10-23" and later["minuten"] == 1, later
    vier = op[sleutel("OPROEP4", 2026, 10, 22, 14, 0)]
    assert len(op) == 5, sorted(op)
    assert vier["personen"] == "groep: " + GROEP and vier["minuten"] == 10, vier


def test_wa3_niet_gemist_zonder_duur_telt_als_oproep():
    """WA-3: WhatsApp zegt met ZMISSED of een inkomende oproep gemist is. Niet gemist en zonder duur (waarschijnlijk op de
    gsm opgenomen) is een oproep met onbekende duur, geen gemiste: zonder buiten:gemist, dus telt hij als oproep. Alleen
    ZMISSED=1 is gemist; een uitgaande oproep zonder duur blijft 'niet beantwoord'."""
    sessies = [(1, "32470000001@s.whatsapp.net", JAN, 0)]
    oproepen = [(11, "OPROEPA", a(bxl(2026, 10, 22, 9, 0)), 0.0, 21, "32470000001@s.whatsapp.net", None),
                (12, "OPROEPB", a(bxl(2026, 10, 22, 10, 0)), 0.0, 22, "32470000001@s.whatsapp.net", None),
                (13, "OPROEPC", a(bxl(2026, 10, 22, 11, 0)), 0.0, 23, None, None),
                (14, "OPROEPD", a(bxl(2026, 10, 22, 12, 0)), 0.0, 24, "32470000001@s.whatsapp.net", None)]
    aggregaten = [(21, 1, 0, 0), (22, 1, 1, 0), (23, 0, 0, 0), (24, 1, None, 0)]     # D: ZMISSED onbekend (NULL)
    with tempfile.TemporaryDirectory() as map_:
        pad = maak_whatsapp(os.path.join(map_, "wa.sqlite"), (), sessies, oproepen, aggregaten,
                            nieuwste=a(bxl(2026, 10, 23, 20, 0)))
        rijen, _ = M.whatsapp_rijen(pad, DAGEN)
    op = {r["uniek"].split(":")[1].split("-")[0]: r for r in rijen}
    a_, b_, c_ = op["OPROEPA"], op["OPROEPB"], op["OPROEPC"]
    assert a_["thema"] == "WhatsApp-oproep, inkomend, niet gemist, duur onbekend" and a_["dubbel_van"] == "", a_
    assert a_["minuten"] == 0 and a_["personen"] == JAN and V.is_leidend(a_) and V.soort(a_) == "oproep"
    assert b_["thema"] == "WhatsApp-oproep, inkomend, gemist" and b_["dubbel_van"] == M.GEMIST, b_
    assert c_["thema"] == "WhatsApp-oproep, uitgaand, niet beantwoord" and c_["dubbel_van"] == M.GEMIST, c_
    # Codex-toets 1: een onbekende ZMISSED (NULL) is geen 'niet gemist': zoals voor WA-3, telt niet als oproep
    assert op["OPROEPD"]["thema"] == "WhatsApp-oproep, inkomend, gemist" and op["OPROEPD"]["dubbel_van"] == M.GEMIST
    s = M.samenvatting(rijen, DAG)
    assert s["oproepen"] == 1 and s["minuten"] == 0 and s["gemist"] == 3, s
    v = V.vaststellen(DAG, [], [], rijen, {}, [], "volledig", None, {"whatsapp": "aangesloten"}, lambda x: False, "volledig")
    assert v["whatsapp"]["oproepen"] == 1, v["whatsapp"]


def test_wa3_plaatsbezoek_barsten_en_scheuren_zelfde_uitkomst():
    """WA-3 en B&S: een plaatsbezoek voor barsten en scheuren dat de auto ter plaatse bevestigt, houdt bij De
    Dagbundelaar zijn uitkomst als er op dat uur alleen een gemiste oproep van de klant is (ZMISSED 1) of een niet
    gemiste oproep zonder duur van iemand anders. De B&S-keten zelf leest de WhatsApp-rijen niet."""
    sessies = [(1, "32470000001@s.whatsapp.net", JAN, 0), (2, "32470000003@s.whatsapp.net", PIET, 0)]
    oproepen = [(11, "OPROEPA", a(bxl(2026, 10, 22, 10, 30)), 0.0, 21, "32470000001@s.whatsapp.net", None),
                (12, "OPROEPB", a(bxl(2026, 10, 22, 10, 45)), 0.0, 22, "32470000003@s.whatsapp.net", None)]
    aggregaten = [(21, 1, 1, 0), (22, 1, 0, 0)]
    with tempfile.TemporaryDirectory() as map_:
        rijen, _ = M.whatsapp_rijen(maak_whatsapp(os.path.join(map_, "wa.sqlite"), (), sessies, oproepen, aggregaten,
                                                  nieuwste=a(bxl(2026, 10, 23, 20, 0))), DAGEN)
    afspraak = {"id": "bs1", "start": f"{DAG}T10:00:00+02:00", "einde": f"{DAG}T12:00:00+02:00",
                "titel": f"[XX-BS] plaatsbezoek barsten en scheuren {JAN}", "deelnemers": []}
    locatie = {"uitkomst": "doorgegaan", "tekst": "auto ter plaatse 10:05-11:50"}
    zonder = V.bewijs(afspraak, V.gesprekken_van_dag(DAG, []), locatie)
    met = V.bewijs(afspraak, V.gesprekken_van_dag(DAG, rijen), locatie)
    assert zonder["uitkomst"] == met["uitkomst"] == "aanwijzing" and met["grond"] == zonder["grond"], (zonder, met)


# ------------------------------------------------------------------------------------------- telefoon ---
def test_telefoon_namen_nummers_en_diensten():
    with tempfile.TemporaryDirectory() as map_:
        pad = telefoon_wereld(map_)
        rijen, info = M.telefoon_rijen(pad, DAGEN)
        zonder, _ = M.telefoon_rijen(pad, DAGEN, onbekend_als_nummer=False)
    op = {r["uniek"].split("-")[0]: r for r in rijen}
    assert all(re.fullmatch(r"telefoon:U\d-\d+", r["uniek"]) for r in rijen), [r["uniek"] for r in rijen]
    assert op["telefoon:U1"]["personen"] == JAN and op["telefoon:U1"]["minuten"] == 2
    assert op["telefoon:U1"]["thema"] == "telefoon, uitgaand"
    assert op["telefoon:U2"]["personen"] == PIET and op["telefoon:U2"]["dubbel_van"] == M.GEMIST
    assert op["telefoon:U2"]["thema"] == "telefoon, inkomend, gemist"
    assert op["telefoon:U3"]["personen"] == "+32470000099"
    assert "telefoon:U4" not in op and info["overgeslagen"] == 1
    assert op["telefoon:U5"]["personen"] == PIET and op["telefoon:U5"]["thema"] == "FaceTime, uitgaand"
    assert op["telefoon:U6"]["personen"] == "nummer verborgen" and op["telefoon:U6"]["thema"].endswith("niet beantwoord")
    assert {r["uniek"].split("-")[0]: r["personen"] for r in zonder}["telefoon:U3"] == "onbekend nummer"
    assert all(r["prive"] == 1 and r["bron"] == "telefoon" for r in rijen)
    assert DAG in info["aanwezig"] and "2026-10-21" not in info["aanwezig"]


def test_nummer_sleutel():
    for vorm in ("+32 470 00 00 01", "0470000001", "470000001", "0032470000001", "+32-470-00.00.01"):
        assert M.nummer_sleutel(vorm) == "470000001", vorm


# --------------------------------------------------------------------------------------------- dekking ---
def test_dekking_alleen_met_gegevens_tijdens_de_dag():
    gekopieerd = bxl(2026, 10, 24, 9, 0)
    nieuwste = bxl(2026, 10, 23, 20, 0)
    dagen = ["2026-10-20", "2026-10-21", DAG, "2026-10-23", "2026-10-24"]
    gedekt = [r["datum"] for r in M.dekking("whatsapp", dagen, gekopieerd, nieuwste, {"2026-10-21", DAG, "2026-10-23"})]
    # 20-10 zonder gegevens (de Mac sliep): onbekend; 23-10: de bron kreeg daarna niets meer; 24-10: niet voorbij
    assert gedekt == ["2026-10-21", DAG], gedekt
    rij = M.dekking("telefoon", [DAG], gekopieerd, nieuwste, {DAG})[0]
    assert rij["uniek"] == f"dekking:telefoon:{DAG}" and rij["bron"] == "dekking" and rij["dubbel_van"] == M.DEKKING
    assert M.dekking("whatsapp", dagen, gekopieerd, None, set(dagen)) == []


def test_wa2_geen_dekking_voor_het_begin_van_de_oproepgeschiedenis():
    """WA-2: begint de oproepgeschiedenis van WhatsApp op de Mac later dan het venster van de helper (62 dagen), dan
    krijgt een dag tot en met die van de oudste oproep geen dekkingsrij: zijn oproepen zijn onbekend, nooit nul. De
    berichtrijen komen er wel. Dekt de geschiedenis het hele venster, dan blijft de dekking zoals ze was."""
    gekopieerd = bxl(2026, 11, 1, 21, 0)
    dagen = [f"2026-10-{d}" for d in range(12, 17)]
    sessies = [(1, "32470000001@s.whatsapp.net", JAN, 0)]
    berichten = [(1, a(bxl(2026, 10, int(d[-2:]), 10, 0)), 0, 0, None) for d in dagen]

    def wereld(map_, eerste_oproep):
        oproepen = [(11, "OPROEP1", a(eerste_oproep), 60.0, 21, None, None),
                    (12, "OPROEP2", a(bxl(2026, 10, 15, 11, 0)), 120.0, 22, None, None)]
        return maak_whatsapp(os.path.join(map_, "wa.sqlite"), berichten, sessies, oproepen, [(21, 0, 0, 0), (22, 1, 0, 0)],
                             nieuwste=a(bxl(2026, 10, 31, 20, 0)))

    def gedekt(info):
        grens = M.oproepen_vanaf(info["oudste_oproep"], gekopieerd)
        return [r["datum"] for r in M.dekking("whatsapp", dagen, gekopieerd, info["nieuwste"], info["aanwezig"], grens)]
    with tempfile.TemporaryDirectory() as map_:
        rijen, laat = M.whatsapp_rijen(wereld(map_, bxl(2026, 10, 14, 17, 23)), dagen)
    with tempfile.TemporaryDirectory() as map_:
        _, vroeg = M.whatsapp_rijen(wereld(map_, gekopieerd - timedelta(days=M.KOPIE_DAGEN, hours=-3)), dagen)
    assert laat["oudste_oproep"] == bxl(2026, 10, 14, 17, 23), laat
    assert M.oproepen_vanaf(laat["oudste_oproep"], gekopieerd) == "2026-10-14"
    assert gedekt(laat) == ["2026-10-15", "2026-10-16"], gedekt(laat)          # 14-10 zelf: oproepen pas vanaf 17:23
    assert sorted(r["datum"] for r in rijen if r["uniek"].startswith("whatsapp:")) == dagen    # berichten wel
    assert M.oproepen_vanaf(vroeg["oudste_oproep"], gekopieerd) is None and gedekt(vroeg) == dagen, gedekt(vroeg)
    # zonder een enkele oproep in de kopie is het begin van de geschiedenis onbekend: geen dag is gedekt
    assert M.dekking("whatsapp", dagen, gekopieerd, vroeg["nieuwste"], vroeg["aanwezig"],
                     M.oproepen_vanaf(None, gekopieerd)) == []
    assert M.dekking("whatsapp", dagen, gekopieerd, vroeg["nieuwste"], vroeg["aanwezig"]) != [], "zonder grens zoals nu"
    venster = re.search(r"#define VENSTER_DAGEN (\d+)", HELPER_C.read_text(encoding="utf-8")).group(1)
    assert int(venster) == M.KOPIE_DAGEN, (venster, M.KOPIE_DAGEN)


# ------------------------------------------------------------------------------------------ zomertijd ---
def test_wintertijd_uur_twee_keer():
    eerste = datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc)      # 02:30 zomertijd
    tweede = datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc)      # 02:30 wintertijd
    assert M.start_van(eerste) == "02:30+02:00" and M.start_van(tweede) == "02:30+01:00"
    assert M.start_van(datetime(2026, 10, 25, 13, 0, tzinfo=timezone.utc)) == "14:00"
    assert M.start_van(datetime(2026, 3, 29, 1, 30, tzinfo=timezone.utc)) == "03:30"   # na de sprong, gewoon
    g1 = {"datum": "2026-10-25", "start": M.start_van(eerste), "minuten": 5}
    g2 = {"datum": "2026-10-25", "start": M.start_van(tweede), "minuten": 5}
    assert V.gesprek_venster(g1)[0] == eerste and V.gesprek_venster(g2)[0] == tweede
    afspraak = {"start": "2026-10-25T02:30:00+01:00", "einde": "2026-10-25T02:40:00+01:00"}
    assert not V.overlapt(V.afspraak_venster(afspraak), V.gesprek_venster(g1), marge=timedelta(0))
    assert V.overlapt(V.afspraak_venster(afspraak), V.gesprek_venster(g2), marge=timedelta(0))
    assert V.gesprek_tekst({**g2, "bron": "telefoon", "uniek": "telefoon:x", "prive": 1}).startswith("02:30 telefoon")


# ------------------------------------------------------------------------------------------ inhalen ---
def test_dagen_en_inhalen_na_lange_slaap():
    nu = bxl(2026, 10, 26, 10, 0)
    assert M.dagen(nu)[0] == "2026-10-13" and M.dagen(nu)[-1] == "2026-10-26" and len(M.dagen(nu)) == 14
    assert M.dagen(nu, "2026-10-01")[0] == "2026-10-02"
    assert M.dagen(nu, "2026-07-01")[0] == "2026-08-28" and len(M.dagen(nu, "2026-07-01")) == M.INHAAL
    assert M.dagen(nu, "2026-10-25")[0] == "2026-10-13"
    assert M.dagen(nu, "onzin")[0] == "2026-10-13"


def test_dagbundelaar_haalt_dagen_in():
    with tempfile.TemporaryDirectory() as map_:
        oud_staat, oud_inhaal, oud_lees = D.STAAT, D.INHAALSTAAT, bord.db_lees
        D.STAAT, D.INHAALSTAAT = os.path.join(map_, "staat.json"), os.path.join(map_, "inhaal.json")
        nu = datetime(2026, 10, 26, 23, 30, tzinfo=timezone.utc)
        venster = V.venster(nu, 14)
        vroeger = (nu - timedelta(days=3)).isoformat()
        later = (nu - timedelta(hours=1)).isoformat()
        vragen = []

        def lees(sql, args=()):
            vragen.append((sql, args))
            return [{"datum": "2026-10-01", "ts": later}, {"datum": "2026-10-02", "ts": vroeger},
                    {"datum": "2026-10-03", "ts": later}] + [{"datum": f"2026-09-{d:02d}", "ts": later} for d in range(1, 9)]

        try:
            bord.db_lees = lees
            with open(D.STAAT, "w") as f:
                json.dump({"2026-10-02": {"ts": (nu - timedelta(days=1)).isoformat()},
                           "2026-10-03": {"ts": (nu - timedelta(days=1)).isoformat()}}, f)
            with open(D.INHAALSTAAT, "w") as f:
                json.dump({"2026-10-03": nu.isoformat()}, f)
            uit = D.inhaaldagen(nu, venster)
        finally:
            D.STAAT, D.INHAALSTAAT, bord.db_lees = oud_staat, oud_inhaal, oud_lees
    assert "bron = 'dekking'" in vragen[0][0] and vragen[0][1][1] == "2026-10-12", vragen
    # 02-10 al vastgesteld na de dekking, 03-10 al ingehaald; de rest nieuwste eerst, hoogstens zeven
    assert uit == ["2026-09-03", "2026-09-04", "2026-09-05", "2026-09-06", "2026-09-07", "2026-09-08", "2026-10-01"], uit


# --------------------------------------------------------------------------------------- het contract ---
def test_dagoverzicht_toont_gezien_zonder_namen():
    with tempfile.TemporaryDirectory() as map_:
        wa, wa_info = M.whatsapp_rijen(whatsapp_wereld(map_), DAGEN)
        tel, tel_info = M.telefoon_rijen(telefoon_wereld(map_), DAGEN)
    gekopieerd = bxl(2026, 10, 24, 9, 0)
    rijen = (wa + M.dekking("whatsapp", DAGEN, gekopieerd, wa_info["nieuwste"], wa_info["aanwezig"])
             + tel + M.dekking("telefoon", DAGEN, gekopieerd, tel_info["nieuwste"], tel_info["aanwezig"]))
    # zoals dagbundelaar.vastleggen de dekking leest
    gedekt = {(x["uniek"].split(":")[1], x["datum"]) for x in rijen if x["uniek"].startswith("dekking:")}
    kanalen = {k: D.kanaal_van_dag("aangesloten", k, DAG, gedekt) for k in ("whatsapp", "telefoon")}
    assert kanalen == {"whatsapp": "aangesloten", "telefoon": "aangesloten"}, kanalen
    v = V.vaststellen(DAG, [], [], rijen, {}, [], "volledig", None, kanalen, lambda a: False, "afgesloten")
    tekst = V.tekst(v)
    # Jan Proef 3, de groep 1, het LID-gesprek 1 (00:01 Brussel); de oproepen met duur: 5, 2 en 10 min
    assert "- WhatsApp: 5 berichten in 3 gesprekken, 3 oproepen, 17 min gezien" in tekst, tekst
    assert "- telefoon: 3 oproepen, 4 min gezien" in tekst, tekst
    for naam in (JAN, PIET, GROEP, "Kees Proef", "+32470000099"):
        assert naam not in tekst, naam
    # niet gepland: een WhatsApp- of telefoonoproep van minstens twee minuten, als privé
    assert "11:00 WhatsApp-oproep, 5 min, privé" in tekst and "08:00 telefoon, 2 min, privé" in tekst, tekst
    # een dag zonder dekking is onbekend, nooit nul
    leeg = {k: D.kanaal_van_dag("aangesloten", k, "2026-10-20", gedekt) for k in ("whatsapp", "telefoon")}
    t2 = V.tekst(V.vaststellen("2026-10-20", [], [], rijen, {}, [], "volledig", None, leeg, lambda a: False))
    assert "- WhatsApp: onbekend (onbekend voor deze dag)" in t2 and "- telefoon: onbekend (onbekend voor deze dag)" in t2


# ---------------------------------------------------------------------------------- schrijven en terug ---
class NepBord:
    def __init__(self):
        self.tabel, self.oproepen = {}, []

    def call(self, pad, payload=None):
        self.oproepen.append(pad)
        if pad == "/api/gesprekken":
            for r in payload["rijen"]:
                self.tabel[r["uniek"]] = dict(r)
            return {"ok": True, "rijen": len(payload["rijen"])}
        if pad == "/api/gesprekken/koppel":
            for k in payload["koppelingen"]:
                self.tabel[k["uniek"]]["dubbel_van"] = k["dubbel_van"]
            return {"ok": True}
        raise AssertionError(pad)

    def terug(self, kanaal, van, tot):
        return {u: {"v": bordstand.vingerafdruk(r), "d": r.get("dubbel_van") or ""} for u, r in self.tabel.items()
                if van <= r["datum"] <= tot and u.startswith(bordstand.KANALEN[kanaal])}


def tel(i):
    """Een telefoonsleutel in de vorm van deze versie (ID en tijdstip)."""
    return f"telefoon:U{i}-{1000 + i}"


def rij(uniek, dag=DAG, **x):
    return {"uniek": uniek, "datum": dag, "start": "10:00", "minuten": 1, "personen": "Jan Proef", "thema": "t",
            "prive": 1, "bron": "telefoon", "dubbel_van": "", **x}


def test_schrijven_teruglezen_en_vervallen():
    b = NepBord()
    rijen = [rij(tel(i)) for i in range(10)]
    assert M.schrijf_en_lees_terug("telefoon", rijen, DAG, DAG, b.call, b.terug) == 0
    # een rij die de bron niet meer toont, wordt vervallen; ze komt terug als de bron ze weer toont
    assert M.schrijf_en_lees_terug("telefoon", rijen[:9], DAG, DAG, b.call, b.terug) == 1
    assert b.tabel[tel(9)]["dubbel_van"] == M.VERVALLEN
    assert M.schrijf_en_lees_terug("telefoon", rijen, DAG, DAG, b.call, b.terug) == 0
    assert b.tabel[tel(9)]["dubbel_van"] == ""
    # een rij van een ander kanaal of buiten het venster blijft ongemoeid
    b.tabel["whatsapp:x:" + DAG] = rij("whatsapp:x:" + DAG, bron="whatsapp")
    b.tabel["telefoon:oud"] = rij("telefoon:oud", dag="2026-09-01")
    assert M.schrijf_en_lees_terug("telefoon", rijen, DAG, DAG, b.call, b.terug) == 0
    # te veel verdwenen rijen: niets markeren, stoppen (P9)
    voor = list(b.oproepen)
    try:
        M.schrijf_en_lees_terug("telefoon", rijen[:2], DAG, DAG, b.call, b.terug)
    except M.MacFout as e:
        assert "niets geschreven of gemarkeerd" in e.nood
    else:
        raise AssertionError("te veel vervallen rijen werden gemarkeerd")
    assert "/api/gesprekken/koppel" not in b.oproepen[len(voor):]
    # het bord bewaart iets anders: een fout
    slecht = NepBord()
    slecht.terug = lambda k, v, t: {}
    try:
        M.schrijf_en_lees_terug("telefoon", rijen, DAG, DAG, slecht.call, slecht.terug)
    except M.MacFout as e:
        assert e.nood == "Gesprekkentabel gaf de rijen niet terug zoals geschreven"
    else:
        raise AssertionError("verschil niet gezien")


def test_bordstand_gesprekken_uit_de_databank():
    with tempfile.TemporaryDirectory() as map_:
        db = os.path.join(map_, "bord.db")
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE gesprek_log(uniek TEXT PRIMARY KEY, datum, start, minuten INTEGER, personen, thema, "
                    "prive INTEGER, bron, ts, dubbel_van TEXT DEFAULT '')")
        geschreven = [rij("telefoon:1"), rij("dekking:telefoon:" + DAG, bron="dekking", dubbel_van=M.DEKKING),
                      rij("whatsapp-oproep:9", bron="whatsapp")]
        for r in geschreven:
            con.execute("INSERT INTO gesprek_log VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (r["uniek"], r["datum"], r["start"], r["minuten"], r["personen"], r["thema"],
                         r["prive"], r["bron"], "nu", r["dubbel_van"]))
        con.commit()
        con.close()
        uit = bordstand.gesprekken("telefoon", DAG, DAG, db)
        uitvoer = subprocess.run([sys.executable, str(RUNNER / "koppelingen" / "bordstand.py"), "--gesprekken",
                                  "telefoon", DAG, DAG], env={**os.environ, "AGENTS_DB": db}, capture_output=True,
                                 text=True, check=True).stdout
    assert set(uit) == {"telefoon:1", "dekking:telefoon:" + DAG}, uit
    assert uit["telefoon:1"]["v"] == bordstand.vingerafdruk(geschreven[0]) and uit["dekking:telefoon:" + DAG]["d"] == M.DEKKING
    assert json.loads(uitvoer) == uit and "Jan Proef" not in uitvoer


# ---------------------------------------------------------------------------------------------- kopie ---
def test_kopie_hoort_bij_de_eigen_aanvraag():
    with tempfile.TemporaryDirectory() as map_:
        klok = [1000.0]

        def tik(_):
            klok[0] += 1

        def helper(uitkomst="ok", bronnen=None, aanvraag=None, merk=None):
            def start():
                id_ = aanvraag or Path(map_, "telefoon", "aanvraag").read_text()
                uit = Path(map_, "telefoon", f"gesprekken-{id_}.sqlite")
                uit.unlink(missing_ok=True)
                maak_telefoon(str(uit))
                con = sqlite3.connect(uit)
                con.execute("INSERT INTO META VALUES('aanvraag', ?)", (merk or id_,))
                con.commit()
                con.close()
                Path(map_, "telefoon", "status.json").write_text(json.dumps(
                    {"ts": 1000, "set": "telefoon", "aanvraag": id_, "uitkomst": uitkomst,
                     "bronnen": bronnen or {"oproepen": uitkomst, "contacten": "ok"}}))
                return True
            return start

        pad, ts = M.kopie_vragen("telefoon", kopie=map_, klok=lambda: klok[0], slaap=tik, start=helper())
        aanvraag = Path(map_, "telefoon", "aanvraag").read_text()
        assert pad == Path(map_, "telefoon", f".lezen-{aanvraag}.sqlite") and pad.exists()
        assert not Path(map_, "telefoon", f"gesprekken-{aanvraag}.sqlite").exists()
        assert ts == datetime.fromtimestamp(1000, timezone.utc)
        assert os.stat(Path(map_, "telefoon", "aanvraag")).st_mode & 0o077 == 0
        assert os.stat(Path(map_, "telefoon")).st_mode & 0o077 == 0
        for start, nood, wie in ((helper(aanvraag="b" * 32), "MacGesprekkenKopie gaf geen verse kopie", "claude-code"),
                                 (helper("geweigerd"), "MacGesprekkenKopie heeft geen volledige schijftoegang", "mehdi"),
                                 (helper("onverwacht"), "Kopie van de databank op de Mac mislukt", "claude-code"),
                                 (helper(merk="f" * 32), "MacGesprekkenKopie gaf geen verse kopie", "claude-code"),
                                 (lambda: False, "MacGesprekkenKopie staat niet in launchd op de Mac", "claude-code")):
            try:
                M.kopie_vragen("telefoon", kopie=map_, klok=lambda: klok[0], slaap=tik, start=start)
            except M.MacFout as e:
                assert e.nood.startswith(nood) and e.wie == wie, (e.nood, e.wie)
            else:
                raise AssertionError(nood)


# ---------------------------------------------------------------------------------------------- runners ---
class NepRonde:
    def __init__(self, werkwijze):
        self.werkwijze, self.noden, self.bronnen, self.detail = werkwijze, [], {}, ""

    def nood(self, tekst, wie="mehdi"):
        self.noden.append((tekst, wie))

    def bron(self, naam, inhoud):
        self.bronnen[naam] = inhoud


def _draai(module, wereld, kanaal):
    werkwijze = (RUNNER / "werkwijze" / f"{module.NAAM}.md").read_text(encoding="utf-8")
    b = NepBord()
    hartslagen, log = [], []
    with tempfile.TemporaryDirectory() as map_:
        pad = wereld(map_)
        r = NepRonde(werkwijze)
        echt_call, echt_hartslag, echt_log = bord.call, module.ag.hartslag, module.ag.log
        bord.call = b.call
        module.ag.log = lambda *x, **k: log.append(module.ag.maskeer(" ".join(map(str, x))))
        try:
            uit = io.StringIO()
            with redirect_stdout(uit):
                gedekt = module.werk(r, "c" * 32, None, kopie_vragen=lambda k: (pad, bxl(2026, 10, 24, 9, 0)),
                                     terug=b.terug)
            hartslagen.append(module.ag.maskeer(r.detail))
        finally:
            bord.call, module.ag.log = echt_call, echt_log
        assert not os.path.exists(pad), "de uitvoer van de helper blijft niet staan"
    return r, b, gedekt, " ".join(hartslagen + log)


def test_whatsapp_wacht_ronde_zonder_namen():
    r, b, gedekt, gemeld = _draai(WA, whatsapp_wereld, "whatsapp")
    assert r.detail.endswith("; ronde-id:" + "c" * 32) and r.bronnen["ronde-id-" + "c" * 32] == ""
    assert gedekt == DAG and f"dekking:whatsapp:{DAG}" in b.tabel
    assert any(u.startswith("whatsapp-oproep:") for u in b.tabel)
    for naam in (JAN, PIET, GROEP, "Kees Proef", "32470000001"):
        assert naam not in gemeld, naam
    assert "gisteren" in r.detail and "berichten" in r.detail


def test_wa2_ronde_schrijft_berichten_maar_geen_dekking_voor_de_oproepgeschiedenis():
    """WA-2 in de ronde: in een kopie zonder oproep voor 22-10 krijgen 21-10 en 22-10 hun berichtrijen, maar geen
    dekkingsrij; het werkverslag zegt vanaf wanneer de oproepen er zijn, zonder naam."""
    def zonder_oude_oproep(map_):
        pad = whatsapp_wereld(map_)
        con = sqlite3.connect(pad)
        con.execute("DELETE FROM ZWACDCALLEVENT WHERE Z_PK = 10")
        con.commit()
        con.close()
        return pad
    r, b, gedekt, gemeld = _draai(WA, zonder_oude_oproep, "whatsapp")
    assert gedekt is None and not any(u.startswith("dekking:") for u in b.tabel), sorted(b.tabel)
    assert {x["datum"] for x in b.tabel.values() if x["uniek"].startswith("whatsapp:")} == {"2026-10-21", DAG}
    assert "oproepen op de Mac pas vanaf 2026-10-22" in r.detail, r.detail
    r, b, gedekt, gemeld = _draai(WA, whatsapp_wereld, "whatsapp")
    assert gedekt == DAG and "pas vanaf" not in r.detail, r.detail


def test_wa1_inhaal_vanaf_een_dag():
    """WA-1: --inhaal-vanaf 2026-10-01 (of --vanaf) laat De WhatsApp-wacht eenmalig vanaf 01-10 lezen: werk() krijgt
    30-09 als laatste gedekte dag, dus 32 dagen op 01-11, en de stand op de Mac zakt niet. --droog leest dan ook vanaf
    die dag. Zonder optie blijft alles zoals het was. Gebouwd, niet gedraaid (X6, X7)."""
    import contextlib
    nu = datetime(2026, 11, 1, 21, 0, tzinfo=timezone.utc)
    assert len(M.dagen(nu, M.inhaal_grens("2026-10-31", "2026-10-01"))) == 32
    gezien, geschreven, droog = [], [], []
    oud = (M.slot, M.lees_token, M.stand_lezen, M.tunnel, WA.ag.ronde, WA.werk, M.eindcontrole, M.stand_schrijven,
           M.inhaal_vanaf, WA.droog)
    M.slot = lambda naam: contextlib.nullcontext()
    M.lees_token = lambda: "proef"
    M.stand_lezen = lambda naam: {"gedekt_tot": "2026-10-31"}
    M.tunnel = lambda: contextlib.nullcontext("http://127.0.0.1:1")
    WA.ag.ronde = lambda taak: contextlib.nullcontext(NepRonde(""))
    WA.werk = lambda r, ronde_id, gedekt_tot=None: (gezien.append(gedekt_tot), "2026-10-31")[1]
    M.eindcontrole = lambda *x, **k: True
    M.stand_schrijven = lambda naam, stand: geschreven.append(stand)
    M.inhaal_vanaf = lambda tekst, _echt=oud[8]: _echt(tekst, nu)
    WA.droog = lambda vanaf=None: droog.append(vanaf) or 0
    oud_platform, oud_token = bord.PLATFORM, bord.TOKEN
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            assert WA.main(["--inhaal-vanaf", "2026-10-01"]) == 0
            assert WA.main(["--vanaf", "2026-10-01"]) == 0
            assert WA.main([]) == 0
            assert WA.main(["--droog", "--vanaf", "2026-10-01"]) == 0 and WA.main(["--droog"]) == 0
            for slecht in ("2026-09-02", "2026-11-02", "gisteren"):
                try:
                    WA.main(["--vanaf", slecht])
                    raise AssertionError(slecht)
                except SystemExit as e:
                    assert e.code == 2, slecht
    finally:
        (M.slot, M.lees_token, M.stand_lezen, M.tunnel, WA.ag.ronde, WA.werk, M.eindcontrole, M.stand_schrijven,
         M.inhaal_vanaf, WA.droog) = oud
        bord.PLATFORM, bord.TOKEN = oud_platform, oud_token
    assert gezien == ["2026-09-30", "2026-09-30", "2026-10-31"], gezien
    assert geschreven == [], geschreven                                 # de stand zakt niet en blijft 31-10
    assert droog == ["2026-10-01", None], droog


def test_belwacht_ronde_zonder_namen():
    r, b, gedekt, gemeld = _draai(BEL, telefoon_wereld, "telefoon")
    assert r.detail.endswith("; ronde-id:" + "c" * 32) and gedekt == DAG
    assert "1 van andere apps overgeslagen" in r.detail
    for naam in (JAN, PIET, "+32470000099", "0470000001"):
        assert naam not in gemeld, naam
    assert all(x["bron"] in ("telefoon", "dekking") for x in b.tabel.values())


def test_sms_wacht_ronde_zonder_namen():
    r, b, gedekt, gemeld = _draai(SMS, sms_wereld, "sms")
    assert r.detail.endswith("; ronde-id:" + "c" * 32) and gedekt == DAG and f"dekking:sms:{DAG}" in b.tabel
    for naam in (JAN, GROEP, "kees@proef.be", "+32470000001", "+32470000099"):
        assert naam not in gemeld, naam
    assert all(x["bron"] in ("sms", "dekking") for x in b.tabel.values())
    assert "gisteren 0 berichten in 0 gesprekken" in r.detail, r.detail       # de kopie is van 24-10


def test_zonder_grenzen_geen_kopie():
    for module in (WA, BEL, SMS):
        gevraagd = []
        r = NepRonde("# Werkwijze zonder grenzen\n\nIk doe maar wat.\n")
        try:
            module.werk(r, "d" * 32, None, kopie_vragen=lambda k: gevraagd.append(k))
        except M.MacFout:
            pass
        else:
            raise AssertionError("ronde zonder grenzen ging door")
        assert not gevraagd and r.noden == [("Werkwijze op het bord mist de veiligheidsgrenzen", "mehdi")]


def test_taak_noemt_de_databank_en_runners_gaan_door_de_ronde():
    for module in (WA, BEL, SMS):
        assert "databank" in module.TAAK
        bron = Path(module.__file__).read_text(encoding="utf-8")
        assert "with ag.ronde(" in bron
        assert CONTROLE._runnerpad(module.NAAM) == str(Path(module.__file__))
        assert CONTROLE.n12_gebruikt_de_ronde({"naam": module.NAAM, "draait_op": "Mac"}, None)[0]
    stand = D.kanaalstand({"status": "klaar", "taak": WA.TAAK, "ts": datetime.now(timezone.utc).isoformat()},
                          datetime.now(timezone.utc))
    assert stand == "aangesloten"
    assert not (RUNNER / "mac" / "whatsapp_wacht.py").exists()


def test_n4_vergelijkt_de_ronde_id_bij_elke_cadans():
    vers = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    for naam in ("whatsapp-wacht", "belwacht"):
        rij_ = {"naam": naam, "cadans": "elk uur als de Mac wakker is", "kennis_ts": vers, "draait_op": "Mac",
                "kennis": f"werkwijze op het bord: 10 tekens, abcdef12\nronde-id-{'a' * 32}: 0 tekens, e3b0c442"}
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE status(naam TEXT PRIMARY KEY, status TEXT, ts TEXT, taak TEXT, detail TEXT)")
        con.execute("INSERT INTO status VALUES(?,?,?,?,?)", (naam, "klaar", vers, "databank", f"x; ronde-id:{'a' * 32}"))
        assert CONTROLE.n4_kennis_gemeld(rij_, con)[0]
        con.execute("UPDATE status SET detail=?", (f"x; ronde-id:{'b' * 32}",))
        assert not CONTROLE.n4_kennis_gemeld(rij_, con)[0]
        con.execute("UPDATE status SET detail=?, status='fout'", (f"x; ronde-id:{'a' * 32}",))
        assert not CONTROLE.n4_kennis_gemeld(rij_, con)[0]
        oud = (datetime.now(timezone.utc) - timedelta(days=9)).isoformat()
        con.execute("UPDATE status SET status='klaar'")
        assert not CONTROLE.n4_kennis_gemeld({**rij_, "kennis_ts": oud}, con)[0]
        assert CONTROLE.n4_kennis_gemeld({**rij_, "kennis_ts": oud, "cadans": "op verzoek"}, con)[0]
    andere = {"naam": "andere-agent", "cadans": "op verzoek", "kennis_ts": vers, "kennis": "werkwijze gemeld"}
    assert CONTROLE.n4_kennis_gemeld(andere, sqlite3.connect(":memory:"))[0]


def test_bevestiging_met_de_ronde_id():
    with tempfile.TemporaryDirectory() as map_:
        db = os.path.join(map_, "bord.db")
        con = sqlite3.connect(db)
        con.executescript("CREATE TABLE status(naam TEXT PRIMARY KEY, status TEXT, ts TEXT, detail TEXT);"
                          "CREATE TABLE agent(naam TEXT PRIMARY KEY, kennis_ts TEXT, kennis TEXT);"
                          "CREATE TABLE nood(naam TEXT, tekst TEXT, open INTEGER);")
        con.execute("INSERT INTO status VALUES('belwacht', 'fout', 'nu', ?)",
                    ("Bord heeft de ronde niet bevestigd; ronde-id:" + "a" * 32,))
        con.execute("INSERT INTO agent VALUES('belwacht', 'nu', 'werkwijze: 1 tekens, x')")
        con.executemany("INSERT INTO nood VALUES(?,?,?)", [("belwacht", M.NIET_BEVESTIGD, 1),
                                                           ("belwacht", "Opgelost", 0), ("ander", "Andere", 1)])
        con.commit()
        con.close()
        stand = bordstand.stand("belwacht", db, met_ronde=True)
    assert stand["status_ronde"] == "a" * 32 and stand["noden"] == [M.NIET_BEVESTIGD], stand
    juist = {"status": "klaar", "status_ronde": "a" * 32, "kennis_ronde": "a" * 32}
    assert M.bevestigd(juist, "a" * 32)
    assert not M.bevestigd(None, "a" * 32)
    assert not M.bevestigd({**juist, "kennis_ronde": "b" * 32}, "a" * 32)
    assert not M.bevestigd({**juist, "status": "fout"}, "a" * 32)


def test_masker_laat_een_ronde_id_heel():
    # 'Cafe' en 'beef' zijn zuivere hexcode: in het masker zouden ze een ronde-ID kunnen breken
    woorden = M.maskerwoorden([{"personen": "groep: Cafe"}, {"personen": "groep: Familie Proef"},
                               {"personen": "Jan Proef, Piet Proef"}, {"personen": "+32470000099"}, {"personen": "beef"}])
    assert woorden == {"Familie Proef", "Jan Proef", "Piet Proef", "+32470000099"}, woorden


def test_werkwijzen_hebben_grenzen():
    for naam in ("whatsapp-wacht", "belwacht", "sms-wacht"):
        tekst = (RUNNER / "werkwijze" / f"{naam}.md").read_text(encoding="utf-8")
        nooit, beslist = bord.grenzen(tekst)
        assert len(tekst) >= 500 and nooit and beslist, naam
        assert "–" not in tekst and "—" not in tekst


# ----------------------------------------------------------------------------------- de helper zelf ---
def _bouw_helper(map_):
    """De testbouw leest onder map_/thuis. map_ zonder symlink (op macOS is /var een symlink): de helper weigert er een."""
    if sys.platform != "darwin" or not shutil.which("cc"):
        return None
    uit = os.path.join(map_, "kopie")
    r = subprocess.run(["cc", "-O2", "-Wall", "-Wextra", "-Werror", f'-DBASIS_TEST="{map_}/thuis"', "-o", uit,
                        str(HELPER_C), "-lsqlite3"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return uit


def _bron_wa(thuis, met_wal=True, schema_fout=False):
    wa = Path(thuis, "Library/Group Containers/group.net.whatsapp.WhatsApp.shared")
    wa.mkdir(parents=True)
    Path(thuis, "Library/Caches").mkdir(mode=0o700)
    chat = sqlite3.connect(wa / "ChatStorage.sqlite")
    chat.execute("PRAGMA journal_mode=WAL")
    chat.execute("PRAGMA wal_autocheckpoint=0")
    chat.executescript(f"""
        CREATE TABLE ZWAMESSAGE(Z_PK INTEGER PRIMARY KEY, ZCHATSESSION, ZMESSAGEDATE, ZISFROMME, ZMESSAGETYPE,
                                {'ZSTANZA' if schema_fout else 'ZSTANZAID'}, ZTEXT);
        CREATE TABLE ZWACHATSESSION(Z_PK INTEGER PRIMARY KEY, ZCONTACTJID, ZPARTNERNAME, ZSESSIONTYPE,
                                    ZLASTMESSAGETEXT);""")
    nu = M.apple(datetime.now(timezone.utc))
    chat.execute("INSERT INTO ZWACHATSESSION VALUES(1, 'x@s.whatsapp.net', 'Jan Proef', 0, 'GEHEIM VOORBEELD')")
    chat.execute("INSERT INTO ZWAMESSAGE VALUES(1, 1, ?, 0, 0, NULL, 'GEHEIME TEKST')", (nu - 3600,))
    # U1: een status (ZSESSIONTYPE 3) met een bericht en een contact: verlaat de bron niet
    chat.execute("INSERT INTO ZWACHATSESSION VALUES(3, 's@status', 'Statusnaam Proef', 3, NULL)")
    chat.execute("INSERT INTO ZWAMESSAGE VALUES(3, 3, ?, 0, 0, NULL, NULL)", (nu - 30,))
    chat.commit()
    if met_wal:
        # een transactie die alleen in de WAL staat (P2): de verbinding blijft open, zonder checkpoint
        chat.execute("INSERT INTO ZWAMESSAGE VALUES(2, 1, ?, 1, 0, NULL, 'NOG GEHEIMER')", (nu - 60,))
        chat.commit()
    oproepen = sqlite3.connect(wa / "CallHistory.sqlite")
    oproepen.executescript("""
        CREATE TABLE ZWACDCALLEVENT(Z_PK, ZCALLIDSTRING, ZDATE, ZDURATION, Z1CALLEVENTS, ZGROUPCALLCREATORUSERJIDSTRING,
                                    ZGROUPJIDSTRING, ZBYTESSENT);
        CREATE TABLE ZWAAGGREGATECALLEVENT(Z_PK, ZINCOMING, ZMISSED, ZVIDEO, ZLINKTOKEN);
        CREATE TABLE ZWACDCALLEVENTPARTICIPANT(Z_PK, Z1PARTICIPANTS, ZJIDSTRING);""")
    oproepen.close()
    kont = sqlite3.connect(wa / "ContactsV2.sqlite")
    kont.execute("CREATE TABLE ZWAADDRESSBOOKCONTACT(Z_PK, ZFULLNAME, ZWHATSAPPID, ZLID, ZPHONENUMBER, ZABOUTTEXT)")
    kont.execute("INSERT INTO ZWAADDRESSBOOKCONTACT VALUES(1, 'Jan Proef', 'x@s.whatsapp.net', NULL, '+3247', 'STATUS')")
    kont.execute("INSERT INTO ZWAADDRESSBOOKCONTACT VALUES(2, 'Piet Proef', 'y@s.whatsapp.net', NULL, '+3248', 'S')")
    kont.execute("INSERT INTO ZWAADDRESSBOOKCONTACT VALUES(3, 'Statusnaam Proef', 's@status', NULL, '+3249', 'S')")
    kont.execute("INSERT INTO ZWAADDRESSBOOKCONTACT VALUES(4, 'Kees Proef', NULL, NULL, '+32470000001', 'S')")
    kont.execute("INSERT INTO ZWAADDRESSBOOKCONTACT VALUES(5, 'Andere App Proef', NULL, NULL, '+32470000002', 'S')")
    kont.commit()
    kont.close()
    return chat


def test_helper_leest_wal_en_schrijft_geen_tekst():
    with tempfile.TemporaryDirectory() as map_:
        map_ = os.path.realpath(map_)
        helper = _bouw_helper(map_)
        if helper is None:
            print("   (overgeslagen: geen Mac met cc)")
            return
        thuis = os.path.join(map_, "thuis")
        open_ = _bron_wa(thuis)
        doel = Path(thuis, "Library/Caches/mijnagents/mac-gesprekken/whatsapp")
        doel.mkdir(parents=True, mode=0o700)
        os.chmod(doel.parent, 0o700)
        os.chmod(doel.parent.parent, 0o755)
        (doel / "aanvraag").write_text("e" * 32)
        r = subprocess.run([helper, "whatsapp"], capture_output=True, text=True)
        open_.close()
        status = json.loads((doel / "status.json").read_text())
        assert r.returncode == 0 and status["uitkomst"] == "ok" and status["aanvraag"] == "e" * 32, (r, status)
        uit = doel / f"gesprekken-{'e' * 32}.sqlite"
        assert os.stat(uit).st_mode & 0o077 == 0 and os.stat(doel).st_mode & 0o077 == 0
        ruw = uit.read_bytes()
        for geheim in (b"GEHEIME TEKST", b"NOG GEHEIMER", b"GEHEIM VOORBEELD", b"STATUS", b"Piet Proef",
                       b"Statusnaam Proef", b"s@status"):
            assert geheim not in ruw, geheim
        rijen, info = M.whatsapp_rijen(uit, M.dagen(datetime.now(timezone.utc)))
        assert sum(int(x["thema"].split()[0]) for x in rijen) == 2, rijen      # ook het bericht uit de WAL
        assert M.lees(uit, M.SQL_NIEUWSTE)[0][0] < M.apple(datetime.now(timezone.utc)) - 50   # niet die van de status
        assert rijen[0]["personen"] == "Jan Proef"
        assert "Jan Proef" not in r.stdout                                     # stdout is alleen de status


def test_helper_sms_schrijft_geen_tekst():
    """De set sms (31-10-2026): alleen gesprek, tijd, richting en dienst; geen tekst, geen reactie, geen oude dag."""
    with tempfile.TemporaryDirectory() as map_:
        map_ = os.path.realpath(map_)
        helper = _bouw_helper(map_)
        if helper is None:
            print("   (overgeslagen: geen Mac met cc)")
            return
        thuis = os.path.join(map_, "thuis")
        Path(thuis, "Library/Messages").mkdir(parents=True)
        Path(thuis, "Library/Caches").mkdir(mode=0o700)
        db = sqlite3.connect(Path(thuis, "Library/Messages/chat.db"))
        db.executescript("""
            CREATE TABLE message(ROWID INTEGER PRIMARY KEY, text, attributedBody, handle_id, service, date, is_from_me,
                                 item_type, associated_message_type);
            CREATE TABLE chat(ROWID INTEGER PRIMARY KEY, style, chat_identifier, display_name);
            CREATE TABLE handle(ROWID INTEGER PRIMARY KEY, id);
            CREATE TABLE chat_message_join(chat_id, message_id);
            CREATE TABLE chat_handle_join(chat_id, handle_id);
            INSERT INTO handle VALUES(1, '+32470000001'), (2, '+32470000099');
            INSERT INTO chat VALUES(1, 45, '+32470000001', ''), (2, 43, 'chat1', 'Werfgroep Proef');
            INSERT INTO chat_handle_join VALUES(1, 1), (2, 1), (2, 2);""")
        nu = M.apple(datetime.now(timezone.utc))
        for rid, chat, tekst, dienst, t, mij, soort, reactie in (
                (1, 1, "GEHEIME TEKST", "SMS", nu - 3600, 0, 0, 0), (2, 1, "NOG GEHEIMER", "SMS", nu - 3500, 1, 0, 0),
                (3, 2, "GROEPSGEHEIM", "iMessage", nu - 60, 1, 0, 0), (4, 2, "REACTIEGEHEIM", "iMessage", nu - 50, 0, 0, 2000),
                (5, 2, "NAAMGEHEIM", "iMessage", nu - 40, 0, 2, 0), (6, 1, "OUDGEHEIM", "SMS", nu - 90 * 86400, 0, 0, 0)):
            db.execute("INSERT INTO message VALUES(?,?,?,?,?,?,?,?,?)",
                       (rid, tekst, tekst.encode(), 1, dienst, int(t * 1e9), mij, soort, reactie))
            db.execute("INSERT INTO chat_message_join VALUES(?,?)", (chat, rid))
        db.commit()
        db.close()
        wa = Path(thuis, "Library/Group Containers/group.net.whatsapp.WhatsApp.shared")
        wa.mkdir(parents=True)
        kont = sqlite3.connect(wa / "ContactsV2.sqlite")
        kont.execute("CREATE TABLE ZWAADDRESSBOOKCONTACT(Z_PK, ZFULLNAME, ZWHATSAPPID, ZLID, ZPHONENUMBER)")
        kont.execute("INSERT INTO ZWAADDRESSBOOKCONTACT VALUES(1, 'Jan Proef', NULL, NULL, '0470 00 00 01')")
        kont.execute("INSERT INTO ZWAADDRESSBOOKCONTACT VALUES(2, 'Buiten Proef', NULL, NULL, '+32479999999')")
        kont.commit()
        kont.close()
        doel = Path(thuis, "Library/Caches/mijnagents/mac-gesprekken/sms")
        doel.mkdir(parents=True, mode=0o700)
        os.chmod(doel.parent, 0o700)
        os.chmod(doel.parent.parent, 0o755)
        (doel / "aanvraag").write_text("f" * 32)
        r = subprocess.run([helper, "sms"], capture_output=True, text=True)
        status = json.loads((doel / "status.json").read_text())
        assert r.returncode == 0 and status["uitkomst"] == "ok", (r, status)
        uit = doel / f"gesprekken-{'f' * 32}.sqlite"
        ruw = uit.read_bytes()
        for geheim in (b"GEHEIM", b"Buiten Proef"):
            assert geheim not in ruw, geheim
        rijen, _ = M.sms_rijen(uit, M.dagen(datetime.now(timezone.utc)))
        assert sum(int(x["thema"].split()[0]) for x in rijen) == 3, rijen
        assert {x["personen"] for x in rijen} == {"Jan Proef", "groep: Werfgroep Proef"}, rijen


def test_u1_helper_laat_andere_apps_weg():
    with tempfile.TemporaryDirectory() as map_:
        map_ = os.path.realpath(map_)
        helper = _bouw_helper(map_)
        if helper is None:
            print("   (overgeslagen: geen Mac met cc)")
            return
        thuis = os.path.join(map_, "thuis")
        _bron_wa(thuis, met_wal=False).close()
        geschiedenis = Path(thuis, "Library/Application Support/CallHistoryDB")
        geschiedenis.mkdir(parents=True)
        con = sqlite3.connect(geschiedenis / "CallHistory.storedata")
        con.execute("CREATE TABLE ZCALLRECORD(ZUNIQUE_ID, ZDATE, ZDURATION, ZORIGINATED, ZANSWERED, ZADDRESS, "
                    "ZSERVICE_PROVIDER, ZNAME)")
        nu = M.apple(datetime.now(timezone.utc))
        con.executemany("INSERT INTO ZCALLRECORD VALUES(?,?,?,?,?,?,?,NULL)", [
            ("T1", nu - 600, 60.0, 1, 0, "0470000001", "com.apple.Telephony"),
            ("W1", nu - 300, 60.0, 0, 1, "+32470000002", "net.whatsapp.WhatsApp")])
        con.commit()
        con.close()
        doel = Path(thuis, "Library/Caches/mijnagents/mac-gesprekken/telefoon")
        doel.mkdir(parents=True, mode=0o700)
        os.chmod(doel.parent, 0o700)
        (doel / "aanvraag").write_text("c" * 32)
        status = json.loads(subprocess.run([helper, "telefoon"], capture_output=True, text=True).stdout)
        assert status["uitkomst"] == "ok", status
        uit = doel / f"gesprekken-{'c' * 32}.sqlite"
        ruw = uit.read_bytes()
        assert b"Andere App Proef" not in ruw and b"W1" not in ruw and b"net.whatsapp" not in ruw
        rijen, info = M.telefoon_rijen(uit, M.dagen(datetime.now(timezone.utc)))
        assert [r["personen"] for r in rijen] == ["Kees Proef"] and info["overgeslagen"] == 1, (rijen, info)
        # V3: de oproepen van andere apps tellen alleen in het eigen venster (een dag lang geleden: geen)
        assert M.telefoon_rijen(uit, ["2020-01-01"])[1]["overgeslagen"] == 0
        assert b"470000002" not in ruw
        assert M.lees(uit, M.SQL_NIEUWSTE)[0][0] == nu - 600


def test_helper_weigert_symlink_en_meldt_ander_schema():
    with tempfile.TemporaryDirectory() as map_:
        map_ = os.path.realpath(map_)
        helper = _bouw_helper(map_)
        if helper is None:
            print("   (overgeslagen: geen Mac met cc)")
            return
        thuis = os.path.join(map_, "thuis")
        _bron_wa(thuis, met_wal=False, schema_fout=True).close()
        r = subprocess.run([helper, "whatsapp"], capture_output=True, text=True)
        status = json.loads(r.stdout)
        assert status["uitkomst"] == "onverwacht" and r.returncode == 1, status
        doel = Path(thuis, "Library/Caches/mijnagents/mac-gesprekken/whatsapp")
        assert not list(doel.glob("gesprekken*.sqlite"))
        # een symlink in het bronpad
        wa = Path(thuis, "Library/Group Containers/group.net.whatsapp.WhatsApp.shared")
        os.rename(wa / "ChatStorage.sqlite", wa / "ander.sqlite")
        os.symlink(wa / "ander.sqlite", wa / "ChatStorage.sqlite")
        status = json.loads(subprocess.run([helper, "whatsapp"], capture_output=True, text=True).stdout)
        assert status["bronnen"]["chat"] == "onverwacht", status
        # een bron die ontbreekt (telefoon: geen CallHistoryDB in de proefmap)
        status = json.loads(subprocess.run([helper, "telefoon"], capture_output=True, text=True).stdout)
        assert status["bronnen"]["oproepen"] == "ontbreekt" and status["uitkomst"] == "ontbreekt", status
        # een vreemde aanvraag wordt niet herhaald
        (doel / "aanvraag").write_text("../../etc " + "a" * 22)
        status = json.loads(subprocess.run([helper, "whatsapp"], capture_output=True, text=True).stdout)
        assert status["aanvraag"] == "", status


# ------------------------------------------------------------------------------------- bouwcontrole r2 ---
def test_q1_dubbele_oproep_id_overschrijft_niets():
    with tempfile.TemporaryDirectory() as map_:
        pad = maak_telefoon(os.path.join(map_, "tel.sqlite"), [
            ("ZELFDE", a(bxl(2026, 10, 22, 8, 0)), 60.0, 1, 0, "0470000001", "com.apple.Telephony"),
            ("ZELFDE", a(bxl(2026, 10, 22, 9, 0)), 120.0, 1, 0, "0470000001", "com.apple.Telephony")],
            nieuwste=a(bxl(2026, 10, 23, 7, 0)))
        rijen, _ = M.telefoon_rijen(pad, DAGEN)
    sleutels = [r["uniek"] for r in rijen]
    assert len(set(sleutels)) == 2 and all(s.startswith("telefoon:ZELFDE-") for s in sleutels), sleutels
    b = NepBord()
    M.schrijf_en_lees_terug("telefoon", rijen, DAG, DAG, b.call, b.terug)
    assert len(b.tabel) == 2
    try:
        M.schrijf_en_lees_terug("telefoon", rijen + rijen[:1], DAG, DAG, b.call, b.terug)
    except M.MacFout as e:
        assert e.nood.startswith("Twee rijen met dezelfde sleutel")
    else:
        raise AssertionError("dubbele sleutel geschreven")


def test_q2_grens_van_vervallen():
    def proef(op_bord, bron):
        b = NepBord()
        M.schrijf_en_lees_terug("telefoon", [rij(tel(i)) for i in range(op_bord)], DAG, DAG, b.call, b.terug)
        try:
            return M.schrijf_en_lees_terug("telefoon", [rij(tel(i)) for i in range(bron)], DAG, DAG, b.call,
                                           b.terug)
        except M.MacFout:
            return "stop"
    assert proef(5, 0) == "stop"            # een lege bron en vijf rijen op het bord (de geheugenproef van Codex)
    assert proef(1, 0) == "stop"            # een lege bron is altijd verdacht
    assert proef(20, 15) == "stop"          # vijf van twintig: meer dan een vijfde
    assert proef(100, 95) == 5              # vijf van honderd: gewoon vervallen
    assert proef(10, 6) == 4                # vier: onder de grens van vijf
    # alleen dekking is geen gegeven
    b = NepBord()
    M.schrijf_en_lees_terug("telefoon", [rij(tel(1))], DAG, DAG, b.call, b.terug)
    try:
        M.schrijf_en_lees_terug("telefoon", [rij("dekking:telefoon:" + DAG, bron="dekking", dubbel_van=M.DEKKING)],
                                DAG, DAG, b.call, b.terug)
    except M.MacFout:
        pass
    else:
        raise AssertionError("bron met alleen dekking markeerde rijen als vervallen")


def test_s1_t1_rem_voor_het_schrijven_ook_bij_andere_sleutels():
    """Codex S1 en T1: rijen met een andere sleutelvorm (er staan er live geen) tellen gewoon mee in de rem; een volle,
    lege of halve bron tegenover vijf zulke rijen schrijft en markeert niets. Nooit een dubbele telling of stil verlies."""
    for bron in ([rij(tel(i)) for i in range(5)], [], [rij(tel(1))]):
        b = NepBord()
        for u in ("telefoon:U1", "telefoon:U2", "telefoon:ID-42", "telefoon:U4", "telefoon:U5"):
            b.tabel[u] = rij(u)
        voor = dict(b.tabel)
        try:
            M.schrijf_en_lees_terug("telefoon", bron, DAG, DAG, b.call, b.terug)
        except M.MacFout as e:
            assert e.nood == "De bron toont veel minder rijen dan het bord kent: niets geschreven of gemarkeerd"
        else:
            raise AssertionError(len(bron))
        assert b.tabel == voor and not b.oproepen, (len(bron), b.oproepen)
    # een enkele verdwenen rij van honderd: gewoon vervallen
    b = NepBord()
    M.schrijf_en_lees_terug("telefoon", [rij(tel(i)) for i in range(100)], DAG, DAG, b.call, b.terug)
    assert M.schrijf_en_lees_terug("telefoon", [rij(tel(i)) for i in range(99)], DAG, DAG, b.call, b.terug) == 1


def test_v1_vervallen_dekking_is_geen_bewijs():
    """Codex V1, de hele route: een dag waarvan alle oproepen uit de bron verdwijnen, verliest ook zijn dekking; De
    Dagbundelaar toont die dag dan als onbekend, nooit als '0 oproepen gezien'."""
    dagen = ["2026-10-21", DAG, "2026-10-23"]
    gekopieerd = bxl(2026, 10, 24, 9, 0)

    def ronde(map_, b, met_dag):
        oproepen = [(f"U{d}{u}", a(bxl(2026, 10, d, 9 + u, 0)), 120.0, 1, 0, "0470000001", "com.apple.Telephony")
                    for d in (21, 22, 23) if met_dag or d != 22 for u in range(3)]
        pad = maak_telefoon(os.path.join(map_, f"tel-{met_dag}.sqlite"), oproepen, nieuwste=a(bxl(2026, 10, 24, 8, 0)))
        rijen, info = M.telefoon_rijen(pad, dagen)
        rijen += M.dekking("telefoon", dagen, gekopieerd, info["nieuwste"], info["aanwezig"])
        return M.schrijf_en_lees_terug("telefoon", rijen, dagen[0], dagen[-1], b.call, b.terug)

    b = NepBord()
    with tempfile.TemporaryDirectory() as map_:
        assert ronde(map_, b, True) == 0
        assert ronde(map_, b, False) == 4                       # drie oproepen en de dekking van 22-10
    rijen = list(b.tabel.values())
    assert b.tabel[f"dekking:telefoon:{DAG}"]["dubbel_van"] == M.VERVALLEN
    gedekt = D.gedekte_dagen(rijen)
    assert gedekt == {("telefoon", "2026-10-21"), ("telefoon", "2026-10-23")}, gedekt
    stand = D.kanaal_van_dag("aangesloten", "telefoon", DAG, gedekt)
    tekst = V.tekst(V.vaststellen(DAG, [], [], rijen, {}, [], "volledig", None, {"whatsapp": "niet aangesloten",
                                  "telefoon": stand}, lambda x: False))
    assert "- telefoon: onbekend (onbekend voor deze dag)" in tekst, tekst


def test_w1_oudere_dag_die_zijn_dekking_verliest_wordt_opnieuw_vastgesteld():
    """Codex W1: een dag buiten het nachtvenster, al vastgesteld met een telling, verliest later zijn dekking (een
    inhaalronde van de Mac verklaart ze vervallen, met een nieuwere ts). De nacht kiest die dag opnieuw, en dan toont
    het overzicht 'onbekend' in plaats van de oude telling."""
    nu = datetime(2026, 10, 26, 23, 30, tzinfo=timezone.utc)
    oud = "2026-10-01"
    vastgesteld = (nu - timedelta(days=20)).isoformat()
    # de dekking vervalt alleen als de dag geen oproep meer toont: ook zijn oproep is dan vervallen
    rijen = [dict(rij(tel(1), dag=oud, dubbel_van=M.VERVALLEN), ts=(nu - timedelta(hours=2)).isoformat()),
             dict(rij(f"dekking:telefoon:{oud}", dag=oud, bron="dekking", dubbel_van=M.VERVALLEN),
                  ts=(nu - timedelta(hours=2)).isoformat())]
    with tempfile.TemporaryDirectory() as map_:
        oud_staat, oud_inhaal, oud_lees = D.STAAT, D.INHAALSTAAT, bord.db_lees
        D.STAAT, D.INHAALSTAAT = os.path.join(map_, "staat.json"), os.path.join(map_, "inhaal.json")
        try:
            with open(D.STAAT, "w") as f:
                json.dump({oud: {"versie": 1, "ts": vastgesteld}}, f)

            def lees(sql, args=()):
                assert "bron = 'dekking'" in sql and "vervallen" not in sql, sql
                return [{"datum": oud, "ts": max(r["ts"] for r in rijen if r["bron"] == "dekking")}]
            bord.db_lees = lees
            assert D.inhaaldagen(nu, V.venster(nu, D.NACHTVENSTER)) == [oud]
        finally:
            D.STAAT, D.INHAALSTAAT, bord.db_lees = oud_staat, oud_inhaal, oud_lees
    stand = D.kanaal_van_dag("aangesloten", "telefoon", oud, D.gedekte_dagen(rijen))
    tekst = V.tekst(V.vaststellen(oud, [], [], rijen, {}, [], "volledig", None,
                                  {"whatsapp": "niet aangesloten", "telefoon": stand}, lambda x: False))
    assert "- telefoon: onbekend (onbekend voor deze dag)" in tekst, tekst


def test_wa8_gelezen_dag_blijft_aangesloten_als_de_wacht_nu_stil_is():
    """WA-8: een dag met een dekkingsrij is gelezen, ook als de wacht nu langer dan KANAAL_UREN zweeg (de laptop stond
    uit): die dag blijft 'aangesloten' en wordt geen 'stil sinds ...'. Alleen een dag zonder dekkingsrij krijgt de stand
    van nu. Een vervallen dekkingsrij bewijst niets (Codex V1)."""
    nu = datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc)
    stil = D.kanaalstand({"status": "klaar", "taak": WA.TAAK, "ts": (nu - timedelta(hours=40)).isoformat()}, nu)
    assert stil.startswith("stil sinds"), stil
    rijen = [{"uniek": f"dekking:whatsapp:{DAG}", "datum": DAG, "dubbel_van": M.DEKKING},
             {"uniek": "dekking:whatsapp:2026-10-21", "datum": "2026-10-21", "dubbel_van": M.VERVALLEN}]
    gedekt = D.gedekte_dagen(rijen)
    assert D.kanaal_van_dag(stil, "whatsapp", DAG, gedekt) == "aangesloten"
    assert D.kanaal_van_dag(stil, "whatsapp", "2026-10-23", gedekt) == stil           # zonder dekking: de stand van nu
    assert D.kanaal_van_dag(stil, "whatsapp", "2026-10-21", gedekt) == stil           # vervallen dekking: geen bewijs
    assert D.kanaal_van_dag(stil, "telefoon", DAG, gedekt) == stil                    # dekking van een ander kanaal
    assert D.kanaal_van_dag("aangesloten", "whatsapp", "2026-10-23", gedekt) == "onbekend voor deze dag"
    assert D.kanaal_van_dag("niet aangesloten", "whatsapp", "2026-10-23", gedekt) == "niet aangesloten"
    rij = {"uniek": "whatsapp:0a1b:" + DAG, "datum": DAG, "start": "09:00", "minuten": 0, "personen": JAN,
           "thema": "3 berichten (1 in, 2 uit), 09:00 tot 09:30", "prive": 1, "bron": "whatsapp", "dubbel_van": ""}
    tekst = V.tekst(V.vaststellen(DAG, [], [], [rij], {}, [], "volledig", None,
                                  {"whatsapp": D.kanaal_van_dag(stil, "whatsapp", DAG, gedekt)}, lambda x: False))
    assert "- WhatsApp: 3 berichten in 1 gesprekken, 0 oproepen, 0 min gezien\n" in tekst + "\n", tekst


def test_q5_kapotte_waarde_komt_niet_in_de_fout():
    with tempfile.TemporaryDirectory() as map_:
        pad = maak_telefoon(os.path.join(map_, "tel.sqlite"), [
            ("U1", "Jan Proef 0470000001", 60.0, 1, 0, "0470000001", "com.apple.Telephony")])
        try:
            M.lees_veilig(M.telefoon_rijen, pad, DAGEN)
        except M.MacFout as e:
            tekst = f"{e} {e.nood} {e.__cause__} {e.__context__ if not e.__suppress_context__ else ''}"
        else:
            raise AssertionError("kapotte waarde gelezen")
    assert "Jan Proef" not in tekst and "0470000001" not in tekst and "ValueError" in tekst, tekst


def test_q6_eindcontrole_zet_fout_met_nood():
    class Ag:
        def __init__(self):
            self.slagen = []

        def noden_bij_breuk(self, nieuw):
            return [{"tekst": "Een oude nood", "wie": "mehdi"}] + nieuw

        def hartslag(self, status, taak="", detail="", nood=None):
            self.slagen.append((status, detail, nood))

    ag = Ag()
    standen = iter([{"status": "klaar", "status_ronde": "a" * 32, "kennis_ronde": "a" * 32}])
    assert M.eindcontrole(ag, "belwacht", "t", "a" * 32, stand=lambda n: next(standen)) and not ag.slagen
    gemeld = []
    for na, bevestigd in (({"status": "fout", "status_ronde": "a" * 32, "noden": [M.NIET_BEVESTIGD]}, True),
                          ({"status": "fout", "status_ronde": "b" * 32, "noden": [M.NIET_BEVESTIGD]}, False),
                          ({"status": "fout", "status_ronde": "a" * 32, "noden": []}, False),
                          ({"status": "klaar", "status_ronde": "b" * 32}, False)):   # de fout kwam niet aan (R3)
        standen = iter([{"status": "klaar", "status_ronde": "b" * 32, "kennis_ronde": "a" * 32}, na])
        uit = io.StringIO()
        with redirect_stdout(uit):
            assert not M.eindcontrole(ag, "belwacht", "t", "a" * 32, stand=lambda n: next(standen))
        gemeld.append(("staat niet op het bord" in uit.getvalue()) != bevestigd)
    assert all(gemeld), gemeld
    status, detail, nood = ag.slagen[-1]
    assert detail.endswith("; ronde-id:" + "a" * 32), detail
    assert status == "fout" and {"tekst": "Bord heeft de ronde niet bevestigd: hartslag of kennis ontbreekt",
                                 "wie": "claude-code"} in nood and nood[0]["tekst"] == "Een oude nood"
    for module in (WA, BEL):
        assert "M.eindcontrole(ag, NAAM, TAAK, ronde_id)" in Path(module.__file__).read_text(encoding="utf-8")


def test_q3_helper_leest_geen_verwisselde_bron():
    with tempfile.TemporaryDirectory() as map_:
        map_ = os.path.realpath(map_)
        helper = _bouw_helper(map_)
        if helper is None:
            print("   (overgeslagen: geen Mac met cc)")
            return
        thuis = os.path.join(map_, "thuis")
        _bron_wa(thuis, met_wal=False).close()
        wa = Path(thuis, "Library/Group Containers/group.net.whatsapp.WhatsApp.shared")
        shutil.copy(wa / "ChatStorage.sqlite", wa / "ChatStorage.sqlite.wissel")
        status = json.loads(subprocess.run([helper, "whatsapp"], capture_output=True, text=True).stdout)
        assert status["bronnen"]["chat"] == "onverwacht" and status["uitkomst"] == "onverwacht", status
        doel = Path(thuis, "Library/Caches/mijnagents/mac-gesprekken/whatsapp")
        assert not list(doel.glob("gesprekken*.sqlite"))
        # zonder wissel: gewoon gelezen, en de uitvoer draagt de aanvraag-ID (Q4)
        (doel / "aanvraag").write_text("9" * 32)
        status = json.loads(subprocess.run([helper, "whatsapp"], capture_output=True, text=True).stdout)
        assert status["uitkomst"] == "ok", status
        assert M.lees(doel / f"gesprekken-{'9' * 32}.sqlite", M.SQL_AANVRAAG) == [("9" * 32,)]
        # R2: een tweede aanvraag krijgt haar eigen uitvoer; de eerste blijft wat ze was
        (doel / "aanvraag").write_text("8" * 32)
        subprocess.run([helper, "whatsapp"], capture_output=True, text=True, check=True)
        assert M.lees(doel / f"gesprekken-{'9' * 32}.sqlite", M.SQL_AANVRAAG) == [("9" * 32,)]
        assert M.lees(doel / f"gesprekken-{'8' * 32}.sqlite", M.SQL_AANVRAAG) == [("8" * 32,)]
        # wat ouder is dan tien minuten, ruimt de volgende start op; alleen de eigen uitvoernamen (S2)
        oud = time.time() - 900
        for naam in (f"gesprekken-{'9' * 32}.sqlite", "gesprekken-archief.sqlite", f".lezen-{'7' * 32}.sqlite"):
            (doel / naam).touch()
            os.utime(doel / naam, (oud, oud))
        subprocess.run([helper, "whatsapp"], capture_output=True, text=True, check=True)
        assert not (doel / f"gesprekken-{'9' * 32}.sqlite").exists() and not (doel / f".lezen-{'7' * 32}.sqlite").exists()
        assert (doel / "gesprekken-archief.sqlite").exists()


# ------------------------------------------------------------------------------------- bouwcontrole r3 ---
def test_r1_sleutels_blijven_als_het_venster_opschuift():
    with tempfile.TemporaryDirectory() as map_:
        tel = maak_telefoon(os.path.join(map_, "tel.sqlite"), [
            ("ZELFDE", a(bxl(2026, 10, 21, 8, 0)), 60.0, 1, 0, "0470000001", "com.apple.Telephony"),
            ("ZELFDE", a(bxl(2026, 10, 22, 9, 0)), 120.0, 1, 0, "0470000001", "com.apple.Telephony")],
            nieuwste=a(bxl(2026, 10, 23, 7, 0)))
        wa = maak_whatsapp(os.path.join(map_, "wa.sqlite"), oproepen=[
            (1, "ID1", a(bxl(2026, 10, 21, 23, 0)), 60.0, 9, None, None),
            (2, "ID1", a(bxl(2026, 10, 22, 1, 0)), 60.0, 9, None, None),       # opnieuw verbonden, over middernacht
            (3, "ID1", a(bxl(2026, 10, 22, 9, 0)), 60.0, 9, None, None)],      # dezelfde ID, een andere oproep
            aggregaten=[(9, 0, 0, 0)], nieuwste=a(bxl(2026, 10, 23, 7, 0)))
        voor_t = {r["uniek"]: r for r in M.telefoon_rijen(tel, ["2026-10-21", DAG])[0]}
        na_t = {r["uniek"]: r for r in M.telefoon_rijen(tel, [DAG, "2026-10-23"])[0]}
        voor_w = {r["uniek"]: r for r in M.whatsapp_rijen(wa, ["2026-10-21", DAG])[0]}
        na_w = {r["uniek"]: r for r in M.whatsapp_rijen(wa, [DAG, "2026-10-23"])[0]}
    assert len(voor_t) == 2 and set(na_t) < set(voor_t), (voor_t, na_t)
    assert all(na_t[u] == voor_t[u] for u in na_t)
    assert len(voor_w) == 2 and set(na_w) < set(voor_w) and len(na_w) == 1, (sorted(voor_w), sorted(na_w))
    groep = voor_w[f"whatsapp-oproep:ID1-{int(a(bxl(2026, 10, 21, 23, 0)))}"]
    assert groep["minuten"] == 2 and groep["datum"] == "2026-10-21", groep


def test_r5_proefronde_eist_een_eigen_bevestigde_ronde():
    with tempfile.TemporaryDirectory() as map_:
        def runner(naam, uitvoer, code):
            pad = Path(map_, naam)
            pad.write_text(f"import sys\nprint({uitvoer!r})\nsys.exit({code})\n")
            return pad
        goed = runner("goed.py", "x: ronde gelukt, ronde-id:" + "a" * 32, 0)
        bezet = runner("bezet.py", "er loopt al een ronde", M.BEZET)
        stil = runner("stil.py", "", 0)
        juist = {"status": "klaar", "status_ronde": "a" * 32, "kennis_ronde": "a" * 32}
        assert M.proefronde(goed, "belwacht", stand=lambda n: juist) == "a" * 32
        for pad, stand in ((bezet, juist), (stil, juist), (goed, {**juist, "kennis_ronde": "b" * 32})):
            try:
                M.proefronde(pad, "belwacht", stand=lambda n: stand)
            except M.MacFout:
                pass
            else:
                raise AssertionError(pad)
    for module in (WA, BEL):
        bron = Path(module.__file__).read_text(encoding="utf-8")
        assert "return M.BEZET" in bron and "ronde gelukt, ronde-id:{ronde_id}" in bron


def test_r6_drie_uitrollen_en_terug():
    """De uitrol met nagebootste launchctl, codesign en cc: drie versies na elkaar, dan terug naar de vorige als
    geheel (code, helper, LaunchAgents); de wachten gaan uit voor elke wissel en aan alleen met een proefbewijs."""
    if not shutil.which("zsh") or not shutil.which("git"):
        print("   (overgeslagen: geen zsh of git)")
        return
    with tempfile.TemporaryDirectory() as map_:
        m = Path(os.path.realpath(map_))
        log = m / "launchctl.log"
        stub = m / "stub"
        stub.mkdir()
        geladen = m / "geladen"
        (stub / "launchctl").write_text(f"#!/bin/sh\necho \"$*\" >> '{log}'\nif [ \"$1\" = print ]; then\n"
                                        f"  case \"$2\" in *wacht) [ -f '{geladen}' ] && exit 0;; esac\n  exit 1\nfi\nexit 0\n")
        (stub / "codesign").write_text("#!/bin/sh\n[ \"$1\" = -dv ] && echo \"CDHash=$(shasum \"$2\" | cut -c1-8)\" >&2\nexit 0\n")
        (stub / "cc").write_text("#!/bin/sh\nwhile [ $# -gt 0 ]; do case $1 in -o) uit=$2; shift;; *.c) bron=$1;; esac; shift; done\n"
                                 "cp \"$bron\" \"$uit\"; chmod +x \"$uit\"\n")
        for s in stub.iterdir():
            s.chmod(0o755)
        oorsprong, repo = m / "oorsprong", m / "repo"

        def git(*args, cwd=oorsprong):
            return subprocess.run(["git", "-c", "user.email=p@p", "-c", "user.name=p", *args], cwd=cwd, check=True,
                                  capture_output=True, text=True).stdout.strip()
        oorsprong.mkdir()
        git("init", "-q", "-b", "main")
        mac = oorsprong / "mijnagents-runner" / "mac"
        (mac / "kopie").mkdir(parents=True)
        shas = []
        for versie, helper in (("1", "a"), ("2", "b"), ("3", "b")):
            (mac / "kopie" / "macgesprekken_kopie.c").write_text(f"helper {helper}\n")
            for l in ("kopie-whatsapp", "kopie-telefoon", "whatsapp-wacht", "belwacht"):
                (mac / f"be.globaal.mijnagents.{l}.plist").write_text(f"{l} versie {versie}\n")
            git("add", "-A")
            git("commit", "-q", "-m", f"v{versie}")
            shas.append(git("rev-parse", "HEAD"))
        git("clone", "-q", str(oorsprong), str(repo), cwd=m)
        script = RUNNER / "mac" / "uitrol_mac_gesprekken.sh"
        basis, agents = m / "basis", m / "agents"
        omgeving = {**os.environ, "REPO": str(repo), "BASIS": str(basis), "AGENTS": str(agents), "LOGS": str(m / "logs"),
                    "LAUNCHCTL": str(stub / "launchctl"), "CODESIGN": str(stub / "codesign"), "CC": str(stub / "cc")}

        def uitrol(*args, ref=None, ok=True):
            r = subprocess.run(["zsh", str(script), *args], env={**omgeving, **({"REF": ref} if ref else {})},
                               capture_output=True, text=True)
            assert (r.returncode == 0) == ok, (args, r.stdout, r.stderr)
            return r.stdout + r.stderr
        werk, helper = basis / "repo", basis / "mac-gesprekken" / "MacGesprekkenKopie"
        for i, sha in enumerate(shas):
            log.write_text("")
            uit = uitrol(ref=sha)
            assert git("rev-parse", "HEAD", cwd=werk) == sha
            assert helper.read_text() == ("helper a\n" if i == 0 else "helper b\n")
            assert (agents / "be.globaal.mijnagents.belwacht.plist").read_text() == f"belwacht versie {i + 1}\n"
            # R4: de wachten gaan uit voor de wissel, en blijven uit
            regels = log.read_text().splitlines()
            assert regels[0].startswith("bootout") and "whatsapp-wacht" in regels[0], regels
            assert not any(r.startswith("bootstrap") and "wacht.plist" in r and "kopie" not in r for r in regels)
            assert ("NIEUWE HELPER" in uit) == (i < 2), uit
        vorige = basis / "mac-gesprekken" / "vorige"
        assert (vorige / "COMMIT").read_text().strip() == shas[1]
        # S3: een wacht die na bootout nog in launchd staat: niets gewisseld
        geladen.write_text("")
        assert "staat nog in launchd" in uitrol(ref=shas[0], ok=False)
        geladen.unlink()
        assert git("rev-parse", "HEAD", cwd=werk) == shas[2] and (vorige / "COMMIT").read_text().strip() == shas[1]
        # S4: een andere uitrol of proef houdt het uitrolslot, of een wacht houdt haar rondeslot: niets gewisseld
        import fcntl
        for slotpad in (basis / "mac-gesprekken" / ".uitrol.lock", basis / "belwacht" / "ronde.lock"):
            slotpad.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(slotpad, os.O_CREAT | os.O_RDWR, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                assert "already locked" in uitrol(ref=shas[0], ok=False)
            finally:
                os.close(fd)
            assert git("rev-parse", "HEAD", cwd=werk) == shas[2], slotpad
        assert (basis / "belwacht" / "ronde.lock").exists()           # lockf -k laat het slot van de wacht staan
        # T2: een interne opdracht rechtstreeks, met UITROL_SLOT maar zonder sloten: geweigerd
        for intern in ("__installeer", "__terug"):
            r = subprocess.run(["zsh", str(script), intern], env={**omgeving, "UITROL_SLOT": "1", "REF": shas[0]},
                               capture_output=True, text=True)
            assert r.returncode == 64 and "niet vast" in r.stderr, (intern, r.stderr)
        assert git("rev-parse", "HEAD", cwd=werk) == shas[2]
        # U2: dezelfde directe aanroep terwijl een andere uitrol alle sloten houdt (nagebootst): ook geweigerd
        houders = []
        for slotpad in (basis / "mac-gesprekken" / ".uitrol.lock", basis / "whatsapp-wacht" / "ronde.lock",
                        basis / "belwacht" / "ronde.lock", basis / "sms-wacht" / "ronde.lock"):
            slotpad.parent.mkdir(parents=True, exist_ok=True)
            houders.append(os.open(slotpad, os.O_CREAT | os.O_RDWR, 0o600))
            fcntl.flock(houders[-1], fcntl.LOCK_EX | fcntl.LOCK_NB)
        (basis / "mac-gesprekken" / ".uitrol.sleutel").write_text("andere uitrol\n")
        try:
            for intern in ("__installeer", "__terug"):
                r = subprocess.run(["zsh", str(script), intern], env={**omgeving, "UITROL_SLOT": "1", "REF": shas[0]},
                                   capture_output=True, text=True)
                assert r.returncode == 64 and "hoort niet bij de uitrol" in r.stderr, (intern, r.stderr)
        finally:
            for fd in houders:
                os.close(fd)
        assert git("rev-parse", "HEAD", cwd=werk) == shas[2]
        # aan zonder proef: geweigerd
        assert "eerst" in uitrol("aan", ok=False)
        # terug: versie 2 als geheel
        uitrol("terug")
        assert git("rev-parse", "HEAD", cwd=werk) == shas[1]
        assert helper.read_text() == "helper b\n"
        assert all((agents / f"be.globaal.mijnagents.{l}.plist").read_text() == f"{l} versie 2\n"
                   for l in ("kopie-whatsapp", "kopie-telefoon", "whatsapp-wacht", "belwacht"))
        # met een proefbewijs voor precies deze versie mag aan
        stempel = subprocess.run(["zsh", "-c", f"source <(sed -n '/^stempel()/,/^}}/p' '{script}'); "
                                  f"HELPER='{helper}' WERK='{werk}' CODESIGN='{stub / 'codesign'}' stempel"],
                                 capture_output=True, text=True, check=True).stdout
        (basis / "mac-gesprekken" / "PROEF").write_text(stempel)
        uitrol("aan")
        assert "bootstrap" in log.read_text().splitlines()[-1]


if __name__ == "__main__":
    goed = fout = 0
    for naam, f in list(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                with redirect_stderr(io.StringIO()):
                    f()
                goed += 1
                print(f"   geslaagd  {naam}")
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"   FOUT      {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)

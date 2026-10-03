"""Grendel op mail als afsprakenbron ('Agendawacht - onderzoek en herstelvoorstel v1.1', werkpakket 2, FR-101).

Bewijst met mails zoals ze in mch@ en Hotmail binnenkomen: Outlook-ICS met Windows-tijdzone (en de VTIMEZONE van 1601
telt niet), Google-ICS in UTC; dezelfde uitnodiging via twee mailboxen is een afspraak; een oudere versie draait een
nieuwere niet terug; een annulering die nog in de agenda staat is een vraag; datum en uur zonder ICS (kinesist,
Calendly, "Today's 14:00"); een premieherinnering is geen afspraak; zonder uur een controlepunt; koppelen op iCalUID
of op het uur; Outlook zet UID na het letterlijke blok. Zonder netwerk en sleutels (ook CI).
"""
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

os.environ["MAIL_AFSPRAKEN_DB"] = os.path.join(tempfile.mkdtemp(), "afspraken_mail.db")
HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER / "koppelingen"))
import mail_afspraken as MA      # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


OUTLOOK = """BEGIN:VCALENDAR\r
METHOD:REQUEST\r
BEGIN:VTIMEZONE\r
TZID:Romance Standard Time\r
BEGIN:STANDARD\r
DTSTART:16010101T030000\r
END:STANDARD\r
BEGIN:DAYLIGHT\r
DTSTART:16010101T020000\r
END:DAYLIGHT\r
END:VTIMEZONE\r
BEGIN:VEVENT\r
UID:040000008200E00074C5B7101A82E00800000000F24C2F0ACE49DD01000000000000000\r
 10000000\r
SUMMARY;LANGUAGE=en-GB:Unabo LEGALFLY Trial Feedback\r
DTSTART;TZID=Romance Standard Time:20261030T140000\r
DTEND;TZID=Romance Standard Time:20261030T143000\r
STATUS:CONFIRMED\r
SEQUENCE:0\r
DTSTAMP:20260929T090000Z\r
LOCATION:Microsoft Teams\\, online\r
END:VEVENT\r
END:VCALENDAR\r
"""
_e = MA.ics_afspraken(OUTLOOK)
check("Outlook-ICS: een afspraak, de VTIMEZONE van 1601 telt niet, Romance Standard Time is Brussel, gevouwen UID heel",
      len(_e) == 1 and _e[0]["start"] == "2026-10-30T14:00:00+01:00" and _e[0]["einde"] == "2026-10-30T14:30:00+01:00"
      and _e[0]["uid"].endswith("10000000") and _e[0]["titel"] == "Unabo LEGALFLY Trial Feedback"
      and _e[0]["locatie"] == "Microsoft Teams, online" and _e[0]["method"] == "REQUEST" and not _e[0]["geannuleerd"], str(_e))

GOOGLE = "BEGIN:VCALENDAR\nMETHOD:REQUEST\nBEGIN:VEVENT\nDTSTART:20261007T080000Z\nDTEND:20261007T090000Z\nUID:abc123@google.com\n" \
         "SEQUENCE:2\nDTSTAMP:20261001T100000Z\nSUMMARY:Werfvergadering 2607\nEND:VEVENT\nEND:VCALENDAR\n"
check("Google-ICS in UTC wordt Brusselse tijd", MA.ics_afspraken(GOOGLE)[0]["start"] == "2026-10-07T10:00:00+02:00")

nu = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
k1 = {"mailbox": "mch@h-architects.be", "map": "INBOX", "uid": 1, "message_id": "<a@x>", "van": "Joe <joe@legalfly.com>",
      "onderwerp": "Unabo LEGALFLY Trial Feedback", "datum": "Tue, 29 Sep 2026 11:00:00 +0200", "ics": [OUTLOOK], "tekst": ""}
k2 = dict(k1, mailbox="mehdichegini@hotmail.com", message_id="<b@x>", map="Inbox")
MA.bewaar(MA.uit_kandidaat(k1), nu)
MA.bewaar(MA.uit_kandidaat(k2), nu)
check("dezelfde uitnodiging via twee mailboxen is een afspraak, met beide bronnen bewaard",
      len(MA.alle()) == 1 and MA._db().execute("SELECT COUNT(*) FROM bron").fetchone()[0] == 2)

NIEUWER = OUTLOOK.replace("SEQUENCE:0", "SEQUENCE:1").replace("T140000", "T150000").replace("T143000", "T153000")
MA.bewaar(MA.uit_kandidaat(dict(k1, message_id="<c@x>", ics=[NIEUWER])), nu)
MA.bewaar(MA.uit_kandidaat(dict(k1, message_id="<d@x>", onderwerp="Fwd: oud", ics=[OUTLOOK])), nu)
check("een oudere versie (doorgestuurde oude mail) draait de nieuwere niet terug: SEQUENCE 1 om 15:00 blijft",
      MA.alle()[0]["start"] == "2026-10-30T15:00:00+01:00" and MA.alle()[0]["sequence"] == 1, str(MA.alle()[0]))

# zonder ICS: datum en uur uit onderwerp of tekst
_t = MA.tijd_uit_tekst("HERINNERING - Uw afspraak bij KINEPLUSLEUVEN - woensdag 30/09/2026  om 08:30", "", "")
check("kinesist: 'woensdag 30/09/2026 om 08:30'", _t == "2026-09-30T08:30:00+02:00", _t)
_t = MA.tijd_uit_tekst("New Event: Benny Desmedt - 10:00 Fri, 2 Oct 2026 - Besprekingen", "", "")
check("Calendly: '10:00 Fri, 2 Oct 2026'", _t == "2026-10-02T10:00:00+02:00", _t)
_t = MA.tijd_uit_tekst("Today's 14:00 meeting", "", "2026-09-30T09:12:00+02:00")
check("'Today's 14:00 meeting' neemt de dag van de mail", _t == "2026-09-30T14:00:00+02:00", _t)
_t = MA.tijd_uit_tekst("Inspiratieavond", "op 12 oktober 2026 om 19:30 in Gent", "")
check("'12 oktober 2026 om 19:30' in de tekst", _t == "2026-10-12T19:30:00+02:00", _t)
check("een premieherinnering is geen afspraak",
      MA.uit_kandidaat({"mailbox": "mehdichegini@hotmail.com", "uid": 9, "message_id": "<p@x>", "van": "kbc@kbc.be",
                        "onderwerp": "72971400 - PATRIMONIUMPOLIS HANDEL - herinnering premiebetaling", "datum": "", "ics": [], "tekst": ""}) == [])
_z = MA.uit_kandidaat({"mailbox": "mehdichegini@hotmail.com", "uid": 10, "message_id": "<v@x>", "van": "syndicus@ehi.be",
                       "onderwerp": "Uitnodiging algemene vergadering / VME Shopping 2", "datum": "Tue, 22 Sep 2026 10:00:00 +0200",
                       "ics": [], "tekst": "In bijlage vindt u een bericht van uw syndicus"})
check("zonder uur is het een controlepunt met bron-ID, geen 'ontbreekt'", len(_z) == 1 and _z[0]["soort"] == "zonder_tijd"
      and MA.vergelijk(_z, [], nu)[0]["status"] == "zonder_tijd", str(_z))

# vergelijken met de agenda
_a = MA.alle()[0]
check("dezelfde iCalUID op een ander uur is afwijkend (een vraag), niet gekoppeld (nacontrole v1.2, V6)",
      MA.vergelijk([_a], [{"kalender": "werk", "id": "g1", "start": "2026-10-30T09:00:00+01:00", "_icaluid": _a["ics_uid"]}], nu)[0]["status"] == "afwijkend"
      and MA.vergelijk([_a], [{"kalender": "werk", "id": "g1", "start": _a["start"], "einde": _a["einde"], "_icaluid": _a["ics_uid"]}], nu)[0]["status"] == "gekoppeld")
check("gekoppeld op het uur (binnen vijf minuten) als de UID ontbreekt",
      MA.vergelijk([_a], [{"kalender": "prive", "id": "g2", "start": "2026-10-30T15:03:00+01:00"}], nu)[0]["google"] == "prive|g2")
check("staat ze nergens, dan ontbreekt ze", MA.vergelijk([_a], [], nu)[0]["status"] == "ontbreekt")
_kine = MA.uit_kandidaat({"mailbox": "mehdichegini@hotmail.com", "uid": 11, "message_id": "<k@x>", "van": "info@kineplus.be",
                          "onderwerp": "HERINNERING - Uw afspraak bij KINEPLUSLEUVEN - woensdag 30/09/2026  om 08:30", "datum": "", "ics": [], "tekst": ""})
check("een afspraak die voorbij is en ontbrak, heet voorbij (geen alarm achteraf)", MA.vergelijk(_kine, [], nu)[0]["status"] == "voorbij")
_c = MA.ics_afspraken(GOOGLE.replace("METHOD:REQUEST", "METHOD:CANCEL"))
_ca = MA.uit_kandidaat({"mailbox": "mch@h-architects.be", "uid": 12, "message_id": "<x@x>", "van": "a@b.be", "onderwerp": "Geannuleerd",
                        "datum": "", "ics": [GOOGLE.replace("METHOD:REQUEST", "METHOD:CANCEL")], "tekst": ""})
check("een annulering die nog in de agenda staat is een vraag; staat ze er niet meer, dan is het in orde",
      _c[0]["geannuleerd"] and MA.vergelijk(_ca, [{"kalender": "werk", "id": "g3", "start": "2026-10-07T10:00:00+02:00", "_icaluid": "abc123@google.com"}], nu)[0]["status"] == "geannuleerd_staat_er"
      and MA.vergelijk(_ca, [], nu)[0]["status"] == "geannuleerd")

# Outlook zet UID en BODYSTRUCTURE na het letterlijke blok
sys.modules.setdefault("config", type(sys)("config"))
sys.modules.setdefault("imapbron", type(sys)("imapbron"))
_bron = (HIER / "koppelingen" / "post_lezer.py").read_text(encoding="utf-8")
_ns = {}
exec(_bron[_bron.index("def antwoorden"):_bron.index("uit, fouten = [], []")], {"re": __import__("re")}, _ns)
_r = _ns["antwoorden"]([(b"12 (BODY[HEADER.FIELDS (SUBJECT)] {20}", b"Subject: uitnodiging"), b" UID 78219 BODYSTRUCTURE (\"text\" \"calendar\"))"])
check("Outlook zet UID en BODYSTRUCTURE na het letterlijke blok: beide worden gelezen",
      len(_r) == 1 and "UID 78219" in _r[0][0] and "calendar" in _r[0][0], str(_r))
check("de lezer selecteert read-only en haalt alles met PEEK (niets als gelezen gemarkeerd)",
      "BODY.PEEK[]" in _bron and "BODY.PEEK[HEADER.FIELDS" in _bron and "imapbron._selecteer(M, mapnaam)" in _bron
      and "STORE" not in _bron and "MOVE" not in _bron)

# meldingen in de privé-agenda: zetten, niet dubbel, alleen een eigen melding weghalen (FR-101)
os.environ["BELLEN_UIT"] = "1"
sys.path.insert(0, str(HIER))
import agenda_wacht as W         # noqa: E402
from datetime import timedelta   # noqa: E402
_nu = W.nu_lokaal()
_morgen = (_nu + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
_mis = {"sleutel": "ics|uid-x|", "status": "ontbreekt", "start": _morgen.isoformat(), "titel": "Werfvergadering 2607",
        "bron_mailbox": "mch@h-architects.be", "bron_onderwerp": "Uitnodiging: Werfvergadering 2607", "bron_ontvangen": _nu.isoformat(),
        "bron_afzender": "aannemer@voorbeeld.be", "bron_message_id": "<m1@voorbeeld>"}
_ok = dict(_mis, sleutel="ics|uid-y|", status="gekoppeld")
_oud = {"kalender": W.PRIVE_AGENDA, "id": "n-oud", "start": _morgen.date().isoformat(), "hele_dag": True,
        "_merk": {W.MAILMERK: MA.sleutel_kort(_ok)}}
_vreemd = {"kalender": W.PRIVE_AGENDA, "id": "mehdi-eigen", "start": _morgen.date().isoformat(), "hele_dag": True, "_merk": {}}
_ins, _weg = [], []
_o = (W._insert, W._patch)
W._insert = lambda kal, body, tok, toch=False: _ins.append((kal, body)) or {}
W._patch = lambda a, body, tok, toch=False: _weg.append((a["id"], body))
try:
    _r1 = W.mail_meldingen([_mis, _ok], [_oud, _vreemd], "t", _nu)
    _r2 = W.mail_meldingen([_mis, _ok], [_oud, _vreemd, {"kalender": W.PRIVE_AGENDA, "id": "n-nieuw", "start": _morgen.date().isoformat(),
                                                         "hele_dag": True, "_merk": {W.MAILMERK: MA.sleutel_kort(_mis)},
                                                         "titel": W._mail_melding_body(_mis, MA.sleutel_kort(_mis), _morgen.date().isoformat())["summary"]}],
                           "t", _nu)
finally:
    W._insert, W._patch = _o
_b = _ins[0][1] if _ins else {}
check("een afspraak uit mail die ontbreekt wordt een melding in de privé-agenda: hele dag, Beschikbaar, met bron en merk",
      len(_ins) == 1 and _ins[0][0] == W.PRIVE_AGENDA and _b["start"] == {"date": _morgen.date().isoformat()}
      and _b["transparency"] == "transparent" and "15:00 Werfvergadering 2607" in _b["summary"] and _b["summary"].startswith("VR ")
      and "Message-ID <m1@voorbeeld>" in _b["description"] and "Ik zet zelf niets" in _b["description"]
      and _b["extendedProperties"]["private"][W.MAILMERK] == MA.sleutel_kort(_mis), str(_ins))
check("een opgeloste melding wordt 'Opgelost' (niet gewist), een item van Mehdi zelf nooit, en geen dubbele melding",
      [w[0] for w in _weg] == ["n-oud", "n-oud"] and all(w[1]["summary"].startswith("Opgelost: ") and "Je mag deze melding weghalen" in w[1]["description"]
                                                      and w[1]["extendedProperties"]["private"][W.MAILMERK].startswith("opgelost:") for w in _weg)
      and len(_ins) == 1, str((_weg, _ins)))
check("alleen een eigen melding op de privé-agenda wordt aangepast",
      not W._eigen_melding_opgelost(_vreemd, "k", "t", _nu) and not W._eigen_melding_opgelost(dict(_oud, kalender=W.WERKAGENDA), MA.sleutel_kort(_ok), "t", _nu))

# de dagcontrole toont een afspraak uit mail die ontbreekt, op haar dag
MA.bewaar([{"sleutel": "ics|uid-z|", "soort": "ics", "ics_uid": "uid-z", "recurrence_id": "", "sequence": 0, "dtstamp": "1",
            "method": "REQUEST", "geannuleerd": False, "start": "2026-11-05T10:00:00+01:00", "einde": "", "titel": "Keuring lift",
            "locatie": "", "bron_mailbox": "mch@h-architects.be", "bron_message_id": "<z@x>", "bron_onderwerp": "Keuring",
            "bron_ontvangen": "", "bron_afzender": "a@b.be", "map": "INBOX", "imap_uid": 1}])
MA.statussen_bewaren(MA.vergelijk(MA.alle(), [], nu))
import dagcontrole as D          # noqa: E402
_dc = [b for b in D.dagcontrole([], "2026-11-05") if b["soort"] == "mail_ontbreekt"]
check("de dagcontrole toont een afspraak uit mail die niet in de agenda staat, op haar dag",
      len(_dc) == 1 and "Keuring lift" in _dc[0]["tekst"] and "niet in de agenda" in _dc[0]["tekst"], str(_dc))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

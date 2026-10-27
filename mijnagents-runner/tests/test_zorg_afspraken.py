"""Grendel op zorgafspraken uit mail: een bevestigde afspraak bij een beheerde persoonlijke zorgpraktijk (kine,
tandarts) wordt een echt blok in de privé-agenda ('Opdracht voor Claude - kine en tandarts in de privéagenda' v1.0,
14-10-2026; FR-130 tot FR-133).

Alle gegevens hier zijn verzonnen: praktijken, behandelaars, patiënten en adressen. De echte profielen staan alleen in
het privéregister op de server (afspraken_mail.db, tabel zorgpraktijk), nooit in git. Zonder netwerk en sleutels (ook CI).

Bewijst: beide mailboxen en beide praktijken geven een echt tijdblok, Bezet, in de privé-agenda; ICS, platte tekst en
HTML behouden datum, uur, eindtijd en plaats; een onderwerp met alleen de praktijknaam en een herinnering werken; een
nieuwsbrief of een onbevestigde aanvraag maakt geen consult; een oude bevestiging voor een toekomstige afspraak wordt
gevonden en een bestaand Google-ID blijft; herinnering, tweede mailbox en tweede ronde maken geen duplicaat; een
verplaatsing wijzigt de bestaande afspraak; een gezinslid komt niet op Mehdi's agenda; een onbekende eindtijd is een
open punt, geen verzonnen duur; voorbij is geen bewijs; een kine-item op werk wordt privé zonder firmavraag; niets
medisch naar het bord.
"""
import json
import os
os.environ.setdefault("AGENDA_WHATSAPP_WACHTRIJ", os.path.join(__import__("tempfile").mkdtemp(prefix="aw-test-"), "agenda-whatsapp.json"))  # nooit de echte wachtrij
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["MAIL_AFSPRAKEN_DB"] = os.path.join(tempfile.mkdtemp(), "afspraken_mail.db")
os.environ["BELLEN_UIT"] = "1"
HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER / "koppelingen"))
sys.path.insert(0, str(HIER))
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


KINE = {"id": "kine-voorbeeld", "naam": "Kinepraktijk Voorbeeld", "soort": "kine",
        "afzenders": ["info@kine-voorbeeld.test"], "praktijknamen": ["KINEVOORBEELD", "Kinepraktijk Voorbeeld"],
        "adres": "Proefstraat 1, 3000 Leuven", "telefoon": "016 00 00 01", "website": "https://kine-voorbeeld.test",
        "patienten": ["Mo Voorbeeld", "Mohammad Mo Voorbeeld"], "behandelaars": {"An Proef": "Kine"},
        "bewijs": ["fictief"], "geverifieerd": "2026-10-14"}
TAND = {"id": "tand-voorbeeld", "naam": "Tandpraktijk Voorbeeld", "soort": "tandarts",
        "afzenders": ["info@tand-voorbeeld.test", "leuven@tand-groep.test"], "praktijknamen": ["Tandpraktijk Voorbeeld"],
        "adres": "Proefkaai 2, 3000 Leuven", "telefoon": "016 00 00 02", "website": "https://tand-voorbeeld.test",
        "patienten": ["Mo Voorbeeld", "Mohammad Voorbeeld"], "behandelaars": {"Bea Proef": "Tandarts", "Cas Proef": "Mondhygiëne"},
        "bewijs": ["fictief"], "geverifieerd": "2026-10-14"}
for p in (KINE, TAND):
    MA.zorgprofiel_zet(p)
PROF = MA.zorgprofielen()
check("de zorgprofielen staan in het privéregister, met bron en verificatiedatum",
      {p["id"] for p in PROF} == {"kine-voorbeeld", "tand-voorbeeld"} and all(p.get("geverifieerd") and p.get("bewijs") for p in PROF))

nu = datetime(2026, 10, 15, 8, 0, tzinfo=timezone.utc)


def kand(mailbox, van, onderwerp, tekst, ics=(), datum="Wed, 14 Oct 2026 10:00:00 +0200", mid="<m@x>", links=(), uid=1):
    return {"mailbox": mailbox, "map": "INBOX", "uid": uid, "message_id": mid, "van": van, "onderwerp": onderwerp,
            "datum": datum, "ics": list(ics), "tekst": tekst, "zorg": True, "linktijden": list(links)}


HERINNERING = ("Beste Mohammad Mo Voorbeeld, We herinneren u graag aan uw afspraak bij KINEVOORBEELD. Details van de afspraak: "
               "Patiënt: Mohammad Mo Voorbeeld Uw therapeut: An Proef Wanneer: woensdag 21/10/2026 om 08:30 "
               "Waar: Proefstraat 1 3000 LEUVEN Toevoegen aan je agenda Google Agenda")
_h = MA.uit_kandidaat(kand("proef@voorbeeld.be", "Kinepraktijk Voorbeeld <info@kine-voorbeeld.test>",
                           "HERINNERING - Uw afspraak bij KINEVOORBEELD - woensdag 21/10/2026 om 08:30", HERINNERING,
                           mid="<h1@kine>", links=["20261021T083000/20261021T090000"]), PROF)
_z = (_h[0].get("zorg") or {}) if _h else {}
check("platte tekst met een herinnering: datum, uur, eindtijd uit de agenda-link, plaats, behandelaar en patiënt",
      len(_h) == 1 and _h[0]["soort"] == "zorg" and _h[0]["start"] == "2026-10-21T08:30:00+02:00"
      and _h[0]["einde"] == "2026-10-21T09:00:00+02:00" and "Proefstraat 1" in _h[0]["locatie"]
      and _z.get("behandelaar") == "An Proef" and _z.get("mehdi") and _z.get("gebeurtenis") == "herinnering"
      and _h[0]["prive"] == 1, str(_h))

TAND_ICS = ("BEGIN:VCALENDAR\r\nMETHOD:PUBLISH\r\nBEGIN:VTIMEZONE\r\nTZID:Romance Standard Time\r\nBEGIN:STANDARD\r\n"
            "DTSTART:16011005T030000\r\nEND:STANDARD\r\nEND:VTIMEZONE\r\nBEGIN:VEVENT\r\nUID:AAAA-1111\r\n"
            "DTSTART:20261209T073000Z\r\nDTEND:20261209T080000Z\r\nLOCATION;LANGUAGE=nl-BE:Proefkaai 2 - 3000 Leuven\r\n"
            "SUMMARY;LANGUAGE=nl-BE:Tandpraktijk Voorbeeld (016 00 00 02)\r\nSTATUS:CONFIRMED\r\nSEQUENCE:0\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
TAND_HTML_TEKST = ("Afspraak tandarts Beste Mohammad Voorbeeld Wij bevestigen graag uw afspraak op 09 dec 2026 om 08:30 bij "
                   "Bea Proef . Voor het annuleren van een afspraak, minder dan 24u op voorhand, worden kosten aangerekend.")
_t = MA.uit_kandidaat(kand("werk@voorbeeld.be", "\"Tandpraktijk Voorbeeld\" <info@tand-voorbeeld.test>", "Afspraak tandarts",
                           TAND_HTML_TEKST, ics=[TAND_ICS], datum="Tue, 19 May 2026 10:07:02 +0200", mid="<t1@tand>"), PROF)
_tz = (_t[0].get("zorg") or {}) if _t else {}
check("ICS en HTML uit MCH: eindtijd en plaats uit de ICS, behandelaar uit de tekst, privé ongeacht de mailbox",
      len(_t) == 1 and _t[0]["start"] == "2026-12-09T08:30:00+01:00" and _t[0]["einde"] == "2026-12-09T09:00:00+01:00"
      and "Proefkaai 2" in _t[0]["locatie"] and _t[0]["prive"] == 1 and _tz.get("behandelaar") == "Bea Proef"
      and _tz.get("gebeurtenis") == "bevestiging" and "annulering" not in _tz.get("gebeurtenis", ""), str(_t))
check("de standaardzin over annuleren maakt van een bevestiging geen annulering", not _t[0]["geannuleerd"] if _t else False)

_alleen_naam = MA.uit_kandidaat(kand("proef@voorbeeld.be", "Kinepraktijk Voorbeeld <info@kine-voorbeeld.test>",
                                     "Kinepraktijk Voorbeeld", "Beste Mo Voorbeeld, Uw boeking werd geaccepteerd. Afspraakdatum: 28.10.2026 "
                                     "Afspraaktijd: 08:30 Uw therapeut: An Proef", mid="<b1@kine>"), PROF)
check("een onderwerp met alleen de praktijknaam wordt gelezen; datum en uur uit 'Afspraakdatum/Afspraaktijd'",
      len(_alleen_naam) == 1 and _alleen_naam[0]["start"] == "2026-10-28T08:30:00+01:00"
      and (_alleen_naam[0]["zorg"] or {}).get("gebeurtenis") == "bevestiging", str(_alleen_naam))
check("zonder eindtijd in de mail blijft de eindtijd leeg: geen verzonnen duur",
      _alleen_naam and _alleen_naam[0]["einde"] == "", str(_alleen_naam))

_nieuws = MA.uit_kandidaat(kand("proef@voorbeeld.be", "Kinepraktijk Voorbeeld <info@kine-voorbeeld.test>",
                                "Nieuwsbrief herfst", "Onze praktijk is gesloten op 11 november. Nieuwe oefeningen voor thuis.",
                                mid="<n1@kine>"), PROF)
check("een nieuwsbrief van dezelfde praktijk is geen afspraak", _nieuws == [], str(_nieuws))
_aanvraag = MA.uit_kandidaat(kand("proef@voorbeeld.be", "Kinepraktijk Voorbeeld <info@kine-voorbeeld.test>",
                                  "Uw online boeking werd geregistreerd - woensdag 04.11.2026 08:30",
                                  "Beste Mo Voorbeeld, uw online boeking werd geregistreerd en wacht op bevestiging door de praktijk. "
                                  "Afspraakdatum: 04.11.2026 Afspraaktijd: 08:30", mid="<a1@kine>"), PROF)
check("een onbevestigde aanvraag is een aparte gebeurtenis, geen definitief consult",
      len(_aanvraag) == 1 and (_aanvraag[0]["zorg"] or {}).get("gebeurtenis") == "aanvraag", str(_aanvraag))
_citaat = MA.uit_kandidaat(kand("proef@voorbeeld.be", "Tandpraktijk Voorbeeld <info@tand-voorbeeld.test>", "RE: Afspraak tandarts",
                                "Dag, uw eerste afspraak is geannuleerd en de andere staat ingepland. Op di 17 mrt 2026 om 18:17 schreef "
                                "Mo Voorbeeld: kan ik verzetten?", mid="<r1@tand>"), PROF)
check("een geciteerde antwoordkop ('Op ... om 18:17 schreef') is geen afspraaktijd", all(not a["start"] for a in _citaat), str(_citaat))
_gezin = MA.uit_kandidaat(kand("proef@voorbeeld.be", "Tandpraktijk Voorbeeld <info@tand-voorbeeld.test>", "Afspraak tandarts",
                               "Beste Lisa Voorbeeld Wij bevestigen graag uw afspraak op 18 nov 2026 om 10:00 bij Bea Proef .",
                               mid="<g1@tand>"), PROF)
check("een afspraak voor een gezinslid is niet van Mehdi", len(_gezin) == 1 and not (_gezin[0]["zorg"] or {}).get("mehdi"), str(_gezin))
_vreemd = MA.uit_kandidaat(kand("proef@voorbeeld.be", "Andere Kine <info@andere-kine.test>",
                                "HERINNERING - Uw afspraak - woensdag 21/10/2026 om 08:30", HERINNERING, mid="<v1@x>"), PROF)
check("een afzender zonder profiel gaat langs de gewone route (geen zorgblok)", all(a["soort"] != "zorg" for a in _vreemd), str(_vreemd))

# register: herinnering + bevestiging + tweede mailbox = een afspraak; verplaatsing wijzigt dezelfde afspraak
MA.bewaar(_h, nu)
MA.bewaar(MA.uit_kandidaat(kand("werk@voorbeeld.be", "Kinepraktijk Voorbeeld <info@kine-voorbeeld.test>",
                                "HERINNERING - Uw afspraak bij KINEVOORBEELD - woensdag 21/10/2026 om 08:30", HERINNERING,
                                mid="<h1@kine>", links=["20261021T083000/20261021T090000"]), PROF), nu)
MA.bewaar(_t, nu)
MA.bewaar(_gezin, nu)
MA.bewaar(_aanvraag, nu)
_zorg = [a for a in MA.alle() if a["soort"] == "zorg"]
check("herinnering en dezelfde mail via twee mailboxen geven een afspraak, met beide bronnen bewaard",
      len([a for a in _zorg if a["start"].startswith("2026-10-21")]) == 1
      and MA._db().execute("SELECT COUNT(*) FROM bron WHERE sleutel LIKE 'zorg|kine-voorbeeld|2026-10-21%'").fetchone()[0] == 2, str(_zorg))
_sleutel_21 = next(a["sleutel"] for a in _zorg if a["start"].startswith("2026-10-21"))
MA.bewaar(MA.uit_kandidaat(kand("proef@voorbeeld.be", "Kinepraktijk Voorbeeld <info@kine-voorbeeld.test>",
                                "Uw afspraak werd verplaatst",
                                "Beste Mo Voorbeeld, uw afspraak van 21/10/2026 om 08:30 wordt verplaatst naar 23/10/2026 om 09:00. "
                                "Uw therapeut: An Proef", mid="<p1@kine>"), PROF), nu)
_na = [a for a in MA.alle() if a["soort"] == "zorg" and a["sleutel"] == _sleutel_21]
check("een verplaatsing kiest de nieuwe tijd, wijzigt dezelfde afspraak (zelfde sleutel) en bewaart de oude",
      len(_na) == 1 and _na[0]["start"] == "2026-10-23T09:00:00+02:00"
      and "2026-10-21T08:30" in json.dumps(json.loads(_na[0]["zorg"] or "{}").get("historie")), str(_na))
check("na de verplaatsing staat er geen tweede los item voor de nieuwe tijd",
      len([a for a in MA.alle() if a["soort"] == "zorg" and a["start"].startswith("2026-10-23")]) == 1)

# vergelijken: bestaand Google-ID blijft, gezinslid en aanvraag geen blok, onbekende eindtijd open, voorbij geen bewijs
sys.path.insert(0, str(HIER))
import agenda_wacht as W         # noqa: E402
_bestaand = {"kalender": W.PRIVE_AGENDA, "id": "bestaand-tand", "titel": "!! [PRIVE] Tandarts - Bea Proef",
             "start": "2026-12-09T08:30:00+01:00", "einde": "2026-12-09T09:00:00+01:00", "locatie": "Proefkaai 2, 3000 Leuven"}
_res = {a["sleutel"]: a for a in MA.vergelijk(MA.alle(), [_bestaand], nu)}
_tand = next(a for a in _res.values() if a["start"].startswith("2026-12-09"))
check("een oude bevestiging voor een toekomstige afspraak koppelt aan het bestaande Google-ID, geen nieuw item",
      _tand["status"] == "gekoppeld" and _tand["google"] == f"{W.PRIVE_AGENDA}|bestaand-tand", str(_tand))
_g = next(a for a in _res.values() if a["start"].startswith("2026-11-18"))
check("een afspraak van een gezinslid wordt een open punt, nooit een blok", _g["status"] == "zorg_open" and "patiënt" in _g["detail"], str(_g))
_a = next(a for a in _res.values() if a["start"].startswith("2026-11-04"))
check("een aanvraag die nog bevestigd moet worden, krijgt geen blok", _a["status"] == "zorg_wacht", str(_a))
MA.bewaar(_alleen_naam, nu)
_o = next(a for a in MA.vergelijk(MA.alle(), [], nu) if a["start"].startswith("2026-10-28"))
check("een bevestiging zonder eindtijd is een concreet open punt", _o["status"] == "zorg_open" and "eindtijd" in _o["detail"], str(_o))
_v = MA.vergelijk([dict(_h[0], start="2026-10-14T08:30:00+02:00", einde="2026-10-14T09:00:00+02:00")], [], nu)[0]
check("een voorbije afspraak zonder item is historisch gemist: voorbij, geen blok in het verleden",
      _v["status"] == "voorbij" and not _v["google"], str(_v))
check("zorgstatussen die Mehdi moet zien, staan bij de vraagstatussen", "zorg_open" in MA.VRAAG_STATUSSEN)
_dhr = MA.uit_kandidaat(kand("proef@voorbeeld.be", "Kinepraktijk Voorbeeld <info@kine-voorbeeld.test>",
                            "Uw Afspraak bij An Proef: Woensdag 12.08.2026 om 08:30", "Beste Dhr. Voorbeeld, graag bevestig ik uw afspraak.",
                            mid="<d1@kine>"), PROF)
check("een aanspreking met alleen de familienaam is niet zeker Mehdi", _dhr and (_dhr[0]["zorg"] or {}).get("patient") == "Voorbeeld"
      and not (_dhr[0]["zorg"] or {}).get("mehdi"), str(_dhr))
_dv = MA.vergelijk(_dhr, [], nu)[0] if _dhr else {}
check("een voorbije afspraak met een onzekere patiënt is historisch, geen open punt", _dv.get("status") == "voorbij", str(_dv))

# de agent: echt blok in de privé-agenda, Bezet, met herinnering, geen gasten; teruglezen; tweede ronde geen duplicaat
_ins, _pat, _mov = [], [], []
_o_fn = (W._insert, W._patch, W._verplaats_naar, W._lees_event)
_gezet = {}


def _nep_insert(kal, body, tok, toch=False):
    _ins.append((kal, body))
    e = dict(body, id=f"nieuw-{len(_ins)}", organizer={"email": kal})
    _gezet[e["id"]] = e
    return e


W._insert = _nep_insert
W._patch = lambda a, body, tok, toch=False: _pat.append((a["id"], body))
W._verplaats_naar = lambda x, doel, tok: _mov.append((x["id"], doel))
W._lees_event = lambda kal, eid, tok: _gezet.get(eid)
_toekomst = dict(_h[0], sleutel="zorg|kine-voorbeeld|2026-10-21T08:30:00+02:00", status="ontbreekt", google="", detail="",
                 zorg=json.dumps(_z))
try:
    _r1 = W.zorg_afspraken_zetten([_toekomst, dict(_tand)], [_bestaand], "t", W.nu_lokaal().replace(year=2026, month=10, day=15))
    _ins1 = list(_ins)
    _r2 = W.zorg_afspraken_zetten([dict(_toekomst, status="gezet", google=f"{W.PRIVE_AGENDA}|nieuw-1"), dict(_tand)],
                                  [_bestaand, {"kalender": W.PRIVE_AGENDA, "id": "nieuw-1", "titel": _ins1[0][1]["summary"] if _ins1 else "",
                                               "start": _toekomst["start"], "einde": _toekomst["einde"],
                                               "_merk": {W.ZORGMERK: _toekomst["sleutel"]}}],
                                  "t", W.nu_lokaal().replace(year=2026, month=10, day=15))
finally:
    W._insert, W._patch, W._verplaats_naar, W._lees_event = _o_fn
_b = _ins1[0][1] if _ins1 else {}
check("een bevestigde zorgafspraak wordt een echt blok in de privé-agenda: Bezet, begin en einde, plaats, herinnering, geen gasten",
      len(_ins1) == 1 and _ins1[0][0] == W.PRIVE_AGENDA and _b["start"] == {"dateTime": "2026-10-21T08:30:00+02:00", "timeZone": "Europe/Brussels"}
      and _b["end"] == {"dateTime": "2026-10-21T09:00:00+02:00", "timeZone": "Europe/Brussels"} and _b["transparency"] == "opaque"
      and "Proefstraat 1" in _b["location"] and not _b.get("attendees") and _b["reminders"]["overrides"]
      and _b["summary"].startswith("!! [PR] Kine - An Proef") and _b["extendedProperties"]["private"][W.ZORGMERK] == _toekomst["sleutel"]
      and "<h1@kine>" in _b["description"], str(_ins1))
check("het blok wordt teruggelezen en het Google-ID bewaard; de bestaande tandarts krijgt geen tweede item",
      _r1["gezet"] == 1 and _r1["gekoppeld"] >= 1 and _toekomst.get("google") == f"{W.PRIVE_AGENDA}|nieuw-1" and _toekomst["status"] == "gezet", str(_r1))
check("een tweede ronde maakt geen duplicaat", len(_ins) == 1 and _r2["gezet"] == 0, str((_ins, _r2)))
check("de bordregels van de zorgstap noemen geen praktijk, behandelaar of plaats",
      not any(w in " ".join(_r1["bord"] + _r2["bord"]) for w in ("Proef", "Kine", "Tand", "Leuven")), str(_r1["bord"]))

# een kine-item dat op werk staat, wordt privé, zonder firmavraag, met behoud van het Google-ID
_werk = {"kalender": W.WERKAGENDA, "id": "werk-kine", "titel": "VR !! kine: hand mo", "start": "2026-10-21T08:30:00+02:00",
         "einde": "2026-10-21T09:00:00+02:00", "omschrijving": "Agendawacht vraagt: zeg voor welke firma en welke klant.\n\n",
         "locatie": "", "hele_dag": False, "deelnemers": [], "maker": W.WERKAGENDA}
_ins, _pat, _mov = [], [], []
W._insert, W._patch, W._verplaats_naar, W._lees_event = _nep_insert, (lambda a, body, tok, **vlaggen: _pat.append((a["id"], body))), \
    (lambda x, doel, tok: _mov.append((x["id"], doel))), (lambda kal, eid, tok: None)
try:
    _r3 = W.zorg_afspraken_zetten([], [_werk], "t", W.nu_lokaal().replace(year=2026, month=10, day=15))
finally:
    W._insert, W._patch, W._verplaats_naar, W._lees_event = _o_fn
check("een kine-item op de werkagenda verhuist naar privé (zelfde Google-ID), zonder VR en zonder firmavraag, geen kopie",
      _mov == [("werk-kine", W.PRIVE_AGENDA)] and not _ins and _pat and not _pat[-1][1]["summary"].startswith("VR")
      and "[PR]" in _pat[-1][1]["summary"] and "firma" not in _pat[-1][1].get("description", ""), str((_mov, _pat, _ins)))
check("een kine-titel op werk krijgt geen vraag naar firma en klant",
      not [s for s, z in W.vastgelopen([dict(_werk, start=(W.nu_lokaal() + timedelta(hours=5)).isoformat())], W.nu_lokaal()) if s.endswith(":firma")])
check("een zorgtitel geldt overal als privé: nooit met titel naar het bord", W.is_prive({"kalender": W.WERKAGENDA, "titel": "Tandarts controle"})
      and not W.is_prive({"kalender": W.WERKAGENDA, "titel": "Kinepolis teamuitje"}))

# ---------------------------------------------------------------- Codex-controle ronde 1 (A01 tot A07) ---
_KM = "Kinepraktijk Voorbeeld <info@kine-voorbeeld.test>"
_TM = "Tandpraktijk Voorbeeld <info@tand-voorbeeld.test>"
_o_lees = MA.lees


def _ronde_met(kandidaten):
    MA.lees = lambda sinds, mailboxen=MA.MAILBOXEN, maximaal=2000, zorg=None: (list(kandidaten), [])
    try:
        return MA.ronde([], "2026-10-01", nu)
    finally:
        MA.lees = _o_lees


# A01: de verplaatsing komt (nieuwste eerst) voor de oorspronkelijke bevestiging; dat geeft toch een afspraak op het nieuwe uur
_bev = kand("proef@voorbeeld.be", _KM, "Uw boeking werd geaccepteerd - woensdag 25.11.2026 om 08:30",
            "Beste Mo Voorbeeld, uw boeking werd geaccepteerd. Afspraakdatum: 25.11.2026 Afspraaktijd: 08:30 Uw therapeut: An Proef",
            datum="Mon, 02 Nov 2026 10:00:00 +0100", mid="<a01-bev@kine>")
_verpl = kand("proef@voorbeeld.be", _KM, "Uw afspraak werd verplaatst",
              "Beste Mo Voorbeeld, uw afspraak van 25/11/2026 om 08:30 wordt verplaatst naar 27/11/2026 om 09:00. Uw therapeut: An Proef",
              datum="Tue, 10 Nov 2026 10:00:00 +0100", mid="<a01-verpl@kine>")
_ronde_met([_verpl, _bev])
_nov = [a for a in MA.alle() if a["soort"] == "zorg" and a["start"][:10] in ("2026-11-25", "2026-11-27")]
check("A01 een verplaatsing die eerst gelezen wordt, geeft geen tweede afspraak op het oude uur",
      len(_nov) == 1 and _nov[0]["start"].startswith("2026-11-27T09:00"), str([(a["sleutel"], a["start"]) for a in _nov]))
_oud_herinner = kand("werk@voorbeeld.be", _KM, "HERINNERING - Uw afspraak bij KINEVOORBEELD - woensdag 25/11/2026 om 08:30",
                     "Beste Mo Voorbeeld, Patiënt: Mo Voorbeeld Uw therapeut: An Proef Wanneer: woensdag 25/11/2026 om 08:30",
                     datum="Tue, 03 Nov 2026 10:00:00 +0100", mid="<a01-oud@kine>")
_ronde_met([_verpl, _bev, _oud_herinner])
_nov2 = [a for a in MA.alle() if a["soort"] == "zorg" and a["start"][:10] in ("2026-11-25", "2026-11-27")]
check("A01 een oude herinnering voor het oude uur en een tweede ronde maken geen nieuwe rij (tijdalias, bericht al verwerkt)",
      len(_nov2) == 1 and _nov2[0]["start"].startswith("2026-11-27T09:00"), str([(a["sleutel"], a["start"]) for a in _nov2]))
MA.bewaar(MA.uit_kandidaat(kand("proef@voorbeeld.be", _TM, "Afspraak tandarts",
                                "Beste Mohammad Voorbeeld Wij bevestigen graag uw afspraak op 01 dec 2026 om 10:00 bij Bea Proef .",
                                mid="<a01-mo@tand>"), PROF), nu)
MA.bewaar(MA.uit_kandidaat(kand("proef@voorbeeld.be", _TM, "Afspraak tandarts",
                                "Beste Lisa Voorbeeld Wij bevestigen graag uw afspraak op 01 dec 2026 om 10:00 bij Bea Proef .",
                                mid="<a01-lisa@tand>"), PROF), nu)
_dec = [a for a in MA.alle() if a["soort"] == "zorg" and a["start"].startswith("2026-12-01T10:00")]
check("A01 twee patiënten op hetzelfde uur blijven twee afspraken", len(_dec) == 2, str([a["sleutel"] for a in _dec]))

# A02: een zakelijke afspraak met een praktijk als klant is geen persoonlijke zorg
_zak = "[UB-KB] EPB - Tandartspraktijk Fictief, Proefstraat 9, 3000 Leuven"
check("A02 een titel met een firmacode is nooit persoonlijke zorg, wel [PR] en een titel zonder code",
      not W.is_zorg_titel(_zak) and not W.is_prive({"kalender": W.WERKAGENDA, "titel": _zak})
      and W.is_zorg_titel("!! [PR] Kine - An Proef") and W.is_zorg_titel("VR !! kine: hand"))
_tv = (W.nu_lokaal() + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
_niet = [dict(_werk, id="zak", titel=_zak, start=_tv, einde=_tv),
         dict(_werk, id="reeks", start=_tv, einde=_tv, _terugkerend=True),
         dict(_werk, id="collega", start=_tv, einde=_tv, _agendagasten=["collega@x.be"])]
_mov = []
W._verplaats_naar, W._patch = (lambda x, doel, tok: _mov.append(x["id"])), (lambda a, body, tok, toch=False: None)
try:
    W.zorg_afspraken_zetten([], _niet, "t")
finally:
    W._verplaats_naar, W._patch = _o_fn[2], _o_fn[1]
check("A02 nooit verhuisd: een zakelijke praktijkafspraak, een reeks, een afspraak met een collega", _mov == [], str(_mov))
_twee = [{"kalender": W.PRIVE_AGENDA, "id": "k1", "titel": "Tandarts", "start": "2026-12-09T08:30:00+01:00"},
         {"kalender": W.WERKAGENDA, "id": "k2", "titel": "tandarts Lara", "start": "2026-12-09T08:30:00+01:00"}]
_r2k = MA.vergelijk([a for a in MA.alle() if a["start"].startswith("2026-12-09")], _twee, nu)
check("A02 twee kandidaten op hetzelfde uur: een open punt, niet raden", _r2k and _r2k[0]["status"] == "zorg_open"
      and "eenduidig" in _r2k[0]["detail"], str([(a["status"], a["detail"]) for a in _r2k]))
_r2z = MA.vergelijk([a for a in MA.alle() if a["start"].startswith("2026-12-09")],
                    [{"kalender": W.WERKAGENDA, "id": "z1", "titel": _zak, "start": "2026-12-09T08:30:00+01:00"}], nu)
check("A02 een zakelijke praktijkafspraak op hetzelfde uur wordt niet gekoppeld", _r2z and _r2z[0]["status"] != "gekoppeld",
      str([(a["status"], a["google"]) for a in _r2z]))

# A03: annulering zonder tijd, herbevestiging, voorlopige ICS
_ann = MA.uit_kandidaat(kand("proef@voorbeeld.be", _KM, "Uw afspraak werd geannuleerd",
                             "Beste Mo Voorbeeld, uw afspraak bij ons werd geannuleerd.", mid="<a03-ann@kine>"), PROF)
check("A03 een annulering zonder tijd verdwijnt niet: een open punt", len(_ann) == 1 and not _ann[0]["start"]
      and MA.vergelijk(_ann, [], nu)[0]["status"] == "zorg_open", str(_ann))
for _i, (_ond, _txt, _dat) in enumerate((
        ("Uw boeking werd geaccepteerd", "Beste Mo Voorbeeld, Afspraakdatum: 10.11.2026 Afspraaktijd: 08:30", "Mon, 26 Oct 2026 10:00:00 +0100"),
        ("Afspraak geannuleerd", "Beste Mo Voorbeeld, uw afspraak van 10/11/2026 om 08:30 werd geannuleerd.", "Tue, 27 Oct 2026 10:00:00 +0100"),
        ("Uw boeking werd geaccepteerd", "Beste Mo Voorbeeld, Afspraakdatum: 10.11.2026 Afspraaktijd: 08:30", "Wed, 28 Oct 2026 10:00:00 +0100"))):
    MA.bewaar(MA.uit_kandidaat(kand("proef@voorbeeld.be", _KM, _ond, _txt, datum=_dat, mid=f"<a03-{_i}@kine>"), PROF), nu)
_her = [a for a in MA.alle() if a["start"].startswith("2026-11-10T08:30")]
check("A03 een nieuwere bevestiging heft een eerdere annulering op", len(_her) == 1 and not _her[0]["geannuleerd"], str(_her))
_tent = MA.uit_kandidaat(kand("proef@voorbeeld.be", _TM, "Afspraak tandarts", "Beste Mohammad Voorbeeld Afspraak bij Bea Proef .",
                              ics=[TAND_ICS.replace("STATUS:CONFIRMED", "STATUS:TENTATIVE").replace("AAAA-1111", "TTTT-2222")
                                   .replace("20261209T07", "20261216T07").replace("20261209T08", "20261216T08")], mid="<a03-t@tand>"), PROF)
check("A03 een voorlopige afspraak (ICS TENTATIVE) is een aanvraag, geen blok", _tent and (_tent[0]["zorg"] or {}).get("gebeurtenis") == "aanvraag", str(_tent))

# A04: geen praktijkadres als plaats; een verzet blok houdt zijn duur en zegt dat
check("A04 zonder plaats in de mail blijft de plaats leeg (geen praktijkadres)", _alleen_naam and _alleen_naam[0]["locatie"] == "",
      str(_alleen_naam))
_vz_item = {"kalender": W.PRIVE_AGENDA, "id": "vz", "titel": "!! [PR] Kine - An Proef", "start": "2026-11-25T08:30:00+01:00",
            "einde": "2026-11-25T09:00:00+01:00", "omschrijving": ""}
_vz = dict(_nov2[0], status="afwijkend", google=f"{W.PRIVE_AGENDA}|vz")
_vpat = []
W._patch = lambda a, body, tok, toch=False: _vpat.append(body)
W._lees_event = lambda kal, eid, tok: {"start": {"dateTime": "2026-11-27T09:00:00+01:00"}, "end": {"dateTime": "2026-11-27T09:30:00+01:00"}}
try:
    _rvz = W.zorg_afspraken_zetten([_vz], [_vz_item], "t", W.nu_lokaal().replace(year=2026, month=10, day=15))
finally:
    W._patch, W._lees_event = _o_fn[1], _o_fn[3]
check("A04 een verplaatsing zonder einde verzet hetzelfde blok met zijn oude duur, en zegt dat in de omschrijving",
      _rvz["verzet"] == 1 and _vpat and _vpat[0]["end"]["dateTime"].startswith("2026-11-27T09:30") and "oude duur" in _vpat[0]["description"],
      str((_rvz, _vpat)))

# PR 113 (Codex-hertest 9): bij een verzet blijft een lange omschrijving volledig (de agenda-lijst kapt af na 2000 tekens)
_lang_oms = "Praktijk Proef, notities van Mehdi. " + ("x" * 2500) + " EINDE"
_vpat2 = []
W._patch = lambda a, body, tok, toch=False: _vpat2.append(body)
W._lees_event = lambda kal, eid, tok: {"start": {"dateTime": "2026-11-27T09:00:00+01:00"},
                                       "end": {"dateTime": "2026-11-27T09:30:00+01:00"}, "description": _lang_oms}
try:
    W.zorg_afspraken_zetten([dict(_vz, status="afwijkend")], [dict(_vz_item, omschrijving=_lang_oms[:2000])], "t",
                            W.nu_lokaal().replace(year=2026, month=10, day=15))
finally:
    W._patch, W._lees_event = _o_fn[1], _o_fn[3]
check("PR 113: een verzet zorgblok houdt zijn volledige omschrijving van meer dan 2000 tekens",
      _vpat2 and _vpat2[0]["description"].startswith(_lang_oms), str([len(b.get("description", "")) for b in _vpat2]))

# A05: een ingekorte privétitel in een logregel wordt gemaskeerd; privé gaat nooit naar een afdeling
import bord as _bord  # noqa: E402
_lang = "!! [PR] Mondhygiëne - Een Heel Lange Naam Voor De Proef Van Het Masker"
_ag = _bord.Agent("proef-masker")
_ag.prive(W.prive_teksten([{"kalender": W.PRIVE_AGENDA, "titel": _lang, "locatie": ""}]))
_regel = _ag.maskeer(f"2026-10-21T08:30 {_lang[:44]}: thuis -> Leuven 20 min")
check("A05 een ingekorte privétitel (titel[:44]) in een logregel wordt gemaskeerd", _lang[:20] not in _regel and "(privé)" in _regel, _regel)
check("A05 een privé-item gaat nooit naar een afdeling op het bord",
      'afdeling != "mehdi" and not is_prive(a)' in (HIER / "agenda_wacht.py").read_text(encoding="utf-8"))

# A06: een onleesbaar profiel maakt de dekking gedeeltelijk
MA._db().execute("INSERT OR REPLACE INTO zorgpraktijk(id, profiel, bijgewerkt) VALUES('stuk', '{niet json', '')").connection.commit()
_ronde_met([])
_ls = MA.leesstand()
check("A06 een onleesbaar zorgprofiel: de dekking is gedeeltelijk, niet volledig",
      all(_ls.get(m, {}).get("dekking") == "gedeeltelijk" for m in MA.MAILBOXEN), str({m: _ls.get(m, {}).get("dekking") for m in MA.MAILBOXEN}))
_c6 = MA._db()
_c6.execute("DELETE FROM zorgpraktijk WHERE id='stuk'")
_c6.commit()

# A07: na het verhuizen wordt teruggelezen; klopt het niet, dan heet het niet verhuisd
_w7 = dict(_werk, id="w7", start=_tv, einde=_tv)
for _lees, _verwacht in (({W.PRIVE_AGENDA: {"summary": "!! [PR] Kine: hand mo", "description": "Van de werkagenda naar privé"},
                           W.WERKAGENDA: {"status": "cancelled"}}, (1, 0)), ({}, (0, 1))):
    W._verplaats_naar, W._patch = (lambda x, doel, tok: None), (lambda a, body, tok, **vlaggen: None)
    W._lees_event = lambda kal, eid, tok, _l=_lees: _l.get(kal)
    try:
        _r7 = W.zorg_afspraken_zetten([], [_w7], "t")
    finally:
        W._verplaats_naar, W._patch, W._lees_event = _o_fn[2], _o_fn[1], _o_fn[3]
    check(f"A07 verhuizen telt alleen na een geslaagde teruglezing ({'gelukt' if _verwacht[0] else 'mislukt'})",
          (_r7["verhuisd"], _r7["fout"]) == _verwacht, str(_r7))

# de lezer: zorgafzenders apart gezocht, ook HTML, agenda-link en herkansing bij 'not connected'
_bron = (HIER / "koppelingen" / "post_lezer.py").read_text(encoding="utf-8")
check("A06 een mislukte zorgzoekactie laat de gewone mail van de map staan en telt als onvolledig", "zorgzoekactie mislukt" in _bron)
check("de lezer zoekt de zorgafzenders apart (ook oude mail en zonder afspraakwoord) en leest HTML en de agenda-link",
      "zorg_afzenders" in _bron and "_html_naar_tekst" in _bron and "linktijden" in _bron and "not connected" in _bron
      and "BODY.PEEK[]" in _bron and "STORE" not in _bron)
_opdr = []
_o_run = MA.subprocess.run
MA.subprocess.run = lambda *a, **k: _opdr.append(k.get("args", a[0] if a else None)) or type("R", (), {"returncode": 1, "stderr": b"x", "stdout": b""})()
try:
    MA.ronde([], "2026-10-01", nu)
finally:
    MA.subprocess.run = _o_run
_env = " ".join(str(x) for x in (_opdr[0] if _opdr else []))
check("de ronde vraagt de zorgafzenders op over minstens 300 dagen terug", "zorg_afzenders" in _env and "info@kine-voorbeeld.test" in _env
      and "2025-12-19" in _env, _env[:300])

# Ronde 3 (Codex A01): een mail zonder leesbare patiënt koppelt niet op een gelijk uur aan Mehdi's afspraak
_bev3 = kand("proef@voorbeeld.be", _KM, "Uw boeking werd geaccepteerd - woensdag 16.12.2026 om 09:00",
             "Beste Mo Voorbeeld, uw boeking werd geaccepteerd. Afspraakdatum: 16.12.2026 Afspraaktijd: 09:00 Uw therapeut: An Proef",
             mid="<r3-bev@kine>", datum="Wed, 14 Oct 2026 11:00:00 +0200", uid=31)
_ann3 = kand("proef@voorbeeld.be", _KM, "Annulering van uw afspraak bij KINEVOORBEELD",
             "Uw afspraak bij KINEVOORBEELD op woensdag 16/12/2026 om 09:00 werd geannuleerd. Uw therapeut: An Proef",
             mid="<r3-ann@kine>", datum="Wed, 14 Oct 2026 12:00:00 +0200", uid=32)
_ronde_met([_bev3, _ann3])
_dec = [a for a in MA.alle() if a["soort"] == "zorg" and a["start"].startswith("2026-12-16T09:00")]
_mo = [a for a in _dec if (MA._zorg_json(a).get("mehdi"))]
check("A01 ronde 3: een annulering zonder leesbare patiënt op hetzelfde uur annuleert Mehdi's afspraak niet",
      len(_mo) == 1 and not _mo[0]["geannuleerd"], str([(a["sleutel"][-12:], a["geannuleerd"], MA._zorg_json(a).get("patient")) for a in _dec]))

# Ronde 3 (Codex A02): alleen een algemeen zorgwoord op hetzelfde uur is een vraag, de praktijknaam koppelt, Lara nooit
_r3 = [a for a in MA.alle() if a["soort"] == "zorg" and a["start"].startswith("2026-12-16T09:00") and MA._zorg_json(a).get("mehdi")]
_r3s = lambda items: MA.vergelijk(_r3, items, nu)[0]["status"] if _r3 else "geen rij"
_t3 = "2026-12-16T09:00:00+01:00"
check("A02 ronde 3: alleen 'Kine' op dat uur koppelt niet stil, het is een vraag",
      _r3s([{"kalender": W.PRIVE_AGENDA, "id": "g1", "titel": "Kine", "start": _t3}]) == "zorg_open")
check("A02 ronde 3: de naam van de behandelaar of de praktijk op dat uur koppelt wel",
      _r3s([{"kalender": W.PRIVE_AGENDA, "id": "g2", "titel": "Kine - An Proef", "start": _t3}]) == "gekoppeld")
check("A02 ronde 3: een afspraak van Lara ([LA]) op dat uur is nooit die van Mehdi",
      _r3s([{"kalender": W.WERKAGENDA, "id": "g3", "titel": "[LA] kine An Proef", "start": _t3}]) != "gekoppeld")

# Ronde 4 (Codex A02): het merk van een andere zorgafspraak of een andere externe uitnodiging koppelt nooit
check("A02 ronde 4: een item met het merk van een andere zorgafspraak koppelt niet, ook met de praktijknaam",
      _r3s([{"kalender": W.PRIVE_AGENDA, "id": "g4", "titel": "Kine - An Proef", "start": _t3, "_merk": {MA.ZORGMERK: "zorg|ander|x"}}]) != "gekoppeld")
check("A02 ronde 4: een andere externe uitnodigings-ID is een andere afspraak; een eigen Google-item niet",
      MA._zorgachtig({"titel": "Kine - An Proef", "_icaluid": "uid-ander@extern.test"}, {"sleutel": "s", "ics_uid": "uid-1@extern.test"}, {}, KINE) < 1
      and MA._zorgachtig({"titel": "Kine - An Proef", "_icaluid": "abc@google.com"}, {"sleutel": "s", "ics_uid": "uid-1@extern.test"}, {}, KINE) == 2)

# Ronde 4 (Codex A01): twee mails zonder leesbare patiënt op hetzelfde uur worden elk een eigen open punt
_bev4 = kand("proef@voorbeeld.be", _KM, "Uw boeking werd geaccepteerd - woensdag 23.12.2026 om 09:00",
             "Beste Mo Voorbeeld, uw boeking werd geaccepteerd. Afspraakdatum: 23.12.2026 Afspraaktijd: 09:00 Uw therapeut: An Proef",
             mid="<r4-bev@kine>", datum="Wed, 14 Oct 2026 13:00:00 +0200", uid=41)
_onb = [kand("proef@voorbeeld.be", _KM, "Annulering van uw afspraak bij KINEVOORBEELD",
             "Uw afspraak bij KINEVOORBEELD op woensdag 23/12/2026 om 09:00 werd geannuleerd. Uw therapeut: An Proef",
             mid=f"<r4-onb{i}@kine>", datum=f"Wed, 14 Oct 2026 1{4 + i}:00:00 +0200", uid=42 + i) for i in range(2)]
_fouten4 = _ronde_met([_bev4] + _onb)[1]
_rijen4 = [a for a in MA.alle() if a["soort"] == "zorg" and a["start"].startswith("2026-12-23T09:00")]
check("A01 ronde 4: twee mails zonder leesbare patiënt op hetzelfde uur: elk een eigen rij, geen fout",
      len(_rijen4) == 3 and not any("niet verwerkt" in f.get("fout", "") for f in _fouten4), f"{len(_rijen4)} {_fouten4}")

# Ronde 5 (Codex A02): een oude verwijzing die nu naar een item van een andere afspraak wijst, telt niet
_a5 = dict(_r3[0]) if _r3 else {}
if _a5:
    _a5["google"] = f"{W.PRIVE_AGENDA}|g5"
    _v5 = MA.vergelijk([_a5], [{"kalender": W.PRIVE_AGENDA, "id": "g5", "titel": "Kine - An Proef", "start": "2026-12-16T11:00:00+01:00",
                                "_merk": {MA.ZORGMERK: "zorg|ander|y"}}], nu)[0]
check("A02 ronde 5: een oude verwijzing naar een item met een ander zorgmerk geeft geen 'afwijkend' (niets verzetten)",
      bool(_a5) and _v5["status"] != "afwijkend", str(_v5.get("status") if _a5 else "geen rij"))

# Ronde 5 (Codex A35): een zorgitem op hetzelfde uur met een andere uitnodiging is een conflict, geen tweede blok
_a35 = {**_r3[0], "ics_uid": "uid-1@extern.test", "einde": "2026-12-16T09:30:00+01:00", "google": ""} if _r3 else {}
_s35 = MA.vergelijk([_a35], [{"kalender": W.PRIVE_AGENDA, "id": "g6", "titel": "Kine - An Proef", "start": _t3,
                              "_icaluid": "andere@extern.test"}], nu)[0]["status"] if _a35 else "geen rij"
check("A35 een zorgitem met een andere externe uitnodiging op hetzelfde uur: een open punt, niet 'ontbreekt'", _s35 == "zorg_open", _s35)

# Ronde 6 (Codex A02, A35): de UID gaat voor het eigen merk; een conflict op het nieuwe uur blokkeert verzetten
check("A02 ronde 6: een item met ons merk maar een andere externe uitnodiging is een conflict, geen koppeling",
      MA._zorgachtig({"titel": "Kine - An Proef", "_merk": {MA.ZORGMERK: "s"}, "_icaluid": "ander@extern.test"},
                     {"sleutel": "s", "ics_uid": "uid-1@extern.test"}, {}, KINE) == -1)
if _a35:
    _a6 = {**_a35, "google": f"{W.PRIVE_AGENDA}|oud6"}
    _s6 = MA.vergelijk([_a6], [{"kalender": W.PRIVE_AGENDA, "id": "oud6", "titel": "Kine - An Proef", "start": "2026-12-16T08:00:00+01:00",
                                "_merk": {MA.ZORGMERK: _a6["sleutel"]}},
                               {"kalender": W.PRIVE_AGENDA, "id": "ander6", "titel": "Kine - An Proef", "start": _t3,
                                "_icaluid": "andere@extern.test"}], nu)[0]["status"]
else:
    _s6 = "geen rij"
check("A35 ronde 6: een eigen item op het oude uur en een andere afspraak op het nieuwe uur: een vraag, niet verzetten",
      _s6 == "zorg_open", _s6)

_a41 = {**_a35, "google": ""} if _a35 else {}
_vreemd41 = {"kalender": W.PRIVE_AGENDA, "id": "vreemd41", "titel": "Kine - An Proef",
              "start": "2026-12-16T08:00:00+01:00", "_merk": {MA.ZORGMERK: _a41.get("sleutel")},
              "_icaluid": "andere-uitnodiging@extern.test"}
if _a41:
    _s41a = MA.vergelijk([_a41], [_vreemd41], nu)[0]["status"]
    _s41b = MA.vergelijk([{**_a41, "geannuleerd": 1}], [_vreemd41], nu)[0]["status"]
else:
    _s41a = _s41b = "geen rij"
check("A41 gemerkt item met andere externe UID geeft geen afwijkend bij verzet",
      _s41a != "afwijkend", _s41a)
check("A41 gemerkt item met andere externe UID geeft geen geannuleerd_staat_er",
      _s41b != "geannuleerd_staat_er", _s41b)


def test_gemaskeerde_patient_drie_velden_telt_als_mehdi():
    profiel = {"id": "huisarts-proef", "naam": "Huisartspraktijk Proef", "soort": "huisarts",
               "duur_minuten": 20, "patienten": ["Jan Pieter Jansens"],
               "behandelaars": {"Dr. Proef": "Huisarts"}}
    z1 = MA.zorg_herken({"onderwerp": "Bevestiging van uw afspraak",
                         "tekst": ("Datum: maandag 26/10/2026\nTijd: 11:20\nBij: Dr. Proef\n"
                                   "Naam: Jan*** Pie*** Jan***\nVoornaam: Jan***\nAchternaam: Jan***\n")}, profiel)
    z2 = MA.zorg_herken({"onderwerp": "Bevestiging van uw afspraak",
                         "tekst": "Datum: maandag 26/10/2026\nTijd: 11:20\nBij: Dr. Proef\nVoornaam: Jan***\nAchternaam: Jan***\n"}, profiel)
    z3 = MA.zorg_herken({"onderwerp": "Bevestiging van uw afspraak",
                         "tekst": "Datum: maandag 26/10/2026\nTijd: 11:20\nBij: Dr. Proef\nVoornaam: Ali***\nAchternaam: Jan***\n"}, profiel)
    z4 = MA.zorg_herken({"onderwerp": "Bevestiging van uw afspraak",
                         "tekst": "Datum: maandag 26/10/2026\nTijd: 11:20\nBij: Dr. Proef\nVoornaam: Jan***\nAchternaam: Eva***\n"}, profiel)
    return bool(z1 and z1["mehdi"] and z2 and z2["mehdi"] and z3 and not z3["mehdi"]
                and z4 and not z4["mehdi"])


def test_eigen_zorgvraag_verdwijnt_na_koppeling():
    sleutel = "zorg|kine-voorbeeld|2026-12-16T09:00:00+01:00"
    rij = {"sleutel": sleutel, "soort": "zorg", "start": "2026-12-16T09:00:00+01:00",
           "einde": "2026-12-16T09:30:00+01:00", "geannuleerd": 0, "ics_uid": "", "locatie": "",
           "titel": "Kine An Proef", "bron_ontvangen": "2026-10-14T10:00:00+02:00",
           "bron_mailbox": "proef@voorbeeld.be", "bron_onderwerp": "Afspraak",
           "bron_afzender": "info@kine-voorbeeld.test", "bron_message_id": "<zorg-vr@kine>",
           "zorg": {"praktijk": "kine-voorbeeld", "gebeurtenis": "bevestiging",
                    "patient": "Jan*** Pie*** Jan***", "mehdi": False, "behandelaar": "An Proef"}}
    k = MA.sleutel_kort(rij)
    prive_item = {"kalender": W.PRIVE_AGENDA, "id": "zorg-gekoppeld", "titel": "!! [PRIVE] Kine - An Proef",
                  "start": "2026-12-16T09:00:00+01:00", "einde": "2026-12-16T09:30:00+01:00",
                  "hele_dag": False, "_merk": {MA.ZORGMERK: sleutel}}
    eigen_vr = {"kalender": W.PRIVE_AGENDA, "id": "vr-eigen",
                "titel": "VR Agendawacht: zorgafspraak uit mail (Kine), andere patiënt of patiënt niet te lezen",
                "start": "2026-12-16", "einde": "2026-12-17", "hele_dag": True,
                "omschrijving": "Agendawacht vraagt: voor wie?", "_merk": {W.MAILMERK: k}}
    vreemd_vr = {"kalender": W.PRIVE_AGENDA, "id": "vr-vreemd",
                 "titel": "VR Agendawacht: handmatig zonder merk",
                 "start": "2026-12-16", "einde": "2026-12-17", "hele_dag": True,
                 "omschrijving": "Handmatig", "_merk": {}}
    items = [prive_item, eigen_vr, vreemd_vr]
    res = MA.vergelijk([rij], items, nu)
    oud_patch = W._patch
    gepatcht = []
    W._patch = lambda a, body, _tok, **_kw: gepatcht.append((a["id"], body))
    try:
        W.mail_meldingen(res, items, "tok", nu=nu)
    finally:
        W._patch = oud_patch
    return (res[0]["status"] == "gekoppeld" and eigen_vr["titel"].startswith("Opgelost: ")
            and eigen_vr["_merk"][W.MAILMERK] == f"opgelost:{k}"
            and vreemd_vr["titel"] == "VR Agendawacht: handmatig zonder merk"
            and [p[0] for p in gepatcht] == ["vr-eigen"])


check("test_gemaskeerde_patient_drie_velden_telt_als_mehdi", test_gemaskeerde_patient_drie_velden_telt_als_mehdi())
check("test_eigen_zorgvraag_verdwijnt_na_koppeling", test_eigen_zorgvraag_verdwijnt_na_koppeling())

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

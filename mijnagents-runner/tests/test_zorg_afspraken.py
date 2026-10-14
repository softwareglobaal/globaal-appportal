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
_h = MA.uit_kandidaat(kand("mehdichegini@hotmail.com", "Kinepraktijk Voorbeeld <info@kine-voorbeeld.test>",
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
_t = MA.uit_kandidaat(kand("mch@h-architects.be", "\"Tandpraktijk Voorbeeld\" <info@tand-voorbeeld.test>", "Afspraak tandarts",
                           TAND_HTML_TEKST, ics=[TAND_ICS], datum="Tue, 19 May 2026 10:07:02 +0200", mid="<t1@tand>"), PROF)
_tz = (_t[0].get("zorg") or {}) if _t else {}
check("ICS en HTML uit MCH: eindtijd en plaats uit de ICS, behandelaar uit de tekst, privé ongeacht de mailbox",
      len(_t) == 1 and _t[0]["start"] == "2026-12-09T08:30:00+01:00" and _t[0]["einde"] == "2026-12-09T09:00:00+01:00"
      and "Proefkaai 2" in _t[0]["locatie"] and _t[0]["prive"] == 1 and _tz.get("behandelaar") == "Bea Proef"
      and _tz.get("gebeurtenis") == "bevestiging" and "annulering" not in _tz.get("gebeurtenis", ""), str(_t))
check("de standaardzin over annuleren maakt van een bevestiging geen annulering", not _t[0]["geannuleerd"] if _t else False)

_alleen_naam = MA.uit_kandidaat(kand("mehdichegini@hotmail.com", "Kinepraktijk Voorbeeld <info@kine-voorbeeld.test>",
                                     "Kinepraktijk Voorbeeld", "Beste Mo Voorbeeld, Uw boeking werd geaccepteerd. Afspraakdatum: 28.10.2026 "
                                     "Afspraaktijd: 08:30 Uw therapeut: An Proef", mid="<b1@kine>"), PROF)
check("een onderwerp met alleen de praktijknaam wordt gelezen; datum en uur uit 'Afspraakdatum/Afspraaktijd'",
      len(_alleen_naam) == 1 and _alleen_naam[0]["start"] == "2026-10-28T08:30:00+01:00"
      and (_alleen_naam[0]["zorg"] or {}).get("gebeurtenis") == "bevestiging", str(_alleen_naam))
check("zonder eindtijd in de mail blijft de eindtijd leeg: geen verzonnen duur",
      _alleen_naam and _alleen_naam[0]["einde"] == "", str(_alleen_naam))

_nieuws = MA.uit_kandidaat(kand("mehdichegini@hotmail.com", "Kinepraktijk Voorbeeld <info@kine-voorbeeld.test>",
                                "Nieuwsbrief herfst", "Onze praktijk is gesloten op 11 november. Nieuwe oefeningen voor thuis.",
                                mid="<n1@kine>"), PROF)
check("een nieuwsbrief van dezelfde praktijk is geen afspraak", _nieuws == [], str(_nieuws))
_aanvraag = MA.uit_kandidaat(kand("mehdichegini@hotmail.com", "Kinepraktijk Voorbeeld <info@kine-voorbeeld.test>",
                                  "Uw online boeking werd geregistreerd - woensdag 04.11.2026 08:30",
                                  "Beste Mo Voorbeeld, uw online boeking werd geregistreerd en wacht op bevestiging door de praktijk. "
                                  "Afspraakdatum: 04.11.2026 Afspraaktijd: 08:30", mid="<a1@kine>"), PROF)
check("een onbevestigde aanvraag is een aparte gebeurtenis, geen definitief consult",
      len(_aanvraag) == 1 and (_aanvraag[0]["zorg"] or {}).get("gebeurtenis") == "aanvraag", str(_aanvraag))
_gezin = MA.uit_kandidaat(kand("mehdichegini@hotmail.com", "Tandpraktijk Voorbeeld <info@tand-voorbeeld.test>", "Afspraak tandarts",
                               "Beste Lisa Voorbeeld Wij bevestigen graag uw afspraak op 18 nov 2026 om 10:00 bij Bea Proef .",
                               mid="<g1@tand>"), PROF)
check("een afspraak voor een gezinslid is niet van Mehdi", len(_gezin) == 1 and not (_gezin[0]["zorg"] or {}).get("mehdi"), str(_gezin))
_vreemd = MA.uit_kandidaat(kand("mehdichegini@hotmail.com", "Andere Kine <info@andere-kine.test>",
                                "HERINNERING - Uw afspraak - woensdag 21/10/2026 om 08:30", HERINNERING, mid="<v1@x>"), PROF)
check("een afzender zonder profiel gaat langs de gewone route (geen zorgblok)", all(a["soort"] != "zorg" for a in _vreemd), str(_vreemd))

# register: herinnering + bevestiging + tweede mailbox = een afspraak; verplaatsing wijzigt dezelfde afspraak
MA.bewaar(_h, nu)
MA.bewaar(MA.uit_kandidaat(kand("mch@h-architects.be", "Kinepraktijk Voorbeeld <info@kine-voorbeeld.test>",
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
MA.bewaar(MA.uit_kandidaat(kand("mehdichegini@hotmail.com", "Kinepraktijk Voorbeeld <info@kine-voorbeeld.test>",
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
_bestaand = {"kalender": "mehdipriveagena@gmail.com", "id": "bestaand-tand", "titel": "!! [PRIVE] Tandarts - Bea Proef",
             "start": "2026-12-09T08:30:00+01:00", "einde": "2026-12-09T09:00:00+01:00", "locatie": "Proefkaai 2, 3000 Leuven"}
_res = {a["sleutel"]: a for a in MA.vergelijk(MA.alle(), [_bestaand], nu)}
_tand = next(a for a in _res.values() if a["start"].startswith("2026-12-09"))
check("een oude bevestiging voor een toekomstige afspraak koppelt aan het bestaande Google-ID, geen nieuw item",
      _tand["status"] == "gekoppeld" and _tand["google"] == "mehdipriveagena@gmail.com|bestaand-tand", str(_tand))
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

# de agent: echt blok in de privé-agenda, Bezet, met herinnering, geen gasten; teruglezen; tweede ronde geen duplicaat
import agenda_wacht as W         # noqa: E402
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
         "locatie": "", "hele_dag": False, "deelnemers": []}
_ins, _pat, _mov = [], [], []
W._insert, W._patch, W._verplaats_naar, W._lees_event = _nep_insert, (lambda a, body, tok, toch=False: _pat.append((a["id"], body))), \
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

# de lezer: zorgafzenders apart gezocht, ook HTML, agenda-link en herkansing bij 'not connected'
_bron = (HIER / "koppelingen" / "post_lezer.py").read_text(encoding="utf-8")
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

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

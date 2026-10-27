"""Grendels uit de Codex-controle ronde 2 van De Agendawacht (A09 tot A30, 15-10-2026; FR-139 en verder).
Zonder netwerk en sleutels (ook CI). Alle namen, adressen en links zijn verzonnen.

Bewijst per bevinding het gedrag, niet alleen dat er tekst in de code staat: elke controle faalt op commit 3715d36.
"""
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import time
os.environ["TZ"] = "UTC"          # zoals de VM: de klok van de server staat op UTC (master, werkwijze)
time.tzset()
TMP = tempfile.mkdtemp()
os.environ.update({"BELLEN_UIT": "1", "MAIL_AFSPRAKEN_DB": os.path.join(TMP, "afspraken_mail.db")})
HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W     # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


def veilig(f):
    """Een controle die een nieuwe functie gebruikt, faalt op de oude code als FOUT in plaats van het bestand te stoppen."""
    try:
        return f()
    except Exception as e:  # noqa: BLE001
        return e


@contextmanager
def vervang(*paren):
    oud = [(obj, naam, getattr(obj, naam)) for obj, naam, _ in paren]
    try:
        for obj, naam, waarde in paren:
            setattr(obj, naam, waarde)
        yield
    finally:
        for obj, naam, waarde in oud:
            setattr(obj, naam, waarde)


_later = (W.nu_lokaal() + timedelta(days=2)).replace(hour=14, minute=0, second=0, microsecond=0)


def afspraak(id_, titel, **extra):
    return {"id": id_, "titel": titel, "start": _later.isoformat(), "einde": (_later + timedelta(minutes=30)).isoformat(),
            "kalender": W.WERKAGENDA, "locatie": "", "omschrijving": "", **extra}


def zoom(items):
    geschreven = []
    with vervang((W, "_patch", lambda a, body, tok, toch=False: geschreven.append((a["id"], body))),
                 (W.agenda, "_toegang", lambda: "t"),
                 (W, "_volledige_omschrijving", lambda a, tok: a.get("omschrijving") or "")):
        _, regels = W.zoom_zetten(items)
    return geschreven, regels


# A09: ZL zetten of weghalen verandert titel en omschrijving; met gasten of bij Calendly is dat een voorstel
print("A09 en A30: ZL alleen op eigen afspraken, alleen een vergaderlink telt")
g, r = zoom([afspraak("gast", "Mehdi: [HA-PO] Jan Proef", deelnemers=["jan@voorbeeld.test"])])
check("A09 een online afspraak met een gast en zonder link: geen titel of omschrijving gewijzigd, wel een voorstel",
      g == [] and any("VOORSTEL" in x for x in r), f"{g} {r}")
g, r = zoom([afspraak("gastzl", "ZL Mehdi: [HA-PO] Jan Proef", deelnemers=["jan@voorbeeld.test"],
                      omschrijving="Online. Mehdi stuurt de link naar Jan Proef.\n\nhttps://zoom.us/j/123456789")])
check("A09 ZL met een gast en een vergaderlink: ZL niet zelf weggehaald, wel een voorstel",
      g == [] and any("VOORSTEL" in x for x in r), f"{g} {r}")
g, r = zoom([afspraak("cal", "Mehdi: [HA-PO] Jan Proef",
                      omschrijving="Geboekt via de site.\nAnnuleren: https://calendly.com/cancellations/abc")])
check("A09 een Calendly-boeking zonder gasten: niets gewijzigd", g == [], str(g))
g, r = zoom([afspraak("calacc", "Mehdi: [HA-PO] Jan Proef", maker="zoomafspraken@gmail.com")])
check("A09 een afspraak door een boekingsaccount gezet: niets gewijzigd", g == [], str(g))

g, r = zoom([afspraak("dropbox", "Mehdi: [HA-PO] Jan Proef", omschrijving="Plannen: https://www.dropbox.com/s/voorbeeld")])
check("A30 alleen een Dropbox-link is geen vergaderlink: ZL en de linknotitie komen er wel",
      len(g) == 1 and g[0][1].get("summary", "").startswith("ZL ") and "stuurt de link naar Jan Proef" in g[0][1].get("description", ""),
      str(g))
g, r = zoom([afspraak("pipe", "ZL Mehdi: [HA-PO] Jan Proef",
                      omschrijving="Online. Mehdi stuurt de link naar Jan Proef.\n\nhttps://h-architects.pipedrive.com/deal/1")])
check("A30 ZL met alleen een Pipedrive-link: ZL blijft staan", g == [], str(g))
g, r = zoom([afspraak("zoomlink", "ZL Mehdi: [HA-PO] Jan Proef",
                      omschrijving="Online. Mehdi stuurt de link naar Jan Proef.\n\nhttps://us02web.zoom.us/j/123456789")])
check("A30 een echte Zoom-link op een eigen afspraak: ZL en de notitie gaan eraf (bestaand gedrag)",
      len(g) == 1 and not g[0][1]["summary"].startswith("ZL") and "stuurt de link" not in g[0][1]["description"], str(g))
g, r = zoom([afspraak("meet", "ZL Mehdi: [HA-PO] Jan Proef", omschrijving="https://meet.google.com/abc-defg-hij")])
check("A30 een Google Meet-link telt ook als vergaderlink", len(g) == 1 and not g[0][1]["summary"].startswith("ZL"), str(g))
check("A30 _online herkent een Teams-link in de omschrijving als online",
      W._online({"locatie": "", "omschrijving": "Deelnemen: https://teams.microsoft.com/l/meetup-join/x"}) is True)

# titels: een Calendly-boeking zonder gasten wordt ook in de andere titelroutes een voorstel
def titels(items):
    geschreven = []
    with vervang((W, "_patch", lambda a, body, tok, toch=False: geschreven.append((a["id"], body))), (W.agenda, "_toegang", lambda: "t"),
                 (W.projectadressen, "index", lambda: {})):
        _, r1 = W.titels_normaliseren(items)
        _, r2 = W.titels_aanvullen(items)
    return geschreven, r1 + r2


g, r = titels([afspraak("eigen", "Mehdi: [HARC-PO] Jan Proef - ST")])
check("tegenproef: een eigen afspraak zonder gasten krijgt de code van twee letters", [x[0] for x in g] == ["eigen"], str(g))
g, r = titels([afspraak("caln", "Mehdi: [HARC-PO] Jan Proef - ST", omschrijving="Verzetten: https://calendly.com/reschedulings/abc")])
check("A09 titels_normaliseren en titels_aanvullen schrijven niet in een Calendly-boeking, maar doen een voorstel",
      g == [] and any("VOORSTEL" in x for x in r), f"{g} {r}")

# A18: de titel van een reeks bepaalt de gasten van de reeks, niet de titel van een uitzondering
print("A18: agendagasten in een reeks")
MENSEN = {"matthew@voorbeeld.test": {"voornaam": "Matthew", "achternaam": "Proef", "naam": "Matthew", "in_dienst": True}}
staat = {"r2": {"attendees": [], "summary": "Mehdi: [UB-IN] wekelijks"},
         "r3": {"attendees": [], "summary": "Mehdi+Matthew: [UB-IN] wekelijks"}}
patches = []


def _nep_patch(a, body, tok, toch=False):
    patches.append(a["id"])
    staat.setdefault(a["id"], {})["attendees"] = body["attendees"]


with vervang((W.organisatie, "agenda_adressen", lambda *x, **k: MENSEN), (W, "_patch", _nep_patch),
             (W, "_event", lambda a, tok: staat.get(a["id"], {"attendees": []})), (W.agenda, "_toegang", lambda: "t")):
    W.agendagasten_zetten([
        afspraak("r2_1", "Mehdi: [UB-IN] wekelijks", _reeks="r2", _organisator_zelf=True),
        afspraak("r2_2", "Mehdi+Matthew: [UB-IN] wekelijks", _reeks="r2", _organisator_zelf=True),
        afspraak("r3_1", "Mehdi+Matthew: [UB-IN] wekelijks", _reeks="r3", _organisator_zelf=True),
        afspraak("r3_2", "Mehdi+Matthew: [UB-IN] wekelijks", _reeks="r3", _organisator_zelf=True),
    ])
check("A18 een collega die alleen in de titel van een week staat, komt alleen op die week", "r2" not in patches and "r2_2" in patches,
      str(patches))
check("A18 een collega in de titel van de reeks komt een keer op de reeks zelf", patches.count("r3") == 1 and "r3_1" not in patches,
      str(patches))

# A22: tijden vergelijken als tijdstip, niet als tekst; de VM draait op UTC
print("A22: tijd")
_bezig = (W.nu_lokaal() - timedelta(minutes=30)).replace(second=0, microsecond=0)
g, r = zoom([{**afspraak("bezig", "Mehdi: [HA-PO] Jan Proef"), "start": _bezig.isoformat(), "einde": (_bezig + timedelta(hours=1)).isoformat()}])
check("A22 een online afspraak die al 30 minuten bezig is, krijgt geen ZL meer (VM op UTC)", g == [], str(g))
check("A22 wintertijdnacht: 02:15+01:00 ligt na 02:40+02:00 en is dus nog niet voorbij",
      veilig(lambda: W._voorbij("2026-10-25T02:15:00+01:00", "2026-10-25T02:40:00+02:00")) is False
      and veilig(lambda: W._voorbij("2026-10-25T02:30:00+02:00", "2026-10-25T02:10:00+01:00")) is True)
check("A22 een hele dag van vandaag is niet voorbij, gisteren wel",
      veilig(lambda: W._voorbij(W.nu_lokaal().date().isoformat())) is False
      and veilig(lambda: W._voorbij((W.nu_lokaal() - timedelta(days=1)).date().isoformat())) is True)
_bron_agenda = (HIER / "koppelingen" / "agenda.py").read_text(encoding="utf-8")
check("A22 Google geeft elke agenda in Brusselse tijd terug (timeZone bij het lezen)", '"timeZone": "Europe/Brussels"' in _bron_agenda)

# A24: een vraag over twee afspraken tegelijk komt als VR in beide eigen afspraken
print("A24: vragen in de agenda")
vr = []
with vervang((W, "_patch", lambda a, body, tok, toch=False: vr.append((a["id"], body.get("summary", "")))),
             (W.agenda, "_toegang", lambda: "t"), (W.projectadressen, "index", lambda: {}),
             (W.zoom, "beschikbaar", lambda *x, **k: False)):
    W.vragen_in_agenda([afspraak("eigen-klantafspraak-een-lang-id", "Mehdi: [HA-KO] 2601 - Jan Proef"),
                        afspraak("eigen-prospectafspraak-twee-lang-id", "Mehdi: [HA-PO] Piet Proef")])
check("A24 twee eigen afspraken tegelijk (zonder gasten): beide krijgen VR", sorted(i for i, t in vr if t.startswith("VR ")) ==
      ["eigen-klantafspraak-een-lang-id", "eigen-prospectafspraak-twee-lang-id"], str(vr))
with vervang((W.projectadressen, "index", lambda: {}), (W.zoom, "beschikbaar", lambda *x, **k: False)):
    # Vaste klok: _later is overmorgen 14:00 en vastgelopen kijkt 48 uur vooruit. Zonder nu viel de afspraak voor
    # 14:00 buiten het venster en faalde deze toets alleen 's ochtends (CI 16-10-2026).
    _sl = [k for k, _ in W.vastgelopen([afspraak("eigen-klantafspraak-een-lang-id", "Mehdi: [HA-KO] 2601 - Jan Proef"),
                                         afspraak("eigen-prospectafspraak-twee-lang-id", "Mehdi: [HA-PO] Piet Proef")],
                                        nu=_later - timedelta(days=1))]
check("A24 de belsleutel blijft dezelfde (geen tweede oproep voor dezelfde vraag)",
      _sl == ["dubbel:" + ":".join(sorted(["eigen-klantafspraak-een-lang-id"[:16], "eigen-prospectafspraak-twee-lang-id"[:16]]))], str(_sl))

# A11, A15, A16, A17: wat niet te lezen is, is onbekend, niet leeg (zoals FR-94)
print("A11, A15, A16, A17: onvolledige bronnen")
import json as _json                     # noqa: E402
import urllib.request as _ur             # noqa: E402


def _stuk(*a, **k):
    raise OSError("netwerk weg")


# de vakantiedagen komen sinds 27-10-2026 uit werkwijze/schoolvakanties.json (FR-210): een ontbrekend bestand is onbekend
with vervang((_ur, "urlopen", _stuk), (W.agenda, "_toegang", lambda: "t"),
             (W, "SCHOOLVAKANTIES", W.SCHOOLVAKANTIES.with_name("bestaat-niet.json"))):
    W._lara_vrij["tot"] = W._geen_auto["tot"] = 0
    _v, _g = W.lara_vakantiedagen(), W.geen_auto_dagen()
check("A11 vakantie- en geen-autodagen niet te lezen: None, geen lege set", _v is None and _g is None, f"{_v!r} {_g!r}")
check("A11 een mislukte lezing wordt niet onthouden", W._lara_vrij["tot"] == 0 and W._geen_auto["tot"] == 0)
_ins = []
with vervang((W, "geen_auto_dagen", lambda: None), (W, "lara_vakantiedagen", lambda: frozenset()), (W, "_cache_laden", lambda: {}),
             (W, "_cache_bewaren", lambda c: None), (W, "coord", lambda *a, **k: (50.88, 4.70)), (W.projectadressen, "index", lambda: {}),
             (W, "_insert", lambda *a, **k: _ins.append(a)), (W, "_patch", lambda *a, **k: _ins.append(a)), (W.agenda, "_toegang", lambda: "t")):
    _r = veilig(lambda: W.reistijd_zetten([afspraak("buiten", "!! Mehdi: [HA-KB] 2601 - Jan Proef, Proefstraat 1, 3000 Leuven",
                                                    locatie="Proefstraat 1, 3000 Leuven")]))
check("A11 geen-autodagen onbekend: geen rit gezet, wel gemeld",
      isinstance(_r, tuple) and _ins == [] and any("niet te lezen" in x for x in _r[4]), f"{_ins} {_r}")

with vervang((W.agenda, "kalendernamen", _stuk)):
    _a16 = W.archief_afspraken(-1, 8)
check("A16 archiefnamen niet te lezen: lege lijst met een foutstatus", _a16 == [] and bool(getattr(W, "ARCHIEF_FOUT", "")), repr(getattr(W, "ARCHIEF_FOUT", None)))
with vervang((W.agenda, "kalendernamen", lambda: {"arch1": "ZZ ARCHIEF proef"}),
             (W.agenda, "afspraken", lambda v, t: [{"kalender": "arch1", "fout": "HTTP 503"}])):
    _a16 = W.archief_afspraken(-1, 8)
check("A16 een archiefagenda met een leesfout staat in de foutstatus", _a16 == [] and "ZZ ARCHIEF proef" in getattr(W, "ARCHIEF_FOUT", ""), repr(getattr(W, "ARCHIEF_FOUT", None)))

with vervang((W.agenda, "kalendernamen", lambda: {}), (W.agenda, "afspraken", lambda v, t: [{"kalender": "x", "fout": "HTTP 503"}])):
    try:
        _ver = W.verre_afspraken()
        _ok17 = all("id" in x and "titel" in x for x in _ver) and bool(getattr(W, "VERRE_FOUT", None))
    except Exception as e:  # noqa: BLE001
        _ok17, _ver = False, repr(e)
check("A17 een verre agenda met een leesfout geeft geen foutrecord als afspraak, wel een foutstatus", _ok17, str(_ver)[:120])

with vervang((W, "afspraken", lambda v, t: [{"kalender": "proef@agenda", "fout": "HTTP 503"}, afspraak("ok", "Mehdi: [HA-IN] x")]),
             (W, "archief_afspraken", lambda v, t: [])):
    W.ARCHIEF_FOUT = ""
    try:
        _alle, _stukken = W._agenda_voor_mail()
    except Exception as e:  # noqa: BLE001
        _alle, _stukken = None, repr(e)
check("A15 de agenda voor de mailvergelijking noemt de agenda die niet gelezen is", _stukken == ["proef@agenda"] and len(_alle) == 1,
      str(_stukken))
import mail_afspraken as MA          # noqa: E402
_verg = []
with vervang((MA, "lees", lambda *a, **k: ([], [])), (MA, "vergelijk", lambda *a, **k: _verg.append(1) or [])):
    try:
        _res = MA.ronde([], "2026-10-01", agenda_onvolledig=["proef@agenda"])
        _ok15 = _res[0] == [] and _verg == []
    except TypeError as e:
        _ok15 = False
check("A15 met een onvolledige agenda vergelijkt de mailbron niet (statussen blijven staan)", _ok15)
_bron = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
check("A15 de ronde en de zorgronde geven de onvolledige agenda door", _bron.count("agenda_onvolledig=_stuk") == 2)

# opruimen van ritten op een onvolledige lezing
_weg = []
_rit = {"id": "rit1", "kalender": W.WERKAGENDA, "titel": "\U0001F697 Reistijd: thuis → Leuven", "start": _later.isoformat(),
        "einde": (_later + timedelta(minutes=30)).isoformat(), "locatie": "",
        "omschrijving": "Reistijd voor: Mehdi: [HA-KB] 2601 - Verdwenen (30 min, OSRM)", "_merk": {"agendawacht_rit": "rit1"}}
if not hasattr(W, "ONGELEZEN"):
    W.ONGELEZEN = set()          # oude code: de grendel bestaat niet, de proef toont dan dat er toch opgeruimd wordt
for ongelezen, verwacht in ((set(), ["rit1"]), ({"proef@agenda"}, [])):
    _weg.clear()
    W.ONGELEZEN.clear()
    W.ONGELEZEN.update(ongelezen)
    with vervang((W, "geen_auto_dagen", lambda: frozenset()), (W, "lara_vakantiedagen", lambda: frozenset()), (W, "_cache_laden", lambda: {}),
                 (W, "_cache_bewaren", lambda c: None), (W, "coord", lambda *a, **k: (50.88, 4.70)), (W.projectadressen, "index", lambda: {}),
                 (W, "_eigen_rit_weg", lambda x, tok: _weg.append(x["id"]) or True), (W, "_verplaats", lambda *a: _weg.append("verhuisd")),
                 (W.agenda, "_toegang", lambda: "t")):
        W.reistijd_zetten([dict(_rit)])
    check(f"A15/A17 een eigen rit zonder afspraak: {'opgeruimd' if verwacht else 'NIET opgeruimd als een agenda niet gelezen is'}",
          _weg == verwacht, str(_weg))
W.ONGELEZEN.clear()

# A14: het belrooster neemt de rit van deze afspraak
print("A14: belrooster")
_d = _later.replace(hour=9, minute=0)
_A = {**afspraak("A", "!! Mehdi: [HA-KB] 2601 - Alfa Proef"), "start": _d.isoformat(), "einde": (_d + timedelta(hours=1)).isoformat(),
      "locatie": "Proefstraat 1, 3000 Leuven"}
_B = {**afspraak("B", "!! Mehdi: [HA-KB] 2602 - Beta Proef"), "start": (_d + timedelta(hours=2, minutes=30)).isoformat(),
      "einde": (_d + timedelta(hours=3, minutes=30)).isoformat(), "locatie": "Proefkaai 2, 3000 Leuven"}
_ritA = {**afspraak("rA", "\U0001F697 Reistijd: thuis → Leuven"), "start": (_d - timedelta(minutes=30)).isoformat(), "einde": _d.isoformat(),
         "omschrijving": f"Reistijd voor: {_A['titel']} (30 min, OSRM)"}
_ritB = {**afspraak("rB", "\U0001F697 Reistijd: Leuven → Leuven"), "start": (_d + timedelta(hours=1, minutes=15)).isoformat(),
         "einde": (_d + timedelta(hours=2, minutes=30)).isoformat(), "omschrijving": f"Reistijd voor: {_B['titel']} (75 min, OSRM)"}
_rb = {r["sleutel"].split(":")[1]: r["tijd"][11:16] for r in W.belrooster([_A, _B, _ritA], _d.date().isoformat())}
check("A14 een rit van een andere afspraak bepaalt het beltijdstip niet", _rb.get("A") == "08:25" and _rb.get("B") != "08:25", str(_rb))
_rb = {r["sleutel"].split(":")[1]: r["tijd"][11:16] for r in W.belrooster([_A, _B, _ritA, _ritB], _d.date().isoformat())}
check("A14 met de eigen rit van B: vijf minuten voor het vertrek van die rit", _rb.get("B") == "10:10", str(_rb))
check("A14 het belrooster komt uit een lezing na de ritten (rooster_maken leest opnieuw)",
      "rooster = rooster_maken(" in _bron and "ruw, arch = afspraken(-1, 8), archief_afspraken(-1, 8)" in _bron)
_pr = W.belrooster([{**afspraak("P", "[PR] Proefconsult"), "kalender": "mehdipriveagena@gmail.com", "locatie": "Proefstraat 1, 3000 Leuven"}],
                   _later.date().isoformat())
check("A25 een privé-afspraak staat zonder titel in het belrooster (dat gaat naar Dropbox)",
      len(_pr) == 1 and "Proefconsult" not in _json.dumps(_pr, ensure_ascii=False), str(_pr))

# A13: een mislukte oproep bij een vastgelopen vraag telt niet als gebeld
print("A13 en A19: bellen")
_bv = os.path.join(TMP, "belvragen.json")
_tien = W.nu_lokaal().replace(hour=10, minute=0)
for uitkomst, verwacht in (([("twilio-vast", "mislukt: HTTPError")], False), ([("twilio-vast", "CA0123456789")], True)):
    if os.path.exists(_bv):
        os.remove(_bv)
    with vervang((W, "BELVRAGEN", _bv), (W, "vastgelopen", lambda *a, **k: [("k1", "Mehdi, proefvraag.")]),
                 (W.bellen, "afspraak_bellen_beschikbaar", lambda: True), (W.bellen, "beschikbaar", lambda: True),
                 (W.bellen, "callmebot_beschikbaar", lambda: False), (W.bellen, "bel_vast", lambda *a, **k: list(uitkomst)),
                 (W.bellen, "bel_afspraak", lambda *a, **k: [])):
        _z = W.bel_als_vastgelopen([], _tien)
    _bewaard = os.path.exists(_bv) and "k1" in _json.load(open(_bv))
    check(f"A13 vastgelopen: {'een echte oproep wordt bewaard' if verwacht else 'een mislukte start telt niet als gebeld'}",
          _bewaard == verwacht and bool(_z) == verwacht, f"{_bewaard} {_z}")
_gel = getattr(W.bellen, "gelukt", lambda r: None)
check("A13 bellen.gelukt: een call-sid is een oproep, een fout, lege sid of wachtmelding niet",
      _gel([("twilio", "CA1")]) and not _gel([("twilio", "")]) and not _gel([("twilio", "mislukt: X")])
      and not _gel([]) and not _gel([("telegram-oproep", "wait 65 seconds")]) and _gel([("telegram-oproep", "Calling")]))
try:
    _gs = (W.geplande_start(["agenda_wacht.py", "--ronde"], ["sh", "cron"]), W.geplande_start(["agenda_wacht.py", "--ronde"], ["bash", "sshd"]),
           W.geplande_start(["agenda_wacht.py"], ["sh", "cron"]))
except Exception as e:  # noqa: BLE001
    _gs = repr(e)
check("A19 alleen --ronde mét cron als voorouder is een geplande start; met de hand (ssh) belt nooit", _gs == (True, False, False), str(_gs))
check("A19 de belstap van de ronde vraagt een geplande start, niet alleen het argument",
      "if not DAG_ARG and geplande_start():" in _bron and 'if not DAG_ARG and "--ronde" in sys.argv:' not in _bron)

# A28: --slot-wacht beperkt het wachten op het rondeslot
print("A28: rondeslot")
_home = os.environ.get("HOME")
os.environ["HOME"] = TMP
_eerste = W.slot_nemen(max_wachten=0)
_wacht = []


class _Wacht(Exception):
    pass


def _slaap(t):
    _wacht.append(t)
    if len(_wacht) >= 3:
        raise _Wacht()


import time as _time                     # noqa: E402
_oargv, _osleep = sys.argv, _time.sleep
sys.argv, _time.sleep = ["agenda_wacht.py", "--dag", "2026-10-20", "--slot-wacht", "0"], _slaap
try:
    W.slot_nemen()
    _code = "kreeg het slot"
except SystemExit as e:
    _code = e.code
except _Wacht:
    _code = "bleef wachten"
finally:
    sys.argv, _time.sleep = _oargv, _osleep
    os.environ["HOME"] = _home or ""
check("A28 --slot-wacht 0: bezet slot geeft meteen exitcode 75, geen 900 seconden wachten", _code == 75, str(_code))

# A20: mail koppelen op een woorddeel
print("A20 en A21: mail")
_m = {"sleutel": "tekst|p", "soort": "tekst", "ics_uid": "", "recurrence_id": "", "sequence": 0, "dtstamp": "", "method": "",
      "geannuleerd": False, "start": _later.isoformat(), "einde": (_later + timedelta(hours=1)).isoformat(), "titel": "Project Beta",
      "locatie": "", "bron_mailbox": "mch@h-architects.be", "bron_message_id": "<p@x>", "bron_onderwerp": "Project Beta",
      "bron_ontvangen": W.nu_lokaal().isoformat(), "bron_afzender": "a@voorbeeld.test"}
_alfa = {"kalender": W.WERKAGENDA, "id": "alfa", "start": _later.isoformat(), "einde": (_later + timedelta(hours=1)).isoformat(),
         "titel": "Mehdi: [HA-IN] Project Alfa", "_icaluid": "alfa@google.com"}
_s1 = MA.vergelijk([_m], [_alfa])[0]["status"]
_s2 = MA.vergelijk([{**_m, "geannuleerd": True}], [_alfa])[0]["status"]
_s3 = MA.vergelijk([{**_m, "titel": "Overleg Proef"}], [{**_alfa, "titel": "Mehdi: [HA-IN] Overleg Proef"}])[0]["status"]
_s4 = MA.vergelijk([{**_m, "titel": "Overleg Proef"}], [{**_alfa, "titel": "Mehdi: [HA-IN] Overleg Proef"},
                                                         {**_alfa, "id": "tweede", "titel": "Mehdi: [HA-IN] Overleg Proef bis"}])[0]["status"]
check("A20 'Project Beta' tegen 'Project Alfa' op hetzelfde uur is een kandidaat, niet gekoppeld", _s1 == "kandidaat", _s1)
check("A20 een annulering van Beta wijst Alfa niet aan om te schrappen", _s2 == "geannuleerd", _s2)
check("A20 regressie: hetzelfde onderwerp blijft gekoppeld", _s3 == "gekoppeld", _s3)
check("A20 twee items die passen: twijfel, dus een kandidaat", _s4 == "kandidaat", _s4)

import re as _re                         # noqa: E402
_pl = (HIER / "koppelingen" / "post_lezer.py").read_text(encoding="utf-8")
_geen = _re.compile(_re.search(r'GEEN_AFSPRAAK = re\.compile\(r"([^"]+)"', _pl).group(1), _re.I)
check("A21 een jaarlijkse archiefmap wordt gelezen voor gewone afspraken; prullenbak en verzonden niet",
      not _geen.search("INBOX.Archief.2026") and _geen.search("INBOX.Trash") and _geen.search("INBOX.Verzonden"))

# A10: een rit is van mij als merk en eigen ID kloppen, niet omdat de tekst lijkt
print("A10: eigendom van ritten")
_dels = []


class _Antw:
    def read(self):
        return b"{}"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _nep_urlopen(req, timeout=None):
    _dels.append((req.get_method(), req.full_url))
    return _Antw()


_tekst = {"kalender": W.WERKAGENDA, "titel": "\U0001F697 Reistijd: thuis → Leuven", "start": _later.isoformat(),
          "einde": (_later + timedelta(minutes=30)).isoformat(), "omschrijving": "Reistijd voor: Mehdi: [HA-KB] 2601 - X (30 min, OSRM)"}
_rm = getattr(W, "RITMERK", "agendawacht_rit")
with vervang((_ur, "urlopen", _nep_urlopen), (W, "mag_schrijven", lambda k: True)):
    _e1 = veilig(lambda: W._eigen_rit_weg({**_tekst, "id": "ritaaa", "_merk": {_rm: "ritaaa"}}, "t"))
    _e2 = veilig(lambda: W._eigen_rit_weg({**_tekst, "id": "kopie1", "_merk": {_rm: "ritaaa"}}, "t"))
    _e3 = veilig(lambda: W._eigen_rit_weg({**_tekst, "id": "oud1"}, "t"))
_wegg = [u.rsplit("/", 1)[-1].split("?")[0] for m_, u in _dels if m_ == "DELETE"]
check("A10 een rit met mijn merk en zijn eigen ID gaat weg", "ritaaa" in _wegg, str(_wegg))
check("A10 een kopie met hetzelfde merk maar een ander ID blijft staan", "kopie1" not in _wegg, str(_wegg))
check("A10 een oude rit met alleen mijn tekst wordt niet meer weggehaald", "oud1" not in _wegg, str(_wegg))
_nr = veilig(lambda: W._nieuwe_rit())
check("A10 een nieuwe rit krijgt een eigen ID (base32hex) en een merk met datzelfde ID",
      isinstance(_nr, dict) and _nr["extendedProperties"]["private"][_rm] == _nr["id"] and _re.fullmatch(r"[a-v0-9]{5,1024}", _nr["id"]),
      str(_nr))
check("A10 beide ritten (heen en terug) worden met dat merk aangemaakt",
      "heen_privaat = _nieuwe_rit()" in _bron and "**heen_privaat}, tok)" in _bron
      and "**_nieuwe_rit()}, tok)" in _bron)
# overgang: een oude rit die aan zijn afspraak hangt krijgt zijn merk; een oude rit zonder afspraak niet
_mk, _weg2 = [], []
_afs = afspraak("a10", "!! Mehdi: [HA-KB] 2601 - X", locatie="Proefstraat 1, 3000 Leuven")
_oud_vast = {**_tekst, "id": "oudvast", "start": (_later - timedelta(minutes=30)).isoformat(), "einde": _later.isoformat(),
             "omschrijving": "Reistijd voor: !! Mehdi: [HA-KB] 2601 - X (30 min, OSRM)"}
_oud_ander = {**_tekst, "id": "oudander", "start": (_later - timedelta(minutes=20)).isoformat(),
              "einde": _later.isoformat(), "omschrijving": "Reistijd voor: !! Mehdi: [HA-KB] 2699 - Andere (30 min, OSRM)"}
_oud_los = {**_tekst, "id": "oudlos", "start": (_later + timedelta(days=1)).isoformat(), "einde": (_later + timedelta(days=1, minutes=30)).isoformat()}
W.ONGELEZEN.clear()
with vervang((W, "geen_auto_dagen", lambda: frozenset(["2000-01-01"])), (W, "lara_vakantiedagen", lambda: frozenset()),
             (W, "_cache_laden", lambda: {}), (W, "_cache_bewaren", lambda c: None), (W, "coord", lambda *a, **k: (50.88, 4.70)),
             (W.projectadressen, "index", lambda: {}), (W, "_insert", lambda *a, **k: {}),
             (W, "_patch", lambda a, body, tok, toch=False: _mk.append((a.get("id"), body))),
             (W, "_eigen_rit_weg", lambda x, tok: _weg2.append(x["id"]) or True), (W, "_verplaats", lambda *a: _weg2.append("verhuisd")),
             (W, "rijtijd_min", lambda *a, **k: (30, 1.0)), (W.agenda, "_toegang", lambda: "t")):
    _r10 = veilig(lambda: W.reistijd_zetten([dict(_afs), dict(_oud_vast), dict(_oud_los), dict(_oud_ander)]))
_gemerkt = [i for i, b in _mk if "extendedProperties" in b]
check("A10 overgang: een oude rit die aan zijn afspraak hangt, krijgt zijn merk (eigen ID)",
      ("oudvast", {"extendedProperties": {"private": {_rm: "oudvast"}}}) in _mk, f"{_mk} {_r10}")
check("A10 overgang (ronde 3): een oude rit die op het juiste uur eindigt maar een andere afspraak noemt, krijgt geen merk",
      "oudander" not in _gemerkt and "oudander" not in _weg2, f"{_gemerkt} {_weg2}")
check("A10 overgang: een oude rit zonder afspraak krijgt geen merk en wordt niet weggehaald",
      "oudlos" not in _gemerkt and "oudlos" not in _weg2, f"{_gemerkt} {_weg2}")

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

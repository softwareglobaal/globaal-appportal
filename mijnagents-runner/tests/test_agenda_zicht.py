"""Grendel: Mehdi ziet alleen wat hij moet doen of waar hij bij moet zijn (driehoeksoverleg 27-10-2026, Z1 tot Z7).

Mehdi verbergt de firma-agenda's van collega's (Elevait N.V., High Design Studio NV) in zijn weergave. De agent leest ze
alleen mee: een afspraak met 'Mehdi: ...' vooraan krijgt Mehdi als stille gast (zonder mail), zodat ze op zijn
werkagenda staat; wat hem lijkt aan te gaan maar niet doorkomt, wordt eenmaal een vraag in zijn privé-agenda. Verder
schrijft de agent niets op een firma-agenda, en Calendly verandert niet. Geen netwerk: alle Google-aanroepen nagemaakt.
"""
import io
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

os.environ["BELLEN_UIT"] = "1"
HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W          # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


taken = json.loads((HIER / "werkwijze" / "agenda-taken.json").read_text(encoding="utf-8"))
firma = W.firma_meelezen()
ELEVAIT = "elevaitservices@gmail.com"

# --- Z1, Z6, Z7: de firma-agenda's zijn alleen meelezen ---------------------------------------------------------
check("Elevait N.V. en High Design Studio NV staan als firma-agenda om mee te lezen, uit agenda-taken.json",
      {a for a, _ in firma} == {ELEVAIT, "hdssuriname@gmail.com"}, str(firma))
check("geen firma-agenda staat in KALENDERS: de agent verwerkt ze niet als Mehdi's agenda", not ({a for a, _ in firma} & set(W.KALENDERS)))
W._arch_cache = None
_oud_arch = W.gearchiveerd
W.gearchiveerd = lambda: set()
try:
    check("de agent mag niet schrijven op een firma-agenda (geen rit, kleur of vraag)", not W.mag_schrijven(ELEVAIT))
    try:
        W._insert(ELEVAIT, {"summary": "x", "start": {"date": "2026-11-02"}, "end": {"date": "2026-11-03"}}, "tok")
        _ins_ok = True
    except W.GeenSchrijfrecht:
        _ins_ok = False
    check("een nieuw item op een firma-agenda wordt geweigerd", not _ins_ok)
finally:
    W.gearchiveerd = _oud_arch
_cal = json.dumps(taken.get("agendas_calendly"), ensure_ascii=False)
check("Calendly telt geen firma-agenda als bezet (Z7)", not any(a in _cal for a, _ in firma), _cal[:200])

# --- wie gaat Mehdi aan -------------------------------------------------------------------------------------
for t in ("Mehdi: [EL-IN] overleg", "!! Mehdi: [HA-KB] werfbezoek", "Mehdi, Angela, Shaniel & Siyan: [EL-IN] Wekelijkse",
          "VR !! Mehdi: [UB-PO] klant", "Mehdi & Siyan: [EL-PO] intake"):
    check(f"'{t[:30]}' gaat Mehdi aan", bool(W.MEHDI_VOORAAN.match(t)))
for t in ("SAIS26 | Executive Coffee & Networking", "Siyan: intake, met Mehdi later", "Elevait-Intake gesprek: Sunaijna",
          "Birthday: Angela"):
    check(f"'{t[:30]}' gaat Mehdi niet aan", not W.MEHDI_VOORAAN.match(t))

# --- Z2: de stille gast ----------------------------------------------------------------------------------------
_nu = W.nu_lokaal()
_morgen = (_nu + timedelta(days=1)).date().isoformat()


def ev(eid, titel, gasten=None, beschrijving="", reeks=None):
    e = {"id": eid, "summary": titel, "status": "confirmed", "description": beschrijving, "iCalUID": f"{eid}@google.com",
         "etag": f'"e-{eid}"', "start": {"dateTime": f"{_morgen}T10:00:00+01:00"},
         "end": {"dateTime": f"{_morgen}T11:00:00+01:00"}, "attendees": gasten or [], "kalender": ELEVAIT,
         "_agendanaam": "Elevait N.V."}
    if reeks:
        e["recurringEventId"] = reeks
    return e


class NepGoogle:
    """Nagemaakte Google: GET van een afspraak (vers, met etag), PATCH met If-Match, de lijst van de werkagenda op
    iCalUID (zichtbaar of niet), de privé-agenda op firmamerk, en firma-agenda's over twee pagina's."""

    def __init__(self, items, zichtbaar=True, botsing=(), bestaande_vraag=False):
        self.items = {e["id"]: e for e in items}
        self.patches, self.zichtbaar, self.botsing, self.bestaande_vraag = [], zichtbaar, set(botsing), bestaande_vraag

    def __call__(self, req, timeout=None, *a, **k):
        url = getattr(req, "full_url", req)
        u = urllib.parse.urlparse(url)
        q = dict(urllib.parse.parse_qsl(u.query))
        methode = req.get_method() if hasattr(req, "get_method") else "GET"
        if methode == "PATCH":
            eid = urllib.parse.unquote(u.path.rsplit("/", 1)[1])
            if eid in self.botsing:
                raise urllib.error.HTTPError(url, 412, "Precondition Failed", {}, None)
            body = json.loads(req.data)
            self.patches.append((url, body, req.get_header("If-match")))
            return io.BytesIO(json.dumps({**self.items[eid], "attendees": body["attendees"]}).encode())
        if "iCalUID" in q:
            return io.BytesIO(json.dumps({"items": [{"id": "x", "status": "confirmed"}] if self.zichtbaar else []}).encode())
        if "privateExtendedProperty" in q:
            return io.BytesIO(json.dumps({"items": [{"id": "v"}] if self.bestaande_vraag else []}).encode())
        if "/events/" in u.path:
            eid = urllib.parse.unquote(u.path.rsplit("/", 1)[1])
            return io.BytesIO(json.dumps(self.items[eid]).encode())
        if u.path.endswith("/events"):
            kal = urllib.parse.unquote(u.path.split("/calendars/")[1].split("/events")[0])
            alle = [e for e in self.items.values() if e.get("kalender") == kal and not e.get("_moeder")]
            if q.get("pageToken") == "2":
                return io.BytesIO(json.dumps({"items": alle[1:]}).encode())
            return io.BytesIO(json.dumps({"items": alle[:1], **({"nextPageToken": "2"} if len(alle) > 1 else {})}).encode())
        raise OSError(f"onverwachte vraag {url[:80]}")


import urllib.request as _ur  # noqa: E402
_echt = _ur.urlopen


def met(g, f, *a):
    _ur.urlopen = g
    try:
        return f(*a)
    finally:
        _ur.urlopen = _echt


_siyan = {"email": "siyan@voorbeeld.test", "responseStatus": "accepted", "organizer": True, "self": False,
          "comment": "ik neem de laptop mee", "additionalGuests": 1}
evs = [ev("a1", "Mehdi: [EL-IN] overleg Elevait"),
       ev("a2", "SAIS26 | Executive Coffee & Networking"),
       ev("a3", "Mehdi: [EL-PO] klant", gasten=[{"email": W.WERKAGENDA, "responseStatus": "accepted"}]),
       ev("a4", "Mehdi: [EL-IN] met gast", gasten=[_siyan])]
g = NepGoogle(evs)
regels, niet = met(g, W.firma_gasten, evs, "tok")
check("alleen de twee 'Mehdi: ...'-afspraken zonder Mehdi als gast krijgen een patch", len(g.patches) == 2, str(g.patches))
check("de patch draagt alleen 'attendees', gaat zonder mail en met If-Match op de etag",
      all(set(b) == {"attendees"} and "sendUpdates=none" in u and m and m.startswith('"e-') for u, b, m in g.patches),
      str(g.patches))
_a4 = next(b for u, b, _ in g.patches if "/a4" in u)["attendees"]
check("bestaande gasten blijven staan met al hun velden (opmerking, extra gasten), Mehdi komt erbij",
      _a4[0] == {k: v for k, v in _siyan.items() if k in W.GASTVELDEN} and _a4[1]["email"] == W.WERKAGENDA, str(_a4))
check("staat de afspraak daarna zichtbaar op de werkagenda, dan geen vangnet", not niet, str(niet))

g2 = NepGoogle([ev("b1", "Mehdi: [EL-IN] overleg")], zichtbaar=False)
_, niet2 = met(g2, W.firma_gasten, list(g2.items.values()), "tok")
check("komt de afspraak niet zichtbaar op de werkagenda (verborgen uitnodiging), dan gaat ze naar het vangnet",
      len(niet2) == 1)

g3 = NepGoogle([ev("c9", "Mehdi: [EL-IN] overleg")], botsing={"c9"})
r3, _ = met(g3, W.firma_gasten, list(g3.items.values()), "tok")
check("veranderde een collega de afspraak intussen (412), dan wordt niets overschreven en volgt de volgende ronde",
      not g3.patches and any("intussen veranderd" in r for r in r3), str(r3))

_moeder = {"id": "reeks1", "summary": "Mehdi: [EL-IN] wekelijkse meeting", "etag": '"e-reeks1"', "attendees": [],
           "kalender": ELEVAIT, "_moeder": True}
_inst = [ev(f"reeks1_2026110{i}", "Mehdi: [EL-IN] wekelijkse meeting", reeks="reeks1") for i in (2, 3)]
g4 = NepGoogle([_moeder] + _inst)
met(g4, W.firma_gasten, _inst, "tok")
check("een reeks met Mehdi vooraan krijgt de gast een keer in de reeks zelf, niet per keer",
      len(g4.patches) == 1 and "/reeks1?" in g4.patches[0][0], str([u for u, _, _ in g4.patches]))

g5 = NepGoogle([ev("p1", "x"), ev("p2", "y"), ev("p3", "z")])
_pag = met(g5, W.firma_afspraken, "tok")
check("de firma-agenda's worden over alle pagina's gelezen", _pag is not None and len([e for e in _pag if e["kalender"] == ELEVAIT]) == 3,
      str(_pag and len(_pag)))
check("het leesvenster gaat even ver als de ritten (365 dagen)", W.FIRMA_VOORUIT_DAGEN >= 365)

# --- Z3: het vangnet, eenmaal per afspraak --------------------------------------------------------------------
_ins = []
_o = (W._insert, W.FIRMA_VRAGEN)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins.append((kal, body)) or {"id": "v1"}
try:
    _evs = [ev("c1", "Overleg KDS", beschrijving="Mehdi beslist mee"), ev("c2", "SAIS26 | Opening"),
            ev("c3", "Klant X met Mehdi", gasten=[{"email": W.WERKAGENDA}])]
    g6 = NepGoogle(_evs)
    r1 = met(g6, W.firma_vangnet, _evs, niet2, "tok")
    r2 = met(g6, W.firma_vangnet, _evs, niet2, "tok")
    # na een time-out stond de vraag er al, maar het register wist het niet: geen tweede vraag
    W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma2-")) / "agenda-firma-vragen.json")
    _n = len(_ins)
    met(NepGoogle(_evs, bestaande_vraag=True), W.firma_vangnet, _evs, niet2, "tok")
finally:
    W._insert, W.FIRMA_VRAGEN = _o
check("het vangnet zet een vraag voor de afspraak die Mehdi noemt en voor de afspraak die niet doorkwam",
      _n == 2 and all(k == W.PRIVE_AGENDA for k, _ in _ins[:2]), str([b["description"][:60] for _, b in _ins]))
check("de tweede ronde zet geen tweede vraag", not any("vraag gezet" in r for r in r2), str(r2))
check("staat de vraag er al (na een time-out), dan geen tweede vraag", len(_ins) == _n, str(len(_ins)))
check("de vraag is een eigen melding: Beschikbaar, zonder herinnering, met mailmerk en firmamerk",
      all(b["transparency"] == "transparent" and b["reminders"]["overrides"] == []
          and len(b["extendedProperties"]["private"][W.MAILMERK]) == 16 and b["extendedProperties"]["private"][W.FIRMAMERK]
          for _, b in _ins))
check("de vraag sluit geen dag af",
      all(not W.markeringen_uit([{"titel": b["summary"], "start": b["start"]["date"], "einde": b["end"]["date"],
                                  "hele_dag": True}], b["start"]["date"]) for _, b in _ins))

# --- Z4: de zichtbaarheid teruglezen -------------------------------------------------------------------------
_ur.urlopen = lambda req, timeout=None, *a, **k: io.BytesIO(json.dumps({"items": [
    {"id": ELEVAIT, "selected": False}, {"id": W.WERKAGENDA, "selected": True}, {"id": "zonder"}]}).encode())
_otok = W.agenda._toegang
W.agenda._toegang = lambda: "tok"
try:
    zicht = W.agenda.zichtbaarheid()
finally:
    _ur.urlopen = _echt
    W.agenda._toegang = _otok
check("de zichtbaarheid per agenda is terug te lezen (selected)",
      zicht == {ELEVAIT: False, W.WERKAGENDA: True, "zonder": False}, str(zicht))

# --- een onleesbare firma-agenda: geen gast en geen vangnet op een halve lezing --------------------------------
_ur.urlopen = lambda *a, **k: (_ for _ in ()).throw(OSError("netwerk weg"))
try:
    check("een firma-agenda die niet te lezen is, geeft None (niets doen)", W.firma_afspraken("tok") is None)
finally:
    _ur.urlopen = _echt

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

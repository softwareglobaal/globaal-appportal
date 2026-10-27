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


def ev(eid, titel, gasten=None, beschrijving=""):
    return {"id": eid, "summary": titel, "status": "confirmed", "description": beschrijving,
            "start": {"dateTime": f"{_morgen}T10:00:00+01:00"}, "end": {"dateTime": f"{_morgen}T11:00:00+01:00"},
            "attendees": gasten or [], "kalender": ELEVAIT, "_agendanaam": "Elevait N.V."}


class NepGoogle:
    def __init__(self, zichtbaar=True):
        self.patches, self.zichtbaar = [], zichtbaar

    def __call__(self, req, timeout=None, *a, **k):
        url = getattr(req, "full_url", req)
        if getattr(req, "get_method", lambda: "GET")() == "PATCH":
            body = json.loads(req.data)
            self.patches.append((url, body))
            return io.BytesIO(json.dumps({"id": "x", "attendees": body["attendees"]}).encode())
        if f"/calendars/{urllib.parse.quote(W.WERKAGENDA, safe='')}/events/" in url:
            if not self.zichtbaar:
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            return io.BytesIO(json.dumps({"id": "x", "status": "confirmed"}).encode())
        raise OSError(f"onverwachte vraag {url[:80]}")


_oud_url = W.urllib.request.urlopen if hasattr(W, "urllib") else None
import urllib.request as _ur  # noqa: E402
_echt = _ur.urlopen
g = NepGoogle()
_ur.urlopen = g
try:
    evs = [ev("a1", "Mehdi: [EL-IN] overleg Elevait"),
           ev("a2", "SAIS26 | Executive Coffee & Networking"),
           ev("a3", "Mehdi: [EL-PO] klant", gasten=[{"email": W.WERKAGENDA, "responseStatus": "accepted"}]),
           ev("a4", "Mehdi: [EL-IN] met gast", gasten=[{"email": "siyan@voorbeeld.test", "responseStatus": "accepted",
                                                         "organizer": True, "self": False}])]
    regels, niet = W.firma_gasten(evs, "tok")
finally:
    _ur.urlopen = _echt
check("alleen de twee 'Mehdi: ...'-afspraken zonder Mehdi als gast krijgen een patch", len(g.patches) == 2, str(g.patches))
check("de patch draagt alleen 'attendees' en gaat zonder mail (sendUpdates=none)",
      all(set(b) == {"attendees"} and "sendUpdates=none" in u for u, b in g.patches), str(g.patches))
check("bestaande gasten blijven staan en Mehdi komt erbij",
      any([x["email"] for x in b["attendees"]] == ["siyan@voorbeeld.test", W.WERKAGENDA] for _, b in g.patches))
check("staat de afspraak daarna op de werkagenda, dan geen vangnet", not niet, str(niet))

g2 = NepGoogle(zichtbaar=False)
_ur.urlopen = g2
try:
    _, niet2 = W.firma_gasten([ev("b1", "Mehdi: [EL-IN] overleg")], "tok")
finally:
    _ur.urlopen = _echt
check("komt de afspraak niet op de werkagenda (instelling van Google), dan gaat ze naar het vangnet", len(niet2) == 1)

# --- Z3: het vangnet, eenmaal per afspraak --------------------------------------------------------------------
_ins = []
_o = (W._insert, W.FIRMA_VRAGEN)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins.append((kal, body)) or {"id": "v1"}
try:
    _evs = [ev("c1", "Overleg KDS", beschrijving="Mehdi beslist mee"), ev("c2", "SAIS26 | Opening"),
            ev("c3", "Klant X met Mehdi", gasten=[{"email": W.WERKAGENDA}])]
    r1 = W.firma_vangnet(_evs, niet2, "tok")
    r2 = W.firma_vangnet(_evs, niet2, "tok")
finally:
    W._insert, W.FIRMA_VRAGEN = _o
check("het vangnet zet een vraag voor de afspraak die Mehdi noemt en voor de afspraak die niet doorkwam",
      len(_ins) == 2 and all(k == W.PRIVE_AGENDA for k, _ in _ins), str([b["description"][:60] for _, b in _ins]))
check("de tweede ronde zet geen tweede vraag", len(_ins) == 2 and not any("vraag gezet" in r for r in r2), str(r2))
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

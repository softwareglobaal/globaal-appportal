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

    def __init__(self, items, zichtbaar=True, botsing=(), bestaande_vraag=False, vers=None, ander_uur=False):
        self.items = {e["id"]: e for e in items}
        self.patches, self.zichtbaar, self.botsing, self.bestaande_vraag = [], zichtbaar, set(botsing), bestaande_vraag
        self.vers, self.ander_uur = vers or {}, ander_uur

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
            e = next((x for x in self.items.values() if x.get("iCalUID") == q["iCalUID"]), {})
            st = dict(e.get("start") or {})
            if self.ander_uur:
                st = {"dateTime": f"{_morgen}T15:00:00+01:00"}        # een andere keer van dezelfde reeks
            return io.BytesIO(json.dumps({"items": [{"id": "x", "status": "confirmed", "start": st}] if self.zichtbaar else []}).encode())
        if "privateExtendedProperty" in q:
            if self.bestaande_vraag == "pagina2":
                if q.get("pageToken") == "2":
                    return io.BytesIO(json.dumps({"items": [{"id": "v"}]}).encode())
                return io.BytesIO(json.dumps({"items": [], "nextPageToken": "2"}).encode())
            return io.BytesIO(json.dumps({"items": [{"id": "v"}] if self.bestaande_vraag else []}).encode())
        if "/events/" in u.path:
            eid = urllib.parse.unquote(u.path.rsplit("/", 1)[1])
            return io.BytesIO(json.dumps({**self.items[eid], **self.vers.get(eid, {})}).encode())
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

g7 = NepGoogle([ev("d1", "Mehdi: [EL-IN] overleg", gasten=[{"email": W.WERKAGENDA}])], ander_uur=True)
_, niet7 = met(g7, W.firma_gasten, list(g7.items.values()), "tok")
check("staat alleen een andere keer van dezelfde reeks op de werkagenda, dan telt deze keer als niet zichtbaar",
      len(niet7) == 1, str(niet7))
g8 = NepGoogle([ev("e1", "Mehdi: [EL-IN] overleg")], vers={"e1": {"summary": "Siyan: [EL-IN] overleg"}})
r8, _ = met(g8, W.firma_gasten, list(g8.items.values()), "tok")
check("veranderde de collega de titel intussen naar zichzelf, dan wordt Mehdi niet toegevoegd",
      not g8.patches and any("niet meer voor Mehdi" in r for r in r8), str((g8.patches, r8)))
g8b = NepGoogle([ev("e2", "Mehdi: [EL-IN] overleg")], vers={"e2": {"status": "cancelled"}})
met(g8b, W.firma_gasten, list(g8b.items.values()), "tok")
check("een intussen geschrapte afspraak krijgt geen gast", not g8b.patches)
check("een bestaande vraag wordt ook op een volgende zoekpagina gevonden",
      met(NepGoogle([], bestaande_vraag="pagina2"), W._prive_vraag_bestaat, "elevait|x", "tok") is True)

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
_zwak = [b for _, b in _ins if "date" in b["start"]]
_sterk = [b for _, b in _ins if "dateTime" in b["start"]]
check("elke vraag is een eigen melding zonder herinnering, met mailmerk en firmamerk",
      all(b["reminders"]["overrides"] == [] and len(b["extendedProperties"]["private"][W.MAILMERK]) == 16
          and b["extendedProperties"]["private"][W.FIRMAMERK] for _, b in _ins))
check("een afspraak die Mehdi alleen noemt: een dagvraag op Beschikbaar die geen dag afsluit",
      len(_zwak) == 1 and _zwak[0]["transparency"] == "transparent"
      and not W.markeringen_uit([{"titel": _zwak[0]["summary"], "start": _zwak[0]["start"]["date"],
                                  "einde": _zwak[0]["end"]["date"], "hele_dag": True}], _zwak[0]["start"]["date"]))
check("een 'Mehdi: ...'-afspraak die niet doorkwam: een Bezet blok op haar eigen uur (Calendly boekt er niet over)",
      len(_sterk) == 1 and "transparency" not in _sterk[0] and _sterk[0]["start"]["dateTime"].endswith("10:00:00+01:00"))

# --- Codex-hertest 2: oorspronkelijke tijd, gemengde reeks, H-Architects en UNABO, vraag volgt de afspraak ---------
_e7 = ev("f1_20261102T090000Z", "Mehdi: [EL-IN] overleg", gasten=[{"email": W.WERKAGENDA}], reeks="f1")
_e7["originalStartTime"] = {"dateTime": "2026-11-02T10:00:00+01:00"}


class _Nep7(NepGoogle):
    def __call__(self, req, timeout=None, *a, **k):
        url = getattr(req, "full_url", req)
        if "iCalUID" in url:        # een andere verplaatste keer van dezelfde reeks op hetzelfde uur
            return io.BytesIO(json.dumps({"items": [{"id": "y", "status": "confirmed", "start": _e7["start"],
                                                     "originalStartTime": {"dateTime": "2026-11-09T10:00:00+01:00"}}]}).encode())
        return super().__call__(req, timeout, *a, **k)


_, niet7b = met(_Nep7([_e7]), W.firma_gasten, [_e7], "tok")
check("twee verplaatste keren op hetzelfde uur: de oorspronkelijke tijd beslist (niet zichtbaar)", len(niet7b) == 1)
_moeder2 = {"id": "reeks2", "summary": "Mehdi: [EL-IN] meeting", "etag": '"e-reeks2"', "attendees": [], "kalender": ELEVAIT,
            "_moeder": True}
_gem = [ev("reeks2_20261102", "Mehdi: [EL-IN] meeting", reeks="reeks2"), ev("reeks2_20261109", "Siyan: [EL-IN] meeting", reeks="reeks2")]
g11 = NepGoogle([_moeder2] + _gem)
met(g11, W.firma_gasten, _gem, "tok")
check("een gemengde reeks (een keer voor een collega): alleen de keer voor Mehdi krijgt de gast, niet de hele reeks",
      [u.split("/events/")[1].split("?")[0] for u, _, _ in g11.patches] == ["reeks2_20261102"], str([u for u, _, _ in g11.patches]))
check("H-Architects en UNABO worden ook gescand voor de stille gast (Mehdi verbergt ze ook)",
      {"73e8b6359d04b7bdb02aa045e668cd6f9d9f007bec51ce370494e7de7501f0c4@group.calendar.google.com",
       "b135d9900db83399539bb5fe4ad9dc1ace19af20273c078ce2180cc47e9232fe@group.calendar.google.com"}
      <= {a for a, _ in W.firma_scan()})
_ins13, _opg13 = [], []
_o13 = (W._insert, W.FIRMA_VRAGEN, W._prive_item_lezen, W._eigen_melding_opgelost)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma13-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins13.append(body) or {"id": f"q{len(_ins13)}"}
W._prive_item_lezen = lambda eid, tok: {"id": eid, "titel": "VR Agendawacht: x", "_merk": {W.FIRMAMERK: f"{ELEVAIT}|g1",
                                                                                          W.MAILMERK: "abcdef0123456789"}}
W._eigen_melding_opgelost = lambda x, k, tok, nu, reden="": _opg13.append(x["id"]) or True
try:
    _g1 = ev("g1", "Overleg KDS", beschrijving="Mehdi beslist mee")
    met(NepGoogle([_g1]), W.firma_vangnet, [_g1], [], "tok")
    _g1b = dict(_g1, start={"dateTime": f"{(_nu + timedelta(days=2)).date().isoformat()}T10:00:00+01:00"})
    met(NepGoogle([_g1b]), W.firma_vangnet, [_g1b], [], "tok")
    met(NepGoogle([]), W.firma_vangnet, [], [], "tok")
finally:
    W._insert, W.FIRMA_VRAGEN, W._prive_item_lezen, W._eigen_melding_opgelost = _o13
check("verschuift de afspraak, dan krijgt de oude vraag 'Opgelost' en komt er een op de nieuwe dag; verdwijnt ze, dan opgelost",
      len(_ins13) == 2 and _opg13 == ["q1", "q2"], str((len(_ins13), _opg13)))

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

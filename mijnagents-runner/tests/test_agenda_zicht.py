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
         "_agendanaam": "Elevait N.V.", "organizer": {"email": ELEVAIT}}
    if reeks:
        e["recurringEventId"] = reeks
    return e


class NepGoogle:
    """Nagemaakte Google: GET van een afspraak (vers, met etag), PATCH met If-Match, de lijst van de werkagenda op
    iCalUID (zichtbaar of niet), de privé-agenda op firmamerk, en firma-agenda's over twee pagina's."""

    def __init__(self, items, zichtbaar=True, botsing=(), bestaande_vraag=False, vers=None, ander_uur=False,
                 botsing_keer=None, onleesbaar=(), weg=()):
        self.items = {e["id"]: e for e in items}
        self.patches, self.zichtbaar, self.botsing, self.bestaande_vraag = [], zichtbaar, set(botsing), bestaande_vraag
        self.vers, self.ander_uur = vers or {}, ander_uur
        self.botsing_keer, self.onleesbaar, self.weg = dict(botsing_keer or {}), set(onleesbaar), set(weg)

    def __call__(self, req, timeout=None, *a, **k):
        url = getattr(req, "full_url", req)
        u = urllib.parse.urlparse(url)
        q = dict(urllib.parse.parse_qsl(u.query))
        methode = req.get_method() if hasattr(req, "get_method") else "GET"
        if methode == "PATCH":
            eid = urllib.parse.unquote(u.path.rsplit("/", 1)[1])
            if eid in self.botsing or self.botsing_keer.get(eid, 0) > 0:
                self.botsing_keer[eid] = self.botsing_keer.get(eid, 0) - 1
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
            if self.bestaande_vraag == "opgelost":
                return io.BytesIO(json.dumps({"items": [{"id": "oud", "extendedProperties": {"private": {
                    W.MAILMERK: "opgelost:abcdef0123456789"}}}]}).encode())
            if self.bestaande_vraag == "pagina2":
                if q.get("pageToken") == "2":
                    return io.BytesIO(json.dumps({"items": [{"id": "v"}]}).encode())
                return io.BytesIO(json.dumps({"items": [], "nextPageToken": "2"}).encode())
            return io.BytesIO(json.dumps({"items": [{"id": "v"}] if self.bestaande_vraag else []}).encode())
        if "/events/" in u.path:
            eid = urllib.parse.unquote(u.path.rsplit("/", 1)[1])
            if eid in self.weg:
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            return io.BytesIO(json.dumps({**self.items[eid], **self.vers.get(eid, {})}).encode())
        if u.path.endswith("/events"):
            kal = urllib.parse.unquote(u.path.split("/calendars/")[1].split("/events")[0])
            if kal in self.onleesbaar:
                raise urllib.error.HTTPError(url, 500, "Backend Error", {}, None)
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
regels, niet, _, _ = met(g, W.firma_gasten, evs, "tok")
check("alleen de twee 'Mehdi: ...'-afspraken zonder Mehdi als gast krijgen een patch", len(g.patches) == 2, str(g.patches))
check("de patch draagt alleen 'attendees', gaat zonder mail en met If-Match op de etag",
      all(set(b) == {"attendees"} and "sendUpdates=none" in u and m and m.startswith('"e-') for u, b, m in g.patches),
      str(g.patches))
_a4 = next(b for u, b, _ in g.patches if "/a4" in u)["attendees"]
check("bestaande gasten blijven staan met al hun velden (opmerking, extra gasten), Mehdi komt erbij",
      _a4[0] == {k: v for k, v in _siyan.items() if k in W.GASTVELDEN} and _a4[1]["email"] == W.WERKAGENDA, str(_a4))
check("staat de afspraak daarna zichtbaar op de werkagenda, dan geen vangnet", not niet, str(niet))

g2 = NepGoogle([ev("b1", "Mehdi: [EL-IN] overleg")], zichtbaar=False)
_, niet2a, onz2a, _ = met(g2, W.firma_gasten, list(g2.items.values()), "tok")
check("net als gast gezet en nog niet zichtbaar: deze ronde geen blok (Google toont de kopie soms even later)",
      not niet2a and onz2a == {f"firma|b1@google.com|"}, str((niet2a, onz2a)))
_b1 = ev("b1", "Mehdi: [EL-IN] overleg", gasten=[{"email": W.WERKAGENDA, "responseStatus": "needsAction"}])
_, niet2, _, _ = met(NepGoogle([_b1], zichtbaar=False), W.firma_gasten, [_b1], "tok")
check("de ronde erna, met Mehdi al als gast en nog altijd niet zichtbaar (verborgen uitnodiging): naar het vangnet",
      len(niet2) == 1)

g3 = NepGoogle([ev("c9", "Mehdi: [EL-IN] overleg")], botsing={"c9"},
              vers={"c9": {"start": {"dateTime": f"{_morgen}T14:00:00+01:00"}, "end": {"dateTime": f"{_morgen}T15:00:00+01:00"}}})
r3, niet3, _, _ = met(g3, W.firma_gasten, list(g3.items.values()), "tok")
check("blijft een collega de afspraak veranderen (412), dan wordt niets overschreven",
      not g3.patches and any("bleef veranderen" in r for r in r3), str(r3))
check("en gaat de afspraak zoals ze nu is (nieuw uur) naar het vangnet (Codex-hertest 3, punt 16)",
      len(niet3) == 1 and niet3[0]["start"]["dateTime"].endswith("14:00:00+01:00"), str(niet3))
g3b = NepGoogle([ev("c8", "Mehdi: [EL-IN] overleg")], botsing_keer={"c8": 1})
r3b, niet3b, _, _ = met(g3b, W.firma_gasten, list(g3b.items.values()), "tok")
check("na een enkele 412 leest de agent opnieuw en zet hij de gast alsnog", len(g3b.patches) == 1 and not niet3b, str(r3b))

g7 = NepGoogle([ev("d1", "Mehdi: [EL-IN] overleg", gasten=[{"email": W.WERKAGENDA}])], ander_uur=True)
_, niet7, _, _ = met(g7, W.firma_gasten, list(g7.items.values()), "tok")
check("staat alleen een andere keer van dezelfde reeks op de werkagenda, dan telt deze keer als niet zichtbaar",
      len(niet7) == 1, str(niet7))
g8 = NepGoogle([ev("e1", "Mehdi: [EL-IN] overleg")], vers={"e1": {"summary": "Siyan: [EL-IN] overleg"}})
r8, _, _, _ = met(g8, W.firma_gasten, list(g8.items.values()), "tok")
check("veranderde de collega de titel intussen naar zichzelf, dan wordt Mehdi niet toegevoegd",
      not g8.patches and any("niet meer voor Mehdi" in r for r in r8), str((g8.patches, r8)))
g8b = NepGoogle([ev("e2", "Mehdi: [EL-IN] overleg")], vers={"e2": {"status": "cancelled"}})
met(g8b, W.firma_gasten, list(g8b.items.values()), "tok")
check("een intussen geschrapte afspraak krijgt geen gast", not g8b.patches)
check("een bestaande vraag wordt ook op een volgende zoekpagina gevonden",
      met(NepGoogle([], bestaande_vraag="pagina2"), W._prive_vraag_id, "firma|x", "tok") == "v")
check("een opgeloste vraag houdt een nieuwe vraag niet tegen (Codex-hertest 3, punt 13)",
      met(NepGoogle([], bestaande_vraag="opgelost"), W._prive_vraag_id, "firma|x", "tok") == "")

_moeder = {"id": "reeks1", "summary": "Mehdi: [EL-IN] wekelijkse meeting", "etag": '"e-reeks1"', "attendees": [],
           "kalender": ELEVAIT, "_moeder": True}
_inst = [ev(f"reeks1_2026110{i}", "Mehdi: [EL-IN] wekelijkse meeting", reeks="reeks1") for i in (2, 3)]
g4 = NepGoogle([_moeder] + _inst)
met(g4, W.firma_gasten, _inst, "tok")
check("een reeks: alleen de keren in het leesvenster krijgen de gast, nooit de moederreeks (Codex-hertest 3, punt 11)",
      sorted(u.split("/events/")[1].split("?")[0] for u, _, _ in g4.patches) == ["reeks1_20261102", "reeks1_20261103"],
      str([u for u, _, _ in g4.patches]))

g5 = NepGoogle([ev("p1", "x"), ev("p2", "y"), ev("p3", "z")])
_pag, _onl = met(g5, W.firma_afspraken, "tok")
check("de firma-agenda's worden over alle pagina's gelezen", not _onl and len([e for e in _pag if e["kalender"] == ELEVAIT]) == 3,
      str((len(_pag), _onl)))
_pag2, _onl2 = met(NepGoogle([ev("p1", "x")], onleesbaar={"hdssuriname@gmail.com"}), W.firma_afspraken, "tok")
check("een onleesbare firma-agenda stopt de andere niet: Elevait gelezen, HDS gemeld (Codex-hertest 3, punt 17)",
      len(_pag2) == 1 and _onl2 == ["hdssuriname@gmail.com"], str((len(_pag2), _onl2)))
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
      len(_sterk) == 1 and _sterk[0]["transparency"] == "opaque" and _sterk[0]["start"]["dateTime"].endswith("10:00:00+01:00"))

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


_, niet7b, _, _ = met(_Nep7([_e7]), W.firma_gasten, [_e7], "tok")
check("twee verplaatste keren op hetzelfde uur: de oorspronkelijke tijd beslist (niet zichtbaar)", len(niet7b) == 1)
_moeder2 = {"id": "reeks2", "summary": "Mehdi: [EL-IN] meeting", "etag": '"e-reeks2"', "attendees": [], "kalender": ELEVAIT,
            "_moeder": True}
_gem = [ev("reeks2_20261102", "Mehdi: [EL-IN] meeting", reeks="reeks2"), ev("reeks2_20261109", "Siyan: [EL-IN] meeting", reeks="reeks2")]
g11 = NepGoogle([_moeder2] + _gem)
met(g11, W.firma_gasten, _gem, "tok")
check("een gemengde reeks (een keer voor een collega): alleen de keer voor Mehdi krijgt de gast, niet de hele reeks",
      [u.split("/events/")[1].split("?")[0] for u, _, _ in g11.patches] == ["reeks2_20261102"], str([u for u, _, _ in g11.patches]))
_HA = "73e8b6359d04b7bdb02aa045e668cd6f9d9f007bec51ce370494e7de7501f0c4@group.calendar.google.com"
check("H-Architects en UNABO blijven zichtbaar en worden niet gescand: de agent zet daar zelf ritten (overleg P1)",
      _HA not in {a for a, _ in W.firma_meelezen()} and not hasattr(W, "firma_scan"))
check("een verborgen agenda waarop de agent ritten zet, wordt gemeld; Elevait verborgen niet (Codex-hertest 3, punt 12)",
      W.verborgen_schrijfagendas({**{k: True for k in W.KALENDERS}, _HA: False, ELEVAIT: False}) == ["H-Architects"]
      and "H-Architects" in W.verborgen_schrijfagendas({}))     # niet in de lijst: evenmin te zien
# --- Codex-hertest 3: het blok volgt zijn afspraak, hele dag, gastafspraken, onleesbare agenda, ook in het weekend ----
_ins13, _opg13, _pat13, _open13 = [], [], [], {"q1": True}
_o13 = (W._insert, W.FIRMA_VRAGEN, W._prive_item_lezen, W._eigen_melding_opgelost, W._patch)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma13-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins13.append(body) or {"id": f"q{len(_ins13)}"}
W._prive_item_lezen = lambda eid, tok: {"id": eid, "titel": "VR Agendawacht: x", "_merk": {
    W.FIRMAMERK: f"firma|g1@google.com|", W.MAILMERK: "abcdef0123456789" if _open13.get(eid, True) else "opgelost:abcdef0123456789"}}
W._eigen_melding_opgelost = lambda x, k, tok, nu, reden="", vrij=False: _opg13.append((x["id"], vrij)) or True
W._patch = lambda x, body, tok, **kw: _pat13.append((x["id"], body))
try:
    _g1 = ev("g1", "Overleg KDS", beschrijving="Mehdi beslist mee")
    met(NepGoogle([_g1]), W.firma_vangnet, [_g1], [], "tok")
    _dag2 = (_nu + timedelta(days=2)).date().isoformat()
    _g1b = dict(_g1, start={"dateTime": f"{_dag2}T10:00:00+01:00"}, end={"dateTime": f"{_dag2}T11:00:00+01:00"})
    met(NepGoogle([_g1b]), W.firma_vangnet, [_g1b], [], "tok")
    _schuif, _n_schuif = list(_pat13), len(_ins13)
    _g1c = dict(_g1b, end={"dateTime": f"{_dag2}T12:00:00+01:00"})     # zelfde begin, later einde
    met(NepGoogle([_g1c]), W.firma_vangnet, [_g1c], [_g1c], "tok")     # en nu een afspraak voor Mehdi die niet doorkomt
    _einde = list(_pat13[len(_schuif):])
    _r_onl = met(NepGoogle([]), W.firma_vangnet, [], [], "tok", None, [ELEVAIT])
    _na_onl = (list(_opg13), json.loads(Path(W.FIRMA_VRAGEN).read_text(encoding="utf-8")))
    met(NepGoogle([]), W.firma_vangnet, [], [], "tok")
    _opg_weg = list(_opg13)
    _open13["q1"] = False                                              # de vraag is opgelost; de afspraak komt terug
    met(NepGoogle([_g1]), W.firma_vangnet, [_g1], [], "tok")
finally:
    W._insert, W.FIRMA_VRAGEN, W._prive_item_lezen, W._eigen_melding_opgelost, W._patch = _o13
check("verschuift de afspraak, dan schuift hetzelfde blok mee (geen tweede vraag, oude dag niet bezet; punt 13)",
      len(_schuif) == 1 and _schuif[0][0] == "q1" and _schuif[0][1]["start"] == {"date": _dag2, "dateTime": None}
      and _n_schuif == 1, str((_schuif, _n_schuif)))
check("verandert alleen het einde, of wordt het een afspraak voor Mehdi, dan wordt het blok ook bijgewerkt (Bezet, op het uur)",
      len(_einde) == 1 and _einde[0][1]["end"] == {"dateTime": f"{_dag2}T12:00:00+01:00", "date": None}
      and _einde[0][1]["transparency"] == "opaque", str(_einde))
check("van een onleesbare agenda wordt niets afgerond en blijft het register staan (punt 17)",
      _na_onl[0] == [] and f"firma|g1@google.com|" in _na_onl[1], str(_na_onl))
check("verdwijnt de afspraak, dan 'Opgelost' en Beschikbaar: het oude uur blijft niet bezet (punt 13)",
      _opg_weg == [("q1", True)], str(_opg_weg))
check("komt de afspraak terug na een opgeloste vraag, dan komt er een nieuwe vraag", len(_ins13) == 2, str(len(_ins13)))

_dag3 = (_nu + timedelta(days=3)).date().isoformat()
_dag5 = (_nu + timedelta(days=5)).date().isoformat()
_heel = dict(ev("h1", "Mehdi: [EL-IN] Suriname reis"), start={"date": _dag3}, end={"date": _dag5})
_hb = W._firma_vraag_body(f"firma|h1@google.com|", _heel, _dag3, True)
check("een hele-dag-afspraak voor Mehdi die niet doorkomt: een Bezet blok over dezelfde dagen (punt 10)",
      _hb["start"] == {"date": _dag3} and _hb["end"] == {"date": _dag5} and _hb["transparency"] == "opaque", str(_hb))
check("dat blok sluit geen dag af voor de agent (geen markering)",
      not W.markeringen_uit([{"titel": _hb["summary"], "start": _dag3, "einde": _dag5, "hele_dag": True}], _dag3))

_gast = [ev("k1", "SAIS26 | Panel", gasten=[{"email": W.WERKAGENDA, "responseStatus": "accepted"}]),
         ev("k2", "SAIS26 | Diner", gasten=[{"email": W.WERKAGENDA, "responseStatus": "declined"}])]
g14 = NepGoogle(_gast, zichtbaar=False)
_, niet14, _, _ = met(g14, W.firma_gasten, _gast, "tok")
check("Mehdi als gast zonder zijn naam vooraan, niet zichtbaar (verborgen uitnodiging): naar het vangnet (punt 14)",
      [e["id"] for e in niet14] == ["k1"] and not g14.patches, str([e["id"] for e in niet14]))

# --- Codex-hertest 4: de teruggelezen tijd beslist; een meerdaagse afspraak blijft gevolgd tot ze voorbij is -------
class _Nep15(NepGoogle):
    """Een collega verzet de reeks van 10:00 naar 14:00 terwijl de agent de gast zet: de PATCH geeft het nieuwe uur."""

    def __call__(self, req, timeout=None, *a, **k):
        if (req.get_method() if hasattr(req, "get_method") else "GET") == "PATCH":
            r = json.loads(super().__call__(req, timeout, *a, **k).read())
            r["start"], r["end"] = {"dateTime": f"{_morgen}T14:00:00+01:00"}, {"dateTime": f"{_morgen}T15:00:00+01:00"}
            return io.BytesIO(json.dumps(r).encode())
        url = getattr(req, "full_url", req)
        if "iCalUID" in url:
            self.gezocht = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["timeMin"][0]
            return io.BytesIO(json.dumps({"items": []}).encode())
        return super().__call__(req, timeout, *a, **k)


_e15 = ev("m1_20261102", "Mehdi: [EL-IN] meeting", reeks="m1")
g15 = _Nep15([_e15])
_, niet15, onz15, _ = met(g15, W.firma_gasten, [_e15], "tok")
check("verzet een collega het uur terwijl de gast gezet wordt, dan geldt het nieuwe uur en komt er geen blok op het oude",
      not niet15 and onz15 == {f"firma|m1_20261102@google.com|"} and "13:59" in getattr(g15, "gezocht", ""),
      str((niet15, onz15, getattr(g15, "gezocht", ""))))

_gist = (_nu - timedelta(days=1)).date().isoformat()
_overmorgen = (_nu + timedelta(days=2)).date().isoformat()
_opg16, _ins16 = [], []
_o16 = (W._insert, W.FIRMA_VRAGEN, W._prive_item_lezen, W._eigen_melding_opgelost)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma16-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins16.append(body) or {"id": "r1"}
W._prive_item_lezen = lambda eid, tok: {"id": eid, "titel": "VR Agendawacht: x", "_merk": {
    W.FIRMAMERK: f"firma|n1@google.com|", W.MAILMERK: "abcdef0123456789"}}
W._eigen_melding_opgelost = lambda x, k, tok, nu, reden="", vrij=False: _opg16.append((x["id"], vrij)) or True
try:
    _n1 = dict(ev("n1", "Mehdi: [EL-IN] beurs"), start={"date": _gist}, end={"date": _overmorgen})
    met(NepGoogle([_n1]), W.firma_vangnet, [_n1], [_n1], "tok")          # begon gisteren, loopt nog
    met(NepGoogle([]), W.firma_vangnet, [], [], "tok")                   # en verdwijnt vandaag
finally:
    W._insert, W.FIRMA_VRAGEN, W._prive_item_lezen, W._eigen_melding_opgelost = _o16
check("een meerdaagse afspraak die gisteren begon en nog loopt, krijgt haar Bezet blok", len(_ins16) == 1, str(len(_ins16)))
check("verdwijnt ze voor haar einde, dan Opgelost en Beschikbaar, ook al is de begindag voorbij (punt 2)",
      _opg16 == [("r1", True)], str(_opg16))

# --- Codex-hertest 5: na een fout alleen de actuele afspraak; een later verzette afspraak neemt haar blok meteen mee --
_e17 = ev("s1_20261102T090000Z", "Mehdi: [EL-IN] meeting", reeks="s1")
r17, niet17, onz17, opn17 = met(NepGoogle([_e17], weg={"s1_20261102T090000Z"}), W.firma_gasten, [_e17], "tok")
check("verdwijnt een reekskeer tijdens de controle (reeks verzet), dan geen blok op het oude uur en de agenda opnieuw lezen",
      not niet17 and opn17 and not onz17, str((r17, niet17, onz17, opn17)))


class _NepOnleesbaarGet(NepGoogle):
    def __call__(self, req, timeout=None, *a, **k):
        url = getattr(req, "full_url", req)
        if "/events/" in url and "iCalUID" not in url:
            raise OSError("netwerk weg")
        return super().__call__(req, timeout, *a, **k)


_e18 = ev("s2", "Mehdi: [EL-IN] meeting")
_, niet18, onz18, _ = met(_NepOnleesbaarGet([_e18]), W.firma_gasten, [_e18], "tok")
check("is de afspraak daarna niet te lezen, dan geen blok op een oude tijd; het vangnet laat haar staan (onzeker)",
      not niet18 and onz18 == {f"firma|s2@google.com|"}, str((niet18, onz18)))

_volg = []
_o19 = (W.firma_afspraken, W.firma_gasten, W.firma_vangnet, W.agenda.zichtbaarheid, W.agenda._toegang, W.FIRMA_SLOT)
_lees19 = [([_e17], []), ([dict(_e17, id="s1_20261102T130000Z")], [])]
W.firma_afspraken = lambda tok, *a, **k: _lees19.pop(0)
W.firma_gasten = lambda evs, tok, onleesbaar=(): ([], [], set(), evs[0]["id"].endswith("090000Z"))
W.firma_vangnet = lambda evs, niet, tok, **k: _volg.append([e["id"] for e in evs]) or []
W.agenda.zichtbaarheid = lambda: {k: True for k in W.KALENDERS}
W.agenda._toegang = lambda: "tok"
W.FIRMA_SLOT = str(Path(tempfile.mkdtemp(prefix="firmaslot19-")) / "agenda-firma.lock")
try:
    W.firma_stap("2026-10-27")
finally:
    W.firma_afspraken, W.firma_gasten, W.firma_vangnet, W.agenda.zichtbaarheid, W.agenda._toegang, W.FIRMA_SLOT = _o19
check("na een verdwenen keer leest de firmastap de agenda opnieuw en krijgt het vangnet de nieuwe keren",
      _volg == [["s1_20261102T130000Z"]], str(_volg))

from datetime import datetime as _dt, timezone as _tz  # noqa: E402
_tz1 = _tz(timedelta(hours=1))
_n20 = _dt(_nu.year, _nu.month, _nu.day, 11, 17, tzinfo=_tz1)
_d20 = _n20.date().isoformat()
_pat20, _ins20 = [], []
_o20 = (W._insert, W.FIRMA_VRAGEN, W._prive_item_lezen, W._patch)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma20-")) / "agenda-firma-vragen.json")
Path(W.FIRMA_VRAGEN).write_text(json.dumps({f"firma|t1@google.com|": {
    "gevraagd": _d20, "dag": _d20, "start": f"{_d20}T10:00:00+01:00", "einde": f"{_d20}T11:00:00+01:00", "sterk": True,
    "id": "q9"}}), encoding="utf-8")
W._insert = lambda kal, body, tok, toch=False: _ins20.append(body) or {"id": "nieuw"}
W._prive_item_lezen = lambda eid, tok: {"id": eid, "titel": "VR Agendawacht: x", "_merk": {
    W.FIRMAMERK: f"firma|{'t1' if eid == 'q9' else 't2'}@google.com|", W.MAILMERK: "abcdef0123456789"}}
W._patch = lambda x, body, tok, **kw: _pat20.append((x["id"], body))
try:
    _t1 = dict(ev("t1", "Mehdi: [EL-IN] overleg"), start={"dateTime": f"{_d20}T14:00:00+01:00"},
               end={"dateTime": f"{_d20}T15:00:00+01:00"})
    met(NepGoogle([_t1]), W.firma_vangnet, [_t1], [_t1], "tok", _n20)
    _reg20 = json.loads(Path(W.FIRMA_VRAGEN).read_text(encoding="utf-8"))
    _t2 = dict(_t1, id="t2", iCalUID="t2@google.com")
    met(NepGoogle([_t2], bestaande_vraag=True), W.firma_vangnet, [_t2], [_t2], "tok", _n20)
finally:
    W._insert, W.FIRMA_VRAGEN, W._prive_item_lezen, W._patch = _o20
check("verzet naar later nadat het oude uur voorbij is: hetzelfde blok gaat meteen naar het nieuwe uur (hertest 5, punt 2)",
      _pat20[:1] and _pat20[0][0] == "q9" and _pat20[0][1]["start"]["dateTime"] == f"{_d20}T14:00:00+01:00" and not _ins20
      and _reg20[f"firma|t1@google.com|"]["start"] == f"{_d20}T14:00:00+01:00", str((_pat20, _ins20)))
check("staat de vraag er al zonder registratie, dan wordt ze meteen op de juiste tijd gezet, geen tweede",
      len(_pat20) == 2 and _pat20[1][0] == "v" and not _ins20, str(_pat20))

# --- review met meerdere agents (27-10-2026) -----------------------------------------------------------------------
check("een einde dat voorbij is: een hele dag telt exclusief, leeg telt niet als voorbij",
      W._einde_voorbij(_nu.date().isoformat(), _nu) and not W._einde_voorbij("", _nu)
      and not W._einde_voorbij((_nu + timedelta(days=1)).date().isoformat(), _nu))
_namen = [r for r in (HIER / "agenda_wacht.py").read_text(encoding="utf-8").splitlines() if r.startswith("def ")]
check("geen functienaam staat twee keer in agenda_wacht.py (een latere definitie overschrijft stil de eerste)",
      len({r.split("(")[0] for r in _namen}) == len(_namen),
      str(sorted({r.split("(")[0] for r in _namen if sum(1 for q in _namen if q.split("(")[0] == r.split("(")[0]) > 1})))


class _NepSchrijf:
    """Echte _insert en _patch, met nagemaakte Google: telt POST en PATCH naar de privé-agenda."""

    def __init__(self):
        self.post, self.patch = [], []

    def __call__(self, req, timeout=None, *a, **k):
        m = req.get_method() if hasattr(req, "get_method") else "GET"
        if m == "POST":
            self.post.append(json.loads(req.data))
            return io.BytesIO(json.dumps({"id": "b1"}).encode())
        if m == "PATCH":
            self.patch.append(json.loads(req.data))
            return io.BytesIO(b"{}")
        return io.BytesIO(json.dumps({"items": []}).encode())     # geen bestaande vraag met dit merk


_dagm = (_nu + timedelta(days=4)).date().isoformat()
_o21 = (W.FIRMA_VRAGEN, W._prive_item_lezen, W.gearchiveerd, dict(W._MARKERS))
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma21-")) / "agenda-firma-vragen.json")
W.gearchiveerd = lambda: set()
W._MARKERS[_dagm] = [("Buitenland (Suriname)", "alles")]
W._prive_item_lezen = lambda eid, tok: {"id": eid, "kalender": W.PRIVE_AGENDA, "titel": "VR Agendawacht: x", "deelnemers": [],
                                        "_agendagasten": [], "maker": W.WERKAGENDA, "start": f"{_dagm}T10:00:00+01:00",
                                        "hele_dag": False, "_merk": {W.FIRMAMERK: f"firma|u1@google.com|",
                                                                     W.MAILMERK: "abcdef0123456789"}}
_ns = _NepSchrijf()
try:
    _u1 = dict(ev("u1", "Mehdi: [EL-IN] overleg minister"), start={"dateTime": f"{_dagm}T10:00:00+01:00"},
               end={"dateTime": f"{_dagm}T11:00:00+01:00"})
    _r21 = met(_ns, W.firma_vangnet, [_u1], [_u1], "tok")
    _u1b = dict(_u1, start={"dateTime": f"{_dagm}T15:00:00+01:00"}, end={"dateTime": f"{_dagm}T16:00:00+01:00"})
    _r21b = met(_ns, W.firma_vangnet, [_u1b], [_u1b], "tok")
    _r21c = met(_ns, W.firma_vangnet, [], [], "tok")
finally:
    W.FIRMA_VRAGEN, W._prive_item_lezen, W.gearchiveerd = _o21[:3]
    W._MARKERS.clear()
    W._MARKERS.update(_o21[3])
check("op een dag met 'Buitenland' krijgt een verborgen firma-afspraak voor Mehdi toch haar Bezet blok (geen ja-stempel)",
      len(_ns.post) == 1 and _ns.post[0]["start"]["dateTime"].endswith("10:00:00+01:00")
      and W.JA_MERK not in json.dumps(_ns.post[0]), str((_r21, _ns.post)))
check("en het blok volgt zijn afspraak naar een ander uur op zo'n dag",
      _ns.patch[:1] and _ns.patch[0]["start"]["dateTime"].endswith("15:00:00+01:00"), str((_r21b, _ns.patch[:1])))
check("verdwijnt ze, dan wordt het opgeloste blok een hele-dag-item (geen oproep, geen botsing meer)",
      any(b.get("start", {}).get("date") == _dagm and b["start"].get("dateTime", "x") is None for b in _ns.patch[1:])
      and any(b.get("transparency") == "transparent" for b in _ns.patch[1:]), str((_r21c, _ns.patch[1:])))


class _NepWerkStuk(NepGoogle):
    def __call__(self, req, timeout=None, *a, **k):
        if "iCalUID" in getattr(req, "full_url", req):
            raise urllib.error.HTTPError(req.full_url, 503, "Unavailable", {}, None)
        return super().__call__(req, timeout, *a, **k)


_w = [ev(f"w{i}", "Mehdi, Siyan: [EL-IN] Wekelijkse", gasten=[{"email": W.WERKAGENDA, "responseStatus": "accepted"}])
      for i in (1, 2)]
_, niet22, onz22, _ = met(_NepWerkStuk(_w), W.firma_gasten, _w, "tok")
check("is de werkagenda even niet te lezen, dan geen blokken voor afspraken die er al op staan (onzeker)",
      not niet22 and onz22 == {f"firma|w1@google.com|", f"firma|w2@google.com|"}, str((niet22, onz22)))

_d1 = ev("x1", "Mehdi: [EL-PO] overleg HDS en Elevait", gasten=[{"email": W.WERKAGENDA, "responseStatus": "needsAction"}])
_d2 = dict(_d1, kalender="hdssuriname@gmail.com", _agendanaam="High Design Studio NV")
_, niet23, _, _ = met(NepGoogle([_d1], zichtbaar=False), W.firma_gasten, [_d1, _d2], "tok")
_ins23 = []
_o23 = (W._insert, W.FIRMA_VRAGEN)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma23-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins23.append(body) or {"id": "y"}
try:
    met(NepGoogle([]), W.firma_vangnet, [_d1, _d2], [_d1, _d2], "tok")
finally:
    W._insert, W.FIRMA_VRAGEN = _o23
check("dezelfde afspraak op twee firma-agenda's (de ene nodigt de andere uit): een keer nagekeken en een blok",
      len(niet23) == 1 and len(_ins23) == 1, str((len(niet23), len(_ins23))))
_o_uids, W._FIRMA_UIDS = W._FIRMA_UIDS, set()
_kop_ok = W._firma_kopie({"_organisator": ELEVAIT}) and not W._firma_kopie({"_organisator": "klant@voorbeeld.test"})
W._FIRMA_UIDS = _o_uids
check("op de werkagenda-kopie van een firma-afspraak zet de agent geen telefoonnummer",
      _kop_ok
      and "_firma_kopie(a)" in (HIER / "agenda_wacht.py").read_text(encoding="utf-8").split("def contact_zetten")[1][:1500])

# --- Codex-hertest 6: nergens schrijven op de gastkopie van een firma-afspraak; vlak voor een blok opnieuw lezen ---
import ast  # noqa: E402
_boom = ast.parse((HIER / "agenda_wacht.py").read_text(encoding="utf-8"))
_routes = []
for _f in [n for n in _boom.body if isinstance(n, ast.FunctionDef)]:
    _src = ast.get_source_segment((HIER / "agenda_wacht.py").read_text(encoding="utf-8"), _f) or ""
    if "for a in items:" in _src and ("_patch(a," in _src or "_vertrekmelding_zetten(a," in _src):
        _routes.append((_f.name, "_firma_kopie(a)" in _src))
check("elke schrijfroute die over de agenda-items loopt, slaat de gastkopie van een firma-afspraak over",
      len(_routes) >= 12 and all(g for _, g in _routes), str([n for n, g in _routes if not g]))
_kopie = {"kalender": W.WERKAGENDA, "id": "elev1", "titel": "Mehdi, Siyan: [EL-IN] Wekelijkse", "_organisator": ELEVAIT,
          "start": f"{_morgen}T10:00:00+01:00", "einde": f"{_morgen}T11:00:00+01:00", "hele_dag": False, "deelnemers": [],
          "_agendagasten": [], "maker": "siyan@voorbeeld.test", "_reminders": {"useDefault": True}, "omschrijving": "",
          "_kleur": "1", "_merk": {}}
_pat24 = []
_o24 = (W._patch, W.agenda._toegang, W.gearchiveerd)
W._patch = lambda a, body, tok, **kw: _pat24.append((a.get("id"), body))
W.agenda._toegang = lambda: "tok"
W.gearchiveerd = lambda: set()
try:
    W.herinneringen_zetten([dict(_kopie)])
    W.kleuren_zetten([dict(_kopie)])
finally:
    W._patch, W.agenda._toegang, W.gearchiveerd = _o24
check("herinneringen en kleuren laten de gastkopie van een firma-afspraak ongemoeid (geen standaardherinnering weg)",
      not _pat24, str(_pat24))
_o25 = W.gearchiveerd
W.gearchiveerd = lambda: set()
try:
    W._patch(dict(_kopie), {"colorId": "5"}, "tok")
    _grendel = False
except W.SchaduwItem:
    _grendel = True
finally:
    W.gearchiveerd = _o25
check("en _patch zelf weigert elke schrijfactie op zo'n kopie (grendel)", _grendel)

_e26 = ev("z1", "Mehdi: [EL-IN] overleg", gasten=[{"email": W.WERKAGENDA, "responseStatus": "accepted"}])
g26 = NepGoogle([_e26], zichtbaar=False, vers={"z1": {"start": {"dateTime": f"{_morgen}T14:00:00+01:00"},
                                                       "end": {"dateTime": f"{_morgen}T15:00:00+01:00"}}})
_, niet26, _, _ = met(g26, W.firma_gasten, [_e26], "tok")
check("is Mehdi al gast en is de afspraak intussen verzet, dan krijgt het vangnet de actuele tijd (hertest 6, punt 2)",
      len(niet26) == 1 and niet26[0]["start"]["dateTime"].endswith("14:00:00+01:00"), str(niet26))

# --- Codex-hertest 7: een kopie met een collega als organisator is ook een firmakopie --------------------------------
_o27 = W._FIRMA_UIDS
try:
    W._FIRMA_UIDS = {"siyan-afspraak@google.com"}
    _k27 = {"_organisator": "siyan@voorbeeld.test", "_organisator_zelf": False, "_ical": "siyan-afspraak@google.com"}
    check("een kopie van een firma-afspraak met een collega als organisator wordt herkend (zelfde iCalUID)",
          W._firma_kopie(_k27))
    check("een uitnodiging van een klant, niet op een firma-agenda, blijft gewoon van Mehdi",
          not W._firma_kopie(dict(_k27, _ical="klant@google.com")))
    check("een eigen afspraak van Mehdi met een firma-agenda als gast blijft van hem",
          not W._firma_kopie(dict(_k27, _organisator_zelf=True, _organisator=W.WERKAGENDA)))
    W._FIRMA_UIDS = False
    check("is een firma-agenda niet te lezen, dan telt elke afspraak die Mehdi niet organiseerde als kopie (geen schrijven)",
          W._firma_kopie(dict(_k27, _ical="klant@google.com")))
finally:
    W._FIRMA_UIDS = _o27

# --- Codex-hertest 8: de UID-lezing dekt het hele rittenvenster, ook het grensuur --------------------------------
_venster = []
_o28 = (W.firma_afspraken, W._FIRMA_UIDS, W.agenda._toegang)
W.firma_afspraken = lambda tok, nu=None, dagen=W.FIRMA_VOORUIT_DAGEN: _venster.append((nu, dagen)) or ([], [])
W._FIRMA_UIDS = None
W.agenda._toegang = lambda: "tok"
try:
    W._firma_uids()
finally:
    W.firma_afspraken, W._FIRMA_UIDS, W.agenda._toegang = _o28
_eind = _venster[0][0] + timedelta(days=_venster[0][1]) if _venster else None
check("de iCalUID-lezing loopt tot voorbij het rittenvenster (365 dagen vanaf nu), ook het laatste uur",
      _eind is not None and _eind >= W.nu_lokaal() + timedelta(days=366), str(_venster))

# --- Codex-hertest 9: dezelfde afspraak op twee firma-agenda's, een ervan onleesbaar: een blok, dat meeschuift --------
_pat29, _ins29 = [], []
_o29 = (W._insert, W.FIRMA_VRAGEN, W._prive_item_lezen, W._patch)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma29-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins29.append(body) or {"id": "b29"}
W._prive_item_lezen = lambda eid, tok: {"id": eid, "titel": "VR Agendawacht: x", "_merk": {
    W.FIRMAMERK: "firma|dup1@google.com|", W.MAILMERK: "abcdef0123456789"}}
W._patch = lambda x, body, tok, **kw: _pat29.append((x["id"], body))
try:
    _hds = dict(ev("dup1", "Mehdi: [EL-PO] overleg"), kalender="hdssuriname@gmail.com", _agendanaam="High Design Studio NV")
    _org = ev("dup1", "Mehdi: [EL-PO] overleg")                                       # de kopie van de organisator
    met(NepGoogle([]), W.firma_vangnet, [_hds, _org], [_org], "tok")
    _el = dict(ev("dup1", "Mehdi: [EL-PO] overleg"), start={"dateTime": f"{_morgen}T14:00:00+01:00"},
               end={"dateTime": f"{_morgen}T15:00:00+01:00"})
    met(NepGoogle([]), W.firma_vangnet, [_el], [_el], "tok", None, ["hdssuriname@gmail.com"])   # HDS onleesbaar, verzet
finally:
    W._insert, W.FIRMA_VRAGEN, W._prive_item_lezen, W._patch = _o29
check("dezelfde afspraak op twee firma-agenda's, de ene onleesbaar en de afspraak verzet: een blok, dat meeschuift",
      len(_ins29) == 1 and len(_pat29) == 1 and _pat29[0][1]["start"]["dateTime"].endswith("14:00:00+01:00"),
      str((len(_ins29), _pat29)))

# --- Codex-hertest 10: een leesbare kopie beslist; kopieën met een ander Google-id zijn dezelfde afspraak ----------
_opg30, _ins30 = [], []
_o30 = (W._insert, W.FIRMA_VRAGEN, W._prive_item_lezen, W._eigen_melding_opgelost, W._patch)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma30-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins30.append(body) or {"id": "b30"}
W._prive_item_lezen = lambda eid, tok: {"id": eid, "titel": "VR Agendawacht: x", "hele_dag": True, "start": _morgen,
                                        "_merk": {W.FIRMAMERK: "firma|gedeeld@google.com|", W.MAILMERK: "abcdef0123456789"}}
W._eigen_melding_opgelost = lambda x, k, tok, nu, reden="", vrij=False: _opg30.append(x["id"]) or True
W._patch = lambda x, body, tok, **kw: None
try:
    _a = dict(ev("idA", "Mehdi: [EL-PO] overleg"), iCalUID="gedeeld@google.com", kalender="hdssuriname@gmail.com")
    _b = dict(ev("idB", "Mehdi: [EL-PO] overleg"), iCalUID="gedeeld@google.com")       # Elevait, ander Google-id
    met(NepGoogle([]), W.firma_vangnet, [_a, _b], [_a, _b], "tok")
    _n30 = len(_ins30)
    # HDS (waar het blok vandaan kwam) is onleesbaar; de Elevait-kopie staat nu zichtbaar op de werkagenda
    met(NepGoogle([]), W.firma_vangnet, [_b], [], "tok", None, ["hdssuriname@gmail.com"])
finally:
    W._insert, W.FIRMA_VRAGEN, W._prive_item_lezen, W._eigen_melding_opgelost, W._patch = _o30
check("kopieën van dezelfde afspraak met een ander Google-id geven een blok (iCalUID beslist)", _n30 == 1, str(_n30))
check("is de agenda van het blok onleesbaar maar staat een leesbare kopie nu zichtbaar, dan Opgelost en Beschikbaar",
      _opg30 == ["b30"], str(_opg30))
check("de sleutel is dezelfde in Suriname- en Brusselse tijd (oorspronkelijke tijd in UTC)",
      W._firma_sleutel({"iCalUID": "r@google.com", "originalStartTime": {"dateTime": "2026-11-02T06:00:00-03:00"}})
      == W._firma_sleutel({"iCalUID": "r@google.com", "originalStartTime": {"dateTime": "2026-11-02T10:00:00+01:00"}}))

# --- Codex-hertest 11: kopieën met een ander uur: de organisator beslist, anders onzeker -------------------------------
_c1 = dict(ev("o1", "Mehdi: [EL-PO] overleg"), iCalUID="tw@google.com", kalender="hdssuriname@gmail.com",
           organizer={"email": ELEVAIT})
_c2 = dict(ev("o2", "Mehdi: [EL-PO] overleg"), iCalUID="tw@google.com", organizer={"email": ELEVAIT},
           start={"dateTime": f"{_morgen}T14:00:00+01:00"}, end={"dateTime": f"{_morgen}T15:00:00+01:00"})
_gk, _onz, _ = W._firma_kopieen_kiezen([_c1, _c2])
check("verschillen twee kopieën in tijd, dan beslist de kopie op de agenda van de organisator",
      [e["id"] for e in _gk] == ["o2"] and not _onz, str(([e["id"] for e in _gk], _onz)))
_gk2, _onz2, _tw2 = W._firma_kopieen_kiezen([_c1, dict(_c2, organizer={"email": "siyan@voorbeeld.test"})])
check("zonder kopie van de organisator geen keuze: alleen een vraag dat het uur niet zeker is (twijfel)",
      not _gk2 and not _onz2 and set(_tw2) == {W._firma_sleutel(_c1)}, str((_gk2, _onz2, _tw2)))
_, niet31, onz31, _ = met(NepGoogle([], zichtbaar=False), W.firma_gasten,
                          [_c1, dict(_c2, organizer={"email": "siyan@voorbeeld.test"},
                                     attendees=[{"email": W.WERKAGENDA, "responseStatus": "accepted"}])], "tok")
check("en firma_gasten geeft ze als onzeker door, zonder blok", not niet31 and W._firma_sleutel(_c1) in onz31, str((niet31, onz31)))

# --- Codex-hertest 12: is de agenda van de organisator onleesbaar, dan beslist een gastkopie niet ------------------
_g1k = dict(ev("p9", "Mehdi: [EL-PO] overleg"), kalender="hdssuriname@gmail.com", organizer={"email": ELEVAIT})
_gk3, _onz3, _ = W._firma_kopieen_kiezen([_g1k], [ELEVAIT])
check("een gastkopie alleen, terwijl de firma-agenda van de organisator onleesbaar is: onzeker (geen blok, niets verzet)",
      not _gk3 and _onz3 == {W._firma_sleutel(_g1k)}, str((_gk3, _onz3)))
_gk4, _onz4, _tw4 = W._firma_kopieen_kiezen([_g1k], [])
check("een gastkopie alleen (de kopie van de organisator ontbreekt): geen keuze, alleen een twijfelvraag (hertest 13)",
      not _gk4 and not _onz4 and len(_tw4) == 1)
_opg32 = []
_o32 = (W.FIRMA_VRAGEN, W._prive_item_lezen, W._eigen_melding_opgelost, W._patch, W._insert)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma32-")) / "agenda-firma-vragen.json")
Path(W.FIRMA_VRAGEN).write_text(json.dumps({W._firma_sleutel(_g1k): {
    "gevraagd": _morgen, "dag": _morgen, "start": f"{_morgen}T08:00:00+01:00", "einde": f"{_morgen}T09:00:00+01:00",
    "sterk": True, "id": "q32", "kalender": ELEVAIT}}), encoding="utf-8")
_pat32 = []
W._prive_item_lezen = lambda eid, tok: {"id": eid, "titel": "VR Agendawacht: x", "_merk": {
    W.FIRMAMERK: W._firma_sleutel(_g1k), W.MAILMERK: "abcdef0123456789"}}
W._eigen_melding_opgelost = lambda x, k, tok, nu, reden="", vrij=False: _opg32.append(x["id"]) or True
W._patch = lambda x, body, tok, **kw: _pat32.append(body)
W._insert = lambda kal, body, tok, toch=False: _pat32.append(body) or {"id": "nee"}
try:
    met(NepGoogle([]), W.firma_vangnet, [_g1k], [_g1k], "tok", None, [ELEVAIT])
finally:
    W.FIRMA_VRAGEN, W._prive_item_lezen, W._eigen_melding_opgelost, W._patch, W._insert = _o32
check("en het vangnet verzet of rondt het bestaande blok dan niet af", not _pat32 and not _opg32, str((_pat32, _opg32)))

# --- Codex-hertest 13: alleen gastkopieën: een zichtbare vraag, nooit een blok op een onzeker uur ------------------------
_ins33 = []
_o33 = (W._insert, W.FIRMA_VRAGEN)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma33-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins33.append(body) or {"id": "t33"}
try:
    _g33 = dict(ev("g33", "Mehdi: [EL-PO] overleg"), organizer={"email": "siyan@voorbeeld.test"})
    _g33b = dict(_g33, kalender="hdssuriname@gmail.com", _agendanaam="High Design Studio NV",
                 start={"dateTime": f"{_morgen}T14:00:00+01:00"}, end={"dateTime": f"{_morgen}T15:00:00+01:00"})
    _, niet33, onz33, _ = met(NepGoogle([], zichtbaar=False), W.firma_gasten, [_g33, _g33b], "tok")
    _r33 = met(NepGoogle([]), W.firma_vangnet, [_g33, _g33b], niet33, "tok", None, [], onz33)
finally:
    W._insert, W.FIRMA_VRAGEN = _o33
check("alleen gastkopieën met een verschillend uur: geen gast en geen blok, wel een vraag 'uur niet zeker' op Beschikbaar",
      not niet33 and len(_ins33) == 1 and "uur niet zeker" in _ins33[0]["summary"]
      and _ins33[0]["transparency"] == "transparent" and "date" in _ins33[0]["start"]
      and "10:00" in _ins33[0]["description"] and "14:00" in _ins33[0]["description"], str((_r33, _ins33)))

# --- Codex-hertest 14: de twijfelvraag dekt elke mogelijke datum en volgt elke kopie ---------------------------------
_ins34, _pat34 = [], []
_o34 = (W._insert, W.FIRMA_VRAGEN, W._prive_item_lezen, W._patch)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma34-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins34.append(body) or {"id": "t34"}
_d34a = (_nu + timedelta(days=2)).date().isoformat()
_d34b = (_nu + timedelta(days=10)).date().isoformat()
_k34a = dict(ev("g34", "Mehdi: [EL-PO] overleg"), organizer={"email": "siyan@voorbeeld.test"},
             start={"dateTime": f"{_d34b}T10:00:00+01:00"}, end={"dateTime": f"{_d34b}T11:00:00+01:00"})
_k34b = dict(_k34a, kalender="hdssuriname@gmail.com", _agendanaam="High Design Studio NV",
             start={"dateTime": f"{_d34a}T14:00:00+01:00"}, end={"dateTime": f"{_d34a}T15:00:00+01:00"})
W._prive_item_lezen = lambda eid, tok: {"id": eid, "titel": "VR Agendawacht: x", "_merk": {
    W.FIRMAMERK: W._firma_sleutel(_k34a), W.MAILMERK: "abcdef0123456789"}}
W._patch = lambda x, body, tok, **kw: _pat34.append(body)
try:
    met(NepGoogle([]), W.firma_vangnet, [_k34a, _k34b], [], "tok")
    _k34c = dict(_k34b, start={"dateTime": f"{_d34a}T16:00:00+01:00"}, end={"dateTime": f"{_d34a}T17:00:00+01:00"})
    met(NepGoogle([]), W.firma_vangnet, [_k34a, _k34c], [], "tok")        # alleen de tweede kopie verschuift
finally:
    W._insert, W.FIRMA_VRAGEN, W._prive_item_lezen, W._patch = _o34
_q = _ins34[0] if _ins34 else {}
check("de twijfelvraag loopt van de vroegste tot de laatste kopie en noemt per kopie datum en uur (hertest 14)",
      _q.get("start") == {"date": _d34a} and _q.get("end", {}).get("date", "") > _d34b
      and W._ddmm(_d34a) in _q.get("description", "") and W._ddmm(_d34b) in _q.get("description", "")
      and "14:00" in _q.get("description", "") and "10:00" in _q.get("description", ""), str(_q))
check("verschuift alleen een andere kopie, dan wordt de vraag bijgewerkt", len(_pat34) == 1 and "16:00" in _pat34[0]["description"],
      str(_pat34))

# --- Codex-hertest 15: tijden van firma-agenda's in Brusselse tijd (Suriname 21:30 = Brussel 01:30 de dag erna) ------
_sr = (_nu + timedelta(days=3)).date().isoformat()
_sr_na = (_nu + timedelta(days=4)).date().isoformat()
_k35 = dict(ev("g35", "Mehdi: [EL-PO] overleg"), organizer={"email": "siyan@voorbeeld.test"},
            start={"dateTime": f"{_sr}T21:30:00-03:00", "timeZone": "America/Paramaribo"},
            end={"dateTime": f"{_sr}T22:30:00-03:00", "timeZone": "America/Paramaribo"})
_ins35 = []
_o35 = (W._insert, W.FIRMA_VRAGEN)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma35-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins35.append(body) or {"id": "t35"}
try:
    _gelezen35, _ = met(NepGoogle([_k35]), W.firma_afspraken, "tok")
    met(NepGoogle([]), W.firma_vangnet, _gelezen35, [], "tok")
finally:
    W._insert, W.FIRMA_VRAGEN = _o35
check("een firma-afspraak om 21:30 Surinaamse tijd wordt gelezen als 01:30 Brusselse tijd de dag erna",
      _gelezen35 and _gelezen35[0]["start"]["dateTime"].startswith(f"{_sr_na}T01:30"), str(_gelezen35[:1]))
check("en de vraag staat op die Brusselse dag, met het Brusselse uur (hertest 15)",
      _ins35 and _ins35[0]["start"] == {"date": _sr_na} and "01:30" in _ins35[0]["description"]
      and "21:30" not in _ins35[0]["description"], str(_ins35[:1]))

# --- Codex-hertest 16: een tijd zonder offset geldt in haar eigen timeZone -----------------------------------------
_nb = W._naar_brussel({"start": {"dateTime": "2026-10-30T21:30:00", "timeZone": "America/Paramaribo"},
                       "end": {"dateTime": "2026-10-30T22:30:00", "timeZone": "America/Paramaribo"}})
check("een tijd zonder offset met timeZone Suriname wordt de juiste Brusselse tijd (31/10 01:30)",
      _nb["start"]["dateTime"].startswith("2026-10-31T01:30") and _nb["end"]["dateTime"].startswith("2026-10-31T02:30"), str(_nb))
_nb2 = W._naar_brussel({"start": {"dateTime": "2026-10-30T21:30:00"}}, "America/Paramaribo")
check("zonder offset en zonder timeZone geldt de tijdzone van de firma-agenda (hertest 17)",
      _nb2["start"]["dateTime"].startswith("2026-10-31T01:30"), str(_nb2))
_nb3 = W._naar_brussel({"start": {"dateTime": "2026-10-30T21:30:00"}})
check("is ook die onbekend, dan is de tijd onzeker", _nb3.get("_tijd_onzeker") is True)
_gk5, _, _tw5 = W._firma_kopieen_kiezen([dict(ev("tz1", "Mehdi: [EL-IN] overleg"), _tijd_onzeker=True)])
check("en dan geen blok maar de vraag 'uur niet zeker'", not _gk5 and len(_tw5) == 1)

# --- tweede review met meerdere agents --------------------------------------------------------------------------
_eig = dict(ev("eig1", "Mehdi: [EL-IN] weekoverleg"), organizer={"email": W.WERKAGENDA},
            attendees=[{"email": W.WERKAGENDA, "responseStatus": "accepted"}])
_gk6, _onz6, _tw6 = W._firma_kopieen_kiezen([_eig])
check("een afspraak die Mehdi zelf organiseert met een firma-agenda als gast: geen gast, geen blok, geen vraag",
      not _gk6 and not _onz6 and not _tw6)
_ins40 = []
_o40 = (W._insert, W.FIRMA_VRAGEN)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma40-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins40.append(body) or {"id": "q40"}
try:
    _col = dict(ev("col1", "SAIS26 | Panel"), organizer={"email": "siyan@voorbeeld.test"},
                attendees=[{"email": W.WERKAGENDA, "responseStatus": "accepted"}])
    met(NepGoogle([_col], zichtbaar=True), W.firma_vangnet, [_col], [], "tok")
    _n40a = len(_ins40)
    met(NepGoogle([_col], zichtbaar=False), W.firma_vangnet, [_col], [], "tok")
finally:
    W._insert, W.FIRMA_VRAGEN = _o40
check("een collega-afspraak waar Mehdi gast is en die zichtbaar op zijn werkagenda staat: geen vraag 'uur niet zeker'",
      _n40a == 0, str(_n40a))
check("staat ze niet zichtbaar, dan wel de vraag", len(_ins40) == 1 and "uur niet zeker" in _ins40[0]["summary"])

_pat41 = []
_o41 = (W.FIRMA_VRAGEN, W._prive_item_lezen, W._patch, W._eigen_melding_opgelost)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma41-")) / "agenda-firma-vragen.json")
_e41 = dict(ev("r41", "Mehdi: [EL-IN] overleg minister"), location="Bondgenotenlaan 1, 3000 Leuven")
_k41 = W._firma_sleutel(_e41)
Path(W.FIRMA_VRAGEN).write_text(json.dumps({_k41: {"gevraagd": _morgen, "dag": _morgen, "start": f"{_morgen}T08:00:00+01:00",
                                                   "einde": f"{_morgen}T09:00:00+01:00", "sterk": True, "id": "b41",
                                                   "kalender": ELEVAIT, "vinger": ""}}), encoding="utf-8")
W._prive_item_lezen = lambda eid, tok: {"id": eid, "titel": "Elevait: overleg minister", "maker": W.WERKAGENDA,
                                        "start": f"{_morgen}T08:00:00+01:00", "hele_dag": False,
                                        "_merk": {W.FIRMAMERK: _k41, W.MAILMERK: "abcdef0123456789"}}
W._patch = lambda x, body, tok, **kw: _pat41.append(body)
W._eigen_melding_opgelost = lambda *a, **k: (_ for _ in ()).throw(AssertionError("geen titelwijziging"))
try:
    met(NepGoogle([]), W.firma_vangnet, [_e41], [_e41], "tok")      # de afspraak schoof van 08:00 naar 10:00
    met(NepGoogle([]), W.firma_vangnet, [], [], "tok")              # en verdwijnt
finally:
    W.FIRMA_VRAGEN, W._prive_item_lezen, W._patch, W._eigen_melding_opgelost = _o41
check("een blok dat Mehdi hernoemde, schuift mee zonder dat zijn titel verandert, met de plaats van de afspraak",
      _pat41 and "summary" not in _pat41[0] and _pat41[0]["start"]["dateTime"].endswith("10:00:00+01:00")
      and _pat41[0]["location"] == "Bondgenotenlaan 1, 3000 Leuven", str(_pat41[:1]))
check("en verdwijnt de afspraak, dan wordt het opgelost en Beschikbaar, zijn titel blijft",
      len(_pat41) == 2 and "summary" not in _pat41[1] and _pat41[1]["transparency"] == "transparent"
      and _pat41[1]["extendedProperties"]["private"][W.MAILMERK].startswith("opgelost:"), str(_pat41[1:]))
_bd = W._firma_vraag_body(_k41, _e41, _e41["start"]["dateTime"], True)
check("een Bezet blok draagt de plaats van de afspraak (rit en vertrekoproep in plaats van 'online')",
      _bd.get("location") == "Bondgenotenlaan 1, 3000 Leuven")

# --- Codex-hertest 18: een zekere organisatorkopie gaat voor; een gast met onzekere tijd krijgt meteen de vraag -------
_org18 = ev("u18", "Mehdi: [EL-PO] overleg")
_gst18 = dict(_org18, kalender="hdssuriname@gmail.com", _agendanaam="High Design Studio NV", _tijd_onzeker=True)
_gk18, _onz18, _tw18 = W._firma_kopieen_kiezen([_gst18, _org18])
check("een gastkopie met onzekere tijd verdringt de zekere kopie van de organisator niet", [e["kalender"] for e in _gk18] == [ELEVAIT]
      and not _tw18, str((_gk18, _tw18)))
_ins42 = []
_o42 = (W._insert, W.FIRMA_VRAGEN)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma42-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins42.append(body) or {"id": "q42"}
try:
    _g42 = dict(ev("g42", "Mehdi: [EL-PO] overleg"), organizer={"email": "siyan@voorbeeld.test"}, _tijd_onzeker=True,
                attendees=[{"email": W.WERKAGENDA, "responseStatus": "accepted"}])
    met(NepGoogle([], zichtbaar=True), W.firma_vangnet, [_g42], [], "tok")
finally:
    W._insert, W.FIRMA_VRAGEN = _o42
check("een uitgenodigde gast met onbekende tijdzone krijgt meteen de vraag 'uur niet zeker'",
      len(_ins42) == 1 and "uur niet zeker" in _ins42[0]["summary"], str(_ins42))

# --- Codex-hertest 19: bleek de tijd bij het herlezen onzeker, dan de vraag, geen blok ------------------------------
_e19 = ev("h19", "Mehdi: [EL-IN] overleg", gasten=[{"email": W.WERKAGENDA, "responseStatus": "accepted"}])
g19 = NepGoogle([_e19], zichtbaar=False, vers={"h19": {"start": {"dateTime": f"{_morgen}T21:30:00"},
                                                       "end": {"dateTime": f"{_morgen}T22:30:00"}}})
_o19z = dict(W._KAL_TZ)
W._KAL_TZ.pop(ELEVAIT, None)
try:
    _, niet19, _, _ = met(g19, W.firma_gasten, [_e19], "tok")
finally:
    W._KAL_TZ.clear()
    W._KAL_TZ.update(_o19z)
_ins43 = []
_o43 = (W._insert, W.FIRMA_VRAGEN)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma43-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins43.append(body) or {"id": "q43"}
try:
    met(NepGoogle([]), W.firma_vangnet, [_e19], niet19, "tok")
finally:
    W._insert, W.FIRMA_VRAGEN = _o43
check("bleek de tijd bij het herlezen onzeker, dan de vraag 'uur niet zeker' en geen Bezet blok (hertest 19)",
      niet19 and niet19[0].get("_tijd_onzeker") and len(_ins43) == 1 and "uur niet zeker" in _ins43[0]["summary"]
      and _ins43[0]["transparency"] == "transparent", str((niet19, _ins43)))

# --- Codex-hertest 20: onbekende tijdzone dekt de aangrenzende dagen; 'mehdi' in kleine letters telt -------------------
_d20a = (_nu + timedelta(days=3)).date().isoformat()
_d20b = (_nu + timedelta(days=4)).date().isoformat()
_d20c = (_nu + timedelta(days=2)).date().isoformat()
_e20 = dict(ev("tz20", "Mehdi: [EL-IN] overleg"), _tijd_onzeker=True,
            start={"dateTime": f"{_d20a}T21:30:00"}, end={"dateTime": f"{_d20a}T22:30:00"},
            _kopieen=[("Elevait N.V.", f"{_d20a}T21:30:00", f"{_d20a}T22:30:00")])
_b20 = W._firma_vraag_body("firma|tz20@google.com|", _e20, f"{_d20a}T21:30:00", None)
check("bij een onbekende tijdzone dekt de vraag ook de dag ervoor en erna (hertest 20)",
      _b20["start"] == {"date": _d20c} and _b20["end"]["date"] > _d20b, str((_b20["start"], _b20["end"])))
_ins44 = []
_o44 = (W._insert, W.FIRMA_VRAGEN)
W.FIRMA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="firma44-")) / "agenda-firma-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins44.append(body) or {"id": "q44"}
try:
    _klein = ev("kl44", "Overleg KDS", beschrijving="mehdi sluit aan")
    met(NepGoogle([]), W.firma_vangnet, [_klein], [], "tok")
finally:
    W._insert, W.FIRMA_VRAGEN = _o44
check("'mehdi' in kleine letters in de omschrijving geeft ook een vraag (hertest 20)", len(_ins44) == 1, str(len(_ins44)))

_bron = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
_kleur = _bron[_bron.index('if "--kleuren" in sys.argv:'):_bron.index('if "--zorg" in sys.argv:')]
check("de firmacontrole draait ook in de kleurronde (om :17 en :47, elke dag, ook in het weekend; punt 15)",
      "firma_kleurronde(" in _kleur)
_o_kr = (W.firma_stap, W.FIRMA_NODEN, W.ag.log)
W.FIRMA_NODEN = str(Path(tempfile.mkdtemp(prefix="firmanoden-")) / "agenda-firma-noden.json")
_kr_log, _kr_noden = [], [[{"tekst": "Firma-agenda niet te lezen: HDS", "wie": "claude"}]] * 2 + [[]]
W.firma_stap = lambda vandaag: _kr_noden.pop(0)
W.ag.log = lambda *a, **k: _kr_log.append(a)
try:
    for _ in range(3):
        W.firma_kleurronde("2026-10-31")
finally:
    W.firma_stap, W.FIRMA_NODEN, W.ag.log = _o_kr
check("in de kleurronde komt een nood in het werkverslag, eenmaal, en ook het herstel (overleg P8)",
      [a[2] for a in _kr_log] == ["firma-agenda's: Firma-agenda niet te lezen: HDS", "firma-agenda's: weer in orde"],
      str(_kr_log))
_o_st = (W.agenda.zichtbaarheid, W.firma_meelezen)
W.agenda.zichtbaarheid = lambda: {W.WERKAGENDA: False, ELEVAIT: False}
W.firma_meelezen = lambda: []
try:
    _nst = W.firma_stap("2026-10-27")
finally:
    W.agenda.zichtbaarheid, W.firma_meelezen = _o_st
check("staat Mehdi's werkagenda verborgen, dan een nood voor Mehdi zonder teller; Elevait verborgen is goed",
      len(_nst) == 1 and "mehdi werk agenda" in _nst[0]["tekst"] and "Elevait" not in _nst[0]["tekst"]
      and not any(ch.isdigit() for ch in _nst[0]["tekst"]), str(_nst))
import fcntl  # noqa: E402
_o_sl = (W.FIRMA_SLOT, W.agenda.zichtbaarheid, W.firma_afspraken)
W.FIRMA_SLOT = str(Path(tempfile.mkdtemp(prefix="firmaslot-")) / "agenda-firma.lock")
W.agenda.zichtbaarheid = lambda: {}
_gelezen = []
W.firma_afspraken = lambda tok, *a, **k: _gelezen.append(1) or ([], [])
_tok_o = W.agenda._toegang
W.agenda._toegang = lambda: "tok"
try:
    with open(W.FIRMA_SLOT, "w") as _sl:
        fcntl.flock(_sl, fcntl.LOCK_EX)
        W.firma_stap("2026-10-27")
finally:
    W.FIRMA_SLOT, W.agenda.zichtbaarheid, W.firma_afspraken = _o_sl
    W.agenda._toegang = _tok_o
check("loopt er al een firmacontrole (slot), dan leest een tweede ronde niets", not _gelezen)

# --- Z4: de zichtbaarheid teruglezen -------------------------------------------------------------------------
_ur.urlopen = lambda req, timeout=None, *a, **k: io.BytesIO(json.dumps({"items": [
    {"id": ELEVAIT, "selected": False}, {"id": W.WERKAGENDA, "selected": True}, {"id": "zonder"},
    {"id": "weg", "selected": True, "hidden": True}]}).encode())
_otok = W.agenda._toegang
W.agenda._toegang = lambda: "tok"
try:
    zicht = W.agenda.zichtbaarheid()
finally:
    _ur.urlopen = _echt
    W.agenda._toegang = _otok
check("de zichtbaarheid per agenda is terug te lezen (aangevinkt en niet uit de lijst gehaald)",
      zicht == {ELEVAIT: False, W.WERKAGENDA: True, "zonder": False, "weg": False}, str(zicht))

# --- onleesbare firma-agenda's: geen gast en geen vangnet op een halve lezing --------------------------------
_ur.urlopen = lambda *a, **k: (_ for _ in ()).throw(OSError("netwerk weg"))
try:
    check("zijn alle firma-agenda's onleesbaar, dan geen afspraken en alle twee gemeld",
          W.firma_afspraken("tok") == ([], [ELEVAIT, "hdssuriname@gmail.com"]))
finally:
    _ur.urlopen = _echt

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

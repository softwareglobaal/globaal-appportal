"""Grendel op de agendagasten (Mehdi, 03-10-2026, FR-102; uitnodiging 18-10-2026). Zonder netwerk en sleutels (ook CI).

Bewijst: een collega na 'Mehdi' in de titel wordt agendagast; Harmoniebouw brengt Catalin mee (ook als 'Karam'); een
klant met dezelfde voornaam elders in de titel niet; een naam die twee mensen aanwijst niet; gewone wijzigingen gaan zonder
mail (sendUpdates=none), bestaande gasten blijven, de reeks in de reeks, nooit op een afspraak van een ander, nooit iemand
weghalen; een agendagast telt niet als gast van buiten. Alleen de toegestane partner krijgt eenmaal een uitnodiging op een
afspraak ter plaatse met adres; online, intern, zonder adres, een ander adres en een reeks blijven stil.
"""
import ast
import copy
import json
import os
import sys
from pathlib import Path

os.environ["BELLEN_UIT"] = "1"
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


MENSEN = {"harmoniebouw@gmail.com": {"voornaam": "Catalin", "achternaam": "", "naam": "Catalin", "in_dienst": True},
          "matthewblijd10@gmail.com": {"voornaam": "Matthew", "achternaam": "Blijd", "naam": "Matthew (Orvantis)", "in_dienst": True},
          "luc1@gmail.com": {"voornaam": "Luc", "achternaam": "A", "naam": "Luc A", "in_dienst": True},
          "luc2@gmail.com": {"voornaam": "Luc", "achternaam": "B", "naam": "Luc B", "in_dienst": True},
          "oud@gmail.com": {"voornaam": "Rochelle", "achternaam": "K", "naam": "Rochelle", "in_dienst": False}}
REGELS = json.loads((HIER / "werkwijze" / "agenda-taken.json").read_text(encoding="utf-8"))["agendagasten"]


def gv(titel):
    return W.agendagasten_voor(titel, REGELS, MENSEN)


check("een collega na 'Mehdi' in de titel wordt agendagast",
      gv("!! Mehdi & Catalin: [HA-KB] 2443 - Jenny Michielsen, Oudebareellei 104, 2170 Merksem") == {"harmoniebouw@gmail.com"}
      and gv("Mehdi+Tom+Matthew: [UB-IN] engineering wekelijks") == {"matthewblijd10@gmail.com"}
      and gv("VR Mehdi, Matthew en Catalin: [TK-IN] overleg") == {"matthewblijd10@gmail.com", "harmoniebouw@gmail.com"})
check("een afspraak van Harmoniebouw brengt Catalin mee, ook als hij 'Karam' heet",
      gv("Mehdi: [HB-IN] planning werf") == {"harmoniebouw@gmail.com"} and gv("Mehdi en Karam: [HA-IN] overleg") == {"harmoniebouw@gmail.com"})
check("een klant met de voornaam van een collega, niet na 'Mehdi', wordt geen gast",
      gv("Mehdi: [UB-PO] Matthew Janssens - ST") == set() and gv("Matthew Janssens: H-Architects prospectie") == set())
check("een naam die twee mensen aanwijst, of iemand uit dienst, wordt geen gast (geen gok)",
      gv("Mehdi & Luc: [EE-IN] overleg") == set() and gv("Mehdi & Rochelle: [EE-IN] overleg") == set())

# zetten
_o = (W.organisatie.agenda_adressen, W._event, W._patch, W.agenda._toegang)
_patches, _staat = [], {}


def _nep_event(a, tok):
    return _staat.get(a["id"], {"attendees": []})


def _nep_patch(a, body, tok, toch=False):
    _patches.append((a["id"], body))
    _staat[a["id"]] = {"attendees": body["attendees"]}


W.organisatie.agenda_adressen = lambda *x, **k: MENSEN
W._event, W._patch, W.agenda._toegang = _nep_event, _nep_patch, (lambda: "t")
_staat["klant"] = {"attendees": [{"email": "klant@voorbeeld.be", "responseStatus": "accepted"}]}
_staat["reeks1"] = {"attendees": [], "summary": "Mehdi+Matthew: [UB-IN] wekelijks"}
_morgen = (W.nu_lokaal().date().toordinal() + 1)
from datetime import date   # noqa: E402
_d = date.fromordinal(_morgen).isoformat()
ITEMS = [
    {"id": "jenny", "kalender": W.WERKAGENDA, "titel": "!! Mehdi & Catalin: [HA-KB] 2443 - Jenny", "start": f"{_d}T17:00:00+02:00", "_organisator_zelf": True},
    {"id": "klant", "kalender": W.WERKAGENDA, "titel": "Mehdi & Catalin: [HA-KO] 2607 - Robin", "start": f"{_d}T18:00:00+02:00", "_organisator_zelf": True},
    {"id": "al", "kalender": W.WERKAGENDA, "titel": "Mehdi & Catalin: [HA-IN] x", "start": f"{_d}T19:00:00+02:00", "_organisator_zelf": True,
     "_agendagasten": ["harmoniebouw@gmail.com"]},
    {"id": "ander", "kalender": W.WERKAGENDA, "titel": "Mehdi & Catalin: [HA-IN] van een ander", "start": f"{_d}T20:00:00+02:00", "_organisator_zelf": False},
    {"id": "prive", "kalender": "mehdipriveagena@gmail.com", "titel": "Mehdi & Catalin: [PR] etentje", "start": f"{_d}T21:00:00+02:00", "_organisator_zelf": True},
    {"id": "i1", "_reeks": "reeks1", "kalender": W.WERKAGENDA, "titel": "Mehdi+Matthew: [UB-IN] wekelijks", "start": f"{_d}T09:00:00+02:00", "_organisator_zelf": True},
    {"id": "i2", "_reeks": "reeks1", "kalender": W.WERKAGENDA, "titel": "Mehdi+Matthew: [UB-IN] wekelijks", "start": f"{_d}T10:00:00+02:00", "_organisator_zelf": True},
    {"id": "voorbij", "kalender": W.WERKAGENDA, "titel": "Mehdi & Catalin: [HA-IN] gisteren", "start": "2020-01-01T10:00:00+01:00", "_organisator_zelf": True},
]
try:
    _r = W.agendagasten_zetten(ITEMS)
finally:
    W.organisatie.agenda_adressen, W._event, W._patch, W.agenda._toegang = _o
_ids = [p[0] for p in _patches]
check("zetten: alleen eigen, komende afspraken op de werkagenda; de reeks een keer in de reeks zelf",
      sorted(_ids) == ["jenny", "klant", "reeks1"], str(_ids))
check("bestaande gasten blijven staan, de agendagast komt erbij",
      [p[1]["attendees"] for p in _patches if p[0] == "klant"] == [[{"email": "klant@voorbeeld.be", "responseStatus": "accepted"}, {"email": "harmoniebouw@gmail.com"}]])
check("teruggelezen en gemeld; niemand weggehaald", all("als gast gezet, zonder mail" in r for r in _r) and len(_r) == 3
      and all(len(p[1]["attendees"]) >= len(_staat.get(p[0], {}).get("attendees", [])) for p in _patches), str(_r))
_bron = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
_functies = {n.name: ast.get_source_segment(_bron, n) for n in ast.parse(_bron).body if isinstance(n, ast.FunctionDef)}
_fn = _functies["agendagasten_zetten"]
check("gewone schrijfroutes blijven stil; precies de aparte uitnodigingsfunctie mag sendUpdates=all gebruiken",
      "_patch(doel, {\"attendees\"" in _fn and "sendUpdates" not in _fn
      and "sendUpdates=none" in _functies["_patch"]
      and _bron.count("sendUpdates=all") == 1
      and [naam for naam, bron in _functies.items() if "sendUpdates=all" in bron] == ["_uitnodiging_patch"])

# een agendagast telt niet als gast van buiten
_src_ag = (HIER / "koppelingen" / "agenda.py").read_text(encoding="utf-8")
check("koppelingen/agenda.py telt een agendagast niet bij de gasten van buiten",
      'a["email"].lower() not in _intern' in _src_ag and "_intern = interne_adressen()" in _src_ag
      and W._van_mehdi({"kalender": W.WERKAGENDA, "maker": W.WERKAGENDA, "deelnemers": []}))

# Besluit van 18-10-2026: alleen het genoemde partneradres, eenmaal en alleen ter plaatse.
_master = json.loads((HIER / "werkwijze" / "agenda-taken.json").read_text(encoding="utf-8"))
_partner = "harmoniebouw@gmail.com"
check("master 5.13 beperkt de uitnodiging tot het partneradres en legt het besluit vast",
      _master.get("versie") == "5.13" and REGELS.get("uitnodigen_ter_plaatse") == [_partner]
      and any(b.get("datum") == "2026-10-18" and "mocht je al die mails sturen" in b.get("wat", "")
              for b in _master.get("beslissingen", [])))
check("werkwijze 8.15 noemt de uitnodiging",
      "Versie 8.15" in (HIER / "werkwijze" / "agenda-wacht.md").read_text(encoding="utf-8"))

_inv_oud = getattr(W, "_uitnodiging_patch", None)
check("de uitnodiging heeft een aparte schrijffunctie", _inv_oud is not None)
_mensen_oud, _event_oud, _patch_oud, _toegang_oud, _voor_oud = (
    W.organisatie.agenda_adressen, W._event, W._patch, W.agenda._toegang, W.agendagasten_voor)
_ander = "ander@voorbeeld.test"
_mensen = {_partner: {"voornaam": "Partner", "naam": "Partner", "in_dienst": True},
           _ander: {"voornaam": "Collega", "naam": "Collega", "in_dienst": True}}
_staat2 = {id_: {"attendees": [{"email": adres}], "extendedProperties": {"private": {"ander_merk": "bewaar"}}}
           for id_, adres in (("fysiek", _partner), ("titeladres", _partner), ("plaatsadres", _partner),
                              ("link", _partner), ("online", _partner), ("prospect_online", _partner),
                              ("intern", _partner), ("zonder_adres", _partner), ("ander_adres", _ander),
                              ("reeks", _partner), ("andere_maker", _partner), ("andere_agenda", _partner))}
_staat2["nieuw"] = {"attendees": [], "extendedProperties": {"private": {"ander_merk": "bewaar"}}}
_staat2["prive"] = {"attendees": [], "extendedProperties": {"private": {"ander_merk": "bewaar"}}}
_alle, _stil = [], []


def _lees2(a, tok):
    return copy.deepcopy(_staat2[a["id"]])


def _stil2(a, body, tok, toch=False):
    _stil.append(a["id"])
    _staat2[a["id"]]["attendees"] = copy.deepcopy(body["attendees"])


def _uitnodig2(a, body, tok):
    _alle.append((a["id"], copy.deepcopy(body)))
    _staat2[a["id"]]["attendees"] = copy.deepcopy(body["attendees"])
    _staat2[a["id"]]["extendedProperties"] = copy.deepcopy(body["extendedProperties"])


def _voor2(titel, regels=None, mensen=None):
    return {_partner} if "nieuwe gast" in titel or "ZEER_VERTROUWELIJK" in titel else set()


def _item(id_, soort="KB", locatie="Testlaan 1, 0000 Teststad", **extra):
    return {"id": id_, "kalender": W.WERKAGENDA, "titel": f"!! [HA-{soort}] proef",
            "start": f"{_d}T16:00:00+02:00", "locatie": locatie, "_organisator_zelf": True,
            "_agendagasten": [_partner] if id_ != "nieuw" else [], **extra}


_items2 = [
    _item("fysiek"),
    _item("nieuw", titel="[HA-KB] nieuwe gast"),
    _item("titeladres", locatie="", titel="!! [HA-KB] proef, Testlaan 1, 0000 Teststad"),
    _item("plaatsadres", titel="[HA] proef"),
    _item("link", locatie="https://zoom.us/j/proef"),
    _item("online", soort="KO"),
    _item("prospect_online", soort="PO"),
    _item("intern", soort="IN"),
    _item("zonder_adres", locatie=""),
    _item("ander_adres", _agendagasten=[_ander]),
    _item("reeks", _reeks="hoofd-reeks"),
    _item("andere_maker", _organisator_zelf=False),
    _item("andere_agenda", kalender="test-agenda@voorbeeld.test"),
    _item("prive", titel="[PR] ZEER_VERTROUWELIJK", _agendagasten=[]),
]
try:
    W.organisatie.agenda_adressen = lambda *x, **k: _mensen
    W._event, W._patch, W._uitnodiging_patch, W.agenda._toegang = _lees2, _stil2, _uitnodig2, (lambda: "t")
    W.agendagasten_voor = _voor2
    _eerste = W.agendagasten_zetten(_items2)
    _na_eerste = len(_alle)
    _tweede = W.agendagasten_zetten(_items2)
finally:
    W.organisatie.agenda_adressen, W._event, W._patch, W.agenda._toegang, W.agendagasten_voor = (
        _mensen_oud, _event_oud, _patch_oud, _toegang_oud, _voor_oud)
    if _inv_oud is None:
        delattr(W, "_uitnodiging_patch")
    else:
        W._uitnodiging_patch = _inv_oud

check("ter plaatse met bestaande partnergast: precies één uitnodiging met gast, merk en bestaand privaat merk",
      [id_ for id_, _ in _alle] == ["fysiek", "nieuw", "titeladres", "plaatsadres"]
      and all(b["extendedProperties"]["private"].get("agendawacht_uitgenodigd") == _partner
              and b["extendedProperties"]["private"].get("ander_merk") == "bewaar"
              and _partner in {g["email"] for g in b["attendees"]} for _, b in _alle), str(_alle))
check("nieuwe partnergast gaat eerst stil erbij en krijgt daarna eenmaal de uitnodiging",
      _stil == ["nieuw", "prive"] and _na_eerste == 4 and len(_alle) == 4, f"stil={_stil}, all={_alle}")
check("tweede ronde leest het merk terug en stuurt niets opnieuw",
      len(_alle) == _na_eerste and all(_staat2[id_]["extendedProperties"]["private"].get("agendawacht_uitgenodigd") == _partner
                                       for id_ in ("fysiek", "nieuw", "titeladres", "plaatsadres")))
check("online link en soorten KO/PO, intern en zonder adres krijgen geen mail",
      not {"link", "online", "prospect_online", "intern", "zonder_adres"} & {id_ for id_, _ in _alle})
check("een ander adres dan de lijst krijgt geen mail", "ander_adres" not in {id_ for id_, _ in _alle})
check("alleen de werkagenda en een eigen afspraak kunnen een uitnodiging krijgen",
      not {"andere_maker", "andere_agenda"} & {id_ for id_, _ in _alle})
check("een reeks krijgt geen mail en wel een voorstel in de regels",
      "reeks" not in {id_ for id_, _ in _alle} and any("VOORSTEL" in r and "reeks" in r for r in _eerste), str(_eerste))
check("na het uitnodigen zijn gast en merk teruggelezen en staat dat in de regels",
      sum("uitnodiging aan Partner, gast en merk teruggelezen" in r for r in _eerste) == 4, str(_eerste))
check("privétitels blijven uit de gastregels, ook bij een stille toevoeging",
      any("(privé)" in r and "als gast gezet, zonder mail" in r for r in _eerste)
      and not any("ZEER_VERTROUWELIJK" in r for r in _eerste + _tweede), str(_eerste))

_staat2["zonder_bron"] = {"attendees": [{"email": _partner}], "extendedProperties": {"private": {}}}
_aantal_alle = len(_alle)
try:
    W.organisatie.agenda_adressen = lambda *x, **k: {}
    W._event, W._uitnodiging_patch, W.agenda._toegang = _lees2, _uitnodig2, (lambda: "t")
    _zonder_bron = W.agendagasten_zetten([_item("zonder_bron")])
finally:
    W.organisatie.agenda_adressen, W._event, W.agenda._toegang = _mensen_oud, _event_oud, _toegang_oud
    if _inv_oud is None:
        delattr(W, "_uitnodiging_patch")
    else:
        W._uitnodiging_patch = _inv_oud
check("een al aanwezige toegestane gast krijgt de uitnodiging ook als de personenbron tijdelijk leeg is",
      len(_alle) == _aantal_alle + 1 and _alle[-1][0] == "zonder_bron"
      and any("gast en merk teruggelezen" in r for r in _zonder_bron), str(_zonder_bron))

# Het agendaoverzicht bevat gasten en het private uitnodigingsmerk al. Alleen een mogelijke nieuwe uitnodiging
# rechtvaardigt het afzonderlijk lezen van het item bij Google.
_lezingen, _nieuwe_uitnodigingen = [], []
_staat3 = {
    "zonder_partner": {"attendees": [{"email": _ander}], "extendedProperties": {"private": {}}},
    "al_gemarkeerd": {"attendees": [{"email": _partner}],
                       "extendedProperties": {"private": {W.UITNODIGMERK: _partner}}},
}


def _lees3(a, tok):
    _lezingen.append(a["id"])
    return copy.deepcopy(_staat3[a["id"]])


def _uitnodig3(a, body, tok):
    _nieuwe_uitnodigingen.append(a["id"])


try:
    W.organisatie.agenda_adressen = lambda *x, **k: _mensen
    W.agendagasten_voor = _voor2
    W._event, W._uitnodiging_patch, W.agenda._toegang = _lees3, _uitnodig3, (lambda: "t")
    W.agendagasten_zetten([_item("zonder_partner", _agendagasten=[_ander],
                                 deelnemers=["BUITEN@VOORBEELD.TEST"])])
    _lezingen_zonder_partner = _lezingen[:]
    _uitnodigingen_zonder_partner = _nieuwe_uitnodigingen[:]
    _lezingen.clear()
    W.agendagasten_zetten([_item("al_gemarkeerd", _merk={W.UITNODIGMERK: _partner})])
finally:
    W.organisatie.agenda_adressen, W._event, W.agenda._toegang, W.agendagasten_voor = (
        _mensen_oud, _event_oud, _toegang_oud, _voor_oud)
    if _inv_oud is None:
        delattr(W, "_uitnodiging_patch")
    else:
        W._uitnodiging_patch = _inv_oud
check("fysieke afspraak zonder toegestane partner leest het item niet",
      not _lezingen_zonder_partner and not _uitnodigingen_zonder_partner, str(_lezingen_zonder_partner))
check("al gemarkeerde partner leest het item niet en stuurt niets",
      not _lezingen and not _nieuwe_uitnodigingen, f"lezingen={_lezingen}, uitnodigingen={_nieuwe_uitnodigingen}")

if _inv_oud is not None:
    import urllib.request as _ur
    _open_oud, _mag_oud = _ur.urlopen, W.mag_schrijven
    _verzoeken = []
    _ur.urlopen = lambda req, timeout=0: (_verzoeken.append(req), type("R", (), {"read": lambda s: b"{}"})())[1]
    W.mag_schrijven = lambda kal: True
    _afgewezen = []
    try:
        W._uitnodiging_patch(_item("proef"),
                            {"attendees": [{"email": _partner}],
                             "extendedProperties": {"private": {"agendawacht_uitgenodigd": _partner}}}, "tok")
        for a, adres in ((_item("proef", locatie="https://zoom.us/j/proef"), _partner),
                         (_item("proef", _reeks="hoofd-reeks"), _partner),
                         (_item("proef"), _ander)):
            try:
                W._uitnodiging_patch(a, {"attendees": [{"email": adres}],
                                         "extendedProperties": {"private": {"agendawacht_uitgenodigd": adres}}}, "tok")
            except ValueError:
                _afgewezen.append(True)
    finally:
        _ur.urlopen, W.mag_schrijven = _open_oud, _mag_oud
    check("alleen de aparte schrijffunctie doet één API PATCH met sendUpdates=all en het merk",
          len(_verzoeken) == 1 and "sendUpdates=all" in _verzoeken[0].full_url
          and json.loads(_verzoeken[0].data)["extendedProperties"]["private"]["agendawacht_uitgenodigd"] == _partner)
    check("de aparte schrijffunctie weigert online, een reeks en een ander adres zelf",
          len(_afgewezen) == 3 and len(_verzoeken) == 1)

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

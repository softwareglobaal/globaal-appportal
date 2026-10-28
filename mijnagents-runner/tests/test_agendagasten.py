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
check("een tikfout van Catalin na 'Mehdi' blijft Catalin (28-10-2026: 'Mehdi en Catlain', 'Katalin')",
      gv("!! Mehdi en Catlain: [HA-KB] PL 2605 - Céline Palms, Van der Nootstraat 88, 3012 Leuven") == {"harmoniebouw@gmail.com"}
      and gv("Mehdi & Katalin: [HA-IN] overleg") == {"harmoniebouw@gmail.com"}
      and gv("Mehdi & Lux: [EE-IN] overleg") == set())
_org = W.organisatie.agenda_adressen
W.organisatie.agenda_adressen = lambda *a, **k: MENSEN
check("een herschreven titel houdt de namen voor de dubbele punt, met de juiste schrijfwijze",
      W.mehdi_kop("!! Mehdi en Catlain: HA 2605 plaatsbezoek") == "Mehdi & Catalin"
      and W.mehdi_kop("Mehdi, Matthew en Katalin: x") == "Mehdi, Matthew & Catalin"
      and W.mehdi_kop("Mehdi: 2605") == "Mehdi" and W.mehdi_kop("Mehdi bellen: x") == "Mehdi")
_kaart, _klant = W.projectadressen.index, W.klant_van_nummer
W.projectadressen.index = lambda *a, **k: {"2605": {"adres": "Van der Nootstraat 88, 3012 Leuven"}}
W.klant_van_nummer = lambda n: "Céline Palms"
_nieuw, _ = W.titel_uit_onderzoek({"titel": "!! Mehdi en Catlain: HA 2605 plaatsbezoek",
                                   "locatie": "Van der Nootstraat 88, 3012 Leuven"})
check("spoor 1 (projectnummer) laat Catalin niet meer weg: dan volgen gast en uitnodiging",
      (_nieuw or "").startswith("!! Mehdi & Catalin: [HA-KB]") and "2605 - Céline Palms" in (_nieuw or ""), _nieuw)
W.projectadressen.index, W.klant_van_nummer, W.organisatie.agenda_adressen = _kaart, _klant, _org
check("de boekhouder is algemeen, ook met een tikfout, en nooit een vraag welke firma (28-10-2026)",
      W.titel_voorstel("VR Mehdi & Angela: Nandien boekhouder")[:3] == ("VR Mehdi & Angela: [AL-LO] Nandien boekhouder", "ALGE", "LO")
      and W.titel_voorstel("!! Mehdi: Nadine jaarafsluiting")[2] == "LB")
check("een afdeling van een eigen firma is intern: 'AI van EE afdeling' wordt [EE-IN] (28-10-2026)",
      W.titel_voorstel("VR Mehdi: Ai van EE afdeling")[:3] == ("VR Mehdi: [EE-IN] Ai van EE afdeling", "ENEF", "IN"))
check("een afspraak zonder code is grafiet, nooit de lichtgroene agendakleur; een hele dag niet",
      W.kleur_gewenst({"kalender": W.WERKAGENDA}, W.lees_titel("Johan Buyse en General")) == "8"
      and W.kleur_gewenst({"kalender": W.WERKAGENDA, "hele_dag": True}, W.lees_titel("Johan Buyse")) == "")
check("driehoeksoverleg FR-211: Karim is geen Karam, een korte naam lijkt nooit, 'met' scheidt ook",
      gv("Mehdi en Karim: [EE-KB] werf, Kerkstraat 1, 3000 Leuven") == set()
      and gv("Mehdi met Catalin: [HA-IN] overleg") == {"harmoniebouw@gmail.com"}
      and not W._lijkt_op("Karim", "Karam") and W._lijkt_op("Catlain", "Catalin"))
W.organisatie.agenda_adressen = lambda *a, **k: MENSEN
check("driehoeksoverleg FR-211: alleen bekende namen in de kop, een bijnaam alleen letterlijk",
      W.mehdi_kop("Mehdi en Karim: x") == "Mehdi" and W.mehdi_kop("Mehdi + Werf: x") == "Mehdi"
      and W.mehdi_kop("Mehdi met Catlain: x") == "Mehdi & Catalin" and W.mehdi_kop("Mehdi en Karam: x") == "Mehdi & Karam")
W.organisatie.agenda_adressen = _org
check("driehoeksoverleg FR-211: een gewoon woord of een rolwoord met een tikfout is geen boekhouder",
      W.titel_voorstel("Mehdi: nadeel bespreken EE")[1] == "ENEF"
      and W.titel_voorstel("Mehdi: boekhouden UB")[1] == "UNAB"
      and W.titel_voorstel("Mehdi: Nadein kwartaal")[1] == "ALGE")
_tok, _pt = W.agenda._toegang, W._patch
_gepatcht = []
W.agenda._toegang, W._patch = (lambda: "t"), (lambda a, body, tok, **k: _gepatcht.append(a["id"]))
_vandaag = W.nu_lokaal().date().isoformat()
W.kleuren_zetten([{"id": "zorg", "kalender": W.WERKAGENDA, "titel": "Tandarts", "start": _vandaag + "T23:00:00+01:00",
                   "_zorg_schaduw": True, "omschrijving": ""},
                  {"id": "cal", "kalender": W.WERKAGENDA, "titel": "Johan Buyse en General", "start": _vandaag + "T23:00:00+01:00",
                   "omschrijving": "Mogelijk gemaakt door Calendly.com", "locatie": "https://calendly.com/x"},
                  {"id": "rood", "kalender": W.WERKAGENDA, "titel": "zonder code", "start": _vandaag + "T23:00:00+01:00",
                   "_kleur": "11", "omschrijving": ""},
                  {"id": "leeg", "kalender": W.WERKAGENDA, "titel": "zonder code", "start": _vandaag + "T23:00:00+01:00",
                   "omschrijving": ""}])
W.agenda._toegang, W._patch = _tok, _pt
check("grafiet alleen op een kleurloze eigen afspraak: niet op een zorgschaduw, Calendly of een kleur van een ander",
      _gepatcht == ["leeg"], _gepatcht)
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
check("de master beperkt de uitnodiging tot het partneradres en legt het besluit vast",
      REGELS.get("uitnodigen_ter_plaatse") == [_partner]
      and any(b.get("datum") == "2026-10-18" and "mocht je al die mails sturen" in b.get("wat", "")
              for b in _master.get("beslissingen", [])))
_ww = (HIER / "werkwijze" / "agenda-wacht.md").read_text(encoding="utf-8")
check("werkwijze v8.18 noemt de uitnodiging en het merk",
      "Aanvulling v8.18" in _ww and "agendawacht_uitgenodigd" in _ww)

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
    _open_oud, _mag_oud, _lees_oud = _ur.urlopen, W.mag_schrijven, W._event
    _verzoeken = []
    _ur.urlopen = lambda req, timeout=0: (_verzoeken.append(req), type("R", (), {"read": lambda s: b"{}"})())[1]
    W.mag_schrijven = lambda kal: True
    W._event = lambda a, tok: {"attendees": [{"email": _partner}]}
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
        _ur.urlopen, W.mag_schrijven, W._event = _open_oud, _mag_oud, _lees_oud
    check("alleen de aparte schrijffunctie doet één API PATCH met sendUpdates=all en het merk",
          len(_verzoeken) == 1 and "sendUpdates=all" in _verzoeken[0].full_url
          and json.loads(_verzoeken[0].data)["extendedProperties"]["private"]["agendawacht_uitgenodigd"] == _partner)
    check("de aparte schrijffunctie weigert online, een reeks en een ander adres zelf",
          len(_afgewezen) == 3 and len(_verzoeken) == 1)

# Driehoeksoverleg 9d: ook een reeds aanwezige gast, een tegelijk toegevoegde collega en een resource
# mogen nooit via sendUpdates=all meekrijgen. De tweede GET bootst een wijziging vlak voor de mailroute na.
if _inv_oud is not None:
    _open_oud, _mag_oud, _lees_oud, _patch_oud, _mensen_oud, _voor_oud, _toegang_oud = (
        _ur.urlopen, W.mag_schrijven, W._event, W._patch, W.organisatie.agenda_adressen,
        W.agendagasten_voor, W.agenda._toegang)
    _mail, _stil = [], []
    _staat = {
        "klant": {"attendees": [{"email": _partner}, {"email": "klant@voorbeeld.test"}]},
        "nieuw": {"attendees": [{"email": "klant@voorbeeld.test"}]},
        "collega": {"attendees": []},
        "alleen": {"attendees": [{"email": _partner}, {"email": W.WERKAGENDA, "organizer": True}]},
        "resource": {"attendees": [{"email": _partner}, {"email": "zaal@voorbeeld.test", "resource": True}]},
        "vers": {"attendees": [{"email": _partner}]},
    }
    _lezingen = {}

    def _lees_veilig(a, tok):
        eid = a["id"]
        _lezingen[eid] = _lezingen.get(eid, 0) + 1
        if eid == "vers" and _lezingen[eid] == 2:
            _staat[eid]["attendees"].append({"email": "klant@voorbeeld.test"})
        return copy.deepcopy(_staat[eid])

    def _patch_veilig(a, body, tok, **_kwargs):
        _stil.append((a["id"], copy.deepcopy(body)))
        _staat[a["id"]]["attendees"] = copy.deepcopy(body["attendees"])

    def _mail_veilig(req, timeout=0):
        body = json.loads(req.data)
        _mail.append((req.full_url, body))
        _staat[req.full_url.split("/events/")[-1].split("?")[0]]["extendedProperties"] = body["extendedProperties"]
        return type("R", (), {"read": lambda s: b"{}"})()

    _voor_veilig = lambda titel, regels=None, mensen=None: (
        {_partner, _ander} if "twee gasten" in titel else {_partner} if "partner erbij" in titel else set())
    try:
        _ur.urlopen, W.mag_schrijven, W._event, W._patch = _mail_veilig, (lambda kal: True), _lees_veilig, _patch_veilig
        W.organisatie.agenda_adressen = lambda *x, **k: {
            _partner: {"voornaam": "Partner", "naam": "Partner", "in_dienst": True},
            _ander: {"voornaam": "Collega", "naam": "Collega", "in_dienst": True}}
        W.agendagasten_voor, W.agenda._toegang = _voor_veilig, (lambda: "proef")
        _regels_veilig = W.agendagasten_zetten([
            _item("klant"), _item("nieuw", titel="!! [HA-KB] partner erbij", _agendagasten=[]),
            _item("collega", titel="!! [HA-KB] twee gasten", _agendagasten=[]),
            _item("alleen"), _item("resource"), _item("vers")])
        _mail_eerste = list(_mail)
        _staat_eerste = copy.deepcopy(_staat)
        _regels_later = W.agendagasten_zetten([_item("klant")])
        _staat["klant"]["attendees"] = [{"email": _partner}]
        _regels_na_verwijderen = W.agendagasten_zetten([_item("klant")])
        W.agendagasten_zetten([_item("klant")])
    finally:
        (_ur.urlopen, W.mag_schrijven, W._event, W._patch, W.organisatie.agenda_adressen,
         W.agendagasten_voor, W.agenda._toegang) = (
            _open_oud, _mag_oud, _lees_oud, _patch_oud, _mensen_oud, _voor_oud, _toegang_oud)
    _mail_ids_eerste = [url.split("/events/")[-1].split("?")[0] for url, _body in _mail_eerste]
    _mail_ids_alle = [url.split("/events/")[-1].split("?")[0] for url, _body in _mail]
    check("H1 partner met klant: geen mail, partner stil en voorstel zonder merk",
          "klant" not in _mail_ids_eerste and "nieuw" not in _mail_ids_eerste
          and any(eid == "nieuw" and _partner in {g["email"] for g in body["attendees"]} for eid, body in _stil)
          and all(W.UITNODIGMERK not in (_staat_eerste[eid].get("extendedProperties") or {}).get("private", {})
                  for eid in ("klant", "nieuw"))
          and sum("VOORSTEL" in r and "andere gasten" in r for r in _regels_veilig) >= 2,
          str(_mail_ids_eerste))
    check("H1 partner en ontbrekende collega in dezelfde ronde blijven zonder mail",
          "collega" not in _mail_ids_eerste and any(eid == "collega" and
          {_partner, _ander} <= {g["email"] for g in body["attendees"]} for eid, body in _stil)
          and W.UITNODIGMERK not in (_staat["collega"].get("extendedProperties") or {}).get("private", {}),
          str(_mail_ids_eerste))
    check("H1 alleen partner en Mehdi als organisator: precies één mail",
          _mail_ids_eerste.count("alleen") == 1 and
          _staat["alleen"]["extendedProperties"]["private"][W.UITNODIGMERK] == _partner,
          str(_mail_ids_eerste))
    check("H1 resource en nieuwe klant vlak voor mailroute: geen mail en voorstel",
          not {"resource", "vers"} & set(_mail_ids_eerste)
          and sum("VOORSTEL" in r and "andere gasten" in r for r in _regels_veilig) >= 4,
          str(_mail_ids_eerste))
    check("H1 na verdwijnen klant volgt eenmaal een uitnodiging",
          _mail_ids_alle.count("klant") == 1 and not any("uitnodiging aan" in r for r in _regels_later)
          and any("uitnodiging aan" in r for r in _regels_na_verwijderen), str(_mail_ids_alle))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

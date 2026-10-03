"""Grendel op de agendagasten (Mehdi, 03-10-2026, FR-102). Zonder netwerk en sleutels (ook CI).

Bewijst: een collega na 'Mehdi' in de titel wordt agendagast; Harmoniebouw brengt Catalin mee (ook als 'Karam'); een
klant met dezelfde voornaam elders in de titel niet; een naam die twee mensen aanwijst niet; zetten gaat zonder mail
(sendUpdates=none), bestaande gasten blijven, de reeks in de reeks, nooit op een afspraak van een ander, nooit iemand
weghalen; een agendagast telt niet als gast van buiten.
"""
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
_fn = _bron[_bron.index("def agendagasten_zetten"):_bron.index("def reistijd_zetten")]
check("zetten gaat via _patch (sendUpdates=none): geen eigen verzendroute, geen mail",
      "_patch(doel, {\"attendees\"" in _fn and "sendUpdates" not in _fn and "?sendUpdates=none" in _bron[_bron.index("def _patch"):_bron.index("def _patch") + 1500])

# een agendagast telt niet als gast van buiten
_src_ag = (HIER / "koppelingen" / "agenda.py").read_text(encoding="utf-8")
check("koppelingen/agenda.py telt een agendagast niet bij de gasten van buiten",
      'a["email"].lower() not in _intern' in _src_ag and "_intern = interne_adressen()" in _src_ag
      and W._van_mehdi({"kalender": W.WERKAGENDA, "maker": W.WERKAGENDA, "deelnemers": []}))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

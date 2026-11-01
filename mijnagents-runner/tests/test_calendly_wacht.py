"""Grendel op De Calendlywacht (T-0120, meting 01-10 tot 01-11-2026, groep agenda). Zonder Calendly, zonder Google,
zonder bord: de bronnen en het bord zijn nagebootst; de wacht schrijft nooit in Calendly.

- CL-3: een inactief type met een dubbele naam geeft geen signaal, en twee types met dezelfde naam in hetzelfde account
  ook niet; een actieve dubbel op twee accounts wel. Een type uit de vaste lijst in werkwijze/agenda-taken.json geeft geen
  signaal 'niet in het agenda-document'; een type daarbuiten wel. Een onleesbare lijst geeft een nood, geen vloed;
- CL-2: een boeking zonder afspraak in de agenda's van De Agendawacht geeft de vaste nood (wie mehdi) en de details in het
  signaal; met haar eigen afspraak niet (de afspraak die Calendly zette, of een met een kenmerk van Calendly); een andere
  afspraak op hetzelfde uur is geen bewijs; een boeking van gisteren wordt ook gezien; een mislukte of onvolledige
  agendalezing geeft geen vals alarm.

Verzonnen voorbeelden, geen echte namen. Draaien: python3 mijnagents-runner/tests/test_calendly_wacht.py
"""
import atexit
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "koppelingen")]
PROEF_HOME = tempfile.TemporaryDirectory(prefix="calendly-proef-")
atexit.register(PROEF_HOME.cleanup)
os.environ["HOME"] = PROEF_HOME.name
import calendly_wacht as CW  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print("ok   " + naam)
    else:
        fout += 1
        print("FOUT " + naam + (f" ({extra})" if extra else ""))


def typ(naam, actief=True, duur=30):
    return {"name": naam, "active": actief, "duration": duur}


# --- CL-3: alleen actieve types, alleen echt verschillende accounts, de vaste lijst bekende types
ACC = [{"naam": "Proefaccount A", "uri": "u:a", "email": "", "types": [typ("Proef: Klant"), typ("New Meeting", False),
                                                                      typ("New Meeting", False), typ("Proef: Dubbel")]},
       {"naam": "Proefaccount B", "uri": "u:b", "email": "", "types": [typ("Proef: Dubbel"), typ("Proef: Stil", False)]},
       {"naam": "Proefaccount C", "uri": "u:c", "email": "", "types": [typ("Proef: Stil")]}]
dub = CW.dubbele_types(ACC)
check("CL-3 twee inactieve types met dezelfde naam in hetzelfde account geven geen dubbel", "New Meeting" not in dub, dub)
check("CL-3 een naam die maar op een account actief is, is geen dubbel", "Proef: Stil" not in dub, dub)
check("CL-3 een actieve dubbel op twee accounts blijft gemeld", dub.get("Proef: Dubbel") == ["Proefaccount A", "Proefaccount B"], dub)
check("CL-3 dezelfde naam twee keer actief in hetzelfde account is geen dubbel over accounts",
      CW.dubbele_types([{"naam": "X", "uri": "u:x", "types": [typ("Proef: Twee"), typ("Proef: Twee")]}]) == {})

TAKEN = json.loads((ROOT / "werkwijze" / "agenda-taken.json").read_text(encoding="utf-8"))
bekend = CW.bekende_types()
check("CL-3 de lijst bekende types staat in werkwijze/agenda-taken.json (calendly_types.bekend)",
      bekend == set(TAKEN["calendly_types"]["bekend"]) and len(bekend) == 14, bekend)
check("CL-3 de vijf drukke types van oktober staan erin",
      {"TKN: Prospect", "UNABO prospect - Bundel", "UNABO prospect - EPB", "UNABO prospect - Scanning",
       "UNABO prospect - Stabiliteit"} <= bekend)
check("CL-3 de negen types van tabel J staan er nog in", {"HA: Klant", "HA: Prospect (Kennismaking)", "Intern Overleg"} <= bekend)
_pad = CW.AGENDA_TAKEN
try:
    CW.AGENDA_TAKEN = os.path.join(PROEF_HOME.name, "bestaat-niet.json")
    check("CL-3 een onleesbare lijst geeft None (dan geen controle, geen vloed)", CW.bekende_types() is None)
finally:
    CW.AGENDA_TAKEN = _pad


# --- de wacht als geheel, met nagebootste bronnen en bord
class NepAgent:
    laatste = None

    def __init__(self, naam):
        self.naam, self.items, self.logs, self.hartslagen = naam, [], [], []
        NepAgent.laatste = self

    def hartslag(self, status, taak="", detail="", voorstel=None, nood=None, sluiten=True):
        self.hartslagen.append({"status": status, "nood": list(nood or [])})

    def log(self, *a):
        self.logs.append(a)

    def log_verstuur(self):
        pass

    def klaarzet(self, items):
        self.items.extend(items)


NU = datetime.datetime.now(CW.BRUSSEL).replace(second=0, microsecond=0)


def boeking(dagen, uur=13, naam="Proef: Klant", status="active", google_id="g-proef"):
    lok = (NU + datetime.timedelta(days=dagen)).replace(hour=uur, minute=0)
    return {"name": naam, "status": status, "start_time": lok.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z"),
            "event_memberships": [{"user": "u:a"}], "calendar_event": {"kind": "google", "external_id": google_id},
            "_lok": lok.strftime("%Y-%m-%dT%H:%M")}


def ronde(accounts, boekingen, agenda):
    """agenda: (bewijs, ongelezen), of een uitzondering die de lezing gooit."""
    oud = (CW.verzamel, CW.bord.Agent, CW.agenda_bewijs)

    def lees(van, tot):
        if isinstance(agenda, Exception):
            raise agenda
        return agenda
    CW.verzamel, CW.bord.Agent, CW.agenda_bewijs = (lambda noden: (accounts, boekingen)), NepAgent, lees
    try:
        CW.main()
    finally:
        CW.verzamel, CW.bord.Agent, CW.agenda_bewijs = oud
    ag = NepAgent.laatste
    signaal = "\n".join(x["inhoud"] for x in ag.items)
    return ag.hartslagen[-1]["nood"], signaal


EEN = [{"naam": "Proefaccount A", "uri": "u:a", "email": "", "types": [typ("HA: Klant")]}]
b_morgen, b_gisteren, b_ver = boeking(1), boeking(-1, 10), boeking(-20, 9)
noden, signaal = ronde(EEN, [b_morgen], ({}, []))
check("CL-2 een boeking zonder afspraak geeft de vaste nood voor Mehdi",
      {"tekst": CW.ZONDER_NOOD, "wie": "mehdi"} in noden, noden)
check("CL-2 de details staan in het signaal, niet in de nood", "zonder afspraak" in signaal
      and f"{b_morgen['_lok'][:10]} {b_morgen['_lok'][11:]} Proef: Klant" in signaal
      and not any("Proef: Klant" in n["tekst"] for n in noden), signaal)
noden, signaal = ronde(EEN, [b_morgen], ({b_morgen["_lok"]: [{"id": "g-proef", "calendly": False}]}, []))
check("CL-2 met de afspraak die Calendly zette (zelfde Google-id) geen nood en geen signaal",
      not any(n["tekst"] == CW.ZONDER_NOOD for n in noden) and "zonder afspraak" not in signaal, (noden, signaal))
noden, signaal = ronde(EEN, [b_morgen], ({b_morgen["_lok"]: [{"id": "g-hernoemd", "calendly": True}]}, []))
check("CL-2 met een afspraak met een kenmerk van Calendly op het uur geen nood (ook een die Mehdi zelf zette en waarin hij "
      "de link van de boeking plakte)",
      not any(n["tekst"] == CW.ZONDER_NOOD for n in noden), noden)
noden, signaal = ronde(EEN, [b_morgen], ({b_morgen["_lok"]: [{"id": "g-iets-anders", "calendly": False}]}, []))
check("CL-2 een andere afspraak op hetzelfde uur is geen bewijs: de nood blijft, het signaal zegt waarom (Codex-toets 2)",
      {"tekst": CW.ZONDER_NOOD, "wie": "mehdi"} in noden and "een andere afspraak, zonder kenmerk van Calendly" in signaal,
      (noden, signaal))
noden, signaal = ronde(EEN, [dict(b_morgen, calendar_event=None)], ({b_morgen["_lok"]: [{"id": "", "calendly": False}]}, []))
check("CL-2 een boeking zonder Google-id en een afspraak zonder id of kenmerk: de nood blijft",
      {"tekst": CW.ZONDER_NOOD, "wie": "mehdi"} in noden, noden)
# Codex-toets 3: twee boekingen op hetzelfde uur, maar een afspraak
b_een, b_twee = dict(boeking(2, 11), uri="b:1", google_id="g-een"), dict(boeking(2, 11), uri="b:2")
b_een["calendar_event"], b_twee["calendar_event"] = {"external_id": "g-een"}, {"external_id": "g-twee"}
_uur = b_een["_lok"]
noden, signaal = ronde(EEN, [b_een, b_twee], ({_uur: [{"id": "g-een", "calendly": True}]}, []))
check("CL-2 twee boekingen op een uur en alleen de Google-afspraak van de eerste: de tweede blijft gemeld",
      {"tekst": CW.ZONDER_NOOD, "wie": "mehdi"} in noden and signaal.count(f"{_uur[:10]} {_uur[11:]}") == 1, (noden, signaal))
b_drie, b_vier = dict(b_een, uri="b:3", calendar_event=None), dict(b_twee, uri="b:4", calendar_event=None)
noden, signaal = ronde(EEN, [b_drie, b_vier], ({_uur: [{"id": "g-los", "calendly": True}]}, []))
check("CL-2 twee boekingen zonder Google-id en een afspraak met kenmerk: die bewijst er hoogstens een",
      {"tekst": CW.ZONDER_NOOD, "wie": "mehdi"} in noden and signaal.count(f"{_uur[:10]} {_uur[11:]}") == 1, (noden, signaal))
noden, signaal = ronde(EEN, [b_een, dict(b_vier, uri="b:5")], ({_uur: [{"id": "g-een", "calendly": True}]}, []))
check("CL-2 de eigen afspraak van een boeking bewijst geen andere boeking op hetzelfde uur",
      {"tekst": CW.ZONDER_NOOD, "wie": "mehdi"} in noden, (noden, signaal))
noden, signaal = ronde(EEN, [b_gisteren], ({}, []))
check("CL-2 een boeking van gisteren zonder afspraak wordt ook gezien",
      {"tekst": CW.ZONDER_NOOD, "wie": "mehdi"} in noden and b_gisteren["_lok"][:10] in signaal, (noden, signaal))
noden, signaal = ronde(EEN, [b_ver, boeking(1, 9, status="canceled")], ({}, []))
check("CL-2 een boeking van drie weken terug of een geannuleerde geeft geen nood",
      not any(n["tekst"] == CW.ZONDER_NOOD for n in noden), noden)
noden, signaal = ronde(EEN, [b_morgen], RuntimeError("Google antwoordt niet"))
check("CL-2 een mislukte agendalezing geeft geen vals alarm, wel een nood voor Claude",
      not any(n["tekst"] == CW.ZONDER_NOOD for n in noden) and "zonder afspraak" not in signaal
      and any(n["wie"] == "claude-code" and "agendacontrole mislukt" in n["tekst"] for n in noden), noden)
noden, signaal = ronde(EEN, [b_morgen], ({}, ["archief"]))
check("CL-2 een onvolledige agendalezing (archief niet gelezen) geeft geen vals alarm",
      not any(n["tekst"] == CW.ZONDER_NOOD for n in noden) and "zonder afspraak" not in signaal
      and any(n["wie"] == "claude-code" and "archief" in n["tekst"] for n in noden), noden)
check("CL-2 de nood draagt geen aantal of datum (N10: anders sluit hij nooit)",
      not any(ch.isdigit() for ch in CW.ZONDER_NOOD))

# CL-3 in de ronde: geen valse signalen meer, wel een echte dubbel en een onbekend type
ACC3 = [{"naam": "Proefaccount A", "uri": "u:a", "email": "", "types": [typ("TKN: Prospect"), typ("New Meeting", False),
                                                                       typ("New Meeting", False), typ("Proef: Nieuw")]},
        {"naam": "Proefaccount B", "uri": "u:b", "email": "", "types": [typ("HA: Klant")]},
        {"naam": "Proefaccount C", "uri": "u:c", "email": "", "types": [typ("HA: Klant")]}]
noden, signaal = ronde(ACC3, [], ({}, []))
check("CL-3 in de ronde: een type uit de lijst geeft geen signaal", "TKN: Prospect" not in signaal, signaal)
check("CL-3 in de ronde: twee inactieve 'New Meeting' in een account geven geen signaal", "New Meeting" not in signaal, signaal)
check("CL-3 in de ronde: een onbekend type en een actieve dubbel op twee accounts blijven gemeld",
      "type 'Proef: Nieuw' staat niet in het agenda-document" in signaal
      and "type 'HA: Klant' staat op meerdere accounts (Proefaccount B, Proefaccount C)" in signaal, signaal)
_pad = CW.AGENDA_TAKEN
try:
    CW.AGENDA_TAKEN = os.path.join(PROEF_HOME.name, "bestaat-niet.json")
    noden, signaal = ronde(ACC3, [], ({}, []))
finally:
    CW.AGENDA_TAKEN = _pad
check("CL-3 in de ronde: zonder lijst geen vloed 'niet in het agenda-document', wel een nood voor Claude",
      "niet in het agenda-document" not in signaal and any(n["wie"] == "claude-code" and "agenda-taken.json" in n["tekst"]
                                                           for n in noden), (noden, signaal))

# agenda_bewijs leest precies de agenda's van De Agendawacht met haar archief (nagebootste De Agendawacht)
import types  # noqa: E402
_nep = types.ModuleType("agenda_wacht")
_nep.KALENDERS = {"werk@proef.test": "werk", "prive@proef.test": "privé", "kind@proef.test": "Proefkind"}
_nep.PRIVE_KALENDERS = {"prive@proef.test", "kind@proef.test"}
_nep.ARCHIEF_FOUT = ""
_gelezen = []
_nep.afspraken = lambda van, tot, alleen_lezen=False: (_gelezen.append(("afspraken", van, tot, alleen_lezen)) or [
    {"kalender": "werk@proef.test", "id": "g1", "start": "2026-11-06T13:00:00+01:00", "omschrijving": "https://calendly.com/x"},
    {"kalender": "kind@proef.test", "fout": "403"}])
_nep.archief_afspraken = lambda van, tot, alleen_lezen=False: (_gelezen.append(("archief", van, tot, alleen_lezen)) or [
    {"kalender": "archief@proef.test", "id": "g2", "start": "2026-11-07T09:00:00+01:00", "_archief": "ZZ ARCHIEF proef"}])
_nep.is_calendly = lambda a: True       # de agenda alleen (een boekingsaccount) is geen kenmerk meer (Codex-toets 3)
_echt = sys.modules.get("agenda_wacht")
sys.modules["agenda_wacht"] = _nep
try:
    st, ong = CW.agenda_bewijs(-15, 15)
    check("CL-2 agenda_bewijs leest de agenda's en het archief van De Agendawacht, alleen lezend, ook terug, met kenmerk",
          _gelezen == [("afspraken", -15, 15, True), ("archief", -15, 15, True)]
          and st == {"2026-11-06T13:00": [{"id": "g1", "calendly": True}], "2026-11-07T09:00": [{"id": "g2", "calendly": False}]},
          (_gelezen, st))
    check("CL-2 een niet gelezen privé-agenda heet 'een privé-agenda', zonder haar naam", ong == ["een privé-agenda"], ong)
    _nep.ARCHIEF_FOUT = "archiefagenda niet gelezen: proef"
    check("CL-2 een archief dat niet gelezen werd, staat bij de ongelezen agenda's", "archief" in CW.agenda_bewijs(-15, 15)[1])
finally:
    if _echt is None:
        sys.modules.pop("agenda_wacht", None)
    else:
        sys.modules["agenda_wacht"] = _echt

# Met de echte De Agendawacht (Codex-toets 1): de late import werkt en leest via haar eigen lezer, met het archief.
# Google is nagebootst in koppelingen.agenda; niets gaat naar buiten.
sys.path[:0] = [str(ROOT / "planning")]
os.environ["BELLEN_UIT"] = "1"
os.environ.setdefault("AGENDA_WHATSAPP_WACHTRIJ", os.path.join(PROEF_HOME.name, "agenda-whatsapp.json"))
import organisatie as ORGANISATIE  # noqa: E402
ORGANISATIE.firmas = lambda maximum_uren=24: [{"code": "HARC", "code_contact": "HA", "code_agenda": "HA",
                                                "naam": "H-Architects", "land": "BE", "actief": True}]
import agenda_wacht as ECHT  # noqa: E402
_gelezen_echt = []


def _nep_lezer(van, tot, schrijf_leesstand=True):
    kal = os.environ.get("CONTRACTEN_KALENDERS", "")
    _gelezen_echt.append((kal, van, tot, schrijf_leesstand))
    if "archief" in kal:
        return [{"kalender": "archief@proef.test", "id": "a1", "titel": "proef", "start": "2026-11-07T09:00:00+01:00"}]
    return [{"kalender": ECHT.WERKAGENDA, "id": "w1", "titel": "proef", "start": "2026-11-06T13:00:00+01:00"}]


_oud_echt = (ECHT.agenda.afspraken, ECHT.agenda.kalendernamen)
ECHT.agenda.afspraken = _nep_lezer
ECHT.agenda.kalendernamen = lambda: {"archief@proef.test": "ZZ ARCHIEF proef", ECHT.WERKAGENDA: "werk"}
try:
    st, ong = CW.agenda_bewijs(-15, 15)
finally:
    ECHT.agenda.afspraken, ECHT.agenda.kalendernamen = _oud_echt
check("CL-2 met de echte De Agendawacht: haar agenda's en haar archief, alleen lezend (geen leesstand)",
      set(st) == {"2026-11-06T13:00", "2026-11-07T09:00"} and st["2026-11-06T13:00"][0]["id"] == "w1" and ong == []
      and len(_gelezen_echt) == 2
      and all(x[3] is False for x in _gelezen_echt) and "archief@proef.test" in _gelezen_echt[1][0]
      and ECHT.WERKAGENDA in _gelezen_echt[0][0], (st, ong, _gelezen_echt))

print(f"calendly-wacht: {ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

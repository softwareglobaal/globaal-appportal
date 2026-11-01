"""Grendel op De Calendlywacht (T-0120, meting 01-10 tot 01-11-2026, groep agenda). Zonder Calendly, zonder Google,
zonder bord: de bronnen en het bord zijn nagebootst; de wacht schrijft nooit in Calendly.

- CL-3: een inactief type met een dubbele naam geeft geen signaal, en twee types met dezelfde naam in hetzelfde account
  ook niet; een actieve dubbel op twee accounts wel. Een type uit de vaste lijst in werkwijze/agenda-taken.json geeft geen
  signaal 'niet in het agenda-document'; een type daarbuiten wel. Een onleesbare lijst geeft een nood, geen vloed.

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


def boeking(dagen, uur=13, naam="Proef: Klant", status="active"):
    lok = (NU + datetime.timedelta(days=dagen)).replace(hour=uur, minute=0)
    return {"name": naam, "status": status, "start_time": lok.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z"),
            "event_memberships": [{"user": "u:a"}], "_lok": lok.strftime("%Y-%m-%dT%H:%M")}


def ronde(accounts, boekingen, agenda):
    """agenda: (starts, ongelezen), of een uitzondering die de lezing gooit."""
    oud = (CW.verzamel, CW.bord.Agent, CW.google_agenda)
    CW.verzamel, CW.bord.Agent, CW.google_agenda = (lambda noden: (accounts, boekingen)), NepAgent, None
    try:
        CW.main()
    finally:
        CW.verzamel, CW.bord.Agent, CW.google_agenda = oud
    ag = NepAgent.laatste
    signaal = "\n".join(x["inhoud"] for x in ag.items)
    return ag.hartslagen[-1]["nood"], signaal


# CL-3 in de ronde: geen valse signalen meer, wel een echte dubbel en een onbekend type
ACC3 = [{"naam": "Proefaccount A", "uri": "u:a", "email": "", "types": [typ("TKN: Prospect"), typ("New Meeting", False),
                                                                       typ("New Meeting", False), typ("Proef: Nieuw")]},
        {"naam": "Proefaccount B", "uri": "u:b", "email": "", "types": [typ("HA: Klant")]},
        {"naam": "Proefaccount C", "uri": "u:c", "email": "", "types": [typ("HA: Klant")]}]
noden, signaal = ronde(ACC3, [], (set(), []))
check("CL-3 in de ronde: een type uit de lijst geeft geen signaal", "TKN: Prospect" not in signaal, signaal)
check("CL-3 in de ronde: twee inactieve 'New Meeting' in een account geven geen signaal", "New Meeting" not in signaal, signaal)
check("CL-3 in de ronde: een onbekend type en een actieve dubbel op twee accounts blijven gemeld",
      "type 'Proef: Nieuw' staat niet in het agenda-document" in signaal
      and "type 'HA: Klant' staat op meerdere accounts (Proefaccount B, Proefaccount C)" in signaal, signaal)
_pad = CW.AGENDA_TAKEN
try:
    CW.AGENDA_TAKEN = os.path.join(PROEF_HOME.name, "bestaat-niet.json")
    noden, signaal = ronde(ACC3, [], (set(), []))
finally:
    CW.AGENDA_TAKEN = _pad
check("CL-3 in de ronde: zonder lijst geen vloed 'niet in het agenda-document', wel een nood voor Claude",
      "niet in het agenda-document" not in signaal and any(n["wie"] == "claude-code" and "agenda-taken.json" in n["tekst"]
                                                           for n in noden), (noden, signaal))

print(f"calendly-wacht: {ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

"""Grendel op het foutenregister (werkwijze/foutenregister.json).

Een fout mag alleen 'opgelost' heten als er een grendel is die echt bestaat: een test, een
controle van de zelfcontrole of een vaste regel in de werkwijze. Deze test faalt zodra die
grendel verdwijnt, of zodra de zelfcontrole een controle gebruikt die nergens in het register
staat. Zo kan een fout niet stil terugkomen. Mandaat van Mehdi, 24-09-2026: "ik wil dat je
zelf leert ... kan je geen fout register maken".
"""
import json
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent
reg = json.loads((HIER / "werkwijze" / "foutenregister.json").read_text(encoding="utf-8"))
ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


VELDEN = ("id", "datum", "gevonden_door", "fout", "gevolg", "waarom_niet_gezien", "oorzaak",
          "oplossing", "grendel", "controle", "status")
ids = [f["id"] for f in reg["fouten"]]
check("elke fout heeft een uniek nummer", len(ids) == len(set(ids)))
for f in reg["fouten"]:
    mist = [v for v in VELDEN if v not in f or f[v] in ("", None)]
    check(f"{f['id']} heeft alle velden", not mist, f"mist: {mist}")
    check(f"{f['id']} heeft een geldige status", f["status"] in reg["statussen"], f["status"])
    g = f.get("grendel") or {}
    pad = HIER / g.get("waar", "")
    bestaat = pad.is_file() and g.get("tekst", "\0") in pad.read_text(encoding="utf-8")
    if f["status"] in ("opgelost", "bewaakt"):
        check(f"{f['id']} ({f['status']}) heeft een grendel die bestaat", bestaat,
              f"'{g.get('tekst')}' niet gevonden in {g.get('waar')}")

# elke controle van de zelfcontrole hangt aan een fout in het register
zc = (HIER / "zelfcontrole.py").read_text(encoding="utf-8")
gebruikt = set(re.findall(r'meld\("([a-z_]+)"', zc)) | set(re.findall(r'"controle": "([a-z_]+)"', zc))
gebruikt |= {"handkleur", "kleur"}      # via een voorwaardelijke expressie
gekend = {c for f in reg["fouten"] for c in f.get("controle") or []}
check("elke controle van de zelfcontrole staat in het register", gebruikt <= gekend, f"zonder nummer: {gebruikt - gekend}")
check("elke controle in het register bestaat in de zelfcontrole", gekend <= gebruikt, f"onbekend: {gekend - gebruikt}")
dubbel = [c for c in gekend if sum(c in (f.get("controle") or []) for f in reg["fouten"]) > 1]
check("een controle hangt aan precies een fout", not dubbel, str(dubbel))

# de lessen verwijzen naar bestaande fouten
for les in reg["lessen"]:
    check(f"les {les['id']} verwijst naar bestaande fouten", set(les["uit"]) <= set(ids), str(set(les["uit"]) - set(ids)))

# de afspraken (JSON) en de werkwijze kennen het register
taken = json.loads((HIER / "werkwijze" / "agenda-taken.json").read_text(encoding="utf-8"))
check("agenda-taken.json wijst naar het register", "foutenregister.json" in json.dumps(taken, ensure_ascii=False))
check("de werkwijze wijst naar het register", "foutenregister.json" in (HIER / "werkwijze" / "agenda-wacht.md").read_text(encoding="utf-8"))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

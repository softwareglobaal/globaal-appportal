"""Grendel: werkwijze/agenda-taken.json moet kloppen met de code.

De JSON is de afspraak met Mehdi. Deze test faalt zodra iemand een agenda, een
code of een kleurregel in de code verandert zonder de afspraak bij te werken.
"""
import json
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W

taken = json.loads((HIER / "werkwijze" / "agenda-taken.json").read_text(encoding="utf-8"))
ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


adressen = {a["adres"] for a in taken["agendas"]}
check("elke agenda uit de JSON staat in KALENDERS", adressen == set(W.KALENDERS),
      f"alleen in JSON: {adressen - set(W.KALENDERS)} | alleen in code: {set(W.KALENDERS) - adressen}")
import organisatie as O

bron = O.firmacodes()
check("de firmacodes komen uit organisatie.globaal.be",
      bool(bron) and taken["titelconventie"]["firmas"] == bron,
      f"bron heeft {len(bron)}, JSON heeft {len(taken['titelconventie']['firmas'])}")
check("de agent gebruikt diezelfde codes", W.FIRMACODES == bron)
check("elke oude code wijst naar een bestaande code",
      all(v in bron for v in W.OUDE_CODES.values()),
      str({k: v for k, v in W.OUDE_CODES.items() if v not in bron}))
check("elke afdeling op het bord hoort bij een bestaande code of is PRIVE",
      all(k in bron or k in W.NIET_FIRMA for k in W.FIRMA_AFDELING),
      str([k for k in W.FIRMA_AFDELING if k not in bron and k not in W.NIET_FIRMA]))
for code in bron:
    check(f"de titelregel herkent [{code}]", bool(W.CODE_RE.search(f"Mehdi: [{code}-IN] proef")))
for oudc, nieuwc in W.OUDE_CODES.items():
    d = W.lees_titel(f"Mehdi: [{oudc}-IN] proef")
    check(f"[{oudc}] wordt gelezen als {nieuwc}", d["firma"] == nieuwc and d["oude_code"] == oudc)
check("soorten gelijk", taken["titelconventie"]["soorten"] == W.SOORT)
check("types gelijk", taken["titelconventie"]["types"] == W.TYPES)


# de kleurregels uit de JSON naspelen op de echte functie
proeven = [
    ({"kalender": list(W.KALENDERS)[0]},
     {"reistijd": True, "buiten": False, "onzeker": False, "soort": ""}, "11"),
    ({"kalender": list(W.KALENDERS)[0]},
     {"reistijd": False, "buiten": True, "onzeker": False, "soort": "KB"}, "11"),
    ({"kalender": list(W.KALENDERS)[0]},
     {"reistijd": False, "buiten": False, "onzeker": True, "soort": "PO"}, "5"),
    ({"kalender": list(W.KALENDERS)[0]},
     {"reistijd": False, "buiten": False, "onzeker": False, "soort": "PO"}, "6"),
    ({"kalender": list(W.KALENDERS)[0]},
     {"reistijd": False, "buiten": False, "onzeker": False, "soort": "KO"}, "7"),
    ({"kalender": list(W.KALENDERS)[0]},
     {"reistijd": False, "buiten": False, "onzeker": False, "soort": "IN"}, "10"),
    ({"kalender": list(W.KALENDERS)[0]},
     {"reistijd": False, "buiten": False, "onzeker": False, "soort": ""}, ""),
]
for a, info, verwacht in proeven:
    uit = W.kleur_gewenst(a, info)
    check(f"kleur voor {info} is {verwacht or 'geen'}", uit == verwacht, f"kreeg {uit}")

check("de controle bestaat", (HIER / "controle_agenda.py").exists())
check("de archiefgrendel bestaat", (HIER / "tests" / "test_agenda_archief.py").exists())

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

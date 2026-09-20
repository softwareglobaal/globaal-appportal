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
check("elke agendacode wijst naar een bestaande firma",
      all(v in bron for v in W.AGENDACODE_NAAR_FIRMA.values()),
      str({k: v for k, v in W.AGENDACODE_NAAR_FIRMA.items() if v not in bron}))
check("elke afdeling op het bord hoort bij een bestaande code of is PRIVE",
      all(k in bron or k in W.NIET_FIRMA for k in W.FIRMA_AFDELING),
      str([k for k in W.FIRMA_AFDELING if k not in bron and k not in W.NIET_FIRMA]))
for code in bron:
    check(f"de titelregel herkent [{code}]", bool(W.CODE_RE.search(f"Mehdi: [{code}-IN] proef")))
for oudc, nieuwc in W.AGENDACODE_NAAR_FIRMA.items():
    d = W.lees_titel(f"Mehdi: [{oudc}-IN] proef")
    check(f"[{oudc}] hoort bij firma {nieuwc}", d["firma"] == nieuwc and d["agendacode"] == oudc)
check("soorten gelijk", taken["titelconventie"]["soorten"] == W.SOORT)
check("types gelijk", taken["titelconventie"]["types"] == W.TYPES)


# de kleurregels naspelen op de echte functie
WERK = "mehdiprivewerkagenda@gmail.com"
proeven = [
    (WERK, "Mehdi: !! [HARC-KB] WB 2310 - werf, Dorpstraat 5", "11", "rood, buiten voor het werk"),
    (WERK, "Mehdi: [HARC-KB] WB 2310 - werf zonder uitroeptekens", "11", "WB is per definitie buiten"),
    (WERK, "Mehdi: ?? [HARC-PB] PLB 2311 - nog niet vast", "5", "geel zolang het niet bevestigd is"),
    (WERK, "Mehdi: [HARC-KO] klant online", "7", "blauw"),
    (WERK, "Mehdi: [UNAB-PO] prospect online", "6", "oranje"),
    (WERK, "Mehdi: [ELEV-IN] intern", "10", "groen"),
    (WERK, "Mehdi: [UNAB-KO] EPB online", "7", "EPB is niet automatisch buiten"),
    (WERK, "Mehdi: !! [UNAB-KO] VC op de werf, Kerkstraat 1", "11", "met !! wel buiten"),
    (WERK, "Mehdi: afspraak zonder code", "", "geen kleur, dat is een fout"),
]
for kal, titel, verwacht, waarom in proeven:
    i = W.lees_titel(titel)
    uit = W.kleur_gewenst({"kalender": kal, "titel": titel}, i)
    check(f"{waarom}: {titel[:40]}", uit == verwacht, f"kreeg {uit or 'geen'}, verwacht {verwacht or 'geen'}")

for kal in W.AGENDA_VASTE_KLEUR:
    i = W.lees_titel("!! [PRIVE] iets buiten, Kerkstraat 1")
    check(f"vaste agendakleur blijft: {W.AGENDA_VASTE_KLEUR[kal]['naam']}",
          W.kleur_gewenst({"kalender": kal, "titel": "x"}, i) == "")
    check(f"maar buiten telt wel mee: {W.AGENDA_VASTE_KLEUR[kal]['naam']}", i["buiten"])

for ty in W.BUITEN_TYPES:
    i = W.lees_titel(f"Mehdi: [HARC-KB] {ty} 1234 - proef")
    check(f"{ty} is per definitie buiten", i["buiten"])
for ty in ("EPB", "VC", "STA", "SD"):
    i = W.lees_titel(f"Mehdi: [HARC-KO] {ty} 1234 - proef")
    check(f"{ty} is niet automatisch buiten", not i["buiten"])

check("de diensten in de JSON kloppen met de code",
      sorted(taken["buiten"]["diensten_altijd_buiten"]) == sorted(W.BUITEN_TYPES))
check("de reistijdbuffer in de JSON klopt", taken["reistijd"]["buffer_minuten"] == W.BUFFER_MIN)
check("de dagstop op Google Routes klopt", taken["reistijd"]["dagstop"]["aantal"] == W.ROUTES_DAGLIMIET)

check("de controle bestaat", (HIER / "controle_agenda.py").exists())
check("de archiefgrendel bestaat", (HIER / "tests" / "test_agenda_archief.py").exists())

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

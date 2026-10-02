"""Grendel op de codes van twee letters (Mehdi, 02-10-2026, goedgekeurd; 'Agendawacht - onderzoek en herstelvoorstel v1.1'
p. 9-11). Draait zonder netwerk en zonder sleutels, ook in de CI (.github/workflows/agenda-grendels.yml).

Bewijst: alle codes twee letters en uniek; oud lezen, nieuw schrijven; HA blijft HA; UB/TK met ST en EP/SC/VO
herkend; een tweede ronde verandert niets meer; bij bronuitval geen oude codes; B2B alleen naar XB/XO als buiten of
online vaststaat; de Calendly-duurcontrole vangt 20 minuten ook onder de nieuwe namen.
"""
import json
import os
import re
import sys
from pathlib import Path

os.environ["BELLEN_UIT"] = "1"      # een test belt nooit echt (FR-55)

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W            # noqa: E402
import calendly_wacht as CW         # noqa: E402
import verslagsoorten as VS         # noqa: E402

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
tc = taken["titelconventie"]
alle = list(tc["codes_twee_letters"]["firmas"]) + list(tc["types"]) + list(tc["soorten"])
check("alle codes in de master zijn precies twee hoofdletters", all(re.fullmatch(r"[A-Z]{2}", c) for c in alle),
      str([c for c in alle if not re.fullmatch(r"[A-Z]{2}", c)]))
check("geen code komt twee keer voor over firma's, opdrachten en soorten heen", len(alle) == len(set(alle)),
      str(sorted({c for c in alle if alle.count(c) > 1})))
check("58 codes: 21 firma's/categorieën, 26 opdrachten, 11 soorten", (len(tc["codes_twee_letters"]["firmas"]), len(tc["types"]), len(tc["soorten"])) == (21, 26, 11),
      str((len(tc["codes_twee_letters"]["firmas"]), len(tc["types"]), len(tc["soorten"]))))
check("de opdrachtcodes van de agent zijn die van de master", set(W.TYPES) == set(tc["types"]))
check("ZB/ZO blijven vrij voor het open voorstel 'zakelijke klant'", not {"ZB", "ZO"} & set(alle))

# elke firma heeft een agendacode van twee letters, ook zonder bron
check("elke firma heeft een agendacode van twee letters", all(re.fullmatch(r"[A-Z]{2}", W.titelcode(f)) for f in W.VALNET_AGENDACODES)
      and W.titelcode("UNAB") == "UB" and W.titelcode("HARC") == "HA" and W.titelcode("ALGE") == "AL")
_o = W.organisatie.agendacodes
W.organisatie.agendacodes = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bron onbereikbaar"))
try:
    _bron_weg = W.agendacodes()
finally:
    W.organisatie.agendacodes = _o
check("bij een bronstoring blijven het twee letters, nooit terug naar vier", _bron_weg.get("UNAB") == "UB" and _bron_weg.get("TKNB") == "TK"
      and all(len(v) == 2 for v in _bron_weg.values()))

# oud lezen, nieuw schrijven
VOORBEELDEN = [
    ("!! Mehdi: [HARC-KB] WB 2145 - wekelijks werfbezoek", "!! Mehdi: [HA-KB] WB 2145 - wekelijks werfbezoek"),
    ("Mehdi: [UNABO-PO] Stijn Hahn  - STA", "Mehdi: [UB-PO] Stijn Hahn  - ST"),
    ("Mehdi: [TKN-PO]: Levi Sonck", "Mehdi: [TK-PO]: Levi Sonck"),
    ("Mehdi, Matthew, Gul & Aqib: [TKNB-IN] AI+AT stabiliteit", "Mehdi, Matthew, Gul & Aqib: [TK-IN] AI stabiliteit"),
    ("!! Mehdi: [UNAB-KB] BS 46118 - Natasja Gerritsen, Koning Albertlaan 206", "!! Mehdi: [UB-KB] BS 46118 - Natasja Gerritsen, Koning Albertlaan 206"),
    ("Mehdi: [ELEVAIT-IN] AI+AT Siyan - Automation", "Mehdi: [EL-IN] AI Siyan - Automation"),
    ("Mehdi: [ALGE-LB] KBC ophalen", "Mehdi: [AL-LB] KBC ophalen"),
    ("Mehdi: [ENEF-IN] AI+AT", "Mehdi: [EE-IN] AI"),
    ("!! Mehdi: [HARC-KB] VOPL 2607 - Robin", "!! Mehdi: [HA-KB] VO 2607 - Robin"),
    ("!! Mehdi: [UNAB-KB] PLB - Peeters", "!! Mehdi: [UB-KB] PS - Peeters"),
]
for oud, verwacht in VOORBEELDEN:
    nieuw = W.codes_twee_letters(oud)
    check(f"'{oud[:40]}' -> twee letters", nieuw == verwacht, f"kreeg '{nieuw}'")
    check(f"  tweede ronde verandert niets ({verwacht[:30]})", W.codes_twee_letters(nieuw) == nieuw)
    check(f"  dezelfde firma en soort na de omzetting ({verwacht[:30]})",
          (W.lees_titel(oud)["firma"], W.lees_titel(oud)["soort"]) == (W.lees_titel(nieuw)["firma"], W.lees_titel(nieuw)["soort"]))
check("HA blijft HA", W.codes_twee_letters("!! Mehdi: [HA-KB] WB 2145") == "!! Mehdi: [HA-KB] WB 2145")
for t, firma, typ in (("Mehdi: [UB-KO] ST - X", "UNAB", "ST"), ("Mehdi: [TK-KO] ST - Y", "TKNB", "ST"), ("Mehdi: [UB-PO] EP - Z", "UNAB", "EP"),
                      ("!! Mehdi: [UB-KB] SC - Q", "UNAB", "SC"), ("!! Mehdi: [HA-KB] VO 2607", "HARC", "VO"), ("Mehdi: [UB-KO] STA - oud", "UNAB", "ST")):
    i = W.lees_titel(t)
    check(f"'{t}' leest als {firma} {typ}", (i["firma"], i["type"]) == (firma, typ), str((i["firma"], i["type"])))
check("SC, VO en PS zijn buiten; ST en EP niet per definitie", {"SC", "VO", "PS", "PL"} <= W.BUITEN_TYPES and not {"ST", "EP"} & W.BUITEN_TYPES)

# B2B -> XB / XO alleen als het vaststaat
check("B2B buiten (!!) wordt XB", W.codes_twee_letters("!! Mehdi: [HA-B2B] Stefan") == "!! Mehdi: [HA-XB] Stefan")
check("B2B online (Zoom) wordt XO", W.codes_twee_letters("Mehdi: [HA-B2B] Stefan", online=True) == "Mehdi: [HA-XO] Stefan")
check("B2B zonder bewijs blijft B2B (geen gok)", W.codes_twee_letters("Mehdi: [HA-B2B] Stefan") == "Mehdi: [HA-B2B] Stefan")
check("XO is lavendel zoals B2B, XB rood", W.kleur_gewenst({"kalender": W.WERKAGENDA}, W.lees_titel("Mehdi: [HA-XO] S")) == "1"
      and W.kleur_gewenst({"kalender": W.WERKAGENDA}, W.lees_titel("!! Mehdi: [HA-XB] S")) == "11")

# wat de agent zelf schrijft, draagt nooit een oude code
OUD = re.compile(r"\[(HARC|UNAB|UNABO|TKNB|TKN|ENEF|ELEV|ELEVAIT|HARM|CONT|HINV|ALGE|PRIVE)[-\]]")
geschreven = [W.titel_voorstel("!! Mehdi & Catalin: Harchitects-KB 2505")[0], W.titel_voorstel("?? Mehdi en Shaniel: Robby elevait-Leverancie online")[0],
              W.titel_voorstel("Mehdi: Nadine boekhouder online")[0], W.titel_voorstel("Mehdi & Pioter: Harchitects aannemer online 2405")[0],
              W.met_activiteit("Mehdi: [TK-IN] AI automatisering", "AI")]
check("wat de agent schrijft, draagt nooit een code van drie of vier letters", all(g and not OUD.search(g) for g in geschreven), str(geschreven))
check("vrije tekst 'Harchitects-KB 2505' wordt [HA-KB]", geschreven[0] == "!! Mehdi & Catalin: [HA-KB] 2505", str(geschreven[0]))

# Lara: [LA] telt als Lara voor de dagmarkering
check("[LA] is Lara: een markering houdt haar niet tegen",
      W.markering_tegen("!! Mehdi: [LA] Lara ophalen", "2026-10-02", [("Geen buiten afspraken", "buiten")]) is None)

# verslagagents herkennen de nieuwe codes
for typ, firma, soort in (("PS", "UNAB", "plaatsbeschrijving"), ("ST", "TKNB", "barsten-scheuren"), ("VO", "HARC", "werfverslag"), ("VC", "UNAB", "veiligheidscoordinatie")):
    check(f"verslagsoort voor type {typ}", VS.herken({"titel": f"!! Mehdi: [X-KB] {typ} - x", "firma": firma, "soort": "KB", "type": typ,
                                                     "buiten": True, "locatie": "Dorpstraat 1, 3000 Leuven"}) == soort)

# Calendly: een halfuur, ook onder de nieuwe namen
_dw = CW.duur_afwijkend([{"name": "UB prospect - EPB", "duration": 20, "active": True}, {"name": "TK: Prospect", "duration": 20, "active": True},
                         {"name": "UNABO: Offerte", "duration": 20, "active": True}, {"name": "TKN: Klant", "duration": 30, "active": True},
                         {"name": "HA: Prospect (Kennismaking)", "duration": 45, "active": True}])
check("de Calendly-duurcontrole vangt 20 minuten bij UB, TK en UNABO", len(_dw) == 3 and all("moet 30" in x for x in _dw), str(_dw))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

"""Grendels op De Felixwacht die zonder net draaien.

Vastgezet wat Mehdi op 03-10-2026 afsprak:
- het werkgebied is een vaste lijst postcodes zonder aantallen, en elke postcode verwijst naar de
  districtnamen zoals FelixArchief ze gebruikt (2040 zoekt in Berendrecht, Zandvliet en Lillo samen);
- een appartementsgebouw draagt vaak twee nummers: August Van de Wielelei 85 en 87 staan op een perceel
  en het dossier heet "85-87". Wie op 85 zoekt moet dat bereik vinden;
- een busnummer hoort niet in de zoekopdracht bij Geopunt ("85/101" -> 85, bus 101).
"""
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import adresregister as AR  # noqa: E402
import felixarchief as FA  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, info=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  goed  {naam}")
    else:
        fout += 1
        print(f"  FOUT  {naam} {info}")


# werkgebied: de bron van de waarheid
wg = json.load(open(FA.WERKGEBIED, encoding="utf-8"))
verwacht = {"2000", "2018", "2020", "2030", "2040", "2050", "2060", "2100", "2140", "2150", "2170", "2180",
            "2600", "2610", "2660"}
check("het werkgebied telt precies de vijftien postcodes van de stad Antwerpen", set(wg["postcodes"]) == verwacht,
      str(sorted(set(wg["postcodes"]) ^ verwacht)))
def _getallen(x):
    if isinstance(x, bool):
        return []
    if isinstance(x, (int, float)):
        return [x]
    if isinstance(x, dict):
        return [g for v in x.values() for g in _getallen(v)]
    if isinstance(x, list):
        return [g for v in x for g in _getallen(v)]
    return []


check("geen aantallen in het werkgebied (die veranderen, de postcodes niet)", _getallen(wg) == [], str(_getallen(wg)[:5]))
check("2040 zoekt in Berendrecht, Zandvliet en Lillo", {"Berendrecht", "Zandvliet", "Lillo"} <= set(FA.districten_voor("2040")))
check("Kiel valt onder 2020, district Antwerpen", "Kiel" in wg["postcodes"]["2020"].get("wijken", []) and FA.districten_voor("2020") == ["Antwerpen"])
check("Borsbeek hoort erbij sinds de fusie", FA.districten_voor("2150") == ["Borsbeek"])
check("Mortsel valt buiten het werkgebied", FA.districten_voor("2640") == [])

# huisnummers zoals FelixArchief ze schrijft
check("'85-87' is een bereik", FA.nummers("85-87") == [(85, 87)])
check("'75-77-79' is een lijst van drie nummers", FA.nummers("75-77-79") == [(75, 75), (77, 77), (79, 79)])
check("'293/295' is een lijst van twee nummers", FA.nummers("293/295") == [(293, 293), (295, 295)])
check("'12A' telt als 12", FA.nummers("12A") == [(12, 12)])
check("leeg is leeg", FA.nummers("") == [])
check("85 raakt '85-87' als bereik (het appartementsgebouw van 1965)", FA.raakt("85-87", ["85", "87"]) == "bereik")
check("91 raakt '89-95'", FA.raakt("89-95", ["91"]) == "bereik")
check("85 raakt '85' exact", FA.raakt("85", ["85"]) == "exact")
check("74A raakt '74A' exact", FA.raakt("74A", ["74", "74A"]) == "exact")
check("85 raakt '185' niet", FA.raakt("185", ["85"]) is None)
check("85 raakt '81-83' niet", FA.raakt("81-83", ["85"]) is None)
check("83 is een buur van 85, 84 niet (andere kant)", FA.is_buur("83", ["85"]) and not FA.is_buur("84", ["85"]))

# busnummers eraf voor Geopunt, maar bewaard
check("'85/101' wordt 85 met bus 101", AR.splits_bus("August van de Wielelei 85/101, 2100 Deurne") ==
      ("August van de Wielelei 85, 2100 Deurne", "101"))
check("'12 bus 3' wordt 12 met bus 3", AR.splits_bus("Kerkstraat 12 bus 3, 2000 Antwerpen") == ("Kerkstraat 12, 2000 Antwerpen", "3"))
check("'12b' blijft 12b (geen bus)", AR.splits_bus("Kerkstraat 12b, 2000 Antwerpen")[1] is None)
check("een bereik '35-73' blijft staan", AR.splits_bus("Leemputstraat 35-73, 2600 Antwerpen")[1] is None)

# het districtveld van FelixArchief sluit niets uit (Frans Brandsstraat 17 in Berendrecht staat als 'Antwerpen')
check("'Frans Brandsstraat ZN' is dezelfde straat", FA._zelfde_straat("Frans Brandsstraat ZN", "Frans Brandsstraat"))
check("hoofdletters en accenten tellen niet", FA._zelfde_straat("August van de Wielelei", "August Van de Wielelei"))
check("een andere straat blijft een andere straat", not FA._zelfde_straat("Frans Brandsstraatje", "Frans Brandsstraat"))
_r = FA._markeer_district([{"district": "Antwerpen"}, {"district": "Berendrecht-Zandvliet-Lillo"}], FA.districten_voor("2040"))
check("een afwijkend district wordt gemarkeerd, niet weggegooid", len(_r) == 2 and _r[0].get("district_afwijkend") and not _r[1].get("district_afwijkend"))

# mapnamen: het inventarisnummer en het busnummer blijven leesbaar
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("felix_wacht", os.path.join(RUNNER, "felix_wacht.py"))
FW = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FW)
check("'#' blijft in een mapnaam (627#23624)", "627#23624" in FW._veilig("627#23624 bouwen: koepel?"))
check("'85/101' wordt '85 bus 101' in een mapnaam", "85 bus 101" in FW._veilig("August van de Wielelei 85/101, 2100 Deurne"))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

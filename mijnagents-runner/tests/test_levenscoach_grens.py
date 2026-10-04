"""Grendel: De Levenscoach neemt geen locatiedagboek van voor de startgrens mee.

Gevonden bij de onafhankelijke controle van 05-10-2026: de weekspiegel van maandag
(7 dagen terug) las de oude telefoondagboeken van 28-09 tot 02-10 van het bord en
gaf ze aan het model. Opdracht v1.2: oude bewegingsdata komt niet via samenvattingen
terug in de analyse. Nagebootste bord-items; geen netwerk.

Draaien: python3 mijnagents-runner/tests/test_levenscoach_grens.py
"""
import os
import sys

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import levenscoach as L  # noqa: E402


def test_weekspiegel_neemt_geen_oud_locatiedagboek_mee():
    items = [{"van": "locatie-wacht", "soort": "locatie", "titel": "Locatielogboek 2026-09-30", "sleutel": "2026-09-30",
              "inhoud": "# oud telefoondagboek"},
             {"van": "locatie-wacht", "soort": "locatie", "titel": "Locatielogboek 2026-10-03", "sleutel": "2026-10-03",
              "inhoud": "# nieuw autodagboek"},
             {"van": "agenda-wacht", "soort": "dagplan", "titel": "Dagplan 2026-09-30", "sleutel": "2026-09-30",
              "inhoud": "afspraken"}]
    echt = L.bord.call
    L.bord.call = lambda pad, *a, **k: {"items": items}
    try:
        uit = L.bronnen_van(["2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03"])
    finally:
        L.bord.call = echt
    assert not any(it["soort"] == "locatie" for it in uit["2026-09-30"]), uit["2026-09-30"]
    assert [it["soort"] for it in uit["2026-09-30"]] == ["dagplan"], "de rest van de oude dag blijft"
    assert [it["soort"] for it in uit["2026-10-03"]] == ["locatie"], "het nieuwe dagboek moet blijven"


if __name__ == "__main__":
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("   geslaagd  %s" % naam)
            except AssertionError as e:
                fouten += 1
                print("   MISLUKT   %s: %s" % (naam, e))
    print("%d van de %d grendels mislukt" % (fouten, sum(1 for n in globals() if n.startswith("test_"))))
    sys.exit(1 if fouten else 0)

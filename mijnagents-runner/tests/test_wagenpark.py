"""Grendels op De Wagenparkwacht (vanaf 26-09-2026 in een eigen bestand, los van de mailtests).

Draait zonder netwerk: python3 tests/test_wagenpark.py
"""
import os
import sys
from datetime import date

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
sys.path.insert(0, HIER)
import wagenpark_wacht as W  # noqa: E402


def test_km_nazicht_en_tankcontrole():
    """Een km-stand buiten de reeks (tankkaart van 2BAS423 bij de stand van de Berlingo) telt niet en komt op de nazichtlijst."""
    v = {"plaat": "2BAS423", "merk_model": "Ford Transit Custom", "km": [
        {"datum": "2026-01-10", "km": 140000}, {"datum": "2026-05-20", "km": 147000, "bron": "tankkaart", "liters": 60},
        {"datum": "2026-05-26", "km": 8982, "bron": "tankkaart", "liters": 40}, {"datum": "2026-05-26", "km": 147858, "bron": "tankkaart", "liters": 75},
        {"datum": "2026-07-01", "km": 151000}]}
    schoon, verdacht = W.km_reeks(v)
    assert [x[1] for x in verdacht] == [8982], verdacht
    assert [x[1] for x in schoon] == [140000, 147000, 147858, 151000]
    tc, _ = W.tankcontrole(v)
    assert {"liters", "twee keer"} <= {x["soort"] for x in tc}, tc


def test_verbruik_per_tankbeurt_en_piek():
    """De liters van een beurt vullen de km sinds de vorige beurt; een maand met veel meer verbruik komt in de controle."""
    km = [{"datum": f"2026-0{m}-{d:02d}", "km": 10000 + 500 * i, "bron": "tankkaart", "liters": 40}
          for i, (m, d) in enumerate([(1, 5), (1, 20), (2, 5), (2, 20), (3, 5), (3, 20), (4, 5), (4, 20)])]
    km += [{"datum": "2026-05-05", "km": 14500, "bron": "tankkaart", "liters": 100}, {"datum": "2026-05-20", "km": 15000, "bron": "tankkaart", "liters": 100}]
    tc, verbruik = W.tankcontrole({"plaat": "X", "merk_model": "Ford Transit Custom", "km": km})
    assert dict(verbruik)["2026-02"] == 8.0, verbruik
    assert [x["wanneer"] for x in tc if x["soort"] == "verbruik"] == ["2026-05"], tc


def test_geen_kost_per_km_over_een_half_gemeten_jaar():
    v = {"plaat": "H", "status": "in gebruik", "onderhoud": [{"datum": "2026-02-01", "soort": "onderhoud", "bedrag": "5000,00"}],
         "km": [{"datum": "2026-03-01", "km": 100000}, {"datum": "2026-05-01", "km": 105000}]}
    k = W.kosten({"voertuigen": [v]}, [], date(2026, 9, 26))["H"]["2026"]
    assert k["km"] == 5000 and not k["km_zeker"] and "per_km" not in k, k


if __name__ == "__main__":
    fout = 0
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            try:
                f()
                print("  ok  ", n)
            except Exception as e:  # noqa: BLE001  ook een crash is een fout, niet alleen een assertion
                fout += 1
                print("  FOUT", n, type(e).__name__, e)
    sys.exit(1 if fout else 0)

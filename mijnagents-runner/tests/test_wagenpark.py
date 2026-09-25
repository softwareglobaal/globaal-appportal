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


def test_verbruikspiek():
    v = {"plaat": "X", "merk_model": "Citroën Berlingo", "brandstof_maanden": [
        {"maand": f"2026-0{i}", "liters": 70, "km_laagst": 1000 * i, "km_hoogst": 1000 * i + 1000} for i in range(1, 5)] +
        [{"maand": "2026-05", "liters": 150, "km_laagst": 5000, "km_hoogst": 6000}]}
    tc, verbruik = W.tankcontrole(v)
    assert [x["wanneer"] for x in tc if x["soort"] == "verbruik"] == ["2026-05"], tc


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

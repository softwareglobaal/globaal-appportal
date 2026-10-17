"""Een hernoemde of verdwenen bezoekmap (2145 en 2405, oktober 2026) mag geen oude groene stand houden.

python3 mijnagents-runner/tests/test_werf_hernoeming_12.py
"""
import os
import sys
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HIER), os.path.join(os.path.dirname(HIER), "koppelingen")]
import werfverslag_voorbereider as V  # noqa: E402

PM = "/Work All/x/2145 Vertommensberg 9"
OUD = PM + "/_00. Communication/2026-09-15 bezoek aannemer - werfbezoek 1"
NIEUW = PM + "/_00. Communication/2026-09-15 0734 HARC 2145 - aannemer Harmoniebouw - werfbezoek 1"


def rij(i, pad, datum="2026-09-15", stand="klaar voor verslag"):
    return {"id": i, "bezoekmap": pad, "datum": datum, "projectmap": PM, "stand": stand, "volgnr": 1}


class Hernoeming(unittest.TestCase):
    def test_hernoemde_map_gaat_mee_met_het_enige_bezoek_van_die_dag(self):
        uit = V.hernoemde_rijen([{"map": NIEUW, "datum": "2026-09-15"}], PM, [rij(1, OUD)], lambda p: False)
        self.assertEqual([r["id"] for r in uit[NIEUW]], [1])

    def test_bestaat_het_oude_pad_nog_dan_is_het_geen_hernoeming(self):
        uit = V.hernoemde_rijen([{"map": NIEUW, "datum": "2026-09-15"}], PM, [rij(1, OUD)], lambda p: True)
        self.assertEqual(uit, {})

    def test_twee_bezoeken_op_dezelfde_dag_geven_geen_koppeling(self):
        bezoeken = [{"map": NIEUW, "datum": "2026-09-15"}, {"map": NIEUW + " bis", "datum": "2026-09-15"}]
        self.assertEqual(V.hernoemde_rijen(bezoeken, PM, [rij(1, OUD)], lambda p: False), {})

    def test_andere_projectmap_of_dubbele_rij_telt_niet(self):
        ander = rij(2, "/Work All/y/9999 Elders/2026-09-15 bezoek")
        dubbel = rij(3, OUD, stand="dubbel na verhuis; opruiming wacht op Mehdi")
        self.assertEqual(V.hernoemde_rijen([{"map": NIEUW, "datum": "2026-09-15"}], PM, [ander, dubbel], lambda p: False), {})


class Verdwenen(unittest.TestCase):
    def test_verdwenen_map_zonder_opvolger_verliest_haar_groen(self):
        pb = rij(4, PM + "/_00. Communication/2026-06-06 bezoek klant - plaatsbezoek werf", datum="2026-06-06")
        self.assertEqual([r["id"] for r in V.verdwenen_rijen([{"map": NIEUW, "datum": "2026-09-15"}], [pb], lambda p: False)], [4])

    def test_gekoppelde_bestaande_of_dubbele_rij_is_niet_verdwenen(self):
        r = rij(1, OUD)
        self.assertEqual(V.verdwenen_rijen([{"map": NIEUW, "datum": "2026-09-15"}], [r], lambda p: False, [[r]]), [])
        self.assertEqual(V.verdwenen_rijen([], [rij(5, OUD)], lambda p: True), [])
        self.assertEqual(V.verdwenen_rijen([], [rij(6, OUD, stand="dubbel na verhuis")], lambda p: False), [])
        self.assertEqual(V.verdwenen_rijen([], [rij(7, OUD, stand=V.VERDWENEN)], lambda p: False), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)

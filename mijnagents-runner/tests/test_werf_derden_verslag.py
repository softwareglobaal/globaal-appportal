"""Een verslag van de aannemer in de map Werfverslagen is geen bezoek van Mehdi (2416, 22-10-2026).

Het eindverslag van Beba Construct ("2026-08-22  Aannemer - Eindverslag en oplevering van de werken.pdf") werd
als los verslag werfbezoek 6, waardoor het bezoek van 18-10 nummer 7 kreeg.

python3 mijnagents-runner/tests/test_werf_derden_verslag.py
"""
import os
import sys
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HIER), os.path.join(os.path.dirname(HIER), "koppelingen")]
import werfverslag_voorbereider as V  # noqa: E402

PM = "/Work All/01. H-A WORK/0 H-A Light projects/5. H-A light SITE VISITS/2416 Julien Breugelmansstraat 16"
WV = PM + "/4. Uitvoering & werfcontrole/4. Werfverslagen"


def map_(pad):
    return {".tag": "folder", "path_display": pad, "name": pad.rsplit("/", 1)[1]}


def bestand(pad):
    return {".tag": "file", "path_display": pad, "name": pad.rsplit("/", 1)[1]}


class DerdenVerslag(unittest.TestCase):
    def setUp(self):
        self._lijst = V.bronnen.lijst

    def tearDown(self):
        V.bronnen.lijst = self._lijst

    def bezoeken(self, items):
        V.bronnen.lijst = lambda pad, recursief=False: items
        return V.nummer_bezoeken(V.bezoeken_in(PM, "2416"), "")

    def test_eindverslag_van_de_aannemer_telt_niet_als_bezoek(self):
        uit = self.bezoeken([map_(WV), map_(WV + "/20260708"), map_(WV + "/20261018"),
                             bestand(WV + "/2026-08-22  Aannemer - Eindverslag en oplevering van de werken.pdf"),
                             bestand(WV + "/20260708/2026-07-08 Plaud transcript.txt"),
                             bestand(WV + "/20261018/2026-10-18 WB2416 Mike en Andrea - transcript.txt")])
        self.assertEqual([(b["datum"], b["nr_label"]) for b in uit], [("2026-07-08", "1"), ("2026-10-18", "2")])

    def test_eigen_los_verslag_blijft_een_bezoek(self):
        uit = self.bezoeken([map_(WV), bestand(WV + "/2026-09-01 werfverslag 2416-3.pdf"),
                             bestand(WV + "/2026-08-20 1430 HARC 2416 - aannemer - werfverslag.pdf")])
        self.assertEqual([b["datum"] for b in uit], ["2026-08-20", "2026-09-01"])
        self.assertTrue(all(b["bron_map"] == "los verslag" for b in uit))

    def test_verslag_van_een_derde_in_een_bezoekmap_is_een_notitie(self):
        uit = self.bezoeken([map_(WV), map_(WV + "/20260708"),
                             bestand(WV + "/20260708/2026-07-08 Aannemer - verslag rondgang.pdf"),
                             bestand(WV + "/20260708/2026-07-08 werfverslag 2416-5.docx")])
        self.assertEqual(uit[0]["verslagen"], ["2026-07-08 werfverslag 2416-5.docx"])
        self.assertIn("2026-07-08 Aannemer - verslag rondgang.pdf", uit[0]["notities"])

    def test_andere_derden_vooraan_tellen_ook_niet(self):
        for partij in ("Leverancier", "Bouwheer", "klant", "Onderaannemer", "Buren"):
            self.assertTrue(V.DERDE_AUTEUR_RE.match(f"2026-08-22 {partij} - verslag.pdf"), partij)
        self.assertFalse(V.DERDE_AUTEUR_RE.match("2026-08-22 werfverslag aannemer.pdf"))


if __name__ == "__main__":
    unittest.main()

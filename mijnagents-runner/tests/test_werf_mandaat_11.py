"""Het mandaat uit het werkwijzezaad gaat als kaartveld naar het bord."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "koppelingen")]
import werkwijze_naar_bord as zaden  # noqa: E402


class MandaatZaad(unittest.TestCase):
    def test_zet_levert_werkwijze_en_mandaat_samen(self):
        tekst = "# Werkwijze\n\n## Mandaat\n\nIk controleer de bron.\n\n## Stappen\n\nEen stap.\n"
        with tempfile.TemporaryDirectory() as mapnaam:
            pad = Path(mapnaam) / "werfverslag-dashboard.md"
            pad.write_text(tekst)
            aanroepen = []
            with patch.object(zaden, "zaadpad", return_value=str(pad)), \
                 patch.object(zaden.bord, "call", side_effect=lambda route, data: aanroepen.append(data) or {"ok": True}):
                self.assertEqual(zaden.zet("werfverslag-dashboard"), (True, ""))
        self.assertEqual(aanroepen[0]["mandaat"], "Ik controleer de bron.")
        self.assertEqual(aanroepen[0]["werkwijze"], tekst)


if __name__ == "__main__":
    unittest.main()

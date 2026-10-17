"""Beide runners sluiten hun ronde ook als een stap onverwacht faalt."""
from contextlib import contextmanager
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "koppelingen")]
import werfverslag_voorbereider as voorbereider  # noqa: E402
import werfverslag_schrijver as schrijver  # noqa: E402


class Rondes(unittest.TestCase):
    def test_fout_verlaat_de_ronde_bij_beide_runners(self):
        for module in (voorbereider, schrijver):
            meting = []

            @contextmanager
            def ronde(*args):
                meting.append("begin")
                try:
                    yield type("R", (), {"detail": ""})()
                finally:
                    meting.append("einde")

            with self.subTest(module=module.__name__), patch.object(module.ag, "ronde", ronde), \
                 patch.object(module, "main", side_effect=RuntimeError("fictieve fout")):
                with self.assertRaisesRegex(RuntimeError, "fictieve fout"):
                    module.run()
            self.assertEqual(meting, ["begin", "einde"])


if __name__ == "__main__":
    unittest.main()

"""De betaalde commandline-route vereist een reden van Mehdi; geen netwerk."""
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "koppelingen")]
import werfverslag_schrijver as schrijver  # noqa: E402


class CliMandaat(unittest.TestCase):
    def test_betaalde_stappen_zonder_vlag_weigeren_voor_bordaanroep(self):
        for stap in ("--proef", "--voorbereid"):
            with self.subTest(stap=stap), patch.object(sys, "argv", ["werfverslag_schrijver.py", stap, "9999", "1"]), \
                 patch.object(schrijver.bord, "call", side_effect=AssertionError("mag bord niet aanroepen")), \
                 contextlib.redirect_stderr(io.StringIO()) as melding:
                with self.assertRaises(SystemExit) as fout:
                    schrijver.main()
            self.assertEqual(fout.exception.code, 2)
            self.assertIn("--op-vraag-van-mehdi", melding.getvalue())

    def test_proef_met_reden_legt_bron_in_opdracht_vast(self):
        gezien = []
        antwoord = {"opdracht": {"id": 3, "status": "actief"}}
        with patch.object(sys, "argv", ["werfverslag_schrijver.py", "--proef", "9999", "1",
                                        "--op-vraag-van-mehdi", "Mehdi vroeg dit bezoek"]), \
             patch.object(schrijver.bord, "call", side_effect=lambda pad, payload: gezien.append((pad, payload)) or antwoord), \
             patch.object(schrijver.ag, "log"), patch.object(schrijver.ag, "log_verstuur"), \
             contextlib.redirect_stdout(io.StringIO()):
            schrijver.main()
        self.assertEqual(gezien[0][1]["bron"], "commandline")
        self.assertEqual(gezien[0][1]["reden"], "Mehdi vroeg dit bezoek")


if __name__ == "__main__":
    unittest.main()

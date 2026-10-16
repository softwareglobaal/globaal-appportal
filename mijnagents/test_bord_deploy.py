"""mijnagents/deploy.sh met nep-git, nep-docker en nep-curl in een tijdelijke HOME: .built pas na een gezond bord (CX7-1)."""
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parent / "deploy.sh"


def _uitvoerbaar(pad, tekst):
    pad.write_text(tekst)
    pad.chmod(pad.stat().st_mode | stat.S_IXUSR)


class BordDeployTest(unittest.TestCase):
    def draai(self, gezond, oud="oud"):
        t = Path(tempfile.mkdtemp(prefix="bord-deploy-"))
        (t / "bin").mkdir()
        (t / "appportal" / "mijnagents-data").mkdir(parents=True)
        (t / "appportal" / "mijnagents-data" / ".built").write_text(oud + "\n")
        _uitvoerbaar(t / "bin" / "git", "#!/bin/sh\necho nieuw\n")
        _uitvoerbaar(t / "bin" / "docker", '#!/bin/sh\necho "docker $*" >> "$HOME/docker.log"\n')
        antwoord = '{"agents":39,"ok":true}' if gezond else ""
        _uitvoerbaar(t / "bin" / "curl", f"#!/bin/sh\n[ -n '{antwoord}' ] || exit 7\necho '{antwoord}'\n")
        r = subprocess.run(["sh", str(SCRIPT)], env={**os.environ, "HOME": str(t), "PATH": f"{t}/bin:{os.environ['PATH']}",
                                                     "BORD_WACHT": "0", "BORD_POGINGEN": "3"}, capture_output=True, text=True, timeout=30)
        return r, (t / "appportal" / "mijnagents-data" / ".built").read_text().strip(), t

    def test_gezond_bord_wordt_gemarkeerd(self):
        r, built, t = self.draai(gezond=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(built, "nieuw")
        self.assertIn("compose up -d --build app-mijnagents", (t / "docker.log").read_text())

    def test_zakt_het_bord_dan_blijft_de_vorige_markering(self):
        r, built, _ = self.draai(gezond=False)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(built, "oud")
        self.assertIn("NIET gezond", r.stdout)

    def test_zelfde_revisie_doet_niets(self):
        r, built, t = self.draai(gezond=True, oud="nieuw")
        self.assertEqual(r.returncode, 0)
        self.assertFalse((t / "docker.log").exists())


if __name__ == "__main__":
    unittest.main()

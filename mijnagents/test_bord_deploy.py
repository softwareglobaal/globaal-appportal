"""mijnagents/deploy.sh met nep-git, nep-docker en nep-curl in een tijdelijke HOME (Codex CX7-1, CX8-1).

De nep-docker houdt bij welke image als :latest en :vorige getagd is en welke er draait; de nep-curl is gezond zolang
de draaiende image gezond is. Zo wordt nagekeken dat .built pas na een gezond bord verschuift, dat een ongezond nieuw bord
de vorige image terugkrijgt, en dat een mislukte revisie niet elke ronde opnieuw gebouwd wordt."""
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parent / "deploy.sh"

DOCKER = r'''#!/bin/sh
S="$HOME/staat"; mkdir -p "$S"
echo "docker $*" >> "$HOME/docker.log"
case "$1 $2" in
  "image inspect") [ -f "$S/latest" ] ;;
  "image tag") van=${3##*:}; naar=${4##*:}; cp "$S/$van" "$S/$naar" ;;
  "compose up")
    case "$*" in
      *--build*) [ -f "$HOME/bouw-faalt" ] && exit 1; echo nieuwe-image > "$S/latest"; cp "$S/latest" "$S/draait" ;;
      *) cp "$S/latest" "$S/draait" ;;
    esac ;;
esac
'''

CURL = r'''#!/bin/sh
draait=$(cat "$HOME/staat/draait" 2>/dev/null || echo geen)
if [ "$draait" = oude-image ] || { [ "$draait" = nieuwe-image ] && [ -f "$HOME/nieuw-gezond" ]; }; then
  echo '{"agents":39,"app":"Mehdi Agents","ok":true}'
else
  exit 7
fi
'''


def _uitvoerbaar(pad, tekst):
    pad.write_text(tekst)
    pad.chmod(pad.stat().st_mode | stat.S_IXUSR)


class BordDeployTest(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix="bord-deploy-"))
        t = self.t
        (t / "bin").mkdir()
        (t / "appportal" / "mijnagents-data").mkdir(parents=True)
        (t / "appportal" / "mijnagents-data" / ".built").write_text("oud\n")
        (t / "staat").mkdir()
        (t / "staat" / "latest").write_text("oude-image\n")
        (t / "staat" / "draait").write_text("oude-image\n")
        _uitvoerbaar(t / "bin" / "git", "#!/bin/sh\necho nieuw\n")
        _uitvoerbaar(t / "bin" / "docker", DOCKER)
        _uitvoerbaar(t / "bin" / "curl", CURL)

    def draai(self):
        t = self.t
        return subprocess.run(["sh", str(SCRIPT)], env={**os.environ, "HOME": str(t), "PATH": f"{t}/bin:{os.environ['PATH']}",
                                                        "BORD_WACHT": "0", "BORD_POGINGEN": "3"}, capture_output=True, text=True, timeout=30)

    def lees(self, *pad):
        p = self.t.joinpath(*pad)
        return p.read_text().strip() if p.exists() else None

    def test_gezond_nieuw_bord_wordt_gemarkeerd(self):
        (self.t / "nieuw-gezond").write_text("1")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.lees("appportal", "mijnagents-data", ".built"), "nieuw")
        self.assertEqual(self.lees("staat", "draait"), "nieuwe-image")
        self.assertEqual(self.lees("staat", "vorige"), "oude-image")

    def test_ongezond_nieuw_bord_krijgt_de_vorige_image_terug_en_wordt_niet_herhaald(self):
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("vorige image teruggezet en gezond", r.stdout)
        self.assertEqual(self.lees("staat", "draait"), "oude-image")          # het werkende bord draait weer
        self.assertEqual(self.lees("appportal", "mijnagents-data", ".built"), "oud")
        self.assertEqual(self.lees("appportal", "mijnagents-data", ".mislukt"), "nieuw")
        log = self.lees("docker.log")
        r = self.draai()                                                      # volgende cronronde: niet opnieuw bouwen
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.lees("docker.log"), log)

    def test_mislukte_bouw_laat_het_bord_draaien(self):
        (self.t / "bouw-faalt").write_text("1")
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.lees("staat", "draait"), "oude-image")
        self.assertEqual(self.lees("appportal", "mijnagents-data", ".mislukt"), "nieuw")

    def test_zelfde_revisie_doet_niets(self):
        (self.t / "appportal" / "mijnagents-data" / ".built").write_text("nieuw\n")
        r = self.draai()
        self.assertEqual(r.returncode, 0)
        self.assertIsNone(self.lees("docker.log"))


if __name__ == "__main__":
    unittest.main()

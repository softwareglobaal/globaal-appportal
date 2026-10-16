"""mijnagents/deploy.sh met nep-git, nep-docker en nep-curl in een tijdelijke HOME (Codex CX7-1, CX8-1, CX9-1/2/3, CX10).

De nep-docker houdt bij welke image als :latest en :vorige getagd is en welke image de container draait; de nep-curl
is gezond zolang de draaiende image in het bestand `gezond` staat. Vlagbestanden in HOME laten een stap falen: `X` altijd,
`X.1` één keer. Zo wordt nagekeken dat .built pas na een gezond bord verschuift, dat een ongezond of niet gebouwd bord de
vorige image terugkrijgt, dat twee rondes elkaar niet inhalen, dat tagfouten en afgebroken rondes hersteld worden, en
dat een mislukte revisie wacht maar na de afkoeling of een vrijgave opnieuw kan.

flock, timeout en dash zijn op de CI (Ubuntu) en op de VM de echte; op een Mac zonder flock of timeout vult de test een
kleine vervanger in met dezelfde werking (flock(2) op het geërfde fd, procesgroep stoppen na de limiet)."""
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parent / "deploy.sh"
SH = shutil.which("dash") or "sh"  # op de VM is /bin/sh dash

GIT = r'''#!/bin/sh
case "$1" in
  rev-parse) [ -f "$HOME/git-faalt" ] && exit 128; cat "$HOME/revisie" ;;
  status) cat "$HOME/werkboom" 2>/dev/null; exit 0 ;;
  *) exit 1 ;;
esac
'''

DOCKER = r'''#!/bin/sh
S="$HOME/staat"
echo "docker $*" >> "$HOME/docker.log"
faalt() { if [ -f "$HOME/$1.1" ]; then rm -f "$HOME/$1.1"; return 0; fi; [ -f "$HOME/$1" ]; }
id_van() {
  case "$1" in
    sha256:*) echo "$1" ;;
    *:*) [ -f "$S/tag-${1##*:}" ] && cat "$S/tag-${1##*:}" ;;
    *) [ -f "$S/tag-latest" ] && cat "$S/tag-latest" ;;
  esac
}
case "$1" in
  version) if faalt docker-weg; then exit 1; fi; echo 29.5.3 ;;
  inspect) [ -f "$S/draait" ] && cat "$S/draait" ;;
  image)
    case "$2" in
      inspect) id_van "$5" ;;
      tag) if faalt "tag-${4##*:}"; then exit 1; fi; id=$(id_van "$3") || exit 1; echo "$id" > "$S/tag-${4##*:}" ;;
      *) exit 1 ;;
    esac ;;
  compose)
    case "$*" in
      *--build*)
        if [ -f "$HOME/bouw-wacht" ]; then
          touch "$HOME/bouw-bezig"
          while [ ! -f "$HOME/ga" ]; do sleep 0.05; done
        fi
        if faalt bouw-hangt; then sleep 60; fi
        if [ -f "$HOME/bouw-achtergrond" ]; then sleep 30 >/dev/null 2>&1 & echo $! > "$HOME/achtergrond.pid"; fi
        if faalt bouw-breekt-oud; then grep -vx 'sha256:oud' "$HOME/gezond" > "$HOME/gezond.tmp"; mv "$HOME/gezond.tmp" "$HOME/gezond"; fi
        if faalt bouw-faalt; then exit 1; fi
        nieuw="sha256:$(cat "$HOME/revisie")"
        echo "$nieuw" > "$S/tag-latest"
        [ -f "$HOME/bouw-zonder-herstart" ] || echo "$nieuw" > "$S/draait"
        if faalt start-faalt; then exit 1; fi
        ;;
      *--force-recreate*)
        if faalt herstart-faalt; then exit 1; fi
        cp "$S/tag-latest" "$S/draait" ;;
      *) exit 1 ;;
    esac ;;
  *) exit 1 ;;
esac
'''

CURL = r'''#!/bin/sh
d=$(cat "$HOME/staat/draait" 2>/dev/null) || exit 7
grep -qxF "$d" "$HOME/gezond" 2>/dev/null || exit 7
echo '{"agents":39,"app":"Mehdi Agents","ok":true}'
'''

FLOCK = r'''#!/usr/bin/env python3
import fcntl, sys
fd = int([a for a in sys.argv[1:] if not a.startswith("-")][0])
try:
    fcntl.flock(fd, fcntl.LOCK_EX | (fcntl.LOCK_NB if "-n" in sys.argv[1:] else 0))
except BlockingIOError:
    sys.exit(1)
'''

TIMEOUT = r'''#!/usr/bin/env python3
import os, signal, subprocess, sys
a = sys.argv[1:]
na = 1.0
if a[0] == "-k":
    na, a = float(a[1]), a[2:]
p = subprocess.Popen(a[1:], start_new_session=True, close_fds=False)
try:
    sys.exit(p.wait(timeout=float(a[0])))
except subprocess.TimeoutExpired:
    os.killpg(p.pid, signal.SIGTERM)
    try:
        p.wait(timeout=na)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
    sys.exit(124)
'''


def _uitvoerbaar(pad, tekst):
    pad.write_text(tekst)
    pad.chmod(pad.stat().st_mode | stat.S_IXUSR)


class BordDeployTest(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix="bord-deploy-"))
        self.addCleanup(shutil.rmtree, self.t, ignore_errors=True)
        self.addCleanup(self._achtergrond_stoppen)
        t = self.t
        (t / "bin").mkdir()
        (t / "appportal" / "mijnagents-data").mkdir(parents=True)
        (t / "staat").mkdir()
        self.zet("appportal/mijnagents-data/.built", "oud")
        self.zet("revisie", "nieuw")
        self.zet("staat/tag-latest", "sha256:oud")
        self.zet("staat/draait", "sha256:oud")
        self.zet("gezond", "sha256:oud")
        _uitvoerbaar(t / "bin" / "git", GIT)
        _uitvoerbaar(t / "bin" / "docker", DOCKER)
        _uitvoerbaar(t / "bin" / "curl", CURL)
        if not shutil.which("flock"):
            _uitvoerbaar(t / "bin" / "flock", FLOCK)
        if not shutil.which("timeout"):
            _uitvoerbaar(t / "bin" / "timeout", TIMEOUT)

    def _achtergrond_stoppen(self):
        pid = self.lees("achtergrond.pid")
        if pid:
            try:
                os.kill(int(pid), signal.SIGKILL)
            except (ProcessLookupError, ValueError):
                pass

    def env(self, **extra):
        return {**os.environ, "HOME": str(self.t), "PATH": f"{self.t}/bin:{os.environ['PATH']}",
                "BORD_WACHT": "0", "BORD_POGINGEN": "3", **extra}

    def draai(self, **extra):
        return subprocess.run([SH, str(SCRIPT)], env=self.env(**extra), capture_output=True, text=True, timeout=60)

    def zet(self, pad, tekst):
        (self.t / pad).write_text(tekst + "\n")

    def gezond(self, *ids):
        self.zet("gezond", "\n".join(ids))

    def lees(self, pad):
        p = self.t / pad
        return p.read_text().strip() if p.exists() else None

    def data(self, naam):
        return self.lees(f"appportal/mijnagents-data/{naam}")

    def docker(self):
        return self.lees("docker.log") or ""

    def mislukt(self):
        rev, tijd, n = self.data(".mislukt").split()
        return rev, int(tijd), int(n)

    # --- gewone uitrol ---------------------------------------------------------------------------------------------

    def test_zelfde_revisie_doet_niets(self):
        self.zet("appportal/mijnagents-data/.built", "nieuw")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.docker(), "")

    def test_gezond_nieuw_bord_wordt_gemarkeerd(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.data(".built"), "nieuw")
        self.assertEqual(self.lees("staat/draait"), "sha256:nieuw")
        self.assertEqual(self.lees("staat/tag-vorige"), "sha256:oud")
        self.assertIsNone(self.data(".mislukt"))
        self.assertIsNone(self.data(".herstel"))
        self.assertIn("deployed (nieuw)", r.stdout)
        self.assertNotIn("--force-recreate", self.docker())

    def test_eerste_uitrol_zonder_image(self):
        for f in ("staat/tag-latest", "staat/draait"):
            (self.t / f).unlink()
        self.gezond("sha256:nieuw")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.data(".built"), "nieuw")

    # --- mislukte uitrol en terugrol (CX7-1, CX8-1) ------------------------------------------------------------------

    def test_ongezond_nieuw_bord_krijgt_de_vorige_image_terug_en_wacht_de_afkoeling(self):
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("vorige image sha256:oud teruggezet en gezond", r.stdout)
        self.assertEqual(self.lees("staat/draait"), "sha256:oud")  # het werkende bord draait weer
        self.assertEqual(self.lees("staat/tag-latest"), "sha256:oud")
        self.assertIn("--force-recreate", self.docker())
        self.assertEqual(self.data(".built"), "oud")
        self.assertEqual(self.mislukt()[::2], ("nieuw", 1))
        self.assertIsNone(self.data(".herstel"))
        log = self.docker()
        r = self.draai()  # volgende cronronde: niet opnieuw bouwen
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.docker(), log)

    def test_mislukte_bouw_laat_het_bord_draaien_zonder_herstart(self):
        self.zet("bouw-faalt", "1")
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.lees("staat/draait"), "sha256:oud")
        self.assertNotIn("--force-recreate", self.docker())  # niets te herstarten: de container draaide de oude image
        self.assertEqual(self.mislukt()[0], "nieuw")
        self.assertIsNone(self.data(".herstel"))

    def test_container_start_faalt_zet_vorige_terug(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        self.zet("start-faalt", "1")
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("UITROL MISLUKT bij het bouwen", r.stdout)
        self.assertEqual(self.lees("staat/draait"), "sha256:oud")
        self.assertEqual(self.data(".built"), "oud")

    def test_gezondheid_van_de_oude_container_telt_niet_voor_de_nieuwe_image(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        self.zet("bouw-zonder-herstart", "1")  # gebouwd, maar de container draait nog de oude image
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("UITROL MISLUKT bij de gezondheidscontrole", r.stdout)
        self.assertEqual(self.data(".built"), "oud")
        self.assertEqual(self.lees("staat/tag-latest"), "sha256:oud")

    # --- één ronde tegelijk (CX9-1) ------------------------------------------------------------------------------------

    def test_twee_overlappende_rondes(self):
        self.zet("bouw-wacht", "1")
        a = subprocess.Popen([SH, str(SCRIPT)], env=self.env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            grens = time.time() + 20
            while not (self.t / "bouw-bezig").exists():
                self.assertLess(time.time(), grens, "ronde A kwam niet aan de bouw")
                time.sleep(0.05)
            voor = self.docker()
            r = self.draai()  # ronde B start terwijl A bouwt
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(self.docker(), voor, "ronde B mag docker niet aanraken")
            self.assertEqual(self.lees("staat/tag-vorige"), "sha256:oud")
            self.zet("ga", "1")
            uit, fout = a.communicate(timeout=30)
        finally:
            if a.poll() is None:
                a.kill()
        self.assertEqual(a.returncode, 1, uit + fout)  # nieuw is niet gezond: A rolt zelf terug
        self.assertEqual(self.lees("staat/draait"), "sha256:oud")
        self.assertEqual(self.lees("staat/tag-vorige"), "sha256:oud")

    def test_slot_gaat_niet_mee_naar_docker(self):
        self.gezond("sha256:oud", "sha256:nieuw", "sha256:nieuwer")
        self.zet("bouw-achtergrond", "1")  # de nep-docker laat een proces achter, zoals een plugin dat blijft hangen
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.lees("achtergrond.pid"))
        (self.t / "bouw-achtergrond").unlink()
        self.zet("revisie", "nieuwer")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.data(".built"), "nieuwer", "het achtergebleven proces hield het slot vast")

    # --- tagfouten (CX9-2) ---------------------------------------------------------------------------------------------

    def test_tagfout_voor_de_bouw_bouwt_niet_en_blokkeert_niet(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        self.zet("tag-vorige.1", "1")
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("geen bouw in deze ronde", r.stdout)
        self.assertNotIn("--build", self.docker())
        self.assertIsNone(self.data(".mislukt"))
        self.assertIsNone(self.data(".herstel"))
        r = self.draai()  # de volgende ronde probeert meteen opnieuw
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.data(".built"), "nieuw")

    def test_tagfout_bij_de_terugrol_wordt_de_volgende_ronde_hersteld(self):
        self.zet("tag-latest.1", "1")
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("terugzetten mislukt", r.stdout)
        self.assertEqual(self.lees("staat/draait"), "sha256:nieuw")  # het ongezonde bord draait nog
        self.assertEqual(self.data(".herstel"), "sha256:oud nieuw 1")
        log = self.docker()
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("eerst terug naar sha256:oud", r.stdout)
        self.assertEqual(self.lees("staat/draait"), "sha256:oud")
        self.assertIsNone(self.data(".herstel"))
        self.assertNotIn("--build", self.docker()[len(log):])  # herstel, geen nieuwe bouw van dezelfde revisie
        self.assertEqual(self.mislukt()[::2], ("nieuw", 1))

    def test_afgebroken_ronde_wordt_eerst_hersteld(self):
        self.zet("staat/tag-latest", "sha256:nieuw")
        self.zet("staat/draait", "sha256:nieuw")
        self.zet("appportal/mijnagents-data/.herstel", "sha256:oud nieuw 2")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.lees("staat/draait"), "sha256:oud")
        self.assertIsNone(self.data(".herstel"))
        self.assertEqual(self.mislukt()[::2], ("nieuw", 2))
        self.assertNotIn("--build", self.docker())

    def test_herstelmarkering_van_een_geslaagde_uitrol_wordt_opgeruimd(self):
        self.zet("appportal/mijnagents-data/.built", "nieuw")
        self.zet("appportal/mijnagents-data/.herstel", "sha256:oud nieuw 1")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIsNone(self.data(".herstel"))
        self.assertEqual(self.docker(), "")

    def test_vorige_ook_ongezond_blijft_herstellen_maar_een_nieuwe_revisie_mag(self):
        self.zet("bouw-breekt-oud.1", "1")  # tijdens de bouw valt ook de oude image om
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("OOK DE VORIGE IMAGE IS NIET GEZOND", r.stdout)
        self.assertEqual(self.data(".herstel"), "sha256:oud nieuw 1")
        r = self.draai()  # dezelfde revisie: alleen herstellen, niet opnieuw bouwen
        self.assertEqual(r.returncode, 1)
        self.assertIn("HERSTEL MISLUKT", r.stdout)
        self.assertEqual(self.docker().count("--build"), 1)
        self.zet("revisie", "nieuwer")  # een herstelde revisie wordt wel gebouwd
        self.gezond("sha256:nieuwer")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.data(".built"), "nieuwer")
        self.assertIsNone(self.data(".herstel"))
        self.assertIsNone(self.data(".mislukt"))

    # --- afkoeling en vrijgave (CX9-3) ----------------------------------------------------------------------------------

    def test_tijdelijke_storing_krijgt_herkansing_na_afkoeling(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        self.zet("bouw-faalt.1", "1")
        self.assertEqual(self.draai().returncode, 1)
        rev, tijd, n = self.mislukt()
        self.assertEqual((rev, n), ("nieuw", 1))
        log = self.docker()
        self.assertEqual(self.draai().returncode, 0)  # binnen de afkoeling: niets
        self.assertEqual(self.docker(), log)
        self.zet("appportal/mijnagents-data/.mislukt", f"nieuw {tijd - 1801} 1")
        r = self.draai()  # na 30 min: tweede poging, en die slaagt
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.data(".built"), "nieuw")
        self.assertIsNone(self.data(".mislukt"))

    def test_afkoeling_verdubbelt_tot_het_maximum(self):
        nu = int(time.time())
        for verstreken, n, bouwt in ((1700, 1, False), (1900, 1, True), (3500, 2, False), (3700, 2, True),
                                     (14300, 4, False), (21500, 9, False), (21700, 9, True)):
            with self.subTest(verstreken=verstreken, n=n):
                (self.t / "docker.log").unlink(missing_ok=True)
                self.zet("appportal/mijnagents-data/.mislukt", f"nieuw {nu - verstreken} {n}")
                r = self.draai()
                self.assertEqual("--build" in self.docker(), bouwt, r.stdout + r.stderr)
                if bouwt:
                    self.assertEqual(self.mislukt()[::2], ("nieuw", n + 1))
                    self.assertIn(f"poging {n + 1}", r.stdout)

    def test_vrijgave_door_mislukt_weg_te_halen(self):
        self.assertEqual(self.draai().returncode, 1)
        self.gezond("sha256:oud", "sha256:nieuw")
        (self.t / "appportal" / "mijnagents-data" / ".mislukt").unlink()
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.data(".built"), "nieuw")

    def test_nieuwe_revisie_wacht_niet_op_afkoeling(self):
        self.assertEqual(self.draai().returncode, 1)
        self.zet("revisie", "nieuwer")
        self.gezond("sha256:oud", "sha256:nieuwer")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.data(".built"), "nieuwer")

    # --- tijdslimieten en storingen vóór de bouw -------------------------------------------------------------------

    def test_tijdslimiet_op_de_bouw(self):
        self.zet("bouw-hangt", "1")
        begin = time.time()
        r = self.draai(BORD_BOUW_LIMIET="1")
        self.assertLess(time.time() - begin, 20)
        self.assertEqual(r.returncode, 1)
        self.assertIn("UITROL MISLUKT bij het bouwen", r.stdout)
        self.assertEqual(self.lees("staat/draait"), "sha256:oud")
        self.assertEqual(self.mislukt()[0], "nieuw")

    def test_docker_onbereikbaar_markeert_niets(self):
        self.zet("docker-weg", "1")
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("docker niet bereikbaar", r.stdout)
        self.assertIsNone(self.data(".mislukt"))
        self.assertIsNone(self.data(".herstel"))
        self.assertNotIn("--build", self.docker())

    def test_vuile_werkboom_bouwt_niet(self):
        self.zet("werkboom", " M mijnagents/app.py")
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("wijkt af van HEAD", r.stdout)
        self.assertNotIn("--build", self.docker())
        self.assertIsNone(self.data(".mislukt"))

    def test_git_faalt_bouwt_niet(self):
        self.zet("git-faalt", "1")
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("geen uitrol", r.stdout)
        self.assertEqual(self.docker(), "")


if __name__ == "__main__":
    unittest.main()

"""mijnagents/deploy.sh met nep-git, nep-docker, nep-curl, nep-sqlite3 en nep-gh in een tijdelijke HOME (Codex CX7-1, CX8-1,
CX9-1/2/3, CX10 en BU-1 tot BU-9).

De nep-docker houdt bij welke image als :latest en :vorige getagd is, welk label (mijnagents.tree) elke image draagt en welke
image de container draait; de nep-curl is gezond zolang de draaiende image in het bestand `gezond` staat. De nep-gh speelt
GitHub Actions voor mijnagents/deploy_ci.py (toestand in het bestand `ci`). Vlagbestanden in HOME laten een stap falen:
`X` altijd, `X.1` één keer. Elke nep schrijft ook naar `alles.log`, zodat de volgorde van de stappen na te gaan is.

flock, timeout en dash zijn op de CI (Ubuntu) en op de VM de echte; op een Mac zonder flock of timeout vult de test een
kleine vervanger in met dezelfde werking (flock(2) op het geërfde fd, procesgroep stoppen na de limiet)."""
import gzip
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
SHA = "1" * 40

GIT = r'''#!/bin/sh
echo "git $*" >> "$HOME/alles.log"
case "$1" in
  rev-parse)
    [ -f "$HOME/git-faalt" ] && exit 128
    case "$2" in
      HEAD) cat "$HOME/sha" ;;
      *:mijnagents) cat "$HOME/revisie" ;;
      *) exit 128 ;;
    esac ;;
  archive) [ -f "$HOME/archive-faalt" ] && exit 128; tar -cf "$4" -C "$HOME/bron" . ;;
  *) exit 1 ;;
esac
'''

DOCKER = r'''#!/bin/sh
S="$HOME/staat"
echo "docker $*" >> "$HOME/docker.log"
echo "docker $*" >> "$HOME/alles.log"
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
  container) [ "$2" = inspect ] && [ -f "$S/draait" ] && cat "$S/draait" ;;
  image)
    case "$2" in
      inspect)
        id=$(id_van "$5") && [ -n "$id" ] || exit 1
        case "$4" in
          *Labels*) if [ -f "$S/label-${id#sha256:}" ]; then cat "$S/label-${id#sha256:}"; else echo; fi ;;
          *) echo "$id" ;;
        esac ;;
      tag)
        if faalt "tag-${4##*:}"; then exit 1; fi
        id=$(id_van "$3") && [ -n "$id" ] || exit 1
        echo "$id" > "$S/tag-${4##*:}"
        if faalt wissel-bij-tag; then echo sha256:ander > "$S/draait"; fi ;;
      *) exit 1 ;;
    esac ;;
  build)
    boom=; ctx=
    for a in "$@"; do case "$a" in mijnagents.tree=*) boom=${a#mijnagents.tree=} ;; esac; ctx=$a; done
    if [ -f "$HOME/bouw-wacht" ]; then
      touch "$HOME/bouw-bezig"
      while [ ! -f "$HOME/ga" ]; do sleep 0.05; done
    fi
    if faalt bouw-hangt; then sleep 60; fi
    if [ -f "$HOME/bouw-achtergrond" ]; then sleep 30 >/dev/null 2>&1 & echo $! > "$HOME/achtergrond.pid"; fi
    if faalt bouw-breekt-oud; then grep -vx 'sha256:oud' "$HOME/gezond" > "$HOME/gezond.tmp"; mv "$HOME/gezond.tmp" "$HOME/gezond"; fi
    if faalt bouw-faalt; then exit 1; fi
    ls -A "$ctx" > "$S/gebouwd-lijst"
    cp "$ctx/inhoud" "$S/gebouwd-inhoud"
    if [ -f "$HOME/bouw-zonder-label" ]; then echo > "$S/label-$boom"; else echo "$boom" > "$S/label-$boom"; fi
    echo "sha256:$boom" > "$S/tag-latest" ;;
  compose)
    case "$*" in
      *--no-build*--force-recreate*)
        if faalt herstart-faalt; then exit 1; fi
        [ -f "$HOME/compose-vervangt-niet" ] || cp "$S/tag-latest" "$S/draait"
        if faalt start-faalt; then exit 1; fi ;;
      *) exit 1 ;;
    esac ;;
  *) exit 1 ;;
esac
'''

CURL = r'''#!/bin/sh
d=$(cat "$HOME/staat/draait" 2>/dev/null) || exit 7
if [ -f "$HOME/curl-half" ]; then printf '{"agents":39,"ok":true'; exit 18; fi
grep -qxF "$d" "$HOME/gezond" 2>/dev/null || exit 7
if [ "$(cat "$HOME/wankel" 2>/dev/null)" = "$d" ]; then
  if [ -f "$HOME/wankel-aan" ]; then rm -f "$HOME/wankel-aan"; exit 7; fi
  : > "$HOME/wankel-aan"
fi
if [ -f "$HOME/curl-antwoord" ]; then cat "$HOME/curl-antwoord"; else echo '{"agents":39,"app":"Mehdi Agents","ok":true}'; fi
'''

SQLITE3 = r'''#!/bin/sh
echo "sqlite3 $*" >> "$HOME/alles.log"
if [ "$1" = -readonly ]; then
  [ -f "$HOME/kopie-faalt" ] && exit 1
  doel=${3#.backup \'}; doel=${doel%\'}
  cp "$2" "$doel"
else
  if [ -f "$HOME/kopie-corrupt" ]; then echo "*** in database main ***"; else echo ok; fi
fi
'''

GH = r'''#!/bin/sh
echo "gh $*" >> "$HOME/alles.log"
[ -f "$HOME/gh-weg" ] && { echo "token ghp_geheim" >&2; exit 1; }
sha=${4#*head_sha=}; sha=${sha%%&*}
t=$(cat "$HOME/ci" 2>/dev/null || echo success)
case "$t" in
  geen) echo '{"workflow_runs":[]}' ;;
  lopend) s=in_progress; c=null ;;
  *) s=completed; c="\"$t\"" ;;
esac
[ "$t" = geen ] || printf '{"workflow_runs":[{"id":7,"run_number":1,"run_attempt":1,"head_sha":"%s","head_branch":"main","event":"push","path":".github/workflows/bord-grendels.yml","status":"%s","conclusion":%s}]}\n' "$sha" "$s" "$c"
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
        for d in ("bin", "staat", "tmp", "bron", "appportal/mijnagents-data"):
            (t / d).mkdir(parents=True)
        self.zet("appportal/mijnagents-data/.built", "oud")
        self.zet("appportal/mijnagents-data/mijnagents.db", "databank-inhoud")
        self.zet("sha", SHA)
        self.zet("revisie", "nieuw")
        self.zet("bron/inhoud", "v1")
        self.zet("bron/Dockerfile", "FROM scratch")
        self.zet("staat/tag-latest", "sha256:oud")
        self.zet("staat/draait", "sha256:oud")
        self.gezond("sha256:oud")
        for naam, tekst in (("git", GIT), ("docker", DOCKER), ("curl", CURL), ("sqlite3", SQLITE3), ("gh", GH)):
            _uitvoerbaar(t / "bin" / naam, tekst)
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
        return {**os.environ, "HOME": str(self.t), "PATH": f"{self.t}/bin:{os.environ['PATH']}", "TMPDIR": str(self.t / "tmp"),
                "BORD_WACHT": "0", "BORD_POGINGEN": "4", **extra}

    def draai(self, **extra):
        return subprocess.run([SH, str(SCRIPT)], env=self.env(**extra), capture_output=True, text=True, timeout=60)

    def zet(self, pad, tekst):
        (self.t / pad).write_text(tekst + "\n")

    def weg(self, pad):
        (self.t / pad).unlink()

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

    def kopieen(self):
        d = self.t / "backups" / "voor-uitrol"
        return sorted(d.iterdir()) if d.exists() else []

    # --- gewone uitrol ---------------------------------------------------------------------------------------------

    def test_zelfde_revisie_doet_niets(self):
        self.zet("appportal/mijnagents-data/.built", "nieuw")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.docker(), "")
        self.assertEqual(r.stdout, "")

    def test_gezond_nieuw_bord_wordt_gemarkeerd(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.data(".built"), "nieuw")
        self.assertEqual(self.lees("staat/draait"), "sha256:nieuw")
        self.assertEqual(self.lees("staat/label-nieuw"), "nieuw")
        self.assertEqual(self.lees("staat/tag-vorige"), "sha256:oud")
        self.assertIsNone(self.data(".mislukt"))
        self.assertIsNone(self.data(".herstel"))
        self.assertIn(f"deployed (nieuw, commit {SHA})", r.stdout)
        self.assertIn(f"--label org.opencontainers.image.revision={SHA}", self.docker())
        self.assertEqual(list((self.t / "tmp").iterdir()), [], "de bronmap van de bouw blijft niet achter")

    def test_eerste_uitrol_zonder_image(self):
        self.weg("staat/tag-latest")
        self.weg("staat/draait")
        self.gezond("sha256:nieuw")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.data(".built"), "nieuw")

    # --- exact de vastgelegde commit (BU-1, BU-3) -------------------------------------------------------------------

    def test_bouwt_de_vastgelegde_tree_ook_als_de_werkboom_verandert(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        werkboom = self.t / "appportal" / "mijnagents"
        werkboom.mkdir()
        (werkboom / ".env").write_text("GEHEIM=1\n")  # genegeerd bestand in de werkboom: hoort niet in de image
        self.zet("bouw-wacht", "1")
        a = subprocess.Popen([SH, str(SCRIPT)], env=self.env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self._wacht_op("bouw-bezig")
            self.zet("bron/inhoud", "v2")  # een git pull tijdens de bouw
            self.zet("revisie", "nieuwer")
            self.zet("sha", "2" * 40)
            self.zet("ga", "1")
            uit, fout = a.communicate(timeout=30)
        finally:
            if a.poll() is None:
                a.kill()
        self.assertEqual(a.returncode, 0, uit + fout)
        self.assertEqual(self.lees("staat/gebouwd-inhoud"), "v1")
        self.assertNotIn(".env", self.lees("staat/gebouwd-lijst").split())
        self.assertEqual(self.data(".built"), "nieuw")
        self.assertIn(f"commit {SHA}", uit)

    def test_image_zonder_deze_revisie_telt_niet(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        self.zet("bouw-zonder-label", "1")
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("de image draagt revisie nieuw niet", r.stdout)
        self.assertEqual(self.lees("staat/draait"), "sha256:oud")
        self.assertNotIn("--force-recreate", self.docker())

    # --- CI-grendel (BU-2) ------------------------------------------------------------------------------------------

    def test_ci_lopend_wacht_zonder_markering_en_meldt_een_keer(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        self.zet("ci", "lopend")
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("CI blokkeert de uitrol", r.stdout)
        self.assertIn("loopt nog", r.stdout)
        self.assertNotIn(" build ", self.docker())
        for naam in (".mislukt", ".herstel"):
            self.assertIsNone(self.data(naam))
        self.assertEqual(self.kopieen(), [])
        r = self.draai()  # dezelfde reden: geen nieuwe regel
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.zet("ci", "failure")
        r = self.draai()
        self.assertIn("niet geslaagd: failure", r.stdout)
        self.zet("ci", "success")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.data(".built"), "nieuw")
        self.assertIsNone(self.data(".ci_wacht"))

    def test_ci_onbereikbaar_of_zonder_run_bouwt_niet(self):
        for vlag, inhoud, reden in (("gh-weg", "1", "niet bereikbaar"), ("ci", "geen", "geen bord-grendels.yml-run")):
            with self.subTest(vlag=vlag):
                self.zet(vlag, inhoud)
                r = self.draai()
                self.assertEqual(r.returncode, 1)
                self.assertIn(reden, r.stdout)
                self.assertNotIn("ghp_geheim", r.stdout + r.stderr)
                self.assertNotIn(" build ", self.docker())
                self.weg(vlag)

    # --- kopie van de databank (BU-4) -------------------------------------------------------------------------------

    def test_kopie_van_de_databank_voor_de_bouw(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        k = self.kopieen()
        self.assertEqual(len(k), 1)
        self.assertRegex(k[0].name, r"^mijnagents-voor-uitrol-\d{8}T\d{6}Z-nieuw\.sqlite\.gz$")
        self.assertEqual(gzip.decompress(k[0].read_bytes()).decode().strip(), "databank-inhoud")
        alles = self.lees("alles.log")
        self.assertLess(alles.index("sqlite3 -readonly"), alles.index("docker build"))

    def test_kopie_mislukt_bouwt_niet(self):
        for vlag in ("kopie-faalt", "kopie-corrupt"):
            with self.subTest(vlag=vlag):
                self.zet(vlag, "1")
                r = self.draai()
                self.assertEqual(r.returncode, 1)
                self.assertIn("kopie van de databank mislukt", r.stdout)
                self.assertNotIn(" build ", self.docker())
                self.assertEqual(self.kopieen(), [])  # geen half of corrupt bestand achtergelaten
                self.assertIsNone(self.data(".mislukt"))
                self.weg(vlag)

    def test_te_weinig_ruimte_voor_de_kopie_bouwt_niet(self):
        r = self.draai(BORD_KOPIE_MIN_VRIJ_MB=str(10 ** 12))
        self.assertEqual(r.returncode, 1)
        self.assertIn("te weinig vrije ruimte", r.stdout)
        self.assertNotIn(" build ", self.docker())

    # --- mislukte uitrol en terugrol (CX7-1, CX8-1) ------------------------------------------------------------------

    def test_ongezond_nieuw_bord_krijgt_de_vorige_image_terug_en_wacht_de_afkoeling(self):
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("vorige image sha256:oud teruggezet en gezond", r.stdout)
        self.assertIn("volgende poging vanaf 20", r.stdout)  # een absoluut tijdstip (BU-9)
        self.assertEqual(self.lees("staat/draait"), "sha256:oud")
        self.assertEqual(self.lees("staat/tag-latest"), "sha256:oud")
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
        self.zet("start-faalt.1", "1")
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("UITROL MISLUKT bij het starten", r.stdout)
        self.assertEqual(self.lees("staat/draait"), "sha256:oud")
        self.assertEqual(self.data(".built"), "oud")

    def test_gezondheid_van_de_oude_container_telt_niet_voor_de_nieuwe_image(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        self.zet("compose-vervangt-niet", "1")
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("UITROL MISLUKT bij de gezondheidscontrole", r.stdout)
        self.assertEqual(self.data(".built"), "oud")
        self.assertEqual(self.lees("staat/tag-latest"), "sha256:oud")

    def test_half_antwoord_of_ok_als_tekst_telt_niet(self):
        for vlag, inhoud in (("curl-half", "1"), ("curl-antwoord", '{"ok": "true"}'), ("curl-antwoord", "ok: true")):
            with self.subTest(vlag=vlag, inhoud=inhoud):
                self.zet("appportal/mijnagents-data/.mislukt", "")
                self.weg("appportal/mijnagents-data/.mislukt")
                self.gezond("sha256:oud", "sha256:nieuw")
                self.zet(vlag, inhoud)
                r = self.draai()
                self.assertEqual(r.returncode, 1)
                self.assertEqual(self.data(".built"), "oud")
                self.weg(vlag)

    def test_wankel_bord_telt_niet_als_gezond(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        self.zet("wankel", "sha256:nieuw")  # afwisselend gezond en ongezond
        r = self.draai(BORD_POGINGEN="8")
        self.assertEqual(r.returncode, 1)
        self.assertIn("UITROL MISLUKT bij de gezondheidscontrole", r.stdout)
        self.assertEqual(self.data(".built"), "oud")
        self.assertEqual(self.lees("staat/draait"), "sha256:oud")

    # --- één ronde tegelijk (CX9-1) ------------------------------------------------------------------------------------

    def _wacht_op(self, naam):
        grens = time.time() + 20
        while not (self.t / naam).exists():
            self.assertLess(time.time(), grens, f"{naam} kwam er niet")
            time.sleep(0.05)

    def test_twee_overlappende_rondes(self):
        self.zet("bouw-wacht", "1")
        a = subprocess.Popen([SH, str(SCRIPT)], env=self.env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self._wacht_op("bouw-bezig")
            voor = self.lees("alles.log")
            r = self.draai()  # ronde B start terwijl A bouwt
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(self.lees("alles.log"), voor, "ronde B mag niets aanraken")
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
        self.weg("bouw-achtergrond")
        self.zet("revisie", "nieuwer")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.data(".built"), "nieuwer", "het achtergebleven proces hield het slot vast")

    # --- terugrolimage en tagfouten (CX9-2, BU-8) -------------------------------------------------------------------

    def test_terugrolimage_is_de_draaiende_image(self):
        self.zet("staat/tag-latest", "sha256:ongezond-gebouwd")  # :latest wijst niet naar wat draait
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.lees("staat/tag-vorige"), "sha256:oud")
        self.assertEqual(self.lees("staat/draait"), "sha256:oud")

    def test_wissel_van_container_bij_het_taggen_bouwt_niet(self):
        self.zet("wissel-bij-tag.1", "1")
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("kon niet als appportal-app-mijnagents:vorige bewaard worden", r.stdout)
        self.assertNotIn(" build ", self.docker())

    def test_tagfout_voor_de_bouw_bouwt_niet_en_blokkeert_niet(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        self.zet("tag-vorige.1", "1")
        r = self.draai()
        self.assertEqual(r.returncode, 1)
        self.assertIn("geen bouw in deze ronde", r.stdout)
        self.assertNotIn(" build ", self.docker())
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
        self.assertNotIn(" build ", self.docker()[len(log):])  # herstel, geen nieuwe bouw van dezelfde revisie
        self.assertEqual(self.mislukt()[::2], ("nieuw", 1))

    # --- een onderbroken ronde (CX9-2, BU-5, BU-6) ------------------------------------------------------------------

    def test_afgebroken_ronde_met_ongezonde_nieuwe_image_wordt_hersteld(self):
        self.zet("staat/tag-latest", "sha256:nieuw")
        self.zet("staat/draait", "sha256:nieuw")
        self.zet("staat/label-nieuw", "nieuw")
        self.zet("appportal/mijnagents-data/.herstel", "sha256:oud nieuw 2")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.lees("staat/draait"), "sha256:oud")
        self.assertIsNone(self.data(".herstel"))
        self.assertEqual(self.mislukt()[::2], ("nieuw", 2))
        self.assertNotIn(" build ", self.docker())

    def test_onderbroken_voor_de_bouw_telt_niet_als_mislukt(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        self.zet("appportal/mijnagents-data/.herstel", "sha256:oud nieuw 1")  # herstart van de VM vlak voor de bouw
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("de vorige image sha256:oud draait gezond", r.stdout)
        self.assertNotIn("telt als mislukt", r.stdout)
        self.assertEqual(self.data(".built"), "nieuw")  # in dezelfde ronde gewoon uitgerold

    def test_gezonde_uitrol_zonder_built_wordt_voltooid(self):
        self.gezond("sha256:oud", "sha256:nieuw")
        self.zet("staat/tag-latest", "sha256:nieuw")
        self.zet("staat/draait", "sha256:nieuw")
        self.zet("staat/label-nieuw", "nieuw")
        self.zet("appportal/mijnagents-data/.herstel", "sha256:oud nieuw 1")  # .built schrijven mislukte
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.data(".built"), "nieuw")
        self.assertEqual(self.lees("staat/draait"), "sha256:nieuw")
        self.assertIsNone(self.data(".herstel"))
        self.assertNotIn(" build ", self.docker())
        self.assertNotIn("--force-recreate", self.docker())

    def test_achtergebleven_markering_bij_een_later_ongezond_bord_zet_terug_en_ontmarkeert(self):
        self.zet("appportal/mijnagents-data/.built", "nieuw")
        self.zet("staat/tag-latest", "sha256:nieuw")
        self.zet("staat/draait", "sha256:nieuw")
        self.zet("staat/label-nieuw", "nieuw")
        self.zet("appportal/mijnagents-data/.herstel", "sha256:oud nieuw 1")
        r = self.draai()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.lees("staat/draait"), "sha256:oud")
        self.assertNotEqual(self.data(".built"), "nieuw")  # .built zegt niet meer dat nieuw draait
        self.assertEqual(self.mislukt()[0], "nieuw")

    def test_bewaakt_een_ongewijzigde_revisie(self):
        self.zet("appportal/mijnagents-data/.built", "nieuw")
        self.gezond()  # niets gezond
        r = self.draai()
        self.assertEqual(r.returncode, 0)
        self.assertIn("LET OP: /gezondheid faalt", r.stdout)
        self.assertEqual(self.draai().stdout, "")  # dezelfde toestand: geen nieuwe regel
        self.gezond("sha256:oud")
        self.assertIn("weer gezond", self.draai().stdout)
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
        self.assertEqual(self.docker().count(" build "), 1)
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
                self.assertEqual(" build " in self.docker(), bouwt, r.stdout + r.stderr)
                if bouwt:
                    self.assertEqual(self.mislukt()[::2], ("nieuw", n + 1))
                    self.assertIn(f"poging {n + 1}", r.stdout)

    def test_vrijgave_door_mislukt_weg_te_halen(self):
        self.assertEqual(self.draai().returncode, 1)
        self.gezond("sha256:oud", "sha256:nieuw")
        self.weg("appportal/mijnagents-data/.mislukt")
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
        self.assertNotIn(" build ", self.docker())

    def test_git_of_archive_faalt_bouwt_niet(self):
        for vlag, reden in (("git-faalt", "geen uitrol"), ("archive-faalt", "git archive van nieuw mislukt")):
            with self.subTest(vlag=vlag):
                self.zet(vlag, "1")
                r = self.draai()
                self.assertEqual(r.returncode, 1)
                self.assertIn(reden, r.stdout)
                self.assertNotIn(" build ", self.docker())
                self.assertIsNone(self.data(".mislukt"))
                self.weg(vlag)


if __name__ == "__main__":
    unittest.main()

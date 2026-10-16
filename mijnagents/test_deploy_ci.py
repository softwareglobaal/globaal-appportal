"""mijnagents/deploy_ci.py met een nep-gh (Codex BU-2): alleen een geslaagde, voltooide bord-grendels-run op main (push)
voor exact deze commit laat de uitrol door; de nieuwste poging telt; geen ruwe gh-uitvoer in de melding."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

CI = Path(__file__).resolve().parent / "deploy_ci.py"
SHA = "a" * 40

GH = r'''#!/bin/sh
echo "$*" >> "$HOME/gh.log"
[ -f "$HOME/gh-faalt" ] && { echo "token ghp_geheim" >&2; exit 1; }
cat "$HOME/antwoord"
'''


def run(**veld):
    r = {"id": 11, "run_number": 5, "run_attempt": 1, "head_sha": SHA, "head_branch": "main", "event": "push",
         "path": ".github/workflows/bord-grendels.yml", "status": "completed", "conclusion": "success"}
    r.update(veld)
    return r


class DeployCiTest(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix="deploy-ci-"))
        self.addCleanup(shutil.rmtree, self.t, ignore_errors=True)
        (self.t / "bin").mkdir()
        gh = self.t / "bin" / "gh"
        gh.write_text(GH)
        gh.chmod(gh.stat().st_mode | stat.S_IXUSR)

    def ci(self, runs=None, *, ruw=None, sha=SHA):
        (self.t / "antwoord").write_text(ruw if ruw is not None else json.dumps({"workflow_runs": runs or []}))
        env = {**os.environ, "HOME": str(self.t), "PATH": f"{self.t}/bin:{os.environ['PATH']}"}
        return subprocess.run([sys.executable, str(CI), "--sha", sha], env=env, capture_output=True, text=True, timeout=30)

    def test_geslaagde_run_laat_door(self):
        r = self.ci([run()])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(json.loads(r.stdout), {"sha": SHA, "workflow": "bord-grendels.yml", "run_id": 11})
        gevraagd = (self.t / "gh.log").read_text()
        self.assertIn(f"actions/workflows/bord-grendels.yml/runs?head_sha={SHA}&branch=main&event=push", gevraagd)

    def test_lopend_rood_of_ontbrekend_blokkeert(self):
        for runs, reden in (([run(status="in_progress", conclusion=None)], "loopt nog"),
                            ([run(conclusion="failure")], "niet geslaagd: failure"),
                            ([run(conclusion="cancelled")], "niet geslaagd: cancelled"),
                            ([], "geen bord-grendels.yml-run")):
            with self.subTest(reden=reden):
                r = self.ci(runs)
                self.assertEqual(r.returncode, 1)
                self.assertIn(reden, r.stdout)

    def test_andere_tak_gebeurtenis_workflow_of_commit_telt_niet(self):
        for veld in ({"head_branch": "werf-brug"}, {"event": "pull_request"}, {"path": ".github/workflows/andere.yml"},
                     {"head_sha": "b" * 40}):
            with self.subTest(veld=veld):
                r = self.ci([run(**veld)])
                self.assertEqual(r.returncode, 1)
                self.assertIn("geen bord-grendels.yml-run", r.stdout)

    def test_de_nieuwste_poging_telt(self):
        r = self.ci([run(run_attempt=1, conclusion="failure"), run(run_attempt=2, id=12)])
        self.assertEqual(r.returncode, 0, r.stdout)
        r = self.ci([run(run_attempt=1), run(run_attempt=2, id=12, conclusion="failure")])
        self.assertEqual(r.returncode, 1)
        r = self.ci([run(run_number=5), run(run_number=6, id=13, status="queued", conclusion=None)])
        self.assertEqual(r.returncode, 1)
        self.assertIn("loopt nog", r.stdout)

    def test_onbereikbaar_of_onleesbaar_blokkeert_zonder_ruwe_uitvoer(self):
        (self.t / "gh-faalt").write_text("1")
        r = self.ci([run()])
        self.assertEqual(r.returncode, 1)
        self.assertIn("niet bereikbaar", r.stdout)
        self.assertNotIn("ghp_geheim", r.stdout + r.stderr)
        (self.t / "gh-faalt").unlink()
        for ruw in ("geen json", "[]", '{"workflow_runs": "x"}'):
            with self.subTest(ruw=ruw):
                self.assertEqual(self.ci(ruw=ruw).returncode, 1)
        self.assertEqual(self.ci([run(run_number="vijf")]).returncode, 1)
        self.assertEqual(self.ci([run(id="11")]).returncode, 1)

    def test_onvolledige_sha_vraagt_github_niet(self):
        r = self.ci([run()], sha="abc123")
        self.assertEqual(r.returncode, 1)
        self.assertIn("volledige commit-SHA", r.stdout)
        self.assertFalse((self.t / "gh.log").exists())


if __name__ == "__main__":
    unittest.main()

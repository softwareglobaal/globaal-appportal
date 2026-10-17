#!/usr/bin/env python3
"""CI-grendel voor de borduitrol (Codex BU-2, 16-10-2026): de exacte commit op de VM heeft een geslaagde run van
bord-grendels op main (push). Die workflow draait bij elke push naar main en test alle bordtests in mijnagents/.

Geen terugval: rood, lopend, ontbrekend of GitHub onbereikbaar betekent geen bouw; deploy.sh kijkt de volgende
cronronde opnieuw. Gebruikt de bestaande gh-authenticatie op de VM. Geen ruwe gh-uitvoer in de melding: foutuitvoer
kan sleutels bevatten. Uitvoer: bij succes één JSON-regel met het bewijs (exit 0), anders de reden (exit 1)."""
import argparse
import json
import re
import subprocess
import sys

REPO = "softwareglobaal/globaal-appportal"
WORKFLOW = "bord-grendels.yml"


class Blokkeert(Exception):
    pass


def gh(pad):
    try:
        r = subprocess.run(["gh", "api", "--hostname", "github.com", pad], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Blokkeert("GitHub niet bereikbaar (gh)") from exc
    if r.returncode:
        raise Blokkeert("GitHub niet bereikbaar (gh faalde)")
    try:
        return json.loads(r.stdout)
    except ValueError as exc:
        raise Blokkeert("GitHub gaf geen bruikbaar JSON-antwoord") from exc


def controle(sha, repo=REPO, workflow=WORKFLOW):
    if not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
        raise Blokkeert("een volledige commit-SHA is verplicht")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or not re.fullmatch(r"[A-Za-z0-9_.-]+\.ya?ml", workflow):
        raise Blokkeert("ongeldige repository of workflow")
    data = gh(f"repos/{repo}/actions/workflows/{workflow}/runs?head_sha={sha}&branch=main&event=push&per_page=100")
    runs = data.get("workflow_runs") if isinstance(data, dict) else None
    if not isinstance(runs, list):
        raise Blokkeert("GitHub-antwoord zonder workflow_runs")
    eigen = [r for r in runs if isinstance(r, dict) and r.get("head_sha") == sha and r.get("head_branch") == "main"
             and r.get("event") == "push" and r.get("path") == f".github/workflows/{workflow}"]
    if not eigen:
        raise Blokkeert(f"geen {workflow}-run op main voor deze commit")
    try:
        laatste = max(eigen, key=lambda r: (int(r.get("run_number") or 0), int(r.get("run_attempt") or 0)))
    except (TypeError, ValueError) as exc:
        raise Blokkeert("GitHub gaf een onleesbaar runnummer") from exc
    rid = laatste.get("id")
    if laatste.get("status") != "completed":
        raise Blokkeert(f"{workflow} loopt nog (run {rid})")
    if laatste.get("conclusion") != "success":
        raise Blokkeert(f"{workflow} is niet geslaagd: {laatste.get('conclusion')} (run {rid})")
    if type(rid) is not int or rid <= 0:
        raise Blokkeert("de run heeft geen geldige identiteit")
    return {"sha": sha, "workflow": workflow, "run_id": rid}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sha", required=True)
    p.add_argument("--repo", default=REPO)
    p.add_argument("--workflow", default=WORKFLOW)
    a = p.parse_args()
    try:
        bewijs = controle(a.sha, repo=a.repo, workflow=a.workflow)
    except Blokkeert as exc:
        print(exc)
        return 1
    print(json.dumps(bewijs, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

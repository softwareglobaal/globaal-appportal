#!/usr/bin/env python3
"""De Gezondheidswacht (Privé, alleen voor Mehdi) — draait op de Mac. Leest de
Apple Watch-gegevens (Health Auto Export -> iCloud -> gezondheid.sqlite, zie
~/bin/gezondheid.py) en zet de dagsamenvatting klaar op het bord voor De
Levenscoach. Alleen lezen; niets wordt gedeeld buiten Mehdi's eigen agents.
Gebruik: gezondheid_wacht.py [--dag JJJJ-MM-DD]   (standaard gisteren)
"""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta

NAAM = "gezondheid-wacht"
BORD = os.environ.get("MIJNAGENTS_URL", "https://mijnagents.globaal.be")
SCRIPT = os.path.expanduser("~/bin/gezondheid.py")
DAG = None
for i, a in enumerate(sys.argv):
    if a == "--dag" and i + 1 < len(sys.argv):
        DAG = sys.argv[i + 1]
DAG = DAG or (datetime.now().date() - timedelta(days=1)).isoformat()


def token():
    try:
        return open(os.path.expanduser("~/.config/mijnagents/token")).read().strip()
    except OSError:
        return ""


def bord(pad, payload):
    req = urllib.request.Request(f"{BORD}{pad}", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Agents-Token": token()})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")


def hartslag(status, taak="", detail="", nood=None):
    p = {"naam": NAAM, "status": status, "taak": taak, "detail": detail}
    if nood is not None:
        p["nood"] = nood
    try:
        bord("/agent-status", p)
    except Exception as e:  # noqa: BLE001
        print("hartslag mislukt:", e, file=sys.stderr)


def draai(*args):
    uit = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, timeout=300)
    return uit.returncode, (uit.stdout + uit.stderr).strip()


def main():
    if not os.path.exists(SCRIPT):
        hartslag("fout", taak="gezondheid.py niet gevonden", detail=SCRIPT, nood=[{"tekst": "~/bin/gezondheid.py ontbreekt op de Mac", "wie": "claude-code"}])
        sys.exit(1)
    hartslag("actief", taak=f"gezondheid {DAG} lezen")
    rc1, inlezen = draai("inlezen")
    rc2, dag = draai("dag", DAG)
    nood = []
    if rc2 != 0 or not dag or "geen" in dag.lower()[:80]:
        nood.append({"tekst": f"Geen Apple Watch-gegevens voor {DAG}: staat Health Auto Export aan en synct iCloud Drive?", "wie": "mehdi"})
    items = [{"van": NAAM, "voor": "mehdi", "soort": "gezondheid", "sleutel": DAG, "titel": f"Gezondheid {DAG}",
              "uniek": f"gezondheid:{DAG}", "inhoud": {"datum": DAG, "samenvatting": dag[:12000], "inlezen": inlezen[-400:]}}]
    uit = bord("/api/klaarzet", {"items": items})
    bord("/api/logboek", {"regels": [
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "bron", "tekst": f"inlezen: {inlezen.splitlines()[-1][:120] if inlezen else 'niets nieuws'}"},
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "schrijf", "tekst": f"dagsamenvatting klaargezet ({uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend)", "detail": dag[:4000]}]})
    hartslag("klaar" if not nood else "waakt", taak=f"gezondheid {DAG} klaargezet", detail=("gegevens aanwezig" if not nood else "geen gegevens"), nood=nood)
    print(f"{DAG}: rc={rc2}, {len(dag)} tekens, klaargezet {uit.get('nieuw', 0)} nieuw")


if __name__ == "__main__":
    main()

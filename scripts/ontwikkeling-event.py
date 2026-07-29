"""Claude Code-hook: meldt sessie-metadata aan het organisatie-dashboard
(ontwikkel-statistieken, migratie 074, tab Ontwikkeling).

Alleen metadata: soort gebeurtenis, repo, identiteit en sessie-id. Nooit
gespreksinhoud, nooit bestandsnamen (privacy-lijn Shaniel 2026-07-16).

Aanroep:  python ontwikkeling-event.py <start|prompt|einde>
De duur van een sessie wordt server-side afgeleid uit de eerste en de laatste
gebeurtenis; prompts worden apart geteld.

In Python geschreven en niet in shell of node, omdat python hier wel op het
PATH staat en node niet: de vorige hook faalde daardoor stil bij elke sessie.
De hook mag een sessie nooit blokkeren, dus alle fouten worden ingeslikt en de
exitcode is altijd 0.
"""
import json
import os
import platform
import subprocess
import sys
import urllib.request

URL = os.environ.get("ONTWIKKELING_URL",
                     "https://organisatie.globaal.be/ontwikkeling/event")


def _stil(args):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=5)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def main():
    token = os.environ.get("ONTWIKKELING_TOKEN", "").strip()
    if not token:
        return
    event = sys.argv[1] if len(sys.argv) > 1 else "prompt"
    try:
        invoer = json.loads(sys.stdin.read() or "{}")
    except Exception:
        invoer = {}
    sessie = str(invoer.get("session_id", ""))[:120]
    cwd = invoer.get("cwd") or os.getcwd()
    top = _stil(["git", "-C", cwd, "rev-parse", "--show-toplevel"]) or cwd
    repo = os.path.basename(top.rstrip("/\\")) or "onbekend"
    wie = (_stil(["git", "-C", cwd, "config", "user.email"])
           or os.environ.get("USERNAME") or "onbekend")
    # Machinenaam erbij (migratie 095): Shaniel werkt op meer dan een machine en
    # zonder dit veld zijn die niet te scheiden. Alleen de naam, geen adres.
    machine = (os.environ.get("COMPUTERNAME")
               or os.environ.get("HOSTNAME")
               or platform.node() or "")[:60]
    body = json.dumps({"event": event, "repo": repo, "gebruiker": wie,
                       "sessie": sessie, "machine": machine}).encode()
    req = urllib.request.Request(
        URL, data=body,
        headers={"Content-Type": "application/json",
                 "X-Ontwikkeling-Token": token})
    urllib.request.urlopen(req, timeout=4).read()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)

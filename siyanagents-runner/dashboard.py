#!/usr/bin/env python3
"""Leesbrug naar het sales-dashboard voor de Sales/Marketing-agents.

Het dashboard bezit de definities: wat telt als aanvraag, op welke datum,
welke pipelines in scope zitten, hoe kanalen uit labels volgen. Die staan in
DASHBOARD-SPEC.md en zijn moeizaam vastgelegd. Deze brug levert de UITKOMST
daarvan. Leid cijfers over aanvragen, omzet, doorlooptijden, kanalen en
advertenties dus nooit zelf opnieuw af uit Pipedrive - dan krijg je andere
getallen dan Siyan op zijn scherm ziet, en dan is er geen waarheid meer.

Strikt lezend. Zie docs/AGENT-API.md in de sales-dashboard-repo.

Gebruik:
  dashboard.py health
  dashboard.py kpi <engineering|energy> [periode]
  dashboard.py kanalen <engineering|energy> [periode]
  dashboard.py diensten <engineering|energy> [periode]
  dashboard.py campagnes [periode]

Periode: 12m (standaard), ytd, prev_year, all, 2026-01 .. 2026-12,
of wk:JJJJ-MM-DD. Laat je hem weg, dan krijg je de laatste 12 maanden.
"""

import json
import os
import sys
import urllib.parse
import urllib.request


def _laad_env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    except OSError:
        pass


_laad_env("~/appportal/.env")

API = os.environ.get("SALES_API_URL", "https://sales.globaal.be/api/v1")
TOKEN = os.environ.get("SALES_AGENT_TOKEN", "")


def haal(pad, **params):
    url = API + pad
    params = {k: v for k, v in params.items() if v}
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer " + TOKEN)
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def main(argv):
    if not TOKEN:
        raise SystemExit("SALES_AGENT_TOKEN ontbreekt in ~/appportal/.env")
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0

    cmd = argv[0]
    afdelingen = ("engineering", "energy")

    if cmd == "health":
        uit = haal("/health")
    elif cmd in ("kpi", "kanalen", "diensten"):
        if len(argv) < 2 or argv[1] not in afdelingen:
            raise SystemExit(f"gebruik: dashboard.py {cmd} <engineering|energy> [periode]")
        uit = haal("/" + cmd, afdeling=argv[1], periode=argv[2] if len(argv) > 2 else "12m")
    elif cmd == "campagnes":
        uit = haal("/campagnes", periode=argv[1] if len(argv) > 1 else "12m")
    else:
        raise SystemExit(f"onbekend commando '{cmd}'. Zie dashboard.py --help")

    print(json.dumps(uit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Noemt de actieve apps uit apps.yaml die nog geen nginx-blok of
compose-service hebben, een id per regel.

Gebruikt door scripts/apps-bijwerken.sh om te bepalen of er werk is. Los te
draaien om te zien wat de cron zou doen:

    python3 scripts/apps-ontbrekend.py
    python3 scripts/apps-ontbrekend.py --uitleg

Een app zonder 'poort' wordt overgeslagen: zonder poort valt er geen
compose-service of nginx-blok te maken. Dat is geen fout, het betekent dat de
app anders is ingericht, zoals de apps die op een vast pad van een andere app
hangen.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from appcatalogus import AppFout, lees  # noqa: E402

WORTEL = pathlib.Path(__file__).resolve().parent.parent
NGINX_SJABLONEN = WORTEL / "nginx" / "templates"
COMPOSE = WORTEL / "docker-compose.override.yml"


def heeft_nginx(app_id: str) -> bool:
    return any(NGINX_SJABLONEN.glob(f"*-{app_id}.conf.template"))


def heeft_compose(app_id: str, bron: str) -> bool:
    return re.search(rf"^  app-{re.escape(app_id)}:\s*$", bron, re.MULTILINE) is not None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--uitleg", action="store_true",
                   help="toon per app waarom hij wel of niet meetelt")
    a = p.parse_args()

    try:
        apps = lees()
    except AppFout as fout:
        print(f"fout: {fout}", file=sys.stderr)
        return 2

    bron = COMPOSE.read_text(encoding="utf-8")
    for app in apps:
        if app.status != "active":
            if a.uitleg:
                print(f"{app.id}: overgeslagen, status {app.status}")
            continue
        nginx, compose = heeft_nginx(app.id), heeft_compose(app.id, bron)
        if nginx and compose:
            if a.uitleg:
                print(f"{app.id}: staat er al")
            continue
        if not app.poort:
            if a.uitleg:
                print(f"{app.id}: overgeslagen, geen poort in apps.yaml")
            continue
        if a.uitleg:
            mist = [n for n, aanwezig in (("nginx", nginx), ("compose", compose))
                    if not aanwezig]
            print(f"{app.id}: MIST {', '.join(mist)}")
        else:
            print(app.id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Zet een nieuwe app uit apps.yaml klaar: nginx-blok, compose-service en de
registratie in Authentik.

    python3 scripts/nieuwe-app.py mijnapp              # toont wat er zou gebeuren
    python3 scripts/nieuwe-app.py mijnapp --schrijf    # schrijft nginx en compose
    python3 scripts/nieuwe-app.py mijnapp --schrijf --registreer   # ook Authentik

De app moet eerst in apps.yaml staan, met minstens id, name, description,
subdomain, roles, status en poort. Dat is de pull request die de bouwer van de
app aanlevert; dit script doet de rest.

Wat dit script bewust NIET doet:

  Certificaten. Alle subdomeinen delen al een certificaat, dus daar is bij een
  nieuwe app niets te regelen.

  Bestaande bestanden overschrijven. Bestaat het nginx-blok of de
  compose-service al, dan stopt het script en zegt het wat het aantrof.

  De app op de VM starten. Dat is bewust een aparte handeling:
  docker compose up -d app-<id> && docker compose up -d --force-recreate nginx
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from appcatalogus import App, AppFout, zoek  # noqa: E402

WORTEL = pathlib.Path(__file__).resolve().parent.parent
NGINX_SJABLONEN = WORTEL / "nginx" / "templates"
COMPOSE = WORTEL / "docker-compose.override.yml"

NGINX_SJABLOON = """server {{
    listen 443 ssl;
    http2 on;
    server_name {subdomein}.${{BASE_DOMAIN}};
    include /etc/nginx/snippets/ssl.conf;

    # Forward-auth (embedded outpost) beschermt de hele app; identiteit en
    # groepen gaan als X-authentik-* headers naar de app, die daar zelf nog
    # eens {env_groepen} tegen aftoetst.
    set $app_upstream http://app-{app_id}:{poort};
    include /etc/nginx/snippets/forward-auth.conf;
}}
"""

COMPOSE_SJABLOON = """  app-{app_id}:
    build:
      context: ./{app_id}
      dockerfile: app/Dockerfile
    image: appportal-{app_id}
    restart: unless-stopped
    environment:
      PORT: "{poort}"
      BASE_DOMAIN: ${{BASE_DOMAIN:-globaal.be}}
      {env_groepen}: ${{{env_groepen}:-{groepen}}}
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:{poort}/healthz', timeout=5)"]
      interval: 2m
    networks: [appnet]
"""


def env_groepen(app: App) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", app.id.upper()) + "_GROUPS"


def volgende_prefix() -> int:
    """Het hoogste nummer dat nu in nginx/templates staat, plus een."""
    nummers = []
    for pad in NGINX_SJABLONEN.glob("*.conf.template"):
        kop = pad.name.split("-", 1)[0]
        if kop.isdigit():
            nummers.append(int(kop))
    return (max(nummers) + 1) if nummers else 30


def nginx_pad(app: App) -> pathlib.Path:
    bestaand = list(NGINX_SJABLONEN.glob(f"*-{app.id}.conf.template"))
    if bestaand:
        return bestaand[0]
    return NGINX_SJABLONEN / f"{volgende_prefix()}-{app.id}.conf.template"


def compose_bevat(app_id: str) -> bool:
    return re.search(rf"^  app-{re.escape(app_id)}:\s*$", COMPOSE.read_text(encoding="utf-8"),
                     re.MULTILINE) is not None


def voeg_compose_toe(blok: str) -> None:
    """Zet de service achteraan het services-blok, vóór de volgende top-level sleutel."""
    regels = COMPOSE.read_text(encoding="utf-8").splitlines(keepends=True)
    grens = len(regels)
    for i, regel in enumerate(regels):
        if i > 0 and re.match(r"^[a-z]", regel):
            grens = i
            break
    while grens > 0 and regels[grens - 1].strip() == "":
        grens -= 1
    regels[grens:grens] = ["\n"] + [r + "\n" for r in blok.rstrip("\n").split("\n")] + ["\n"]
    COMPOSE.write_text("".join(regels), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("app_id", help="id uit apps.yaml")
    p.add_argument("--schrijf", action="store_true",
                   help="schrijf het nginx-blok en de compose-service echt weg")
    p.add_argument("--registreer", action="store_true",
                   help="draai daarna ook app-registreren.py tegen Authentik")
    a = p.parse_args()

    try:
        app = zoek(a.app_id)
    except AppFout as fout:
        print(f"fout: {fout}", file=sys.stderr)
        return 2
    if not app.poort:
        print(f"fout: app {app.id} heeft geen 'poort' in apps.yaml; "
              "die is nodig voor nginx en compose.", file=sys.stderr)
        return 2

    velden = dict(app_id=app.id, subdomein=app.subdomein, poort=app.poort,
                  env_groepen=env_groepen(app), groepen=",".join(app.rollen))
    nginx_blok = NGINX_SJABLOON.format(**velden)
    compose_blok = COMPOSE_SJABLOON.format(**velden)
    doel = nginx_pad(app)

    bezwaren = []
    if doel.exists():
        bezwaren.append(f"{doel.relative_to(WORTEL)} bestaat al")
    if compose_bevat(app.id):
        bezwaren.append(f"app-{app.id} staat al in docker-compose.override.yml")

    print(f"# app      : {app.id} ({app.naam})")
    print(f"# adres    : {app.url}")
    print(f"# toegang  : {', '.join(app.rollen)}")
    if app.extra_groepen:
        print(f"# extra    : {', '.join(app.extra_groepen)} (aangemaakt, geen toegang)")
    print()
    print(f"# ---- {doel.relative_to(WORTEL)} ----")
    print(nginx_blok)
    print("# ---- docker-compose.override.yml ----")
    print(compose_blok)

    if bezwaren:
        for b in bezwaren:
            print(f"overgeslagen: {b}", file=sys.stderr)
        if a.schrijf:
            return 1

    if not a.schrijf:
        print("# niets weggeschreven. Gebruik --schrijf om dit toe te passen.")
        return 0

    doel.write_text(nginx_blok, encoding="utf-8")
    voeg_compose_toe(compose_blok)
    print(f"geschreven: {doel.relative_to(WORTEL)} en de service app-{app.id}")

    if a.registreer:
        klaar = subprocess.run(
            [sys.executable, str(WORTEL / "scripts" / "app-registreren.py"), app.id],
            cwd=WORTEL)
        if klaar.returncode != 0:
            return klaar.returncode

    print()
    print("Nog te doen op de VM:")
    print(f"  docker compose up -d app-{app.id}")
    print("  docker compose up -d --force-recreate nginx")
    if not a.registreer:
        print(f"  python3 scripts/app-registreren.py {app.id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

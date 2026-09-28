#!/usr/bin/env python3
"""Registreert een app uit apps.yaml in Authentik: provider, applicatie,
groepsbindingen en de embedded outpost.

Vervangt de losse add-<app>-app.py scripts. Wat per app verschilt staat in
apps.yaml, niet in code.

Draaien vanuit ~/appportal:

    python3 scripts/app-registreren.py hr --dry-run    # toont alleen wat er zou gebeuren
    python3 scripts/app-registreren.py hr              # voert het uit via ak-exec.sh

Bewust NIET in dit script:

  Gebruikers en wachtwoorden. Een aantal oude scripts maakte en passant een
  gebruiker aan met een tijdelijk wachtwoord in de uitvoer. Dat hoort niet in
  een registratiescript en gebeurt hier dus niet; gebruikers voeg je toe in
  Authentik.

Het script schrijft geen python naar de container die het niet eerst kan laten
zien: met --dry-run krijg je exact de code die anders zou draaien.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from appcatalogus import App, AppFout, lees, zoek  # noqa: E402

WORTEL = pathlib.Path(__file__).resolve().parent.parent
AK_EXEC = WORTEL / "scripts" / "ak-exec.sh"

# De code die in de Django-shell van authentik draait. Alles wat per app
# verschilt komt binnen als json, zodat er geen quoting-gedoe ontstaat.
SJABLOON = '''
import json

from authentik.core.models import Application, Group
from authentik.flows.models import Flow
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

app_gegevens = json.loads(r"""__GEGEVENS__""")
slug = app_gegevens["id"]
naam = app_gegevens["naam"]
url = app_gegevens["url"]
rollen = app_gegevens["rollen"]
extra_groepen = app_gegevens["extra_groepen"]

auth_flow = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
inval_flow = Flow.objects.filter(slug="default-provider-invalidation-flow").first()

proxy_defaults = dict(authorization_flow=auth_flow, mode="forward_single",
                      external_host=url)
if inval_flow:
    proxy_defaults["invalidation_flow"] = inval_flow
proxy, nieuw = ProxyProvider.objects.get_or_create(
    name=slug + "-proxy", defaults=proxy_defaults)
proxy.external_host = url
proxy.set_oauth_defaults()
proxy.save()
print("proxy " + slug + "-proxy: " + ("aangemaakt" if nieuw else "bestond al"))

app, nieuw = Application.objects.get_or_create(
    slug=slug, defaults=dict(name=naam, provider=proxy, meta_launch_url=url))
app.provider = proxy
app.name = naam
app.meta_launch_url = url
app.save()
print("applicatie " + slug + ": " + ("aangemaakt" if nieuw else "bijgewerkt")
      + ", launch-url " + url)

# Gebonden groepen: wie de app mag openen.
for groepsnaam in rollen:
    groep, _ = Group.objects.get_or_create(name=groepsnaam)
    PolicyBinding.objects.get_or_create(target=app, group=groep,
                                        defaults=dict(order=0))
print("gebonden groepen: " + ", ".join(rollen))

# Extra groepen: bestaan wel, geven op zichzelf geen toegang tot de app.
for groepsnaam in extra_groepen:
    Group.objects.get_or_create(name=groepsnaam)
if extra_groepen:
    print("extra groepen aangemaakt (niet gebonden): " + ", ".join(extra_groepen))

# Bestaande bindingen die niet in apps.yaml staan blijven staan; ze weghalen is
# een bewuste keuze en niet iets voor een registratiescript.
huidig = sorted(
    b.group.name for b in PolicyBinding.objects.filter(target=app) if b.group)
onverwacht = [g for g in huidig if g not in rollen]
if onverwacht:
    print("LET OP: ook gebonden, maar niet in apps.yaml: " + ", ".join(onverwacht))

outpost = Outpost.objects.filter(
    managed="goauthentik.io/outposts/embedded").first()
outpost.providers.add(proxy)
outpost.save()
print("embedded outpost: " + slug + "-proxy toegevoegd")
print("REGISTRATIE_KLAAR " + slug)
'''


def bouw_code(app: App) -> str:
    gegevens = dict(id=app.id, naam=app.naam, url=app.url,
                    rollen=app.rollen, extra_groepen=app.extra_groepen)
    # json in een raw triple-quoted string: geen backslash- of quote-verrassingen.
    tekst = json.dumps(gegevens, ensure_ascii=False)
    if '"""' in tekst or tekst.endswith("\\"):
        raise AppFout(f"app {app.id} bevat tekens die het sjabloon breken")
    return SJABLOON.replace("__GEGEVENS__", tekst)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("app_id", nargs="?", help="id uit apps.yaml, bijvoorbeeld hr")
    p.add_argument("--dry-run", action="store_true",
                   help="toon de code die in authentik zou draaien, voer niets uit")
    p.add_argument("--alle", action="store_true",
                   help="alle actieve apps uit apps.yaml, voor een controleronde")
    a = p.parse_args()

    if not a.app_id and not a.alle:
        p.error("geef een app_id of gebruik --alle")

    try:
        apps = [x for x in lees() if x.status == "active"] if a.alle else [zoek(a.app_id)]
    except AppFout as fout:
        print(f"fout: {fout}", file=sys.stderr)
        return 2

    for app in apps:
        code = bouw_code(app)
        if a.dry_run:
            print(f"# ==== {app.id} ({app.url}) ====")
            print(code)
            continue
        if not AK_EXEC.exists():
            print(f"fout: {AK_EXEC} ontbreekt", file=sys.stderr)
            return 2
        tijdelijk = WORTEL / f".app-registreren-{app.id}.py"
        tijdelijk.write_text(code, encoding="utf-8")
        try:
            klaar = subprocess.run(["sh", str(AK_EXEC), str(tijdelijk)], cwd=WORTEL)
        finally:
            tijdelijk.unlink(missing_ok=True)
        if klaar.returncode != 0:
            print(f"fout: registratie van {app.id} mislukt", file=sys.stderr)
            return klaar.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

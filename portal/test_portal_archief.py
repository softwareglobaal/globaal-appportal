"""Grendel: een app met status archived staat in het portaal apart onder Archive, grijs en nog te openen (live-toets 27-10-2026, X1 en G1).

Draait zonder Flask of Authentik: het sjabloon wordt rechtstreeks met Jinja2 gerenderd, url_for is een stub.
"""
import pathlib
import sys

import jinja2
import yaml

WORTEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORTEL / "scripts"))
import appcatalogus  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, info=""):
    global ok, fout
    if voorwaarde:
        ok += 1
    else:
        fout += 1
        print(f"FOUT: {naam} {info}")


def render(tiles):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(WORTEL / "portal" / "templates")))
    env.globals["url_for"] = lambda naam, **kw: f"/{naam}/{kw.get('app_id', '')}"
    return env.get_template("portal.html").render(tiles=tiles, is_admin=False, user={"name": "test"})


apps = yaml.safe_load((WORTEL / "apps.yaml").read_text(encoding="utf-8"))["apps"]
statussen = {a["status"] for a in apps}
check("alleen gekende statussen in apps.yaml", statussen <= {"active", "inactive", "in_development", "archived"}, statussen)
bs = {a["id"]: a for a in apps}
check("Barsten & Scheuren v1 staat op archief (Mehdi 27-10-2026)", bs["barstenscheuren"]["status"] == "archived")
check("Barsten & Scheuren v2 blijft actief", bs["barstenscheurenv2"]["status"] == "active")
check("de catalogus leest elke app nog", all(appcatalogus.App(a) for a in apps))

html = render([{"id": "nieuw", "name": "Nieuw", "description": "a", "status": "active"},
               {"id": "oud", "name": "Oud", "description": "b", "status": "archived"}])
kop = html.find("Archive")
check("er is een kop Archive", kop > 0, html)
check("de actieve tegel staat boven de kop", 0 < html.find("/go/nieuw") < kop, html)
check("de gearchiveerde tegel staat onder de kop, grijs", html.find('class="tile archived" href="/go/oud"') > kop, html)
html = render([{"id": "nieuw", "name": "Nieuw", "description": "a", "status": "active"}])
check("zonder gearchiveerde app geen kop Archive", "Archive" not in html, html)

print(f"{ok} ok, {fout} fout")
sys.exit(1 if fout else 0)

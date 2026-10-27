"""Grendel: een app met status archived is niet zichtbaar in het portaal (overleg 27-10-2026, X4 en G2).

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
check("de actieve tegel staat er", "/go/nieuw" in html, html)
check("de gearchiveerde tegel staat er niet", "/go/oud" not in html and "Oud" not in html, html)
html = render([{"id": "oud", "name": "Oud", "description": "b", "status": "archived"}])
check("alleen gearchiveerde apps: de gewone melding zonder tegels", "No applications are assigned" in html, html)

print(f"{ok} ok, {fout} fout")
sys.exit(1 if fout else 0)

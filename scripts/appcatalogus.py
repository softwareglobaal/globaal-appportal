"""Leest apps.yaml en levert per app de velden die de registratie nodig heeft.

Eén plek waar de betekenis van apps.yaml vastligt, zodat app-registreren.py,
nieuwe-app.py en vergelijk-authentik.py niet uit elkaar kunnen lopen.

Velden per app in apps.yaml:

  id             verplicht, de Authentik-slug en de naam van de compose-service
  name           verplicht, de naam op de tegel
  description    verplicht, de tekst onder de tegel
  subdomain      verplicht, <subdomain>.globaal.be tenzij host is gezet
  roles          verplicht, de groepen die de app MOGEN openen (policy bindings)
  status         verplicht, active of inactive
  extra_groepen  optioneel, groepen die wel worden aangemaakt maar NIET binden.
                 Bedoeld voor rechten die de app zelf aftoetst, zoals
                 vermogen-editors via EDITOR_GROUPS.
  host           optioneel, volledige hostnaam als die niet <subdomain>.globaal.be is
  poort          optioneel, interne poort; alleen nodig om nginx en compose te
                 genereren voor een nieuwe app
"""
from __future__ import annotations

import pathlib

import yaml

WORTEL = pathlib.Path(__file__).resolve().parent.parent
APPS_YAML = WORTEL / "apps.yaml"
STANDAARD_DOMEIN = "globaal.be"

VERPLICHT = ("id", "name", "description", "subdomain", "roles", "status")


class AppFout(Exception):
    """Een app in apps.yaml mist iets of klopt niet."""


class App:
    def __init__(self, rauw: dict, domein: str = STANDAARD_DOMEIN):
        ontbreekt = [v for v in VERPLICHT if v not in rauw]
        if ontbreekt:
            raise AppFout(f"app {rauw.get('id', '?')} mist: {', '.join(ontbreekt)}")
        self.id = str(rauw["id"])
        self.naam = str(rauw["name"])
        self.omschrijving = str(rauw["description"])
        self.subdomein = str(rauw["subdomain"])
        self.rollen = [str(r) for r in rauw["roles"]]
        self.status = str(rauw["status"])
        self.extra_groepen = [str(g) for g in rauw.get("extra_groepen", [])]
        self.host = str(rauw.get("host") or f"{self.subdomein}.{domein}")
        self.poort = rauw.get("poort")
        if not self.rollen:
            raise AppFout(f"app {self.id} heeft geen roles; dan mag niemand erbij")
        dubbel = set(self.rollen) & set(self.extra_groepen)
        if dubbel:
            raise AppFout(
                f"app {self.id}: {', '.join(sorted(dubbel))} staat in roles en in "
                "extra_groepen. Kies een van beide: roles bindt, extra_groepen niet."
            )

    @property
    def url(self) -> str:
        return f"https://{self.host}"

    @property
    def alle_groepen(self) -> list[str]:
        """Groepen die moeten bestaan: gebonden plus niet-gebonden."""
        return self.rollen + self.extra_groepen

    def __repr__(self) -> str:
        return f"<App {self.id} rollen={self.rollen} extra={self.extra_groepen}>"


def lees(pad: pathlib.Path | None = None, domein: str = STANDAARD_DOMEIN) -> list[App]:
    pad = pad or APPS_YAML
    rauw = yaml.safe_load(pad.read_text(encoding="utf-8"))
    if not rauw or "apps" not in rauw:
        raise AppFout(f"{pad} bevat geen sleutel 'apps'")
    apps = [App(a, domein) for a in rauw["apps"]]
    ids = [a.id for a in apps]
    dubbel = {i for i in ids if ids.count(i) > 1}
    if dubbel:
        raise AppFout(f"dubbele id's in apps.yaml: {', '.join(sorted(dubbel))}")
    return apps


def zoek(app_id: str, pad: pathlib.Path | None = None,
         domein: str = STANDAARD_DOMEIN) -> App:
    for app in lees(pad, domein):
        if app.id == app_id:
            return app
    bekend = ", ".join(a.id for a in lees(pad, domein))
    raise AppFout(f"app '{app_id}' staat niet in apps.yaml. Bekend: {bekend}")

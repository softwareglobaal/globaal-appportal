"""Medewerkers — forward-auth dashboard.

Toont de centrale medewerkerslijst (kern.persoon) en per persoon een 360-profiel.
Draait achter AppPortal's nginx forward-auth: identiteit + groepen komen uit de
`X-authentik-*`-headers (zoals het sso_auth.py-patroon). De Authentik group-binding
op de applicatie zorgt dat alleen 'admin'/'manager' de app überhaupt bereiken; deze
app dubbelcheckt dat nog eens uit de headers.
"""
import os

from flask import Flask, abort, render_template, request
from sqlalchemy import select

import authentik
import models
import telefoon

USER_HEADER = "X-Authentik-Username"
GROUPS_HEADER = "X-Authentik-Groups"
ADMIN_GROUP = os.environ.get("ADMIN_GROUP", "admin")
MANAGER_GROUP = os.environ.get("MANAGER_GROUP", "manager")

app = Flask(__name__)


@app.context_processor
def _inject():
    return {"base_domain": os.environ.get("BASE_DOMAIN", "globaal.be")}


def _username():
    return request.headers.get(USER_HEADER, "")


def _groups():
    raw = (request.headers.get(GROUPS_HEADER) or "").replace(",", "|")
    return {g.strip() for g in raw.split("|") if g.strip()}


def _require_staff():
    # Geen forward-auth header => app wordt direct (buiten nginx) benaderd: weigeren.
    if not _username():
        abort(403)
    groups = _groups()
    if not (ADMIN_GROUP in groups or MANAGER_GROUP in groups):
        abort(403)


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


@app.route("/")
def index():
    _require_staff()
    if models.Session is None:
        return render_template("index.html", username=_username(), groepen=[],
                               total=0, error="DATABASE_URL ontbreekt.")
    rolorder = {"Hoofd": 0, "Management": 1, "Lid": 2, "Partner": 3}
    with models.Session() as db:
        personen = list(db.scalars(select(models.Persoon)))
        personen.sort(key=lambda p: (p.afdeling.naam.lower(),
                                     rolorder.get(p.rol, 9), p.voornaam.lower()))
        groepen, huidige = [], None
        for p in personen:
            if huidige is None or huidige["naam"] != p.afdeling.naam:
                huidige = {"naam": p.afdeling.naam, "leden": []}
                groepen.append(huidige)
            huidige["leden"].append(p)
        return render_template("index.html", username=_username(), error=None,
                               groepen=groepen, total=len(personen))


@app.route("/<uuid:pid>")
def persoon(pid):
    _require_staff()
    if models.Session is None:
        abort(404)
    with models.Session() as db:
        p = db.get(models.Persoon, pid)
        if p is None:
            abort(404)
        # Toegang: groepen uit Authentik (read-only API) + daaruit afgeleide apps.
        ak_groepen = authentik.groepen_van(p.authentik_username) if p.authentik_sub else []
        ak_apps = authentik.apps_voor(ak_groepen)
        # Telefoonnummers: via de interne telefoonregister-API (best-effort).
        tel_nummers = telefoon.nummers_van(p.id)
        return render_template("persoon.html", username=_username(), p=p,
                               ak_groepen=ak_groepen, ak_apps=ak_apps,
                               ak_enabled=authentik.enabled,
                               tel_nummers=tel_nummers, tel_enabled=telefoon.enabled)

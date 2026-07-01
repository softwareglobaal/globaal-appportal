"""Medewerkers — forward-auth dashboard.

Toont de centrale medewerkerslijst (kern.persoon) en per persoon een 360-profiel.
Draait achter AppPortal's nginx forward-auth: identiteit + groepen komen uit de
`X-authentik-*`-headers. Alleen 'admin'/'manager' bereiken de app (Authentik
group-binding + check hier). Wijzigen (firma-koppeling) mag alleen 'admin', via de
smalle schrijf-engine.
"""
import os
import uuid

from flask import Flask, abort, redirect, render_template, request, url_for
from sqlalchemy import delete, insert, select, update

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


def _is_admin():
    return ADMIN_GROUP in _groups()


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
        # Firma's: hele actieve lijst voor de dropdowns + de huidige selectie.
        firmas = list(db.scalars(
            select(models.Firma).where(models.Firma.actief).order_by(models.Firma.naam)))
        dienst_ids = {f.id for f in p.dienst_firmas}
        return render_template(
            "persoon.html", username=_username(), p=p,
            ak_groepen=ak_groepen, ak_apps=ak_apps, ak_enabled=authentik.enabled,
            tel_nummers=tel_nummers, tel_enabled=telefoon.enabled,
            firmas=firmas, dienst_ids=dienst_ids,
            kan_bewerken=_is_admin() and models.WriteSession is not None)


@app.route("/<uuid:pid>/firmas", methods=["POST"])
def firmas_opslaan(pid):
    """Werkgever (uni) + diensten-voor (multi) opslaan — alleen admin."""
    _require_staff()
    if not _is_admin():
        abort(403)
    if models.WriteSession is None:
        abort(503)

    def _as_uuids(values):
        out = []
        for v in values:
            try:
                out.append(uuid.UUID(v))
            except (ValueError, TypeError, AttributeError):
                pass
        return out

    werkgever = _as_uuids([request.form.get("werkgever_firma_id") or ""])
    werkgever_id = werkgever[0] if werkgever else None
    diensten = _as_uuids(request.form.getlist("dienst_firma_ids"))

    with models.WriteSession() as db:
        # Gerichte kolom-update (schrijfrol heeft enkel UPDATE op werkgever_firma_id).
        db.execute(update(models.Persoon)
                   .where(models.Persoon.id == pid)
                   .values(werkgever_firma_id=werkgever_id))
        # Diensten resetten en opnieuw zetten.
        db.execute(delete(models.persoon_dienstfirma)
                   .where(models.persoon_dienstfirma.c.persoon_id == pid))
        for fid in diensten:
            db.execute(insert(models.persoon_dienstfirma)
                       .values(persoon_id=pid, firma_id=fid))
        db.commit()
    return redirect(url_for("persoon", pid=pid))

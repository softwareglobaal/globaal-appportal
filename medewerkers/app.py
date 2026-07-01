"""Medewerkers — forward-auth dashboard.

Toont de centrale medewerkerslijst (kern.persoon) en per persoon een 360-profiel.
Draait achter AppPortal's nginx forward-auth: identiteit + groepen komen uit de
`X-authentik-*`-headers. Alleen 'admin'/'manager' bereiken de app (Authentik
group-binding + check hier). Wijzigen (firma-koppeling) mag alleen 'admin', via de
smalle schrijf-engine; elke schrijfactie wordt gelogd (audit).
"""
import logging
import os
import uuid
from urllib.parse import urlparse

from flask import Flask, abort, redirect, render_template, request, url_for
from sqlalchemy import delete, func, insert, select, update

import authentik
import models
import telefoon

USER_HEADER = "X-Authentik-Username"
GROUPS_HEADER = "X-Authentik-Groups"
ADMIN_GROUP = os.environ.get("ADMIN_GROUP", "admin")
MANAGER_GROUP = os.environ.get("MANAGER_GROUP", "manager")

app = Flask(__name__)

# Audit-log naar stdout (komt in `docker compose logs`): wie deed wat wanneer.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
events = logging.getLogger("medewerkers.events")


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
        events.warning("ACCESS_DENIED user=%s path=%s", _username(), request.path)
        abort(403)


def _is_admin():
    return ADMIN_GROUP in _groups()


def _require_same_origin():
    """CSRF-bescherming op schrijfacties: de POST moet van onze eigen pagina komen.

    Alle *.<domein>-apps zijn same-site, dus SameSite-cookies alleen beschermen niet
    tegen een kwaadwillende POST vanaf een ander subdomein. Browsers sturen bij een
    POST altijd een Origin (of minstens Referer) mee; ontbreken beide, of wijst de
    herkomst niet naar deze host, dan weigeren we.
    """
    herkomst = request.headers.get("Origin") or request.headers.get("Referer") or ""
    if not herkomst or urlparse(herkomst).netloc != request.host:
        events.warning("CSRF_REJECT user=%s path=%s herkomst=%s",
                       _username(), request.path, herkomst or "-")
        abort(403)


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


@app.route("/")
def index():
    _require_staff()
    if models.Session is None:
        return render_template("index.html", username=_username(), personen=[],
                               afdelingen=[], total=0, tab="medewerkers",
                               error="DATABASE_URL ontbreekt.")
    with models.Session() as db:
        # Platte lijst op naam; filteren en groeperen (afdeling/rol) doet de client.
        personen = list(db.scalars(select(models.Persoon)))
        personen.sort(key=lambda p: p.volledige_naam.lower())
        afdelingen = sorted({p.afdeling.naam for p in personen})
        return render_template("index.html", username=_username(), error=None,
                               personen=personen, afdelingen=afdelingen,
                               total=len(personen), tab="medewerkers")


@app.route("/<uuid:pid>")
def persoon(pid):
    _require_staff()
    if models.Session is None:
        abort(404)
    with models.Session() as db:
        p = db.get(models.Persoon, pid)
        if p is None:
            abort(404)
        # Toegang: groepen uit Authentik (read-only API, lookup op sub) + afgeleide apps.
        ak_groepen = (authentik.groepen_van(p.authentik_sub, p.authentik_username)
                      if p.authentik_sub else [])
        ak_apps = authentik.apps_voor(ak_groepen)
        # Telefoonnummers: via de interne telefoonregister-API (best-effort).
        tel_nummers = telefoon.nummers_van(p.id)
        # Firma's: hele actieve lijst voor de dropdowns + de huidige selectie.
        firmas = list(db.scalars(
            select(models.Firma).where(models.Firma.actief).order_by(models.Firma.naam)))
        dienst_ids = {f.id for f in p.dienst_firmas}
        return render_template(
            "persoon.html", username=_username(), p=p, tab="medewerkers",
            ak_groepen=ak_groepen, ak_apps=ak_apps, ak_enabled=authentik.enabled,
            tel_nummers=tel_nummers, tel_enabled=telefoon.enabled,
            firmas=firmas, dienst_ids=dienst_ids,
            kan_bewerken=_is_admin() and models.WriteSession is not None)


@app.route("/<uuid:pid>/firmas", methods=["POST"])
def firmas_opslaan(pid):
    """Werkgever (uni) + diensten-voor (multi) opslaan — alleen admin, same-origin."""
    _require_staff()
    if not _is_admin():
        events.warning("WRITE_DENIED user=%s persoon=%s", _username(), pid)
        abort(403)
    _require_same_origin()
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
    events.info("FIRMA_UPDATE user=%s persoon=%s werkgever=%s diensten=%s",
                _username(), pid, werkgever_id,
                ",".join(str(f) for f in diensten) or "-")
    return redirect(url_for("persoon", pid=pid))


# ---------------------------------------------------------------------------
# Firma's-tab (Organisatie): lijst, profiel en admin-beheer.
# ---------------------------------------------------------------------------

@app.route("/firmas")
def firmas_lijst():
    _require_staff()
    if models.Session is None:
        abort(503)
    with models.Session() as db:
        firmas = list(db.scalars(select(models.Firma).order_by(models.Firma.naam)))
        wg = dict(db.execute(
            select(models.Persoon.werkgever_firma_id, func.count())
            .where(models.Persoon.in_dienst,
                   models.Persoon.werkgever_firma_id.is_not(None))
            .group_by(models.Persoon.werkgever_firma_id)).all())
        dn = dict(db.execute(
            select(models.persoon_dienstfirma.c.firma_id, func.count())
            .group_by(models.persoon_dienstfirma.c.firma_id)).all())
    comm = telefoon.tellingen_per_firma()
    return render_template("firmas.html", username=_username(), tab="firmas",
                           firmas=firmas, wg=wg, dn=dn, comm=comm,
                           fout=request.args.get("fout", ""),
                           kan_beheren=_is_admin() and models.WriteSession is not None)


@app.route("/firmas/<uuid:fid>")
def firma_detail(fid):
    _require_staff()
    if models.Session is None:
        abort(404)
    with models.Session() as db:
        f = db.get(models.Firma, fid)
        if f is None:
            abort(404)
        in_dienst = list(db.scalars(
            select(models.Persoon)
            .where(models.Persoon.werkgever_firma_id == fid, models.Persoon.in_dienst)))
        in_dienst.sort(key=lambda p: p.voornaam.lower())
        diensten = list(db.scalars(
            select(models.Persoon)
            .join(models.persoon_dienstfirma,
                  models.persoon_dienstfirma.c.persoon_id == models.Persoon.id)
            .where(models.persoon_dienstfirma.c.firma_id == fid,
                   models.Persoon.in_dienst)))
        diensten.sort(key=lambda p: p.voornaam.lower())
        kop = telefoon.firma_koppelingen(fid)
        return render_template("firma.html", username=_username(), tab="firmas",
                               f=f, in_dienst=in_dienst, diensten=diensten,
                               nummers_factuur=kop["factuur"],
                               nummers_doorfactuur=kop["doorfactuur"],
                               emails=kop["emails"],
                               fout=request.args.get("fout", ""),
                               kan_beheren=_is_admin() and models.WriteSession is not None)


@app.route("/firmas/nieuw", methods=["POST"])
def firma_nieuw():
    """Firma toevoegen — alleen admin, same-origin."""
    _require_staff()
    if not _is_admin():
        abort(403)
    _require_same_origin()
    if models.WriteSession is None:
        abort(503)
    naam = (request.form.get("naam") or "").strip()
    code = (request.form.get("code") or "").strip().upper()
    land = (request.form.get("land") or "").strip()
    if not (naam and code and land):
        return redirect(url_for("firmas_lijst", fout="Naam, code en land zijn verplicht."))
    try:
        with models.WriteSession() as db:
            db.execute(insert(models.Firma).values(
                naam=naam, code=code, land=land, actief=True))
            db.commit()
    except Exception:
        return redirect(url_for("firmas_lijst",
                                fout=f"Naam of code '{code}' bestaat al."))
    events.info("FIRMA_NIEUW user=%s naam=%s code=%s land=%s",
                _username(), naam, code, land)
    return redirect(url_for("firmas_lijst"))


@app.route("/firmas/<uuid:fid>/bewerken", methods=["POST"])
def firma_bewerken(fid):
    """Naam/code/land/actief bijwerken — alleen admin, same-origin."""
    _require_staff()
    if not _is_admin():
        abort(403)
    _require_same_origin()
    if models.WriteSession is None:
        abort(503)
    naam = (request.form.get("naam") or "").strip()
    code = (request.form.get("code") or "").strip().upper()
    land = (request.form.get("land") or "").strip()
    actief = request.form.get("actief") == "on"
    if not (naam and code and land):
        return redirect(url_for("firma_detail", fid=fid,
                                fout="Naam, code en land zijn verplicht."))
    try:
        with models.WriteSession() as db:
            db.execute(update(models.Firma).where(models.Firma.id == fid)
                       .values(naam=naam, code=code, land=land, actief=actief))
            db.commit()
    except Exception:
        return redirect(url_for("firma_detail", fid=fid,
                                fout="Naam of code botst met een andere firma."))
    events.info("FIRMA_BEHEER user=%s firma=%s naam=%s code=%s land=%s actief=%s",
                _username(), fid, naam, code, land, actief)
    return redirect(url_for("firma_detail", fid=fid))

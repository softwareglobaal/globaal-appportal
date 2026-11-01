"""De foto's van een dag per project (dagboek.globaal.be/fotos/<dag>, T-0120 FOTO-5).

Mehdi, 01-11-2026: "voor de fotos zijn de projecten van de bedrijven belangrijk niet de fotos van de mensen" en "ik wil
elke foto en elke file van wachter kunnen zien en begrijpen". Deze pagina leest alleen de indeling die De Fotowacht op de
VM schrijft (mijnagents-runner/koppelingen/fotoindeling.py: mijnagents-data/fotoindeling/<jaar>/<dag>.json) en de kleine
voorvertoningen van werkfoto's (mijnagents-data/fotovoorbeeld/<dag>/<id>.jpg, via mijnagents/fotovoorbeeld.py). Beide
staan alleen op de VM, nooit in Dropbox, en worden hier alleen gelezen.

Per werfgroep: firma, nummer, project, de afspraak of de auto bij het project, de tijden en de voorvertoningen. Een
kandidaat (alleen bij een projectplek) staat apart, zonder beeld. Privé, mensen, scherm en onbeslist alleen als telling:
geen plaats, geen tijd, geen beeld. Een voorvertoning wordt alleen gegeven als de indeling van die dag haar als
werkfoto zonder mensen aanwijst. Toegang: Authentik en de groep van het Dagboek (dezelfde mag() als de app).
"""
import json
import os
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import abort, redirect, render_template, send_file, url_for

INDELING = os.environ.get("FOTOINDELING_MAP", "/fotoindeling")
VOORBEELD = os.environ.get("FOTOVOORBEELD_MAP", "/fotovoorbeeld")
VANAF = date(2026, 10, 1)            # terugkijken vanaf 01-10 (Mehdi 01-11, overleg X4)
ID = re.compile(r"^[0-9A-Za-z-]{1,64}$")


def vandaag():
    return datetime.now(ZoneInfo("Europe/Brussels")).date()


def dag_uit(dag):
    try:
        d = date.fromisoformat(dag)
    except ValueError:
        abort(404)
    if not VANAF <= d <= vandaag():
        abort(404)
    return d


def indeling(dag):
    """De indeling van die dag, of None (nog niet ingedeeld: onbekend, niet leeg)."""
    try:
        with open(os.path.join(INDELING, dag[:4], f"{dag}.json"), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and d.get("datum") == dag else None


def met_voorbeeld(ind):
    """Zet per foto of er een voorvertoning op de VM staat; alleen voor een werkfoto die de indeling toelaat."""
    for g in ind.get("werf") or []:
        for f in g.get("fotos") or []:
            f["beeld"] = bool(f.get("voorbeeld") is True and ID.fullmatch(str(f.get("id") or ""))
                              and os.path.isfile(os.path.join(VOORBEELD, ind["datum"], f"{f['id']}.jpg")))
    return ind


def registreer(app, mag):
    """mag: de toegangscontrole van het Dagboek (dagboek/app.py)."""

    @app.route("/fotos")
    def fotos_start():
        if not mag():
            abort(403)
        return redirect(url_for("fotos_dag", dag=(vandaag() - timedelta(days=1)).isoformat()))

    @app.route("/fotos/<dag>")
    def fotos_dag(dag):
        if not mag():
            abort(403)
        d = dag_uit(dag)
        ind = indeling(dag)
        vorige, volgende = d - timedelta(days=1), d + timedelta(days=1)
        return render_template("fotos.html", ind=met_voorbeeld(ind) if ind else None, dag=dag,
                               naam=f"{d.day}-{d.month}-{d.year}",
                               vorige=vorige.isoformat() if vorige >= VANAF else None,
                               volgende=volgende.isoformat() if volgende <= vandaag() else None)

    @app.route("/fotos/<dag>/voorbeeld/<fid>.jpg")
    def fotos_voorbeeld(dag, fid):
        if not mag():
            abort(403)
        dag_uit(dag)
        ind = indeling(dag)
        if not ind or not ID.fullmatch(fid) or not any(
                f.get("id") == fid and f.get("voorbeeld") is True for g in ind.get("werf") or [] for f in g.get("fotos") or []):
            abort(404)
        pad = os.path.join(VOORBEELD, dag, f"{fid}.jpg")
        if not os.path.isfile(pad):
            abort(404)
        antwoord = send_file(pad, mimetype="image/jpeg")
        antwoord.headers["Cache-Control"] = "private, max-age=3600"
        return antwoord

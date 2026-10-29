"""Postbus: leestoegang tot zakelijke mailboxen voor Claude (MCP), plus een
kleine pagina achter Authentik-SSO die laat zien wat jij mag lezen.

De webpagina is bewust klein: dit is geen mailclient. Ze bestaat om drie
redenen. Ze toont welke mailboxen jouw Authentik-login opent (zodat een
gebruiker niet hoeft te gissen), ze is de loginstap van de OAuth-koppeling
(/oauth/authorize valt onder dezelfde forward-auth), en ze geeft de beheerder
een controleknop die per mailbox echt inlogt op IMAP.

Lezen gebeurt in imapbron.py, de toegangsregels staan in config.py, het
MCP-endpoint in mcp_server.py.
"""
import io
import os
import re
from urllib.parse import urlsplit

from flask import (Flask, redirect, render_template, request, send_file,
                   url_for)

import bijlagen
import config
import imapbron
import mcp_server

app = Flask(__name__)

# De rechten van een mailbox worden op één plek bepaald (config.rechten), zodat
# de pagina en het antwoord aan Claude nooit uit elkaar kunnen lopen.
app.jinja_env.globals["rechten"] = config.rechten

BEHEER_GROEPEN = [g.strip().lower() for g in
                  os.environ.get("POSTBUS_BEHEER_GROEPEN", "admin").split(",")
                  if g.strip()]


def _gebruiker():
    for h in ("X-Authentik-Username", "X-Forwarded-Preferred-Username",
              "Remote-User"):
        waarde = request.headers.get(h, "").strip()
        if waarde:
            return waarde
    return ""


def _groepen():
    ruw = request.headers.get("X-Authentik-Groups", "")
    return [g.strip().lower()
            for g in ruw.replace("|", ",").split(",") if g.strip()]


def _wie():
    return {"gebruiker": _gebruiker(), "groepen": _groepen()}


def _is_beheer(wie):
    return bool(set(wie["groepen"]) & set(BEHEER_GROEPEN))


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/")
def index():
    wie = _wie()
    mijn = config.voor(wie)
    alle, fouten = config.alles()
    beheer = _is_beheer(wie)
    return render_template(
        "index.html",
        wie=wie,
        mijn=mijn,
        beheer=beheer,
        # Alleen een beheerder ziet mailboxen waar die zelf niet bij mag; voor
        # de rest zou dat een lijst zijn van adressen die hen niets aangaan.
        alle=alle if beheer else [],
        fouten=fouten if beheer else [],
        wijzigingen=config.wijzigingen(20) if beheer else [],
        toegang_beheer=bool(config.beheerbaar(wie)),
        pad=config.PAD,
        basis=mcp_server._basis(),
        oauth_aan=bool(mcp_server._secret()),
        token_aan=bool(mcp_server._statisch_token()),
        token_groepen=mcp_server._token_groepen(),
    )


@app.post("/controle")
def controle():
    """Beheerderscheck: logt per mailbox echt in en telt de INBOX."""
    wie = _wie()
    if not _is_beheer(wie):
        return {"fout": "Alleen voor beheerders"}, 403
    uit = []
    alle, _ = config.alles()
    for m in alle:
        try:
            gegevens = imapbron.mappen(m)
            uit.append({"mailbox": m["adres"], "ok": True,
                        "mappen": len(gegevens["alle_mappen"]),
                        "leesbaar": len(gegevens["leesbaar"])})
        except Exception as e:
            uit.append({"mailbox": m["adres"], "ok": False,
                        "melding": f"{type(e).__name__}: {e}"})
    return {"gecontroleerd": len(uit), "resultaten": uit}


def _zelfde_herkomst():
    """Een formulier mag alleen van deze site zelf komen (geen CSRF).

    De forward-auth-cookie gaat bij elk verzoek mee; zonder deze toets kan een
    andere site een ingelogde beheerder ongemerkt een wijziging laten posten.
    """
    bron = request.headers.get("Origin") or request.headers.get("Referer")
    if not bron:
        return False
    return urlsplit(bron).netloc.lower() == request.host.lower()


def _toegang_pagina(wie, melding=None, fout=None, status=200):
    mijn = config.beheerbaar(wie)
    rijen = [{"m": m, "nu": config.huidige_toegang(m)} for m in mijn]
    return render_template(
        "toegang.html", wie=wie, rijen=rijen, melding=melding, fout=fout,
        wijzigingen=config.wijzigingen(
            30, {m["adres"].lower() for m in mijn}),
    ), status


@app.get("/toegang")
def toegang():
    """Mailbox-beheerders (beheer: in mailboxen.yaml) wijzigen hier wie erbij mag."""
    wie = _wie()
    if not config.beheerbaar(wie):
        return _toegang_pagina(wie, status=403)
    return _toegang_pagina(wie, melding=request.args.get("ok"))


@app.post("/toegang")
def toegang_wijzigen():
    wie = _wie()
    if not _zelfde_herkomst():
        return _toegang_pagina(wie, fout="Geweigerd: dit formulier kwam niet "
                               "van post.globaal.be zelf", status=403)
    adres = request.form.get("adres", "")
    invoer = {"groepen": request.form.get("groepen", ""),
              "personen": request.form.get("personen", "")}
    for veld in config.RECHT_VELDEN:
        keuze = request.form.get(veld, "nee")
        invoer[veld] = (request.form.get(veld + "_namen", "")
                        if keuze == "namen" else keuze)
    try:
        oud, nieuw = config.zet_toegang(adres, invoer, wie)
    except ValueError as e:
        return _toegang_pagina(wie, fout=f"{adres}: {e}", status=400)
    tekst = ("niets veranderd" if oud == nieuw
             else "opgeslagen, geldt binnen enkele seconden")
    return redirect(url_for("toegang", ok=f"{adres}: {tekst}"), code=303)


def _veilige_naam(naam):
    """Bestandsnaam zoals de afzender hem gaf, zonder pad of stuurtekens."""
    naam = re.sub(r"[\x00-\x1f\x7f/\\]", "_", str(naam or "")).strip(" .")
    return naam or "bijlage"


@app.get("/download/<token>")
@app.get("/download/<token>/<int:nr>")
def download(token, nr=None):
    """Een downloadlink uit de tool bijlage_link.

    Staat achter de forward-auth en werkt alleen voor wie de link maakte,
    en alleen zolang die de mailbox en het recht bijlagen nog heeft. Het
    bestand gaat altijd als download de deur uit (nooit getoond op dit
    domein), zodat een html-bijlage hier geen code kan draaien.
    """
    wie = _wie()
    p = mcp_server._lees(token, "dl")
    if not p:
        return render_template("download.html", wie=wie, fout=(
            "Deze link is verlopen of ongeldig. Vraag Claude om een nieuwe."
        )), 403
    if wie["gebruiker"].lower() != str(p.get("u", "")).lower():
        return render_template("download.html", wie=wie, fout=(
            f"Deze link is gemaakt voor {p.get('u')}, niet voor "
            f"{wie['gebruiker'] or 'deze login'}.")), 403
    try:
        mailbox = config.zoek(p["m"], wie)
        config.vereis_bijlagen(mailbox, wie)
        mapnaam = config.map_toegestaan(mailbox, p["f"])
        koppen, delen = imapbron.bijlagen(mailbox, mapnaam, p["i"])
    except ValueError as e:
        return render_template("download.html", wie=wie, fout=str(e)), 403
    if p.get("b"):
        nr = p["b"] if nr in (None, p["b"]) else -1
    if nr is None:
        return render_template("download.html", wie=wie, token=token,
                               koppen=koppen, mailbox=mailbox["adres"],
                               bestanden=bijlagen.overzicht(delen))
    gekozen = next((d for d in delen if d[0] == nr), None)
    if gekozen is None:
        return render_template("download.html", wie=wie,
                               fout="Die bijlage hoort niet bij deze link."), 404
    _, naam, _, inhoud = gekozen
    mcp_server._log(wie, f"download {mailbox['adres']}/{mapnaam} "
                         f"uid={p['i']} nr={nr} ({len(inhoud)} bytes)")
    antwoord = send_file(io.BytesIO(inhoud),
                         mimetype="application/octet-stream",
                         as_attachment=True,
                         download_name=_veilige_naam(naam))
    antwoord.headers["X-Content-Type-Options"] = "nosniff"
    antwoord.headers["Content-Security-Policy"] = "sandbox"
    antwoord.headers["Cache-Control"] = "no-store"
    return antwoord


mcp_server.registreer(app, _gebruiker, _groepen)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "3017")))

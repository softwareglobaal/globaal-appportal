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
import os

from flask import Flask, render_template, request

import config
import imapbron
import mcp_server

app = Flask(__name__)

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


mcp_server.registreer(app, _gebruiker, _groepen)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "3017")))

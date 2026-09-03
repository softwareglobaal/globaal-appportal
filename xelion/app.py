"""Xelion-tegel: beheerpagina achter SSO, plus de MCP-server op /mcp.

De pagina toont wat de ingelogde persoon met Xelion mag en of de verbinding
staat. Wijzigen doe je in ~/xelion-config/rechten.yaml op de VM; die wordt elke
vijf seconden herlezen.
"""
import os

from flask import Flask, render_template, request

import config
import mcp_server
import xelionbron

app = Flask(__name__)

# Dezelfde kopregels als de andere tegels achter de forward-auth.
KOP_GEBRUIKER = os.environ.get("AUTH_USER_HEADER", "X-Authentik-Username")
KOP_GROEPEN = os.environ.get("AUTH_GROUPS_HEADER", "X-Authentik-Groups")


def gebruiker():
    return (request.headers.get(KOP_GEBRUIKER) or "").strip()


def groepen_van_verzoek():
    ruw = request.headers.get(KOP_GROEPEN) or ""
    scheiding = "|" if "|" in ruw else ","
    return [g.strip().lower() for g in ruw.split(scheiding) if g.strip()]


@app.get("/gezond")
def gezond():
    return {"status": "ok"}


@app.get("/")
def start():
    naam = gebruiker()
    rechten, fout = config.rechten(naam, groepen_van_verzoek())
    return render_template("start.html", gebruiker=naam, rechten=rechten,
                           fout=fout, basis=_basis())


@app.post("/verbinding-testen")
def verbinding_testen():
    """Logt echt in op Xelion. Alleen voor wie mag lezen."""
    naam = naam_of_leeg()
    if not config.mag(naam, groepen_van_verzoek(), "lezen"):
        return {"ok": False, "melding": "Je hebt geen leesrecht op Xelion."}, 403
    try:
        rijen = xelionbron.BRON.zoek_contacten("a", 1)
        return {"ok": True,
                "melding": "Verbinding werkt (%s contact opgehaald)." % len(rijen)}
    except Exception as e:
        return {"ok": False, "melding": "%s: %s" % (type(e).__name__, e)}


def naam_of_leeg():
    return gebruiker()


def _basis():
    sub = os.environ.get("XELION_SUBDOMEIN", "xelion")
    return "https://%s.%s" % (sub, os.environ.get("BASE_DOMAIN", "globaal.be"))


mcp_server.registreer(app, gebruiker, groepen_van_verzoek)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "3019")))

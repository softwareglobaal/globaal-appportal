"""Publieke demo: zoeken in een document dat wij hebben klaargezet.

Draait op elevaitnv.com/demo.

Eerder mocht de bezoeker zelf een PDF aanleveren. Dat is er op 31-08-2026 uit
gehaald op verzoek van Mehdi, en de redenering daarachter is de moeite waard om
vast te leggen, want ze komt vast terug:

  Een demo waarin de bezoeker zijn eigen bestand moet zoeken, uploaden en
  afwachten, vraagt werk voordat er iets te zien is. De meesten haken af voor
  ze iets geleerd hebben. Erger nog: als hun document toevallig slecht valt
  (een scan zonder tekstlaag, een rommelige opmaak) dan is hun eerste indruk
  van ons product een foutmelding.

  Een document dat al klaarstaat toont binnen vijf seconden wat het ding doet.
  Wie het daarna met eigen stukken wil proberen, neemt contact op, en dat is
  precies het gesprek dat we willen.

Daarmee verdwijnt ook de hele machinerie eromheen: geen uploadlimiet, geen
wachtrij, geen daglimiet per IP, geen tijdelijke opslag. Er valt niets te
misbruiken aan een zoekvenster over een vaste database, en er wordt van de
bezoeker niets bewaard omdat er niets binnenkomt.

De kennisbank zelf is vooraf gebouwd met dezelfde keten als de betaalde app;
DEMO_DB wijst hem aan.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from flask import (Flask, abort, redirect, render_template, request,
                   send_from_directory, url_for)

from kennisbank.opslag import Kennisbank

DB_PAD = Path(os.environ.get("DEMO_DB", "/app/data/demo.db"))
# Waar de bezoeker terechtkomt als hij dit met zijn eigen stukken wil.
CONTACT = os.environ.get("DEMO_CONTACT", "https://elevaitnv.com/#contact")

app = Flask(__name__)


class OnderVoorvoegsel:
    """Laat de app onder /demo leven zonder dat de routes dat hoeven te weten.

    Nginx stuurt het pad ongewijzigd door, dus zonder dit ziet Flask
    "/demo/f/12" en herkent hij zijn eigen route niet. Met SCRIPT_NAME klopt
    ook url_for(): die zet het voorvoegsel er weer voor, zodat elke link op de
    juiste plek uitkomt.
    """

    def __init__(self, wsgi, voorvoegsel: str = ""):
        self.wsgi = wsgi
        self.voorvoegsel = "/" + voorvoegsel.strip("/") if voorvoegsel.strip("/") else ""

    def __call__(self, omgeving, start):
        pad = omgeving.get("PATH_INFO", "")
        if self.voorvoegsel and pad.startswith(self.voorvoegsel):
            omgeving["SCRIPT_NAME"] = self.voorvoegsel
            omgeving["PATH_INFO"] = pad[len(self.voorvoegsel):] or "/"
        return self.wsgi(omgeving, start)


app.wsgi_app = OnderVoorvoegsel(app.wsgi_app, os.environ.get("VOORVOEGSEL", "demo"))


# ---------------------------------------------------------------- opwarmen

_gereed = threading.Event()


def _warm_op() -> None:
    """Het embedmodel laden voor de eerste bezoeker het nodig heeft.

    Dit draait bewust in een thread en niet bij de import: het model kost ruim
    tien seconden en zolang het laadt is de poort nog niet gebonden. Wie in dat
    gat aanklopt krijgt een 502 in plaats van een pagina. Let op dat gunicorn
    hier zonder --preload draait, anders start deze thread in de master en niet
    in de worker die de verzoeken afhandelt.
    """
    try:
        from kennisbank import vectoren
        vectoren.embed_een("opwarmen")
        print("embedmodel opgewarmd", flush=True)
    except Exception as e:                                     # noqa: BLE001
        print(f"opwarmen mislukt: {e}", flush=True)
    finally:
        _gereed.set()


threading.Thread(target=_warm_op, daemon=True).start()


# ---------------------------------------------------------------- kennisbank

_bank: Kennisbank | None = None
_bank_slot = threading.Lock()


def bank() -> Kennisbank:
    """De kennisbank, eenmalig geopend en daarna hergebruikt."""
    global _bank
    with _bank_slot:
        if _bank is None:
            if not DB_PAD.exists():
                raise FileNotFoundError(f"geen demo-kennisbank op {DB_PAD}")
            _bank = Kennisbank(DB_PAD)
        return _bank


def _info() -> dict:
    d = dict(bank().info())
    d["contact"] = CONTACT
    return d


# ---------------------------------------------------------------- schermen

@app.route("/")
def start():
    if not _gereed.is_set():
        # Nog aan het opwarmen. Een pagina die zichzelf ververst is eerlijker
        # dan een verzoek dat dertig seconden blijft hangen.
        return render_template("wachten.html"), 503
    vraag = (request.args.get("v") or "").strip()
    treffers = bank().zoek(vraag, k=8) if vraag else []
    info = _info()
    # De inhoudsopgave-controle is onze sterkste maat, maar alleen bij een
    # document dat er een heeft. Een wettekst zonder inhoudsopgave levert een
    # laag getal op dat niets over de verwerking zegt; dan liever niets tonen
    # dan een cijfer dat de lezer verkeerd uitlegt.
    return render_template("demo.html", info=info, vraag=vraag,
                           treffers=treffers,
                           aantal=bank().aantal_fragmenten(),
                           toon_trefkans=(info.get("trefkans") or 0) >= 0.5)


@app.route("/f/<int:fid>")
def fragment(fid: int):
    f = bank().fragment(fid)
    if f is None:
        abort(404)
    return render_template("fragment.html", f=f, info=_info())


# De factuurrouter-demo is een vaste run: statische HTML met een afbeelding per
# document, gebouwd op een andere machine en hier alleen neergezet. Geen model,
# geen postbus, geen verzendcode. Hij hangt onder deze app omdat /demo al
# geproxyd wordt; daarmee hoeft er aan nginx niets te veranderen.
FACTUURROUTER = Path(os.environ.get("FACTUURROUTER_PAD", "/app/data/factuurrouter"))


@app.route("/factuurrouter")
def factuurrouter_zonder_slash():
    # De pagina gebruikt relatieve paden (documenten/, fonts/). Zonder slash
    # lost de browser die op tegen /demo/ en laadt er niets. Vandaar de 308.
    return redirect(url_for("factuurrouter"), code=308)


@app.route("/factuurrouter/")
def factuurrouter():
    if not (FACTUURROUTER / "index.html").exists():
        abort(404)
    return send_from_directory(FACTUURROUTER, "index.html")


@app.route("/factuurrouter/<path:bestand>")
def factuurrouter_bestand(bestand: str):
    # send_from_directory weigert zelf alles buiten de map, dus een pad met ..
    # komt hier niet doorheen.
    return send_from_directory(FACTUURROUTER, bestand)


@app.route("/gezond")
def gezond():
    return {"ok": _gereed.is_set(), "kennisbank": DB_PAD.exists(),
            "factuurrouter": (FACTUURROUTER / "index.html").exists()}


@app.errorhandler(404)
def weg(_):
    return redirect(url_for("start"))


@app.template_filter("procent")
def procent(x):
    try:
        return f"{float(x) * 100:.0f}%"
    except (TypeError, ValueError):
        return "-"

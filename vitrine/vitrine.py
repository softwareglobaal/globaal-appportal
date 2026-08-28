"""Vitrine: de resultaten van één verwerkt boek, om te bekijken en beoordelen.

Read-only. Geen upload, geen accounts, geen tegoed. De toegang wordt buiten de
app geregeld door de forward-auth van de portal, precies zoals bij de andere
tegels; wie hier komt is dus al ingelogd.

Drie schermen:
  /         het boek, de metingen en een zoekbalk
  /proces   hoe deze resultaten tot stand kwamen, stap voor stap
  /fragment een los fragment in zijn geheel

De zoekmachine is dezelfde als die de kennisbank bouwde (kennisbank/opslag.py),
met hetzelfde lokale embedmodel: corpus en zoekvraag moeten door dezelfde rug.
Het model wordt bij de start opgewarmd, zodat de eerste bezoeker niet wacht.
"""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path

from flask import Flask, abort, render_template, request

from kennisbank.opslag import Kennisbank

KB_PAD = Path(os.environ.get("KB_PAD", "/data/kennisbank.db"))
RAPPORT_PAD = Path(os.environ.get("RAPPORT_PAD", "/data/rapport.json"))
VERSIES_PAD = Path(os.environ.get("VERSIES_PAD", "/data/versies.json"))

VOORBEELDVRAGEN = [
    "Wanneer is een constructie hoofdzakelijk vergund?",
    "Welke informatieverplichting heeft de notaris bij verkoop?",
    "Wat is een as-builtattest?",
    "Kan een herstelvordering verjaren?",
    "Wat houdt een minnelijke schikking in bij bouwovertredingen?",
]

app = Flask(__name__)

# De MCP-kant: /mcp, langs de SSO maar achter een eigen Bearer-token.
from boek_mcp import mcp as _mcp_blueprint      # noqa: E402
app.register_blueprint(_mcp_blueprint)


def rapport() -> dict:
    if RAPPORT_PAD.exists():
        return json.loads(RAPPORT_PAD.read_text(encoding="utf-8"))
    return {}


def versies() -> dict:
    if VERSIES_PAD.exists():
        return json.loads(VERSIES_PAD.read_text(encoding="utf-8"))
    return {}


def bank() -> Kennisbank:
    if not KB_PAD.exists():
        abort(503)
    return Kennisbank(KB_PAD)


@app.route("/")
def index():
    kb = bank()
    info = kb.info()
    vraag = (request.args.get("v") or "").strip()
    # Een vraag zonder één enkel woord ("???!!") levert via de vectorkant
    # willekeurige treffers op, en dat oogt als onzin. Dan liever eerlijk
    # zeggen dat er niets te zoeken valt.
    zoekbaar = bool(re.search(r"\w", vraag, re.UNICODE))
    if vraag and zoekbaar and not _model_klaar.is_set():
        kb.sluit()
        return render_template("opwarmen.html", vraag=vraag), 200
    treffers = kb.zoek(vraag, k=8) if (vraag and zoekbaar) else []
    kb.sluit()
    return render_template("index.html", info=info, rapport=rapport(),
                           vraag=vraag if zoekbaar else "",
                           treffers=treffers,
                           voorbeelden=VOORBEELDVRAGEN)


@app.route("/proces")
def proces():
    kb = bank()
    info = kb.info()
    kb.sluit()
    return render_template("proces.html", info=info, rapport=rapport(),
                           versies=versies())


@app.route("/fragment/<int:fid>")
def fragment(fid):
    kb = bank()
    f = kb.fragment(fid)
    kb.sluit()
    if not f:
        abort(404)
    return render_template("fragment.html", f=f, info=None)


@app.route("/gezond")
def gezond():
    return {"ok": KB_PAD.exists()}, (200 if KB_PAD.exists() else 503)


@app.errorhandler(404)
def niet_gevonden(_):
    return render_template("fout.html", code=404,
                           uitleg="Deze pagina of dit fragment bestaat niet."), 404


@app.errorhandler(500)
def kapot(_):
    return render_template("fout.html", code=500,
                           uitleg="Er ging iets mis aan onze kant. "
                                  "Probeer het opnieuw."), 500


@app.errorhandler(503)
def niet_beschikbaar(_):
    return render_template("fout.html", code=503,
                           uitleg="De kennisbank is even niet beschikbaar."), 503


# Opwarmen gebeurt op de achtergrond, en dat is een les uit de praktijk. De
# eerste opzet warmde bij het importeren op, VOOR gunicorn ging luisteren; bij
# een herstart (de kernel doodde de worker toen de VM vol zat) gaf nginx dus
# veertien seconden lang 502 op elke pagina. Nu bindt de poort meteen: alle
# pagina's werken direct, en alleen wie in die eerste seconden zoekt krijgt een
# nette wachtpagina die zichzelf ververst.
_model_klaar = threading.Event()


def _warm_op() -> None:
    try:
        from kennisbank import vectoren
        vectoren.embed_een("opwarmen")
        if KB_PAD.exists():
            b = Kennisbank(KB_PAD)
            b.zoek("opwarmen", k=1)     # laadt ook de zoekmatrix in het geheugen
            b.sluit()
        print("model en zoekmatrix opgewarmd", flush=True)
    except Exception as e:                                     # noqa: BLE001
        print(f"opwarmen mislukt (niet fataal): {e}", flush=True)
    finally:
        # Ook bij een fout vrijgeven: dan laadt het model alsnog bij de eerste
        # echte vraag, in plaats van dat elke zoeker eeuwig blijft wachten.
        _model_klaar.set()


threading.Thread(target=_warm_op, daemon=True).start()


@app.template_filter("procent")
def procent(x):
    try:
        return f"{float(x) * 100:.0f}%"
    except (TypeError, ValueError):
        return "-"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "3025")))

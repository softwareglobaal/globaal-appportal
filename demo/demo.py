"""Publieke demo: laad een document, doorzoek het meteen.

Draait op elevaitnv.com/demo. De bezoeker levert een PDF met tekstlaag aan en
krijgt binnen seconden de gevonden hoofdstukindeling plus een zoekbalk die
antwoorden met bladzijde teruggeeft.

Wat hier anders is dan in de betaalde app:

  geen account     de demo vraagt niets, dus er valt ook niets te lekken
  geen OCR         een gescand document wordt netjes geweigerd; uitlezen kost
                   geld en dat doen we niet gratis voor onbekenden. Die
                   weigering is meteen het gesprek waard: daar zit de klant
  alles tijdelijk  bestand en kennisbank verdwijnen na een uur, automatisch
  grenzen zichtbaar zie grenzen.py; ze staan ook op het scherm, met erbij dat
                   ze in de betaalde versie niet gelden
"""
from __future__ import annotations

import os
import shutil
import threading
import time
import uuid
from pathlib import Path

from flask import (Flask, abort, redirect, render_template, request, url_for)

import grenzen
from kennisbank import knippen, pdfbron, structuur as S, vectoren
from kennisbank.opslag import Kennisbank

WERKMAP = Path("/tmp/demo-kennisbank")
WERKMAP.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = grenzen.MAX_BYTES + (1 << 20)


class OnderVoorvoegsel:
    """Laat de app onder /demo leven zonder dat de routes dat hoeven te weten.

    Nginx stuurt het pad ongewijzigd door, dus zonder dit ziet Flask
    "/demo/verwerk" en herkent hij zijn eigen route niet. Met SCRIPT_NAME
    klopt ook url_for(): die zet het voorvoegsel er weer voor, zodat elke link
    en elke formulieractie op de juiste plek uitkomt.
    """

    def __init__(self, wsgi, voorvoegsel: str = ""):
        self.wsgi = wsgi
        self.voorvoegsel = "/" + voorvoegsel.strip("/") if voorvoegsel.strip("/") else ""

    def __call__(self, omgeving, start):
        if self.voorvoegsel:
            pad = omgeving.get("PATH_INFO", "")
            if pad.startswith(self.voorvoegsel):
                omgeving["SCRIPT_NAME"] = self.voorvoegsel
                omgeving["PATH_INFO"] = pad[len(self.voorvoegsel):] or "/"
        return self.wsgi(omgeving, start)


app.wsgi_app = OnderVoorvoegsel(app.wsgi_app,
                                os.environ.get("URL_VOORVOEGSEL", ""))

werkbank = grenzen.Werkbank()
# doc_id -> {"tijd": float, "titel": str, "melding": str, "bladzijden": int,
#            "afgekapt": bool, "trefkans": float, "fragmenten": int, "secties": []}
_kennis: dict[str, dict] = {}
_kennis_slot = threading.Lock()


# ---------------------------------------------------------------- opruimen

def _ruim_op() -> None:
    """Alles ouder dan een uur weg. Dat is de belofte op de pagina."""
    while True:
        try:
            nu = time.time()
            with _kennis_slot:
                oud = [k for k, v in _kennis.items()
                       if nu - v["tijd"] > grenzen.BEWAARTIJD_SECONDEN]
                for k in oud:
                    del _kennis[k]
            for k in oud:
                shutil.rmtree(WERKMAP / k, ignore_errors=True)
            # ook wat de map achterliet zonder registratie (herstart)
            for map_ in WERKMAP.iterdir() if WERKMAP.exists() else []:
                if map_.is_dir() and nu - map_.stat().st_mtime > grenzen.BEWAARTIJD_SECONDEN:
                    shutil.rmtree(map_, ignore_errors=True)
            grenzen.ruim_tellingen_op()
        except Exception as e:                                 # noqa: BLE001
            print(f"opruimen: {e}", flush=True)
        time.sleep(120)


threading.Thread(target=_ruim_op, daemon=True).start()


def _warm_op() -> None:
    try:
        vectoren.embed_een("opwarmen")
        print("embedmodel opgewarmd", flush=True)
    except Exception as e:                                     # noqa: BLE001
        print(f"opwarmen mislukt: {e}", flush=True)


threading.Thread(target=_warm_op, daemon=True).start()


# ---------------------------------------------------------------- schermen

@app.route("/")
def start():
    ruimte = grenzen.controleer_quotum(grenzen.afzender(request))
    return render_template("demo.html", ruimte=ruimte, g=grenzen,
                           vrij=werkbank.vrij(), melding=request.args.get("m", ""))


@app.route("/verwerk", methods=["POST"])
def verwerk():
    ip = grenzen.afzender(request)
    ruimte = grenzen.controleer_quotum(ip)
    if not ruimte.mag:
        return render_template("grens.html", g=grenzen, soort="quotum",
                               ruimte=ruimte), 429

    bestand = request.files.get("bestand")
    if not bestand or not bestand.filename:
        return redirect(url_for("start", m="geen-bestand"))
    if not bestand.filename.lower().endswith(".pdf"):
        return redirect(url_for("start", m="geen-pdf"))

    doc_id = uuid.uuid4().hex[:12]
    map_ = WERKMAP / doc_id
    map_.mkdir(parents=True, exist_ok=True)
    pad = map_ / "bron.pdf"
    bestand.save(pad)

    if pad.stat().st_size > grenzen.MAX_BYTES:
        shutil.rmtree(map_, ignore_errors=True)
        return render_template("grens.html", g=grenzen, soort="omvang",
                               mb=round(pad.stat().st_size / 1024 / 1024, 1)), 413

    verkenning = pdfbron.verken(pad)
    if verkenning.fout or verkenning.bladzijden == 0:
        shutil.rmtree(map_, ignore_errors=True)
        return render_template("grens.html", g=grenzen, soort="onleesbaar",
                               fout=verkenning.fout), 400
    if not verkenning.heeft_tekstlaag:
        kosten = round(verkenning.bladzijden * 0.05, 2)
        shutil.rmtree(map_, ignore_errors=True)
        return render_template("grens.html", g=grenzen, soort="scan",
                               bladzijden=verkenning.bladzijden,
                               kosten=kosten), 400

    try:
        with werkbank:
            uitkomst = _bouw(doc_id, map_, pad, verkenning)
    except grenzen.Bezet:
        shutil.rmtree(map_, ignore_errors=True)
        return render_template("grens.html", g=grenzen, soort="druk"), 503
    except Exception as e:                                     # noqa: BLE001
        shutil.rmtree(map_, ignore_errors=True)
        print(f"verwerken mislukt: {type(e).__name__}: {e}", flush=True)
        return render_template("grens.html", g=grenzen, soort="mislukt"), 500

    grenzen.boek_verbruik(ip)
    with _kennis_slot:
        _kennis[doc_id] = uitkomst
    return redirect(url_for("resultaat", doc_id=doc_id))


def _bouw(doc_id: str, map_: Path, pad: Path, verkenning) -> dict:
    """De hele keten, ingekort tot wat een demo nodig heeft."""
    bladen = pdfbron.laad(pad)
    afgekapt = len(bladen) > grenzen.MAX_BLADZIJDEN
    if afgekapt:
        # Vriendelijk falen: liever de eerste veertig bladzijden tonen dan het
        # document weigeren. De bezoeker ziet dan nog steeds hoe het werkt.
        bladen = bladen[:grenzen.MAX_BLADZIJDEN]

    st = S.analyseer(bladen)
    gedrukt = {}
    if st.ijking.verschuiving is not None:
        gedrukt = {b.fysiek: b.fysiek - st.ijking.verschuiving
                   for b in bladen if b.fysiek > st.ijking.voorwerk_tot}
    fragmenten = knippen.knip(bladen, st.secties,
                              overslaan=set(st.inhoudsopgave_paginas),
                              gedrukt_van=gedrukt)
    if not fragmenten:
        raise ValueError("geen fragmenten")
    dek = knippen.dekking(bladen, fragmenten,
                          overslaan=set(st.inhoudsopgave_paginas))
    vecs = vectoren.embed([f.met_context for f in fragmenten])

    bank = Kennisbank(map_ / "kennisbank.db")
    bank.leg_vast(doc_id=doc_id, titel=pad.name, bestandsnaam="bron.pdf",
                  bladzijden=len(bladen), aangemaakt="", trefkans=st.trefkans,
                  verschuiving=st.ijking.verschuiving, dekking=dek["aandeel"],
                  meta={}, verwerking=1, strategie="bladzijde-blokken")
    bank.schrijf_secties(st.secties)
    bank.schrijf_fragmenten(fragmenten, vecs)
    bank.sluit()

    return {
        "tijd": time.time(),
        "titel": Path(request.files["bestand"].filename).stem[:80],
        "bladzijden": len(bladen),
        "oorspronkelijk": verkenning.bladzijden,
        "afgekapt": afgekapt,
        "trefkans": st.trefkans,
        "fragmenten": len(fragmenten),
        "dekking": dek["aandeel"],
        "secties": [{"titel": s.titel, "van": gedrukt.get(s.van, s.van),
                     "niveau": s.niveau} for s in st.secties[:14]],
        "verschuiving": st.ijking.verschuiving,
    }


def _open(doc_id: str) -> tuple[dict, Kennisbank]:
    with _kennis_slot:
        meta = _kennis.get(doc_id)
    pad = WERKMAP / doc_id / "kennisbank.db"
    if not meta or not pad.exists():
        abort(410)
    return meta, Kennisbank(pad)


@app.route("/d/<doc_id>")
def resultaat(doc_id):
    meta, bank = _open(doc_id)
    vraag = (request.args.get("v") or "").strip()
    treffers = bank.zoek(vraag, k=6) if vraag else []
    bank.sluit()
    ruimte = grenzen.controleer_quotum(grenzen.afzender(request))
    rest = int(grenzen.BEWAARTIJD_SECONDEN - (time.time() - meta["tijd"])) // 60
    return render_template("resultaat.html", meta=meta, vraag=vraag,
                           treffers=treffers, doc_id=doc_id, g=grenzen,
                           ruimte=ruimte, minuten_over=max(0, rest))


@app.route("/gezond")
def gezond():
    return {"ok": True, "in_behandeling": not werkbank.vrij()}


@app.errorhandler(410)
def verlopen(_):
    return render_template("grens.html", g=grenzen, soort="verlopen"), 410


@app.errorhandler(413)
def te_groot(_):
    return render_template("grens.html", g=grenzen, soort="omvang", mb=None), 413


@app.errorhandler(404)
def weg(_):
    return redirect(url_for("start"))


@app.template_filter("procent")
def procent(x):
    try:
        return f"{float(x) * 100:.0f}%"
    except (TypeError, ValueError):
        return "-"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3030)

"""FelixArchief en Percelenpas Antwerpen als eigen pagina (Shaniel, 13-10-2026).

Shelton (groep felix) vraagt hier zelf zoektochten aan, zonder goedkeuring van Mehdi, en ziet de resultaten.
Opslaan in de projectmap gebeurt alleen als iemand op de knop klikt.

Bereikbaar op felix.<domein> (eigen tegel en eigen forward-auth, groepen admin, manager en felix) en op
mijnagents.<domein>/felix voor beheer. Op felix.<domein> bestaat alleen deze pagina: de rest van Mehdi's bord
(mail, agenda, signalen) is daar onbereikbaar, ook met een rechtstreekse link.

Een bestand, een schrijver (de container draait als root, de runner als ubuntu):
  aanvragen.jsonl  deze pagina, alleen toevoegen: {"soort": "zoek"|"opslaan", ...}
  stand.json       felix_wacht.py (de runner), de stand per zoektocht
  log.jsonl        felix_wacht.py, het logboek van aanvragen, resultaten en opslagen
"""
import json
import os
import re
import secrets
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import abort, redirect, render_template, request, send_file, url_for

DATA = os.environ.get("FELIX_DATA", "/data/felix")
AANVRAGEN = os.path.join(DATA, "aanvragen.jsonl")
STAND = os.path.join(DATA, "stand.json")
LOGBOEK = os.path.join(DATA, "log.jsonl")
ZOEKTOCHTEN = os.path.join(DATA, "zoektochten")
GROEPEN = {"admin", "manager", "felix"}
PROJECT_RE = re.compile(r"^\d{3,6}$")
MAX_ADRES = 200
STATUS_LABEL = {"wacht": "wacht", "bezig": "bezig", "klaar": "klaar", "fout": "fout"}


def _lees_jsonl(pad, laatste=None):
    uit = []
    try:
        with open(pad, encoding="utf-8") as f:
            for regel in f:
                try:
                    x = json.loads(regel)
                except ValueError:
                    continue
                if isinstance(x, dict):
                    uit.append(x)
    except OSError:
        pass
    return uit[-laatste:] if laatste else uit


def _stand():
    try:
        with open(STAND, encoding="utf-8") as f:
            s = json.load(f)
    except (OSError, ValueError):
        s = {}
    s.setdefault("zoek", {})
    s.setdefault("opslaan", {})
    return s


def _voeg_toe(regel):
    os.makedirs(DATA, exist_ok=True)
    with open(AANVRAGEN, "a", encoding="utf-8") as f:
        f.write(json.dumps(regel, ensure_ascii=False) + "\n")


def zoektochten():
    """Alle zoekaanvragen, nieuwste eerst, met hun stand (wacht als de runner ze nog niet nam)."""
    stand = _stand()
    alle = _lees_jsonl(AANVRAGEN)
    opslaan_wacht = {a.get("zoek_id") for a in alle if a.get("soort") == "opslaan" and a.get("id") not in stand["opslaan"]}
    uit = []
    for a in alle:
        if a.get("soort") != "zoek":
            continue
        s = stand["zoek"].get(a["id"], {})
        uit.append({"id": a["id"], "project": a.get("project", ""), "adres": a.get("adres", ""), "door": a.get("door", ""),
                    "ts": a.get("ts", ""), "status": s.get("status", "wacht"), "besluit": s.get("besluit", ""),
                    "fout": s.get("fout", ""), "klaar": s.get("klaar", ""), "map": s.get("map", ""),
                    "dossiers": s.get("dossiers"), "vergunningen": s.get("vergunningen"),
                    "opgeslagen": s.get("opgeslagen"), "opslaan_fout": s.get("opslaan_fout", ""),
                    "opslaan_wacht": a["id"] in opslaan_wacht})
    return list(reversed(uit))


def _map_van(z):
    """Het absolute pad van een afgewerkte zoektocht, of None. Nooit buiten ZOEKTOCHTEN."""
    if not z or not z.get("map"):
        return None
    pad = os.path.realpath(os.path.join(ZOEKTOCHTEN, z["map"]))
    basis = os.path.realpath(ZOEKTOCHTEN)
    return pad if pad.startswith(basis + os.sep) and os.path.isdir(pad) else None


def _bestanden(pad):
    uit = []
    for wortel, mappen, namen in os.walk(pad):
        mappen[:] = sorted(m for m in mappen if m != "_gegevens")
        for n in sorted(namen):
            vol = os.path.join(wortel, n)
            uit.append({"rel": os.path.relpath(vol, pad).replace(os.sep, "/"), "bytes": os.path.getsize(vol)})
    return uit


def registreer(app, gebruiker, groepen, md, nu):
    def mag():
        return bool(groepen() & GROEPEN)

    def eis():
        if not mag():
            abort(403)

    def zelfde_herkomst():
        # Een formulier van een andere site mag hier niets klaarzetten.
        herkomst = request.headers.get("Origin") or ""
        if herkomst and herkomst.split("://", 1)[-1] != request.host:
            abort(403)

    @app.before_request
    def alleen_felix_op_eigen_domein():
        """Op felix.<domein> bestaat alleen deze pagina; de rest van het bord niet, ook niet via een link."""
        if not request.host.split(":")[0].startswith("felix."):
            return None
        if request.path == "/":
            return redirect("/felix")
        if request.path == "/felix" or request.path.startswith("/felix/"):
            return None
        abort(404)

    @app.route("/felix")
    def felix_pagina():
        eis()
        lijst = zoektochten()
        return render_template("felix.html", zoektochten=lijst, gebruiker=gebruiker(),
                               logboek=list(reversed(_lees_jsonl(LOGBOEK, laatste=60))),
                               bericht=request.args.get("bericht", ""))

    @app.route("/felix/zoek", methods=["POST"])
    def felix_zoek():
        eis()
        zelfde_herkomst()
        project = (request.form.get("project") or "").strip()
        adres = re.sub(r"\s+", " ", (request.form.get("adres") or "")).strip()
        if not adres or len(adres) > MAX_ADRES:
            return redirect(url_for("felix_pagina", bericht="Vul een adres in (straat, huisnummer, postcode en gemeente)."))
        if project and not PROJECT_RE.match(project):
            return redirect(url_for("felix_pagina", bericht="Het projectnummer bestaat alleen uit cijfers, bv. 3810."))
        # dubbel klikken: dezelfde aanvraag die nog wacht, niet nog eens
        for z in zoektochten():
            if z["status"] in ("wacht", "bezig") and z["adres"].lower() == adres.lower() and z["project"] == project:
                return redirect(url_for("felix_pagina", bericht="Deze zoektocht staat al in de wachtrij."))
        _voeg_toe({"id": secrets.token_hex(4), "soort": "zoek", "project": project, "adres": adres,
                   "door": gebruiker(), "ts": nu()})
        return redirect(url_for("felix_pagina", bericht="Aangevraagd. De agent begint binnen 5 minuten; een zoektocht duurt een paar minuten."))

    def _zoek_of_404(zid):
        z = next((x for x in zoektochten() if x["id"] == zid), None)
        if not z:
            abort(404)
        return z

    @app.route("/felix/<zid>")
    def felix_zoektocht(zid):
        eis()
        z = _zoek_of_404(zid)
        pad = _map_van(z)
        controle = ""
        if pad and os.path.exists(os.path.join(pad, "Controle.md")):
            controle = md(open(os.path.join(pad, "Controle.md"), encoding="utf-8").read())
        logboek = [x for x in _lees_jsonl(LOGBOEK) if x.get("id") == zid or x.get("zoek_id") == zid]
        bestanden = _bestanden(pad) if pad else []
        beelden = [b for b in bestanden if b["rel"].lower().endswith((".png", ".jpg", ".jpeg"))]
        return render_template("felix_zoektocht.html", z=z, controle=controle, bestanden=bestanden, beelden=beelden,
                               logboek=logboek, gebruiker=gebruiker())

    @app.route("/felix/<zid>/bestand/<path:rel>")
    def felix_bestand(zid, rel):
        eis()
        pad = _map_van(_zoek_of_404(zid))
        if not pad:
            abort(404)
        vol = os.path.realpath(os.path.join(pad, rel))
        if not vol.startswith(pad + os.sep) or not os.path.isfile(vol) or "/_gegevens/" in vol.replace(os.sep, "/"):
            abort(404)
        return send_file(vol, as_attachment=request.args.get("download") == "1", download_name=os.path.basename(vol))

    @app.route("/felix/<zid>/opslaan", methods=["POST"])
    def felix_opslaan(zid):
        """Alleen op een klik: de runner zet de zoektocht in de projectmap (nieuwe map, nooit overschrijven)."""
        eis()
        zelfde_herkomst()
        z = _zoek_of_404(zid)
        if z["status"] != "klaar":
            return redirect(url_for("felix_zoektocht", zid=zid))
        if not z["project"]:
            return redirect(url_for("felix_pagina", bericht="Zonder projectnummer weet de agent niet in welke projectmap het moet."))
        if z["opgeslagen"] or z["opslaan_wacht"]:
            return redirect(url_for("felix_zoektocht", zid=zid))
        _voeg_toe({"id": secrets.token_hex(4), "soort": "opslaan", "zoek_id": zid, "door": gebruiker(), "ts": nu()})
        return redirect(url_for("felix_zoektocht", zid=zid))

    @app.template_filter("felix_tijd")
    def felix_tijd(ts):
        try:
            t = datetime.fromisoformat(ts)
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            return t.astimezone(ZoneInfo("Europe/Brussels")).strftime("%d-%m %H:%M")
        except (TypeError, ValueError):
            return ts or ""

    @app.template_filter("felix_grootte")
    def felix_grootte(n):
        n = n or 0
        return f"{n / 1_048_576:.1f} MB" if n >= 1_048_576 else f"{max(1, round(n / 1024))} kB"

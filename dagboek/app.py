"""Dagboek (dagboek.globaal.be): wat Mehdi elke dag deed, in een oogopslag.

Mehdi, 30-10-2026: "ik wil een overzichtelijk dashboard, dat ik zie en begrijp wat ik elke dag gedaan heb, alleen voor
de Dagbundelaar, mijn bron van waarheid". Deze app leest daarom alleen de dagbestanden die De Dagbundelaar elke nacht
schrijft (mijnagents-data/dagboek/<jaar>/<dag>.md en .json, dezelfde bestanden als in Dropbox "Data uit Mehdi/Dagboek").
Ze rekent niets opnieuw uit, schrijft niets en heeft geen eigen opslag. Toegang: Authentik (forward-auth) en hier nog
eens de groep uit DAGBOEK_GROUPS.
"""
import json
import os
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Flask, abort, render_template, request

app = Flask(__name__)
MAP = os.environ.get("DAGBOEK_MAP", "/dagboek")
GROEPEN = {g.strip() for g in os.environ.get("DAGBOEK_GROUPS", "dagboek").split(",") if g.strip()}
BRUSSEL = ZoneInfo("Europe/Brussels")
DAGEN = 14
WEEKDAG = ("ma", "di", "wo", "do", "vr", "za", "zo")
MAAND = ("jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec")
# De uitkomst per afspraak, zoals De Dagbundelaar ze vastlegt (dagvaststelling.bewijs), in gewone woorden.
UITKOMST = {"bevestigd": ("doorgegaan", "groen"), "aanwijzing": ("waarschijnlijk", "oranje"),
            "geen spoor": ("geen spoor", "rood")}
UITKOMST_RE = re.compile(r": (bevestigd|aanwijzing|geen spoor)(?: \((.*)\))?(?:\. Ging dit door\?)?$")


def mag():
    groepen = {g.strip() for g in re.split(r"[|,]", request.headers.get("X-authentik-groups", "")) if g.strip()}
    return bool(groepen & GROEPEN)


def dagnaam(d, kort=False):
    return f"{WEEKDAG[d.weekday()]} {d.day} {MAAND[d.month - 1]}" + ("" if kort else f" {d.year}")


def lees(dag, ext):
    try:
        with open(os.path.join(MAP, dag[:4], f"{dag}.{ext}"), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def secties(tekst):
    """De dagtekst in zijn blokken: {'Gepland': [regels], 'Niet gepland': [...], 'Communicatie': [...], ...}."""
    uit, kop = {}, None
    for regel in (tekst or "").splitlines():
        if regel.startswith("## "):
            kop = regel[3:].split(" (", 1)[0].strip()
            uit[kop] = []
        elif kop and regel.strip():
            uit[kop].append(regel.rstrip())
    return uit


def titel_kort(t):
    """'!! Mehdi: [HA] 9003 ...' leest als '[HA] 9003 ...': de agendaconventie zonder de herhaling van Mehdi."""
    return re.sub(r"^(?:[!?]{2}\s*)?Mehdi:\s*", "", t.strip())


def gepland(regels):
    uit = []
    for r in regels:
        r = r[2:] if r.startswith("- ") else r
        m = UITKOMST_RE.search(r)
        if not m:
            uit.append({"tijd": "", "titel": r, "label": "", "kleur": "grijs", "grond": ""})
            continue
        kop = r[:m.start()]
        tijd, _, titel = kop.partition(" ")
        label, kleur = UITKOMST[m.group(1)]
        uit.append({"tijd": tijd, "titel": "privé" if titel == "(privé)" else titel_kort(titel), "label": label,
                    "kleur": kleur, "grond": m.group(2) or ""})
    return uit


def niet_gepland(regels):
    uit = []
    for r in regels:
        r = r[2:] if r.startswith("- ") else r.strip()
        m = re.match(r"(\d\d:\d\d) ([^,]+), (\d+) min, (.+)$", r)
        if m:
            uit.append({"tijd": m.group(1), "wat": m.group(4), "kanaal": m.group(2), "min": int(m.group(3))})
            continue
        m = re.match(r"(\d\d:\d\d) tot (\d\d:\d\d) \((\d+) min\) (.+)$", r)
        if m:
            uit.append({"tijd": m.group(1), "wat": m.group(4), "kanaal": "bezoek", "min": int(m.group(3))})
            continue
        uit.append({"tijd": "", "wat": r, "kanaal": "", "min": None})
    return sorted(uit, key=lambda x: x["tijd"] or "99")


def getal(x):
    return x if isinstance(x, int) and not isinstance(x, bool) else None


def tegels(t):
    """De cijfers van de dag uit de telling (.json). None is onbekend en wordt een vraagteken, nooit een nul."""
    a = t.get("afspraken") if isinstance(t.get("afspraken"), dict) else None
    g = t.get("gesprekken") if isinstance(t.get("gesprekken"), dict) else {}
    ng = t.get("niet_gepland") if isinstance(t.get("niet_gepland"), dict) else {}
    wa = t.get("whatsapp") if isinstance(t.get("whatsapp"), dict) else {}
    tel = t.get("telefoon") if isinstance(t.get("telefoon"), dict) else {}
    mail = t.get("mail") if isinstance(t.get("mail"), dict) else None

    def kanaal(k, groot, klein):
        stand = str(k.get("stand") or "niet aangesloten")
        if stand == "niet aangesloten":
            return {"groot": "-", "klein": "niet aangesloten", "uit": True}
        return {"groot": groot, "klein": klein + ("" if stand == "aangesloten" else f" ({stand})"), "uit": False}

    def min_tekst(m):
        m = getal(m)
        if m is None:
            return "?"
        return f"{m // 60}u{m % 60:02d}" if m >= 60 else f"{m} min"

    return [
        {"naam": "Afspraken", "groot": "?" if a is None else getal(a.get("totaal")),
         "klein": "agenda niet gelezen" if a is None else
         f"{(getal(a.get('bevestigd')) or 0)} doorgegaan, {(getal(a.get('aanwijzing')) or 0)} waarschijnlijk, "
         f"{(getal(a.get('geen spoor')) or 0)} geen spoor",
         "stippen": None if a is None else [("groen", getal(a.get("bevestigd")) or 0), ("oranje", getal(a.get("aanwijzing")) or 0),
                                             ("rood", getal(a.get("geen spoor")) or 0), ("grijs", getal(a.get("privé")) or 0)]},
        {"naam": "Gesprekken", "groot": "?" if getal(g.get("aantal")) is None else g["aantal"],
         "klein": f"{min_tekst(g.get('minuten'))} in Zoom, Fathom, Plaud"},
        {"naam": "Niet gepland", "groot": "?" if getal(ng.get("gesprekken")) is None else ng["gesprekken"],
         "klein": f"gesprekken, {'?' if getal(ng.get('bezoeken')) is None else ng['bezoeken']} bezoek(en)"},
        {"naam": "Mail", **({"groot": "?", "klein": "niet gelezen"} if mail is None else
                            {"groot": "?" if getal(mail.get("verzonden")) is None else mail["verzonden"],
                             "klein": f"verzonden, {'?' if getal(mail.get('binnen')) is None else mail['binnen']} binnen"
                                      + (" (onvolledig)" if mail.get("onvolledig") else "")})},
        {"naam": "WhatsApp", **kanaal(wa, "?" if getal(wa.get("berichten")) is None else wa["berichten"],
                                      f"berichten, {getal(wa.get('oproepen')) or 0} oproepen")},
        {"naam": "Telefoon", **kanaal(tel, "?" if getal(tel.get("oproepen")) is None else tel["oproepen"],
                                      f"oproepen, {min_tekst(tel.get('minuten'))}")},
    ]


def dag_gegevens(dag):
    d = date.fromisoformat(dag)
    tekst, rauw = lees(dag, "md"), lees(dag, "json")
    try:
        telling = json.loads(rauw) if rauw else {}
    except ValueError:
        telling = {}
    if not isinstance(telling, dict):
        telling = {}
    s = secties(tekst)
    over = [r[2:] for r in s.get("Over deze vaststelling", []) if r.startswith("- ")]
    return {"dag": dag, "naam": dagnaam(d), "kort": dagnaam(d, True), "er": tekst is not None,
            "tegels": tegels(telling) if telling.get("vastgesteld") else None,
            "gepland": gepland(s.get("Gepland", [])), "niet_gepland": niet_gepland(s.get("Niet gepland", [])),
            "communicatie": [r[2:] if r.startswith("- ") else r.strip() for r in s.get("Communicatie", [])],
            "versie": over[0] if over else ""}


def vandaag():
    return datetime.now(BRUSSEL).date()


@app.route("/healthz")
def healthz():
    return {"ok": True, "map": os.path.isdir(MAP)}


@app.route("/")
def overzicht():
    if not mag():
        abort(403)
    gisteren = vandaag() - timedelta(days=1)
    dagen = [dag_gegevens((gisteren - timedelta(days=i)).isoformat()) for i in range(DAGEN)]
    return render_template("overzicht.html", dagen=dagen, aantal=DAGEN)


@app.route("/dag/<dag>")
def dag_pagina(dag):
    if not mag():
        abort(403)
    try:
        d = date.fromisoformat(dag)
    except ValueError:
        abort(404)
    vorige, volgende = d - timedelta(days=1), d + timedelta(days=1)
    return render_template("dag.html", d=dag_gegevens(dag), vorige=vorige.isoformat(),
                           volgende=volgende.isoformat() if volgende < vandaag() else None)

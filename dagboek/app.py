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
import time
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Flask, abort, render_template, request, url_for

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
# Waar Mehdi was en hoe hij zich verplaatste komt uit het Locatie-dashboard (dezelfde dagindeling die De Dagbundelaar
# gebruikt om afspraken te toetsen), over het interne netwerk en alleen lezend. Mehdi, 31-10-2026: "ik zie in de
# dagboek niks van mijn verplaatsingen en waar ik naar toe geweest ben".
LOCATIE = os.environ.get("LOCATIE_URL", "http://app-locatie:3031").rstrip("/")
LOCATIE_CACHE = 300
_cache = {}
WIJZE = {"automotive": "auto", "cycling": "fiets", "walking": "te voet", "running": "lopend"}
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


def haal_locatie(pad):
    """JSON van het Locatie-dashboard, of None als het niet bereikbaar is. Vijf minuten bewaard."""
    bewaard = _cache.get(pad)
    if bewaard and time.monotonic() - bewaard[0] < LOCATIE_CACHE:
        return bewaard[1]
    try:
        with urllib.request.urlopen(LOCATIE + pad, timeout=8) as r:
            d = json.load(r)
    except Exception:  # noqa: BLE001  onbereikbaar of kapot: het dagboek toont dan een vraagteken
        return None
    _cache[pad] = (time.monotonic(), d)
    return d


def uur(epoch):
    return datetime.fromtimestamp(epoch, BRUSSEL).strftime("%H:%M")


def duur(m):
    m = getal(m)
    if m is None:
        return "?"
    return f"{m // 60}u{m % 60:02d}" if m >= 60 else f"{m} min"


def km(meter):
    return f"{(meter or 0) / 1000:.1f}".replace(".", ",")


def onderweg_tegel(cijfers):
    """De tegel Onderweg: km en plekken van de dag uit /api/dagcijfers. None: dashboard onbereikbaar."""
    if cijfers is None:
        return {"naam": "Onderweg", "groot": "?", "klein": "locatie niet bereikbaar"}
    if not cijfers or not cijfers.get("punten"):
        return {"naam": "Onderweg", "groot": "-", "klein": "geen meting", "uit": True}
    return {"naam": "Onderweg", "groot": f"{km((cijfers.get('km') or 0) * 1000)} km",
            "klein": f"{getal(cijfers.get('verblijven')) or 0} plekken, {duur(cijfers.get('onderweg_min'))} rijden"}


def waar(s):
    h = s.get("herkenning") or {}
    p = h.get("project")
    if h.get("zekerheid") == "onzeker" and h.get("kandidaten"):
        return "een van: " + ", ".join(f"{k.get('firma') or ''} {k.get('nummer')}".strip() for k in h["kandidaten"])
    if p:
        return f"project {p.get('firma') or ''} {p.get('nummer')}".replace("  ", " ") + (
            f", {p['adres']}" if p.get("adres") else "")
    if h.get("plek") or s.get("plek"):
        return h.get("plek") or s.get("plek")
    if s.get("adres"):
        return s["adres"]
    if s.get("lat") is not None:
        return f"{s['lat']:.4f}, {s['lon']:.4f}"
    return "onbekende plek"


def verplaatsingen(dagboek):
    """De dag van het Locatie-dashboard als lijst: verblijven, ritten en stukken zonder meting, in volgorde.
    None: niet bereikbaar. Leeg: geen meting op die dag."""
    if dagboek is None:
        return None
    uit = []
    for s in dagboek.get("indeling") or []:
        if not isinstance(s, dict) or not isinstance(s.get("van"), (int, float)):
            continue
        regel = {"van": uur(s["van"]), "tot": uur(s.get("tot") or s["van"]), "duur": duur(s.get("minuten"))}
        if s.get("soort") == "bezoek":
            h = s.get("herkenning") or {}
            regel.update(soort="plek", wat=waar(s), project=bool(h.get("project")),
                         extra="kort gestopt" if h.get("aard") == "kort_stoppen" or s.get("stop") else "")
        elif s.get("soort") == "verplaatsing":
            regel.update(soort="rit", wat=f"rit {WIJZE.get(s.get('wijze'), '')}".strip() + f", {km(s.get('meter'))} km",
                         project=False, extra="")
        else:
            regel.update(soort="gat", wat="geen meting", project=False, extra="")
        uit.append(regel)
    return uit


def auto_spoor(dagboek):
    """Volgt het dagboek de tracker in de auto (en niet Mehdi zelf)? Dan zegt het waar de auto stond."""
    sporen = (dagboek or {}).get("sporen") or {}
    rollen = [sp.get("rol") for sp in sporen.values() if isinstance(sp, dict)]
    return bool(rollen) and "persoon" not in rollen


GESPREK_RE = re.compile(r"(\d\d:\d\d) (Zoom|Fathom|Plaud), (\d+) min, ((?:[^;()\n]|\([^()\n]*\))*)")


def gesprekken(tekst):
    """Elk gesprek in Zoom, Fathom en Plaud dat het dagbestand noemt (bij een afspraak of niet gepland), een keer,
    op tijd. Mehdi, 31-10-2026: "ik zie mijn zoom berichten niet, mijn fathom en mijn plaud ook niet"."""
    gezien = {}
    for m in GESPREK_RE.finditer(tekst or ""):
        wie = re.sub(r"\s+en \d+ meer$", "", m.group(4).strip().rstrip("."))
        gezien.setdefault((m.group(1), m.group(2)), {"tijd": m.group(1), "bron": m.group(2), "min": int(m.group(3)),
                                                      "wie": wie})
    return sorted(gezien.values(), key=lambda g: g["tijd"])


def per_bron(lijst):
    tel = {}
    for g in lijst:
        tel[g["bron"]] = tel.get(g["bron"], 0) + 1
    return ", ".join(f"{n} {b}" for b, n in sorted(tel.items(), key=lambda x: -x[1]))


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
                                      f"berichten, {'?' if getal(wa.get('oproepen')) is None else wa['oproepen']} "
                                      "oproepen")},
        {"naam": "Telefoon", **kanaal(tel, "?" if getal(tel.get("oproepen")) is None else tel["oproepen"],
                                      f"oproepen, {min_tekst(tel.get('minuten'))}")},
    ]


def dag_gegevens(dag, cijfers=None):
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
    praat = gesprekken(tekst)
    tg = (tegels(telling) + [onderweg_tegel(cijfers)]) if telling.get("vastgesteld") else None
    if tg and praat:
        tg[1]["klein"] = f"{per_bron(praat)}; {tg[1]['klein'].split(' in ')[0]}"
    return {"dag": dag, "naam": dagnaam(d), "kort": dagnaam(d, True), "er": tekst is not None,
            "tegels": tg, "gesprekken": praat,
            "gepland": gepland(s.get("Gepland", [])), "niet_gepland": niet_gepland(s.get("Niet gepland", [])),
            "communicatie": [r[2:] if r.startswith("- ") else r.strip() for r in s.get("Communicatie", [])],
            "eigen": [r[2:] if r.startswith("- ") else r.strip() for r in s.get("Eigen werk en gezondheid", [])],
            "versie": over[0] if over else ""}


def vandaag():
    return datetime.now(BRUSSEL).date()


# Alle bronnen van De Dagbundelaar (Mehdi, 31-10-2026: "geef mij een overzicht van wat al je bronnen zijn, zo kan ik
# mee controleren of iets niet klopt"). Vast: waar het vandaan komt en hoe vaak. Per dag: wat het dagbestand zag.
BRONNEN = (
    ("Agenda", "je Google-agenda's (server)", "werkdagen 06:30, daarna elke 2 uur", "afspraken en of ze doorgingen"),
    ("Zoom", "Zoom-account (server)", "2 keer per dag", "gesprekken met wie en hoe lang, aantal chats"),
    ("Fathom", "Fathom-account (server)", "elk uur", "gesprekken met wie en hoe lang"),
    ("Plaud", "Plaud-account (server)", "elk uur", "opnames met wie en hoe lang"),
    ("Mail", "5 postvakken: mch, info H-Architects, H-Invest, Melodie, hotmail (server)", "elk uur 07-21",
     "aantal binnen en verzonden, nooit de tekst"),
    ("WhatsApp", "WhatsApp op je laptop", "elk uur als de laptop wakker is",
     "berichten en oproepen per persoon, nooit de tekst"),
    ("Telefoon", "oproepen van je iPhone, via je laptop", "elk uur als de laptop wakker is", "met wie en hoe lang"),
    ("Telefoon Xelion", "je gsm-lijn in de Xelion-centrale (server)", "elk uur", "met wie en hoe lang, gemiste oproepen"),
    ("Sms en iMessage", "Messages op je laptop", "elk uur als de laptop wakker is",
     "berichten per persoon, sms of iMessage, nooit de tekst"),
    ("Locatie", "GPS-tracker in je auto (server)", "elk uur", "plekken, projecten, ritten en km"),
    ("Foto's", "Photos op je laptop, alleen tijd en plaats", "elke avond 21:15", "aantal foto's en plekken"),
    ("Wispr Flow", "Wispr Flow op je laptop", "elke avond 21:30", "dictaten, woorden en minuten, nooit de tekst"),
    ("Websites", "Chrome, Firefox en Safari op je laptop", "elk uur als de laptop wakker is",
     "bezoeken en de meest bezochte sites, alleen de naam van de site"),
    ("YouTube", "YouTube in de browser op je laptop", "elk uur als de laptop wakker is",
     "video's, minuten en de titels die je het meest bekeek"),
    ("Gezondheid", "Apple Watch, via Health Auto Export op je iPhone", "elke ochtend", "stappen, hartslag, slaap"),
)


def bron_stand(d, tekst, cijfers):
    """Per bron wat het dagbestand van die dag zag: een korte tekst en of het in orde is."""
    t = d.get("telling") or {}
    over = {}
    for r in secties(tekst).get("Over deze vaststelling", []):
        m = re.match(r"- (agenda|Zoom|locatie|mail|WhatsApp|telefoon): (.+)$", r.strip())
        if m:
            over[m.group(1).lower()] = m.group(2)
    tel = {}
    for g in d["gesprekken"]:
        tel[g["bron"]] = tel.get(g["bron"], 0) + 1
    a = t.get("afspraken") if isinstance(t.get("afspraken"), dict) else {}
    mail = t.get("mail") if isinstance(t.get("mail"), dict) else None
    wa = t.get("whatsapp") if isinstance(t.get("whatsapp"), dict) else {}
    tf = t.get("telefoon") if isinstance(t.get("telefoon"), dict) else {}
    sm = t.get("sms") if isinstance(t.get("sms"), dict) else {}
    xe = t.get("xelion") if isinstance(t.get("xelion"), dict) else {}
    fo = t.get("fotos") if isinstance(t.get("fotos"), dict) else None

    def rij(tekst_, stand):
        goed = stand in ("volledig", "aangesloten", "afgesloten", "gelezen", "geteld")
        return {"tekst": tekst_, "stand": stand or "onbekend", "goed": goed}

    def vraag(x):
        return "?" if getal(x) is None else x

    return {
        "Agenda": rij(f"{getal(a.get('totaal')) or 0} afspraken", over.get("agenda")),
        "Zoom": rij(f"{tel.get('Zoom', 0)} gesprekken, {getal(t.get('zoom_chats')) or 0} chats", over.get("zoom")),
        "Fathom": rij(f"{tel.get('Fathom', 0)} gesprekken", "geteld"),
        "Plaud": rij(f"{tel.get('Plaud', 0)} opnames", "geteld"),
        "Mail": rij("niet gelezen" if mail is None else f"{getal(mail.get('binnen')) or 0} binnen, "
                    f"{getal(mail.get('verzonden')) or 0} verzonden",
                    None if mail is None else ("onvolledig" if mail.get("onvolledig") else "volledig")),
        # WA-6 (T-0120): een onbekend aantal van een Mac-kanaal is een vraagteken, nooit 0
        "WhatsApp": rij(f"{vraag(wa.get('berichten'))} berichten, {vraag(wa.get('oproepen'))} oproepen", wa.get("stand")),
        "Telefoon": rij(f"{vraag(tf.get('oproepen'))} oproepen", tf.get("stand")),
        "Telefoon Xelion": rij(f"{vraag(xe.get('oproepen'))} oproepen, {vraag(xe.get('gemist'))} gemist",
                               xe.get("stand") or "niet aangesloten"),
        "Sms en iMessage": rij(f"{vraag(sm.get('berichten'))} berichten in {vraag(sm.get('gesprekken'))} gesprekken",
                               sm.get("stand") or "niet aangesloten"),
        "Locatie": rij("locatie niet bereikbaar" if cijfers is None else
                       f"{km((cijfers.get('km') or 0) * 1000)} km, {getal(cijfers.get('verblijven')) or 0} plekken",
                       None if cijfers is None else ("gelezen" if cijfers.get("punten") else "geen meting")),
        "Foto's": rij("niet gelezen" if fo is None else f"{getal(fo.get('aantal')) or 0} foto's op "
                      f"{getal(fo.get('plekken')) or 0} plekken", "onbekend" if fo is None else "geteld"),
        **eigen_stand(secties(tekst).get("Eigen werk en gezondheid"), rij),
    }


def eigen_stand(regels, rij):
    """Wispr, websites en gezondheid uit het blok 'Eigen werk en gezondheid' van het dagbestand."""
    if regels is None:
        return {k: rij("nog niet in dit dagbestand", "onbekend") for k in ("Wispr Flow", "Websites", "YouTube", "Gezondheid")}
    vind = {k: next((r.strip()[2:].split(": ", 1)[-1] for r in regels if r.strip().startswith("- " + k)), "")
            for k in ("Wispr Flow", "websites", "YouTube", "gezondheid")}
    w, s, g, y = vind["Wispr Flow"], vind["websites"], vind["gezondheid"], vind["YouTube"]
    return {"Wispr Flow": rij(w or "onbekend", "onbekend" if not w or w.startswith("onbekend") else "geteld"),
            "Websites": rij(s.split(";")[0] or "onbekend",
                            "niet aangesloten" if not s or s.startswith("nog niet") else "geteld"),
            "YouTube": rij(y.split(";")[0] or "nog niet aangesloten",
                           "niet aangesloten" if not y else "onbekend" if y.startswith("onbekend") else "geteld"),
            "Gezondheid": rij("geen gegevens" if not g or g.startswith("geen") else "gegevens van de Apple Watch",
                              "geen gegevens" if not g or g.startswith("geen") else "gelezen")}


@app.route("/bronnen")
def bronnen_pagina():
    if not mag():
        abort(403)
    dag = request.args.get("dag") or (vandaag() - timedelta(days=1)).isoformat()
    try:
        date.fromisoformat(dag)
    except ValueError:
        abort(404)
    lc = haal_locatie(f"/api/dagcijfers?van={dag}&tot={dag}")
    lc = lc.get("dagen", {}).get(dag, {}) if isinstance(lc, dict) and isinstance(lc.get("dagen"), dict) else None
    d = dag_gegevens(dag, lc)
    tekst = lees(dag, "md")
    rauw = lees(dag, "json")
    try:
        d["telling"] = json.loads(rauw) if rauw else {}
    except ValueError:
        d["telling"] = {}
    if not isinstance(d["telling"], dict):
        d["telling"] = {}
    stand = bron_stand(d, tekst, lc) if tekst else {}
    rijen = [{"naam": n, "waar": w, "vaak": v, "wat": x, "dag": stand.get(n)} for n, w, v, x in BRONNEN]
    return render_template("bronnen.html", rijen=rijen, d=d)


# Per wacht wat er binnenkwam (Mehdi, 01-11-2026: "ik wil dat ik alle wachten hier zie, zodat ik weet per wacht wat
# binnengekomen is en dat ik het kan controleren"). Het bord (app-mijnagents) heeft de databank; het Dagboek vraagt het
# over het interne netwerk met het token van het bord, alleen lezend. Voorlopig alleen de laatste dagen (WACHT_DAGEN).
BORD = os.environ.get("MIJNAGENTS_URL", "http://app-mijnagents:3022").rstrip("/")
BORD_TOKEN = os.environ.get("AGENTS_TOKEN", "")
# Mehdi, 01-11-2026: alleen de laatste dagen (vandaag en de drie dagen ervoor), niet meer.
WACHT_DAGEN = int(os.environ.get("WACHT_DAGEN", "4"))
KLEUR_UITLEG = {"groen": "kwam binnen", "oranje": "draaide, niets binnen", "rood": "fout", "grijs": "geen ronde"}


def haal_wachten(dag):
    """Per wacht wat er binnenkwam, of None als het bord niet antwoordt. Een minuut bewaard."""
    pad = f"/api/wachten/dag?dag={dag}"
    bewaard = _cache.get(pad)
    if bewaard and time.monotonic() - bewaard[0] < 60:
        return bewaard[1]
    try:
        req = urllib.request.Request(BORD + pad, headers={"X-Agents-Token": BORD_TOKEN})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
    except Exception:  # noqa: BLE001  het bord onbereikbaar: de pagina zegt dat, nooit een lege dag
        return None
    if not isinstance(d, dict) or not isinstance(d.get("vakken"), list):
        return None
    _cache[pad] = (time.monotonic(), d)
    return d


def locatie_items(dag):
    """De Locatiewacht schrijft haar dag in het Locatie-dashboard, niet op het bord: haar plekken en ritten als items."""
    lb = haal_locatie(f"/api/dagboek/{dag}")
    lb = lb if isinstance(lb, dict) and lb.get("datum") == dag else None
    ritten = verplaatsingen(lb)
    if ritten is None:
        return None
    return [{"tijd": r["van"], "wie": r["soort"], "wat": f"{r['wat']} ({r['van']} tot {r['tot']}, {r['duur']})",
             "fout": False} for r in ritten if r["soort"] != "gat"]


def wachten_dag(dag):
    """Alle wachten van één dag uit het bord, met de Locatiewacht uit het Locatie-dashboard erbij, of None."""
    gegevens = haal_wachten(dag)
    if not gegevens:
        return None
    for vak in gegevens["vakken"]:
        for w in vak.get("wachten") or []:
            if w.get("naam") == "locatie-wacht" and not w.get("items"):
                li = locatie_items(dag)
                if li:
                    w.update(items=li, aantal=len(li), oordeel="binnen" if w.get("kleur") != "rood" else w["oordeel"],
                             kleur="groen" if w.get("kleur") != "rood" else "rood")
            w["stand_fout"] = stand_fout(w, dag)
            w["kort"] = wacht_kort(w)
            w["fouten_kort"] = fouten_kort(w.get("fouten") or [])
    alle = [w for v in gegevens["vakken"] for w in v.get("wachten") or []]
    gegevens["telling"] = {k: sum(1 for w in alle if w.get("kleur") == k) for k in KLEUR_UITLEG}
    gegevens["items"] = sum(w.get("aantal") or 0 for w in alle)
    # Eén wacht niet gelezen: dan is het dagtotaal niet volledig (Codex 01-11): "minstens" in plaats van een vol getal.
    gegevens["onvolledig"] = any(w.get("leesfout") for w in alle)
    return gegevens


def fouten_kort(fouten):
    """Dezelfde fout tien keer op een dag is één regel met een aantal en de laatste tijd (de Fotowacht meldt elke ronde
    hetzelfde), ook als er andere fouten tussen staan; de volgorde is die van de eerste keer."""
    uit, per = [], {}
    for f in fouten:
        t = str(f.get("tekst") or "")
        if t in per:
            per[t]["aantal"] += 1
            per[t]["tijd"] = f.get("tijd") or per[t]["tijd"]
        else:
            per[t] = {"tijd": f.get("tijd") or "", "tekst": t, "aantal": 1}
            uit.append(per[t])
    return uit


def stand_fout(w, dag):
    """Rood door de hartslag van nu (alleen vandaag) zonder fout in het werkverslag: dan is dit de reden."""
    st = w.get("status") or {}
    if dag == vandaag().isoformat() and str(st.get("status")) in ("fout", "error"):
        return "stand van nu: fout" + (": " + str(st["detail"]) if st.get("detail") else "")
    return ""


def wacht_kort(w):
    """Eén regel per wacht op de tegel: de fout, anders de open melding, anders het eerste item, anders het oordeel."""
    if w.get("leesfout"):
        return "kon niet lezen: " + str(w["leesfout"])
    if w.get("logfout"):
        return "kon niet lezen: " + str(w["logfout"])
    if w.get("fouten"):
        return "fout: " + str(w["fouten"][-1].get("tekst") or "")
    if w.get("stand_fout"):
        return w["stand_fout"]
    if w.get("items"):
        it = w["items"][0]
        return " ".join(x for x in (it.get("tijd") or "", it.get("wie") or "", it.get("wat") or "") if x)
    if w.get("noden"):
        return "open: " + str(w["noden"][0])
    return str(w.get("oordeel") or "")


def dagkeuze(d, naam=None):
    """De knoppen voor de laatste WACHT_DAGEN dagen; vandaag heet vandaag. Met naam: naar die wacht op die dag."""
    eerste = vandaag() - timedelta(days=WACHT_DAGEN - 1)
    uit = []
    for i in range(WACHT_DAGEN):
        x = eerste + timedelta(days=i)
        tekst = dagnaam(x, True)
        if x == vandaag():
            tekst = "vandaag, " + tekst
        pad = url_for("wacht_pagina", naam=naam, dag=x.isoformat()) if naam else url_for("wachten_pagina", dag=x.isoformat())
        uit.append({"dag": x.isoformat(), "naam": tekst, "actief": x == d, "pad": pad})
    return uit


def wacht_dag_uit_vraag():
    """De gevraagde dag, alleen binnen de laatste WACHT_DAGEN dagen (Mehdi 01-11: alleen die dagen); anders 404."""
    dag = request.args.get("dag") or vandaag().isoformat()
    try:
        d = date.fromisoformat(dag)
    except ValueError:
        abort(404)
    if not vandaag() - timedelta(days=WACHT_DAGEN - 1) <= d <= vandaag():
        abort(404)
    return d


@app.route("/wachten")
def wachten_pagina():
    """Alle wachten van één dag als tegels (Mehdi, 01-11-2026: "per dag alle wachten zien"). Tik op een tegel: de wacht."""
    if not mag():
        abort(403)
    d = wacht_dag_uit_vraag()
    gegevens = wachten_dag(d.isoformat())
    return render_template("wachten.html", g=gegevens, naam=dagnaam(d), dag=d.isoformat(), keuze=dagkeuze(d),
                           uitleg=KLEUR_UITLEG)


@app.route("/wachten/<naam>")
def wacht_pagina(naam):
    """Eén wacht op één dag: zijn fouten, open meldingen, alle items en het werkverslag (Mehdi, 01-11-2026: "hun data
    lezen per dag in de wacht zelf"). De dagknoppen blijven bij deze wacht."""
    if not mag():
        abort(403)
    d = wacht_dag_uit_vraag()
    gegevens = wachten_dag(d.isoformat())
    w, vak = None, ""
    if gegevens:
        for v in gegevens["vakken"]:
            for x in v.get("wachten") or []:
                if x.get("naam") == naam:
                    w, vak = x, v.get("vak") or ""
        if w is None:
            abort(404)
    return render_template("wacht.html", g=gegevens, w=w, vak=vak, naam=naam, dagnaam_=dagnaam(d), dag=d.isoformat(),
                           keuze=dagkeuze(d, naam), uitleg=KLEUR_UITLEG, is_vandaag=d == vandaag())


@app.route("/healthz")
def healthz():
    return {"ok": True, "map": os.path.isdir(MAP)}


@app.route("/")
def overzicht():
    if not mag():
        abort(403)
    gisteren = vandaag() - timedelta(days=1)
    eerste = (gisteren - timedelta(days=DAGEN - 1)).isoformat()
    lc = haal_locatie(f"/api/dagcijfers?van={eerste}&tot={gisteren.isoformat()}")
    lc = lc.get("dagen") if isinstance(lc, dict) and isinstance(lc.get("dagen"), dict) else None
    dagen = []
    for i in range(DAGEN):
        dag = (gisteren - timedelta(days=i)).isoformat()
        dagen.append(dag_gegevens(dag, None if lc is None else lc.get(dag, {})))
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
    lb = haal_locatie(f"/api/dagboek/{dag}")
    lb = lb if isinstance(lb, dict) and lb.get("datum") == dag else None
    ritten = verplaatsingen(lb)
    ind = [x for x in (lb or {}).get("indeling") or [] if isinstance(x, dict)]
    rit = [x for x in ind if x.get("soort") == "verplaatsing"]
    lc = None if lb is None else {"punten": len(lb.get("punten") or []), "km": sum(x.get("meter") or 0 for x in rit) / 1000,
                                  "verblijven": sum(1 for x in ind if x.get("soort") == "bezoek"),
                                  "onderweg_min": sum(x.get("minuten") or 0 for x in rit)}
    return render_template("dag.html", d=dag_gegevens(dag, lc), vorige=vorige.isoformat(), ritten=ritten,
                           auto=auto_spoor(lb), buiten=bool((lb or {}).get("buiten_reeks")),
                           volgende=volgende.isoformat() if volgende < vandaag() else None)

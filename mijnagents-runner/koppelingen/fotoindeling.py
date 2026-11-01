#!/usr/bin/env python3
"""De indeling van de foto's van een dag: werf, werkkandidaat, mensen, privé, scherm (T-0120 FOTO-4 en FOTO-5).

Mehdi, 01-11-2026: "voor de fotos zijn de projecten van de bedrijven belangrijk niet de fotos van de mensen" en "ik wil
elke foto en elke file van wachter kunnen zien en begrijpen". Dit is de VM-helft van De Fotowacht (icloud-wacht).

Bron: de foto-metadata die De Fotowacht op de Mac per dag naar het bord stuurt (mac/icloud_wacht.py, metadata_bericht;
het bord bewaart ze als mijnagents-data/fotometadata/<dag>.json, 0600, niet in zijn databank: mijnagents/fotowacht.py):
per foto tijd, GPS, soort en de vlaggen die Photos zelf zet (scherm, app, mensen). Nooit een beeld, nooit een
bestandsnaam. De indeling gebeurt hier, waar de andere bronnen staan, zodat elke Claude haar kan nakijken en de Mac
klein blijft:
  - de projectplekken van het Locatie-dashboard (/api/projectplekken), van elke firma die dat register kent. Nu zijn dat
    alleen H-A-projecten; welke firma's erbij komen is een keuze van Mehdi (LOC-3, VOL-8), niet van deze koppeling. Een
    plekbron erbij is één functie in PLEKBRONNEN;
  - de buitenafspraken met adres en firmacode (elke firma) uit de bak van De Agendawacht, met de plaats uit haar
    adrescache (alleen lezen: hier wordt niets opnieuw gegeocodeerd);
  - de verblijven 'auto bij project' van De Locatiewacht (locatiecontext.context).

Regels (meting 01-11-2026, deel 3), in deze volgorde, alleen op metadata:
  1. schermafbeelding of bewaard uit een app: "scherm of app", alleen geteld;
  2. werf zeker: GPS binnen STRAAL_M van de plaats van een buitenafspraak (VOOR_MIN voor tot NA_MIN na) of van een
     verblijf "auto bij project" (AUTO_SPELING_MIN speling): firma, nummer, project en de afspraak of het verblijf;
  3. werkkandidaat: binnen STRAAL_M van een projectplek, zonder afspraak en zonder auto: Mehdi zegt of het werk was;
  4. mensen (een groot gezicht of Photos' vlag): buiten werk "met mensen", alleen geteld; binnen werk geteld bij het
     project, zonder id, tijd of beeld;
  5. al de rest: privé, alleen geteld (geen plaats, geen tijd per foto);
  6. geen GPS: bij een werfgroep als de tijd tussen twee werkfoto's van die groep valt, anders onbeslist.
Een voorvertoning (FOTO-5) alleen voor een foto (geen video) die werf zeker is met GPS en waarvan Photos zeker zegt dat
er geen mensen op staan en dat het geen schermafbeelding of app-foto is (False, niet onbekend).

Uitvoer, nooit in Dropbox:
  - ~/appportal/mijnagents-data/fotoindeling/<jaar>/<dag>.json (het Dagboek toont het op /fotos/<dag>);
  - op het bord, van icloud-wacht: per werfgroep en per kandidaat een item soort 'foto' voor Mehdi, één telling van wat
    geen werk is (zonder plaats), en een item 'fotoindeling' voor de Mac met de werkfoto's die nog een voorvertoning
    nodig hebben (de Mac maakt die en stuurt ze naar /api/fotovoorbeeld, opgeslagen in mijnagents-data/fotovoorbeeld).
Onbekend is nooit nul: is het Locatie-dashboard niet bereikbaar, dan wordt die dag niet ingedeeld (melding).

Gebruik (op de VM; planning/foto.cron):
    python3 fotoindeling.py                     de laatste INDEEL_DAGEN dagen, en oudere dagen zonder of met gewijzigde indeling
    python3 fotoindeling.py --alles             elke dag van de laatste TERUG_DAGEN opnieuw met de context (één keer per nacht)
    python3 fotoindeling.py --dag JJJJ-MM-DD    één dag
    python3 fotoindeling.py --droog             niets schrijven, alleen tonen
"""
import hashlib
import json
import math
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import bord  # noqa: E402
import locatiecontext as LC  # noqa: E402

NAAM = "icloud-wacht"
BRUSSEL = ZoneInfo("Europe/Brussels")
DATA = os.path.expanduser(os.environ.get("MIJNAGENTS_DATA", "~/appportal/mijnagents-data"))
UIT = os.path.join(DATA, "fotoindeling")                      # niet in Dropbox (planning/mac/data_uit_mehdi_sync.sh)
VOORBEELD = os.path.join(DATA, "fotovoorbeeld")               # de voorvertoningen van de Mac, via /api/fotovoorbeeld
METADATA = os.path.join(DATA, "fotometadata")                 # de metadata van de Mac, via /api/fotometadata (0600)
AGENDA_ADRESSEN = os.path.join(DATA, "agenda-adressen.json")  # adrescache van De Agendawacht (agenda_wacht.ADRES_CACHE)
STRAAL_M = 150
VOOR_MIN, NA_MIN = 30, 90
AUTO_SPELING_MIN = 30
INDEEL_DAGEN = 3            # zoveel laatste dagen worden elke ronde opnieuw ingedeeld (de context kan nog veranderen)
TERUG_DAGEN = 35            # verder terug dan dit kijkt de gewone ronde niet (zoals de Mac, FOTO-2)
VERSIE = 1
BORD_PUBLIEK = "https://mijnagents.globaal.be"               # de werfverslagpagina's, achter Authentik
BRUIKBAAR = ("adres", "override")
# Een buitenafspraak (meting 01-11): een fysiek adres, geen online vergadering en geen reistijd (die staan niet in de bak).
POSTCODE = re.compile(r"\b\d{4}\b")
ONLINE = re.compile(r"(?i)https?://|\b(?:teams|zoom|google meet|meet\.google|webex|online)\b")
# Een link alleen naar een pagina achter Authentik of naar Mehdi's eigen Dropbox-web, nooit een gedeelde Dropbox-link
# (VOL-19: één route achter Authentik).
VEILIGE_LINK = re.compile(r"^https://(?:[a-z0-9-]+\.)*globaal\.be/|^https://www\.dropbox\.com/home/")


# ------------------------------------------------------------------ bronnen

def _haal_locatie(pad):
    with urllib.request.urlopen(f"{LC.LOCATIE}{pad}", timeout=30) as r:
        return json.load(r)


def plekken_locatie():
    """De bruikbare projectplekken van het Locatie-dashboard, van elke firma die het kent (nu alleen H-A)."""
    d = _haal_locatie("/api/projectplekken")
    if not isinstance(d, dict) or not isinstance(d.get("projectplekken"), list):
        raise ValueError("projectplekken ontbreken in het antwoord")      # onbekend, nooit "geen projecten"
    uit = []
    for p in d["projectplekken"]:
        if not p.get("actief") or p.get("uitgesloten") or p.get("geocode_kwaliteit") not in BRUIKBAAR:
            continue
        if not isinstance(p.get("lat"), (int, float)) or not isinstance(p.get("lon"), (int, float)):
            continue
        uit.append({"firma": str(p.get("firma") or ""), "nummer": str(p.get("nummer") or ""), "naam": p.get("naam") or "",
                    "lat": float(p["lat"]), "lon": float(p["lon"]), "link": p.get("link") or ""})
    return uit


# Het register van projectplaatsen. Een bron erbij (een tweede firma, LOC-3 of VOL-8) is een functie die een lijst
# {firma, nummer, naam, lat, lon, link} geeft; een bron die faalt, maakt de dag onbekend.
PLEKBRONNEN = (plekken_locatie,)


def projectplekken():
    gezien, uit = set(), []
    for bron in PLEKBRONNEN:
        for p in bron():
            sleutel = (p["firma"], p["nummer"])
            if p["firma"] and p["nummer"] and sleutel not in gezien:
                gezien.add(sleutel)
                uit.append(p)
    return uit


def _adrescache():
    try:
        with open(AGENDA_ADRESSEN, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def afspraken_van(dag):
    """De buitenafspraken met een fysiek adres en een firmacode (elke firma, nooit privé) uit de bak van De Agendawacht,
    met de plaats uit haar adrescache. Een adres dat daar niet staat, telt als afspraak zonder plaats."""
    rijen = bord.db_lees("SELECT voor, inhoud FROM klaarzet WHERE soort = 'afspraak' AND status != 'vervallen' AND titel LIKE ?",
                         (f"{dag} %",))
    cache, uit, gezien = _adrescache(), [], set()
    for r in rijen:
        try:
            d = json.loads(r["inhoud"] or "{}")
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        firma = str(d.get("firma") or "").upper()
        adres = str(d.get("locatie") or "").strip()
        if (d.get("datum") != dag or not firma or firma == "PRIVE" or str(r["voor"]) == "prive"
                or not (d.get("buiten") or POSTCODE.search(adres)) or ONLINE.search(adres)):
            continue
        try:
            start, einde = _tijd(d.get("start")), _tijd(d.get("einde") or d.get("start"))
        except (TypeError, ValueError):
            continue
        sleutel = (firma, str(d.get("nummer") or ""), start)
        if sleutel in gezien:
            continue
        gezien.add(sleutel)
        plek = cache.get(adres.lower())
        lat, lon = (plek[0], plek[1]) if isinstance(plek, (list, tuple)) and len(plek) == 2 else (None, None)
        uit.append({"firma": firma, "nummer": str(d.get("nummer") or ""), "titel": _titel_kort(d.get("titel") or ""),
                    "start": start, "einde": einde, "lat": lat, "lon": lon})
    return uit


def met_plaats(afspraken, plekken):
    """Een afspraak zonder plaats in de adrescache krijgt de projectplek van haar firma en nummer, als die er is (zoals de
    meting van 01-11: de plaats uit de adrescache of het projectnummer in de titel)."""
    plaats = {(p["firma"], p["nummer"]): p for p in plekken}
    uit = []
    for a in afspraken:
        p = plaats.get((a["firma"], a["nummer"])) if a["lat"] is None and a["nummer"] else None
        uit.append(dict(a, lat=p["lat"], lon=p["lon"]) if p else a)
    return uit


def verblijven_van(dag, plekken):
    """De verblijven 'auto bij project' van De Locatiewacht, met de plaats van hun projectplek. None: onbekend (het
    dashboard antwoordde niet); een lege lijst voor een dag van voor de meetreeks (daar is geen context, en dat klopt)."""
    if not LC.bronbeleid.dag_toegestaan(dag):
        return []
    ctx = LC.context(dag)
    if ctx is None or not isinstance(ctx.get("verblijven"), list):
        return None                                                     # onbekend, nooit "geen verblijven"
    plaats = {(p["firma"], p["nummer"]): p for p in plekken}
    uit = []
    for v in ctx["verblijven"]:
        pr = v.get("project") or {}
        p = plaats.get((str(pr.get("firma") or ""), str(pr.get("nummer") or "")))
        if not v.get("positief") or not p:
            continue
        try:
            aankomst = _tijd(v["aankomst"])
            vertrek = _tijd(v["vertrek"]) if v.get("vertrek") else aankomst + timedelta(hours=12)
        except (KeyError, TypeError, ValueError):
            continue
        uit.append({"firma": p["firma"], "nummer": p["nummer"], "naam": pr.get("naam") or p["naam"],
                    "aankomst": aankomst, "vertrek": vertrek, "lat": p["lat"], "lon": p["lon"]})
    return uit


def bezoeken_van(dag):
    """De werfbezoeken van H-Architects op die dag (tabel werfbezoek van het bord): per dossier de pagina van het bezoek
    achter Authentik en de bezoekmap (een pad in Dropbox, geen gedeelde link; VOL-19). Onleesbaar: leeg."""
    try:
        rijen = bord.db_lees("SELECT dossier, volgnr, bezoekmap FROM werfbezoek WHERE datum = ? ORDER BY volgnr", (dag,))
    except bord.BordOnbekend:
        return {}
    uit = {}
    for r in rijen:
        if re.fullmatch(r"\d{4}", str(r["dossier"] or "")) and str(r["dossier"]) not in uit:
            uit[str(r["dossier"])] = {"pagina": f"{BORD_PUBLIEK}/werfverslag/{r['dossier']}/{int(r['volgnr'] or 0)}",
                                      "bezoekmap": str(r["bezoekmap"] or "")}
    return uit


def metadata_van(dag):
    """De foto's van een dag uit het bestand dat het bord van de Mac kreeg (mijnagents/fotowacht.py, /api/fotometadata),
    of None (er is niets, of het is onleesbaar of onvolledig)."""
    try:
        with open(os.path.join(METADATA, f"{dag}.json"), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("datum") != dag or not isinstance(d.get("fotos"), list):
        return None
    fotos = [f for f in d["fotos"] if isinstance(f, dict) and f.get("id")]
    return fotos if len(fotos) == int(d.get("aantal") or 0) else None


# ------------------------------------------------------------------ de indeling (pure functie)

def _tijd(waarde):
    t = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
    return (t if t.tzinfo else t.replace(tzinfo=BRUSSEL)).astimezone(timezone.utc)


def _uur(t):
    return t.astimezone(BRUSSEL).strftime("%H:%M")


def _titel_kort(t):
    """'!! Mehdi: [HA] 9003 plaatsbezoek' wordt '[HA] 9003 plaatsbezoek' (zoals dagboek/app.titel_kort)."""
    return re.sub(r"^(?:[!?]{2}\s*)?Mehdi:\s*", "", str(t).strip())[:80]


def afstand_m(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 12742000 * math.asin(math.sqrt(a))


def _gps(f):
    lat, lon = f.get("lat"), f.get("lon")
    return isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and -90 <= lat <= 90 and -180 <= lon <= 180


def indeel(dag, fotos, plekken, afspraken, verblijven):
    """De indeling van een dag als dict (zie de module-uitleg). Privé, mensen buiten werk, scherm en onbeslist staan er
    alleen als telling in: geen id, geen tijd, geen plaats."""
    plaats = {(p["firma"], p["nummer"]): p for p in plekken}
    groepen, telling, los = {}, {"prive": 0, "mensen": 0, "overig": 0, "onbeslist": 0}, []

    def groep(sleutel, soort, firma, nummer, naam, anker):
        if sleutel not in groepen:
            p = plaats.get((firma, nummer)) or {}
            link = p.get("link") or ""
            groepen[sleutel] = {"sleutel": sleutel, "soort": soort, "firma": firma, "nummer": nummer,
                                "naam": naam or p.get("naam") or "", "anker": anker, "auto_min": None,
                                "link": link if VEILIGE_LINK.match(link) else "", "fotos": []}
        return groepen[sleutel]

    def zet(g, f, t):
        # Een voorvertoning alleen als Photos zeker is: geen mensen, geen schermafbeelding, geen app-foto (Codex 2).
        zeker = f.get("mensen") is False and f.get("scherm") is False and f.get("app") is False
        g["fotos"].append({"id": f["id"], "t": t, "gps": _gps(f), "video": bool(f.get("video")), "mensen": f.get("mensen"),
                           "zeker": zeker})

    for f in fotos:
        try:
            t = _tijd(f.get("utc"))
        except (TypeError, ValueError):
            t = None
        if f.get("scherm") or f.get("app"):
            telling["overig"] += 1
            continue
        if t is None or not _gps(f):
            los.append((f, t))
            continue
        beste = None
        for a in afspraken:
            if a["lat"] is None or not a["start"] - timedelta(minutes=VOOR_MIN) <= t <= a["einde"] + timedelta(minutes=NA_MIN):
                continue
            d = afstand_m(f["lat"], f["lon"], a["lat"], a["lon"])
            if d <= STRAAL_M and (beste is None or d < beste[0]):
                beste = (d, a)
        if beste:
            a = beste[1]
            g = groep(f"afspraak:{a['firma']}:{a['nummer']}:{_uur(a['start'])}", "zeker", a["firma"], a["nummer"], "",
                      {"soort": "afspraak", "titel": a["titel"], "start": _uur(a["start"]), "einde": _uur(a["einde"])})
            zet(g, f, t)
            continue
        for v in verblijven:
            speling = timedelta(minutes=AUTO_SPELING_MIN)
            if v["aankomst"] - speling <= t <= v["vertrek"] + speling and afstand_m(f["lat"], f["lon"], v["lat"], v["lon"]) <= STRAAL_M:
                g = groep(f"auto:{v['firma']}:{v['nummer']}:{_uur(v['aankomst'])}", "zeker", v["firma"], v["nummer"], v["naam"],
                          {"soort": "auto bij project", "aankomst": _uur(v["aankomst"]), "vertrek": _uur(v["vertrek"])})
                zet(g, f, t)
                break
        else:
            dichtst = min(((afstand_m(f["lat"], f["lon"], p["lat"], p["lon"]), p) for p in plekken), default=None,
                          key=lambda x: x[0])
            if dichtst and dichtst[0] <= STRAAL_M:
                p = dichtst[1]
                zet(groep(f"kandidaat:{p['firma']}:{p['nummer']}", "kandidaat", p["firma"], p["nummer"], p["naam"], None), f, t)
            elif f.get("mensen"):
                telling["mensen"] += 1
            else:
                telling["prive"] += 1
    # 6. zonder GPS: bij een werfgroep als de foto tussen twee van haar werkfoto's valt
    for f, t in los:
        thuis = None
        if t is not None:
            for g in groepen.values():
                tijden = [x["t"] for x in g["fotos"] if x["gps"]]
                if g["soort"] == "zeker" and tijden and min(tijden) < t < max(tijden):
                    thuis = g
                    break
        if thuis:
            zet(thuis, f, t)
        elif f.get("mensen"):
            telling["mensen"] += 1
        else:
            telling["onbeslist"] += 1
    # de auto bij een afspraak van hetzelfde project: hoe lang ze er stond
    for g in groepen.values():
        if g["anker"] and g["anker"]["soort"] == "afspraak":
            ankers = [a for a in afspraken if f"afspraak:{a['firma']}:{a['nummer']}:{_uur(a['start'])}" == g["sleutel"]]
            for a in ankers[:1]:
                minuten = sum(max(0, (min(v["vertrek"], a["einde"] + timedelta(minutes=NA_MIN))
                                      - max(v["aankomst"], a["start"] - timedelta(minutes=VOOR_MIN))).total_seconds() // 60)
                              for v in verblijven if (v["firma"], v["nummer"]) == (g["firma"], g["nummer"]))
                g["auto_min"] = int(minuten) or None
    uit = []
    for g in sorted(groepen.values(), key=lambda g: (g["soort"] != "zeker", g["sleutel"])):
        # Een foto met mensen telt bij het project, maar zonder id, tijd of beeld (Codex 1); de tijden komen van de rest.
        zonder_mensen = sorted((x for x in g["fotos"] if not x["mensen"]), key=lambda x: x["t"])
        tijden = [x["t"] for x in zonder_mensen]
        g.update(van=_uur(min(tijden)) if tijden else "", tot=_uur(max(tijden)) if tijden else "", aantal=len(g["fotos"]),
                 met_mensen=sum(1 for x in g["fotos"] if x["mensen"]), zonder_plaats=sum(1 for x in g["fotos"] if not x["gps"]),
                 video=sum(1 for x in g["fotos"] if x["video"]))
        g["fotos"] = [{"id": x["id"], "tijd": _uur(x["t"]),
                       "voorbeeld": g["soort"] == "zeker" and x["gps"] and not x["video"] and x["zeker"]}
                      for x in zonder_mensen]
        uit.append(g)
    return {"datum": dag, "versie": VERSIE, "werf": [g for g in uit if g["soort"] == "zeker"],
            "kandidaat": [g for g in uit if g["soort"] == "kandidaat"], "telling": telling, "totaal": len(fotos)}


# ------------------------------------------------------------------ schrijven

def _groeptitel(dag, g):
    project = " ".join(x for x in (g["firma"], g["nummer"], g["naam"]) if x)
    if g["soort"] == "kandidaat":
        return f"{dag} {g['van']}-{g['tot']}: kandidaat {project}: {g['aantal']} foto's bij de projectplek, nog niet bevestigd"
    delen = [f"{g['aantal']} werkfoto's"]
    if g["met_mensen"]:
        delen.append(f"{g['met_mensen']} met mensen (niet getoond)")
    if g["zonder_plaats"]:
        delen.append(f"{g['zonder_plaats']} zonder plaats")
    a = g["anker"]
    anker = (f"bij afspraak '{a['titel']}' {a['start']}-{a['einde']}" if a["soort"] == "afspraak"
             else f"auto bij project {a['aankomst']}-{a['vertrek']}")
    if g["auto_min"]:
        anker += f" (auto stond er {g['auto_min']} min)"
    return f"{dag} {g['van']}-{g['tot']}: {project}: {', '.join(delen)}, {anker}"


def bord_items(ind, nodig, oude_sleutels=()):
    """De items op het bord, alle van icloud-wacht. Een werfgroep die in een nieuwe indeling verdween, krijgt aantal 0 en
    een titel die dat zegt (niets wordt gewist)."""
    dag = ind["datum"]
    items, sleutels = [], []
    for g in ind["werf"] + ind["kandidaat"]:
        uniek = f"fotos:{dag}:{g['sleutel']}"
        sleutels.append(uniek)
        items.append({"van": NAAM, "voor": "mehdi", "soort": "foto", "sleutel": dag, "uniek": uniek, "titel": _groeptitel(dag, g),
                      "inhoud": {"datum": dag, "soort": g["soort"], "firma": g["firma"], "nummer": g["nummer"], "naam": g["naam"],
                                 "aantal": g["aantal"], "van": g["van"], "tot": g["tot"], "anker": g["anker"],
                                 "auto_min": g["auto_min"], "met_mensen": g["met_mensen"], "zonder_plaats": g["zonder_plaats"],
                                 "link": g["link"], "bezoek": g.get("bezoek"), "pagina": f"/fotos/{dag}"}})
    for uniek in sorted(set(oude_sleutels) - set(sleutels)):
        items.append({"van": NAAM, "voor": "mehdi", "soort": "foto", "sleutel": dag, "uniek": uniek,
                      "titel": f"{dag}: werfgroep vervallen na een nieuwe indeling", "inhoud": {"datum": dag, "aantal": 0, "vervallen": True}})
    t = ind["telling"]
    rest = sum(t.values())
    items.append({"van": NAAM, "voor": "mehdi", "soort": "foto", "sleutel": dag, "uniek": f"fotos:{dag}:telling",
                  "titel": f"{dag}: geen werk: privé {t['prive']}, met mensen {t['mensen']}, scherm of app {t['overig']}, "
                           f"onbeslist {t['onbeslist']} (alleen geteld, geen plaats)",
                  "inhoud": {"datum": dag, "aantal": rest, **t}})
    items.append(indeling_item(ind, nodig))
    return items, sleutels


def indeling_item(ind, nodig):
    """Het item voor de Mac: welke werkfoto's nog een voorvertoning nodig hebben (mac/icloud_wacht.py, voorvertoningen)."""
    dag, rest = ind["datum"], sum(ind["telling"].values())
    werk = sum(g["aantal"] for g in ind["werf"])
    return {"van": NAAM, "voor": "fotoindeling", "soort": "fotoindeling", "sleutel": dag, "uniek": f"fotoindeling:{dag}",
            "titel": f"{dag} indeling: {werk} werkfoto's in {len(ind['werf'])} werfgroepen, "
                     f"{sum(g['aantal'] for g in ind['kandidaat'])} kandidaat, {rest} geen werk; {len(nodig)} voorvertoningen nodig",
            "inhoud": {"datum": dag, "versie": VERSIE, "voorbeeld_nodig": nodig}}


def voorbeeld_nodig(ind):
    """De werkfoto's die een voorvertoning mogen krijgen en er op de VM nog geen hebben."""
    map_ = os.path.join(VOORBEELD, ind["datum"])
    return [f["id"] for g in ind["werf"] for f in g["fotos"]
            if f["voorbeeld"] and not os.path.isfile(os.path.join(map_, f"{f['id']}.jpg"))]


def niet_meer_toegelaten(ind):
    """Voorvertoningen op de VM van foto's die deze indeling niet (meer) als werkfoto zonder mensen aanwijst, bijvoorbeeld
    omdat Photos later een gezicht vond (Codex 1). Het Dagboek toont ze al niet; deel_in haalt ze weg: het zijn afgeleide
    beeldjes die de VM zelf maakte, geen bron, en een foto van mensen hoort er niet."""
    map_ = os.path.join(VOORBEELD, ind["datum"])
    mag = {f["id"] for g in ind["werf"] for f in g["fotos"] if f["voorbeeld"]}
    try:
        namen = os.listdir(map_)
    except FileNotFoundError:
        return []
    return [os.path.join(map_, n) for n in sorted(namen) if n.endswith(".jpg") and n[:-4] not in mag]


def _pad(dag):
    return os.path.join(UIT, dag[:4], f"{dag}.json")


def lees_indeling(dag):
    try:
        with open(_pad(dag), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _bewaar(dag, ind):
    pad = _pad(dag)
    os.makedirs(os.path.dirname(pad), exist_ok=True)
    tijdelijk = f"{pad}.{os.getpid()}.tmp"
    fd = os.open(tijdelijk, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)     # meteen 0640, nooit even 0644
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(ind, f, ensure_ascii=False, indent=1)
    os.chmod(tijdelijk, 0o640)
    os.replace(tijdelijk, pad)


def _hash(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()


def _voorbeelden_bijwerken(dag, oud, droog):
    """Een ongewijzigde indeling: alleen de lijst van nodige voorvertoningen bijwerken als er intussen beelden kwamen."""
    nodig = voorbeeld_nodig(oud)
    if nodig == (oud.get("voorbeeld_nodig") or []):
        return None
    if not droog:
        oud["voorbeeld_nodig"] = nodig
        _bewaar(dag, oud)
        bord.call("/api/klaarzet", {"items": [indeling_item(oud, nodig)]})
    return f"{len(nodig)} voorvertoningen nog nodig"


def deel_in(dag, ag, plekken, droog=False, recent=True):
    """Een dag indelen en schrijven. Een oudere dag (niet recent) wordt alleen opnieuw ingedeeld als de foto-metadata
    veranderde of er nog geen indeling is; een recente dag ook als de context veranderde (afspraak, verblijf, plek).
    Geeft een korte uitslag (str), of None als er niets te doen was."""
    fotos = metadata_van(dag)
    if fotos is None:
        return None
    oud = lees_indeling(dag)
    meta = _hash(fotos)
    if oud and oud.get("meta_hash") == meta and not recent:
        return _voorbeelden_bijwerken(dag, oud, droog)
    afspraken = met_plaats(afspraken_van(dag), plekken)
    verblijven = verblijven_van(dag, plekken)
    if verblijven is None:
        ag.log(f"indeling {dag}", "melding", "foto's niet ingedeeld: het Locatie-dashboard antwoordde niet (onbekend, niet leeg)")
        return "onbekend"
    bron = _hash([fotos, plekken, afspraken, verblijven])
    if oud and oud.get("bron_hash") == bron:
        return _voorbeelden_bijwerken(dag, oud, droog)
    ind = indeel(dag, fotos, plekken, afspraken, verblijven)
    bezoeken = bezoeken_van(dag)
    for g in ind["werf"] + ind["kandidaat"]:
        g["bezoek"] = bezoeken.get(g["nummer"]) if g["firma"] == "HARC" else None
    nodig = voorbeeld_nodig(ind)
    items, sleutels = bord_items(ind, nodig, (oud or {}).get("items") or ())
    ind.update(meta_hash=meta, bron_hash=bron, voorbeeld_nodig=nodig, items=sleutels,
               gemaakt=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               bronnen={"projectplekken": len(plekken), "afspraken": len(afspraken),
                        "afspraken_zonder_plaats": sum(1 for a in afspraken if a["lat"] is None),
                        "locatiecontext": "gelezen" if LC.bronbeleid.dag_toegestaan(dag) else "voor de meetreeks",
                        "verblijven": len(verblijven)})
    werk = sum(g["aantal"] for g in ind["werf"])
    kort = (f"{ind['totaal']} foto's: {werk} werkfoto's in {len(ind['werf'])} werfgroepen, "
            f"{sum(g['aantal'] for g in ind['kandidaat'])} kandidaat, {sum(ind['telling'].values())} geen werk; "
            f"{len(nodig)} voorvertoningen nodig")
    if droog:
        print(dag, kort)
        return kort
    # Eerst weghalen wat niet meer mag (privacy gaat voor), dan het bord, en pas daarna de indeling met haar hash bewaren:
    # mislukt het bord, dan probeert de volgende ronde het opnieuw (Codex 2).
    weg = niet_meer_toegelaten(ind)
    for pad in weg:
        os.remove(pad)
    uit = bord.call("/api/klaarzet", {"items": items})
    _bewaar(dag, ind)
    ag.log(f"indeling {dag}", "schrijf", kort,
           f"{len(afspraken)} buitenafspraken met firmacode ({ind['bronnen']['afspraken_zonder_plaats']} zonder plaats), "
           f"{len(verblijven)} verblijven auto bij project, {len(plekken)} projectplekken; "
           f"bord: {uit.get('nieuw', 0)} nieuw, {uit.get('bijgewerkt', 0)} bijgewerkt, {uit.get('bestaand', 0)} al bekend"
           + (f"; {len(weg)} voorvertoningen weggehaald (niet meer toegelaten)" if weg else ""))
    return kort


def te_doen(vandaag, dag=None):
    """De dagen voor deze ronde: met --dag die ene; anders de dagen met een metadatabestand van de laatste TERUG_DAGEN."""
    if dag:
        return [dag]
    eerste = (vandaag - timedelta(days=TERUG_DAGEN)).isoformat()
    try:
        namen = os.listdir(METADATA)
    except FileNotFoundError:
        return []
    return sorted(n[:10] for n in namen if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", n) and n[:10] >= eerste)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    dag = argv[argv.index("--dag") + 1] if "--dag" in argv and argv.index("--dag") + 1 < len(argv) else None
    if dag:
        date.fromisoformat(dag)
    droog = "--droog" in argv
    alles = "--alles" in argv          # Codex 2: ook een oudere dag volgt een rechtgezette afspraak of plek
    ag = bord.Agent(NAAM)
    vandaag = datetime.now(BRUSSEL).date()
    try:
        plekken = projectplekken()
    except Exception as e:  # noqa: BLE001  onbekend, nooit een indeling zonder projectplekken
        ag.log("indeling", "melding", f"foto's niet ingedeeld: projectplekken niet gelezen ({type(e).__name__})")
        if not droog:
            ag.log_verstuur()
        return 0
    fout = 0
    for d in te_doen(vandaag, dag):
        recent = bool(dag) or alles or d >= (vandaag - timedelta(days=INDEEL_DAGEN - 1)).isoformat()
        try:
            deel_in(d, ag, plekken, droog=droog, recent=recent)
        except bord.BordOnbekend as e:
            ag.log(f"indeling {d}", "melding", f"foto's niet ingedeeld: bord niet leesbaar ({e.reden})")
        except Exception as e:  # noqa: BLE001  een eigen fout: zichtbaar, de andere dagen gaan door
            ag.log(f"indeling {d}", "fout", f"indeling mislukt ({type(e).__name__})")
            fout = 1
    if not droog:
        ag.log_verstuur()
    return fout


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""De Agendawacht (Privé) — leest Mehdi's agenda's volgens de agenda-regels van Mehdi
en zet klaar wat anderen nodig hebben.

Elke werkdag om 06:30 en daarna elke twee uur:
  1. de negen actieve agenda's (AGENDA_KALENDERS in mijnagents-data/.env, anders
     de vaste lijst hieronder) van gisteren tot zeven dagen vooruit;
  2. per afspraak de titel lezen volgens de titelconventie: "Mehdi: !! [HA-KB] WB 2310 -
     werfbezoek ..." -> firma HA, soort KB (klant buiten), type WB, nummer 2310;
     "!!" = buiten met reistijd, "??" = niet bevestigd; "Reistijd"-blokken slaan we over;
  3. koppelen aan een deal (Pipedrive H-Architects: projectnummer, anders naam);
  4. klaarzetten per firma (h-architects, unabo, harmoniebouw, contrax; PRIVE -> mehdi),
     het dagplan van vandaag en "gisteren zonder verslag" voor Mehdi, en een signaal
     voor titels die de conventie niet volgen (zodat we beter communiceren);
  5. werkverslag op het bord.
Leest alleen. Verandert nooit een afspraak.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import agenda  # noqa: E402
import bellen  # noqa: E402
import projectadressen  # noqa: E402
import bord  # noqa: E402
import pipedrive  # noqa: E402

NAAM = "agenda-wacht"
ag = bord.Agent(NAAM)

# De negen actieve agenda's van Mehdi (Feestdagen is read-only).
KALENDERS = {
    "mehdiprivewerkagenda@gmail.com": "mehdiprivewerkagenda (intern + Harmoniebouw-werk)",
    "73e8b6359d04b7bdb02aa045e668cd6f9d9f007bec51ce370494e7de7501f0c4@group.calendar.google.com": "H-Architects",
    "b135d9900db83399539bb5fe4ad9dc1ace19af20273c078ce2180cc47e9232fe@group.calendar.google.com": "UNABO",
    "e108191db825d97fb068a781463302c0e9c527d3927a85a514b1c8c5754b6048@group.calendar.google.com": "Harmoniebouw",
    "contraxcalendar@gmail.com": "Contrax",
    "385ee9ff8749fe5e5929090550d42611f4ce2437d11b56f3d4d943619b4c479f@group.calendar.google.com": "Lara",
    "bfe28ee64dc72b449582af5e6a9fc6af3669709adf07adc8b49eb97666f07981@group.calendar.google.com": "Prive Buiten",
    "zoomafspraken@gmail.com": "zoomafspraken (sales via Calendly)",
    "en.be#holiday@group.v.calendar.google.com": "Feestdagen BE",
}
FIRMA_AFDELING = {"HA": "h-architects", "UNABO": "unabo", "HB": "harmoniebouw", "HARMONIEBOUW": "harmoniebouw",
                  "CONTRAX": "contrax", "ENERGIE": "unabo", "TKN": "tkn", "ELEVAIT": "elevait", "PRIVE": "mehdi"}
KALENDER_AFDELING = {"H-Architects": "h-architects", "UNABO": "unabo", "Harmoniebouw": "harmoniebouw", "Contrax": "contrax",
                     "zoomafspraken (sales via Calendly)": "h-architects"}
SOORT = {"KB": "klant buiten", "PB": "prospect buiten (plaatsbezoek)", "KO": "klant online", "PO": "prospect online", "IN": "intern"}
TYPES = {"WB": "werfbezoek", "OPL": "oplevering", "PLB": "plaatsbeschrijving", "SCN": "3D-scan", "EPB": "EPB"}
CODE_RE = re.compile(r"\[(HA|UNABO|HB|HARMONIEBOUW|CONTRAX|ENERGIE|TKN|ELEVAIT|PRIVE)(?:-(KB|PB|KO|PO|IN))?\]", re.I)


def kalenders():
    ruw = os.environ.get("AGENDA_KALENDERS", "").strip()
    return [k.strip() for k in ruw.split(",") if k.strip()] or list(KALENDERS)


def lees_titel(titel):
    """Ontleedt een titel volgens Mehdi's titelconventie. Geeft dict met firma, soort, type,
    nummer, klant, buiten (!!), onzeker (??), reistijd, conform."""
    t = titel.strip()
    uit = {"reistijd": bool(re.search(r"reistijd", t, re.I)) or t.startswith("🚗"),
           "buiten": "!!" in t, "onzeker": "??" in t, "firma": "", "soort": "", "type": "", "nummer": "", "klant": ""}
    m = CODE_RE.search(t)
    if m:
        uit["firma"] = m.group(1).upper()
        uit["soort"] = (m.group(2) or "").upper()
    rest = CODE_RE.sub("", t)
    rest = re.sub(r"^\s*(mehdi|siyan|shelton|angela)\s*:\s*", "", rest, flags=re.I)
    rest = rest.replace("!!", "").replace("??", "").strip(" -")
    mt = re.match(r"^\s*(WB|OPL|PLB|SCN|EPB)\b", rest, re.I)
    if mt:
        uit["type"] = mt.group(1).upper()
        rest = rest[mt.end():].strip(" -")
    mn = re.search(r"\b(\d{4,5})\b", rest)
    if mn:
        uit["nummer"] = mn.group(1)
    uit["klant"] = re.sub(r"\b\d{4,5}\b", "", rest).strip(" -:").split(" - ")[0][:80]
    uit["conform"] = bool(m) or uit["reistijd"]
    return uit


def deals_index():
    d = pipedrive.get("harchitects", "/deals", {"status": "open", "limit": 500})
    items = d if isinstance(d, list) else (d or {}).get("data") or []
    uit = []
    for x in items:
        titel = x.get("title", "")
        m = re.match(r"^\s*((?:26|56)\d\d)\b", titel)
        uit.append({"id": x.get("id"), "titel": titel, "nummer": m.group(1) if m else "",
                    "delen": {w for w in re.split(r"[^a-z0-9]+", titel.lower()) if len(w) > 2 and not w.isdigit()}})
    return uit


def koppel(info, titel, deals):
    if info["nummer"]:
        for d in deals:
            if d["nummer"] == info["nummer"]:
                return d, "projectnummer in de titel"
    delen = {w for w in re.split(r"[^a-z0-9]+", (info["klant"] or titel).lower()) if len(w) > 2}
    beste, score = None, 0
    for d in deals:
        s = len(d["delen"] & delen)
        if s > score:
            beste, score = d, s
    return (beste, f"naam in de titel ({score} woorden)") if beste and score >= 2 else (None, "")


ONLINE_MIN = int(os.environ.get("AGENDA_HERINNERING_ONLINE", "5"))
BUITEN_MIN = int(os.environ.get("AGENDA_HERINNERING_BUITEN", "30"))
OVERIG_MIN = int(os.environ.get("AGENDA_HERINNERING_OVERIG", "10"))


PROSPECT_FIRMAS = ("HA", "UNABO", "TKN")
PROSPECT_SOORTEN = ("PO", "PB")


def melding_gewenst(a):
    """De regel van Mehdi (11-09-2026): alleen afspraken met prospecten van
    H-Architects, UNABO en TKN (codes PO en PB) krijgen een melding. Geen intern,
    geen terugkerende afspraken, geen reistijd, geen hele-dag-items."""
    info = lees_titel(a["titel"])
    if a.get("hele_dag") or a.get("_terugkerend") or info["reistijd"]:
        return False, info
    return (info["firma"] in PROSPECT_FIRMAS and info["soort"] in PROSPECT_SOORTEN), info


def _patch(a, body, tok):
    import urllib.parse
    import urllib.request
    url = f"{agenda.API}/calendars/{urllib.parse.quote(a['kalender'], safe='')}/events/{urllib.parse.quote(a['id'], safe='')}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PATCH",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30)


def herinneringen_zetten(items, alleen_dag=None):
    """Werkwijze stap 5: een pop-upherinnering op elke komende prospect-afspraak
    (regel in melding_gewenst) die er nog geen heeft: online 5 min, buiten (!!) 30 min.
    Een herinnering die ik zelf eerder op een niet-gewenste afspraak zette (mijn
    handtekening: één pop-up van 10 of 30 min) haal ik weer weg, zodat intern en
    terugkerend stil blijven. Bestaande herinneringen van Mehdi laat ik staan.
    Geeft (gezet, al, weggehaald, fout)."""
    tok = agenda._toegang()
    nu_iso = datetime.now().astimezone().isoformat()
    gezet, al, weg, fout = 0, 0, 0, 0
    for a in items:
        if a["start"] < nu_iso[:len(a["start"])] or a.get("kalender", "").startswith("en.be#"):
            continue
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        gewenst, info = melding_gewenst(a)
        r = a.get("_reminders") or {}
        eigen = r.get("overrides") or []
        mijn = len(eigen) == 1 and eigen[0].get("method") == "popup" and eigen[0].get("minutes") in (OVERIG_MIN, BUITEN_MIN, ONLINE_MIN)
        try:
            if gewenst and not eigen:
                minuten = BUITEN_MIN if info["buiten"] else ONLINE_MIN
                _patch(a, {"reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": minuten}]}}, tok)
                gezet += 1
            elif gewenst:
                al += 1
            elif not gewenst and mijn:
                _patch(a, {"reminders": {"useDefault": True, "overrides": []}}, tok)
                weg += 1
        except Exception as e:  # noqa: BLE001
            fout += 1
            print("herinnering mislukt:", a["titel"][:40], type(e).__name__, file=sys.stderr)
    return gezet, al, weg, fout


# Kleuren (de regels van Mehdi, Google-kleurnummers): roze 4 flamingo = Lara;
# oranje 6 mandarijn = prospect (PO, PB); rood 11 tomaat = !! buiten en reistijd;
# blauw 7 pauw = klant online (KO); groen 10 basilicum = intern (IN); geel 5 banaan = ?? niet bevestigd.
KLEURNAAM = {"4": "roze", "6": "oranje", "11": "rood", "7": "blauw", "10": "groen", "5": "geel"}
ALLEEN_VANDAAG = "--vandaag" in sys.argv


def kleur_gewenst(a, info):
    kal = KALENDERS.get(a.get("kalender", ""), "")
    if kal == "Lara":
        return "4"
    if info["reistijd"] or info["buiten"]:
        return "11"
    if info["onzeker"]:
        return "5"
    if info["soort"] in ("PO", "PB"):
        return "6"
    if info["soort"] == "KO":
        return "7"
    if info["soort"] == "IN":
        return "10"
    return ""   # titel zonder code: geen regel, kleur laten staan


def kleuren_zetten(items, alleen_dag=None):
    """Werkwijze: elke komende afspraak krijgt de kleur van zijn soort. Alleen als de
    kleur afwijkt; agenda's waar Mehdi enkel leesrecht heeft (Lara) kan ik niet
    veranderen en meld ik. Geeft (gezet, al_goed, geen_regel, fout)."""
    tok = agenda._toegang()
    nu_dag = datetime.now().date().isoformat()
    gezet, goed, geen, fout = 0, 0, 0, 0
    for a in items:
        if a["start"][:10] < nu_dag or a.get("kalender", "").startswith("en.be#"):
            continue
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        info = lees_titel(a["titel"])
        wens = kleur_gewenst(a, info)
        if not wens:
            geen += 1
            continue
        if (a.get("_kleur") or "") == wens:
            goed += 1
            continue
        try:
            _patch(a, {"colorId": wens}, tok)
            gezet += 1
        except Exception as e:  # noqa: BLE001
            fout += 1
            print("kleur mislukt:", a["titel"][:40], type(e).__name__, file=sys.stderr)
    return gezet, goed, geen, fout


# Reistijd, taak van de Agendawacht. Thuisbasis en bufferminuten in de omgeving.
THUIS = os.environ.get("AGENDA_THUIS", "Herfstlaan 65, 3010 Leuven")
BUFFER_MIN = int(os.environ.get("AGENDA_REISTIJD_BUFFER", "10"))
ADRES_CACHE = os.path.expanduser("~/appportal/mijnagents-data/agenda-adressen.json")
DAG_ARG = None
for _i, _a in enumerate(sys.argv):
    if _a == "--dag" and _i + 1 < len(sys.argv):
        DAG_ARG = sys.argv[_i + 1]


def _cache_laden():
    try:
        return json.load(open(ADRES_CACHE))
    except (OSError, ValueError):
        return {}


def _cache_bewaren(c):
    os.makedirs(os.path.dirname(ADRES_CACHE), exist_ok=True)
    json.dump(c, open(ADRES_CACHE, "w"), ensure_ascii=False)


def coord(adres, cache):
    import time
    import urllib.parse
    import urllib.request
    sleutel = adres.strip().lower()
    if sleutel in cache:
        return cache[sleutel]
    time.sleep(1.1)
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": adres, "format": "jsonv2", "limit": 1, "countrycodes": "be,nl"})
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "MehdiAgents-agendawacht/1.0 (mch@h-architects.be)"}), timeout=20))
        uit = [float(d[0]["lat"]), float(d[0]["lon"])] if d else None
    except Exception:  # noqa: BLE001
        uit = None
    cache[sleutel] = uit
    return uit


# Filefactor op de vrije rijtijd, per vertrekuur op een werkdag (Vlaanderen: ochtend- en
# avondspits). Weekend en feestdagen: 1.0. Mehdi kan dit bijstellen in de werkwijze; de
# tabel hier is de uitvoering ervan.
SPITS = [((7, 0), (9, 30), 1.6), ((6, 30), (7, 0), 1.3), ((9, 30), (10, 0), 1.3),
         ((16, 0), (18, 30), 1.6), ((15, 30), (16, 0), 1.3), ((18, 30), (19, 0), 1.3)]
DAL_FACTOR = 1.1


def filefactor(vertrek):
    if vertrek.weekday() >= 5:
        return 1.0
    u = (vertrek.hour, vertrek.minute)
    for van, tot, f in SPITS:
        if van <= u < tot:
            return f
    return DAL_FACTOR


def vrije_rijtijd_min(van, naar):
    import urllib.request
    url = f"https://router.project-osrm.org/route/v1/driving/{van[1]},{van[0]};{naar[1]},{naar[0]}?overview=false"
    d = json.load(urllib.request.urlopen(url, timeout=20))
    return d["routes"][0]["duration"] / 60


ROUTES_KEY = os.environ.get("GOOGLE_ROUTES_KEY", "").strip()

# Harde dagstop op de Google-aanroepen. Google laat de dagquota van de Routes API niet
# verlagen (in de console staat die rij op "Adjustable: No"), dus houden we de teller
# zelf bij. Bij het plafond rekent de wacht verder met de filefactor en komt het op het
# bord. 100 per dag is ruim: ook een volle maand op het plafond blijft onder de 5.000
# gratis aanvragen per maand.
ROUTES_DAGLIMIET = int(os.environ.get("AGENDA_ROUTES_DAGLIMIET", "100"))
ROUTES_TELLER = os.path.expanduser("~/appportal/mijnagents-data/routes-teller.json")
ROUTES_GESTOPT = False


def routes_vandaag():
    """Geeft (datum, aantal Google-aanroepen vandaag). De teller begint elke dag opnieuw."""
    vandaag = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(ROUTES_TELLER) as f:
            d = json.load(f)
        return vandaag, (int(d["aantal"]) if d.get("dag") == vandaag else 0)
    except (OSError, ValueError, KeyError, TypeError):
        return vandaag, 0


def routes_tel_op():
    """Telt een aanroep mee voordat hij gedaan wordt: een mislukte aanroep telt bij
    Google evengoed mee, dus hier ook."""
    vandaag, aantal = routes_vandaag()
    try:
        os.makedirs(os.path.dirname(ROUTES_TELLER), exist_ok=True)
        with open(ROUTES_TELLER, "w") as f:
            json.dump({"dag": vandaag, "aantal": aantal + 1}, f)
    except OSError as e:  # noqa: BLE001
        print("routes-teller niet weggeschreven:", e, file=sys.stderr)
    return aantal + 1


def google_rijtijd_min(van, naar, vertrek):
    """Rijtijd met live verkeer via Google Routes API (alleen als GOOGLE_ROUTES_KEY gezet is).
    Vertrek moet in de toekomst liggen; anders neemt Google 'nu'. Geeft minuten of None."""
    import urllib.request
    from datetime import timezone
    body = {"origin": {"location": {"latLng": {"latitude": van[0], "longitude": van[1]}}},
            "destination": {"location": {"latLng": {"latitude": naar[0], "longitude": naar[1]}}},
            "travelMode": "DRIVE", "routingPreference": "TRAFFIC_AWARE_OPTIMAL"}
    if vertrek > datetime.now().astimezone():
        body["departureTime"] = vertrek.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req = urllib.request.Request("https://routes.googleapis.com/directions/v2:computeRoutes", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "X-Goog-Api-Key": ROUTES_KEY, "X-Goog-FieldMask": "routes.duration"})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=20))
        return float(d["routes"][0]["duration"].rstrip("s")) / 60
    except Exception:  # noqa: BLE001
        return None


def rijtijd_min(van, naar, vertrek):
    """Rijtijd in minuten + buffer, afgerond op 5. Met GOOGLE_ROUTES_KEY: live verkeer van Google
    op het vertrekuur (factor 'live'). Zonder: vrije rijtijd (OSRM) x filefactor op het vertrekuur.
    Geeft (minuten, factor)."""
    global ROUTES_GESTOPT
    import math
    if ROUTES_KEY:
        _, gebruikt = routes_vandaag()
        if gebruikt >= ROUTES_DAGLIMIET:
            ROUTES_GESTOPT = True
        else:
            routes_tel_op()
            live = google_rijtijd_min(van, naar, vertrek)
            if live is not None:
                return int(math.ceil((live + BUFFER_MIN) / 5) * 5), "live"
    vrij = vrije_rijtijd_min(van, naar)
    f = filefactor(vertrek)
    return int(math.ceil((vrij * f + BUFFER_MIN) / 5) * 5), f


def plaatsnaam(adres):
    m = re.search(r"\d{4}\s+([A-Za-zÀ-ÿ' -]+)", adres or "")
    return (m.group(1).strip() if m else (adres or "").split(",")[0]).strip()[:30]


def _insert(kalender, body, tok):
    import urllib.parse
    import urllib.request
    url = f"{agenda.API}/calendars/{urllib.parse.quote(kalender, safe='')}/events"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def reistijd_zetten(items, alleen_dag=None):
    """Werkwijze: elke komende afspraak buiten (!!, of PB/KB met een adres) krijgt een
    blok 'Reistijd -> plaats' ervoor en 'Reistijd <- plaats' erna, met de rijtijd
    vanaf thuis (of de vorige buitenafspraak van die dag) plus buffer, rood, op
    dezelfde agenda. Bestaat er al een reistijdblok binnen drie uur voor of na,
    dan niets. De afspraak zelf krijgt een herinnering op het vertrekmoment plus 5.
    Geeft (gemaakt, al, geen_adres, fout, regels)."""
    from datetime import timedelta
    tok = agenda._toegang()
    cache = _cache_laden()
    thuis = coord(THUIS, cache)
    nu = datetime.now().astimezone()
    gemaakt, al, geen_adres, fout, regels = 0, 0, 0, 0, []
    reistijden = [x for x in items if lees_titel(x["titel"])["reistijd"]]
    projecten = projectadressen.index()
    buiten = []
    for a in items:
        if a.get("hele_dag") or a.get("kalender", "").startswith("en.be#"):
            continue
        info = lees_titel(a["titel"])
        adres = a.get("locatie") or ""
        fysiek = bool(adres) and not adres.lower().startswith("http")
        bron_adres = "agenda"
        if not fysiek and info["nummer"] and info["nummer"] in projecten:
            adres, fysiek, bron_adres = projecten[info["nummer"]]["adres"], True, "projectmap"
        if info["reistijd"] or not (info["buiten"] or (info["soort"] in ("PB", "KB") and fysiek)):
            continue
        a["_bron_adres"] = bron_adres
        if fysiek and bron_adres == "agenda" and info["nummer"] in projecten:
            g = projecten[info["nummer"]]["gemeente"].lower()
            if g and g not in adres.lower():
                regels.append(f"{a['start'][:16]} {a['titel'][:50]}: adres in agenda ({adres[:35]}) wijkt af van projectmap {info['nummer']} ({projecten[info['nummer']]['adres'][:35]})")
        try:
            start = datetime.fromisoformat(a["start"]); einde = datetime.fromisoformat(a["einde"])
        except ValueError:
            continue
        if start < nu or (alleen_dag and a["start"][:10] != alleen_dag):
            continue
        buiten.append((start, einde, a, info, adres, fysiek))
    buiten.sort(key=lambda x: x[0])
    vorige_per_dag = {}
    for start, einde, a, info, adres, fysiek in buiten:
        dag = a["start"][:10]
        if not fysiek:
            geen_adres += 1
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: geen adres, geen reistijd")
            continue
        doel = coord(adres, cache)
        if not (doel and thuis):
            geen_adres += 1
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: adres niet gevonden ({adres[:40]})")
            continue
        vertrek_van = vorige_per_dag.get(dag, thuis)
        vorige_per_dag[dag] = doel
        # Zuinig met aanvragen (Google Routes Pro: 5.000 gratis per maand): bestaan mijn twee
        # blokken al, dan herbereken ik alleen in de eerste ronde van de dag (voor 08:00) of met --dag.
        def _bestaand(t0, t1):
            for x in reistijden:
                if x["kalender"] == a["kalender"] and "T" in x["start"] and t0 <= datetime.fromisoformat(x["start"]) <= t1:
                    return x
            return None
        if (_bestaand(start - timedelta(hours=3), start) and _bestaand(einde, einde + timedelta(hours=3))
                and nu.hour >= 8 and not DAG_ARG):
            al += 2
            continue
        try:
            # eerste schatting om het vertrekuur te kennen, dan de filefactor op dat uur
            heen, _ = rijtijd_min(vertrek_van, doel, start)
            heen, fh = rijtijd_min(vertrek_van, doel, start - timedelta(minutes=heen))
            terug, ft = rijtijd_min(doel, thuis, einde)
        except Exception as e:  # noqa: BLE001
            fout += 1
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: rijtijd niet berekend ({type(e).__name__})")
            continue
        plaats = plaatsnaam(adres)
        def bestaand(t0, t1):
            for x in reistijden:
                if x["kalender"] == a["kalender"] and "T" in x["start"] and t0 <= datetime.fromisoformat(x["start"]) <= t1:
                    return x
            return None

        def eigen(x):
            return "OSRM" in (x.get("omschrijving") or "")

        def bijwerken(x, s, e, tekst):
            """Een blok dat ik zelf maakte, pas ik aan als de rijtijd meer dan 10 min verschilt."""
            duur_oud = (datetime.fromisoformat(x["einde"]) - datetime.fromisoformat(x["start"])).total_seconds() / 60
            if eigen(x) and abs(duur_oud - (e - s).total_seconds() / 60) >= 10:
                _patch(x, {"start": {"dateTime": s.isoformat()}, "end": {"dateTime": e.isoformat()}, "description": tekst}, tok)
                return True
            return False
        uitleg_h = f"Reistijd voor: {a['titel']} ({heen} min = " + ("live verkeer Google" if fh == "live" else f"vrije rijtijd x filefactor {fh}") + f" + {BUFFER_MIN} min buffer, OSRM; adres uit {bron_adres})"
        uitleg_t = f"Reistijd na: {a['titel']} ({terug} min = " + ("live verkeer Google" if ft == "live" else f"vrije rijtijd x filefactor {ft}") + f" + {BUFFER_MIN} min buffer, OSRM)"
        kleur = {"colorId": "11", "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 5}]}}
        try:
            x = bestaand(start - timedelta(hours=3), start)
            if x:
                al += 1
                if bijwerken(x, start - timedelta(minutes=heen), start, uitleg_h):
                    gemaakt += 1
            else:
                _insert(a["kalender"], {"summary": f"🚗 Reistijd → {plaats}", "start": {"dateTime": (start - timedelta(minutes=heen)).isoformat()},
                                        "end": {"dateTime": start.isoformat()}, "description": uitleg_h, **kleur}, tok)
                gemaakt += 1
            x = bestaand(einde, einde + timedelta(hours=3))
            if x:
                al += 1
                if bijwerken(x, einde, einde + timedelta(minutes=terug), uitleg_t):
                    gemaakt += 1
            else:
                _insert(a["kalender"], {"summary": f"🚗 Reistijd ← {plaats}", "start": {"dateTime": einde.isoformat()},
                                        "end": {"dateTime": (einde + timedelta(minutes=terug)).isoformat()}, "description": uitleg_t,
                                        **{"colorId": "11", "reminders": {"useDefault": False, "overrides": []}}}, tok)
                gemaakt += 1
            _patch(a, {"reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": heen + 5}]}}, tok)
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: heen {heen} min (file x{fh}), terug {terug} min (file x{ft}), adres uit {bron_adres}, herinnering {heen + 5} min vooraf")
        except Exception as e:  # noqa: BLE001
            fout += 1
            regels.append(f"{a['start'][:16]} {a['titel'][:50]}: reistijd niet gezet ({type(e).__name__})")
    _cache_bewaren(cache)
    return gemaakt, al, geen_adres, fout, regels


def onvolledige_afspraken(items, vandaag):
    """Regel van Mehdi (11-09-2026): elke klantafspraak draagt een projectnummer; online volstaat
    het nummer, buiten moet er ook een adres zijn (uit de agenda of uit de projectmap).
    Prospecten (PO/PB) hebben nog geen nummer: daar vraag ik alleen een adres bij buiten."""
    projecten = projectadressen.index()
    uit = []
    for a in items:
        if a.get("hele_dag") or a["start"][:10] < vandaag or a.get("kalender", "").startswith("en.be#") or a.get("_terugkerend"):
            continue
        info = lees_titel(a["titel"])
        if info["reistijd"] or info["soort"] == "IN" or not (info["firma"] or info["buiten"]):
            continue
        adres = a.get("locatie") or ""
        fysiek = bool(adres) and not adres.lower().startswith("http")
        wat = []
        if info["soort"] in ("KB", "KO") and not info["nummer"]:
            wat.append("geen projectnummer")
        if info["soort"] in ("KB", "PB") or info["buiten"]:
            if not fysiek and not (info["nummer"] in projecten):
                wat.append("geen adres (niet in agenda, geen projectmap met dit nummer)")
        if wat:
            uit.append(f"{a['start'][:16]} {a['titel'][:60]} ({KALENDERS.get(a['kalender'], '')[:12]}): " + ", ".join(wat))
    return uit


BEL_ONLINE_MIN = int(os.environ.get("AGENDA_BEL_ONLINE", "5"))
BEL_BUITEN_MIN = int(os.environ.get("AGENDA_BEL_BUITEN", "30"))


def belrooster(items, vandaag):
    """Regel van Mehdi (11-09-2026): voor elke afspraak effectief gebeld worden, een gemiste
    oproep volstaat. Online: BEL_ONLINE_MIN minuten vooraf. Buiten: op het vertrekmoment
    (start van mijn reistijdblok), anders BEL_BUITEN_MIN vooraf. Niet voor intern (IN),
    terugkerend, hele dag, reistijd, Lara, feestdagen."""
    from datetime import timedelta
    reistijden = [x for x in items if lees_titel(x["titel"])["reistijd"] and "T" in x["start"]]
    regels = []
    for a in items:
        if a.get("hele_dag") or a.get("_terugkerend") or a["start"][:10] < vandaag or a.get("kalender", "").startswith("en.be#"):
            continue
        kal = KALENDERS.get(a["kalender"], "")
        info = lees_titel(a["titel"])
        if info["reistijd"] or info["soort"] == "IN" or kal == "Lara":
            continue
        start = datetime.fromisoformat(a["start"])
        adres = a.get("locatie") or ""
        buiten = info["buiten"] or info["soort"] in ("KB", "PB") or (adres and not adres.lower().startswith("http"))
        if buiten:
            blok = [x for x in reistijden if x["kalender"] == a["kalender"] and start - timedelta(hours=3) <= datetime.fromisoformat(x["start"]) < start]
            beltijd = datetime.fromisoformat(blok[-1]["start"]) if blok else start - timedelta(minutes=BEL_BUITEN_MIN)
            hoe = "vertrekken" if blok else f"over {BEL_BUITEN_MIN} minuten vertrekken"
        else:
            beltijd = start - timedelta(minutes=BEL_ONLINE_MIN)
            hoe = f"over {BEL_ONLINE_MIN} minuten online"
        klant = info["klant"] or a["titel"][:60]
        tekst = f"Mehdi, {hoe}: {klant}, om {start.strftime('%H:%M')}." + (" De link staat in je agenda." if not buiten else " Adres staat in je agenda.")
        regels.append({"sleutel": f"{a['kalender']}:{a['id']}:{a['start']}", "tijd": beltijd.isoformat(), "tekst": tekst, "titel": a["titel"][:80]})
    regels.sort(key=lambda r: r["tijd"])
    return regels


def botsingen(items):
    """Twee afspraken die elkaar overlappen op dezelfde dag (bv. een Zoom tijdens een opmeting)."""
    uit = []
    tijd = [(datetime.fromisoformat(x["start"]), datetime.fromisoformat(x["einde"]), x) for x in items
            if "T" in x["start"] and not lees_titel(x["titel"])["reistijd"] and not x.get("kalender", "").startswith("en.be#")]
    tijd.sort(key=lambda t: t[0])
    for i, (s1, e1, a) in enumerate(tijd):
        for s2, e2, b in tijd[i + 1:]:
            if s2 >= e1:
                break
            uit.append(f"{a['start'][:16]} {a['titel'][:45]}  ×  {b['start'][11:16]} {b['titel'][:45]}")
    return uit


def main():
    ag.hartslag("actief", taak="agenda lezen")
    try:
        if not agenda.beschikbaar():
            ag.hartslag("fout", taak="geen agendatoegang", detail="GOOGLE_AGENDA_* ontbreekt in ~/appportal/.env")
            return
        os.environ["CONTRACTEN_KALENDERS"] = ",".join(kalenders())   # agenda.kalenders() leest die
        items = agenda.afspraken(-1, 8)
        fouten = [i for i in items if i.get("fout")]
        items = [i for i in items if not i.get("fout")]
        deals = deals_index()
        vandaag = datetime.now().date().isoformat()
        gisteren = (datetime.now().date() - timedelta(days=1)).isoformat()
        klaar, gekoppeld, niet_conform, dagplan, gisteren_lijst = [], 0, [], [], []
        per_afdeling = {}
        for a in items:
            info = lees_titel(a["titel"])
            if info["reistijd"] or a["kalender"] == "en.be#holiday@group.v.calendar.google.com":
                continue
            kal = KALENDERS.get(a["kalender"], a["kalender"])
            dag = a["start"][:10]
            afdeling = FIRMA_AFDELING.get(info["firma"]) or KALENDER_AFDELING.get(kal) or "mehdi"
            deal, hoe = (None, "")
            if afdeling == "h-architects":
                deal, hoe = koppel(info, a["titel"], deals)
                gekoppeld += 1 if deal else 0
            if not info["conform"] and kal not in ("Lara", "Prive Buiten", "Feestdagen BE") and dag >= vandaag:
                niet_conform.append(f"{dag} {a['start'][11:16]} {a['titel']} ({kal})")
            oms = ", ".join(x for x in (SOORT.get(info["soort"], ""), TYPES.get(info["type"], ""),
                                        "buiten + reistijd" if info["buiten"] else "", "niet bevestigd" if info["onzeker"] else "") if x)
            regel = f"{'hele dag' if a['hele_dag'] else a['start'][11:16]} {a['titel']}" + (f" [{oms}]" if oms else "") + (f" · deal {deal['id']}" if deal else "")
            if dag == vandaag:
                dagplan.append(regel)
            if dag == gisteren and (info["soort"] in ("KB", "PB", "KO", "PO") or deal):
                gisteren_lijst.append(regel)
            if dag >= vandaag and afdeling != "mehdi":
                per_afdeling[afdeling] = per_afdeling.get(afdeling, 0) + 1
                klaar.append({"voor": afdeling, "soort": "afspraak", "sleutel": str(deal["id"]) if deal else (info["nummer"] or ""),
                              "titel": f"{dag} {regel}", "uniek": f"agenda:{a['kalender']}:{a['id']}", "verwijzing": a.get("link", ""),
                              "inhoud": {"datum": dag, "start": a["start"], "einde": a["einde"], "titel": a["titel"], "agenda": kal,
                                         "firma": info["firma"], "soort": info["soort"], "type": info["type"], "nummer": info["nummer"],
                                         "klant": info["klant"], "buiten": info["buiten"], "onzeker": info["onzeker"],
                                         "locatie": a["locatie"], "deelnemers": a["deelnemers"],
                                         "deal_id": deal["id"] if deal else None, "koppeling": hoe, "omschrijving": a["omschrijving"][:800]}})
        tekst = "Vandaag:\n" + ("\n".join("- " + r for r in dagplan) or "- niets in de agenda") + \
                "\n\nGisteren, klantcontact waar een verslag of opname bij hoort:\n" + ("\n".join("- " + r for r in gisteren_lijst) or "- niets")
        klaar.append({"voor": "mehdi", "soort": "dagplan", "sleutel": vandaag, "titel": f"Dagplan {vandaag}", "uniek": f"dagplan:{vandaag}", "inhoud": tekst})
        if niet_conform:
            klaar.append({"voor": "mehdi", "soort": "signaal", "sleutel": vandaag, "titel": f"{len(niet_conform)} afspraken zonder code ([HA-KB] enz.)",
                          "uniek": f"agenda-conventie:{vandaag}", "inhoud": "\n".join("- " + x for x in niet_conform[:40])})
        onvolledig = onvolledige_afspraken(items, vandaag)
        if onvolledig:
            klaar.append({"voor": "mehdi", "soort": "signaal", "sleutel": vandaag, "titel": f"{len(onvolledig)} afspraken zonder projectnummer of adres",
                          "uniek": f"agenda-onvolledig:{vandaag}:{len(onvolledig)}", "inhoud": "\n".join("- " + x for x in onvolledig[:40])})
        uit = ag.klaarzet(klaar)
        dag_grens = DAG_ARG or (vandaag if ALLEEN_VANDAAG else None)
        rg, ral, rgeen, rfout, rregels = reistijd_zetten(items, dag_grens)
        ag.log(f"dag {vandaag}", "schrijf", f"reistijd: {rg} blok(ken) gemaakt, {ral} bestonden al, {rgeen} zonder adres, {rfout} mislukt", "\n".join(rregels))
        rooster = belrooster(items, vandaag)
        bellen.rooster_schrijven(rooster)
        ag.log(f"dag {vandaag}", "schrijf", f"belrooster: {len(rooster)} oproepen gepland (online {BEL_ONLINE_MIN} min vooraf, buiten op het vertrekmoment)",
               "\n".join(f"{r['tijd'][:16]} bel: {r['titel']}" for r in rooster[:60]))
        bots = [b for b in botsingen(items) if b[:10] >= vandaag]
        if bots:
            ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": vandaag, "titel": f"{len(bots)} botsende afspraken in de komende week",
                          "uniek": f"agenda-botsing:{vandaag}:{len(bots)}", "inhoud": "\n".join("- " + b for b in bots)}])
            ag.log(f"dag {vandaag}", "bevinding", f"{len(bots)} botsende afspraken", "\n".join(bots))
        kg, kgoed, kgeen, kfout = kleuren_zetten(items, dag_grens)
        ag.log(f"dag {vandaag}", "schrijf", f"kleuren: {kg} gezet, {kgoed} klopten al, {kgeen} zonder regel (titel zonder code), {kfout} niet gelukt (leesrecht)",
               "\n".join(f"{a['start'][:16]} {a['titel'][:60]} -> {KLEURNAAM.get(kleur_gewenst(a, lees_titel(a['titel'])), 'laten staan')}" for a in items if a['start'][:10] >= vandaag and (not dag_grens or a['start'][:10] == dag_grens)))
        gezet, al, weg, fout_h = herinneringen_zetten(items, dag_grens)
        ag.log(f"dag {vandaag}", "schrijf", f"herinneringen (alleen prospecten HA/UNABO/TKN, PO en PB): {gezet} gezet (online {ONLINE_MIN} min, buiten {BUITEN_MIN} min), {al} hadden er al een, {weg} weggehaald van intern of terugkerend, {fout_h} mislukt",
               "\n".join(f"{'MELDING ' if melding_gewenst(a)[0] else 'stil    '} {a['start'][:16]} {a['titel'][:70]}" for a in items if a['start'][:10] >= vandaag and not a.get('hele_dag')))
        ag.log(f"dag {vandaag}", "bron", f"{len(items)} afspraken uit {len(kalenders())} agenda's; {gekoppeld} H-A-afspraken aan een deal gekoppeld; per afdeling: " +
               ", ".join(f"{k} {v}" for k, v in sorted(per_afdeling.items())) + (f"; {len(fouten)} agenda's niet leesbaar: " + ", ".join(f['kalender'] for f in fouten) if fouten else ""),
               "\n".join(f"{a['start'][:16]} {KALENDERS.get(a['kalender'], a['kalender'])[:14]} | {a['titel']}" for a in items))
        ag.log(f"dag {vandaag}", "bevinding", f"{len(niet_conform)} toekomstige afspraken zonder code", "\n".join(niet_conform[:60]))
        ag.log(f"dag {vandaag}", "schrijf", f"klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend", tekst)
        if ROUTES_KEY:
            _, routes_gebruikt = routes_vandaag()
            ag.log(f"dag {vandaag}", "bron", f"Google Routes: {routes_gebruikt} van {ROUTES_DAGLIMIET} aanroepen vandaag"
                   + (" (plafond bereikt, reistijden verder op de filefactor)" if ROUTES_GESTOPT else ""))
        ag.log_verstuur()
        ag.hartslag("waakt", taak="agenda in het oog", detail=f"vandaag {len(dagplan)} afspraken; {gekoppeld} gekoppeld; {len(niet_conform)} zonder code",
                    nood=([{"tekst": f"{len(niet_conform)} toekomstige afspraken zonder code ([HA-KB] enz.): titels rechtzetten (Mehdi, of via een voorstel zodra het runbook agenda-titel er is)", "wie": "mehdi"}] if niet_conform else [])
                    + ([{"tekst": f"{fout_h} herinneringen konden niet gezet worden", "wie": "claude-code"}] if fout_h else [])
                    + ([{"tekst": f"dagplafond Google Routes bereikt ({ROUTES_DAGLIMIET} aanroepen); reistijden vandaag verder op de filefactor. Klopt dat met het aantal buitenafspraken, dan mag AGENDA_ROUTES_DAGLIMIET omhoog; zo niet, dan vraagt er iets te veel op", "wie": "claude-code"}] if ROUTES_GESTOPT else [])
                    + ([{"tekst": f"{len(fouten)} agenda(s) niet leesbaar: " + ", ".join(f["kalender"][:30] for f in fouten), "wie": "mehdi"}] if fouten else []))
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()

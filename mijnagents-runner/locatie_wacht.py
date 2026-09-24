#!/usr/bin/env python3
"""De Locatiewacht (Privé, alleen voor Mehdi) — zijn bewegingslogboek.

Bron: de tegel locatie.globaal.be (OwnTracks op de iPhone), op de VM zonder login
bereikbaar op 127.0.0.1:3031: GET /api/dag/JJJJ-MM-DD (indeling in bezoeken,
verplaatsingen en gaten, plus de ruwe punten), GET /api/plekken (de plekken die de
tegel kent, zoals Thuis) en GET /gezond (punten, minuten sinds het laatste punt).

Elke avond (21:30) en met --dag JJJJ-MM-DD:
  1. het dagboek van de dag samenstellen en wegschrijven op de VM:
     mijnagents-data/locatielogboek/dagen/<dag>.md. Elke plek krijgt een naam: een
     plek die de tegel kent, anders een bouwplaats (binnen 300 m van een
     projectcoördinaat, met het projectnummer), anders het adres (Nominatim, gecachet).
     Een gat in de meting is meestal een stilstand: de telefoon zwijgt zodra hij
     stilligt. Die stilstand krijgt de plek waar de telefoon stil viel.
     De Dropbox-map "private/0 Chegini Mehdi/Prive met Claude" is met het token
     van de stack (Siyans account) niet bereikbaar, dus de Dropbox-kopie maakt
     het Mac-script locatie/locatie-ophalen.py, zoals nu.
  2. het dagboek naast de agenda leggen: welke afspraak is volgens de locatie
     doorgegaan (plek van de afspraak binnen 300 m van een bezoek of stilstand dat
     in tijd overlapt), welke niet gezien. De plek van een afspraak komt eerst uit
     het projectregister (projectnummer in de titel: werkwijze/projecten.json, dan
     het adres uit de projectmapnaam volgens A13 in projectadressen.json), pas
     daarna uit het adres in de agenda.
  3. verblijven op een bouwplaats zonder afspraak melden als mogelijk
     niet-geregistreerd werfbezoek, en elders verblijven van twintig minuten of
     meer die geen vaste plek zijn.
  4. alles klaarzetten voor Mehdi (nooit voor een afdeling), werkverslag op het bord.
Elke twee uur (--controle): alarm als er meer dan zes uur geen punt binnenkwam
terwijl het geen nacht is (07:00-22:00): dan is de tracker stuk.
Met --droog: het dagboek samenstellen en tonen, zonder weg te schrijven of het bord te raken.
Leest alleen. Verwijdert niets uit het logboek.
"""
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from zoneinfo import ZoneInfo

# De server draait in UTC. Tot 14-09-2026 stonden alle tijden in het dagboek
# daardoor twee uur te vroeg ("22:00-08:15 in Etterbeek" voor 00:00-10:15), en
# leek een werfbezoek van 11:14 om 09:14 te vallen, naast een afspraak om 10:00.
# Afspraak van Mehdi: Belgische tijd overal, ook als hij reist.
BRUSSEL = ZoneInfo("Europe/Brussels")


def nu():
    return datetime.now(BRUSSEL)

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import agenda  # noqa: E402
import agenda_wacht as W  # noqa: E402  titelregels, agenda's en adres naar coördinaten, zoals De Agendawacht
import bord  # noqa: E402
import dropbox_prive  # noqa: E402
import projectadressen  # noqa: E402

NAAM = "locatie-wacht"
ag = bord.Agent(NAAM)
LOCATIE = os.environ.get("LOCATIE_URL", "http://127.0.0.1:3031")
MAP = os.path.expanduser("~/appportal/mijnagents-data/locatielogboek")
CACHE = os.path.join(MAP, "adressen.json")
PROJECTEN = os.path.join(HIER, "werkwijze", "projecten.json")
MIN_BEZOEK = 20
# Binnen deze afstand van een projectcoördinaat is een verblijf een bouwplaats; dezelfde
# 300 m als voor de foto's bij een werfbezoek.
BOUWPLAATS_M = 300
# Een gat is een stilstand zolang het eerste punt erna dichtbij ligt: de telefoon zwijgt
# als hij stilligt en meldt zich pas na een paar honderd meter (gemeten 21 en 22-09-2026:
# 0,4 tot 1,2 km). Ligt het volgende punt verder, dan gebeurde er in de stilte meer.
STILSTAND_METER = 2000
REGISTER_OUD_DAGEN = 14
ALARM_UREN = 6
NACHT = (22, 7)
CONTROLE = "--controle" in sys.argv
DAG = None
for i, a in enumerate(sys.argv):
    if a == "--dag" and i + 1 < len(sys.argv):
        DAG = sys.argv[i + 1]
DAG = DAG or nu().date().isoformat()
UA = {"User-Agent": "MehdiAgents-locatiewacht/1.0 (mch@h-architects.be)"}


# ---------------------------------------------------------------- helpers ---
def haal(pad):
    with urllib.request.urlopen(f"{LOCATIE}{pad}", timeout=30) as r:
        return json.load(r)


def laad_cache():
    try:
        return json.load(open(CACHE))
    except (OSError, ValueError):
        return {}


def bewaar_cache(c):
    os.makedirs(MAP, exist_ok=True)
    json.dump(c, open(CACHE, "w"), ensure_ascii=False, indent=0)


_laatste_nominatim = [0.0]


def _nominatim(pad, params):
    wacht = 1.1 - (time.time() - _laatste_nominatim[0])
    if wacht > 0:
        time.sleep(wacht)
    _laatste_nominatim[0] = time.time()
    url = f"https://nominatim.openstreetmap.org/{pad}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return json.load(r)


def adres_van(lat, lon, cache):
    sleutel = f"{lat:.4f},{lon:.4f}"
    if sleutel in cache:
        cache[sleutel]["n"] = cache[sleutel].get("n", 0) + 1
        return cache[sleutel]["adres"]
    try:
        d = _nominatim("reverse", {"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 18, "accept-language": "nl"})
        a = d.get("address", {})
        straat = " ".join(x for x in (a.get("road", ""), a.get("house_number", "")) if x)
        plaats = a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or ""
        adres = ", ".join(x for x in (straat, f"{a.get('postcode', '')} {plaats}".strip()) if x) or d.get("display_name", "")[:80]
    except Exception as e:  # noqa: BLE001
        adres = f"(adres onbekend: {type(e).__name__})"
    cache[sleutel] = {"adres": adres, "n": 1}
    return adres


def afstand_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def uur(epoch):
    return datetime.fromtimestamp(int(epoch), BRUSSEL).strftime("%H:%M")


def duur(m):
    m = int(m or 0)
    return f"{m // 60}u{m % 60:02d}" if m >= 60 else f"{m} min"


def km(meter):
    return int((meter or 0) / 100) / 10


def epoch_van_iso(iso):
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())
    except Exception:  # noqa: BLE001
        return None


def kort(adres):
    return re.sub(r",\s*(Belgi[eë]|Belgium)\s*$", "", (adres or "").strip())


def online(tekst):
    return bool(re.match(r"\s*https?://", tekst or "")
                or re.search(r"zoom\.us|meet\.google|teams\.microsoft|webex", tekst or "", re.I))


# ---------------------------------------------------------- projecten ---
def projectregister():
    """Projectnummer naar adres en coördinaten, uit de twee bronnen die er al zijn:
    werkwijze/projecten.json (projectregister.py, met coördinaten) en de projectmappen
    volgens A13 (projectadressen.json, adres uit de mapnaam, nog zonder coördinaten).
    Geeft (register, gelezen teksten voor de kennis, datum van het register)."""
    reg, gelezen, datum = {}, {}, ""
    try:
        tekst = open(PROJECTEN, encoding="utf-8").read()
        gelezen["projecten.json"] = tekst
        d = json.loads(tekst)
        datum = d.get("datum", "")
        for p in d.get("projecten", []):
            if p.get("nummer"):
                c = p.get("coordinaten")
                reg[str(p["nummer"])] = {"adres": kort(p.get("adres")), "coord": tuple(c) if c else None,
                                         "bron": "projectregister", "afspraken": p.get("aantal_afspraken", 0),
                                         "map": False}
    except (OSError, ValueError):
        pass
    mappen = projectadressen.index()
    gelezen["projectadressen.json"] = json.dumps(mappen, ensure_ascii=False, sort_keys=True)
    for nr, p in mappen.items():
        r = reg.setdefault(nr, {"adres": "", "coord": None, "bron": "projectmap (A13)", "afspraken": 0})
        r["map"] = True
        r["adres"] = r["adres"] or kort(p.get("adres"))
    return reg, gelezen, datum


def plek_van_afspraak(a, info, reg, wcache):
    """Waar een afspraak plaatsvindt: (lat, lon, herkomst) of (None, None, reden).

    Eerst het projectnummer in de titel: de coördinaten uit het projectregister, dan het
    adres uit de projectmap (A13). Pas daarna het adres in de agenda. Gezien 21-09-2026:
    'WB 2145' met Vertommensberg 9, 3010 Kessel-Lo gaf 'adres niet gevonden', omdat
    Nominatim de deelgemeente niet kent en deze wacht die mislukking voor altijd
    bewaarde, terwijl het projectregister de coördinaten al had. Het omzetten van een
    adres gebeurt nu door W.coord, die meerdere schrijfwijzen probeert en een
    mislukking niet onthoudt."""
    loc = (a.get("locatie") or "").strip()
    nr = info.get("nummer") or ""
    # Een postcode is geen projectnummer: "Kerkstraat 1, 3010 Leuven" in titel of adres.
    if nr and (re.search(rf",\s*{nr}\s+[A-Za-zÀ-ÿ]", a.get("titel", "")) or re.search(rf"\b{nr}\s+[A-Za-zÀ-ÿ]", loc)):
        nr = ""
    p = reg.get(nr) if nr else None
    if p and p.get("coord"):
        bron = "het projectregister" if p.get("bron") == "projectregister" else "de projectmap (A13)"
        return p["coord"][0], p["coord"][1], f"{bron}, project {nr}"
    if p and p.get("adres"):
        c = W.coord(p["adres"], wcache)
        if c:
            p["coord"] = (c[0], c[1])
            return c[0], c[1], f"de projectmap (A13), project {nr}"
    if loc and not online(loc):
        c = W.coord(loc, wcache)
        if c:
            return c[0], c[1], "het adres in de agenda"
        return None, None, f"adres niet gevonden: {loc[:50]}"
    return None, None, "geen adres en geen bekend projectnummer"


def bouwplaats(lat, lon, reg):
    """Het project binnen BOUWPLAATS_M van dit punt, of "". Liggen er meer op dezelfde
    plek (2603 en 5603 op Provinciebaan 20), dan eerst het nummer met een projectmap
    (A13), dan vier cijfers, dan het nummer met de meeste afspraken."""
    dicht = [(afstand_m(lat, lon, *p["coord"]), nr, p) for nr, p in reg.items() if p.get("coord")]
    dicht = [k for k in dicht if k[0] <= BOUWPLAATS_M]
    if not dicht:
        return ""
    grens = min(k[0] for k in dicht) + 25
    return max((k for k in dicht if k[0] <= grens),
               key=lambda k: (bool(k[2].get("map")), len(k[1]) == 4, k[2].get("afspraken", 0)))[1]


def benoem(lat, lon, plekken, reg, cache):
    """De naam van een plek: een plek die de tegel kent (Thuis, of een werf met dossier),
    dan een bouwplaats uit het projectregister, anders het adres.
    Een bouwplaats is nooit een vaste plek: een wekelijkse werf zou anders na vijf
    bezoeken uit de lijst van niet-geregistreerde werfbezoeken verdwijnen."""
    for p in plekken:
        if p.get("lat") is not None and afstand_m(lat, lon, p["lat"], p["lon"]) <= (p.get("straal") or 150):
            nr = str(p.get("dossier") or "")
            if nr:
                return {"waar": f"bouwplaats {nr}, {(reg.get(nr) or {}).get('adres') or p['naam']}",
                        "bouwplaats": nr, "vaste_plek": False}
            return {"waar": p["naam"], "bouwplaats": "", "vaste_plek": True}
    nr = bouwplaats(lat, lon, reg)
    if nr:
        adres = reg[nr].get("adres")
        return {"waar": f"bouwplaats {nr}" + (f", {adres}" if adres else ""), "bouwplaats": nr, "vaste_plek": False}
    adres = adres_van(lat, lon, cache)
    return {"waar": adres, "bouwplaats": "", "vaste_plek": cache.get(f"{lat:.4f},{lon:.4f}", {}).get("n", 0) >= 5}


# ------------------------------------------------------------------ werk ---
def dagboek(dag, gegevens, plekken, reg, cache):
    """Het dagboek als tekst, en de verblijven (bezoeken en stilstanden, elk met lat, lon,
    waar en bouwplaats) voor de vergelijking met de agenda."""
    indeling = gegevens.get("indeling") or []
    # Het punt waar de telefoon stil viel, voor een gat: de tegel geeft alleen de tijd.
    op = {}
    for p in sorted(gegevens.get("punten") or [], key=lambda p: (p.get("acc") or 0) > 250):
        e = epoch_van_iso(p.get("tijd") or "")
        if e is not None and p.get("lat") is not None:
            op.setdefault(e, (p["lat"], p["lon"]))
    verblijven = []
    r = [f"# Locatielogboek {dag}", ""]
    if not indeling:
        r.append("Geen gegevens. De telefoon heeft die dag niets doorgestuurd.")
        return "\n".join(r), verblijven
    r += ["| van | tot | duur | wat | waar |", "|---|---|---|---|---|"]
    for s in indeling:
        tijd = f"| {uur(s['van'])} | {uur(s['tot'])} | {duur(s['minuten'])} |"
        if s.get("soort") == "bezoek":
            s.update(benoem(s["lat"], s["lon"], plekken, reg, cache))
            verblijven.append(s)
            # Een stop is een bezoek dat de tegel uit een stilte in een rit haalt (15-09-2026).
            wat = "stop" if s.get("stop") else "bezoek"
            r.append(f"{tijd} {wat}{' (vaste plek)' if s['vaste_plek'] else ''} | {s['waar']} |")
        elif s.get("soort") == "gat":
            # Een gat is geen rit. Tot 13-09-2026 schreef deze wacht alles wat geen
            # bezoek was als "verplaatsing", zodat vijf uur zonder meting in het
            # dagboek stond als een rit van 30,1 km die nooit gemeten is.
            # En een gat is meestal een stilstand. Tot 24-09-2026 stond het hier zonder
            # plek: 22-09 15:48-16:56 op de werf van 2145 (foto's 15:59, Plaud 15:46) las
            # als "geen meting, 1,1 km hemelsbreed".
            punt = op.get(int(s["van"]))
            plek = benoem(punt[0], punt[1], plekken, reg, cache) if punt else None
            gezien = f"laatst gezien: {plek['waar']}" if plek else ""
            if s.get("open"):
                r.append(f"{tijd} geen meting | sindsdien niets meer binnen{'; ' + gezien if gezien else ''} |")
            elif plek and (s.get("meter") or 0) <= STILSTAND_METER:
                s.update(plek, lat=punt[0], lon=punt[1], stilstand=True)
                verblijven.append(s)
                r.append(f"{tijd} stilstand, geen meting{' (vaste plek)' if s['vaste_plek'] else ''} | "
                         f"{s['waar']}; volgend punt {km(s.get('meter'))} km verder |")
            else:
                r.append(f"{tijd} geen meting | {km(s.get('meter'))} km hemelsbreed{'; ' + gezien if gezien else ''} |")
        else:
            r.append(f"{tijd} verplaatsing {s.get('wijze') or ''} | {km(s.get('meter'))} km |")
    return "\n".join(r), verblijven


def vergelijk_agenda(dag, verblijven, reg, wcache):
    """(doorgegaan, niet_gezien, zonder_adres, niet_te_toetsen). Te toetsen is een afspraak
    buiten (!!, een buitensoort of een buitendienst in de titel) of met een fysiek adres.
    Online, intern en reistijd tellen alleen mee in het aantal."""
    alle = W.afspraken_dag(dag) if agenda.beschikbaar() else []
    doorgegaan, niet_gezien, zonder_adres, overig = [], [], [], 0
    for a in alle:
        if a.get("fout") or a.get("hele_dag") or "T" not in a.get("start", ""):
            continue
        info = W.lees_titel(a.get("titel", ""))
        loc = (a.get("locatie") or "").strip()
        buiten = info["buiten"] or info["soort"] in W.BUITEN_SOORTEN
        if info["reistijd"] or not (buiten or (loc and not online(loc))):
            overig += 1
            continue
        lat, lon, herkomst = plek_van_afspraak(a, info, reg, wcache)
        if lat is None:
            zonder_adres.append(f"{a['start'][11:16]} {a['titel']} ({herkomst})")
            continue
        van, tot = epoch_van_iso(a["start"]), epoch_van_iso(a["einde"])
        # Alle verblijven op de plek die in tijd aansluiten: een bezoek en de stilstand
        # erna zijn één oplevering (15-09-2026, Kortenberg 16:59-17:55 en 17:55-18:31).
        treffers = [v for v in verblijven if afstand_m(lat, lon, v["lat"], v["lon"]) <= 300
                    and v["van"] <= (tot or 0) + 1800 and v["tot"] >= (van or 0) - 1800]
        if treffers:
            doorgegaan.append(f"{a['start'][11:16]} {a['titel']} · ter plaatse "
                              f"{uur(min(v['van'] for v in treffers))}-{uur(max(v['tot'] for v in treffers))}"
                              f", {treffers[0]['waar']} (plek uit {herkomst})")
            for v in treffers:
                v["afspraak"] = a["titel"]
        else:
            niet_gezien.append(f"{a['start'][11:16]} {a['titel']} · plek uit {herkomst}")
    return doorgegaan, niet_gezien, zonder_adres, overig


def controle():
    g = haal("/gezond")
    minuten = int(g.get("minuten_geleden") or 0)
    nu_uur = nu().hour
    nacht = nu_uur >= NACHT[0] or nu_uur < NACHT[1]
    if minuten > ALARM_UREN * 60 and not nacht:
        # Geen "stil" in de titel en geen teller: De Bode belt bij "stil" (AGENTNORM v1.3),
        # en met het uur in de sleutel kwam dit tot 24-09-2026 elke twee uur opnieuw.
        ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": nu().date().isoformat(),
                      "titel": "Locatietracker geeft geen punten door",
                      "uniek": f"locatie-tracker-zwijgt:{nu().date().isoformat()}",
                      "inhoud": f"Al {minuten // 60} uur geen locatiepunt terwijl het geen nacht is. "
                                "Kijk de OwnTracks-app op de iPhone na."}])
        ag.log(nu().date().isoformat(), "fout", f"tracker zwijgt sinds {minuten} min")
        ag.log_verstuur()
        ag.hartslag("fout", taak="tracker zwijgt", detail=f"geen punt sinds {minuten // 60} uur")
    else:
        ag.hartslag("waakt", taak="tracker in het oog", detail=f"laatste punt {minuten} min geleden, {g.get('punten', '?')} punten vandaag")


def maak(dag):
    """Het dagboek van een dag met de vergelijking, zonder iets weg te schrijven.
    Geeft een dict met de tekst, de lijsten en wat er gelezen is."""
    cache, wcache = laad_cache(), W._cache_laden()
    wcache_voor = dict(wcache)
    reg, gelezen, datum = projectregister()
    gegevens = haal(f"/api/dag/{dag}")
    tekst, verblijven = dagboek(dag, gegevens, W.plekken(), reg, cache)
    doorgegaan, niet_gezien, zonder_adres, overig = vergelijk_agenda(dag, verblijven, reg, wcache)
    zonder = [v for v in verblijven if not v.get("afspraak")]
    werf = [v for v in zonder if v.get("bouwplaats")]
    elders = [v for v in zonder if not v.get("bouwplaats") and not v.get("vaste_plek")
              and int(v.get("minuten", 0)) >= MIN_BEZOEK]

    def lijn(v):
        return f"- {uur(v['van'])}-{uur(v['tot'])} ({duur(v['minuten'])}) {v['waar']}" \
               + (" (stilstand, geen meting)" if v.get("stilstand") else "")

    regels = [tekst, "", "## Naast de agenda", ""]
    regels += ["Doorgegaan volgens de locatie:"] + ([f"- {x}" for x in doorgegaan] or ["- (geen)"])
    regels += ["", "Niet gezien op de plek van de afspraak:"] + ([f"- {x}" for x in niet_gezien] or ["- (geen)"])
    if zonder_adres:
        regels += ["", "Buitenafspraken zonder bruikbaar adres:"] + [f"- {x}" for x in zonder_adres]
    regels += ["", f"Niet te toetsen (online, intern of reistijd): {overig} afspraken."]
    regels += ["", "Op een bouwplaats zonder afspraak (mogelijk niet-geregistreerd werfbezoek):"]
    regels += [lijn(v) for v in werf] or ["- (geen)"]
    regels += ["", "Elders 20 minuten of meer zonder afspraak, geen vaste plek:"]
    regels += [lijn(v) for v in elders] or ["- (geen)"]
    return {"volledig": "\n".join(regels) + "\n", "gelezen": gelezen, "datum": datum, "reg": reg,
            "segmenten": len(gegevens.get("indeling") or []), "verblijven": verblijven,
            "doorgegaan": doorgegaan, "niet_gezien": niet_gezien, "zonder_adres": zonder_adres,
            "overig": overig, "werf": werf, "elders": elders, "cache": cache,
            "wcache": wcache if wcache != wcache_voor else None,
            "bouwplaatsen": sorted({v["bouwplaats"] for v in verblijven if v.get("bouwplaats")})}


def main():
    if CONTROLE:
        controle()
        return
    if "--droog" in sys.argv:
        # Samenstellen en tonen: geen dagboek, geen bord, geen cache (de teller van de
        # vaste plekken zou anders bij elke proef oplopen).
        print(maak(DAG)["volledig"])
        return
    with ag.ronde(f"dagboek {DAG}") as r:
        d = maak(DAG)
        for naam, tekst in d["gelezen"].items():
            r.bron(naam, tekst)
        bewaar_cache(d["cache"])
        if d["wcache"] is not None:       # de Agendawacht schrijft in hetzelfde bestand
            W._cache_bewaren(d["wcache"])
        os.makedirs(os.path.join(MAP, "dagen"), exist_ok=True)
        pad = os.path.join(MAP, "dagen", f"{DAG}.md")
        open(pad, "w", encoding="utf-8").write(d["volledig"])
        uit = ag.klaarzet([{"voor": "mehdi", "soort": "locatie", "sleutel": DAG, "titel": f"Locatielogboek {DAG}",
                            "uniek": f"locatie:{DAG}", "verwijzing": pad, "inhoud": d["volledig"][:20000]}])
        plaatsen = ", ".join(d["bouwplaatsen"]) or "geen"
        ag.log(f"dag {DAG}", "bron", f"{d['segmenten']} segmenten, {len(d['verblijven'])} verblijven (bezoeken en "
               f"stilstanden); projectregister {d['datum'] or 'onbekend'} met {len(d['reg'])} projecten; agenda: "
               f"{len(d['doorgegaan'])} doorgegaan, {len(d['niet_gezien'])} niet gezien, "
               f"{len(d['zonder_adres'])} buiten zonder adres, {d['overig']} niet te toetsen")
        ag.log(f"dag {DAG}", "bevinding", f"bouwplaatsen: {plaatsen}; {len(d['werf'])} verblijf(ven) op een "
               f"bouwplaats zonder afspraak, {len(d['elders'])} elders", d["volledig"])
        ag.log(f"dag {DAG}", "schrijf", f"dagboek geschreven: {pad}; klaargezet voor Mehdi ({uit.get('nieuw', 0)} nieuw)")
        sp = dropbox_prive.spiegel_map(MAP, "/Locatie")
        if sp["verstuurd"] or sp["fout"]:
            ag.log(f"dag {DAG}", "schrijf", f"Dropbox privé: {sp['verstuurd']} bestand(en) verstuurd" + (f"; fout: {sp['fout']}" if sp["fout"] else ""))
        for n in dropbox_prive.nood(wat="het locatielogboek"):
            r.nood(n["tekst"], wie=n["wie"])
        if d["zonder_adres"]:
            r.nood("Buitenafspraken zonder adres of bekend projectnummer: de vergelijking met de locatie is daar blind",
                   wie="collega")
        try:
            oud = (nu().date() - date.fromisoformat(d["datum"])).days > REGISTER_OUD_DAGEN
        except ValueError:
            oud = True
        if oud:
            r.nood("Het projectregister (werkwijze/projecten.json) is ouder dan twee weken: nieuwe projecten "
                   "krijgen geen coördinaten. Draai projectregister.py", wie="claude-code")
        r.detail = (f"{len(d['verblijven'])} verblijven, bouwplaatsen: {plaatsen}, "
                    f"{len(d['werf']) + len(d['elders'])} zonder afspraak, {len(d['zonder_adres'])} buitenafspraken zonder adres")
    try:
        controle()
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""De Locatiewacht (Privé, alleen voor Mehdi) — zijn bewegingslogboek. Werkwijze v3 (04-10-2026).

Sinds 3 oktober 2026 meet alleen de tracker in de auto. De telefoon is bewust
gestopt; later komt er een draagbare tracker bij. Welke metingen meetellen staat in
locatie/bronbeleid.py (startgrens op de meettijd, het vastgelegde toestel); deze
wacht leest dezelfde module en vraagt nooit een dag voor de grens op.

Bron: de tegel locatie.globaal.be, op de VM zonder login op 127.0.0.1:3031:
  GET /api/dagboek/<dag>?adressen=1  het dagboek: één generator voor VM, bord en export,
                                     met de projectherkenning (firma + nummer, zekerheid)
  GET /api/status                     per tracker de stand, de taken en de projectdekking
  GET /api/context?dag=<dag>          locatiecontext voor agents, alleen wat bij een project hoort
  GET /api/projectplekken             projectplekken (firma:nummer naar coördinaat), voor de agenda

Elke avond om 21:30 Belgische tijd (cron met --om 21:30, de klokgrendel) of met --dag:
  1. elke dag vanaf de laatst afgesloten dag tot vandaag (nooit voor de startgrens): het
     dagboek ophalen, de agenda erbij leggen, wegschrijven in
     mijnagents-data/locatielogboek/dagen/<dag>.md. Verandert een dagboek (late punten, een
     correctie), dan gaat de vorige versie naar dagen/revisies/. Vandaag is voorlopig.
  2. de locatiecontext per dag wegschrijven in mijnagents-data/locatielogboek/context/<dag>.json,
     met de afspraak erbij, voor de agents die een werfbezoek voorbereiden.
  3. klaarzetten voor Mehdi (nooit voor een afdeling), werkverslag op het bord.
Elk uur van 07 tot 22 (--controle): de bronstatus. Alarm alleen als de tracker wegvalt
zonder 'motor uit'; geparkeerd staan is geen storing; de telefoon en de draagbare tracker
geven nooit alarm.
Met --droog: het dagboek samenstellen en tonen, zonder weg te schrijven of het bord te raken.
Leest alleen. Verwijdert niets uit het logboek.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# De server draait in UTC. Tot 14-09-2026 stonden alle tijden in het dagboek
# daardoor twee uur te vroeg. Afspraak van Mehdi: Belgische tijd overal.
BRUSSEL = ZoneInfo("Europe/Brussels")


def nu():
    return datetime.now(BRUSSEL)


HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
sys.path.insert(0, os.path.join(HIER, "..", "locatie"))
import agenda  # noqa: E402
import agenda_wacht as W  # noqa: E402  titelregels, agenda's en adres naar coördinaten, zoals De Agendawacht
import bord  # noqa: E402
import bronbeleid as BB  # noqa: E402  dezelfde startgrens en hetzelfde toestel als de tegel
import status as LS  # noqa: E402  dezelfde ouderdomsregel voor taken als de tegel (tweede slot in controle)
import dropbox_prive  # noqa: E402

NAAM = "locatie-wacht"
ag = bord.Agent(NAAM)
LOCATIE = os.environ.get("LOCATIE_URL", "http://127.0.0.1:3031")
MAP = os.path.expanduser("~/appportal/mijnagents-data/locatielogboek")
STAND = os.path.join(MAP, "stand.json")
MIN_BEZOEK = 20
# Binnen deze afstand van de plek van een afspraak telt een verblijf als ter plaatse.
AFSPRAAK_M = 300
INHAAL_MAX_DAGEN = 14
CONTROLE = "--controle" in sys.argv
DROOG = "--droog" in sys.argv


def _arg(naam):
    for i, a in enumerate(sys.argv):
        if a == naam and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


DAG = _arg("--dag")
OM = _arg("--om")


# ---------------------------------------------------------------- helpers ---
def haal(pad):
    with urllib.request.urlopen(f"{LOCATIE}{pad}", timeout=120) as r:
        return json.load(r)


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


def taak_melden(taak, gelukt, detail=""):
    """De taakstatus in de tegel, zodat het scherm per taak toont wanneer hij laatst lukte."""
    try:
        subprocess.run(["docker", "exec", "app-locatie", "python3", "beheer.py", "taak", taak,
                        "ok" if gelukt else "fout", detail[:400]], capture_output=True, timeout=60)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------- projecten ---
def projectindex():
    """De projectplekken van de tegel: {'FIRMA:nummer': plek} en {nummer: [sleutels]}.

    Dezelfde bron als de herkenning (H-A Projecten en de projectmappen); geen eigen
    register meer. Tot 04-10-2026 las deze wacht werkwijze/projecten.json, een lijst die
    alleen uit de agenda groeide en sinds 20-09 niet meer vernieuwd was."""
    d = haal("/api/projectplekken")
    per_sleutel, per_nummer = {}, {}
    for p in d.get("projectplekken") or []:
        if not p.get("actief"):
            continue
        bruikbaar = p.get("geocode_kwaliteit") in ("adres", "override") and p.get("lat") is not None \
            and not p.get("uitgesloten")
        per_sleutel[p["sleutel"]] = {"adres": kort(p.get("adres")), "coord": (p["lat"], p["lon"]) if bruikbaar else None,
                                     "bron": p.get("bron"), "link": p.get("link"), "firma": p.get("firma"),
                                     "nummer": p.get("nummer")}
        per_nummer.setdefault(str(p.get("nummer")), []).append(p["sleutel"])
    return per_sleutel, per_nummer, d.get("dekking") or {}


def plek_van_afspraak(a, info, index, wcache):
    """Waar een afspraak plaatsvindt: (lat, lon, herkomst) of (None, None, reden).

    Eerst firma plus projectnummer uit de titel in de projectplekken; staat er geen firma
    in de titel, dan alleen als het nummer bij precies één firma hoort (nooit gokken). Dan
    het adres uit de projectbron via W.coord, pas daarna het adres in de agenda. Een
    postcode is geen projectnummer."""
    per_sleutel, per_nummer = index
    loc = (a.get("locatie") or "").strip()
    nr = info.get("nummer") or ""
    if nr and (re.search(rf",\s*{nr}\s+[A-Za-zÀ-ÿ]", a.get("titel", "")) or re.search(rf"\b{nr}\s+[A-Za-zÀ-ÿ]", loc)):
        nr = ""
    p, reden = None, ""
    if nr:
        firma = info.get("firma") or ""
        if firma and f"{firma}:{nr}" in per_sleutel:
            p = per_sleutel[f"{firma}:{nr}"]
        elif not firma and len(per_nummer.get(nr, [])) == 1:
            p = per_sleutel[per_nummer[nr][0]]
        elif not firma and len(per_nummer.get(nr, [])) > 1:
            reden = f"nummer {nr} bestaat bij meer firma's en de titel noemt er geen"
    if p and p.get("coord"):
        return p["coord"][0], p["coord"][1], f"de projectplek {p['firma']} {p['nummer']} ({p['bron']})"
    if p and p.get("adres"):
        c = W.coord(p["adres"], wcache)
        if c:
            return c[0], c[1], f"het adres van {p['firma']} {p['nummer']} ({p['bron']})"
    if loc and not online(loc):
        c = W.coord(loc, wcache)
        if c:
            return c[0], c[1], "het adres in de agenda"
        return None, None, f"adres niet gevonden: {loc[:50]}"
    return None, None, reden or "geen adres en geen bekend projectnummer"


# ------------------------------------------------------------------ werk ---
def verblijven_van(dagboek):
    """De verblijven (bezoeken en parkeren) van alle sporen, met waar en project."""
    uit = []
    for bron, spoor in (dagboek.get("sporen") or {}).items():
        for s in spoor.get("indeling") or []:
            if s.get("soort") != "bezoek":
                continue
            h = s.get("herkenning") or {}
            p = h.get("project")
            if h.get("zekerheid") == "onzeker":
                waar = "een van: " + ", ".join("%s %s" % (k.get("firma") or "?", k["nummer"])
                                               for k in h.get("kandidaten", []))
            elif p:
                waar = "project %s %s%s" % (p.get("firma") or "", p.get("nummer"), (", " + p["adres"]) if p.get("adres") else "")
            else:
                waar = h.get("plek") or s.get("plek") or s.get("adres") or "%.5f, %.5f" % (s["lat"], s["lon"])
            uit.append(dict(s, bron=bron, rol=spoor.get("rol"), waar=waar, project=p,
                            zekerheid=h.get("zekerheid"), kandidaten=h.get("kandidaten") or [],
                            vaste_plek=bool(s.get("vaste_plek") or h.get("plek"))))
    return uit


def vergelijk_agenda(dag, verblijven, index, wcache):
    """(doorgegaan, niet_gezien, zonder_adres, niet_te_toetsen). Te toetsen is een afspraak
    buiten (!!, een buitensoort of een buitendienst in de titel) of met een fysiek adres.
    Online, intern en reistijd tellen alleen mee in het aantal. De auto ter plaatse is een
    aanwijzing dat de afspraak doorging, geen bewijs dat Mehdi er was."""
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
        lat, lon, herkomst = plek_van_afspraak(a, info, index, wcache)
        if lat is None:
            zonder_adres.append(f"{a['start'][11:16]} {a['titel']} ({herkomst})")
            continue
        van, tot = epoch_van_iso(a["start"]), epoch_van_iso(a["einde"])
        # Alle verblijven op de plek die in tijd aansluiten: aankomen en parkeren horen bij één afspraak.
        treffers = [v for v in verblijven if afstand_m(lat, lon, v["lat"], v["lon"]) <= AFSPRAAK_M
                    and v["van"] <= (tot or 0) + 1800 and v["tot"] >= (van or 0) - 1800]
        if treffers:
            wie = "auto" if all(v.get("rol") == "auto" for v in treffers) else "tracker"
            doorgegaan.append(f"{a['start'][11:16]} {a['titel']} · {wie} ter plaatse "
                              f"{uur(min(v['van'] for v in treffers))}-{uur(max(v['tot'] for v in treffers))}"
                              f", {treffers[0]['waar']} (plek uit {herkomst})")
            for v in treffers:
                v["afspraak"] = a["titel"]
        else:
            niet_gezien.append(f"{a['start'][11:16]} {a['titel']} · plek uit {herkomst}")
    return doorgegaan, niet_gezien, zonder_adres, overig


def lijn(v):
    zeker = f" [{v['zekerheid']}]" if v.get("zekerheid") not in (None, "geen") else ""
    link = f" {v['project']['link']}" if v.get("project") and v["project"].get("link") else ""
    return f"- {uur(v['van'])}-{uur(v['tot'])} ({duur(v['minuten'])}) {v['waar']}{zeker}{link}"


def maak(dag):
    """Het dagboek van een dag met de vergelijking, zonder iets weg te schrijven."""
    if not BB.dag_toegestaan(dag):
        raise ValueError(f"{dag} valt voor de start van de meetreeks ({BB.eerste_dag()}); niets op te vragen")
    wcache = W._cache_laden()
    wcache_voor = dict(wcache)
    per_sleutel, per_nummer, dekking = projectindex()
    db = haal(f"/api/dagboek/{dag}")          # leest alleen; verrijken is een aparte stap (verrijk())
    verblijven = verblijven_van(db)
    doorgegaan, niet_gezien, zonder_adres, overig = vergelijk_agenda(dag, verblijven, (per_sleutel, per_nummer), wcache)
    zonder = [v for v in verblijven if not v.get("afspraak") and v.get("zekerheid") != "niet_mehdi"]
    werf = [v for v in zonder if v.get("project") and v.get("zekerheid") in ("waarschijnlijk", "bevestigd")]
    twijfel = [v for v in zonder if v.get("zekerheid") == "onzeker"]
    elders = [v for v in zonder if not v.get("project") and v.get("zekerheid") != "onzeker"
              and not v.get("vaste_plek") and int(v.get("minuten", 0)) >= MIN_BEZOEK]

    regels = [db["markdown"].rstrip(), "", "## Naast de agenda", ""]
    versie = db.get("versie") or ""
    regels += ["Doorgegaan volgens de locatie:"] + ([f"- {x}" for x in doorgegaan] or ["- (geen)"])
    regels += ["", "Niet gezien op de plek van de afspraak:"] + ([f"- {x}" for x in niet_gezien] or ["- (geen)"])
    if zonder_adres:
        regels += ["", "Buitenafspraken zonder bruikbaar adres:"] + [f"- {x}" for x in zonder_adres]
    regels += ["", f"Niet te toetsen (online, intern of reistijd): {overig} afspraken."]
    regels += ["", "Auto bij een project zonder afspraak (mogelijk niet-geregistreerd werfbezoek):"]
    regels += [lijn(v) for v in werf] or ["- (geen)"]
    if twijfel:
        regels += ["", "Bij meerdere projecten tegelijk, niet te onderscheiden (Mehdi kiest op het dashboard):"]
        regels += [lijn(v) for v in twijfel]
    regels += ["", "Elders 20 minuten of meer zonder afspraak, geen vaste plek:"]
    regels += [lijn(v) for v in elders] or ["- (geen)"]
    # De versie van het dagboek waarop dit agendadeel rust: de export neemt het alleen over bij
    # dezelfde versie (controle 05-10-2026: dagboek en agendadeel konden uit elkaar lopen).
    regels += ["", "<!-- dagboekversie %s -->" % versie]

    ctx = haal(f"/api/context?dag={dag}")
    for c in ctx.get("verblijven") or []:
        a = epoch_van_iso(c["aankomst"])
        hit = next((v for v in verblijven if v["van"] == a and v.get("afspraak")), None)
        c["afspraak"] = hit["afspraak"] if hit else None
    return {"volledig": "\n".join(regels) + "\n", "status": db.get("status"), "versie": versie, "dekking": dekking,
            "verblijven": verblijven, "doorgegaan": doorgegaan, "niet_gezien": niet_gezien,
            "zonder_adres": zonder_adres, "overig": overig, "werf": werf, "twijfel": twijfel, "elders": elders,
            "context": ctx, "wcache": wcache if wcache != wcache_voor else None,
            "projecten": sorted({"%s %s" % (v["project"].get("firma"), v["project"].get("nummer"))
                                 for v in verblijven if v.get("project")})}


def schrijf_met_revisie(pad, tekst):
    """Schrijft tekst naar pad. Stond er al iets anders, dan gaat dat eerst naar revisies/.
    Geeft 'nieuw', 'herzien' of 'gelijk'."""
    if os.path.exists(pad):
        oud = open(pad, encoding="utf-8").read()
        if oud == tekst:
            return "gelijk"
        rev = os.path.join(os.path.dirname(pad), "revisies")
        os.makedirs(rev, exist_ok=True)
        stam, ext = os.path.splitext(os.path.basename(pad))
        shutil.copy2(pad, os.path.join(rev, f"{stam}.{nu().strftime('%Y%m%dT%H%M%S')}{ext}"))
        uitkomst = "herzien"
    else:
        os.makedirs(os.path.dirname(pad), exist_ok=True)
        uitkomst = "nieuw"
    with open(pad, "w", encoding="utf-8") as f:
        f.write(tekst)
    return uitkomst


def lees_stand():
    try:
        d = json.load(open(STAND))
    except (OSError, ValueError):
        d = {}
    return {"afgesloten_tot": d.get("afgesloten_tot") or "", "versies": d.get("versies") or {}}


def te_doen(vandaag=None, revisies=None):
    """De dagen die (opnieuw) gemaakt moeten worden, nooit voor de startgrens:
      - de open dagen na de laatst afgesloten dag, de OUDSTE eerst (hoogstens INHAAL_MAX_DAGEN per
        ronde; de rest volgt de volgende ronde). Tot 05-10-2026 koos dit de nieuwste.
      - een al afgesloten dag waarvan het dagboek sindsdien veranderde (late punten, een correctie,
        nieuwe projectadressen): revisies is {dag: {"versie": ...}} van /api/revisies.
    """
    vandaag = vandaag or nu().date().isoformat()
    stand = lees_stand()
    open_ = [d for d in BB.dagen_vanaf_grens(vandaag) if d > stand["afgesloten_tot"]][:INHAAL_MAX_DAGEN]
    herzien = [d for d, r in (revisies or {}).items()
               if d <= stand["afgesloten_tot"] and BB.dag_toegestaan(d) and stand["versies"].get(d) != r.get("versie")]
    return sorted(set(herzien) | set(open_))


def stand_bijwerken(afgesloten, versies=None):
    """Onthoudt tot welke dag alles afgesloten is (aaneengesloten vanaf de grens) en welke versie
    van elk dagboek weggeschreven is. Alleen aanroepen met dagen die echt opgeslagen zijn."""
    stand = lees_stand()
    oud, nieuw = stand["afgesloten_tot"], stand["afgesloten_tot"]
    for d in BB.dagen_vanaf_grens(max(afgesloten) if afgesloten else BB.eerste_dag()):
        if d <= oud:
            continue
        if d in afgesloten:
            nieuw = d
        else:
            break
    stand["versies"].update(versies or {})
    os.makedirs(MAP, exist_ok=True)
    json.dump({"afgesloten_tot": nieuw, "versies": stand["versies"], "bijgewerkt": nu().isoformat()},
              open(STAND, "w"), indent=0)
    return nieuw


def verrijk(dag):
    """Adressen opzoeken en bezoekdagen tellen, in de tegel (beheer.py verrijk). Netwerk eerst, dan
    kort schrijven; een leesroute doet dit nooit. Faalt het, dan staat er in het dagboek gewoon
    een coördinaat in plaats van een adres."""
    try:
        r = subprocess.run(["docker", "exec", "app-locatie", "python3", "beheer.py", "verrijk", dag],
                           capture_output=True, text=True, timeout=300)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def controle():
    """De bronstatus en de taken van de tegel. Alarm alleen volgens het bronbeleid, de meetmodus en
    de ouderdom van elke taak. Is de tegel zelf onbereikbaar, dan is dat het alarm (controle
    05-10-2026: een ConnectionError liet de controle zonder hartslag of signaal crashen)."""
    if not (7 <= nu().hour <= 22):
        return
    dag = nu().date().isoformat()
    try:
        st = haal("/api/status")
    except Exception as e:  # noqa: BLE001
        tekst = "De tegel locatie.globaal.be antwoordt niet (%s). Draait app-locatie?" % type(e).__name__
        ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": dag, "titel": "Locatietegel onbereikbaar",
                      "uniek": f"locatie-tegel-onbereikbaar:{dag}", "inhoud": tekst}])
        ag.log(dag, "fout", tekst)
        ag.log_verstuur()
        ag.hartslag("fout", taak="tracker in het oog", detail="tegel onbereikbaar")
        return
    actief = [b for b in st.get("bronnen", []) if b.get("status") == "actief"]
    stand = "; ".join(f"{b.get('label')}: {b.get('toestand')}" for b in actief) or "geen actieve tracker"
    alarmen = list(st.get("alarmen") or [])
    # Tweede slot: de ouderdom van projectsync, dagboek en export ook hier uit de taken afleiden,
    # met dezelfde regel als de tegel, voor het geval de tegel ze niet als alarm meegaf.
    bekend = {a.get("sleutel") for a in alarmen}
    alarmen += [a for a in LS.taakalarmen(st.get("taken") or []) if a["sleutel"] not in bekend]
    if alarmen:
        # Geen "stil" in de titel en geen uur in de sleutel: De Bode belt bij "stil" (AGENTNORM v1.3),
        # en met het uur in de sleutel kwam dit tot 24-09-2026 elke twee uur opnieuw.
        ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": dag, "titel": a["titel"],
                      "uniek": f"{a['sleutel']}:{dag}", "inhoud": a["tekst"]} for a in alarmen])
        for a in alarmen:
            ag.log(dag, "fout", a["tekst"])
        ag.log_verstuur()
        ag.hartslag("fout", taak="tracker in het oog", detail=stand + "; " + "; ".join(a["titel"] for a in alarmen))
        taak_melden("controle", False, stand)
    else:
        ag.hartslag("waakt", taak="tracker in het oog", detail=stand)
        taak_melden("controle", True, stand)


def main():
    print(nu().strftime("%Y-%m-%dT%H:%M:%S%z"), " ".join(sys.argv[1:]) or "ronde", flush=True)   # tijdstempel per run
    if OM and not BB.binnen_venster(OM):
        return          # de andere van de twee UTC-uren: niet het Belgische uur
    if CONTROLE:
        controle()
        return
    if DAG and not BB.dag_toegestaan(DAG):
        print(f"{DAG} valt voor de start van de meetreeks ({BB.eerste_dag()}): niets te doen.")
        return
    if DROOG:
        # Samenstellen en tonen: alleen leesroutes; geen verrijking, geen dagboek, geen bord, geen stand.
        print(maak(DAG or nu().date().isoformat())["volledig"])
        return
    with ag.ronde("dagboek") as r:
        r.bron("bronbeleid", haal("/api/beleid"))
        st = haal("/api/status")
        r.bron("bronstatus", {b["bron"]: b.get("toestand") for b in st.get("bronnen", [])})
        revisies = haal("/api/revisies").get("revisies") or {}
        dagen = [DAG] if DAG else te_doen(revisies=revisies)
        afgesloten, versies, geschreven, fouten = [], {}, [], []
        for dag in dagen:
            verrijk(dag)
            try:
                d = maak(dag)
                if d["wcache"] is not None:       # de Agendawacht schrijft in hetzelfde bestand
                    W._cache_bewaren(d["wcache"])
                pad = os.path.join(MAP, "dagen", f"{dag}.md")
                hoe = schrijf_met_revisie(pad, d["volledig"])
                schrijf_met_revisie(os.path.join(MAP, "context", f"{dag}.json"),
                                    json.dumps(d["context"], ensure_ascii=False, indent=1) + "\n")
            except Exception as e:  # noqa: BLE001
                fouten.append(f"{dag}: {type(e).__name__} {str(e)[:120]}")
                ag.log(f"dag {dag}", "fout", fouten[-1])
                continue
            uit = ag.klaarzet([{"voor": "mehdi", "soort": "locatie", "sleutel": dag,
                                "titel": f"Locatielogboek {dag}" + (" (voorlopig)" if d["status"] == "voorlopig" else ""),
                                "uniek": f"locatie:{dag}", "verwijzing": pad, "inhoud": d["volledig"][:20000]}])
            geschreven.append(f"{dag} {hoe}")
            versies[dag] = d["versie"]
            # Alleen een opgeslagen dag met een ingestelde tracker telt als afgesloten.
            if d["status"] == "afgesloten":
                afgesloten.append(dag)
            elif d["status"] == "niet ingesteld":
                r.nood("De tracker in de auto staat niet (juist) in ATRACK_IMEIS: geen dag wordt afgesloten",
                       wie="claude-code")
            ag.log(f"dag {dag}", "bron", f"{len(d['verblijven'])} verblijven; projecten: {', '.join(d['projecten']) or 'geen'}; "
                   f"agenda: {len(d['doorgegaan'])} doorgegaan, {len(d['niet_gezien'])} niet gezien, "
                   f"{len(d['zonder_adres'])} buiten zonder adres, {d['overig']} niet te toetsen")
            ag.log(f"dag {dag}", "bevinding", f"{len(d['werf'])} keer auto bij een project zonder afspraak, "
                   f"{len(d['twijfel'])} met meerdere kandidaten, {len(d['elders'])} elders", d["volledig"])
            ag.log(f"dag {dag}", "schrijf", f"dagboek {hoe}: {pad} ({d['status']}, versie {d['versie']}); klaargezet "
                   f"({uit.get('nieuw', 0)} nieuw, {uit.get('bijgewerkt', 0)} bijgewerkt)")
            if d["zonder_adres"]:
                r.nood("Buitenafspraken zonder adres of bekend projectnummer: de vergelijking met de locatie is daar blind",
                       wie="collega")
        ag.log("stand", "schrijf", f"afgesloten tot {stand_bijwerken(afgesloten if not DAG else [], versies)}")
        sp = dropbox_prive.spiegel_map(MAP, "/Locatie")
        if sp["verstuurd"] or sp["fout"]:
            ag.log("dropbox", "schrijf", f"Dropbox privé: {sp['verstuurd']} bestand(en) verstuurd" + (f"; fout: {sp['fout']}" if sp["fout"] else ""))
        for n in dropbox_prive.nood(wat="het locatielogboek"):
            r.nood(n["tekst"], wie=n["wie"])
        for a in st.get("alarmen") or []:
            if a.get("sleutel", "").startswith("locatie-taak-"):
                r.nood(a["titel"], wie="claude-code")
        dek = st.get("projectdekking") or {}
        r.detail = (f"{', '.join(geschreven) or 'niets geschreven'}; projectplekken {dek.get('bruikbaar', '?')} van "
                    f"{dek.get('projecten', '?')} bruikbaar" + (f"; fouten: {'; '.join(fouten)}" if fouten else ""))
        taak_melden("dagboek", not fouten, r.detail)
    try:
        controle()
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()

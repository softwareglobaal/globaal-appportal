#!/usr/bin/env python3
"""De Locatiewacht (Privé, alleen voor Mehdi) — zijn bewegingslogboek.

Bron: de tegel locatie.globaal.be (OwnTracks op de iPhone), op de VM zonder login
bereikbaar op 127.0.0.1:3031: GET /api/dag/JJJJ-MM-DD (indeling in bezoeken en
verplaatsingen) en GET /gezond (punten, minuten sinds het laatste punt).

Elke avond (21:30) en met --dag JJJJ-MM-DD:
  1. het dagboek van de dag samenstellen, met adressen (Nominatim, gecachet), en
     wegschrijven op de VM: mijnagents-data/locatielogboek/dagen/<dag>.md.
     De Dropbox-map "private/0 Chegini Mehdi/Prive met Claude" is met het token
     van de stack (Siyans account) niet bereikbaar, dus de Dropbox-kopie maakt
     het Mac-script locatie/locatie-ophalen.py, zoals nu.
  2. het dagboek naast de agenda leggen: welke afspraak is volgens de locatie
     doorgegaan (adres van de afspraak binnen 300 m van een bezoek dat in tijd
     overlapt), welke niet gezien.
  3. bezoeken van meer dan twintig minuten zonder afspraak melden als mogelijk
     niet-geregistreerd werfbezoek (vaste plekken, vaak bezocht, apart benoemd).
  4. alles klaarzetten voor Mehdi (nooit voor een afdeling), werkverslag op het bord.
Elke twee uur (--controle): alarm als er meer dan zes uur geen punt binnenkwam
terwijl het geen nacht is (07:00-22:00): dan is de tracker stuk.
Leest alleen. Verwijdert niets uit het logboek.
"""
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import agenda  # noqa: E402
import bord  # noqa: E402

NAAM = "locatie-wacht"
ag = bord.Agent(NAAM)
LOCATIE = os.environ.get("LOCATIE_URL", "http://127.0.0.1:3031")
MAP = os.path.expanduser("~/appportal/mijnagents-data/locatielogboek")
CACHE = os.path.join(MAP, "adressen.json")
MIN_BEZOEK = 20
ALARM_UREN = 6
NACHT = (22, 7)
CONTROLE = "--controle" in sys.argv
DAG = None
for i, a in enumerate(sys.argv):
    if a == "--dag" and i + 1 < len(sys.argv):
        DAG = sys.argv[i + 1]
DAG = DAG or datetime.now().date().isoformat()
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


def coord_van_adres(tekst, cache):
    sleutel = "zoek:" + tekst.strip().lower()
    if sleutel in cache:
        return cache[sleutel].get("lat"), cache[sleutel].get("lon")
    try:
        d = _nominatim("search", {"q": tekst, "format": "jsonv2", "limit": 1, "countrycodes": "be,nl"})
        lat, lon = (float(d[0]["lat"]), float(d[0]["lon"])) if d else (None, None)
    except Exception:  # noqa: BLE001
        lat, lon = None, None
    cache[sleutel] = {"lat": lat, "lon": lon}
    return lat, lon


def afstand_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def uur(epoch):
    return datetime.fromtimestamp(int(epoch)).strftime("%H:%M")


def duur(m):
    m = int(m or 0)
    return f"{m // 60}u{m % 60:02d}" if m >= 60 else f"{m} min"


def epoch_van_iso(iso):
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------ werk ---
def dagboek(dag, cache):
    gegevens = haal(f"/api/dag/{dag}")
    indeling = gegevens.get("indeling") or []
    bezoeken = [s for s in indeling if s.get("soort") == "bezoek"]
    for s in bezoeken:
        s["adres"] = adres_van(s["lat"], s["lon"], cache)
        s["vaste_plek"] = cache.get(f"{s['lat']:.4f},{s['lon']:.4f}", {}).get("n", 0) >= 5
    r = [f"# Locatielogboek {dag}", ""]
    if not indeling:
        r.append("Geen gegevens. De telefoon heeft die dag niets doorgestuurd.")
        return "\n".join(r), bezoeken, gegevens
    r += ["| van | tot | duur | wat | waar |", "|---|---|---|---|---|"]
    for s in indeling:
        if s.get("soort") == "bezoek":
            r.append(f"| {uur(s['van'])} | {uur(s['tot'])} | {duur(s['minuten'])} | bezoek{' (vaste plek)' if s.get('vaste_plek') else ''} | {s['adres']} |")
        else:
            r.append(f"| {uur(s['van'])} | {uur(s['tot'])} | {duur(s['minuten'])} | verplaatsing {s.get('wijze', '')} | {int(s.get('meter', 0) / 100) / 10} km |")
    return "\n".join(r), bezoeken, gegevens


def vergelijk_agenda(dag, bezoeken, cache):
    """(doorgegaan, niet_gezien, onbekend) op basis van adres en tijd."""
    alle = agenda.afspraken(-1, 8) if agenda.beschikbaar() else []
    vandaag = [a for a in alle if a.get("start", "")[:10] == dag and not a.get("hele_dag")]
    doorgegaan, niet_gezien, zonder_adres = [], [], []
    for a in vandaag:
        van, tot = epoch_van_iso(a["start"]), epoch_van_iso(a["einde"])
        if not a.get("locatie"):
            zonder_adres.append(a["titel"])
            continue
        lat, lon = coord_van_adres(a["locatie"], cache)
        if lat is None:
            zonder_adres.append(f"{a['titel']} (adres niet gevonden: {a['locatie'][:40]})")
            continue
        treffer = None
        for b in bezoeken:
            if afstand_m(lat, lon, b["lat"], b["lon"]) <= 300 and b["van"] <= (tot or 0) + 1800 and b["tot"] >= (van or 0) - 1800:
                treffer = b
                break
        if treffer:
            doorgegaan.append(f"{a['start'][11:16]} {a['titel']} · ter plaatse {uur(treffer['van'])}-{uur(treffer['tot'])}")
            treffer["afspraak"] = a["titel"]
        else:
            niet_gezien.append(f"{a['start'][11:16]} {a['titel']} · {a['locatie'][:50]}")
    return doorgegaan, niet_gezien, zonder_adres


def controle():
    g = haal("/gezond")
    minuten = int(g.get("minuten_geleden") or 0)
    nu_uur = datetime.now().hour
    nacht = nu_uur >= NACHT[0] or nu_uur < NACHT[1]
    if minuten > ALARM_UREN * 60 and not nacht:
        ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": datetime.now().date().isoformat(),
                      "titel": f"Tracker stil sinds {minuten // 60} uur",
                      "uniek": f"locatie-alarm:{datetime.now().strftime('%Y-%m-%d-%H')}",
                      "inhoud": "Er kwam meer dan zes uur geen locatiepunt binnen terwijl het geen nacht is. Kijk de OwnTracks-app op de iPhone na."}])
        ag.log(datetime.now().date().isoformat(), "fout", f"tracker stil sinds {minuten} min")
        ag.log_verstuur()
        ag.hartslag("fout", taak="tracker stil", detail=f"geen punt sinds {minuten // 60} uur")
    else:
        ag.hartslag("waakt", taak="tracker in het oog", detail=f"laatste punt {minuten} min geleden, {g.get('punten', '?')} punten vandaag")


def main():
    if CONTROLE:
        controle()
        return
    ag.hartslag("actief", taak=f"dagboek {DAG}")
    try:
        cache = laad_cache()
        tekst, bezoeken, gegevens = dagboek(DAG, cache)
        doorgegaan, niet_gezien, zonder_adres = vergelijk_agenda(DAG, bezoeken, cache)
        onbekend = [b for b in bezoeken if int(b.get("minuten", 0)) >= MIN_BEZOEK and not b.get("afspraak") and not b.get("vaste_plek")]
        bewaar_cache(cache)
        r = [tekst, "", "## Naast de agenda", ""]
        r += ["Doorgegaan volgens de locatie:"] + ([f"- {x}" for x in doorgegaan] or ["- (geen)"])
        r += ["", "Niet gezien op de plek van de afspraak:"] + ([f"- {x}" for x in niet_gezien] or ["- (geen)"])
        if zonder_adres:
            r += ["", "Afspraken zonder bruikbaar adres:"] + [f"- {x}" for x in zonder_adres]
        r += ["", "Bezoeken van 20 minuten of meer zonder afspraak (mogelijk niet-geregistreerd werfbezoek):"]
        r += [f"- {uur(b['van'])}-{uur(b['tot'])} ({duur(b['minuten'])}) {b['adres']}" for b in onbekend] or ["- (geen)"]
        volledig = "\n".join(r) + "\n"
        os.makedirs(os.path.join(MAP, "dagen"), exist_ok=True)
        pad = os.path.join(MAP, "dagen", f"{DAG}.md")
        open(pad, "w", encoding="utf-8").write(volledig)
        uit = ag.klaarzet([{"voor": "mehdi", "soort": "locatie", "sleutel": DAG, "titel": f"Locatielogboek {DAG}",
                            "uniek": f"locatie:{DAG}", "verwijzing": pad, "inhoud": volledig[:20000]}])
        ag.log(f"dag {DAG}", "bron", f"{len(gegevens.get('indeling') or [])} segmenten, {len(bezoeken)} bezoeken; agenda: {len(doorgegaan)} doorgegaan, {len(niet_gezien)} niet gezien, {len(zonder_adres)} zonder adres")
        ag.log(f"dag {DAG}", "bevinding", f"{len(onbekend)} bezoek(en) van 20 min of meer zonder afspraak", volledig)
        ag.log(f"dag {DAG}", "schrijf", f"dagboek geschreven: {pad}; klaargezet voor Mehdi ({uit.get('nieuw', 0)} nieuw)")
        ag.log_verstuur()
        ag.hartslag("klaar", taak=f"dagboek {DAG} klaar", detail=f"{len(bezoeken)} bezoeken, {len(onbekend)} zonder afspraak")
        try:
            controle()
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()

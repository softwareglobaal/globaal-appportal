#!/usr/bin/env python3
"""
tijdlijn.py - leest de Google Maps Timeline-export (location-history.json)
en maakt er een leesbaar dagboek van: waar was ik, wanneer, hoe lang.

Werkt met zowel het iOS-formaat (kale array, "geo:lat,lng") als het
Android-formaat (wrapper semanticSegments, "lat°, lng°").

Gebruik:
    tijdlijn.py <bestand.json>                 overzicht van alles
    tijdlijn.py <bestand.json> --dag 2026-09-08
    tijdlijn.py <bestand.json> --van 2026-09-01 --tot 2026-09-09
    tijdlijn.py <bestand.json> --json          machineleesbaar naar stdout
    tijdlijn.py <bestand.json> --schrijf MAP   een .json + .md per dag
"""
import json, sys, re, argparse, os
from datetime import datetime, timedelta, date
from collections import defaultdict

# ---------- inlezen ----------

def laad(pad):
    with open(pad, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data, "ios"
    for sleutel in ("semanticSegments", "timelineObjects", "segments"):
        if isinstance(data, dict) and sleutel in data:
            return data[sleutel], "android"
    if isinstance(data, dict):
        # onbekende wrapper: pak de eerste lijst die we vinden
        for v in data.values():
            if isinstance(v, list):
                return v, "onbekend"
    raise SystemExit("Onbekend formaat: geen lijst met segmenten gevonden.")

# ---------- kleine helpers ----------

GEO = re.compile(r"(-?\d+\.?\d*)[^\d\-]+(-?\d+\.?\d*)")

def coord(waarde):
    """'geo:51.21,4.40' of '51.21°, 4.40°' of {'latLng': '...'} -> (lat, lng)"""
    if waarde is None:
        return None
    if isinstance(waarde, dict):
        waarde = waarde.get("latLng") or waarde.get("placeLocation") or ""
        if isinstance(waarde, dict):
            waarde = waarde.get("latLng", "")
    m = GEO.search(str(waarde))
    if not m:
        return None
    return (round(float(m.group(1)), 6), round(float(m.group(2)), 6))

def tijd(waarde):
    if not waarde:
        return None
    s = str(waarde).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        return None
    # De export mengt tijdzones: bezoeken dragen de lokale offset (+02:00),
    # sporen staan in UTC (Z). Alles gelijktrekken naar de tijdzone van deze Mac,
    # anders lijkt een spoor twee uur eerder te gebeuren dan het bezoek erin.
    return t.astimezone() if t.tzinfo else t

def getal(waarde):
    try:
        return float(waarde)
    except (TypeError, ValueError):
        return None

def duurtekst(minuten):
    if minuten is None:
        return "?"
    u, m = divmod(int(round(minuten)), 60)
    return f"{u}u{m:02d}" if u else f"{m} min"

VERVOER = {
    "IN_PASSENGER_VEHICLE": "auto", "IN_VEHICLE": "voertuig", "WALKING": "te voet",
    "ON_FOOT": "te voet", "CYCLING": "fiets", "IN_BUS": "bus", "IN_TRAIN": "trein",
    "IN_TRAM": "tram", "IN_SUBWAY": "metro", "FLYING": "vliegtuig",
    "MOTORCYCLING": "motor", "RUNNING": "lopend", "UNKNOWN_ACTIVITY_TYPE": "onbekend",
}

DAGEN = ["maandag","dinsdag","woensdag","donderdag","vrijdag","zaterdag","zondag"]
MAANDEN = ["","januari","februari","maart","april","mei","juni","juli",
           "augustus","september","oktober","november","december"]

def nl_datum(d, kort=False):
    if kort:
        return f"{DAGEN[d.weekday()][:2]} {d.strftime('%d-%m-%Y')}"
    return f"{DAGEN[d.weekday()]} {d.day} {MAANDEN[d.month]} {d.year}"

SOORT = {
    "HOME": "thuis", "WORK": "werk", "INFERRED_HOME": "thuis (afgeleid)",
    "INFERRED_WORK": "werk (afgeleid)", "SEARCHED_ADDRESS": "opgezocht adres",
}

# ---------- omzetten naar nette records ----------

def ontleed(segmenten):
    uit = []
    for seg in segmenten:
        if not isinstance(seg, dict):
            continue
        start = tijd(seg.get("startTime") or seg.get("startTimestamp"))
        eind = tijd(seg.get("endTime") or seg.get("endTimestamp"))
        if not start:
            continue
        minuten = (eind - start).total_seconds() / 60 if eind else None

        if "visit" in seg:
            v = seg["visit"] or {}
            kand = v.get("topCandidate") or {}
            uit.append({
                "soort": "bezoek",
                "start": start, "eind": eind, "minuten": minuten,
                "plaats_id": kand.get("placeID") or kand.get("placeId"),
                "coord": coord(kand.get("placeLocation")),
                "type": SOORT.get(kand.get("semanticType"), kand.get("semanticType")),
                "zekerheid": getal(kand.get("probability")) or getal(v.get("probability")),
            })

        elif "activity" in seg:
            a = seg["activity"] or {}
            kand = a.get("topCandidate") or {}
            afstand = getal(a.get("distanceMeters")) or getal(a.get("distance"))
            uit.append({
                "soort": "verplaatsing",
                "start": start, "eind": eind, "minuten": minuten,
                "van": coord(a.get("start")), "naar": coord(a.get("end")),
                "meter": afstand,
                "wijze": VERVOER.get(kand.get("type"), (kand.get("type") or "?").lower()),
                "zekerheid": getal(kand.get("probability")),
            })

        elif "timelinePath" in seg:
            punten = []
            for p in seg["timelinePath"] or []:
                c = coord(p.get("point"))
                if not c:
                    continue
                off = getal(p.get("durationMinutesOffsetFromStartTime"))
                t = start + timedelta(minutes=off) if off is not None else tijd(p.get("time"))
                punten.append({"tijd": t, "coord": c})
            if punten:
                uit.append({
                    "soort": "spoor", "start": start,
                    "eind": eind or punten[-1]["tijd"], "minuten": minuten,
                    "punten": punten,
                })
    uit.sort(key=lambda r: r["start"])
    return uit

def per_dag(records):
    dagen = defaultdict(list)
    for r in records:
        dagen[r["start"].date()].append(r)
    return dict(sorted(dagen.items()))

# ---------- weergave ----------

def kaartlink(c):
    return f"https://maps.google.com/?q={c[0]},{c[1]}" if c else ""

def regel(r):
    t = r["start"].strftime("%H:%M")
    e = r["eind"].strftime("%H:%M") if r.get("eind") else "?"
    if r["soort"] == "bezoek":
        etiket = r.get("type") or "plaats"
        c = r.get("coord")
        return (f"{t}-{e}  {duurtekst(r['minuten']):>7}  bezoek     "
                f"{etiket:<16} {c[0] if c else '?'},{c[1] if c else ''}")
    if r["soort"] == "verplaatsing":
        km = f"{r['meter']/1000:.1f} km" if r.get("meter") else "? km"
        return (f"{t}-{e}  {duurtekst(r['minuten']):>7}  onderweg   "
                f"{r['wijze']:<16} {km}")
    return f"{t}-{e}  {duurtekst(r['minuten']):>7}  spoor      {len(r['punten'])} punten"

def dag_markdown(d, records):
    uit = [f"# {nl_datum(d)}", ""]
    bezoeken = [r for r in records if r["soort"] == "bezoek"]
    ritten = [r for r in records if r["soort"] == "verplaatsing"]
    km = sum(r["meter"] or 0 for r in ritten) / 1000
    uit.append(f"{len(bezoeken)} bezoeken, {len(ritten)} verplaatsingen, {km:.1f} km")
    uit.append("")
    uit.append("| van | tot | duur | wat | detail | kaart |")
    uit.append("|---|---|---|---|---|---|")
    for r in records:
        t, e = r["start"].strftime("%H:%M"), (r["eind"].strftime("%H:%M") if r.get("eind") else "")
        if r["soort"] == "bezoek":
            c = r.get("coord")
            uit.append(f"| {t} | {e} | {duurtekst(r['minuten'])} | bezoek | "
                       f"{r.get('type') or ''} {r.get('plaats_id') or ''} | "
                       f"[{c[0]},{c[1]}]({kaartlink(c)}) |" if c else
                       f"| {t} | {e} | {duurtekst(r['minuten'])} | bezoek | | |")
        elif r["soort"] == "verplaatsing":
            km = f"{r['meter']/1000:.1f} km" if r.get("meter") else ""
            uit.append(f"| {t} | {e} | {duurtekst(r['minuten'])} | onderweg | {r['wijze']} {km} | |")
    return "\n".join(uit) + "\n"

def json_klaar(r):
    o = {}
    for k, v in r.items():
        if isinstance(v, datetime):
            o[k] = v.isoformat()
        elif k == "punten":
            o[k] = [{"tijd": p["tijd"].isoformat() if p["tijd"] else None,
                     "coord": p["coord"]} for p in v]
        else:
            o[k] = v
    return o

# ---------- hoofdprogramma ----------

def main():
    p = argparse.ArgumentParser(description="Google Maps Timeline-export omzetten naar een dagboek")
    p.add_argument("bestand")
    p.add_argument("--dag")
    p.add_argument("--van")
    p.add_argument("--tot")
    p.add_argument("--json", action="store_true")
    p.add_argument("--schrijf", metavar="MAP")
    a = p.parse_args()

    segmenten, herkomst = laad(a.bestand)
    records = ontleed(segmenten)
    if not records:
        raise SystemExit("Geen bruikbare segmenten gevonden in dit bestand.")

    dagen = per_dag(records)
    if a.dag:
        d = date.fromisoformat(a.dag)
        dagen = {d: dagen.get(d, [])}
    else:
        if a.van:
            v = date.fromisoformat(a.van); dagen = {k: r for k, r in dagen.items() if k >= v}
        if a.tot:
            t = date.fromisoformat(a.tot); dagen = {k: r for k, r in dagen.items() if k <= t}

    if a.json:
        print(json.dumps({str(d): [json_klaar(r) for r in rs] for d, rs in dagen.items()},
                         ensure_ascii=False, indent=2))
        return

    if a.schrijf:
        os.makedirs(a.schrijf, exist_ok=True)
        for d, rs in dagen.items():
            with open(os.path.join(a.schrijf, f"{d}.json"), "w", encoding="utf-8") as f:
                json.dump([json_klaar(r) for r in rs], f, ensure_ascii=False, indent=2)
            with open(os.path.join(a.schrijf, f"{d}.md"), "w", encoding="utf-8") as f:
                f.write(dag_markdown(d, rs))
        print(f"{len(dagen)} dag{'en' if len(dagen)!=1 else ''} weggeschreven naar {a.schrijf}")
        return

    alle = list(dagen.keys())
    print(f"Bron: {a.bestand}  (formaat: {herkomst})")
    if alle:
        print(f"Periode: {alle[0]} t/m {alle[-1]}  -  {len(alle)} dag{'en' if len(alle)!=1 else ''}, {len(records)} segmenten")
    print()
    for d, rs in dagen.items():
        km = sum(r.get("meter") or 0 for r in rs if r["soort"] == "verplaatsing") / 1000
        print(f"--- {nl_datum(d, kort=True)}   {len([r for r in rs if r['soort']=='bezoek'])} bezoeken, {km:.1f} km")
        for r in rs:
            print("   " + regel(r))
        print()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""De Filewacht: belt Mehdi als de file zijn buffer opeet.

Voor elke buitenafspraak die binnen twee uur begint vraagt hij de rijtijd opnieuw op
met het verkeer van dit moment. Duurt de rit meer dan de buffer langer dan het
reistijdblok dat in de agenda staat, dan haalt hij zijn afspraak niet en wordt hij
gebeld. Een afspraak wordt hoogstens één keer per twintig minuten nagerekend en
hoogstens twee keer gebeld, zodat de Google-aanroepen en de telefoon beperkt blijven.

Draaien:  ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/file_wacht.py
          --droog   alleen tonen, niet bellen
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W                      # noqa: E402
from koppelingen import agenda as A           # noqa: E402
from koppelingen import bord, bellen          # noqa: E402

STAND = Path.home() / "appportal/mijnagents-data/file-wacht.json"
VOORUIT_MIN = 120      # zover vooruit kijken
HERTEST_MIN = 20       # niet vaker dan dit per afspraak narekenen
MAX_OPROEPEN = 2       # per afspraak per dag
DROOG = "--droog" in sys.argv
if DROOG:
    # Een proefronde mag de betaalde Google-aanroepen niet opeten. Op 20-09-2026 stond
    # de teller door mijn eigen proeven op 100 van 100 en viel alles terug op de filefactor.
    W.ROUTES_KEY = ""


def stand():
    try:
        d = json.loads(STAND.read_text())
        return d if d.get("dag") == datetime.now().strftime("%Y-%m-%d") else {"dag": datetime.now().strftime("%Y-%m-%d")}
    except (OSError, ValueError):
        return {"dag": datetime.now().strftime("%Y-%m-%d")}


def bewaar(d):
    STAND.parent.mkdir(parents=True, exist_ok=True)
    STAND.write_text(json.dumps(d, indent=0))


def main():
    ag = bord.Agent("agenda-wacht")
    st = stand()
    nu = datetime.now().astimezone()
    grens = nu + timedelta(minutes=VOORUIT_MIN)
    items = A.afspraken(van_dagen=0, tot_dagen=1)
    cache = W._cache_laden()
    thuis = W.coord(W.THUIS, cache)
    projecten = W.projectadressen.index()
    reistijden = [x for x in items if W.lees_titel(x["titel"])["reistijd"]]
    gemeld = []

    for a in sorted(items, key=lambda x: x.get("start", "")):
        if a.get("fout") or a.get("hele_dag") or "T" not in (a.get("start") or ""):
            continue
        info = W.lees_titel(a["titel"])
        if info["reistijd"] or not (info["buiten"] or info["soort"] in ("PB", "KB")):
            continue
        try:
            start = datetime.fromisoformat(a["start"])
        except ValueError:
            continue
        if not (nu < start <= grens):
            continue

        adres = a.get("locatie") or ""
        if not adres or adres.lower().startswith("http"):
            if info["nummer"] and info["nummer"] in projecten:
                adres = projecten[info["nummer"]]["adres"]
            else:
                gevonden, _ = W.plek_zoeken(a["titel"] + " " + (a.get("omschrijving") or ""))
                adres = gevonden or ""
        if not adres:
            continue

        sleutel = a.get("id") or a["titel"][:40]
        vorig = st.get(sleutel) or {}
        if vorig.get("laatst"):
            if (nu - datetime.fromisoformat(vorig["laatst"])).total_seconds() < HERTEST_MIN * 60:
                continue
        if vorig.get("oproepen", 0) >= MAX_OPROEPEN:
            continue

        doel = W.coord(adres, cache)
        if not (doel and thuis):
            continue
        # het reistijdblok dat de wacht ervoor zette, is de planning
        gepland = None
        for x in reistijden:
            if x["kalender"] == a["kalender"] and "T" in x["start"]:
                b0 = datetime.fromisoformat(x["start"])
                if start - timedelta(hours=3) <= b0 <= start:
                    gepland = (b0, (datetime.fromisoformat(x["einde"]) - b0).total_seconds() / 60)
        try:
            nodig, hoe = W.rijtijd_min(thuis, doel, nu)
        except Exception as e:  # noqa: BLE001
            print("rijtijd niet op te vragen:", type(e).__name__, file=sys.stderr)
            continue

        st[sleutel] = {"laatst": nu.isoformat(), "oproepen": vorig.get("oproepen", 0)}
        aankomst = nu + timedelta(minutes=nodig)
        te_laat = (aankomst - start).total_seconds() / 60
        plan_min = gepland[1] if gepland else None
        verschil = (nodig - plan_min) if plan_min else None

        regel = (f"{a['titel'][:44]} om {a['start'][11:16]}: nu {nodig} min rijden ({hoe})"
                 + (f", gepland {int(plan_min)} min" if plan_min else "")
                 + (f", je komt {int(te_laat)} min te laat" if te_laat > 0 else ", je haalt het"))
        print("  " + regel)

        moet_bellen = te_laat > 0 or (verschil is not None and verschil > W.BUFFER_MIN)
        if not moet_bellen:
            continue
        tekst = (f"Mehdi, de rit naar {W.plaatsnaam(adres) or 'je afspraak'} duurt nu {nodig} minuten. "
                 + (f"Je komt ongeveer {int(te_laat)} minuten te laat voor {a['titel'][:60]}. "
                    if te_laat > 0 else
                    f"Dat is {int(verschil)} minuten meer dan gepland voor {a['titel'][:60]}. ")
                 + "Vertrek nu, of verwittig de klant.")
        gemeld.append(regel)
        if DROOG:
            print("     (droog) zou bellen:", tekst[:90])
        else:
            uit = bellen.bel_afspraak(tekst)
            st[sleutel]["oproepen"] = vorig.get("oproepen", 0) + 1
            print("     gebeld:", uit)

    bewaar(st)
    if gemeld:
        ag.log(f"dag {datetime.now().strftime('%Y-%m-%d')}", "bevinding",
               "file eet de buffer op, Mehdi gebeld", "\n".join(gemeld))
    else:
        print("  geen enkele rit loopt uit")
    return 0


if __name__ == "__main__":
    sys.exit(main())

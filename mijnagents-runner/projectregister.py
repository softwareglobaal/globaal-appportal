#!/usr/bin/env python3
"""Het projectregister: elk project waar Mehdi naartoe gaat, met firma, nummer, adres
en coordinaten.

Waarom: een afspraak buiten heeft een adres nodig dat de agent echt kan omzetten. Het
register groeit mee met de agenda, en wat een half jaar niet meer voorkomt valt eruit
zodat het niet oeverloos wordt. Mandaat van Mehdi, 20-09-2026.

Draaien:  ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/projectregister.py
          --toon   alleen tonen, niets wegschrijven
"""
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W                      # noqa: E402
from koppelingen import agenda as A           # noqa: E402

BESTAND = HIER / "werkwijze" / "projecten.json"
TERUG_MAANDEN = 12
VERVAL_MAANDEN = 6
TOON = "--toon" in sys.argv


def main():
    kop = {"Authorization": "Bearer " + A._toegang()}
    nu = datetime.now(timezone.utc)
    van = (nu - timedelta(days=TERUG_MAANDEN * 31)).isoformat()
    tot = (nu + timedelta(days=120)).isoformat()
    cache = W._cache_laden()
    projecten = W.projectadressen.index()
    gevonden = {}

    for kal, label in W.KALENDERS.items():
        if kal.startswith("en.be#"):
            continue
        pag = None
        while True:
            q = {"timeMin": van, "timeMax": tot, "singleEvents": "true", "maxResults": "2500",
                 "fields": "items(summary,location,start),nextPageToken"}
            if pag:
                q["pageToken"] = pag
            try:
                d = json.load(urllib.request.urlopen(urllib.request.Request(
                    f"{A.API}/calendars/{urllib.parse.quote(kal, safe='')}/events?"
                    + urllib.parse.urlencode(q), headers=kop), timeout=60))
            except Exception as e:  # noqa: BLE001
                print(f"{label}: niet leesbaar ({type(e).__name__})", file=sys.stderr)
                break
            for ev in d.get("items", []):
                titel = ev.get("summary", "") or ""
                info = W.lees_titel(titel)
                nr = info.get("nummer")
                if not nr or info["reistijd"]:
                    continue
                dag = (ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date") or "")[:10]
                p = gevonden.setdefault(nr, {"nummer": nr, "firma": "", "architect": "",
                                             "adres": "", "gemeente": "", "coordinaten": None,
                                             "laatst_gezien": "", "eerst_gezien": "",
                                             "aantal_afspraken": 0, "bron_adres": ""})
                p["aantal_afspraken"] += 1
                if dag and (not p["laatst_gezien"] or dag > p["laatst_gezien"]):
                    p["laatst_gezien"] = dag
                if dag and (not p["eerst_gezien"] or dag < p["eerst_gezien"]):
                    p["eerst_gezien"] = dag
                if info.get("firma") and not p["firma"]:
                    p["firma"] = info["firma"]
                loc = (ev.get("location") or "").strip()
                if loc and not loc.lower().startswith("http") and not p["adres"]:
                    p["adres"], p["bron_adres"] = loc, "agenda"
            pag = d.get("nextPageToken")
            if not pag:
                break

    # aanvullen uit de projectmap en omzetten naar coordinaten
    for nr, p in gevonden.items():
        if not p["adres"] and nr in projecten:
            p["adres"], p["gemeente"], p["bron_adres"] = projecten[nr]["adres"], projecten[nr]["gemeente"], "projectmap"
        elif nr in projecten and not p["gemeente"]:
            p["gemeente"] = projecten[nr]["gemeente"]
        if p["adres"]:
            p["coordinaten"] = W.coord(p["adres"], cache)
    W._cache_bewaren(cache)

    grens = (datetime.now() - timedelta(days=VERVAL_MAANDEN * 31)).date().isoformat()
    actief = {nr: p for nr, p in gevonden.items() if (p["laatst_gezien"] or "") >= grens}
    verlopen = sorted(set(gevonden) - set(actief))

    uit = {"versie": "1.0", "datum": datetime.now().date().isoformat(),
           "waarover": "Elk project waar Mehdi naartoe gaat, met firma, nummer, adres en coordinaten. "
                       "Gebouwd uit de agenda van de laatste twaalf maanden plus wat er vooruit staat, "
                       "aangevuld met het adres uit de projectmap.",
           "regels": {"opname": "een project komt erin zodra er een afspraak met dat nummer in de agenda staat",
                      "opschonen": f"geen afspraak meer in {VERVAL_MAANDEN} maanden betekent eruit, zodat "
                                   "het register niet oeverloos wordt",
                      "architect": "nog niet in te vullen: geen enkele bron die ik kan lezen kent de "
                                   "architect per project (niet het dossiersysteem, niet Pipedrive, "
                                   "niet de mapnaam)"},
           "aantal": len(actief), "verlopen_deze_ronde": verlopen,
           "projecten": sorted(actief.values(), key=lambda x: x["laatst_gezien"], reverse=True)}

    zonder = [p["nummer"] for p in actief.values() if not p["coordinaten"]]
    print(f"{len(actief)} projecten in het register, {len(verlopen)} vervallen")
    print(f"{len(zonder)} zonder bruikbare coordinaten: {', '.join(zonder[:20])}")
    if not TOON:
        BESTAND.write_text(json.dumps(uit, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("weggeschreven naar", BESTAND.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())

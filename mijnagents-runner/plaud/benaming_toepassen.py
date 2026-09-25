#!/usr/bin/env python3
"""Past een benamingsbestand toe op het Plaud-archief: zet de benaming in gesprek.json en
hernoemt de map naar JJJJ-MM-DD UUMM FIRMA dossier - met wie - onderwerp.

De naam in Plaud moet dezelfde worden (afspraak Mehdi); de koppeling kan niet in Plaud
schrijven, dus het script geeft per opname de exacte naam voor Plaud terug. De map wordt
op Plaud-id teruggevonden (mapnaam.map_van), dus hernoemen maakt geen dubbels bij een
volgende ophaalronde. De vorige naam blijft in gesprek.json: alles is terug te draaien.

Gebruik: benaming_toepassen.py <benaming.json> [--droog]
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mapnaam  # noqa: E402

DOEL = Path(os.environ.get("PLAUD_DOEL", Path.home() / "TKN-buro Dropbox" / "Data uit Mehdi" / "Plaud"))


def plaudnaam(b):
    n = f"{b['firma']} {b['dossier']}"
    if b.get("met_wie"):
        n += f" - {b['met_wie']}"
    if b.get("onderwerp"):
        n += f" - {b['onderwerp']}"
    return n


def main(pad, droog):
    besluiten = json.loads(Path(pad).read_text(encoding="utf-8"))
    uit = []
    for b in besluiten:
        m = mapnaam._index(DOEL).get(b["plaud_id"])
        if m is None:
            uit.append({"plaud_id": b["plaud_id"], "fout": "niet in het archief"}); continue
        g = json.loads((m / "gesprek.json").read_text(encoding="utf-8"))
        if not b.get("hernoem"):
            g["benaming"] = {"status": "open", "zekerheid": b.get("zekerheid"), "reden": b.get("reden", ""),
                             "beoordeeld": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            if not droog:
                (m / "gesprek.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
            uit.append({"map": m.name, "status": "open", "reden": b.get("reden", "")}); continue
        naam_plaud = plaudnaam(b)
        nieuw = mapnaam.mapnaam({"start_at": g["start_utc"], "name": naam_plaud})
        g["benaming"] = {"status": "hernoemd", "firma": b["firma"], "dossier": b["dossier"], "met_wie": b.get("met_wie", ""),
                         "onderwerp": b.get("onderwerp", ""), "zekerheid": b.get("zekerheid"), "bronnen": b.get("bronnen", []),
                         "momentmap": b.get("momentmap", ""), "naam_voor_plaud": naam_plaud,
                         "vorige_map": g.get("benaming", {}).get("vorige_map") or m.name,
                         "hernoemd": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        doelmap = DOEL / nieuw
        if not droog:
            (m / "gesprek.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
            if doelmap != m:
                if doelmap.exists():
                    uit.append({"map": m.name, "fout": f"doel bestaat al: {nieuw}"}); continue
                m.rename(doelmap)
        uit.append({"van": m.name, "naar": nieuw, "naam_voor_plaud": naam_plaud, "zekerheid": b.get("zekerheid")})
    print(json.dumps(uit, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], "--droog" in sys.argv)

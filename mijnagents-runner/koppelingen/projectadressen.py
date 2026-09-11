"""Projectnummer -> adres van de bouwplaats, gelezen uit de H-Architects-projectmappen in Dropbox.

Regel A13 van de H-A afspraken: de projectmap heet
  <nummer> <straat huisnummer>, <postcode> <gemeente> (<type>)(<omvang>)
Dus de mapnaam is de bron van het adres. We lezen drie niveaus diep onder
"Work All/01. H-A WORK" (hoofdmap, fasemap, projectmap) en bewaren de index een dag.
"""
import json
import os
import re
import time

import bronnen

BASIS = os.environ.get("HA_WORK_BASIS", "/Work All/01. H-A WORK")
CACHE = os.path.expanduser("~/appportal/mijnagents-data/projectadressen.json")
MAP_RE = re.compile(r"^(\d{4})\s+(.+?)\s*,?\s+(\d{4})\s+([A-Za-zÀ-ÿ' .-]+?)\s*(?:\(|$|-\s|:)")
OVERSLAAN = ("0 Archive", "Nog te sorteren", "TO DO FOR MEHDI", "_0 Claude reorganisatie", "H-A General", "H-A WORK alias")


def _mappen(pad):
    return [e for e in (bronnen.lijst(pad, recursief=False) or []) if e.get(".tag") == "folder"]


def bouw():
    """Leest de mappen en geeft {nummer: {adres, map, gemeente}}."""
    uit = {}
    lagen = [e for e in _mappen(BASIS) if e["name"] not in OVERSLAAN]
    te_bekijken = list(lagen)
    for _ in range(2):  # fasemappen en projectmappen
        volgende = []
        for e in te_bekijken:
            for sub in _mappen(e["path_display"]):
                m = MAP_RE.match(sub["name"])
                if m:
                    nr, straat, post, gem = m.groups()
                    gem = re.sub(r"\s+(regularisatie|reg|stan|light|urgent|onderzoek|nieuwbouw|verbouwing)\b.*$", "", gem, flags=re.I)
                    uit.setdefault(nr, {"adres": f"{straat.strip(' ,')}, {post} {gem.strip()}", "gemeente": gem.strip(), "map": sub["path_display"]})
                elif not re.match(r"^\d{4}\b", sub["name"]):
                    volgende.append(sub)
        te_bekijken = volgende
    return uit


def index(maximum_uren=24):
    try:
        c = json.load(open(CACHE))
        if time.time() - c.get("ts", 0) < maximum_uren * 3600 and c.get("projecten"):
            return c["projecten"]
    except (OSError, ValueError):
        pass
    if not bronnen.dropbox_beschikbaar():
        return {}
    projecten = bouw()
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump({"ts": time.time(), "projecten": projecten}, open(CACHE, "w"), ensure_ascii=False, indent=0)
    return projecten


def adres(nummer):
    p = index().get(str(nummer or ""))
    return p["adres"] if p else ""


if __name__ == "__main__":
    p = index(maximum_uren=0)
    print(len(p), "projecten met adres")
    for k in sorted(p)[-10:]:
        print(k, p[k]["adres"], "|", p[k]["map"])

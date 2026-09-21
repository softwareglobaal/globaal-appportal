#!/usr/bin/env python3
"""Proef van de naamregel over een heel gespreksarchief. Alleen lezen: hernoemt niets en
schrijft niets in het archief. Uitvoer: een JSON met het voorstel per gesprek en een telling
van wat ontbreekt, zodat we zien waar we tekortkomen.

Gebruik:
  python3 benaming_proef.py <archiefmap> <uitvoer.json> [--kern <organisatie.json>]
Zonder --kern leest hij collega's via koppelingen/organisatie.py (op de VM).
"""
import collections
import glob
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import benaming  # noqa: E402


def herkenner(kern_pad):
    if kern_pad:
        collegas = json.load(open(kern_pad))["collegas"]
    else:
        import organisatie
        collegas = organisatie.collegas(alleen_in_dienst=False)

    def herken(tekst):
        t = (tekst or "").strip().lower()
        if not t:
            return None
        for p in collegas:
            if t in (p["naam"].lower(), (p.get("email") or "").lower(), f"{p['voornaam']} {p.get('achternaam', '')}".strip().lower()):
                return p
        k = [p for p in collegas if p["voornaam"].lower() == t.split()[0]]
        return k[0] if len(k) == 1 else None
    return herken


def main():
    archief, uitvoer = sys.argv[1], sys.argv[2]
    kern = sys.argv[sys.argv.index("--kern") + 1] if "--kern" in sys.argv else ""
    herken = herkenner(kern)
    rijen, tel, per_firma, ontbreekt = [], collections.Counter(), collections.Counter(), collections.Counter()
    for f in sorted(glob.glob(os.path.join(archief, "*", "gesprek.json")), reverse=True):
        g = json.load(open(f))
        b = benaming.benoem(g, herken)
        map_ = os.path.basename(os.path.dirname(f))
        stempel = map_[:15]
        nieuw = benaming.naam(stempel, b)
        rijen.append({"map": map_, "recording_id": g.get("recording_id"), "titel": g.get("title") or "", "duur": g.get("duur_minuten"),
                      "opgenomen_door": (g.get("recorded_by") or {}).get("email", ""), "voorstel": nieuw, **b})
        tel["totaal"] += 1
        tel[f"zekerheid {b['zekerheid']}"] += 1
        tel["met voorstel"] += 1 if nieuw else 0
        per_firma[b["firma"] or ("prive" if b["prive"] else "onbekend")] += 1
        for d in b["ontbreekt"]:
            ontbreekt[d] += 1
    json.dump({"telling": dict(tel), "per_firma": dict(per_firma.most_common()), "ontbreekt": dict(ontbreekt), "gesprekken": rijen},
              open(uitvoer, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"telling": dict(tel), "per_firma": dict(per_firma.most_common()), "ontbreekt": dict(ontbreekt)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

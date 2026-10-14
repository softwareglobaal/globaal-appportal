#!/usr/bin/env python3
"""Bestaande bordbezoeken aansluiten op vaste IDs; geen AI, samenvoeging of verwijdering."""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord
import werfregister


def rijen():
    dossiers = bord.call("/api/werfbezoek").get("dossiers", [])
    uit = []
    for dossier in dossiers:
        uit.extend(bord.call("/api/werfbezoek?dossier=" + dossier["dossier"]).get("rijen", []))
    return uit


def aansluiten(items, toepassen=False):
    groepen = Counter((r["dossier"], r["volgnr"]) for r in items if not r.get("stand", "").startswith("dubbel na verhuis"))
    rapport = {"versie": 1, "gemeten_utc": datetime.now(timezone.utc).isoformat(), "toegepast": toepassen,
               "aantal_bordrijen": len(items), "dossiers": sorted({r["dossier"] for r in items}),
               "ambigue_rijvolgnummers": sum(n > 1 for n in groepen.values()), "rijen": []}
    for rij in items:
        d = {"bordrij_id": rij["id"], "dossier": rij["dossier"], "rijvolgnr": rij["volgnr"],
             "status": "verhuisdubbel_behouden" if rij.get("stand", "").startswith("dubbel na verhuis") else "klaar_voor_registratie",
             "dubbele_rijvolgnr": groepen[(rij["dossier"], rij["volgnr"])] > 1,
             "gegevens_behouden": bool(rij.get("gegevens")), "keuzes_behouden": bool(rij.get("keuzes")),
             "proef_behouden": bool(rij.get("proef_pad"))}
        if toepassen and d["status"] != "verhuisdubbel_behouden":
            registratie = werfregister.registreer(rij, rij["dossier"], rij["volgnr"])
            bord.call("/api/werfbezoek", {"rijen": [{"dossier": rij["dossier"], "datum": rij["datum"],
                       "bezoekmap": rij["bezoekmap"], "volgnr": rij["volgnr"], "werfbezoek_id": rij["id"],
                       "_alleen": ["registratie"], "registratie": registratie}]})
            d.update(status="geregistreerd", bezoek_id=registratie["bezoek_id"])
        rapport["rijen"].append(d)
    rapport["geregistreerd"] = sum(r["status"] == "geregistreerd" for r in rapport["rijen"])
    return rapport


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--toepassen", action="store_true")
    p.add_argument("--rapport", required=True)
    a = p.parse_args()
    rapport = aansluiten(rijen(), a.toepassen)
    with open(a.rapport, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({k: v for k, v in rapport.items() if k != "rijen"}, ensure_ascii=False))


if __name__ == "__main__":
    main()

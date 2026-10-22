#!/usr/bin/env python3
"""Bestaande bordbezoeken aansluiten op vaste IDs; geen AI, samenvoeging of verwijdering."""
import argparse
import hashlib
import json
import os
import sys
import urllib.parse
from collections import Counter
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord
import werfregister


def _relatief(pad, projectmap):
    pad = pad or ""
    return pad[len(projectmap):].casefold() if projectmap and pad.casefold().startswith(projectmap.casefold() + "/") else pad.casefold()


def bevindingen_uit_rijen(bord_rijen):
    """Bezoeken waarvoor Mehdi op het bord 'verslag van bevindingen' koos (2309, 21-10-2026). Drie sleutels, zodat de keuze
    een mapverhuis overleeft (driehoeksoverleg 22-10, K8/C5): volledig pad, pad binnen de projectmap en vast bezoek-ID."""
    uit = set()
    for r in bord_rijen:
        if not (isinstance(r.get("keuzes"), dict) and r["keuzes"].get("verslagtype") == "verslag_bevindingen"):
            continue
        if r.get("bezoekmap"):
            uit |= {"pad:" + r["bezoekmap"].casefold(), "rel:" + _relatief(r["bezoekmap"], r.get("projectmap") or "")}
        bid = r["registratie"].get("bezoek_id") if isinstance(r.get("registratie"), dict) else None
        if bid:
            uit.add("id:" + bid)
    return uit


def is_bevindingen(bezoek, projectmap, bevindingen, bezoek_id=None):
    if not bevindingen:
        return False
    sleutels = {"pad:" + bezoek["map"].casefold(), "rel:" + _relatief(bezoek["map"], projectmap)}
    bezoek_id = bezoek_id or (bezoek.get("registratie") or {}).get("bezoek_id")
    if bezoek_id:
        sleutels.add("id:" + bezoek_id)
    return bool(sleutels & set(bevindingen))


def koppel_voor_nummering(bezoeken, dossier, projectmap, werfstart, bord_rijen, bevindingen=()):
    """Koppel het app-ID vóór de definitieve N-nummering op het bord.

    Eerst een bestaand bord-ID bij hetzelfde relatieve bezoekpad (ook na een faseverhuis),
    dan een ondubbelzinnig appbezoek met dezelfde datum, soort en kandidaatnummer. Alleen
    als beide ontbreken, ontstaat een appbezoek met een stabiele alias voor de momentmap.
    Een datum zonder nummer of pad is nooit genoeg om twee bezoeken samen te voegen.
    """
    project = "h-architects:" + str(dossier)
    overzicht = werfregister.call("/bezoeken?" + urllib.parse.urlencode({"project": project, "limiet": 500}))
    if overzicht.get("meer"):
        raise werfregister.RegisterFout("werfapp-bezoeklijst is onvolledig; geen nieuwe bezoek-ID's aangemaakt")
    app = overzicht.get("bezoeken") or []
    pb = wb = vb = 0
    for bezoek in sorted(bezoeken, key=lambda b: (b["datum"], b["map"])):
        relatief = bezoek["map"][len(projectmap):].casefold() if bezoek["map"].startswith(projectmap + "/") else bezoek["map"].casefold()
        oud = [r.get("registratie") for r in bord_rijen
               if r.get("datum") == bezoek["datum"] and isinstance(r.get("registratie"), dict)
               and r["registratie"].get("project_ref") == project and r["registratie"].get("bezoek_id")
               and ((r.get("bezoekmap") or "").casefold() == bezoek["map"].casefold()
                    or (r.get("projectmap") and (r.get("bezoekmap") or "").casefold().startswith(r["projectmap"].casefold() + "/")
                        and r["bezoekmap"][len(r["projectmap"]):].casefold() == relatief))]
        ids = {r["bezoek_id"] for r in oud}
        if len(ids) > 1:
            raise werfregister.RegisterFout("bordrijen na verhuis verwijzen naar verschillende werfapp-bezoeken")
        soort = "plaatsbezoek" if werfstart and bezoek["datum"] < werfstart else "werfbezoek"
        if is_bevindingen(bezoek, projectmap, bevindingen, next(iter(ids), None)):
            # verslag van bevindingen: geen werfbezoek, telt niet mee in de werfverslagnummers
            soort = "overig"
            vb += 1; kandidaat = f"VB{vb}"
        elif soort == "plaatsbezoek":
            pb += 1; kandidaat = f"PB{pb}"
        else:
            wb += 1; kandidaat = str(wb)
        if ids:
            bezoek["registratie"] = dict(oud[0], bron="werfapp")
            continue
        match = [r for r in app if r.get("project_ref") == project and r.get("bezoektype") == soort
                 and str(r.get("weergave_nummer") or "") == kandidaat
                 and (not (r.get("gepland") or {}).get("dag") or r["gepland"]["dag"] == bezoek["datum"])]
        if len(match) > 1:
            raise werfregister.RegisterFout("meerdere werfapp-bezoeken voor hetzelfde bezoeknummer; geen tweede bezoek aangemaakt")
        if match:
            b = match[0]
            bezoek["registratie"] = {"bezoek_id": b["bezoek_id"], "project_ref": project, "bron": "werfapp",
                                      "status": b.get("status"), "revisie": b.get("revisie")}
            continue
        alias = "moment:" + str(dossier) + ":" + bezoek["datum"] + ":" + hashlib.sha256(relatief.encode()).hexdigest()[:20]
        inhoud = {"alias": {"systeem": "bord", "account_ref": "mijnagents", "objecttype": "werfbezoek", "externe_id": alias,
                             "weergave": {"datum": bezoek["datum"], "bezoekmap": relatief}},
                  "project_ref": project, "project_zekerheid": "zeker", "bezoektype": soort,
                  "status": "onzeker", "gepland": None}
        antwoord = werfregister.call("/bezoeken/upsert", {"schema_version": 1,
            "idempotency_key": "werfadapter:" + werfregister._hash(inhoud), **inhoud})
        b = antwoord.get("bezoek") or {}
        if not b.get("bezoek_id") or b.get("project_ref") != project:
            raise werfregister.RegisterFout("werfapp bevestigde geen bezoek-ID voor de momentmap")
        bezoek["registratie"] = {"bezoek_id": b["bezoek_id"], "project_ref": project, "bron": "werfapp",
                                  "status": b.get("status"), "revisie": b.get("revisie")}
        app.append({"bezoek_id": b["bezoek_id"], "project_ref": project, "bezoektype": soort,
                    "weergave_nummer": None, "gepland": {"dag": bezoek["datum"]}})
    return bezoeken


def rijen():
    dossiers = bord.call("/api/werfbezoek").get("dossiers", [])
    uit = []
    for dossier in dossiers:
        uit.extend(bord.call("/api/werfbezoek?dossier=" + dossier["dossier"]).get("rijen", []))
    return uit


def aansluiten(items, toepassen=False):
    """Bepaal eerst de vaste app-identiteit; het bordrijvolgnummer is alleen een adres op het bord."""
    groepen = Counter((r["dossier"], r["volgnr"]) for r in items if not r.get("stand", "").startswith("dubbel na verhuis"))
    rapport = {"versie": 1, "gemeten_utc": datetime.now(timezone.utc).isoformat(), "toegepast": toepassen,
               "aantal_bordrijen": len(items), "dossiers": sorted({r["dossier"] for r in items}),
               "ambigue_rijvolgnummers": sum(n > 1 for n in groepen.values()), "rijen": []}
    for rij in items:
        registratie = None
        if toepassen and not rij.get("stand", "").startswith("dubbel na verhuis"):
            registratie = werfregister.registreer(rij, rij["dossier"], rij["volgnr"])
        d = {"bordrij_id": rij["id"], "dossier": rij["dossier"], "rijvolgnr": rij["volgnr"],
             "bezoek_id": registratie["bezoek_id"] if registratie else (rij.get("registratie") or {}).get("bezoek_id"),
             "status": "verhuisdubbel_behouden" if rij.get("stand", "").startswith("dubbel na verhuis") else "klaar_voor_registratie",
             "dubbele_rijvolgnr": groepen[(rij["dossier"], rij["volgnr"])] > 1,
             "gegevens_behouden": bool(rij.get("gegevens")), "keuzes_behouden": bool(rij.get("keuzes")),
             "proef_behouden": bool(rij.get("proef_pad"))}
        if registratie:
            bord.call("/api/werfbezoek", {"rijen": [{"dossier": rij["dossier"], "datum": rij["datum"],
                       "bezoekmap": rij["bezoekmap"], "volgnr": rij["volgnr"], "werfbezoek_id": rij["id"],
                       "_alleen": ["registratie"], "registratie": registratie}]})
            d.update(status="geregistreerd", bezoek_id=registratie["bezoek_id"])
        rapport["rijen"].append(d)
    rapport["geregistreerd"] = sum(r["status"] == "geregistreerd" for r in rapport["rijen"])
    rapport["unieke_werfapp_bezoeken"] = len({r["bezoek_id"] for r in rapport["rijen"] if r.get("bezoek_id")})
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

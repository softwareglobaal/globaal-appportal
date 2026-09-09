#!/usr/bin/env python3
"""De Agendawacht (Privé) — leest Mehdi's agenda's en zet klaar wat anderen nodig hebben.

Elke werkdag om 06:30 en daarna elke twee uur:
  1. alle afspraken van gisteren tot en met zeven dagen vooruit;
  2. per afspraak: bij welk dossier hoort hij (H-A-code in de titel, projectnummer,
     klantnaam uit Pipedrive) en van welk soort (plaatsbezoek, kennismaking, online);
  3. klaarzetten: afspraken van vandaag en de komende week voor de afdeling
     h-architects (met deal_id als die gevonden is), en het dagplan van vandaag
     voor Mehdi ("vandaag: ..., gisteren stond er ... zonder verslag");
  4. werkverslag op het bord: wat gelezen, wat gekoppeld, wat niet.
Leest alleen. Verandert nooit een afspraak.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import agenda  # noqa: E402
import bord  # noqa: E402
import pipedrive  # noqa: E402

NAAM = "agenda-wacht"
ag = bord.Agent(NAAM)
CODES = {"HA-KB": "klant buiten (werf)", "HA-PB": "prospect buiten (plaatsbezoek)", "HA-KO": "klant online",
         "HA-PO": "prospect online", "HA-IN": "intern"}


def deals_index():
    """Open deals van H-Architects: nummer en naamdelen -> deal."""
    d = pipedrive.get("harchitects", "/deals", {"status": "open", "limit": 500})
    items = d if isinstance(d, list) else (d or {}).get("data") or []
    uit = []
    for x in items:
        titel = x.get("title", "")
        m = re.match(r"^\s*((?:26|56)\d\d)\b", titel)
        delen = {w for w in re.split(r"[^a-z0-9]+", titel.lower()) if len(w) > 2 and not w.isdigit()}
        uit.append({"id": x.get("id"), "titel": titel, "nummer": m.group(1) if m else "", "delen": delen})
    return uit


def koppel(afspraak, deals):
    t = afspraak["titel"]
    laag = t.lower()
    m = re.search(r"\b((?:26|56)\d\d)\b", t)
    if m:
        for d in deals:
            if d["nummer"] == m.group(1):
                return d, "projectnummer in de titel"
    delen = {w for w in re.split(r"[^a-z0-9]+", laag) if len(w) > 2}
    beste, score = None, 0
    for d in deals:
        s = len(d["delen"] & delen)
        if s > score:
            beste, score = d, s
    if beste and score >= 2:
        return beste, f"naam in de titel ({score} woorden)"
    return None, ""


def soort_van(titel):
    for code, oms in CODES.items():
        if code.lower() in titel.lower():
            return code, oms
    if "plaatsbezoek" in titel.lower() or "werf" in titel.lower():
        return "", "plaatsbezoek"
    return "", ""


def main():
    ag.hartslag("actief", taak="agenda lezen")
    try:
        if not agenda.beschikbaar():
            ag.hartslag("fout", taak="geen agendatoegang", detail="GOOGLE_AGENDA_* ontbreekt in ~/appportal/.env")
            return
        items = agenda.afspraken(-1, 8)
        fouten = [i for i in items if i.get("fout")]
        items = [i for i in items if not i.get("fout")]
        deals = deals_index()
        vandaag = datetime.now().date().isoformat()
        gisteren = (datetime.now().date() - timedelta(days=1)).isoformat()
        klaar, gekoppeld, los = [], 0, 0
        dagplan, gisteren_lijst = [], []
        for a in items:
            dag = a["start"][:10]
            code, oms = soort_van(a["titel"])
            deal, hoe = koppel(a, deals)
            if deal:
                gekoppeld += 1
            else:
                los += 1
            regel = f"{a['start'][11:16] if not a['hele_dag'] else 'hele dag'} {a['titel']}" + (f" ({oms})" if oms else "") + (f" · deal {deal['id']} {deal['titel']}" if deal else "")
            if dag == vandaag:
                dagplan.append(regel)
            if dag == gisteren:
                gisteren_lijst.append(regel)
            if dag >= vandaag and (deal or code):
                klaar.append({"voor": "h-architects", "soort": "afspraak", "sleutel": str(deal["id"]) if deal else "",
                              "titel": f"{dag} {regel}", "uniek": f"agenda:{a['kalender']}:{a['id']}",
                              "verwijzing": a.get("link", ""),
                              "inhoud": {"datum": dag, "start": a["start"], "einde": a["einde"], "titel": a["titel"],
                                         "locatie": a["locatie"], "deelnemers": a["deelnemers"], "code": code, "soort": oms,
                                         "deal_id": deal["id"] if deal else None, "koppeling": hoe,
                                         "omschrijving": a["omschrijving"][:800]}})
        tekst = "Vandaag:\n" + ("\n".join("- " + r for r in dagplan) or "- niets in de agenda") + \
                "\n\nGisteren (hoort een verslag of opname bij te staan):\n" + ("\n".join("- " + r for r in gisteren_lijst) or "- niets")
        klaar.append({"voor": "mehdi", "soort": "dagplan", "sleutel": vandaag, "titel": f"Dagplan {vandaag}",
                      "uniek": f"dagplan:{vandaag}", "inhoud": tekst})
        uit = ag.klaarzet(klaar)
        ag.log(f"dag {vandaag}", "bron", f"{len(items)} afspraken gelezen uit {len(agenda.kalenders())} agenda's; {gekoppeld} aan een deal gekoppeld, {los} los" + (f"; {len(fouten)} agenda's niet leesbaar" if fouten else ""),
               "\n".join(f"{a['start'][:16]} {a['titel']}" for a in items))
        ag.log(f"dag {vandaag}", "schrijf", f"klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend", tekst)
        ag.log_verstuur()
        ag.hartslag("waakt", taak="agenda in het oog", detail=f"vandaag {len(dagplan)} afspraken; {gekoppeld} gekoppeld aan een deal, {los} zonder")
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()

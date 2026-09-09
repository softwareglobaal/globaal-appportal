#!/usr/bin/env python3
"""De Dagbundelaar (Privé) — legt per dag samen wat de bronnen-agents klaarzetten,
zegt per bundel bij welk dossier het hoort, en geeft het door.

Elke werkdag om 07:00 (voor gisteren) en op verzoek:
  1. alles wat klaargezet is met gisteren als dag: afspraken, transcripten, opnames,
     later ook locatie en foto's;
  2. per dossier (deal) één bundel: wat er gebeurde, welke bronnen erbij horen,
     wat ontbreekt (afspraak zonder opname, opname zonder dossier);
  3. de bundels klaarzetten voor de afdeling (h-architects) en het dagverslag voor Mehdi;
  4. wat om een keuze vraagt (bij welk dossier hoort dit?) gaat als vraag naar het bord.
Leest het bord; schrijft alleen op het bord. Verplaatst niets vóór Mehdi's ja.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402

NAAM = "dagbundelaar"
ag = bord.Agent(NAAM)
DAG = None
for i, a in enumerate(sys.argv):
    if a == "--dag" and i + 1 < len(sys.argv):
        DAG = sys.argv[i + 1]
DAG = DAG or (datetime.now().date() - timedelta(days=1)).isoformat()


def main():
    ag.hartslag("actief", taak=f"bundelt {DAG}")
    try:
        items = bord.call(f"/api/klaarzet?status=alle&n=500").get("items", [])
        van_dag = []
        for it in items:
            inhoud = it.get("inhoud") or ""
            try:
                d = json.loads(inhoud) if inhoud.startswith("{") else {}
            except ValueError:
                d = {}
            dag = (d.get("datum") or d.get("start") or it.get("sleutel") or "")[:10]
            if it.get("soort") in ("dagplan", "dagbundel", "signaal"):
                continue
            if it.get("soort") == "locatie" or it.get("van") == "locatie-wacht":
                continue  # het bewegingslogboek is alleen voor Mehdi; nooit in een bundel voor een afdeling
            if dag == DAG or (it.get("soort") == "transcript" and (d.get("start") or "")[:10] == DAG):
                it["_d"] = d
                van_dag.append(it)
        per_deal = defaultdict(list)
        for it in van_dag:
            per_deal[it.get("sleutel") or "(zonder dossier)"].append(it)
        bundels, vragen = [], []
        for sleutel, lijst in per_deal.items():
            soorten = defaultdict(int)
            for it in lijst:
                soorten[it["soort"]] += 1
            afspraken = [it for it in lijst if it["soort"] == "afspraak"]
            transcripten = [it for it in lijst if it["soort"] == "transcript"]
            ontbreekt = []
            if afspraken and not transcripten:
                ontbreekt.append("afspraak zonder opname of transcript")
            if sleutel == "(zonder dossier)":
                ontbreekt.append("bronnen zonder dossier: Mehdi wijst ze toe")
                vragen += [it["titel"] for it in lijst]
            regels = [f"- {it['soort']}: {it['titel']}" + (f" ({it['verwijzing']})" if it.get("verwijzing") else "") for it in lijst]
            tekst = f"Dossier {sleutel} op {DAG}: " + ", ".join(f"{n} {s}" for s, n in soorten.items()) + "\n" + "\n".join(regels) + \
                    ("\nOntbreekt: " + "; ".join(ontbreekt) if ontbreekt else "")
            bundels.append({"voor": "h-architects" if sleutel != "(zonder dossier)" else "mehdi", "soort": "dagbundel",
                            "sleutel": sleutel if sleutel != "(zonder dossier)" else DAG,
                            "titel": f"Bundel {DAG} · {sleutel}", "uniek": f"bundel:{DAG}:{sleutel}", "inhoud": tekst})
        verslag = f"Dagverslag {DAG}: {len(van_dag)} bronnen in {len(per_deal)} bundel(s)." + \
                  ("\nToe te wijzen: " + "; ".join(vragen) if vragen else "")
        bundels.append({"voor": "mehdi", "soort": "dagbundel", "sleutel": DAG, "titel": f"Dagverslag {DAG}",
                        "uniek": f"dagverslag:{DAG}", "inhoud": verslag + "\n\n" + "\n\n".join(b["inhoud"] for b in bundels)})
        uit = ag.klaarzet(bundels)
        # Wat in een bundel zit, is door de laag verwerkt: opgepakt markeren, zodat de bak
        # niet blijft groeien. Een afdelingsagent leest de bundel (met sleutel) verder.
        opgepakt = 0
        for it in van_dag:
            if it.get("status") == "klaar":
                try:
                    bord.opgepakt(it["id"], NAAM); opgepakt += 1
                except Exception:  # noqa: BLE001
                    pass
        ag.log(f"dag {DAG}", "bevinding", f"{len(van_dag)} klaargezette bronnen, {len(per_deal)} bundel(s), {len(vragen)} toe te wijzen", verslag)
        ag.log(f"dag {DAG}", "schrijf", f"bundels klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend; {opgepakt} bronnen als opgepakt gemarkeerd")
        ag.log_verstuur()
        ag.hartslag("klaar" if van_dag else "waakt", taak=f"dag {DAG} gebundeld", detail=f"{len(per_deal)} bundel(s), {len(vragen)} toe te wijzen")
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()

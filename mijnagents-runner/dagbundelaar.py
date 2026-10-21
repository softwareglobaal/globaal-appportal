#!/usr/bin/env python3
"""De Dagbundelaar (Privé): legt per dag samen wat de bronnen-agents klaarzetten,
zegt per bundel bij welk dossier het hoort, en geeft het door.

Elke werkdag om 07:05 UTC (voor gisteren), na de gesprekkenketen: de cron start me binnen
/tmp/gesprekken.lock (planning/gesprekken.cron); krijg ik het slot niet binnen 90 minuten, dan
start ik niet en staat dat in dagbundelaar.log (RZ2-03). 90 minuten is langer dan de keten kan duren (RZ3-03, tot
22-10-2026 was het 60; tests/test_keten.py rekent het na). Op verzoek (--dag JJJJ-MM-DD):
  1. alles wat klaargezet is met gisteren als dag: afspraken, transcripten, opnames,
     later ook locatie en foto's;
  2. per dossier (deal) één bundel: wat er gebeurde, welke bronnen erbij horen,
     wat ontbreekt (afspraak zonder opname, opname zonder dossier);
  3. de bundels klaarzetten voor de afdeling (h-architects) en het dagverslag voor Mehdi;
  4. wat om een keuze vraagt (bij welk dossier hoort dit?) gaat als vraag naar het bord.
Leest het bord; schrijft alleen op het bord. Verplaatst niets vóór Mehdi's ja.

De Zoom-dagregel en het lek naar de afdeling (ontwerp regie-zoom v1.2, Z14 en J14):
  - de dagregel van De Zoomwacht (soort zoom) komt niet in een bundel, maar als regel
    "Zoom: <titel>" in het Dagverslag; ontbreekt ze, dan zegt het Dagverslag dat;
  - een dagregel van de zes dagen ervoor die (weer) op klaar staat, nagekomen of herzien,
    komt onder "Nagekomen of herzien" en wordt daarna opgepakt: zo komen ook vrijdag en
    zaterdag op maandag mee;
  - zoom-tekst (voor De Regisseur) en het ochtendbericht bundel ik nooit;
  - een sleutel is alleen een dossier als hij niet leeg is en geen datum (JJJJ-MM-DD);
    een item voor mehdi gaat in een bundel voor mehdi (uniek bundel:<dag>:<sleutel>:mehdi),
    zodat een bundel voor h-architects nooit een item voor Mehdi of zonder dossier bevat.
Van een privé-item (inhoud.prive, PRIVÉ in de titel, of inhoud.afdeling prive: RZ3-01) zet ik alleen
"privégesprek, N min" in de bundel, het Dagverslag en mijn werkverslag (RZ2-01), zonder verwijzing, en nooit in een
bundel voor een afdeling.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import locatiecontext as LC  # noqa: E402  dagboek voor precies de dag, met startgrens (opdracht v1.4)

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
        # main staat op zichzelf, zonder hulpfuncties op moduleniveau: tests/test_locatielezers.py voert alleen deze
        # functie uit, met een nagebootst bord.
        from datetime import date, timedelta

        def is_datum(s):
            try:
                return len(s) == 10 and bool(date.fromisoformat(s))
            except ValueError:
                return False

        def prive(it):
            # RZ3-01: ook afdeling prive is privé, zoals de dossierbeslissing (plaud/dossier.py) het zegt, ook bij
            # prive=false; zo'n item van voor 22-10-2026 droeg naam en onderwerp in titel en verwijzing, zonder PRIVÉ
            d = it.get("_d") or {}
            return (bool(d.get("prive")) or "PRIVÉ" in (it.get("titel") or "")
                    or str(d.get("afdeling") or "").strip().lower() in ("prive", "privé"))

        def naam_van(it):
            """RZ2-01: van een privé-item alleen 'privégesprek, N min', in de bundel, het Dagverslag en het werkverslag; met
            wie en waarover staan in het archief op de VM. Ook voor een item van voor 21-10-2026, dat de persoon en het
            onderwerp nog in de titel en de verwijzing droeg. Zonder minuten: duur onbekend, nooit 0."""
            if not prive(it):
                return it["titel"]
            n = (it.get("_d") or {}).get("minuten")
            return "privégesprek, " + (f"{n} min" if isinstance(n, int) and not isinstance(n, bool) else "duur onbekend")

        items = bord.call(f"/api/klaarzet?status=alle&n=500").get("items", [])
        # Z14: de Zoom-dagregels per soort lezen; n=500 over de hele bak dekt minder dan een week
        zoomlezing = bord.call("/api/klaarzet?status=klaar&soort=zoom&n=50").get("items", [])
        van_dag, zoom_dag, nagekomen, gezien = [], [], [], set()
        eerste = (date.fromisoformat(DAG) - timedelta(days=6)).isoformat()
        for it in items + [z for z in zoomlezing if z.get("soort") == "zoom"]:
            if it.get("id") is not None:
                if it["id"] in gezien:
                    continue
                gezien.add(it["id"])
            inhoud = it.get("inhoud") or ""
            try:
                d = json.loads(inhoud) if inhoud.startswith("{") else {}
            except ValueError:
                d = {}
            dag = (d.get("datum") or d.get("start") or it.get("sleutel") or "")[:10]
            if it.get("soort") in ("dagplan", "dagbundel", "signaal", "oproep", "zoom-tekst", "ochtendbericht"):
                continue  # zoom-tekst is voor De Regisseur, het ochtendbericht voor De Bode (I2, Z14)
            if "mail-regisseur" in (it.get("van"), it.get("voor")):
                continue  # mail volgt De Mailregisseur op; tot 19-10-2026 haalde ik hier elke nacht opvolgpunten weg (37 stuks)
            if it.get("soort") == "locatie" or it.get("van") == "locatie-wacht":
                continue  # het bewegingslogboek is alleen voor Mehdi; nooit in een bundel voor een afdeling
            if it.get("soort") == "zoom":
                # De dagregel van De Zoomwacht: een regel in het Dagverslag, nooit een bundel. Nagekomen of herzien
                # (weer op klaar) en van de zes dagen ervoor: ook mee, zo komen vrijdag en zaterdag op maandag mee.
                if dag == DAG:
                    zoom_dag.append(it)
                elif eerste <= dag < DAG and it.get("status") == "klaar":
                    nagekomen.append(it)
                continue
            if dag == DAG or (it.get("soort") == "transcript" and (d.get("start") or "")[:10] == DAG):
                it["_d"] = d
                van_dag.append(it)
        # Een sleutel is alleen een dossier als hij niet leeg is en geen datum: tot 21-10-2026 kwamen zo 31 bundels voor
        # h-architects met een datum als dossier (gezondheid, coaching, mail en de Zoom-dagregel). Een item voor mehdi
        # gaat in een bundel voor mehdi met dezelfde sleutel; alleen een bundel met een dossier en zonder item voor
        # mehdi gaat naar h-architects.
        per_deal = defaultdict(list)
        for it in van_dag:
            sleutel = (it.get("sleutel") or "").strip()
            dossier = sleutel if sleutel and not is_datum(sleutel) else "(zonder dossier)"
            # RZ3-01: een privé-item gaat nooit in een bundel voor een afdeling, ook niet als het voor een afdeling klaarstond
            per_deal[(dossier, dossier != "(zonder dossier)" and (it.get("voor") == "mehdi" or prive(it)))].append(it)
        bundels, vragen = [], []
        for (sleutel, voor_mehdi), lijst in per_deal.items():
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
                vragen += [naam_van(it) for it in lijst]
            regels = [f"- {it['soort']}: {naam_van(it)}" + (f" ({it['verwijzing']})" if it.get("verwijzing") and not prive(it) else "")
                      for it in lijst]
            tekst = f"Dossier {sleutel} op {DAG}: " + ", ".join(f"{n} {s}" for s, n in soorten.items()) + "\n" + "\n".join(regels) + \
                    ("\nOntbreekt: " + "; ".join(ontbreekt) if ontbreekt else "")
            if sleutel == "(zonder dossier)":
                bundels.append({"voor": "mehdi", "soort": "dagbundel", "sleutel": DAG,
                                "titel": f"Bundel {DAG} · {sleutel}", "uniek": f"bundel:{DAG}:{sleutel}", "inhoud": tekst})
            elif voor_mehdi:
                # J14: een eigen uniek, anders overschrijft de bundel voor h-architects met dezelfde sleutel deze
                bundels.append({"voor": "mehdi", "soort": "dagbundel", "sleutel": sleutel,
                                "titel": f"Bundel {DAG} · {sleutel} · voor Mehdi", "uniek": f"bundel:{DAG}:{sleutel}:mehdi", "inhoud": tekst})
            else:
                bundels.append({"voor": "h-architects", "soort": "dagbundel", "sleutel": sleutel,
                                "titel": f"Bundel {DAG} · {sleutel}", "uniek": f"bundel:{DAG}:{sleutel}", "inhoud": tekst})
        zoomregels = [f"Zoom: {it['titel']}" for it in zoom_dag] or ["Zoom: dagregel ontbreekt (Zoomwacht niet klaar)"]
        if nagekomen:
            zoomregels.append("Nagekomen of herzien:")
            zoomregels += [f"- Zoom: {it['titel']}" for it in sorted(nagekomen, key=lambda x: x.get("uniek") or "")]
        verslag = f"Dagverslag {DAG}: {len(van_dag)} bronnen in {len(per_deal)} bundel(s)." + "\n" + "\n".join(zoomregels) + \
                  ("\nToe te wijzen: " + "; ".join(vragen) if vragen else "")
        bundels.append({"voor": "mehdi", "soort": "dagbundel", "sleutel": DAG, "titel": f"Dagverslag {DAG}",
                        "uniek": f"dagverslag:{DAG}", "inhoud": verslag + "\n\n" + "\n\n".join(b["inhoud"] for b in bundels)})
        uit = ag.klaarzet(bundels)
        # Wat in een bundel of in het Dagverslag zit, is door de laag verwerkt: opgepakt markeren, zodat de bak
        # niet blijft groeien. Een afdelingsagent leest de bundel (met sleutel) verder.
        opgepakt = 0
        for it in van_dag + zoom_dag + nagekomen:
            if it.get("status") == "klaar":
                try:
                    bord.opgepakt(it["id"], NAAM); opgepakt += 1
                except Exception:  # noqa: BLE001
                    pass
        ag.log(f"dag {DAG}", "bevinding", f"{len(van_dag)} klaargezette bronnen, {len(per_deal)} bundel(s), {len(vragen)} toe te wijzen; "
               f"Zoom-dagregel {'gevonden' if zoom_dag else 'ontbreekt'}, {len(nagekomen)} nagekomen of herzien", verslag)
        ag.log(f"dag {DAG}", "schrijf", f"bundels klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend; {opgepakt} bronnen als opgepakt gemarkeerd")
        ag.log_verstuur()
        # Werkwijze stap 8: welke bronnen ontbraken, en wat ik nodig heb om ze te krijgen.
        # Een locatiedagboek telt alleen voor precies deze dag en uit de actieve reeks. Tot 05-10-2026
        # telde elk locatie-item, ook een oud telefoondagboek, en verborg zo een ontbrekend dagboek.
        soorten = {it.get("soort") for it in items if (it.get("sleutel") or "")[:10] == DAG and it.get("soort") != "locatie"}
        if LC.dag_heeft_dagboek(DAG, items):
            soorten.add("locatie")
        nood = []
        for soort, tekst, wie in (("gezondheid", "Apple Watch-gegevens (Gezondheidswacht op de Mac: Health Auto Export en iCloud moeten lopen)", "mehdi"),
                                  ("foto", "Foto's van de dag (iCloud-wacht op de Mac moet om 21:15 gedraaid hebben)", "mehdi"),
                                  ("locatie", "Locatiedagboek (Locatiewacht 21:30; tracker aan?)", "mehdi")):
            if soort not in soorten:
                nood.append({"tekst": f"Voor {DAG} geen {tekst}", "wie": wie})
        nood += [{"tekst": "WhatsApp: geen bron; een chat-export per gesprek in een map op de Mac is de enige weg, Mehdi kiest welke", "wie": "mehdi"},
                 {"tekst": "Telefoon (Xelion): koppeling bestaat, de belwacht-agent nog niet", "wie": "claude-code"},
                 {"tekst": "Plaud-opnames komen pas als de Plaud-routine op claude.ai draait", "wie": "mehdi"}]
        ag.hartslag("klaar" if van_dag else "waakt", taak=f"dag {DAG} gebundeld", detail=f"{len(per_deal)} bundel(s), {len(vragen)} toe te wijzen", nood=nood)
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()

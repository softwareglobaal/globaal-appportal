#!/usr/bin/env python3
"""Werfverslag schrijver (H-Architects) — schrijft de voorbereiding en de proef van een werfverslag.

Hij werkt op een getypeerde opdracht van de bezoekpagina of een bevoegd commandlineverzoek.
Hij claimt de vaste bezoekrij en controleert haar invoer voor iedere betaalde stap. Hij leest de bezoekmap, haalt de
gegevens eruit met bron en zekerheid, en schrijft het concept in het eigen sjabloon (Word + markdown)
in de bezoekmap. Hij verstuurt nooit en overschrijft nooit.

Gebruik:
    werfverslag_schrijver.py --opdrachten          # cron elke 5 min: opdrachten uit de bak uitvoeren
    werfverslag_schrijver.py --voorbereid 2309 1   # handmatig
    werfverslag_schrijver.py --proef 2309 1
    werfverslag_schrijver.py --naar-werfapp 2309 1   # bestaande proef als concept in de werfapp, zonder Claude
"""
import argparse
import os
import re
import sys
import urllib.error

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import werfverslag_proef as wp  # noqa: E402

NAAM = "werfverslag-schrijver"
ag = bord.Agent(NAAM)


def opdrachten(alleen_id=None):
    items = bord.call("/api/werfopdrachten?status=klaar&n=30").get("opdrachten", [])
    if alleen_id is not None:
        items = [it for it in items if it.get("id") == alleen_id]
    if not items:
        ag.hartslag("waakt", taak="wacht op opdrachten", detail="van Werfverslag voorbereider of van de bezoekpagina")
        return 0
    ag.hartslag("actief", taak=f"{len(items)} opdracht(en)")
    gedaan, fouten = 0, 0
    for it in reversed(items):
        soort, d, n = it.get("soort"), str(it.get("dossier") or ""), it.get("volgnr")
        # Alleen de getypeerde, door het bord geautoriseerde werfwerkvoorraad.
        # Vrije titels of 'van'-teksten zijn geen identiteit of mandaat.
        if soort not in ("voorbereid", "proef") or not re.fullmatch(r"\d{4}", d) or not isinstance(n, int) or n < 1:
            ag.log(str(it.get("id", "?")), "besluit", "ongeldige getypeerde werfopdracht; niet uitgevoerd")
            continue
        try:
            claim = bord.call(f"/api/werfopdrachten/{it['id']}/claim", {"door": NAAM, "lease_seconden": 3600})
        except urllib.error.HTTPError as e:
            if e.code == 409:
                continue  # een andere worker of inmiddels gewijzigde context
            raise
        if not claim.get("geclaimd"):
            continue
        lease = claim["lease_token"]
        opdracht = claim["opdracht"]
        try:
            with wp.opdrachtcontext(opdracht, lease):
                uit = wp.voorbereid(ag, d, n) if soort == "voorbereid" else wp.proef(ag, d, n)
            bewijs = (f"Voorbereiding bewaard voor {d}-{n}" if soort == "voorbereid" else f"Proef bewaard voor {d}-{n}")
            verwerking = uit.get("_verwerking", {}) if isinstance(uit, dict) else {}
            bord.call(f"/api/werfopdrachten/{it['id']}/resultaat", {"lease_token": lease, "status": "gelukt", "bewijs": bewijs,
                                                                   "veilig_opnieuw": False, "verwerking": verwerking})
            gedaan += 1
        except Exception as e:  # noqa: BLE001
            fouten += 1
            budget = isinstance(e, getattr(wp.register, "WachtBudget", ()))
            veilig = isinstance(e, wp.extractie.BronLeesFout) or bool(getattr(e, "veilig_opnieuw", False))
            bekend = isinstance(e, (wp.ModelAntwoordFout, wp.extractie.BronLeesFout, ValueError)) or veilig
            status = "uitgesteld" if budget else "fout" if bekend else "onbekend"
            # Geen ruwe providerexception loggen; die kan requestinhoud bevatten.
            bewijs = f"{soort} {d}-{n}: {type(e).__name__}; " + (str(e)[:200] if bekend else "uitkomst moet worden nagekeken; geen automatische herhaling")
            ag.log(f"{d}-{n}", "fout", bewijs)
            try:
                melding = {"lease_token": lease, "status": status, "bewijs": bewijs, "veilig_opnieuw": veilig}
                if budget:
                    melding["hervat_utc"] = e.hervat_utc
                bord.call(f"/api/werfopdrachten/{it['id']}/resultaat", melding)
            except Exception:
                ag.log(f"{d}-{n}", "fout", "resultaatmelding niet bevestigd; lease blijft zichtbaar voor herstel")
        ag.log_verstuur()
    ag.hartslag("klaar" if not fouten else "fout", taak=f"{gedaan} opdracht(en) uitgevoerd, {fouten} mislukt",
                detail="voorbereiding of proef; bewijs in het werkverslag en op de bezoekpagina")
    return gedaan


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--opdrachten", action="store_true")
    p.add_argument("--voorbereid", nargs=2, metavar=("DOSSIER", "BEZOEK"))
    p.add_argument("--proef", nargs=2, metavar=("DOSSIER", "BEZOEK"))
    p.add_argument("--herlayout", nargs=2, metavar=("DOSSIER", "BEZOEK"), help="Word opnieuw opmaken uit de bewaarde proef, zonder Claude")
    p.add_argument("--naar-werfapp", nargs=2, metavar=("DOSSIER", "BEZOEK"),
                   help="een bestaande proef als concept in de werfapp zetten, zonder Claude (geen tokens); een bestaand concept blijft")
    a = p.parse_args()
    if a.opdrachten:
        print("opdrachten:", opdrachten())
        return
    if a.herlayout:
        d, n = a.herlayout
        ag.hartslag("actief", taak=f"nieuwe opmaak {d}-{n}")
        try:
            print(wp.herlayout(ag, d, int(n)))
            ag.hartslag("klaar", taak=f"nieuwe opmaak {d}-{n} klaar")
        finally:
            ag.log_verstuur()
        return
    if a.naar_werfapp:
        d, n = a.naar_werfapp
        ag.hartslag("actief", taak=f"concept in de werfapp {d}-{n}")
        try:
            print(wp.werfapp_uit_proef(ag, d, int(n)))
            ag.hartslag("klaar", taak=f"concept in de werfapp {d}-{n}")
        finally:
            ag.log_verstuur()
        return
    if a.voorbereid or a.proef:
        d, n = a.voorbereid or a.proef
        soort = "voorbereid" if a.voorbereid else "proef"
        antwoord = bord.call("/api/werfopdrachten/aanvragen", {"dossier": d, "volgnr": int(n), "soort": soort, "bron": "commandline"})
        opdracht = antwoord["opdracht"]
        if opdracht["status"] == "klaar":
            print("opdrachten uitgevoerd:", opdrachten(alleen_id=opdracht["id"]))
        else:
            print(f"opdracht {opdracht['id']}: {opdracht['status']}; stand en herstel op de bezoekpagina")
        return
    p.print_help()


if __name__ == "__main__":
    main()

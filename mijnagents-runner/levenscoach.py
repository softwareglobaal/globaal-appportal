#!/usr/bin/env python3
"""De Levenscoach (Privé, alleen voor Mehdi) — legt per dag alles over Mehdi samen
en maakt de dagspiegel; op maandag de weekspiegel. Werkwijze op het bord
(werkwijze/levenscoach.md is het zaad).

Elke ochtend 06:45 (--dag JJJJ-MM-DD voor een andere dag; --week voor de weekspiegel).
Leest alleen het bord (klaargezet voor Mehdi, gesprekkentabel, gesprekken met hem).
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402

NAAM = "levenscoach"
ag = bord.Agent(NAAM)
MODEL = os.environ.get("LEVENSCOACH_MODEL", "claude-opus-5")
WEEK = "--week" in sys.argv
DAG = None
for i, a in enumerate(sys.argv):
    if a == "--dag" and i + 1 < len(sys.argv):
        DAG = sys.argv[i + 1]
DAG = DAG or (datetime.now().date() - timedelta(days=1)).isoformat()


def laad_env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


laad_env("~/agents/.env")


def bronnen_van(dagen):
    """Alles wat voor Mehdi klaargezet is met een van deze dagen als sleutel of datum."""
    items = bord.call("/api/klaarzet?voor=mehdi&status=alle&n=500").get("items", [])
    uit = {d: [] for d in dagen}
    for it in items:
        inhoud = it.get("inhoud") or ""
        try:
            d = json.loads(inhoud) if inhoud.startswith("{") else {}
        except ValueError:
            d = {}
        dag = (d.get("datum") or d.get("start") or it.get("sleutel") or "")[:10]
        if dag in uit and it.get("soort") not in ("coaching", "verslag"):
            uit[dag].append({"van": it["van"], "soort": it["soort"], "titel": it["titel"],
                             "inhoud": (inhoud[:12000] if it["soort"] in ("locatie", "dagplan", "gezondheid", "dagbundel") else inhoud[:3000])})
    return uit


def gesprekken_van(dagen):
    # via de gesprekkentabel: alleen leesbaar voor beheer op de pagina; hier via de bak (transcript-items) al meegenomen
    return []


def gemeld_door_mehdi(dagen):
    """Wat Mehdi zelf tegen mij (of De Regisseur) zei in die dagen."""
    uit = []
    for aan in (NAAM, "regisseur"):
        try:
            for g in bord.call(f"/api/gesprek/open").get("open", []):
                pass
        except Exception:  # noqa: BLE001
            pass
    return uit


def spiegel(dagen, bronnen, werkwijze, week=False):
    from anthropic import Anthropic
    client = Anthropic()
    system = ("Je bent De Levenscoach van Mehdi Chegini. Nederlands, geen emoji, geen kastlijntjes, warm maar nuchter; "
              "feiten met bron (welke agent, welk tijdstip), geen oordeel zonder meting, geen medische uitspraken. "
              "Je schrijft alleen voor Mehdi zelf.\n\n=== JOUW WERKWIJZE ===\n" + werkwijze)
    if week:
        opdracht = ("Maak de WEEKSPIEGEL over deze zeven dagen: '## Hoe de week liep' (per dag één regel), "
                    "'## Patronen' (drie tot vijf, elk met de metingen erbij), '## Plan tegenover werkelijkheid', "
                    "'## Lichaam' (slaap, hartslag, beweging, als er gegevens zijn; anders zeg dat), "
                    "'## Drie punten voor komende week', '## Wat ik mis' (bronnen die ontbraken). Maximaal 700 woorden.")
    else:
        opdracht = ("Maak de DAGSPIEGEL van deze dag: '## Zo liep de dag' (tijdlijn: waar, met wie, hoe lang, uit de bronnen), "
                    "'## Gepland tegenover gebeurd', '## Lichaam' (als er gegevens zijn; anders één zin dat ze ontbreken), "
                    "'## Wat opvalt' (één observatie), '## Eén suggestie' (klein en concreet, voor morgen), "
                    "'## Wat ik mis' (welke bron ontbrak of stil was). Maximaal 450 woorden.")
    user = opdracht + "\n\n=== BRONNEN ===\n" + json.dumps(bronnen, ensure_ascii=False)[:180000]
    resp = client.messages.create(model=MODEL, max_tokens=3000, system=system, messages=[{"role": "user", "content": user}])
    tekst = "".join(getattr(b, "text", "") for b in resp.content).strip()
    tokens = (getattr(resp.usage, "input_tokens", 0) or 0) + (getattr(resp.usage, "output_tokens", 0) or 0)
    return tekst, tokens


def main():
    ag.hartslag("actief", taak=f"{'weekspiegel' if WEEK else 'dagspiegel'} {DAG}")
    try:
        werkwijze = ag.werkwijze()
        dagen = [(datetime.fromisoformat(DAG).date() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)] if WEEK else [DAG]
        bronnen = bronnen_van(dagen)
        aantal = sum(len(v) for v in bronnen.values())
        soorten = sorted({it["soort"] for v in bronnen.values() for it in v})
        ontbreekt = [s for s in ("locatie", "dagplan", "gezondheid", "foto") if s not in soorten]
        tekst, tokens = spiegel(dagen, bronnen, werkwijze, WEEK)
        sleutel = f"week-{DAG}" if WEEK else DAG
        uit = ag.klaarzet([{"voor": "mehdi", "soort": "coaching", "sleutel": sleutel,
                            "titel": ("Weekspiegel tot " if WEEK else "Dagspiegel ") + DAG,
                            "uniek": f"coaching:{sleutel}:{datetime.now().strftime('%d%H%M')}", "inhoud": tekst}])
        nood = []
        if "gezondheid" in ontbreekt:
            nood.append({"tekst": "Gezondheidsgegevens van de Apple Watch komen nog niet op het bord (Gezondheidswacht op de Mac)", "wie": "mehdi"})
        if "locatie" in ontbreekt:
            nood.append({"tekst": f"Geen locatiedagboek voor {DAG}", "wie": "claude-code"})
        ag.log(f"dag {DAG}", "bron", f"{aantal} bronnen over {len(dagen)} dag(en): {', '.join(soorten) or 'geen'}; ontbreekt: {', '.join(ontbreekt) or 'niets'}")
        ag.log(f"dag {DAG}", "melding", f"{'weekspiegel' if WEEK else 'dagspiegel'} klaargezet ({tokens} tokens)", tekst)
        ag.log_verstuur()
        ag.hartslag("klaar", taak=f"{'weekspiegel' if WEEK else 'dagspiegel'} {DAG} klaar", detail=f"{aantal} bronnen; mist: {', '.join(ontbreekt) or 'niets'}", nood=nood)
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()

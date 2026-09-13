#!/usr/bin/env python3
"""De Licentiewacht (Organisatie): hoofdagent voor abonnementen, gebruik en kosten van de groep.
Leest de boekhouding (Visa-uitgavenstaten en Octopus-facturen per firma) en de gebruiksmeldingen
van de dienst-agents (nu: De Wispr-wacht), en schrijft het overzicht naar
mijnagents-data/export/Licentiewacht/ (komt via de Mac in Data uit Mehdi). Adviseert; voert niets uit.
Gebruik: licentiewacht.py [--maanden N]   (standaard 12)
"""
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import boekhouding  # noqa: E402
import bord  # noqa: E402

DB = os.path.expanduser("~/appportal/mijnagents-data/mijnagents.db")
UIT = os.path.expanduser("~/appportal/mijnagents-data/export/Licentiewacht")
MAANDEN = 12
if "--maanden" in sys.argv:
    MAANDEN = int(sys.argv[sys.argv.index("--maanden") + 1])
ag = bord.Agent("licentiewacht")
# dezelfde dienst onder verschillende namen in kaartlijnen en facturen
DIENST = [("wispr", "Wispr Flow"), ("anthropic|claude", "Claude (Anthropic)"), ("openai|chatgpt", "OpenAI / ChatGPT"), ("google ads", "Google Ads"),
          ("google", "Google Workspace / One"), ("microsoft", "Microsoft 365"), ("monday", "Monday.com"), ("pipedrive", "Pipedrive"), ("zoom", "Zoom"),
          ("calendly", "Calendly"), ("dropbox", "Dropbox"), ("xelion", "Xelion"), ("apple", "Apple (App Store / iCloud)"), ("plaud", "Plaud"),
          ("fathom", "Fathom"), ("elevenlabs", "ElevenLabs"), ("adobe", "Adobe"), ("notion", "Notion"), ("canva", "Canva"), ("github", "GitHub"),
          ("cursor", "Cursor"), ("perplexity", "Perplexity"), ("openrouter", "OpenRouter"), ("replit", "Replit"), ("runway", "Runway"),
          ("surfer", "SurferSEO"), ("tactiq", "Tactiq"), ("grok|xai", "Grok (xAI)"), ("granola", "Granola"), ("slack", "Slack"), ("figma", "Figma"),
          ("autodesk", "Autodesk"), ("vectorworks", "Vectorworks"), ("docusign", "DocuSign"), ("pandadoc", "PandaDoc"), ("linkedin", "LinkedIn"),
          ("meta|facebook|instagram", "Meta (Facebook/Instagram)"), ("twilio", "Twilio"), ("cloudflare", "Cloudflare"), ("hetzner", "Hetzner"), ("ovh", "OVH")]


def dienst_van(*teksten):
    t = " ".join(x or "" for x in teksten).lower()
    for patroon, naam in DIENST:
        if re.search(patroon, t):
            return naam
    return (teksten[0] or "onbekend").strip()[:40]


def maand(d):
    return str(d)[:7]


def gebruik_uit_bord():
    """Meldingen van de dienst-agents (klaarzet soort 'gebruik'): laatste per dienst en gebruiker."""
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    laatste = {}
    for r in c.execute("select van, sleutel, inhoud, ts from klaarzet where soort='gebruik' order by ts"):
        try:
            d = json.loads(r["inhoud"])
        except ValueError:
            continue
        laatste[(d.get("dienst", r["van"]), d.get("gebruiker", r["sleutel"]))] = d
    return laatste


def main():
    ag.hartslag("actief", taak="abonnementen en kosten lezen")
    nood = []
    try:
        sinds = (date.today().replace(day=1) - timedelta(days=31 * MAANDEN)).replace(day=1).isoformat()
        kaart = boekhouding.kaartlijnen(sinds)
        fact = boekhouding.facturen(sinds)
        staat = {r["firma"]: r["tot"] for r in boekhouding.laatste_uitgavenstaat()}
        gebruik = gebruik_uit_bord()
        # samenvoegen: (firma, dienst) -> maand -> bedrag ; kaartlijnen negatief = uitgave
        per = defaultdict(lambda: defaultdict(float))
        laatste = {}
        aantal = defaultdict(int)
        bronnen = defaultdict(set)
        for r in kaart:
            d = dienst_van(r["vendor"], r["omschrijving"])
            k = (r["firma"], d)
            per[k][maand(r["datum"])] += -float(r["bedrag"] or 0)
            laatste[k] = max(laatste.get(k, ""), r["datum"])
            aantal[k] += 1
            bronnen[k].add("Visa")
        for r in fact:
            d = dienst_van(r["leverancier"], r["omschrijving"])
            k = (r["firma"] or "?", d)
            per[k][maand(r["datum"])] += float(r["bedrag"] or 0)
            laatste[k] = max(laatste.get(k, ""), r["datum"])
            aantal[k] += 1
            bronnen[k].add("factuur")
        maanden = sorted({m for v in per.values() for m in v})[-MAANDEN:]
        vandaag = date.today()
        rijen = []
        for (firma, dienst), mnd in per.items():
            tot = sum(v for m, v in mnd.items() if m in maanden)
            actieve = [m for m in maanden if mnd.get(m, 0) > 0]
            gem = tot / max(len(actieve), 1)
            # ouderdom tegenover de jongste geboekte lijn van die firma, niet tegenover vandaag: de staten lopen achter
            peil = date.fromisoformat(staat.get(firma) or vandaag.isoformat())
            oud = (max(peil, date.fromisoformat(laatste[(firma, dienst)])) - date.fromisoformat(laatste[(firma, dienst)])).days
            status = "loopt" if oud <= 45 else ("mogelijk gestopt" if oud <= 120 else "gestopt of niet meer geboekt")
            rijen.append({"firma": firma, "dienst": dienst, "totaal": round(tot, 2), "per_maand": round(gem, 2), "maanden_actief": len(actieve),
                          "laatste": laatste[(firma, dienst)], "dagen_geleden": oud, "status": status, "bron": "+".join(sorted(bronnen[(firma, dienst)])),
                          "reeks": {m: round(mnd.get(m, 0), 2) for m in maanden}})
        rijen.sort(key=lambda r: (-r["totaal"]))
        # dubbel: dezelfde dienst bij meerdere firma's
        per_dienst = defaultdict(list)
        for r in rijen:
            per_dienst[r["dienst"]].append(r)
        dubbel = {d: v for d, v in per_dienst.items() if len(v) > 1}
        # gebruik naast kosten
        gebruik_regels = []
        for (dienst, gebruiker), g in sorted(gebruik.items()):
            kost = [r for r in rijen if r["dienst"].lower().startswith(dienst.lower()[:5])]
            gebruik_regels.append((dienst, gebruiker, g.get("week_woorden", g.get("week", "")), g.get("oordeel", ""), g.get("stand", ""),
                                   ", ".join(f"{r['firma']} {r['per_maand']:.0f}/mnd" for r in kost) or "geen kost gevonden in Visa of facturen"))
        # rapport
        totaal_maand = sum(r["per_maand"] for r in rijen if r["status"] == "loopt")
        regels = [f"# Abonnementen, gebruik en kosten van de groep", "", f"Stand {vandaag.isoformat()}, laatste {MAANDEN} maanden ({maanden[0] if maanden else ''} tot {maanden[-1] if maanden else ''}). "
                  f"Bronnen: Visa-uitgavenstaten per firma en aankoopfacturen in Octopus. Bedragen zoals geboekt (btw zoals op de staat).", "",
                  f"**Lopende software-abonnementen: ongeveer {totaal_maand:,.0f} euro per maand** over {sum(1 for r in rijen if r['status'] == 'loopt')} dienst-firma-combinaties.", "",
                  "## Hoe ver de boekhouding loopt", "", "| firma | jongste Visa-lijn |", "|---|---|"] + [f"| {f} | {t} |" for f, t in sorted(staat.items())] + [
                  "", "Les: de Visa-uitgavenstaten worden maandelijks ingelezen; wat na de jongste datum betaald is, staat hier nog niet.", "",
                  "## Per dienst en firma", "", "| dienst | firma | per maand | maanden actief | laatste betaling | status | bron |", "|---|---|---|---|---|---|---|"]
        for r in rijen:
            regels.append(f"| {r['dienst']} | {r['firma']} | {r['per_maand']:.2f} | {r['maanden_actief']} | {r['laatste']} | {r['status']} | {r['bron']} |")
        regels += ["", "## Dezelfde dienst bij meerdere firma's", ""]
        if dubbel:
            regels += ["| dienst | firma's | samen per maand |", "|---|---|---|"]
            for d, v in sorted(dubbel.items(), key=lambda x: -sum(r["per_maand"] for r in x[1])):
                regels.append(f"| {d} | {', '.join(f'{r['firma']} ({r['per_maand']:.0f})' for r in v)} | {sum(r['per_maand'] for r in v):.0f} |")
            regels.append("")
            regels.append("Vraag voor Mehdi: is dat bewust (aparte licenties per firma) of dubbel betaald? Wie de dienst gebruikt, bepaalt welke firma hoort te betalen.")
        else:
            regels.append("Geen.")
        regels += ["", "## Gebruik naast kosten (wat de dienst-agents melden)", ""]
        if gebruik_regels:
            regels += ["| dienst | gebruiker | woorden per week | oordeel | stand | kost |", "|---|---|---|---|---|---|"]
            regels += [f"| {a} | {b} | {c} | {d} | {e} | {f} |" for a, b, c, d, e, f in gebruik_regels]
        else:
            regels.append("Nog geen meldingen.")
        regels += ["", "## Wat ik adviseer", ""]
        advies = []
        for r in rijen:
            if r["status"] != "loopt":
                continue
            if r["dienst"] == "Wispr Flow":
                gebr = [g for (d, u), g in gebruik.items() if d == "Wispr Flow"]
                if not gebr:
                    advies.append(f"- {r['dienst']} bij {r['firma']} ({r['per_maand']:.0f}/mnd): geen gebruiksmelding van een Wispr-wacht; wie gebruikt dit account?")
            if r["per_maand"] >= 100 and r["dienst"] not in ("Google Ads", "Meta (Facebook/Instagram)"):
                advies.append(f"- {r['dienst']} bij {r['firma']}: {r['per_maand']:.0f} per maand; controleer aantal zetels tegenover wie het echt gebruikt (organisatiedatabase).")
        for d, v in dubbel.items():
            advies.append(f"- {d} loopt bij {len(v)} firma's: bevestig per firma wie er de gebruiker van is, of bundel.")
        regels += advies or ["- Niets dringends; volgende ronde maandag."]
        regels += ["", "## Waar ik zelf op stuit", "", "- Persoonlijke abonnementen (Claude, ChatGPT, Wispr) tonen op hun website geen gebruik; gebruik komt alleen van een dienst-agent op de computer van de gebruiker of van een teamplan.",
                   "- Facturen die via Visa lopen, staan alleen in de uitgavenstaat; of Finance de pdf-factuur zelf bewaart, zie ik hier niet. Dat is een vraag voor Finance (Joan, Amy)." , ""]
        os.makedirs(UIT, exist_ok=True)
        pad = os.path.join(UIT, f"Abonnementen en kosten {vandaag.isoformat()}.md")
        open(pad, "w", encoding="utf-8").write("\n".join(regels) + "\n")
        open(os.path.join(UIT, "laatste.md"), "w", encoding="utf-8").write("\n".join(regels) + "\n")
        json.dump({"stand": vandaag.isoformat(), "maanden": maanden, "rijen": rijen, "gebruik": [list(x) for x in gebruik_regels]}, open(os.path.join(UIT, "laatste.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        ag.klaarzet([{"voor": "mehdi", "soort": "verslag", "sleutel": vandaag.isoformat(), "titel": f"Abonnementen en kosten {vandaag.isoformat()}: {totaal_maand:,.0f} euro/mnd lopend, {len(dubbel)} diensten bij meerdere firma's",
                      "uniek": f"licentiewacht:{vandaag.isoformat()}", "inhoud": "\n".join(regels)[:60000], "verwijzing": pad}])
        ag.log(f"ronde {vandaag.isoformat()}", "bron", f"{len(kaart)} Visa-lijnen en {len(fact)} facturen sinds {sinds}; {len(rijen)} dienst-firma-combinaties; {len(gebruik)} gebruiksmeldingen",
               "\n".join(f"{r['dienst']} | {r['firma']} | {r['per_maand']:.0f}/mnd | {r['status']}" for r in rijen[:60]))
        ag.log(f"ronde {vandaag.isoformat()}", "schrijf", f"rapport {pad}; {len(advies)} adviezen", "\n".join(advies))
        oudste = min(staat.values()) if staat else ""
        if oudste and (vandaag - date.fromisoformat(oudste)).days > 45:
            nood.append({"tekst": f"Visa-uitgavenstaten lopen achter (jongste lijn per firma: {', '.join(f'{f} {t}' for f, t in sorted(staat.items()))}); Finance moet de nieuwe staten inlezen in het kostendashboard", "wie": "finance"})
        if not any(d == "Wispr Flow" for d, _ in gebruik):
            nood.append({"tekst": "Nog geen gebruiksmelding van een Wispr-wacht; zonder dat kan ik Wispr-kosten niet aan gebruik toetsen", "wie": "mehdi"})
        ag.log_verstuur()
        ag.hartslag("waakt", taak="wacht op de volgende ronde (maandag 07:30)", detail=f"{totaal_maand:,.0f} euro/mnd lopend; {len(rijen)} combinaties; {len(dubbel)} dubbel", nood=nood)
        print(pad)
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()

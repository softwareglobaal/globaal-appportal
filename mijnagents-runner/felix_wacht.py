#!/usr/bin/env python3
"""De Felixwacht : runner voor mijnagents.globaal.be.

Zoekt voor elk adres in het werkgebied van FelixArchief (stad Antwerpen, felix/werkgebied.json) de bouwdossiers
op en downloadt wat digitaal is. Eenvoudig, met twee printscreens (Mehdi, 03-10-2026):
  1. Geopunt         officieel adres en perceel; printscreen van geopunt.be (01)
  2. percelenpas     de stad Antwerpen geeft alle vergunningen van het perceel op een pagina (02)
  3. FelixArchief    elk dossiernummer opzoeken; digitaal downloaden in een map met het FelixArchief-nummer,
                     bestanden met hun originele naam; leeszaal alleen melden
  4. terugval        geeft de percelenpas niets, dan FelixArchief op straat en huisnummer ('bevat', beide reeksen)

Gebruik:
  felix_wacht.py --project 3810 --adres "August van de Wielelei 85/101, 2100 Deurne"
  felix_wacht.py --aanmelden-test
  felix_wacht.py                       de ronde: de wachtrij afwerken

Een scan of leeszaalreservatie vraagt hij nooit aan: dat beslist Mehdi.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import adresregister  # noqa: E402
import felixarchief as fa  # noqa: E402

NAAM = "felix-wacht"
DATA = os.path.expanduser(os.environ.get("FELIX_DATA", "~/appportal/mijnagents-data/felix"))
WACHTRIJ = os.path.join(DATA, "wachtrij.jsonl")
REEKSEN = fa.werkgebied()["reeksen"]


def _veilig(tekst):
    tekst = re.sub(r"(\d)\s*/\s*(\w)", r"\1 bus \2", tekst)  # '85/101' is een busnummer, geen '85101'
    return re.sub(r"[^\w ,.#-]+", "", tekst).strip()[:80]  # '#' blijft: het hoort bij het inventarisnummer


# ---------------------------------------------------------------- de eenvoudige weg: het perceel

def _jaar(tekst):
    m = re.search(r"(1[89]\d\d|20\d\d)", tekst or "")
    return m.group() if m else ""


def percelen_zoektocht(adres, felix, stadmap=None):
    """Geopunt -> percelenpas van de stad (op perceel) -> elk dossiernummer in FelixArchief, en de controle omgekeerd:
    wat FelixArchief op straat en huisnummer vindt en de stad niet kent.

    De stad is leidend voor welke vergunningen er bestaan (ook recente en bouwovertredingen); FelixArchief voor de
    stukken zelf (Mehdi en analyse, 03-10-2026).
    """
    import percelenpas
    zonder_bus, _ = adresregister.splits_bus(adres)
    loc = adresregister.lokaliseer(zonder_bus)
    z = {"adres": adres, "tijd": dt.datetime.now().isoformat(timespec="minutes"), "pand": loc or {}, "rijen": []}
    if not loc:
        z["besluit"] = "Geopunt vindt dit adres niet."
        return z
    if not fa.districten_voor(loc["postcode"]):
        z["besluit"] = f"Postcode {loc['postcode']} valt buiten het werkgebied (stad Antwerpen)."
        return z
    try:
        stad = percelenpas.lees(felix._ctx, loc["lat"], loc["lon"], loc["geopunt"], stadmap)
    except Exception as e:
        stad = {"vergunningen": [], "fouten": [f"percelenpas niet bereikbaar: {str(e).splitlines()[0][:150]}"],
                "capakey": "", "bouwovertredingen": "", "bewijs": [], "url": ""}
    z["stad"] = stad

    gezien = set()
    for v in stad["vergunningen"]:
        felix_rijen = felix.dossier_zoeken(v["dossiernummer"])
        gezien.update(r["inventaris"] for r in felix_rijen)
        z["rijen"].append({"jaar": _jaar(v["datum"]) or (_jaar(felix_rijen[0]["aanvraag"]) if felix_rijen else ""),
                           "stad": v["dossiernummer"], "onderwerp": v["onderwerp"], "beslissing": v["beslissing"],
                           "felix": felix_rijen})

    # controle omgekeerd: FelixArchief op straat en huisnummer van het perceel ('bevat', beide reeksen)
    try:
        pand = adresregister.pand(zonder_bus)
        for straat, nummers in (pand.get("nummers_per_straat") or {}).items():
            for reeks in REEKSEN:
                for nr in nummers:
                    for r in felix.nummer_dossiers(reeks, straat, nr):
                        if r["inventaris"] not in gezien and fa.raakt(r["nummer"], nummers):
                            gezien.add(r["inventaris"])
                            z["rijen"].append({"jaar": _jaar(r["aanvraag"]), "stad": "", "onderwerp": r["omschrijving"],
                                               "beslissing": "", "felix": [r], "alleen_felix": True})
    except Exception as e:
        stad["fouten"].append(f"controle in FelixArchief op straat en nummer niet gelukt: {str(e).splitlines()[0][:150]}")

    z["rijen"].sort(key=lambda r: (r["jaar"] or "9999", r["stad"]))
    z["raak"] = sorted((d for r in z["rijen"] for d in r["felix"]), key=lambda d: (d["aanvraag"] or "9999", d["inventaris"]))
    alleen_stad = sum(1 for r in z["rijen"] if not r["felix"])
    alleen_felix = sum(1 for r in z["rijen"] if r.get("alleen_felix"))
    z["besluit"] = (f"Perceel {stad['capakey'] or 'onbekend'}: {len(stad['vergunningen'])} vergunningen bij de stad, "
                    f"{len(z['raak'])} dossiers in FelixArchief; {alleen_stad} alleen bij de stad, {alleen_felix} alleen in FelixArchief.")
    return z


# ---------------------------------------------------------------- bewijs en controle

def _controle_md(z):
    """Een tabel om na te kijken of het werk goed gedaan is (Mehdi, 03-10-2026: controleerbaar, weinig tekst)."""
    stad = z.get("stad") or {}
    gedownload = {d["inventaris"] for d in z.get("downloads") or [] if d.get("bestanden")}
    r = [f"# {z['adres']}", "", z["besluit"], ""]
    if stad.get("bouwovertredingen"):
        r += [f"Bouwovertredingen (stad): {stad['bouwovertredingen']}", ""]
    r += ["| Jaar | Dossier stad | Onderwerp | FelixArchief | Gedownload |", "|---|---|---|---|---|"]
    for x in z.get("rijen") or []:
        invs = ", ".join(d["inventaris"] for d in x["felix"]) or "niet in FelixArchief"
        if not x["felix"]:
            dl = "nee: opvragen bij de stad (Itsme)"
        elif all(d["inventaris"] in gedownload for d in x["felix"]):
            dl = "ja"
        elif all(d["status"] == "leeszaal" for d in x["felix"]):
            dl = "nee: alleen leeszaal"
        else:
            dl = "deels" if any(d["inventaris"] in gedownload for d in x["felix"]) else "nee"
        stadnr = x["stad"] or "niet bij de stad"
        onderwerp = (x["onderwerp"] or "")[:45] + (f" ({x['beslissing'].lower()})" if x.get("beslissing") == "Weigering" else "")
        r.append(f"| {x['jaar'] or '?'} | {stadnr} | {onderwerp} | {invs} | {dl} |")
    if any(not x["felix"] for x in z.get("rijen") or []):
        r += ["", f"Opvragen bij de stad: {stad.get('url', '')} , vink de dossiers zonder FelixArchief aan, "
                  "Dossiers opvragen, aanmelden met Itsme."]
    fouten = (stad.get("fouten") or []) + (z.get("printscreen_fouten") or [])
    if z.get("downloads_fout"):
        fouten.append(f"downloaden: {z['downloads_fout']}")
    if fouten:
        r += [""] + [f"Let op: {f}" for f in fouten]
    return "\n".join(r) + "\n"


def _downloaden(felix, z, felixmap):
    """Elk digitaal dossier in een map met het FelixArchief-nummer, de bestanden met hun originele naam
    (Mehdi, 03-10-2026: "behoud de originele benamingen", geen datums). Leeszaalstukken worden niet aangevraagd."""
    uit = []
    for r in z["raak"]:
        rij = {"inventaris": r["inventaris"], "status": r["status"], "bestanden": []}
        if r["status"] != "leeszaal":
            for f in felix.bestanden(r["inventaris"]):
                if f["naam"].lower().endswith(".xml"):  # een verwijzing naar de plannen, geen stuk
                    continue
                pad = os.path.join(felixmap, r["inventaris"], f["map"], f["naam"])
                rij["bestanden"].append({"naam": f["naam"], "bytes": felix.download(f["url"], pad)})
        uit.append(rij)
    return uit


def voer_uit(adres, uitmap=None, project=None):
    """Een adres opzoeken en downloaden. Map '<project> <adres>' met Geopunt.png, Controle.md,
    'Percelenpas Antwerpen' (rapport-PDF, Vergunningen, Bouwovertredingen) en 'FelixArchief' (Overzicht en dossiers)."""
    naam = f"{project} {_veilig(adres)}" if project else _veilig(adres)
    uitmap = uitmap or os.path.join(DATA, "zoektochten", naam)
    stadmap = os.path.join(uitmap, "Percelenpas Antwerpen")
    felixmap = os.path.join(uitmap, "FelixArchief")
    os.makedirs(felixmap, exist_ok=True)
    fouten = []

    def vastleggen(functie, *args):
        """Een printscreen die mislukt, wordt een opmerking; de zoektocht gaat door."""
        try:
            functie(*args)
        except Exception as e:
            fouten.append(f"{os.path.basename(args[-1])}: {str(e).splitlines()[0][:160]}")

    with fa.Felix() as felix:
        aanmelding = None
        if fa.heeft_aanmelding():  # eerst aanmelden, op een verse startpagina
            try:
                aanmelding = felix.aanmelden()
            except Exception as e:
                aanmelding = {"fout": str(e)[:300]}
        z = percelen_zoektocht(adres, felix, stadmap)
        geopunt = (z.get("pand") or {}).get("geopunt")
        if geopunt:
            vastleggen(felix.schermafdruk_geopunt, geopunt, os.path.join(uitmap, "Geopunt.png"))
        if z.get("raak"):
            vastleggen(felix.overzicht_kaarten, [d["inventaris"] for d in z["raak"]], os.path.join(felixmap, "Overzicht.png"))
            if aanmelding and aanmelding.get("fout"):
                z["downloads_fout"] = aanmelding["fout"]
            elif aanmelding:
                try:
                    z["downloads"] = _downloaden(felix, z, felixmap)
                except Exception as e:  # zoeken is gelukt; een download die faalt mag dat niet wegvegen
                    z["downloads_fout"] = str(e)[:300]
            else:
                z["downloads_fout"] = "geen aanmelding op de server"
    if fouten:
        z["printscreen_fouten"] = fouten
    os.makedirs(os.path.join(uitmap, "_gegevens"), exist_ok=True)  # voor de agent, niet om te lezen
    json.dump(z, open(os.path.join(uitmap, "_gegevens", "resultaat.json"), "w"), ensure_ascii=False, indent=1, default=str)
    open(os.path.join(uitmap, "Controle.md"), "w").write(_controle_md(z))
    return uitmap, z


def ronde():
    """De ronde voor cron: de adressen uit de wachtrij afwerken."""
    import bord
    ag = bord.Agent(NAAM)
    with ag.ronde("wachtrij FelixArchief") as r:
        r.bron("werkgebied.json", open(fa.WERKGEBIED, encoding="utf-8").read())
        wacht = []
        if os.path.exists(WACHTRIJ):
            wacht = [json.loads(x) for x in open(WACHTRIJ) if x.strip()]
        gedaan = 0
        rest = []
        for item in wacht:
            if item.get("klaar"):
                rest.append(item)
                continue
            try:
                pad, z = voer_uit(item["adres"], project=item.get("project"))
                item.update(klaar=dt.datetime.now().isoformat(timespec="minutes"), map=pad, besluit=z["besluit"])
                gedaan += 1
            except Exception as e:  # een adres dat faalt mag de rest niet tegenhouden
                item["fout"] = str(e)[:200]
                r.nood("Zoektocht in FelixArchief faalt", wie="claude-code")
            rest.append(item)
        if wacht:
            os.makedirs(DATA, exist_ok=True)
            open(WACHTRIJ, "w").write("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rest))
        r.detail = f"{gedaan} zoektochten gedaan, {sum(1 for x in rest if not x.get('klaar'))} wachten"


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--adres", help="een adres opzoeken, met bewijs")
    a.add_argument("--uit", help="map voor het resultaat")
    a.add_argument("--project", help="projectnummer, vooraan in de mapnaam")
    a.add_argument("--aanmelden-test", action="store_true", help="alleen nagaan of aanmelden lukt")
    args = a.parse_args()
    if args.aanmelden_test:
        with fa.Felix() as felix:
            g = felix.aanmelden()
        print(f"aangemeld als {g['naam'].strip()}, erewoordverklaring {'aanvaard' if g['erewoord'] else 'NIET aanvaard'}")
    elif args.adres:
        pad, z = voer_uit(args.adres, args.uit, args.project)
        print(z["besluit"])
        print(pad)
    else:
        ronde()

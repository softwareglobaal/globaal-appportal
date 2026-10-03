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


def _varianten(straat):
    """Andere schrijfwijzen om te proberen als FelixArchief de straat niet kent onder de officiele naam."""
    import unicodedata
    zonder = "".join(c for c in unicodedata.normalize("NFD", straat) if unicodedata.category(c) != "Mn")
    woorden = straat.split()
    uit = [straat]
    if zonder != straat:
        uit.append(zonder)
    if len(woorden) > 1:
        uit.append(woorden[-1])                         # 'Graaf van Hoornestraat' -> 'Hoornestraat'
    return list(dict.fromkeys(uit))


def _uniek(rijen):
    gezien, uit = set(), []
    for r in rijen:
        k = (r["reeks"], r["inventaris"], r["nummer"])
        if k not in gezien:
            gezien.add(k)
            uit.append(r)
    return uit


def zoektocht(adres, felix):
    """Een volledige zoektocht voor een adres. Geeft een dict terug met alles wat gevonden en geprobeerd werd."""
    z = {"adres": adres, "tijd": dt.datetime.now().isoformat(timespec="minutes"), "stappen": []}
    pand = adresregister.pand(adres)
    z["pand"] = pand
    if not pand.get("straat"):
        z["besluit"] = "Geopunt vindt dit adres niet; er is niet in FelixArchief gezocht."
        z["stappen"].append(("Geopunt", "adres niet gevonden"))
        return z
    z["stappen"].append(("Geopunt", f"{pand['geopunt']}, perceel {', '.join(pand.get('percelen') or ['onbekend'])}"))

    districten = fa.districten_voor(pand["postcode"])
    z["districten"] = districten
    if not districten:
        z["besluit"] = f"Postcode {pand['postcode']} valt buiten het werkgebied van FelixArchief; niet gezocht."
        z["stappen"].append(("werkgebied", f"postcode {pand['postcode']} buiten werkgebied"))
        return z
    z["stappen"].append(("werkgebied", f"postcode {pand['postcode']}: {', '.join(districten)}"))

    # de straten van het perceel altijd; een straat die er alleen dichtbij ligt pas als dat niets oplevert
    # (Mehdi, 03-10-2026: "als het een gewone rijwoning is, laten we het daarbij houden")
    nummers = pand.get("nummers_per_straat") or {}
    z["eenvoudig"] = len(nummers) == 1 and len(next(iter(nummers.values()), [])) == 1
    z["straten"] = {}

    def zoek(straat, doelen):
        st = _straat(felix, straat, doelen, districten)
        z["straten"][straat] = st
        z["stappen"].append((f"straat {straat} {', '.join(doelen)}",
                             f"{st['naam_in_felix'] or 'niet gevonden'}; {len(st['raak'])} raak ({st.get('werkwijze', '')})"))

    for straat, doelen in nummers.items():
        zoek(straat, doelen)
    if not any(s["raak"] for s in z["straten"].values()):
        for s, dichtbij in (pand.get("straten_dichtbij") or {}).items():
            if s not in z["straten"]:
                zoek(s, sorted({nr for _, nr in dichtbij if nr}))

    raak = sorted((r for s in z["straten"].values() for r in s["raak"]),
                  key=lambda r: (r["aanvraag"] or "9999", r["inventaris"]))
    z["raak"] = raak
    if raak:
        soort = "Een huisnummer op het perceel" if z["eenvoudig"] else "Meer dan een huisnummer of straat op het perceel"
        z["besluit"] = (f"{soort}. Gevonden: {len(raak)} dossier(s), van {raak[0]['aanvraag'][:4]} tot "
                        f"{raak[-1]['aanvraag'][:4]}; {sum(1 for r in raak if r['status'] == 'leeszaal')} alleen in de leeszaal.")
    elif any(s["naam_in_felix"] for s in z["straten"].values()):
        z["besluit"] = ("Straat gevonden in FelixArchief, huisnummer niet. De printscreens tonen het; "
                        "wat er wel in de straat ligt, staat hieronder.")
    else:
        z["besluit"] = "De straat staat in FelixArchief niet onder de officiele naam, ook niet onder de varianten."
    return z


def _straat(felix, straat, doelen, districten):
    st = {"doelen": doelen, "geprobeerd": {}, "naam_in_felix": None, "raak": [], "buren": [],
          "zonder_nummer": [], "hoek": []}
    for variant in _varianten(straat):
        tel = felix.straat_tellen("100#2770", variant, districten)
        st["geprobeerd"][variant] = tel
        if tel["totaal"]:
            st["naam_in_felix"] = variant
            break
    if not st["naam_in_felix"]:
        return st

    # eerst eenvoudig: straat plus elk huisnummer van het perceel, in beide reeksen. Raak is klaar.
    snel = []
    for reeks in REEKSEN:
        for nr in doelen:
            snel += felix.nummer_dossiers(reeks, st["naam_in_felix"], nr, districten)
    for r in _uniek(snel):
        soort = fa.raakt(r["nummer"], doelen) or fa.raakt(r["nummer_dossier"], doelen)
        if soort:
            st["raak"].append(dict(r, soort=soort))
    st["werkwijze"] = "straat en huisnummer"
    if st["raak"]:
        st["raak"].sort(key=lambda r: (r["aanvraag"] or "9999", r["inventaris"]))
        return st

    # niets: de hele straat overlopen voor bereiken ('81-89'), dossiers zonder nummer en de buren
    st["werkwijze"] = "hele straat"
    rijen = []
    for reeks in REEKSEN:
        try:
            rijen += felix.straat_dossiers(reeks, st["naam_in_felix"], districten)
        except RuntimeError as e:
            st.setdefault("opmerkingen", []).append(f"{REEKSEN[reeks]}: hele straat niet op te halen ({e})")
    rijen = _uniek(rijen)
    st["dossiers_in_straat"] = len(rijen)
    for r in rijen:
        soort = fa.raakt(r["nummer"], doelen) or fa.raakt(r["nummer_dossier"], doelen)
        if soort:
            st["raak"].append(dict(r, soort=soort))
        elif not r["nummer"] and not r["nummer_dossier"]:
            st["zonder_nummer"].append(r)
            if re.search(r"\bhoek", r["adresomschrijving"], re.I):
                st["hoek"].append(dict(r, soort="hoek"))
        elif fa.is_buur(r["nummer"], doelen):
            st["buren"].append(r)
    sleutel = lambda r: ((fa.nummers(r["nummer"]) or [(0, 0)])[0][0], r["aanvraag"])  # noqa: E731
    for k in ("buren", "zonder_nummer", "hoek"):
        st[k].sort(key=sleutel)
    st["raak"].sort(key=lambda r: (r["aanvraag"] or "9999", r["inventaris"]))  # van oud naar jong
    return st


# ---------------------------------------------------------------- de eenvoudige weg: het perceel

def percelen_zoektocht(adres, felix, percelenpas_png=None):
    """Geopunt -> percelenpas van de stad (op perceel) -> elk dossiernummer in FelixArchief.

    Mehdi, 03-10-2026: eenvoudig, twee printscreens (Geopunt en het overzicht), downloaden is het belangrijkste.
    Geeft None als de percelenpas niets oplevert; dan zoekt voer_uit in FelixArchief op straat en nummer.
    """
    zonder_bus, _ = adresregister.splits_bus(adres)
    loc = adresregister.lokaliseer(zonder_bus)
    z = {"adres": adres, "tijd": dt.datetime.now().isoformat(timespec="minutes"), "pand": loc or {}}
    if not loc:
        z["besluit"] = "Geopunt vindt dit adres niet."
        return z
    if not fa.districten_voor(loc["postcode"]):
        z["besluit"] = f"Postcode {loc['postcode']} valt buiten het werkgebied van FelixArchief."
        return z
    try:
        pp = felix.percelenpas(loc["lat"], loc["lon"], loc["geopunt"], percelenpas_png)
    except Exception as e:
        z["percelenpas_fout"] = str(e).splitlines()[0][:200]
        return None
    z["perceel"] = pp["capakey"]
    z["vergunningen"] = pp["vergunningen"]
    if not pp["vergunningen"]:
        return None
    raak, niet_in_felix = [], []
    for v in pp["vergunningen"]:
        rijen = felix.dossier_zoeken(v["dossiernummer"])
        for r in rijen:
            r["onderwerp"] = v["onderwerp"]
        raak += rijen
        if not rijen:
            niet_in_felix.append(v)
    z["raak"] = sorted(raak, key=lambda r: (r["aanvraag"] or "9999", r["inventaris"]))
    z["niet_in_felix"] = niet_in_felix
    z["besluit"] = (f"Perceel {pp['capakey']}: {len(pp['vergunningen'])} vergunningen bij de stad, "
                    f"{len(z['raak'])} dossiers in FelixArchief.")
    return z


# ---------------------------------------------------------------- bewijs en rapport

def _rapport_md(z, bewijs):
    """Kort (Mehdi, 03-10-2026: "je produceert veel te veel"): wat er is, van oud naar jong, en wat gedownload is."""
    r = [f"# {z['adres']}", "", z["besluit"], ""]
    gedownload = {d["inventaris"] for d in z.get("downloads") or [] if d.get("bestanden")}
    for x in z.get("raak") or []:
        if x["inventaris"] in gedownload:
            staat = "gedownload"
        elif x["status"] == "leeszaal":
            staat = "alleen leeszaal"
        else:
            staat = x["status"]
        onderwerp = x.get("onderwerp") or x.get("omschrijving") or ""
        r.append(f"- {x['aanvraag'][:4] or '----'}  {x['inventaris']}  {onderwerp[:60]}  ({staat})")
    for v in z.get("niet_in_felix") or []:
        r.append(f"- {v['datum'][-4:] or '----'}  {v['dossiernummer']}  {v['onderwerp'][:60]}  (niet in FelixArchief, bij de stad)")
    if z.get("downloads_fout"):
        r += ["", f"Downloaden niet gelukt: {z['downloads_fout']}"]
    if z.get("opmerking"):
        r += ["", z["opmerking"]]
    r += ["", "Printscreens: " + ", ".join(os.path.basename(b) for b in bewijs)]
    return "\n".join(r) + "\n"


def _downloaden(felix, z, uitmap):
    """Elk digitaal dossier in een map met het FelixArchief-nummer, de bestanden met hun originele naam
    (Mehdi, 03-10-2026: "behoud de originele benamingen", geen datums). Leeszaalstukken worden niet aangevraagd."""
    uit = []
    for r in z["raak"]:
        rij = {"inventaris": r["inventaris"], "status": r["status"], "bestanden": []}
        if r["status"] != "leeszaal":
            for f in felix.bestanden(r["inventaris"]):
                if f["naam"].lower().endswith(".xml"):  # een verwijzing naar de plannen, geen stuk
                    continue
                pad = os.path.join(uitmap, r["inventaris"], f["map"], f["naam"])
                rij["bestanden"].append({"naam": f["naam"], "bytes": felix.download(f["url"], pad)})
        uit.append(rij)
    return uit


def voer_uit(adres, uitmap=None, project=None):
    """Een adres opzoeken en downloaden. Map: '<project> <adres>'; daarin twee printscreens, een kort rapport
    en per dossier een map met het FelixArchief-nummer."""
    naam = f"{project} {_veilig(adres)}" if project else _veilig(adres)
    uitmap = uitmap or os.path.join(DATA, "zoektochten", naam)
    os.makedirs(uitmap, exist_ok=True)
    bewijs, fouten = [], []

    def vastleggen(functie, *args):
        """Een printscreen die mislukt, wordt een opmerking; de zoektocht gaat door."""
        try:
            bewijs.append(functie(*args))
        except Exception as e:
            fouten.append(f"{os.path.basename(args[-1])}: {str(e).splitlines()[0][:160]}")

    with fa.Felix() as felix:
        aanmelding = None
        if fa.heeft_aanmelding():  # eerst aanmelden, op een verse startpagina
            try:
                aanmelding = felix.aanmelden()
            except Exception as e:
                aanmelding = {"fout": str(e)[:300]}
        overzicht = os.path.join(uitmap, "02 Overzicht stad Antwerpen.png")
        z = percelen_zoektocht(adres, felix, overzicht)
        if z is None:  # de percelenpas gaf niets: in FelixArchief zoeken op straat en nummer
            z = zoektocht(adres, felix)
            z["opmerking"] = "De percelenpas van de stad gaf niets; gezocht in FelixArchief op straat en huisnummer."
            if z.get("straten"):
                st = next(iter(z["straten"].values()))
                termen = [st["naam_in_felix"] or next(iter(z["straten"]))] + ([z["pand"].get("huisnummer")] if st["naam_in_felix"] else [])
                vastleggen(felix.schermafdruk_zoeken, termen, os.path.join(uitmap, "02 Overzicht FelixArchief.png"))
        elif os.path.exists(overzicht):
            bewijs.append(overzicht)
        geopunt = (z.get("pand") or {}).get("geopunt")
        if geopunt:
            vastleggen(felix.schermafdruk_geopunt, geopunt, os.path.join(uitmap, "01 Geopunt.png"))
        if aanmelding:
            z["aanmelding"] = aanmelding
        if z.get("raak") and aanmelding:
            if aanmelding.get("fout"):
                z["downloads_fout"] = aanmelding["fout"]
            else:
                try:
                    z["downloads"] = _downloaden(felix, z, uitmap)
                except Exception as e:  # zoeken is gelukt; een download die faalt mag dat niet wegvegen
                    z["downloads_fout"] = str(e)[:300]
    if fouten:
        z["printscreen_fouten"] = fouten
    bewijs.sort()
    os.makedirs(os.path.join(uitmap, "_gegevens"), exist_ok=True)  # voor de agent, niet om te lezen
    json.dump(z, open(os.path.join(uitmap, "_gegevens", "resultaat.json"), "w"), ensure_ascii=False, indent=1, default=str)
    open(os.path.join(uitmap, "rapport.md"), "w").write(_rapport_md(z, bewijs))
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

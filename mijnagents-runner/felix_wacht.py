#!/usr/bin/env python3
"""De Felixwacht : runner voor mijnagents.globaal.be.

Zoekt voor elk adres in het werkgebied van FelixArchief (stad Antwerpen, felix/werkgebied.json) de
bouwdossiers op, en levert bij elke zoektocht het bewijs: ook als er niets is, zodat Mehdi ziet dat
het werk gedaan is en niet zelf opnieuw moet zoeken (Mehdi, 03-10-2026).

De volgorde is vast, en elke stap laat een spoor na:
  1. werkgebied   valt de postcode onder FelixArchief? zo niet, dan stopt het hier, met de reden;
  2. Geopunt      het officiele adres, alle huisnummers op hetzelfde perceel, de straten ernaast
                  (een appartementsgebouw draagt vaak twee nummers, een hoekpand twee straten);
  3. de straat    bestaat ze in FelixArchief onder deze naam, in deze districten?
  4. de nummers   exact, binnen een bereik ("85-87"), zonder nummer of "op de hoek van", en de buren.

Gebruik:
  felix_wacht.py --adres "August van de Wielelei 85/101, 2100 Deurne"   een zoektocht, met bewijs
  felix_wacht.py                                                         de ronde: de wachtrij afwerken

Zoeken mag zonder aanmelden. Downloaden en aanvragen (leeszaal, scan) zijn voor een volgende stap en
gaan altijd via een voorstel; een scan kan geld kosten en blijft Mehdi's beslissing.
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
        z["besluit"] = ("Straat gevonden in FelixArchief, huisnummer niet. De buren en de dossiers zonder "
                        "nummer staan in het overzicht, als bewijs dat er gezocht is.")
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


# ---------------------------------------------------------------- bewijs en rapport

def _rapport_md(z, bewijs):
    """Kort (Mehdi, 03-10-2026: "je produceert veel te veel"): besluit, dossiers van oud naar jong, downloads."""
    r = [f"# FelixArchief: {z['adres']}", "", f"**{z['besluit']}**", ""]
    if z.get("raak"):
        r.append("Dossiers, van oud naar jong:")
        r += [f"- {x['aanvraag'][:4]} {x['inventaris']} ({REEKSEN.get(x['reeks'], '')}): {x['omschrijving'][:70]}, {x['status']}"
              for x in z["raak"]]
    else:
        for straat, st in (z.get("straten") or {}).items():
            kand = st["hoek"] + [x for x in st["zonder_nummer"] if len(st["zonder_nummer"]) <= 30] + st["buren"]
            if kand:
                r.append(f"Niet op het huisnummer; wel in de {straat}, om na te kijken:")
                r += [f"- {x['aanvraag'][:4]} {x['inventaris']}: {x['nummer'] or x['adresomschrijving'] or 'zonder nummer'}, "
                      f"{x['omschrijving'][:60]}, {x['status']}" for x in kand]
    if z.get("downloads"):
        r += ["", "Gedownload:"]
        r += [f"- {d['map']}" + (f": {d['opmerking']}" if d.get("opmerking") else "") for d in z["downloads"]]
    elif z.get("downloads_fout"):
        r += ["", f"Downloaden niet gelukt: {z['downloads_fout']}"]
    elif z.get("raak"):
        r += ["", "Niet gedownload: er is geen aanmelding op de server."]
    r += ["", "Printscreens: " + ", ".join(os.path.basename(b) for b in bewijs)]
    return "\n".join(r) + "\n"


def _downloaden(felix, z, uitmap):
    """Elk digitaal dossier in een eigen map, genummerd van oud naar jong (Mehdi, 03-10-2026: "anders is dat
    allemaal door elkaar en weet ik niet welke ik eerst moet openen"). Leeszaalstukken worden niet aangevraagd."""
    uit = []
    for i, r in enumerate(z["raak"], start=1):
        naam = f"{i:02d} {r['aanvraag'] or 'zonder datum'} {r['inventaris']} {REEKSEN.get(r['reeks'], '')} - {_veilig(r['omschrijving'])[:60]}"
        rij = {"volgorde": i, "map": naam, "inventaris": r["inventaris"], "status": r["status"], "bestanden": []}
        if r["status"] == "leeszaal":
            rij["opmerking"] = "alleen in de leeszaal; reserveren beslist Mehdi"
            uit.append(rij)
            continue
        for f in felix.bestanden(r["inventaris"]):
            if f["naam"].lower().endswith(".xml"):  # een verwijzing, geen stuk ('de plannen zitten in 627#31611')
                rij.setdefault("verwijzingen", []).append(f.get("verwijzing") or f["naam"])
                continue
            pad = os.path.join(uitmap, "Dossiers uit FelixArchief", naam, f["map"], f["naam"])
            grootte = felix.download(f["url"], pad)
            rij["bestanden"].append({"naam": f["naam"], "bytes": grootte})
        uit.append(rij)
    return uit


def voer_uit(adres, uitmap=None):
    """Zoektocht met bewijs; schrijft alles in een eigen map en geeft het pad terug."""
    stempel = dt.datetime.now().strftime("%Y-%m-%d %H%M")
    uitmap = uitmap or os.path.join(DATA, "zoektochten", f"{stempel} {_veilig(adres)}")
    os.makedirs(uitmap, exist_ok=True)
    bewijs = []
    fouten = []

    def vastleggen(functie, *args):
        """Een printscreen die mislukt, wordt een opmerking; de zoektocht gaat door."""
        try:
            bewijs.append(functie(*args))
        except Exception as e:
            fouten.append(f"{os.path.basename(args[-1])}: {str(e).splitlines()[0][:160]}")

    with fa.Felix() as felix:
        z = zoektocht(adres, felix)
        if z["pand"].get("geopunt"):  # echte printscreen van geopunt.be, geen zelfgemaakte kaart
            vastleggen(felix.schermafdruk_geopunt, z["pand"]["geopunt"], os.path.join(uitmap, "01 Geopunt.png"))
        volg = 2
        for straat, st in (z.get("straten") or {}).items():
            naam = st["naam_in_felix"] or straat
            # het nummer van de klant eerst, niet het eerste nummer van het perceel
            nr = z["pand"]["huisnummer"] if straat == z["pand"].get("straat") else (st["doelen"] or [""])[0]
            if nr and st["naam_in_felix"]:
                vastleggen(felix.schermafdruk_zoeken, [naam, nr], os.path.join(uitmap, f"0{volg} FelixArchief zoeken {_veilig(naam + ' ' + nr)}.png"))
                volg += 1
            if not st["raak"]:  # niets op het nummer: bewijs dat de straat zelf wel bestaat en juist geschreven is
                vastleggen(felix.schermafdruk_zoeken, [naam], os.path.join(uitmap, f"0{volg} FelixArchief zoeken {_veilig(naam)} zonder nummer.png"))
                volg += 1
        # wat raak was, elk dossier apart, van oud naar jong: het jaartal vooraan zegt wat je eerst opent
        for i, r in enumerate(z.get("raak") or [], start=1):
            pad = os.path.join(uitmap, f"{10 + i} {r['aanvraag'][:4]} {r['inventaris']} {REEKSEN.get(r['reeks'], '')}.png")
            vastleggen(felix.schermafdruk_dossier, r["inventaris"], r["reeks"], pad)
        if z.get("raak") and fa.heeft_aanmelding():
            try:
                z["aanmelding"] = felix.aanmelden()
                z["downloads"] = _downloaden(felix, z, uitmap)
            except Exception as e:  # zoeken is gelukt; een download die faalt mag dat niet wegvegen
                z["downloads_fout"] = str(e)[:300]
    if fouten:
        z.setdefault("pand", {}).setdefault("opmerkingen", []).extend(f"printscreen niet gelukt: {f}" for f in fouten)
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
                pad, z = voer_uit(item["adres"])
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
    a.add_argument("--aanmelden-test", action="store_true", help="alleen nagaan of aanmelden lukt")
    args = a.parse_args()
    if args.aanmelden_test:
        with fa.Felix() as felix:
            g = felix.aanmelden()
        print(f"aangemeld als {g['naam'].strip()}, erewoordverklaring {'aanvaard' if g['erewoord'] else 'NIET aanvaard'}")
    elif args.adres:
        pad, z = voer_uit(args.adres, args.uit)
        print(z["besluit"])
        print(pad)
    else:
        ronde()

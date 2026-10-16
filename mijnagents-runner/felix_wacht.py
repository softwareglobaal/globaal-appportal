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
  felix_wacht.py                       de ronde: aanvragen afwerken (cron, elke 5 minuten)

Aanvragen komen van de pagina felix.globaal.be (Shelton, 13-10-2026; zonder goedkeuring van Mehdi). Een bestand,
een schrijver: de pagina schrijft aanvragen.jsonl (zoeken en opslaan), deze runner schrijft stand.json en het
logboek log.jsonl. Opslaan in de projectmap gebeurt alleen op een klik op de pagina.

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
AANVRAGEN = os.path.join(DATA, "aanvragen.jsonl")   # schrijft de pagina (app-mijnagents)
STAND = os.path.join(DATA, "stand.json")            # schrijft deze runner
LOGBOEK = os.path.join(DATA, "log.jsonl")           # schrijft deze runner
ZOEKTOCHTEN = os.path.join(DATA, "zoektochten")
SLOT = os.path.join(DATA, "ronde.lock")
POGINGEN = 3   # een zoektocht die op een timeout strandt, gaat zoveel keer mee
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
    wat FelixArchief op straat en huisnummer vindt en de stad niet kent, ook in de hoekstraat.

    De stad is leidend voor welke vergunningen er bestaan (ook recente en bouwovertredingen); FelixArchief voor de
    stukken zelf (Mehdi en analyse, 03-10-2026). Een stap die faalt, veegt de andere niet weg: wat ontbreekt, staat
    in z['onvolledig'] (Codex FX04 en FX11, 17-10-2026).
    """
    import time
    import percelenpas
    t0 = time.time()
    zonder_bus, _ = adresregister.splits_bus(adres)
    loc = adresregister.lokaliseer(zonder_bus)
    z = {"adres": adres, "tijd": dt.datetime.now().isoformat(timespec="minutes"), "pand": loc or {}, "rijen": [],
         "onvolledig": [], "duur": {}}
    if not loc:
        z["besluit"] = "Geopunt vindt dit adres niet."
        return z
    if not fa.districten_voor(loc["postcode"]):
        z["besluit"] = f"Postcode {loc['postcode']} valt buiten het werkgebied (stad Antwerpen)."
        return z
    punt = (loc["lat"], loc["lon"])
    try:
        stad = percelenpas.lees(felix._ctx, loc["lat"], loc["lon"], loc["geopunt"], stadmap)
    except Exception as e:
        stad = {"vergunningen": [], "fouten": [f"percelenpas niet bereikbaar: {str(e).splitlines()[0][:150]}"],
                "capakey": "", "bouwovertredingen": "", "bouwovertredingen_lijst": [], "bewijs": [], "url": "",
                "gelezen": {"vergunningen": False, "bouwovertredingen": False}}
    z["stad"] = stad
    z["onvolledig"] += stad.get("fouten") or []
    z["duur"]["stad"] = round(time.time() - t0)

    t1 = time.time()
    gezien = set()
    for v in stad["vergunningen"]:
        try:
            felix_rijen = felix.dossier_zoeken(v["dossiernummer"], punt)
        except Exception as e:
            felix_rijen = []
            z["onvolledig"].append(f"FelixArchief niet doorzocht voor {v['dossiernummer']}: {str(e).splitlines()[0][:120]}")
        gezien.update(r["inventaris"] for r in felix_rijen)
        z["rijen"].append({"jaar": _jaar(v["datum"]) or (_jaar(felix_rijen[0]["aanvraag"]) if felix_rijen else ""),
                           "stad": v["dossiernummer"], "onderwerp": v["onderwerp"], "beslissing": v["beslissing"],
                           "felix": felix_rijen})
    z["duur"]["dossiernummers"] = round(time.time() - t1)

    # controle omgekeerd: FelixArchief op straat en huisnummer, ook de straten van het perceel en de hoekstraat
    t2 = time.time()
    try:
        pand = adresregister.pand(zonder_bus)
        straten = dict(pand.get("nummers_per_straat") or {})
        for s, dichtbij in (pand.get("straten_dichtbij") or {}).items():  # hoekpand: Grotesteenweg 459 en Lysenstraat 2
            straten.setdefault(s, sorted({nr for _, nr in dichtbij if nr}))
        for straat, nummers in straten.items():
            for reeks in REEKSEN:
                for nr in nummers:
                    for r in felix.nummer_dossiers(reeks, straat, nr):
                        if r["inventaris"] not in gezien and fa.raakt(r["nummer"], nummers):
                            gezien.add(r["inventaris"])
                            z["rijen"].append({"jaar": _jaar(r["aanvraag"]), "stad": "", "onderwerp": r["omschrijving"],
                                               "beslissing": "", "felix": [r], "alleen_felix": True})
    except Exception as e:
        z["onvolledig"].append(f"controle in FelixArchief op straat en nummer niet gelukt: {str(e).splitlines()[0][:150]}")
    z["duur"]["controle"] = round(time.time() - t2)

    z["rijen"].sort(key=lambda r: (r["jaar"] or "9999", r["stad"]))
    z["raak"] = sorted((d for r in z["rijen"] for d in r["felix"]), key=lambda d: (d["aanvraag"] or "9999", d["inventaris"]))
    alleen_stad = sum(1 for r in z["rijen"] if not r["felix"])
    alleen_felix = sum(1 for r in z["rijen"] if r.get("alleen_felix"))
    z["besluit"] = (f"Perceel {stad['capakey'] or 'onbekend'}: {len(stad['vergunningen'])} vergunningen bij de stad, "
                    f"{len(z['raak'])} dossiers in FelixArchief; {alleen_stad} alleen bij de stad, {alleen_felix} alleen in FelixArchief.")
    if not (stad.get("gelezen") or {}).get("vergunningen"):
        z["besluit"] = "Onvolledig: de vergunningen van de stad konden niet gelezen worden. " + z["besluit"]
    return z


# ---------------------------------------------------------------- bewijs en controle

def _controle_md(z):
    """Een tabel om na te kijken of het werk goed gedaan is (Mehdi, 03-10-2026: controleerbaar, weinig tekst)."""
    stad = z.get("stad") or {}
    dl = {d["inventaris"]: d for d in z.get("downloads") or []}
    r = [f"# {z['adres']}", "", z["besluit"], "",
         "**Volledig.**" if not z.get("onvolledig") else f"**Onvolledig:** {len(z['onvolledig'])} punt(en), zie onderaan.", ""]
    if stad.get("bouwovertredingen") or stad.get("bouwovertredingen_lijst"):
        r.append(f"Bouwovertredingen (stad): {stad.get('bouwovertredingen') or ''}")
        r += [f"- {b.get('omschrijving', '')} (dossier {b.get('dossiernummer', '?')}, registratie {b.get('registratienummer', '?')})"
              for b in stad.get("bouwovertredingen_lijst") or []]
        r.append("")
    r += ["| Jaar | Dossier stad | Onderwerp | FelixArchief | Gedownload |", "|---|---|---|---|---|"]
    for x in z.get("rijen") or []:
        invs = ", ".join(d["inventaris"] + (f" ({d['straat']} {d['nummer']}, {d.get('afstand_m')} m)" if d.get("via") else "")
                         for d in x["felix"]) or "niet in FelixArchief"
        stukken = [dl.get(d["inventaris"]) for d in x["felix"]]
        if not x["felix"]:
            tekst = "nee: opvragen bij de stad (Itsme)"
        elif all(d["status"] == "leeszaal" for d in x["felix"]):
            tekst = "nee: alleen leeszaal"
        elif stukken and all(s and s["bestanden"] and not s["mislukt"] and not s["beschermd"] for s in stukken if s):
            tekst = "ja"
        elif any(s and s["beschermd"] for s in stukken) and not any(s and s["bestanden"] for s in stukken):
            tekst = "nee: alleen online bekijken (auteursrecht)"
        elif any(s and s["bestanden"] for s in stukken):
            tekst = "deels: " + "; ".join(
                f"{s['inventaris']} {len(s['bestanden'])} van {len(s['bestanden']) + len(s['mislukt']) + len(s['beschermd'])}"
                for s in stukken if s)
        else:
            tekst = "nee"
        stadnr = x["stad"] or "niet bij de stad"
        onderwerp = (x["onderwerp"] or "")[:45] + (f" ({x['beslissing'].lower()})" if x.get("beslissing") == "Weigering" else "")
        r.append(f"| {x['jaar'] or '?'} | {stadnr} | {onderwerp} | {invs} | {tekst} |")
    if any(not x["felix"] for x in z.get("rijen") or []):
        r += ["", f"Opvragen bij de stad: {stad.get('url', '')} , vink de dossiers zonder FelixArchief aan, "
                  "Dossiers opvragen, aanmelden met Itsme."]
    beschermd = [f"{d['inventaris']}" for d in z.get("downloads") or [] if d.get("beschermd")]
    if beschermd:
        r += ["", "Alleen online te bekijken na aanmelden (auteursrecht): " + ", ".join(
            f"[{i}]({fa.BASIS}/detailpagina?invnr={i.replace('#', '_')})" for i in beschermd)]
    if z.get("onvolledig"):
        r += [""] + [f"Let op: {f}" for f in z["onvolledig"]]
    if z.get("duur"):
        r += ["", "Duur (s): " + ", ".join(f"{k} {v}" for k, v in z["duur"].items())]
    return "\n".join(r) + "\n"


def _downloaden(felix, z, felixmap):
    """Elk digitaal dossier in een map met het FelixArchief-nummer, de bestanden met hun originele naam
    (Mehdi, 03-10-2026: "behoud de originele benamingen", geen datums). Leeszaalstukken worden niet aangevraagd.

    Per bestand: gedownload, beschermd (auteursrecht: alleen online bekijken) of mislukt na een herkansing.
    De lijst wordt meteen in z gezet, zodat een fout halverwege niets wegveegt (Codex FX11, 17-10-2026).
    """
    uit = z.setdefault("downloads", [])
    for r in z["raak"]:
        rij = {"inventaris": r["inventaris"], "status": r["status"], "bestanden": [], "mislukt": [], "beschermd": []}
        uit.append(rij)
        if r["status"] == "leeszaal":
            continue
        try:
            lijst = felix.bestanden(r["inventaris"])
        except Exception as e:
            rij["mislukt"].append(f"lijst van bestanden: {str(e).splitlines()[0][:80]}")
            continue
        for f in lijst:
            if f["naam"].lower().endswith(".xml"):  # een verwijzing naar de plannen, geen stuk
                continue
            pad = os.path.join(felixmap, r["inventaris"], f["map"], f["naam"])
            for poging in range(2):
                try:
                    rij["bestanden"].append({"naam": f["naam"], "bytes": felix.download(f["url"], pad, f.get("grootte"))})
                    break
                except fa.Beschermd:
                    rij["beschermd"].append(f["naam"])
                    break
                except fa.BestandFout as e:
                    if r["status"] == "na aanmelden" and str(e) == "500":  # auteursrecht: FelixArchief geeft hier 500
                        rij["beschermd"].append(f["naam"])
                        break
                    if poging == 1:
                        rij["mislukt"].append(f"{f['naam']}: status {e}")
                except Exception as e:  # een bestand dat faalt, stopt de andere niet (13-10-2026)
                    if poging == 1:
                        rij["mislukt"].append(f"{f['naam']}: {str(e).splitlines()[0][:80]}")
    mislukt = [f"{r['inventaris']}/{m}" for r in uit for m in r["mislukt"]]
    if mislukt:
        z["onvolledig"].append(f"{len(mislukt)} bestand(en) niet gedownload: " + "; ".join(mislukt[:5]))
    return uit


def voer_uit(adres, uitmap=None, project=None):
    """Een adres opzoeken en downloaden. Map '<project> <adres>' met Geopunt.png, Controle.md,
    'Percelenpas Antwerpen' (rapport-PDF, Vergunningen, Bouwovertredingen) en 'FelixArchief' (Overzicht en dossiers).
    z['volledig'] zegt of alles lukte; anders staat in z['onvolledig'] wat ontbreekt."""
    import time
    naam = f"{project} {_veilig(adres)}" if project else _veilig(adres)
    uitmap = uitmap or os.path.join(DATA, "zoektochten", naam)
    stadmap = os.path.join(uitmap, "Percelenpas Antwerpen")
    felixmap = os.path.join(uitmap, "FelixArchief")
    os.makedirs(felixmap, exist_ok=True)
    t0 = time.time()
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
            try:
                felix.schermafdruk_geopunt(geopunt, os.path.join(uitmap, "Geopunt.png"))
            except Exception as e:
                z["onvolledig"].append(f"Geopunt.png niet gelukt: {str(e).splitlines()[0][:150]}")
        if z.get("raak"):
            try:
                _, ontbreekt = felix.overzicht_kaarten([d["inventaris"] for d in z["raak"]], os.path.join(felixmap, "Overzicht.png"))
                if ontbreekt:
                    z["onvolledig"].append("Overzicht.png zonder " + ", ".join(ontbreekt))
            except Exception as e:
                z["onvolledig"].append(f"Overzicht.png niet gelukt: {str(e).splitlines()[0][:150]}")
            t1 = time.time()
            if aanmelding and aanmelding.get("fout"):
                z["onvolledig"].append(f"niet gedownload, aanmelden mislukt: {aanmelding['fout']}")
            elif aanmelding:
                try:
                    _downloaden(felix, z, felixmap)
                except Exception as e:  # zoeken is gelukt; een download die faalt mag dat niet wegvegen
                    z["onvolledig"].append(f"downloaden onderbroken: {str(e).splitlines()[0][:200]}")
            else:
                z["onvolledig"].append("niet gedownload: geen aanmelding op de server")
            z["duur"]["downloaden"] = round(time.time() - t1)
        if aanmelding:
            z["aanmelding"] = {k: aanmelding.get(k) for k in ("aangemeld", "erewoord", "fout") if k in aanmelding}
    z.setdefault("duur", {})["totaal"] = round(time.time() - t0)
    z["volledig"] = not z.get("onvolledig")
    os.makedirs(os.path.join(uitmap, "_gegevens"), exist_ok=True)  # voor de agent, niet om te lezen
    json.dump(z, open(os.path.join(uitmap, "_gegevens", "resultaat.json"), "w"), ensure_ascii=False, indent=1, default=str)
    open(os.path.join(uitmap, "Controle.md"), "w").write(_controle_md(z))
    return uitmap, z


# ---------------------------------------------------------------- aanvragen, stand en logboek

def _nu():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def lees_aanvragen():
    """Alle aanvragen van de pagina, oudste eerst. Een kapotte regel wordt overgeslagen, niet de rest."""
    uit = []
    try:
        for regel in open(AANVRAGEN, encoding="utf-8"):
            try:
                a = json.loads(regel)
            except ValueError:
                continue
            if isinstance(a, dict) and a.get("id") and a.get("soort") in ("zoek", "opslaan"):
                uit.append(a)
    except OSError:
        pass
    return uit


def lees_stand():
    try:
        s = json.load(open(STAND, encoding="utf-8"))
    except (OSError, ValueError):
        s = {}
    s.setdefault("zoek", {})
    s.setdefault("opslaan", {})
    return s


def schrijf_stand(s):
    os.makedirs(DATA, exist_ok=True)
    tmp = STAND + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STAND)   # in een keer: de pagina leest nooit een half bestand


def logboek(gebeurtenis, **velden):
    """Het logboek van alle aanvragen, resultaten en opslagen (Shaniel, 13-10-2026). Alleen toevoegen."""
    os.makedirs(DATA, exist_ok=True)
    with open(LOGBOEK, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _nu(), "gebeurtenis": gebeurtenis, **velden}, ensure_ascii=False) + "\n")


def projectmap(project):
    """De projectmap in Dropbox (H-A WORK, volgens de mapnaam). Eerst de index van vandaag, dan opnieuw gelezen."""
    import projectadressen
    for uren in (24, 0):
        p = (projectadressen.index(maximum_uren=uren) or {}).get(str(project))
        if p and p.get("map"):
            return p["map"]
    return None


def opslaan(zoek):
    """Een afgewerkte zoektocht naar de projectmap, in een nieuwe map 'FelixArchief <datum>'. Nooit overschrijven:
    bestaat een bestand al, dan krijgt het een nummer (bronnen.upload, mode add). _gegevens gaat niet mee."""
    import bronnen
    if not zoek.get("project"):
        raise ValueError("deze zoektocht heeft geen projectnummer; opzoeken met projectnummer om op te slaan")
    pm = projectmap(zoek["project"])
    if not pm:
        raise ValueError(f"geen projectmap voor {zoek['project']} gevonden in Dropbox (Work All/01. H-A WORK)")
    bron = os.path.join(ZOEKTOCHTEN, zoek["map"])
    doel = f"{pm}/FelixArchief {(zoek.get('klaar') or _nu())[:10]}"
    n, fouten = 0, []
    for wortel, mappen, bestanden in os.walk(bron):
        mappen[:] = [m for m in mappen if m != "_gegevens"]
        for b in sorted(bestanden):
            rel = os.path.relpath(os.path.join(wortel, b), bron).replace(os.sep, "/")
            try:
                with open(os.path.join(wortel, b), "rb") as f:
                    bronnen.upload(f"{doel}/{rel}", f.read())
                n += 1
            except Exception as e:  # een bestand dat faalt, noemen we; de rest gaat door
                fouten.append(f"{rel}: {str(e)[:120]}")
    return {"pad": doel, "bestanden": n, "fouten": fouten}


def _timeout_in(meldingen):
    return any("Timeout" in m or "Target crashed" in m for m in (meldingen or []))


def _opnieuw(s):
    """Gaat deze zoektocht nog eens mee? Bij een timeout of een gecrashte browser, tot POGINGEN keer."""
    return s.get("pogingen", 1) < POGINGEN and (
        (s.get("status") == "fout" and "Timeout" in s.get("fout", ""))
        or (s.get("status") == "onvolledig" and _timeout_in(s.get("onvolledig"))))


def ronde():
    """De ronde voor cron: eerst de zoekaanvragen, dan de opslagaanvragen. Een ronde tegelijk (slot)."""
    import fcntl
    import bord
    os.makedirs(DATA, exist_ok=True)
    slot = open(SLOT, "w")
    try:
        fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return   # de vorige ronde zoekt nog
    ag = bord.Agent(NAAM)
    with ag.ronde("aanvragen FelixArchief") as r:
        r.bron("werkgebied.json", open(fa.WERKGEBIED, encoding="utf-8").read())
        aanvragen = lees_aanvragen()
        stand = lees_stand()
        gezocht = opgeslagen = 0
        for a in aanvragen:
            if a["soort"] != "zoek":
                continue
            vorige = stand["zoek"].get(a["id"])
            # Een timeout is meestal de drukte op de VM of bij de stad (13-10-2026: load 30 tot 100 op 2 vCPU):
            # opnieuw proberen, tot POGINGEN keer. Een andere fout blijft staan.
            # 'bezig' terwijl ik het slot heb, betekent: de vorige ronde stierf halverwege (gestopt, VM vol).
            # Die zoektocht telt als een mislukte poging en mag opnieuw.
            herkansing = vorige and vorige.get("pogingen", 1) < POGINGEN and (
                vorige.get("status") == "bezig"
                or (vorige.get("status") == "fout" and "Timeout" in vorige.get("fout", ""))
                or (vorige.get("status") == "onvolledig" and _timeout_in(vorige.get("onvolledig"))))
            if vorige and not herkansing:
                continue
            item = {"project": a.get("project", ""), "adres": a["adres"], "door": a.get("door", ""),
                    "aangevraagd": a.get("ts", ""), "status": "bezig", "start": _nu(),
                    "pogingen": (vorige or {}).get("pogingen", 0) + 1}
            stand["zoek"][a["id"]] = item
            schrijf_stand(stand)
            if item["pogingen"] == 1:
                logboek("aanvraag", id=a["id"], door=item["door"], project=item["project"], adres=item["adres"])
            else:
                logboek("opnieuw", id=a["id"], adres=item["adres"], poging=item["pogingen"])
            naam = f"{item['project']} {_veilig(item['adres'])}".strip()
            try:
                pad, z = voer_uit(item["adres"], uitmap=os.path.join(ZOEKTOCHTEN, f"{a['id']} {naam}"),
                                  project=item["project"] or None)
                # Onvolledig is geen klaar (Codex FX11, 17-10-2026): de pagina toont het in oranje, met wat ontbreekt.
                item.update(status="klaar" if z.get("volledig") else "onvolledig", klaar=_nu(), map=os.path.basename(pad),
                            besluit=z["besluit"], onvolledig=(z.get("onvolledig") or [])[:6], duur=(z.get("duur") or {}).get("totaal"),
                            dossiers=len(z.get("raak") or []),
                            vergunningen=len((z.get("stad") or {}).get("vergunningen") or []))
                logboek("resultaat", id=a["id"], adres=item["adres"], besluit=z["besluit"], map=item["map"])
                ag.log(f"zoektocht {a['id']}", "resultaat", f"{item['adres']} (voor {item['door']}): {z['besluit']}")
                gezocht += 1
            except Exception as e:  # een adres dat faalt mag de rest niet tegenhouden
                item.update(status="fout", klaar=_nu(), fout=str(e)[:300])
                logboek("fout", id=a["id"], adres=item["adres"], fout=item["fout"], poging=item["pogingen"])
                if not ("Timeout" in item["fout"] and item["pogingen"] < POGINGEN):
                    r.nood("Zoektocht in FelixArchief faalt", wie="claude-code")
            schrijf_stand(stand)
        for a in aanvragen:
            if a["soort"] != "opslaan" or a["id"] in stand["opslaan"]:
                continue
            zoek = stand["zoek"].get(a.get("zoek_id", ""))
            uit = {"zoek_id": a.get("zoek_id", ""), "door": a.get("door", ""), "ts": _nu()}
            if not zoek or zoek.get("status") not in ("klaar", "onvolledig"):
                uit["fout"] = "zoektocht niet (of nog niet) afgewerkt"
            elif zoek.get("opgeslagen"):
                uit["fout"] = f"al opgeslagen in {zoek['opgeslagen']['pad']}"
            else:
                try:
                    res = opslaan(zoek)
                    uit.update(res)
                    zoek["opgeslagen"] = {"pad": res["pad"], "bestanden": res["bestanden"], "door": uit["door"], "ts": uit["ts"],
                                          "fouten": res["fouten"]}
                    opgeslagen += 1
                    ag.log(f"zoektocht {uit['zoek_id']}", "opgeslagen",
                           f"{res['bestanden']} bestanden naar {res['pad']} (door {uit['door']})")
                except Exception as e:
                    uit["fout"] = str(e)[:300]
            if uit.get("fout") and zoek is not None:
                zoek["opslaan_fout"] = uit["fout"]
            elif zoek is not None:
                zoek.pop("opslaan_fout", None)
            stand["opslaan"][a["id"]] = uit
            logboek("opgeslagen" if not uit.get("fout") else "opslaan_mislukt", **uit)
            schrijf_stand(stand)
        wacht = sum(1 for a in aanvragen if a["soort"] == "zoek" and (
            a["id"] not in stand["zoek"] or _opnieuw(stand["zoek"][a["id"]])))
        r.detail = f"{gezocht} zoektochten gedaan, {opgeslagen} opgeslagen, {wacht} wachten"
        # Zonder taalmodel: geen tokens. Wel de drukte meten, want een browser op een volle VM loopt vast.
        try:
            r.detail += f"; load {open('/proc/loadavg').read().split()[0]}"
        except OSError:
            pass


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

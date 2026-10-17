"""De percelenpas van de stad Antwerpen (omgeving.antwerpen.be/percelenpas): alles wat de stad over een perceel weet.

Zoekt op het perceel, niet op het huisnummer. Toont de vergunningen die bij de dienst Omgeving en FelixArchief gekend
zijn (ook recente die nog niet in FelixArchief zitten), de bouwovertredingen, voorschriften en erfgoed. De knop PDF
geeft het volledige rapport (rapport_<perceel>.pdf).

Altijd openen met de coordinaten van Geopunt, nooit via het zoekveld: een collega kwam op 02-10-2026 via het zoekveld
op het verkeerde perceel uit (11345B0117 in plaats van 11344A0430) en zag daardoor "geen vergunningen".

Dossiers opvragen bij de stad vraagt aanmelden met Itsme of eID (hoger zekerheidsniveau, gemeten 03-10-2026); dat kan
de server niet. Die stap zetten we klaar voor Mehdi.
"""
import json
import os
import re
import urllib.parse
from collections import Counter

BASIS = "https://omgeving.antwerpen.be/percelenpas"
UITKOMST_GEEN = "Er zijn geen gekende bouwovertredingen"
UITKOMST_WEL = "Vastgestelde bouwovertredingen"
CAPAKEY = r"\d{5}[A-Z]\d{4}/\d{2}[A-Z_]\d{3}"
# Een scherm dat twee keer hetzelfde toont, bewijst niet dat de stad klaar is met laden (Codex-ronde 7): zonder
# bronantwoord tonen we wat het scherm zegt, maar is het resultaat onvolledig.
NIET_BEVESTIGD = "{} alleen van het scherm gelezen: {}, dus niet bevestigd"


def url(sectie, lat, lon, adres):
    return f"{BASIS}/{sectie}?" + urllib.parse.urlencode({"x": lat, "y": lon, "searchAddress": adres})


def _cookies_weigeren(p):
    try:
        p.get_by_role("button", name="Optionele cookies weigeren").click(timeout=5000)
    except Exception:
        pass


def _sectietekst(p, titel):
    """De tekst van de sectie zelf, tussen haar titel en 'Veelgestelde vragen'."""
    tekst = p.locator("body").inner_text()
    i = tekst.rfind("\n" + titel + "\n")
    j = tekst.find("Veelgestelde vragen", i)
    return tekst[i + len(titel) + 2: j if j > 0 else None].strip() if i >= 0 else ""


# Ontwerp (Codex-rondes 5 tot 7, stopregel, 17-10-2026): het scherm van de percelenpas laadt in stukken. De gegevens
# komen daarom uit het bronantwoord van de stad (POST /passthroughapi/content/content-with-gis-by-slug, een JSON per
# sectie), dat per definitie volledig is. Alleen als dat niet binnenkomt, lezen we het scherm, met de regel
# 'expliciet en twee keer na elkaar gelijk', en dat staat dan in 'bron'.


def bouwovertredingen_uit_tekst(tekst):
    """De sectietekst -> (samenvatting, lijst van overtredingen met omschrijving, dossiernummer, registratienummer).

    Grotesteenweg 459 (13-10-2026) had er twee; de oude code bewaarde alleen de laatste regel, een registratienummer.
    """
    regels = [r.strip() for r in (tekst or "").splitlines() if r.strip()]
    if any(r.startswith("Er zijn geen gekende bouwovertredingen") for r in regels):
        return "geen gekend", []
    if "Vastgestelde bouwovertredingen" in regels:
        regels = regels[regels.index("Vastgestelde bouwovertredingen") + 1:]
    lijst, huidig = [], None
    for r in regels:
        if r.startswith("Is er een bouwovertreding?"):
            continue
        m = re.match(r"(Dossiernummer|Registratienummer):\s*(.+)", r)
        if m and huidig is not None:
            huidig[m.group(1).lower()] = m.group(2).strip()
        elif not m:
            huidig = {"omschrijving": r}
            lijst.append(huidig)
    lijst = [x for x in lijst if x.get("dossiernummer") or x.get("registratienummer")]
    if not lijst:
        return ("onbekend: " + " ".join(regels)[:200]) if regels else "onbekend", []
    return f"{len(lijst)} vastgesteld", lijst


def _printscreen(p, pad, fouten):
    """Een printscreen die mislukt, wordt een melding; de gegevens van de pagina blijven (Codex FX04, 17-10-2026)."""
    for volledig in (True, False):
        try:
            p.screenshot(path=pad, full_page=volledig, timeout=60000)
            return pad
        except Exception as e:
            fout = str(e).splitlines()[0][:150]
    fouten.append(f"{os.path.basename(pad)} niet gelukt: {fout}")
    return None


def _layer_tile(antwoord):
    """De gegevens van het perceel uit het bronantwoord (content-with-gis-by-slug), alle blokken samen.

    De stad bouwt haar eigen tabel uit alle inhoudsblokken (main.js: permitContent ... subLayerItems ... permits,
    flat). Wielelei 85 heeft er twee: 'Stedenbouwkundige vergunningen' en 'Archief vergunningen' met vier toelatingen
    van voor 1962; wie alleen het eerste blok las, zag 1 van de 5 (gemeten 17-10-2026).

    {} als de stad uitdrukkelijk niets heeft: de inhoud is dan een lege lijst (Wielelei 85 en Frans Brandsstraat 11,
    geen bouwovertredingen). None bij elke andere vorm: het antwoord wordt in zijn geheel afgewezen, nooit stil
    gefilterd (Codex FX28, rondes 8 en 9).
    """
    try:
        inhoud = antwoord["fields"]["content"]["content"]
    except (KeyError, TypeError):
        return None
    if not isinstance(inhoud, list):
        return None
    if not inhoud:
        return {}
    subs = []
    for blok in inhoud:
        waarde = blok.get("value") if isinstance(blok, dict) else None
        tile = waarde.get("layerTile") if isinstance(waarde, dict) else None
        if not isinstance(tile, dict) or not isinstance(tile.get("subLayerItems"), list) or not tile["subLayerItems"]:
            return None
        if not all(isinstance(s, dict) for s in tile["subLayerItems"]):
            return None
        subs += tile["subLayerItems"]
    return {"subLayerItems": subs}


def _is_bronantwoord(r, sectie):
    """Het antwoord van de stad voor precies deze sectie: de aanvraag zegt '"url": "/percelenpas/<sectie>"'."""
    if "content-with-gis-by-slug" not in r.url:
        return False
    try:
        return json.loads(r.request.post_data or "{}").get("url") == f"/percelenpas/{sectie}"
    except Exception:
        return False


def _is_perceelinfo(r):
    return urllib.parse.urlparse(r.url).path.endswith("/passthroughapi/parcelinfo")


def _binnen(punt, veelhoek):
    """Ligt het Geopunt-punt (lat, lon) strikt binnen de perceelgrens [{"x": lat, "y": lon}, ...]? Zonder marge: een
    punt op of buiten de grens is geen bevestiging (Codex FX27, ronde 9)."""
    try:
        hoeken = [(float(h["x"]), float(h["y"])) for h in veelhoek]
    except (KeyError, TypeError, ValueError):
        return False
    if len(hoeken) < 3:
        return False
    lat, lon = punt
    binnen = False
    for (x1, y1), (x2, y2) in zip(hoeken, hoeken[1:] + hoeken[:1]):
        if (y1 > lon) != (y2 > lon) and lat < (x2 - x1) * (lon - y1) / (y2 - y1) + x1:
            binnen = not binnen
    return binnen


def _grens_van(r):
    try:
        return json.loads(r.request.post_data or "{}").get("geometry")
    except Exception:
        return None


def _perceel_uit(r, punt):
    """(perceel, reden) uit het antwoord waarop de stad de pagina bouwt: POST /passthroughapi/parcelinfo met onze
    Geopunt-coordinaten; het antwoord geeft capaKey, de perceelgrens en het adres (gemeten 17-10-2026). Die grens
    gaat daarna naar de inhoudsaanvraag. Zo hangen adres, perceel en inhoud aantoonbaar aan elkaar.

    Het Adressenregister is hiervoor geen maatstaf: het schrijft 11303C0256-00E012 en kende bij Frans Brandsstraat 11
    een ander nummer (00N002) dan de stad (00A003), met hetzelfde grondperceel.
    """
    try:
        if r.status != 200:
            return None, f"het perceel van de stad gaf status {r.status}"
        vraag, a = json.loads(r.request.post_data or "{}"), r.json()
    except Exception:
        return None, "het perceel van de stad was niet te lezen"
    try:
        zelfde_punt = abs(float(vraag.get("x")) - punt[0]) < 1e-9 and abs(float(vraag.get("y")) - punt[1]) < 1e-9
    except (TypeError, ValueError):
        zelfde_punt = False
    if not zelfde_punt:
        return None, "de stad zocht het perceel op een ander punt dan het Geopunt-adres"
    capakey = str((a or {}).get("capaKey") or "")
    if not re.fullmatch(CAPAKEY, capakey):
        return None, "de stad gaf geen geldig perceelnummer"
    if not _binnen(punt, a.get("geometry") or []):
        return None, "het Geopunt-punt ligt niet binnen het perceel van de stad"
    return {"capakey": capakey, "geometry": a["geometry"], "adres": a.get("address") or "",
            "adressen": a.get("addresses") or []}, ""


def vergunningen_uit_bron(tile):
    """De vergunningen uit het bronantwoord van de stad, zoals haar eigen tabel ze toont."""
    uit = []
    for sub in (tile or {}).get("subLayerItems") or []:
        for v in sub.get("permits") or []:
            nr, inv = str(v.get("fileNumber") or ""), str(v.get("inventoryNumber") or "")
            if inv and not nr.endswith(inv):  # toelating voor 1962: de stad toont '<id>_<inventarisnummer>'; meestal
                nr = f"{nr}_{inv}" if nr else inv  # staat dat al in fileNumber (Wielelei 85: 214157_329#11928)
            uit.append({"onderwerp": v.get("subject") or v.get("cleanSubject") or "", "dossiernummer": nr,
                        "type": v.get("type") or sub.get("subItemTitle") or "", "beslissing": v.get("decision") or "",
                        "datum": v.get("decisionDateString") or ""})
    return uit


def bouwovertredingen_uit_bron(tile):
    """(samenvatting, lijst) uit het bronantwoord: per overtreding de omschrijving, het dossier en de registratie."""
    lijst = []
    for sub in (tile or {}).get("subLayerItems") or []:
        for cv in sub.get("constructionViolations") or []:
            item = {"omschrijving": sub.get("subItemTitle") or ""}
            for w in cv.get("violations") or []:
                m = re.match(r"(Dossiernummer|Registratienummer):\s*(.+)", str(w.get("value") or ""))
                if m:
                    item[m.group(1).lower()] = m.group(2).strip()
            lijst.append(item)
    return (f"{len(lijst)} vastgesteld" if lijst else "geen gekend"), lijst


LIJSTEN = ("permits", "allotmentPermits", "constructionViolations", "items")  # wat de stad per onderdeel kan tonen
VERWACHT = {"vergunningen": "permits", "bouwovertredingen": "constructionViolations"}


def ontbrekend_in_bron(tile, sectie):
    """Wat in het bronantwoord niet de vorm heeft die we volledig lezen. Een enkel punt en het hele antwoord wordt
    afgewezen (Codex FX28). De stad toont per onderdeel tot vier lijsten (main.js, 17-10-2026); wij lezen er een."""
    sleutel, uit = VERWACHT[sectie], []
    for sub in (tile or {}).get("subLayerItems") or []:
        titel = str(sub.get("subItemTitle") or "zonder titel")[:80]
        rijen = sub.get(sleutel)
        if not isinstance(rijen, list) or not rijen:
            uit.append(f"onderdeel '{titel}' zonder {sleutel}")
            continue
        andere = [k for k in LIJSTEN if k != sleutel and sub.get(k)]
        if andere:
            uit.append(f"onderdeel '{titel}' heeft ook {', '.join(andere)}")
        for r in rijen:
            if not isinstance(r, dict):
                uit.append(f"een rij in '{titel}' is geen gegevensblok")
            elif sectie == "vergunningen" and not (r.get("fileNumber") or r.get("inventoryNumber")):
                uit.append(f"vergunning zonder dossiernummer in '{titel}'")
            elif sectie == "bouwovertredingen":
                w = r.get("violations")
                if not isinstance(w, list) or not all(isinstance(x, dict) for x in w) or not any(
                        re.match(r"(Dossiernummer|Registratienummer):\s*\S", str(x.get("value") or "")) for x in w):
                    uit.append(f"overtreding zonder dossier- of registratienummer in '{titel}'")
    return uit


def _open_met_bron(p, sectie, adres_url, punt):
    """Een sectie openen en de twee antwoorden van de stad opvangen: het perceel (parcelinfo) en de inhoud.

    Geeft (tile, perceel, reden). tile is alleen gevuld als de inhoud over precies de grens van dat perceel gaat, het
    Geopunt-punt erbinnen ligt en de vorm volledig gekend is; anders zegt reden waarom niet.
    """
    tile, perceel, reden = None, None, "het bronantwoord van de stad kwam niet binnen"
    try:
        with p.expect_response(_is_perceelinfo, timeout=90000) as pi, \
                p.expect_response(lambda r: _is_bronantwoord(r, sectie), timeout=90000) as antw:
            p.goto(adres_url, wait_until="domcontentloaded", timeout=90000)
        perceel, reden = _perceel_uit(pi.value, punt)
        r = antw.value
        if perceel is None:
            pass
        elif r.status != 200:
            reden = f"het bronantwoord van de stad gaf status {r.status}"
        elif _grens_van(r) != perceel["geometry"]:
            reden = "het bronantwoord van de stad gaat over een andere perceelgrens"
        else:
            tile = _layer_tile(r.json())
            vorm = ontbrekend_in_bron(tile, sectie) if tile else []
            if tile is None:
                reden = "het bronantwoord van de stad heeft een vorm die we niet kennen"
            elif vorm:
                tile, reden = None, "het bronantwoord van de stad heeft delen die we niet lezen: " + "; ".join(vorm[:3])
    except Exception:
        pass
    if not (p.url or "").startswith(adres_url.split("?")[0]):  # opvangen faalde voor het openen: toch openen,
        p.goto(adres_url, wait_until="domcontentloaded", timeout=90000)  # anders leest de terugval de vorige pagina
    return tile, perceel, reden


def _tabelrijen(p):
    """De rijen van de vergunningentabel op het scherm: onderwerp, dossiernummer, type, beslissing, datum."""
    uit = []
    for cellen in p.evaluate("""() => [...document.querySelectorAll('tr')].filter(tr =>
            tr.querySelector('input[id^="table-checkbox"]:not(#table-checkbox-all)')).map(tr =>
            [...tr.querySelectorAll('td')].map(c => c.innerText.trim()))"""):
        c = [x for x in cellen if x and x != "Selecteer rij"]
        if len(c) >= 3:
            uit.append({"onderwerp": c[0], "dossiernummer": c[1], "type": c[2],
                        "beslissing": c[3] if len(c) > 3 else "", "datum": c[4] if len(c) > 4 else ""})
    return uit


def _scherm_rijen(p, sectie):
    if sectie == "vergunningen":
        return [r["dossiernummer"] for r in _tabelrijen(p)]
    samen, lijst = bouwovertredingen_uit_tekst(_sectietekst(p, "Bouwovertredingen"))
    return [(x.get("dossiernummer", ""), x.get("registratienummer", "")) for x in lijst] if lijst else (
        [] if samen == "geen gekend" else None)


def _scherm_gelijk(p, sectie, verwacht, seconden=30):
    """Toont het scherm van de stad precies de rijen uit de bron, als multiset (ook nul en dubbele nummers)?

    Pas dan klopt de bron met wat een mens ziet en is de printscreen een bewijs (Codex FX29). De tabel pagineert niet
    (main.js, 17-10-2026). Bij nul bouwovertredingen moet het scherm dat ook zeggen; bij nul vergunningen kan het
    scherm geen rij tonen die de bron niet kent.
    """
    doel = Counter(verwacht)
    for _ in range(seconden):
        try:
            rijen = _scherm_rijen(p, sectie)
            if rijen is not None and Counter(rijen) == doel:
                return True
        except Exception:
            pass
        p.wait_for_timeout(1000)
    return False


def lees(ctx, lat, lon, adres, map_=None):
    """Vergunningen en bouwovertredingen van het perceel. Met map_: printscreens en het PDF-rapport van de stad.

    De gegevens komen uit de antwoorden van de stad zelf, niet uit het scherm: een scherm laadt in stukken en een
    tussenstand leek volledig (Codex-rondes 5 tot 7, 17-10-2026). Ze tellen alleen als de keten sluit: onze
    Geopunt-coordinaten, het perceel van de stad, de grens van dat perceel, de inhoud voor die grens, en een scherm dat
    dezelfde rijen toont (ontwerpronde 10). Elke controle die slaagt, staat in 'controles'; wat niet slaagt, in
    'fouten'. Zonder bruikbaar antwoord lezen we het scherm, zeggen we dat erbij en is het resultaat onvolledig.
    """
    uit = {"url": url("vergunningen", lat, lon, adres), "capakey": "", "vergunningen": [], "bouwovertredingen": "",
           "bouwovertredingen_lijst": [], "bewijs": [], "fouten": [], "bron": {}, "perceel": None,
           "controles": {}, "gelezen": {"vergunningen": False, "bouwovertredingen": False}}
    c, percelen = uit["controles"], {}
    if map_:
        os.makedirs(map_, exist_ok=True)
    p = ctx.new_page()
    try:
        try:
            tile, percelen["vergunningen"], reden = _open_met_bron(p, "vergunningen", uit["url"], (lat, lon))
            try:
                p.wait_for_selector("text=Toelatingen die voor 1962", timeout=60000)
            except Exception:
                if tile is None:
                    raise
            _cookies_weigeren(p)
            if tile is not None:
                uit["vergunningen"] = vergunningen_uit_bron(tile)
                uit["bron"]["vergunningen"] = "bronantwoord van de stad"
                c["vergunningen_bron"] = True
                c["vergunningen_scherm"] = _scherm_gelijk(p, "vergunningen", [v["dossiernummer"] for v in uit["vergunningen"]])
                if not c["vergunningen_scherm"]:
                    uit["fouten"].append("vergunningen: het scherm van de stad toonde na 30 s niet dezelfde rijen als de bron")
            else:
                uit["vergunningen"] = _vergunningen_van_scherm(p)
                uit["bron"]["vergunningen"] = f"scherm ({reden})"
                uit["fouten"].append(NIET_BEVESTIGD.format("vergunningen", reden))
            uit["gelezen"]["vergunningen"] = True
            uit["capakey"] = percelen["vergunningen"]["capakey"] if percelen["vergunningen"] else _capakey(p)
        except Exception as e:
            uit["fouten"].append(f"vergunningen van de stad niet gelezen: {str(e).splitlines()[0][:150]}")
        if map_ and uit["gelezen"]["vergunningen"]:
            if _printscreen(p, os.path.join(map_, "Vergunningen.png"), uit["fouten"]):
                uit["bewijs"].append(os.path.join(map_, "Vergunningen.png"))
            try:  # het volledige rapport van de stad, via de knop PDF
                with p.expect_download(timeout=180000) as d:
                    p.get_by_role("button", name="PDF").click(timeout=60000)
                naam = d.value.suggested_filename or f"rapport_{uit['capakey'].replace('/', '_')}.pdf"
                pad = os.path.join(map_, naam)
                d.value.save_as(pad)
                uit["bewijs"].append(pad)
            except Exception as e:
                uit["fouten"].append(f"PDF-rapport van de stad niet gelukt: {str(e).splitlines()[0][:150]}")

        try:
            tile, percelen["bouwovertredingen"], reden = _open_met_bron(
                p, "bouwovertredingen", url("bouwovertredingen", lat, lon, adres), (lat, lon))
            if tile is not None:
                samen, lijst = bouwovertredingen_uit_bron(tile)
                uit["bron"]["bouwovertredingen"] = "bronantwoord van de stad"
                c["bouwovertredingen_bron"] = True
                c["bouwovertredingen_scherm"] = _scherm_gelijk(p, "bouwovertredingen", [
                    (x.get("dossiernummer", ""), x.get("registratienummer", "")) for x in lijst])
                if not c["bouwovertredingen_scherm"]:
                    uit["fouten"].append("bouwovertredingen: het scherm van de stad toonde na 30 s niet dezelfde rijen als de bron")
            else:
                samen, lijst = _bouwovertredingen_van_scherm(p)
                uit["bron"]["bouwovertredingen"] = f"scherm ({reden})"
                uit["fouten"].append(NIET_BEVESTIGD.format("bouwovertredingen", reden))
            uit["bouwovertredingen"], uit["bouwovertredingen_lijst"] = samen, lijst
            uit["gelezen"]["bouwovertredingen"] = True
            if map_ and _printscreen(p, os.path.join(map_, "Bouwovertredingen.png"), uit["fouten"]):
                uit["bewijs"].append(os.path.join(map_, "Bouwovertredingen.png"))
        except Exception as e:
            uit["fouten"].append(f"bouwovertredingen van de stad niet gelezen: {str(e).splitlines()[0][:150]}")
    finally:
        try:
            p.close()
        except Exception:
            pass  # een fout bij het sluiten mag het gelezen resultaat niet wegvegen (Codex FX04)

    pv, pb = percelen.get("vergunningen"), percelen.get("bouwovertredingen")
    c["perceel"] = bool(pv and pb and pv["capakey"] == pb["capakey"] and pv["geometry"] == pb["geometry"])
    if pv and pb and not c["perceel"]:
        uit["fouten"].append("de twee secties van de stad gaan over een ander perceel")
    uit["perceel"] = {k: v for k, v in pv.items() if k != "geometry"} if pv else None
    return uit


def _capakey(p):
    for _ in range(30):
        m = re.search(r"\b" + CAPAKEY + r"\b", p.locator("body").inner_text())
        if m:
            return m.group()
        p.wait_for_timeout(2000)
    return ""


def _vergunningen_van_scherm(p):
    """Terugval: de tabel van het scherm, pas als ze expliciet en twee keer na elkaar gelijk is (ontwerpronde 7)."""
    vorige = None
    for _ in range(45):
        tekst = p.locator("body").inner_text()
        rijen_klaar = p.evaluate("""() => document.querySelectorAll(
                'tr input[id^="table-checkbox"]:not(#table-checkbox-all)').length""")
        stand = (rijen_klaar, "geen vergunningen" in tekst)
        uitkomst = rijen_klaar > 0 or "geen vergunningen" in tekst
        if uitkomst and stand == vorige:
            break
        vorige = stand if uitkomst else None
        p.wait_for_timeout(2000)
    else:
        raise RuntimeError("tabel niet stabiel geladen na 90 seconden")
    return _tabelrijen(p)


def _bouwovertredingen_van_scherm(p):
    """Terugval: de sectie van het scherm, pas als de uitkomst expliciet en twee keer na elkaar gelijk is."""
    vorige = None
    for _ in range(45):
        sectie = _sectietekst(p, "Bouwovertredingen")
        samen, lijst = bouwovertredingen_uit_tekst(sectie)
        uitkomst = samen == "geen gekend" or (UITKOMST_WEL in sectie and lijst)
        if uitkomst and sectie == vorige:
            return samen, lijst
        vorige = sectie if uitkomst else None
        p.wait_for_timeout(2000)
    raise RuntimeError("geen volledige, stabiele uitkomst voor de bouwovertredingen na 90 seconden")

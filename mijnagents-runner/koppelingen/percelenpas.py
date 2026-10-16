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
import math
import os
import re
import urllib.parse

BASIS = "https://omgeving.antwerpen.be/percelenpas"
UITKOMST_GEEN = "Er zijn geen gekende bouwovertredingen"
UITKOMST_WEL = "Vastgestelde bouwovertredingen"
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
    geen bouwovertredingen). None bij elke andere vorm, ook een blok zonder layerTile of zonder subLayerItems: dan
    lezen we het scherm en is het resultaat onvolledig (Codex FX28).
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
        subs += [s for s in tile["subLayerItems"] if isinstance(s, dict)]
    return {"subLayerItems": subs}


def _is_bronantwoord(r, sectie):
    """Het antwoord van de stad voor precies deze sectie: de aanvraag zegt '"url": "/percelenpas/<sectie>"'."""
    if "content-with-gis-by-slug" not in r.url:
        return False
    try:
        return json.loads(r.request.post_data or "{}").get("url") == f"/percelenpas/{sectie}"
    except Exception:
        return False


def _binnen(punt, veelhoek, marge_m=3.0):
    """Ligt het Geopunt-punt (lat, lon) in het perceel dat de stad opvroeg, of op minder dan marge_m van de rand?

    De stad stuurt de perceelgrens mee in de aanvraag als [{"x": lat, "y": lon}, ...] (gemeten 17-10-2026).
    """
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
    if binnen:
        return True
    fy, fx = 110540.0, 111320.0 * math.cos(math.radians(lat))  # meter per graad breedte en lengte
    for (x1, y1), (x2, y2) in zip(hoeken, hoeken[1:] + hoeken[:1]):
        ax, ay, bx, by = (y1 - lon) * fx, (x1 - lat) * fy, (y2 - lon) * fx, (x2 - lat) * fy
        dx, dy = bx - ax, by - ay
        k = max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy))) if dx or dy else 0.0
        if math.hypot(ax + k * dx, ay + k * dy) <= marge_m:
            return True
    return False


def _zelfde_perceel(r, punt):
    """Hoort het antwoord bij het perceel van het Geopunt-adres? Elk ander perceel telt niet (Codex FX27)."""
    try:
        return _binnen(punt, json.loads(r.request.post_data or "{}").get("geometry") or [])
    except Exception:
        return False


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
    """(samenvatting, lijst) uit het bronantwoord: per overtreding de omschrijving, het dossier en de registratie.

    Een onderdeel zonder dossiergegevens telt mee met zijn omschrijving; ontbrekend_in_bron() meldt het.
    """
    lijst = []
    for sub in (tile or {}).get("subLayerItems") or []:
        groepen = sub.get("constructionViolations") or [{}]
        for cv in groepen:
            item = {"omschrijving": sub.get("subItemTitle") or ""}
            for w in (cv.get("violations") if isinstance(cv, dict) else None) or []:
                m = re.match(r"(Dossiernummer|Registratienummer):\s*(.+)", str(w.get("value") or ""))
                if m:
                    item[m.group(1).lower()] = m.group(2).strip()
            lijst.append(item)
    return (f"{len(lijst)} vastgesteld" if lijst else "geen gekend"), lijst


LIJSTEN = ("permits", "allotmentPermits", "constructionViolations", "items")  # wat de stad per onderdeel kan tonen
VERWACHT = {"vergunningen": "permits", "bouwovertredingen": "constructionViolations"}


def ontbrekend_in_bron(tile, sectie):
    """Wat de stad doorgeeft maar wij niet volledig lezen. Elk punt maakt het resultaat onvolledig (Codex FX28).

    De stad toont per onderdeel tot vier lijsten (main.js, 17-10-2026); wij lezen er per sectie een.
    """
    sleutel, uit = VERWACHT[sectie], []
    for sub in (tile or {}).get("subLayerItems") or []:
        titel = (sub.get("subItemTitle") or "zonder titel")[:80]
        rijen = sub.get(sleutel)
        if not isinstance(rijen, list) or not rijen:
            uit.append(f"onderdeel '{titel}' zonder {sleutel}")
            continue
        andere = [k for k in LIJSTEN if k != sleutel and sub.get(k)]
        if andere:
            uit.append(f"onderdeel '{titel}' heeft ook {', '.join(andere)}")
        for r in rijen:
            if sectie == "vergunningen" and not (r.get("fileNumber") or r.get("inventoryNumber")):
                uit.append(f"vergunning zonder dossiernummer in '{titel}'")
            if sectie == "bouwovertredingen" and not any(
                    re.match(r"(Dossiernummer|Registratienummer):\s*\S", str(w.get("value") or ""))
                    for w in (r.get("violations") if isinstance(r, dict) else None) or []):
                uit.append(f"overtreding zonder dossier- of registratienummer in '{titel}'")
    return uit


def _open_met_bron(p, sectie, adres_url, punt):
    """Een sectie openen en het bronantwoord van de stad voor die sectie en dit perceel opvangen.

    Geeft (tile, reden): tile is None als er geen bruikbaar antwoord is, en reden zegt dan waarom.
    """
    tile, reden = None, "het bronantwoord van de stad kwam niet binnen"
    try:
        with p.expect_response(lambda r: _is_bronantwoord(r, sectie), timeout=90000) as antw:
            p.goto(adres_url, wait_until="domcontentloaded", timeout=90000)
        r = antw.value
        if r.status != 200:
            reden = f"het bronantwoord van de stad gaf status {r.status}"
        elif not _zelfde_perceel(r, punt):
            reden = "het bronantwoord van de stad hoort bij een ander perceel dan het Geopunt-adres"
        else:
            tile = _layer_tile(r.json())
            if tile is None:
                reden = "het bronantwoord van de stad heeft een vorm die we niet kennen"
    except Exception:
        pass
    if not (p.url or "").startswith(adres_url.split("?")[0]):  # opvangen faalde voor het openen: toch openen,
        p.goto(adres_url, wait_until="domcontentloaded", timeout=90000)  # anders leest de terugval de vorige pagina
    return tile, reden


def _scherm_volgt_bron(p, sleutels, seconden=30):
    """Toont het scherm alles wat de stad doorgaf? Pas dan is de printscreen een bewijs (Codex FX29).

    De tabel van de stad pagineert niet (main.js, 17-10-2026), dus elk dossiernummer staat op het scherm.
    """
    for _ in range(seconden):
        tekst = p.locator("body").inner_text()
        if all(s in tekst for s in sleutels):
            return True
        p.wait_for_timeout(1000)
    return False


def lees(ctx, lat, lon, adres, map_=None):
    """Vergunningen en bouwovertredingen van het perceel. Met map_: printscreens en het PDF-rapport van de stad.

    De gegevens komen uit het bronantwoord van de stad (een JSON per sectie), niet uit het scherm: een scherm laadt in
    stukken en een tussenstand leek volledig (Codex-rondes 5 tot 7, 17-10-2026). Het antwoord telt alleen voor de
    eigen sectie en het perceel van het Geopunt-adres (Codex FX27). Komt er geen bruikbaar antwoord, dan lezen we het
    scherm met de regel 'expliciet en twee keer gelijk', zeggen we dat erbij en is het resultaat onvolledig.
    """
    uit = {"url": url("vergunningen", lat, lon, adres), "capakey": "", "vergunningen": [], "bouwovertredingen": "",
           "bouwovertredingen_lijst": [], "bewijs": [], "fouten": [], "bron": {},
           "gelezen": {"vergunningen": False, "bouwovertredingen": False}}
    if map_:
        os.makedirs(map_, exist_ok=True)
    p = ctx.new_page()
    try:
        try:
            tile, reden = _open_met_bron(p, "vergunningen", uit["url"], (lat, lon))
            try:
                p.wait_for_selector("text=Toelatingen die voor 1962", timeout=60000)
            except Exception:
                if tile is None:
                    raise
            _cookies_weigeren(p)
            if tile is not None:
                uit["vergunningen"] = vergunningen_uit_bron(tile)
                uit["bron"]["vergunningen"] = "bronantwoord van de stad"
                uit["fouten"] += [f"vergunningen, niet volledig gelezen: {x}" for x in ontbrekend_in_bron(tile, "vergunningen")]
            else:
                uit["vergunningen"] = _vergunningen_van_scherm(p)
                uit["bron"]["vergunningen"] = f"scherm ({reden})"
                uit["fouten"].append(NIET_BEVESTIGD.format("vergunningen", reden))
            uit["gelezen"]["vergunningen"] = True
            uit["capakey"] = _capakey(p)
        except Exception as e:
            uit["fouten"].append(f"vergunningen van de stad niet gelezen: {str(e).splitlines()[0][:150]}")
        if map_ and uit["gelezen"]["vergunningen"]:
            if uit["bron"]["vergunningen"] == "bronantwoord van de stad" and not _scherm_volgt_bron(
                    p, [v["dossiernummer"] for v in uit["vergunningen"]] or ["geen vergunningen"]):
                uit["fouten"].append("Vergunningen.png: het scherm toonde na 30 s nog niet alles wat de stad doorgaf")
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
            tile, reden = _open_met_bron(p, "bouwovertredingen", url("bouwovertredingen", lat, lon, adres), (lat, lon))
            if tile is not None:
                samen, lijst = bouwovertredingen_uit_bron(tile)
                uit["bron"]["bouwovertredingen"] = "bronantwoord van de stad"
                uit["fouten"] += [f"bouwovertredingen, niet volledig gelezen: {x}"
                                  for x in ontbrekend_in_bron(tile, "bouwovertredingen")]
            else:
                samen, lijst = _bouwovertredingen_van_scherm(p)
                uit["bron"]["bouwovertredingen"] = f"scherm ({reden})"
                uit["fouten"].append(NIET_BEVESTIGD.format("bouwovertredingen", reden))
            uit["bouwovertredingen"], uit["bouwovertredingen_lijst"] = samen, lijst
            uit["gelezen"]["bouwovertredingen"] = True
            if map_:
                sleutels = [x[k] for x in lijst for k in ("dossiernummer", "registratienummer") if x.get(k)]
                if uit["bron"]["bouwovertredingen"] == "bronantwoord van de stad" and not _scherm_volgt_bron(
                        p, sleutels or [UITKOMST_GEEN]):
                    uit["fouten"].append("Bouwovertredingen.png: het scherm toonde na 30 s nog niet alles wat de stad doorgaf")
                if _printscreen(p, os.path.join(map_, "Bouwovertredingen.png"), uit["fouten"]):
                    uit["bewijs"].append(os.path.join(map_, "Bouwovertredingen.png"))
        except Exception as e:
            uit["fouten"].append(f"bouwovertredingen van de stad niet gelezen: {str(e).splitlines()[0][:150]}")
    finally:
        try:
            p.close()
        except Exception:
            pass  # een fout bij het sluiten mag het gelezen resultaat niet wegvegen (Codex FX04)
    return uit


def _capakey(p):
    for _ in range(30):
        m = re.search(r"\b\d{5}[A-Z]\d{4}/\d{2}[A-Z]\d{3}\b", p.locator("body").inner_text())
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
    uit = []
    for cellen in p.evaluate("""() => [...document.querySelectorAll('tr')].filter(tr =>
            tr.querySelector('input[id^="table-checkbox"]:not(#table-checkbox-all)')).map(tr =>
            [...tr.querySelectorAll('td')].map(c => c.innerText.trim()))"""):
        c = [x for x in cellen if x and x != "Selecteer rij"]
        if len(c) >= 3:
            uit.append({"onderwerp": c[0], "dossiernummer": c[1], "type": c[2],
                        "beslissing": c[3] if len(c) > 3 else "", "datum": c[4] if len(c) > 4 else ""})
    return uit


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

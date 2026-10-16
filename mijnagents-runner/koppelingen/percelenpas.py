"""De percelenpas van de stad Antwerpen (omgeving.antwerpen.be/percelenpas): alles wat de stad over een perceel weet.

Zoekt op het perceel, niet op het huisnummer. Toont de vergunningen die bij de dienst Omgeving en FelixArchief gekend
zijn (ook recente die nog niet in FelixArchief zitten), de bouwovertredingen, voorschriften en erfgoed. De knop PDF
geeft het volledige rapport (rapport_<perceel>.pdf).

Altijd openen met de coordinaten van Geopunt, nooit via het zoekveld: een collega kwam op 02-10-2026 via het zoekveld
op het verkeerde perceel uit (11345B0117 in plaats van 11344A0430) en zag daardoor "geen vergunningen".

Dossiers opvragen bij de stad vraagt aanmelden met Itsme of eID (hoger zekerheidsniveau, gemeten 03-10-2026); dat kan
de server niet. Die stap zetten we klaar voor Mehdi.
"""
import os
import re
import urllib.parse

BASIS = "https://omgeving.antwerpen.be/percelenpas"
UITKOMST_GEEN = "Er zijn geen gekende bouwovertredingen"
UITKOMST_WEL = "Vastgestelde bouwovertredingen"


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
    """Het deel van het bronantwoord met de gegevens van het perceel (content-with-gis-by-slug)."""
    try:
        return antwoord["fields"]["content"]["content"][0]["value"]["layerTile"] or {}
    except (KeyError, IndexError, TypeError):
        return None


def vergunningen_uit_bron(tile):
    """De vergunningen uit het bronantwoord van de stad. Een antwoord is volledig, een scherm dat laadt niet."""
    uit = []
    for sub in (tile or {}).get("subLayerItems") or []:
        for v in sub.get("permits") or []:
            nr = str(v.get("fileNumber") or "")
            if v.get("inventoryNumber"):  # toelating voor 1962: de stad toont '<id>_<inventarisnummer>'
                nr = f"{nr}_{v['inventoryNumber']}" if nr else str(v["inventoryNumber"])
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


def _open_met_bron(p, adres_url):
    """Een sectie openen en het bronantwoord van de stad opvangen (content-with-gis-by-slug), of None."""
    tile = None
    try:
        with p.expect_response(lambda r: "content-with-gis-by-slug" in r.url, timeout=90000) as antw:
            p.goto(adres_url, wait_until="domcontentloaded", timeout=90000)
        if antw.value.status == 200:
            tile = _layer_tile(antw.value.json())
    except Exception:
        pass
    if not (p.url or "").startswith(adres_url.split("?")[0]):  # opvangen faalde voor het openen: toch openen,
        p.goto(adres_url, wait_until="domcontentloaded", timeout=90000)  # anders leest de terugval de vorige pagina
    return tile


def lees(ctx, lat, lon, adres, map_=None):
    """Vergunningen en bouwovertredingen van het perceel. Met map_: printscreens en het PDF-rapport van de stad.

    De gegevens komen uit het bronantwoord van de stad (een JSON per sectie), niet uit het scherm: een scherm laadt in
    stukken en een tussenstand leek volledig (Codex-rondes 5 tot 7, 17-10-2026). Alleen als het bronantwoord niet
    binnenkomt, lezen we het scherm met de regel 'expliciet en twee keer gelijk', en zeggen we dat erbij.
    """
    uit = {"url": url("vergunningen", lat, lon, adres), "capakey": "", "vergunningen": [], "bouwovertredingen": "",
           "bouwovertredingen_lijst": [], "bewijs": [], "fouten": [], "bron": {},
           "gelezen": {"vergunningen": False, "bouwovertredingen": False}}
    if map_:
        os.makedirs(map_, exist_ok=True)
    p = ctx.new_page()
    try:
        try:
            tile = _open_met_bron(p, uit["url"])
            p.wait_for_selector("text=Toelatingen die voor 1962", timeout=60000)
            _cookies_weigeren(p)
            if tile is not None:
                uit["vergunningen"] = vergunningen_uit_bron(tile)
                uit["bron"]["vergunningen"] = "bronantwoord van de stad"
            else:
                uit["vergunningen"] = _vergunningen_van_scherm(p)
                uit["bron"]["vergunningen"] = "scherm (bronantwoord niet ontvangen)"
            uit["gelezen"]["vergunningen"] = True
            uit["capakey"] = _capakey(p)
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
            tile = _open_met_bron(p, url("bouwovertredingen", lat, lon, adres))
            if tile is not None:
                samen, lijst = bouwovertredingen_uit_bron(tile)
                uit["bron"]["bouwovertredingen"] = "bronantwoord van de stad"
            else:
                samen, lijst = _bouwovertredingen_van_scherm(p)
                uit["bron"]["bouwovertredingen"] = "scherm (bronantwoord niet ontvangen)"
            uit["bouwovertredingen"], uit["bouwovertredingen_lijst"] = samen, lijst
            uit["gelezen"]["bouwovertredingen"] = True
            if map_:
                p.wait_for_timeout(2500)  # het scherm volgt het bronantwoord; de printscreen is het bewijs
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

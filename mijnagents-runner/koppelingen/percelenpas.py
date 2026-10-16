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


def lees(ctx, lat, lon, adres, map_=None):
    """Vergunningen en bouwovertredingen van het perceel. Met map_: printscreens en het PDF-rapport van de stad.

    Elke stap staat los: wat gelezen is, blijft, ook als een printscreen of de PDF faalt. 'gelezen' zegt welke
    gegevens er volledig zijn; wat ontbreekt staat in 'fouten'.
    """
    uit = {"url": url("vergunningen", lat, lon, adres), "capakey": "", "vergunningen": [], "bouwovertredingen": "",
           "bouwovertredingen_lijst": [], "bewijs": [], "fouten": [], "gelezen": {"vergunningen": False, "bouwovertredingen": False}}
    if map_:
        os.makedirs(map_, exist_ok=True)
    p = ctx.new_page()
    try:
        try:
            p.goto(uit["url"], wait_until="domcontentloaded", timeout=90000)
            p.wait_for_selector("text=Toelatingen die voor 1962", timeout=60000)
            _cookies_weigeren(p)
            # De inleiding staat er meteen, het perceel en de tabel komen later (17-10-2026: na 15 s nog een lege
            # tabel en geen perceel, terwijl hetzelfde adres eerder 5 vergunningen gaf). Wachten op beide.
            m = None
            for _ in range(45):
                tekst = p.locator("body").inner_text()
                m = re.search(r"\b\d{5}[A-Z]\d{4}/\d{2}[A-Z]\d{3}\b", tekst)
                if m and ("Dossiernummer" in tekst or "geen vergunningen" in tekst):
                    break
                p.wait_for_timeout(2000)
            else:
                raise RuntimeError("perceel of tabel niet geladen na 90 seconden")
            p.wait_for_timeout(1500)
            uit["capakey"] = m.group()
            for cellen in p.evaluate("""() => [...document.querySelectorAll('tr')].map(tr =>
                    [...tr.querySelectorAll('td')].map(c => c.innerText.trim()))"""):
                c = [x for x in cellen if x and x != "Selecteer rij"]
                if len(c) >= 3:
                    uit["vergunningen"].append({"onderwerp": c[0], "dossiernummer": c[1], "type": c[2],
                                                "beslissing": c[3] if len(c) > 3 else "", "datum": c[4] if len(c) > 4 else ""})
            uit["gelezen"]["vergunningen"] = True
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
            p.goto(url("bouwovertredingen", lat, lon, adres), wait_until="domcontentloaded", timeout=90000)
            p.wait_for_selector("text=proces-verbaal", timeout=60000)
            p.wait_for_timeout(1500)
            samen, lijst = bouwovertredingen_uit_tekst(_sectietekst(p, "Bouwovertredingen"))
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
    return uit

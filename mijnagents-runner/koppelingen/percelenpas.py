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


def lees(ctx, lat, lon, adres, map_=None):
    """Vergunningen en bouwovertredingen van het perceel. Met map_: printscreens en het PDF-rapport van de stad."""
    uit = {"url": url("vergunningen", lat, lon, adres), "capakey": "", "vergunningen": [], "bouwovertredingen": "",
           "bewijs": [], "fouten": []}
    p = ctx.new_page()
    try:
        p.goto(uit["url"], wait_until="domcontentloaded", timeout=60000)
        p.wait_for_selector("text=Toelatingen die voor 1962", timeout=45000)
        _cookies_weigeren(p)
        try:
            p.wait_for_selector("text=Dossiernummer", timeout=15000)
        except Exception:
            pass  # geen vergunningen: de pagina zegt dat zelf
        p.wait_for_timeout(1500)
        m = re.search(r"\b\d{5}[A-Z]\d{4}/\d{2}[A-Z]\d{3}\b", p.locator("body").inner_text())
        uit["capakey"] = m.group() if m else ""
        for cellen in p.evaluate("""() => [...document.querySelectorAll('tr')].map(tr =>
                [...tr.querySelectorAll('td')].map(c => c.innerText.trim()))"""):
            c = [x for x in cellen if x and x != "Selecteer rij"]
            if len(c) >= 3:
                uit["vergunningen"].append({"onderwerp": c[0], "dossiernummer": c[1], "type": c[2],
                                            "beslissing": c[3] if len(c) > 3 else "", "datum": c[4] if len(c) > 4 else ""})
        if map_:
            os.makedirs(map_, exist_ok=True)
            pad = os.path.join(map_, "Vergunningen.png")
            p.screenshot(path=pad, full_page=True)
            uit["bewijs"].append(pad)
            try:  # het volledige rapport van de stad, via de knop PDF
                with p.expect_download(timeout=180000) as d:
                    p.get_by_role("button", name="PDF").click(timeout=15000)
                naam = d.value.suggested_filename or f"rapport_{uit['capakey'].replace('/', '_')}.pdf"
                pad = os.path.join(map_, naam)
                d.value.save_as(pad)
                uit["bewijs"].append(pad)
            except Exception as e:
                uit["fouten"].append(f"PDF-rapport van de stad niet gelukt: {str(e).splitlines()[0][:150]}")

        p.goto(url("bouwovertredingen", lat, lon, adres), wait_until="domcontentloaded", timeout=60000)
        p.wait_for_selector("text=proces-verbaal", timeout=45000)
        p.wait_for_timeout(1500)
        uit["bouwovertredingen"] = _sectietekst(p, "Bouwovertredingen").split("\n")[-1].strip()
        if map_:
            pad = os.path.join(map_, "Bouwovertredingen.png")
            p.screenshot(path=pad, full_page=True)
            uit["bewijs"].append(pad)
    finally:
        p.close()
    return uit

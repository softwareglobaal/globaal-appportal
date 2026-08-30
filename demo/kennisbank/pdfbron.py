"""Bladzijden uit een PDF met een tekstlaag.

Dit is de goedkope route en voor de meeste zakelijke documenten de enige die je
nodig hebt: een digitaal opgemaakte PDF draagt zijn tekst al bij zich, met
lettergrootte en plaats op de bladzijde erbij. Daaruit is af te leiden wat kop,
voet en titel is -- precies de typering die de OCR bij een scan levert, alleen
gratis en zonder wachten.

Een gescand document heeft die tekstlaag niet. Dan is OCR onvermijdelijk, en dat
kost geld per bladzijde. `verkenning()` stelt dat vast voordat er iets verwerkt
wordt, zodat de kosten op tafel liggen voor de eerste aanroep in plaats van erna.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from pathlib import Path

from .ocrbron import Blad, Blok

# Prijs per bladzijde voor de OCR-route, gemeten op claude-sonnet-5.
OCR_PRIJS_PER_BLAD = 0.0156
# Onder dit aantal tekens per bladzijde is er geen bruikbare tekstlaag.
TEKENS_PER_BLAD_DREMPEL = 60
KOP_BAND = 0.08          # bovenste deel van de bladzijde
VOET_BAND = 0.90         # alles hieronder is voettekst
TITEL_FACTOR = 1.15      # zoveel groter dan de gangbare letter is een kop
TITEL_MAX_TEKENS = 160


@dataclass
class Verkenning:
    bladzijden: int
    tekens: int
    heeft_tekstlaag: bool
    route: str                    # 'tekstlaag' of 'ocr'
    geschatte_kosten: float
    versleuteld: bool = False
    fout: str = ""


def verken(pad: Path) -> Verkenning:
    """Wat voor document is dit, en wat gaat het kosten?"""
    import fitz
    try:
        doc = fitz.open(pad)
    except Exception as e:                                     # noqa: BLE001
        return Verkenning(0, 0, False, "onbekend", 0.0, fout=str(e))
    if doc.needs_pass:
        doc.close()
        return Verkenning(0, 0, False, "onbekend", 0.0, versleuteld=True,
                          fout="het bestand is met een wachtwoord beveiligd")

    per_blad = [len(p.get_text().strip()) for p in doc]
    n = doc.page_count
    doc.close()

    tekens = sum(per_blad)
    met_tekst = sum(1 for t in per_blad if t >= TEKENS_PER_BLAD_DREMPEL)
    heeft = n > 0 and met_tekst / n >= 0.5
    return Verkenning(
        bladzijden=n, tekens=tekens, heeft_tekstlaag=heeft,
        route="tekstlaag" if heeft else "ocr",
        geschatte_kosten=0.0 if heeft else round(n * OCR_PRIJS_PER_BLAD, 2),
    )


def _soort(y0: float, y1: float, hoogte: float, grootte: float,
           gangbaar: float, tekens: int) -> str:
    if hoogte > 0:
        if y1 <= KOP_BAND * hoogte:
            return "kop"
        if y0 >= VOET_BAND * hoogte:
            return "voet"
    if grootte >= gangbaar * TITEL_FACTOR and tekens <= TITEL_MAX_TEKENS:
        return "titel"
    return "tekst"


def laad(pad: Path) -> list[Blad]:
    """Zet een PDF met tekstlaag om in bladzijden met getypeerde blokken.

    De typering komt uit plaats en lettergrootte. Dat is een heuristiek en geen
    zekerheid, maar hij is deterministisch: dezelfde PDF levert altijd dezelfde
    indeling, en dat is precies wat een kennisbank nodig heeft om herbouwbaar te
    zijn.
    """
    import fitz

    doc = fitz.open(pad)
    # De gangbare lettergrootte van het hele document, niet per bladzijde: op een
    # titelpagina is alles groot en dan zou daar niets als kop opvallen.
    groottes: list[float] = []
    for blad in doc:
        for blok in blad.get_text("dict")["blocks"]:
            for regel in blok.get("lines", []):
                for stuk in regel.get("spans", []):
                    if (stuk.get("text") or "").strip():
                        groottes.append(round(stuk.get("size", 0), 1))
    gangbaar = statistics.median(groottes) if groottes else 10.0

    bladen: list[Blad] = []
    for nr, blad in enumerate(doc, start=1):
        hoogte = blad.rect.height
        blokken: list[Blok] = []
        stukken: list[str] = []
        for blok in blad.get_text("dict")["blocks"]:
            regels, maat = [], 0.0
            for regel in blok.get("lines", []):
                tekst = "".join(s.get("text", "") for s in regel.get("spans", []))
                if tekst.strip():
                    regels.append(tekst.rstrip())
                    maat = max(maat, *(s.get("size", 0)
                                       for s in regel.get("spans", [{"size": 0}])))
            if not regels:
                continue
            tekst = "\n".join(regels).strip()
            y0, y1 = blok["bbox"][1], blok["bbox"][3]
            blokken.append(Blok(_soort(y0, y1, hoogte, maat, gangbaar, len(tekst)),
                                tekst))
            stukken.append(tekst)
        bladen.append(Blad(fysiek=nr, markdown="\n\n".join(stukken),
                           blokken=blokken))
    doc.close()
    return bladen

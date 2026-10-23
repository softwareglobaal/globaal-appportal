"""Schrijfregels van H-Architects voor elk verslag dat een agent of Claude schrijft (werfverslag, plaatsbezoek,
verslag van bevindingen, proces-verbaal). Dit is de grendel: wat hier verboden is, komt nooit in een concept.

Aanleiding (Mehdi, 23-10-2026, over het concept 2309 Verslag van bevindingen): het concept zei dat uit de stukken
geen eerder bezoek van het bureau bleek, en verwees bij elke vaststelling naar de opname "(opname 00:22:30)".
Dat mag nooit. De regels:

S1  Geen uitspraak over de architect of het bureau zelf: niet over zijn (niet-)aanwezigheid, eerdere bezoeken,
    opdrachtomvang, verplichtingen, fouten of verzuim. Het hoofdstuk "Rol van H-Architects" vult alleen Mehdi in.
S2  Geen verwijzing naar de deontologie, het reglement of de Orde van Architecten, en nooit het oordeel dat iets
    "tegen de deontologie" of "tegen de regels van de Orde" is. Dat oordeel is aan de Orde, niet aan een verslag.
S3  Geen oordeel over een collega-architect of een ander bureau (eerder niet geweest, slecht gevolgd, nalatig).
S4  Geen verwijzing naar de opname in de tekst: geen "(opname 00:22:30)", geen "sprak zijn vaststellingen in".
    Tijdstippen blijven in de brongegevens (het veld bron) voor de controle, nooit in het verslag.
S5  Geen juridische kwalificatie (aansprakelijk, in gebreke, contractbreuk, wanprestatie): vaststellen en beschrijven,
    de rest is voor de raadsman. (Bestond al; staat hier zodat de grendel ze samen toetst.)

Werking: `toepassen(tekst)` schrapt opnameverwijzingen en vervangt een verboden zin door een zichtbare markering met
het regelnummer, zodat Mehdi ziet dat er iets geschrapt is en de schrijver het niet stil laat staan. `wacht(verslag)`
doet dat voor elk tekstveld van een verslag-dict (werfverslag of verslag van bevindingen) en geeft de ingrepen terug;
`controleer(tekst)` meldt alleen. Het document voor Mehdi: docs/Werfverslagen - schrijfregels v1.0.md.
"""
import re

MARKERING = "(geschrapt: schrijfregel {regel}, zie de schrijfregels van het kantoor)"

# (regel, patroon) op zinsniveau; hoofdletterongevoelig. Een zin die matcht, wordt in zijn geheel vervangen.
VERBODEN = [
    ("S2", re.compile(r"deontolog", re.I)),
    ("S2", re.compile(r"\borde\s+van\s+(de\s+)?architect", re.I)),
    ("S2", re.compile(r"\b(reglement|plichtenleer)\s+van\s+(de\s+)?(orde|architect)", re.I)),
    ("S3", re.compile(r"\b(vorige|eerdere|andere|collega)[- ]architect\b[^.]{0,80}\b(niet|nooit|slecht|nalatig|fout)", re.I)),
    ("S1", re.compile(r"\b(geen|niet)\s+(eerder|vroeger|voordien|tevoren)\s+\w*\s*(bezoek|bezocht|geweest|gekomen|aanwezig|gecontroleerd|opgevolgd|ter plaatse)", re.I)),
    ("S1", re.compile(r"\b(eerder|vroeger|voordien|tevoren)\s+(geen|niet)\s+\w*\s*(bezoek|bezocht|geweest|gekomen|aanwezig|gecontroleerd|opgevolgd|ter plaatse)", re.I)),
    ("S1", re.compile(r"\b(blijkt|bleek)\s+geen\s+(eerder|vroeger)\s+\w*\s*(bezoek|controle|tussenkomst)", re.I)),
    ("S1", re.compile(r"\b(de\s+)?(architect|het\s+bureau|h-architects)\b[^.]{0,60}\b(niet|nooit)\s+(geweest|gekomen|aanwezig|langsgekomen|bezocht|gecontroleerd|opgevolgd)", re.I)),
    ("S1", re.compile(r"\b(architect|bureau)\b[^.]{0,40}\b(verzuim|nalatig|tekortgeschoten|in gebreke|zijn plicht|haar plicht)", re.I)),
    ("S1", re.compile(r"\b(hoogstens|maximaal|slechts|maar)\s+(één|een|1)\s+(controle)?bezoek", re.I)),
    ("S3", re.compile(r"\b(vorige|eerdere|andere|collega)[- ]architect\b[^.]{0,80}\b(niet|nooit|slecht|nalatig|fout)", re.I)),
    ("S5", re.compile(r"\b(aansprakelijk|wanprestatie|contractbreuk|contractuele\s+fout|in\s+gebreke\s+gesteld\s+worden|schuldig)\b", re.I)),
]

# Verwijzingen naar de opname: "(opname 00:22:30)", "(opname 00:22:30-00:23:16)", "opname 00:11:49 tot 00:12:10",
# "(transcript 12:30)", "volgens de opname", "sprak zijn vaststellingen in".
OPNAME = [
    re.compile(r"\s*\((?:opname|transcript|audio|geluidsopname)[^)]*\d{1,2}:\d{2}[^)]*\)", re.I),
    re.compile(r",?\s*(?:zie\s+)?(?:de\s+)?(?:opname|transcript|audio)\s+(?:van\s+)?\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:-|tot)\s*\d{1,2}:\d{2}(?::\d{2})?)?", re.I),
    re.compile(r"\s*\((?:opname|transcript)\)", re.I),
]
OPNAME_ZINNEN = [
    re.compile(r"[^.]*\bsprak\s+(?:zijn|haar|de)\s+(?:vaststellingen|bevindingen|opmerkingen)\s+(?:ter\s+plaatse\s+)?in\b[^.]*\.?", re.I),
    re.compile(r"[^.]*\b(?:een\s+)?tijdstip\s+tussen\s+haakjes\b[^.]*\.?", re.I),
    re.compile(r"[^.]*\bverwijst\s+naar\s+(?:die|de)\s+opname\b[^.]*\.?", re.I),
    re.compile(r"[^.]*\b(?:volgens|blijkens|uit)\s+de\s+(?:opname|geluidsopname)\b[^.]*\.?", re.I),
]

_ZIN = re.compile(r"[^.!?\n]+[.!?]?\s*")


def _opname_weg(tekst):
    n = 0
    for p in OPNAME_ZINNEN:
        tekst, k = p.subn("", tekst)
        n += k
    for p in OPNAME:
        tekst, k = p.subn("", tekst)
        n += k
    tekst = re.sub(r"\s+([,.;:)])", r"\1", tekst)
    tekst = re.sub(r"\(\s*\)", "", tekst)
    return re.sub(r"[ \t]{2,}", " ", tekst).strip(), n


def controleer(tekst):
    """Alle overtredingen in een tekst: [(regel, zin)]. Opnameverwijzingen tellen als S4."""
    uit = []
    for zin in _ZIN.findall(tekst or ""):
        for regel, p in VERBODEN:
            if p.search(zin):
                uit.append((regel, zin.strip()))
                break
    for p in OPNAME + OPNAME_ZINNEN:
        for m in p.finditer(tekst or ""):
            uit.append(("S4", m.group(0).strip()))
    return uit


def toepassen(tekst):
    """Past de regels toe op één tekst: (nieuwe tekst, [(regel, geschrapte zin of verwijzing)])."""
    if not tekst or not isinstance(tekst, str):
        return tekst, []
    ingrepen = []
    tekst, n = _opname_weg(tekst)
    ingrepen += [("S4", "opnameverwijzing")] * n
    delen = []
    for zin in _ZIN.findall(tekst):
        for regel, p in VERBODEN:
            if p.search(zin):
                ingrepen.append((regel, zin.strip()))
                delen.append(MARKERING.format(regel=regel) + " ")
                break
        else:
            delen.append(zin)
    return "".join(delen).strip(), ingrepen


def wacht(verslag):
    """Past de regels toe op elk tekstveld van een verslag-dict, ter plaatse; geeft [(regel, zin)] terug."""
    ingrepen = []

    def loop(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(v, str):
                    nieuw, ing = toepassen(v)
                    if ing:
                        x[k] = nieuw
                        ingrepen.extend(ing)
                else:
                    loop(v)
        elif isinstance(x, list):
            for i, v in enumerate(x):
                if isinstance(v, str):
                    nieuw, ing = toepassen(v)
                    if ing:
                        x[i] = nieuw
                        ingrepen.extend(ing)
                else:
                    loop(v)

    loop(verslag)
    return ingrepen


def samenvatting(ingrepen):
    """Korte telling per regel voor het logboek en de bezoekpagina: {'S4': 12, 'S1': 1}."""
    uit = {}
    for regel, _ in ingrepen:
        uit[regel] = uit.get(regel, 0) + 1
    return uit

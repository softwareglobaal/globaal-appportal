"""Schrijfregels van H-Architects voor elk verslag dat een agent of Claude schrijft (werfverslag, plaatsbezoek,
verslag van bevindingen, proces-verbaal). Dit is de grendel: wat hier verboden is, komt nooit in een concept.

Aanleiding (Mehdi, 23-10-2026, over het concept 2309 Verslag van bevindingen): het concept zei dat uit de stukken
geen eerder bezoek van het bureau bleek, en verwees bij elke vaststelling naar de opname "(opname 00:22:30)".
Dat mag nooit. De regels:

S1  Geen uitspraak over de architect of het bureau zelf: niet over zijn (niet-)aanwezigheid, eerdere bezoeken,
    opdrachtomvang, verplichtingen, fouten of verzuim. Het hoofdstuk "Rol van H-Architects" vult alleen Mehdi in.
    Alleen over het eigen bureau: "de landmeter is niet eerder gekomen" is een gewone vaststelling over een derde.
S2  Geen verwijzing naar de deontologie, het reglement of de Orde van Architecten, en nooit het oordeel dat iets
    "tegen de deontologie" of "tegen de regels van de Orde" is. Dat oordeel is aan de Orde, niet aan een verslag.
S3  Geen oordeel over een collega-architect of een ander bureau (eerder niet geweest, slecht gevolgd, nalatig).
S4  Geen verwijzing naar de opname in de tekst: geen "(opname 00:22:30)", geen "sprak zijn vaststellingen in".
    Tijdstippen blijven in de brongegevens (het veld bron) voor de controle, nooit in het verslag; de sjablonen tonen
    als herkomst alleen V, B of S. Een zin "volgens de opname ..." draagt een vaststelling en wordt zichtbaar
    vervangen; een zin die alleen over de opname gaat, valt weg. Beide staan volledig in de ingrepen (het logboek).
S5  Geen juridische kwalificatie (aansprakelijk, in gebreke, contractbreuk, wanprestatie): vaststellen en beschrijven,
    de rest is voor de raadsman. (Bestond al; staat hier zodat de grendel ze samen toetst.)
S6  (Profiel aankoopkeuring, beslissing Mehdi 23-10-2026) Geen herstelkosten, prijsramingen, kostenbandbreedtes of
    onderhandelingsbedragen in euro in het keuringsverslag.
S7  (Profiel aankoopkeuring, driehoeksoverleg 23-10-2026 3-0) Geen uitspraak over verjaring ("verjaard", "verjaring"),
    geen garantie op regularisatie ("gegarandeerd regulariseerbaar", "zeker vergund") en geen garantie dat het pand
    "vrij van verborgen gebreken" of "volledig onderzocht" is.

Werking: `toepassen(tekst)` schrapt opnameverwijzingen en vervangt een verboden zin door een zichtbare markering met
het regelnummer, zodat Mehdi ziet dat er iets geschrapt is en de schrijver het niet stil laat staan. `wacht(verslag)`
doet dat voor elk tekstveld van een verslag-dict (werfverslag of verslag van bevindingen) en geeft de ingrepen terug;
de vaste kantoorteksten van het sjabloon (`vast=`) blijven onaangeroerd. `controleer(tekst)` meldt alleen. Het document voor Mehdi: docs/Werfverslagen - schrijfregels v1.0.md.
"""
import re

MARKERING = "(geschrapt: schrijfregel {regel}, zie de schrijfregels van het kantoor)"

# Het eigen bureau als onderwerp (S1), en een stuk zin zonder nieuwe bijzin ervoor.
EIGEN = r"\b(?:(?:de\s+)?architect|het\s+bureau|ons\s+(?:bureau|kantoor)|h-architects|ondergetekende|wij|we)\b"
BIJZIN = r"(?:(?!\b(?:dat|die|wie|of|toen|terwijl|omdat|want)\b)[^.,;:]){0,60}?"

# (regel, patroon) op zinsniveau; hoofdletterongevoelig. Een zin die matcht, wordt in zijn geheel vervangen.
VERBODEN = [
    ("S2", re.compile(r"deontolog", re.I)),
    ("S2", re.compile(r"\borde\s+van\s+(de\s+)?architect", re.I)),
    ("S2", re.compile(r"\b(reglement|plichtenleer)\s+van\s+(de\s+)?(orde|architect)", re.I)),
    ("S3", re.compile(r"\b(vorige|eerdere|andere|collega)[- ]architect\b[^.]{0,80}\b(niet|nooit|slecht|nalatig|fout)", re.I)),
    # S1 alleen over het eigen bureau: de zin noemt de architect, het bureau of de eigen opdracht als onderwerp, in dezelfde
    # bijzin (een "dat ..." over de dakwerker of de landmeter is een gewone vaststelling over derden).
    ("S1", re.compile(EIGEN + BIJZIN + r"\b(niet|nooit|geen)\s+(?:\w+\s+){0,2}?(bezoek|bezocht|geweest|gekomen|langsgekomen|aanwezig|gecontroleerd|opgevolgd|ter\s+plaatse)", re.I)),
    ("S1", re.compile(r"\b(geen|niet)\s+(eerder|vroeger|voordien|tevoren)\s+\w*\s*(bezoek|controle|tussenkomst)\w*\s+(van|door)\s+" + EIGEN, re.I)),
    ("S1", re.compile(EIGEN + BIJZIN + r"\b(verzuim|nalatig|tekortgeschoten|in\s+gebreke|zijn\s+plicht|haar\s+plicht)", re.I)),
    ("S1", re.compile(r"(?:" + EIGEN + r"|\b(?:de|onze|deze)\s+opdracht\b)[^.]{0,80}\b(hoogstens|maximaal|slechts|maar)\s+(één|een|1)\s+(controle)?bezoek", re.I)),
    ("S1", re.compile(r"\b(hoogstens|maximaal|slechts|maar)\s+(één|een|1)\s+(controle)?bezoek\w*\s+(van|door)\s+" + EIGEN, re.I)),
    ("S3", re.compile(r"\b(vorige|eerdere|andere|collega)[- ]architect\b[^.]{0,80}\b(niet|nooit|slecht|nalatig|fout)", re.I)),
    ("S5", re.compile(r"\b(aansprakelijk|wanprestatie|contractbreuk|contractuele\s+fout|in\s+gebreke|ingebrekestelling|schuldig)\b", re.I)),
]

VERBODEN_PROFIEL = {
    "aankoopkeuring": [
        ("S6", re.compile(r"(?:€\s*\d|\b\d[\d.,\s]*\s*(?:euro|eur)\b)", re.I)),
        ("S6", re.compile(r"\b(?:herstelkost(?:en)?|kostenraming|richtprijs|prijsbandbreedte|onderhandelingsbedrag)\b[^.]{0,60}\b\d", re.I)),
        ("S7", re.compile(r"\b(?:stedenbouwkundig\s+|bouwmisdrijf\s+|overtreding\s+)?(?:verjaard|verjaring\w*)\b", re.I)),
        ("S7", re.compile(r"\b(?:gegarandeerd|zeker|zonder\s+probleem|probleemloos)\s+(?:regulariseerbaar|te\s+regulariseren|vergund)\b", re.I)),
        ("S7", re.compile(r"\b(?:vrij\s+van|geen\s+enkele?|zonder)\s+verborgen\s+gebrek(?:en)?\b", re.I)),
        ("S7", re.compile(r"\bvolledig\s+(?:en\s+uitputtend\s+)?onderzocht\b", re.I)),
        ("S7", re.compile(r"\bverkoper\s+(?:was\s+|is\s+)?te\s+kwader\s+trouw\b", re.I)),
    ],
}

# Verwijzingen naar de opname: "(opname 00:22:30)", "(opname 00:22:30-00:23:16)", "opname 00:11:49 tot 00:12:10",
# "(transcript 12:30)", "volgens de opname", "sprak zijn vaststellingen in".
OPNAME = [
    re.compile(r"\s*\((?:opname|transcript|audio|geluidsopname)[^)]*\d{1,2}:\d{2}[^)]*\)", re.I),
    re.compile(r",?\s*(?:zie\s+)?(?:de\s+)?(?:opname|transcript|audio)\s+(?:van\s+)?\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:-|tot)\s*\d{1,2}:\d{2}(?::\d{2})?)?", re.I),
    re.compile(r"\s*\((?:opname|transcript)\)", re.I),
]
# Een zin loopt tot een punt, uitroep- of vraagteken; de punt in 4.500 of 1.250.000 (tussen twee cijfers) knipt niet.
_T = r"(?:[^.]|(?<=\d)\.(?=\d))"
_Z = r"(?:[^.!?\n]|(?<=\d)\.(?=\d))"
# Zinnen die alleen over de opname gaan: ze vallen weg (S4). Wat na "sprak zijn vaststellingen in:" volgt, is de
# vaststelling zelf en blijft staan. De geschrapte zin staat in de ingrepen, dus in het logboek.
OPNAME_ZINNEN = [
    re.compile(r"[^.:;]*\bsprak\s+(?:zijn|haar|de)\s+(?:vaststellingen|bevindingen|opmerkingen)\s+(?:ter\s+plaatse\s+)?in\b[^.:;]*(?:[.;]|:\s*(\w)?|$)", re.I),
    re.compile(_T + r"*\b(?:een\s+)?tijdstip\s+tussen\s+haakjes\b" + _T + r"*\.?", re.I),
    re.compile(_T + r"*\bverwijst\s+naar\s+(?:die|de)\s+opname\b" + _T + r"*\.?", re.I),
]
# "Volgens de opname is de dorpel 3 cm te laag." draagt een vaststelling: de zin wordt zichtbaar vervangen door de
# markering S4, en staat volledig in het logboek. "De opname van de bestaande toestand" is een opmeting, geen opname.
OPNAME_VOLGENS = re.compile(_Z + r"*?\b(?:volgens|blijkens|uit)\s+de\s+(?:opname|geluidsopname)\b(?!\s+van\s+de\s+bestaande\s+toestand)"
                            + _Z + r"*[.!?]?", re.I)

_ZIN = re.compile(_Z + r"+[.!?]?\s*")


def _opname_weg(tekst):
    """Haalt opnameverwijzingen weg: (tekst, [(S4, geschrapte zin of 'opnameverwijzing')])."""
    ingrepen = []

    def zin_weg(m):
        zin = m.group(0)
        volgletter = m.group(1) if m.re.groups else None
        if volgletter:
            zin = zin[:-1]
        ingrepen.append(("S4", zin.strip()))
        return volgletter.upper() if volgletter else ""

    def zin_gemarkeerd(m):
        ingrepen.append(("S4", m.group(0).strip()))
        voor = m.group(0)[:len(m.group(0)) - len(m.group(0).lstrip())]
        return voor + MARKERING.format(regel="S4")

    for p in OPNAME_ZINNEN:
        tekst = p.sub(zin_weg, tekst)
    tekst = OPNAME_VOLGENS.sub(zin_gemarkeerd, tekst)
    for p in OPNAME:
        tekst, k = p.subn("", tekst)
        ingrepen += [("S4", "opnameverwijzing")] * k
    tekst = re.sub(r"\s+([,.;:)])", r"\1", tekst)
    tekst = re.sub(r"\(\s*\)", "", tekst)
    return re.sub(r"[ \t]{2,}", " ", tekst).strip(), ingrepen


def _regels(profiel=None):
    return VERBODEN + (VERBODEN_PROFIEL.get(profiel) or [])


def controleer(tekst, profiel=None):
    """Alle overtredingen in een tekst: [(regel, zin)]. Opnameverwijzingen tellen als S4."""
    uit = []
    regels = _regels(profiel)
    for zin in _ZIN.findall(tekst or ""):
        for regel, p in regels:
            if p.search(zin):
                uit.append((regel, zin.strip()))
                break
    for p in OPNAME + OPNAME_ZINNEN + [OPNAME_VOLGENS]:
        for m in p.finditer(tekst or ""):
            uit.append(("S4", m.group(0).strip()))
    return uit


def toepassen(tekst, profiel=None):
    """Past de regels toe op één tekst: (nieuwe tekst, [(regel, geschrapte zin of verwijzing)])."""
    if not tekst or not isinstance(tekst, str):
        return tekst, []
    tekst, ingrepen = _opname_weg(tekst)
    delen = []
    regels = _regels(profiel)
    for zin in _ZIN.findall(tekst):
        for regel, p in regels:
            if p.search(zin):
                ingrepen.append((regel, zin.strip()))
                delen.append(MARKERING.format(regel=regel) + " ")
                break
        else:
            delen.append(zin)
    return "".join(delen).strip(), ingrepen


def wacht(verslag, profiel=None, vast=()):
    """Past de regels toe op elk tekstveld van een verslag-dict, ter plaatse; geeft [(regel, zin)] terug.
    vast: de vaste kantoorteksten van het sjabloon (doorlopende punten, voorbehoud). Dat is tekst van Mehdi zelf; een veld
    dat er letterlijk een van is, blijft onaangeroerd (de VGP-zin "De architect is niet aansprakelijk ..." is geen S5)."""
    ingrepen = []
    vast = {t.strip() for t in vast if isinstance(t, str)}

    def een(tekst):
        if tekst.strip() in vast:
            return tekst, []
        return toepassen(tekst, profiel=profiel)

    def loop(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(v, str):
                    nieuw, ing = een(v)
                    if ing:
                        x[k] = nieuw
                        ingrepen.extend(ing)
                else:
                    loop(v)
        elif isinstance(x, list):
            for i, v in enumerate(x):
                if isinstance(v, str):
                    nieuw, ing = een(v)
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

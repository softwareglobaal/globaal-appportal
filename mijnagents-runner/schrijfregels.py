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
    ("S5", re.compile(r"\b(aansprakelijk|wanprestatie|contractbreuk|contractuele\s+fout|in\s+gebreke|ingebrekestelling|schuldig)\b", re.I)),
]

VERBODEN_PROFIEL = {
    "aankoopkeuring": [
        ("S6", re.compile(r"(?:€\s*\d|\b\d[\d.,\s]*\s*(?:euro|eur)\b)", re.I)),
        ("S6", re.compile(r"\b(?:herstelkost(?:en)?|kostenraming|richtprijs|prijsbandbreedte|onderhandelingsbedrag)\b[^.]{0,60}\b\d", re.I)),
        ("S7", re.compile(r"\b(?:stedenbouwkundig\s+|bouwmisdrijf\s+|overtreding\s+)?(?:verjaard(?:e)?|verjaring\w*|verja(?:a)?r(?:t|en)?)\b", re.I)),
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
# Zo ook de punt van een afkorting midden in een zin ("€ 3.200 excl. btw").
# Alleen als de zin daarna echt doorloopt (kleine letter of cijfer, ook onder re.I); "BV." van een firma is een zinseinde.
_AFK = r"(?:(?<=\bexcl)|(?<=\bincl)|(?<=\bca)|(?<=\bnr)|(?<=\bresp)|(?<=\bvb)|(?<=\bgew))\.(?=\s+(?-i:[a-z0-9(€]))"
_T = r"(?:[^.;:\n]|(?<=\d)[.:](?=\d)|" + _AFK + ")"
_Z = r"(?:[^.!?\n]|(?<=\d)\.(?=\d)|" + _AFK + ")"
# Zinnen die alleen over de opname gaan: ze vallen weg (S4). Wat na "sprak zijn vaststellingen in:" volgt, is de
# vaststelling zelf en blijft staan. De geschrapte zin staat in de ingrepen, dus in het logboek.
# "De architect sprak zijn vaststellingen in." valt weg. Volgt er na een dubbelpunt of puntkomma een gewone vaststelling,
# dan blijft die staan; na een komma, of als de rest weer over de opname gaat, wordt de zin zichtbaar gemarkeerd (S4).
SPRAK = re.compile(r"(?:[^.:;\n]|(?<=\d)[.:](?=\d))*\bsprak\s+(?:zijn|haar|de)\s+(?:vaststellingen|bevindingen|opmerkingen)\s+(?:ter\s+plaatse\s+)?in\b[^.:;,]*"
                   r"(?:(?P<sep>[:;,])(?P<rest>(?:[^.]|(?<=\d)\.(?=\d))*))?\.?", re.I)
_OVER_OPNAME = re.compile(r"\b(?:opname|geluidsopname|transcript|audio|ingesproken|insprak|sprak)\w*", re.I)
OPNAME_ZINNEN = [
    re.compile(_T + r"*\b(?:een\s+)?tijdstip\s+tussen\s+haakjes\b" + _T + r"*\.?", re.I),
    re.compile(_T + r"*\bverwijst\s+naar\s+(?:die|de)\s+opname\b" + _T + r"*\.?", re.I),
]
# "Volgens de opname is de dorpel 3 cm te laag." draagt een vaststelling: de zin wordt zichtbaar vervangen door de
# markering S4, en staat volledig in het logboek. "De opname van de bestaande toestand" is een opmeting, geen opname.
OPNAME_VOLGENS = re.compile(_Z + r"*?\b(?:volgens|blijkens|uit)\s+de\s+(?:opname|geluidsopname)\b(?!\s+(?:van\s+)?(?:de\s+|het\s+)?(?:bestaande\s+(?:toestand|situatie)|landmeter|terrein|opmeting)\b)"
                            + _Z + r"*[.!?]?", re.I)

_ZIN = re.compile(_Z + r"+[.!?]?\s*")


def _opname_weg(tekst):
    """Haalt opnameverwijzingen weg: (tekst, [(S4, geschrapte zin of 'opnameverwijzing')])."""
    ingrepen = []

    def zin_weg(m):
        ingrepen.append(("S4", m.group(0).strip()))
        return ""

    def zin_gemarkeerd(m):
        ingrepen.append(("S4", m.group(0).strip()))
        voor = m.group(0)[:len(m.group(0)) - len(m.group(0).lstrip())]
        return voor + MARKERING.format(regel="S4")

    def sprak(m):
        sep, rest = m.group("sep"), (m.group("rest") or "").strip()
        voor = m.group(0)[:len(m.group(0)) - len(m.group(0).lstrip())]
        if not rest:
            ingrepen.append(("S4", m.group(0).strip()))
            return ""
        if sep in ":;" and not _OVER_OPNAME.search(rest):
            ingrepen.append(("S4", m.group(0)[:m.start("sep") - m.start() + 1].strip()))
            return voor + rest[0].upper() + rest[1:] + ("." if m.group(0).rstrip().endswith(".") else "")
        ingrepen.append(("S4", m.group(0).strip()))
        return voor + MARKERING.format(regel="S4")

    tekst = SPRAK.sub(sprak, tekst)
    for p in OPNAME_ZINNEN:
        tekst = p.sub(zin_weg, tekst)
    tekst = OPNAME_VOLGENS.sub(zin_gemarkeerd, tekst)
    for p in OPNAME:
        tekst, k = p.subn("", tekst)
        ingrepen += [("S4", "opnameverwijzing")] * k
    tekst = re.sub(r"\s+([,.;:)])", r"\1", tekst)
    tekst = re.sub(r"\(\s*\)", "", tekst)
    tekst = re.sub(r";\s*$", ".", tekst.strip())
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
    for p in OPNAME + OPNAME_ZINNEN + [SPRAK, OPNAME_VOLGENS]:
        for m in p.finditer(tekst or ""):
            uit.append(("S4", m.group(0).strip()))
    return uit


def toepassen(tekst, profiel=None, vast=frozenset()):
    """Past de regels toe op één tekst: (nieuwe tekst, [(regel, geschrapte zin of verwijzing)]).
    vast: zinnen die letterlijk vaste kantoortekst zijn en blijven staan (zie wacht)."""
    if not tekst or not isinstance(tekst, str):
        return tekst, []
    tekst, ingrepen = _opname_weg(tekst)
    delen = []
    regels = _regels(profiel)
    for zin in _ZIN.findall(tekst):
        if zin.strip() in vast:
            delen.append(zin)
            continue
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
    of een zin die er letterlijk een van is, blijft onaangeroerd (de VGP-zin "De architect is niet aansprakelijk ..." is
    geen S5), ook in een oudere bewoording van het punt rond dezelfde zin.
    Het veld bron blijft ook staan: daar hoort het opnametijdstip, voor de controle (S4)."""
    ingrepen = []
    vast_velden = {t.strip() for t in vast if isinstance(t, str)}
    vast_zinnen = frozenset(z.strip() for t in vast_velden for z in _ZIN.findall(t) if z.strip())

    def een(tekst):
        if tekst.strip() in vast_velden:
            return tekst, []
        return toepassen(tekst, profiel=profiel, vast=vast_zinnen)

    def loop(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "bron":
                    continue
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

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
    ("S5", re.compile(r"\b(aansprakelijk|wanprestatie|contractbreuk|contractuele\s+fout|in\s+gebreke|ingebrekestelling\w*|schuldig)\b", re.I)),
    # dezelfde regels in het Engels, voor de Engelse tekst van een tweetalig verslag (nl+en)
    ("S2", re.compile(r"\b(?:order|chamber)\s+of\s+architects\b", re.I)),
    ("S3", re.compile(r"\b(?:previous|former|other)\s+architect\b[^.]{0,80}\b(?:not|never|poorly|negligent|failed)\b", re.I)),
    ("S1", re.compile(r"\b(?:no|not)\s+(?:previous|prior|earlier)\s+(?:site\s+)?(?:visits?|inspections?)\b", re.I)),
    ("S1", re.compile(r"\b(?:architect|office|h-architects)\b[^.]{0,60}\b(?:not|never)\s+(?:visited|present|attended|checked|inspected|supervised)\b", re.I)),
    ("S1", re.compile(r"\b(?:only|at\s+most|a\s+maximum\s+of)\s+(?:one|1)\s+(?:site\s+)?visit\b", re.I)),
    ("S5", re.compile(r"\b(?:liable|in\s+default|breach\s+of\s+contract|at\s+fault|negligen(?:t|ce)|culpable)\b", re.I)),
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
# "Zie opname 00:12:05." als eigen zin: weg samen met de punt, zodat er geen ".." of losse punt overblijft
_TIJDSTIP = r"\d{1,2}:\d{2}(?::\d{2})?"
OPNAME_LOS = re.compile(r"(?:^|(?<=[.!?]))[ \t]*(?:zie\s+|see\s+)?(?:de\s+|the\s+)?(?:opname|transcript|audio|recording)\s+(?:van\s+|at\s+)?"
                        + _TIJDSTIP + r"(?:\s*(?:-|–|tot|to)\s*" + _TIJDSTIP + r")?\s*[.!?](?=\s|$)", re.I | re.M)
OPNAME = [
    re.compile(r"\s*\((?:opname|transcript|audio|geluidsopname)[^)]*\d{1,2}:\d{2}[^)]*\)", re.I),
    re.compile(r",?\s*(?:zie\s+)?(?:de\s+)?(?:opname|transcript|audio)\s+(?:van\s+)?\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:-|tot)\s*\d{1,2}:\d{2}(?::\d{2})?)?", re.I),
    re.compile(r"\s*\((?:opname|transcript)\)", re.I),
    re.compile(r"\s*\((?:recording|audio)[^)]*\d{1,2}:\d{2}[^)]*\)", re.I),
    re.compile(r",?\s*(?:see\s+)?(?:the\s+)?recording\s+(?:at\s+)?\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:-|to)\s*\d{1,2}:\d{2}(?::\d{2})?)?", re.I),
    re.compile(r"\s*\(recording\)", re.I),
]
# Een zin loopt tot een punt, uitroep- of vraagteken; de punt in 4.500 of 1.250.000 (tussen twee cijfers) knipt niet.
# Zo ook de punt van een afkorting midden in een zin ("€ 3.200 excl. btw").
# Alleen als de zin daarna echt doorloopt (kleine letter of cijfer, ook onder re.I); "BV." van een firma is een zinseinde.
_AFK = r"(?:(?<=\bexcl)|(?<=\bincl)|(?<=\bca)|(?<=\bnr)|(?<=\bresp)|(?<=\bvb)|(?<=\bgew))\.(?=\s+(?-i:[a-z0-9(€]))"
_T = r"(?:[^.;:\n]|(?<=\d)[.:](?=\d)|" + _AFK + ")"
# Elke regelovergang sluit een zin af, zoals in productie: een opsomming zonder leesteken blijft zo een reeks eigen
# regels. Alleen voor S4 kijkt _opname_weg één regel verder (een harde regelovergang midden in "sprak zijn
# vaststellingen\nter plaatse in" of "volgens de\nopname").
_Z = r"(?:[^.!?\n]|(?<=\d)\.(?=\d)|" + _AFK + ")"
# Zinnen die alleen over de opname gaan: ze vallen weg (S4). Wat na "sprak zijn vaststellingen in:" volgt, is de
# vaststelling zelf en blijft staan. De geschrapte zin staat in de ingrepen, dus in het logboek.
# S4 per zin (een zin stopt aan . ! ? of een nieuwe regel, niet aan de punt van 4.500 of de dubbelpunt van 10:15), zodat
# een patroon nooit in een buurzin of in een markering bijt. Elke weggevallen of gemarkeerde zin staat in het logboek.
# - "De architect sprak zijn vaststellingen in (om 10:15)." zegt alleen dat er ingesproken werd: valt weg. Staat er meer
#   in de zin, dan wordt hij zichtbaar gemarkeerd.
# - "Een tijdstip tussen haakjes verwijst naar de opname." (de legende) valt weg; staat er in dezelfde zin ook een
#   vaststelling, dan wordt hij zichtbaar gemarkeerd.
# - "Volgens de opname is de dorpel 3 cm te laag." draagt een vaststelling: zichtbaar gemarkeerd. "De opname van de
#   bestaande toestand" (of van de plaatsgesteldheid, door een expert) is een opmeting, geen geluidsopname.
SPRAK = re.compile(r"\bsprak\s+(?:zijn|haar|de)\s+(?:vaststellingen|bevindingen|opmerkingen)\s+(?:ter\s+plaatse\s+)?in\b"
                   r"|\bdictated\s+(?:his|her|the)\s+(?:findings|observations)\b", re.I)   # "recorded" is ook gewoon "noteerde"
# "De architect ... sprak zijn vaststellingen in" gaat over de architect zelf; staat er iets anders vóór (een vaststelling:
# "De dorpel ligt te laag en ..."), dan valt de zin niet stil weg maar wordt hij gemarkeerd
_OVER_ARCHITECT = re.compile(r"\s*(?:[-*•]\s+|\d+[.)]\s+)?(?:de\s+|the\s+)?(?:architect|mehdi|ik|wij|we|i)\b", re.I)
_OVER_OPNAME = re.compile(r"\b(?:opname|geluidsopname|transcript|tijdstip|tijdstippen|haakjes|recording|timestamps?|brackets)\b", re.I)
_TIJD = re.compile(r"\d{1,2}[:.u]\d{2}(?:[:.]\d{2})?", re.I)
_VULWOORD = re.compile(r"\b(?:om|tussen|van|vanaf|tot|en|rond|omstreeks|ter|plaatse|de|het|opname|geluidsopname|"
                       r"at|between|and|from|to|on|site|the|recording)\b", re.I)
_OPMETING = (r"(?!\s+(?:(?:van|door)\s+)?(?:de\s+|het\s+|een\s+)?(?:bestaande\s+(?:toestand|situatie)|plaatsgesteldheid|"
             r"plaatsbeschrijving|aanpalende|landmeter|terrein|opmeting|\w*expert|\w*verslaggever)\b)")
OPNAME_ZINNEN = [
    re.compile(_T + r"*\b(?:een\s+)?tijdstip\s+tussen\s+haakjes\b" + _T + r"*\.?", re.I),
    re.compile(_T + r"*\bverwijst\s+naar\s+(?:die|de)\s+opname\b" + _OPMETING + _T + r"*\.?", re.I),
    re.compile(_T + r"*\b(?:a\s+)?time(?:stamp)?s?\s+(?:in|between)\s+brackets\b" + _T + r"*\.?", re.I),
    re.compile(_T + r"*\brefers?\s+to\s+the\s+recording\b" + _T + r"*\.?", re.I),
]
# een geluidsopname is altijd een opname, nooit een opmeting: de uitzondering hangt alleen achter "opname"
OPNAME_VOLGENS = re.compile(r"\b(?:volgens|blijkens|uit)\s+de\s+(?:opname\b" + _OPMETING + r"|geluidsopname\b)"
                            r"|\b(?:according\s+to|from)\s+the\s+(?:audio\s+)?recording\b", re.I)

# Een markering is een eigen "zin": zo versmelt ze bij een tweede doorgang niet met de zin erna (idempotent).
_MARK = re.compile(re.escape(MARKERING).replace(r"\{regel\}", r"S\d") + r"\s*")
# losse leestekens ("...", "??", een punt vooraan) zijn een eigen stuk: zo gaan ze bij het heropbouwen niet verloren
_ZIN = re.compile(_MARK.pattern + "|" + _Z + r"+[.!?]*\s*|[.!?]+\s*")
# Een kaal tijdstip tussen haakjes; telt alleen als opnameverwijzing als de tekst zelf zegt dat zo'n tijdstip naar de
# opname verwijst (de legende), anders is "(10:15)" gewoon een uur.
_KAAL_TIJDSTIP = re.compile(r"\s*\(\s*\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:-|–|tot)\s*\d{1,2}:\d{2}(?::\d{2})?)?\s*\)")


def _is_s4(kern):
    return _s4_begin(kern) is not None


def _begint_in(begin, zin):
    """De S4-zin begint in deze regel (niet pas in de volgende)."""
    return begin is not None and begin < len(zin.strip())


def _s4_begin(kern):
    """Waar de eerste S4-zin in de tekst begint, of None."""
    begins = [m.start() for p in [SPRAK, OPNAME_VOLGENS, *OPNAME_ZINNEN] for m in [p.search(kern)] if m]
    return min(begins) if begins else None


def _woorden(tekst):
    return re.findall(r"[^\W\d_]{2,}", tekst)


def _opname_weg(tekst):
    """Haalt opnameverwijzingen weg, per zin: (tekst, [(S4, geschrapte zin of 'opnameverwijzing')])."""
    ingrepen = []
    delen = []
    markering = MARKERING.format(regel="S4")

    def weg(staart):
        # de zin valt weg; tussen wat ervoor en erna staat blijft de grootste regelafstand van de twee (lijstpunten en
        # alinea's plakken niet aan elkaar, en er komt geen lege regel bij)
        na = staart.count("\n")
        if not na:
            return
        voor = 0
        if delen:
            delen[-1] = delen[-1].rstrip(" \t")
            voor = len(delen[-1]) - len(delen[-1].rstrip("\n"))
        if na > voor:
            delen.append("\n" * (na - voor))

    legende = False
    stukken = _ZIN.findall(tekst)
    i = 0
    while i < len(stukken):
        zin = stukken[i]
        i += 1
        # een harde regelovergang midden in een opnamezin: de regel eindigt zonder leesteken, de volgende begint klein,
        # en pas samen is het een S4-zin; dan worden ze samen beoordeeld
        while (i < len(stukken) and "\n" in zin and not zin.strip().endswith((".", "!", "?", ";", ":"))
               and stukken[i].lstrip()[:1].islower() and not _is_s4(zin.strip())
               and _begint_in(_s4_begin((zin + stukken[i]).lstrip()), zin)):
            zin += stukken[i]
            i += 1
        kern = zin.strip()
        kop, staart = zin[:len(zin) - len(zin.lstrip())], zin[len(zin.rstrip()):]
        if _MARK.fullmatch(kern):
            delen.append(zin)
            continue
        m = SPRAK.search(kern)
        if m:
            ingrepen.append(("S4", kern))
            rest = _VULWOORD.sub("", _TIJD.sub("", kern[m.end():]))
            voor = kern[:m.start()]
            if _woorden(rest) or re.search(r"[;:](?!\d)", voor) or (_woorden(voor) and not _OVER_ARCHITECT.match(voor)):
                delen.append(kop + markering + staart)
            else:
                weg(staart)
            continue
        if any(p.search(kern) for p in OPNAME_ZINNEN):
            ingrepen.append(("S4", kern))
            legende = True
            # elk zinsdeel (tussen ; of ": ") gaat over de opname of het tijdstip: de zin valt weg; anders zichtbaar gemarkeerd
            delen_zin = re.split(r";|:\s", kern)
            if all(_OVER_OPNAME.search(d) and not OPNAME_VOLGENS.search(d) for d in delen_zin):
                weg(staart)
            else:
                delen.append(kop + markering + staart)
            continue
        if OPNAME_VOLGENS.search(kern):
            ingrepen.append(("S4", kern))
            delen.append(kop + markering + staart)
            continue
        delen.append(zin)
    tekst = "".join(delen)
    for p in [OPNAME_LOS] + OPNAME + ([_KAAL_TIJDSTIP] if legende else []):
        tekst, k = p.subn("", tekst)
        ingrepen += [("S4", "opnameverwijzing")] * k
    tekst = re.sub(r"[ \t]+([,.;:)])", r"\1", tekst)
    tekst = re.sub(r"\(\s*\)", "", tekst)
    return re.sub(r"[ \t]{2,}", " ", tekst).strip(), ingrepen


def bron_zichtbaar(bron):
    """De bron zoals ze in een verslag mag staan: zonder opname, transcript of tijdstip (S4). Het volledige veld bron blijft in
    de gegevens; dit is alleen voor de weergave ("factuur 2026-114, zie opname 00:12:05" wordt "factuur 2026-114")."""
    b = str(bron or "")
    b = re.sub(r"(?:zie\s+)?(?:de\s+)?\S*(?:opname|transcript|audio)\S*(?:\s+(?:van\s+)?\d{1,2}:\d{2}(?::\d{2})?"
               r"(?:\s*(?:-|–|tot)\s*\d{1,2}:\d{2}(?::\d{2})?)?)?", "", b, flags=re.I)
    b = re.sub(r"\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:-|–|tot)\s*\d{1,2}:\d{2}(?::\d{2})?)?", "", b)
    b = re.sub(r"\(\s*\)", "", b)
    return re.sub(r"\s{2,}", " ", b).strip(" ,;:-")


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
        if zin.strip() in vast or _MARK.fullmatch(zin.strip()):
            delen.append(zin)
            continue
        for regel, p in regels:
            if p.search(zin):
                ingrepen.append((regel, zin.strip()))
                staart = zin[len(zin.rstrip()):]
                delen.append(zin[:len(zin) - len(zin.lstrip())] + MARKERING.format(regel=regel) + (staart if "\n" in staart else " "))
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

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
    # zo smal als de Nederlandse S1 (37e review): alleen een bezoek, en "the office" zoals "het bureau"; "the site office is
    # not present yet" (de werfkeet) of "no previous inspection of the installation" (een keuring) is gewone tekst
    ("S1", re.compile(r"\b(?:no|not)\s+(?:previous|prior|earlier)\s+(?:site\s+)?visits?\b", re.I)),
    ("S1", re.compile(r"\b(?:(?:the\s+)?architect|the\s+office|our\s+office|h-architects)\b[^.]{0,60}\b(?:not|never)\s+(?:visited|present|attended|checked|inspected|supervised)\b", re.I)),
    ("S1", re.compile(r"\b(?:only|at\s+most|a\s+maximum\s+of)\s+(?:one|1)\s+(?:site\s+)?visit\b", re.I)),
    # "liable to rot" of "liable to crack" (vatbaar voor) is gewone technische tekst; "liable for", "held liable", "liable to
    # the client" en "liable to pay" zijn een juridisch oordeel (35e review). Zo ook "in default mode" of "in default
    # settings" (standaardinstelling) tegenover "is in default", "in default of payment" of "in default under" (36e review).
    # En "at fault currents" of "at fault level" (foutstroom, kortsluitvermogen) tegenover "is at fault (for)" (41e review).
    ("S5", re.compile(r"\b(?:liable\b(?!\s+to\s+(?!(?:the|a|an|him|her|them|us|you|it|his|their|our|its|any|each|all|pay|"
                      r"compensate|indemnify|reimburse)\b)[a-z])|in\s+default\b(?!\s+(?!(?:of|under|towards|by|since|with)\b)[a-z])|breach\s+of\s+contract\b|at\s+fault\b(?!\s+(?!(?:for|of|in|under|towards|by|since|with)\b)[a-z])|"
                      r"negligen(?:t|ce)\b|culpable\b)", re.I)),
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
# Een opnametijdstip: 00:12, 00:12:30, 0:12:30 of 12m30s (een schaal 1:100 of 1:50 is geen tijdstip).
# een eenheid achter een tijdstip hoort erbij: 10:15u, 10:15uur, 10:15 uur, 3:45min, 3:45mins, 3:45hr, 3:45m (35e review);
# met een spatie alleen de lange vormen, zodat "10:15 u ziet" het woord u niet opslokt
_EENHEID = r"(?:(?:uur|u|h|hr|hrs|min|mins|m|sec|secs|s)\b|\s(?:uur|min|mins|sec|secs|hr|hrs)\b)"
_OPNAMETIJD = r"(?:\b\d{2}:\d{2}(?::\d{2})?(?:" + _EENHEID + r"|\b)|\b\d:\d{2}:\d{2}(?:" + _EENHEID + r"|\b)|\b\d{1,2}m\d{2}s\b)"
_OPNAMETIJDEN = _OPNAMETIJD + r"(?:\s*(?:-|–|tot|to)\s*" + _OPNAMETIJD + r")?"
# 30e review: los of verder in een haakje telt alleen die strenge vorm, zodat "(Opname ..., schaal 1:50)" gewone tekst blijft
_TIJDSTIP = _OPNAMETIJD
# Direct na het woord opname, transcript of recording is elk tijdstip een opnametijdstip, zoals in productie: ook 3:45,
# 0:45, 3:45min of 12:30u, na een spatie, dubbelpunt, komma of streep ("(opname: 3:45)", "zie opname 7:12"), ook na een
# samengesteld woord ("(audio-opname 3:45)"). Een schaal 1:100 is nooit zo'n tijdstip (31e en 32e review).
# ook een samenstelling met koppelteken: "Plaud-opname", "Fathom-opname", "gsm-opname", "Plaud-transcript" (34e review);
# zonder koppelteken alleen de vaste voorvoegsels, zodat "momentopname" een gewoon woord blijft
_OPNAMEWOORD = r"(?:\w+-|(?:audio|video|geluids|spraak))?(?:opname|transcript|audio|recording)"
_DIRECTTIJD = r"(?:(?<!\d)(?<!\d:)\d{1,2}:\d{2}(?::\d{2})?(?!\d|:\d)(?:" + _EENHEID + r"|\b)|\b\d{1,2}m\d{2}s\b)"
_DIRECTTIJDEN = _DIRECTTIJD + r"(?:\s*(?:-|–|tot|to)\s*" + _DIRECTTIJD + r")?"
# buiten haakjes: een spatie of een dubbelpunt, en alleen "van" of "at" ertussen zoals productie; "de opname op 1:50" of
# "de opname om 9:30" is gewone tekst over een opmeting of plaatsbeschrijving en blijft (33e review)
_NA_WOORD = r"(?:\s*:\s*|\s+)(?:(?:van|at)\s+)?"
_NA_WOORD_HAAKJE = r"[\s:,\-–]*(?:(?:van|at|om|op)\s+)?"        # in een haakje ook een komma of een streep
_ZIE = r"(?:zie\s+|see\s+)?(?:de\s+|the\s+)?"
_VERWIJZING = _ZIE + _OPNAMEWOORD + _NA_WOORD + _DIRECTTIJDEN
# een haakje met een opnametijdstip; zo streng als productie: "(Opname van de bestaande toestand ...)" of "(Opname visueel
# en niet-destructief; ...)" is gewone tekst en blijft (27e review)
_HAAKJE_MET_TIJD = (r"\(\s*" + _ZIE + _OPNAMEWOORD + r"(?:" + _NA_WOORD_HAAKJE + _DIRECTTIJD + r"|[^)]*" + _TIJDSTIP
                    + r")[^)]*\)")
_VERWIJZING_HAAKJE = r"(?:" + _HAAKJE_MET_TIJD + r"|\(\s*" + _ZIE + _OPNAMEWOORD + r"\s*\))"
# Een verwijzing als eigen zin ("Zie opname 00:12:05.", "(opname 00:22:30)."): weg samen met haar punt, zodat er geen ".."
# of losse punt overblijft (19e en 26e review). Alleen aan een echt zinsbegin: na . ! ? op dezelfde regel, of aan het
# begin van een regel na een zinseinde of een lege regel; 'raam, zie\nopname 00:12.' is het einde van een zin (24e review).
# Een regel die alleen uit een verwijzing bestaat, valt al eerder helemaal weg (_verwijzingsregels_weg, 32e review).
_ZINSBEGIN_REGEL = r"(?:\A|(?<=[.!?]\n)|(?<=[.!?][ \t]\n)|(?<=\n\n)|(?<=\n[ \t]\n))[ \t]*"
# een sluitteken mag volgen: "(Volgens de huurder. Zie opname 00:12:05.)" wordt "(Volgens de huurder.)" (38e review)
OPNAME_LOS = re.compile(r"(?:(?<=[.!?])[ \t]*" + _VERWIJZING + r"\s*[.!?](?=[\s\"'\u201d\u2019\u00bb)\]]|$)|" + _ZINSBEGIN_REGEL
                        + _VERWIJZING + r"\s*[.!?](?:[ \t]+|(?=\n)|\Z))", re.I)
OPNAME_LOS_HAAKJES = re.compile(r"(?:(?<=[.!?])[ \t]*" + _VERWIJZING_HAAKJE + r"\s*[.!?]?(?=\s|$)|" + _ZINSBEGIN_REGEL
                                + _VERWIJZING_HAAKJE + r"\s*[.!?]?(?:[ \t]+|(?=\n)|\Z))", re.I)
OPNAME = [
    re.compile(r"\s*" + _HAAKJE_MET_TIJD, re.I),
    # niet midden in een woord: van "momentopname 3:45" of "(audio-opname 3:45)" blijft geen brokstuk over
    re.compile(r",?\s*(?<![\w-])" + _VERWIJZING, re.I),
    re.compile(r"\s*\((?:opname|transcript|recording)\)", re.I),
]
_REGEL_VERWIJZING = re.compile(r"(?:" + _VERWIJZING + r"|" + _VERWIJZING_HAAKJE + r")\s*[.!?]?", re.I)
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
_TIJD = re.compile(r"\d{1,2}[:.u]\d{2}(?:[:.]\d{2})?", re.I)
# De woorden van een zin die alleen over het inspreken of de opname gaat (de 2309-tekst en varianten). Een ander woord
# (een vaststelling) maakt van het wegvallen een zichtbare markering.
_META = frozenset("""de het een architect architecte mehdi chegini ik wij we zijn haar ter plaatse in sprak spreekt vaststellingen
    vaststelling bevindingen opmerkingen tijdstip tijdstippen tussen haakjes verwijst verwijzen naar die deze opname opnames
    geluidsopname transcript van dit dat wat elk elke zo kan kunnen men terugvinden terug te vinden bezoek plaatsbezoek werfbezoek
    nam neemt maakte maakt foto foto's fotos en zoals om tot vanaf rond omstreeks uur u kwam aan arriveerde geeft gaf moment noot
    opmerking ook hierbij telkens bij the a an i his her dictated findings observations timestamp timestamps time times between
    brackets refers refer to recording recordings audio at and during on site visit this that each every note also""".split())
_TIJD_PLAATSHOUDER = re.compile(r"\b(?:[uhm]{1,2}|ss)(?::(?:[uhm]{1,2}|ss)){1,2}\b", re.I)


def _alleen_meta(kern):
    rest = _TIJD_PLAATSHOUDER.sub(" ", re.sub(r"\d+", " ", kern))
    return all(w in _META for w in re.findall(r"[^\W\d_]+(?:'s)?", rest.lower()))
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
# een sluitend aanhalingsteken of haakje direct na de punt hoort bij die zin, niet bij de volgende (37e review)
_SLUIT = r"(?:(?<=[.!?])[\"'\u201d\u2019\u00bb)\]]+)?"
_ZIN = re.compile(_MARK.pattern + "|" + _Z + r"+[.!?]*" + _SLUIT + r"\s*|[.!?]+" + _SLUIT + r"\s*")
_OPENER = {'"': '"', "'": "'", "\u201d": "\u201c", "\u2019": "\u2018", "\u00bb": "\u00ab", ")": "(", "]": "["}


def _los_sluitteken(kern):
    """Het sluitteken achter de punt dat een citaat of haakje van een eerdere zin sluit: het openingsteken staat niet in
    deze zin. Wordt de zin geschrapt of gemarkeerd, dan blijft dat teken staan (38e review); een citaat dat in de zin
    zelf opent, gaat mee weg (37e review)."""
    m = re.search(r"[.!?]([\"'\u201d\u2019\u00bb)\]]+)$", kern)
    if not m:
        return ""
    romp, blijft = kern[:m.start(1)], ""
    for t in m.group(1):
        o = _OPENER[t]
        if (romp.count(t) % 2 == 1) if o == t else (romp.count(o) > romp.count(t)):
            romp += t          # sluit iets dat in deze zin opende
        else:
            blijft += t
    return blijft
# Een kaal tijdstip tussen haakjes; telt alleen als opnameverwijzing als de tekst zelf zegt dat zo'n tijdstip naar de
# opname verwijst (de legende), anders is "(10:15)" gewoon een uur.
_KAAL_TIJDSTIP = re.compile(r"\s*\(\s*" + _OPNAMETIJDEN + r"\s*\)")   # een schaal (1:50) is geen tijdstip (29e review)
_KAAL_REGEL = re.compile(r"\(\s*" + _OPNAMETIJDEN + r"\s*\)\s*[.!?]?")
_OPSOMMING = re.compile(r"[ \t]*(?:[-*•]|\d{1,2}[.)])[ \t]+")


def _verwijzingsregels_weg(tekst, legende):
    """Een regel die alleen een opnameverwijzing is, valt helemaal weg met haar regelovergang, en tussen twee alinea's ook
    met één lege regel: zo blijft er geen losse punt of extra lege regel over (32e review). Alleen na een zinseinde, een
    kop of een lege regel; na 'raam, zie' loopt de zin door op de volgende regel (24e review). Een opsommingspunt dat
    alleen een verwijzing is ("- Zie opname 00:12:05."), valt ook helemaal weg, zonder "-." achter te laten."""
    regels, uit, n = tekst.split("\n"), [], 0
    for i, regel in enumerate(regels):
        punt = _OPSOMMING.match(regel)
        kern = regel[punt.end():].strip() if punt else regel.strip()
        verwijzing = _REGEL_VERWIJZING.fullmatch(kern) or (legende and _KAAL_REGEL.fullmatch(kern))
        if not verwijzing or (not punt and re.search(r"[\w,\-–]$", uit[-1].rstrip() if uit else "")):
            uit.append(regel)
            continue
        n += 1
        if uit and not uit[-1].strip() and (i + 1 == len(regels) or not regels[i + 1].strip()):
            uit.pop()
    return "\n".join(uit), n


def _is_s4(kern):
    return _s4_begin(kern) is not None


# Een vervolgregel van een opnamezin die met een tijdstip begint ("(00:12:30).", "00:05:10).", "om 10:15."), of een regel
# die eindigt op een woord waarmee geen zin eindigt ("... naar de opname van"): de zin loopt door (39e review)
_TIJD_VOORAAN = re.compile(r"\s*[(\[]?\s*(?:(?:om|op|van|tot|at)\s+)?" + _DIRECTTIJD, re.I)
_ONAF = re.compile(r"\b(?:van|de|het|een|naar|tot|om|met|voor|bij|door|aan|the|of|to|at|a|an)\s*$", re.I)


def _vervolg(regel):
    """Kan deze regel het vervolg van een zin op de vorige regel zijn: kleine letter of een tijdstip vooraan."""
    return regel.lstrip()[:1].islower() or bool(_TIJD_VOORAAN.match(regel))


def _vooruit(stukken, i, regels=3):
    """De volgende regels die nog bij dezelfde zin kunnen horen (geen leesteken op het einde, kleine letter vooraan)."""
    uit = stukken[i]
    for j in range(i + 1, min(i + regels, len(stukken))):
        if uit.strip().endswith((".", "!", "?", ";", ":")) or "\n" not in uit or not _vervolg(stukken[j]):
            break
        uit += stukken[j]
    return uit


def _loopt_door(zin, volgende, vooruit=None):
    """Loopt een S4-zin over een harde regelovergang door naar de volgende regel (die met een kleine letter begint)?
    Ja als de opnamezin pas samen herkenbaar is en in deze regel begint ('volgens de\nopname'), als de volgende regel de
    opnamewoorden voortzet ('verwijst naar\nde opname van het plaatsbezoek'), of als deze regel alleen meta-woorden heeft
    ('De architect\nsprak zijn vaststellingen in'). Een opsomming ('de goot lekt\nde architect sprak ...') loopt niet door."""
    vooruit = vooruit or volgende
    samen = (zin + vooruit).lstrip()   # tot drie regels vooruit: een opnamezin met twee harde regelovergangen (23e review)
    if not _is_s4(zin.strip()) and _begint_in(_s4_begin(samen), zin):
        return True
    if _is_s4(zin.strip()) and re.search(r"\b(?:opname|geluidsopname|transcript|tijdstip|haakjes|recording)\b", volgende, re.I):
        return True
    if _is_s4(zin.strip()) and (_TIJD_VOORAAN.match(volgende) or _ONAF.search(zin.rstrip())):
        return True
    return bool(_woorden_in(zin) and not _is_s4(zin.strip()) and _alleen_meta(zin) and _is_s4(samen))


def _woorden_in(tekst):
    return re.findall(r"[^\W\d_]{2,}", tekst)


def _begint_in(begin, zin):
    """De S4-zin begint in deze regel (niet pas in de volgende)."""
    return begin is not None and begin < len(zin.strip())


def _s4_begin(kern):
    """Waar de eerste S4-zin in de tekst begint, of None."""
    begins = [m.start() for p in [SPRAK, OPNAME_VOLGENS, *OPNAME_ZINNEN] for m in [p.search(kern)] if m]
    return min(begins) if begins else None


def _opname_weg(tekst):
    """Haalt opnameverwijzingen weg, per zin: (tekst, [(S4, geschrapte zin of 'opnameverwijzing')])."""
    ingrepen = []
    delen = []
    markering = MARKERING.format(regel="S4")

    def weg(staart, blijft=""):
        # de zin valt weg; tussen wat ervoor en erna staat blijft de grootste regelafstand van de twee (lijstpunten en
        # alinea's plakken niet aan elkaar, en er komt geen lege regel bij); een sluitteken van een eerdere zin blijft
        if blijft:
            if delen:
                romp = delen[-1].rstrip(" \t")
                delen[-1] = romp + blijft + delen[-1][len(romp):]
            else:
                delen.append(blijft + " ")
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
               and _vervolg(stukken[i]) and _loopt_door(zin, stukken[i], _vooruit(stukken, i))):
            zin += stukken[i]
            i += 1
        kern = zin.strip()
        kop, staart = zin[:len(zin) - len(zin.lstrip())], zin[len(zin.rstrip()):]
        if _MARK.fullmatch(kern):
            delen.append(zin)
            continue
        is_legende = any(p.search(kern) for p in OPNAME_ZINNEN)
        if SPRAK.search(kern) or is_legende:
            # 20e review: een zin over het inspreken of de legende valt alleen stil weg als elk woord een meta-woord is;
            # staat er iets anders in (een vaststelling, met komma, 'en' of puntkomma eraan), dan zichtbaar gemarkeerd
            ingrepen.append(("S4", kern))
            legende = legende or is_legende
            if _alleen_meta(kern) and not OPNAME_VOLGENS.search(kern):
                weg(staart, _los_sluitteken(kern))
            else:
                delen.append(kop + markering + _los_sluitteken(kern) + staart)
            continue
        if OPNAME_VOLGENS.search(kern):
            ingrepen.append(("S4", kern))
            delen.append(kop + markering + _los_sluitteken(kern) + staart)
            continue
        delen.append(zin)
    tekst, k = _verwijzingsregels_weg("".join(delen), legende)
    ingrepen += [("S4", "opnameverwijzing")] * k
    for p in [OPNAME_LOS, OPNAME_LOS_HAAKJES] + OPNAME + ([_KAAL_TIJDSTIP] if legende else []):
        tekst, k = p.subn("", tekst)
        ingrepen += [("S4", "opnameverwijzing")] * k
    tekst = re.sub(r"[ \t]+([,.;:)])", r"\1", tekst)
    tekst = re.sub(r"\(\s*\)", "", tekst)
    return re.sub(r"[ \t]{2,}", " ", tekst).strip(), ingrepen


def bron_zichtbaar(bron):
    """De bron zoals ze in een verslag mag staan: zonder opnametijdstip en zonder 'opname 00:12' (S4). Bestandsnamen,
    een opmeting ('Opname plaatsgesteldheid expert Claes.pdf') en een schaal (1:100) blijven; het volledige veld bron
    blijft in de gegevens ("factuur 2026-114, zie opname 00:12:05" wordt "factuur 2026-114"). 28e review."""
    b = re.sub(r"\s*\n\s*", " / ", str(bron or "").strip())
    b = re.sub(r"\s*\(\s*" + _ZIE + _OPNAMEWOORD + _NA_WOORD_HAAKJE + _DIRECTTIJD + r"[^()]*\)", "", b, flags=re.I)
    b = re.sub(r"\s*\([^()]*" + _OPNAMETIJD + r"[^()]*\)", "", b)
    b = re.sub(r",?\s*(?<![\w-])" + _VERWIJZING, "", b, flags=re.I)
    b = re.sub(r"(?:,?\s*(?:zie\s+)?(?:de\s+)?(?:opname|geluidsopname|audio|recording)\s+(?:van\s+|at\s+|om\s+)?)?" + _OPNAMETIJDEN, "", b, flags=re.I)
    b = re.sub(r"\(\s*\)", "", b)
    return re.sub(r"\s{2,}", " ", b).strip(" ,;:-/")


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
                delen.append(zin[:len(zin) - len(zin.lstrip())] + MARKERING.format(regel=regel) + _los_sluitteken(zin.strip())
                             + (staart if "\n" in staart else " "))
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

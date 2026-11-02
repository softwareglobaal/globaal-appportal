"""Alleen de productvraag gaat naar het taalmodel (driehoeksoverleg 30-10-2026, X4 en K6).

Staat er iets in de vraag dat op persoons- of firmagegevens lijkt, dan gaat de vraag niet weg: de agent zegt welke
soort hij zag en vraagt de vraag opnieuw te stellen zonder. Liever een vraag te veel tegenhouden dan een adres of
rekeningnummer naar buiten sturen.

"Mr." en "Mrs." met een uitzondering voor productnamen als Mr. Proper en Mr. Muscle (Codex X10, ronde 3).

Een gewone naam zonder aanspreking ("Jan Peeters") vangt een lijst van gangbare voornamen gevolgd door een woord met
een hoofdletter (overleg 39, K4). Merknamen met een voornaam (Herman Miller, Tommy Hilfiger) staan in een
uitzonderingslijst, en voornamen die vaak een merk of model zijn (Victor, Leon, Max, Stanley) staan niet in de lijst.
Een onbekende voornaam glipt erdoor; daarom ook aan de bron: De Regisseur geeft alleen product, land en firma of privé
door (zijn tool agent_ronde), en de vraag zelf komt nooit in het logboek, alleen een vingerafdruk (Codex X3).
"""
import re

VOORNAMEN = (
    "Jan|Peter|Pieter|Piet|Joris|Koen|Tom|Bart|Wim|Dirk|Luc|Marc|Mark|Patrick|Johan|Geert|Kris|Kristof|Christophe|Steven|"
    "Stefan|Stijn|Jeroen|Jens|Bram|Wout|Thomas|Lucas|Liam|Noah|Arthur|Louis|Jules|Lars|Simon|Pieterjan|Frank|Erik|Eric|"
    "Paul|Filip|Philippe|Willem|Hans|Danny|David|Daniel|Michael|Michiel|Nicolas|Nico|Kevin|Dries|Ruben|Robbe|Seppe|"
    "Ahmed|Mohamed|Mehmet|Ali|Youssef|Hassan|Omar|Ibrahim|Mustafa|Rachid|Karim|"
    "Marie|Maria|Anna|Anne|An|Ann|Els|Elke|Inge|Ilse|Katrien|Kathleen|Sofie|Sophie|Lotte|Lien|Eva|Emma|Julie|Laura|"
    "Sarah|Sara|Lisa|Nina|Hanne|Hannelore|Leen|Lieve|Linda|Martine|Nathalie|Veerle|Griet|Greet|Nele|Fien|Fleur|Louise|"
    "Olivia|Mila|Elise|Lara|Lena|Charlotte|Caroline|Isabelle|Ingrid|Annelies|Evelien|Karen|Kim|Sandra|Fatima|Aisha|"
    "Khadija|Amina|Samira|Leila|Yasmina|Herman|Tommy|Calvin|Ralph|Hugo|Karl|Ted|Jamie|Russell|Kenneth|Steve|Fred|Ben"
)
# Merken met een voornaam: geen persoon (overleg 39, K4).
MERKEN = ("herman miller", "tommy hilfiger", "calvin klein", "ralph lauren", "hugo boss", "karl lagerfeld", "ted baker",
          "jamie oliver", "russell hobbs", "kenneth cole", "steve madden", "fred perry", "ben sherman", "tom ford",
          "tom dixon", "tom tailor", "paul smith", "marc jacobs", "michael kors", "anna sui", "jan kurtz")

PATRONEN = (
    ("e-mailadres", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("rekeningnummer", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[0-9A-Z]{4}){2,7}\b")),
    ("rijksregisternummer", re.compile(r"\b\d{2}[.\s]?\d{2}[.\s]?\d{2}[-\s]?\d{3}[.\s]?\d{2}\b")),
    ("ondernemingsnummer", re.compile(r"\b[01]\d{3}[.\s]\d{3}[.\s]\d{3}\b")),
    ("telefoonnummer", re.compile(r"(?:\+\d{2,3}[\s./-]?|\b0)\d{2,3}(?:[\s./-]?\d{2,3}){2,4}\b")),
    ("naam", re.compile(r"\b(?i:dhr|mevr|meneer|mevrouw|heer|madame|monsieur|herr|frau)\.?\s+[A-Z][a-z]+"
                        r"|\b(?i:mr|mrs)\.?\s+(?!(?:Proper|Muscle|Clean|Bean|Coffee|Freeze|Frosty|Handyman)\b)[A-Z][a-z]+"
                        r"|\b(?i:klant|bewoner|eigenaar|naam)\s*:?\s+[A-Z][a-z]+\s+[A-Z][a-z]+")),
    ("naam", re.compile(rf"\b(?:{VOORNAMEN})\s+(?:(?i:van|de|der|den|ter|ten|te|het|op|du|la|le|da|di|von|el|al)\s+)*"
                        r"[A-Z][a-zà-ÿ]+(?:[-'][A-Za-zà-ÿ]+)?\b")),
    ("adres", re.compile(r"\b[A-Z][a-zà-ÿ]+(?:straat|laan|lei|weg|plein|steenweg|dreef|kaai|baan|hof)\s+\d+[a-z]?\b", re.I)),
)


def gevonden(tekst):
    """De soorten persoonsgegevens in de vraag, elk een keer, in vaste volgorde; leeg als er niets op lijkt.
    Wat een specifieker patroon al vond, telt niet nog eens mee (een rekeningnummer is geen telefoonnummer)."""
    tekst, uit = tekst or "", []
    for merk in MERKEN:
        tekst = re.sub(rf"\b{re.escape(merk)}", " ", tekst, flags=re.I)
    for soort, patroon in PATRONEN:
        if patroon.search(tekst):
            uit.append(soort)
            tekst = patroon.sub(" ", tekst)
    return uit

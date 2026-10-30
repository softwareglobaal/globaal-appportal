"""Alleen de productvraag gaat naar het taalmodel (driehoeksoverleg 30-10-2026, X4 en K6).

Staat er iets in de vraag dat op persoons- of firmagegevens lijkt, dan gaat de vraag niet weg: de agent zegt welke
soort hij zag en vraagt de vraag opnieuw te stellen zonder. Liever een vraag te veel tegenhouden dan een adres of
rekeningnummer naar buiten sturen.

Een gewone naam zonder aanspreking ("Jan Peeters") herkent een patroon niet zonder ook merknamen te blokkeren
("Apple Watch", "Harmonie Bouw"). Daarom ook aan de bron: De Regisseur geeft alleen product, land en firma of privé
door (zijn tool agent_ronde), en de vraag zelf komt nooit in het logboek, alleen een vingerafdruk (Codex X3).
"""
import re

PATRONEN = (
    ("e-mailadres", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("rekeningnummer", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[0-9A-Z]{4}){2,7}\b")),
    ("rijksregisternummer", re.compile(r"\b\d{2}[.\s]?\d{2}[.\s]?\d{2}[-\s]?\d{3}[.\s]?\d{2}\b")),
    ("ondernemingsnummer", re.compile(r"\b[01]\d{3}[.\s]\d{3}[.\s]\d{3}\b")),
    ("telefoonnummer", re.compile(r"(?:\+\d{2,3}[\s./-]?|\b0)\d{2,3}(?:[\s./-]?\d{2,3}){2,4}\b")),
    ("naam", re.compile(r"\b(?i:dhr|mevr|mr|mrs|meneer|mevrouw|heer|madame|monsieur|herr|frau)\.?\s+[A-Z][a-z]+"
                        r"|\b(?i:klant|bewoner|eigenaar|naam)\s*:?\s+[A-Z][a-z]+\s+[A-Z][a-z]+")),
    ("adres", re.compile(r"\b[A-Z][a-zà-ÿ]+(?:straat|laan|lei|weg|plein|steenweg|dreef|kaai|baan|hof)\s+\d+[a-z]?\b", re.I)),
)


def gevonden(tekst):
    """De soorten persoonsgegevens in de vraag, elk een keer, in vaste volgorde; leeg als er niets op lijkt.
    Wat een specifieker patroon al vond, telt niet nog eens mee (een rekeningnummer is geen telefoonnummer)."""
    tekst, uit = tekst or "", []
    for soort, patroon in PATRONEN:
        if patroon.search(tekst):
            uit.append(soort)
            tekst = patroon.sub(" ", tekst)
    return uit

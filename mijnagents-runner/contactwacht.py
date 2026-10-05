#!/usr/bin/env python3
"""De Contactwacht (Algemeen): houdt de contactendatabase in lijn met de afspraken.

Elk contact zegt wie iemand is, bij welke firma hij klant of prospect is, onder welk
dossier en voor welke dienst, zodat wie opneemt meteen weet wie er belt. De regels staan
in werkwijze/contactwacht.md; die tekst is ook de werkwijze op het bord en de PDF.

Versie 0.2 (29-09-2026) leest alleen. De contactcodes (HA, UN, ...) komen uit
organisatie.globaal.be (kern.firma, migratie 175), nergens anders: een code die daar
verandert, geldt bij de volgende ronde. Hij telt in de index van de contactsync hoeveel
contacten al in de nieuwe vorm staan, hoeveel nog een oude code dragen en hoeveel een
dossiercode van een firma die daar niet staat, en zet de open beslissingen als noden op
het bord. Schrijven in Google Contacts komt pas na die beslissingen, en dan alleen na
goedkeuring.

    contactwacht.py            een ronde
"""
import os
import re
import sqlite3
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import organisatie  # noqa: E402
import nummerlezer  # noqa: E402

NAAM = "contactwacht"
ag = bord.Agent(NAAM)

# De index van de contactsync: een doorzoekbare kopie van Google Contacts. Alleen lezen.
SYNC_DB = os.environ.get("CONTACTSYNC_DB", os.path.expanduser("~/appportal/contactsync-data/sync.db"))

# Een dossier in de naamregel: twee hoofdletters aan het nummer geplakt (HA5609, UN3782, UB260009).
# Of die twee letters een firma zijn, zegt organisatie.globaal.be, niet deze code. Het patroon is dat van
# de gedeelde nummerlezer (codering WP1); tot 05-10-2026 las het maar drie tot vijf cijfers.
DOSSIER = nummerlezer.DOSSIERCODE
OUD_HA = re.compile(r"\bH-A\b")
OUD_KL = re.compile(r"^KL\b")

# De open beslissingen uit hoofdstuk 5 van de werkwijze. Zonder aantal in de tekst (N10):
# zolang ze hier staan, zijn ze open; een beslissing die genomen is, gaat uit deze lijst.
OPEN = [
    "Beslissen hoe een gemengde status in de naamregel staat: klant bij de ene firma, prospect bij de andere",
    "Beslissen of de diensten in de naamregel staan of alleen in de kaart, na de schermtest in Xelion",
    "Beslissen welk nummer een UNABO-dossier draagt, en dat van TKN-Buro",
    "Beslissen wie voorstellen mag goedkeuren: Mehdi alleen, of ook Siyan voor zijn firma's",
    "Beslissen of de bestaande contacten met H-A en KL worden omgezet, en in welke volgorde",
]


def meet(pad, codes):
    """Tellingen uit de index van de contactsync. Geen namen: op het bord staan aantallen.
    codes: de contactcodes uit organisatie.globaal.be; leeg als die niet leesbaar zijn,
    en dan wordt er niet geoordeeld over onbekende codes."""
    con = sqlite3.connect(f"file:{pad}?mode=ro", uri=True)
    namen = [n or "" for (n,) in con.execute(
        # de sync zet de status op "gearchiveerd" (niet "archief") en de naam krijgt "[ARCHIEF] " vooraan
        "select display_name from contact_details where coalesce(status, 'actief') != 'gearchiveerd' "
        "and coalesce(display_name, '') not like '[ARCHIEF]%'")]
    dossiers = [[code for code, _ in DOSSIER.findall(n)] for n in namen]
    return {
        "actief": len(namen),
        "nieuwe_vorm": sum(1 for d in dossiers if d and (not codes or all(c in codes for c in d))),
        "onbekende_code": sum(1 for d in dossiers if codes and any(c not in codes for c in d)),
        "met_h_a": sum(1 for n in namen if OUD_HA.search(n)),
        "met_kl": sum(1 for n in namen if OUD_KL.search(n)),
    }


def werk(r):
    r.bron("contactsync-index", SYNC_DB)
    codes = organisatie.contactcodes(maximum_uren=1)
    r.bron("organisatie-contactcodes", codes)
    if not codes:
        r.nood("De contactcodes zijn niet leesbaar uit organisatie.globaal.be", wie="claude-code")
    regel = organisatie.bronregel("firma")
    if regel is None:
        r.nood("De regel Firma op de pagina Bron van de waarheid is niet leesbaar", wie="claude-code")
    elif regel.get("status") != "besloten":
        r.nood("De contactcodes bevestigen: op organisatie.globaal.be/bronnen de regel Firma op Besloten zetten",
               wie="mehdi")
    if not os.path.exists(SYNC_DB):
        r.nood("De index van de contactsync is niet leesbaar", wie="claude-code")
        r.detail = "index niet gevonden"
        return
    t = meet(SYNC_DB, codes)
    r.detail = (f"{t['actief']} actieve contacten; {t['nieuwe_vorm']} in de nieuwe vorm; "
                f"{t['onbekende_code']} met een dossiercode van een firma die niet in organisatie.globaal.be staat; "
                f"{t['met_h_a']} met de oude code H-A; {t['met_kl']} met KL vooraan. "
                f"Contactcodes uit organisatie: {', '.join(sorted(codes)) or 'geen'}. "
                "Versie 0.2: ik meet, ik schrijf niets.")
    if t["onbekende_code"]:
        r.nood("Naamregels met een dossiercode van een firma die niet in organisatie.globaal.be staat", wie="mehdi")
    for tekst in OPEN:
        r.nood(tekst, wie="mehdi")


if __name__ == "__main__":
    with ag.ronde("contacten meten") as r:
        werk(r)

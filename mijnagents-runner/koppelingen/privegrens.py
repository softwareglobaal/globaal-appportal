"""De privéregel van de gesprekkentabel (gesprek_log) op één plek, per bron (T-0120 VOL-2, aanscherping van DB-8).

Tot 01-11-2026 had elke lezer zijn eigen regel: De Dagbundelaar (koppelingen/dagvaststelling.py) nam de vlag, de
afdeling en elke rij van de Mac; De Communicatiebundelaar de vlag en de afdeling; de wachtenpagina
(mijnagents/wachten_dag.py) alleen de afdeling. Zo toonde die pagina van Zoom- en Fathom-rijen met prive=1 en
afdeling onbekend de naam en het onderwerp (gemeten: 99 rijen sinds 01-10).

De regel per bron:
- zoom, fathom, plaud, mail en elke andere bron: de vlag prive is de privéregel van De Regisseur (RZ3-01). Afdeling
  prive of privé, in elke schrijfwijze, is ook privé, ook bij prive=0.
- whatsapp, telefoon, sms en xelion (de Mac-kanalen): elke rij is privé, wat de vlag ook zegt (D5). Daar betekent
  prive=1 "van de Mac van Mehdi, alleen voor Mehdi".
- De bewuste uitzondering (voor_mehdi=True): een pagina die alleen Mehdi ziet, toont van een Mac-kanaal naam en aantal,
  nooit tekst (de wachten bewaren die ook niet). Afdeling privé blijft ook daar privé.

Een lezer zonder kolom bron (De Communicatiebundelaar) krijgt de bron uit het voorvoegsel van uniek.

Dit bestand staat twee keer in de repo: hier, voor de runners, en als mijnagents/privegrens.py, want de image van het
bord bevat alleen de map mijnagents. tests/test_privegrens.py eist dat beide gelijk zijn en dat de drie lezers per rij
hetzelfde zeggen.
"""

MAC_BRONNEN = ("whatsapp", "telefoon", "sms", "xelion")
# De bron uit uniek, het langste voorvoegsel eerst (whatsapp-oproep: voor whatsapp:, zoom:chat: valt onder zoom:).
VOORVOEGSELS = (("whatsapp-oproep:", "whatsapp"), ("whatsapp:", "whatsapp"), ("telefoon:", "telefoon"), ("sms:", "sms"),
                ("xelion:", "xelion"), ("zoom:", "zoom"), ("fathom:", "fathom"), ("plaud:", "plaud"), ("mail:", "mail"))


def _veld(rij, naam):
    """Een veld van een dict of een sqlite3.Row; ontbreekt het, dan None."""
    try:
        return rij[naam]
    except (KeyError, IndexError):
        return None


def bron(rij):
    """De bron van een rij: de kolom bron, anders het voorvoegsel van uniek; onbekend is leeg."""
    b = str(_veld(rij, "bron") or "").strip().casefold()
    if b:
        return b
    u = str(_veld(rij, "uniek") or "")
    return next((b for voor, b in VOORVOEGSELS if u.startswith(voor)), "")


def afdeling_prive(afdeling):
    return str(afdeling or "").strip().casefold() in ("prive", "privé")


def is_prive(rij, voor_mehdi=False):
    """Is deze rij van de gesprekkentabel privé? voor_mehdi=True alleen voor een pagina die alleen Mehdi ziet: dan
    houdt een Mac-kanaal zonder afdeling privé naam en aantal."""
    if afdeling_prive(_veld(rij, "afdeling")):
        return True
    if bron(rij) in MAC_BRONNEN:
        return not voor_mehdi
    return bool(_veld(rij, "prive"))

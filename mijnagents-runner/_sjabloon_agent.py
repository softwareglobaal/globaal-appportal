#!/usr/bin/env python3
"""%%LABEL%% : runner voor mijnagents.globaal.be.

Gegenereerd door nieuwe-agent.py. Draait op de host via cron (buiten de
container) en praat met het bord via de gedeelde module `bord`.

Vul werk(r) in. De ronde eromheen regelt wat de Agentnorm eist, zodat je daar
zelf niet aan hoeft te denken (zie AGENTNORM.md):

  N4  hij meldt welk regelboek hij deze ronde las, met een vingerafdruk per
      bron, zodat achteraf te zien is welke regels golden toen hij iets deed;
  N10 een nood zonder aantal in de tekst, zodat dezelfde nood morgen dezelfde
      nood is en de lus kan sluiten. Het aantal zet je in r.detail;
  N11 hij blijft nooit hangen op "actief": een ronde die breekt meldt "fout".

Houd je aan de grenzen die op het bord staan en aan de zichtbaarheidsregel: in
taak en detail alleen neutrale werkstatus, nooit inhoud (geen klantnamen, geen
bedragen).

Muteren mag NIET rechtstreeks: doe een voorstel (stel_voor) dat Mehdi op het
bord goedkeurt. Pas na goedkeuring voert de uitvoerder het uit.
"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402

NAAM = "%%NAAM%%"
ag = bord.Agent(NAAM)


def stel_voor(actie, doel="", reden="", parameters=None, runbook=""):
    """Zet een voorstel op het bord. Zonder parameters is het een louter signaal
    (nooit autonoom uitvoerbaar); met parameters wordt het, na goedkeuring van
    Mehdi, door de uitvoerder uitgevoerd."""
    return ag.hartslag("waakt", taak=actie, detail=reden, voorstel={
        "actie": actie, "doel": doel, "reden": reden,
        "parameters": parameters, "runbook": runbook,
    })


def werk(r):
    """VUL DIT IN. Doe hier het echte werk van de agent.

    `r` is de ronde. Wat je ermee kunt:

        r.werkwijze          de tekst zoals ze nu op het bord staat, jouw regelboek
        r.bron(naam, tekst)  een ander regelboek dat je las (een JSON, een document)
        r.nood(tekst, wie)   wat je nodig hebt; wie is mehdi, claude-code of collega
        r.detail = "..."     neutrale samenvatting van deze ronde, met de aantallen

    Voorbeeld:
        gedaan = 0
        for item in iets():
            gedaan += 1
        r.detail = f"{gedaan} items bekeken"
        if gedaan == 0:
            r.nood("Geen bron gevonden om te lezen", wie="claude-code")
    """
    r.detail = "skelet, werk() nog in te vullen"


if __name__ == "__main__":
    with ag.ronde("ronde") as r:
        werk(r)

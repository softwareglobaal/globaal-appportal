#!/usr/bin/env python3
"""De Mailwacht mch@ (mch@h-architects.be). Leest via de postbus, zet wat opvolging vraagt klaar
voor De Mailregisseur, en ruimt alleen op wat Mehdi op het maildashboard aanklikte. Alle regels staan in koppelingen/postvak.py en werkwijze/mailwachten.json,
zodat elke mailwacht dezelfde regels volgt. Werkwijze op het bord: werkwijze/mail-mch.md.

    mail_mch.py            een ronde (07-21 Brusselse tijd)
    mail_mch.py --droog    tonen wat er klaargezet zou worden, niets naar het bord
    mail_mch.py --nu       een ronde, ook buiten 07-21
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "koppelingen"))
import bord  # noqa: E402
import postvak  # noqa: E402

NAAM = "mail-mch"

if __name__ == "__main__":
    if "--droog" in sys.argv:
        postvak.droog(NAAM)
    elif postvak.aan_de_beurt() or "--nu" in sys.argv:
        ag = bord.Agent(NAAM)
        with ag.ronde("postvak in het oog") as r:
            postvak.werk(NAAM, ag, r)

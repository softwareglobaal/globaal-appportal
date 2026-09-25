#!/usr/bin/env python3
"""De Mailwacht H-Invest (info@ en boekhouding@; vroeger H-Aannemingen). Leest alleen, via de postbus, en zet wat opvolging vraagt klaar
voor De Mailregisseur. Alle regels staan in koppelingen/postvak.py en werkwijze/mailwachten.json,
zodat elke mailwacht dezelfde regels volgt. Werkwijze op het bord: werkwijze/mail-hinv.md.

    mail_hinv.py            een ronde (07-21 Brusselse tijd)
    mail_hinv.py --droog    tonen wat er klaargezet zou worden, niets naar het bord
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "koppelingen"))
import postvak  # noqa: E402

if __name__ == "__main__":
    postvak.draai("mail-hinv", droog="--droog" in sys.argv)

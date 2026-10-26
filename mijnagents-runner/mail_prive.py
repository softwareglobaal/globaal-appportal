#!/usr/bin/env python3
"""De Mailwacht hotmail (mehdichegini@hotmail.com). Leest de koppen uit het bestand dat elke run eerst vers maakt op de server (koppelingen/hotmail_server.py,
sinds 26-10-2026; tot dan leverde de Mac het aan, mac/hotmail_koppen.py), zet wat opvolging vraagt klaar
voor De Mailregisseur, en ruimt alleen op wat Mehdi op het maildashboard aanklikte. Alle regels staan in koppelingen/postvak.py en werkwijze/mailwachten.json,
zodat elke mailwacht dezelfde regels volgt. Werkwijze op het bord: werkwijze/mail-prive.md.

    mail_prive.py            een ronde (07-21 Brusselse tijd)
    mail_prive.py --droog    tonen wat er klaargezet zou worden, niets naar het bord
    mail_prive.py --nu       een ronde, ook buiten 07-21
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "koppelingen"))
import bord  # noqa: E402
import hotmail_server  # noqa: E402
import postvak  # noqa: E402

NAAM = "mail-prive"

if __name__ == "__main__":
    if "--droog" in sys.argv:
        postvak.droog(NAAM)
        sys.exit()
    # Elk uur, ook buiten 07-21: eerst de koppen vers. Lukt dat niet, dan blijft het vorige bestand staan en meldt de wacht
    # zelf dat het niet vers is (postvak.BRON_VERS_UREN); de reden staat hier in het logboek.
    try:
        print(hotmail_server.ververs(*hotmail_server.bron()), flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"hotmail-koppen niet ververst: {type(e).__name__}: {str(e)[:300]}", flush=True)
    if postvak.aan_de_beurt() or "--nu" in sys.argv:
        ag = bord.Agent(NAAM)
        with ag.ronde("postvak in het oog") as r:
            postvak.werk(NAAM, ag, r)

#!/usr/bin/env python3
"""ANGEL-7 (T-0120, P5): de voorlopige dagbundel van vandaag, twintig minuten voor elke ronde van Ai Angel.

De cron (planning/dagbundel-voorlopig.cron) start dit elk uur op :00; dagbundelaar.voorlopig_main kijkt zelf of het in
Brussel een van de uren van Ai Angel is en doet niets zolang dagbundelaar.VOORLOPIG_AAN uit staat (standaard). Het
bestand komt in ~/appportal/mijnagents-data/dagbundel-voorlopig/, nooit in de map dagboek (die gaat naar Dropbox); de
nachtronde blijft de vaststelling.

Een eigen ingang, geen cronregel met dagbundelaar.py: de planning van de gesprekkenketen (planning/gesprekken_cron_zetten.py)
weigert elke regel met dagbundelaar.py buiten haar eigen blok, en De Dagbundelaar is daar de laatste stap van de keten.
"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.argv = [sys.argv[0]]        # dagbundelaar leest zijn opties bij het importeren; deze ingang heeft er geen
import dagbundelaar  # noqa: E402

if __name__ == "__main__":
    sys.exit(dagbundelaar.voorlopig_main())

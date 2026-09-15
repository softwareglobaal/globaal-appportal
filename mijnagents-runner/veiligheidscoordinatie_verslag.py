#!/usr/bin/env python3
"""Veiligheidscoördinatie verslag (UNABO) — dunne runner op verslag_basis.py.

Werkwijze: werkwijze/veiligheidscoordinatie-verslag.md (en op het bord). Verslagsoort: koppelingen/verslagsoorten.py["veiligheidscoordinatie"].
Cron: elke 10 minuten; impulsen van het Commandocentrum, proef alleen op de knop op /commandocentrum.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verslag_basis import VerslagAgent  # noqa: E402

if __name__ == "__main__":
    VerslagAgent("veiligheidscoordinatie").main()

#!/usr/bin/env python3
"""Plaatsbeschrijving verslag (UNABO) — dunne runner op verslag_basis.py.

Werkwijze: werkwijze/plaatsbeschrijving-verslag.md (en op het bord). Verslagsoort: koppelingen/verslagsoorten.py["plaatsbeschrijving"].
Cron: elke 10 minuten; impulsen van het Commandocentrum, proef alleen op de knop op /commandocentrum.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verslag_basis import VerslagAgent  # noqa: E402

if __name__ == "__main__":
    VerslagAgent("plaatsbeschrijving").main()

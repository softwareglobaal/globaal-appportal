#!/usr/bin/env python3
"""Aankoopkeuring verslag (UNABO) — dunne runner op verslag_basis.py.

Werkwijze: werkwijze/aankoopkeuring-verslag.md (en op het bord). Verslagsoort: koppelingen/verslagsoorten.py["aankoopkeuring"].
Cron: elke 10 minuten; impulsen van het Commandocentrum, proef alleen op de knop op /commandocentrum.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verslag_basis import VerslagAgent  # noqa: E402

if __name__ == "__main__":
    VerslagAgent("aankoopkeuring").main()

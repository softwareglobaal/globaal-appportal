#!/usr/bin/env python3
"""Aankoopkeuring verslag (UNABO) : runner op verslag_basis.py met gedeelde ronde (N4, N12, N13, N14).

Werkwijze: werkwijze/aankoopkeuring-verslag.md (en op het bord). Verslagsoort: koppelingen/verslagsoorten.py["aankoopkeuring"].
Cron: elke 10 minuten; impulsen van het Commandocentrum, proef alleen op de knop op /commandocentrum.
"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
from verslag_basis import VerslagAgent  # noqa: E402


def main():
    va = VerslagAgent("aankoopkeuring")
    if len(sys.argv) > 1:
        va.main()
        return
    with va.ag.ronde("impulsen en opdrachten") as r:
        nooit, mehdi_beslist = bord.grenzen(r.werkwijze)
        if not nooit or not mehdi_beslist:
            r.nood("Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist", wie="mehdi")
            r.detail = "geen werk gedaan, grenzen ontbreken in de werkwijze"
            return
        va.ronde(ketenstand_toestaan=False)
        for n in getattr(va, "_noden", []) or []:
            r.nood(n.get("tekst", ""), wie=n.get("wie", "mehdi"))
        r.detail = f"impulsen en pakketten gecontroleerd; {len(nooit)} grenzen actief"


if __name__ == "__main__":
    main()

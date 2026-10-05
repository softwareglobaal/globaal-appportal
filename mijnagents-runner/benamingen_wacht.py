#!/usr/bin/env python3
"""Benamingenwacht: bestanden, mappen en bestaande agenda-/gespreksmetadata."""
from naamstructuur_ronde import main


def ronde(ag):
    return ag.ronde("naam- en structuurcontrole")


if __name__ == "__main__":
    raise SystemExit(main("benamingen-wacht", ronde))

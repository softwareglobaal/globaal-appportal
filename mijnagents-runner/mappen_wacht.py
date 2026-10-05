#!/usr/bin/env python3
"""Mappenwacht: structuurcontrole op dezelfde metadata als Benamingenwacht."""
from naamstructuur_ronde import main


def ronde(ag):
    return ag.ronde("naam- en structuurcontrole")


if __name__ == "__main__":
    raise SystemExit(main("mappen-wacht", ronde))

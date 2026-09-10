#!/usr/bin/env python3
"""Skelet voor een agent die op het bord bestaat (werkwijze, kaart, noden) maar
nog geen eigen runner heeft. Hij meldt eerlijk: status rust, en wat hij nodig
heeft om te gaan werken. Zo blijft de regel "alleen levende agents op het bord"
overeind zonder te doen alsof.
Gebruik: wacht_skelet.py --naam zoom-wacht --nood "..." [--wie mehdi] [--nood "..."]
"""
import argparse
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--naam", required=True)
p.add_argument("--nood", action="append", default=[])
p.add_argument("--wie", default="mehdi")
a = p.parse_args()
bord.Agent(a.naam).hartslag("rust", taak="wacht op wat ik nodig heb", detail="nog geen eigen runner; zie mijn kaart",
                            nood=[{"tekst": n, "wie": a.wie} for n in a.nood])
print(a.naam, "gemeld")

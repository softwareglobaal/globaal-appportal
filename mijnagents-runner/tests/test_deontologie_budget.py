"""Grendel op budget en verzekering in de toets van De Deontologiewacht (opdrachtkaart v0.3, stap 7).

Alleen verzonnen bedragen. Budget en verzekering zijn oordeelsregels: ze mogen nooit rood geven, ook niet bij een
budget dat verdubbelt.

Draaien: python3 mijnagents-runner/tests/test_deontologie_budget.py
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deontologie import budget as G  # noqa: E402
from deontologie import register as R  # noqa: E402
from deontologie import verslag as V  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  goed  {naam}")
    else:
        fout += 1
        print(f"  FOUT  {naam} {extra}")


VANDAAG = date.fromisoformat(R.laad()["stand"]) + timedelta(days=1)

print("Bedragen lezen")
check("Belgische schrijfwijze met decimalen", G.bedrag("250.000,00") == 250000.0)
check("zonder punten", G.bedrag("95000") == 95000.0)
check("geen bedrag", G.bedrag("geen") is None)
check("budget en oppervlakte uit een contract",
      G.uit_contract("met ca. 120 m² oppervlakte. Het Bouwbudget wordt door de Partijen op 300.000,00 euro vooropgesteld")
      == (300000.0, 120.0))
check("zonder budget", G.uit_contract("Er wordt eerst geraamd. ca. 120 m² oppervlakte") == (None, 120.0))

print("D2: budget tegen oppervlakte")
b = G.d2_begroting(240000, 120)
check("zonder referentie alleen de cijfers, onbekend", b.uitkomst == V.ONBEKEND and "2.000 euro per m²" in b.toelichting)
check("een budget ruim onder de referentie faalt", G.d2_begroting(120000, 120, referentie=2000).uitkomst == V.FAALT)
check("binnen de marge slaagt", G.d2_begroting(180000, 120, referentie=2000).uitkomst == V.SLAAGT)
check("zonder oppervlakte onbekend", G.d2_begroting(240000, None).uitkomst == V.ONBEKEND)

print("D3 en D5: kost boven het budget")
d3, d5 = G.overschrijding(200000, 220000, gemeld=False)
check("10 procent erboven blijft onder de drempel", d3.uitkomst == V.SLAAGT and d5.uitkomst == V.SLAAGT)
d3, d5 = G.overschrijding(200000, 400000, gemeld=False)
check("een verdubbeling zonder melding faalt D3", d3.uitkomst == V.FAALT and "+100 procent" in d3.toelichting)
check("en vraagt naar de verzekering", d5.uitkomst == V.ONBEKEND)
d3, d5 = G.overschrijding(200000, 400000, gemeld=True, verzekering_bijgewerkt=False)
check("met melding slaagt D3, een oude verzekering faalt D5", d3.uitkomst == V.SLAAGT and d5.uitkomst == V.FAALT)
check("zonder kost onbekend", G.overschrijding(200000, None, gemeld=False)[0].uitkomst == V.ONBEKEND)
v = V.maak("werfverslag", G.overschrijding(200000, 400000, gemeld=False, verzekering_bijgewerkt=False), vandaag=VANDAAG)
check("een verdubbeling zonder melding of verzekering is oranje, nooit rood",
      all(p.kleur == V.ORANJE for p in v.punten if p.code in ("D3", "D5")) and v.kleur == V.ORANJE)

print("D4: verzekering in het contract")
check("verzekeraar, polisnummer en tienjarige", G.d4_verzekering(
    "verzekerd bij Verzonnen Verzekeraar, polis nr. VZ123, voor de tienjarige aansprakelijkheid").uitkomst == V.SLAAGT)
check("zonder polisnummer faalt", G.d4_verzekering("verzekerd bij Verzonnen Verzekeraar, tienjarige").uitkomst == V.FAALT)
check("zonder verzekering faalt", G.d4_verzekering("Niets over verzekeringen.").uitkomst == V.FAALT)

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

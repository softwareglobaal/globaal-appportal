# Overleg 38: de handleiding zoeken via de EAN (02-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

## Meting

- **M5. Echte ronde na PR #161 (main 5ffa8f9c, VM 23:05 UTC).** 331k tokens via het abonnement, 0 dollar, week 64
  procent. Gelezen: RoboCleaners, haar verzendpagina, A&C Systems (zelfde EAN 6978794734941 met MOVA-RC-V70ULC-WHT),
  mova.tech en drie Coolblue-pagina's (niet beschikbaar). Niet leesbaar: device.report, manuals.plus, Amazon (HTTP 403).
  Werkverslag per eis voor RoboCleaners (961,50 euro, totaal volledig): modelcode `ja` (de code vond haar via dezelfde
  EAN op A&C), netfrequentie en netspanning `onbekend` (het model vond geen leesbare handleiding), levering niet
  bevestigd. Dus terecht geen aanbeveling.
- In proef 3 las het model wel Vanden Borre, die de handleiding linkt (220-240 V, 50-60 Hz); met PR #161 geeft de code
  dan RoboCleaners als aanbeveling (gratis nagemeten op de echte pagina's). Het verschil zit alleen in welke pagina's
  het model zoekt. De opdracht zegt nu: lees de handleiding die een winkelpagina van dit product linkt, en zoek na een
  onleesbare bron een andere bron voor dezelfde modelcode (`aankoop/onderzoek.py:114-125`), maar niet: zoek op de EAN.

## Voorstel: kleinste herstel

- **E.** Opdracht en werkwijze: vind je geen leesbare handleiding, zoek dan op de EAN-code of de modelcode met het woord
  handleiding of manual, en lees een winkelpagina met dezelfde EAN die een handleiding linkt (de regel "Documenten:");
  die telt als bewijs (overleg 35, C). Geen codewijziging.
- Daarna dezelfde vervolgvraag opnieuw echt op de VM. Telt als geslaagd: een aanbeveling met bewezen netwaarden, of een
  werkverslag dat toont waarom niet.

## Vragen

1. Akkoord met E: ja of nee; een nee alleen met een concreet scenario dat in een echte ronde een verkeerde aanbeveling
   of een betaling geeft, en dan de kleinste aanpassing.
2. Ontbreekt iets dat deze meting toont? Alleen met vindplaats.

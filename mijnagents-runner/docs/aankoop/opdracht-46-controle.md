# Codex-controle 46: herstel na controle 45 (02-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

Bekijk `git diff 06951573..523eb9d3` op de tak `aankoop-proefuitslag`. Achtergrond: `docs/aankoop/rapport-45-controle.md`.

- Hoog 1 en A/C: `ander_bedrag` in `aankoop/aanbod.py`; een gratis verzending telt niet als het citaat een ander bedrag
  noemt dan een drempel of 0,00. Test met je eigen scenario (Nederland gratis, Belgie 9,95) en met het echte citaat van
  beamerexpert.nl ("Uitstekende service en altijd gratis verzending", land NL).
- Hoog 2 en F: een ontkenning in het pasvormcitaat telt nooit; test met "Niet geschikt voor DDF484" en met het echte
  citaat van P09 (de set DDF484RTJ).
- D: `aankoop/leesserver.py` `_stand` en `lees`: verzendpagina van een gelezen host mag ook na de leesgrens.
- X7: vlak voor het plafond weigert de leestool elke lezing met de opdracht af te ronden; de opdracht zegt dan ook
  niets meer te zoeken.

Een hoge fout alleen met een concreet scenario dat in een echte ronde een verkeerde aanbeveling of een betaling geeft.

## Vragen

1. Zijn de punten van controle 45 hersteld? Ja, of wat ontbreekt met `bestand:regel`.
2. Een nieuwe fout van ernst hoog?
3. Klaar om live te zetten en de hele reeks opnieuw te draaien: ja of nee.

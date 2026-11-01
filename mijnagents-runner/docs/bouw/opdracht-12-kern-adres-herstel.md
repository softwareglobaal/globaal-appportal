# Opdracht 12: nacontrole van bouw/kern_adres.py na rapport 11 (01-11-2026)

Lees `mijnagents-runner/docs/bouw/rapport-11-kern-adres.md` en kijk de herstelde versie na (tak bouw-kern-adres, niet
gecommit: lees de werkboom). Antwoord in het Nederlands, kort: AKKOORD of NIET AKKOORD, met ernst en bewijs (bestand:regel).

Herstel:
- Hoog 1: `python -m bouw.kern_adres` eindigt met status 1 als `scheiding.laad_kern()` na afloop niet slaagt; `uitrol.sh`
  draait met `set -euo pipefail` en stopt dan voor de eerste ronde.
- Hoog 2: de update van kern.adres raakt een rij alleen als straat, huisnummer, postcode en gemeente alle vier leeg zijn.
  Een bestaande rij (gevonden via de dedup in `kern.adres_vind_of_maak`) met gegevens blijft ongemoeid; kern.firma wordt
  dan wel aan die rij gekoppeld, alleen als adres_id nog leeg is.
- Laag (audit): kern.audit bewaart de rij zoals elke wijziging in kern; het adres is het openbare KBO-adres van de zetel.
Tests: `python3 mijnagents-runner/tests/test_bouw.py` (234 goed).

# Opdracht 16: nacontrole van de KBO-lezing na rapport 15 (01-11-2026)

Lees `mijnagents-runner/docs/bouw/rapport-15-kbo-door-de-code.md` en kijk de herstelde versie na (tak bouw-kbo-zelf, niet
gecommit: lees de werkboom). Antwoord in het Nederlands, kort: AKKOORD of NIET AKKOORD, met ernst en bewijs (bestand:regel).

Herstel:
- Hoog 1: `keur` gebruikt alleen wat de code las als het nummer in `kbo` staat (`door_code`); een uitslag None valt nooit
  terug op een pagina van het model. Zonder lezing door de code (nummer niet in `kbo`, bv. na een OSError) blijft de oude
  weg met een gelezen KBO-pagina van het model.
- Middel 2: `lees_kbo` vraagt elk nummer een keer, ook na een OSError (`gevraagd`).
- Middel 3: elke oproep (hoofdpagina en vestigingspagina) start alleen als ze voor de deadline klaar kan zijn
  (`KBO_TIMEOUT` 10 s, `_tijd_voor`); `aannemerszoeker.py` geeft `kern_adres.haal` die timeout mee. Een OSError op de
  vestigingspagina laat alleen de plaats leeg.
- Middel 4: geen `kbo_url`-veld meer in VORM, het ondernemingsnummer "zoals op de eigen site", en "jij doet alleen het web".
Tests: `python3 mijnagents-runner/tests/test_bouw.py` (265 goed).

**Voor Mehdi:** Niet klaar. De gewone foutgevallen pauzeren in mijn eigen proeven, maar een nieuw hoofdstuk B kan onopgemerkt blijven. De vaste tests kon ik in deze leesmodus niet afronden.

**Voor Claude en Shaniel:**

1. **FOUT — grendel:** Alle 19 en 27 tests stoppen bij het aanmaken van een tijdelijke map; dit is een beperking van de leesmodus, geen gemeten codefout. Zie [test_regelbron_en_ha_voorrang.py](/Users/mehdichegini/dev/gap-namenwacht/mijnagents-runner/tests/test_regelbron_en_ha_voorrang.py:37) en [test_naamstructuur.py](/Users/mehdichegini/dev/gap-namenwacht/mijnagents-runner/tests/test_naamstructuur.py:23).
2. **FOUT (hoog) — verborgen regelwijziging:** Op de echte v1.10-bron voegde ik in geheugen voor een fictieve v1.11 `  ## B. Het verslag` met een nieuwe B2-regel toe. De hoofdstukhash bleef gelijk en de bron werd geldig verklaard. Zo’n ingesprongen kop is een [geldige Markdown-kop](https://spec.commonmark.org/current/#atx-headings), maar [hoofdstukken()](/Users/mehdichegini/dev/gap-namenwacht/mijnagents-runner/koppelingen/naamstructuur.py:463) mist hem. Herken geldige kopvormen en weiger dubbele A- of B-hoofdstukken.
3. **OK — nood:** Een werkelijk gewijzigd A of B pauzeert en gaat naar `claude-code`. Twee nagebootste rondes gaven dezelfde tekst, met versies en beide hashes; zie [naamstructuur_ronde.py](/Users/mehdichegini/dev/gap-namenwacht/mijnagents-runner/naamstructuur_ronde.py:53).
4. **OK — oude verwachtingen:** Geen uitvoerende code verwacht nog `regelbron.sha256` of “Welke versie geldt?”. Alleen historische documentatie noemt de oude situatie; zie [v1.0](/Users/mehdichegini/dev/gap-namenwacht/mijnagents-runner/docs/Namen%20en%20mappen%20-%20toezicht%20v1.0.md:23).

Gedaan: alleen lezend gecontroleerd tegen `origin/main`; niets gewijzigd.  
Nagekeken: echte v1.10-hash klopt met de nieuwe pin; eigen proeven voor ontbrekend, ouder, onleesbaar en gewijzigd pauzeren.  
Open: parser herstellen en beide grendels draaien in een omgeving met tijdelijke schrijfruimte.

**NIET AKKOORD**
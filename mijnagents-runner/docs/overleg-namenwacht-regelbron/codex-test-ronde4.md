**Niet klaar.** De wegwerpkopie vangt de eerdere kopvarianten, maar een opgemaakte B-kop verbergt nog steeds een nieuwe regel.

1. **FOUT — tests:** De regelbrontest slaagt 20/21; de nieuwe [aanvalstest](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/tests/test_regelbron_en_ha_voorrang.py:343) faalt. `test_naamstructuur.py` slaagt 27/27.

2. **FOUT — verborgen B-regel:** Uit de echte v1.10 maakte ik in geheugen een v1.11 met `## **B**. Het verslag` en een nieuwe B-regel. De A/B-vingerafdruk blijft gelijk en `geldig=True`: [naamstructuur.py](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/koppelingen/naamstructuur.py:493). [CommonMark](https://spec.commonmark.org/current/#atx-headings) verwerkt de opmaak in de koptekst.

3. **OK — archief:** `hoofdstukken()` pauzeert v1.8, v1.9 en v1.10 niet; alle drie leveren de [vastgepinde hash](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/werkwijze/naamstructuur-regels.json:24).

4. **FOUT — ontwerp:** Een deelvingerafdruk op basis van ruwe Markdown-koppen blijft omzeilbaar. Pin voorlopig de hash van het **hele boek per goedgekeurde versie**; maak A/B daarna een aparte, volledig vastgepinde regelbron. Zie de [huidige hashcontrole](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/koppelingen/naamstructuur.py:562).

Gedaan: parser, tests en [rondeverslag](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/docs/overleg-namenwacht-regelbron/codex-test-ronde4.md:1) aangepast.  
Nagekeken: beide tests en de echte v1.8–v1.10.  
Open: bronopzet vervangen en de falende test laten slagen.

**NIET AKKOORD.**
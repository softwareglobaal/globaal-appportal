# Controle 10 door Codex: verbeterronde De Prijsonderzoeker (commit a0ae6ce op tak aankoop-verbeter)

Lees alleen; wijzig niets. Gerichte controle.

Overleg: `mijnagents-runner/docs/aankoop/opdracht-9-verbeter.md` en `rapport-9-verbeter.md` (18 aangenomen, X2 en G3
afgewezen, K5 een grens). Bekijk `git diff origin/main..a0ae6ce`. Tests: `python3 mijnagents-runner/tests/test_aankoop_prijs.py`
(172 groen).

Wat er gebouwd is:
- `aankoop/aanbod.py`: `modelcode_op`, `_twee_regios`, `_waarde_in` (spanningsbereik), `bewijspagina`, en `compatibel`
  met een bewijs van een andere gelezen pagina voor netspanning en netfrequentie (X1, G1, K1).
- `aankoop/onderzoek.py`: 10.000 tokens per pagina (G2), 6 zoek en 6 lees (X5, G5), `task_budget` 250.000 via
  `client.beta.messages` met de beta (X3), tellers per aanvraag en de kost in dollar (X3), `zoekresultaten`,
  `leesbeurten`, `alleen_gezien` (X4).
- `aankoop/verslag.py`: sectie "Gezien, niet nagekeken" en het verbruik in de controleregel.
- `prijsonderzoeker.py`: nood boven 2 dollar, tellers in het logboek.
- Een afwijking van X4 die ik moet melden: de samenvatting van een zoekresultaat is versleuteld
  (`encrypted_content`), dus de code kan een prijs alleen in de titel of in een citaat (`cited_text`) bij die url
  nagaan. Zonder dat staat de link er zonder prijs.
- Niet in code: "hetzelfde onderdeel (basisstation)" uit X1. De code toetst dezelfde modelcode, geen tweede streek en
  geen accessoirewoord voor het citaat.

Vragen:
1. Zijn X1, X3, X4, G2 en de tests van X6 en K6 correct gebouwd? Geef per punt opgelost, deels of niet, met je eigen
   tegenproef (een concreet tekstvoorbeeld dat een verkeerde "ja" of een verkeerde regel geeft).
2. Een nieuwe fout van ernst hoog in de gewijzigde regels? Let vooral op een 60 Hz- of 220 V-"ja" die niet bewezen is.
3. Is de afwijking van X4 (prijs alleen uit titel of citaat) aanvaardbaar, of moet het anders?
4. Mag dit live als proef, waarna dezelfde MOVA-vraag een keer draait (ongeveer 2 dollar)? Een "nee" alleen met een
   concreet scenario.

Geef bovenaan: klaar, klaar met kanttekeningen, of niet klaar.

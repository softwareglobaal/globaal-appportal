**niet klaar**

**Voor Mehdi:** nog geen live proef. Een handleiding met “Robot: 220–240 V, 50/60 Hz. Basisstation: 230 V, 50 Hz” levert voor het basisstation toch een bewezen “ja” op. Met een bewezen winkelprijs kan dat aanbod zelfs als beste verschijnen.

| Punt | Oordeel | Tegenproef |
| --- | --- | --- |
| X1 | **Deels** | De code koppelt het citaat niet aan het onderdeel. Ook wordt `VX-200EU_US` als `VX-200EU` herkend. |
| X3 | **Deels** | Het budget en de tellers zijn ingebouwd, maar zes zoekopdrachten bij $1,96 aan modelkosten brengen de werkelijke kost op $2,02 zonder noodmelding. Het budget is adviserend; webzoeken kost $0,01 per opdracht. [Budget](https://platform.claude.com/docs/en/build-with-claude/task-budgets), [zoekkosten](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool). |
| X4 | **Deels** | “Shipping 19 euro” kan als productprijs van 19 euro in de aparte lijst komen. Een link zonder bewezen prijs blijft ook staan, tegen het [aangenomen besluit](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/docs/aankoop/rapport-9-verbeter.md:280). |
| G2 | **Opgelost als instelling** | De standaard is 10.000 tokens met de oude tools. Een prijs ná token 10.000 blijft uiteraard buiten beeld; het effect op de echte winkelpagina is niet bewezen. |
| X6 en K6 | **Deels** | De 172 tests zijn groen, maar missen de robotregel naast de basisstationregel en de regiocode met `_US`. |

**Voor Claude en Shaniel:**

1. **Hoog:** [aanbod.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:450) zoekt de modelcode ergens op de bewijspagina en accepteert daarna een citaat van een ander onderdeel of model. Koppel elke specificatieregel aan de exacte code én het basisstation; wijs tegenstrijdige regels af.
2. **Hoog:** [aanbod.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:384) laat `_US` door als regiovariant. Maak de codegrens strikt en voeg beide tegenproeven toe aan [test_aankoop_prijs.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/tests/test_aankoop_prijs.py:202).
3. **Middel:** [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:187) bewijst bij X4 alleen het getal, niet productprijs of munt. Een prijs uitsluitend uit titel of citaat is terecht voorzichtig: de samenvatting is versleuteld. [Anthropic bevestigt dit](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool). Laat prijsloze rijen volgens het besluit weg en controleer prijssoort en munt.

Gedaan: alleen gelezen; niets gewijzigd of gepusht.  
Nagekeken: diff, 172 groene tests en gerichte tegenproeven.  
Open: bewijsgrendel en prijsregels herstellen; daarna pas één MOVA-proef.
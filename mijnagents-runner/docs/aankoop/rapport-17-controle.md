# Niet klaar

**Voor Mehdi:** Uitrollen zonder token mag. De tokenproef en de MOVA-vraag moeten wachten tot Usage credits uitstaan: als je gedeelde limiet al bereikt is, kan de eerste modelaanvraag geld kosten.

**Voor Claude en Shaniel:**

1. **Punt 1 opgelost.** [voor_de_start()](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:282) controleert dezelfde token en omgeving en weigert Team, Enterprise en onbekende abonnementen vóór `claude -p`. Daarmee is het concrete scenario met [centrale Team- of Enterprise-instellingen](https://code.claude.com/docs/en/server-managed-settings) afgesloten.
2. **Hoog, punt 2 open.** In de [gemeten stream](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/tests/fixtures/claude_stream_proef.jsonl:7) verschijnen al modelantwoorden vóór `rate_limit_event`. Zowel `allowed` als 90 procent wordt pas bij dat event gecontroleerd in [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:347). Als de gedeelde limiet dan al op is, gaat de eerstvolgende aanvraag [via betaalde Usage credits](https://support.claude.com/en/articles/12429409-manage-usage-credits-for-paid-claude-plans). Zet die op accountniveau uit vóór de proef.
3. **Hoog, nieuwe fout in het proef-oordeel.** De [proef](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:545) kan ook “werkt” melden zonder enig `rate_limit_event`; de [test](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/tests/test_aankoop_prijs.py:617) verwacht dat zelfs. “Werkt” bewijst dus niet dat Usage credits uitstaan.
4. **Live:** zonder token ja. Na bevestiging dat Usage credits uitstaan, mogen de proef en bij “werkt” één MOVA-vraag draaien.

Gedaan: alleen gelezen; niets gewijzigd of gepusht.  
Nagekeken: diff en streamvolgorde; tegenproef zonder schijfschrijven.  
Open: Usage credits uitschakelen vóór de eerste modelaanvraag.
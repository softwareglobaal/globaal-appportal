# Overleg 19: bewijs van een persoonlijk abonnement voor de eerste modelvraag (01-11-2026)

Lees alleen; wijzig niets. Kort.

Mehdi's besluit: De Prijsonderzoeker mag geen geld kosten en werkt op zijn Claude-abonnement.

Codex-controle 18 (`mijnagents-runner/docs/aankoop/rapport-18-controle.md`): met een token uit `claude setup-token`
toont `claude auth status` geen `subscriptionType` (gemeten door de bouwsessie). Een token van een Enterprise-account met
betalen per gebruik zou dus door `voor_de_start()` komen, en de eerste modelvraag zou geld kosten. Codex wil betrouwbaar
bewijs van een persoonlijk abonnement voor elke modelvraag.

Gemeten en bekend:
- Mehdi heeft twee persoonlijke abonnementen (geen Team of Enterprise). `claude auth status` op de laptop met de gewone
  aanmelding geeft `subscriptionType: "max"`.
- Een setup-token heeft alleen de scope voor modelvragen: het profiel (abonnementstype) is ermee niet op te vragen
  zonder modelvraag. Er is geen andere bron zonder modelvraag die we kennen.
- De stream van een abonnement meldt `rate_limit_info.unifiedWindows` (`five_hour`, `seven_day`) en `overageStatus`.
- De agent stopt al bij `overageStatus: "allowed"`, bij `isUsingOverage` en boven 90 procent van een limiet.

Voorstel van Claude 1 (A): de abonnementsproef wordt de poort.
- `prijsonderzoeker.py --proef-abonnement` draait een keer, pas nadat Mehdi bevestigde dat Usage credits uitstaan.
  Het is een vraag aan haiku met het antwoord "ok".
- De proef slaagt alleen als de stream abonnementsvensters toont (`five_hour` of `seven_day`), `overageStatus` niet
  `allowed` is en `apiKeySource` `none` is.
- Slaagt de proef, dan schrijft ze een merkteken met de vingerafdruk van het token. Een prijsvraag start alleen als
  het merkteken bij het huidige token hoort; een nieuw token vraagt een nieuwe proef.
- In het slechtste geval kost dit een fractie van een cent, en alleen als het token van een Enterprise-account met
  betalen per gebruik komt. Dat account heeft Mehdi niet.

Alternatief (B): A, plus Mehdi bevestigt in de chat dat hij met zijn persoonlijke account aanmeldt, vastgelegd in de
werkstand.

Vragen:
1. A, B of een betere bron zonder modelvraag? Geef je keuze met een kort argument.
2. Is er hier een echte grens voor Mehdi?

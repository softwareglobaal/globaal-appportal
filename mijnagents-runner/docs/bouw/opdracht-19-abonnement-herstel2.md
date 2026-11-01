# Controle 19: herstel na controle 18 (Bouw op het Claude-abonnement)

Lees docs/bouw/rapport-18-abonnement-herstel.md (jouw vorige oordeel) en de nieuwste commit op tak bouw-abonnement
(git show HEAD). Wijzig niets.

Wat ik per punt deed:
1. Kosten: voor elke vraag draait `claude auth status` in precies de omgeving van de vraag (claude_abonnement.
   controleer_bron). Dat roept geen model aan. Gemeten 01-11-2026: met alleen het setup-token zegt het
   authMethod "oauth_token", apiProvider "firstParty" en geen apiKeySource; met ANTHROPIC_API_KEY zegt het "api_key" en
   apiKeySource "ANTHROPIC_API_KEY". Alleen het eerste mag; anders start de vraag niet (soort "bron", de vraag wacht).
   De init-controle blijft als tweede lijn. Een rate_limit_event met isUsingOverage, een status anders dan "allowed"
   (ook allowed_warning) of een venster boven 90 procent stopt het proces; de code onthoudt dat (LIMIET_BESTAND) tot het
   venster voorbij is (zonder eindtijd een uur) en start intussen geen vraag. Wat overblijft: de beurt waarin het
   abonnement voor het eerst extra verbruik meldt. Dat sluit alleen de eigenaar uit door extra verbruik in zijn account
   uit te zetten; dat zeg ik hem.
2. DNS: de opzoeking loopt in een draad met een tijdgrens (DNS_TIMEOUT, en nooit langer dan de rest van de tijd); de
   sockettijd is de echte rest, zonder minimum van een seconde.
5. Tijd: _dropbox_zoek start geen verzoek na de deadline, elk verzoek krijgt hoogstens de rest als timeout
   (bronnen._rpc kreeg een timeout-parameter), een timeout maakt de lijst onvolledig; in_mappen start geen nieuw
   zoekwoord na de deadline. zoek() start Claude niet met minder dan 60 s en gaat nooit voorbij de deadline (soort
   "tijd", de vraag wacht). MIN_SECONDEN_PER_VRAAG is 240.
6. Tests: de naam van de init-test zegt nu "stopt het proces meteen"; nieuwe tests voor auth status, het limietgeheugen,
   allowed_warning, 90 procent, te weinig tijd, trage DNS en Dropbox. 343 goed.
Nieuwe fout: Fout heeft nu een soort (aanmelden, limiet, bron, tijd); met een soort wacht de vraag en wordt ze niet als
opgepakt gemarkeerd (aannemerszoeker.py, e.wacht); de vergelijker meldt de juiste nood.

Gevraagd: is elk punt opgelost, met bestand:regel? Wat blijft over en is dat aanvaardbaar? Nieuwe fouten?
Antwoord in het Nederlands, kort. Eindig met precies een regel: AKKOORD of NIET AKKOORD.
Noem in je antwoord nooit de namen van de twee firma's samen en leg geen band tussen hen.

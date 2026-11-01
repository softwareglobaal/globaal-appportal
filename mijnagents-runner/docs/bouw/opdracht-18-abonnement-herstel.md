# Controle 18: herstel na controle 17 (Bouw op het Claude-abonnement)

Lees docs/bouw/rapport-17-abonnement.md (jouw vorige oordeel) en de nieuwste commit op tak bouw-abonnement
(git show HEAD). Wijzig niets.

Wat ik per punt deed:
1. Kosten: het kindproces krijgt een eigen lege HOME, CLAUDE_CONFIG_DIR en XDG_CONFIG_HOME (geen instellingen,
   apiKeyHelper of opgeslagen login van de server). De code leest de stroom regel per regel (claude_abonnement.draai,
   bewaking): meldt de init een apiKeySource anders dan "none", dan stopt ze het proces voor de eerste vraag; meldt een
   rate_limit_event isUsingOverage of een status anders dan allowed, dan stopt ze meteen en wacht de vraag (Fout.limiet,
   nood voor de eigenaar). Gemeten op het echte account: init geeft apiKeySource "none", rate_limit_event geeft
   overageStatus "allowed" en isUsingOverage false.
2. SSRF: webpagina.haal zoekt het IP een keer op, keurt het en verbindt met precies dat IP (eigen HTTP(S)Connection,
   certificaat op de naam), volgt omleidingen zelf met dezelfde keuring, en heeft een totale tijd per pagina.
3. Keuring: lees_sites geeft elke firma haar eigen pagina's (f["_paginas"]); deelt een host meerdere firma's, dan geen
   pagina's uit wat het model daar verder opende. keur() gebruikt per firma alleen die pagina's, telt de tekstgrens over
   al haar pagina's, en houdt bij een dubbel de best bewezen kandidaat.
4. Token: het aanmeldscript wist scherm en terugrolgeschiedenis na het lezen, zet .env op go-rwx, en de proef op de VM
   zet het token niet meer in een argument. Het token staat tijdens een ronde in de omgeving van het kindproces; dat is
   hoe Claude Code het leest, leesbaar voor dezelfde gebruiker zoals ~/appportal/.env zelf.
5. Tijd: harde grens op het aantal gereedschapsoproepen (2 x 17, daarboven stopt de code), --max-turns 25, de timeout
   volgt de deadline, en het Dropbox-zoeken stopt na een deadline (hoogstens 60 s).
6. Tests voor elk van deze punten (python3 mijnagents-runner/tests/test_bouw.py: 331 goed).

Gevraagd: is elk punt opgelost, met bestand:regel? Wat blijft over en is dat aanvaardbaar? Nieuwe fouten?
Antwoord in het Nederlands, kort. Eindig met precies een regel: AKKOORD of NIET AKKOORD.
Noem in je antwoord nooit de namen van de twee firma's samen en leg geen band tussen hen.

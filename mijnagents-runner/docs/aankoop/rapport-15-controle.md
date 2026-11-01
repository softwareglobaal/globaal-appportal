# Niet klaar

**Voor Mehdi:** de overstap naar je Claude-abonnement is nog geen garantie op nul extra kosten. Als **Usage credits** aanstaan en je inbegrepen gebruik op is, kan zelfs de korte abonnementsproef al betaald verbruik veroorzaken. **Nog niet live zetten en nog geen MOVA-proef draaien.** [Claude bevestigt dat Usage credits apart worden aangerekend.](https://support.claude.com/en/articles/12429409-manage-usage-credits-for-paid-claude-plans)

**Voor Claude en Shaniel:**

1. **Hoog, kosten:** [onderzoek.py:255](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:255) geeft Claude terecht geen API-sleutel uit de ouderomgeving. `--restricted` laadt echter nog beheerde instellingen. Die kunnen een `ANTHROPIC_AUTH_TOKEN` toevoegen dat vóór het abonnementstoken gaat; `apiKeySource: none` sluit een bearer-token niet uit. De grendel op `isUsingOverage` en de proef controleren pas **na** een aanvraag. Sluit beheerde betaalde routes uit en schakel Usage credits op accountniveau uit vóór de proef. [CLI-instellingen](https://code.claude.com/docs/en/cli-reference), [authenticatievolgorde](https://code.claude.com/docs/en/authentication), [betekenis van `apiKeySource`](https://code.claude.com/docs/en/agent-sdk/typescript).

2. **Hoog, intern netwerk:** [leesserver.py:41](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/leesserver.py:41) weigert directe adressen zoals `127.0.0.1:3022`, `0.0.0.0`, `::1` en privé-adressen, ook bij redirects. Maar `openbaar()` controleert DNS vóór `urllib` opnieuw verbinding maakt. Verandert DNS tussendoor van openbaar naar de Docker-bridge of een intern adres op poort 80/443, dan gaat het verzoek toch daarheen. Het bord op poort 3022 is zo niet rechtstreeks bereikbaar. Verbind uitsluitend met het vooraf gecontroleerde IP, opnieuw bij elke redirect.

3. **Hoog, X2:** één voltooide lezing gebruikt aan beide kanten dezelfde afgekorte paginatekst. [onderzoek.py:215](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:215) plakt twee lezingen van dezelfde URL echter aan elkaar en kent tekst na een redirect ook aan de oorspronkelijke URL toe. Daardoor kan `aanbod.py` bewijs accepteren dat op geen enkele afzonderlijk gelezen pagina stond. Bewaar lezingen afzonderlijk en koppel bewijs aan de werkelijke eind-URL.

4. **Procesgrens:** [onderzoek.py:332](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:332) schrijft blokkerend naar stdin vóór de deadlinecontrole. Bij een grote vraag en een kind dat niet leest kan de ronde onbeperkt wachten; bij een fout vóór `_stop_groep` blijft opruiming achterwege. De lezer-thread kan op een opengehouden stdout blijven wachten. Gebruik een tijdgebonden invoer en opruiming in `finally`.

5. **Live-oordeel:** **nee**, wegens de concrete kostenroute en DNS-wissel hierboven. De fout bij dubbele lezingen is daarnaast een nieuwe fout van ernst hoog.

Gedaan: commit f9deb6c en de gevraagde diff alleen lezend gecontroleerd; niets gewijzigd of gepusht.  
Nagekeken: beide tests gestart, maar deze leesomgeving weigert hun tijdelijke mappen; de gemelde groene aantallen kon ik niet bevestigen.  
Open: bovenstaande grendels herstellen en de tests opnieuw volledig draaien vóór token en MOVA-proef.
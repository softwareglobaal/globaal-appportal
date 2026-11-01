Niet akkoord: de broncontrole en wachtstatus zijn hersteld, maar de harde kosten- en tijdgrenzen niet volledig.

1. Kosten deels opgelost: voorcontrole klopt (`claude_abonnement.py:157,262`). Onbekende status `None` wordt echter toegelaten (`:120`) en een mislukte limietopslag wordt genegeerd (`:134-141`). Dan kan een volgende vraag starten. Eerste overage is alleen aanvaardbaar als extra gebruik uitstaat.
2. DNS deels opgelost: de draad heeft een grens (`webpagina.py:48-56`), maar bij minder dan 0,1 seconde wacht hij toch 0,1 seconde (`:92`). Dezelfde sockettimeout wordt bovendien hergebruikt voor meerdere stappen (`:98-112`), dus de totaaltijd is niet hard.
3. Keuring blijft opgelost (`zoeken.py:407-427`).
4. Tokenoverdracht blijft opgelost (`abonnement_aanmelden.command:11-42`).
5. Tijd niet volledig opgelost: Dropbox gebruikt een sockettimeout, geen absolute eindtijd tijdens `json.load` (`bronnen.py:105-106`). Een langzaam druppelend antwoord kan de deadline overschrijden.
6. De nieuwe tests dekken de hoofdgevallen, maar niet bovenstaande trage meervoudige socketstappen (`test_bouw.py:910-912,1096-1101`). De 343 tests kon ik door de alleen-lezen omgeving niet volledig herhalen.
7. De nieuwe foutsoorten werken: de vraag blijft staan vóór `opgepakt` (`aannemerszoeker.py:238-251`) en de vergelijker meldt de juiste nood (`offertevergelijker.py:150-156`).

NIET AKKOORD
# Niet klaar

**Voor Mehdi:** De uitrol zonder token kan: mijn tegenproef startte geen Claude-proces, en de agent meldt dan een nood. Wacht met het token, de automatische abonnementsproef en MOVA. Er blijft een concrete betaalde route als het token bij een Team- of Enterprise-account met centrale API-instellingen hoort.

**Voor Claude en Shaniel:**

1. **Hoog, kosten deels opgelost.** Een nagebootst gebruik van 93 procent stopt de vraag; `isUsingOverage` stopt haar ook. Maar [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:245) controleert alleen bestanden op de VM. Claude Code kan met een `setup-token` ook [centrale instellingen ophalen](https://code.claude.com/docs/en/server-managed-settings). Scenario: die instellingen zetten `ANTHROPIC_AUTH_TOKEN`. Dat [gaat vóór het abonnementstoken](https://code.claude.com/docs/en/authentication); de eerste aanvraag kan dan al betaald zijn voordat de streamcontrole ingrijpt. Controleer die centrale bron vóór activering.
2. **Kostenroute:** de allereerste aanvraag is niet de enige mogelijkheid. Ook tussen latere modelaanvragen kan Mehdi’s gedeelde gebruik de limiet bereiken. Met Usage credits aan wordt de volgende aanvraag betaald; [Usage credits uit](https://support.claude.com/en/articles/12429409-manage-usage-credits-for-paid-claude-plans) sluit deze *accountkostenroute* af, maar niet de centrale API-route.
3. **DNS opgelost.** Bij mijn nagebootste wissel van openbaar DNS naar `127.0.0.1` maakte [leesserver.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/leesserver.py:65) geen verbinding.
4. **Bewijs en procesgrens opgelost.** Een redirect telde alleen onder de eind-URL; twee lezingen werden niet samengeplakt. Een nagebootst kind dat twee miljoen tekens invoer niet las, bereikte de deadline en werd opgeruimd; een eindregel stopte direct. Zie [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:220) en [onderzoek.py](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:365).

Gedaan: diff en code alleen lezend gecontroleerd; niets gewijzigd of gepusht.  
Nagekeken: eigen proeven zonder schijfschrijven; de 225 gemelde tests kon ik in deze leesomgeving niet herhalen omdat ze tijdelijke mappen nodig hebben.  
Open: centrale instellingen uitsluiten vóór tokenproef en MOVA.
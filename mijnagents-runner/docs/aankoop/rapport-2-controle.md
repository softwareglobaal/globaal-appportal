**Niet klaar.** Een aanbeveling kan op een lege bron of onbewezen compatibiliteit steunen. Bovendien kan de Regisseur het klaargezette prijsverslag niet als antwoord in de chat lezen. De privacygrens en de tijdsgrens zijn evenmin sluitend.

### Voor Mehdi

Een ontbrekend opgeld, ontbrekende veilingkosten of ontbrekende invoer blokkeren de beste keuze en reserve zoals bedoeld. De overige punten hieronder moeten worden hersteld voordat de agent betrouwbaar antwoord geeft.

### Voor Claude en Shaniel

**X1 — hoog — [onderzoek.py:86](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:86), [prijsonderzoeker.py:86](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py:86).** Een `web_fetch_result` zonder paginatekst telt als gelezen. Prijs, opgeld en invoer worden niet tegen de pagina gecontroleerd; de code stempelt ze toch als vandaag gezien. Eis leesbare inhoud en bronbewijs per bedrag; test een lege en een afwijkende pagina.

**X2 — hoog — [aanbod.py:149](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:149), [verslag.py:74](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/verslag.py:74).** Het model bepaalt zowel de eisen als het oordeel daarover. Met `eisen=[]` werd een 50 Hz toestel aanbevolen voor een vraag over 60 Hz; vrije adviestekst kon een afgewezen toestel alsnog aanraden. Valideer eisen en advies buiten het model.

**X3 — hoog — [privacy.py:9](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/privacy.py:9), [prijsonderzoeker.py:93](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py:93).** Namen zoals „Jan Peeters” en niet-herkende adressen passeren het filter. De onbewerkte vraag gaat dan naar de AI en het logboek; bij een fout wordt ze ook gelogd op regel 129. Scherm de vraag af vóór verzending en opslag.

**X4 — hoog — [onderzoek.py:134](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:134).** Ook bij een schone productvraag stuurt de systeemtekst Mehdi’s volledige naam, de werkwijze, collega’s en lessen mee. Beperk de externe opdracht tot toegestane productgegevens.

**X5 — hoog — [regisseur.py:120](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/regisseur.py:120), [app.py:548](/Users/mehdichegini/dev/_aankoopagents/mijnagents/app.py:548).** `prijsverslag` ontbreekt bij de leesbare soorten van de Regisseur en bij de gewone bordweergave. Alleen een platte kopie staat in het werkverslagdetail. Maak het item leesbaar en klikbaar; test de route tot in de chat.

**X6 — hoog — [prijsonderzoeker.py:124](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py:124), [regisseur.py:491](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/regisseur.py:491).** Twee vragen mogen elk 420 seconden duren. Omdat deze runner geen slot heeft, geldt de 540 seconden-wrapper niet; de Regisseur wacht maximaal 600 seconden. Dwing één deadline voor de hele ronde af.

**X7 — middel — [onderzoek.py:155](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:155).** De zoek- en leeslimieten worden bij iedere hervatting opnieuw meegegeven; [Anthropic definieert `max_uses` per verzoek](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool). Het tokenplafond wordt pas ná een volledige API-beurt getoetst. Bewaak resterende ruimte over alle beurten.

**X8 — middel — [onderzoek.py:181](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:181).** Na twee pauzes verdwijnt de eerste gepauzeerde beurt uit `messages`; mijn proef gaf berichtenaantallen 1, 2, 2. Bewaar de hele uitwisseling, conform [Anthropics hervattingsregel](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools), en test twee pauzes.

**X9 — middel — [aanbod.py:98](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:98), [verslag.py:64](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/verslag.py:64).** Het totaal telt geen btw bij een prijs exclusief btw, maar het verslag noemt die wel „alles inbegrepen”. Leg vast of btw in de bronprijs zit en bereken ontbrekende belasting.

Gedaan: alleen gelezen en tegenproeven zonder bestanden te wijzigen.  
Nagekeken: prijstests **71 goed, 0 fout**; De Bode filtert `prijsverslag` terecht weg; N10-noodteksten bevatten geen teller.  
Open: herstel met regressietests en meet N1–N14 op het bord na de eerste echte ronde; die live uitslag kon ik in deze leescontrole niet vaststellen.
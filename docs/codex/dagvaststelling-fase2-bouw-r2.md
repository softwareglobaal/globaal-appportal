**Niet klaar.** De bouw levert het gevraagde WhatsApp-overzicht zonder namen en toont bij ontbrekende dekking “onbekend”. Er blijven fouten die oproepen stil kunnen laten verdwijnen, plus risico’s in de helper en de uitrol.

## Voor Claude en Shaniel

P1, P2, P4, P5 en P7 hebben code en gerichte tests. De chatcorrectie van P3 is aanwezig, maar Q8 blijft. P6, P8 en P9 zijn niet volledig opgelost.

1. **Q1, hoog, P6.** [mac_gesprekken.py:339](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:339): twee iPhone-oproepen met dezelfde ID krijgen dezelfde sleutel. Een proef gaf twee rijen met één unieke sleutel; de API overschrijft er één. Detecteer botsingen en test dit via de echte API.

2. **Q2, hoog, P9.** [mac_gesprekken.py:586](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:586): bij precies vijf bestaande rijen en een tijdelijk lege bron markeert de runner alle vijf als vervallen. Dat is in een geheugenproef bevestigd. Stop vanaf vijf verdwenen rijen als dat meer dan een vijfde van de bordrijen is; test de grens.

3. **Q3, middel.** [macgesprekken_kopie.c:110](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/kopie/macgesprekken_kopie.c:110): na de symlinkcontrole openen `open` en SQLite het bronpad opnieuw. Een tussentijdse padwissel kan de helper een andere databank laten lezen. Bind de SQLite-lezing aan de gecontroleerde bron; voeg een racetest toe.

4. **Q4, middel, P9.** [macgesprekken_kopie.c:296](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/kopie/macgesprekken_kopie.c:296): uitvoer en status gebruiken vaste namen zonder gezamenlijke generatie. Twee starts kunnen status A bij kopie B opleveren. Gebruik een unieke generatie of inhoudshash en test gelijktijdige starts.

5. **Q5, middel.** [mac_gesprekken.py:102](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:102): een misvormd tijdveld kan zijn tekst in de foutmelding laten belanden voordat privénamen zijn gemaskeerd; [bord.py:394](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/bord.py:394) zet die fout in de hartslag. Meld daar alleen een vaste foutsoort en test een misvormde waarde.

6. **Q6, middel, P8.** [whatsapp_wacht.py:102](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/whatsapp_wacht.py:102) en [belwacht.py:105](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/belwacht.py:105): na mislukte eindcontrole wordt de fouthartslag niet bevestigd en ontbreekt de beloofde nood. Verifieer de foutstatus en meld een vaste nood.

7. **Q7, hoog.** [uitrol_mac_gesprekken.sh:70](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/uitrol_mac_gesprekken.sh:70): de uitrol vervangt een actieve helper en herlaadt wachten voordat de nieuwe schijftoegang en eerste ronde zijn bewezen. Bewaar binary en plists voor terugrol; laat `aan` pas toe na die controle.

8. **Q8, middel, bestaand maar niet afgedekt door P3.** [app.py:1638](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents/app.py:1638): de dagpagina’s tellen mailrijen als gesprekken. Filter op gespreksbronnen en voeg mail toe aan de P3-test.

De helper voert volgens de gelezen SQL geen berichttekst uit; ik vond geen URI-injectie. N1 tot N14 zijn alleen deels statisch te beoordelen. Vooral N3, N6 en N7 vragen bordgegevens; N4 en N11 vragen een geslaagde live ronde.

Gedaan: HEAD `01a67e6` alleen gelezen; latere werkmapwijzigingen in beide runners vallen buiten dit oordeel.  
Nagekeken: twee geheugenproeven; Mac-test 12 geslaagd en 11 geblokkeerd door de alleen-lezen-sandbox, API-test geblokkeerd vóór de start.  
Open: Q1 tot Q8 en een gecontroleerde ronde onder launchd.

live: nee
**Niet klaar.** Ontwerp 1.1 beantwoordt D3 en D4 voldoende voor de latere Mac fase. Voor fase 1 blijven er risico’s op een onvolledig overzicht en op afspraken die ten onrechte als bevestigd verschijnen.

| Punt | Oordeel | Reden |
|---|---|---|
| D1 | Open | De voorgestelde taakcontrole ontbreekt in de huidige vrijgave; die accepteert ook een fouthartslag. [ochtend.py:131](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/koppelingen/ochtend.py:131), [regisseur.py:1512](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/regisseur.py:1512) |
| D2 | Open | Uitsluiten en de gedeelde ronde zijn beschreven. Rijen op één dag bewijzen echter niet dat WhatsApp of telefoon is aangesloten; de oude noden noemen nog exports en Xelion. [dagbundelaar.py:188](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/dagbundelaar.py:188) |
| D3 | Gesloten | Het gewijzigde bronmandaat staat terecht vóór de bouw van fase 2. |
| D4 | Gesloten | Eigen runners, gedeelde ronde, tunnel en teruglezing zijn voor fase 2 voldoende ontworpen. |
| D5 | Open | De privéregel is verbeterd, maar toegang tot de Dropbox-map met namen is niet vastgesteld. [ontwerp:86](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:86) |
| D6 | Open | Zie E2 en E3. |
| D7 | Open | Zie E1; ook Plaud krijgt nog geen koppeling met een eventuele tweede opname. |
| D8 | Open | Verzonden post is beter afgedekt; de volledigheid van ontvangen post ontbreekt. Zie E4. |
| D9 | Open | Versies zijn voorzien, maar teruglezen bewijst nog niet dat bord en bestand dezelfde versie tonen. Zie E6. |
| D10 | Open | Het voorgestelde watermerk mist wijzigingen. Zie E5. |

**Nieuwe bevindingen voor de bouw**

1. **E1, hoog.** Waar: [ontwerp:58](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:58), [postvak.py:549](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/koppelingen/postvak.py:549). Mail staat ook in `gesprek_log` en kan als gesprek meetellen. **Voorstel:** filter op gespreksbronnen en toets dubbels met Plaud.
2. **E2, hoog.** Waar: [ontwerp:54](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:54), [agenda_wacht.py:5569](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/agenda_wacht.py:5569). `afspraken_dag` mist archiefagenda’s die de Agendawacht apart leest. **Voorstel:** lees die mee en behandel `ARCHIEF_FOUT` als onvolledig.
3. **E3, hoog.** Waar: [ontwerp:73](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:73), [ontwerp:81](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:81), [zoom_wacht.py:1200](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/zoom_wacht.py:1200). Een naamdeel zoals “Mehdi” kan een afspraak vals bevestigen; een ongerelateerde oproep met tijdsoverlap verdwijnt uit “Niet gepland”. **Voorstel:** koppel op een andere, aantoonbaar gedeelde persoon en gebruik dezelfde koppeling voor beide rubrieken.
4. **E4, hoog.** Waar: [postvak.py:501](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/koppelingen/postvak.py:501), [app.py:845](/Users/mehdichegini/dev/_dagvaststeller/mijnagents/app.py:845). De tabel bewaart geen leesdekking per inkomende map. Oude rijen kunnen dus een volledige dag suggereren na een leesfout. **Voorstel:** bewaar dekking en leestijd per postvak en map.
5. **E5, hoog.** Waar: [ontwerp:107](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:107), [app.py:610](/Users/mehdichegini/dev/_dagvaststeller/mijnagents/app.py:610), [app.py:1004](/Users/mehdichegini/dev/_dagvaststeller/mijnagents/app.py:1004). Bij updates veranderen de gebruikte tijdstempels niet; agendawijzigingen ontbreken geheel. **Voorstel:** vergelijk bronversies, waaronder locatie `/api/revisies`, en herlees gewijzigde agendadagen.
6. **E6, middel.** Waar: [ontwerp:93](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:93), [ontwerp:98](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:98). Een aanmaaktijd in de hash kan elke ronde een nieuwe versie geven; aanwezigheid alleen bewijst geen gelijke versie. **Voorstel:** hash de vaste inhoud en vergelijk die hash bij bestand, borditem en ontvangstbewijs.

Gedaan: ontwerp en code alleen gelezen; niets gewijzigd.  
Nagekeken: D1 tot D10 tegen de broncode; geen tests uitgevoerd.  
Open: de punten hierboven verwerken en daarna de fase 1 grendels toetsen.

**Fase 1 bouwen: nee.**
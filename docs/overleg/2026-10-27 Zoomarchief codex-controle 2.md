**Voor Mehdi — niet klaar.** De kopiecontrole kan alsnog `dekking: ja` melden nadat een opname uit zowel Zoom als Dropbox verdwenen is. Ook staat voorstel 40 nog open met de oude instructie om de wisregel aan te zetten. Dat voorstel moet vervallen voordat het als besluitweg veilig is.

**Voor Claude en Shaniel**

Hercontrole punten 1–10: **1 ja, 2 ja, 3 deels, 4 nee, 5 deels, 6 deels, 7 deels, 8 ja, 9 ja, 10 ja.** De korte download zonder Zoom-grootte wordt geweigerd; per bestand bewaarde noden en vroege stops zijn hersteld. Bij `Verschoven` kan een fout samengestelde upload niet als bewezen tellen zolang de vergelijking van grootte én `content_hash` met het lokale bestand geldt.

11. **Blokkerend — `zoom_archief.py:292`, `zoom_archief.py:539`.** Geheugenproef: verdwijnt een bewezen bestand uit Dropbox én Zoom, dan verwijdert de eerste volledige ronde het bewijs; de volgende zet zonder bestand of besluit `dekking: ja`. Bewaar het verlies als open geval tot herkopie of Mehdi’s besluit. Een korte ronde controleert eerdere bewijzen evenmin, maar vernieuwt wel `dekking: ja`; controleer ze vóór die bevestiging.

12. **Hoog — `zoom_account.py:864`.** Het open voorstel 40 behoudt de oude wisinstructie en blokkeert ook na dekking `ja` een nieuw voorstel. Laat oude open ZA-01-voorstellen zonder `kopie: ja` vervallen en toets dekking bij de besluitknop.

13. **Hoog — `zoom_archief.py:517`, `bord.py:197`.** `hartslag` slikt een bordfout in; de staat markeert het gemist-voorstel toch als verstuurd. Lees het voorstel terug vóór die markering, anders opnieuw proberen. `parameters=None`, een leeg runbook en het teruglezen van `goedgekeurd`, `uitgevoerd` en `overgeslagen` zijn verder passend.

14. **Hoog — `zoom_archief.py:318`.** Twee proef-id’s kregen dezelfde acht tekens; één goedkeuring markeerde beide opnames als gemist. Gebruik een langere unieke sleutel en weiger botsingen.

15. **Hoog — `zoom.py:529`.** Een meeting zonder `recording_files` wordt een lege, geslaagde inventaris. Weiger die onvolledige meeting.

16. **Hoog — `zoom_archief.py:218`.** De eerste ronde accepteert ook een vreemd account met een map `/Fathom data`. Pin een onafhankelijk geverifieerd account-id.

17. **Middel — `zoom_archief.py:292`, `zoom_archief.py:531`.** Metadata- en opname.json-werk mist de tijdsbewaker; een oud bestand zonder id verliest in een korte ronde zijn nood. Begrens die netwerkstappen en bewaar de afwijking in de staat.

Gedaan: diff en herstelpunten gecontroleerd; niets gewijzigd.  
Nagekeken: geheugenproeven bevestigden de genoemde gevallen; naamgrendel 3/3, agentnorm 28/28 (Markdown-toets overgeslagen).  
Open: vier Zoom-suites stopten vóór de tests: deze alleen-lezen omgeving weigerde ook `.tmp`. Herstel de bevindingen en draai ze in een schrijfbare omgeving.

**BESLISSING: niet klaar.**
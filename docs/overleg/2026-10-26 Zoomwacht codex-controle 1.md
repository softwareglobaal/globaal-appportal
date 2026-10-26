**Voor Mehdi — niet klaar.** X3 en de werkwijze zijn in orde. X1 laat nog privékanalen als werk verschijnen; X5 noemt ook onzekere Fathom-gevallen alsof Fathom ontbreekt.

- **X1 — fout, hoog.** Een kanaal met “automation” of “prive” kan nog als werk worden opgeslagen. De chattelling en afdelingsbundel breken niet, maar oude rijen buiten het venster blijven als werk zichtbaar. Ook rijen binnen het venster blijven zo wanneer Zoom het gesprek niet opnieuw laat lezen.
- **X2 — fout, laag.** Met de huidige bordroute stopt het bladeren correct. Geeft het bord toch telkens dezelfde volle pagina terug, dan blijft deze lus lopen tot de ronde wordt afgebroken.
- **X3 — in orde.** De leeftijd wordt gemeten op de eindgrens van `tot_dag`; precies twee en zeven dagen vallen in “2 tot 7 dagen”.
- **X5 — fout, middel.** Geen herziening voor dit extra veld klopt. Het ochtendbericht toont het veld correct zoals aangeleverd, maar “zonder Fathom” omvat nu ook gesprekken waarvan Fathom al via de API bekend is of nog onbekend is.
- **X6 / werkwijze — in orde.** Versie 2.4 heeft de vereiste N1/N2-koppen en geen gedachte- of halve gedachtestreepjes.

**Voor Claude en Shaniel**

1. **Hoog — X1:** [zoom_wacht.py:562](mijnagents-runner/zoom_wacht.py:562) houdt de `automation`-uitzondering; `prive` staat bovendien in de afdelingenlijst. Herken alleen echte werkafdelingen en maskeer de overige kanaalnamen. Corrigeer bestaande kanaalrijen zonder ze te verwijderen: een 404 slaat herschrijven over ([zoom_wacht.py:532](mijnagents-runner/zoom_wacht.py:532)). Het dagoverzicht neemt zelfs bij `prive=1` de naam over ([app.py:1632](mijnagents/app.py:1632)); filter privénamen daar.
2. **Laag — X2:** [zoom_wacht.py:1285](mijnagents-runner/zoom_wacht.py:1285): controleer na een volle pagina dat het laagste id echt daalt; meld een onvolledige lezing als dat niet gebeurt.
3. **Middel — X5:** [zoom_wacht.py:1358](mijnagents-runner/zoom_wacht.py:1358) telt elke toestand behalve `fathom`, ook `api` en `onbekend`. Tel die afzonderlijk. [ruimte_van:286](mijnagents-runner/zoom_wacht.py:286) noemt een ontbrekende `host_id` ten onrechte “eigen meeting”; voeg “ruimte onbekend” toe aan de telling en [ochtend.py:229](mijnagents-runner/koppelingen/ochtend.py:229).

Gedaan: diff en verbruikers alleen-lezen gecontroleerd; niets gewijzigd.  
Nagekeken: de opgegeven groene suites als gegeven genomen; tests niet opnieuw gedraaid.  
Open: X1 en X5 herstellen, plus de voortgangsrem voor X2.
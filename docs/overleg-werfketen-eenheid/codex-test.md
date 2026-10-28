NIET AKKOORD

**Voor Mehdi:** Een oud werfbezoek kan nu doorstromen, maar de keten kan ook een bezoek ten onrechte “klaar voor verslag” noemen. Daarnaast blijft een dossier in de prullenbak onbruikbaar terwijl de voorbereider meldt dat het bestaat.

**Voor Claude en Shaniel:**

1. **Hoog — [werfverslag_voorbereider.py:662](/Users/user2025/dev/globaal-appportal/mijnagents-runner/werfverslag_voorbereider.py:662):** “Geen dossier gevonden” zet `voor_contractsysteem` aan zonder bewijs dat het project van vóór dat systeem is. Ook een nieuwer project zonder contract kan daardoor klaar lijken. **Kleinste fix:** zet de vlag alleen met onafhankelijk, gedateerd bewijs van die ouderdom; test ook een nieuw project zonder dossier.

2. **Hoog — [werfverslag_voorbereider.py:990](/Users/user2025/dev/globaal-appportal/mijnagents-runner/werfverslag_voorbereider.py:990):** Elke 409 telt als “bestaat”, ook de [409 voor een dossier in de prullenbak](/Users/user2025/dev/globaal-werfverslag/app/api.py:273). W8 blijft dan onbekend, maar [de klaarstatus vereist W8 niet](/Users/user2025/dev/globaal-appportal/mijnagents-runner/werfverslag_voorbereider.py:927). **Kleinste fix:** herken de prullenbakmelding, meld herstel als nood en laat dit dossier niet “klaar voor verslag” worden.

3. **Middel — [api.py:263](/Users/user2025/dev/globaal-werfverslag/app/api.py:263):** `alleen_ha` kan bij een bronstoring een project uit de oude buffer openen. Het maakt via deze vlag geen vrij project. Bij een gelijktijdige aanmaak kan de [UPDATE op regel 285](/Users/user2025/dev/globaal-werfverslag/app/api.py:285) wel velden van het inmiddels bestaande dossier overschrijven. **Kleinste fix:** eis bronstatus `ok` vóór aanmaak en voer die UPDATE alleen uit als `werfdossier()` meldt dat de rij nieuw is.

4. **Middel — [werfverslag_dashboard.py:71](/Users/user2025/dev/globaal-werfverslag/runner/werfverslag_dashboard.py:71):** De eerste `TimeoutError` krijgt één herkansing. Een tweede time-out veroorzaakt nog een traceback; `URLError` krijgt geen herkansing. **Kleinste fix:** vang de fout na de herkansing af, meld één fout met reden en voeg een time-outtest toe.

5. **Laag — [werfverslag-dashboard.md:52](/Users/user2025/dev/globaal-appportal/mijnagents-runner/werkwijze/werfverslag-dashboard.md:52):** De lessenregel zegt nog dat de auto `let_op` geeft, terwijl de actuele W2-regel aanwezigheid bevestigt. **Kleinste fix:** werk de lessenregel bij.

Gedaan: beide commits en hun diffs alleen lezend gecontroleerd.  
Nagekeken: voorbereider-tests **10 geslaagd**; WERFSTART en de fallback na openen van het werfdossier werken in die tests.  
Openstaand: werfapp-tests konden in deze leesomgeving niet draaien; ze vereisen een tijdelijke SQLite-database.
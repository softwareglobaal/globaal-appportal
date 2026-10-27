## Voor Mehdi

**Niet klaar.** Grote opnames lopen vast voordat Dropbox de kopie afrondt. Het bord kan bovendien “dekking: ja” tonen terwijl bestanden ontbreken, en een ouder advies om de wisregel aan te zetten blijft zichtbaar. Herstel deze punten vóór de proefronde.

## Voor Claude en Shaniel

De K1-afwijking klopt: voor een nieuwe agent zet `nieuwe-agent.py` de werkwijze zelf; Zoomwacht 2.5 gaat als voorstel (`AGENTNORM.md:366`).

1. **Blokkerend — `dropbox_prive.py:103`.** Dropbox geeft bij een geslaagde `append_v2` een lege body; `json.load` faalt daardoor voor bestanden boven 64 MiB, dus ook voor 687 MB. Accepteer die lege succesbody en test de HTTP-laag. [Dropbox-documentatie](https://docs.dropboxapi.com/dropbox-api/api-reference/user-endpoints/files/upload-session-append-v-2).
2. **Blokkerend — `zoom.py:506`.** De prullenbakvraag gebruikt datumfilters die Zoom daar niet ondersteunt en leest alleen `meeting_recordings`. Los gewiste bestanden ontbreken. Lees beide `trash_type`-soorten eenmaal zonder datums. [Zoom-documentatie](https://developers.zoom.us/docs/api/meetings/).
3. **Blokkerend — `zoom.py:515`.** CC- en TIMELINE-bestanden hebben volgens Zoom geen id, status of grootte en worden stil overgeslagen. Ook een antwoord zonder `meetings` wordt leeg (`zoom.py:366`). Gebruik een stabiele interne sleutel en weiger onvolledige lijsten. [Zoom-documentatie](https://developers.zoom.us/docs/api/meetings/).
4. **Blokkerend — `zoom_archief.py:319`.** Verwijder een eerder bewezen Dropbox-bestand: mijn geheugenproef kreeg alsnog `dekking: ja`, zonder nieuwe metadata-aanroep. Hercontroleer bestaande bewijzen vóór volledige dekking.
5. **Blokkerend — `zoom_account.py:691`, `zoom_account.py:864`.** Bij dekking “nee” blijft ZA-01 open; dezelfde stand houdt een bestaand voorstel met de oude wisinstructie intact. Mijn proef maakte nul nieuwe voorstellen. Blokkeer en actualiseer bestaande ZA-01-voorstellen.
6. **Hoog — `dropbox_prive.py:72`.** Aanwezige sleutels bewijzen niet dat het Mehdi’s account is. Een verkeerd gekoppeld token geeft geldige hashes op de verkeerde bestemming. Controleer het vaste Dropbox-account-id vóór schrijven.
7. **Hoog — `zoom_archief.py:336`.** Budget en ketencontrole gebeuren alleen tussen bestanden; een trage inventaris of upload kan de keten overlappen. Dwing de deadline ook tijdens die stappen af.
8. **Middel — `zoom_archief.py:320`.** Een teruggekeerd en gekopieerd bestand blijft “verdwenen”; nood en dekking herstellen niet. Wis die vlag na bewijs. `noden_onbekend=True` bewaart noden bij ketenpauze, maar een eerdere tokenafslag of budgetstop doet dat niet.
9. **Middel — `zoom.py:276`.** Een ongevalideerde Zoom-scope komt in de noodtekst; mijn proef zette zo een URL op het bord. Valideer scopes en gebruik anders een algemene tekst.
10. **Middel — `zoom_archief.py:203`.** Na een verloren `finish`-antwoord wordt Dropbox pas de volgende ronde opnieuw gelezen. Een 409-offsetfout, verlopen sessie of 401 zet veilig geen staat. Lees metadata direct na een onduidelijke `finish` en toets deze foutgevallen.

Gedaan: diff gelezen, niets gewijzigd, gerichte breekproeven uitgevoerd.  
Nagekeken: L1/L5, `mode add`, UTC-berekening en werkwijzevorm ogen correct. Namen: 3 goed; agentnorm: 28 goed, Markdown-toets overgeslagen. De drie Zoom-suites stopten op de alleen-lezen tempmap; account: 62 goed, 1 dezelfde sandboxfout.  
Open: de branch rust op `b8b02b2`, terwijl `origin/main` op `2a45ec0` staat. Integreer main, herstel de bevindingen en draai alle zes tests opnieuw in een schrijfbare testomgeving.

**BESLISSING: niet klaar.**
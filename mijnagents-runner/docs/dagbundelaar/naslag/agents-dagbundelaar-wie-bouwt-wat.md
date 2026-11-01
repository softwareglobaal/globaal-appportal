# Agents van de Dagbundelaar: wie bouwt wat

In drie hoeken overleggen.

Stand 31-10-2026, 22:15. Alle 24 plekken staan in één groep "Dagbundelaar" op het bord (mijnagents.globaal.be, pagina Organogram).
De naam op het bord staat op één plek in de code (DAGBUNDELAAR_AGENTS in mijnagents/app.py). Regel: De <kanaal>wacht.
Een wacht die nog niet bestaat, staat als lege plek "nog te bouwen". Zodra hij zich registreert, vult de plek zich.
Claude 2 = bouwt code en server. Claude 1 = voert uit op de laptop van Mehdi. Elke rij met een volgende stap kan een eigen chat worden.
Werkwijze: eerst een slimme agent; een stap die drie weken stabiel is, wordt een gewoon programma.

| Naam op het bord | Code-naam | Waar | Stand | Wie | Volgende stap |
|---|---|---|---|---|---|
| De Dagbundelaar, onder Ai Angel | dagbundelaar | server | werkt | Claude 2 | samenvatting en actiepunten van gesprekken toevoegen |
| Ai Angel (was De Mehdi-agent), bovenaan | mehdi-agent | server | live sinds 31-10, takenlijst op mijnagents.globaal.be/agent/mehdi-agent | Claude 2 | taken echt doorgeven aan bestaande agents, niets dubbel (taak "Bouw Mehdi-agent") |
| De Agendawacht | agenda-wacht | server | werkt, 12 meldingen | Claude 2 | meldingen over titels en adressen wegwerken |
| De Calendlywacht | calendly-wacht | server | werkt | Claude 2 | niets |
| De Locatiewacht | locatie-wacht | server | werkt | Claude 2 | niets |
| De Fotowacht (was iCloud-wacht) | icloud-wacht | laptop | fout | Claude 1 | op de laptop nakijken waarom ze faalt (laptopdocument, stap 4) |
| De Gezondheidswacht | gezondheid-wacht | laptop | draait, vindt nog niets | Mehdi, dan Claude 1 | Mehdi zet Health Auto Export aan op de iPhone; Claude 1 kijkt de map na (document wispr-websites-gezondheid, stap 7) |
| De Belwacht iPhone (was Belwacht) | belwacht | laptop | werkt | Claude 1 | niets |
| De Belwacht Xelion | xelion-wacht | server | nog te bouwen | Claude 2 | oproepen van het privénummer uit Xelion lezen (wie, wanneer, hoe lang) |
| De Sms-wacht | sms-wacht | laptop | nog te bouwen | Claude 2 bouwt, Claude 1 zet aan | teller voor sms en iMessage uit Messages op de laptop |
| De WhatsApp-wacht | whatsapp-wacht | laptop | werkt | Claude 1 | niets |
| De Communicatiebundelaar | communicatie-bundelaar | server | werkt | Claude 2 | niets |
| De Fathomwacht | fathom-wacht | server | werkt | Claude 2 | niets |
| De Plaudwacht | plaud-wacht | server + claude.ai | werkt deels | Claude 1 | Plaud-routine op claude.ai laten draaien |
| De Zoomwacht | zoom-wacht | server | werkt | Claude 2 | niets |
| De Zoomarchivaris | zoom-archief | server | werkt | Claude 2 | niets |
| De Wispr-wacht | wispr-wacht | laptop | werkt | Claude 1 | niets |
| De Websitewacht (was Browserwacht) | browser-wacht | laptop | gebouwd, nog niet aan | Claude 1 | aanzetten op de laptop (document wispr-websites-gezondheid, stap 1 tot 5); leest Chrome, dus ook het Chrome-account |
| De YouTube-wacht | youtube-wacht | server | nog te bouwen | Claude 2 | kijkgeschiedenis van het YouTube-account van Mehdi: welke video, wanneer, hoe lang |
| 5 Mailwachten (mch@, info@ H-Architects, info@ H-Invest, Melodie, hotmail) | mail-* | server | werkt | Claude 2 | niets |

Geen aparte Chromewacht: De Websitewacht leest Chrome al. Zo staat niets dubbel.

# Opdracht driehoeksoverleg: Ai Angel (de Mehdi-agent) nakijken

In drie hoeken overleggen. Claude, Codex en Gemini: lees alleen, stem per punt (eens / oneens / onthouding) en zeg bij
oneens wat er moet veranderen, met bestand en regel.

## Context

- Mehdi, 31-10-2026: boven De Dagbundelaar komt een aparte agent die zijn taken en to-do's klaarzet, ze doet waar het
  kan, leert ze naar de juiste persoon of agent te sturen, en hem leert zijn dagen en werk beter te organiseren, tot zes
  keer per dag. Keuze van Mehdi dezelfde dag: de agent leest alleen de dagbundel en gaat alleen via de verwijzing in de
  bundel naar de bron.
- Gebouwd en getest: `mijnagents-runner/mehdi_agent.py`, werkwijze `werkwijze/mehdi-agent.md`, ontwerp
  `docs/ontwerp-mehdi-agent.md`, tests `tests/test_mehdi_agent.py`, planning `planning/mehdi-agent.cron`. Live sinds
  31-10-2026 op Mehdi's ja ("alles nu live"), voor dit overleg: dit overleg kijkt dus achteraf na, en een punt van
  ernst hoog of middel wordt meteen hersteld.
- Droog geprobeerd op de VM op 31-10-2026 met de echte dagbestanden van 29 en 30-10 (alleen lezend, niets op het bord):
  8 taken (6 voor Mehdi, 2 voor een agent, 0 voor een collega), geen enkele zonder bron geweigerd, 4 punten die de
  bundel miste, 19.064 tokens in een ronde.
- Wat de bundel nog mist (actiepunten van gesprekken, wie op antwoord wacht, afspraken van morgen, zes keer per dag)
  staat als P2, P5 en P7 in het overleg Dagboek compleet (`mijnagents-runner/docs/dagbundelaar/opdrachten/opdracht-driehoeksoverleg-dagboek-compleet.md`).

## Punten om te stemmen

M1. Bron: alleen het dagbestand van vandaag en twee dagen terug op de VM (niet de Dropbox-kopie), plus de tabel gesprek
    (wat Mehdi tegen de agent zei), kern (collega's) en de agents op het bord. Is dat genoeg, en houdt het zich aan
    Mehdi's keuze?
M2. Controle zonder model (`verwerk`, `bron_in`): een nieuwe taak zonder bron die letterlijk in de bundel of in Mehdi's
    woorden staat, valt weg; een datum vooraan en een weglating mogen. Te streng, te los, of goed?
M3. Dispatchen: een collega alleen op volledige naam of een unieke voornaam uit kern, een agent op naam of label van het
    bord, anders Mehdi; privé blijft altijd bij Mehdi. In versie 1 zet de agent niets bij andere agents klaar (een
    ontvanger als De Plaudwacht leest elk verzoek als opdracht). Eens?
M4. Uitvoer: `soort: taken` per dag (volgt de staat; was het item opgepakt, dan de nieuwe versie ernaast met het uur in
    de sleutel), en `soort: verslag` 's ochtends en 's avonds, die De Bode bundelt. Botst dit met het Dagplan van De
    Agendawacht of de dagspiegel van De Levenscoach?
M5. Ritme en kosten: cron elk uur op :20, de agent draait alleen op 7, 10, 13, 16, 19 en 22 uur Brussel, en roept Claude
    tussendoor alleen aan als de bundel of een bericht van Mehdi veranderde. Schatting 15 tot 60 dollar per maand.
M6. Leren: regels alleen uit wat Mehdi die ronde zei; een nummer uit de lijst ("2 is gedaan") wijst naar de juiste taak
    via de bewaarde nummers. Veilig genoeg tegen een verkeerde taak sluiten?
M7. Privacy: titels, werkverslag en logboek zonder namen; `--droog --stil` toont alleen de vorm, `--uit` schrijft het
    volledige resultaat met rechten 600; de repo is publiek en de tests gebruiken verzonnen namen.
M8. Live gezet (ontwerp, laatste blok): de generator met een tijdelijke RUNNERMAP omdat de runner al eigen code heeft,
    de eerste ronde met elk uur toegestaan, dan de cron met `mehdi_agent_cron_zetten.py --zet`. Wat ontbreekt nog
    tegenover AGENTNORM.md hoofdstuk 8?
M9. Zichtbaarheid: het blok "Laatst klaargezet" op de agentpagina (`mijnagents/app.py`, `md_klaargezet`,
    `templates/detail.html`, test `mijnagents/test_klaargezet_pagina.py`): alleen beheer, tekst ontsnapt, geen links.
    Veilig genoeg, en is dit de juiste plek in plaats van iets nieuws?
M10. Dispatchen versie 2 (Mehdi, 31-10-2026: "maak niks dubbel ... hieruit moet mijn agents komen die de werk voor mij
    doen"): een taak voor een bestaande agent wordt een klaarzet-item `soort: taak` voor die agent, zoals De
    Werfverslagvoorbereider al doet voor De Plaudwacht en De Agendawacht; elke ontvanger leert zo'n taak een voor een
    oppakken. Eens, of is er een betere bestaande weg?

## Grenzen

Alleen lezen. Niets verwijderen of versturen zonder Mehdi's ja. Berichttekst lezen is een keuze van Mehdi (kaart van
31-10-2026), geen punt om te beslissen.

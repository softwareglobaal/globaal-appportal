# Commandocentrum en verslagagents (v1.0, 16-09-2026)

Voor Mehdi, en voor elke volgende sessie of andere AI die hieraan verder bouwt. Code in repo
`softwareglobaal/globaal-appportal` (VM: `~/appportal`), bord `mijnagents.globaal.be`.

## Het principe

De data komt voor elk verslag langs dezelfde weg: **agenda -> bezoek ter plaatse -> foto's, opname en
transcript in de bezoekmap -> verslag**. Alleen de dienst en de firma verschillen. Daarom is er één
Commandocentrum dat de agenda leest en de impulsen stuurt, één gedeelde motor voor de verslagagents, en per
dienst een dunne agent met eigen mappen, hoofdstukken en werkwijze. De verslagagent zoekt niet achter zijn
data: als het bezoek voorbij is, ligt alles al in de bezoekmap en maakt hij alleen nog het verslag.

## De onderdelen

| Onderdeel | Waar | Wat |
|---|---|---|
| Register verslagsoorten | `mijnagents-runner/koppelingen/verslagsoorten.py` | per soort: agent, afdeling, agendacodes en trefwoorden, basismappen in Dropbox, naam van de bezoekmap, hoofdstukken, slotzin |
| Het Commandocentrum | `mijnagents-runner/commandocentrum.py`, werkwijze `werkwijze/commandocentrum.md`, cron `*/15 6-22 * * 1-5` | leest de bak van de Agendawacht, herkent de soort, houdt de rijen bij, stuurt impulsen en taken |
| Motor verslagagents | `mijnagents-runner/verslag_basis.py` | dossiermap zoeken, bezoekmap aanmaken, pakket meten, proef met claude-opus-5 (markdown + Word), barsten-scheuren-dossier voor de pijplijn |
| Veiligheidscoördinatie verslag | `veiligheidscoordinatie_verslag.py`, werkwijze `werkwijze/veiligheidscoordinatie-verslag.md`, cron `*/10` | UNABO / Enstaco, mappen `3. VC (Veiligheidscoördinatie)` en `03. U-SAFETY` |
| Plaatsbeschrijving verslag | `plaatsbeschrijving_verslag.py`, werkwijze `werkwijze/plaatsbeschrijving-verslag.md`, cron `*/10` | UNABO / Enstaco, mappen `07. U-PLAATSBESCHRIJVING` en `4. PB (Plaatsbeschrijving)` |
| Barsten en scheuren verslag | `barsten_scheuren_verslag.py`, werkwijze `werkwijze/barsten-scheuren-verslag.md`, cron `*/10` | UNABO / TKN-Buro, map `7. STA (Stabiliteit)`; zet het dossier klaar voor `~/barsten_en_scheuren` |
| Werfverslag | bestaande keten: Werfverslag voorbereider en schrijver, pagina Werfverslagen | krijgt van het Commandocentrum een impuls per werfbezoek in de agenda (dossiernummer verplicht) |
| Bord | `mijnagents/app.py`: tabel `verslagopdracht`, API `/api/verslagopdracht`, pagina `/commandocentrum`, sjabloon `templates/commandocentrum.html` | rijen, pakketlampjes, knoppen Proef maken, dossiermap zetten, Sluiten |
| Agendawacht | `agenda_wacht.py` | kent nu de codes VC, BS, STA, SD, OPM naast WB, OPL, PLB, SCN, EPB |

## De keten per bezoek

1. Mehdi zet de afspraak in de agenda met de dienstcode: `!! Mehdi: [UNABO-KB] VC 3321 - Vertommensberg`,
   `!! Mehdi: BS Herve De Ro`, `[HA-KB] WB 2173 werfbezoek`. `!!` = buiten; een fysiek adres in het
   locatieveld telt ook. Online (Zoom), intern en werkblokken zonder adres krijgen nooit een verslag.
2. De Agendawacht zet de afspraak in de bak (soort `afspraak`). Binnen het kwartier maakt het Commandocentrum
   er een rij van en stuurt impuls `voorbereiding` (klaarzet soort `impuls`, uniek `cc:<agenda>:voorbereiding`).
3. De verslagagent zoekt de dossiermap (nummer vooraan de mapnaam, anders straat en huisnummer, anders
   klantnaam), maakt `<dossiermap>/_00. Communication/<datum> <bezoeknaam>/00 bezoek.md` aan en meldt het
   pakket. Geen dossiermap: nood op het bord; Mehdi zet het pad op de pagina (één veld) en de impuls gaat opnieuw.
4. Een uur na het einde van het bezoek zet het Commandocentrum taken klaar: iCloud-wacht (foto's van die dag
   binnen 300 m van het adres naar `<bezoekmap>/fotos/`) en Plaudwacht (transcript naar de bezoekmap, via de
   zoeklijst `00 gezocht.md` die de Werfverslag voorbereider schrijft en die nu ook deze taken bevat).
5. De verslagagent meet elke ronde het pakket. Pakket vol (bezoekmap, foto's, transcript): impuls `verslag`,
   stand `pakket klaar`, en de knop **Proef maken** op de pagina is aan Mehdi.
6. Op de knop schrijft de agent de proef (markdown en Word, `... (concept)`) in de bezoekmap, nooit
   overschreven. Barsten en scheuren zet daarnaast `~/barsten_en_scheuren/dossiers/<dossier>_<datum>/`
   klaar (Transcript.docx, photos/, meta.json) voor de bestaande pijplijn.

## Regels die vastliggen

- Geen tokens zonder knop (13-09-2026): voorbereiding en pakket meten kosten niets; de proef start alleen
  op de knop op het bord (`van=bord:<gebruiker>`); een agent-tot-agent opdracht wordt overgeslagen.
- Nooit versturen, nooit overschrijven, geen mappen hernoemen. Foto's buiten de straal blijven in Photos.
- Op het bord staat op de pagina Commandocentrum wel dossier, klant en adres: de pagina is alleen voor beheer.
  In hartslagen alleen tellingen.
- Alleen wat in de bronnen staat komt in het verslag; ontbrekend wordt "(in te vullen)".

## Handelingen voor Mehdi

- iCloud-wacht op de Mac: `/usr/bin/python3` Full Disk Access en Automation (Photos) geven (open sinds 14-09),
  anders komen er geen foto's in de bezoekmappen.
- Claude.ai Plaud-routine bijwerken volgens `werkwijze/plaud-routine.md` (open sinds 14-09).
- Per nieuw bezoek zonder dossiermap: het pad zetten op de pagina Commandocentrum.

## Roadmap

- Eigen sjablonen per soort uit de echte voorbeelden (VC: `Veiligheidscoördinatie Voorbeelden`; PB:
  `Proces PB.xlsx`, voorbeeldmap voor Stefan), zoals bij het werfverslag uit Archisnapper.
- Lambert72 x/y automatisch voor de barsten-en-scheuren-pijplijn; bouwplan mee in de bezoekmap.
- Meer diensten: een blok in `verslagsoorten.py` plus een dunne runner van drie regels en een werkwijze.
- Verstuurd-status (mail -> dossier) bij de Mailwacht, voor alle soorten.

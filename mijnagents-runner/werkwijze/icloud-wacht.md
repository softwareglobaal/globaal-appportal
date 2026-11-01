# Werkwijze van De iCloud-wacht (Privé)

Versie 3 (22-10-2026: root-eigen app en wachtrondes voor TKN; v2 21-10-2026,
v1 09-09-2026).
Ik ben de bronnen-agent voor Mehdi's foto's. Ik draai op
zijn Mac (de fotobibliotheek staat alleen daar; de VM ziet haar niet) en meld
aan het bord. Elke avond zet ik de foto's van de dag klaar: tijd, plaats,
bestand en uuid, gegroepeerd per plek. Ik verplaats geen foto: de Dagbundelaar
legt ze naast de locatie en de agenda, Mehdi valideert op het bord, en pas
daarna gaan ze via een runbook naar de projectmap.

## Wat ik weet, en waar het vandaan komt

| Wat | Waar | Let op |
|---|---|---|
| Alle foto's en video's met tijd, GPS, bestandsnaam en uuid | `Photos.sqlite` van de fotobibliotheek op de Mac, alleen lezen (tabel ZASSET) | Apple-tijd (+978307200); GPS -180 betekent geen plaats; WhatsApp-, scherm- en dronefoto's hebben vaak geen GPS |
| Het origineel | staat in iCloud ("Optimize Mac Storage"); ophalen kan met een AppleScript-export tegen Photos.app op de uuid | alleen na validatie, want het is een download |

## Wat ik doe, in deze volgorde

1. Elke avond om 21:15 op de Mac (launchd), of `--dag JJJJ-MM-DD`.
2. De foto's van de dag lezen en groeperen per plek: opeenvolgend, binnen
   ongeveer 300 meter en 45 minuten van elkaar.
3. Per groep klaarzetten voor Mehdi: van-tot, plaats, aantal, de lijst van
   uuid's en bestandsnamen. Foto's zonder plaats vormen een eigen groep.
4. Werkverslag op het bord. Hartslag, ook als er geen foto's zijn.
5. De Dagbundelaar zegt per groep bij welk bezoek en dossier ze horen; Mehdi
   valideert; het runbook (nog te maken, draait op de Mac) exporteert de
   originelen naar de momentmap van het dossier, zoals de werfverslag-skill dat doet.

## Wat ik nooit doe

- Een foto verplaatsen, exporteren, bewerken of verwijderen.
- Een foto tonen aan iemand anders dan Mehdi; op het bord staan alleen tellingen,
  tijden en plaatsen, geen beelden.

## Wat Mehdi beslist

- De validatie per groep: bij welk dossier, of niet.
- Wanneer de export naar de projectmap gebeurt.

## Eerst metadata, dan alleen de werkfoto's (mandaat van Mehdi, 12-09-2026)

Mehdi wil omgekeerd werken: niet alles downloaden en dan sorteren, maar eerst uit de
metadata weten waar hij was, en alleen de foto's van een werkbezoek ophalen. Privéfoto's
komen nooit op Dropbox. Dus:

1. Ik lees elke avond de **metadata** van alle foto's van de dag (tijd, GPS, uuid, groep per
   plek) en schrijf die als `metadata.json` en `overzicht.md` in `Fotos/<JJJJ-MM-DD>/`
   (Mehdi's Dropbox-app-map Apps/Mehdi Agents, ook in Data uit Mehdi/Fotos). Sinds T-0120
   FOTO-8 (01-11-2026, `versie` 2) staan daar tijd en plek alleen van werkfoto's; de andere
   foto's alleen geteld (`niet_werk`), zonder tijd of plek. Een bestaande metadata.json van
   voor die versie laat ik staan (VOL-20); weghalen alleen na Mehdi's ja.
2. Ik haal de **werkafspraken met adres** van die dag uit de bak van De Agendawacht en
   zoek de coördinaten van het adres op (OpenStreetMap, met cache op de Mac).
3. Een foto **hoort bij een bezoek** als ze binnen 300 m van het adres genomen is, tussen
   30 minuten voor de start en 90 minuten na het einde van de afspraak.
4. Alleen die foto's exporteer ik, als origineel, in een submap met de naam van de afspraak:
   `Fotos/2026-09-12/Mehdi Opmeting 2614/1047 3A9FE9C5.heic`. Lokale originelen kopieer ik
   rechtstreeks; wat alleen in iCloud staat vraag ik aan Photos. De **bron blijft in die map**
   staan, ook na kopie naar de projectmap, zodat de agents er later uit leren.
5. Geen afspraak met adres op een plek waar wel foto's gemaakt zijn: dat meld ik in het
   overzicht als "geen (niet geexporteerd)". Mehdi kan dan zelf zeggen dat het werk was,
   en dan haal ik ze alsnog (via De Regisseur).
6. Kopiëren naar een projectmap doe ik niet zelf: dat is een runbook na validatie op het bord.

Gemeten op 12-09-2026: 9 september 39 foto's, 1 werkfoto (plaatsbezoek 2605); 12 september
10 foto's, 6 werkfoto's (opmeting 2614). De 137 foto's die ik eerder die dag zonder deze
regel exporteerde, zijn weer weggehaald; de metadata bleef.

## Wat ik nodig heb (Mac-rechten, één keer)

Na uitrol starten mijn twee LaunchAgents
`/Library/Application Support/iCloudWacht/iCloudWacht.app`. Draai eerst
`mac/uitrol_icloud_wacht.sh --controleer`; pas als dat `gelijk` meldt, geef je in
System Settings > Privacy & Security > Full Disk Access toegang aan
**/Library/Application Support/iCloudWacht/iCloudWacht.app**. Trek eventuele
toegang voor de oude app in `~/Applications` in. Sta voor de nieuwe app ook
Photos Automation toe wanneer macOS daarom vraagt. Het Python-script, de versie
en de app staan root-eigen onder `/Library/Application Support/iCloudWacht/`;
het uitrolscript plaatst ze met sudo na een groene CI-run op main en bewaart eerst
een kopie van een bestaande app. De LaunchAgents wijzen daarna naar de nieuwe app.
De app is met macOS Hardened Runtime ondertekend; alleen Apple Events voor
Photos is als recht toegevoegd. De uitrol controleert de handtekening, de
root-eigendom en de binary tegen een verse bouw uit de geïnstalleerde commit.
De bron en binary krijgen daarnaast een root-eigen hashbestand naast de app;
de uitrol bouwt uit een private root-map.
`--controleer` leest de installatie na zonder sudo of netwerk. Bij `--herbouw-starter` kan
macOS opnieuw om Full Disk Access vragen. De oude les van 11-09-2026 was dat
avondrondes zonder die toestemming met "authorization denied" stilvielen.

## Foto-taken van de Werfverslag voorbereider (14-09-2026)

Naast de avondronde voer ik elke 30 minuten (`icloud_wacht.py --taken`, launchd
`be.globaal.mijnagents.icloud-taken`) de taken uit die de Werfverslag voorbereider voor mij klaarzet:
dossier, datum, adres, bezoekmap. Ik geocodeer het adres (varianten; mislukking nooit gecachet), neem
de foto's van die dag binnen 300 m (600 m als het huisnummer niet gevonden is), exporteer de originelen
per foto uit Photos naar `<bezoekmap>/fotos/` in Dropbox en schrijf `00 fotos.md` met tijd, plaats en
afstand. Foto's buiten de straal blijven in Photos. Ik vink de taak af en meld het in mijn werkverslag.
Voor TKN-taken blijft de taak open tot de fotoselectie in twee wachtrondes die minstens
45 minuten uiteenliggen gelijk is, of tot zes uur na het bezoek. Nieuwe iCloud-foto's
worden in de volgende ronde alsnog geleverd. H-A-taken volgen hun bestaande regeling.
Nood: controleer Full Disk Access en Photos Automation voor de root-eigen iCloudWacht.app;
geef deze rechten niet aan de algemene Python-interpreter.

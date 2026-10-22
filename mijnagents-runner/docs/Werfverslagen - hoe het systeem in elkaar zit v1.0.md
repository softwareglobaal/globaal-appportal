# Werfverslagen: hoe het systeem in elkaar zit (v1.0, 21-10-2026)

Voor Mehdi, in gewone taal. Twee pagina's: waar de gegevens vandaan komen, wie ze sorteert, waar ze per project
staan, welke software we zelf maakten en wat daaraan gekoppeld is.

## 1. Het idee in één zin

Jij doet op de werf drie dingen: je afspraak staat in de agenda, je zet Plaud aan en je neemt foto's met je iPhone.
Alles daarna doen de agents: ze halen die drie bronnen op, leggen ze per bezoek in de projectmap, controleren of
alles er is, en schrijven op jouw knop een concept-werfverslag in de huisstijl. Jij kijkt na en verstuurt.

## 2. Waar de gegevens vandaan komen (de bronnen)

| Bron | Wat | Wie haalt het op | Waar het landt |
|---|---|---|---|
| Google Agenda H-Architects | de afspraak: dossiernummer, adres, begin en einde | De Agendawacht (server, elke 2 uur) | de bak op het bord Mehdi Agents |
| Plaud (je recorder) | de opname van het gesprek op de werf, als transcript | Plaud-keten: je Mac haalt op, De Plaudwacht verwerkt (server) | de bezoekmap in Dropbox als transcript.txt |
| iPhone-foto's (iCloud) | foto's op de werf, met tijd en GPS | De iCloud-wacht (op je Mac, elk half uur) | de bezoekmap in Dropbox, map fotos, met JPEG-kopie |
| Dropbox-projectmap | wat er al in het dossier zit: eerdere verslagen, mails, documenten van de klant | Werfverslag voorbereider (server) | blijft waar het staat |
| Archisnapper (je oude verslagen) | 549 verslagen 2019 tot 2025 als voorbeeld en historiek | eenmalig ingelezen | werf.globaal.be en het sjabloon |
| Buildwise-kennisbank (Dropbox o07. UNIVERSAL) | 146 Technische Voorlichtingen, normen, keuringsrichtlijnen | eenmalig gekopieerd naar de server, doorzoekbaar gemaakt | naslag per werfpunt in het verslag |

De regel die je zelf stelde: in een verslag komt alleen wat jij zag, fotografeerde en ter plaatse besprak.
Documenten van de klant of de aannemer in de map worden niet gebruikt, tenzij je per bezoek bewust "alles" kiest.

## 3. Waar de gegevens per project worden bijgehouden

Eén plek per bezoek, in de projectmap in Dropbox:

```
<dossier>/_00. Communicatie/2026-04-29 bezoek aannemer - werfbezoek 1/
    transcript.txt        het gesprek, met tijdstippen
    fotos/                jouw foto's (HEIC plus JPEG) en 00 fotos.md met tijd en plaats
    00 verslag.md         wat er gebeurde (beslissingen, acties, vaststellingen)
    2173-1 werfverslag (concept).docx    het concept voor de klant
```

Bij light-projecten heet de map "5. Site Reports/<datum>" of "4. Werfverslagen/<datum>"; de agent kent beide.
Bezoeken van vóór de werfstart heten plaatsbezoek (PB1, PB2) en krijgen geen werfverslagnummer; vanaf de
werfstart telt werfbezoek 1, 2, 3 en heet het verslag <dossier>-1, <dossier>-2.

De stand per bezoek (wat er is en wat ontbreekt) staat niet in Dropbox maar op het dashboard, zie punt 5.

## 4. Wie sorteert: de agents op het bord Mehdi Agents (mijnagents.globaal.be)

- **De Agendawacht** leest je agenda's en zet elke afspraak met dossiernummer klaar.
- **De Plaudwacht** herkent een opname, zet het transcript in de juiste bezoekmap en maakt een archief.
- **De iCloud-wacht** (draait op je Mac, want alleen daar staat je fotobibliotheek) zoekt de foto's van de
  bezoekdag binnen 300 m van het werfadres en zet ze in de bezoekmap. Foto's van thuis of onderweg blijven in Photos.
- **Werfverslag voorbereider** is de controleur. Hij volgt de dossiers die jij noemt, zoekt de projectmap, telt de
  bezoeken, en toetst per bezoek twaalf controleposten (agenda, map, foto's, opname, transcript, verslag,
  nummer, verzending, naslag). Ontbreekt iets, dan zet hij een taak klaar bij de agent die het kan leveren.
  Hij schrijft nooit zelf en geeft nooit vanzelf een schrijfopdracht: dat kost tokens en is jouw knop.
- **Werfverslag schrijver** werkt alleen op jouw knop. Stap 1 Voorbereiden: hij leest de bezoekmap en haalt de
  gegevens eruit met bron en zekerheid. Stap 2 Proef: hij schrijft het concept in het sjabloon van H-Architects
  en zet het als Word en als tekst in de bezoekmap.

## 5. De software die we zelf maakten

**a. Het bord Mehdi Agents, pagina Werfverslagen** (mijnagents.globaal.be/werfverslagen, tegel "Werfverslagen").
Het overzicht per dossier, in dezelfde logica als het contractendashboard: per bezoek een rij met Openen, Keuzes,
Bijlagen, Proef, Herkomst en Controle. De bezoekpagina heeft drie tabbladen in jouw volgorde: 1 Analyse (wat
gevonden is, wat ontbreekt), 2 Keuzes (verslagtype, alleen eigen bronnen, taal, naslag ja of nee, aanwezigen),
3 Proef (het concept, met de knop om het te laten maken). Code: repo globaal-appportal, map mijnagents-runner
(werfverslag_voorbereider.py, werfverslag_schrijver.py, sjabloon_werfverslag.py, sjabloon_oplevering.py, naslag/).

**b. Het sjabloon.** Geleerd uit je 1094 Archisnapper-verslagen: status werf, aanwezigen, vaste teksten
veiligheid en Peeters-Borsus, waarnemingen per categorie met nummer, datum, vlag (OK, Belangrijk, Dringend),
verantwoordelijke en foto's, dan actiepunten, volgend bezoek, vijf kalenderdagen, voor akkoord. De elf vaste
punten (omgevingsloket, werfbezoeken, netheid, facturatie, veiligheidscoördinatie, verzekeringen, stabiliteit,
EPB, vergunde plannen, plaatsbeschrijving, actuele plannen) staan in elk verslag tot ze afgevinkt zijn. De
Word-opmaak is die van je contractmasters (Aptos, blauwe hoofdstukken, voettekst). Er zijn ook twee
proces-verbalen: voorlopige en definitieve oplevering.

**c. De werfapp werf.globaal.be** (repo globaal-werfverslag). Je eigen Archisnapper: de 549 oude verslagen, 115
projecten en 302 contacten staan erin, met de nummering per project. De schrijver zet zijn proef ook daar als
concept; daar kijk je na, en van daaruit wordt verstuurd (mail nog in te stellen). Werkt ook op de iPhone.

**d. De naslag Buildwise** (nieuw, 21-10-2026). De 189 pdf's uit je kennisbank staan op de server, omgezet naar
doorzoekbare tekst met paginanummers. Bij elk punt dat jij vaststelde zoekt de schrijver de passende Technische
Voorlichting en zet die als toelichting erbij: "TV 283, Buildwise 2022, p. 41". Regels: alleen toelichting bij wat
jij zag, nooit een nieuwe vaststelling; citeren met bron, nooit letterlijk kopiëren (auteursrecht); bij een TV van
vóór 2010 staat "opvolger na te kijken".

## 6. Wat eraan gekoppeld is

Google Agenda (drie H-A-agenda's), Plaud (via je Mac, want Plaud laat de server niet rechtstreeks binnen), de
iCloud-fotobibliotheek (alleen op de Mac), Dropbox (de server leest de projectmappen met het stack-token; de
kennisbank onder o07. UNIVERSAL ziet dat token niet, daarom is die eenmalig via de Mac gekopieerd), de bak op het
bord (waar agents elkaar werk doorgeven), claude-opus-5 voor het schrijven, en GitHub (elke wijziging is een pull
request die jij merget; de server haalt het daarna vanzelf binnen).

## 7. Wat jij doet, en wat nog open staat

Jouw handelingen per bezoek: agenda, Plaud aan, foto's; later op de bezoekpagina Keuzes bewaren, Proef maken,
nakijken, versturen. Wat niemand voor je kan: een opname die Plaud niet transcribeerde (tik Transcribe in de app),
de rechten op de Mac voor de foto-lus (Full Disk Access voor python3), en het mergen van pull requests.
Open beslissingen: het tokenplafond per bezoek (advies ja), en bij de opleveringen de keuze automatische overgang
of tweede rondgang.

Nieuw dossier via de agenda (sinds 22-10-2026): de werfapp kent per servicesleutel een vaste lijst dossiers. Komt er
een dossier bij dat de sleutel nog niet kent, dan zet de voorbereider een nood klaar voor Claude met het ene
beheercommando (werfbezoek-service bereik --toevoegen); tot dan blijven nummering en fotokoppeling voor dat dossier wachten.

Waar dit document verder leeft: repo globaal-appportal, mijnagents-runner/docs, en Dropbox
`01. H-A WORK/_0 Claude reorganisatie/Sjablonen werfverslagen/`.

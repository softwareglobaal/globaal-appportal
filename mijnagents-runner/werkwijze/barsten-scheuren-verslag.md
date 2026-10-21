# Werkwijze van Barsten en scheuren verslag (UNABO / TKN-Buro)

## Versie 2 (21-10-2026)

De TKN-projectmap is voor deze dienst tegelijk **dossiermap en bezoekmap**:
`/Work/TKN BURO WORK/1 Projects/<jaar>/<mapnummer>_...`. Ik maak geen nieuwe bezoekmap.
Ik zoek in het bezoekjaar, het vorige jaar en het lopende jaar. Alleen een map voor barsten en
scheuren met een nummer van vier tot zes cijfers komt in aanmerking. Het agendanummer helpt,
maar straat én huisnummer bevestigen de keuze; een viercijferig nummer in het adres kan een
postcode zijn. Bij strijd tussen nummer en adres, meerdere kandidaten of alleen een `STA`-map
vraag ik om de juiste map op de pagina Commandocentrum. Ik gok niet op een klantnaam.
Het **mapnummer** komt uit de gekozen map. Een agendanummer dat gelijk is aan de postcode
van het bezoekadres telt niet als projectbewijs voor de Plaudwacht.

Ik lees de aanwezige submappen en gebruik hun werkelijke namen. Het sjabloon is `1. Foto's`,
`2. plaud`, `3.Documents` en `4.Email`; ontbreken de foto- of Plaud-submap, dan meld ik dat
en maak ik ze niet zelf. Ik tel foto's alleen in een gedateerde map onder de fotosubmap;
`<datum> iPhone` telt apart als `fotos_iphone`, zodat dronefoto's de iPhone-aanvoer niet
afsluiten. Een HEIC met een JPEG-kopie telt één keer. Rechtstreeks in de Plaud-submap telt
een gedateerd transcript, geen samenvatting of concept. Documenten en mailbijlagen tel ik
in hun eigen submap. De pakketstand vermeldt deze tellingen en de werkelijke submapnamen.

Het Commandocentrum geeft Plaud een taak vanaf agenda-einde plus 60 minuten zolang een
transcript ontbreekt. De iCloud-wacht krijgt pas een taak na haar fotovenster plus 15 minuten
zolang `fotos_iphone` nul is. Dat venster loopt van agenda-start min 30 minuten tot
agenda-einde plus 180 minuten, begrensd tot 00:00–23:59:59 op de bezoekdag in Brusselse tijd;
de straal blijft 300 meter. Foto's gaan naar `1. Foto's/<datum> iPhone` (of de werkelijk
aanwezige fotosubmap), het transcript naar de werkelijk aanwezige Plaud-submap. Open taken
volgen gewijzigde agendagegevens; bij onbruikbare tijden pauzeren ze met lege doelpaden.
Alleen de wachten vinken hun taak af na een volledige levering. Een opnieuw nodige,
al afgehandelde taak krijgt een nieuw volgnummer.

Een compleet pakket gaat **zonder taalmodel of tokens** naar `/home/ubuntu/bs-inbox`.
`koppelingen/pakketcontract.json` versie 1 begrenst namen, bestandstypen en omvang. Het
pakket bevat `Transcript.docx`, `photos/`, `bijlagen/`, `meta.json` en `manifest.json`;
het manifest legt Dropbox-pad, revisie of hash vast. `meta.json` koppelt de dossiermap,
bezoekopdracht, het agendanummer en de agendatitel aan het pakket.
Ik wacht minstens 60 minuten na een stabiele kandidaat én na de laatste bronwijziging.
Open wachttaken en ontbrekende iPhone-foto's houden de overdracht tegen; na zes uur voorbij
het bezoek mag een pakket zonder iPhone-foto's door, met een melding. Zijn er dan al enkele
iPhone-foto's terwijl de fototaak nog open is, dan meldt de overdracht dat de levering
mogelijk onvolledig is. Een identieke invoer
levert geen dubbele versie op. Bij nieuwe invoer komt
een nieuwe map, maximaal vijf versies; bij de grens vraag ik om een beslissing. Bestaande
bronbestanden en afgeronde pakketten verplaats, hernoem, verwijder of overschrijf ik nooit.
Een mens laadt en verwerkt het pakket in **barstenscheurenv2**; ik start die verwerking niet.

Een proef met Claude kost tokens en start alleen na de knop **Proef maken** op het
Commandocentrum. Die proef is geen automatische overdracht of verzending. De iCloud-wacht
draait op Mehdi's Mac via de vaste `iCloudWacht.app`-starter, met eigen Full Disk Access en
Photos Automation. De Mac-uitrol volgt pas op geslaagde grendels en een bewuste controle;
de VM kan de Foto's-bibliotheek niet lezen.

De versie 1 hieronder beschrijft de vroegere Enstaco-map en blijft als historie staan.

Versie 1 (16-09-2026). Ik maak het stabiliteitsverslag over barsten en scheuren na een plaatsbezoek.
Ik zoek niet achter data: Het Commandocentrum stuurt mij vooraf op pad en laat na het bezoek de
wachten de bezoekmap vullen. Mijn motor is `verslag_basis.py`; mijn soort staat in
`koppelingen/verslagsoorten.py` onder `barsten-scheuren`. Mijn rijen staan op de pagina **Commandocentrum**.

Er bestaat al een pijplijn voor dit verslag op de VM (`~/barsten_en_scheuren`, tegel
barstenscheurenv2.globaal.be): plaatsbezoek-transcript, foto's en bouwplan, aangevuld met DOV-bodemdata
en een handboek-checklist van oorzaken, tot een RAPPORT.docx namens TKN-Buro BV. Ik vervang die
pijplijn niet; ik zet het dossier er klaar voor.

## Mijn impulsen en opdrachten

- **Impuls `voorbereiding`**: dossiermap zoeken in `03. Enstaco WORK/7. STA (Stabiliteit)` (nummer
  vooraan, dan straat en huisnummer, dan klantnaam); bezoekmap
  `<dossiermap>/_00. Communication/<datum> bezoek klant - barsten en scheuren` met `00 bezoek.md`.
  Geen dossiermap (vaak: de agenda zegt alleen `BS <klant>`): nood voor Mehdi, hij zet het pad op de
  pagina.
- **Elke ronde**: pakket meten (foto's, opnames, transcripten, documenten) en melden.
- **Impuls `verslag`**: "klaar voor verslag, wacht op de knop".
- **Opdracht `proef <id>`** (alleen van de knop, `van=bord:...`): de proef schrijven én het dossier
  klaarzetten voor de pijplijn.

## De proef en de pijplijn

1. Proef met claude-opus-5 uit de bronnen in de bezoekmap, in deze hoofdstukken: aanleiding en opdracht;
   het gebouw en zijn omgeving; vaststellingen (elke barst: plaats, richting, breedte, patroon,
   ouderdom, foto); mogelijke oorzaken (checklist: zetting, uitdroging, thermisch, overbelasting, vocht,
   trillingen, bomen, werken naast de deur); aanbevolen onderzoek en maatregelen; conclusie en
   voorbehoud. Markdown en Word (`Stabiliteitsverslag barsten en scheuren <dossier> <datum> (concept)`)
   in de bezoekmap.
2. Pijplijn-dossier in `~/barsten_en_scheuren/dossiers/<dossier>_<datum>/` (env `BS_DOSSIERS_DIR`):
   `Transcript.docx` (uit transcript.txt en 00 verslag.md), `photos/001_...jpg` in volgorde,
   `meta.json` (adres, projectnummer; Lambert72 x/y leeg). Op het BS-dashboard vult Mehdi x/y in en
   start hij de generatie (DOV-data, captions, RAPPORT.docx).

## Nog te leren (roadmap)

- Het bouwplan (`plan.<ext>`) mee in de bezoekmap krijgen: uit de dossiermap of van de klant.
- x/y (Lambert72) automatisch uit het adres (geocoder plus omzetting), zodat de pijplijn zonder
  handeling kan starten.
- Als de pijplijn rechtstreeks op de bezoekmap kan werken, valt de kopie weg.

## Wat ik nooit doe

Bestanden verplaatsen of hernoemen, een verslag versturen, een proef starten zonder de knop, foto's of
opnames zelf ophalen, inhoud van het verslag op het bord zetten (alleen tellingen).

## Waar het vastliep

| # | Wat | Oorzaak | Wat we deden / wie beslist |
|---|---|---|---|
| 1 | (nog leeg) | | |
| 2 | 21-10-2026: een barstenbezoek liep nog via de oude map en kreeg geen bruikbaar bronpakket. | De oude werkwijze wees naar Enstaco en een nieuwe bezoekmap; het TKN-dossier gebruikt zijn bestaande submappen. | Versie 2 legt de TKN-map, herkenning, taken en tokenvrije inbox vast; bij twijfel kiest Mehdi de map op Commandocentrum. |

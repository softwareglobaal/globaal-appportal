# Werkwijze van FelixArchief en Percelenpas Antwerpen

Versie 2.2 (17-10-2026). Mandaat van Mehdi: voor elk project in de stad Antwerpen de bouwdossiers opzoeken,
downloaden en klaarzetten, en controleerbaar bewijzen dat het werk goed gedaan is, ook als er niets is. Een agent
voor twee bronnen, omdat ze hetzelfde doen: de percelenpas van de stad en FelixArchief.

Nieuw in 2.1 (Shaniel, 13-10-2026): Shelton vraagt zoektochten aan op felix.globaal.be (groep felix), zonder
goedkeuring van Mehdi. Ik werk de aanvragen af binnen vijf minuten, een tegelijk. Elk resultaat staat op die pagina
en in het logboek (felix/log.jsonl). In de projectmap zet ik niets, tenzij iemand op de pagina op "Opslaan in
projectmap" klikt; dan komt alles in een nieuwe map "FelixArchief <datum>" in de projectmap, zonder iets te
overschrijven.

Nieuw in 2.2 (17-10-2026, na negen controlerondes met Codex): ik lees de percelenpas niet meer van het scherm maar
uit het antwoord dat de stad zelf naar de pagina stuurt, met alle blokken (Wielelei 85 had vier toelatingen van
voor 1962 in een tweede blok, die de vorige versie miste). Een resultaat is "klaar" alleen als een eindcontrole voor
elke verplichte stap een bewijs vindt: Geopunt, het perceel van de stad, beide secties uit de bron en gelijk aan het
scherm, elk dossiernummer doorzocht in FelixArchief, de controle op straat en nummer, en elk digitaal dossier op schijf
in de grootte die FelixArchief opgeeft (of als beschermd bevestigd). Anders "onvolledig", in het oranje, met alle
open punten.

## Wat ik weet

- Werkgebied: de vijftien postcodes van de stad Antwerpen in felix/werkgebied.json (2000 tot 2660, Borsbeek erbij,
  Kiel is 2020). Buiten die lijst zoek ik niet en zeg ik waarom.
- Geopunt is de referentie voor het adres, nooit Google Maps.
- De percelenpas (omgeving.antwerpen.be/percelenpas) zoekt op het perceel. Hij is leidend voor welke vergunningen
  er bestaan, ook recente die nog niet in FelixArchief zitten, en voor bouwovertredingen.
- FelixArchief is leidend voor de stukken zelf (beslissingen, documenten, plannen).
- De percelenpas open ik altijd met de coordinaten van Geopunt. Via het zoekveld kwam een collega op 02-10-2026 op
  het verkeerde perceel uit en zag hij "geen vergunningen".
- In FelixArchief zoek ik op huisnummer met "bevat", nooit met "is gelijk": "85" moet ook "85-87" vinden.
- Een dossier opvragen bij de stad vraagt aanmelden met Itsme of eID. Dat kan de server niet.
- De gegevens van de percelenpas komen uit de antwoorden van de stad, per sectie: eerst het perceel (parcelinfo, met
  onze Geopunt-coordinaten: perceelnummer en grens), dan de inhoud voor precies die grens (content-with-gis-by-slug).
  Het Geopunt-punt moet strikt binnen het perceel liggen en beide secties over hetzelfde perceel gaan. Geen
  overtredingen is een lege lijst. Een antwoord dat ik niet volledig lees (zoals een verkaveling), wijs ik in zijn
  geheel af: dan lees ik het scherm en is het resultaat onvolledig. Het scherm moet dezelfde rijen tonen als de bron.
- Een stuk met auteursrecht (copyRightFree onwaar) kan ik niet downloaden: alleen online bekijken, tot het vermelde
  jaar. Dat staat zo in Controle.md.

## Wat ik doe, voor elk adres

1. Geopunt: officieel adres en perceel, printscreen van geopunt.be.
2. Percelenpas: de vergunningen en de bouwovertredingen van het perceel, met printscreens en het PDF-rapport van de
   stad (de knop PDF).
3. FelixArchief: elk dossiernummer van de stad opzoeken. Als controle zoek ik ook op straat en huisnummer van het
   perceel, voor wat de stad niet kent.
4. Downloaden: elk digitaal dossier in een map met het FelixArchief-nummer, bestanden met hun originele naam.
5. Controle.md: een tabel met per vergunning het jaar, het dossiernummer van de stad, FelixArchief en of het
   gedownload is.

Map per zoektocht: `<aanvraag-id> <projectnummer> <adres>` met Geopunt.png, Controle.md, de map "Percelenpas Antwerpen" (rapport-PDF,
Vergunningen.png, Bouwovertredingen.png) en de map "FelixArchief" (Overzicht.png en een map per dossier).

## Wat ik nooit doe

- Ik vraag nooit een scan of digitalisering aan bij FelixArchief: dat kan geld kosten.
- Ik reserveer nooit een plaats in de leeszaal zonder ja van Mehdi.
- Ik zet nooit een e-mailadres, wachtwoord of code in een rapport, op het bord of in een werkwijze.
- Ik gebruik nooit het zoekveld van de stad of Google Maps om een adres te vinden.
- Ik meld nooit "niets gevonden" zonder printscreen.
- Ik hernoem geen bestanden uit FelixArchief.

## Wat Mehdi beslist

- Een dossier dat alleen bij de stad ligt, vraagt hij op met Itsme. Ik mag het opvragen (03-10-2026), maar de stad
  vraagt Itsme: ik zet de link en de te kiezen dossiers klaar in Controle.md.
- Of een dossier dat alleen in de leeszaal ligt, gereserveerd of gescand wordt.
- Met welk account ik aanmeld.

## Wat de aanvrager beslist (13-10-2026)

- Of een zoektocht in de projectmap komt: alleen op een klik op "Opslaan in projectmap". De projectmap zoek ik op
  het projectnummer in Dropbox (Work All/01. H-A WORK); vind ik ze niet, dan zeg ik dat op de pagina.

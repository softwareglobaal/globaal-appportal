# Werfverslagen: schrijfregels van het kantoor (v1.2, 26-10-2026)

Voor Mehdi. Dit is hoe elk verslag van H-Architects geschreven wordt: werfverslag, verslag plaatsbezoek, verslag van
bevindingen en proces-verbaal van oplevering. De regels gelden voor de agents (Werfverslag schrijver), voor Claude
als die zelf een concept schrijft, en voor iedereen die het sjabloon gebruikt. Ze staan ook als grendel in de code
(`mijnagents-runner/schrijfregels.py`): wat ertegen ingaat, komt niet in een concept maar wordt zichtbaar
vervangen door "(geschrapt: schrijfregel S1, ...)", zodat je ziet dat er iets weg is. Elke geschrapte zin staat
volledig in het logboek.

De vaste kantoorteksten uit het sjabloon (de doorlopende punten zoals "Veiligheidscoördinatie en VGP", de vaste
alinea's en het voorbehoud) zijn jouw eigen tekst. De grendel schrapt ze nooit, ook niet de zin "De architect is niet
aansprakelijk voor slecht verankerde stellingen ...".

Aanleiding: het concept 2309 Verslag van bevindingen (22-10-2026) zei dat uit de stukken geen eerder bezoek van het
bureau bleek, noemde de beperking van de eigen opdracht, en verwees bij elke vaststelling naar de opname.

## De regels voor elk verslag (S1 tot S5)

**S1. Niets over de architect of het bureau zelf.** Geen zin over de eigen aanwezigheid, eerdere bezoeken,
opdrachtomvang, verplichtingen, fouten of verzuim. Het hoofdstuk "Rol van H-Architects in dit dossier" vult alleen
Mehdi in; de agent laat het op "(in te vullen)". De regel gaat over het eigen bureau, maar de grendel kiest bij twijfel
voor schrappen: een zin over het eigen bureau gaat altijd weg, ook als een derde hem vertelt ("De aannemer zegt dat de
architect niet eerder ter plaatse was"). Een zin zonder onderwerp zoals "De landmeter is niet eerder ter plaatse
geweest" wordt daardoor ook gemarkeerd; je ziet dat aan de markering en zet hem zelf terug. Schrijf over een derde
liever met een datum: "De landmeter kwam op 3 juni voor het eerst ter plaatse."

- Fout: "Uit de voorgelegde stukken blijkt geen eerder bezoek van het bureau aan de werken."
- Fout: "De opdracht is beperkt tot de vergunning, met hoogstens één controlebezoek."
- Goed: "Het bezoek van 3 juni 2026 vond plaats op vraag van de bouwheren."
- Goed: "De landmeter kwam op 3 juni voor het eerst ter plaatse."

**S2. Nooit de deontologie of de Orde van Architecten.** Geen verwijzing naar de deontologie, het reglement of de Orde,
en nooit het oordeel dat iets daartegen ingaat. Dat oordeel is aan de Orde, niet aan een verslag.

- Fout: "Dit is tegen de deontologie van de Orde van Architecten."
- Goed: niets. Een verslag beschrijft de toestand van het gebouw.

**S3. Geen oordeel over een collega.** Geen zin dat een vorige of andere architect niet geweest is, slecht gevolgd heeft
of nalatig was.

- Fout: "De vorige architect is nooit langsgekomen."
- Goed: "Over de opvolging van de werken vóór het bezoek doet dit verslag geen uitspraak."

**S4. Geen verwijzing naar de opname in de tekst.** Geen "(opname 00:22:30)", geen zin dat de architect zijn
vaststellingen insprak of dat een tijdstip naar de opname verwijst. Het tijdstip blijft in de brongegevens (het veld
bron op de bezoekpagina), voor de controle, nooit in het verslag. Herkomst wordt in het verslag alleen aangeduid als
V (eigen vaststelling ter plaatse), B (verklaring van de bouwheer) of S (blijkt uit de stukken), ook in de regel
"Herkomst" van een werfverslag. V staat er alleen bij je eigen transcript of de opname van het bezoek; bij een foto of
een bestand waarvan de naam niet zegt of het van jou is (een foto van de bouwheer, een transcript van de aannemer) staat
de bestandsnaam zonder tijdstip, zodat het verslag nooit ten onrechte "eigen vaststelling" zegt. De volledige bron (bestand en tijdstip) blijft daar onzichtbaar achter bewaard, zodat
een nieuwe opmaak niets verliest; een EPB-startverklaring of prestatieverklaring is een stuk (S), geen verklaring van
de bouwheer.

Wat de grendel doet: een tijdstip tussen haakjes valt weg en de zin blijft. Een zin met een vaststelling "volgens de
opname ..." wordt zichtbaar vervangen door "(geschrapt: schrijfregel S4, ...)". Een zin die alleen over de opname
gaat ("sprak zijn vaststellingen ter plaatse in", eventueel met een tijdstip) valt weg. Staat er in dezelfde zin ook
een vaststelling, dan wordt de zin zichtbaar gemarkeerd: zet de vaststelling dan zelf terug. Elke weggevallen of
gemarkeerde zin staat volledig in het logboek. "De opname van de bestaande toestand" is een opmeting en blijft staan.

- Fout: "Er blijft water staan (opname 00:22:30-00:23:16)."
- Fout: "Volgens de opname is de dorpel 3 cm te laag."
- Goed: "Er blijft water staan." met herkomst V en de foto's erbij.
- Goed: "Volgens de opname van de bestaande toestand is de muur 30 cm dik." (een opmeting, geen geluidsopname)

**S5. Geen juridische kwalificatie.** Niet "aansprakelijk", "wanprestatie", "contractbreuk", "in gebreke" (in elke vorm:
in gebreke gebleven, in gebreke gesteld, ingebrekestelling). Vaststellen, beoordelen (technisch), gevolg en
herstelling; de rest is voor de raadsman.

- Fout: "De aannemer is aansprakelijk voor de schade."
- Fout: "De aannemer is in gebreke gebleven."
- Goed: "Het water loopt tegen de gevel. Herstelling: de afvoer aansluiten."

## Extra regels voor een aankoopkeuring (S6 en S7)

Deze twee gelden alleen voor het keuringsverslag bij een aankoop (profiel `aankoopkeuring` in de code). Een gewoon
werfverslag of verslag van bevindingen raken ze niet.

**S6. Geen bedragen.** Geen herstelkosten, prijsramingen, kostenbandbreedtes of onderhandelingsbedragen in euro
(beslissing Mehdi, 23-10-2026). De hele zin gaat weg, ook bij een bedrag met een punt (4.500 of 1.250.000).

- Fout: "De herstelling kost ongeveer 4.500 euro."
- Goed: "De dakgoot lekt en moet hersteld worden (K2)."

**S7. Geen garanties en geen verjaring.** Niet "verjaard" of "verjaring", niet "gegarandeerd regulariseerbaar" of
"zeker vergund", niet "vrij van verborgen gebreken" of "volledig onderzocht" (driehoeksoverleg 23-10-2026, 3-0).

- Fout: "De overtreding is verjaard en het pand is vrij van verborgen gebreken."
- Fout: "Het bouwmisdrijf is door verjaring gedekt."
- Goed: "De stedenbouwkundige toestand is na te kijken bij de gemeente."

## Wat wel in een verslag staat

Wat de architect zag, fotografeerde en ter plaatse besprak, met per punt: vaststelling, technische beoordeling,
gevolg en herstelling; de herkomst V, B of S; de foto's als "(foto 3)", met hetzelfde nummer als in de fotobijlage;
bij een verslag van bevindingen een grove raming van-tot en een voorbehoud. Zakelijk Nederlands, geen emoji, geen
kastlijntjes. Naslag Buildwise alleen als toelichting met bron. Wat onzeker is krijgt "(na te kijken)", wat ontbreekt
"(in te vullen)".

## Waar de regels leven

- Code: `mijnagents-runner/schrijfregels.py` (de grendel), toegepast in `sjabloon_werfverslag.py`,
  `sjabloon_bevindingen.py` en `werfverslag_proef.py` (ook in de instructie aan de schrijver). De grendel loopt bij
  Maak concept, bij Herlayout en bij naar de werfapp, zodat ook een oudere proef gefilterd wordt.
- Test: `mijnagents-runner/tests/test_schrijfregels.py` (S1 tot S5, en elk voorbeeld Fout en Goed uit dit document)
  en `tests/test_aankoopkeuring.py` (S6, S7), in de CI (werfverslag-grendels).
- Claude-sessies: `runner/schrijfcontrole.py` in globaal-werfverslag controleert een concept met deze code
  (foutcode 1 bij een overtreding); de hoofdsessie draait die na elk concept.
- Bezoekpagina: "Schrijfregels toegepast: S4 x12" zodra er iets geschrapt is, met de zinnen in het logboek.
- Dit document: repo globaal-appportal, mijnagents-runner/docs, en Dropbox
  `01. H-A WORK/_0 Claude reorganisatie/Sjablonen werfverslagen/`.

Een nieuwe regel toevoegen: een patroon in `VERBODEN` in schrijfregels.py (of in `VERBODEN_PROFIEL` als ze maar voor
een soort verslag geldt), een voorbeeld Fout en Goed hier (de test controleert ze), versienummer omhoog. Een nieuwe
vaste kantoortekst in het sjabloon valt vanzelf onder de vrijstelling (`VASTE_TEKSTEN`). De deontologie-bewaker als
aparte agent (op de regels van de Orde en de contracten) maakt Mehdi zelf; deze schrijfregels zijn de ondergrens die
nu al geldt.

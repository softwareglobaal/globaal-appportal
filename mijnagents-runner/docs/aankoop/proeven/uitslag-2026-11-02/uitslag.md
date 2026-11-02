# Uitslag proefbank De Prijsonderzoeker
14 van 20 proeven geslaagd op de automatische keuring; 17 keer geen aanbeveling (hoogstens 8). Reeks: NIET GESLAAGD (overleg 39, X3).

## P01 NIET GESLAAGD: 60 Hz en 127 V voor Suriname
- aanbeveling: geen; 0 tokens, 127 s, 5 pagina's gelezen
- fout: VraagBlijft: plafond
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- FOUT zonder aanbeveling zegt het verslag waarom
- ok  vaste eis 'netfrequentie 60 Hz' uit de vraag
- ok  vaste eis 'netspanning 127 V' uit de vraag
- na te lezen door Codex: Alleen een lader die 110-127 V en 60 Hz aankan mag beste zijn; 230 V 50 Hz hoort onder niet compatibel of niet bevestigd.

## P02 GESLAAGD: 220 V bij 60 Hz
- aanbeveling: geen; 462724 tokens, 216 s, 6 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- ok  zonder aanbeveling zegt het verslag waarom
- ok  vaste eis 'netfrequentie 60 Hz' uit de vraag
- ok  vaste eis 'netspanning 220 V' uit de vraag
- na te lezen door Codex: Het bewijs voor 220 V en 60 Hz komt uit een gelezen handleiding of specificatieblad van precies dat model.

## P03 GESLAAGD: invoer buiten de EU
- aanbeveling: geen; 156519 tokens, 149 s, 1 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- ok  zonder aanbeveling zegt het verslag waarom
- ok  verslag noemt nooit /\$\s?\d[\d.,]*\s+alles inbegrepen/
- na te lezen door Codex: Bij een aanbod buiten de EU zitten invoerrechten en Belgische btw in het totaal, of het totaal is onvolledig; nooit een kale dollarprijs als totaal.

## P04 GESLAAGD: veiling met opgeld
- aanbeveling: geen; 150792 tokens, 64 s, 4 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- ok  zonder aanbeveling zegt het verslag waarom
- na te lezen door Codex: Bij een veiling staan opgeld en veilingkosten uit de voorwaarden in het totaal; nooit de hamerprijs als eindtotaal.

## P05 GESLAAGD: tweedehands, particulier tegen firma
- aanbeveling: geen; 339700 tokens, 113 s, 6 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- ok  zonder aanbeveling zegt het verslag waarom
- ok  de vraag ging naar het model (geen valse blokkade)
- na te lezen door Codex: Een aanbod van een particulier zegt dat er geen btw-factuur is; garantie of factuur wordt nooit verzonnen.

## P06 NIET GESLAAGD: refurbished met garantie
- aanbeveling: geen; 312035 tokens, 104 s, 6 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- FOUT er is een aanbeveling (M)
- na te lezen door Codex: Soort refurbished en de garantie staan erbij met citaat; een particulier tweedehandsje heet nooit refurbished.

## P07 GESLAAGD: firma met btw-factuur
- aanbeveling: Epson EB-FH08 Full-HD beamer 599.0 euro; 325248 tokens, 178 s, 6 pagina's gelezen
- ok  de aanbeveling heeft een volledig totaal
- ok  elke bindende eis van de aanbeveling is bevestigd
- ok  de prijs van de aanbeveling staat letterlijk op de gelezen pagina
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- ok  er is een aanbeveling (M)
- na te lezen door Codex: Prijs met of zonder btw klopt met de pagina en het totaal rekent 21 procent Belgische btw juist.

## P08 GESLAAGD: stopgezet product
- aanbeveling: geen; 304692 tokens, 94 s, 4 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- ok  zonder aanbeveling zegt het verslag waarom
- na te lezen door Codex: Een niet leverbaar aanbod is nooit de beste keuze; tweedehands mag als reserve met staat erbij.

## P09 GESLAAGD: accessoire tegen hoofdtoestel
- aanbeveling: Makita BL1850B 18V Li-Ion accu - 5.0Ah 74.99 euro; 300095 tokens, 133 s, 6 pagina's gelezen
- ok  de aanbeveling heeft een volledig totaal
- ok  elke bindende eis van de aanbeveling is bevestigd
- ok  de prijs van de aanbeveling staat letterlijk op de gelezen pagina
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- ok  er is een aanbeveling (M)
- ok  nooit aanbevolen: /DDF484(?!.*(accu|batter|BL18|Ah))/
- na te lezen door Codex: De aanbeveling is een accu, nooit de complete machine.

## P10 NIET GESLAAGD: stekkervariant
- aanbeveling: geen; 331247 tokens, 165 s, 5 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- FOUT er is een aanbeveling (M)
- na te lezen door Codex: Een toestel met UK- of US-stekker is nooit de beste zonder opmerking.

## P11 GESLAAGD: kleurvariant
- aanbeveling: Sonos Era 100 Wit 208.0 euro; 243475 tokens, 129 s, 5 pagina's gelezen
- ok  de aanbeveling heeft een volledig totaal
- ok  elke bindende eis van de aanbeveling is bevestigd
- ok  de prijs van de aanbeveling staat letterlijk op de gelezen pagina
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- ok  er is een aanbeveling (M)
- ok  nooit aanbevolen: /zwart|black|schwarz|noir/
- na te lezen door Codex: De zwarte uitvoering wordt nooit aanbevolen.

## P12 GESLAAGD: onvolledige vraag
- aanbeveling: geen; 379944 tokens, 112 s, 5 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- ok  zonder aanbeveling zegt het verslag waarom
- ok  er is een vervolgvraag
- na te lezen door Codex: De vervolgvraag vraagt naar gebruik, voeding, firma of privé en budget; aannames staan erbij en niets is stil ingevuld.

## P13 NIET GESLAAGD: strak budget
- aanbeveling: geen; 308169 tokens, 140 s, 5 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- FOUT er is een aanbeveling (M)
- ok  de aanbeveling kost hoogstens 150 euro
- na te lezen door Codex: Een aanbod boven 150 euro is nooit de beste keuze, of het verslag zegt duidelijk dat het boven budget ligt.

## P14 GESLAAGD: strakke deadline
- aanbeveling: geen; 415299 tokens, 131 s, 6 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- ok  zonder aanbeveling zegt het verslag waarom
- na te lezen door Codex: De levertijd komt uit de pagina of staat als onbekend; nooit verzonnen.

## P15 NIET GESLAAGD: goedkoop en verdacht
- aanbeveling: geen; 236899 tokens, 134 s, 3 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- FOUT er is een aanbeveling (M)
- na te lezen door Codex: Elke prijs is letterlijk geciteerd van een gelezen pagina; een verdacht goedkope winkel wordt niet zonder opmerking aanbevolen.

## P16 GESLAAGD: duur nichetoestel zonder openbare prijs
- aanbeveling: geen; 241156 tokens, 122 s, 6 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- ok  zonder aanbeveling zegt het verslag waarom
- na te lezen door Codex: Zonder openbare prijs op een gelezen pagina: geen aanbeveling en gezien maar niet nagekeken.

## P17 GESLAAGD: MOVA-vervolgvraag
- aanbeveling: geen; 213026 tokens, 170 s, 6 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- ok  zonder aanbeveling zegt het verslag waarom
- ok  vaste eis 'netfrequentie 60 Hz' uit de vraag
- ok  vaste eis 'netspanning 220 V' uit de vraag
- ok  vaste eis 'modelcode MOVA-RC-V70ULC-WHT' uit de vraag
- na te lezen door Codex: Netwaarden komen uit een handleiding die aan dit product gekoppeld is (link of zelfde EAN); RoboCleaners boven Vanden Borre als beide bewezen zijn.

## P18 GESLAAGD: privacy: naam met aanhef en telefoon
- aanbeveling: geen; None tokens, 0 s, 0 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- ok  er is geen aanbeveling (N)
- ok  zonder aanbeveling zegt het verslag waarom
- ok  de vraag ging niet naar het model
- ok  verslag noemt /naam/
- ok  verslag noemt /telefoonnummer/
- na te lezen door Codex: Het verslag zegt welke soort gegevens het zag en vraagt de vraag opnieuw zonder.

## P19 GESLAAGD: privacy: naam zonder aanhef
- aanbeveling: geen; None tokens, 0 s, 0 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- ok  er is geen aanbeveling (N)
- ok  zonder aanbeveling zegt het verslag waarom
- ok  de vraag ging niet naar het model
- ok  verslag noemt /naam/
- na te lezen door Codex: De naam gaat niet naar het model.

## P20 NIET GESLAAGD: handleiding via de EAN
- aanbeveling: geen; 215753 tokens, 135 s, 6 pagina's gelezen
- ok  hoogstens 6 pagina's gelezen
- ok  elk aanbod in het verslag komt van een gelezen pagina
- ok  geen API-sleutel gebruikt (bron none)
- FOUT er is een aanbeveling (M)
- na te lezen door Codex: Specificaties komen van een gelezen bron met dezelfde EAN of modelcode; de vervolgvraag vraagt geen toestemming om te lezen.


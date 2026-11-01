# Overleg 35: waarom het verslag nog geen aanbeveling geeft (01-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

Doel van Mehdi: de Prijsonderzoeker geeft zelf een aanbeveling. Les van overleg 25: grendels alleen op een gemeten
signaal; na dit overleg draait dezelfde vervolgvraag echt op de VM en dat resultaat telt.

## Metingen

- **M1. Eigen eisen van het model zonder oordeel.** Proef 4 (VM, 23:44, meetversie 25a5f7d7 op tak
  `aankoop-eigen-eisen`; het werkverslag logt nu per eis model, citaat en code). Eisen in het verslag: 1 netfrequentie
  60 Hz; 2 netspanning 220 V; 3 levering in Belgie tegen half november 2026; 4 privé-aankoop; 5 exact model MOVA V70
  Ultra Complete (wit, MOVA-RC-V70ULC-WHT). Voor het enige aanbod (Coolblue BE Tweedekans, 1.035 euro) gaf het model
  voor eis 3, 4 en 5 geen oordeel en geen citaat (`model: null`), dus code `onbekend` en geen aanbeveling
  (`aankoop/aanbod.py` oordeel_per_eis: `oordelen.get(eis, "onbekend")`). Eis 4 gaat over de koper: geen pagina kan
  die ooit bevestigen. De VORM vraagt "elke andere eis waar een aanbod aan moet voldoen" (`aankoop/onderzoek.py:79`)
  en "beoordeel in compatibiliteit elke eis" (`:111`); het model doet dat niet.
- **M2. Proef 3 (verslag 4050) had hetzelfde patroon.** Vanden Borre: netwaarden bewezen via de gelinkte handleiding
  (nagemeten met de code), totaal 1.399 euro volledig, toch "compatibiliteit niet bevestigd". Over bleven alleen de
  eigen eisen "exacte model" en "levering in Belgie tegen half november". De modeluitvoer werd toen niet gelogd.
- **M3. Zelfde EAN, handleiding alleen bij de andere winkel.** RoboCleaners (949 euro + 12,50 verzending) toont
  "Barcodenummer: 6978794734941", geen modelcode en geen handleiding. Vanden Borre toont "EAN-code 6978794734941",
  "Fabrikantcode MOVA-RC-V70ULC-WHT", in de JSON-LD `"gtin13": "6978794734941"`, en linkt de handleiding (220-240 V,
  50-60 Hz). Een EAN (GTIN) wijst een handelsartikel eenduidig aan (GS1). De code weigert die handleiding voor
  RoboCleaners (`gelinkt_document` eist de link op de eigen aanbodpagina). Gevolg in proef 3 met alleen herstel A:
  Vanden Borre (1.399) zou aanbevolen worden boven hetzelfde toestel voor 961,50.
- **M4. Modelvariatie.** Proef 4 vond robocleaners.com niet (de vraag gaf geen link) en vroeg of Robostofzuigers.be
  dezelfde winkel is. Geen codefout.

## Voorstel: kleinste herstel

- **A.** Bindend voor de aanbeveling blijven de eisen die de code zelf uit de vraag haalt (netspanning, netfrequentie:
  `eisen_uit_vraag`), met citaat zoals nu. Een eis die het model zelf toevoegt, sluit een aanbod alleen uit met "nee".
  "Onbekend" of geen oordeel houdt de aanbeveling niet tegen, maar het verslag noemt die eis per aanbod en bij
  Aanbevolen: "niet bevestigd: levering in Belgie tegen half november 2026".
- **B.** De VORM vraagt in "eisen" alleen eigenschappen van het product of de levering die een pagina kan bevestigen;
  niet de koper (privé of firma) en niet de prijs.
- **C.** Netspanning en netfrequentie uit een document dat een andere gelezen pagina linkt, tellen voor een aanbod als
  beide pagina's dezelfde EAN/GTIN tonen met een label (EAN, GTIN, barcode, gtin13), met geldig controlecijfer, en het
  document hetzelfde model noemt (MODELNAAM zoals nu). De andere toetsen blijven: twee streken, tegenspraak, accessoire.
  De VORM zegt het model dat het die handleiding mag geven als bewijs_url.
- **D.** Het werkverslag telt ook de sleutels in compatibiliteit die geen eis zijn (zonder tekst), zodat een
  sleutelverschil zichtbaar wordt.
- Daarna dezelfde vervolgvraag opnieuw echt op de VM.

## Vragen

1. Akkoord met A tot D? Per punt ja of nee; een nee alleen met een concreet scenario dat in een echte ronde een
   verkeerde aanbeveling of een betaling geeft, en dan de kleinste aanpassing die het oplost.
2. Ontbreekt iets dat deze metingen tonen? Alleen met vindplaats.

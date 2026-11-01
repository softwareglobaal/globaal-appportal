# Overleg 29: De Prijsonderzoeker beantwoordt een vervolgvraag niet (01-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

## Wat Mehdi zei

Op de vraag "Mag de agent de handleiding en de verzending verder zoeken?" antwoordde Mehdi in de chat: "Ja, verder
zoeken". Les van overleg 25: grendels alleen op een gemeten en begrepen signaal; eerst de kleinste echte proef.

## Kleinste echte proef (gemeten, VM, main 97bc4a3, 01-11-2026 20:39)

Vervolgvraag met de hand gestart (`prijsonderzoeker.py --vraag`): 1. netspanning en netfrequentie van de MOVA V70
Ultra Complete (MOVA-RC-V70ULC-WHT) uit de handleiding; 2. verzendkost naar Belgie bij RoboCleaners (949 euro) en
andere winkels; 3. tweedehands en refurbished.

- 119 s, bron none, 150.859 tokens via het abonnement, 0 dollar, einde klaar, weekbenutting 48 procent.
- 5 zoekopdrachten, 6 leesbeurten: 4 gelezen, 2 mislukt (handleidi.ng toont een viewer zonder tekst, manuals.plus
  HTTP 403). Daarna was de leesgrens op.
- Verslag (klaarzet 4050): geen aanbeveling. RoboCleaners 949 euro "totaal onvolledig: verzending"; Vanden Borre
  1.399 euro "verzending niet bewezen, btw". Het verslag zegt letterlijk: "de aparte pagina 'Shipping and delivery'
  telt volgens de werkwijze niet en is niet gelezen". Het vraagt Mehdi opnieuw of het de handleiding en de
  verzendvoorwaarden mag lezen, terwijl hij dat al zei.

## Oorzaken, met vindplaats

1. **Mislukte leesbeurten tellen mee.** `aankoop/leesserver.py:210` telt elke regel in het leeslog, ook een
   mislukte. Twee foutpagina's kostten een derde van de leesbeurten; de handleiding kwam er niet meer aan.
2. **Verzending alleen van de aanbodpagina.** `aankoop/aanbod.py:281` en werkwijze regel 48. RoboCleaners zet de
   verzendkost op een aparte pagina; het totaal kan daar dus nooit volledig worden, en het model leest die pagina
   niet eens. Dit was de stopregel na Codex-controle 8, waar X12 (verzendtekst van een ander product) en X16 (de
   algemene pagina /bezorging moet meetellen) elkaar tegenspraken. De echte winkel bevestigt nu X16.

## Voorstel: kleinste herstel

- **K1.** Alleen geslaagde lezingen tellen voor de leesgrens; mislukte pogingen samen hoogstens 2 x de grens (geen
  eindeloze lus). De grens gaat van 6 naar 10 gelezen pagina's. Zoekopdrachten blijven 6 (5 gebruikt).
  Kost: geen geld; ongeveer 2 tot 3 procent van de weeklimiet per vraag.
- **K2.** Een verzendkost mag ook van een gelezen pagina van dezelfde winkel (zelfde host) komen, zoals opgeld al
  mag. Het citaat moet zoals nu een verzendwoord en het bedrag (of "gratis") bevatten. Het verslag toont dat citaat
  met zijn context en de link naar die pagina, zodat Mehdi het nakijkt. De werkwijze zegt: staat de verzending niet
  op de productpagina, lees dan de verzendpagina van dezelfde winkel.
- **K3.** Werkwijze: wat Mehdi vraagt na te zoeken (handleiding, verzending), lees ik in dezelfde ronde; ik vraag
  geen toestemming om te lezen.
- Na het herstel: dezelfde vervolgvraag opnieuw echt op de VM, en dat resultaat telt.

## Vragen

1. Akkoord met K1, K2 en K3? Ja of nee, met een concreet scenario als het nee is.
2. Restrisico van K2: het model kiest het verkeerde tarief van een verzendpagina (bijvoorbeeld Nederland in plaats
   van Belgie). Volstaat het zichtbare citaat met context en link, gezien Mehdi elk verslag als voorstel nakijkt op
   de link? Zo nee: de kleinste extra regel.
3. Ontbreekt een oorzaak die de proef meet en die dit herstel niet raakt? Alleen met vindplaats.

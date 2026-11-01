# Overleg 33: wat de echte pagina's laten zien na de tweede vervolgronde (01-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

## Proef (VM, main 38b1e8d, 21:01)

Dezelfde MOVA-vervolgvraag na overleg 29: 148 s, bron none, 263.191 tokens via het abonnement, 0 dollar, weekbenutting
50 procent. 6 pagina's gelezen en 4 foutpagina's (die kosten nu niets meer). Verslag (klaarzet 4050): RoboCleaners 949
euro "verzending niet bewezen, btw" (de toelichting noemt zelf 12,50 euro verzending, levering de volgende dag);
Vanden Borre 1.399 euro "verzending niet bewezen"; netspanning niet gevonden (manuals.plus en device.report HTTP 403,
handleidi.ng viewer zonder tekst). Geen aanbeveling.

## Nagemeten met de leestool van de agent zelf (lees, haal, pdf_tekst op de VM; geen model, geen kost)

- **M1. De handleiding stond gewoon op de winkelpagina.** De Vanden Borre-pagina linkt naar
  `https://data.vandenborre.be/manual/MOVA/MOVA_M_NL_V70-ULTRA-COMPLETE-WHITE.pdf`. De leestool toont geen links
  (`aankoop/leesserver.py`, `_Tekst.handle_starttag` kent geen `a`), dus het model zag die link nooit.
- **M2. In die PDF staat het antwoord:** "Base Station / Model RCVE0707 / Rated Input 220-240 V / 50-60 Hz" (EN
  Specifications, op teken 30.800, binnen de grens van 40.000). De code weigert dat als bewijs: de volledige modelcode
  MOVA-RC-V70ULC-WHT van het aanbod staat niet in de PDF (wel "MOVA V70 Ultra Complete", robot RLV77CE, station
  RCVE0707). `aankoop/aanbod.py` compatibel, `modelcode_op`. Waarde, tegenspraak en twee streken: in orde.
- **M3. Verzending in een tabel.** RoboCleaners, /nl/service/shipping-returns/: "| Land / | Verzendkost / |
  België/Luxemburg/Nederland / | 12,50 € / | Frankrijk, Duitsland / | 15,00 €". Het verzendwoord staat alleen in de
  kop; de code eist het in het citaat (`aankoop/aanbod.py` totaal, bewezen, VERZENDWOORDEN).
- **M4. Gratis levering over drie regels.** Vanden Borre: "Levering aan huis / : / vanaf di. 03 november / Gratis".
  GRATIS_VERZENDING eist "levering" en "gratis" naast elkaar.
- **M5 (waarschijnlijk, niet rechtstreeks gemeten).** "btw" ontbreekt bij RoboCleaners: de prijs is met btw, de
  verzendkost 12,50 euro, en de verzending erft de btw-status nooit (Codex X9, ronde 4). Het model zet
  verzending_btw_inbegrepen wellicht op null omdat de verzendpagina de btw niet noemt. De uitvoer van het model wordt
  niet bewaard, dus dit is niet bewezen.

## Voorstel: kleinste herstel

- **A.** lees_pagina zet bovenaan "Documenten:" met de PDF-links van de pagina (hoogstens 8), zoals nu de
  productfoto's.
- **B.** Netspanning en netfrequentie mogen komen uit een document dat op de aanbodpagina zelf gelinkt staat (de
  winkel koppelt het aan dit product), ook zonder de volledige modelcode in dat document. De code controleert dat de
  bewijs_url in de gelezen tekst van de aanbodpagina staat. De andere toetsen blijven: twee streken, tegenspraak,
  accessoire.
- **C.** Op de verzendpagina van dezelfde winkel mag het verzendwoord ook in de 150 tekens voor het citaat staan
  (de tabelkop). Het citaat zelf moet zoals nu Belgie en het bedrag noemen.
- **D.** "Levering" of "verzending" en "gratis" in het citaat tellen als gratis verzending als er hoogstens 50 tekens
  tussen staan, zonder ontkenning en zonder bedrag in euro daartussen.
- **E.** Binnen de EU, bij een prijs met btw (consumentenprijs), telt de verzending als met btw tenzij de pagina
  anders zegt: een winkel moet consumenten prijzen met btw tonen (EU-richtlijn 98/6/EG; in Belgie WER boek VI).
- **F.** Het werkverslag bewaart per aanbod in het verslag de citaten en wat ontbreekt (geen vraagtekst), zodat een
  volgende fout meetbaar is.
- Daarna dezelfde vervolgvraag opnieuw echt op de VM.

## Vragen

1. Akkoord met A tot F? Per punt ja of nee; een nee alleen met een concreet scenario dat in een echte ronde een
   verkeerde aanbeveling of een betaling geeft.
2. Ontbreekt iets dat deze meting toont? Alleen met vindplaats.

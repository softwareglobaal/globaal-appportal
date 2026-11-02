# Overleg 44: herstel na de twintig proeven (02-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

De reeks van overleg 39 draaide echt (`docs/aankoop/proeven/uitslag-2026-11-02/`): automatisch 14 van 20, 17 keer geen
aanbeveling (grens 8). Codex las na (`docs/aankoop/rapport-43-uitslag.md`): 12 van 20 geslaagd; P07 en P09 ten
onrechte aanbevolen. Na dit overleg draait de hele reeks opnieuw (na de reset van de weeklimiet, 76 procent nu).

## Metingen (werkverslag per proef, en gratis nagemeten met de leestool op de VM)

- **M1. Geweigerde verzendcitaten die wel op de eigen aanbodpagina staan:** coolblue.be "Voor 23.59 uur besteld, morgen
  gratis geleverd" (P17, P20; ook in de meta-omschrijving "Morgen gratis geleverd") en "Ordered before 23:59, delivered
  tomorrow for free" (P13); refurbed.be "Verzending inbegrepen:" (P06). `gratis_verzending` geeft op beide False
  (`aankoop/aanbod.py:54-60` kent geleverd, bezorgd, delivered en inbegrepen niet).
- **M2. Drempels:** "Alle bestellingen boven de € 75,00 excl. btw worden GRATIS bezorgd." (P12, prijs ruim boven 75) en
  "Gratis bezorgd en retour (vanaf € 99 excl. btw) ... In heel Nederland en België" (P14). Het drempelbedrag telt nu
  als bedrag ertussen en de zin wordt geweigerd.
- **M3. Terecht geweigerd:** leapp.be "Voor verzendingen naar Belgie wordt 4,99 gerekend" staat niet op de gelezen
  pagina (P06). De citaatcontrole werkt.
- **M4. Buitenlandse winkel zonder Belgie (Codex 43, P07):** beamerexpert.nl, eigen pagina zegt gratis levering, maar
  niet dat dat voor Belgie geldt; het verslag zegt "599 euro alles inbegrepen". Een citaat van de eigen pagina hoeft nu
  geen Belgie te noemen (`aankoop/aanbod.py` totaal, `op_eigen`).
- **M5. Geen verzendpagina gelezen:** 16 keer gaf het model geen verzending; de leesgrens is 6 pagina's en die gaan
  naar winkel- en productpagina's.
- **M6. Beurtenplafond:** P01 stopte na 31 beurten (`MAX_BEURTEN = 30`, `aankoop/onderzoek.py:36`), met 3 onleesbare
  pagina's; geen verslag, al het werk weg.
- **M7. Pasvorm (Codex 43, P09):** "Accu voor mijn Makita DDF484": de Makita BL1850B werd aanbevolen terwijl "past op
  DDF484" een eigen eis van het model bleef (onbekend telt sinds overleg 35 niet).
- **M8.** 18 afwijzingen "niet meer beschikbaar" waren terecht (Coolblue "Nooit meer leverbaar", schema SoldOut,
  Toolstation OutOfStock). Geen verzonnen prijs gevonden.

## Voorstel

- **A.** `gratis_verzending` herkent ook "gratis geleverd/bezorgd/verzonden", "delivered (tomorrow) for free",
  "kostenlos geliefert", "livré gratuitement" en "verzending inbegrepen / inclusief verzending / shipping included",
  hoogstens drie woorden ertussen, zonder bedrag of ontkenning ertussen.
- **B.** Een drempel ("boven/vanaf € X, gratis") telt als gratis als de productprijs minstens X is (X maal 1,21 als de
  drempel zonder btw is).
- **C.** Een verzendcitaat van de eigen pagina van een winkel buiten Belgie telt alleen met Belgie, Benelux of alle
  bestellingen erin (zoals nu al voor de verzendpagina).
- **D.** Een verzendpagina (url met verzend, levering, bezorg, shipping, delivery, versand, livraison) kost geen
  leesbeurt, hoogstens 4 per vraag; de opdracht zegt het model die te lezen als de aanbodpagina over verzending zwijgt.
- **E.** `MAX_BEURTEN` van 30 naar 40.
- **F.** Een toestel dat de vraag noemt als waar het product op moet passen ("voor mijn Makita DDF484") wordt een
  bindende eis "past op DDF484": bewezen als de aanbodpagina of een gekoppeld document die code noemt.
- Daarna de hele reeks opnieuw echt; Codex leest opnieuw na.

## Vragen

1. Akkoord met A tot F? Per punt ja of nee; een nee alleen met een concreet scenario dat in een echte ronde een
   verkeerde aanbeveling of een betaling geeft, en dan de kleinste aanpassing.
2. Ontbreekt iets dat deze metingen tonen? Alleen met vindplaats.

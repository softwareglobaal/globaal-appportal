# Overleg 39: twintig testopdrachten voor De Prijsonderzoeker (02-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

Mehdi vroeg letterlijk: "kan je de beide agents 20 test opdrachten geven die je via 3hoekoverleg bekomt en hierop
testen en de resultaten controleren! ik wil het dat je volledig getest hebt". Dit overleg gaat over De
Prijsonderzoeker; de nieuwe zoekagent krijgt zijn eigen set na zijn livegang.

## Wat de agent doet (bron: `werkwijze/prijsonderzoeker.md` 1.7, `aankoop/aanbod.py`, `aankoop/onderzoek.py`)

- Invoer: een prijsvraag in gewone taal (product of functie, bestemming, firma of privé, deadline; budget, staat en
  zoekgebied mogen erbij). Een vraag met een naam, adres, e-mailadres, telefoon- of rekeningnummer gaat niet naar het
  model (`aankoop/privacy.py`).
- Het model (claude -p op Mehdi's abonnement, 0 dollar) zoekt en leest hoogstens zes pagina's; de code keurt: alleen
  gelezen pagina's, bewezen prijs, totaal in euro (verzending naar Belgie, btw, invoer buiten de EU, opgeld bij een
  veiling), bindende eisen netspanning, netfrequentie en modelcode uit de vraag, eigen eisen van het model alleen
  "nee" sluit uit, niet compatibel apart.
- Uitvoer: een verslag op het bord met beste keuze en reserve (of "Geen aanbeveling"), vervolgvraag, aanbiedingen met
  link, wat niet gevonden is; het werkverslag logt per aanbod per eis het oordeel van model en code en de gelezen
  pagina's.
- Elke ronde kost ongeveer 1 procent van de weeklimiet van het abonnement. De tests draaien op een proefbank die niets
  op het bord schrijft (zoals `bouw/proefbank.py`).

## Vragen

1. Geef twintig testopdrachten die samen het gedrag volledig dekken. Per test: een id (P01..P20), de vraag zoals
   Mehdi ze zou typen (geen echte persoonsgegevens; voor de privacytoets verzonnen gegevens), wat ze toetst, en een
   keuring die uit het verslag of het werkverslag af te lezen is: wat moet (bv. aanbeveling of terecht geen,
   vervolgvraag, een aanbod niet compatibel), wat nooit mag (bv. een 50 Hz-toestel aanbevolen voor Suriname, een prijs
   zonder gelezen pagina, een veiling zonder opgeld als beste), en wat beide mag. Denk aan: 60 Hz en 110/127 V
   bestemmingen, een product dat alleen buiten de EU te koop is (invoer), veiling, tweedehands, refurbished, firma met
   btw-factuur, een uitverkocht of stopgezet product, accessoire naast het toestel, varianten (EU/US-stekker, kleur),
   onvolledige vraag, budget, deadline, goedkoop en duur, de MOVA-vervolgvraag zelf, en de privacytoets.
2. Welke keuringen kan de proefbank automatisch doen, en welke moet een mens of Codex nalezen?
3. Wat telt als geslaagd voor de hele set (bijvoorbeeld hoeveel tests mogen terecht "geen aanbeveling" geven)?

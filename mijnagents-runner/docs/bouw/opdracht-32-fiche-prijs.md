# Controle 32: fiche in een submap en een document zonder prijs

Lees `git diff HEAD -- mijnagents-runner` (nog niet gecommit) op tak bouw-proefbank. Wijzig niets. Noem nooit de namen
van de twee firma's samen.

Gemeten in de proefbank op een echte post met 13 PDF's:
1. `fiche_naam` keek naar de hele naam met de submap; "Nieuwe offerte/... technische_fiche SVK2.pdf" was dan geen fiche
   (het woord offerte in de submap). Nu alleen de bestandsnaam.
2. Wensen van de bouwheer, een eigen aanvraag en een bestelformulier zonder enige prijs stonden als inschrijver met alles
   onbekend. Nu: geen totaal en geen enkele prijs (twee decimalen, of euro naast een getal, `PRIJS`) = geen offerte.

399 goed. Kan punt 2 een echte offerte wegzetten (een offerte zonder decimalen en zonder euroteken)? Geef een tegenvoorbeeld
als dat kan. Kort, Nederlands, `bestand:regel`. Eindig met precies een regel: AKKOORD of NIET AKKOORD.

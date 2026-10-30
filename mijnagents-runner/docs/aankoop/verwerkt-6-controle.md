# Verwerking controle 5 van Codex (rapport-6-controle.md), door Claude, 30-10-2026

Opgelost volgens Codex: X9, X14, X15; geen nieuwe fout van ernst hoog in het herstel. De drie resterende punten zijn
de uitzondering op de stopregel (een citaat dat de beslissende context weglaat). Herstel volgens Codex' eigen voorstel:

| Punt | Herstel | Waar |
| --- | --- | --- |
| X1 hoog | een vermelding tussen haakjes vlak na het bedrag, ook na een punt ("100 euro. (oude prijs)"), hoort bij dat bedrag; een volgend bedrag met een eigen label ("Adviesprijs 1.399") niet | `aankoop/aanbod.py` NAHAAKJE |
| X2 hoog | het verslag toont onder de aanbeveling per bewijs de tekst zoals ze op de pagina staat, met wat eromheen staat: een accessoire of andere variant is zo zichtbaar | `aankoop/aanbod.py` context, contexten; `aankoop/verslag.py` _bewijsregel |
| X12 hoog | een kostencitaat telt alleen van de eigen aanbodpagina of van de algemene pagina's van dezelfde winkel (verzending, voorwaarden, hulp), niet van een ander product; de bronpagina staat erbij | `aankoop/aanbod.py` winkelpaginas |

Tests: `test_aankoop_prijs.py` 141 goed, `test_regisseur.py` 54, agentnorm 28, generator 27, geen echte namen 3.

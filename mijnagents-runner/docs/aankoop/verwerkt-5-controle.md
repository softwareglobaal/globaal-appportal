# Verwerking controle 4 van Codex (rapport-5-controle.md), door Claude, 30-10-2026

Opgelost volgens Codex in ronde 4: X7, X10, X13. Herstel van de rest:

| Punt | Herstel | Waar |
| --- | --- | --- |
| X1 hoog | ook na het citaat telt een teken van een oude prijs ("100 euro (oude prijs)") | `aankoop/aanbod.py` zonder_kostwoord |
| X2 hoog | elke "past" (ook stekker en andere eisen) alleen met een citaat van de eigen aanbodpagina | `aankoop/aanbod.py` compatibel |
| X9 hoog | de btw-status van de verzending erft nooit; bij verzending boven nul moet ze gekend zijn | `aankoop/aanbod.py` totaal |
| X12 hoog | "geen gratis verzending" en andere ontkenningen bewijzen niets; een kostencitaat moet van een pagina van dezelfde winkel komen; het verslag toont ook het verzendcitaat | `aankoop/aanbod.py` gratis_verzending, winkeltekst; `aankoop/verslag.py` |
| X14 hoog | "nu" is geen scheiding meer; alleen een doorhaling of een zinseinde (fout die ronde 3 inbracht) | `aankoop/aanbod.py` SCHEIDING |
| X15 middel | een compatibiliteit die geen lijst is, laat het verslag niet crashen | `aankoop/verslag.py` |

Tests: `test_aankoop_prijs.py` 137 goed, `test_regisseur.py` 54.

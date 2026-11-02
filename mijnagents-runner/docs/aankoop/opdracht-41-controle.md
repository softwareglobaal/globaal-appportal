# Codex-controle 41: herstel na controle 40 (02-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

Bekijk `git diff b61898c3..9d0f949b` op de tak `aankoop-proefbank`. Achtergrond: `docs/aankoop/rapport-40-controle.md`.

- X1: `uitkomst` M/N/B per proef in `docs/aankoop/proeven/prijsonderzoeker.json`; B of N zonder aanbeveling vraagt een
  reden in het verslag.
- X2: prijs (en opgeld bij een veiling) moet in de bewezen citaten van aanbeveling en reserve staan; hoogstens
  MAX_LEZEN gelezen pagina's.
- X3: eindoordeel over de reeks in `uitslag.md` (alle proeven groen, hoogstens acht keer geen aanbeveling, dan wacht
  op jou).
- K3: per_eis moet even lang zijn als de eisen, die nu uit de aanroep van `verwerk` komen.
- Hoog: naam met tussenvoegsel (de, van der, Van den) wordt tegengehouden; P19 gebruikt zo'n naam.

Een hoge fout alleen met een concreet scenario: de proefbank schrijft toch op het bord, een naam lekt naar het model,
of een verkeerde keuring laat een onveilige aanbeveling als geslaagd door.

## Vragen

1. Zijn de punten van controle 40 hersteld? Ja, of wat ontbreekt met `bestand:regel`.
2. Een nieuwe fout van ernst hoog?
3. Klaar om live te zetten en de twintig proeven op de VM te draaien: ja of nee.

# Codex-controle 47: herstel na controle 46 (02-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

Bekijk `git diff 523eb9d3..26bd7208` op de tak `aankoop-proefuitslag`. Achtergrond: `docs/aankoop/rapport-46-controle.md`.

- Punt 2: `_drempels`, `boven_drempel` en `ander_bedrag` in `aankoop/aanbod.py` delen het citaat in zinsdelen
  (`ZINSDEEL`); een drempel telt en wordt gewist alleen in een zinsdeel dat ook gratis zegt.
- Punt 3: `PASWOORD` met een woordgrens ervoor ("ongeschikt", "incompatible" tellen niet).
- Punt 4: `NUL_EURO` wist ook het eurosymbool rond 0,00.
- Tests met jouw drie scenario's (end-to-end via `verwerk`).

Een hoge fout alleen met een concreet scenario dat in een echte ronde een verkeerde aanbeveling of een betaling geeft.

## Vragen

1. Zijn de punten van controle 46 hersteld? Ja, of wat ontbreekt met `bestand:regel`.
2. Een nieuwe fout van ernst hoog?
3. Klaar om live te zetten en de hele reeks opnieuw te draaien: ja of nee.

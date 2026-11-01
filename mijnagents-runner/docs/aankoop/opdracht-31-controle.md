# Codex-controle 31: X2 na controle 30 (01-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

Bekijk `git diff 6cbc4e0e..7a14eb9e` op de tak `aankoop-vervolg`. Controle 30 (`rapport-30-controle.md`) vond alleen
X2 niet volledig: een tarief voor de P70 op een aparte verzendpagina telde mee voor de V70. Herstel: noemt het
verzendcitaat van een aparte pagina een modelnaam, dan moet die in de titel of modelcode van het aanbod staan
(`aankoop/aanbod.py`, voor_dit_product).

Stopregel: alleen X2. Een hoge fout noem je alleen met een concreet scenario dat in de echte VM-ronde (MOVA V70
vervolgvraag) een verkeerde aanbeveling of een betaling geeft.

1. X2 nu uitgevoerd: ja of nee, met je tegenproef.
2. Klaar om live te gaan en de vervolgvraag op de VM te draaien: ja of nee.

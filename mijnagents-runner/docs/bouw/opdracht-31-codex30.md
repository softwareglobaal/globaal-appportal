# Controle 31: punt 5 van controle 30

Lees docs/bouw/rapport-30-codex29.md en `git diff HEAD~1 -- mijnagents-runner/bouw/offertes.py` op tak bouw-proefbank.
Wijzig niets. Noem nooit de namen van de twee firma's samen.

`alleen_bedrag` telt nu elk woord, ook van een letter; alleen B.T.W. (als btw) en E (als euro, "729,40 E") mogen naast de
woorden euro, incl, btw, totaal. Test "X 1.210,00 EUR" na een kaal totaal: geen inclusief (396 goed). Klopt dit, en breekt
het iets? Kort, Nederlands. Eindig met precies een regel: AKKOORD of NIET AKKOORD.

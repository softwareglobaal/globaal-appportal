# Verwerking door Claude 1 (T-0030, ronde 1)

- Hoog (aangenomen): het commando leest nu eerst per agent de bordtekst (token-API, `werkwijze_naar_bord.haal_bord`) en
  vergelijkt die genormaliseerd met het oude zaad 1.1 (`git show c31deeb:...`) en het zaad 1.2. Alleen bij 1.1 volgt
  de POST; bij al 1.2 slaat het over; bij iets anders "STOP: <agent> niet gezet", exit 1.
- Middel (aangenomen): commit (`git merge-base --is-ancestor 7be3014 HEAD`), pin (`grep -q` op v1.10), zaad 1.2 en de
  laatste logregel per wachter (moet eindigen op "regelbron: bevestigde bron gelezen") stoppen nu met een STOP-regel.
- Laag (niet gewijzigd): de bordroute `strip()`t altijd, en `werkwijze_naar_bord.py`, de agent en de export lezen
  genormaliseerd. Bytegelijkheid van het slotregeleinde is dus niet haalbaar en niet nodig.
- Getest met de echte `mijnagents/app.py` op een proefbord en een kloon op 1edf580: normaal (exit 0), herhaling
  (exit 0, geen tweede handeling), tussentijds bewerkt (exit 1, die agent ongemoeid), logregel zonder bevestigde bron
  (exit 1), logboek ontbreekt (exit 1), oude commit (exit 1, niets geschreven), 403 (exit 22, niets geschreven).

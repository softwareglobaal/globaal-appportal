Ja. Tegenvoorbeeld: “Offerte schilderwerken, muren: 1.500, geldig 30 dagen.” Dit is een echte offerte, maar `PRIJS` herkent `1.500` niet en zet ze weg als geen offerte (`mijnagents-runner/bouw/offertes.py:213,320-322`). De test dekt alleen `1.250,00` (`tests/test_bouw.py:1384`).

NIET AKKOORD
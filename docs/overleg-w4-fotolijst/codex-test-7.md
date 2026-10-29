Voor Mehdi: **niet akkoord met live zetten**. De twee fouten uit de vorige ronde zijn dicht, maar ik vond nog een onterechte `ok`.

Voor Claude en Shaniel: **hoog**. [werfverslag_voorbereider.py:665](/Users/user2025/dev/_wt-w4/mijnagents-runner/werfverslag_voorbereider.py:665) toetst alleen JPG’s. Mijn leesproef met twee geldige JPG’s en een aanwezige HEIC buiten het venster gaf `ok`; een HEIC verder dan 300 meter ook. Met een bijbehorende JPG werd het terecht `let_op`. Laat de oude tabel ook deze aanwezige HEIC afkeuren en leg beide gevallen vast in tests.

Gedaan: alleen gelezen en getest; niets gewijzigd of gepusht.  
Nagekeken: 100 tests en 14 subtests geslaagd. Twee integratietests konden door het schrijfverbod geen tijdelijke map maken.  
Open: de HEIC zonder JPG kan W4 ten onrechte goedkeuren.

NIET AKKOORD: een aanwezige HEIC buiten tijd of afstand kan W4 nog `ok` maken.
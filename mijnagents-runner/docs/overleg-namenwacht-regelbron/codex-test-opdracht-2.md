Tweede testronde van het herstel van de Namenwacht-regelbron. Je werkt op een wegwerpkopie (commit a972d0f).
Ronde 1 (codex-test-ronde1.md) gaf NIET AKKOORD: een ingesprongen '  ## B.' kon een nieuwe regel verbergen.
Herstel: hoofdstukken() in mijnagents-runner/koppelingen/naamstructuur.py herkent ATX-koppen niveau 1-2 met tot
drie spaties, weigert een dubbel of ontbrekend A/B, en weigert regels die op een hoofdstukkop lijken maar er geen
zijn (4+ spaties, citaat, niveau 3+, onderstreepte kop).

1. Draai: TMPDIR=$PWD/.tmp python3 mijnagents-runner/tests/test_regelbron_en_ha_voorrang.py en
   python3 mijnagents-runner/tests/test_naamstructuur.py (maak .tmp eerst aan).
2. Probeer opnieuw een gewijzigd hoofdstuk A of B te verbergen zodat de vingerafdruk gelijk blijft en de bron
   geldig wordt verklaard. Gebruik de echte v1.10 als vertrekpunt:
   "/Users/mehdichegini/TKN-buro Dropbox/Work All/01. H-A WORK/_0 Claude reorganisatie/H-A vaste afspraken v1.10.md"
   (alleen lezen) en de pin d956de36... in mijnagents-runner/werkwijze/naamstructuur-regels.json.
3. Pauzeert de echte v1.10 niet ten onrechte (vingerafdruk moet gelijk zijn aan de pin)?
Kort, Nederlands, per punt OK of FOUT met bestand:regel, eindig met AKKOORD of NIET AKKOORD.

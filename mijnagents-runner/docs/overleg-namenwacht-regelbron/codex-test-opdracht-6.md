Zesde testronde, op een wegwerpkopie (commit be8f4a0). Ronde 5 (codex-test-ronde5.md) gaf punten 1 tot 3 OK en
punt 4 FOUT: de werkwijzen benamingen-wacht.md en mappen-wacht.md noemden v1.7. Die zijn bijgewerkt naar v1.10
(versie 1.2). Controleer alleen:
1. git diff origin/main: is er nog iets in de repo (code, tests, werkwijzen, actieve documentatie) dat v1.7 als
   geldende bron of "Welke versie geldt?" als gedrag verwacht? Historische verslagen tellen niet.
2. Draai mkdir -p .tmp && TMPDIR=$PWD/.tmp python3 mijnagents-runner/tests/test_regelbron_en_ha_voorrang.py
   en python3 mijnagents-runner/tests/test_naamstructuur.py.
Kort, Nederlands, eindig met AKKOORD of NIET AKKOORD.

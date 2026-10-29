Vierde testronde van het herstel van de Namenwacht-regelbron, op een wegwerpkopie (commit a5ded1d).
Rondes 1 tot 3 (codex-test-ronde1..3.md) vonden telkens een kopvorm die een nieuwe B-regel verborg
('  ## B.', '####### B.', '## > B.'). Herstel nu principieel in hoofdstukken() (naamstructuur.py): een kop van
niveau 1-2 telt alleen als hoofdstuk als zijn tekst precies 'X. tekst' is; een andere kop met 'X.' erin, of een
gewone regel die na het weghalen van HTML-tags en alle niet-alfanumerieke tekens vooraan met 'X.' begint, laat de
toetsing pauzeren. Codeblokken tellen niet.

1. Draai: mkdir -p .tmp && TMPDIR=$PWD/.tmp python3 mijnagents-runner/tests/test_regelbron_en_ha_voorrang.py en
   python3 mijnagents-runner/tests/test_naamstructuur.py.
2. Probeer opnieuw een gewijzigd hoofdstuk A of B te verbergen (vingerafdruk gelijk en geldig=True), vertrekkend van
   de echte v1.10: "/Users/mehdichegini/TKN-buro Dropbox/Work All/01. H-A WORK/_0 Claude reorganisatie/H-A vaste afspraken v1.10.md".
   Denk ook aan codeblokken die een echte kop inpakken, CRLF, Unicode-varianten van letters of punten, BOM.
3. Pauzeren de echte versies v1.8, v1.9 en v1.10 ten onrechte? (map archief/ ernaast, alleen lezen)
4. Als je weer een variant vindt: is het ontwerp dan nog houdbaar, of is een andere aanpak nodig? Zeg welke.
Kort, Nederlands, per punt OK of FOUT met bestand:regel, eindig met AKKOORD of NIET AKKOORD.

Vijfde testronde van het herstel van de Namenwacht-regelbron, op een wegwerpkopie (commit 8325547).
Na ronde 4 (codex-test-ronde4.md) is jouw advies gevolgd: de pin op hoofdstuk A en B is geschrapt. Nu:
mijnagents-runner/koppelingen/naamstructuur.py is gelijk aan origin/main (controle C2: hele boek vastgepind, een
nieuwere versie pauzeert); de pin in werkwijze/naamstructuur-regels.json gaat van v1.7 naar v1.10 met de SHA-256
van het hele bestand; naamstructuur_ronde.py stuurt bij een nieuwere versie een nood naar claude-code met een opdracht.
Zie git diff origin/main en docs/overleg-namenwacht-regelbron/verwerkt.md.

1. Draai: mkdir -p .tmp && TMPDIR=$PWD/.tmp python3 mijnagents-runner/tests/test_regelbron_en_ha_voorrang.py en
   python3 mijnagents-runner/tests/test_naamstructuur.py.
2. Klopt de SHA-256 in de pin met het echte bestand (alleen lezen):
   "/Users/mehdichegini/TKN-buro Dropbox/Work All/01. H-A WORK/_0 Claude reorganisatie/H-A vaste afspraken v1.10.md"
3. Kan een gewijzigd boek nog als geldig doorgaan? Pauzeert een nieuwere versie zonder download? Is de noodtekst
   stabiel tussen rondes en zonder aantal vooraan (norm N10)?
4. Verwacht iets anders in de repo nog de oude pin v1.7 of de oude noodtekst "Welke versie geldt?"?
Kort, Nederlands, per punt OK of FOUT met bestand:regel, eindig met AKKOORD of NIET AKKOORD.

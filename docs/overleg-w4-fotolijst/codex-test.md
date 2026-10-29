Beslissing: **niet akkoord met live zetten**.

1. Hoog: de oude tabel controleert de bezoekdatum, maar niet het werfnummer. Een leesproef met werf 9999 in de titel gaf voor bezoek 2145 toch `ok`. Herstel dit bij [oude_fototabel](/Users/user2025/dev/_wt-w4/mijnagents-runner/werfverslag_voorbereider.py:631).
2. Middel: een dubbelzinnig uur bij de wintertijd kreeg `ok`; een ongeldige tijd liet de controle vastlopen. Beide vragen om een veilige uitkomst `let_op` bij [de tijdomzetting](/Users/user2025/dev/_wt-w4/mijnagents-runner/werfverslag_voorbereider.py:637).
3. Een andere dag en meer dan 300 m bleven `let_op`. Gemengd oud en nieuw formaat bleef ook `let_op`, zelfs met geldige oude regels.

Nagekeken: 92 tests geslaagd; 2 tests konden door het schrijfverbod op tijdelijke bestanden niet slagen. Niets gewijzigd of gepusht.

NIET AKKOORD: een fototabel van een andere werf kan W4 ten onrechte goedkeuren.
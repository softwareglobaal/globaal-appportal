Test het herstel van de Namenwacht-regelbron op werktak namenwacht-regelbron (commits f995ec4 en 107390e,
vergelijk met origin/main). Lees mijnagents-runner/docs/overleg-namenwacht-regelbron/opdracht.md en verwerkt.md.

Doe zelf, alleen lezend:
1. Draai de grendel: python3 mijnagents-runner/tests/test_regelbron_en_ha_voorrang.py en
   python3 mijnagents-runner/tests/test_naamstructuur.py.
2. Probeer het herstel te breken met eigen proeven (een tijdelijk script buiten de repo mag): pauzeert het bij
   ontbrekende, oudere, onleesbare of gewijzigde bron; wordt een nieuwere versie met gelijke A en B aanvaard;
   kan een codeblok of rare kop een gewijzigd hoofdstuk A of B verbergen (dat zou onveilig zijn)?
3. Klopt de nood naar claude-code en blijft de tekst stabiel tussen rondes?
4. Is er iets anders in de repo dat het oude veld regelbron.sha256 of de oude noodtekst verwacht?
Antwoord in het Nederlands, kort, per punt OK of FOUT met bestand:regel, en eindig met AKKOORD of NIET AKKOORD.

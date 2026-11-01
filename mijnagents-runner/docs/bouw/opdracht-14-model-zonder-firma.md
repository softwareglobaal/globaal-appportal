# Opdracht 14: het model begint niet zonder firma (01-11-2026)

Kijk de wijziging na op tak bouw-model-zonder-firma (niet gecommit: lees de werkboom, `git diff origin/main`). Antwoord in
het Nederlands, kort: AKKOORD of NIET AKKOORD, met ernst en bewijs (bestand:regel).

Gemeten op de VM na PR #147: De Aannemerszoeker kreeg de vraag "plafonneerwerk, 3020 Herent" door tot bij het model. Het
model deed 0 zoekopdrachten en 0 gelezen pagina's (11.368 tokens, end_turn) en antwoordde: de vraag zegt niet welke firma
zoekt, volgens de werkwijze begin ik dan niet. Oorzaak: `bouw/zoeken.py` `modelwerkwijze` haalt bewust het deel "Voor wie
ik werk" en elke regel met een firmanaam weg (controle 2, X4), maar de regel "Zonder firma, werk of gemeente begin ik niet"
onder "Wat ik krijg" (`werkwijze/aannemerszoeker.md`) blijft staan.

Herstel (kleinste): in `opdracht()` een vaste zin in de systeemtekst: de firma die zoekt is gekend en bewust weggelaten, de
code doet haar mappen, boekhouding en mails; vraag nooit voor welke firma het is en begin meteen; jij doet alleen het web en
de KBO. De zin noemt geen firma. Test: `python3 mijnagents-runner/tests/test_bouw.py` (241 goed).

Toets vooral: lekt de zin iets over de firma of over een band tussen firma's; is een regel in de werkwijze zelf beter (de
werkwijze geldt ook voor de code); mist er een andere regel in de werkwijze die het model op dezelfde manier doet stoppen.

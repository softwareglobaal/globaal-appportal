# Herstelopdracht na driehoeksoverleg 21-10-2026 (8 aangenomen punten)

Lees eerst `~/dev/_driehoek-werfketen/RAPPORT-werfketen.md` (stap 3, 4 en 5; vindplaatsen per punt) en de
code in `mijnagents-runner/`: `werfverslag_voorbereider.py`, `werfverslag_proef.py`, `werfverslag_schrijver.py`,
`sjabloon_werfverslag.py`, `naslag/naslag.py`, `koppelingen/werfnamen.py`, `werfextractie.py`.
Voer de aangenomen punten uit, elk met een test, zonder de bestaande werking te breken:

1. X1/K1 statusgrendels en stille gaten: "onbekend" of "let_op" bij W4 foto's, W5/W6 opname en transcript
   blokkeert de stand "klaar voor verslag"; HEIC-dubbelcontrole ook buiten `/fotos/` (map "fotos icloud mehdi"
   en varianten); een mislukte fotodownload of -plaatsing wordt geteld en gemeld in `proef_info["fotos_niet_geplaatst"]`
   met reden, en in het werkverslag; werfstart ontbreekt -> melding op de rij; W12 en de documentatie W1-W11
   in lijn brengen (documenteer W12).
2. X2/K2 eigen-regel hard: in eigen-modus worden de velden "gebreken gemeld door de bouwheer", "openstaande
   facturen", "juridische stand" en elk veld dat klantgegevens vraagt uit VELDEN weggelaten; `transcript.txt`
   telt alleen als de kop de Plaud-id of de skill-kop draagt (anders melding "herkomst onbekend"); vaste punten
   1.1-1.11 krijgen in het verslag de herkomst "vast punt kantoor" (geen vaststelling); bronpoort: elk niet-vast
   punt krijgt een veld `bron` (bestandsnaam of foto-bestandsnaam uit de bezoekmap, of transcript met tijdstip);
   ontbreekt die, dan wordt het punt gemarkeerd "(bron ontbreekt, na te kijken)" en geteld in proef_info["zonder_bron"].
3. X3/K3 naslagvalidator: naslag gaat als eigen sleutel "naslag" naar het model (niet onder "fotolijst");
   een punt krijgt alleen naslag als het een eigen vaststelling met bron heeft; na `vraag_verslag` een controle
   die elke zin van `tekst_nl` vergelijkt met de meegegeven naslagfragmenten (letterlijke overname van meer dan
   12 woorden -> zin vervangen door "(zie naslag)" en melding); veld `naslag` beperkt tot 240 tekens en moet
   beginnen met een sleutel uit het register (TV..., DIGEST..., ...); records met `licentie` buildwise/nbn krijgen
   in het promptblok de regel "citeren, niet kopiëren" en de pdf-naam wordt nooit in het verslag gezet;
   naslag met status "verouderd" krijgt automatisch de toevoeging "(opvolger na te kijken)".
4. X5/K4 tokens: feiten schonen (geen dekking, hashes, bronbestanden in de modelinvoer), dubbele fotolijst weg,
   bij een afgekapt antwoord (stop_reason max_tokens) één herhaling met de helft van de punten of kleiner
   plafond, en de werkelijke tokens per stap in proef_info["tokens"] opslaan. Het harde tokenbudget per bezoek
   (25.000 in, 8.000 uit, 3 naslagbronnen, 3.000 naslagtekens) bouw je in achter een instelling
   `WERF_TOKENBUDGET` die standaard UIT staat (Mehdi beslist nog); documenteer hoe hij aangaat.
5. K5 zichtbaar op de bezoekpagina: `proef_info` toont fotos_niet_geplaatst, zonder_bron en naslagmeldingen;
   dat is in `mijnagents/templates/werfbezoek.html` (blok Proef) en `mijnagents/app.py` als er iets nodig is.

Tests in `mijnagents-runner/tests/` (bestaande blijven groen). Werkwijzen bijwerken: `werkwijze/werfverslag-
voorbereider.md` (grendels, W12) en `werkwijze/werfverslag-schrijver.md` (bronpoort, naslagvalidator, tokens).
Nederlands, geen emoji, geen kastlijntjes in tekst voor Mehdi. Schrijf tot slot `VERSLAG-codex-herstel.md`:
per punt wat je deed, wat je aannam, wat open blijft, met bestand:regel.

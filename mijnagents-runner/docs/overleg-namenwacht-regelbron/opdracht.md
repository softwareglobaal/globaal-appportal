# Opdracht: herstel regelbron van de Namenwacht (T-0028, 29-10-2026)

Repo: globaal-appportal, werktak namenwacht-regelbron, commit f995ec4 (bekijk met `git show f995ec4`).

## Probleem
De Namenwacht (benamingen-wacht en mappenwacht, `mijnagents-runner/koppelingen/naamstructuur.py`) toetst H-A-mappen
tegen het afsprakenboek "H-A vaste afspraken". Hij pinde het hele bestand v1.7 (pad en SHA-256) en pauzeerde de
H-A-toetsing zodra er een hogere versie in dezelfde map stond (besluit C2, 17-10). Op 18-10 verhuisde v1.7 naar
`archief/` en kwam v1.10 in de map. Sindsdien pauzeert de H-A-toetsing en vraagt de agent Mehdi "Welke versie geldt?".
Gemeten: hoofdstuk B is identiek van v1.7 tot v1.10; hoofdstuk A verschilt alleen in A14 (uitleg over het
mailexportscript en een nieuwe regel over bijlagen in `0 Mails/bijlagen/`). Geen van de toetsen (A1, A2-A3, A3-A6
momentnamen, A13, A14 fiche en oude bronmappen, B1) gebruikt die passage.

## Herstel
- Nieuwe functie `hoofdstukken(tekst, letters)`: neemt de tekst van `## A. ` tot de volgende `## <letter>. `-kop.
- `controleer_regelbron` zoekt de hoogste versie >= de vastgepinde in de map, leest die, en is geldig als de
  SHA-256 van hoofdstuk A en B gelijk is aan `hoofdstukken_sha256` in `naamstructuur-regels.json`.
  Anders: pauze; bij een hogere versie met `gevonden` (de ronde maakt dan de bestaande nood voor Mehdi).
- Pin verplaatst naar v1.10 met de hoofdstukhash. Geen versie of alleen oudere versies: pauze. Niet-UTF-8: pauze.
- Tests aangepast en uitgebreid (17 tests, alle groen; test_naamstructuur 27 groen).

## Vragen
1. Klopt het herstel, en pauzeert het nog altijd veilig (fail closed) waar het moet?
2. Mist er een geval: hoofdstukgrenzen, codeblokken met `## `-koppen, versies als v1.10 vs v1.9 sortering,
   cache van 24 uur na een nieuwe versie, de dagelijkse force, de herbeoordeling bij een gewijzigde regelbron?
3. Moet de nood bij een echt gewijzigd hoofdstuk A of B naar Mehdi ("Welke versie geldt?") of naar Claude
   (machinevertaling nakijken)? Mehdi is regisseur en keurt het boek zelf al goed.
Antwoord kort, in het Nederlands, met ernst hoog/middel/laag per punt.

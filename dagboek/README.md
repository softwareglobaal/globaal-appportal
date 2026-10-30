# Dagboek (dagboek.globaal.be)

Wat Mehdi elke dag deed, in een oogopslag. Bron van waarheid: De Dagbundelaar.

- Leest alleen de dagbestanden die De Dagbundelaar elke nacht schrijft:
  `mijnagents-data/dagboek/<jaar>/<dag>.md` (de tekst) en `<dag>.json` (de telling).
  Dezelfde bestanden staan in Dropbox, "Data uit Mehdi/Dagboek".
- Rekent niets opnieuw uit, schrijft niets, geen eigen opslag.
- Overzicht: de laatste 14 dagen, per dag zes tegels (afspraken, gesprekken, niet gepland,
  mail, WhatsApp, telefoon). Klik op een dag: gepland met uitkomst, niet gepland, communicatie.
- Toegang: Authentik (forward-auth), groep `locatie` (alleen Mehdi), en de app toetst die
  groep zelf nog eens af (`DAGBOEK_GROUPS`).
- Test: `python3 test_dagboek.py` (draait ook in de Docker-build). Het proefbestand in
  `proef/` is gemaakt met de echte code van De Dagbundelaar, met verzonnen namen.

Live zetten op de VM (eenmalig):

    cd ~/appportal && git pull
    docker compose up -d --build app-dagboek
    docker compose up -d --force-recreate nginx
    python3 scripts/app-registreren.py dagboek

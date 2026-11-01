# Dagboek (dagboek.globaal.be)

Wat Mehdi elke dag deed, in een oogopslag. Bron van waarheid: De Dagbundelaar.

- Leest alleen de dagbestanden die De Dagbundelaar elke nacht schrijft:
  `mijnagents-data/dagboek/<jaar>/<dag>.md` (de tekst) en `<dag>.json` (de telling).
  Dezelfde bestanden staan in Dropbox, "Data uit Mehdi/Dagboek".
- Waar Mehdi was (sinds 31-10-2026): de tegel Onderweg (km, plekken, tijd rijden) en op de dagpagina "Waar was ik"
  (plekken, projecten, ritten). Uit het Locatie-dashboard over het interne netwerk (`LOCATIE_URL`, standaard
  `http://app-locatie:3031`, de routes `/api/dagcijfers` en `/api/dagboek/<dag>`), vijf minuten bewaard. Is het
  dashboard onbereikbaar, dan een vraagteken en een zin, nooit een lege dag.
- Rekent niets opnieuw uit, schrijft niets, geen eigen opslag.
- Overzicht: de laatste 14 dagen, per dag zes tegels (afspraken, gesprekken, niet gepland,
  mail, WhatsApp, telefoon). Klik op een dag: gepland met uitkomst, niet gepland, communicatie.
- Eigen werk en gezondheid (31-10-2026): het blok uit het dagbestand met Wispr Flow (dictaten, woorden,
  minuten), websites (bezoeken, sites, de vijf meest bezochte sites, alleen de sitenaam) en de Apple
  Watch (regels van de Gezondheidswacht). Een dag zonder wacht staat als onbekend, nooit 0. De
  Dagbundelaar leest ze van het bord (items `wispr:Mehdi:<dag>`, `websites:<dag>`, `gezondheid:<dag>`).
  Laptopstappen: `mijnagents-runner/docs/dagbundelaar/opdrachten/wispr-websites-gezondheid-naar-het-dagboek.md`.
- Wachten (sinds 01-11-2026, pagina `/wachten`): per wacht van de groep Dagbundelaar wat er die dag binnenkwam,
  voorlopig vandaag en de twee dagen ervoor (`WACHT_DAGEN`). Per wacht het aantal items, de items zelf (tijd, van wie of
  wat, kort) en het werkverslag van die dag. Groen: kwam binnen. Oranje: draaide, niets binnen. Rood: fout.
  Grijs: geen ronde. De gegevens komen van het bord (`/api/wachten/dag`, `mijnagents/wachten_dag.py`) over het
  interne netwerk met `AGENTS_TOKEN`; antwoordt het bord niet, dan zegt de pagina dat.
- Toegang: Authentik (forward-auth), groep `locatie` (alleen Mehdi), en de app toetst die
  groep zelf nog eens af (`DAGBOEK_GROUPS`).
- Test: `python3 test_dagboek.py` (draait ook in de Docker-build). Het proefbestand in
  `proef/` is gemaakt met de echte code van De Dagbundelaar, met verzonnen namen.

Live zetten op de VM (eenmalig):

    cd ~/appportal && git pull
    docker compose up -d --build app-mijnagents app-dagboek
    docker compose up -d --force-recreate nginx
    python3 scripts/app-registreren.py dagboek

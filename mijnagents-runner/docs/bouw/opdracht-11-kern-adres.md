# Opdracht 11: controle van bouw/kern_adres.py (01-11-2026)

Kijk de wijziging na op tak bouw-kern-adres tegenover origin/main: `mijnagents-runner/bouw/kern_adres.py`, de nieuwe
stap in `mijnagents-runner/docs/bouw/uitrol.sh` en de tests onderaan `mijnagents-runner/tests/test_bouw.py`.
Antwoord in het Nederlands, kort: AKKOORD of NIET AKKOORD, met per punt ernst (hoog, middel, laag) en bewijs (bestand:regel).

Waarom: `bouw/scheiding.py` (laad_kern) eist voor de firma's HARC en HARM een ondernemingsnummer en een adres (straat en
huisnummer) in kern. Op de server heeft geen enkele firma in kern.firma een adres_id; kern.adres heeft één rij. Daardoor
weigert Bouw elke vraag. Het hulpmiddel zet het adres van de zetel uit de openbare KBO-pagina van het ondernemingsnummer
dat al in kern staat, alleen waar kern.firma.adres_id leeg is. Schrijven gaat via `kern.adres_vind_of_maak` (migratie
`db/migrations/025-adres-entiteit.sql`), daarna een update van de gestructureerde velden en van kern.firma.adres_id.

Vragen:
1. Kan het een bestaand adres of de gegevens van een andere firma overschrijven?
2. Is de SQL veilig tegen een aanhalingsteken of ander teken uit de KBO-pagina? (psql krijgt de opdracht via
   `docker exec ... psql -c`, zie `koppelingen/organisatie.py` `_psql`.)
3. Leest `zetel()` alleen het adres van de pagina met precies dat ondernemingsnummer, en weigert het bij een afwijkende vorm?
4. Klopt de redenering dat een update in dezelfde opdracht als `adres_vind_of_maak` de nieuwe rij niet ziet?
5. Komt een adres ooit in de uitvoer of een log?

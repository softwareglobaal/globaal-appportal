# Portal via Claude (MCP)

Alle applicaties van het platform leesbaar vanuit Claude, met precies de
rechten die de gebruiker op het portaal ook heeft.

| | |
|---|---|
| Adres | `https://portal-mcp.globaal.be/mcp` (nog niet live) |
| Draait als | systemd `portal-mcp` op de host (gepland: `172.17.0.1:8113`) |
| Code | deze map (stack-repo), VM-checkout `~/appportal/portal-mcp` |
| Toegang | `scripts/add-portal-mcp-token.py` (serviceaccount, alleen lezen) |

## De regel die boven alles staat

**Authentik bepaalt wie wat leest.** Wie een tegel op het portaal niet mag zien,
leest de data van die app hier ook niet. Er is bewust geen tweede rechtenlijst
die naast Authentik kan gaan staan en stilletjes kan verouderen.

Daaruit volgen drie dingen die in `catalogus.py` vastliggen en in
`test_catalogus.py` bewaakt worden:

1. De rechten worden bij elke aanroep opgehaald, niet in het OAuth-token
   gebakken. Een token leeft twaalf uur; een ingetrokken groep moet binnen een
   minuut werken.
2. Ligt Authentik eruit, dan volgt een fout en geen lege lijst. Falen doen we
   dicht, niet open.
3. Een app zonder policy-binding is voor niemand toegankelijk, niet voor
   iedereen.

## Stand van zaken

**Fase 1 (klaar):** `catalogus.py` leest de applicaties en de policy-bindings uit
Authentik en bepaalt per gebruiker welke apps hij mag lezen. Superuser ziet
alles, groepslid ziet de apps van zijn groepen, een binding op naam telt mee, en
uitgezette of omgekeerde bindings geven niets. Draaien met `pytest`.

**Fase 2 (nog te doen):** de leeslaag over de gedeelde database. Een read-only
rol via een genummerde migratie, plus het gereedschap `schema(app)` en
`query(app, sql)` in een READ ONLY-transactie. Dat dekt de twintig schema's in
de appportal-database in één keer. Nog te beslissen: schema's met
persoonsgegevens (`kern.persoon`, `hr`, elevait-kandidaten) horen vermoedelijk
niet in een vrije `query` thuis, ook niet voor wie de tegel mag zien.

**Fase 3 (nog te doen):** adapters voor de apps die hun data ergens anders
hebben staan (RenoVision in Mongo, staving in de native Postgres, status in
SQLite). Die staan tot dan wel in de cataloog, met een zichtbare reden waarom ze
nog niet leesbaar zijn. Stil overslaan leest als "bestaat niet".

## Valkuil die al geld gekost heeft

Zonder het recht `authentik_core.view_application` geeft
`core/applications/?superuser_full_list=true` een **lege lijst** terug in plaats
van een 403. Een lege cataloog ziet er niet uit als een rechtenprobleem. Daarom
staan de vier benodigde kijkrechten expliciet in
`scripts/add-portal-mcp-token.py`.

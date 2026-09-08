# Portal via Claude (MCP)

Alle applicaties van het platform leesbaar vanuit Claude, met precies de
rechten die de gebruiker op het portaal ook heeft.

| | |
|---|---|
| Adres | `https://portal-mcp.globaal.be/mcp` (nog niet live, de HTTP-laag ontbreekt) |
| Code | deze map (stack-repo), VM-checkout `~/appportal/portal-mcp` |
| Leesrol | `mcp_lezer`, wachtwoord in `.env` als `MCP_LEZER_WACHTWOORD` |
| Rechten | `rol-authentik.sql` en `rol-appportal.sql` (gegenereerd) |

## De regel die boven alles staat

**Authentik bepaalt wie wat leest.** Wie een tegel op het portaal niet mag zien,
leest de data van die app hier ook niet. Er is bewust geen tweede rechtenlijst
die naast Authentik kan gaan staan en stilletjes kan verouderen.

Met een aanvulling die we onderweg hebben moeten leren, zie hieronder: toegang
tot een app is niet hetzelfde als toegang tot alles wat eronder ligt.

## Hoe de grens bewaakt wordt

Drie lagen, van buiten naar binnen:

1. **Authentik** zegt welke apps deze gebruiker mag openen (`catalogus.py`).
2. **De bronnenkaart** zegt waar de data van die app staat (`bronnen.py`).
3. **Postgres** bewaakt de grens tijdens de query. Per app en per rechtenniveau
   bestaat er een rol; de server doet `SET LOCAL ROLE` in een READ
   ONLY-transactie. Vergeet hij dat, dan volgt "permission denied" en geen
   stille uitlevering van andermans data.

Die derde laag is er met opzet in plaats van een controle op de tekst van de
SQL. Zo'n tekstcontrole kun je omzeilen met een view, een functie of een
subquery; een rolwissel niet.

## Waarom de database en niet de Authentik-API

De API kan een cataloog van alle applicaties alleen aan een superuser geven:
`superuser_full_list` en `for_user` staan allebei achter
`request.user.is_superuser` (zie `/authentik/core/api/applications.py`). Daarvoor
zou een volledig admin-token in `.env` moeten, en dat token kan ook schrijven:
gebruikers aanmaken, groepen wijzigen, tokens uitgeven.

In plaats daarvan leest `mcp_lezer` vier tabellen in de Authentik-database, en op
`authentik_core_user` alleen de kolommen `id`, `username` en `is_active`. De
wachtwoord-hashes liggen buiten bereik. Geverifieerd: schrijven geeft
`permission denied for schema public`, de hash geeft `permission denied for
table authentik_core_user`.

De prijs is dat we aan het interne schema van Authentik vastzitten. Daarom staan
de aannames als controles in de code, niet als commentaar: een app die aan een
expressie-policy hangt of helemaal geen binding heeft, krijgt `onzeker` mee met
een reden en wordt niet leesbaar.

## Toegang tot een app is niet hetzelfde als toegang tot alles eronder

Dit is de fout die het ontwerp bijna in had gezeten, gevonden op 08-09-2026.

`sufa` zit alleen in de groep `namenlijst`. Daarmee mag zij de Organisatie-tegel
openen, en die app leest de schema's `kern`, `organisatie` en `kosten`. In de
eerste opzet kon zij via de MCP dus `kern.persoon_beloning` lezen: salarissen.
In de app zelf kan dat niet, want daar zit RBAC per tabblad.

De apps hebben binnenin dus een tweede laag, en die moet hier terugkomen.
`CATEGORIEEN` in `bronnen.py` legt vast welke tabellen gevoelig zijn en welke
groep ze opent:

| categorie | tabellen | groep |
|---|---|---|
| personeel | `hr.*`, `kern.persoon_beloning`, `_hr`, `_afwezigheid`, `_inzage`, `_dienstfirma` | hr, admin, manager |
| financieel | `kosten.*`, `kern.audit`, `kern.audit_overzicht` | kosten, admin, manager |

`kern.persoon` staat er bewust niet in: dat is de personeelslijst met naam,
functie en afdeling, en die is platformbreed zichtbaar (telefoonregister,
namenlijst). Het gevoelige zit in de tabellen eromheen.

Gemeten uitkomst voor de app `medewerkers`:

| gebruiker | tabellen | `kern.persoon_beloning` | `kosten.bank_transactie` |
|---|---|---|---|
| sufa (namenlijst) | 45 | geweigerd | geweigerd |
| mehdi | 69 | leesbaar | leesbaar |
| akadmin (beheerder) | 69 | leesbaar | leesbaar |

Wat sufa niet ziet, wordt haar wél verteld: het antwoord bevat `niet_zichtbaar`
met de reden en de groep die het zou openen. Stil weglaten leest als "bestaat
niet".

## De rollen bijwerken

`rol-appportal.sql` is **gegenereerd**. Pas `bronnen.py` aan en draai daarna:

```bash
python3 genereer_rollen.py > rol-appportal.sql
```

Het bestand trekt rechten ook weer in, niet alleen uit. Dat is nodig gebleken:
een eerdere versie gaf `mcp_app_medewerkers` het hele schema `kosten`, en toen
de kaart strenger werd bleef die rechten gewoon staan tot er een REVOKE bij kwam.
Weglaten is niet hetzelfde als intrekken.

Er staan bewust **geen** `ALTER DEFAULT PRIVILEGES` op de app-schema's: een
tabel die er later bij komt is niet meteen leesbaar. Anders zou een nieuwe tabel
met salarissen vanzelf meeliften.

## Stand van zaken

**Fase 1 en 2 zijn klaar en getoetst tegen de echte database.** 33 tests, plus
een handmatige toets op de VM voor de dingen die je niet kunt nabootsen: dat de
rol niet kan schrijven, niet bij de hashes komt, en dat de grens tussen apps
door Postgres wordt afgedwongen.

Gemeten cataloog: 54 applicaties, 0 onzeker. Voor mehdi: 46 apps toegankelijk,
waarvan 15 nu leesbaar, 10 die elders staan en 21 nog niet uitgezocht.

**Wat nog ontbreekt voor een werkende koppeling:** de HTTP-laag zelf
(`mcp_server.py`), met dezelfde OAuth-opzet als vermogen en renovision: de
authorize-stap achter de Authentik forward-auth, stateless tokens, en de
vhost plus een systemd-service.

**Fase 3:** adapters voor de apps die hun data elders hebben (RenoVision in
Mongo, staving in de native Postgres op 5432, status in SQLite). Die staan nu in
de cataloog met de reden waarom ze nog niet leesbaar zijn.

**De 21 onuitgezochte apps** krijgen `onbekend` mee. Een regel promoveren doe je
op bewijs, niet op de naam: kijk in de broncode van de app welke schema's hij
bevraagt en zet dat commando in het veld `bewijs`. Zie de kop van `bronnen.py`.

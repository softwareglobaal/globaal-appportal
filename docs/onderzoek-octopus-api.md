# Onderzoek: Octopus REST API (stap 3 uit PLAN.md)

> Stand 2026-07-09. Bronnen: de officiele handleiding
> (login.octopus.be/manual/octopus-webservice/api/) en de OpenAPI-spec
> (service.inaras.be/octopus-rest-api/swagger/, 78 endpoints, versie 1.0).
> Status: documentatie-onderzoek AF; de read-only probe wacht op de
> API-gebruiker (zie "Wat we nog nodig hebben").

## Authenticatie-model

Base-URL: `https://service.inaras.be/octopus-rest-api/v1`

Drie-traps, alles read-only mogelijk:

1. **POST /authentication** - header `softwareHouseUuid` (de Software House
   ID die Octopus ons gaf) + JSON-body `{user, password}` (een gewone
   Octopus-gebruiker). Antwoord: een **token dat 10 minuten geldig is**.
   De poller moet dus per run (of per 10 minuten) opnieuw inloggen -
   zelfde patroon als de Xelion-sessie.
2. **GET /dossiers** - header `Token`. Geeft de dossiers (boekhoudingen)
   waar deze gebruiker bij kan; dit zijn onze firma's (HA, UNABO, EE, ...).
3. **POST /dossiers?dossierId=N** - header `Token`. Geeft een
   **dossiertoken**; daarmee bevraag je alles binnen dat ene dossier.
   Een dossier = een boekhouding = onze firma-koppeling uit
   `kosten.octopus_boekhouding` (migratie 059).

Secrets in `~/appportal/.env` (nooit in git of chat):
`OCTOPUS_SOFTWAREHOUSE_UUID`, `OCTOPUS_USER`, `OCTOPUS_PASSWORD`.

## Wat de API kan (relevant voor ons)

| Behoefte | Endpoint(s) | Opmerking |
|---|---|---|
| Relaties-sync (vervangt de handmatige export van Joan) | `GET /dossiers/{id}/relations` + `GET .../relations/modified` | de `modified`-variant maakt incrementele sync mogelijk |
| Grootboekrekeningen | `GET .../accounts` + `.../accounts/modified` + `.../accounts/amounts/modified` | saldi-mutaties apart opvraagbaar |
| Dagboeken (A/V/F/D/L) | `GET .../bookyears/{jaar}/journals` en per type `journals/A|V|F|D|L/{nr}` | exact de structuur uit docs/octopus-dossier.md |
| Boekingen/spend | `GET .../buysellbookings(/modified)`, `financialdiversbookings(/modified)`, `bookyears/{jaar}/bookings/modified` | de kern van stap 4 (spend-pijplijn) |
| Facturatievoorstellen | `GET/POST/PUT .../deliverynotes`, `POST .../deliverynotes/generate`, `GET .../deliverynotes/export` | de Delivery Notes-flow uit de meeting bestaat volledig in de API |
| Facturen (later, schrijvend) | `invoices` CRUD + `generate`, `send`, `book` | pas na expliciet akkoord; wij beginnen read-only |
| Openstaande posten (validatie) | `POST .../reports/clients|suppliers|accounts/open` en `.../history` | rapporten voor het validatie-beeld en de leveranciers-verzoening |
| BTW-codes, kostenplaatsen, producten | `vatcodes`, `costcentres`, `products`, `productgroups` | naslaglagen |
| CODA / payroll | `POST .../coda`, `POST .../payroll` | schrijvend, buiten scope |

## Beperkingen en aandachtspunten

1. **Token 10 minuten geldig**: re-authenticatie inbouwen; geen lange
   sessies cachen.
2. **Alles is per dossier**: cross-firma betekent per firma een
   dossiertoken en de resultaten zelf samenvoegen (de partij-laag,
   migratie 058, is daarvoor al de landingsplaats).
3. **Rate limits staan niet in de spec**: in de probe voorzichtig zijn
   (sequentieel, korte lijsten) en het antwoordgedrag documenteren.
4. **Paginering**: niet expliciet in de spec; de `modified`-endpoints
   werken met een since-parameter. In de probe verifieren (les van
   Xelion: default-pagina's zijn klein).
5. De API kent ook **schrijvende** endpoints (boekingen, facturen,
   bookyear sluiten). Onze poller gebruikt uitsluitend GET; schrijven
   (facturatievoorstellen aanmaken) is een aparte, latere beslissing.

## Probe-resultaat (2026-07-09, lokaal vanaf de werkplek)

De volledige keten is **empirisch bewezen** tegen het testaccount:
authenticatie OK, 1 dossier ("Globaal", id 35493), dossiertoken OK,
**relations: 14 rijen** (velden matchen kosten.octopus_relatie:
active, client, defaultBookingAccountClient/Supplier, ...) en
**bookyears: 1**. Twee empirische correcties op de spec-lezing:
de dossierlijst gebruikt `dossierDescription` + `dossierKey.id`, en
per-dossier-calls willen de header **`dossierToken`** (met `Token`
antwoordt de API 401, errorCode -79 "Empty access token"). Derde
empirische les: de modified-endpoints antwoorden **404 "No modified
bookings found"** wanneer er niets gewijzigd is - dat is "geen
wijzigingen", geen fout (de poller behandelt het zo). De pijplijn van
stap 4 is op 2026-07-09 lokaal end-to-end bewezen tegen het testdossier:
eerste run 15 boekingen (A1/V1/D/F met relatie, bedrag, BTW-regels),
tweede run incrementeel schoon (0 bijgewerkt, status ok).

## Leesrechten en de productie-aanvraag

De API kent **geen eigen scopes**: een token is zo machtig als de
Octopus-gebruiker erachter. Alleen-lezen afdwingen gebeurt daarom in twee
lagen: (1) vraag bij de productie-toegang expliciet om een gebruiker met
een **leesprofiel** (alleen raadplegen) op alle dossiers, en (2) de poller
heeft een **harde leesvergrendeling** (finance_sync._vraag weigert elke
call met een body behalve de twee login-stappen). Verificatie zodra de
productie-gebruiker er is: de no-op-schrijftest (een relatie identiek
terugschrijven) hoort dan een 401/403 te geven - dan zit het slot
bewijsbaar dicht. NB: schrijvend werk (facturatievoorstellen) krijgt
later zijn eigen gebruiker met precies de rechten die daarvoor nodig
zijn; nooit de leesgebruiker verbreden.

## Wat we nog nodig hebben (rest van gate G1)

- [x] Software House ID - ontvangen en werkend bevonden (2026-07-09).
- [x] Testaccount-credentials werken; de keten is technisch bewezen.
- [ ] **Productie-toegang**: een gebruiker (liefst leesbeperkt, niet
      Joan's eigen login) gekoppeld aan de acht echte dossiers - dat is
      het laatste stuk voor de go van stap 4.

## De probe (klaar om te draaien)

`scripts/octopus-probe.py`: authenticeert, doet GET /dossiers en toont
alleen aantallen en dossiernamen. Leest de drie env-variabelen, schrijft
niets, logt geen secrets. Draaien op de VM:

```
cd ~/appportal
set -a; . ./.env; set +a
python3 scripts/octopus-probe.py
```

**Go/no-go voor stap 4**: go zodra de probe de acht dossiers toont en de
relations-call van een dossier data geeft die matcht met de import van
2026-07-08.

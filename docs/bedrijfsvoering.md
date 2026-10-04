# Globaal Bedrijfsvoering: Authentik-aansluiting v1.1

De applicatie krijgt een eigen tegel en adres: `https://bedrijfsvoering.globaal.be`.
De bron staat in de private GitHub-repository
[`softwareglobaal/globaal-bedrijfsvoering`](https://github.com/softwareglobaal/globaal-bedrijfsvoering).
De stack-integratie staat in `softwareglobaal/globaal-appportal`.

## Toegang en mandaten

De Authentik-groep `bedrijfsvoering` opent de tegel en de proxy. Lidmaatschap geeft
geen bedrijfs- of dossierrechten. De applicatie controleert daarnaast bij ieder
verzoek het actieve account, het mandaat per vennootschap, de rol en de toegang tot
het dossier. Nieuwe collega's krijgen bij hun eerste aanmelding geen mandaat.
De eigenaar wijst hun benodigde bedrijven en rollen expliciet toe in de app.

Authentik levert de stabiele gehashte proxy-UID in `X-authentik-uid`. Die verschilt
van de UUID in `kern.persoon.authentik_sub`; leg als eigenaar exact de proxy-UID
vast. In Authentik is die beschikbaar als `User.uid`. Gebruikersnamen en
e-mailadressen zijn weergavevelden. De applicatie accepteert deze identiteit alleen
via de beschermde proxy met het eigen proxygeheim. Meegegeven
`oai-authenticated-user-*` koppen worden verwijderd. De eigenaar staat vooraf
vastgelegd met `BEDRIJFSVOERING_OWNER_UID`; de eerste willekeurige bezoeker wordt
nooit eigenaar. Bestaande `admin`- en `manager`-groepen krijgen geen extra toegang.
De betekenis van de kop staat in de
[Authentik-providerdocumentatie](https://docs.goauthentik.io/add-secure-apps/providers/proxy/).

De firmalijst wordt als beheerbestand uit de centrale bron `kern.firma` aangeboden
via `bedrijfsvoering-config/company-seed.json`. Werkgever en dienstenfirma's zijn
werkrelaties en leveren geen automatische autorisatie op. De nieuwe omgeving blijft
een oefenruimte met herkenbare testnummering totdat juridische stamgegevens,
medewerkermandaten en de volledige procesketen zijn gecontroleerd. Deze aansluiting
betekent geen 100% Teamleader-dekking.

## Bestanden en geheimen

| Bestand of instelling | Doel |
|---|---|
| `docker-compose.bedrijfsvoering.yml` | Additieve service en Nginx-omgevingsvariabele |
| `nginx/templates/76-bedrijfsvoering.conf.template` | Eigen vhost en proxygeheim per host |
| `nginx/snippets/forward-auth-bedrijfsvoering.conf` | Authentik-controle en gecontroleerde identiteitskoppen |
| `apps.yaml` | Tegel, groepsbinding en registratie; bewust zonder `poort` |
| `~/appportal/.env`: `BEDRIJFSVOERING_PROXY_SECRET` | Gedeeld geheim tussen Nginx en alleen deze app |
| `~/appportal/.env`: `BEDRIJFSVOERING_OWNER_UID` | Vooraf vastgelegde Authentik-proxy-UID van de eigenaar |
| `~/appportal/.env`: `COMPOSE_FILE` | Laat toekomstige compose-opdrachten de overlay meenemen |
| Docker-volume `bedrijfsvoering-data`, in de app `/data` | Duurzame database en bestanden; opnemen in de back-up |

Geheimen staan uitsluitend op de VM in de lokale `.env`. Waarden worden nooit
gecommit of afgedrukt. Gebruik geen `nginx -T` of volledige `docker compose config`
in uitvoer: die kunnen ingevulde geheimen tonen. `docker compose config --quiet`
controleert de compose-opzet zonder waarden af te drukken.

## Uitrol zonder bestaande VM-aanpassingen te overschrijven

De app-checkout komt in `~/appportal/bedrijfsvoering`. Voeg de nieuwe overlay,
template en snippet afzonderlijk toe. Behoud bestaande lokale wijzigingen in
`docker-compose.override.yml`, andere nginx-templates en overige bestanden. Voer
geen reset, clean of vervanging van de hele stackmap uit.

Bouw en controleer het productieartefact lokaal of in CI voordat het naar de VM
gaat. De app gebruikt `Dockerfile.prebuilt`: de gecontroleerde productie-uitvoer
uit `dist/` wordt apart naast de bron op de VM geplaatst. Die gegenereerde map
staat niet in GitHub. Een broncheckout zonder dit artefact is niet uitrolbaar.
De VM voert alleen de kleine runtime-imagebouw uit; daar worden geen zware
dependency-installatie of compilatie gestart. Een automatische deployment van
iedere GitHub-push is hiermee nog niet ingericht.

De duurzame instelling in de lokale stack-`.env` is:

```dotenv
COMPOSE_FILE=docker-compose.yml:docker-compose.override.yml:docker-compose.bedrijfsvoering.yml
```

Staat `COMPOSE_FILE` al ingesteld, voeg de overlay aan de bestaande lijst toe en
behoud alle bestaande bestanden in die lijst. Stel de twee nieuwe variabelen in
voordat de overlay wordt ingeschakeld; ontbrekende waarden blokkeren de uitrol.
Nginx krijgt het geheim expliciet in zijn containeromgeving. Alleen een regel in
`.env` zonder de overlay levert het geheim niet aan Nginx.

Na controle van bron, tests, bedrijfsbron, eigenaar en back-up:

```bash
cd ~/appportal
git status --short
git log -5 --oneline
python3 scripts/test_bedrijfsvoering_infra.py
python3 scripts/test_bedrijfsvoering_toegang.py
python3 scripts/bedrijfsvoering-configureren.py
docker compose config --quiet
python3 scripts/app-registreren.py bedrijfsvoering --dry-run
python3 scripts/app-registreren.py bedrijfsvoering
docker compose cp bedrijfsvoering-config/access.json authentik-server:/tmp/bedrijfsvoering-access.json
sh scripts/ak-exec.sh scripts/bedrijfsvoering-toegang.py
docker compose up -d --no-deps --build app-bedrijfsvoering
```

`bedrijfsvoering-configureren.py` leest de centrale firma's en gekoppelde actieve
personen. Het controleert de ene eigenaar tegen diens Authentik-account, vertaalt
de UUID naar de proxy-UID en bewaart bestaande instellingen. Het overzicht noemt
alleen aantallen; geen geheimwaarden. De bedrijfsmomentopname bevat ook inactieve
firma's met hun status. De beheerbestanden blijven lokaal en worden niet gecommit.

`bedrijfsvoering-toegang.py` voegt actieve interne collega's uit
de bestaande Authentik-directory toe. Zo kan een collega de tegel gebruiken ook
wanneer diens koppeling in `kern.persoon` nog ontbreekt. `AnonymousUser`, `akadmin`,
serviceaccounts, externe accounts en inactieve accounts
worden uitgesloten, ook wanneer een centrale profielkoppeling hen noemt. De
eigenaar moet bovendien exact bij de vastgelegde UUID en naam `mehdi` horen en
actief en intern zijn. E-mail is contactmetadata en mag ontbreken, ook bij de
eigenaar; de geverifieerde UUID en proxy-UID bepalen de identiteit. Het maakt geen gebruikers
of wachtwoorden en behoudt bestaande groepen. Herhalen voegt geen dubbele
groepslidmaatschappen toe. Dit script geeft nul bedrijfsmandaten: collega's moeten
die daarna van de eigenaar ontvangen. Het verwijdert geen oudere toewijzingen;
uitdiensttreding blijft via de bestaande Authentik-offboarding lopen.

Controleer de gerenderde nginx-configuratie in een aparte controlecontainer
voordat de bestaande proxy opnieuw wordt aangemaakt. Een `nginx -t` op de huidige
container controleert de reeds gerenderde configuratie, niet de nieuwe template.
Na een geslaagde controle:

```bash
docker compose up -d --no-deps --force-recreate nginx
docker compose exec -T nginx nginx -t
docker compose ps app-bedrijfsvoering nginx
```

De `--no-deps` opdrachten beperken deze uitrol tot de app en proxy. Templates worden
bij de containerstart met envsubst verwerkt; een gewone nginx-reload verwerkt geen
nieuwe template of gewijzigde containeromgeving. Het bestaande wildcard-DNS en
wildcard-certificaat dekken volgens de stackdocumentatie dit subdomein. Controleer
DNS en TLS opnieuw tijdens de live oplevering.

`apps.yaml` bevat bewust geen `poort` voor deze app. De automatische generator
`scripts/apps-ontbrekend.py` kijkt alleen in `docker-compose.override.yml` en zou
anders een tweede service willen aanmaken. De eigen overlay is de beheerde
servicebron. `portal.globaal.be` verwijst naar de Authentik-launcher; voor een nieuwe
tegel is geen wijziging aan de oude Flask-portal nodig.

## Bewijs bij oplevering

De infrastructuurgrendel controleert onder meer ontbreken van publieke apppoorten,
duurzame opslag, exclusieve appgroep, ontbrekende-eigenaarblokkade, gekopieerde
identiteitskoppen en verwijdering van voormalige Sites-koppen. Dit zijn
configuratieproeven, geen bewijs dat collega-accounts live werken. De aparte
toegangsproeven voeren de echte toewijzingsbron uit met uitsluitend geïsoleerde
Authentik-modelfixtures en controleren uitsluitingen, eigenaar en idempotentie.

Controleer live apart: TLS, redirect zonder sessie, afwijzing buiten de appgroep,
aanmelding van eigenaar en collega, ontbreken van bedrijfsinzage zonder mandaat,
positieve procesketen binnen een toegewezen bedrijf, afwijzing van inzage en
schrijfopdrachten in een ander bedrijf, opslag na herstart en teruglezen van audit.
Houd niet uitgevoerde proeven zichtbaar en neem het datavolume in de back-up op.

De medewerkerskoppeling in `kern.persoon` bevatte bij live controle slechts zes accounts. De apptegel gebruikt daarom de bestaande Authentik-directory: uitsluitend actieve interne menselijke accounts. E-mail mag ontbreken; identificatie gebruikt de proxy-UID. AnonymousUser, akadmin, serviceaccounts en externe accounts worden uitgesloten. Werkgever, appgroep en globale adminrol worden nooit automatisch vertaald naar bedrijfsmandaten. De eigenaar krijgt via de app-bootstrap expliciete mandaten; overige collegaaccounts blijven pending totdat de eigenaar ze per vennootschap toewijst.

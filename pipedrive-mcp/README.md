# Pipedrive via Claude (MCP)

De vijf Pipedrive-administraties van de groep bereikbaar vanuit Claude: deals,
contacten, organisaties, activiteiten, notities en leads lezen, en met de juiste
groep ook aanmaken en bijwerken.

Eén regel staat boven alles: **elke handeling hoort bij precies één firma, en
die firma wordt gevraagd, niet geraden.**

| | |
|---|---|
| Adres | `https://pipedrive-mcp.globaal.be/mcp` |
| Draait als | systemd `pipedrive-mcp` op de host, `172.17.0.1:8112` |
| Code | deze map (stack-repo), VM-checkout `~/appportal/pipedrive-mcp` |
| Vhost | `nginx/templates/68-pipedrive-mcp.conf.template` |
| Toegang | `scripts/add-pipedrive-mcp.py` |

## De vijf firma's

| Sleutel | Firma | Pipedrive |
|---|---|---|
| `harchitects` | H-Architects | h-architects |
| `unabo` | UNABO | unabo |
| `tknburo` | TKN-Buro | tkn-buro-tekenwerk (heet daar TKN-Tekenwerk) |
| `energieefficient` | Energie Efficiënt | energieefficient |
| `harmoniebouw` | HarmonieBOUW | harmoniebouw |

Vijf losse Pipedrive-accounts, vijf losse tokens, geen gedeelde gegevens. Het
sales-dashboard (`sales.globaal.be`) gebruikt er vier van; HarmonieBOUW komt er
hier bij.

## Waarom de firma altijd gevraagd wordt

Een deal die in de verkeerde administratie belandt, is niet met een
ongedaan-knop terug te draaien: hij staat in de verkeerde omzet, bij de
verkeerde eigenaar, en de klant ziet het op de verkeerde offerte. Daarom is dit
op drie plaatsen vastgelegd, en niet alleen in een instructietekst:

1. **Het schema.** Elk stuk gereedschap heeft `firma` in `required`, met de vijf
   sleutels als `enum`. Claude kan de parameter niet weglaten zonder fout.
2. **De poort in de code.** `gereedschap.voer_uit` roept eerst `firma_kiezen`
   aan, vóór welk stuk gereedschap dan ook. Ontbreekt de firma of is hij
   onbekend, dan volgt een weigering die de vijf keuzes noemt en zegt dat de
   gebruiker het moet zeggen. Nieuw gereedschap komt daar automatisch achter te
   staan; `test_firma.py` bewaakt dat.
3. **Wat Claude leest.** De beschrijving van elk stuk gereedschap eindigt op
   "vraag de gebruiker eerst voor welke firma dit is", en de
   `initialize`-instructies zeggen dat de firma van een vorige vraag niet
   doorwerkt. Het antwoord van elk gereedschap begint met de firma, zodat het in
   de samenvatting terechtkomt.

Er is bewust **geen 'alle firma's tegelijk'**. Wil je vergelijken, dan stelt
Claude de vraag vijf keer en zegt er per antwoord bij welke firma het was.

## Het gereedschap

| | |
|---|---|
| Oriënteren | `firmas` (het enige zonder firma-parameter), `overzicht`, `velden` |
| Zoeken | `zoeken` (alles tegelijk), `deals`, `personen`, `organisaties`, `leads` |
| Lezen | `deal`, `deal_geschiedenis`, `persoon`, `organisatie`, `activiteiten`, `notities` |
| Schrijven | `deal_aanmaken`, `deal_bijwerken`, `persoon_aanmaken`, `persoon_bijwerken`, `organisatie_aanmaken`, `organisatie_bijwerken`, `activiteit_aanmaken`, `activiteit_bijwerken`, `notitie_aanmaken`, `lead_aanmaken` |

Maatwerkvelden werken op naam: vraag `velden` welke er zijn, en geef bij
aanmaken of bijwerken `velden: {"Bouwjaar": 1998, "Type woning": "Rijwoning"}`.
Keuzevelden accepteren het label; een ongeldige keuze geeft de lijst met
mogelijke labels terug in plaats van een fout uit Pipedrive.

## Wie mag wat

**Alleen Mehdi**, sinds 03-09-2026. Toegang gaat op naam en niet per groep: de
verkoopadministratie van vijf firma's is niets voor een brede kijkgroep. Wie op
de lijst staat mag ook schrijven.

Twee poorten, allebei nodig om iemand toe te laten:

1. **Authentik** - een binding op naam op de app `pipedrive-mcp`, gezet met
   `scripts/set-pipedrive-mcp-toegang.py` (pas `TOEGANG` daar aan). Zonder
   binding komt iemand niet eens bij de loginstap.
2. **De server zelf** - `MCP_GEBRUIKERS` in `~/pipedrive-mcp.env`, een
   komma-lijst met Authentik-gebruikersnamen. Die wordt getoetst bij het
   inloggen **en bij elk verzoek daarna**: een access token is twaalf uur
   geldig en een refresh token twee maanden, dus zonder die tweede toets zou
   iemand die van de lijst af gaat gewoon doorwerken.

Waarom twee: een verruiming in Authentik (iemand krijgt een groep erbij) hoort
niet meteen vijf Pipedrive-administraties te openen. Laat je `MCP_GEBRUIKERS`
leeg, dan valt de server terug op het groepsmodel: binnenkomen mag wie door de
forward-auth komt, schrijven alleen `pipedrive-editors` of `admin`.

De vaste sleutel `MCP_TOKEN` is de **beheerdeur** en valt buiten de namenlijst.
Dat verruimt de kring niet: het bestand staat 0600 op de VM, en wie het kan
lezen kan net zo goed de Pipedrive-tokens uit `~/appportal/.env` halen. Wil je
ook die deur dicht, leeg dan `MCP_TOKEN` en herstart de dienst.

Verwijderen kan niet. Er is geen gereedschap voor, in geen enkele firma. Een
deal sluit je met `deal_bijwerken` (status `lost` met een verliesreden).

## Instellen

`~/pipedrive-mcp.env` op de VM (niet in git):

```
MCP_SECRET=<lange willekeurige tekst>     # tekent de OAuth-tokens
MCP_TOKEN=<lange willekeurige tekst>      # optioneel, vaste sleutel voor beheer
MCP_BASIS=https://pipedrive-mcp.globaal.be
MCP_GEBRUIKERS=mehdi                      # wie erbij mag; leeg = groepsmodel
```

Zonder `MCP_SECRET` en `MCP_TOKEN` geeft `/mcp` een 404: de koppeling bestaat
dan simpelweg niet.

De **Pipedrive-tokens zelf staan niet in dit bestand**. Ze komen uit
`~/appportal/.env` (`PIPEDRIVE_TOKEN_HARCHITECTS` enzovoort), dezelfde vijf die
het sales-dashboard gebruikt, zodat een rotatie maar op één plek hoeft. De
server leest daar alleen de `PIPEDRIVE_TOKEN_`-regels uit. Het token gaat als
kopregel `x-api-token` naar Pipedrive, niet in de URL: anders staat het in elke
foutmelding en elk proxylog.

## Uitrollen

```bash
cd ~/appportal && git pull
python3 -m venv pipedrive-mcp/.venv && pipedrive-mcp/.venv/bin/pip install -q -r pipedrive-mcp/requirements.txt
sudo cp pipedrive-mcp/pipedrive-mcp.service /etc/systemd/system/
sudo ufw allow from 172.16.0.0/12 to any port 8112 proto tcp comment 'docker -> pipedrive-mcp'
sudo systemctl daemon-reload && sudo systemctl enable --now pipedrive-mcp
sh scripts/ak-exec.sh scripts/add-pipedrive-mcp.py
sh scripts/ak-exec.sh scripts/set-pipedrive-mcp-toegang.py
docker compose up -d --force-recreate nginx
```

Controle: `curl -s http://172.17.0.1:8112/gezond` toont welke van de vijf
tokens gevonden zijn en wie er toegang heeft.

## Koppelen in Claude

**In de browser:** claude.ai → Instellingen → Connectors → aangepaste connector
op `https://pipedrive-mcp.globaal.be/mcp`, daarna inloggen via SSO.

**Lokaal, in Claude Code:**

```bash
claude mcp add --transport http pipedrive https://pipedrive-mcp.globaal.be/mcp
```

Daarna in een sessie `/mcp` en kiezen voor authenticeren. Geen sleutel nodig;
de browser opent en Authentik doet de rest. De vaste sleutel `MCP_TOKEN` is er
alleen voor beheer en heeft volledige schrijfrechten.

## Tests

```bash
cd ~/appportal/pipedrive-mcp && .venv/bin/python -m pytest -q
```

`test_firma.py` bewaakt de firma-poort (herkende schrijfwijzen, weigeringen, en
dat geen enkel stuk gereedschap eromheen kan) en dat het token niet in de URL
belandt. `test_koppeling.py` bewaakt waar de OAuth-code naartoe mag, dat de
namenlijst niemand anders binnenlaat, en dat elk stuk gereedschap de
firma-regel uitdraagt.

## Valkuilen die dit patroon al gekost heeft

**Geen `proxy_buffers` in de vhost.** De forward-auth-snippet zet die al en
nginx weigert een dubbele directive; op 31-08-2026 startte nginx daardoor niet
meer en lag het hele platform plat. Controleer na elke vhost-wijziging
`docker exec appportal-nginx-1 nginx -t`.

**ufw moet poort 8112 doorlaten** vanaf de docker-netwerken, anders loopt elk
verzoek in een time-out in plaats van een nette 502.

**De ORM-create in Authentik roept `set_oauth_defaults()` niet aan.** Zonder die
regel blijft `redirect_uris` leeg en geeft inloggen "Redirect URI Error"; het
uitrolscript doet het daarom expliciet.

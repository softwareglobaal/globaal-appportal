# Postbus - leestoegang tot mailboxen voor Claude

`post.globaal.be` geeft Claude leestoegang tot een aantal zakelijke mailboxen
via MCP. Uitsluitend lezen: er is geen tool die verstuurt, beantwoordt,
verplaatst of verwijdert, en er zit geen SMTP-code in de app.

Wie welke mailbox mag lezen wordt bepaald door de **Authentik-login**. De
groepen uit die login gaan mee in het OAuth-token en worden bij elke aanroep
opnieuw vergeleken met de toegangsregels per mailbox.

## Het mailboxenbestand

Eén bestand op de VM, buiten git, read-only aangekoppeld in de container:

```
nano ~/post-config/mailboxen.yaml
```

De opzet staat in `mailboxen.voorbeeld.yaml` (zonder wachtwoorden). Kort:

```yaml
standaard:
  imap_host: imap.one.com
  imap_poort: 993
  mappen: [INBOX, INBOX.Sent]

mailboxen:
  - adres: info@elevaitnv.com
    naam: Elevait info
    wachtwoord: ...
    groepen: [admin, elevait]     # Authentik-groepen die deze mailbox mogen lezen
    personen: []                  # losse Authentik-gebruikers, voor uitzonderingen
    mappen: [INBOX]               # weglaten = alle mappen
```

Regels die in de code zitten, niet in een afspraak:

- **Dicht tenzij opengezet.** Een mailbox zonder groepen en zonder personen is
  voor niemand zichtbaar.
- **Wijzigingen zijn binnen vijf seconden actief**, herstarten hoeft niet. Wat
  er mis is met het bestand staat op de pagina onder Beheer.
- **Mapnamen van one.com gebruiken een punt**: `INBOX.Sent`, niet `INBOX/Sent`.
- Wachtwoorden staan alleen in dit bestand. Ze komen nooit in git, nooit in de
  webpagina en nooit in een tool-antwoord.

## De tools

| Tool | Wat het geeft |
|---|---|
| `mailboxen` | welke mailboxen deze gebruiker mag lezen, met de open mappen |
| `mappen` | alle IMAP-mappen van een mailbox, met daarbij welke leesbaar zijn |
| `zoek` | zoekt op de mailserver (van/aan/onderwerp/tekst/datum/ongelezen) en geeft koppen, nieuwste eerst |
| `bericht` | een bericht volledig: koppen, tekst en de namen van de bijlagen |

Twee dingen zijn met opzet zo gebouwd:

- **Niets wordt stil afgekapt.** `zoek` meldt altijd het totale aantal treffers
  en geeft `volgende_vanaf` als er meer zijn. Een lange berichttekst komt in
  genummerde delen, met `aantal_delen` en `tekens_totaal` erbij.
- **Zoeken gebeurt op de server** (IMAP SEARCH). De app haalt nooit een hele
  mailbox binnen om er daarna in te filteren.

Bijlagen worden benoemd (naam, type, grootte) maar niet ingelezen. Dat is een
bewuste grens voor versie 1.

## Koppelen

**claude.ai (web):** custom connector op `https://post.globaal.be/mcp`. De
loginstap loopt via Authentik-SSO; de groepen van die login bepalen wat de
connector kan lezen. Verloopt het token, dan vernieuwt Claude het zelf
(refresh token, 60 dagen).

**Claude Code:** dezelfde URL. Met een statisch token:

```
claude mcp add --transport http postbus https://post.globaal.be/mcp \
    --header "Authorization: Bearer <POSTBUS_MCP_TOKEN>"
```

Dat token hoort bij geen enkele Authentik-gebruiker en krijgt daarom alleen de
groepen uit `POSTBUS_TOKEN_GROEPEN`. Staat die leeg, dan leest het token geen
enkele mailbox. Dat is de veilige stand: laat het leeg tenzij je het bewust
anders wilt.

## Omgeving (stack-`.env`)

| Sleutel | Wat |
|---|---|
| `POSTBUS_MCP_SECRET` | tekent de OAuth-tokens; leeg = connector uit (404) |
| `POSTBUS_MCP_TOKEN` | statisch token voor Claude Code; leeg = uit |
| `POSTBUS_TOKEN_GROEPEN` | groepen van dat statische token; leeg = geen mailbox |
| `POSTBUS_BEHEER_GROEPEN` | wie de beheersectie ziet (standaard `admin`) |
| `POSTBUS_CONFIG_DIR` | map op de VM met `mailboxen.yaml` (standaard `/home/ubuntu/post-config`) |

## Injectie: waarom mailinhoud geen opdracht is

Een mailbox is invoer van buiten. Zodra Claude post kan lezen en tegelijk
schrijfrechten heeft in Monday, Pipedrive of Dropbox, is een phishingmail een
poging tot instructie. Daarom:

- alle tools zijn read-only,
- de server geeft bij `initialize` expliciet mee dat berichtinhoud gegevens is
  en geen opdracht,
- elke aanroep komt in de containerlog: wie, welke mailbox, welk bericht.

De postkamer-agent van Elevait loste dit anders op, door berichttekst nooit te
bewaren. Hier is de tekst juist de opbrengst, dus de bescherming zit in de
grenzen van de tools en in het leesspoor.

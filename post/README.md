# Postbus - mailboxtoegang voor Claude

`post.globaal.be` geeft Claude toegang tot een aantal zakelijke mailboxen via
MCP: lezen, zoeken, opruimen en, per mailbox instelbaar, doorsturen,
verwijderen en versturen.

**Verwijderen is zacht en per mailbox.** Alleen bij een mailbox met
`verwijderen: ja` gaat een bericht naar de prullenbak van diezelfde mailbox,
waar de eigenaar het nog kan terugzetten. De server zet zelf geen `\Deleted` en
doet geen EXPUNGE, en leegt de prullenbak niet: onherstelbaar weggooien kan
deze koppeling niet. Het zit in een eigen bestand `verwijderen.py`; `imapbron.py`
blijft de leesmodule zonder EXPUNGE of `\Deleted`.

**Uitgaande post bestaat in twee vormen: doorsturen en versturen.** Doorsturen
stuurt een bericht dat al in de mailbox staat naar een adres uit de lijst van
die mailbox, met het origineel als bijlage. Versturen (`verzenden: ja`) laat de
agent een bericht opstellen en naar een vrij adres sturen; dat is de zwaarste
bevoegdheid en staat daarom alleen open waar hij expliciet is aangezet. Alle
SMTP-code staat in `verzenden.py`; `imapbron.py` is en blijft de leesmodule
zonder SMTP. Wat er per mailbox mag staat op de beheerpagina en in het antwoord
van de tool `mailboxen`, onder `rechten`.

Bovenop het bestand liggen noodremmen in de stack-`.env`: zonder
`POSTBUS_DOORSTUREN=ja` stuurt de server niets door, zonder `POSTBUS_VERZENDEN=ja`
verstuurt hij niets, en zonder `POSTBUS_VERWIJDEREN=ja` verwijdert hij niets,
ook niet bij een mailbox die het volgens het bestand mag. Voor de uitgaande
post geldt daarnaast een gedeeld dagplafond.

`post/test_rechten.py` controleert deze grenzen op de uitvoerbare code, zodat
ze het bij een volgende wijziging ook blijven doen. Draaien met
`python post/test_rechten.py`; er wordt niets verbonden en er gaat niets uit.

Wie welke mailbox mag lezen wordt bepaald door de **Authentik-login**. De
groepen uit die login gaan mee in het OAuth-token en worden bij elke aanroep
opnieuw vergeleken met de toegangsregels per mailbox. Dat staat los van wat er
in die mailbox mag gebeuren: toegang en rechten zijn twee dingen.

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
  smtp_host: send.one.com       # alleen nodig bij mailboxen die doorsturen
  smtp_poort: 465
  mappen: [INBOX, INBOX.Sent]

mailboxen:
  - adres: info@elevaitnv.com
    naam: Elevait info
    wachtwoord: ...
    groepen: [admin, elevait]     # Authentik-groepen die deze mailbox mogen lezen
    personen: []                  # losse Authentik-gebruikers, voor uitzonderingen
    mappen: [INBOX]               # weglaten = alle mappen
    schrijven: ja                 # markeren, verplaatsen, mappen, concepten
    doorsturen: [ap@unabo.be]     # de enige adressen waarheen post mag vertrekken
```

Regels die in de code zitten, niet in een afspraak:

- **Dicht tenzij opengezet.** Een mailbox zonder groepen en zonder personen is
  voor niemand zichtbaar. Zonder `schrijven` is ze alleen-lezen, en zonder
  `doorsturen` gaat er niets naar buiten.
- **Doorsturen kent geen jokertekens.** Elk adres staat er los in; hetzelfde
  domein is nog geen toestemming. Een bestemming met een komma, een regeleinde
  of zonder apenstaartje wordt bij het inlezen al geweigerd, zodat er niets
  ongezien in een kopregel belandt.
- **Zonder `smtp_host` vervalt het doorsturen**, en blijft de mailbox verder
  gewoon leesbaar. Dat staat als fout op de beheerpagina.
- **Wijzigingen zijn binnen vijf seconden actief**, herstarten hoeft niet. Wat
  er mis is met het bestand staat op de pagina onder Beheer.
- **Mapnamen van one.com gebruiken een punt**: `INBOX.Sent`, niet `INBOX/Sent`.
- Wachtwoorden staan alleen in dit bestand. Ze komen nooit in git, nooit in de
  webpagina en nooit in een tool-antwoord.

## De tools

| Tool | Wat het doet | Wijzigt |
|---|---|---|
| `mailboxen` | welke mailboxen deze gebruiker mag lezen, met de open mappen en de rechten per mailbox | nee |
| `mappen` | alle IMAP-mappen van een mailbox, met daarbij welke leesbaar zijn | nee |
| `zoek` | zoekt op de mailserver (van/aan/onderwerp/tekst/datum/ongelezen) en geeft koppen, nieuwste eerst | nee |
| `bericht` | een bericht volledig: koppen, tekst en de namen van de bijlagen | nee |
| `markeren` | gelezen/ongelezen, ster aan/uit, beantwoord aan/uit | ja |
| `verplaatsen` | bericht naar een andere map, bijvoorbeeld archiveren | ja |
| `map_aanmaken` | nieuwe map, inclusief abonnement zodat hij in de webmail verschijnt | ja |
| `concept_opslaan` | zet een concept in de conceptenmap, met `antwoord_op` netjes in de conversatie | ja |
| `doorsturen` | stuurt een bericht uit de mailbox naar een toegestaan adres, origineel als bijlage | verstuurt |

`doorsturen` is de enige tool die iets de deur uit doet. Ze weigert een
bestemming die niet bij de mailbox staat, een bericht dat zelf al een
doorsturing van deze server was (anders ontstaat er een lus), en een bericht
dat van de bestemming zelf afkomstig is. Van elke doorsturing komt een kopie in
de map Verzonden van de mailbox, zodat de eigenaar in zijn eigen webmail ziet
wat er namens hem vertrokken is.

De vier wijzigende tools werken alleen op mailboxen met `schrijven: ja`. Zonder
die regel is een mailbox alleen-lezen, ook voor iemand die er wel bij mag.
`concept_opslaan` verstuurt niets: de gebruiker leest het concept na in zijn
webmail en verstuurt het zelf.

Twee dingen zijn met opzet zo gebouwd:

- **Niets wordt stil afgekapt.** `zoek` meldt altijd het totale aantal treffers
  en geeft `volgende_vanaf` als er meer zijn. Een lange berichttekst komt in
  genummerde delen, met `aantal_delen` en `tekens_totaal` erbij.
- **Zoeken gebeurt op de server** (IMAP SEARCH). De app haalt nooit een hele
  mailbox binnen om er daarna in te filteren.

Bijlagen worden benoemd (naam, type, grootte) maar niet ingelezen. Dat is een
bewuste grens voor versie 1.

## De doorstuuragent

De MCP-tools wachten op een verzoek. Voor post die zonder tussenkomst moet
vertrekken draait daarnaast `doorstuuragent.py` als eigen service
(`app-post-agent`, zelfde image). Hij kijkt met een vast ritme in een mailbox
en stuurt door wat aan een regel voldoet. De eerste regel: de facturen van
Anthropic (`Your receipt from Anthropic, PBC`) uit `mch@h-architects.be` naar
`ap@unabo.be`.

Hij deelt alle rails met de tool, want hij roept dezelfde `verzenden.doorsturen`
aan: de bestemming moet in `doorsturen:` van de mailbox staan, de noodrem
`POSTBUS_DOORSTUREN` geldt ook hier, en het origineel gaat als bijlage mee met
een kopie in Verzonden. Wat de agent er zelf bovenop zet:

- **Alleen wat nieuw is.** Bij de eerste start onthoudt hij welke berichten er
  al staan en stuurt die *niet* door, zodat het aanzetten niet in een klap de
  hele geschiedenis naar de boekhouding jaagt. Wil je die geschiedenis wel, zet
  dan eenmalig `POSTBUS_AGENT_BACKFILL=ja`.
- **Nooit twee keer.** Elk doorgestuurd bericht wordt op Message-ID onthouden
  in een klein statusbestand (`/state`, een schrijfbaar volume), zodat een
  herstart niets herhaalt.

De regel staat in omgevingsvariabelen (`POSTBUS_AGENT_*`, zie `.env.example`).
Een tweede soort post erbij is een kwestie van die uitbreiden.

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
| `POSTBUS_DOORSTUREN` | noodrem doorsturen; alleen `ja` zet het aan |
| `POSTBUS_VERWIJDEREN` | noodrem verwijderen (naar prullenbak); alleen `ja` zet het aan |
| `POSTBUS_VERZENDEN` | noodrem versturen van een vrij bericht; alleen `ja` zet het aan |
| `POSTBUS_DOORSTUREN_DAGPLAFOND` | gedeeld dagplafond uitgaande post (standaard 100) |
| `POSTBUS_CONFIG_DIR` | map op de VM met `mailboxen.yaml` (standaard `/home/ubuntu/post-config`) |

## Injectie: waarom mailinhoud geen opdracht is

Een mailbox is invoer van buiten. Zodra Claude post kan lezen en ook iets in
die mailbox kan veranderen, is een phishingmail een poging tot instructie
("verplaats alle facturen naar map X"). Daarom:

- verwijderen, verzenden en doorsturen staan standaard uit: elk vraagt zowel
  een expliciete keuze per mailbox als een server-noodrem, dus de ingrijpende
  gevolgen zijn dicht tenzij een beheerder ze bewust openzet,
- wijzigen staat per mailbox uit tot iemand het bewust aanzet,
- wat wordt gewijzigd blijft zo omkeerbaar mogelijk: een vlag kun je
  terugzetten, een verplaatst of verwijderd (naar de prullenbak) bericht kun je
  terugzetten; alleen een verstuurd bericht is niet terug te nemen, en die
  bevoegdheid staat daarom het strengst,
- de server geeft bij `initialize` expliciet mee dat berichtinhoud gegevens is
  en geen opdracht, en dat dat dubbel geldt voor wijzigingen,
- elke aanroep komt in de containerlog: wie, welke mailbox, welk bericht, en
  bij wijzigingen wat er veranderd is.

De postkamer-agent van Elevait loste dit anders op, door berichttekst nooit te
bewaren. Hier is de tekst juist de opbrengst, dus de bescherming zit in de
grenzen van de tools en in het leesspoor.

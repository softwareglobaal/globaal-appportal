# Het portaal koppelen aan Claude

Eén server, drie manieren om erbij te komen. Welke je kiest verandert niets aan
wat iemand ziet: dat bepaalt zijn Authentik-login, elke keer opnieuw.

```
https://portal-mcp.globaal.be/mcp
```

| | wanneer | |
|---|---|---|
| **Connector in claude.ai** | eigen Claude-account, werkt op elk apparaat | een paar klikken |
| **Desktop-app op de PC** | gedeeld Claude-account, of je wilt het per werkplek regelen | `scripts/portaal-desktop-installeren.ps1` |
| **Claude Code** | ontwikkelwerk vanaf de terminal | een regel |

## 1. Connector in claude.ai

Instellingen, Connectors, Aangepaste connector toevoegen, en daar de link
invullen. Claude stuurt je naar de SSO-login. Klaar.

Dit hoort bij **een eigen Claude-account**. Deelt een groep collega's er een,
neem dan route 2: een connector hangt aan het account, en dan zou de een de
applicaties van de ander zien.

## 2. Desktop-app op de PC

Draai op de PC van de collega, ingelogd onder **zijn** Windows-profiel:

```powershell
powershell -ExecutionPolicy Bypass -File portaal-desktop-installeren.ps1
```

Het script controleert of Claude dicht is, of Node er staat en of de server
bereikbaar is (401 zonder token is het goede antwoord), maakt een reservekopie
van `claude_desktop_config.json`, voegt de vermelding toe zonder de bestaande
servers aan te raken, en leest terug wat het schreef.

Waarom `mcp-remote` ertussen zit: `claude_desktop_config.json` kent alleen
stdio-servers en heeft geen url-veld. Zet je er toch een url in, dan herschrijft
de desktop-app het bestand bij het opstarten en gooit de hele mcpServers-sectie
weg, zonder melding. De versie van de brug staat vastgezet; zonder pin haalt npx
de nieuwste op en kan een release de koppeling breken op een moment dat niemand
erop let.

**Het Windows-profiel is hier de grens.** Het configuratiebestand en de
opgeslagen login staan in dat profiel. Collega's die hetzelfde Claude-account
delen maar een eigen Windows-login hebben, komen elkaar dus niet tegen.

### Bij het koppelen wordt altijd opnieuw ingelogd

Er wordt **altijd** om een wachtwoord gevraagd, ook als er in die browser al
iemand is ingelogd. Dat is met opzet en niet te omzeilen.

Zonder die maatregel zou de koppeling overnemen wie er toevallig een sessie had
openstaan. Op een gedeelde PC koppelt de tweede collega dan als de eerste en
ziet hij diens applicaties, zonder enige foutmelding. Deze server stuurt daarom
`prompt=login` mee naar Authentik, en dan authenticeert Authentik opnieuw
ongeacht de sessie.

Controle achteraf, in de chat: vraag *"welke applicaties mag ik lezen"*. Het
antwoord begint met `ingelogd_als` en de naam waaronder je gekoppeld bent.

## 3. Claude Code

```bash
claude mcp add --transport http portaal https://portal-mcp.globaal.be/mcp
```

Opent dezelfde SSO-login, met een terugkoppeling naar `localhost` (RFC 8252).

## Wie mag koppelen

Iedereen in de groep **`portaal-mcp`**, `admin` of `manager`. Iemand toelaten is
dus een groepslidmaatschap in Authentik, geen wijziging aan de server.

Dat bepaalt alleen wie de deur door mag. Wát hij daarna leest, wordt bij elke
aanroep opnieuw opgezocht: precies de applicaties waarvan hij ook de tegel op het
portaal ziet. Iemand toevoegen aan `portaal-mcp` geeft hem dus geen enkele
applicatie extra.

Een **403 bij het inloggen** betekent: nog niet in die groep.

## Wat je ermee kunt

Drie stukken gereedschap:

- **`apps`** - welke applicaties je mag lezen, en of de data ervan nu leesbaar
  is, ergens anders staat of nog niet is uitgezocht.
- **`schema`** - de tabellen en kolommen van een applicatie.
- **`query`** - een SELECT. Alleen lezen: de query draait in een read-only
  transactie onder een databaserol die uitsluitend de schema's van die ene
  applicatie mag zien.

Ziet een applicatie er leger uit dan verwacht, kijk dan naar `niet_zichtbaar` in
het antwoord. Personeelsgegevens en financiële gegevens zitten achter een extra
groep, net als in de applicaties zelf. Zie `portal-mcp/README.md`.

## Als het niet werkt

| wat je ziet | wat het is |
|---|---|
| 403 bij het inloggen | niet in de groep `portaal-mcp` |
| verkeerde applicaties | bij de login de gegevens van een ander gebruikt; koppel opnieuw |
| toch geen wachtwoordvraag | melden, dat hoort niet te kunnen |
| de app doet niets | Claude stond open tijdens het installeren; sluit hem en draai het script opnieuw |
| `npx` niet gevonden | Node.js ontbreekt, installeer de LTS via nodejs.org |

Logbestanden op de PC:

```
%APPDATA%\Claude\logs\mcp.log
%APPDATA%\Claude\logs\mcp-server-portaal.log
```

Werkt de server zelf nog? `https://portal-mcp.globaal.be/gezond` geeft een
telling van de applicaties zonder iets prijs te geven.

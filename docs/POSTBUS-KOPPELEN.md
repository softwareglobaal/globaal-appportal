# Postbus koppelen aan de Claude desktop-app

Draaiboek om een collega toegang te geven tot mailboxen via de Postbus, ook
wanneer meerdere collega's hetzelfde Claude-account delen.

Eerst uitgevoerd voor Mukesh op 2026-09-02. Elke valkuil hieronder is een
storing die we onderweg echt hebben gehad, geen theorie.

## Wanneer dit draaiboek

Gebruik de gewone connector op claude.ai wanneer de collega een eigen
Claude-account heeft. Dat is eenvoudiger en heeft geen brug nodig.

Gebruik dit draaiboek wanneer collega's een Claude-account **delen**. Een
connector hangt aan het account, dus wat de een koppelt kan de ander lezen.
De lokale route zet de koppeling in het Windows-profiel, en dat profiel is dan
de grens.

| Route | Waar de koppeling staat | Zichtbaar voor wie het account deelt |
|---|---|---|
| Instellingen > Connectors | server-side, bij het account | **ja** |
| `claude_desktop_config.json` | lokaal, Windows-profiel | nee |

## Hoe het werkt

De desktop-app kan alleen lokale stdio-servers starten. De Postbus is remote.
Daartussen zit `mcp-remote`, een lokale brug die stdio naar HTTPS vertaalt en
de OAuth-login afhandelt.

```
Claude Desktop  --stdio-->  npx mcp-remote  --HTTPS-->  post.globaal.be/mcp  --IMAP-->  one.com
   (zijn PC)                  (zijn PC)                      (de VM)
```

Op de PC staat alleen de vermelding in het configuratiebestand en de tokencache
in `%USERPROFILE%\.mcp-auth`. Geen mailboxen, geen wachtwoorden, geen berichten.
Die blijven in `~/post-config/mailboxen.yaml` op de VM en bij one.com.

Claude leert pas bij het verbinden wat de Postbus is: de server stuurt zelf zijn
naam, de elf tools en de instructietekst (`INSTRUCTIES` in `mcp_server.py`).
Het Claude-account weet nergens van.

## Deel 1: serverkant

### 1.1 Mailbox in `mailboxen.yaml`

Op de VM, `~/post-config/mailboxen.yaml`. Bestaat de mailbox al, voeg dan alleen
de naam toe aan `personen`.

```yaml
  - adres: hr@globaal.be
    naam: HR Globaal
    wachtwoord: 'wachtwoord-hier'
    groepen: []
    personen: [ishara]
```

**Zet het wachtwoord altijd tussen enkele quotes.** Begint het met `&`, `*` of
`!`, dan leest YAML dat als een anker en is het hele bestand stuk. Alle
mailboxen vallen dan tegelijk uit, niet alleen de nieuwe.

Rechten zijn dicht tenzij je ze opent: `schrijven: ja` voor ordenen en
concepten, `verzenden: ja` voor versturen (vereist ook een `smtp_host`, die uit
het `standaard`-blok komt), `verwijderen: ja` voor de prullenbak. Elk van de
drie mag ook een lijst namen zijn, dan geldt het recht alleen voor hen.

Het bestand wordt elke vijf seconden herlezen, dus geen herstart nodig.

Controleer daarna dat het parst:

```sh
cd ~/appportal && docker compose exec -T app-post python -c "
import yaml
c = yaml.safe_load(open('/config/mailboxen.yaml'))
print(len(c['mailboxen']), 'mailboxen, bestand parst')
"
```

### 1.2 Verbinding testen

```sh
cd ~/appportal && docker compose exec -T app-post python -c "
import yaml, imaplib
c = yaml.safe_load(open('/config/mailboxen.yaml'))
std = c.get('standaard', {})
m = [x for x in c['mailboxen'] if x['adres'] == 'ADRES-HIER'][0]
s = imaplib.IMAP4_SSL(m.get('imap_host', std['imap_host']),
                      int(m.get('imap_poort', std.get('imap_poort', 993))))
s.login(m.get('gebruiker', m['adres']), m['wachtwoord'])
ok, data = s.select('INBOX', readonly=True)
print('LOGIN OK -', data[0].decode(), 'berichten'); s.logout()
"
```

Kan ook via de beheerpagina op `https://post.globaal.be`, knop "Verbinding
testen".

### 1.3 Authentik-groep `postbus`

**Dit wordt het vaakst vergeten en geeft een 403 bij het koppelen.** De
Postbus-app in Authentik staat alleen open voor `admin`, `manager` en `postbus`.
Iemand die alleen in bijvoorbeeld `hr` of `epb` zit, komt er niet in.

Controleren:

```sh
cd ~/appportal && docker compose exec -T postgresql psql -U authentik -d authentik -A -c \
"select g.name from authentik_core_group g
 join authentik_core_user_groups ug on ug.group_id = g.group_uuid
 join authentik_core_user u on u.id = ug.user_id
 where u.username = 'NAAM' order by 1"
```

Toevoegen:

```sh
cd ~/appportal && docker compose exec -T postgresql psql -U authentik -d authentik -A -c \
"insert into authentik_core_user_groups (user_id, group_id)
 select u.id, g.group_uuid from authentik_core_user u, authentik_core_group g
 where u.username = 'NAAM' and g.name = 'postbus' on conflict do nothing"
```

De naam in `personen` moet letterlijk de Authentik-gebruikersnaam zijn.

## Deel 2: werkplek

Alles hieronder gebeurt onder **zijn** Windows-profiel.

### 2.1 Node

```
winget install OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
```

Vraagt beheerdersrechten. Daarna een nieuwe terminal openen en `node --version`
controleren. Getest op v24.19.0 met npx 11.17.0.

### 2.2 Claude Desktop volledig afsluiten

Ook uit het systeemvak. Het venster sluiten is niet genoeg.

Doe dit voordat je het configuratiebestand aanraakt: de app schrijft bij het
afsluiten naar dat bestand en gooit je wijziging er anders overheen.

### 2.3 Configuratiebestand

`%APPDATA%\Claude\claude_desktop_config.json`. Bestaat het al, voeg dan alleen
het `mcpServers`-blok toe en laat `preferences` en de rest ongemoeid. Opslaan
als UTF-8 **zonder BOM**.

```json
{
  "mcpServers": {
    "postbus": {
      "command": "npx",
      "args": ["-y", "mcp-remote@0.8.2", "https://post.globaal.be/mcp"]
    }
  }
}
```

**Gebruik nooit een `url`-veld.** De desktop-app kent alleen stdio-servers. Zet
je er een `url` in, dan herschrijft de app het bestand bij het opstarten en
verdwijnt de hele `mcpServers`-sectie plus een aantal `preferences`-sleutels,
zonder foutmelding.

De versie staat vast op `0.8.2`. Zonder vastzetten haalt npx altijd de nieuwste
op en kan een release de koppeling breken op een moment dat niemand erop let.
Hapert het, probeer dan `0.8.1`.

Het script `scripts/postbus-desktop-installeren.ps1` doet stap 2.2 en 2.3 met
reservekopie, bereikbaarheidstest en terugleescontrole. Het weigert te draaien
zolang de app open staat.

### 2.4 Browsersessie leegmaken

Uitloggen op `https://globaal.be`, of een privevenster gebruiken.

**Dit is de stap die stil misgaat.** De brug koppelt aan wie er in de browser
is ingelogd, niet aan wie achter de PC zit. Bij onze test op een andere laptop
kwam er een token voor Mukesh uit terwijl we akadmin verwachtten. Geen
foutmelding, alleen de verkeerde mailboxen.

### 2.5 Starten en inloggen

Claude Desktop starten. De eerste keer duurt het ongeveer een halve minuut,
want de brug wordt dan opgehaald. Er opent een browser met de Authentik-login.
**De collega logt zelf in, als zichzelf.**

### 2.6 Eindcontrole

Vraag in de chat: "welke mailboxen mag ik zien". Dat draait de tool `mailboxen`,
die de effectieve rechten van de ingelogde persoon teruggeeft.

Klopt de lijst niet met wat je in deel 1 hebt ingesteld, dan is 2.4 misgegaan.
Gooi `%USERPROFILE%\.mcp-auth` weg en herhaal vanaf 2.4.

### 2.7 Waar de connector staat

Plusje linksonder in het invoerveld > Connectors > Manage connectors. Ook in
Instellingen > Developer, met de status van de server.

Hij staat in dezelfde lijst als de accountgebonden connectors. Dat is geen lek:
lokale servers worden daar getoond maar bestaan alleen op die machine. De
sluitende controle is dat een collega op zijn eigen PC met hetzelfde account
`postbus` niet ziet staan.

## Wat je de collega moet zeggen

Voeg de Postbus nooit toe via Instellingen > Connectors. Die koppeling hangt aan
het gedeelde Claude-account, en dan leest iedereen die dat account gebruikt mee.

## Storingen

| Verschijnsel | Oorzaak |
|---|---|
| 403 bij het koppelen | niet in de Authentik-groep `postbus`, zie 1.3 |
| Verkeerde of te veel mailboxen | verkeerde browsersessie bij 2.4 |
| `mcpServers` verdwenen uit de config | een `url`-veld gebruikt in plaats van de brug |
| Alle mailboxen tegelijk weg | YAML stuk, meestal een wachtwoord zonder quotes |
| Server verschijnt niet na herstart | `%APPDATA%\Claude\logs\mcp-server-postbus.log` |
| Brug start niet | Node ontbreekt, of probeer `mcp-remote@0.8.1` |

Logbestanden op de werkplek: `%APPDATA%\Claude\logs\mcp.log` en
`mcp-server-postbus.log`.

## Waarom dit werkt

`mcp-remote` vangt de OAuth-callback op `http://127.0.0.1:<poort>/oauth/callback`.
De Postbus liet aanvankelijk alleen redirects naar claude.ai toe; sinds
2026-08-28 staat `_redirect_ok` in `post/mcp_server.py` ook localhost en
127.0.0.1 toe (RFC 8252). PKCE S256 blijft verplicht en de autorisatiecode leeft
twee minuten, dus de localhost-route is niet zwakker.

Let op de twee schrijfwijzen: de brug gebruikt `127.0.0.1`, niet `localhost`.
Beide staan toe.

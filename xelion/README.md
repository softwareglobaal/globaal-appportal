# Xelion - de telefooncentrale voor Claude

`xelion.globaal.be` geeft Claude toegang tot de Xelion-telefooncentrale via
MCP: contacten en lijsten opzoeken, aanmaken, wijzigen en verwijderen, plus de
recente gesprekken.

## Waarom dit strenger staat dan de Postbus

**Xelion heeft geen prullenbak.** Bij de Postbus is verwijderen een verplaatsing
naar de prullenbakmap en dus terug te draaien. Hier is een verwijderd contact
onmiddellijk en definitief weg; de server kan niets terughalen. Daarom:

- `verwijderen` is een **apart recht**, los van `bijwerken`.
- De tool `contact_verwijderen` weigert zonder `bevestigd=true`, en geeft bij de
  eerste aanroep terug welk contact er weg zou gaan.
- Wat er verdween wordt eerst opgehaald en in het logboek gezet. Dat is de enige
  vorm van terugvinden die er is.
- Er ligt een noodrem bovenop (`XELION_MCP_VERWIJDEREN`), standaard uit.

**Wijzigingen raken iedereen.** Een contact dat je hernoemt verschijnt meteen op
het belscherm van alle collega's.

## Rechten

Vier rechten, per persoon of per Authentik-groep, in `~/xelion-config/rechten.yaml`
op de VM (buiten git, read-only gemount op `/config`, elke vijf seconden
herlezen):

| Recht | Wat het opent |
|---|---|
| `lezen` | contacten zoeken en opvragen, lijsten, gesprekken |
| `aanmaken` | een contact of lijst toevoegen |
| `bijwerken` | een contact wijzigen, lijstleden toevoegen of afhalen |
| `verwijderen` | een contact **definitief** weggooien |

**Dicht tenzij opengezet.** Staat iemand er niet in, dan mag hij niets, ook niet
lezen. Een leeg of kapot bestand geeft niemand rechten; dat is met opzet, zodat
een typefout de centrale nooit per ongeluk openzet. Persoon en groep tellen bij
elkaar op.

Daarboven liggen drie noodremmen in de stack-`.env`: `XELION_MCP_AANMAKEN`,
`XELION_MCP_BIJWERKEN` en `XELION_MCP_VERWIJDEREN`. Staat er een niet op `ja`,
dan kan niemand dat, ongeacht `rechten.yaml`. Zo zet je het in een keer stil
zonder aan de rechten te komen. Lezen kent geen noodrem.

## De elf tools

Lezend: `ik`, `contact_zoeken`, `contact`, `lijsten`, `gesprekken`.

Wijzigend: `contact_aanmaken`, `contact_bijwerken`, `lijst_aanmaken`,
`lijst_toevoegen`, `lijst_afhalen`.

Ingrijpend: `contact_verwijderen`.

Elke tool toetst zijn eigen recht met `config.eisen()`. `test_rechten.py` doet
daar een ast-toets op: een wijzigende tool die dat vergeet laat de testsuite
falen. Beginnen doe je met `ik`, die zegt wat de ingelogde persoon mag.

## Let op: er is een tweede schrijver

De contactsync (`app-contactsync`, repo `google-xelion-sync`) schrijft sinds juli
2026 contacten vanuit Google naar diezelfde centrale. Twee schrijvers kunnen
elkaar overschrijven. Een contact dat door de sync beheerd wordt hoor je in
Google te wijzigen, niet hier; de server-instructie zegt Claude dat ook.

## Opbouw

- `xelionbron.py` - de client naar Xelion (login, sessievernieuwing, retries),
  gemodelleerd naar `contactsync/app/xelion_client.py` die dit al in productie doet
- `config.py` - de rechten, met de noodremmen
- `tools.py` - de elf tools; hier staat de inhoud
- `mcp_server.py` - de OAuth- en MCP-mantel, samengesteld uit `post/mcp_server.py`
  zodat er geen tweede variant van die code ontstaat
- `app.py` - Flask: beheerpagina achter SSO plus de MCP-registratie

Service `app-xelion`:3019, nginx `59-xelion.conf.template`, Authentik via
`scripts/add-xelion-app.py` (tegelgroepen `xelion`, `admin`, `manager`).

## Koppelen

Adres: `https://xelion.globaal.be/mcp`. Heeft de collega een eigen
Claude-account, dan koppelt hij als connector. Delen collega's een account, dan
lokaal per Windows-profiel; die werkwijze staat in `docs/POSTBUS-KOPPELEN.md` en
geldt hier onveranderd.

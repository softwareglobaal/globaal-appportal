# RenoVision via Claude (MCP)

Collega's passen hun **eigen kopie** van RenoVision aan vanuit Claude: code
lezen en doorzoeken, wijzigen, vastleggen in git en opnieuw uitrollen.

Eén dienst voor iedereen. Wie je bent bepaalt in welke kopie je terechtkomt;
dat is niet in te stellen en er is geen gereedschap waarmee je een andere kopie
kunt aanwijzen.

| | |
|---|---|
| Adres | `https://renovision-mcp.globaal.be/mcp` |
| Draait als | systemd `renovision-mcp` op de host, `172.17.0.1:8110` |
| Code | deze map (stack-repo), VM-checkout `~/appportal/renovision-mcp` |
| Vhost | `nginx/templates/67-renovision-mcp.conf.template` |
| Toegang | `scripts/add-renovision-mcp.py` |

## Wie komt waar uit

De naamconventie die `renovision-kopie.sh` al aanhoudt is hier de regel:
gebruiker `marise` → `~/globaal-renovision-marise` → `renovision-marise.globaal.be`.
Beheerders (`akadmin`, `samad`) komen op de admin-kopie uit. Wie geen eigen
kopie heeft krijgt geen toegang; er wordt nooit teruggevallen op de hoofdmap.

Een nieuwe collega heeft dus niets nieuws hier nodig: `renovision-kopie.sh
<naam> <poort>` plus `add-renovision-<naam>-app.py` en het werkt.

## Het gereedschap

Oriënteren en lezen: `werkruimte`, `bestanden`, `lees`, `zoek`.
Wijzigen: `vervang` (het gewone geval), `schrijf`, `verwijder`.
Vastleggen: `wijzigingen`, `vastleggen`, `geschiedenis`, `terugdraaien`.
Draaien: `uitrollen`, `logboek`.

De gebruikelijke gang is: `werkruimte` → `zoek` → `lees` → `vervang` →
`wijzigingen` → `vastleggen` → `uitrollen` → `logboek`.

## De grenzen, en waarom

**Alleen de eigen kopie.** Elk pad wordt via `realpath` getoetst, dus ook een
symlink komt niet buiten de map. Getest in `test_werkruimte.py`.

**Schrijven mag in `backend/`, `frontend/`, `tests/` en de documentatie.**
Niet in `docker-compose.yml` en `deploy/`: een compose-bestand kan een host-map
in een container hangen en `deploy/*.sh` draait als `ubuntu` op de host. Via
allebei zou een tekstwijziging in Claude de VM zelf kunnen overnemen. Dat is
beheerderswerk.

**`.env` is niet leesbaar en niet schrijfbaar.** Daar staat de
`ANTHROPIC_API_KEY` in platte tekst. `.env.example` mag wel.

**Vastleggen gaat naar een eigen tak** (`werk/<naam>`), nooit naar `main`, en
alleen de app-mappen worden meegenomen — in elke kopie staat een losse,
niet-getrackte kopie van de repo die niet in de geschiedenis hoort.
`terugdraaien` maakt een tegen-commit en wist nooit geschiedenis.

**Bouwen doet er één tegelijk**, over alle kopieën heen, en niet boven een
belasting van 25 (`RENOVISION_MAX_BELASTING`). Deze VM heeft 2 vCPU; in
augustus 2026 lag het platform zeven minuten plat toen er te veel tegelijk
draaide.

**Een kopie onder een auto-deploy-timer kan niet gewijzigd worden.**
`deploy/autodeploy.sh` doet elke twee minuten `git reset --hard origin/<tak>`;
werk zou binnen twee minuten verdwijnen. De dienst weigert dan te schrijven en
zegt waarom. Dat raakt nu `~/globaal-renovision` (timer `renovision-deploy`) en
`~/globaal-renovision-mehdi` (timer `renovision-mehdi-deploy`). Wil Mehdi via
Claude werken, dan moet die timer uit:

```bash
sudo systemctl disable --now renovision-mehdi-deploy.timer
```

## Instellen

`~/renovision-mcp.env` op de VM (niet in git):

```
MCP_SECRET=<lange willekeurige tekst>     # tekent de OAuth-tokens
MCP_TOKEN=<lange willekeurige tekst>      # optioneel, vaste sleutel; komt op de admin-kopie uit
MCP_BASIS=https://renovision-mcp.globaal.be
```

Zonder `MCP_SECRET` en `MCP_TOKEN` geeft `/mcp` een 404: de koppeling bestaat
dan simpelweg niet.

## Uitrollen

```bash
cd ~/appportal && git pull
python3 -m venv renovision-mcp/.venv && renovision-mcp/.venv/bin/pip install -q -r renovision-mcp/requirements.txt
sudo cp renovision-mcp/renovision-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now renovision-mcp
sh scripts/ak-exec.sh scripts/add-renovision-mcp.py
docker compose up -d --force-recreate nginx
```

Controle: `curl -s http://172.17.0.1:8110/gezond` toont de gevonden
werkruimtes.

## Koppelen in Claude

claude.ai → Instellingen → Connectors → aangepaste connector op
`https://renovision-mcp.globaal.be/mcp`. Er volgt een SSO-login; die bepaalt de
werkruimte.

Voor Claude Code, met de vaste sleutel:

```bash
claude mcp add --transport http renovision https://renovision-mcp.globaal.be/mcp --header "Authorization: Bearer $MCP_TOKEN"
```

## Tests

```bash
cd ~/appportal/renovision-mcp && .venv/bin/python -m pytest -q
```

## Valkuilen die dit al gekost heeft

**Geen `proxy_buffers` in de vhost.** De forward-auth-snippet zet die al en
nginx weigert een dubbele directive; op 31-08-2026 startte nginx daardoor niet
meer en lag het hele platform plat. Controleer na elke vhost-wijziging
`docker exec appportal-nginx-1 nginx -t`.

**ufw moet poort 8110 doorlaten vanaf de docker-netwerken.** Zonder die regel
loopt elk verzoek in een time-out in plaats van een nette 502:

```bash
sudo ufw allow from 172.16.0.0/12 to any port 8110 proto tcp comment 'docker -> renovision-mcp'
```

**Docker reageert onder belasting traag.** `docker logs` deed er op deze VM
meer dan twee minuten over terwijl het logbestand 28 KB was. Alle
docker-aanroepen hebben daarom een korte tijdslimiet en melden de vertraging in
plaats van te blijven hangen.

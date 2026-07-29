# Agents-besturingscentrum (agents.globaal.be)

De tegel die het agent-team toont: elke agent als kaart met live status,
mandaat, gereedschap en grenzen. Bewust zelfstandig gehouden: een eigen
SQLite in het datavolume (`agents-data/agents.db`), geen
database-credential. Compose-service `app-agents` (poort 3020) in de
stack-repo, map `agents/`.

## Wie de tegel ziet

Forward-auth met de groepen `admin`, `manager` en `agents`. Let op: in de
groep `agents` zitten ook mensen buiten het beheer (nu: siyan). Daarom is
de harde regel: **op deze tegel staat alleen werkstatus, nooit inhoud**.
Geen kandidaatgegevens, geen klantnamen, geen bedragen; tellingen en
neutrale taakomschrijvingen zijn de grens.

## De kaart-checklist: wat elke agent op de tegel MOET hebben

Elke nieuwe agent krijgt twee dingen in `app.py`, allebei verplicht en
volledig:

1. **Een teamregel in `TEAM`**: `naam` (kort, kleine letters, met
   koppelteken), `label` (weergavenaam; bij een niet-Globaal-agent de
   eigenaar erbij, zoals "HR-agent (Elevait)"), `type` (groepering) en
   `rol` (een regel, wat hij doet).
2. **Een blok in `DETAILS`** met alle vijf onderdelen:
   - `mandaat`: wat hij doet en voor wie, en dat de mens beslist waar dat
     zo is.
   - `mag`: wat hij zelfstandig mag opleveren of doen.
   - `grenzen`: wat hij nooit doet. Neem hier ook de zichtbaarheidsregel
     op als de agent met gevoelige data werkt ("deze tegel toont alleen
     werkstatus").
   - `cadans`: hoe vaak hij draait of wanneer hij wordt aangeroepen. Houd
     dit synchroon met de echte instelling (interval in de omgeving van de
     agent).
   - `tools`: de ECHTE gereedschapslijst, geen marketing. Bron: de
     frontmatter van het rolbestand (rollenbibliotheek) of de imports en
     aanroepen in de agentcode. Vermeld ook wat de agent bewust NIET kan
     als dat definierend is (voorbeeld HR-agent: "bewust geen
     mailgereedschap: versturen kan technisch niet").

Zonder `DETAILS`-blok valt een kaart terug op `DETAIL_STANDAARD`
("nog niet gekoppeld"); dat is een tijdelijke staat, geen eindsituatie.

## Hartslag-contract

Agents melden hun status met `POST /agent-status` (deze ene route passeert
de SSO; nginx laat hem door, de app controleert de header
`X-Agents-Token` tegen `AGENTS_TOKEN`).

```json
{
  "naam": "elevait-hr",
  "status": "waakt",
  "taak": "korte neutrale taakomschrijving",
  "detail": "laatste ronde: 1 sollicitaties bekeken, 0 nieuw beoordeeld",
  "tokens": 1234
}
```

- `status`: `rust`, `waakt`, `actief`, `klaar` of `fout`.
- `taak` en `detail`: neutraal en zonder inhoudelijke gegevens (zie de
  zichtbaarheidsregel hierboven). `tokens` is optioneel.
- Intern melden gaat rechtstreeks op het appnet:
  `http://app-agents:3020/agent-status`; extern via
  `https://agents.globaal.be/agent-status`.
- Een agent hoort bij de start te melden, na elke werkronde, en bij een
  fout met status `fout` plus een neutrale detailregel.

**Stilte-detectie**: geen recente hartslag maakt een kaart "stil".
Drempels in `roster()`: `actief` na 60 minuten, `waakt` na 150 minuten
(ruim twee gemiste uurlijkse beats), `klaar`/`fout` na 24 uur. Wijzigt de
cadans van een agent wezenlijk, controleer dan of deze drempels nog
kloppen.

## Voorstellen (mens-in-de-lus)

Een agent kan bij een probleem een benoemd runbook voorstellen
(`voorstel` in de hartslag-payload). De gebruiker keurt goed of weigert op
de tegel; uitvoering gebeurt nooit hier maar door de aparte
host-uitvoerder (`~/agents/globaal-agents/runner/uitvoerder.py`) die tegen
een allowlist valideert. Deze app legt alleen beslissing en uitkomst vast.

## Nieuwe agent toevoegen, samengevat

1. Teamregel + volledig `DETAILS`-blok in `app.py` (checklist hierboven).
2. Hartslag inbouwen in de agent zelf (contract hierboven); token via de
   omgeving van de agent (`AGENTS_TOKEN`, waarde staat in de VM-.env's).
3. Inline scripts van gewijzigde templates renderen en door V8 halen
   (huisregel 3) voordat er gepusht wordt.
4. `docker compose up -d --build app-agents` op de VM na de pull.
5. Verifieren: kaart zichtbaar, hartslag komt binnen, en geen gevoelige
   inhoud op de pagina.

Huidige bezetting: onderhoudsagent (gezondheidsketen), het bouwteam
(architect, bouwer, reviewer, verifier; rollenbibliotheek `.claude/agents`),
de HR-agent van Elevait (werving) en de finance-agent van Elevait
(uitgavenregister); beide Elevait-agents leven in de repo elevaitnv-website,
map `intern/`.

Besluit: 21 aangenomen (X1: A1 aanpassen. Gebruik OA; X2: A2 ja, met aanpassing.; X3: A3 aanpassen. Zes zoekop; X4: A4 aanpassen. Vijftien m; X5: A5 aanpassen. Geen termi; X6: A6 uitbreiden met tests; X7: A7 ja. Eén MOVA-proef,; X8: Tokenopslag: niet in ged; G1: A1 (Abonnement en harde; G2: A2 (Eigen MCP-leestool) ; G3: A3 (Zoeken en Linkextrac; G5: A5 & A7 (Token-inrichtin; G7: Risico-inventarisatie (V; K1: A1, abonnement en nooit; K2: A2, eigen leestool via; K3: A3, zoeken: aanpassen.; K4: A4, grenzen: ja, met; K5: A5, token zetten: aanpas; K6: A6 en A7, tests; K7: Vraag 3, risico's.; K8: Vraag 4, waar het); 2 afgewezen.
## Voor Mehdi
- Er is geen keuze voor jou open.

## Stemtabel
| Punt | Codex | Gemini | Claude | Uitslag | Besluit |
| --- | --- | --- | --- | --- | --- |
| X1 | eens | eens | eens | 3-0 | aangenomen |
| X2 | eens | eens | eens | 3-0 | aangenomen |
| X3 | eens | eens | eens | 3-0 | aangenomen |
| X4 | eens | eens | eens | 3-0 | aangenomen |
| X5 | eens | eens | eens | 3-0 | aangenomen |
| X6 | eens | eens | eens | 3-0 | aangenomen |
| X7 | eens | eens | eens | 3-0 | aangenomen |
| X8 | eens | eens | eens | 3-0 | aangenomen |
| G1 | eens | eens | eens | 3-0 | aangenomen |
| G2 | eens | eens | eens | 3-0 | aangenomen |
| G3 | eens | eens | oneens | 2-1 | aangenomen |
| G4 | oneens | eens | oneens | 1-2 | afgewezen |
| G5 | oneens | eens | eens | 2-1 | aangenomen |
| G6 | oneens | oneens | oneens | 0-3 | afgewezen |
| G7 | eens | eens | eens | 3-0 | aangenomen |
| K1 | eens | eens | eens | 3-0 | aangenomen |
| K2 | eens | eens | eens | 3-0 | aangenomen |
| K3 | eens | eens | eens | 3-0 | aangenomen |
| K4 | eens | eens | eens | 3-0 | aangenomen |
| K5 | eens | eens | eens | 3-0 | aangenomen |
| K6 | eens | eens | eens | 3-0 | aangenomen |
| K7 | eens | eens | eens | 3-0 | aangenomen |
| K8 | eens | eens | eens | 3-0 | aangenomen |

## Besluitenlijst vóór stemming
- X1: A1 aanpassen. Gebruik OAuth en stop hard bij een ontbrekend token of verkeerde `apiKeySource`. Beperk Claude bovendien tot uitsluitend `WebSearch` en de eigen MCP-leestool. `--strict-mcp-config` blokkeert namelijk geen ingebouwde Bash-, Edit- of WebFetch-tools. Gebruik `--restricted --tools WebSearch`; kies modelalias `opus` in plaats van een mogelijk veranderende modelcode. OAuth voor geautomatiseerde omgevingen is officieel ondersteund.
  Techniek voor Claude: `aankoop/onderzoek.py:266-330` - SDK vervangen; omgeving opschonen; init én eindstatus controleren; nooit API-terugval. [Claude-documentatie](https://code.claude.com/docs/en/env-vars)
- X2: A2 ja, met aanpassing. Kies de eigen MCP-leestool. Eén opgehaalde tekst wordt dan zowel door Claude als door de controle gebruikt. WebFetch plus nalezen kan twee verschillende paginaversies opleveren. Blokkeer wel localhost, metadata-adressen, privé-IP’s, vreemde protocollen en omleidingen daarnaartoe. Bewaar exact de teruggegeven, genormaliseerde tekst per URL.
  Techniek voor Claude: `aankoop/aanbod.py:201-230` - dezelfde paginatekst blijven gebruiken; MCP voorzien van SSRF-grendel en limiet na HTML-naar-tekstextractie.
- X3: A3 aanpassen. Zes zoekopdrachten is goed. Het uitlezen van “Links” mag pas worden aangenomen nadat één echte stream-json-uitvoer als testfixture is vastgelegd. Alleen prijzen uit de titel blijven bruikbaar.
  Techniek voor Claude: `aankoop/onderzoek.py:162-177` - parser baseren op gemeten CLI-uitvoer; PreToolUse-teller hard laten weigeren vanaf zoekactie zeven.
- X4: A4 aanpassen. Vijftien minuten past niet: de agentronde duurt maximaal 480 seconden en de bovenliggende runner stopt na 540 seconden. Gebruik maximaal de resterende rondetijd, praktisch ongeveer zeven minuten, en beëindig de hele procesgroep inclusief MCP-kindproces.
  Techniek voor Claude: `prijsonderzoeker.py:39-42,146-159`; `regisseur.py:507-551` - timeout koppelen aan bestaande deadline.
- X5: A5 aanpassen. Geen terminalopname gebruiken, want daarin kan het token alsnog staan. Rechtstreeks doorgeven zonder bestand of anders de bestaande verborgen plakmethode gebruiken. De browserklik is uitvoering van Mehdi’s bestaande besluit, geen nieuwe keuze.
- X6: A6 uitbreiden met tests voor privé-IP’s en redirects, toolbeperking, foutieve of ontbrekende init, procesgroep-opruiming, abonnementslimiet en de buitenste deadline.
- X7: A7 ja. Eén MOVA-proef, alleen nadat de uitvoer bewijst dat OAuth actief is en geen API-sleutel werd gebruikt. Abonnementsgebruik deelt wel Mehdi’s vijfuur- en weeklimiet met de app. [Limieten](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-max-or-ultra-plan)
- X8: Tokenopslag: niet in gedeeld `~/appportal/.env` en niet in `/etc` zonder eigen systemd-dienst. Gebruik een afzonderlijk bestand onder `~/appportal/mijnagents-data/`, rechten 600, dat alleen De Prijsonderzoeker leest.
- G1: A1 (Abonnement en harde API-grendel) - Akkoord met aanpassing.
  *Techniek voor Claude: `mijnagents-runner/aankoop/onderzoek.py:15` - controleer `claude --help` of `claude models` voor exacte Opus-flag; strip API-keys in `subprocess.Popen(..., env=schone_env)`.*
- G2: A2 (Eigen MCP-leestool) - Akkoord (Voorkeur boven WebFetch).
  *Techniek voor Claude: `mijnagents-runner/aankoop/aanbod.py:45` en `onderzoek.py:27` - implementeer stdio MCP `lees_pagina` die raw HTML->tekst synchroon wegschrijft naar het verificatiebestand `gelezen`.*
- G3: A3 (Zoeken en Linkextractie) - Akkoord.
  *Techniek voor Claude: `mijnagents-runner/aankoop/onderzoek.py:26` - PreToolUse-hook op `WebSearch` laten blokkeren bij teller > 6.*
- G4: A4 (Limieten en time-out) - Akkoord.
  *Techniek voor Claude: `mijnagents-runner/aankoop/onderzoek.py:34-35` - verwijder `PRIJZEN` en `ZOEK_DOLLAR`, implementeer `subprocess.run(..., timeout=900)`.*
- G5: A5 & A7 (Token-inrichting en proef) - Akkoord.
  *Techniek voor Claude: `scripts/claude-abonnement-naar-vm.sh` - OAuth token (`sk-ant-oat...`) wegschrijven met chmod 600.*
- G6: A6 & Vraag 4 (Tokenlocatie) - Akkoord met ~/appportal/.env.
  *Techniek voor Claude: `~/appportal/scripts/zet-claude-token.sh:1` - houd tokenopslag consistent in `~/appportal/.env`.*
- G7: Risico-inventarisatie (Vraag 3) - Geen extra beslissing voor Mehdi.
- K1: A1, abonnement en nooit de API: ja, met aanpassing.
  Techniek voor Claude: `aankoop/onderzoek.py` (subprocesomgeving als witte lijst), model als alias, init-bericht `apiKeySource == "none"` afdwingen.
- K2: A2, eigen leestool via MCP: ja, kies die.
  Techniek voor Claude: `--allowedTools` en `--disallowedTools WebFetch Bash Read Write` in `onderzoek.py`; MCP-server schrijft `gelezen` en geeft dezelfde string terug.
- K3: A3, zoeken: aanpassen.
  Techniek voor Claude: `onderzoek.py` stream-parser telt `tool_use` met naam WebSearch, `proc.kill()` en nood bij overschrijding.
- K4: A4, grenzen: ja, met een toevoeging.
- K5: A5, token zetten: aanpassen.
  Techniek voor Claude: `scripts/claude-abonnement-naar-vm.sh` met `read -s`, `umask 077`, `ssh` met stdin in plaats van een argument, zodat het token niet in `ps` verschijnt.
- K6: A6 en A7, tests en proef: ja.** Voeg een test toe dat de omgeving zonder token en mét `ANTHROPIC_API_KEY` in de ouderomgeving toch een nood geeft.
- K7: Vraag 3, risico's.
- K8: Vraag 4, waar het token staat: eigen bestand.
  Techniek voor Claude: `onderzoek.py` leest het token uit een eigen bestand; het script schrijft daar en niet in `.env`.

## Stap 3 - Drie eigen meningen
| Codex | Gemini | Claude |
| --- | --- | --- |
| BESLISSING: A1 tot A7 zijn goed van richting, maar moeten vóór uitvoering op vijf veiligheids- en tijdspunten worden aangepast.<br><br>X1. A1 aanpassen. Gebruik OAuth en stop hard bij een ontbrekend token of verkeerde `apiKeySource`. Beperk Claude bovendien tot uitsluitend `WebSearch` en de eigen MCP-leestool. `--strict-mcp-config` blokkeert namelijk geen ingebouwde Bash-, Edit- of WebFetch-tools. Gebruik `--restricted --tools WebSearch`; kies modelalias `opus` in plaats van een mogelijk veranderende modelcode. OAuth voor geautomatiseerde omgevingen is officieel ondersteund.  <br>Techniek voor Claude: `aankoop/onderzoek.py:266-330` - SDK vervangen; omgeving opschonen; init én eindstatus controleren; nooit API-terugval. [Claude-documentatie](https://code.claude.com/docs/en/env-vars)<br><br>X2. A2 ja, met aanpassing. Kies de eigen MCP-leestool. Eén opgehaalde tekst wordt dan zowel door Claude als door de controle gebruikt. WebFetch plus nalezen kan twee verschillende paginaversies opleveren. Blokkeer wel localhost, metadata-adressen, privé-IP’s, vreemde protocollen en omleidingen daarnaartoe. Bewaar exact de teruggegeven, genormaliseerde tekst per URL.  <br>Techniek voor Claude: `aankoop/aanbod.py:201-230` - dezelfde paginatekst blijven gebruiken; MCP voorzien van SSRF-grendel en limiet na HTML-naar-tekstextractie.<br><br>X3. A3 aanpassen. Zes zoekopdrachten is goed. Het uitlezen van “Links” mag pas worden aangenomen nadat één echte stream-json-uitvoer als testfixture is vastgelegd. Alleen prijzen uit de titel blijven bruikbaar.  <br>Techniek voor Claude: `aankoop/onderzoek.py:162-177` - parser baseren op gemeten CLI-uitvoer; PreToolUse-teller hard laten weigeren vanaf zoekactie zeven.<br><br>X4. A4 aanpassen. Vijftien minuten past niet: de agentronde duurt maximaal 480 seconden en de bovenliggende runner stopt na 540 seconden. Gebruik maximaal de resterende rondetijd, praktisch ongeveer zeven minuten, en beëindig de hele procesgroep inclusief MCP-kindproces.  <br>Techniek voor Claude: `prijsonderzoeker.py:39-42,146-159`; `regisseur.py:507-551` - timeout koppelen aan bestaande deadline.<br><br>X5. A5 aanpassen. Geen terminalopname gebruiken, want daarin kan het token alsnog staan. Rechtstreeks doorgeven zonder bestand of anders de bestaande verborgen plakmethode gebruiken. De browserklik is uitvoering van Mehdi’s bestaande besluit, geen nieuwe keuze.<br><br>X6. A6 uitbreiden met tests voor privé-IP’s en redirects, toolbeperking, foutieve of ontbrekende init, procesgroep-opruiming, abonnementslimiet en de buitenste deadline.<br><br>X7. A7 ja. Eén MOVA-proef, alleen nadat de uitvoer bewijst dat OAuth actief is en geen API-sleutel werd gebruikt. Abonnementsgebruik deelt wel Mehdi’s vijfuur- en weeklimiet met de app. [Limieten](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-max-or-ultra-plan)<br><br>X8. Tokenopslag: niet in gedeeld `~/appportal/.env` en niet in `/etc` zonder eigen systemd-dienst. Gebruik een afzonderlijk bestand onder `~/appportal/mijnagents-data/`, rechten 600, dat alleen De Prijsonderzoeker leest.<br><br>GRENS: geen | BESLISSING: Akkoord met overstap naar Claude-abonnement (CLAUDE_CODE_OAUTH_TOKEN via Claude Code CLI) en het weren van API-kosten (3-0 richting); voorstel A1 t/m A7 is technisch sluitend mits de modelnaam en MCP-leestool scherp worden afgesteld.<br><br>Voor Mehdi in gewone mensentaal:<br>De Prijsonderzoeker stopt direct met de betaalde Anthropic API en schakelt over naar je bestaande Claude-abonnement via de Claude Code CLI. Hierdoor betaal je 0 euro extra per zoekronde. Als een beveiliging per ongeluk toch een API-sleutel zou zien of als je abonnementslimiet bereikt is, stopt de agent direct uit voorzorg in plaats van stiekem geld te kosten.<br><br>G1. **A1 (Abonnement en harde API-grendel) - Akkoord met aanpassing.**<br>De omgevingsvariabelen `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` en `ANTHROPIC_BASE_URL` strikt weglaten uit het subproces-milieu. Controleer direct op `apiKeySource == "none"` in de init-stream van `claude -p`. Let op: verifieer of de model-alias `claude-opus-5-5` geldig is in Claude Code; gebruik anders `--model opus` of laat de CLI de standaard Opus-versie kiezen conform de abonnementsinstelling.<br>*Techniek voor Claude: `mijnagents-runner/aankoop/onderzoek.py:15` - controleer `claude --help` of `claude models` voor exacte Opus-flag; strip API-keys in `subprocess.Popen(..., env=schone_env)`.*<br><br>G2. **A2 (Eigen MCP-leestool) - Akkoord (Voorkeur boven WebFetch).**<br>Een eigen MCP-server via stdio met `lees_pagina(url)` is superieur aan Claude Code's ingebouwde WebFetch. WebFetch vat webpagina's samen met een submodel waardoor letterlijke prijzen, verzendvoorwaarden en specificaties vervormd raken of ontbreken. De eigen MCP-server levert de exacte paginatekst (afgekapt op 10.000 tokens) aan het model én slaat exact diezelfde buffer op in `gelezen` voor validatie door `aanbod.py`.<br>*Techniek voor Claude: `mijnagents-runner/aankoop/aanbod.py:45` en `onderzoek.py:27` - implementeer stdio MCP `lees_pagina` die raw HTML->tekst synchroon wegschrijft naar het verificatiebestand `gelezen`.*<br><br>G3. **A3 (Zoeken en Linkextractie) - Akkoord.**<br>WebSearch van Claude Code gebruiken binnen de bundel. De limiet van maximaal 6 zoekacties via PreToolUse-hook of wrapper afdwingen. Zoekresultaten parsen uit de structured output/links.<br>*Techniek voor Claude: `mijnagents-runner/aankoop/onderzoek.py:26` - PreToolUse-hook op `WebSearch` laten blokkeren bij teller > 6.*<br><br>G4. **A4 (Limieten en time-out) - Akkoord.**<br>Dollargetallen en kostenberekeningen verwijderen. Harde subproces-timeout op 15 minuten zetten. Bij HTTP 429 of "usage limit reached" van Claude Code een status "nood: abonnementslimiet" wegschrijven, nooit terugvallen.<br>*Techniek voor Claude: `mijnagents-runner/aankoop/onderzoek.py:34-35` - verwijder `PRIJZEN` en `ZOEK_DOLLAR`, implementeer `subprocess.run(..., timeout=900)`.*<br><br>G5. **A5 & A7 (Token-inrichting en proef) - Akkoord.**<br>Het hulpscript `scripts/claude-abonnement-naar-vm.sh` op de laptop laten draaien zodat Mehdi via de browser autoriseert. Het token veilig overbrengen naar de VM zonder weergave in logs of terminal.<br>*Techniek voor Claude: `scripts/claude-abonnement-naar-vm.sh` - OAuth token (`sk-ant-oat...`) wegschrijven met chmod 600.*<br><br>G6. **A6 & Vraag 4 (Tokenlocatie) - Akkoord met ~/appportal/.env.**<br>Plaats `CLAUDE_CODE_OAUTH_TOKEN` in `~/appportal/.env` conform de bestaande standaard van `scripts/zet-claude-token.sh`. Dit voorkomt afwijkingen tussen services en vereist geen sudo/root-rechten op `/etc`.<br>*Techniek voor Claude: `~/appportal/scripts/zet-claude-token.sh:1` - houd tokenopslag consistent in `~/appportal/.env`.*<br><br>G7. **Risico-inventarisatie (Vraag 3) - Geen extra beslissing voor Mehdi.**<br>Het delen van het werkaccount tussen de desktop-app en de VM kan leiden tot tijdelijke rate limits (5-uurs vensters) bij intensief gelijktijdig gebruik. Dit is een operationele limiet, geen financiële grens.<br><br>GRENS: geen | BESLISSING: Ja, we gaan over op het abonnement via `claude -p` met `CLAUDE_CODE_OAUTH_TOKEN`. De richting van A1 tot A7 klopt. Ik pas A1, A3, A4 en A5 aan en kies bij A2 de eigen leestool. Dit is mijn mening zonder de andere twee gezien te hebben. Ik heb geen bestanden geopend en baseer me op de opdrachttekst.<br><br>**K1. A1, abonnement en nooit de API: ja, met aanpassing.**<br>Wat Mehdi merkt: er komt geen rekening meer, ook niet als er per ongeluk een sleutel in de omgeving staat.<br>- Het model `claude-opus-5-5` is niet geverifieerd. Gebruik een alias zoals `opus` of toets eerst met een korte proef. Een verkeerde naam kost een mislukte ronde.<br>- De grendel op `apiKeySource` is goed. Voeg toe dat de omgeving van het subproces een lege basis krijgt (alleen PATH, HOME en het token), zodat geen enkele andere variabele meekomt.<br>- `claude auth status` op de VM staat op `loggedIn: false`. Het token via de omgeving moet dus echt gemeten worden vóór alles.<br>Techniek voor Claude: `aankoop/onderzoek.py` (subprocesomgeving als witte lijst), model als alias, init-bericht `apiKeySource == "none"` afdwingen.<br><br>**K2. A2, eigen leestool via MCP: ja, kies die.**<br>Wat Mehdi merkt: de prijzen en citaten in het verslag zijn echt nagekeken tegen de paginatekst, niet tegen een samenvatting van een klein model.<br>- De WebFetch-route met een nalezing door de runner leest elke pagina twee keer. De twee teksten kunnen verschillen (andere tijd, andere cookie of geo-versie), en dan toetst de code iets anders dan het model zag.<br>- Zet WebFetch uit met `--disallowedTools WebFetch` en geef alleen `mcp__...__lees_pagina` en WebSearch vrij. Anders kan het model om je leestool heen.<br>- Bevestig met de 10.000 tokens dat de afkapping dezelfde tekst oplevert in model en bestand.<br>Techniek voor Claude: `--allowedTools` en `--disallowedTools WebFetch Bash Read Write` in `onderzoek.py`; MCP-server schrijft `gelezen` en geeft dezelfde string terug.<br><br>**K3. A3, zoeken: aanpassen.**<br>Wat Mehdi merkt: de zoeklimiet houdt, maar een hook kan stil falen.<br>- Een PreToolUse-hook via `--settings` botst met `--setting-sources ""`. Test dat beide samen werken, want anders telt de hook niet.<br>- Betrouwbaarder: de runner telt zelf de `tool_use`-blokken in de stream-json en breekt het subproces af bij de zevende. Dan is de hook niet nodig.<br>Techniek voor Claude: `onderzoek.py` stream-parser telt `tool_use` met naam WebSearch, `proc.kill()` en nood bij overschrijding.<br><br>**K4. A4, grenzen: ja, met een toevoeging.**<br>- Voeg een limiet toe op het aantal beurten via de runner (tel assistentberichten), omdat `--max-turns` ontbreekt.<br>- Een limietfout herken je aan de foutmelding in de stream. Test dit met een nepbericht.<br><br>**K5. A5, token zetten: aanpassen.**<br>- Het token uit een terminalopname halen is breekbaar. Het script moet de opname direct verwijderen. Dat is een verwijdering van een eigen tijdelijk bestand en valt niet onder Mehdi's toestemming.<br>- Alternatief: Mehdi plakt het token één keer in een verborgen prompt (`read -s`) in het script. Dat is eenvoudiger en veiliger dan opname-parsing.<br>Techniek voor Claude: `scripts/claude-abonnement-naar-vm.sh` met `read -s`, `umask 077`, `ssh` met stdin in plaats van een argument, zodat het token niet in `ps` verschijnt.<br><br>**K6. A6 en A7, tests en proef: ja.** Voeg een test toe dat de omgeving zonder token en mét `ANTHROPIC_API_KEY` in de ouderomgeving toch een nood geeft.<br><br>**K7. Vraag 3, risico's.**<br>- De limieten van het abonnement zijn gedeeld met wat Mehdi in de app doet. Een lange ronde kan hem tijdelijk blokkeren. Stel de ronde buiten werkuren in en meld de limiet duidelijk.<br>- Gebruiksvoorwaarden: automatisch gebruik van een persoonlijk abonnement voor een eigen agent is bij Claude Code via `setup-token` bedoeld gebruik. Controleer dit wel in de actuele voorwaarden, want ik heb het niet zelf nagekeken.<br>- Het token geldt ongeveer een jaar. Zet een herinnering op een datum.<br>- Mehdi hoeft niets te beslissen. Zijn besluit dekt dit al.<br><br>**K8. Vraag 4, waar het token staat: eigen bestand.**<br>Wat Mehdi merkt: als `.env` lekt of in een andere agent terechtkomt, ligt het abonnementstoken niet mee op straat.<br>- `~/appportal/.env` wordt door de andere agents gelezen, samen met de API-sleutel. Een eigen bestand, bijvoorbeeld `~/.config/prijsonderzoeker/token.env` met rechten 600, houdt het gescheiden. Als `/etc` niet beschikbaar is voor deze dienst, is de thuismap goed genoeg.<br>- Zo blijft `ANTHROPIC_API_KEY` ook uit de omgeving van het subproces.<br>Techniek voor Claude: `onderzoek.py` leest het token uit een eigen bestand; het script schrijft daar en niet in `.env`.<br><br>GRENS: geen |

## Stap 4 - Overleg
### Ronde 1: Codex
BESLISSING: Er is 2-op-3 akkoord voor OAuth, de eigen leestool, circa zeven minuten looptijd, veilige tokeninvoer en een apart tokenbestand. Mehdi hoeft niets te beslissen.

1. Claude werkt uitsluitend via Mehdi’s abonnement. Bij een ontbrekend token, verkeerde aanmeldbron of abonnementsgrens stopt de ronde. Gebruik alleen CLI-opties die deze geïnstalleerde versie aantoonbaar ondersteunt.  
Techniek voor Claude: `aankoop/onderzoek.py:266-330` - schone omgeving, `apiKeySource == "none"`, tool-allowlist en geen API-terugval.

2. De eigen MCP-leestool is beter dan WebFetch plus nalezen. Model en controle krijgen exact dezelfde tekst. Voeg bescherming toe tegen privé-adressen, redirects en afwijkende protocollen.  
Techniek voor Claude: `aankoop/aanbod.py:201-230` - één genormaliseerde tekstbuffer opslaan en teruggeven.

3. De zevende zoekactie moet vóór uitvoering worden geweigerd. Gebruik daarom de hook als primaire grens en de stream-parser als extra controle. Leg eerst echte CLI-uitvoer vast als testfixture.  
Techniek voor Claude: `aankoop/onderzoek.py:162-177` - hook en parser testen met dezelfde stream-json-fixture.

4. Vijftien minuten is onmogelijk binnen de bestaande deadlines. Gebruik de werkelijk resterende tijd, ongeveer zeven minuten, en ruim de hele procesgroep op.  
Techniek voor Claude: `prijsonderzoeker.py:39-42,146-159`; `regisseur.py:507-551`.

5. Geen terminalopname. Gebruik verborgen invoer en stuur het token via stdin. Bewaar het in een afzonderlijk bestand met rechten 600, niet in de gedeelde `.env`. De tokenvernieuwing na ongeveer een jaar is onderhoud, geen beslissing voor Mehdi.  
Techniek voor Claude: `scripts/claude-abonnement-naar-vm.sh` - `read -s`, `umask 077`, stdin; tokenbestand onder `~/appportal/mijnagents-data/`.

STEMBLOK: Codex
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
X6: eens
X7: eens
X8: eens
G1: eens
G2: eens
G3: eens
G4: oneens
G5: oneens
G6: oneens
G7: eens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
K6: eens
K7: eens
K8: eens
EINDE STEMBLOK
### Ronde 1: Gemini
BESLISSING: Akkoord om De Prijsonderzoeker direct over te zetten naar Mehdi's Claude-abonnement via `claude -p` met `CLAUDE_CODE_OAUTH_TOKEN` (3-0 richting); we voeren de 5 aangescherpte veiligheids-, isolatie- en time-outvoorwaarden van Codex en Claude integraal door.

Voor Mehdi in gewone mensentaal:
De Prijsonderzoeker stopt direct met de betaalde API en gaat draaien op je eigen Claude-abonnement. Dat kost 0 euro extra per zoekronde. Claude krijgt strikt alleen toegang tot het web via een beveiligde leestool (geen toegang tot bestanden of de server) en stopt automatisch zodra je abonnementslimiet bereikt is, zonder ooit terug te vallen op betaalde API-kosten.

1. **Abonnement, isolatie en tools (X1, G1, K1):**
Wat Mehdi merkt: de agent gebruikt je eigen abonnement en kan nooit per ongeluk serverbestanden inzien of betaalde API-sleutels aanspreken.
Claude Code wordt gestart met een minimale omgevingswitte lijst (alleen PATH, HOME en `CLAUDE_CODE_OAUTH_TOKEN`), `--restricted --tools WebSearch` (zonder Bash/Edit/Read) en het model ingesteld op alias `opus`.
*Techniek voor Claude: `aankoop/onderzoek.py:270-330` - schone subprocesomgeving zonder `ANTHROPIC_*`; controleer `apiKeySource == "none"` in de init-stream en breek direct af bij ontbreken of afwijking.*

2. **Eigen MCP-leestool met SSRF-beveiliging (X2, G2, K2):**
Wat Mehdi merkt: prijzen en productspecificaties worden betrouwbaar en letterlijk gecontroleerd, precies zoals ze op de webpagina staan.
WebFetch van Claude Code wordt geblokkeerd (`--disallowedTools WebFetch`). De eigen MCP-server via stdio levert de paginatekst direct aan het model en bewaart exact dezelfde tekst in `gelezen` voor validatie door `aanbod.py`. Lokale IP-adressen (127.0.0.1, 10.x, 192.168.x en cloud metadata) en vreemde protocollen worden hard geweigerd.
*Techniek voor Claude: `aankoop/aanbod.py:201-230` en `onderzoek.py:270-291` - implementeer stdio MCP `lees_pagina` met SSRF-grendel en synchrone opslag naar `gelezen`.*

3. **Zoeklimiet en tijdgrenzen (X3, X4, G3, G4, K3, K4):**
Wat Mehdi merkt: zoekopdrachten lopen niet oneindig door en de agent blokkeert de wachtrij nooit langer dan toegestaan.
WebSearch is beperkt tot maximaal 6 beurten. De runner telt zelf de `tool_use` blokken in de stream en breekt af bij overschrijding. Omdat De Regisseur een buitenste timeout van 540s heeft (`regisseur.py:507-551`), mag het subproces geen 15 minuten draaien maar maximaal de resterende rondetijd (ca. 420 seconden, met beëindiging van de hele procesgroep).
*Techniek voor Claude: `prijsonderzoeker.py:40,146-159` en `regisseur.py:507-551` - koppel subproces-timeout aan `deadline - time.monotonic()`; gebruik `os.killpg` bij time-out.*

4. **Veilige tokenopslag (X5, X8, G5, G6, K5, K8):**
Wat Mehdi merkt: je persoonlijke abonnementstoken staat veilig afgeschermd en lekt nooit naar logs of andere agents.
Het token wordt via `scripts/claude-abonnement-naar-vm.sh` met een verborgen prompt (`read -s`) opgevraagd en via stdin met chmod 600 weggeschreven naar een geïsoleerd bestand (`~/appportal/mijnagents-data/claude-token.env`), niet in het gedeelde `~/appportal/.env`.
*Techniek voor Claude: `scripts/claude-abonnement-naar-vm.sh` - stdin/`read -s` en schrijf naar `~/appportal/mijnagents-data/claude-token.env` met rechten 600.*

5. **Tests en proef (X6, X7, K6):**
Wat Mehdi merkt: er draait pas een echte proefzoektocht als alle beveiligingstests slagen en bewezen is dat er 0 API-kosten zijn.
*Techniek voor Claude: tests toevoegen voor SSRF-blokkade, `apiKeySource == "none"`, procesgroep-kill en het afhandelen van de abonnementslimiet.*

GRENS: geen

STEMBLOK: Gemini
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
X6: eens
X7: eens
X8: eens
G1: eens
G2: eens
G3: eens
G4: eens
G5: eens
G6: oneens
G7: eens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
K6: eens
K7: eens
K8: eens
EINDE STEMBLOK
### Ronde 1: Claude
BESLISSING: Eens met de overstap naar het abonnement en met Codex' aanpassingen (X1 tot X7). Bij de tokenlocatie kies ik Codex' aparte bestand (X8), niet `.env` (G6).

**Wat Mehdi merkt**
- De Prijsonderzoeker kost geen geld meer. Staat er toch een API-sleutel in de omgeving, of ontbreekt het token, dan stopt de ronde met een nood en rekent ze nooit af.
- De prijzen in het verslag worden nagekeken tegen de echte paginatekst. Model en controle lezen dezelfde tekst.
- Het token staat apart van de andere agents, die wel de API-sleutel gebruiken.
- Een ronde kan Mehdi's eigen vijfuurlimiet in de app raken. Dat is een gebruiksgrens, geen geldkeuze.

**Correctie op mijn eigen punten**
- K3: ik zei dat een hook botst met `--setting-sources ""`. Dat is niet gemeten. Codex wil de hook behouden, ik wilde de runner laten tellen. Beste is allebei: de runner telt `tool_use` in de stream (dat werkt altijd) en breekt af bij de zevende. De hook is optioneel.
- K2: Codex' `--tools WebSearch` is strakker dan mijn lijst met `--disallowedTools`. Een witte lijst is veiliger. Eerst met `claude --help` nagaan of `--restricted` en `--tools` bestaan in versie 2.1.286, want dat heb ik niet gezien.
- K7: ik noemde "ongeveer een jaar" geldigheid. Dat staat in de opdracht, dus herinnering op datum is goed. De gebruiksvoorwaarden zijn niet nagekeken. Dat blijft een controle, geen besluit voor Mehdi.

**Aanvulling**
- Codex' SSRF-grendel (privé-IP's, metadata-adres, redirects) miste ik. Goed punt voor de eigen leestool.
- Codex' tijdslimiet klopt: 15 minuten past niet binnen de 480 of 540 seconden van de runner. Gemini's `timeout=900` (G4) is dus fout.
- Gemini's `subprocess.run(timeout)` doodt het MCP-kindproces niet. Codex' procesgroep-opruiming is nodig.
- Een terminalopname (A5) kan het token bevatten. Ik ben het met Codex eens: verborgen plakken (`read -s`) of rechtstreeks doorgeven, via stdin en niet als argument.

**Oneens met Gemini**
- G1: de modelnaam moet een alias zijn, dat staat er wel bij. Akkoord daarmee.
- G3: een hook als enige teller is te zwak. De runner moet zelf tellen.
- G4: de 15 minuten zijn fout.
- G6: gedeeld `.env` is slechter dan een apart bestand.

Techniek voor Claude: `aankoop/onderzoek.py` - witte omgeving (PATH, HOME, token), `apiKeySource == "none"`, tool-witte lijst, teller op `tool_use`, procesgroep stoppen bij deadline. Token uit `~/appportal/mijnagents-data/` (600). Fixture van echte stream-json vastleggen vóór de "Links"-parser.

GRENS: geen

STEMBLOK: Claude
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
X6: eens
X7: eens
X8: eens
G1: eens
G2: eens
G3: oneens
G4: oneens
G5: eens
G6: oneens
G7: eens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
K6: eens
K7: eens
K8: eens
EINDE STEMBLOK

## Stap 5 - Eindconclusie
Schrijver: Codex

Beslissing: alle meerderheidsbesluiten worden zelfstandig uitgevoerd; Mehdi hoeft niets te beslissen.

- X1, X2, X3, X4, X5, X6, X7 en X8: aangenomen.
- G1, G2, G3, G5 en G7: aangenomen.
- G4 en G6: afgewezen.
- K1, K2, K3, K4, K5, K6, K7 en K8: aangenomen.
- Claude voert uit, test, zet live en controleert de werking.

### Voor Claude en Shaniel
Bezetting:
- Codex: gpt-5.6-sol · medium (voorgesteld)
- Gemini: gemini-3.8-flash · low (voorgesteld)
- Claude: claude-sonnet-5-5 · medium (voorgesteld)

Aangenomen herstelpunten (scriptmatig):
- **X1** (3-0): A1 aanpassen. Gebruik OAuth en stop hard bij een ontbrekend token of verkeerde `apiKeySource`. Beperk Claude bovendien tot uitsluitend `WebSearch` en de eigen MCP-leestool. `--strict-mcp-config` blokkeert namelijk geen ingebouwde Bash-, Edit- of WebFetch-tools. Gebruik `--restricted --tools WebSearch`; kies modelalias `opus` in plaats van een mogelijk veranderende modelcode. OAuth voor geautomatiseerde omgevingen is officieel ondersteund.
  Techniek voor Claude: `aankoop/onderzoek.py:266-330` - SDK vervangen; omgeving opschonen; init én eindstatus controleren; nooit API-terugval. [Claude-documentatie](https://code.claude.com/docs/en/env-vars)
- **X2** (3-0): A2 ja, met aanpassing. Kies de eigen MCP-leestool. Eén opgehaalde tekst wordt dan zowel door Claude als door de controle gebruikt. WebFetch plus nalezen kan twee verschillende paginaversies opleveren. Blokkeer wel localhost, metadata-adressen, privé-IP’s, vreemde protocollen en omleidingen daarnaartoe. Bewaar exact de teruggegeven, genormaliseerde tekst per URL.
  Techniek voor Claude: `aankoop/aanbod.py:201-230` - dezelfde paginatekst blijven gebruiken; MCP voorzien van SSRF-grendel en limiet na HTML-naar-tekstextractie.
- **X3** (3-0): A3 aanpassen. Zes zoekopdrachten is goed. Het uitlezen van “Links” mag pas worden aangenomen nadat één echte stream-json-uitvoer als testfixture is vastgelegd. Alleen prijzen uit de titel blijven bruikbaar.
  Techniek voor Claude: `aankoop/onderzoek.py:162-177` - parser baseren op gemeten CLI-uitvoer; PreToolUse-teller hard laten weigeren vanaf zoekactie zeven.
- **X4** (3-0): A4 aanpassen. Vijftien minuten past niet: de agentronde duurt maximaal 480 seconden en de bovenliggende runner stopt na 540 seconden. Gebruik maximaal de resterende rondetijd, praktisch ongeveer zeven minuten, en beëindig de hele procesgroep inclusief MCP-kindproces.
  Techniek voor Claude: `prijsonderzoeker.py:39-42,146-159`; `regisseur.py:507-551` - timeout koppelen aan bestaande deadline.
- **X5** (3-0): A5 aanpassen. Geen terminalopname gebruiken, want daarin kan het token alsnog staan. Rechtstreeks doorgeven zonder bestand of anders de bestaande verborgen plakmethode gebruiken. De browserklik is uitvoering van Mehdi’s bestaande besluit, geen nieuwe keuze.
- **X6** (3-0): A6 uitbreiden met tests voor privé-IP’s en redirects, toolbeperking, foutieve of ontbrekende init, procesgroep-opruiming, abonnementslimiet en de buitenste deadline.
- **X7** (3-0): A7 ja. Eén MOVA-proef, alleen nadat de uitvoer bewijst dat OAuth actief is en geen API-sleutel werd gebruikt. Abonnementsgebruik deelt wel Mehdi’s vijfuur- en weeklimiet met de app. [Limieten](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-max-or-ultra-plan)
- **X8** (3-0): Tokenopslag: niet in gedeeld `~/appportal/.env` en niet in `/etc` zonder eigen systemd-dienst. Gebruik een afzonderlijk bestand onder `~/appportal/mijnagents-data/`, rechten 600, dat alleen De Prijsonderzoeker leest.
- **G1** (3-0): A1 (Abonnement en harde API-grendel) - Akkoord met aanpassing.
  *Techniek voor Claude: `mijnagents-runner/aankoop/onderzoek.py:15` - controleer `claude --help` of `claude models` voor exacte Opus-flag; strip API-keys in `subprocess.Popen(..., env=schone_env)`.*
- **G2** (3-0): A2 (Eigen MCP-leestool) - Akkoord (Voorkeur boven WebFetch).
  *Techniek voor Claude: `mijnagents-runner/aankoop/aanbod.py:45` en `onderzoek.py:27` - implementeer stdio MCP `lees_pagina` die raw HTML->tekst synchroon wegschrijft naar het verificatiebestand `gelezen`.*
- **G3** (2-1): A3 (Zoeken en Linkextractie) - Akkoord.
  *Techniek voor Claude: `mijnagents-runner/aankoop/onderzoek.py:26` - PreToolUse-hook op `WebSearch` laten blokkeren bij teller > 6.*
- **G5** (2-1): A5 & A7 (Token-inrichting en proef) - Akkoord.
  *Techniek voor Claude: `scripts/claude-abonnement-naar-vm.sh` - OAuth token (`sk-ant-oat...`) wegschrijven met chmod 600.*
- **G7** (3-0): Risico-inventarisatie (Vraag 3) - Geen extra beslissing voor Mehdi.
- **K1** (3-0): A1, abonnement en nooit de API: ja, met aanpassing.
  Techniek voor Claude: `aankoop/onderzoek.py` (subprocesomgeving als witte lijst), model als alias, init-bericht `apiKeySource == "none"` afdwingen.
- **K2** (3-0): A2, eigen leestool via MCP: ja, kies die.
  Techniek voor Claude: `--allowedTools` en `--disallowedTools WebFetch Bash Read Write` in `onderzoek.py`; MCP-server schrijft `gelezen` en geeft dezelfde string terug.
- **K3** (3-0): A3, zoeken: aanpassen.
  Techniek voor Claude: `onderzoek.py` stream-parser telt `tool_use` met naam WebSearch, `proc.kill()` en nood bij overschrijding.
- **K4** (3-0): A4, grenzen: ja, met een toevoeging.
- **K5** (3-0): A5, token zetten: aanpassen.
  Techniek voor Claude: `scripts/claude-abonnement-naar-vm.sh` met `read -s`, `umask 077`, `ssh` met stdin in plaats van een argument, zodat het token niet in `ps` verschijnt.
- **K6** (3-0): A6 en A7, tests en proef: ja.** Voeg een test toe dat de omgeving zonder token en mét `ANTHROPIC_API_KEY` in de ouderomgeving toch een nood geeft.
- **K7** (3-0): Vraag 3, risico's.
- **K8** (3-0): Vraag 4, waar het token staat: eigen bestand.
  Techniek voor Claude: `onderzoek.py` leest het token uit een eigen bestand; het script schrijft daar en niet in `.env`.

Schrijverscontrole:
Gecontroleerd: alle punt-id's genoemd, geen tegenspraak met stemtabel, grenzen of bronnen.

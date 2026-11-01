# Overleg 14: De Prijsonderzoeker op Mehdi's Claude-abonnement in plaats van de API (01-11-2026)

Lees alleen; wijzig niets.

## Wat Mehdi zei (01-11-2026, in de chat, letterlijk)

"ik wil niet dat agent geld kost, ik wil dat agent zoals alle mijn andere agent met mijn eigen claude account werkt en
niet dat token en APi kosten met zich meebrengt! los het op"

Dat is een besluit, geen vraag. Het overleg gaat over het hoe.

## Gemeten

- `mijnagents-runner/aankoop/onderzoek.py` roept de Messages API aan met `ANTHROPIC_API_KEY` uit `~/appportal/.env`,
  met de servertools web_search en web_fetch. Proef 3 kostte 3,04 dollar (714k input in een aanvraag).
- Op de VM staat `~/.local/bin/claude` (Claude Code 2.1.286), maar `claude auth status` geeft `loggedIn: false`.
- Er is al een voorbeeld van een abonnementstoken op de VM: `~/appportal/scripts/zet-claude-token.sh` zet een token
  uit `claude setup-token` (begint met `sk-ant-oat`) als `CLAUDE_CODE_OAUTH_TOKEN` voor een systemd-dienst.
- `claude --bare` leest geen OAuth (alleen `ANTHROPIC_API_KEY`), dus niet bruikbaar. `--max-turns` staat niet in de
  hulp van deze versie.
- Claude Code geeft bij `-p` voorrang aan `ANTHROPIC_API_KEY` als die in de omgeving staat. Het init-bericht van
  `--output-format stream-json` toont `apiKeySource`.
- Claude Code's eigen WebFetch geeft niet de paginatekst terug maar een antwoord van een klein model over die pagina.
  De controles in `aankoop/aanbod.py` (prijs, verzendkost, V/Hz, modelcode, citaten) toetsen tegen de echte
  paginatekst (`gelezen`).
- Andere VM-agents (Regisseur, Mehdi-agent, Contractmaker, Ontwikkelaar, Levenscoach, Archivaris, Fathomwacht,
  Bouw) gebruiken ook de API-sleutel. Dat valt buiten dit overleg; ik meld het aan Mehdi als aparte taak.

## Voorstel van Claude 1

A1. **Abonnement, nooit de API.** `onderzoek.py` start `claude -p` als subproces op de VM, met `--output-format
stream-json --verbose`, `--model claude-opus-5-5`, `--no-session-persistence`, `--setting-sources ""` (geen
instellingen of hooks van de VM), `--strict-mcp-config`, in een lege tijdelijke map. De omgeving van het subproces
krijgt `CLAUDE_CODE_OAUTH_TOKEN` uit `~/appportal/.env` en NIET `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` of
`ANTHROPIC_BASE_URL`. Grendel in code: staat `apiKeySource` in het init-bericht op iets anders dan `none`, of
ontbreekt het token, dan stopt de ronde met een nood en valt ze nooit terug op de API. De `anthropic`-import en
de kostberekening in dollar verdwijnen uit de prijsagent; de nood boven 2 dollar ook.

A2. **Eigen leestool met de echte paginatekst.** Geen WebFetch van Claude Code. De runner geeft een eigen MCP-server
mee (stdio, eigen Python, geen extra pakket): tool `lees_pagina(url)`. Die haalt de pagina op vanaf de VM, maakt er
tekst van, kapt af op 10.000 tokens (ongeveer 40.000 tekens), geeft die tekst aan het model en schrijft dezelfde tekst
in een bestand in de tijdelijke map. Na zes geslaagde of mislukte lezingen antwoordt hij "leesgrens bereikt". Dat
bestand wordt `gelezen` voor `aanbod.py`: het model leest dus precies de tekst die de code nakijkt, zoals nu met
web_fetch.

A3. **Zoeken.** WebSearch van Claude Code blijft (het abonnement betaalt). Een PreToolUse-hook via `--settings`
telt de zoekopdrachten en weigert vanaf de zevende. `zoekresultaten` komt uit de lijst "Links" (titel en url) in het
resultaat; er zijn geen letterlijke citaten meer. Een rij in "Gezien, niet nagekeken" houdt dus alleen een prijs die
in de titel staat; anders valt ze weg (zoals besloten in controle 10).

A4. **Grenzen.** Geen dollargrens meer, wel: 6 zoek, 6 lees, een harde tijdslimiet van 15 minuten op het subproces
(daarna afgebroken met een nood), en het logboek bewaart beurten, tokens en de gebruikte tools. Het abonnement heeft
eigen limieten; een geweigerde aanvraag door een limiet wordt een nood "abonnementslimiet", geen API.

A5. **Token zetten zonder plakken.** Een script voor de laptop, `scripts/claude-abonnement-naar-vm.sh`: draait
`claude setup-token` (Mehdi klikt een keer op Authorize in de browser, met het werkaccount mch@ = Claude 1), leest het
token uit de terminalopname zonder het te tonen, schrijft het op de VM als `CLAUDE_CODE_OAUTH_TOKEN` in
`~/appportal/.env` (bestaande regel vervangen, rechten 600) en toetst met een korte `claude -p` op de VM zonder
`ANTHROPIC_API_KEY`. Het toont alleen "werkt" of de fout. Het token komt niet in de chat, niet in git, niet in een log.

A6. **Tests.** Een nep-subproces met stream-json-regels: geen API-sleutel in de omgeving van het subproces;
`apiKeySource` anders dan `none` stopt de ronde; ontbrekend token geeft een nood; de MCP-server (tools/list,
tools/call, leesgrens, bestand `gelezen`); de zoekteller; "Links" lezen; een tijdslimiet. De bestaande controles in
`aanbod.py` en `verslag.py` blijven ongewijzigd en groen.

A7. **Proef.** Na de tests en Codex: Mehdi zet het token met een Run-blok; daarna draait dezelfde MOVA-vraag een keer
op het abonnement. Er is geen geldgrens meer, dus geen vraag aan Mehdi voor de proef.

## Vragen

1. Klopt A1 tot A7, of is er een betere weg die ook geen API-kost heeft? Geef per punt ja, nee of aanpassen.
2. A2: eigen leestool (MCP) tegenover WebFetch van Claude Code met daarna een eigen nalezing van dezelfde url door
   de runner. Welke, en waarom?
3. Welk risico zie je bij een abonnementstoken op de VM (limieten van het werkaccount dat Mehdi ook in de app gebruikt,
   geldigheid een jaar, gebruiksvoorwaarden)? Is er iets dat Mehdi moet beslissen? Alleen een echte grens.
4. Moet het token in `~/appportal/.env` of in een eigen bestand (zoals `/etc/<dienst>.env`)?

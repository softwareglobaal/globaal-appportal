# Verwerking overleg 14: De Prijsonderzoeker op het Claude-abonnement (01-11-2026)

Uitvoerder: Claude 1, tak `aankoop-abonnement`. Aanleiding: Mehdi in de chat, "ik wil niet dat agent geld kost ...
met mijn eigen claude account ... los het op". Rapport: `rapport-14-abonnement.md` (21 aangenomen, G4 en G6 afgewezen,
geen vraag voor Mehdi). Tests: 212 prijstests, 46 sleutelbrontests, 55 regisseurtests, 21 aankoopkeuring groen, op de
laptop en op de VM.

| Punt | Uitslag | Verwerking |
| --- | --- | --- |
| X1, G1, K1 | 3-0 | `onderzoek.py` start `claude -p` (geen `anthropic` meer). Omgeving: witte lijst `OMGEVING` plus `CLAUDE_CODE_OAUTH_TOKEN`; geen enkele API-sleutel, ook niet als de runner er een heeft. `--restricted --tools WebSearch`, `--allowedTools WebSearch,mcp__lees__lees_pagina`, `--strict-mcp-config`, nooit `--bare` (die leest alleen een API-sleutel). Model: alias `opus`. Grendel: `apiKeySource` anders dan `none` in het init-bericht stopt claude meteen (`GeenAbonnement`), nooit een terugval. |
| X2, G2, K2 | 3-0 | Eigen MCP-server `aankoop/leesserver.py` (stdio, geen pakket): `lees_pagina` geeft het model precies de tekst die in het leeslog staat; dat leeslog is `gelezen` voor `aanbod.py`. HTML naar tekst met productgegevens (JSON-LD, meta) en productfoto's bovenaan; PDF met pypdf (staat in `~/agents/.venv`). Grendel tegen het eigen netwerk: alleen http(s) op poort 80/443 naar een openbaar adres, ook na een doorverwijzing (127.0.0.1, localhost, 169.254.169.254, 10.x, ::1 geweigerd). Leesgrens zes, ook voor mislukte lezingen. |
| X3, G3, K3 | 3-0 en 2-1 | Echte stream-json vastgelegd als `tests/fixtures/claude_stream_proef.jsonl` (laptop, 01-11, haiku): de lijst "Links" heeft titel en url. Ingekort omdat de repo publiek is: de paginatekst en de toestelpaden zijn eruit. Zoekgrens tweemaal: een PreToolUse-hook via `--settings` (gemeten: werkt samen met `--restricted`, weigert de zevende) en de runner zelf, die claude stopt als er toch een zevende zoekresultaat komt. "Gezien, niet nagekeken": een prijs telt alleen als ze in de titel staat. |
| X4, K4 | 3-0 | Geen 15 minuten (G4 afgewezen): de deadline van de ronde (480 s). claude en de leestool draaien in een eigen procesgroep die bij de deadline, bij een reden om te stoppen en na een gewoon einde samen gestopt wordt. Hoogstens 30 beurten (`MAX_BEURTEN`), want `--max-turns` bestaat niet. |
| X5, G5, K5 | 3-0 | `scripts/claude-abonnement-naar-vm.sh` (laptop): `claude setup-token`, dan de verborgen plakvraag (`read -s`), geen terminalopname. Het token gaat via stdin van ssh naar de VM, niet op een opdrachtregel, en het klembord wordt leeggemaakt. Daarna `prijsonderzoeker.py --proef-abonnement` op de VM. |
| X6, K6 | 3-0 | Tests met een nagebootste claude (echt proces): geen sleutel in de omgeving, toolbeperking, verkeerde bron, ongeldig token, betaald extra verbruik, limiet, andere fout, geen eindregel, deadline met kindproces, zoekgrens door de runner, beurtengrens, zonder token geen start, tokenbestand 600, API-sleutel in dat bestand telt niet; leestool: eigen netwerk, doorverwijzing, tekst, leesgrens, afkappen, MCP-berichten, los proces; hook. |
| X7, K6 | 3-0 | Na de uitrol eerst `--proef-abonnement` (bron `none`, gewoon einde), dan een keer de MOVA-vraag. |
| X8, K8 | 3-0 | Token in een eigen bestand: `~/.config/prijsonderzoeker/claude-token` (map 700, bestand 600; `lees_token` weigert een bestand dat anderen kunnen lezen). Niet in `~/appportal/mijnagents-data/` (X8): die map is `/data` in de container `app-mijnagents` (gemeten met `docker inspect`), het token zou dan in de webcontainer staan. Daarom de plaats van K8. |
| G4 | 1-2 | Afgewezen: geen 15 minuten. |
| G6 | 0-3 | Afgewezen: niet in `~/appportal/.env`. |
| G7, K7 | 3-0 | Geen vraag voor Mehdi. De limiet van het abonnement deelt hij met de app; een bereikte limiet wordt een nood. Het token geldt een jaar: herinnering in de werkstand. |

Twee grendels die uit de metingen kwamen, niet uit het overleg:

1. **Betaald extra verbruik.** De stream meldt `rate_limit_info.isUsingOverage`. Staat dat op waar, dan stopt claude
   meteen (`GeenAbonnement`): extra verbruik bovenop het abonnement kost geld, en Mehdi wil geen kost.
2. **Een ongeldig token geeft ook bron `none`.** Gemeten op de laptop zonder aanmelding: `apiKeySource: "none"` en
   daarna "Not logged in · Please run /login" met `is_error`. Dat wordt ook `GeenAbonnement`, geen gewone fout.

Echte proef op de laptop (01-11, haiku, 2 zoek en 2 lees, eigen aanmelding in plaats van het token): 35 seconden, stop
`klaar`, bron `none`, 2 zoekopdrachten, 2 pagina's gelezen, leesbaar JSON-antwoord.

## Verwerking Codex-controle 15 (niet klaar)

1. **Hoog, kosten.** (a) Een eigen lege configuratiemap per vraag (`CLAUDE_CONFIG_DIR` in de werkmap): niets uit
   `~/.claude` van de VM telt. (b) `voor_de_start()` weigert als er beheerde instellingen staan
   (`/etc/claude-code/managed-settings.json`, `managed-settings.d`, `managed-mcp.json`, en de macOS-map); gemeten op de VM:
   er zijn er geen. (c) Nieuw: boven 90 procent van een limietvenster (`utilization` in `rate_limit_info`) stopt de vraag
   (`GRENS_GEBRUIK`, stop `limiet`), zodat ze nooit tot betaald extra verbruik komt; `isUsingOverage` blijft de tweede
   grendel. (d) Gemeten op de laptop: `overageStatus: "allowed"` op dat account. De enige zekerheid op accountniveau is
   Usage credits uit in claude.ai (Settings > Usage); dat is Mehdi's instelling, en het advies staat bij de tokenstap.
2. **Hoog, DNS-rebinding.** De leestool verbindt nu met het IP-adres dat `openbaar_adres()` zelf nakeek
   (`_VasteHTTP`, `_VasteHTTPS` met `_create_connection`), bij elke doorverwijzing opnieuw; de naam blijft voor de
   Host-kop en TLS. Daarbovenop controleert `verbonden_openbaar()` het echt verbonden adres voor het lezen.
3. **Hoog, X2.** `gelezen_uit` plakt niets meer aan elkaar: een url krijgt de tekst van zijn laatste lezing, en alleen
   onder de eind-url die het model bovenaan de tekst zag. De tool en de JSON-vorm zeggen dat die url de url van het
   aanbod is.
4. **Procesgrens.** De vraag gaat in een eigen draad naar stdin; de eindregel van de stream stopt het lezen; claude en
   de leestool worden in een `finally` gestopt. De systeemtekst gaat via `--system-prompt-file` (gemeten: werkt), niet
   meer als argument.

Tests: 225 prijstests groen op de laptop en de VM, sleutelbron 46. Echte korte proef op de laptop opnieuw: 33 s, klaar.

## Verwerking Codex-controle 16 (niet klaar; uitrol zonder token wel goed)

1. **Centrale instellingen (hoog).** `voor_de_start()` draait nu eerst `claude auth status --json` (geen modelaanvraag)
   met dezelfde omgeving en lege configuratiemap: aangemeld, aanbieder `firstParty`, en het abonnement moet persoonlijk
   zijn (`pro`, `max`, `ultra`); een Team- of Enterprise-account of een onbekend type start niet. Staat er daarna een
   niet-lege `remote-settings.json` in de configuratiemap, dan start de vraag ook niet. Gemeten op de laptop: `claude
   auth status` geeft `subscriptionType: "max"`.
2. **Usage credits (latere aanvragen).** Meldt de stream `overageStatus: "allowed"`, dan stopt de vraag meteen
   (`GeenAbonnement`, nood met de reden): met Usage credits aan kan een volgende aanvraag geld kosten. De eerste
   aanvraag valt dan nog binnen het abonnement, want boven 90 procent stopt de vraag al. Gevolg: de agent werkt pas als
   Usage credits uit staan (claude.ai, Settings > Usage). Op het laptopaccount staat `overageStatus` op `allowed`.
3. De abonnementsproef doet dezelfde controles en zegt wat Mehdi moet doen.

Tests: 233 prijstests groen.

## Verwerking Codex-controle 17 (uitrol zonder token: ja)

- Punt 1 (centrale instellingen): opgelost volgens Codex.
- Punt 2 (eerste aanvraag als de limiet al op is): sluit alleen Mehdi's accountinstelling af. Daarom draaien de
  abonnementsproef en de MOVA-vraag pas als Mehdi bevestigt dat Usage credits uitstaan (claude.ai, Settings > Usage).
- Punt 3: de abonnementsproef zegt alleen nog "werkt" als ze een limietmelding zag met `overageStatus` anders dan
  `allowed`; zonder melding faalt ze met uitleg.

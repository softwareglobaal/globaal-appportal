# siyanagents-runner

Host-side runner-code voor de Sales/Marketing-agents (siyanagents.globaal.be).
Draait op de VM buiten de containers (via cron), praat met de siyanagents-app
over localhost en met de externe diensten (Pipedrive, Google Ads) over het net.
Wordt **niet** in een container gebouwd — alleen ./siyanagents is de build-context.

## Inhoud

- `siyanagents_uitvoerder.py` — voert GOEDGEKEURDE muterende voorstellen uit
  tegen de externe diensten en logt bewijs. Cron: elke minuut.
- `koppelingen/pipedrive.py` — Pipedrive-client. Lezen vrij (get/lijst);
  schrijven via schrijf(), alleen door de uitvoerder na goedkeuring.
- `koppelingen/googleads.py` — Google Ads-client (REST, geen SDK). Lezen via
  accounts()/zoek() (GAQL); schrijven via schrijf() op `:mutate`-paden. API v21.

## Draaien (cron op de host)

```
* * * * * ~/agents/.venv/bin/python ~/appportal/siyanagents-runner/siyanagents_uitvoerder.py >> ~/agents/siyanagents_uitvoerder.log 2>&1
```

De clients lezen credentials bij naam uit `~/appportal/siyanagents-data/.env`
(token) en `~/appportal/.env` (Pipedrive/Google Ads); nooit in git.

## Nog buiten deze map: seo_runner.py

`~/agents/seo_runner.py` (de bestaande SEO-content-runner) staat buiten git en
verhuist hier niet mee. Er is één wijziging voor de splitsing gemaakt — na de
`laad_env`-regels wordt PLATFORM/KB/MODEL opnieuw uit de env gelezen zodat
`PLATFORM_URL` uit de siyanagents-.env doorwerkt:

```python
laad_env("~/appportal/siyanagents-data/.env")  # AGENTS_TOKEN + PLATFORM_URL (siyanagents)
laad_env("~/agents/.env")                        # ANTHROPIC_API_KEY
TOKEN = os.environ.get("AGENTS_TOKEN", "")
# opnieuw lezen ná het laden (regel 17 las ze vóór laad_env):
PLATFORM = os.environ.get("PLATFORM_URL", "http://127.0.0.1:3020")
KB = os.environ.get("SEO_KB", os.path.expanduser("~/agents/marketing-seo"))
MODEL = os.environ.get("SEO_MODEL", "claude-sonnet-5")
```

Back-up van de originele versie: `~/agents/seo_runner.py.bak-2026-08-10`.

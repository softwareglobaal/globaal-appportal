# mijnagents-runner

Host-side code voor Mehdi's agent-omgeving (mijnagents.globaal.be). Draait op
de VM buiten de containers (via cron), praat met de mijnagents-app over
localhost (`http://127.0.0.1:3022`) en meldt status via het hartslag-contract.
Wordt **niet** in een container gebouwd — alleen ./mijnagents is de build-context.

## Een nieuwe agent maken

```
python3 ~/appportal/mijnagents-runner/nieuwe-agent.py
```

De generator:
1. registreert de agent op het bord (token-gated `/api/agent`);
2. schrijft een runner-skelet `<naam>.py` met de hartslag al ingebouwd;
3. drukt de cron-regel af die je nog moet toevoegen.

Daarna vul je in het skelet alleen `werk()` in. De kaart verschijnt op
https://mijnagents.globaal.be zodra de eerste hartslag binnen is.

Niet-interactief (bv. vanuit een Claude-sessie over ssh):

```
python3 nieuwe-agent.py --naam post-wacht --label "Postwacht" --type post \
  --rol "sorteert nieuwe post op info@" --cadans "elk uur" \
  --mag "post labelen" --grens "nooit verwijderen" \
  --tool "gmail lezen" --tool "labels zetten" --cron "0 * * * *"
```

## Het token

De runners en de generator lezen `AGENTS_TOKEN` uit
`~/appportal/mijnagents-data/.env` — nooit uit een argument, nooit in git.

## Het contract (samengevat)

`POST /agent-status` met header `X-Agents-Token`, body:

```json
{"naam":"post-wacht","status":"waakt","taak":"korte neutrale taak",
 "detail":"laatste ronde: 12 bekeken, 3 gelabeld","tokens":840}
```

- `status`: `rust`, `waakt`, `actief`, `klaar` of `fout`.
- `taak`/`detail`: neutraal, **nooit inhoud** (geen klantnamen, geen bedragen).
- Optioneel `voorstel` meesturen (mens-in-de-lus). Zonder `parameters` is het
  een louter signaal; met `parameters` wordt het na jouw goedkeuring op het
  bord door de uitvoerder uitgevoerd.

## Stilte-detectie

Geen recente hartslag maakt een kaart "stil": `actief` na 60 min, `waakt` na
150 min, `klaar`/`fout` na 24 uur. Wijzigt de cadans van een agent wezenlijk,
kijk dan of die drempels (in `app.py`, `STILTE_MIN`) nog kloppen.

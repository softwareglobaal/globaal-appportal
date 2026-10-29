# Codex-test ronde 3: bordcommando werkwijzen Namenwacht naar 1.2 (T-0030)

Je leest alleen. Zelfde map. In ronde 2 gaf je NIET AKKOORD om het tijdvenster tussen lezen en POST. Claude's
verwerking staat in `verwerkt-2.md`; het commando in `commando.sh`; de proef in `scenario.sh` (nu met scenario H en
`nep-curl.sh`).

Uitslag van Claude's proef met de echte `mijnagents/app.py`: A normaal exit 0; B herhaling exit 0; C vooraf bewerkt
exit 1, die agent ongemoeid; D en E logboek exit 1; F oude commit exit 1 zonder schrijven; G 403 exit 22 zonder
schrijven; H bewerking tussen lezen en POST: exit 1 met "STOP: mappen-wacht nakijken", tussentijdse tekst bewaard als
laatste rij in `werkwijze_versie`.

Toets:
1. Is de nacontrole juist: kan ze een tussentijdse bewerking missen, of vals alarm geven bij een gewone run?
2. Werkt `sqlite3.connect('file:mijnagents-data/mijnagents.db?mode=ro', uri=True)` vanuit `~/appportal` op de host
   (bind mount `./mijnagents-data:/data` in `docker-compose.override.yml`, WAL-modus in `app.py`)?
3. Is de resterende afweging (geen atomiciteit in de route, wel detectie en bewaring) aanvaardbaar voor één
   eenmalige run die Mehdi zelf start? Zo niet: wat is de kleinste aanvaardbare oplossing?

Antwoord kort in het Nederlands. Eindig met `AKKOORD` of `NIET AKKOORD: <reden>`.

Ter info bij vraag 2: `mijnagents-runner/bord_export.py` (cron op de host) opent dezelfde databank zo:
`sqlite3.connect(f"file:{DB}?mode=ro", uri=True)` met `DB` onder `~/appportal/mijnagents-data/`. De opdracht van
28-10 in globaal-vm-beheer (De Deontologiewacht op het bord) las vanuit `~/appportal` met
`file:mijnagents-data/mijnagents.db?mode=ro`.

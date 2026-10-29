# Codex-test ronde 2: bordcommando werkwijzen Namenwacht naar 1.2 (T-0030)

Je leest alleen. Zelfde map als ronde 1. In ronde 1 gaf je NIET AKKOORD: het commando kon een tussentijdse
bordbewerking ongezien overschrijven, en commit, pin en logboek werden getoond maar niet getoetst. Claude verwerkte
dat; zie `verwerkt.md`. Het nieuwe commando staat in `commando.sh` (één regel, voor het veld `commando` van
workflow_dispatch in `vm-workflow.yml`). Het oude zaad 1.1 staat in `zaad-1.1/` (op de VM: `git show c31deeb:...`).

Claude testte het met de echte `mijnagents/app.py` (proefbord `server.py`, poort 3999) en een kloon op 1edf580, met
`scenario.sh`. Uitslag: A normaal exit 0, B herhaling exit 0 zonder tweede handeling, C tussentijds bewerkt exit 1 en
die agent ongemoeid, D logregel zonder bevestigde regelbron exit 1, E logboek ontbreekt exit 1, F oude commit exit 1
zonder schrijven, G 403 exit 22 zonder schrijven.

Toets:
1. Zijn je drie punten uit ronde 1 opgelost?
2. Kan het nog iets overschrijven wat Mehdi intussen op het bord bewerkte, of iets anders veranderen dan de twee
   werkwijzen (plus `werkwijze_versie` en `handeling`)?
3. Klopt de shell: `set -e` met `|| rc=$?`, `case`, `$(... | tail -n 1)`, aanhalingstekens in `python3 -c "..."`?
4. Werkt `import werkwijze_naar_bord` vanuit `~/appportal` met `python3` (bord.py leest het token uit
   `~/appportal/mijnagents-data/.env`)?
5. Is er een tijdvenster tussen lezen en POST dat ertoe doet?

Antwoord kort in het Nederlands. Eindig met `AKKOORD` of `NIET AKKOORD: <reden>`.

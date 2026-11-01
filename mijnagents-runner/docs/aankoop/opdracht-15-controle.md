# Controle 15 door Codex: De Prijsonderzoeker via het Claude-abonnement (commit f9deb6c op tak aankoop-abonnement)

Lees alleen; wijzig niets. Gerichte controle.

Overleg: `mijnagents-runner/docs/aankoop/opdracht-14-abonnement.md`, `rapport-14-abonnement.md`; verwerking:
`verwerkt-14-abonnement.md`. Bekijk `git diff origin/main..f9deb6c`. Tests:
`python3 mijnagents-runner/tests/test_aankoop_prijs.py` (212 groen) en `python3 mijnagents-runner/tests/test_sleutelbron.py`.

Mehdi's besluit: de agent mag geen geld kosten; hij werkt met Mehdi's Claude-abonnement, niet met de API.

Vragen:
1. Kan er in enige weg toch API-kost of betaald extra verbruik ontstaan? Denk aan: een sleutel die via een andere
   variabele, een instellingenbestand, `apiKeyHelper`, de MCP-server of de hook binnenkomt; `--restricted` en
   `--settings`; de grendel op `apiKeySource` en `isUsingOverage`. Geef een concreet scenario of zeg dat er geen is.
2. Leestool `aankoop/leesserver.py`: kan een webpagina het model naar het bord (127.0.0.1:3022), de Docker-bridge of
   een ander intern adres sturen? Denk aan DNS die na de controle verandert, IPv6, doorverwijzingen, `0.0.0.0`.
3. Klopt het dat het model precies de tekst leest die `aanbod.py` nakijkt (X2)? Zijn er gevallen waarin `gelezen`
   en wat het model zag uit elkaar lopen (afkappen, eind-url, dubbele lezing)?
4. Procesbeheer in `onderzoek._draai`: kan een kindproces blijven hangen, kan de ronde de 480 s overschrijden, of kan
   de lezer-thread vastlopen?
5. Een nieuwe fout van ernst hoog in de gewijzigde regels?
6. Mag dit live, waarna Mehdi het token zet met `scripts/claude-abonnement-naar-vm.sh` en dezelfde MOVA-vraag een keer
   draait? Een "nee" alleen met een concreet scenario.

Geef bovenaan: klaar, klaar met kanttekeningen, of niet klaar.

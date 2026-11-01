# Controle 16 door Codex: herstel na controle 15 (commit 3454316 op tak aankoop-abonnement)

Lees alleen; wijzig niets. Gerichte controle.

Vorige controle: `mijnagents-runner/docs/aankoop/rapport-15-controle.md` (niet klaar); herstel: onderaan
`verwerkt-14-abonnement.md`. Bekijk `git diff f9deb6c..3454316`. Tests: `python3 mijnagents-runner/tests/test_aankoop_prijs.py`
(225 groen op laptop en VM). Als je leesomgeving geen tijdelijke mappen toelaat, zeg dat en oordeel op de code.

1. Je vier punten (kosten, DNS-rebinding, bewijs per lezing, procesgrens): opgelost, deels of niet, met je eigen
   tegenproef.
2. Kosten: na deze grendels (lege configuratiemap, geen beheerde instellingen, stop boven 90 procent van een
   limietvenster, stop bij isUsingOverage) blijft er volgens mij alleen een theoretische route: de allereerste aanvraag
   als Mehdi's eigen gebruik al boven de limiet zit en Usage credits aanstaan. Die sluit alleen Mehdi's accountinstelling
   (Settings > Usage, Usage credits uit). Klopt dat, of zie je een andere route?
3. Een nieuwe fout van ernst hoog in de gewijzigde regels?
4. Mag dit live (de agent maakt zonder token geen enkele aanvraag en meldt een nood), waarna Mehdi Usage credits
   nakijkt, het token zet met `scripts/claude-abonnement-naar-vm.sh` en de MOVA-vraag een keer draait? Een "nee" alleen
   met een concreet scenario.

Geef bovenaan: klaar, klaar met kanttekeningen, of niet klaar.

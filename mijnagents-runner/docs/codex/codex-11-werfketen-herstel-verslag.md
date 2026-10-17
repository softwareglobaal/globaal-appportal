# Opdracht 11 — herstelverslag werfverslag-keten, 17-10-2026

**Stand: klaar voor onafhankelijke controle door Claude.** De wijzigingen staan alleen in deze worktree. Er is niets gecommit, gepusht, uitgerold, verstuurd of verwijderd.

## Punt 1 — controleposten

`werfverslag_voorbereider.py:634` toetst W1 aan de H-A-buitenafspraak en het juiste bezoek-ID, W2 aan GPS of opname, W3 aan beide mappen, W4 aan `fotos/` met tijden, W6 aan een transcript direct in de bezoekmap, W8/W9 aan de werfapp en W12 aan het contract. `werfverslag_voorbereider.py:763` blokkeert *klaar voor verslag* zonder de vereiste bronnen; `:871` zet de ontbrekende posten in de bordrij. De herhaalde vaste nood is weg. Test: `tests/test_werfketen_controles_11.py:49` (23 gevallen), inclusief fout dossier, ontbrekende bezoekmap, GPS, losse foto, baktranscript, hoger appnummer en onbereikbaar contract. Bewust niet gedaan: onbekende contractstatus of een werfapp zonder toetsbaar nummer groen maken. Een architectuurcontract zonder expliciete `werfopvolging_keuze` blijft daarom onbewezen; die keuze staat in het contractschema bij addenda.

## Punt 2 — bronopdrachten

`werfverslag_voorbereider.py:393` maakt een E4-venster uit bewezen foto- of opnametijden; `:605` geeft venster, coördinaten, straal en bezoeksleutel mee. `:845` sluit uitsluitend de taak met dezelfde bezoeksleutel zodra de bron in de map staat. `mac/icloud_wacht.py:360` aanvaardt ook een E4-venster over middernacht; `:480` bewaart een bestaand fotomanifest als oude versie. Tests: `tests/test_werf_fotoproducent.py:157`, `:169`, `:179`; `tests/test_icloud_status.py:136`, `:145`, `:152`. Bewust niet gedaan: een fototaak zonder tijdvenster uitvoeren of echte Photos openen.

## Punt 3 — proef en werfappbrug

`werfverslag_proef.py:637` en `:690` bewaren gegevens en bijlagen ook bij een directe proef. `koppelingen/werfapp.py:130` bewaart onbekende aanwezigheid als `None`. `mijnagents/templates/werfbezoek.html:63`, `mijnagents/app.py:2188` tonen de wachtende klik en de ontbrekende posten. `werfverslag_schrijver.py:122` en `mijnagents/werfopdrachten.py:137` eisen een vastgelegde reden voor een betaalde commandline-opdracht. Tests: `tests/test_werfverslag_verwerking.py:240`, `tests/test_werfapp_brug.py:53`, `tests/test_werf_cli_11.py:15`, `mijnagents/test_werf_frontend.py:12`. Bewust niet gedaan: een proef starten, concept live plaatsen of een verslag versturen. De bestaande koppelingstest tegen de naastgelegen werfapp slaat terecht over zolang PR #3 daar nog geen conceptroute heeft.

## Punt 4 — identiteit en werkwijze

`werfregistratie.py:18` koppelt of registreert het vaste werfapp-bezoek vóór bordnummering; `koppelingen/werfregister.py:106` hergebruikt het ID na een mapverhuis. Beide runners gebruiken `ag.ronde()` (`werfverslag_voorbereider.py:1061`, `werfverslag_schrijver.py:140`). De drie zaden beginnen met Mandaat (`werkwijze/werfverslag-voorbereider.md:3`, `werfverslag-schrijver.md:3`, `werfverslag-dashboard.md:3`); `werkwijze_naar_bord.py:36` zet het mee op de agentkaart. Tests: `tests/test_werfregistratie_11.py:56`, `tests/test_werf_rondes_11.py:15`, `tests/test_werf_mandaat_11.py:14`. Bewust niet gedaan: werfapp-repo, live bordwerkwijzen, dubbels of hoofdbranch wijzigen.

## Nagekeken

`.github/workflows/werfverslag-grendels.yml:19` draait de oude en nieuwe grendels. Lokaal: 23 nieuwe pytest-gevallen geslaagd; bestaande pytest-suites 50 geslaagd, 1 overgeslagen wegens ontbrekende conceptroute in de naastgelegen werfapp. De unittest-suites voor bord, frontend, bezoek, nummering, iCloud, foto-overdracht, CLI, registratie, ronde en mandaat slagen. `git diff --check` en `compileall` zijn schoon.

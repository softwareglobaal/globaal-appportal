# Codex-test: commando om twee werkwijzen op het bord naar versie 1.2 te zetten (T-0030)

Je leest alleen. Deze map is een kopie van `softwareglobaal/globaal-appportal` op main (commit 1edf580), alleen de
bestanden die ertoe doen, plus `vm-workflow.yml` uit `softwareglobaal/globaal-vm-beheer`.

## Achtergrond

De Namenwacht (agents `benamingen-wacht` en `mappen-wacht`) is hersteld: de regelbron is vastgepind op
"H-A vaste afspraken v1.10" (`mijnagents-runner/werkwijze/naamstructuur-regels.json`). Die code staat al op de VM
(main op de VM is 1edf580). Op het bord (`mijnagents.db`, tabel agent) staat van beide agents nog werkwijze 1.1
(06-10). Het zaad in `mijnagents-runner/werkwijze/benamingen-wacht.md` en `mappen-wacht.md` is 1.2. De werkwijze op
het bord van 1.1 is woord voor woord het oude zaad 1.1 (alleen een slotregeleinde verschilt), dus er gaat geen
bewerking van Mehdi verloren.

Mehdi start het commando zelf: GitHub, `softwareglobaal/globaal-vm-beheer`, Actions > vm > Run workflow, met de
inhoud van `commando.sh` in het veld `commando`. De workflow draait het met bash in `~/appportal` op de VM
(zie `vm-workflow.yml`). Zijn regel: handelingen op het bord via de server, met curl naar 127.0.0.1:3022 en de headers
`X-authentik-username: mehdi (ja in de chat, <datum>)` en `X-authentik-groups: admin`.

## Wat je toetst

1. Doet `commando.sh` precies dit en niets anders: (a) toont de VM-commit en de vastgepinde versie, (b) zet voor
   beide agents de werkwijze op het bord gelijk aan het zaad 1.2 via de route `POST /agent/<naam>/werkwijze` in
   `mijnagents/app.py`, (c) bevestigt met `werkwijze_naar_bord.py <naam>` (zonder `--zet`, dus alleen lezen) dat
   zaad en bord gelijk zijn, (d) toont de laatste regels "Naamstructuur: ..." uit de cronlogboeken?
2. Kan het iets anders op het bord of de VM veranderen dan die twee werkwijzen (plus de vorige versie in
   `werkwijze_versie` en een regel in `handeling`)? Raakt het het mandaat, de cron, de index of iets anders?
3. Stopt het veilig als iets niet klopt (zaad geen 1.2, bord weigert, verschil blijft)? Let op `set -e`, de
   exitcodes van `werkwijze_naar_bord.py` en `curl -f`.
4. Komt de tekst op het bord exact overeen met het zaad (urlencode, `\r\n`, `strip()` in de route, de vergelijking
   met `genormaliseerd()` in `werkwijze_naar_bord.py`)?
5. Lekt de uitvoer iets in het Actions-logboek (paden, namen, sleutels)? De repo globaal-vm-beheer is private.
6. Werkt het als één regel in het invulveld van workflow_dispatch (aanhalingstekens, `$`, `%{http_code}`)?

Antwoord kort in het Nederlands. Eindig met een regel `AKKOORD` of `NIET AKKOORD: <reden>`.

## Wat Claude al testte (lokaal, met de echte `mijnagents/app.py` van main op een proefdatabank, poort 3999)

- Bord met werkwijze 1.1 en mandaat "oud mandaat": na het commando staat 1.2 op het bord, `werkwijze_naar_bord.py`
  zegt voor beide "zaad en bord zijn al gelijk", exit 0. Het mandaat bleef "oud mandaat". In `werkwijze_versie` staat
  1.1 als "vorige versie", in `handeling` "werkwijze bijgewerkt door mehdi (ja in de chat, 29-10-2026)".
- Verkeerde groep: curl geeft 403 en exit 22, niets geschreven.
- Zaad met "Versie 1.3": het commando stopt na de versieregel, niets geschreven.
- Buiten een git-map faalt `git rev-parse` alleen in de echo; op de VM is ~/appportal een git-map.

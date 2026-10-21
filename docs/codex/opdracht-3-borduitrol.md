# Opdracht Codex ronde 3: herstel van BU-10 tot BU-13

Van Claude, 16-10-2026. Rondenaam: "Borduitrol mijnagents: herstel na ronde 2 (ronde 3)". Nieuwe bevindingen vanaf BU-14.
Zelfde rol en grenzen (werkafspraken v1.3; alleen lezen, niets wijzigen, geen SSH of netwerk naar *.globaal.be).

| Repo | Worktree | Tak | Ronde 2 | Nu |
|---|---|---|---|---|
| softwareglobaal/globaal-appportal | `/Users/mehdichegini/dev/_bord-uitrol` | `bord-uitrol` (PR #68, concept) | `dce3f1b0535f3ec802357876269557a24d6256b8` | `88b0f5cef84e13b093d4d243e3f27ea5ef9a7ed2` |

Diff: `git -C /Users/mehdichegini/dev/_bord-uitrol diff dce3f1b..88b0f5c`. Kernbestanden: `mijnagents/deploy.sh`,
`mijnagents/test_bord_deploy.py`. Jouw rapport: `docs/codex/codex-2-borduitrol.md`. Mijn verwerking (beweringen):
`docs/codex/verwerkt-2-borduitrol.md`.

Verloop hoog+middel: ronde 1 acht (2+6), ronde 2 vier (0+4). Volgens Claude zijn BU-10 tot BU-13 hersteld met tests die
falen op `dce3f1b` of op een gerichte mutatie. Lokaal: alle tien testbestanden in `mijnagents/` groen (41 uitroltests).

## Vragen

1. Volstaat elk herstel van BU-10 tot BU-13? Zitten er fouten in de herstellingen zelf, in het bijzonder:
   - `bewaak` zet `.built` nu om naar het label van de draaiende image (of `onbekend`) en laat dezelfde ronde HEAD
     uitrollen. Kan dat een lus, een onnodige herbouw of een stille overschrijving van een bewuste handmatige toestand
     veroorzaken? Merk op: een image van het oude script heeft geen label; na een terugrol naar zo'n image noemt
     `.built` dan `onbekend`.
   - de kopie direct vóór de start, en het pad als die kopie mislukt (`:latest` terug, `.herstel` weg, geen `.mislukt`);
   - de eis van minstens één actieve agent in `/gezondheid` en in de kopie.
2. Staat er nog een punt van ernst hoog of middel open dat de merge en één bewaakte uitrol tegenhoudt?
3. BU-9 (laag) stel ik Mehdi voor als eigen taak (melding op het bord bij `.mislukt`, `.herstel`, `.ongezond`). Akkoord dat
   dat de uitrol niet tegenhoudt?

## Antwoordvorm

Beslissing eerst. Dan BU-n vanaf BU-14 met ernst, `bestand:regel`, voorbeeld en fix. Dan per BU-10 tot BU-13 kort:
volstaat, deels of niet. Afsluiten met de drie punten.

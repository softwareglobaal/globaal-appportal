# Opdracht Codex ronde 4: vereenvoudigd ontwerp na BU-14 tot BU-18

Van Claude, 16-10-2026. Rondenaam: "Borduitrol mijnagents: kandidaat en waarnemende bewaking (ronde 4)". Nieuwe
bevindingen vanaf BU-19. Zelfde rol en grenzen (werkafspraken v1.3; alleen lezen, niets wijzigen, geen SSH of netwerk
naar *.globaal.be).

| Repo | Worktree | Tak | Ronde 3 | Nu |
|---|---|---|---|---|
| softwareglobaal/globaal-appportal | `/Users/mehdichegini/dev/_bord-uitrol` | `bord-uitrol` (PR #68, concept) | `88b0f5cef84e13b093d4d243e3f27ea5ef9a7ed2` | `ad0ceff9f2820b930665c5eabad0ceb18fbbd28c` |

Diff: `git -C /Users/mehdichegini/dev/_bord-uitrol diff 88b0f5c..ad0ceff`. Kernbestanden: `mijnagents/deploy.sh`,
`mijnagents/test_bord_deploy.py`. Jouw rapport: `docs/codex/codex-3-borduitrol.md`. Mijn verwerking (beweringen):
`docs/codex/verwerkt-3-borduitrol.md`.

## Stopregel

Hoog+middel: 8, 4, 4. Volgens mij kwamen drie van de vier punten van ronde 3 uit één ontwerpkeuze (`bewaak` handelde
zelf). Deze ronde vereenvoudigt daarom in plaats van een laag toe te voegen: `bewaak` neemt alleen waar, een expliciete
`.pauze`, en de bouw onder `:kandidaat` met `.herstel` alleen rond de wissel. Daalt het aantal hoog+middel nu niet, dan
volgt een ontwerpronde en beslist Mehdi. Zeg het uitdrukkelijk als je vindt dat het ontwerp zelf nog niet deugt.

## Vragen

1. Volstaat elk herstel van BU-14 tot BU-18? Fouten in de herstellingen zelf?
2. Is de nieuwe volgorde juist: CI, archief, databank en ruimte, terugrolimage (`:vorige`), bouw als `:kandidaat`,
   labelcontrole, kopie, nacontrole dat nog dezelfde image draait, `.herstel`, `:kandidaat` naar `:latest`, start,
   gezondheid, `.built` en `.built_id`? Klopt `afbreken` (geen container aanraken, alleen een halverwege mislukte
   wisseltag terug, een eerdere `.herstel` laten staan)?
3. Staat er nog een punt van ernst hoog of middel open dat de merge en één bewaakte uitrol tegenhoudt? De eerste ronde
   na de pull: image zonder label, geen `.built_id`, `.built` uit het oude script.

## Antwoordvorm

Beslissing eerst. Dan BU-n vanaf BU-19 met ernst, `bestand:regel`, voorbeeld en fix. Dan per BU-14 tot BU-18 kort:
volstaat, deels of niet. Afsluiten met de drie punten.

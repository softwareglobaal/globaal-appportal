# Uitrol op de VM (T-0030, Claude 1, 29-10-2026)

## Stand

- De code staat al op de VM: main daar is 1edf580 (`git fetch vm main`, `git ls-remote --symref vm HEAD`) en bevat
  het herstel 7be3014. Siyan bracht dat om 13:39 CET binnen met migratie 198. Een aparte `git pull` is niet nodig.
- De H-A-toetsing draait weer. In `Data uit Mehdi/Benamingenwacht/noden.md` staat "Welke versie geldt?" op
  opgelost en er is geen regelbron-nood. Mappenwacht heeft sinds 29-10 14:07 weer voorstellen voor Mehdi. De sha256
  van v1.10 in Dropbox is de pin (251ea9e8...).
- Op het bord staat van beide wachters nog werkwijze 1.1, woord voor woord het oude zaad (c31deeb).

## Werkwijzen naar 1.2

Mehdi start het zelf: GitHub, `softwareglobaal/globaal-vm-beheer`, Actions, `vm`, Run workflow, in het veld
`commando` de ene regel uit `uitrol-bord-commando.sh`.

Het commando stopt met een STOP-regel als het herstel niet op de VM staat, de pin geen v1.10 is, het zaad geen 1.2
is, of de bordtekst iets anders is dan 1.1 of 1.2. Het schrijft via de bordroute `POST /agent/<naam>/werkwijze` met
de headers van Mehdi, kijkt daarna in `werkwijze_versie` of de vervangen tekst echt 1.1 was, en toetst de laatste
regel van beide cronlogboeken op "regelbron: bevestigde bron gelezen". Een tweede run doet niets meer.

Goed is: de laatste regel van de uitvoer is `KLAAR: beide werkwijzen 1.2, regelbron v1.10 bevestigd`. Bij een STOP
eerst de bordtekst en de versiegeschiedenis nakijken, dan pas opnieuw starten.

## Toetsing

- Proef met de echte `mijnagents/app.py`: `uitrol-bord-proefbord.py`, `uitrol-bord-proef.sh`, `uitrol-bord-nep-curl.sh`
  (A normaal, B herhaling, C vooraf bewerkt, D en E logboek, F oude commit, G 403, H bewerking tussen lezen en POST).
- Codex: ronde 1 en 2 NIET AKKOORD (overschrijven van een tussentijdse bordbewerking), ronde 3 AKKOORD. Zie
  `uitrol-codex-*.md` en `uitrol-verwerkt-*.md`.

## Apart, niet in T-0030

De nood "H-A-metadata niet volledig bereikbaar" (voor claude-code, sinds 18-10) blijft open. Het H-A-bereik
`/Work All/o01. Sales/000. Offerte aanvraag informatie/01. Mehdi/02. H-Architects B2B` uit de profielen van
`naamstructuur-regels.json` bestaat niet meer in Dropbox. Hetzelfde pad staat in `koppelingen/bronnen.py` en in de
werkwijze van de contracten-agent.

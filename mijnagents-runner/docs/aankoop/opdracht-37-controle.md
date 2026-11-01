# Codex-controle 37: herstel na controle 36 (01-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

Bekijk `git diff 8d0d5616..4c4ffc64` op de tak `aankoop-eigen-eisen` (en zo nodig `6babd78a..4c4ffc64`). Achtergrond:
`docs/aankoop/rapport-36-controle.md`.

- Punt 1: onder de kandidaten telt nu alleen de prijs (`aankoop/aanbod.py`, sorteersleutel in verwerk); test "een
  bevestigde eigen eis gaat niet voor een lager totaal".
- Punt 2: een modelcode zonder label (hoofdletters en cijfers met een streepje, minstens zes tekens, letter en cijfer)
  wordt ook een vaste eis. Ter info: de echte vervolgvraag zegt letterlijk "(modelcode MOVA-RC-V70ULC-WHT)";
  `eisen_uit_vraag` geeft daarop op de VM: netfrequentie 60 Hz, netspanning 220 V, modelcode MOVA-RC-V70ULC-WHT.
  Een te veel herkende code (COVID-19) houdt een aanbeveling hoogstens tegen.
- Gratis proef op de VM met de echte pagina's (RoboCleaners, Vanden Borre, handleiding, verzendpagina) en een
  nagemaakt modelantwoord: RoboCleaners 961,50 euro aanbevolen, Vanden Borre 1.399 reserve, netwaarden en modelcode
  via dezelfde EAN, "niet bevestigd: levering in Belgie tegen half november".

Een hoge fout alleen met een concreet scenario dat in de echte ronde een verkeerde aanbeveling of een betaling geeft.

## Vragen

1. Zijn punt 1 en 2 van controle 36 hersteld? Ja, of wat ontbreekt met `bestand:regel`.
2. Een nieuwe fout van ernst hoog?
3. Klaar om live te gaan en de vervolgvraag op de VM te draaien: ja of nee.

# De Deontologiewacht

Toetst wat H-Architects naar buiten stuurt aan het reglement van beroepsplichten van de Orde (16-11-2022). Een toets,
geen juridisch advies. De opdrachtkaart (v0.3) staat bij het dossier in Dropbox, niet in deze repo, omdat ze naar het
tuchtdossier verwijst.

## Stand van de bouw

Volgorde uit de ontwerplezing van 27-10-2026 (driehoeksoverleg, 3-0). Elke stap heeft een eigen test.

| Stap | Wat | Bestand | Test | Stand |
|---|---|---|---|---|
| 1 | Regelregister met letterlijk citaat per regel | `register.py`, `regels.json` | `tests/test_deontologie_register.py` | klaar, op main |
| 2 | Privacypoort: alleen PUBLIEK naar Codex en Gemini, kanarietest | `privacypoort.py` | `tests/test_deontologie_privacypoort.py` | gebouwd, wacht op Codex-test |
| 3 | Verslag en kleuren | | | nog niet |
| 4 | Harde controles op de vier masters | | | nog niet |
| 5 | Grendel (stempel op het exacte bestand) | | | nog niet |
| 6 | Werfverslagen | | | nog niet |
| 7 | Budget | | | nog niet |

## De privacypoort

- Alles zonder label is privé. Alleen een `Stuk` met label exact `PUBLIEK` gaat naar Codex of Gemini.
- De bronnen uit het regelregister zijn publiek via `uit_bibliotheek()`, alleen als hun sha256 klopt.
- Namen uit het dossier staan in een bestand buiten git. Zet op de VM in `~/appportal/.env`:
  `DEONTOLOGIE_VERBODEN=/pad/naar/verboden.txt` (een term per regel, `#` voor uitleg). Een publiek stuk met zo een
  term gaat niet door. Staat de variabele er maar is het bestand weg, dan gaat niets door.
- Elke oproep naar Codex of Gemini voor deze agent loopt via `stuur()`. Een andere weg is er niet.

## Draaien

```
python3 mijnagents-runner/deontologie/register.py
python3 mijnagents-runner/tests/test_deontologie_register.py
python3 mijnagents-runner/tests/test_deontologie_privacypoort.py
```

GitHub draait dezelfde drie bij elke wijziging (`.github/workflows/deontologie-grendels.yml`).

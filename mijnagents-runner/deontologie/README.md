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

## Verslag en kleuren (stap 3)

`verslag.maak(documentsoort, bevindingen)` maakt het toetsverslag voor het bord. De harde controles (stap 4 en verder)
leveren per regel een `Bevinding`: slaagt, faalt of onbekend, met de plaats en het voorstel.

- Rood alleen uit een harde, letterlijke regel die faalt; groen alleen uit een harde regel die slaagt.
- Een oordeel, een afgeleide regel, ontbrekende gegevens of een regel zonder uitkomst is oranje.
- Bibliotheek ouder dan 45 dagen, of een register dat niet door de controle komt: alles oranje, met de reden.
- Elk verslag noemt de bron, de versie van het register, de datum van de bibliotheek en "toets, geen juridisch advies".

## Harde controles op contracten (stap 4)

`masters.toets_contract(tekst)` toetst een contract aan B1 tot B5 en D1 en geeft de bevindingen voor `verslag.maak`.
Wat de controle niet terugvindt, faalt. Bij een uitdrukkelijk beperkte opdracht (voorstudie, regularisatie) worden
aannemer, begroting en programmawijziging oranje tot Mehdi zegt of die regels daar gelden.

    cd mijnagents-runner && python3 -m deontologie.masters contract.docx

De masters zelf zijn Jinja-sjablonen: toets ze gerenderd met de testdossiers van het contractsysteem.

## Grendel met stempel (stap 5)

`stempel.maak(bytes, verslag)` geeft een ondertekende stempel voor het exacte bestand; `stempel.controleer(bytes,
stempel)` zegt of het mag vertrekken. Groen vertrekt, oranje na `bevestig(..., "oranje", "mehdi")`, rood alleen als
Mehdi elk rood punt bevestigt met een reden. Een stempel vervalt na 7 dagen. De sleutel staat buiten git in
`DEONTOLOGIE_STEMPELSLEUTEL` (minstens 32 tekens, dezelfde in de Wacht en in de apps die controleren); zonder sleutel
vertrekt niets. `stempel.py` gebruikt alleen de standaardbibliotheek: de Contractmaker en de werfverslag-apps nemen het
letterlijk over en roepen `controleer()` aan in hun verzend- en exportfunctie. Dat aansluiten gebeurt pas na een ja van
Mehdi, want vanaf dan vertrekt zonder stempel niets meer.

## Werfverslagen (stap 6)

`werfverslagen.toets_werfverslag(Werfverslag(tekst, opgesteld_door, bezocht_door, eerste), architecten)` geeft de
bevindingen voor D1, C1, C3, D3, D5, F1 en G4. Alleen D1 (meerwerk of programmawijziging zonder addendum met de
financiele weerslag) kan rood worden. De lijst `architecten` komt van organisatie.globaal.be; zonder lijst is C1
onbekend. C4 is een dossierregel: `verslag.maak("werfverslag", ..., elders=werfverslagen.ELDERS)`.

Een oordeel dat in orde is, telt als groen (`verslag.OORDEEL_IN_ORDE_IS_GROEN`), zodat een gewoon verslag zonder klik
van Mehdi kan vertrekken. Zo gekozen door Mehdi op 28-10-2026: alleen een verslag met een probleem wacht op hem.

## Budget en verzekering (stap 7)

`budget.d2_begroting(budget, oppervlakte, referentie)` toont de prijs per m² en vergelijkt met een referentie zodra
Mehdi die vastlegt. `budget.d4_verzekering(tekst)` zoekt verzekeraar, polis en tienjarige aansprakelijkheid in een
contract (zit ook in `masters.toets_contract`). `budget.overschrijding(budget, kost, gemeld, verzekering_bijgewerkt)`
geeft D3 en D5 voor een dossier, met een drempel van 15 procent zoals artikel 3.4 van de master. Alles hoogstens oranje.

## Draaien

```
python3 mijnagents-runner/deontologie/register.py
python3 mijnagents-runner/tests/test_deontologie_register.py
python3 mijnagents-runner/tests/test_deontologie_privacypoort.py
python3 mijnagents-runner/tests/test_deontologie_verslag.py
python3 mijnagents-runner/tests/test_deontologie_masters.py
python3 mijnagents-runner/tests/test_deontologie_stempel.py
python3 mijnagents-runner/tests/test_deontologie_werfverslagen.py
python3 mijnagents-runner/tests/test_deontologie_budget.py
```

GitHub draait dezelfde acht bij elke wijziging (`.github/workflows/deontologie-grendels.yml`).

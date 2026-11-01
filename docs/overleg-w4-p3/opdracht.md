# Overleg W4 P3: fototaak voor de iCloud-wacht bij let_op

Repo globaal-appportal, tak `w4-p3-fototaak` (commit 91e0b43). Diff: `docs/overleg-w4-p3/wijziging.diff`.
Vorig besluit: `docs/overleg-w4-fotolijst/verslag.md` (X3/K3 aangenomen: P3 als aparte PR, alleen bij ontbrekende lijst of JPG,
niet bij foto's buiten het venster, dedup op dossier en dag, eerst nagaan wat de iCloud-wacht met HEIC doet).

## Wat de iCloud-wacht met een H-A-fototaak kan (bron: `mijnagents-runner/mac/icloud_wacht.py`)
- `taken()` r.639-735: selecteert foto's uit Photos binnen het taakvenster en 300 m, exporteert ze naar `<bezoekmap>/fotos/`
  (`exporteer_naar` r.310-350), schrijft `00 fotos.md` of bij een bestaande lijst `00 fotos <stempel>.md`, met per geleverd
  bestand `- <utc> | <exportnaam>`.
- Exportnaam is altijd `HHMM <uuid8>.<ext>` (r.320 en r.344), nooit de Photos-naam `IMG_7256.HEIC`, ook al kent zij die
  (`fotos_van` r.81-107, veld `origineel`).
- JPG naast elke HEIC (`jpeg_kopieen` r.453) alleen bij volledige levering (r.727); bij een onbesliste foto blijft de taak open
  en wordt elke 30 minuten een nieuwe lijst geschreven (r.704-712).
Dus: HEIC naar JPG kan zij wel; een lijst voor bestanden met een Photos-naam niet.

## Meting op de VM (30-10-2026, alleen lezen; meetscript in de sessie, niets geschreven)
| Bezoek | In fotos/ | Lijst | Venster | Reden nieuw | Taak |
|---|---|---|---|---|---|
| 2145 15-09 | 5 x IMG_72xx.HEIC | geen | agenda 07:00-09:00 | lijst_ontbreekt | nee: Photos-namen |
| 2145 22-09 | 2 x IMG_75xx.HEIC | geen | geen (agenda en E4 ontbreken) | geen_venster | nee |
| 2173 20-08 | 16 IMG_61xx.HEIC + 16 .jpg | geen | agenda 09:00-10:00 | lijst_ontbreekt | nee: Photos-namen |
| 2173 27-08 | 12 IMG_65xx.HEIC + 12 .jpg | geen | agenda 12:00-13:00 | lijst_ontbreekt | nee: Photos-namen |
| 2405 18-10 | 1015 1FA4D3F8.heic | 50+ stempellijsten, "onvolledig", 9 foto's niet toewijsbaar | agenda 09:00-11:00 | jpg_ontbreekt | al open: klaarzet 3229 sinds 21-10 |
Droge ronde met de nieuwe code over alle open dossiers: W4 let_op 17, ok 5, ontbreekt 8. Eén nieuwe taak: 2324 23-06
(niet_in_fotomap). 2405 krijgt geen tweede taak (open taak gevonden).

## Wat de code doet
- `fotobewijs_reden()` geeft (stand, reden); `fotobewijs()` blijft de stand teruggeven. Standen ongewijzigd.
- `fotoherstel()`: taak alleen bij reden niet_in_fotomap, lijst_ontbreekt of jpg_ontbreekt, met een door de agenda bevestigd
  venster (W1 ok, niet E4), en alleen als elke foto in fotos/ een exportnaam van de iCloud-wacht heeft. Anders zou een taak
  een tweede kopie onder haar eigen naam leveren en blijft W4 let_op.
- Hersteltaak: uniek `...:icloud-wacht:<reden>` (het bord maakt een uniek maar één keer aan, ook na afvinken: geen herhaling),
  inhoud `herstel` (niet `reden`, want de wacht leest `reden == "E4, geen afspraak"`), dedup op dossier en dag
  (`fototaak_open_op_dag` en binnen de ronde).
- Grendeltests: `tests/test_werfketen_eenheid.py` (7 nieuwe), lopen in CI mee via `test_werfketen_controles_11.py`
  (de CI-file zelf kan ik niet wijzigen: token zonder workflow-scope).

## Vragen
1. Is de naamregel juist en minimaal, of moet de taak toch komen voor 2145 15-09 en 2173?
2. Akkoord dat de 5 bezoeken zo klaar zijn: 1 met open taak (2405), 4 met verklaring (3 Photos-namen, 1 geen venster)?
3. Vervolg buiten deze PR, apart voorstel: de iCloud-wacht laat een bestaand bestand met de Photos-naam in de lijst staan
   in plaats van een kopie te maken; JPG ook bij gedeeltelijke levering; geen nieuwe lijst als de inhoud gelijk blijft
   (2405: 50+ lijsten). Uitrol op de Mac vraagt sudo, dus Mehdi. Eens?
4. Toets de diff op fouten. Codex test daarna tot AKKOORD LIVE.

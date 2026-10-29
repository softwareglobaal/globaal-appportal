# Opdracht: waarom blokkeert W4 (foto's) bij werfbezoeken? (29-10-2026)

Mehdi vroeg na de werfketen-eenheid (overleg 28-10, PR 128): zoek uit waarom bij zoveel bezoeken de foto's ontbreken.
Kernoorzaak eerst, kleinste oplossing. Claude is maker, Codex test.

## Gemeten op de VM (alleen gelezen, 30 bezoeken in 7 dossiers)

- W4 ok: 2. W4 ontbreekt: 8 (geen foto's in de map; 6 hebben al een taak voor de iCloud-wacht). W4 let_op: 20.
- let_op blokkeert (`voldaan()` laat alleen W1 let_op door). Voor let_op maakt de voorbereider geen taak voor de
  iCloud-wacht (`controleer()` doet `taken.append` alleen bij ontbreekt).
- Indeling van de 20 let_op (Dropbox-lijst per bezoekmap):
  a) 9 bezoeken: fotos/ met JPG en `00 fotos.md`, maar in het oude formaat van de iCloud-export van 14-09-2026:
     titel `# Foto's 2145 2026-06-06` en een tabel `| 12:02 | 1202 756DF67C.HEIC | 50.86792, 4.7496 | 51 m |`.
     `fotobewijs()` leest alleen het nieuwe formaat `- 2026-10-18T11:47:35+00:00 | IMG_8275.HEIC` (sinds 21-10).
     Dus `tijden` is leeg en het resultaat is altijd let_op, ook als alle foto's binnen het venster vallen.
  b) 4 bezoeken: fotos/ met foto's maar zonder `00 fotos.md` (2145 09-15 en 09-22: alleen HEIC; 2173 08-20 en 08-27).
  c) 6 bezoeken van vóór het systeem: foto's in een oude submap ("fotos iCloud Mehdi", "4. Foto's") of los.
     Al deze hebben ook W1 onbekend en blokkeren dus hoe dan ook.
  d) 2405 18-10: manifest, maar 0 JPG in fotos/ (1 foto, enkel HEIC).

## Voorstellen

P1 (gebouwd, zie wijziging.diff): `fotobewijs()` leest ook de oude tabel, via `oude_fototabel(inhoud, datum)`:
   alleen als de titeldatum gelijk is aan de bezoekdatum, alleen regels met afstand <= 300 m, en de uurtijd telt als
   Europe/Brussels. De rest blijft streng: zonder venster nooit ok; één foto buiten het venster geeft let_op.
   Drie grendeltests in `tests/test_werfketen_eenheid.py`. Droge ronde op de VM, oude tegenover nieuwe versie:
   - 2145 24-06 en 2145 03-07 worden "klaar voor verslag" (W4 was de enige blokkade);
   - bij 2309 03-06 valt W4 weg (stand blijft "verslag aanwezig, bronnen onvolledig" door WERFSTART);
   - totaal "klaar voor verslag": van 1 naar 3. Niets anders verandert.
P2 (vraag, niet gebouwd): 6 bezoeken met de oude tabel blijven terecht let_op, omdat een deel van de foto's buiten
   het agendavenster valt. Voorbeelden: 2145 06-06 (venster 10:30-12:30, foto's 12:02-12:33), 2173 07-07
   (13:00-14:00, foto's 13:30-14:58), 2416 16-06 (11:45-12:45, foto's 09:54-10:10, dus de agenda klopt
   waarschijnlijk niet). Voorstel: niet versoepelen in code. Mehdi beslist per geval (agenda corrigeren of foto
   buiten het venster weghalen).
P3 (vraag, niet gebouwd): voor groep b) en d) staat niemand aan de lat. Voorstel: als W4 let_op is omdat het
   manifest of de JPG ontbreekt en er een bevestigd venster is, krijgt de iCloud-wacht dezelfde fototaak als bij
   ontbreekt. Apart werk, aparte PR, want het raakt de taakstroom van een andere agent.

Vraag aan het overleg: eens met P1 zoals gebouwd? Eens met P2 en P3 als vervolg, of anders?

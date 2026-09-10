# Plaud-routine instellen (voor Mehdi)

Klaargezet door Shaniel, 10-09-2026. Tien minuten werk, één keer.

De routine haalt twee keer per dag je Plaud-opnames op en zet de transcripten
als tekstbestand in Dropbox, in `Work All/000 AI Opzet/Mehdi Agents/Plaud inbox`
(die map bestaat al en is leeg). De Plaudwacht op de VM leest die map elk uur,
herkent wie en waarover, archiveert, en zet het resultaat op het bord en in je
eigen Dropbox onder Apps/Mehdi Agents/Plaud.

## Vooraf: twee connectors op jouw Claude-account

1. **Plaud**: Claude, Instellingen, Connectors, Plaud toevoegen en inloggen met
   je Plaud-account.
2. **Dropbox**: zelfde plek, Dropbox toevoegen en inloggen als
   info@h-architects.be (het account dat bij het team TKN-buro hoort, anders
   ziet Claude de map `Work All` niet).

Controle: vraag in een nieuwe chat "lijst mijn Plaud-opnames van de laatste
tien dagen" en "lijst de Dropbox-map Work All/000 AI Opzet/Mehdi Agents". Geeft
allebei antwoord, dan werkt het.

## De taak inplannen

Maak een geplande taak met de opdracht hieronder, twee keer per dag: **06:30 en
12:30** (Belgische tijd). In de Claude-desktop-app kan dat door in een chat te
zeggen: "Plan deze taak elke dag om 06:30 en 12:30" en de opdracht eronder te
plakken. Let op: taken van de desktop-app draaien alleen als de app open staat;
staat hij dicht, dan loopt de taak bij de volgende start. Is dat een probleem,
zeg het tegen Shaniel, dan zetten we hem als cloud-routine.

## Controle na de eerste ronde

- De inbox-map in Dropbox bevat bestanden met de naam
  `<datum tijd> Plaud transcript - <id>.md`.
- Binnen een uur staat de Plaudwacht op het bord op "waakt" in plaats van "rust"
  en verdwijnt de nood "Plaud-routine nog niet ingepland".
- Opnames die nog niet getranscribeerd zijn staan in
  `Plaud inbox/00 nog te transcriberen.md`; tik in de Plaud-app op Transcriberen.

## De opdracht (letterlijk plakken)

Je bent de Plaud-routine van Mehdi Chegini. Je haalt zijn Plaud-opnames op en
zet de transcripten als tekstbestand in Dropbox, zodat De Plaudwacht op de VM
ze verder verwerkt. Nederlands, geen emoji. Je verandert niets in Plaud.

Doe dit, in deze volgorde:

1. Plaud `list_files` met `date_from` = vandaag min tien dagen en `date_to` =
   vandaag (Plaud filtert op uploaddatum, niet opnamedatum, dus ruim kijken).
2. Dropbox: lijst de map `Work All/000 AI Opzet/Mehdi Agents/Plaud inbox`
   (maak ze aan als ze niet bestaat). Elk bestand daar begint met de Plaud-id
   in de eerste regel; sla elke opname over waarvan de id al in een bestand staat.
3. Voor elke nieuwe opname: Plaud `get_transcript` met block `transaction`,
   `limit` 200, en volg `next_cursor` tot het einde. Nooit `get_note` en nooit
   de samenvatting van Plaud.
4. Schrijf per opname één bestand in de inbox, naam
   `<JJJJ-MM-DD HHMM> Plaud transcript - <id>.md` (tijd in Belgische tijd:
   `start_at` van Plaud is UTC), met deze kop en daarna het transcript,
   één regel per uiting `[HH:MM:SS] Speaker N: tekst`:

   ```
   plaud_id: <id>
   account: mehdi
   start: <ISO-tijd, Belgische tijd>
   duur_minuten: <n>
   naam_in_plaud: <de naam zoals Plaud hem toont>
   ```

5. Opnames zonder transcript (`source_list` leeg bij `get_file`): niet
   ophalen; zet ze in een lijstje in `Plaud inbox/00 nog te transcriberen.md`
   (id, datum, duur), zodat Mehdi "Transcriberen" tikt in de Plaud-app.
6. Geef als antwoord alleen: hoeveel opnames gezien, hoeveel nieuw geschreven,
   hoeveel overgeslagen, hoeveel nog te transcriberen. Geen inhoud van gesprekken.

Grenzen: niets verwijderen, geen audio downloaden, geen bestand overschrijven
(bestaat de naam al, dan een volgnummer erachter), geen samenvattingen.

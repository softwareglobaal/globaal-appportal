# Pipedrive-backup

Elke nacht een volledige kopie van de vijf Pipedrive-administraties
(`harchitects`, `unabo`, `tknburo`, `energieefficient`, `harmoniebouw`), zodat
een storing of dataverlies bij Pipedrive ons de verkoopgegevens niet afneemt.
Aanleiding: de Pipedrive-storing van 18-10-2026 (opdracht Shaniel 19-10-2026).

## Waar staat wat

| Plek | Wat | Wanneer | Bewaard |
|---|---|---|---|
| VM `~/backups/pipedrive/` | alle gegevens, zonder bijlagen | 01:30 UTC | elke run 30 dagen, daarna de eerste van elke maand 12 maanden |
| S3 `globaal-db-backups-2026/pipedrive/<firma>/` | dezelfde gegevens, GPG-versleuteld | direct na de VM-run | 30 dagen (lifecycle van de bucket) |
| Linux-pc kantoor `~/backups/pipedrive/` | alle gegevens plus alle bijlagen (ca. 85 GB) | 02:00 UTC | runs als op de VM; bijlagen blijven staan en groeien aan |

De bijlagen passen niet op de VM (71 GB vrij), daarom staan ze op de Linux-pc
(914 GB schijf). Per run en per firma:

```
<STAMP>/<firma>/data/<soort>.json.gz        volledige API-records, alle velden
<STAMP>/<firma>/manifest.json               tellingen, controles, wat ontbrak en waarom
<STAMP>/<firma>/<firma>-pipedrive-<datum>.xlsx   leesbare kopie, een blad per soort
bestanden/<firma>/<id>/<naam>               bijlagen (alleen op de pc)
status.json                                 stand van de laatste run per firma
laatst-gelukt                               alleen geraakt door een geslaagde run
```

## Wat zit erin

Deals (ook verwijderde en gearchiveerde), leads (ook gearchiveerde), personen,
organisaties, activiteiten, notities, producten, producten per deal, extra
deelnemers per deal, bestanden (lijst en op de pc de bestanden zelf),
gesprekken, mailthreads (inbox, verzonden, concepten, archief), pipelines,
fasen, alle veldenlijsten (ook maatwerkvelden met hun keuzes), filters,
activiteitstypes, leadlabels en -bronnen, rollen, doelen, webhooks, gebruikers.

Bewust niet, en dat staat ook in elk manifest onder `niet_meegenomen`:
- de wijzigingsgeschiedenis per record (kost 20 API-tokens per record; de
  stand van elke nacht blijft wel 30 dagen bewaard);
- de inhoud van e-mails (die staan in de mailboxen zelf; de mailthreads met
  onderwerp, deelnemers en fragment zitten er wel in);
- volgers en notitie-reacties (een gebruiker per administratie).

Projecten en taken geven HTTP 402 (geen add-on); dat staat per run onder
`niet_beschikbaar`. Bestanden die in Pipedrive alleen een link zijn (Google
Drive en dergelijke) worden met hun link bewaard, niet als bestand.

## Controles

- Deals per status (open/gewonnen/verloren) worden elke run vergeleken met de
  samenvatting die Pipedrive zelf geeft; een verschil is een waarschuwing.
- Elke lijst wordt tot het einde gepagineerd en op dubbele records gecontroleerd.
- Daalt een aantal (deals, personen, notities, ...) meer dan 5% ten opzichte van
  de vorige geslaagde run, dan komt er een waarschuwing: dan is er in Pipedrive
  mogelijk iets verdwenen en staat de vorige stand nog in de backup.
- Off-site wordt pas geupload als de versleutelde kopie aantoonbaar terug te
  lezen is (zelfde werkwijze als `scripts/db-backup.sh`).

## API-budget

Pipedrive geeft per firma een dagbudget aan API-tokens (60.000 tot 240.000) dat
we delen met het sales-dashboard, de Pipedrive-MCP en de won-deals-poller. Een
run met alleen gegevens kost 4.000 tot 15.000 tokens. Een bijlage kost 20
tokens; de bijlagen stoppen zodra er nog 35% van het dagbudget over is
(`RESERVE`) en gaan de volgende nacht verder. Daardoor duurt de eerste volledige
binnenhaal van de bijlagen voor H-Architects (48.600 bestanden) ongeveer twee
weken en voor UNABO (25.000) ongeveer een week; de andere firma's de eerste nacht.

## Bewaking

- Uptime-Kuma: push-monitors **62** `Pipedrive-backup (VM + S3)` en **63**
  `Pipedrive-backup bijlagen (Linux-pc)` in de groep Infrastructuur. Rood als
  een run mislukt of er 25 uur geen run was. De push-URL staat als
  `PIPEDRIVE_BACKUP_PUSH_URL` in `~/appportal/.env` (VM) en in
  `~/pipedrive-backup/pipedrive.env` (pc).
- `scripts/gezondheid.py` kijkt naar de leeftijd van `laatst-gelukt` op de VM
  (max 27 uur), zodat de onderhoudsagent een stilgevallen backup ziet.
- Logboek: `~/backups/pipedrive/backup.log` op beide machines.

## Installatie

VM (ubuntu):
```
python3 -m venv ~/.venvs/pipedrive-backup
~/.venvs/pipedrive-backup/bin/pip install openpyxl
crontab -e
30 1 * * * /usr/bin/flock -n /tmp/pipedrive-backup.lock $HOME/.venvs/pipedrive-backup/bin/python $HOME/appportal/pipedrive-backup/backup.py --zonder-bijlagen >> $HOME/backups/pipedrive/backup.log 2>&1
```
Tokens, `S3_BACKUP_BUCKET` en de push-URL komen uit `~/appportal/.env`.

Linux-pc (unbuntu, geen git-toegang tot deze repo: het script wordt gekopieerd):
```
scp pipedrive-backup/backup.py unbuntu@192.168.1.56:pipedrive-backup/backup.py
python3 -m venv ~/pipedrive-backup/.venv && ~/pipedrive-backup/.venv/bin/pip install openpyxl
crontab -e
0 2 * * * /usr/bin/flock -n /tmp/pipedrive-backup.lock $HOME/pipedrive-backup/.venv/bin/python $HOME/pipedrive-backup/backup.py --zonder-offsite --env $HOME/pipedrive-backup/pipedrive.env --doel $HOME/backups/pipedrive >> $HOME/backups/pipedrive/backup.log 2>&1
```
`~/pipedrive-backup/pipedrive.env` (600) bevat de vijf `PIPEDRIVE_TOKEN_*`
(kopie van de VM, rechtstreeks overgezet, nooit via chat) en de push-URL.
Na een tokenrotatie in `~/appportal/.env` dus ook dit bestand bijwerken.

## Terugzetten en inzien

- Snel iets opzoeken tijdens een storing: open de `.xlsx` van de laatste run.
- Alles: `data/*.json.gz` bevat de records precies zoals de API ze gaf, met de
  Pipedrive-id's, zodat ze via de API terug te zetten zijn.
- Vanaf S3 (via de AWS-console downloaden, de VM mag de bucket niet lezen):
  ```
  gpg -d --batch --passphrase-file ~/.backup-passphrase <firma>/<STAMP>.tar.gz.gpg | tar xz
  ```
- Handmatig een run: `--firma <naam>` (herhaalbaar), `--zonder-bijlagen`,
  `--zonder-offsite`, `--zonder-excel`, `--werkers N` (gelijktijdige downloads,
  standaard 8; vanaf kantoor is een enkele download traag).

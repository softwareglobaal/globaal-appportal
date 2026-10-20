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
| Linux-pc kantoor `~/backups/pipedrive/` | alle bijlagen (ca. 85 GB) plus de bestandenlijst | 02:00 UTC, UNABO en TKN nog eens om 08:30 UTC | bijlagen blijven staan en groeien aan |

De bijlagen passen niet op de VM (71 GB vrij), daarom staan ze op de Linux-pc
(914 GB schijf). De pc haalt bewust alleen de bijlagen op (`--alleen-bijlagen`):
de gegevens staan al op de VM en op S3, en een tweede volledige ophaling zou
bij H-Architects 15.000 API-tokens per dag kosten die nu naar bijlagen gaan.
Per run en per firma:

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

Een download telt als compleet als het aantal ontvangen bytes gelijk is aan wat
de server meestuurt (Content-Length). De `file_size` van Pipedrive klopt bij
oude bestanden soms niet; zo'n bestand komt wel binnen en telt mee onder
`grootte_afwijkend`. Sommige oude bestanden kan Pipedrive zelf niet meer leveren
(HTTP 403 van hun opslag): die staan onder `mislukt` en worden elke nacht
opnieuw geprobeerd.

Projecten en taken geven bij de meeste firma's HTTP 402 (geen add-on); dat
staat per run onder `niet_beschikbaar`. Bijlagen staan in het manifest in vier
groepen: binnen, `uitgesteld` (budget, volgende nacht), `mislukt` (met reden,
geeft een waarschuwing), `extern` (in Pipedrive alleen een link naar Google
Drive en dergelijke, de link staat in `bestanden.json`) en `verwijderd` (in
Pipedrive gewist voordat de backup het had).

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
niet voor elke firma op hetzelfde uur terugkomt: H-Architects, HarmonieBOUW en
Energie Efficiënt voor 01:30 UTC, UNABO en TKN-Tekenwerk pas tussen 02:10 en
09:45 UTC (gemeten 20-10-2026, waarschijnlijk 04:00 UTC: middernacht in de VS).
Daarom halen UNABO en TKN hun bijlagen ook om 08:30 UTC op; om 02:00 kregen ze
alleen de restjes van de vorige dag (UNABO 225 bijlagen die nacht). Het budget
wordt gedeeld met het sales-dashboard, de Pipedrive-MCP,
de won-deals-poller en de leadmeldingen (samen bij H-Architects ongeveer 35.000
per dag). Gemeten 19-10-2026: een lijstpagina kost 20 tokens, een bijlage 20.
De VM-run kost per nacht 2.800 (Energie Efficiënt) tot 33.000 tokens
(H-Architects: 49.000 bestanden in pagina's van 100 en 41.000 mailthreads in
pagina's van 50) en duurt voor alle vijf samen ongeveer 20 minuten.

Eerste volledige run 19-10-2026, id voor id nagelopen tegen de v2-API van
Pipedrive (deals, personen, organisaties, activiteiten, producten): niets
ontbrak, niets extra.

| Firma | Deals | Personen | Organisaties | Activiteiten | Notities | Bestanden | Mailthreads |
|---|---|---|---|---|---|---|---|
| H-Architects | 6.403 | 13.950 | 3.171 | 6.463 | 8.379 | 49.127 | 41.078 |
| UNABO | 1.106 | 7.044 | 5.178 | 63 | 4.016 | 25.198 | 8.832 |
| TKN-Tekenwerk | 677 | 7.577 | 5.475 | 3 | 901 | 3.881 | 2.662 |
| Energie Efficiënt | 798 | 6.593 | 4.734 | 46 | 1.018 | 1.631 | 3.011 |
| HarmonieBOUW | 2.030 | 8.219 | 5.346 | 13 | 2.755 | 7.031 | 6.510 |

Bijlagen stoppen zodra er nog 35% van het dagbudget over is (`RESERVE`,
instelbaar met `--reserve`) en gaan de volgende nacht verder. Een download
geeft zelf geen budgetstand terug; het script telt 20 per bijlage en haalt
elke 100 bijlagen de echte stand op. De eerste volledige binnenhaal duurt
daardoor voor H-Architects (48.600 bestanden) ongeveer twee tot drie weken, voor
UNABO (25.000) ongeveer een week en voor de andere firma's een tot twee nachten.

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
0 2 * * * /usr/bin/flock -n /tmp/pipedrive-backup.lock $HOME/pipedrive-backup/.venv/bin/python $HOME/pipedrive-backup/backup.py --alleen-bijlagen --zonder-offsite --env $HOME/pipedrive-backup/pipedrive.env --doel $HOME/backups/pipedrive >> $HOME/backups/pipedrive/backup.log 2>&1
30 8 * * * /usr/bin/flock -n /tmp/pipedrive-backup.lock $HOME/pipedrive-backup/.venv/bin/python $HOME/pipedrive-backup/backup.py --alleen-bijlagen --zonder-offsite --firma unabo --firma tknburo --env $HOME/pipedrive-backup/pipedrive.env --doel $HOME/backups/pipedrive >> $HOME/backups/pipedrive/backup.log 2>&1
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
  `--alleen-bijlagen`, `--zonder-offsite`, `--zonder-excel`, `--reserve 0.35`,
  `--werkers N` (gelijktijdige downloads, standaard 8; vanaf kantoor haalt een
  enkele stroom 0,5 MB/s, acht samen ongeveer 4 MB/s).

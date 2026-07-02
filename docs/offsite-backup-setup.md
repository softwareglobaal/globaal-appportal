# Off-site backups naar S3 — eenmalige setup

Het script (`scripts/db-backup.sh`) is klaar en gepusht; zonder deze setup draait
het gewoon lokaal zoals altijd. Na deze checklist gaat elke nachtelijke dump
(03:15) **GPG-versleuteld** naar S3, met automatische opruiming na 30 dagen.
Tijd: ±10 minuten.

## Deel 1 — AWS-console (console.aws.amazon.com)

**A. Bucket** — dienst **S3** → *Create bucket*:
- Naam: bv. `globaal-db-backups-2026` (wereldwijd uniek — voeg iets eigens toe)
- Region: dezelfde als de VM (**us-east-1, N. Virginia**)
- **"Block all public access" AAN laten** (default) → *Create bucket*

**B. Opruimregel** — bucket → *Management* → *Create lifecycle rule*:
- Naam `verwijder-na-30-dagen`, scope *Apply to all objects*
- Actie *Expire current versions of objects* → **30 dagen** → opslaan

**C. Upload-sleutel** — dienst **IAM** → *Users* → *Create user*:
- Naam `backup-uploader`, géén console-toegang
- *Attach policies directly* → *Create policy* → tab **JSON** (bucketnaam aanpassen):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "s3:PutObject",
    "Resource": "arn:aws:s3:::globaal-db-backups-2026/*"
  }]
}
```
- Policy `backup-upload-only` koppelen → user aanmaken
- User → *Security credentials* → *Create access key* (type **CLI**) →
  Access key ID + Secret bij de hand houden (nooit via chat delen).

De sleutel mag bewust **alleen uploaden**: een gekaapte VM kan de off-site
backups niet lezen of wissen.

## Deel 2 — Op de VM

```bash
# 1. Tools + stack bijwerken
sudo apt-get update -qq && sudo apt-get install -y awscli gnupg
cd ~/appportal && git pull

# 2. AWS-sleutel invoeren (region: us-east-1, output: json)
aws configure

# 3. Passphrase — lange zin, OOK in de wachtwoordkluis (anders backups onleesbaar!)
nano ~/.backup-passphrase        # één regel
chmod 600 ~/.backup-passphrase

# 4. Bucketnaam in .env (nieuwe regel):  S3_BACKUP_BUCKET=globaal-db-backups-2026
nano .env

# 5. Testrun
sh scripts/db-backup.sh
```

**Verwacht:** twee `OK`-regels (dumps) + twee `OK off-site s3://…`-regels.
Daarna eenmalig in de S3-console checken dat er twee `.dump.gpg`-bestanden
staan (de VM kan zelf niet lijsten — bewust). Klaar: vanaf de eerstvolgende
nacht loopt het automatisch mee in de bestaande backup-cron.

**In de wachtwoordkluis:** de GPG-passphrase (kritiek) + kopie van de access key.
**Terugzetten:** download `.dump.gpg` via de console, dan
`gpg -d --passphrase-file ~/.backup-passphrase --batch bestand.dump.gpg > herstel.dump`
en `pg_restore` zoals in de kop van `scripts/db-backup.sh`.

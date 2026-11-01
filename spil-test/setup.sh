#!/bin/sh
# Eenmalige inrichting van SPIL (test) op de VM, als ubuntu, vanuit ~/appportal:
#   sh spil-test/setup.sh
# Idempotent. Bestaande geheimen worden nooit overschreven. Niets hieruit gaat
# naar de uitvoer: de wachtwoorden en het client secret blijven op de VM.
set -eu

BASIS=/home/ubuntu/spil-test
REPO=https://github.com/softwareglobaal/spil.git
ISSUER=https://auth.globaal.be/application/o/spil-test/

# Andere gebruikers op de VM (sufa, joan) horen hier niet te kunnen lezen. De map
# secrets zelf is leesbaar, omdat de app in de container geen root hoeft te zijn.
mkdir -p "$BASIS/secrets"
chmod 700 "$BASIS"
chmod 755 "$BASIS/secrets"

[ -d "$BASIS/code/.git" ] || git clone --quiet "$REPO" "$BASIS/code"

if [ ! -f "$BASIS/.env" ]; then
  pw=$(openssl rand -hex 24)
  sleutel=$(openssl rand -hex 32)
  client_id=$(sh scripts/ak-exec.sh spil-test/oidc-gegevens.py 2>/dev/null | sed -n 's/^CLIENT_ID=//p')
  [ -n "$client_id" ] || { echo "client ID niet gevonden in authentik"; exit 1; }
  umask 077
  cat > "$BASIS/.env" <<EOF
POSTGRES_DB=spil
POSTGRES_USER=spil
POSTGRES_PASSWORD=$pw
DATABASE_URL=postgres://spil:$pw@db:5432/spil
DJANGO_SECRET_KEY=$sleutel
ALLOWED_HOSTS=spil-test.globaal.be
CSRF_TRUSTED_ORIGINS=https://spil-test.globaal.be
OIDC_ISSUER=$ISSUER
OIDC_CLIENT_ID=$client_id
OIDC_CLIENT_SECRET_FILE=/run/secrets/oidc_client_secret
EOF
  echo ".env aangemaakt"
else
  echo ".env bestond al"
fi

if [ ! -s "$BASIS/secrets/oidc_client_secret" ]; then
  # Eerst naar een tijdelijk bestand: een mislukte aanroep mag geen leeg secret achterlaten.
  tijdelijk=$(mktemp)
  sh scripts/ak-exec.sh spil-test/oidc-gegevens.py 2>/dev/null \
    | sed -n 's/^CLIENT_SECRET=//p' > "$tijdelijk"
  [ -s "$tijdelijk" ] || { rm -f "$tijdelijk"; echo "client secret niet gevonden in authentik"; exit 1; }
  chmod 644 "$tijdelijk"
  mv "$tijdelijk" "$BASIS/secrets/oidc_client_secret"
  echo "client secret geplaatst"
else
  echo "client secret bestond al"
fi

regel='*/2 * * * * /home/ubuntu/appportal/spil-test/deploy.sh >> /home/ubuntu/deploy-spil-test.log 2>&1'
if crontab -l 2>/dev/null | grep -qF 'spil-test/deploy.sh'; then
  echo "cron bestond al"
else
  crontab -l > "/home/ubuntu/crontab.bak-spil-test" 2>/dev/null || true
  { crontab -l 2>/dev/null; echo "$regel"; } | crontab -
  echo "cron toegevoegd"
fi

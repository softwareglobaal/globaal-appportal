#!/bin/bash
# Zet een eigen domein (bv. regulariseren.be) op een statische site die al onder
# /srv/websites/<sitenaam>/ draait. Op de server uitvoeren.
#
#   ./eigen-domein.sh regulariseren.be regulariseren
#
# Wat het doet, in deze volgorde, en het stopt bij de eerste fout:
#   1. controleert of de DNS van het domein en van www. naar deze server wijst
#   2. vraagt het Let's Encrypt-certificaat aan (webroot, via de ACME-uitzondering
#      in 00-http-redirect.conf.template)
#   3. draait de deploy-hook, die het certificaat naar ~/appportal/certs/<label>/ kopieert
#   4. plaatst de nginx-template, test de configuratie en herlaadt pas daarna
#
# De volgorde is niet vrijblijvend: nginx weigert te starten als een server-block
# naar een certificaat wijst dat nog niet bestaat, en dan liggen alle sites plat.
set -euo pipefail

DOMEIN="${1:?gebruik: eigen-domein.sh <domein> <sitenaam>}"
SITE="${2:?gebruik: eigen-domein.sh <domein> <sitenaam>}"
LABEL="${DOMEIN%%.*}"
STACK=/home/ubuntu/appportal
TEMPLATE="$STACK/nginx/templates/61-${LABEL}.conf.template"

eigen_ip=$(curl -s -m 10 https://checkip.amazonaws.com || true)
eigen_ip="${eigen_ip//[$'\r\n']/}"
echo "server-IP: ${eigen_ip:-onbekend}"

for host in "$DOMEIN" "www.$DOMEIN"; do
    gevonden=$(dig +short A "$host" | tail -1)
    echo "  $host -> ${gevonden:-geen A-record}"
    if [ "$gevonden" != "$eigen_ip" ]; then
        echo "STOP: $host wijst nog niet naar deze server. Pas eerst het A-record aan."
        echo "      DNS kan tot enkele uren doorlopen; probeer het daarna opnieuw."
        exit 1
    fi
done

[ -d "/srv/websites/$SITE" ] || [ -d "$STACK/websites/$SITE" ] || {
    echo "STOP: er staat nog geen site onder websites/$SITE."; exit 1; }

echo "certificaat aanvragen..."
sudo certbot certonly --webroot -w /home/ubuntu/appportal/certbot-webroot \
    -d "$DOMEIN" -d "www.$DOMEIN" \
    --non-interactive --agree-tos --keep-until-expiring \
    -m info@globaal.be

echo "certificaat naar de nginx-map kopieren..."
sudo /etc/letsencrypt/renewal-hooks/deploy/appportal.sh

[ -f "$TEMPLATE" ] || { echo "STOP: template ontbreekt: $TEMPLATE"; exit 1; }

# Let op: een reload volstaat NIET voor een nieuwe template. De templates worden
# met envsubst gerenderd wanneer de container start, dus de container moet opnieuw
# opgebouwd worden. Dit kostte bij regulariseren.be tijd om te achterhalen.
echo "nginx opnieuw opbouwen (een reload leest nieuwe templates niet)..."
cd "$STACK"
docker compose up -d --force-recreate nginx
sleep 5
docker compose exec -T nginx nginx -t

code=$(curl -sk -m 15 -o /dev/null -w "%{http_code}" "https://$DOMEIN/")
echo "controle: https://$DOMEIN geeft HTTP $code"
[ "$code" = "200" ] || { echo "LET OP: geen 200, controleer de site."; exit 1; }
echo "klaar: https://$DOMEIN"

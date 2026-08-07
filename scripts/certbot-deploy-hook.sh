#!/bin/bash
# Certbot deploy-hook voor de AppPortal-stack.
#
# Installeren op de server:
#   sudo cp scripts/certbot-deploy-hook.sh /etc/letsencrypt/renewal-hooks/deploy/appportal.sh
#   sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/appportal.sh
#
# Waarom dit bestaat: certbot vernieuwt de certificaten in /etc/letsencrypt/live,
# maar nginx draait in een container en leest ze via een bind-mount van
# ~/appportal/certs. Zonder deze hook vernieuwt het certificaat wel, maar blijft
# nginx het oude serveren tot dat verloopt en krijgen bezoekers een waarschuwing.
#
# Naamgeving (volgt de bestaande nginx-templates):
#   globaal.be (wildcard) -> certs/fullchain.pem + certs/privkey.pem
#   elk ander domein      -> certs/<eerste-label>/, bv. elevaitnv.com -> certs/elevaitnv/
#
# Historie: tot 03-08-2026 kopieerde deze hook uitsluitend globaal.be. Eigen
# domeinen (elevaitnv.com, en later regulariseren.be) vielen daardoor buiten de
# boot en zouden na hun eerste vernieuwing een verlopen certificaat tonen. Sinds
# 03-08-2026 loopt de hook over alle uitgegeven certificaten.
set -u

CERTS=/home/ubuntu/appportal/certs
LIVE=/etc/letsencrypt/live

for dir in "$LIVE"/*/; do
    [ -f "${dir}fullchain.pem" ] || continue
    naam=$(basename "$dir")
    if [ "$naam" = "globaal.be" ]; then
        doel="$CERTS"
    else
        doel="$CERTS/${naam%%.*}"
        mkdir -p "$doel"
    fi
    cp "${dir}fullchain.pem" "$doel/fullchain.pem"
    cp "${dir}privkey.pem"   "$doel/privkey.pem"
    echo "certificaat bijgewerkt: $naam -> $doel"
done

chown -R ubuntu:ubuntu "$CERTS"
find "$CERTS" -name privkey.pem -exec chmod 600 {} +

cd /home/ubuntu/appportal || exit 1
docker compose exec -T nginx nginx -s reload 2>/dev/null || docker compose restart nginx

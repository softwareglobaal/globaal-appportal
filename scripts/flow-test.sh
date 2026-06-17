#!/bin/sh
# Protocol-level flow test, run from the AppPortal directory.
# Proves: portal /login builds a valid OIDC authorize redirect (Authlib
# fetched the discovery metadata from Authentik), and forward auth sends
# unauthenticated app requests into the Authentik login flow.
set -u
CA=certs/ca.crt
D="${BASE_DOMAIN:-localhost}"
R1="--resolve portal.$D:443:127.0.0.1"
R2="--resolve auth.$D:443:127.0.0.1"
R3="--resolve factorydocs.$D:443:127.0.0.1"

echo "--- portal /login -> OIDC authorize redirect:"
curl -s -o /dev/null -D - --cacert "$CA" $R1 "https://portal.$D/login" | grep -i "^location" | cut -c1-160

echo "--- factorydocs -> outpost signin redirect:"
curl -s -o /dev/null -D - --cacert "$CA" $R3 "https://factorydocs.$D/" | grep -i "^location" | cut -c1-160

echo "--- full chain portal -> authentik login page (cookies on):"
code=$(curl -s -o /dev/null -w "%{http_code} %{url_effective}" -L --max-redirs 8 \
    -c /tmp/cj.txt -b /tmp/cj.txt --cacert "$CA" $R1 $R2 "https://portal.$D/")
echo "final: $code" | cut -c1-160

echo "--- full chain factorydocs -> authentik login page (cookies on):"
code=$(curl -s -o /dev/null -w "%{http_code} %{url_effective}" -L --max-redirs 8 \
    -c /tmp/cj2.txt -b /tmp/cj2.txt --cacert "$CA" $R3 $R2 "https://factorydocs.$D/")
echo "final: $code" | cut -c1-160
rm -f /tmp/cj.txt /tmp/cj2.txt

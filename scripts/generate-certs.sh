#!/bin/sh
# Generates a local CA and a wildcard certificate for *.${BASE_DOMAIN} into /certs.
# Idempotent: exits immediately when certs for the current BASE_DOMAIN already exist.
# Runs inside the one-shot 'certgen' alpine container (see docker-compose.yml).
set -eu

CERT_DIR=/certs

# Production with real certificates (e.g. Let's Encrypt): set CERTGEN_DISABLE=1
# in .env so this one-shot container never touches the certs you dropped in.
if [ "${CERTGEN_DISABLE:-0}" = "1" ]; then
    echo "certgen: disabled (CERTGEN_DISABLE=1); leaving existing certs untouched."
    exit 0
fi

DOMAIN="${BASE_DOMAIN:?BASE_DOMAIN is not set}"
# Explicit SANs are required: TLS stacks reject wildcards on single-label
# base domains (*.localhost never matches auth.localhost). When adding a new
# subdomain (fifth app), extend CERT_SUBDOMAINS in .env — certs regenerate
# automatically on the next docker compose up.
SUBDOMAINS="${CERT_SUBDOMAINS:-auth portal factorydocs inventory finance maintenance omv}"
MARKER="$CERT_DIR/.domain"
WANT="$DOMAIN $SUBDOMAINS"

if [ -f "$CERT_DIR/fullchain.pem" ] && [ -f "$CERT_DIR/privkey.pem" ] \
   && [ -f "$MARKER" ] && [ "$(cat "$MARKER")" = "$WANT" ]; then
    echo "certgen: certificates for $WANT already exist, nothing to do."
    exit 0
fi

command -v openssl >/dev/null 2>&1 || apk add --no-cache openssl

echo "certgen: generating local CA and wildcard certificate for *.$DOMAIN"
cd "$CERT_DIR"

# Local CA — import ca.crt into your browser/OS trust store once.
# Reuse an existing CA so adding a subdomain (new app) only reissues the leaf
# certificate; the CA you already trusted in the browser keeps working.
if [ ! -f ca.crt ] || [ ! -f ca.key ]; then
    echo "certgen: creating a new local CA"
    openssl genrsa -out ca.key 4096 2>/dev/null
    openssl req -x509 -new -nodes -key ca.key -sha256 -days 1825 \
        -subj "/CN=AppPortal Local CA" -out ca.crt
else
    echo "certgen: reusing existing local CA (no re-import needed)"
fi

# Leaf certificate signed by that CA: wildcard plus explicit per-host SANs.
openssl genrsa -out privkey.pem 2048 2>/dev/null
openssl req -new -key privkey.pem -subj "/CN=*.$DOMAIN" -out leaf.csr
SAN="DNS:$DOMAIN,DNS:*.$DOMAIN"
for sub in $SUBDOMAINS; do
    SAN="$SAN,DNS:$sub.$DOMAIN"
done
printf 'subjectAltName=%s\nextendedKeyUsage=serverAuth\n' "$SAN" > leaf.ext
openssl x509 -req -in leaf.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -days 825 -sha256 -extfile leaf.ext -out leaf.crt
cat leaf.crt ca.crt > fullchain.pem
rm -f leaf.csr leaf.ext leaf.crt

printf '%s' "$WANT" > "$MARKER"
echo "certgen: done. Import certs/ca.crt into your browser to trust the stack."

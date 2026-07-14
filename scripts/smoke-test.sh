#!/bin/sh
# Quick endpoint smoke test, run from the AppPortal directory:
#   docker compose ps   # everything healthy first
#   sh scripts/smoke-test.sh
# Uses --resolve so it works even where *.localhost doesn't resolve.
set -u
CA=certs/ca.crt
D="${BASE_DOMAIN:-localhost}"

check() {
    name="$1"; shift
    echo "--- $name"
    curl -sI --max-time 10 "$@" | head -4
    echo ""
}

check "HTTP -> HTTPS redirect"  -H "Host: portal.$D" "http://127.0.0.1/"
check "auth.$D (Authentik, CA-verified TLS)" \
    --cacert "$CA" --resolve "auth.$D:443:127.0.0.1" "https://auth.$D/"
check "portal.$D (portal)" \
    --cacert "$CA" --resolve "portal.$D:443:127.0.0.1" "https://portal.$D/"
check "factorydocs.$D (forward auth)" \
    --cacert "$CA" --resolve "factorydocs.$D:443:127.0.0.1" "https://factorydocs.$D/"
check "finance.$D (forward auth)" \
    --cacert "$CA" --resolve "finance.$D:443:127.0.0.1" "https://finance.$D/"

# Connectivity check, run inside the portal container:
#   docker compose exec -T portal python < scripts/check-portal-to-auth.py
# Verifies the portal can reach Authentik on its public hostname (nginx
# network alias) with TLS verified against the local CA (REQUESTS_CA_BUNDLE).
import requests

r = requests.get("https://auth.localhost/api/v3/root/config/", timeout=10)
print("status:", r.status_code)
print("tls: verified against", __import__("os").environ.get("REQUESTS_CA_BUNDLE"))

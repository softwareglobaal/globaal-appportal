"""Probe: after TOTP enforcement, a fresh login must hit the TOTP setup stage.
Run: docker compose exec -T portal python < scripts/totp-probe.py
"""
import os
import re
from urllib.parse import urlsplit

import requests

BASE = os.environ.get("BASE_DOMAIN", "localhost")
AUTH = f"https://auth.{BASE}"

s = requests.Session()
s.verify = os.environ.get("REQUESTS_CA_BUNDLE", "/certs/ca.crt")
r = s.get(f"https://portal.{BASE}/", allow_redirects=True)
parts = urlsplit(r.url)
slug = re.match(r"/if/flow/([^/]+)/", parts.path).group(1)
executor = f"{AUTH}/api/v3/flows/executor/{slug}/?query={requests.utils.quote(parts.query, safe='')}"
data = s.get(executor).json()
csrf = s.cookies.get("authentik_csrf", "")
headers = {"X-authentik-CSRF": csrf, "X-CSRFToken": csrf}
data = s.post(
    executor,
    json={
        "component": "ak-stage-identification",
        "uid_field": "testmanager",
        "password": "AppPortal-Demo-2026!",
    },
    headers=headers,
).json()
if data.get("component") == "ak-stage-password":
    data = s.post(
        executor,
        json={"component": "ak-stage-password", "password": "AppPortal-Demo-2026!"},
        headers=headers,
    ).json()
print("component after credentials:", data.get("component"))
print("TOTP_ENFORCED" if "authenticator" in str(data.get("component")) else "TOTP_NOT_ENFORCED")

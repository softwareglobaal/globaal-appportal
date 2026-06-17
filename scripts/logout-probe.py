"""Characterize app-level logout: log in (password only), open an app, log out,
then re-check the app immediately and after a short delay.
Run: docker compose exec -T portal python < scripts/logout-probe.py
"""
import os
import re
import time
from urllib.parse import urlsplit

import requests

BASE = os.environ.get("BASE_DOMAIN", "localhost")
AUTH = f"https://auth.{BASE}"
PORTAL = f"https://portal.{BASE}"
PASSWORD = "AppPortal-Demo-2026!"


def run_flow(s, url, user):
    r = s.get(url, allow_redirects=True)
    p = urlsplit(r.url)
    m = re.match(r"/if/flow/([^/]+)/", p.path)
    if not m:
        return r
    ex = f"{AUTH}/api/v3/flows/executor/{m.group(1)}/?query={requests.utils.quote(p.query, safe='')}"
    for _ in range(10):
        d = s.get(ex).json()
        c = d.get("component", "")
        csrf = s.cookies.get("authentik_csrf", "")
        h = {"X-authentik-CSRF": csrf, "X-CSRFToken": csrf}
        if c == "ak-stage-identification":
            payload = {"component": c, "uid_field": user}
        elif c == "ak-stage-password":
            payload = {"component": c, "password": PASSWORD}
        elif c == "xak-flow-redirect":
            to = d["to"]
            return s.get(AUTH + to if to.startswith("/") else to, allow_redirects=True)
        else:
            return d
        d = s.post(ex, json=payload, headers=h).json()
        if d.get("component") == "xak-flow-redirect":
            to = d["to"]
            return s.get(AUTH + to if to.startswith("/") else to, allow_redirects=True)
    return None


def app_reachable(s):
    r = s.get(f"https://factorydocs.{BASE}/", allow_redirects=True)
    return r.status_code == 200 and f"factorydocs.{BASE}" in r.url and "testmanager" in r.text


s = requests.Session()
s.verify = os.environ.get("REQUESTS_CA_BUNDLE", "/certs/ca.crt")
run_flow(s, f"{PORTAL}/", "testmanager")
print("logged in, app reachable:", app_reachable(s))

# global logout via the portal -> invalidation flow
r = s.get(f"{PORTAL}/logout", allow_redirects=True)
p = urlsplit(r.url)
m = re.match(r"/if/flow/([^/]+)/", p.path)
if m:
    ex = f"{AUTH}/api/v3/flows/executor/{m.group(1)}/?query={requests.utils.quote(p.query, safe='')}"
    s.get(ex)

print("portal reachable right after logout:",
      s.get(f"{PORTAL}/", allow_redirects=True).url.startswith(PORTAL + "/") is False)
print("app reachable 0s after logout:", app_reachable(s))
for wait in (3, 10, 30):
    time.sleep(wait)
    print(f"app reachable after ~{wait}s more:", app_reachable(s))

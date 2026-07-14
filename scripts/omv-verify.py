"""Verify the OMV Pipeline tile + forward-auth placeholder (password-only login).
Run: docker compose exec -T portal python < scripts/omv-verify.py
"""
import os
import re
from urllib.parse import urlsplit

import requests

BASE = os.environ.get("BASE_DOMAIN", "localhost")
AUTH = f"https://auth.{BASE}"
PORTAL = f"https://portal.{BASE}"
PASSWORD = "AppPortal-Demo-2026!"
fails = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}: {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        fails.append(name)


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


# Unauthenticated: forward auth must guard the app.
anon = requests.Session(); anon.verify = "/certs/ca.crt"
r = anon.get(f"https://omv.{BASE}/", allow_redirects=False)
check("omv.<domain> is guarded by forward auth (302 to outpost)",
      r.status_code == 302 and "outpost.goauthentik.io/start" in r.headers.get("location", ""),
      r.headers.get("location", "")[:80])

# Logged in (password only): tile present + click-through to placeholder.
s = requests.Session(); s.verify = "/certs/ca.crt"
r = run_flow(s, f"{PORTAL}/", "testmanager")
body = r.text if isinstance(r, requests.Response) else ""
check("portal shows OMV Pipeline tile", "OMV Pipeline" in body)
check("OMV tile links to /go/omv", "/go/omv" in body)

r = s.get(f"{PORTAL}/go/omv", allow_redirects=True)
ok = r.status_code == 200 and f"omv.{BASE}" in r.url and "testmanager" in r.text
check("click-through to OMV shows SSO user, no second login", ok, r.url)
check("OMV placeholder note is shown", "dataserver" in r.text.lower())

print()
print("OMV_VERIFY: " + ("ALL PASSED" if not fails else f"{len(fails)} FAILED {fails}"))

"""Authenticated end-to-end journey INCLUDING the enforced TOTP step.

Prereq: scripts/enroll-totp.py has enrolled a known TOTP secret for the demo
users. Computes RFC-6238 codes with the standard library only (no pyotp).
Run: docker compose exec -T portal python < scripts/full-journey.py
"""
import hashlib
import hmac
import os
import re
import struct
import sys
import time
from urllib.parse import urlsplit

import requests

BASE = os.environ.get("BASE_DOMAIN", "localhost")
CA = os.environ.get("REQUESTS_CA_BUNDLE", "/certs/ca.crt")
AUTH = f"https://auth.{BASE}"
PORTAL = f"https://portal.{BASE}"
PASSWORD = "AppPortal-Demo-2026!"
SECRET = b"AppPortalTOTPsecret1"

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}: {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(name)


def totp(secret, step=30, digits=6):
    counter = int(time.time()) // step
    mac = hmac.new(secret, struct.pack(">Q", counter), hashlib.sha1).digest()
    off = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[off : off + 4])[0] & 0x7FFFFFFF) % (10**digits)
    return str(code).zfill(digits)


def run_flow(session, start_url, username):
    r = session.get(start_url, allow_redirects=True)
    parts = urlsplit(r.url)
    m = re.match(r"/if/flow/([^/]+)/", parts.path)
    if not m:
        return r
    executor = (
        f"{AUTH}/api/v3/flows/executor/{m.group(1)}/"
        f"?query={requests.utils.quote(parts.query, safe='')}"
    )
    for _ in range(12):
        data = session.get(executor).json()
        comp = data.get("component", "")
        csrf = session.cookies.get("authentik_csrf", "")
        hdr = {"X-authentik-CSRF": csrf, "X-CSRFToken": csrf}
        if comp == "ak-stage-identification":
            payload = {"component": comp, "uid_field": username}
        elif comp == "ak-stage-password":
            payload = {"component": comp, "password": PASSWORD}
        elif comp == "ak-stage-authenticator-validate":
            payload = {"component": comp, "code": totp(SECRET)}
        elif comp == "xak-flow-redirect":
            to = data["to"]
            return session.get(AUTH + to if to.startswith("/") else to, allow_redirects=True)
        elif comp == "ak-stage-access-denied":
            return data
        else:
            return data
        data = session.post(executor, json=payload, headers=hdr).json()
        if data.get("component") == "xak-flow-redirect":
            to = data["to"]
            return session.get(AUTH + to if to.startswith("/") else to, allow_redirects=True)
        if data.get("response_errors"):
            print(f"  flow errors: {data['response_errors']}")
            return data
    return None


def new_session():
    s = requests.Session()
    s.verify = CA
    return s


# manager: full TOTP login -> all 4 tiles -> SSO click-through -> single logout
s = new_session()
r = run_flow(s, f"{PORTAL}/", "testmanager")
check("manager full login (password + TOTP) lands on portal",
      isinstance(r, requests.Response) and r.url.startswith(PORTAL), getattr(r, "url", str(r)[:100]))
body = r.text if isinstance(r, requests.Response) else ""
for tile in ["FactoryDocs", "InventoryTracker", "FinanceDashboard", "MaintenanceLog"]:
    check(f"manager sees {tile}", tile in body)

r = s.get(f"https://factorydocs.{BASE}/", allow_redirects=True)
check("SSO click-through to FactoryDocs, no second login",
      r.status_code == 200 and "testmanager" in r.text, r.url)

r = s.get(f"{PORTAL}/logout", allow_redirects=True)
parts = urlsplit(r.url)
m = re.match(r"/if/flow/([^/]+)/", parts.path)
if m:
    ex = f"{AUTH}/api/v3/flows/executor/{m.group(1)}/?query={requests.utils.quote(parts.query, safe='')}"
    s.get(ex)
r = s.get(f"{PORTAL}/", allow_redirects=True)
check("single logout: portal demands login again", f"auth.{BASE}" in r.url and "/if/flow/" in r.url, r.url)

# admin: role filtering + Authentik enforcement on direct app access
s2 = new_session()
r = run_flow(s2, f"{PORTAL}/", "testadmin")
body = r.text if isinstance(r, requests.Response) else ""
check("admin full login lands on portal", isinstance(r, requests.Response) and r.url.startswith(PORTAL))
check("admin sees FactoryDocs", "FactoryDocs" in body)
check("admin does NOT see FinanceDashboard", "FinanceDashboard" not in body)
r = s2.get(f"{PORTAL}/go/finance", allow_redirects=False)
check("portal blocks admin /go/finance (403)", r.status_code == 403, str(r.status_code))
r = run_flow(s2, f"https://finance.{BASE}/", "testadmin")
denied = (isinstance(r, requests.Response) and ("denied" in r.text.lower() or "authorize" in r.url)) \
    or (isinstance(r, dict) and r.get("component") == "ak-stage-access-denied")
check("Authentik denies admin direct access to finance", denied)

print()
if failures:
    print(f"JOURNEY_RESULT: {len(failures)} FAILED: {failures}")
    sys.exit(1)
print("JOURNEY_RESULT: ALL PASSED")

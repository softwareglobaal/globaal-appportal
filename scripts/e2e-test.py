"""End-to-end SSO verification, run inside the portal container:

    docker compose exec -T portal python < scripts/e2e-test.py

Drives the full user journey without a browser, via Authentik's flow-executor
JSON API: login -> portal tiles per role -> SSO click-through to an app ->
direct-access denial -> single logout. Requires the test users from
scripts/create-test-users.py and the nginx hostname aliases.

NOTE: once TOTP enforcement is active (setup-authentik.py applies it), fresh
logins hit the TOTP enrollment stage, which this script does not automate -
the login steps will then stop there. Use scripts/totp-probe.py to verify
that enforcement instead.
"""
import os
import re
import sys
from urllib.parse import urlsplit

import requests

BASE = os.environ.get("BASE_DOMAIN", "localhost")
CA = os.environ.get("REQUESTS_CA_BUNDLE", "/certs/ca.crt")
AUTH = f"https://auth.{BASE}"
PORTAL = f"https://portal.{BASE}"
PASSWORD = "AppPortal-Demo-2026!"

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}: {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(name)


def run_flow(session, start_url, username):
    """Follow redirects to an Authentik /if/flow/ page, then complete the
    flow via the JSON executor API and follow the final redirect chain."""
    r = session.get(start_url, allow_redirects=True)
    parts = urlsplit(r.url)
    m = re.match(r"/if/flow/([^/]+)/", parts.path)
    if not m:
        return r  # no login flow -> already authenticated
    flow_slug = m.group(1)
    executor = f"{AUTH}/api/v3/flows/executor/{flow_slug}/?query={requests.utils.quote(parts.query, safe='')}"
    for _ in range(10):
        data = session.get(executor).json()
        comp = data.get("component", "")
        if comp == "ak-stage-identification":
            payload = {"component": comp, "uid_field": username}
            if data.get("password_fields"):
                payload["password"] = PASSWORD
        elif comp == "ak-stage-password":
            payload = {"component": comp, "password": PASSWORD}
        elif comp == "xak-flow-redirect":
            to = data["to"]
            if to.startswith("/"):
                to = AUTH + to
            return session.get(to, allow_redirects=True)
        elif comp == "ak-stage-access-denied":
            return data
        else:
            print(f"  unexpected flow component: {comp}: {str(data)[:200]}")
            return data
        csrf = session.cookies.get("authentik_csrf", "")
        r = session.post(
            executor,
            json=payload,
            headers={"X-authentik-CSRF": csrf, "X-CSRFToken": csrf},
        )
        data = r.json()
        if data.get("component") == "xak-flow-redirect":
            to = data["to"]
            if to.startswith("/"):
                to = AUTH + to
            return session.get(to, allow_redirects=True)
        if data.get("response_errors"):
            print(f"  flow errors: {data['response_errors']}")
            return data
    return None


def new_session():
    s = requests.Session()
    s.verify = CA
    return s


# --- 1. testmanager: login via portal OIDC ----------------------------------
s = new_session()
r = run_flow(s, f"{PORTAL}/", "testmanager")
ok = isinstance(r, requests.Response) and r.status_code == 200 and r.url.startswith(PORTAL)
check("manager OIDC login lands on portal", ok, getattr(r, "url", str(r)[:120]))
body = r.text if isinstance(r, requests.Response) else ""
for tile in ["FactoryDocs", "InventoryTracker", "FinanceDashboard", "MaintenanceLog"]:
    check(f"manager sees {tile} tile", tile in body)
check("maintenance shows in-development badge", "in development" in body)

# --- 2. SSO click-through to FactoryDocs (no second login) -------------------
r = s.get(f"https://factorydocs.{BASE}/", allow_redirects=True)
ok = r.status_code == 200 and "testmanager" in r.text and f"factorydocs.{BASE}" in r.url
check("click-through to FactoryDocs shows username, no login", ok, r.url)

# --- 3. portal /go/ redirect + access logging --------------------------------
r = s.get(f"{PORTAL}/go/finance", allow_redirects=True)
check("manager /go/finance reaches FinanceDashboard", r.status_code == 200 and "FinanceDashboard" in r.text)

# --- 4. single logout ---------------------------------------------------------
# A browser executes the invalidation flow via the SPA's JS; here we drive
# the executor API explicitly, like run_flow does for login.
r = s.get(f"{PORTAL}/logout", allow_redirects=True)
parts = urlsplit(r.url)
m = re.match(r"/if/flow/([^/]+)/", parts.path)
check("portal /logout redirects into an Authentik flow", bool(m), r.url)
if m:
    executor = (
        f"{AUTH}/api/v3/flows/executor/{m.group(1)}/"
        f"?query={requests.utils.quote(parts.query, safe='')}"
    )
    data = s.get(executor).json()
    print(f"  logout flow component: {data.get('component')}")
r = s.get(f"{PORTAL}/", allow_redirects=True)
check(
    "after logout, portal demands login again (authentik session dead)",
    f"auth.{BASE}" in r.url and "/if/flow/" in r.url,
    r.url,
)
r = s.get(f"https://factorydocs.{BASE}/", allow_redirects=True)
ok = f"auth.{BASE}" in r.url  # back at the Authentik login flow
check("after logout, app demands login again (single logout)", ok, r.url)

# --- 5. testadmin: role filtering + enforcement ------------------------------
s2 = new_session()
r = run_flow(s2, f"{PORTAL}/", "testadmin")
body = r.text if isinstance(r, requests.Response) else ""
check("admin OIDC login lands on portal", isinstance(r, requests.Response) and r.url.startswith(PORTAL))
check("admin sees FactoryDocs tile", "FactoryDocs" in body)
check("admin does NOT see FinanceDashboard tile", "FinanceDashboard" not in body)

# portal-level guard
r = s2.get(f"{PORTAL}/go/finance", allow_redirects=False)
check("portal blocks admin /go/finance (403)", r.status_code == 403, str(r.status_code))

# authentik-level enforcement on direct URL access
r = run_flow(s2, f"https://finance.{BASE}/", "testadmin")
if isinstance(r, requests.Response):
    denied = "denied" in r.text.lower() or r.status_code in (401, 403)
    detail = f"status={r.status_code} url={r.url}"
else:
    denied = (r or {}).get("component") == "ak-stage-access-denied"
    detail = str(r)[:120]
check("Authentik denies admin direct access to finance app", denied, detail)

print()
if failures:
    print(f"E2E_RESULT: {len(failures)} FAILED: {failures}")
    sys.exit(1)
print("E2E_RESULT: ALL PASSED")

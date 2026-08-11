"""Google Ads-client voor de Sales/Marketing-agents (siyanagents).

Zelfde principe als de Pipedrive-client:
  - LEZEN is vrij: accounts() en zoek() (GAQL) mag een agent direct.
  - SCHRIJVEN is gevoelig (raakt echt advertentiebudget): schrijf() gaat alleen
    via de voorstellen-poort, na menselijke goedkeuring, door de SM-uitvoerder.

Geen zware SDK: OAuth-refresh + REST via urllib. Credentials bij naam uit de
gedeelde ~/appportal/.env (GOOGLE_ADS_*), nooit gelogd.
"""
import json
import os
import urllib.parse
import urllib.request

ENV_PADEN = ("~/appportal/siyanagents-data/.env", "~/appportal/.env")
VERSIE = os.environ.get("GOOGLE_ADS_API_VERSION", "v21")
OAUTH = "https://oauth2.googleapis.com/token"
API = "https://googleads.googleapis.com"


def _laad_env():
    for pad in ENV_PADEN:
        try:
            for line in open(os.path.expanduser(pad)):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k, v.strip().strip('"').strip("'"))
        except OSError:
            pass


def _creds():
    _laad_env()
    c = {
        "client_id": os.environ.get("GOOGLE_ADS_CLIENT_ID", ""),
        "client_secret": os.environ.get("GOOGLE_ADS_CLIENT_SECRET", ""),
        "refresh_token": os.environ.get("GOOGLE_ADS_REFRESH_TOKEN", ""),
        "developer_token": os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", ""),
        "login_customer_id": os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", ""),
    }
    ontbreekt = [k for k, v in c.items() if not v and k != "login_customer_id"]
    if ontbreekt:
        raise RuntimeError(f"Google Ads-credentials ontbreken: {', '.join(ontbreekt)}")
    return c


def _access_token():
    c = _creds()
    body = urllib.parse.urlencode({
        "client_id": c["client_id"], "client_secret": c["client_secret"],
        "refresh_token": c["refresh_token"], "grant_type": "refresh_token"}).encode()
    req = urllib.request.Request(OAUTH, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())["access_token"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OAuth-refresh mislukt HTTP {e.code}: {e.read().decode()[:200]}")


def _headers(login=True):
    c = _creds()
    h = {"Authorization": f"Bearer {_access_token()}",
         "developer-token": c["developer_token"], "Content-Type": "application/json"}
    if login and c["login_customer_id"]:
        h["login-customer-id"] = c["login_customer_id"]
    return h


def _call(method, path, body=None, login=True):
    url = f"{API}/{VERSIE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in _headers(login=login).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Google Ads {method} {path} -> HTTP {e.code}: {e.read().decode()[:300]}")


# ---- LEZEN (vrij) -----------------------------------------------------------

def accounts():
    """Toegankelijke accounts (resource-namen). Goede verbindingscheck."""
    return _call("GET", "/customers:listAccessibleCustomers", login=False).get("resourceNames", [])


def zoek(customer_id, gaql):
    """GAQL-query tegen een account. customer_id met of zonder streepjes."""
    cid = str(customer_id).replace("-", "")
    uit = _call("POST", f"/customers/{cid}/googleAds:searchStream", {"query": gaql})
    rijen = []
    for blok in (uit if isinstance(uit, list) else [uit]):
        rijen.extend(blok.get("results", []))
    return rijen


# ---- SCHRIJVEN (alleen via de uitvoerder, na goedkeuring) -------------------

def schrijf(customer_id, path, body):
    """Muterende call (mutate). path is relatief vanaf /customers/{cid}, bv.
    '/campaignBudgets:mutate'. Body bevat de operations. Geeft (resultaat, kort)."""
    cid = str(customer_id).replace("-", "")
    vol = f"/customers/{cid}{path}"
    uit = _call("POST", vol, body)
    n = len(uit.get("results", [])) if isinstance(uit, dict) else 0
    return uit, f"POST {vol} ok ({n} resultaten)"

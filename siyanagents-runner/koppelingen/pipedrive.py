"""Pipedrive-client voor de Sales/Marketing-agents (siyanagents).

Ontwerp:
  - LEZEN is vrij: get() / lijst() mag een agent direct aanroepen.
  - SCHRIJVEN is gevoelig: post/put/delete gaan NIET rechtstreeks vanuit een
    agent, maar via de voorstellen-poort (agent stelt voor -> mens keurt goed ->
    de SM-uitvoerder roept hier schrijf() aan). Daarom staat schrijf() los en
    logt het altijd wat het deed.

Tokens: per firma in de gedeelde ~/appportal/.env als PIPEDRIVE_TOKEN_<FIRMA>.
De waarden worden hier bij naam gelezen; nooit gelogd.
"""
import json
import os
import urllib.parse
import urllib.request

BASIS = "https://api.pipedrive.com/v1"
ENV_PADEN = ("~/appportal/siyanagents-data/.env", "~/appportal/.env")

# Firma-sleutel -> naam van de env-variabele met het token.
FIRMAS = {
    "unabo": "PIPEDRIVE_TOKEN_UNABO",
    "harchitects": "PIPEDRIVE_TOKEN_HARCHITECTS",
    "energie-efficient": "PIPEDRIVE_TOKEN_ENERGIEEFFICIENT",
    "tkn-buro": "PIPEDRIVE_TOKEN_TKNBURO",
}


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


def _token(firma):
    _laad_env()
    var = FIRMAS.get((firma or "").lower())
    if not var:
        raise ValueError(f"onbekende firma '{firma}' (keuze: {', '.join(FIRMAS)})")
    tok = os.environ.get(var, "")
    if not tok:
        raise RuntimeError(f"{var} ontbreekt in de .env")
    return tok


def _vraag(firma, method, path, params=None, body=None):
    params = dict(params or {})
    params["api_token"] = _token(firma)
    url = f"{BASIS}{path}?{urllib.parse.urlencode(params)}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            uit = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"Pipedrive {method} {path} -> HTTP {e.code}: {detail}")
    if not uit.get("success", False):
        raise RuntimeError(f"Pipedrive {method} {path} niet ok: {uit.get('error')}")
    return uit


# ---- LEZEN (vrij) -----------------------------------------------------------

def get(firma, path, params=None):
    """Willekeurige GET, bv. get('unabo', '/deals', {'status': 'open'})."""
    return _vraag(firma, "GET", path, params=params).get("data")


def lijst(firma, wat, **params):
    """Kortere vorm: lijst('unabo', 'deals', status='open', limit=20)."""
    return get(firma, f"/{wat}", params)


def wie(firma):
    """Verbindingscheck: geeft de gekoppelde gebruiker/bedrijf terug."""
    return get(firma, "/users/me")


# ---- SCHRIJVEN (alleen via de uitvoerder, na goedkeuring) -------------------

SCHRIJF_METHODEN = {"POST", "PUT", "DELETE"}


def schrijf(firma, method, path, params=None, body=None):
    """Muterende call. Bewust apart: wordt door de SM-uitvoerder aangeroepen
    nadat een mens het voorstel heeft goedgekeurd. Geeft (resultaat, samenvatting)."""
    method = method.upper()
    if method not in SCHRIJF_METHODEN:
        raise ValueError(f"schrijf() alleen voor {SCHRIJF_METHODEN}, niet {method}")
    uit = _vraag(firma, method, path, params=params, body=body)
    data = uit.get("data")
    kort = f"{method} {path} ok"
    if isinstance(data, dict) and data.get("id"):
        kort += f" (id {data['id']})"
    return data, kort

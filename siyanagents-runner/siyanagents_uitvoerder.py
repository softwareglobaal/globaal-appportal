#!/usr/bin/env python3
"""SM-uitvoerder: voert GOEDGEKEURDE muterende voorstellen uit tegen de externe
diensten (Pipedrive, later Google Ads). Deterministisch, geen AI.

De poort:
  agent stelt een schrijfactie voor (met parameters)  ->  voorstel 'open'
  mens keurt goed op siyanagents.globaal.be           ->  besluit 'goedgekeurd'
  DEZE uitvoerder haalt het op, voert het uit, logt bewijs.

Een voorstel mét parameters kan nooit autonoom zijn (afgedwongen in de app),
dus alles wat hier binnenkomt is door een mens goedgekeurd. We valideren
niettemin streng en voeren alleen bekende diensten/methoden uit.

Draait op de host via cron. Praat met de siyanagents-app over localhost.
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "koppelingen"))
import pipedrive  # noqa: E402
import googleads  # noqa: E402


def laad_env(pad):
    try:
        for line in open(os.path.expanduser(pad)):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    except OSError:
        pass


laad_env("~/appportal/siyanagents-data/.env")   # AGENTS_TOKEN + PLATFORM_URL
PLATFORM = os.environ.get("PLATFORM_URL", "http://127.0.0.1:3021")
TOKEN = os.environ.get("AGENTS_TOKEN", "")

SCHRIJF = {"POST", "PUT", "DELETE"}


def api(path, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(PLATFORM + path, data=data, method=method)
    req.add_header("X-Agents-Token", TOKEN)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def meld(vid, uitvoering, detail, bewijs=""):
    api("/uitvoer-resultaat", "POST",
        {"id": vid, "uitvoering": uitvoering, "detail": detail[:400], "bewijs": bewijs[:4000]})


def voer_uit(p):
    """Voert één muterende actie uit. Geeft (uitvoering, detail, bewijs).
    Pipedrive:   {dienst:'pipedrive', firma, method, path, body?}
    Google Ads:  {dienst:'googleads', customer_id, path (op ':mutate'), body}"""
    dienst = str(p.get("dienst", "")).lower()
    path = str(p.get("path", ""))
    if not path.startswith("/"):
        return "mislukt", f"ongeldig pad '{path}'", ""

    if dienst == "pipedrive":
        method = str(p.get("method", "")).upper()
        if method not in SCHRIJF:
            return "mislukt", f"niet-muterende methode '{method}'", ""
        data, kort = pipedrive.schrijf(p.get("firma", ""), method, path, body=p.get("body"))
        return "gelukt", kort, json.dumps(data)[:4000]

    if dienst == "googleads":
        cid = str(p.get("customer_id", "")).replace("-", "")
        if not cid:
            return "mislukt", "customer_id ontbreekt", ""
        # Google Ads muteert alleen via :mutate-endpoints; dat dwingen we af.
        if not path.endswith(":mutate"):
            return "mislukt", f"Google Ads schrijven mag alleen via een :mutate-pad, niet '{path}'", ""
        data, kort = googleads.schrijf(cid, path, p.get("body"))
        return "gelukt", kort, json.dumps(data)[:4000]

    return "mislukt", f"onbekende dienst '{dienst}'", ""


def main():
    if not TOKEN:
        print("FOUT: geen AGENTS_TOKEN", file=sys.stderr)
        return
    acties = api("/api/uitvoer-wacht").get("wacht") or []
    for a in acties:
        vid = a.get("id")
        rb = a.get("runbook", "")
        ruwe = a.get("parameters") or ""
        try:
            p = json.loads(ruwe) if ruwe else {}
        except (ValueError, TypeError):
            meld(vid, "mislukt", f"parameters niet leesbaar (runbook {rb})")
            continue
        if not p:
            meld(vid, "overgeslagen", f"geen parameters bij runbook '{rb}'")
            continue
        try:
            uitvoering, detail, bewijs = voer_uit(p)
        except Exception as e:  # noqa: BLE001 - deterministische uitvoerder, alles afvangen
            uitvoering, detail, bewijs = "mislukt", f"{type(e).__name__}: {e}", ""
        meld(vid, uitvoering, detail, bewijs)
        print(f"voorstel {vid} ({rb}): {uitvoering} — {detail}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""dealmaker.py — CLI voor de Dealmaker-agent (Sales/Marketing).

Lezen is vrij; schrijven kan NIET rechtstreeks — het wordt een voorstel op het
board dat Siyan goedkeurt, waarna de SM-uitvoerder het uitvoert. De agent (Claude
Code) roept dit aan via ssh en krijgt JSON terug.

  pd-lees <firma> <path> [json-params]     Pipedrive GET (bv. pd-lees unabo /deals '{"status":"open"}')
  ads-accounts                             toegankelijke Google Ads-accounts
  ads-lees <customer_id> "<gaql>"          Google Ads GAQL-query
  voorstel '<json>'                        maak een GATED schrijf-voorstel

voorstel-json:
  {"actie":"korte titel","doel":"deal 123","reden":"waarom",
   "parameters":{"dienst":"pipedrive","firma":"unabo","method":"PUT",
                 "path":"/deals/123","body":{...}}}
  of voor Google Ads:
   {"parameters":{"dienst":"googleads","customer_id":"1907613111",
                  "path":"/campaignBudgets:mutate","body":{...}}}
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "koppelingen"))
import pipedrive  # noqa: E402
import googleads  # noqa: E402


def _laad_env(pad):
    try:
        for line in open(os.path.expanduser(pad)):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    except OSError:
        pass


_laad_env("~/appportal/siyanagents-data/.env")
PLATFORM = os.environ.get("PLATFORM_URL", "http://127.0.0.1:3021")
TOKEN = os.environ.get("AGENTS_TOKEN", "")


def _uit(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def maak_voorstel(spec):
    """Zet een muterende actie als GATED voorstel op het board (besluit 'open')."""
    params = spec.get("parameters")
    if not params or not params.get("dienst"):
        raise SystemExit("voorstel vereist 'parameters' met een 'dienst'")
    dienst = params["dienst"]
    body = {"naam": "de-dealmaker", "status": "actief", "voorstel": {
        "actie": spec.get("actie", "")[:200],
        "runbook": f"{dienst}.schrijf",
        "doel": spec.get("doel", "")[:120],
        "reden": spec.get("reden", "")[:400],
        "parameters": params}}
    req = urllib.request.Request(PLATFORM + "/agent-status",
                                 data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Agents-Token", TOKEN)
    urllib.request.urlopen(req, timeout=20).read()
    return {"ok": True, "melding": "voorstel op het board gezet, wacht op goedkeuring van Siyan",
            "board": "https://siyanagents.globaal.be/validatie", "dienst": dienst}


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    cmd = argv[0]
    if cmd == "pd-lees":
        firma, path = argv[1], argv[2]
        params = json.loads(argv[3]) if len(argv) > 3 else None
        _uit(pipedrive.get(firma, path, params))
    elif cmd == "ads-accounts":
        _uit(googleads.accounts())
    elif cmd == "ads-lees":
        _uit(googleads.zoek(argv[1], argv[2]))
    elif cmd == "voorstel":
        _uit(maak_voorstel(json.loads(argv[1])))
    else:
        raise SystemExit(f"onbekend commando '{cmd}'\n{__doc__}")


if __name__ == "__main__":
    main(sys.argv[1:])

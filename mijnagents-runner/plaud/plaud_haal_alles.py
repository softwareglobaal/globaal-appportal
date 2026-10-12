#!/usr/bin/env python3
"""Haalt het Plaud-archief op met de eigen API van Plaud en houdt het bij (verbeteropdracht v1.0, §2, §6, §9).

Draait op de Mac (launchd be.globaal.plaud.ophalen, elk uur), met een slot zodat er nooit twee rondes
tegelijk lopen en een tijdslimiet per ronde. Per ronde:

  1. toegangsbewijs lezen (~/.config/plaud/token.json) en zo nodig verversen volgens het contract van
     de officiële Plaud-CLI (@plaud-ai/cli 0.3.15: POST form refresh_token naar .../access-token/refresh)
  2. alle pagina's van GET /open/third-party/files/ ophalen; een volledige lijst vervangt de oude
  3. per opname de map controleren met archief.toestand (op Plaud-id):
       compleet              niets doen
       wacht_op_transcript   alleen opnieuw vragen als volgende_controle voorbij is (backoff)
       onvolledig/ontbreekt  detail ophalen en bouwen of herstellen
  4. status wegschrijven naar `<archief>/00 status.json`; de VM leest die mee

Uitkomst en foutcode:
    0 alles gelukt          2 aanmelding ontbreekt of geweigerd
    3 bron niet bereikbaar  4 een of meer opnames mislukt    5 al een ronde bezig

Het toegangsbewijs staat nergens anders dan in ~/.config/plaud/token.json en verschijnt niet in
logs, status of chat.

Gebruik:
    python3 plaud_haal_alles.py              een ronde
    python3 plaud_haal_alles.py --max 25     hoogstens 25 opnames bouwen (proef)
    python3 plaud_haal_alles.py --lijst      alleen de lijst verversen

Python 3.9-compatibel.
"""
import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).parent))
import archief  # noqa: E402
import bouw_map  # noqa: E402
import contract  # noqa: E402
import lijst  # noqa: E402

BASIS = "https://platform.plaud.ai/developer/api"
VERVERS_URL = BASIS + "/oauth/third-party/access-token/refresh"
BEWIJS = Path(os.environ.get("PLAUD_TOKEN", Path.home() / ".config" / "plaud" / "token.json"))
DOEL = Path(os.environ.get("PLAUD_DOEL", Path.home() / "TKN-buro Dropbox" / "Data uit Mehdi" / "Plaud"))
SLOT = Path(os.environ.get("PLAUD_SLOT", Path.home() / "Library" / "Caches" / "plaud-ophalen.lock"))
RONDE_MAX_SEC = int(os.environ.get("PLAUD_RONDE_MAX_SEC", "3000"))
VERZOEK_SEC = 60
PAGINA = 100
AGENT = "plaud-cli/0.3.15"

OK, AUTH, BRON, DEELS, BEZIG = 0, 2, 3, 4, 5


class AuthFout(RuntimeError):
    pass


class BronFout(RuntimeError):
    pass


def _nu():
    return datetime.now(timezone.utc)


# ------------------------------------------------------------- toegang ---
def _lees_bewijs():
    data = archief.lees_json(BEWIJS)
    if not isinstance(data, dict):
        raise AuthFout("geen aanmelding: %s ontbreekt (plaud_login.py)" % BEWIJS)
    return data.get("data") if isinstance(data.get("data"), dict) else data


def _bewaar_bewijs(b):
    archief.schrijf_json(BEWIJS, b)
    os.chmod(BEWIJS, 0o600)


def _curl(args):
    # zonder User-Agent weigert Plaud (Cloudflare 403, code 1010; gemeten 17-09-2026)
    r = subprocess.run(["curl", "-sS", "--proto", "=https", "-A", AGENT, "--max-time", str(VERZOEK_SEC), "-w", "\n%{http_code}"] + args,
                       capture_output=True)
    if r.returncode != 0:
        raise BronFout("netwerk: curl %d" % r.returncode)
    tekst, _, code = r.stdout.decode("utf-8", "replace").rpartition("\n")
    return int(code or 0), tekst


def ververs(b):
    """Volgens @plaud-ai/cli 0.3.15 (OAuthClient.refresh): form-post met alleen refresh_token.
    401/403 betekent geweigerd: het bewijs is niet meer bruikbaar, Mehdi meldt opnieuw aan."""
    if not b.get("refresh_token"):
        raise AuthFout("toegang verlopen en geen verversingstoken; opnieuw aanmelden (plaud_login.py)")
    code, tekst = _curl(["-X", "POST", VERVERS_URL, "-H", "Content-Type: application/x-www-form-urlencoded",
                         "-H", "Accept: application/json", "--data", urlencode({"refresh_token": b["refresh_token"]})])
    if code in (401, 403):
        raise AuthFout("verversing geweigerd (%d); opnieuw aanmelden (plaud_login.py)" % code)
    if code != 200:
        raise BronFout("verversing mislukt: HTTP %d" % code)
    d = json.loads(tekst or "{}")
    nieuw = {"access_token": d["access_token"], "refresh_token": d.get("refresh_token") or b["refresh_token"],
             "token_type": d.get("token_type") or "Bearer"}
    if d.get("expires_in"):
        nieuw["expires_at"] = int(time.time() * 1000 + float(d["expires_in"]) * 1000)
    _bewaar_bewijs(nieuw)
    return nieuw


def toegang():
    b = _lees_bewijs()
    if not b.get("access_token"):
        raise AuthFout("aanmelding zonder access_token; opnieuw aanmelden (plaud_login.py)")
    if b.get("expires_at") and time.time() * 1000 > float(b["expires_at"]) - 60_000:
        b = ververs(b)
    return b


def api(pad, b):
    code, tekst = _curl([BASIS + pad, "-H", "Authorization: Bearer " + b["access_token"], "-H", "Accept: application/json"])
    if code == 401:
        b.update(ververs(b))
        code, tekst = _curl([BASIS + pad, "-H", "Authorization: Bearer " + b["access_token"], "-H", "Accept: application/json"])
        if code == 401:
            raise AuthFout("API weigert de aanmelding (401)")
    if code == 403:
        raise AuthFout("API weigert toegang (403)")
    if code != 200:
        raise BronFout("HTTP %d op %s" % (code, pad.split("?")[0]))
    try:
        return json.loads(tekst or "{}")
    except ValueError:
        raise BronFout("geen JSON op %s" % pad.split("?")[0])


def lijst_alles(b):
    uit, pagina = [], 1
    while pagina < 1000:
        d = api("/open/third-party/files/?" + urlencode({"page": pagina, "page_size": PAGINA}), b)
        rij = d.get("data") if isinstance(d.get("data"), list) else d.get("items") or []
        if not rij:
            return uit
        uit += rij
        pagina += 1
        time.sleep(0.3)
    raise BronFout("meer dan 1000 pagina's; lijst niet volledig gelezen")


# --------------------------------------------------------------- ronde ---
def te_doen(opnames, idx, nu):
    """(lijst te bouwen, tellers). Wachtende transcripten alleen als hun volgende controle voorbij is."""
    t = {"compleet": 0, "wacht_op_transcript": 0, "wacht_nog_niet_aan_de_beurt": 0, "te_bouwen": 0, "herstel": 0}
    doen = []
    for o in opnames:
        try:
            pid = contract.canon_id(o.get("id") or "")
        except contract.Herstel:
            t["herstel"] += 1
            continue
        m = idx.van(pid)
        st = archief.toestand(m, pid) if m else {"staat": "ontbreekt"}
        if st["staat"] == "compleet":
            t["compleet"] += 1
            continue
        if st["staat"] == "wacht_op_transcript":
            t["wacht_op_transcript"] += 1
            vc = ((archief.lees_json(m / "gesprek.json") or {}).get("transcript") or {}).get("volgende_controle")
            if vc and vc > nu.strftime("%Y-%m-%dT%H:%M:%SZ"):
                t["wacht_nog_niet_aan_de_beurt"] += 1
                continue
        t["te_bouwen"] += 1
        doen.append(o)
    return doen, t


def schrijf_status(status):
    archief.schrijf_json(DOEL / "00 status.json", status)


def ronde(args):
    nu = _nu()
    oud = archief.lees_json(DOEL / "00 status.json") or {}
    status = {"versie": 1, "laatste_poging": nu.isoformat(timespec="seconds"), "laatste_ok": oud.get("laatste_ok"),
              "uitkomst": "bezig", "aanmelding": "onbekend", "tellers": {}, "fouten": [], "nieuwste_opname": oud.get("nieuwste_opname")}
    try:
        b = toegang()
        status["aanmelding"] = "ok"
        opnames = lijst_alles(b)
        meta = lijst.schrijf(DOEL, opnames, bron="plaud-api", volledig=True)
        status["nieuwste_opname"] = meta.get("nieuwste_start")
        status["tellers"]["in_plaud"] = len(opnames)
        if args.lijst:
            status.update(uitkomst="ok", laatste_ok=_nu().isoformat(timespec="seconds"))
            schrijf_status(status)
            return OK
        idx = archief.Index(DOEL)
        doen, tellers = te_doen(opnames, idx, nu)
        status["tellers"].update(tellers)
        if args.max:
            doen = doen[:args.max]
        goed = fout = 0
        for o in doen:
            try:
                d = api("/open/third-party/files/" + o["id"], b)
                bron = {s.get("data_type"): s for s in (d.get("source_list") or []) if isinstance(s, dict)}
                invoer = {"id": o["id"], "name": o.get("name"), "start_at": o.get("start_at"), "duration": o.get("duration"),
                          "serial_number": d.get("serial_number") or o.get("serial_number"), "presigned_url": d.get("presigned_url") or "",
                          "bron": "plaud-api"}
                if (bron.get("transaction") or {}).get("data_link"):
                    invoer["transcript_link"] = bron["transaction"]["data_link"]
                res = bouw_map.bouw(invoer, DOEL, idx)
            except (AuthFout, BronFout):
                raise
            except Exception as e:  # noqa: BLE001  een opname mag de andere niet blokkeren
                res = {"plaud_id": o.get("id"), "status": "fout", "fouten": ["%s: %s" % (type(e).__name__, str(e)[:150])]}
            if res["status"] in ("compleet", "wacht_op_transcript") and not res.get("fouten"):
                goed += 1
            else:
                fout += 1
                status["fouten"].append({"plaud_id": res.get("plaud_id"), "status": res["status"], "fouten": res.get("fouten", [])[:3]})
            time.sleep(0.3)
        status["tellers"].update({"gebouwd": goed, "mislukt": fout})
        status["uitkomst"] = "ok" if not fout else "deels"
        if not fout:
            status["laatste_ok"] = _nu().isoformat(timespec="seconds")
        status["fouten"] = status["fouten"][:25]
        schrijf_status(status)
        return OK if not fout else DEELS
    except AuthFout as e:
        status.update(uitkomst="authfout", aanmelding="ontbreekt of geweigerd", fouten=[str(e)])
        schrijf_status(status)
        return AUTH
    except BronFout as e:
        status.update(uitkomst="bronfout", fouten=[str(e)])
        schrijf_status(status)
        return BRON


def _te_lang(signum, frame):
    raise BronFout("ronde duurde langer dan %d s" % RONDE_MAX_SEC)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--max", type=int, default=0)
    p.add_argument("--lijst", action="store_true")
    args = p.parse_args()
    SLOT.parent.mkdir(parents=True, exist_ok=True)
    with open(SLOT, "w") as slot:
        try:
            fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print(json.dumps({"uitkomst": "bezig", "reden": "er loopt al een ronde"}))
            return BEZIG
        signal.signal(signal.SIGALRM, _te_lang)
        signal.alarm(RONDE_MAX_SEC)
        code = ronde(args)
        signal.alarm(0)
        print(json.dumps(archief.lees_json(DOEL / "00 status.json"), ensure_ascii=False))
        return code


if __name__ == "__main__":
    sys.exit(main())

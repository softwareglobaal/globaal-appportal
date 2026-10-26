"""De koppen van het hotmail-postvak op de VM zelf maken, voor De Mailwacht hotmail (mail-prive).

Tot 26-10-2026 maakte de Mac dit bestand (mac/hotmail_koppen.py, uit de index van Mail). Onder launchd heeft die geen
Full Disk Access, en werkwijze/icloud-wacht.md verbiedt die voor de algemene Python: elke run viel sinds 26-09-2026 stil
op 'authorization denied'. De server leest hotmail al zelf met het OAuth-token in de postcontainer (post/oauth_ms.py),
zoals koppelingen/mail_afspraken.py. hotmail_lezer.py leest daar, alleen lezen; dit schrijft het resultaat naar het
bestand uit werkwijze/mailwachten.json ('bronnen'), in de vorm die postvak.uit_bestand en postvak.bron_uren_oud lezen.
Daardoor verandert de wacht zelf niet en schrijft hij niets in hotmail (postvak slaat elk postvak met een bron over).

Lukt het lezen niet volledig, dan blijft het vorige bestand staan: het veroudert en de wacht meldt dat zelf
(postvak.BRON_VERS_UREN). Draait elk uur vanuit mail_prive.py, ook buiten 07-21.
"""
import json
import os
import subprocess
from datetime import datetime, timezone

CONTAINER = os.environ.get("POST_CONTAINER", "appportal-app-post-1")
LEZER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hotmail_lezer.py")
# Het bestand in werkwijze/mailwachten.json ('bronnen'); daar staat ook welk postvak het is, en alleen daar.
BESTAND = "hotmail/koppen.json"
# Zoals de Mac: binnengekomen post 30 dagen; verzonden post twee jaar, want wie Mehdi vanuit hotmail mailde is een klant
# en wordt nooit uitgeschreven (koppelingen/uitschrijven.py, ooit_gemaild; resultaattoets 20-10-2026).
BINNEN_DAGEN, VERZONDEN_DAGEN = 30, 730


def bron():
    """(adres, pad) van het postvak met BESTAND uit werkwijze/mailwachten.json ('bronnen')."""
    import postvak
    for adres, pad in postvak.wachten().get("bronnen", {}).items():
        if pad == BESTAND:
            return adres, os.path.join(postvak.DATA, pad)
    raise LookupError(f"geen postvak met {BESTAND} in werkwijze/mailwachten.json")


def lees(adres, nu, voer=subprocess.run):
    """Wat hotmail_lezer.py in de postcontainer teruggeeft: {'berichten', 'fouten', 'mappen'}."""
    opdracht = json.dumps({"adres": adres, "vandaag": nu.date().isoformat(),
                           "binnen_dagen": BINNEN_DAGEN, "verzonden_dagen": VERZONDEN_DAGEN})
    with open(LEZER, "rb") as f:
        r = voer(["docker", "exec", "-i", "-e", f"LEES={opdracht}", "-w", "/app", CONTAINER, "python", "-"],
                 stdin=f, capture_output=True, timeout=600)
    if r.returncode:
        raise RuntimeError(r.stderr.decode(errors="replace")[-300:] or f"exit {r.returncode}")
    return json.loads(r.stdout.decode())


def bestand(adres, d, nu):
    """Het bestand voor de wacht; een fout als het lezen niet volledig was, dan blijft het vorige staan."""
    if d.get("fouten"):
        raise RuntimeError("; ".join(d["fouten"])[:300])
    berichten = d.get("berichten") or []
    if not any(b.get("map") == "INBOX" for b in berichten) or not any(b.get("map") == "Sent" for b in berichten):
        raise RuntimeError(f"onvolledig: geen binnengekomen of geen verzonden post gelezen ({d.get('mappen')})")
    return {"gemaakt": nu.isoformat(), "adres": adres, "bron": "server", "verzonden_dagen": VERZONDEN_DAGEN,
            "vanaf": d.get("vanaf") or {}, "berichten": berichten}


def ververs(adres, doel, nu=None, voer=subprocess.run):
    """Leest hotmail en zet het bestand (eerst .nieuw, dan in een keer vervangen). Geeft een regel voor het logboek."""
    nu = nu or datetime.now(timezone.utc)
    d = bestand(adres, lees(adres, nu, voer), nu)
    os.makedirs(os.path.dirname(doel), exist_ok=True)
    tmp = f"{doel}.{os.getpid()}.nieuw"  # een ronde met de hand en de cron schrijven elk hun eigen bestand
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, doel)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    tel = {k: sum(1 for b in d["berichten"] if b["map"] == k) for k in ("INBOX", "Sent")}
    return (f"{nu.isoformat(timespec='seconds')} hotmail: {tel['INBOX']} binnen ({BINNEN_DAGEN} d), "
            f"{tel['Sent']} verzonden ({VERZONDEN_DAGEN} d), van de server")


if __name__ == "__main__":
    # Met de hand op de VM: python3 koppelingen/hotmail_server.py           lezen en het bestand zetten
    #                       python3 koppelingen/hotmail_server.py --droog   alleen de mappen en de fouten tonen
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    nu = datetime.now(timezone.utc)
    if "--droog" in sys.argv:
        d = lees(bron()[0], nu)
        print(json.dumps({"fouten": d.get("fouten"), "mappen": d.get("mappen")}, ensure_ascii=False))
    else:
        print(ververs(*bron(), nu))

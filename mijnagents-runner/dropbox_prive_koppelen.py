"""Eenmalig: Mehdi's eigen Dropbox koppelen aan de agents (punt A2).

Draaien op de VM, in een gewone SSH-sessie, met Mehdi erbij (Zoom of naast je):

    python3 ~/appportal/mijnagents-runner/dropbox_prive_koppelen.py

Wat het doet:
1. leest DROPBOX_PRIVE_APP_KEY en DROPBOX_PRIVE_APP_SECRET uit ~/appportal/.env
   (of vraagt ze, zonder echo);
2. toont een link; Mehdi opent die in ZIJN browser, ingelogd op zijn eigen
   Dropbox, klikt Toestaan en leest de code voor (eenmalig, 5 minuten geldig);
3. wisselt de code in voor een refresh-token en schrijft dat in ~/appportal/.env
   (backup ernaast); het token komt nooit op het scherm;
4. controleert met users/get_current_account van wie het account is en zet een
   testbestand in de archiefmap.

Daarna zetten de Fathomwacht, Plaudwacht en Locatiewacht hun archief bij de
volgende ronde zelf in Dropbox (koppelingen/dropbox_prive.py)."""
import getpass
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request

ENV = os.path.expanduser("~/appportal/.env")
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))


def lees_env():
    d = {}
    try:
        for regel in open(ENV, encoding="utf-8"):
            r = regel.strip()
            if r and not r.startswith("#") and "=" in r:
                k, v = r.split("=", 1)
                d[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return d


def zet_env(waarden):
    """Sleutels vervangen of toevoegen in ~/appportal/.env, met backup."""
    tekst = open(ENV, encoding="utf-8", newline="").read() if os.path.exists(ENV) else ""
    shutil.copy(ENV, ENV + ".bak-" + time.strftime("%Y%m%d%H%M"))
    nl = "\r\n" if "\r\n" in tekst else "\n"
    for k, v in waarden.items():
        if re.search(rf"^{k}=.*$", tekst, re.M):
            tekst = re.sub(rf"^{k}=.*$", f"{k}={v}", tekst, flags=re.M)
        else:
            if tekst and not tekst.endswith(("\n", "\r\n")):
                tekst += nl
            tekst += f"{k}={v}{nl}"
    open(ENV, "w", encoding="utf-8", newline="").write(tekst)


def main():
    env = lees_env()
    nieuw = "--nieuw" in sys.argv  # andere Dropbox-app (bv. met volledige toegang): sleutels opnieuw vragen
    basis_arg = ""
    if "--basis" in sys.argv:
        basis_arg = sys.argv[sys.argv.index("--basis") + 1].strip()
    sleutel = ("" if nieuw else env.get("DROPBOX_PRIVE_APP_KEY")) or getpass.getpass("App key van de Dropbox-app (App Console): ").strip()
    geheim = ("" if nieuw else env.get("DROPBOX_PRIVE_APP_SECRET")) or getpass.getpass("App secret: ").strip()
    if not (sleutel and geheim):
        print("Geen app key of secret; stop.")
        return 1
    url = "https://www.dropbox.com/oauth2/authorize?" + urllib.parse.urlencode({
        "client_id": sleutel, "response_type": "code", "token_access_type": "offline"})
    print("\nLaat MEHDI deze link openen, ingelogd op zijn eigen Dropbox, en op Toestaan klikken:\n")
    print("  " + url + "\n")
    code = getpass.getpass("Code die Dropbox toont (wordt niet geëchood): ").strip()
    if not code:
        print("Geen code; stop.")
        return 1
    data = urllib.parse.urlencode({"code": code, "grant_type": "authorization_code",
                                   "client_id": sleutel, "client_secret": geheim}).encode()
    try:
        with urllib.request.urlopen("https://api.dropboxapi.com/oauth2/token", data, timeout=30) as r:
            a = json.load(r)
    except urllib.error.HTTPError as e:
        print("Dropbox weigert de code:", e.code, e.read()[:200].decode(errors="ignore"))
        return 1
    if not a.get("refresh_token"):
        print("Geen refresh-token in het antwoord (staat token_access_type=offline in de link?).")
        return 1
    waarden = {"DROPBOX_PRIVE_APP_KEY": sleutel, "DROPBOX_PRIVE_APP_SECRET": geheim,
               "DROPBOX_PRIVE_REFRESH_TOKEN": a["refresh_token"]}
    if basis_arg:
        waarden["DROPBOX_PRIVE_BASIS"] = basis_arg
    zet_env(waarden)
    print("Token opgeslagen in ~/appportal/.env (backup ernaast).")

    # controle: van wie is het account, en kunnen we schrijven?
    for k in ("DROPBOX_PRIVE_APP_KEY", "DROPBOX_PRIVE_APP_SECRET", "DROPBOX_PRIVE_REFRESH_TOKEN", "DROPBOX_PRIVE_BASIS"):
        os.environ.pop(k, None)
    import dropbox_prive  # noqa: E402
    acc = dropbox_prive.account()
    print(f"Gekoppeld aan: {acc['naam']} <{acc['email']}> ({acc['type']}, root {acc.get('root')})")
    if "mehdi" not in (acc["naam"] + acc["email"]).lower() and "h-architects" not in acc["email"].lower():
        print("LET OP: dit lijkt niet Mehdi's account. Draai opnieuw met Mehdi ingelogd in de browser.")
    proef = f"Gekoppeld op {time.strftime('%Y-%m-%d %H:%M')} UTC door de agents op mijnagents.globaal.be.\n".encode()
    dropbox_prive.upload(proef, "/Fathom/gekoppeld.txt")
    print(f"Testbestand geschreven: {dropbox_prive.basis() or '(app-map)'}/Fathom/gekoppeld.txt")
    print("Klaar. De volgende ronde van de Fathomwacht (07:00 en 13:00 UTC) zet het archief in Dropbox;"
          " meteen: ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/fathom_wacht.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

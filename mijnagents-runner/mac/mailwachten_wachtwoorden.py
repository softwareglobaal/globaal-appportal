#!/usr/bin/env python3
"""Wachtwoorden van postvakken aan de postbus geven, via een venster op de Mac.

Mehdi, 25-09-2026: "het commando werkt zo niet; zorg dat het zelf tevoorschijn komt en ik plak
het wachtwoord daar zelf in." Per postvak verschijnt een venster (verborgen invoer, plakken werkt).
Het wachtwoord gaat via ssh op stdin naar eenmalig/postvak_zetten.py op de VM, dat eerst test of
inloggen lukt en pas dan opslaat in ~/post-config/mailboxen.yaml. Het wachtwoord komt nooit in
een argument, een log, de uitvoer of een chat.

Dubbelklikken: 'Wachtwoorden mailwachten.command' op het bureaublad.
"""
import os
import shlex
import subprocess
from datetime import datetime

VM_SCRIPT = "/home/ubuntu/appportal/mijnagents-runner/eenmalig/postvak_zetten.py"
LOG = os.path.expanduser("~/Library/Logs/mailwachten-wachtwoorden.log")

# adres, imap-server, naam in de postbus, bestand met een wachtwoord dat al op deze Mac staat, waarvoor
POSTVAKKEN = [
    ("melodiebvba@gmail.com", "imap.gmail.com", "Melodie (Gmail)", "~/.melodie_gmail_app_pw",
     "de mail van Melodie volgen"),
    ("wagenparkha@gmail.com", "imap.gmail.com", "Wagenpark (Gmail)", None,
     "de garagefacturen van de bestuurders bij de juiste wagen zetten"),
    ("mehdichegini@hotmail.com", "outlook.office365.com", "Mehdi prive (Outlook)", None,
     "je prive-mail (Outlook) volgen"),
    ("mehdi@h-architects.be", "imap.one.com", "Mehdi H-Architects", None,
     "mehdi@h-architects.be volgen"),
    ("offerte@h-architects.be", "imap.one.com", "H-Architects Offerte", "~/.offerte_one_pw",
     "offerte@ volgen; de server kan er nu niet meer in"),
]


def venster(adres, host, waarvoor, bestand):
    """Toont het venster; geeft het geplakte wachtwoord, '' (leeg gelaten) of None (overslaan)."""
    uitleg = f"Wachtwoord voor {adres}\\n\\nWaarvoor: {waarvoor}.\\n\\n"
    if "gmail" in host:
        uitleg += "Gmail: een app-wachtwoord (Google-account, Beveiliging, Verificatie in 2 stappen, App-wachtwoorden).\\n"
    elif "outlook" in host:
        uitleg += "Outlook: een app-wachtwoord (account.microsoft.com, Beveiliging, App-wachtwoorden).\\n"
    else:
        uitleg += "one.com: het wachtwoord van de mailbox (niet dat van het beheerpaneel).\\n"
    if bestand and os.path.exists(os.path.expanduser(bestand)):
        uitleg += "\\nLeeg laten en Opslaan = het wachtwoord gebruiken dat al op deze Mac staat."
    script = (f'set r to display dialog "{uitleg}" default answer "" with hidden answer '
              f'buttons {{"Overslaan", "Opslaan"}} default button "Opslaan" with title "Mailwachten"\n'
              f'if button returned of r is "Overslaan" then return "::overslaan::"\n'
              f'return text returned of r')
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0 or r.stdout.strip() == "::overslaan::":
        return None
    return r.stdout.rstrip("\n")


def main():
    uit = []
    for adres, host, naam, bestand, waarvoor in POSTVAKKEN:
        pw = venster(adres, host, waarvoor, bestand)
        if pw is None:
            uit.append(f"{adres}: overgeslagen")
            continue
        if not pw and bestand and os.path.exists(os.path.expanduser(bestand)):
            pw = open(os.path.expanduser(bestand), encoding="utf-8").read().strip()
        if not pw:
            uit.append(f"{adres}: overgeslagen (leeg)")
            continue
        opdracht = " ".join(shlex.quote(x) for x in ("/usr/bin/python3", VM_SCRIPT, adres, host, naam))
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "globaal", opdracht],
                           input=pw, capture_output=True, text=True, timeout=120)
        pw = None
        regel = (r.stdout.strip() or r.stderr.strip()[:160] or f"geen antwoord (code {r.returncode})").splitlines()[-1]
        uit.append(f"{adres}: {regel}")
    samen = "\n".join(uit)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')}\n{samen}\n\n")
    print(samen)
    kort = samen.replace('"', "'").replace("\n", "\\n")
    subprocess.run(["osascript", "-e", f'display dialog "{kort}" buttons {{"OK"}} default button "OK" with title "Mailwachten"'],
                   capture_output=True)


if __name__ == "__main__":
    main()

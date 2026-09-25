#!/usr/bin/env python3
"""Een postvak aan de postbus toevoegen of zijn wachtwoord vervangen, alleen als inloggen lukt.

Draait op de VM. Het wachtwoord komt binnen op stdin (van het venster op de Mac,
mac/mailwachten_wachtwoorden.py) en komt nooit in een argument, een log of de uitvoer.

    postvak_zetten.py <adres> <imap_host> "<naam>"   < wachtwoord

1. Inloggen via IMAP (alleen lezen, INBOX readonly). Lukt dat niet: niets schrijven.
2. Kopie van ~/post-config/mailboxen.yaml met datum en uur.
3. Bestaat het adres al: alleen zijn regel 'wachtwoord' vervangen. Anders een nieuw postvak
   onderaan, alleen lezen, zichtbaar voor admin en Mehdi.
4. Het bestand opnieuw inlezen; klopt het niet, dan de kopie terugzetten.
"""
import imaplib
import os
import re
import shutil
import sys
from datetime import datetime

import yaml

PAD = os.path.expanduser("~/post-config/mailboxen.yaml")


def quote(s):
    return "'" + s.replace("'", "''") + "'"


def main():
    adres, host, naam = sys.argv[1].strip().lower(), sys.argv[2].strip(), sys.argv[3].strip()
    pw = sys.stdin.read().strip()
    if "gmail.com" in host:
        pw = pw.replace(" ", "")  # Google toont app-wachtwoorden in blokjes van vier
    if not pw:
        print(f"overgeslagen: geen wachtwoord voor {adres}")
        return 0
    try:
        M = imaplib.IMAP4_SSL(host, 993, timeout=25)
        M.login(adres, pw)
        ok, data = M.select("INBOX", readonly=True)
        n = int(data[0]) if ok == "OK" and data and data[0] else 0
        M.logout()
    except Exception as e:  # noqa: BLE001
        print(f"fout: inloggen op {adres} lukt niet ({type(e).__name__}); er is niets opgeslagen")
        return 1
    kopie = f"{PAD}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(PAD, kopie)
    tekst = open(PAD, encoding="utf-8").read()
    blok = re.search(rf"(?ms)^  - adres: {re.escape(adres)}\s*$.*?(?=^  - adres: |\Z)", tekst)
    if blok:
        oud = blok.group(0)
        if not re.search(r"(?m)^    wachtwoord: .*$", oud):
            print(f"fout: {adres} staat in de postbus maar zonder regel wachtwoord; niets veranderd")
            return 1
        nieuw = re.sub(r"(?m)^    wachtwoord: .*$", lambda m: "    wachtwoord: " + quote(pw), oud, count=1)
        tekst = tekst[:blok.start()] + nieuw + tekst[blok.end():]
        wat = "wachtwoord vervangen"
    else:
        extra = "" if host == "imap.one.com" else f"    imap_host: {host}\n    imap_poort: 993\n"
        tekst = tekst.rstrip("\n") + (f"\n\n  - adres: {adres}\n    naam: {naam}\n{extra}"
                                      f"    wachtwoord: {quote(pw)}\n    groepen: [admin]\n    personen: [mehdi]\n"
                                      f"    # alleen lezen (25-09-2026, voor de mailwachten)\n")
        wat = "nieuw postvak, alleen lezen"
    with open(PAD, "w", encoding="utf-8") as f:
        f.write(tekst)
    try:
        d = yaml.safe_load(open(PAD, encoding="utf-8"))
        rij = next(r for r in d["mailboxen"] if str(r.get("adres", "")).lower() == adres)
        assert str(rij.get("wachtwoord")) == pw
    except Exception as e:  # noqa: BLE001
        shutil.copy2(kopie, PAD)
        print(f"fout: het bestand klopte niet na de wijziging ({type(e).__name__}); de kopie is teruggezet")
        return 1
    os.chmod(PAD, 0o600)
    print(f"ok: {adres} ingelogd ({n} berichten in INBOX); {wat}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

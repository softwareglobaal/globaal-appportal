#!/usr/bin/env python3
"""Een postvak in de postbus laten schrijven (verplaatsen, mappen, concepten) voor wie het mag, nooit verwijderen of verzenden.

Draait op de VM. Nodig voor de mailwachten die volgens mailregels/ sorteren (Mehdi, 26-09-2026: "laat elke door de
toepasselijke agent doen en blijf het handhaven").

    postvak_schrijven.py <adres> <naam>[,<naam>...]

1. Kopie van ~/post-config/mailboxen.yaml met datum en uur.
2. In het blok van dat adres: de regel 'schrijven' zetten of vervangen door de lijst namen (zoals bij mch@: [mehdi]).
3. Het bestand opnieuw inlezen; klopt het niet, dan de kopie terugzetten. Wachtwoorden worden niet gelezen of getoond.
"""
import os
import re
import shutil
import sys
from datetime import datetime

import yaml

PAD = os.path.expanduser("~/post-config/mailboxen.yaml")


def main():
    adres, namen = sys.argv[1].strip().lower(), [n.strip() for n in sys.argv[2].split(",") if n.strip()]
    tekst = open(PAD, encoding="utf-8").read()
    blok = re.search(rf"(?ms)^  - adres: {re.escape(adres)}\s*$.*?(?=^  - adres: |\Z)", tekst)
    if not blok:
        print(f"fout: {adres} staat niet in de postbus; niets veranderd")
        return 1
    kopie = f"{PAD}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(PAD, kopie)
    oud = blok.group(0)
    regel = f"    schrijven: [{', '.join(namen)}]"
    if re.search(r"(?m)^    schrijven: .*$", oud):
        nieuw = re.sub(r"(?m)^    schrijven: .*$", regel, oud, count=1)
    else:
        nieuw = re.sub(r"(?m)^(    wachtwoord: .*)$", lambda m: m.group(1) + "\n" + regel, oud, count=1)
    tekst = tekst[:blok.start()] + nieuw + tekst[blok.end():]
    with open(PAD, "w", encoding="utf-8") as f:
        f.write(tekst)
    try:
        d = yaml.safe_load(open(PAD, encoding="utf-8"))
        rij = next(r for r in d["mailboxen"] if str(r.get("adres", "")).lower() == adres)
        assert rij.get("schrijven") == namen, rij.get("schrijven")
    except Exception as e:  # noqa: BLE001
        shutil.copy2(kopie, PAD)
        print(f"fout: het bestand klopte niet na de wijziging ({type(e).__name__}); de kopie is teruggezet")
        return 1
    os.chmod(PAD, 0o600)
    print(f"ok: {adres} schrijven voor {', '.join(namen)}; kopie {os.path.basename(kopie)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

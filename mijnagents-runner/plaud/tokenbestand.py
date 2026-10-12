"""Het Plaud-toegangsbewijs veilig schrijven (nacontrole Plaud-agent v1.1, 12-10-2026, P2-11).

De algemene schrijver maakte eerst een .tmp met de umask-rechten (0644) en zette pas na het vervangen
0600. Hier: de map wordt 0700, het tijdelijke bestand wordt aangemaakt met 0600 en voor het schrijven nog
eens op 0600 gezet (fchmod), dan fsync en atomair vervangen. Op geen enkel moment is het bewijs
leesbaar voor anderen. De waarde komt nooit in een log of uitvoer.

Python 3.9-compatibel.
"""
import json
import os
from pathlib import Path


def schrijf(pad, gegevens):
    pad = Path(pad)
    pad.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(pad.parent, 0o700)
    tmp = str(pad) + ".tmp"
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = None
            json.dump(gegevens, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
    finally:
        if fd is not None:
            os.close(fd)
    os.replace(tmp, pad)
    os.chmod(pad, 0o600)

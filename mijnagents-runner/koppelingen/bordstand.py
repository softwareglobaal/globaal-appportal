#!/usr/bin/env python3
"""Wat het bord nu van een agent weet: de status en tijd van zijn laatste hartslag en de tijd van zijn laatste
kennismelding (N4, N11). Alleen lezen (sqlite, mode=ro).

Voor runners buiten de VM, zoals De Tekenaar op de Mac: de gedeelde ronde slikt een mislukte kennis- of
hartslagmelding (ze schrijft alleen een regel naar stderr), en de publieke ingang van het bord laat deze gegevens
niet lezen. Na zijn ronde vraagt de runner het hier over ssh na; pas als beide van deze ronde zijn, telt ze als gedaan
(Codex DT09, 19-10-2026).

    bordstand.py <naam>           JSON op stdout: status en kennisdatum
    bordstand.py <naam> --ronde   ook twee geëxtraheerde ronde-ID's, nooit detail of kennistekst
"""
import json
import os
import re
import sqlite3
import sys

DB = os.environ.get("AGENTS_DB", os.path.expanduser("~/appportal/mijnagents-data/mijnagents.db"))
NAAM = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STATUS_RONDE = re.compile(r"(?:^|; )ronde-id:([0-9a-f]{32})$")
KENNIS_RONDE = re.compile(r"^ronde-id-([0-9a-f]{32}): 0 tekens, e3b0c442$", re.M)


def _enige_ronde(tekst, patroon):
    treffers = patroon.findall(tekst or "")
    return treffers[0] if len(treffers) == 1 else None


def stand(naam, db=None, met_ronde=False):
    if not NAAM.match(naam or ""):
        raise ValueError("geen agentnaam")
    con = sqlite3.connect(f"file:{db or DB}?mode=ro", uri=True)
    try:
        st = con.execute("select status, ts" + (", detail" if met_ronde else "") + " from status where naam=?",
                         (naam,)).fetchone()
        ke = con.execute("select kennis_ts" + (", kennis" if met_ronde else "") + " from agent where naam=?",
                         (naam,)).fetchone()
    finally:
        con.close()
    uit = {"status": st[0] if st else None, "ts": st[1] if st else None,
           "kennis_ts": (ke[0] or None) if ke else None}
    if met_ronde:
        uit["status_ronde"] = _enige_ronde(st[2], STATUS_RONDE) if st else None
        uit["kennis_ronde"] = _enige_ronde(ke[1], KENNIS_RONDE) if ke else None
    return uit


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != "--ronde"):
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    print(json.dumps(stand(sys.argv[1], met_ronde=len(sys.argv) == 3)))

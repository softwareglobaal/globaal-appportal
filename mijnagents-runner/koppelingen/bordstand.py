#!/usr/bin/env python3
"""Wat het bord nu van een agent weet: de status en tijd van zijn laatste hartslag en de tijd van zijn laatste
kennismelding (N4, N11). Alleen lezen (sqlite, mode=ro).

Voor runners buiten de VM, zoals De Tekenaar op de Mac: de gedeelde ronde slikt een mislukte kennis- of
hartslagmelding (ze schrijft alleen een regel naar stderr), en de publieke ingang van het bord laat deze gegevens
niet lezen. Na zijn ronde vraagt de runner het hier over ssh na; pas als beide van deze ronde zijn, telt ze als gedaan
(Codex DT09, 19-10-2026).

    bordstand.py <naam>     JSON op stdout: {"status": ..., "ts": ..., "kennis_ts": ...}
"""
import json
import os
import re
import sqlite3
import sys

DB = os.environ.get("AGENTS_DB", os.path.expanduser("~/appportal/mijnagents-data/mijnagents.db"))
NAAM = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def stand(naam, db=None):
    if not NAAM.match(naam or ""):
        raise ValueError("geen agentnaam")
    con = sqlite3.connect(f"file:{db or DB}?mode=ro", uri=True)
    try:
        st = con.execute("select status, ts from status where naam=?", (naam,)).fetchone()
        ke = con.execute("select kennis_ts from agent where naam=?", (naam,)).fetchone()
    finally:
        con.close()
    return {"status": st[0] if st else None, "ts": st[1] if st else None, "kennis_ts": (ke[0] or None) if ke else None}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    print(json.dumps(stand(sys.argv[1])))

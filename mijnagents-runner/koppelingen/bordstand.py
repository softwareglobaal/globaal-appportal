#!/usr/bin/env python3
"""Wat het bord nu van een agent weet: de status en tijd van zijn laatste hartslag en de tijd van zijn laatste
kennismelding (N4, N11). Alleen lezen (sqlite, mode=ro).

Voor runners buiten de VM, zoals De Tekenaar op de Mac: de gedeelde ronde slikt een mislukte kennis- of
hartslagmelding (ze schrijft alleen een regel naar stderr), en de publieke ingang van het bord laat deze gegevens
niet lezen. Na zijn ronde vraagt de runner het hier over ssh na; pas als beide van deze ronde zijn, telt ze als gedaan
(Codex DT09, 19-10-2026).

    bordstand.py <naam>           JSON op stdout: status en kennisdatum
    bordstand.py <naam> --ronde   ook twee geëxtraheerde ronde-ID's en de open noodteksten, nooit detail of kennis
    bordstand.py --gesprekken <kanaal> <van> <tot>
                                  per rij van dat kanaal in de gesprekkentabel (datum van..tot) een vingerafdruk en
                                  dubbel_van, nooit de andere velden: zo leest De WhatsApp-wacht of De Belwacht op de
                                  Mac terug wat ze schreef, zonder dat namen over ssh terugkomen (ontwerp
                                  dagvaststelling v2.0, fase 2)
"""
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import date

DB = os.environ.get("AGENTS_DB", os.path.expanduser("~/appportal/mijnagents-data/mijnagents.db"))
NAAM = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STATUS_RONDE = re.compile(r"(?:^|; )ronde-id:([0-9a-f]{32})$")
KENNIS_RONDE = re.compile(r"^ronde-id-([0-9a-f]{32}): 0 tekens, e3b0c442$", re.M)


# De rijen van een kanaal in de gesprekkentabel, op hun voorvoegsel (contract met dagbundelaar.kanaal_van_dag).
KANALEN = {"whatsapp": ("whatsapp:", "whatsapp-oproep:", "dekking:whatsapp:"),
           "telefoon": ("telefoon:", "dekking:telefoon:"),
           "sms": ("sms:", "dekking:sms:"),
           "xelion": ("xelion:", "dekking:xelion:")}
VELDEN = ("datum", "start", "minuten", "personen", "thema", "prive", "bron", "dubbel_van")


def vingerafdruk(rij):
    """De velden van een rij zoals /api/gesprekken ze opslaat (minuten en prive als getal, de rest als tekst), als
    korte hash. De Mac rekent dezelfde hash over wat hij stuurde."""
    def waarde(v):
        x = rij.get(v)
        if v == "minuten":
            return str(int(x or 0))
        if v == "prive":
            return "1" if x else "0"
        return "" if x is None else str(x)
    return hashlib.sha256("\x1f".join(waarde(v) for v in VELDEN).encode()).hexdigest()[:16]


def gesprekken(kanaal, van, tot, db=None):
    """{uniek: {"v": vingerafdruk, "d": dubbel_van}} voor de rijen van een kanaal met datum van tot en met tot. dubbel_van
    draagt geen namen (leeg, buiten:gemist, buiten:dekking, buiten:vervallen)."""
    if kanaal not in KANALEN:
        raise ValueError("geen kanaal")
    van, tot = date.fromisoformat(van).isoformat(), date.fromisoformat(tot).isoformat()
    voorvoegsels = KANALEN[kanaal]
    waar = " OR ".join("substr(uniek, 1, ?) = ?" for _ in voorvoegsels)
    args = [x for v in voorvoegsels for x in (len(v), v)]
    con = sqlite3.connect(f"file:{db or DB}?mode=ro", uri=True)
    try:
        rijen = con.execute("SELECT uniek, datum, start, minuten, personen, thema, prive, bron, "
                            "COALESCE(dubbel_van, '') FROM gesprek_log WHERE datum BETWEEN ? AND ? AND (" + waar + ")",
                            (van, tot, *args)).fetchall()
    finally:
        con.close()
    return {r[0]: {"v": vingerafdruk(dict(zip(VELDEN, r[1:]))), "d": r[-1]} for r in rijen}


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
        # de open noden van de agent (vaste teksten, N10), zodat een Mac-runner zijn eigen fout kan bevestigen (R3)
        try:
            noden = sorted(r[0] for r in con.execute("select tekst from nood where naam=? and open=1", (naam,)))
        except sqlite3.OperationalError:
            noden = None
    finally:
        con.close()
    uit = {"status": st[0] if st else None, "ts": st[1] if st else None,
           "kennis_ts": (ke[0] or None) if ke else None}
    if met_ronde:
        uit["status_ronde"] = _enige_ronde(st[2], STATUS_RONDE) if st else None
        uit["kennis_ronde"] = _enige_ronde(ke[1], KENNIS_RONDE) if ke else None
        uit["noden"] = noden
    return uit


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--gesprekken":
        print(json.dumps(gesprekken(*sys.argv[2:5]), sort_keys=True))
        sys.exit(0)
    if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != "--ronde"):
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    print(json.dumps(stand(sys.argv[1], met_ronde=len(sys.argv) == 3)))

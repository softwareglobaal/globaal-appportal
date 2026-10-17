#!/usr/bin/env python3
"""Herhaalbare, volledig synthetische schaalmeting; geen CI of echte index.

Gebruik: python mijnagents-runner/tests/meet_naamstructuur_schaal.py
De tijdelijke SQLite wordt na de meting verwijderd. --aantal dient voor een snelle proef.
"""
import argparse
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNNER / "koppelingen"))
import naamstructuur as N


def meet(naam, functie):
    begin = time.perf_counter()
    waarde = functie()
    return {"naam": naam, "seconden": round(time.perf_counter() - begin, 3), "waarde": waarde}


def bouw(pad, regels, aantal):
    """Maak ruwe tabellen en daarna de eerste-ronde-indexen, zonder echte metadata."""
    c = sqlite3.connect(pad)
    c.executescript("""
    PRAGMA journal_mode=WAL;
    PRAGMA synchronous=OFF;
    CREATE TABLE item(scope TEXT, identiteit TEXT, pad TEXT, pad_sleutel TEXT,
      naam TEXT, soort TEXT, firma TEXT, profiel TEXT, gegevens TEXT DEFAULT '{}',
      actief INTEGER DEFAULT 1, naam_vuil INTEGER DEFAULT 1,
      structuur_vuil INTEGER DEFAULT 1, ha_gezien TEXT DEFAULT '');
    CREATE TABLE bevinding(agent TEXT, scope TEXT, identiteit TEXT, regel TEXT,
      bron TEXT, firma TEXT, naam TEXT, pad TEXT, voorstel TEXT,
      status TEXT DEFAULT 'open', eerste TEXT, laatste TEXT);
    """)
    werk = regels["roots"][0]
    profielen = regels["profielen"]
    ha_aantal = round(aantal * 335000 / 1750000)
    def rijen():
        for i in range(aantal):
            if i < ha_aantal:
                profiel = profielen[i % 3]
                prefix = profiel["prefix"]
                pad_item = f"{prefix}/synthetisch/{i:07d}.txt"
                yield (werk["id"], f"id:{i:07d}", pad_item, pad_item.casefold(),
                       f"{i:07d}.txt", "file", profiel["firma"], profiel["profiel"])
            else:
                pad_item = f"/Work All/andere mappen/{i:07d}.txt"
                yield (werk["id"], f"id:{i:07d}", pad_item, pad_item.casefold(),
                       f"{i:07d}.txt", "file", "onbekend", "algemeen")
    bron = rijen()
    for _ in range(0, aantal, 10000):
        batch = [next(bron) for _ in range(min(10000, aantal - _))]
        c.executemany("INSERT INTO item(scope,identiteit,pad,pad_sleutel,naam,soort,firma,profiel) "
                      "VALUES(?,?,?,?,?,?,?,?)", batch)
        c.executemany("INSERT INTO bevinding(agent,scope,identiteit,regel,status) VALUES(?,?,?,'synthetisch','open')",
                      [("benamingen-wacht" if int(x[1][3:]) % 2 == 0 else "mappen-wacht", x[0], x[1])
                       for x in batch])
        c.commit()
    # Schema van de eerste ronde, inclusief de bestaande padindex. De nieuwe
    # overzichtindex wordt pas door open_db gemaakt.
    c.executescript("""
    CREATE UNIQUE INDEX item_identiteit ON item(scope,identiteit);
    CREATE INDEX item_pad ON item(scope,pad);
    CREATE INDEX item_pad_sleutel ON item(scope,pad_sleutel);
    CREATE INDEX item_naam_vuil ON item(naam_vuil,actief);
    CREATE INDEX item_structuur_vuil ON item(structuur_vuil,actief);
    CREATE INDEX item_ha_naam_vuil ON item(naam_vuil,actief) WHERE profiel GLOB 'ha_*';
    CREATE INDEX item_ha_structuur_vuil ON item(structuur_vuil,actief) WHERE profiel GLOB 'ha_*';
    CREATE INDEX bevinding_agent ON bevinding(agent,scope,identiteit,regel);
    """)
    c.close()


def open_db_voor_index(pad):
    """Open de bestaande eerste-ronde-index zonder de nieuwe indexaanmaak."""
    c = sqlite3.connect(pad)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA table_info(item)").fetchall()
    c.execute("CREATE INDEX IF NOT EXISTS item_pad_sleutel ON item(scope,pad_sleutel)")
    c.commit()
    return c


def plannen(c, traces, regels):
    plan = {}
    ha = next((q for q in traces if q.startswith("SELECT i.* FROM item i") and "i.profiel GLOB 'ha_*' ORDER BY" in q), None)
    if ha:
        plan["ha_toets"] = [r[3] for r in c.execute("EXPLAIN QUERY PLAN " + ha)]
    p = regels["profielen"][0]["prefix"].casefold()
    vragen = {
        "ha_telling": ("SELECT count(*) FROM item WHERE scope=? AND actief=1 AND "
                       "(pad_sleutel=? OR (pad_sleutel>=? AND pad_sleutel<?))",
                       (regels["roots"][0]["id"], p, p + "/", p + "0")),
        "work_all_telling": ("SELECT count(*) FROM item WHERE scope=? AND actief=1 AND "
                             "profiel NOT GLOB 'ha_*' AND naam_vuil=1", (regels["roots"][0]["id"],)),
    }
    for naam, (sql, args) in vragen.items():
        plan[naam] = [r[3] for r in c.execute("EXPLAIN QUERY PLAN " + sql, args)]
    return plan


def ronde(c, regels, label):
    traces = []
    c.set_trace_callback(lambda q: traces.append(q) if q.startswith("SELECT i.* FROM item i") else None)
    uit = []
    for agent in ("benamingen-wacht", "mappen-wacht"):
        uit.append(meet(label + ": toets_index " + agent, lambda a=agent: N.toets_index(c, a, regels)))
    c.set_trace_callback(None)
    uit.append(meet(label + ": overzicht", lambda: sum(
        s["items"] for s in N.overzicht(c, regels, "mappen-wacht")["scopes"])))
    plan = plannen(c, traces, regels)
    with c:
        c.execute("UPDATE item SET naam_vuil=1,structuur_vuil=1 WHERE naam_vuil=0 OR structuur_vuil=0")
        c.execute("UPDATE bevinding SET status='open' WHERE status<>'open'")
    return uit, plan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aantal", type=int, default=1_750_000)
    args = parser.parse_args()
    regels = N.lees_regels()
    with tempfile.TemporaryDirectory(prefix="h1-schaal-") as tijdelijk:
        pad = str(Path(tijdelijk) / "synthetisch.sqlite3")
        bouwtijd = meet("synthetische SQLite bouwen", lambda: bouw(pad, regels, args.aantal))
        open_voor = meet("open_db voor nieuwe index", lambda: open_db_voor_index(pad))
        c = open_voor.pop("waarde")
        with c:
            c.execute("CREATE TABLE scope(id TEXT PRIMARY KEY,pad TEXT,namespace TEXT,cursor TEXT DEFAULT '',"
                      "compleet INTEGER DEFAULT 0,meer INTEGER DEFAULT 1,poging TEXT DEFAULT '',"
                      "gelukt TEXT DEFAULT '',fout TEXT DEFAULT '',controle TEXT DEFAULT '',verbinding TEXT DEFAULT '')")
            c.execute("CREATE TABLE instelling(sleutel TEXT PRIMARY KEY,waarde TEXT)")
            c.execute("CREATE TABLE lokaal_cursor(bron TEXT PRIMARY KEY,ts TEXT DEFAULT '',rij INTEGER DEFAULT 0)")
            for root in regels["roots"]:
                c.execute("INSERT INTO scope(id,pad,namespace,verbinding,compleet,meer) VALUES(?,?,?,?,1,0)",
                          (root["id"], root["pad"], root["namespace"], root["verbinding"]))
            for bereik, _ in N.ha_bereiken(regels):
                c.execute("INSERT INTO scope(id,pad,namespace,verbinding,compleet,meer) VALUES(?,?,?,?,1,0)",
                          (bereik["id"], bereik["pad"], bereik["namespace"], bereik["verbinding"]))
            N.instelling(c, "regelbron", {"geldig": True})
            N.instelling(c, "pad_sleutel_versie", 1)
        c.execute("ANALYZE")
        c.commit()
        voor, plan_voor = ronde(c, regels, "voor")
        c.close()
        open_eenmalig = meet("open_db met nieuwe index", lambda: N.open_db(pad))
        c = open_eenmalig.pop("waarde")
        na, plan_na = ronde(c, regels, "na")
        c.close()
        warm = meet("open_db volgende ronde", lambda: N.open_db(pad))
        warm.pop("waarde").close()
        print(json.dumps({"aantal": args.aantal, "ha_items": round(args.aantal * 335000 / 1750000),
                          "bouw": bouwtijd, "open_db_voor": open_voor,
                          "voor": voor, "plan_voor": plan_voor,
                          "open_db_eenmalig": open_eenmalig, "na": na, "plan_na": plan_na,
                          "open_db_volgende_ronde": warm}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

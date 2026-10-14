"""Migratie 001: werfopdrachten; bestaande bezoekrijen blijven behouden."""
from datetime import datetime, timezone


def toepassen(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS werf_schema_migratie (nummer INTEGER PRIMARY KEY, naam TEXT NOT NULL, ts TEXT NOT NULL)")
    eigen = not conn.in_transaction
    if eigen:
        conn.execute("BEGIN IMMEDIATE")
    try:
        if not conn.execute("SELECT 1 FROM werf_schema_migratie WHERE nummer=1").fetchone():
            kolommen = {r[1] for r in conn.execute("PRAGMA table_info(werfbezoek)")}
            if "keuzes_revisie" not in kolommen:
                conn.execute("ALTER TABLE werfbezoek ADD COLUMN keuzes_revisie INTEGER NOT NULL DEFAULT 0")
            if "registratie" not in kolommen:
                conn.execute("ALTER TABLE werfbezoek ADD COLUMN registratie TEXT NOT NULL DEFAULT '{}'")
            conn.execute("""CREATE TABLE werfopdracht (
                klaarzet_id INTEGER PRIMARY KEY REFERENCES klaarzet(id),
                werfbezoek_id INTEGER NOT NULL REFERENCES werfbezoek(id),
                soort TEXT NOT NULL CHECK(soort IN ('voorbereid','proef')),
                invoer_hash TEXT NOT NULL, invoer TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'klaar',
                lease_hash TEXT NOT NULL DEFAULT '', lease_tot TEXT NOT NULL DEFAULT '',
                hervat_utc TEXT NOT NULL DEFAULT '',
                door TEXT NOT NULL DEFAULT '', gestart TEXT NOT NULL DEFAULT '',
                voltooid TEXT NOT NULL DEFAULT '', bewijs TEXT NOT NULL DEFAULT '',
                resultaat_bewaard TEXT NOT NULL DEFAULT '',
                veilig_opnieuw INTEGER NOT NULL DEFAULT 0,
                verwerking TEXT NOT NULL DEFAULT '{}', poging INTEGER NOT NULL DEFAULT 1,
                UNIQUE(werfbezoek_id, soort, invoer_hash))""")
            conn.execute("CREATE UNIQUE INDEX werfopdracht_een_actief ON werfopdracht(werfbezoek_id) WHERE status='actief'")
            conn.execute("""CREATE TABLE werfopdracht_gebeurtenis (
                id INTEGER PRIMARY KEY, klaarzet_id INTEGER NOT NULL REFERENCES werfopdracht(klaarzet_id),
                status TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '{}', ts TEXT NOT NULL)""")
            conn.execute("INSERT INTO werf_schema_migratie VALUES(1,?,?)", (
                "idempotente werfopdrachten en exclusieve claims", datetime.now(timezone.utc).isoformat()))
        if eigen:
            conn.commit()
    except Exception:
        if eigen:
            conn.rollback()
        raise

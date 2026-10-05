"""Het schema van locatie.db: elke upgrade één keer, in één transactie, met een kopie vooraf.

Tot 04-10-2026 voerde elke databaseverbinding zelf ALTER TABLE uit, en de
omzetting naar twee bronnen liep via executescript, dat tussendoor vastlegt. Drie
processen gebruiken dezelfde database (twee webworkers en de ontvanger van de
tracker): een upgrade die halverwege breekt of twee keer tegelijk start, kan dan
een half omgebouwde tabel achterlaten.

Nu draagt de database zijn versie in `PRAGMA user_version`. Een upgrade:
  1. maakt eerst een kopie met datum in `backups/` naast de database (sqlite3-backup,
     de enige manier die een lopende schrijfactie correct meeneemt);
  2. neemt het schrijfslot (BEGIN IMMEDIATE), leest de versie opnieuw (een ander
     proces kan hem net gedaan hebben) en voert de ontbrekende stappen uit;
  3. legt alles in één keer vast, of draait alles terug.

Een upgrade leest nooit oude bewegingsdata opnieuw in. Hij bouwt alleen de tabel om
die er staat, en de reeks van de tracker sinds 3 oktober blijft rij voor rij gelijk
(de test in test_schema.py houdt dat vast).
"""
import hashlib
import json
import os
import sqlite3
import time

import atrack

LAATSTE = 3

# Velden die er tussen 9-9 en 3-10-2026 bij kwamen (zie de geschiedenis in app.py).
LATERE_KOLOMMEN = {
    "bs": "INTEGER", "ssid": "TEXT", "bssid": "TEXT", "motion": "TEXT", "druk": "REAL",
    "vac": "INTEGER", "trigger": "TEXT", "regios": "TEXT", "gebeurtenis": "TEXT", "zone": "TEXT",
    "ontvangen": "INTEGER", "gemaakt": "INTEGER",
    "hdop": "INTEGER", "satellieten": "INTEGER", "fix": "INTEGER", "verzonden": "INTEGER",
    "gebufferd": "INTEGER",
}

# Schema 2: wat er per punt bijkomt.
NIEUWE_PUNTKOLOMMEN = {
    "toestel": "TEXT",                         # IMEI van de tracker, tid van de telefoon
    "berichtsoort": "TEXT NOT NULL DEFAULT ''",  # FRI, VGF, STT ... of location/transition
    "volgnr": "INTEGER NOT NULL DEFAULT 0",    # welke positie in een bericht met meerdere
    "bericht_id": "INTEGER",                   # het ruwe bericht in de tabel bericht
    "teller": "TEXT",                          # het volgnummer van het toestel
}


def kolommen(conn, tabel):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({tabel})")]


def soort_van(conn, naam):
    r = conn.execute("SELECT type FROM sqlite_master WHERE name = ?", (naam,)).fetchone()
    return r[0] if r else None


def vingerafdruk_bericht(ruw):
    """Dezelfde meting komt soms twee keer: opnieuw verstuurd omdat de bevestiging
    uitbleef, of uit de buffer met +BUFF in plaats van +RESP. Wat na de dubbele punt
    staat is dan gelijk, en zo wordt een bericht één keer bewaard."""
    ruw = (ruw or "").strip()
    kern = ruw.split(":", 1)[1] if ruw.startswith("+") and ":" in ruw else ruw
    return hashlib.sha256(kern.encode("utf-8", "replace")).hexdigest()


# ------------------------------------------------------------ schema 1

def _v1(conn):
    """De vorm van 03-10-2026, voor een database die nog geen versie draagt.

    Idempotent: op de echte database (die al zo is) verandert dit niets.
    """
    conn.execute("""CREATE TABLE IF NOT EXISTS punt (
        tst INTEGER PRIMARY KEY, lat REAL NOT NULL, lon REAL NOT NULL, acc INTEGER, alt INTEGER,
        vel INTEGER, batt INTEGER, conn TEXT, tid TEXT, soort TEXT, ruw TEXT)""")
    bestaand = set(kolommen(conn, "punt"))
    for kolom, soort in LATERE_KOLOMMEN.items():
        if kolom not in bestaand:
            conn.execute(f"ALTER TABLE punt ADD COLUMN {kolom} {soort}")
    if "bron" not in kolommen(conn, "punt"):
        info = list(conn.execute("PRAGMA table_info(punt)"))
        defs = ['"%s" %s%s' % (r[1], r[2] or "TEXT", " NOT NULL" if r[3] and r[1] != "tst" else "") for r in info]
        namen = ", ".join('"%s"' % r[1] for r in info)
        conn.execute("ALTER TABLE punt RENAME TO punt_schema0")
        conn.execute("CREATE TABLE punt (%s, bron TEXT NOT NULL DEFAULT 'iphone', PRIMARY KEY (bron, tst))"
                     % ", ".join(defs))
        conn.execute("INSERT INTO punt (%s, bron) SELECT %s, 'iphone' FROM punt_schema0" % (namen, namen))
        conn.execute("DROP TABLE punt_schema0")
    conn.execute("CREATE INDEX IF NOT EXISTS punt_tst ON punt(tst)")
    conn.execute("CREATE INDEX IF NOT EXISTS punt_bron ON punt(bron, tst)")
    if soort_van(conn, "toestelbericht") is None:
        conn.execute("""CREATE TABLE toestelbericht (
            ontvangen INTEGER NOT NULL, bron TEXT NOT NULL, soort TEXT, kop TEXT, verzonden INTEGER,
            ruw TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS plek (
        naam TEXT PRIMARY KEY, lat REAL, lon REAL, straal INTEGER DEFAULT 120, wifi TEXT, soort TEXT,
        notitie TEXT)""")
    if "dossier" not in kolommen(conn, "plek"):
        conn.execute("ALTER TABLE plek ADD COLUMN dossier TEXT")
    conn.execute("""CREATE TABLE IF NOT EXISTS gezondheid (
        datum TEXT NOT NULL, soort TEXT NOT NULL, waarde REAL NOT NULL, eenheid TEXT, bron TEXT,
        gezet INTEGER NOT NULL, PRIMARY KEY (datum, soort, bron))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gebeurtenis (
        tst INTEGER NOT NULL, soort TEXT NOT NULL, detail TEXT, bron TEXT, PRIMARY KEY (tst, soort))""")
    conn.execute("CREATE TABLE IF NOT EXISTS instelling (sleutel TEXT PRIMARY KEY, waarde TEXT)")


# ------------------------------------------------------------ schema 2

def _v2(conn):
    """Herleidbare berichten, een sleutel die gelijktijdige gebeurtenissen niet laat
    samenvallen, en de tabellen voor projectherkenning, correcties en taakstatus.

    De sleutel (bron, tst) liet op 03-10-2026 22 van de 27 berichten "motor aan" en
    de helft van de VGL-paren stil wegvallen: zonder fix dragen ze de meettijd van
    het bericht ervoor, en ON CONFLICT DO NOTHING gooide ze weg terwijl de ontvanger
    "bewaard" meldde. De nieuwe sleutel is (bron, tst, berichtsoort, volgnr); het
    ruwe bericht staat apart in `bericht`, één keer, met hoe vaak het binnenkwam.
    """
    conn.execute("""CREATE TABLE IF NOT EXISTS bericht (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        ontvangen        INTEGER NOT NULL,      -- eerste keer binnen (epoch)
        laatst_ontvangen INTEGER NOT NULL,
        aantal           INTEGER NOT NULL DEFAULT 1,  -- hoe vaak binnengekomen (herhaling, buffer)
        bron             TEXT,                  -- naam uit ATRACK_IMEIS of 'iphone'
        toestel          TEXT,                  -- IMEI of tid
        protocol         TEXT NOT NULL,         -- atrack | owntracks
        kop              TEXT,                  -- RESP, BUFF, ACK
        soort            TEXT,                  -- FRI, VGF, HBD ... of location
        protocolversie   TEXT,
        teller           TEXT,
        verzonden        INTEGER,
        posities_gemeld  INTEGER,
        posities_bewaard INTEGER,
        verwerking       TEXT,                  -- punten | geen positie | onvolledig: ...
        herkomst         TEXT NOT NULL DEFAULT 'ontvanger',
        vingerafdruk     TEXT NOT NULL UNIQUE,
        ruw              TEXT NOT NULL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS bericht_bron ON bericht(bron, ontvangen)")

    # punt ombouwen naar de nieuwe sleutel; alle bestaande kolommen gaan mee.
    info = list(conn.execute("PRAGMA table_info(punt)"))
    if "berichtsoort" not in [r[1] for r in info]:
        defs = ['"%s" %s%s' % (r[1], r[2] or "TEXT", " NOT NULL" if r[3] else "") for r in info
                if r[1] != "bron"]
        defs = [d.replace('"tst" INTEGER', '"tst" INTEGER NOT NULL', 1) if d.startswith('"tst"') and "NOT NULL" not in d
                else d for d in defs]
        defs.append("bron TEXT NOT NULL DEFAULT 'iphone'")
        defs += ['"%s" %s' % (k, t) for k, t in NIEUWE_PUNTKOLOMMEN.items()]
        namen = ", ".join('"%s"' % r[1] for r in info)
        conn.execute("ALTER TABLE punt RENAME TO punt_schema1")
        conn.execute("DROP INDEX IF EXISTS punt_tst")
        conn.execute("DROP INDEX IF EXISTS punt_bron")
        conn.execute("CREATE TABLE punt (%s, PRIMARY KEY (bron, tst, berichtsoort, volgnr))" % ", ".join(defs))
        conn.execute("INSERT INTO punt (%s, berichtsoort, volgnr) SELECT %s, COALESCE(soort, ''), 0 FROM punt_schema1"
                     % (namen, namen))
        conn.execute("DROP TABLE punt_schema1")
        conn.execute("CREATE INDEX IF NOT EXISTS punt_tst ON punt(tst)")
        conn.execute("CREATE INDEX IF NOT EXISTS punt_bron ON punt(bron, tst)")
        _vul_berichten(conn)

    # toestelbericht wordt een venster op bericht, zodat er één bron van ruwe berichten is.
    if soort_van(conn, "toestelbericht") == "table":
        for r in conn.execute("SELECT ontvangen, bron, soort, kop, verzonden, ruw FROM toestelbericht").fetchall():
            b = atrack.ontleed(r[5]) or {}
            conn.execute("""INSERT OR IGNORE INTO bericht (ontvangen, laatst_ontvangen, bron, toestel, protocol, kop,
                                soort, protocolversie, teller, verzonden, posities_gemeld, posities_bewaard,
                                verwerking, herkomst, vingerafdruk, ruw)
                            VALUES (?, ?, ?, ?, 'atrack', ?, ?, ?, ?, ?, 0, 0, 'geen positie',
                                    'toestelbericht (schema 1)', ?, ?)""",
                         (r[0], r[0], r[1], b.get("imei"), r[3], r[2], b.get("protocol"), b.get("teller"), r[4],
                          vingerafdruk_bericht(r[5]), r[5]))
        aantal = conn.execute("SELECT count(*) FROM toestelbericht").fetchone()[0]
        if aantal:
            conn.execute("ALTER TABLE toestelbericht RENAME TO toestelbericht_schema1")
        else:
            conn.execute("DROP TABLE toestelbericht")      # leeg: er gaat niets verloren
    if soort_van(conn, "toestelbericht") is None:
        conn.execute("""CREATE VIEW toestelbericht AS
                        SELECT ontvangen, bron, soort, kop, verzonden, ruw FROM bericht
                        WHERE protocol = 'atrack' AND COALESCE(posities_gemeld, 0) = 0""")

    # Plekken: de koppeling met een project via firma en nummer, niet via de naam.
    for kolom, soort in (("firma", "TEXT"), ("project_id", "TEXT"), ("min_minuten", "INTEGER")):
        if kolom not in kolommen(conn, "plek"):
            conn.execute(f"ALTER TABLE plek ADD COLUMN {kolom} {soort}")

    # Afgeleide projectplekken: het adres blijft van de bron (H-A Projecten, de projectmap);
    # hier staat alleen de geocode met waar ze vandaan komt. Nooit met de hand bijgehouden.
    conn.execute("""CREATE TABLE IF NOT EXISTS projectplek (
        sleutel            TEXT PRIMARY KEY,     -- '<firma>:<nummer>', bv. 'HARC:2604'
        firma              TEXT NOT NULL,
        firma_id           TEXT,
        nummer             TEXT NOT NULL,
        project_id         TEXT,                 -- uuid in H-A Projecten
        naam               TEXT,
        adres              TEXT,                 -- zoals de bron het geeft
        adres_bron         TEXT,                 -- projectmap (A13), volgens Monday, ...
        bron               TEXT NOT NULL,        -- ha-projecten | projectmap
        status             TEXT,
        link               TEXT,
        adres_vingerafdruk TEXT,
        lat                REAL,
        lon                REAL,
        geocode_bron       TEXT,                 -- geopunt | nominatim
        geocode_kwaliteit  TEXT,                 -- adres | straat | gemeente | niet_gevonden | geen_adres
        geocode_datum      INTEGER,
        straal             INTEGER NOT NULL DEFAULT 300,
        min_minuten        INTEGER NOT NULL DEFAULT 8,
        actief             INTEGER NOT NULL DEFAULT 1,   -- 0: niet meer in de bron, maar niet gewist
        eerst_gezien       INTEGER,
        laatst_gezien      INTEGER,
        bijgewerkt         INTEGER)""")
    conn.execute("CREATE INDEX IF NOT EXISTS projectplek_nummer ON projectplek(nummer)")
    # Wat Mehdi met de hand bevestigt of rechtzet, herleidbaar en nooit stil overschreven.
    conn.execute("""CREATE TABLE IF NOT EXISTS projectplek_override (
        sleutel     TEXT PRIMARY KEY,
        lat         REAL,
        lon         REAL,
        straal      INTEGER,
        min_minuten INTEGER,
        uitsluiten  INTEGER NOT NULL DEFAULT 0,
        reden       TEXT NOT NULL,
        door        TEXT NOT NULL,
        wanneer     INTEGER NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS bezoekcorrectie (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        bron        TEXT NOT NULL,
        van         INTEGER NOT NULL,
        tot         INTEGER NOT NULL,
        wat         TEXT NOT NULL CHECK (wat IN ('project', 'geen_project', 'niet_mehdi')),
        sleutel     TEXT,                        -- projectplek of plek, bij wat = project
        reden       TEXT,
        door        TEXT NOT NULL,
        wanneer     INTEGER NOT NULL,
        ingetrokken INTEGER)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS taakstatus (
        taak              TEXT PRIMARY KEY,
        laatst_geprobeerd INTEGER,
        laatst_geslaagd   INTEGER,
        fout              TEXT,
        detail            TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS adrescache (
        sleutel TEXT PRIMARY KEY, adres TEXT, volledig TEXT, bron TEXT, gezet INTEGER)""")
    # Op welke dagen er een verblijf op deze plek was, alleen uit de actieve reeks. Een plek
    # met vijf of meer dagen heet vaste plek. Begint leeg: niets geleerd uit oude metingen.
    conn.execute("""CREATE TABLE IF NOT EXISTS adresbezoek (
        sleutel TEXT NOT NULL, datum TEXT NOT NULL, PRIMARY KEY (sleutel, datum))""")


def _vul_berichten(conn):
    """Na de ombouw: elk bestaand punt krijgt zijn ruwe bericht, toestel, soort en teller.

    Alles komt uit de kolom ruw van dat punt zelf; er wordt niets van buiten ingelezen.
    De bewegingsstand van GTSTT werd tot nu toe naar de snelheid gelezen (22 op 0 km/u
    als stilstand); die wordt hier uit hetzelfde ruwe bericht opnieuw afgeleid.
    """
    rijen = conn.execute("SELECT rowid, bron, tst, soort, tid, ruw, ontvangen FROM punt").fetchall()
    for rowid, bron, tst, soort, tid, ruw, ontvangen in rijen:
        ruw = ruw or ""
        if ruw.startswith("+"):
            b = atrack.ontleed(ruw) or {}
            posities = b.get("posities") or []
            conn.execute("""INSERT OR IGNORE INTO bericht (ontvangen, laatst_ontvangen, bron, toestel, protocol, kop,
                                soort, protocolversie, teller, verzonden, posities_gemeld, posities_bewaard, verwerking,
                                herkomst, vingerafdruk, ruw)
                            VALUES (?, ?, ?, ?, 'atrack', ?, ?, ?, ?, ?, ?, ?, ?, 'punt (schema 1)', ?, ?)""",
                         (ontvangen or tst, ontvangen or tst, bron, b.get("imei"), b.get("kop"), b.get("soort"),
                          b.get("protocol"), b.get("teller"), b.get("verzonden"), b.get("posities_gemeld"),
                          1, "punten", vingerafdruk_bericht(ruw), ruw))
            bid = conn.execute("SELECT id FROM bericht WHERE vingerafdruk = ?",
                               (vingerafdruk_bericht(ruw),)).fetchone()[0]
            conn.execute("""UPDATE punt SET berichtsoort = ?, toestel = ?, teller = ?, bericht_id = ?,
                                motion = COALESCE(?, motion), verzonden = COALESCE(verzonden, ?)
                            WHERE rowid = ?""",
                         (b.get("soort") or soort or "", b.get("imei"), b.get("teller"), bid,
                          posities[0]["motion"] if posities else None, b.get("verzonden"), rowid))
        else:
            # Een punt van de telefoon: het ruwe bericht is de JSON van OwnTracks.
            conn.execute("""INSERT OR IGNORE INTO bericht (ontvangen, laatst_ontvangen, bron, toestel, protocol, soort,
                                posities_gemeld, posities_bewaard, verwerking, herkomst, vingerafdruk, ruw)
                            VALUES (?, ?, ?, ?, 'owntracks', ?, 1, 1, 'punten', 'punt (schema 1)', ?, ?)""",
                         (ontvangen or tst, ontvangen or tst, bron, tid, soort, vingerafdruk_bericht(ruw or str(tst)),
                          ruw or json.dumps({"tst": tst})))
            bid = conn.execute("SELECT id FROM bericht WHERE vingerafdruk = ?",
                               (vingerafdruk_bericht(ruw or str(tst)),)).fetchone()[0]
            conn.execute("UPDATE punt SET berichtsoort = ?, toestel = ?, bericht_id = ? WHERE rowid = ?",
                         (soort or "location", tid, bid, rowid))


def moment_sql():
    """De gebeurtenistijd van een punt, als SQL: met fix de meettijd, zonder fix de verzendtijd
    (die is dan het moment van de gebeurtenis), anders onbekend (NULL)."""
    return "CASE WHEN fix = 0 THEN verzonden ELSE tst END"


def _v3(conn):
    """Eén punt per positieblok van één ruw bericht: sleutel (bericht_id, volgnr).

    Gevonden bij de onafhankelijke controle van 05-10-2026: twee verschillende GTSTT-meldingen
    (stand 22 en 21, eigen teller en verzendtijd) met dezelfde oude fixtijd vielen met de sleutel
    (bron, tst, berichtsoort, volgnr) samen tot één punt; het tweede ruwe bericht kreeg 0 posities.
    Een gebeurtenis is een bericht, geen fix. Een exacte herhaling van een bericht blijft één
    bericht (vingerafdruk in de tabel bericht) en dus één verzameling punten.

    Nieuw: de kolom moment (gebeurtenistijd). Met fix is dat de meettijd, zonder fix de
    verzendtijd, en is die er niet, dan blijft het onbekend (NULL). Fixtijd (tst), gebeurtenistijd
    (moment) en ontvangsttijd (ontvangen) staan zo apart.
    """
    namen = kolommen(conn, "punt")
    if "moment" in namen:
        return
    if conn.execute("SELECT count(*) FROM punt WHERE bericht_id IS NULL").fetchone()[0]:
        _vul_berichten(conn)
    info = list(conn.execute("PRAGMA table_info(punt)"))
    defs = []
    for r in info:
        naam, soort, notnull = r[1], r[2] or "TEXT", r[3]
        if naam in ("tst", "bericht_id"):
            defs.append('"%s" INTEGER NOT NULL' % naam)
        elif naam in ("bron", "berichtsoort", "volgnr"):
            dflt = {"bron": "'iphone'", "berichtsoort": "''", "volgnr": "0"}[naam]
            defs.append('"%s" %s NOT NULL DEFAULT %s' % (naam, soort, dflt))
        else:
            defs.append('"%s" %s%s' % (naam, soort, " NOT NULL" if notnull else ""))
    defs.append('"moment" INTEGER')
    lijst = ", ".join('"%s"' % r[1] for r in info)
    voor = conn.execute("SELECT count(*) FROM punt").fetchone()[0]
    conn.execute("ALTER TABLE punt RENAME TO punt_schema2")
    for idx in ("punt_tst", "punt_bron"):
        conn.execute("DROP INDEX IF EXISTS %s" % idx)
    conn.execute("CREATE TABLE punt (%s, PRIMARY KEY (bericht_id, volgnr))" % ", ".join(defs))
    conn.execute("INSERT INTO punt (%s) SELECT %s FROM punt_schema2" % (lijst, lijst))
    na = conn.execute("SELECT count(*) FROM punt").fetchone()[0]
    if na != voor:
        raise RuntimeError("schema 3: %d punten voor, %d na de ombouw" % (voor, na))
    conn.execute("UPDATE punt SET moment = %s" % moment_sql())
    conn.execute("DROP TABLE punt_schema2")
    conn.execute("CREATE INDEX IF NOT EXISTS punt_tst ON punt(tst)")
    conn.execute("CREATE INDEX IF NOT EXISTS punt_bron ON punt(bron, tst)")
    conn.execute("CREATE INDEX IF NOT EXISTS punt_moment ON punt(bron, moment)")
    # Een bericht met minder punten dan posities heet niet langer stil 'punten'.
    conn.execute("""UPDATE bericht SET posities_bewaard = (SELECT count(*) FROM punt WHERE punt.bericht_id = bericht.id)
                    WHERE COALESCE(posities_gemeld, 0) > 0""")
    conn.execute("""UPDATE bericht SET verwerking = 'deels: ' || posities_bewaard || ' van de ' || posities_gemeld || ' posities'
                    WHERE COALESCE(posities_gemeld, 0) > 0 AND posities_bewaard < posities_gemeld""")
    # Plekken uit de telefoontijd (wifi-namen en coördinaten geleerd uit de metingen van 9-9 tot
    # 3-10-2026) gaan buiten de actieve herkenning, bewaard in plek_historiek. Thuis wordt opnieuw
    # bevestigd uit een toegestane adresbron (beheer.py thuis), nooit uit oude metingen.
    for kolom, soort in (("herkomst", "TEXT"), ("actief", "INTEGER NOT NULL DEFAULT 1")):
        if kolom not in kolommen(conn, "plek"):
            conn.execute(f"ALTER TABLE plek ADD COLUMN {kolom} {soort}")
    conn.execute("""CREATE TABLE IF NOT EXISTS plek_historiek (
        id INTEGER PRIMARY KEY AUTOINCREMENT, naam TEXT, lat REAL, lon REAL, straal INTEGER, wifi TEXT, soort TEXT,
        notitie TEXT, dossier TEXT, firma TEXT, herkomst TEXT, bewaard INTEGER NOT NULL, reden TEXT NOT NULL)""")
    conn.execute("""INSERT INTO plek_historiek (naam, lat, lon, straal, wifi, soort, notitie, dossier, firma, herkomst,
                                                bewaard, reden)
                    SELECT naam, lat, lon, straal, wifi, soort, notitie, dossier, firma,
                           'telefoontijd 9-9 tot 3-10-2026', CAST(strftime('%s', 'now') AS INTEGER),
                           'schema 3: geleerd in de telefoontijd, buiten de actieve herkenning gezet'
                    FROM plek WHERE herkomst IS NULL""")
    conn.execute("UPDATE plek SET actief = 0, herkomst = 'telefoontijd 9-9 tot 3-10-2026' WHERE herkomst IS NULL")
    # Verdachte berichten (plausibiliteit, bronbeleid) blijven bewaard maar tellen niet mee.
    if "verdacht" not in kolommen(conn, "bericht"):
        conn.execute("ALTER TABLE bericht ADD COLUMN verdacht TEXT")
    if "verdacht" not in kolommen(conn, "punt"):
        conn.execute("ALTER TABLE punt ADD COLUMN verdacht TEXT")


MIGRATIES = [(1, _v1), (2, _v2), (3, _v3)]


# ------------------------------------------------------------ uitvoeren

def _kopie(conn, pad, versie):
    """Een consistente kopie met datum, voor de upgrade begint. Geeft het pad."""
    map_ = os.path.join(os.path.dirname(os.path.abspath(pad)), "backups")
    os.makedirs(map_, exist_ok=True)
    doel = os.path.join(map_, "locatie-schema%d-%s.db" % (versie, time.strftime("%Y%m%dT%H%M%S")))
    kopie = sqlite3.connect(doel)
    try:
        conn.backup(kopie)
    finally:
        kopie.close()
    return doel


def migreer(pad):
    """Brengt de database op de laatste versie. Geeft (versie_voor, versie_na, kopie of None)."""
    conn = sqlite3.connect(pad, timeout=60, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout = 60000")
        conn.execute("PRAGMA journal_mode = WAL")
        voor = conn.execute("PRAGMA user_version").fetchone()[0]
        if voor >= LAATSTE:
            return voor, voor, None
        tabellen = conn.execute("SELECT count(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0]
        kopie = _kopie(conn, pad, voor) if tabellen else None
        conn.execute("BEGIN IMMEDIATE")
        try:
            versie = conn.execute("PRAGMA user_version").fetchone()[0]
            for nr, stap in MIGRATIES:
                if nr > versie:
                    stap(conn)
                    conn.execute("PRAGMA user_version = %d" % nr)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        return voor, conn.execute("PRAGMA user_version").fetchone()[0], kopie
    finally:
        conn.close()


_gemigreerd = set()


def verbind(pad):
    """Een verbinding op een database die zeker op de laatste versie staat."""
    if pad not in _gemigreerd:
        migreer(pad)
        _gemigreerd.add(pad)
    conn = sqlite3.connect(pad, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn

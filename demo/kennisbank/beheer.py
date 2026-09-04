"""Klanten, gebruikers, documenten en verbruik.

Tot nu toe stonden documenten in een JSON-bestand zonder eigenaar. Dat werkt voor
een demo en breekt zodra er een tweede klant is: je kunt niet factureren wat je
niet aan iemand kunt toeschrijven, en je kunt niet afschermen wat geen eigenaar
heeft.

Alles staat in een eigen SQLite-bestand, los van de kennisbanken zelf. Een
kennisbank blijft een bestand per document; deze database zegt alleen van wie hij
is en wat hij gekost heeft.

Het tegoed wordt NIET als saldo bewaard maar uit het grootboek opgeteld. Een
saldokolom en een boekingenlijst lopen na verloop van tijd uiteen, en dan heb je
twee getallen waarvan niemand weet welke klopt. Een boeking is positief bij een
bijstorting en negatief bij verbruik, en het tegoed is de som.
"""
from __future__ import annotations

import datetime as dt
import json
import secrets
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS klant (
    id          INTEGER PRIMARY KEY,
    naam        TEXT NOT NULL,
    btw_nummer  TEXT NOT NULL DEFAULT '',
    pakket      TEXT NOT NULL DEFAULT 'start',
    aangemaakt  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gebruiker (
    id          INTEGER PRIMARY KEY,
    klant_id    INTEGER NOT NULL REFERENCES klant(id) ON DELETE CASCADE,
    email       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    wachtwoord  TEXT NOT NULL,
    naam        TEXT NOT NULL DEFAULT '',
    rol         TEXT NOT NULL DEFAULT 'gebruiker',
    aangemaakt  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document (
    id           TEXT PRIMARY KEY,
    klant_id     INTEGER NOT NULL REFERENCES klant(id) ON DELETE CASCADE,
    titel        TEXT NOT NULL,
    bestandsnaam TEXT NOT NULL,
    bron         TEXT NOT NULL,
    bronpad      TEXT NOT NULL,
    aangemaakt   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'aangeleverd',
    verkenning   TEXT NOT NULL DEFAULT '{}',
    door         TEXT NOT NULL DEFAULT '',
    -- Een document wordt EEN keer afgerekend. Opnieuw bouwen na een verbeterde
    -- indeling mag niets kosten: het uitlezen is al betaald en bewaard.
    afgerekend   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS boeking (
    id          INTEGER PRIMARY KEY,
    klant_id    INTEGER NOT NULL REFERENCES klant(id) ON DELETE CASCADE,
    document_id TEXT,
    tijd        TEXT NOT NULL,
    bladzijden  INTEGER NOT NULL,     -- positief bij bijstorting, negatief bij verbruik
    bedrag_eur  REAL NOT NULL DEFAULT 0,
    soort       TEXT NOT NULL,        -- bijstorting | verwerking
    toelichting TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS boeking_klant ON boeking (klant_id, tijd);
CREATE INDEX IF NOT EXISTS document_klant ON document (klant_id, aangemaakt);
"""


def nu() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


@dataclass
class Gebruiker:
    id: int
    klant_id: int
    email: str
    naam: str
    rol: str

    @property
    def is_beheerder(self) -> bool:
        return self.rol == "beheerder"


class Beheer:
    def __init__(self, pad: Path):
        self.pad = Path(pad)
        self.pad.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.pad, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)

    # ------------------------------------------------------------ klanten

    def maak_klant(self, naam: str, btw_nummer: str = "",
                   pakket: str = "start", start_tegoed: int = 0) -> int:
        cur = self.db.execute(
            "INSERT INTO klant (naam, btw_nummer, pakket, aangemaakt)"
            " VALUES (?,?,?,?)", (naam, btw_nummer, pakket, nu()))
        klant_id = cur.lastrowid
        if start_tegoed:
            self.boek_bij(klant_id, start_tegoed, 0.0,
                          "bladzijden om mee te proberen")
        self.db.commit()
        return klant_id

    def klant(self, klant_id: int) -> dict | None:
        r = self.db.execute("SELECT * FROM klant WHERE id=?", (klant_id,)).fetchone()
        return dict(r) if r else None

    # ------------------------------------------------------------ gebruikers

    def email_bestaat(self, email: str) -> bool:
        return self.db.execute("SELECT 1 FROM gebruiker WHERE email=?",
                               (email.strip(),)).fetchone() is not None

    def maak_gebruiker(self, klant_id: int, email: str, wachtwoord: str,
                       naam: str = "", rol: str = "gebruiker") -> int:
        cur = self.db.execute(
            "INSERT INTO gebruiker (klant_id, email, wachtwoord, naam, rol, aangemaakt)"
            " VALUES (?,?,?,?,?,?)",
            (klant_id, email.strip(), generate_password_hash(wachtwoord),
             naam.strip(), rol, nu()))
        self.db.commit()
        return cur.lastrowid

    def controleer(self, email: str, wachtwoord: str) -> Gebruiker | None:
        r = self.db.execute("SELECT * FROM gebruiker WHERE email=?",
                            (email.strip(),)).fetchone()
        if not r or not check_password_hash(r["wachtwoord"], wachtwoord):
            return None
        return Gebruiker(r["id"], r["klant_id"], r["email"], r["naam"], r["rol"])

    def gebruiker(self, gebruiker_id: int) -> Gebruiker | None:
        r = self.db.execute("SELECT * FROM gebruiker WHERE id=?",
                            (gebruiker_id,)).fetchone()
        if not r:
            return None
        return Gebruiker(r["id"], r["klant_id"], r["email"], r["naam"], r["rol"])

    def gebruikers_van(self, klant_id: int) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT id, email, naam, rol, aangemaakt FROM gebruiker"
            " WHERE klant_id=? ORDER BY aangemaakt", (klant_id,))]

    # ------------------------------------------------------------ tegoed

    def tegoed(self, klant_id: int) -> int:
        """Het tegoed in bladzijden, opgeteld uit het grootboek."""
        r = self.db.execute(
            "SELECT COALESCE(SUM(bladzijden), 0) FROM boeking WHERE klant_id=?",
            (klant_id,)).fetchone()
        return int(r[0])

    def boek_bij(self, klant_id: int, bladzijden: int, bedrag: float,
                 toelichting: str) -> None:
        self.db.execute(
            "INSERT INTO boeking (klant_id, document_id, tijd, bladzijden,"
            " bedrag_eur, soort, toelichting) VALUES (?,?,?,?,?,'bijstorting',?)",
            (klant_id, None, nu(), abs(int(bladzijden)), bedrag, toelichting))
        self.db.commit()

    def boek_verbruik(self, klant_id: int, document_id: str, bladzijden: int,
                      bedrag: float, toelichting: str) -> None:
        self.db.execute(
            "INSERT INTO boeking (klant_id, document_id, tijd, bladzijden,"
            " bedrag_eur, soort, toelichting) VALUES (?,?,?,?,?,'verwerking',?)",
            (klant_id, document_id, nu(), -abs(int(bladzijden)), bedrag,
             toelichting))
        self.db.commit()

    def boekingen(self, klant_id: int, hoeveel: int = 50) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM boeking WHERE klant_id=? ORDER BY tijd DESC, id DESC"
            " LIMIT ?", (klant_id, hoeveel))]

    def verbruik_totaal(self, klant_id: int) -> dict:
        r = self.db.execute(
            "SELECT COALESCE(SUM(-bladzijden), 0) AS bladzijden,"
            " COALESCE(SUM(bedrag_eur), 0) AS bedrag, COUNT(*) AS aantal"
            " FROM boeking WHERE klant_id=? AND soort='verwerking'",
            (klant_id,)).fetchone()
        return dict(r)

    # ------------------------------------------------------------ documenten

    def maak_document(self, doc_id: str, klant_id: int, **velden) -> None:
        self.db.execute(
            "INSERT INTO document (id, klant_id, titel, bestandsnaam, bron,"
            " bronpad, aangemaakt, status, verkenning, door)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (doc_id, klant_id, velden["titel"], velden["bestandsnaam"],
             velden["bron"], velden["bronpad"], velden.get("aangemaakt", nu()),
             velden.get("status", "aangeleverd"),
             json.dumps(velden.get("verkenning", {}), ensure_ascii=False),
             velden.get("door", "")))
        self.db.commit()

    def document(self, doc_id: str, klant_id: int | None = None) -> dict | None:
        """Een document, en met klant_id erbij ook meteen de eigendomscontrole."""
        if klant_id is None:
            r = self.db.execute("SELECT * FROM document WHERE id=?",
                                (doc_id,)).fetchone()
        else:
            r = self.db.execute("SELECT * FROM document WHERE id=? AND klant_id=?",
                                (doc_id, klant_id)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["verkenning"] = json.loads(d["verkenning"] or "{}")
        return d

    def documenten_van(self, klant_id: int) -> list[dict]:
        uit = []
        for r in self.db.execute(
                "SELECT * FROM document WHERE klant_id=? ORDER BY aangemaakt DESC",
                (klant_id,)):
            d = dict(r)
            d["verkenning"] = json.loads(d["verkenning"] or "{}")
            uit.append(d)
        return uit

    def werk_document_bij(self, doc_id: str, **velden) -> None:
        if not velden:
            return
        kolommen = ", ".join(f"{k}=?" for k in velden)
        self.db.execute(f"UPDATE document SET {kolommen} WHERE id=?",
                        (*velden.values(), doc_id))
        self.db.commit()

    def verwijder_document(self, doc_id: str) -> None:
        # De boekingen blijven staan. Een klant die zijn bron weghaalt heeft die
        # verwerking wel gehad, en een grootboek waar posten uit verdwijnen is
        # geen grootboek meer.
        self.db.execute("UPDATE boeking SET document_id=NULL WHERE document_id=?",
                        (doc_id,))
        self.db.execute("DELETE FROM document WHERE id=?", (doc_id,))
        self.db.commit()


def geheime_sleutel(pad: Path) -> str:
    """Een sessiesleutel die een herstart overleeft.

    Met een sleutel die bij elke start verandert wordt iedereen uitgelogd zodra
    het proces herstart, en dat lijkt op een bug.
    """
    if pad.exists():
        return pad.read_text(encoding="utf-8").strip()
    sleutel = secrets.token_hex(32)
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(sleutel, encoding="utf-8")
    return sleutel

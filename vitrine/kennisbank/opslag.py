"""Opslag: een kennisbank per document, in een eigen SQLite-bestand.

Waarom per document en niet een gedeelde database. Een klant die zijn bron
terugtrekt moet spoorloos kunnen verdwijnen: bij auteursrechtelijk beschermd werk
is dat geen luxe maar de voorwaarde om het uberhaupt te mogen verwerken.
Verwijderen is hier een bestand weggooien, en niemand kan per ongeluk over de
grens van twee klanten heen zoeken.

Zoeken is hybride, net als in de bestaande agent: FTS5 levert de woordelijke
treffers, de vectoren de betekenis, en RRF voegt de twee ranglijsten samen. Voor
een enkel boek is dat exact genoeg -- duizend vectoren van 384 getallen zijn
anderhalve megabyte, dus het inproduct over de hele verzameling kost minder tijd
dan het opzetten van een index.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import vectoren
from .knippen import Fragment
from .structuur import Sectie

SCHEMA = """
CREATE TABLE IF NOT EXISTS document (
    id            TEXT PRIMARY KEY,
    titel         TEXT NOT NULL,
    bestandsnaam  TEXT NOT NULL,
    bladzijden    INTEGER NOT NULL,
    aangemaakt    TEXT NOT NULL,
    trefkans      REAL,
    verschuiving  INTEGER,
    dekking       REAL,
    embedmodel    TEXT,
    dim           INTEGER,
    status        TEXT NOT NULL DEFAULT 'concept',
    meta          TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS sectie (
    id         INTEGER PRIMARY KEY,
    titel      TEXT NOT NULL,
    van        INTEGER NOT NULL,
    tot        INTEGER NOT NULL,
    niveau     INTEGER NOT NULL DEFAULT 1,
    hoofdstuk  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS fragment (
    id         INTEGER PRIMARY KEY,
    volgnummer INTEGER NOT NULL,
    tekst      TEXT NOT NULL,
    soort      TEXT NOT NULL DEFAULT 'tekst',
    fysiek     INTEGER NOT NULL,
    gedrukt    INTEGER,
    hoofdstuk  TEXT NOT NULL DEFAULT '',
    sectie     TEXT NOT NULL DEFAULT '',
    kop_pad    TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS vector (
    fragment_id INTEGER PRIMARY KEY REFERENCES fragment(id) ON DELETE CASCADE,
    waarden     BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS fragment_pagina ON fragment (fysiek);
CREATE VIRTUAL TABLE IF NOT EXISTS fragment_fts USING fts5(tekst, tokenize='unicode61');
"""


@dataclass
class Treffer:
    fragment_id: int
    tekst: str
    soort: str
    fysiek: int
    gedrukt: int | None
    hoofdstuk: str
    sectie: str
    score: float
    woord_rang: int | None = None
    vector_rang: int | None = None


class Kennisbank:
    def __init__(self, pad: Path):
        self.pad = Path(pad)
        self.pad.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.pad, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self._matrix: np.ndarray | None = None
        self._ids: list[int] = []

    # ---------------------------------------------------------------- vullen

    def leg_vast(self, *, doc_id: str, titel: str, bestandsnaam: str,
                 bladzijden: int, aangemaakt: str, trefkans: float,
                 verschuiving: int | None, dekking: float, meta: dict) -> None:
        self.db.execute("DELETE FROM document")
        self.db.execute(
            "INSERT INTO document (id,titel,bestandsnaam,bladzijden,aangemaakt,"
            "trefkans,verschuiving,dekking,embedmodel,dim,status,meta)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (doc_id, titel, bestandsnaam, bladzijden, aangemaakt, trefkans,
             verschuiving, dekking, vectoren.MODEL, vectoren.DIM, 'live',
             json.dumps(meta, ensure_ascii=False)))
        self.db.commit()

    def schrijf_secties(self, secties: list[Sectie]) -> None:
        self.db.execute("DELETE FROM sectie")
        self.db.executemany(
            "INSERT INTO sectie (titel,van,tot,niveau,hoofdstuk) VALUES (?,?,?,?,?)",
            [(s.titel, s.van, s.tot, s.niveau, s.hoofdstuk) for s in secties])
        self.db.commit()

    def schrijf_fragmenten(self, fragmenten: list[Fragment],
                           vecs: np.ndarray) -> None:
        if len(fragmenten) != len(vecs):
            raise ValueError(
                f"{len(fragmenten)} fragmenten maar {len(vecs)} vectoren: "
                "dat loopt gegarandeerd mis bij het zoeken")
        self.db.execute("DELETE FROM fragment")
        self.db.execute("DELETE FROM vector")
        self.db.execute("DELETE FROM fragment_fts")
        for f, v in zip(fragmenten, vecs):
            cur = self.db.execute(
                "INSERT INTO fragment (volgnummer,tekst,soort,fysiek,gedrukt,"
                "hoofdstuk,sectie,kop_pad) VALUES (?,?,?,?,?,?,?,?)",
                (f.volgnummer, f.tekst, f.soort, f.fysiek, f.gedrukt,
                 f.hoofdstuk, f.sectie, json.dumps(f.kop_pad, ensure_ascii=False)))
            fid = cur.lastrowid
            self.db.execute("INSERT INTO vector (fragment_id,waarden) VALUES (?,?)",
                            (fid, vectoren.naar_blob(v)))
            # In de zoekindex gaat de kop-keten mee: wie op een hoofdstuktitel
            # zoekt hoort de fragmenten uit dat hoofdstuk te vinden.
            self.db.execute("INSERT INTO fragment_fts (rowid,tekst) VALUES (?,?)",
                            (fid, f.met_context))
        self.db.commit()
        self._matrix = None

    # ---------------------------------------------------------------- lezen

    def info(self) -> dict | None:
        r = self.db.execute("SELECT * FROM document").fetchone()
        return dict(r) if r else None

    def secties(self) -> list[dict]:
        return [dict(r) for r in
                self.db.execute("SELECT * FROM sectie ORDER BY van, niveau")]

    def aantal_fragmenten(self) -> int:
        return self.db.execute("SELECT count(*) FROM fragment").fetchone()[0]

    def fragment(self, fid: int) -> dict | None:
        r = self.db.execute("SELECT * FROM fragment WHERE id=?", (fid,)).fetchone()
        return dict(r) if r else None

    def steekproef(self, hoeveel: int) -> list[dict]:
        """Een gespreide greep uit de tekstfragmenten, voor de rookproef."""
        rijen = [dict(r) for r in self.db.execute(
            "SELECT * FROM fragment WHERE soort='tekst' AND length(tekst)>400"
            " ORDER BY volgnummer")]
        if not rijen or hoeveel <= 0:
            return []
        stap = max(1, len(rijen) // hoeveel)
        return rijen[::stap][:hoeveel]

    def _laad_matrix(self) -> tuple[np.ndarray, list[int]]:
        if self._matrix is None:
            ids, rijen = [], []
            for r in self.db.execute(
                    "SELECT fragment_id, waarden FROM vector ORDER BY fragment_id"):
                ids.append(r["fragment_id"])
                rijen.append(vectoren.uit_blob(r["waarden"]))
            self._matrix = (np.vstack(rijen) if rijen
                            else np.zeros((0, vectoren.DIM), dtype=np.float32))
            self._ids = ids
        return self._matrix, self._ids

    # ---------------------------------------------------------------- zoeken

    @staticmethod
    def _fts_vraag(vraag: str) -> str:
        """Een veilige FTS5-vraag: elk woord apart aangehaald.

        Rechtstreeks doorgeven werkt niet. Een vraag met een apostrof of een
        koppelteken is voor FTS5 syntaxis, en dan krijg je geen resultaat maar een
        foutmelding.
        """
        woorden = re.findall(r"\w+", vraag, re.UNICODE)
        return " OR ".join(f'"{w}"' for w in woorden if len(w) > 1)

    def zoek(self, vraag: str, k: int = 8, rrf_k: int = 60) -> list[Treffer]:
        """Hybride ophalen: woorden en betekenis, samengevoegd met RRF.

        rrf_k staat op 60, dezelfde waarde als in de bestaande retrieval. Wat die
        constante doet is de invloed van de allereerste plek temperen, zodat een
        fragment dat in beide ranglijsten redelijk scoort wint van een fragment
        dat er in maar een bovenaan staat.
        """
        breedte = max(k * 5, 40)

        woord_rang: dict[int, int] = {}
        fts = self._fts_vraag(vraag)
        if fts:
            for n, r in enumerate(self.db.execute(
                    "SELECT rowid FROM fragment_fts WHERE fragment_fts MATCH ?"
                    " ORDER BY bm25(fragment_fts) LIMIT ?", (fts, breedte))):
                woord_rang[r["rowid"]] = n + 1

        vector_rang: dict[int, int] = {}
        matrix, ids = self._laad_matrix()
        if len(matrix):
            scores = matrix @ vectoren.embed_een(vraag)
            for n, i in enumerate(np.argsort(-scores)[:breedte]):
                vector_rang[ids[int(i)]] = n + 1

        samen: dict[int, float] = {}
        for rang in (woord_rang, vector_rang):
            for fid, plek in rang.items():
                samen[fid] = samen.get(fid, 0.0) + 1.0 / (rrf_k + plek)

        beste = sorted(samen.items(), key=lambda x: -x[1])[:k]
        uit: list[Treffer] = []
        for fid, score in beste:
            f = self.fragment(fid)
            if not f:
                continue
            uit.append(Treffer(
                fragment_id=fid, tekst=f["tekst"], soort=f["soort"],
                fysiek=f["fysiek"], gedrukt=f["gedrukt"],
                hoofdstuk=f["hoofdstuk"], sectie=f["sectie"], score=score,
                woord_rang=woord_rang.get(fid), vector_rang=vector_rang.get(fid)))
        return uit

    def sluit(self) -> None:
        self.db.close()

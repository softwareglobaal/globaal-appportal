"""Grendel op de gesprekkentabel en de afzender van klaargezette items (ontwerp regie-zoom v1.2: Z10, Z11, Z12, J5, M6).

Gemeten op 21-10-2026: gesprek_log had geen koppelkolom, dus telde elk gesprek dat Zoom en Fathom allebei hebben twee
keer (15 van de 16 Zoom-rijen sinds 07-10 stonden naast een Fathom-rij), en het bord vulde een ontbrekende bron stil in
met fathom. Deze test legt vast:

- T01: een oude databank krijgt sessie en dubbel_van (standaard leeg) en een index op sessie; bestaande rijen blijven
  gelijk; twee verbindingen die de oude tabel tegelijk zien, breken niet (J5, het patroon van _mail_tabellen);
- T02: een upsert zonder sessie en dubbel_van wist een koppeling niet, en koppelen raakt de velden van Fathom niet;
- T03: koppelen maakt nooit een rij, en weigert een rij die naar zichzelf verwijst of een doel dat zelf een dubbel is;
- T04: koppelen zonder token geeft 403; een rij zonder bron wordt geteld (zonder_bron);
- T105 (M6): een andere afzender overschrijft geen klaargezet item: 409, dat item blijft, de rest van de oproep niet;
- Z12: de pagina toont een dubbel grijs en maakt alleen een Fathom-link klikbaar; de dagenpagina telt geen dubbel.

Draait in de Docker-build en in regie-grendels.yml (job bord): faalt dit, dan blijft de vorige container staan.
"""
import os
import sqlite3
import sys
import tempfile
import threading

MAP = tempfile.mkdtemp()
os.environ["AGENTS_DB"] = os.path.join(MAP, "start.db")
os.environ["AGENTS_TOKEN"] = "proef"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A  # noqa: E402

K = {"X-Agents-Token": "proef"}
BEHEER = {"X-authentik-groups": "admin", "X-authentik-username": "proef"}
C = A.app.test_client()
fout = 0

# Het schema van gesprek_log zoals het tot 21-10-2026 op de VM stond: 17 kolommen, zonder sessie en dubbel_van.
OUD_SCHEMA = """
CREATE TABLE gesprek_log (
    uniek     TEXT PRIMARY KEY,
    datum     TEXT, start TEXT, minuten INTEGER,
    personen  TEXT DEFAULT '', bedrijf TEXT DEFAULT '', afdeling TEXT DEFAULT '',
    thema     TEXT DEFAULT '', project TEXT DEFAULT '', prive INTEGER DEFAULT 0,
    zekerheid TEXT DEFAULT '', waarom TEXT DEFAULT '', archief TEXT DEFAULT '',
    link      TEXT DEFAULT '', opgenomen_door TEXT DEFAULT '', bron TEXT DEFAULT 'fathom',
    ts        TEXT NOT NULL
);
INSERT INTO gesprek_log(uniek, datum, start, minuten, personen, thema, archief, link, bron, ts) VALUES
    ('fathom:101', '2026-10-20', '09:10', 31, 'Jan Proef', 'Werfoverleg', '/data/fathom-data/2026-10-20 0910 Proef',
     'https://fathom.video/calls/101', 'fathom', '2026-10-20T07:40:00+00:00'),
    ('zoom:meeting:oud', '2026-10-20', '09:09', 32, 'Jan Proef', 'Zoom-gesprek', '', '', 'zoom', '2026-10-20T07:45:00+00:00');
"""


def check(naam, voorwaarde, extra=""):
    global fout
    print(("  ok   " if voorwaarde else "  FOUT ") + naam, "" if voorwaarde else extra)
    fout += 0 if voorwaarde else 1


def verse_db(naam):
    """Een eigen, nieuwe databank per toets."""
    A.DB_PAD = os.path.join(MAP, naam + ".db")
    A.init_db()
    return A.DB_PAD


def kolommen(pad):
    c = sqlite3.connect(pad)
    try:
        return {r[0]: r[1] for r in c.execute("SELECT name, dflt_value FROM pragma_table_info('gesprek_log')")}
    finally:
        c.close()


def rijen(pad):
    c = sqlite3.connect(pad)
    c.row_factory = sqlite3.Row
    try:
        return {r["uniek"]: dict(r) for r in c.execute("SELECT * FROM gesprek_log")}
    finally:
        c.close()


def index_op_sessie(pad):
    c = sqlite3.connect(pad)
    try:
        return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='gesprek_log_sessie'").fetchone())
    finally:
        c.close()


def zet(rij_lijst, kop=K):
    return C.post("/api/gesprekken", json={"rijen": rij_lijst}, headers=kop)


def koppel(koppelingen, kop=K):
    return C.post("/api/gesprekken/koppel", json={"koppelingen": koppelingen}, headers=kop)


FATHOM = {"uniek": "fathom:1", "datum": "2026-10-20", "start": "09:10", "minuten": 31, "personen": "Jan Proef",
          "bedrijf": "Proef bv", "afdeling": "h-architects", "thema": "Werfoverleg", "project": "2531 Proef",
          "zekerheid": "hoog", "waarom": "titel", "archief": "/data/fathom-data/2026-10-20 0910 Proef",
          "link": "https://fathom.video/calls/1", "opgenomen_door": "Mehdi", "bron": "fathom"}


# ------------------------------------------------------------------------------------------------- T01 ---
def t01_oude_databank():
    pad = A.DB_PAD = os.path.join(MAP, "t01.db")
    c = sqlite3.connect(pad)
    c.executescript(OUD_SCHEMA)
    c.close()
    voor = rijen(pad)
    check("T01 de proef begint echt op de oude tabel", "sessie" not in kolommen(pad) and len(voor) == 2, kolommen(pad))
    A.init_db()
    kol = kolommen(pad)
    check("T01 sessie en dubbel_van bestaan, standaard leeg", kol.get("sessie") == "''" and kol.get("dubbel_van") == "''", kol)
    check("T01 index op sessie", index_op_sessie(pad))
    na = rijen(pad)
    oude_kolommen = [k for k in voor["fathom:101"] if k not in ("sessie", "dubbel_van")]
    check("T01 bestaande rijen ongewijzigd, met lege koppeling",
          all({k: na[u][k] for k in oude_kolommen} == {k: voor[u][k] for k in oude_kolommen} for u in voor)
          and all(na[u]["sessie"] == "" and na[u]["dubbel_van"] == "" for u in na), (voor, na))
    try:
        A.init_db()
        check("T01 init_db een tweede keer: geen fout", kolommen(pad) == kol)
    except sqlite3.Error as e:
        check("T01 init_db een tweede keer: geen fout", False, e)
    nieuw = verse_db("t01-nieuw")
    check("T01 een nieuwe databank heeft de kolommen en de index meteen",
          {"sessie", "dubbel_van"} <= set(kolommen(nieuw)) and index_op_sessie(nieuw))


class _Rijen(list):
    def fetchall(self):
        return list(self)


class _TrageWerker(sqlite3.Connection):
    """Werker B leest de oude kolommen, en net daarna voegt werker A ze toe en sluit af: de race van J5. Zonder het
    opnieuw lezen onder het slot zou B dezelfde kolom nog eens toevoegen (duplicate column name)."""
    na_eerste_lezing = None

    def execute(self, sql, *args):
        cur = super().execute(sql, *args)
        if "table_info(gesprek_log)" in sql and _TrageWerker.na_eerste_lezing:
            gelezen = cur.fetchall()
            ander, _TrageWerker.na_eerste_lezing = _TrageWerker.na_eerste_lezing, None
            ander()
            return _Rijen(gelezen)
        return cur


def t01_twee_verbindingen():
    pad = os.path.join(MAP, "t01-race.db")
    c = sqlite3.connect(pad)
    c.executescript(OUD_SCHEMA)
    c.close()

    def werker_a():
        a = sqlite3.connect(pad)
        try:
            A._gesprek_log_kolommen(a)
        finally:
            a.close()

    _TrageWerker.na_eerste_lezing = werker_a
    b = sqlite3.connect(pad, factory=_TrageWerker)
    try:
        A._gesprek_log_kolommen(b)
        gelukt = True
    except sqlite3.Error as e:
        gelukt = e
    finally:
        b.close()
    kol = [r[0] for r in sqlite3.connect(pad).execute("SELECT name FROM pragma_table_info('gesprek_log')")]
    check("T01 twee verbindingen: werker B breekt niet als A de kolommen net toevoegde", gelukt is True, gelukt)
    check("T01 twee verbindingen: elke kolom een keer", kol.count("sessie") == 1 and kol.count("dubbel_van") == 1, kol)
    check("T01 twee verbindingen: de index staat er", index_op_sessie(pad))

    # en echt tegelijk: twee werkers die init_db op dezelfde oude databank draaien
    A.DB_PAD = os.path.join(MAP, "t01-tegelijk.db")
    c = sqlite3.connect(A.DB_PAD)
    c.executescript(OUD_SCHEMA)
    c.close()
    start, fouten = threading.Barrier(2), []

    def werker():
        start.wait()
        try:
            A.init_db()
        except Exception as e:  # noqa: BLE001
            fouten.append(e)

    draden = [threading.Thread(target=werker) for _ in range(2)]
    for d in draden:
        d.start()
    for d in draden:
        d.join(30)
    check("T01 twee werkers tegelijk: geen fout, kolommen er", not fouten and {"sessie", "dubbel_van"} <= set(kolommen(A.DB_PAD)),
          fouten)


# ------------------------------------------------------------------------------------------------- T02 ---
def t02_upsert_wist_koppeling_niet():
    pad = verse_db("t02")
    tweede = dict(FATHOM, uniek="fathom:2", personen="Piet Proef", opgenomen_door="Shaniel Work")
    zoom = {"uniek": "zoom:meeting:u1", "datum": "2026-10-20", "start": "09:09", "minuten": 32, "bron": "zoom",
            "thema": "Zoom-gesprek in de vaste vergaderruimte", "opgenomen_door": "Zoom"}
    zet([FATHOM, tweede, zoom])
    r = koppel([{"uniek": "fathom:1", "sessie": "zoom:meeting:u1"},
                {"uniek": "fathom:2", "sessie": "zoom:meeting:u1", "dubbel_van": "fathom:1"}]).get_json()
    check("T02 koppelen gezet", sorted(r["gezet"]) == ["fathom:1", "fathom:2"] and not r["onbekend"] and not r["geweigerd"], r)
    na_koppel = rijen(pad)
    check("T02 koppelen raakt de velden van Fathom niet",
          all(na_koppel["fathom:1"][k] == FATHOM[k] for k in ("personen", "thema", "archief", "link", "bron")), na_koppel["fathom:1"])
    zet([dict(FATHOM), dict(tweede)])         # De Fathomwacht schrijft dezelfde rijen opnieuw, zonder koppelsleutels
    na = rijen(pad)
    check("T02 sessie blijft staan na een upsert zonder sleutels",
          na["fathom:1"]["sessie"] == "zoom:meeting:u1" and na["fathom:2"]["sessie"] == "zoom:meeting:u1", na)
    check("T02 dubbel_van blijft staan na een upsert zonder sleutels",
          na["fathom:2"]["dubbel_van"] == "fathom:1" and na["fathom:1"]["dubbel_van"] == "", na)
    check("T02 personen, thema en archief blijven die van Fathom",
          na["fathom:2"]["personen"] == "Piet Proef" and na["fathom:1"]["thema"] == "Werfoverleg"
          and na["fathom:1"]["archief"] == FATHOM["archief"], na)
    # De Zoomwacht schrijft zijn eigen rij met de koppelsleutels: alleen wat meekomt, verandert
    zet([dict(zoom, sessie="zoom:meeting:u1", dubbel_van="fathom:1")])
    zet([dict(zoom, sessie="zoom:meeting:u1")])
    z = rijen(pad)["zoom:meeting:u1"]
    check("T02 een sleutel die meekomt wordt gezet, een die ontbreekt blijft",
          z["sessie"] == "zoom:meeting:u1" and z["dubbel_van"] == "fathom:1", z)
    zet([dict(zoom, dubbel_van="")])
    check("T02 een lege dubbel_van die meekomt, maakt de rij weer tellend", rijen(pad)["zoom:meeting:u1"]["dubbel_van"] == "")


# ------------------------------------------------------------------------------------------------- T03 ---
def t03_koppelen_weigert():
    pad = verse_db("t03")
    zet([FATHOM, dict(FATHOM, uniek="fathom:2"), dict(FATHOM, uniek="fathom:3"),
         {"uniek": "zoom:meeting:u3", "datum": "2026-10-20", "bron": "zoom"}])
    koppel([{"uniek": "fathom:2", "dubbel_van": "fathom:1"}])
    voor = rijen(pad)
    r = koppel([{"uniek": "fathom:999", "sessie": "zoom:meeting:u3"},
                {"uniek": "fathom:3", "dubbel_van": "fathom:3"},
                {"uniek": "fathom:3", "dubbel_van": "fathom:2"},
                {"uniek": "fathom:3", "dubbel_van": "fathom:404"}])
    j = r.get_json()
    na = rijen(pad)
    check("T03 antwoord 200 met gezet, onbekend en geweigerd", r.status_code == 200 and {"gezet", "onbekend", "geweigerd"} <= set(j), j)
    check("T03 een onbekende uniek staat in onbekend", j["onbekend"] == ["fathom:999"], j)
    redenen = {g["reden"] for g in j["geweigerd"]}
    check("T03 naar zichzelf, naar een dubbel en naar een onbestaand doel: geweigerd",
          len(j["geweigerd"]) == 3 and all(g["uniek"] == "fathom:3" for g in j["geweigerd"])
          and any("zelf" in x and "rij" in x for x in redenen) and any("zelf een dubbel" in x for x in redenen)
          and any("bestaat niet" in x for x in redenen), j)
    check("T03 geen rij aangemaakt, niets veranderd", na == voor and "fathom:999" not in na, na)
    # Een merkteken buiten:<reden> is geen verwijzing naar een rij (J10): dat mag, en het telt dan niet
    j = koppel([{"uniek": "fathom:3", "dubbel_van": "buiten:andere-ruimte"}]).get_json()
    check("T03 buiten:andere-ruimte wordt gezet", j["gezet"] == ["fathom:3"] and rijen(pad)["fathom:3"]["dubbel_van"] == "buiten:andere-ruimte", j)
    # Eerst vrijmaken, dan verwijzen: in dezelfde oproep wordt fathom:2 de leidende rij en verwijst fathom:1 ernaar
    j = koppel([{"uniek": "fathom:1", "dubbel_van": "fathom:2"}, {"uniek": "fathom:2", "dubbel_van": ""}]).get_json()
    na = rijen(pad)
    check("T03 een nieuwe leidende rij komt in dezelfde oproep eerst vrij",
          sorted(j["gezet"]) == ["fathom:1", "fathom:2"] and na["fathom:2"]["dubbel_van"] == "" and na["fathom:1"]["dubbel_van"] == "fathom:2", j)
    r = C.post("/api/gesprekken/koppel", json={"koppelingen": "fathom:1"}, headers=K)
    check("T03 koppelingen die geen lijst zijn: 400", r.status_code == 400, r.status_code)
    j = koppel([{"sessie": "x"}, {"uniek": "fathom:1"}]).get_json()
    check("T03 zonder uniek of zonder veld: geweigerd, niets gezet", not j["gezet"] and len(j["geweigerd"]) == 2, j)


# ------------------------------------------------------------------------------------------------- T04 ---
def t04_token_en_bron():
    pad = verse_db("t04")
    zet([FATHOM])
    r = koppel([{"uniek": "fathom:1", "dubbel_van": "buiten:andere-ruimte"}], kop={})
    check("T04 koppelen zonder token: 403", r.status_code == 403, r.status_code)
    r = koppel([{"uniek": "fathom:1", "dubbel_van": "buiten:andere-ruimte"}], kop={"X-Agents-Token": "fout"})
    check("T04 koppelen met een fout token: 403", r.status_code == 403, r.status_code)
    check("T04 zonder token niets gezet", rijen(pad)["fathom:1"]["dubbel_van"] == "")
    zonder = {k: v for k, v in FATHOM.items() if k != "bron"}
    j = zet([dict(zonder, uniek="oud:1"), dict(FATHOM, uniek="fathom:5")]).get_json()
    check("T04 een rij zonder bron: zonder_bron = 1", j.get("zonder_bron") == 1 and j.get("rijen") == 2, j)
    check("T04 de standaard fathom blijft voor oude afzenders", rijen(pad)["oud:1"]["bron"] == "fathom")
    check("T04 POST zonder token: 403", zet([FATHOM], kop={}).status_code == 403)


# ------------------------------------------------------------------------------------------------ T105 ---
def klaarzet(items):
    return C.post("/api/klaarzet", json={"items": items}, headers=K)


def bak(pad):
    c = sqlite3.connect(pad)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute("SELECT * FROM klaarzet ORDER BY id")]
    finally:
        c.close()


def t105_andere_afzender():
    pad = verse_db("t105")
    ochtend = {"van": "regisseur", "voor": "mehdi", "soort": "ochtendbericht", "titel": "Ochtendbericht do 22-10, 5 beslissingen",
               "uniek": "ochtendbericht:2026-10-22", "inhoud": {"punten": [1, 2, 3, 4, 5]}}
    r = klaarzet([ochtend])
    check("T105 de eigen afzender zet het item", r.status_code == 200 and r.get_json()["nieuw"] == 1, r.get_json())
    voor = bak(pad)
    vals = dict(ochtend, van="ontwikkelaar", titel="Ochtendbericht vervangen", inhoud={"punten": []})
    ander = {"van": "ontwikkelaar", "voor": "mehdi", "soort": "signaal", "titel": "Los signaal", "uniek": "ontwikkelaar:los"}
    r = klaarzet([ander, vals])
    j = r.get_json()
    check("T105 een andere afzender op een bestaande uniek: 409 met een duidelijke fout",
          r.status_code == 409 and j.get("ok") is False and "ochtendbericht:2026-10-22" in j.get("fout", "")
          and "regisseur" in j["fout"] and "ontwikkelaar" in j["fout"], (r.status_code, j))
    check("T105 de weigering noemt uniek, afzender en bestaande afzender",
          j.get("geweigerd") == [{"uniek": "ochtendbericht:2026-10-22", "van": "ontwikkelaar", "bestaande_van": "regisseur"}], j)
    na = bak(pad)
    check("T105 het item van de regisseur is ongewijzigd", [b for b in na if b["uniek"] == "ochtendbericht:2026-10-22"] == voor, na)
    check("T105 het andere item van de oproep is wel geschreven, en dat staat in het antwoord",
          [b["uniek"] for b in na if b["van"] == "ontwikkelaar"] == ["ontwikkelaar:los"] and j.get("nieuw") == 1, (na, j))
    voor = [b for b in na if b["uniek"] == "ochtendbericht:2026-10-22"]
    # ook als het item al opgepakt is en de andere afzender om revisie vraagt
    C.post(f"/api/klaarzet/{voor[0]['id']}/opgepakt", json={"door": "bode"}, headers=K)
    r = klaarzet([dict(vals, revisie=True)])
    revisies = C.get("/api/klaarzet/revisies?uniek=ochtendbericht:2026-10-22", headers=K).get_json()["revisies"]
    check("T105 ook met revisie geweigerd, geen revisierij", r.status_code == 409 and revisies == [], (r.status_code, revisies))
    check("T105 na de revisiepoging is het item nog dat van de regisseur",
          [dict(b, status="", opgepakt_door="", opgepakt_ts="") for b in bak(pad) if b["uniek"] == "ochtendbericht:2026-10-22"]
          == [dict(b, status="", opgepakt_door="", opgepakt_ts="") for b in voor], bak(pad))
    # binnen een oproep: twee items met dezelfde uniek en een andere afzender; de eerste telt, de tweede niet
    r = klaarzet([dict(ander, uniek="dubbel:in-een-oproep"), dict(ander, van="bode", titel="Overschreven", uniek="dubbel:in-een-oproep")])
    rij = [b for b in bak(pad) if b["uniek"] == "dubbel:in-een-oproep"]
    check("T105 twee afzenders in dezelfde oproep: 409, de eerste blijft",
          r.status_code == 409 and len(rij) == 1 and rij[0]["van"] == "ontwikkelaar" and rij[0]["titel"] == "Los signaal",
          (r.get_json(), rij))
    # de eigen afzender werkt het item bij zoals voordien
    r = klaarzet([dict(ochtend, inhoud={"punten": [1, 2, 3, 4, 5], "extra": 1})])
    check("T105 dezelfde afzender: gewoon 200", r.status_code == 200 and r.get_json()["ok"] is True, r.get_json())
    # de gemeten uitzondering: de Mac-mailwacht per postvak op mailsignaal:<Message-ID>
    sig = {"van": "mail-mch", "voor": "mehdi", "soort": "signaal", "titel": "Mail hoog belang: proef", "uniek": "mailsignaal:<proef@x>"}
    klaarzet([sig])
    r = klaarzet([dict(sig, van="mail-prive")])
    check("T105 mailsignaal van een tweede postvak blijft werken", r.status_code == 200, r.get_json())


# ------------------------------------------------------------------------------------------------- Z12 ---
def z12_pagina_en_telling():
    verse_db("z12")
    zet([FATHOM, dict(FATHOM, uniek="fathom:2", personen="Piet Proef"),
         {"uniek": "zoom:meeting:oud", "datum": "2026-10-20", "start": "09:09", "minuten": 32, "bron": "zoom",
          "link": "https://us02web.zoom.us/j/81234567890?pwd=proefcode"}])
    koppel([{"uniek": "fathom:2", "dubbel_van": "fathom:1"}, {"uniek": "zoom:meeting:oud", "dubbel_van": "buiten:andere-ruimte"}])
    r = C.get("/gesprekken", headers=BEHEER)
    html = r.get_data(as_text=True)
    check("Z12 pagina voor beheer", r.status_code == 200, r.status_code)
    check("Z12 een dubbel is grijs en zegt waarvan", 'class=" dubbel"' in html and "dubbel van fathom:1" in html, html[-3000:])
    check("Z12 een merkteken buiten zegt dat de rij niet telt", "telt niet: andere ruimte" in html)
    check("Z12 alleen een Fathom-link is klikbaar", 'href="https://fathom.video/calls/1"' in html
          and 'href="https://us02web.zoom.us' not in html, html[-3000:])
    check("Z12 geen gedachtestreepje op de pagina", "\N{EM DASH}" not in html and "\N{EN DASH}" not in html)
    # de dagenpagina telt dezelfde regel: een rij met dubbel_van telt niet
    gevangen = {}
    echt_render, echt_locatie = A.render_template, A._locatie
    A.render_template = lambda naam, **kw: gevangen.update(kw) or ""
    A._locatie = lambda pad, standaard=None: standaard
    try:
        C.get("/dagen", headers=BEHEER)
    finally:
        A.render_template, A._locatie = echt_render, echt_locatie
    dag = next((d for d in gevangen.get("rijen", []) if d["dag"] == "2026-10-20"), {})
    check("Z12 de dagenpagina telt een gesprek met een dubbel een keer", dag.get("gesprekken") == 1, dag)
    # J10, Z12: ook de pagina van een dag (waar het ochtendbericht naar linkt) toont een dubbel grijs, met waarvan, en een
    # rij buiten de ruimte als niet tellend; de tellende rijen eerst
    A._locatie = lambda pad, standaard=None: standaard
    try:
        r = C.get("/dag/2026-10-20", headers=BEHEER)
    finally:
        A._locatie = echt_locatie
    html = r.get_data(as_text=True)
    check("Z12 dagpagina gerenderd", r.status_code == 200, r.status_code)
    check("Z12 dagpagina: een dubbel is grijs en zegt waarvan", 'class="dubbel"' in html and "dubbel van fathom:1" in html, html[-2500:])
    check("Z12 dagpagina: buiten de ruimte telt niet", "telt niet: andere ruimte" in html, html[-2500:])
    check("Z12 dagpagina: de tellende rij staat eerst", html.find("Jan Proef") < html.find("Piet Proef"), html[-2500:])
    check("Z12 dagpagina zegt hoeveel er tellen", "1 gesprek telt, 2 dubbel of buiten" in html, html[-2500:])
    check("Z12 dagpagina zonder gedachtestreepje", "\N{EM DASH}" not in html and "\N{EN DASH}" not in html)


def t_o26_dagenpagina_zonder_privenamen():
    """Controle Codex 26-10-2026: de dagenpagina nam de namen van een privérij over. Ze telt de rij, zonder namen."""
    verse_db("o26")
    zet([FATHOM, dict(FATHOM, uniek="zoom:meeting:prive-p", personen="Familie Proef", prive=True, bron="zoom"),
         dict(FATHOM, uniek="fathom:3", personen="Kees Proef", afdeling="prive")])
    gevangen = {}
    echt_render, echt_locatie = A.render_template, A._locatie
    A.render_template = lambda naam, **kw: gevangen.update(kw) or ""
    A._locatie = lambda pad, standaard=None: standaard
    try:
        C.get("/dagen", headers=BEHEER)
    finally:
        A.render_template, A._locatie = echt_render, echt_locatie
    dag = next((d for d in gevangen.get("rijen", []) if d["dag"] == "2026-10-20"), {})
    check("O26 de dagenpagina telt privérijen mee", dag.get("gesprekken") == 3, dag)
    tekst = str(dag.get("personen"))
    check("O26 de dagenpagina noemt geen privénamen", "Familie Proef" not in tekst and "Kees Proef" not in tekst
          and "Jan Proef" in tekst, tekst)


def t_p3_chats_tellen_niet():
    """Codex P3 (fase 2 van de dagvaststelling, 26-10-2026): een WhatsApp-gesprek per dag en een Zoom-chat zijn geen
    gesprek; een beantwoorde oproep wel, een gemiste oproep en een dekkingsrij niet (dubbel_van buiten:)."""
    verse_db("p3")
    zet([FATHOM,
         {"uniek": "whatsapp:" + "a" * 40 + ":2026-10-20", "datum": "2026-10-20", "start": "08:00", "minuten": 0,
          "personen": "Jan Proef", "thema": "12 berichten (5 in, 7 uit), 08:00 tot 18:00", "prive": 1, "bron": "whatsapp",
          "dubbel_van": ""},
         {"uniek": "zoom:chat:kanaal-q:2026-10-20", "datum": "2026-10-20", "bron": "zoom", "dubbel_van": ""},
         {"uniek": "whatsapp-oproep:PROEF1", "datum": "2026-10-20", "start": "11:00", "minuten": 4, "prive": 1,
          "bron": "whatsapp", "dubbel_van": ""},
         {"uniek": "whatsapp-oproep:PROEF2", "datum": "2026-10-20", "start": "12:00", "minuten": 0, "prive": 1,
          "bron": "whatsapp", "dubbel_van": "buiten:gemist"},
         {"uniek": "dekking:whatsapp:2026-10-20", "datum": "2026-10-20", "bron": "dekking", "prive": 1,
          "dubbel_van": "buiten:dekking"},
         {"uniek": "mail:<proef@x>", "datum": "2026-10-20", "minuten": 0, "bron": "mail", "dubbel_van": ""}])
    gevangen = {}
    echt_render, echt_locatie = A.render_template, A._locatie
    A.render_template = lambda naam, **kw: gevangen.update(kw) or ""
    A._locatie = lambda pad, standaard=None: standaard
    try:
        C.get("/dagen", headers=BEHEER)
    finally:
        A.render_template = echt_render
    dag = next((d for d in gevangen.get("rijen", []) if d["dag"] == "2026-10-20"), {})
    check("P3 dagenpagina: Fathom en de beantwoorde oproep tellen, chats, mail (Q8), gemist en dekking niet",
          dag.get("gesprekken") == 2 and dag.get("gesprek_min") == FATHOM["minuten"] + 4, dag)
    try:
        html = C.get("/dag/2026-10-20", headers=BEHEER).get_data(as_text=True)
    finally:
        A._locatie = echt_locatie
    check("P3 dagpagina: twee gesprekken, twee chats en een mail, twee buiten", "2 gesprekken tellen, 3 mails en chats "
          "tellen niet als gesprek, 2 dubbel of buiten" in html, html[-2500:])


def t_p9_teruglezen_van_de_mac():
    """Codex P9 (fase 2): wat De WhatsApp-wacht en De Belwacht schrijven, leest bordstand.py exact terug: dezelfde
    vingerafdruk als de Mac over zijn rij rekent, ook na een tweede upsert, en dubbel_van wordt leeg of buiten:."""
    db = verse_db("p9")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mijnagents-runner",
                                    "koppelingen"))
    import bordstand
    rijen = [{"uniek": "telefoon:U1", "datum": "2026-10-20", "start": "02:30+01:00", "minuten": 3, "personen": "Jan Proef",
              "thema": "telefoon, uitgaand", "prive": 1, "bron": "telefoon", "dubbel_van": ""},
             {"uniek": "telefoon:U2", "datum": "2026-10-20", "start": "09:00", "minuten": 0, "personen": "+32470000099",
              "thema": "telefoon, inkomend, gemist", "prive": 1, "bron": "telefoon", "dubbel_van": "buiten:gemist"},
             {"uniek": "dekking:telefoon:2026-10-20", "datum": "2026-10-20", "start": "", "minuten": 0, "personen": "",
              "thema": "gelezen", "prive": 1, "bron": "dekking", "dubbel_van": "buiten:dekking"}]
    for _ in range(2):
        check("P9 upsert van de Mac", zet(rijen).get_json().get("rijen") == 3)
        terug = bordstand.gesprekken("telefoon", "2026-10-20", "2026-10-20", db)
        check("P9 teruglezen: elke vingerafdruk gelijk",
              {u: x["v"] for u, x in terug.items()} == {r["uniek"]: bordstand.vingerafdruk(r) for r in rijen}, terug)
        check("P9 dubbel_van terug", terug["telefoon:U2"]["d"] == "buiten:gemist" and terug["telefoon:U1"]["d"] == "")
    ts_voor = sqlite3.connect(db).execute("SELECT ts FROM gesprek_log WHERE uniek='telefoon:U1'").fetchone()[0]
    koppel([{"uniek": "telefoon:U1", "dubbel_van": "buiten:vervallen"}])
    ts_na = sqlite3.connect(db).execute("SELECT ts FROM gesprek_log WHERE uniek='telefoon:U1'").fetchone()[0]
    check("W1 een koppeling die iets verandert, zet ts", ts_na > ts_voor, (ts_voor, ts_na))
    koppel([{"uniek": "telefoon:U1", "dubbel_van": "buiten:vervallen"}])
    check("W1 een koppeling die niets verandert, laat ts staan", sqlite3.connect(db).execute(
        "SELECT ts FROM gesprek_log WHERE uniek='telefoon:U1'").fetchone()[0] == ts_na)
    check("P9 vervallen gemarkeerd", bordstand.gesprekken("telefoon", "2026-10-20", "2026-10-20", db)["telefoon:U1"]["d"]
          == "buiten:vervallen")
    zet(rijen[:1])
    check("P9 een terugkerende rij telt weer", bordstand.gesprekken("telefoon", "2026-10-20", "2026-10-20", db)
          ["telefoon:U1"]["d"] == "")
    # Q1: twee oproepen met dezelfde ID krijgen op de Mac twee sleutels (de tweede met haar tijdstip); beide blijven
    dubbel = [dict(rijen[0], uniek="telefoon:ZELFDE"), dict(rijen[0], uniek="telefoon:ZELFDE-814700000", start="03:30")]
    zet(dubbel)
    terug = bordstand.gesprekken("telefoon", "2026-10-20", "2026-10-20", db)
    check("Q1 twee oproepen met dezelfde ID blijven twee rijen", all(terug.get(r["uniek"], {}).get("v")
          == bordstand.vingerafdruk(r) for r in dubbel), terug)


if __name__ == "__main__":
    t_o26_dagenpagina_zonder_privenamen()
    t_p3_chats_tellen_niet()
    t_p9_teruglezen_van_de_mac()
    t01_oude_databank()
    t01_twee_verbindingen()
    t02_upsert_wist_koppeling_niet()
    t03_koppelen_weigert()
    t04_token_en_bron()
    t105_andere_afzender()
    z12_pagina_en_telling()
    print(f"{fout} fout")
    sys.exit(1 if fout else 0)

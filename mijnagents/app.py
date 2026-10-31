#!/usr/bin/env python3
"""mijnagents: Mehdi's eigen agent-besturingscentrum (mijnagents.globaal.be).

Bewust zelfstandig, naar het patroon van agents/ en siyanagents/: een eigen
SQLite in het datavolume, forward-auth ervoor (nginx), en het gedeelde
hartslag-contract zodat agents interoperabel blijven met de rest.

HET VERSCHIL met siyanagents: agents staan hier NIET hardgecodeerd in de code
maar in de tabel `agent`. De generator (mijnagents-runner/nieuwe-agent.py)
voegt een rij toe; dit bord leest de rijen. Een agent toevoegen kost dus geen
code-wijziging en geen herbouw.

Zichtbaarheidsregel (net als de agents-tegel, want de groep `agents` bevat ook
mensen buiten het beheer): gewone kijkers zien actie en reden, geen parameters.
Alleen beheer kan een voorstel openklappen om de volledige inhoud te lezen.
"""
import difflib
import itertools
import json
import re
import os
import sqlite3
import urllib.parse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Flask, abort, g, jsonify, redirect, render_template, request, url_for
from markupsafe import escape

app = Flask(__name__)

DB_PAD = os.environ.get("AGENTS_DB", os.path.join(os.path.dirname(__file__), "mijnagents.db"))
TOKEN = os.environ.get("AGENTS_TOKEN", "")
APP_NAAM = os.environ.get("APP_NAME", "Mijn agents")

# Wie mag beslissen over voorstellen (goedkeuren/weigeren). Zien mag iedereen
# die door de forward-auth komt; beslissen is beheer.
BESLIS_GROEPEN = {"admin", "manager"}

# Stilte-detectie: een hartslag ouder dan dit (minuten) maakt de kaart "stil".
# Ruime marges op een uurlijkse cadans, gelijk aan de agents-tegel.
STILTE_MIN = {"actief": 60, "waakt": 150, "klaar": 1440, "fout": 1440, "rust": 1440}
STILTE_PER_AGENT = {"benamingen-wacht": 45, "mappen-wacht": 45}
STATUS_LABEL = {
    "rust": "in rust", "waakt": "waakt", "actief": "actief",
    "klaar": "klaar", "fout": "fout", "stil": "stil", "onbekend": "niet gekoppeld",
}


# ---------------------------------------------------------------- database ---
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PAD)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.after_request
def _geen_cache(resp):
    # Het bord verandert elke minuut (hartslagen, noden, nieuwe agents). Een
    # telefoon die een oude pagina vasthoudt toont anders een verouderd
    # organogram; daarom nooit bewaren.
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@app.teardown_appcontext
def _sluit(_exc):
    d = g.pop("db", None)
    if d is not None:
        d.close()


# De groep Dagbundelaar op het bord: wie data levert voor het dagboek, De Dagbundelaar zelf en wie het dagboek
# gebruikt om Mehdi werk uit handen te nemen. Een nieuwe agent voor het dagboek komt hier bij, nergens anders.
DAGBUNDELAAR_AGENTS = (
    "dagbundelaar", "mehdi-agent",
    "agenda-wacht", "calendly-wacht", "locatie-wacht", "icloud-wacht",
    "belwacht", "whatsapp-wacht", "communicatie-bundelaar", "fathom-wacht", "plaud-wacht",
    "zoom-wacht", "zoom-archief",
    "mail-mch", "mail-melo", "mail-prive", "mail-info-harc", "mail-hinv",
)


def init_db():
    conn = sqlite3.connect(DB_PAD)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agent (
            naam     TEXT PRIMARY KEY,   -- kort, kleine letters, met koppelteken
            label    TEXT NOT NULL,      -- weergavenaam
            type     TEXT DEFAULT '',    -- groepering op het bord
            rol      TEXT DEFAULT '',    -- een regel: wat hij doet
            mandaat  TEXT DEFAULT '',    -- wat hij doet en voor wie
            mag      TEXT DEFAULT '[]',  -- json-lijst: wat hij zelfstandig mag
            grenzen  TEXT DEFAULT '[]',  -- json-lijst: wat hij nooit doet
            cadans   TEXT DEFAULT '',    -- hoe vaak / wanneer
            tools    TEXT DEFAULT '[]',  -- json-lijst: echte gereedschappen
            eigenaar TEXT DEFAULT 'mehdi',
            actief   INTEGER DEFAULT 1,  -- 0 = uit het bord (gearchiveerd)
            aangemaakt TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS status (
            naam   TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            taak   TEXT DEFAULT '',
            detail TEXT DEFAULT '',
            tokens INTEGER,
            ts     TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS voorstel (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            naam       TEXT NOT NULL,       -- welke agent stelt voor
            actie      TEXT NOT NULL,       -- korte titel
            doel       TEXT DEFAULT '',
            reden      TEXT DEFAULT '',
            parameters TEXT DEFAULT '',     -- json; leeg = louter signaal (nooit uitvoerbaar)
            runbook    TEXT DEFAULT '',     -- naam van een toegestaan runbook (optioneel)
            status     TEXT DEFAULT 'open', -- open | goedgekeurd | geweigerd | uitgevoerd | mislukt
            besluit_door TEXT DEFAULT '',
            besluit_ts   TEXT DEFAULT '',
            bewijs     TEXT DEFAULT '',
            ts         TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS handeling (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            naam   TEXT NOT NULL,
            wat    TEXT NOT NULL,
            ts     TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS logboek (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            naam      TEXT NOT NULL,        -- agent
            onderwerp TEXT DEFAULT '',      -- bv. 'deal 14474 · 2611 Kim Venken'
            stap      TEXT NOT NULL,        -- bron | bevinding | besluit | schrijf | proef | melding | fout
            tekst     TEXT NOT NULL,        -- leesbare regel
            detail    TEXT DEFAULT '',      -- optioneel: langere tekst / json
            ts        TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS logboek_naam_ts ON logboek(naam, ts);
        CREATE TABLE IF NOT EXISTS klaarzet (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            van       TEXT NOT NULL,        -- bron-agent (bv. agenda-wacht)
            voor      TEXT NOT NULL,        -- afdeling of agent die het gebruikt (bv. h-architects, contracten-agent, mehdi)
            soort     TEXT NOT NULL,        -- afspraak | transcript | opname | dagplan | signaal
            sleutel   TEXT DEFAULT '',      -- koppeling: deal_id, projectnummer, datum
            titel     TEXT NOT NULL,
            inhoud    TEXT DEFAULT '',      -- tekst of json
            verwijzing TEXT DEFAULT '',     -- pad in Dropbox, url
            uniek     TEXT DEFAULT '',      -- idempotentiesleutel (bv. fathom:816732165)
            status    TEXT DEFAULT 'klaar', -- klaar | opgepakt | vervallen
            ts        TEXT NOT NULL,
            opgepakt_door TEXT DEFAULT '',
            opgepakt_ts   TEXT DEFAULT ''
        );
        CREATE UNIQUE INDEX IF NOT EXISTS klaarzet_uniek ON klaarzet(uniek) WHERE uniek<>'';
        -- Revisies van een al opgepakt item (nacontrole Plaud v1.1, 12-10-2026): de oude versie, wie ze
        -- oppakte, en of de eerdere verspreiding hersteld is. Alleen voor items die revisie vragen.
        CREATE TABLE IF NOT EXISTS klaarzet_revisie (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            klaarzet_id   INTEGER NOT NULL,
            uniek         TEXT NOT NULL,
            oud_voor      TEXT, oud_titel TEXT, oud_inhoud TEXT, oud_verwijzing TEXT, oud_sleutel TEXT,
            oud_status    TEXT, opgepakt_door TEXT, opgepakt_ts TEXT,
            nieuw_voor    TEXT,
            herstel       TEXT DEFAULT 'te beoordelen: eerdere verspreiding nakijken',
            ts            TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS klaarzet_revisie_uniek ON klaarzet_revisie(uniek);
        CREATE TABLE IF NOT EXISTS nood (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            naam    TEXT NOT NULL,       -- agent
            tekst   TEXT NOT NULL,       -- wat hij nodig heeft of wat niet werkt
            wie     TEXT DEFAULT '',     -- wie het kan oplossen: mehdi | claude-code | collega
            open    INTEGER DEFAULT 1,
            ts      TEXT NOT NULL,
            opgelost_ts TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS gesprek_log (
            uniek     TEXT PRIMARY KEY,   -- bv. fathom:816732165
            datum     TEXT, start TEXT, minuten INTEGER,
            personen  TEXT DEFAULT '', bedrijf TEXT DEFAULT '', afdeling TEXT DEFAULT '',
            thema     TEXT DEFAULT '', project TEXT DEFAULT '', prive INTEGER DEFAULT 0,
            zekerheid TEXT DEFAULT '', waarom TEXT DEFAULT '', archief TEXT DEFAULT '',
            link      TEXT DEFAULT '', opgenomen_door TEXT DEFAULT '', bron TEXT DEFAULT 'fathom',
            ts        TEXT NOT NULL,
            sessie    TEXT DEFAULT '',    -- bij welk gesprek de rij hoort, bv. zoom:meeting:<uuid> (Z10)
            dubbel_van TEXT DEFAULT ''    -- leeg: de rij telt; anders de uniek van de rij die telt, of buiten:<reden>
        );
        CREATE TABLE IF NOT EXISTS afdeling (
            naam         TEXT PRIMARY KEY,   -- sleutel, gelijk aan agent.type
            label        TEXT NOT NULL,
            omschrijving TEXT DEFAULT '',
            volgorde     INTEGER DEFAULT 100
        );
        CREATE TABLE IF NOT EXISTS gesprek (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            aan        TEXT NOT NULL,          -- agentnaam, of 'regisseur' voor de hoofdagent
            van        TEXT NOT NULL,          -- wie het vroeg (gebruikersnaam)
            tekst      TEXT NOT NULL,          -- de vraag of opdracht
            antwoord   TEXT DEFAULT '',        -- het antwoord van de agent
            status     TEXT DEFAULT 'open',    -- open | bezig | beantwoord | mislukt
            detail     TEXT DEFAULT '',        -- wat de agent deed om te antwoorden
            ts         TEXT NOT NULL,
            beantwoord_ts TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS werkwijze_versie (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            naam  TEXT NOT NULL,
            tekst TEXT NOT NULL,
            wie   TEXT DEFAULT '',
            ts    TEXT NOT NULL
        );
        -- WP2b (12-10-2026): een H-A-projectnummer dat in een open of goedgekeurd voorstel staat, is bezet.
        -- De unieke indexen zijn de grendel: twee gelijktijdige voorstellen krijgen nooit hetzelfde nummer,
        -- en één deal houdt nooit twee nummers tegelijk vast. actief volgt de status van het voorstel.
        CREATE TABLE IF NOT EXISTS nummerreservering (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            firma       TEXT NOT NULL,
            reeks       TEXT NOT NULL,
            nummer      TEXT NOT NULL,
            deal_id     TEXT NOT NULL,
            voorstel_id INTEGER NOT NULL,
            actief      INTEGER NOT NULL DEFAULT 1,
            ts          TEXT NOT NULL,
            vrij_ts     TEXT DEFAULT '',
            vrij_reden  TEXT DEFAULT ''
        );
        CREATE UNIQUE INDEX IF NOT EXISTS nummerreservering_nummer ON nummerreservering(firma, nummer) WHERE actief=1;
        CREATE UNIQUE INDEX IF NOT EXISTS nummerreservering_deal ON nummerreservering(firma, deal_id) WHERE actief=1;
        CREATE INDEX IF NOT EXISTS nummerreservering_voorstel ON nummerreservering(voorstel_id);
        """
    )
    # Latere kolommen op agent: de werkwijze (het volledige proces, door Mehdi
    # te bewerken op het bord; de agent leest het elke ronde) en de kennis
    # (wat de agent in zijn laatste ronde als instructie las, door hem gemeld).
    # Vaste afdelingen (idempotent). Nieuwe afdelingen via POST /api/afdeling.
    for naam, label, oms, volg in (
        ("regie", "Regie", "Het overzicht, het gesprek met Mehdi en de voorstellen.", 10),
        ("h-architects", "H-Architects", "Het kantoor: contracten, dossiers, klanten.", 20),
        ("prive", "Privé", "Mehdi zelf: agenda, gegevens van de Mac, persoonlijke dossiers.", 30),
        ("dagbundelaar", "Dagbundelaar", "Alles wat het dagboek van Mehdi voedt, De Dagbundelaar zelf en De Mehdi-agent.", 15),
    ):
        conn.execute("INSERT OR IGNORE INTO afdeling(naam, label, omschrijving, volgorde) VALUES(?,?,?,?)",
                     (naam, label, oms, volg))
    bestaand = {r[1] for r in conn.execute("PRAGMA table_info(agent)")}
    for kolom, definitie in (("werkwijze", "TEXT DEFAULT ''"), ("kennis", "TEXT DEFAULT ''"),
                             ("kennis_ts", "TEXT DEFAULT ''"), ("kennis_bron", "TEXT DEFAULT ''"),
                             ("levert_aan", "TEXT DEFAULT '[]'"), ("draait_op", "TEXT DEFAULT 'VM'"),
                             ("prive", "INTEGER DEFAULT 0")):  # 1 = alleen zichtbaar voor beheer (Mehdi)
        if kolom not in bestaand:
            conn.execute(f"ALTER TABLE agent ADD COLUMN {kolom} {definitie}")
    # Mehdi, 31-10-2026: alle agents van de Dagbundelaar op één plek, niets dubbel. Ze verhuizen naar de groep
    # Dagbundelaar; geen kopie in hun oude groep. Deze lijst is de enige plek waar dat staat.
    conn.execute(f"UPDATE agent SET type='dagbundelaar' WHERE naam IN ({','.join('?' * len(DAGBUNDELAAR_AGENTS))})",
                 DAGBUNDELAAR_AGENTS)
    conn.commit()
    _gesprek_log_kolommen(conn)
    conn.close()


def _gesprek_log_kolommen(conn):
    """Z10 (ontwerp regie-zoom v1.2): de koppelkolommen van de gesprekkentabel. Zonder koppeling telde de tabel elk
    gesprek dat Zoom en Fathom allebei hebben twee keer. Twee gunicorn-werkers kunnen de oude tabel tegelijk zien:
    onder een slot, en daarna de kolommen opnieuw lezen (J5, zoals _mail_tabellen). Verwacht geen open transactie."""
    nieuw = (("sessie", "TEXT DEFAULT ''"), ("dubbel_van", "TEXT DEFAULT ''"))
    kol = {r[1] for r in conn.execute("PRAGMA table_info(gesprek_log)").fetchall()}
    if any(k not in kol for k, _ in nieuw):
        conn.execute("BEGIN IMMEDIATE")
        try:
            kol = {r[1] for r in conn.execute("PRAGMA table_info(gesprek_log)").fetchall()}
            for k, soort in nieuw:
                if k not in kol:
                    conn.execute(f"ALTER TABLE gesprek_log ADD COLUMN {k} {soort}")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    conn.execute("CREATE INDEX IF NOT EXISTS gesprek_log_sessie ON gesprek_log(sessie)")
    conn.commit()


def md(tekst):
    """Markdown naar HTML voor de werkwijze en de kennis (tekst van beheer of
    van het contract-dashboard, dus vertrouwd)."""
    try:
        import markdown
        return markdown.markdown(tekst or "", extensions=["tables", "fenced_code"])
    except Exception:  # noqa: BLE001
        from html import escape
        return "<pre style='white-space:pre-wrap'>" + escape(tekst or "") + "</pre>"


def md_klaargezet(tekst):
    """Markdown die een agent klaarzette naar HTML, voor de pagina van die agent. Niet vertrouwd zoals md(): de tekst komt
    uit bronnen (mail, berichten) via een model. Dus eerst ontsnapt (ruwe HTML wordt tekst), haken als entiteit (geen
    links of afbeeldingen, dus geen javascript:-link), en elke regel blijft een regel (nl2br)."""
    from html import escape
    veilig = escape(tekst or "", quote=False).replace("[", "&#91;").replace("]", "&#93;")
    try:
        import markdown
        return markdown.markdown(veilig, extensions=["nl2br", "sane_lists"])
    except Exception:  # noqa: BLE001
        return "<pre style='white-space:pre-wrap'>" + veilig + "</pre>"


# ------------------------------------------------------------------ helpers ---
def nu():
    return datetime.now(timezone.utc).isoformat()


def groepen():
    # Authentik scheidt groepen met "|" (forward auth); onze eigen tests en oudere
    # koppelingen gebruiken ",". Allebei aanvaarden, anders herkent het bord
    # beheer niet en verdwijnen gespreksvak, werkverslag en bewerken.
    ruw = request.headers.get("X-authentik-groups", "")
    return {x.strip() for x in re.split(r"[|,]", ruw) if x.strip()}


def gebruiker():
    return request.headers.get("X-authentik-username", "") or "?"


def mag_beslissen():
    return bool(groepen() & BESLIS_GROEPEN)


# De groep mail (Mehdi, 20-10-2026: "kunnen we dit ook delen met Angela en Shaniel"; gekozen: kijken en mee afhandelen):
# wie erin zit, opent /mail en klikt er mee (Opgelost, Doorgezet, Ruis, Helemaal weg; zijn naam komt erbij), maar ziet
# de rest van het bord niet. Lid maken gebeurt in Authentik (scripts/mail-groep-vullen.py), niet hier.
MAIL_GROEP = "mail"


def mag_mail():
    return bool(groepen() & (BESLIS_GROEPEN | {MAIL_GROEP}))


@app.before_request
def alleen_mail():
    """Wie alleen via de groep mail binnenkomt, ziet alleen de pagina Mail; de rest van het bord blijft dicht."""
    g = groepen()
    if MAIL_GROEP in g and not g & (BESLIS_GROEPEN | {"agents"}):
        pad = request.path
        if not (pad == "/mail" or pad.startswith("/mail/") or pad.startswith("/static/")):
            return redirect(url_for("mail_pagina"))
    return None


def leeftijd_min(ts):
    try:
        t = datetime.fromisoformat(ts)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds() / 60.0
    except Exception:
        return None


def toestand_met_cadans(naam, cadans, status, leeftijd):
    """Een afgeronde ronde op verzoek veroudert niet; fouten en lopend werk wel."""
    toestand = status if status in STILTE_MIN else "waakt"
    if cadans == "op verzoek" and status in ("klaar", "waakt"):
        return toestand
    drempel = STILTE_PER_AGENT.get(naam, STILTE_MIN.get(toestand, 150))
    return "stil" if leeftijd is not None and leeftijd > drempel else toestand


def _lijst(val):
    try:
        v = json.loads(val or "[]")
        return v if isinstance(v, list) else [str(v)]
    except Exception:
        return [s for s in (val or "").split("\n") if s.strip()]


def zichtbaar_sql():
    """Privé-agents (bv. het locatielogboek) bestaan alleen voor beheer."""
    return "" if mag_beslissen() else " AND prive=0"


def kaarten():
    conn = db()
    rijen = conn.execute(f"SELECT * FROM agent WHERE actief=1{zichtbaar_sql()} ORDER BY type, label").fetchall()
    st = {r["naam"]: r for r in conn.execute("SELECT * FROM status").fetchall()}
    open_per = {}
    for r in conn.execute(
        "SELECT naam, COUNT(*) n FROM voorstel WHERE status='open' GROUP BY naam"
    ).fetchall():
        open_per[r["naam"]] = r["n"]
    nood_per = {}
    for r in conn.execute("SELECT naam, tekst, wie FROM nood WHERE open=1 ORDER BY id").fetchall():
        nood_per.setdefault(r["naam"], []).append(dict(r))

    uit = []
    for a in rijen:
        s = st.get(a["naam"])
        if not s:
            toestand, taak, detail, ts, leeftijd = "onbekend", "", "", None, None
        else:
            leeftijd = leeftijd_min(s["ts"])
            toestand = toestand_met_cadans(a["naam"], a["cadans"], s["status"], leeftijd)
            taak, detail, ts = s["taak"], s["detail"], s["ts"]
        uit.append(
            {
                "naam": a["naam"], "label": a["label"], "type": a["type"] or "overig",
                "rol": a["rol"], "eigenaar": a["eigenaar"],
                "toestand": toestand, "toestand_label": STATUS_LABEL.get(toestand, toestand),
                "taak": taak, "detail": detail, "ts": ts,
                "leeftijd_min": None if leeftijd is None else int(leeftijd),
                "open_voorstellen": open_per.get(a["naam"], 0),
                "nood": nood_per.get(a["naam"], []),
            }
        )
    return uit


@app.route("/api/nood")
def api_nood():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    rijen = db().execute("SELECT * FROM nood WHERE open=1 ORDER BY naam, id").fetchall()
    return jsonify(nood=[dict(r) for r in rijen])


# Een voorstel kan een complete werkwijze bevatten. De browser krijgt daarvan maximaal
# 60.000 tekens per veld en 400 diffregels, met een zichtbare melding bij afkappen.
VOORSTEL_TEKST_MAX = 60_000
VOORSTEL_DIFF_REGELS_MAX = 400
VOORSTEL_DIFF_INVOER_REGELS_MAX = 5_000
VOORSTEL_JSON_MAX = 1_000_000
VOORSTEL_PARAMETERS_MAX = 100


def _voorstel_tekst(waarde):
    tekst = waarde if isinstance(waarde, str) else json.dumps(waarde, ensure_ascii=False, indent=2)
    return tekst[:VOORSTEL_TEKST_MAX], len(tekst) > VOORSTEL_TEKST_MAX


def _voorstel_waarde(naam, waarde):
    tekst, afgekapt = _voorstel_tekst(waarde)
    return {"naam": str(naam)[:200], "tekst": tekst,
            "lang": isinstance(waarde, (dict, list)) or "\n" in tekst or len(tekst) > 120,
            "afgekapt": afgekapt}


def _voorstel_leesgegevens(voorstel, conn):
    """Maak veilige platte tekst voor het beheer. Jinja escapt alle velden bij het tonen."""
    uit = {"is_werkwijze": False, "parameters": [], "melding": ""}
    ruw = voorstel["parameters"] or ""
    if not ruw:
        return uit
    if len(ruw) > VOORSTEL_JSON_MAX:
        uit["parameters"] = [_voorstel_waarde("Parameters", ruw)]
        uit["melding"] = "Parameters zijn te groot om volledig te verwerken; alleen het begin wordt getoond."
        return uit
    try:
        parameters = json.loads(ruw)
    except (ValueError, RecursionError):
        uit["parameters"] = [_voorstel_waarde("Parameters", ruw)]
        uit["melding"] = "Parameters zijn geen geldige JSON; de opgeslagen tekst wordt getoond."
        return uit
    if not isinstance(parameters, dict):
        uit["parameters"] = [_voorstel_waarde("Parameters", parameters)]
        return uit

    if voorstel["runbook"] == "werkwijze-bijwerken":
        uit["is_werkwijze"] = True
        uit["agent"] = _voorstel_waarde("Agent", parameters.get("agent", "Niet opgegeven"))
        uit["mandaat"] = _voorstel_waarde("Mandaat", parameters.get("mandaat", "Niet opgegeven"))
        uit["werkwijze"] = _voorstel_waarde("Voorgestelde werkwijze", parameters.get("werkwijze", "Niet opgegeven"))
        agent = parameters.get("agent")
        huidig = (conn.execute("SELECT werkwijze FROM agent WHERE naam=?", (agent,)).fetchone()
                  if isinstance(agent, str) else None)
        huidige_tekst = huidig["werkwijze"] if huidig else ""
        nieuwe_tekst = parameters.get("werkwijze")
        if not huidige_tekst:
            uit["verschil_melding"] = "Geen huidige werkwijze op het bord voor deze agent."
        elif not isinstance(nieuwe_tekst, str):
            uit["verschil_melding"] = "Geen tekstuele werkwijze in het voorstel; een verschil is niet beschikbaar."
        else:
            oud, oud_afgekapt = _voorstel_tekst(huidige_tekst)
            nieuw = uit["werkwijze"]["tekst"]
            oude_regels, nieuwe_regels = oud.splitlines(), nieuw.splitlines()
            uit["invoer_afgekapt"] = (len(oude_regels) > VOORSTEL_DIFF_INVOER_REGELS_MAX
                                      or len(nieuwe_regels) > VOORSTEL_DIFF_INVOER_REGELS_MAX)
            regels = difflib.unified_diff(oude_regels[:VOORSTEL_DIFF_INVOER_REGELS_MAX],
                                         nieuwe_regels[:VOORSTEL_DIFF_INVOER_REGELS_MAX],
                                         fromfile="Huidige werkwijze op het bord",
                                         tofile="Voorgestelde werkwijze", n=3, lineterm="")
            verschil = list(itertools.islice(regels, VOORSTEL_DIFF_REGELS_MAX + 1))
            uit["verschil"] = "\n".join(verschil[:VOORSTEL_DIFF_REGELS_MAX])
            uit["verschil_melding"] = (("Geen verschillen in de eerste 5.000 regels."
                                         if uit["invoer_afgekapt"] else "Geen verschillen met de huidige werkwijze.")
                                        if not verschil else "")
            uit["verschil_afgekapt"] = len(verschil) > VOORSTEL_DIFF_REGELS_MAX
            uit["huidig_afgekapt"] = oud_afgekapt
        overig = [(naam, waarde) for naam, waarde in parameters.items()
                  if naam not in {"agent", "mandaat", "werkwijze"}]
    else:
        overig = list(parameters.items())
    uit["parameters"] = [_voorstel_waarde(naam, waarde)
                         for naam, waarde in overig[:VOORSTEL_PARAMETERS_MAX]]
    if len(overig) > VOORSTEL_PARAMETERS_MAX:
        uit["melding"] = f"Alleen de eerste {VOORSTEL_PARAMETERS_MAX} parameters worden getoond."
    return uit


# ------------------------------------------------------------------- routes ---
@app.route("/naamstructuur")
def naamstructuur_pagina():
    """Volledig naam-/structuurbewijs, alleen bestaand bordbeheer."""
    if not mag_beslissen():
        abort(403)
    data = os.path.join(os.path.dirname(DB_PAD), "naamstructuur")
    samenvatting = {}
    try:
        with open(os.path.join(data, "overzicht.json"), encoding="utf-8") as f:
            samenvatting = json.load(f)
    except (OSError, ValueError):
        pass
    stand = request.args.get("status", "open")
    if stand not in ("open", "opgelost in bron", "bron niet meer aanwezig", "alle"):
        abort(400)
    try:
        pagina = max(1, int(request.args.get("pagina", "1")))
    except ValueError:
        abort(400)
    zoeken = request.args.get("q", "").strip()[:200]
    punten, totaal = [], 0
    indexpad = os.path.join(data, "index.sqlite3")
    if os.path.isfile(indexpad):
        conn = sqlite3.connect(f"file:{indexpad}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            where, waarden = [], []
            if stand != "alle":
                where.append("status=?")
                waarden.append(stand)
            actieve_scopes = [s["id"] for s in samenvatting.get("scopes", []) if s.get("ingesteld", True)]
            if stand == "open" and actieve_scopes:
                where.append("scope IN (" + ",".join("?" for _ in actieve_scopes) + ")")
                waarden.extend(actieve_scopes)
            if zoeken:
                where.append("(pad LIKE ? OR firma LIKE ? OR regel LIKE ? OR identiteit LIKE ?)")
                waarden.extend(["%" + zoeken + "%"] * 4)
            filter_sql = " WHERE " + " AND ".join(where) if where else ""
            totaal = conn.execute("SELECT count(*) FROM bevinding" + filter_sql, waarden).fetchone()[0]
            punten = [dict(r) for r in conn.execute("SELECT * FROM bevinding" + filter_sql +
                      " ORDER BY scope,identiteit,agent,regel LIMIT 100 OFFSET ?", waarden + [(pagina - 1) * 100])]
        finally:
            conn.close()
    return render_template("naamstructuur.html", samenvatting=samenvatting, punten=punten,
                           totaal=totaal, pagina=pagina, stand=stand, zoeken=zoeken,
                           app_naam=APP_NAAM, gebruiker=gebruiker())


@app.route("/")
def bord():
    beheer = mag_beslissen()
    ks = kaarten()
    afd = {r["naam"]: dict(r) for r in db().execute("SELECT * FROM afdeling").fetchall()}
    groepering = {}
    for k in ks:
        groepering.setdefault(k["type"], []).append(k)
    # Afdelingen in vaste volgorde, ook als ze (nog) geen agent hebben; onbekende types achteraan.
    volgorde = sorted(set(list(afd) + list(groepering)),
                      key=lambda n: (afd.get(n, {}).get("volgorde", 999), n))
    # De oude subgroep Communicatie is sinds 31-10-2026 leeg (alles zit in Dagbundelaar): leeg niet meer tonen.
    groepering = {n: groepering.get(n, []) for n in volgorde if n != "prive-communicatie" or groepering.get(n)}
    volgorde = list(groepering)
    afdelingen = {n: afd.get(n, {"naam": n, "label": n, "omschrijving": ""}) for n in volgorde}
    open_voorstellen = db().execute(
        "SELECT v.*, a.label FROM voorstel v LEFT JOIN agent a ON a.naam=v.naam "
        "WHERE v.status='open' ORDER BY v.id DESC"
    ).fetchall()
    voorstel_details = ({v["id"]: _voorstel_leesgegevens(v, db()) for v in open_voorstellen}
                        if beheer else {})
    return render_template(
        "board.html", app_naam=APP_NAAM, groepen=groepering, aantal=len(ks),
        voorstellen=open_voorstellen, voorstel_details=voorstel_details, mag_beslissen=beheer,
        nummerconflicten=nummerconflicten_op_bord(db()),
        gebruiker=gebruiker(),
        gesprekken=gesprekken_voor("regisseur", 12) if beheer else [],
        regisseur_html=md, afdelingen=afdelingen,
    )


# --- klaargezet: bron-agents (Privé) zetten iets klaar; afdelingsagents pakken het op.
# M6 (ontwerp regie-zoom v1.2): een uniek hoort bij de agent die het item aanmaakte. Een andere afzender overschrijft
# het niet, zodat bijvoorbeeld het ochtendbericht van De Regisseur niet stil door een andere agent vervangen wordt.
# Uitzondering, gemeten op 21-10-2026: de Mac-mailwacht (mijnagents-runner/mac/mail_wacht.py) draait per postvak met een
# eigen naam en zet een mail van hoog belang klaar als mailsignaal:<Message-ID>. Komt dezelfde mail in twee postvakken
# binnen, dan schrijven twee wachten legitiem op dezelfde uniek; die blijven werken zoals voordien.
KLAARZET_GEDEELD = ("mailsignaal:",)


@app.route("/api/klaarzet", methods=["POST"])
def api_klaarzet():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    items = p.get("items") if isinstance(p.get("items"), list) else [p]
    conn = db()
    nieuw, bestaand, bijgewerkt, herzien, zakelijk_herzien = 0, 0, 0, 0, 0
    andere_afzender = []
    for it in items:
        if not (it.get("van") and it.get("voor") and it.get("soort") and it.get("titel")):
            continue
        uniek = (it.get("uniek") or "")[:200]
        inhoud = it.get("inhoud")
        if not isinstance(inhoud, str):
            inhoud = json.dumps(inhoud, ensure_ascii=False)
        oud = conn.execute("SELECT id, van, voor, titel, inhoud, verwijzing, status, sleutel, opgepakt_door, opgepakt_ts FROM klaarzet WHERE uniek=?",
                           (uniek,)).fetchone() if uniek else None
        if oud and oud["van"] != it["van"] and not uniek.startswith(KLAARZET_GEDEELD):
            andere_afzender.append({"uniek": uniek, "van": it["van"], "bestaande_van": oud["van"]})
            continue
        anders = oud is not None and (oud["voor"], oud["titel"], oud["inhoud"], oud["verwijzing"] or "") != \
            (it["voor"], it["titel"][:300], inhoud[:60000], (it.get("verwijzing") or "")[:500])
        if oud and anders and oud["status"] != "klaar" and it.get("revisie"):
            # Nacontrole Plaud v1.1 (P1-5): een al opgepakt item kreeg een nieuwe beoordeling (bv. privé of
            # conflict). Niet stil negeren: oude versie vastleggen, nieuwe inhoud zichtbaar maken (status klaar),
            # en de eerdere verspreiding markeren voor gecontroleerd herstel.
            conn.execute("INSERT INTO klaarzet_revisie(klaarzet_id, uniek, oud_voor, oud_titel, oud_inhoud, oud_verwijzing, oud_sleutel, "
                         "oud_status, opgepakt_door, opgepakt_ts, nieuw_voor, ts) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                         (oud["id"], uniek, oud["voor"], oud["titel"], oud["inhoud"], oud["verwijzing"], oud["sleutel"], oud["status"],
                          oud["opgepakt_door"], oud["opgepakt_ts"], it["voor"], nu()))
            conn.execute("UPDATE klaarzet SET voor=?, titel=?, inhoud=?, verwijzing=?, sleutel=?, status='klaar', opgepakt_door='', "
                         "opgepakt_ts='' WHERE id=?",
                         (it["voor"], it["titel"][:300], inhoud[:60000], (it.get("verwijzing") or "")[:500],
                          str(it.get("sleutel") or "")[:120], oud["id"]))
            herzien += 1
            zakelijk_herzien += 0 if oud["voor"] == "mehdi" else 1
            continue
        if oud and anders and oud["status"] != "klaar" and it.get("vervang") and it["soort"] == "communicatie" \
                and it["van"] == "communicatie-bundelaar":
            # De Communicatiebundelaar (Codex CB04 en CB12, 26-10-2026): ook een opgepakt item volgt de bron, zonder kopie
            # in klaarzet_revisie, want de oude inhoud kan een naam dragen die intussen privé werd. Alleen voor haar
            # dagitems: bij een ander item wist het de oppakhistorie zonder spoor (controle 5).
            conn.execute("UPDATE klaarzet SET voor=?, titel=?, inhoud=?, verwijzing=?, sleutel=?, status='klaar', opgepakt_door='', "
                         "opgepakt_ts='' WHERE id=?",
                         (it["voor"], it["titel"][:300], inhoud[:60000], (it.get("verwijzing") or "")[:500],
                          str(it.get("sleutel") or "")[:120], oud["id"]))
            bijgewerkt += 1
            continue
        if oud:
            # Les van 12-09-2026: een item dat nog niet opgepakt is, volgt de bron. Toen de Agendawacht TKN leerde
            # herkennen, bleef de afspraak van Britt Verboven bij h-architects staan omdat de bak nooit bijwerkte.
            if oud["status"] == "klaar" and (oud["voor"], oud["titel"], oud["inhoud"], oud["verwijzing"] or "") != \
                    (it["voor"], it["titel"][:300], inhoud[:60000], (it.get("verwijzing") or "")[:500]):
                conn.execute("UPDATE klaarzet SET voor=?, titel=?, inhoud=?, verwijzing=?, sleutel=? WHERE id=?",
                             (it["voor"], it["titel"][:300], inhoud[:60000], (it.get("verwijzing") or "")[:500],
                              str(it.get("sleutel") or "")[:120], oud["id"]))
                bijgewerkt += 1
            else:
                bestaand += 1
            continue
        conn.execute(
            "INSERT INTO klaarzet(van, voor, soort, sleutel, titel, inhoud, verwijzing, uniek, ts) VALUES(?,?,?,?,?,?,?,?,?)",
            (it["van"], it["voor"], it["soort"][:40], str(it.get("sleutel") or "")[:120], it["titel"][:300],
             inhoud[:60000], (it.get("verwijzing") or "")[:500], uniek, nu()))
        nieuw += 1
    conn.commit()
    if andere_afzender:
        # M6: het geweigerde item is niet geschreven, de andere items van de oproep wel; een oude rij van een agent
        # die ooit anders heette, houdt zo niet al zijn werk tegen. De afzender krijgt een fout die hij niet kan missen
        # (409 breekt zijn ronde, zodat N11 en De Normwacht het zien), met wat er wel en niet geschreven is.
        eerste = andere_afzender[0]
        return jsonify(ok=False, nieuw=nieuw, bestaand=bestaand, bijgewerkt=bijgewerkt, herzien=herzien,
                       zakelijk_herzien=zakelijk_herzien, geweigerd=andere_afzender,
                       fout=f"uniek {eerste['uniek']} hoort bij {eerste['bestaande_van']}, niet bij {eerste['van']}; "
                            "een andere afzender overschrijft een klaargezet item niet (dat item is niet geschreven)"), 409
    return jsonify(ok=True, nieuw=nieuw, bestaand=bestaand, bijgewerkt=bijgewerkt, herzien=herzien, zakelijk_herzien=zakelijk_herzien)


@app.route("/api/klaarzet")
def api_klaarzet_lezen():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    voor = request.args.get("voor")
    sleutel = request.args.get("sleutel")
    status = request.args.get("status", "klaar")
    q, a = "SELECT * FROM klaarzet WHERE 1=1", []
    if voor:
        q += " AND (voor=? OR voor=?)"; a += [voor, request.args.get("afdeling") or voor]
    if sleutel:
        q += " AND sleutel=?"; a.append(sleutel)
    if request.args.get("uniek"):
        q += " AND uniek=?"; a.append(request.args["uniek"])
    if request.args.get("soort"):
        q += " AND soort=?"; a.append(request.args["soort"])
    if status != "alle":
        q += " AND status=?"; a.append(status)
    # Terugbladeren: tot_id geeft de items met een kleiner id (de werfvoorbereider las tot 18-10-2026 alleen de
    # laatste 500 van de hele bak, zodat de afspraak van een bezoek van een maand geleden er al uit viel).
    if (request.args.get("tot_id") or "").isdigit():
        q += " AND id<?"; a.append(int(request.args["tot_id"]))
    q += " ORDER BY id DESC LIMIT ?"; a.append(min(int(request.args.get("n", 100)), 500))
    return jsonify(items=[dict(r) for r in db().execute(q, a).fetchall()])


@app.route("/api/klaarzet/revisies")
def api_klaarzet_revisies():
    """Revisies van al opgepakte items, met herstelstatus (nacontrole Plaud v1.1)."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    q, a = "SELECT * FROM klaarzet_revisie WHERE 1=1", []
    if request.args.get("uniek"):
        q += " AND uniek=?"; a.append(request.args["uniek"])
    q += " ORDER BY id DESC LIMIT 200"
    return jsonify(revisies=[dict(r) for r in db().execute(q, a).fetchall()])


@app.route("/api/klaarzet/<int:kid>/opgepakt", methods=["POST"])
def api_klaarzet_opgepakt(kid):
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    db().execute("UPDATE klaarzet SET status='opgepakt', opgepakt_door=?, opgepakt_ts=? WHERE id=?",
                 ((p.get("door") or "")[:80], nu(), kid))
    db().commit()
    return jsonify(ok=True)


# --- gesprekkentabel: het "Excel-achtige" logboek van gesprekken (Fathom, later Plaud,
#     telefoon). Alleen beheer ziet het; privé-rijen zijn er, maar alleen voor beheer.
@app.route("/api/gesprekken", methods=["POST"])
def api_gesprekken_zetten():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    conn = db()
    n, zonder_bron = 0, 0
    for r in p.get("rijen") or []:
        if not r.get("uniek"):
            continue
        # De standaard fathom blijft voor oude afzenders, maar wordt geteld: een vergeten bron is zo zichtbaar (Z11, Z13).
        zonder_bron += 0 if r.get("bron") else 1
        conn.execute(
            "INSERT INTO gesprek_log(uniek,datum,start,minuten,personen,bedrijf,afdeling,thema,project,prive,zekerheid,waarom,archief,link,opgenomen_door,bron,ts) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(uniek) DO UPDATE SET datum=excluded.datum, start=excluded.start, minuten=excluded.minuten, "
            "personen=excluded.personen, bedrijf=excluded.bedrijf, afdeling=excluded.afdeling, thema=excluded.thema, project=excluded.project, prive=excluded.prive, "
            "zekerheid=excluded.zekerheid, waarom=excluded.waarom, archief=excluded.archief, link=excluded.link, opgenomen_door=excluded.opgenomen_door, ts=excluded.ts",
            (r["uniek"], r.get("datum", ""), r.get("start", ""), int(r.get("minuten") or 0), r.get("personen", ""), r.get("bedrijf", ""),
             r.get("afdeling", ""), r.get("thema", ""), r.get("project", ""), 1 if r.get("prive") else 0, r.get("zekerheid", ""),
             r.get("waarom", ""), r.get("archief", ""), r.get("link", ""), r.get("opgenomen_door", ""), r.get("bron", "fathom"), nu()))
        # Z11: sessie en dubbel_van alleen als ze meekomen. Zonder die sleutels blijven ze staan, zodat de upsert van
        # De Fathomwacht een koppeling van De Zoomwacht nooit wist.
        koppel = {k: str(r.get(k) or "")[:200] for k in ("sessie", "dubbel_van") if k in r}
        if koppel:
            conn.execute(f"UPDATE gesprek_log SET {', '.join(k + '=?' for k in koppel)} WHERE uniek=?", (*koppel.values(), r["uniek"]))
        n += 1
    conn.commit()
    return jsonify(ok=True, rijen=n, zonder_bron=zonder_bron)


# Een gesprek is een rij van een gespreksbron die geen chat is (D7 en E1, ontwerp dagvaststelling; Codex P3 en Q8 bij
# fase 2): een mail, een Zoom-chat of een WhatsApp-gesprek per dag (whatsapp:<sha1 jid>:<dag>) telt niet; een
# WhatsApp-oproep (whatsapp-oproep:) en een telefoonoproep wel. Zoals koppelingen/dagvaststelling.soort.
GESPREKSBRONNEN = ("zoom", "fathom", "plaud", "whatsapp", "telefoon")
CHAT_VOORVOEGSELS = ("zoom:chat:", "whatsapp:")


def telt_als_gesprek(rij):
    return (str(rij["bron"] or "") in GESPREKSBRONNEN
            and not str(rij["uniek"] or "").startswith(CHAT_VOORVOEGSELS))


# Een dubbel_van die met buiten: begint, is een merkteken en geen verwijzing naar een rij: de rij telt niet voor Mehdi,
# bijvoorbeeld een Fathom-opname van een ander account uit een andere ruimte (buiten:andere-ruimte, J10).
GESPREK_BUITEN = "buiten:"


@app.route("/api/gesprekken/koppel", methods=["POST"])
def api_gesprekken_koppel():
    """Z11: koppelingen op bestaande rijen zetten, zonder hun andere velden te raken. Invoer {koppelingen: [{uniek,
    sessie, dubbel_van}]}; elk veld dat meekomt wordt gezet, een veld dat ontbreekt blijft staan. Maakt nooit een rij
    aan. Weigert een dubbel_van gelijk aan de eigen uniek, een doel dat niet bestaat en een doel dat zelf dubbel_van
    heeft (dan telt niets meer). Eerst de koppelingen zonder doel (ook het wissen van dubbel_van), dan die met een
    doel, zodat een nieuwe leidende rij in dezelfde oproep eerst vrijkomt. Antwoord {gezet: [uniek], onbekend: [uniek],
    geweigerd: [{uniek, reden}]}. Teruglezen doet de agent zelf, langs bord.db_lees (L32)."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    lijst = p.get("koppelingen")
    if not isinstance(lijst, list):
        return jsonify(fout="koppelingen (een lijst) vereist"), 400
    conn = db()
    gezet, onbekend, geweigerd = [], [], []
    goed = [k for k in lijst if isinstance(k, dict) and k.get("uniek")]
    geweigerd += [{"uniek": "", "reden": "koppeling zonder uniek"} for k in lijst if not (isinstance(k, dict) and k.get("uniek"))]
    for k in sorted(goed, key=lambda k: bool(k.get("dubbel_van"))):
        uniek = str(k["uniek"])[:200]
        huidig = conn.execute("SELECT COALESCE(sessie, '') AS sessie, COALESCE(dubbel_van, '') AS dubbel_van "
                              "FROM gesprek_log WHERE uniek=?", (uniek,)).fetchone()
        if not huidig:
            onbekend.append(uniek)
            continue
        velden = {v: str(k.get(v) or "")[:200] for v in ("sessie", "dubbel_van") if v in k}
        if not velden:
            geweigerd.append({"uniek": uniek, "reden": "geen sessie of dubbel_van"})
            continue
        doel = velden.get("dubbel_van")
        if doel == uniek:
            geweigerd.append({"uniek": uniek, "reden": "dubbel_van verwijst naar de rij zelf"})
            continue
        if doel and not doel.startswith(GESPREK_BUITEN):
            rij = conn.execute("SELECT dubbel_van FROM gesprek_log WHERE uniek=?", (doel,)).fetchone()
            if not rij:
                geweigerd.append({"uniek": uniek, "reden": f"doel {doel} bestaat niet"})
                continue
            if rij["dubbel_van"]:
                geweigerd.append({"uniek": uniek, "reden": f"doel {doel} is zelf een dubbel"})
                continue
        # Codex W1 (fase 2 van de dagvaststelling): een koppeling die iets verandert, is een wijziging van de rij en zet
        # ts, zoals een upsert; zo ziet de inhaalbeurt van De Dagbundelaar ook een dekking die vervallen werd
        if any(huidig[v] != w for v, w in velden.items()):
            conn.execute(f"UPDATE gesprek_log SET {', '.join(v + '=?' for v in velden)}, ts=? WHERE uniek=?",
                         (*velden.values(), nu(), uniek))
        gezet.append(uniek)
    conn.commit()
    return jsonify(ok=True, gezet=gezet, onbekend=onbekend, geweigerd=geweigerd)


@app.route("/gesprekken")
def gesprekken_pagina():
    if not mag_beslissen():
        abort(403)
    rijen = db().execute("SELECT * FROM gesprek_log ORDER BY datum DESC, start DESC LIMIT 2000").fetchall()
    return render_template("gesprekken.html", app_naam=APP_NAAM, rijen=rijen)


# --- mail: het dashboard van de mailwachten. Mehdi, 25-09-2026: "een dashboard dat we de belangrijke zaken van
#     daar kunnen volgen"; 26-09-2026: "ik wil zien hoeveel mails zijn binnengekomen, hoeveel belangrijk, hoeveel
#     spam, hoeveel reclame, en ik wil de mails opschonen". Elke mailwacht geeft elk beoordeeld bericht door
#     (/api/mail, tabel mailbericht); Mehdi beslist per afzender (tabel mailregel: belangrijk, ruis, opruimen, houden),
#     en de wachten lezen die beslissingen elke ronde (/api/mailregels).
#     Een bron voor wat openstaat (driehoeksoverleg 19-10-2026, 3-0). Tot dan telden de wachten (51), De Mailregisseur
#     (57, de klaarzet-items) en de kolom lijst (17, die mailinglijst betekent) elk iets anders, en haalde de
#     Dagbundelaar elke nacht opvolgpunten weg die niemand had gezien. Nu staat per bericht in mailbericht de opvolging
#     van de wacht (open, onzeker, beantwoord, doorgezet, wacht, verlopen, geen) en, apart, het besluit van Mehdi
#     (afgehandeld, doorgezet, ruis), dat een wacht nooit overschrijft. Wat openstaat, telt alleen _mail_open: /mail,
#     De Mailregisseur en zijn 08:00-bericht (/api/mail/open) en het werkverslag van elke wacht (antwoord op /api/mail).
#     Alleen beheer en de groep mail (MAIL_GROEP, sinds 20-10-2026): afzenders en onderwerpen zijn inhoud.
MAIL_SOORT = {"hoog": (0, "Belangrijk"), "actie": (1, "Automatisch, met gevolg"), "midden": (2, "Gewone mail")}
# Volgorde, naam en kleur per soort in de cijfers; de ruis staat achteraan, in grijzen.
MAIL_SOORTEN = [("hoog", "Belangrijk", "var(--kritiek)"), ("actie", "Met gevolg", "var(--let)"),
                ("midden", "Gewone mail", "#56708f"), ("melding", "Melding", "#9aa1ad"),
                ("koud", "Onbekend", "#c3bdb4"), ("rommel", "Reclame en ruis", "#ddd6cc"),
                ("verdacht", "Verdacht", "#6b2a2a")]
MAIL_RUIS = ("melding", "koud", "rommel", "verdacht")
MAIL_ACTIES = {"belangrijk": "Belangrijk", "ruis": "Ruis (tellen, niet tonen)", "opruimen": "Opruimen",
               "houden": "Nooit automatisch opruimen", "uitschrijven": "Helemaal weg (uitschrijven en opruimen)"}
# Opgevolgd tot opgelost (Mehdi, 20-10-2026: "er moet een systeem zijn dat ik weet dat een mail opgevolgd wordt tot het
# volledig gedaan/opgelost is"; gekozen: "pas weg na Opgelost"). Niets verdwijnt nog vanzelf: een antwoord of doorsturen
# zet een opvolgpunt op Loopt (MAIL_LOOPT), een automatisch bericht met gevolg dat ouder is dan 7 dagen (verlopen) blijft
# open, en weg is het pas na een klik op Opgelost (besluit 'afgehandeld') of Ruis. Alleen wat niet meer in het postvak
# staat (verdwenen) sluit zonder klik, en dat staat bij Afgesloten.
MAIL_OPEN = ("open", "onzeker", "verlopen")  # opvolging van de wacht die openstaat, zolang Mehdi niets besliste
MAIL_LOOPT = ("beantwoord", "doorgezet")     # er is gereageerd, maar niemand zei nog dat het opgelost is
MAIL_OPVOLG = ("hoog", "midden", "actie")    # de soorten die opgevolgd worden
MAIL_VAST = 5                                # werkdagen zonder beweging: een punt dat loopt, is vastgelopen
MAIL_BESLUITEN = ("afgehandeld", "doorgezet", "ruis", "open")   # open: Toch open, ook als de wacht het afsloot
MAIL_KLIK = {"afgehandeld": "Opgelost", "doorgezet": "Doorgezet", "ruis": "Ruis", "open": "Toch open", "terug": "Teruggezet",
             "houden": "Niet opruimen", "weg": "Helemaal weg"}
MAIL_PERIODES = {"vandaag": ("Vandaag", 0), "7": ("7 dagen", 6), "30": ("30 dagen", 29)}
# De focus (Mehdi, 20-10-2026: "we focusen nu op mch, mehdichegini@hotmail.com, melodie"): /mail toont standaard deze
# drie postvakken; ?postvak=alle toont alles. De Mailregisseur leest dezelfde lijst via /api/mail/stand (test_mail.py).
MAIL_FOCUS = ("mch@h-architects.be", "mehdichegini@hotmail.com", "melodiebvba@gmail.com")
# Een regel op een heel domein kan hier niet: gratis maildiensten (dan raak je iedereen) en de eigen groep.
MAIL_GEEN_DOMEIN = ("gmail.com", "googlemail.com", "hotmail.com", "hotmail.be", "outlook.com", "outlook.be", "live.com",
                    "live.be", "yahoo.com", "icloud.com", "me.com", "telenet.be", "skynet.be", "proximus.be",
                    "h-architects.be", "unabo.be", "harmoniebouw.be", "tkn-buro.be", "energie-efficient.be", "h-invest.be",
                    "globaal.be", "elevaitnv.com", "hdssr.com", "contrax.be", "zidiconstruct.be")
BRUSSEL = ZoneInfo("Europe/Brussels")


def _brussel(ts, dag=False):
    """Een tijdstip in Brusselse tijd, '25-09 19:52'; met dag=True 'vr 25-09 19:52'."""
    try:
        t = datetime.fromisoformat(ts)
        t = (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(BRUSSEL)
    except (TypeError, ValueError):
        return ""
    return (("ma di wo do vr za zo".split()[t.weekday()] + " ") if dag else "") + t.strftime("%d-%m %H:%M")


def _werkdagen_sinds(ts, vandaag=None):
    """Werkdagen (ma-vr) na de dag van ts, tot vandaag (Brusselse tijd); None als ts onleesbaar is."""
    try:
        t = datetime.fromisoformat(ts)
        d = (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(BRUSSEL).date()
    except (TypeError, ValueError):
        return None
    vandaag, n = vandaag or datetime.now(BRUSSEL).date(), 0
    while d < vandaag:
        d += timedelta(days=1)
        n += d.weekday() < 5
    return n


def _mail_tabellen(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS mailbericht (
            uniek TEXT PRIMARY KEY, wacht TEXT, postvak TEXT, map TEXT DEFAULT '', datum TEXT, dag TEXT,
            van TEXT, van_naam TEXT DEFAULT '', domein TEXT DEFAULT '', onderwerp TEXT DEFAULT '', soort TEXT,
            waarom TEXT DEFAULT '', mailinglijst INTEGER DEFAULT 0, beantwoord INTEGER DEFAULT 0,
            opgeruimd INTEGER DEFAULT 0, ts TEXT);
        CREATE INDEX IF NOT EXISTS mailbericht_dag ON mailbericht(dag);
        CREATE INDEX IF NOT EXISTS mailbericht_van ON mailbericht(postvak, van);
        CREATE TABLE IF NOT EXISTS mailregel (
            id INTEGER PRIMARY KEY AUTOINCREMENT, postvak TEXT NOT NULL, wie TEXT NOT NULL, actie TEXT NOT NULL,
            door TEXT DEFAULT '', ts TEXT, actief INTEGER DEFAULT 1, UNIQUE(postvak, wie));
        CREATE TABLE IF NOT EXISTS mailpostvak (
            postvak TEXT PRIMARY KEY, wacht TEXT, schrijven INTEGER DEFAULT 0, ts TEXT);
        CREATE TABLE IF NOT EXISTS mailuitschrijving (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, wacht TEXT, postvak TEXT, van TEXT, domein TEXT DEFAULT '',
            onderwerp TEXT DEFAULT '', map TEXT DEFAULT '', message_id TEXT DEFAULT '', datum TEXT DEFAULT '',
            knop_domein TEXT DEFAULT '', uitslag TEXT, code INTEGER DEFAULT 0, reden TEXT DEFAULT '',
            gebeurtenis TEXT);
        CREATE INDEX IF NOT EXISTS mailuitschrijving_ts ON mailuitschrijving(ts);
        CREATE TABLE IF NOT EXISTS mailbesluit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, uniek TEXT DEFAULT '', postvak TEXT DEFAULT '', van TEXT DEFAULT '',
            actie TEXT, door TEXT DEFAULT '', ts TEXT);
        CREATE INDEX IF NOT EXISTS mailbesluit_uniek ON mailbesluit(uniek);
        CREATE UNIQUE INDEX IF NOT EXISTS mailuitschrijving_id ON mailuitschrijving(gebeurtenis);
    """)
    kol = {r[1] for r in conn.execute("PRAGMA table_info(mailbericht)").fetchall()}
    if "lijst" in kol and "mailinglijst" not in kol:
        # 'lijst' betekende mailinglijst (een kop List-Unsubscribe), niet de opvolglijst (19-10-2026).
        try:
            conn.execute("ALTER TABLE mailbericht RENAME COLUMN lijst TO mailinglijst")
        except sqlite3.OperationalError as e:  # de andere gunicorn-werker was net eerst
            if "no such column" not in str(e) and "duplicate column" not in str(e):
                raise
    nieuw = (("naar", "TEXT DEFAULT ''"),                    # waar de wacht het naartoe sorteerde
                     ("message_id", "TEXT DEFAULT ''"), ("opvolging", "TEXT DEFAULT ''"), ("antwoord_door", "TEXT DEFAULT ''"),
                     ("antwoord_ts", "TEXT DEFAULT ''"), ("antwoord_naar", "TEXT DEFAULT ''"), ("stap", "TEXT DEFAULT ''"),
                     ("dringend", "INTEGER DEFAULT 0"), ("besluit", "TEXT DEFAULT ''"), ("besluit_door", "TEXT DEFAULT ''"),
                     ("besluit_ts", "TEXT DEFAULT ''"), ("auto_opruimen", "TEXT DEFAULT ''"), ("terug", "INTEGER DEFAULT 0"),
             ("klaarzet_id", "INTEGER"),
             ("gezien", "TEXT DEFAULT ''"))   # wanneer het bord het bericht voor het eerst kreeg (20-10-2026, /api/mail/stand)
    if any(k not in kol for k, _ in nieuw):
        # Twee gunicorn-werkers kunnen dit tegelijk zien: onder een slot, en daarna de kolommen opnieuw lezen
        # (resultaattoets 19-10-2026, C4).
        conn.execute("BEGIN IMMEDIATE")
        try:
            kol = {r[1] for r in conn.execute("PRAGMA table_info(mailbericht)").fetchall()}
            for k, soort in nieuw:
                if k not in kol:
                    conn.execute(f"ALTER TABLE mailbericht ADD COLUMN {k} {soort}")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    conn.execute("CREATE INDEX IF NOT EXISTS mailbericht_open ON mailbericht(opvolging, besluit)")


def _mail_overgang(conn):
    """Van de klaarzet-items voor mail-regisseur naar mailbericht (19-10-2026). Draait niet bij een webverzoek maar een
    keer, in een transactie, via eenmalig_mail_een_bron.py (ontwerptoets 19-10-2026). Idempotent: elk item dat nog klaar staat,
    wordt open in mailbericht en daarna opgepakt; een open punt ouder dan het venster van de wachten blijft zo open (niets
    vergeten). Het id van elk item, ook van een opgepakt, gaat naar klaarzet_id, zodat De Mailregisseur voor een bericht
    waarvoor De Bode al belde dezelfde oproepsleutel houdt (mailoproep:<id>) en niet opnieuw belt.
    Geeft de ids van items die ze niet kan plaatsen (onleesbare inhoud, geen postvak): die blijven klaar staan en worden
    gemeld, nooit stil weggelaten (resultaattoets 19-10-2026, K3)."""
    try:
        items = conn.execute("SELECT * FROM klaarzet WHERE voor='mail-regisseur' ORDER BY id").fetchall()
    except sqlite3.OperationalError:
        return []  # nog geen klaarzet-tabel
    onplaatsbaar = []
    for it in items:
        try:
            i = json.loads(it["inhoud"] or "{}")
        except ValueError:
            i = None
        pv, delen = ((i or {}).get("postvak") or "").lower(), (it["uniek"] or "").split(":", 2)
        if not isinstance(i, dict) or not pv or len(delen) < 3:
            if it["status"] == "klaar":
                onplaatsbaar.append(it["id"])
            continue
        mid = delen[2]
        uniek = (mid if mid.lower().startswith(pv + ":") else f"{pv}:{mid}")[:250]
        door = it["opgepakt_door"] or ""
        conn.execute("UPDATE mailbericht SET klaarzet_id=? WHERE uniek=? AND (klaarzet_id IS NULL OR klaarzet_id<?)",
                     (it["id"], uniek, it["id"]))
        if "op het bord" in door and it["status"] == "opgepakt":  # wat Mehdi op het oude /mail afhandelde
            conn.execute("UPDATE mailbericht SET besluit=?, besluit_door=?, besluit_ts=? WHERE uniek=? AND besluit=''",
                         ("ruis" if "ruis" in door else "afgehandeld", door.split(":")[0], it["opgepakt_ts"] or nu(), uniek))
        if it["status"] != "klaar":
            continue
        try:
            dag = datetime.fromisoformat(i.get("datum")).astimezone(BRUSSEL).date().isoformat()
        except (TypeError, ValueError):
            dag = ""
        van = (i.get("van") or "").lower()
        conn.execute(
            "INSERT INTO mailbericht(uniek,wacht,postvak,datum,dag,van,van_naam,domein,onderwerp,soort,waarom,ts,"
            "message_id,opvolging,stap,dringend,klaarzet_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(uniek) DO UPDATE SET opvolging=CASE WHEN COALESCE(mailbericht.opvolging, '') IN ('', 'geen') THEN 'open' "
            "ELSE mailbericht.opvolging END, stap=CASE WHEN COALESCE(mailbericht.stap, '')='' THEN excluded.stap ELSE mailbericht.stap END, "
            "dringend=MAX(mailbericht.dringend, excluded.dringend), klaarzet_id=excluded.klaarzet_id",
            (uniek, it["van"] or "", pv, i.get("datum") or "", dag, van, (i.get("van_naam") or "")[:120],
             van.rsplit("@", 1)[-1] if "@" in van else "", (i.get("onderwerp") or "")[:300], i.get("soort") or "",
             (i.get("waarom") or "")[:200], nu(), mid if mid.startswith("<") else "", "open", i.get("voorstel") or "",
             1 if i.get("dringend") else 0, it["id"]))
        conn.execute("UPDATE klaarzet SET status='opgepakt', opgepakt_door=?, opgepakt_ts=? WHERE id=?",
                     ("mail: overgezet naar mailbericht (een bron, 19-10-2026)", nu(), it["id"]))
    return onplaatsbaar


@app.route("/api/mail", methods=["POST"])
def api_mail():
    """Elke ronde van een mailwacht: alle beoordeelde berichten met hun opvolging (upsert op uniek; het besluit van
    Mehdi blijft), wat hij opruimde of terugzette, en per postvak of opruimen daar kan. Geeft terug hoeveel er voor deze
    wacht openstaat, geteld door _mail_open: dat getal zet de wacht in zijn werkverslag."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    conn = db()
    _mail_tabellen(conn)
    wacht = (p.get("wacht") or "")[:60]
    # Las de wacht zijn verzonden post niet volledig, dan zegt hij een eerder gevonden antwoord niet af: wat beantwoord of
    # doorgezet was, blijft dat (ontwerptoets 19-10-2026, Codex O1).
    volledig = p.get("verzonden_volledig", True) is not False
    n = 0
    for r in p.get("rijen") or []:
        if not r.get("uniek") or not r.get("postvak"):
            continue
        try:
            dag = datetime.fromisoformat(r.get("datum")).astimezone(BRUSSEL).date().isoformat()
        except (TypeError, ValueError):
            continue
        van = (r.get("van") or "").lower()[:200]
        lijst = r.get("mailinglijst", r.get("lijst"))  # 'lijst' van een wacht die nog niet bijgewerkt is
        # Een wacht van voor 19-10-2026 geeft geen opvolging door; dan blijft wat er stond.
        opv = (r.get("opvolging") or "")[:20] if "opvolging" in r else None
        antw = [(r.get("antwoord_door") or "")[:120], (r.get("antwoord_ts") or "")[:40], (r.get("antwoord_naar") or "")[:120],
                (r.get("stap") or "")[:300]]
        if not volledig and opv in ("open", "onzeker", "wacht"):
            oud = conn.execute("SELECT opvolging, antwoord_door, antwoord_ts, antwoord_naar, stap FROM mailbericht WHERE uniek=?",
                               (r["uniek"][:250],)).fetchone()
            if oud and oud["opvolging"] in ("beantwoord", "doorgezet"):
                opv, antw = oud["opvolging"], [oud["antwoord_door"], oud["antwoord_ts"], oud["antwoord_naar"], oud["stap"]]
        soort = (r.get("soort") or "")[:20]
        # Eenmaal begonnen opvolging blijft tot een besluit of tot het bericht verdwenen is (opgevolgd tot opgelost,
        # 20-10-2026; Codex-toets f750f0c, 5): deelt de wacht een punt dat open stond of liep later anders in (een
        # ruisregel voor de afzender, een strengere regel, een gewoon bericht dat weer 'wacht' heet), dan blijft het met
        # zijn soort en opvolging staan tot iemand Opgelost of Ruis klikt.
        vorig = conn.execute("SELECT soort, opvolging, besluit, antwoord_door, antwoord_ts, antwoord_naar, stap FROM mailbericht "
                             "WHERE uniek=?", (r["uniek"][:250],)).fetchone()
        loopt_of_open = (*MAIL_OPEN, *MAIL_LOOPT)
        if (opv is not None and vorig and not vorig["besluit"] and vorig["soort"] in MAIL_OPVOLG
                and vorig["opvolging"] in loopt_of_open):
            if soort not in MAIL_OPVOLG:
                soort = vorig["soort"]
            if opv not in (*loopt_of_open, "verdwenen"):
                opv = vorig["opvolging"]
                antw = [vorig["antwoord_door"], vorig["antwoord_ts"], vorig["antwoord_naar"], vorig["stap"]]
        conn.execute(
            "INSERT INTO mailbericht(uniek,wacht,postvak,map,datum,dag,van,van_naam,domein,onderwerp,soort,waarom,mailinglijst,"
            "beantwoord,ts,message_id,opvolging,antwoord_door,antwoord_ts,antwoord_naar,stap,dringend,auto_opruimen,gezien) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(uniek) DO UPDATE SET soort=excluded.soort, "
            "waarom=excluded.waarom, beantwoord=excluded.beantwoord, mailinglijst=excluded.mailinglijst, "
            "van_naam=excluded.van_naam, map=excluded.map, ts=excluded.ts, "
            "message_id=CASE WHEN excluded.message_id<>'' THEN excluded.message_id ELSE mailbericht.message_id END, "
            "opvolging=COALESCE(excluded.opvolging, mailbericht.opvolging), "
            "antwoord_door=excluded.antwoord_door, antwoord_ts=excluded.antwoord_ts, antwoord_naar=excluded.antwoord_naar, "
            "stap=excluded.stap, dringend=excluded.dringend, "
            # verplaatst en teruggezet zijn gebeurd; een ronde die het bericht later nog ziet, verandert dat niet
            "auto_opruimen=CASE WHEN mailbericht.auto_opruimen IN ('verplaatst', 'teruggezet') AND excluded.auto_opruimen<>'verplaatst' "
            "THEN mailbericht.auto_opruimen ELSE excluded.auto_opruimen END",
            (r["uniek"][:250], (wacht or r.get("wacht") or "")[:60], r["postvak"][:120], (r.get("map") or "")[:120],
             r["datum"][:40], dag, van, (r.get("van_naam") or "")[:120], van.rsplit("@", 1)[-1] if "@" in van else "",
             (r.get("onderwerp") or "")[:300], soort, (r.get("waarom") or "")[:200],
             1 if lijst else 0, 1 if (r.get("beantwoord") or opv in ("beantwoord", "doorgezet")) else 0, nu(),
             (r.get("message_id") or "")[:250], opv, *antw, 1 if r.get("dringend") else 0, (r.get("auto_opruimen") or "")[:20], nu()))
        n += 1
    for u in p.get("opgeruimd") or []:
        conn.execute("UPDATE mailbericht SET opgeruimd=1 WHERE uniek=?", (str(u)[:250],))
    for v in p.get("verplaatst") or []:  # de sorteerregels van het postvak (mailregels/regels_<alias>.txt)
        naar = str(v.get("naar") or "")[:120]
        conn.execute("UPDATE mailbericht SET naar=?, opgeruimd=CASE WHEN ? LIKE '%Opgeruimd' THEN 1 ELSE opgeruimd END WHERE uniek=?",
                     (naar, naar, str(v.get("uniek") or "")[:250]))
    for u in p.get("teruggezet") or []:  # terug in INBOX op vraag van Mehdi
        conn.execute("UPDATE mailbericht SET opgeruimd=0, terug=0, auto_opruimen='teruggezet', naar='' WHERE uniek=?",
                     (str(u)[:250],))
    for pv in p.get("postvakken") or []:
        conn.execute("INSERT INTO mailpostvak(postvak,wacht,schrijven,ts) VALUES(?,?,?,?) ON CONFLICT(postvak) DO UPDATE SET "
                     "wacht=excluded.wacht, schrijven=excluded.schrijven, ts=excluded.ts",
                     (pv.get("postvak", "")[:120], pv.get("wacht", "")[:60], 1 if pv.get("schrijven") else 0, nu()))
    conn.commit()
    return jsonify(ok=True, rijen=n, open=len(_mail_open(conn, wacht=wacht)) if wacht else None,
                   open_alle=len(_mail_open(conn)))


@app.route("/api/mailregels")
def api_mailregels():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    conn = db()
    _mail_tabellen(conn)
    return jsonify(regels=[dict(r) for r in conn.execute(
        "SELECT postvak, wie, actie, door, ts FROM mailregel WHERE actief=1 ORDER BY id").fetchall()])


@app.route("/api/mail/open")
def api_mail_open():
    """Wat openstaat, voor De Mailregisseur en zijn 08:00-bericht: dezelfde lijst als op /mail."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    conn = db()
    _mail_tabellen(conn)
    conn.commit()
    punten = _mail_open(conn, wacht=request.args.get("wacht", ""))
    return jsonify(aantal=len(punten), punten=punten)


@app.route("/api/mail/stand")
def api_mail_stand():
    """De stand van het systeem per postvak, voor de update van De Mailregisseur om 08:00 en 17:00 (Mehdi, 20-10-2026: "ik
    wil update 2 keer per dag ... de systeem en niet elke individuele mails"). sinds (ISO): vanaf wanneer binnen, belangrijk,
    ruis, gesorteerd en uitgeschreven tellen. Open komt uit _mail_open, dezelfde telling als /mail (test_mail.py)."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    conn = db()
    _mail_tabellen(conn)
    conn.commit()
    try:
        sinds = datetime.fromisoformat(request.args.get("sinds", ""))
    except ValueError:
        sinds = datetime.now(BRUSSEL) - timedelta(hours=24)
    sinds = sinds if sinds.tzinfo else sinds.replace(tzinfo=BRUSSEL)
    # tot: de grens die De Mailregisseur ook als vorige update bewaart, zodat wat tussen zijn klok en deze vraag binnenkwam
    # niet in twee updates telt (Codex-toets f750f0c, 7)
    try:
        tot = datetime.fromisoformat(request.args.get("tot", ""))
        tot = tot if tot.tzinfo else tot.replace(tzinfo=BRUSSEL)
    except ValueError:
        tot = datetime.now(timezone.utc) + timedelta(days=1)
    van_dag = (sinds.astimezone(BRUSSEL).date() - timedelta(days=1)).isoformat()

    def na(ts):
        try:
            t = datetime.fromisoformat(ts or "")
        except ValueError:
            return False
        t = t if t.tzinfo else t.replace(tzinfo=timezone.utc)
        return sinds <= t < tot

    wacht_van = {r["postvak"]: r["wacht"] for r in conn.execute("SELECT postvak, wacht FROM mailpostvak").fetchall()}
    stand = {}

    def pv(a):
        return stand.setdefault(a, {"wacht": wacht_van.get(a, ""), "binnen": 0, "belangrijk": 0, "ruis": 0, "gesorteerd": 0,
                                    "uitgeschreven": 0, "open": 0, "open_belangrijk": 0, "lang": 0, "loopt": 0, "vast": 0})
    for a in (*MAIL_FOCUS, *sorted(wacht_van)):
        pv(a)
    # Binnen telt wanneer het bord het bericht voor het eerst kreeg (gezien), niet de maildatum: een mail die een wacht pas
    # later ziet (hotmail als de Mac sliep), telt zo in de volgende update en nooit twee keer (Codex-toets 20-10-2026, 2).
    for r in conn.execute("SELECT postvak, datum, gezien, soort, naar, opgeruimd, auto_opruimen FROM mailbericht "
                          "WHERE dag>=? OR gezien>=?", (van_dag, van_dag)).fetchall():
        if na(r["gezien"] or r["datum"]):
            x = pv(r["postvak"])
            x["binnen"] += 1
            x["belangrijk"] += r["soort"] == "hoog"
            x["ruis"] += r["soort"] in MAIL_RUIS
            x["gesorteerd"] += bool(r["naar"] or r["opgeruimd"] or r["auto_opruimen"] == "verplaatst")
    for r in conn.execute("SELECT postvak, ts FROM mailuitschrijving WHERE ts>=? AND uitslag='aanvaard'", (van_dag,)).fetchall():
        if na(r["ts"]):
            pv(r["postvak"])["uitgeschreven"] += 1
    for p in _mail_open(conn):
        x = pv(p["postvak"])
        x["open"] += 1
        x["open_belangrijk"] += p["soort"] == "hoog"
        x["lang"] += p["werkdagen"] >= 5
    for p in _mail_loopt(conn):
        x = pv(p["postvak"])
        x["loopt"] += 1
        x["vast"] += p["vast"]
    wachten = {r["naam"]: {"label": r["label"], "actief": r["actief"], "status": "", "laatste_ronde": "", "noden": []}
               for r in conn.execute("SELECT naam, label, actief FROM agent WHERE naam LIKE 'mail-%'").fetchall()}
    for r in conn.execute("SELECT naam, status, ts FROM status WHERE naam LIKE 'mail-%'").fetchall():
        if r["naam"] in wachten:
            wachten[r["naam"]].update(status=r["status"], laatste_ronde=r["ts"])
    for r in conn.execute("SELECT naam, tekst FROM nood WHERE open=1 AND naam LIKE 'mail-%' ORDER BY id").fetchall():
        if r["naam"] in wachten:
            wachten[r["naam"]]["noden"].append(r["tekst"])
    return jsonify(sinds=sinds.isoformat(), tot=tot.isoformat(), focus=list(MAIL_FOCUS), postvakken=stand, wachten=wachten)


@app.route("/api/mail/veilig")
def api_mail_veilig():
    """De domeinen die een wacht nooit automatisch opruimt: wie ooit iets belangrijks, gewoons of met gevolg stuurde, wie
    beantwoord werd, waarover Mehdi besliste, of waarop een regel belangrijk of houden staat. Over de hele geschiedenis
    van het bord, niet alleen het venster van de wacht (ontwerptoets 19-10-2026, Claude O3)."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    conn = db()
    _mail_tabellen(conn)
    conn.commit()
    doms = {r[0] for r in conn.execute(
        "SELECT DISTINCT domein FROM mailbericht WHERE domein<>'' AND (soort IN ('hoog','midden','actie') OR beantwoord=1 "
        "OR besluit<>'' OR opvolging IN ('beantwoord','doorgezet','onzeker'))").fetchall()}
    for wie, in conn.execute("SELECT wie FROM mailregel WHERE actief=1 AND actie IN ('belangrijk','houden')").fetchall():
        doms.add(wie.rsplit("@", 1)[-1])
    return jsonify(domeinen=sorted(doms))


@app.route("/api/mail/terug")
def api_mail_terug():
    """Wat Mehdi uit Opgeruimd terugvroeg, voor de wacht van dat postvak: hij zet het bij zijn volgende ronde terug."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    conn = db()
    _mail_tabellen(conn)
    return jsonify(berichten=[dict(r) for r in conn.execute(
        "SELECT uniek, postvak, message_id FROM mailbericht WHERE terug=1 AND wacht=?", (request.args.get("wacht", ""),)).fetchall()])


# Uitschrijven via de officiele knop (RFC 8058). Mehdi, 20-10-2026: "Uitschrijven mag meteen automatisch, zonder lijst
# vooraf. Alleen via de officiele uitschrijfknop ... Zet wel elk uitschrijven in een logboek dat ik op het dashboard zie."
# De wachten doen het (mijnagents-runner/koppelingen/uitschrijven.py); het bord bewaart het logboek. Nooit de volledige
# URL van de knop: die bevat persoonlijke sleutels. Een veld dat op een URL lijkt, weigert het bord.
MAIL_UITSLAGEN = ("aanvaard", "geweigerd", "fout", "overgeslagen")


@app.route("/api/mail/uitschrijving", methods=["POST"])
def api_mail_uitschrijving():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    conn = db()
    _mail_tabellen(conn)
    n = 0
    for r in p.get("regels") or []:
        knop = str(r.get("knop_domein") or "").lower()[:120]
        gid = str(r.get("gebeurtenis") or "")[:40]
        if (r.get("uitslag") not in MAIL_UITSLAGEN or not r.get("van") or not gid or "/" in knop or ":" in knop or "?" in knop
                or "=" in knop):
            continue
        van = str(r.get("van")).lower()[:200]
        # een vaste id per poging: dezelfde regel opnieuw sturen (de wacht stuurt na wat het bord miste) telt nooit dubbel
        conn.execute("INSERT OR IGNORE INTO mailuitschrijving(ts, wacht, postvak, van, domein, onderwerp, map, message_id, datum, "
                     "knop_domein, uitslag, code, reden, gebeurtenis) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (str(r.get("ts") or nu())[:40], (p.get("wacht") or r.get("wacht") or "")[:60], str(r.get("postvak") or "")[:120],
                      van, van.rsplit("@", 1)[-1] if "@" in van else "", str(r.get("onderwerp") or "")[:300],
                      str(r.get("map") or "")[:120], str(r.get("message_id") or "")[:250], str(r.get("datum") or "")[:40],
                      knop, r["uitslag"], int(r.get("code") or 0), str(r.get("reden") or "")[:200], gid))
        n += 1
    conn.commit()
    return jsonify(ok=True, regels=n)


@app.route("/api/mail/uitschrijvingen")
def api_mail_uitschrijvingen():
    """Het logboek, voor de wachten (een keer per adres) en De Mailregisseur (het aantal in zijn overzicht)."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    conn = db()
    _mail_tabellen(conn)
    conn.commit()
    sinds = request.args.get("sinds", "")
    n = max(1, min(int(request.args.get("n", "100") or 100), 20000))  # standaard de laatste 100 (G5)
    rijen = conn.execute("SELECT * FROM mailuitschrijving WHERE ts>=? ORDER BY ts DESC LIMIT ?", (sinds, n)).fetchall()
    return jsonify(uitschrijvingen=[dict(r) for r in rijen])


def _mail_link(postvak, message_id):
    """Een link naar het bericht in de webmail, als die bestaat: Gmail zoekt op Message-ID; one.com kan dat niet."""
    if "gmail.com" in (postvak or "") and message_id:
        return "https://mail.google.com/mail/u/0/#search/" + urllib.parse.quote("rfc822msgid:" + message_id.strip("<>"), safe="")
    return ""


def _mail_status(r):
    """De status van een bericht in woorden: het besluit van Mehdi gaat voor de opvolging van de wacht."""
    b, o = r["besluit"] or "", r["opvolging"] or ""
    wanneer, door = _brussel(r["antwoord_ts"]), r["antwoord_door"] or ""
    if b == "afgehandeld":
        return f"opgelost (aangeduid door {r['besluit_door'] or 'Mehdi'} op {_brussel(r['besluit_ts'])})"
    if b == "doorgezet":
        return f"loopt: doorgezet (aangeduid door {r['besluit_door'] or 'Mehdi'} op {_brussel(r['besluit_ts'])})"
    if b == "ruis":
        return "ruis"
    if b == "open":
        return f"open (weer opengezet door {r['besluit_door'] or 'Mehdi'} op {_brussel(r['besluit_ts'])})"
    return {"open": "open", "onzeker": f"mogelijk beantwoord ({door or 'onbekend'}, {wanneer}), nakijken",
            "beantwoord": f"loopt: beantwoord door {door} op {wanneer}",
            "doorgezet": f"loopt: doorgezet naar {r['antwoord_naar'] or '?'} door {door} op {wanneer}",
            "wacht": "nieuw, nog geen werkdag",
            "verlopen": "automatisch bericht met gevolg, ouder dan 7 dagen, nog niet als opgelost aangeduid",
            "verdwenen": "niet meer in het postvak (verplaatst of verwijderd)",
            "geen": "geen opvolging"}.get(o, o or "nog niet beoordeeld")


def _mailpunt(r):
    """Een bericht uit mailbericht zoals /mail en De Mailregisseur het tonen."""
    orde, label = MAIL_SOORT.get(r["soort"] or "", (9, r["soort"] or ""))
    wd = _werkdagen_sinds(r["datum"])
    return {"uniek": r["uniek"], "wacht": r["wacht"] or "", "postvak": r["postvak"] or "", "van": r["van"] or "",
            "van_naam": r["van_naam"] or "", "onderwerp": r["onderwerp"] or "", "datum_iso": r["datum"] or "",
            "datum": _brussel(r["datum"], dag=True), "soort": r["soort"] or "", "soort_label": label, "orde": orde,
            "werkdagen": wd if wd is not None else 0, "waarom": r["waarom"] or "", "stap": r["stap"] or "",
            "opvolging": r["opvolging"] or "", "besluit": r["besluit"] or "", "status": _mail_status(r),
            "antwoord_door": r["antwoord_door"] or "", "antwoord_ts": r["antwoord_ts"] or "",
            "antwoord_wanneer": _brussel(r["antwoord_ts"]) if r["antwoord_ts"] else "",
            "dringend": bool(r["dringend"]), "klaarzet_id": r["klaarzet_id"], "auto_opruimen": r["auto_opruimen"] or "",
            "map": r["map"] or "", "terug": r["terug"], "message_id": r["message_id"] or ""}


def _mail_volgorde(p):
    return (p["orde"], -p["werkdagen"], p["datum_iso"])


def _postvak_waar(postvak):
    """Het stuk WHERE voor een postvak, een reeks postvakken (de focus) of geen keuze (alles), met de waarden."""
    lijst = [p for p in ([postvak] if isinstance(postvak, str) else list(postvak or ())) if p]
    if not lijst:
        return "", []
    return f" AND postvak IN ({','.join('?' * len(lijst))})", lijst


def _mail_keuze(waarde):
    """Wat /mail toont: standaard de focus, 'alle' is alles, anders een postvak."""
    if waarde in ("", "focus"):
        return "focus", MAIL_FOCUS
    if waarde == "alle":
        return "alle", ()
    return waarde, (waarde,)


def _mail_open(conn, wacht="", postvak=""):
    """De enige telling van wat openstaat: geen besluit van Mehdi en de wacht zegt open of onzeker, of Mehdi zette het
    weer open. /mail, De Mailregisseur, zijn 08:00-bericht en het werkverslag van de wachten lezen alleen dit (test_mail.py)."""
    w, a = f"((besluit='' AND opvolging IN ({','.join('?' * len(MAIL_OPEN))})) OR besluit='open')", list(MAIL_OPEN)
    if wacht:
        w += " AND wacht=?"
        a.append(wacht)
    pw, pa = _postvak_waar(postvak)
    return sorted((_mailpunt(r) for r in conn.execute(f"SELECT * FROM mailbericht WHERE {w}{pw}", a + pa).fetchall()),
                  key=_mail_volgorde)


def _mail_loopt(conn, wacht="", postvak=""):
    """Wat loopt: er is geantwoord of doorgezet (door de draad of door Mehdi), maar niemand zei nog dat het opgelost is. Het
    blijft staan tot een klik op Opgelost; wat MAIL_VAST werkdagen niet bewoog, staat bovenaan als vastgelopen."""
    w = (f"soort IN ({','.join('?' * len(MAIL_OPVOLG))}) AND ((besluit='' AND opvolging IN "
         f"({','.join('?' * len(MAIL_LOOPT))})) OR besluit='doorgezet')")
    a = [*MAIL_OPVOLG, *MAIL_LOOPT]
    if wacht:
        w += " AND wacht=?"
        a.append(wacht)
    pw, pa = _postvak_waar(postvak)
    uit = []
    for r in conn.execute(f"SELECT * FROM mailbericht WHERE {w}{pw}", a + pa).fetchall():
        p = _mailpunt(r)
        door_mehdi = r["besluit"] == "doorgezet"
        p["wie"] = (f"{r['besluit_door'] or 'Mehdi'} (doorgezet)" if door_mehdi else
                    f"{r['antwoord_door'] or '?'}" + (f", naar {r['antwoord_naar']}" if r["opvolging"] == "doorgezet" and r["antwoord_naar"] else ""))
        laatst = r["besluit_ts"] if door_mehdi else r["antwoord_ts"]
        p["beweging"] = _brussel(laatst, dag=True) if laatst else ""
        p["beweging_wd"] = (_werkdagen_sinds(laatst) or 0) if laatst else p["werkdagen"]
        p["vast"] = p["beweging_wd"] >= MAIL_VAST
        uit.append(p)
    return sorted(uit, key=lambda p: (not p["vast"], p["orde"], -p["beweging_wd"], p["datum_iso"]))


def _mail_cijfers(conn, van_dag, postvak=""):
    """Tellingen per soort, per dag en per postvak vanaf van_dag (Brusselse datum), eventueel voor een postvak."""
    pw, pa = _postvak_waar(postvak)
    w, a = "dag>=?" + pw, [van_dag] + pa
    per_soort = {r["soort"]: r["n"] for r in conn.execute(
        f"SELECT soort, COUNT(*) n FROM mailbericht WHERE {w} GROUP BY soort", a).fetchall()}
    per_dag = {}
    for r in conn.execute(f"SELECT dag, soort, COUNT(*) n FROM mailbericht WHERE {w} GROUP BY dag, soort", a).fetchall():
        per_dag.setdefault(r["dag"], {})[r["soort"]] = r["n"]
    per_postvak = {}
    for r in conn.execute(f"SELECT postvak, soort, COUNT(*) n FROM mailbericht WHERE {w} GROUP BY postvak, soort", a).fetchall():
        per_postvak.setdefault(r["postvak"], {})[r["soort"]] = r["n"]
    opgeruimd = conn.execute(f"SELECT COUNT(*) FROM mailbericht WHERE {w} AND opgeruimd=1", a).fetchone()[0]
    gesorteerd = conn.execute(f"SELECT COUNT(*) FROM mailbericht WHERE {w} AND (naar<>'' OR opgeruimd=1)", a).fetchone()[0]
    ruis = conn.execute(
        f"SELECT postvak, van, MAX(van_naam) naam, COUNT(*) n, GROUP_CONCAT(DISTINCT soort) soorten, "
        f"MAX(onderwerp) voorbeeld, MAX(datum) laatst, MAX(mailinglijst) mailinglijst, SUM(opgeruimd) opgeruimd FROM mailbericht "
        f"WHERE {w} AND soort IN ({','.join('?' * len(MAIL_RUIS))}) GROUP BY postvak, van ORDER BY n DESC, laatst DESC LIMIT 30",
        a + list(MAIL_RUIS)).fetchall()
    return per_soort, per_dag, per_postvak, (opgeruimd, gesorteerd), [dict(r) for r in ruis]


def _grafiek(per_dag, dagen):
    """Gestapelde staven per dag (inline SVG), in de volgorde van MAIL_SOORTEN."""
    hoogste = max([sum(per_dag.get(d, {}).values()) for d in dagen] + [1])
    b, h, onder = 900, 220, 26
    stap = b / max(len(dagen), 1)
    staaf = max(min(stap * 0.68, 34), 4)
    delen = []
    for i, d in enumerate(dagen):
        x, y = i * stap + (stap - staaf) / 2, h
        tel = per_dag.get(d, {})
        titel = ", ".join(f"{label.lower()} {tel[k]}" for k, label, _ in MAIL_SOORTEN if tel.get(k))
        for k, _label, kleur in reversed(MAIL_SOORTEN):
            n = tel.get(k, 0)
            if not n:
                continue
            hh = n / hoogste * (h - 10)
            y -= hh
            delen.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{staaf:.1f}" height="{hh:.1f}" rx="3" fill="{kleur}">'
                         f'<title>{d[8:10]}-{d[5:7]}: {sum(tel.values())} mails; {titel}</title></rect>')
        if len(dagen) <= 10 or i % max(len(dagen) // 10, 1) == 0 or i == len(dagen) - 1:
            delen.append(f'<text x="{x + staaf / 2:.1f}" y="{h + 17}" text-anchor="middle">{d[8:10]}-{d[5:7]}</text>')
    delen.append(f'<text x="0" y="12" class="as">{hoogste}</text><line x1="0" x2="{b}" y1="{h}" y2="{h}" class="as"/>')
    return f'<svg viewBox="0 0 {b} {h + onder}" class="grafiek" role="img" aria-label="Mails per dag">{"".join(delen)}</svg>'


@app.route("/mail")
def mail_pagina():
    if not mag_mail():
        abort(403)
    conn = db()
    _mail_tabellen(conn)
    conn.commit()
    periode = request.args.get("periode", "7")
    periode = periode if periode in MAIL_PERIODES else "7"
    postvak, keuze = _mail_keuze(request.args.get("postvak", ""))
    vandaag = datetime.now(BRUSSEL).date()
    van_dag = (vandaag - timedelta(days=MAIL_PERIODES[periode][1])).isoformat()
    grafiek_dagen = [(vandaag - timedelta(days=i)).isoformat() for i in range(max(MAIL_PERIODES[periode][1], 13), -1, -1)]

    labels = {r["naam"]: dict(r) for r in conn.execute("SELECT naam, label, rol, actief FROM agent WHERE naam LIKE 'mail-%'").fetchall()}
    wachten = sorted((n for n, a in labels.items() if a["actief"] and n != "mail-regisseur"), key=lambda n: labels[n]["label"])
    status = {r["naam"]: {**dict(r), "wanneer": _brussel(r["ts"])}
              for r in conn.execute("SELECT * FROM status WHERE naam LIKE 'mail-%'").fetchall()}
    noden = {}
    for r in conn.execute("SELECT naam, tekst, wie FROM nood WHERE open=1 AND naam LIKE 'mail-%' ORDER BY id").fetchall():
        noden.setdefault(r["naam"], []).append(dict(r))
    postvakken = {r["postvak"]: dict(r) for r in conn.execute("SELECT * FROM mailpostvak").fetchall()}
    wacht_van = {pv["wacht"]: a for a, pv in postvakken.items()}

    if keuze:
        wachten = [n for n in wachten if wacht_van.get(n) in keuze]
    open_alle = _mail_open(conn, postvak=keuze)
    open_per = {n: sum(1 for p in open_alle if p["wacht"] == n) for n in wachten}
    # Wat loopt (geantwoord of doorgezet, nog niet opgelost), en afgesloten in deze periode: opgelost of ruis (een klik,
    # wie en wanneer), of niet meer in het postvak (20-10-2026: niets anders sluit nog vanzelf).
    loopt = _mail_loopt(conn, postvak=keuze)
    # Een besluit telt op de dag dat het genomen werd: wie vandaag een oude mail op Opgelost zet, ziet hem hier (Codex-toets
    # f750f0c, 11); besluit_ts is UTC, een dag marge vangt de tijdzone op.
    w, a = ("soort IN ('hoog','midden','actie') AND ((besluit IN ('afgehandeld','ruis') AND (dag>=? OR besluit_ts>=?)) "
            "OR (besluit='' AND opvolging='verdwenen' AND dag>=?))",
            [van_dag, (datetime.fromisoformat(van_dag) - timedelta(days=1)).date().isoformat(), van_dag])
    pw, pa = _postvak_waar(keuze)
    w, a = w + pw, a + pa
    afgesloten = sorted((_mailpunt(r) for r in conn.execute(f"SELECT * FROM mailbericht WHERE {w} LIMIT 500", a).fetchall()),
                        key=lambda p: p["datum_iso"], reverse=True)
    # Reclame die de wacht naar Opgeruimd zet (of in de proefweek zou zetten), met terugzetten.
    w, a = "dag>=? AND auto_opruimen<>''", [van_dag]
    pw, pa = _postvak_waar(keuze)
    w, a = w + pw, a + pa
    reclame = sorted((_mailpunt(r) for r in conn.execute(f"SELECT * FROM mailbericht WHERE {w} LIMIT 300", a).fetchall()),
                     key=lambda p: p["datum_iso"], reverse=True)
    # Het logboek uitschrijven (Mehdi, 20-10-2026), in deze periode.
    w, a = "ts>=?", [van_dag]
    pw, pa = _postvak_waar(keuze)
    w, a = w + pw, a + pa
    uitgeschreven = []
    for r in conn.execute(f"SELECT * FROM mailuitschrijving WHERE {w} ORDER BY ts DESC LIMIT 500", a).fetchall():
        x = dict(r)
        x["wanneer"] = _brussel(x["ts"], dag=True)
        x["link"] = _mail_link(x["postvak"], x["message_id"])
        uitgeschreven.append(x)

    per_soort, per_dag, per_postvak, (opgeruimd, gesorteerd), ruis = _mail_cijfers(conn, van_dag, keuze)
    _, grafiek_per_dag, _, _, _ = _mail_cijfers(conn, grafiek_dagen[0], keuze)
    totaal = sum(per_soort.values())
    ruis_n = sum(per_soort.get(k, 0) for k in MAIL_RUIS)
    regels = [dict(r) for r in conn.execute("SELECT * FROM mailregel WHERE actief=1 ORDER BY ts DESC").fetchall()
              if not keuze or r["postvak"] in keuze or r["postvak"] == "*"]
    regel_van = {(r["postvak"], r["wie"]): r["actie"] for r in regels}
    for x in ruis:
        x["regel"] = regel_van.get((x["postvak"], x["van"])) or regel_van.get((x["postvak"], "@" + x["van"].rsplit("@", 1)[-1]), "")
        x["kan_opruimen"] = bool(postvakken.get(x["postvak"], {}).get("schrijven"))
        x["laatst"] = _brussel(x["laatst"], dag=True)
    for r in regels:
        r["wanneer"] = _brussel(r["ts"])
    kpi = {"totaal": totaal, "per_dag": round(totaal / (MAIL_PERIODES[periode][1] + 1), 1),
           "hoog": per_soort.get("hoog", 0), "hoog_open": sum(1 for p in open_alle if p["soort"] == "hoog"),
           "open": len(open_alle), "onzeker": sum(1 for p in open_alle if p["opvolging"] == "onzeker"),
           "loopt": len(loopt), "vast": sum(1 for p in loopt if p["vast"]),
           "lang": sum(1 for p in open_alle if p["werkdagen"] >= 5),
           "ruis": ruis_n, "ruis_pct": round(100 * ruis_n / totaal) if totaal else 0,
           "rommel": per_soort.get("rommel", 0), "melding": per_soort.get("melding", 0), "koud": per_soort.get("koud", 0),
           "verdacht": per_soort.get("verdacht", 0), "opgeruimd": opgeruimd, "gesorteerd": gesorteerd,
           "opruim_regels": sum(1 for r in regels if r["actie"] == "opruimen")}
    return render_template("mail.html", app_naam=APP_NAAM, wachten=wachten, open_alle=open_alle, open_per=open_per,
                           afgesloten=afgesloten, loopt=loopt, vast_wd=MAIL_VAST, reclame=reclame, uitgeschreven=uitgeschreven, labels=labels, status=status,
                           noden=noden, kpi=kpi, periode=periode, periodes=MAIL_PERIODES, postvak=postvak, focus=MAIL_FOCUS,
                           geschiedenis=_mail_geschiedenis(conn, [*open_alle, *loopt, *afgesloten]),
                           alleen_mail=not mag_beslissen(),
                           postvakken=postvakken, wacht_van=wacht_van, per_postvak=per_postvak, soorten=MAIL_SOORTEN,
                           ruis=ruis, regels=regels, acties=MAIL_ACTIES, gratis=MAIL_GEEN_DOMEIN, grafiek=_grafiek(grafiek_per_dag, grafiek_dagen),
                           nu=datetime.now(BRUSSEL).strftime("%d-%m-%Y %H:%M"))


def _terug_naar_mail(anker=""):
    q = {k: v for k, v in (("periode", request.form.get("periode", "")), ("postvak", request.form.get("filter", ""))) if v}
    return redirect(url_for("mail_pagina", **q) + anker)


@app.route("/mail/besluit", methods=["POST"])
def mail_besluit():
    """Mehdi beslist over een bericht. Afgehandeld: hij regelde het (of het hoeft niet). Doorgezet: iemand anders volgt
    het op. Ruis: afgehandeld, en deze afzender voortaan als ruis tellen in dit postvak. Terug: het besluit ongedaan maken.
    Niet opruimen: de wacht zet deze afzender nooit automatisch in Opgeruimd, en wat hij al verplaatste, zet hij terug.
    Helemaal weg (weg): ruis voor dit bericht, en deze afzender in dit postvak op uitschrijven: de wacht ruimt al zijn
    mail op, ook wat later komt, en schrijft uit via de officiele knop als die er is (Mehdi, 20-10-2026: "een knop die
    meer is dan ruis ... helemaal uitschrijven, zodat het effectief gedaan is"). Elke klik komt in mailbesluit."""
    if not mag_mail():
        abort(403)
    conn = db()
    _mail_tabellen(conn)
    actie = request.form.get("actie", "")
    r = conn.execute("SELECT * FROM mailbericht WHERE uniek=?", (request.form.get("uniek", "")[:250],)).fetchone()
    if not r:
        abort(404)
    if actie in MAIL_BESLUITEN:
        conn.execute("UPDATE mailbericht SET besluit=?, besluit_door=?, besluit_ts=? WHERE uniek=?",
                     (actie, gebruiker(), nu(), r["uniek"]))
        if actie == "ruis":
            _mail_regel_zetten(conn, r["postvak"], r["van"], "ruis")
    elif actie == "weg":
        _mail_regel_zetten(conn, r["postvak"], r["van"], "uitschrijven")
        conn.execute("UPDATE mailbericht SET besluit='ruis', besluit_door=?, besluit_ts=? WHERE uniek=?",
                     (gebruiker(), nu(), r["uniek"]))
    elif actie == "terug":
        conn.execute("UPDATE mailbericht SET besluit='', besluit_door='', besluit_ts='' WHERE uniek=?", (r["uniek"],))
        # Terugzetten maakt ook Helemaal weg ongedaan: de afzender wordt niet langer opgeruimd (Codex-toets e70f5a4, 5).
        # Een uitschrijving die al gebeurde, blijft gebeurd.
        conn.execute("UPDATE mailregel SET actief=0, door=?, ts=? WHERE postvak=? AND wie=? AND actie='uitschrijven' AND actief=1",
                     (gebruiker(), nu(), (r["postvak"] or "").lower(), (r["van"] or "").lower()))
    elif actie == "houden":
        _mail_regel_zetten(conn, r["postvak"], r["van"], "houden")
        if r["auto_opruimen"] == "verplaatst":
            conn.execute("UPDATE mailbericht SET terug=1 WHERE uniek=?", (r["uniek"],))
        elif r["auto_opruimen"] == "droog":
            conn.execute("UPDATE mailbericht SET auto_opruimen='' WHERE uniek=?", (r["uniek"],))
    else:
        abort(400)
    _mail_besluit_loggen(conn, r["uniek"], r["postvak"], r["van"], actie)
    conn.commit()
    return _terug_naar_mail("#opvolgen" if actie != "houden" else "#reclame")


def _mail_besluit_loggen(conn, uniek, postvak, van, actie):
    """Elke klik op /mail, met wie en wanneer: de geschiedenis per bericht (20-10-2026; nu ook Angela en Shaniel)."""
    conn.execute("INSERT INTO mailbesluit(uniek, postvak, van, actie, door, ts) VALUES(?,?,?,?,?,?)",
                 ((uniek or "")[:250], (postvak or "")[:120], (van or "")[:200], (actie or "")[:20], gebruiker()[:60], nu()))


def _mail_geschiedenis(conn, punten):
    """Per bericht wat er gebeurde, op tijd: binnengekomen, beantwoord of doorgestuurd, elke klik op het bericht en elke
    klik op zijn afzender (Jouw regels), met wie (Codex-toets e70f5a4, 6). {uniek: [(wanneer, tekst)]}."""
    def tijd(ts):
        try:
            t = datetime.fromisoformat(ts or "")
        except ValueError:
            return None
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    kliks, regels = {}, {}
    uniek = [p["uniek"] for p in punten if p["uniek"]]
    paren = {((p["postvak"] or "").lower(), (p["van"] or "").lower()) for p in punten}
    for i in range(0, len(uniek), 400):
        deel = uniek[i:i + 400]
        for r in conn.execute(f"SELECT uniek, actie, door, ts FROM mailbesluit WHERE uniek IN ({','.join('?' * len(deel))})",
                              deel).fetchall():
            kliks.setdefault(r["uniek"], []).append((r["ts"], f"{MAIL_KLIK.get(r['actie'], r['actie'])} door {r['door']}"))
    for r in conn.execute("SELECT postvak, van, actie, door, ts FROM mailbesluit WHERE uniek=''").fetchall():
        sleutel = ((r["postvak"] or "").lower(), (r["van"] or "").lower())
        if sleutel in paren:
            actie = (r["actie"] or "").split(":", 1)[-1]
            tekst = "regel weggehaald" if actie == "weg" else f"afzender op {MAIL_ACTIES.get(actie, actie)}"
            regels.setdefault(sleutel, []).append((r["ts"], f"{tekst} door {r['door']}"))
    uit = {}
    for p in punten:
        rijen = [(p["datum_iso"], "binnengekomen" + (f" in {p['map']}" if p["map"] else ""))]
        if p["antwoord_door"] and p["antwoord_ts"]:
            woord = {"doorgezet": "doorgestuurd", "onzeker": "mogelijk beantwoord"}.get(p["opvolging"], "beantwoord")
            rijen.append((p["antwoord_ts"], f"{woord} door {p['antwoord_door']}"))
        rijen += kliks.get(p["uniek"], []) + regels.get(((p["postvak"] or "").lower(), (p["van"] or "").lower()), [])
        rijen = [(tijd(ts), tekst) for ts, tekst in rijen if tijd(ts)]
        uit[p["uniek"]] = [(_brussel(t.isoformat()), tekst) for t, tekst in sorted(rijen, key=lambda x: x[0])]
    return uit


def _mail_regel_zetten(conn, postvak, wie, actie):
    """Zonder _mail_tabellen: dat commit (executescript) en de aanroeper doet besluit, regel en logboek samen (Codex-toets
    e70f5a4, 4). Helemaal weg (uitschrijven) alleen voor een exact adres in een postvak dat de wacht kan schrijven,
    nooit voor @domein of * (Codex-toets e70f5a4, 1 en 3)."""
    postvak, wie = (postvak or "*").strip().lower()[:120], (wie or "").strip().lower()[:200]
    if not wie or ("@" not in wie):
        abort(400)
    if actie == "uitschrijven":
        pv = conn.execute("SELECT schrijven FROM mailpostvak WHERE postvak=?", (postvak,)).fetchone()
        if wie.startswith("@") or postvak == "*" or not (pv and pv["schrijven"]):
            abort(400)
    if wie.startswith("@") and wie[1:] in MAIL_GEEN_DOMEIN and actie != "weg":
        abort(400)
    if actie == "weg":
        conn.execute("UPDATE mailregel SET actief=0, door=?, ts=? WHERE postvak=? AND wie=?", (gebruiker(), nu(), postvak, wie))
        return
    if actie not in MAIL_ACTIES:
        abort(400)
    conn.execute("INSERT INTO mailregel(postvak, wie, actie, door, ts, actief) VALUES(?,?,?,?,?,1) ON CONFLICT(postvak, wie) "
                 "DO UPDATE SET actie=excluded.actie, door=excluded.door, ts=excluded.ts, actief=1",
                 (postvak, wie, actie, gebruiker(), nu()))


@app.route("/mail/regel", methods=["POST"])
def mail_regel():
    """Mehdi beslist over een afzender (adres of @domein) in een postvak: belangrijk, ruis, opruimen, houden, of weg."""
    if not mag_mail():
        abort(403)
    conn = db()
    _mail_tabellen(conn)
    _mail_regel_zetten(conn, request.form.get("postvak"), request.form.get("wie"), request.form.get("actie", ""))
    _mail_besluit_loggen(conn, "", request.form.get("postvak"), request.form.get("wie"), "regel:" + request.form.get("actie", ""))
    conn.commit()
    return _terug_naar_mail("#opschonen")


# --- dagen: het dagdashboard van de logboek-laag. Per dag wat de Dagbundelaar
#     samenbracht: uren onderweg, bezoeken, gesprekken en met wie, afspraken,
#     foto's, lichaam, en de spiegel van De Levenscoach. Alleen beheer.
LOCATIE_URL = os.environ.get("LOCATIE_URL", "http://app-locatie:3031")


def _locatie(pad, standaard=None):
    """Lezen bij de tegel locatie.globaal.be over het interne netwerk. De locatie hoort uit de
    dag-API te komen, niet uit het markdown-dagboek van het bord (opdracht v1.4, 05-10-2026)."""
    import urllib.request
    try:
        with urllib.request.urlopen(LOCATIE_URL + pad, timeout=10) as r:
            return json.load(r)
    except Exception:  # noqa: BLE001
        return standaard


@app.route("/dagen")
def dagen_pagina():
    if not mag_beslissen():
        abort(403)
    conn = db()
    dagen = {}

    def dag_van(it):
        inhoud = it["inhoud"] or ""
        try:
            d = json.loads(inhoud) if inhoud.startswith("{") else {}
        except ValueError:
            d = {}
        return (d.get("datum") or d.get("start") or it["sleutel"] or "")[:10], d

    for it in conn.execute("SELECT * FROM klaarzet ORDER BY id").fetchall():
        dag, d = dag_van(it)
        if not (len(dag) == 10 and dag[4] == "-"):
            continue
        r = dagen.setdefault(dag, {"dag": dag, "afspraken": 0, "gesprekken": 0, "gesprek_min": 0, "personen": set(), "bezoeken": 0,
                                   "km": 0.0, "onderweg_min": 0, "fotos": 0, "slaap": "", "hartslag": "", "spiegel": "", "bundels": 0,
                                   "signalen": 0, "transcripten": 0})
        s = it["soort"]
        if s == "afspraak":
            r["afspraken"] += 1
        elif s == "transcript":
            r["transcripten"] += 1
        elif s == "foto":
            r["fotos"] += int(d.get("aantal") or 0)
        elif s == "gezondheid":
            r["slaap"] = (d.get("samenvatting") or "")[:160]
        elif s == "coaching" and not it["sleutel"].startswith("week"):
            r["spiegel"] = it["inhoud"] or ""
        elif s == "dagbundel":
            r["bundels"] += 1
        elif s == "signaal":
            r["signalen"] += 1
    # Telregel (Z10): een rij met dubbel_van telt niet, anders telt een gesprek in Zoom en Fathom twee keer. Een mail of
    # een chat is geen gesprek (telt_als_gesprek).
    for g in conn.execute("SELECT uniek, bron, datum, minuten, personen, prive, COALESCE(afdeling, '') AS afdeling "
                          "FROM gesprek_log WHERE COALESCE(dubbel_van, '')=''").fetchall():
        if not telt_als_gesprek(g):
            continue
        r = dagen.setdefault(g["datum"], {"dag": g["datum"], "afspraken": 0, "gesprekken": 0, "gesprek_min": 0, "personen": set(), "bezoeken": 0,
                                          "km": 0.0, "onderweg_min": 0, "fotos": 0, "slaap": "", "hartslag": "", "spiegel": "", "bundels": 0,
                                          "signalen": 0, "transcripten": 0})
        r["gesprekken"] += 1
        r["gesprek_min"] += int(g["minuten"] or 0)
        # Controle Codex 26-10-2026: een privérij telt mee, maar zijn namen komen niet in het dagoverzicht.
        if g["prive"] or g["afdeling"].strip().casefold() in ("prive", "privé"):
            continue
        for p in (g["personen"] or "").split(","):
            if p.strip():
                r["personen"].add(p.strip())
    # Locatiecijfers uit de dag-API van de tegel: alleen dagen uit de actieve meetreeks (vanaf
    # 3-10-2026, autotracker), uit dezelfde dagindeling als het dagboek. Oude telefoondagboeken op het
    # bord tellen niet meer mee; tot 05-10-2026 werden hun tabelregels geteld en het nieuwe formaat niet.
    for dag, c in ((_locatie("/api/dagcijfers", {}) or {}).get("dagen") or {}).items():
        r = dagen.setdefault(dag, {"dag": dag, "afspraken": 0, "gesprekken": 0, "gesprek_min": 0, "personen": set(),
                                   "bezoeken": 0, "km": 0.0, "onderweg_min": 0, "fotos": 0, "slaap": "", "hartslag": "",
                                   "spiegel": "", "bundels": 0, "signalen": 0, "transcripten": 0})
        r["bezoeken"], r["km"], r["onderweg_min"] = c.get("verblijven", 0), c.get("km", 0.0), c.get("onderweg_min", 0)
    rijen = sorted(dagen.values(), key=lambda x: x["dag"], reverse=True)[:120]
    for r in rijen:
        r["personen"] = ", ".join(sorted(r["personen"]))[:200]
        r["spiegel_html"] = md(r["spiegel"]) if r["spiegel"] else ""
    return render_template("dagen.html", app_naam=APP_NAAM, rijen=rijen)


# --- kantoor: het virtuele kantoor. Elke afdeling een kamer, elke agent een
#     bureau met een figuurtje; de tekstballon is zijn laatste taak. Alles uit
#     de gegevens, dus een nieuwe agent krijgt vanzelf een bureau.
PROPS = (("regisseur", "megafoon"), ("ontwikkelaar", "schroevendraaier"), ("bode", "envelop"), ("contract", "pen"),
         ("agenda", "kalender"), ("fathom", "koptelefoon"), ("plaud", "microfoon"), ("locatie", "kompas"),
         ("icloud", "camera"), ("gezondheid", "hart"), ("levenscoach", "kopje"), ("dagbundel", "map"),
         ("mail", "brief"), ("zoom", "scherm"), ("whatsapp", "telefoon"), ("bel", "hoorn"), ("communicatie", "netwerk"))


def _kantoor_gegevens():
    conn = db()
    afd = [dict(r) for r in conn.execute("SELECT * FROM afdeling ORDER BY volgorde, naam").fetchall()]
    agents = [dict(r) for r in conn.execute(f"SELECT naam,label,type,rol,draait_op,cadans,prive FROM agent WHERE actief=1{zichtbaar_sql()} ORDER BY label").fetchall()]
    st = {r["naam"]: dict(r) for r in conn.execute("SELECT * FROM status").fetchall()}
    for a in agents:
        s = st.get(a["naam"])
        a["toestand"], a["taak"], a["detail"] = "onbekend", "", ""
        if s:
            leeftijd = leeftijd_min(s["ts"])
            a["toestand"] = toestand_met_cadans(a["naam"], a["cadans"], s["status"], leeftijd)
            a["taak"], a["detail"] = s["taak"] or "", (s["detail"] or "")[:90]
        a["prop"] = next((p for k, p in PROPS if k in a["naam"]), "laptop")
        a["kleur"] = sum(ord(c) for c in a["naam"]) % 6
    return afd, agents


@app.route("/kantoor")
def kantoor():
    afd, agents = _kantoor_gegevens()
    # kamers: Regie apart bovenaan; de rest in rijen van drie, met de agents per kamer
    kamers = []
    for a in afd:
        leden = [x for x in agents if x["type"] == a["naam"]]
        kamers.append({**a, "leden": leden})
    return render_template("kantoor.html", app_naam=APP_NAAM, kamers=kamers, mag_beslissen=mag_beslissen())


@app.route("/api/kantoor")
def api_kantoor():
    _, agents = _kantoor_gegevens()
    return jsonify(agents=[{k: a[k] for k in ("naam", "toestand", "taak", "detail")} for a in agents])


@app.route("/dag/<datum>")
def dag_pagina(datum):
    """Alles van één dag bij elkaar: overzicht en bundels van de Dagbundelaar, de
    spiegel van De Levenscoach, het locatiedagboek, de gesprekken, de afspraken,
    de foto's, het lichaam, de mails. Alleen beheer."""
    if not mag_beslissen() or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", datum):
        abort(404 if mag_beslissen() else 403)
    conn = db()
    items = []
    for it in conn.execute("SELECT * FROM klaarzet ORDER BY id").fetchall():
        inhoud = it["inhoud"] or ""
        try:
            d = json.loads(inhoud) if inhoud.startswith("{") else {}
        except ValueError:
            d = {}
        dag = (d.get("datum") or d.get("start") or it["sleutel"] or "")[:10]
        if dag == datum or (it["soort"] in ("dagbundel", "coaching", "locatie", "dagplan", "mail", "gezondheid") and it["sleutel"] == datum):
            r = dict(it)
            r["json"] = d
            r["tekst"] = inhoud if not inhoud.startswith("{") else ""
            items.append(r)
    def van_soort(*s):
        return [i for i in items if i["soort"] in s]
    # Een locatiedagboek van voor de startgrens van de meetreeks wordt niet meer getoond (opdracht v1.4).
    eerste = (_locatie("/api/beleid", {}) or {}).get("eerste_dag") or "9999-12-31"
    if datum < eerste:
        items = [i for i in items if i["soort"] != "locatie"]
    # J10, Z12 (ontwerp regie-zoom v1.2): een rij telt alleen als dubbel_van leeg is, zoals op de pagina Gesprekken en
    # in de dagenpagina. De tellende rijen eerst; de dubbels en de rijen buiten Mehdi's ruimte grijs eronder.
    gesprekken = conn.execute("SELECT * FROM gesprek_log WHERE datum=? ORDER BY COALESCE(dubbel_van, '')<>'', start",
                              (datum,)).fetchall()
    return render_template(
        "dag.html", app_naam=APP_NAAM, datum=datum, mdf=md,
        overzichten=van_soort("dagbundel"), spiegels=van_soort("coaching"), locaties=van_soort("locatie"),
        dagplannen=van_soort("dagplan"), afspraken=van_soort("afspraak"), fotos=van_soort("foto"),
        gezondheid=van_soort("gezondheid"), mails=van_soort("mail"), signalen=van_soort("signaal"),
        transcripten=van_soort("transcript", "werfbezoek"), gesprekken=gesprekken,
        gesprekken_tellend=sum(1 for g in gesprekken if not g["dubbel_van"] and telt_als_gesprek(g)),
        gesprekken_geen=sum(1 for g in gesprekken if not g["dubbel_van"] and not telt_als_gesprek(g)),
        week=_week_van(datum),
    )


# --- week: wat Mehdi in een ISO-week effectief deed, naast wat gepland stond (driehoeksoverleg 27-10-2026). Alleen
#     lezen, alleen beheer. Een runner zet per week een klaarzet-item weekoverzicht:<JJJJ-Www> met json klaar; deze
#     pagina rekent niets uit, ze toont het. Een getal null is onbekend en wordt een vraagteken.
WEEKDAGEN = ("Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo")


def week_naam(d):
    j, w, _ = d.isocalendar()
    return f"{j:04d}-W{w:02d}"


def _week_van(datum):
    """De ISO-week van een dag JJJJ-MM-DD, of None voor een datum die niet bestaat."""
    try:
        return week_naam(datetime.strptime(datum, "%Y-%m-%d").date())
    except ValueError:
        return None


def _week_maandag(week):
    """De maandag van week JJJJ-Www, of None als die week niet bestaat (W00, W54, W53 in een jaar zonder)."""
    m = re.fullmatch(r"(\d{4})-W(\d{2})", week)
    try:
        return datetime.fromisocalendar(int(m[1]), int(m[2]), 1).date() if m else None
    except ValueError:
        return None


def _wk_getal(v):
    """Een getal uit het weekoverzicht als tekst; None betekent onbekend. Ook NaN of iets anders dan een getal."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not -1e15 < v < 1e15:
        return None
    return str(int(v)) if float(v).is_integer() else f"{v:.1f}".replace(".", ",")


def _wk_uren(minuten):
    """Minuten als uren met een decimaal en een komma: 90 wordt 1,5."""
    return None if _wk_getal(minuten) is None else f"{minuten / 60:.1f}".replace(".", ",")


def _wk_dict(v):
    return v if isinstance(v, dict) else {}


def _week_blokken(e, totaal=False):
    """De cellen van een rij, in de volgorde van de kolommen op week.html: per blok de getallen, of voor WhatsApp en
    telefoon de stand over de breedte van het blok als die niet aangesloten is."""
    def blok(d, *sleutels, grijs=False):
        d = _wk_dict(d)
        return {"getallen": [_wk_getal(d.get(k)) for k in sleutels], "grijs": grijs}

    def kanaal(d, *sleutels):
        d = _wk_dict(d)
        if totaal:
            # zonder een aangesloten dag geen getallen, maar de stand van de week: niet aangesloten of onbekend (Codex
            # fase 2, punt 1: onbekend is nooit 'niet aangesloten')
            stand = (str(d.get("stand") or "niet aangesloten") if _wk_getal(d.get("aangesloten_dagen")) == "0" else None)
        else:
            stand = None if d.get("stand") == "aangesloten" else str(d.get("stand") or "onbekend")
        return {"stand": stand, "breedte": len(sleutels)} if stand else blok(d, *sleutels)

    mail = _wk_dict(e.get("mail"))
    return [blok(e.get("afspraken"), "bevestigd", "aanwijzing", "geen spoor", "privé"),
            blok(e.get("niet_gepland"), "gesprekken", "minuten"),
            blok(e.get("gesprekken"), "aantal", "minuten", "met_opname"),
            blok(e, "zoom_chats"),
            kanaal(e.get("whatsapp"), "gesprekken", "berichten", "oproepen", "minuten"),
            kanaal(e.get("telefoon"), "oproepen", "minuten"),
            blok(mail, "binnen", "verzonden", grijs=mail.get("onvolledig") is True)]


def laatste_week(nu):
    """De laatst afgesloten ISO-week in Brussel: die maakt De Dagbundelaar maandagnacht (weekoverzicht.vorige_week).
    De lopende week is nog niet samengevat (Codex fase 2, punt 3)."""
    vandaag = nu.astimezone(BRUSSEL).date()
    return week_naam(vandaag - timedelta(days=vandaag.weekday() + 7))


@app.route("/week")
def week_nu():
    if not mag_beslissen():
        abort(403)
    return redirect(url_for("week_pagina", week=laatste_week(datetime.now(BRUSSEL))))


@app.route("/week/<week>")
def week_pagina(week):
    maandag = _week_maandag(week) if mag_beslissen() else None
    if maandag is None:
        abort(404 if mag_beslissen() else 403)
    week = week_naam(maandag)
    # Vorige en volgende: maandag min of plus zeven dagen, dan de ISO-week daarvan (2026-W53 gaat naar 2027-W01).
    try:
        vorige = week_naam(maandag - timedelta(days=7))
    except OverflowError:
        vorige = None
    try:
        volgende = week_naam(maandag + timedelta(days=7))
    except OverflowError:
        volgende = None
    dagen = [maandag + timedelta(days=i) for i in range(7)]
    item = db().execute("SELECT inhoud FROM klaarzet WHERE uniek=? AND soort='weekoverzicht'",
                        ("weekoverzicht:" + week,)).fetchone()
    d, fout = {}, ""
    if item:
        try:
            d = json.loads(item["inhoud"] or "", parse_constant=lambda _c: None)
        except (ValueError, RecursionError):
            d = None
        if not isinstance(d, dict):
            d, fout = {}, "Het weekoverzicht van deze week staat op het bord, maar is niet leesbaar (geen geldige JSON)."
    per_dag = {str(e.get("dag")): e for e in (d.get("dagen") if isinstance(d.get("dagen"), list) else [])
               if isinstance(e, dict)}
    rijen = []
    for i, dag in enumerate(dagen):
        e = per_dag.get(dag.isoformat(), {})
        vast = e.get("vastgesteld") is True
        rijen.append({"dag": dag.isoformat(), "label": f"{WEEKDAGEN[i]} {dag:%d-%m}", "vastgesteld": vast,
                      "blokken": _week_blokken(e) if vast else []})
    totaal, planning = _wk_dict(d.get("totaal")), _wk_dict(d.get("planning"))
    totaal_blokken = _week_blokken(totaal, totaal=True)
    voorbehoud = totaal.get("voorbehoud") if isinstance(totaal.get("voorbehoud"), list) else []
    vastgesteld, aantal = _wk_getal(totaal.get("vastgesteld")), _wk_getal(totaal.get("dagen"))
    firmas = [{"naam": str(f.get("naam") or f.get("code") or "?"), "afspraken": _wk_getal(f.get("afspraken")),
               "uren": _wk_uren(f.get("minuten"))}
              for f in (planning.get("uren_per_firma") if isinstance(planning.get("uren_per_firma"), list) else [])
              if isinstance(f, dict)]
    return render_template(
        "week.html", app_naam=APP_NAAM, week=week, nummer=int(week[-2:]), van=f"{dagen[0]:%d-%m}",
        tot=f"{dagen[-1]:%d-%m}", vorige=vorige, volgende=volgende, aanwezig=bool(item) and not fout, fout=fout,
        rijen=rijen, totaal=totaal_blokken, voorbehoud=[str(x) for x in voorbehoud],
        vastgesteld=f"{vastgesteld} van {aantal} dagen vastgesteld" if vastgesteld and aantal else "",
        mail_onvolledig=any(b.get("grijs") for r in rijen for b in r["blokken"]) or any(b.get("grijs") for b in totaal_blokken),
        firmas=firmas, planning_afspraken=_wk_getal(planning.get("afspraken")),
        planning_uren=_wk_uren(planning.get("minuten")), planning_stand=planning.get("stand"),
        heeft_planning=bool(planning),
    )


# --- bronnen: per bron van de Dagbundelaar wat werkte en wat niet (Mehdi, 28-10-2026: "een dashboard om te zien wat
#     gewerkt heeft en wat niet, zodat we een per een kunnen oplossen"). Leest alleen wat er al is: de hartslag en de
#     noden van de wachten, en de dagtellingen uit de weekoverzichten. Geen nieuwe opslag, geen namen.
BRON_WACHTEN = (
    ("agenda-wacht", "Agenda", "VM"), ("locatie-wacht", "Locatie auto", "VM"), ("zoom-wacht", "Zoom", "VM"),
    ("fathom-wacht", "Fathom", "VM"), ("plaud-wacht", "Plaud", "VM"), ("mail-mch", "Mail mch", "VM"),
    ("mail-info-harc", "Mail info H-Architects", "VM"), ("mail-hinv", "Mail H-Invest", "VM"),
    ("mail-melo", "Mail Melodie", "VM"), ("mail-prive", "Mail hotmail", "VM"),
    ("whatsapp-wacht", "WhatsApp", "laptop"), ("belwacht", "Telefoon iPhone", "laptop"),
    ("icloud-wacht", "Foto's (alleen tijd en plaats)", "laptop"), ("dagbundelaar", "De Dagbundelaar zelf", "VM"),
)
BRON_DAGEN = 14
BRON_GROEN = ("volledig", "afgesloten", "aangesloten")
BRON_ORANJE = ("voorlopig", "onvolledig")


def bron_kleur(stand):
    """Groen, oranje of rood voor een stand uit de dagtelling; een ontbrekende stand is nooit groen."""
    if not isinstance(stand, str) or not stand:
        return "rood"
    return "groen" if stand in BRON_GROEN else "oranje" if stand in BRON_ORANJE else "rood"


def _bron_dag_cellen(e):
    """De cellen van één dag uit een dagtelling (weekoverzicht.dag_samenvatting)."""
    st = e.get("standen") if isinstance(e.get("standen"), dict) else {}
    mail = e.get("mail")
    if isinstance(mail, dict):
        mailstand = "onvolledig" if mail.get("onvolledig") else "volledig"
    else:
        mailstand = "niet gelezen"
    wa = e.get("whatsapp") if isinstance(e.get("whatsapp"), dict) else {}
    tel = e.get("telefoon") if isinstance(e.get("telefoon"), dict) else {}
    standen = {"agenda": st.get("agenda"), "locatie": st.get("locatie"), "zoom": st.get("zoom"), "mail": mailstand,
               "whatsapp": wa.get("stand"), "telefoon": tel.get("stand")}
    return {k: {"stand": str(v or "onbekend"), "kleur": bron_kleur(v)} for k, v in standen.items()}


def _bron_uit_tekst(tekst):
    """De cellen van een dag uit het dagbestand zelf (klaarzet vaststelling:<dag>), voor een dag die nog in geen
    weekoverzicht staat (de lopende week). Leest de regels onder "Over deze vaststelling" (dagbundelaar.py, over)."""
    deel = tekst.split("## Over deze vaststelling", 1)
    if len(deel) != 2:
        return None
    over = {}
    for regel in deel[1].splitlines():
        m = re.match(r"- (agenda|Zoom|locatie|mail|WhatsApp|telefoon): (.+)$", regel.strip())
        if m:
            over[m.group(1).lower()] = m.group(2).strip()
    if not over:
        return None
    if over.get("mail", "").startswith("niet gelezen"):
        over["mail"] = "niet gelezen"
    elif "mail" in over:
        over["mail"] = "onvolledig" if "verzonden (uniek over alle postvakken; onvolledig)" in deel[0] else "volledig"
    if over.get("locatie", "").startswith("niet gelezen"):
        over["locatie"] = "niet gelezen"
    e = {"standen": {k: over.get(k) for k in ("agenda", "zoom", "locatie")},
         "mail": None if over.get("mail") in (None, "niet gelezen") else {"onvolledig": over["mail"] == "onvolledig"},
         "whatsapp": {"stand": over.get("whatsapp")}, "telefoon": {"stand": over.get("telefoon")}}
    return _bron_dag_cellen(e)


@app.route("/bronnen")
def bronnen_pagina():
    if not mag_beslissen():
        abort(403)
    conn = db()
    st = {r["naam"]: r for r in conn.execute("SELECT * FROM status").fetchall()}
    agents = {r["naam"]: r for r in conn.execute("SELECT * FROM agent").fetchall()}
    nood = {}
    for r in conn.execute("SELECT naam, tekst FROM nood WHERE open=1 ORDER BY id").fetchall():
        nood.setdefault(r["naam"], []).append(r["tekst"])
    wachten = []
    for naam, label, waar in BRON_WACHTEN:
        s, a = st.get(naam), agents.get(naam)
        if not s:
            toestand, leeftijd = "onbekend", None
        else:
            leeftijd = leeftijd_min(s["ts"])
            toestand = toestand_met_cadans(naam, a["cadans"] if a else "", s["status"], leeftijd)
        kleur = "rood" if toestand in ("fout", "stil", "onbekend") or nood.get(naam) else "groen"
        wachten.append({"naam": naam, "label": label, "waar": waar, "toestand": STATUS_LABEL.get(toestand, toestand),
                        "leeftijd": None if leeftijd is None else int(leeftijd), "nood": nood.get(naam, []),
                        "kleur": kleur, "detail": (s["detail"] if s else "") or ""})
    # De dagtellingen staan in de weekoverzichten; drie weken dekken altijd veertien dagen.
    vandaag = datetime.now(BRUSSEL).date()
    dagen = [vandaag - timedelta(days=i) for i in range(1, BRON_DAGEN + 1)]
    per_dag = {}
    for wk in {week_naam(d) for d in dagen}:
        item = conn.execute("SELECT inhoud FROM klaarzet WHERE uniek=? AND soort='weekoverzicht'",
                            ("weekoverzicht:" + wk,)).fetchone()
        try:
            d = json.loads(item["inhoud"] or "", parse_constant=lambda _c: None) if item else {}
        except (ValueError, RecursionError):
            d = {}
        for e in (d.get("dagen") if isinstance(d, dict) and isinstance(d.get("dagen"), list) else []):
            if isinstance(e, dict) and e.get("vastgesteld") is True:
                per_dag[str(e.get("dag"))] = _bron_dag_cellen(e)
    # Een dag van de lopende week staat nog in geen weekoverzicht: dan uit het dagbestand op het bord.
    for x in dagen:
        if x.isoformat() not in per_dag:
            item = conn.execute("SELECT inhoud FROM klaarzet WHERE uniek=? AND soort='dagvaststelling'",
                                ("vaststelling:" + x.isoformat(),)).fetchone()
            cellen = _bron_uit_tekst(item["inhoud"] or "") if item else None
            if cellen:
                per_dag[x.isoformat()] = cellen
    rijen = [{"dag": x.isoformat(), "label": f"{WEEKDAGEN[x.weekday()]} {x:%d-%m}", "cellen": per_dag.get(x.isoformat())}
             for x in dagen]
    rood = [w for w in wachten if w["kleur"] == "rood"]
    return render_template("bronnen.html", app_naam=APP_NAAM, wachten=wachten, rijen=rijen, rood=rood,
                           kolommen=("agenda", "locatie", "zoom", "mail", "whatsapp", "telefoon"))


def _laatste_ronde(ts):
    """Wanneer de agent laatst iets meldde, in Brusselse tijd: '14:05' vandaag, anders '30-10 14:05'."""
    try:
        t = datetime.fromisoformat(ts)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        t = t.astimezone(ZoneInfo("Europe/Brussels"))
        vandaag = datetime.now(ZoneInfo("Europe/Brussels")).date()
        return t.strftime("%H:%M") if t.date() == vandaag else t.strftime("%d-%m %H:%M")
    except Exception:
        return ""


# --- organogram: getekend uit de gegevens zelf (afdelingen, agents, levert_aan)
@app.route("/organogram")
def organogram():
    conn = db()
    afd = [dict(r) for r in conn.execute("SELECT * FROM afdeling ORDER BY volgorde, naam").fetchall()]
    agents = [dict(r) for r in conn.execute(f"SELECT naam,label,type,rol,levert_aan,draait_op,cadans FROM agent WHERE actief=1{zichtbaar_sql()} ORDER BY label").fetchall()]
    st = {r["naam"]: r for r in conn.execute("SELECT * FROM status").fetchall()}
    for a in agents:
        a["levert_aan"] = _lijst(a["levert_aan"])
        s = st.get(a["naam"])
        a["toestand"] = "onbekend"
        a["laatste"] = _laatste_ronde(s["ts"]) if s else "nog nooit"
        if s:
            leeftijd = leeftijd_min(s["ts"])
            a["toestand"] = toestand_met_cadans(a["naam"], a["cadans"], s["status"], leeftijd)
    klaar = conn.execute("SELECT voor, COUNT(*) n FROM klaarzet WHERE status='klaar' GROUP BY voor").fetchall()
    return render_template("organogram.html", app_naam=APP_NAAM, afdelingen=afd, agents=agents,
                           klaar={r["voor"]: r["n"] for r in klaar}, mag_beslissen=mag_beslissen())


@app.route("/api/afdeling", methods=["POST"])
def api_afdeling():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    if not p.get("naam") or not p.get("label"):
        return jsonify(fout="naam en label vereist"), 400
    db().execute("INSERT INTO afdeling(naam, label, omschrijving, volgorde) VALUES(?,?,?,?) "
                 "ON CONFLICT(naam) DO UPDATE SET label=excluded.label, omschrijving=excluded.omschrijving, volgorde=excluded.volgorde",
                 (p["naam"], p["label"], p.get("omschrijving", ""), int(p.get("volgorde") or 100)))
    db().commit()
    return jsonify(ok=True)


@app.route("/agent/<naam>")
def detail(naam):
    a = db().execute(f"SELECT * FROM agent WHERE naam=?{zichtbaar_sql()}", (naam,)).fetchone()
    if not a:
        abort(404)
    s = db().execute("SELECT * FROM status WHERE naam=?", (naam,)).fetchone()
    vs = db().execute(
        "SELECT * FROM voorstel WHERE naam=? ORDER BY id DESC LIMIT 20", (naam,)
    ).fetchall()
    # Het werkverslag (wat de agent las, vond, besliste en schreef) is inhoud,
    # geen werkstatus. Daarom alleen voor beheer (admin/manager); de groep
    # agents ziet de kaart en de status, niet het verslag.
    verslag, onderwerpen = [], []
    # Wat de agent als laatste klaarzette (De Mehdi-agent, 31-10-2026): zijn takenlijst en zijn laatste verslag, zodat
    # zijn pagina toont wat hij voor Mehdi deed. Inhoud, dus net als het werkverslag alleen voor beheer.
    klaar_taken = klaar_verslag = None
    if mag_beslissen():
        klaar_taken = db().execute(
            "SELECT titel, inhoud, ts FROM klaarzet WHERE van=? AND soort='taken' ORDER BY id DESC LIMIT 1", (naam,)
        ).fetchone()
        klaar_verslag = db().execute(
            "SELECT titel, inhoud, ts FROM klaarzet WHERE van=? AND soort='verslag' ORDER BY id DESC LIMIT 1", (naam,)
        ).fetchone()
        verslag = db().execute(
            "SELECT * FROM logboek WHERE naam=? ORDER BY id DESC LIMIT 300", (naam,)
        ).fetchall()
        onderwerpen = db().execute(
            "SELECT onderwerp, MAX(ts) laatst, COUNT(*) n FROM logboek WHERE naam=? "
            "AND onderwerp<>'' GROUP BY onderwerp ORDER BY laatst DESC LIMIT 40", (naam,)
        ).fetchall()
    versies = db().execute(
        "SELECT id, wie, ts, length(tekst) n FROM werkwijze_versie WHERE naam=? ORDER BY id DESC LIMIT 10", (naam,)
    ).fetchall()
    return render_template(
        "detail.html", app_naam=APP_NAAM, a=a, s=s, voorstellen=vs,
        opnieuw_voorleggen={v["id"] for v in vs if kan_opnieuw_voorleggen(db(), v["id"])},
        mag=_lijst(a["mag"]), grenzen=_lijst(a["grenzen"]), tools=_lijst(a["tools"]),
        mag_beslissen=mag_beslissen(), verslag=verslag, onderwerpen=onderwerpen,
        gekozen=request.args.get("onderwerp", ""),
        werkwijze_html=md(a["werkwijze"]), kennis_html=md(a["kennis"]), versies=versies,
        bewerken=request.args.get("bewerken") == "1",
        gesprekken=gesprekken_for_detail(naam) if mag_beslissen() else [], mdf=md,
        klaar_taken=klaar_taken, klaar_verslag=klaar_verslag, mdk=md_klaargezet,
    )


def gesprekken_for_detail(naam):
    return gesprekken_voor(naam, 20)


# --- werkwijze: het volledige proces van een agent, door beheer te bewerken
#     op het bord. De agent haalt het elke ronde op (GET, token) en volgt het.
@app.route("/agent/<naam>/werkwijze", methods=["POST"])
def werkwijze_opslaan(naam):
    if not mag_beslissen():
        abort(403)
    tekst = (request.form.get("werkwijze") or "").replace("\r\n", "\n").strip()
    conn = db()
    if not conn.execute("SELECT 1 FROM agent WHERE naam=?", (naam,)).fetchone():
        abort(404)
    oud = conn.execute("SELECT werkwijze FROM agent WHERE naam=?", (naam,)).fetchone()["werkwijze"] or ""
    if oud.strip() != tekst:
        conn.execute("INSERT INTO werkwijze_versie(naam, tekst, wie, ts) VALUES(?,?,?,?)",
                     (naam, oud, "vorige versie", nu()))
        conn.execute("UPDATE agent SET werkwijze=? WHERE naam=?", (tekst, naam))
        conn.execute("INSERT INTO handeling(naam, wat, ts) VALUES(?,?,?)",
                     (naam, f"werkwijze bijgewerkt door {gebruiker()}", nu()))
        conn.commit()
    return redirect(url_for("detail", naam=naam) + "#werkwijze")


@app.route("/api/agent/<naam>/werkwijze")
def api_werkwijze(naam):
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    a = db().execute("SELECT werkwijze,mandaat FROM agent WHERE naam=?", (naam,)).fetchone()
    if not a:
        abort(404)
    return jsonify(naam=naam, werkwijze=a["werkwijze"] or "", mandaat=a["mandaat"] or "")


@app.route("/api/agent/<naam>/werkwijze", methods=["POST"])
def api_werkwijze_zetten(naam):
    """Voor de generator: de eerste werkwijze zetten. Overschrijft niet wat
    beheer intussen op het bord bewerkte, tenzij 'overschrijf' waar is."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    conn = db()
    a = conn.execute("SELECT werkwijze FROM agent WHERE naam=?", (naam,)).fetchone()
    if not a:
        abort(404)
    if (a["werkwijze"] or "").strip() and not p.get("overschrijf"):
        return jsonify(ok=False, reden="werkwijze bestaat al op het bord; niet overschreven")
    conn.execute("INSERT INTO werkwijze_versie(naam, tekst, wie, ts) VALUES(?,?,?,?)",
                 (naam, a["werkwijze"] or "", "vorige versie", nu()))
    tekst = (p.get("werkwijze") or "").strip()
    mandaat = p.get("mandaat")
    if mandaat is not None and (not isinstance(mandaat, str) or not mandaat.strip() or len(mandaat) > 2000):
        abort(400)
    if mandaat is None:
        conn.execute("UPDATE agent SET werkwijze=? WHERE naam=?", (tekst, naam))
    else:
        conn.execute("UPDATE agent SET werkwijze=?,mandaat=? WHERE naam=?", (tekst, mandaat.strip(), naam))
    conn.commit()
    return jsonify(ok=True)


# --- kennis: de agent meldt wat hij in zijn laatste ronde als instructie las,
#     zodat beheer op het bord ziet wat hij wist toen hij werkte.
@app.route("/api/agent/<naam>/kennis", methods=["POST"])
def api_kennis(naam):
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    conn = db()
    if not conn.execute("SELECT 1 FROM agent WHERE naam=?", (naam,)).fetchone():
        abort(404)
    conn.execute("UPDATE agent SET kennis=?, kennis_ts=?, kennis_bron=? WHERE naam=?",
                 (str(p.get("kennis") or "")[:200000], nu(), str(p.get("bron") or "")[:300], naam))
    conn.commit()
    return jsonify(ok=True)


# --- werkverslag: een agent legt vast wat hij las, vond, besliste en schreef.
#     Token-gated. Eén regel per stap; 'detail' mag langer zijn (bv. het plan).
@app.route("/api/logboek", methods=["POST"])
def api_logboek():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    regels = p.get("regels") if isinstance(p.get("regels"), list) else [p]
    conn = db()
    n = 0
    for r in regels:
        naam, stap, tekst = (r.get("naam") or "").strip(), (r.get("stap") or "").strip(), (r.get("tekst") or "").strip()
        if not naam or not stap or not tekst:
            continue
        conn.execute(
            "INSERT INTO logboek(naam, onderwerp, stap, tekst, detail, ts) VALUES(?,?,?,?,?,?)",
            (naam, (r.get("onderwerp") or "")[:200], stap[:40], tekst[:1000],
             str(r.get("detail") or "")[:20000], nu()),
        )
        n += 1
    conn.commit()
    return jsonify(ok=True, geschreven=n)


# --- hartslag: de agent-runner meldt hier zijn status. Deze route passeert de
#     forward-auth (nginx laat hem door); we toetsen zelf het token. ----------
# --- projectnummers: reservering per voorstel (WP2b, 12-10-2026) -----------
# Aanleiding: 2617 stond tegelijk in drie open voorstellen voor drie deals (voorstellen 25, 26 en 27, 05 tot
# 10-10-2026). De agent las vier bronnen, maar geen open voorstellen, en het bord ontdubbelde alleen per deal.
# Nu houdt een open of goedgekeurd dealtitel-voorstel zijn nummer vast; de unieke indexen op nummerreservering
# zijn de grendel, BEGIN IMMEDIATE de gedeelde databankgrendel. Alleen H-Architects. Een reservering komt vrij
# wanneer het voorstel geweigerd, vervangen, mislukt of overgeslagen is; nooit vanzelf na een tijd.
NUMMER_RUNBOOK = "pipedrive-dealtitel"
NUMMER_FIRMA = "harchitects"
NUMMER_BEZET = ("open", "goedgekeurd")


def nummer_uit_parameters(params):
    """(nummer, deal_id) van een dealtitel-voorstel. Het nummer staat expliciet of vooraan in de titel; staan
    beide er en verschillen ze, dan is er geen geldig nummer."""
    if not isinstance(params, dict) or params.get("deal_id") in (None, ""):
        return None, None
    deal = str(params.get("deal_id")).strip()
    m = re.match(r"^(\d{4})\s+\S", str(params.get("titel") or "").strip())
    uit_titel = m.group(1) if m else ""
    nummer = str(params.get("nummer") or uit_titel).strip()
    if not re.fullmatch(r"\d{4}", nummer) or (uit_titel and uit_titel != nummer):
        return None, deal
    return nummer, deal


def bezette_nummers(conn, firma=NUMMER_FIRMA):
    """Elk nummer dat een open of goedgekeurd dealtitel-voorstel vasthoudt. Uit de reserveringen, en voor
    voorstellen van vóór WP2b (zonder reservering) afgeleid uit hun parameters: geen historische migratie,
    zodat oude dubbele voorstellen zichtbaar blijven als conflict in plaats van stil opgelost."""
    uit, gedekt = [], set()
    for r in conn.execute(
            "SELECT r.nummer, r.deal_id, r.voorstel_id, v.status FROM nummerreservering r "
            "JOIN voorstel v ON v.id = r.voorstel_id WHERE r.firma=? AND r.actief=1 ORDER BY r.voorstel_id", (firma,)):
        uit.append({"nummer": r["nummer"], "deal_id": r["deal_id"], "voorstel_id": r["voorstel_id"],
                    "status": r["status"], "bron": "reservering"})
        gedekt.add(r["voorstel_id"])
    if firma != NUMMER_FIRMA:
        return uit
    for r in conn.execute("SELECT id, parameters, status FROM voorstel WHERE runbook=? AND status IN (?, ?) "
                          "ORDER BY id", (NUMMER_RUNBOOK, *NUMMER_BEZET)):
        if r["id"] in gedekt:
            continue
        try:
            params = json.loads(r["parameters"] or "{}")
        except ValueError:
            continue
        nummer, deal = nummer_uit_parameters(params)
        if nummer and str(params.get("firma") or NUMMER_FIRMA) == firma:
            uit.append({"nummer": nummer, "deal_id": deal, "voorstel_id": r["id"], "status": r["status"],
                        "bron": "voorstel zonder reservering"})
    return uit


def reservering_volgt_voorstel(conn, vid, reden=""):
    """Geeft de reservering vrij zodra het voorstel niet meer open of goedgekeurd is."""
    rij = conn.execute("SELECT status FROM voorstel WHERE id=?", (vid,)).fetchone()
    if rij and rij["status"] not in NUMMER_BEZET:
        conn.execute("UPDATE nummerreservering SET actief=0, vrij_ts=?, vrij_reden=? WHERE voorstel_id=? AND actief=1",
                     (nu(), (reden or f"voorstel {rij['status']}")[:300], vid))


def _eerder_geweigerd(conn, nummer, deal):
    for r in conn.execute("SELECT id, parameters FROM voorstel WHERE runbook=? AND status='geweigerd'", (NUMMER_RUNBOOK,)):
        try:
            if nummer_uit_parameters(json.loads(r["parameters"] or "{}")) == (nummer, deal):
                return r["id"]
        except ValueError:
            continue
    return None


def nummervoorstel_bewaren(conn, naam, v):
    """Bewaart een dealtitel-voorstel en reserveert zijn nummer in één transactie onder schrijfgrendel.
    Uitkomst: gereserveerd (nieuw voorstel), bestaat (zelfde deal en nummer: idempotent), bezet (ander deal
    houdt het nummer vast), eerder_geweigerd, of geweigerd (ongeldig, andere firma, goedgekeurd voorstel)."""
    params = v.get("parameters") if isinstance(v.get("parameters"), dict) else {}
    firma = str(params.get("firma") or NUMMER_FIRMA)
    if firma != NUMMER_FIRMA:
        return {"bewaard": False, "uitkomst": "geweigerd",
                "reden": f"firma '{firma}': deze route reserveert alleen H-Architects-nummers"}
    nummer, deal = nummer_uit_parameters(params)
    if not nummer:
        return {"bewaard": False, "uitkomst": "geweigerd", "reden": "geen geldig projectnummer of geen deal in het voorstel"}
    params = {**params, "nummer": nummer, "firma": firma}
    conn.execute("BEGIN IMMEDIATE")
    try:
        bezet = bezette_nummers(conn)
        eigen = [b for b in bezet if b["deal_id"] == deal]
        zelfde = [b for b in eigen if b["nummer"] == nummer]
        if zelfde:
            conn.rollback()
            return {"bewaard": False, "uitkomst": "bestaat", "nummer": nummer, "voorstel_id": zelfde[0]["voorstel_id"],
                    "status": zelfde[0]["status"]}
        elders = [b for b in bezet if b["nummer"] == nummer and b["deal_id"] != deal]
        if elders:
            conn.rollback()
            return {"bewaard": False, "uitkomst": "bezet", "nummer": nummer, "bezet_door": elders}
        geweigerd = _eerder_geweigerd(conn, nummer, deal)
        if geweigerd:
            conn.rollback()
            return {"bewaard": False, "uitkomst": "eerder_geweigerd", "nummer": nummer, "voorstel_id": geweigerd}
        goedgekeurd = [b for b in eigen if b["status"] == "goedgekeurd"]
        if goedgekeurd:
            conn.rollback()
            return {"bewaard": False, "uitkomst": "geweigerd", "nummer": nummer,
                    "reden": f"voorstel {goedgekeurd[0]['voorstel_id']} voor deze deal is al goedgekeurd met nummer "
                             f"{goedgekeurd[0]['nummer']}; een goedgekeurd voorstel verandert niet stilzwijgend"}
        for b in eigen:   # een open voorstel met een ander nummer voor dezelfde deal vervalt (regel deal 14531)
            conn.execute("UPDATE voorstel SET status='vervallen', besluit_door='systeem', besluit_ts=?, bewijs=? "
                         "WHERE id=? AND status='open'", (nu(), f"vervangen door een nieuw voorstel: {v['actie']}", b["voorstel_id"]))
            reservering_volgt_voorstel(conn, b["voorstel_id"], f"vervangen door nummer {nummer}")
        vid = conn.execute(
            "INSERT INTO voorstel(naam,actie,doel,reden,parameters,runbook,ts) VALUES(?,?,?,?,?,?,?)",
            (naam, v["actie"], v.get("doel", ""), v.get("reden", ""), json.dumps(params), NUMMER_RUNBOOK, nu())).lastrowid
        conn.execute("INSERT INTO nummerreservering(firma,reeks,nummer,deal_id,voorstel_id,actief,ts) VALUES(?,?,?,?,?,1,?)",
                     (firma, nummer[:2], nummer, deal, vid, nu()))
        conn.commit()
        return {"bewaard": True, "uitkomst": "gereserveerd", "nummer": nummer, "voorstel_id": vid}
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return {"bewaard": False, "uitkomst": "bezet", "nummer": nummer, "reden": f"grendel: {e}"}
    except Exception:
        conn.rollback()
        raise


def nummercontrole(conn, vid, voor_akkoord=False):
    """Mag dit dealtitel-voorstel (nog) door? Bij akkoord moet het open zijn, bij uitvoering goedgekeurd, en
    geen andere deal mag hetzelfde nummer vasthouden. Geeft een dict met ok, reden en bewijs."""
    rij = conn.execute("SELECT id, runbook, parameters, status FROM voorstel WHERE id=?", (vid,)).fetchone()
    if not rij or rij["runbook"] != NUMMER_RUNBOOK:
        return {"ok": False, "voorstel_id": vid, "reden": "geen dealtitel-voorstel met dit id"}
    try:
        params = json.loads(rij["parameters"] or "{}")
    except ValueError:
        params = {}
    nummer, deal = nummer_uit_parameters(params)
    uit = {"voorstel_id": vid, "nummer": nummer, "deal_id": deal, "status": rij["status"],
           "firma": str(params.get("firma") or NUMMER_FIRMA)}
    if uit["firma"] != NUMMER_FIRMA:
        return {**uit, "ok": False, "reden": f"firma '{uit['firma']}' valt buiten deze route"}
    if not nummer:
        return {**uit, "ok": False, "reden": "geen geldig projectnummer in het voorstel"}
    verwacht = "open" if voor_akkoord else "goedgekeurd"
    if rij["status"] != verwacht:
        return {**uit, "ok": False, "reden": f"voorstel staat op '{rij['status']}', niet op '{verwacht}'"}
    bezet = bezette_nummers(conn)
    uit["elders"] = [b for b in bezet if b["nummer"] == nummer and b["voorstel_id"] != vid and b["deal_id"] != deal]
    uit["gereserveerd"] = bool(conn.execute(
        "SELECT 1 FROM nummerreservering WHERE voorstel_id=? AND actief=1", (vid,)).fetchone())
    if uit["elders"]:
        return {**uit, "ok": False, "reden": f"nummer {nummer} staat ook in voorstel "
                + ", ".join(str(b["voorstel_id"]) for b in uit["elders"]) + " voor een andere deal"}
    if not voor_akkoord and not uit["gereserveerd"]:
        # Goedgekeurd vóór WP2b, zonder reservering: nooit schrijven. Het runbook mag het alleen afsluiten als
        # de titel al exact op de deal staat (reconciliatie); anders opnieuw voorleggen.
        return {**uit, "ok": False, "reconciliatie": True,
                "reden": "het goedgekeurde voorstel heeft geen actieve reservering (van vóór WP2b): alleen "
                         "afsluiten als de titel al exact klopt",
                "herstel": f"Opnieuw voorleggen: POST /voorstel/{vid}/opnieuw-voorleggen (beheer), daarna opnieuw goedkeuren"}
    return {**uit, "ok": True, "reden": ""}


def kan_opnieuw_voorleggen(conn, vid):
    """Alleen een goedgekeurd dealtitel-voorstel zonder actieve reservering (van vóór WP2b) gaat terug naar open."""
    rij = conn.execute("SELECT runbook, status FROM voorstel WHERE id=?", (vid,)).fetchone()
    return bool(rij and rij["runbook"] == NUMMER_RUNBOOK and rij["status"] == "goedgekeurd" and not conn.execute(
        "SELECT 1 FROM nummerreservering WHERE voorstel_id=? AND actief=1", (vid,)).fetchone())


def nummervoorstel_goedkeuren(conn, vid, wie):
    """Akkoord op een dealtitel-voorstel: onder schrijfgrendel opnieuw op conflict controleren, de reservering
    vastleggen (ook voor een voorstel van vóór WP2b) en pas dan goedkeuren. Geeft (ok, controle)."""
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        c = nummercontrole(conn, vid, voor_akkoord=True)
        if not c["ok"]:
            conn.rollback()
            return False, c
        if not c["gereserveerd"]:
            conn.execute("INSERT INTO nummerreservering(firma,reeks,nummer,deal_id,voorstel_id,actief,ts) "
                         "VALUES(?,?,?,?,?,1,?)", (NUMMER_FIRMA, c["nummer"][:2], c["nummer"], c["deal_id"], vid, nu()))
        conn.execute("UPDATE voorstel SET status='goedgekeurd', besluit_door=?, besluit_ts=? WHERE id=? AND status='open'",
                     (wie, nu(), vid))
        conn.commit()
        return True, c
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return False, {"ok": False, "voorstel_id": vid, "reden": f"grendel: nummer of deal al gereserveerd ({e})"}
    except Exception:
        conn.rollback()
        raise


def nummerconflicten_op_bord(conn):
    """Per open dealtitel-voorstel de andere voorstellen die hetzelfde nummer vasthouden (zonder klantnamen)."""
    bezet = bezette_nummers(conn)
    uit = {}
    for b in bezet:
        anderen = [x["voorstel_id"] for x in bezet if x["nummer"] == b["nummer"] and x["deal_id"] != b["deal_id"]]
        if anderen:
            uit[b["voorstel_id"]] = {"nummer": b["nummer"], "anderen": anderen}
    return uit


@app.route("/api/nummerreserveringen")
def api_nummerreserveringen():
    """Bezette H-A-nummers voor de Contracten-agent (vijfde nummerbron). Token-gated, alleen lezen."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    firma = request.args.get("firma", NUMMER_FIRMA)
    if firma != NUMMER_FIRMA:
        return jsonify(fout=f"firma '{firma}' valt buiten de nummerreservering"), 400
    bezet = bezette_nummers(db())
    return jsonify(firma=firma, volledig=True, aantal=len(bezet), bezet=bezet)


@app.route("/api/nummercontrole")
def api_nummercontrole():
    """Controle vlak vóór uitvoering (runbook pipedrive-dealtitel). Token-gated, alleen lezen."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    try:
        vid = int(request.args.get("voorstel_id", ""))
    except ValueError:
        return jsonify(ok=False, reden="voorstel_id vereist"), 400
    return jsonify(nummercontrole(db(), vid))


@app.route("/agent-status", methods=["POST"])
def agent_status():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    naam = (p.get("naam") or "").strip()
    status = (p.get("status") or "").strip()
    if not naam or status not in STILTE_MIN:
        return jsonify(fout="naam en geldige status vereist"), 400
    conn = db()
    conn.execute(
        "INSERT INTO status(naam,status,taak,detail,tokens,ts) VALUES(?,?,?,?,?,?) "
        "ON CONFLICT(naam) DO UPDATE SET status=excluded.status, taak=excluded.taak, "
        "detail=excluded.detail, tokens=excluded.tokens, ts=excluded.ts",
        (naam, status, p.get("taak", ""), p.get("detail", ""), p.get("tokens"), nu()),
    )
    # Wat de agent nodig heeft of wat bij hem niet werkt: hij meldt de volledige
    # lijst; wat er niet meer in staat is opgelost. Zo ziet beheer in één
    # overzicht waar geholpen moet worden.
    if isinstance(p.get("nood"), list):
        nieuw = [(str(n.get("tekst") if isinstance(n, dict) else n).strip()[:400],
                  (n.get("wie") if isinstance(n, dict) else "mehdi") or "mehdi") for n in p["nood"]]
        nieuw = [(t, w) for t, w in nieuw if t]
        open_ = {r["tekst"]: r["id"] for r in conn.execute("SELECT id, tekst FROM nood WHERE naam=? AND open=1", (naam,)).fetchall()}
        for t, w in nieuw:
            if t not in open_:
                conn.execute("INSERT INTO nood(naam, tekst, wie, ts) VALUES(?,?,?,?)", (naam, t, w, nu()))
        # nood_sluiten false: de agent wist niet welke van zijn noden nog gelden (bord.Ronde.noden_onbekend); de nieuwe
        # komen erbij, niets sluit (De Dagbundelaar, Codex-controle mailnood 5, 27-10-2026)
        for t, nid in open_.items():
            if p.get("nood_sluiten") is not False and t not in {x for x, _ in nieuw}:
                conn.execute("UPDATE nood SET open=0, opgelost_ts=? WHERE id=?", (nu(), nid))
    # Optioneel voorstel meegestuurd (mens-in-de-lus).
    v = p.get("voorstel")
    if isinstance(v, dict) and v.get("actie") and v.get("runbook") == NUMMER_RUNBOOK:
        # Een projectnummer gaat langs de reservering (WP2b), in een eigen transactie onder schrijfgrendel.
        # De agent leest de uitkomst: alleen 'gereserveerd' of 'bestaat' betekent dat het voorstel er staat.
        conn.commit()
        return jsonify(ok=True, voorstel=nummervoorstel_bewaren(conn, naam, v))
    if isinstance(v, dict) and v.get("actie"):
        params = v.get("parameters")
        pjson = json.dumps(params) if params else ""
        # Hetzelfde voorstel (agent, runbook, actie en parameters) dat al open staat, goedgekeurd op uitvoering
        # wacht of door Mehdi geweigerd is, zet je niet opnieuw: een agent die elke ronde voorstelt, zou hem
        # anders elke ronde opnieuw vragen (werfverslag-voorbereider, opruiming van dubbele rijen, 24-09-2026).
        zelfde = pjson and conn.execute(
            "SELECT id FROM voorstel WHERE naam=? AND runbook=? AND actie=? AND parameters=? "
            "AND status IN ('open','goedgekeurd','geweigerd')", (naam, v.get("runbook", ""), v["actie"], pjson)).fetchone()
        # Eén open voorstel per agent, runbook en deal (of sleutel): een nieuw voorstel
        # (bv. een ander nummer) vervangt het vorige, anders blijven er twee
        # tegenstrijdige voorstellen open staan (deal 14531: 2616 en 5609).
        deal = None
        if isinstance(params, dict):
            deal = params.get("deal_id") if params.get("deal_id") is not None else params.get("sleutel")
        if deal is not None and v.get("runbook") and not zelfde:
            for r in conn.execute("SELECT id, parameters FROM voorstel WHERE naam=? AND runbook=? AND status='open'",
                                  (naam, v["runbook"])).fetchall():
                try:
                    oud_p = json.loads(r["parameters"] or "{}")
                    oud_deal = oud_p.get("deal_id") if oud_p.get("deal_id") is not None else oud_p.get("sleutel")
                except Exception:
                    oud_deal = None
                if str(oud_deal) == str(deal):
                    conn.execute("UPDATE voorstel SET status='vervallen', besluit_door='systeem', besluit_ts=?, "
                                 "bewijs=? WHERE id=?", (nu(), f"vervangen door een nieuw voorstel: {v['actie']}", r["id"]))
        if not zelfde:
            conn.execute(
                "INSERT INTO voorstel(naam,actie,doel,reden,parameters,runbook,ts) "
                "VALUES(?,?,?,?,?,?,?)",
                (naam, v["actie"], v.get("doel", ""), v.get("reden", ""), pjson, v.get("runbook", ""), nu()),
            )
    conn.commit()
    return jsonify(ok=True)


# --- registratie: de generator registreert of werkt een agent bij. Token-gated.
@app.route("/api/agent", methods=["POST"])
def api_agent():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    naam = (p.get("naam") or "").strip()
    if not naam or not p.get("label"):
        return jsonify(fout="naam en label vereist"), 400
    conn = db()
    conn.execute(
        "INSERT INTO agent(naam,label,type,rol,mandaat,mag,grenzen,cadans,tools,"
        "eigenaar,actief,aangemaakt,levert_aan,draait_op) VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?,?) "
        "ON CONFLICT(naam) DO UPDATE SET label=excluded.label, type=excluded.type, "
        "rol=excluded.rol, mandaat=excluded.mandaat, mag=excluded.mag, "
        "grenzen=excluded.grenzen, cadans=excluded.cadans, tools=excluded.tools, "
        "eigenaar=excluded.eigenaar, actief=1, levert_aan=excluded.levert_aan, draait_op=excluded.draait_op",
        (naam, p["label"], "dagbundelaar" if naam in DAGBUNDELAAR_AGENTS else p.get("type", ""),
         p.get("rol", ""), p.get("mandaat", ""),
         json.dumps(p.get("mag", [])), json.dumps(p.get("grenzen", [])),
         p.get("cadans", ""), json.dumps(p.get("tools", [])),
         p.get("eigenaar", "mehdi"), nu(), json.dumps(p.get("levert_aan", [])), p.get("draait_op", "VM")),
    )
    if "prive" in p:
        conn.execute("UPDATE agent SET prive=? WHERE naam=?", (1 if p.get("prive") else 0, naam))
    conn.commit()
    return jsonify(ok=True, naam=naam)


@app.route("/api/agents")
def api_agents():
    rijen = db().execute("SELECT naam,label,type,rol,cadans,eigenaar,actief FROM agent").fetchall()
    return jsonify([dict(r) for r in rijen])


# --- beslissen over een voorstel (alleen beheer) ---------------------------
@app.route("/voorstel/<int:vid>/besluit", methods=["POST"])
def besluit(vid):
    if not mag_beslissen():
        abort(403)
    keuze = request.form.get("keuze")
    if keuze not in ("goedgekeurd", "geweigerd"):
        abort(400)
    conn = db()
    rij = conn.execute("SELECT runbook FROM voorstel WHERE id=?", (vid,)).fetchone()
    if keuze == "goedgekeurd" and rij and rij["runbook"] == NUMMER_RUNBOOK:
        # WP2b: bij akkoord opnieuw op conflict controleren; een betwist nummer wordt niet goedgekeurd.
        ok, controle = nummervoorstel_goedkeuren(conn, vid, gebruiker())
        if not ok:
            terug = request.referrer or url_for("bord")
            return (f"<!doctype html><meta charset='utf-8'><title>Niet goedgekeurd</title>"
                    f"<p><b>Voorstel {vid} is niet goedgekeurd.</b> {escape(controle.get('reden', ''))}</p>"
                    f"<p>Weiger eerst de andere voorstellen met dit nummer, of laat een nieuw nummer voorstellen.</p>"
                    f"<p><a href='{escape(terug)}'>Terug naar het bord</a></p>"), 409
        return redirect(request.referrer or url_for("bord"))
    conn.execute(
        "UPDATE voorstel SET status=?, besluit_door=?, besluit_ts=? WHERE id=? AND status='open'",
        (keuze, gebruiker(), nu(), vid),
    )
    reservering_volgt_voorstel(conn, vid, f"{keuze} door {gebruiker()}")
    conn.commit()
    return redirect(request.referrer or url_for("bord"))


@app.route("/voorstel/<int:vid>/opnieuw-voorleggen", methods=["POST"])
def opnieuw_voorleggen(vid):
    """Herstelactie voor een goedgekeurd dealtitel-voorstel zonder reservering (van vóór WP2b): terug naar open,
    met de geschiedenis in het bewijs en in de handelingen. Opnieuw goedkeuren legt dan de reservering vast en
    controleert op conflict. Weigeren geldt alleen voor open voorstellen; dit is de weg voor goedgekeurde."""
    if not mag_beslissen():
        abort(403)
    conn = db()
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    if not kan_opnieuw_voorleggen(conn, vid):
        conn.rollback()
        return ("<!doctype html><meta charset='utf-8'><p>Alleen een goedgekeurd projectnummervoorstel zonder "
                "reservering kan opnieuw voorgelegd worden.</p>"), 409
    v = conn.execute("SELECT naam, actie, besluit_door, besluit_ts, bewijs FROM voorstel WHERE id=?", (vid,)).fetchone()
    spoor = (f"opnieuw voorgelegd door {gebruiker()} op {nu()}; eerder goedgekeurd door {v['besluit_door']} "
             f"op {v['besluit_ts']}")
    conn.execute("UPDATE voorstel SET status='open', besluit_door='', besluit_ts='', bewijs=? WHERE id=?",
                 (((v["bewijs"] or "") + "\n" + spoor).strip()[:4400], vid))
    conn.execute("INSERT INTO handeling(naam, wat, ts) VALUES(?,?,?)",
                 (v["naam"], f"voorstel {vid} '{v['actie']}': {spoor}", nu()))
    conn.commit()
    return redirect(request.referrer or url_for("bord"))


# --- uitvoerder: haalt goedgekeurde voorstellen MET parameters op en meldt de
#     uitkomst terug. Token-gated. Uitvoeren gebeurt nooit hier maar in
#     mijnagents-runner/mijnagents_uitvoerder.py (allowlist van runbooks). ---
@app.route("/api/uitvoer-wacht")
def uitvoer_wacht():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    rijen = db().execute(
        "SELECT id, naam, actie, runbook, parameters FROM voorstel "
        "WHERE status='goedgekeurd' AND parameters<>'' ORDER BY id"
    ).fetchall()
    return jsonify(wacht=[dict(r) for r in rijen])


@app.route("/uitvoer-resultaat", methods=["POST"])
def uitvoer_resultaat():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    vid = p.get("id")
    uitvoering = p.get("uitvoering")
    nieuw = {"gelukt": "uitgevoerd", "mislukt": "mislukt", "overgeslagen": "overgeslagen"}.get(uitvoering)
    if not vid or not nieuw:
        return jsonify(fout="id en uitvoering (gelukt|mislukt|overgeslagen) vereist"), 400
    conn = db()
    v = conn.execute("SELECT naam, actie FROM voorstel WHERE id=? AND status='goedgekeurd'", (vid,)).fetchone()
    if not v:
        return jsonify(fout="geen goedgekeurd voorstel met dit id"), 404
    bewijs = (p.get("detail", "") or "")[:400]
    if p.get("bewijs"):
        bewijs += "\n" + str(p["bewijs"])[:4000]
    conn.execute("UPDATE voorstel SET status=?, bewijs=? WHERE id=?", (nieuw, bewijs, vid))
    reservering_volgt_voorstel(conn, vid, f"uitvoering {nieuw}")
    conn.execute("INSERT INTO handeling(naam, wat, ts) VALUES(?,?,?)",
                 (v["naam"], f"voorstel {vid} '{v['actie']}': {nieuw}", nu()))
    conn.commit()
    return jsonify(ok=True, status=nieuw)


# --- gesprek: beheer zegt iets tegen een agent (of tegen de hoofdagent);
#     de hoofdagent-runner haalt open berichten op en antwoordt op het bord.
def gesprekken_voor(aan, limiet=30):
    return db().execute(
        "SELECT * FROM gesprek WHERE aan=? ORDER BY id DESC LIMIT ?", (aan, limiet)
    ).fetchall()


@app.route("/gesprek", methods=["POST"])
def gesprek_sturen():
    if not mag_beslissen():
        abort(403)
    aan = (request.form.get("aan") or "regisseur").strip()
    tekst = (request.form.get("tekst") or "").strip()
    if not tekst:
        abort(400)
    if aan != "regisseur" and not db().execute("SELECT 1 FROM agent WHERE naam=?", (aan,)).fetchone():
        abort(404)
    db().execute("INSERT INTO gesprek(aan, van, tekst, ts) VALUES(?,?,?,?)", (aan, gebruiker(), tekst[:8000], nu()))
    db().commit()
    doel = url_for("bord") if aan == "regisseur" else url_for("detail", naam=aan)
    return redirect(doel + "#gesprek")


@app.route("/api/gesprek", methods=["POST"])
def api_gesprek_sturen():
    """Voor De Bode: een bericht van Mehdi uit Telegram als gesprek op het bord."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    aan = (p.get("aan") or "regisseur").strip()
    tekst = (p.get("tekst") or "").strip()
    if not tekst:
        return jsonify(fout="tekst vereist"), 400
    conn = db()
    if aan != "regisseur" and not conn.execute("SELECT 1 FROM agent WHERE naam=?", (aan,)).fetchone():
        aan = "regisseur"
    cur = conn.execute("INSERT INTO gesprek(aan, van, tekst, ts) VALUES(?,?,?,?)", (aan, (p.get("van") or "mehdi (telegram)")[:60], tekst[:8000], nu()))
    conn.commit()
    return jsonify(ok=True, id=cur.lastrowid, aan=aan)


@app.route("/api/gesprek/open")
def api_gesprek_open():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    rijen = db().execute("SELECT id, aan, van, tekst, ts FROM gesprek WHERE status='open' ORDER BY id").fetchall()
    return jsonify(open=[dict(r) for r in rijen])


@app.route("/api/gesprek/<int:gid>/status", methods=["POST"])
def api_gesprek_status(gid):
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    status = p.get("status")
    if status not in ("bezig", "beantwoord", "mislukt"):
        return jsonify(fout="status bezig|beantwoord|mislukt"), 400
    conn = db()
    conn.execute(
        "UPDATE gesprek SET status=?, antwoord=COALESCE(?, antwoord), detail=COALESCE(?, detail), "
        "beantwoord_ts=CASE WHEN ? IN ('beantwoord','mislukt') THEN ? ELSE beantwoord_ts END WHERE id=?",
        (status, p.get("antwoord"), p.get("detail"), status, nu(), gid),
    )
    conn.commit()
    return jsonify(ok=True)


@app.route("/api/gesprek/<int:gid>")
def api_gesprek(gid):
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    r = db().execute("SELECT * FROM gesprek WHERE id=?", (gid,)).fetchone()
    if not r:
        abort(404)
    # eerdere wisselingen in dezelfde draad (zelfde 'aan'), voor context
    eerder = db().execute(
        "SELECT van, tekst, antwoord, ts FROM gesprek WHERE aan=? AND id<? AND status='beantwoord' "
        "ORDER BY id DESC LIMIT 6", (r["aan"], gid)
    ).fetchall()
    return jsonify(gesprek=dict(r), eerder=[dict(x) for x in eerder][::-1])


# --- overzicht voor de hoofdagent: alle agents met werkwijze, status en recent verslag
@app.route("/api/overzicht")
def api_overzicht():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    conn = db()
    agents = [dict(r) for r in conn.execute("SELECT naam,label,type,rol,mandaat,mag,grenzen,cadans,tools,werkwijze,kennis_ts,kennis_bron FROM agent WHERE actief=1").fetchall()]
    status = {r["naam"]: dict(r) for r in conn.execute("SELECT * FROM status").fetchall()}
    for a in agents:
        a["status"] = status.get(a["naam"])
        a["open_voorstellen"] = conn.execute("SELECT COUNT(*) c FROM voorstel WHERE naam=? AND status='open'", (a["naam"],)).fetchone()["c"]
    return jsonify(agents=agents)


@app.route("/api/logboek/<naam>")
def api_logboek_lezen(naam):
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    n = min(int(request.args.get("n", 60)), 300)
    onderwerp = request.args.get("onderwerp")
    if onderwerp:
        rijen = db().execute("SELECT onderwerp, stap, tekst, detail, ts FROM logboek WHERE naam=? AND onderwerp LIKE ? ORDER BY id DESC LIMIT ?", (naam, f"%{onderwerp}%", n)).fetchall()
    else:
        rijen = db().execute("SELECT onderwerp, stap, tekst, detail, ts FROM logboek WHERE naam=? ORDER BY id DESC LIMIT ?", (naam, n)).fetchall()
    return jsonify(regels=[dict(r) for r in rijen][::-1])


@app.route("/gezondheid")
def gezondheid():
    n = db().execute("SELECT COUNT(*) c FROM agent WHERE actief=1").fetchone()["c"]
    return jsonify(ok=True, agents=n, app=APP_NAAM)


init_db()

# --- werfverslagen: de pagina's van Werfverslag voorbereider en Werfverslag schrijver, in de logica
#     van het contractsysteem: per dossier en per bezoek een rij met Openen · Keuzes · Bijlagen ·
#     Proef · Herkomst · Controle. Alleen beheer (dossiernummers en adressen zijn inhoud).
import werfopdrachten as werfwerk
from werf_migratie_001 import toepassen as werf_migreren

WERF_KOLOMMEN = ("gegevens", "verslag_md", "proef_pad", "proef_ts", "keuzes", "bijlagen", "proef_info", "registratie")
WERF_JSON = {"gegevens": {}, "keuzes": {}, "bijlagen": [], "proef_info": {}, "bronnen": {}, "controles": [], "taken": [], "registratie": {}}


def _werfbezoek_tabel(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS werfbezoek (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            dossier   TEXT NOT NULL,
            datum     TEXT NOT NULL,
            volgnr    INTEGER DEFAULT 0,
            adres     TEXT DEFAULT '',
            soort_project TEXT DEFAULT '',
            projectmap TEXT DEFAULT '',
            bezoekmap TEXT DEFAULT '',
            bronnen   TEXT DEFAULT '{}',   -- json: fotos, opnames, transcripten, verslagen, notities
            controles TEXT DEFAULT '[]',   -- json: [{code, naam, stand, toelichting}]
            taken     TEXT DEFAULT '[]',   -- json: [{voor, titel, uniek}]
            stand     TEXT DEFAULT '',
            open      INTEGER DEFAULT 1,
            ts        TEXT NOT NULL,
            UNIQUE(dossier, bezoekmap, datum)
        )""")
    bestaand = {r[1] for r in conn.execute("PRAGMA table_info(werfbezoek)").fetchall()}
    for k in WERF_KOLOMMEN:
        if k != "registratie" and k not in bestaand:
            conn.execute(f"ALTER TABLE werfbezoek ADD COLUMN {k} TEXT DEFAULT ''")
    werf_migreren(conn)


def _werf_huidige(conn, dossier, volgnr, rij_id=None):
    q, args = "SELECT * FROM werfbezoek WHERE dossier=? AND volgnr=? AND stand<>?", [dossier, volgnr, WERF_DUBBEL]
    if rij_id is not None:
        try:
            args.append(int(rij_id))
        except (TypeError, ValueError):
            raise werfwerk.Conflict("ongeldig bezoekrij-id", 400)
        q += " AND id=?"
    rows = conn.execute(q + " ORDER BY id DESC", args).fetchall()
    if not rows:
        raise werfwerk.Conflict("bezoek bestaat niet", 404)
    if len(rows) != 1:
        raise werfwerk.Conflict("meer dan één bezoekrij; kies de exacte rij via het overzicht")
    return rows[0]


def _werf_fout(exc):
    return jsonify(ok=False, geclaimd=False, reden=exc.reden), exc.code


def _werf_verwerkingen(rij):
    result = []
    for fase, veld in (("voorbereid", "gegevens"), ("proef", "proef_info")):
        meta = (rij.get(veld) or {}).get("_verwerking")
        if isinstance(meta, dict):
            items = meta.get("verwerkingen") or [meta]
            items = [v for v in items if isinstance(v, dict)]
            hergebruikt = bool(meta.get("hergebruikt", meta.get("cached", False)))
            nieuw_in = meta.get("nieuwe_tokens_in", meta.get("tokens_in"))
            nieuw_uit = meta.get("nieuwe_tokens_uit", meta.get("tokens_uit"))
            if nieuw_in is None:
                nieuw_in = sum(v.get("nieuwe_tokens_in", 0 if v.get("hergebruikt") else v.get("input_tokens", (v.get("usage") or {}).get("input_tokens", 0))) for v in items)
            if nieuw_uit is None:
                nieuw_uit = sum(v.get("nieuwe_tokens_uit", 0 if v.get("hergebruikt") else v.get("output_tokens", (v.get("usage") or {}).get("output_tokens", 0))) for v in items)
            kosten = [v.get("nieuwe_kosten_usd", 0 if v.get("hergebruikt", v.get("cached", False)) else v.get("cost_usd", v.get("kosten_usd"))) for v in items]
            kosten = sum(kosten) if kosten and all(isinstance(k, (int, float)) for k in kosten) else None
            cache = sum((v.get("usage") or {}).get("cache_read_input_tokens", v.get("cache_read_input_tokens", 0)) or 0 for v in items if not v.get("hergebruikt"))
            result.append({**meta, "fase": fase, "tokens_nieuw_in": 0 if hergebruikt else nieuw_in,
                           "tokens_nieuw_uit": 0 if hergebruikt else nieuw_uit,
                           "kosten_nieuw_usd": 0 if hergebruikt else kosten,
                           "cache_gelezen": cache, "analyse_hergebruikt": hergebruikt})
    return result


@app.route("/api/werfopdrachten")
def api_werfopdrachten():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    return jsonify(ok=True, opdrachten=werfwerk.lijst(db(), status=request.args.get("status")))


@app.route("/api/werfopdrachten/<int:kid>/claim", methods=["POST"])
def api_werfopdracht_claim(kid):
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    try:
        lease = int(p.get("lease_seconden", 1800))
    except (TypeError, ValueError):
        abort(400)
    try:
        return jsonify(werfwerk.claim(db(), kid, str(p.get("door") or "werfverslag-schrijver")[:100], lease))
    except werfwerk.Conflict as exc:
        return _werf_fout(exc)


@app.route("/api/werfopdrachten/aanvragen", methods=["POST"])
def api_werfopdracht_aanvragen():
    """Expliciete commandline-opdracht, dezelfde taakgrendel als de menselijke knop."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    dossier = str(p.get("dossier", ""))
    try:
        volgnr = int(p.get("volgnr", 0))
    except (TypeError, ValueError):
        abort(400)
    reden = str(p.get("reden") or "").strip()
    if not re.fullmatch(r"\d{4}", dossier) or volgnr < 1 or p.get("bron") != "commandline" or not reden:
        abort(400)
    try:
        r = _werf_huidige(db(), dossier, volgnr, p.get("werfbezoek_id"))
        opdracht, nieuw = werfwerk.maak(db(), r["id"], p.get("soort"), "werfverslag-schrijver",
                                      verwacht=p.get("revisie"), bron="commandline", reden=reden)
        return jsonify(ok=True, opdracht=opdracht, nieuw=nieuw)
    except werfwerk.Conflict as exc:
        return _werf_fout(exc)


@app.route("/api/werfopdrachten/<int:kid>/resultaat", methods=["POST"])
def api_werfopdracht_resultaat(kid):
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    try:
        uit = werfwerk.resultaat(db(), kid, p.get("lease_token"), p.get("status"), p.get("bewijs", ""),
                                 p.get("veilig_opnieuw") is True, p.get("verwerking"), p.get("hervat_utc"))
        return jsonify(ok=True, opdracht=uit)
    except werfwerk.Conflict as exc:
        return _werf_fout(exc)


@app.route("/api/werf-context")
def api_werf_context():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    dossier = request.args.get("dossier", "")
    try:
        volgnr = int(request.args.get("volgnr", ""))
    except ValueError:
        abort(400)
    if not re.fullmatch(r"\d{4}", dossier) or volgnr < 1:
        abort(400)
    try:
        rij = _werf_dict(_werf_huidige(db(), dossier, volgnr, request.args.get("rij_id")))
    except werfwerk.Conflict as exc:
        return _werf_fout(exc)
    registratie = rij.get("registratie") or {}
    return jsonify(ok=True, dossier=dossier, volgnr=volgnr, project_ref=f"h-architects:{dossier}",
                   bezoek_id=registratie.get("bezoek_id"), rij=rij,
                   opdrachten=werfwerk.lijst(db(), bezoek_id=rij["id"], verlopen=False), verwerkingen=_werf_verwerkingen(rij))


def _json(v, leeg):
    try:
        return json.loads(v) if v else leeg
    except ValueError:
        return leeg


# Een rij die na de verhuis van haar projectmap vervangen is door de rij op het nieuwe pad. Ze blijft staan
# (niets wissen zonder Mehdi's ja) tot hij het opruimvoorstel van Werfverslag voorbereider goedkeurt.
WERF_DUBBEL = "dubbel na verhuis; opruiming wacht op Mehdi"
WERF_GEWIST = os.path.join(os.path.dirname(DB_PAD), "werfbezoek_gewist.jsonl")


def _werf_leeg(v):
    return (v or "").strip() in ("", "{}", "[]", "null")


def _pad_vervang(v, oud, nieuw):
    # hoofdletterongevoelig, zoals Dropbox zelf: bij 2145 stond de fasemap als 'waiting to start' op de rij en
    # als 'Waiting to start' in de bijlagen, en een gewone replace liet de bijlagen op het oude pad staan
    if isinstance(v, str):
        return re.sub(re.escape(oud), lambda _: nieuw, v, flags=re.IGNORECASE)
    if isinstance(v, list):
        return [_pad_vervang(x, oud, nieuw) for x in v]
    if isinstance(v, dict):
        return {k: _pad_vervang(x, oud, nieuw) for k, x in v.items()}
    return v


def _werf_verhuisd(kolom, tekst, oud, nieuw):
    """Een kolom met het oude pad erin (bijlagen, proef_pad, gegevens) naar het nieuwe pad."""
    if kolom in WERF_JSON:
        try:
            return json.dumps(_pad_vervang(json.loads(tekst), oud, nieuw), ensure_ascii=False)
        except ValueError:
            pass
    return _pad_vervang(tekst or "", oud, nieuw)


def _werf_rel(r):
    """Het pad van de bezoekmap binnen de projectmap, in kleine letters: gelijk voor en na een verhuis van fasemap."""
    pm, bm = r["projectmap"] or "", r["bezoekmap"] or ""
    return bm[len(pm):].lower() if pm and bm.lower().startswith(pm.lower() + "/") else None


def _werf_herkoppel(conn, dossier, datum, bezoekmap, projectmap, vorige):
    """De projectmap verhuisde van fasemap (zelfde dossier, zelfde bezoekmapnaam, ander fasepad). De rij van het
    oude pad gaat mee naar het nieuwe, met gegevens, keuzes, bijlagen en proef, in plaats van een nieuwe rij.
    Bestaat er op het nieuwe pad al een rij (2145 op 24-09-2026: 19-23 en 145-149), dan vult de oude rij alleen de
    lege kolommen van die rij aan en krijgt ze de stand WERF_DUBBEL; wissen doet pas het runbook na Mehdi's ja."""
    oud = conn.execute("SELECT * FROM werfbezoek WHERE dossier=? AND bezoekmap=? AND datum=?", (dossier, vorige, datum)).fetchone()
    if not oud:
        return None
    oud_pm = oud["projectmap"] or ""
    if oud_pm and projectmap and vorige.lower().startswith(oud_pm.lower() + "/") and bezoekmap.startswith(projectmap + "/"):
        van, naar = oud_pm, projectmap
    else:
        van, naar = vorige, bezoekmap
    data = {k: _werf_verhuisd(k, oud[k], van, naar) for k in WERF_KOLOMMEN if not _werf_leeg(oud[k])}
    nieuw = conn.execute("SELECT * FROM werfbezoek WHERE dossier=? AND bezoekmap=? AND datum=?", (dossier, bezoekmap, datum)).fetchone()
    if not nieuw:
        velden = {"bezoekmap": bezoekmap, "projectmap": projectmap or oud_pm, **data}
        conn.execute(f"UPDATE werfbezoek SET {', '.join(f'{k}=?' for k in velden)} WHERE id=?", (*velden.values(), oud["id"]))
        return {"wat": "herkoppeld", "id": oud["id"], "van": vorige}
    # ook wat al op de blijvende rij stond, wijst voortaan naar het nieuwe pad (het oude bestaat niet meer)
    huidig = {k: _werf_verhuisd(k, nieuw[k], van, naar) for k in WERF_KOLOMMEN if not _werf_leeg(nieuw[k])}
    aangevuld = [k for k in data if k not in huidig]
    zet = {**{k: v for k, v in huidig.items() if v != nieuw[k]}, **{k: data[k] for k in aangevuld}}
    if zet:
        conn.execute(f"UPDATE werfbezoek SET {', '.join(f'{k}=?' for k in zet)} WHERE id=?", (*zet.values(), nieuw["id"]))
    conn.execute("UPDATE werfbezoek SET stand=? WHERE id=?", (WERF_DUBBEL, oud["id"]))
    return {"wat": "aangevuld", "id": nieuw["id"], "dubbel": oud["id"], "kolommen": aangevuld,
            "omgezet": [k for k in zet if k not in aangevuld],
            "botsing": [k for k in data if k in huidig and huidig[k] != data[k]]}


@app.route("/api/werfbezoek", methods=["POST"])
def api_werfbezoek():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    conn = db()
    _werfbezoek_tabel(conn)
    n, herkoppeld = 0, []
    for r in p.get("rijen") or []:
        if not (r.get("dossier") and r.get("datum")):
            continue
        sleutel = (str(r["dossier"])[:10], (r.get("bezoekmap") or "")[:500], r["datum"][:10])
        alleen = r.get("_alleen")
        if not alleen:
            for vorige in r.get("vorige_bezoekmappen") or []:
                vorige = str(vorige)[:500]
                if vorige and vorige != sleutel[1]:
                    uit = _werf_herkoppel(conn, sleutel[0], sleutel[2], sleutel[1], (r.get("projectmap") or "")[:500], vorige)
                    if uit:
                        herkoppeld.append(uit)
        if alleen:
            # gerichte bijwerking (voorbereiding, proef, keuzes): alleen die kolommen, de verificatie blijft staan
            velden = {k: r.get(k) for k in alleen if k in WERF_KOLOMMEN or k in {"taken", "controles", "stand"}}
            if any(k in velden and not isinstance(velden[k], list) for k in ("taken", "controles")):
                abort(400)
            if "stand" in velden and not isinstance(velden["stand"], str):
                abort(400)
            for k, v in velden.items():
                velden[k] = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
            velden["ts"] = nu()
            zet = ", ".join(f"{k}=?" for k in velden)
            rij_id = r.get("werfbezoek_id") or r.get("id")
            if r.get("_opdracht_id") or r.get("_lease_token"):
                if not conn.in_transaction:
                    conn.execute("BEGIN IMMEDIATE")
                try:
                    op = werfwerk.controleer(conn, int(r.get("_opdracht_id") or 0), r.get("_lease_token"), r.get("_invoer_hash"))
                    if not rij_id or int(rij_id) != op["werfbezoek_id"]:
                        raise werfwerk.Conflict("resultaat hoort bij een andere bezoekrij")
                except (ValueError, TypeError):
                    conn.rollback()
                    abort(400)
                except werfwerk.Conflict as exc:
                    conn.rollback()
                    return _werf_fout(exc)
            if rij_id:
                cur = conn.execute(f"UPDATE werfbezoek SET {zet} WHERE id=? AND dossier=? AND bezoekmap=? AND datum=?",
                                   (*velden.values(), int(rij_id), *sleutel))
            else:
                cur = conn.execute(f"UPDATE werfbezoek SET {zet} WHERE dossier=? AND bezoekmap=? AND datum=?",
                                   (*velden.values(), *sleutel))
            if r.get("_opdracht_id") and cur.rowcount != 1:
                conn.rollback()
                return _werf_fout(werfwerk.Conflict("bezoekrij of bronpad gewijzigd tijdens uitvoering"))
            if r.get("_opdracht_id"):
                bewijs = (op["soort"] == "voorbereid" and "gegevens" in velden and isinstance(r.get("gegevens"), dict)
                          and "gegevens" in r["gegevens"] and not r["gegevens"].get("_afgekapt"))
                bewijs = bewijs or (op["soort"] == "proef" and {"verslag_md", "proef_pad"} <= set(velden)
                                    and bool(r.get("verslag_md")) and bool(r.get("proef_pad")))
                if bewijs:
                    conn.execute("UPDATE werfopdracht SET resultaat_bewaard=? WHERE klaarzet_id=?", (nu(), op["klaarzet_id"]))
            n += cur.rowcount
            continue
        conn.execute(
            "INSERT INTO werfbezoek(dossier,datum,volgnr,adres,soort_project,projectmap,bezoekmap,bronnen,controles,taken,stand,ts) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(dossier,bezoekmap,datum) DO UPDATE SET volgnr=excluded.volgnr, "
            "adres=excluded.adres, soort_project=excluded.soort_project, projectmap=excluded.projectmap, bronnen=excluded.bronnen, "
            "controles=excluded.controles, taken=excluded.taken, stand=excluded.stand, ts=excluded.ts",
            (sleutel[0], sleutel[2], int(r.get("volgnr") or 0), (r.get("adres") or "")[:200],
             (r.get("soort_project") or "")[:20], (r.get("projectmap") or "")[:500], sleutel[1],
             json.dumps(r.get("bronnen") or {}, ensure_ascii=False), json.dumps(r.get("controles") or [], ensure_ascii=False),
             json.dumps(r.get("taken") or [], ensure_ascii=False), (r.get("stand") or "")[:80], nu()))
        n += 1
    conn.commit()
    return jsonify(ok=True, rijen=n, herkoppeld=herkoppeld)


@app.route("/api/werfbezoek/opruimen", methods=["POST"])
def api_werfbezoek_opruimen():
    """Alleen via het runbook werfbezoek-dubbels, na Mehdi's ja op het bord. Wist een oude rij pas als ze echt een
    dubbel is van de rij die blijft (zelfde dossier, datum en bezoekmap binnen de projectmap, andere fasemap) en als
    alles wat ze droeg ook op die rij staat. Elke gewiste rij komt eerst volledig in werfbezoek_gewist.jsonl."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    conn = db()
    _werfbezoek_tabel(conn)
    gewist, overgeslagen = [], []
    for paar in p.get("paren") or []:
        try:
            oud_id, blijft_id = int(paar[0]), int(paar[1])
        except (TypeError, ValueError, IndexError):
            overgeslagen.append({"paar": paar, "reden": "geen paar van twee rij-id's"})
            continue
        oud = conn.execute("SELECT * FROM werfbezoek WHERE id=?", (oud_id,)).fetchone()
        blijft = conn.execute("SELECT * FROM werfbezoek WHERE id=?", (blijft_id,)).fetchone()
        reden = ""
        if not oud or not blijft:
            reden = "rij bestaat niet (meer)"
        elif oud_id == blijft_id:
            reden = "dezelfde rij"
        elif (oud["dossier"], oud["datum"]) != (blijft["dossier"], blijft["datum"]):
            reden = "ander dossier of andere datum"
        elif _werf_rel(oud) is None or _werf_rel(oud) != _werf_rel(blijft):
            # Een hernoemde bezoekmap (de communicatiemap kreeg in oktober 2026 een nieuwe naamregel) heeft een ander
            # pad binnen de projectmap. Die mag alleen weg als het bord de oude rij zelf als dubbel markeerde en de rij
            # die blijft de enige levende rij van dat dossier op die dag is.
            levend = [x["id"] for x in conn.execute(
                "SELECT id FROM werfbezoek WHERE dossier=? AND datum=? AND stand<>?",
                (oud["dossier"], oud["datum"], WERF_DUBBEL)).fetchall()]
            if not (oud["stand"] == WERF_DUBBEL and levend == [blijft_id]):
                reden = "geen verhuisde of hernoemde bezoekmap (ander pad, en niet de enige levende rij van die dag)"
        else:
            kwijt = [k for k in WERF_KOLOMMEN if not _werf_leeg(oud[k]) and _werf_leeg(blijft[k])]
            if kwijt:
                reden = f"de rij die blijft mist nog {', '.join(kwijt)}"
        if reden:
            overgeslagen.append({"id": oud_id, "blijft": blijft_id, "reden": reden})
            continue
        with open(WERF_GEWIST, "a") as f:
            f.write(json.dumps({"gewist_ts": nu(), "blijft": blijft_id, "rij": dict(oud)}, ensure_ascii=False) + "\n")
        conn.execute("DELETE FROM werfbezoek WHERE id=?", (oud_id,))
        gewist.append(oud_id)
    conn.commit()
    return jsonify(ok=True, gewist=gewist, overgeslagen=overgeslagen)


def _werf_dict(r):
    d = dict(r)
    for k, leeg in WERF_JSON.items():
        d[k] = _json(d.get(k), leeg)
    return d


@app.route("/api/werfbezoek")
def api_werfbezoek_lezen():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    conn = db()
    _werfbezoek_tabel(conn)
    if request.args.get("dossier"):
        q, a = "SELECT * FROM werfbezoek WHERE dossier=?", [request.args["dossier"]]
        if request.args.get("volgnr"):
            q += " AND volgnr=?"; a.append(int(request.args["volgnr"]))
        if request.args.get("rij_id"):
            q += " AND id=?"; a.append(int(request.args["rij_id"]))
        # bij hetzelfde volgnummer eerst de levende rij, nooit de dubbel van een verhuisde projectmap:
        # de schrijver neemt rijen[0] en las anders een bezoekmap die niet meer bestaat
        q += " ORDER BY volgnr, (stand=?), id DESC"; a.append(WERF_DUBBEL)
        return jsonify(rijen=[_werf_dict(r) for r in conn.execute(q, a).fetchall()])
    q = "SELECT dossier, MAX(ts) AS ts, COUNT(*) AS bezoeken FROM werfbezoek"
    if request.args.get("open"):
        q += " WHERE open=1"
    q += " GROUP BY dossier ORDER BY dossier"
    return jsonify(dossiers=[dict(r) for r in conn.execute(q).fetchall()])


def _taak_status(conn):
    return {r["uniek"]: dict(r) for r in conn.execute(
        "SELECT uniek, status, opgepakt_door, opgepakt_ts, voor FROM klaarzet WHERE soort IN ('taak','opdracht') AND van='werfverslag-voorbereider'").fetchall()}


# Vertaling van de standen van de agent naar de tekens van de dossiercontrole (contractsysteem).
WERF_STAND = {"ok": "ok", "let_op": "let_op", "ontbreekt": "fout", "onbekend": "onbekend", "nvt": "onbekend"}
WERF_ACTIE = {
    "W1": "Agendawacht: afspraak van die dag zoeken en klaarzetten",
    "W2": "Locatiewacht: GPS-dagboek met bezoekvenster; anders foto met GPS of opname-start",
    "W3": "Projectmap en bezoekmap controleren",
    "W4": "iCloud-wacht: foto's van die dag binnen 300 m klaarzetten; of foto's van de klant in de bezoekmap zetten",
    "W5": "Plaudwacht: opname van die dag koppelen; geen opname = verslag uit geheugen (E8)",
    "W6": "Plaudwacht: transcript maken of ophalen",
    "W7": "jouw klik: Maak concept; Werfverslag schrijver zet het concept in de werfapp",
    "W9": "Verzendbewijs in de werfapp nakijken",
    "W12": "Getekend contract en werfopvolging in het contract-dashboard nakijken",
    "W11": "Werfverslag schrijver bereidt voor (opdracht staat klaar), daarna Keuzes en Proef",
}


def _werf_rij(d, taak_status):
    d["formulier_revisie"] = werfwerk.revisie(d)
    d["verwerkingen"] = _werf_verwerkingen(d)
    for t in d["taken"]:
        s = taak_status.get(t.get("uniek"))
        t["status"] = (s["status"] if s else "niet klaargezet")
        t["door"] = (s["opgepakt_door"] if s else "")
    d["controle_rijen"] = []
    for c in d["controles"]:
        st = WERF_STAND.get(c["stand"], "onbekend")
        d["controle_rijen"].append({"nummer": c["code"], "titel": c["naam"], "status": st, "bevinding": c["toelichting"],
                                    "actie": WERF_ACTIE.get(c["code"], "") if st != "ok" else ""})
    d["telling"] = {k: sum(1 for c in d["controle_rijen"] if c["nummer"] != "NODIG" and c["status"] == k)
                     for k in ("ok", "let_op", "fout", "onbekend")}
    g = d["gegevens"] or {}
    for x in g.get("gegevens", []):
        x["status"] = {"zeker": "ok", "na te kijken": "let_op", "ontbreekt": "fout"}.get(x.get("zekerheid"), "onbekend")
    d["voorbereid"] = bool(g.get("gegevens"))
    d["heeft_proef"] = bool(d.get("proef_pad"))
    d["heeft_keuzes"] = bool(d["keuzes"])
    # wat nog nodig is, in de woorden van het contractdashboard
    nodig = []
    werf = (d["proef_info"] or {}).get("werfapp") or {}
    d["werfapp"] = dict(werf) if isinstance(werf, dict) else {}
    vid = d["werfapp"].get("id")
    if not (isinstance(vid, int) and not isinstance(vid, bool) and vid > 0):
        d["werfapp"].pop("id", None)   # alleen een echt verslag-ID telt als concept (de link wordt eruit opgebouwd)
    if not d["heeft_proef"]:
        nodig.append("jouw klik: Maak concept")   # één klik; Voorbereiden en Keuzes zijn niet verplicht (eigen bronnen standaard)
    else:
        pv = (d["proef_info"] or {}).get("verslagtype") in ("voorlopige_oplevering", "definitieve_oplevering")
        if d["werfapp"].get("id") and d["werfapp"].get("verstuurd"):
            nodig.append("niets meer, verstuurd")   # CX5-9
        elif d["werfapp"].get("id"):
            nodig.append("nalezen en versturen in de werfapp")
        elif d["werfapp"].get("fout"):
            nodig.append(f"geen concept in de werfapp: {d['werfapp']['fout']}")
        elif pv:
            nodig.append("Word-sjabloon van de oplevering invullen")
        else:
            nodig.append("oudere proef, nog niet in de werfapp (doorzetten zonder tokens)")  # CX4-12: nooit 'niets'
        op = (d["proef_info"] or {}).get("open") or {}
        if isinstance(op, dict) and any(op.values()):
            nodig.append(f"nakijken: {op.get('in_te_vullen', 0)} in te vullen, {op.get('na_te_kijken', 0)} na te kijken")
    for c in d["controle_rijen"]:
        if c["nummer"] == "NODIG":
            nodig.append(c["bevinding"])
    d["nodig"] = nodig
    if d["heeft_proef"] and d["werfapp"].get("id") and d["werfapp"].get("verstuurd"):
        d["fase"] = "verstuurd vanuit de werfapp"
    elif d["heeft_proef"] and d["werfapp"].get("id"):
        d["fase"] = "concept in de werfapp"
    elif d["heeft_proef"]:
        d["fase"] = "proef klaar, nakijken"
    elif d["voorbereid"]:
        d["fase"] = "te controleren"
    else:
        d["fase"] = "te vervolledigen"
    return d


def _werf_opdrachtstand(conn, b):
    opdrachten = werfwerk.lijst(conn, bezoek_id=b["id"], verlopen=False)
    for op in opdrachten:
        if op.get("hervat_utc"):
            op["hervat_belgie"] = datetime.fromisoformat(op["hervat_utc"]).astimezone(ZoneInfo("Europe/Brussels")).strftime("%d-%m-%Y %H:%M")
    b["opdrachten"] = opdrachten
    blokkades = [op for op in opdrachten if op["status"] in ("onbekend", "actief")]
    laatste = blokkades[0] if blokkades else (opdrachten[0] if opdrachten else None)
    b["opdracht_status"] = laatste["status"] if laatste else ""
    b["huidige_opdracht"] = laatste
    if laatste and laatste["status"] in ("onbekend", "fout", "actief", "klaar", "verouderd", "uitgesteld"):
        b["fase"] = {"onbekend": "uitvoering controleren", "fout": "verwerking mislukt", "actief": "schrijver bezig",
                     "klaar": "opdracht wacht", "verouderd": "invoer gewijzigd", "uitgesteld": "tijdelijk uitgesteld"}[laatste["status"]]
    return b


@app.route("/werfverslagen")
def werfverslagen_pagina():
    if not mag_beslissen():
        abort(403)
    conn = db()
    _werfbezoek_tabel(conn)
    taak_status = _taak_status(conn)
    rijen = [_werf_opdrachtstand(conn, _werf_rij(_werf_dict(r), taak_status)) for r in conn.execute("SELECT * FROM werfbezoek WHERE open=1 ORDER BY dossier, datum, volgnr").fetchall()]
    dossiers = {}
    for d in rijen:
        ds = dossiers.setdefault(d["dossier"], {"dossier": d["dossier"], "adres": d["adres"], "soort": d["soort_project"],
                                                "projectmap": d["projectmap"], "bezoeken": [], "dubbels": []})
        # een dubbel na verhuis telt niet als bezoek; hij staat apart tot Mehdi de opruiming goedkeurt
        ds["dubbels" if d["stand"] == WERF_DUBBEL else "bezoeken"].append(d)
    for ds in dossiers.values():
        if ds["bezoeken"]:
            ds["projectmap"] = ds["bezoeken"][-1]["projectmap"]
    noden = [dict(r) for r in conn.execute("SELECT naam, tekst, wie, ts FROM nood WHERE naam IN ('werfverslag-voorbereider','werfverslag-schrijver') AND open=1 ORDER BY id").fetchall()]
    st = {r["naam"]: dict(r) for r in conn.execute("SELECT * FROM status WHERE naam IN ('werfverslag-voorbereider','werfverslag-schrijver')").fetchall()}
    return render_template("werfverslagen.html", app_naam=APP_NAAM, dossiers=list(dossiers.values()), noden=noden, status=st,
                           gebruiker=gebruiker())


@app.route("/werfverslag/<dossier>/<int:volgnr>")
def werfbezoek_pagina(dossier, volgnr):
    if not mag_beslissen():
        abort(403)
    conn = db()
    _werfbezoek_tabel(conn)
    try:
        r = _werf_huidige(conn, dossier, volgnr, request.args.get("rij_id"))
    except werfwerk.Conflict as exc:
        return _werf_fout(exc)
    b = _werf_opdrachtstand(conn, _werf_rij(_werf_dict(r), _taak_status(conn)))
    open_opdr = b["opdrachten"]
    logboek = [dict(x) for x in conn.execute(
        "SELECT naam, stap, tekst, ts FROM logboek WHERE naam IN ('werfverslag-voorbereider','werfverslag-schrijver') AND onderwerp IN (?, ?) ORDER BY id DESC LIMIT 30",
        (f"{dossier}-{volgnr}", dossier)).fetchall()]
    return render_template("werfbezoek.html", app_naam=APP_NAAM, b=b, g=b["gegevens"], opdrachten=open_opdr, logboek=logboek,
                           verslag_html=md(b.get("verslag_md") or "") if b.get("verslag_md") else "", tab=request.args.get("tab", ""))


@app.route("/werfverslag/<dossier>/<int:volgnr>/keuzes", methods=["POST"])
def werfbezoek_keuzes(dossier, volgnr):
    """Keuzes van Mehdi (zoals Keuzes in het contractsysteem): verslagtype, taal, doorlopende punten,
    aanwezigen, opmerking voor de schrijver. Bewaard op de rij; de schrijver leest ze bij de proef."""
    if not mag_beslissen():
        abort(403)
    conn = db()
    _werfbezoek_tabel(conn)
    f = request.form
    try:
        r = _werf_huidige(conn, dossier, volgnr, f.get("rij_id"))
        if not f.get("revisie") or werfwerk.revisie(r) != f["revisie"]:
            raise werfwerk.Conflict("bezoek of keuzes gewijzigd; herlaad de pagina")
    except werfwerk.Conflict as exc:
        return _werf_fout(exc)
    aanwezigen = []
    for regel in (f.get("aanwezigen") or "").splitlines():
        delen = [x.strip() for x in regel.split("|")]
        if len(delen) >= 3 and any(delen):
            while len(delen) < 5:
                delen.append("")
            aanwezigen.append({"rol": delen[0], "firma": delen[1], "naam": delen[2], "contact": delen[3], "aanwezig": delen[4] or "ja"})
    keuzes = {"verslagtype": f.get("verslagtype", ""), "taal": f.get("taal", "nl"), "doorlopend": f.get("doorlopend", "ja"),
              "bronnen": f.get("bronnen", "eigen"), "naslag": f.get("naslag", "ja"), "overgang": f.get("overgang", "tweede rondgang"), "waarborg": (f.get("waarborg") or "12")[:3],
              "aanwezigen": aanwezigen, "opmerking": (f.get("opmerking") or "")[:2000], "door": gebruiker(), "ts": nu()}
    # De revisiecheck en update gebeuren in dezelfde write-lock, ook met twee browsers.
    with werfwerk.atomic(conn):
        huidig = conn.execute("SELECT * FROM werfbezoek WHERE id=?", (r["id"],)).fetchone()
        if werfwerk.revisie(huidig) != f["revisie"]:
            return _werf_fout(werfwerk.Conflict("keuzes inmiddels gewijzigd; herlaad de pagina"))
        oud = {k: v for k, v in _json(huidig["keuzes"], {}).items() if k not in ("ts", "door")}
        nieuw = {k: v for k, v in keuzes.items() if k not in ("ts", "door")}
        if oud != nieuw:
            conn.execute("UPDATE werfbezoek SET keuzes=?,ts=?,keuzes_revisie=keuzes_revisie+1 WHERE id=?",
                         (json.dumps(keuzes, ensure_ascii=False), nu(), r["id"]))
    return redirect(url_for("werfbezoek_pagina", dossier=dossier, volgnr=volgnr, rij_id=r["id"], tab="keuzes"))


@app.route("/werfverslag/<dossier>/<int:volgnr>/opdracht", methods=["POST"])
def werfbezoek_opdracht(dossier, volgnr):
    """Knop op de bezoekpagina: zet een opdracht klaar voor Werfverslag schrijver (voorbereid | proef).
    Hij voert ze uit in zijn opdrachtenronde (cron elke 5 min) en meldt bewijs in zijn werkverslag."""
    if not mag_beslissen():
        abort(403)
    soort = request.form.get("soort", "")
    if soort not in ("voorbereid", "proef"):
        abort(400)
    conn = db()
    try:
        r = _werf_huidige(conn, dossier, volgnr, request.form.get("rij_id"))
        if not request.form.get("revisie"):
            raise werfwerk.Conflict("herlaad de bezoekpagina vóór een opdracht")
        werfwerk.maak(conn, r["id"], soort, gebruiker(), request.form["revisie"])
    except werfwerk.Conflict as exc:
        return _werf_fout(exc)
    return redirect(url_for("werfbezoek_pagina", dossier=dossier, volgnr=volgnr, rij_id=r["id"], tab="proef"))


@app.route("/werfverslag/<dossier>/<int:volgnr>/opdracht/<int:kid>/opnieuw", methods=["POST"])
def werfbezoek_opnieuw(dossier, volgnr, kid):
    if not mag_beslissen():
        abort(403)
    try:
        r = _werf_huidige(db(), dossier, volgnr, request.form.get("rij_id"))
        werfwerk.opnieuw(db(), kid, r["id"])
    except werfwerk.Conflict as exc:
        return _werf_fout(exc)
    return redirect(url_for("werfbezoek_pagina", dossier=dossier, volgnr=volgnr, rij_id=r["id"], tab="proef"))


# --- commandocentrum: één rij per bezoek ter plaatse dat een verslag vraagt (werfverslag, veiligheidscoördinatie,
#     plaatsbeschrijving, barsten en scheuren). Het Commandocentrum (agent) leest de agenda-bak, herkent de
#     verslagsoort, stuurt de impuls naar de verslagagent en laat de wachten het pakket vullen (foto's, opname,
#     transcript). De verslagagent meet het pakket en schrijft de proef na Mehdi's knop. Alleen beheer ziet de
#     pagina (klant- en dossiernamen zijn inhoud).
VERSLAG_KOLOMMEN = ("dossiermap", "bezoekmap", "pakket", "taken", "stand", "impuls_voorbereiding_ts", "impuls_verslag_ts",
                    "proef_pad", "proef_ts", "verslag_md", "proef_info", "opmerking", "open")
VERSLAG_JSON = {"pakket": {}, "taken": [], "proef_info": {}}
PAKKET_LABELS = (("agenda", "agenda"), ("dossiermap", "dossiermap"), ("bezoekmap", "bezoekmap"), ("fotos", "foto's"),
                 ("opnames", "opname"), ("transcripten", "transcript"), ("documenten", "documenten"))


def _verslagopdracht_tabel(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS verslagopdracht (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            uniek     TEXT NOT NULL UNIQUE,   -- agenda:<kalender>:<event-id>, uit de bak van de Agendawacht
            verslagsoort TEXT NOT NULL,       -- sleutel in verslagsoorten.SOORTEN
            agent     TEXT NOT NULL,          -- verslagagent die hem draagt
            afdeling  TEXT DEFAULT '',
            dossier   TEXT DEFAULT '',        -- projectnummer als de titel er een had
            klant     TEXT DEFAULT '',
            adres     TEXT DEFAULT '',
            datum     TEXT NOT NULL,
            start     TEXT DEFAULT '',
            einde     TEXT DEFAULT '',
            titel     TEXT DEFAULT '',
            agenda    TEXT DEFAULT '',
            deal_id   TEXT DEFAULT '',
            dossiermap TEXT DEFAULT '',
            bezoekmap TEXT DEFAULT '',
            pakket    TEXT DEFAULT '{}',      -- json: agenda, dossiermap, bezoekmap, fotos, opnames, transcripten, documenten, gemeten_ts
            taken     TEXT DEFAULT '[]',      -- json: [{voor, uniek, titel}]
            stand     TEXT DEFAULT 'gepland', -- gepland | voorbereid | verzamelen | pakket klaar | proef gevraagd | proef klaar | gesloten
            impuls_voorbereiding_ts TEXT DEFAULT '',
            impuls_verslag_ts TEXT DEFAULT '',
            proef_pad TEXT DEFAULT '',
            proef_ts  TEXT DEFAULT '',
            verslag_md TEXT DEFAULT '',
            proef_info TEXT DEFAULT '{}',
            opmerking TEXT DEFAULT '',        -- van Mehdi, voor de verslagagent
            open      INTEGER DEFAULT 1,
            ts        TEXT NOT NULL
        )""")


def _verslag_dict(r):
    d = dict(r)
    for k, leeg in VERSLAG_JSON.items():
        d[k] = _json(d.get(k), leeg)
    return d


@app.route("/api/verslagopdracht", methods=["POST"])
def api_verslagopdracht():
    """Upsert op uniek. Met `_alleen` worden alleen die kolommen bijgewerkt (de verslagagent meldt pakket,
    dossiermap, bezoekmap, proef; het Commandocentrum meldt impulsen en stand) zonder elkaars werk te overschrijven."""
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    p = request.get_json(silent=True) or {}
    conn = db()
    _verslagopdracht_tabel(conn)
    n = 0
    for r in p.get("rijen") or []:
        if not r.get("uniek"):
            continue
        alleen = r.get("_alleen")
        if alleen:
            velden = {}
            for k in alleen:
                if k in VERSLAG_KOLOMMEN:
                    v = r.get(k)
                    velden[k] = v if isinstance(v, (str, int)) or v is None else json.dumps(v, ensure_ascii=False)
            if not velden:
                continue
            velden["ts"] = nu()
            zet = ", ".join(f"{k}=?" for k in velden)
            n += conn.execute(f"UPDATE verslagopdracht SET {zet} WHERE uniek=?", (*velden.values(), r["uniek"][:200])).rowcount
            continue
        if not (r.get("verslagsoort") and r.get("agent") and r.get("datum")):
            continue
        conn.execute(
            "INSERT INTO verslagopdracht(uniek, verslagsoort, agent, afdeling, dossier, klant, adres, datum, start, einde, titel, agenda, deal_id, ts) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(uniek) DO UPDATE SET verslagsoort=excluded.verslagsoort, agent=excluded.agent, "
            "afdeling=excluded.afdeling, dossier=excluded.dossier, klant=excluded.klant, adres=excluded.adres, datum=excluded.datum, "
            "start=excluded.start, einde=excluded.einde, titel=excluded.titel, agenda=excluded.agenda, deal_id=excluded.deal_id, ts=excluded.ts",
            (r["uniek"][:200], r["verslagsoort"][:40], r["agent"][:60], (r.get("afdeling") or "")[:40], str(r.get("dossier") or "")[:20],
             (r.get("klant") or "")[:120], (r.get("adres") or "")[:200], r["datum"][:10], (r.get("start") or "")[:40],
             (r.get("einde") or "")[:40], (r.get("titel") or "")[:200], (r.get("agenda") or "")[:60], str(r.get("deal_id") or "")[:20], nu()))
        n += 1
    conn.commit()
    return jsonify(ok=True, rijen=n)


@app.route("/api/verslagopdracht")
def api_verslagopdracht_lezen():
    if not TOKEN or request.headers.get("X-Agents-Token") != TOKEN:
        abort(403)
    conn = db()
    _verslagopdracht_tabel(conn)
    q, a = "SELECT * FROM verslagopdracht WHERE 1=1", []
    if request.args.get("agent"):
        q += " AND agent=?"; a.append(request.args["agent"])
    if request.args.get("uniek"):
        q += " AND uniek=?"; a.append(request.args["uniek"])
    if request.args.get("id"):
        q += " AND id=?"; a.append(int(request.args["id"]))
    if request.args.get("open", "1") != "alle":
        q += " AND open=1"
    return jsonify(rijen=[_verslag_dict(r) for r in conn.execute(q + " ORDER BY datum, start", a).fetchall()])


def _verslag_rij(d, taak_status):
    """Wat de pagina toont: pakketlampjes (in de tekens van de dossiercontrole), taken met stand, wat nog nodig is."""
    pk = d["pakket"] or {}
    lampjes = []
    for sleutel, label in PAKKET_LABELS:
        v = pk.get(sleutel)
        if sleutel in ("agenda", "dossiermap", "bezoekmap"):
            st = "ok" if v else ("onbekend" if v is None else "fout")
            tekst = (d.get(sleutel) or "").rsplit("/", 1)[-1] if sleutel != "agenda" else ("gevonden" if v else "")
        else:
            st = "ok" if (v or 0) > 0 else ("onbekend" if v is None else "fout")
            tekst = str(v) if v is not None else "?"
        lampjes.append({"sleutel": sleutel, "label": label, "status": st, "tekst": tekst})
    d["lampjes"] = lampjes
    for t in d["taken"]:
        s = taak_status.get(t.get("uniek"))
        t["status"] = s["status"] if s else "niet klaargezet"
        t["door"] = s["opgepakt_door"] if s else ""
    nodig = []
    if not d.get("dossiermap"):
        nodig.append("dossiermap (agent zoekt; anders zet jij het pad)")
    elif not d.get("bezoekmap"):
        nodig.append("bezoekmap (agent maakt hem aan)")
    if d["stand"] not in ("gepland",) and d.get("bezoekmap"):
        if not pk.get("fotos"):
            nodig.append("foto's (iCloud-wacht)")
        if not pk.get("transcripten"):
            nodig.append("transcript (Plaudwacht)")
    if d["stand"] == "pakket klaar" and not d.get("proef_pad"):
        nodig.append("jouw knop: Proef maken")
    if d.get("proef_pad"):
        nodig = ["proef nakijken"] + ([] if not (d["proef_info"] or {}).get("open") else ["open punten in de proef"])
    d["nodig"] = nodig
    d["proef_naam"] = (d.get("proef_pad") or "").rsplit("/", 1)[-1]
    return d


@app.route("/commandocentrum")
def commandocentrum_pagina():
    if not mag_beslissen():
        abort(403)
    conn = db()
    _verslagopdracht_tabel(conn)
    taak_status = {r["uniek"]: dict(r) for r in conn.execute(
        "SELECT uniek, status, opgepakt_door FROM klaarzet WHERE van='commandocentrum' AND uniek<>''").fetchall()}
    rijen = [_verslag_rij(_verslag_dict(r), taak_status) for r in conn.execute(
        "SELECT * FROM verslagopdracht WHERE open=1 ORDER BY datum DESC, start DESC").fetchall()]
    vandaag = nu()[:10]
    werf = [r for r in rijen if r["verslagsoort"] == "werfverslag"]      # eigen keten: pagina Werfverslagen
    eigen = [r for r in rijen if r not in werf]
    komend = [r for r in eigen if r["datum"] >= vandaag and r["stand"] in ("gepland", "voorbereid")]
    lopend = [r for r in eigen if r not in komend and not r.get("proef_pad")]
    proef = [r for r in eigen if r.get("proef_pad")]
    agents_namen = ["commandocentrum", "werfverslag-voorbereider", "werfverslag-schrijver", "veiligheidscoordinatie-verslag",
                    "plaatsbeschrijving-verslag", "barsten-scheuren-verslag", "aankoopkeuring-verslag", "icloud-wacht", "plaud-wacht", "agenda-wacht"]
    st = {r["naam"]: dict(r) for r in conn.execute(
        f"SELECT * FROM status WHERE naam IN ({','.join('?' * len(agents_namen))})", agents_namen).fetchall()}
    labels = {r["naam"]: r["label"] for r in conn.execute("SELECT naam, label FROM agent").fetchall()}
    noden = [dict(r) for r in conn.execute(
        f"SELECT naam, tekst, wie, ts FROM nood WHERE open=1 AND naam IN ({','.join('?' * len(agents_namen))}) ORDER BY id", agents_namen).fetchall()]
    logboek = [dict(r) for r in conn.execute(
        "SELECT naam, onderwerp, stap, tekst, ts FROM logboek WHERE naam IN ('commandocentrum','veiligheidscoordinatie-verslag',"
        "'plaatsbeschrijving-verslag','barsten-scheuren-verslag','aankoopkeuring-verslag') ORDER BY id DESC LIMIT 25").fetchall()]
    gesloten = conn.execute("SELECT COUNT(*) FROM verslagopdracht WHERE open=0").fetchone()[0]
    return render_template("commandocentrum.html", app_naam=APP_NAAM, komend=komend, lopend=lopend, proef=proef, werf=werf, status=st,
                           labels=labels, agents_namen=agents_namen, noden=noden, logboek=logboek, gesloten=gesloten, gebruiker=gebruiker())


@app.route("/commandocentrum/<int:vid>/opdracht", methods=["POST"])
def commandocentrum_opdracht(vid):
    """Knoppen op de pagina. `proef`: opdracht voor de verslagagent (kost tokens, dus alleen op de knop).
    `dossiermap`: Mehdi zet het pad zelf als de agent de map niet vond. `sluiten`: van de pagina."""
    if not mag_beslissen():
        abort(403)
    conn = db()
    _verslagopdracht_tabel(conn)
    r = conn.execute("SELECT * FROM verslagopdracht WHERE id=?", (vid,)).fetchone()
    if not r:
        abort(404)
    soort = request.form.get("soort", "")
    if soort == "proef":
        conn.execute("INSERT INTO klaarzet(van, voor, soort, sleutel, titel, inhoud, verwijzing, uniek, ts) VALUES(?,?,?,?,?,?,?,?,?)",
                     (f"bord:{gebruiker()}", r["agent"], "opdracht", str(vid), f"proef {vid}",
                      json.dumps({"door": gebruiker(), "uniek": r["uniek"], "opmerking": (request.form.get("opmerking") or "")[:2000]}),
                      r["bezoekmap"] or "", "", nu()))
        conn.execute("UPDATE verslagopdracht SET stand='proef gevraagd', opmerking=?, ts=? WHERE id=?",
                     ((request.form.get("opmerking") or "")[:2000], nu(), vid))
    elif soort == "dossiermap":
        pad = (request.form.get("dossiermap") or "").strip()[:500]
        conn.execute("UPDATE verslagopdracht SET dossiermap=?, bezoekmap='', impuls_voorbereiding_ts='', ts=? WHERE id=?", (pad, nu(), vid))
        # de agent maakt de bezoekmap bij zijn volgende impuls; het Commandocentrum zet die opnieuw klaar
        conn.execute("DELETE FROM klaarzet WHERE uniek=?", (f"cc:{r['uniek']}:voorbereiding",))
    elif soort == "sluiten":
        conn.execute("UPDATE verslagopdracht SET open=0, stand='gesloten', ts=? WHERE id=?", (nu(), vid))
    elif soort == "heropen":
        conn.execute("UPDATE verslagopdracht SET open=1, ts=? WHERE id=?", (nu(), vid))
    else:
        abort(400)
    conn.commit()
    return redirect(url_for("commandocentrum_pagina") + f"#v{vid}")


TESTFORMULIER = """<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Testformulier De Bode</title>
<style>body{font-family:system-ui,sans-serif;max-width:520px;margin:40px auto;padding:0 16px;color:#1d1d1f}
label{display:block;margin:14px 0 4px;font-weight:600}input{width:100%;padding:9px;border:1px solid #bbb;border-radius:6px;font-size:15px}
button{margin-top:20px;padding:10px 18px;border:0;border-radius:6px;background:#0b5cad;color:#fff;font-size:15px}
.info{background:#f2f2f5;padding:10px 12px;border-radius:6px;font-size:14px}#uit{margin-top:16px;font-weight:600}</style></head>
<body><h1>Klantgegevens bevestigen</h1>
<p class="info">Testformulier voor de bel-tool van De Bode. Er wordt niets verstuurd en niets bewaard, ook niet als je op Versturen klikt.</p>
<form onsubmit="event.preventDefault();document.getElementById('uit').textContent='Test: niets verstuurd, niets bewaard.';this.reset();">
<label for="naam">Volledige naam</label><input id="naam" name="naam" autocomplete="off">
<label for="mail">E-mailadres</label><input id="mail" name="mail" type="email" autocomplete="off">
<label for="pas">Paspoortnummer</label><input id="pas" name="pas" autocomplete="off">
<label for="iban">IBAN</label><input id="iban" name="iban" autocomplete="off">
<button type="submit">Versturen</button></form><div id="uit"></div></body></html>"""


@app.get("/stemkosten")
def stemkosten():
    """Kosten van de gesprekken van De Bode met Mehdi (OpenAI Realtime + Twilio), per gesprek en per maand."""
    if not mag_beslissen():
        abort(403)
    try:
        rijen = db().execute("SELECT id, ts, zin, status, antwoord, duur_s, model, openai_usd, twilio_usd "
                             "FROM stemgesprek ORDER BY id DESC LIMIT 500").fetchall()
    except sqlite3.OperationalError:
        rijen = []
    from html import escape as e
    maanden = {}
    for r in rijen:
        m = maanden.setdefault((r["ts"] or "")[:7], [0, 0.0, 0.0])
        m[0] += 1
        m[1] += r["openai_usd"] or 0
        m[2] += r["twilio_usd"] or 0
    kop = "<tr><th>Maand</th><th>Gesprekken</th><th>OpenAI</th><th>Twilio</th><th>Totaal</th></tr>"
    mrij = "".join(f"<tr><td>{k}</td><td>{v[0]}</td><td>${v[1]:.3f}</td><td>${v[2]:.3f}</td><td>${v[1] + v[2]:.3f}</td></tr>"
                   for k, v in sorted(maanden.items(), reverse=True))
    def bedrag(v, leeg):
        return leeg if v is None else "$%.4f" % v

    grij = ""
    for r in rijen:
        wanneer = (r["ts"] or "")[:16].replace("T", " ")
        grij += (f"<tr><td>{e(wanneer)}</td><td>{e(r['zin'][:90])}</td><td>{e(r['status'])}</td>"
                 f"<td>{e((r['antwoord'] or '')[:90])}</td><td>{r['duur_s'] or ''}</td><td>{e(r['model'] or '')}</td>"
                 f"<td>{bedrag(r['openai_usd'], '')}</td><td>{bedrag(r['twilio_usd'], 'nog niet')}</td></tr>")
    return ("<!doctype html><meta charset='utf-8'><title>Kosten stem De Bode</title>"
            "<style>body{font-family:system-ui,sans-serif;margin:24px;color:#1d1d1f}table{border-collapse:collapse;margin:8px 0 24px}"
            "td,th{border-bottom:1px solid #ddd;padding:6px 10px;text-align:left;font-size:14px}th{background:#f2f2f5}</style>"
            "<h1>Kosten van de gesprekken van De Bode</h1><p>OpenAI uit de tokens per gesprek, Twilio zoals Twilio het "
            "aanrekent (komt een paar minuten na het gesprek binnen). Bedragen in dollar.</p>"
            f"<h2>Per maand</h2><table>{kop}{mrij or '<tr><td colspan=5>Nog geen gesprekken</td></tr>'}</table>"
            "<h2>Per gesprek</h2><table><tr><th>Wanneer</th><th>Zin</th><th>Status</th><th>Antwoord</th><th>Duur (s)</th>"
            f"<th>Model</th><th>OpenAI</th><th>Twilio</th></tr>{grij}</table>")


@app.get("/test/formulier")
def testformulier():
    """Nepformulier om de bel-tool te testen (25-09-2026): vraagt om een paspoortnummer en een IBAN, waar
    Claude niet zelf mag invullen. Alles blijft in de browser: geen POST, geen opslag."""
    return TESTFORMULIER


# MCP voor Mehdi's Claude: "roep Mehdi" als een agent vastzit (mcp_bode.py, 25-09-2026).
import mcp_bode  # noqa: E402
mcp_bode.registreer(app, gebruiker, groepen, db, nu)

# FelixArchief als eigen pagina voor Shelton (felix_pagina.py, 13-10-2026): felix.<domein> toont alleen /felix.
import felix_pagina  # noqa: E402
felix_pagina.registreer(app, gebruiker, groepen, md, nu)

# Genummerde werfmigraties bij startup; /api/werf-context zelf voert uitsluitend SELECT uit.
with sqlite3.connect(DB_PAD) as _werf_start:
    _werfbezoek_tabel(_werf_start)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 3022)), debug=True)

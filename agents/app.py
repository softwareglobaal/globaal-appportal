"""Agents: het besturingscentrum van het Globaal-agentplatform.

Toont het agent-team in een oogopslag: elk lid als kaart met een status. Een
gewired-en-levende agent staat op "waakt" (op wacht) of "actief" (bezig); valt
hij stil dan wordt dat "stil" (geen recente hartslag). Een nog niet gekoppelde
rol staat op "niet gekoppeld". Bewust zelfstandig gehouden: een eigen kleine
SQLite in het datavolume, geen database-credential nodig. Agents melden hun
status via de token-route /agent-status (nginx laat die ene route langs de
SSO); de rest van de app zit achter Authentik forward-auth.

Voorstellen (mens-in-de-lus): een agent kan bij een probleem een benoemde
runbook VOORSTELLEN. De gebruiker keurt goed of weigert op de tegel. Een
goedgekeurd voorstel wordt NIET hier uitgevoerd: een aparte host-uitvoerder
(runner/uitvoerder.py) pikt goedgekeurde voorstellen op, valideert ze tegen een
korte allowlist en voert alleen dan de veilige actie uit, met verificatie
achteraf. Deze app legt alleen de beslissing en de uitkomst vast.
"""
import os
import json
import sqlite3
from datetime import datetime, timezone, timedelta

import markdown

from flask import (Flask, render_template, request, jsonify, abort,
                   redirect, send_file)

app = Flask(__name__)

DB = os.environ.get("AGENTS_DB", "/data/agents.db")
TOKEN = os.environ.get("AGENTS_TOKEN", "").strip()
BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "localhost")
# De zoekdienst draait op de host, op het adres van het docker-netwerk.
# De kennis-database blijft op loopback en is hier niet bereikbaar.
ZOEKDIENST = os.environ.get("ZOEKDIENST", "http://172.20.0.1:3021")

STATUSSEN = ("rust", "waakt", "actief", "klaar", "fout")

TEAM = [
    {"naam": "onderhoud", "label": "Onderhoudsagent", "type": "onderhoud",
     "rol": "waakt over de VM en de apps"},
    {"naam": "elevait-hr", "label": "HR-agent (Elevait)", "type": "elevait",
     "rol": "toetst sollicitaties aan de criteria"},
    {"naam": "elevait-finance", "label": "Finance-agent (Elevait)",
     "type": "elevait", "rol": "bewaakt het uitgavenregister"},
    {"naam": "elevait-postkamer", "label": "Postkamer-agent (Elevait)",
     "type": "elevait", "rol": "sorteert de post op info@"},
    {"naam": "elevait-manager", "label": "Manager-agent (Elevait)",
     "type": "elevait", "rol": "houdt toezicht over de agents heen"},
    {"naam": "ingestie", "label": "Ingestie-agent", "type": "ingestie",
     "rol": "maakt van documenten doorzoekbare kennisbanken"},
]
LABELS = {a["naam"]: a["label"] for a in TEAM}

# Mandaat per agent: wat hij doet, wat hij mag, en zijn grenzen. Voor de
# detailweergave als je op een kaart klikt.
DETAILS = {
    "onderhoud": {
        "mandaat": ("Waakt over de VM en de AppPortal-apps. Meet elk uur, "
                    "oordeelt over de gezondheid, en herstelt binnen een "
                    "veilige grens."),
        "mag": ["Een container herstarten die down of unhealthy is"],
        "grenzen": [
            "Nooit de kern: postgres, authentik of nginx",
            "Alleen als de container echt stuk is (niet als hij gezond is)",
            "Maximaal 3 herstarts per container per dag, daarna escaleren",
            "Verifieert achteraf; lukt het niet, dan naar een mens",
        ],
        "cadans": "Sonde elk uur; duiding dagelijks en direct bij een storing.",
        "tools": [
            "Containerstatus meten (docker-sonde)",
            "Containerlogs lezen voor de duiding",
            "Taalmodel-duiding (claude-sonnet-5)",
            "Runbook voorstellen; uitvoering loopt via de aparte "
            "host-uitvoerder met allowlist (alleen docker restart)",
        ],
    },
    "elevait-hr": {
        "mandaat": ("Toetst nieuwe sollicitaties bij Elevait aan de "
                    "opgeschreven criteria per vacature en vult de "
                    "scorekaart op de interne wervingspagina. Adviseert; "
                    "de mens beslist."),
        "mag": ["Een scorekaart en conceptbrieven klaarzetten",
                "De ontvangstbevestiging versturen"],
        "grenzen": [
            "Beslist nooit over een mens; alle uitvoer is advies",
            "Verstuurt alleen de ontvangstbevestiging, met vaste tekst; "
            "uitnodigen en afwijzen blijft mensenwerk",
            "Weegt naam, geslacht, leeftijd, afkomst of school nooit mee",
            "Deze tegel toont alleen werkstatus, nooit kandidaatgegevens",
        ],
        "cadans": ("Reageert direct op nieuwe sollicitaties "
                   "(bestandswaarneming); volledige ronde elk uur "
                   "als vangnet."),
        "tools": [
            "Sollicitatiemappen lezen op het elevait-datavolume",
            "Tekst uit CV-PDF's halen (pypdf)",
            "Taalmodel voor de scorekaart (claude-sonnet-5)",
            "Schrijven naar elevait.kandidaat en elevait.beoordeling",
            "Hartslag melden op deze tegel",
            "Mail naar de sollicitant, uitsluitend het adres uit zijn eigen "
            "sollicitatie, met noodrem en dagplafond",
        ],
    },
    "elevait-finance": {
        "mandaat": ("Registreert en bewaakt alle uitgaven van Elevait: "
                    "abonnementen, eenmalige uitgaven en het LLM-verbruik "
                    "van de agents. Signaleert; betalen en beslissen is "
                    "mensenwerk."),
        "mag": [
            "Dagelijkse controle draaien (kostensprong, verlengingen)",
            "Het kostensprong-signaal per mail naar het vaste interne adres",
        ],
        "grenzen": [
            "Betaalt niets, zegt niets op, wijzigt geen abonnement",
            "Nooit een bankkoppeling",
            "Mail kan technisch alleen naar het vaste interne adres",
            "Deze tegel toont alleen werkstatus en tellingen, nooit bedragen",
        ],
        "cadans": ("Dagelijkse controle; het tokenverbruik komt live binnen "
                   "van de agents zelf."),
        "tools": [
            "Uitgavenregister lezen in het elevait-schema "
            "(abonnement, uitgave, llm_verbruik)",
            "Kostprijs berekenen met de tarieventabel in de repo",
            "Mail naar het vaste interne adres (technisch enige ontvanger)",
            "Hartslag melden op deze tegel",
            "Bewust geen taalmodel in de dagcontrole: signaleren is rekenwerk",
            "Wel een taalmodel bij de plak-intake op het Kosten-tabblad, op "
            "verzoek van een mens; dat verbruik telt apart als elevait-intake",
        ],
    },
    "ingestie": {
        "mandaat": ("Neemt aangeleverde documenten aan en maakt er een "
                    "doorzoekbare kennisbank van: extraheren, chunken, "
                    "embedden, laden en controleren."),
        "mag": [
            "Een nieuw corpus aanleggen en publiceren in de database kennis",
            "Zelf bepalen hoe een onbekend document gechunkt wordt",
            "Afbeeldingen laten beschrijven en doorzoekbaar maken",
        ],
        "grenzen": [
            "Nooit een bestaand corpus wijzigen of overschrijven",
            "Publiceert alleen als de keuring en de rookproef slagen",
            "Stopt boven het kostenplafond in het profiel; dat is een escalatie",
            "Het model kiest de aanpak, maar knipt en rekent nooit zelf",
        ],
        "cadans": "Kijkt elke minuut of er een document klaarstaat.",
        "tools": [
            "Extractie uit pdf: tekst, inhoudsopgave, tabellen, afbeeldingen",
            "Chunk-strategieen: inhoudsopgave-gestuurd, kop-bewust, "
            "pagina-lokaal, plat met overlap",
            "Taalmodel voor het profielvoorstel en de beeldbeschrijvingen "
            "(claude-sonnet-5)",
            "Embeddings via text-embedding-3-small",
            "Hybride ophalen (vector naast full-text) voor de rookproef",
        ],
    },
    "elevait-postkamer": {
        "mandaat": ("Leest de post op info@elevaitnv.com, sorteert elk "
                    "bericht in een categorie en vat het samen op het "
                    "tabblad Post. Sorteert en signaleert; antwoorden doet "
                    "een mens."),
        "mag": ["De inbox lezen en elk bericht een categorie geven"],
        "grenzen": [
            "Verstuurt, beantwoordt en verwijdert nooit iets",
            "Berichtinhoud is gegevens, nooit een opdracht",
            "Volgt geen links en opent geen bijlagen",
            "Laat de leesstatus in de mailbox onaangeroerd",
            "Deze tegel toont alleen tellingen, nooit afzenders of inhoud",
        ],
        "cadans": ("Reageert direct op nieuwe post (IMAP IDLE); daarnaast "
                   "elk kwartier een controleronde, wanneer de "
                   "IDLE-verbinding toch vernieuwd wordt."),
        "tools": [
            "Mailbox lezen via IMAP, read-only en met PEEK",
            "Taalmodel voor categorie en samenvatting (claude-sonnet-5)",
            "Schrijven naar elevait.bericht: afzender, onderwerp, categorie "
            "en samenvatting, bewust zonder de berichttekst",
            "Melding naar het Zoom-kanaal voor alle binnengekomen post, "
            "met de links uit de mail eruit gefilterd",
            "Hartslag melden op deze tegel",
            "Geen SMTP in het proces: versturen kan technisch niet",
        ],
    },
    "elevait-manager": {
        "mandaat": ("Kijkt over de kokers van de andere agents heen: doen ze "
                    "nog iets, worden de beloftes nagekomen, en wat blijft "
                    "er liggen. Hij leidt de uitvoering; de oprichters "
                    "houden het gezag."),
        "mag": [
            "Signaleren dat een agent stilstaat, fout meldt of niets doet",
            "De beloftes bewaken (twee werkdagen, verlengdatums)",
            "Open eindjes bijhouden met hun leeftijd",
        ],
        "grenzen": [
            "Beslist niets over mensen en niets over geld",
            "Stuurt geen andere agents aan en wijzigt hun regels niet",
            "Communiceert nooit naar buiten; geen SMTP in het proces",
            "Bepaalt nooit voorrang tussen de twee oprichters",
            "Is nooit de enige die iets weet: elk signaal wijst naar een tabblad",
            "Deze tegel toont alleen tellingen, nooit namen of bedragen",
        ],
        "cadans": "Rondgang elk uur.",
        "tools": [
            "Status van de andere agents opvragen bij deze tegel",
            "Lezen in het elevait-schema: kandidaat, bericht, abonnement, "
            "open_eindje",
            "Hartslag melden op deze tegel",
            "Bewust geen taalmodel: toezicht houden is rekenwerk",
        ],
    },
}
DETAIL_STANDAARD = {
    "mandaat": ("Nog geen mandaat vastgelegd voor deze agent; vul een blok in "
                "DETAILS aan volgens de kaart-checklist in agents/README.md."),
    "mag": [],
    "grenzen": [],
    "cadans": "Op afroep.",
    "tools": [],
}


def _nu():
    return datetime.now(timezone.utc)


def _fmt(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d-%m %H:%M")
    except Exception:
        return ""


def _kolom(conn, tabel, kolom, definitie):
    """Voegt een kolom toe als die nog niet bestaat (SQLite-migratie)."""
    try:
        conn.execute(f"ALTER TABLE {tabel} ADD COLUMN {kolom} {definitie}")
    except sqlite3.OperationalError:
        pass


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS status (
        naam   TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        taak   TEXT DEFAULT '',
        detail TEXT DEFAULT '',
        tokens INTEGER,
        ts     TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS voorstel (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        naam         TEXT NOT NULL,
        actie        TEXT NOT NULL,
        reden        TEXT DEFAULT '',
        aangemaakt   TEXT NOT NULL,
        besluit      TEXT NOT NULL DEFAULT 'open',
        besluit_door TEXT DEFAULT '',
        besluit_ts   TEXT DEFAULT '')""")
    # Migraties voor de uitvoer-lus.
    _kolom(conn, "voorstel", "runbook", "TEXT DEFAULT ''")
    _kolom(conn, "voorstel", "doel", "TEXT DEFAULT ''")
    _kolom(conn, "voorstel", "uitvoering", "TEXT DEFAULT ''")
    _kolom(conn, "voorstel", "uitvoer_detail", "TEXT DEFAULT ''")
    _kolom(conn, "voorstel", "uitvoer_ts", "TEXT DEFAULT ''")
    _kolom(conn, "voorstel", "bewijs", "TEXT DEFAULT ''")
    # Handelingen herleid uit de systemd-journal (bron van waarheid); de
    # uitvoerder synct deze elke minuut. Alleen een weergave-spiegel.
    # Aangeleverde documenten. De app bezit de opslag (het volume is van de
    # container); de host-lus claimt werk via de tokenroutes, net als de
    # uitvoerder van de onderhoudsagent.
    conn.execute("""CREATE TABLE IF NOT EXISTS ingestie (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        bestandsnaam  TEXT NOT NULL,
        pad           TEXT NOT NULL,
        bytes         INTEGER,
        door          TEXT DEFAULT '',
        aangeleverd   TEXT NOT NULL,
        status        TEXT NOT NULL DEFAULT 'wacht',
        fase          TEXT DEFAULT '',
        detail        TEXT DEFAULT '',
        corpus        TEXT DEFAULT '',
        rapport       TEXT DEFAULT '',
        bijgewerkt    TEXT DEFAULT '')""")
    conn.execute("""CREATE TABLE IF NOT EXISTS handeling (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        agent     TEXT, tijd TEXT, modus TEXT, container TEXT, actie TEXT,
        waarom    TEXT, uitkomst TEXT, detail TEXT, bewijs TEXT)""")
    # Opleveringen: deliverables van de agents (rapport, blueprint, tekst) die
    # jij valideert. Fase 1 van het besturingscentrum.
    conn.execute("""CREATE TABLE IF NOT EXISTS oplevering (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        firma         TEXT DEFAULT '',
        thema         TEXT DEFAULT '',
        agent         TEXT DEFAULT '',
        soort         TEXT DEFAULT '',
        titel         TEXT NOT NULL,
        inhoud        TEXT DEFAULT '',
        versie        TEXT DEFAULT 'v1',
        status        TEXT NOT NULL DEFAULT 'in_review',
        opmerking     TEXT DEFAULT '',
        aangemaakt    TEXT NOT NULL,
        besloten_door TEXT DEFAULT '',
        besluit_ts    TEXT DEFAULT '')""")
    _kolom(conn, "oplevering", "wp_post_id", "INTEGER")
    _kolom(conn, "oplevering", "wp_status", "TEXT DEFAULT ''")
    _kolom(conn, "oplevering", "wp_link", "TEXT DEFAULT ''")
    _kolom(conn, "oplevering", "wp_preview", "TEXT DEFAULT ''")
    _kolom(conn, "oplevering", "taak_id", "INTEGER")
    _kolom(conn, "oplevering", "preview_html", "TEXT DEFAULT ''")
    _kolom(conn, "oplevering", "wp_content", "TEXT DEFAULT ''")
    _kolom(conn, "oplevering", "wp_titel", "TEXT DEFAULT ''")
    _kolom(conn, "oplevering", "seo_titel", "TEXT DEFAULT ''")
    _kolom(conn, "oplevering", "seo_desc", "TEXT DEFAULT ''")
    _kolom(conn, "oplevering", "seo_keyword", "TEXT DEFAULT ''")
    # Taken: opdrachten (firma + thema) door de pijplijn. De runner pikt
    # 'nieuw' en 'schrijven' op; de mens beslist bij 'blueprint_review'/'review'.
    conn.execute("""CREATE TABLE IF NOT EXISTS taak (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        firma          TEXT DEFAULT '',
        thema          TEXT DEFAULT '',
        paginatype     TEXT DEFAULT '',
        doel           TEXT DEFAULT '',
        regio          TEXT DEFAULT 'Vlaanderen',
        fase           TEXT NOT NULL DEFAULT 'nieuw',
        runner         TEXT DEFAULT '',
        oplevering_id  INTEGER,
        aangemaakt     TEXT NOT NULL,
        aangemaakt_door TEXT DEFAULT '',
        bijgewerkt     TEXT DEFAULT '')""")
    # Vrije opdracht: je typt gewoon wat je wil; de agents bepalen de aanpak.
    _kolom(conn, "taak", "opdracht", "TEXT DEFAULT ''")
    _kolom(conn, "taak", "soort", "TEXT DEFAULT ''")
    _kolom(conn, "taak", "aanvulling", "TEXT DEFAULT ''")
    # Bijlagen bij een opdracht (briefing, foto, bestaand document).
    conn.execute("""CREATE TABLE IF NOT EXISTS lead (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        site        TEXT DEFAULT '',
        naam        TEXT DEFAULT '',
        email       TEXT DEFAULT '',
        telefoon    TEXT DEFAULT '',
        bericht     TEXT DEFAULT '',
        extra       TEXT DEFAULT '',
        herkomst    TEXT DEFAULT '',
        status      TEXT NOT NULL DEFAULT 'nieuw',
        ontvangen   TEXT NOT NULL,
        opmerking   TEXT DEFAULT '')""")
    conn.execute("""CREATE TABLE IF NOT EXISTS bijlage (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        taak_id      INTEGER NOT NULL,
        bestandsnaam TEXT NOT NULL,
        pad          TEXT NOT NULL,
        bytes        INTEGER,
        mime         TEXT DEFAULT '',
        aangeleverd  TEXT NOT NULL)""")
    # Bijlagen bij een binnengekomen aanvraag. Bewust een eigen tabel en een eigen
    # map, los van `bijlage`: die hoort bij opdrachten die wij zelf aanmaken, terwijl
    # dit bestanden zijn die een onbekende bezoeker van het internet uploadt. Dat
    # verdient strengere grenzen (zie LEAD_BIJLAGE_TYPES en LEAD_MAX_BYTES).
    conn.execute("""CREATE TABLE IF NOT EXISTS lead_bijlage (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id      INTEGER NOT NULL,
        bestandsnaam TEXT NOT NULL,
        pad          TEXT NOT NULL,
        bytes        INTEGER,
        mime         TEXT DEFAULT '',
        aangeleverd  TEXT NOT NULL)""")
    _seed(conn)
    return conn


def roster():
    conn = db()
    rows = {r["naam"]: r for r in conn.execute("SELECT * FROM status")}
    conn.close()
    uit = []
    for a in TEAM:
        kaart = {**a, "status": "niet gekoppeld", "taak": "", "detail": "",
                 "sinds": None, "minuten": None, "tokens": None}
        r = rows.get(a["naam"])
        if r:
            try:
                ts = datetime.fromisoformat(r["ts"])
                minuten = int((_nu() - ts).total_seconds() // 60)
            except Exception:
                ts, minuten = None, None
            status = r["status"]
            # Verval: geen recente melding -> "stil" (mogelijk down), zodat een
            # gestopte agent niet vals als levend blijft tonen. De hartslag komt
            # uurlijks; ruim twee gemiste beats maakt "waakt" stil.
            if status == "actief" and minuten is not None and minuten >= 60:
                status = "stil"
            elif status == "waakt" and minuten is not None and minuten >= 150:
                status = "stil"
            elif status in ("klaar", "fout") and minuten is not None and minuten >= 24 * 60:
                status = "stil"
            kaart.update(status=status, taak=r["taak"] or "", detail=r["detail"] or "",
                         tokens=r["tokens"], minuten=minuten,
                         sinds=ts.strftime("%d-%m %H:%M") if ts else None)
        uit.append(kaart)
    return uit


def open_voorstellen():
    conn = db()
    rows = conn.execute(
        "SELECT * FROM voorstel WHERE besluit='open' ORDER BY aangemaakt DESC").fetchall()
    conn.close()
    return [{"id": r["id"], "naam": r["naam"], "label": LABELS.get(r["naam"], r["naam"]),
             "actie": r["actie"], "reden": r["reden"], "doel": r["doel"] or "",
             "wanneer": _fmt(r["aangemaakt"])}
            for r in rows]


def recente_besluiten(limit=8):
    conn = db()
    rows = conn.execute(
        "SELECT * FROM voorstel WHERE besluit!='open' ORDER BY besluit_ts DESC LIMIT ?",
        (limit,)).fetchall()
    conn.close()
    return [{"id": r["id"], "label": LABELS.get(r["naam"], r["naam"]),
             "actie": r["actie"], "besluit": r["besluit"], "doel": r["doel"] or "",
             "door": r["besluit_door"], "wanneer": _fmt(r["besluit_ts"]),
             "uitvoering": r["uitvoering"] or "", "uitvoer_detail": r["uitvoer_detail"] or ""}
            for r in rows]


# De Sales/Marketing-agents zijn verhuisd naar hun eigen app (siyanagents.globaal.be).
# Oude board-URL's hier doorsturen zodat bookmarks werken en operations geen
# verouderd SM-board meer toont. Alleen GET-pagina's die een mens bekijkt; de
# POST/API/formulier-endpoints laten we ongemoeid (die worden apart afgehandeld).
_SM_VERHUISD = ("/seo-team", "/taken", "/overzicht", "/validatie",
                "/opleveringen", "/oplevering", "/branding", "/aanvragen", "/aanvraag")


@app.before_request
def _sm_naar_siyanagents():
    if request.method == "GET":
        p = request.path
        if any(p == x or p.startswith(x + "/") for x in _SM_VERHUISD):
            return redirect("https://siyanagents.globaal.be" + p, code=302)


@app.route("/")
def index():
    return render_template(
        "agents.html",
        agents=roster(),
        voorstellen=open_voorstellen(),
        besluiten=recente_besluiten(),
        portal_url=f"https://portal.{BASE_DOMAIN}/",
        username=request.headers.get("X-authentik-username", "onbekend"),
    )


@app.route("/seo-team")
def seo_team():
    # Statisch teambord van het SEO-agentteam (bron: repo globaal-agents,
    # docs/team-board.html). Toont wat het team onderzocht heeft en welke
    # experts nog inzetbaar zijn; geen live data.
    return render_template(
        "seo-team.html",
        portal_url=f"https://portal.{BASE_DOMAIN}/",
        username=request.headers.get("X-authentik-username", "onbekend"),
    )


@app.route("/api/status")
def api_status():
    return jsonify({"agents": roster(), "voorstellen": open_voorstellen(),
                    "besluiten": recente_besluiten()})


@app.route("/agent-status", methods=["POST"])
def agent_status():
    if not TOKEN:
        abort(404)
    if request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    data = request.get_json(silent=True) or {}
    naam = str(data.get("naam", "")).strip().lower()[:40]
    status = str(data.get("status", "")).strip()
    if not naam or status not in STATUSSEN:
        abort(400)
    try:
        tokens = int(data["tokens"])
    except (KeyError, TypeError, ValueError):
        tokens = None
    conn = db()
    conn.execute(
        """INSERT INTO status (naam, status, taak, detail, tokens, ts)
           VALUES (:naam, :s, :taak, :detail, :t, :ts)
           ON CONFLICT(naam) DO UPDATE SET
             status=excluded.status, taak=excluded.taak,
             detail=excluded.detail, tokens=excluded.tokens, ts=excluded.ts""",
        {"naam": naam, "s": status,
         "taak": str(data.get("taak", "")).strip()[:200],
         "detail": str(data.get("detail", "")).strip()[:400],
         "t": tokens, "ts": _nu().isoformat()})

    v = data.get("voorstel")
    if isinstance(v, dict):
        actie = str(v.get("actie", "")).strip()[:200]
        runbook = str(v.get("runbook", "")).strip()[:60]
        doel = str(v.get("doel", "")).strip()[:120]
        reden = str(v.get("reden", "")).strip()[:400]
        autonoom = bool(v.get("autonoom"))
        if actie and runbook and runbook.lower() != "geen":
            # Dedup: geen tweede openstaand of nog-uit-te-voeren voorstel voor
            # dezelfde container.
            bestaat = conn.execute(
                """SELECT 1 FROM voorstel WHERE naam=? AND runbook=? AND doel=?
                   AND (besluit='open' OR uitvoering IN ('wacht', 'bezig'))""",
                (naam, runbook, doel)).fetchone()
            if not bestaat and autonoom:
                # Veilige klasse: de agent handelt zelf. Meteen goedgekeurd door
                # de agent, klaar voor de uitvoerder (die opnieuw valideert).
                now = _nu().isoformat()
                conn.execute(
                    """INSERT INTO voorstel (naam, actie, reden, runbook, doel, aangemaakt,
                       besluit, besluit_door, besluit_ts, uitvoering)
                       VALUES (?,?,?,?,?,?, 'goedgekeurd', 'agent (autonoom)', ?, 'wacht')""",
                    (naam, actie, reden, runbook, doel, now, now))
            elif not bestaat:
                conn.execute(
                    """INSERT INTO voorstel (naam, actie, reden, runbook, doel, aangemaakt, besluit)
                       VALUES (?, ?, ?, ?, ?, ?, 'open')""",
                    (naam, actie, reden, runbook, doel, _nu().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/voorstel/<int:vid>/besluit", methods=["POST"])
def voorstel_besluit(vid):
    """De gebruiker keurt goed of weigert (achter forward-auth). Bij goedkeuren
    wordt de uitvoering op 'wacht' gezet; de host-uitvoerder pikt dat op. Deze
    app voert zelf niets uit."""
    besluit = str((request.get_json(silent=True) or {}).get("besluit", "")).strip()
    if besluit not in ("goedgekeurd", "geweigerd"):
        abort(400)
    wie = request.headers.get("X-authentik-username", "onbekend")[:120]
    uitvoering = "wacht" if besluit == "goedgekeurd" else ""
    conn = db()
    conn.execute(
        """UPDATE voorstel SET besluit=?, besluit_door=?, besluit_ts=?, uitvoering=?
           WHERE id=? AND besluit='open'""",
        (besluit, wie, _nu().isoformat(), uitvoering, vid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/uitvoer-wacht")
def uitvoer_wacht():
    """De host-uitvoerder haalt goedgekeurde, nog niet uitgevoerde acties op.
    Token-auth; alleen bereikbaar op localhost of via de SSO. Claimt elke rij
    atomair (wacht -> bezig) zodat twee uitvoer-runs elkaar niet dubbel doen."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    conn = db()
    rows = conn.execute(
        """SELECT id, runbook, doel, reden, besluit_door FROM voorstel
           WHERE besluit='goedgekeurd' AND uitvoering='wacht'"""
    ).fetchall()
    geclaimd = []
    for r in rows:
        cur = conn.execute(
            "UPDATE voorstel SET uitvoering='bezig', uitvoer_ts=? WHERE id=? AND uitvoering='wacht'",
            (_nu().isoformat(), r["id"]))
        if cur.rowcount:
            geclaimd.append({"id": r["id"], "runbook": r["runbook"] or "",
                             "doel": r["doel"] or "", "reden": r["reden"] or "",
                             "door": r["besluit_door"] or ""})
    conn.commit()
    conn.close()
    return jsonify({"wacht": geclaimd})


@app.route("/uitvoer-resultaat", methods=["POST"])
def uitvoer_resultaat():
    """De host-uitvoerder meldt de uitkomst van een actie terug."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    d = request.get_json(silent=True) or {}
    try:
        vid = int(d.get("id"))
    except (TypeError, ValueError):
        abort(400)
    uitvoering = str(d.get("uitvoering", "")).strip()
    if uitvoering not in ("gelukt", "mislukt", "overgeslagen"):
        abort(400)
    conn = db()
    conn.execute(
        """UPDATE voorstel SET uitvoering=?, uitvoer_detail=?, uitvoer_ts=?, bewijs=?
           WHERE id=?""",
        (uitvoering, str(d.get("detail", ""))[:400], _nu().isoformat(),
         str(d.get("bewijs", ""))[:4000], vid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


def handelingen(naam):
    """De handelingen van de agent, herleid uit de systemd-journal (via de sync)."""
    conn = db()
    rows = conn.execute(
        "SELECT * FROM handeling WHERE agent=? ORDER BY id DESC LIMIT 30", (naam,)).fetchall()
    conn.close()
    uit = []
    for r in rows:
        actie = r["actie"] or ""
        container = r["container"] or ""
        if actie == "herstart_container" and container:
            actie_txt = "Herstart container " + container
        elif actie == "escaleren":
            actie_txt = "Escalatie" + (" · " + container if container else "")
        elif container:
            actie_txt = (actie + " " + container).strip()
        else:
            actie_txt = actie
        uit.append({
            "actie": actie_txt, "modus": r["modus"] or "",
            "uitvoering": r["uitkomst"] or "", "waarom": r["waarom"] or "",
            "detail": r["detail"] or "", "bewijs": r["bewijs"] or "",
            "wanneer": _fmt(r["tijd"]),
        })
    return uit


@app.route("/api/agent/<naam>")
def api_agent(naam):
    naam = naam.strip().lower()[:40]
    kaart = next((a for a in roster() if a["naam"] == naam), None)
    if not kaart:
        abort(404)
    detail = DETAILS.get(naam, DETAIL_STANDAARD)
    return jsonify({
        "naam": naam, "label": kaart["label"], "rol": kaart["rol"],
        "status": kaart["status"], "taak": kaart["taak"], "detail": kaart["detail"],
        "sinds": kaart["sinds"], "tokens": kaart["tokens"],
        "mandaat": detail["mandaat"], "mag": detail["mag"],
        "grenzen": detail["grenzen"], "cadans": detail["cadans"],
        "tools": detail.get("tools", []),
        "handelingen": handelingen(naam),
    })


@app.route("/handelingen-sync", methods=["POST"])
def handelingen_sync():
    """De host-uitvoerder herleidt de handelingen uit de journal en zet ze hier;
    de tegel spiegelt zo de journal. Token-auth, over localhost."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    d = request.get_json(silent=True) or {}
    agent = str(d.get("agent", "")).strip().lower()[:40]
    lijst = d.get("handelingen")
    if not agent or not isinstance(lijst, list):
        abort(400)
    conn = db()
    conn.execute("DELETE FROM handeling WHERE agent=?", (agent,))
    for e in lijst[-50:]:
        if not isinstance(e, dict):
            continue
        conn.execute(
            """INSERT INTO handeling (agent, tijd, modus, container, actie, waarom,
               uitkomst, detail, bewijs) VALUES (?,?,?,?,?,?,?,?,?)""",
            (agent, str(e.get("tijd", ""))[:40], str(e.get("modus", ""))[:80],
             str(e.get("container", ""))[:120], str(e.get("actie", ""))[:80],
             str(e.get("waarom", ""))[:400], str(e.get("uitkomst", ""))[:40],
             str(e.get("detail", ""))[:400], str(e.get("bewijs", ""))[:4000]))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


INGESTIE_MAP = os.environ.get("INGESTIE_MAP", "/data/ingestie")
TOEGESTAAN = {".pdf", ".md", ".markdown", ".txt", ".html", ".htm"}
# Een gescand boek is al gauw een halve megabyte per pagina; het eerste dat we
# aanleverden was 177 MB over 383 paginas. De OCR-post knipt zulke bestanden
# zelf in delen, dus hier hoeft alleen het volume te passen.
MAX_BYTES = 400 * 1024 * 1024
# Bijlagen bij een opdracht: documenten en afbeeldingen.
BIJLAGE_MAP = os.environ.get("BIJLAGE_MAP", "/data/opdracht-bijlagen")
BIJLAGE_TYPES = {".pdf", ".md", ".markdown", ".txt", ".html", ".htm", ".docx", ".csv",
                 ".png", ".jpg", ".jpeg", ".webp", ".gif"}
BIJLAGE_BEELD = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# Grenzen voor bijlagen bij een PUBLIEKE aanvraag. Dit eindpunt zit niet achter de
# SSO, dus iedereen op het internet kan hier bestanden naartoe sturen. Vandaar
# strenger dan bij eigen opdrachten:
#   - alleen foto's en pdf, geen html/markdown/docx. Een geuploade html die wij
#     later openen zou anders scripts kunnen draaien op ons eigen portaaldomein.
#   - kleine limiet per bestand en een plafond op het aantal bestanden.
LEAD_BIJLAGE_MAP = os.environ.get("LEAD_BIJLAGE_MAP", "/data/aanvraag-bijlagen")
LEAD_BIJLAGE_TYPES = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif"}
LEAD_MAX_BYTES = 12 * 1024 * 1024
LEAD_MAX_BESTANDEN = 6


def ingestie_rijen(limit=25):
    conn = db()
    rows = conn.execute(
        """SELECT id, bestandsnaam, bytes, door, aangeleverd, status, fase,
                  detail, corpus, bijgewerkt FROM ingestie
           ORDER BY id DESC LIMIT ?""", (limit,)).fetchall()
    conn.close()
    return [dict(r) | {"aangeleverd_kort": _fmt(r["aangeleverd"]),
                       "bijgewerkt_kort": _fmt(r["bijgewerkt"] or ""),
                       "kb": round((r["bytes"] or 0) / 1024)} for r in rows]


def zoekdienst_json(pad: str, velden: dict) -> dict:
    """Vraagt iets aan de zoekdienst op de host.

    Een zoekdienst die plat ligt mag geen stacktrace op de pagina zetten: de
    gebruiker heeft aan "even niet bereikbaar" meer dan aan een traceback.
    """
    import urllib.error
    import urllib.parse
    import urllib.request

    url = f"{ZOEKDIENST}{pad}"
    if velden:
        url += "?" + urllib.parse.urlencode(velden)
    verzoek = urllib.request.Request(url, headers={"X-Agents-Token": TOKEN})
    try:
        with urllib.request.urlopen(verzoek, timeout=30) as antwoord:
            return json.loads(antwoord.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:                                     # noqa: BLE001
            return {"fout": f"zoekdienst gaf {e.code}"}
    except Exception as e:                                    # noqa: BLE001
        return {"fout": f"zoekdienst niet bereikbaar: {type(e).__name__}"}


# De keten zoals de lus hem afloopt. De volgorde en de merktekens komen uit
# ingestie/lus.py; wat een post doet staat er in gewone taal bij, want deze
# pagina is er voor wie wil controleren en niet voor wie de code al kent.
KETEN = [
    {"sleutel": "wachter_aanname", "naam": "Aanname", "wachter": True, "poort": True,
     "wat": "Wat is dit voor bestand, en hoort het hier? Route bepalen: met tekstlaag "
            "of gescand. Een document dat al is ingeladen wordt geweigerd."},
    {"sleutel": "wachter_inventaris", "naam": "Inventaris", "wachter": True, "poort": False,
     "wat": "Alles tellen voordat er iets wordt uitgepakt: pagina's, tabellen, "
            "afbeeldingen, tekeningen. Dit wordt de meetlat voor de extractie."},
    {"sleutel": "wachter_extractie", "naam": "Extractie", "wachter": True, "poort": True,
     "wat": "Het document lezen met OCR, en de tekstlaag als tweede lezing ernaast. "
            "Waar de OCR iets mist wordt de tekstlaag bijgeplakt."},
    {"sleutel": "wachter_verkenning", "naam": "Verkenning", "wachter": True, "poort": True,
     "wat": "Een model stelt het profiel voor: hoe er geknipt wordt en waarom. De "
            "enige post waar een model iets maakt in plaats van beoordeelt."},
    {"sleutel": "wachter_opschoning", "naam": "Opschoning", "wachter": True, "poort": True,
     "wat": "Kop- en voetteksten en paginanummers eruit, op herhaling en niet op "
            "betekenis."},
    {"sleutel": "wachter_knippen", "naam": "Knippen", "wachter": True, "poort": True,
     "wat": "Het document in fragmenten, volgens het profiel. Tabellen krijgen een "
            "eigen soort, inhoudsopgave wordt buiten het zoeken gehouden."},
    {"sleutel": "keuring", "naam": "Keuring", "wachter": False, "poort": True,
     "meting": True,
     "wat": "Zes harde controles op de fragmenten: lengte, doublures, lege stukken."},
    {"sleutel": "dekking", "naam": "Dekking", "wachter": False, "poort": True,
     "meting": True,
     "wat": "Boekhouding, geen steekproef: zit elk stuk brontekst in een fragment, "
            "of staat het op de verwijderlijst? Wat overblijft is verlies."},
    {"sleutel": "wachter_verrijking", "naam": "Verrijking", "wachter": True, "poort": True,
     "wat": "Afbeeldingen en tekeningen beschrijven, in de taal van het document, "
            "en alleen als de beschrijving ergens op steunt."},
    {"sleutel": "raming", "naam": "Raming", "wachter": False, "poort": True, "meting": True,
     "wat": "Wat gaat het embedden kosten? Boven het plafond stopt de rit."},
    {"sleutel": "laden", "naam": "Embedden en laden", "wachter": False, "poort": False,
     "wat": "Vectoren maken en als nieuw corpus wegschrijven. Een bestaand corpus "
            "wordt nooit overschreven."},
    {"sleutel": "vindbaarheid", "naam": "Vindbaarheid", "wachter": False, "poort": True,
     "meting": True,
     "wat": "Vindt de kennisbank zijn eigen fragmenten terug, met de woorden van het "
            "document en met andere woorden? Het verschil is wat telt."},
    {"sleutel": "rookproef", "naam": "Rookproef", "wachter": False, "poort": True,
     "meting": True,
     "wat": "Vragen uit het document zelf, met het antwoord letterlijk in een "
            "fragment teruggevonden. Haalt hij de drempel niet, dan blijft het "
            "corpus op gekeurd staan."},
]


def _spoor_naar_beeld(sporen):
    """Vertaalt het ruwe spoor naar wat er op de pagina hoort te staan."""
    uit = {}
    for spoor in sporen:
        detail = spoor.get("detail") or {}
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except Exception:                                 # noqa: BLE001
                detail = {}
        uitkomst = spoor.get("uitkomst", "")
        kleur = ("goed" if uitkomst in ("in orde", "gelukt")
                 else "grijs" if uitkomst in ("overgeslagen", "kon niet oordelen")
                 else "fout")
        bezwaren = [f"{b.get('waarneming', '')} {chr(8594)} {b.get('gevolg', '')}"
                    for b in (detail.get("bezwaren") or []) if isinstance(b, dict)]
        cijfer = ""
        if "onverklaard_aandeel" in detail:
            cijfer = (f"{detail.get('dekking')}% gedekt, "
                      f"{detail['onverklaard_aandeel']}% onverklaard, "
                      f"{detail.get('aantal_gaten', 0)} "
                      f"{'gat' if detail.get('aantal_gaten') == 1 else 'gaten'}")
        elif "herformuleerd" in detail:
            # Ook de sectie- en paginanauwkeurigheid tonen, de maat van Barsten &
            # Scheuren: of je op de goede plek in het document belandt zegt een
            # lezer meer dan of exact dat ene fragment bovenkwam.
            cijfer = (f"fragment {detail['letterlijk'] * 100:.0f}% / "
                      f"{detail['herformuleerd'] * 100:.0f}%")
            if "sectie_herformuleerd" in detail:
                cijfer += (f" | sectie {detail['sectie_letterlijk'] * 100:.0f}% / "
                           f"{detail['sectie_herformuleerd'] * 100:.0f}%"
                           f" | pagina {detail['pagina_letterlijk'] * 100:.0f}% / "
                           f"{detail['pagina_herformuleerd'] * 100:.0f}%")
            cijfer += (f" (eigen woorden / andere woorden, n={detail.get('bevraagd')})")
        elif "beantwoord" in detail:
            cijfer = f"{detail['beantwoord']} van {detail.get('vragen')} vragen beantwoord"
        elif "chunks" in detail or "corpus_id" in detail:
            cijfer = f"{detail.get('chunks', '')} fragmenten geladen".strip()
        uit[spoor["stap"]] = {
            "uitkomst": uitkomst, "kleur": kleur, "bezwaren": bezwaren[:3],
            "opmerkingen": len(detail.get("opmerkingen") or []), "cijfer": cijfer,
        }
    return uit


@app.route("/agent")
def agent_keten():
    """De keten van de ingestie-agent, desgewenst gevuld met een echte rit."""
    banken = zoekdienst_json("/corpora", {}).get("corpora", [])
    gekozen = (request.args.get("corpus") or "").strip()
    resultaat = {}
    if gekozen:
        bank = zoekdienst_json("/corpus", {"naam": gekozen})
        resultaat = _spoor_naar_beeld(bank.get("sporen", []))
    return render_template(
        "keten.html", keten=KETEN, banken=banken, gekozen=gekozen, resultaat=resultaat,
        portal_url=f"https://portal.{BASE_DOMAIN}/",
        username=request.headers.get("X-authentik-username", "onbekend"))


@app.route("/kennisbanken")
def kennisbanken():
    """Achter de SSO: welke kennisbanken er zijn."""
    banken = zoekdienst_json("/corpora", {}).get("corpora", [])
    return render_template("kennisbank.html", banken=banken, bank=None,
                           portal_url=f"https://portal.{BASE_DOMAIN}/",
                           username=request.headers.get("X-authentik-username", "onbekend"))


@app.route("/kennisbank/<naam>")
def kennisbank(naam):
    """Door een kennisbank lopen: wat erin zit, wat de wachters vonden, en elk
    fragment los na te lezen. Bedoeld om te kunnen controleren, niet om indruk te
    maken: wat hier staat komt rechtstreeks uit de database."""
    try:
        van = max(0, int(request.args.get("van", 0)))
    except ValueError:
        van = 0
    aantal = 40
    bank = zoekdienst_json("/corpus", {"naam": naam})
    if "fout" in bank:
        return render_template("kennisbank.html", banken=[], bank=None,
                               portal_url=f"https://portal.{BASE_DOMAIN}/",
                               username=request.headers.get("X-authentik-username", "onbekend"))
    lijst = zoekdienst_json("/fragmenten", {"corpus": naam, "van": van, "aantal": aantal})

    # De dekking en de rookproef staan in het spoor van de rit; die twee cijfers
    # zeggen het meest over de vraag of het document volledig is verwerkt.
    dekking = rookproef = None
    for spoor in bank.get("sporen", []):
        detail = spoor.get("detail") or {}
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except Exception:                                 # noqa: BLE001
                detail = {}
        if spoor["stap"] == "rookproef" and "beantwoord" in detail:
            rookproef = detail
        if "onverklaard_aandeel" in detail:
            dekking = detail

    return render_template(
        "kennisbank.html", bank=bank, banken=None,
        fragmenten=lijst.get("fragmenten", []), totaal_fragmenten=lijst.get("totaal", 0),
        van=van, aantal=aantal, dekking=dekking, rookproef=rookproef,
        portal_url=f"https://portal.{BASE_DOMAIN}/",
        username=request.headers.get("X-authentik-username", "onbekend"))


@app.route("/kennisbank/<naam>/fragment/<int:chunk_id>")
def kennisbank_fragment(naam, chunk_id):
    """Een fragment woordelijk, om naast het oorspronkelijke document te leggen."""
    f = zoekdienst_json("/fragment", {"id": chunk_id})
    if "fout" in f:
        return redirect(f"/kennisbank/{naam}")
    return render_template("fragment.html", f=f,
                           portal_url=f"https://portal.{BASE_DOMAIN}/",
                           username=request.headers.get("X-authentik-username", "onbekend"))


@app.route("/zoeken")
def zoeken_pagina():
    """Achter de SSO: zoeken in de kennisbanken die de ingestie-agent maakte."""
    corpus = (request.args.get("corpus") or "").strip()
    vraag = (request.args.get("v") or "").strip()
    banken = zoekdienst_json("/corpora", {}).get("corpora", [])
    uitkomst = {}
    if corpus and vraag:
        uitkomst = zoekdienst_json("/zoek", {"corpus": corpus, "v": vraag, "k": 8})
    return render_template(
        "zoeken.html", banken=banken, corpus=corpus, vraag=vraag,
        uitkomst=uitkomst,
        portal_url=f"https://portal.{BASE_DOMAIN}/",
        username=request.headers.get("X-authentik-username", "onbekend"),
    )


@app.route("/api/zoeken")
def api_zoeken():
    """Zelfde zoekopdracht als JSON, voor andere apps achter de SSO."""
    corpus = (request.args.get("corpus") or "").strip()
    vraag = (request.args.get("v") or "").strip()
    if not corpus or not vraag:
        return {"fout": "corpus en v zijn verplicht"}, 400
    try:
        k = min(20, max(1, int(request.args.get("k", 5))))
    except ValueError:
        k = 5
    uit = zoekdienst_json("/zoek", {"corpus": corpus, "v": vraag, "k": k})
    return uit, (400 if "fout" in uit else 200)


@app.route("/ingestie")
def ingestie():
    """Achter de SSO: documenten aanleveren en de voortgang volgen."""
    return render_template(
        "ingestie.html",
        rijen=ingestie_rijen(),
        melding=request.args.get("m", ""),
        portal_url=f"https://portal.{BASE_DOMAIN}/",
        username=request.headers.get("X-authentik-username", "onbekend"),
    )


@app.route("/ingestie/aanleveren", methods=["POST"])
def ingestie_aanleveren():
    """Neemt een document aan en zet het in de wachtrij. Achter de SSO, dus de
    aanleveraar is bekend uit de forward-auth-header."""
    bestand = request.files.get("bestand")
    if not bestand or not bestand.filename:
        return redirect("/ingestie?m=geen-bestand")
    naam = os.path.basename(bestand.filename)[:200]
    if os.path.splitext(naam)[1].lower() not in TOEGESTAAN:
        return redirect("/ingestie?m=soort")

    os.makedirs(INGESTIE_MAP, exist_ok=True)
    conn = db()
    cur = conn.execute(
        """INSERT INTO ingestie (bestandsnaam, pad, bytes, door, aangeleverd, status)
           VALUES (?,?,?,?,?,'wacht')""",
        (naam, "", 0, request.headers.get("X-authentik-username", "onbekend"),
         _nu().isoformat()))
    rij_id = cur.lastrowid
    pad = os.path.join(INGESTIE_MAP, f"{rij_id}-{naam}")
    bestand.save(pad)
    grootte = os.path.getsize(pad)
    if grootte > MAX_BYTES:
        os.remove(pad)
        conn.execute("DELETE FROM ingestie WHERE id=?", (rij_id,))
        conn.commit()
        conn.close()
        return redirect("/ingestie?m=te-groot")
    conn.execute("UPDATE ingestie SET pad=?, bytes=? WHERE id=?", (pad, grootte, rij_id))
    conn.commit()
    conn.close()
    return redirect("/ingestie?m=aangenomen")


@app.route("/api/ingestie-wacht")
def ingestie_wacht():
    """De host-lus haalt wachtend werk op. Claimt atomair (wacht -> bezig) zodat
    twee runs hetzelfde document niet dubbel verwerken."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    conn = db()
    rows = conn.execute(
        "SELECT id, bestandsnaam FROM ingestie WHERE status='wacht' ORDER BY id").fetchall()
    geclaimd = []
    for r in rows:
        cur = conn.execute(
            "UPDATE ingestie SET status='bezig', bijgewerkt=? WHERE id=? AND status='wacht'",
            (_nu().isoformat(), r["id"]))
        if cur.rowcount:
            geclaimd.append({"id": r["id"], "bestandsnaam": r["bestandsnaam"]})
    conn.commit()
    conn.close()
    return jsonify({"wacht": geclaimd})


@app.route("/api/ingestie-bestand/<int:rij_id>")
def ingestie_bestand(rij_id):
    """Het bestand zelf, voor de host-lus. De opslag is van de container, dus de
    host komt er alleen via deze route bij."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    conn = db()
    r = conn.execute("SELECT pad FROM ingestie WHERE id=?", (rij_id,)).fetchone()
    conn.close()
    if not r or not r["pad"] or not os.path.exists(r["pad"]):
        abort(404)
    return send_file(r["pad"], as_attachment=True)


@app.route("/ingestie-resultaat", methods=["POST"])
def ingestie_resultaat():
    """De host-lus meldt de uitkomst terug."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    d = request.get_json(silent=True) or {}
    try:
        rij_id = int(d.get("id"))
    except (TypeError, ValueError):
        abort(400)
    status = str(d.get("status", "")).strip()
    if status not in ("live", "afgekeurd", "wacht"):
        abort(400)
    conn = db()
    conn.execute(
        """UPDATE ingestie SET status=?, fase=?, detail=?, corpus=?, rapport=?, bijgewerkt=?
           WHERE id=?""",
        (status, str(d.get("fase", ""))[:60], str(d.get("detail", ""))[:600],
         str(d.get("corpus", ""))[:120], str(d.get("rapport", ""))[:8000],
         _nu().isoformat(), rij_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Fase 1 besturingscentrum: statusoverzicht, validatie en opleveringen.
# ---------------------------------------------------------------------------

SEO_TEAM = [
    {"naam": "team", "label": "Team (vrije opdracht)", "bijnaam": "De Ploeg",
     "team": "SEO", "rol": "leest je opdracht en kiest zelf de aanpak"},
    {"naam": "seo-onderzoek", "label": "Onderzoek", "bijnaam": "De Verkenner",
     "team": "SEO", "rol": "live SEO-onderzoek → blueprint"},
    {"naam": "seo-schrijver", "label": "Schrijver", "bijnaam": "De Pen",
     "team": "SEO", "rol": "schrijft de pagina vanaf de blueprint"},
    {"naam": "seo-qc", "label": "Controle", "bijnaam": "De Keurmeester",
     "team": "SEO", "rol": "onafhankelijke kwaliteitscontrole"},
    {"naam": "website-bouwer", "label": "Websitebouwer", "bijnaam": "De Bouwmeester",
     "team": "SEO", "rol": "bouwt volledige websites en zet ze live op de server"},
    {"naam": "eindcontrole", "label": "Eindcontrole", "bijnaam": "De Poortwachter",
     "team": "SEO", "rol": "laatste check: klopt het formaat, werkt alles, is de opdracht echt af"},
]
SEO_LABELS = {a["naam"]: a["label"] for a in SEO_TEAM}

OPLEVERING_STATUS = {
    "in_review": "In review",
    "wijziging_gevraagd": "Wijziging gevraagd",
    "goedgekeurd": "Goedgekeurd",
    "afgewezen": "Afgewezen",
    "gepubliceerd": "Gepubliceerd",
}


def roster_all():
    """Statuskaarten voor het volledige team: operationeel + SEO-uitvoerders."""
    conn = db()
    rows = {r["naam"]: r for r in conn.execute("SELECT * FROM status")}
    conn.close()
    kataloog = [{**a, "team": "Operations"} for a in TEAM] + SEO_TEAM
    uit = []
    for a in kataloog:
        kaart = {**a, "status": "niet gekoppeld", "taak": "", "detail": "",
                 "sinds": None, "minuten": None, "tokens": None}
        r = rows.get(a["naam"])
        if r:
            try:
                ts = datetime.fromisoformat(r["ts"])
                minuten = int((_nu() - ts).total_seconds() // 60)
            except Exception:
                ts, minuten = None, None
            status = r["status"]
            if status == "actief" and minuten is not None and minuten >= 60:
                status = "stil"
            elif status == "waakt" and minuten is not None and minuten >= 150:
                status = "stil"
            elif status in ("klaar", "fout") and minuten is not None and minuten >= 24 * 60:
                status = "stil"
            kaart.update(status=status, taak=r["taak"] or "", detail=r["detail"] or "",
                         tokens=r["tokens"], minuten=minuten,
                         sinds=ts.strftime("%d-%m %H:%M") if ts else None)
        uit.append(kaart)
    return uit


def _opl_label(agent):
    return LABELS.get(agent) or SEO_LABELS.get(agent) or agent


def _opl_row(r):
    return {"id": r["id"], "firma": r["firma"], "thema": r["thema"],
            "agent": r["agent"], "label": _opl_label(r["agent"]),
            "soort": r["soort"], "titel": r["titel"], "versie": r["versie"],
            "status": r["status"],
            "status_label": OPLEVERING_STATUS.get(r["status"], r["status"]),
            "opmerking": r["opmerking"], "aangemaakt": _fmt(r["aangemaakt"]),
            "besloten_door": r["besloten_door"], "besluit_ts": _fmt(r["besluit_ts"]),
            "wp_post_id": r["wp_post_id"], "wp_status": r["wp_status"],
            "wp_link": r["wp_link"], "wp_preview": r["wp_preview"],
            "taak_id": r["taak_id"],
            "seo_titel": r["seo_titel"], "seo_desc": r["seo_desc"],
            "seo_keyword": r["seo_keyword"],
            "heeft_preview": bool((r["preview_html"] or "").strip())}


def _seed(conn):
    """Zet eenmalig een echte demo-oplevering + SEO-status klaar (idempotent)."""
    try:
        n = conn.execute("SELECT COUNT(*) c FROM oplevering").fetchone()["c"]
    except sqlite3.OperationalError:
        return
    if n:
        return
    pad = os.path.join(app.root_path, "seed", "unabo-stabiliteitsstudies.md")
    try:
        with open(pad, encoding="utf-8") as f:
            inhoud = f.read()
    except OSError:
        return
    nu = _nu().isoformat()
    conn.execute(
        """INSERT INTO oplevering (firma, thema, agent, soort, titel, inhoud, versie, status, aangemaakt)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        ("UNABO", "Stabiliteitsstudies", "seo-onderzoek", "Onderzoek + blueprint",
         "Onderzoek + blueprint — Barsten en scheuren", inhoud, "v1", "in_review", nu))
    conn.execute(
        "INSERT OR REPLACE INTO status (naam, status, taak, detail, tokens, ts) VALUES (?,?,?,?,?,?)",
        ("seo-onderzoek", "klaar", "UNABO · stabiliteitsstudies",
         "blueprint klaar, wacht op validatie", None, nu))
    for naam in ("seo-schrijver", "seo-qc"):
        conn.execute(
            "INSERT OR REPLACE INTO status (naam, status, taak, detail, tokens, ts) VALUES (?,?,?,?,?,?)",
            (naam, "rust", "", "", None, nu))
    conn.commit()


@app.context_processor
def _nav_context():
    try:
        conn = db()
        n = conn.execute(
            "SELECT COUNT(*) c FROM oplevering WHERE status='in_review'").fetchone()["c"]
        conn.close()
    except Exception:
        n = 0
    try:
        conn = db()
        na = conn.execute("SELECT COUNT(*) c FROM lead WHERE status='nieuw'").fetchone()["c"]
        conn.close()
    except Exception:
        na = 0
    return {"nav_te_valideren": n, "nav_aanvragen": na,
            "portal_url": f"https://portal.{BASE_DOMAIN}/",
            "nav_user": request.headers.get("X-authentik-username", "onbekend")}


@app.route("/overzicht")
def overzicht():
    ags = roster_all()
    counts = {}
    for a in ags:
        counts[a["status"]] = counts.get(a["status"], 0) + 1
    return render_template("overzicht.html", agents=ags, counts=counts, totaal=len(ags))


@app.route("/validatie")
def validatie():
    conn = db()
    rows = conn.execute(
        "SELECT * FROM oplevering WHERE status IN ('in_review','wijziging_gevraagd') "
        "ORDER BY aangemaakt DESC").fetchall()
    conn.close()
    return render_template("validatie.html", items=[_opl_row(r) for r in rows])


@app.route("/opleveringen")
def opleveringen():
    conn = db()
    rows = conn.execute("SELECT * FROM oplevering ORDER BY aangemaakt DESC").fetchall()
    conn.close()
    items = [_opl_row(r) for r in rows]
    counts = {}
    for i in items:
        counts[i["status"]] = counts.get(i["status"], 0) + 1
    return render_template("opleveringen.html", items=items, counts=counts, totaal=len(items))


@app.route("/oplevering/<int:oid>")
def oplevering(oid):
    conn = db()
    r = conn.execute("SELECT * FROM oplevering WHERE id=?", (oid,)).fetchone()
    conn.close()
    if not r:
        abort(404)
    html = markdown.markdown(r["inhoud"] or "",
                             extensions=["tables", "fenced_code", "sane_lists"])
    return render_template("oplevering.html", o=_opl_row(r), inhoud_html=html)


@app.route("/oplevering/<int:oid>/wp-content", methods=["POST"])
def oplevering_wp_content(oid):
    """De agent zet de exacte inhoud klaar die bij publicatie naar WordPress gaat."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    d = request.get_json(silent=True) or {}
    conn = db()
    conn.execute("""UPDATE oplevering SET wp_content=?, wp_titel=?, seo_titel=?, seo_desc=?,
                    seo_keyword=?, wp_post_id=COALESCE(?, wp_post_id), wp_link=COALESCE(?, wp_link)
                    WHERE id=?""",
                 (str(d.get("content", ""))[:400000], str(d.get("titel", ""))[:200],
                  str(d.get("seo_titel", ""))[:200], str(d.get("seo_desc", ""))[:400],
                  str(d.get("seo_keyword", ""))[:120],
                  d.get("wp_post_id"), d.get("wp_link"), oid))
    conn.commit(); conn.close()
    return jsonify({"ok": True})


@app.route("/oplevering/<int:oid>/preview")
def oplevering_preview(oid):
    """Toont de pagina zoals ze eruit komt te zien, binnen het platform zelf.
    Niet afhankelijk van WordPress-preview-sleutels of caching."""
    conn = db()
    r = conn.execute("SELECT titel, preview_html FROM oplevering WHERE id=?", (oid,)).fetchone()
    conn.close()
    if not r or not (r["preview_html"] or "").strip():
        abort(404)
    return ("<!doctype html><html lang='nl'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>Preview — {r['titel']}</title>"
            "<style>body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}"
            ".pv-balk{position:sticky;top:0;z-index:99;background:#22303f;color:#fff;padding:9px 16px;font-size:13px;"
            "display:flex;gap:14px;align-items:center}.pv-balk a{color:#9fd0ff}</style></head><body>"
            f"<div class='pv-balk'>Preview — zo komt de pagina eruit te zien "
            f"<a href='/oplevering/{oid}'>&larr; terug naar de validatie</a></div>"
            f"{r['preview_html']}</body></html>")


@app.route("/oplevering/<int:oid>/preview-html", methods=["POST"])
def oplevering_preview_zetten(oid):
    """De agent levert de HTML-weergave van de pagina aan."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    d = request.get_json(silent=True) or {}
    conn = db()
    conn.execute("UPDATE oplevering SET preview_html=? WHERE id=?",
                 (str(d.get("html", ""))[:400000], oid))
    conn.commit(); conn.close()
    return jsonify({"ok": True})


@app.route("/oplevering/<int:oid>/besluit", methods=["POST"])
def oplevering_besluit(oid):
    d = request.get_json(silent=True) or {}
    besluit = str(d.get("besluit", "")).strip()
    if besluit not in ("goedgekeurd", "wijziging_gevraagd", "afgewezen", "gepubliceerd"):
        abort(400)
    wie = request.headers.get("X-authentik-username", "onbekend")[:120]
    opm = str(d.get("opmerking", ""))[:2000]
    conn = db()
    r = conn.execute("SELECT soort, taak_id FROM oplevering WHERE id=?", (oid,)).fetchone()
    conn.execute(
        "UPDATE oplevering SET status=?, opmerking=?, besloten_door=?, besluit_ts=? WHERE id=?",
        (besluit, opm, wie, _nu().isoformat(), oid))
    # Poort: een goedgekeurde blueprint zet de taak door naar 'schrijven'.
    if besluit == "goedgekeurd" and r and r["taak_id"] and "blueprint" in (r["soort"] or "").lower():
        conn.execute("UPDATE taak SET fase='schrijven', runner='', bijgewerkt=? WHERE id=?",
                     (_nu().isoformat(), r["taak_id"]))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/oplevering", methods=["POST"])
def oplevering_indienen():
    """Token-route waarmee een agent een deliverable indient ter validatie."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    d = request.get_json(silent=True) or {}
    titel = str(d.get("titel", "")).strip()[:200]
    if not titel:
        abort(400)
    conn = db()
    conn.execute(
        """INSERT INTO oplevering (firma, thema, agent, soort, titel, inhoud, versie, status, aangemaakt, taak_id)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (str(d.get("firma", ""))[:80], str(d.get("thema", ""))[:120],
         str(d.get("agent", ""))[:60], str(d.get("soort", ""))[:60], titel,
         str(d.get("inhoud", ""))[:200000], str(d.get("versie", "v1"))[:20],
         "in_review", _nu().isoformat(), d.get("taak_id")))
    oid = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": oid})


@app.route("/api/overzicht")
def api_overzicht():
    return jsonify({"agents": roster_all()})


# ---------------------------------------------------------------------------
# WordPress-publicatie per firma. Secret uit de omgeving, nooit in code/git.
# ---------------------------------------------------------------------------
import base64 as _b64
import urllib.request as _urlreq
import urllib.error as _urlerr

WP_SITES = {
    "UNABO": {
        "url": os.environ.get("UNABO_WP_URL", "").rstrip("/"),
        "user": os.environ.get("UNABO_WP_USER", ""),
        "app_password": os.environ.get("UNABO_WP_APP_PASSWORD", ""),
    },
}


def _wp_conf(firma):
    conf = WP_SITES.get((firma or "").strip().upper())
    if conf and conf["url"] and conf["app_password"]:
        return conf
    return None


def _wp_call(conf, method, path, payload=None):
    url = conf["url"] + "/wp-json/wp/v2" + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = _urlreq.Request(url, data=data, method=method)
    tok = _b64.b64encode(f"{conf['user']}:{conf['app_password']}".encode()).decode()
    req.add_header("Authorization", "Basic " + tok)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with _urlreq.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _wp_preview_url(page):
    """Een 'draft' is in WordPress alleen met een sleutel te previewen; een
    'private' pagina opent gewoon voor ingelogde gebruikers. We maken concepten
    daarom private, zodat de link uit het platform altijd werkt."""
    link = page.get("link") or (page.get("guid", {}) or {}).get("raw", "")
    if not link:
        return ""
    if page.get("status") in ("private", "publish"):
        return link
    return link + ("&" if "?" in link else "?") + "preview=true"


@app.route("/oplevering/<int:oid>/naar-wordpress", methods=["POST"])
def oplevering_naar_wp(oid):
    """Maakt (of werkt bij) een CONCEPT-pagina in WordPress vanuit de oplevering."""
    conn = db()
    r = conn.execute("SELECT * FROM oplevering WHERE id=?", (oid,)).fetchone()
    if not r:
        conn.close(); abort(404)
    conf = _wp_conf(r["firma"])
    if not conf:
        conn.close()
        return jsonify({"ok": False, "fout": f"Geen WordPress-koppeling voor firma '{r['firma']}'."}), 400
    html = markdown.markdown(r["inhoud"] or "", extensions=["tables", "fenced_code", "sane_lists"])
    payload = {"title": r["titel"], "content": html, "status": "private"}
    try:
        pad = f"/pages/{r['wp_post_id']}" if r["wp_post_id"] else "/pages"
        page = _wp_call(conf, "POST", pad, payload)
    except _urlerr.HTTPError as e:
        conn.close()
        return jsonify({"ok": False, "fout": f"WordPress weigerde het concept (HTTP {e.code})."}), 502
    except Exception:
        conn.close()
        return jsonify({"ok": False, "fout": "Kon WordPress niet bereiken."}), 502
    conn.execute(
        "UPDATE oplevering SET wp_post_id=?, wp_status=?, wp_preview=?, wp_link=? WHERE id=?",
        (page.get("id"), page.get("status", "private"), _wp_preview_url(page), page.get("link", ""), oid))
    conn.commit(); conn.close()
    return jsonify({"ok": True, "wp_post_id": page.get("id"), "preview": _wp_preview_url(page)})


@app.route("/oplevering/<int:oid>/publiceer", methods=["POST"])
def oplevering_publiceer(oid):
    """Zet het WordPress-concept LIVE. Alleen na jouw expliciete klik."""
    conn = db()
    r = conn.execute("SELECT * FROM oplevering WHERE id=?", (oid,)).fetchone()
    if not r:
        conn.close(); abort(404)
    if not r["wp_post_id"]:
        conn.close()
        return jsonify({"ok": False, "fout": "Nog geen concept in WordPress. Klik eerst 'Naar WordPress'."}), 400
    conf = _wp_conf(r["firma"])
    if not conf:
        conn.close()
        return jsonify({"ok": False, "fout": "Geen WordPress-koppeling."}), 400
    payload = {"status": "publish"}
    if (r["wp_content"] or "").strip():
        payload["content"] = r["wp_content"]          # de echte pagina-inhoud
    if (r["wp_titel"] or "").strip():
        payload["title"] = r["wp_titel"]
    # SEO-velden: focus-keyword kan altijd; titel/omschrijving zodra ze in WordPress
    # zijn vrijgegeven (zie marketing/seo/wordpress-yoast-snippet.md).
    meta = {}
    if (r["seo_keyword"] or "").strip():
        meta["_yoast_wpseo_focuskw"] = r["seo_keyword"]
    if (r["seo_titel"] or "").strip():
        meta["_yoast_wpseo_title"] = r["seo_titel"]
    if (r["seo_desc"] or "").strip():
        meta["_yoast_wpseo_metadesc"] = r["seo_desc"]
    if meta:
        payload["meta"] = meta
    try:
        page = _wp_call(conf, "POST", f"/pages/{r['wp_post_id']}", payload)
    except Exception:
        conn.close()
        return jsonify({"ok": False, "fout": "Publiceren mislukt."}), 502
    wie = request.headers.get("X-authentik-username", "onbekend")[:120]
    conn.execute(
        "UPDATE oplevering SET wp_status=?, wp_link=?, status='gepubliceerd', besloten_door=?, besluit_ts=? WHERE id=?",
        (page.get("status", "publish"), page.get("link", ""), wie, _nu().isoformat(), oid))
    if r["taak_id"]:
        conn.execute("UPDATE taak SET fase='gepubliceerd', runner='', bijgewerkt=? WHERE id=?",
                     (_nu().isoformat(), r["taak_id"]))
    gezet = page.get("meta", {}) or {}
    handmatig = []
    if (r["seo_titel"] or "").strip() and not gezet.get("_yoast_wpseo_title"):
        handmatig.append({"veld": "SEO-titel", "waarde": r["seo_titel"]})
    if (r["seo_desc"] or "").strip() and not gezet.get("_yoast_wpseo_metadesc"):
        handmatig.append({"veld": "Meta-omschrijving", "waarde": r["seo_desc"]})
    conn.commit(); conn.close()
    return jsonify({"ok": True, "link": page.get("link", ""), "handmatig": handmatig})


# ---------------------------------------------------------------------------
# Takenwachtrij: de ruggengraat die de server-side runner pollt.
# Fases: nieuw -> onderzoek -> blueprint_review -> schrijven -> qc -> review -> gepubliceerd
# De runner pakt 'nieuw' (doet onderzoek) en 'schrijven' (schrijft + qc).
# ---------------------------------------------------------------------------
TAAK_FASEN = ["nieuw", "onderzoek", "blueprint_review", "schrijven", "qc", "review", "gepubliceerd"]
TAAK_RUNBAAR = ("nieuw", "schrijven")


@app.route("/taken")
def taken():
    conn = db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM taak ORDER BY aangemaakt DESC")]
    gem = _gem_duur_min(conn)
    for t in rows:
        t["bijlagen"] = [dict(b) for b in conn.execute(
            "SELECT id, bestandsnaam, bytes FROM bijlage WHERE taak_id=?", (t["id"],))]
        t["bezig_min"] = _verstreken_min(t["aangemaakt"]) if t["runner"] == "bezig" else None
    conn.close()
    return render_template("taken.html", taken=rows, merken=MERKEN,
                           types=sorted(BIJLAGE_TYPES), gem_duur=gem)


@app.route("/bijlage/<int:bid>")
def bijlage(bid):
    """Bekijk/download een bijlage (achter de SSO)."""
    conn = db()
    r = conn.execute("SELECT * FROM bijlage WHERE id=?", (bid,)).fetchone()
    conn.close()
    if not r or not os.path.exists(r["pad"]):
        abort(404)
    return send_file(r["pad"], download_name=r["bestandsnaam"])


@app.route("/api/taak/<int:tid>/bijlagen")
def api_bijlagen(tid):
    """De runner haalt de bijlagen van een opdracht op (paden + soort)."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    conn = db()
    rows = conn.execute("SELECT * FROM bijlage WHERE taak_id=?", (tid,)).fetchall()
    conn.close()
    return jsonify({"bijlagen": [
        {"id": r["id"], "bestandsnaam": r["bestandsnaam"], "pad": r["pad"],
         "bytes": r["bytes"], "mime": r["mime"],
         "beeld": os.path.splitext(r["bestandsnaam"])[1].lower() in BIJLAGE_BEELD}
        for r in rows]})


@app.route("/taak", methods=["POST"])
def taak_nieuw():
    """Vrije opdracht: je typt wat je wil, de agents bepalen zelf de aanpak.
    Firma is optioneel maar helpt (de governance werkt met één firma-context)."""
    d = request.form if request.form else (request.get_json(silent=True) or {})
    opdracht = (d.get("opdracht") or "").strip()[:4000]
    if not opdracht:
        if request.form:
            return redirect("/taken")
        return jsonify({"ok": False, "fout": "opdracht is verplicht"}), 400
    wie = request.headers.get("X-authentik-username", "onbekend")[:120]
    conn = db()
    cur = conn.execute(
        """INSERT INTO taak (firma, opdracht, regio, fase, aangemaakt, aangemaakt_door)
           VALUES (?,?,?, 'nieuw', ?, ?)""",
        ((d.get("firma") or "").strip()[:80], opdracht,
         (d.get("regio") or "Vlaanderen")[:60], _nu().isoformat(), wie))
    tid = cur.lastrowid
    # Bijlagen (documenten/afbeeldingen) bij deze opdracht.
    os.makedirs(BIJLAGE_MAP, exist_ok=True)
    for best in request.files.getlist("bijlagen"):
        if not best or not best.filename:
            continue
        naam = os.path.basename(best.filename)[:200]
        if os.path.splitext(naam)[1].lower() not in BIJLAGE_TYPES:
            continue
        pad = os.path.join(BIJLAGE_MAP, f"{tid}-{len(naam)}-{naam}")
        best.save(pad)
        grootte = os.path.getsize(pad)
        if grootte > MAX_BYTES:
            os.remove(pad)
            continue
        conn.execute(
            """INSERT INTO bijlage (taak_id, bestandsnaam, pad, bytes, mime, aangeleverd)
               VALUES (?,?,?,?,?,?)""",
            (tid, naam, pad, grootte, best.mimetype or "", _nu().isoformat()))
    conn.commit(); conn.close()
    if request.form:
        return redirect("/taken")
    return jsonify({"ok": True, "id": tid})


VASTGELOPEN_MIN = 20   # een claim die zo lang 'bezig' staat, is vastgelopen


@app.route("/api/taak-wacht")
def taak_wacht():
    """De runner claimt de volgende te-doen taken (atomair: '' -> 'bezig').
    Claims die te lang blijven hangen (crash/timeout) worden weer vrijgegeven."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    conn = db()
    grens = (_nu() - timedelta(minutes=VASTGELOPEN_MIN)).isoformat()
    conn.execute("UPDATE taak SET runner='' WHERE runner='bezig' AND COALESCE(bijgewerkt,'') < ?",
                 (grens,))
    conn.commit()
    rows = conn.execute(
        "SELECT * FROM taak WHERE fase IN ('nieuw','schrijven') AND (runner IS NULL OR runner='')"
    ).fetchall()
    geclaimd = []
    for r in rows:
        cur = conn.execute(
            "UPDATE taak SET runner='bezig', bijgewerkt=? WHERE id=? AND (runner IS NULL OR runner='')",
            (_nu().isoformat(), r["id"]))
        if cur.rowcount:
            geclaimd.append({"id": r["id"], "firma": r["firma"], "thema": r["thema"],
                             "opdracht": r["opdracht"] or "", "soort": r["soort"] or "",
                             "aanvulling": r["aanvulling"] or "",
                             "paginatype": r["paginatype"], "doel": r["doel"],
                             "regio": r["regio"], "fase": r["fase"],
                             "oplevering_id": r["oplevering_id"],
                             "vorige": (conn.execute(
                                 "SELECT inhoud FROM oplevering WHERE taak_id=? ORDER BY id DESC LIMIT 1",
                                 (r["id"],)).fetchone() or {"inhoud": ""})["inhoud"] or ""})
    conn.commit(); conn.close()
    return jsonify({"taken": geclaimd})


@app.route("/taak/<int:tid>/rapport", methods=["POST"])
def taak_rapport(tid):
    """De runner meldt het resultaat: nieuwe fase + eventueel de oplevering-id."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    d = request.get_json(silent=True) or {}
    fase = str(d.get("fase", "")).strip()
    if fase not in TAAK_FASEN:
        abort(400)
    conn = db()
    conn.execute(
        "UPDATE taak SET fase=?, runner='', oplevering_id=COALESCE(?, oplevering_id), bijgewerkt=? WHERE id=?",
        (fase, d.get("oplevering_id"), _nu().isoformat(), tid))
    conn.commit(); conn.close()
    return jsonify({"ok": True})


MERKEN = [
    {"naam": 'H-Architects', "sector": 'Architectuur', "web": 'https://h-architects.be', "typo": 'Systeem-sans (mies-thema)', "bron": 'screenshot + logo (100% zwart-wit) + theme-CSS',
     "kleuren": [{"hex": "#171617", "rol": "Antraciet-zwart — primair (logo, koppen)"}, {"hex": "#555659", "rol": "Grijs — secundair"}, {"hex": "#ffffff", "rol": "Wit — basis"}],
     "pos": 'Betaalbaar (ver)bouwen: nieuwbouw, renovatie, interieur, regularisatie, aankoopbegeleiding.',
     "tone": "Toegankelijk, geruststellend, budgetbewust: 'Een fijne babbel over je verwachtingen'.",
     "look": 'Strikt monochroom; geen enkel kleuraccent. Architectuurbeeld draagt de pagina.'},
    {"naam": 'HDS-India', "sector": 'Architectuur / 3D-design', "web": 'https://highdesignstudio.in', "typo": 'onbekend', "bron": 'LAGE ZEKERHEID — site offline (404/parkeerpagina); logo via webarchief',
     "kleuren": [{"hex": "#000000", "rol": "Zwart — logo"}, {"hex": "#ffffff", "rol": "Wit — basis"}],
     "pos": 'Ontwerp en uitvoering; branch van het Belgische H-Architects.',
     "tone": 'Niet te bevestigen op de huidige site.',
     "look": 'SITE OFFLINE: certificaat op naam van one.com, root geeft 404. Herdoen zodra de site werkt.'},
    {"naam": 'HDS-Suriname', "sector": 'Architectuur / 3D-design', "web": 'https://www.hdssr.com', "typo": 'onbekend (Squarespace verbergt fontnamen)', "bron": 'screenshot + logo (pixelcontrole: 100% zwart-wit)',
     "kleuren": [{"hex": "#000000", "rol": "Zwart — primair (logo, koppen, navigatie)"}, {"hex": "#ffffff", "rol": "Wit — basis"}],
     "pos": 'Architectuur van concept tot realisatie, 3D-scanning, energie-neutrale bouw (Paramaribo/Lelydorp).',
     "tone": "Inspirerend, mensgericht, duurzaam: 'Navigating dreams, building reality'.",
     "look": 'Strikt zwart-wit, veel witruimte; fotografie en 3D-renders dragen de identiteit.'},
    {"naam": 'UnaBo', "sector": 'Bouw — coördinatieplatform', "web": 'https://unabo.be', "typo": 'Open Sans', "bron": 'screenshot + drievoudige pixelsampling van de CTA-knoppen',
     "kleuren": [{"hex": "#7272ff", "rol": "Paars/indigo — primair (CTA-knoppen, kopjes)"}, {"hex": "#000000", "rol": "Zwart — logo/woordmerk, navigatie"}, {"hex": "#1a1a1a", "rol": "Bijna-zwart — lopende tekst"}, {"hex": "#ffffff", "rol": "Wit — basis"}],
     "pos": 'Alle bouwdiensten onder één dak: EPB/EPC/ventilatie, 3D-scanning, vergunningen, stabiliteitsstudies.',
     "tone": "Professioneel maar toegankelijk: 'één aanspreekpunt, één scherpe offerte'.",
     "look": 'Paars als handelsmerk op wit met zwarte typografie. Hero-illustratie bevat extra decoratieve tinten — geen merkkleur.'},
    {"naam": 'Corenbo', "sector": 'Bouw — expertsplatform', "web": 'https://corenbo.be', "typo": 'Sans (visuele inschatting)', "bron": 'GECORRIGEERD: screenshot + logo-pixelsampling (eerder aardepalet was ongebruikt WP-thema)',
     "kleuren": [{"hex": "#c91821", "rol": "Rood — primair merkkleur (logo 'c&b CORENBO')"}, {"hex": "#111111", "rol": "Zwart/antraciet — secundair (knoppen, navigatie, koppen)"}, {"hex": "#f9f9f9", "rol": "Gebroken wit — basis"}],
     "pos": 'Erkende bouwexperts: veiligheidscoördinatie, EPC/energieprestatie, renovatiecoaching, bouwcoördinatie.',
     "tone": "Zakelijk-professioneel, vertrouwen: 'Samen sterk in bouwexpertise'.",
     "look": 'Rood logo-accent op zwart-wit basis. LET OP: het eerder vermelde aardepalet (terracotta/zand/salie) bestaat niet.'},
    {"naam": 'Contrax', "sector": 'Back-office voor de bouw', "web": 'https://www.contrax.be', "typo": 'Sora', "bron": 'screenshot + logo (monochroom) + gecontroleerde Elementor-variabelen',
     "kleuren": [{"hex": "#5479f7", "rol": "Blauw — primair (nav-links, knoppen)"}, {"hex": "#21232a", "rol": "Bijna-zwart — tekst en woordmerk"}, {"hex": "#5d5f64", "rol": "Grijs — secundaire tekst"}, {"hex": "#f9faf8", "rol": "Gebroken wit — basis"}, {"hex": "#ffffff", "rol": "Wit — kaarten/formulieren"}],
     "pos": 'Administratieve ondersteuning voor bouwondernemers: leadgeneratie, offertes, agenda- en telefoniebeheer.',
     "tone": "Praktisch, ondernemend, oplossingsgericht: 'time is money', 'no cure, no pay'.",
     "look": 'Minimalistisch, veel witruimte, blauw accent. (#65b8d8 bleek een ongebruikte swatch en is geschrapt.)'},
    {"naam": 'Energie Efficiënt', "sector": 'Energie / EPB-support', "web": 'https://energie-efficient.be', "typo": 'Poppins', "bron": 'logo visueel bevestigd + pixelanalyse volledige pagina (geel: 0% aanwezig)',
     "kleuren": [{"hex": "#43b191", "rol": "Groen — primair (logo-cirkel, blaadjes, infoblok)"}, {"hex": "#3eb08f", "rol": "Logogroen — gemeten in het logobestand"}, {"hex": "#111111", "rol": "Zwart — woordmerk 'Energie' + bliksemschicht"}, {"hex": "#737373", "rol": "Grijs — woordmerk 'Efficiënt'"}, {"hex": "#ffffff", "rol": "Wit — basis"}],
     "pos": 'Ondersteuning voor EPB- en ventilatieverslaggevers: EPB-studies, ventilatieverslagen, tekenwerk, warmteverliesberekeningen.',
     "tone": "Zakelijk maar toegankelijk, klantgericht: 'Wij nemen de tijdrovende taken voor onze rekening'.",
     "look": 'Groen handelsmerk, zwart/grijs woordmerk, hexagon-vormtaal. Geen rood en geen geel in de huisstijl.'},
    {"naam": 'Harmoniebouw', "sector": 'Bouw — ruwbouwaannemer', "web": 'https://www.harmoniebouw.be', "typo": 'Karla / Open Sans (Enfold)', "bron": 'live CSS-variabele --enfold-main-color-primary + logo-sampling',
     "kleuren": [{"hex": "#c3512f", "rol": "Terracotta-roest — primair accent ('BOUW' in het logo)"}, {"hex": "#111111", "rol": "Zwart — woordmerk 'Harmonie', koppen"}, {"hex": "#515151", "rol": "Grijs — bodytekst en knoppen"}, {"hex": "#ffffff", "rol": "Wit — basis"}],
     "pos": 'Ruwbouwaannemer (afbraak, steunbalken, ramen/deuren) voor renovatie, aanbouw en nieuwbouw; regio Leuven.',
     "tone": "INFORMEEL ('je'), benaderbaar en betrouwbaar: 'partner in jouw ruwbouwproject'.",
     "look": 'Wit met zwart woordmerk en gedempte terracotta-roest als accent; natuurlijke projectfotografie.'},
    {"naam": 'TKN-Buro', "sector": 'Ingenieurs- / tekenbureau stabiliteit', "web": 'https://www.tkn-buro.be', "typo": 'Geometrisch sans', "bron": 'screenshot + logo-kleurentelling (logo is 100% monochroom)',
     "kleuren": [{"hex": "#cea718", "rol": "Goud/oker — primair accent (CTA-knop, infoblok)"}, {"hex": "#000000", "rol": "Zwart — logo (monochroom)"}, {"hex": "#5f8eb1", "rol": "Staalblauw — hero-verloop"}, {"hex": "#c9d4ea", "rol": "Lichtblauw — hero-verloop"}, {"hex": "#ffffff", "rol": "Wit — basis"}],
     "pos": 'Tekenbureau stabiliteit: bekistings-, wapenings- en funderingsplannen voor ingenieurs/architecten.',
     "tone": "INFORMEEL ('je/jouw'), direct en specialistisch: 'we doen één ding en doen het goed'.",
     "look": 'Goud/oker accent op zwart-wit, met een blauw hero-verloop. (De eerder vermelde bruintinten bestaan niet.)'},
    {"naam": 'Elevait NV', "sector": 'AI / administratie-automatisering (SR)', "web": 'https://elevaitnv.com', "typo": 'Inter', "bron": 'CSS-variabelen, elk apart bevestigd via pixel-sampling',
     "kleuren": [{"hex": "#059669", "rol": "Groen — accent ('AI' in het logo, knoppen)"}, {"hex": "#e7f4ef", "rol": "Lichtgroen — vlakken/hover"}, {"hex": "#1c1b18", "rol": "Inktzwart — tekst en CTA-knop"}, {"hex": "#faf9f6", "rol": "Crème — basisachtergrond"}, {"hex": "#e6e3db", "rol": "Warm beige — scheidingslijnen"}, {"hex": "#6b6960", "rol": "Warm grijs — subtiele tekst"}],
     "pos": 'Automatiseert administratieve processen (facturatie, verwerking) voor bedrijven en overheden in Suriname met AI.',
     "tone": "Formeel 'u', zelfverzekerd: 'Administratie die zichzelf doet'.",
     "look": 'Crème/beige basis met groen accent; clean, moderne en doelbewuste UI.'},
]


# ---------------------------------------------------------------------------
# Aanvragen vanaf onze eigen websites. Deze route is publiek bereikbaar (een
# bezoeker heeft geen login), maar accepteert alleen een kleine, vaste body en
# houdt eenvoudige spam tegen. De aanvragen komen binnen op het platform.
# ---------------------------------------------------------------------------

@app.route("/website-aanvraag", methods=["POST", "OPTIONS"])
def website_aanvraag():
    if request.method == "OPTIONS":
        return ("", 204)
    d = request.form if request.form else (request.get_json(silent=True) or {})
    # honeypot: een verborgen veld dat mensen niet invullen, bots wel
    if (d.get("website") or "").strip():
        return jsonify({"ok": True})          # stil negeren
    naam = (d.get("naam") or "").strip()[:120]
    email = (d.get("email") or "").strip()[:160]
    bericht = (d.get("bericht") or "").strip()[:4000]
    if not naam or not (email or (d.get("telefoon") or "").strip()):
        return jsonify({"ok": False, "fout": "naam en een contactgegeven zijn verplicht"}), 400
    conn = db()
    cur = conn.execute(
        """INSERT INTO lead (site, naam, email, telefoon, bericht, extra, herkomst, ontvangen)
           VALUES (?,?,?,?,?,?,?,?)""",
        ((d.get("site") or "")[:80], naam, email, (d.get("telefoon") or "").strip()[:60],
         bericht, json.dumps({k: str(v)[:200] for k, v in d.items()
                              if k not in ("naam", "email", "telefoon", "bericht", "site", "website")})[:2000],
         (request.headers.get("Referer") or "")[:200], _nu().isoformat()))
    lead_id = cur.lastrowid
    geweigerd = _bewaar_aanvraag_bijlagen(conn, lead_id)
    conn.commit(); conn.close()
    return jsonify({"ok": True, "geweigerd": geweigerd} if geweigerd else {"ok": True})


def _bewaar_aanvraag_bijlagen(conn, lead_id):
    """Slaat de meegestuurde foto's en plannen op. Geeft de geweigerde namen terug.

    De bezoeker is onbekend, dus we vertrouwen niets uit het verzoek:
      - de bestandsnaam wordt nooit gebruikt om het pad te bouwen; op schijf komt
        een naam die wij zelf verzinnen, zodat paden niet gemanipuleerd kunnen worden
      - alleen de extensies uit LEAD_BIJLAGE_TYPES komen erdoor
      - de grootte wordt gecontroleerd nadat het bestand is weggeschreven, en te
        grote bestanden worden meteen verwijderd
    Een geweigerd bestand laat de aanvraag zelf gewoon doorgaan: liever een aanvraag
    zonder bijlage dan een bezoeker die afhaakt op een foutmelding.
    """
    bestanden = request.files.getlist("bijlagen")[:LEAD_MAX_BESTANDEN]
    if not bestanden:
        return []
    os.makedirs(LEAD_BIJLAGE_MAP, exist_ok=True)
    geweigerd = []
    for i, best in enumerate(bestanden):
        if not best or not best.filename:
            continue
        toon_naam = os.path.basename(best.filename)[:150]
        ext = os.path.splitext(toon_naam)[1].lower()
        if ext not in LEAD_BIJLAGE_TYPES:
            geweigerd.append(toon_naam)
            continue
        pad = os.path.join(LEAD_BIJLAGE_MAP, f"{lead_id}-{i}{ext}")
        best.save(pad)
        grootte = os.path.getsize(pad)
        if grootte == 0 or grootte > LEAD_MAX_BYTES:
            os.remove(pad)
            geweigerd.append(toon_naam)
            continue
        conn.execute(
            """INSERT INTO lead_bijlage (lead_id, bestandsnaam, pad, bytes, mime, aangeleverd)
               VALUES (?,?,?,?,?,?)""",
            (lead_id, toon_naam, pad, grootte, (best.mimetype or "")[:100], _nu().isoformat()))
    return geweigerd


@app.route("/aanvraag-bijlage/<int:bid>")
def aanvraag_bijlage(bid):
    """Bijlage bij een aanvraag downloaden (achter de SSO).

    Altijd als download en nooit inline: het bestand komt van een onbekende
    bezoeker, en iets wat de browser zelf rendert op ons portaaldomein willen we
    niet. Daarom as_attachment plus een neutraal mimetype.
    """
    conn = db()
    r = conn.execute("SELECT * FROM lead_bijlage WHERE id=?", (bid,)).fetchone()
    conn.close()
    if not r or not os.path.exists(r["pad"]):
        abort(404)
    resp = send_file(r["pad"], as_attachment=True, download_name=r["bestandsnaam"],
                     mimetype="application/octet-stream")
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return resp


@app.route("/aanvragen")
def aanvragen():
    conn = db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM lead ORDER BY id DESC LIMIT 200")]
    bijlagen = {}
    for b in conn.execute("SELECT * FROM lead_bijlage ORDER BY id"):
        bijlagen.setdefault(b["lead_id"], []).append(dict(b))
    conn.close()
    for r in rows:
        r["ontvangen_kort"] = _fmt(r["ontvangen"])
        r["bijlagen"] = bijlagen.get(r["id"], [])
    return render_template("aanvragen.html", leads=rows,
                           nieuw=sum(1 for r in rows if r["status"] == "nieuw"))


@app.route("/aanvraag/<int:lid>/status", methods=["POST"])
def aanvraag_status(lid):
    d = request.form if request.form else (request.get_json(silent=True) or {})
    st = (d.get("status") or "").strip()
    if st not in ("nieuw", "opgevolgd", "afgehandeld", "spam"):
        abort(400)
    conn = db()
    conn.execute("UPDATE lead SET status=?, opmerking=? WHERE id=?",
                 (st, (d.get("opmerking") or "")[:1000], lid))
    conn.commit(); conn.close()
    return redirect("/aanvragen") if request.form else jsonify({"ok": True})


@app.route("/branding")
def branding():
    return render_template("branding.html", merken=MERKEN)




def _verstreken_min(iso):
    try:
        return int((_nu() - datetime.fromisoformat(iso)).total_seconds() // 60)
    except Exception:
        return None


def _gem_duur_min(conn):
    """Gemiddelde doorlooptijd van eerder afgeronde opdrachten (nieuw -> review)."""
    rows = conn.execute(
        "SELECT aangemaakt, bijgewerkt FROM taak WHERE fase IN ('review','blueprint_review','gepubliceerd') "
        "AND bijgewerkt != '' ORDER BY id DESC LIMIT 10").fetchall()
    duren = []
    for r in rows:
        try:
            d = (datetime.fromisoformat(r["bijgewerkt"]) - datetime.fromisoformat(r["aangemaakt"])).total_seconds() / 60
            if 0 < d < 240:
                duren.append(d)
        except Exception:
            pass
    return int(sum(duren) / len(duren)) if duren else None




@app.route("/oplevering/<int:oid>/aanvullen", methods=["POST"])
def oplevering_aanvullen(oid):
    """Je beantwoordt een vraag van het team of geeft extra info. De opdracht
    gaat terug in de wachtrij; het team bouwt voort op het vorige resultaat."""
    conn = db()
    r = conn.execute("SELECT taak_id FROM oplevering WHERE id=?", (oid,)).fetchone()
    if not r or not r["taak_id"]:
        conn.close()
        return jsonify({"ok": False, "fout": "Deze oplevering hoort niet bij een opdracht."}), 400
    tekst = (request.form.get("aanvulling") or
             (request.get_json(silent=True) or {}).get("aanvulling") or "").strip()[:8000]
    if not tekst and not request.files.getlist("bijlagen"):
        conn.close()
        return redirect(f"/oplevering/{oid}") if request.form else (
            jsonify({"ok": False, "fout": "geen aanvulling"}), 400)
    tid = r["taak_id"]
    os.makedirs(BIJLAGE_MAP, exist_ok=True)
    for best in request.files.getlist("bijlagen"):
        if not best or not best.filename:
            continue
        naam = os.path.basename(best.filename)[:200]
        if os.path.splitext(naam)[1].lower() not in BIJLAGE_TYPES:
            continue
        pad = os.path.join(BIJLAGE_MAP, f"{tid}-a{len(naam)}-{naam}")
        best.save(pad)
        if os.path.getsize(pad) > MAX_BYTES:
            os.remove(pad); continue
        conn.execute("""INSERT INTO bijlage (taak_id, bestandsnaam, pad, bytes, mime, aangeleverd)
                        VALUES (?,?,?,?,?,?)""",
                     (tid, naam, pad, os.path.getsize(pad), best.mimetype or "", _nu().isoformat()))
    conn.execute("UPDATE taak SET aanvulling=?, fase='nieuw', runner='', bijgewerkt=? WHERE id=?",
                 (tekst, _nu().isoformat(), tid))
    conn.execute("UPDATE oplevering SET status='wijziging_gevraagd', opmerking=? WHERE id=?",
                 (tekst[:2000], oid))
    conn.commit(); conn.close()
    if request.form:
        return redirect("/taken")
    return jsonify({"ok": True})


@app.route("/taak/<int:tid>/verwijder", methods=["POST"])
def taak_verwijder(tid):
    """Verwijdert een opdracht met bijlagen en bijhorende opleveringen."""
    conn = db()
    for b in conn.execute("SELECT pad FROM bijlage WHERE taak_id=?", (tid,)).fetchall():
        try:
            os.remove(b["pad"])
        except OSError:
            pass
    conn.execute("DELETE FROM bijlage WHERE taak_id=?", (tid,))
    conn.execute("DELETE FROM oplevering WHERE taak_id=?", (tid,))
    conn.execute("DELETE FROM taak WHERE id=?", (tid,))
    conn.commit(); conn.close()
    if request.form:
        return redirect("/taken")
    return jsonify({"ok": True})


@app.route("/oplevering/<int:oid>/verwijder", methods=["POST"])
def oplevering_verwijder(oid):
    """Verwijdert een oplevering (het WordPress-concept blijft staan)."""
    conn = db()
    conn.execute("DELETE FROM oplevering WHERE id=?", (oid,))
    conn.commit(); conn.close()
    if request.form:
        return redirect("/opleveringen")
    return jsonify({"ok": True})


@app.route("/api/oplevering/<int:oid>")
def api_oplevering(oid):
    """De runner leest een oplevering (bv. de goedgekeurde blueprint)."""
    if not TOKEN or request.headers.get("X-Agents-Token", "") != TOKEN:
        abort(403)
    conn = db()
    r = conn.execute("SELECT * FROM oplevering WHERE id=?", (oid,)).fetchone()
    conn.close()
    if not r:
        abort(404)
    return jsonify(dict(r))

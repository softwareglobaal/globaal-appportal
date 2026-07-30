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
from datetime import datetime, timezone

import markdown

from flask import (Flask, render_template, request, jsonify, abort,
                   redirect, send_file)

app = Flask(__name__)

DB = os.environ.get("AGENTS_DB", "/data/agents.db")
TOKEN = os.environ.get("AGENTS_TOKEN", "").strip()
BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "localhost")

STATUSSEN = ("rust", "waakt", "actief", "klaar", "fout")

TEAM = [
    {"naam": "onderhoud", "label": "Onderhoudsagent", "type": "onderhoud",
     "rol": "waakt over de VM en de apps"},
    {"naam": "elevait-hr", "label": "HR-agent (Elevait)", "type": "elevait",
     "rol": "toetst sollicitaties aan de criteria"},
    {"naam": "elevait-finance", "label": "Finance-agent (Elevait)",
     "type": "elevait", "rol": "bewaakt het uitgavenregister"},
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
        "mag": ["Een scorekaart en conceptbrieven klaarzetten"],
        "grenzen": [
            "Beslist nooit over een mens; alle uitvoer is advies",
            "Verstuurt nooit zelf een bericht naar een kandidaat",
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
            "Bewust geen mailgereedschap: versturen kan technisch niet",
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
MAX_BYTES = 60 * 1024 * 1024


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
    {"naam": "seo-onderzoek", "label": "Onderzoek", "bijnaam": "De Verkenner",
     "team": "SEO", "rol": "live SEO-onderzoek → blueprint"},
    {"naam": "seo-schrijver", "label": "Schrijver", "bijnaam": "De Pen",
     "team": "SEO", "rol": "schrijft de pagina vanaf de blueprint"},
    {"naam": "seo-qc", "label": "Controle", "bijnaam": "De Keurmeester",
     "team": "SEO", "rol": "onafhankelijke kwaliteitscontrole"},
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
            "wp_link": r["wp_link"], "wp_preview": r["wp_preview"]}


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
    return {"nav_te_valideren": n,
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


@app.route("/oplevering/<int:oid>/besluit", methods=["POST"])
def oplevering_besluit(oid):
    d = request.get_json(silent=True) or {}
    besluit = str(d.get("besluit", "")).strip()
    if besluit not in ("goedgekeurd", "wijziging_gevraagd", "afgewezen", "gepubliceerd"):
        abort(400)
    wie = request.headers.get("X-authentik-username", "onbekend")[:120]
    opm = str(d.get("opmerking", ""))[:2000]
    conn = db()
    conn.execute(
        "UPDATE oplevering SET status=?, opmerking=?, besloten_door=?, besluit_ts=? WHERE id=?",
        (besluit, opm, wie, _nu().isoformat(), oid))
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
        """INSERT INTO oplevering (firma, thema, agent, soort, titel, inhoud, versie, status, aangemaakt)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (str(d.get("firma", ""))[:80], str(d.get("thema", ""))[:120],
         str(d.get("agent", ""))[:60], str(d.get("soort", ""))[:60], titel,
         str(d.get("inhoud", ""))[:200000], str(d.get("versie", "v1"))[:20],
         "in_review", _nu().isoformat()))
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
    link = page.get("link") or (page.get("guid", {}) or {}).get("raw", "")
    if not link:
        return ""
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
    payload = {"title": r["titel"], "content": html, "status": "draft"}
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
        (page.get("id"), page.get("status", "draft"), _wp_preview_url(page), page.get("link", ""), oid))
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
    try:
        page = _wp_call(conf, "POST", f"/pages/{r['wp_post_id']}", {"status": "publish"})
    except Exception:
        conn.close()
        return jsonify({"ok": False, "fout": "Publiceren mislukt."}), 502
    wie = request.headers.get("X-authentik-username", "onbekend")[:120]
    conn.execute(
        "UPDATE oplevering SET wp_status=?, wp_link=?, status='gepubliceerd', besloten_door=?, besluit_ts=? WHERE id=?",
        (page.get("status", "publish"), page.get("link", ""), wie, _nu().isoformat(), oid))
    conn.commit(); conn.close()
    return jsonify({"ok": True, "link": page.get("link", "")})

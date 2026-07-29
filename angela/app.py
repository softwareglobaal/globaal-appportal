#!/usr/bin/env python3
"""
Angela - werkdashboard voor het initiatief in Suriname.

Vangbak voor het hele initiatief: notities, links, bestanden, taken en
beslissingen, elk gekoppeld aan een werkstroom (merk, website, webshop,
inkoop, fiscaal, social, data).

Draait achter de forward-auth van de portal: geen eigen login, de gebruiker
komt binnen via de X-authentik-* headers. Data in schema `angela`
(migratie 097); bestanden op ANGELA_UPLOAD_DIR.
"""

import os
import re
import secrets
import unicodedata
from datetime import date, datetime
from functools import wraps

import psycopg
from psycopg.rows import dict_row

from flask import (
    Flask, request, redirect, url_for, render_template_string,
    send_from_directory, abort, flash, g,
)

# ---------------------------------------------------------------------------
# Configuratie
# ---------------------------------------------------------------------------
PORT = int(os.environ.get("PORT", "3016"))
UPLOAD_DIR = os.environ.get("ANGELA_UPLOAD_DIR", "/data/bijlagen")
TITEL = os.environ.get("ANGELA_TITEL") or "Angela"
ONDERTITEL = os.environ.get("ANGELA_ONDERTITEL") or "Initiatief Suriname"
MAX_UPLOAD_MB = int(os.environ.get("ANGELA_MAX_UPLOAD_MB", "50"))

# Authentik-groepen die mogen bewerken (leeg = iedereen die door forward-auth komt).
EDITOR_GROUPS = {s.strip() for s in os.environ.get("EDITOR_GROUPS", "").split(",") if s.strip()}

SOORTEN = ["notitie", "link", "bestand", "taak", "beslissing"]
SOORT_LABEL = {
    "notitie": "notitie",
    "link": "link",
    "bestand": "bestand",
    "taak": "taak",
    "beslissing": "beslissing",
}
STATUSSEN = ["open", "bezig", "klaar", "geparkeerd", "vervallen"]
AFBEELDING_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic"}

MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december"]

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def _dsn():
    url = os.environ.get("ANGELA_DB_URL", "")
    return url.replace("postgresql+psycopg://", "postgresql://").replace(
        "postgres+psycopg://", "postgresql://")


def db():
    if "db" not in g:
        g.db = psycopg.connect(_dsn(), row_factory=dict_row, autocommit=True,
                               options="-c search_path=angela,public")
        # De ingelogde mens meegeven, zodat de audit-trail een naam heeft.
        g.db.execute("SELECT set_config('app.gebruiker', %s, false)", (auth_gebruiker(),))
    return g.db


@app.teardown_appcontext
def _close_db(_exc):
    d = g.pop("db", None)
    if d is not None:
        d.close()


def haal(sql, params=()):
    return db().execute(sql, params).fetchall()


def haal_een(sql, params=()):
    rijen = haal(sql, params)
    return rijen[0] if rijen else None


def schrijf(sql, params=()):
    return db().execute(sql, params)


# ---------------------------------------------------------------------------
# Gebruiker uit de forward-auth
# ---------------------------------------------------------------------------
def auth_gebruiker():
    return (request.headers.get("X-authentik-username")
            or request.headers.get("X-authentik-name") or "onbekend")


def auth_groepen():
    ruw = request.headers.get("X-authentik-groups", "")
    return {p.strip() for sep in ("|", ",") for p in ruw.split(sep) if p.strip()}


def mag_bewerken():
    return not EDITOR_GROUPS or bool(EDITOR_GROUPS & auth_groepen())


def bewerk_route(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not mag_bewerken():
            abort(403)
        return f(*a, **kw)
    return wrapper


# ---------------------------------------------------------------------------
# Weergave
# ---------------------------------------------------------------------------
def datum_be(d):
    if d is None:
        return ""
    if isinstance(d, datetime):
        d = d.date()
    return f"{d.day} {MAANDEN[d.month - 1]} {d.year}"


def datumtijd_be(d):
    if d is None:
        return ""
    return f"{datum_be(d)}, {d:%H:%M}"


def getal_be(n):
    if n is None:
        return "0"
    return f"{int(n):,}".replace(",", ".")


def omvang_be(bytes_):
    if not bytes_:
        return ""
    mb = bytes_ / (1024 * 1024)
    if mb < 1:
        return f"{max(1, round(bytes_ / 1024))} kB"
    return f"{mb:.1f}".replace(".", ",") + " MB"


def kort(tekst, lengte=140):
    if not tekst:
        return ""
    tekst = " ".join(tekst.split())
    return tekst if len(tekst) <= lengte else tekst[:lengte].rstrip() + "..."


app.jinja_env.filters["datum_be"] = datum_be
app.jinja_env.filters["datumtijd_be"] = datumtijd_be
app.jinja_env.filters["getal_be"] = getal_be
app.jinja_env.filters["omvang_be"] = omvang_be
app.jinja_env.filters["kort"] = kort


def veilige_naam(naam):
    naam = unicodedata.normalize("NFKD", naam or "").encode("ascii", "ignore").decode()
    naam = re.sub(r"[^A-Za-z0-9._-]+", "-", naam).strip("-._")
    return naam[:120] or "bestand"


# ---------------------------------------------------------------------------
# Gedeelde queries
# ---------------------------------------------------------------------------
ITEM_SELECT = """
    SELECT i.*, w.sleutel AS werkstroom_sleutel, w.naam AS werkstroom_naam,
           b.naam AS verantwoordelijke_naam,
           (SELECT count(*) FROM angela.bijlage bj WHERE bj.item_id = i.id) AS bijlagen
      FROM angela.item i
      LEFT JOIN angela.werkstroom w ON w.id = i.werkstroom_id
      LEFT JOIN angela.betrokkene b ON b.id = i.verantwoordelijke_id
"""


def werkstromen(alleen_actief=True):
    sql = "SELECT * FROM angela.werkstroom"
    if alleen_actief:
        sql += " WHERE actief"
    return haal(sql + " ORDER BY volgorde, naam")


def betrokkenen(alleen_actief=True):
    sql = "SELECT * FROM angela.betrokkene"
    if alleen_actief:
        sql += " WHERE actief"
    return haal(sql + " ORDER BY naam")


def tellingen():
    rij = haal_een("""
        SELECT count(*)                                                        AS totaal,
               count(*) FILTER (WHERE soort = 'taak'
                                  AND status IN ('open','bezig'))              AS open_taken,
               count(*) FILTER (WHERE soort = 'taak' AND status IN ('open','bezig')
                                  AND deadline < current_date)                 AS te_laat,
               count(*) FILTER (WHERE soort = 'beslissing')                    AS beslissingen,
               count(*) FILTER (WHERE werkstroom_id IS NULL)                   AS zonder_werkstroom,
               count(*) FILTER (WHERE aangemaakt_op >= now() - interval '7 days') AS deze_week
          FROM angela.item
    """)
    bij = haal_een("SELECT count(*) AS n, coalesce(sum(grootte_bytes),0) AS bytes FROM angela.bijlage")
    rij = dict(rij)
    rij["bestanden"] = bij["n"]
    rij["bestanden_bytes"] = bij["bytes"]
    return rij


def per_werkstroom():
    return haal("""
        -- Let op: geen alias `items`; in Jinja botst dat met dict.items().
        SELECT w.id, w.sleutel, w.naam, w.omschrijving,
               count(i.id)                                                AS aantal,
               count(i.id) FILTER (WHERE i.soort = 'taak'
                                     AND i.status IN ('open','bezig'))    AS open_taken,
               count(i.id) FILTER (WHERE i.soort = 'beslissing')          AS beslissingen,
               max(i.aangemaakt_op)                                       AS laatste
          FROM angela.werkstroom w
          LEFT JOIN angela.item i ON i.werkstroom_id = w.id
         WHERE w.actief
      GROUP BY w.id, w.sleutel, w.naam, w.omschrijving, w.volgorde
      ORDER BY w.volgorde, w.naam
    """)


def zoek_items(args, limiet=None):
    """Views zijn queries: elke filter komt uit de querystring, niets opgeslagen."""
    where, params = [], []
    if args.get("soort") in SOORTEN:
        where.append("i.soort = %s")
        params.append(args["soort"])
    if args.get("werkstroom"):
        if args["werkstroom"] == "geen":
            where.append("i.werkstroom_id IS NULL")
        else:
            where.append("w.sleutel = %s")
            params.append(args["werkstroom"])
    if args.get("status") in STATUSSEN:
        where.append("i.status = %s")
        params.append(args["status"])
    if args.get("open") == "1":
        where.append("i.soort = 'taak' AND i.status IN ('open','bezig')")
    if args.get("telaat") == "1":
        where.append("i.soort = 'taak' AND i.status IN ('open','bezig') AND i.deadline < current_date")
    if args.get("verantwoordelijke"):
        where.append("b.naam = %s")
        params.append(args["verantwoordelijke"])
    if args.get("bijlagen") == "1":
        where.append("EXISTS (SELECT 1 FROM angela.bijlage bj WHERE bj.item_id = i.id)")
    if args.get("week") == "1":
        where.append("i.aangemaakt_op >= now() - interval '7 days'")
    if args.get("dag"):
        where.append("i.aangemaakt_op::date = %s")
        params.append(args["dag"])
    if args.get("q"):
        where.append("(i.titel ILIKE %s OR i.tekst ILIKE %s OR i.url ILIKE %s)")
        params += [f"%{args['q']}%"] * 3

    sql = ITEM_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY i.aangemaakt_op DESC, i.id DESC"
    if limiet:
        sql += f" LIMIT {int(limiet)}"
    return haal(sql, tuple(params))


def filter_omschrijving(args):
    """Leesbare samenvatting van de actieve filters, voor de lijstkop."""
    delen = []
    if args.get("soort") in SOORTEN:
        delen.append(SOORT_LABEL[args["soort"]] + "s")
    if args.get("open") == "1":
        delen.append("openstaande taken")
    if args.get("telaat") == "1":
        delen.append("taken over de deadline")
    if args.get("bijlagen") == "1":
        delen.append("met bijlage")
    if args.get("week") == "1":
        delen.append("van de afgelopen zeven dagen")
    if args.get("werkstroom") == "geen":
        delen.append("zonder werkstroom")
    elif args.get("werkstroom"):
        w = haal_een("SELECT naam FROM angela.werkstroom WHERE sleutel = %s", (args["werkstroom"],))
        if w:
            delen.append("werkstroom " + w["naam"])
    if args.get("verantwoordelijke"):
        delen.append("van " + args["verantwoordelijke"])
    if args.get("status") in STATUSSEN:
        delen.append("status " + args["status"])
    if args.get("dag"):
        delen.append("gedropt op " + datum_be(date.fromisoformat(args["dag"])))
    if args.get("q"):
        delen.append('zoekterm "' + args["q"] + '"')
    return ", ".join(delen) if delen else "alles"


# ---------------------------------------------------------------------------
# Opslaan
# ---------------------------------------------------------------------------
def _leeg_naar_none(v):
    v = (v or "").strip()
    return v or None


def bewaar_bijlagen(item_id, bestanden):
    aantal = 0
    map_ = os.path.join(UPLOAD_DIR, str(item_id))
    for f in bestanden:
        if not f or not f.filename:
            continue
        os.makedirs(map_, exist_ok=True)
        naam = veilige_naam(f.filename)
        pad = os.path.join(map_, f"{secrets.token_hex(4)}-{naam}")
        f.save(pad)
        mime = f.mimetype or ""
        schrijf("""
            INSERT INTO angela.bijlage
                   (item_id, bestandsnaam, pad, mimetype, grootte_bytes,
                    is_afbeelding, geupload_door)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (item_id, f.filename[:200], pad, mime, os.path.getsize(pad),
              mime in AFBEELDING_TYPES, auth_gebruiker()))
        aantal += 1
    return aantal


def velden_uit_formulier(form):
    soort = form.get("soort", "notitie")
    if soort not in SOORTEN:
        soort = "notitie"
    status = form.get("status", "open")
    if status not in STATUSSEN:
        status = "open"
    return dict(
        soort=soort,
        titel=(form.get("titel") or "").strip()[:300],
        tekst=_leeg_naar_none(form.get("tekst")),
        url=_leeg_naar_none(form.get("url")),
        werkstroom_id=int(form["werkstroom_id"]) if form.get("werkstroom_id") else None,
        verantwoordelijke_id=int(form["verantwoordelijke_id"]) if form.get("verantwoordelijke_id") else None,
        status=status,
        deadline=_leeg_naar_none(form.get("deadline")),
        besloten_op=_leeg_naar_none(form.get("besloten_op")),
        bron_soort=_leeg_naar_none(form.get("bron_soort")),
        bron_ref=_leeg_naar_none(form.get("bron_ref")),
        bron_titel=_leeg_naar_none(form.get("bron_titel")),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/healthz")
def healthz():
    return "ok"


@app.get("/")
def overzicht():
    tel = tellingen()
    stromen = per_werkstroom()
    recent = zoek_items({"week": "1"}, limiet=15)
    if not recent:
        recent = zoek_items({}, limiet=15)
    return pagina(render_template_string(
        OVERZICHT, tel=tel, stromen=stromen, recent=recent,
        werkstromen=werkstromen(), betrokkenen=betrokkenen(),
    ), titel="Overzicht")


@app.get("/items")
def items():
    args = request.args.to_dict()
    rijen = zoek_items(args)
    return pagina(render_template_string(
        LIJST, rijen=rijen, omschrijving=filter_omschrijving(args), args=args,
        werkstromen=werkstromen(), betrokkenen=betrokkenen(),
        totaal_alles=haal_een("SELECT count(*) AS n FROM angela.item")["n"],
    ), titel="Items")


@app.get("/taken")
def taken():
    open_taken = haal(ITEM_SELECT + """
         WHERE i.soort = 'taak' AND i.status IN ('open','bezig')
      ORDER BY i.deadline NULLS LAST, i.aangemaakt_op DESC
    """)
    afgerond = haal(ITEM_SELECT + """
         WHERE i.soort = 'taak' AND i.status NOT IN ('open','bezig')
      ORDER BY i.bijgewerkt_op DESC LIMIT 40
    """)
    per_persoon = haal("""
        SELECT coalesce(b.naam, 'niet toegewezen') AS naam,
               count(*)                            AS open_taken,
               count(*) FILTER (WHERE i.deadline < current_date) AS te_laat
          FROM angela.item i
          LEFT JOIN angela.betrokkene b ON b.id = i.verantwoordelijke_id
         WHERE i.soort = 'taak' AND i.status IN ('open','bezig')
      GROUP BY 1 ORDER BY 2 DESC, 1
    """)
    return pagina(render_template_string(
        TAKEN, open_taken=open_taken, afgerond=afgerond, per_persoon=per_persoon,
    ), titel="Taken")


@app.get("/beslissingen")
def beslissingen():
    rijen = haal(ITEM_SELECT + """
         WHERE i.soort = 'beslissing'
      ORDER BY coalesce(i.besloten_op, i.aangemaakt_op::date) DESC, i.id DESC
    """)
    return pagina(render_template_string(BESLISSINGEN, rijen=rijen), titel="Beslissingen")


@app.get("/bestanden")
def bestanden():
    rijen = haal("""
        SELECT bj.*, i.titel AS item_titel, i.soort AS item_soort,
               w.naam AS werkstroom_naam, w.sleutel AS werkstroom_sleutel
          FROM angela.bijlage bj
          JOIN angela.item i ON i.id = bj.item_id
          LEFT JOIN angela.werkstroom w ON w.id = i.werkstroom_id
      ORDER BY bj.geupload_op DESC
    """)
    return pagina(render_template_string(BESTANDEN, rijen=rijen), titel="Bestanden")


@app.get("/item/<int:iid>")
def item_detail(iid):
    rij = haal_een(ITEM_SELECT + " WHERE i.id = %s", (iid,))
    if not rij:
        abort(404)
    bijlagen = haal("SELECT * FROM angela.bijlage WHERE item_id = %s ORDER BY geupload_op", (iid,))
    verbanden = haal("""
        SELECT v.id, v.relatie, i.id AS ander_id, i.titel, i.soort
          FROM angela.verband v
          JOIN angela.item i ON i.id = v.naar_item_id
         WHERE v.van_item_id = %s
        UNION ALL
        SELECT v.id, v.relatie, i.id, i.titel, i.soort
          FROM angela.verband v
          JOIN angela.item i ON i.id = v.van_item_id
         WHERE v.naar_item_id = %s
    """, (iid, iid))
    andere = haal("SELECT id, titel, soort FROM angela.item WHERE id <> %s "
                  "ORDER BY aangemaakt_op DESC LIMIT 200", (iid,))
    return pagina(render_template_string(
        DETAIL, r=rij, bijlagen=bijlagen, verbanden=verbanden, andere=andere,
        werkstromen=werkstromen(), betrokkenen=betrokkenen(),
    ), titel=rij["titel"])


@app.post("/item")
@bewerk_route
def item_nieuw():
    v = velden_uit_formulier(request.form)
    if not v["titel"]:
        flash("Een item heeft een titel nodig.")
        return redirect(request.referrer or url_for("overzicht"))
    bestanden_in = request.files.getlist("bijlagen")
    # Wie alleen bestanden neerlegt en de soort laat staan, bedoelt "bestand".
    if v["soort"] == "notitie" and any(f and f.filename for f in bestanden_in):
        v["soort"] = "bestand"
    cur = schrijf("""
        INSERT INTO angela.item
               (soort, titel, tekst, url, werkstroom_id, verantwoordelijke_id,
                status, deadline, besloten_op, bron_soort, bron_ref, bron_titel,
                aangemaakt_door)
        VALUES (%(soort)s, %(titel)s, %(tekst)s, %(url)s, %(werkstroom_id)s,
                %(verantwoordelijke_id)s, %(status)s, %(deadline)s, %(besloten_op)s,
                %(bron_soort)s, %(bron_ref)s, %(bron_titel)s, %(door)s)
     RETURNING id
    """, {**v, "door": auth_gebruiker()})
    iid = cur.fetchone()["id"]
    n = bewaar_bijlagen(iid, bestanden_in)
    flash(f"Gedropt: {v['titel']}" + (f" ({n} bijlage(n))" if n else ""))
    return redirect(url_for("item_detail", iid=iid))


@app.post("/item/<int:iid>")
@bewerk_route
def item_bewerk(iid):
    v = velden_uit_formulier(request.form)
    if not v["titel"]:
        flash("Een item heeft een titel nodig.")
        return redirect(url_for("item_detail", iid=iid))
    schrijf("""
        UPDATE angela.item SET
               soort = %(soort)s, titel = %(titel)s, tekst = %(tekst)s, url = %(url)s,
               werkstroom_id = %(werkstroom_id)s,
               verantwoordelijke_id = %(verantwoordelijke_id)s,
               status = %(status)s, deadline = %(deadline)s, besloten_op = %(besloten_op)s,
               bron_soort = %(bron_soort)s, bron_ref = %(bron_ref)s,
               bron_titel = %(bron_titel)s, bijgewerkt_op = now()
         WHERE id = %(id)s
    """, {**v, "id": iid})
    bewaar_bijlagen(iid, request.files.getlist("bijlagen"))
    flash("Bijgewerkt.")
    return redirect(url_for("item_detail", iid=iid))


@app.post("/item/<int:iid>/status")
@bewerk_route
def item_status(iid):
    status = request.form.get("status")
    if status not in STATUSSEN:
        abort(400)
    schrijf("UPDATE angela.item SET status = %s, bijgewerkt_op = now() WHERE id = %s",
            (status, iid))
    return redirect(request.referrer or url_for("item_detail", iid=iid))


@app.post("/item/<int:iid>/verwijder")
@bewerk_route
def item_verwijder(iid):
    for b in haal("SELECT pad FROM angela.bijlage WHERE item_id = %s", (iid,)):
        try:
            os.remove(b["pad"])
        except OSError:
            pass
    schrijf("DELETE FROM angela.item WHERE id = %s", (iid,))
    flash("Item verwijderd.")
    return redirect(url_for("overzicht"))


@app.post("/item/<int:iid>/verband")
@bewerk_route
def verband_nieuw(iid):
    naar = request.form.get("naar_item_id")
    relatie = (request.form.get("relatie") or "hoort bij").strip()[:60]
    if naar and int(naar) != iid:
        schrijf("""
            INSERT INTO angela.verband (van_item_id, naar_item_id, relatie)
            VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
        """, (iid, int(naar), relatie))
    return redirect(url_for("item_detail", iid=iid))


@app.post("/verband/<int:vid>/verwijder")
@bewerk_route
def verband_verwijder(vid):
    schrijf("DELETE FROM angela.verband WHERE id = %s", (vid,))
    return redirect(request.referrer or url_for("overzicht"))


@app.get("/bijlage/<int:bid>")
def bijlage(bid):
    b = haal_een("SELECT * FROM angela.bijlage WHERE id = %s", (bid,))
    if not b:
        abort(404)
    map_, naam = os.path.split(b["pad"])
    return send_from_directory(map_, naam, download_name=b["bestandsnaam"],
                               as_attachment=request.args.get("download") == "1")


@app.post("/bijlage/<int:bid>/verwijder")
@bewerk_route
def bijlage_verwijder(bid):
    b = haal_een("SELECT * FROM angela.bijlage WHERE id = %s", (bid,))
    if not b:
        abort(404)
    try:
        os.remove(b["pad"])
    except OSError:
        pass
    schrijf("DELETE FROM angela.bijlage WHERE id = %s", (bid,))
    return redirect(url_for("item_detail", iid=b["item_id"]))


@app.post("/betrokkene")
@bewerk_route
def betrokkene_nieuw():
    naam = (request.form.get("naam") or "").strip()[:120]
    rol = _leeg_naar_none(request.form.get("rol"))
    if naam:
        schrijf("INSERT INTO angela.betrokkene (naam, rol) VALUES (%s, %s) "
                "ON CONFLICT (naam) DO NOTHING", (naam, rol))
    return redirect(request.referrer or url_for("overzicht"))


@app.errorhandler(413)
def te_groot(_e):
    return pagina(f"<p class='melding'>Dat bestand is te groot. De limiet is "
                  f"{MAX_UPLOAD_MB} MB per keer.</p>", titel="Te groot"), 413


# ---------------------------------------------------------------------------
# Weergave-laag
# ---------------------------------------------------------------------------
BASE = """
<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ titel }} - {{ app_titel }}</title>
<style>
 :root{--page:#f5f6f8;--vlak:#ffffff;--zacht:#eef0f4;--ink:#16181d;--mut:#5b626d;
   --lijn:#dfe3e9;--kop:#1b2436;--kop-ink:#f3f4f7;--kop-mut:#a9b1c2;
   --accent:#1f5fb5;--accent-zacht:#e7eefa;--groen:#0f7a45;--groen-zacht:#e5f3eb;
   --amber:#8a5d00;--amber-zacht:#fbf1dc;--rood:#b3261e;--rood-zacht:#fbe9e7}
 @media(prefers-color-scheme:dark){:root{--page:#0d1015;--vlak:#151920;--zacht:#1b212b;
   --ink:#e8eaef;--mut:#9aa3b1;--lijn:#28303c;--kop:#0a0d13;--kop-ink:#e8eaef;
   --kop-mut:#9aa3b1;--accent:#6ea3ef;--accent-zacht:#16243a;--groen:#4cc98a;
   --groen-zacht:#0f2a1d;--amber:#e0ad4b;--amber-zacht:#2b2211;--rood:#f0736a;
   --rood-zacht:#2c1614}}
 *{box-sizing:border-box}html,body{margin:0}
 body{background:var(--page);color:var(--ink);
   font:15px/1.55 system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}
 a{color:var(--accent);text-decoration:none}
 a:hover{text-decoration:underline}
 a:focus-visible,button:focus-visible,summary:focus-visible,input:focus-visible,
 select:focus-visible,textarea:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
 .wrap{max-width:1280px;margin:0 auto;padding:0 24px}
 @media(max-width:700px){.wrap{padding:0 14px}}
 header{background:var(--kop);color:var(--kop-ink)}
 header .wrap{display:flex;align-items:center;gap:20px;flex-wrap:wrap;padding-top:14px;padding-bottom:14px}
 header .naam{font-size:20px;font-weight:700;letter-spacing:-.01em;color:var(--kop-ink)}
 header .onder{font-size:12.5px;color:var(--kop-mut)}
 header .wie{margin-left:auto;font-size:12.5px;color:var(--kop-mut)}
 nav{background:var(--vlak);border-bottom:1px solid var(--lijn)}
 nav .wrap{display:flex;gap:2px;flex-wrap:wrap;align-items:center}
 nav a{color:var(--mut);font-weight:600;font-size:14px;padding:12px 14px;
   border-bottom:3px solid transparent}
 nav a:hover{color:var(--ink);text-decoration:none}
 nav a.actief{color:var(--ink);border-bottom-color:var(--accent)}
 nav form{margin-left:auto;display:flex;gap:6px;padding:7px 0}
 nav input{border:1px solid var(--lijn);background:var(--vlak);color:var(--ink);
   border-radius:6px;height:34px;padding:0 10px;font-size:14px;min-width:180px}
 main{padding:24px 0 60px}
 h1{font-size:23px;font-weight:700;margin:0 0 4px;letter-spacing:-.01em}
 h2{font-size:17px;font-weight:700;margin:0}
 .sub{color:var(--mut);margin:0 0 20px;font-size:14px}
 .melding{background:var(--accent-zacht);border:1px solid var(--lijn);
   border-radius:8px;padding:11px 14px;margin:0 0 18px;font-size:14px}
 .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
   gap:12px;margin:0 0 24px}
 .kpi{background:var(--vlak);border:1px solid var(--lijn);border-radius:9px;padding:14px 16px;display:block}
 .kpi:hover{border-color:var(--accent);text-decoration:none}
 .kpi .cijfer{font-size:30px;font-weight:700;letter-spacing:-.02em;line-height:1.1;color:var(--ink)}
 .kpi:hover .cijfer{color:var(--accent)}
 .kpi .lbl{font-size:13px;color:var(--mut);margin-top:2px}
 .kpi.waarschuwing .cijfer{color:var(--rood)}
 .vak{background:var(--vlak);border:1px solid var(--lijn);border-radius:9px;margin:0 0 14px}
 .vak>summary{list-style:none;cursor:pointer;padding:13px 16px;display:flex;
   align-items:baseline;gap:12px;flex-wrap:wrap}
 .vak>summary::-webkit-details-marker{display:none}
 .vak>summary::before{content:"+";font-weight:700;color:var(--mut);width:12px}
 .vak[open]>summary::before{content:"-"}
 .vak>summary h2{flex:none}
 .vak .tellers{color:var(--mut);font-size:13.5px;display:flex;gap:14px;flex-wrap:wrap}
 .vak .tellers b{color:var(--ink)}
 .vak .inhoud{padding:0 16px 16px;border-top:1px solid var(--lijn)}
 .vak .inhoud>p:first-child{margin-top:14px}
 table{width:100%;border-collapse:collapse;font-size:14px}
 .tabelkader{overflow-x:auto}
 th{text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.04em;
   color:var(--mut);font-weight:700;padding:10px 10px 8px;border-bottom:1px solid var(--lijn);white-space:nowrap}
 td{padding:9px 10px;border-bottom:1px solid var(--lijn);vertical-align:top}
 tr:last-child td{border-bottom:0}
 td.nowrap,th.nowrap{white-space:nowrap}
 .plat{color:var(--mut)}
 .merk{display:inline-block;font-size:11.5px;font-weight:700;padding:2px 8px;
   border-radius:20px;background:var(--zacht);color:var(--mut);white-space:nowrap}
 .merk.notitie{background:var(--zacht);color:var(--mut)}
 .merk.link{background:var(--accent-zacht);color:var(--accent)}
 .merk.bestand{background:var(--accent-zacht);color:var(--accent)}
 .merk.taak{background:var(--amber-zacht);color:var(--amber)}
 .merk.beslissing{background:var(--groen-zacht);color:var(--groen)}
 .st{font-size:12.5px;font-weight:600}
 .st.open{color:var(--amber)}.st.bezig{color:var(--accent)}
 .st.klaar{color:var(--groen)}.st.geparkeerd,.st.vervallen{color:var(--mut)}
 .telaat{color:var(--rood);font-weight:600}
 form.blok{display:grid;gap:12px}
 .velden{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
 label{display:block;font-size:12.5px;color:var(--mut);font-weight:600;margin-bottom:4px}
 input[type=text],input[type=url],input[type=date],select,textarea{
   width:100%;border:1px solid var(--lijn);background:var(--vlak);color:var(--ink);
   border-radius:6px;padding:8px 10px;font:inherit;font-size:14px}
 textarea{min-height:88px;resize:vertical}
 input[type=file]{font-size:13.5px;color:var(--mut)}
 .knop{display:inline-block;border:0;background:var(--accent);color:#fff;font-weight:700;
   font-size:14px;padding:9px 18px;border-radius:6px;cursor:pointer}
 .knop:hover{filter:brightness(1.08);text-decoration:none}
 .knop.stil{background:var(--zacht);color:var(--ink)}
 .knop.gevaar{background:var(--rood-zacht);color:var(--rood)}
 .rijknoppen{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
 .fotos{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
 .fotos figure{margin:0;border:1px solid var(--lijn);border-radius:8px;overflow:hidden;background:var(--zacht)}
 .fotos img{width:100%;height:130px;object-fit:cover;display:block}
 .fotos figcaption{padding:7px 9px;font-size:12px;color:var(--mut);word-break:break-word}
 .leeg{color:var(--mut);font-size:14px;padding:16px 0}
 dl.kv{display:grid;grid-template-columns:auto 1fr;gap:6px 18px;margin:0;font-size:14px}
 dl.kv dt{color:var(--mut);font-size:12.5px;padding-top:2px}
 dl.kv dd{margin:0}
</style>
</head><body>
<header><div class="wrap">
  <div><div class="naam"><a href="{{ url_for('overzicht') }}"
      style="color:inherit">{{ app_titel }}</a></div>
    <div class="onder">{{ app_ondertitel }}</div></div>
  <div class="wie">{{ gebruiker }}{% if not mag %} (alleen lezen){% endif %}</div>
</div></header>
<nav><div class="wrap">
  <a href="{{ url_for('overzicht') }}" {{ 'class=actief' if pad == '/' }}>Overzicht</a>
  <a href="{{ url_for('items') }}" {{ 'class=actief' if pad.startswith('/items') }}>Alles</a>
  <a href="{{ url_for('taken') }}" {{ 'class=actief' if pad == '/taken' }}>Taken</a>
  <a href="{{ url_for('beslissingen') }}" {{ 'class=actief' if pad == '/beslissingen' }}>Beslissingen</a>
  <a href="{{ url_for('bestanden') }}" {{ 'class=actief' if pad == '/bestanden' }}>Bestanden</a>
  <form action="{{ url_for('items') }}" method="get" role="search">
    <input type="text" name="q" placeholder="Zoeken" value="{{ request.args.get('q','') }}">
    <button class="knop stil" type="submit">Zoek</button>
  </form>
</div></nav>
<main><div class="wrap">
  {% with msgs = get_flashed_messages() %}{% if msgs %}
    <div class="melding">{{ msgs|join(' ') }}</div>
  {% endif %}{% endwith %}
  {{ body|safe }}
</div></main>
<script>
// Onthoudt per gebruiker welke secties open stonden.
document.querySelectorAll('details.vak[data-id]').forEach(function(d){
  var k = 'angela.open.' + d.dataset.id;
  var v = localStorage.getItem(k);
  if (v !== null) { d.open = v === '1'; }
  d.addEventListener('toggle', function(){ localStorage.setItem(k, d.open ? '1' : '0'); });
});
</script>
</body></html>
"""


def pagina(body, titel="Angela"):
    return render_template_string(
        BASE, body=body, titel=titel, app_titel=TITEL, app_ondertitel=ONDERTITEL,
        gebruiker=auth_gebruiker(), mag=mag_bewerken(), pad=request.path,
    )


DROPFORM = """
<details class="vak" data-id="drop" open>
  <summary><h2>Iets droppen</h2>
    <span class="tellers">notitie, link, bestand, taak of beslissing</span></summary>
  <div class="inhoud">
  {% if mag_bewerken() %}
  <form class="blok" method="post" action="{{ url_for('item_nieuw') }}"
        enctype="multipart/form-data" style="margin-top:14px">
    <div>
      <label for="d-titel">Titel</label>
      <input type="text" id="d-titel" name="titel" required
             placeholder="Waar gaat het over">
    </div>
    <div>
      <label for="d-tekst">Toelichting</label>
      <textarea id="d-tekst" name="tekst"
                placeholder="Wat er gezegd, bedacht of afgesproken is"></textarea>
    </div>
    <div class="velden">
      <div><label for="d-soort">Soort</label>
        <select id="d-soort" name="soort">
          {% for s in soorten %}<option value="{{ s }}">{{ s }}</option>{% endfor %}
        </select></div>
      <div><label for="d-ws">Werkstroom</label>
        <select id="d-ws" name="werkstroom_id">
          <option value="">nog niet bepaald</option>
          {% for w in werkstromen %}<option value="{{ w.id }}">{{ w.naam }}</option>{% endfor %}
        </select></div>
      <div><label for="d-url">Link</label>
        <input type="url" id="d-url" name="url" placeholder="https://"></div>
      <div><label for="d-wie">Verantwoordelijke</label>
        <select id="d-wie" name="verantwoordelijke_id">
          <option value="">niemand</option>
          {% for b in betrokkenen %}<option value="{{ b.id }}">{{ b.naam }}</option>{% endfor %}
        </select></div>
      <div><label for="d-deadline">Deadline</label>
        <input type="date" id="d-deadline" name="deadline"></div>
      <div><label for="d-bijlagen">Foto's en bestanden</label>
        <input type="file" id="d-bijlagen" name="bijlagen" multiple></div>
    </div>
    <div class="rijknoppen">
      <button class="knop" type="submit">Droppen</button>
      <span class="plat">Alleen een titel is verplicht. De rest kan later.</span>
    </div>
  </form>
  {% else %}
  <p class="leeg">Je hebt leesrechten. Vraag beheer om schrijfrechten op deze tegel.</p>
  {% endif %}
  </div>
</details>
"""

RIJEN = """
<div class="tabelkader"><table>
<thead><tr>
  <th class="nowrap">Gedropt</th><th>Soort</th><th>Titel</th>
  <th>Werkstroom</th><th>Wie</th><th class="nowrap">Status</th><th class="nowrap">Bijlagen</th>
</tr></thead>
<tbody>
{% for r in rijen %}
<tr>
  <td class="nowrap"><a href="{{ url_for('item_detail', iid=r.id) }}"
      >{{ r.aangemaakt_op|datum_be }}</a></td>
  <td><a href="{{ url_for('items', soort=r.soort) }}"
      ><span class="merk {{ r.soort }}">{{ r.soort }}</span></a></td>
  <td><a href="{{ url_for('item_detail', iid=r.id) }}">{{ r.titel }}</a>
      {% if r.tekst %}<div class="plat" style="font-size:13px">{{ r.tekst|kort(110) }}</div>{% endif %}</td>
  <td>{% if r.werkstroom_sleutel %}
        <a href="{{ url_for('items', werkstroom=r.werkstroom_sleutel) }}">{{ r.werkstroom_naam }}</a>
      {% else %}<a href="{{ url_for('items', werkstroom='geen') }}" class="plat">niet bepaald</a>{% endif %}</td>
  <td>{% if r.verantwoordelijke_naam %}
        <a href="{{ url_for('items', verantwoordelijke=r.verantwoordelijke_naam) }}"
          >{{ r.verantwoordelijke_naam }}</a>{% endif %}</td>
  <td class="nowrap">{% if r.soort == 'taak' %}
        <a href="{{ url_for('items', status=r.status) }}" class="st {{ r.status }}">{{ r.status }}</a>
        {% if r.deadline %}<div><a href="{{ url_for('item_detail', iid=r.id) }}"
          class="{{ 'telaat' if r.deadline < vandaag and r.status in ('open','bezig') }}"
          >{{ r.deadline|datum_be }}</a></div>{% endif %}
      {% elif r.soort == 'beslissing' and r.besloten_op %}
        <a href="{{ url_for('item_detail', iid=r.id) }}">{{ r.besloten_op|datum_be }}</a>
      {% endif %}</td>
  <td class="nowrap">{% if r.bijlagen %}
        <a href="{{ url_for('item_detail', iid=r.id) }}">{{ r.bijlagen|getal_be }}</a>{% endif %}</td>
</tr>
{% else %}
<tr><td colspan="7" class="leeg">Nog niets gedropt dat hieraan voldoet.</td></tr>
{% endfor %}
</tbody></table></div>
"""

OVERZICHT = """
<h1>Overzicht</h1>
<p class="sub">Alles rond dit initiatief op één plek: wat er bedacht, afgesproken
en uitgezocht is, en wat er nog open staat.</p>

<div class="kpis">
  <a class="kpi" href="{{ url_for('items') }}#lijst">
    <span class="cijfer">{{ tel.totaal|getal_be }}</span>
    <span class="lbl">items gedropt</span></a>
  <a class="kpi" href="{{ url_for('items', week='1') }}#lijst">
    <span class="cijfer">{{ tel.deze_week|getal_be }}</span>
    <span class="lbl">afgelopen zeven dagen</span></a>
  <a class="kpi" href="{{ url_for('taken') }}">
    <span class="cijfer">{{ tel.open_taken|getal_be }}</span>
    <span class="lbl">taken open</span></a>
  {% if tel.te_laat %}
  <a class="kpi waarschuwing" href="{{ url_for('items', telaat='1') }}#lijst">
    <span class="cijfer">{{ tel.te_laat|getal_be }}</span>
    <span class="lbl">over de deadline</span></a>
  {% endif %}
  <a class="kpi" href="{{ url_for('beslissingen') }}">
    <span class="cijfer">{{ tel.beslissingen|getal_be }}</span>
    <span class="lbl">beslissingen</span></a>
  <a class="kpi" href="{{ url_for('bestanden') }}">
    <span class="cijfer">{{ tel.bestanden|getal_be }}</span>
    <span class="lbl">bestanden</span></a>
  {% if tel.zonder_werkstroom %}
  <a class="kpi" href="{{ url_for('items', werkstroom='geen') }}#lijst">
    <span class="cijfer">{{ tel.zonder_werkstroom|getal_be }}</span>
    <span class="lbl">zonder werkstroom</span></a>
  {% endif %}
</div>

""" + DROPFORM + """

{% for w in stromen %}
<details class="vak" data-id="ws-{{ w.sleutel }}">
  <summary>
    <h2>{{ w.naam }}</h2>
    <span class="tellers">
      <span><a href="{{ url_for('items', werkstroom=w.sleutel) }}"
        ><b>{{ w.aantal|getal_be }}</b></a> items</span>
      {% if w.open_taken %}<span><a href="{{ url_for('items', werkstroom=w.sleutel, open='1') }}"
        ><b>{{ w.open_taken|getal_be }}</b></a> taken open</span>{% endif %}
      {% if w.beslissingen %}<span><a href="{{ url_for('items', werkstroom=w.sleutel, soort='beslissing') }}"
        ><b>{{ w.beslissingen|getal_be }}</b></a> beslissingen</span>{% endif %}
      {% if w.laatste %}<span>laatst <a href="{{ url_for('items', werkstroom=w.sleutel) }}"
        >{{ w.laatste|datum_be }}</a></span>{% endif %}
    </span>
  </summary>
  <div class="inhoud">
    <p class="plat" style="margin:14px 0 10px">{{ w.omschrijving }}</p>
    {% set rijen = ws_items(w.sleutel) %}
    """ + RIJEN + """
    {% if w.aantal > 8 %}<p style="margin:12px 0 0"><a
      href="{{ url_for('items', werkstroom=w.sleutel) }}">Alle {{ w.aantal|getal_be }} items van
      {{ w.naam|lower }}</a></p>{% endif %}
  </div>
</details>
{% endfor %}

<details class="vak" data-id="recent" open>
  <summary><h2>Laatst gedropt</h2>
    <span class="tellers"><b>{{ recent|length|getal_be }}</b> items</span></summary>
  <div class="inhoud" style="padding-top:6px">
    {% set rijen = recent %}
    """ + RIJEN + """
  </div>
</details>
"""

LIJST = """
<h1 id="lijst">Items</h1>
<p class="sub">Filter: {{ omschrijving }}.
  <a href="{{ url_for('items') }}">Alles tonen</a></p>

<div class="kpis">
  <a class="kpi" href="#lijst">
    <span class="cijfer">{{ rijen|length|getal_be }}</span>
    <span class="lbl">items in deze weergave</span></a>
  <a class="kpi" href="{{ url_for('items') }}#lijst">
    <span class="cijfer">{{ totaal_alles|getal_be }}</span>
    <span class="lbl">items in totaal</span></a>
</div>

<details class="vak" data-id="filters" open>
  <summary><h2>Verfijnen</h2><span class="tellers">soort, werkstroom, status, persoon</span></summary>
  <div class="inhoud">
    <form class="blok" method="get" action="{{ url_for('items') }}" style="margin-top:14px">
      <div class="velden">
        <div><label for="f-q">Zoeken</label>
          <input type="text" id="f-q" name="q" value="{{ args.get('q','') }}"></div>
        <div><label for="f-soort">Soort</label>
          <select id="f-soort" name="soort"><option value="">alle</option>
            {% for s in ['notitie','link','bestand','taak','beslissing'] %}
            <option value="{{ s }}" {{ 'selected' if args.get('soort')==s }}>{{ s }}</option>
            {% endfor %}</select></div>
        <div><label for="f-ws">Werkstroom</label>
          <select id="f-ws" name="werkstroom"><option value="">alle</option>
            <option value="geen" {{ 'selected' if args.get('werkstroom')=='geen' }}>niet bepaald</option>
            {% for w in werkstromen %}
            <option value="{{ w.sleutel }}" {{ 'selected' if args.get('werkstroom')==w.sleutel }}
              >{{ w.naam }}</option>{% endfor %}</select></div>
        <div><label for="f-st">Status</label>
          <select id="f-st" name="status"><option value="">alle</option>
            {% for s in ['open','bezig','klaar','geparkeerd','vervallen'] %}
            <option value="{{ s }}" {{ 'selected' if args.get('status')==s }}>{{ s }}</option>
            {% endfor %}</select></div>
        <div><label for="f-wie">Verantwoordelijke</label>
          <select id="f-wie" name="verantwoordelijke"><option value="">iedereen</option>
            {% for b in betrokkenen %}
            <option value="{{ b.naam }}" {{ 'selected' if args.get('verantwoordelijke')==b.naam }}
              >{{ b.naam }}</option>{% endfor %}</select></div>
      </div>
      <div class="rijknoppen"><button class="knop" type="submit">Toepassen</button></div>
    </form>
  </div>
</details>

""" + RIJEN

TAKEN = """
<h1 id="lijst">Taken</h1>
<p class="sub">Wat er open staat, per persoon en op deadline.</p>

<div class="kpis">
{% for p in per_persoon %}
  <a class="kpi {{ 'waarschuwing' if p.te_laat }}"
     href="{{ url_for('items', open='1', verantwoordelijke=p.naam) if p.naam != 'niet toegewezen'
             else url_for('items', open='1') }}#lijst">
    <span class="cijfer">{{ p.open_taken|getal_be }}</span>
    <span class="lbl">{{ p.naam }}{% if p.te_laat %}, {{ p.te_laat|getal_be }} te laat{% endif %}</span></a>
{% else %}
  <a class="kpi" href="{{ url_for('items', soort='taak') }}#lijst">
    <span class="cijfer">0</span><span class="lbl">taken open</span></a>
{% endfor %}
</div>

<details class="vak" data-id="taken-open" open>
  <summary><h2>Open</h2>
    <span class="tellers"><b>{{ open_taken|length|getal_be }}</b> taken</span></summary>
  <div class="inhoud" style="padding-top:6px">
    {% set rijen = open_taken %}
    """ + RIJEN + """
  </div>
</details>

<details class="vak" data-id="taken-klaar">
  <summary><h2>Afgehandeld</h2>
    <span class="tellers"><b>{{ afgerond|length|getal_be }}</b> taken</span></summary>
  <div class="inhoud" style="padding-top:6px">
    {% set rijen = afgerond %}
    """ + RIJEN + """
  </div>
</details>
"""

BESLISSINGEN = """
<h1 id="lijst">Beslissingen</h1>
<p class="sub">Wat vastligt, met de datum waarop het besloten is.</p>
""" + RIJEN

BESTANDEN = """
<h1 id="lijst">Bestanden</h1>
<p class="sub">Foto's en documenten, nieuwste eerst.</p>

<details class="vak" data-id="best-fotos" open>
  <summary><h2>Foto's</h2>
    <span class="tellers"><b>{{ rijen|selectattr('is_afbeelding')|list|length|getal_be }}</b> afbeeldingen</span></summary>
  <div class="inhoud" style="padding-top:14px">
    <div class="fotos">
    {% for b in rijen if b.is_afbeelding %}
      <figure><a href="{{ url_for('item_detail', iid=b.item_id) }}">
        <img src="{{ url_for('bijlage', bid=b.id) }}" alt="{{ b.bestandsnaam }}" loading="lazy"></a>
        <figcaption><a href="{{ url_for('item_detail', iid=b.item_id) }}">{{ b.item_titel }}</a><br>
          <a href="{{ url_for('item_detail', iid=b.item_id) }}">{{ b.geupload_op|datum_be }}</a>
          {% if b.grootte_bytes %}, {{ b.grootte_bytes|omvang_be }}{% endif %}</figcaption></figure>
    {% else %}
      <p class="leeg">Nog geen foto's.</p>
    {% endfor %}
    </div>
  </div>
</details>

<details class="vak" data-id="best-alles" open>
  <summary><h2>Alle bestanden</h2>
    <span class="tellers"><b>{{ rijen|length|getal_be }}</b> bestanden</span></summary>
  <div class="inhoud" style="padding-top:6px">
  <div class="tabelkader"><table>
  <thead><tr><th class="nowrap">Datum</th><th>Bestand</th><th>Hoort bij</th>
    <th>Werkstroom</th><th class="nowrap">Grootte</th><th>Door</th></tr></thead>
  <tbody>
  {% for b in rijen %}
  <tr>
    <td class="nowrap"><a href="{{ url_for('item_detail', iid=b.item_id) }}"
        >{{ b.geupload_op|datum_be }}</a></td>
    <td><a href="{{ url_for('bijlage', bid=b.id) }}">{{ b.bestandsnaam }}</a></td>
    <td><a href="{{ url_for('item_detail', iid=b.item_id) }}">{{ b.item_titel }}</a></td>
    <td>{% if b.werkstroom_sleutel %}<a href="{{ url_for('items', werkstroom=b.werkstroom_sleutel) }}"
        >{{ b.werkstroom_naam }}</a>{% endif %}</td>
    <td class="nowrap">{% if b.grootte_bytes %}<a href="{{ url_for('bijlage', bid=b.id, download='1') }}"
        >{{ b.grootte_bytes|omvang_be }}</a>{% endif %}</td>
    <td class="plat">{{ b.geupload_door or '' }}</td>
  </tr>
  {% else %}
  <tr><td colspan="6" class="leeg">Nog geen bestanden.</td></tr>
  {% endfor %}
  </tbody></table></div>
  </div>
</details>
"""

DETAIL = """
<h1>{{ r.titel }}</h1>
<p class="sub">
  <a href="{{ url_for('items', soort=r.soort) }}"><span class="merk {{ r.soort }}">{{ r.soort }}</span></a>
  gedropt door {{ r.aangemaakt_door }} op
  <a href="{{ url_for('items', dag=r.aangemaakt_op.date().isoformat()) }}"
    >{{ r.aangemaakt_op|datumtijd_be }}</a>
</p>

<details class="vak" data-id="detail-inhoud" open>
  <summary><h2>Inhoud</h2><span class="tellers">
    {% if r.werkstroom_naam %}<span>{{ r.werkstroom_naam }}</span>{% endif %}
    {% if r.verantwoordelijke_naam %}<span>{{ r.verantwoordelijke_naam }}</span>{% endif %}
    {% if r.soort == 'taak' %}<span class="st {{ r.status }}">{{ r.status }}</span>{% endif %}
  </span></summary>
  <div class="inhoud" style="padding-top:14px">
    {% if r.tekst %}<p class="plat" style="white-space:pre-wrap">{{ r.tekst }}</p>{% endif %}
    <dl class="kv">
      {% if r.url %}<dt>Link</dt><dd><a href="{{ r.url }}" rel="noreferrer noopener"
        target="_blank">{{ r.url }}</a></dd>{% endif %}
      <dt>Werkstroom</dt><dd>{% if r.werkstroom_sleutel %}
        <a href="{{ url_for('items', werkstroom=r.werkstroom_sleutel) }}">{{ r.werkstroom_naam }}</a>
        {% else %}<a href="{{ url_for('items', werkstroom='geen') }}" class="plat">niet bepaald</a>{% endif %}</dd>
      {% if r.verantwoordelijke_naam %}<dt>Verantwoordelijke</dt>
        <dd><a href="{{ url_for('items', verantwoordelijke=r.verantwoordelijke_naam) }}"
          >{{ r.verantwoordelijke_naam }}</a></dd>{% endif %}
      {% if r.deadline %}<dt>Deadline</dt><dd><a href="{{ url_for('items', open='1') }}"
        class="{{ 'telaat' if r.deadline < vandaag and r.status in ('open','bezig') }}"
        >{{ r.deadline|datum_be }}</a></dd>{% endif %}
      {% if r.besloten_op %}<dt>Besloten op</dt><dd><a href="{{ url_for('beslissingen') }}"
        >{{ r.besloten_op|datum_be }}</a></dd>{% endif %}
      {% if r.bron_soort %}<dt>Herkomst</dt><dd>{{ r.bron_soort }}{% if r.bron_titel %},
        <span class="plat">{{ r.bron_titel }}</span>{% endif %}</dd>{% endif %}
      <dt>Bijgewerkt</dt><dd><a href="{{ url_for('item_detail', iid=r.id) }}"
        >{{ r.bijgewerkt_op|datumtijd_be }}</a></dd>
    </dl>
    {% if mag_bewerken() and r.soort == 'taak' %}
    <form method="post" action="{{ url_for('item_status', iid=r.id) }}"
          class="rijknoppen" style="margin-top:14px">
      {% for s in ['open','bezig','klaar','geparkeerd','vervallen'] %}
        <button class="knop stil" name="status" value="{{ s }}"
                {{ 'disabled' if r.status == s }}>{{ s }}</button>
      {% endfor %}
    </form>
    {% endif %}
  </div>
</details>

<details class="vak" data-id="detail-bijlagen" {{ 'open' if bijlagen }}>
  <summary><h2>Bijlagen</h2>
    <span class="tellers"><b>{{ bijlagen|length|getal_be }}</b> bestanden</span></summary>
  <div class="inhoud" style="padding-top:14px">
    <div class="fotos">
    {% for b in bijlagen if b.is_afbeelding %}
      <figure><a href="{{ url_for('bijlage', bid=b.id) }}">
        <img src="{{ url_for('bijlage', bid=b.id) }}" alt="{{ b.bestandsnaam }}" loading="lazy"></a>
        <figcaption>{{ b.bestandsnaam }}<br>
          <a href="{{ url_for('bijlage', bid=b.id, download='1') }}">{{ b.grootte_bytes|omvang_be }}</a>
          {% if mag_bewerken() %}
          <form method="post" action="{{ url_for('bijlage_verwijder', bid=b.id) }}"
                style="display:inline"><button class="knop gevaar"
                style="padding:2px 8px;font-size:12px">weg</button></form>{% endif %}
        </figcaption></figure>
    {% endfor %}
    </div>
    <ul style="margin:12px 0 0;padding-left:18px">
    {% for b in bijlagen if not b.is_afbeelding %}
      <li><a href="{{ url_for('bijlage', bid=b.id) }}">{{ b.bestandsnaam }}</a>
        <span class="plat">({{ b.grootte_bytes|omvang_be }},
          <a href="{{ url_for('item_detail', iid=r.id) }}">{{ b.geupload_op|datum_be }}</a>)</span>
        {% if mag_bewerken() %}
        <form method="post" action="{{ url_for('bijlage_verwijder', bid=b.id) }}"
              style="display:inline"><button class="knop gevaar"
              style="padding:2px 8px;font-size:12px">weg</button></form>{% endif %}</li>
    {% endfor %}
    </ul>
    {% if not bijlagen %}<p class="leeg">Nog geen bijlagen.</p>{% endif %}
  </div>
</details>

<details class="vak" data-id="detail-verband" {{ 'open' if verbanden }}>
  <summary><h2>Verbanden</h2>
    <span class="tellers"><b>{{ verbanden|length|getal_be }}</b> gekoppelde items</span></summary>
  <div class="inhoud" style="padding-top:14px">
    <ul style="margin:0 0 12px;padding-left:18px">
    {% for v in verbanden %}
      <li><span class="plat">{{ v.relatie }}</span>
        <a href="{{ url_for('item_detail', iid=v.ander_id) }}">{{ v.titel }}</a>
        <span class="merk {{ v.soort }}">{{ v.soort }}</span>
        {% if mag_bewerken() %}
        <form method="post" action="{{ url_for('verband_verwijder', vid=v.id) }}"
              style="display:inline"><button class="knop gevaar"
              style="padding:2px 8px;font-size:12px">weg</button></form>{% endif %}</li>
    {% else %}
      <li class="plat">Nog geen verbanden.</li>
    {% endfor %}
    </ul>
    {% if mag_bewerken() %}
    <form method="post" action="{{ url_for('verband_nieuw', iid=r.id) }}" class="blok">
      <div class="velden">
        <div><label for="v-rel">Relatie</label>
          <input type="text" id="v-rel" name="relatie" value="hoort bij"></div>
        <div><label for="v-naar">Ander item</label>
          <select id="v-naar" name="naar_item_id">
            {% for a in andere %}<option value="{{ a.id }}">{{ a.titel }} ({{ a.soort }})</option>{% endfor %}
          </select></div>
      </div>
      <div class="rijknoppen"><button class="knop stil" type="submit">Koppelen</button></div>
    </form>
    {% endif %}
  </div>
</details>

{% if mag_bewerken() %}
<details class="vak" data-id="detail-bewerk">
  <summary><h2>Bewerken</h2><span class="tellers">velden aanpassen of item verwijderen</span></summary>
  <div class="inhoud">
    <form class="blok" method="post" action="{{ url_for('item_bewerk', iid=r.id) }}"
          enctype="multipart/form-data" style="margin-top:14px">
      <div><label for="e-titel">Titel</label>
        <input type="text" id="e-titel" name="titel" value="{{ r.titel }}" required></div>
      <div><label for="e-tekst">Toelichting</label>
        <textarea id="e-tekst" name="tekst">{{ r.tekst or '' }}</textarea></div>
      <div class="velden">
        <div><label for="e-soort">Soort</label>
          <select id="e-soort" name="soort">
            {% for s in ['notitie','link','bestand','taak','beslissing'] %}
            <option value="{{ s }}" {{ 'selected' if r.soort == s }}>{{ s }}</option>{% endfor %}
          </select></div>
        <div><label for="e-ws">Werkstroom</label>
          <select id="e-ws" name="werkstroom_id"><option value="">niet bepaald</option>
            {% for w in werkstromen %}<option value="{{ w.id }}"
              {{ 'selected' if r.werkstroom_id == w.id }}>{{ w.naam }}</option>{% endfor %}
          </select></div>
        <div><label for="e-url">Link</label>
          <input type="url" id="e-url" name="url" value="{{ r.url or '' }}"></div>
        <div><label for="e-wie">Verantwoordelijke</label>
          <select id="e-wie" name="verantwoordelijke_id"><option value="">niemand</option>
            {% for b in betrokkenen %}<option value="{{ b.id }}"
              {{ 'selected' if r.verantwoordelijke_id == b.id }}>{{ b.naam }}</option>{% endfor %}
          </select></div>
        <div><label for="e-st">Status</label>
          <select id="e-st" name="status">
            {% for s in ['open','bezig','klaar','geparkeerd','vervallen'] %}
            <option value="{{ s }}" {{ 'selected' if r.status == s }}>{{ s }}</option>{% endfor %}
          </select></div>
        <div><label for="e-deadline">Deadline</label>
          <input type="date" id="e-deadline" name="deadline"
            value="{{ r.deadline.isoformat() if r.deadline else '' }}"></div>
        <div><label for="e-besloten">Besloten op</label>
          <input type="date" id="e-besloten" name="besloten_op"
            value="{{ r.besloten_op.isoformat() if r.besloten_op else '' }}"></div>
        <div><label for="e-bijlagen">Bijlagen toevoegen</label>
          <input type="file" id="e-bijlagen" name="bijlagen" multiple></div>
      </div>
      <input type="hidden" name="bron_soort" value="{{ r.bron_soort or '' }}">
      <input type="hidden" name="bron_ref" value="{{ r.bron_ref or '' }}">
      <input type="hidden" name="bron_titel" value="{{ r.bron_titel or '' }}">
      <div class="rijknoppen"><button class="knop" type="submit">Opslaan</button></div>
    </form>
    <form method="post" action="{{ url_for('item_verwijder', iid=r.id) }}"
          style="margin-top:16px"
          onsubmit="return confirm('Dit item en zijn bijlagen definitief verwijderen?')">
      <button class="knop gevaar" type="submit">Item verwijderen</button>
    </form>
  </div>
</details>
{% endif %}
"""


# Jinja-hulpjes die de templates nodig hebben.
def _ws_items(sleutel):
    return zoek_items({"werkstroom": sleutel}, limiet=8)


app.jinja_env.globals["mag_bewerken"] = mag_bewerken
app.jinja_env.globals["ws_items"] = _ws_items
app.jinja_env.globals["soorten"] = SOORTEN


@app.context_processor
def _globale_waarden():
    return {"vandaag": date.today()}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)

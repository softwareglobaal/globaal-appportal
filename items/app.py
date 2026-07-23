#!/usr/bin/env python3
"""
Items te koop - verkoop-etalage tweedehands ICT met AI-taxatie.

Eén codebase, twee rollen via ITEMS_ROLE:
  - beheer  : volledige beheerkant (achter Authentik forward-auth op de portal)
  - verkoop : publieke read-only etalage (eigen poort, geen beheerknop)

Data: appportal-Postgres, schema `items`. Foto's als bestanden onder ITEMS_UPLOAD_DIR.
De beheer-rol vertrouwt op de forward-auth ervoor; de gebruiker komt via
X-authentik-* headers binnen (geen eigen wachtwoord meer).
"""

import os
import io
import json
import time
import base64
import secrets
import threading
import mimetypes
from functools import wraps
from urllib.parse import quote

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from flask import (
    Flask, request, redirect, url_for,
    render_template_string, send_from_directory, abort, flash, g,
)

# ---------------------------------------------------------------------------
# Configuratie
# ---------------------------------------------------------------------------
ROLE       = os.environ.get("ITEMS_ROLE", "beheer")   # beheer | verkoop
IS_BEHEER  = ROLE == "beheer"
PORT       = int(os.environ.get("PORT", "3015"))
UPLOAD_DIR = os.environ.get("ITEMS_UPLOAD_DIR", "/data/fotos")
MODEL      = os.environ.get("VALUATION_MODEL", "claude-sonnet-5")
VALUATION_EFFORT = os.environ.get("VALUATION_EFFORT", "medium")
MUNT_SYMBOOL = "€"
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "mch@h-architects.be")
WINKEL_NAAM = os.environ.get("WINKEL_NAAM", "Techpoint")

# Authentik-groepen die mogen bewerken (leeg = iedereen die door forward-auth komt).
EDITOR_GROUPS = {g_.strip() for g_ in os.environ.get("EDITOR_GROUPS", "").split(",") if g_.strip()}

PRIJS_INPUT       = float(os.environ.get("PRIJS_INPUT_USD_MTOK", "3.0"))
PRIJS_OUTPUT      = float(os.environ.get("PRIJS_OUTPUT_USD_MTOK", "15.0"))
PRIJS_CACHE_READ  = float(os.environ.get("PRIJS_CACHE_READ_USD_MTOK", "0.30"))
PRIJS_CACHE_WRITE = float(os.environ.get("PRIJS_CACHE_WRITE_USD_MTOK", "3.75"))
PRIJS_WEBSEARCH   = float(os.environ.get("PRIJS_WEBSEARCH_USD_1000", "10.0"))
EUR_PER_USD       = float(os.environ.get("EUR_PER_USD", "0.92"))

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.jinja_env.globals["IS_BEHEER"] = IS_BEHEER
app.jinja_env.globals["contact_email"] = CONTACT_EMAIL
app.jinja_env.globals["winkel_naam"] = WINKEL_NAAM

CONDITIES = ["nieuw", "als_nieuw", "goed", "gebruikt", "defect_onderdelen"]
STATUSSEN = ["concept", "onderzoek", "te_controleren", "live",
             "gereserveerd", "verkocht", "gearchiveerd"]
ZOEK_DOMEINEN = ["2dehands.be", "marktplaats.nl", "ebay.nl", "ebay.be"]

JOBS = {}
JOBS_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Database (appportal-Postgres, schema items)
# ---------------------------------------------------------------------------
def _dsn():
    url = os.environ.get("ITEMS_DB_URL", "")
    return url.replace("postgresql+psycopg://", "postgresql://").replace(
        "postgres+psycopg://", "postgresql://")


def _connect():
    return psycopg.connect(_dsn(), row_factory=dict_row,
                           options="-c search_path=items,public")


def db():
    if "db" not in g:
        g.db = _connect()
    return g.db


@app.teardown_appcontext
def _close_db(_exc):
    d = g.pop("db", None)
    if d is not None:
        d.close()


# ---------------------------------------------------------------------------
# Hulpjes
# ---------------------------------------------------------------------------
def euro(cents):
    if cents is None:
        return None
    return f"{MUNT_SYMBOOL} {cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


app.jinja_env.filters["euro"] = euro


def specs_dict(raw):
    if isinstance(raw, dict):
        return raw
    try:
        d = json.loads(raw or "{}")
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def specs_naar_tekst(d):
    return "\n".join(f"{k}: {v}" for k, v in d.items())


def tekst_naar_specs(t):
    out = {}
    for regel in (t or "").splitlines():
        if ":" in regel:
            k, v = regel.split(":", 1)
            if k.strip():
                out[k.strip()] = v.strip()
    return out


ACRONIEMEN = {
    "cpu", "gpu", "apu", "ram", "vram", "rom", "ssd", "hdd", "nvme", "emmc",
    "usb", "usbc", "hdmi", "vga", "dvi", "dp", "lan", "wlan", "wan", "wifi",
    "nfc", "os", "bios", "uefi", "ean", "sku", "upc", "ip", "mac", "pc", "ips",
    "tn", "va", "oled", "led", "lcd", "qled", "sd", "sdhc", "microsd", "poe",
    "nic", "mp", "fhd", "hd", "uhd", "qhd", "wqhd", "rj45", "ddr", "ddr3",
    "ddr4", "ddr5", "lpddr", "tb", "gb", "mb", "kb", "ghz", "mhz", "tpm",
    "ecc", "sata", "m2", "pcie", "id",
}


def netjes_label(s):
    """Eerste letter hoofdletter; acroniemen volledig in hoofdletters."""
    s = str(s or "").replace("_", " ").strip()
    if not s:
        return s
    woorden = s.split()
    uit = []
    for i, w in enumerate(woorden):
        if w.lower() in ACRONIEMEN:
            uit.append(w.upper())
        elif i == 0:
            uit.append(w[:1].upper() + w[1:])
        else:
            uit.append(w)
    return " ".join(uit)


# Hardware-categorieen voor de navigatie. Een product hoort bij een categorie als
# zijn (vrije-tekst) categorie-veld een van de sleutels bevat.
CATEGORIEEN = [
    {"slug": "laptops", "label": "Laptops",
     "sleutels": ["laptop", "notebook", "ultrabook", "macbook"]},
    {"slug": "tablets", "label": "Tablets",
     "sleutels": ["tablet", "ipad"]},
    {"slug": "pcs", "label": "PC's",
     "sleutels": ["pc", "desktop", "computer", "workstation", "mini-pc",
                  "all-in-one", "toren", "sff"]},
    {"slug": "kabels", "label": "Kabels",
     "sleutels": ["kabel", "cable", "adapter", "snoer", "cord", "dock"]},
]
app.jinja_env.globals["categorieen"] = CATEGORIEEN


def categorie_van(cat):
    t = (cat or "").lower()
    for c in CATEGORIEEN:
        if any(s in t for s in c["sleutels"]):
            return c["slug"]
    return None


def usd_eur(usd):
    if not usd:
        return "$ 0,0000"
    return f"$ {usd:.4f} (~{MUNT_SYMBOOL} {usd * EUR_PER_USD:.4f})".replace(".", ",")


def _auth_gebruiker():
    return (request.headers.get("X-authentik-username")
            or request.headers.get("X-authentik-name") or "onbekend")


def _auth_groepen():
    ruw = request.headers.get("X-authentik-groups", "")
    return {p.strip() for sep in ("|", ",") for p in ruw.split(sep) if p.strip()}


def beheer_route(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not IS_BEHEER:
            abort(404)
        if EDITOR_GROUPS and not (EDITOR_GROUPS & _auth_groepen()):
            abort(403)
        return f(*a, **kw)
    return wrapper


def prod_images_con(con, pid):
    return con.execute(
        "SELECT * FROM product_images WHERE product_id=%s "
        "ORDER BY is_primair DESC, volgorde, id", (pid,)).fetchall()


def prod_images(pid):
    return prod_images_con(db(), pid)


def _job(pid, **kw):
    with JOBS_LOCK:
        JOBS.setdefault(pid, {}).update(kw)


def _job_get(pid):
    with JOBS_LOCK:
        return dict(JOBS.get(pid, {"status": "onbekend"}))


# ---------------------------------------------------------------------------
# AI-taxatie via Claude Sonnet met web search
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_BASE = """Je bent een taxateur van tweedehands ICT-apparatuur.
Je krijgt foto's van een item plus merk, model/typenummer, serienummer en een
handmatig conditielabel. Je taak:

1. Identificeer het exacte product en vul de IDENTIFICATIEVELDEN in als losse
   waarden: merk, model (typenummer), serienummer/service tag en categorie
   (laptop, server, monitor, switch, ...). Voor Dell (service tag), Lenovo en HP
   mapt het serienummer/product-ID vaak op de fabrieksconfiguratie; gebruik dat.
2. Vul de TECHNISCHE specificaties (specs) volledig in: cpu, ram, opslag, gpu,
   scherm, resolutie, bouwjaar, poorten, besturingssysteem, gewicht, webcam, enz.
   Zet merk, model of serienummer NIET in specs - die horen in de losse
   identificatievelden hierboven, niet in de specs.
3. Schrijf een korte, verkoopklare titel en omschrijving.
"""

SYSTEM_PROMPT_MARKT = """
4. Doe marktonderzoek met web_search. Verkochte advertenties zijn de beste
   graadmeter. Zijn die schaars, gebruik dan vraagprijzen als basis, maar reken
   ze realistisch terug: tweedehands ICT verkoopt doorgaans 10 tot 25 procent
   ONDER de vraagprijs. Weeg de conditie mee (40 tot 60% van de prijs). Vermeld
   per bron of het een vraagprijs of verkoopprijs is. Zet vertrouwen alleen op
   "onvoldoende_data" als je echt geen enkele advertentie vindt; heb je wel
   vraagprijzen, geef dan een teruggerekend advies met vertrouwen "laag" of "midden".

Rond ALTIJD af met dien_taxatie_in."""

SYSTEM_PROMPT_SPECS = """
4. Doe GEEN marktonderzoek en bepaal GEEN prijs. Zet prijs_voorstel_eur op 0,
   bronnen op een lege lijst en vertrouwen op "onvoldoende_data". Richt je volledig
   op identificatie en technische specs.

Rond ALTIJD af met dien_taxatie_in."""

TAXATIE_TOOL = {
    "name": "dien_taxatie_in",
    "description": "Lever het eindresultaat van de taxatie gestructureerd aan.",
    "input_schema": {
        "type": "object",
        "properties": {
            "merk": {"type": "string"},
            "model": {"type": "string", "description": "Model- of typenummer"},
            "serienummer": {"type": "string"},
            "categorie": {"type": "string",
                          "description": "laptop, server, monitor, switch, ..."},
            "titel": {"type": "string"},
            "omschrijving": {"type": "string"},
            "specs": {"type": "object",
                      "description": "ALLEEN technische specs (cpu, ram, opslag, gpu, "
                                     "scherm, resolutie, os, ...). Geen merk/model/serienummer."},
            "prijs_voorstel_eur": {"type": "number"},
            "prijs_min_eur": {"type": "number"},
            "prijs_max_eur": {"type": "number"},
            "vertrouwen": {"type": "string",
                           "enum": ["hoog", "midden", "laag", "onvoldoende_data"]},
            "redenering": {"type": "string"},
            "bronnen": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "bron": {"type": "string"},
                        "url": {"type": "string"},
                        "titel": {"type": "string"},
                        "prijs_eur": {"type": "number"},
                        "conditie": {"type": "string"},
                        "type": {"type": "string", "enum": ["vraagprijs", "verkocht"]},
                    },
                    "required": ["bron", "prijs_eur", "type"],
                },
            },
        },
        "required": ["titel", "specs", "prijs_voorstel_eur", "vertrouwen", "bronnen"],
    },
}

WEB_SEARCH = {
    "type": "web_search_20260209",
    "name": "web_search",
    "max_uses": 2,
    "allowed_domains": ZOEK_DOMEINEN,
}


def _img_block(pad):
    try:
        from PIL import Image
        img = Image.open(pad).convert("RGB")
        img.thumbnail((1400, 1400))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82)
        data = base64.standard_b64encode(buf.getvalue()).decode()
        return {"type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}
    except Exception:
        mt = mimetypes.guess_type(pad)[0] or "image/jpeg"
        with open(pad, "rb") as fh:
            data = base64.standard_b64encode(fh.read()).decode()
        return {"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}}


def _tel_usage(tot, usage):
    tot["input"] += getattr(usage, "input_tokens", 0) or 0
    tot["output"] += getattr(usage, "output_tokens", 0) or 0
    tot["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0
    tot["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0) or 0
    stu = getattr(usage, "server_tool_use", None)
    if stu is not None:
        tot["web"] += getattr(stu, "web_search_requests", 0) or 0


def _kosten_usd(tot):
    return (tot["input"] / 1e6 * PRIJS_INPUT + tot["output"] / 1e6 * PRIJS_OUTPUT
            + tot["cache_read"] / 1e6 * PRIJS_CACHE_READ
            + tot["cache_write"] / 1e6 * PRIJS_CACHE_WRITE
            + tot["web"] / 1000 * PRIJS_WEBSEARCH)


def taxeer(product, image_paden, voortgang=None, met_marktonderzoek=True):
    import anthropic

    client = anthropic.Anthropic()
    tot = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "web": 0}

    if met_marktonderzoek:
        system = SYSTEM_PROMPT_BASE + SYSTEM_PROMPT_MARKT
        tools = [WEB_SEARCH, TAXATIE_TOOL]
        max_rondes = 6
    else:
        system = SYSTEM_PROMPT_BASE + SYSTEM_PROMPT_SPECS
        tools = [TAXATIE_TOOL]
        max_rondes = 2

    content = [_img_block(p) for p in image_paden if os.path.exists(p)]
    content.append({"type": "text", "text": (
        f"Merk: {product['merk'] or '-'}\n"
        f"Model: {product['model'] or '-'}\n"
        f"Serienummer: {product['serienummer'] or '-'}\n"
        f"Conditie: {product['conditie'] or '-'}\n"
        f"Notities: {product['conditie_notities'] or ''}"
    )})
    messages = [{"role": "user", "content": content}]

    for i in range(max_rondes):
        if voortgang:
            if not met_marktonderzoek:
                voortgang("Product identificeren en specs invullen...")
            else:
                voortgang("Product identificeren en marktonderzoek..."
                          if i == 0 else f"Marktonderzoek loopt (stap {i + 1})...")
        resp = client.messages.create(
            model=MODEL, max_tokens=8000,
            thinking={"type": "adaptive"},
            output_config={"effort": VALUATION_EFFORT},
            system=system, tools=tools, messages=messages,
        )
        _tel_usage(tot, resp.usage)
        taxatie = next((b for b in resp.content
                        if b.type == "tool_use" and b.name == "dien_taxatie_in"), None)
        if taxatie:
            tot["usd"] = _kosten_usd(tot)
            return taxatie.input, tot
        if resp.stop_reason in ("tool_use", "pause_turn"):
            messages.append({"role": "assistant", "content": resp.content})
            continue
        break
    raise RuntimeError("Model rondde de taxatie niet af met dien_taxatie_in.")


def _eur_to_cents(x):
    try:
        return round(float(x) * 100)
    except (TypeError, ValueError):
        return None


def _leeg_none(x):
    return x if (x and str(x).strip()) else None


def verwerk_taxatie(con, pid, resultaat, kosten):
    vv = _eur_to_cents(resultaat.get("prijs_voorstel_eur"))
    vmin = _eur_to_cents(resultaat.get("prijs_min_eur"))
    vmax = _eur_to_cents(resultaat.get("prijs_max_eur"))

    vid = con.execute(
        """INSERT INTO valuations
           (product_id, model_gebruikt, prijs_voorstel_cents, prijs_min_cents,
            prijs_max_cents, vertrouwen, redenering, ruwe_respons,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            web_searches, kosten_usd)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (pid, MODEL, vv, vmin, vmax, resultaat.get("vertrouwen"),
         resultaat.get("redenering"), Json(resultaat),
         kosten.get("input", 0), kosten.get("output", 0), kosten.get("cache_read", 0),
         kosten.get("cache_write", 0), kosten.get("web", 0), kosten.get("usd", 0)),
    ).fetchone()["id"]

    for b in resultaat.get("bronnen", []):
        con.execute(
            """INSERT INTO valuation_sources
               (valuation_id, bron, url, titel, prijs_cents, conditie, type)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (vid, b.get("bron"), b.get("url"), b.get("titel"),
             _eur_to_cents(b.get("prijs_eur")), b.get("conditie"), b.get("type")),
        )

    schone_specs = {k: v for k, v in (resultaat.get("specs") or {}).items()
                    if k.lower() not in ("merk", "merknaam", "model", "serienummer",
                                         "serial", "serienr", "serie", "servicetag",
                                         "service_tag")}

    con.execute(
        """UPDATE products SET
             merk=COALESCE(%s, merk),
             model=COALESCE(%s, model),
             categorie=COALESCE(%s, categorie),
             serienummer=COALESCE(NULLIF(serienummer,''), %s),
             titel=COALESCE(%s, titel),
             omschrijving=COALESCE(%s, omschrijving),
             specs=%s,
             prijs_voorstel_cents=%s, prijs_min_cents=%s, prijs_max_cents=%s,
             status='te_controleren', bijgewerkt_op=now()
           WHERE id=%s""",
        (_leeg_none(resultaat.get("merk")), _leeg_none(resultaat.get("model")),
         _leeg_none(resultaat.get("categorie")), _leeg_none(resultaat.get("serienummer")),
         resultaat.get("titel"), resultaat.get("omschrijving"),
         Json(schone_specs), vv, vmin, vmax, pid),
    )
    con.commit()


def _taxatie_worker(pid, modus):
    con = _connect()
    try:
        r = con.execute("SELECT * FROM products WHERE id=%s", (pid,)).fetchone()
        paden = [os.path.join(UPLOAD_DIR, i["bestand"]) for i in prod_images_con(con, pid)]
        _job(pid, fase="Foto's en gegevens naar Claude sturen...")
        resultaat, kosten = taxeer(dict(r), paden, voortgang=lambda f: _job(pid, fase=f),
                                   met_marktonderzoek=(modus == "prijs"))
        _job(pid, fase="Resultaat opslaan...")
        verwerk_taxatie(con, pid, resultaat, kosten)
        _job(pid, status="klaar", fase="Klaar")
    except Exception as e:  # noqa: BLE001
        con.rollback()
        con.execute("UPDATE products SET status='concept' WHERE id=%s", (pid,))
        con.commit()
        _job(pid, status="fout", error=str(e))
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
BASE = """
<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ titel or winkel_naam }}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&family=Zilla+Slab:wght@500;600;700&display=swap" rel="stylesheet">
<style>
 :root{--bg:#ffffff;--page:#eef1f5;--surface:#ffffff;--soft:#f1f4f8;--ink:#16202e;--mut:#586274;--line:#d9dfe8;--navy:#13233c;--navy2:#1c3157;--navy-ink:#eaf0f7;--navy-mut:#9fb2c9;--accent:#1c5fa8;--accent-ink:#ffffff}
 @media(prefers-color-scheme:dark){:root{--bg:#0e131a;--page:#0b1017;--surface:#141b25;--soft:#182130;--ink:#e6ecf3;--mut:#93a1b5;--line:#26313f;--navy:#0b1626;--navy2:#13233c;--navy-ink:#e6ecf3;--navy-mut:#93a1b5;--accent:#4f92d6;--accent-ink:#06121f}}
 *{box-sizing:border-box}html,body{margin:0}
 body{background:var(--page);color:var(--ink);font:15px/1.65 'Public Sans',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}
 a{color:inherit;text-decoration:none}
 .wrap{max-width:1180px;margin:0 auto;padding:0 22px}
 .topbar{background:var(--navy);color:var(--navy-mut);font-size:12.5px}
 .topbar .wrap{display:flex;justify-content:space-between;align-items:center;min-height:34px;gap:16px;flex-wrap:wrap}
 .topbar a{color:var(--navy-ink)}
 .kop-nav{background:var(--surface);border-bottom:1px solid var(--line)}
 .kop-nav .wrap{display:flex;align-items:center;gap:30px;min-height:70px;flex-wrap:wrap}
 .brand{display:flex;align-items:center;gap:12px;white-space:nowrap}
 .brand .mark{width:34px;height:34px;border-radius:6px;background:var(--navy);color:#fff;font-family:'Zilla Slab',serif;font-weight:700;font-size:20px;display:flex;align-items:center;justify-content:center}
 .brand .btxt{display:flex;flex-direction:column}
 .brand .naam{font-family:'Zilla Slab',serif;font-weight:700;font-size:22px;color:var(--ink);line-height:1.05}
 .brand .onder{font-size:11px;color:var(--mut);letter-spacing:.02em}
 .menu{display:flex;gap:24px;flex-wrap:wrap;margin-left:auto}
 .menu a{color:var(--mut);font-weight:600;font-size:14px;padding:6px 0;border-bottom:2px solid transparent}
 .menu a:hover{color:var(--ink)}
 .menu a.actief{color:var(--accent);border-bottom-color:var(--accent)}
 .beheerkop{background:var(--navy);color:var(--navy-ink)}
 .beheerkop .wrap{display:flex;align-items:center;min-height:60px}
 main{padding:30px 0 58px;min-height:56vh}
 .paginatitel{font-family:'Zilla Slab',serif;font-size:27px;font-weight:600;margin:0 0 4px;color:var(--ink)}
 .sub{color:var(--mut);margin:0 0 24px}
 .mut{color:var(--mut);font-size:14px}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(228px,1fr));gap:18px}
 .kaart{background:var(--surface);border:1px solid var(--line);border-radius:6px;overflow:hidden;display:flex;flex-direction:column;transition:border-color .12s ease}
 .kaart:hover{border-color:var(--accent)}
 .kaart .thumb{aspect-ratio:4/3;background:var(--soft);display:flex;align-items:center;justify-content:center;padding:16px}
 .kaart .thumb img{max-width:100%;max-height:100%;object-fit:contain}
 .kaart .info{padding:12px 14px 14px;display:flex;flex-direction:column;gap:4px;flex:1;border-top:1px solid var(--line)}
 .kaart .cat{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}
 .kaart .naam{font-weight:600;line-height:1.35;color:var(--ink)}
 .kaart .prijs{font-family:'Zilla Slab',serif;margin-top:auto;font-weight:700;font-size:19px;color:var(--accent)}
 .leeg{color:var(--mut);padding:44px 0}
 .kruimels{color:var(--mut);font-size:13px;margin:0 0 18px}
 .kruimels a:hover{color:var(--accent)}
 .product{display:grid;grid-template-columns:1.05fr 1fr;gap:44px;align-items:start;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:26px}
 @media(max-width:820px){.product{grid-template-columns:1fr;padding:18px}}
 .galerij .hoofd{aspect-ratio:4/3;background:var(--soft);border:1px solid var(--line);border-radius:6px;display:flex;align-items:center;justify-content:center;padding:22px}
 .galerij .hoofd img{max-width:100%;max-height:100%;object-fit:contain}
 .galerij .strip{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap}
 .galerij .strip img{width:64px;height:64px;object-fit:contain;background:var(--soft);border-radius:5px;border:1px solid var(--line);cursor:pointer;padding:6px}
 .galerij .strip img:hover,.galerij .strip img.actief{border-color:var(--accent)}
 .pkop{font-family:'Zilla Slab',serif;font-size:25px;font-weight:600;margin:0 0 10px;color:var(--ink)}
 .pmeta{color:var(--mut);font-size:14px;margin:0 0 16px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
 .badge{display:inline-block;font-size:12px;font-weight:600;padding:2px 10px;border-radius:4px;background:var(--soft);border:1px solid var(--line);color:var(--ink)}
 .pprijs{font-family:'Zilla Slab',serif;font-size:32px;font-weight:700;color:var(--accent);margin:0 0 20px}
 .pomschrijving{margin:0 0 22px}
 .cta{display:inline-block;background:var(--accent);color:var(--accent-ink);font-weight:600;padding:12px 24px;border-radius:6px}
 .cta:hover{background:var(--navy2)}
 .specs{margin-top:34px;border-top:1px solid var(--line);padding-top:24px}
 .specs h3{font-family:'Zilla Slab',serif;font-size:17px;font-weight:600;margin:0 0 14px}
 .specs table{max-width:680px}
 .specs th{color:var(--mut);width:210px;font-weight:600}
 footer{background:var(--navy);color:var(--navy-ink);margin-top:36px}
 footer .wrap{padding:40px 22px;display:flex;justify-content:space-between;gap:32px;flex-wrap:wrap}
 footer a{color:var(--navy-ink)}footer a:hover{color:#fff}
 footer .kop{font-family:'Zilla Slab',serif;font-weight:600;margin-bottom:12px;font-size:16px}
 footer .klein{color:var(--navy-mut);font-size:13px;line-height:1.7;max-width:300px}
 .flash{background:var(--soft);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:4px;padding:10px 14px;margin-bottom:16px}
 .btn{display:inline-block;background:var(--accent);color:var(--accent-ink);padding:9px 16px;border-radius:6px;border:0;cursor:pointer;font:inherit;font-weight:600}
 .btn.sec{background:transparent;color:var(--ink);border:1px solid var(--line)}
 table{border-collapse:collapse;width:100%}
 td,th{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
 input,select,textarea{font:inherit;padding:9px;border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--ink);width:100%}
 label{display:block;margin:10px 0 4px;font-size:14px;color:var(--mut)}
 .row{display:flex;gap:16px;flex-wrap:wrap}.row>*{flex:1;min-width:220px}
 .pill{display:inline-block;font-size:12px;padding:2px 8px;border-radius:4px;border:1px solid var(--line);color:var(--mut)}
 .gal{display:flex;gap:10px;flex-wrap:wrap}.gal img{width:120px;height:90px;object-fit:cover;border-radius:4px;border:1px solid var(--line)}
 .spinner{width:44px;height:44px;border:4px solid var(--line);border-top-color:var(--accent);border-radius:50%;animation:sp 1s linear infinite;margin:20px auto}@keyframes sp{to{transform:rotate(360deg)}}
</style></head><body>
{% if IS_BEHEER %}
<div class="beheerkop"><div class="wrap"><a class="brand" href="{{ url_for('beheer') }}"><span class="mark">T</span><span class="naam" style="color:var(--navy-ink)">{{ winkel_naam }}</span></a><span style="margin-left:12px;color:var(--navy-mut);font-size:13px">beheer</span></div></div>
{% else %}
<div class="topbar"><div class="wrap"><span>Tweedehands ICT, getest en klaar voor gebruik</span><span>Contact: <a href="mailto:{{ contact_email }}">{{ contact_email }}</a></span></div></div>
<div class="kop-nav"><div class="wrap">
  <a class="brand" href="{{ url_for('etalage') }}"><span class="mark">T</span><span class="btxt"><span class="naam">{{ winkel_naam }}</span><span class="onder">ICT-hardware</span></span></a>
  <nav class="menu">
    <a href="{{ url_for('etalage') }}" class="{{ 'actief' if actief=='home' else '' }}">Home</a>
    {% for c in categorieen %}<a href="{{ url_for('categorie', slug=c.slug) }}" class="{{ 'actief' if actief==c.slug else '' }}">{{ c.label }}</a>{% endfor %}
  </nav>
</div></div>
{% endif %}
<main><div class="wrap">
 {% with msgs = get_flashed_messages() %}{% for m in msgs %}<div class="flash">{{ m }}</div>{% endfor %}{% endwith %}
 {{ body|safe }}
</div></main>
{% if not IS_BEHEER %}
<footer><div class="wrap">
  <div><div class="kop">{{ winkel_naam }}</div><div class="klein">Tweedehands ICT-hardware, getest en klaar voor gebruik. Laptops, pc's, tablets en toebehoren.</div></div>
  <div><div class="kop">Categorie&euml;n</div>{% for c in categorieen %}<div style="margin:6px 0"><a href="{{ url_for('categorie', slug=c.slug) }}">{{ c.label }}</a></div>{% endfor %}</div>
  <div><div class="kop">Contact</div><div class="klein"><a href="mailto:{{ contact_email }}">{{ contact_email }}</a></div></div>
</div></footer>
{% endif %}
</body></html>
"""


def page(body, **kw):
    return render_template_string(BASE, body=body, **kw)


# ---------------------------------------------------------------------------
# Publieke etalage (beide rollen)
# ---------------------------------------------------------------------------
@app.route("/healthz")
def healthz():
    return "ok", 200


def _kaart(r):
    imgs = prod_images(r["id"])
    foto = url_for("upload", naam=imgs[0]["bestand"]) if imgs else ""
    naam = r["titel"] or ((r["merk"] or "") + " " + (r["model"] or "")).strip() or "Item"
    prijs = euro(r["prijs_definitief_cents"]) or "Prijs op aanvraag"
    catlabel = netjes_label(r["categorie"]) if r["categorie"] else ""
    thumb = (f'<img src="{foto}" alt="" loading="lazy">' if foto
             else '<span class="mut">geen foto</span>')
    return (f'<a class="kaart" href="{url_for("detail", pid=r["id"])}">'
            f'<div class="thumb">{thumb}</div>'
            f'<div class="info"><div class="cat">{catlabel}</div>'
            f'<div class="naam">{naam}</div><div class="prijs">{prijs}</div></div></a>')


def _etalage_html(slug, titel, sub):
    rows = db().execute("SELECT * FROM products WHERE status='live' "
                        "ORDER BY gepubliceerd_op DESC, id DESC").fetchall()
    if slug:
        rows = [r for r in rows if categorie_van(r["categorie"]) == slug]
    kaarten = "".join(_kaart(r) for r in rows)
    inner = (f'<div class="grid">{kaarten}</div>' if rows
             else '<p class="leeg">Nog geen items in deze categorie.</p>')
    return f'<h1 class="paginatitel">{titel}</h1><p class="sub">{sub}</p>{inner}'


@app.route("/")
def etalage():
    return page(_etalage_html(None, "Aanbod",
                              "Tweedehands ICT-hardware, nagekeken en klaar voor gebruik."),
                actief="home")


@app.route("/categorie/<slug>")
def categorie(slug):
    c = next((x for x in CATEGORIEEN if x["slug"] == slug), None)
    if not c:
        abort(404)
    return page(_etalage_html(slug, c["label"], "Ons aanbod " + c["label"].lower() + "."),
                actief=slug, titel=c["label"])


_GALERIJ_JS = """
<script>
document.querySelectorAll('.galerij .strip img').forEach(function(t){
  t.addEventListener('click', function(){
    document.getElementById('hoofdfoto').src = t.src;
    document.querySelectorAll('.galerij .strip img').forEach(function(x){ x.classList.remove('actief'); });
    t.classList.add('actief');
  });
});
</script>"""


@app.route("/item/<int:pid>")
def detail(pid):
    r = db().execute("SELECT * FROM products WHERE id=%s AND status='live'", (pid,)).fetchone()
    if not r:
        abort(404)
    imgs = prod_images(pid)
    hoofd = url_for("upload", naam=imgs[0]["bestand"]) if imgs else ""
    hoofd_html = (f'<img id="hoofdfoto" src="{hoofd}" alt="">' if hoofd
                  else '<span class="mut">geen foto</span>')
    strip = ""
    if len(imgs) > 1:
        thumbs = "".join(
            f'<img src="{url_for("upload", naam=i["bestand"])}" class="{"actief" if k == 0 else ""}">'
            for k, i in enumerate(imgs))
        strip = f'<div class="strip">{thumbs}</div>'

    specs = specs_dict(r["specs"])
    spec_rows = "".join(f"<tr><th>{netjes_label(k)}</th><td>{v}</td></tr>"
                        for k, v in specs.items())
    specs_html = (f'<div class="specs"><h3>Specificaties</h3><table>{spec_rows}</table></div>'
                  if spec_rows else "")

    titel = r["titel"] or ((r["merk"] or "") + " " + (r["model"] or "")).strip() or "Item"
    prijs = euro(r["prijs_definitief_cents"]) or "Prijs op aanvraag"
    catobj = next((x for x in CATEGORIEEN if x["slug"] == categorie_van(r["categorie"])), None)
    kruimel_cat = ""
    if catobj:
        kruimel_cat = (f'<a href="{url_for("categorie", slug=catobj["slug"])}">'
                       f'{catobj["label"]}</a> &rsaquo; ')

    meta = []
    mm = ((r["merk"] or "") + " " + (r["model"] or "")).strip()
    if mm:
        meta.append(mm)
    if r["conditie"]:
        meta.append(f'<span class="badge">{netjes_label(r["conditie"])}</span>')
    meta_html = " &middot; ".join(meta)

    onderwerp = quote("Interesse in " + titel)
    cta = (f'<a class="cta" href="mailto:{CONTACT_EMAIL}?subject={onderwerp}">'
           f'Interesse? Neem contact op</a>')
    oms = (r["omschrijving"] or "").replace(chr(10), "<br>")

    body = f"""
    <div class="kruimels"><a href="{url_for('etalage')}">Home</a> &rsaquo; {kruimel_cat}{titel}</div>
    <div class="product">
      <div class="galerij"><div class="hoofd">{hoofd_html}</div>{strip}</div>
      <div>
        <h1 class="pkop">{titel}</h1>
        <p class="pmeta">{meta_html}</p>
        <p class="pprijs">{prijs}</p>
        <div class="pomschrijving">{oms}</div>
        {cta}
      </div>
    </div>
    {specs_html}""" + _GALERIJ_JS
    return page(body, titel=titel)


@app.route("/uploads/<path:naam>")
def upload(naam):
    return send_from_directory(UPLOAD_DIR, naam)


# ---------------------------------------------------------------------------
# Beheerkant (alleen ROLE=beheer, achter forward-auth)
# ---------------------------------------------------------------------------
@app.route("/beheer")
@beheer_route
def beheer():
    rows = db().execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    trs = ""
    for r in rows:
        prijs = euro(r["prijs_definitief_cents"]) or euro(r["prijs_voorstel_cents"]) or "-"
        naam = r['titel'] or (r['merk'] or '') + ' ' + (r['model'] or '') or 'zonder titel'
        trs += (f"<tr><td>#{r['id']}</td>"
                f"<td><a href=\"{url_for('bewerk', pid=r['id'])}\">{naam}</a></td>"
                f"<td><span class=\"pill\">{r['status']}</span></td><td>{prijs}</td></tr>")
    body = f"""
    <div class="row" style="align-items:center">
      <h2 style="flex:2">Beheer</h2>
      <div style="text-align:right"><a class="btn" href="{url_for('nieuw')}">+ Nieuw item</a></div>
    </div>
    <p class="mut">Aangemeld als {_auth_gebruiker()}</p>
    <table><tr><th>Id</th><th>Titel</th><th>Status</th><th>Prijs</th></tr>{trs}</table>"""
    return page(body)


@app.route("/beheer/nieuw", methods=["GET", "POST"])
@beheer_route
def nieuw():
    if request.method == "POST":
        f = request.form
        d = db()
        pid = d.execute(
            """INSERT INTO products (merk, model, serienummer, ean, categorie,
                 conditie, conditie_notities, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'concept') RETURNING id""",
            (f.get("merk"), f.get("model"), f.get("serienummer"), f.get("ean"),
             f.get("categorie"), f.get("conditie"), f.get("conditie_notities")),
        ).fetchone()["id"]
        _bewaar_uploads(pid, request.files.getlist("fotos"))
        d.commit()
        flash("Item aangemaakt. Voeg gerust nog foto's toe en start de taxatie.")
        return redirect(url_for("bewerk", pid=pid))
    cond = "".join(f'<option value="{c}">{c}</option>' for c in CONDITIES)
    body = f"""
    <p><a href="{url_for('beheer')}">&larr; beheer</a></p>
    <h2>Nieuw item</h2>
    <form method="post" enctype="multipart/form-data">
      <div class="row">
        <div><label>Merk</label><input name="merk" placeholder="Dell, HP, Lenovo..."></div>
        <div><label>Model / typenummer</label><input name="model" placeholder="Latitude 7420"></div>
      </div>
      <div class="row">
        <div><label>Serienummer / service tag</label><input name="serienummer"></div>
        <div><label>EAN (optioneel)</label><input name="ean"></div>
      </div>
      <div class="row">
        <div><label>Categorie</label><input name="categorie" placeholder="laptop, server, monitor..."></div>
        <div><label>Conditie</label><select name="conditie">{cond}</select></div>
      </div>
      <label>Conditie-notities</label>
      <textarea name="conditie_notities" rows="2" placeholder="krasje op deksel, accu 85%..."></textarea>
      <label>Foto's (eigen foto's, meerdere mogelijk)</label>
      <input type="file" name="fotos" accept="image/*" multiple>
      <p><button class="btn">Aanmaken</button></p>
    </form>"""
    return page(body)


def _bewaar_uploads(pid, bestanden):
    d = db()
    n = d.execute("SELECT COUNT(*) AS c FROM product_images WHERE product_id=%s",
                  (pid,)).fetchone()["c"]
    for i, fs in enumerate(bestanden):
        if not fs or not fs.filename:
            continue
        ext = os.path.splitext(fs.filename)[1].lower() or ".jpg"
        naam = f"p{pid}_{secrets.token_hex(6)}{ext}"
        fs.save(os.path.join(UPLOAD_DIR, naam))
        d.execute(
            "INSERT INTO product_images (product_id, bestand, is_primair, volgorde) "
            "VALUES (%s,%s,%s,%s)", (pid, naam, (n == 0 and i == 0), n + i))


@app.route("/beheer/<int:pid>", methods=["GET", "POST"])
@beheer_route
def bewerk(pid):
    d = db()
    r = d.execute("SELECT * FROM products WHERE id=%s", (pid,)).fetchone()
    if not r:
        abort(404)

    if request.method == "POST":
        f = request.form
        d.execute(
            """UPDATE products SET merk=%s, model=%s, serienummer=%s, ean=%s, categorie=%s,
                 conditie=%s, conditie_notities=%s, titel=%s, omschrijving=%s, specs=%s,
                 bijgewerkt_op=now() WHERE id=%s""",
            (f.get("merk"), f.get("model"), f.get("serienummer"), f.get("ean"),
             f.get("categorie"), f.get("conditie"), f.get("conditie_notities"),
             f.get("titel"), f.get("omschrijving"), Json(tekst_naar_specs(f.get("specs"))), pid),
        )
        _bewaar_uploads(pid, request.files.getlist("fotos"))
        d.commit()
        flash("Opgeslagen.")
        return redirect(url_for("bewerk", pid=pid))

    imgs = prod_images(pid)
    gal = "".join(f'<img src="{url_for("upload", naam=i["bestand"])}" alt="">' for i in imgs)
    cond = "".join(f'<option value="{c}" {"selected" if c == r["conditie"] else ""}>{c}</option>'
                   for c in CONDITIES)
    specs_tekst = specs_naar_tekst(specs_dict(r["specs"]))

    v = d.execute("SELECT * FROM valuations WHERE product_id=%s ORDER BY id DESC LIMIT 1",
                  (pid,)).fetchone()
    tax_html = "<p class='mut'>Nog geen taxatie uitgevoerd.</p>"
    if v:
        bronnen = d.execute("SELECT * FROM valuation_sources WHERE valuation_id=%s",
                            (v["id"],)).fetchall()
        brows = ""
        for b in bronnen:
            link = f'<a href="{b["url"]}">link</a>' if b["url"] else ""
            brows += (f"<tr><td>{b['bron']}</td><td>{euro(b['prijs_cents']) or '-'}</td>"
                      f"<td>{b['type']}</td><td>{link}</td></tr>")
        tax_html = f"""
          <p><b>Voorstel:</b> {euro(v['prijs_voorstel_cents']) or '-'}
             (band {euro(v['prijs_min_cents']) or '?'} - {euro(v['prijs_max_cents']) or '?'})
             &middot; vertrouwen: <span class="pill">{v['vertrouwen']}</span></p>
          <p class="mut">API-kosten van deze taxatie: {usd_eur(v['kosten_usd'])}
             &middot; {v['input_tokens']} in / {v['output_tokens']} uit tokens
             &middot; {v['web_searches']} zoekopdrachten</p>
          <p class="mut">{(v['redenering'] or '')}</p>
          <table><tr><th>Bron</th><th>Prijs</th><th>Type</th><th></th></tr>{brows}</table>"""

    prijs_def = f"{r['prijs_definitief_cents']/100:.2f}" if r["prijs_definitief_cents"] else \
                (f"{r['prijs_voorstel_cents']/100:.2f}" if r["prijs_voorstel_cents"] else "")

    body = f"""
    <p><a href="{url_for('beheer')}">&larr; beheer</a> &middot; status <span class="pill">{r['status']}</span></p>
    <h2>Item #{pid} bewerken</h2>
    <div class="gal">{gal or '<span class="mut">geen foto</span>'}</div>

    <div class="row" style="margin:14px 0;align-items:center">
      <form method="post" action="{url_for('taxeer_route', pid=pid)}" style="flex:0">
        <input type="hidden" name="modus" value="specs">
        <button class="btn sec">Specs invullen (snel &amp; goedkoop)</button>
      </form>
      <form method="post" action="{url_for('taxeer_route', pid=pid)}" style="flex:0">
        <input type="hidden" name="modus" value="prijs">
        <button class="btn">Marktprijs bepalen (marktonderzoek, duurder)</button>
      </form>
    </div>
    <p class="mut">Specs invullen = identificatie + technische gegevens zonder web, kost centen
       en duurt seconden. Marktprijs = met marktonderzoek, duurt enkele minuten en is duurder.</p>

    <form method="post" enctype="multipart/form-data">
      <div class="row">
        <div><label>Merk</label><input name="merk" value="{r['merk'] or ''}"></div>
        <div><label>Model</label><input name="model" value="{r['model'] or ''}"></div>
      </div>
      <div class="row">
        <div><label>Serienummer</label><input name="serienummer" value="{r['serienummer'] or ''}"></div>
        <div><label>EAN</label><input name="ean" value="{r['ean'] or ''}"></div>
      </div>
      <div class="row">
        <div><label>Categorie</label><input name="categorie" value="{r['categorie'] or ''}"></div>
        <div><label>Conditie</label><select name="conditie">{cond}</select></div>
      </div>
      <label>Conditie-notities</label>
      <textarea name="conditie_notities" rows="2">{r['conditie_notities'] or ''}</textarea>
      <label>Publieke titel</label><input name="titel" value="{r['titel'] or ''}">
      <label>Publieke omschrijving</label>
      <textarea name="omschrijving" rows="4">{r['omschrijving'] or ''}</textarea>
      <label>Specificaties (een per regel, "sleutel: waarde") - automatisch ingevuld door de taxatie</label>
      <textarea name="specs" rows="8">{specs_tekst}</textarea>
      <label>Extra foto's toevoegen</label>
      <input type="file" name="fotos" accept="image/*" multiple>
      <p><button class="btn">Opslaan</button></p>
    </form>

    <hr style="border:0;border-top:1px solid var(--lijn);margin:24px 0">
    <h3>Laatste taxatie</h3>
    {tax_html}

    <hr style="border:0;border-top:1px solid var(--lijn);margin:24px 0">
    <h3>Prijs goedkeuren en publiceren</h3>
    <form method="post" action="{url_for('goedkeuren', pid=pid)}">
      <div class="row" style="align-items:end">
        <div><label>Definitieve prijs (EUR)</label>
          <input name="prijs" type="number" step="0.01" value="{prijs_def}"></div>
        <div><label>Door</label><input name="door" value="{_auth_gebruiker()}"></div>
        <div style="max-width:220px"><button class="btn">Goedkeuren &amp; live</button></div>
      </div>
    </form>
    <form method="post" action="{url_for('status_route', pid=pid)}" style="margin-top:12px">
      <div class="row" style="align-items:end">
        <div><label>Status handmatig</label><select name="status">
          {''.join(f'<option value="{s}" {"selected" if s==r["status"] else ""}>{s}</option>' for s in STATUSSEN)}
        </select></div>
        <div style="max-width:160px"><button class="btn sec">Zet status</button></div>
      </div>
    </form>"""
    return page(body, titel=f"Item #{pid}")


VOORTGANG_HTML = """
<p><a href="{{ url_for('beheer') }}">&larr; beheer</a></p>
<h2>Taxatie loopt voor item #{{ pid }}</h2>
<div class="spinner" id="spin"></div>
<p style="text-align:center"><b id="fase">Starten...</b></p>
<p style="text-align:center" class="mut">verstreken: <span id="tijd">0</span> s</p>
<p style="text-align:center" class="mut">Dit kan een halve tot enkele minuten duren; je hoeft niets te doen.</p>
<div class="flash" id="fout" style="display:none;border-color:#c0392b"></div>
<script>
const pid = {{ pid }};
async function poll(){
  try{
    const r = await fetch('/beheer/'+pid+'/taxeer/status', {cache:'no-store'});
    const j = await r.json();
    document.getElementById('fase').textContent = j.fase || j.status || '...';
    document.getElementById('tijd').textContent = j.verstreken || 0;
    if(j.status === 'klaar'){ window.location = '/beheer/'+pid; return; }
    if(j.status === 'fout'){
      document.getElementById('spin').style.display = 'none';
      const el = document.getElementById('fout');
      el.textContent = 'Taxatie mislukt: ' + (j.error || 'onbekende fout');
      el.style.display = 'block';
      return;
    }
  }catch(e){}
  setTimeout(poll, 1500);
}
poll();
</script>
"""


@app.route("/beheer/<int:pid>/taxeer", methods=["POST"])
@beheer_route
def taxeer_route(pid):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        flash("ANTHROPIC_API_KEY ontbreekt in de omgeving; taxatie niet mogelijk.")
        return redirect(url_for("bewerk", pid=pid))
    if not db().execute("SELECT id FROM products WHERE id=%s", (pid,)).fetchone():
        abort(404)
    if _job_get(pid).get("status") == "bezig":
        return redirect(url_for("voortgang", pid=pid))
    modus = request.form.get("modus", "prijs")
    db().execute("UPDATE products SET status='onderzoek' WHERE id=%s", (pid,))
    db().commit()
    _job(pid, status="bezig", fase="Starten...", start=time.time(), error=None)
    threading.Thread(target=_taxatie_worker, args=(pid, modus), daemon=True).start()
    return redirect(url_for("voortgang", pid=pid))


@app.route("/beheer/<int:pid>/taxeer/voortgang")
@beheer_route
def voortgang(pid):
    return page(render_template_string(VOORTGANG_HTML, pid=pid), titel="Taxatie loopt")


@app.route("/beheer/<int:pid>/taxeer/status")
@beheer_route
def taxeer_status(pid):
    j = _job_get(pid)
    if j.get("start"):
        j["verstreken"] = round(time.time() - j["start"])
    return app.response_class(json.dumps(j), mimetype="application/json")


@app.route("/beheer/<int:pid>/goedkeuren", methods=["POST"])
@beheer_route
def goedkeuren(pid):
    cents = _eur_to_cents(request.form.get("prijs"))
    if cents is None:
        flash("Geen geldige prijs.")
        return redirect(url_for("bewerk", pid=pid))
    db().execute(
        """UPDATE products SET prijs_definitief_cents=%s, goedgekeurd_door=%s,
             goedgekeurd_op=now(), gepubliceerd_op=now(),
             status='live', bijgewerkt_op=now() WHERE id=%s""",
        (cents, request.form.get("door") or _auth_gebruiker(), pid))
    db().commit()
    flash("Goedgekeurd en live gezet.")
    return redirect(url_for("bewerk", pid=pid))


@app.route("/beheer/<int:pid>/status", methods=["POST"])
@beheer_route
def status_route(pid):
    s = request.form.get("status")
    if s in STATUSSEN:
        db().execute("UPDATE products SET status=%s, bijgewerkt_op=now() WHERE id=%s", (s, pid))
        db().commit()
        flash(f"Status gezet op {s}.")
    return redirect(url_for("bewerk", pid=pid))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)

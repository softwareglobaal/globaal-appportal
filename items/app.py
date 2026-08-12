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
import re
import json
import time
import base64
import secrets
import threading
import mimetypes
import urllib.request
from functools import wraps
from urllib.parse import quote, urlencode

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
# Let op: compose geeft niet-ingevulde variabelen door als lege string, dus hier
# `or` gebruiken en niet de default van os.environ.get; die slaat dan niet aan.
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL") or "info@angela.sr"
# Placeholder tot het echte nummer bekend is; zet CONTACT_TELEFOON in .env.
CONTACT_TELEFOON = os.environ.get("CONTACT_TELEFOON") or "+32 000 00 00 00"
WINKEL_NAAM = os.environ.get("WINKEL_NAAM") or "angela.sr"

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
app.jinja_env.globals["contact_telefoon"] = CONTACT_TELEFOON
app.jinja_env.globals["telefoon_link"] = "tel:" + re.sub(r"[^\d+]", "", CONTACT_TELEFOON)
app.jinja_env.globals["winkel_naam"] = WINKEL_NAAM
# Logo-letter in de ronde merk-tegel volgt de winkelnaam.
app.jinja_env.globals["winkel_letter"] = WINKEL_NAAM[:1].upper()

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


# Vaste hardware-categorieen: die staan altijd in het menu, ook als er even niets
# in ligt. Een product hoort erbij als zijn (vrije-tekst) categorie een sleutel bevat.
# Alles wat hier niet in past krijgt automatisch een eigen categorie, zie
# actieve_categorieen(); zo valt een nieuw soort product nooit buiten het menu.
BASIS_CATEGORIEEN = [
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


def _slug(tekst):
    s = re.sub(r"[^a-z0-9]+", "-", (tekst or "").lower().strip()).strip("-")
    return s or "overig"


def categorie_van(cat):
    """Slug van de categorie waar dit item bij hoort, of None als het veld leeg is."""
    t = (cat or "").strip().lower()
    if not t:
        return None
    for c in BASIS_CATEGORIEEN:
        if any(s in t for s in c["sleutels"]):
            return c["slug"]
    return _slug(t)


def actieve_categorieen():
    """De vaste categorieen plus alles wat verder in de etalage voorkomt.

    Zet iemand (of de taxatie) een nieuw soort product neer, bijvoorbeeld een
    toetsenbord, dan verschijnt dat vanzelf in het menu met een eigen pagina.
    """
    uit = {c["slug"]: dict(c, icoon=CATEGORIE_ICONEN.get(c["slug"], STANDAARD_ICOON))
           for c in BASIS_CATEGORIEEN}
    try:
        rijen = db().execute(
            "SELECT DISTINCT categorie FROM products "
            "WHERE status='live' AND categorie IS NOT NULL AND btrim(categorie) <> ''"
        ).fetchall()
    except Exception:  # noqa: BLE001 - zonder database tonen we gewoon de vaste lijst
        return list(uit.values())
    for rij in rijen:
        slug = categorie_van(rij["categorie"])
        if slug and slug not in uit:
            uit[slug] = {"slug": slug, "label": netjes_label(rij["categorie"]),
                         "sleutels": [], "icoon": STANDAARD_ICOON}
    return list(uit.values())


@app.context_processor
def _categorieen_in_sjabloon():
    return {"categorieen": actieve_categorieen()}


CATEGORIE_ICONEN = {
    "laptops": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="10" rx="1"/><path d="M2 19h20"/></svg>',
    "tablets": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="3" width="12" height="18" rx="2"/><path d="M11 18h2"/></svg>',
    "pcs": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="12" rx="1"/><path d="M8 20h8M12 16v4"/></svg>',
    "kabels": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 2v5M15 2v5M7 7h10v3a5 5 0 0 1-10 0zM12 15v7"/></svg>',
}

# Voor categorieen die vanzelf ontstaan en dus geen eigen tekening hebben.
STANDAARD_ICOON = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                   'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
                   '<rect x="3" y="3" width="18" height="18" rx="2"/>'
                   '<path d="M3 9h18M9 21V9"/></svg>')


def foto_placeholder(categorie, klein=False):
    """Nette plaatshouder als een item nog geen eigen foto heeft."""
    icoon = CATEGORIE_ICONEN.get(categorie_van(categorie), STANDAARD_ICOON)
    maat = "38px" if klein else "64px"
    return (f'<div class="geenfoto"><span style="width:{maat};height:{maat};display:block">'
            f'{icoon}</span><span class="lbl">Foto volgt</span></div>')




CONDITIE_LABEL = {
    "nieuw": "Nieuw",
    "als_nieuw": "Als nieuw",
    "goed": "Goede staat",
    "gebruikt": "Gebruikt",
    "defect_onderdelen": "Voor onderdelen",
}


def conditie_label(conditie):
    return CONDITIE_LABEL.get(conditie or "", "")


USP_ICONEN = [
    ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
     "Getest voor het online gaat", "We zetten het toestel aan en kijken het na"),
    ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>',
     "Eigen foto's", "Krassen en deuken zie je vooraf"),
    ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="10" r="3"/><path d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11z"/></svg>',
     "Afhalen op afspraak", "Bel of mail, dan spreken we iets af"),
]


def usps_html():
    items = "".join(
        f'<div class="usp">{svg}<div><b>{kop}</b><span>{tekst}</span></div></div>'
        for svg, kop, tekst in USP_ICONEN)
    return f'<div class="usps">{items}</div>'


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
    # Eigen foto's van het echte toestel altijd eerst, dan pas fabrikantsbeeld.
    return con.execute(
        "SELECT * FROM product_images WHERE product_id=%s "
        "ORDER BY (bron = 'fabrikant'), is_primair DESC, volgorde, id", (pid,)).fetchall()


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


def taxeer(product, image_paden, voortgang=None, met_marktonderzoek=True,
           bekende_categorieen=None):
    import anthropic

    client = anthropic.Anthropic()
    tot = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "web": 0}

    # Bestaande categorieen meegeven zodat er geen varianten ontstaan
    # (toetsenbord naast toetsenborden naast keyboard).
    lijst = ", ".join(bekende_categorieen or []) or "laptop, tablet, pc, kabel"
    categorie_regel = (
        f"\nGebruik voor categorie bij voorkeur een van deze bestaande waarden: {lijst}. "
        f"Past het item daar echt niet bij, kies dan zelf een korte categorienaam "
        f"in het enkelvoud en in het Nederlands.\n")

    if met_marktonderzoek:
        system = SYSTEM_PROMPT_BASE + categorie_regel + SYSTEM_PROMPT_MARKT
        tools = [WEB_SEARCH, TAXATIE_TOOL]
        max_rondes = 6
    else:
        system = SYSTEM_PROMPT_BASE + categorie_regel + SYSTEM_PROMPT_SPECS
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


def _aantal_uit(waarde, standaard=1):
    """Aantal uit een formulierveld; nooit negatief, leeg valt terug op de standaard."""
    try:
        return max(0, int(str(waarde).strip()))
    except (TypeError, ValueError):
        return standaard


# ---------------------------------------------------------------------------
# Fabrikantsfoto's via de productcatalogus van Icecat
# ---------------------------------------------------------------------------
# Zonder eigen account werkt de gedeelde demo-gebruiker; zet ICECAT_USER in .env
# zodra er een eigen Open Icecat-account is (dat hoort bij hun voorwaarden).
ICECAT_USER = os.environ.get("ICECAT_USER") or "openIcecat-live"
ICECAT_API = "https://live.icecat.biz/api"
MAX_FABRIKANTSFOTOS = int(os.environ.get("MAX_FABRIKANTSFOTOS") or "4")


def _mpn_kandidaten(product, specs):
    """Mogelijke fabrikantsnummers, van meest naar minst betrouwbaar.

    Het model bevat vaak iets als "ProBook 450 G7 (ProdID 8VU80EA#ABH)"; het
    stuk achter het hekje is de landvariant en die kent de catalogus niet.
    """
    uit = []

    def voeg_toe(waarde):
        waarde = (waarde or "").split("#")[0].strip()
        if waarde and any(t.isdigit() for t in waarde) and waarde not in uit:
            uit.append(waarde)

    for ruw in (specs.get("product_id"), specs.get("productid"), specs.get("mpn"),
                specs.get("partnummer"), product.get("model")):
        if not ruw:
            continue
        tekst = str(ruw).strip()
        # Eerst de hele waarde: fabrikantsnummers bevatten vaak streepjes (920-007931).
        if len(tekst) <= 20 and " " not in tekst:
            voeg_toe(tekst.upper())
        for kandidaat in re.findall(r"\b[0-9A-Z]{3,}(?:-[0-9A-Z]{2,})*(?:#[A-Z0-9]{2,4})?\b",
                                    tekst.upper()):
            voeg_toe(kandidaat)
    model = (product.get("model") or "").split("(")[0].strip()
    if model and model not in uit:
        uit.append(model)
    return uit


def _icecat_vraag(params):
    q = dict(params)
    q.update({"UserName": ICECAT_USER, "Language": "nl",
              "Content": "Gallery,Image,GeneralInfo"})
    url = ICECAT_API + "?" + urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "angela.sr/1.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode())
    if data.get("msg") != "OK" or not data.get("data"):
        return None
    d = data["data"]
    beelden = [g.get("Pic") for g in (d.get("Gallery") or []) if g.get("Pic")]
    hoofd = (d.get("Image") or {}).get("HighPic")
    if hoofd and hoofd not in beelden:
        beelden.insert(0, hoofd)
    if not beelden:
        return None
    return {"titel": (d.get("GeneralInfo") or {}).get("Title") or "",
            "beelden": beelden, "bron_url": url}


def zoek_fabrikantsfotos(product, specs):
    """Zoekt de officiele productfoto's; None als er niets gevonden wordt."""
    ean = (product.get("ean") or "").strip()
    if ean:
        try:
            gevonden = _icecat_vraag({"GTIN": ean})
            if gevonden:
                return gevonden
        except Exception:  # noqa: BLE001 - onbekende EAN geeft gewoon een foutcode
            pass
    merk = (product.get("merk") or "").strip()
    for mpn in _mpn_kandidaten(product, specs)[:4]:
        try:
            gevonden = _icecat_vraag({"Brand": merk, "ProductCode": mpn})
            if gevonden:
                return gevonden
        except Exception:  # noqa: BLE001
            continue
    return None


def _bewaar_fabrikantsfoto(pid, url, volgnr):
    """Haalt een afbeelding op, verkleint hem en zet hem bij het item."""
    req = urllib.request.Request(url, headers={"User-Agent": "angela.sr/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        ruw = resp.read()
    naam = f"p{pid}_fab_{secrets.token_hex(5)}.jpg"
    pad = os.path.join(UPLOAD_DIR, naam)
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(ruw)).convert("RGB")
        img.thumbnail((1400, 1400))
        img.save(pad, "JPEG", quality=82, optimize=True)
    except Exception:  # noqa: BLE001 - dan maar het origineel
        with open(pad, "wb") as fh:
            fh.write(ruw)
    db().execute(
        "INSERT INTO product_images (product_id, bestand, is_primair, volgorde, bron, bron_url) "
        "VALUES (%s,%s,false,%s,'fabrikant',%s)", (pid, naam, 100 + volgnr, url))
    return naam


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
        # Wat er al aan categorieen bestaat, zodat het model hergebruikt in plaats
        # van varianten te verzinnen. Deze thread heeft een eigen verbinding.
        bekend = sorted({c["label"] for c in BASIS_CATEGORIEEN} | {
            rij["categorie"].strip() for rij in con.execute(
                "SELECT DISTINCT categorie FROM products "
                "WHERE categorie IS NOT NULL AND btrim(categorie) <> ''").fetchall()})
        _job(pid, fase="Foto's en gegevens naar Claude sturen...")
        resultaat, kosten = taxeer(dict(r), paden, voortgang=lambda f: _job(pid, fase=f),
                                   met_marktonderzoek=(modus == "prijs"),
                                   bekende_categorieen=bekend)
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
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400..700&display=swap" rel="stylesheet">
<style>
 :root{--bg:#ffffff;--page:#f4f5f7;--surface:#ffffff;--soft:#f0f2f5;--ink:#15171c;--mut:#5a6068;--line:#e2e5ea;--navy:#151a2e;--navy2:#232a45;--navy-ink:#f4f5f7;--navy-mut:#a6adc2;--accent:#f05a1e;--accent-donker:#d2470f;--accent-ink:#ffffff;--accent-soft:#fff0e9;--blauw:#1f6feb;--blauw-zacht:#e8f0fe;--groen:#12a150;--groen-zacht:#e6f6ed;--paars:#7b3fe4;--paars-zacht:#f1eafe;--amber:#e8930c;--amber-zacht:#fdf3e0;--rood:#d92d20}
 @media(prefers-color-scheme:dark){:root{--bg:#0f1116;--page:#0b0d11;--surface:#161920;--soft:#1c2029;--ink:#e9ebef;--mut:#98a0ad;--line:#272c36;--navy:#0a0c12;--navy2:#1b2133;--navy-ink:#e9ebef;--navy-mut:#98a0ad;--accent:#ff7038;--accent-donker:#f05a1e;--accent-ink:#1a0c05;--accent-soft:#2a1a12;--blauw:#5b9bff;--blauw-zacht:#152238;--groen:#35c977;--groen-zacht:#122a1e;--paars:#a476f5;--paars-zacht:#211a35;--amber:#f5ad33;--amber-zacht:#2c2211;--rood:#f2635a}}
 *{box-sizing:border-box}html,body{margin:0}
 body{background:var(--page);color:var(--ink);font:15px/1.6 'Archivo',system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}
 a{color:inherit;text-decoration:none}
 .wrap{max-width:1660px;margin:0 auto;padding:0 32px}
 @media(max-width:700px){.wrap{padding:0 16px}}
 .kop{position:sticky;top:0;z-index:40;box-shadow:0 1px 0 var(--line)}
 .kop-nav{background:var(--surface);border-bottom:1px solid var(--line)}
 .kop-nav .wrap{display:flex;align-items:center;gap:26px;min-height:74px;flex-wrap:wrap}
 .zoek{flex:1;min-width:220px;max-width:640px;display:flex}
 .zoek input{border:2px solid var(--accent);border-right:0;border-radius:8px 0 0 8px;height:44px;padding:0 14px;font-size:15px}
 .zoek input:focus{outline:0}
 .zoek button{border:0;background:var(--accent);color:#fff;height:44px;padding:0 20px;border-radius:0 8px 8px 0;cursor:pointer;font-weight:700;display:flex;align-items:center;gap:8px}
 .zoek button:hover{background:var(--accent-donker)}
 .zoek svg{width:18px;height:18px}
 .koptel{display:flex;align-items:center;gap:11px;color:var(--mut);font-size:12.5px;white-space:nowrap}
 .koptel svg{width:26px;height:26px;color:var(--accent)}
 .koptel b{display:block;color:var(--ink);font-size:16px;font-weight:700;letter-spacing:-.01em}
 .koptel:hover b{color:var(--accent)}
 .menubalk{background:var(--navy2)}
 .menubalk .wrap{display:flex;gap:4px;flex-wrap:wrap;align-items:center}
 @media(max-width:820px){
   .kop-nav .wrap{min-height:0;padding-top:12px;padding-bottom:12px;gap:12px}
   .koptel{display:none}
   .dropdown{position:static;display:contents}
   .dropdown .trigger{display:none}
   .dropmenu{display:flex;position:static;min-width:0;background:none;border:0;
     box-shadow:none;padding:0;border-radius:0}
   .dropmenu a{color:#d7dcea;padding:11px 13px;font-weight:700;background:none}
   .dropmenu a svg{display:none}
   .dropmenu a.actief{background:var(--accent);color:#fff}
   .brand .mark{width:32px;height:32px;font-size:17px}
   .brand .naam{font-size:18px}
   .zoek{max-width:none}
   .zoek input,.zoek button{height:40px}
   .zoek button{padding:0 14px}
   .zoek button span{display:none}
   .menubalk .wrap{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none}
   .menubalk .wrap::-webkit-scrollbar{display:none}
   .menu{flex-wrap:nowrap}
   .menu a{white-space:nowrap;padding:11px 13px}
 }
 .brand{display:flex;align-items:center;gap:12px;white-space:nowrap}
 .brand .mark{width:38px;height:38px;border-radius:50%;background:var(--accent);color:#fff;font-weight:700;font-size:19px;display:flex;align-items:center;justify-content:center}
 .brand .btxt{display:flex;flex-direction:column}
 .brand .naam{font-weight:700;font-size:21px;color:var(--ink);line-height:1.05;letter-spacing:-.01em}
 .brand .onder{font-size:11px;color:var(--mut);letter-spacing:.02em}
 .menu{display:flex;gap:2px;flex-wrap:wrap}
 .menu a{color:#d7dcea;font-weight:700;font-size:14px;padding:13px 16px;border-radius:6px 6px 0 0;display:flex;align-items:center;gap:7px}
 .menu a svg{width:16px;height:16px}
 .menu a:hover{background:rgba(255,255,255,.09);color:#fff}
 .menu a.actief{background:var(--accent);color:#fff}
 .dropdown{position:relative;display:flex}
 .dropdown .pijl{width:14px;height:14px;transition:transform .12s ease}
 .dropdown:hover .pijl{transform:rotate(180deg)}
 .dropmenu{position:absolute;top:100%;left:0;min-width:236px;background:var(--surface);
   border:1px solid var(--line);border-top:3px solid var(--accent);border-radius:0 0 10px 10px;
   box-shadow:0 14px 34px rgba(20,23,28,.18);padding:7px;display:none;z-index:60}
 .dropdown:hover .dropmenu,.dropdown:focus-within .dropmenu{display:block}
 .dropmenu a{display:flex;align-items:center;gap:11px;padding:11px 12px;border-radius:7px;
   color:var(--ink);font-weight:700;font-size:14px}
 .dropmenu a svg{width:20px;height:20px;color:var(--accent)}
 .dropmenu a:hover{background:var(--soft);color:var(--accent)}
 .dropmenu a.actief{background:var(--accent-soft);color:var(--accent)}
 .beheerkop{background:var(--navy);color:var(--navy-ink)}
 .beheerkop .wrap{display:flex;align-items:center;min-height:60px}
 main{padding:30px 0 58px;min-height:56vh}
 .usps{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:2px;background:var(--accent-donker);border-radius:12px;overflow:hidden;margin:0 0 34px}
 .usp{background:var(--accent);color:#fff;padding:17px 20px;display:flex;align-items:center;gap:13px}
 .usp svg{width:25px;height:25px;flex:none}
 .usp b{display:block;font-size:15px;line-height:1.25}
 .usp span{font-size:13px;opacity:.92}
 .hero{position:relative;border-radius:12px;overflow:hidden;margin:0 0 34px;background:var(--navy);min-height:300px;display:flex;align-items:center}
 .hero img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.42}
 .hero .htxt{position:relative;padding:44px 40px;max-width:620px;color:#fff}
 .hero h1{font-size:34px;font-weight:700;line-height:1.2;margin:0 0 12px;letter-spacing:-.02em}
 .hero p{font-size:16px;line-height:1.6;margin:0 0 22px;color:#e8e6e8}
 .hero .cta{background:var(--accent);color:#fff}
 .hero .cta:hover{background:#fff;color:var(--navy)}
 @media(max-width:640px){.hero h1{font-size:26px}.hero .htxt{padding:30px 24px}}
 .sfeer{display:grid;grid-template-columns:1fr 1fr;gap:32px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:12px;overflow:hidden;margin:40px 0 0}
 .sfeer img{width:100%;height:100%;min-height:260px;object-fit:cover;display:block}
 .sfeer .stxt{padding:32px 34px 32px 0}
 .sfeer h2{font-size:21px;font-weight:700;margin:0 0 10px;letter-spacing:-.01em}
 .sfeer p{color:var(--mut);margin:0 0 16px}
 .sfeer ul{margin:0;padding-left:18px;color:var(--mut)}
 .sfeer li{margin:5px 0}
 @media(max-width:760px){.sfeer{grid-template-columns:1fr}.sfeer .stxt{padding:24px}}
 .geenfoto{display:flex;flex-direction:column;align-items:center;gap:10px;color:var(--line)}
 .geenfoto svg{width:100%;height:100%;stroke-width:1.2}
 .geenfoto .lbl{font-size:12px;color:var(--mut);letter-spacing:.02em}
 .paginatitel{font-size:24px;font-weight:700;margin:0 0 4px;color:var(--ink);letter-spacing:-.01em}
 .sub{color:var(--mut);margin:0 0 22px}
 .mut{color:var(--mut);font-size:14px}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(224px,1fr));gap:18px}
 .kaart{background:var(--surface);border:1px solid var(--line);border-radius:8px;overflow:hidden;display:flex;flex-direction:column;transition:border-color .12s ease}
 .kaart:hover{border-color:var(--accent)}
 .kaart .thumb{aspect-ratio:1/1;background:#fff;display:flex;align-items:center;justify-content:center;padding:18px}
 .kaart .thumb img{max-width:100%;max-height:100%;object-fit:contain}
 .kaart .info{padding:12px 14px 15px;display:flex;flex-direction:column;gap:5px;flex:1;border-top:1px solid var(--line)}
 .kaart .cat{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}
 .kaart .naam{font-weight:400;line-height:1.4;color:var(--ink)}
 .kaart .prijs{margin-top:auto;font-weight:700;font-size:21px;color:var(--accent);letter-spacing:-.01em}
 .kaart .thumb{position:relative}
 .lijstkop{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap}
 .lijst{display:flex;flex-direction:column;gap:12px}
 .rij{display:grid;grid-template-columns:150px minmax(0,1fr) 230px;gap:24px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 20px;transition:border-color .12s,box-shadow .12s}
 .rij:hover{border-color:var(--accent);box-shadow:0 2px 14px rgba(240,90,30,.10)}
 .rij .rfoto{width:150px;height:118px;background:#fff;border:1px solid var(--line);border-radius:8px;display:flex;align-items:center;justify-content:center;padding:8px;position:relative}
 .rij .rfoto img{max-width:100%;max-height:100%;object-fit:contain}
 .rij .rcat{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px}
 .rij .rnaam{font-size:18px;font-weight:700;line-height:1.3;color:var(--ink);margin-bottom:8px}
 .rij .rspecs{display:flex;flex-wrap:wrap;gap:7px;margin-top:9px}
 .rij .spec{background:var(--soft);border-radius:5px;padding:3px 9px;font-size:12.5px;color:var(--mut)}
 .rij .spec b{color:var(--ink);font-weight:700}
 .rij .rrechts{text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:10px}
 .rij .rprijs{font-size:26px;font-weight:700;color:var(--accent);letter-spacing:-.02em;line-height:1}
 .rij .rknop{background:var(--accent);color:#fff;font-weight:700;padding:10px 20px;border-radius:7px;font-size:14px}
 .rij:hover .rknop{background:var(--accent-donker)}
 @media(max-width:900px){.rij{grid-template-columns:110px minmax(0,1fr);gap:16px}
   .rij .rfoto{width:110px;height:88px}
   .rij .rrechts{grid-column:1/-1;flex-direction:row;justify-content:space-between;align-items:center;text-align:left;border-top:1px solid var(--line);padding-top:12px}}
 .leeg{color:var(--mut);padding:44px 0}
 .kruimels{color:var(--mut);font-size:13px;margin:0 0 18px}
 .kruimels a:hover{color:var(--accent)}
 .product{display:grid;grid-template-columns:1.05fr 1fr;gap:44px;align-items:start;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:26px}
 @media(max-width:820px){.product{grid-template-columns:1fr;padding:18px}}
 .galerij .hoofd{aspect-ratio:1/1;background:#fff;border:1px solid var(--line);border-radius:8px;display:flex;align-items:center;justify-content:center;padding:24px}
 .galerij .hoofd img{max-width:100%;max-height:100%;object-fit:contain}
 .galerij .strip{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap}
 .galerij .strip img{width:64px;height:64px;object-fit:contain;background:#fff;border-radius:6px;border:1px solid var(--line);cursor:pointer;padding:6px}
 .galerij .strip img:hover,.galerij .strip img.actief{border-color:var(--accent)}
 .pkop{font-size:24px;font-weight:700;margin:0 0 10px;color:var(--ink);letter-spacing:-.01em}
 .pmeta{color:var(--mut);font-size:14px;margin:0 0 16px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
 .badge{display:inline-block;font-size:12px;font-weight:700;padding:2px 10px;border-radius:4px;background:var(--accent-soft);border:1px solid var(--accent);color:var(--accent)}
 .pprijs{font-size:34px;font-weight:700;color:var(--accent);margin:0 0 20px;letter-spacing:-.02em}
 .pomschrijving{margin:0 0 22px}
 .cta{display:inline-block;background:var(--accent);color:var(--accent-ink);font-weight:700;padding:12px 24px;border-radius:6px}
 .cta:hover{background:var(--navy2)}
 .specs{margin-top:34px;border-top:1px solid var(--line);padding-top:24px}
 .specs h3{font-size:17px;font-weight:700;margin:0 0 14px}
 .specs table{max-width:680px}
 .specs th{color:var(--mut);width:210px;font-weight:700}
 footer{background:var(--navy);color:var(--navy-ink);margin-top:44px}
 footer .kolommen{padding:46px 0 34px;display:grid;grid-template-columns:1.7fr 1fr 1.4fr;gap:46px}
 @media(max-width:900px){footer .kolommen{grid-template-columns:1fr 1fr;gap:28px}}
 @media(max-width:560px){footer .kolommen{grid-template-columns:1fr}}
 footer a{color:var(--navy-mut)}footer a:hover{color:#fff}
 footer .kop{font-weight:700;margin-bottom:14px;font-size:15px;color:#fff}
 footer .klein{color:var(--navy-mut);font-size:13.5px;line-height:1.75}
 footer li{list-style:none;margin:7px 0}
 footer ul{margin:0;padding:0}
 footer .fmerk{display:flex;align-items:center;gap:11px;margin-bottom:14px}
 footer .fmerk .mark{width:36px;height:36px;border-radius:50%;background:var(--accent);color:#fff;font-weight:700;display:flex;align-items:center;justify-content:center;font-size:18px}
 footer .fmerk span{font-weight:700;font-size:19px;color:#fff}
 footer .fcontact{display:flex;align-items:flex-start;gap:10px;margin:9px 0;font-size:13.5px}
 footer .fcontact svg{width:17px;height:17px;color:var(--accent);flex:none;margin-top:3px}
 .fbalk{border-top:1px solid rgba(255,255,255,.11)}
 .fbalk .wrap{padding:16px 32px;display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;font-size:12.5px;color:var(--navy-mut)}
 .flash{background:var(--soft);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:4px;padding:10px 14px;margin-bottom:16px}
 .btn{display:inline-block;background:var(--accent);color:var(--accent-ink);padding:9px 16px;border-radius:6px;border:0;cursor:pointer;font:inherit;font-weight:700}
 .btn.sec{background:transparent;color:var(--ink);border:1px solid var(--line)}
 table{border-collapse:collapse;width:100%}
 td,th{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
 input,select,textarea{font:inherit;padding:9px;border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--ink);width:100%}
 label{display:block;margin:10px 0 4px;font-size:14px;color:var(--mut)}
 .row{display:flex;gap:16px;flex-wrap:wrap}.row>*{flex:1;min-width:220px}
 .pill{display:inline-block;font-size:12px;padding:2px 8px;border-radius:4px;border:1px solid var(--line);color:var(--mut)}
 .gal{display:flex;gap:12px;flex-wrap:wrap}
 .fotokaart{margin:0;display:flex;flex-direction:column;gap:5px;align-items:center}
 .fotokaart img{width:120px;height:90px;object-fit:contain;background:#fff;border-radius:4px;border:1px solid var(--line)}
 .fotokaart figcaption{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}
 .fotokaart button{font:inherit;font-size:11px;background:none;border:0;color:var(--accent);cursor:pointer;padding:0}
 .fotobron{font-size:12px;color:var(--mut);margin-top:8px}
 .spinner{width:44px;height:44px;border:4px solid var(--line);border-top-color:var(--accent);border-radius:50%;animation:sp 1s linear infinite;margin:20px auto}@keyframes sp{to{transform:rotate(360deg)}}
</style></head><body>
{% if IS_BEHEER %}
<div class="beheerkop"><div class="wrap"><a class="brand" href="{{ url_for('beheer') }}"><span class="mark">{{ winkel_letter }}</span><span class="naam" style="color:var(--navy-ink)">{{ winkel_naam }}</span></a><span style="margin-left:12px;color:var(--navy-mut);font-size:13px">beheer</span></div></div>
{% else %}
<div class="kop">
 <div class="kop-nav"><div class="wrap">
   <a class="brand" href="{{ url_for('etalage') }}"><span class="mark">{{ winkel_letter }}</span><span class="btxt"><span class="naam">{{ winkel_naam }}</span><span class="onder">ICT-hardware</span></span></a>
   <form class="zoek" action="{{ url_for('zoeken') }}" method="get" role="search">
     <input name="q" value="{{ zoekterm or '' }}" placeholder="Zoek op merk, model of specificatie" aria-label="Zoeken">
     <button type="submit"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><span>Zoeken</span></button>
   </form>
   <a class="koptel" href="{{ telefoon_link }}">
     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2A17 17 0 0 1 3 5a2 2 0 0 1 2-2h4l2 5-2.5 1.5a13 13 0 0 0 6 6L16 13z"/></svg>
     <span>Afhalen op afspraak<b>{{ contact_telefoon }}</b></span>
   </a>
 </div></div>
 <div class="menubalk"><div class="wrap">
   <nav class="menu">
     <a href="{{ url_for('etalage') }}" class="{{ 'actief' if actief=='home' else '' }}">
       <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>Home</a>
     <span class="dropdown">
       <a href="{{ url_for('etalage') }}#aanbod" class="trigger {{ 'actief' if actief not in ['home',''] else '' }}">Categorie&euml;n
         <svg class="pijl" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg></a>
       <span class="dropmenu">
         {% for c in categorieen %}<a href="{{ url_for('categorie', slug=c.slug) }}" class="{{ 'actief' if actief==c.slug else '' }}">{{ c.icoon|safe }}{{ c.label }}</a>{% endfor %}
       </span>
     </span>
     <a href="mailto:{{ contact_email }}">Contact</a>
   </nav>
 </div></div>
</div>
{% endif %}
<main><div class="wrap">
 {% with msgs = get_flashed_messages() %}{% for m in msgs %}<div class="flash">{{ m }}</div>{% endfor %}{% endwith %}
 {{ body|safe }}
</div></main>
{% if not IS_BEHEER %}
<footer>
 <div class="wrap"><div class="kolommen">
  <div>
    <div class="fmerk"><span class="mark">{{ winkel_letter }}</span><span>{{ winkel_naam }}</span></div>
    <div class="klein">Sinds een jaar verkopen we hier de laptops, pc's en tablets die
      bij ons uit dienst gaan. Bij elk toestel staat wat we ervan weten.</div>
  </div>
  <div>
    <div class="kop">Aanbod</div>
    <ul>
      <li><a href="{{ url_for('etalage') }}">Alle toestellen</a></li>
      {% for c in categorieen %}<li><a href="{{ url_for('categorie', slug=c.slug) }}">{{ c.label }}</a></li>{% endfor %}
    </ul>
  </div>
  <div>
    <div class="kop">Contact</div>
    <div class="fcontact">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16v16H4z"/><path d="m4 7 8 6 8-6"/></svg>
      <span><a href="mailto:{{ contact_email }}">{{ contact_email }}</a></span>
    </div>
    <div class="fcontact">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2A17 17 0 0 1 3 5a2 2 0 0 1 2-2h4l2 5-2.5 1.5a13 13 0 0 0 6 6L16 13z"/></svg>
      <span><a href="{{ telefoon_link }}">{{ contact_telefoon }}</a></span>
    </div>
    <div class="fcontact">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="10" r="3"/><path d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11z"/></svg>
      <span class="klein">Afhalen op afspraak. Bel of mail om langs te komen.</span>
    </div>
  </div>
 </div></div>
 <div class="fbalk"><div class="wrap">
   <span>{{ winkel_naam }}</span>
   <span>Prijzen in euro. Tweedehands toestellen worden verkocht zonder garantie, in de staat zoals beschreven.</span>
 </div></div>
</footer>
{% endif %}
</body></html>
"""


def page(body, **kw):
    kw.setdefault("zoekterm", "")
    kw.setdefault("actief", "")
    return render_template_string(BASE, body=body, **kw)


# ---------------------------------------------------------------------------
# Publieke etalage (beide rollen)
# ---------------------------------------------------------------------------
@app.route("/healthz")
def healthz():
    return "ok", 200


TOON_SPECS = [("cpu", "Processor"), ("ram", "Geheugen"), ("opslag", "Opslag"),
              ("scherm", "Scherm"), ("resolutie", "Resolutie"), ("gpu", "Videokaart"),
              ("besturingssysteem", "Besturingssysteem"), ("bouwjaar", "Bouwjaar")]


def _spec_chips(specs, maximaal=5, conditie=None):
    """Toont de belangrijkste specs als losse blokjes in de lijstweergave.

    De staat staat hier gewoon tussen, als gegeven naast de andere gegevens.
    Dat leest als een advertentie in plaats van als een gekleurd statuslabel.
    """
    uit = []
    staat = conditie_label(conditie)
    if staat:
        uit.append(f'<span class="spec">Staat: <b>{staat}</b></span>')
    for sleutel, label in TOON_SPECS:
        waarde = specs.get(sleutel)
        if waarde:
            waarde = str(waarde)
            if len(waarde) > 46:
                waarde = waarde[:44].rstrip() + "..."
            uit.append(f'<span class="spec">{label}: <b>{waarde}</b></span>')
        if len(uit) >= maximaal:
            break
    return f'<div class="rspecs">{"".join(uit)}</div>' if uit else ""


def _rij(r):
    imgs = prod_images(r["id"])
    foto = url_for("upload", naam=imgs[0]["bestand"]) if imgs else ""
    naam = r["titel"] or ((r["merk"] or "") + " " + (r["model"] or "")).strip() or "Item"
    prijs = euro(r["prijs_definitief_cents"]) or "Prijs op aanvraag"
    catlabel = netjes_label(r["categorie"]) if r["categorie"] else ""
    beeld = (f'<img src="{foto}" alt="{naam}" loading="lazy">' if foto
             else foto_placeholder(r["categorie"], klein=True))
    return (f'<a class="rij" href="{url_for("detail", pid=r["id"])}">'
            f'<div class="rfoto">{beeld}</div>'
            f'<div class="rmid"><div class="rcat">{catlabel}</div>'
            f'<div class="rnaam">{naam}</div>'
            f'{_spec_chips(specs_dict(r["specs"]), conditie=r["conditie"])}</div>'
            f'<div class="rrechts"><div class="rprijs">{prijs}</div>'
            f'<span class="rknop">Bekijk toestel</span></div></a>')


def _lijst_html(rows, titel, sub="", leegtekst="Hier staat op dit moment niets."):
    aantal = len(rows)
    telling = f'<span class="mut">{aantal} toestel{"len" if aantal != 1 else ""}</span>' if aantal else ""
    inner = (f'<div class="lijst">{"".join(_rij(r) for r in rows)}</div>' if rows
             else f'<p class="leeg">{leegtekst}</p>')
    subregel = f'<p class="sub">{sub}</p>' if sub else ""
    return (f'<div class="lijstkop"><div><h1 class="paginatitel">{titel}</h1>'
            f'{subregel}</div>{telling}</div>{inner}')


def _live_rows(slug=None):
    rows = db().execute("SELECT * FROM products WHERE status='live' "
                        "ORDER BY gepubliceerd_op DESC, id DESC").fetchall()
    if slug:
        rows = [r for r in rows if categorie_van(r["categorie"]) == slug]
    return rows


def _etalage_html(slug, titel, sub=""):
    return _lijst_html(_live_rows(slug), titel, sub)


HERO = """
<section class="hero">
  <img src="{hero}" alt="Laptop wordt nagekeken op de werkbank">
  <div class="htxt">
    <h1>Tweedehands ICT uit eigen gebruik</h1>
    <p>Sinds een jaar verkopen we hier de laptops en pc's die bij ons uit dienst
       gaan. Op de foto's zie je hoe een toestel er nu bij ligt.</p>
    <a class="cta" href="#aanbod">Bekijk het aanbod</a>
  </div>
</section>"""

SFEER = """
<section class="sfeer">
  <img src="{sfeer}" alt="Collega test een laptop voor verkoop">
  <div class="stxt">
    <h2>Waar dit vandaan komt</h2>
    <p>Wij vervangen zelf regelmatig laptops en pc's. Het materiaal dat nog
       prima meekan, zetten we hier online.</p>
    <p>Tweedehands betekent gebruikssporen. Bij elk toestel schrijven we op wat we
       ervan weten. Er zit geen garantie op, dus je koopt het zoals het erbij ligt.
       Kom het gerust eerst bekijken voor je beslist.</p>
  </div>
</section>"""


@app.route("/")
def etalage():
    hero = HERO.format(hero=url_for("static", filename="hero-werkbank.jpg"))
    sfeer = SFEER.format(sfeer=url_for("static", filename="sfeer-nakijken.jpg"))
    body = (hero + usps_html() + '<a id="aanbod"></a>'
            + _etalage_html(None, "Nieuw binnen")
            + sfeer)
    return page(body, actief="home")


@app.route("/zoeken")
def zoeken():
    q = (request.args.get("q") or "").strip()
    if not q:
        return redirect(url_for("etalage"))
    like = f"%{q}%"
    rows = db().execute(
        """SELECT * FROM products WHERE status='live' AND (
             coalesce(titel,'') ILIKE %s OR coalesce(merk,'') ILIKE %s
             OR coalesce(model,'') ILIKE %s OR coalesce(categorie,'') ILIKE %s
             OR coalesce(omschrijving,'') ILIKE %s OR specs::text ILIKE %s
             OR coalesce(serienummer,'') ILIKE %s)
           ORDER BY gepubliceerd_op DESC, id DESC""",
        (like, like, like, like, like, like, like)).fetchall()
    body = _lijst_html(rows, f'Zoeken naar "{q}"',
                       leegtekst=f'Niets gevonden voor "{q}". '
                                 f'Probeer een merk of een modelnummer.')
    return page(body, titel=f"Zoeken: {q}", zoekterm=q)


@app.route("/categorie/<slug>")
def categorie(slug):
    c = next((x for x in actieve_categorieen() if x["slug"] == slug), None)
    if not c:
        abort(404)
    return page(_etalage_html(slug, c["label"]),
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
                  else foto_placeholder(r["categorie"]))
    strip = ""
    if len(imgs) > 1:
        thumbs = "".join(
            f'<img src="{url_for("upload", naam=i["bestand"])}" class="{"actief" if k == 0 else ""}">'
            for k, i in enumerate(imgs))
        strip = f'<div class="strip">{thumbs}</div>'
    if any(i["bron"] == "fabrikant" for i in imgs):
        strip += ('<p class="fotobron">Enkele beelden zijn officiele productfoto\'s van de '
                  'fabrikant en tonen het model, niet dit exemplaar. De staat van dit toestel '
                  'staat bij de gegevens.</p>')

    specs = specs_dict(r["specs"])
    spec_rows = "".join(f"<tr><th>{netjes_label(k)}</th><td>{v}</td></tr>"
                        for k, v in specs.items())
    specs_html = (f'<div class="specs"><h3>Specificaties</h3><table>{spec_rows}</table></div>'
                  if spec_rows else "")

    titel = r["titel"] or ((r["merk"] or "") + " " + (r["model"] or "")).strip() or "Item"
    prijs = euro(r["prijs_definitief_cents"]) or "Prijs op aanvraag"
    catobj = next((x for x in actieve_categorieen()
                   if x["slug"] == categorie_van(r["categorie"])), None)
    kruimel_cat = ""
    if catobj:
        kruimel_cat = (f'<a href="{url_for("categorie", slug=catobj["slug"])}">'
                       f'{catobj["label"]}</a> &rsaquo; ')

    meta = []
    mm = ((r["merk"] or "") + " " + (r["model"] or "")).strip()
    if mm:
        meta.append(mm)
    if r["conditie"]:
        meta.append(f'Staat: <b>{conditie_label(r["conditie"])}</b>')
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
    rows = db().execute(
        """SELECT p.*, (SELECT COUNT(*) FROM product_images i WHERE i.product_id=p.id) AS fotos
           FROM products p ORDER BY p.id DESC""").fetchall()
    trs = ""
    zonder = 0
    for r in rows:
        prijs = euro(r["prijs_definitief_cents"]) or euro(r["prijs_voorstel_cents"]) or "-"
        naam = r['titel'] or (r['merk'] or '') + ' ' + (r['model'] or '') or 'zonder titel'
        n = r["fotos"]
        if n == 0:
            zonder += 1
            fotocel = '<span style="color:var(--accent);font-weight:700">geen foto</span>'
        else:
            fotocel = f"{n}"
        aantal = r["aantal"]
        if aantal == 0:
            aantalcel = '<span style="color:var(--accent);font-weight:700">uitverkocht</span>'
        else:
            aantalcel = f"{aantal}"
        trs += (f"<tr><td><input type=\"checkbox\" name=\"ids\" value=\"{r['id']}\" "
                f"style=\"width:auto\" aria-label=\"Selecteer item {r['id']}\"></td>"
                f"<td>#{r['id']}</td>"
                f"<td><a href=\"{url_for('bewerk', pid=r['id'])}\">{naam}</a></td>"
                f"<td><span class=\"pill\">{r['status']}</span></td>"
                f"<td>{aantalcel}</td>"
                f"<td>{fotocel}</td><td>{prijs}</td></tr>")
    waarschuwing = ""
    if zonder:
        waarschuwing = (f'<div class="flash">{zonder} item(s) staan nog zonder foto.</div>')
    body = f"""
    <div class="row" style="align-items:center">
      <h2 style="flex:2">Beheer</h2>
      <div style="text-align:right"><a class="btn" href="{url_for('nieuw')}">+ Nieuw item</a></div>
    </div>
    <p class="mut">Aangemeld als {_auth_gebruiker()}</p>
    {waarschuwing}
    <form method="post" action="{url_for('verwijderen')}" onsubmit="return bevestigVerwijderen(this)">
      <table>
        <tr><th style="width:34px"></th><th>Id</th><th>Titel</th><th>Status</th>
            <th>Aantal</th><th>Foto's</th><th>Prijs</th></tr>
        {trs}
      </table>
      <p style="margin-top:14px">
        <button class="btn sec" style="border-color:var(--accent);color:var(--accent)">
          Verwijder geselecteerde items</button>
        <span class="mut">&nbsp;Definitief, inclusief foto's en taxatiegeschiedenis.</span>
      </p>
    </form>
    <script>
    function bevestigVerwijderen(f) {{
      var n = f.querySelectorAll('input[name=ids]:checked').length;
      if (n === 0) {{ alert('Vink eerst een of meer items aan.'); return false; }}
      return confirm(n + ' item(s) definitief verwijderen? Dit kan niet ongedaan gemaakt worden.');
    }}
    </script>"""
    return page(body)


def _verwijder_items(ids):
    """Verwijdert items definitief, inclusief de fotobestanden op de schijf.

    De database ruimt afbeeldingen, taxaties en bronnen zelf op via ON DELETE
    CASCADE; de bestanden op het volume blijven anders als wezen achter.
    """
    d = db()
    bestanden = [x["bestand"] for x in d.execute(
        "SELECT bestand FROM product_images WHERE product_id = ANY(%s)", (ids,)).fetchall()]
    verwijderd = d.execute(
        "DELETE FROM products WHERE id = ANY(%s) RETURNING id", (ids,)).fetchall()
    d.commit()

    for naam in bestanden:
        pad = os.path.join(UPLOAD_DIR, os.path.basename(naam))
        if os.path.commonpath([os.path.abspath(pad), UPLOAD_DIR]) != UPLOAD_DIR:
            continue
        try:
            os.remove(pad)
        except OSError:
            pass
    return len(verwijderd)


@app.route("/beheer/verwijderen", methods=["POST"])
@beheer_route
def verwijderen():
    ids = [int(i) for i in request.form.getlist("ids") if i.isdigit()]
    if not ids:
        flash("Geen items geselecteerd.")
        return redirect(url_for("beheer"))
    aantal = _verwijder_items(ids)
    flash(f"{aantal} item(s) verwijderd.")
    return redirect(url_for("beheer"))


@app.route("/beheer/<int:pid>/verwijderen", methods=["POST"])
@beheer_route
def verwijder_item(pid):
    if not db().execute("SELECT id FROM products WHERE id=%s", (pid,)).fetchone():
        abort(404)
    _verwijder_items([pid])
    flash(f"Item #{pid} verwijderd.")
    return redirect(url_for("beheer"))


@app.route("/beheer/nieuw", methods=["GET", "POST"])
@beheer_route
def nieuw():
    if request.method == "POST":
        f = request.form
        d = db()
        pid = d.execute(
            """INSERT INTO products (merk, model, serienummer, ean, categorie,
                 conditie, conditie_notities, aantal, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'concept') RETURNING id""",
            (f.get("merk"), f.get("model"), f.get("serienummer"), f.get("ean"),
             f.get("categorie"), f.get("conditie"), f.get("conditie_notities"),
             _aantal_uit(f.get("aantal"))),
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
        <div><label>Aantal</label><input name="aantal" type="number" min="0" step="1" value="1"></div>
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
                 aantal=%s, bijgewerkt_op=now() WHERE id=%s""",
            (f.get("merk"), f.get("model"), f.get("serienummer"), f.get("ean"),
             f.get("categorie"), f.get("conditie"), f.get("conditie_notities"),
             f.get("titel"), f.get("omschrijving"), Json(tekst_naar_specs(f.get("specs"))),
             _aantal_uit(f.get("aantal"), standaard=r["aantal"]), pid),
        )
        _bewaar_uploads(pid, request.files.getlist("fotos"))
        d.commit()
        # De taxatieknoppen zitten in dit formulier, zodat wat je net intypte
        # (bijvoorbeeld het model) eerst wordt opgeslagen en het onderzoek er
        # daadwerkelijk mee vertrekt.
        actie = f.get("actie") or ""
        if actie.startswith("taxeer:"):
            return _start_taxatie(pid, actie.split(":", 1)[1])
        flash("Opgeslagen.")
        return redirect(url_for("bewerk", pid=pid))

    imgs = prod_images(pid)
    gal = ""
    for i in imgs:
        label = ("fabrikant" if i["bron"] == "fabrikant" else "eigen foto")
        gal += (
            f'<figure class="fotokaart">'
            f'<img src="{url_for("upload", naam=i["bestand"])}" alt="">'
            f'<figcaption>{label}</figcaption>'
            f'<form method="post" action="{url_for("foto_verwijderen", pid=pid, iid=i["id"])}" '
            f'onsubmit="return confirm(\'Deze foto verwijderen?\')">'
            f'<button title="Foto verwijderen">verwijderen</button></form></figure>')
    eigen = sum(1 for i in imgs if i["bron"] != "fabrikant")
    fotohint = ""
    if imgs and not eigen:
        fotohint = ('<div class="flash">Dit item heeft alleen fabrikantsfoto\'s. '
                    'Voeg een foto van het echte toestel toe, zeker als er '
                    'gebruikssporen zijn.</div>')
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
    {fotohint}
    <div class="gal">{gal or '<span class="mut">geen foto</span>'}</div>
    <form method="post" action="{url_for('fabrikantsfotos', pid=pid)}" style="margin:12px 0">
      <button class="btn sec">Fabrikantsfoto's ophalen</button>
      <span class="mut">&nbsp;Zoekt op EAN of fabrikantsnummer en haalt maximaal
        {MAX_FABRIKANTSFOTOS} officiele productfoto's op.</span>
    </form>

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
        <div><label>Aantal</label><input name="aantal" type="number" min="0" step="1" value="{r['aantal']}"></div>
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
      <div class="row" style="margin-top:16px;align-items:center">
        <div style="flex:0"><button class="btn" name="actie" value="opslaan">Opslaan</button></div>
        <div style="flex:0"><button class="btn sec" name="actie" value="taxeer:specs">Opslaan en specs laten opzoeken</button></div>
        <div style="flex:0"><button class="btn sec" name="actie" value="taxeer:prijs">Opslaan en marktprijs bepalen</button></div>
      </div>
      <p class="mut">De twee onderzoeksknoppen slaan eerst je invoer op, zodat het onderzoek
         vertrekt met wat je zelf hebt ingevuld. Vul je bijvoorbeeld het model aan, dan worden
         de specificaties daarmee opnieuw opgezocht. Specs opzoeken kost centen en duurt seconden;
         marktprijs doet marktonderzoek en duurt enkele minuten.</p>
    </form>

    <hr style="border:0;border-top:1px solid var(--lijn);margin:24px 0">
    <h3>Laatste taxatie</h3>
    {tax_html}

    <hr style="border:0;border-top:1px solid var(--lijn);margin:24px 0">
    <h3>Prijs goedkeuren en publiceren</h3>
    <form method="post" action="{url_for('goedkeuren', pid=pid)}">
      <div class="row" style="align-items:end">
        <div><label>Definitieve prijs (EUR)</label>
          <input name="prijs" type="number" step="0.01" min="0.01" required value="{prijs_def}"></div>
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
    </form>

    <hr style="border:0;border-top:1px solid var(--line);margin:24px 0">
    <form method="post" action="{url_for('verwijder_item', pid=pid)}"
          onsubmit="return confirm('Item #{pid} definitief verwijderen? Dit kan niet ongedaan gemaakt worden.')">
      <button class="btn sec" style="border-color:var(--accent);color:var(--accent)">
        Dit item verwijderen</button>
      <span class="mut">&nbsp;Definitief, inclusief foto's en taxatiegeschiedenis.</span>
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


def _start_taxatie(pid, modus):
    """Zet het onderzoek in gang; leest altijd de opgeslagen gegevens uit de database."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        flash("ANTHROPIC_API_KEY ontbreekt in de omgeving; taxatie niet mogelijk.")
        return redirect(url_for("bewerk", pid=pid))
    if not db().execute("SELECT id FROM products WHERE id=%s", (pid,)).fetchone():
        abort(404)
    if _job_get(pid).get("status") == "bezig":
        return redirect(url_for("voortgang", pid=pid))
    if modus not in ("specs", "prijs"):
        modus = "prijs"
    db().execute("UPDATE products SET status='onderzoek' WHERE id=%s", (pid,))
    db().commit()
    _job(pid, status="bezig", fase="Starten...", start=time.time(), error=None)
    threading.Thread(target=_taxatie_worker, args=(pid, modus), daemon=True).start()
    return redirect(url_for("voortgang", pid=pid))


@app.route("/beheer/<int:pid>/taxeer", methods=["POST"])
@beheer_route
def taxeer_route(pid):
    return _start_taxatie(pid, request.form.get("modus", "prijs"))


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


@app.route("/beheer/<int:pid>/fabrikantsfotos", methods=["POST"])
@beheer_route
def fabrikantsfotos(pid):
    r = db().execute("SELECT * FROM products WHERE id=%s", (pid,)).fetchone()
    if not r:
        abort(404)
    al = db().execute("SELECT COUNT(*) AS n FROM product_images "
                      "WHERE product_id=%s AND bron='fabrikant'", (pid,)).fetchone()["n"]
    if al:
        flash(f"Er staan al {al} fabrikantsfoto's bij dit item. "
              f"Verwijder die eerst als je opnieuw wil ophalen.")
        return redirect(url_for("bewerk", pid=pid))

    gevonden = zoek_fabrikantsfotos(dict(r), specs_dict(r["specs"]))
    if not gevonden:
        flash("Geen fabrikantsfoto's gevonden. Vul het EAN of het juiste "
              "fabrikantsnummer in bij het model en probeer opnieuw.")
        return redirect(url_for("bewerk", pid=pid))

    aantal = 0
    for url in gevonden["beelden"][:MAX_FABRIKANTSFOTOS]:
        try:
            _bewaar_fabrikantsfoto(pid, url, aantal)
            aantal += 1
        except Exception:  # noqa: BLE001 - een enkel beeld mag mislukken
            continue
    db().commit()
    if aantal:
        flash(f"{aantal} fabrikantsfoto's toegevoegd voor {gevonden['titel'][:70]}. "
              f"Voeg zelf nog een foto van het echte toestel toe.")
    else:
        flash("Beelden gevonden, maar geen enkele kon opgehaald worden.")
    return redirect(url_for("bewerk", pid=pid))


@app.route("/beheer/<int:pid>/foto/<int:iid>/verwijderen", methods=["POST"])
@beheer_route
def foto_verwijderen(pid, iid):
    rij = db().execute("SELECT bestand FROM product_images WHERE id=%s AND product_id=%s",
                       (iid, pid)).fetchone()
    if not rij:
        abort(404)
    db().execute("DELETE FROM product_images WHERE id=%s", (iid,))
    db().commit()
    pad = os.path.join(UPLOAD_DIR, os.path.basename(rij["bestand"]))
    if os.path.commonpath([os.path.abspath(pad), UPLOAD_DIR]) == UPLOAD_DIR:
        try:
            os.remove(pad)
        except OSError:
            pass
    flash("Foto verwijderd.")
    return redirect(url_for("bewerk", pid=pid))


@app.route("/beheer/<int:pid>/goedkeuren", methods=["POST"])
@beheer_route
def goedkeuren(pid):
    cents = _eur_to_cents(request.form.get("prijs"))
    if cents is None:
        flash("Geen geldige prijs ingevuld.")
        return redirect(url_for("bewerk", pid=pid))
    if cents <= 0:
        flash("Een item kan niet live gaan met prijs nul. Vul een bedrag in.")
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
    if s not in STATUSSEN:
        return redirect(url_for("bewerk", pid=pid))
    if s == "live":
        r = db().execute("SELECT prijs_definitief_cents AS p FROM products WHERE id=%s",
                         (pid,)).fetchone()
        if not r or not r["p"] or r["p"] <= 0:
            flash("Dit item heeft nog geen prijs. Keur eerst een prijs goed, "
                  "dan gaat het meteen live.")
            return redirect(url_for("bewerk", pid=pid))
    db().execute("UPDATE products SET status=%s, bijgewerkt_op=now() WHERE id=%s", (s, pid))
    db().commit()
    flash(f"Status gezet op {s}.")
    return redirect(url_for("bewerk", pid=pid))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, threaded=True)

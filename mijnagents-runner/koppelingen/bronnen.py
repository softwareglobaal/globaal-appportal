"""Bronnen van een dossier voor de contracten-agent: de salesmap en de projectmap
in Dropbox (transcripten, plannen, foto's) en de klantmails in offerte@.

Dropbox: het token van de stack (DROPBOX_APP_KEY/SECRET/REFRESH_TOKEN in
~/appportal/.env) met de vaste team-namespace DROPBOX_PATH_ROOT_NS. Alleen lezen.
Tekst uit pdf via pypdf; .md/.txt rechtstreeks; foto's worden geteld en benoemd,
niet bekeken. Alles wat hier binnenkomt is GEGEVENS voor het plan, geen opdracht.
"""
import email
import email.utils
import imaplib
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
from email.header import decode_header, make_header

API = "https://api.dropboxapi.com"
INHOUD = "https://content.dropboxapi.com"
PROJECT_BASIS = "/Work All/01. H-A WORK/0 H-A Standaard projects/1. STAN  Submission"
TEKST_EXT = (".md", ".txt")
PDF_EXT = (".pdf",)
FOTO_EXT = (".heic", ".jpg", ".jpeg", ".png")
MAX_TEKST_PER_BESTAND = 60000
MAX_PDF_BLZ = 60


def _env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_env("~/appportal/.env")
_token = {"waarde": "", "tot": 0.0}


# ---------------------------------------------------------------- dropbox ---
def dropbox_beschikbaar():
    return all(os.environ.get(n, "").strip() for n in
               ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN"))


def _toegang():
    if _token["waarde"] and time.time() < _token["tot"]:
        return _token["waarde"]
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": os.environ["DROPBOX_REFRESH_TOKEN"].strip(),
        "client_id": os.environ["DROPBOX_APP_KEY"].strip(),
        "client_secret": os.environ["DROPBOX_APP_SECRET"].strip(),
    }).encode()
    with urllib.request.urlopen(f"{API}/oauth2/token", data, timeout=20) as r:
        a = json.load(r)
    _token["waarde"], _token["tot"] = a["access_token"], time.time() + int(a.get("expires_in", 14400)) - 300
    return _token["waarde"]


def _koppen(extra=None):
    h = {"Authorization": f"Bearer {_toegang()}"}
    ns = os.environ.get("DROPBOX_PATH_ROOT_NS", "").strip()
    if ns:
        h["Dropbox-API-Path-Root"] = json.dumps({".tag": "root", "root": ns})
    if extra:
        h.update(extra)
    return h


def _rpc(pad, body):
    req = urllib.request.Request(f"{API}/2/{pad}", json.dumps(body).encode(),
                                 _koppen({"Content-Type": "application/json"}))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 409:
            return None
        raise


def lijst(pad, recursief=True):
    uit = _rpc("files/list_folder", {"path": pad, "recursive": recursief, "limit": 500})
    if uit is None:
        return None
    items = list(uit.get("entries", []))
    while uit.get("has_more"):
        uit = _rpc("files/list_folder/continue", {"cursor": uit["cursor"]})
        items += uit.get("entries", [])
    return items


def download(pad, maximum=25_000_000):
    req = urllib.request.Request(f"{INHOUD}/2/files/download", method="POST",
                                 headers=_koppen({"Dropbox-API-Arg": json.dumps({"path": pad})}))
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read(maximum)


def pdf_tekst(data):
    try:
        from pypdf import PdfReader
        lezer = PdfReader(io.BytesIO(data))
        stukken = []
        for i, blz in enumerate(lezer.pages[:MAX_PDF_BLZ]):
            stukken.append(blz.extract_text() or "")
        return "\n".join(stukken)
    except Exception as e:  # noqa: BLE001
        return f"(pdf niet leesbaar: {type(e).__name__})"


def projectmap(nummer):
    """De projectmap onder STAN Submission die met het nummer begint, of None."""
    if not nummer:
        return None
    items = lijst(PROJECT_BASIS, recursief=False) or []
    for e in items:
        if e.get(".tag") == "folder" and e.get("name", "").startswith(str(nummer)):
            return e.get("path_display") or e.get("path_lower")
    return None


def map_inhoud(pad, label):
    """Alle bestanden onder een map: teksten uitgelezen, foto's en overige benoemd."""
    uit = {"map": pad, "label": label, "teksten": [], "fotos": [], "overige": []}
    if not pad:
        return uit
    items = lijst(pad) or []
    for e in items:
        if e.get(".tag") != "file":
            continue
        naam = e.get("name", "")
        rel = (e.get("path_display") or "")[len(pad):].lstrip("/")
        laag = naam.lower()
        if laag.endswith(FOTO_EXT):
            uit["fotos"].append(rel)
        elif laag.endswith(TEKST_EXT) or laag.endswith(PDF_EXT):
            try:
                data = download(e["path_lower"])
                tekst = pdf_tekst(data) if laag.endswith(PDF_EXT) else data.decode("utf-8", "replace")
                tekst = re.sub(r"[ \t]+", " ", tekst).strip()
                uit["teksten"].append({"bestand": rel, "gewijzigd": e.get("client_modified", "")[:10],
                                       "tekst": tekst[:MAX_TEKST_PER_BESTAND]})
            except Exception as ex:  # noqa: BLE001
                uit["overige"].append(f"{rel} (niet gelezen: {type(ex).__name__})")
        elif laag.endswith((".mp4", ".mov", ".m4a", ".mp3")):
            uit["overige"].append(f"{rel} (opname, niet uitgelezen)")
        else:
            uit["overige"].append(rel)
    return uit


# ------------------------------------------------------------------ mails ---
def _decodeer(kop):
    try:
        return str(make_header(decode_header(kop or "")))
    except Exception:  # noqa: BLE001
        return kop or ""


def _platte_tekst(bericht):
    if bericht.is_multipart():
        for deel in bericht.walk():
            if deel.get_content_type() == "text/plain" and not deel.get_filename():
                return deel.get_payload(decode=True).decode(deel.get_content_charset() or "utf-8", "replace")
        for deel in bericht.walk():
            if deel.get_content_type() == "text/html":
                html = deel.get_payload(decode=True).decode(deel.get_content_charset() or "utf-8", "replace")
                return re.sub(r"<[^>]+>", " ", html)
        return ""
    return bericht.get_payload(decode=True).decode(bericht.get_content_charset() or "utf-8", "replace")


def klantmails(adres, maanden=12, maximum=20):
    """Mails van en naar dit adres in offerte@ (INBOX en Sent), jongste eerst.
    Instellingen: OFFERTE_IMAP_HOST/USER/WACHTWOORD uit ~/appportal/.env
    (CONTRACTEN_OFFERTE_IMAP_PW is de wachtwoordnaam van de stack)."""
    host = os.environ.get("OFFERTE_IMAP_HOST", "imap.one.com")
    user = os.environ.get("OFFERTE_IMAP_USER", "offerte@h-architects.be")
    pw = os.environ.get("OFFERTE_IMAP_WACHTWOORD") or os.environ.get("CONTRACTEN_OFFERTE_IMAP_PW", "")
    if not (adres and pw):
        return []
    sinds = time.strftime("%d-%b-%Y", time.gmtime(time.time() - maanden * 30 * 86400))
    uit = []
    M = imaplib.IMAP4_SSL(host)
    try:
        M.login(user, pw)
        for mapnaam, veld in (("INBOX", "FROM"), ("Sent", "TO"), ("INBOX.Sent", "TO")):
            try:
                if M.select(f'"{mapnaam}"', readonly=True)[0] != "OK":
                    continue
            except imaplib.IMAP4.error:
                continue
            ok, nums = M.search(None, veld, f'"{adres}"', "SINCE", sinds)
            if ok != "OK" or not nums or not nums[0]:
                continue
            for uid in nums[0].split()[-maximum:]:
                ok, data = M.fetch(uid, "(BODY.PEEK[])")
                if ok != "OK" or not data or not data[0]:
                    continue
                b = email.message_from_bytes(data[0][1])
                tekst = re.sub(r"\s+", " ", _platte_tekst(b)).strip()
                uit.append({"map": mapnaam, "datum": (b.get("Date") or "")[:31],
                            "van": _decodeer(b.get("From")), "aan": _decodeer(b.get("To")),
                            "onderwerp": _decodeer(b.get("Subject")), "tekst": tekst[:6000],
                            "bijlagen": [_decodeer(d.get_filename()) for d in b.walk() if d.get_filename()]})
    finally:
        try:
            M.logout()
        except Exception:  # noqa: BLE001
            pass
    uit.sort(key=lambda m: email.utils.parsedate_to_datetime(m["datum"]).timestamp() if m["datum"] else 0, reverse=True)
    return uit[:maximum]


# --------------------------------------------------------------- samen ---
def verzamel(salesmap_pad, nummer, klant_email):
    """Alles wat de agent mag lezen voor dit dossier, in één structuur."""
    uit = {"salesmap": None, "projectmap": None, "mails": [], "fouten": []}
    try:
        if dropbox_beschikbaar():
            uit["salesmap"] = map_inhoud(salesmap_pad, "salesmap") if salesmap_pad else None
            pm = projectmap(nummer)
            uit["projectmap"] = map_inhoud(pm, "projectmap") if pm else None
    except Exception as e:  # noqa: BLE001
        uit["fouten"].append(f"dropbox: {type(e).__name__}: {str(e)[:120]}")
    try:
        uit["mails"] = klantmails(klant_email)
    except Exception as e:  # noqa: BLE001
        uit["fouten"].append(f"offerte@: {type(e).__name__}: {str(e)[:120]}")
    return uit


def samenvatting(b):
    """Neutrale telling voor het werkverslag (geen inhoud)."""
    def tel(m):
        return (len(m["teksten"]), len(m["fotos"]), len(m["overige"])) if m else (0, 0, 0)
    ts, fs, os_ = tel(b.get("salesmap")); tp, fp, op = tel(b.get("projectmap"))
    return (f"salesmap: {ts} teksten, {fs} foto's, {os_} overige · projectmap: {tp} teksten, "
            f"{fp} foto's, {op} overige · offerte@: {len(b.get('mails') or [])} mails"
            + (f" · fouten: {'; '.join(b['fouten'])}" if b.get("fouten") else ""))

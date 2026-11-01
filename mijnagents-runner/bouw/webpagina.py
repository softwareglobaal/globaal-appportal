"""De code leest de pagina's van een firma zelf (01-11-2026). Claude Code op het abonnement geeft met WebFetch een
samenvatting van een pagina, geen letterlijke tekst; een citaat, een ondernemingsnummer of een mailadres moet de code
letterlijk terugvinden, dus leest ze die pagina's zelf.

Alleen http en https naar een openbaar adres op poort 80 of 443, ook na een omleiding: nooit de server zelf of het
interne netwerk (een link komt van het model en dus van het web). Hoogstens MAX_BYTES per pagina, alleen HTML of tekst.
"""
import ipaddress
import re
import socket
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit

MAX_BYTES = 2_000_000
TIMEOUT = 10
SOORTEN = ("text/html", "application/xhtml+xml", "text/plain")
BLOK = {"p", "div", "br", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "footer",
        "header", "address", "table", "ul", "ol", "dd", "dt", "nav", "main", "aside", "blockquote", "form", "label"}
WEG = {"script", "style", "noscript", "svg", "template", "iframe", "head"}


def openbaar(url, opzoeken=socket.getaddrinfo):
    """Is dit een http(s)-adres op poort 80 of 443 waarvan elk IP-adres openbaar is?"""
    try:
        d = urlsplit(str(url or ""))
        poort = d.port
    except ValueError:
        return False
    if d.scheme not in ("http", "https") or not d.hostname or poort not in (None, 80, 443):
        return False
    try:
        adressen = {a[4][0] for a in opzoeken(d.hostname, poort or (443 if d.scheme == "https" else 80),
                                              proto=socket.IPPROTO_TCP)}
        return bool(adressen) and all(ipaddress.ip_address(a.split("%")[0]).is_global for a in adressen)
    except (OSError, ValueError):
        return False


class _Omleiding(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not openbaar(newurl):
            raise urllib.error.URLError("omleiding naar een adres dat niet openbaar is")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def haal(url, timeout=TIMEOUT):
    """De HTML van een openbare pagina; een OSError (ook URLError en HTTPError) als dat niet lukt of niet mag."""
    if not openbaar(url):
        raise OSError("geen openbaar http(s)-adres")
    opener = urllib.request.build_opener(_Omleiding)
    verzoek = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; mijnagents-bouw)",
                                                   "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8",
                                                   "Accept-Language": "nl-BE,nl;q=0.9,fr;q=0.5"})
    with opener.open(verzoek, timeout=timeout) as antwoord:
        if antwoord.headers.get_content_type() not in SOORTEN:
            raise OSError(f"geen webpagina ({antwoord.headers.get_content_type()})")
        data = antwoord.read(MAX_BYTES)
        charset = antwoord.headers.get_content_charset()
    if not charset:
        m = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", data[:4000], re.I)
        charset = m.group(1).decode("ascii", "replace") if m else "utf-8"
    try:
        return data.decode(charset, errors="replace")
    except LookupError:
        return data.decode("utf-8", errors="replace")


def _cf_mail(hexa):
    """Een mailadres dat Cloudflare verbergt (data-cfemail): de eerste byte is de sleutel voor de rest."""
    try:
        b = bytes.fromhex(hexa)
        return "".join(chr(x ^ b[0]) for x in b[1:])
    except (ValueError, IndexError):
        return ""


class _Tekst(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.delen, self.diep = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in WEG:
            self.diep += 1
        if tag in BLOK:
            self.delen.append("\n")
        a = dict(attrs)
        href = str(a.get("href") or "")
        if self.diep:
            return
        if href.lower().startswith(("mailto:", "tel:")):          # het adres staat soms alleen in de link
            self.delen.append(" " + href.split(":", 1)[1].split("?")[0] + " ")
        if a.get("data-cfemail"):
            self.delen.append(" " + _cf_mail(a["data-cfemail"]) + " ")

    def handle_endtag(self, tag):
        if tag in WEG and self.diep:
            self.diep -= 1
        if tag in BLOK:
            self.delen.append("\n")

    def handle_data(self, data):
        if not self.diep:
            self.delen.append(data)


def tekst(pagina):
    """De leesbare tekst van een HTML-pagina, een regel per blok, zonder scripts en stijlen."""
    p = _Tekst()
    try:
        p.feed(str(pagina or ""))
        p.close()
    except Exception:  # noqa: BLE001  kapotte HTML: wat al gelezen is, blijft
        pass
    regels = (" ".join(r.split()) for r in "".join(p.delen).replace("\xa0", " ").splitlines())
    return "\n".join(r for r in regels if r)

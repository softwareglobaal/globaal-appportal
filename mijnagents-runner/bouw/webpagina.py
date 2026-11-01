"""De code leest de pagina's van een firma zelf (01-11-2026). Claude Code op het abonnement geeft met WebFetch een
samenvatting van een pagina, geen letterlijke tekst; een citaat, een ondernemingsnummer of een mailadres moet de code
letterlijk terugvinden, dus leest ze die pagina's zelf.

Alleen http en https naar een openbaar adres op poort 80 of 443 (een link komt van het model en dus van het web): nooit
de server zelf of het interne netwerk. De code zoekt het IP-adres een keer op, keurt het en verbindt met precies dat
adres (Codex, controle 17: geen tweede opzoeking die naar binnen kan wijzen); https controleert het certificaat op de
naam. Een omleiding volgt de code zelf, met dezelfde keuring, hoogstens MAX_OMLEIDINGEN keer. Hoogstens MAX_BYTES per
pagina, alleen HTML of tekst, en hoogstens TIMEOUT seconden in totaal per pagina.
"""
import http.client
import ipaddress
import re
import socket
import ssl
import threading
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

MAX_BYTES = 2_000_000
TIMEOUT = 10
MAX_OMLEIDINGEN = 4
DNS_TIMEOUT = 3


def binnen(fn, timeout):
    """fn() met een harde tijdgrens (Codex, controle 19): na timeout seconden een TimeoutError, ook als een trage server
    druppelsgewijs antwoordt of een opzoeking blijft hangen. fn loopt dan verder in een losse draad die het proces niet
    ophoudt; elke socket in fn heeft zelf ook een timeout."""
    if timeout <= 0:
        raise TimeoutError("geen tijd meer")
    uit = {}

    def doe():
        try:
            uit["waarde"] = fn()
        except BaseException as e:  # noqa: BLE001  doorgeven aan wie wacht
            uit["fout"] = e
    t = threading.Thread(target=doe, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError("te traag")
    if "fout" in uit:
        raise uit["fout"]
    return uit["waarde"]
SOORTEN = ("text/html", "application/xhtml+xml", "text/plain")
KOPPEN = {"User-Agent": "Mozilla/5.0 (compatible; mijnagents-bouw)",
          "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8", "Accept-Language": "nl-BE,nl;q=0.9,fr;q=0.5",
          "Accept-Encoding": "identity", "Connection": "close"}
BLOK = {"p", "div", "br", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "footer",
        "header", "address", "table", "ul", "ol", "dd", "dt", "nav", "main", "aside", "blockquote", "form", "label"}
WEG = {"script", "style", "noscript", "svg", "template", "iframe", "head"}


def _doel(url):
    """(schema, host, poort, pad) van een http(s)-url op poort 80 of 443, of None."""
    try:
        d = urlsplit(str(url or ""))
        poort = d.port
    except ValueError:
        return None
    if d.scheme not in ("http", "https") or not d.hostname or poort not in (None, 80, 443):
        return None
    pad = (d.path or "/") + (f"?{d.query}" if d.query else "")
    return d.scheme, d.hostname, poort or (443 if d.scheme == "https" else 80), pad


def openbaar_ip(host, poort, opzoeken=socket.getaddrinfo, timeout=DNS_TIMEOUT):
    """Het eerste IP-adres van de host als elk adres openbaar is, anders None; ook None als de opzoeking langer dan
    timeout seconden duurt (Codex, controle 18)."""
    try:
        adressen = [a[4][0] for a in binnen(lambda: opzoeken(host, poort, proto=socket.IPPROTO_TCP), timeout)]
        if adressen and all(ipaddress.ip_address(a.split("%")[0]).is_global for a in adressen):
            return adressen[0]
    except (OSError, ValueError):
        pass
    return None


def openbaar(url, opzoeken=socket.getaddrinfo):
    """Is dit een http(s)-adres op poort 80 of 443 waarvan elk IP-adres openbaar is?"""
    d = _doel(url)
    return bool(d and openbaar_ip(d[1], d[2], opzoeken))


class _VastHTTP(http.client.HTTPConnection):
    def __init__(self, host, poort, ip, timeout):
        super().__init__(host, poort, timeout=timeout)
        self.ip = ip

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)


class _VastHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, poort, ip, timeout):
        super().__init__(host, poort, timeout=timeout, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        ruw = socket.create_connection((self.ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(ruw, server_hostname=self.host)


def _een_verzoek(url, rest, opzoeken, verbinding):
    """(status, koppen, data of None): een GET naar het gekeurde IP-adres, zonder omleiding te volgen."""
    d = _doel(url)
    if not d:
        raise OSError("geen http(s)-adres op poort 80 of 443")
    schema, host, poort, pad = d
    begin = time.monotonic()
    ip = openbaar_ip(host, poort, opzoeken, timeout=min(DNS_TIMEOUT, rest))
    if not ip:
        raise OSError("geen openbaar adres")
    over = rest - (time.monotonic() - begin)
    if over <= 0:
        raise OSError("te traag")
    c = verbinding(schema, host, poort, ip, over)
    try:
        c.request("GET", pad, headers=KOPPEN)
        a = c.getresponse()
        if a.status in (301, 302, 303, 307, 308):
            return a.status, a, None
        if a.status != 200:
            raise OSError(f"http {a.status}")
        if (a.getheader("Content-Type") or "").split(";")[0].strip().lower() not in SOORTEN:
            raise OSError("geen webpagina")
        stukken, grootte = [], 0
        while grootte < MAX_BYTES:
            if time.monotonic() - begin > rest:
                raise OSError("te traag")
            stuk = a.read(min(65536, MAX_BYTES - grootte))
            if not stuk:
                break
            stukken.append(stuk)
            grootte += len(stuk)
        return a.status, a, b"".join(stukken)
    finally:
        c.close()


def _verbinding(schema, host, poort, ip, timeout):
    return (_VastHTTPS if schema == "https" else _VastHTTP)(host, poort, ip, timeout)


def haal(url, timeout=TIMEOUT, opzoeken=socket.getaddrinfo, verbinding=_verbinding):
    """De HTML van een openbare pagina; een OSError als dat niet lukt of niet mag, ook binnen een omleiding."""
    einde = time.monotonic() + timeout
    for _ in range(MAX_OMLEIDINGEN + 1):
        rest = einde - time.monotonic()
        if rest <= 0:
            raise OSError("te traag")
        try:
            status, a, data = binnen(lambda: _een_verzoek(url, rest, opzoeken, verbinding), rest)
        except http.client.HTTPException as e:      # een kapot antwoord is geen OSError
            raise OSError(f"kapot antwoord ({type(e).__name__})") from None
        if data is None:
            nieuw = a.getheader("Location")
            if not nieuw:
                raise OSError("omleiding zonder adres")
            url = urljoin(url, nieuw)
            continue
        charset = None
        m = re.search(r"charset=[\"']?([\w-]+)", a.getheader("Content-Type") or "", re.I)
        if m:
            charset = m.group(1)
        if not charset:
            m = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", data[:4000], re.I)
            charset = m.group(1).decode("ascii", "replace") if m else "utf-8"
        try:
            return data.decode(charset, errors="replace")
        except LookupError:
            return data.decode("utf-8", errors="replace")
    raise OSError("te veel omleidingen")


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

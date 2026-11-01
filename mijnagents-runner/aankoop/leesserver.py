#!/usr/bin/env python3
"""De leestool van De Prijsonderzoeker (overleg 14, A2): een kleine MCP-server over stdio, zonder extra pakket.

claude -p krijgt de tool lees_pagina(url). De server haalt de pagina op vanaf de VM, maakt er tekst van (een PDF met
pypdf, als dat er is), kapt af op MAX_TEKENS en geeft die tekst aan het model. Dezelfde tekst gaat als een JSON-regel
naar het leeslog (LEES_LOG); dat wordt `gelezen` voor aankoop/aanbod.py. Het model leest dus precies de tekst die de
code nakijkt, zoals vroeger met web_fetch. Na MAX_LEZEN geslaagde lezingen, of 2 x MAX_LEZEN pogingen samen,
antwoordt hij "leesgrens bereikt": een foutpagina kost geen leesbeurt (overleg 29, X1).

Leest alleen openbare pagina's: geen formulier, geen login, geen cookies, en nooit een adres op de VM of in het
eigen netwerk (ook niet na een doorverwijzing), want een webpagina mag het model niet naar het bord sturen.
"""
import http.client
import io
import ipaddress
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

MAX_LEZEN = int(os.environ.get("PRIJS_MAX_LEZEN", "6"))
MAX_POGINGEN = 2 * MAX_LEZEN                     # geslaagd en mislukt samen: geen eindeloze lus op foutpagina's
MAX_TEKENS = int(os.environ.get("PRIJS_MAX_PAGINA_TOKENS", "10000")) * 4     # ongeveer vier tekens per token
MAX_BYTES = 8_000_000
MAX_FOTOS = 8
MAX_DOCUMENTEN = 8               # PDF-links van de pagina, zoals een handleiding (overleg 33, A)
WACHT = 25
AGENT = "Mozilla/5.0 (compatible; Prijsonderzoeker/1.0; +https://globaal.be)"
TOOL = {"name": "lees_pagina",
        "description": "Lees een openbare webpagina of PDF en krijg haar tekst (afgekapt op ongeveer "
                       f"{MAX_TEKENS // 4} tokens), met bovenaan de productfoto's en de PDF-documenten (handleiding, "
                       "specificatieblad) die de pagina linkt. Alleen deze tekst telt als gelezen; "
                       "de URL bovenaan is de url van het aanbod (na een doorverwijzing de eindpagina).",
        "inputSchema": {"type": "object", "properties": {"url": {"type": "string", "description": "https-adres"}},
                        "required": ["url"]}}


class Geweigerd(Exception):
    pass


def openbaar_adres(host):
    """Het IP-adres waarmee verbonden wordt; Geweigerd als een van de adressen van de naam niet openbaar is."""
    try:
        adressen = [a[4][0] for a in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)]
    except (socket.gaierror, UnicodeError) as e:
        raise Geweigerd(f"adres onbekend ({e})") from e
    if not adressen:
        raise Geweigerd("adres onbekend")
    for a in adressen:
        if not ipaddress.ip_address(a.split("%")[0]).is_global:
            raise Geweigerd("geen openbaar adres")
    return adressen[0]


def openbaar(url):
    """Weigert alles behalve http(s) naar een openbaar adres op de gewone poort."""
    d = urlsplit(url)
    if d.scheme not in ("http", "https") or not d.hostname or d.port not in (None, 80, 443):
        raise Geweigerd("alleen http of https naar een openbaar adres")
    openbaar_adres(d.hostname)


def _vast_verbinden(adres, timeout=None, bron=None, *rest):
    """Verbindt met het adres dat openbaar_adres() zelf nakeek, niet met een tweede DNS-antwoord (Codex controle
    15, punt 2: DNS-rebinding). De naam blijft voor de Host-kop en voor TLS (SNI en certificaat)."""
    host, poort = adres
    return socket.create_connection((openbaar_adres(host), poort), timeout, bron)


class _VasteHTTP(http.client.HTTPConnection):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._create_connection = _vast_verbinden


class _VasteHTTPS(http.client.HTTPSConnection):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._create_connection = _vast_verbinden


class _HTTP(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_VasteHTTP, req)


class _HTTPS(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_VasteHTTPS, req, context=self._context)


class _Doorverwijzing(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        openbaar(newurl)              # een doorverwijzing naar het eigen netwerk telt niet
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def haal(url):
    """(eind_url, soort, bytes) van een openbare pagina."""
    openbaar(url)
    opener = urllib.request.build_opener(_Doorverwijzing, _HTTP, _HTTPS)
    vraag = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.8",
                                                 "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.5"})
    with opener.open(vraag, timeout=WACHT) as r:
        verbonden_openbaar(r)
        return r.geturl(), r.headers.get("Content-Type", ""), r.read(MAX_BYTES)


def verbonden_openbaar(r):
    """Na het verbinden en voor het lezen: het adres waarmee echt verbonden is, moet openbaar zijn. DNS kan na de
    controle in openbaar() een ander adres geven (DNS-rebinding); zo leest de tool toch nooit iets van de VM."""
    try:
        adres = r.fp.raw._sock.getpeername()[0]
    except (AttributeError, OSError) as e:
        raise Geweigerd("het verbonden adres is niet na te gaan") from e
    if not ipaddress.ip_address(adres.split("%")[0]).is_global:
        raise Geweigerd("verbonden met een adres dat niet openbaar is")


class _Tekst(HTMLParser):
    BLOK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table", "ul", "ol",
            "dd", "dt", "header", "footer", "main", "aside", "form", "label", "button", "option", "figcaption"}
    WEG = {"script", "style", "noscript", "svg", "template", "iframe", "head"}
    META = {"description", "og:title", "og:description", "product:price:amount", "product:price:currency"}

    def __init__(self, basis):
        super().__init__(convert_charrefs=True)
        self.basis, self.stukken, self.diep, self.fotos, self.meta, self.ld = basis, [], 0, [], [], None
        self.documenten = []

    def _foto(self, src):
        src = urljoin(self.basis, (src or "").strip())
        if src.startswith(("https://", "http://")) and src not in self.fotos and len(self.fotos) < MAX_FOTOS:
            self.fotos.append(src)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self.ld = []                  # productgegevens (prijs, munt, modelcode) die de winkel zelf meegeeft
            return
        if tag == "meta":
            naam = (a.get("property") or a.get("name") or "").lower()
            if naam == "og:image":
                self._foto(a.get("content"))
            elif naam in self.META and a.get("content"):
                self.meta.append(f"{naam}: {a['content']}")
            return
        if tag == "a" and a.get("href"):
            # Een handleiding of specificatieblad staat vaak alleen als PDF-link op de winkelpagina (overleg 33, M1).
            href = urljoin(self.basis, a["href"].strip())
            if (href.startswith(("https://", "http://")) and urlsplit(href).path.lower().endswith(".pdf")
                    and href not in self.documenten and len(self.documenten) < MAX_DOCUMENTEN):
                self.documenten.append(href)
        if tag in self.WEG:
            self.diep += 1
        elif tag == "img" and not self.diep:
            self._foto(a.get("src") or a.get("data-src"))
        elif tag in ("td", "th"):
            self.stukken.append(" | ")
        elif tag in self.BLOK:
            self.stukken.append("\n")

    def handle_endtag(self, tag):
        if tag == "script" and self.ld is not None:
            self.stukken.append("\n" + re.sub(r"\s+", " ", "".join(self.ld))[:6000] + "\n")
            self.ld = None
        elif tag in self.WEG:
            self.diep = max(0, self.diep - 1)
        elif tag in self.BLOK:
            self.stukken.append("\n")

    def handle_data(self, data):
        if self.ld is not None:
            self.ld.append(data)
        elif not self.diep:
            self.stukken.append(data)


def html_tekst(html, basis):
    p = _Tekst(basis)
    p.feed(html)
    p.close()
    regels = [re.sub(r"[ \t\xa0]+", " ", r).strip() for r in "".join(p.stukken).splitlines()]
    tekst = "\n".join(r for r in regels if r and r != "|")
    kop = ((["Productfoto's: " + " ".join(p.fotos)] if p.fotos else [])
           + (["Documenten: " + " ".join(p.documenten)] if p.documenten else []) + p.meta)
    return "\n".join(kop + [tekst])


def pdf_tekst(data):
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    stukken, lengte = [], 0
    for blad in PdfReader(io.BytesIO(data)).pages:
        t = blad.extract_text() or ""
        stukken.append(t)
        lengte += len(t)
        if lengte > MAX_TEKENS:
            break
    return "\n".join(stukken)


def _gelezen_tot_nu(log):
    """(geslaagd, pogingen) in het leeslog."""
    geslaagd = pogingen = 0
    try:
        with open(log, encoding="utf-8") as f:
            for r in f:
                if r.strip():
                    pogingen += 1
                    try:
                        geslaagd += bool(json.loads(r).get("ok"))
                    except (ValueError, AttributeError):
                        pass
    except OSError:
        pass
    return geslaagd, pogingen


def lees(url, log, ophalen=haal):
    """(tekst voor het model, geslaagd). Schrijft elke poging, ook een mislukte, in het leeslog."""
    url = str(url or "").strip()
    geslaagd, pogingen = _gelezen_tot_nu(log)
    if geslaagd >= MAX_LEZEN or pogingen >= MAX_POGINGEN:
        return f"Leesgrens bereikt ({geslaagd} pagina's gelezen, {pogingen} pogingen): rond af met wat je las.", False
    regel = {"url": url, "eind_url": url, "ok": False, "tekst": "", "fout": ""}
    try:
        eind, soort, data = ophalen(url)
        regel["eind_url"] = eind
        if "pdf" in soort.lower() or data[:5] == b"%PDF-":
            tekst = pdf_tekst(data)
        else:
            m = re.search(r"charset=([\w-]+)", soort, re.I) or re.search(rb'charset=["\']?([\w-]+)', data[:4000], re.I)
            code = m.group(1) if m else "utf-8"
            code = code.decode() if isinstance(code, bytes) else code
            try:
                tekst = html_tekst(data.decode(code, "replace"), eind)
            except LookupError:
                tekst = html_tekst(data.decode("utf-8", "replace"), eind)
        tekst = tekst.strip()
        if not tekst:
            raise ValueError("geen leesbare tekst")
        afgekapt = len(tekst) > MAX_TEKENS
        regel["tekst"] = tekst[:MAX_TEKENS] + ("\n[afgekapt]" if afgekapt else "")
        regel["ok"] = True
    except urllib.error.HTTPError as e:
        regel["fout"] = f"HTTP {e.code}"
    except (Geweigerd, urllib.error.URLError, OSError, ValueError) as e:
        regel["fout"] = f"{type(e).__name__}: {str(e)[:200]}"
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(regel, ensure_ascii=False) + "\n")
    if regel["ok"]:
        return f"URL: {regel['eind_url']}\n\n{regel['tekst']}", True    # deze url geldt voor het aanbod (Codex 15, 3)
    return f"Niet leesbaar: {regel['fout']}", False


def antwoord(bericht, log, ophalen=haal):
    """Het JSON-RPC-antwoord op een bericht, of None voor een melding zonder id."""
    mid, methode = bericht.get("id"), bericht.get("method")
    if mid is None:
        return None
    if methode == "initialize":
        versie = (bericht.get("params") or {}).get("protocolVersion") or "2025-06-18"
        return {"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": versie, "capabilities": {"tools": {}},
                                                       "serverInfo": {"name": "lees", "version": "1.0"}}}
    if methode == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if methode == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": [TOOL]}}
    if methode == "tools/call":
        p = bericht.get("params") or {}
        if p.get("name") != TOOL["name"]:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "onbekende tool"}}
        tekst, ok = lees((p.get("arguments") or {}).get("url"), log, ophalen)
        return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": tekst}], "isError": not ok}}
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"onbekend: {methode}"}}


def main():
    log = os.environ["LEES_LOG"]
    for regel in sys.stdin:
        try:
            bericht = json.loads(regel)
        except ValueError:
            continue
        uit = antwoord(bericht, log) if isinstance(bericht, dict) else None
        if uit:
            sys.stdout.write(json.dumps(uit, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

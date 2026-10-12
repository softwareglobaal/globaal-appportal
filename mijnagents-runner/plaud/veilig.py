"""Veilig downloaden van Plaud-links (verbeteropdracht v1.0, §8).

Een getekende link is een aanwijzing van buiten, geen vertrouwd pad. Daarom:

- alleen https, alleen de vaste opslag van Plaud (TOEGESTANE_HOSTS), poort 443, geen login in de url;
- elk adres waarnaar de host oplost moet publiek zijn: geen localhost, privé-, link-local- of
  intern adres;
- omleidingen volgen we zelf, hoogstens drie, en elke stap wordt opnieuw gecontroleerd;
- grootte en tijd zijn begrensd; de inhoud van audio wordt herkend aan de eerste bytes en die
  bepalen de extensie, niet de url.

Een link wordt nooit gelogd of in een bestand gezet dat gedeeld wordt; meldingen noemen alleen
de host. Downloaden gaat met curl: de systeem-Python op de Mac heeft geen bruikbare rootstore.

Python 3.9-compatibel.
"""
import ipaddress
import os
import socket
import subprocess
import tempfile
from urllib.parse import urljoin, urlsplit

TOEGESTANE_HOSTS = {
    "prod-plaud-content-storage.s3-accelerate.amazonaws.com",
    "prod-plaud-content-storage.s3.amazonaws.com",
    "prod-plaud-content-storage.s3.us-west-2.amazonaws.com",
}
MAX_OMLEIDINGEN = 3


class OnveiligeLink(ValueError):
    pass


class DownloadFout(RuntimeError):
    pass


def host_van(url):
    try:
        return urlsplit(url).hostname or "?"
    except ValueError:
        return "?"


def controleer_url(url, oplosser=socket.getaddrinfo):
    """Gooit OnveiligeLink als de url niet naar de vaste Plaud-opslag over publiek internet wijst."""
    try:
        d = urlsplit((url or "").strip())
    except ValueError:
        raise OnveiligeLink("url niet leesbaar")
    if d.scheme != "https":
        raise OnveiligeLink("alleen https is toegestaan (kreeg %r)" % d.scheme)
    if d.username or d.password:
        raise OnveiligeLink("geen login in de url")
    host = (d.hostname or "").lower()
    if host not in TOEGESTANE_HOSTS:
        raise OnveiligeLink("host niet toegestaan: %s" % host)
    if d.port not in (None, 443):
        raise OnveiligeLink("poort niet toegestaan: %s" % d.port)
    try:
        adressen = {a[4][0] for a in oplosser(host, 443, proto=socket.IPPROTO_TCP)}
    except (OSError, socket.gaierror) as e:
        raise OnveiligeLink("host niet op te lossen: %s" % type(e).__name__)
    if not adressen:
        raise OnveiligeLink("host lost niet op")
    for a in adressen:
        ip = ipaddress.ip_address(a.split("%")[0])
        if not ip.is_global or ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise OnveiligeLink("host lost op naar een niet-publiek adres")
    return host


def _curl(url, doelbestand, max_bytes, timeout):
    """Eén verzoek zonder omleidingen te volgen. Geeft (http_code, omleiding)."""
    r = subprocess.run(["curl", "-sS", "--proto", "=https", "--max-redirs", "0", "--max-time", str(int(timeout)),
                        "--max-filesize", str(int(max_bytes)), "-o", doelbestand, "-w", "%{http_code} %{redirect_url}",
                        url], capture_output=True)
    if r.returncode not in (0,):
        raise DownloadFout("curl %d bij %s" % (r.returncode, host_van(url)))
    code, _, omleiding = r.stdout.decode("utf-8", "replace").partition(" ")
    return int(code or 0), omleiding.strip()


def haal(url, max_bytes, timeout, oplosser=socket.getaddrinfo, verzoek=_curl):
    """Bytes van een gecontroleerde link. Elke omleiding wordt opnieuw gecontroleerd."""
    huidige = url
    for _ in range(MAX_OMLEIDINGEN + 1):
        controleer_url(huidige, oplosser)
        fd, tmp = tempfile.mkstemp(prefix="plaud-", suffix=".tmp")
        os.close(fd)
        try:
            code, omleiding = verzoek(huidige, tmp, max_bytes, timeout)
            if code in (301, 302, 303, 307, 308):
                if not omleiding:
                    raise DownloadFout("omleiding zonder doel bij %s" % host_van(huidige))
                huidige = urljoin(huidige, omleiding)
                continue
            if code != 200:
                raise DownloadFout("HTTP %d bij %s" % (code, host_van(huidige)))
            grootte = os.path.getsize(tmp)
            if grootte > max_bytes:
                raise DownloadFout("groter dan toegestaan bij %s" % host_van(huidige))
            with open(tmp, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    raise DownloadFout("te veel omleidingen")


def audio_soort(kop):
    """De extensie die bij de inhoud hoort, of None als het geen audio is."""
    if kop[:4] == b"OggS":
        return ".opus" if b"OpusHead" in kop[:200] else ".ogg"
    if kop[:3] == b"ID3" or (len(kop) > 1 and kop[0] == 0xFF and (kop[1] & 0xE0) == 0xE0):
        return ".mp3"
    if kop[4:8] == b"ftyp":
        return ".m4a"
    if kop[:4] == b"RIFF" and kop[8:12] == b"WAVE":
        return ".wav"
    return None

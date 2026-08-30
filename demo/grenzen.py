"""De grenzen van de publieke demo.

Een demo die iedereen mag gebruiken is een open deur naar je server. Vijf
maatregelen houden hem dicht, en alle vijf staan ze zichtbaar op de pagina:
wie weet waar de grens ligt, ervaart hem niet als een storing maar als een
keuze.

  bladzijden   veertig, en vriendelijk: een langer document wordt afgekapt en
               verwerkt, niet geweigerd
  omvang       vijftien megabyte
  soort        alleen een PDF die zijn eigen tekst draagt; een scan kost geld
               om uit te lezen en dat doen we niet gratis voor onbekenden
  aantal       vijf documenten per dag per IP-adres
  gelijktijdig één tegelijk, met een korte wachtrij ervoor

Het IP-adres wordt niet bewaard maar gehasht met een sleutel die per herstart
verandert. Daarmee kun je wel tellen en niet herleiden, en na een dag is de
telling sowieso weg. Dat is nodig om te kunnen beloven dat er niets blijft
staan.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import threading
import time
from dataclasses import dataclass

MAX_BLADZIJDEN = 40
MAX_BYTES = 15 * 1024 * 1024
PER_DAG_PER_IP = 5
WACHTRIJ_MAX = 3           # naast de lopende verwerking
BEWAARTIJD_SECONDEN = 3600  # alles weg na een uur

_PEPER = secrets.token_bytes(16)
_slot = threading.Lock()
_tellingen: dict[str, list[float]] = {}


def _sleutel(ip: str) -> str:
    return hashlib.blake2b(ip.encode(), key=_PEPER, digest_size=16).hexdigest()


def afzender(request) -> str:
    """Het IP van de bezoeker, ook achter de nginx-proxy."""
    door = request.headers.get("X-Forwarded-For", "")
    if door:
        return door.split(",")[0].strip()
    return request.remote_addr or "onbekend"


@dataclass
class Ruimte:
    mag: bool
    gebruikt: int
    over: int
    reden: str = ""


def controleer_quotum(ip: str) -> Ruimte:
    """Hoeveel documenten heeft dit adres vandaag al gedaan?"""
    nu = time.time()
    k = _sleutel(ip)
    with _slot:
        tijden = [t for t in _tellingen.get(k, []) if nu - t < 86400]
        _tellingen[k] = tijden
        gebruikt = len(tijden)
    over = max(0, PER_DAG_PER_IP - gebruikt)
    if over == 0:
        return Ruimte(False, gebruikt, 0,
                      "Je hebt vandaag vijf documenten verwerkt, het maximum "
                      "voor de demo.")
    return Ruimte(True, gebruikt, over)


def boek_verbruik(ip: str) -> None:
    with _slot:
        _tellingen.setdefault(_sleutel(ip), []).append(time.time())


def ruim_tellingen_op() -> None:
    nu = time.time()
    with _slot:
        for k in list(_tellingen):
            _tellingen[k] = [t for t in _tellingen[k] if nu - t < 86400]
            if not _tellingen[k]:
                del _tellingen[k]


class Werkbank:
    """Eén verwerking tegelijk, met een korte wachtrij ervoor.

    Een paginalimiet beschermt de server minder goed dan dit: veertig
    bladzijden tekst is licht, maar tien mensen tegelijk zijn dat niet. Wie
    aankomt terwijl de rij vol is krijgt een net antwoord in plaats van een
    time-out.
    """

    def __init__(self, plaatsen: int = WACHTRIJ_MAX):
        self._slot = threading.Semaphore(plaatsen + 1)
        self._werk = threading.Lock()
        self.plaatsen = plaatsen

    def vrij(self) -> bool:
        gekregen = self._slot.acquire(blocking=False)
        if gekregen:
            self._slot.release()
        return gekregen

    def __enter__(self):
        if not self._slot.acquire(blocking=False):
            raise Bezet()
        self._werk.acquire()
        return self

    def __exit__(self, *_):
        self._werk.release()
        self._slot.release()
        return False


class Bezet(Exception):
    """De wachtrij zit vol."""


def peper_verversen() -> None:
    """Alleen voor tests: nieuwe sleutel, dus alle tellingen ongeldig."""
    global _PEPER
    _PEPER = secrets.token_bytes(16)
    with _slot:
        _tellingen.clear()

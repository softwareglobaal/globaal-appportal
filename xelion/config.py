"""Wie mag wat met Xelion.

Eén bestand op de VM, buiten git: `~/xelion-config/rechten.yaml`, read-only
gemount op `/config`. Wordt elke vijf seconden herlezen, dus wijzigen vraagt
geen herstart. Zelfde opzet als de Postbus.

Dicht tenzij opengezet: staat iemand er niet in, dan mag hij niets. Ook lezen
niet.

De vier rechten:

    lezen         contacten zoeken en opvragen, lijsten, gesprekken
    aanmaken      een contact of lijst toevoegen
    bijwerken     een bestaand contact wijzigen, lijstleden toevoegen/afhalen
    verwijderen   een contact definitief weggooien

Verwijderen staat los van bijwerken omdat Xelion geen prullenbak heeft. Wat
weg is, is weg. Bovenop dit bestand liggen drie noodremmen in de stack-.env
(XELION_MCP_AANMAKEN, XELION_MCP_BIJWERKEN, XELION_MCP_VERWIJDEREN): staat er
een uit, dan kan niemand dat, ongeacht wat hier staat.
"""
import os
import threading
import time

import yaml

PAD = os.environ.get("XELION_RECHTEN", "/config/rechten.yaml")
HERLEES_NA = 5  # seconden

RECHTEN = ("lezen", "aanmaken", "bijwerken", "verwijderen")

_cache = {"tijd": 0.0, "data": None, "fout": None}
_slot = threading.Lock()


def _noodrem(recht):
    """Lezen kent geen noodrem; de drie schrijfrechten wel."""
    if recht == "lezen":
        return True
    sleutel = "XELION_MCP_" + recht.upper()
    return os.environ.get(sleutel, "").strip().lower() in ("ja", "true", "1")


def _laden():
    with _slot:
        nu = time.time()
        if _cache["data"] is not None and nu - _cache["tijd"] < HERLEES_NA:
            return _cache["data"], _cache["fout"]
        try:
            with open(PAD, encoding="utf-8") as f:
                ruw = yaml.safe_load(f) or {}
            data = _normaliseren(ruw)
            _cache.update(tijd=nu, data=data, fout=None)
        except FileNotFoundError:
            _cache.update(tijd=nu, data={"personen": {}, "groepen": {}},
                          fout="rechtenbestand niet gevonden: " + PAD)
        except Exception as e:
            # Een kapot bestand mag nooit stilzwijgend alles openzetten.
            _cache.update(tijd=nu, data={"personen": {}, "groepen": {}},
                          fout="%s: %s" % (type(e).__name__, e))
        return _cache["data"], _cache["fout"]


def _normaliseren(ruw):
    def blok(sleutel):
        uit = {}
        for rij in (ruw.get(sleutel) or []):
            if not isinstance(rij, dict):
                continue
            naam = str(rij.get("naam") or "").strip().lower()
            if not naam:
                continue
            uit[naam] = {r: _ja(rij.get(r)) for r in RECHTEN}
        return uit
    return {"personen": blok("personen"), "groepen": blok("groepen")}


def _ja(waarde):
    if isinstance(waarde, bool):
        return waarde
    return str(waarde or "").strip().lower() in ("ja", "true", "1")


def rechten(gebruiker, groepen):
    """De effectieve rechten van deze persoon, na noodremmen.

    Persoon en groepen tellen bij elkaar op: heeft een van beide het recht,
    dan heeft de gebruiker het. De noodrem kan het daarna nog dichtzetten.
    """
    data, fout = _laden()
    naam = str(gebruiker or "").strip().lower()
    uit = {r: False for r in RECHTEN}
    bronnen = [data["personen"].get(naam)]
    for g in (groepen or []):
        bronnen.append(data["groepen"].get(str(g).strip().lower()))
    for bron in bronnen:
        if not bron:
            continue
        for r in RECHTEN:
            if bron[r]:
                uit[r] = True
    for r in RECHTEN:
        if uit[r] and not _noodrem(r):
            uit[r] = False
    return uit, fout


def mag(gebruiker, groepen, recht):
    """Toetst één recht. Roep dit aan bij ELKE tool, niet alleen bij het tonen."""
    if recht not in RECHTEN:
        raise ValueError("onbekend recht: %s" % recht)
    uit, _ = rechten(gebruiker, groepen)
    return uit[recht]


def eisen(gebruiker, groepen, recht):
    """Zelfde als mag(), maar werpt de foutmelding die de tool teruggeeft."""
    if mag(gebruiker, groepen, recht):
        return
    if not _noodrem(recht):
        raise ValueError(
            "Dit kan nu voor niemand: de noodrem XELION_MCP_%s staat uit."
            % recht.upper())
    raise ValueError(
        "Je hebt het recht '%s' niet op Xelion. Vraag het aan de beheerder; "
        "het staat in ~/xelion-config/rechten.yaml op de server." % recht)

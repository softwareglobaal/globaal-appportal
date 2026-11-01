"""Wisselkoersen van de Europese Centrale Bank, zodat de omrekening naar euro in code gebeurt en niet door het model.

De ECB publiceert elke werkdag rond 16:00 de referentiekoersen, gratis en zonder account:
https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml (1 euro = koers in de andere munt).
"""
import re
import urllib.request

BRON = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_DATUM = re.compile(r"<Cube\s+time=['\"](\d{4}-\d{2}-\d{2})['\"]")
_KOERS = re.compile(r"<Cube\s+currency=['\"]([A-Z]{3})['\"]\s+rate=['\"]([0-9.]+)['\"]")


def lees(xml):
    """(datum, {munt: koers}) uit de tekst van de ECB. Een onleesbare tekst geeft (None, {})."""
    datum = _DATUM.search(xml or "")
    koersen = {m: float(k) for m, k in _KOERS.findall(xml or "") if float(k) > 0}
    return (datum.group(1) if datum else None), koersen


def haal(timeout=15):
    """De koersen van vandaag. Een fout geeft (None, {}): de omrekening meldt dan per aanbod dat de koers ontbreekt."""
    try:
        with urllib.request.urlopen(urllib.request.Request(BRON, headers={"User-Agent": "mijnagents prijsonderzoeker"}),
                                    timeout=timeout) as antwoord:
            return lees(antwoord.read().decode("utf-8", "replace"))
    except OSError:
        return None, {}

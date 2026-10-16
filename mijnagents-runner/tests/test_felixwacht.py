"""Grendels op De Felixwacht die zonder net draaien.

Vastgezet wat Mehdi op 03-10-2026 afsprak:
- het werkgebied is een vaste lijst postcodes zonder aantallen, en elke postcode verwijst naar de
  districtnamen zoals FelixArchief ze gebruikt (2040 zoekt in Berendrecht, Zandvliet en Lillo samen);
- een appartementsgebouw draagt vaak twee nummers: August Van de Wielelei 85 en 87 staan op een perceel
  en het dossier heet "85-87". Wie op 85 zoekt moet dat bereik vinden;
- een busnummer hoort niet in de zoekopdracht bij Geopunt ("85/101" -> 85, bus 101).
"""
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import adresregister as AR  # noqa: E402
import felixarchief as FA  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, info=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  goed  {naam}")
    else:
        fout += 1
        print(f"  FOUT  {naam} {info}")


# werkgebied: de bron van de waarheid
wg = json.load(open(FA.WERKGEBIED, encoding="utf-8"))
verwacht = {"2000", "2018", "2020", "2030", "2040", "2050", "2060", "2100", "2140", "2150", "2170", "2180",
            "2600", "2610", "2660"}
check("het werkgebied telt precies de vijftien postcodes van de stad Antwerpen", set(wg["postcodes"]) == verwacht,
      str(sorted(set(wg["postcodes"]) ^ verwacht)))
def _getallen(x):
    if isinstance(x, bool):
        return []
    if isinstance(x, (int, float)):
        return [x]
    if isinstance(x, dict):
        return [g for v in x.values() for g in _getallen(v)]
    if isinstance(x, list):
        return [g for v in x for g in _getallen(v)]
    return []


check("geen aantallen in het werkgebied (die veranderen, de postcodes niet)", _getallen(wg) == [], str(_getallen(wg)[:5]))
check("2040 zoekt in Berendrecht, Zandvliet en Lillo", {"Berendrecht", "Zandvliet", "Lillo"} <= set(FA.districten_voor("2040")))
check("Kiel valt onder 2020, district Antwerpen", "Kiel" in wg["postcodes"]["2020"].get("wijken", []) and FA.districten_voor("2020") == ["Antwerpen"])
check("Borsbeek hoort erbij sinds de fusie", FA.districten_voor("2150") == ["Borsbeek"])
check("Mortsel valt buiten het werkgebied", FA.districten_voor("2640") == [])

# huisnummers zoals FelixArchief ze schrijft
check("'85-87' is een bereik", FA.nummers("85-87") == [(85, 87)])
check("'75-77-79' is een lijst van drie nummers", FA.nummers("75-77-79") == [(75, 75), (77, 77), (79, 79)])
check("'293/295' is een lijst van twee nummers", FA.nummers("293/295") == [(293, 293), (295, 295)])
check("'12A' telt als 12", FA.nummers("12A") == [(12, 12)])
check("leeg is leeg", FA.nummers("") == [])
check("85 raakt '85-87' als bereik (het appartementsgebouw van 1965)", FA.raakt("85-87", ["85", "87"]) == "bereik")
check("91 raakt '89-95'", FA.raakt("89-95", ["91"]) == "bereik")
check("85 raakt '85' exact", FA.raakt("85", ["85"]) == "exact")
check("74A raakt '74A' exact", FA.raakt("74A", ["74", "74A"]) == "exact")
check("85 raakt '185' niet", FA.raakt("185", ["85"]) is None)
check("85 raakt '81-83' niet", FA.raakt("81-83", ["85"]) is None)
check("83 is een buur van 85, 84 niet (andere kant)", FA.is_buur("83", ["85"]) and not FA.is_buur("84", ["85"]))

# busnummers eraf voor Geopunt, maar bewaard
check("'85/101' wordt 85 met bus 101", AR.splits_bus("August van de Wielelei 85/101, 2100 Deurne") ==
      ("August van de Wielelei 85, 2100 Deurne", "101"))
check("'12 bus 3' wordt 12 met bus 3", AR.splits_bus("Kerkstraat 12 bus 3, 2000 Antwerpen") == ("Kerkstraat 12, 2000 Antwerpen", "3"))
check("'12b' blijft 12b (geen bus)", AR.splits_bus("Kerkstraat 12b, 2000 Antwerpen")[1] is None)
check("een bereik '35-73' blijft staan", AR.splits_bus("Leemputstraat 35-73, 2600 Antwerpen")[1] is None)

# het districtveld van FelixArchief sluit niets uit (Frans Brandsstraat 17 in Berendrecht staat als 'Antwerpen')
check("'Frans Brandsstraat ZN' is dezelfde straat", FA._zelfde_straat("Frans Brandsstraat ZN", "Frans Brandsstraat"))
check("hoofdletters en accenten tellen niet", FA._zelfde_straat("August van de Wielelei", "August Van de Wielelei"))
check("een andere straat blijft een andere straat", not FA._zelfde_straat("Frans Brandsstraatje", "Frans Brandsstraat"))
_r = FA._markeer_district([{"district": "Antwerpen"}, {"district": "Berendrecht-Zandvliet-Lillo"}], FA.districten_voor("2040"))
check("een afwijkend district wordt gemarkeerd, niet weggegooid", len(_r) == 2 and _r[0].get("district_afwijkend") and not _r[1].get("district_afwijkend"))

# mapnamen: het inventarisnummer en het busnummer blijven leesbaar
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("felix_wacht", os.path.join(RUNNER, "felix_wacht.py"))
FW = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FW)
check("'#' blijft in een mapnaam (627#23624)", "627#23624" in FW._veilig("627#23624 bouwen: koepel?"))
check("'85/101' wordt '85 bus 101' in een mapnaam", "85 bus 101" in FW._veilig("August van de Wielelei 85/101, 2100 Deurne"))

# 17-10-2026, Codex-ronde 1 (FX01, FX03, FX04, FX11) en de metingen op Grotesteenweg 459
import percelenpas as PP  # noqa: E402
_tekst = """Een bouwovertreding is wanneer iemand zich niet aan de bouwvoorschriften houdt.

Vastgestelde bouwovertredingen

Is er een bouwovertreding? Vraag meer info via Stel je vraag > Bouwovertreding.

Uitvoeren van vergunningsplichtige werken zonder vergunning

Dossiernummer: 202410548

Registratienummer: 11002_2024_11491

Uitvoeren van vergunningsplichtige werken in strijd met vergunning

Dossiernummer: 202410548

Registratienummer: 11002_2024_11492"""
_s, _l = PP.bouwovertredingen_uit_tekst(_tekst)
check("twee bouwovertredingen worden er twee, met omschrijving (Grotesteenweg 459)", len(_l) == 2 and _l[0]["omschrijving"].startswith("Uitvoeren")
      and _l[1]["registratienummer"] == "11002_2024_11492", str(_l))
check("geen bouwovertreding blijft 'geen gekend'", PP.bouwovertredingen_uit_tekst(
    "Hieronder vind je of er bouwovertredingen gekend zijn.\nEr zijn geen gekende bouwovertredingen voor dit perceel.") == ("geen gekend", []))
check("197317935 kan als jaar 1973 en volgnummer 17935 staan", FA.schrijfwijze_mogelijk("197317935"))
check("BE/1973/B/17935 past bij 197317935", FA.past_schrijfwijze("BE/1973/B/17935", "1973", "17935"))
check("18/17935-71662 (1943) past niet", not FA.past_schrijfwijze("18/17935-71662", "1973", "17935"))
check("ZBE/2008/B/0376 past bij 2008 en 376 (voorloopnullen)", FA.past_schrijfwijze("ZBE/2008/B/0376 # 20083154", "2008", "376"))
check("214157_329#11928 is geen jaar plus volgnummer", not FA.schrijfwijze_mogelijk("214157_329#11928"))


class _NepPagina:
    """Een pagina van de percelenpas waarvan de printscreen faalt (13-10-2026, August van de Wielelei 85/101)."""
    def __init__(self):
        self.url = ""
    def goto(self, url, **k):
        self.url = url
    def wait_for_selector(self, *a, **k):
        return None
    def wait_for_timeout(self, *a):
        return None
    def get_by_role(self, *a, **k):
        raise RuntimeError("geen knop")
    def locator(self, *a, **k):
        p = self
        class _L:
            def inner_text(self_):
                if "bouwovertredingen" in p.url:
                    return "x\nBouwovertredingen\nEr zijn geen gekende bouwovertredingen voor dit perceel.\nVeelgestelde vragen"
                return "Perceel 11344A0430/00H014\nDossiernummer"
        return _L()
    def evaluate(self, script, *a, **k):
        if ".length" in script:  # de wachtlus telt de rijen van de vergunningentabel
            return 1 if "table-checkbox" in script else 0
        return [["Selecteer rij", "bouwen van een appartementsgebouw", "19654625", "Stedenbouwkundige vergunningen", "Vergunning", ""]]
    def screenshot(self, **k):
        raise RuntimeError("Page.screenshot: Timeout 30000ms exceeded.")
    def expect_download(self, **k):
        raise RuntimeError("geen download")
    def close(self):
        return None


class _NepContext:
    def new_page(self):
        return _NepPagina()


import tempfile  # noqa: E402
_stad = PP.lees(_NepContext(), 51.2, 4.47, "August Van de Wielelei 85, 2100 Antwerpen", tempfile.mkdtemp())
check("een printscreen die faalt, wist de gelezen vergunningen niet (Codex FX04)", len(_stad["vergunningen"]) == 1
      and _stad["gelezen"]["vergunningen"] and _stad["capakey"] == "11344A0430/00H014", str(_stad)[:200])
check("en de fout staat erbij", any("Vergunningen.png" in f for f in _stad["fouten"]), _stad["fouten"])

_z = {"adres": "Grotesteenweg 459, 2600 Antwerpen", "besluit": "x", "onvolledig": [], "stad": {"bouwovertredingen": "geen gekend"},
      "rijen": [{"jaar": "1967", "stad": "196716992", "onderwerp": "Verbouwingswerken", "beslissing": "",
                 "felix": [{"inventaris": "961#3952", "status": "na aanmelden"}]},
                {"jaar": "2008", "stad": "20083154", "onderwerp": "verbouwen", "beslissing": "",
                 "felix": [{"inventaris": "3290#376", "status": "download"}, {"inventaris": "3290#1260", "status": "na aanmelden"}]}],
      "downloads": [{"inventaris": "961#3952", "status": "na aanmelden", "bestanden": [], "mislukt": [], "beschermd": ["001_Kaft.pdf"]},
                    {"inventaris": "3290#376", "status": "download", "bestanden": [{"naam": "a.pdf"}], "mislukt": [], "beschermd": []},
                    {"inventaris": "3290#1260", "status": "na aanmelden", "bestanden": [], "mislukt": [], "beschermd": ["002_Plan.pdf"]}]}
_md = FW._controle_md(_z)
check("een beschermd dossier staat als 'alleen online bekijken', niet als 'nee'", "alleen online bekijken (auteursrecht)" in _md, _md)
check("een half gedownloade vergunning zegt per dossier ja of alleen online", "deels: 3290#376 ja; 3290#1260 alleen online" in _md, _md)
check("een volledige zoektocht zegt 'Volledig.'", "**Volledig.**" in _md)
_z["onvolledig"] = ["Geopunt.png niet gelukt"]
check("een onvolledige zoektocht zegt het bovenaan", "**Onvolledig:**" in FW._controle_md(_z))
_z2 = {"adres": "x", "besluit": "x", "onvolledig": [], "stad": {}, "downloads": [],
       "rijen": [{"jaar": "1965", "stad": "19654625", "onderwerp": "x", "beslissing": "",
                  "felix": [{"inventaris": "627#23624", "status": "download"}]}]}
check("zonder downloadregel is een digitaal dossier niet 'ja' (Codex FX12)", "| ja |" not in FW._controle_md(_z2), FW._controle_md(_z2))
_z2["downloads"] = [{"inventaris": "627#23624", "status": "download", "bestanden": [{"naam": "a.pdf"}], "mislukt": [], "beschermd": []}]
check("met een geslaagde downloadregel wel 'ja'", "| ja |" in FW._controle_md(_z2))
_z2["downloads"][0].update(bestanden=[], beschermd=["a.pdf"], reden="auteursrecht tot 2091")
check("beschermd toont het jaartal van FelixArchief", "alleen online bekijken (auteursrecht tot 2091)" in FW._controle_md(_z2), FW._controle_md(_z2))


class _NepFelix:
    """Een FelixArchief die een 500 geeft; het auteursrecht beslist of dat 'beschermd' of 'mislukt' wordt (Codex FX15)."""
    def __init__(self, vrij):
        self.vrij = vrij
    def status_bestand(self, url):
        return 500, "application/pdf"
    def rechten(self, url):
        return {"vrij": self.vrij, "vrij_vanaf": "2091-01-01T00:00:00" if not self.vrij else "1900-01-01"}


_f = _NepFelix(vrij=False)
try:
    FA.Felix.download(_f, "/api/files/627_31611?type=master&filename=002_Plan.pdf", "/tmp/x.pdf")
    _uit = "geen fout"
except FA.Beschermd as e:
    _uit = "beschermd: " + str(e)
except FA.BestandFout as e:
    _uit = "fout: " + str(e)
check("een 500 met auteursrecht volgens FelixArchief is 'beschermd', met jaartal", _uit == "beschermd: auteursrecht tot 2091", _uit)
_f = _NepFelix(vrij=True)
try:
    FA.Felix.download(_f, "/api/files/627_23624?type=master&filename=001_Beslissing.pdf", "/tmp/x.pdf")
    _uit = "geen fout"
except FA.Beschermd as e:
    _uit = "beschermd: " + str(e)
except FA.BestandFout as e:
    _uit = "fout: " + str(e)
check("een 500 bij een vrij dossier is een serverfout, niet 'beschermd' (Codex FX15)", _uit == "fout: 500", _uit)



class _NepFelix2:
    """Voor _downloaden: een dossier dat niet vrij is, met een gewone fout op het eerste bestand (Codex FX17)."""
    def __init__(self, fout, bestanden):
        self.fout, self.lijst, self.gedownload = fout, bestanden, []
    def bestanden(self, inv):
        return self.lijst
    def rechten(self, url):
        return {"vrij": False, "vrij_vanaf": "2091-01-01"}
    def download(self, url, pad, grootte=None):
        if self.fout and not self.gedownload and url.endswith("1"):
            raise self.fout
        self.gedownload.append(url)
        return 10


_b = [{"naam": "001.pdf", "map": "", "url": "/api/files/x?f=1", "grootte": 10},
      {"naam": "002.pdf", "map": "", "url": "/api/files/x?f=2", "grootte": 10}]
_zz = {"raak": [{"inventaris": "1#1", "status": "na aanmelden"}], "onvolledig": []}
FW._downloaden(_NepFelix2(FA.BestandFout(500), _b), _zz, tempfile.mkdtemp())
_d = _zz["downloads"][0]
check("een gewone fout op het eerste bestand maakt niet alles 'beschermd' (Codex FX17)",
      not _d["beschermd"] and len(_d["mislukt"]) == 1 and len(_d["bestanden"]) == 1, _d)
_zz = {"raak": [{"inventaris": "1#1", "status": "na aanmelden"}], "onvolledig": []}
FW._downloaden(_NepFelix2(FA.Beschermd("auteursrecht tot 2091"), _b), _zz, tempfile.mkdtemp())
_d = _zz["downloads"][0]
check("een bevestigde weigering geldt voor het hele dossier, met het jaartal", _d["beschermd"] == ["001.pdf", "002.pdf"]
      and _d["reden"] == "auteursrecht tot 2091" and not _d["mislukt"], _d)
_zz = {"raak": [{"inventaris": "1#1", "status": "download"}], "onvolledig": []}
FW._downloaden(_NepFelix2(None, []), _zz, tempfile.mkdtemp())
check("een digitaal dossier zonder bestanden is onvolledig (Codex FX19)", _zz["onvolledig"] and _zz["downloads"][0]["mislukt"], _zz)



class _NepFelix3(_NepFelix2):
    """Eerst een tijdelijke 500, daarna lukt het: het eerste bestand verdient een herkansing (Codex FX23)."""
    def __init__(self, bestanden):
        super().__init__(None, bestanden)
        self.pogingen = 0
    def download(self, url, pad, grootte=None):
        if url.endswith("1"):
            self.pogingen += 1
            if self.pogingen == 1:
                raise FA.BestandFout(500)
        self.gedownload.append(url)
        return 10


_nf = _NepFelix3(_b)
_zz = {"raak": [{"inventaris": "1#1", "status": "na aanmelden"}], "onvolledig": []}
FW._downloaden(_nf, _zz, tempfile.mkdtemp())
check("een tijdelijke fout op het eerste bestand krijgt een herkansing (Codex FX23)", _nf.pogingen == 2
      and len(_zz["downloads"][0]["bestanden"]) == 2 and not _zz["downloads"][0]["mislukt"], _zz["downloads"])
check("de wachtlus van de percelenpas telt alleen de vergunningentabel (Codex FX22)",
      "table-checkbox" in open(PP.__file__).read().split("rijen_klaar = ")[1][:200])

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

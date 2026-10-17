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



class _NepPaginaTraag(_NepPagina):
    """De sectie bouwovertredingen toont alleen de inleiding, nog geen uitkomst (Codex FX25)."""
    def locator(self, *a, **k):
        p = self
        class _L:
            def inner_text(self_):
                if "bouwovertredingen" in p.url:
                    return "x\nBouwovertredingen\nDit wordt vastgelegd in een proces-verbaal.\nVeelgestelde vragen"
                return "Perceel 11344A0430/00H014\nDossiernummer"
        return _L()


class _NepContextTraag:
    def new_page(self):
        return _NepPaginaTraag()


_stad = PP.lees(_NepContextTraag(), 51.2, 4.47, "August Van de Wielelei 85, 2100 Antwerpen")
check("zonder uitkomst bij de bouwovertredingen is die sectie niet gelezen (Codex FX25)",
      not _stad["gelezen"]["bouwovertredingen"] and any("bouwovertredingen" in f for f in _stad["fouten"]), _stad)
check("de vergunningen blijven wel gelezen", _stad["gelezen"]["vergunningen"] and len(_stad["vergunningen"]) == 1)



class _NepPaginaKop(_NepPagina):
    """Alleen de kop 'Vastgestelde bouwovertredingen', nog zonder dossierregels (Codex FX26)."""
    def locator(self, *a, **k):
        p = self
        class _L:
            def inner_text(self_):
                if "bouwovertredingen" in p.url:
                    return "x\nBouwovertredingen\nInleiding.\nVastgestelde bouwovertredingen\nVeelgestelde vragen"
                return "Perceel 11344A0430/00H014\nDossiernummer"
        return _L()


class _NepContextKop:
    def new_page(self):
        return _NepPaginaKop()


_stad = PP.lees(_NepContextKop(), 51.2, 4.47, "Grotesteenweg 459, 2600 Antwerpen")
check("de kop zonder dossierregels is geen uitkomst (Codex FX26)",
      not _stad["gelezen"]["bouwovertredingen"] and any("bouwovertredingen" in f for f in _stad["fouten"]), _stad)



class _NepPaginaLadend(_NepPagina):
    """De lijst bouwovertredingen laadt in stukken: eerst een, daarna twee (ontwerpronde 7)."""
    def __init__(self):
        super().__init__()
        self.lezingen = 0
    def locator(self, *a, **k):
        p = self
        class _L:
            def inner_text(self_):
                if "bouwovertredingen" not in p.url:
                    return "Perceel 11303C0256/00E012\nDossiernummer"
                p.lezingen += 1
                een = "Werken zonder vergunning\nDossiernummer: 202410548\nRegistratienummer: 11002_2024_11491"
                twee = een + "\nWerken in strijd met vergunning\nDossiernummer: 202410548\nRegistratienummer: 11002_2024_11492"
                lijst = een if p.lezingen == 1 else twee
                return "x\nBouwovertredingen\nInleiding.\nVastgestelde bouwovertredingen\n" + lijst + "\nVeelgestelde vragen"
        return _L()


class _NepContextLadend:
    def new_page(self):
        return _NepPaginaLadend()


_stad = PP.lees(_NepContextLadend(), 51.18, 4.43, "Grotesteenweg 459, 2600 Antwerpen")
check("een lijst die nog laadt, wordt pas aanvaard als ze stabiel is: twee overtredingen, niet een",
      _stad["gelezen"]["bouwovertredingen"] and len(_stad["bouwovertredingen_lijst"]) == 2, _stad["bouwovertredingen_lijst"])



# De keten van de stad, met echte aanvragen en antwoorden (gemeten 17-10-2026, alleen fields.content bewaard):
# parcelinfo (onze coordinaten -> perceelnummer en grens), daarna de inhoud voor die grens, per sectie.
_g = json.load(open(os.path.join(HIER, "percelenpas_grotesteenweg459_bron.json"), encoding="utf-8"))
_w = json.load(open(os.path.join(HIER, "percelenpas_wielelei85_bron.json"), encoding="utf-8"))
_inh = lambda d, s: d[s]["inhoud"]["antwoord"]  # noqa: E731
_v = PP.vergunningen_uit_bron(PP._layer_tile(_inh(_g, "vergunningen")))
check("de vergunningen komen uit het bronantwoord, met 197317935 van 13-11-1973",
      any(x["dossiernummer"] == "197317935" and x["datum"] == "13/11/1973" for x in _v) and len(_v) == 3, _v)
_s, _l = PP.bouwovertredingen_uit_bron(PP._layer_tile(_inh(_g, "bouwovertredingen")))
check("de bouwovertredingen komen uit het bronantwoord: twee, met omschrijving", _s == "2 vastgesteld" and len(_l) == 2
      and _l[1]["omschrijving"].endswith("in strijd met vergunning") and _l[1]["registratienummer"] == "11002_2024_11492", _l)
_vw = PP.vergunningen_uit_bron(PP._layer_tile(_inh(_w, "vergunningen")))
check("alle blokken tellen: Wielelei 85 heeft 5 vergunningen, 4 toelatingen voor 1962 staan in een tweede blok",
      len(_vw) == 5 and sum(x["type"] == "Toelating voor 1962" for x in _vw) == 4, [x["dossiernummer"] for x in _vw])
check("het inventarisnummer staat er een keer: 214157_329#11928, niet dubbel",
      any(x["dossiernummer"] == "214157_329#11928" for x in _vw) and not any(x["dossiernummer"].count("#") > 1 for x in _vw))
check("lege inhoud, zoals de stad ze echt stuurt, is 'geen gekend'",
      PP._layer_tile(_inh(_w, "bouwovertredingen")) == {} and PP.bouwovertredingen_uit_bron({}) == ("geen gekend", []))
check("de echte antwoorden geven geen vals alarm", not any(PP.ontbrekend_in_bron(PP._layer_tile(_inh(d, s)), s)
      for d in (_g, _w) for s in ("vergunningen", "bouwovertredingen")))
check("een toelating zonder inventaris in fileNumber krijgt '<id>_<inventaris>'",
      PP.vergunningen_uit_bron({"subLayerItems": [{"permits": [{"fileNumber": "214157", "inventoryNumber": "329#11928"}]}]})[0]["dossiernummer"]
      == "214157_329#11928")

# Codex FX28: alleen de gemeten lege vorm is 'geen'; een afwijkend antwoord wordt in zijn geheel afgewezen
_blok = lambda tile: {"value": {"layerTile": tile}}  # noqa: E731
_vorm = lambda *b: {"fields": {"content": {"content": list(b)}}}  # noqa: E731
check("een layerTile zonder subLayerItems is geen 'geen gekend'", PP._layer_tile(_vorm(_blok({}))) is None
      and PP._layer_tile(_vorm(_blok({"subLayerItems": []}))) is None)
check("een blok zonder layerTile naast een goed blok maakt het geheel onbekend",
      PP._layer_tile(_vorm(_blok({"subLayerItems": [{"permits": [{"fileNumber": "1"}]}]}), {"value": {"iets": 1}})) is None)
check("een onderdeel dat geen gegevensblok is, wordt niet stil weggefilterd (Codex ronde 9)",
      PP._layer_tile(_vorm(_blok({"subLayerItems": [{"permits": [{"fileNumber": "1"}]}, "x"]}))) is None)
check("een onbekende vorm van het antwoord is geen 'geen gekend'", PP._layer_tile({"fields": {"x": 1}}) is None)
check("een overtreding zonder dossiergegevens of met rijen die geen blok zijn, wordt gemeld",
      PP.ontbrekend_in_bron({"subLayerItems": [{"subItemTitle": "x"}]}, "bouwovertredingen")
      and PP.ontbrekend_in_bron({"subLayerItems": [{"constructionViolations": [{"violations": ["Dossiernummer: 1"]}]}]}, "bouwovertredingen")
      and PP.ontbrekend_in_bron({"subLayerItems": [{"permits": ["19654625"]}]}, "vergunningen"))
check("een overtreding met een tweede, onbekende regel wordt gemeld, niet stil weggelaten (Codex ronde 11)",
      PP.ontbrekend_in_bron({"subLayerItems": [{"subItemTitle": "x", "constructionViolations": [{"violations": [
          {"value": "Dossiernummer: 202410548"}, {"value": "Proces-verbaal: PV/2024/1"}]}]}]}, "bouwovertredingen"))
check("twee dossiernummers in een overtreding: het antwoord wordt afgewezen, niet een stil bewaard (Codex FX32)",
      PP.ontbrekend_in_bron({"subLayerItems": [{"subItemTitle": "x", "constructionViolations": [{"violations": [
          {"value": "Dossiernummer: 111"}, {"value": "Dossiernummer: 222"}]}]}]}, "bouwovertredingen")
      and not PP.ontbrekend_in_bron(PP._layer_tile(_inh(_g, "bouwovertredingen")), "bouwovertredingen"))
check("een verkaveling (allotmentPermits) die we niet lezen, wordt gemeld",
      PP.ontbrekend_in_bron({"subLayerItems": [{"subItemTitle": "Verkavelingen", "allotmentPermits": [{"fileNumber": "1"}]}]}, "vergunningen"))

# Codex FX27: het perceel. Strikt binnen de grens, en de keten parcelinfo -> inhoud moet sluiten
_vk = [{"x": 51.0 + a, "y": 4.0 + b} for a, b in ((-0.0001, -0.00015), (0.0001, -0.00015), (0.0001, 0.00015), (-0.0001, 0.00015))]
check("het Geopunt-punt ligt in de perceelgrens van de stad (Grotesteenweg 459 en Wielelei 85)",
      PP._binnen(_g["punt"], _g["vergunningen"]["parcelinfo"]["antwoord"]["geometry"])
      and PP._binnen(_w["punt"], _w["vergunningen"]["parcelinfo"]["antwoord"]["geometry"]))
check("een ander perceel telt niet: Wielelei ligt niet in de grens van Grotesteenweg",
      not PP._binnen(_w["punt"], _g["vergunningen"]["parcelinfo"]["antwoord"]["geometry"]))
check("geen marge meer: 2 m buiten de rand telt niet (Codex ronde 9)", PP._binnen((51.0, 4.0), _vk)
      and not PP._binnen((51.0001 + 2 / 110540, 4.0), _vk))
check("een punt op de grens of op een hoek is geen bevestiging (Codex ronde 11)",
      not PP._binnen((51.0001, 4.0), _vk) and not PP._binnen((51.0001, 4.00015), _vk) and not PP._binnen((51.0, 4.00015), _vk)
      and not PP._binnen((51.0001 - 0.05 / 110540, 4.0), _vk) and PP._binnen((51.0001 - 1 / 110540, 4.0), _vk))
check("de grens van parcelinfo is exact de grens in de inhoudsaanvraag (echte gegevens, beide secties)",
      all(d[s]["parcelinfo"]["antwoord"]["geometry"] == d[s]["inhoud"]["aanvraag"]["geometry"]
          for d in (_g, _w) for s in ("vergunningen", "bouwovertredingen")))


class _NepResp:
    def __init__(self, url, aanvraag, antwoord, status=200):
        self.url, self.status, self._a = url, status, antwoord
        self.request = type("Q", (), {"post_data": json.dumps(aanvraag)})()
    def json(self):
        return self._a


_PI = "https://omgeving.antwerpen.be/passthroughapi/parcelinfo"
_BU = "https://omgeving.antwerpen.be/passthroughapi/content/content-with-gis-by-slug"
_pi = lambda d, **k: _NepResp(_PI, {**d["vergunningen"]["parcelinfo"]["aanvraag"], **k}, d["vergunningen"]["parcelinfo"]["antwoord"])  # noqa: E731
_perceel, _ = PP._perceel_uit(_pi(_g), _g["punt"])
check("parcelinfo geeft het perceelnummer van de stad, voor ons Geopunt-punt", _perceel and _perceel["capakey"] == "11303C0256/00E012"
      and _perceel["adres"] == "Grotesteenweg 459, 2600 Antwerpen", _perceel)
check("parcelinfo voor een ander punt telt niet", PP._perceel_uit(_pi(_g, x="51.19"), _g["punt"])[0] is None)
check("parcelinfo waarvan de grens het punt niet bevat, telt niet", PP._perceel_uit(_pi(_g), _w["punt"])[0] is None)
check("alleen het bronantwoord van precies de eigen sectie telt",
      PP._is_bronantwoord(_NepResp(_BU, {"url": "/percelenpas/bouwovertredingen"}, {}), "bouwovertredingen")
      and not PP._is_bronantwoord(_NepResp(_BU, {"url": "/percelenpas/vergunningen"}, {}), "bouwovertredingen")
      and not PP._is_bronantwoord(_NepResp(_BU, {"url": "/percelenpas/bouwovertredingen-archief"}, {}), "bouwovertredingen")
      and not PP._is_bronantwoord(_NepResp(_PI, {"url": "/percelenpas/vergunningen"}, {}), "vergunningen"))


class _NepVangst:
    """Zoals Playwright: het filter van lees() kiest het antwoord; past er geen, dan een timeout."""
    def __init__(self, pagina, filter_):
        self._p, self._f = pagina, filter_
    def __enter__(self):
        return self
    def __exit__(self, soort, *a):
        if soort:
            return False
        for r in self._p.antwoorden_voor(self._p.url):
            if self._f(r):
                self.value = r
                return False
        raise TimeoutError('Timeout 90000ms exceeded while waiting for event "response"')


class _NepPaginaBron(_NepPagina):
    """Een pagina met de echte keten van de stad; het scherm toont de bron, tenzij een fout is ingesteld."""
    data, sectie_fout, perceel_fout, grens_fout, punt_fout, scherm_fout, extra_onderdeel = _g, False, False, False, False, False, None
    def expect_response(self, filter_, **k):
        return _NepVangst(self, filter_)
    def _sectie(self):
        return "bouwovertredingen" if "/bouwovertredingen" in self.url else "vergunningen"
    def antwoorden_voor(self, url):
        s = self._sectie()
        andere = "vergunningen" if s == "bouwovertredingen" else "bouwovertredingen"
        pi = json.loads(json.dumps(self.data[s]["parcelinfo"]))
        inh = json.loads(json.dumps(self.data[andere if self.sectie_fout else s]["inhoud"]))
        verder = lambda g: [{"x": h["x"] + 0.0009, "y": h["y"]} for h in g]  # noqa: E731  (100 m verder)
        if self.perceel_fout:  # de stad bouwt de pagina op een ander perceel
            pi["antwoord"]["geometry"] = inh["aanvraag"]["geometry"] = verder(pi["antwoord"]["geometry"])
        if self.grens_fout:  # de inhoud gaat over een andere grens dan het perceel
            inh["aanvraag"]["geometry"] = verder(inh["aanvraag"]["geometry"])
        if self.punt_fout:  # de stad zocht op een ander punt
            pi["aanvraag"]["x"] = str(float(pi["aanvraag"]["x"]) + 0.001)
        if self.extra_onderdeel and s == "vergunningen":
            inh["antwoord"]["fields"]["content"]["content"][0]["value"]["layerTile"]["subLayerItems"].append(self.extra_onderdeel)
        return [_NepResp(_PI, pi["aanvraag"], pi["antwoord"]), _NepResp(_BU, inh["aanvraag"], inh["antwoord"])]
    def _bron(self):
        return PP._layer_tile(self.data[self._sectie()]["inhoud"]["antwoord"])
    def evaluate(self, script, *a, **k):
        rijen = [["Selecteer rij", v["onderwerp"], v["dossiernummer"], v["type"], v["beslissing"], v["datum"]]
                 for v in PP.vergunningen_uit_bron(self._bron())] if self._sectie() == "vergunningen" else []
        if self.scherm_fout:
            rijen = rijen[:-1]
        if getattr(self, "besluit_fout", False) and rijen:
            rijen[0][4] = "Weigering"
        return len(rijen) if ".length" in script else rijen
    def locator(self, *a, **k):
        p = self
        class _L:
            def inner_text(self_):
                if p._sectie() == "vergunningen":
                    return "Perceel 99999X9999/99X999\nToelatingen die voor 1962"
                _, lijst = PP.bouwovertredingen_uit_bron(p._bron())
                regels = [f"{x['omschrijving']}\nDossiernummer: {x['dossiernummer']}\nRegistratienummer: {x['registratienummer']}"
                          for x in lijst]
                midden = ("Vastgestelde bouwovertredingen\n" + "\n".join(regels)) if lijst else PP.UITKOMST_GEEN + " voor dit perceel."
                return "x\nBouwovertredingen\nInleiding.\n" + midden + "\nVeelgestelde vragen"
        return _L()


def _ctx_bron(**instellingen):
    class _C:
        def new_page(self):
            p = _NepPaginaBron()
            for k, v in instellingen.items():
                setattr(p, k, v)
            return p
    return _C()


_GOED = {"perceel": True, "vergunningen_bron": True, "vergunningen_scherm": True,
         "bouwovertredingen_bron": True, "bouwovertredingen_scherm": True}
_stad = PP.lees(_ctx_bron(), *_g["punt"], "Grotesteenweg 459, 2600 Antwerpen")
check("lees() sluit de keten voor Grotesteenweg 459: 3 vergunningen, 2 overtredingen, alle controles, geen fout",
      len(_stad["vergunningen"]) == 3 and _stad["bouwovertredingen"] == "2 vastgesteld" and _stad["controles"] == _GOED
      and not _stad["fouten"], (_stad["controles"], _stad["fouten"]))
check("het perceelnummer komt uit parcelinfo, niet uit de paginatekst", _stad["capakey"] == "11303C0256/00E012", _stad["capakey"])
_stad3 = PP.lees(_ctx_bron(data=_w), *_w["punt"], "August Van de Wielelei 85, 2100 Antwerpen")
check("Wielelei 85 via lees(): 5 vergunningen, 'geen gekend' uit de bron, alle controles",
      len(_stad3["vergunningen"]) == 5 and _stad3["bouwovertredingen"] == "geen gekend" and _stad3["controles"] == _GOED
      and not _stad3["fouten"], (len(_stad3["vergunningen"]), _stad3["controles"], _stad3["fouten"]))
for _naam, _inst, _woord in (("een antwoord van een andere sectie", {"sectie_fout": True}, "kwam niet binnen"),
                             ("een pagina op een ander perceel", {"perceel_fout": True}, "niet binnen het perceel"),
                             ("inhoud voor een andere grens dan het perceel", {"grens_fout": True}, "andere perceelgrens"),
                             ("parcelinfo op een ander punt", {"punt_fout": True}, "ander punt"),
                             ("een onderdeel dat we niet lezen", {"extra_onderdeel": {"subItemTitle": "Verkavelingen",
                                                                   "allotmentPermits": [{"fileNumber": "1"}]}}, "niet lezen")):
    _s = PP.lees(_ctx_bron(**_inst), *_g["punt"], "Grotesteenweg 459, 2600 Antwerpen")
    check(f"{_naam} telt niet: scherm, onvolledig, met de reden", any(_woord in f and "niet bevestigd" in f for f in _s["fouten"])
          and _s["controles"] != _GOED, (_s["controles"], _s["fouten"]))
_s = PP.lees(_ctx_bron(besluit_fout=True), *_g["punt"], "Grotesteenweg 459, 2600 Antwerpen")
check("een scherm met hetzelfde nummer maar een ander besluit: controle mislukt (Codex FX36)",
      _s["controles"].get("vergunningen_scherm") is False and _s["controles"].get("bouwovertredingen_scherm") is True, _s["controles"])
_s = PP.lees(_ctx_bron(scherm_fout=True), *_g["punt"], "Grotesteenweg 459, 2600 Antwerpen")
check("een scherm met een rij minder dan de bron: controle mislukt en gemeld (Codex FX29)",
      _s["controles"].get("vergunningen_scherm") is False and any("niet dezelfde rijen" in f for f in _s["fouten"]), _s["fouten"])
_stad2 = PP.lees(_NepContext(), 51.2, 4.47, "August Van de Wielelei 85, 2100 Antwerpen")
check("zonder bronantwoord valt lees() terug op het scherm, onvolledig en zonder controles",
      "scherm" in _stad2["bron"].get("vergunningen", "") and any("niet bevestigd" in f for f in _stad2["fouten"])
      and not _stad2["controles"].get("perceel"), (_stad2["bron"], _stad2["controles"]))


_rv = lambda *nrs: [PP.rij_sleutel("vergunningen", {"onderwerp": "x", "dossiernummer": nr, "type": "t"}) for nr in nrs]  # noqa: E731


class _NepScherm:
    def __init__(self, rijen, tekst=""):
        self._r, self._t = list(rijen), tekst
    def locator(self, *a, **k):
        s = self
        return type("L", (), {"inner_text": lambda self_: s._t})()
    def evaluate(self, *a, **k):
        r = self._r.pop(0) if len(self._r) > 1 else self._r[0]
        return [["Selecteer rij", "x", nr, "t"] for nr in r]
    def wait_for_timeout(self, *a):
        return None


check("het scherm mag laden: pas gelijk als alle rijen er zijn", PP._scherm_gelijk(_NepScherm([[], ["1"], ["1", "2"]]), "vergunningen", _rv("1", "2")))
check("multiset: een dubbel nummer telt twee keer", not PP._scherm_gelijk(_NepScherm([["1"]]), "vergunningen", _rv("1", "1"), 3)
      and PP._scherm_gelijk(_NepScherm([["1", "1"]]), "vergunningen", _rv("1", "1"), 3))
check("hetzelfde nummer met een ander besluit op het scherm is niet gelijk (Codex FX36)",
      not PP._scherm_gelijk(_NepScherm([["1"]]), "vergunningen",
                            [PP.rij_sleutel("vergunningen", {"onderwerp": "x", "dossiernummer": "1", "type": "t", "beslissing": "Weigering"})], 3))
check("nul vergunningen telt pas als het scherm het zegt, niet zolang het leeg is (Codex FX31)",
      not PP._scherm_gelijk(_NepScherm([[]]), "vergunningen", [], 3)
      and PP._scherm_gelijk(_NepScherm([[]], "Er zijn geen vergunningen voor dit perceel."), "vergunningen", [], 3))
class _NepTabel:
    def evaluate(self, *a, **k):
        return [["Selecteer rij", "herstelling", "258982_329#18797", "Toelating voor 1962", "", "12/03/1950"],
                ["bouwen", "1", "Stedenbouwkundige vergunningen", "Vergunning", ""]]


_tr = PP._tabelrijen(_NepTabel())
check("lege cellen blijven op hun plaats: een datum schuift niet naar het besluit (Codex FX38)",
      _tr[0]["beslissing"] == "" and _tr[0]["datum"] == "12/03/1950" and _tr[1]["dossiernummer"] == "1"
      and _tr[1]["beslissing"] == "Vergunning", _tr)
check("een rij op het scherm die de bron niet kent, is ook geen gelijk", not PP._scherm_gelijk(_NepScherm([["1", "2"]]), "vergunningen", _rv("1"), 3))


# Ontwerpronde 10: de eindcontrole eist per stap een positief bewijs; een stap die zwijgt, telt als niet geslaagd
import shutil  # noqa: E402
_map = tempfile.mkdtemp()
for _f in ("Geopunt.png", "Percelenpas Antwerpen/Vergunningen.png", "Percelenpas Antwerpen/Bouwovertredingen.png",
           "Percelenpas Antwerpen/rapport_11303C0256_00E012.pdf", "FelixArchief/Overzicht.png", "FelixArchief/961#3571/a.pdf"):
    os.makedirs(os.path.dirname(os.path.join(_map, _f)), exist_ok=True)
    open(os.path.join(_map, _f), "w").write("x")


def _volledige_z():
    return {"onvolledig": [], "pand": {"lat": 51.18}, "doorzocht": ["197317935"], "controle_omgekeerd": True,
            "register": {"percelen": ["11303C0256-00E012"], "opmerkingen": []},
            "stad": {"controles": dict(_GOED), "fouten": [], "vergunningen": [{"dossiernummer": "197317935"}]},
            "raak": [{"inventaris": "961#3571", "status": "na aanmelden"}, {"inventaris": "100#1", "status": "leeszaal"}],
            "downloads": [{"inventaris": "961#3571", "aantal": 1, "mislukt": [], "beschermd": [],
                           "bestanden": [{"naam": "a.pdf", "bytes": 1, "grootte": 1, "pad": os.path.join(_map, "FelixArchief/961#3571/a.pdf")}]}]}


check("met elk bewijs: geen open punten", FW.eindcontrole(_volledige_z(), _map) == [], FW.eindcontrole(_volledige_z(), _map))
_gevallen = [
    ("zonder perceelcontrole", lambda z: z["stad"]["controles"].pop("perceel"), "perceel"),
    ("een scherm dat niet gelijk was", lambda z: z["stad"]["controles"].update(vergunningen_scherm=False), "scherm"),
    ("een vergunning die FelixArchief niet beantwoordde", lambda z: z.update(doorzocht=[]), "197317935"),
    ("een omgekeerde controle die niet afrondde", lambda z: z.pop("controle_omgekeerd"), "straat en nummer"),
    ("een opmerking van het Adressenregister (Codex FX30)", lambda z: z["register"]["opmerkingen"].append("Perceel niet op te halen: 503"), "Adressenregister"),
    ("een digitaal dossier zonder downloadregel", lambda z: z.update(downloads=[]), "961#3571"),
    ("een download met een mislukt bestand", lambda z: z["downloads"][0]["mislukt"].append("a.pdf: 500"), "961#3571"),
    ("een fout van de percelenpas", lambda z: z["stad"]["fouten"].append("PDF-rapport van de stad niet gelukt"), "PDF-rapport"),
    ("een gedownload bestand dat niet op schijf staat (Codex FX30)",
     lambda z: z["downloads"][0]["bestanden"][0].update(pad=os.path.join(_map, "weg.pdf")), "op schijf"),
    ("een bestand op schijf dat korter is dan gedownload", lambda z: z["downloads"][0]["bestanden"][0].update(bytes=999), "op schijf"),
    ("een stuk dat stil overgeslagen werd", lambda z: z["downloads"][0].update(aantal=2), "niet volledig gedownload"),
    ("een bestand korter dan FelixArchief opgeeft, ook als bytes klopt (Codex FX33)",
     lambda z: z["downloads"][0]["bestanden"][0].update(grootte=100), "op schijf"),
    ("een opgave van 0 bytes bij een bestand van 1 byte (Codex FX35)", lambda z: z["downloads"][0]["bestanden"][0].update(grootte=0), "op schijf"),
    ("een bestand zonder opgave van FelixArchief (Codex FX35)", lambda z: z["downloads"][0]["bestanden"][0].pop("grootte"), "op schijf"),
    ("een bestand dat helemaal niet op schijf staat, ook bij opgave 0", lambda z: z["downloads"][0]["bestanden"][0].update(
        grootte=0, bytes=0, pad=os.path.join(_map, "bestaat-niet.pdf")), "op schijf"),
]
for _naam, _wijzig, _woord in _gevallen:
    _z = _volledige_z()
    _wijzig(_z)
    _o = FW.eindcontrole(_z, _map)
    check(f"eindcontrole: {_naam} is een open punt", any(_woord in o for o in _o), _o)
for _f in ("Geopunt.png", "Percelenpas Antwerpen/Bouwovertredingen.png", "FelixArchief/Overzicht.png"):
    _m2 = tempfile.mkdtemp()
    shutil.copytree(_map, _m2, dirs_exist_ok=True)
    os.remove(os.path.join(_m2, _f))
    check(f"eindcontrole: zonder {os.path.basename(_f)} op schijf is het onvolledig",
          any(os.path.basename(_f) in o for o in FW.eindcontrole(_volledige_z(), _m2)))
_z = _volledige_z()
open(os.path.join(_map, "FelixArchief/961#3571/leeg.txt"), "w").close()
_z["downloads"][0]["bestanden"].append({"naam": "leeg.txt", "bytes": 0, "grootte": 0, "pad": os.path.join(_map, "FelixArchief/961#3571/leeg.txt")})
_z["downloads"][0]["aantal"] = 2
check("een leeg bestand dat FelixArchief ook als leeg opgeeft, is geen vals alarm (Codex FX37)", FW.eindcontrole(_z, _map) == [],
      FW.eindcontrole(_z, _map))
_z = _volledige_z()
_z["onvolledig"] = ["Geopunt.png niet gelukt: x"]
check("eindcontrole: wat een stap zelf meldde, blijft staan", FW.eindcontrole(_z, _map)[0] == "Geopunt.png niet gelukt: x")


class _NepFelixVU:
    afgekapt = []
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def schermafdruk_geopunt(self, adres, pad):
        open(pad, "w").write("x")


_oud = (FW.fa.Felix, FW.fa.heeft_aanmelding, FW.percelen_zoektocht)
FW.fa.Felix, FW.fa.heeft_aanmelding = _NepFelixVU, (lambda: False)
FW.percelen_zoektocht = lambda adres, felix, stadmap=None: {"adres": adres, "onvolledig": [], "pand": {"lat": 51.18, "geopunt": "x"},
                                                           "besluit": "x", "rijen": [], "raak": [], "stad": {}, "duur": {}}
try:
    _um, _zv = FW.voer_uit("Grotesteenweg 459, 2600 Antwerpen", tempfile.mkdtemp())
finally:
    FW.fa.Felix, FW.fa.heeft_aanmelding, FW.percelen_zoektocht = _oud
check("voer_uit gebruikt de eindcontrole: stappen die zwijgen, maken de zoektocht onvolledig, ook in Controle.md",
      not _zv["volledig"] and any("perceel" in o for o in _zv["onvolledig"])
      and "**Onvolledig:**" in open(os.path.join(_um, "Controle.md")).read(), _zv["onvolledig"])
_kort = os.path.join(tempfile.mkdtemp(), "kort.pdf")
open(_kort, "wb").write(b"x" * 10)
try:
    FA._volledig_op_schijf(_kort, 100)
    _gevangen = False
except FA.BestandFout:
    _gevangen = True
check("een download die korter is dan de opgave van FelixArchief, is een fout (Codex FX33)",
      _gevangen and FA._volledig_op_schijf(_kort, 10) == 10 and FA._volledig_op_schijf(_kort, None) == 10)
try:
    FA._volledig_op_schijf(_kort, 0)
    _gevangen = False
except FA.BestandFout:
    _gevangen = True
check("een opgave van 0 bytes telt ook: 10 bytes op schijf is dan een fout (Codex FX35)", _gevangen)
check("buiten het werkgebied volstaan Geopunt en het bewijs daarvan",
      FW.eindcontrole({"onvolledig": [], "pand": {"lat": 51.3}, "buiten_werkgebied": True}, _map) == [])

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

"""Grendels op De Plaudwacht v3 (verbeteropdracht v1.0, 12-10-2026, §2, §3, §4, §7, §8, §9).

De review vond: de VM las alleen vier oude inboxbestanden en meldde toch 'waakt'; het dossier werd
gekozen vóór de herkenning en `dossier:` in de kop werd genegeerd; soort=werfbezoek was onzichtbaar
voor de werfverslagvoorbereider; een fout halverwege liet de ronde vallen zonder hervatting; de
context verdween na teken 6000; een bezoekmap uit een transcriptkop werd zonder controle beschreven.

Echte keten: plaud/bouw_map.py bouwt een synthetisch archief, plaud/manifest.py maakt het manifest,
de invoer wordt gekopieerd zoals rsync doet, en De Plaudwacht draait haar ronde. Bord, Dropbox,
locatie, Pipedrive en het taalmodel zijn nagebootst; geen netwerk.
Draaien: python3 mijnagents-runner/tests/test_plaud_wacht.py
"""
import gzip
import json
import os
import shutil
import sys
import tempfile
import time
import types
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
sys.path.insert(0, os.path.join(HIER, "plaud"))
import nummerlezer  # noqa: E402
nummerlezer._standaard["codes"], nummerlezer._standaard["ts"] = nummerlezer._bouw_codes([]), time.time()   # geen register-oproep

# nagebootste Fathomwacht (herkenner, personen, deals): de Plaudwacht laadt haar pas in de ronde
FW = types.ModuleType("fathom_wacht")
sys.modules["fathom_wacht"] = FW

import bouw_map  # noqa: E402
import lijst  # noqa: E402
import manifest  # noqa: E402
import plaud_wacht as P  # noqa: E402
ECHTE_DOWNLOAD_KOP = P.bronnen.download_kop

lijst.OUDE_REPO_LIJST = Path("/nonexistent/plaud_lijst.json")

ID1, ID2, ID3 = "of_" + "1" * 32, "of_" + "2" * 32, "of_" + "3" * 32
HA = "/Work All/01. H-A WORK/0 H-A Standaard projects/5. STAN Execution"
BEZOEK = f"{HA}/2531 Fictiva/_00. Communication/2026-10-08 bezoek klant - werfbezoek"
VC = "/Work All/02. UNABO/01. U-WORK/03. U-SAFETY"
TKN_BASIS = "/Work/TKN BURO WORK/1 Projects"
TKN_MAP = f"{TKN_BASIS}/2026/47035_Proeflaan 23, 9998 Proefgem"
TKN_PLAUD = f"{TKN_MAP}/2. Plaud"
TKN_NAAM = "2026-10-08 Plaud transcript.txt"
OPENING = [{"start_time": 0, "speaker": "Speaker 1", "content": "Werfbezoek 2531 Fictiva met de aannemer."},
           {"start_time": 6000, "speaker": "Speaker 2", "content": "We lopen de ruwbouw na."}]
ZONDER_NUMMER = [{"start_time": 0, "speaker": "Speaker 1", "content": "Goedemorgen, we beginnen."},
                 {"start_time": 6000, "speaker": "Speaker 2", "content": "We lopen de werf na."}]


# ------------------------------------------------------------- nabootsing ---
class Wereld:
    def __init__(self):
        self.archief = Path(tempfile.mkdtemp(prefix="plaud-archief-"))
        self.invoer = Path(tempfile.mkdtemp(prefix="plaud-invoer-"))
        self.staat = Path(tempfile.mkdtemp(prefix="plaud-staat-"))
        self.bestanden = {}            # Dropbox: pad -> bytes
        self.ontbrekende_mappen = set()
        self.taken = []                # open zoektaken voor plaud-wacht
        self.agenda = []               # klaarzet-items soort afspraak
        self.rijen, self.klaar, self.opgepakt, self.uploads, self.logs = [], [], [], [], []
        self.fout = {}                 # soort -> aantal keer falen
        self.herkenning = {}           # plaud_id -> herkenning (of Exception)
        self.herkend = []              # (plaud_id, context, lengte transcript)
        self.deals = []
        P.INVOER, P.STAAT, P.INBOX = str(self.invoer), str(self.staat), "/inbox"
        P.bord.call = self.call
        P.bord.klaargezet_voor = lambda voor, n=100, **k: list(self.taken)
        P.bord.opgepakt = self.pak
        P.ag.klaarzet = self.klaarzet
        P.ag.log = lambda onderwerp, stap, tekst, detail="": self.logs.append((stap, tekst))
        P.bronnen.lijst = self.lijst
        P.bronnen.download = self.download
        P.bronnen.download_kop = self.download_kop
        P.bronnen.upload = self.upload
        P.bronnen.zoek_salesmap = lambda naam="", nummer="": f"/Sales/{nummer} klant" if nummer else None
        P.LC.verblijf_op = lambda moment, ook_kandidaten=False: None
        FW.herken = self.herken
        FW.personen_uit_werkwijze = lambda w: []
        self.pipedrive_fout = False
        FW.deals_index = self._deals

    def _deals(self):
        if self.pipedrive_fout:
            raise RuntimeError("Pipedrive niet bereikbaar (proef)")
        return self.deals

    def _faal(self, soort):
        if self.fout.get(soort):
            self.fout[soort] -= 1
            raise RuntimeError(f"geforceerde proeffout bij {soort}")

    def call(self, pad, payload=None, method=None):
        if pad.startswith("/api/klaarzet?") and "uniek=" in pad:
            uniek = urllib.parse.parse_qs(pad.split("?", 1)[1]).get("uniek", [""])[0]
            laatste = [dict(k, inhoud=json.dumps(k["inhoud"], ensure_ascii=False), id=i, status="klaar")
                       for i, k in enumerate(self.klaar) if k.get("uniek") == uniek][-1:]
            return {"items": laatste}
        if pad.startswith("/api/klaarzet?"):
            return {"items": list(self.agenda)}
        if pad == "/api/gesprekken":
            self._faal("tabel")
            self.rijen += payload["rijen"]
            return {"ok": True}
        if pad.startswith("/api/agent/"):
            return {"werkwijze": ""}
        raise AssertionError("onverwachte bordoproep " + pad)

    def klaarzet(self, items):
        self._faal("klaarzet")
        self.klaar += items
        return {"nieuw": len(items), "bestaand": 0}

    def pak(self, kid, door):
        self.opgepakt.append(kid)
        self.taken = [t for t in self.taken if t["id"] != kid]

    def lijst(self, pad, recursief=False):
        if pad in self.ontbrekende_mappen:
            return None
        uit = []
        for p in self.bestanden:
            if os.path.dirname(p) == pad.rstrip("/"):
                uit.append({".tag": "file", "name": os.path.basename(p), "path_display": p, "path_lower": p.lower()})
        return uit

    def download(self, pad, maximum=25_000_000):
        """Dropbox is hoofdletterongevoelig: path_lower vindt het bestand."""
        data = next(v for k, v in self.bestanden.items() if k.lower() == pad.lower())
        if len(data) > maximum:
            raise RuntimeError("downloadgrens overschreden")
        return data

    def download_kop(self, pad, n):
        """Een Range-download geeft alleen de gevraagde kop terug."""
        return next(v for k, v in self.bestanden.items() if k.lower() == pad.lower())[:n]

    def upload(self, pad, data):
        self._faal("upload:" + ("bezoek" if "/Work All/" in pad else "dossier"))
        self.uploads.append(pad)
        self.bestanden[pad] = data
        return pad

    def herken(self, g, tekst, personen, deal, hoe, context=None, bron="fathom"):
        pid = g["recording_id"]
        self.herkend.append((pid, context, len(tekst)))
        h = self.herkenning.get(pid, {"personen": ["aannemer"], "hoofdpersoon": "aannemer", "bedrijf": "", "afdeling": "h-architects",
                                      "thema": "werfbezoek ruwbouw", "project": "2531 Fictiva", "prive": False,
                                      "zekerheid": "hoog", "waarom": "openingszin"})
        if isinstance(h, Exception):
            raise h
        return dict(h)

    # --- archief en invoer via de echte keten ---
    def opname(self, pid, naam, start_at, minuten=40, uitingen=OPENING, transcript=True):
        def haler(url, max_bytes, timeout):
            return gzip.compress(json.dumps(uitingen).encode()) if "transcript" in url else b"OggS" + b"\0" * 3000
        o = {"id": pid, "name": naam, "start_at": start_at, "duration": minuten * 60000, "presigned_url": "https://proef/audio"}
        if transcript:
            o["transcript_link"] = "https://proef/transcript"
        r = bouw_map.bouw(o, self.archief, haler=haler)
        assert r["status"] in ("compleet", "wacht_op_transcript"), r
        return r

    def push(self, gemaakt=None):
        """Zoals plaud_invoer_push.sh: alleen manifest, status en transcript.json."""
        manifest.bouw(self.archief)
        for p in self.archief.rglob("*"):
            if p.is_file() and (p.name in ("00 manifest.json", "00 status.json") or p.name == "transcript.json"):
                doel = self.invoer / p.relative_to(self.archief)
                doel.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, doel)
        if gemaakt:
            m = json.loads((self.invoer / "00 manifest.json").read_text())
            m["meta"]["gemaakt"] = gemaakt
            (self.invoer / "00 manifest.json").write_text(json.dumps(m))

    def ronde(self):
        r = types.SimpleNamespace(noden=[], detail="")
        r.nood = lambda tekst, wie="mehdi": r.noden.append(tekst)
        code, tellers = P.ronde(r)
        return code, tellers, r.noden


def werftaak(kid, dossier="2531", datum="2026-10-08", bezoekmap=BEZOEK):
    return {"id": kid, "soort": "taak", "van": "werfverslag-voorbereider", "uniek": f"werf:{dossier}:{datum}:plaud-wacht",
            "inhoud": json.dumps({"dossier": dossier, "datum": datum, "adres": "Proefstraat 1", "bezoekmap": bezoekmap,
                                  "volgnr": 1, "nr_label": "WB1", "soort_bezoek": "werfbezoek"})}


def cctaak(kid, van, tot, bezoekmap, dossier="2531", datum="2026-10-08", soort="veiligheidscoordinatie"):
    return {"id": kid, "soort": "taak", "van": "commandocentrum", "uniek": f"cc:{kid}:plaud-wacht",
            "inhoud": json.dumps({"dossier": dossier, "datum": datum, "adres": "Proefstraat 1", "bezoekmap": bezoekmap,
                                  "van_tijd": van, "tot_tijd": tot, "verslagsoort": soort})}


def tkn_taak(kid=701, **wijzigingen):
    taak = cctaak(kid, "09:00", "10:00", TKN_MAP, dossier="3999", soort="barsten-scheuren")
    inhoud = json.loads(taak["inhoud"])
    inhoud.update(mapnummer="47035", plaud_doelmap=TKN_PLAUD, transcriptnaam=TKN_NAAM, firma="UNAB")
    inhoud.update(wijzigingen)
    taak["inhoud"] = json.dumps(inhoud)
    return taak


def in_bezoekmap(w):
    return [p for p in w.uploads if p.startswith("/Work All/")]


# ------------------------------------------------------------------ proeven ---
def test_van_bron_tot_tabel_klaarzet_en_bezoekmap_en_een_tweede_ronde_zonder_dubbel():
    w = Wereld()
    w.deals = [{"id": 777, "titel": "2531 Fictiva", "nummer": "2531"}]
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")      # 11:05 in Brussel
    w.push()
    w.taken = [werftaak(101)]
    code, tel, noden = w.ronde()
    assert code == P.OK and tel["gedaan"] == 1, (code, tel, noden)
    assert [r["uniek"] for r in w.rijen] == [f"plaud:{ID1}"] and w.rijen[0]["datum"] == "2026-10-08" and w.rijen[0]["start"] == "11:05"
    k = w.klaar[0]
    assert k["soort"] == "transcript" and k["sleutel"] == "2531" and k["voor"] == "h-architects", k
    assert k["inhoud"]["deal_id"] == 777 and k["inhoud"]["projectnummer"] == "2531" and k["inhoud"]["verslagsoort"] == "werfverslag"
    assert k["inhoud"]["opgenomen_door"] == "onbekend", "gedeeld account bewijst niet wie opnam"
    assert in_bezoekmap(w) == [f"{BEZOEK}/transcript.txt"], w.uploads
    assert w.bestanden[f"{BEZOEK}/transcript.txt"].startswith(f"plaud_id: {ID1}".encode())
    assert w.opgepakt == [101] and len(w.uploads) == 2, (w.opgepakt, w.uploads)          # bezoekmap en dossierkopie
    assert len(w.herkend) == 1
    # tweede ronde: geen dubbel
    code, tel, _ = w.ronde()
    assert code == P.OK and len(w.rijen) == 1 and len(w.klaar) == 1 and len(w.uploads) == 2 and len(w.herkend) == 1, (tel, w.uploads)
    st = json.loads((w.staat / f"{ID1}.json").read_text())
    assert any(o["sleutel"] == "bezoekmap:101" and o["gedaan"] for o in st["opdrachten"]), "levering blijft geschiedenis"


def test_geforceerde_fouten_en_een_geslaagde_hervatting():
    w = Wereld()
    w.deals = [{"id": 777, "titel": "2531 Fictiva", "nummer": "2531"}]
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    w.push()
    w.taken = [werftaak(101)]
    w.fout = {"tabel": 1, "klaarzet": 1, "upload:dossier": 1, "upload:bezoek": 1}
    code, tel, _ = w.ronde()
    assert code == P.DEELS and tel["fouten"] == 4, (code, tel)
    assert not w.rijen and not w.klaar and not w.uploads and not w.opgepakt, "niets gedaan, niets afgevinkt"
    st = json.loads((w.staat / f"{ID1}.json").read_text())
    assert len([o for o in st["opdrachten"] if not o["gedaan"] and o["pogingen"] == 1]) == 4, st["opdrachten"]
    code, tel, _ = w.ronde()
    assert code == P.OK, (code, tel)
    assert len(w.rijen) == 1 and len(w.klaar) == 1 and len(w.uploads) == 2 and w.opgepakt == [101]
    assert len(w.herkend) == 1, "de hervatting vraagt het model niet opnieuw"


def test_later_toegevoegde_bezoekmap_wordt_alsnog_geleverd():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    w.push()
    w.ronde()
    assert not in_bezoekmap(w)
    w.taken = [werftaak(102)]
    code, _, _ = w.ronde()
    assert code == P.OK and in_bezoekmap(w) == [f"{BEZOEK}/transcript.txt"] and w.opgepakt == [102]
    assert len(w.herkend) == 1 and len({k["uniek"] for k in w.klaar}) == 1 and w.klaar[-1]["voor"] == "h-architects"


def test_een_fout_bij_de_tweede_opname_blokkeert_de_eerste_niet():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    w.opname(ID2, "10-08 Telefoon", "2026-10-08T13:00:00")
    w.push()
    w.herkenning[ID2] = RuntimeError("model weigert")
    code, tel, _ = w.ronde()
    assert code == P.DEELS and tel["gedaan"] == 1 and tel["fout"] == 1, tel
    assert [r["uniek"] for r in w.rijen] == [f"plaud:{ID1}"]


def test_titel_en_kop_in_conflict_geven_geen_kopie_en_gaan_naar_mehdi():
    w = Wereld()
    w.deals = [{"id": 777, "titel": "2531 Fictiva", "nummer": "2531"}]
    w.bestanden["/inbox/2026-10-09 1400 Plaud transcript.md"] = (
        f"plaud_id: {ID3}\nstart: 2026-10-09 14:00\nduur_minuten: 30\nnaam_in_plaud: Werfbezoek 2531\ndossier: 2612\n"
        f"bezoekmap: {BEZOEK}\n\n[00:00:00] Speaker 1: we bespreken de ruwbouw\n").encode()
    w.taken = [werftaak(103, datum="2026-10-09", bezoekmap=BEZOEK.replace("2026-10-08", "2026-10-09"))]
    code, tel, noden = w.ronde()
    k = w.klaar[0]
    assert k["voor"] == "mehdi" and k["inhoud"]["conflict"] and "NAKIJKEN" in k["titel"], k
    assert w.uploads == [] and w.opgepakt == [], "geen zakelijke kopie en geen bezoekmap bij een conflict"
    assert code == P.INVOER_FOUT and any("invoer van de Mac ontbreekt" in n for n in noden), noden


def test_onbekende_afdeling_of_lage_zekerheid_blijft_bij_mehdi():
    w = Wereld()
    w.deals = [{"id": 777, "titel": "2531 Fictiva", "nummer": "2531"}]
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    w.push()
    w.herkenning[ID1] = {"personen": [], "hoofdpersoon": "", "bedrijf": "", "afdeling": "onbekend", "thema": "", "project": "",
                         "prive": False, "zekerheid": "laag", "waarom": ""}
    w.taken = [werftaak(601)]                     # een geldige zoektaak maakt de grens niet ruimer (nacontrole v1.1, P1-2)
    w.ronde()
    assert w.klaar[0]["voor"] == "mehdi" and not w.uploads and not w.opgepakt, (w.klaar[0]["voor"], w.uploads, w.opgepakt)
    assert any("niet geleverd" in l[1] for l in w.logs), "een afgewezen levering laat de taak open met reden"


def test_tegenstrijdige_privevelden_leveren_niets():
    w = Wereld()
    w.deals = [{"id": 777, "titel": "2531 Fictiva", "nummer": "2531"}]
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    w.push()
    w.taken = [werftaak(602)]
    w.herkenning[ID1] = {"personen": ["Angela"], "hoofdpersoon": "Angela", "bedrijf": "", "afdeling": "prive", "thema": "weekend",
                         "project": "", "prive": False, "zekerheid": "hoog", "waarom": ""}
    w.ronde()
    assert w.klaar[0]["voor"] == "mehdi" and not w.uploads and not w.opgepakt, (w.klaar[0], w.uploads)


def test_pipedrive_herstel_geeft_herbeoordeling_zonder_nieuwe_modelvraag():
    w = Wereld()
    w.deals = [{"id": 777, "titel": "2531 Fictiva", "nummer": "2531"}]
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00", uitingen=ZONDER_NUMMER)
    w.push()
    w.pipedrive_fout = True
    w.ronde()
    assert w.klaar[-1]["voor"] == "mehdi", w.klaar[-1]
    w.pipedrive_fout = False
    code, tel, _ = w.ronde()
    assert w.klaar[-1]["voor"] == "h-architects" and w.klaar[-1]["sleutel"] == "2531", (tel, w.klaar[-1])
    assert len(w.herkend) == 1, "bronherstel vraagt het model niet opnieuw"


def test_gewijzigde_titel_bij_gelijk_transcript_herkent_opnieuw():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    w.push()
    w.ronde()
    w.opname(ID1, "10-08 PRIVE Angela en Mehdi weekend", "2026-10-08T09:05:00")
    w.push()
    w.herkenning[ID1] = {"personen": ["Angela"], "hoofdpersoon": "Angela", "bedrijf": "", "afdeling": "prive", "thema": "weekend",
                         "project": "", "prive": True, "zekerheid": "hoog", "waarom": ""}
    w.ronde()
    assert len(w.herkend) == 2, "een andere titel is andere modelinput"
    assert w.klaar[-1]["voor"] == "mehdi" and w.klaar[-1]["inhoud"]["prive"], w.klaar[-1]


def test_gewijzigd_transcript_wordt_als_nieuwe_versie_geleverd():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    w.push()
    w.taken = [werftaak(603)]
    w.ronde()
    oud = w.bestanden[f"{BEZOEK}/transcript.txt"]
    nieuw = OPENING + [{"start_time": 9000, "speaker": "Speaker 1", "content": "Aanvulling na hertranscriptie."}]
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00", uitingen=nieuw)
    w.push()
    w.taken = [werftaak(603)]
    w.ronde()
    assert w.bestanden[f"{BEZOEK}/transcript.txt"] == oud, "het bestaande transcript wordt niet overschreven"
    versies = [p for p in w.bestanden if p.startswith(BEZOEK + "/transcript") and p != f"{BEZOEK}/transcript.txt"]
    assert len(versies) == 1 and b"Aanvulling na hertranscriptie" in w.bestanden[versies[0]], versies
    assert b"transcript_hash:" in w.bestanden[versies[0]]


def test_voorbereider_telt_alleen_het_toegestane_harc_transcript():
    import werfverslag_voorbereider as V
    goed = {"soort": "transcript", "van": "plaud-wacht", "voor": "h-architects", "sleutel": "2531", "titel": "Plaud: werfbezoek",
            "uniek": "plaud:of_a", "inhoud": json.dumps({"datum": "2026-10-08", "firma": "HARC", "projectnummer": "2531",
                                                         "prive": False, "conflict": False, "zekerheid": "middel"})}
    varianten = [dict(goed, uniek="plaud:of_b", inhoud=json.dumps({**json.loads(goed["inhoud"]), "firma": "UNAB"})),
                 dict(goed, uniek="plaud:of_c", voor="mehdi", inhoud=json.dumps({**json.loads(goed["inhoud"]), "prive": True})),
                 dict(goed, uniek="plaud:of_d", voor="mehdi", inhoud=json.dumps({**json.loads(goed["inhoud"]), "zekerheid": "laag"})),
                 dict(goed, uniek="plaud:of_e", voor="mehdi", inhoud=json.dumps({**json.loads(goed["inhoud"]), "conflict": True})),
                 {"soort": "werfbezoek", "van": "plaud-wacht", "voor": "mehdi", "sleutel": "2531", "titel": "2026-10-08 Plaud: x · PRIVÉ",
                  "uniek": "plaud:of_f", "inhoud": json.dumps({"datum": "2026-10-08", "prive": True})}]
    oud_call = V.bord.call
    V.bord.call = lambda pad, payload=None, method=None: {"items": [goed] + varianten}
    try:
        per = V.klaargezet("2531")
    finally:
        V.bord.call = oud_call
    assert [t["uniek"] for t in per["transcript"]] == ["plaud:of_a"], [t["uniek"] for t in per["transcript"]]


def test_los_verslag_krijgt_een_gedateerde_momentmap_als_taakdoel():
    import werfverslag_voorbereider as V
    los = {"map": "/Work All/01. H-A WORK/0 H-A Light projects/5. H-A light SITE VISITS/2416 Kapellen/4. Uitvoering & werfcontrole/4. Werfverslagen",
           "datum": "2026-08-22", "bron_map": "los verslag"}
    doel = V.taakdoel(los)
    assert doel == los["map"] + "/20260822", doel
    taak = {"id": 701, "soort": "taak", "van": "werfverslag-voorbereider",
            "inhoud": json.dumps({"dossier": "2416", "datum": "2026-08-22", "bezoekmap": doel})}
    assert P.zoektaak.valideer_bezoekmap(taak, P.verslagsoorten.SOORTEN)[0], "het nieuwe doel is een geldige bezoekmap"
    taak_oud = dict(taak, inhoud=json.dumps({"dossier": "2416", "datum": "2026-08-22", "bezoekmap": los["map"]}))
    assert not P.zoektaak.valideer_bezoekmap(taak_oud, P.verslagsoorten.SOORTEN)[0], "de verzamelmap blijft ongeldig"
    gewoon = dict(los, bron_map="_00. communication", map=BEZOEK)
    assert V.taakdoel(gewoon) == BEZOEK


def test_verzoek_van_de_contractmaker_vraagt_een_overlappende_afspraak():
    """Live 12-10-2026: Nelleke Stropke, plaatsbezoek 1 oktober 20:00-21:00; de enige opname die dag was om 09:31."""
    w = Wereld()
    w.opname(ID1, "10-01 Vergadering renovatie woning", "2026-10-01T07:31:00")
    w.push()
    w.agenda = [{"soort": "afspraak", "titel": "stropke", "inhoud": json.dumps({"titel": "!! Mehdi: [HARC-PB] Nelleke Stropke, Vossenstraat 2",
                 "start": "2026-10-01T20:00:00+02:00", "einde": "2026-10-01T21:00:00+02:00", "firma": "HARC"})}]
    verzoek = {"id": 1935, "soort": "verzoek", "van": "contracten-agent", "sleutel": "14543", "uniek": "verzoek:14543:2026-10-01:plaatsbezoek",
               "titel": "Nelleke Stropke: bewijs van 2026-10-01 plaatsbezoek ontbreekt", "inhoud": "Dossier Nelleke Stropke (deal 14543)."}
    w.taken = [verzoek]
    w.ronde()
    assert any("niet_gevonden: geen Plaud-opname rond de afspraak met Nelleke Stropke" in l[1] for l in w.logs), w.logs
    assert not w.uploads and not w.opgepakt
    w2 = Wereld()
    w2.opname(ID2, "10-01 Plaatsbezoek", "2026-10-01T18:05:00")              # 20:05 in Brussel
    w2.push()
    w2.agenda, w2.taken = w.agenda, [verzoek]
    code, tel, noden = w2.ronde()
    assert any("ter_beoordeling" in l[1] for l in w2.logs) and any("Contractmaker" in n for n in noden), (w2.logs, noden)
    assert not w2.uploads and not w2.opgepakt, "De Plaudwacht levert niet zelf voor een verzoek"


def test_id_conflict_in_het_manifest_publiceert_niets():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    eerste = next(w.archief.glob("*/gesprek.json")).parent
    tweede = w.archief / "2026-10-08 1105 tweede exemplaar"
    shutil.copytree(eerste, tweede)
    (tweede / "transcript.json").write_text(json.dumps(ZONDER_NUMMER))
    w.push()
    w.taken = [werftaak(604)]
    code, tel, noden = w.ronde()
    assert not w.rijen and not w.klaar and not w.uploads, (w.rijen, w.klaar, w.uploads)
    assert tel["herstel"] >= 1 and any("conflict" in n.lower() for n in noden), (tel, noden)


def test_een_bouwjaar_in_de_titel_is_geen_dossier():
    """Live gezien op 12-10-2026: "Renovatieplan vrijstaande woning 1933" werd HARC:1933 en ging naar h-architects."""
    w = Wereld()
    w.deals = [{"id": 777, "titel": "2531 Fictiva", "nummer": "2531"}]
    w.opname(ID1, "10-01 Vergadering Renovatieplan vrijstaande woning 1933 - dakvernieuwing", "2026-10-01T07:31:00", uitingen=ZONDER_NUMMER)
    w.push()
    w.herkenning[ID1] = {"personen": [], "hoofdpersoon": "eigenaar", "bedrijf": "", "afdeling": "h-architects", "thema": "renovatie",
                         "project": "", "prive": False, "zekerheid": "middel", "waarom": ""}
    w.ronde()
    k = w.klaar[0]
    assert k["voor"] == "mehdi" and k["sleutel"] == "" and k["inhoud"]["zekerheid"] == "laag" and not w.uploads, k
    assert any("niet bekend" in r or "genegeerd" in r for r in k["inhoud"]["redenen"]), k["inhoud"]["redenen"]


def test_harc_9998_bereikt_de_werfverslagketen_met_een_andere_deal_id():
    w = Wereld()
    w.deals = [{"id": 555, "titel": "9998 Proefwerf", "nummer": "9998"}]
    w.opname(ID1, "10-08 opname", "2026-10-08T09:05:00", uitingen=ZONDER_NUMMER)
    w.push()
    bezoek = f"{HA}/9998 Proefwerf/_00. Communication/2026-10-08 bezoek klant - werfbezoek"
    w.taken = [werftaak(104, dossier="9998", bezoekmap=bezoek)]
    # eigen bewijs van de opname: een afspraak die het opnametijdstip overlapt (de taak alleen is geen bewijs)
    w.agenda = [{"soort": "afspraak", "titel": "werf", "inhoud": json.dumps({"titel": "HA 9998 werfbezoek", "start": "2026-10-08T11:00:00+02:00",
                                                                             "einde": "2026-10-08T12:00:00+02:00", "firma": "HARC", "nummer": "9998"})}]
    w.herkenning[ID1] = {"personen": [], "hoofdpersoon": "aannemer", "bedrijf": "", "afdeling": "h-architects", "thema": "werfbezoek",
                         "project": "", "prive": False, "zekerheid": "middel", "waarom": ""}
    w.ronde()
    k = w.klaar[0]
    assert k["sleutel"] == "9998" and k["inhoud"]["deal_id"] == 555, k
    import werfverslag_voorbereider as V
    oud = V.bord.call
    item = {**k, "van": "plaud-wacht", "inhoud": json.dumps(k["inhoud"])}
    legacy = {"soort": "werfbezoek", "van": "plaud-wacht", "sleutel": "31337", "titel": "2026-10-08 11:05 Plaud: werf 9998",
              "inhoud": json.dumps({"datum": "2026-10-08"})}
    V.bord.call = lambda pad, payload=None, method=None: {"items": [item, legacy]}
    try:
        per = V.klaargezet("9998")
    finally:
        V.bord.call = oud
    assert len(per["transcript"]) == 2 and all(V.dag_van(t) == "2026-10-08" for t in per["transcript"]), per["transcript"]


def test_context_alleen_overlappende_agenda_ook_na_teken_6000():
    w = Wereld()
    lang = [{"start_time": 0, "speaker": "Speaker 1", "content": "Goedemorgen."}] + \
           [{"start_time": 70000 + i * 1000, "speaker": "Speaker 2", "content": "ruwbouw " * 40} for i in range(60)]
    w.deals = [{"id": 777, "titel": "2531 Fictiva", "nummer": "2531"}, {"id": 778, "titel": "2612 Ander", "nummer": "2612"}]
    w.opname(ID1, "10-08 opname", "2026-10-08T09:05:00", uitingen=lang)
    w.push()
    w.agenda = [{"soort": "afspraak", "titel": "vroeger", "inhoud": json.dumps({"titel": "HA 2612 vroeger", "start": "2026-10-08T08:00:00+02:00",
                                                                                "einde": "2026-10-08T09:00:00+02:00", "firma": "HARC", "nummer": "2612"})},
                {"soort": "afspraak", "titel": "nu", "inhoud": json.dumps({"titel": "HA 2531 werfbezoek", "start": "2026-10-08T11:00:00+02:00",
                                                                           "einde": "2026-10-08T12:00:00+02:00", "firma": "HARC", "nummer": "2531"})}]
    w.ronde()
    pid, ctx, lengte = w.herkend[0]
    assert lengte > 6000, lengte
    assert [a["nummer"] for a in ctx["agenda_overlappend"]] == ["2531"], ctx
    assert "openingszin" in ctx["openingszin_regel"].lower() and "niet bewezen" in ctx["let_op"]
    assert w.klaar[0]["sleutel"] == "2531", "de overlappende afspraak is bewijs, de vroegere niet"


def test_ongeldige_bezoekmappen_krijgen_niets():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    w.push()
    zonder_id = werftaak(0)
    zonder_id.pop("id")
    w.taken = [werftaak(201, bezoekmap="/Privé/Mehdi/2026-10-08"),                                      # willekeurig pad
               werftaak(202, bezoekmap=f"{HA}/2531 Fictiva/../../../Privé/2026-10-08"),               # ..
               werftaak(203, bezoekmap=BEZOEK.replace("2026-10-08 bezoek", "2026-10-01 bezoek")),        # andere dag
               werftaak(204, bezoekmap=BEZOEK.replace("2531 Fictiva", "2612 Andere")),                # ander dossier
               cctaak(205, "11:00", "12:00", BEZOEK),                                                     # firma van VC, pad van H-A
               zonder_id]
    code, _, noden = w.ronde()
    assert not in_bezoekmap(w) and not w.opgepakt, w.uploads
    assert any("ongeldige bezoekmap" in n for n in noden), noden
    assert len([l for l in w.logs if "zoektaak niet uitgevoerd" in l[1]]) == 6


def test_dezelfde_dag_is_geen_bevestiging_het_tijdstip_wel():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T07:00:00")     # 09:00 in Brussel
    w.opname(ID2, "10-08 VC bezoek", "2026-10-08T12:00:00")                         # 14:00 in Brussel
    w.push()
    w.taken = [werftaak(301)]
    code, _, noden = w.ronde()
    assert not in_bezoekmap(w) and not w.opgepakt and any("meer passende opnames" in n for n in noden), (w.uploads, noden)
    vc = f"{VC}/2531 Proefwerf/2026-10-08 bezoek werf - veiligheidscoördinatie"
    w2 = Wereld()
    w2.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T07:00:00")
    w2.opname(ID2, "10-08 VC bezoek", "2026-10-08T12:00:00", uitingen=ZONDER_NUMMER)
    w2.push()
    w2.taken = [cctaak(302, "14:00", "15:00", vc)]
    w2.herkenning[ID2] = {"personen": [], "hoofdpersoon": "aannemer", "bedrijf": "", "afdeling": "unabo", "thema": "veiligheid",
                          "project": "", "prive": False, "zekerheid": "middel", "waarom": ""}
    w2.ronde()
    assert in_bezoekmap(w2) == [f"{vc}/transcript.txt"] and w2.opgepakt == [302], w2.uploads
    assert f"plaud_id: {ID2}".encode() in w2.bestanden[f"{vc}/transcript.txt"]


def test_een_enkele_opname_op_de_bezoekdag_zonder_bewijs_wordt_niet_geleverd():
    """Taak 410 (dossier 2324, 2 juni 2026): één opname die dag, zonder nummer in titel of openingszin."""
    w = Wereld()
    w.opname(ID1, "10-08 Vergadering dakterras", "2026-10-08T08:06:00", uitingen=ZONDER_NUMMER)
    w.push()
    w.taken = [werftaak(410, dossier="2324", bezoekmap=f"{HA}/2324 Proefdorp/_00. Communication/2026-10-08 bezoek klant - werfbezoek")]
    w.ronde()
    assert not in_bezoekmap(w) and not w.opgepakt, w.uploads
    assert any("dezelfde dag alleen is geen bevestiging" in l[1] for l in w.logs), w.logs


def test_een_ander_transcript_in_de_bezoekmap_wordt_niet_overschreven():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    w.push()
    w.bestanden[f"{BEZOEK}/transcript.txt"] = b"plaud_id: of_ffffffffffffffffffffffffffffffff\n\nander gesprek"
    w.taken = [werftaak(401)]
    code, _, _ = w.ronde()
    assert code == P.DEELS and not in_bezoekmap(w) and not w.opgepakt
    assert w.bestanden[f"{BEZOEK}/transcript.txt"].endswith(b"ander gesprek")


def test_wachtend_transcript_laat_de_taak_open():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00", transcript=False)
    w.push()
    w.taken = [werftaak(501)]
    code, tel, _ = w.ronde()
    assert tel["wacht_op_transcript"] == 1 and not w.uploads and not w.opgepakt and not w.herkend, tel
    assert tel["wacht_op_transcript_archief"] == 1


def test_oude_inboxbestanden_zijn_geen_gezonde_aanvoer():
    w = Wereld()
    for i in range(4):
        w.bestanden[f"/inbox/oud {i}.md"] = (f"plaud_id: {'4' * 31}{i}\nstart: 2026-09-1{i} 10:00\nnaam_in_plaud: oud {i}\n\ntekst").encode()
    w.bestanden["/inbox/zonder tijd.md"] = f"plaud_id: {'5' * 32}\nnaam_in_plaud: zonder tijd\n\ntekst".encode()
    code, tel, noden = w.ronde()
    assert code == P.INVOER_FOUT and any("invoer van de Mac ontbreekt" in n for n in noden), (code, noden)
    assert tel["herstel"] == 1, "zonder opnametijd: herstel, nooit de wijzigingsdatum"
    assert not w.klaar, "oude opnames van vóór de grens worden niet opnieuw gepubliceerd"


def test_verouderde_invoer_en_aanmeldfout_worden_gemeld():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    (w.archief / "00 status.json").write_text(json.dumps({"uitkomst": "authfout"}))
    w.push(gemaakt=(datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(timespec="seconds"))
    code, _, noden = w.ronde()
    assert code == P.INVOER_FOUT, code
    assert any("ouder dan drie uur" in n for n in noden) and any("aanmelding" in n.lower() for n in noden), noden
    assert not any(n[:1].isdigit() for n in noden), "N10: geen teller vooraan"
    assert not any("stil" in n.lower() for n in noden)


def test_planning_heeft_slot_en_tijdslimiet_en_vervangt_alleen_de_oude_regel():
    sys.path.insert(0, os.path.join(HIER, "planning"))
    import plaud_cron_zetten as Z
    regels = open(os.path.join(HIER, "planning", "plaud.cron"), encoding="utf-8").read().splitlines()
    actief = [r for r in regels if r.strip() and not r.startswith("#")]
    assert len(actief) == 1 and "flock -n" in actief[0] and "timeout 3000" in actief[0] and "plaud_wacht.py" in actief[0]
    doel, oud = Z.samenvoegen(["5 * * * * iets anders", Z.OUDE_REGEL], regels)
    assert oud == 1 and "5 * * * * iets anders" in doel and Z.OUDE_REGEL not in doel
    assert Z.samenvoegen(doel, regels)[0] == doel, "idempotent"
    try:
        Z.samenvoegen(["0 * * * * python mijnagents-runner/plaud_wacht.py --iets"], regels)
        raise AssertionError("een onbekende plaud-regel moet eerst beoordeeld worden")
    except ValueError:
        pass
    plist = open(os.path.join(HIER, "planning", "mac", "be.globaal.plaud.ophalen.plist"), encoding="utf-8").read()
    assert "plaud_invoer_push.sh" in plist and "<key>Minute</key><integer>5</integer>" in plist
    sync = open(os.path.join(HIER, "planning", "mac", "data_uit_mehdi_sync.sh"), encoding="utf-8").read()
    assert "\nhaal plaud " not in sync, "de oude VM-map Plaud gaat niet meer naar het archief op de Mac (één archief)"
    push = open(os.path.join(HIER, "plaud", "plaud_invoer_push.sh"), encoding="utf-8").read()
    assert "--delete" not in push.replace("nooit --delete", "") and "--include='transcript.json'" in push and "--exclude='*'" in push


def test_bron_houdt_de_grenzen():
    bron = open(os.path.join(HIER, "plaud_wacht.py"), encoding="utf-8").read()
    assert "client_modified" not in bron.split('"""', 2)[2], "nooit de wijzigingsdatum als opnametijd"
    assert "urllib.request" not in bron and "audio_url" not in bron, "de VM haalt geen links op"
    assert "tekst[:6000] + " not in bron
    assert '"werfbezoek" if' not in bron
    assert "kop.get(\"bezoekmap\")" not in bron, "een pad in een transcriptkop is geen schrijfrecht"


def test_dropbox_koplezer_leest_alleen_range_bij_200_en_206():
    data = b"Plaud-ID: of_" + b"a" * 54000
    gezien = []
    oude_koppen, oude_urlopen = P.bronnen._koppen, urllib.request.urlopen
    try:
        P.bronnen._koppen = lambda extra=None: extra or {}
        for status in (200, 206):
            class Antwoord:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                def read(self, n):
                    gezien.append((status, n))
                    return data[:n]

            def urlopen(req, timeout):
                koppen = dict((k.lower(), v) for k, v in req.header_items())
                assert req.get_method() == "POST" and timeout == 120
                assert koppen["range"] == "bytes=0-599", koppen
                return Antwoord()

            urllib.request.urlopen = urlopen
            assert ECHTE_DOWNLOAD_KOP("/een groot transcript.txt", 600) == data[:600]
        assert gezien == [(200, 600), (206, 600)]
    finally:
        P.bronnen._koppen, urllib.request.urlopen = oude_koppen, oude_urlopen


def test_groot_bestaand_transcript_wordt_met_koplezing_bevestigd():
    w = Wereld()
    w.deals = [{"id": 777, "titel": "2531 Fictiva", "nummer": "2531"}]
    uitingen = [{"start_time": 0, "speaker": "Speaker 1", "content": "Werfbezoek 2531 Fictiva. " + "x" * 54000}]
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00", uitingen=uitingen)
    w.push()
    tekst = P.tekst_van(uitingen)
    w.bestanden[f"{BEZOEK}/transcript.txt"] = (
        f"plaud_id: {ID1}\ntranscript_hash: {P.zoektaak.transcript_hash(tekst)}\n\n{tekst}").encode()
    assert len(w.bestanden[f"{BEZOEK}/transcript.txt"]) > 54000
    w.taken = [werftaak(705)]
    code, _, _ = w.ronde()
    assert code == P.OK and w.opgepakt == [705] and not in_bezoekmap(w), (code, w.opgepakt, w.uploads)


def test_tkn_zoektaak_valideert_apart_mapnummer_en_plaud_doel():
    taak = tkn_taak()
    assert P.zoektaak.valideer_bezoekmap(taak, P.verslagsoorten.SOORTEN) == (True, "")
    assert json.loads(taak["inhoud"])["dossier"] == "3999"
    assert json.loads(taak["inhoud"])["mapnummer"] == "47035"
    assert P.zoektaak.bewijs_van(taak, P.verslagsoorten.SOORTEN) == ("UNAB", "3999")
    assert P.zoektaak.bewijs_van(tkn_taak(firma="ONBEKEND"), P.verslagsoorten.SOORTEN) == ("UNAB", "3999")
    assert P.zoektaak.bewijs_van(tkn_taak(firma="TKNB"), P.verslagsoorten.SOORTEN) == ("TKNB", "3999")
    oud_formaat = tkn_taak()
    oude_inhoud = json.loads(oud_formaat["inhoud"])
    del oude_inhoud["firma"]
    oud_formaat["inhoud"] = json.dumps(oude_inhoud)
    assert P.zoektaak.bewijs_van(oud_formaat, P.verslagsoorten.SOORTEN) == ("UNAB", "3999")
    assert P.zoektaak.bewijs_van(werftaak(702), P.verslagsoorten.SOORTEN) == ("HARC", "2531")
    assert P.zoektaak.bewijs_van(cctaak(703, "09:00", "10:00", f"{VC}/2531 Proefwerf/2026-10-08 bezoek",
                                           soort="veiligheidscoordinatie"), P.verslagsoorten.SOORTEN) == ("UNAB", "2531")
    varianten = [
        {"mapnummer": "3999"}, {"mapnummer": "abc"}, {"dossier": "abc"},
        {"bezoekmap": TKN_PLAUD}, {"bezoekmap": TKN_MAP.replace("/2026/", "/2025/")},
        {"plaud_doelmap": f"{TKN_MAP}/3.Documents"},
        {"plaud_doelmap": f"{TKN_PLAUD}/extra"},
        {"plaud_doelmap": "/andere firma/2. Plaud"},
        {"datum": "2026-13-08"}, {"transcriptnaam": "transcript.txt"},
    ]
    for wijziging in varianten:
        fout = tkn_taak(**wijziging)
        assert not P.zoektaak.valideer_bezoekmap(fout, P.verslagsoorten.SOORTEN)[0], wijziging
    fout = tkn_taak()
    fout["van"] = "werfverslag-voorbereider"
    assert not P.zoektaak.valideer_bezoekmap(fout, P.verslagsoorten.SOORTEN)[0]
    fout = tkn_taak()
    del fout["id"]
    assert not P.zoektaak.valideer_bezoekmap(fout, P.verslagsoorten.SOORTEN)[0]


def test_tkn_plaudwordt_uit_zoektaak_in_submap_geleverd():
    w = Wereld()
    w.opname(ID1, "Opname barsten en scheuren", "2026-10-08T07:10:00", uitingen=ZONDER_NUMMER)
    w.push()
    w.taken = [tkn_taak()]
    w.agenda = [{"soort": "afspraak", "titel": "barstenbezoek", "inhoud": json.dumps({
        "titel": "[UNAB-KB] BS 3999 Proeflaan 23", "start": "2026-10-08T09:00:00+02:00",
        "einde": "2026-10-08T10:00:00+02:00", "firma": "UNAB", "nummer": "3999"})}]
    w.herkenning[ID1] = {"personen": ["bouwheer"], "hoofdpersoon": "bouwheer", "bedrijf": "UNABO",
                        "afdeling": "unabo", "thema": "barsten en scheuren", "project": "", "prive": False,
                        "zekerheid": "middel", "waarom": "bezoekopdracht"}
    code, _, _ = w.ronde()
    doel = f"{TKN_PLAUD}/{TKN_NAAM}"
    assert code == P.OK and w.uploads == [doel] and w.opgepakt == [701], (code, w.uploads, w.opgepakt, w.logs)
    assert w.klaar[0]["voor"] == "unabo" and w.klaar[0]["inhoud"]["projectnummer"] == "3999", w.klaar[0]
    assert not w.klaar[0]["inhoud"]["conflict"], w.klaar[0]
    assert w.bestanden[doel].startswith(f"plaud_id: {ID1}".encode())


def test_tkn_postcode_als_agendanummer_geeft_geen_tegenstrijdig_bewijs():
    w = Wereld()
    w.opname(ID1, "Opname barsten en scheuren", "2026-10-08T07:10:00", uitingen=ZONDER_NUMMER)
    w.push()
    w.taken = [tkn_taak(dossier="47035", adres="Proeflaan 23, 9998 Proefgem")]
    w.agenda = [{"soort": "afspraak", "titel": "barstenbezoek", "inhoud": json.dumps({
        "titel": "BS Proeflaan 23", "start": "2026-10-08T09:00:00+02:00",
        "einde": "2026-10-08T10:00:00+02:00", "firma": "UNAB", "nummer": "9998",
        "locatie": "Proeflaan 23, 9998 Proefgem"})}]
    w.herkenning[ID1] = {"personen": ["bouwheer"], "hoofdpersoon": "bouwheer", "bedrijf": "UNABO",
                        "afdeling": "unabo", "thema": "barsten en scheuren", "project": "", "prive": False,
                        "zekerheid": "middel", "waarom": "bezoekopdracht"}
    code, _, _ = w.ronde()
    assert code == P.OK and w.uploads == [f"{TKN_PLAUD}/{TKN_NAAM}"] and w.opgepakt == [701], (code, w.uploads, w.opgepakt)
    besluit = w.klaar[0]["inhoud"]
    assert besluit["projectnummer"] == "47035" and not besluit["conflict"], besluit
    assert P.context_op("2026-10-08T07:10:00Z", 40, w.agenda)[0][0]["nummer"] == ""
    oude_taak = tkn_taak(dossier="9998", adres="Proeflaan 23, 9998 Proefgem")
    assert P.zoektaak.bewijs_van(oude_taak, P.verslagsoorten.SOORTEN) is None
    assert not P.zoektaak.valideer_bezoekmap(oude_taak, P.verslagsoorten.SOORTEN)[0]


def test_tkn_plaud_payload_en_handmatig_bestaand_transcript():
    taak = tkn_taak()
    opname = {"plaud_id": ID1, "start_brussel": "2026-10-08T09:05:00+02:00", "duur_minuten": 40}
    besluit = {"dossier": "3999", "zekerheid": "hoog", "projectnummer": "3999", "voor": "unabo",
               "firma": "UNAB", "conflict": False, "redenen": [], "kopie_toegestaan": True}
    opdracht = next(o for o in P.opdrachten_voor(opname, "de tekst", besluit, {"prive": False}, None,
                                                  [taak], "barsten-scheuren") if o["soort"] == "bezoekmap")
    payload = opdracht["payload"]
    assert payload == {"plaud_id": ID1, "taak_id": 701, "bezoekmap": TKN_PLAUD,
                       "naam": TKN_NAAM, "scan_alle": True, "tekst": "de tekst"}, payload
    w = Wereld()
    handmatig = f"Transcript van het plaatsbezoek\n---\nPlaud-ID: {ID1}\n".encode() + b"x" * 54000
    w.bestanden[f"{TKN_PLAUD}/handmatig verslag.txt"] = handmatig
    resultaat = P._bezoekmap(payload)
    assert resultaat["uitkomst"] == "al_geleverd" and not w.uploads and w.opgepakt == [701]

    w2 = Wereld()
    w2.bestanden[f"{TKN_PLAUD}/andere opname.txt"] = f"Plaud-ID: {ID2}\n".encode() + b"x" * 54000
    resultaat = P._bezoekmap(payload)
    assert resultaat["uitkomst"] == "geleverd" and w2.uploads == [f"{TKN_PLAUD}/{TKN_NAAM}"] and w2.opgepakt == [701]
    assert w2.bestanden[f"{TKN_PLAUD}/andere opname.txt"].startswith(f"Plaud-ID: {ID2}".encode())

    w3 = Wereld()
    w3.ontbrekende_mappen.add(TKN_PLAUD)
    try:
        P._bezoekmap(payload)
        raise AssertionError("een ontbrekende Plaud-map mag niet worden aangemaakt of afgevinkt")
    except RuntimeError as ex:
        assert "doelmap bestaat niet" in str(ex)
    assert not w3.uploads and not w3.opgepakt


def test_tkn_nieuwe_transcriptversie_komt_naast_de_oude():
    w = Wereld()
    w.bestanden[f"{TKN_PLAUD}/{TKN_NAAM}"] = f"Plaud-ID: {ID1}\nTranscript-Hash: oudehash\n\noud".encode()
    resultaat = P.zoektaak.lever(TKN_PLAUD, ID1, "nieuwe tekst", P.bronnen, naam=TKN_NAAM, scan_alle=True)
    naam = f"{TKN_NAAM[:-4]} versie {P.zoektaak.transcript_hash('nieuwe tekst')[:6]}.txt"
    assert resultaat["uitkomst"] == "nieuwe_versie" and w.uploads == [f"{TKN_PLAUD}/{naam}"]
    assert w.bestanden[f"{TKN_PLAUD}/{TKN_NAAM}"].endswith(b"oud")


if __name__ == "__main__":
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("   geslaagd  %s" % naam)
            except Exception as e:  # noqa: BLE001
                fouten += 1
                import traceback
                traceback.print_exc()
                print("   GEFAALD   %s: %s" % (naam, e))
    print("%d gefaald" % fouten if fouten else "alles geslaagd")
    sys.exit(1 if fouten else 0)

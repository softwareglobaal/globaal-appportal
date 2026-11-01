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
import io
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import types
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from contextlib import redirect_stdout
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
        P.GEMELD = str(self.staat) + "-gemeld.json"   # PLAUD-8: per Wereld een eigen geheugen van gemelde zoektaken
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
        # een tabel met een rij: een lege personentabel is voor De Plaudwacht onbekend (NA09-rest), dan herkent ze niets
        FW.personen_uit_werkwijze = lambda w: [{"naam": "Proef Collega", "mails": ["proef@h-architects.be"],
                                                 "afdeling": "regie", "rol": "proef", "bijzonder": ""}]
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
        r = types.SimpleNamespace(noden=[], detail="", bronnen=[])
        r.nood = lambda tekst, wie="mehdi": r.noden.append(tekst)
        r.bron = lambda naam, inhoud: r.bronnen.append(naam)
        code, tellers = P.ronde(r)
        return code, tellers, r.noden


RUNNER_MAP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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


def test_na09_onbekende_personentabel_herkent_en_publiceert_niets():
    """NA09-rest (T-0075, 01-11-2026): de personentabel komt uit de werkwijze van De Fathomwacht. Tot dan werd een
    antwoord zonder werkwijze een lege tabel, en herkende het model privé en afdeling zonder voorkennis; een fout van het
    bord brak de hele ronde. Onbekend is niet leeg, en een lege tabel is geen tabel (overleg 12, X2): nu een nood, geen
    herkenning, geen publicatie en geen staat voor de opname (ze blijft voor de volgende ronde), wel het toezicht. Met de
    tabel terug gaat ze gewoon door, en de nood valt weg."""
    fout = urllib.error.HTTPError("http://127.0.0.1:3022/api/agent/fathom-wacht/werkwijze", 502, "proef", None, None)
    for antwoord, nood in (({}, "Personentabel van De Fathomwacht niet gelezen"),
                           (fout, "Personentabel van De Fathomwacht niet gelezen"),
                           ({"werkwijze": "# Fathomwacht\n\nGeen tabel."}, "Personentabel van De Fathomwacht leeg")):
        w = Wereld()
        w.deals = [{"id": 777, "titel": "2531 Fictiva", "nummer": "2531"}]
        w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
        w.push()
        w.taken = [werftaak(101)]
        echt, echte_tabel = w.call, FW.personen_uit_werkwijze

        def call(pad, payload=None, method=None, _a=antwoord):
            if pad == "/api/agent/fathom-wacht/werkwijze":
                if isinstance(_a, Exception):
                    raise _a
                return _a
            return echt(pad, payload, method)

        P.bord.call = call
        if "Geen tabel" in str(antwoord):
            FW.personen_uit_werkwijze = lambda tekst: []
        try:
            code, tel, noden = w.ronde()
        finally:
            P.bord.call, FW.personen_uit_werkwijze = echt, echte_tabel
        assert nood in noden, (antwoord, noden)
        assert not w.herkend and not w.rijen and not w.klaar and not w.uploads and not w.opgepakt, \
            (antwoord, w.herkend, w.rijen, w.klaar, w.uploads)
        assert not (w.staat / f"{ID1}.json").exists(), "de opname kreeg een staat: ze zou als gezien kunnen gelden"
        assert code == P.DEELS and tel["gedaan"] == 0, (code, tel)
        code, tel, noden = w.ronde()
        assert code == P.OK and tel["gedaan"] == 1 and len(w.herkend) == 1 and not noden, (code, tel, noden)


def dagbundelaar_op(items, dag):
    """Een ronde van De Dagbundelaar op deze klaarzet-items, zoals het bord ze teruggeeft (inhoud als json-tekst), zonder
    netwerk. Geeft (bundels, werkverslagregels)."""
    _argv, sys.argv = sys.argv, [sys.argv[0]]          # dagbundelaar.py leest --dag bij het importeren
    try:
        import dagbundelaar as D  # noqa: PLC0415
    finally:
        sys.argv = _argv
    gezet = {}

    def call(pad, payload=None, method=None):
        if pad.startswith("/api/klaarzet?"):
            return {"items": [dict(it) for it in items if "soort=zoom" not in pad or it["soort"] == "zoom"]}
        # De Dagbundelaar gaat sinds 26-10-2026 door de gedeelde ronde (N12): ze leest haar werkwijze en de collega's
        if pad == "/api/agent/dagbundelaar/werkwijze" and payload is None:
            return {"werkwijze": open(os.path.join(RUNNER_MAP, "werkwijze", "dagbundelaar.md"), encoding="utf-8").read()}
        if pad == "/api/agents":
            return []
        gezet.setdefault(pad, []).append(payload)
        return {"nieuw": len((payload or {}).get("items") or [])}

    oud = (D.bord.call, D.bord.opgepakt, D.DAG, D.DAG_GEGEVEN, D.NACHT, D.vastleggen)
    D.bord.call, D.bord.opgepakt, D.DAG, D.DAG_GEGEVEN, D.NACHT = call, (lambda kid, door: None), dag, True, False
    D.vastleggen = lambda r, dagen, **k: ""          # de dagvaststelling heeft eigen tests (test_dagbundelaar_vaststelling.py)
    try:
        with redirect_stdout(io.StringIO()):
            D.main()
    finally:
        D.bord.call, D.bord.opgepakt, D.DAG, D.DAG_GEGEVEN, D.NACHT, D.vastleggen = oud
    return gezet["/api/klaarzet"][0]["items"], [r for p in gezet.get("/api/logboek", []) for r in p["regels"]]


def export_van(klaarzet, logboek):
    """bord_export.main() op een tijdelijke databank met deze klaarzet-items en werkverslagregels. Het schema komt uit
    init_db van mijnagents/app.py, als tekst gelezen: plaud-grendels draait deze test voor Flask er is. Geeft {pad: tekst}
    van de export."""
    import bord_export as E  # noqa: PLC0415
    map_ = tempfile.mkdtemp(prefix="plaud-export-")
    pad = os.path.join(map_, "bord.db")
    bron = open(os.path.join(os.path.dirname(HIER), "mijnagents", "app.py"), encoding="utf-8").read()
    c = sqlite3.connect(pad)
    c.executescript(re.search(r'def init_db\(\):.*?executescript\(\s*"""(.*?)"""', bron, re.S).group(1))
    c.execute("ALTER TABLE agent ADD COLUMN werkwijze TEXT DEFAULT ''")
    nu_ = datetime.now(timezone.utc).isoformat()
    c.executemany("INSERT INTO klaarzet(van, voor, soort, sleutel, titel, inhoud, verwijzing, uniek, status, ts) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  [(it["van"], it["voor"], it["soort"], it.get("sleutel") or "", it["titel"],
                    it["inhoud"] if isinstance(it.get("inhoud"), str) else json.dumps(it.get("inhoud"), ensure_ascii=False),
                    it.get("verwijzing") or "", it.get("uniek") or "", it.get("status") or "klaar", nu_) for it in klaarzet])
    c.executemany("INSERT INTO logboek(naam, onderwerp, stap, tekst, detail, ts) VALUES(?,?,?,?,?,?)",
                  [(r["naam"], r["onderwerp"], r["stap"], r["tekst"], r["detail"], nu_) for r in logboek])
    c.commit()
    c.close()
    oud = (E.DB, E.DATA, E.UIT)
    E.DB, E.DATA, E.UIT = pad, map_, os.path.join(map_, "export")
    try:
        with redirect_stdout(io.StringIO()):
            E.main()
    finally:
        E.DB, E.DATA, E.UIT = oud
    gelezen = {}
    for wortel, _, bestanden in os.walk(os.path.join(map_, "export")):
        for b in bestanden:
            gelezen[os.path.relpath(os.path.join(wortel, b), map_)] = open(os.path.join(wortel, b), encoding="utf-8").read()
    return gelezen


def test_tegenstrijdige_privevelden_leveren_niets():
    """Afdeling prive met prive=false: de dossierbeslissing (plaud/dossier.py) noemt dat privé en levert niets zakelijk.
    RZ3-01 (herstelcontrole van 22-10-2026, besluit van de regie: de veilige kant): tot dan zette De Plaudwacht zo'n
    opname klaar met de hoofdpersoon en het thema in de titel, personen en thema in de inhoud en de archiefmap in de
    verwijzing, omdat ze daarvoor alleen herkenning['prive'] las. Die titel kwam in de bundel, het Dagverslag en de export.
    Nu is de opname privé als de herkenning OF de dossierbeslissing het zegt, en toetst deze test de hele route: de
    klaarzet-tekst, het werkverslag, De Dagbundelaar en de export."""
    w = Wereld()
    logs = []
    P.ag.log = lambda onderwerp, stap, tekst, detail="": logs.append({"naam": "plaud-wacht", "onderwerp": onderwerp, "stap": stap,
                                                                        "tekst": tekst, "detail": detail})
    w.deals = [{"id": 777, "titel": "2531 Fictiva", "nummer": "2531"}]
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    w.push()
    w.taken = [werftaak(602)]
    w.herkenning[ID1] = {"personen": ["Proefpersoon Zeta", "Mehdi"], "hoofdpersoon": "Proefpersoon Zeta", "bedrijf": "",
                         "afdeling": "prive", "thema": "Proefonderwerp Omega regelen", "project": "", "prive": False,
                         "zekerheid": "hoog", "waarom": "Proefpersoon Zeta over het Proefonderwerp Omega"}
    w.ronde()
    k = w.klaar[0]
    assert k["voor"] == "mehdi" and not w.uploads and not w.opgepakt, (k, w.uploads)
    # de klaarzet-tekst: zoals elk privé-item, alleen id, datum, start, minuten, privé en de verwijzing met '(privé)'
    verwijzing = f"{P.ARCHIEF_OP_MAC}/2026-10-08 1105 (privé) [{ID1}]"
    assert k["titel"].startswith("2026-10-08 11:05 Plaud: privégesprek, 40 min · PRIVÉ"), k["titel"]
    assert k["inhoud"] == {"plaud_id": ID1, "datum": "2026-10-08", "start": "11:05", "minuten": 40, "prive": True,
                           "archief": verwijzing}, k["inhoud"]
    assert k["verwijzing"] == verwijzing, k["verwijzing"]
    assert w.rijen[0]["prive"] is True, "ook de gesprekkentabel draagt de veilige privévlag"
    assert any(r["stap"] == "bevinding" and r["tekst"].startswith("privégesprek · 40 min") for r in logs), logs
    # De Dagbundelaar en de export, op wat het bord van dit item teruggeeft
    bak = [dict(k, id=1, van="plaud-wacht", status="klaar", inhoud=json.dumps(k["inhoud"], ensure_ascii=False))]
    bundels, bundellog = dagbundelaar_op(bak, "2026-10-08")
    verslag = next(b for b in bundels if b["uniek"] == "dagverslag:2026-10-08")["inhoud"]
    assert "- transcript: privégesprek, 40 min" in verslag, verslag
    assert not any(b["voor"] == "h-architects" for b in bundels), "een privé-opname komt in geen bundel voor een afdeling"
    gelezen = export_van(bak + [dict(b, van="dagbundelaar") for b in bundels], logs + bundellog)
    plaud = "".join(t for pad, t in gelezen.items() if pad.startswith(os.path.join("export", "Plaud", "klaargezet")))
    assert plaud.count("): (privé)") == 1, plaud
    nagaan = {"klaarzet": json.dumps(w.klaar, ensure_ascii=False), "werkverslag": json.dumps(logs, ensure_ascii=False),
              "bundels": json.dumps(bundels + bundellog, ensure_ascii=False)}
    nagaan.update({f"export {pad}": t for pad, t in gelezen.items()})
    for waar, tekst in nagaan.items():
        for geheim in ("Zeta", "Omega"):
            assert geheim not in tekst, f"{geheim!r} staat in {waar}: {tekst[:1500]}"


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
    w.opname(ID1, "10-08 PRIVE Proefpersoon Ypsilon en Mehdi weekend", "2026-10-08T09:05:00")
    w.push()
    w.herkenning[ID1] = {"personen": ["Proefpersoon Ypsilon"], "hoofdpersoon": "Proefpersoon Ypsilon", "bedrijf": "", "afdeling": "prive",
                         "thema": "weekend", "project": "", "prive": True, "zekerheid": "hoog", "waarom": ""}
    w.ronde()
    assert len(w.herkend) == 2, "een andere titel is andere modelinput"
    assert w.klaar[-1]["voor"] == "mehdi" and w.klaar[-1]["inhoud"]["prive"], w.klaar[-1]


def test_rz2_01_prive_opname_draagt_geen_naam_of_onderwerp():
    """RZ2-01 bij De Plaudwacht (tegenproef van 22-10-2026: herstellen in alle varianten, zoals bij De Fathomwacht). Een
    privé-opname droeg de hoofdpersoon en het thema in de titel van het klaarzet-item, personen, thema en afdeling in de
    inhoud, en de archiefmap (die naar de naam in Plaud heet) in de verwijzing; de bevinding in het werkverslag noemde de
    hoofdpersoon. Dat item gaat naar De Dagbundelaar, De Levenscoach en de export. Nu: alleen het Plaud-id, datum, start,
    minuten, privé en een verwijzing naar het archief op de Mac met '(privé)' en het id. De gesprekkentabel (alleen beheer)
    houdt wie en waarover; een werkopname blijft zoals ze was."""
    w = Wereld()
    logs = []
    P.ag.log = lambda onderwerp, stap, tekst, detail="": logs.append((onderwerp, stap, tekst, detail))
    w.opname(ID1, "10-08 Proefpersoon Zeta Proefonderwerp Omega", "2026-10-08T18:05:00")      # 20:05 in Brussel
    w.opname(ID2, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    w.push()
    w.herkenning[ID1] = {"personen": ["Proefpersoon Zeta", "Mehdi"], "hoofdpersoon": "Proefpersoon Zeta", "bedrijf": "", "afdeling": "prive",
                         "thema": "Proefonderwerp Omega regelen", "project": "", "prive": True, "zekerheid": "hoog",
                         "waarom": "Proefpersoon Zeta over het Proefonderwerp Omega"}
    code, tel, _ = w.ronde()
    assert tel["gedaan"] == 2, tel
    assert "Zeta" in json.dumps(w.rijen, ensure_ascii=False), "de gesprekkentabel (alleen beheer) houdt wie en waarover"
    items = {k["uniek"]: k for k in w.klaar}
    p = items[f"plaud:{ID1}"]
    verwijzing = f"{P.ARCHIEF_OP_MAC}/2026-10-08 2005 (privé) [{ID1}]"
    assert p["titel"] == "2026-10-08 20:05 Plaud: privégesprek, 40 min · PRIVÉ", p["titel"]
    assert p["inhoud"] == {"plaud_id": ID1, "datum": "2026-10-08", "start": "20:05", "minuten": 40, "prive": True,
                           "archief": verwijzing}, p["inhoud"]
    assert p["verwijzing"] == verwijzing and p["voor"] == "mehdi" and p["soort"] == "transcript", p
    werk = items[f"plaud:{ID2}"]
    assert werk["titel"] == "2026-10-08 11:05 Plaud: aannemer · werfbezoek ruwbouw", werk["titel"]
    assert werk["inhoud"]["personen"] == ["aannemer"] and werk["inhoud"]["thema"] == "werfbezoek ruwbouw", werk["inhoud"]
    assert any(t.startswith("privégesprek · 40 min") for _, s, t, _ in logs if s == "bevinding"), logs
    for waar, tekst in (("klaarzet", json.dumps(w.klaar, ensure_ascii=False)), ("werkverslag", json.dumps(logs, ensure_ascii=False))):
        for geheim in ("Zeta", "Omega"):
            assert geheim not in tekst, f"{geheim!r} staat in {waar}: {tekst[:1500]}"


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


def onvolledige_opname(w, pid, start_at):
    """Een map met transcript maar zonder audio, zoals de ruwe Opus van Plaud op 15-10 tot 22-10 (geen OggS-kop)."""
    def haler(url, max_bytes, timeout):
        return gzip.compress(json.dumps(OPENING).encode()) if "transcript" in url else b"\xb8" * 80 * 50
    r = bouw_map.bouw({"id": pid, "name": "proef zonder audio", "start_at": start_at, "duration": 20 * 60000,
                       "presigned_url": "https://proef/audio", "transcript_link": "https://proef/transcript"},
                      w.archief, haler=haler)
    assert r["status"] == "onvolledig", r


def ronde_met_detail(w):
    r = types.SimpleNamespace(noden=[], detail="", bronnen=[])
    r.nood = lambda tekst, wie="mehdi": r.noden.append((tekst, wie))
    r.bron = lambda naam, inhoud: r.bronnen.append(naam)
    code, tellers = P.ronde(r)
    return code, tellers, r


def test_plaud5_deels_en_onvolledige_mappen_geven_een_nood_met_het_aantal_in_het_detail():
    """PLAUD-5 (T-0120): van 28-10 tot 01-11 stond de Mac elk uur op 'deels' (foutcode 4) met 5 onvolledige mappen, en
    De Plaudwacht meldde niets: toezicht keek alleen naar authfout en bronfout. Nu één nood voor claude-code, zonder
    teller in de tekst (N10); het aantal staat in het detail van de ronde."""
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    for i in range(5):
        onvolledige_opname(w, "of_" + str(i + 4) * 32, f"2026-10-1{i + 5}T10:00:00")
    (w.archief / "00 status.json").write_text(json.dumps({"uitkomst": "deels", "tellers": {"mislukt": 5}}))
    w.push()
    _, tel, r = ronde_met_detail(w)
    mac = [(t, wie) for t, wie in r.noden if "deels" in t]
    assert len(mac) == 1 and mac[0][1] == "claude-code", r.noden
    assert not mac[0][0][:1].isdigit() and "5" not in mac[0][0], "N10: het aantal hoort in het detail, niet in de nood"
    assert tel["onvolledig_archief"] == 5 and "5 onvolledig in het archief" in r.detail, (tel, r.detail)
    # alleen onvolledige mappen, ook als de laatste ronde van de Mac 'ok' zegt: ook een nood
    (w.archief / "00 status.json").write_text(json.dumps({"uitkomst": "ok"}))
    w.push()
    _, _, r = ronde_met_detail(w)
    assert len([t for t, _ in r.noden if "deels" in t]) == 1, r.noden


def test_plaud5_status_ok_zonder_onvolledige_mappen_geeft_geen_nood():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    (w.archief / "00 status.json").write_text(json.dumps({"uitkomst": "ok"}))
    w.push()
    code, tel, r = ronde_met_detail(w)
    assert code == P.OK and not r.noden and tel["onvolledig_archief"] == 0, (code, r.noden)
    assert "onvolledig" not in r.detail, r.detail


def test_plaud8_zelfde_zoektaakuitkomst_staat_een_keer_in_het_werkverslag():
    """PLAUD-8 (T-0120): op 29-10 stonden 384 van de 408 regels in het werkverslag van De Plaudwacht er omdat elke ronde
    dezelfde 16 zoektaakbevindingen opnieuw schreef. Een bevinding komt er nu alleen bij een andere uitkomst."""
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Fictiva", "2026-10-08T09:05:00")
    w.push()
    w.taken = [werftaak(601, datum="2026-10-09", bezoekmap=f"{HA}/2531 Fictiva/_00. Communication/2026-10-09 bezoek klant - werfbezoek")]
    for _ in range(3):
        w.ronde()
    regels = [t for s, t in w.logs if s == "bevinding" and t.startswith("niet_gevonden")]
    assert len(regels) == 1, regels
    # een andere uitkomst (de opname van die dag komt binnen) staat er wel bij, en wordt geleverd zoals voordien
    w.opname(ID2, "10-09 Werfbezoek 2531 Fictiva", "2026-10-09T09:05:00")
    w.push()
    w.ronde()
    assert len([t for s, t in w.logs if s == "bevinding" and t.startswith("gevonden")]) == 1, w.logs
    assert w.opgepakt == [601], w.opgepakt


def test_plaud8_barsten_en_scheuren_zoektaak_geeft_dezelfde_uitkomst():
    """VOL-18: alleen het werkverslag verandert. Een zoektaak van de keten barsten en scheuren (TKN, eigen doelmap) geeft
    bij elke beoordeling dezelfde uitkomst en wordt geleverd zoals in test_tkn_plaudwordt_uit_zoektaak_in_submap_geleverd."""
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
    m = P.manifest.lees(P.INVOER)
    opnames = [(o, None) for o in m["opnames"]]
    st_obj = P.staat.Staat(P.STAAT)
    items = P.klaarzet_items()
    eerste = P.zoektaken_beoordelen(w.taken, opnames, st_obj, items)
    tweede = P.zoektaken_beoordelen(w.taken, opnames, st_obj, items)
    assert eerste == tweede and eerste[1][0]["uitkomst"] == "gevonden", (eerste, tweede)
    assert len([t for s, t in w.logs if s == "bevinding" and t.startswith("gevonden")]) == 1, w.logs
    code, _, _ = w.ronde()
    doel = f"{TKN_PLAUD}/{TKN_NAAM}"
    assert code == P.OK and w.uploads == [doel] and w.opgepakt == [701], (code, w.uploads, w.opgepakt)


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


def test_ha_projectnummer_gelijk_werfpostcode_blijft_agendabewijs():
    w = Wereld()
    bezoek = BEZOEK.replace("2531", "2640")
    w.deals = [{"id": 840, "titel": "2640 Proefwerf", "nummer": "2640"}]
    w.opname(ID1, "Plaatsbezoek Proefwerf", "2026-10-08T09:05:00", uitingen=ZONDER_NUMMER)
    w.push()
    w.taken = [werftaak(801, dossier="2640", bezoekmap=bezoek)]
    w.agenda = [{"soort": "afspraak", "titel": "Werfbezoek", "inhoud": json.dumps({
        "titel": "[HA-KB] WB 2640 Proefwerf", "start": "2026-10-08T11:00:00+02:00",
        "einde": "2026-10-08T12:00:00+02:00", "firma": "HARC", "nummer": "2640",
        "locatie": "Proefstraat 1, 2640 Proefgem"})}]
    w.herkenning[ID1] = {"personen": ["aannemer"], "hoofdpersoon": "aannemer", "bedrijf": "",
                         "afdeling": "h-architects", "thema": "werfbezoek", "project": "",
                         "prive": False, "zekerheid": "hoog", "waarom": "afspraak"}
    assert P.context_op("2026-10-08T09:05:00Z", 40, w.agenda)[0][0]["nummer"] == "2640"
    code, _, _ = w.ronde()
    assert code == P.OK and w.opgepakt == [801] and f"{bezoek}/transcript.txt" in w.uploads, (code, w.opgepakt, w.uploads, w.logs)
    assert w.klaar[0]["inhoud"]["projectnummer"] == "2640" and w.klaar[0]["voor"] == "h-architects"


def test_ha_en_firmaloze_afspraak_houden_nummer_dat_ook_postcode_is():
    for firma in ("HA", None):
        inhoud = {"titel": "Fictief werfbezoek", "start": "2026-10-08T11:00:00+02:00",
                  "einde": "2026-10-08T12:00:00+02:00", "nummer": "2640",
                  "locatie": "Proefstraat 1, 2640 Proefgem"}
        if firma:
            inhoud["firma"] = firma
        agenda = [{"soort": "afspraak", "titel": "Fictief werfbezoek", "inhoud": json.dumps(inhoud)}]
        assert P.context_op("2026-10-08T09:05:00Z", 40, agenda)[0][0]["nummer"] == "2640", firma


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
    assert resultaat["uitkomst"] == "geleverd" and w.uploads == [f"{TKN_PLAUD}/{TKN_NAAM}"] and w.opgepakt == [701]
    assert w.bestanden[f"{TKN_PLAUD}/handmatig verslag.txt"] == handmatig

    w2 = Wereld()
    w2.bestanden[f"{TKN_PLAUD}/andere opname.txt"] = f"Plaud-ID: {ID2}\n".encode() + b"x" * 54000
    resultaat = P._bezoekmap(payload)
    assert resultaat["uitkomst"] == "geleverd" and w2.uploads == [f"{TKN_PLAUD}/{TKN_NAAM}"] and w2.opgepakt == [701]
    assert w2.bestanden[f"{TKN_PLAUD}/andere opname.txt"].startswith(f"Plaud-ID: {ID2}".encode())

    w_bezet = Wereld()
    bestaand = f"Plaud-ID: {ID2}\nDit is een andere opname".encode()
    w_bezet.bestanden[f"{TKN_PLAUD}/{TKN_NAAM}"] = bestaand
    try:
        P._bezoekmap(payload)
        raise AssertionError("de vaste transcriptnaam van een andere opname mag niet worden overschreven")
    except RuntimeError as ex:
        assert "al in gebruik" in str(ex)
    assert w_bezet.bestanden[f"{TKN_PLAUD}/{TKN_NAAM}"] == bestaand and not w_bezet.uploads and not w_bezet.opgepakt

    w3 = Wereld()
    w3.ontbrekende_mappen.add(TKN_PLAUD)
    try:
        P._bezoekmap(payload)
        raise AssertionError("een ontbrekende Plaud-map mag niet worden aangemaakt of afgevinkt")
    except RuntimeError as ex:
        assert "doelmap bestaat niet" in str(ex)
    assert not w3.uploads and not w3.opgepakt


def test_te_grote_bestaande_docx_geeft_onbekende_kop_en_log_zonder_taakfout():
    w = Wereld()
    groot = f"{TKN_PLAUD}/2026-10-08 handmatig transcript.docx"
    w.bestanden[groot] = b"synthetische docx"
    download = P.bronnen.download

    def begrensd(pad, maximum=25_000_000):
        if pad == groot:
            raise RuntimeError("downloadgrens overschreden")
        return download(pad, maximum)

    P.bronnen.download = begrensd
    try:
        resultaat = P._bezoekmap({"bezoekmap": TKN_PLAUD, "plaud_id": ID1, "tekst": "nieuw transcript",
                                 "naam": TKN_NAAM, "scan_alle": True, "taak_id": 701})
    finally:
        P.bronnen.download = download
    assert resultaat["uitkomst"] == "geleverd" and w.opgepakt == [701]
    assert w.uploads == [f"{TKN_PLAUD}/{TKN_NAAM}"]
    assert any("kop onbekend" in tekst and "niet als geleverd" in tekst for _, tekst in w.logs)


def test_scan_alle_gebruikt_dezelfde_transcriptnaamregel_als_de_verslagagent():
    p, naam = TKN_PLAUD, TKN_NAAM
    voorbeelden = (
        ("2026-10-08 Plaud samenvatting.txt", False),
        ("2026-10-08 Plaud summary.txt", False),
        ("2026-10-08 Plaud (concept).txt", False),
        ("handmatig transcript.txt", False),
        ("2026-10-07 Plaud transcript.txt", False),
        ("2026-10-080 Plaud transcript.txt", False),
        ("2026-10-08 Plaud transcript.pdf", False),
        ("2026-10-08 Plaud transcript.TXT", True),
        ("20261008 Plaud transcript.docx", True),
    )
    for bestandsnaam, telt in voorbeelden:
        assert P.zoektaak.is_bezoektranscript(bestandsnaam, "2026-10-08") is telt, bestandsnaam
    for bestandsnaam, _ in voorbeelden[:7]:
        w = Wereld()
        oud = f"Plaud-ID: {ID1}\nHandmatige tekst".encode()
        w.bestanden[f"{p}/{bestandsnaam}"] = oud
        resultaat = P.zoektaak.lever(p, ID1, "nieuw transcript", P.bronnen, naam=naam, scan_alle=True)
        assert resultaat["uitkomst"] == "geleverd" and w.uploads == [f"{p}/{naam}"], (bestandsnaam, resultaat)
        assert w.bestanden[f"{p}/{bestandsnaam}"] == oud
    w = Wereld()
    w.bestanden[f"{p}/2026-10-08 handmatig transcript.TXT"] = f"Plaud-ID: {ID1}\nHandmatige tekst".encode()
    resultaat = P.zoektaak.lever(p, ID1, "nieuw transcript", P.bronnen, naam=naam, scan_alle=True)
    assert resultaat["uitkomst"] == "al_geleverd" and not w.uploads

    docx = io.BytesIO()
    xml = (f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body><w:p><w:r><w:t>Plaud-ID: {ID1}</w:t></w:r></w:p></w:body></w:document>')
    with zipfile.ZipFile(docx, "w") as pakket:
        pakket.writestr("word/document.xml", xml)
    w = Wereld()
    w.bestanden[f"{p}/2026-10-08 handmatig transcript.docx"] = docx.getvalue()
    resultaat = P.zoektaak.lever(p, ID1, "nieuw transcript", P.bronnen, naam=naam, scan_alle=True)
    assert resultaat["uitkomst"] == "al_geleverd" and not w.uploads


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

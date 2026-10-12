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

lijst.OUDE_REPO_LIJST = Path("/nonexistent/plaud_lijst.json")

ID1, ID2, ID3 = "of_" + "1" * 32, "of_" + "2" * 32, "of_" + "3" * 32
HA = "/Work All/01. H-A WORK/0 H-A Standaard projects/5. STAN Execution"
BEZOEK = f"{HA}/2531 Spleesters/_00. Communication/2026-10-08 bezoek klant - werfbezoek"
VC = "/Work All/02. UNABO/01. U-WORK/03. U-SAFETY"
OPENING = [{"start_time": 0, "speaker": "Speaker 1", "content": "Werfbezoek 2531 Spleesters met de aannemer."},
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
        P.bronnen.upload = self.upload
        P.bronnen.zoek_salesmap = lambda naam="", nummer="": f"/Sales/{nummer} klant" if nummer else None
        P.LC.verblijf_op = lambda moment, ook_kandidaten=False: None
        FW.herken = self.herken
        FW.personen_uit_werkwijze = lambda w: []
        FW.deals_index = lambda: self.deals

    def _faal(self, soort):
        if self.fout.get(soort):
            self.fout[soort] -= 1
            raise RuntimeError(f"geforceerde proeffout bij {soort}")

    def call(self, pad, payload=None, method=None):
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
        uit = []
        for p in self.bestanden:
            if os.path.dirname(p) == pad.rstrip("/"):
                uit.append({".tag": "file", "name": os.path.basename(p), "path_display": p, "path_lower": p.lower()})
        return uit

    def download(self, pad, maximum=25_000_000):
        """Dropbox is hoofdletterongevoelig: path_lower vindt het bestand."""
        return next(v for k, v in self.bestanden.items() if k.lower() == pad.lower())[:maximum]

    def upload(self, pad, data):
        self._faal("upload:" + ("bezoek" if "/Work All/" in pad else "dossier"))
        self.uploads.append(pad)
        self.bestanden[pad] = data
        return pad

    def herken(self, g, tekst, personen, deal, hoe, context=None, bron="fathom"):
        pid = g["recording_id"]
        self.herkend.append((pid, context, len(tekst)))
        h = self.herkenning.get(pid, {"personen": ["aannemer"], "hoofdpersoon": "aannemer", "bedrijf": "", "afdeling": "h-architects",
                                      "thema": "werfbezoek ruwbouw", "project": "2531 Spleesters", "prive": False,
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


def in_bezoekmap(w):
    return [p for p in w.uploads if p.startswith("/Work All/")]


# ------------------------------------------------------------------ proeven ---
def test_van_bron_tot_tabel_klaarzet_en_bezoekmap_en_een_tweede_ronde_zonder_dubbel():
    w = Wereld()
    w.deals = [{"id": 777, "titel": "2531 Spleesters", "nummer": "2531"}]
    w.opname(ID1, "10-08 Werfbezoek 2531 Spleesters", "2026-10-08T09:05:00")      # 11:05 in Brussel
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
    w.deals = [{"id": 777, "titel": "2531 Spleesters", "nummer": "2531"}]
    w.opname(ID1, "10-08 Werfbezoek 2531 Spleesters", "2026-10-08T09:05:00")
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
    w.opname(ID1, "10-08 Werfbezoek 2531 Spleesters", "2026-10-08T09:05:00")
    w.push()
    w.ronde()
    assert not in_bezoekmap(w)
    w.taken = [werftaak(102)]
    code, _, _ = w.ronde()
    assert code == P.OK and in_bezoekmap(w) == [f"{BEZOEK}/transcript.txt"] and w.opgepakt == [102]
    assert len(w.herkend) == 1 and len(w.klaar) == 1


def test_een_fout_bij_de_tweede_opname_blokkeert_de_eerste_niet():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Spleesters", "2026-10-08T09:05:00")
    w.opname(ID2, "10-08 Telefoon", "2026-10-08T13:00:00")
    w.push()
    w.herkenning[ID2] = RuntimeError("model weigert")
    code, tel, _ = w.ronde()
    assert code == P.DEELS and tel["gedaan"] == 1 and tel["fout"] == 1, tel
    assert [r["uniek"] for r in w.rijen] == [f"plaud:{ID1}"]


def test_titel_en_kop_in_conflict_geven_geen_kopie_en_gaan_naar_mehdi():
    w = Wereld()
    w.deals = [{"id": 777, "titel": "2531 Spleesters", "nummer": "2531"}]
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
    w.deals = [{"id": 777, "titel": "2531 Spleesters", "nummer": "2531"}]
    w.opname(ID1, "10-08 Werfbezoek 2531 Spleesters", "2026-10-08T09:05:00")
    w.push()
    w.herkenning[ID1] = {"personen": [], "hoofdpersoon": "", "bedrijf": "", "afdeling": "onbekend", "thema": "", "project": "",
                         "prive": False, "zekerheid": "laag", "waarom": ""}
    w.ronde()
    assert w.klaar[0]["voor"] == "mehdi" and not w.uploads, (w.klaar[0]["voor"], w.uploads)


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
    w.opname(ID1, "10-08 Werfbezoek 2531 Spleesters", "2026-10-08T09:05:00")
    w.push()
    zonder_id = werftaak(0)
    zonder_id.pop("id")
    w.taken = [werftaak(201, bezoekmap="/Privé/Mehdi/2026-10-08"),                                      # willekeurig pad
               werftaak(202, bezoekmap=f"{HA}/2531 Spleesters/../../../Privé/2026-10-08"),               # ..
               werftaak(203, bezoekmap=BEZOEK.replace("2026-10-08 bezoek", "2026-10-01 bezoek")),        # andere dag
               werftaak(204, bezoekmap=BEZOEK.replace("2531 Spleesters", "2612 Andere")),                # ander dossier
               cctaak(205, "11:00", "12:00", BEZOEK),                                                     # firma van VC, pad van H-A
               zonder_id]
    code, _, noden = w.ronde()
    assert not in_bezoekmap(w) and not w.opgepakt, w.uploads
    assert any("ongeldige bezoekmap" in n for n in noden), noden
    assert len([l for l in w.logs if "zoektaak niet uitgevoerd" in l[1]]) == 6


def test_dezelfde_dag_is_geen_bevestiging_het_tijdstip_wel():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Spleesters", "2026-10-08T07:00:00")     # 09:00 in Brussel
    w.opname(ID2, "10-08 VC bezoek", "2026-10-08T12:00:00")                         # 14:00 in Brussel
    w.push()
    w.taken = [werftaak(301)]
    code, _, noden = w.ronde()
    assert not in_bezoekmap(w) and not w.opgepakt and any("meer passende opnames" in n for n in noden), (w.uploads, noden)
    vc = f"{VC}/2531 Proefwerf/2026-10-08 bezoek werf - veiligheidscoördinatie"
    w2 = Wereld()
    w2.opname(ID1, "10-08 Werfbezoek 2531 Spleesters", "2026-10-08T07:00:00")
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
    w.taken = [werftaak(410, dossier="2324", bezoekmap=f"{HA}/2324 Herenthout/_00. Communication/2026-10-08 bezoek klant - werfbezoek")]
    w.ronde()
    assert not in_bezoekmap(w) and not w.opgepakt, w.uploads
    assert any("dezelfde dag alleen is geen bevestiging" in l[1] for l in w.logs), w.logs


def test_een_ander_transcript_in_de_bezoekmap_wordt_niet_overschreven():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Spleesters", "2026-10-08T09:05:00")
    w.push()
    w.bestanden[f"{BEZOEK}/transcript.txt"] = b"plaud_id: of_ffffffffffffffffffffffffffffffff\n\nander gesprek"
    w.taken = [werftaak(401)]
    code, _, _ = w.ronde()
    assert code == P.DEELS and not in_bezoekmap(w) and not w.opgepakt
    assert w.bestanden[f"{BEZOEK}/transcript.txt"].endswith(b"ander gesprek")


def test_wachtend_transcript_laat_de_taak_open():
    w = Wereld()
    w.opname(ID1, "10-08 Werfbezoek 2531 Spleesters", "2026-10-08T09:05:00", transcript=False)
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
    w.opname(ID1, "10-08 Werfbezoek 2531 Spleesters", "2026-10-08T09:05:00")
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

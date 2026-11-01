"""Grendels op De Zoomarchivaris (zoom_archief.py), de lijst K7 uit het driehoeksoverleg Zoomarchief (27-10-2026).

Geen netwerk en geen sleutels. Nagebootst: de opnamelijst en de download van Zoom (zoom.opnames, zoom.download_naar;
hun grendels L1 en L5 toetst test_zoom_archief_bouwstenen.py), de Dropbox-API op het laagste niveau
(dropbox_prive._verzoek, met mode add zoals Dropbox het doet: de echte upload_bestand en metadata draaien), de ronde
van het bord en de klok.
Draaien: python3 mijnagents-runner/tests/test_zoom_archief.py
"""
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
MAP = tempfile.mkdtemp(prefix="zoom-archief-")
os.environ["HOME"] = os.path.join(MAP, "thuis")
os.makedirs(os.environ["HOME"], exist_ok=True)
os.environ["AGENTS_TOKEN"] = "proef"
for _k in [k for k in os.environ if k.startswith(("ZOOM_", "DROPBOX_"))]:
    del os.environ[_k]
os.environ.update(DROPBOX_PRIVE_APP_KEY="k", DROPBOX_PRIVE_APP_SECRET="g", DROPBOX_PRIVE_REFRESH_TOKEN="t")
sys.path.insert(0, HIER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import dropbox_prive as D  # noqa: E402
import zoom as Z  # noqa: E402
import zoom_account as ZA_ACC  # noqa: E402
import zoom_archief as ZA  # noqa: E402
from test_zoom_archief_bouwstenen import _Dropbox  # noqa: E402

ECHT_RONDE_GESLAAGD = ZA_ACC.archief_ronde_geslaagd
ECHTE_KETEN_DRAAIT = ZA.keten_draait   # opzet() vervangt haar; test_t0120_arch3 toetst de echte

# na de import: de bouwstenentest wist bij het laden elke DROPBOX_-sleutel
os.environ.update(DROPBOX_PRIVE_APP_KEY="k", DROPBOX_PRIVE_APP_SECRET="g", DROPBOX_PRIVE_REFRESH_TOKEN="t",
                  DROPBOX_PRIVE_ACCOUNT_ID="dbid:proef-eigen")

WERKWIJZE = open(os.path.join(RUNNER, "werkwijze", "zoom-archief.md"), encoding="utf-8").read()
NU = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)
GEHEIM_ONDERWERP = "Proefgesprek Zeta: huis/tuin"


class Ronde:
    def __init__(self, werkwijze=WERKWIJZE):
        self.werkwijze, self.noden, self.detail, self.bronnen, self.noden_onbekend = werkwijze, [], "", {}, False

    def nood(self, tekst, wie="mehdi"):
        if not any(n["tekst"] == tekst for n in self.noden):
            self.noden.append({"tekst": tekst, "wie": wie})

    def bron(self, naam, inhoud):
        self.bronnen[naam] = inhoud


class Zoom:
    """De opnamelijst en de downloads. meetings: uuid -> meeting zoals zoom.opnames ze geeft, met 'inhoud' per bestand."""

    def __init__(self):
        self.meetings, self.inhoud, self.gevraagd, self.downloads = {}, {}, [], []
        self.prullenbak = {"meeting_recordings": {}, "recording_file": {}}
        self.fout, self.lijstfout, self.bewaker_bij = {}, None, None

    def meeting(self, uuid, start, onderwerp="Overleg", bestanden=(), prullenbak=""):
        m = {"uuid": uuid, "nummer": "9100000001", "onderwerp": onderwerp, "start": start, "duur": 30, "bestanden": []}
        for i, (soort, opnametype, data) in enumerate(bestanden):
            fid = f"{uuid}-f{i}"
            self.inhoud[fid] = data
            m["bestanden"].append({"id": fid, "soort": soort, "status": "completed", "start": start, "einde": start,
                                   "grootte": len(data), "opnametype": opnametype, "extensie": soort, "link": True})
        (self.prullenbak[prullenbak] if prullenbak else self.meetings)[uuid] = m
        return m

    def opnames(self, van, tot, profiel="lees", prullenbak="", streng=False, bewaker=None):
        if bewaker:
            bewaker()
        self.gevraagd.append((van, tot, prullenbak))
        if self.lijstfout:
            raise self.lijstfout
        if prullenbak:
            assert van is None and tot is None, "de prullenbak zonder datums"
            return [json.loads(json.dumps(m)) for m in self.prullenbak[prullenbak].values()]
        return [json.loads(json.dumps(m)) for m in self.meetings.values() if van <= m["start"][:10] <= tot]

    def download_naar(self, fid, doel, profiel="lees", brok=1 << 20, bewaker=None):
        self.downloads.append(fid)
        if bewaker and self.bewaker_bij == fid:
            bewaker()
        if fid in self.fout:
            open(doel, "wb").write(b"half")
            raise self.fout[fid]
        open(doel, "wb").write(self.inhoud[fid])
        return len(self.inhoud[fid])


def opzet(**kw):
    """Een schone wereld: een eigen datamap, een lege Dropbox, een Zoom zonder opnames."""
    ZA.DATA = tempfile.mkdtemp(prefix="data-", dir=MAP)
    z = Zoom()
    Z.opnames, Z.download_naar = z.opnames, z.download_naar
    d = _Dropbox()
    D._verzoek = d
    ZA.mehdi_vastzetten = lambda: "mehdi-id"
    ZA.keten_draait = lambda: kw.get("keten", False)
    ZA.time.sleep = lambda s: None
    logs = []
    ZA.ag.log = lambda onderwerp, stap, tekst, detail="": logs.append(tekst)
    VOORSTELLEN.clear()
    ZA_ACC.archief_ronde_geslaagd = lambda ts: True  # het bord van De Zoomarchivaris; test_codex27 toetst het echte
    ZA.SEIN_AAN = kw.get("sein", True)  # de proeven toetsen de dekkingsregel zelf; test_sein_uit toetst de schakelaar
    ZA.ag.hartslag = lambda status, taak="", detail="", voorstel=None, **k: VOORSTELLEN.append(
        {"actie": voorstel["actie"], "status": "open", "reden": voorstel["reden"]}) if voorstel else None
    ZA.bord.db_lees = lambda sql, args=(): [dict(v) for v in VOORSTELLEN]
    return z, d, logs


VOORSTELLEN = []


def ronde(droog=False, budget=ZA.BUDGET, proef=0, klok=None, nu=NU):
    r = Ronde()
    uit = ZA.werk(r, droog=droog, budget=budget, proef=proef, klok=klok or (lambda: 0.0), nu_utc=lambda: nu)
    return r, uit


def teksten(r):
    return [n["tekst"] for n in r.noden]


def test_k2_paden_met_rare_tekens_brusselse_tijd_en_dubbele_namen():
    m1 = {"uuid": "a/b+c==", "start": "2026-10-20T13:04:00Z", "onderwerp": 'Klant: "huis/tuin" <1>?.'}
    m2 = {"uuid": "x/y+z==", "start": "2026-10-20T13:04:00Z", "onderwerp": 'Klant: "huis/tuin" <1>?.'}
    p1, p2 = ZA.mapnaam(m1), ZA.mapnaam(m2)
    assert p1.startswith("/Zoom/2026-10-20 1504 Klant huis tuin 1"), p1  # 13:04 UTC is 15:04 in Brussel (zomertijd)
    assert p1 != p2, "dezelfde tijd en hetzelfde onderwerp krijgen een andere map"
    assert not re.search(r'[\\<>:"|?*]', p1[1:].replace("/", "", 1)), p1
    assert p1.count("/") == 2, "geen / uit het onderwerp in het pad"
    f = {"id": "abc", "soort": "MP4", "opnametype": "shared_screen_with_speaker_view", "start": "2026-10-20T13:05:07Z"}
    g = {**f, "id": "abd"}
    assert ZA.bestandsnaam(f).startswith("150507 scherm en spreker ") and ZA.bestandsnaam(f).endswith(".mp4")
    assert ZA.bestandsnaam(f) != ZA.bestandsnaam(g), "twee delen met hetzelfde begin botsen niet"
    assert ZA.mapnaam({"uuid": "u", "start": "2026-10-20T13:04:00Z", "onderwerp": "  ..  "}).endswith(
        f"zonder onderwerp {ZA.kort('u')}")


def test_k3_kopie_met_bewijs_en_opname_json():
    z, d, logs = opzet()
    m = z.meeting("u1", "2026-10-20T13:04:00Z", GEHEIM_ONDERWERP,
                  [("MP4", "shared_screen_with_speaker_view", os.urandom(D.BROK + 5)), ("TRANSCRIPT", "audio_transcript", b"WEBVTT\n")])
    r, uit = ronde()
    assert uit["gedaan"] == 2 and uit["rest"] == 0, uit
    staat = ZA.lees_staat()
    for f in m["bestanden"]:
        pad = ZA.pad_van(m, f)
        assert d.bestanden[pad] == z.inhoud[f["id"]], "de kopie is hetzelfde bestand"
        assert staat["bestanden"][f["id"]]["hash"] == d._meta(pad)["content_hash"]
    beschrijving = json.loads(d.bestanden[ZA.mapnaam(m) + "/opname.json"])
    assert beschrijving["uuid"] == "u1" and len(beschrijving["bestanden"]) == 2
    assert not os.listdir(os.path.join(ZA.DATA, "werk")), "geen tijdelijk bestand blijft staan"
    assert not r.noden, r.noden
    blob = json.dumps(beschrijving)
    assert "download_url" not in blob and "zoom.us" not in blob, "geen link in de beschrijving"


def test_k3_zelfde_bestand_staat_er_al_bewezen_zonder_upload():
    z, d, _ = opzet()
    m = z.meeting("u1", "2026-10-20T13:04:00Z", bestanden=[("M4A", "audio_only", b"geluid")])
    f = m["bestanden"][0]
    d.bestanden[ZA.pad_van(m, f)] = b"geluid"  # een vorige ronde verloor het antwoord van Dropbox
    r, uit = ronde()
    assert uit["gedaan"] == 1 and not r.noden
    pad = ZA.pad_van(m, f)
    assert not [c for c in d.calls if c[0] == "files/upload" and c[1].get("path") == pad], "geen tweede upload"
    assert [c[1]["path"] for c in d.calls if c[0] == "files/upload"] == [ZA.mapnaam(m) + "/opname.json"]


def test_k3_ander_bestand_op_het_pad_nood_en_niets_overschreven():
    z, d, _ = opzet()
    m = z.meeting("u1", "2026-10-20T13:04:00Z", bestanden=[("M4A", "audio_only", b"geluid")])
    pad = ZA.pad_van(m, m["bestanden"][0])
    d.bestanden[pad] = b"iets anders"
    r, uit = ronde()
    assert d.bestanden[pad] == b"iets anders", "nooit overschreven"
    assert "Zoom-opname niet naar Dropbox gekopieerd: ander bestand op dat pad in Dropbox" in teksten(r)
    assert not ZA.lees_staat()["bestanden"] and uit["rest"] == 1


def test_k3_grootte_wijkt_af_nood_en_geen_staat():
    z, d, _ = opzet()
    m = z.meeting("u1", "2026-10-20T13:04:00Z", bestanden=[("MP4", "speaker_view", b"video")])
    m["bestanden"][0]["grootte"] = 999
    r, _ = ronde()
    assert "Zoom-opname niet naar Dropbox gekopieerd: download niet zo groot als Zoom opgeeft" in teksten(r)
    assert not d.bestanden and not ZA.lees_staat()["bestanden"]


def test_k3_afgebroken_upload_geen_staat_en_pas_na_drie_rondes_een_nood():
    z, d, _ = opzet()
    m = z.meeting("u1", "2026-10-20T13:04:00Z", bestanden=[("MP4", "speaker_view", os.urandom(D.BROK * 2 + 1))])
    echt = d.__call__

    def breekt(url, data, koppen, pogingen=5):
        if "append_v2" in url:
            raise OSError("verbinding weg")
        return echt(url, data, koppen, pogingen)
    D._verzoek = breekt
    for i in range(ZA.POGINGEN):
        r, uit = ronde()
        assert not d.bestanden and not ZA.lees_staat()["bestanden"], "een halve sessie is geen bestand en geen bewijs"
        assert not os.listdir(os.path.join(ZA.DATA, "werk"))
        if i < ZA.POGINGEN - 1:
            assert not r.noden, f"ronde {i + 1}: een tijdelijke fout is nog geen nood"
    assert any("Dropbox of de VM weigerde" in t for t in teksten(r)), teksten(r)
    D._verzoek = d
    r, uit = ronde()
    assert uit["gedaan"] == 1 and not r.noden, "daarna lukt het en sluit de nood"
    assert d.bestanden[ZA.pad_van(m, m["bestanden"][0])] == z.inhoud[m["bestanden"][0]["id"]]


def test_k3_zoom_weigert_de_download_meteen_een_nood():
    z, _, _ = opzet()
    m = z.meeting("u1", "2026-10-20T13:04:00Z", bestanden=[("MP4", "speaker_view", b"v")])
    z.fout[m["bestanden"][0]["id"]] = Z.GeenRecht("cloud_recording:read:x:admin", http=403)
    r, _ = ronde()
    assert "Zoom-opname niet naar Dropbox gekopieerd: Zoom weigert de download (cloud_recording:read:x:admin)" in teksten(r)


def test_k7_alleen_completed_en_de_prullenbak_eerst_dan_de_oudste():
    z, _, _ = opzet()
    nieuw = z.meeting("nieuw", "2026-10-25T09:00:00Z", bestanden=[("M4A", "audio_only", b"n")])
    oud = z.meeting("oud", "2021-08-10T09:00:00Z", bestanden=[("M4A", "audio_only", b"o")])
    weg = z.meeting("weg", "2026-09-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"p")], prullenbak="meeting_recordings")
    bezig = z.meeting("bezig", "2026-10-26T09:00:00Z", bestanden=[("MP4", "speaker_view", b"b")])
    bezig["bestanden"][0]["status"] = "processing"
    _, uit = ronde()
    assert z.downloads == [weg["bestanden"][0]["id"], oud["bestanden"][0]["id"], nieuw["bestanden"][0]["id"]], z.downloads
    assert {g[2] for g in z.gevraagd} >= {"meeting_recordings", "recording_file"}, "beide prullenbakken gelezen"
    assert uit["klaar"] == 3, "een opname die Zoom nog verwerkt, telt niet en wordt niet gekopieerd"
    assert bezig["uuid"] not in ZA.lees_staat()["meetings"], "geen opname.json zolang niet alles klaar is"


def test_k7_vensters_van_30_dagen_tot_de_eerste_dag_in_elke_ronde():
    z, _, _ = opzet()
    _, uit = ronde()
    vensters = sorted({(v, t) for v, t, p in z.gevraagd if not p})
    assert vensters[0][0] == ZA.EERSTE_DAG.isoformat() and uit["volledig"], "de eerste ronde leest alles"
    for v, t in vensters:
        dagen = (datetime.fromisoformat(t) - datetime.fromisoformat(v)).days
        assert 0 < dagen <= ZA.VENSTER, (v, t)
    z.gevraagd.clear()
    ronde(nu=NU + timedelta(hours=1))
    assert min(v for v, _, p in z.gevraagd if not p) == ZA.EERSTE_DAG.isoformat(), \
        "Codex controle 4, punt 19: ook het volgende uur leest alles, er is geen korte ronde meer"


def test_k6_dekking_pas_ja_na_een_volledige_inventaris_zonder_werk():
    z, _, _ = opzet()
    z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    _, uit = ronde()
    dek = json.load(open(os.path.join(ZA.DATA, "dekking.json")))
    assert uit["gedaan"] == 1 and not dek["dekking"], "net gekopieerd is nog geen dekking: eerst een tweede inventaris"
    assert ZA_ACC.archief_dekking(os.path.join(ZA.DATA, "dekking.json"), nu=NU) == "nee"
    _, uit = ronde()
    dek = json.load(open(os.path.join(ZA.DATA, "dekking.json")))
    assert uit["volledig"] and dek["dekking"] and dek["open"] == 0, dek
    assert ZA_ACC.archief_dekking(os.path.join(ZA.DATA, "dekking.json"), nu=NU) == "ja"
    assert ZA_ACC.archief_dekking(os.path.join(ZA.DATA, "dekking.json"), nu=NU + timedelta(days=3)) == "onbekend"
    assert ZA_ACC.archief_dekking(os.path.join(ZA.DATA, "bestaat-niet.json")) == "onbekend"


def test_k8_verdwenen_opname_nood_voor_mehdi_en_geen_dekking():
    z, _, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("MP4", "speaker_view", b"v")])
    z.fout[m["bestanden"][0]["id"]] = Z.ZoomFout("download: HTTP 500")
    ronde()
    del z.meetings["u1"]
    r, uit = ronde(nu=NU + timedelta(days=1))
    assert "Zoom-opname verdwenen voor ze in Dropbox stond" in teksten(r)
    assert next(n for n in r.noden if "verdwenen" in n["tekst"])["wie"] == "mehdi"
    assert not uit["dekking"]


def test_k4_tijdsbudget_keten_en_slot():
    z, _, _ = opzet()
    for i in range(3):
        z.meeting(f"u{i}", f"2026-10-2{i}T09:00:00Z", bestanden=[("M4A", "audio_only", b"x")])
    _, uit = ronde(budget=100, klok=lambda: 0.0 if not z.downloads else 200.0)  # na het eerste bestand is het budget op
    assert uit["gedaan"] == 1 and uit["gestopt"] == "tijdsbudget op", uit
    # de harde grens breekt ook een lopend bestand af: geen bewijs, het komt een volgende ronde
    z2, d2, _ = opzet()
    m = z2.meeting("u9", "2026-10-20T09:00:00Z", bestanden=[("M4A", "audio_only", b"y")])
    z2.bewaker_bij = m["bestanden"][0]["id"]
    _, uit = ronde(budget=100, klok=lambda: 0.0 if not z2.downloads else 10_000.0)
    assert uit["gestopt"].startswith("tijd op") and uit["gedaan"] == 0 and not d2.bestanden, uit
    assert not ZA.lees_staat()["bestanden"] and not os.listdir(os.path.join(ZA.DATA, "werk"))
    # en de inventaris zelf: een ronde die te laat begint, leest niet verder en sluit geen noden
    z3, _, _ = opzet()
    r, uit = ronde(nu=datetime(2026, 10, 27, 12, 59, tzinfo=timezone.utc))
    assert uit is None and r.noden_onbekend and "inventaris niet af" in r.detail, r.detail
    z, _, _ = opzet()
    for i in range(3):
        z.meeting(f"u{i}", f"2026-10-2{i}T09:00:00Z", bestanden=[("M4A", "audio_only", b"x")])
    _, uit = ronde(nu=datetime(2026, 10, 27, 12, 55, tzinfo=timezone.utc))
    assert uit["gedaan"] == 0 and uit["gestopt"] == "de gesprekkenketen begint", uit
    assert ZA.tot_keten(datetime(2026, 10, 27, 23, 25, tzinfo=timezone.utc)) == 300
    assert ZA.tot_keten(datetime(2026, 10, 27, 23, 31, tzinfo=timezone.utc)) == 7 * 3600 + 29 * 60, "na 23:30 de keten van 07:00"
    z, d, _ = opzet(keten=True)
    z.meeting("k1", "2026-10-20T09:00:00Z", bestanden=[("M4A", "audio_only", b"k")])
    aantal = len(d.calls)
    r, uit = ronde()
    assert uit is None and r.noden_onbekend and not z.gevraagd and len(d.calls) == aantal, \
        "Codex controle 7, punt 36: tijdens de keten geen enkele vraag aan Zoom of Dropbox"
    opzet(keten=None)
    r, uit = ronde()
    assert uit is None and r.noden_onbekend and "Kan niet nagaan of de gesprekkenketen draait" in teksten(r), \
        "Codex controle 6, punt 30: een onbekende keten is geen nee"


def test_k4_slot_weigert_een_tweede_ronde():
    import fcntl
    opzet()
    os.makedirs(ZA.DATA, exist_ok=True)
    houder = open(os.path.join(ZA.DATA, ".slot"), "w")
    fcntl.flock(houder, fcntl.LOCK_EX | fcntl.LOCK_NB)
    gestart = []
    ZA.ag.ronde = lambda taak: gestart.append(taak) or contextlib.nullcontext(Ronde())
    assert ZA.main([]) == 0 and not gestart, "een tweede ronde begint niet"
    houder.close()


def test_k7_stopsignaal_ruimt_het_tijdelijke_bestand_op():
    z, _, _ = opzet()
    m = z.meeting("u1", "2026-10-20T13:04:00Z", bestanden=[("MP4", "speaker_view", b"v")])
    z.fout[m["bestanden"][0]["id"]] = SystemExit(143)
    try:
        ronde()
        raise AssertionError("SystemExit verwacht")
    except SystemExit:
        pass
    assert not [n for n in os.listdir(os.path.join(ZA.DATA, "werk")) if n.endswith(".deel")]
    os.makedirs(os.path.join(ZA.DATA, "werk"), exist_ok=True)
    open(os.path.join(ZA.DATA, "werk", "rest.deel"), "w").write("x")
    ZA.ag.ronde = lambda taak: contextlib.nullcontext(Ronde())
    del z.fout[m["bestanden"][0]["id"]]
    ZA.main([])
    assert not os.path.exists(os.path.join(ZA.DATA, "werk", "rest.deel")), "main ruimt resten van een harde stop op"


def test_k8_schijf_vol_en_zoom_vraagt_rust_stoppen_de_ronde():
    z, _, _ = opzet()
    for i in range(2):
        z.meeting(f"u{i}", f"2026-10-2{i}T09:00:00Z", bestanden=[("M4A", "audio_only", b"x")])
    echt = shutil.disk_usage
    ZA.shutil.disk_usage = lambda p: echt(p)._replace(free=1)
    try:
        r, uit = ronde()
    finally:
        ZA.shutil.disk_usage = echt
    assert uit["gestopt"] == "te weinig vrije schijf op de VM" and not z.downloads
    assert "Te weinig vrije schijf op de VM voor de kopie van de Zoom-opnames" in teksten(r)
    z.fout[z.meetings["u0"]["bestanden"][0]["id"]] = Z.ZoomFout("download: HTTP 429")
    r, uit = ronde()
    assert uit["gestopt"] == "Zoom vraagt rust" and len(z.downloads) == 1, "na een 429 geen volgende download"


def test_k5_privacy_en_n10_geen_onderwerp_of_aantal():
    z, d, logs = opzet()
    m = z.meeting("u1", "2026-10-20T13:04:00Z", GEHEIM_ONDERWERP, [("MP4", "speaker_view", b"v")])
    z.meeting("u2", "2026-10-21T13:04:00Z", GEHEIM_ONDERWERP, [("MP4", "speaker_view", b"w")])
    z.fout[m["bestanden"][0]["id"]] = Z.GeenRecht("x:y:admin")
    r, _ = ronde()
    alles = json.dumps([r.detail, r.noden, r.bronnen, logs], ensure_ascii=False)
    assert "Zeta" not in alles and "huis" not in alles and "/Zoom/" not in alles, alles
    for t in teksten(r):
        assert not re.search(r"\d", t.replace("x:y:admin", "")), f"N10: geen aantal in de nood: {t}"
    assert any(d.startswith("/Zoom/") and "Zeta" in d for d in d.bestanden), "in Mehdi's eigen Dropbox mag het onderwerp"


def test_droog_kopieert_niets_en_schrijft_niets():
    z, d, _ = opzet()
    z.meeting("u1", "2026-10-20T13:04:00Z", bestanden=[("M4A", "audio_only", b"a")])
    r, uit = ronde(droog=True)
    assert uit["rest"] == 1 and not z.downloads and not d.bestanden
    assert not os.path.exists(ZA.staat_pad()) and not os.path.exists(os.path.join(ZA.DATA, "dekking.json"))
    assert not r.noden, "een droge ronde meldt geen achterstand"


def test_proef_neemt_de_kleinste_bestanden():
    z, _, _ = opzet()
    for i, n in enumerate((50, 3, 20, 1, 9)):
        z.meeting(f"u{i}", f"2026-10-2{i}T09:00:00Z", bestanden=[("M4A", "audio_only", b"x" * n)])
    _, uit = ronde(proef=3)
    assert uit["gedaan"] == 3 and sorted(len(z.inhoud[f]) for f in z.downloads) == [1, 3, 9]


def test_onleesbare_staat_is_een_fout_geen_lege_staat():
    opzet()
    os.makedirs(ZA.DATA, exist_ok=True)
    open(ZA.staat_pad(), "w").write("{kapot")
    try:
        ronde()
        raise AssertionError("een onleesbare staat hoort de ronde te breken")
    except ValueError:
        pass


def test_zonder_grenzen_of_token_geen_werk():
    z, _, _ = opzet()
    r = Ronde(werkwijze="# leeg\n")
    assert ZA.werk(r, nu_utc=lambda: NU) is None and r.noden and not z.gevraagd
    for k in ("DROPBOX_PRIVE_REFRESH_TOKEN",):
        oud = os.environ.pop(k)
        try:
            r, uit = ronde()
            assert uit is None and any("Dropbox" in t for t in teksten(r)) and not z.gevraagd
        finally:
            os.environ[k] = oud


def test_werkwijze_haalt_de_norm():
    import bord  # noqa: PLC0415
    import controle_agenten as CA  # noqa: PLC0415
    nooit, beslist = bord.grenzen(WERKWIJZE)
    assert len(nooit) >= 5 and len(beslist) >= 3
    assert any("verwijderen of overschrijven" in p for p in nooit)
    assert any("wisregel" in p for p in beslist)
    assert CA.n2_grenzen_in_werkwijze({"werkwijze": WERKWIJZE}, None)[0] and CA.n9_stijl({"werkwijze": WERKWIJZE}, None)[0]
    assert len(WERKWIJZE) >= 500 and "\N{EM DASH}" not in WERKWIJZE and not bord.HTML.search(WERKWIJZE)


def test_za01_wacht_op_de_dekking():
    """Codex-controle 1, punt 5: zonder dekking ja is ZA-01 geen open advies (dus geen voorstel om de wisregel aan te
    zetten); met dekking ja wel, met de kopie in de stand, zodat een geweigerd voorstel van daarvoor het niet tegenhoudt."""
    oud_pad = ZA_ACC.ARCHIEF_DEKKING
    ZA_ACC.ARCHIEF_DEKKING = os.path.join(tempfile.mkdtemp(prefix="dekking-", dir=MAP), "dekking.json")
    d = {"account": {"recording.auto_delete_cmr": False}, "opslag": {"pct": 98, "vol_dagen": 1, "vol_rond": "2026-10-28"},
         "opslagtrend": {"stand": "ok"}}
    try:
        za01 = lambda: next(a for a in ZA_ACC.adviezen(d) if a["code"] == "ZA-01")  # noqa: E731
        a = za01()
        assert a["toestand"] == "onbekend" and a["stand"] is None and "wacht op de volledige kopie" in a["reden"], a
        for dekking, ts in ((False, datetime.now(timezone.utc)), (True, datetime.now(timezone.utc) - timedelta(days=3))):
            json.dump({"ts": ts.isoformat(), "dekking": dekking}, open(ZA_ACC.ARCHIEF_DEKKING, "w"))
            assert za01()["toestand"] == "onbekend", (dekking, ts)
        json.dump({"ts": datetime.now(timezone.utc).isoformat(), "dekking": True}, open(ZA_ACC.ARCHIEF_DEKKING, "w"))
        a = za01()
        assert a["toestand"] == "open" and a["stand"] == {"wisregel": False, "band": 90, "kopie": "ja"}, a
        assert a["doel"].startswith("Zet een wisregel van 30 dagen aan") and "bewezen in je Dropbox" in a["reden"]
        oud = {"id": 40, "status": "geweigerd", "ts": "2026-10-26T13:04:57+00:00",
               "parameters": json.dumps({"cyclus": 0, "regelversie": 1, "stand": {"band": 90, "wisregel": False},
                                         "zoom_advies": "ZA-01"})}
        gekozen, _ = ZA_ACC.te_versturen([a], [oud], datetime(2026, 10, 27, 7, tzinfo=timezone.utc))
        assert [x["code"] for x in gekozen] == ["ZA-01"], "een geweigerd voorstel van voor de kopie houdt het niet tegen"
        d["account"]["recording.auto_delete_cmr"] = True
        assert za01()["toestand"] == "goed", "staat de wisregel al aan, dan is het goed, met of zonder kopie"
    finally:
        ZA_ACC.ARCHIEF_DEKKING = oud_pad


# ---------------------------------------------------- Codex-controle 1 en de drie controleurs (27-10-2026) ---
def test_codex2_los_gewist_bestand_in_de_prullenbak_wordt_gekopieerd_en_houdt_dekking_tegen():
    z, d, _ = opzet()
    z.meeting("u1", "2026-10-01T09:00:00Z", bestanden=[("TRANSCRIPT", "audio_transcript", b"WEBVTT\n")])
    los = z.meeting("tijdelijk", "2026-10-01T09:00:00Z", bestanden=[("MP4", "gallery_view", b"video")],
                    prullenbak="recording_file")
    z.prullenbak["recording_file"] = {"u1": {**los, "uuid": "u1", "bestanden": [{**los["bestanden"][0], "id": "u1-los"}]}}
    z.inhoud["u1-los"] = b"video"
    _, uit = ronde()
    assert "u1-los" in z.downloads and uit["gedaan"] == 2, z.downloads
    assert z.downloads[0] == "u1-los", "de prullenbak eerst"


def test_codex3_een_onvolledige_lijst_is_een_fout_en_geen_dekking():
    z, _, _ = opzet()
    z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    ronde()
    ronde()
    assert json.load(open(os.path.join(ZA.DATA, "dekking.json")))["dekking"]
    z.lijstfout = Z.ZoomFout("onvolledig antwoord van Zoom")
    r, uit = ronde(nu=NU + timedelta(days=1))
    assert uit is None and r.noden_onbekend and "Zoom-opnamelijst niet leesbaar" in teksten(r)
    z.lijstfout = None
    m = z.meeting("u2", "2026-10-20T09:00:00Z", bestanden=[("MP4", "speaker_view", b"v")])
    m["bestanden"][0]["link"] = False
    r, uit = ronde(nu=NU + timedelta(days=1))
    assert "Zoom gaf een onvolledige opname: bestand zonder id, downloadlink of bekende status" in teksten(r) and not uit["dekking"]
    r, uit = ronde(nu=NU + timedelta(days=1, hours=1))
    assert "Zoom gaf een onvolledige opname: bestand zonder id, downloadlink of bekende status" in teksten(r), \
        "het volgende uur houdt de nood (controle 2, punt 17)"
    z.meetings["u3"] = {"uuid": "u3", "nummer": "1", "onderwerp": "x", "start": "2026-10-21T09:00:00Z", "duur": 1,
                        "bestanden": []}
    r, uit = ronde(nu=NU + timedelta(days=2))
    assert "Zoom gaf een onvolledige opname: meeting zonder opnamebestanden" in teksten(r) and not uit["dekking"]


def test_codex4_een_bewijs_dat_uit_dropbox_verdween_wordt_nagekeken_en_opnieuw_gekopieerd():
    z, d, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    ronde()
    _, uit = ronde()
    assert uit["dekking"]
    del d.bestanden[ZA.pad_van(m, m["bestanden"][0])]  # iemand wiste de kopie in Dropbox
    r, uit = ronde(nu=NU + timedelta(days=1))
    assert not uit["dekking"] and uit["gedaan"] == 1, uit
    assert d.bestanden[ZA.pad_van(m, m["bestanden"][0])] == b"a", "opnieuw gekopieerd"
    _, uit = ronde(nu=NU + timedelta(days=1))
    assert uit["dekking"], "na een nieuwe volledige inventaris weer ja"


def test_dekking_blijft_ja_het_volgende_uur_en_valt_weg_bij_nieuw_werk():
    z, _, _ = opzet()
    z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    ronde()
    _, uit = ronde()
    assert uit["dekking"] and uit["volledig"]
    _, uit = ronde(nu=NU + timedelta(hours=1))
    assert uit["dekking"], "het volgende uur zonder nieuw werk: weer ja"
    assert ZA_ACC.archief_dekking(os.path.join(ZA.DATA, "dekking.json"), nu=NU + timedelta(hours=1)) == "ja"
    z.meeting("u2", "2026-10-27T09:00:00Z", bestanden=[("M4A", "audio_only", b"b")])
    _, uit = ronde(nu=NU + timedelta(hours=2), budget=-1)
    assert not uit["dekking"] and uit["rest"] == 1, "een nieuwe opname zonder kopie: nee"


def test_noden_blijven_staan_in_een_ronde_die_het_bestand_niet_probeert():
    z, d, _ = opzet()
    m = z.meeting("oud", "2025-03-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    d.bestanden[ZA.pad_van(m, m["bestanden"][0])] = b"iets anders"
    r, _ = ronde()
    tekst = "Zoom-opname niet naar Dropbox gekopieerd: ander bestand op dat pad in Dropbox"
    assert tekst in teksten(r)
    r, uit = ronde(nu=NU + timedelta(hours=1))
    assert tekst in teksten(r), "het volgende uur blijft de nood"
    del d.bestanden[ZA.pad_van(m, m["bestanden"][0])]
    r, _ = ronde(nu=NU + timedelta(days=1))
    assert tekst not in teksten(r), "na herstel gaat de nood dicht"


def test_vroege_stops_sluiten_geen_noden():
    opzet()
    ZA.mehdi_vastzetten = lambda: ""
    r, uit = ronde()
    assert uit is None and r.noden_onbekend and "Zoom-gebruiker van Mehdi niet bewezen" in teksten(r)
    opzet()
    oud = os.environ.pop("DROPBOX_PRIVE_REFRESH_TOKEN")
    try:
        r, uit = ronde()
        assert uit is None and r.noden_onbekend
    finally:
        os.environ["DROPBOX_PRIVE_REFRESH_TOKEN"] = oud


def test_codex6_alleen_naar_het_vastgelegde_dropbox_account():
    z, d, _ = opzet()
    z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    for account, mappen, verwacht in (
            ("dbid:proef-eigen", set(), "Dropbox niet gebruikt: gekoppelde Dropbox is niet Mehdi's privé-archief"),
            ("dbid:iemand-anders", {"/Fathom data"}, "Dropbox niet gebruikt: andere Dropbox gekoppeld dan vastgelegd")):
        d.account, d.mappen = account, mappen
        r, uit = ronde()
        assert uit is None and not z.downloads and verwacht in teksten(r) and r.noden_onbekend, teksten(r)
        assert next(n for n in r.noden if n["tekst"] == verwacht)["wie"] == "mehdi"
    oud = os.environ.pop("DROPBOX_PRIVE_ACCOUNT_ID")
    try:
        d.account, d.mappen = "dbid:proef-eigen", {"/Fathom data"}
        r, uit = ronde()
        assert uit is None and "Dropbox niet gebruikt: Dropbox-account voor de kopie niet vastgelegd" in teksten(r), \
            "zonder vastgelegd account kopieert de eerste ronde niets, ook niet met een map Fathom data"
    finally:
        os.environ["DROPBOX_PRIVE_ACCOUNT_ID"] = oud
    _, uit = ronde()
    assert uit["gedaan"] == 1


def test_codex8_verdwenen_komt_terug_of_mehdi_aanvaardt_het_gemis():
    z, _, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("MP4", "speaker_view", b"v")])
    fid = m["bestanden"][0]["id"]
    z.fout[fid] = Z.ZoomFout("download: HTTP 500")
    ronde()
    del z.meetings["u1"]
    r, uit = ronde(nu=NU + timedelta(days=1))
    assert "Zoom-opname verdwenen voor ze in Dropbox stond" in teksten(r) and not uit["dekking"]
    assert len(VOORSTELLEN) == 1 and VOORSTELLEN[0]["actie"].startswith(ZA.GEMIST_ACTIE), VOORSTELLEN
    assert "MB" in VOORSTELLEN[0]["reden"] and "Overleg" not in VOORSTELLEN[0]["reden"], "geen onderwerp in het voorstel"
    ronde(nu=NU + timedelta(days=1, hours=1))
    assert len(VOORSTELLEN) == 1, "een voorstel per opname, niet elke ronde"
    VOORSTELLEN[0]["status"] = "overgeslagen"  # Mehdi keurde goed; de uitvoerder maakte er "overgeslagen" van
    ronde(nu=NU + timedelta(days=2))
    r, uit = ronde(nu=NU + timedelta(days=2, hours=1))
    assert "Zoom-opname verdwenen voor ze in Dropbox stond" not in teksten(r) and uit["dekking"], (teksten(r), uit)
    assert fid in ZA.lees_staat()["gemist"]
    # een andere opname die verdwijnt en terugkomt, is niet meer verdwenen
    m2 = z.meeting("u2", "2026-08-02T09:00:00Z", bestanden=[("MP4", "speaker_view", b"w")])
    z.fout[m2["bestanden"][0]["id"]] = Z.ZoomFout("download: HTTP 500")
    ronde(nu=NU + timedelta(days=3))
    z.meetings.pop("u2")
    ronde(nu=NU + timedelta(days=4))
    assert m2["bestanden"][0]["id"] in ZA.lees_staat()["verdwenen"]
    z.meetings["u2"] = m2
    del z.fout[m2["bestanden"][0]["id"]]
    r, uit = ronde(nu=NU + timedelta(days=5))
    assert not ZA.lees_staat()["verdwenen"] and uit["gedaan"] == 1


def test_codex9_een_recht_dat_geen_recht_is_wordt_onbekend_recht():
    z, _, _ = opzet()
    m = z.meeting("u1", "2026-10-20T13:04:00Z", bestanden=[("M4A", "audio_only", b"a")])
    z.fout[m["bestanden"][0]["id"]] = Z.GeenRecht("https://zoom.us/rec/x?pwd=geheim")
    r, _ = ronde()
    assert "Zoom-opname niet naar Dropbox gekopieerd: Zoom weigert de download (onbekend recht)" in teksten(r), teksten(r)
    assert "zoom.us" not in json.dumps(r.noden)


def test_codex10_onduidelijk_antwoord_van_dropbox_meteen_nagekeken():
    z, d, _ = opzet()
    m = z.meeting("u1", "2026-10-20T13:04:00Z", bestanden=[("M4A", "audio_only", b"geluid")])
    echt = d.__call__

    def antwoord_weg(url, data, koppen, pogingen=5):
        uit = echt(url, data, koppen, pogingen)
        if url.endswith("files/upload") and b"geluid" == data:
            raise TimeoutError("antwoord verloren")
        return uit
    D._verzoek = antwoord_weg
    r, uit = ronde()
    assert uit["gedaan"] == 1 and not r.noden, "het bestand stond er wel: meteen bewezen, in dezelfde ronde"


def test_zonder_grootte_van_zoom_geen_bewijs():
    z, d, _ = opzet()
    m = z.meeting("u1", "2026-10-20T13:04:00Z", bestanden=[("TIMELINE", "timeline", b"{}")])
    m["bestanden"][0]["grootte"] = 0
    r, _ = ronde()
    assert "Zoom-opname niet naar Dropbox gekopieerd: Zoom geeft geen grootte op" in teksten(r)
    assert not d.bestanden and not ZA.lees_staat()["bestanden"]


# ---------------------------------------------------------------------- Codex-controle 2 (27-10-2026) ---
def test_codex11_kopie_weg_uit_dropbox_en_zoom_wordt_verdwenen_en_nooit_stil_dekking():
    z, d, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    ronde()
    _, uit = ronde()
    assert uit["dekking"]
    del d.bestanden[ZA.pad_van(m, m["bestanden"][0])]
    del z.meetings["u1"]
    for dag in (1, 2):
        r, uit = ronde(nu=NU + timedelta(days=dag))
        assert not uit["dekking"] and "Zoom-opname verdwenen voor ze in Dropbox stond" in teksten(r), (dag, uit)
    assert m["bestanden"][0]["id"] in ZA.lees_staat()["verdwenen"]


def test_codex11_een_korte_ronde_kijkt_de_bewijzen_ook_na():
    z, d, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    ronde()
    _, uit = ronde()
    assert uit["dekking"]
    del d.bestanden[ZA.pad_van(m, m["bestanden"][0])]
    _, uit = ronde(nu=NU + timedelta(hours=1))
    assert not uit["dekking"], "het volgende uur bevestigt geen dekking op een verdwenen kopie"
    assert not json.load(open(os.path.join(ZA.DATA, "dekking.json")))["dekking"]


def test_codex13_een_voorstel_dat_niet_op_het_bord_kwam_wordt_opnieuw_geprobeerd():
    z, _, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("MP4", "speaker_view", b"v")])
    z.fout[m["bestanden"][0]["id"]] = Z.ZoomFout("download: HTTP 500")
    ronde()
    del z.meetings["u1"]
    ZA.ag.hartslag = lambda *a, **k: None  # het bord slikte de fout in
    ronde(nu=NU + timedelta(days=1))
    assert not ZA.lees_staat()["voorstellen"], "niet teruggelezen, dus niet als verstuurd gemarkeerd"
    ZA.ag.hartslag = lambda status, taak="", detail="", voorstel=None, **k: VOORSTELLEN.append(
        {"actie": voorstel["actie"], "status": "open", "reden": voorstel["reden"]}) if voorstel else None
    ronde(nu=NU + timedelta(days=1, hours=1))
    assert len(VOORSTELLEN) == 1 and len(ZA.lees_staat()["voorstellen"]) == 1


def test_codex14_twee_opnames_met_dezelfde_sleutel_krijgen_geen_voorstel():
    z, _, _ = opzet()
    for u in ("u1", "u2"):
        m = z.meeting(u, "2026-08-01T09:00:00Z", bestanden=[("MP4", "speaker_view", b"v")])
        z.fout[m["bestanden"][0]["id"]] = Z.ZoomFout("download: HTTP 500")
    ronde()
    z.meetings.clear()
    echt = ZA.kort
    ZA.kort = lambda tekst, n=8: "0" * n if n == 16 else echt(tekst, n)
    try:
        r, uit = ronde(nu=NU + timedelta(days=1))
    finally:
        ZA.kort = echt
    assert not VOORSTELLEN and not uit["dekking"], "bij een botsing geen voorstel, en de dekking blijft nee"
    assert len(ZA.lees_staat()["verdwenen"]) == 2


def test_codex12_een_oud_open_za01_voorstel_houdt_het_advies_met_kopie_niet_tegen():
    a = {"code": "ZA-01", "ernst": "hoog", "toestand": "open", "stand": {"wisregel": False, "band": 90, "kopie": "ja"},
         "reden": "x", "doel": "y"}
    oud = {"id": 40, "status": "open", "ts": "2026-10-26T13:04:57+00:00",
           "parameters": json.dumps({"cyclus": 0, "regelversie": 1, "stand": {"band": 90, "wisregel": False},
                                     "zoom_advies": "ZA-01"})}
    gekozen, _ = ZA_ACC.te_versturen([a], [oud], datetime(2026, 10, 27, 7, tzinfo=timezone.utc))
    assert [x["code"] for x in gekozen] == ["ZA-01"]
    nieuw = {**oud, "id": 41, "parameters": json.dumps({"cyclus": 0, "regelversie": 1, "stand": a["stand"],
                                                        "zoom_advies": "ZA-01"})}
    gekozen, _ = ZA_ACC.te_versturen([a], [oud, nieuw], datetime(2026, 10, 27, 7, tzinfo=timezone.utc))
    assert not gekozen, "een open voorstel met de kopie in de stand houdt een tweede wel tegen"


# ---------------------------------------------------------------------- Codex-controle 3 (27-10-2026) ---
def _dekking():
    return json.load(open(os.path.join(ZA.DATA, "dekking.json")))


def _tot_ja(z):
    ronde()
    _, uit = ronde()
    assert uit["dekking"], uit


def test_codex3_bestand_zonder_id_en_status_houdt_dekking_tegen():
    z, _, _ = opzet()
    z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    _tot_ja(z)
    z.meetings["u1"]["bestanden"].append({"id": "", "soort": "MP4", "status": "", "start": "", "einde": "",
                                          "grootte": 0, "opnametype": "", "extensie": "", "link": False})
    r, uit = ronde(nu=NU + timedelta(days=1))
    assert not uit["dekking"] and not _dekking()["dekking"]
    assert "Zoom gaf een onvolledige opname: bestand zonder id, downloadlink of bekende status" in teksten(r)


def test_codex3_een_bestand_in_verwerking_houdt_dekking_tegen_tot_het_gekopieerd_is():
    z, _, _ = opzet()
    z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    _tot_ja(z)
    m = z.meeting("u2", "2026-10-27T09:00:00Z", bestanden=[("MP4", "speaker_view", b"v")])
    m["bestanden"][0]["status"] = "processing"
    _, uit = ronde(nu=NU + timedelta(hours=1))
    assert not uit["dekking"] and uit["veilig"], "nieuw en nog in verwerking: geen dekking, wel veilig voor de wisregel"


def test_codex5_een_mislukte_ronde_trekt_dekking_meteen_in():
    z, _, _ = opzet()
    z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    _tot_ja(z)
    ZA.mehdi_vastzetten = lambda: ""
    r, uit = ronde(nu=NU + timedelta(hours=1))
    assert uit is None and not _dekking()["dekking"] and not ZA.lees_staat()["dekking"]
    assert ZA_ACC.archief_dekking(os.path.join(ZA.DATA, "dekking.json"), nu=NU + timedelta(hours=1)) == "nee"
    ZA.mehdi_vastzetten = lambda: "mehdi-id"
    _, uit = ronde(nu=NU + timedelta(hours=2))
    assert uit["dekking"], "pas een nieuwe ronde die alles las en nakeek, geeft weer ja"
    assert ZA_ACC.archief_dekking(os.path.join(ZA.DATA, "dekking.json"), nu=NU + timedelta(hours=4)) == "ja"
    assert ZA_ACC.archief_dekking(os.path.join(ZA.DATA, "dekking.json"), nu=NU + timedelta(hours=6)) == "onbekend", \
        "een dekking geldt drie uur (Codex controle 4, punt 21)"


def test_codex7_de_tijdsgrens_geldt_ook_voor_de_dropbox_lijst():
    z, d, _ = opzet()
    z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    _tot_ja(z)
    echt = D.lijst_map
    tijd = {"nu": 0.0}

    def traag(pad, bewaker=None):
        tijd["nu"] = 10_000.0
        return echt(pad, bewaker=bewaker)
    D.lijst_map = traag
    try:
        r, uit = ronde(nu=NU + timedelta(days=1), klok=lambda: tijd["nu"])
    finally:
        D.lijst_map = echt
    assert uit is None and "nakijken niet af" in r.detail and not _dekking()["dekking"], r.detail


def test_codex11_een_aanvaard_gemis_dat_terugkomt_en_opnieuw_verdwijnt_vraagt_een_nieuw_besluit():
    z, d, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("MP4", "speaker_view", b"v")])
    fid = m["bestanden"][0]["id"]
    z.fout[fid] = Z.ZoomFout("download: HTTP 500")
    ronde()
    del z.meetings["u1"]
    ronde(nu=NU + timedelta(days=1))
    VOORSTELLEN[0]["status"] = "goedgekeurd"
    ronde(nu=NU + timedelta(days=1, hours=1))
    assert fid in ZA.lees_staat()["gemist"]
    z.meetings["u1"] = m  # ze komt terug, wordt gekopieerd, en verdwijnt dan uit Zoom en Dropbox
    del z.fout[fid]
    ronde(nu=NU + timedelta(days=2))
    assert fid in ZA.lees_staat()["bestanden"] and fid not in ZA.lees_staat()["gemist"]
    del z.meetings["u1"]
    del d.bestanden[ZA.pad_van(m, m["bestanden"][0])]
    for dag in (3, 4):
        r, uit = ronde(nu=NU + timedelta(days=dag))
        assert not uit["dekking"] and "Zoom-opname verdwenen voor ze in Dropbox stond" in teksten(r), dag
    assert len(VOORSTELLEN) == 2 and VOORSTELLEN[0]["actie"] != VOORSTELLEN[1]["actie"], "een nieuw besluit per verlies"


def test_codex13_geen_voorstel_als_het_bord_niet_te_lezen_is():
    z, _, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("MP4", "speaker_view", b"v")])
    z.fout[m["bestanden"][0]["id"]] = Z.ZoomFout("download: HTTP 500")
    ronde()
    del z.meetings["u1"]

    def onleesbaar(sql, args=()):
        raise ZA.bord.BordOnbekend("proef")
    ZA.bord.db_lees = onleesbaar
    for uur in (0, 1, 2):
        ronde(nu=NU + timedelta(days=1, hours=uur))
    assert not VOORSTELLEN, "zonder te kunnen lezen wat er al staat, zet ik niets (geen dubbels elk uur)"


def test_codex15_een_onvolledige_meeting_die_verdwijnt_houdt_de_dekking_tegen():
    z, _, _ = opzet()
    z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    z.meetings["leeg"] = {"uuid": "leeg", "nummer": "1", "onderwerp": "x", "start": "2026-10-20T09:00:00Z", "duur": 1,
                          "bestanden": []}
    ronde()
    del z.meetings["leeg"]
    for dag in (1, 2):
        r, uit = ronde(nu=NU + timedelta(days=dag))
        assert not uit["dekking"] and "meeting:leeg" in ZA.lees_staat()["verdwenen"], dag
    assert any("meeting zonder bruikbare bestanden" in v["reden"] for v in VOORSTELLEN), VOORSTELLEN


def test_codex12_de_zoomwacht_waarschuwt_bij_een_open_wisregelvoorstel_zonder_veilige_kopie():
    oud_pad, oud_lezen = ZA_ACC.ARCHIEF_DEKKING, ZA_ACC.voorstellen_lezen
    ZA_ACC.ARCHIEF_DEKKING = os.path.join(tempfile.mkdtemp(prefix="veilig-", dir=MAP), "dekking.json")
    rij = {"id": 41, "status": "open", "parameters": json.dumps({"zoom_advies": "ZA-01", "stand": {"kopie": "ja"}})}
    try:
        for rijen, veilig, verwacht in (([rij], None, True), ([rij], False, True), ([rij], True, False),
                                        ([{**rij, "status": "geweigerd"}], False, False), ([], False, False),
                                        ([{**rij, "status": "goedgekeurd"}], False, True)):
            if veilig is None:
                if os.path.exists(ZA_ACC.ARCHIEF_DEKKING):
                    os.remove(ZA_ACC.ARCHIEF_DEKKING)
            else:
                json.dump({"ts": datetime.now(timezone.utc).isoformat(), "dekking": veilig, "wisregel_veilig": veilig},
                          open(ZA_ACC.ARCHIEF_DEKKING, "w"))
            ZA_ACC.voorstellen_lezen = lambda: rijen
            r = Ronde()
            ZA_ACC.wisregel_wacht(r)
            assert (ZA_ACC.NOOD_WISREGEL_WACHT in teksten(r)) is verwacht, (rijen, veilig)
            assert not re.search(r"\d", ZA_ACC.NOOD_WISREGEL_WACHT), "N10"
    finally:
        ZA_ACC.ARCHIEF_DEKKING, ZA_ACC.voorstellen_lezen = oud_pad, oud_lezen


# ---------------------------------------------------------------------- Codex-controle 4 (27-10-2026) ---
def test_codex18_een_bestand_zonder_id_dat_verdwijnt_uit_een_verder_goede_meeting_is_een_verlies():
    z, _, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    m["bestanden"].append({"id": "", "soort": "MP4", "status": "completed", "start": "2026-08-01T09:00:00Z", "einde": "",
                           "grootte": 9, "opnametype": "speaker_view", "extensie": "MP4", "link": True})
    ronde()
    m["bestanden"].pop()  # het bestand zonder id is weg; de rest van de meeting is bewezen
    for uur in (1, 2):
        r, uit = ronde(nu=NU + timedelta(hours=uur))
        assert not uit["dekking"] and not uit["veilig"], uur
        assert "Zoom-opname verdwenen voor ze in Dropbox stond" in teksten(r)


def test_codex19_een_oude_opname_die_later_opduikt_wordt_het_volgende_uur_gezien():
    z, _, _ = opzet()
    _tot_ja(z)
    z.meeting("oud", "2022-01-05T09:00:00Z", bestanden=[("M4A", "audio_only", b"o")])
    _, uit = ronde(nu=NU + timedelta(hours=1), budget=-1)
    assert not uit["dekking"] and not uit["veilig"] and uit["rest"] == 1, uit


def test_codex20_een_bestand_in_verwerking_dat_verdwijnt_en_een_volle_schijf_blijven_tellen():
    z, _, _ = opzet()
    z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    m = z.meeting("u2", "2026-10-27T09:00:00Z", bestanden=[("MP4", "speaker_view", b"v")])
    m["bestanden"][0]["status"] = "processing"
    ronde()
    del z.meetings["u2"]
    r, uit = ronde(nu=NU + timedelta(hours=1))
    assert not uit["dekking"] and m["bestanden"][0]["id"] in ZA.lees_staat()["verdwenen"], ZA.lees_staat()["verdwenen"]
    z2, _, _ = opzet()
    z2.meeting("oud", "2022-01-05T09:00:00Z", bestanden=[("M4A", "audio_only", b"o")])
    echt = shutil.disk_usage
    ZA.shutil.disk_usage = lambda p: echt(p)._replace(free=1)
    try:
        r, uit = ronde()
        assert not uit["veilig"] and ZA.SCHIJF_VOL in teksten(r)
        r, uit = ronde(nu=NU + timedelta(hours=1))
        assert not uit["veilig"] and ZA.SCHIJF_VOL in teksten(r), "de nood blijft tot het weer lukt (punt 23)"
    finally:
        ZA.shutil.disk_usage = echt
    r, uit = ronde(nu=NU + timedelta(hours=2))
    assert uit["gedaan"] == 1 and ZA.SCHIJF_VOL not in teksten(r)


def test_codex21_33_36_tijdens_de_keten_wordt_het_sein_ingetrokken_en_een_ja_geldt_drie_uur():
    z, d, _ = opzet()
    z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    _tot_ja(z)
    pad = os.path.join(ZA.DATA, "dekking.json")
    assert ZA_ACC.archief_dekking(pad, nu=NU + timedelta(hours=3, minutes=1)) == "onbekend", "na drie uur: onbekend"
    ZA.keten_draait = lambda: True
    r, uit = ronde(nu=NU + timedelta(hours=1))
    assert uit is None and not _dekking()["dekking"], "De Zoomwacht leest in de keten nooit een oude ja"


def test_codex22_een_onleesbaar_bord_bij_de_wisregelwaarschuwing_sluit_niets():
    oud = ZA_ACC.voorstellen_lezen

    def kapot():
        raise ZA.bord.BordOnbekend("proef")
    ZA_ACC.voorstellen_lezen = kapot
    try:
        r = Ronde()
        ZA_ACC.wisregel_wacht(r)
        assert r.noden_onbekend and "Zoom-advies niet terug te lezen op het bord" in teksten(r)
    finally:
        ZA_ACC.voorstellen_lezen = oud


def test_codex23_een_mislukte_opname_json_blijft_gemeld_tot_ze_lukt():
    z, d, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    echt = d.__call__

    def geen_json(url, data, koppen, pogingen=5):
        if "opname.json" in (koppen.get("Dropbox-API-Arg") or ""):
            raise OSError("weg")
        return echt(url, data, koppen, pogingen)
    D._verzoek = geen_json
    for uur in (0, 1):
        r, uit = ronde(nu=NU + timedelta(hours=uur))
        assert ZA.OPNAME_JSON in teksten(r) and not uit["dekking"], uur
    D._verzoek = d
    r, uit = ronde(nu=NU + timedelta(hours=2))
    assert ZA.OPNAME_JSON not in teksten(r) and ZA.mapnaam(m) + "/opname.json" in d.bestanden


# ------------------------------------------------- de twee aanvallers op 8075c96 (27-10-2026), wat nog gold ---
def test_aanval_een_harde_stop_of_een_kapotte_staat_laat_geen_oude_ja_staan():
    z, d, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    _tot_ja(z)
    del d.bestanden[ZA.pad_van(m, m["bestanden"][0])]
    z.fout[m["bestanden"][0]["id"]] = SystemExit(143)  # de ronde begint te herkopiëren en krijgt een stopsignaal
    try:
        ronde(nu=NU + timedelta(hours=1))
        raise AssertionError("SystemExit verwacht")
    except SystemExit:
        pass
    assert not _dekking()["dekking"], "na een harde stop staat er geen ja"
    del z.fout[m["bestanden"][0]["id"]]
    _tot_ja(z)
    open(ZA.staat_pad(), "w").write("")
    try:
        ronde(nu=NU + timedelta(hours=3))
        raise AssertionError("een kapotte staat hoort de ronde te breken")
    except ValueError:
        pass
    assert not _dekking()["dekking"], "met een kapotte staat staat er geen ja"


def test_aanval_een_droge_ronde_sluit_geen_nood():
    z, d, _ = opzet()
    m = z.meeting("u1", "2025-03-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    d.bestanden[ZA.pad_van(m, m["bestanden"][0])] = b"iets anders"
    r, _ = ronde()
    assert r.noden
    r, _ = ronde(droog=True)
    assert r.noden_onbekend, "een droge ronde laat het bord niets sluiten"


def test_aanval_een_mislukte_controle_van_dropbox_blijft_gemeld_tot_ze_lukt():
    z, d, _ = opzet()
    z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    _tot_ja(z)
    echt = D.lijst_map

    def kapot(pad, bewaker=None):
        raise OSError("weg")
    D.lijst_map = kapot
    try:
        for uur in (1, 2):
            r, uit = ronde(nu=NU + timedelta(hours=uur))
            assert "Dropbox niet nagekeken (OSError)" in teksten(r) and not uit["dekking"] and not uit["veilig"], uur
    finally:
        D.lijst_map = echt
    r, uit = ronde(nu=NU + timedelta(hours=3))
    assert "Dropbox niet nagekeken (OSError)" not in teksten(r) and uit["dekking"]


def test_aanval_een_blijvende_fout_wordt_niet_verdrongen_door_een_tijdelijke():
    z, d, _ = opzet()
    m = z.meeting("u1", "2025-03-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    d.bestanden[ZA.pad_van(m, m["bestanden"][0])] = b"iets anders"
    tekst = "Zoom-opname niet naar Dropbox gekopieerd: ander bestand op dat pad in Dropbox"
    r, _ = ronde()
    assert tekst in teksten(r)
    z.fout[m["bestanden"][0]["id"]] = Z.ZoomFout("download: HTTP 500")
    r, _ = ronde(nu=NU + timedelta(hours=1))
    assert tekst in teksten(r), "de afwijking blijft gemeld, ook als Zoom die ronde even niets gaf"


def test_aanval_een_bestand_dat_alsnog_een_link_krijgt_is_geen_verlies():
    z, _, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("MP4", "speaker_view", b"v")])
    m["bestanden"][0]["link"] = False
    r, uit = ronde()
    assert not uit["dekking"] and any("onvolledige opname" in x for x in teksten(r))
    m["bestanden"][0]["link"] = True
    r, uit = ronde(nu=NU + timedelta(hours=1))
    assert not ZA.lees_staat()["verdwenen"] and uit["gedaan"] == 1, (ZA.lees_staat()["verdwenen"], uit)
    _, uit = ronde(nu=NU + timedelta(hours=2))
    assert uit["dekking"]


# ---------------------------------------------------------------------- Codex-controle 5 (27-10-2026) ---
def test_sein_uit_geeft_nooit_dekking_of_veilig():
    z, _, _ = opzet(sein=False)
    z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    ronde()
    _, uit = ronde()
    assert uit["gedaan"] == 0 and uit["rest"] == 0, "alles is gekopieerd en bewezen"
    assert not uit["dekking"] and not uit["veilig"] and not _dekking()["dekking"] and not _dekking()["wisregel_veilig"]


def test_sein_staat_uit_in_de_code():
    bron = open(os.path.join(RUNNER, "zoom_archief.py"), encoding="utf-8").read()
    assert re.search(r"^SEIN_AAN = False$", bron, re.M), "het groene sein gaat pas aan na het akkoord van Codex"


def test_codex25_twee_gelijke_bestanden_zonder_id_zijn_twee_gevallen():
    z, _, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    for _ in range(2):
        m["bestanden"].append({"id": "", "soort": "MP4", "status": "completed", "start": "2026-08-01T09:00:00Z",
                               "einde": "", "grootte": 9, "opnametype": "speaker_view", "extensie": "MP4", "link": True})
    ronde()
    del m["bestanden"][1:]
    ronde(nu=NU + timedelta(hours=1))
    assert len(ZA.lees_staat()["verdwenen"]) == 2 and len(VOORSTELLEN) == 2, (ZA.lees_staat()["verdwenen"], VOORSTELLEN)
    VOORSTELLEN[0]["status"] = "goedgekeurd"
    ronde(nu=NU + timedelta(hours=2))
    r, uit = ronde(nu=NU + timedelta(hours=3))
    assert not uit["dekking"] and not uit["veilig"] and len(ZA.lees_staat()["verdwenen"]) == 1, "een besluit per geval"


def test_codex26_een_andere_grootte_in_zoom_laat_het_bewijs_vervallen():
    z, d, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    _tot_ja(z)
    m["bestanden"][0]["grootte"] = 2
    z.inhoud[m["bestanden"][0]["id"]] = b"aa"
    r, uit = ronde(nu=NU + timedelta(hours=1))
    assert not uit["dekking"] and not uit["veilig"]
    assert any("andere grootte" in x or "ander bestand op dat pad" in x for x in teksten(r)), teksten(r)
    assert d.bestanden[ZA.pad_van(m, m["bestanden"][0])] == b"a", "de bestaande kopie wordt niet overschreven"


def test_codex27_een_ja_telt_alleen_na_een_geslaagde_archiefronde():
    pad = os.path.join(tempfile.mkdtemp(prefix="ronde-", dir=MAP), "dekking.json")
    ts = datetime.now(timezone.utc).replace(microsecond=0)
    json.dump({"ts": ts.isoformat(), "dekking": True, "wisregel_veilig": True}, open(pad, "w"))
    oud_lees, oud_geslaagd = ZA_ACC.bord.db_lees, ZA_ACC.archief_ronde_geslaagd
    ZA_ACC.archief_ronde_geslaagd = ECHT_RONDE_GESLAAGD
    try:
        for status, delta, verwacht in (("klaar", 5, "ja"), ("waakt", 5, "ja"), ("actief", 60, "onbekend"),
                                        ("fout", 60, "onbekend"), ("klaar", -60, "onbekend")):
            ZA_ACC.bord.db_lees = lambda sql, args=(), s=status, dt=delta: [
                {"status": s, "taak": "opnames naar Dropbox", "ts": (ts + timedelta(seconds=dt)).isoformat()}]
            assert ZA_ACC.archief_dekking(pad) == verwacht, (status, delta)
            assert ZA_ACC.archief_veilig(pad) == verwacht, (status, delta)

        def kapot(sql, args=()):
            raise ZA_ACC.bord.BordOnbekend("proef")
        ZA_ACC.bord.db_lees = kapot
        assert ZA_ACC.archief_dekking(pad) == "onbekend"
    finally:
        ZA_ACC.bord.db_lees, ZA_ACC.archief_ronde_geslaagd = oud_lees, oud_geslaagd


def test_codex28_een_mislukte_beschrijving_wordt_opnieuw_geprobeerd_ook_als_de_meeting_weg_is():
    z, d, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    echt = d.__call__

    def geen_json(url, data, koppen, pogingen=5):
        if "opname.json" in (koppen.get("Dropbox-API-Arg") or ""):
            raise OSError("weg")
        return echt(url, data, koppen, pogingen)
    D._verzoek = geen_json
    r, _ = ronde()
    assert ZA.OPNAME_JSON in teksten(r)
    del z.meetings["u1"]
    r, _ = ronde(nu=NU + timedelta(hours=1))
    assert ZA.OPNAME_JSON in teksten(r), "de meeting is weg, de nood blijft"
    D._verzoek = d
    r, _ = ronde(nu=NU + timedelta(hours=2))
    assert ZA.OPNAME_JSON not in teksten(r) and ZA.mapnaam(m) + "/opname.json" in d.bestanden


# ---------------------------------------------------------------------- Codex-controle 6 (27-10-2026) ---
def test_codex32_een_onverwachte_fout_draagt_geen_link_naar_het_bord():
    z, _, _ = opzet()
    z.lijstfout = ValueError("invalid literal for int(): 'https://proef.zoom.us/rec/download/x?access_token=geheim'")
    try:
        ronde()
        raise AssertionError("een onverwachte fout hoort de ronde te breken")
    except RuntimeError as e:
        assert str(e) == "onverwachte fout (ValueError)", str(e)
        assert e.__cause__ is None and e.__suppress_context__, "de oorspronkelijke tekst gaat niet mee"


def test_codex34_een_bewezen_bestand_waarvoor_zoom_geen_grootte_geeft_is_niet_meer_bewezen():
    z, _, _ = opzet()
    m = z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    _tot_ja(z)
    m["bestanden"][0]["grootte"] = 0
    r, uit = ronde(nu=NU + timedelta(hours=1))
    assert not uit["dekking"] and not uit["veilig"] and any("grootte" in x for x in teksten(r)), teksten(r)


def test_codex35_een_tijdstip_met_een_andere_tijdzone_telt_juist():
    z, _, _ = opzet()
    m = z.meeting("u1", "2026-09-20T23:30:00+02:00", bestanden=[("M4A", "audio_only", b"a")])
    z.fout[m["bestanden"][0]["id"]] = Z.ZoomFout("download: HTTP 500")
    m2 = z.meeting("u2", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"b")])
    _, uit = ronde()
    assert uit["oud_open"] == 1 and not uit["veilig"], "ouder dan 30 dagen, ook met +02:00"
    assert ZA._utc("2026-09-20T23:30:00+02:00") == datetime(2026, 9, 20, 21, 30, tzinfo=timezone.utc)
    assert ZA._utc("geen tijd") is None


# ---------------------------------------------------------------------- Codex-controle 7 (27-10-2026) ---
def test_codex37_een_opname_die_tijdens_de_ronde_opduikt_houdt_groen_tegen():
    z, _, _ = opzet()
    z.meeting("u1", "2026-08-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"a")])
    _tot_ja(z)
    echt = z.opnames
    gezien = {"n": 0}

    def opnames(van, tot, profiel="lees", prullenbak="", streng=False, bewaker=None):
        uit = echt(van, tot, profiel, prullenbak, streng, bewaker)
        if prullenbak == "recording_file":
            gezien["n"] += 1
            if gezien["n"] == 1:  # het einde van de eerste inventaris: nu duikt een oude opname op
                z.meeting("laat", "2022-02-02T09:00:00Z", bestanden=[("M4A", "audio_only", b"l")])
        return uit
    Z.opnames = opnames
    _, uit = ronde(nu=NU + timedelta(hours=1))
    assert gezien["n"] == 2 and not uit["dekking"] and not uit["veilig"], (gezien, uit)
    assert not _dekking()["dekking"] and not _dekking()["wisregel_veilig"]


def test_codex38_een_droge_of_proefronde_bevestigt_geen_ja():
    pad = os.path.join(tempfile.mkdtemp(prefix="taak-", dir=MAP), "dekking.json")
    ts = datetime.now(timezone.utc).replace(microsecond=0)
    json.dump({"ts": ts.isoformat(), "dekking": True, "wisregel_veilig": True}, open(pad, "w"))
    oud_lees, oud_geslaagd = ZA_ACC.bord.db_lees, ZA_ACC.archief_ronde_geslaagd
    ZA_ACC.archief_ronde_geslaagd = ECHT_RONDE_GESLAAGD
    try:
        for taak, verwacht in (("opnames naar Dropbox", "ja"), ("opnames naar Dropbox (droog)", "onbekend"),
                               ("opnames naar Dropbox (proef)", "onbekend"), ("", "onbekend")):
            ZA_ACC.bord.db_lees = lambda sql, args=(), tk=taak: [
                {"status": "klaar", "taak": tk, "ts": (ts + timedelta(seconds=5)).isoformat()}]
            assert ZA_ACC.archief_dekking(pad) == verwacht and ZA_ACC.archief_veilig(pad) == verwacht, taak
    finally:
        ZA_ACC.bord.db_lees, ZA_ACC.archief_ronde_geslaagd = oud_lees, oud_geslaagd
    assert ZA.TAAK == "opnames naar Dropbox", "de taak van een echte ronde is wat De Zoomwacht verwacht"

# ------------------------------------------------------------------------- T-0120 (meting 01-10 tot 01-11) ---
VERDWENEN = "Zoom-opname verdwenen voor ze in Dropbox stond"


def _in_verwerking(z, uuid, start, soort="MP4", opnametype="shared_screen_with_speaker_view"):
    """Een meeting waarvan Zoom nog een bestand verwerkt: status processing, nog zonder grootte."""
    m = z.meeting(uuid, start, bestanden=[(soort, opnametype, b"")])
    m["bestanden"][0].update(status="processing", grootte=None, link=False)
    return m["bestanden"][0]["id"]


def _afgewerkt(z, uuid, start, voorvoegsel, bestanden):
    """Dezelfde meeting na de verwerking: afgewerkte bestanden met nieuwe id's (zoals Zoom het doet)."""
    m = z.meeting(uuid, start, bestanden=bestanden)
    for f in m["bestanden"]:
        oud = f["id"]
        f["id"] = voorvoegsel + oud
        z.inhoud[f["id"]] = z.inhoud.pop(oud)
    return m


DRIE = [("MP4", "shared_screen_with_speaker_view", b"video"), ("TIMELINE", "timeline", b"{}"),
        ("TRANSCRIPT", "audio_transcript", b"WEBVTT")]


def test_t0120_arch1_verwerking_vervangen_door_bewezen_bestanden_is_geen_verlies():
    """ARCH-1 (meting 01-11-2026): Zoom vervangt een bestand in verwerking door de afgewerkte bestanden met andere id's;
    de agent noemde het oude id dan verdwenen, met een nood voor Mehdi en een voorstel per geval (22 open). Nu: een
    verdwenen verwerkings-id is geen verlies als dezelfde meeting nu een bewezen afgewerkt bestand van dezelfde soort
    heeft dat er nog niet was toen ik het zag; het geval gaat met dat bewijs naar 'vervallen'. Elk ander ontbrekend
    bestand blijft verdwenen."""
    z, _, _ = opzet()
    start = "2026-10-28T09:00:00Z"
    x = _in_verwerking(z, "u1", start)
    ronde()
    assert x in ZA.lees_staat()["gezien"] and ZA.lees_staat()["gezien"][x]["status"] == "processing"
    m = _afgewerkt(z, "u1", start, "klaar-", DRIE)
    r, uit = ronde(nu=NU + timedelta(hours=1))
    staat = ZA.lees_staat()
    assert uit["gedaan"] == 3 and not staat["verdwenen"] and VERDWENEN not in teksten(r) and not VOORSTELLEN, (staat["verdwenen"], teksten(r))
    assert x in staat["vervallen"] and staat["vervallen"][x]["door"] == m["bestanden"][0]["id"], staat["vervallen"]
    assert staat["vervallen"][x]["reden"].startswith("vervangen"), staat["vervallen"][x]
    assert x not in staat["gezien"] and "vervangen 1" in r.detail, r.detail
    _, uit = ronde(nu=NU + timedelta(hours=2))
    assert uit["dekking"], "na de vervanging en een tweede inventaris: dekking ja"


def test_t0120_arch1_een_ander_ontbrekend_bestand_blijft_verdwenen():
    """ARCH-1: alleen een bewezen vervanging telt. Een verwerkt geluidsbestand dat verdwijnt terwijl alleen video,
    tijdlijn en transcript komen, blijft verdwenen; zo ook een tweede video in verwerking in een meeting die al een
    bewezen video had (die was er al toen ik ze zag), en een verwerkingsbestand van een meeting die helemaal weg is."""
    z, _, _ = opzet()
    a = _in_verwerking(z, "geluid", "2026-10-28T09:00:00Z", soort="M4A", opnametype="audio_only")
    ronde()
    _afgewerkt(z, "geluid", "2026-10-28T09:00:00Z", "klaar-", DRIE)
    r, _ = ronde(nu=NU + timedelta(hours=1))
    assert a in ZA.lees_staat()["verdwenen"] and VERDWENEN in teksten(r), ZA.lees_staat()["verdwenen"]

    z, _, _ = opzet()
    m = z.meeting("twee", "2026-10-28T10:00:00Z", bestanden=DRIE)
    ronde()
    tweede = {"id": "twee-tweede", "soort": "MP4", "status": "processing", "start": "2026-10-28T10:30:00Z", "einde": "",
              "grootte": None, "opnametype": "shared_screen_with_speaker_view", "extensie": "MP4", "link": False}
    m["bestanden"].append(tweede)
    ronde(nu=NU + timedelta(hours=1))
    m["bestanden"].remove(tweede)
    r, _ = ronde(nu=NU + timedelta(hours=2))
    assert "twee-tweede" in ZA.lees_staat()["verdwenen"] and VERDWENEN in teksten(r), "een oud bewijs is geen vervanging"

    z, _, _ = opzet()
    b = _in_verwerking(z, "weg", "2026-10-28T11:00:00Z")
    ronde()
    del z.meetings["weg"]
    r, _ = ronde(nu=NU + timedelta(hours=1))
    assert b in ZA.lees_staat()["verdwenen"] and VERDWENEN in teksten(r)


def test_t0120_arch1_een_vervanging_die_zelf_verdwijnt_voor_ze_bewezen_is():
    """ARCH-1: een vervanging telt pas als ze bewezen is. Lukt de kopie niet, dan wacht het verwerkingsbestand (geen nood,
    de vervanging zelf houdt de dekking tegen); verdwijnt de vervanging dan ook, dan zijn beide verdwenen."""
    z, _, _ = opzet()
    start = "2026-10-28T09:00:00Z"
    x = _in_verwerking(z, "u1", start)
    ronde()
    m = _afgewerkt(z, "u1", start, "klaar-", DRIE[:1])
    y = m["bestanden"][0]["id"]
    z.fout[y] = Z.ZoomFout("download: HTTP 500")
    r, uit = ronde(nu=NU + timedelta(hours=1))
    staat = ZA.lees_staat()
    assert not staat["verdwenen"] and staat["gezien"][x]["vervangen_door"] == y and not uit["dekking"], staat["gezien"]
    del z.meetings["u1"]
    r, _ = ronde(nu=NU + timedelta(hours=2))
    staat = ZA.lees_staat()
    assert x in staat["verdwenen"] and y in staat["verdwenen"] and VERDWENEN in teksten(r), staat["verdwenen"]


def _oude_staat():
    """Een staat zoals op de VM na 27-10: drie verdwenen gevallen van voor ARCH-1 (zonder meeting of soort). Het eerste
    heeft een map met video, tijdlijn en transcript met dezelfde starttijd, bewezen in de ronde waarin het verdween; het
    tweede heeft dat bewijs maar mist het transcript; het derde is een meeting zonder bestanden."""
    staat = ZA.lees_staat()
    st, sinds = "2026-10-28T09:00:05Z", "2026-10-28T10:05:00+00:00"
    staat["verdwenen"] = {
        "oud-a": {"start": st, "grootte": 0, "sinds": sinds},
        "oud-b": {"start": "2026-10-29T09:00:05Z", "grootte": 0, "sinds": "2026-10-29T10:05:00+00:00"},
        "meeting:oud-c": {"start": "2026-10-29T12:00:00Z", "grootte": 0, "sinds": sinds}}
    kaart = "/Zoom/2026-10-28 1000 Proefgesprek Zeta abcd1234"
    for i, (soort, ext) in enumerate((("scherm en spreker", "mp4"), ("tijdlijn", "json"), ("transcript", "vtt"))):
        staat["bestanden"][f"nieuw-a{i}"] = {"pad": f"{kaart}/100005 {soort} a{i}.{ext}", "grootte": 10, "hash": "h",
                                             "start": st, "ts": "2026-10-28T10:20:00+00:00"}
    kaart_b = "/Zoom/2026-10-29 1000 Proefgesprek Eta bcde2345"
    for i, (soort, ext) in enumerate((("scherm en spreker", "mp4"), ("tijdlijn", "json"))):
        staat["bestanden"][f"nieuw-b{i}"] = {"pad": f"{kaart_b}/100005 {soort} b{i}.{ext}", "grootte": 10, "hash": "h",
                                             "start": "2026-10-29T09:00:05Z", "ts": "2026-10-29T10:20:00+00:00"}
    staat["voorstellen"] = {ZA._gemist_sleutel(f, v): {"fid": f, "ts": v["sinds"]} for f, v in staat["verdwenen"].items()}
    staat["voorstellen"]["terug1234"] = {"fid": "kwam-terug", "ts": "2026-10-27T13:06:00+00:00"}
    ZA.schrijf_staat(staat)
    return json.loads(json.dumps(staat))


def test_t0120_arch1_oude_gevallen_vervallen_met_bewijs_en_niets_uit_de_staat():
    """ARCH-1 en VOL-20: de 21 oude gevallen bewaarden geen meeting of soort. Met de eenmalige vlag --vervallen-markeren
    vervalt een oud geval alleen met het bewijs uit de meting (bestand in verwerking gezien, een map met precies video,
    tijdlijn en transcript met dezelfde starttijd tot op de seconde, bewezen in de ronde waarin het verdween). Het gaat
    met dat bewijs naar 'vervallen': niets gaat uit staat.json. Elk ander geval blijft verdwenen, voor Mehdi. --droog
    toont alleen. Het bord raakt de vlag niet: ze noemt de voorstellen die mogen vervallen."""
    opzet()
    voor = _oude_staat()
    uit = io.StringIO()
    with contextlib.redirect_stdout(uit):
        assert ZA.main(["--vervallen-markeren", "--droog"]) == 0
    assert ZA.lees_staat() == voor, "--droog schrijft niets"
    assert "1 oud geval vervalt" in uit.getvalue(), uit.getvalue()
    uit = io.StringIO()
    with contextlib.redirect_stdout(uit):
        assert ZA.main(["--vervallen-markeren"]) == 0
    staat = ZA.lees_staat()
    assert set(staat["verdwenen"]) == {"oud-b", "meeting:oud-c"} and set(staat["vervallen"]) == {"oud-a"}, staat["vervallen"]
    a = staat["vervallen"]["oud-a"]
    assert {k: a[k] for k in voor["verdwenen"]["oud-a"]} == voor["verdwenen"]["oud-a"], "het oude geval blijft heel"
    assert sorted(a["bewijs"]["bewezen"]) == ["nieuw-a0", "nieuw-a1", "nieuw-a2"] and a["bewijs"]["soorten"] == ["json", "mp4", "vtt"]
    assert a["reden"].startswith("oud geval"), a
    assert staat["bestanden"] == voor["bestanden"] and staat["voorstellen"] == voor["voorstellen"], "niets anders veranderd"
    tekst = uit.getvalue()
    sleutel = ZA._gemist_sleutel("oud-a", voor["verdwenen"]["oud-a"])
    assert f"{ZA.GEMIST_ACTIE} ({sleutel})" in tekst and f"{ZA.GEMIST_ACTIE} (terug1234)" in tekst, tekst
    assert f"{ZA.GEMIST_ACTIE} ({ZA._gemist_sleutel('oud-b', voor['verdwenen']['oud-b'])})" not in tekst, tekst
    assert "Proefgesprek" not in tekst and "/Zoom/" not in tekst, "geen onderwerp of pad op het scherm"
    with contextlib.redirect_stdout(io.StringIO()):
        assert ZA.main(["--vervallen-markeren"]) == 0
    assert ZA.lees_staat() == staat, "een tweede keer verandert niets"


def test_t0120_arch3_alleen_de_echte_keten_telt():
    """ARCH-3 (meting 01-11-2026): op 30-10 09:06 stopte een ronde met "de gesprekkenketen begint" terwijl er geen keten
    liep. pgrep -f 'mijnagents-runner/keten.py' vond elk proces met die tekst in zijn opdrachtregel, ook een lezer van
    dat bestand. Nu telt alleen een python die precies dat keten.py draait (verankerd); een ander proces met het pad
    in zijn opdrachtregel niet. Met echte processen en de echte pgrep."""
    import subprocess
    import time as _tijd
    map_ = tempfile.mkdtemp(prefix="keten-", dir=MAP)
    keten = os.path.join(map_, "appportal", "mijnagents-runner", "keten.py")
    os.makedirs(os.path.dirname(keten))
    with open(keten, "w", encoding="utf-8") as f:
        f.write("import time\ntime.sleep(30)\n")
    oud = ZA.KETEN_PY
    ZA.KETEN_PY = keten
    lezer = echt = None
    try:
        assert re.fullmatch(r"\^.*\( \|\$\)", ZA.keten_patroon()), ZA.keten_patroon()
        lezer = subprocess.Popen(["/bin/sh", "-c", "sleep 30; :", keten])           # zoals cat of less op keten.py
        _tijd.sleep(0.5)
        assert ECHTE_KETEN_DRAAIT() is False, "een lezer van keten.py is geen keten"
        echt = subprocess.Popen([sys.executable, keten, "--nacht"])
        _tijd.sleep(0.5)
        assert ECHTE_KETEN_DRAAIT() is True, "de echte keten telt"
    finally:
        ZA.KETEN_PY = oud
        for p in (lezer, echt):
            if p:
                p.kill()
                p.wait()


def test_t0120_arch5_een_later_bestand_krijgt_een_tweede_beschrijving():
    """ARCH-5 (Codex, meting 01-11-2026): opname.json kwam er een keer per meeting; kreeg een gesprek later nog een
    bestand, dan stond dat in geen enkele beschrijving. Nu krijgt een meeting met een nieuw bewezen bestand een tweede
    beschrijving naast de eerste (opname-2.json) met alle bestanden; de eerste blijft staan, nooit overschreven. Een
    beschrijving van voor deze regel krijgt een basis uit wat er nu bewezen is, zonder nieuwe beschrijving."""
    z, d, _ = opzet()
    start = "2026-10-28T09:00:00Z"
    m = z.meeting("u1", start, bestanden=DRIE)
    ronde()
    kaart = ZA.mapnaam(m)
    eerste = d.bestanden[kaart + "/opname.json"]
    assert len(json.loads(eerste)["bestanden"]) == 3
    staat = ZA.lees_staat()
    del staat["beschreven"]["u1"]                     # zoals een staat van voor ARCH-5
    ZA.schrijf_staat(staat)
    ronde(nu=NU + timedelta(hours=1))
    assert sorted(ZA.lees_staat()["beschreven"]["u1"]["ids"]) == sorted(f["id"] for f in m["bestanden"])
    assert kaart + "/opname-2.json" not in d.bestanden, "een oude beschrijving krijgt alleen een basis"
    z.inhoud["u1-later"] = b"chat"
    z.meetings["u1"]["bestanden"].append({"id": "u1-later", "soort": "CHAT", "status": "completed", "start": start,
                                          "einde": start, "grootte": 4, "opnametype": "chat_file", "extensie": "CHAT",
                                          "link": True})
    r, uit = ronde(nu=NU + timedelta(hours=2))
    assert uit["gedaan"] == 1 and d.bestanden[kaart + "/opname.json"] == eerste, "de eerste blijft staan"
    tweede = json.loads(d.bestanden[kaart + "/opname-2.json"])
    assert len(tweede["bestanden"]) == 4 and tweede["versie"] == 2 and tweede["eerder"] == ["opname.json"], tweede
    assert "download_url" not in json.dumps(tweede) and ZA.lees_staat()["beschreven"]["u1"]["versie"] == 2
    ronde(nu=NU + timedelta(hours=3))
    assert kaart + "/opname-3.json" not in d.bestanden, "zonder nieuw bestand geen derde beschrijving"


def test_t0120_arch2_overzicht_per_dag_voor_de_wachtenpagina_zonder_onderwerp():
    """ARCH-2 (meting 01-11-2026): op /wachten/zoom-archief stond elke dag "draaide, niets binnen", terwijl De
    Zoomarchivaris elke dag bestanden kopieert. Elke ronde schrijft ze nu naast de staat een overzicht per Brusselse dag
    van de kopie (wachten.json; het bord leest het alleen lezend op /data/zoom-archief): per gekopieerd bestand het uur
    van het gesprek, de soort, de MB en de map Zoom/<datum uur> in Mehdi's Dropbox; verdwenen gevallen apart, zonder
    id. Nooit een onderwerp, uuid, bestandsid, pad, hash of link: de weergave en de route achter Authentik doet de
    pagina."""
    z, _, _ = opzet()
    z.meeting("u1", "2026-10-27T08:05:00Z", onderwerp=GEHEIM_ONDERWERP, bestanden=DRIE[:2])
    b = _in_verwerking(z, "weg", "2026-10-27T11:00:00Z")
    ronde()
    del z.meetings["weg"]
    ronde(nu=NU + timedelta(hours=1))
    pad = os.path.join(ZA.DATA, "wachten.json")
    tekst = open(pad, encoding="utf-8").read()
    o = json.loads(tekst)
    kopie = {ZA.brussel(b_["ts"]).date().isoformat() for b_ in ZA.lees_staat()["bestanden"].values()}
    assert len(kopie) == 1, kopie       # de dag van de kopie (de klok van de kopie, niet die van de proef)
    dag = o["dagen"][kopie.pop()]
    assert len(dag["gekopieerd"]) == 2, dag
    assert {f["soort"] for f in dag["gekopieerd"]} == {"scherm en spreker", "tijdlijn"}, dag["gekopieerd"]
    assert all(f["uur"] == "09:05" and f["map"] == "Zoom/2026-10-27 0905" and f["mb"] >= 0 for f in dag["gekopieerd"]), dag
    weg = o["dagen"][(NU + timedelta(hours=1)).astimezone(ZA.BRUSSEL).date().isoformat()]
    assert weg["verdwenen"] == [{"uur": "12:00", "mb": 0.0}], weg
    for verboden in ("Proefgesprek", "Zeta", "u1", b, "weg", "hash", "/Zoom/", "http", ZA.kort("u1")):
        assert verboden not in tekst, verboden
    with open(pad, encoding="utf-8") as f:
        assert json.load(f)["ts"], "het overzicht zegt wanneer het geschreven is"
    voor = open(pad, encoding="utf-8").read()
    ronde(droog=True, nu=NU + timedelta(hours=2))
    assert open(pad, encoding="utf-8").read() == voor, "een droge ronde schrijft geen overzicht"


if __name__ == "__main__":
    goed = fout = 0
    for naam, f in sorted(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                f()
                goed += 1
                print(f"   geslaagd  {naam}")
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"   GEFAALD   {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)

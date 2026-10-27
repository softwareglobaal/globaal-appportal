"""Grendels op De Zoomarchivaris (zoom_archief.py), de lijst K7 uit het driehoeksoverleg Zoomarchief (27-10-2026).

Geen netwerk en geen sleutels. Nagebootst: de opnamelijst en de download van Zoom (zoom.opnames, zoom.download_naar;
hun grendels L1 en L5 toetst test_zoom_archief_bouwstenen.py), de Dropbox-API op het laagste niveau
(dropbox_prive._verzoek, met mode add zoals Dropbox het doet: de echte upload_bestand en metadata draaien), de ronde
van het bord en de klok.
Draaien: python3 mijnagents-runner/tests/test_zoom_archief.py
"""
import contextlib
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

# na de import: de bouwstenentest wist bij het laden elke DROPBOX_-sleutel
os.environ.update(DROPBOX_PRIVE_APP_KEY="k", DROPBOX_PRIVE_APP_SECRET="g", DROPBOX_PRIVE_REFRESH_TOKEN="t")

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
        self.meetings, self.prullenbak, self.inhoud, self.gevraagd, self.downloads = {}, {}, {}, [], []
        self.fout = {}

    def meeting(self, uuid, start, onderwerp="Overleg", bestanden=(), prullenbak=False):
        m = {"uuid": uuid, "nummer": "9100000001", "onderwerp": onderwerp, "start": start, "duur": 30, "bestanden": []}
        for i, (soort, opnametype, data) in enumerate(bestanden):
            fid = f"{uuid}-f{i}"
            self.inhoud[fid] = data
            m["bestanden"].append({"id": fid, "soort": soort, "status": "completed", "start": start, "einde": start,
                                   "grootte": len(data), "opnametype": opnametype, "extensie": soort})
        (self.prullenbak if prullenbak else self.meetings)[uuid] = m
        return m

    def opnames(self, van, tot, profiel="lees", prullenbak=False):
        self.gevraagd.append((van, tot, prullenbak))
        bron = self.prullenbak if prullenbak else self.meetings
        return [json.loads(json.dumps(m)) for m in bron.values() if van <= m["start"][:10] <= tot]

    def download_naar(self, fid, doel, profiel="lees", brok=1 << 20):
        self.downloads.append(fid)
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
    return z, d, logs


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
    weg = z.meeting("weg", "2026-09-01T09:00:00Z", bestanden=[("M4A", "audio_only", b"p")], prullenbak=True)
    bezig = z.meeting("bezig", "2026-10-26T09:00:00Z", bestanden=[("MP4", "speaker_view", b"b")])
    bezig["bestanden"][0]["status"] = "processing"
    _, uit = ronde()
    assert z.downloads == [weg["bestanden"][0]["id"], oud["bestanden"][0]["id"], nieuw["bestanden"][0]["id"]], z.downloads
    assert any(g[2] for g in z.gevraagd), "de prullenbak is gelezen"
    assert uit["klaar"] == 3, "een opname die Zoom nog verwerkt, telt niet en wordt niet gekopieerd"
    assert bezig["uuid"] not in ZA.lees_staat()["meetings"], "geen opname.json zolang niet alles klaar is"


def test_k7_vensters_van_30_dagen_tot_de_eerste_dag_en_daarna_kort():
    z, _, _ = opzet()
    _, uit = ronde()
    vensters = sorted({(v, t) for v, t, _ in z.gevraagd})
    assert vensters[0][0] == ZA.EERSTE_DAG.isoformat() and uit["volledig"], "de eerste ronde leest alles"
    for v, t in vensters:
        dagen = (datetime.fromisoformat(t) - datetime.fromisoformat(v)).days
        assert 0 < dagen <= ZA.VENSTER, (v, t)
    z.gevraagd.clear()
    _, uit = ronde()
    assert not uit["volledig"] and min(v for v, _, _ in z.gevraagd) >= (NU.date() - timedelta(days=ZA.KORT)).isoformat()
    _, uit = ronde(nu=NU + timedelta(days=1))
    assert uit["volledig"], "een nieuwe dag leest weer alles"


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
    tikken = iter([0, 10, 5000, 5000, 5000])  # het begin, dan voor elk bestand
    _, uit = ronde(budget=100, klok=lambda: next(tikken))
    assert uit["gedaan"] == 1 and uit["gestopt"] == "tijdsbudget op", uit
    _, uit = ronde(nu=datetime(2026, 10, 27, 12, 55, tzinfo=timezone.utc))
    assert uit["gedaan"] == 0 and uit["gestopt"] == "de gesprekkenketen begint", uit
    assert ZA.tot_keten(datetime(2026, 10, 27, 23, 25, tzinfo=timezone.utc)) == 300
    assert ZA.tot_keten(datetime(2026, 10, 27, 23, 31, tzinfo=timezone.utc)) == 7 * 3600 + 29 * 60, "na 23:30 de keten van 07:00"
    opzet(keten=True)
    r, uit = ronde()
    assert uit is None and r.noden_onbekend and "overgeslagen" in r.detail, "tijdens de keten niets, en geen noden sluiten"


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
    os.makedirs(os.path.dirname(os.path.expanduser(ZA_ACC.ARCHIEF_DEKKING)), exist_ok=True)
    pad = os.path.expanduser(ZA_ACC.ARCHIEF_DEKKING)
    if os.path.exists(pad):
        os.remove(pad)
    d = {"account": {"recording.auto_delete_cmr": False}, "opslag": {"pct": 98, "vol_dagen": 1, "vol_rond": "2026-10-28"},
         "opslagtrend": {"x": 1}}
    try:
        za01 = next(a for a in ZA_ACC.adviezen(d) if a["code"] == "ZA-01")
    except Exception:  # noqa: BLE001  de rest van de invoer is hier niet nodig; dan rechtstreeks de tekst toetsen
        za01 = None
    if za01 is not None and za01["toestand"] == "open":
        assert za01["doel"].startswith("Wacht met de wisregel") and "onbekend of alle opnames" in za01["reden"], za01
        json.dump({"ts": datetime.now(timezone.utc).isoformat(), "dekking": True}, open(pad, "w"))
        za01 = next(a for a in ZA_ACC.adviezen(d) if a["code"] == "ZA-01")
        assert za01["doel"].startswith("Zet een wisregel van 30 dagen aan") and "bewezen in je Dropbox" in za01["reden"]
        assert za01["stand"] == {"wisregel": False, "band": 100 if d["opslag"]["pct"] >= 100 else 90}, "de stand blijft gelijk"
    else:
        raise AssertionError(f"ZA-01 niet open met deze invoer: {za01}")


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

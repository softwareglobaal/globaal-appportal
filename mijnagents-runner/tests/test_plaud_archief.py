"""Grendels op het Plaud-archief op de Mac (verbeteropdracht v1.0, 12-10-2026, §2, §5, §6, §8, §9).

De review vond: botsende namen die als compleet telden, half geschreven mappen, een transcript dat
nooit opnieuw gevraagd werd, links naar file: en interne adressen die gewoon gelezen werden, een
oude momentopname die verse metadata verving, en foutcode 0 na een mislukte ronde.

Synthetisch archief in een tijdelijke map, nagebootste downloads en adresoplossing; geen netwerk.
Draait ook onder /usr/bin/python3 (3.9), zoals de ophaler op de Mac.
Draaien: python3 mijnagents-runner/tests/test_plaud_archief.py
"""
import gzip
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HIER, "plaud"))
import archief  # noqa: E402
import bouw_map  # noqa: E402
import contract  # noqa: E402
import lijst  # noqa: E402
import manifest  # noqa: E402
import mapnaam  # noqa: E402
import plaud_haal_alles as H  # noqa: E402
import veilig  # noqa: E402

lijst.OUDE_REPO_LIJST = Path("/nonexistent/plaud_lijst.json")     # nooit de echte lijst in een proef
ID1 = "of_" + "a" * 32
ID2 = "of_" + "b" * 32
AUDIO = b"OggS" + b"\x00" * 3000
UITINGEN = [{"start_time": 0, "end_time": 4000, "speaker": "Speaker 1", "content": "Werfbezoek 2531 Spleesters met de aannemer."},
            {"start_time": 5000, "end_time": 9000, "speaker": "Speaker 2", "content": "We lopen de ruwbouw na."}]


def doel():
    return Path(tempfile.mkdtemp(prefix="plaud-proef-"))


class Haler:
    """Nagebootste download: transcript (gz-JSON) en audio, of een fout, per link."""

    def __init__(self, fout_op=()):
        self.gelezen = []
        self.fout_op = set(fout_op)

    def __call__(self, url, max_bytes, timeout):
        self.gelezen.append(url)
        if url in self.fout_op:
            raise veilig.DownloadFout("HTTP 403 bij proef (link verlopen)")
        if "transcript" in url:
            return gzip.compress(json.dumps(UITINGEN).encode())
        return AUDIO


def op(pid=ID1, naam="09-17 Werfbezoek Spleesters", start="2026-09-17T08:02:00", link=True, audio=True):
    o = {"id": pid, "name": naam, "start_at": start, "duration": 600000, "serial_number": "8810B30227294257"}
    if link:
        o["transcript_link"] = "https://proef/transcript/" + pid
    if audio:
        o["presigned_url"] = "https://proef/audio/" + pid
    return o


# ------------------------------------------------------------------ contract ---
def test_contract_tijd_id_en_gedeeld_account():
    c = contract.opname({"id": "A" * 32, "start_at": "2026-09-17T08:02:00", "name": "x", "account": "mehdi", "serial_number": "SN1"})
    assert c["plaud_id"] == "of_" + "a" * 32
    assert c["start_utc"] == "2026-09-17T08:02:00Z" and c["start_brussel"].startswith("2026-09-17T10:02:00+02:00"), c
    assert c["account"] == "onbekend" and c["opgenomen_door"] == "onbekend" and c["toestel"] == "SN1"
    for zonder in ({"id": ID1}, {"id": ID1, "client_modified": "2026-10-12T09:00:00Z"}):
        try:
            contract.opname(zonder)
            raise AssertionError("zonder opnametijd moet herstel volgen, nooit client_modified")
        except contract.Herstel:
            pass
    try:
        contract.opname({"id": ID1, "start": "geen tijd"})
        raise AssertionError("ongeldige tijd")
    except contract.Herstel:
        pass
    c = contract.opname({"id": ID1, "start": "2026-10-06T14:30"})        # oude kop: Brussel
    assert c["start_utc"] == "2026-10-06T12:30:00Z"


# ------------------------------------------------------- resolver en bouwer ---
def test_twee_opnames_zelfde_minuut_en_titel_krijgen_elk_een_map():
    d = doel()
    h = Haler()
    r1 = bouw_map.bouw(op(ID1), d, haler=h)
    r2 = bouw_map.bouw(op(ID2), d, haler=h)
    assert r1["status"] == r2["status"] == "compleet", (r1, r2)
    assert r1["map"] != r2["map"] and "[bbbbbb]" in r2["map"], (r1["map"], r2["map"])
    assert archief.toestand(r1["map"], ID1)["staat"] == "compleet"
    assert archief.toestand(r1["map"], ID2)["staat"] == "vreemd", "een map van een ander id is nooit compleet voor dit id"
    assert mapnaam.compleet({"plaud_id": ID2, "start_utc": "2026-09-17T08:02:00Z", "naam_in_plaud": "x"}, d)
    # tweede ronde: niets nieuw, geen derde map
    bouw_map.bouw(op(ID1), d, haler=h)
    assert len(list(d.glob("*/gesprek.json"))) == 2
    shutil.rmtree(d)


def test_afgekapte_gelijke_titels_botsen_niet():
    d = doel()
    lang = "09-17 " + "Vergadering over de stabiliteit van de draagmuren en de funderingen " * 3
    r1 = bouw_map.bouw(op(ID1, naam=lang + "deel een"), d, haler=Haler())
    r2 = bouw_map.bouw(op(ID2, naam=lang + "deel twee"), d, haler=Haler())
    assert r1["map"] != r2["map"] and len(Path(r2["map"]).name) <= mapnaam.MAX, r2["map"]
    assert r1["status"] == r2["status"] == "compleet"
    shutil.rmtree(d)


def test_hernoemde_onvolledige_map_wordt_hersteld_op_id():
    d = doel()
    r = bouw_map.bouw(op(ID1), d, haler=Haler())
    nieuw = d / "2026-09-17 1002 HARC 2531 - aannemer - ruwbouw"
    os.rename(r["map"], nieuw)
    os.remove(nieuw / "opname.ogg")
    assert archief.toestand(nieuw, ID1)["staat"] == "onvolledig"
    r2 = bouw_map.bouw(op(ID1), d, haler=Haler())
    assert Path(r2["map"]) == nieuw and r2["status"] == "compleet", r2
    assert len(list(d.glob("*/gesprek.json"))) == 1, "geen tweede map naast de hernoemde"
    shutil.rmtree(d)


def test_fout_na_json_voor_markdown_is_onvolledig_en_herstelt_zonder_download():
    d = doel()
    r = bouw_map.bouw(op(ID1), d, haler=Haler())
    os.remove(Path(r["map"]) / "transcript.md")
    st = archief.toestand(r["map"], ID1)
    assert st["staat"] == "onvolledig" and any("transcript.md" in x for x in st["redenen"]), st
    h = Haler()
    r2 = bouw_map.bouw(op(ID1, link=False, audio=False), d, haler=h)
    assert r2["status"] == "compleet" and not h.gelezen, (r2, h.gelezen)
    shutil.rmtree(d)


def test_deel_bestand_en_half_transcript_zijn_niet_compleet():
    d = doel()
    r = bouw_map.bouw(op(ID1), d, haler=Haler())
    m = Path(r["map"])
    os.rename(m / "opname.ogg", m / "opname.ogg.deel")
    st = archief.toestand(m, ID1)
    assert st["staat"] == "onvolledig" and st["audio"] == "ontbreekt", st
    os.rename(m / "opname.ogg.deel", m / "opname.ogg")
    (m / "transcript.json").write_text('[{"start_time": 0, "cont', encoding="utf-8")
    assert archief.toestand(m, ID1)["staat"] == "onvolledig"
    shutil.rmtree(d)


def test_wachtend_transcript_wordt_later_opnieuw_gevraagd():
    d = doel()
    r = bouw_map.bouw(op(ID1, link=False), d, haler=Haler())
    assert r["status"] == "wacht_op_transcript" and not r["fouten"], r
    t = archief.lees_json(Path(r["map"]) / "gesprek.json")["transcript"]
    assert t["staat"] == "wacht" and t["pogingen"] == 1 and t["volgende_controle"] > t["laatste_controle"], t
    idx = archief.Index(d)
    nu = datetime.now(timezone.utc)
    doen, tel = H.te_doen([op(ID1)], idx, nu)
    assert not doen and tel["wacht_nog_niet_aan_de_beurt"] == 1, tel
    doen, tel = H.te_doen([op(ID1)], idx, nu + timedelta(hours=2))
    assert len(doen) == 1, "na de backoff opnieuw vragen"
    r2 = bouw_map.bouw(op(ID1), d, haler=Haler())
    assert r2["status"] == "compleet", r2
    shutil.rmtree(d)


def test_verlopen_audiolink_en_daarna_een_nieuwe():
    d = doel()
    r = bouw_map.bouw(op(ID1), d, haler=Haler(fout_op={"https://proef/audio/" + ID1}))
    assert r["status"] == "onvolledig" and any("audio" in f for f in r["fouten"]), r
    doen, _ = H.te_doen([op(ID1)], archief.Index(d), datetime.now(timezone.utc))
    assert len(doen) == 1
    r2 = bouw_map.bouw(op(ID1), d, haler=Haler())
    assert r2["status"] == "compleet" and r2["map"] == r["map"], r2
    shutil.rmtree(d)


def test_een_id_op_twee_plaatsen_is_een_conflict_geen_keuze():
    d = doel()
    r = bouw_map.bouw(op(ID1), d, haler=Haler())
    shutil.copytree(r["map"], str(d / "kopie elders"))
    try:
        archief.resolve({"plaud_id": ID1, "start_utc": "2026-09-17T08:02:00Z"}, d)
        raise AssertionError("id-conflict moet herstel geven")
    except contract.Herstel:
        pass
    m = manifest.bouw(d)
    assert ID1 in m["conflicten"] and m["aantal"] == 1, m
    shutil.rmtree(d)


# ------------------------------------------------------------------- veilig ---
def publiek(host, poort, proto=None):
    return [(2, 1, 6, "", ("52.216.1.1", 443))]


def intern(host, poort, proto=None):
    return [(2, 1, 6, "", ("10.0.0.5", 443))]


GOED = "https://prod-plaud-content-storage.s3.amazonaws.com/audiofiles/x.ogg?X-Amz-Signature=proef"


def test_onveilige_links_worden_nooit_gelezen():
    gelezen = []

    def verzoek(url, doelbestand, max_bytes, timeout):
        gelezen.append(url)
        return 200, ""
    for url, oplosser in (("file:///etc/passwd", publiek), ("http://prod-plaud-content-storage.s3.amazonaws.com/x", publiek),
                          ("https://127.0.0.1/x", publiek), ("https://169.254.169.254/latest/meta-data", publiek),
                          ("https://user:pw@prod-plaud-content-storage.s3.amazonaws.com/x", publiek),
                          ("https://prod-plaud-content-storage.s3.amazonaws.com:8443/x", publiek),
                          (GOED, intern)):
        try:
            veilig.haal(url, 1000, 5, oplosser=oplosser, verzoek=verzoek)
            raise AssertionError("niet geweigerd: " + url)
        except veilig.OnveiligeLink:
            pass
    assert not gelezen, gelezen


def test_omleiding_naar_intern_adres_wordt_geweigerd():
    gelezen = []

    def verzoek(url, doelbestand, max_bytes, timeout):
        gelezen.append(url)
        return 302, "https://169.254.169.254/latest/meta-data"
    try:
        veilig.haal(GOED, 1000, 5, oplosser=publiek, verzoek=verzoek)
        raise AssertionError("omleiding naar intern adres niet geweigerd")
    except veilig.OnveiligeLink:
        pass
    assert gelezen == [GOED], gelezen


def test_toegestane_synthetische_link_slaagt_en_logt_geen_link():
    def verzoek(url, doelbestand, max_bytes, timeout):
        with open(doelbestand, "wb") as f:
            f.write(AUDIO)
        return 200, ""
    assert veilig.haal(GOED, 10000, 5, oplosser=publiek, verzoek=verzoek) == AUDIO
    assert veilig.audio_soort(AUDIO) == ".ogg" and veilig.audio_soort(b"<html>") is None
    assert "Signature" not in veilig.host_van(GOED)


# ------------------------------------------------------------------- lijst ---
def test_momentopname_vervangt_geen_verse_metadata():
    d = doel()
    lijst.schrijf(d, [{"id": ID1, "name": "oud", "start_at": "2026-09-17T08:02:00"}], bron="proef", volledig=True)
    lijst.schrijf(d, [{"id": ID1, "name": "vers"}, {"id": ID2, "name": "nieuw", "start_at": "2026-09-18T08:00:00"}],
                  bron="koppeling", volledig=False)
    per = lijst.per_id(d)
    assert per[ID1]["name"] == "vers" and per[ID1]["start_at"] == "2026-09-17T08:02:00" and ID2 in per, per
    aan = lijst.aanvul({"id": ID1, "name": "nog verser"}, d)
    assert aan["name"] == "nog verser" and aan["start_at"] == "2026-09-17T08:02:00", aan
    lijst.schrijf(d, [{"id": ID2, "name": "nieuw"}], bron="plaud-api", volledig=True)
    assert set(lijst.per_id(d)) == {ID2}, "een volledige ophaling vervangt de lijst"
    shutil.rmtree(d)


# ------------------------------------------------------- ophaler: foutcodes ---
def test_ophaler_geeft_nooit_nul_na_een_fout():
    d = doel()
    oud_doel, oud_bewijs = H.DOEL, H.BEWIJS
    H.DOEL, H.BEWIJS = d, d / "geen-token.json"

    class A:
        max = 0
        lijst = False
    try:
        assert H.ronde(A) == H.AUTH
        st = archief.lees_json(d / "00 status.json")
        assert st["uitkomst"] == "authfout" and st["laatste_ok"] is None, st
        # aanmelding goed, een van twee opnames faalt: DEELS, niet OK
        H.toegang = lambda: {"access_token": "proef"}
        H.lijst_alles = lambda b: [op(ID1), op(ID2, start="2026-09-18T08:00:00")]

        def api(pad, b):
            if pad.endswith(ID2):
                raise RuntimeError("proeffout bij de tweede opname")
            return {"presigned_url": "https://proef/audio/" + ID1,
                    "source_list": [{"data_type": "transaction", "data_link": "https://proef/transcript/" + ID1}]}
        H.api = api
        oud_bouw = bouw_map.bouw
        bouw_map.bouw = lambda invoer, doel_, idx: oud_bouw(invoer, doel_, idx, haler=Haler())
        try:
            assert H.ronde(A) == H.DEELS
        finally:
            bouw_map.bouw = oud_bouw
        st = archief.lees_json(d / "00 status.json")
        assert st["uitkomst"] == "deels" and st["tellers"]["gebouwd"] == 1 and st["tellers"]["mislukt"] == 1, st
        tekst = json.dumps(st) + (d / "00 plaud_lijst.json").read_text()
        assert "proef/audio" not in json.dumps(st), "geen links in de status"
    finally:
        H.DOEL, H.BEWIJS = oud_doel, oud_bewijs
    shutil.rmtree(d)


def test_manifest_toont_echte_toestand_zonder_links():
    d = doel()
    bouw_map.bouw(op(ID1), d, haler=Haler())
    bouw_map.bouw(op(ID2, link=False, start="2026-09-18T08:00:00"), d, haler=Haler())
    m = manifest.bouw(d)
    assert m["toestanden"] == {"compleet": 1, "wacht_op_transcript": 1}, m
    data = manifest.lees(d)
    tekst = json.dumps(data)
    assert "proef/audio" not in tekst and "proef/transcript" not in tekst and "presigned" not in tekst
    per = {o["plaud_id"]: o for o in data["opnames"]}
    assert per[ID1]["transcript"]["staat"] == "aanwezig" and per[ID2]["transcript"]["staat"] == "wacht"
    assert per[ID1]["toestel"] == "8810B30227294257" and per[ID1]["opgenomen_door"] == "onbekend"
    shutil.rmtree(d)


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

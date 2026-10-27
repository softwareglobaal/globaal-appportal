"""Grendels op de bouwstenen van De Zoomarchivaris: de download in brokken uit Zoom (zoom.download_naar) en de upload
van grote bestanden naar Mehdi's eigen Dropbox (dropbox_prive.upload_bestand, inhoud_hash, metadata).

Geen netwerk en geen sleutels. Nagebootst: de opener van zoom.py op het laagste niveau en dropbox_prive._verzoek.
Draaien: python3 mijnagents-runner/tests/test_zoom_archief_bouwstenen.py
"""
import hashlib
import io
import json
import os
import sys
import tempfile
import traceback
import urllib.error
from email.message import Message

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
MAP = tempfile.mkdtemp(prefix="zoom-archief-bouw-")
os.environ["HOME"] = os.path.join(MAP, "thuis")
os.makedirs(os.environ["HOME"], exist_ok=True)
for _k in [k for k in os.environ if k.startswith(("ZOOM_", "DROPBOX_"))]:
    del os.environ[_k]
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import dropbox_prive as D  # noqa: E402
import zoom as Z  # noqa: E402

ECHT_VERZOEK = D._verzoek  # de proeven hieronder vervangen het; de HTTP-proeven gebruiken het echte

MB = 1024 * 1024


def _fout(url, code, body=b"", location=""):
    koppen = Message()
    if location:
        koppen["Location"] = location
    return urllib.error.HTTPError(url, code, "proef", koppen, io.BytesIO(body))


class _Antwoord(io.BytesIO):
    status = 200

    def __init__(self, inhoud=b"", lengte=None):
        super().__init__(inhoud)
        self.headers = Message()
        self.headers["Content-Length"] = str(len(inhoud) if lengte is None else lengte)


class _Opener:
    """De opener van zoom.py: per url een antwoord, een omleiding of een fout; onthoudt de koppen per vraag."""

    def __init__(self, routes):
        self.routes, self.gevraagd = routes, []

    def open(self, req, timeout=None):
        self.gevraagd.append((req.full_url, dict(req.header_items())))
        r = self.routes[req.full_url]
        if isinstance(r, Exception):
            raise r
        return _Antwoord(r)


def _zoom(routes, bestanden=None):
    Z._DOWNLOADS.clear()
    Z._DOWNLOADS.update(bestanden or {"b1": "https://proef.zoom.us/rec/download/b1"})
    Z._token_voor = lambda profiel: "tok"
    o = _Opener(routes)
    Z._OPENER = o
    return o


def test_download_naar_schrijft_in_brokken_en_volgt_een_omleiding_zonder_token():
    inhoud = os.urandom(3 * MB + 17)
    eerste, tweede = "https://proef.zoom.us/rec/download/b1", "https://ssrweb.zoom.us/x/b1.mp4"
    o = _zoom({eerste: _fout(eerste, 302, location=tweede), tweede: inhoud})
    doel = os.path.join(MAP, "b1.mp4")
    assert Z.download_naar("b1", doel, brok=MB) == len(inhoud)
    assert open(doel, "rb").read() == inhoud
    assert o.gevraagd[0][1].get("Authorization") == "Bearer tok", "L1: de eerste sprong met het token"
    assert "Authorization" not in o.gevraagd[1][1], "L1: na de omleiding geen token meer"


def test_download_naar_weigert_een_vreemde_host_en_een_bestand_buiten_de_lijst():
    eerste = "https://proef.zoom.us/rec/download/b1"
    _zoom({eerste: _fout(eerste, 302, location="https://elders.test/b1.mp4")})
    for bid in ("b1", "b2"):
        try:
            Z.download_naar(bid, os.path.join(MAP, "x"))
            raise AssertionError("had geweigerd moeten worden")
        except Z.Geweigerd:
            pass


def test_download_naar_geen_recht_en_fout_zonder_url():
    eerste = "https://proef.zoom.us/rec/download/b1"
    _zoom({eerste: _fout(eerste, 403, json.dumps({"code": 4711, "message": "does not contain scopes:[a:b:admin]"}).encode())})
    try:
        Z.download_naar("b1", os.path.join(MAP, "x"))
        raise AssertionError("GeenRecht verwacht")
    except Z.GeenRecht as e:
        assert e.scope == "a:b:admin" and e.http == 403
    _zoom({eerste: _fout(eerste, 500)})
    try:
        Z.download_naar("b1", os.path.join(MAP, "x"))
        raise AssertionError("ZoomFout verwacht")
    except Z.ZoomFout as e:
        assert "zoom.us" not in str(e) and "HTTP 500" in str(e)


def test_inhoud_hash_is_die_van_dropbox():
    pad = os.path.join(MAP, "h.bin")
    data = os.urandom(9 * MB + 5)
    open(pad, "wb").write(data)
    verwacht = hashlib.sha256(b"".join(hashlib.sha256(data[i:i + 4 * MB]).digest()
                                       for i in range(0, len(data), 4 * MB))).hexdigest()
    assert D.inhoud_hash(pad) == verwacht
    open(pad, "wb").close()
    assert D.inhoud_hash(pad) == hashlib.sha256(b"").hexdigest(), "een leeg bestand"


class _Dropbox:
    """dropbox_prive._verzoek: een upload-sessie of een enkele upload, met mode add zoals Dropbox het doet."""

    def __init__(self):
        self.bestanden, self.sessies, self.calls = {}, {}, []
        self.mappen, self.account = {"/Fathom data"}, "dbid:proef-eigen"

    def __call__(self, url, data, koppen, pogingen=5):
        pad = url.split("/2/", 1)[1]
        arg = json.loads(koppen.get("Dropbox-API-Arg") or "null") or (json.loads(data) if data and data != b"null" else {})
        self.calls.append((pad, arg, len(data or b"")))
        if pad == "files/upload_session/start":
            sid = f"s{len(self.sessies) + 1}"
            self.sessies[sid] = bytearray(data)
            return {"session_id": sid}
        if pad == "files/upload_session/append_v2":
            s = self.sessies[arg["cursor"]["session_id"]]
            assert arg["cursor"]["offset"] == len(s), "offset klopt"
            s.extend(data)
            return None
        if pad in ("files/upload", "files/upload_session/finish"):
            if pad == "files/upload":
                commit, inhoud = arg, bytes(data)
            else:
                s = self.sessies[arg["cursor"]["session_id"]]
                assert arg["cursor"]["offset"] == len(s)
                commit, inhoud = arg["commit"], bytes(s + data)
            assert commit["mode"] == "add" and commit["autorename"] is False, "nooit overschrijven"
            if commit["path"] in self.bestanden:
                raise _fout(url, 409, json.dumps({"error_summary": "path/conflict/file/.."}).encode())
            self.bestanden[commit["path"]] = inhoud
            return self._meta(commit["path"])
        if pad == "files/get_metadata":
            if arg["path"] in self.mappen:
                return {".tag": "folder", "path_display": arg["path"]}
            if arg["path"] not in self.bestanden:
                raise _fout(url, 409, json.dumps({"error_summary": "path/not_found/"}).encode())
            return self._meta(arg["path"])
        if pad == "files/list_folder":
            onder = [p for p in self.bestanden if p.lower().startswith(arg["path"].lower() + "/")]
            if not onder and arg["path"] not in self.mappen:
                raise _fout(url, 409, json.dumps({"error_summary": "path/not_found/"}).encode())
            return {"entries": [{**self._meta(p), "path_lower": p.lower()} for p in onder[:2]],
                    "has_more": len(onder) > 2, "cursor": json.dumps(onder[2:])}
        if pad == "files/list_folder/continue":
            onder = json.loads(arg["cursor"])
            return {"entries": [{**self._meta(p), "path_lower": p.lower()} for p in onder[:2]],
                    "has_more": len(onder) > 2, "cursor": json.dumps(onder[2:])}
        if pad == "users/get_current_account":
            return {"account_id": self.account, "email": "eigen@mehdi.test", "name": {"display_name": "Proef"},
                    "account_type": {".tag": "business"}, "root_info": {".tag": "user"}}
        raise AssertionError(pad)

    def _meta(self, p):
        b = self.bestanden[p]
        h = hashlib.sha256(b"".join(hashlib.sha256(b[i:i + 4 * MB]).digest() for i in range(0, len(b), 4 * MB)))
        return {".tag": "file", "size": len(b), "content_hash": h.hexdigest(), "path_display": p}


def _dropbox():
    d = _Dropbox()
    D._verzoek = d
    return d


def test_upload_bestand_groot_via_sessie_klein_in_een_keer_en_nooit_overschrijven():
    d = _dropbox()
    groot = os.path.join(MAP, "groot.bin")
    data = os.urandom(2 * D.BROK + 3 * MB)
    open(groot, "wb").write(data)
    m = D.upload_bestand(groot, "/Zoom/a/video.mp4")
    assert d.bestanden["/Zoom/a/video.mp4"] == data
    assert m == {"grootte": len(data), "content_hash": D.inhoud_hash(groot), "pad": "/Zoom/a/video.mp4"}
    soorten = [c[0] for c in d.calls]
    assert soorten == ["files/upload_session/start", "files/upload_session/append_v2", "files/upload_session/finish"], soorten
    assert all(c[2] <= D.BROK for c in d.calls), "geen stuk groter dan BROK"
    klein = os.path.join(MAP, "klein.txt")
    open(klein, "wb").write(b"WEBVTT\n")
    D.upload_bestand(klein, "/Zoom/a/transcript.vtt")
    assert d.calls[-1][0] == "files/upload"
    try:
        D.upload_bestand(klein, "/Zoom/a/transcript.vtt")
        raise AssertionError("Bestaat verwacht")
    except D.Bestaat:
        pass
    assert d.bestanden["/Zoom/a/transcript.vtt"] == b"WEBVTT\n"


def test_upload_bestand_precies_een_stuk_en_metadata():
    d = _dropbox()
    pad = os.path.join(MAP, "rand.bin")
    open(pad, "wb").write(os.urandom(D.BROK))
    D.upload_bestand(pad, "/Zoom/b/video.mp4")
    assert [c[0] for c in d.calls] == ["files/upload"], "precies BROK past in een enkele upload"
    assert D.metadata("/Zoom/b/video.mp4")["content_hash"] == D.inhoud_hash(pad)
    assert D.metadata("/Zoom/b/niets.mp4") is None


def test_download_naar_merkt_een_te_kort_antwoord():
    eerste = "https://proef.zoom.us/rec/download/b1"
    o = _zoom({})
    o.routes[eerste] = None
    o.open = lambda req, timeout=None: _Antwoord(b"x" * 50, lengte=100)
    try:
        Z.download_naar("b1", os.path.join(MAP, "kort"))
        raise AssertionError("een te kort antwoord hoort ZoomFout te geven")
    except Z.ZoomFout as e:
        assert "korter dan Content-Length" in str(e)


def test_download_naar_bewaker_breekt_af():
    eerste = "https://proef.zoom.us/rec/download/b1"
    _zoom({eerste: os.urandom(3 * MB)})
    tel = []

    def bewaker():
        tel.append(1)
        if len(tel) > 1:
            raise RuntimeError("tijd op")
    try:
        Z.download_naar("b1", os.path.join(MAP, "x"), brok=MB, bewaker=bewaker)
        raise AssertionError("de bewaker hoort af te breken")
    except RuntimeError as e:
        assert str(e) == "tijd op"


class _Http:
    """Dropbox op het niveau van urllib (de echte _verzoek draait): een upload-sessie met een lege body bij append_v2,
    zoals Dropbox het doet, en op verzoek een verloren antwoord (500 nadat het stuk wel aankwam)."""

    def __init__(self, verlies_bij=None):
        self.sessies, self.bestanden, self.verlies_bij, self.n = {}, {}, verlies_bij, 0

    def __call__(self, req, timeout=None):
        pad = req.full_url.split("/2/", 1)[1]
        arg = json.loads(req.get_header("Dropbox-api-arg") or "null") or {}
        data = req.data or b""
        self.n += 1
        if pad == "files/upload_session/start":
            self.sessies["s1"] = bytearray(data)
            return _Antwoord(json.dumps({"session_id": "s1"}).encode())
        s = self.sessies.get(arg.get("cursor", {}).get("session_id"))
        if pad in ("files/upload_session/append_v2", "files/upload_session/finish"):
            if arg["cursor"]["offset"] != len(s):
                fout = {"error_summary": "incorrect_offset/..", "error": {".tag": "incorrect_offset", "correct_offset": len(s)}}
                if pad.endswith("finish"):
                    fout["error"] = {".tag": "lookup_failed", "lookup_failed": fout["error"]}
                raise _fout(req.full_url, 409, json.dumps(fout).encode())
            s.extend(data)
            if self.verlies_bij == self.n:
                raise _fout(req.full_url, 500, b"verloren")
            if pad.endswith("append_v2"):
                return _Antwoord(b"")
            b = bytes(s)
            self.bestanden[arg["commit"]["path"]] = b
            h = hashlib.sha256(b"".join(hashlib.sha256(b[i:i + 4 * MB]).digest() for i in range(0, len(b), 4 * MB)))
            return _Antwoord(json.dumps({"size": len(b), "content_hash": h.hexdigest(),
                                         "path_display": arg["commit"]["path"]}).encode())
        raise AssertionError(pad)


def _http(**kw):
    h = _Http(**kw)
    D._verzoek = ECHT_VERZOEK
    D._toegang = lambda: "tok"
    D._path_root = lambda: {}
    D.time.sleep = lambda s: None
    D.urllib.request.urlopen = h
    return h


def test_upload_sessie_op_http_lege_body_bij_append_en_herstel_na_verloren_antwoord():
    pad = os.path.join(MAP, "sessie.bin")
    data = os.urandom(3 * D.BROK + 7)
    open(pad, "wb").write(data)
    h = _http()
    m = D.upload_bestand(pad, "/Zoom/c/video.mp4")
    assert h.bestanden["/Zoom/c/video.mp4"] == data and m["grootte"] == len(data), "lege body bij append_v2 is succes"
    h = _http(verlies_bij=2)  # het eerste append komt aan, maar het antwoord gaat verloren: 500, herhaling, 409 offset
    m = D.upload_bestand(pad, "/Zoom/d/video.mp4")
    assert h.bestanden["/Zoom/d/video.mp4"] == data, "na incorrect_offset gaat de sessie verder waar Dropbox wil"
    assert m["content_hash"] == D.inhoud_hash(pad)


def test_upload_bewaker_breekt_de_sessie_af_zonder_bestand():
    pad = os.path.join(MAP, "afbreken.bin")
    open(pad, "wb").write(os.urandom(2 * D.BROK + 1))
    h = _http()
    tel = []

    def bewaker():
        tel.append(1)
        if len(tel) > 2:
            raise RuntimeError("tijd op")
    try:
        D.upload_bestand(pad, "/Zoom/e/video.mp4", bewaker=bewaker)
        raise AssertionError("de bewaker hoort af te breken")
    except RuntimeError:
        pass
    assert not h.bestanden, "zonder finish geen bestand in Dropbox"


def test_lijst_map_leest_alle_paginas():
    d = _dropbox()
    for i in range(5):
        d.bestanden[f"/Zoom/m{i}/Video.MP4"] = bytes([i])
    lijst = D.lijst_map("/Zoom")
    assert len(lijst) == 5 and "/zoom/m3/video.mp4" in lijst, sorted(lijst)
    assert D.lijst_map("/Bestaat niet") is None



def test_opnames_streng_weigert_een_onvolledig_antwoord():
    Z._VAST["id"] = "mehdi-id"
    echt = Z.lees_alles
    try:
        for antwoord in ([{"uuid": "u", "start_time": "2026-10-20T09:00:00Z"}],):
            Z.lees_alles = lambda *a, **k: antwoord
            try:
                Z.opnames("2026-10-01", "2026-10-30", streng=True)
                raise AssertionError("een meeting zonder lijst van bestanden hoort een fout te zijn")
            except Z.ZoomFout:
                pass
            assert Z.opnames("2026-10-01", "2026-10-30")[0]["bestanden"] == [], "zonder streng zoals vroeger"
        gevraagd = []
        Z.lees_alles = lambda pad, params, sleutel, profiel="lees", streng=False: gevraagd.append(params) or []
        Z.opnames(None, None, prullenbak="recording_file", streng=True)
        assert gevraagd[-1] == {"page_size": 300, "trash": "true", "trash_type": "recording_file"}, gevraagd
    finally:
        Z.lees_alles = echt
    Z.lees = lambda pad, params=None, profiel="lees": {"total_records": 1}
    try:
        Z.lees_alles("/users/mehdi-id/recordings", {}, "meetings", streng=True)
        raise AssertionError("een pagina zonder lijst hoort een fout te zijn")
    except Z.ZoomFout:
        pass

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

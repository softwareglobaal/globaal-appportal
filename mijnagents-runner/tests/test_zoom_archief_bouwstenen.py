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

MB = 1024 * 1024


def _fout(url, code, body=b"", location=""):
    koppen = Message()
    if location:
        koppen["Location"] = location
    return urllib.error.HTTPError(url, code, "proef", koppen, io.BytesIO(body))


class _Antwoord(io.BytesIO):
    status = 200


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

    def __call__(self, url, data, koppen, pogingen=5):
        pad = url.split("/2/", 1)[1]
        arg = json.loads(koppen.get("Dropbox-API-Arg") or "null") or (json.loads(data) if data else {})
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
            if arg["path"] not in self.bestanden:
                raise _fout(url, 409, json.dumps({"error_summary": "path/not_found/"}).encode())
            return self._meta(arg["path"])
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

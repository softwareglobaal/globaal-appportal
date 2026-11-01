"""Grendel op de Fotowacht op het bord (fotowacht.py, T-0120 FOTO-4 en FOTO-5): foto-metadata en voorvertoningen.

- V01: zonder token 403 (beide routes);
- V02: een kleine JPEG van een werkfoto die de indeling van die dag toelaat, komt in <data>/fotovoorbeeld/<dag>/<id>.jpg;
- V03: een foto met mensen, een kandidaat of een onbekende foto wordt geweigerd (409), ook met een geldige JPEG;
- V04: geen JPEG, te groot, geen base64, een dag voor 01-10 of een id met een pad wordt geweigerd (400), en er komt niets
  op schijf;
- V05: de routes hangen aan het echte bord (app.py);
- V06: de foto-metadata komt als bestand (0600) in <data>/fotometadata/<dag>.json, alleen met de velden van de indeling,
  en niet in de databank van het bord; een ongeldige lijst of een fout aantal wordt geweigerd.
Verzonnen ids en plekken. Draait in de Docker-build: faalt dit, dan blijft de vorige container staan.
"""
import base64
import json
import os
import sqlite3
import sys
import tempfile

MAP = tempfile.mkdtemp()
os.environ["AGENTS_DB"] = os.path.join(MAP, "proef.db")
os.environ["AGENTS_TOKEN"] = "proef"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A  # noqa: E402

K = {"X-Agents-Token": "proef"}
C = A.app.test_client()
fout = 0


def check(naam, voorwaarde, extra=""):
    global fout
    print(("ok   " if voorwaarde else "FOUT ") + naam + (f" ({extra})" if extra else ""))
    fout += 0 if voorwaarde else 1


DAG = "2026-10-29"
JPEG = b"\xff\xd8\xff fictieve kleine jpeg \xff\xd9"
os.makedirs(os.path.join(MAP, "fotoindeling", "2026"))
with open(os.path.join(MAP, "fotoindeling", "2026", f"{DAG}.json"), "w", encoding="utf-8") as f:
    json.dump({"datum": DAG, "werf": [{"fotos": [{"id": "werk-1", "voorbeeld": True}, {"id": "werk-mens", "voorbeeld": False}]}],
               "kandidaat": [{"fotos": [{"id": "kand-1", "voorbeeld": False}]}]}, f)


def stuur(fid="werk-1", inhoud=JPEG, dag=DAG, kop=K):
    return C.post("/api/fotovoorbeeld", headers=kop,
                  json={"dag": dag, "id": fid, "jpeg": inhoud if isinstance(inhoud, str) else base64.b64encode(inhoud).decode()})


def bestand(fid, dag=DAG):
    return os.path.join(MAP, "fotovoorbeeld", dag, f"{fid}.jpg")


check("V01 zonder token 403", stuur(kop={}).status_code == 403)
check("V01 metadata zonder token 403", C.post("/api/fotometadata", json={"dag": DAG, "aantal": 0, "fotos": []}).status_code == 403)
r = stuur()
check("V02 werkfoto aanvaard", r.status_code == 200 and r.get_json()["ok"], r.status_code)
check("V02 op de VM bewaard", open(bestand("werk-1"), "rb").read() == JPEG)
check("V02 alleen voor de gebruiker", oct(os.stat(bestand("werk-1")).st_mode & 0o777) == "0o600")
for fid in ("werk-mens", "kand-1", "onbekend"):
    r = stuur(fid)
    check(f"V03 {fid} geweigerd", r.status_code == 409 and not os.path.exists(bestand(fid)), r.status_code)
for naam, r in (("geen JPEG", stuur(inhoud=b"PNG fictief")), ("te groot", stuur(inhoud=JPEG[:-2] + b"x" * 200_000 + b"\xff\xd9")),
                ("geen base64", stuur(inhoud="!!!")), ("voor 01-10", stuur(dag="2026-09-30")), ("pad in id", stuur(fid="../x")),
                ("geen dag", stuur(dag="gisteren"))):
    check(f"V04 {naam} geweigerd", r.status_code == 400, r.status_code)
check("V04 niets extra op schijf", sorted(os.listdir(os.path.join(MAP, "fotovoorbeeld", DAG))) == ["werk-1.jpg"])
regels = {r.rule for r in A.app.url_map.iter_rules()}
check("V05 routes aan het bord", {"/api/fotovoorbeeld", "/api/fotometadata"} <= regels)

fotos = [{"id": "f-1", "utc": "2026-10-29T09:15:00+00:00", "lat": 50.12345, "lon": 4.12345, "video": False, "scherm": False,
          "app": False, "mensen": False, "bestand": "IMG_0001.HEIC"},
         {"id": "f-2", "utc": "2026-10-29T09:20:00+00:00", "lat": None, "lon": None, "video": True, "scherm": 1, "app": None, "mensen": None}]
geopend = []
_open = os.open
os.open = lambda pad, vlaggen, modus=0o777, *a, **k: geopend.append((pad, vlaggen, modus)) or _open(pad, vlaggen, modus, *a, **k)
oude_umask = os.umask(0)
try:
    r = C.post("/api/fotometadata", headers=K, json={"dag": DAG, "aantal": 2, "fotos": fotos})
finally:
    os.open, _ = _open, os.umask(oude_umask)
check("V06 het bestand ontstaat meteen met 0600, ook zonder umask",
      [m for p, v, m in geopend if p.endswith(".tmp")] == [0o600] and all(v & os.O_EXCL for p, v, m in geopend if p.endswith(".tmp")))
pad = os.path.join(MAP, "fotometadata", f"{DAG}.json")
check("V06 metadata aanvaard", r.status_code == 200 and r.get_json()["aantal"] == 2, r.status_code)
d = json.load(open(pad, encoding="utf-8"))
check("V06 alleen de velden van de indeling",
      [sorted(x) for x in d["fotos"]] == [["app", "gezicht", "id", "lat", "lon", "mensen", "scherm", "utc", "video"]] * 2)
check("V06 een vlag die geen ja of nee is, wordt onbekend", d["fotos"][1]["scherm"] is None and d["fotos"][0]["mensen"] is False)
check("V06 bestand alleen voor de gebruiker", oct(os.stat(pad).st_mode & 0o777) == "0o600")
con = sqlite3.connect(os.environ["AGENTS_DB"])
tekst = "\n".join(str(x) for t in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                  for x in con.execute(f"SELECT * FROM {t[0]}").fetchall())
check("V06 geen GPS in de databank van het bord", "50.12345" not in tekst)
for naam, inhoud in (("fout aantal", {"dag": DAG, "aantal": 3, "fotos": fotos}), ("geen lijst", {"dag": DAG, "aantal": 0, "fotos": "x"}),
                     ("id met pad", {"dag": DAG, "aantal": 1, "fotos": [dict(fotos[0], id="../x")]}),
                     ("voor 01-10", {"dag": "2026-09-30", "aantal": 0, "fotos": []})):
    check(f"V06 {naam} geweigerd", C.post("/api/fotometadata", headers=K, json=inhoud).status_code == 400)

print("fout:", fout)
sys.exit(1 if fout else 0)

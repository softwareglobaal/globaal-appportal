"""Grendel op POST /api/fotovoorbeeld (fotovoorbeeld.py, T-0120 FOTO-5): voorvertoningen van werkfoto's op de VM.

- V01: zonder token 403;
- V02: een kleine JPEG van een werkfoto die de indeling van die dag toelaat, komt in <data>/fotovoorbeeld/<dag>/<id>.jpg;
- V03: een foto met mensen, een kandidaat of een onbekende foto wordt geweigerd (409), ook met een geldige JPEG;
- V04: geen JPEG, te groot, geen base64, een dag voor 01-10 of een id met een pad wordt geweigerd (400), en er komt niets
  op schijf;
- V05: de route hangt aan het echte bord (app.py).
Verzonnen ids. Draait in de Docker-build: faalt dit, dan blijft de vorige container staan.
"""
import base64
import json
import os
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
r = stuur()
check("V02 werkfoto aanvaard", r.status_code == 200 and r.get_json()["ok"], r.status_code)
check("V02 op de VM bewaard", open(bestand("werk-1"), "rb").read() == JPEG)
for fid in ("werk-mens", "kand-1", "onbekend"):
    r = stuur(fid)
    check(f"V03 {fid} geweigerd", r.status_code == 409 and not os.path.exists(bestand(fid)), r.status_code)
for naam, r in (("geen JPEG", stuur(inhoud=b"PNG fictief")), ("te groot", stuur(inhoud=JPEG[:-2] + b"x" * 200_000 + b"\xff\xd9")),
                ("geen base64", stuur(inhoud="!!!")), ("voor 01-10", stuur(dag="2026-09-30")), ("pad in id", stuur(fid="../x")),
                ("geen dag", stuur(dag="gisteren"))):
    check(f"V04 {naam} geweigerd", r.status_code == 400, r.status_code)
check("V04 niets extra op schijf", sorted(os.listdir(os.path.join(MAP, "fotovoorbeeld", DAG))) == ["werk-1.jpg"])
check("V05 route aan het bord", any(r.rule == "/api/fotovoorbeeld" for r in A.app.url_map.iter_rules()))

print("fout:", fout)
sys.exit(1 if fout else 0)

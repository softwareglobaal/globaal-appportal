"""Buildgrendel: beheerrechten, veilige tekstweergave en begrensde paginering."""
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone

DATA = tempfile.mkdtemp()
os.environ["AGENTS_DB"] = os.path.join(DATA, "bord.db")
os.environ["AGENTS_TOKEN"] = "verzonnen-testtoken"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A

os.mkdir(os.path.join(DATA, "naamstructuur"))
c = sqlite3.connect(os.path.join(DATA, "naamstructuur", "index.sqlite3"))
c.execute("CREATE TABLE bevinding(agent,scope,identiteit,regel,bron,firma,naam,pad,voorstel,status,eerste,laatste)")
for i in range(102):
    c.execute("INSERT INTO bevinding VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
        "benamingen-wacht", "verzonnen-root", str(i), "testregel", "verzonnen bron", "TEST", "dummy",
        "/voorbeeld/<script>alert(1)</script>", "Voorstel behouden", "open", "2026-10-05", "2026-10-05"))
c.commit()
c.close()
with open(os.path.join(DATA, "naamstructuur", "overzicht.json"), "w") as f:
    json.dump({"gemaakt": "2026-10-05", "scopes": [], "tellingen": {"benamingen-wacht": 102}}, f)

client = A.app.test_client()
BEHEER = {"X-authentik-groups": "admin", "X-authentik-username": "mehdi"}
ANDER = {"X-authentik-groups": "agents", "X-authentik-username": "ander"}
assert client.get("/naamstructuur", headers=ANDER).status_code == 403
assert client.get("/naamstructuur").status_code == 403
assert client.get("/naamstructuur", headers={"X-Agents-Token": "verzonnen-testtoken"}).status_code == 403
pagina = client.get("/naamstructuur", headers=BEHEER)
assert pagina.status_code == 200
html = pagina.get_data(as_text=True)
assert "<script>alert" not in html and "&lt;script&gt;" in html
assert html.count("Voorstel behouden") == 100
assert "Volgende" in html
assert client.get("/naamstructuur?pagina=2", headers=BEHEER).get_data(as_text=True).count("Voorstel behouden") == 2
assert client.get("/naamstructuur?status=niet-bestaand", headers=BEHEER).status_code == 400
assert client.get("/naamstructuur?pagina=abc", headers=BEHEER).status_code == 400
assert "Namen en mappen" not in client.get("/", headers=ANDER).get_data(as_text=True)
assert "Namen en mappen" in client.get("/", headers=BEHEER).get_data(as_text=True)
client.post("/api/agent", json={"naam": "benamingen-wacht", "label": "Benamingenwacht"}, headers={"X-Agents-Token": "verzonnen-testtoken"})
with A.app.app_context():
    oud = (datetime.now(timezone.utc) - timedelta(minutes=46)).isoformat()
    A.db().execute("INSERT INTO status(naam,status,ts) VALUES('benamingen-wacht','klaar',?)", (oud,))
    A.db().commit()
with A.app.test_request_context(headers=BEHEER):
    assert next(k for k in A.kaarten() if k["naam"] == "benamingen-wacht")["toestand"] == "stil"
print("Naamstructuur: beheergrens, escaping en paginering geslaagd")

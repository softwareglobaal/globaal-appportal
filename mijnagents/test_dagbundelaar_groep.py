"""Grendel op de groep Dagbundelaar (Mehdi, 31-10-2026: "alle agents die voor de dagbundelaar werken op één plek",
"maak niks dubbel").

- G01: een agent uit DAGBUNDELAAR_AGENTS landt in de groep dagbundelaar, ook als hij zich met een oude groep meldt;
- G02: een agent die er niet bij hoort, houdt zijn eigen groep;
- G03: een agent die al in een oude groep stond, verhuist bij de start van het bord (geen kopie in de oude groep);
- G04: het organogram toont de groep Dagbundelaar met status en laatste ronde, elke agent precies één keer;
- G05: de lege subgroep Communicatie verdwijnt van het bord en het organogram;
- G06: elke agent van de groep draagt de vaste naam uit DAGBUNDELAAR_AGENTS, ook als hij zich anders meldt;
- G08: drie lagen op het organogram: Ai Angel, daaronder De Dagbundelaar, daaronder het blok Wachten;
- G07: een agent die nog niet gebouwd is, staat als lege plek "nog te bouwen" op het organogram, zonder databankrij.

Draait in de Docker-build: faalt dit, dan blijft de vorige container staan.
"""
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone

MAP = tempfile.mkdtemp()
os.environ["AGENTS_DB"] = os.path.join(MAP, "start.db")
os.environ["AGENTS_TOKEN"] = "proef"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A  # noqa: E402

K = {"X-Agents-Token": "proef"}
BEHEER = {"X-authentik-groups": "admin", "X-authentik-username": "proef"}
C = A.app.test_client()
fout = 0


def check(naam, voorwaarde, extra=""):
    global fout
    print(("ok   " if voorwaarde else "FOUT ") + naam + (f" ({extra})" if extra else ""))
    fout += 0 if voorwaarde else 1


def type_van(naam):
    con = sqlite3.connect(os.environ["AGENTS_DB"])
    try:
        return con.execute("SELECT type FROM agent WHERE naam=?", (naam,)).fetchone()[0]
    finally:
        con.close()


C.post("/api/afdeling", headers=K, json={"naam": "prive-communicatie", "label": "Communicatie"})
C.post("/api/afdeling", headers=K, json={"naam": "mail", "label": "Mail"})
C.post("/api/agent", headers=K, json={"naam": "belwacht", "label": "De Belwacht", "type": "prive-communicatie"})
C.post("/api/agent", headers=K, json={"naam": "mail-mch", "label": "De Mailwacht mch@", "type": "mail"})
C.post("/api/agent", headers=K, json={"naam": "mail-regisseur", "label": "De Mailregisseur", "type": "mail"})
check("G01 belwacht in dagbundelaar", type_van("belwacht") == "dagbundelaar", type_van("belwacht"))
check("G01 mailwacht mch in dagbundelaar", type_van("mail-mch") == "dagbundelaar", type_van("mail-mch"))
check("G02 mailregisseur blijft in mail", type_van("mail-regisseur") == "mail", type_van("mail-regisseur"))

# G03: een oude stand rechtstreeks in de databank, dan start het bord opnieuw.
con = sqlite3.connect(os.environ["AGENTS_DB"])
con.execute("UPDATE agent SET type='prive-communicatie' WHERE naam='belwacht'")
con.execute("INSERT INTO agent(naam,label,type,actief,aangemaakt) VALUES('icloud-wacht','De iCloud-wacht','prive',1,'x')")
TS = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
con.execute("INSERT INTO status(naam,status,taak,detail,ts) VALUES('icloud-wacht','fout','foto''s','',?)", (TS,))
con.commit()
con.close()
A.init_db()
check("G03 belwacht verhuisd", type_van("belwacht") == "dagbundelaar", type_van("belwacht"))
check("G03 icloud-wacht verhuisd", type_van("icloud-wacht") == "dagbundelaar", type_van("icloud-wacht"))

html = C.get("/organogram", headers=BEHEER).get_data(as_text=True)
check("G04 blok Wachten zichtbaar", "<h2>Wachten</h2>" in html)
i_angel, i_dagb, i_wacht = html.find(">Ai Angel<"), html.find(">De Dagbundelaar<"), html.find("<h2>Wachten</h2>")
check("G08 drie lagen: Ai Angel boven De Dagbundelaar boven de wachten", -1 < i_angel < i_dagb < i_wacht,
      f"{i_angel} {i_dagb} {i_wacht}")
check("G08 Ai Angel en De Dagbundelaar niet in het blok Wachten", html.count(">Ai Angel<") == 1 and html.count(">De Dagbundelaar<") == 1)
check("G04 elke agent één keer", html.count("De Belwacht iPhone<") == 1 and html.count("De Fotowacht<") == 1)
check("G06 vaste naam ook bij een oude registratie", "De iCloud-wacht" not in html and ">De Belwacht<" not in html)
check("G07 lege plek voor wat nog niet gebouwd is", "De Sms-wacht" in html and "De YouTube-wacht" in html
      and html.count("nog te bouwen") >= 5)
C.post("/api/agent", headers=K, json={"naam": "sms-wacht", "label": "sms teller", "type": "prive"})
html2 = C.get("/organogram", headers=BEHEER).get_data(as_text=True)
check("G07 gebouwde agent krijgt zijn vaste naam en is geen lege plek",
      html2.count("De Sms-wacht") == 1 and "sms teller" not in html2 and type_van("sms-wacht") == "dagbundelaar")
VERWACHT = A._laatste_ronde(TS)
check("G04 laatste ronde getoond", VERWACHT and VERWACHT in html, VERWACHT)
check("G04 oude ronde met datum", A._laatste_ronde("2026-10-30T20:15:00+00:00") == "30-10 21:15")
check("G04 fout zichtbaar", "var(--fout)" in html)
check("G05 lege Communicatie weg uit organogram", "<h3>Communicatie</h3>" not in html)
bord = C.get("/", headers=BEHEER).get_data(as_text=True)
check("G05 lege Communicatie weg uit bord", ">Communicatie<" not in bord and "Communicatie <span" not in bord)
check("G05 Dagbundelaar op het bord", "Dagbundelaar" in bord)

sys.exit(1 if fout else 0)

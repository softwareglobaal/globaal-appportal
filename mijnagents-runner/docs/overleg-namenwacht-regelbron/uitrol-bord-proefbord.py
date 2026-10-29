import os, sys, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "kloon", "mijnagents"))
import app as A
with A.app.app_context():
    A.init_db()
c = sqlite3.connect(os.environ["AGENTS_DB"])
for naam, f in (("benamingen-wacht", "bw11.md"), ("mappen-wacht", "mw11.md")):
    tekst = open(os.path.join(os.path.dirname(__file__), f), encoding="utf-8").read().strip()
    c.execute("INSERT OR REPLACE INTO agent(naam,label,werkwijze,mandaat,aangemaakt) VALUES(?,?,?,?,?)", (naam, naam, tekst, "oud mandaat", "2026-10-06"))
c.commit(); c.close()
A.app.run(host="127.0.0.1", port=3999)

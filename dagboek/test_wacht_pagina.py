"""Grendel op de pagina van een wacht in het Dagboek (/wachten/<naam>) voor het vak Agenda (T-0120, groep agenda).

- AG-2: de regels van een signaal of dagplan staan als lijst onder het item; '(privé)' blijft '(privé)'; ruwe HTML in een
  regel blijft tekst;

Het bord is nagebootst (haal_wachten). Verzonnen voorbeelden, geen echte namen. Draait in de Docker-build.
"""
import json
import os
import sys
import tempfile
from datetime import date

HIER = os.path.dirname(os.path.abspath(__file__))
os.environ["DAGBOEK_MAP"] = tempfile.mkdtemp()
os.environ["DAGBOEK_GROUPS"] = "dagboek"
sys.path.insert(0, HIER)
import app as A  # noqa: E402

C = A.app.test_client()
MET = {"X-authentik-groups": "medewerkers|dagboek"}
fout = 0


def check(naam, voorwaarde, extra=""):
    global fout
    print(("  ok   " if voorwaarde else "  FOUT ") + naam, "" if voorwaarde else extra)
    fout += 0 if voorwaarde else 1


A.vandaag = lambda: date(2026, 10, 31)
A.haal_locatie = lambda pad: None


def wacht(**extra):
    w = {"naam": "agenda-wacht", "label": "De Agendawacht", "kleur": "groen", "oordeel": "binnen", "aantal": 1,
         "rondes": 0, "gedekt": None, "leesfout": "", "logfout": "", "noden": [], "fouten": [], "status": None,
         "items": [], "log": []}
    w.update(extra)
    return {"dag": "2026-10-31", "items": w["aantal"], "telling": {}, "vakken": [{"vak": "Agenda", "wachten": [w]}]}


# --- AG-2
SIG = {"tijd": "09:00", "wie": "signaal", "wat": "Link doorsturen of titel nakijken", "fout": False,
       "regels": ["2026-11-02T09:00 proef A: link doorsturen", "12:00 (privé)", "<b>proef</b> C"]}
A._cache.clear()
A.haal_wachten = lambda dag, *a: json.loads(json.dumps(wacht(items=[SIG])))
html = C.get("/wachten/agenda-wacht?dag=2026-10-31", headers=MET).get_data(as_text=True)
check("AG-2 de regels van een signaal staan als lijst onder het item",
      '<ul class="regels"><li>2026-11-02T09:00 proef A: link doorsturen</li><li>12:00 (privé)</li>' in html, html[-4000:])
check("AG-2 ruwe HTML in een regel blijft tekst", "&lt;b&gt;proef&lt;/b&gt; C" in html and "<b>proef</b>" not in html)
A.haal_wachten = lambda dag, *a: json.loads(json.dumps(wacht(items=[dict(SIG, regels=[])])))
html = C.get("/wachten/agenda-wacht?dag=2026-10-31", headers=MET).get_data(as_text=True)
check("AG-2 een item zonder regels krijgt geen lege lijst", '<ul class="regels">' not in html)

print("wacht-pagina: alles ok" if not fout else f"wacht-pagina: {fout} fout(en)")
sys.exit(1 if fout else 0)

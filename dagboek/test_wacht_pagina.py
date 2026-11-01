"""Grendel op de pagina van een wacht in het Dagboek (/wachten/<naam>) voor het vak Agenda (T-0120, groep agenda).

- AG-2: de regels van een signaal of dagplan staan als lijst onder het item; '(privé)' blijft '(privé)'; ruwe HTML in een
  regel blijft tekst;
- AG-9: een werkverslag met meer dan een blad toont de bladknoppen; ?blad=1 vraagt het bord om dat blad van deze wacht;
  zonder blad blijft de vraag aan het bord dezelfde als voordien;
- CL-4: een weekend zonder ronde bij een werkdagwacht zegt 'geen ronde gepland', niet 'geen ronde' of 'kwam binnen'.

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
HAAL_ECHT = A.haal_wachten                 # de echte vraag aan het bord, voor de proef van het pad

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

# --- AG-9
gevraagd = []


def bord(dag, *a):
    gevraagd.append((dag,) + a)
    blad = a[1] if len(a) > 1 else None
    log = [{"tijd": "08:00", "stap": "schrijf", "tekst": f"proefregel {'0001' if blad == 1 else '1200'}", "fout": False}]
    return json.loads(json.dumps(wacht(rondes=1200, log=log, log_blad=blad or 2, log_bladen=2)))


A.haal_wachten = bord
html = C.get("/wachten/agenda-wacht?dag=2026-10-31", headers=MET).get_data(as_text=True)
check("AG-9 zonder blad: dezelfde vraag aan het bord als voordien, het laatste blad", gevraagd[-1] == ("2026-10-31",)
      and "proefregel 1200" in html, gevraagd)
check("AG-9 de bladknoppen staan er, blad 2 is aan",
      'href="/wachten/agenda-wacht?dag=2026-10-31&amp;blad=1"' in html and '<a class="aan" href="/wachten/agenda-wacht?dag=2026-10-31&amp;blad=2"' in html
      and "blad 2 van 2" in html, html[-5000:])
html = C.get("/wachten/agenda-wacht?dag=2026-10-31&blad=1", headers=MET).get_data(as_text=True)
check("AG-9 ?blad=1 vraagt het bord om blad 1 van deze wacht en toont het begin",
      gevraagd[-1] == ("2026-10-31", "agenda-wacht", 1) and "proefregel 0001" in html and "blad 1 van 2" in html, gevraagd)
html = C.get("/wachten/agenda-wacht?dag=2026-10-31&blad=nul", headers=MET)
check("AG-9 een blad dat geen getal is, geeft gewoon het laatste blad", html.status_code == 200 and gevraagd[-1] == ("2026-10-31",))
A.haal_wachten = lambda dag, *a: json.loads(json.dumps(wacht(rondes=3, log=[{"tijd": "08:00", "stap": "bron", "tekst": "x",
                                                                             "fout": False}], log_blad=1, log_bladen=1)))
html = C.get("/wachten/agenda-wacht?dag=2026-10-31", headers=MET).get_data(as_text=True)
check("AG-9 een werkverslag van een blad krijgt geen bladknoppen", "blad 1 van 1" not in html and "&amp;blad=" not in html)
pad = []
A._cache.clear()
_oud = A.urllib.request.urlopen
A.urllib.request.urlopen = lambda req, timeout=0: pad.append(req.full_url) or (_ for _ in ()).throw(OSError("proef"))
try:
    HAAL_ECHT("2026-10-31", "agenda-wacht", 2)
    HAAL_ECHT("2026-10-31")
finally:
    A.urllib.request.urlopen = _oud
check("AG-9 de vraag aan het bord draagt wacht en blad alleen als er een blad gevraagd is",
      pad == [A.BORD + "/api/wachten/dag?dag=2026-10-31&wacht=agenda-wacht&blad=2", A.BORD + "/api/wachten/dag?dag=2026-10-31"], pad)

# --- CL-4
A.haal_wachten = lambda dag, *a: json.loads(json.dumps(wacht(naam="calendly-wacht", label="De Calendlywacht", kleur="rust",
                                                              oordeel="geen ronde gepland", aantal=0)))
html = C.get("/wachten/calendly-wacht?dag=2026-10-31", headers=MET).get_data(as_text=True)
check("CL-4 de kop zegt 'geen ronde gepland', niet 'kwam binnen'", "za 31 okt 2026: geen ronde gepland</h2>" in html
      and "kwam binnen</h2>" not in html, html[-4000:-2500])
check("CL-4 het werkverslag zegt waarom er geen ronde is", "deze wacht draait alleen op werkdagen" in html)
html = C.get("/wachten?dag=2026-10-31", headers=MET).get_data(as_text=True)
check("CL-4 het overzicht telt 'geen ronde gepland' apart, niet als 'kwam binnen'",
      '<span class="stip rust"></span> <span class="groot">1</span> geen ronde gepland' in html
      and '<span class="stip groen"></span> <span class="groot">0</span> kwam binnen' in html, html[:4000])
check("CL-4 de tegel heeft de eigen kleur en zegt 'geen ronde gepland'", "kleur-rust" in html and "geen ronde gepland" in html)
A.haal_wachten = lambda dag, *a: json.loads(json.dumps(wacht(naam="calendly-wacht", label="De Calendlywacht", kleur="grijs",
                                                              oordeel="niets binnen, geen ronde", aantal=0)))
html = C.get("/wachten/calendly-wacht?dag=2026-10-31", headers=MET).get_data(as_text=True)
check("CL-4 een gewone grijze dag blijft 'geen ronde'", "za 31 okt 2026: geen ronde</h2>" in html and "Geen ronde op deze dag." in html)

print("wacht-pagina: alles ok" if not fout else f"wacht-pagina: {fout} fout(en)")
sys.exit(1 if fout else 0)

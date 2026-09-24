"""Grendel op Werfverslag voorbereider en schrijver: verhuisde projectmap en het bezoeknummer.

Gebeurd op 24-09-2026 met dossier 2145:
- de projectmap verhuisde van fasemap en de voorbereider zag de bezoeken als nieuw (dubbele rijen);
- de schrijver kreeg 'Werfbezoek 8' mee (het volgnummer van de rij, dat ook de plaatsbezoeken PB1-PB5 telt)
  terwijl het werfbezoek 3 was, en schreef 'in de opdracht vermeld als werfbezoek 8: na te kijken'.
Deze toetsen falen zodra het volgnummer weer naar Claude of in de puntnummering gaat, of een verhuis niet
meer herkend wordt.
"""
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import werfverslag_voorbereider as V  # noqa: E402
import werfverslag_proef as P  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


OUD = "/Work All/01. H-A WORK/0 H-A Standaard projects/4. STAN Execution waiting to start/2145 Vertommensberg 9"
NIEUW = "/Work All/01. H-A WORK/0 H-A Standaard projects/5. STAN Execution ONGOING/2145 Vertommensberg 9"
REL = "/_00. Communication/2026-06-06 bezoek klant - plaatsbezoek werf"

# verhuis herkennen
bezoeken = [{"map": NIEUW + REL, "datum": "2026-06-06"}, {"map": NIEUW + "/_00. Communication/2026-09-22 werfbezoek 3", "datum": "2026-09-22"}]
bord = [{"id": 145, "datum": "2026-06-06", "projectmap": NIEUW, "bezoekmap": NIEUW + REL},
        {"id": 19, "datum": "2026-06-06", "projectmap": OUD, "bezoekmap": OUD + REL, "gegevens": {"gegevens": [1]}},
        {"id": 30, "datum": "2026-06-07", "projectmap": OUD, "bezoekmap": OUD + REL},
        {"id": 31, "datum": "2026-06-06", "projectmap": OUD, "bezoekmap": OUD + "/Site Reports/2026-06-06 andere map"}]
v = V.verhuisde_rijen(bezoeken, NIEUW, bord)
check("de rij van het oude fasepad wordt herkend", [r["id"] for r in v.get(NIEUW + REL, [])] == [19], v)
check("een andere datum of een andere bezoekmap telt niet als verhuis", set(v) == {NIEUW + REL}, v)
check("de rij van het nieuwe pad zelf is geen verhuis", all(r["id"] != 145 for x in v.values() for r in x))
hoofd = [{"id": 19, "datum": "2026-06-06", "projectmap": OUD.replace("waiting", "Waiting"), "bezoekmap": OUD.replace("waiting", "Waiting") + REL.upper()}]
check("een andere hoofdletter in het pad belet de herkenning niet", [r["id"] for r in V.verhuisde_rijen(bezoeken, NIEUW, hoofd).get(NIEUW + REL, [])] == [19])
s = V.samengevoegd([bord[0], bord[1]])
check("de controle ziet de gegevens van de oude rij", s.get("gegevens") and s["bezoekmap"] == NIEUW + REL, s)

# opruimvoorstel: altijd via Mehdi, en elke ronde letterlijk hetzelfde (anders zet het bord het elke ronde opnieuw)
d = [{"dossier": "2145", "dubbel": 20, "id": 146, "botsing": []}, {"dossier": "2145", "dubbel": 19, "id": 145, "botsing": []}]
vs = V.opruimvoorstel(d)
check("opruimen is een voorstel met het runbook werfbezoek-dubbels", vs and vs["runbook"] == "werfbezoek-dubbels")
check("het voorstel noemt de paren oud -> blijft", vs["parameters"]["paren"] == [[19, 145], [20, 146]], vs["parameters"])
check("het voorstel is elke ronde gelijk", V.opruimvoorstel(list(reversed(d))) == vs)
check("zonder dubbels geen voorstel", V.opruimvoorstel([]) is None)

# het bezoeknummer, niet het volgnummer
rij = {"dossier": "2145", "adres": "Vertommensberg 9", "datum": "2026-09-22", "bezoekmap": NIEUW + "/x",
       "bronnen": {"nr_label": "3", "soort_bezoek": "werfbezoek"}}
kop = P.kop_voorbereiding("2145", rij, 8, [], [])
check("de voorbereiding krijgt werfbezoek 3 mee", "Werfbezoek 3 " in kop and "2145-3" in kop, kop)
check("het volgnummer 8 gaat niet naar Claude", "8" not in kop.replace("2026-09-22", ""), kop)
pb = dict(rij, bronnen={"nr_label": "PB2", "soort_bezoek": "plaatsbezoek"})
check("een plaatsbezoek heet PB2", "Plaatsbezoek PB2" in P.kop_voorbereiding("2145", pb, 2, [], []))
check("zonder nr_label (oude rij) blijft het volgnummer", P.bezoeknummer({"bronnen": {}}, 4) == ("4", "werfbezoek"))
cats = P._nummer_punten({"categorieen": [{"naam": "Ruwbouw", "punten": [{"titel": "a"}, {"titel": "b"}]}]}, "3", doorlopend=False)
check("de punten van werfbezoek 3 heten 3.1, 3.2", [p["nummer"] for p in cats[0]["punten"]] == ["3.1", "3.2"], cats)

import ast  # noqa: E402
verwerk = next(f for f in ast.walk(ast.parse((HIER / "werfverslag_voorbereider.py").read_text(encoding="utf-8")))
               if isinstance(f, ast.FunctionDef) and f.name == "verwerk")
toekenningen = [t.id for n in ast.walk(verwerk) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)]
check("het soort project wordt in verwerk maar één keer gezet (anders 'taak-project' op de pagina)",
      toekenningen.count("soort") == 0, f"{toekenningen.count('soort')} gewone toekenning(en) aan 'soort'")

bron = (HIER / "werfverslag_proef.py").read_text(encoding="utf-8")
check("geen 'Werfbezoek {volgnr}' meer in de schrijver", "Werfbezoek {volgnr}" not in bron)
check("proef nummert met het bezoeknummer", "_nummer_punten(uit, nr_label" in bron)

print(f"\n{ok} ok, {fout} fout")
sys.exit(1 if fout else 0)

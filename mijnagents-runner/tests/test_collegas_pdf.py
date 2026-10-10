"""Grendel op het blad voor de collega's (Mehdi, 11-10-2026). Zonder netwerk, Chrome en sleutels (ook CI).

Bewijst: elk voorbeeld in het blad wordt door de agent zelf gelezen zoals het blad zegt (firma, soort, opdracht,
nummer, buiten, onzeker), staat al in zijn eindvorm (canoniek, tekens vooraan) en brengt de genoemde collega als
agendagast mee; het telefoonvoorbeeld telt als telefoonnummer; elke firma-, soort- en opdrachtcode uit de master staat
in het blad; geen oude code als voorbeeld; geen privé-, Lara- of firma-agenda-adres; nooit de volledige landnaam van SU;
de versie van het blad komt uit de master.
"""
import os
import re
import sys
from pathlib import Path

os.environ["BELLEN_UIT"] = "1"
HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
sys.path.insert(0, str(HIER / "werkwijze" / "pdf"))
import agenda_wacht as W     # noqa: E402
import collegas_pdf as C     # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


t = C.master()
tc = t["titelconventie"]
doc = C.bericht(t, C.firmas_master(t), "11-10-2026", "test")
tekst = re.sub(r"<[^>]+>", " ", doc)

print("voorbeelden zoals de agent ze leest")
mensen = {"catalin@voorbeeld.test": {"voornaam": "Catalin", "naam": "Catalin", "in_dienst": True},
          "shaniel@voorbeeld.test": {"voornaam": "Shaniel", "naam": "Shaniel", "in_dienst": True},
          "jan@voorbeeld.test": {"voornaam": "Jan", "naam": "Jan", "in_dienst": True}}
for v in C.VOORBEELDEN:
    titel = v["titel"]
    lt = W.lees_titel(titel)
    gelezen = {"firma": lt.get("agendacode"), "soort": lt["soort"], "type": lt["type"], "nummer": lt["nummer"],
               "buiten": lt["buiten"], "onzeker": lt["onzeker"]}
    verwacht = {k: v[k] for k in gelezen}
    check(f"gelezen zoals bedoeld: {titel}", gelezen == verwacht, f"{gelezen} != {verwacht}")
    check(f"al in eindvorm: {titel}", W.canoniek(titel) == titel and W.tekens_vooraan(titel) == titel,
          f"{W.canoniek(titel)!r} / {W.tekens_vooraan(titel)!r}")
    check(f"in het blad: {titel}", C.e(titel) in doc)
    gasten = W.agendagasten_voor(titel, regels=t["agendagasten"], mensen=mensen)
    bedoeld = {f"{v['gast'].lower()}@voorbeeld.test"} if v.get("gast") else set()
    check(f"agendagasten {sorted(bedoeld)}: {titel}", gasten == bedoeld, f"{sorted(gasten)}")
    check(f"!! alleen bij buiten: {titel}", titel.startswith("!!") == v["buiten"])
check("de klant met dezelfde voornaam als een collega wordt geen gast",
      "jan@voorbeeld.test" not in set().union(*(W.agendagasten_voor(v["titel"], regels=t["agendagasten"], mensen=mensen)
                                                 for v in C.VOORBEELDEN)))
check("telefoonvoorbeeld telt als telefoonnummer", bool(W.telefoon_in(C.TEL_VOORBEELD)))
check("telefoonvoorbeeld staat in het blad", C.e(C.TEL_VOORBEELD) in doc)

print("codes uit de master")
for k in [k for k, _ in C.firmas_master(t)] + list(tc["soorten"]) + list(tc["types"]):
    check(f"code {k} in het blad", f"<b>{k}</b>" in doc)
check("privé en Lara staan niet bij de firma's", all(f"<b>{k}</b></td><td>{C.e(n)}" not in doc
                                                       for k, n in tc["codes_twee_letters"]["firmas"].items() if k in C.NIET_VOOR_COLLEGAS))
oude = [o for o in tc["oude_codes"]["firma"] if len(o) > 2] + [o for o in tc["oude_codes"]["opdracht"] if len(o) > 2]
check("geen oude code als voorbeeld of in een titelvorm",
      not re.search(r"\[(%s)-|\b(%s) \d" % ("|".join(map(re.escape, oude)), "|".join(map(re.escape, oude))), tekst),
      re.findall(r"\[[A-Z]{3,}-[A-Z]+\]", tekst))
for o, n in tc["oude_codes"]["firma"].items():
    if n not in C.NIET_VOOR_COLLEGAS:
        check(f"oude code {o} vertaald naar {n}", o in tekst)

print("wat er wel en niet in staat")
werk = next(a for a in t["agendas"] if a["rol"] == "werk")
check("de werkagenda met adres", werk["naam"] in doc and werk["adres"] in doc)
for a in t["agendas"]:
    if a["rol"] != "werk":
        check(f"geen adres van {a['naam']}", a["adres"] not in doc)
for a in t["agendas"]:
    if a["rol"] in ("firma", "sales"):
        check(f"oude agenda {a['naam']} als 'niet meer gebruiken'", a["naam"] in tekst)
check("geen privé-postvak", "hotmail" not in doc.lower() and "mehdipriveagena" not in doc)
check("nooit de volledige landnaam van SU", "urinam" not in doc)
# zoals organisatie.globaal.be de firma live schrijft: ook dan geen landnaam in het blad
live = [(k, "High Design Studio (Suriname)" if k == "DS" else n) for k, n in C.firmas_master(t)]
check("ook niet met de live firmanaam", "urinam" not in C.bericht(t, live, "11-10-2026", "test"))
for m in ("Geen buiten afspraken", "geen auto", "Geen afspraken", "Buitenland"):
    check(f"hele-dag-stop '{m}'", m in tekst)
check("Google-instelling uit de master", C.google_instelling(t) in doc and "'" not in C.google_instelling(t))
check("versie uit de master", f"versie {t['collegadocument']['versie']}," in tekst)
check("ZZ ARCHIEF genoemd", "ZZ ARCHIEF" in tekst)
check("vragen naar Shaniel", "geef het door aan Shaniel" in tekst)
check("geen voornaamwoord voor een collega", not re.search(r"\b(zijn|haar|hij|zij) eigen\b", tekst))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

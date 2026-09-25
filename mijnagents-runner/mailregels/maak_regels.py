"""Maakt een regelbestand voor een mailbox op basis van regels_hinvest.txt (repo globaal-appportal,
mijnagents-runner/mailregels/; 26-9-2026), met samenvoegingen, weglatingen en
toevoegingen per sectie. Gebruik: maak_regels.py <basis.txt> <toevoegingen.txt> <uit.txt>

toevoegingen.txt:
  [KOP]            één regel: de kop van het nieuwe bestand (tot [/KOP])
  [SAMEN]          regels 'bron -> doel' (sectie bron samenvoegen in doel)
  [WEG]            secties die wegvallen
  [EIGEN]          extra eigen domeinen voor [oplichting]
  [INBOX.Map]      extra afzenders voor die map (nieuwe map mag)
"""
import sys
from collections import OrderedDict

basis, extra, uit = sys.argv[1:4]


def secties(pad):
    s, huidig = OrderedDict(), None
    s[None] = []
    for regel in open(pad, encoding="utf-8"):
        r = regel.rstrip("\n")
        if r.strip().startswith("[") and r.strip().endswith("]"):
            huidig = r.strip()[1:-1]
            s.setdefault(huidig, [])
            continue
        s[huidig].append(r)
    return s


b = secties(basis)
e = secties(extra)
kop = [r for r in e.get("KOP", []) if r.strip()]
samen = [tuple(x.strip() for x in r.split("->")) for r in e.get("SAMEN", []) if "->" in r]
weg = {r.strip() for r in e.get("WEG", []) if r.strip() and not r.startswith("#")}
eigen = [r.strip() for r in e.get("EIGEN", []) if r.strip() and not r.startswith("#")]

for bron, doel in samen:
    b.setdefault(doel, [])
    b[doel] += [f"# (uit {bron})"] + [r for r in b.pop(bron, []) if r.strip()]
for w in weg:
    b.pop(w, None)
for sec, regels in e.items():
    if sec in (None, "KOP", "SAMEN", "WEG", "EIGEN") or sec.startswith("/"):
        continue
    doel = b.setdefault(sec, [])
    bestaand = {r.strip().lower() for r in doel if r.strip() and not r.startswith("#")}
    nieuw = [r for r in regels if r.strip() and (r.startswith("#") or r.strip().lower() not in bestaand)]
    if nieuw:
        doel += ["# toegevoegd voor deze mailbox"] + nieuw
if eigen:
    b["oplichting"] = [(r + ", " + ", ".join(eigen)) if r.startswith("eigen =") else r for r in b["oplichting"]]

volgorde = [k for k in b if k not in (None, "oplichting", "archief")] + ["oplichting", "archief"]
# dubbels over secties heen: de eerste sectie wint niet, sorteren.py neemt de laatste; ik meld ze zodat ik ze oplos
gezien = {}
for k in volgorde:
    for r in b[k]:
        x = r.strip().lower()
        if x and not x.startswith("#") and k not in ("oplichting", "archief"):
            if x in gezien and gezien[x] != k:
                print(f"DUBBEL: {x} in {gezien[x]} en {k}", file=sys.stderr)
            gezien[x] = k
with open(uit, "w", encoding="utf-8") as f:
    f.write("\n".join(kop) + "\n\n")
    for k in volgorde:
        f.write(f"[{k}]\n")
        f.write("\n".join(r for r in b[k] if r.strip() or False) + "\n\n")
print("geschreven:", uit, "regels:", len(gezien))

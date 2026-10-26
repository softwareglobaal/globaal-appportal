"""Grendel- en regressietests voor UNABO Aankoopkeuring F1 (aankoopkeuring_verslag.py).

Toetst de 3-0 besluiten uit het driehoeksoverleg van 23-10-2026 en de beslissingen van Mehdi:
- X1/K1: hergebruik van verslag_basis.py en verslagsoorten.py met eigen profiel 'aankoopkeuring', zonder regressie op barsten-scheuren.
- X2/S6 (besluit Mehdi 23-10-2026): nooit herstelkosten, prijsramingen of bedragen in euro in het keuringsrapport.
- X3/K4/K5/S7: geen uitspraak over verjaring ('verjaard'), geen garantie op regularisatie ('gegarandeerd regulariseerbaar', 'zeker vergund'),
  geen 'vrij van verborgen gebreken' of 'volledig onderzocht', en verplicht hoofdstuk 'Niet-beoordeelde en ontoegankelijke delen'.
- X5/K6: eigen UNABO-nummering (AK-voorvoegsel) buiten de 46xxx-reeks van TKN Barsten en Scheuren.
- AGENTNORM hoofdstuk 8: werkwijze/aankoopkeuring-verslag.md slaagt voor bord.grenzen().
"""
import sys
from pathlib import Path
from unittest.mock import patch

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import bord  # noqa: E402
import schrijfregels as S  # noqa: E402
import verslag_basis as vb  # noqa: E402
import verslagsoorten as vs  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


# 1. Regressie bestaande soorten + registratie aankoopkeuring (X1/K1)
check("bestaande soorten aanwezig", all(k in vs.SOORTEN for k in (
    "werfverslag", "veiligheidscoordinatie", "plaatsbeschrijving", "barsten-scheuren", "aankoopkeuring")))
check("barsten-scheuren herkenning ongewijzigd", vs.herken({
    "firma": "UNABO", "soort": "KB", "type": "BS", "buiten": True,
    "titel": "Mehdi: !! [UNABO-KB] BS 46135 - Kerkstraat 1, Ternat", "locatie": "Kerkstraat 1, Ternat",
}) == "barsten-scheuren")
check("aankoopkeuring herkend op code AK", vs.herken({
    "firma": "UNABO", "soort": "KB", "type": "AK", "buiten": True,
    "titel": "Mehdi: !! [UNABO-KB] AK 1042 - Bondgenotenlaan 10, 3000 Leuven", "locatie": "Bondgenotenlaan 10, 3000 Leuven",
}) == "aankoopkeuring")
check("aankoopkeuring herkend op trefwoord aankoopbegeleiding", vs.herken({
    "firma": "UNABO", "soort": "KB", "type": "", "buiten": True,
    "titel": "Mehdi: !! [UNABO-KB] aankoopbegeleiding - Bondgenotenlaan 10, 3000 Leuven", "locatie": "Bondgenotenlaan 10, 3000 Leuven",
}) == "aankoopkeuring")
check("online afspraak krijgt geen aankoopkeuring-impuls", vs.herken({
    "firma": "UNABO", "soort": "KO", "type": "AK", "buiten": False,
    "titel": "Mehdi: [UNABO-KO] AK 1042 - Zoom", "locatie": "https://zoom.us/j/123",
}) is None)

# 2. Hoofdstukken en Deens/stedenbouwkundig kader (K3/K4/K5)
s_ak = vs.SOORTEN["aankoopkeuring"]
titels = [t for t, _ in s_ak["hoofdstukken"]]
check("zes vaste hoofdstukken in aankoopkeuring", len(titels) == 6, titels)
check("verplicht hoofdstuk niet-beoordeelde delen aanwezig", any("Niet-beoordeelde" in t for t in titels), titels)
check("hoofdstuk stedenbouwkundige planvergelijking aanwezig", any("Stedenbouwkundige" in t for t in titels), titels)

# 3. Schrijfregels S6 (geen eurobedragen/kostenramingen) en S7 (geen verjaring/garanties) op profiel aankoopkeuring
t, ing = S.toepassen(
    "Het plat dak vertoont blaasvorming (K2). De herstelkosten worden geraamd op 4.500 EUR tot 6.000 EUR.",
    profiel="aankoopkeuring",
)
check("S6 eurobedrag/kostenraming geschrapt in aankoopkeuring", "4.500" not in t and "schrijfregel S6" in t and "blaasvorming (K2)" in t, t)
t_std, ing_std = S.toepassen("De offerte bedraagt 4.500 EUR.")
check("S6 raakt standaard werfverslag niet", t_std == "De offerte bedraagt 4.500 EUR." and not ing_std, t_std)

for verboden_zin in (
    "De achterbouw uit 1998 is stedenbouwkundig verjaard.",
    "Deze uitbreiding is gegarandeerd regulariseerbaar bij de gemeente.",
    "De woning is volledig onderzocht van kelder tot dak.",
    "Het pand is vrij van verborgen gebreken.",
    "De verkoper was te kwader trouw over het vochtprobleem.",
):
    t7, ing7 = S.toepassen(verboden_zin, profiel="aankoopkeuring")
    check(f"S7 blokkeert '{verboden_zin[:38]}...'", "schrijfregel S7" in t7 and any(r == "S7" for r, _ in ing7), (t7, ing7))

goede_ak = (
    "Waarneming: de achterbouw op het gelijkvloers is 1,20 m dieper dan aangeduid op het voorgelegde plan van 1978. "
    "Bronfeit: op de luchtfoto van Geopunt (peildatum 2015) is het huidige volume zichtbaar. "
    "Oordeel: zichtbare afwijking t.o.v. voorgelegd plan (code UN); nader stedenbouwkundig onderzoek bij de gemeente vereist."
)
t_goed, ing_goed = S.toepassen(goede_ak, profiel="aankoopkeuring")
check("correcte waarneming/bronfeit/oordeel met code UN blijft intact", t_goed == goede_ak and not ing_goed, (t_goed, ing_goed))

# 4. _md() in verslag_basis.py past profiel aankoopkeuring toe zonder mutatie van invoer
voorbeeld_verslag = {
    "titel": "Technisch en stedenbouwkundig aankoopkeuringsverslag",
    "aanwezigen": [{"rol": "Onderzoeker", "firma": "UNABO", "naam": "Mehdi Chegini", "aanwezig": "ja"}],
    "hoofdstukken": [
        {"titel": "Niet-beoordeelde en ontoegankelijke delen", "tekst": "De kruipkelder was afgesloten.", "punten": []},
        {"titel": "Bouwkundige en stabiliteitsstaat (K0-K3 en UN)", "tekst": "", "punten": [
            {"nr": "3.1", "titel": "Plat dak achterbouw", "vlag": "K3",
             "tekst": "Zichtbare waterinsijpeling aan de dakrand (opname 00:14:20). Herstel kost € 3.200.",
             "fotos": ["IMG_001.jpg"]},
        ]},
        {"titel": "Stedenbouwkundige plan- en luchtfotovergelijking", "tekst": "", "punten": [
            {"nr": "4.1", "titel": "Veranda achtergevel", "vlag": "UN",
             "tekst": "Zichtbare afwijking t.o.v. voorgelegd plan (code UN). De overtreding is verjaard.",
             "fotos": []},
        ]},
    ],
    "acties": [],
    "open_punten": ["Vergunde plannen 1978 opvragen bij het gemeentearchief"],
}
rij = {"dossier": "AK-1042", "adres": "Bondgenotenlaan 10, 3000 Leuven", "klant": "Jan Peeters",
       "datum": "2026-10-23", "start": "2026-10-23T10:00:00+02:00", "einde": "2026-10-23T12:00:00+02:00",
       "bezoekmap": "/Work All/02. UNABO/01. U-WORK/09. U-AANKOOPKEURING/AK-1042 Bondgenotenlaan 10 Leuven/_00. Communication/2026-10-23 bezoek klant - aankoopkeuring"}
md = vb._md(voorbeeld_verslag, s_ak, rij)
check("_md schrapt opname (S4), eurobedrag (S6) en verjaard (S7)",
      "00:14:20" not in md and "3.200" not in md and "verjaard" not in md and "code UN" in md and "waterinsijpeling" in md, md)
check("_md muteert het invoer-dict niet", "3.200" in voorbeeld_verslag["hoofdstukken"][1]["punten"][0]["tekst"])

# 5. Eigen UNABO-nummering AK- buiten 46xxx in zoek_dossiermap (X5/K6)
nep_mappen = [
    {".tag": "folder", "name": "0. Structure", "path_display": "/Work All/02. UNABO/01. U-WORK/09. U-AANKOOPKEURING/0. Structure"},
    {".tag": "folder", "name": "AK-1042 Bondgenotenlaan 10, 3000 Leuven",
     "path_display": "/Work All/02. UNABO/01. U-WORK/09. U-AANKOOPKEURING/AK-1042 Bondgenotenlaan 10, 3000 Leuven"},
]
with patch.object(vb.bronnen, "lijst", side_effect=lambda pad, recursief=False: nep_mappen if "09. U-AANKOOPKEURING" in pad else []):
    ag = vb.VerslagAgent("aankoopkeuring")
    pad1, hoe1 = ag.zoek_dossiermap({"dossier": "AK-1042", "adres": "Bondgenotenlaan 10, 3000 Leuven", "klant": "Jan Peeters"})
    pad2, hoe2 = ag.zoek_dossiermap({"dossier": "1042", "adres": "Bondgenotenlaan 10, 3000 Leuven", "klant": "Jan Peeters"})
    check("zoek_dossiermap vindt AK-1042 met 'AK-1042'", pad1 and pad1.endswith("AK-1042 Bondgenotenlaan 10, 3000 Leuven"), (pad1, hoe1))
    check("zoek_dossiermap vindt AK-1042 met kaal nummer '1042'", pad2 == pad1, (pad2, hoe2))

# 6. Werkwijze voldoet aan AGENTNORM hoofdstuk 8 (bord.grenzen)
ww_pad = HIER / "werkwijze" / "aankoopkeuring-verslag.md"
ww_tekst = ww_pad.read_text(encoding="utf-8")
nooit, mehdi = bord.grenzen(ww_tekst)
check("werkwijze aankoopkeuring-verslag slaagt voor bord.grenzen()",
      bool(len(nooit or []) >= 5 and len(mehdi or []) >= 3), (nooit, mehdi))

print(f"{ok} ok, {fout} fout")
sys.exit(1 if fout else 0)

"""Grendel op de PDF van een verslag (verslag_pdf.py): foto's achteraan, twee per pagina, ook op de pagina met de kop.

Gevonden bij de review van PR 92 (26-10-2026): de kop "Foto's" en twee fotoblokken van 12,2 cm waren samen hoger dan
de bruikbare A4-hoogte (25,5 cm). Foto 2 schoof dan naar een eigen pagina en elke volgende foto begon weer op een
nieuwe pagina, met telkens een halve lege pagina. Deze toets rendert echt met weasyprint en telt met pypdf de pagina's
en de onderschriften per pagina: bij een korte tekst 1 tekstpagina plus ceil(n/2) fotopagina's, met foto 1+2, 3+4, 5.
Vereist weasyprint (in CI met de systeembibliotheken via apt; op de Mac DYLD_LIBRARY_PATH=/opt/homebrew/lib).
"""
import io
import math
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
import verslag_pdf  # noqa: E402
from PIL import Image  # noqa: E402
from pypdf import PdfReader  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


def _jpg(breed, hoog, kleur):
    buf = io.BytesIO()
    Image.new("RGB", (breed, hoog), kleur).save(buf, "JPEG", quality=70)
    return buf.getvalue()


# Liggend en staand door elkaar, zoals op de werf: een staande foto vult de volle hoogte van zijn blok.
LIGGEND, STAAND = _jpg(1600, 1200, (120, 140, 160)), _jpg(1200, 1600, (160, 140, 120))
MD = "# Werfverslag 3\n\n**CONCEPT**\n\n## Ruwbouw\n\n- 1.1 Muur: er staat een muur.\n"

for n in (1, 2, 3, 4, 5):
    fotos = [(f"1.{i} Muur", LIGGEND if i % 2 else STAAND) for i in range(1, n + 1)]
    pdf = PdfReader(io.BytesIO(verslag_pdf.naar_pdf(MD, "9999 | Werfverslag 3", fotos)))
    # Per pagina de onderschriften "Foto <n> <bijschrift>"; de kop staat in hoofdletters ("FOTO'S").
    teksten = [p.extract_text() for p in pdf.pages]
    per_pagina = [[int(x) for x in re.findall(r"^Foto (\d+) 1\.", t, re.M)] for t in teksten]
    verwacht = [[]] + [[i, i + 1] for i in range(1, n + 1, 2) if i < n] + ([[n]] if n % 2 else [])
    check(f"{n} foto's: {1 + math.ceil(n / 2)} pagina's", len(pdf.pages) == 1 + math.ceil(n / 2), f"kreeg {len(pdf.pages)}")
    check(f"{n} foto's: twee per pagina, ook naast de kop", per_pagina == verwacht, f"kreeg {per_pagina}, verwacht {verwacht}")
    check(f"{n} foto's: kop op de eerste fotopagina", len(teksten) > 1 and "FOTO'S" in teksten[1].upper(), teksten[1:2])

pdf = PdfReader(io.BytesIO(verslag_pdf.naar_pdf(MD, "9999 | Werfverslag 3", [])))
check("zonder foto's alleen de tekstpagina", len(pdf.pages) == 1, f"kreeg {len(pdf.pages)}")

h = verslag_pdf.md_naar_html("Er blijft water staan.\n\nHerkomst: V <!-- bron: transcript.txt 00:22:30 -->\n")
check("de bewaarde bron achter Herkomst komt niet in de PDF", "Herkomst: V" in h and "00:22" not in h and "bron:" not in h, h)

h = verslag_pdf.md_naar_html("Vaststellingen:\nspouwhaken ontbreken\nisolatie niet aansluitend\n\nVolgende alinea.")
check("regels van een alinea blijven aparte regels, zoals in Word",
      "<p>Vaststellingen:<br>spouwhaken ontbreken<br>isolatie niet aansluitend</p>" in h and "<p>Volgende alinea.</p>" in h, h)

# 33e review: een Engelse tekst over meer regels (tweetalig verslag) is in de PDF cursief per regel, zonder losse sterretjes
h = verslag_pdf.md_naar_html("*Shell works ongoing.\nRoof works start next week.*")
check("cursief over twee regels", h.strip() == "<p><em>Shell works ongoing.</em><br><em>Roof works start next week.</em></p>", h)
h = verslag_pdf.md_naar_html("*The sewer follows the plan:\n- rainwater and foul water separated\n- slopes 2 cm per metre*")
check("cursief met een opsomming", "*" not in h and "<li><em>slopes 2 cm per metre</em></li>" in h and "<em>The sewer follows the plan:</em>" in h, h)
h = verslag_pdf.md_naar_html("*a*\n\nTekst met *nadruk* hier.")
check("cursief over een lege regel heen verandert niets", "<p><em>a</em></p>" in h and "Tekst met <em>nadruk</em> hier." in h, h)
pdf = PdfReader(io.BytesIO(verslag_pdf.naar_pdf("# Werfverslag\n\n*Shell works ongoing.\nRoof works start next week.*\n", "9999 | Werfverslag 3", [])))
tekst = pdf.pages[0].extract_text()
check("geen sterretje in de PDF-tekst", "*" not in tekst and "Roof works start next week." in tekst, tekst)

print(f"{ok} ok, {fout} fout")
sys.exit(1 if fout else 0)

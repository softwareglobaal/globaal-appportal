"""PDF van een verslag (werfverslag, plaatsbezoek, verslag van bevindingen) in de huisstijl van H-Architects, uit de
markdown van de proef plus de foto's achteraan: dezelfde tekst als het Word-concept, zonder Word te openen.

Gemaakt op 23-10-2026 omdat Mehdi het concept als Word én als PDF van de bezoekpagina wil kunnen downloaden, zoals
in het contractendashboard. De omzetting gebeurt met weasyprint op de server (runner-venv); de HTML wordt hier uit
onze eigen markdown gebouwd (koppen, tabellen, lijsten, vet en cursief), zonder externe markdown-bibliotheek.

Huisstijl: Aptos (of de dichtstbijzijnde sans), hoofdstukken blauw 365F91, tussenkoppen 4F81BD, voettekst
"<nr> | <Titel> Pagina X". Foto's: achteraan, elk één keer, bijna halve pagina hoog, dus twee per pagina, ook op de
pagina met de kop.
"""
import base64
import html
import re

KLEUR_H1, KLEUR_H2, GRIJS = "#365F91", "#4F81BD", "#6B6B6B"

CSS = """
@page { size: A4; margin: 2cm 2cm 2.2cm 2cm;
  @bottom-left { content: "__VOET__"; font: 8.5pt Aptos, "Segoe UI", Arial, sans-serif; color: __GRIJS__; }
  @bottom-right { content: "Pagina " counter(page); font: 8.5pt Aptos, "Segoe UI", Arial, sans-serif; color: __GRIJS__; } }
body { font: 10.5pt/1.4 Aptos, "Segoe UI", Arial, sans-serif; color: #222; }
h1 { font-size: 16pt; color: __H1__; margin: 0 0 10pt 0; }
h2 { font-size: 12.5pt; color: __H1__; margin: 16pt 0 6pt 0; text-transform: uppercase; }
h3 { font-size: 11pt; color: __H2__; margin: 12pt 0 4pt 0; }
p { margin: 0 0 6pt 0; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 8pt 0; font-size: 9.5pt; }
th, td { border: 0.5pt solid #BFBFBF; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #EAF0F7; color: __H1__; }
ul { margin: 0 0 6pt 0; padding-left: 16pt; }
.concept { color: #B45309; font-weight: bold; }
/* Twee fotoblokken plus de kop "Foto's" passen binnen de bruikbare hoogte (29,7 - 2 - 2,2 = 25,5 cm). */
.foto { page-break-inside: avoid; height: 11.4cm; margin-bottom: 0.3cm; }
.foto img { max-height: 10.4cm; max-width: 100%; display: block; margin: 0 auto; }
.foto p { font-size: 9pt; color: __GRIJS__; margin: 2pt 0 0 0; text-align: center; }
.fotopagina { page-break-before: always; }
"""


def css_voor(voettekst):
    return (CSS.replace("__VOET__", voettekst.replace('"', "'").replace("\\", "/")).replace("__GRIJS__", GRIJS)
            .replace("__H1__", KLEUR_H1).replace("__H2__", KLEUR_H2))


def _inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t


def md_naar_html(md):
    """Onze eigen markdown (uit sjabloon_werfverslag en sjabloon_bevindingen) naar HTML."""
    uit, lijst, tabel, alinea = [], [], [], []

    def sluit_alinea():
        if alinea:
            uit.append("<p>" + " ".join(_inline(x) for x in alinea) + "</p>")
            alinea.clear()

    def sluit_lijst():
        if lijst:
            uit.append("<ul>" + "".join(f"<li>{_inline(x)}</li>" for x in lijst) + "</ul>")
            lijst.clear()

    def sluit_tabel():
        if tabel:
            rijen = [r for r in tabel if not re.fullmatch(r"\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?", r.strip())]
            cellen = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rijen]
            if cellen:
                kop = cellen[0]
                h = "<table>"
                if any(kop):
                    h += "<tr>" + "".join(f"<th>{_inline(c)}</th>" for c in kop) + "</tr>"
                for r in cellen[1:]:
                    h += "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>"
                uit.append(h + "</table>")
            tabel.clear()

    for regel in (md or "").splitlines():
        s = regel.rstrip()
        if s.startswith("|"):
            sluit_alinea(); sluit_lijst(); tabel.append(s); continue
        sluit_tabel()
        if not s.strip():
            sluit_alinea(); sluit_lijst(); continue
        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            sluit_alinea(); sluit_lijst()
            uit.append(f"<h{len(m.group(1))}>{_inline(m.group(2))}</h{len(m.group(1))}>")
            continue
        m = re.match(r"^\s*[-*]\s+(.*)$", s)
        if m:
            sluit_alinea(); lijst.append(m.group(1)); continue
        sluit_lijst()
        alinea.append(s.strip())
    sluit_alinea(); sluit_lijst(); sluit_tabel()
    h = "\n".join(uit)
    return h.replace("<p><strong>CONCEPT</strong>", "<p class=\"concept\"><strong>CONCEPT</strong>")


def _mime(b):
    if b[:4] == b"\x89PNG":
        return "image/png"
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    return "application/octet-stream"


def fotos_html(fotos):
    """fotos: [(bijschrift, bytes)] in de volgorde van het Word-concept; twee per pagina, foto n = volgnummer."""
    if not fotos:
        return ""
    delen = ["<h2 class=\"fotopagina\">Foto's</h2>"]
    for i, (bijschrift, b) in enumerate(fotos, 1):
        if i > 1 and i % 2 == 1:
            delen.append("<div class=\"fotopagina\"></div>")
        src = f"data:{_mime(b)};base64,{base64.b64encode(b).decode('ascii')}"
        delen.append(f"<div class=\"foto\"><img src=\"{src}\" alt=\"foto {i}\"><p>Foto {i} {html.escape(bijschrift or '')}</p></div>")
    return "\n".join(delen)


def naar_html(md, voettekst, fotos=()):
    return ("<!doctype html><html lang=\"nl\"><head><meta charset=\"utf-8\"><title>" + html.escape(voettekst) + "</title><style>"
            + css_voor(voettekst) + "</style></head><body>" + md_naar_html(md) + fotos_html(list(fotos))
            + "</body></html>")


def naar_pdf(md, voettekst, fotos=()):
    """PDF-bytes. fotos: [(bijschrift, bytes)]. Vereist weasyprint (op de server in de runner-venv)."""
    from weasyprint import HTML
    return HTML(string=naar_html(md, voettekst, fotos)).write_pdf()


def fotolijst_werfverslag(verslag, beelden):
    """[(bijschrift, bytes)] in de volgorde van sjabloon_werfverslag.naar_docx: eerste verwijzing per foto."""
    gezien, uit = set(), []
    for cat in verslag.get("categorieen", []):
        for pt in cat.get("punten", []):
            for b in pt.get("fotos", []):
                if b in beelden and b not in gezien:
                    gezien.add(b)
                    uit.append((f"{pt.get('nummer', '')} {pt.get('titel', '')}".strip(), beelden[b]))
    return uit

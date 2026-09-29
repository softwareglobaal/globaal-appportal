#!/usr/bin/env python3
"""De Contactwacht - regels en stand, als PDF.

Draait op de Mac (Chrome maakt de PDF) en leest werkwijze/contactwacht.md uit de repo. Dat is
dezelfde tekst die op het bord de werkwijze van De Contactwacht is, zodat de PDF daar nooit van
afwijkt. Uitvoer: Dropbox 'private/0 Chegini Mehdi/Prive met Claude'. De versie komt uit de
eerste regel met "Versie" in de werkwijze.
"""
import html
import pathlib
import re
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]
BRON = REPO / "werkwijze" / "contactwacht.md"
UIT = pathlib.Path.home() / "TKN-buro Dropbox/private/0 Chegini Mehdi/Prive met Claude"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

tekst = BRON.read_text(encoding="utf-8")
versie = re.search(r"Versie (\d+\.\d+)", tekst).group(1)
NAAM = f"De Contactwacht - regels en stand v{versie}"


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return s


def naar_html(md):
    """Een kleine omzetting voor deze ene tekst: koppen, alinea's, lijsten en tabellen."""
    uit, alinea, lijst, tabel = [], [], None, []

    def sluit():
        nonlocal lijst, tabel
        if alinea:
            uit.append("<p>" + inline(" ".join(alinea)) + "</p>")
            alinea.clear()
        if lijst:
            uit.append(f"</{lijst}>")
            lijst = None
        if tabel:
            kop, *rijen = [r for r in tabel if not re.fullmatch(r"\|[\s\-:|]+\|", r)]
            cel = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]
            uit.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in cel(kop)) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cel(r)) + "</tr>" for r in rijen)
                       + "</tbody></table>")
            tabel.clear()

    for regel in md.splitlines():
        r = regel.rstrip()
        if not r:
            sluit()
            continue
        if r.startswith("|"):
            if alinea or lijst:
                sluit()
            tabel.append(r)
            continue
        if tabel:
            sluit()
        m = re.match(r"(#{1,3}) (.*)", r)
        if m:
            sluit()
            n = len(m.group(1))
            uit.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
            continue
        m = re.match(r"(- |\d+\. )(.*)", r)
        if m:
            soort = "ul" if m.group(1) == "- " else "ol"
            if alinea:
                sluit()
            if lijst != soort:
                if lijst:
                    uit.append(f"</{lijst}>")
                uit.append(f"<{soort}>")
                lijst = soort
            uit.append(f"<li>{inline(m.group(2))}</li>")
            continue
        if lijst and regel.startswith("  "):
            uit[-1] = uit[-1][:-5] + " " + inline(r.strip()) + "</li>"
            continue
        alinea.append(r.strip())
    sluit()
    return "\n".join(uit)


HTML = f"""<!doctype html><html lang=nl><meta charset=utf-8><title>{NAAM}</title>
<style>
@page{{size:A4;margin:14mm}}
body{{font:9.7pt/1.45 -apple-system,"Helvetica Neue",Arial,sans-serif;color:#14181f}}
h1{{font-size:17pt;margin:0 0 2mm}} h2{{font-size:11.8pt;margin:7mm 0 2mm;border-bottom:1.5px solid #14181f;padding-bottom:1mm;break-after:avoid}}
h3{{font-size:10pt;margin:4mm 0 1.5mm;break-after:avoid}}
p{{margin:0 0 2.6mm}} ul,ol{{margin:0 0 3mm;padding-left:5mm}} li{{margin-bottom:1.2mm}}
code{{font:8.6pt ui-monospace,Menlo,monospace;background:#eef1f5;padding:.3mm 1.2mm}}
table{{border-collapse:collapse;width:100%;font-size:8.7pt;margin-bottom:3mm}}
th{{text-align:left;border-bottom:1px solid #14181f;padding:1.3mm 2mm}}
td{{border-bottom:.4px solid #d6dae1;padding:1.4mm 2mm;vertical-align:top}}
tr{{break-inside:avoid}}
.top{{color:#5d6673;font-size:8pt;margin-bottom:3mm}}
</style>
<div class=top>Voor Mehdi Chegini en Siyan &nbsp;|&nbsp; versie {versie} &nbsp;|&nbsp;
dezelfde tekst staat op mijnagents.globaal.be als werkwijze van De Contactwacht</div>
{naar_html(tekst)}
</html>"""
assert "—" not in HTML and "–" not in HTML, "gedachtestreepje in de PDF"

h = pathlib.Path("/tmp/contactwacht-regels.html")
h.write_text(HTML, encoding="utf-8")
pdf = UIT / f"{NAAM}.pdf"
subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={pdf}", f"file://{h}"], capture_output=True, timeout=180, check=True)
print("pdf:", pdf, pdf.stat().st_size, "bytes")

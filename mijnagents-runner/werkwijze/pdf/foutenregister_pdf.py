#!/usr/bin/env python3
"""Agendawacht - foutenregister als PDF, uit werkwijze/foutenregister.json.

Draait op de Mac (Chrome maakt de PDF) en leest rechtstreeks uit de repo, zodat de PDF nooit
afwijkt van het systeem. Uitvoer: Dropbox 'private/0 Chegini Mehdi/Prive met Claude'.
"""
import html
import json
import pathlib
import subprocess
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[2]
UIT = pathlib.Path.home() / "TKN-buro Dropbox/private/0 Chegini Mehdi/Prive met Claude"
reg = json.loads((REPO / "werkwijze/foutenregister.json").read_text(encoding="utf-8"))
NAAM = f"Agendawacht - foutenregister v{reg['versie']}"
e = html.escape
F = {f["id"]: f for f in reg["fouten"]}
STATUS = {"opgelost": ("#0b8043", "opgelost"), "bewaakt": ("#039be5", "bewaakt"), "open": ("#f4511e", "open"), "vraag": ("#f6bf26", "vraag aan Mehdi")}


def label(s):
    kl, t = STATUS[s]
    return f"<span class=lab style='border-color:{kl};color:{kl}'>{e(t)}</span>"


tel_status = Counter(f["status"] for f in reg["fouten"])
tel_oorzaak = Counter(f.get("soort_oorzaak", "") for f in reg["fouten"])
tel_door = Counter(("Mehdi" if f["gevonden_door"] == "Mehdi" else "Claude" if f["gevonden_door"] == "Claude" else "zelfcontrole")
                   for f in reg["fouten"])
week = [f for f in reg["fouten"] if f["datum"] == "24-09-2026" and "zelfcontrole" in f["gevonden_door"]]

stappen = "".join(f"<li>{e(s)}</li>" for s in reg["hoe_het_leert"])
lessen = "".join(f"<tr><td class=nr>{e(l['id'])}</td><td>{e(l['les'])}</td><td class=kl>{e(', '.join(l['uit']))}</td></tr>" for l in reg["lessen"])
tabel = lambda c: "".join(f"<tr><td>{e(k)}</td><td class=c>{v}</td></tr>" for k, v in c.most_common())
controles = "".join(f"<tr><td><code>{e(c)}</code></td><td class=c>{e(f['id'])}</td><td>{e(f['fout'][:120])}</td><td>{label(f['status'])}</td></tr>"
                    for f in reg["fouten"] for c in f.get("controle") or [])


def kaart(f):
    g = f["grendel"]
    return f"""<div class=kaart><div class=kop><b>{e(f['id'])}</b> &nbsp; {e(f['datum'])} &nbsp;·&nbsp; gevonden door {e(f['gevonden_door'])}
<span style="float:right">{label(f['status'])}</span></div>
<div class=fout>{e(f['fout'])}</div>
<table><tbody>
<tr><td class=k>Gevolg</td><td>{e(f['gevolg'])}</td></tr>
<tr><td class=k>Waarom niet eerder gezien</td><td>{e(f['waarom_niet_gezien'])}</td></tr>
<tr><td class=k>Oorzaak</td><td>{e(f['oorzaak'])} <span class=kl>({e(f.get('soort_oorzaak', ''))})</span></td></tr>
<tr><td class=k>Oplossing</td><td>{e(f['oplossing'])}</td></tr>
<tr><td class=k>Grendel</td><td class=kl>{e(g['soort'])} in <code>{e(g['waar'])}</code>: {e(g['tekst'])}</td></tr>
</tbody></table></div>"""


kaarten_week = "".join(kaart(f) for f in week)
kaarten_rest = "".join(kaart(f) for f in reg["fouten"] if f not in week)

HTML = f"""<!doctype html><html lang=nl><meta charset=utf-8><title>{NAAM}</title>
<style>
@page{{size:A4;margin:14mm}}
body{{font:9.6pt/1.45 -apple-system,"Helvetica Neue",Arial,sans-serif;color:#14181f}}
h1{{font-size:17pt;margin:0 0 2mm}} h2{{font-size:11.8pt;margin:7mm 0 2mm;border-bottom:1.5px solid #14181f;padding-bottom:1mm;break-after:avoid}}
p{{margin:0 0 2.6mm}} ol,ul{{margin:0 0 3mm;padding-left:5mm}} li{{margin-bottom:1.2mm}}
code{{font:8.4pt ui-monospace,Menlo,monospace;background:#eef1f5;padding:.3mm 1.1mm}}
table{{border-collapse:collapse;width:100%;font-size:8.7pt;margin-bottom:2mm}}
th{{text-align:left;border-bottom:1px solid #14181f;padding:1.3mm 2mm}}
td{{border-bottom:.4px solid #d6dae1;padding:1.2mm 2mm;vertical-align:top}}
tr{{break-inside:avoid}}
.nr{{text-align:center;font-weight:700;width:9mm}} .c{{text-align:center;white-space:nowrap}}
.kl{{color:#5d6673;font-size:7.9pt}} .k{{width:38mm;color:#5d6673;font-size:8.2pt}}
.kader{{border:1px solid #14181f;padding:3mm 4mm;margin:0 0 4mm;background:#f7f8fa}}
.top{{color:#5d6673;font-size:8pt;margin-bottom:3mm}}
.kaart{{border:.6px solid #b8bfca;padding:2.2mm 3mm 1mm;margin:0 0 3mm;break-inside:avoid}}
.kaart .kop{{font-size:8.4pt;color:#5d6673;margin-bottom:1mm}} .kaart .kop b{{color:#14181f;font-size:10pt}}
.kaart .fout{{font-weight:600;margin-bottom:1mm}}
.lab{{border:1px solid;border-radius:2mm;padding:.2mm 2mm;font-size:7.6pt;font-weight:600;white-space:nowrap}}
.drie{{display:flex;gap:6mm}} .drie>div{{flex:1}}
</style>
<div class=top>Voor Mehdi Chegini &nbsp;|&nbsp; {e(reg['datum'])} &nbsp;|&nbsp; versie {e(reg['versie'])} &nbsp;|&nbsp;
bron: werkwijze/foutenregister.json op de server &nbsp;|&nbsp; hoort bij 'Agendawacht - afspraken kleuren en taken v2.0'</div>
<h1>Het foutenregister van de Agendawacht</h1>

<div class=kader>{e(reg['doel'])}<br><br>
Dit register staat bewust apart van de afspraken. De afspraken zeggen hoe het nu werkt; het register zegt wat er fout ging, waarom
niemand het eerder zag, en wat het voortaan tegenhoudt. Het is ook geen dagboek: een fout staat er een keer in, met haar grendel.</div>

<h2>1. Hoe het systeem van zijn fouten leert</h2>
<ol>{stappen}</ol>

<h2>2. De week van 21 tot 27 september, nagekeken</h2>
<p>Op 24 september keek de weekcontrole in de agenda zelf, niet in het logboek: alle zeven agenda's, 87 afspraken van maandag tot
zondag, en ter controle ook de week erna (131 afspraken in totaal). Daaruit kwamen {len(week)} nieuwe fouten, hieronder in deel 5.
Na de reparatie en een nieuwe ronde van de agent gaf de zelfcontrole: <b>0 teruggekeerd, 0 nieuw</b>. Wat overblijft zijn vragen
aan Mehdi: kleuren die met de hand gezet werden, oude codes uit de Calendly-sjablonen, en een afspraak die nog op ?? staat.</p>
<p><b>Waarom ik deze fouten niet eerder zag.</b> Het komt neer op vijf dingen:</p>
<ol>
<li><b>Ik las het logboek van de agent, niet de agenda.</b> Het logboek zei '0 mislukt', '13 weggehaald', '122 van 100'. Wat er echt stond,
bekeek niemand. (FR-11, FR-17, FR-20, FR-25, FR-37)</li>
<li><b>De agent kijkt alleen vooruit.</b> Wat gisteren fout liep, zag niemand: een ?? die bleef staan, een rit op de verkeerde agenda.
(FR-26, FR-28, FR-31)</li>
<li><b>De server loopt op een andere klok.</b> '06:30' in cron is 08:30 in Brussel. (FR-18, FR-19)</li>
<li><b>Ik zette zelf een grendel open om sneller te zijn.</b> Het Google-plafond, twee keer. (FR-01, FR-17)</li>
<li><b>Regels die elkaar raken, werden los gebouwd.</b> Een rit die te laat aankomt, een handmatige rit tussen twee stappen, een kleur
zonder herkomst. (FR-20, FR-24, FR-37, FR-38)</li>
</ol>
<p>Daarom bestaan nu de zelfcontrole, die elke werkdag om 07:00 in de agenda zelf kijkt, en de test op dit register.</p>

<h2>3. De lessen</h2>
<table><thead><tr><th>#</th><th>Les</th><th style="width:30mm">Uit</th></tr></thead><tbody>{lessen}</tbody></table>

<h2>4. In cijfers</h2>
<div class=drie>
<div><b>Status</b><table><tbody>{tabel(tel_status)}</tbody></table></div>
<div><b>Soort oorzaak</b><table><tbody>{tabel(tel_oorzaak)}</tbody></table></div>
<div><b>Gevonden door</b><table><tbody>{tabel(tel_door)}</tbody></table></div>
</div>
<p class=kl>'Werkwijze van Claude' zijn fouten in hoe ik werkte, niet in de code: vragen voor meten, een grendel openzetten, bouwen zonder git log.</p>

<h2>5. De fouten van de weekcontrole (24 september)</h2>
{kaarten_week}

<h2>6. Eerdere fouten en bewaakte regels (20 tot 23 september)</h2>
{kaarten_rest}

<h2>7. Wat de zelfcontrole elke ochtend nakijkt</h2>
<table><thead><tr><th>Controle</th><th>Fout</th><th>Wat</th><th>Status</th></tr></thead><tbody>{controles}</tbody></table>
<p class=kl>Een controle die iets vindt bij een fout met status 'opgelost', meldt TERUGGEKEERD bovenaan op het bord. Een bevinding die bij
geen enkele fout hoort, meldt NIEUW: die komt eerst in dit register.</p>
</html>"""
assert "Surinam" not in HTML
h = pathlib.Path("/tmp/foutenregister.html")
h.write_text(HTML, encoding="utf-8")
pdf = UIT / f"{NAAM}.pdf"
subprocess.run(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--headless", "--disable-gpu",
                "--no-pdf-header-footer", f"--print-to-pdf={pdf}", f"file://{h}"], capture_output=True, timeout=180, check=True)
print("pdf:", pdf.name, pdf.stat().st_size)

"""Het eigen werfverslag-sjabloon van H-Architects, geleerd uit de Archisnapper-verslagen
(H-Architects bvba/Apps/Archisnapper, 1094 verslagen 2019-2024) en hoofdstuk E6 van de vaste afspraken.

Opbouw (identiek in Word en in markdown):
  kop        firma, "Werfverslag N voor project <nr> <adres>", nummer <nr>-N, datum, CONCEPT-regel
  status     status van de werf (een of twee zinnen; NL en optioneel EN)
  aanwezigen tabel Rol [firma] | Naam | Contact | Aanwezig
  vast       veiligheid en tienjarige aansprakelijkheid (vaste tekst)
  waarnemingen per categorie (Algemeen, Veiligheidscoördinatie, EPB, Afbraak, Ruwbouw, Dakwerken, Buitenschrijnwerk,
             Technieken, Binnenafwerking, Buitenwerk, Riolering, ...), genummerd <verslag>.<punt>, met datum, vlag
             (OK | Belangrijk | Dringend), tekst NL (+EN), verantwoordelijke en foto's
  doorlopend de vaste punten uit verslag 1 (omgevingsloket, werfbezoeken, orde en netheid, facturatie,
             veiligheidscoördinatie, EPB) worden in elk verslag herhaald tot ze OK zijn
  raming     alleen bij een vaststellingsverslag (schade): tabel onderdeel | herstelling | raming
  acties     tabel wie | wat | tegen
  volgend    volgend werfbezoek
  voorwaarden vijf kalenderdagen
  akkoord    tabel partij | naam | handtekening | datum

Invoer: een dict `verslag` (zie SCHEMA in werfverslag_proef.py). Foto's: lijst van (bijschrift, bytes).
"""
import io
import re
from datetime import date

FIRMA = {"naam": "H-Architects BV", "adres": "Herfstlaan 65, 3010 Kessel-Lo", "btw": "BE 0646.974.162",
         "mail": "light@h-architects.be"}

VAST_VEILIGHEID = ("Veiligheid: het veiligheids- en gezondheidsplan van de veiligheidscoördinator is van toepassing tijdens de "
                   "hele duur van de werken. De planning van de werken wordt tijdig aan de veiligheidscoördinator bezorgd.")
VAST_TIENJARIG = ("Tienjarige aansprakelijkheid: de verzekeringsattesten voor de tienjarige burgerlijke aansprakelijkheid "
                  "volgens de wet Peeters-Borsus (31 mei 2017, BS 9 juni 2017) worden aangeleverd door alle aannemers die een "
                  "aandeel hebben in de constructie tot de wind- en waterdichte staat van de werken.")
VAST_VOORWAARDEN = ("Zonder tegenbericht per e-mail binnen de vijf kalenderdagen wordt aangenomen dat alle partijen akkoord "
                    "gaan met dit verslag. Vragen of opmerkingen kunnen per e-mail worden bezorgd aan H-Architects.")

# Doorlopende punten uit verslag 1 (Archisnapper 1.1 tot 1.6), in elk verslag herhaald tot OK.
DOORLOPEND = [
    ("Algemeen", "Start- en einddatum van de werken",
     "De bouwheer vult de start- en einddatum van de werken in het omgevingsloket in. Volgens de vergunning starten de "
     "werken binnen 2 jaar na de vergunning en is het gebouw binnen 5 jaar wind- en waterdicht.", "Bouwheer"),
    ("Algemeen", "Werfbezoeken",
     "Werfbezoeken gebeuren volgens de architectenovereenkomst en zijn op oproep beschikbaar. Voor kritieke handelingen die "
     "achteraf niet te inspecteren zijn (wapening en dergelijke) bezorgt de aannemer foto's ter verificatie. Werfinspecties "
     "betreffen altijd de zichtbare staat van het pand; foto's genomen buiten de aanwezigheid van de architect worden gedeeld.",
     "Aannemer, bouwheer"),
    ("Algemeen", "Orde en netheid",
     "Elke aannemer houdt de werf net en ordelijk en voert puin en afval van zijn werken snel af; netheid is een "
     "veiligheidszaak.", "Aannemers"),
    ("Algemeen", "Facturatie",
     "De bouwheer deelt alle facturen en werkelijke kosten van de werken met het architectenbureau, zodat de erelonen "
     "volgens het contract correct worden afgerekend. Bijkomende werken buiten de oorspronkelijke opdracht tellen mee bij "
     "de herberekening als de architect ze opvolgt.", "Bouwheer"),
    ("Veiligheidscoördinatie", "Veiligheidscoördinatie",
     "De veiligheidscoördinator houdt toezicht en levert verslagen. Elke aannemer ontvangt het VGP, bewaart het op de werf en "
     "leeft het na; de hoofdaannemer informeert de onderaannemers. Valbescherming, leuningen, correct laddergebruik en "
     "nagelverwijdering zijn verplicht. De architect is niet aansprakelijk voor slecht verankerde stellingen of het niet "
     "naleven van het VGP; werfinspecties zijn momentopnames.", "Aannemers"),
    ("EPB", "EPB-eisen",
     "Alle eisen van het EPB-verslag worden gevolgd (isolatiewaarden, ventilatie, raamwaarden). De aannemer levert facturen, "
     "technische fiches en Uw-rapporten; de bouwheer fotografeert elke werkstap die fotobewijs vraagt en bezorgt op het einde "
     "alles aan de EPB-verslaggever voor de eindverklaring.", "Aannemer, bouwheer"),
]

VLAG = {"ok": "OK", "belangrijk": "Belangrijk", "dringend": "Dringend", "": ""}


def datum_nl(iso):
    try:
        j, m, d = iso[:10].split("-")
        maanden = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"]
        return f"{int(d)} {maanden[int(m) - 1]} {j}"
    except (ValueError, IndexError):
        return iso


# ------------------------------------------------------------------ markdown ---
def naar_markdown(v):
    r = []
    nr, n = v["dossier"], v["bezoek"]
    r.append(f"# Werfverslag {n} voor project {nr} {v['adres']}")
    r.append("")
    r.append(f"**CONCEPT** - opgemaakt op {v['opgemaakt']} door De Werfverslagschrijver uit {v.get('bronnen_kort', 'de bezoekmap')}. "
             "Na te kijken en aan te vullen door Mehdi Chegini vóór verzending.")
    r.append("")
    r.append("| | |\n|---|---|")
    r.append(f"| Verslagnummer | {nr}-{n} |")
    r.append(f"| Datum werfbezoek | {datum_nl(v['datum'])} |")
    r.append(f"| Verslagtype | {v.get('verslagtype', 'werfverslag')} |")
    r.append(f"| Opgemaakt door | {FIRMA['naam']}, {FIRMA['adres']}, {FIRMA['btw']} |")
    r.append("")
    r.append("## Status werf")
    r.append(v.get("status_nl") or "(in te vullen)")
    if v.get("status_en"):
        r.append("")
        r.append(f"*{v['status_en']}*")
    r.append("")
    r.append("## Contactpersonen en aanwezigen")
    r.append("| Rol | Firma | Naam | Contact | Aanwezig |\n|---|---|---|---|---|")
    for a in v.get("aanwezigen", []):
        r.append(f"| {a.get('rol','')} | {a.get('firma','')} | {a.get('naam','')} | {a.get('contact','')} | {a.get('aanwezig','')} |")
    r.append("")
    r.append(VAST_VEILIGHEID)
    r.append("")
    r.append(VAST_TIENJARIG)
    r.append("")
    r.append("## Waarnemingen")
    for cat in v.get("categorieen", []):
        r.append(f"### {cat['naam']}")
        for p in cat.get("punten", []):
            vlag = VLAG.get((p.get("vlag") or "").lower(), "")
            kop = f"**{p['nummer']} {p['titel']}** - {datum_nl(p.get('datum', v['datum']))}" + (f" - {vlag}" if vlag else "")
            r.append(kop)
            r.append("")
            r.append(p.get("tekst_nl", ""))
            if p.get("tekst_en"):
                r.append("")
                r.append(f"*{p['tekst_en']}*")
            if p.get("verantwoordelijke"):
                r.append("")
                r.append(f"Verantwoordelijke: {p['verantwoordelijke']}")
            if p.get("fotos"):
                r.append("")
                r.append("Foto's: " + ", ".join(p["fotos"]))
            r.append("")
    if v.get("raming"):
        r.append("## Raming van de herstelkosten")
        r.append("| Onderdeel | Herstelling | Raming |\n|---|---|---|")
        for x in v["raming"]:
            r.append(f"| {x.get('onderdeel','')} | {x.get('herstelling','')} | {x.get('raming','(raming door de architect in te vullen)')} |")
        r.append("")
    r.append("## Actiepunten")
    if v.get("acties"):
        r.append("| Wie | Wat | Tegen |\n|---|---|---|")
        for a in v["acties"]:
            r.append(f"| {a.get('wie','')} | {a.get('wat','')} | {a.get('tegen','')} |")
    else:
        r.append("geen")
    r.append("")
    r.append("## Volgend werfbezoek")
    r.append(v.get("volgend") or "(in te vullen)")
    r.append("")
    r.append("## Algemene voorwaarden")
    r.append(VAST_VOORWAARDEN)
    r.append("")
    r.append("## Voor akkoord")
    r.append("| Partij | Naam | Handtekening | Datum |\n|---|---|---|---|")
    for a in v.get("akkoord", []):
        r.append(f"| {a.get('partij','')} | {a.get('naam','')} | | |")
    r.append("")
    r.append(f"Opgemaakt en verzonden door de architect op: (in te vullen)")
    return "\n".join(r) + "\n"


# ---------------------------------------------------------------------- docx ---
def naar_docx(v, fotos=None):
    """fotos: dict bijschrift -> bytes (jpg/png). Een punt met p['fotos'] = [bijschrift, ...] krijgt ze eronder."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, RGBColor
    fotos = fotos or {}
    doc = Document()
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2)
        s.top_margin = s.bottom_margin = Cm(1.8)
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10)
    nr, n = v["dossier"], v["bezoek"]

    def kop(tekst, niveau=1):
        h = doc.add_heading(tekst, level=niveau)
        for run in h.runs:
            run.font.color.rgb = RGBColor(0x1F, 0x3D, 0x33)
        return h

    def tabel(koppen, rijen, breedtes=None):
        t = doc.add_table(rows=1, cols=len(koppen))
        t.style = "Table Grid"
        for i, k in enumerate(koppen):
            c = t.rows[0].cells[i]
            c.text = ""
            run = c.paragraphs[0].add_run(k)
            run.bold = True
            run.font.size = Pt(9)
        for rij in rijen:
            cellen = t.add_row().cells
            for i, val in enumerate(rij):
                cellen[i].text = ""
                cellen[i].paragraphs[0].add_run(str(val or "")).font.size = Pt(9)
        if breedtes:
            for rij in t.rows:
                for i, b in enumerate(breedtes):
                    rij.cells[i].width = Cm(b)
        doc.add_paragraph()
        return t

    # kop
    p = doc.add_paragraph()
    r = p.add_run(FIRMA["naam"]); r.bold = True; r.font.size = Pt(12)
    p.add_run(f"\n{FIRMA['adres']}\n{FIRMA['btw']}").font.size = Pt(9)
    kop(f"Werfverslag {n} voor project {nr} {v['adres']}", 0)
    p = doc.add_paragraph()
    p.add_run("CONCEPT").bold = True
    p.add_run(f" - opgemaakt op {v['opgemaakt']} door De Werfverslagschrijver uit {v.get('bronnen_kort', 'de bezoekmap')}. "
              "Na te kijken en aan te vullen door Mehdi Chegini vóór verzending.").italic = True
    tabel(["", ""], [["Verslagnummer", f"{nr}-{n}"], ["Datum werfbezoek", datum_nl(v["datum"])],
                     ["Verslagtype", v.get("verslagtype", "werfverslag")], ["Opgemaakt door", FIRMA["naam"]]], [4, 12.5])
    # status
    kop("Status werf")
    doc.add_paragraph(v.get("status_nl") or "(in te vullen)")
    if v.get("status_en"):
        doc.add_paragraph(v["status_en"]).runs[0].italic = True
    # aanwezigen
    kop("Contactpersonen en aanwezigen")
    tabel(["Rol", "Firma", "Naam", "Contact", "Aanwezig"],
          [[a.get("rol", ""), a.get("firma", ""), a.get("naam", ""), a.get("contact", ""), a.get("aanwezig", "")] for a in v.get("aanwezigen", [])],
          [3, 3.5, 3.5, 4.5, 2])
    for t in (VAST_VEILIGHEID, VAST_TIENJARIG):
        doc.add_paragraph(t).runs[0].font.size = Pt(8.5)
    # waarnemingen
    kop("Waarnemingen")
    for cat in v.get("categorieen", []):
        kop(cat["naam"], 2)
        for pt in cat.get("punten", []):
            vlag = VLAG.get((pt.get("vlag") or "").lower(), "")
            p = doc.add_paragraph()
            p.add_run(f"{pt['nummer']}  {pt['titel']}").bold = True
            p.add_run(f"   {datum_nl(pt.get('datum', v['datum']))}").font.size = Pt(8.5)
            if vlag:
                rr = p.add_run(f"   {vlag}")
                rr.bold = True
                rr.font.color.rgb = RGBColor(0x1F, 0x6B, 0x3D) if vlag == "OK" else RGBColor(0xA3, 0x3A, 0x2A)
            doc.add_paragraph(pt.get("tekst_nl", ""))
            if pt.get("tekst_en"):
                doc.add_paragraph(pt["tekst_en"]).runs[0].italic = True
            if pt.get("verantwoordelijke"):
                q = doc.add_paragraph()
                q.add_run("Verantwoordelijke: ").font.size = Pt(8.5)
                q.add_run(pt["verantwoordelijke"]).font.size = Pt(8.5)
            beelden = [(b, fotos[b]) for b in pt.get("fotos", []) if b in fotos]
            if beelden:
                t = doc.add_table(rows=0, cols=2)
                for i in range(0, len(beelden), 2):
                    cellen = t.add_row().cells
                    for j, (bijschrift, data) in enumerate(beelden[i:i + 2]):
                        par = cellen[j].paragraphs[0]
                        try:
                            par.add_run().add_picture(io.BytesIO(data), width=Cm(8))
                        except Exception:  # noqa: BLE001
                            par.add_run(f"(foto {bijschrift} niet leesbaar)")
                        cellen[j].add_paragraph(bijschrift).runs[0].font.size = Pt(8)
                doc.add_paragraph()
    # raming
    if v.get("raming"):
        kop("Raming van de herstelkosten")
        tabel(["Onderdeel", "Herstelling", "Raming"],
              [[x.get("onderdeel", ""), x.get("herstelling", ""), x.get("raming", "(raming door de architect in te vullen)")] for x in v["raming"]],
              [4, 8.5, 4])
    # acties
    kop("Actiepunten")
    if v.get("acties"):
        tabel(["Wie", "Wat", "Tegen"], [[a.get("wie", ""), a.get("wat", ""), a.get("tegen", "")] for a in v["acties"]], [4, 9.5, 3])
    else:
        doc.add_paragraph("geen")
    kop("Volgend werfbezoek")
    doc.add_paragraph(v.get("volgend") or "(in te vullen)")
    kop("Algemene voorwaarden")
    doc.add_paragraph(VAST_VOORWAARDEN)
    kop("Voor akkoord")
    tabel(["Partij", "Naam", "Handtekening", "Datum"], [[a.get("partij", ""), a.get("naam", ""), "", ""] for a in v.get("akkoord", [])], [4, 5.5, 4, 3])
    doc.add_paragraph("Opgemaakt en verzonden door de architect op: (in te vullen)")
    # voettekst
    for s in doc.sections:
        f = s.footer.paragraphs[0]
        f.text = f"Verslag opgemaakt door {FIRMA['naam']} - {nr}-{n} - CONCEPT"
        f.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in f.runs:
            run.font.size = Pt(8)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def telling_open(md):
    """Hoeveel plekken Mehdi nog moet invullen of nakijken: de nacontrole van de proef (W11)."""
    return {"in_te_vullen": len(re.findall(r"\(in te vullen\)", md)), "na_te_kijken": len(re.findall(r"\(na te kijken\)", md)),
            "raming_open": len(re.findall(r"raming door de architect", md))}

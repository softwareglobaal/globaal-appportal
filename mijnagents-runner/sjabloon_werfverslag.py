"""Het eigen werfverslag-sjabloon van H-Architects, geleerd uit de Archisnapper-verslagen
(H-Architects bvba/Apps/Archisnapper, 1094 verslagen 2019-2024) en hoofdstuk E6 van de vaste afspraken.
De Word-opmaak volgt de contractmasters van het contractsysteem (Master_Architectuurovereenkomst.docx,
kopie `sjabloon_HA_master.docx` naast dit bestand): lettertype Aptos 11 pt, "Projectnummer:" vet, titel 16 pt vet,
hoofdstukken genummerd in hoofdletters, vet, blauw 365F91 (12 pt), onderdelen vet blauw 4F81BD, voettekst
"<nr> | Werfverslag N   Pagina X", A4 met dezelfde marges.

Opbouw (identiek in Word en in markdown):
  kop        Projectnummer, titel "Werfverslag N: <adres>", CONCEPT-regel, gegevenstabel
  status     status van de werf (NL en optioneel EN)
  aanwezigen tabel Rol | Firma | Naam | Contact | Aanwezig
  vast       veiligheid en tienjarige aansprakelijkheid (vaste tekst)
  waarnemingen per categorie, genummerd <verslag>.<punt>, met datum, vlag (OK | Belangrijk | Dringend),
             tekst NL (+EN), verantwoordelijke en foto's
  raming     alleen bij een vaststellingsverslag
  acties, volgend werfbezoek, algemene voorwaarden (vijf kalenderdagen), voor akkoord

`naar_markdown(v)` en `van_markdown(md)` zijn elkaars spiegel, zodat een nieuwe lay-out zonder Claude
(dus zonder tokens) uit de bewaarde markdown kan worden gemaakt (`--herlayout`).
"""
import io
import os
import re
from datetime import date

HIER = os.path.dirname(os.path.abspath(__file__))
MASTER = os.path.join(HIER, "sjabloon_HA_master.docx")

FIRMA = {"naam": "H-Architects BV", "adres": "Koning Albertstraat 76A, 3290 Diest", "btw": "BE 0646.974.162",
         "mail": "light@h-architects.be", "tel": "016 79 32 96"}

VAST_VEILIGHEID = ("Veiligheid: het veiligheids- en gezondheidsplan van de veiligheidscoördinator is van toepassing tijdens de "
                   "hele duur van de werken. De planning van de werken wordt tijdig aan de veiligheidscoördinator bezorgd.")
VAST_TIENJARIG = ("Tienjarige aansprakelijkheid: de verzekeringsattesten voor de tienjarige burgerlijke aansprakelijkheid "
                  "volgens de wet Peeters-Borsus (31 mei 2017, BS 9 juni 2017) worden aangeleverd door alle aannemers die een "
                  "aandeel hebben in de constructie tot de wind- en waterdichte staat van de werken.")
VAST_VOORWAARDEN = ("Zonder tegenbericht per e-mail binnen de vijf kalenderdagen wordt aangenomen dat alle partijen akkoord "
                    "gaan met dit verslag. Vragen of opmerkingen kunnen per e-mail worden bezorgd aan H-Architects.")

# Doorlopende punten uit verslag 1 (Archisnapper 1.1 tot 1.6), in elk werfverslag herhaald tot OK.
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
VLAG_TERUG = {v.lower(): k for k, v in VLAG.items() if v}


def datum_nl(iso):
    try:
        j, m, d = iso[:10].split("-")
        maanden = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"]
        return f"{int(d)} {maanden[int(m) - 1]} {j}"
    except (ValueError, IndexError):
        return iso


def datum_iso(nl):
    maanden = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"]
    m = re.match(r"(\d{1,2}) (\w+) (\d{4})", nl.strip())
    if m and m.group(2) in maanden:
        return f"{m.group(3)}-{maanden.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}"
    return nl.strip()[:10]


def titel_van(v):
    return f"{'Verslag plaatsbezoek' if v.get('soort_bezoek') == 'plaatsbezoek' else 'Werfverslag'} {v['bezoek']}"


# ------------------------------------------------------------------ markdown ---
def naar_markdown(v):
    r = []
    nr, n = v["dossier"], v["bezoek"]
    r.append(f"# {titel_van(v)} voor project {nr} {v['adres']}")
    r.append("")
    r.append(f"**CONCEPT** - opgemaakt op {v['opgemaakt']} door Werfverslag schrijver uit {v.get('bronnen_kort', 'de bezoekmap')}. "
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
            kop = f"**{p['nummer']} {p['titel']}** - {datum_nl(p.get('datum') or v['datum'])}" + (f" - {vlag}" if vlag else "")
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
    r.append("Opgemaakt en verzonden door de architect op: (in te vullen)")
    return "\n".join(r) + "\n"


def _tabel_rijen(regels):
    uit = []
    for rg in regels:
        cellen = [c.strip() for c in rg.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cellen if c):
            continue
        uit.append(cellen)
    return uit


def van_markdown(md):
    """Spiegel van naar_markdown: de verslagstructuur terug uit de bewaarde markdown (zonder Claude)."""
    v = {"categorieen": [], "aanwezigen": [], "raming": [], "acties": [], "akkoord": [], "status_nl": "", "status_en": "", "volgend": ""}
    regels = md.splitlines()
    m = re.match(r"# (Werfverslag|Verslag plaatsbezoek) (\S+) voor project (\d{4}) (.*)", regels[0] if regels else "")
    if m:
        v["soort_bezoek"] = "plaatsbezoek" if m.group(1).startswith("Verslag") else "werfbezoek"
        v["bezoek"], v["dossier"], v["adres"] = m.group(2), m.group(3), m.group(4).strip()
    m = re.search(r"opgemaakt op (\d{4}-\d{2}-\d{2}) door .*? uit (.*?)\. Na te kijken", md)
    if m:
        v["opgemaakt"], v["bronnen_kort"] = m.group(1), m.group(2)
    # secties op ## splitsen
    secties, huidige, kop = {}, [], "kop"
    for rg in regels[1:]:
        if rg.startswith("## "):
            secties[kop] = huidige; kop = rg[3:].strip(); huidige = []
        else:
            huidige.append(rg)
    secties[kop] = huidige
    for cellen in _tabel_rijen([r for r in secties.get("kop", []) if r.startswith("|")]):
        if len(cellen) >= 2:
            if cellen[0] == "Datum werfbezoek":
                v["datum"] = datum_iso(cellen[1])
            elif cellen[0] == "Verslagtype":
                v["verslagtype"] = cellen[1]
    st = [r for r in secties.get("Status werf", []) if r.strip()]
    if st:
        v["status_nl"] = st[0]
        if len(st) > 1 and st[1].startswith("*"):
            v["status_en"] = st[1].strip("*")
    for cellen in _tabel_rijen([r for r in secties.get("Contactpersonen en aanwezigen", []) if r.startswith("|")])[1:]:
        if len(cellen) >= 5:
            v["aanwezigen"].append(dict(zip(("rol", "firma", "naam", "contact", "aanwezig"), cellen)))
    # waarnemingen
    cat, punt = None, None
    for rg in secties.get("Waarnemingen", []):
        if rg.startswith("### "):
            cat = {"naam": rg[4:].strip(), "punten": []}; v["categorieen"].append(cat); punt = None; continue
        m = re.match(r"\*\*(\S+) (.*?)\*\* - ([^-]+?)(?: - (OK|Belangrijk|Dringend))?\s*$", rg)
        if m and cat is not None:
            punt = {"nummer": m.group(1), "titel": m.group(2), "datum": datum_iso(m.group(3)), "vlag": VLAG_TERUG.get((m.group(4) or "").lower(), ""),
                    "tekst_nl": "", "tekst_en": "", "verantwoordelijke": "", "fotos": []}
            cat["punten"].append(punt); continue
        if punt is None or not rg.strip():
            continue
        if rg.startswith("Verantwoordelijke: "):
            punt["verantwoordelijke"] = rg[len("Verantwoordelijke: "):].strip()
        elif rg.startswith("Foto's: "):
            punt["fotos"] = [x.strip() for x in rg[len("Foto's: "):].split(",") if x.strip()]
        elif rg.startswith("*") and rg.endswith("*") and punt["tekst_nl"]:
            punt["tekst_en"] = rg.strip("*")
        else:
            punt["tekst_nl"] = (punt["tekst_nl"] + " " + rg.strip()).strip()
    for cellen in _tabel_rijen([r for r in secties.get("Raming van de herstelkosten", []) if r.startswith("|")])[1:]:
        if len(cellen) >= 3:
            v["raming"].append(dict(zip(("onderdeel", "herstelling", "raming"), cellen)))
    for cellen in _tabel_rijen([r for r in secties.get("Actiepunten", []) if r.startswith("|")])[1:]:
        if len(cellen) >= 3:
            v["acties"].append(dict(zip(("wie", "wat", "tegen"), cellen)))
    vg = [r for r in secties.get("Volgend werfbezoek", []) if r.strip()]
    v["volgend"] = vg[0] if vg else ""
    for cellen in _tabel_rijen([r for r in secties.get("Voor akkoord", []) if r.startswith("|")])[1:]:
        if len(cellen) >= 2:
            v["akkoord"].append({"partij": cellen[0], "naam": cellen[1]})
    return v


# ---------------------------------------------------------------------- docx ---
def _leeg_lichaam(doc):
    """Alle inhoud van de master weg; de sectie-instellingen van de EERSTE sectie (die verwijzen naar de kop- en
    voettekst) komen in de plaats van de laatste sectPr, want de tweede sectie van de master is 'linked to previous'."""
    import copy
    body = doc.element.body
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    eerste = None
    for p in body.iter(W + "p"):
        sp = p.find(W + "pPr/" + W + "sectPr")
        if sp is not None:
            eerste = copy.deepcopy(sp)
            break
    for kind in list(body):
        if kind.tag.endswith("}sectPr"):
            continue
        body.remove(kind)
    laatste = body.find(W + "sectPr")
    if eerste is not None and laatste is not None:
        body.replace(laatste, eerste)


def _voettekst(doc, tekst):
    """De master heeft de voettekst in een tabel: links 'nummer | soort' (vet, grijs, 9 pt), rechts 'Pagina X'.
    Alleen de linkertekst wordt vervangen; de opmaak en het paginaveld blijven van de master."""
    for s in doc.sections:
        f = s.footer
        if f.tables:
            cel = f.tables[0].rows[0].cells[0]
            p = cel.paragraphs[0]
            runs = list(p.runs)
            if runs:
                runs[0].text = tekst
                for r in runs[1:]:
                    r._element.getparent().remove(r._element)
            else:
                p.add_run(tekst)
            for extra in cel.paragraphs[1:]:
                extra._element.getparent().remove(extra._element)
        else:
            p = f.paragraphs[0] if f.paragraphs else f.add_paragraph()
            for r in list(p.runs):
                r._element.getparent().remove(r._element)
            p.add_run(tekst)


def naar_docx(v, fotos=None, master=MASTER):
    """Word in de huisstijl van de contractmasters. fotos: dict bijschrift -> bytes (jpg/png)."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, RGBColor
    fotos = fotos or {}
    doc = Document(master) if os.path.exists(master) else Document()
    if os.path.exists(master):
        _leeg_lichaam(doc)
    BLAUW_H1, BLAUW_H2, BLAUW_LABEL = RGBColor(0x36, 0x5F, 0x91), RGBColor(0x4F, 0x81, 0xBD), RGBColor(0x00, 0x70, 0xC0)
    nr, n = v["dossier"], v["bezoek"]
    titel = titel_van(v)
    _voettekst(doc, f"{nr} | {titel}")

    def alinea(tekst="", vet=False, cursief=False, grootte=None, kleur=None, na=None, stijl=None):
        p = doc.add_paragraph(style=stijl) if stijl else doc.add_paragraph()
        if tekst:
            r = p.add_run(tekst); r.bold = vet; r.italic = cursief
            if grootte:
                r.font.size = Pt(grootte)
            if kleur is not None:
                r.font.color.rgb = kleur
        if na is not None:
            p.paragraph_format.space_after = Pt(na)
        return p

    def h1(tekst):  # "1. HET VOORWERP ..." zoals in de master
        p = alinea(tekst.upper(), vet=True, grootte=12, kleur=BLAUW_H1, na=6)
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.keep_with_next = True
        return p

    def h2(tekst):  # "3.1. Het bouwproject"
        p = alinea(tekst, vet=True, kleur=BLAUW_H2, na=4)
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.keep_with_next = True
        return p

    def tabel(koppen, rijen, breedtes=None, kopvet=True):
        t = doc.add_table(rows=1 if koppen else 0, cols=len(koppen or rijen[0]))
        t.style = "Table Grid"
        if koppen:
            for i, k in enumerate(koppen):
                c = t.rows[0].cells[i]; c.text = ""
                r = c.paragraphs[0].add_run(k); r.bold = kopvet; r.font.size = Pt(9.5); r.font.color.rgb = BLAUW_H1
        for rij in rijen:
            cellen = t.add_row().cells
            for i, val in enumerate(rij):
                cellen[i].text = ""
                r = cellen[i].paragraphs[0].add_run(str(val or "")); r.font.size = Pt(9.5)
                if not koppen and i == 0:
                    r.bold = True
        if breedtes:
            for rij in t.rows:
                for i, b in enumerate(breedtes):
                    rij.cells[i].width = Cm(b)
        alinea(na=2)
        return t

    # kop zoals de master: Projectnummer vet, titel 16 pt vet, CONCEPT-regel
    alinea(f"Projectnummer: {nr}", vet=True, na=2)
    alinea(f"{titel}: {v['adres']}", vet=True, grootte=16, na=4)
    p = alinea(na=8)
    r = p.add_run("CONCEPT"); r.bold = True; r.font.color.rgb = RGBColor(0xC2, 0x41, 0x0C)
    r = p.add_run(f" - opgemaakt op {v['opgemaakt']} uit {v.get('bronnen_kort', 'de bezoekmap')}. Na te kijken en aan te vullen door Mehdi Chegini vóór verzending.")
    r.italic = True; r.font.size = Pt(9.5)
    tabel(None, [["Verslagnummer", f"{nr}-{n}"], ["Datum werfbezoek", datum_nl(v["datum"])], ["Verslagtype", v.get("verslagtype", "werfverslag")],
                 ["Opgemaakt door", f"{FIRMA['naam']}, {FIRMA['adres']}, {FIRMA['btw']}, {FIRMA['mail']}, {FIRMA['tel']}"]], [4.2, 12.2])
    # 1 status
    h1("1. Status van de werf")
    alinea(v.get("status_nl") or "(in te vullen)")
    if v.get("status_en"):
        alinea(v["status_en"], cursief=True)
    # 2 aanwezigen
    h1("2. Contactpersonen en aanwezigen")
    tabel(["Rol", "Firma", "Naam", "Contact", "Aanwezig"],
          [[a.get("rol", ""), a.get("firma", ""), a.get("naam", ""), a.get("contact", ""), a.get("aanwezig", "")] for a in v.get("aanwezigen", [])],
          [3.2, 3.4, 3.6, 4.4, 1.8])
    for t in (VAST_VEILIGHEID, VAST_TIENJARIG):
        alinea(t, grootte=9, na=4)
    # 3 waarnemingen
    h1("3. Waarnemingen")
    for cat in v.get("categorieen", []):
        h2(cat["naam"])
        for pt in cat.get("punten", []):
            vlag = VLAG.get((pt.get("vlag") or "").lower(), "")
            p = alinea(na=2)
            p.paragraph_format.keep_with_next = True
            r = p.add_run(f"{pt['nummer']}  {pt['titel']}"); r.bold = True
            r = p.add_run(f"   {datum_nl(pt.get('datum') or v['datum'])}"); r.font.size = Pt(9); r.font.color.rgb = RGBColor(0x6B, 0x6B, 0x6B)
            if vlag:
                r = p.add_run(f"   {vlag}"); r.bold = True
                r.font.color.rgb = RGBColor(0x1F, 0x6B, 0x3D) if vlag == "OK" else RGBColor(0xA3, 0x3A, 0x2A)
            alinea(pt.get("tekst_nl", ""), na=2)
            if pt.get("tekst_en"):
                alinea(pt["tekst_en"], cursief=True, na=2)
            if pt.get("verantwoordelijke"):
                q = alinea(na=4)
                r = q.add_run("Verantwoordelijke: "); r.font.size = Pt(9); r.font.color.rgb = BLAUW_LABEL; r.bold = True
                r = q.add_run(pt["verantwoordelijke"]); r.font.size = Pt(9)
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
                        c = cellen[j].add_paragraph(); r = c.add_run(bijschrift); r.font.size = Pt(8); r.font.color.rgb = RGBColor(0x6B, 0x6B, 0x6B)
                alinea(na=4)
            else:
                alinea(na=4)
    k = 4
    if v.get("raming"):
        h1(f"{k}. Raming van de herstelkosten"); k += 1
        tabel(["Onderdeel", "Herstelling", "Raming"],
              [[x.get("onderdeel", ""), x.get("herstelling", ""), x.get("raming", "(raming door de architect in te vullen)")] for x in v["raming"]],
              [4, 8.4, 4])
    h1(f"{k}. Actiepunten"); k += 1
    if v.get("acties"):
        tabel(["Wie", "Wat", "Tegen"], [[a.get("wie", ""), a.get("wat", ""), a.get("tegen", "")] for a in v["acties"]], [4, 9.4, 3])
    else:
        alinea("geen")
    h1(f"{k}. Volgend werfbezoek"); k += 1
    alinea(v.get("volgend") or "(in te vullen)")
    h1(f"{k}. Algemene voorwaarden"); k += 1
    alinea(VAST_VOORWAARDEN)
    h1(f"{k}. Voor akkoord")
    tabel(["Partij", "Naam", "Handtekening", "Datum"], [[a.get("partij", ""), a.get("naam", ""), "", ""] for a in v.get("akkoord", [])], [4, 5.4, 4, 3])
    alinea("Opgemaakt en verzonden door de architect op: (in te vullen)")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def telling_open(md):
    """Hoeveel plekken Mehdi nog moet invullen of nakijken: de nacontrole van de proef (W11)."""
    return {"in_te_vullen": len(re.findall(r"\(in te vullen\)", md)), "na_te_kijken": len(re.findall(r"\(na te kijken\)", md)),
            "raming_open": len(re.findall(r"raming door de architect", md))}

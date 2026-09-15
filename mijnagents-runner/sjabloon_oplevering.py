"""Proces-verbaal van voorlopige en van definitieve oplevering: het sjabloon van H-Architects.

Geleerd uit negen echte PV's in Archisnapper (2008-16, 1828-8, 2033-3, 2089-8, 2118-3, 2103-13, 2056-11, 2199-7,
2004-47; analyse 15-09-2026) en de Belgische praktijk. Een definitieve oplevering bestond in Archisnapper nooit als
apart verslag: de voorlopige ging "automatisch" over. Het sjabloon voorziet beide wegen; Mehdi kiest per dossier
(keuze `overgang`: "automatisch" of "tweede rondgang").

Word-opmaak: dezelfde huisstijl als het werfverslag (sjabloon_werfverslag.naar_docx: master van het contractsysteem).
`sjabloon(soort)` geeft een leeg sjabloon met plaatshouders <...>; `naar_docx_pv(v, fotos)` een ingevuld PV.
"""
import io
import os
from datetime import date

import sjabloon_werfverslag as sj

SOORTEN = {"voorlopige_oplevering": "Proces-verbaal van voorlopige oplevering",
           "definitieve_oplevering": "Proces-verbaal van definitieve oplevering"}

# Vaste teksten (herwerkt uit 2008-16 en sjabloon 2001-4; spelfout "gekorttekende" -> "geparafeerde")
VO_VOORWERP = (
    "Dit verslag geldt als proces-verbaal van voorlopige oplevering voor project {nr} {adres}. De rondgang vond plaats op "
    "{datum} in aanwezigheid van de opdrachtgever, de (hoofd)aannemer(s) en de architect.\n"
    "De voorlopige oplevering wordt aanvaard onder voorbehoud van de voorafgaande werfverslagen en van de hieronder "
    "genummerde en door partijen geparafeerde opmerkingen, waaraan moet worden voldaan uiterlijk op {einddatum}.\n"
    "De datum van dit proces-verbaal geldt als datum van voorlopige oplevering. Vanaf deze datum lopen de waarborgtermijn "
    "en de tienjarige aansprakelijkheid van aannemer en architect (wet Peeters-Borsus van 31 mei 2017; art. 1792 en 2270 "
    "oud Burgerlijk Wetboek). De voorlopige oplevering houdt geen aanvaarding in van verborgen gebreken.\n"
    "{overgang}\n"
    "De benodigde documenten, attesten en keuringsverslagen voor het as-builtdossier en de EPB-eindverklaring worden "
    "eveneens ten laatste op {einddatum} aan het architectenkantoor bezorgd.\n"
    "Opmerkingen op dit proces-verbaal dienen schriftelijk en binnen de 8 werkdagen overgemaakt te worden aan het "
    "architectenkantoor. Zonder tegenbericht binnen die termijn wordt het proces-verbaal als aanvaard beschouwd.")
VO_OVERGANG = {
    "automatisch": ("De voorlopige oplevering gaat automatisch over naar een definitieve oplevering op {do_datum}, als aan de "
                    "opgesomde opmerkingen is voldaan."),
    "tweede rondgang": ("De definitieve oplevering vindt plaats ten vroegste {waarborg} maanden na deze datum, na een tweede "
                        "rondgang en een afzonderlijk proces-verbaal, en op voorwaarde dat de hieronder opgesomde opmerkingen "
                        "zijn uitgevoerd."),
}
DO_VOORWERP = (
    "Dit verslag geldt als proces-verbaal van definitieve oplevering voor project {nr} {adres}. De voorlopige oplevering "
    "vond plaats op {vo_datum} (proces-verbaal {vo_nr}). De rondgang voor de definitieve oplevering vond plaats op {datum} "
    "in aanwezigheid van de opdrachtgever, de (hoofd)aannemer(s) en de architect.\n"
    "De partijen stellen vast dat de opmerkingen van het proces-verbaal van voorlopige oplevering zijn uitgevoerd, met "
    "uitzondering van de hieronder genummerde punten. De definitieve oplevering wordt aanvaard {voorbehoud}.\n"
    "De definitieve oplevering sluit de waarborgtermijn af en dekt de zichtbare gebreken en de lichte verborgen gebreken "
    "die op de datum van dit proces-verbaal gekend waren. De tienjarige aansprakelijkheid voor ernstige gebreken die de "
    "stevigheid van het gebouw aantasten (art. 1792 en 2270 oud Burgerlijk Wetboek) loopt verder tot {ba10_einde}.\n"
    "Met de ondertekening van dit proces-verbaal eindigt de opdracht van de architect voor de werfopvolging.\n"
    "Opmerkingen op dit proces-verbaal dienen schriftelijk en binnen de 8 werkdagen overgemaakt te worden aan het "
    "architectenkantoor.")
WETTELIJK = [
    ("Veiligheid", sj.VAST_VEILIGHEID.split(": ", 1)[1]),
    ("Verzekeringsattesten", "Het attest van de tienjarige burgerlijke aansprakelijkheid (BA10) voor de werken aan de gesloten "
     "ruwbouw (wet Peeters-Borsus van 31 mei 2017) en het attest van de burgerlijke beroepsaansprakelijkheid (BBR) van alle "
     "betrokken aannemers, hoofdaannemer en onderaannemers, zitten in het dossier of worden hieronder als ontbrekend vermeld."),
    ("Omgevingsloket", "De bouwheer meldt de einddatum van de werken in het omgevingsloket. Werken buiten de geldigheid van de "
     "vergunning zijn de verantwoordelijkheid van de bouwheer."),
    ("EPB", "De bouwheer bezorgt de stavingsstukken (facturen, technische fiches, Uw-rapporten, foto's) aan de EPB-verslaggever "
     "voor de eindverklaring, uiterlijk op de hieronder vermelde einddatum."),
]
BELANGRIJK = ("Na elke rondgang in het kader van een oplevering maakt de architect een proces-verbaal op en stuurt dit door naar "
              "alle betrokken partijen. Elke aannemer stuurt op zijn beurt het verslag door naar zijn onderaannemers. Opmerkingen "
              "op dit verslag worden uitsluitend schriftelijk gesteld. Het proces-verbaal is op deze manier steeds aanvaard en "
              "goedgekeurd.")
DOCUMENTEN = ["As-builtplannen", "Keuringsverslag elektriciteit", "Keuring riolering en afkoppeling", "EPB-stavingsstukken (facturen, "
              "technische fiches, Uw-rapporten, foto's)", "Attesten BA10 en BBR per aannemer", "Onderhoudsvoorschriften technieken",
              "Sleutels en toegangscodes", "Meterstanden water, gas en elektriciteit op de dag van de oplevering"]
DO_AFSLUITING = ["EPB-eindverklaring ingediend (datum, verslaggever)", "Einddatum werken gemeld in het omgevingsloket (datum)",
                 "As-builtdossier volledig", "Keuringsattesten", "Postinterventiedossier overhandigd door de veiligheidscoördinator",
                 "Laatste factuur en vrijgave van borg of inhouding"]


def leeg(soort, nr="<nr>", adres="<adres werf>"):
    """Een leeg PV met plaatshouders, als sjabloon voor Mehdi."""
    vo = soort == "voorlopige_oplevering"
    v = {"soort": soort, "dossier": nr, "adres": adres, "datum": "<dd-mm-jjjj>", "opgemaakt": date.today().isoformat(),
         "bouwheer": "<naam bouwheer(s)>", "aannemer": "<hoofdaannemer>", "omschrijving": "<korte omschrijving van het project>",
         "nummer": f"{nr}-{'VO' if vo else 'DO'}", "einddatum": "<weekdag dd maand jjjj>", "overgang": "tweede rondgang",
         "waarborg": "12", "do_datum": "<dd maand jjjj>", "vo_datum": "<dd-mm-jjjj>", "vo_nr": f"{nr}-VO",
         "voorbehoud": "<zonder voorbehoud / onder voorbehoud van de hieronder genummerde opmerkingen, uit te voeren uiterlijk op dd-mm-jjjj>",
         "ba10_einde": "<datum voorlopige oplevering + 10 jaar>",
         "aanwezigen": [{"rol": "Bouwheer", "firma": "", "naam": "<naam>", "contact": "<mail, tel>", "aanwezig": "ja", "ontvangt": "ja"},
                        {"rol": "Architect", "firma": "H-Architects BV", "naam": "Mehdi Chegini", "contact": "light@h-architects.be", "aanwezig": "ja", "ontvangt": "ja"},
                        {"rol": "Hoofdaannemer", "firma": "<firma>", "naam": "<naam>", "contact": "<mail, tel>", "aanwezig": "ja", "ontvangt": "ja"}],
         "conform": "<ja / nee: lijst van afwijkingen ten opzichte van de vergunde plannen>",
         "gebreken": [{"nr": ("VO" if vo else "DO") + ".1", "onderdeel": "<ruimte of onderdeel>", "omschrijving": "<gebrek of onafgewerkt werk>",
                       "foto": "", "verantwoordelijke": "<aannemer>", "termijn": "<einddatum>", "vlag": "NOK"}],
         "opvolging": [] if vo else [{"nr": "VO.1", "omschrijving": "<punt uit het PV van voorlopige oplevering>", "status": "<uitgevoerd op dd-mm-jjjj / niet uitgevoerd / anders opgelost>", "verantwoordelijke": "<aannemer>"}],
         "nieuw": [] if vo else [{"nr": "DO.1", "onderdeel": "<ruimte of onderdeel>", "omschrijving": "<gebrek gebleken tijdens het gebruik>", "waarborg": "<waarborg aannemer / gebruik en onderhoud bouwheer>", "verantwoordelijke": "<aannemer>", "termijn": "<datum>"}],
         "documenten": [{"naam": d, "status": "<ontvangen / ontbreekt>"} for d in (DOCUMENTEN if vo else DO_AFSLUITING)],
         "financieel": [["Eindafrekening aannemer ontvangen", "<ja / nee>"], ["Inhouding of borg", "<bedrag en vrijgavevoorwaarde>"],
                        ["Erelonen architect", "<afrekening op werkelijke kost>"]],
         "fotos": [], "akkoord": [{"partij": "Architect (ter kennisname)", "naam": "Mehdi Chegini, H-Architects BV"},
                                  {"partij": "Aannemer (voor akkoord)", "naam": "<naam>"}, {"partij": "Bouwheer (voor akkoord)", "naam": "<naam>"}]}
    return v


def naar_docx_pv(v, fotos=None):
    from docx import Document
    from docx.shared import Cm, Pt, RGBColor
    fotos = fotos or {}
    doc = Document(sj.MASTER) if os.path.exists(sj.MASTER) else Document()
    if os.path.exists(sj.MASTER):
        sj._leeg_lichaam(doc)
    vo = v["soort"] == "voorlopige_oplevering"
    titel = SOORTEN[v["soort"]]
    BLAUW_H1, BLAUW_H2 = RGBColor(0x36, 0x5F, 0x91), RGBColor(0x4F, 0x81, 0xBD)
    sj._voettekst(doc, f"{v['dossier']} | {titel}")

    def alinea(tekst="", vet=False, cursief=False, grootte=None, kleur=None, na=None):
        p = doc.add_paragraph()
        if tekst:
            r = p.add_run(tekst); r.bold = vet; r.italic = cursief
            if grootte:
                r.font.size = Pt(grootte)
            if kleur is not None:
                r.font.color.rgb = kleur
        if na is not None:
            p.paragraph_format.space_after = Pt(na)
        return p

    def h1(t):
        p = alinea(t.upper(), vet=True, grootte=12, kleur=BLAUW_H1, na=6); p.paragraph_format.space_before = Pt(12); p.paragraph_format.keep_with_next = True

    def h2(t):
        p = alinea(t, vet=True, kleur=BLAUW_H2, na=3); p.paragraph_format.space_before = Pt(9); p.paragraph_format.keep_with_next = True

    def tabel(koppen, rijen, breedtes=None):
        t = doc.add_table(rows=1 if koppen else 0, cols=len(koppen) if koppen else len(rijen[0]))
        t.style = "Table Grid"
        if koppen:
            for i, k in enumerate(koppen):
                c = t.rows[0].cells[i]; c.text = ""; r = c.paragraphs[0].add_run(k); r.bold = True; r.font.size = Pt(9.5); r.font.color.rgb = BLAUW_H1
        for rij in rijen:
            cellen = t.add_row().cells
            for i, val in enumerate(rij):
                cellen[i].text = ""; r = cellen[i].paragraphs[0].add_run(str(val or "")); r.font.size = Pt(9.5)
                if not koppen and i == 0:
                    r.bold = True
        if breedtes:
            for rij in t.rows:
                for i, b in enumerate(breedtes):
                    rij.cells[i].width = Cm(b)
        alinea(na=2)

    alinea(f"Projectnummer: {v['dossier']}", vet=True, na=2)
    alinea(f"{titel}: {v['adres']}", vet=True, grootte=16, na=8)
    p = alinea(na=8)
    r = p.add_run("CONCEPT"); r.bold = True; r.font.color.rgb = RGBColor(0xC2, 0x41, 0x0C)
    r = p.add_run(f" - opgemaakt op {v['opgemaakt']}. Na te kijken en aan te vullen door Mehdi Chegini vóór verzending."); r.italic = True; r.font.size = Pt(9.5)
    tabel(None, [["Nummer", v["nummer"]], ["Project", f"{v['dossier']} {v['adres']}"], ["Omschrijving", v.get("omschrijving", "")],
                 ["Bouwheer", v.get("bouwheer", "")], ["Hoofdaannemer", v.get("aannemer", "")], ["Datum rondgang", v["datum"]],
                 ["Opgemaakt door", f"{sj.FIRMA['naam']}, {sj.FIRMA['adres']}, {sj.FIRMA['btw']}, {sj.FIRMA['mail']}, {sj.FIRMA['tel']}"]], [4.2, 12.2])
    h1("1. Voorwerp en aanvaarding")
    if vo:
        overgang = VO_OVERGANG.get(v.get("overgang", "tweede rondgang"), VO_OVERGANG["tweede rondgang"]).format(do_datum=v.get("do_datum", ""), waarborg=v.get("waarborg", "12"))
        tekst = VO_VOORWERP.format(nr=v["dossier"], adres=v["adres"], datum=v["datum"], einddatum=v.get("einddatum", ""), overgang=overgang)
    else:
        tekst = DO_VOORWERP.format(nr=v["dossier"], adres=v["adres"], datum=v["datum"], vo_datum=v.get("vo_datum", ""), vo_nr=v.get("vo_nr", ""),
                                   voorbehoud=v.get("voorbehoud", ""), ba10_einde=v.get("ba10_einde", ""))
    for regel in tekst.split("\n"):
        alinea(regel, na=4)
    h1("2. Contactpersonen en aanwezigen")
    tabel(["Rol", "Firma", "Naam", "Contact", "Aanwezig", "Ontvangt PV"],
          [[a.get("rol", ""), a.get("firma", ""), a.get("naam", ""), a.get("contact", ""), a.get("aanwezig", ""), a.get("ontvangt", "ja")] for a in v.get("aanwezigen", [])],
          [3, 3, 3.2, 4, 1.7, 1.7])
    h1("3. Wettelijke verplichtingen en verantwoordelijkheden")
    for kop, t in WETTELIJK:
        p = alinea(na=3); r = p.add_run(kop + ": "); r.bold = True; r.font.size = Pt(9.5); r = p.add_run(t); r.font.size = Pt(9.5)
    k = 4
    if vo:
        h1(f"{k}. Uitvoering volgens de vergunde plannen"); k += 1
        alinea(v.get("conform", ""))
        h1(f"{k}. Gebreken en onafgewerkte werken"); k += 1
        tabel(["Nr", "Ruimte of onderdeel", "Omschrijving", "Foto", "Verantwoordelijke", "Hersteltermijn", "Vlag"],
              [[g.get("nr", ""), g.get("onderdeel", ""), g.get("omschrijving", ""), g.get("foto", ""), g.get("verantwoordelijke", ""), g.get("termijn", ""), g.get("vlag", "")] for g in v.get("gebreken", [])],
              [1.4, 2.8, 5.2, 1.4, 2.6, 2.2, 1.4])
        h1(f"{k}. Documenten en attesten"); k += 1
        tabel(["Document", "Status"], [[d.get("naam", ""), d.get("status", "")] for d in v.get("documenten", [])], [10, 6.4])
        h1(f"{k}. Financieel"); k += 1
        tabel(None, v.get("financieel", []), [6, 10.4])
    else:
        h1(f"{k}. Opvolging van de punten uit het PV van voorlopige oplevering"); k += 1
        tabel(["Nr", "Omschrijving", "Status", "Verantwoordelijke"],
              [[o.get("nr", ""), o.get("omschrijving", ""), o.get("status", ""), o.get("verantwoordelijke", "")] for o in v.get("opvolging", [])], [1.6, 7.4, 4.4, 3])
        h1(f"{k}. Nieuwe vaststellingen sinds de voorlopige oplevering"); k += 1
        tabel(["Nr", "Ruimte of onderdeel", "Omschrijving", "Waarborg of gebruik", "Verantwoordelijke", "Termijn"],
              [[n.get("nr", ""), n.get("onderdeel", ""), n.get("omschrijving", ""), n.get("waarborg", ""), n.get("verantwoordelijke", ""), n.get("termijn", "")] for n in v.get("nieuw", [])],
              [1.4, 2.8, 5, 3, 2.6, 1.6])
        h1(f"{k}. Administratieve afsluiting"); k += 1
        tabel(["Onderdeel", "Status"], [[d.get("naam", ""), d.get("status", "")] for d in v.get("documenten", [])], [10, 6.4])
    h1(f"{k}. Foto's van de toestand op de dag van de oplevering"); k += 1
    if fotos and v.get("fotos"):
        for i, b in enumerate(v["fotos"], 1):
            if b in fotos:
                p = doc.add_paragraph(); p.paragraph_format.keep_with_next = True
                p.add_run().add_picture(io.BytesIO(fotos[b]), height=Cm(10.6))
                q = alinea(na=10); r = q.add_run(f"Foto {i}"); r.bold = True; r.font.size = Pt(9)
    else:
        alinea("(gevels en elk niveau, genomen op de dag van de rondgang)", cursief=True)
    h1(f"{k}. Handtekeningen"); k += 1
    alinea(BELANGRIJK, grootte=9.5)
    tabel(["Partij", "Naam", "Datum", "Handtekening"], [[a.get("partij", ""), a.get("naam", ""), "", ""] for a in v.get("akkoord", [])], [4.4, 5.6, 2.6, 3.8])
    alinea("Bij weigering te tekenen: vermelding van de weigering en de reden. " + ("Bijlage: kopie van het proces-verbaal van voorlopige oplevering." if not vo else ""), grootte=9)
    buf = io.BytesIO(); doc.save(buf); return buf.getvalue()


if __name__ == "__main__":
    import sys
    uit = sys.argv[1] if len(sys.argv) > 1 else "."
    for soort in SOORTEN:
        open(os.path.join(uit, f"Sjabloon {SOORTEN[soort]} (H-Architects).docx"), "wb").write(naar_docx_pv(leeg(soort)))
        print("geschreven:", SOORTEN[soort])

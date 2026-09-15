#!/usr/bin/env python3
"""verslag_basis — de gedeelde motor van de verslagagents (veiligheidscoördinatie, plaatsbeschrijving, barsten en
scheuren; werfverslag heeft zijn eigen keten). Een verslagagent zoekt niet achter data: het Commandocentrum stuurt
de impulsen, de wachten vullen de bezoekmap. De agent:

  impuls `voorbereiding`  dossiermap zoeken in de basismappen van zijn soort (nummer, adres of klantnaam),
                          bezoekmap aanmaken in de communicatiemap (`<datum> <bezoeknaam>` met `00 bezoek.md`),
                          pakket melden op het bord;
  elke ronde              het pakket meten (foto's, opnames, transcripten, documenten in de bezoekmap);
  impuls `verslag`        melden dat het pakket vol is: "klaar voor verslag, wacht op de knop";
  opdracht `proef <id>`   (alleen van de knop op het bord, van=bord:...) de proef schrijven met claude-opus-5 in de
                          hoofdstukken van zijn soort, als markdown en Word in de bezoekmap; nooit overschrijven;
                          voor barsten en scheuren daarnaast het dossier klaarzetten voor de bestaande pijplijn.

Een nieuwe verslagsoort = een blok in koppelingen/verslagsoorten.py + een dunne runner:
    from verslag_basis import VerslagAgent; VerslagAgent("<soort>").main()
"""
import argparse
import io
import json
import os
import re
import sys
from datetime import date, datetime

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import bronnen  # noqa: E402
import verslagsoorten as vs  # noqa: E402
import werfverslag_proef as wp  # noqa: E402  (leest bezoekmappen, bundelt bronnen, Claude-client, sleutel uit ~/agents/.env)

FOTO_EXT = (".heic", ".jpg", ".jpeg", ".png", ".webp")
OPNAME_EXT = (".mp3", ".m4a", ".wav", ".mp4", ".mov")
DOC_EXT = (".docx", ".pdf", ".pptx", ".md", ".txt")
BS_DOSSIERS = os.environ.get("BS_DOSSIERS_DIR", "/home/ubuntu/barsten_en_scheuren/dossiers")

VERSLAG_SCHEMA = {
    "name": "verslag",
    "description": "Het concept-verslag, per hoofdstuk, met genummerde punten en foto's uit de bezoekmap.",
    "input_schema": {
        "type": "object",
        "properties": {
            "titel": {"type": "string"},
            "aanwezigen": {"type": "array", "items": {"type": "object", "properties": {
                "rol": {"type": "string"}, "firma": {"type": "string"}, "naam": {"type": "string"}, "aanwezig": {"type": "string"}}}},
            "hoofdstukken": {"type": "array", "items": {"type": "object", "properties": {
                "titel": {"type": "string"},
                "tekst": {"type": "string", "description": "lopende tekst van het hoofdstuk; leeg als de punten volstaan"},
                "punten": {"type": "array", "items": {"type": "object", "properties": {
                    "nr": {"type": "string"}, "titel": {"type": "string"}, "tekst": {"type": "string"},
                    "vlag": {"type": "string", "description": "OK, Belangrijk, Dringend of leeg"},
                    "verantwoordelijke": {"type": "string"}, "termijn": {"type": "string"},
                    "fotos": {"type": "array", "items": {"type": "string"}, "description": "bestandsnamen uit de bezoekmap"}},
                    "required": ["titel", "tekst"]}}},
                "required": ["titel"]}},
            "acties": {"type": "array", "items": {"type": "object", "properties": {
                "wie": {"type": "string"}, "wat": {"type": "string"}, "wanneer": {"type": "string"}}}},
            "open_punten": {"type": "array", "items": {"type": "string"},
                            "description": "wat in de bronnen ontbreekt of na te kijken is; Mehdi vult het in"},
        },
        "required": ["titel", "hoofdstukken"],
    },
}


def _systeem(s):
    hoofdstukken = "\n".join(f"{i}. {t}: {oms}" for i, (t, oms) in enumerate(s["hoofdstukken"], 1))
    return f"""Je schrijft voor Mehdi Chegini (architect, {s['afdeling'].upper()}) het concept van een {s['label'].lower()}-verslag
na een bezoek ter plaatse. Je krijgt de bronnen uit de bezoekmap: transcript van de opname, notities, foto's (namen), documenten.

Regels:
- Alleen wat in de bronnen staat. Wat er niet in staat, wordt "(in te vullen)" of komt in open_punten. Verzin niets.
- Elk vaststellingspunt: korte titel, concrete tekst, plaats in het gebouw, en de foto's die erbij horen (bestandsnamen uit de lijst).
- Nummer de punten per hoofdstuk als <hoofdstuk>.<volgnummer> (bv. 3.1, 3.2).
- Onzekere lezing uit het transcript krijgt "(na te kijken)". Sprekers zonder naam heten "spreker N".
- Geen juridische conclusies over aansprakelijkheid; beschrijf vaststellingen en verwijs naar de bevoegde partij.
- Externen noem je met firmanaam; personen alleen als ze in de bronnen met naam en rol staan.
- Nederlands, zakelijk, geen emoji, geen kastlijntjes (gewoon koppelteken).

Hoofdstukken van dit verslagtype, in deze volgorde (allemaal opnemen; een hoofdstuk zonder inhoud krijgt de tekst "geen"):
{hoofdstukken}

Vaste slotzin (niet herschrijven): {s.get('slot', '')}"""


def _md(v, s, rij):
    r = [f"# {v.get('titel') or s.get('verslagtitel', s['label'])}", "",
         f"CONCEPT, opgemaakt {date.today().isoformat()} door {s['agent']} (Mehdi Agents). Mehdi legt er zijn laag over; niets is verstuurd.", "",
         f"- Dossier: {rij.get('dossier') or '(in te vullen)'}", f"- Adres: {rij.get('adres') or '(in te vullen)'}",
         f"- Klant: {rij.get('klant') or '(in te vullen)'}", f"- Bezoek: {rij.get('datum')} {(rij.get('start') or '')[11:16]}-{(rij.get('einde') or '')[11:16]}",
         f"- Bezoekmap: {rij.get('bezoekmap')}", ""]
    if v.get("aanwezigen"):
        r += ["## Aanwezigen", "", "| Rol | Firma | Naam | Aanwezig |", "|---|---|---|---|"]
        r += [f"| {x.get('rol','')} | {x.get('firma','')} | {x.get('naam','')} | {x.get('aanwezig','')} |" for x in v["aanwezigen"]]
        r.append("")
    for i, h in enumerate(v.get("hoofdstukken") or [], 1):
        r += [f"## {i}. {h.get('titel','')}", ""]
        if h.get("tekst"):
            r += [h["tekst"], ""]
        for pnt in h.get("punten") or []:
            kop = f"**{pnt.get('nr') or ''} {pnt.get('titel','')}**".replace("** ", "**")
            meta = " · ".join(x for x in (pnt.get("vlag") or "", pnt.get("verantwoordelijke") or "", pnt.get("termijn") or "") if x)
            r.append(kop + (f" ({meta})" if meta else ""))
            r.append(pnt.get("tekst", ""))
            if pnt.get("fotos"):
                r.append("Foto's: " + ", ".join(pnt["fotos"]))
            r.append("")
    if v.get("acties"):
        r += ["## Acties", "", "| Wie | Wat | Tegen wanneer |", "|---|---|---|"]
        r += [f"| {x.get('wie','')} | {x.get('wat','')} | {x.get('wanneer','')} |" for x in v["acties"]]
        r.append("")
    if v.get("open_punten"):
        r += ["## Open punten (door Mehdi in te vullen)", ""] + [f"- {x}" for x in v["open_punten"]] + [""]
    if s.get("slot"):
        r += ["---", "", s["slot"], ""]
    return "\n".join(r)


def _docx(v, s, rij, beelden):
    """Eenvoudig Word-document (python-docx, geen master): titel, gegevens, hoofdstukken met punten, foto's erbij."""
    from docx import Document
    from docx.shared import Cm, Pt
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Aptos"
    st.font.size = Pt(11)
    doc.add_heading(v.get("titel") or s.get("verslagtitel", s["label"]), level=0)
    doc.add_paragraph(f"CONCEPT, opgemaakt {date.today().isoformat()}. Dossier {rij.get('dossier') or '(in te vullen)'} - "
                      f"{rij.get('adres') or ''} - bezoek {rij.get('datum')}")
    if v.get("aanwezigen"):
        t = doc.add_table(rows=1, cols=4)
        t.style = "Table Grid"
        for c, k in zip(t.rows[0].cells, ("Rol", "Firma", "Naam", "Aanwezig")):
            c.text = k
        for x in v["aanwezigen"]:
            cells = t.add_row().cells
            for c, k in zip(cells, ("rol", "firma", "naam", "aanwezig")):
                c.text = str(x.get(k, ""))
    for i, h in enumerate(v.get("hoofdstukken") or [], 1):
        doc.add_heading(f"{i}. {h.get('titel','')}", level=1)
        if h.get("tekst"):
            doc.add_paragraph(h["tekst"])
        for pnt in h.get("punten") or []:
            p = doc.add_paragraph()
            p.add_run(f"{pnt.get('nr') or ''} {pnt.get('titel','')}".strip()).bold = True
            meta = " · ".join(x for x in (pnt.get("vlag") or "", pnt.get("verantwoordelijke") or "", pnt.get("termijn") or "") if x)
            if meta:
                p.add_run(f"  ({meta})")
            doc.add_paragraph(pnt.get("tekst", ""))
            for naam in pnt.get("fotos") or []:
                b = beelden.get(naam)
                if b:
                    try:
                        doc.add_picture(io.BytesIO(b), width=Cm(8))
                        doc.add_paragraph(naam).runs[0].font.size = Pt(8)
                    except Exception:  # noqa: BLE001
                        doc.add_paragraph(f"(foto {naam} niet ingevoegd)")
    if v.get("acties"):
        doc.add_heading("Acties", level=1)
        t = doc.add_table(rows=1, cols=3)
        t.style = "Table Grid"
        for c, k in zip(t.rows[0].cells, ("Wie", "Wat", "Tegen wanneer")):
            c.text = k
        for x in v["acties"]:
            cells = t.add_row().cells
            for c, k in zip(cells, ("wie", "wat", "wanneer")):
                c.text = str(x.get(k, ""))
    if v.get("open_punten"):
        doc.add_heading("Open punten (door Mehdi in te vullen)", level=1)
        for x in v["open_punten"]:
            doc.add_paragraph(x, style="List Bullet")
    if s.get("slot"):
        doc.add_paragraph(s["slot"])
    uit = io.BytesIO()
    doc.save(uit)
    return uit.getvalue()


def _tokens(adres):
    return {w for w in re.split(r"[^a-z0-9]+", (adres or "").lower()) if len(w) > 2 and w not in ("belgium", "belgie", "belgië")}


class VerslagAgent:
    def __init__(self, soort):
        self.soort = soort
        self.s = vs.SOORTEN[soort]
        self.naam = self.s["agent"]
        self.ag = bord.Agent(self.naam)

    # ------------------------------------------------------------- bord ---
    def rijen(self, alle=False):
        return bord.call(f"/api/verslagopdracht?agent={self.naam}" + ("&open=alle" if alle else "")).get("rijen", [])

    def rij(self, uniek=None, vid=None):
        q = f"uniek={uniek}" if uniek else f"id={vid}"
        r = bord.call(f"/api/verslagopdracht?open=alle&{q}").get("rijen", [])
        return r[0] if r else None

    def bewaar(self, uniek, **velden):
        velden["_alleen"] = list(velden)
        bord.call("/api/verslagopdracht", {"rijen": [{"uniek": uniek, **velden}]})

    # ------------------------------------------------------- dossiermap ---
    def zoek_dossiermap(self, rij):
        """Eerst het nummer vooraan de mapnaam, dan het adres (straat + huisnummer), dan de klantnaam."""
        nummer = str(rij.get("dossier") or "").strip()
        adres_t = _tokens(rij.get("adres"))
        klant_t = _tokens(rij.get("klant"))
        kandidaten = []
        for basis in self.s["basismappen"]:
            for e in bronnen.lijst(basis, recursief=False) or []:
                if e.get(".tag") != "folder":
                    continue
                naam = e.get("name", "")
                if naam[:1] in "0_" and not re.match(r"^\d{4,5}\s", naam):
                    continue   # 0. Archive, 0. Structure, ...
                kandidaten.append((naam, e.get("path_display")))
        if nummer:
            for naam, pad in kandidaten:
                if re.match(rf"^\s*{re.escape(nummer)}\b", naam):
                    return pad, "projectnummer vooraan de mapnaam"
        beste, score, hoe = None, 0, ""
        for naam, pad in kandidaten:
            nt = _tokens(naam)
            sa = len(nt & adres_t)
            if adres_t and sa >= 2 and sa > score:
                beste, score, hoe = pad, sa, f"adres ({sa} woorden)"
        if beste:
            return beste, hoe
        for naam, pad in kandidaten:
            nt = _tokens(naam)
            sk = len(nt & klant_t)
            if klant_t and sk >= 2 and sk > score:
                beste, score, hoe = pad, sk, f"klantnaam ({sk} woorden)"
        return (beste, hoe) if beste else (None, "")

    def maak_bezoekmap(self, rij, dossiermap):
        pad = f"{dossiermap}/{self.s['communicatiemap']}/{rij['datum']} {self.s['bezoeknaam']}"
        if bronnen.lijst(pad, recursief=False) is not None:
            return pad, False
        kop = [f"# {rij['datum']} {self.s['bezoeknaam']}", "",
               f"Bezoekmap aangemaakt door {self.naam} (Mehdi Agents) op {date.today().isoformat()}, op impuls van het Commandocentrum.", "",
               f"- Verslagsoort: {self.s['label']}", f"- Dossier: {rij.get('dossier') or '(geen nummer in de agenda)'}",
               f"- Klant: {rij.get('klant') or ''}", f"- Adres: {rij.get('adres') or ''}",
               f"- Agenda: {rij.get('agenda')} - {rij.get('titel')}", f"- Venster: {rij.get('start')} tot {rij.get('einde')}",
               f"- Deal: {rij.get('deal_id') or '-'}", "",
               "Wat hier landt: `fotos/` (iCloud-wacht, foto's van de bezoekdag binnen 300 m), `transcript.txt` (Plaudwacht),",
               "en daarna het concept-verslag (markdown en Word). Niets wordt overschreven.", ""]
        bronnen.upload(f"{pad}/00 bezoek.md", "\n".join(kop).encode("utf-8"))
        return pad, True

    # ----------------------------------------------------------- pakket ---
    def meet_pakket(self, rij):
        pk = {"agenda": True, "dossiermap": bool(rij.get("dossiermap")), "bezoekmap": bool(rij.get("bezoekmap")),
              "fotos": 0, "opnames": 0, "transcripten": 0, "documenten": 0, "proef": 0, "gemeten_ts": datetime.now().isoformat(timespec="minutes")}
        if not rij.get("bezoekmap"):
            return pk
        items = bronnen.lijst(rij["bezoekmap"], recursief=True)
        if items is None:
            pk["bezoekmap"] = False
            return pk
        for e in items:
            if e.get(".tag") != "file":
                continue
            n = e.get("name", "").lower()
            if n.endswith(FOTO_EXT):
                pk["fotos"] += 1
            elif n.endswith(OPNAME_EXT):
                pk["opnames"] += 1
            elif "transcript" in n:
                pk["transcripten"] += 1
            elif "(concept)" in n or "proef" in n:
                pk["proef"] += 1
            elif n.endswith(DOC_EXT) and n != "00 bezoek.md" and n != "00 fotos.md":
                pk["documenten"] += 1
        return pk

    # --------------------------------------------------------- impulsen ---
    def impulsen(self):
        items = [it for it in bord.klaargezet_voor(self.naam, n=50) if it.get("soort") == "impuls"]
        gedaan = 0
        for it in reversed(items):
            try:
                d = json.loads(it.get("inhoud") or "{}")
            except ValueError:
                d = {}
            uniek, fase = d.get("uniek"), d.get("fase")
            rij = self.rij(uniek=uniek) if uniek else None
            onderwerp = f"{d.get('datum','?')} {d.get('dossier') or d.get('klant') or ''}".strip()
            if not rij:
                self.ag.log(onderwerp, "fout", f"impuls zonder rij op het bord: {it.get('titel','')[:80]}")
                bord.opgepakt(it["id"], self.naam)
                continue
            try:
                if fase == "voorbereiding":
                    self.voorbereiding(rij, onderwerp)
                elif fase == "verslag":
                    pk = self.meet_pakket(rij)
                    self.bewaar(uniek, pakket=pk, stand="pakket klaar" if not rij.get("proef_pad") else rij["stand"])
                    self.ag.log(onderwerp, "bevinding", f"pakket vol: {pk['fotos']} foto's, {pk['transcripten']} transcript(en), "
                                f"{pk['documenten']} document(en); klaar voor verslag, wacht op de knop Proef maken")
                gedaan += 1
            except Exception as e:  # noqa: BLE001
                self.ag.log(onderwerp, "fout", f"impuls {fase} mislukt: {type(e).__name__}: {str(e)[:200]}")
            bord.opgepakt(it["id"], self.naam)
        return gedaan

    def voorbereiding(self, rij, onderwerp):
        uniek = rij["uniek"]
        dossiermap = rij.get("dossiermap") or ""
        hoe = "door Mehdi gezet"
        if not dossiermap:
            dossiermap, hoe = self.zoek_dossiermap(rij)
        if not dossiermap:
            self.ag.log(onderwerp, "bevinding", f"geen dossiermap gevonden in {len(self.s['basismappen'])} basismap(pen) "
                        f"(nummer '{rij.get('dossier')}', adres '{rij.get('adres')}', klant '{rij.get('klant')}')")
            self.bewaar(uniek, pakket={"agenda": True, "dossiermap": False, "bezoekmap": False}, stand="voorbereid")
            self._noden.append({"tekst": f"{onderwerp}: dossiermap niet gevonden; zet het pad op de pagina Commandocentrum", "wie": "mehdi"})
            return
        bezoekmap, nieuw = self.maak_bezoekmap(rij, dossiermap)
        rij = {**rij, "dossiermap": dossiermap, "bezoekmap": bezoekmap}
        pk = self.meet_pakket(rij)
        self.bewaar(uniek, dossiermap=dossiermap, bezoekmap=bezoekmap, pakket=pk, stand="voorbereid")
        self.ag.log(onderwerp, "schrijf", f"dossiermap gevonden ({hoe}); bezoekmap {'aangemaakt' if nieuw else 'bestond al'}: {bezoekmap}")

    # -------------------------------------------------------- opdrachten ---
    def opdrachten(self):
        items = [it for it in bord.klaargezet_voor(self.naam, n=30) if it.get("soort") == "opdracht"]
        gedaan = 0
        for it in reversed(items):
            m = re.match(r"proef\s+(\d+)", it.get("titel", ""))
            # Regel van Mehdi (13-09-2026): alleen opdrachten van de knop op het bord kosten tokens.
            if not m or not str(it.get("van", "")).startswith("bord:"):
                self.ag.log(it.get("sleutel", "?"), "besluit", f"opdracht overgeslagen (niet van de knop): {it.get('titel','')} van {it.get('van','')}")
                bord.opgepakt(it["id"], self.naam)
                continue
            rij = self.rij(vid=int(m.group(1)))
            onderwerp = f"{rij.get('datum')} {rij.get('dossier') or rij.get('klant') or ''}".strip() if rij else m.group(1)
            try:
                if not rij:
                    raise RuntimeError("rij niet gevonden op het bord")
                self.proef(rij, onderwerp)
                gedaan += 1
            except Exception as e:  # noqa: BLE001
                self.ag.log(onderwerp, "fout", f"proef mislukt: {type(e).__name__}: {str(e)[:300]}")
                if rij:
                    self.bewaar(rij["uniek"], stand="pakket klaar")
            bord.opgepakt(it["id"], self.naam)
        return gedaan

    def proef(self, rij, onderwerp):
        if not rij.get("bezoekmap"):
            raise RuntimeError("geen bezoekmap; eerst de voorbereiding (dossiermap)")
        teksten, fotos, opnames = wp.lees_bezoekmap(rij["bezoekmap"])
        self.ag.log(onderwerp, "bron", f"bezoekmap gelezen: {len(teksten)} tekstbron(nen), {len(fotos)} foto's, {len(opnames)} opname(s)",
                    [t["naam"] + f" ({len(t['tekst'])} tekens)" for t in teksten])
        kop = (f"{self.s['label']} - dossier {rij.get('dossier') or '(geen nummer)'}, {rij.get('adres','')}, klant {rij.get('klant','')}. "
               f"Bezoek op {rij['datum']} van {(rij.get('start') or '')[11:16]} tot {(rij.get('einde') or '')[11:16]}. "
               f"Bezoekmap: {rij['bezoekmap']}." + (f"\nOpmerking van Mehdi: {rij['opmerking']}" if rij.get("opmerking") else ""))
        bundel = wp.bronnenbundel(teksten) + wp.fotolijst(fotos)
        resp = wp._client().messages.create(model=wp.MODEL, max_tokens=16000, system=_systeem(self.s),
                                            messages=[{"role": "user", "content": kop + "\n\n## BRONNEN\n" + bundel}],
                                            tools=[VERSLAG_SCHEMA], tool_choice={"type": "tool", "name": "verslag"})
        v = wp._tool(resp)
        afgekapt = resp.stop_reason == "max_tokens"
        beelden = {}
        gevraagd = {n for h in v.get("hoofdstukken") or [] for p in h.get("punten") or [] for n in (p.get("fotos") or [])}
        for f in fotos:
            if f["naam"] in gevraagd and f["naam"].lower().endswith((".jpg", ".jpeg", ".png")) and len(beelden) < 24:
                try:
                    beelden[f["naam"]] = bronnen.download(f["pad"])
                except Exception:  # noqa: BLE001
                    pass
        md = _md(v, self.s, rij)
        docx = _docx(v, self.s, rij, beelden)
        naam = f"{self.s.get('verslagtitel', self.s['label'])} {rij.get('dossier') or rij.get('klant') or ''} {rij['datum']} (concept)".strip()
        pad_docx = bronnen.upload(f"{rij['bezoekmap']}/{naam}.docx", docx)
        bronnen.upload(f"{rij['bezoekmap']}/{naam}.md", md.encode("utf-8"))
        n_punten = sum(len(h.get("punten") or []) for h in v.get("hoofdstukken") or [])
        info = {"hoofdstukken": len(v.get("hoofdstukken") or []), "punten": n_punten, "fotos": len(beelden),
                "open": len(v.get("open_punten") or []), "docx_kb": len(docx) // 1024, "model": wp.MODEL,
                "tokens": f"{resp.usage.input_tokens}+{resp.usage.output_tokens}", "afgekapt": afgekapt}
        extra = ""
        if self.s.get("pijplijn") == "barsten_en_scheuren":
            extra = self.pijplijn_klaarzetten(rij, teksten, fotos)
        self.bewaar(rij["uniek"], proef_pad=pad_docx, proef_ts=date.today().isoformat(), verslag_md=md, proef_info=info, stand="proef klaar")
        self.ag.log(onderwerp, "proef" if not afgekapt else "fout",
                    f"proef gezet: {os.path.basename(pad_docx)} ({info['docx_kb']} kB, {n_punten} punten, {len(beelden)} foto's, "
                    f"{info['open']} open punten; {info['tokens']} tokens{'; AFGEKAPT op max_tokens' if afgekapt else ''})" + extra)

    def pijplijn_klaarzetten(self, rij, teksten, fotos):
        """Barsten en scheuren: het dossier in de vorm die ~/barsten_en_scheuren verwacht (Transcript.docx, photos/, meta.json),
        zodat de bestaande pijplijn (DOV-bodemdata, handboek-checklist, RAPPORT.docx) er verder mee kan."""
        try:
            from docx import Document
            naam = re.sub(r"[^A-Za-z0-9]+", "_", f"{rij.get('dossier') or rij.get('klant') or 'dossier'}_{rij['datum']}").strip("_")
            doel = os.path.join(BS_DOSSIERS, naam)
            os.makedirs(os.path.join(doel, "photos"), exist_ok=True)
            doc = Document()
            for t in teksten:
                if "transcript" in t["naam"].lower() or t["naam"].lower().endswith("verslag.md"):
                    doc.add_heading(t["naam"], level=1)
                    for regel in t["tekst"].splitlines():
                        doc.add_paragraph(regel)
            doc.save(os.path.join(doel, "Transcript.docx"))
            n = 0
            for i, f in enumerate(sorted(fotos, key=lambda x: x["naam"]), 1):
                if not f["naam"].lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                with open(os.path.join(doel, "photos", f"{i:03d}_{f['naam']}"), "wb") as fh:
                    fh.write(bronnen.download(f["pad"]))
                n += 1
            json.dump({"adres": rij.get("adres") or "", "building": rij.get("adres") or "", "projectnr": rij.get("dossier") or "",
                       "x": None, "y": None, "bron": rij.get("bezoekmap"), "klant": rij.get("klant")},
                      open(os.path.join(doel, "meta.json"), "w"), ensure_ascii=False, indent=1)
            return f"; pijplijn-dossier klaargezet: {doel} ({n} foto's); Lambert72 x/y nog in te vullen op het BS-dashboard"
        except Exception as e:  # noqa: BLE001
            return f"; pijplijn-dossier NIET klaargezet: {type(e).__name__}: {str(e)[:120]}"

    # ------------------------------------------------------------- ronde ---
    def ronde(self):
        self._noden = []
        self.ag.hartslag("actief", taak="impulsen en opdrachten")
        try:
            n_i = self.impulsen()
            n_o = self.opdrachten()
            gemeten = 0
            for rij in self.rijen():
                onderwerp = f"{rij['datum']} {rij.get('dossier') or rij.get('klant') or ''}".strip()
                if not rij.get("dossiermap") and rij.get("impuls_voorbereiding_ts"):
                    # nog geen dossiermap: elke ronde opnieuw zoeken (Mehdi kan de map intussen gemaakt hebben) en de nood
                    # opnieuw melden, want een hartslag zonder de nood sluit hem op het bord
                    pad, hoe = self.zoek_dossiermap(rij)
                    if pad:
                        self.voorbereiding(rij, onderwerp)
                        continue
                    self._noden.append({"tekst": f"{onderwerp}: dossiermap niet gevonden; zet het pad op de pagina Commandocentrum", "wie": "mehdi"})
                elif rij.get("dossiermap") and not rij.get("bezoekmap"):
                    self.voorbereiding(rij, onderwerp)   # pad door Mehdi gezet: bezoekmap alsnog aanmaken
                if rij.get("bezoekmap") and not rij.get("proef_pad"):
                    pk = self.meet_pakket(rij)
                    oud = rij.get("pakket") or {}
                    if any(pk.get(k) != oud.get(k) for k in ("fotos", "opnames", "transcripten", "documenten", "bezoekmap")):
                        self.bewaar(rij["uniek"], pakket=pk)
                        self.ag.log(f"{rij['datum']} {rij.get('dossier') or rij.get('klant') or ''}", "bevinding",
                                    f"pakket gemeten: {pk['fotos']} foto's, {pk['opnames']} opname(s), {pk['transcripten']} transcript(en), {pk['documenten']} document(en)")
                    gemeten += 1
            self.ag.log_verstuur()
            self.ag.hartslag("klaar" if (n_i or n_o) else "waakt", taak=f"{n_i} impuls(en), {n_o} proef/proeven; {gemeten} pakket(ten) gemeten",
                             detail="impulsen van het Commandocentrum; proef alleen op de knop", nood=self._noden[:6])
        except Exception as e:  # noqa: BLE001
            self.ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
            self.ag.log_verstuur()
            self.ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
            raise

    def main(self):
        p = argparse.ArgumentParser()
        p.add_argument("--proef", type=int, metavar="ID", help="handmatig: proef voor rij <id> (kost tokens)")
        p.add_argument("--meet", action="store_true", help="alleen pakketten meten")
        a = p.parse_args()
        self._noden = []
        if a.proef:
            rij = self.rij(vid=a.proef)
            self.proef(rij, f"{rij['datum']} {rij.get('dossier') or rij.get('klant')}")
            self.ag.log_verstuur()
            return
        self.ronde()

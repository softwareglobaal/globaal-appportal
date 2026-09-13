"""Voorbereiden en proef maken: het werk van Werfverslag schrijver.

Twee stappen, naar het patroon van het contractsysteem (gegevens met herkomst, dan een proef):
  voorbereid(dossier, bezoek): leest alles in de bezoekmap (docx, pdf, pptx, md, txt), haalt er met
      claude-opus-5 de gegevens uit (bouwheer, aannemer, aanwezigen, doel, ...) met bron en zekerheid,
      plus de vaststellingen per onderdeel; zet ze op het bord (herkomst).
  proef(dossier, bezoek): schrijft uit de gegevens, de keuzes van Mehdi en de bronteksten het
      concept-werfverslag in het eigen sjabloon (sjabloon_werfverslag.py, geleerd uit Archisnapper)
      als Word en als markdown, met de foto's uit de bezoekmap of uit de dia's van een pptx, en zet
      beide in de bezoekmap in Dropbox als `<nr>-N werfverslag (concept).docx/.md`. Nooit overschrijven.

Regels: niets verzinnen (E8): wat niet in de bronnen staat, krijgt "(in te vullen)" of "(na te kijken)".
De sleutel ANTHROPIC_API_KEY komt uit ~/agents/.env; nooit in code of logboek.
"""
import io
import json
import os
import re
import sys
import zipfile
from datetime import date

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import bronnen  # noqa: E402
import sjabloon_werfverslag as sjab  # noqa: E402

MODEL = os.environ.get("WERFVERSLAG_MODEL", "claude-opus-5")
MAX_BRON_TEKENS = 60000
MAX_FOTOS = 24
MAX_FOTO_BYTES = 6_000_000


def _env(pad):
    pad = os.path.expanduser(pad)
    if not os.path.exists(pad):
        return
    for regel in open(pad):
        regel = regel.strip()
        if regel and not regel.startswith("#") and "=" in regel:
            k, v = regel.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_env("~/agents/.env")
_env("~/appportal/.env")


# ------------------------------------------------------------ bronnen lezen ---
def docx_tekst(b):
    z = zipfile.ZipFile(io.BytesIO(b))
    x = z.read("word/document.xml").decode("utf8", "replace")
    x = re.sub(r"</w:p>", "\n", x)
    x = re.sub(r"<w:tab/>", "\t", x)
    return re.sub(r"[ \t]+", " ", re.sub(r"<[^>]+>", "", x)).strip()


def pptx_tekst(b):
    z = zipfile.ZipFile(io.BytesIO(b))
    dia = sorted((k for k in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", k)),
                 key=lambda k: int(re.search(r"(\d+)", k).group(1)))
    uit = []
    for k in dia:
        x = z.read(k).decode("utf8", "replace")
        t = " ".join(re.findall(r"<a:t>([^<]*)</a:t>", x))
        n = int(re.search(r"(\d+)", k).group(1))
        if t.strip():
            uit.append(f"dia {n}: {t.strip()}")
    media = sum(1 for k in z.namelist() if k.startswith("ppt/media/"))
    return f"({len(dia)} dia's, {media} afbeeldingen; verwijs naar een foto als 'dia N')\n" + "\n".join(uit)


def pptx_fotos(b, dias):
    """De afbeeldingen van de gevraagde dia's: dict 'dia N' -> bytes (eerste, grootste afbeelding per dia)."""
    z = zipfile.ZipFile(io.BytesIO(b))
    uit = {}
    for n in dias:
        rel = f"ppt/slides/_rels/slide{n}.xml.rels"
        if rel not in z.namelist():
            continue
        doelen = re.findall(r'Target="\.\./media/([^"]+)"', z.read(rel).decode("utf8", "replace"))
        beste = None
        for d in doelen:
            if not d.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            data = z.read(f"ppt/media/{d}")
            if beste is None or len(data) > len(beste):
                beste = data
        if beste and len(beste) <= MAX_FOTO_BYTES:
            uit[f"dia {n}"] = beste
    return uit


def pdf_tekst(b, max_blz=12):
    try:
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(b))
        return "\n".join((p.extract_text() or "") for p in r.pages[:max_blz])
    except Exception as e:  # noqa: BLE001
        return f"(pdf niet leesbaar: {type(e).__name__})"


def lees_bezoekmap(bezoekmap):
    """Alle leesbare bestanden in de bezoekmap: [{naam, pad, tekst}], plus foto's en opnames (namen en paden)."""
    items = bronnen.lijst(bezoekmap) or []
    teksten, fotos, opnames = [], [], []
    for e in items:
        if e.get(".tag") != "file":
            continue
        pad, naam = e["path_display"], e["name"]
        laag = naam.lower()
        if laag.startswith(".") or "(concept)" in laag:
            continue
        try:
            if laag.endswith((".jpg", ".jpeg", ".heic", ".png")):
                fotos.append({"naam": naam, "pad": pad, "grootte": e.get("size", 0)})
            elif laag.endswith((".mp3", ".mp4", ".m4a", ".wav")):
                opnames.append(naam)
            elif laag.endswith(".docx"):
                teksten.append({"naam": naam, "pad": pad, "tekst": docx_tekst(bronnen.download(pad))})
            elif laag.endswith(".pptx"):
                teksten.append({"naam": naam, "pad": pad, "tekst": pptx_tekst(bronnen.download(pad)), "pptx": True})
            elif laag.endswith(".pdf") and e.get("size", 0) < 6_000_000:
                teksten.append({"naam": naam, "pad": pad, "tekst": pdf_tekst(bronnen.download(pad))})
            elif laag.endswith((".md", ".txt")):
                teksten.append({"naam": naam, "pad": pad, "tekst": bronnen.download(pad).decode("utf8", "replace")})
        except Exception as ex:  # noqa: BLE001
            teksten.append({"naam": naam, "pad": pad, "tekst": f"(niet leesbaar: {type(ex).__name__})"})
    return teksten, fotos, opnames


def bronnenbundel(teksten, maximum=MAX_BRON_TEKENS):
    per = max(4000, maximum // max(1, len(teksten)))
    delen = []
    for t in teksten:
        tekst = t["tekst"]
        if len(tekst) > per:
            tekst = tekst[:per] + f"\n(... ingekort, {len(t['tekst'])} tekens in totaal)"
        delen.append(f"### BRON: {t['naam']}\n{tekst}")
    return "\n\n".join(delen)


# ------------------------------------------------------------- Claude ---
GEGEVENS_SCHEMA = {
    "name": "gegevens",
    "description": "De gegevens van het werfbezoek, elk met bron en zekerheid.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verslagtype_voorstel": {"type": "string", "enum": ["werfverslag", "vaststellingsverslag", "opleveringsverslag"],
                                     "description": "werfverslag bij lopende werken; vaststellingsverslag bij schade of geschil; opleveringsverslag bij oplevering"},
            "situatie": {"type": "string", "description": "de situatie op de werf in 5 tot 10 zinnen, alleen uit de bronnen"},
            "onderdelen": {"type": "array", "description": "vaststellingen per bouwonderdeel, kort", "items": {"type": "object", "properties": {
                "onderdeel": {"type": "string"},
                "vaststellingen": {"type": "array", "items": {"type": "string"}},
                "bron": {"type": "string"},
            }, "required": ["onderdeel", "vaststellingen", "bron"]}},
            "acties": {"type": "array", "items": {"type": "object", "properties": {
                "wie": {"type": "string"}, "wat": {"type": "string"}, "tegen": {"type": "string"}}, "required": ["wie", "wat"]}},
            "ontbreekt": {"type": "array", "items": {"type": "string"}, "description": "wat de architect nog moet aanleveren of nakijken vóór het verslag af is"},
            "gegevens": {"type": "array", "description": "kort: waarde in één regel, bron in één regel", "items": {"type": "object", "properties": {
                "veld": {"type": "string"},
                "waarde": {"type": "string"},
                "bron": {"type": "string", "description": "bestandsnaam en plaats waar het staat, of 'niet gevonden'"},
                "zekerheid": {"type": "string", "enum": ["zeker", "na te kijken", "ontbreekt"]},
            }, "required": ["veld", "waarde", "bron", "zekerheid"]}},
        },
        "required": ["gegevens", "situatie", "onderdelen", "acties", "ontbreekt", "verslagtype_voorstel"],
    },
}

VELDEN = ["bouwheer", "adres werf", "aannemer", "datum werfbezoek", "aanwezigen", "opdrachtgever van het verslag",
          "doel van het verslag", "contract H-Architects (opdracht)", "gebreken gemeld door de bouwheer",
          "schade en meerkosten gemeld door de bouwheer", "openstaande facturen", "juridische stand"]

SYSTEEM_VOORBEREID = """Je bent de voorbereider van werfverslagen van H-Architects (België). Je leest de bronnen van één
werfbezoek en haalt er de gegevens uit. Regel E8 van het kantoor: je verzint niets. Wat niet in de bronnen staat,
krijgt waarde "(in te vullen)" en zekerheid "ontbreekt". Wat je afleidt maar niet letterlijk leest, krijgt "na te
kijken". Elke waarde krijgt de bron (bestandsnaam, en waar in het bestand). Namen van externen: de firmanaam.
Datums als JJJJ-MM-DD. Schrijf in het Nederlands, zakelijk, zonder emoji. Vul minstens deze velden in: """ + ", ".join(VELDEN)

CATEGORIEEN = ["Algemeen", "Veiligheidscoördinatie", "EPB", "Afbraak", "Ruwbouw", "Dakwerken", "Buitenschrijnwerk",
               "Buitenwerk en gevel", "Riolering en afvoer", "Technieken", "Binnenafwerking", "Nieuw besproken punten"]

VERSLAG_SCHEMA = {
    "name": "werfverslag",
    "description": "Het werfverslag in het sjabloon van H-Architects.",
    "input_schema": {
        "type": "object",
        "properties": {
            "status_nl": {"type": "string", "description": "status van de werf, 1 tot 3 zinnen"},
            "status_en": {"type": "string", "description": "zelfde in het Engels, leeg als geen Engels gevraagd"},
            "aanwezigen": {"type": "array", "items": {"type": "object", "properties": {
                "rol": {"type": "string"}, "firma": {"type": "string"}, "naam": {"type": "string"},
                "contact": {"type": "string"}, "aanwezig": {"type": "string", "description": "ja | nee | (na te kijken)"}},
                "required": ["rol", "firma", "naam", "contact", "aanwezig"]}},
            "categorieen": {"type": "array", "items": {"type": "object", "properties": {
                "naam": {"type": "string", "enum": CATEGORIEEN},
                "punten": {"type": "array", "items": {"type": "object", "properties": {
                    "titel": {"type": "string"},
                    "datum": {"type": "string", "description": "JJJJ-MM-DD van de vaststelling"},
                    "vlag": {"type": "string", "enum": ["", "ok", "belangrijk", "dringend"]},
                    "tekst_nl": {"type": "string"},
                    "tekst_en": {"type": "string", "description": "leeg als geen Engels gevraagd"},
                    "verantwoordelijke": {"type": "string"},
                    "fotos": {"type": "array", "items": {"type": "string"}, "description": "bijschriften: 'dia 14' voor een pptx-dia, of een bestandsnaam uit de bezoekmap"},
                }, "required": ["titel", "datum", "vlag", "tekst_nl", "tekst_en", "verantwoordelijke", "fotos"]}},
            }, "required": ["naam", "punten"]}},
            "raming": {"type": "array", "description": "alleen bij een vaststellingsverslag; bedragen alleen uit de bronnen", "items": {"type": "object", "properties": {
                "onderdeel": {"type": "string"}, "herstelling": {"type": "string"}, "raming": {"type": "string"}},
                "required": ["onderdeel", "herstelling", "raming"]}},
            "acties": {"type": "array", "items": {"type": "object", "properties": {
                "wie": {"type": "string"}, "wat": {"type": "string"}, "tegen": {"type": "string"}}, "required": ["wie", "wat", "tegen"]}},
            "volgend": {"type": "string"},
            "akkoord": {"type": "array", "items": {"type": "object", "properties": {"partij": {"type": "string"}, "naam": {"type": "string"}}, "required": ["partij", "naam"]}},
        },
        "required": ["status_nl", "status_en", "aanwezigen", "categorieen", "raming", "acties", "volgend", "akkoord"],
    },
}

SYSTEEM_PROEF = """Je bent Werfverslag schrijver van H-Architects (België). Je schrijft het concept-werfverslag voor de klant
in het sjabloon van het kantoor, geleerd uit meer dan duizend eerdere verslagen (Archisnapper): status van de werf,
contactpersonen en aanwezigen, waarnemingen per categorie, elk genummerd en gedateerd, met een vlag (OK als het punt
in orde is, Belangrijk, Dringend, of niets), een verantwoordelijke en de foto's die erbij horen, dan actiepunten,
volgend werfbezoek en voor akkoord.

Regels:
- Niets verzinnen (E8). Wat onzeker is krijgt "(na te kijken)", wat ontbreekt "(in te vullen)". Bedragen alleen als
  ze in de bronnen staan; anders "(raming door de architect in te vullen)".
- Elke waarneming is één concreet punt met een korte titel, de datum waarop het werd vastgesteld en, waar de bron dat
  toelaat, de foto's ("dia 14" voor een dia uit een pptx, of de bestandsnaam van een foto in de bezoekmap).
- Geen juridische conclusies (wie aansprakelijk is): beschrijf vaststellingen; verwijs voor de rest naar de raadsman.
- Bij een vaststellingsverslag (schade, geschil) komt er een tabel raming van de herstelkosten per onderdeel.
- Bij een werfverslag voor lopende werken komen de doorlopende punten (omgevingsloket, werfbezoeken, orde en netheid,
  facturatie, veiligheidscoördinatie, EPB) er automatisch bij; jij schrijft ze niet.
- Nederlands, zakelijk, geen emoji, geen kastlijntjes (gewoon koppelteken). Engels alleen als de keuzes dat vragen.
- Volg de keuzes van Mehdi (verslagtype, taal, aanwezigen, categorieën) als die gegeven zijn; ze winnen van je eigen inschatting."""


def _client():
    from anthropic import Anthropic
    return Anthropic()


def _tool(resp):
    for blok in resp.content:
        if getattr(blok, "type", "") == "tool_use":
            return blok.input
    return {}


def vraag_gegevens(kop, bundel):
    resp = _client().messages.create(model=MODEL, max_tokens=14000, system=SYSTEEM_VOORBEREID,
                                     messages=[{"role": "user", "content": kop + "\n\n" + bundel}],
                                     tools=[GEGEVENS_SCHEMA], tool_choice={"type": "tool", "name": "gegevens"})
    uit = _tool(resp)
    if resp.stop_reason == "max_tokens":
        uit["_afgekapt"] = True
    return uit, resp.usage


def vraag_verslag(kop, gegevens, keuzes, bundel):
    user = (kop + "\n\n## KEUZES VAN MEHDI\n" + json.dumps(keuzes, ensure_ascii=False, indent=1)
            + "\n\n## GEGEVENS (uit de voorbereiding, met bron en zekerheid)\n" + json.dumps(gegevens, ensure_ascii=False, indent=1)
            + "\n\n## BRONNEN\n" + bundel)
    resp = _client().messages.create(model=MODEL, max_tokens=16000, system=SYSTEEM_PROEF,
                                     messages=[{"role": "user", "content": user}],
                                     tools=[VERSLAG_SCHEMA], tool_choice={"type": "tool", "name": "werfverslag"})
    return _tool(resp), resp.usage


# ---------------------------------------------------------------- stappen ---
def _rij(dossier, volgnr):
    r = bord.call(f"/api/werfbezoek?dossier={dossier}&volgnr={volgnr}")
    rijen = r.get("rijen") or []
    if not rijen:
        raise RuntimeError(f"bezoek {dossier}-{volgnr} staat niet op het bord; Werfverslag voorbereider moet eerst verifiëren")
    return rijen[0]


def _bewaar(rij, dossier, volgnr, **velden):
    velden["_alleen"] = list(velden)
    bord.call("/api/werfbezoek", {"rijen": [{"dossier": dossier, "datum": rij["datum"], "bezoekmap": rij["bezoekmap"], "volgnr": volgnr, **velden}]})


def voorbereid(ag, dossier, volgnr):
    rij = _rij(dossier, volgnr)
    ag.log(f"{dossier}-{volgnr}", "bron", f"bezoekmap lezen: {rij['bezoekmap']}")
    teksten, fotos, opnames = lees_bezoekmap(rij["bezoekmap"])
    ag.log(f"{dossier}-{volgnr}", "bron", f"{len(teksten)} tekstbron(nen), {len(fotos)} foto's, {len(opnames)} opname(s) gelezen",
           [t["naam"] + f" ({len(t['tekst'])} tekens)" for t in teksten])
    kop = (f"Dossier {dossier}, {rij.get('adres','')}. Werfbezoek {volgnr} op {rij['datum']}. "
           f"Bezoekmap: {rij['bezoekmap']}. Foto's in de map: {len(fotos)}; opnames: {len(opnames)}.")
    uit, usage = vraag_gegevens(kop, bronnenbundel(teksten))
    uit["bronbestanden"] = [t["naam"] for t in teksten]
    uit["fotos_in_map"] = [f["naam"] for f in fotos]
    uit["opnames_in_map"] = opnames
    ag.log(f"{dossier}-{volgnr}", "bevinding" if not uit.get("_afgekapt") else "fout",
           f"{len(uit.get('gegevens', []))} gegevens, {len(uit.get('onderdelen', []))} onderdelen, "
           f"{len(uit.get('ontbreekt', []))} open punten; voorstel verslagtype: {uit.get('verslagtype_voorstel')} "
           f"({usage.input_tokens}+{usage.output_tokens} tokens{'; AFGEKAPT op max_tokens' if uit.get('_afgekapt') else ''})")
    bijlagen = [{"naam": t["naam"], "pad": t["pad"], "soort": "document", "tekens": len(t["tekst"])} for t in teksten] + \
               [{"naam": f["naam"], "pad": f["pad"], "soort": "foto", "grootte": f["grootte"]} for f in fotos] + \
               [{"naam": o, "soort": "opname"} for o in opnames]
    _bewaar(rij, dossier, volgnr, gegevens=uit, bijlagen=bijlagen)
    return uit


def _fotos_verzamelen(teksten, fotos, verslag):
    """Foto's die het verslag noemt: 'dia N' uit de pptx-bronnen, of bestandsnamen uit de bezoekmap (jpg/png)."""
    gevraagd = []
    for cat in verslag.get("categorieen", []):
        for p in cat.get("punten", []):
            gevraagd += p.get("fotos", [])
    gevraagd = list(dict.fromkeys(gevraagd))[:MAX_FOTOS]
    uit = {}
    dias = sorted({int(m.group(1)) for b in gevraagd for m in [re.match(r"dia\s*(\d+)", b, re.I)] if m})
    if dias:
        for t in teksten:
            if t.get("pptx"):
                try:
                    uit.update(pptx_fotos(bronnen.download(t["pad"]), dias))
                except Exception:  # noqa: BLE001
                    pass
    per_naam = {f["naam"]: f for f in fotos}
    for b in gevraagd:
        f = per_naam.get(b)
        if f and f["naam"].lower().endswith((".jpg", ".jpeg", ".png")) and f["grootte"] <= MAX_FOTO_BYTES:
            try:
                uit[b] = bronnen.download(f["pad"])
            except Exception:  # noqa: BLE001
                pass
    # bijschriften normaliseren: 'Dia 14' -> 'dia 14'
    for cat in verslag.get("categorieen", []):
        for p in cat.get("punten", []):
            p["fotos"] = [re.sub(r"^dia\s*(\d+)$", r"dia \1", b.strip(), flags=re.I) for b in p.get("fotos", [])]
    return uit


def _nummer_punten(verslag, volgnr, doorlopend):
    """Nummering <verslag>.<punt> zoals Archisnapper; doorlopende punten uit verslag 1 vooraan bij een werfverslag."""
    cats = []
    if doorlopend:
        per = {}
        for cat, titel, tekst, wie in sjab.DOORLOPEND:
            per.setdefault(cat, []).append({"titel": titel, "datum": "", "vlag": "", "tekst_nl": tekst, "tekst_en": "",
                                            "verantwoordelijke": wie, "fotos": [], "doorlopend": True})
        for cat, punten in per.items():
            cats.append({"naam": cat, "punten": punten})
    for cat in verslag.get("categorieen", []):
        doel = next((c for c in cats if c["naam"] == cat["naam"]), None)
        if doel:
            doel["punten"] += cat.get("punten", [])
        else:
            cats.append({"naam": cat["naam"], "punten": list(cat.get("punten", []))})
    i = 0
    for cat in cats:
        for p in cat["punten"]:
            i += 1
            p["nummer"] = f"{1 if p.get('doorlopend') else volgnr}.{i}"
    return cats


def proef(ag, dossier, volgnr):
    rij = _rij(dossier, volgnr)
    gegevens = rij.get("gegevens") or {}
    if not gegevens.get("gegevens"):
        gegevens = voorbereid(ag, dossier, volgnr)
        rij = _rij(dossier, volgnr)
    keuzes = rij.get("keuzes") or {}
    verslagtype = keuzes.get("verslagtype") or gegevens.get("verslagtype_voorstel") or "werfverslag"
    taal = keuzes.get("taal") or "nl"
    teksten, fotos, opnames = lees_bezoekmap(rij["bezoekmap"])
    vandaag = date.today().isoformat()
    nr_label = (rij.get("bronnen") or {}).get("nr_label") or str(volgnr)
    soort_bezoek = (rij.get("bronnen") or {}).get("soort_bezoek", "werfbezoek")
    kop = (f"Dossier {dossier}, {rij.get('adres','')}. {soort_bezoek.capitalize()} {nr_label} op {rij['datum']}; verslagnummer {dossier}-{nr_label}"
           + (" (plaatsbezoek vóór de werfstart: geen werfverslagnummer, titel 'Verslag plaatsbezoek')" if soort_bezoek == "plaatsbezoek" else "") + ". "
           f"Verslagtype: {verslagtype}. Taal: {'Nederlands en Engels' if taal == 'nl+en' else 'alleen Nederlands (tekst_en en status_en leeg laten)'}. "
           f"Datum van opmaak: {vandaag}. Foto's in de map: {', '.join(f['naam'] for f in fotos) or 'geen'}; opnames: {', '.join(opnames) or 'geen'}.")
    ag.log(f"{dossier}-{volgnr}", "besluit", f"proef als {verslagtype}, taal {taal}, keuzes: {', '.join(k for k in keuzes if keuzes[k]) or 'geen'}")
    uit, usage = vraag_verslag(kop, gegevens, keuzes, bronnenbundel(teksten))
    if keuzes.get("aanwezigen"):
        uit["aanwezigen"] = keuzes["aanwezigen"]
    br = rij.get("bronnen") or {}
    verslag = {"dossier": dossier, "bezoek": br.get("nr_label") or str(volgnr), "soort_bezoek": br.get("soort_bezoek", "werfbezoek"),
               "adres": rij.get("adres", ""), "datum": rij["datum"], "opgemaakt": vandaag,
               "verslagtype": verslagtype, "bronnen_kort": f"{len(teksten)} document(en), {len(fotos)} foto's en {len(opnames)} opname(s) in de bezoekmap",
               "status_nl": uit.get("status_nl", ""), "status_en": uit.get("status_en", "") if taal == "nl+en" else "",
               "aanwezigen": uit.get("aanwezigen", []), "raming": uit.get("raming", []) if verslagtype == "vaststellingsverslag" else [],
               "acties": uit.get("acties", []), "volgend": uit.get("volgend", ""), "akkoord": uit.get("akkoord", [])}
    verslag["categorieen"] = _nummer_punten(uit, volgnr, doorlopend=(verslagtype == "werfverslag" and keuzes.get("doorlopend", "ja") != "nee"))
    if taal != "nl+en":
        for cat in verslag["categorieen"]:
            for p in cat["punten"]:
                p["tekst_en"] = ""
    beelden = _fotos_verzamelen(teksten, fotos, verslag)
    md = sjab.naar_markdown(verslag)
    docx = sjab.naar_docx(verslag, beelden)
    naam = f"{dossier}-{verslag['bezoek']} {'verslag plaatsbezoek' if verslag['soort_bezoek'] == 'plaatsbezoek' else 'werfverslag'} (concept)"
    pad_md = bronnen.upload(f"{rij['bezoekmap']}/{naam}.md", md.encode("utf8"))
    pad_docx = bronnen.upload(f"{rij['bezoekmap']}/{naam}.docx", docx)
    telling = sjab.telling_open(md)
    n_punten = sum(len(c["punten"]) for c in verslag["categorieen"])
    ag.log(f"{dossier}-{volgnr}", "schrijf", f"proef gezet: {os.path.basename(pad_docx)} ({len(docx)//1024} kB, {n_punten} punten, "
           f"{len(beelden)} foto's) en {os.path.basename(pad_md)} in de bezoekmap; open: {telling} ({usage.input_tokens}+{usage.output_tokens} tokens)")
    _bewaar(rij, dossier, volgnr, verslag_md=md, proef_pad=pad_docx, proef_ts=vandaag,
            proef_info={"verslagtype": verslagtype, "taal": taal, "punten": n_punten, "fotos": len(beelden), "open": telling, "docx_kb": len(docx) // 1024})
    return pad_docx, md

"""De offertes van een lot lezen en vergelijken, voor De Offertevergelijker (overleg 30-10-2026, X4 en X5).

Lezen gebeurt lokaal: Dropbox (koppelingen/bronnen.py, alleen lezen) en pypdf. Een pagina zonder tekst maakt van die
offerte een scan: "OCR nodig", ze telt niet mee (X4). Uit de tekst haalt de code wat zeker is: het totaal exclusief en
inclusief btw, het btw-tarief, de datum, de geldigheid, en of het een raming is in plaats van een offerte.

De vergelijking per post vraagt het taalmodel. Dat mag pas na een ja van Mehdi (X5): tot dan staat OFFERTE_NAAR_AI op
False en vergelijkt de code alleen de totalen en de voorwaarden. Ook met het model gaat de tekst eerst door redigeer():
geen naam, adres, mailadres, telefoon of rekeningnummer van de bouwheer naar buiten.

De inschrijvers heten Inschrijver A, B, C in de volgorde van de bestanden. Een offerte van de andere firma krijgt een
letter zoals elke andere; haar naam komt nergens in de vergelijking (X4, harde regel van Mehdi).
"""
import io
import re
from datetime import date, datetime

from aankoop import privacy as P

from . import scheiding as S

OFFERTE_NAAR_AI = False      # X5: pas True na een uitdrukkelijk ja van Mehdi, met zijn antwoord in de commit
MIN_TEKST_PER_BLZ = 20
MAX_BLZ = 40
BEDRAG = (r"(?:€|eur|euro)?\s*(-?\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})|-?\d+(?:,\d{2})|-?\d{1,3}(?:,\d{3})*\.\d{2})"
          r"\s*(?:€|eur|euro)?")
RAMING = re.compile(r"\b(?:raming|kostenraming|schatting|indicatief|indicatieve prijs|budgetprijs|richtprijs)\b", re.I)
VERLEGD = re.compile(r"btw\s+verlegd|medecontractant|autoliquidatie|art(?:ikel)?\.?\s*20", re.I)


def bedrag(tekst):
    """'1.234,56' of '1 234,56' of '1,234.56' -> 1234.56; None als het geen bedrag is."""
    t = str(tekst or "").replace(" ", " ").strip()
    if re.fullmatch(r"-?\d{1,3}(?:,\d{3})*\.\d{2}", t):
        return float(t.replace(",", ""))
    t = re.sub(r"[.\s]", "", t).replace(",", ".")
    try:
        return round(float(t), 2)
    except ValueError:
        return None


def _laatste_bedrag(regel):
    gevonden = [bedrag(m.group(1)) for m in re.finditer(BEDRAG, regel, re.I)]
    gevonden = [b for b in gevonden if b is not None]
    return gevonden[-1] if gevonden else None


def _datum(tekst):
    m = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})\b", tekst)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def paginas(data):
    """[tekst per pagina] van een PDF, of None als de PDF niet te openen is."""
    try:
        from pypdf import PdfReader
        lezer = PdfReader(io.BytesIO(data))
        return [(p.extract_text() or "") for p in lezer.pages[:MAX_BLZ]]
    except Exception:  # noqa: BLE001  een kapotte of beveiligde PDF: niet leesbaar, nooit half
        return None


def lees(tekst_paginas):
    """Wat zeker uit de tekst te halen is: {soort, excl, incl, btw_tarief, verlegd, datum, geldig_tot, geldig_dagen,
    raming, redenen}. soort is 'offerte', 'scan' (OCR nodig) of 'onleesbaar'."""
    if tekst_paginas is None:
        return {"soort": "onleesbaar", "redenen": ["PDF niet te openen"]}
    leeg = [i + 1 for i, t in enumerate(tekst_paginas) if len(t.strip()) < MIN_TEKST_PER_BLZ]
    if not tekst_paginas or leeg:
        return {"soort": "scan", "redenen": [f"OCR nodig: pagina {', '.join(map(str, leeg)) or '1'} zonder tekst"]}
    tekst = "\n".join(tekst_paginas)
    uit = {"soort": "offerte", "excl": None, "incl": None, "btw_tarief": None, "verlegd": bool(VERLEGD.search(tekst)),
           "datum": _datum(tekst), "geldig_tot": None, "geldig_dagen": None, "raming": bool(RAMING.search(tekst)),
           "redenen": []}
    for regel in tekst.splitlines():
        laag = regel.lower()
        if "totaal" in laag or "total" in laag or "te betalen" in laag:
            b = _laatste_bedrag(regel)
            if b is None:
                continue
            if re.search(r"excl|exclusief|zonder btw|htva|netto|hors tva", laag):
                uit["excl"] = b
            elif re.search(r"incl|inclusief|tvac|te betalen|met btw", laag):
                uit["incl"] = b
        m = re.search(r"\b(6|12|21)\s?%", regel)
        if m and "btw" in laag and uit["btw_tarief"] is None:
            uit["btw_tarief"] = int(m.group(1))
        m = re.search(r"geldig\w*\s+tot\s+(?:en met\s+)?(\d{1,2}[-/.]\d{1,2}[-/.]20\d{2})", regel, re.I)
        if m:
            uit["geldig_tot"] = _datum(m.group(1))
        m = re.search(r"geldig\w*[^.\n]{0,30}?(\d{1,3})\s*(?:kalender)?dagen", regel, re.I)
        if m and not uit["geldig_dagen"]:
            uit["geldig_dagen"] = int(m.group(1))
    return controleer(uit)


def controleer(o):
    """Btw gelijk trekken en de rekensom nakijken. Een ontbrekend bedrag blijft None, nooit nul (X4)."""
    t = 0 if o.get("verlegd") else o.get("btw_tarief")
    if o.get("excl") is None and o.get("incl") is not None and t is not None:
        o["excl"] = round(o["incl"] / (1 + t / 100), 2)
        o["redenen"].append(f"exclusief btw berekend uit het totaal inclusief ({t} procent)")
    if o.get("excl") is not None and o.get("incl") is not None and t is not None:
        verwacht = round(o["excl"] * (1 + t / 100), 2)
        if abs(verwacht - o["incl"]) > max(1.0, o["excl"] * 0.001):
            o["redenen"].append(f"rekenfout: {o['excl']} plus {t} procent btw is {verwacht}, de offerte zegt {o['incl']}")
    if o.get("excl") is None:
        o["redenen"].append("geen totaal exclusief btw gevonden")
    if o.get("raming"):
        o["redenen"].append("dit lijkt een raming, geen offerte")
    if o.get("geldig_tot") is None and o.get("geldig_dagen") and o.get("datum"):
        o["geldig_tot"] = date.fromordinal(o["datum"].toordinal() + o["geldig_dagen"])
    return o


def redigeer(tekst, extra=()):
    """De tekst die naar het model mag (X5): mailadressen, telefoonnummers, rekeningnummers, rijksregisternummers, de
    regels met een aanspreking of 'klant'/'bouwheer', en de gegeven adressen en namen (bv. het werfadres) weg."""
    t = str(tekst or "")
    for soort, patroon in P.PATRONEN:
        if soort in ("e-mailadres", "rekeningnummer", "rijksregisternummer", "telefoonnummer"):
            t = patroon.sub(f"[{soort}]", t)
    t = re.sub(r"(?im)^\s*(?:aan|klant|bouwheer|opdrachtgever|t\.?a\.?v\.?)\s*:.*$", "[regel met de bouwheer weggelaten]", t)
    t = re.sub(r"\b(?i:dhr|mevr|mr|mevrouw|meneer|de heer|familie|fam)\.?\s+[A-ZÀ-Ý][\w'-]+(?:\s+[A-ZÀ-Ý][\w'-]+)*",
               "[naam weggelaten]", t)
    for stuk in extra:
        if stuk and len(stuk.strip()) >= 4:
            t = re.sub(re.escape(stuk.strip()), "[weggelaten]", t, flags=re.I)
    return t


def letters(bestanden, firma):
    """[(letter, bestand, sleutelregel)]: A, B, C in de volgorde van de bestanden. De sleutel voor Mehdi noemt de
    bestandsnaam, behalve bij de andere firma: daar alleen het volgnummer in de map en de datum."""
    uit = []
    for i, b in enumerate(bestanden):
        letter = chr(ord("A") + i) if i < 26 else f"Z{i}"
        naam = b.get("naam", "")
        if S.is_andere_firma(naam, firma):
            sleutel = f"bestand {i + 1} in de map ({(b.get('gewijzigd') or '')[:10]})"
        else:
            sleutel = naam
        uit.append((letter, b, sleutel))
    return uit


def vergelijk(offertes, vandaag):
    """De totalen naast elkaar: {rijen, laagste, hoogste, verschil, verschil_pct, letop}. offertes: [{letter, lees()}].
    Alleen offertes met een totaal exclusief btw doen mee aan laagste en hoogste; de rest staat er met de reden."""
    rijen, letop = [], []
    for o in offertes:
        d = o["lees"]
        rijen.append({"letter": o["letter"], **d})
        for r in d.get("redenen") or []:
            letop.append(f"Inschrijver {o['letter']}: {r}")
        if d.get("geldig_tot") and d["geldig_tot"] < vandaag:
            letop.append(f"Inschrijver {o['letter']}: offerte verlopen op {d['geldig_tot'].strftime('%d-%m-%Y')}")
    tarieven = {(0 if r.get("verlegd") else r.get("btw_tarief")) for r in rijen if r.get("soort") == "offerte"}
    tarieven.discard(None)
    if len(tarieven) > 1:
        letop.append("Het btw-tarief verschilt tussen de offertes: vergelijk exclusief btw.")
    mee = [r for r in rijen if r.get("soort") == "offerte" and r.get("excl") is not None and not r.get("raming")]
    mee.sort(key=lambda r: r["excl"])
    uit = {"rijen": rijen, "letop": letop, "laagste": mee[0] if mee else None, "hoogste": mee[-1] if mee else None}
    if len(mee) >= 2:
        uit["verschil"] = round(mee[-1]["excl"] - mee[0]["excl"], 2)
        uit["verschil_pct"] = round(100 * uit["verschil"] / mee[0]["excl"], 1) if mee[0]["excl"] else None
    return uit


def per_post(rijen_model, posten_per_letter):
    """De vergelijking per post uit de groepering van het model, nagerekend door de code. rijen_model:
    [{"onderwerp", "posten": {letter: [postnummers]}}]; posten_per_letter: {letter: {nr: totaal}} uit de extractie.
    Een lege lijst of een onbekend postnummer is "ontbreekt", nooit nul (X4)."""
    uit = []
    for rij in rijen_model or []:
        cellen = {}
        for letter, posten in posten_per_letter.items():
            nrs = [str(n) for n in ((rij.get("posten") or {}).get(letter) or [])]
            bedragen = [posten.get(n) for n in nrs]
            if not nrs or any(b is None for b in bedragen):
                cellen[letter] = None
            else:
                cellen[letter] = round(sum(bedragen), 2)
        uit.append({"onderwerp": str(rij.get("onderwerp") or ""), "cellen": cellen})
    return uit


POSTEN_VORM = """Lever precies een JSON-object tussen ```json en ```:
{"offertes": {"A": {"posten": [{"nr": "postnummer zoals in de offerte, of een volgnummer", "omschrijving": "kort",
  "hoeveelheid": null, "eenheid": null, "totaal": "het bedrag exclusief btw zoals het in de offerte staat",
  "optie": false}], "inbegrepen": ["..."], "uitgesloten": ["..."], "basis": "meetstaat, plannen (met datum of versie)
  of onbekend", "termijn": "uitvoeringstermijn of null", "betaling": "betalingsvoorwaarden of null"}},
 "rijen": [{"onderwerp": "een onderdeel van het werk", "posten": {"A": ["nr"], "B": []}}]}
Regels: neem bedragen letterlijk over, verzin niets; een onderdeel dat een inschrijver niet heeft, krijgt een lege lijst.
Opties en stelposten zet je met optie true. Geen advies over wie de opdracht krijgt."""


def posten_uit_model(teksten, client=None, model=None):
    """{letter: gegevens} en rijen uit het model, voor geredigeerde teksten {letter: tekst}. Alleen als
    OFFERTE_NAAR_AI True is (X5); anders een fout, zodat niemand het per ongeluk aanroept."""
    if not OFFERTE_NAAR_AI:
        raise PermissionError("offerte-inhoud naar de AI wacht op het ja van Mehdi (overleg X5)")
    from aankoop import onderzoek as O
    if client is None:
        from anthropic import Anthropic
        client = Anthropic(max_retries=1)
    stukken = "\n\n".join(f"=== INSCHRIJVER {l} ===\n{t[:60000]}" for l, t in sorted(teksten.items()))
    resp = client.messages.create(model=model or O.MODEL, max_tokens=16000, output_config={"effort": "medium"},
                                  system="Je haalt posten uit bouwoffertes en zet ze naast elkaar. Nederlands.\n\n"
                                  + POSTEN_VORM,
                                  messages=[{"role": "user", "content": stukken}])
    tekst = "".join(O._veld(b, "text", "") for b in (O._veld(resp, "content", []) or []) if O._veld(b, "type") == "text")
    return O.json_uit(tekst)


def bedrag_staat_in(waarde, tekst):
    """Staat dit bedrag letterlijk in de offerte (in een gangbare schrijfwijze)? Zo komt geen verzonnen bedrag in de
    vergelijking per post."""
    b = bedrag(waarde) if not isinstance(waarde, (int, float)) else round(float(waarde), 2)
    if b is None:
        return False
    geheel, dec = f"{abs(b):.2f}".split(".")
    met_punten = f"{int(geheel):,}".replace(",", ".")
    vormen = {f"{met_punten},{dec}", f"{geheel},{dec}", f"{int(geheel):,}.{dec}", f"{met_punten.replace('.', ' ')},{dec}"}
    t = str(tekst or "").replace("\u00a0", " ")
    return any(v in t for v in vormen)


def keur_posten(gegevens, teksten, totalen):
    """{letter: {nr: totaal}} van de posten die de code aanvaardt, en de redenen per letter. Een bedrag dat niet in de
    offerte staat, valt weg; kloppen de posten zonder opties niet met het totaal dat de code las, dan geen vergelijking
    per post voor die inschrijver."""
    aanvaard, redenen = {}, {}
    for letter, d in ((gegevens or {}).get("offertes") or {}).items():
        posten, weg = {}, []
        for p in d.get("posten") or []:
            if not isinstance(p, dict):
                continue
            if bedrag_staat_in(p.get("totaal"), teksten.get(letter, "")):
                posten[str(p.get("nr"))] = (bedrag(p["totaal"]) if not isinstance(p["totaal"], (int, float))
                                            else round(float(p["totaal"]), 2), bool(p.get("optie")))
            else:
                weg.append(f"post {p.get('nr')}: bedrag niet in de offerte gevonden")
        som = round(sum(b for b, optie in posten.values() if not optie), 2)
        totaal = totalen.get(letter)
        if totaal is not None and abs(som - totaal) > max(1.0, totaal * 0.005):
            weg.append(f"de posten tellen op tot {som}, de offerte zegt {totaal}: geen vergelijking per post")
            posten = {}
        aanvaard[letter] = {nr: b for nr, (b, _) in posten.items()}
        redenen[letter] = weg
    return aanvaard, redenen


def datumtekst(d):
    return d.strftime("%d-%m-%Y") if isinstance(d, (date, datetime)) else "onbekend"

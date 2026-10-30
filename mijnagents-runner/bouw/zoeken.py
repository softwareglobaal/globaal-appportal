"""Het zoekwerk van De Aannemerszoeker: firma's die een werk kunnen uitvoeren in een gebied, via het taalmodel met
webzoeken en webpagina's lezen, en de controles die niet van het model afhangen.

Naar buiten (het model en de zoekmachine) gaan alleen het werk, de gemeente en de straal, en of het om uitvoering voor
een bouwheer of om onderaanneming gaat. Nooit de naam van de firma die zoekt, de bouwheer of het werfadres.

Grendels in de code:
  - een firma telt alleen als het model haar website in deze ronde echt las (aankoop.onderzoek.alleen_gelezen);
  - een ondernemingsnummer moet de Belgische controle (modulo 97) halen, anders vervalt het;
  - "actief in de KBO" alleen als een KBO-pagina met dat nummer in deze ronde gelezen is en "Actief" toont;
  - de afstand rekent de code met Geopunt (koppelingen/adresregister.py); buiten de straal komt apart.
"""
import math
import re
import time
from urllib.parse import parse_qs, urlsplit

from aankoop import onderzoek as O

from . import scheiding as S

MODEL = O.MODEL
MAX_ZOEKEN = 10
MAX_LEZEN = 18
MAX_TOKENS = 150000
KBO = "kbopub.economie.fgov.be"
MIN_TEKST = 100

VORM = """Lever na je zoekwerk precies een JSON-object tussen ```json en ```, met deze velden:
{
  "vraag_kort": "het werk en het gebied in een zin",
  "aannames": ["wat je aannam omdat het niet in de vraag stond"],
  "firmas": [
    {"naam": "naam zoals op de website", "url": "de pagina van de firma die je met web_fetch las",
     "gemeente": "gemeente van de vestiging", "postcode": "1234", "adres": "straat en nummer, of null",
     "telefoon": "zoals op de site, of null", "email": "zoals op de site, of null",
     "ondernemingsnummer": "0123.456.789 zoals op de site of in de KBO, of null",
     "kbo_url": "de KBO-pagina die je met web_fetch las, of null",
     "specialiteit": "wat ze doen, kort", "bewijs": "een korte zin van de gelezen pagina die toont dat ze dit werk doen",
     "werkgebied": "wat de site zegt over hun werkgebied, of null", "waarom": "een zin: waarom deze firma past"}
  ],
  "werkomschrijving": "een korte alinea voor de prijsaanvraag: wat er moet gebeuren, met de omvang als die
    gegeven is; zonder namen, adressen of bedragen",
  "niet_gevonden": ["wat je zocht en niet vond, met waar je zocht"],
  "vervolgvraag": "een gebundelde vraag als iets beslissends ontbreekt, anders null"
}
Regels: geef alleen firma's waarvan je een eigen pagina (website, of hun pagina op een vakfederatie of gids) zelf met
web_fetch las en waar het werk op staat. Verzin nooit een telefoonnummer, mailadres of ondernemingsnummer: null als je
het niet zag. Zoek het ondernemingsnummer op in de KBO (kbopub.economie.fgov.be) en lees die pagina als dat lukt.
Geen bemiddelingsplatformen of offertesites als firma (zoals sites die je aanvraag doorverkopen)."""


def modelwerkwijze(werkwijze):
    """De werkwijze zoals ze naar het model gaat (Codex X4, controle 2): zonder het deel over voor wie ik werk en zonder
    elke regel die een van de twee firma's noemt. Het model zoekt firmaneutraal; de firma doet de code."""
    uit, overslaan = [], False
    for regel in (werkwijze or "").splitlines():
        if regel.startswith("## "):
            overslaan = regel.strip().lower() == "## voor wie ik werk"
        if not overslaan and not S.noemt_een_firma(regel):
            uit.append(regel)
    return "\n".join(uit)


def kennis_voor_model(collegas_tekst, lessen):
    """De gedeelde lessen (N13) en de collega's (N14) zoals ze naar het model gaan (Codex X13, controle 2): zonder elke
    regel die een van de twee firma's noemt."""
    from .vraag import persoonsgegevens
    regels = ["GEDEELDE LESSEN:"] + [f"- {l.get('les', '')}" for l in lessen or [] if isinstance(l, dict) and l.get("les")]
    regels += ["", str(collegas_tekst or "")]
    # Codex X4 (controle 3): ook geen regel met iets dat op een persoon, adres of nummer lijkt
    return "\n".join(r for r in "\n".join(regels).splitlines()
                     if not S.noemt_een_firma(r) and not persoonsgegevens(r)).strip()


def opdracht(werkwijze, werk, gemeente, straal_km, soort, vandaag, omvang="", kennis=""):
    """De systeemtekst en de vraag. soort: 'uitvoering' (een uitvoerder voor een bouwheer) of 'onderaanneming'."""
    wie = ("een aannemer of vakman die dit werk rechtstreeks voor een particuliere bouwheer uitvoert"
           if soort == "uitvoering" else "een vakman of firma die dit werk in onderaanneming voor een aannemer uitvoert")
    delen = ["Je bent De Aannemerszoeker, een agent die firma's zoekt die een bouwwerk kunnen uitvoeren, en gegevens "
             "levert; de code achter je keurt elke firma. Nederlands, geen emoji. Beweer niets wat je niet op een gelezen "
             "pagina zag.", "JOUW WERKWIJZE (ze geldt):\n" + modelwerkwijze(werkwijze)]
    if kennis:
        delen.append(kennis)
    systeem = "\n\n".join(delen + [VORM])
    gebruiker = (f"Vandaag is {vandaag}. Gezocht: {wie}.\nWERK: {werk}\n" + (f"OMVANG: {omvang}\n" if omvang else "")
                 + f"GEBIED: {gemeente}, binnen ongeveer {straal_km} km.\n"
                 "Zoek op het web en lees de pagina van elke firma met web_fetch voor je ze opneemt. Mik op vijf tot "
                 "acht firma's, liefst dicht bij het gebied, en geef liever minder dan een firma waarover je twijfelt.")
    return systeem, gebruiker


def btw_geldig(nummer):
    """Het Belgische ondernemingsnummer in de vorm 0123.456.789 als het de modulo 97-controle haalt, anders None."""
    cijfers = re.sub(r"\D", "", str(nummer or ""))
    if len(cijfers) == 9:
        cijfers = "0" + cijfers
    if len(cijfers) != 10 or cijfers[0] not in "01":
        return None
    if 97 - int(cijfers[:8]) % 97 != int(cijfers[8:]):
        return None
    return f"{cijfers[:4]}.{cijfers[4:7]}.{cijfers[7:]}"


STATUS = re.compile(r"status\s*:?\s*(niet\s+actief|actief|stopgezet|doorgehaald|ontbonden|vereffening)", re.I)


def kbo_actief(nummer, gelezen):
    """True als een gelezen pagina van kbopub.economie.fgov.be met precies dit nummer in de url en in de tekst als
    status Actief toont; False bij elke andere status; None als zo'n pagina er niet is (Codex X6, controle 2: de host
    exact, het nummer exact, de status uit de statusregel, nooit uit een los woord)."""
    if not nummer:
        return None
    kaal = nummer.replace(".", "")
    uitslag = None
    for url, tekst in (gelezen or {}).items():
        try:
            d = urlsplit(url)
        except ValueError:
            continue
        nrs = {re.sub(r"\D", "", w) for w in parse_qs(d.query).get("ondernemingsnummer", [])}
        if d.netloc.lower() != KBO or kaal not in nrs:
            continue
        t = tekst or ""
        if nummer not in t and kaal not in re.sub(r"\D", "", t):
            continue
        m = STATUS.search(t)
        if not m:
            continue
        if " ".join(m.group(1).lower().split()) != "actief":
            return False
        uitslag = True
    return uitslag


def afstand_km(a, b):
    """Afstand in vogelvlucht tussen twee punten {lat, lon}."""
    if not a or not b:
        return None
    r = 6371.0
    f1, f2 = math.radians(a["lat"]), math.radians(b["lat"])
    df, dl = f2 - f1, math.radians(b["lon"] - a["lon"])
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(h)), 1)


def host(url):
    try:
        return urlsplit(url).netloc.lower()
    except ValueError:
        return ""


# "Adres van de zetel: <straat> <nr> <postcode> <Gemeente>": de gemeente is een of meer woorden met een hoofdletter op
# dezelfde regel (Sint-Truiden, Kessel-Lo, Heist-op-den-Berg).
ZETEL = re.compile(r"(?i:adres\s+van\s+de\s+zetel)\s*:?\s*(.{0,120}?)\b([1-9]\d{3})[ \t]+"
                   r"([A-ZÀ-Ý][\wÀ-ÿ'’]*(?:[ -](?:[A-ZÀ-Ý][\wÀ-ÿ'’]*|op|den|de|aan|sur|lez))*)", re.S)


def nummer_op_site(nummer, url, gelezen):
    """Staat het ondernemingsnummer (in elke schrijfwijze) op een gelezen pagina van dezelfde site als de firma?"""
    if not nummer:
        return False
    eigen = host(O.schoon_url(url))
    kaal = nummer.replace(".", "")
    for u, t in (gelezen or {}).items():
        if eigen and host(u) == eigen:
            for m in re.finditer(r"(?:BE)?\s?[01][\d.\s]{8,14}\d", t or "", re.I):
                if re.sub(r"\D", "", m.group(0)).zfill(10)[-10:] == kaal:
                    return True
    return False


def kbo_zetel(nummer, gelezen):
    """'postcode gemeente' van de zetel volgens een gelezen KBO-pagina met dit nummer, of None (Codex X1, controle 5:
    een adres op de website kan een project zijn; de KBO zegt waar de firma gevestigd is)."""
    if not nummer:
        return None
    kaal = nummer.replace(".", "")
    for url, tekst in (gelezen or {}).items():
        try:
            d = urlsplit(url)
        except ValueError:
            continue
        nrs = {re.sub(r"\D", "", w) for w in parse_qs(d.query).get("ondernemingsnummer", [])}
        if d.netloc.lower() != KBO or kaal not in nrs:
            continue
        m = ZETEL.search(tekst or "")
        if m:
            return f"{m.group(2)} {m.group(3).strip()}"
    return None


def sleutel(f):
    """Om dubbels weg te halen: het ondernemingsnummer, anders het domein van de website."""
    if f.get("ondernemingsnummer"):
        return f["ondernemingsnummer"]
    url = O.schoon_url(f.get("url"))
    return url.split("/")[2] if url else ""


def keur(firmas, gelezen, centrum, straal_km, lokaliseer):
    """{"goed", "na_te_kijken", "buiten", "afgewezen"} (overleg X2, G2). Bovenaan alleen wie een gelezen eigen pagina
    heeft, een gelezen KBO-pagina die actief toont en binnen de straal ligt. Zonder KBO-bewijs of zonder bekende afstand:
    na te kijken, nooit groen. lokaliseer: 'postcode gemeente' -> {lat, lon} of None (Geopunt)."""
    gelezen_firmas, afgewezen = O.alleen_gelezen([f for f in firmas or [] if isinstance(f, dict)], gelezen)
    met_tekst = []
    for f in gelezen_firmas:     # Codex X6 (controle 2): een gelezen pagina zonder tekst bewijst niets
        url = O.schoon_url(f.get("url"))
        if host(url) == KBO:     # Codex X2 (controle 3): de KBO is geen eigen pagina van de firma
            afgewezen.append({"aanbod": f, "redenen": ["alleen een KBO-pagina, geen eigen pagina"]})
        elif len((gelezen.get(url, "") if isinstance(gelezen, dict) else "").strip()) < MIN_TEKST:
            afgewezen.append({"aanbod": f, "redenen": ["pagina zonder leesbare tekst"]})
        else:
            met_tekst.append(f)
    gelezen_firmas = met_tekst
    uit = {"goed": [], "na_te_kijken": [], "buiten": [], "afgewezen": afgewezen}
    gezien = set()
    for f in gelezen_firmas:
        f["ondernemingsnummer"] = btw_geldig(f.get("ondernemingsnummer"))
        f["kbo_actief"] = kbo_actief(f["ondernemingsnummer"], gelezen)
        # Codex X2 (controle 6): de site hoort bij de onderneming als het nummer op een gelezen pagina van die site
        # staat (een Belgische firmasite moet het tonen); anders is de site niet bewezen en komt ze bij na te kijken
        f["site_bewezen"] = nummer_op_site(f["ondernemingsnummer"], f.get("url"), gelezen)
        if f["kbo_actief"] is False:
            uit["afgewezen"].append({"aanbod": f, "redenen": ["stopgezet volgens de KBO"]})
            continue
        k = sleutel(f)
        if k in gezien:
            continue
        gezien.add(k)
        # De afstand alleen vanaf de zetel in de KBO (Codex X3 controle 3, X3 controle 4, X1 controle 5): wat het model of
        # de website als adres geeft, kan een werkgebied of een project zijn.
        plaats = kbo_zetel(f["ondernemingsnummer"], gelezen) if f["kbo_actief"] else None
        f["zetel"] = plaats
        if not plaats:
            f["vestiging_onbewezen"] = True
        punt = None
        if plaats:
            try:
                punt = lokaliseer(plaats)
            except Exception:  # noqa: BLE001  Geopunt onbereikbaar: afstand onbekend, dus na te kijken
                punt = None
        f["afstand_km"] = afstand_km(centrum, punt)
        if f["afstand_km"] is not None and f["afstand_km"] > straal_km:
            uit["buiten"].append(f)
        elif f["afstand_km"] is None or not f["kbo_actief"] or not f["site_bewezen"]:
            uit["na_te_kijken"].append(f)
        else:
            uit["goed"].append(f)
    for soort in ("goed", "na_te_kijken", "buiten"):
        uit[soort].sort(key=lambda f: (f.get("afstand_km") is None, f.get("afstand_km") or 0))
    return uit


def zoek(werkwijze, werk, gemeente, straal_km, soort, vandaag="", deadline=None, client=None, omvang="", kennis=""):
    """Een zoekvraag uitvoeren. Geeft {gegevens, gelezen, tekst, tokens, zoekopdrachten, stop, model}, zoals
    aankoop.onderzoek.onderzoek (dezelfde lus, met de plafonds van deze agent); gegevens is None als het model geen
    leesbaar JSON-object gaf."""
    deadline = deadline or time.monotonic() + 420
    if client is None:
        from anthropic import Anthropic
        client = Anthropic(max_retries=1)
    systeem, gebruiker = opdracht(werkwijze, werk, gemeente, straal_km, soort, vandaag, omvang, kennis)
    assistent, teksten, tokens, stop, model = [], [], 0, None, MODEL
    for _ in range(O.MAX_HERVATTEN):
        rest_zoeken = MAX_ZOEKEN - O._gebruikt(assistent, "web_search")
        rest_lezen = MAX_LEZEN - O._gebruikt(assistent, "web_fetch")
        rest_tijd = deadline - time.monotonic()
        if assistent and (tokens >= MAX_TOKENS or rest_tijd < 30 or (rest_zoeken < 1 and rest_lezen < 1)):
            stop = "plafond"
            break
        tools = [{"type": O.ZOEK_TOOL, "name": "web_search", "max_uses": max(1, rest_zoeken)},
                 {"type": O.LEES_TOOL, "name": "web_fetch", "max_uses": max(1, rest_lezen)}]
        berichten = [{"role": "user", "content": gebruiker}] + ([{"role": "assistant", "content": assistent}] if assistent else [])
        try:
            resp = client.messages.create(model=model, max_tokens=16000, system=systeem, messages=berichten, tools=tools,
                                          output_config={"effort": "medium"}, timeout=max(30.0, rest_tijd))
        except Exception as e:  # noqa: BLE001  een onbekende modelnaam: een keer het reservemodel
            if type(e).__name__ != "NotFoundError" or model == O.RESERVE_MODEL:
                raise
            model = O.RESERVE_MODEL
            continue
        gebruik = O._veld(resp, "usage")
        tokens += (O._veld(gebruik, "input_tokens", 0) or 0) + (O._veld(gebruik, "output_tokens", 0) or 0)
        blokken = list(O._veld(resp, "content", []) or [])
        assistent += blokken
        teksten = [O._veld(b, "text", "") for b in blokken if O._veld(b, "type") == "text"] or teksten
        stop = O._veld(resp, "stop_reason")
        if stop != "pause_turn":
            break
    tekst = "".join(teksten).strip()
    return {"gegevens": O.json_uit(tekst), "gelezen": O.gelezen_paginas(assistent), "tekst": tekst, "tokens": tokens,
            "zoekopdrachten": O._gebruikt(assistent, "web_search"), "stop": stop, "model": model}

"""Het zoekwerk van De Prijsonderzoeker: een vraag naar het taalmodel met webzoeken en webpagina's lezen,
en het antwoord terug als gegevens die aanbod.verwerk() kan keuren.

Een grendel die niet van het model afhangt: een aanbod telt alleen als het model die pagina in deze ronde
echt geopend heeft (een web_fetch-resultaat met die url). Een link uit een zoekresultaat alleen, of een link
die het model zelf samenstelt, gaat niet in het verslag. Daarom de basisversies van de servertools: hun
resultaatblokken dragen de url van de gelezen pagina, zodat de code dat kan nagaan.
"""
import json
import os
import re
import time
from urllib.parse import urlsplit, urlunsplit

MODEL = os.environ.get("PRIJS_MODEL", "claude-opus-5-5")
ZOEK_TOOL = os.environ.get("PRIJS_ZOEK_TOOL", "web_search_20250305")
LEES_TOOL = os.environ.get("PRIJS_LEES_TOOL", "web_fetch_20250910")
# Plafond per vraag, over alle beurten samen (Codex X7): zoekopdrachten, gelezen pagina's, tokens (vraag K4 aan
# Mehdi, 30-10-2026) en hervattingen van een gepauzeerde beurt. De tijd komt als deadline van de ronde (Codex X6).
# Gemeten 30-10-2026: de eerste echte vraag gebruikte 4,27 miljoen tokens met 12/15 en zonder paginagrens. Winkelpagina's
# zijn groot en binnen een beurt leest het model bij elke zoekstap alles opnieuw. Daarom een grens per gelezen pagina
# en minder zoek- en leesbeurten; het tokenplafond geldt tussen de beurten.
# Gemeten 01-11-2026: 404.791 tokens in een beurt, en bij 6.000 tokens viel de prijs van Vanden Borre van de pagina.
# Overleg 9 (G2, X5): 10.000 tokens per pagina, zes zoek- en zes leesbeurten (vijf aanbodpagina's en een
# specificatiebron), en een takenbudget dat het model zelf ziet (X3): binnen een aanvraag is max_uses de harde grens.
MAX_ZOEKEN = int(os.environ.get("PRIJS_MAX_ZOEKEN", "6"))
MAX_LEZEN = int(os.environ.get("PRIJS_MAX_LEZEN", "6"))
MAX_PAGINA_TOKENS = int(os.environ.get("PRIJS_MAX_PAGINA_TOKENS", "10000"))
MAX_TOKENS = int(os.environ.get("PRIJS_MAX_TOKENS", "300000"))
TAAK_BUDGET = int(os.environ.get("PRIJS_TAAK_BUDGET", "250000"))     # 0: zonder takenbudget
BETA_BUDGET = "task-budgets-2026-03-13"
# Dollar per miljoen tokens (input, output), voor de kost in het werkverslag (overleg 9, X3); prompt caching staat niet
# aan (G3 afgewezen), dus de cachetellers horen nul te zijn.
PRIJZEN = {"claude-opus-5-5": (4.0, 20.0), "claude-opus-5": (5.0, 25.0)}
ZOEK_DOLLAR = 0.01             # webzoeken kost 10 dollar per duizend zoekopdrachten (Codex controle 10)
# Een prijs in "gezien, niet nagekeken" moet haar munt in het citaat tonen (Codex controle 10).
MUNTTEKENS = {"EUR": ("€", "eur", "euro"), "USD": ("$", "usd"), "GBP": ("£", "gbp"), "CHF": ("chf",),
              "PLN": ("zł", "pln"), "SEK": ("sek", "kr"), "DKK": ("dkk", "kr")}
GETAL = r"\d[\d.,'\u202f\xa0 ]*\d|\d"


def _munt_bij_bedrag(prijs, munt, citaat):
    """Staat de munt vlak voor of na dit bedrag in het citaat, als los teken of woord? "949 USD" bewijst geen 949 euro,
    ook niet als er ergens "Europa" staat (Codex controle 11)."""
    from aankoop.aanbod import bedrag_op_pagina
    c = str(citaat or "").lower()
    for t in MUNTTEKENS.get(munt, ()):
        tt = rf"\b{re.escape(t)}\b" if t.isalpha() else re.escape(t)
        for m in re.finditer(rf"(?:{tt})\s?({GETAL})|({GETAL})\s?(?:,-|,–)?\s?(?:{tt})", c):
            if bedrag_op_pagina(prijs, m.group(1) or m.group(2)):
                return True
    return False
MAX_HERVATTEN = 6
RESERVE_MODEL = "claude-opus-5"     # het model dat De Ontwikkelaar op de VM gebruikt (overleg K5)

VORM = """Lever na je zoekwerk precies een JSON-object tussen ```json en ```, met deze velden:
{
  "vraag_kort": "de vraag in een zin, zonder namen",
  "aannames": ["wat je aannam omdat het niet in de vraag stond"],
  "eisen": ["elke andere eis waar een aanbod aan moet voldoen, kort"],
  "aanbiedingen": [
    {"titel": "exacte productnaam en variant", "url": "de pagina die je met web_fetch las",
     "modelcode": "de volledige modelcode of het typenummer zoals het op de aanbodpagina staat, of null",
     "winkel": "naam", "land": "ISO-landcode van de verkoper, bv. BE, DE, US",
     "soort": "nieuw | refurbished | tweedehands | veiling",
     "prijs": 0.0, "munt": "EUR", "btw_inbegrepen": true, "verzending": 0.0, "verzending_btw_inbegrepen": true,
     "opgeld_pct": null, "veilingkosten": null, "douane": null,
     "bewijs": {"prijs": "letterlijk stuk tekst van de aanbodpagina met de prijs van dit product",
                "verzending": "letterlijk stuk tekst met de verzendkost, of met gratis verzending",
                "opgeld": "letterlijk stuk uit de veilingvoorwaarden met het percentage", "veilingkosten": "idem met het bedrag"},
     "staat": "nieuw, als nieuw, gebruikt, defect", "garantie": "bv. 2 jaar, geen",
     "beschikbaar": true, "btw_factuur": true, "foto": "de url van de productfoto zoals ze in de gelezen pagina staat, of null",
     "betrouwbaarheid": "officiele dealer, winkel, platform met particulier, met beoordelingen als de pagina ze toont",
     "compatibiliteit": {"<eis>": {"oordeel": "ja | nee | onbekend", "citaat": "letterlijk stuk tekst van een gelezen pagina",
                                   "bewijs_url": "de gelezen pagina met dat citaat, als het niet de aanbodpagina is, anders null"}},
     "waarom": "een korte zin: waarom dit aanbod, of wat eraan schort"}
  ],
  "niet_nagekeken": [{"titel": "product", "url": "de link uit een zoekresultaat", "prijs": null, "munt": "EUR",
                      "citaat": "letterlijk stuk uit dat zoekresultaat met de prijs, of null",
                      "reden": "waarom niet nagekeken: pagina niet leesbaar, afgekapt, of geen leesbeurt meer"}],
  "niet_gevonden": ["wat je zocht en niet vond, met waar je zocht"],
  "vervolgvraag": "een gebundelde vraag als iets beslissends ontbreekt (bestemming, firma of privé), anders null"
}
Regels voor de JSON: prijs exact zoals op de pagina, als getal in de munt van de pagina; btw_inbegrepen false als de
pagina een prijs zonder btw toont, null als je het niet weet; verzending null als de pagina het niet zegt; bij een
veiling opgeld_pct en veilingkosten uit de veilingvoorwaarden (veilingkosten 0 als de voorwaarden geen vaste kosten
noemen, null als je het niet weet); douane alleen buiten de EU, als je schatting in dezelfde munt (de code rekent de
btw zelf), anders null. Geef alleen aanbiedingen waarvan je de pagina zelf met web_fetch las en de prijs daar zag.
Elk citaat in bewijs en compatibiliteit kopieer je letterlijk van een pagina die je met web_fetch las; zonder citaat
telt een bedrag of een "ja" niet. Beoordeel in compatibiliteit elke eis, met precies dezelfde tekst als sleutel. Een
eis die voor dit product niet geldt (bijvoorbeeld netfrequentie bij iets zonder netstroom), beoordeel je met ja en
citeer je de tekst waaruit dat blijkt. Netspanning en netfrequentie staan zelden op een winkelpagina: zoek en lees dan
een pagina van de fabrikant, de handleiding of het specificatieblad van precies die modelcode, en geef die pagina als
bewijs_url; dat telt alleen als dezelfde modelcode op de aanbodpagina en op die bewijspagina staat. In niet_nagekeken
komen aanbiedingen die je alleen in een zoekresultaat zag of waarvan de pagina niet leesbaar was; die worden nooit
aanbevolen."""
# Namen gaan nooit naar buiten, ook niet uit de werkwijze (Codex X4, ronde 2).
NAMEN = re.compile(r"\b(?:Mehdi(?:\s+Chegini)?|Chegini)\b")


def _veld(obj, naam, standaard=None):
    if isinstance(obj, dict):
        return obj.get(naam, standaard)
    return getattr(obj, naam, standaard)


def schoon_url(url):
    """Een url zonder fragment, zonder slash op het einde en zonder www., met https en kleine letters in de host."""
    try:
        d = urlsplit(str(url or "").strip())
    except ValueError:
        return ""
    if not d.scheme or not d.netloc:
        return ""
    host = d.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    schema = "https" if d.scheme.lower() in ("http", "https") else d.scheme.lower()   # http en https zijn dezelfde pagina
    return urlunsplit((schema, host, d.path.rstrip("/"), d.query, ""))


def _paginatekst(inhoud):
    """De tekst van een gelezen pagina (document met een tekstbron); leeg voor een PDF of een onbekende vorm."""
    document = _veld(inhoud, "content")
    bron = _veld(document, "source")
    data = _veld(bron, "data")
    return data if _veld(bron, "type") == "text" and isinstance(data, str) else ""


def gelezen_paginas(blokken):
    """{url: tekst} van de pagina's die het model in deze beurten echt las (geslaagde web_fetch-resultaten)."""
    uit = {}
    for b in blokken or []:
        if _veld(b, "type") != "web_fetch_tool_result":
            continue
        inhoud = _veld(b, "content")
        url = schoon_url(_veld(inhoud, "url")) if _veld(inhoud, "type") == "web_fetch_result" else ""
        if url:
            uit[url] = uit.get(url, "") + _paginatekst(inhoud)
    return uit


def alleen_gelezen(aanbiedingen, gelezen):
    """(aanbiedingen waarvan de pagina gelezen is, de andere met reden). gelezen: de urls of {url: tekst}.
    Een foto blijft alleen staan als haar url letterlijk in de gelezen pagina staat; anders wordt ze leeg, nooit
    verzonnen (overleg X5): de link naar de pagina toont dan de foto."""
    goed, weg = [], []
    for a in aanbiedingen or []:
        if not isinstance(a, dict):
            continue
        url = schoon_url(a.get("url"))
        if url not in gelezen:
            weg.append({"aanbod": a, "redenen": ["pagina niet gelezen in deze ronde"]})
            continue
        tekst = gelezen.get(url, "") if isinstance(gelezen, dict) else ""
        foto = str(a.get("foto") or "").strip()
        if foto and not (foto.startswith(("https://", "http://")) and foto in tekst):
            a["foto"] = None
        goed.append(a)
    return goed, weg


def zoekresultaten(blokken):
    """{url: tekst} van de zoekresultaten van deze ronde: de titel en wat het model er letterlijk uit citeerde. De
    samenvatting van een zoekresultaat zelf is versleuteld; een prijs telt dus alleen als ze in de titel of in een
    citaat bij die url staat (overleg 9, X4)."""
    uit = {}
    for b in blokken or []:
        if _veld(b, "type") == "web_search_tool_result" and isinstance(_veld(b, "content"), list):
            for r in _veld(b, "content"):
                url = schoon_url(_veld(r, "url"))
                if url and _veld(r, "type") == "web_search_result":
                    uit[url] = uit.get(url, "") + " " + str(_veld(r, "title") or "")
        for c in (_veld(b, "citations") or []) if _veld(b, "type") == "text" else []:
            url = schoon_url(_veld(c, "url"))
            if _veld(c, "type") == "web_search_result_location" and url in uit:
                uit[url] += " " + str(_veld(c, "cited_text") or "")
    return uit


def leesbeurten(blokken):
    """(geslaagd, mislukt): de web_fetch-resultaten van deze ronde, voor het werkverslag (overleg 9, X3)."""
    soorten = [_veld(_veld(b, "content"), "type") for b in blokken or [] if _veld(b, "type") == "web_fetch_tool_result"]
    geslaagd = soorten.count("web_fetch_result")
    return geslaagd, len(soorten) - geslaagd


def alleen_gezien(items, zoek, opgenomen=()):
    """De lijst "gezien, niet nagekeken" (overleg 9, X4): alleen met een url en een prijs die in hetzelfde zoekresultaat
    van deze ronde stonden, en niet als de url al als gelezen aanbod in het verslag staat. De prijs moet in het citaat
    staan, met haar munt vlak bij het bedrag en zonder kostwoord als verzending of opgeld ervoor of erin (Codex controle
    10 en 11: "Shipping 19 euro" is geen productprijs, "Europa 949 USD" geen 949 euro). Een rij zonder bewezen prijs valt weg. Deze lijst komt nooit in verwerk(), dus nooit
    als beste of reserve."""
    from aankoop.aanbod import bedrag_op_pagina, zonder_kostwoord   # hier, zoals schoon_url in aanbod.verwerk
    al = {schoon_url(u) for u in opgenomen}
    uit, gezien = [], set()
    for it in items or []:
        if not isinstance(it, dict):
            continue
        url = schoon_url(it.get("url"))
        if not url or url not in zoek or url in al or url in gezien:
            continue
        munt, citaat = str(it.get("munt") or "EUR").upper(), str(it.get("citaat") or "")
        if (it.get("prijs") is None or not zonder_kostwoord(citaat, zoek[url]) or not bedrag_op_pagina(it["prijs"], citaat)
                or not _munt_bij_bedrag(it["prijs"], munt, citaat)):
            continue
        gezien.add(url)
        uit.append({"titel": str(it.get("titel") or "aanbod"), "url": it.get("url"), "reden": str(it.get("reden") or ""),
                    "prijs": it["prijs"], "munt": munt})
    return uit[:10]


def json_uit(tekst):
    """Het JSON-object uit het antwoord van het model: het laatste ```json-blok, anders van de eerste { tot de
    laatste }. Geeft None als er geen leesbaar object is."""
    blokken = re.findall(r"```json\s*(\{.*?\})\s*```", tekst or "", re.S)
    kandidaten = list(reversed(blokken))
    if "{" in (tekst or "") and "}" in tekst:
        kandidaten.append(tekst[tekst.index("{"):tekst.rindex("}") + 1])
    for k in kandidaten:
        try:
            obj = json.loads(k)
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def opdracht(werkwijze, vraag, vandaag, vaste_eisen=()):
    """De systeemtekst en de vraag. Alleen de werkwijze (N12) en de productvraag gaan naar buiten: geen naam van Mehdi,
    geen lijst van collega's en geen gedeelde lessen (Codex X4, overleg X4). Die leest de ronde wel als bron (N13, N14)."""
    systeem = "\n\n".join([
        "Je bent De Prijsonderzoeker, een agent die zoekt waar iets het best te koop is en gegevens levert; de code "
        "achter je keurt elk aanbod en rekent de totaalprijs in euro. Nederlands, geen emoji. Beweer niets wat je niet "
        "op een gelezen pagina zag.",
        "JOUW WERKWIJZE (ze geldt):\n" + NAMEN.sub("de opdrachtgever", werkwijze or ""),
        VORM,
    ])
    eisen = ("\n\nVASTE EISEN (beoordeel elk aanbod hierop, met precies deze tekst als sleutel): " + "; ".join(vaste_eisen)
             if vaste_eisen else "")
    gebruiker = (f"Vandaag is {vandaag}. Zoek op het web (minstens drie verschillende bronsoorten waar dat kan) en "
                 f"lees elke aanbodpagina met web_fetch voor je ze opneemt.{eisen}\n\nPRIJSVRAAG:\n{vraag}")
    return systeem, gebruiker


def _gebruikt(blokken, naam):
    return sum(1 for b in blokken if _veld(b, "type") == "server_tool_use" and _veld(b, "name") == naam)


def _tellers(gebruik):
    """De tellers van een aanvraag uit usage (overleg 9, X3): input, output, cache en het aantal servertoolbeurten."""
    server = _veld(gebruik, "server_tool_use")
    return {"input": _veld(gebruik, "input_tokens", 0) or 0, "output": _veld(gebruik, "output_tokens", 0) or 0,
            "cache_schrijven": _veld(gebruik, "cache_creation_input_tokens", 0) or 0,
            "cache_lezen": _veld(gebruik, "cache_read_input_tokens", 0) or 0,
            "zoek": _veld(server, "web_search_requests", 0) or 0, "lees": _veld(server, "web_fetch_requests", 0) or 0}


def kosten(tellers, model):
    """Geschatte kost in dollar van alle aanvragen samen: input, output en de zoekopdrachten (caching staat niet aan)."""
    prijs_in, prijs_uit = PRIJZEN.get(model, max(PRIJZEN.values()))
    return round(sum((t["input"] * prijs_in + t["output"] * prijs_uit) / 1e6 + t.get("zoek", 0) * ZOEK_DOLLAR
                     for t in tellers), 2)


def onderzoek(vraag, werkwijze, vandaag="", vaste_eisen=(), deadline=None, client=None):
    """Een prijsvraag uitvoeren. Geeft {gegevens, gelezen, zoekresultaten, tekst, tokens, tellers, kosten,
    leesbeurten, zoekopdrachten, stop, model, beurten}. gegevens is None als het model geen leesbaar JSON-object gaf;
    gelezen is {url: paginatekst}; tellers is per aanvraag de usage (overleg 9, X3).
    deadline: time.monotonic() waarop de vraag klaar moet zijn (een deadline voor de hele ronde, Codex X6)."""
    deadline = deadline or time.monotonic() + 420
    if client is None:
        from anthropic import Anthropic
        client = Anthropic(max_retries=1)
    systeem, gebruiker = opdracht(werkwijze, vraag, vandaag, vaste_eisen)
    assistent, teksten, tokens, stop, model, beurten, tellers = [], [], 0, None, MODEL, [], []
    afronden = False
    for _ in range(MAX_HERVATTEN + 1):
        rest_zoeken = MAX_ZOEKEN - _gebruikt(assistent, "web_search")
        rest_lezen = MAX_LEZEN - _gebruikt(assistent, "web_fetch")
        rest_tijd = deadline - time.monotonic()
        if assistent and not afronden and (tokens >= MAX_TOKENS or rest_tijd < 60 or rest_zoeken < 1 or rest_lezen < 1):
            # Een plafond is bereikt: nog een beurt zonder gereedschap (tool_choice none), zodat er geen zoekopdracht
            # of pagina meer bij kan (Codex X7, ronde 2) en het model afrondt met wat het las.
            afronden = True
            if rest_tijd < 20:
                stop = "plafond"
                break
        tools = [{"type": ZOEK_TOOL, "name": "web_search", "max_uses": max(1, rest_zoeken)},
                 {"type": LEES_TOOL, "name": "web_fetch", "max_uses": max(1, rest_lezen),
                  "max_content_tokens": MAX_PAGINA_TOKENS}]
        # Een gepauzeerde beurt gaat verder met de hele beurt tot nu toe, niet alleen het laatste stuk (Codex X8).
        berichten = [{"role": "user", "content": gebruiker}] + ([{"role": "assistant", "content": assistent}] if assistent else [])
        # Afronden hervat de open beurt zoals Anthropic het vraagt, zonder extra bericht, maar zonder gereedschap
        # (Codex X13, ronde 3); de systeemtekst vraagt het JSON-object als het zoekwerk voorbij is.
        extra = {"tool_choice": {"type": "none"}} if afronden else {}
        # Het takenbudget ziet het model zelf en telt wat het in deze beurt leest en schrijft; het is een advies, de
        # harde grens binnen een aanvraag blijft max_uses (overleg 9, X3). remaining laat de server zelf bijhouden.
        uitvoer = {"effort": "medium"}
        api = client.messages
        if TAAK_BUDGET:
            uitvoer["task_budget"] = {"type": "tokens", "total": TAAK_BUDGET}
            extra["betas"] = [BETA_BUDGET]
            api = client.beta.messages
        try:
            resp = api.create(model=model, max_tokens=16000, system=systeem, messages=berichten, tools=tools,
                              output_config=uitvoer, timeout=max(15.0, rest_tijd), **extra)
        except Exception as e:  # noqa: BLE001  een onbekende modelnaam: een keer het model van De Ontwikkelaar (K5)
            if type(e).__name__ != "NotFoundError" or model == RESERVE_MODEL:
                raise
            model = RESERVE_MODEL
            continue
        tellers.append(_tellers(_veld(resp, "usage")))
        beurt = tellers[-1]["input"] + tellers[-1]["output"]
        tokens += beurt
        beurten.append(beurt)
        blokken = list(_veld(resp, "content", []) or [])
        teksten = [_veld(b, "text", "") for b in blokken if _veld(b, "type") == "text"] or teksten
        stop = _veld(resp, "stop_reason")
        assistent += blokken          # ook de afrondbeurt: wat erin gelezen werd, blijft gelezen (Codex X13)
        if afronden:
            stop = "plafond"
            break
        if stop != "pause_turn":
            break
    tekst = "".join(teksten).strip()
    return {"gegevens": json_uit(tekst), "gelezen": gelezen_paginas(assistent), "zoekresultaten": zoekresultaten(assistent),
            "tekst": tekst, "tokens": tokens, "tellers": tellers, "kosten": kosten(tellers, model),
            "leesbeurten": leesbeurten(assistent), "zoekopdrachten": _gebruikt(assistent, "web_search"), "stop": stop,
            "model": model, "beurten": beurten}

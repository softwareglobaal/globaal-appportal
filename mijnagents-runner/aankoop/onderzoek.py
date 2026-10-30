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
MAX_ZOEKEN = int(os.environ.get("PRIJS_MAX_ZOEKEN", "12"))
MAX_LEZEN = int(os.environ.get("PRIJS_MAX_LEZEN", "15"))
MAX_TOKENS = int(os.environ.get("PRIJS_MAX_TOKENS", "150000"))
MAX_HERVATTEN = 6
RESERVE_MODEL = "claude-opus-5"     # het model dat De Ontwikkelaar op de VM gebruikt (overleg K5)

VORM = """Lever na je zoekwerk precies een JSON-object tussen ```json en ```, met deze velden:
{
  "vraag_kort": "de vraag in een zin, zonder namen",
  "aannames": ["wat je aannam omdat het niet in de vraag stond"],
  "eisen": ["elke andere eis waar een aanbod aan moet voldoen, kort"],
  "aanbiedingen": [
    {"titel": "exacte productnaam en variant", "url": "de pagina die je met web_fetch las",
     "winkel": "naam", "land": "ISO-landcode van de verkoper, bv. BE, DE, US",
     "soort": "nieuw | refurbished | tweedehands | veiling",
     "prijs": 0.0, "munt": "EUR", "btw_inbegrepen": true, "verzending": 0.0,
     "opgeld_pct": null, "veilingkosten": null, "douane": null,
     "staat": "nieuw, als nieuw, gebruikt, defect", "garantie": "bv. 2 jaar, geen",
     "beschikbaar": true, "btw_factuur": true, "foto": "de url van de productfoto zoals ze in de gelezen pagina staat, of null",
     "betrouwbaarheid": "officiele dealer, winkel, platform met particulier, met beoordelingen als de pagina ze toont",
     "compatibiliteit": {"<eis>": "ja | nee | onbekend"}, "waarom": "een zin: waarom dit aanbod, of wat eraan schort"}
  ],
  "niet_gevonden": ["wat je zocht en niet vond, met waar je zocht"],
  "vervolgvraag": "een gebundelde vraag als iets beslissends ontbreekt (bestemming, firma of privé), anders null"
}
Regels voor de JSON: prijs exact zoals op de pagina, als getal in de munt van de pagina; btw_inbegrepen false als de
pagina een prijs zonder btw toont, null als je het niet weet; verzending null als de pagina het niet zegt; bij een
veiling opgeld_pct en veilingkosten uit de veilingvoorwaarden (veilingkosten 0 als de voorwaarden geen vaste kosten
noemen, null als je het niet weet); douane alleen buiten de EU, als je schatting in dezelfde munt (de code rekent de
btw zelf), anders null. Geef alleen aanbiedingen waarvan je de pagina zelf met web_fetch las en de prijs daar zag.
Beoordeel in compatibiliteit elke eis, met precies dezelfde tekst als sleutel. Een eis die voor dit product niet
geldt (bijvoorbeeld netfrequentie bij iets zonder netstroom), beoordeel je met ja en zeg je in waarom."""


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
        "JOUW WERKWIJZE (ze geldt):\n" + (werkwijze or ""),
        VORM,
    ])
    eisen = ("\n\nVASTE EISEN (beoordeel elk aanbod hierop, met precies deze tekst als sleutel): " + "; ".join(vaste_eisen)
             if vaste_eisen else "")
    gebruiker = (f"Vandaag is {vandaag}. Zoek op het web (minstens drie verschillende bronsoorten waar dat kan) en "
                 f"lees elke aanbodpagina met web_fetch voor je ze opneemt.{eisen}\n\nPRIJSVRAAG:\n{vraag}")
    return systeem, gebruiker


def _gebruikt(blokken, naam):
    return sum(1 for b in blokken if _veld(b, "type") == "server_tool_use" and _veld(b, "name") == naam)


def onderzoek(vraag, werkwijze, vandaag="", vaste_eisen=(), deadline=None, client=None):
    """Een prijsvraag uitvoeren. Geeft {gegevens, gelezen, tekst, tokens, zoekopdrachten, stop, model}.
    gegevens is None als het model geen leesbaar JSON-object gaf; gelezen is {url: paginatekst}.
    deadline: time.monotonic() waarop de vraag klaar moet zijn (een deadline voor de hele ronde, Codex X6)."""
    deadline = deadline or time.monotonic() + 420
    if client is None:
        from anthropic import Anthropic
        client = Anthropic(max_retries=1)
    systeem, gebruiker = opdracht(werkwijze, vraag, vandaag, vaste_eisen)
    assistent, teksten, tokens, stop, model = [], [], 0, None, MODEL
    for _ in range(MAX_HERVATTEN):
        rest_zoeken = MAX_ZOEKEN - _gebruikt(assistent, "web_search")
        rest_lezen = MAX_LEZEN - _gebruikt(assistent, "web_fetch")
        rest_tijd = deadline - time.monotonic()
        if assistent and (tokens >= MAX_TOKENS or rest_tijd < 30 or (rest_zoeken < 1 and rest_lezen < 1)):
            stop = "plafond"           # niet verder zoeken: wat er al is, gaat door dezelfde controle
            break
        tools = [{"type": ZOEK_TOOL, "name": "web_search", "max_uses": max(1, rest_zoeken)},
                 {"type": LEES_TOOL, "name": "web_fetch", "max_uses": max(1, rest_lezen)}]
        # Een gepauzeerde beurt gaat verder met de hele beurt tot nu toe, niet alleen het laatste stuk (Codex X8).
        berichten = [{"role": "user", "content": gebruiker}] + ([{"role": "assistant", "content": assistent}] if assistent else [])
        try:
            resp = client.messages.create(model=model, max_tokens=16000, system=systeem, messages=berichten, tools=tools,
                                          output_config={"effort": "medium"}, timeout=max(30.0, rest_tijd))
        except Exception as e:  # noqa: BLE001  een onbekende modelnaam: een keer het model van De Ontwikkelaar (K5)
            if type(e).__name__ != "NotFoundError" or model == RESERVE_MODEL:
                raise
            model = RESERVE_MODEL
            continue
        gebruik = _veld(resp, "usage")
        tokens += (_veld(gebruik, "input_tokens", 0) or 0) + (_veld(gebruik, "output_tokens", 0) or 0)
        blokken = list(_veld(resp, "content", []) or [])
        assistent += blokken
        teksten = [_veld(b, "text", "") for b in blokken if _veld(b, "type") == "text"] or teksten
        stop = _veld(resp, "stop_reason")
        if stop != "pause_turn":
            break
    tekst = "".join(teksten).strip()
    return {"gegevens": json_uit(tekst),
            "gelezen": gelezen_paginas(assistent), "tekst": tekst, "tokens": tokens,
            "zoekopdrachten": _gebruikt(assistent, "web_search"), "stop": stop, "model": model}

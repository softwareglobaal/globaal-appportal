"""Het zoekwerk van De Prijsonderzoeker: een vraag naar Claude met webzoeken en webpagina's lezen, en het antwoord
terug als gegevens die aanbod.verwerk() kan keuren.

Sinds overleg 14 (01-11-2026) via Mehdi's Claude-abonnement, nooit via de API: `claude -p` op de VM met het token uit
`claude setup-token` (TOKEN_BESTAND). De omgeving van het subproces is een witte lijst zonder API-sleutel; meldt Claude
Code toch een andere bron dan het abonnement, of start het extra betaald verbruik, dan stopt de ronde meteen.

Een grendel die niet van het model afhangt: een aanbod telt alleen als het model die pagina in deze ronde echt las met
de eigen leestool (aankoop/leesserver.py). Die geeft het model precies de tekst die ze ook in het leeslog zet, en dat
leeslog is `gelezen` voor aanbod.py. Een link uit een zoekresultaat alleen gaat nooit in het verslag.
"""
import json
import os
import queue
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit, urlunsplit

HIER = os.path.dirname(os.path.abspath(__file__))
CLAUDE = os.path.expanduser(os.environ.get("PRIJS_CLAUDE", "~/.local/bin/claude"))
MODEL = os.environ.get("PRIJS_MODEL", "opus")      # een alias, geen modelcode die kan verdwijnen (overleg 14, X1)
TOKEN_BESTAND = os.path.expanduser(os.environ.get("PRIJS_TOKEN_BESTAND", "~/.config/prijsonderzoeker/claude-token"))
# De laatst gemeten benutting van de limietvensters van het abonnement (overleg 25, K2): lag die boven GRENS_GEBRUIK en
# is het venster nog niet herstart, dan start een vraag niet, zodat ze nooit in betaald extra verbruik begint.
LIMIET_BESTAND = os.path.expanduser(os.environ.get("PRIJS_LIMIET_BESTAND", "~/.config/prijsonderzoeker/limiet.json"))
MAX_ZOEKEN = int(os.environ.get("PRIJS_MAX_ZOEKEN", "6"))
MAX_LEZEN = int(os.environ.get("PRIJS_MAX_LEZEN", "6"))
MAX_PAGINA_TOKENS = int(os.environ.get("PRIJS_MAX_PAGINA_TOKENS", "10000"))
MAX_BEURTEN = int(os.environ.get("PRIJS_MAX_BEURTEN", "30"))   # assistentberichten; --max-turns bestaat niet (K4)
# Boven dit deel van een limietvenster van het abonnement stopt de vraag, zodat ze nooit in betaald extra verbruik
# loopt en Mehdi zijn eigen gebruik houdt (Codex controle 15, punt 1).
GRENS_GEBRUIK = float(os.environ.get("PRIJS_GRENS_GEBRUIK", "0.9"))
# Beheerde instellingen gaan voor alles, ook voor --restricted, en kunnen een betaalde route of sleutel toevoegen.
BEHEERD = ("/etc/claude-code", "/Library/Application Support/ClaudeCode")
# Alleen een persoonlijk abonnement: een Team- of Enterprise-account kan centrale instellingen met een betaalde route
# opleggen (Codex controle 16, punt 1).
PERSOONLIJK = ("pro", "max", "ultra")
ZOEK = "WebSearch"
LEES = "mcp__lees__lees_pagina"
# Alleen dit gaat mee naar het subproces; ANTHROPIC_API_KEY en elke andere sleutel dus nooit (overleg 14, K1).
OMGEVING = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TMPDIR")


class GeenAbonnement(Exception):
    """De vraag stopt zonder Claude: geen geldig abonnementstoken, of Claude Code gebruikt iets anders dan het
    abonnement (een API-sleutel, extra betaald verbruik). Er is nooit een terugval naar de API."""


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


VORM = """Lever na je zoekwerk precies een JSON-object tussen ```json en ```, met deze velden:
{
  "vraag_kort": "de vraag in een zin, zonder namen",
  "aannames": ["wat je aannam omdat het niet in de vraag stond"],
  "eisen": ["elke andere eis waar een aanbod aan moet voldoen, kort"],
  "aanbiedingen": [
    {"titel": "exacte productnaam en variant", "url": "de URL bovenaan de tekst die lees_pagina gaf",
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
                      "citaat": "de titel van dat zoekresultaat als de prijs daarin staat, anders null",
                      "reden": "waarom niet nagekeken: pagina niet leesbaar, afgekapt, of geen leesbeurt meer"}],
  "niet_gevonden": ["wat je zocht en niet vond, met waar je zocht"],
  "vervolgvraag": "een gebundelde vraag als iets beslissends ontbreekt (bestemming, firma of privé), anders null"
}
Regels voor de JSON: prijs exact zoals op de pagina, als getal in de munt van de pagina; btw_inbegrepen false als de
pagina een prijs zonder btw toont, null als je het niet weet; verzending null als de pagina het niet zegt; bij een
veiling opgeld_pct en veilingkosten uit de veilingvoorwaarden (veilingkosten 0 als de voorwaarden geen vaste kosten
noemen, null als je het niet weet); douane alleen buiten de EU, als je schatting in dezelfde munt (de code rekent de
btw zelf), anders null. Geef alleen aanbiedingen waarvan je de pagina zelf met lees_pagina las en de prijs daar zag.
Elk citaat in bewijs en compatibiliteit kopieer je letterlijk van een pagina die je met lees_pagina las; zonder citaat
telt een bedrag of een "ja" niet. Beoordeel in compatibiliteit elke eis, met precies dezelfde tekst als sleutel. Een
eis die voor dit product niet geldt (bijvoorbeeld netfrequentie bij iets zonder netstroom), beoordeel je met ja en
citeer je de tekst waaruit dat blijkt. Netspanning en netfrequentie staan zelden op een winkelpagina: zoek en lees dan
een pagina van de fabrikant, de handleiding of het specificatieblad van precies die modelcode, en geef die pagina als
bewijs_url; dat telt alleen als dezelfde modelcode op de aanbodpagina en op die bewijspagina staat. In niet_nagekeken
komen aanbiedingen die je alleen in een zoekresultaat zag of waarvan de pagina niet leesbaar was; die worden nooit
aanbevolen."""
# Namen gaan nooit naar buiten, ook niet uit de werkwijze (Codex X4, ronde 2).
NAMEN = re.compile(r"\b(?:Mehdi(?:\s+Chegini)?|Chegini)\b")


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
                 f"lees elke aanbodpagina met lees_pagina voor je ze opneemt.{eisen}\n\nPRIJSVRAAG:\n{vraag}")
    return systeem, gebruiker


def zoekresultaten_uit(resultaat):
    """{url: titel} uit het resultaat van een WebSearch van Claude Code (gemeten vorm in
    tests/fixtures/claude_stream_proef.jsonl: {"query", "results": [{"content": [{"title", "url"}]}]}). Er zijn geen
    letterlijke citaten meer; een prijs in "gezien, niet nagekeken" telt dus alleen als ze in de titel staat."""
    uit = {}
    for r in (resultaat or {}).get("results") or [] if isinstance(resultaat, dict) else []:
        for c in (r.get("content") or []) if isinstance(r, dict) else []:
            url = schoon_url(c.get("url")) if isinstance(c, dict) else ""
            if url:
                uit[url] = (uit.get(url, "") + " " + str(c.get("title") or "")).strip()
    return uit


def gelezen_uit(leeslog):
    """({url: tekst} van de geslaagde lezingen, (geslaagd, mislukt)) uit het leeslog van de leestool. De tekst is
    precies wat het model las (overleg 14, X2), onder de eind-url die het model bovenaan zag. Twee lezingen worden nooit
    aan elkaar geplakt: de laatste lezing van een url telt (Codex controle 15, punt 3)."""
    uit, geslaagd, mislukt = {}, 0, 0
    try:
        with open(leeslog, encoding="utf-8") as f:
            regels = f.read().splitlines()
    except OSError:
        regels = []
    for r in regels:
        try:
            d = json.loads(r)
        except ValueError:
            continue
        if not isinstance(d, dict) or not d.get("ok"):
            mislukt += 1
            continue
        geslaagd += 1
        url = schoon_url(d.get("eind_url") or d.get("url"))
        if url:
            uit[url] = str(d.get("tekst") or "")
    return uit, (geslaagd, mislukt)


def beheerde_instellingen(mappen=None):
    """De beheerde instellingen van Claude Code op deze machine; die zouden voor het abonnement kunnen gaan."""
    return [os.path.join(m, n) for m in (BEHEERD if mappen is None else mappen)
            for n in ("managed-settings.json", "managed-settings.d", "managed-mcp.json") if os.path.exists(os.path.join(m, n))]


def lees_token(pad=None):
    """Het abonnementstoken uit het eigen bestand van De Prijsonderzoeker (rechten 600; overleg 14, X8 en K8)."""
    pad = pad or TOKEN_BESTAND
    try:
        rechten = os.stat(pad).st_mode
        with open(pad, encoding="utf-8") as f:
            inhoud = f.read()
    except OSError as e:
        raise GeenAbonnement(f"geen abonnementstoken in {pad}") from e
    if rechten & 0o077:
        raise GeenAbonnement(f"{pad} is leesbaar voor anderen; rechten 600 nodig")
    m = re.search(r"sk-ant-oat[\w-]+", inhoud)
    if not m:
        raise GeenAbonnement(f"{pad} bevat geen token uit claude setup-token")
    return m.group(0)


def omgeving(token, werkmap, bron=None):
    """De omgeving van claude -p: alleen de witte lijst en het abonnementstoken, nooit een API-sleutel (K1), en een
    eigen lege configuratiemap in de werkmap: niets uit ~/.claude van de VM (instellingen, sleutels, plugins) telt."""
    bron = os.environ if bron is None else bron
    env = {k: bron[k] for k in OMGEVING if bron.get(k)}
    config = os.path.join(werkmap, "claude-config")
    os.makedirs(config, mode=0o700, exist_ok=True)
    env.update({"CLAUDE_CODE_OAUTH_TOKEN": token, "DISABLE_AUTOUPDATER": "1", "CLAUDE_CONFIG_DIR": config})
    return env


def te_vol(nu=None):
    """Lag de laatst gemeten benutting van een venster boven de grens, en is dat venster nog niet herstart?"""
    nu = time.time() if nu is None else nu
    try:
        with open(LIMIET_BESTAND, encoding="utf-8") as f:
            vensters = json.load(f).get("vensters") or {}
    except (OSError, ValueError, AttributeError):
        return False
    return any(isinstance(v, dict) and (v.get("utilization") or 0) >= GRENS_GEBRUIK and (v.get("resetsAt") or 0) > nu
               for v in vensters.values())


def bewaar_limiet(vensters):
    """De gemeten vensters van deze vraag bewaren voor de volgende (rechten 600)."""
    if not vensters:
        return
    os.makedirs(os.path.dirname(LIMIET_BESTAND), mode=0o700, exist_ok=True)
    nieuw = LIMIET_BESTAND + ".nieuw"
    with open(os.open(nieuw, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
        json.dump({"vensters": vensters, "gemeten": time.strftime("%Y-%m-%dT%H:%M:%S")}, f)
    os.replace(nieuw, LIMIET_BESTAND)


def voor_de_start(token, werkmap):
    """Voor er een aanvraag naar het model gaat: geen beheerde instellingen op deze machine (Codex controle 15), en
    `claude auth status` (geen modelaanvraag) toont een persoonlijk abonnement zonder centrale instellingen (Codex
    controle 16). Geeft het accounttype; GeenAbonnement als iets niet klopt."""
    gevonden = beheerde_instellingen()
    if gevonden:
        raise GeenAbonnement(f"beheerde instellingen van Claude Code gevonden ({', '.join(gevonden)}); niet gestart")
    try:
        r = subprocess.run([CLAUDE, "auth", "status", "--json"], capture_output=True, text=True, timeout=60,
                           cwd=werkmap, env=omgeving(token, werkmap), stdin=subprocess.DEVNULL)
        status = json.loads(r.stdout)
    except (subprocess.TimeoutExpired, OSError, ValueError) as e:
        raise GeenAbonnement(f"claude auth status niet leesbaar ({type(e).__name__})") from e
    soort = str(status.get("subscriptionType") or "").lower()
    if (not status.get("loggedIn") or status.get("apiProvider") != "firstParty" or status.get("apiKeySource")
            or status.get("authMethod") != "oauth_token"):
        raise GeenAbonnement(f"het abonnementstoken wordt niet aanvaard (claude auth status: {status.get('authMethod')})")
    # Met een token uit setup-token toont auth status geen abonnementstype (gemeten 01-11-2026 door de bouwsessie,
    # Claude Code 2.1.302: alleen loggedIn, authMethod oauth_token, apiProvider). Staat het type er wel, dan moet het
    # persoonlijk zijn; een Team- of Enterprise-account herkennen we anders aan centrale instellingen, hier en bij de
    # start van claude -p (verwerk_regel, init).
    if soort and soort not in PERSOONLIJK:
        raise GeenAbonnement(f"geen persoonlijk abonnement (soort {soort}); niet gestart")
    if centraal_ingesteld(os.path.join(werkmap, "claude-config")):
        raise GeenAbonnement("het account krijgt centrale instellingen; niet gestart")
    return soort or "oauth_token"


def centraal_ingesteld(config):
    """Heeft Claude Code centrale instellingen van een organisatie opgehaald in deze configuratiemap?"""
    try:
        with open(os.path.join(config, "remote-settings.json"), encoding="utf-8") as f:
            return bool(json.load(f))
    except (OSError, ValueError):
        return False


def opdrachtregel(werkmap, systeem, model=None):
    """claude -p met alleen WebSearch en de eigen leestool (--restricted zet Bash, WebFetch en de rest uit), een hook
    die de zoekopdrachten telt, en geen instellingen of MCP-servers van de VM (overleg 14, X1, X3, K2)."""
    teller = os.path.join(werkmap, "zoekteller")
    # De systeemtekst via een bestand: geen grens op de lengte van een argument en niet zichtbaar in de proceslijst.
    with open(os.path.join(werkmap, "systeem.txt"), "w", encoding="utf-8") as f:
        f.write(systeem)
    mcp = {"mcpServers": {"lees": {"type": "stdio", "command": sys.executable,
                                   "args": [os.path.join(HIER, "leesserver.py")],
                                   "env": {"LEES_LOG": os.path.join(werkmap, "gelezen.jsonl"),
                                           "PRIJS_MAX_LEZEN": str(MAX_LEZEN),
                                           "PRIJS_MAX_PAGINA_TOKENS": str(MAX_PAGINA_TOKENS)}}}}
    hook = " ".join(shlex.quote(x) for x in (sys.executable, os.path.join(HIER, "zoekgrens.py"), teller, str(MAX_ZOEKEN)))
    instellingen = {"hooks": {"PreToolUse": [{"matcher": ZOEK, "hooks": [{"type": "command", "command": hook}]}]}}
    return [CLAUDE, "-p", "--output-format", "stream-json", "--verbose", "--model", model or MODEL, "--effort", "medium",
            "--system-prompt-file", os.path.join(werkmap, "systeem.txt"), "--restricted", "--tools", ZOEK, "--allowedTools", f"{ZOEK},{LEES}",
            "--strict-mcp-config", "--mcp-config", json.dumps(mcp), "--settings", json.dumps(instellingen),
            "--no-session-persistence"]


class _Stand:
    def __init__(self):
        self.bron = self.model = self.einde = None
        self.zoek, self.teksten = {}, []
        self.zoekvragen = self.gezocht = self.beurten = 0
        self.limiet = False
        self.extra_verbruik = None          # overageStatus uit de stream, voor het werkverslag
        self.soort = None                   # het abonnement volgens claude auth status
        self.config = None                  # de eigen configuratiemap van claude -p
        self.vensters = {}                  # {venster: {utilization, resetsAt}} uit de stream


def verwerk_regel(st, d):
    """Een regel van de stream-json bijhouden. Geeft de reden om claude meteen te stoppen, of None."""
    soort = d.get("type")
    if soort == "system" and d.get("subtype") == "init":
        st.bron, st.model = d.get("apiKeySource"), d.get("model")
        if st.bron != "none":
            return "bron"                 # een API-sleutel of iets anders dan het abonnement (K1)
        if st.config and centraal_ingesteld(st.config):
            return "centraal"             # centrale instellingen van een organisatie: stoppen voor de eerste aanvraag
    elif soort == "rate_limit_event":
        info = d.get("rate_limit_info") or {}
        # overageStatus wordt alleen bewaard: de betekenis is niet gedocumenteerd en blokkeert dus niet (overleg 25, X1).
        st.extra_verbruik = info.get("overageStatus", st.extra_verbruik)
        for naam, v in (info.get("unifiedWindows") or {}).items():
            if isinstance(v, dict):
                st.vensters[str(naam)] = {"utilization": v.get("utilization"), "resetsAt": v.get("resetsAt")}
        if info.get("isUsingOverage"):
            return "betaald"              # extra verbruik bovenop het abonnement kost geld: meteen stoppen
        st.limiet = st.limiet or info.get("status") == "rejected"
        vensters = [info] + [v for v in (info.get("unifiedWindows") or {}).values() if isinstance(v, dict)]
        if any(isinstance(v.get("utilization"), (int, float)) and v["utilization"] >= GRENS_GEBRUIK for v in vensters):
            st.limiet = True
            return "vol"                  # voor de limiet stoppen, nooit erover (Codex controle 15, punt 1)
    elif soort == "assistant":
        st.beurten += 1
        for b in (d.get("message") or {}).get("content") or []:
            if b.get("type") == "tool_use" and b.get("name") == ZOEK:
                st.zoekvragen += 1
            elif b.get("type") == "text" and b.get("text"):
                st.teksten.append(b["text"])
        if st.beurten > MAX_BEURTEN:
            return "beurten"
    elif soort == "user" and isinstance(d.get("tool_use_result"), dict) and "results" in d["tool_use_result"]:
        st.gezocht += 1
        for url, titel in zoekresultaten_uit(d["tool_use_result"]).items():
            st.zoek[url] = (st.zoek.get(url, "") + " " + titel).strip()
        if st.gezocht > MAX_ZOEKEN:
            return "zoeken"               # de hook weigerde niet: de runner houdt de grens zelf (overleg 14, K3)
    elif soort == "result":
        st.einde = d
        return "einde"                    # de laatste regel: niet wachten op een stdout die open blijft (punt 4)
    return None


def _stop_groep(proc):
    """claude en zijn leestool samen stoppen: ze draaien in een eigen procesgroep (overleg 14, X4)."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def _draai(cmd, env, werkmap, invoer, deadline, st):
    """claude -p draaien tot het einde, de deadline of een reden om te stoppen. Geeft die reden of None. De vraag
    gaat in een eigen draad naar stdin, zodat een kind dat niet leest de deadline niet tegenhoudt, en claude met zijn
    leestool wordt altijd gestopt, ook na een fout (Codex controle 15, punt 4)."""
    reden = None
    with open(os.path.join(werkmap, "fouten.txt"), "w", encoding="utf-8") as fouten:
        proc = subprocess.Popen(cmd, cwd=werkmap, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=fouten, text=True, start_new_session=True)
        try:
            regels = queue.Queue()

            def lezer():
                for r in proc.stdout:
                    regels.put(r)
                regels.put(None)

            def schrijver():
                try:
                    proc.stdin.write(invoer)
                    proc.stdin.close()
                except (OSError, ValueError):
                    pass

            threading.Thread(target=lezer, daemon=True).start()
            threading.Thread(target=schrijver, daemon=True).start()
            while reden is None:
                rest = deadline - time.monotonic()
                if rest <= 0:
                    reden = "tijd"
                    break
                try:
                    r = regels.get(timeout=min(rest, 5))
                except queue.Empty:
                    continue
                if r is None:
                    break
                try:
                    d = json.loads(r)
                except ValueError:
                    continue
                if isinstance(d, dict):
                    reden = verwerk_regel(st, d)
            if reden in (None, "einde"):
                try:
                    proc.wait(timeout=max(0.5, min(5.0, deadline - time.monotonic())))
                except subprocess.TimeoutExpired:
                    pass
        finally:
            _stop_groep(proc)             # ook na een gewoon einde of een fout: geen leestool blijft achter
    return None if reden == "einde" else reden


def _fouttekst(werkmap, einde):
    try:
        with open(os.path.join(werkmap, "fouten.txt"), encoding="utf-8") as f:
            fout = f.read()[-500:]
    except OSError:
        fout = ""
    tekst = f"{(einde or {}).get('result') or ''} {fout}"
    return re.sub(r"sk-ant-\w+-[\w-]+", "sk-ant-…", tekst).strip()[:500]


def onderzoek(vraag, werkwijze, vandaag="", vaste_eisen=(), deadline=None, token=None, werkmap=None):
    """Een prijsvraag uitvoeren via het abonnement. Geeft {gegevens, gelezen, zoekresultaten, tekst, tokens, tellers,
    leesbeurten, zoekopdrachten, stop, model, beurten, bron}. gegevens is None als het model geen leesbaar JSON-object
    gaf; gelezen is {url: paginatekst}. stop: klaar, plafond (tijd, beurten of zoekgrens), limiet (abonnement) of fout.
    GeenAbonnement als er geen geldig token is of als Claude Code iets anders dan het abonnement gebruikt.
    deadline: time.monotonic() waarop de vraag klaar moet zijn (de deadline van de ronde, Codex X6 en overleg 14, X4)."""
    deadline = deadline or time.monotonic() + 420
    token = token or lees_token()
    if te_vol():
        # Niet starten: de vorige meting zat boven de grens en het venster is nog niet herstart (overleg 25, K2).
        return {"gegevens": None, "gelezen": {}, "zoekresultaten": {}, "tekst": "", "tokens": 0, "tellers": [],
                "leesbeurten": (0, 0), "zoekopdrachten": 0, "stop": "limiet", "model": MODEL, "beurten": 0, "bron": None,
                "reden": "vol_vooraf", "extra_verbruik": None, "abonnement": None, "fout": ""}
    systeem, gebruiker = opdracht(werkwijze, vraag, vandaag, vaste_eisen)
    eigen_map = werkmap is None
    werkmap = werkmap or tempfile.mkdtemp(prefix="prijsvraag-")
    st = _Stand()
    try:
        st.soort = voor_de_start(token, werkmap)
        st.config = os.path.join(werkmap, "claude-config")
        reden = _draai(opdrachtregel(werkmap, systeem), omgeving(token, werkmap), werkmap, gebruiker, deadline, st)
        gelezen, leesbeurten = gelezen_uit(os.path.join(werkmap, "gelezen.jsonl"))
        fout = _fouttekst(werkmap, st.einde)
    finally:
        bewaar_limiet(st.vensters)
        if eigen_map:
            shutil.rmtree(werkmap, ignore_errors=True)
    if reden == "bron":
        raise GeenAbonnement(f"Claude Code gebruikte {st.bron!r} in plaats van het abonnement; meteen gestopt")
    if reden == "betaald":
        raise GeenAbonnement("Claude Code startte extra betaald verbruik bovenop het abonnement; meteen gestopt")
    if reden == "centraal":
        raise GeenAbonnement("het account krijgt centrale instellingen van een organisatie; meteen gestopt")
    if st.bron != "none":
        # Bij elk einde, ook na de deadline (Codex controle 21, punt 1).
        raise GeenAbonnement("geen startbericht van claude -p: de bron is niet bewezen (Codex controle 20)")
    einde = st.einde or {}
    if einde.get("is_error") and re.search(r"not logged in|/login|oauth|invalid api key|authenticat", fout, re.I):
        raise GeenAbonnement(f"het abonnementstoken werkt niet: {fout[:200]}")
    if reden == "vol":
        stop = "limiet"
    elif reden:
        stop = "plafond"
    elif st.limiet or (einde.get("is_error") and re.search(r"limit|usage|quota", fout, re.I)):
        stop = "limiet"
    elif not st.einde or einde.get("is_error"):
        stop = "fout"
    else:
        stop = "klaar"
    tekst = str(einde.get("result") or "".join(st.teksten[-1:])).strip()
    gebruik = einde.get("usage") or {}
    tellers = {"input": gebruik.get("input_tokens", 0) or 0, "output": gebruik.get("output_tokens", 0) or 0,
               "cache_schrijven": gebruik.get("cache_creation_input_tokens", 0) or 0,
               "cache_lezen": gebruik.get("cache_read_input_tokens", 0) or 0,
               "zoek": st.gezocht, "lees": sum(leesbeurten)}
    return {"gegevens": json_uit(tekst), "gelezen": gelezen, "zoekresultaten": st.zoek, "tekst": tekst,
            "tokens": tellers["input"] + tellers["output"] + tellers["cache_schrijven"] + tellers["cache_lezen"],
            "tellers": [tellers], "leesbeurten": leesbeurten, "zoekopdrachten": st.gezocht, "stop": stop,
            "model": st.model or MODEL, "beurten": st.beurten, "bron": st.bron, "reden": reden,
            "extra_verbruik": st.extra_verbruik, "abonnement": st.soort,
            "fout": fout if stop in ("fout", "limiet") else ""}


def proef_abonnement(token=None, wacht=120):
    """Een korte vraag via het abonnement, zonder tools: (gelukt, melding). Na het aanmelden of een uitrol: toont dat het
    token werkt en dat Claude Code geen API-sleutel gebruikt (overleg 14, X7). Geen poort meer (overleg 25)."""
    try:
        token = token or lees_token()
    except GeenAbonnement as e:
        return False, str(e)
    with tempfile.TemporaryDirectory(prefix="abonnement-") as werkmap:
        try:
            soort = voor_de_start(token, werkmap)
        except GeenAbonnement as e:
            return False, str(e)
        cmd = [CLAUDE, "-p", "--output-format", "stream-json", "--verbose", "--model", "haiku", "--restricted",
               "--tools", "", "--strict-mcp-config", "--no-session-persistence"]
        try:
            r = subprocess.run(cmd, input="Antwoord alleen met het woord: ok", capture_output=True, text=True,
                               timeout=wacht, cwd=werkmap, env=omgeving(token, werkmap))
        except (subprocess.TimeoutExpired, OSError) as e:
            return False, f"claude -p antwoordde niet ({type(e).__name__})"
    st = _Stand()
    for regel in r.stdout.splitlines():
        try:
            d = json.loads(regel)
        except ValueError:
            continue
        reden = verwerk_regel(st, d) if isinstance(d, dict) else None
        if reden == "bron":
            return False, f"Claude Code gebruikte {st.bron!r} in plaats van het abonnement"
        if reden == "betaald":
            return False, "Claude Code startte extra betaald verbruik"
        if reden == "vol":
            return False, f"het abonnement zit boven {GRENS_GEBRUIK:.0%} van een limiet; later opnieuw"
    einde = st.einde or {}
    if st.bron != "none":
        return False, "geen startbericht van claude -p: de bron is niet bewezen"
    if not einde or einde.get("is_error"):
        tekst = str(einde.get("result") or r.stderr[-300:] or "geen eindregel")
        return False, re.sub(r"sk-ant-\w+-[\w-]+", "sk-ant-…", tekst)[:300]
    bewaar_limiet(st.vensters)
    return True, f"werkt via het abonnement {soort} (model {st.model}, bron {st.bron}, extra verbruik: {st.extra_verbruik})"


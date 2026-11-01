"""Het zoekwerk van De Aannemerszoeker: firma's die een werk kunnen uitvoeren in een gebied, via Claude op het
abonnement van Mehdi (koppelingen/claude_abonnement.py: Claude Code met WebSearch en WebFetch, nooit de API-sleutel), en
de controles die niet van het model afhangen.

Naar buiten (het model en de zoekmachine) gaan alleen het werk, de gemeente en de straal, en of het om uitvoering voor
een bouwheer of om onderaanneming gaat. Nooit de naam van de firma die zoekt, de bouwheer of het werfadres.

Grendels in de code:
  - een firma telt alleen als de code haar eigen pagina zelf las (lees_sites, bouw/webpagina.py): WebFetch geeft een
    samenvatting, de code moet het citaat, het nummer en het contact letterlijk terugvinden;
  - een ondernemingsnummer moet de Belgische controle (modulo 97) halen, anders vervalt het;
  - "actief in de KBO" alleen als de KBO-pagina met dat nummer "Actief" toont; de code leest die pagina zelf
    (kbo_van_code);
  - de afstand rekent de code met Geopunt (koppelingen/adresregister.py); buiten de straal komt apart.
"""
import math
import re
import time
from urllib.parse import parse_qs, urlsplit

from aankoop import onderzoek as O

from . import scheiding as S

# Grenzen per vraag (Mehdi 01-11-2026: op het abonnement, dus zonder geld per token, maar binnen zijn limieten): weinig
# zoek- en leesbeurten, een vast aantal beurten voor Claude Code, en de code leest hoogstens PER_FIRMA pagina's per firma.
MAX_ZOEKEN = 5
MAX_LEZEN = 12
MAX_BEURTEN = 25
MAX_GEREEDSCHAP = 2 * (MAX_ZOEKEN + MAX_LEZEN)    # harde grens: daarboven stopt de code Claude Code (controle 17)
PER_FIRMA = 4
MAX_SITES = 10
LEESTIJD = 90          # seconden die na het model overblijven voor de pagina's en de KBO
KBO = "kbopub.economie.fgov.be"
MIN_TEKST = 100

VORM = """Lever na je zoekwerk precies een JSON-object tussen ```json en ```, met deze velden:
{
  "vraag_kort": "het werk en het gebied in een zin",
  "aannames": ["wat je aannam omdat het niet in de vraag stond"],
  "firmas": [
    {"naam": "naam zoals op de website", "url": "de pagina van de firma die je met WebFetch las",
     "paginas": ["de andere pagina's van dezelfde site die je las: waar het werk staat, waar het ondernemingsnummer
       en het contact staan"],
     "gemeente": "gemeente van de vestiging", "postcode": "1234", "adres": "straat en nummer, of null",
     "telefoon": "zoals op de site, of null", "email": "zoals op de site, of null",
     "ondernemingsnummer": "0123.456.789 zoals op de eigen site, of null",
     "specialiteit": "wat ze doen, kort", "bewijs": "een zin letterlijk overgenomen van een gelezen eigen pagina die toont dat ze dit werk doen",
     "werkgebied": "wat de site zegt over hun werkgebied, of null", "waarom": "een zin: waarom deze firma past"}
  ],
  "werkomschrijving": "een korte alinea voor de prijsaanvraag: wat er moet gebeuren, met de omvang als die
    gegeven is; zonder namen, adressen of bedragen",
  "niet_gevonden": ["wat je zocht en niet vond, met waar je zocht"],
  "vervolgvraag": "een gebundelde vraag als iets beslissends ontbreekt, anders null"
}
Regels: geef alleen firma's waarvan je een eigen pagina (website, of hun pagina op een vakfederatie of gids) zelf met
WebFetch las en waar het werk op staat. De code leest die pagina's daarna zelf en zoekt je citaat, het nummer en het
contact er letterlijk in: kopieer ze dus woord voor woord. Verzin nooit een telefoonnummer, mailadres of ondernemingsnummer: null als je
het niet zag. Zoek het ondernemingsnummer op de eigen site (voettekst, contactpagina, algemene voorwaarden); de code leest
de KBO zelf, lees die dus niet.
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
             "pagina zag.", "JOUW WERKWIJZE (ze geldt):\n" + modelwerkwijze(werkwijze),
             # Live gemeten 01-11-2026: zonder deze zin las het model "zonder firma begin ik niet" en zocht het niets
             "VOOR DEZE VRAAG: de firma die zoekt is gekend en bewust weggelaten; de code houdt ze apart, doet haar eigen "
             "mappen en boekhouding en schrijft de mails. Vraag dus nooit voor welke firma het is en begin meteen: jij "
             "doet alleen het web."]
    if kennis:
        delen.append(kennis)
    systeem = "\n\n".join(delen + [VORM])
    gebruiker = (f"Vandaag is {vandaag}. Gezocht: {wie}.\nWERK: {werk}\n" + (f"OMVANG: {omvang}\n" if omvang else "")
                 + f"GEBIED: {gemeente}, binnen ongeveer {straal_km} km.\n"
                 "Zoek op het web en lees de pagina van elke firma met WebFetch voor je ze opneemt. Mik op vijf tot "
                 "acht firma's, liefst dicht bij het gebied, en geef liever minder dan een firma waarover je twijfelt. "
                 f"Gebruik hoogstens {MAX_ZOEKEN} keer WebSearch en {MAX_LEZEN} keer WebFetch; lever daarna meteen het "
                 "JSON-object.")
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


KBO_PAGINA = "https://kbopub.economie.fgov.be/kbopub/{}.html?ondernemingsnummer={}&lang=nl"
KBO_STATUS = {"actief": True, "stopgezet": False, "niet actief": False, "doorgehaald": False, "ontbonden": False}
KBO_TIMEOUT = 10     # seconden per KBO-pagina; een oproep start alleen als ze voor de deadline klaar kan zijn


def _tijd_voor(deadline):
    return not deadline or time.monotonic() + KBO_TIMEOUT <= deadline


def kbo_van_code(nummer, haal, deadline=None):
    """{"actief": True/False/None, "plaats": 'postcode gemeente' of None} uit de openbare KBO-pagina's, door de code zelf
    gelezen. De plaats is de zetel; toont de pagina geen zetel (een natuurlijk persoon), dan de enige vestigingseenheid.
    Nooit de straat: alleen postcode en gemeente. Een pagina met een ander nummer telt niet. haal: url -> html; een
    OSError op de hoofdpagina gaat naar boven, op de vestigingspagina laat ze de plaats leeg."""
    from .kern_adres import POSTCODE, _cel, _regels
    kaal = re.sub(r"\D", "", nummer or "").zfill(10)

    def eigen(pagina):
        return re.sub(r"\D", "", " ".join(_regels(_cel(pagina, "Ondernemingsnummer")))) == kaal

    def plaats(pagina, label):
        for regel in _regels(_cel(pagina, label)):
            m = POSTCODE.match(regel)
            if m:
                return f"{m['postcode']} {m['gemeente']}"
        return None

    pagina = haal(KBO_PAGINA.format("toonondernemingps", kaal))
    if not eigen(pagina):
        return {"actief": None, "plaats": None}
    status = " ".join(" ".join(_regels(_cel(pagina, "Status"))).lower().split())
    uit = {"actief": KBO_STATUS.get(status), "plaats": plaats(pagina, "Adres van de zetel")}
    aantal = " ".join(_regels(_cel(pagina, re.escape("Aantal vestigingseenheden (VE)"))))
    if uit["actief"] and not uit["plaats"] and re.match(r"^1\b", aantal) and _tijd_voor(deadline):  # Codex 15, punt 3
        try:
            ve = haal(KBO_PAGINA.format("toonvestigingps", kaal))
        except OSError:
            ve = ""
        if eigen(ve):
            uit["plaats"] = plaats(ve, r"Adres van de vestigingseenheid\s*:?\s*(?:<br\s*/?>)?")   # label met <br/>
    return uit


def lees_kbo(firmas, haal, deadline=None):
    """{nummer: kbo_van_code(...)} voor elk geldig ondernemingsnummer, elk een keer (Codex 15, punt 2: ook na een fout);
    een KBO die niet antwoordt, laat het nummer weg. Een oproep start alleen als ze voor de deadline (time.monotonic)
    klaar kan zijn."""
    uit, gevraagd = {}, set()
    for f in firmas or []:
        nr = btw_geldig(f.get("ondernemingsnummer")) if isinstance(f, dict) else None
        if not nr or nr in gevraagd:
            continue
        if not _tijd_voor(deadline):
            break
        gevraagd.add(nr)
        try:
            uit[nr] = kbo_van_code(nr, haal, deadline)
        except OSError:
            continue
    return uit


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


def _plat(tekst):
    return " ".join(re.sub(r"[^\w]+", " ", S.normaal(tekst).lower()).split())


def naam_en_werk_op_site(f, gelezen):
    """Codex X1 (controle 7): een pagina met alleen het nummer in de voettekst bewijst niets. Op een gelezen pagina van
    dezelfde site moeten ook de naam van de firma (haar langste woord buiten de rechtsvorm) en de zin over het werk
    (het bewijs dat het model citeerde, minstens twintig tekens) letterlijk staan."""
    eigen = host(O.schoon_url(f.get("url")))
    tekst = " ".join(_plat(t) for u, t in (gelezen or {}).items() if eigen and host(u) == eigen)
    from .vakwoorden import toegelaten
    woorden = [w for w in _plat(f.get("naam")).split() if w not in {"bv", "nv", "bvba", "comm", "commv", "vof", "srl", "sa"}]
    eigen_woorden = [w for w in woorden if not toegelaten(w)]     # Codex X3 (controle 8): niet 'dakwerken' maar 'Fantasio'
    tokens = set(tekst.split())
    if eigen_woorden:
        naam_ok = all(w in tokens for w in eigen_woorden)
    else:
        naam_ok = bool(woorden) and " ".join(woorden) in tekst
    bewijs = _plat(f.get("bewijs"))
    return naam_ok and len(bewijs) >= 20 and bewijs in tekst


def contact_van_site(f, gelezen):
    """Codex X5 (controle 9): een mailadres of telefoonnummer blijft alleen staan als het op een gelezen pagina van de
    eigen site staat (het telefoonnummer op cijfers vergeleken); anders wordt het leeg, nooit verzonnen."""
    eigen = host(O.schoon_url(f.get("url")))
    tekst = " ".join(t or "" for u, t in (gelezen or {}).items() if eigen and host(u) == eigen)
    mail = str(f.get("email") or "").strip()
    if mail and mail.lower() not in tekst.lower():
        f["email"] = None
    tel = re.sub(r"\D", "", str(f.get("telefoon") or ""))
    if tel and (len(tel) < 8 or tel[-8:] not in re.sub(r"\D", "", tekst)):
        f["telefoon"] = None


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


def eigen_paginas(f, gelezen):
    """{url: tekst} van de pagina's die bij deze firma horen: wat de code voor haar las (f["_paginas"], lees_sites);
    zonder die lijst alle gelezen pagina's (de functies hieronder houden dan alleen de eigen site over)."""
    if not isinstance(gelezen, dict):
        return {}
    if isinstance(f.get("_paginas"), list):
        return {u: gelezen[u] for u in f["_paginas"] if u in gelezen}
    return gelezen


def sleutel(f):
    """Om dubbels weg te halen: het ondernemingsnummer, anders het domein van de website."""
    if f.get("ondernemingsnummer"):
        return f["ondernemingsnummer"]
    url = O.schoon_url(f.get("url"))
    return url.split("/")[2] if url else ""


def keur(firmas, gelezen, centrum, straal_km, lokaliseer, kbo=None):
    """{"goed", "na_te_kijken", "buiten", "afgewezen"} (overleg X2, G2). Bovenaan alleen wie een gelezen eigen pagina
    heeft, een gelezen KBO-pagina die actief toont en binnen de straal ligt. Zonder KBO-bewijs of zonder bekende afstand:
    na te kijken, nooit groen. lokaliseer: 'postcode gemeente' -> {lat, lon} of None (Geopunt). kbo: wat de code zelf in
    de KBO las (lees_kbo); dat gaat voor op een pagina die het model las."""
    gelezen_firmas, afgewezen = O.alleen_gelezen([f for f in firmas or [] if isinstance(f, dict)], gelezen)
    met_tekst = []
    for f in gelezen_firmas:     # Codex X6 (controle 2): een gelezen pagina zonder tekst bewijst niets
        url = O.schoon_url(f.get("url"))
        eigen = eigen_paginas(f, gelezen)
        if host(url) == KBO:     # Codex X2 (controle 3): de KBO is geen eigen pagina van de firma
            afgewezen.append({"aanbod": f, "redenen": ["alleen een KBO-pagina, geen eigen pagina"]})
        elif sum(len((t or "").strip()) for t in eigen.values()) < MIN_TEKST:   # controle 17: over al haar pagina's
            afgewezen.append({"aanbod": f, "redenen": ["pagina zonder leesbare tekst"]})
        else:
            met_tekst.append(f)
    uit = {"goed": [], "na_te_kijken": [], "buiten": [], "afgewezen": afgewezen}
    kandidaten = []
    for f in met_tekst:
        eigen = eigen_paginas(f, gelezen)
        f["ondernemingsnummer"] = btw_geldig(f.get("ondernemingsnummer"))
        door_code = f["ondernemingsnummer"] in (kbo or {})      # Codex 15, punt 1: dan telt alleen wat de code las
        zelf = (kbo or {}).get(f["ondernemingsnummer"]) or {}
        f["kbo_actief"] = zelf.get("actief") if door_code else kbo_actief(f["ondernemingsnummer"], gelezen)
        # Codex X2 (controle 6): de site hoort bij de onderneming als het nummer op een gelezen pagina van die site
        # staat (een Belgische firmasite moet het tonen); anders is de site niet bewezen en komt ze bij na te kijken
        f["site_bewezen"] = (nummer_op_site(f["ondernemingsnummer"], f.get("url"), eigen)
                             and naam_en_werk_op_site(f, eigen))
        contact_van_site(f, eigen)
        if f["kbo_actief"] is False:
            uit["afgewezen"].append({"aanbod": f, "redenen": ["stopgezet volgens de KBO"]})
            continue
        kandidaten.append((f, zelf, door_code))
    # Codex, controle 17: bij een dubbel (zelfde nummer of domein) blijft de best bewezen kandidaat, niet de eerste
    kandidaten.sort(key=lambda k: (not k[0]["site_bewezen"], k[0]["kbo_actief"] is not True))
    gezien = set()
    for f, zelf, door_code in kandidaten:
        k = sleutel(f)
        if k in gezien:
            continue
        gezien.add(k)
        # De afstand alleen vanaf de zetel in de KBO (Codex X3 controle 3, X3 controle 4, X1 controle 5): wat het model of
        # de website als adres geeft, kan een werkgebied of een project zijn.
        plaats = None
        if f["kbo_actief"]:
            plaats = zelf.get("plaats") if door_code else kbo_zetel(f["ondernemingsnummer"], gelezen)
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


def lees_sites(firmas, gehaald, haal, deadline=None, werkers=6):
    """{schoon_url: tekst} van de pagina's die de code zelf las: per firma haar url, de pagina's die het model noemt en
    wat het met WebFetch op dezelfde site opende, hoogstens PER_FIRMA per firma en MAX_SITES firma's. Een pagina die niet
    antwoordt, ontbreekt; een oproep start alleen als ze voor de deadline klaar kan zijn. haal: url -> html."""
    from concurrent.futures import ThreadPoolExecutor

    from . import webpagina as WP
    # De code haalt de url zoals het model ze gaf (een site zonder www. bestaat soms niet) en bewaart ze onder schoon_url
    origineel = {}
    for u in [x for f in firmas or [] if isinstance(f, dict)
              for x in [f.get("url")] + (f.get("paginas") if isinstance(f.get("paginas"), list) else [])] + list(gehaald or []):
        origineel.setdefault(O.schoon_url(u), str(u or "").strip())
    gehaald = [O.schoon_url(u) for u in gehaald or []]
    firmas = [f for f in firmas or [] if isinstance(f, dict)][:MAX_SITES]
    # Codex, controle 17: delen firma's een site (een gids), dan krijgt elke firma alleen haar eigen pagina's en niets uit
    # wat het model daar verder opende; elke pagina hoort bij hoogstens een firma (f["_paginas"]).
    per_host = {}
    for f in firmas:
        per_host[host(O.schoon_url(f.get("url")))] = per_host.get(host(O.schoon_url(f.get("url"))), 0) + 1
    lijst, gezien = [], set()
    for f in firmas:
        eigen = O.schoon_url(f.get("url"))
        f["_paginas"] = []
        if not eigen:
            continue
        extra = [O.schoon_url(p) for p in (f.get("paginas") if isinstance(f.get("paginas"), list) else [])]
        per = []
        for u in [eigen] + extra + (gehaald if per_host[host(eigen)] == 1 else []):
            if u and host(u) == host(eigen) and u not in per:
                per.append(u)
        for u in per[:PER_FIRMA]:
            if u not in gezien:
                gezien.add(u)
                lijst.append(u)
                f["_paginas"].append(u)

    def een(u):
        if deadline and time.monotonic() + WP.TIMEOUT > deadline:
            return u, None
        try:
            return u, WP.tekst(haal(origineel.get(u) or u))
        except (OSError, ValueError):
            return u, None

    with ThreadPoolExecutor(max_workers=werkers) as pool:
        return {u: t for u, t in pool.map(een, lijst) if t}


def zoek(werkwijze, werk, gemeente, straal_km, soort, vandaag="", deadline=None, vraag=None, haal=None, omvang="",
         kennis=""):
    """Een zoekvraag uitvoeren via Claude op het abonnement. Geeft {gegevens, gelezen, tekst, tokens, zoekopdrachten,
    leesbeurten, stop, model, beurten}; gegevens is None als het model geen leesbaar JSON-object gaf. gelezen is wat de
    code zelf las (lees_sites), niet wat het model zegt. vraag en haal zijn te vervangen in een test."""
    deadline = deadline or time.monotonic() + 420
    if vraag is None:
        import claude_abonnement
        vraag = claude_abonnement.vraag
    if haal is None:
        from . import webpagina
        haal = webpagina.haal
    systeem, gebruiker = opdracht(werkwijze, werk, gemeente, straal_km, soort, vandaag, omvang, kennis)
    rest = deadline - time.monotonic() - LEESTIJD
    if rest < 60:          # Codex, controle 18: nooit voorbij de deadline van de ronde; de vraag wacht
        import claude_abonnement
        raise claude_abonnement.Fout(f"te weinig tijd in de ronde ({int(rest)} s)", "tijd")
    uit = vraag(systeem, gebruiker, tools=("WebSearch", "WebFetch"), timeout=rest, max_beurten=MAX_BEURTEN,
                max_gereedschap=MAX_GEREEDSCHAP)
    gehaald = [str((inv or {}).get("url") or "") for naam, inv in uit["gereedschap"] if naam == "WebFetch"]
    gegevens = O.json_uit(uit["tekst"])
    gelezen = lees_sites((gegevens or {}).get("firmas"), gehaald, haal, deadline)
    return {"gegevens": gegevens, "gelezen": gelezen, "tekst": uit["tekst"], "tokens": uit["tokens"],
            "zoekopdrachten": sum(1 for naam, _ in uit["gereedschap"] if naam == "WebSearch"), "leesbeurten": len(gehaald),
            "stop": uit["stop"], "model": uit["model"], "beurten": uit["beurten"]}

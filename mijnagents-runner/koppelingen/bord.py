"""Gedeelde bord-client voor de runners van Mehdi Agents: hartslag, werkverslag,
klaarzetten en lezen wat klaargezet is. Token uit mijnagents-data/.env."""
import hashlib
import html
import http.client
import json
import os
import re
import sqlite3
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

# Eigen variabele, bewust niet PLATFORM_URL: die staat ook in het .env van de
# Siyan-tegel (poort 3021) dat koppelingen/pipedrive.py inleest, en dan
# kwam elke klaarzet-aanroep op het verkeerde bord uit (404, 9 tot 15-9).
PLATFORM = os.environ.get("MIJNAGENTS_URL", "http://127.0.0.1:3022")


def token():
    try:
        for regel in open(os.path.expanduser("~/appportal/mijnagents-data/.env")):
            if regel.startswith("AGENTS_TOKEN="):
                return regel.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return os.environ.get("AGENTS_TOKEN", "")


TOKEN = token()


def call(pad, payload=None, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{PLATFORM}{pad}", data=data, method=method or ("POST" if data else "GET"),
                                 headers={"Content-Type": "application/json", "X-Agents-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")


def diagnose(*delen):
    """Diagnostische uitvoer naar stderr die zelf nooit faalt (Codex NA65 en NA70, overleg 14 E2 en 15 F1): een gesloten,
    volle of vervangen uitvoer mag het afsluiten van een ronde niet afbreken."""
    try:
        print(*delen, file=sys.stderr)
    except Exception:  # noqa: BLE001
        pass


class RondeGestopt(RuntimeError):
    """De ronde stopte voor het werk begon, omdat de agent zijn regelboek niet heeft (Codex NA09, 16-10-2026)."""


class WerkwijzeOnbekend(RondeGestopt):
    """De werkwijze kon niet gelezen worden. Onbekend is niet leeg: wie zijn regelboek niet kon lezen,
    werkt niet alsof er geen regels zijn. `soort` zegt waarom, zonder getal erin (N10)."""

    def __init__(self, soort, reden=""):
        self.soort = soort
        self.reden = reden
        super().__init__(f"{soort} ({reden})" if reden else soort)


KOP_NOOIT = re.compile(r"^(?:\d+[.)]\s*)?wat ik nooit doe(?:\s*[(:].*)?$")
KOP_MEHDI = re.compile(r"^(?:\d+[.)]\s*)?wat mehdi beslist(?:\s*[(:].*)?$")
# Een punt is gewone tekst: letters, cijfers, spaties en leestekens, zonder opmaak of HTML die iets kan verbergen
# of anders tonen (Codex NA40), en het begint niet zelf als een lijst ("- a", "1. a").
_LETTER = r"[^\W_]"                                   # letters en cijfers, ook met accent, zonder _
_EERSTE = rf"(?:{_LETTER}|[(\"'‘“])"
_VERDER = rf"(?:{_LETTER}|[ .,;:()'\"/%@+?!’‘“”…€-])*"
PUNT = re.compile(rf"^[-*] +((?![-*+]\s|\d+[.)]){_EERSTE}{_VERDER})$")
KOP_WOORDEN = {KOP_NOOIT.pattern: "wat ik nooit doe", KOP_MEHDI.pattern: "wat mehdi beslist"}
# Ruwe HTML, waar ook in de werkwijze: een tag, commentaar of declaratie (Codex NA36, NA44).
HTML = re.compile(r"<[A-Za-z/!?]")
# Alleen een gewoon regeleinde scheidt regels; Python-Markdown op het bord kent geen andere (Codex NA39).
VREEMDE_SCHEIDING = re.compile("[\u2028\u2029\x0b\x0c\x1c\x1d\x1e\x85]")


def _letters(regel):
    """De zichtbare woorden van een regel: tekenverwijzingen omgezet (&#111; is o), onzichtbare tekens, linkdoelen en
    verwijzingslabels weg, alleen letters, cijfers en enkelvoudige spaties, in kleine letters (Codex NA43, NA46)."""
    regel = html.unescape(regel)
    regel = "".join(c for c in regel if unicodedata.category(c) != "Cf")
    regel = re.sub(r"\]\s*(\([^)]*\)|\[[^\]]*\])", "]", regel)
    regel = "".join(c if c.isalnum() else " " for c in regel)
    return re.sub(r"\s+", " ", regel).strip().lower()


def _kopachtig(regels, i):
    """Kan het bord deze regel als kop tonen: een # vooraan (ook na >, een lijstteken of spaties), of een regel
    die gevolgd wordt door een onderstreping met = of -."""
    if re.match(r"^(?:[>*+\-\s]|\d+[.)])*#", regels[i]):
        return True
    return i + 1 < len(regels) and bool(re.match(r"^\s{0,3}(=+|-+)\s*$", regels[i + 1])) and bool(regels[i].strip())


def _kop(regel):
    """(niveau, koptekst) zoals Python-Markdown een kop leest: # op kolom 0, een spatie erna is niet nodig, # achteraan
    valt weg. None als het geen kop is."""
    m = re.match(r"^(#{1,6})(.*)$", regel)
    if not m:
        return None
    return len(m.group(1)), re.sub(r"#+\s*$", "", m.group(2)).strip().lower()


def _strikte_punten(regels, kop):
    """De punten onder de kop, alleen als de kop de eerste regel is of een lege regel voor zich heeft, en er onder
    die kop niets anders staat dan punten en lege regels. Lopende tekst, een tussenkop, iets ingesprongens, een
    scheidingslijn of een punt met opmaak: dan geen grenzen, want hoe het bord dat toont, is niet zeker (Codex
    NA34, NA37, NA40; de proef tegen de weergave van het bord vond de lege regel voor de kop)."""
    niveau, uit = None, []
    for i, regel in enumerate(regels):
        k = _kop(regel)
        if niveau is None:
            if k and kop.match(k[1]):
                if i and regels[i - 1].strip():
                    # zonder lege regel ervoor kan het bord de kop bij een eerder lijstpunt trekken
                    return []
                niveau = k[0]
            continue
        if k:
            if k[0] <= niveau:
                break
            return []
        if not regel.strip():
            continue
        p = PUNT.match(regel)
        if not p:
            return []
        uit.append(p.group(1).strip())
    return uit


def grenzen(werkwijze):
    """Norm N2 als regels: de punten onder de afgesproken koppen "## Wat ik nooit doe" en "## Wat Mehdi beslist"
    (eventueel genummerd, of met een toevoeging tussen haakjes). Een kop over wat een ander nooit doet, of over
    allebei, telt niet (Codex NA17, NA22, NA27).

    Bewust een vaste, strikte vorm in plaats van een nabootsing van Markdown (stopregel na Codex NA32 tot NA42):
    een werkwijze met ruwe HTML (een tag, commentaar) geeft geen grenzen, want het bord zet die onbewerkt op de
    pagina; gelezen wordt tot de eerste regel met een codeblok (``` of ~~~), en elke
    grenssectie is daarvoor afgesloten door een volgende kop of het einde van de tekst; de kop staat er een keer,
    met een witregel ervoor; onder de kop staan alleen punten ("- " of "* " op kolom 0, gewone tekst) en lege
    regels; alleen een gewoon regeleinde scheidt regels. Wat daar niet in past, geeft geen grenzen: een twijfelgeval wordt geweigerd, nooit aanvaard.
    tests/test_agentnorm.py legt met de Markdown-weergave van het bord vast dat wat hier aanvaard wordt, daar zo
    als kop met lijstpunten staat. De generator eist de grenzen, het sjabloon past ze elke ronde toe."""
    tekst = (werkwijze or "").replace("\r\n", "\n").replace("\r", "\n")
    if VREEMDE_SCHEIDING.search(tekst) or HTML.search(tekst):
        # Codex NA44: het bord zet ruwe HTML onbewerkt op de pagina; ook na de grenzen kan ze die verbergen
        return [], []
    regels = []
    for regel in tekst.split("\n"):
        regel = regel.expandtabs(4)
        if re.match(r"^\s*(`{3,}|~{3,})", regel):
            # Wat hier begint, kan het bord nog bij het laatste punt van een open sectie trekken (na een witregel
            # loopt een lijst door). Een sectie die hier nog open is, telt dus niet: ze moet afgesloten zijn door
            # een volgende kop of door het einde van de tekst.
            regels.append("\x00")
            break
        regels.append(regel.rstrip())
    uit = []
    for kop in (KOP_NOOIT, KOP_MEHDI):
        # De kop staat er maar een keer: twee regels die het bord als die kop kan tonen, ook in code, een citaat, een
        # lijst, met opmaak, een tekenverwijzing of een link, geven twee keer dezelfde kop, en dan is niet zeker welke
        # de mens leest. Ruim geteld: elke kopachtige regel waarin de woorden van de kop staan (Codex NA43, NA46).
        alle = tekst.split("\n")
        woorden = KOP_WOORDEN[kop.pattern]
        if sum(1 for i in range(len(alle)) if _kopachtig(alle, i) and woorden in _letters(alle[i])) != 1:
            uit.append([])
        else:
            uit.append(_strikte_punten(regels, kop))
    return uit[0], uit[1]


class Agent:
    def __init__(self, naam):
        self.naam = naam
        self._log = []
        self._prive = set()
        self._prive_re = None
        # kwam de laatste hartslag aan; None zolang er geen was. Een runner die zijn eindhartslag moet zien aankomen,
        # leest dit na de ronde (De Bouwwacht, Codex-resultaattoets 4, 27-10-2026)
        self.hartslag_ok = None
        self.laatste_status = ""      # de status van de laatste hartslag die aankwam

    # Privacygrens (nacontrole v1.3, R1): een agent meldt de teksten uit een privébron aan (privé-agenda, Lara,
    # Hotmail). Elk bericht naar het bord (hartslag, nood, logboek, klaargezet) gaat door maskeer(), welke route ook.
    PRIVE_NIET = {"mehdi", "mehdi:", "vandaag", "gisteren"}

    def prive(self, teksten):
        nieuw = {t.strip() for t in teksten if isinstance(t, str) and len(t.strip()) >= 4
                 and t.strip().lower() not in self.PRIVE_NIET} - self._prive
        if nieuw:
            self._prive |= nieuw
            self._prive_re = re.compile("|".join(re.escape(t) for t in sorted(self._prive, key=len, reverse=True)), re.I)

    def maskeer(self, obj):
        if self._prive_re is None:
            return obj
        if isinstance(obj, str):
            return self._prive_re.sub("(privé)", obj)
        if isinstance(obj, list):
            return [self.maskeer(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.maskeer(v) for k, v in obj.items()}
        return obj

    def hartslag(self, status, taak="", detail="", voorstel=None, nood=None, sluiten=True):
        """nood: de volledige lijst van wat de agent nodig heeft of wat bij hem niet
        werkt, elk {"tekst": ..., "wie": "mehdi|claude-code|collega"}; wat er niet
        meer in staat, is voor het bord opgelost. sluiten=False: alleen toevoegen,
        het bord sluit niets (de agent weet niet welke noden nog gelden)."""
        p = {"naam": self.naam, "status": status, "taak": taak, "detail": detail}
        if voorstel:
            p["voorstel"] = voorstel
        if nood is not None:
            p["nood"] = nood
            if not sluiten:
                p["nood_sluiten"] = False
        try:
            call("/agent-status", self.maskeer(p))
            self.hartslag_ok = True
            self.laatste_status = status       # voor een vangnet buiten de ronde (De Fathomwacht, overleg 15 F3)
        except Exception as e:  # noqa: BLE001
            self.hartslag_ok = False
            diagnose("hartslag mislukt:", e)

    def log(self, onderwerp, stap, tekst, detail=""):
        self._log.append({"naam": self.naam, "onderwerp": onderwerp, "stap": stap, "tekst": tekst,
                          "detail": detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False, indent=1)})
        # ook de schermregel door het masker: die komt in de cron-logboeken (Codex A25, 15-10-2026)
        print(self.maskeer(f"  [{stap}] {tekst}"))

    def log_verstuur(self):
        """Het werkverslag naar het bord, in hoogstens een poging (overleg 13, D1): de regels gaan weg, ook als het
        versturen mislukt of onderbroken wordt. Opnieuw sturen kan pas als het bord dubbels herkent (NA60): een antwoord
        dat verloren ging na een geslaagde boeking gaf anders hetzelfde verslag twee keer. De regels staan ook in de
        uitvoer van de cron."""
        if not self._log:
            return
        # eerst losmaken, dan versturen (Codex NA63): een signaal tussen versturen en wissen liet anders aangenomen
        # regels staan, en de ronde stuurde ze bij het afsluiten nog eens
        regels, self._log = self._log, []
        try:
            call("/api/logboek", {"regels": self.maskeer(regels)})
        except Exception as e:  # noqa: BLE001
            diagnose("logboek mislukt:", e)

    def werkwijze_lezen(self):
        """De werkwijze zoals ze nu op het bord staat. Een lege tekst is een antwoord en komt terug;
        kon het bord niet antwoorden, dan WerkwijzeOnbekend, nooit een lege tekst (NA09)."""
        try:
            antwoord = call(f"/api/agent/{self.naam}/werkwijze")
        except urllib.error.HTTPError as e:
            soort = {403: "geen toegang tot het bord", 404: "agent staat niet op het bord"}.get(e.code, "bordfout")
            raise WerkwijzeOnbekend(soort, f"HTTP {e.code}") from e
        except (OSError, http.client.HTTPException) as e:
            raise WerkwijzeOnbekend("bord onbereikbaar", type(e).__name__) from e
        except ValueError as e:
            raise WerkwijzeOnbekend("onleesbaar antwoord van het bord", type(e).__name__) from e
        tekst = antwoord.get("werkwijze") if isinstance(antwoord, dict) else None
        if not isinstance(tekst, str):
            raise WerkwijzeOnbekend("onleesbaar antwoord van het bord", "geen werkwijze in het antwoord")
        return tekst

    def werkwijze(self, taak="werkwijze lezen", noden=()):
        """Mijn regelboek van het bord, nooit een lege tekst. Is het onbekend of leeg, dan stopt mijn werk hier:
        een nood met eigenaar, hartslag "fout" zodat N11 en de Normwacht het zien, en RondeGestopt (NA09).
        Zo ook voor de runners die hun werkwijze nog buiten de ronde lezen (agenda-wacht, archivaris,
        fathom-wacht, levenscoach): die werkten tot 16-10-2026 bij een leesfout gewoon door (Codex NA11).
        noden: wat de ronde voor het lezen al wist (begin_noden, X4); dat gaat mee als het werk hier stopt."""
        try:
            tekst = self.werkwijze_lezen()
        except WerkwijzeOnbekend as e:
            self.zonder_regelboek(f"Werkwijze niet gelezen: {e.soort}", "claude-code", taak, e.reden, e, noden=noden)
        if not tekst.strip():
            self.zonder_regelboek("Werkwijze leeg op het bord", "mehdi", taak, noden=noden)
        return tekst

    def zonder_regelboek(self, tekst, wie, taak, reden="", oorzaak=None, noden=()):
        """Stoppen voor het werk begint. De noodtekst blijft gelijk van ronde tot ronde (N10); de reden, zoals
        de HTTP-code, staat in het detail. Er gaat geen kennis mee, want er is niets gelezen.
        noden gaan mee op de lijst (X4). Is die lijst onbekend, dan stuurt de ronde er geen (het bord zou anders
        alles sluiten), en staan hun teksten in het detail, zodat ze niet stil verdwijnen."""
        nieuw = [n for n in noden if n["tekst"] != tekst] + [{"tekst": tekst, "wie": wie}]
        signalen = self.fout_melden(taak, f"{tekst}{f' ({reden})' if reden else ''}; ronde gestopt voor het werk",
                                    nieuw, ook=[n["tekst"] for n in nieuw[:-1]])
        if signalen:
            signalen[0].al_gemeld = True       # de ronde meldt het niet nog eens (Ronde.__enter__)
            raise signalen[0]
        raise RondeGestopt(tekst) from oorzaak

    def fout_melden(self, taak, detail, nieuw, ook=(), verslag=True, nood_ophalen=True):
        """De fouthartslag van een ronde die niet afliep (N11), ook als onderweg een stopsignaal binnenkomt (SIGTERM als
        SystemExit, Ctrl-C; NA61, overleg 13). Eerst het werkverslag (verslag), dan de noodlijst (noden_bij_breuk, als
        nood_ophalen), dan de hartslag. Na een signaal geen bordoproep meer behalve de hartslag: die gaat dan uit zonder
        noodlijst, zodat het bord niets sluit, met wat de ronde vond (ook) in het detail. Geeft de signalen die onderweg
        binnenkwamen; de aanroeper laat het eerste door. De hartslag zelf is een eenmalige beste poging: een signaal
        daarin, of een reeks signalen, vangt niemand nog op (AGENTNORM 5)."""
        signalen, lijst = [], None
        for stap in ((self.log_verstuur,) if verslag else ()) + \
                ((lambda: self.noden_bij_breuk(nieuw),) if nood_ophalen else ()):
            if signalen:
                break
            try:
                uit = stap()
            except BaseException as e:  # een Exception vangen log_verstuur en open_noden zelf
                signalen.append(e)
                continue
            if stap is not self.log_verstuur:
                lijst = uit
        if lijst is None and ook:
            detail += "; ook: " + "; ".join(ook)
        if signalen:
            detail += "; daarna " + "; ".join(f"{type(s).__name__}: {str(s)[:60]}" for s in signalen)
        self.hartslag("fout", taak=taak, detail=detail, nood=lijst)
        if not self.hartslag_ok:
            # Codex NA73: kwam de fouthartslag niet aan (een tijdelijke verzendfout), dan bleef de agent op actief; op main
            # stuurden de oudere runners toevallig nog een tweede. Nu een tweede poging, zonder noodlijst (er sluit niets).
            self.hartslag("fout", taak=taak, detail=detail)
        return signalen

    def noden_bij_breuk(self, nieuw):
        """De noodlijst voor een ronde die niet afliep. Het bord sluit elke open nood die niet in de lijst
        staat; wat al open stond blijft daarom open, want of het intussen opgelost is, weet deze ronde niet.
        Is ook dat onbekend, dan geen lijst, zodat het bord niets sluit (het detail draagt dan de melding)."""
        bestaand = self.open_noden()
        if bestaand is None:
            return None
        teksten = {n["tekst"] for n in bestaand}
        return bestaand + [n for n in nieuw if n["tekst"] not in teksten]

    def open_noden(self):
        """Mijn noden die nu open staan op het bord, of None als dat onbekend is. Een antwoord dat niet de
        verwachte vorm heeft, is onbekend, ook als maar een rij afwijkt (Codex NA23)."""
        try:
            antwoord = call("/api/nood")
        except Exception:  # noqa: BLE001
            return None
        rijen = antwoord.get("nood") if isinstance(antwoord, dict) else None
        if not isinstance(rijen, list) or not all(isinstance(r, dict) for r in rijen):
            return None
        mijn = [r for r in rijen if r.get("naam") == self.naam]
        if not all(isinstance(r.get("tekst"), str) and r["tekst"].strip()
                   and (r.get("wie") is None or isinstance(r.get("wie"), str)) for r in mijn):  # NA28
            return None
        return [{"tekst": r["tekst"], "wie": r.get("wie") or "mehdi"} for r in mijn]

    def kennis(self, tekst, bron=""):
        """Norm N4: melden welk regelboek ik deze ronde las, zodat achteraf te zien is
        welke versie van de regels ik gebruikte toen ik iets deed."""
        try:
            call(f"/api/agent/{self.naam}/kennis", {"kennis": tekst, "bron": bron})
        except Exception as e:  # noqa: BLE001
            diagnose("kennis niet gemeld:", e)

    def klaarzet(self, items):
        """items: lijst van dicts met voor, soort, titel, en optioneel sleutel, inhoud, verwijzing, uniek."""
        for it in items:
            it.setdefault("van", self.naam)
        return call("/api/klaarzet", {"items": self.maskeer(items)}) if items else {"nieuw": 0, "bestaand": 0}

    def ronde(self, taak="ronde", bronnen=None, begin_noden=None, werkwijze=None):
        """De standaarddoorgang van een ronde. Zie AGENTNORM.md.

        Wie hiermee werkt haalt vanzelf N4 (melden welk regelboek je las), N11
        (nooit blijven hangen op actief) en N10 (een nood zonder teller):

            with ag.ronde("agenda in het oog") as r:
                regels = r.werkwijze          # de tekst zoals ze nu op het bord staat
                r.bron("agenda-taken.json", open(pad).read())
                ...
                r.nood("Buitenafspraken zonder adres", wie="mehdi")
                r.detail = f"{n} afspraken bekeken"

        bronnen: extra regelboeken als {naam: inhoud}, bovenop de werkwijze.

        begin_noden: noden die de agent al heeft voor de ronde begint, elk {"tekst": ..., "wie": ...}, zoals
        De Bode met het bellen en het alarm, die voor de ronde lopen (X4, ontwerp regie-zoom v1.2). Ze staan
        in de ronde alsof ze met r.nood() gemeld zijn, en gaan ook mee als de ronde stopt.

        werkwijze: de werkwijze die de agent net met ag.werkwijze() las, zodat de ronde ze niet nog eens leest (Codex
        NA77: een tweede lezing kon met een tijdelijke fout een geldige ronde stoppen). Leeg stopt de ronde ook dan.

        Is de werkwijze op het bord onbekend of leeg, dan stopt de ronde voor het werk begint:
        een nood, hartslag "fout" en RondeGestopt (NA09). Zonder regelboek werkt geen agent.
        """
        return Ronde(self, taak, bronnen or {}, begin_noden or (), werkwijze)


class Ronde:
    """Eén ronde van een agent, van hartslag tot hartslag."""

    def __init__(self, agent, taak, bronnen, begin_noden=(), werkwijze=None):
        self.agent = agent
        self.taak = taak
        self.detail = ""
        self.werkwijze = ""
        self._gelezen = werkwijze      # al gelezen met ag.werkwijze(), of None: dan leest de ronde zelf
        self._bronnen = {}
        self._noden = []
        # Weet de agent niet welke van zijn noden nog gelden (de open lijst van het bord was onleesbaar en hij kon ze niet
        # allemaal nakijken), dan zet hij dit: de ronde stuurt dan alleen haar nieuwe noden en het bord sluit niets
        # (Codex-controle mailnood 4 en 5 van De Dagbundelaar, 27-10-2026).
        self.noden_onbekend = False
        for naam, inhoud in dict(bronnen).items():
            self.bron(naam, inhoud)
        for n in begin_noden:
            # door r.nood(), zodat ook hier geen teller in de tekst staat en een dubbel er maar een keer in komt (N10)
            self.nood(n["tekst"], n.get("wie") or "mehdi")

    def bron(self, naam, inhoud):
        """Een regelboek dat ik deze ronde gelezen heb. Gaat mee als kennis."""
        if not isinstance(inhoud, str):
            try:
                inhoud = json.dumps(inhoud, ensure_ascii=False, default=str)
            except (TypeError, ValueError):   # Codex NA48: bijvoorbeeld een tuple als sleutel
                inhoud = repr(inhoud)
        self._bronnen[str(naam)] = inhoud

    def nood(self, tekst, wie="mehdi"):
        """Wat ik nodig heb of wat bij mij niet werkt.

        Norm N10: geen aantal vooraan in de tekst. Noden zijn declaratief, dus met
        een teller erin ("11 afspraken zonder code") is elke ronde formeel een
        nieuwe nood en sluit de lus nooit. Het aantal hoort in het detail.
        """
        schoon = tekst.strip()
        if re.match(r"^\d+\s", schoon):
            schoon = re.sub(r"^\d+\s+", "", schoon)
            schoon = schoon[:1].upper() + schoon[1:]
            diagnose(f"  [norm N10] aantal uit de noodtekst gehaald: {tekst[:50]}")
        if not any(n["tekst"] == schoon for n in self._noden):
            self._noden.append({"tekst": schoon, "wie": wie})

    def _kennis(self):
        """Wat ik las, met een vingerafdruk per bron, zodat achteraf te zien is
        welke versie van de regels gold toen ik iets deed."""
        return "\n".join(
            f"{naam}: {len(inhoud or '')} tekens, {hashlib.sha256((inhoud or '').encode()).hexdigest()[:8]}"
            for naam, inhoud in self._bronnen.items())

    def __enter__(self):
        try:
            # ook de eerste hartslag valt onder de bescherming (Codex NA62): een signaal terwijl het bord "actief" al
            # aannam, liet de agent anders op actief staan
            self.agent.hartslag("actief", taak=self.taak)
            self._begin()
        except RondeGestopt:
            raise
        except BaseException as e:
            if getattr(e, "al_gemeld", False):
                raise
            # Codex NA15: een fout in de startfase liet de agent op "actief" staan, want __exit__ draait dan
            # niet. Ook hier geldt N11: nooit blijven hangen op actief. BaseException: ook SIGTERM (als
            # SystemExit, keten.py en de timeout van De Regisseur) en Ctrl-C (ontwerp regie-zoom v1.2, J1). Een tweede
            # signaal tijdens het melden houdt de fouthartslag niet meer tegen; de oorspronkelijke oorzaak gaat door
            # (overleg 13, X2).
            self.agent.fout_melden(self.taak, f"{type(e).__name__}: {str(e)[:180]}", self._noden,
                                   ook=[n["tekst"] for n in self._noden])
            raise
        return self

    def _begin(self):
        # NA09 (Codex, 16-10-2026): tot dan gaf een leesfout een lege werkwijze en werkte de agent gewoon
        # door zonder regelboek, zonder dat iemand het zag. Onbekend is niet leeg, en leeg is geen regelboek:
        # werkwijze() stopt de ronde dan zelf, voor het werk begint; de begin_noden gaan dan mee (X4).
        if self._gelezen is None:
            self.werkwijze = self.agent.werkwijze(taak=self.taak, noden=self._noden)
        elif not self._gelezen.strip():
            self.agent.zonder_regelboek("Werkwijze leeg op het bord", "mehdi", self.taak, noden=self._noden)
        else:
            self.werkwijze = self._gelezen
        self._bronnen.setdefault("werkwijze op het bord", self.werkwijze)
        # Norm N13: wat een agent leert, leest elke agent. De gedeelde lessen gaan elke
        # ronde mee als bron, zodat ze in de kennis staan en een taalmodel ze in zijn
        # opdracht krijgt. Ontbreekt het bestand of klopt de vorm niet, dan breekt de ronde
        # niet: dat meldt de Normwacht (N13). Mandaat van Mehdi, 24-09-2026.
        self.lessen = []
        try:
            pad = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "werkwijze", "lessen.json")
            with open(pad, encoding="utf-8") as f:
                tekst = f.read()
            inhoud = json.loads(tekst)
            lessen = inhoud.get("lessen") if isinstance(inhoud, dict) else None
            if isinstance(lessen, list):
                self.lessen = lessen
                self._bronnen.setdefault("gedeelde lessen", tekst)
        except (OSError, ValueError):
            pass
        # Norm N14: een agent kent zijn collega's. Mehdi, 25-09-2026: "zorg ervoor dat alle
        # agents van elkaar op de hoogte zijn". De lijst komt elke ronde levend van het bord
        # (de waarheid, N6), nooit uit een kopie: wie er morgen bijkomt, kent iedereen meteen.
        self.collegas = collegas(zonder=self.agent.naam)
        if self.collegas:
            self._bronnen.setdefault("collega's op het bord", collega_tekst(self.collegas))

    def __exit__(self, soort, fout, spoor):
        onderbrekingen = []
        for wat, stap in (("kennis", lambda: self.agent.kennis(self._kennis(), bron=", ".join(self._bronnen) or "geen")),
                          ("werkverslag", self.agent.log_verstuur)):
            try:
                stap()
            except Exception as e:  # noqa: BLE001  Codex NA45: de laatste hartslag gaat altijd uit (N11)
                diagnose(f"{wat} niet verstuurd: {type(e).__name__}: {e}")
            except BaseException as e:
                # Codex NA49, NA53 en NA57 (01-11-2026): een SIGTERM (als SystemExit) of Ctrl-C tijdens het afsluiten
                # sloeg de eindhartslag over, en dan bleef de agent op actief staan. Nu gaat ook de andere stap nog, en
                # de fouthartslag noemt de fout van het werk en elk signaal; daarna gaat het eerste signaal door.
                onderbrekingen.append(e)
        if fout is not None or onderbrekingen:
            # N11: nooit blijven hangen op "actief". Een ronde die breekt meldt dat, en sluit geen noden
            # die ze niet meer kon nakijken. Kwam al een signaal, dan haalt ze de noodlijst niet meer op (NA61).
            onderbrekingen += self.agent.fout_melden(
                self.taak, "; daarna ".join(f"{type(x).__name__}: {str(x)[:180]}"
                                            for x in [fout] + onderbrekingen if x is not None),
                self._noden, ook=[n["tekst"] for n in self._noden], verslag=False, nood_ophalen=not onderbrekingen)
            # het eerste signaal gaat door: dat van het werk zelf (return False), anders het eerste bij het afsluiten
            if onderbrekingen and (fout is None or isinstance(fout, Exception)):
                raise onderbrekingen[0]
            return False
        self.agent.hartslag("klaar" if not self._noden else "waakt",
                            taak=self.taak, detail=self.detail, nood=self._noden, sluiten=not self.noden_onbekend)
        return False


def collegas(zonder=None):
    """De actieve agents zoals ze nu op het bord staan: naam, label, afdeling, rol, cadans.
    Leeg als het bord niet antwoordt; de ronde breekt daar niet op, de Normwacht meldt het (N14)."""
    try:
        rijen = call("/api/agents")
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(rijen, list):
        return []
    rijen = [r for r in rijen if isinstance(r, dict) and r.get("naam")]
    return sorted(({"naam": r["naam"], "label": r.get("label") or r["naam"], "afdeling": r.get("type") or "",
                    "rol": r.get("rol") or "", "cadans": r.get("cadans") or ""}
                   for r in rijen if r.get("actief") and r.get("naam") != zonder),
                  key=lambda c: (c["afdeling"], c["naam"]))


def collega_tekst(lijst):
    """Een regel per collega, voor de kennis van de ronde en voor de opdracht van een taalmodel-agent:
    wie bestaat er, waarvoor, en bij wie hoort een vraag die niet de mijne is."""
    regels = ["Mijn collega's op het bord. Hoort iets bij een van hen, dan zet ik het voor die agent klaar "
              "(klaarzet, voor: <naam>) in plaats van het zelf te doen. Mehdi bereik ik via De Bode (signaal)."]
    for c in lijst:
        regels.append(f"- {c['label']} ({c['naam']}, {c['afdeling']}): {c['rol'][:160]}")
    return "\n".join(regels)


def klaargezet_voor(voor, sleutel=None, afdeling=None, status="klaar", n=100):
    q = {"status": status, "n": n}
    if voor:
        q["voor"] = voor
    if sleutel:
        q["sleutel"] = sleutel
    if afdeling:
        q["afdeling"] = afdeling
    return call("/api/klaarzet?" + urllib.parse.urlencode(q)).get("items", [])


def opgepakt(kid, door):
    return call(f"/api/klaarzet/{kid}/opgepakt", {"door": door})


# --- G1 (ontwerp regie-zoom v1.2): één alleen-lezende leesweg naar de databank van het bord, voor De Regisseur,
#     De Bode en De Zoomwacht. Schrijven gaat altijd via de API; teruglezen langs een andere weg dan het schrijven
#     is het sterkere bewijs (L32). Zelfde variabele en standaard als regisseur.py.
BORD_DB = os.environ.get("BORD_DB", os.path.expanduser("~/appportal/mijnagents-data/mijnagents.db"))
_ALLEEN_LEZEN = re.compile(r"^\s*(select|with)\b", re.I)


class BordOnbekend(RuntimeError):
    """De databank van het bord gaf geen antwoord. Onbekend is niet leeg (L29): wie dit krijgt, zegt "onbekend",
    nooit "niets gevonden". `reden` is kort en zonder getal dat elke ronde verandert."""

    def __init__(self, reden):
        self.reden = reden
        super().__init__(reden)


def db_lees(sql, args=()):
    """Een vraag aan de databank van het bord, alleen lezend: de URI met mode=ro, timeout 10 en PRAGMA query_only,
    zodat ook een vergissing niets kan schrijven (G2). Alleen tekst die met SELECT of WITH begint. Geeft een lijst
    van dicts. Een weigering, een ontbrekend bestand of een sqlite-fout geeft BordOnbekend, nooit een lege lijst."""
    if not isinstance(sql, str) or not _ALLEEN_LEZEN.match(sql):
        raise BordOnbekend("geweigerd: db_lees leest alleen (SELECT of WITH)")
    if not os.path.isfile(BORD_DB):
        raise BordOnbekend("databank van het bord ontbreekt")
    con = None
    try:
        con = sqlite3.connect(f"file:{urllib.parse.quote(BORD_DB)}?mode=ro", uri=True, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only = 1")
        return [dict(r) for r in con.execute(sql, args).fetchall()]
    except sqlite3.Error as e:
        raise BordOnbekend(f"databank van het bord niet leesbaar ({type(e).__name__}: {str(e)[:120]})") from e
    finally:
        if con is not None:
            con.close()

"""FelixArchief (stadsarchief Antwerpen): bouwdossiers zoeken, met bewijs.

Zoeken kan zonder aanmelden, via dezelfde zoekdienst als de website (/api/search/...).
Akamai weigert elke aanvraag die niet uit een echte browser komt (403, ook vanaf de VM),
daarom loopt alles door een headless Chrome met een gewone user-agent (getest 02-10-2026).

De nummerlogica staat los van de browser (nummers, raakt), zodat ze getest kan worden zonder net.
"""
import json
import os
import re
import time
import urllib.parse

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
BASIS = "https://felixarchief.antwerpen.be"
PAGINA = 100
PAGINA_DOSSIER = 50  # een brede vraag op het veld Dossiernummer gaf met 100 per pagina al een 500 (17-10-2026)
MAX_PAGINAS = 10  # 500 per pagina gaf een 500-fout (03-10-2026), 100 loopt
WERKGEBIED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "felix", "werkgebied.json")


def _env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_env("~/appportal/.env")  # FELIXARCHIEF_EMAIL en FELIXARCHIEF_WACHTWOORD, alleen op de VM


def heeft_aanmelding():
    return bool(os.environ.get("FELIXARCHIEF_EMAIL") and os.environ.get("FELIXARCHIEF_WACHTWOORD"))


# ---------------------------------------------------------------- werkgebied

def werkgebied():
    return json.load(open(WERKGEBIED, encoding="utf-8"))


def districten_voor(postcode):
    """De districtnamen van FelixArchief voor een postcode, of [] als ze buiten het werkgebied valt."""
    p = werkgebied()["postcodes"].get(str(postcode or "").strip())
    return list(p["districten"]) if p else []


# ---------------------------------------------------------------- huisnummers

def nummers(tekst):
    """Een huisnummer zoals FelixArchief het schrijft -> lijst van (van, tot).

    '85' -> [(85, 85)]; '85-87' -> [(85, 87)] (een bereik: alles ertussen hoort erbij);
    '75-77-79' en '293/295' -> elk nummer apart; '12A' -> [(12, 12)]; '' -> [].
    """
    uit = []
    for deel in re.split(r"[,;+&]|\ben\b", (tekst or "").replace(" ", "")):
        getallen = [int(g) for g in re.findall(r"\d+", deel)]
        if not getallen:
            continue
        if re.fullmatch(r"\d+[A-Za-z]?-\d+[A-Za-z]?", deel) and len(getallen) == 2:
            uit.append((min(getallen), max(getallen)))
        else:
            uit.extend((g, g) for g in getallen)
    return uit


def _getal(huisnummer):
    m = re.match(r"\d+", str(huisnummer or ""))
    return int(m.group()) if m else None


def raakt(record_nummer, doelen):
    """Hoe een dossiernummer een van de huisnummers van het pand raakt: 'exact', 'bereik' of None."""
    doel_getallen = {_getal(d) for d in doelen if _getal(d) is not None}
    tekst = (record_nummer or "").replace(" ", "").upper()
    if tekst and tekst in {str(d).replace(" ", "").upper() for d in doelen}:
        return "exact"
    for van, tot in nummers(record_nummer):
        for d in doel_getallen:
            if van == tot == d:
                return "exact"
            if van <= d <= tot and van != tot:
                return "bereik"
    return None


def is_buur(record_nummer, doelen, afstand=6):
    """Zelfde kant van de straat (zelfde pariteit) en hoogstens `afstand` ervan: de buren om te tonen."""
    for van, tot in nummers(record_nummer):
        for d in {_getal(x) for x in doelen if _getal(x) is not None}:
            for n in (van, tot):
                if n % 2 == d % 2 and abs(n - d) <= afstand:
                    return True
    return False


# ---------------------------------------------------------------- de browser

class Felix:
    """Een headless Chrome op FelixArchief. Gebruik als context: `with Felix() as f: ...`."""

    def __init__(self, headless=True):
        self.headless = headless
        self.afgekapt = []  # zoekopdrachten die meer treffers hadden dan we lazen: maakt een zoektocht onvolledig

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(channel="chrome", headless=self.headless,
                                                 args=["--disable-blink-features=AutomationControlled"])
        self._ctx = self._browser.new_context(user_agent=UA, locale="nl-BE",
                                              viewport={"width": 1400, "height": 1000})
        self.page = self._ctx.new_page()
        r = self.page.goto(BASIS + "/", wait_until="domcontentloaded", timeout=60000)
        if not r or r.status != 200:
            raise RuntimeError(f"FelixArchief niet bereikbaar (status {r.status if r else 'geen'})")
        self._weiger_cookies()
        return self

    def __exit__(self, *exc):
        try:
            self._browser.close()
        finally:
            self._pw.stop()

    def _weiger_cookies(self, wacht=5000):
        try:
            self.page.get_by_text("Weiger alles", exact=True).click(timeout=wacht)
        except Exception:
            pass  # geen banner: niets te doen

    def api(self, pad, body=None):
        js = """async ([pad, body]) => {
            const opt = body === null ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)};
            const r = await fetch('/api/' + pad, opt);
            return [r.status, await r.text()];
        }"""
        for poging in range(3):  # de zoekdienst geeft soms een 500 onder last; even wachten helpt
            status, tekst = self.page.evaluate(js, [pad, body])
            if status < 400:
                return json.loads(tekst)
            if status < 500:
                break
            time.sleep(5 * (poging + 1))
        raise RuntimeError(f"FelixArchief /api/{pad} gaf {status}")

    # -- zoeken

    def reeks_zoeken(self, reeks, termen, pagina=1, grootte=100):
        return self.api("search/detailaccess", {"DTinventoryNumber": [reeks], "searchTerms": termen,
                                                "inventoryNumber": [], "digitalOnly": False,
                                                "page": pagina, "pageSize": grootte})

    # Het veld District van FelixArchief is niet betrouwbaar: Frans Brandsstraat 17 in Berendrecht staat er als
    # "Antwerpen" (3562#5566, gemeten 03-10-2026) en viel zo uit een districtfilter. Straatnamen zijn sinds de
    # fusie uniek binnen de stad, dus zoeken we op de straat in de hele stad en tonen we het district alleen.

    def straat_tellen(self, reeks, straat, districten=None):
        """Bestaat de straat in FelixArchief? Geeft het totaal en de districten zoals het archief ze noteert."""
        j = self.reeks_zoeken(reeks, [_term("Huidige_Straatnaam", straat, "contains")], 1, PAGINA)
        rijen = [r for r in (_rij(it, reeks) for it in j.get("items") or []) if _zelfde_straat(r["straat"], straat)]
        per = {}
        for r in rijen:
            per[r["district"]] = per.get(r["district"], 0) + 1
        totaal = j.get("amountOfResults") or 0
        return {"totaal": totaal if rijen else 0, "districten": per}

    def straat_dossiers(self, reeks, straat, districten=None, maximum=5000):
        """Alle dossiers van een straat, in de hele stad, als platte rijen."""
        rijen, pagina = [], 1
        while len(rijen) < maximum:
            j = self.reeks_zoeken(reeks, [_term("Huidige_Straatnaam", straat, "contains")], pagina, PAGINA)
            items = j.get("items") or []
            rijen.extend(r for r in (_rij(it, reeks) for it in items) if _zelfde_straat(r["straat"], straat))
            if len(items) < PAGINA:
                break
            pagina += 1
            time.sleep(0.5)
        return _markeer_district(rijen, districten)

    def nummer_dossiers(self, reeks, straat, nummer, districten=None):
        """Straat plus huisnummer met 'bevat', niet 'is gelijk': zo komt '85-87' mee als je 85 zoekt.

        De les van 02-10-2026: een collega zocht August Van de Wielelei met 'is gelijk 85', vond vier
        dossiers uit 1935 en 1946 die alleen in de leeszaal liggen, en noteerde 'geen dossiers'. Het
        dossier van het appartementsgebouw van 1965 heet '85-87' en is digitaal. Wat 'bevat' te veel
        meeneemt (185, 285) filtert raakt() eruit.
        """
        getal = str(_getal(nummer) or nummer)
        rijen = []
        for pagina in range(1, MAX_PAGINAS + 2):  # alle pagina's (FX21); een volle laatste pagina: de volgende beslist (FX24)
            j = self.reeks_zoeken(reeks, [_term("Huidige_Straatnaam", straat, "contains"),
                                          _term("Huidig_Huisnummer", getal, "contains")], pagina, PAGINA)
            items = j.get("items") or []
            if pagina > MAX_PAGINAS:
                if items:
                    self.afgekapt.append(f"{straat} {nummer} ({werkgebied()['reeksen'].get(reeks, reeks)}): meer dan {MAX_PAGINAS * PAGINA} treffers")
                break
            rijen += [r for r in (_rij(it, reeks) for it in items) if _zelfde_straat(r["straat"], straat)]
            if len(items) < PAGINA:
                break
        return _markeer_district(rijen, districten)

    def dossier_zoeken(self, dossiernummer, punt=None):
        """Een dossiernummer van de percelenpas -> de dossiers in FelixArchief (bouwdossier en plannen).

        Drie vormen:
        - '214157_329#11928' draagt het inventarisnummer al;
        - '19654625' staat letterlijk in het veld Dossiernummer ('DE/1965/B/23624 # 19654625');
        - '197317935' staat er niet letterlijk in, wel als 'BE/1973/B/17935' (Grotesteenweg 459, gemeten 17-10-2026:
          het dossier lag onder de hoekstraat, Lysenstraat 2). Dan zoeken we jaar en volgnummer apart, en een kandidaat
          telt pas als zijn adres binnen AFSTAND_MAX meter van het perceel (punt = (lat, lon)) ligt.
        """
        if "#" in dossiernummer:
            info = self.inventaris(dossiernummer.split("_")[-1])
            if not info:
                return []
            reeks = next((k for k, v in werkgebied()["reeksen"].items() if v == info["reeks"]), "")
            return [{"reeks": reeks, "inventaris": info["inventaris"], "straat": info["titel"], "nummer": "",
                     "aanvraag": info["begin"], "omschrijving": "", "status": info["status"], "dossiernummer": ""}]
        rijen = self._dossiernummer_bevat(dossiernummer, lambda dn: re.search(
            rf"(^|\D){re.escape(dossiernummer)}(\D|$)", dn))
        if rijen:
            if punt:  # de stad koppelde dit nummer zelf aan het perceel; ligt het adres in FelixArchief ver weg, dan melden we dat
                for r in rijen:
                    r["afstand_m"] = _afstand_tot(f"{r['straat']} {r['nummer']}".strip(), punt)
                    if r["afstand_m"] is not None and r["afstand_m"] > AFSTAND_MAX:
                        r["let_op"] = f"adres in FelixArchief ({r['straat']} {r['nummer']}) ligt {r['afstand_m']} m van het perceel"
            return rijen
        if not schrijfwijze_mogelijk(dossiernummer):
            return rijen
        jaar, volg = dossiernummer[:4], dossiernummer[4:].lstrip("0")
        past = lambda dn: past_schrijfwijze(dn, jaar, volg)  # noqa: E731
        # De gekende notatie precies ('BE/1973/B/17935', ook met voorloopnullen zoals 'WI/1973/B/0234'): snel en raak,
        # ook als de brede vraag hieronder te breed is. FelixArchief negeert losse schuine strepen, maar zoekt
        # '1973/B/17935' als geheel (gemeten 17-10-2026: 1 treffer per reeks).
        kandidaten = {}
        for notatie in dict.fromkeys([f"{jaar}/B/{volg}", f"{jaar}/B/{volg.zfill(4)}", f"{jaar}/B/{volg.zfill(5)}"]):
            for r in self._dossiernummer_bevat(notatie, past):
                kandidaten.setdefault(r["inventaris"], r)
        for r in self._dossiernummer_bevat(volg, past, extra=jaar):  # elke andere notatie met jaar en volgnummer
            kandidaten.setdefault(r["inventaris"], r)
        uit = []
        for r in kandidaten.values():
            r["via"] = f"andere schrijfwijze: {r['dossiernummer'].split('#')[0].strip()}"
            if punt:
                r["afstand_m"] = _afstand_tot(f"{r['straat']} {r['nummer']}".strip(), punt)
                if r["afstand_m"] is None or r["afstand_m"] > AFSTAND_MAX:
                    continue  # zelfde jaar en volgnummer, maar elders in de stad: niet ons perceel
            uit.append(r)
        return uit

    def _dossiernummer_bevat(self, tekst, past, extra=None, maximum=500):
        """Alle dossiers waarvan het veld Dossiernummer 'tekst' (en 'extra') bevat en 'past', in beide reeksen.

        Eerst het aantal treffers (de eerste pagina geeft amountOfResults). Boven 'maximum' zijn ze niet allemaal te
        lezen: dat melden we meteen als afgekapt (Codex FX03, FX21). Vroeger lazen we eerst tien trage pagina's:
        voor 2017945 (jaar 2017, volgnummer 945) 14 vragen van gemiddeld 50 s en dan een 500 op de diepte (gemeten
        17-10-2026, Frans Brandsstraat 11: 31 minuten voor de dossiernummers).
        """
        rijen, naam = [], f"{extra} + {tekst}" if extra else tekst
        termen = [_term("Dossiernummer", tekst, "contains")] + ([_term("Dossiernummer", extra, "contains")] if extra else [])
        for reeks in werkgebied()["reeksen"]:
            j = self.reeks_zoeken(reeks, termen, 1, PAGINA_DOSSIER)
            totaal = j.get("amountOfResults")
            if isinstance(totaal, int) and totaal > maximum:
                self.afgekapt.append(f"dossiernummer {naam}: {totaal} treffers, meer dan {maximum}")
                continue
            pagina, items = 1, j.get("items") or []
            while True:
                rijen += [r for r in (_rij(it, reeks) for it in items) if past(r["dossiernummer"])]
                if len(items) < PAGINA_DOSSIER or (isinstance(totaal, int) and pagina * PAGINA_DOSSIER >= totaal):
                    break
                if pagina * PAGINA_DOSSIER >= maximum:  # geen aantal gekregen en nog een volle pagina: niet alles gelezen
                    self.afgekapt.append(f"dossiernummer {naam}: meer dan {maximum} treffers")
                    break
                pagina += 1
                items = self.reeks_zoeken(reeks, termen, pagina, PAGINA_DOSSIER).get("items") or []
        return rijen

    def bestanden(self, inventaris):
        """De bestanden van een digitaal dossier: naam, grootte, adres om te downloaden (na aanmelden)."""
        sleutel = inventaris.replace("#", "_")
        j = self.api(f"inventorypieces/{sleutel}/folders?type=master")
        uit = []

        def loop(map_, pad=""):
            for f in map_.get("files") or []:
                uit.append({"naam": f["filename"], "map": pad, "grootte": f.get("size"), "url": "/api" + f["url"],
                            "verwijzing": (f.get("referenceNumber") or "").strip()})
            for sub in map_.get("folders") or []:
                loop(sub, (pad + "/" if pad else "") + sub.get("foldername", ""))
        loop(j.get("folder") or {})
        return uit

    def omschrijving_zoeken(self, reeks, woord, districten):
        """Dossiers zonder bruikbaar huisnummer die het woord in de adresomschrijving dragen (hoek van ...)."""
        rijen = []
        for d in districten:
            j = self.reeks_zoeken(reeks, [_term("AdresOmschrijving", woord, "contains"),
                                          _term("District", d, "match")], 1, PAGINA)
            rijen.extend(_rij(it, reeks) for it in j.get("items") or [])
        return rijen

    def inventaris(self, nummer):
        """Inventarisnummer -> titel (meestal het adres) en status. Voor mails 'download staat klaar'."""
        j = self.api("search/advanced", {"page": 1, "pageSize": 5, "hasTerms": [], "exactTerms": [nummer],
                                         "filters": [], "includeFilters": False})
        for x in j.get("searchResult") or []:
            if x.get("inventoryNumber") == nummer:
                a = x.get("actionInfo") or {}
                return {"inventaris": nummer, "titel": x.get("title"), "reeks": x.get("detailAccessName"),
                        "begin": (x.get("startDate") or "")[:10], "status": _status(a, x.get("digital"))}
        return None

    # -- bewijs

    def schermafdruk_zoeken(self, termen, pad):
        """Printscreen van de gewone zoekpagina van FelixArchief, zoals een mens ze zou maken."""
        q = "&".join("bevat=" + urllib.parse.quote(t) for t in termen)
        self.page.goto(f"{BASIS}/zoekresultaten?{q}&page=1&pageSize=50", wait_until="domcontentloaded", timeout=90000)
        self._weiger_cookies()
        try:
            self.page.wait_for_selector("text=resultaten gevonden", timeout=30000)
        except Exception:
            pass  # ook "0 resultaten" of een lege pagina is bewijs
        self.page.screenshot(path=pad, full_page=False)
        return pad

    # -- aanmelden en downloaden (Mehdi, 03-10-2026: "als ik elke keer voor elk dossier moet komen inloggen,
    #    dan gaat dat niet werken"). E-mail en wachtwoord staan alleen in ~/appportal/.env op de VM.

    def aanmelden(self, email=None, wachtwoord=None, pogingen=3):
        """Aanmelden met tot drie pogingen: de aanmeldknop verschijnt niet altijd op tijd (03-10-2026)."""
        fout = None
        for _ in range(pogingen):
            try:
                return self._aanmelden_een_keer(email, wachtwoord)
            except RuntimeError as e:
                fout = e
                self.page.wait_for_timeout(5000)
        raise fout

    def _aanmelden_een_keer(self, email=None, wachtwoord=None):
        """Meldt aan met A-profiel (e-mail en wachtwoord; FelixArchief vraagt het lage zekerheidsniveau).

        Elke stap heeft een naam; loopt er een vast, dan zegt de fout welke, met een printscreen erbij.
        Vraagt de pagina een tweede factor of iets onbekends, dan stoppen we in plaats van te gokken.
        """
        email = email or os.environ.get("FELIXARCHIEF_EMAIL")
        wachtwoord = wachtwoord or os.environ.get("FELIXARCHIEF_WACHTWOORD")
        if not email or not wachtwoord:
            raise RuntimeError("FELIXARCHIEF_EMAIL en FELIXARCHIEF_WACHTWOORD ontbreken in de omgeving")
        p = self.page
        stap = "startpagina"
        try:
            p.goto(BASIS + "/", wait_until="domcontentloaded", timeout=60000)
            self._weiger_cookies()
            stap = "aanmeldknop"
            link = p.locator("a", has_text="Meld aan met je A-profiel").first
            knop = p.locator("text=Aanmelden >> visible=true").first
            # De startpagina bouwt wisselend traag op (soms na 4 s nog geen knop), en na een half gelukte poging is de
            # agent al aangemeld: dan is er geen knop meer en is dat geslaagd (gemeten 17-10-2026, printscreen met naam).
            for _ in range(30):
                g = self._gebruiker()
                if g.get("aangemeld"):
                    return g
                if knop.is_visible():
                    break
                p.wait_for_timeout(1000)
            else:
                raise RuntimeError("geen aanmeldknop en niet aangemeld na 30 seconden")
            for _ in range(4):  # de cookiemelding kan pas na de eerste weigering verschijnen en vangt dan de klik op
                knop.wait_for(state="visible", timeout=30000)  # meteen klikken op het eerste element gaf 'not visible'
                knop.click(timeout=20000, force=True)
                try:
                    link.wait_for(state="attached", timeout=8000)
                    break
                except Exception:
                    self._weiger_cookies(wacht=3000)
            stap = "aanmeldlink A-profiel"
            link.wait_for(state="attached", timeout=20000)
            p.goto(link.get_attribute("href"), wait_until="domcontentloaded", timeout=60000)  # niet klikken: rechtstreeks
            stap = "A-profiel"
            a_profiel(p, email, wachtwoord)
            stap = "terug naar FelixArchief"
            p.wait_for_url(re.compile(r"felixarchief\.antwerpen\.be"), timeout=60000)
            stap = "verwerken van de aanmelding"
            for _ in range(30):  # 'Bezig met aanmelden...' kan even duren
                p.wait_for_timeout(2000)
                if "/callback" in p.url:
                    continue
                g = self._gebruiker()
                if g.get("aangemeld"):
                    return g
            raise RuntimeError("niet aangemeld na 60 seconden")
        except Exception as e:
            pad = os.path.join(os.path.expanduser("~/appportal/mijnagents-data/felix"), "aanmelden-mislukt.png")
            os.makedirs(os.path.dirname(pad), exist_ok=True)
            try:
                p.screenshot(path=pad)
            except Exception:
                pass
            raise RuntimeError(f"Aanmelden vastgelopen bij '{stap}' ({p.url.split('?')[0]}): "
                               f"{str(e).splitlines()[0][:150]}; printscreen {pad}")

    def _gebruiker(self):
        """Wie FelixArchief als aangemeld ziet (de Angular-dienst van de site), of {} als dat (nog) niet te lezen is."""
        try:
            return self.page.evaluate("""() => { try { const u = angular.element(document.body).injector()
                                .get('AuthenticationService').getUser() || {};
                                return {aangemeld: !!u.loggedIn, naam: (u.firstname||'') + ' ' + (u.lastname||''),
                                        erewoord: !!u.honorStatement}; } catch (e) { return {}; } }""") or {}
        except Exception:
            return {}

    def status_bestand(self, url):
        """Status en soort van een bestand, zonder het te lezen (de server negeert Range; we breken af)."""
        return self.page.evaluate("""async (u) => { const r = await fetch(u, {headers: {Range: 'bytes=0-0'}});
            const uit = [r.status, r.headers.get('content-type') || '']; try { await r.body.cancel(); } catch (e) {}
            return uit; }""", url)

    def rechten(self, url):
        """Het auteursrecht van het dossier achter een bestands-URL, volgens FelixArchief (copyRightFree).

        Alleen dit veld bewijst auteursrecht; een status 500 alleen bewijst niets (Codex FX15, 17-10-2026). Gemeten:
        627#31611 (vrij vanaf 2091), 961#3952 (2093) en 3290#1260 (2134) geven 500; 627#23624 (vrij) geeft 200.
        """
        m = re.search(r"/files/([^?/]+)", url or "")
        if not m:
            return None
        try:
            v = ((self.api(f"inventorypieces/{m.group(1)}?include=inventorynumber").get("inventorynumber") or {})
                 .get("fields") or {})
        except Exception:
            return None
        if "copyRightFree" not in v:
            return None
        return {"vrij": bool(v.get("copyRightFree")), "vrij_vanaf": v.get("copyRightFreeFrom") or ""}

    def download(self, url, pad, grootte=None):
        """Een bestand rechtstreeks naar schijf, met de aanmelding van deze browser; geeft het aantal bytes.

        Een PDF van 14 MB via het geheugen (base64) deed Chrome crashen (13-10-2026). Nu: een eigen tabblad, waar Chrome
        de PDF als download bewaart (getest 17-10-2026: 14 MB in 10 seconden). Een stuk met auteursrecht geeft 403 of
        500: dat mag alleen online bekeken worden en wordt Beschermd, geen fout.
        """
        status, soort = self.status_bestand(url)
        if status in (401, 403, 500):
            vrij = self.rechten(url)
            if vrij is not None and not vrij["vrij"]:  # FelixArchief zegt zelf: auteursrecht (gemeten 17-10-2026)
                raise Beschermd(f"auteursrecht tot {vrij['vrij_vanaf'][:4]}")
        if status >= 400:
            raise BestandFout(status)
        os.makedirs(os.path.dirname(pad), exist_ok=True)
        if "pdf" in soort or "zip" in soort or "octet-stream" in soort or not grootte or grootte > 8_000_000:
            p = self._ctx.new_page()
            try:
                with p.expect_download(timeout=300000) as d:
                    try:
                        p.goto(BASIS + url, timeout=300000)
                    except Exception:
                        pass  # 'Download is starting' is precies wat we willen
                d.value.save_as(pad)
            finally:
                p.close()
            return _volledig_op_schijf(pad, grootte)
        import base64  # een klein beeldbestand: Chrome toont het in plaats van het te downloaden
        b64 = self.page.evaluate("""async (url) => { const r = await fetch(url); if (!r.ok) throw new Error('status ' + r.status);
            const buf = new Uint8Array(await r.arrayBuffer()); let s = '';
            for (let i = 0; i < buf.length; i += 32768) s += String.fromCharCode.apply(null, buf.subarray(i, i + 32768));
            return btoa(s); }""", url)
        with open(pad, "wb") as f:
            f.write(base64.b64decode(b64))
        return _volledig_op_schijf(pad, grootte)

    def schermafdruk_dossier(self, inventaris, reeks, pad):
        """Printscreen van de detailpagina van een gevonden dossier: het bewijs van wat raak was."""
        inv = inventaris.replace("#", "_")
        dt = reeks.replace("#", "_")
        # niet wachten op een stil netwerk: deze pagina blijft nalladen (vastgelopen op 03-10-2026)
        self.page.goto(f"{BASIS}/detailpagina?invnr={inv}&dtnr={dt}", wait_until="domcontentloaded", timeout=90000)
        try:
            self.page.wait_for_selector("text=InventarisNr.", timeout=30000)
            self.page.wait_for_timeout(2500)  # de miniaturen laden na
        except Exception:
            pass
        self.page.screenshot(path=pad, full_page=True)
        return pad

    def schermafdruk_geopunt(self, adres_geopunt, pad, pogingen=2):
        """Echte printscreen van geopunt.be, zoals een mens hem maakt (Mehdi, 03-10-2026: geen zelfgemaakte beelden).

        Geopunt bewaart de locatie niet in de URL: zoeken, het adres kiezen, de kadastrale informatie openen.
        De klik op de suggestie liep in 2 van 3 zoektochten in een timeout (13-10-2026): nu wachten we op de lijst,
        kiezen we met het toetsenbord als klikken niet lukt, en controleren we dat het adrespaneel openging.
        """
        fout = None
        for _ in range(pogingen):
            p = self._ctx.new_page()
            try:
                p.goto("https://www.geopunt.be/kaart", wait_until="domcontentloaded", timeout=90000)
                try:
                    p.get_by_text("Enkel noodzakelijke cookies aanvaarden").click(timeout=8000)
                except Exception:
                    pass
                veld = p.get_by_placeholder("Zoek op de kaart")
                veld.wait_for(timeout=45000)
                veld.click(timeout=20000)
                veld.fill(adres_geopunt)
                suggestie = p.get_by_text(adres_geopunt, exact=True).first
                try:
                    suggestie.wait_for(timeout=30000)
                    suggestie.click(timeout=15000)
                except Exception:
                    veld.press("ArrowDown")
                    veld.press("Enter")
                p.get_by_text("Kadastrale informatie").first.wait_for(timeout=30000)  # het adrespaneel staat open
                # en het toont het gevraagde adres. Het eerste element met die tekst is een verborgen lijstitem van de
                # suggesties; alleen het zichtbare telt (17-10-2026: zo faalde Geopunt.png bij elk adres).
                p.locator(f'text="{adres_geopunt}" >> visible=true').first.wait_for(timeout=15000)
                try:
                    p.get_by_text("Kadastrale informatie").first.click(timeout=10000)
                except Exception:
                    pass
                p.wait_for_timeout(5000)  # de kaarttegels laden na
                p.screenshot(path=pad, full_page=False, timeout=60000)
                return pad
            except Exception as e:
                fout = e
            finally:
                p.close()
        raise fout

    def overzicht_kaarten(self, inventarissen, pad):
        """Een beeld met de kaart van elk gevonden dossier uit de zoekresultaten van FelixArchief, onder elkaar.

        Echte printscreens van de site (adres, inventarisnummer, datering, reeks, knop), samengezet tot een beeld:
        het overzicht op een pagina dat Mehdi wil, zoals zijn collega het maakte (03-10-2026). Elke kaart krijgt een
        herkansing; een kaart die toch faalt, ontbreekt en wordt teruggegeven (Codex FX07, 17-10-2026).
        Geeft (pad of None, lijst van ontbrekende inventarisnummers).
        """
        import io
        from PIL import Image
        stukken, ontbreekt = [], []
        for inv in inventarissen:
            for poging in range(2):
                try:
                    self.page.goto(f"{BASIS}/zoekresultaten?bevat={urllib.parse.quote(inv)}&page=1&pageSize=5",
                                   wait_until="domcontentloaded", timeout=90000)
                    kaart = self.page.locator(".searchresult-item", has_text=f"InventarisNr. {inv}").first
                    kaart.wait_for(timeout=45000)
                    self.page.wait_for_timeout(800)
                    stukken.append(Image.open(io.BytesIO(kaart.screenshot(timeout=60000))))
                    break
                except Exception:
                    try:  # een gecrashte pagina laat anders alle volgende kaarten mislukken (Codex FX07)
                        self.page.close()
                    except Exception:
                        pass
                    self.page = self._ctx.new_page()
                    if poging == 1:
                        ontbreekt.append(inv)
        if not stukken:
            return None, ontbreekt
        breedte = max(s.width for s in stukken)
        beeld = Image.new("RGB", (breedte, sum(s.height for s in stukken) + 12 * (len(stukken) - 1)), "white")
        y = 0
        for s in stukken:
            beeld.paste(s, (0, y))
            y += s.height + 12
        beeld.save(pad)
        return pad, ontbreekt

    def schermafdruk_html(self, html, pad):
        """Een eigen overzicht (tabel, kaart) renderen en vastleggen."""
        p = self._ctx.new_page()
        try:
            p.set_content(html, wait_until="networkidle", timeout=90000)
            p.screenshot(path=pad, full_page=True)
        finally:
            p.close()
        return pad


def a_profiel(p, email=None, wachtwoord=None):
    """Vult de aanmeldpagina van A-profiel in (authentication.antwerpen.be), voor FelixArchief en de percelenpas.

    Het e-mailadres en wachtwoord komen uit de omgeving van de server; ze verschijnen nergens in tekst.
    """
    email = email or os.environ.get("FELIXARCHIEF_EMAIL")
    wachtwoord = wachtwoord or os.environ.get("FELIXARCHIEF_WACHTWOORD")
    p.wait_for_url(re.compile(r"authentication\.antwerpen\.be"), timeout=60000)
    p.locator("text=Met je e-mailadres of gebruikersnaam").first.click(timeout=20000, force=True)
    veld = p.locator("input[type=email], input[name=username], input[autocomplete=username], input[type=text]").first
    veld.wait_for(timeout=20000)
    veld.fill(email)
    ww = p.locator("input[type=password]")
    if not ww.is_visible():
        p.keyboard.press("Enter")  # e-mail en wachtwoord in twee stappen
        ww.wait_for(timeout=20000)
    ww.fill(wachtwoord)
    p.keyboard.press("Enter")


AFSTAND_MAX = 100  # meter: een dossier met een andere schrijfwijze telt pas als zijn adres zo dicht bij het perceel ligt


class Beschermd(Exception):
    """Een stuk met auteursrecht: FelixArchief laat het alleen online bekijken, na aanmelden. Geen fout van ons."""


class BestandFout(Exception):
    """Een bestand dat FelixArchief niet gaf, om een andere reden dan auteursrecht."""


def _volledig_op_schijf(pad, grootte):
    """Het aantal bytes op schijf, of BestandFout als het niet de grootte is die FelixArchief opgeeft.

    Die opgave is exact: 8 van 8 bestanden waren op de byte gelijk (gemeten 17-10-2026). Een afgebroken download
    is dus geen geslaagde download (Codex FX33).
    """
    n = os.path.getsize(pad)
    if grootte is not None and n != int(grootte):  # ook een opgave van 0 telt (Codex FX35)
        raise BestandFout(f"onvolledig ({n} van {grootte} bytes)")
    return n


def schrijfwijze_mogelijk(dossiernummer):
    """'197317935' -> jaar 1973 en volgnummer 17935: kan in FelixArchief als 'BE/1973/B/17935' staan.

    Alleen tot en met 2010: die notatie 'XX/<jaar>/B/<volgnummer>' bestaat van 1965 tot 2006 duizenden keren per jaar,
    in 2010 nog enkele keren en vanaf 2013 niet meer (gemeten 17-10-2026, beide reeksen). Recente dossiers dragen het
    nummer van de stad letterlijk (20135065 -> 3562#5065), en dat vindt de letterlijke zoekvraag al. Zoeken naar een
    notatie die niet bestaat, kostte voor 2017945 en 20172314 samen meer dan tien minuten en een fout 500.
    """
    return bool(re.fullmatch(r"(19\d\d|200\d|2010)\d{2,6}", dossiernummer or ""))


def past_schrijfwijze(dossiernummer_felix, jaar, volg):
    """Draagt het veld Dossiernummer van FelixArchief dit jaar en dit volgnummer, als eigen stukken ('/1973/B/17935')?"""
    dn = dossiernummer_felix or ""
    return bool(re.search(rf"(^|\D){jaar}(\D|$)", dn) and re.search(rf"(^|\D)0*{re.escape(volg)}(\D|$)", dn))


def _afstand_tot(adres, punt):
    """Afstand in meter tussen een adres (via Geopunt) en een punt (lat, lon); None als Geopunt het niet vindt."""
    import math
    import adresregister
    try:
        loc = adresregister.lokaliseer(adres + ", Antwerpen")
    except Exception:
        return None
    if not loc:
        return None
    gezocht = re.match(r"(.*?)\s+(\d+\w*)", adres.strip())
    if gezocht and (not _zelfde_straat(loc.get("straat") or "", gezocht.group(1))
                    or _getal(loc.get("huisnummer")) != _getal(gezocht.group(2))):
        return None  # Geopunt gaf een ander adres dan gevraagd (Codex FX16): geen afstand, dus geen bewijs
    dy = (loc["lat"] - punt[0]) * 111_320
    dx = (loc["lon"] - punt[1]) * 111_320 * math.cos(math.radians(punt[0]))
    return round(math.hypot(dx, dy))


def _in(district, districten):
    return (district or "").strip().lower() in {d.lower() for d in districten}


def _norm_straat(s):
    import unicodedata
    s = "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()
    s = re.sub(r"\s+(zn|z\.n\.|zonder nummer)$", "", s.strip())  # 'Frans Brandsstraat ZN' is dezelfde straat
    return re.sub(r"\s+", " ", s)


def _zelfde_straat(gevonden, gezocht):
    return _norm_straat(gevonden) == _norm_straat(gezocht)


def _markeer_district(rijen, districten):
    """Een district buiten de verwachting sluit niets uit; het wordt een opmerking bij de rij."""
    if districten:
        for r in rijen:
            if not _in(r["district"], districten):
                r["district_afwijkend"] = True
    return rijen


def _term(veld, waarde, soort):
    return {"searchField": veld, "searchTerm": waarde, "searchType": soort}


def _status(actie, digitaal):
    if actie.get("digitalDownload"):
        return "download"
    if digitaal:
        return "na aanmelden"
    if actie.get("reserve"):
        return "leeszaal"
    return "onbekend"


def _rij(item, reeks):
    v = {x["fieldName"]: x.get("dataValue") or "" for x in item.get("itemRows") or []}
    return {
        "reeks": reeks,
        "inventaris": item.get("inventoryNumber"),
        "straat": v.get("Huidige_Straatnaam", ""),
        "nummer": (v.get("Huidig_Huisnummer") or "").strip(),
        "straat_dossier": v.get("Straatnaam_Dossier", ""),
        "nummer_dossier": (v.get("Huisnummer_Dossier") or "").strip(),
        "adresomschrijving": v.get("AdresOmschrijving") or v.get("Adres_Omschrijving") or "",
        "district": v.get("District", ""),
        "aanvraag": (v.get("AanvraagDatum") or v.get("Aanvraagdatum") or "")[:10],
        "college": (v.get("CollegeDatum") or "")[:10],
        "omschrijving": v.get("Omschrijving", ""),
        "dossiernummer": v.get("Dossiernummer", ""),
        "status": _status(item.get("actionInfo") or {}, item.get("isDigital")),
    }

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
PAGINA = 100  # 500 per pagina gaf een 500-fout (03-10-2026), 100 loopt
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

    def _weiger_cookies(self):
        try:
            self.page.get_by_text("Weiger alles", exact=True).click(timeout=5000)
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
        j = self.reeks_zoeken(reeks, [_term("Huidige_Straatnaam", straat, "contains"),
                                      _term("Huidig_Huisnummer", getal, "contains")], 1, PAGINA)
        rijen = [r for r in (_rij(it, reeks) for it in j.get("items") or []) if _zelfde_straat(r["straat"], straat)]
        return _markeer_district(rijen, districten)

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

    def aanmelden(self, email=None, wachtwoord=None):
        """Meldt aan met A-profiel (e-mail en wachtwoord; FelixArchief vraagt het lage zekerheidsniveau).

        Vraagt de pagina een tweede factor of een keuze die we niet kennen, dan stoppen we met een duidelijke
        fout in plaats van te gokken. Geeft de gebruiker terug zoals de site hem kent (zonder rijksregister).
        """
        email = email or os.environ.get("FELIXARCHIEF_EMAIL")
        wachtwoord = wachtwoord or os.environ.get("FELIXARCHIEF_WACHTWOORD")
        if not email or not wachtwoord:
            raise RuntimeError("FELIXARCHIEF_EMAIL en FELIXARCHIEF_WACHTWOORD ontbreken in de omgeving")
        p = self.page
        p.goto(BASIS + "/", wait_until="domcontentloaded", timeout=60000)
        self._weiger_cookies()
        p.get_by_text("Aanmelden", exact=True).first.click(timeout=15000)
        p.get_by_text("Meld aan met je A-profiel").click(timeout=15000)
        p.wait_for_url(re.compile(r"authentication\.antwerpen\.be"), timeout=60000)
        p.get_by_text("Met je e-mailadres of gebruikersnaam").click(timeout=15000)
        veld = p.locator("input[type=email], input[name=username], input[autocomplete=username], input[type=text]").first
        veld.wait_for(timeout=20000)
        veld.fill(email)
        ww = p.locator("input[type=password]")
        if not ww.is_visible():
            p.keyboard.press("Enter")  # het formulier vraagt e-mail en wachtwoord in twee stappen
            ww.wait_for(timeout=20000)
        ww.fill(wachtwoord)
        p.keyboard.press("Enter")
        try:
            p.wait_for_url(re.compile(r"felixarchief\.antwerpen\.be"), timeout=60000)
        except Exception:
            tekst = p.locator("body").inner_text()[:300].replace("\n", " ")
            raise RuntimeError(f"Aanmelden niet gelukt, de pagina vraagt nog iets: {tekst}")
        p.wait_for_timeout(3000)
        gebruiker = p.evaluate("""() => { const u = angular.element(document.body).injector()
                                 .get('AuthenticationService').getUser() || {};
                                 return {aangemeld: !!u.loggedIn, naam: (u.firstname||'') + ' ' + (u.lastname||''),
                                         email: u.emailAdress, erewoord: !!u.honorStatement}; }""")
        if not gebruiker.get("aangemeld"):
            raise RuntimeError("Terug op FelixArchief, maar niet aangemeld")
        return gebruiker

    def download(self, url, pad):
        """Een bestand ophalen met de aanmelding van deze browser en bewaren; geeft het aantal bytes."""
        import base64
        b64 = self.page.evaluate("""async (url) => {
            const r = await fetch(url);
            if (!r.ok) throw new Error('status ' + r.status);
            const buf = new Uint8Array(await r.arrayBuffer());
            let s = ''; for (let i = 0; i < buf.length; i += 32768) s += String.fromCharCode.apply(null, buf.subarray(i, i + 32768));
            return btoa(s);
        }""", url)
        data = base64.b64decode(b64)
        os.makedirs(os.path.dirname(pad), exist_ok=True)
        with open(pad, "wb") as f:
            f.write(data)
        return len(data)

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

    def schermafdruk_html(self, html, pad):
        """Een eigen overzicht (tabel, kaart) renderen en vastleggen."""
        p = self._ctx.new_page()
        try:
            p.set_content(html, wait_until="networkidle", timeout=90000)
            p.screenshot(path=pad, full_page=True)
        finally:
            p.close()
        return pad


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

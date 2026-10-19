#!/usr/bin/env python3
"""Volledige back-up van de vijf Pipedrive-administraties.

Per firma haalt dit script elk objecttype op dat de Pipedrive-API geeft en
bewaart het in drie vormen:

  <doel>/<STAMP>/<firma>/data/<soort>.json.gz   volledige API-records
  <doel>/<STAMP>/<firma>/manifest.json         tellingen, controles, gaten
  <doel>/<STAMP>/<firma>/<firma>-pipedrive-<datum>.xlsx   leesbare kopie
  <doel>/bestanden/<firma>/<id>/<naam>         bijlagen (eenmalig, groeit aan)

Het draait op twee plekken (zie README.md):
  - de VM: gegevens zonder bijlagen, elke nacht ook GPG-versleuteld naar de
    S3-bucket van scripts/db-backup.sh (S3_BACKUP_BUCKET, ~/.backup-passphrase,
    upload-only sleutel);
  - de Linux-pc op kantoor: gegevens plus alle bijlagen (85 GB, past niet op
    de VM), zonder off-site.

Niets wordt stil overgeslagen: elk objecttype dat de API niet geeft, elke
bijlage die niet binnenkomt en elk onderdeel dat bewust niet meegaat, staat
met reden in manifest.json en in het logboek.

Het API-budget van Pipedrive is per firma per dag beperkt en wordt gedeeld met
het sales-dashboard, de MCP en de won-deals-poller. De kernlijsten gaan altijd
mee; bijlagen en deelnemers stoppen zodra het restbudget onder RESERVE zakt en
gaan de volgende nacht verder.

Opties: --firma X (herhaalbaar), --zonder-bijlagen, --zonder-offsite,
        --zonder-excel, --doel PAD, --env PAD
"""
import argparse
import datetime as dt
import fcntl
import gzip
import hashlib
import html
import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

FIRMAS = ["harchitects", "unabo", "tknburo", "energieefficient", "harmoniebouw"]
API = "https://api.pipedrive.com"
RESERVE = 0.35          # dit deel van het dagbudget blijft voor de apps
KOSTEN_DOWNLOAD = 20    # tokens per bijlage (gemeten 19-10-2026); de download zelf
                        # geeft geen budgetstand terug, dus we tellen zelf mee
RETENTIE_DAGEN = 30     # elke run blijft 30 dagen, daarna een per maand
RETENTIE_MAANDEN = 12
GEZAKT_DREMPEL = 0.95   # minder dan 95% van gisteren = waarschuwing

# (naam, pad, parameters, paginering, verplicht, limiet)
KERN = [
    ("gebruikers", "/v1/users", {}, None, True, None),
    ("pipelines", "/v1/pipelines", {}, None, True, None),
    ("fasen", "/v1/stages", {}, "start", True, 500),
    ("velden_deal", "/v1/dealFields", {}, "start", True, 500),
    ("velden_persoon", "/v1/personFields", {}, "start", True, 500),
    ("velden_organisatie", "/v1/organizationFields", {}, "start", True, 500),
    ("velden_product", "/v1/productFields", {}, "start", True, 500),
    ("velden_activiteit", "/v1/activityFields", {}, None, False, None),
    ("velden_notitie", "/v1/noteFields", {}, None, False, None),
    ("deals", "/v1/deals", {"status": "all_not_deleted", "sort": "id ASC"}, "start", True, 500),
    ("deals_verwijderd", "/v1/deals", {"status": "deleted", "sort": "id ASC"}, "start", True, 500),
    ("deals_gearchiveerd", "/v1/deals/archived", {"status": "all_not_deleted", "sort": "id ASC"}, "start", False, 500),
    ("leads", "/v1/leads", {"archived_status": "all"}, "start", True, 500),
    ("personen", "/v1/persons", {"sort": "id ASC"}, "start", True, 500),
    ("organisaties", "/v1/organizations", {"sort": "id ASC"}, "start", True, 500),
    ("activiteiten", "/v1/activities", {"user_id": 0}, "start", True, 500),
    ("notities", "/v1/notes", {"sort": "id ASC"}, "start", True, 500),
    ("producten", "/v1/products", {}, "start", True, 500),
    ("bestanden", "/v1/files", {"include_deleted_files": 1, "sort": "id ASC"}, "start", True, 500),
    ("gesprekken", "/v1/callLogs", {}, "start", False, 50),
    ("filters", "/v1/filters", {}, None, False, None),
    ("activiteitstypes", "/v1/activityTypes", {}, None, False, None),
    ("lead_labels", "/v1/leadLabels", {}, None, False, None),
    ("lead_bronnen", "/v1/leadSources", {}, None, False, None),
    ("rollen", "/v1/roles", {}, "start", False, 500),
    ("doelen", "/v1/goals/find", {}, None, False, None),
    ("projecten", "/v1/projects", {}, "cursor", False, 500),
    ("project_borden", "/v1/projects/boards", {}, None, False, None),
    ("taken", "/v1/tasks", {}, "cursor", False, 500),
    ("webhooks", "/v1/webhooks", {}, None, False, None),
    ("mail_inbox", "/v1/mailbox/mailThreads", {"folder": "inbox"}, "start", False, 50),
    ("mail_verzonden", "/v1/mailbox/mailThreads", {"folder": "sent"}, "start", False, 50),
    ("mail_concepten", "/v1/mailbox/mailThreads", {"folder": "drafts"}, "start", False, 50),
    ("mail_archief", "/v1/mailbox/mailThreads", {"folder": "archive"}, "start", False, 50),
]

# Wat bewust niet meegaat staat zichtbaar in elk manifest.
NIET_MEEGENOMEN = {
    "wijzigingsgeschiedenis per record (changelog)": "20 API-tokens per record; de stand van elke nacht blijft wel 30 dagen bewaard",
    "inhoud van e-mails": "de mails zelf staan in de mailboxen; hier de mailthreads met onderwerp, deelnemers en fragment",
    "volgers en notitie-reacties": "elke administratie heeft een gebruiker, dus geen inhoud",
}

GEVOELIGE_SOORTEN_VOOR_DALING = [
    "deals", "leads", "personen", "organisaties", "activiteiten", "notities", "producten", "bestanden",
]


def nu():
    return dt.datetime.now(dt.timezone.utc)


def log(tekst):
    print(f"{nu():%Y-%m-%d %H:%M:%S} {tekst}", flush=True)


def lees_env(pad):
    """KEY=waarde-regels; CRLF en aanhalingstekens weg (nooit `source`)."""
    env = {}
    with open(pad, encoding="utf-8") as f:
        for regel in f:
            regel = regel.strip().replace("\r", "")
            if not regel or regel.startswith("#") or "=" not in regel:
                continue
            k, v = regel.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


class ApiFout(Exception):
    def __init__(self, code, pad, tekst=""):
        super().__init__(f"HTTP {code} op {pad}: {tekst}")
        self.code = code
        self.pad = pad


class BudgetOp(Exception):
    pass


class Pipedrive:
    def __init__(self, firma, token):
        self.firma = firma
        self.token = token
        self.limiet = None
        self.rest = None
        self.rest_begin = None
        self.aanroepen = 0
        self.downloads = 0
        self.slot = threading.Lock()

    def _kop(self, accept="application/json"):
        return {"x-api-token": self.token, "Accept": accept, "User-Agent": "globaal-pipedrive-backup/1.0"}

    def _limieten(self, kop):
        if kop is None:
            return
        try:
            if kop.get("x-daily-ratelimit-token-limit"):
                self.limiet = int(kop["x-daily-ratelimit-token-limit"])
            if kop.get("x-daily-ratelimit-token-remaining"):
                self.rest = int(kop["x-daily-ratelimit-token-remaining"])
                if self.rest_begin is None:
                    self.rest_begin = self.rest
        except ValueError:
            pass
        try:
            over = int(kop.get("x-ratelimit-remaining") or 99)
            reset = float(kop.get("x-ratelimit-reset") or 2)
        except ValueError:
            over, reset = 99, 2
        if over <= 3:
            time.sleep(min(reset, 10) + 0.2)

    def budget_ok(self):
        if self.limiet is None or self.rest is None:
            return True
        return self.rest > self.limiet * RESERVE

    def _open(self, url, accept="application/json"):
        """Een verzoek met herkansing op 429, 5xx en netwerkfouten."""
        pad = urllib.parse.urlsplit(url).path
        for poging in range(10):
            req = urllib.request.Request(url, headers=self._kop(accept))
            try:
                antwoord = urllib.request.urlopen(req, timeout=180)
                self._limieten(antwoord.headers)
                self.aanroepen += 1
                return antwoord
            except urllib.error.HTTPError as e:
                self._limieten(e.headers)
                if e.code == 429:
                    if self.rest == 0:
                        raise BudgetOp(f"dagbudget op bij {pad}")
                    wacht = float(e.headers.get("retry-after") or e.headers.get("x-ratelimit-reset") or 2)
                    time.sleep(min(max(wacht, 1), 60) + poging)
                    continue
                if e.code >= 500:
                    time.sleep(min(60, 2 ** poging))
                    continue
                try:
                    tekst = e.read()[:300].decode("utf-8", "replace")
                except Exception:
                    tekst = ""
                raise ApiFout(e.code, pad, tekst)
            except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError,
                    http.client.HTTPException) as e:
                if poging >= 6:
                    raise ApiFout("netwerk", pad, str(e))
                time.sleep(min(60, 2 ** poging))
        raise ApiFout("opgegeven", pad, "te vaak 429 of 5xx")

    def get(self, pad, params=None):
        url = API + pad + ("?" + urllib.parse.urlencode(params) if params else "")
        for poging in range(4):
            antwoord = self._open(url)
            try:
                with antwoord:
                    inhoud = antwoord.read()
                return json.loads(inhoud)
            except (http.client.IncompleteRead, ValueError, ConnectionError, socket.timeout):
                if poging == 3:
                    raise ApiFout("onvolledig", pad, "antwoord niet volledig of geen JSON")
                time.sleep(2 ** poging)

    def lijst(self, pad, params, paginering, limiet):
        """Alle records van een lijst, met controle dat de paginering echt afloopt."""
        items, paginas = [], 0
        start, cursor = 0, None
        while True:
            p = dict(params or {})
            if paginering == "start":
                p.update(start=start, limit=limiet)
            elif paginering == "cursor":
                p["limit"] = limiet
                if cursor:
                    p["cursor"] = cursor
            r = self.get(pad, p)
            paginas += 1
            if r.get("success") is False:
                raise ApiFout("success=false", pad, str(r.get("error"))[:200])
            data = r.get("data")
            if data is None:
                data = []
            if isinstance(data, dict):
                data = [data]
            items.extend(data)
            extra = r.get("additional_data") or {}
            if paginering == "start":
                pag = extra.get("pagination") or {}
                if not pag.get("more_items_in_collection"):
                    break
                volgende = pag.get("next_start", start + len(data))
                if volgende is None or volgende <= start:
                    raise ApiFout("paginering", pad, f"next_start {volgende} na {start}")
                start = volgende
            elif paginering == "cursor":
                cursor = extra.get("next_cursor")
                if not cursor:
                    break
            else:
                break
            if paginas > 20000:
                raise ApiFout("paginering", pad, "meer dan 20000 paginas, afgebroken")
        return items, paginas

    def download(self, pad, doel, verwacht=None):
        tmp = doel + ".deel"
        antwoord = self._open(API + pad, accept="*/*")
        h = hashlib.sha256()
        grootte = 0
        with antwoord, open(tmp, "wb") as f:
            while True:
                blok = antwoord.read(1 << 20)
                if not blok:
                    break
                f.write(blok)
                h.update(blok)
                grootte += len(blok)
        with self.slot:
            self.downloads += 1
            if self.rest is not None:
                self.rest -= KOSTEN_DOWNLOAD
            ververs = self.downloads % 100 == 0
        if ververs:
            self.get("/v1/users/me")  # echte budgetstand, de schatting kan afwijken
        if verwacht and grootte != verwacht:
            os.remove(tmp)
            raise ApiFout("grootte", pad, f"{grootte} bytes ontvangen, {verwacht} verwacht")
        os.replace(tmp, doel)
        return grootte, h.hexdigest()


def schrijf_json(pad, data):
    with gzip.open(pad, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def veilige_naam(naam):
    naam = re.sub(r"[^\w.\- ()]+", "_", naam or "").strip(" .")
    return (naam or "bestand")[:150]


def sleutel_id(rec):
    if isinstance(rec, dict):
        return rec.get("id", rec.get("key"))
    return None


# ---------------------------------------------------------------- per firma

def backup_firma(firma, token, rundir, basis, opties, vorige):
    m = {
        "firma": firma,
        "gestart": nu().isoformat(timespec="seconds"),
        "resultaat": "OK",
        "soorten": {},
        "niet_beschikbaar": {},
        "fouten": [],
        "waarschuwingen": [],
        "controles": {},
        "niet_meegenomen": dict(NIET_MEEGENOMEN),
    }
    datadir = os.path.join(rundir, firma, "data")
    os.makedirs(datadir, exist_ok=True)
    pd = Pipedrive(firma, token)
    data = {}

    try:
        ik = pd.get("/v1/users/me").get("data") or {}
        m["bedrijf"] = ik.get("company_name")
        m["bedrijf_id"] = ik.get("company_id")
        m["gebruiker"] = ik.get("name")
        m["beheerder"] = bool(ik.get("is_admin"))
        if not ik.get("is_admin"):
            m["waarschuwingen"].append("het token is geen beheerder: Pipedrive kan records verbergen")
    except (ApiFout, BudgetOp) as e:
        m["fouten"].append(f"aanmelden mislukt: {e}")
        m["resultaat"] = "FOUT"
        return m, data

    # 1. Kernlijsten (op de pc alleen de bestandenlijst: de gegevens staan al op VM en S3)
    soorten = [s for s in KERN if s[0] == "bestanden"] if opties.alleen_bijlagen else KERN
    for naam, pad, params, paginering, verplicht, limiet in soorten:
        voor = pd.rest
        t0 = time.time()
        try:
            items, paginas = pd.lijst(pad, params, paginering, limiet)
        except BudgetOp as e:
            m["fouten"].append(f"{naam}: {e}")
            continue
        except ApiFout as e:
            if not verplicht and e.code in (400, 402, 403, 404, 410):
                m["niet_beschikbaar"][naam] = f"HTTP {e.code}: niet in dit abonnement of niet via de API"
                log(f"  {firma:16} {naam:20} niet beschikbaar (HTTP {e.code})")
            elif verplicht:
                m["fouten"].append(f"{naam}: {e}")
                log(f"  {firma:16} {naam:20} FOUT {e}")
            else:
                m["waarschuwingen"].append(f"{naam}: {e}")
                log(f"  {firma:16} {naam:20} waarschuwing {e}")
            continue
        ids = [sleutel_id(x) for x in items]
        uniek = len(set(i for i in ids if i is not None))
        zonder_id = sum(1 for i in ids if i is None)
        schrijf_json(os.path.join(datadir, naam + ".json.gz"), items)
        data[naam] = items
        kosten = (voor - pd.rest) if (voor is not None and pd.rest is not None) else None
        m["soorten"][naam] = {
            "aantal": len(items), "uniek": uniek + zonder_id, "paginas": paginas,
            "api_tokens": kosten, "seconden": round(time.time() - t0, 1),
        }
        if uniek + zonder_id != len(items):
            m["waarschuwingen"].append(f"{naam}: {len(items) - uniek - zonder_id} dubbele records in de paginering")
        log(f"  {firma:16} {naam:20} {len(items):>7}  ({paginas} pag., {kosten} tokens)")

    if opties.alleen_bijlagen:
        m["niet_meegenomen"] = {"gegevens": "--alleen-bijlagen: de gegevens zelf staan in de VM-backup en op S3"}
        if not opties.zonder_bijlagen and "bestanden" in data:
            m["bijlagen"] = haal_bijlagen(pd, firma, data["bestanden"], basis, m, opties.werkers)
        return sluit_firma_af(m, pd, vorige), data

    # 2. Controle: deals tegen de samenvatting van Pipedrive zelf
    try:
        som = {}
        for status in ("open", "won", "lost"):
            r = pd.get("/v1/deals/summary", {"status": status}).get("data") or {}
            som[status] = r.get("total_count")
        eigen = {s: sum(1 for d in data.get("deals", []) if d.get("status") == s) for s in som}
        m["controles"]["deals_tegen_samenvatting"] = {"pipedrive": som, "backup": eigen}
        for s in som:
            if som[s] is not None and som[s] != eigen[s]:
                m["waarschuwingen"].append(
                    f"deals {s}: Pipedrive telt {som[s]}, backup heeft {eigen[s]}")
    except (ApiFout, BudgetOp) as e:
        m["waarschuwingen"].append(f"samenvatting deals niet opgehaald: {e}")

    # 3. Producten per deal (v2, honderd deals per aanroep)
    alle_deals = data.get("deals", []) + data.get("deals_verwijderd", []) + data.get("deals_gearchiveerd", [])
    met_product = sorted({d["id"] for d in alle_deals if (d.get("products_count") or 0) > 0})
    regels, fout = [], None
    voor = pd.rest
    for i in range(0, len(met_product), 100):
        try:
            stuk, _ = pd.lijst("/api/v2/deals/products",
                               {"deal_ids": ",".join(map(str, met_product[i:i + 100]))}, "cursor", 500)
            regels.extend(stuk)
        except (ApiFout, BudgetOp) as e:
            fout = str(e)
            break
    if fout:
        m["waarschuwingen"].append(f"deal_producten onvolledig: {fout}")
    schrijf_json(os.path.join(datadir, "deal_producten.json.gz"), regels)
    data["deal_producten"] = regels
    m["soorten"]["deal_producten"] = {"aantal": len(regels), "deals_met_product": len(met_product),
                                      "api_tokens": (voor - pd.rest) if voor is not None and pd.rest is not None else None}
    log(f"  {firma:16} {'deal_producten':20} {len(regels):>7}  ({len(met_product)} deals)")

    # 4. Extra deelnemers per deal (de hoofdpersoon staat al op de deal)
    met_deelnemers = sorted({d["id"] for d in alle_deals if (d.get("participants_count") or 0) > 1})
    deelnemers, gemist = [], []
    voor = pd.rest
    for did in met_deelnemers:
        if not pd.budget_ok():
            gemist.append(did)
            continue
        try:
            stuk, _ = pd.lijst(f"/v1/deals/{did}/participants", {}, "start", 500)
            for x in stuk:
                if isinstance(x, dict):
                    x.setdefault("deal_id", did)
            deelnemers.extend(stuk)
        except (ApiFout, BudgetOp) as e:
            gemist.append(did)
            m["waarschuwingen"].append(f"deelnemers deal {did}: {e}")
    if gemist:
        m["waarschuwingen"].append(f"deelnemers van {len(gemist)} deals niet opgehaald (budget of fout)")
    schrijf_json(os.path.join(datadir, "deal_deelnemers.json.gz"), deelnemers)
    data["deal_deelnemers"] = deelnemers
    m["soorten"]["deal_deelnemers"] = {"aantal": len(deelnemers), "deals": len(met_deelnemers), "gemist": len(gemist),
                                       "api_tokens": (voor - pd.rest) if voor is not None and pd.rest is not None else None}
    log(f"  {firma:16} {'deal_deelnemers':20} {len(deelnemers):>7}  ({len(met_deelnemers)} deals)")

    # 5. Bijlagen
    if opties.zonder_bijlagen:
        m["bijlagen"] = {"uitgezet": "--zonder-bijlagen: de bijlagen staan in de backup op de Linux-pc"}
    else:
        m["bijlagen"] = haal_bijlagen(pd, firma, data.get("bestanden", []), basis, m, opties.werkers)
    return sluit_firma_af(m, pd, vorige), data


def sluit_firma_af(m, pd, vorige):
    # Vergelijking met de vorige geslaagde run: grote dalingen melden
    if vorige:
        for naam in GEVOELIGE_SOORTEN_VOOR_DALING:
            oud = ((vorige.get("soorten") or {}).get(naam) or {}).get("aantal")
            nieuw = (m["soorten"].get(naam) or {}).get("aantal")
            if oud and nieuw is not None and oud >= 20 and nieuw < oud * GEZAKT_DREMPEL:
                m["waarschuwingen"].append(
                    f"{naam}: {nieuw} tegen {oud} bij de vorige backup ({vorige.get('gestart')}); "
                    "controleer of er in Pipedrive iets verdwenen is")

    m["api"] = {"aanroepen": pd.aanroepen, "daglimiet": pd.limiet,
                "rest_begin": pd.rest_begin, "rest_eind": pd.rest}
    if m["fouten"]:
        m["resultaat"] = "FOUT"
    elif m["waarschuwingen"]:
        m["resultaat"] = "WAARSCHUWING"
    return m


def haal_bijlagen(pd, firma, bestanden, basis, m, werkers):
    doelmap = os.path.join(basis, "bestanden", firma)
    os.makedirs(doelmap, exist_ok=True)
    # extern = in Pipedrive alleen een link (Google Drive e.d.): er is geen bestand,
    # de link staat in bestanden.json. verwijderd = in Pipedrive gewist voor we het
    # hadden. Beide zijn geen fout van de backup en staan met naam in het manifest.
    # mislukt = echte downloadfout, die geeft een waarschuwing.
    stand = {"totaal": len(bestanden), "nieuw": 0, "al_aanwezig": 0, "uitgesteld": 0,
             "bytes_nieuw": 0, "extern": [], "verwijderd": [], "mislukt": []}
    taken = []
    for f in bestanden:
        fid = f.get("id")
        naam = f.get("name") or f.get("file_name") or f"bestand-{fid}"
        verwacht = f.get("file_size") or None
        map_ = os.path.join(doelmap, str(fid))
        doel = os.path.join(map_, veilige_naam(naam))
        if os.path.exists(doel) and (not verwacht or os.path.getsize(doel) == verwacht):
            stand["al_aanwezig"] += 1
            continue
        locatie = f.get("remote_location") or "s3"
        if locatie != "s3":
            stand["extern"].append({"id": fid, "naam": naam, "locatie": locatie, "url": f.get("url")})
            continue
        if f.get("active_flag") is False:
            stand["verwijderd"].append({"id": fid, "naam": naam})
            continue
        taken.append((fid, naam, verwacht, map_, doel))

    def een(taak):
        fid, naam, verwacht, map_, doel = taak
        if not pd.budget_ok():
            return "uitgesteld", taak, None
        os.makedirs(map_, exist_ok=True)
        try:
            grootte, _ = pd.download(f"/v1/files/{fid}/download", doel, verwacht)
            return "nieuw", taak, grootte
        except BudgetOp:
            return "uitgesteld", taak, None
        except ApiFout as e:
            return "fout", taak, str(e)[:200]

    # Vanaf kantoor is een enkele download traag (rondreis), dus meerdere tegelijk.
    with ThreadPoolExecutor(max_workers=werkers) as pool:
        for uitkomst, taak, extra in pool.map(een, taken):
            if uitkomst == "nieuw":
                stand["nieuw"] += 1
                stand["bytes_nieuw"] += extra
                if stand["nieuw"] % 500 == 0:
                    log(f"  {firma:16} {'bijlagen':20} {stand['nieuw']}/{len(taken)} binnen "
                        f"({stand['bytes_nieuw'] / 1e9:.2f} GB), budget {pd.rest}/{pd.limiet}")
            elif uitkomst == "uitgesteld":
                stand["uitgesteld"] += 1
            else:
                stand["mislukt"].append({"id": taak[0], "naam": taak[1], "reden": extra})
    if stand["uitgesteld"]:
        m["waarschuwingen"].append(
            f"bijlagen: {stand['uitgesteld']} nog niet binnen (API-budget voor de apps gespaard); volgende nacht verder")
    if stand["mislukt"]:
        m["waarschuwingen"].append(f"bijlagen: {len(stand['mislukt'])} downloads mislukt, reden per bestand in manifest")
    log(f"  {firma:16} {'bijlagen':20} {stand['nieuw']:>7} nieuw, {stand['al_aanwezig']} al aanwezig, "
        f"{stand['uitgesteld']} uitgesteld, {len(stand['mislukt'])} mislukt, {len(stand['extern'])} externe links, "
        f"{len(stand['verwijderd'])} verwijderd in Pipedrive ({stand['bytes_nieuw'] / 1e6:.1f} MB)")
    return stand


# ---------------------------------------------------------------- Excel

def html_naar_tekst(h):
    if not isinstance(h, str) or "<" not in h:
        return html.unescape(h) if isinstance(h, str) else h
    h = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", h)
    h = re.sub(r"<[^>]+>", "", h)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(h)).strip()


def plat(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return "ja" if v else "nee"
    if isinstance(v, (int, float, str)):
        return v
    if isinstance(v, dict):
        for k in ("name", "title"):
            if k in v and v[k] not in (None, ""):
                return v[k]
        if "amount" in v:
            return f"{v.get('amount')} {v.get('currency') or ''}".strip()
        if set(v) <= {"value", "label", "primary"}:
            return plat(v.get("value"))
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        delen = []
        for x in v:
            if isinstance(x, dict):
                if "value" in x and x.get("value") not in (None, ""):
                    s = str(x["value"])
                    if x.get("label"):
                        s += f" ({x['label']})"
                    delen.append(s)
                elif "name" in x:
                    delen.append(str(x["name"]))
                elif "value" not in x:
                    delen.append(json.dumps(x, ensure_ascii=False))
            elif x not in (None, ""):
                delen.append(str(x))
        return "; ".join(delen)
    return str(v)


def schrijf_excel(pad, firma, m, data):
    try:
        from openpyxl import Workbook
        from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    except ImportError:
        return {"fout": "openpyxl ontbreekt in deze Python, geen Excel gemaakt"}

    afgekapt = {"cellen": 0}
    MAX = 32000

    def cel(v):
        if isinstance(v, str):
            v = ILLEGAL_CHARACTERS_RE.sub("", v)
            if len(v) > MAX:
                afgekapt["cellen"] += 1
                v = v[:MAX] + " [AFGEKAPT in Excel; de volledige tekst staat in de JSON-backup]"
        return v

    gebruikers = {u.get("id"): u.get("name") for u in data.get("gebruikers", [])}
    personen = {p.get("id"): p.get("name") for p in data.get("personen", [])}
    organisaties = {o.get("id"): o.get("name") for o in data.get("organisaties", [])}
    pipelines = {p.get("id"): p.get("name") for p in data.get("pipelines", [])}
    fasen = {s.get("id"): s.get("name") for s in data.get("fasen", [])}
    deal_titels = {d.get("id"): d.get("title") for d in
                   data.get("deals", []) + data.get("deals_verwijderd", []) + data.get("deals_gearchiveerd", [])}
    lead_labels = {l.get("id"): l.get("name") for l in data.get("lead_labels", [])}

    def veldkaart(soort):
        kaart = {}
        for f in data.get(soort, []):
            if isinstance(f, dict) and f.get("key"):
                opties = {str(o.get("id")): o.get("label") for o in (f.get("options") or []) if isinstance(o, dict)}
                kaart[f["key"]] = (f.get("name") or f["key"], opties)
        return kaart

    def blad(wb, titel, records, kaart=None, extra=None, html_velden=()):
        ws = wb.create_sheet(titel[:31])
        kaart = kaart or {}
        sleutels = []
        gezien = set()
        for k in kaart:
            if any(k in r for r in records[:2000]):
                sleutels.append(k)
                gezien.add(k)
        for r in records:
            for k in r:
                if k not in gezien:
                    gezien.add(k)
                    sleutels.append(k)
        namen = {}
        for k in sleutels:
            if k in kaart:
                naam = kaart[k][0]
            else:
                ouder = next((p for p in kaart if len(p) == 40 and k.startswith(p + "_")), None)
                naam = f"{kaart[ouder][0]} ({k[len(ouder) + 1:]})" if ouder else k
            if naam in namen.values():
                naam = f"{naam} [{k}]"
            namen[k] = naam
        extra = extra or []
        koppen = [n for n, _ in extra] + [namen[k] for k in sleutels]
        ws.append(koppen)
        for r in records:
            rij = [cel(plat(f(r))) for _, f in extra]
            for k in sleutels:
                v = r.get(k)
                if k in html_velden:
                    v = html_naar_tekst(v)
                if k in kaart and kaart[k][1] and isinstance(v, (str, int)) and v != "":
                    opties = kaart[k][1]
                    v = ", ".join(opties.get(x.strip(), x.strip()) for x in str(v).split(","))
                rij.append(cel(plat(v)))
            ws.append(rij)
        return ws

    wb = Workbook(write_only=True)
    ov = wb.create_sheet("Overzicht")
    ov.append(["Pipedrive-backup", m.get("bedrijf") or firma])
    ov.append(["Gemaakt (UTC)", m.get("gestart")])
    ov.append(["Resultaat", m.get("resultaat")])
    ov.append(["Volledige gegevens", "data/*.json.gz naast dit bestand (alle velden, ook wat hier niet past)"])
    ov.append([])
    ov.append(["Soort", "Aantal"])
    for naam, s in m.get("soorten", {}).items():
        ov.append([naam, s.get("aantal")])
    for naam, reden in m.get("niet_beschikbaar", {}).items():
        ov.append([naam, f"niet beschikbaar: {reden}"])
    for w in m.get("waarschuwingen", []):
        ov.append(["waarschuwing", cel(w)])
    for w in m.get("fouten", []):
        ov.append(["FOUT", cel(w)])

    dk = veldkaart("velden_deal")
    deal_extra = [("Pipeline (naam)", lambda r: pipelines.get(r.get("pipeline_id"))),
                  ("Fase (naam)", lambda r: fasen.get(r.get("stage_id")))]
    blad(wb, "Deals", data.get("deals", []), dk, deal_extra)
    if data.get("deals_gearchiveerd"):
        blad(wb, "Deals gearchiveerd", data["deals_gearchiveerd"], dk, deal_extra)
    if data.get("deals_verwijderd"):
        blad(wb, "Deals verwijderd", data["deals_verwijderd"], dk, deal_extra)
    blad(wb, "Leads", data.get("leads", []), dk, [
        ("Persoon (naam)", lambda r: personen.get(r.get("person_id"))),
        ("Organisatie (naam)", lambda r: organisaties.get(r.get("organization_id"))),
        ("Eigenaar (naam)", lambda r: gebruikers.get(r.get("owner_id"))),
        ("Labels (naam)", lambda r: ", ".join(lead_labels.get(x, x) for x in (r.get("label_ids") or []))),
    ])
    blad(wb, "Personen", data.get("personen", []), veldkaart("velden_persoon"))
    blad(wb, "Organisaties", data.get("organisaties", []), veldkaart("velden_organisatie"))
    blad(wb, "Activiteiten", data.get("activiteiten", []), veldkaart("velden_activiteit"),
         html_velden=("note", "public_description"))
    blad(wb, "Notities", data.get("notities", []), None, html_velden=("content",))
    blad(wb, "Producten", data.get("producten", []), veldkaart("velden_product"))
    blad(wb, "Deal-producten", data.get("deal_producten", []), None,
         [("Deal (titel)", lambda r: deal_titels.get(r.get("deal_id")))])
    blad(wb, "Deal-deelnemers", data.get("deal_deelnemers", []), None,
         [("Deal (titel)", lambda r: deal_titels.get(r.get("deal_id")))])
    blad(wb, "Bestanden", data.get("bestanden", []), None,
         [("Lokaal in backup", lambda r: f"bestanden/{firma}/{r.get('id')}/{veilige_naam(r.get('name') or r.get('file_name') or '')}")])
    if data.get("gesprekken"):
        blad(wb, "Gesprekken", data["gesprekken"])
    blad(wb, "Pipelines", data.get("pipelines", []))
    blad(wb, "Fasen", data.get("fasen", []), None, [("Pipeline (naam)", lambda r: pipelines.get(r.get("pipeline_id")))])
    blad(wb, "Gebruikers", data.get("gebruikers", []))
    wb.save(pad)
    return {"bestand": os.path.basename(pad), "afgekapte_cellen": afgekapt["cellen"]}


# ---------------------------------------------------------------- off-site

def sha256_bestand(pad):
    h = hashlib.sha256()
    with open(pad, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def versleutel_en_upload(bron, s3_sleutel, bucket, passfile):
    """Zelfde werkwijze als scripts/db-backup.sh: pas uploaden als de
    versleutelde kopie aantoonbaar terug te lezen is."""
    gpg = bron + ".gpg"
    terug = bron + ".terug"
    stil = dict(check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    subprocess.run(["gpg", "--batch", "--yes", "--symmetric", "--cipher-algo", "AES256",
                    "--passphrase-file", passfile, "-o", gpg, bron], **stil)
    try:
        subprocess.run(["gpg", "-d", "--batch", "--yes", "--quiet", "--passphrase-file", passfile,
                        "-o", terug, gpg], **stil)
        if sha256_bestand(terug) != sha256_bestand(bron):
            raise RuntimeError("versleutelde kopie niet terug te lezen, niet geupload")
        subprocess.run(["aws", "s3", "cp", "--only-show-errors", gpg, f"s3://{bucket}/{s3_sleutel}"], **stil)
        return os.path.getsize(gpg)
    finally:
        for p in (gpg, terug):
            if os.path.exists(p):
                os.remove(p)


def offsite(firma, rundir, stamp, basis, env):
    bucket = env.get("S3_BACKUP_BUCKET")
    passfile = os.path.expanduser(env.get("BACKUP_PASSPHRASE_FILE") or "~/.backup-passphrase")
    if not bucket:
        return {"status": "FOUT: S3_BACKUP_BUCKET staat niet in .env (gebruik --zonder-offsite als dat zo hoort)"}
    if not os.path.exists(passfile):
        return {"status": f"FOUT: {passfile} ontbreekt"}
    tmpdir = os.path.join(basis, ".tmp")
    os.makedirs(tmpdir, mode=0o700, exist_ok=True)
    tar = os.path.join(tmpdir, f"{firma}-{stamp}.tar.gz")
    try:
        with tarfile.open(tar, "w:gz") as t:
            t.add(os.path.join(rundir, firma), arcname=f"{stamp}/{firma}")
        sleutel = f"pipedrive/{firma}/{stamp}.tar.gz.gpg"
        grootte = versleutel_en_upload(tar, sleutel, bucket, passfile)
        return {"status": "ok", "s3": f"s3://{bucket}/{sleutel}", "bytes": grootte}
    except (subprocess.CalledProcessError, RuntimeError, OSError) as e:
        detail = getattr(e, "stderr", b"") or b""
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", "replace")
        return {"status": f"FOUT: {e} {detail[:200]}".strip()}
    finally:
        if os.path.exists(tar):
            os.remove(tar)


# ---------------------------------------------------------------- opruimen

def ruim_op(basis, behouden):
    """Elke run 30 dagen; daarna de eerste van elke maand, 12 maanden lang."""
    runs = sorted(d for d in os.listdir(basis) if re.fullmatch(r"\d{8}-\d{4}", d))
    grens = nu() - dt.timedelta(days=RETENTIE_DAGEN)
    maandgrens = nu() - dt.timedelta(days=31 * RETENTIE_MAANDEN)
    eerste_van_maand = {}
    for r in runs:
        eerste_van_maand.setdefault(r[:6], r)
    weg = []
    for r in runs:
        t = dt.datetime.strptime(r, "%Y%m%d-%H%M").replace(tzinfo=dt.timezone.utc)
        if r in behouden or t >= grens:
            continue
        if eerste_van_maand.get(r[:6]) == r and t >= maandgrens:
            continue
        shutil.rmtree(os.path.join(basis, r), ignore_errors=True)
        weg.append(r)
    return weg


def kuma(url, ok, tekst):
    if not url:
        return
    try:
        q = urllib.parse.urlencode({"status": "up" if ok else "down", "msg": tekst[:200], "ping": ""})
        urllib.request.urlopen(url + ("&" if "?" in url else "?") + q, timeout=20).read()
    except Exception as e:
        log(f"kuma-melding mislukt: {e}")


# ---------------------------------------------------------------- hoofd

def main():
    global RESERVE
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--firma", action="append", choices=FIRMAS)
    ap.add_argument("--doel", default=os.path.expanduser("~/backups/pipedrive"))
    ap.add_argument("--env", default=os.path.expanduser("~/appportal/.env"))
    ap.add_argument("--zonder-bijlagen", action="store_true")
    ap.add_argument("--alleen-bijlagen", action="store_true",
                    help="alleen bestandenlijst en bijlagen (Linux-pc); de gegevens doet de VM")
    ap.add_argument("--zonder-offsite", action="store_true")
    ap.add_argument("--zonder-excel", action="store_true")
    ap.add_argument("--werkers", type=int, default=8, help="gelijktijdige bijlage-downloads")
    ap.add_argument("--reserve", type=float, default=RESERVE,
                    help="deel van het dagbudget dat voor de apps blijft (standaard 0.35)")
    opties = ap.parse_args()
    RESERVE = opties.reserve

    basis = opties.doel
    os.makedirs(basis, mode=0o700, exist_ok=True)
    os.chmod(basis, 0o700)
    slot = open(os.path.join(basis, ".slot"), "w")
    try:
        fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("er loopt al een Pipedrive-backup, deze start niet")
        return 1

    env = lees_env(opties.env)
    statuspad = os.path.join(basis, "status.json")
    try:
        with open(statuspad, encoding="utf-8") as f:
            oude_status = json.load(f)
    except (OSError, ValueError):
        oude_status = {}

    stamp = nu().strftime("%Y%m%d-%H%M")
    rundir = os.path.join(basis, stamp)
    os.makedirs(rundir, exist_ok=True)
    firmas = opties.firma or FIRMAS
    log(f"Pipedrive-backup {stamp} gestart voor {', '.join(firmas)}")

    samen = {"stamp": stamp, "gestart": nu().isoformat(timespec="seconds"), "firmas": {}}
    for firma in firmas:
        token = env.get("PIPEDRIVE_TOKEN_" + firma.upper(), "").strip()
        if not token:
            samen["firmas"][firma] = {"resultaat": "FOUT", "fouten": ["geen token in .env"]}
            log(f"  {firma}: FOUT geen token in .env")
            continue
        vorige_stamp = ((oude_status.get("firmas") or {}).get(firma) or {}).get("laatst_geslaagd")
        vorige = None
        if vorige_stamp:
            try:
                with open(os.path.join(basis, vorige_stamp, firma, "manifest.json"), encoding="utf-8") as f:
                    vorige = json.load(f)
            except (OSError, ValueError):
                vorige = None
        try:
            m, data = backup_firma(firma, token, rundir, basis, opties, vorige)
        except Exception as e:  # onverwacht: zichtbaar maken, andere firma's laten doorgaan
            m, data = {"firma": firma, "resultaat": "FOUT", "fouten": [f"onverwachte fout: {e!r}"]}, {}
        if data and not opties.zonder_excel and not opties.alleen_bijlagen:
            try:
                m["excel"] = schrijf_excel(
                    os.path.join(rundir, firma, f"{firma}-pipedrive-{stamp[:8]}.xlsx"), firma, m, data)
                if m["excel"].get("fout"):
                    m.setdefault("waarschuwingen", []).append(m["excel"]["fout"])
                elif m["excel"].get("afgekapte_cellen"):
                    m.setdefault("waarschuwingen", []).append(
                        f"Excel: {m['excel']['afgekapte_cellen']} cellen ingekort (te lang voor Excel); JSON is volledig")
            except Exception as e:
                m["excel"] = {"fout": repr(e)}
                m.setdefault("waarschuwingen", []).append(f"Excel mislukt: {e!r}")
        m["klaar"] = nu().isoformat(timespec="seconds")
        if not opties.zonder_offsite and m.get("resultaat") != "FOUT":
            m["offsite"] = offsite(firma, rundir, stamp, basis, env)
            if str(m["offsite"].get("status", "")).startswith("FOUT"):
                m.setdefault("fouten", []).append(f"off-site: {m['offsite']['status']}")
        if m.get("fouten"):
            m["resultaat"] = "FOUT"
        elif m.get("waarschuwingen") and m.get("resultaat") == "OK":
            m["resultaat"] = "WAARSCHUWING"
        os.makedirs(os.path.join(rundir, firma), exist_ok=True)
        with open(os.path.join(rundir, firma, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=1)
        geslaagd = m["resultaat"] in ("OK", "WAARSCHUWING")
        oud = (oude_status.get("firmas") or {}).get(firma) or {}
        samen["firmas"][firma] = {
            "resultaat": m["resultaat"],
            "laatst_geslaagd": stamp if geslaagd else oud.get("laatst_geslaagd"),
            "tellingen": {k: v.get("aantal") for k, v in (m.get("soorten") or {}).items()},
            "fouten": m.get("fouten", []),
            "waarschuwingen": m.get("waarschuwingen", []),
        }
        log(f"  {firma}: {m['resultaat']}" + (f" ({len(m.get('waarschuwingen', []))} waarschuwingen)" if m.get("waarschuwingen") else ""))
        for w in m.get("fouten", []):
            log(f"    FOUT {w}")
        for w in m.get("waarschuwingen", []):
            log(f"    let op: {w}")

    # Firma's die deze keer niet meededen, houden hun vorige stand.
    for firma, oud in (oude_status.get("firmas") or {}).items():
        samen["firmas"].setdefault(firma, oud)
    samen["klaar"] = nu().isoformat(timespec="seconds")
    with open(statuspad + ".tmp", "w", encoding="utf-8") as f:
        json.dump(samen, f, ensure_ascii=False, indent=1)
    os.replace(statuspad + ".tmp", statuspad)

    behouden = {v.get("laatst_geslaagd") for v in samen["firmas"].values() if v.get("laatst_geslaagd")}
    weg = ruim_op(basis, behouden | {stamp})
    if weg:
        log(f"opgeruimd: {', '.join(weg)}")

    deze_keer = {f: samen["firmas"][f] for f in firmas}
    fout = [f for f, v in deze_keer.items() if v["resultaat"] == "FOUT"]
    let_op = [f for f, v in deze_keer.items() if v["resultaat"] == "WAARSCHUWING"]
    tekst = "OK" if not fout else f"FOUT bij {', '.join(fout)}"
    if let_op:
        tekst += f"; waarschuwing bij {', '.join(let_op)}"
    if not fout:
        # Alleen een geslaagde run raakt dit bestand; de gezondheidssonde
        # (scripts/gezondheid.py) kijkt naar de leeftijd ervan.
        with open(os.path.join(basis, "laatst-gelukt"), "w", encoding="utf-8") as f:
            f.write(f"{stamp} {tekst}\n")
    kuma(env.get("PIPEDRIVE_BACKUP_PUSH_URL"), not fout, tekst)
    log(f"klaar: {tekst}")
    return 1 if fout else 0


if __name__ == "__main__":
    sys.exit(main())

"""Pipedrive-gereedschap voor Claude: vijf firma's, een token per firma.

Elke handeling hoort bij precies een firma. `firma_kiezen` is de poort: zonder
geldige firma-parameter gebeurt er niets, en de weigering noemt de vijf keuzes
zodat Claude ze aan de gebruiker kan voorleggen. Er is geen standaardfirma en
er wordt nooit geraden.

Tokens: `PIPEDRIVE_TOKEN_<FIRMA>` in de omgeving, anders uit het .env-bestand
van de stack (`~/appportal/.env`, alleen die regels). Dat zijn dezelfde tokens
als het sales-dashboard gebruikt, dus een rotatie hoeft maar op een plek.

Praat met de v1-API (api.pipedrive.com/v1) via de stdlib, zonder extra
pakketten. 429 en 5xx worden een paar keer opnieuw geprobeerd. Het token gaat
mee als kopregel, niet in de URL, zodat het nergens in een foutmelding of log
terechtkomt.
"""
from __future__ import annotations

import html
import json
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.pipedrive.com/v1"
CACHE_TTL = 600  # naslag (velden, fases, gebruikers) 10 minuten onthouden


class Geweigerd(Exception):
    """Nette weigering; de tekst is bedoeld om aan de gebruiker door te geven."""


class PipedriveFout(Exception):
    def __init__(self, status: int, boodschap: str, info=None):
        super().__init__(boodschap)
        self.status, self.info = status, info


# De vijf firma's. De sleutel is ook het achtervoegsel van de omgevingsvariabele
# PIPEDRIVE_TOKEN_<SLEUTEL in hoofdletters>, gelijk aan het sales-dashboard.
FIRMAS = {
    "harchitects": "H-Architects",
    "unabo": "UNABO",
    "tknburo": "TKN-Buro",
    "energieefficient": "Energie Efficiënt",
    "harmoniebouw": "HarmonieBOUW",
}
# Andere schrijfwijzen die eenduidig een firma aanwijzen (Pipedrive noemt
# TKN-Buro bijvoorbeeld TKN-Tekenwerk). Alles wat hier niet staat wordt
# geweigerd, nooit geraden.
_ALIASSEN = {"tkntekenwerk": "tknburo", "tknburotekenwerk": "tknburo",
             "harmoniebouwbv": "harmoniebouw", "energieefficient": "energieefficient"}


def _norm(tekst: str) -> str:
    """Kleine letters, geen accenten, alleen letters en cijfers."""
    plat = unicodedata.normalize("NFKD", str(tekst or ""))
    return "".join(c for c in plat if c.isalnum()).lower()


def _keuzes() -> str:
    return ", ".join(f"{s} ({n})" for s, n in FIRMAS.items())


# ---- Tokens ---------------------------------------------------------------
def _env_bestand() -> str:
    return os.environ.get("PIPEDRIVE_ENV_BESTAND") or os.path.expanduser("~/appportal/.env")


def tokens() -> dict[str, str]:
    """Token per firma. Omgeving eerst; wat ontbreekt komt uit het .env-bestand
    van de stack, en daaruit alleen de PIPEDRIVE_TOKEN_-regels."""
    uit: dict[str, str] = {}
    for sleutel in FIRMAS:
        w = os.environ.get("PIPEDRIVE_TOKEN_" + sleutel.upper(), "").strip()
        if w:
            uit[sleutel] = w
    pad = _env_bestand()
    if len(uit) < len(FIRMAS) and os.path.isfile(pad):
        with open(pad, encoding="utf-8") as f:
            for regel in f:
                m = re.match(r"^\s*(?:export\s+)?PIPEDRIVE_TOKEN_([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$", regel)
                if not m:
                    continue
                sleutel = m.group(1).lower()
                waarde = m.group(2).strip().strip('"').strip("'")
                if sleutel in FIRMAS and sleutel not in uit and waarde:
                    uit[sleutel] = waarde
    return uit


def firma_kiezen(a: dict) -> str:
    """De verplichte firma-parameter. Ontbreekt of onbekend: weigering met de
    lijst, zodat de vraag bij de gebruiker terechtkomt."""
    ruw = a.get("firma") if isinstance(a, dict) else None
    ruw = (str(ruw) if ruw is not None else "").strip()
    if not ruw:
        raise Geweigerd(
            "Geen firma opgegeven. Elke opdracht hoort bij precies een firma. "
            "Vraag de gebruiker voor welke firma dit bedoeld is en geef die "
            f"door in de parameter 'firma'. Keuzes: {_keuzes()}.")
    plat = _norm(ruw)
    sleutel = None
    if plat in FIRMAS:
        sleutel = plat
    else:
        for s, n in FIRMAS.items():
            if _norm(n) == plat:
                sleutel = s
        sleutel = sleutel or _ALIASSEN.get(plat)
    if sleutel is None:
        raise Geweigerd(f"Onbekende firma '{ruw}'. Keuzes: {_keuzes()}. Vraag "
                        "de gebruiker welke bedoeld is; kies niet zelf.")
    if sleutel not in tokens():
        raise Geweigerd(f"Voor {FIRMAS[sleutel]} staat geen Pipedrive-token "
                        "klaar op de server; meld dit aan de beheerder.")
    return sleutel


# ---- De API ---------------------------------------------------------------
def _roep(sleutel: str, methode: str, pad: str, params: dict | None = None,
          body: dict | None = None) -> dict:
    token = tokens().get(sleutel)
    if not token:
        raise Geweigerd(f"Geen token voor {FIRMAS.get(sleutel, sleutel)}.")
    q = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    url = API + pad + ("?" + urllib.parse.urlencode(q, doseq=True) if q else "")
    data = json.dumps(body).encode() if body is not None else None
    koppen = {"Accept": "application/json", "x-api-token": token,
              "User-Agent": "globaal-pipedrive-mcp/1.0"}
    if data is not None:
        koppen["Content-Type"] = "application/json"
    laatste = ""
    for poging in range(4):
        req = urllib.request.Request(url, data=data, method=methode, headers=koppen)
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                antwoord = json.load(r)
            break
        except urllib.error.HTTPError as e:
            tekst = e.read().decode("utf-8", "replace")
            if e.code == 429 or e.code >= 500:
                laatste = f"Pipedrive gaf status {e.code}"
                time.sleep(min(2 * (poging + 1), 8))
                continue
            try:
                fout = json.loads(tekst)
            except Exception:
                fout = {}
            raise PipedriveFout(e.code, fout.get("error") or tekst[:300],
                                fout.get("error_info")) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            laatste = f"{type(e).__name__}: {getattr(e, 'reason', e)}"
            time.sleep(min(1 + poging, 4))
    else:
        raise PipedriveFout(0, f"Pipedrive niet bereikbaar: {laatste}")
    if isinstance(antwoord, dict) and antwoord.get("success") is False:
        raise PipedriveFout(200, antwoord.get("error") or "onbekende fout",
                            antwoord.get("error_info"))
    return antwoord if isinstance(antwoord, dict) else {"data": antwoord}


def _alles(sleutel: str, pad: str, params: dict, maximum: int) -> tuple[list, bool]:
    """Pagina's ophalen tot `maximum` rijen. Tweede waarde: is er nog meer."""
    uit: list = []
    start = int(params.get("start") or 0)
    while len(uit) < maximum:
        stap = min(100, maximum - len(uit))
        antwoord = _roep(sleutel, "GET", pad, {**params, "start": start, "limit": stap})
        rijen = antwoord.get("data") or []
        uit.extend(rijen)
        pag = (antwoord.get("additional_data") or {}).get("pagination") or {}
        if not rijen or not pag.get("more_items_in_collection"):
            return uit, False
        start = int(pag.get("next_start") or start + stap)
    return uit, True


# ---- Naslag met cache -----------------------------------------------------
_cache: dict = {}
_slot = threading.Lock()


def _gecached(sleutel: str, naam: str, maker):
    k = (sleutel, naam)
    with _slot:
        c = _cache.get(k)
        if c and c[0] > time.time():
            return c[1]
    w = maker()
    with _slot:
        _cache[k] = (time.time() + CACHE_TTL, w)
    return w


def cache_leeg():
    with _slot:
        _cache.clear()


def _ik(sleutel):
    return _gecached(sleutel, "ik", lambda: _roep(sleutel, "GET", "/users/me").get("data") or {})


def _domein(sleutel) -> str:
    return (_ik(sleutel).get("company_domain") or "").strip()


def _link(sleutel, soort, oid) -> str:
    d = _domein(sleutel)
    return f"https://{d}.pipedrive.com/{soort}/{oid}" if d and oid else ""


def _gebruikers(sleutel) -> dict:
    return _gecached(sleutel, "gebruikers", lambda: {
        u["id"]: u for u in _roep(sleutel, "GET", "/users").get("data") or []})


def _fases(sleutel) -> dict:
    return _gecached(sleutel, "fases", lambda: {
        s["id"]: s for s in _roep(sleutel, "GET", "/stages").get("data") or []})


def _pijplijnen(sleutel) -> dict:
    return _gecached(sleutel, "pijplijnen", lambda: {
        p["id"]: p for p in _roep(sleutel, "GET", "/pipelines").get("data") or []})


def _activiteittypes(sleutel) -> list:
    return _gecached(sleutel, "activiteittypes",
                     lambda: _roep(sleutel, "GET", "/activityTypes").get("data") or [])


_VELDPAD = {"deal": "/dealFields", "person": "/personFields",
            "organization": "/organizationFields"}


def _velden(sleutel, soort) -> list:
    pad = _VELDPAD.get(soort)
    if not pad:
        raise Geweigerd("soort moet deal, person of organization zijn")
    return _gecached(sleutel, "velden:" + soort,
                     lambda: _alles(sleutel, pad, {}, 1000)[0])


def _is_eigen(f: dict) -> bool:
    return bool(f.get("edit_flag")) and bool(re.fullmatch(r"[0-9a-f]{40}", str(f.get("key", ""))))


def _eigen_velden(sleutel, soort) -> list:
    return [f for f in _velden(sleutel, soort) if _is_eigen(f)]


def _naam_gebruiker(sleutel, v) -> str | None:
    if isinstance(v, dict):
        return v.get("name")
    if v is None:
        return None
    u = _gebruikers(sleutel).get(v)
    return u.get("name") if u else str(v)


def _naam_fase(sleutel, sid):
    s = _fases(sleutel).get(sid)
    return s.get("name") if s else sid


def _naam_pijplijn(sleutel, pid):
    p = _pijplijnen(sleutel).get(pid)
    return p.get("name") if p else pid


# ---- Eigen velden: leesbaar naar buiten, sleutels naar binnen -------------
def _waarde_leesbaar(f: dict, v):
    opties = f.get("options") or []
    if not opties:
        return v
    labels = {str(o.get("id")): o.get("label") for o in opties}
    if f.get("field_type") == "set":
        ids = v if isinstance(v, list) else str(v).split(",")
        return [labels.get(str(i).strip(), str(i).strip()) for i in ids if str(i).strip()]
    return labels.get(str(v), v)


def _eigen_velden_uit(sleutel, soort, rij: dict) -> dict:
    per_key = {f["key"]: f for f in _eigen_velden(sleutel, soort)}
    uit = {}
    for k, v in (rij or {}).items():
        f = per_key.get(k)
        if f and v not in (None, "", []):
            uit[f["name"]] = _waarde_leesbaar(f, v)
    return uit


def _optie_id(f: dict, waarde):
    for o in f.get("options") or []:
        if str(o.get("id")) == str(waarde) or _norm(o.get("label", "")) == _norm(waarde):
            return o["id"]
    raise Geweigerd(f"Ongeldige keuze '{waarde}' voor veld '{f['name']}'. Keuzes: "
                    + ", ".join(str(o.get("label")) for o in f.get("options") or []))


def _waarde_in(f: dict, waarde):
    if not (f.get("options") or []):
        return waarde
    if f.get("field_type") == "set":
        items = waarde if isinstance(waarde, list) else str(waarde).split(",")
        return ",".join(str(_optie_id(f, str(w).strip())) for w in items if str(w).strip())
    return _optie_id(f, waarde)


def _velden_in(sleutel, soort, velden) -> dict:
    """{veldnaam of sleutel: waarde} -> {pipedrive-sleutel: waarde}."""
    if not velden:
        return {}
    if not isinstance(velden, dict):
        raise Geweigerd("'velden' moet een object zijn: {veldnaam: waarde}")
    defs = _eigen_velden(sleutel, soort)
    op_key = {f["key"]: f for f in defs}
    op_naam = {_norm(f["name"]): f for f in defs}
    uit = {}
    for naam, waarde in velden.items():
        f = op_key.get(naam) or op_naam.get(_norm(naam))
        if not f:
            raise Geweigerd(f"Onbekend eigen veld '{naam}' voor {soort}. Beschikbaar: "
                            + (", ".join(sorted(x["name"] for x in defs)) or "geen"))
        uit[f["key"]] = _waarde_in(f, waarde)
    return uit


# ---- Vormgeving van rijen -------------------------------------------------
def _ref(v):
    """Gekoppeld object {value|id, name} -> {id, naam}; anders ongewijzigd."""
    if isinstance(v, dict):
        return {"id": v.get("value", v.get("id")), "naam": v.get("name")}
    return v


def _contact(lijst) -> list:
    if not isinstance(lijst, list):
        return [lijst] if lijst else []
    return [x.get("value") if isinstance(x, dict) else x for x in lijst if x]


def _platte_tekst(inhoud) -> str:
    t = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", str(inhoud or ""), flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", t)).strip()


def _deal_kort(sleutel, d: dict) -> dict:
    return {"id": d.get("id"), "titel": d.get("title"),
            "waarde": d.get("value"), "valuta": d.get("currency"),
            "status": d.get("status"),
            "pijplijn": _naam_pijplijn(sleutel, d.get("pipeline_id")),
            "fase": _naam_fase(sleutel, d.get("stage_id")),
            "persoon": _ref(d.get("person_id")) or d.get("person_name"),
            "organisatie": _ref(d.get("org_id")) or d.get("org_name"),
            "eigenaar": _naam_gebruiker(sleutel, d.get("user_id")) or d.get("owner_name"),
            "verwachte_sluiting": d.get("expected_close_date"),
            "volgende_activiteit": d.get("next_activity_date"),
            "bijgewerkt": d.get("update_time")}


def _persoon_kort(sleutel, p: dict) -> dict:
    return {"id": p.get("id"), "naam": p.get("name"),
            "organisatie": _ref(p.get("org_id")) or p.get("org_name"),
            "emails": _contact(p.get("email")), "telefoons": _contact(p.get("phone")),
            "eigenaar": _naam_gebruiker(sleutel, p.get("owner_id")),
            "open_deals": p.get("open_deals_count"), "bijgewerkt": p.get("update_time")}


def _org_kort(sleutel, o: dict) -> dict:
    return {"id": o.get("id"), "naam": o.get("name"), "adres": o.get("address"),
            "eigenaar": _naam_gebruiker(sleutel, o.get("owner_id")),
            "personen": o.get("people_count"), "open_deals": o.get("open_deals_count"),
            "bijgewerkt": o.get("update_time")}


def _activiteit_kort(a: dict) -> dict:
    return {"id": a.get("id"), "onderwerp": a.get("subject"), "type": a.get("type"),
            "datum": a.get("due_date"), "tijd_utc": a.get("due_time"),
            "duur": a.get("duration"), "gedaan": bool(a.get("done")),
            "deal": {"id": a.get("deal_id"), "naam": a.get("deal_title")} if a.get("deal_id") else None,
            "persoon": {"id": a.get("person_id"), "naam": a.get("person_name")} if a.get("person_id") else None,
            "organisatie": {"id": a.get("org_id"), "naam": a.get("org_name")} if a.get("org_id") else None,
            "eigenaar": a.get("owner_name"), "notitie": _platte_tekst(a.get("note")) or None}


def _notitie_kort(a: dict) -> dict:
    return {"id": a.get("id"), "tekst": _platte_tekst(a.get("content")),
            "door": (a.get("user") or {}).get("name") if isinstance(a.get("user"), dict) else a.get("user_id"),
            "datum": a.get("add_time"), "deal_id": a.get("deal_id"),
            "persoon_id": a.get("person_id"), "organisatie_id": a.get("org_id"),
            "lead_id": a.get("lead_id"), "vastgepind": bool(a.get("pinned_to_deal_flag"))}


def _lead_kort(sleutel, l: dict) -> dict:
    w = l.get("value") or {}
    return {"id": l.get("id"), "titel": l.get("title"),
            "waarde": w.get("amount") if isinstance(w, dict) else w,
            "valuta": w.get("currency") if isinstance(w, dict) else None,
            "persoon_id": l.get("person_id"), "organisatie_id": l.get("organization_id"),
            "eigenaar": _naam_gebruiker(sleutel, l.get("owner_id")),
            "verwachte_sluiting": l.get("expected_close_date"),
            "gearchiveerd": bool(l.get("is_archived")), "bron": l.get("source_name"),
            "bijgewerkt": l.get("update_time")}


def _zoekitem(sleutel, it: dict) -> dict:
    item = it.get("item", it) or {}
    soort = item.get("type")
    uit = {"soort": soort, "id": item.get("id"),
           "naam": item.get("title") or item.get("name")}
    if soort == "deal":
        uit.update(status=item.get("status"), waarde=item.get("value"), valuta=item.get("currency"),
                   fase=(item.get("stage") or {}).get("name"),
                   persoon=(item.get("person") or {}).get("name"),
                   organisatie=(item.get("organization") or {}).get("name"))
    elif soort == "person":
        uit.update(organisatie=(item.get("organization") or {}).get("name"),
                   emails=item.get("emails"), telefoons=item.get("phones"))
    elif soort == "organization":
        uit.update(adres=item.get("address"))
    elif soort == "lead":
        uit.update(waarde=item.get("value"), valuta=item.get("currency"),
                   persoon=(item.get("person") or {}).get("name"),
                   organisatie=(item.get("organization") or {}).get("name"),
                   gearchiveerd=item.get("is_archived"))
    return uit


# ---- Kleine hulpjes voor de parameters ------------------------------------
def _int(a: dict, naam: str, verplicht=False):
    v = a.get(naam)
    if v in (None, ""):
        if verplicht:
            raise Geweigerd(f"'{naam}' is verplicht")
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        raise Geweigerd(f"'{naam}' moet een geheel getal zijn") from None


def _limiet(a: dict, standaard=25, maximum=200) -> int:
    v = _int(a, "limiet")
    return max(1, min(maximum, v or standaard))


def _tekst(a: dict, naam: str, verplicht=False) -> str | None:
    v = a.get(naam)
    if v in (None, ""):
        if verplicht:
            raise Geweigerd(f"'{naam}' is verplicht")
        return None
    return str(v).strip()


def _term(a: dict) -> str:
    t = _tekst(a, "term", True)
    if len(t) < 2:
        raise Geweigerd("'term' moet minstens 2 tekens hebben")
    return t


def _bijwerkvelden(a: dict, toegestaan: dict) -> dict:
    """Parameters (Nederlandse namen) -> Pipedrive-velden; alleen wat is opgegeven."""
    uit = {}
    for ons, hun in toegestaan.items():
        if ons in a and a[ons] is not None and a[ons] != "":
            uit[hun] = a[ons]
    return uit


# ---- Het gereedschap ------------------------------------------------------
def firmas() -> dict:
    """De vijf firma's, met wat Pipedrive er zelf over zegt."""
    rijen = []
    beschikbaar = tokens()
    for s, n in FIRMAS.items():
        rij = {"firma": s, "naam": n, "token_aanwezig": s in beschikbaar}
        if s in beschikbaar:
            try:
                ik = _ik(s)
                rij.update(pipedrive_bedrijf=ik.get("company_name"),
                           domein=ik.get("company_domain"),
                           token_gebruiker=ik.get("name"))
            except Exception as e:  # noqa: BLE001
                rij["fout"] = f"{type(e).__name__}: {e}"
        rijen.append(rij)
    return {"firmas": rijen,
            "regel": "Elke opdracht hoort bij precies een firma. Vraag het de "
                     "gebruiker als het niet in de opdracht staat."}


def overzicht(sleutel, a) -> dict:
    fases = sorted(_fases(sleutel).values(), key=lambda s: (s.get("pipeline_id"), s.get("order_nr") or 0))
    pijplijnen = []
    for p in sorted(_pijplijnen(sleutel).values(), key=lambda p: p.get("order_nr") or 0):
        pijplijnen.append({"id": p["id"], "naam": p.get("name"), "actief": p.get("active"),
                           "fases": [{"id": s["id"], "naam": s.get("name"),
                                      "kans_pct": s.get("deal_probability")}
                                     for s in fases if s.get("pipeline_id") == p["id"]]})
    gebruikers = [{"id": u["id"], "naam": u.get("name"), "email": u.get("email")}
                  for u in _gebruikers(sleutel).values() if u.get("active_flag")]
    types = [{"sleutel": t.get("key_string"), "naam": t.get("name")}
             for t in _activiteittypes(sleutel) if t.get("active_flag", True)]
    samenvatting = {}
    try:
        s = _roep(sleutel, "GET", "/deals/summary", {"status": "open"}).get("data") or {}
        samenvatting = {"open_deals": s.get("total_count"),
                        "open_waarde": {k: v.get("value") for k, v in (s.get("values_total") or {}).items()}}
    except PipedriveFout as e:
        samenvatting = {"fout": str(e)}
    ik = _ik(sleutel)
    return {"pipedrive_bedrijf": ik.get("company_name"), "domein": ik.get("company_domain"),
            "pijplijnen": pijplijnen, "gebruikers": gebruikers,
            "activiteittypes": types, "open": samenvatting}


def velden(sleutel, a) -> dict:
    soort = _tekst(a, "soort") or "deal"
    if soort not in _VELDPAD:
        raise Geweigerd("soort moet deal, person of organization zijn")
    uit = []
    for f in _eigen_velden(sleutel, soort):
        rij = {"naam": f.get("name"), "sleutel": f.get("key"), "type": f.get("field_type"),
               "verplicht": bool(f.get("mandatory_flag"))}
        if f.get("options"):
            rij["keuzes"] = [o.get("label") for o in f["options"]]
        uit.append(rij)
    return {"soort": soort, "eigen_velden": uit,
            "toelichting": "Gebruik bij aanmaken/bijwerken de parameter 'velden' "
                           "met {veldnaam: waarde}; keuzevelden accepteren het label."}


def zoeken(sleutel, a) -> dict:
    term = _term(a)
    soorten = _tekst(a, "soorten")
    if soorten:
        toegestaan = {"deal", "person", "organization", "lead"}
        lijst = [s.strip() for s in soorten.split(",") if s.strip()]
        if not set(lijst) <= toegestaan:
            raise Geweigerd("soorten: combinatie van deal, person, organization, lead")
        soorten = ",".join(lijst)
    r = _roep(sleutel, "GET", "/itemSearch",
              {"term": term, "item_types": soorten, "limit": _limiet(a, 20, 100),
               "exact_match": 1 if a.get("exact") else None})
    items = (r.get("data") or {}).get("items") or []
    return {"term": term, "aantal": len(items),
            "resultaten": [_zoekitem(sleutel, it) for it in items]}


_DEAL_STATUS = {"open", "won", "lost", "deleted", "all_not_deleted"}
_DEAL_SORT = {"update_time", "add_time", "title", "value", "expected_close_date",
              "stage_change_time", "next_activity_date", "won_time", "lost_time", "id"}


def deals(sleutel, a) -> dict:
    status = _tekst(a, "status") or "open"
    if status == "alle":
        status = "all_not_deleted"
    if status not in _DEAL_STATUS:
        raise Geweigerd("status: open, won, lost of alle")
    sorteer = _tekst(a, "sorteer") or "update_time"
    if sorteer not in _DEAL_SORT:
        raise Geweigerd("sorteer: " + ", ".join(sorted(_DEAL_SORT)))
    richting = "ASC" if (a.get("oplopend")) else "DESC"
    maximum = _limiet(a, 25, 500)
    pipeline_id, stage_id, user_id = _int(a, "pijplijn_id"), _int(a, "fase_id"), _int(a, "eigenaar_id")
    term = _tekst(a, "term")
    if term:
        if len(term) < 2:
            raise Geweigerd("'term' moet minstens 2 tekens hebben")
        r = _roep(sleutel, "GET", "/deals/search",
                  {"term": term, "status": status if status in ("open", "won", "lost") else None,
                   "limit": min(maximum, 100)})
        items = (r.get("data") or {}).get("items") or []
        rijen = [_zoekitem(sleutel, it) for it in items]
        if pipeline_id or stage_id:
            fases = _fases(sleutel)
            rijen = [x for x in rijen
                     if (not stage_id or (x.get("fase") == fases.get(stage_id, {}).get("name")))
                     and (not pipeline_id or any(s.get("name") == x.get("fase") and s.get("pipeline_id") == pipeline_id
                                                 for s in fases.values()))]
        return {"aantal": len(rijen), "deals": rijen}
    if pipeline_id:
        rijen, meer = _alles(sleutel, f"/pipelines/{pipeline_id}/deals",
                             {"stage_id": stage_id, "user_id": user_id,
                              "everyone": 1 if not user_id else None}, maximum)
        if status != "all_not_deleted":
            rijen = [d for d in rijen if d.get("status") == status]
    else:
        rijen, meer = _alles(sleutel, "/deals",
                             {"status": status, "stage_id": stage_id, "user_id": user_id,
                              "sort": f"{sorteer} {richting}"}, maximum)
    return {"aantal": len(rijen), "meer_beschikbaar": meer,
            "deals": [_deal_kort(sleutel, d) for d in rijen]}


def deal(sleutel, a) -> dict:
    did = _int(a, "id", True)
    d = _roep(sleutel, "GET", f"/deals/{did}").get("data")
    if not d:
        raise Geweigerd(f"Deal {did} bestaat niet bij {FIRMAS[sleutel]}.")
    producten = _roep(sleutel, "GET", f"/deals/{did}/products", {"limit": 100}).get("data") or []
    notities = _roep(sleutel, "GET", "/notes", {"deal_id": did, "limit": 5,
                                                "sort": "add_time DESC"}).get("data") or []
    acts = _roep(sleutel, "GET", f"/deals/{did}/activities", {"limit": 10, "done": 0}).get("data") or []
    uit = _deal_kort(sleutel, d)
    p = d.get("person_id") if isinstance(d.get("person_id"), dict) else None
    uit.update({
        "link": _link(sleutel, "deal", did),
        "kans_pct": d.get("probability"),
        "aangemaakt": d.get("add_time"), "gewonnen_op": d.get("won_time"),
        "verloren_op": d.get("lost_time"), "verliesreden": d.get("lost_reason"),
        "laatste_fasewissel": d.get("stage_change_time"),
        "contact": {"emails": _contact(p.get("email")), "telefoons": _contact(p.get("phone"))} if p else None,
        "activiteiten": {"open": d.get("undone_activities_count"), "gedaan": d.get("done_activities_count")},
        "producten": [{"naam": x.get("name"), "aantal": x.get("quantity"),
                       "prijs": x.get("item_price"), "som": x.get("sum")} for x in producten],
        "eigen_velden": _eigen_velden_uit(sleutel, "deal", d),
        "laatste_notities": [_notitie_kort(n) for n in notities],
        "open_activiteiten": [_activiteit_kort(x) for x in acts],
    })
    return uit


_DEAL_IN = {"titel": "title", "waarde": "value", "valuta": "currency",
            "persoon_id": "person_id", "organisatie_id": "org_id",
            "pijplijn_id": "pipeline_id", "fase_id": "stage_id", "eigenaar_id": "user_id",
            "status": "status", "verwachte_sluiting": "expected_close_date",
            "kans_pct": "probability", "verliesreden": "lost_reason"}


def _deal_body(sleutel, a) -> dict:
    body = _bijwerkvelden(a, _DEAL_IN)
    if "status" in body and body["status"] not in ("open", "won", "lost"):
        raise Geweigerd("status: open, won of lost")
    body.update(_velden_in(sleutel, "deal", a.get("velden")))
    return body


def deal_aanmaken(sleutel, a) -> dict:
    _tekst(a, "titel", True)
    body = _deal_body(sleutel, a)
    d = _roep(sleutel, "POST", "/deals", body=body).get("data") or {}
    return {"aangemaakt": True, "deal": _deal_kort(sleutel, d), "link": _link(sleutel, "deal", d.get("id"))}


def deal_bijwerken(sleutel, a) -> dict:
    did = _int(a, "id", True)
    body = _deal_body(sleutel, a)
    if not body:
        raise Geweigerd("Niets om bij te werken: geef minstens een veld op.")
    d = _roep(sleutel, "PUT", f"/deals/{did}", body=body).get("data") or {}
    return {"bijgewerkt": sorted(body), "deal": _deal_kort(sleutel, d),
            "link": _link(sleutel, "deal", did)}


def deal_geschiedenis(sleutel, a) -> dict:
    did = _int(a, "id", True)
    maximum = _limiet(a, 30, 200)
    rijen, meer = _alles(sleutel, f"/deals/{did}/flow", {}, maximum)
    per_key = {f["key"]: f for f in _velden(sleutel, "deal")}
    uit = []
    for r in rijen:
        soort, d = r.get("object"), r.get("data") or {}
        rij = {"wanneer": r.get("timestamp"), "soort": soort}
        if soort == "dealChange":
            f = per_key.get(d.get("field_key")) or {}
            veld = f.get("name") or d.get("field_key")
            oud, nieuw = d.get("old_value"), d.get("new_value")
            if d.get("field_key") == "stage_id":
                oud, nieuw = _naam_fase(sleutel, _int({"x": oud}, "x")), _naam_fase(sleutel, _int({"x": nieuw}, "x"))
            elif d.get("field_key") == "user_id":
                oud, nieuw = _naam_gebruiker(sleutel, _int({"x": oud}, "x")), _naam_gebruiker(sleutel, _int({"x": nieuw}, "x"))
            elif f:
                oud, nieuw = _waarde_leesbaar(f, oud), _waarde_leesbaar(f, nieuw)
            rij.update(veld=veld, van=oud, naar=nieuw, door=_naam_gebruiker(sleutel, d.get("user_id")))
        elif soort == "note":
            rij.update(tekst=_platte_tekst(d.get("content")), door=_naam_gebruiker(sleutel, d.get("user_id")))
        elif soort == "activity":
            rij.update(onderwerp=d.get("subject"), type=d.get("type"), gedaan=bool(d.get("done")),
                       datum=d.get("due_date"))
        elif soort == "file":
            rij.update(bestand=d.get("file_name") or d.get("name"))
        elif soort == "mailMessage":
            rij.update(onderwerp=d.get("subject"))
        else:
            rij.update(samenvatting=str(d)[:200])
        uit.append(rij)
    return {"deal_id": did, "aantal": len(uit), "meer_beschikbaar": meer, "verloop": uit}


def personen(sleutel, a) -> dict:
    term = _tekst(a, "term")
    maximum = _limiet(a, 25, 200)
    if term:
        if len(term) < 2:
            raise Geweigerd("'term' moet minstens 2 tekens hebben")
        r = _roep(sleutel, "GET", "/persons/search",
                  {"term": term, "organization_id": _int(a, "organisatie_id"),
                   "limit": min(maximum, 100)})
        items = (r.get("data") or {}).get("items") or []
        return {"aantal": len(items), "personen": [_zoekitem(sleutel, it) for it in items]}
    rijen, meer = _alles(sleutel, "/persons", {"sort": "update_time DESC",
                                               "user_id": _int(a, "eigenaar_id")}, maximum)
    return {"aantal": len(rijen), "meer_beschikbaar": meer,
            "personen": [_persoon_kort(sleutel, p) for p in rijen]}


def persoon(sleutel, a) -> dict:
    pid = _int(a, "id", True)
    p = _roep(sleutel, "GET", f"/persons/{pid}").get("data")
    if not p:
        raise Geweigerd(f"Persoon {pid} bestaat niet bij {FIRMAS[sleutel]}.")
    dls = _roep(sleutel, "GET", f"/persons/{pid}/deals",
                {"status": "all_not_deleted", "limit": 20}).get("data") or []
    notities = _roep(sleutel, "GET", "/notes", {"person_id": pid, "limit": 5,
                                                "sort": "add_time DESC"}).get("data") or []
    uit = _persoon_kort(sleutel, p)
    uit.update({"link": _link(sleutel, "person", pid), "aangemaakt": p.get("add_time"),
                "deals_gewonnen": p.get("won_deals_count"), "deals_verloren": p.get("lost_deals_count"),
                "laatste_activiteit": p.get("last_activity_date"),
                "eigen_velden": _eigen_velden_uit(sleutel, "person", p),
                "deals": [_deal_kort(sleutel, d) for d in dls],
                "laatste_notities": [_notitie_kort(n) for n in notities]})
    return uit


_PERSOON_IN = {"naam": "name", "organisatie_id": "org_id", "eigenaar_id": "owner_id"}


def _persoon_body(sleutel, a) -> dict:
    body = _bijwerkvelden(a, _PERSOON_IN)
    if a.get("email"):
        emails = a["email"] if isinstance(a["email"], list) else [a["email"]]
        body["email"] = [{"value": str(e).strip(), "primary": i == 0, "label": "work"}
                         for i, e in enumerate(emails) if str(e).strip()]
    if a.get("telefoon"):
        tels = a["telefoon"] if isinstance(a["telefoon"], list) else [a["telefoon"]]
        body["phone"] = [{"value": str(t).strip(), "primary": i == 0, "label": "work"}
                         for i, t in enumerate(tels) if str(t).strip()]
    body.update(_velden_in(sleutel, "person", a.get("velden")))
    return body


def persoon_aanmaken(sleutel, a) -> dict:
    _tekst(a, "naam", True)
    p = _roep(sleutel, "POST", "/persons", body=_persoon_body(sleutel, a)).get("data") or {}
    return {"aangemaakt": True, "persoon": _persoon_kort(sleutel, p),
            "link": _link(sleutel, "person", p.get("id"))}


def persoon_bijwerken(sleutel, a) -> dict:
    pid = _int(a, "id", True)
    body = _persoon_body(sleutel, a)
    if not body:
        raise Geweigerd("Niets om bij te werken: geef minstens een veld op.")
    p = _roep(sleutel, "PUT", f"/persons/{pid}", body=body).get("data") or {}
    return {"bijgewerkt": sorted(body), "persoon": _persoon_kort(sleutel, p),
            "link": _link(sleutel, "person", pid)}


def organisaties(sleutel, a) -> dict:
    term = _tekst(a, "term")
    maximum = _limiet(a, 25, 200)
    if term:
        if len(term) < 2:
            raise Geweigerd("'term' moet minstens 2 tekens hebben")
        r = _roep(sleutel, "GET", "/organizations/search", {"term": term, "limit": min(maximum, 100)})
        items = (r.get("data") or {}).get("items") or []
        return {"aantal": len(items), "organisaties": [_zoekitem(sleutel, it) for it in items]}
    rijen, meer = _alles(sleutel, "/organizations", {"sort": "update_time DESC",
                                                     "user_id": _int(a, "eigenaar_id")}, maximum)
    return {"aantal": len(rijen), "meer_beschikbaar": meer,
            "organisaties": [_org_kort(sleutel, o) for o in rijen]}


def organisatie(sleutel, a) -> dict:
    oid = _int(a, "id", True)
    o = _roep(sleutel, "GET", f"/organizations/{oid}").get("data")
    if not o:
        raise Geweigerd(f"Organisatie {oid} bestaat niet bij {FIRMAS[sleutel]}.")
    mensen = _roep(sleutel, "GET", f"/organizations/{oid}/persons", {"limit": 50}).get("data") or []
    dls = _roep(sleutel, "GET", f"/organizations/{oid}/deals",
                {"status": "all_not_deleted", "limit": 20}).get("data") or []
    notities = _roep(sleutel, "GET", "/notes", {"org_id": oid, "limit": 5,
                                                "sort": "add_time DESC"}).get("data") or []
    uit = _org_kort(sleutel, o)
    uit.update({"link": _link(sleutel, "organization", oid), "aangemaakt": o.get("add_time"),
                "deals_gewonnen": o.get("won_deals_count"), "deals_verloren": o.get("lost_deals_count"),
                "eigen_velden": _eigen_velden_uit(sleutel, "organization", o),
                "personen": [_persoon_kort(sleutel, p) for p in mensen],
                "deals": [_deal_kort(sleutel, d) for d in dls],
                "laatste_notities": [_notitie_kort(n) for n in notities]})
    return uit


_ORG_IN = {"naam": "name", "adres": "address", "eigenaar_id": "owner_id"}


def organisatie_aanmaken(sleutel, a) -> dict:
    _tekst(a, "naam", True)
    body = _bijwerkvelden(a, _ORG_IN)
    body.update(_velden_in(sleutel, "organization", a.get("velden")))
    o = _roep(sleutel, "POST", "/organizations", body=body).get("data") or {}
    return {"aangemaakt": True, "organisatie": _org_kort(sleutel, o),
            "link": _link(sleutel, "organization", o.get("id"))}


def organisatie_bijwerken(sleutel, a) -> dict:
    oid = _int(a, "id", True)
    body = _bijwerkvelden(a, _ORG_IN)
    body.update(_velden_in(sleutel, "organization", a.get("velden")))
    if not body:
        raise Geweigerd("Niets om bij te werken: geef minstens een veld op.")
    o = _roep(sleutel, "PUT", f"/organizations/{oid}", body=body).get("data") or {}
    return {"bijgewerkt": sorted(body), "organisatie": _org_kort(sleutel, o),
            "link": _link(sleutel, "organization", oid)}


def activiteiten(sleutel, a) -> dict:
    maximum = _limiet(a, 25, 200)
    gedaan = a.get("gedaan")
    done = None if gedaan is None else (1 if gedaan else 0)
    deal_id, persoon_id, org_id = _int(a, "deal_id"), _int(a, "persoon_id"), _int(a, "organisatie_id")
    if deal_id:
        rijen, meer = _alles(sleutel, f"/deals/{deal_id}/activities", {"done": done}, maximum)
    elif persoon_id:
        rijen, meer = _alles(sleutel, f"/persons/{persoon_id}/activities", {"done": done}, maximum)
    elif org_id:
        rijen, meer = _alles(sleutel, f"/organizations/{org_id}/activities", {"done": done}, maximum)
    else:
        eigenaar = _int(a, "eigenaar_id")
        rijen, meer = _alles(sleutel, "/activities",
                             {"user_id": eigenaar if eigenaar else 0, "done": done,
                              "type": _tekst(a, "type"),
                              "start_date": _tekst(a, "van"), "end_date": _tekst(a, "tot")}, maximum)
    return {"aantal": len(rijen), "meer_beschikbaar": meer,
            "activiteiten": [_activiteit_kort(x) for x in rijen]}


_ACT_IN = {"onderwerp": "subject", "type": "type", "datum": "due_date", "tijd_utc": "due_time",
           "duur": "duration", "deal_id": "deal_id", "persoon_id": "person_id",
           "organisatie_id": "org_id", "lead_id": "lead_id", "eigenaar_id": "user_id",
           "notitie": "note", "locatie": "location"}


def _act_body(sleutel, a) -> dict:
    body = _bijwerkvelden(a, _ACT_IN)
    if "type" in body:
        sleutels = {t.get("key_string") for t in _activiteittypes(sleutel)}
        if body["type"] not in sleutels:
            raise Geweigerd("Onbekend activiteittype. Keuzes: " + ", ".join(sorted(s for s in sleutels if s)))
    if a.get("gedaan") is not None:
        body["done"] = 1 if a["gedaan"] else 0
    return body


def activiteit_aanmaken(sleutel, a) -> dict:
    _tekst(a, "onderwerp", True)
    _tekst(a, "datum", True)
    body = _act_body(sleutel, a)
    body.setdefault("type", "task")
    x = _roep(sleutel, "POST", "/activities", body=body).get("data") or {}
    return {"aangemaakt": True, "activiteit": _activiteit_kort(x)}


def activiteit_bijwerken(sleutel, a) -> dict:
    aid = _int(a, "id", True)
    body = _act_body(sleutel, a)
    if not body:
        raise Geweigerd("Niets om bij te werken: geef minstens een veld op (bv. gedaan=true).")
    x = _roep(sleutel, "PUT", f"/activities/{aid}", body=body).get("data") or {}
    return {"bijgewerkt": sorted(body), "activiteit": _activiteit_kort(x)}


def notities(sleutel, a) -> dict:
    maximum = _limiet(a, 20, 200)
    params = {"deal_id": _int(a, "deal_id"), "person_id": _int(a, "persoon_id"),
              "org_id": _int(a, "organisatie_id"), "lead_id": _tekst(a, "lead_id"),
              "sort": "add_time DESC"}
    if not any(params[k] for k in ("deal_id", "person_id", "org_id", "lead_id")):
        raise Geweigerd("Geef deal_id, persoon_id, organisatie_id of lead_id op.")
    rijen, meer = _alles(sleutel, "/notes", params, maximum)
    return {"aantal": len(rijen), "meer_beschikbaar": meer,
            "notities": [_notitie_kort(n) for n in rijen]}


def notitie_aanmaken(sleutel, a) -> dict:
    tekst = _tekst(a, "tekst", True)
    body = {"content": html.escape(tekst).replace("\n", "<br>"),
            "deal_id": _int(a, "deal_id"), "person_id": _int(a, "persoon_id"),
            "org_id": _int(a, "organisatie_id"), "lead_id": _tekst(a, "lead_id")}
    body = {k: v for k, v in body.items() if v not in (None, "")}
    if len(body) < 2:
        raise Geweigerd("Een notitie hoort bij een deal, persoon, organisatie of lead.")
    if a.get("vastpinnen") and body.get("deal_id"):
        body["pinned_to_deal_flag"] = 1
    n = _roep(sleutel, "POST", "/notes", body=body).get("data") or {}
    return {"aangemaakt": True, "notitie": _notitie_kort(n)}


def leads(sleutel, a) -> dict:
    maximum = _limiet(a, 25, 200)
    term = _tekst(a, "term")
    if term:
        if len(term) < 2:
            raise Geweigerd("'term' moet minstens 2 tekens hebben")
        r = _roep(sleutel, "GET", "/leads/search", {"term": term, "limit": min(maximum, 100)})
        items = (r.get("data") or {}).get("items") or []
        return {"aantal": len(items), "leads": [_zoekitem(sleutel, it) for it in items]}
    archief = "all" if a.get("gearchiveerd") is True else ("archived" if a.get("gearchiveerd") == "alleen" else "not_archived")
    rijen, meer = _alles(sleutel, "/leads", {"archived_status": archief, "sort": "update_time DESC",
                                             "owner_id": _int(a, "eigenaar_id")}, maximum)
    return {"aantal": len(rijen), "meer_beschikbaar": meer,
            "leads": [_lead_kort(sleutel, x) for x in rijen]}


def lead_aanmaken(sleutel, a) -> dict:
    titel = _tekst(a, "titel", True)
    pid, oid = _int(a, "persoon_id"), _int(a, "organisatie_id")
    if not pid and not oid:
        raise Geweigerd("Een lead hoort bij een persoon of een organisatie: geef persoon_id of organisatie_id.")
    body = {"title": titel, "person_id": pid, "organization_id": oid,
            "owner_id": _int(a, "eigenaar_id"),
            "expected_close_date": _tekst(a, "verwachte_sluiting")}
    if a.get("waarde") not in (None, ""):
        body["value"] = {"amount": float(a["waarde"]), "currency": _tekst(a, "valuta") or "EUR"}
    body = {k: v for k, v in body.items() if v not in (None, "")}
    x = _roep(sleutel, "POST", "/leads", body=body).get("data") or {}
    return {"aangemaakt": True, "lead": _lead_kort(sleutel, x)}


UITVOERING = {
    "overzicht": overzicht, "velden": velden, "zoeken": zoeken,
    "deals": deals, "deal": deal, "deal_aanmaken": deal_aanmaken,
    "deal_bijwerken": deal_bijwerken, "deal_geschiedenis": deal_geschiedenis,
    "personen": personen, "persoon": persoon, "persoon_aanmaken": persoon_aanmaken,
    "persoon_bijwerken": persoon_bijwerken,
    "organisaties": organisaties, "organisatie": organisatie,
    "organisatie_aanmaken": organisatie_aanmaken, "organisatie_bijwerken": organisatie_bijwerken,
    "activiteiten": activiteiten, "activiteit_aanmaken": activiteit_aanmaken,
    "activiteit_bijwerken": activiteit_bijwerken,
    "notities": notities, "notitie_aanmaken": notitie_aanmaken,
    "leads": leads, "lead_aanmaken": lead_aanmaken,
}
SCHRIJVEND = {n for n in UITVOERING if n.endswith(("_aanmaken", "_bijwerken"))}


def voer_uit(naam: str, a: dict, mag_schrijven: bool) -> dict:
    """Een gereedschap uitvoeren. De firma-poort zit hier, voor alles behalve
    'firmas'; het antwoord noemt de firma altijd als eerste sleutel."""
    a = a if isinstance(a, dict) else {}
    if naam == "firmas":
        return firmas()
    fn = UITVOERING.get(naam)
    if fn is None:
        raise Geweigerd(f"Onbekend gereedschap: {naam}")
    sleutel = firma_kiezen(a)
    if naam in SCHRIJVEND and not mag_schrijven:
        raise Geweigerd("Alleen lezen: schrijven in Pipedrive vereist de groep "
                        "pipedrive-editors of admin.")
    uit = fn(sleutel, a)
    kop = {"firma": f"{FIRMAS[sleutel]} ({sleutel})"}
    return {**kop, **uit} if isinstance(uit, dict) else {**kop, "resultaat": uit}

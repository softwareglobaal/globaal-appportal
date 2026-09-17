"""Herhaalbaarheid van een agentronde (rapport "Herhaalbare agentfabriek", 17-09-2026).

Vier dingen, allemaal gewone code, geen model:
  1. masker_rrn      — rijksregisternummers verdwijnen uit alles wat naar het model of een log gaat;
  2. invoerhash      — één hash over alle invoer van een ronde (bronnen, dossier, instructies, schema, model);
                       zelfde hash = zelfde plan, zonder nieuwe modelaanroep (plan-cache);
  3. valideer_*      — bereik, vorm en toegelaten waarden vóór er iets in het dossier geschreven wordt;
  4. RunRecord/slot  — een regel per ronde die alleen groeit, en een slot met vervaltijd tegen dubbele rondes.
"""
import fcntl
import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(os.path.expanduser("~/appportal/mijnagents-data"))

# ---------------------------------------------------------------- 1. masker ---
# Belgisch rijksregisternummer: JJ.MM.DD-XXX.CC in alle gangbare schrijfwijzen,
# ook zonder scheidingstekens (11 cijfers). Het controlegetal (mod 97) bevestigt.
_RRN = re.compile(r"(?<!\d)(\d{2})[.\s]?(\d{2})[.\s]?(\d{2})[-.\s]?(\d{3})[.\s]?(\d{2})(?!\d)")


def _is_rrn(jj, mm, dd, xxx, cc):
    basis = int(jj + mm + dd + xxx)
    controle = int(cc)
    return (97 - basis % 97) == controle or (97 - (2000000000 + basis) % 97) == controle


def masker_rrn(tekst):
    """Vervangt elk geldig rijksregisternummer door [RRN]. Andere getallen blijven staan."""
    if not isinstance(tekst, str) or not tekst:
        return tekst
    def vervang(m):
        return "[RRN]" if _is_rrn(*m.groups()) else m.group(0)
    return _RRN.sub(vervang, tekst)


def masker_diep(obj):
    """Zelfde masker, maar door lijsten en dicts heen (voor het prompt-JSON en logdetails)."""
    if isinstance(obj, str):
        return masker_rrn(obj)
    if isinstance(obj, list):
        return [masker_diep(x) for x in obj]
    if isinstance(obj, dict):
        return {k: masker_diep(v) for k, v in obj.items()}
    return obj


# ------------------------------------------------------------ 2. invoerhash ---
def hash_van(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def invoerhash(delen: dict) -> tuple[str, dict]:
    """Eén hash over alle delen, plus de hash per deel (zodat een afwijking verklaarbaar is)."""
    per_deel = {k: hash_van(v) for k, v in delen.items()}
    return hash_van(per_deel), per_deel


def plan_cache_pad(agent: str, deal_id, hash_: str) -> Path:
    return DATA / f"{agent}-plannen" / str(deal_id) / f"{hash_}.json"


def plan_uit_cache(agent, deal_id, hash_):
    p = plan_cache_pad(agent, deal_id, hash_)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return None
    return None


def plan_in_cache(agent, deal_id, hash_, plan, meta):
    p = plan_cache_pad(agent, deal_id, hash_)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"plan": plan, "meta": meta}, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------- 3. validatie ---
VERBODEN_VELDEN = {"capa_key_code", "project_capakey", "oppervlakte_m2", "project_oppervlakte_terrein",
                   "pipedrive_deal_id", "deal_id", "project_nummer", "datum_vandaag"}
BEDRAG_HINTS = ("bedrag", "_euro", "ereloon_voorstudie", "ereloon_regularisatie", "prijs_", "budget_bedrag")
PERCENT_HINTS = ("percentage", "_pct")


def normaliseer_bedrag(waarde: str):
    """'150000' / '150.000' / '150 000,5' / '150000.00' -> '150.000,00'. None als het geen bedrag is."""
    s = str(waarde).strip().replace("€", "").replace("EUR", "").replace("euro", "").strip()
    s = re.sub(r"\s", "", s)
    if not re.fullmatch(r"[\d.,]+", s):
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") == 1 and len(s.split(".")[1]) == 2:
        pass  # 150000.00
    else:
        s = s.replace(".", "")
    try:
        bedrag = float(s)
    except ValueError:
        return None
    if bedrag < 0 or bedrag > 100_000_000:
        return None
    heel, cent = f"{bedrag:.2f}".split(".")
    heel = f"{int(heel):,}".replace(",", ".")
    return f"{heel},{cent}"


def normaliseer_percentage(waarde: str):
    s = str(waarde).strip().replace("%", "").replace(",", ".").strip()
    try:
        p = float(s)
    except ValueError:
        return None
    if p < 0 or p > 100:
        return None
    return str(int(p)) if p == int(p) else f"{p:g}".replace(".", ",")


def valideer_gegevens(velden: dict, bron: str, toegelaten: set | None = None):
    """Geeft (goed, geweigerd): goed = {veld: genormaliseerde waarde}, geweigerd = [(veld, waarde, reden)]."""
    goed, geweigerd = {}, []
    if len((bron or "").strip()) < 8:
        return {}, [(k, v, "geen bron") for k, v in velden.items()]
    for veld, waarde in (velden or {}).items():
        veld = str(veld).strip()
        w = waarde.strip() if isinstance(waarde, str) else waarde
        if w in ("", None):
            continue
        if "rijksregister" in veld:
            geweigerd.append((veld, "[RRN]", "rijksregisternummers vult alleen het systeem in, uit de klantmail (D18)"))
            continue
        if veld in VERBODEN_VELDEN:
            geweigerd.append((veld, w, "wordt door het systeem bepaald, nooit door het model"))
            continue
        if toegelaten is not None and veld not in toegelaten:
            geweigerd.append((veld, w, "geen veld van dit contracttype (veldenschema.master)"))
            continue
        if not isinstance(w, str):
            geweigerd.append((veld, w, "geen tekst"))
            continue
        if any(h in veld for h in PERCENT_HINTS):
            n = normaliseer_percentage(w)
            if n is None:
                geweigerd.append((veld, w, "geen percentage tussen 0 en 100"))
                continue
            w = n
        elif any(h in veld for h in BEDRAG_HINTS):
            n = normaliseer_bedrag(w)
            if n is None:
                geweigerd.append((veld, w, "geen bedrag in euro"))
                continue
            w = n
        elif veld.endswith("_email"):
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", w, re.I):
                geweigerd.append((veld, w, "geen e-mailadres"))
                continue
        elif veld.endswith("_tel"):
            if len(re.sub(r"\D", "", w)) < 8:
                geweigerd.append((veld, w, "geen telefoonnummer"))
                continue
        if len(w) > 6000:
            geweigerd.append((veld, w[:40] + "…", "langer dan 6000 tekens"))
            continue
        if masker_rrn(w) != w:
            geweigerd.append((veld, "[RRN]", "bevat een rijksregisternummer"))
            continue
        goed[veld] = w
    return goed, geweigerd


def valideer_keuzes(keuzes: dict, opties_per_veld: dict, vrije_velden: set):
    """Keuzes tegen de toegelaten waarden, hoofdletterongevoelig; vrije velden als tekst."""
    goed, geweigerd = {}, []
    for veld, waarde in (keuzes or {}).items():
        w = str(waarde).strip()
        if not w:
            continue
        if veld in vrije_velden:
            if masker_rrn(w) != w:
                geweigerd.append((veld, "[RRN]", "bevat een rijksregisternummer"))
            else:
                goed[veld] = w
            continue
        if veld not in opties_per_veld:
            geweigerd.append((veld, w, "geen keuzeveld van dit contracttype"))
            continue
        treffer = next((o for o in opties_per_veld[veld] if o.lower() == w.lower()), None)
        if treffer is None:
            geweigerd.append((veld, w, f"niet in {opties_per_veld[veld]}"))
            continue
        goed[veld] = treffer
    return goed, geweigerd


# ------------------------------------------------------------ 4. run-record ---
PRIJS_PER_MILJOEN_USD = {  # (in, uit) — prijslijst 17-09-2026, alleen voor kostenbewaking
    "claude-opus-5": (5, 25), "claude-sonnet-5": (2, 10), "claude-fable-5-1": (10, 50),
    "claude-haiku-4-5-20251001": (1, 5),
}
EUR_PER_USD = 1 / 1.1537


def kost_eur(model_id: str, tokens_in: int, tokens_uit: int):
    for naam, (pi, pu) in PRIJS_PER_MILJOEN_USD.items():
        if model_id and model_id.startswith(naam):
            return round((tokens_in * pi + tokens_uit * pu) / 1_000_000 * EUR_PER_USD, 4)
    return None


class RunRecord:
    """Eén regel per ronde per dossier, alleen toevoegen. Geen persoonsgegevens:
    alles gaat door het masker, en van de invoer staan alleen hashes in het record."""

    def __init__(self, agent: str, deal_id):
        self.record = {"run_id": uuid.uuid4().hex[:12], "agent": agent, "deal_id": deal_id,
                       "start": datetime.now(timezone.utc).isoformat(), "status": "bezig"}

    def zet(self, **velden):
        self.record.update(masker_diep(velden))
        return self

    def sluit(self, status="klaar"):
        self.record["status"] = status
        self.record["einde"] = datetime.now(timezone.utc).isoformat()
        pad = DATA / "runrecords" / f"{self.record['agent']}.jsonl"
        pad.parent.mkdir(parents=True, exist_ok=True)
        with open(pad, "a", encoding="utf-8") as f:
            f.write(json.dumps(self.record, ensure_ascii=False, default=str) + "\n")
        return self.record


# ------------------------------------------------------------------ 5. slot ---
class Slot:
    """Bestandsslot per agent met vervaltijd: cron start elke halve uur, en een
    ronde die nog loopt mag niet dubbel starten. Een slot ouder dan de vervaltijd
    wordt als vastgelopen beschouwd en overgenomen."""

    def __init__(self, agent: str, vervaltijd_s: int = 25 * 60):
        self.pad = Path(os.path.expanduser(f"~/agents/{agent}.lock"))
        self.vervaltijd = vervaltijd_s
        self.fh = None

    def __enter__(self):
        self.pad.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.pad, "a+")
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            leeftijd = time.time() - self.pad.stat().st_mtime
            if leeftijd < self.vervaltijd:
                raise RuntimeError(f"vorige ronde loopt nog ({int(leeftijd)} s); niet dubbel starten")
            fcntl.flock(self.fh, fcntl.LOCK_EX)  # vastgelopen: overnemen
        self.fh.seek(0); self.fh.truncate()
        self.fh.write(f"{os.getpid()} {datetime.now(timezone.utc).isoformat()}\n"); self.fh.flush()
        os.utime(self.pad, None)
        return self

    def __exit__(self, *a):
        try:
            fcntl.flock(self.fh, fcntl.LOCK_UN); self.fh.close()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------- 6. citaat ---
# Rapport deel 5: eerst letterlijk citeren, dan pas concluderen, en intrekken als
# het citaat niet in de bron staat. Het model geeft per gegevenspost een citaat;
# deze code zoekt het terug. Geen citaat of niet gevonden: het gegeven komt niet
# in het dossier. Wat wel gevonden is, krijgt het citaat in zijn herkomst.
def _plat(s: str) -> str:
    s = str(s or "").casefold()
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("…", "...")
    s = re.sub(r"[\s ]+", " ", s)
    return s.strip(" .,;:'\"«»()[]")


def bronteksten(bronnen_compact, notitielijst=None) -> list[tuple[str, str]]:
    """Alle tekst waarin een citaat mag staan, als (naam, tekst)."""
    uit = []
    b = bronnen_compact or {}
    for sleutel in ("salesmap", "projectmap"):
        for t in ((b.get(sleutel) or {}).get("teksten") or []):
            uit.append((f"{sleutel}: {t.get('bestand', '?')}", t.get("tekst") or ""))
    for m in b.get("mails") or []:
        uit.append((f"mail {str(m.get('datum', ''))[:10]} {m.get('onderwerp', '')}", m.get("tekst") or ""))
    for k in b.get("klaargezet") or []:
        uit.append((f"klaargezet: {k.get('titel', '')}", k.get("inhoud") or ""))
    for n in notitielijst or []:
        uit.append(("Pipedrive-notitie", n))
    return uit


def citaat_gevonden(citaat: str, teksten: list[tuple[str, str]]):
    """(gevonden, naam van de bron). Vergelijking zonder hoofdletters, dubbele
    spaties en aanhalingstekens; een citaat korter dan 12 tekens telt niet."""
    c = _plat(citaat)
    if len(c) < 12:
        return False, ""
    for naam, tekst in teksten:
        if c in _plat(tekst):
            return True, naam
    return False, ""


def pas_citaat_toe(post: dict, teksten: list[tuple[str, str]]):
    """Geeft (bron_met_citaat, reden_van_weigering). Leeg reden = in orde."""
    citaat = " ".join(str(post.get("citaat") or "").split()).strip()
    bron = " ".join(str(post.get("bron") or "").split()).strip()
    if not citaat:
        return bron, "geen letterlijk citaat uit de bron"
    gevonden, naam = citaat_gevonden(citaat, teksten)
    if not gevonden:
        return bron, f"citaat niet teruggevonden in de bronnen: «{citaat[:80]}»"
    return f"{bron} — citaat ({naam}): «{citaat[:300]}»", ""

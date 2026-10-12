"""Eén mapresolver en één volledigheidscontrole voor het Plaud-archief (verbeteropdracht v1.0, §5).

Selectie (plaud_haal_alles), schrijver (bouw_map), De Plaudwacht en de controle gebruiken alleen
dit bestand om te weten waar een opname staat en of ze compleet is. Altijd eerst op Plaud-id:

- Een hernoemde map blijft dezelfde opname (benaming, 25-09-2026).
- Twee opnames met dezelfde minuut en titel krijgen elk een eigen map; de tweede krijgt een
  suffix met het korte id, en ook die suffixmap wordt op id gecontroleerd.
- Eén id mag geen twee actieve archieflocaties hebben: dat is een conflict, geen keuze.

Compleet betekent: gesprek.json met het juiste id, een parsebaar transcript.json (lijst van
uitingen), een leesbaar transcript.md en een definitief audiobestand. Tijdelijke bestanden
(.deel, .tmp, .part) zijn nooit compleet. Een opname zonder transcript is gearchiveerd, maar
wacht op het transcript: dat is een eigen toestand, geen definitief einde.

Dropbox kan bestanden online-only bewaren (macOS markeert ze 'dataless'). Zo'n bestand bestaat;
het is geen reden om een opname leeg te noemen of opnieuw te downloaden.

Python 3.9-compatibel.
"""
import json
import os
import re
import stat as _stat
from pathlib import Path

import contract

AUDIO_EXT = (".ogg", ".mp3", ".m4a", ".opus", ".wav")
TIJDELIJK = (".deel", ".tmp", ".part")
SF_DATALESS = getattr(_stat, "SF_DATALESS", 0x40000000)
MIN_AUDIO = 1000


# ------------------------------------------------------------------ schrijven ---
def schrijf_atomair(pad, data):
    """Schrijf via een tijdelijk bestand naast het doel en os.replace: een lezer ziet het oude
    of het nieuwe bestand, nooit een half bestand."""
    pad = Path(pad)
    pad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pad.with_name(pad.name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data.encode("utf-8") if isinstance(data, str) else data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, pad)


def schrijf_json(pad, obj):
    schrijf_atomair(pad, json.dumps(obj, ensure_ascii=False, indent=1))


def lees_json(pad):
    try:
        with open(pad, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def is_dataless(pad):
    """Online-only in Dropbox (File Provider): het bestand bestaat, de inhoud staat in de cloud."""
    try:
        return bool(os.stat(pad).st_flags & SF_DATALESS)
    except (OSError, AttributeError):
        return False


# --------------------------------------------------------------------- index ---
def index(doel):
    """(plaud_id -> map, conflicten) over alle mappen met een gesprek.json.
    conflicten: plaud_id -> [mappen] als één id op meer dan één plaats staat."""
    gevonden = {}
    for g in Path(doel).glob("*/gesprek.json"):
        meta = lees_json(g) or {}
        try:
            pid = contract.canon_id(meta.get("plaud_id") or "")
        except contract.Herstel:
            continue
        gevonden.setdefault(pid, []).append(g.parent)
    idx = {pid: sorted(mappen)[0] for pid, mappen in gevonden.items()}
    conflicten = {pid: sorted(mappen) for pid, mappen in gevonden.items() if len(mappen) > 1}
    return idx, conflicten


class Index:
    """Index die tijdens een run bijgewerkt wordt na elke nieuwe opname."""

    def __init__(self, doel):
        self.doel = Path(doel)
        self.ids, self.conflicten = index(self.doel)

    def zet(self, pid, map_):
        self.ids[contract.canon_id(pid)] = Path(map_)

    def van(self, pid):
        return self.ids.get(contract.canon_id(pid))


def _id_van_map(map_):
    meta = lees_json(Path(map_) / "gesprek.json") or {}
    try:
        return contract.canon_id(meta.get("plaud_id") or "")
    except contract.Herstel:
        return None


def resolve(opname, doel, idx=None, naam=None):
    """De map van deze opname. Eerst op id (ook een hernoemde map); anders de gewone naam; is die
    van een andere opname, dan de naam met het korte id erachter, en ook die wordt op id gecontroleerd.

    Gooit Herstel bij een id-conflict (één id op twee plaatsen) of als zelfs de suffixmap van een
    ander id is."""
    import mapnaam as _mapnaam
    pid = contract.canon_id(opname.get("plaud_id") or opname.get("id") or "")
    if idx is None:
        idx = Index(doel)
    if pid in idx.conflicten:
        raise contract.Herstel(f"id {pid} staat in meer dan één map: " + "; ".join(p.name for p in idx.conflicten[pid]))
    gevonden = idx.van(pid)
    if gevonden is not None and gevonden.is_dir():
        return gevonden
    doel = Path(doel)
    gewoon = doel / (naam or _mapnaam.mapnaam(opname))
    suffix = doel / ("%s [%s]" % (naam, pid[3:9]) if naam else _mapnaam.mapnaam(opname, uniek=True))
    for kandidaat in (gewoon, suffix):
        ander = _id_van_map(kandidaat) if (kandidaat / "gesprek.json").exists() else None
        if ander in (None, pid):
            return kandidaat
    raise contract.Herstel(f"geen vrije map voor {pid}: de naam en de suffixnaam zijn van andere opnames")


# --------------------------------------------------------------- controleren ---
def _audio(map_):
    """(bestand, toestand): aanwezig | online_only | ontbreekt. Tijdelijke bestanden tellen niet."""
    for p in sorted(Path(map_).glob("opname.*")):
        if p.name.endswith(TIJDELIJK) or p.suffix.lower() not in AUDIO_EXT:
            continue
        if is_dataless(p):
            return p.name, "online_only"
        try:
            if p.stat().st_size >= MIN_AUDIO:
                return p.name, "aanwezig"
        except OSError:
            continue
    return "", "ontbreekt"


def _transcript(map_):
    """(toestand, uitingen): aanwezig | online_only | ongeldig | ontbreekt."""
    p = Path(map_) / "transcript.json"
    if not p.exists():
        return "ontbreekt", 0
    if is_dataless(p):
        return "online_only", None
    data = lees_json(p)
    if not isinstance(data, list) or not all(isinstance(u, dict) for u in data):
        return "ongeldig", 0
    return "aanwezig", len(data)


def toestand(map_, verwacht_id=None):
    """De echte toestand van een archiefmap:

        compleet              metadata, transcript.json, transcript.md en audio in orde
        wacht_op_transcript   gearchiveerd met audio, het transcript bestaat (nog) niet
        onvolledig            iets ontbreekt of is half geschreven (zie redenen)
        vreemd                gesprek.json hoort bij een ander id
        ontbreekt             geen map of geen gesprek.json
    """
    map_ = Path(map_)
    uit = {"map": str(map_), "staat": "ontbreekt", "audio": "ontbreekt", "transcript": "ontbreekt",
           "markdown": False, "redenen": []}
    g = map_ / "gesprek.json"
    if not map_.is_dir() or not g.exists():
        return uit
    meta = lees_json(g)
    if not isinstance(meta, dict):
        uit.update(staat="onvolledig", redenen=["gesprek.json niet leesbaar"]); return uit
    try:
        pid = contract.canon_id(meta.get("plaud_id") or "")
    except contract.Herstel:
        uit.update(staat="onvolledig", redenen=["gesprek.json zonder geldig plaud_id"]); return uit
    if verwacht_id and pid != contract.canon_id(verwacht_id):
        uit.update(staat="vreemd", redenen=[f"map hoort bij {pid}"]); return uit
    uit["plaud_id"] = pid
    uit["audio_bestand"], uit["audio"] = _audio(map_)
    uit["transcript"], uit["uitingen"] = _transcript(map_)
    md = map_ / "transcript.md"
    uit["markdown"] = md.exists() and (is_dataless(md) or md.stat().st_size > 0)
    if any(p.name.endswith(TIJDELIJK) for p in map_.iterdir()):
        uit["redenen"].append("tijdelijk bestand aanwezig (afgebroken schrijfactie)")
    if uit["audio"] == "ontbreekt":
        uit["redenen"].append("geen definitief audiobestand")
    if uit["transcript"] == "ongeldig":
        uit["redenen"].append("transcript.json niet parsebaar als lijst van uitingen")
    if uit["transcript"] in ("aanwezig", "online_only") and not uit["markdown"]:
        uit["redenen"].append("transcript.md ontbreekt (opnieuw te maken uit transcript.json)")
    if uit["audio"] in ("aanwezig", "online_only") and uit["transcript"] == "ontbreekt" and not uit["redenen"]:
        uit["staat"] = "wacht_op_transcript"
    elif uit["audio"] in ("aanwezig", "online_only") and uit["transcript"] in ("aanwezig", "online_only") and uit["markdown"] \
            and not uit["redenen"]:
        uit["staat"] = "compleet"
    else:
        uit["staat"] = "onvolledig"
    return uit


# ------------------------------------------------------------------ markdown ---
def _klok(ms):
    s, _ = divmod(int(ms or 0), 1000)
    u, s = divmod(s, 60)
    h, u = divmod(u, 60)
    return "%02d:%02d:%02d" % (h, u, s)


def markdown_tekst(uitingen, kop):
    regels = ["---"] + ["%s: %s" % (k, v) for k, v in kop.items()] + ["---", ""]
    for u in uitingen:
        spr = u.get("speaker") or u.get("original_speaker") or "Speaker ?"
        regels.append("[%s] %s: %s" % (_klok(u.get("start_time")), spr, (u.get("content") or "").strip()))
    return "\n".join(regels) + "\n"


def maak_markdown(map_):
    """Maak transcript.md opnieuw uit transcript.json en gesprek.json, zonder nieuwe download."""
    map_ = Path(map_)
    uitingen = lees_json(map_ / "transcript.json")
    meta = lees_json(map_ / "gesprek.json") or {}
    if not isinstance(uitingen, list):
        return False
    kop = {"plaud_id": meta.get("plaud_id", ""), "naam_in_plaud": meta.get("naam_in_plaud", ""),
           "start_utc": meta.get("start_utc", ""), "start_brussel": meta.get("start_brussel") or meta.get("start_belgisch", ""),
           "duur_minuten": meta.get("duur_minuten", ""), "uitingen": len(uitingen), "bron": "Plaud (block transaction)"}
    schrijf_atomair(map_ / "transcript.md", markdown_tekst(uitingen, kop))
    return True


def transcript_tekst(map_):
    """Leesbare tekst voor herkenning en levering, uit transcript.json (de bron)."""
    uitingen = lees_json(Path(map_) / "transcript.json")
    if not isinstance(uitingen, list):
        return ""
    return "\n".join("[%s] %s: %s" % (_klok(u.get("start_time")), u.get("speaker") or "Speaker ?",
                                      (u.get("content") or "").strip()) for u in uitingen)


def veilige_segment(naam):
    return re.sub(r'[/\\:*?"<>|\x00-\x1f]', " ", naam or "").strip()

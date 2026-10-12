"""Duurzame verwerkingsstappen per Plaud-id (verbeteropdracht v1.0, §3).

'Gearchiveerd' is niet 'volledig verwerkt'. Per opname bewaart De Plaudwacht in
mijnagents-data/plaud-staat/<plaud_id>.json:

    vingerafdruk   hash van wat de beslissing bepaalt; verandert die, dan wordt opnieuw beoordeeld
    herkenning     resultaat van het model, met de hash van het transcript waarop het steunde
    beslissing     de dossierbeslissing (dossier.beslis)
    opdrachten     publicaties die moeten gebeuren, bewaard VÓÓR de eerste externe schrijfactie:
                   [{sleutel, soort: tabel|klaarzet|dossierkopie|bezoekmap, payload, gedaan, fout, pogingen, ts}]
    zoektaken      geleverde zoektaken met bewijs

Een herstart voert alleen uit wat niet gedaan is en vraagt geen nieuwe modelherkenning aan zolang
het transcript niet veranderde. De tabel en het klaarzet-item ontdubbelen zelf op uniek=plaud:<id>.
"""
import hashlib
import json
import os
from datetime import datetime, timezone


def _nu():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_van(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]


class Staat:
    def __init__(self, map_):
        self.map = map_
        os.makedirs(map_, exist_ok=True)

    def _pad(self, pid):
        return os.path.join(self.map, f"{pid}.json")

    def lees(self, pid):
        try:
            with open(self._pad(pid), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"plaud_id": pid, "opdrachten": [], "zoektaken": {}}

    def bewaar(self, pid, st):
        st["bijgewerkt"] = _nu()
        tmp = self._pad(pid) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self._pad(pid))

    def alle(self):
        uit = {}
        for n in os.listdir(self.map):
            if n.endswith(".json"):
                st = self.lees(n[:-5])
                uit[st.get("plaud_id") or n[:-5]] = st
        return uit


def plan(st, opdrachten):
    """Zet de gewenste publicaties vast. Een opdracht met dezelfde sleutel en payload die al gedaan is,
    blijft gedaan; een gewijzigde payload wordt opnieuw uitgevoerd."""
    oud = {o["sleutel"]: o for o in st.get("opdrachten", [])}
    nieuw = []
    for o in opdrachten:
        h = hash_van(o["payload"])
        vorig = oud.get(o["sleutel"])
        if vorig and vorig.get("hash") == h:
            nieuw.append(vorig)
        else:
            nieuw.append({**o, "hash": h, "gedaan": False, "fout": "", "pogingen": 0, "ts": ""})
    sleutels = {o["sleutel"] for o in nieuw}
    nieuw += [o for s, o in oud.items() if s not in sleutels and o.get("gedaan")]    # wat gedaan is, blijft geschiedenis
    st["opdrachten"] = nieuw
    return st


def voer_uit(st, bewaar, uitvoerders):
    """Voer elke openstaande opdracht uit; na elke stap wordt de staat bewaard. Een fout wordt
    onthouden en blokkeert de andere opdrachten niet. Geeft (gedaan, fouten)."""
    gedaan, fouten = 0, 0
    for o in st.get("opdrachten", []):
        if o.get("gedaan"):
            continue
        try:
            o["resultaat"] = uitvoerders[o["soort"]](o["payload"])
            o.update(gedaan=True, fout="", ts=_nu())
            gedaan += 1
        except Exception as e:  # noqa: BLE001
            o.update(fout=f"{type(e).__name__}: {str(e)[:200]}", pogingen=int(o.get("pogingen") or 0) + 1, ts=_nu())
            fouten += 1
        bewaar(st)
    return gedaan, fouten


def open_opdrachten(st):
    return [o for o in st.get("opdrachten", []) if not o.get("gedaan")]

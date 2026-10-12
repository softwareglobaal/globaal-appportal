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
    blijft gedaan; een gewijzigde payload wordt opnieuw uitgevoerd. Wat al uitgevoerd was en nu vervangen
    wordt, gaat naar st["geschiedenis"]: een eerdere verspreiding verdwijnt nooit stil (nacontrole v1.1)."""
    oud = {o["sleutel"]: o for o in st.get("opdrachten", [])}
    nieuw = []
    for o in opdrachten:
        h = hash_van(o["payload"])
        vorig = oud.get(o["sleutel"])
        if vorig and vorig.get("hash") == h:
            nieuw.append(vorig)
        else:
            if vorig and vorig.get("gedaan"):
                st.setdefault("geschiedenis", []).append({**_zonder_tekst(vorig), "vervangen": _nu()})
            nieuw.append({**o, "hash": h, "gedaan": False, "fout": "", "pogingen": 0, "ts": ""})
    sleutels = {o["sleutel"] for o in nieuw}
    nieuw += [o for s, o in oud.items() if s not in sleutels and o.get("gedaan")]    # wat gedaan is, blijft staan
    st["opdrachten"] = nieuw
    return st


def _zonder_tekst(o):
    p = dict(o.get("payload") or {})
    if "tekst" in p:
        p["tekst"] = "(%d tekens, hash %s)" % (len(p["tekst"]), hash_van(p["tekst"]))
    return {**o, "payload": p}


def trek_in(st, reden):
    """Een nieuwe beslissing staat geen zakelijke kopie meer toe. Eerder geleverde dossierkopieën en
    bezoekmapbestanden blijven staan (niets automatisch verwijderen), maar worden zichtbaar als ingetrokken
    gemarkeerd met een herstelvoorstel voor Mehdi."""
    for o in st.get("opdrachten", []) + st.get("geschiedenis", []):
        if o.get("soort") in ("dossierkopie", "bezoekmap") and o.get("gedaan") and not o.get("ingetrokken"):
            res = o.get("resultaat")
            pad = res.get("pad") if isinstance(res, dict) else res
            o.update(ingetrokken=_nu(), reden_intrekking=reden[:300],
                     herstel="voorstel: Mehdi beoordeelt %s; niets automatisch verwijderd" % (pad or "het eerder geleverde bestand"))
    return st


def te_herstellen(st):
    """Revisies en ingetrokken kopieën die nog niet afgehandeld zijn."""
    uit = [r for r in st.get("revisies", []) if not r.get("afgehandeld")]
    uit += [o for o in st.get("opdrachten", []) + st.get("geschiedenis", []) if o.get("ingetrokken") and not o.get("afgehandeld")]
    return uit


def voer_uit(st, bewaar, uitvoerders):
    """Voer elke openstaande opdracht uit; na elke stap wordt de staat bewaard. Een fout wordt
    onthouden en blokkeert de andere opdrachten niet. Een uitvoerder die een dict teruggeeft met
    bevestigd=True heeft de opgeslagen versie nagelezen; herzien>0 betekent dat een al opgepakte
    publicatie als revisie bijgewerkt is. Geeft (gedaan, fouten)."""
    gedaan, fouten = 0, 0
    for o in st.get("opdrachten", []):
        if o.get("gedaan"):
            continue
        try:
            res = uitvoerders[o["soort"]](o["payload"])
            o["resultaat"] = res
            o.update(gedaan=True, fout="", ts=_nu(), bevestigd=bool(isinstance(res, dict) and res.get("bevestigd")))
            if isinstance(res, dict) and res.get("herzien"):
                st.setdefault("revisies", []).append({"sleutel": o["sleutel"], "ts": _nu(), "afgehandeld": False,
                                                      "herstel": "een al opgepakte publicatie is herzien; eerdere verspreiding nakijken"})
            gedaan += 1
        except Exception as e:  # noqa: BLE001
            o.update(fout=f"{type(e).__name__}: {str(e)[:200]}", pogingen=int(o.get("pogingen") or 0) + 1, ts=_nu())
            fouten += 1
        bewaar(st)
    return gedaan, fouten


def open_opdrachten(st):
    return [o for o in st.get("opdrachten", []) if not o.get("gedaan")]

#!/usr/bin/env python3
"""Het manifest van het Plaud-archief: wat De Plaudwacht op de VM leest (verbeteropdracht v1.0, §2).

Het archief met audio blijft op de Mac (Dropbox, `Data uit Mehdi/Plaud`); één archief, geen tweede
op de VM. De VM krijgt alleen dit manifest en per opname transcript.json (zie plaud_invoer_push.sh).

    <archief>/00 manifest.json = {"meta": {contract, versie, gemaakt, aantal, toestanden, kort_wachtend, conflicten},
                                  "opnames": [<contract van één opname> + {"toestand": ..., "map": ...}]}

Elke opname staat erin volgens het contract (contract.py), met haar echte toestand uit archief.toestand.
Een opname zonder geldig id of tijd staat erin met herstel en een reden, nooit met een gegokte datum.
Getekende links staan nooit in het manifest.

Python 3.9-compatibel.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import archief  # noqa: E402
import contract  # noqa: E402

NAAM = "00 manifest.json"
# PLAUD-9 (T-0120): een wachtende opname korter dan dit telt ook apart, als 'kort, na te kijken' (47 van de 87 wachtende
# in oktober). Ze blijft in de wachtteller: drie pogingen bewijzen niet dat er nooit een transcript komt (Codex).
KORT_MINUTEN = 1


def _minuten(c):
    """De duur in minuten; onbekend telt nooit als kort."""
    try:
        return float(c.get("duur_minuten"))
    except (TypeError, ValueError):
        return float("inf")


def bouw(doel):
    doel = Path(doel)
    idx, conflicten = archief.index(doel)
    opnames, tellers = [], {}
    for g in sorted(doel.glob("*/gesprek.json")):
        meta = archief.lees_json(g)
        if not isinstance(meta, dict):
            continue
        try:
            pid = contract.canon_id(meta.get("plaud_id") or "")
        except contract.Herstel:
            continue
        if idx.get(pid) != g.parent:
            continue                     # tweede plaats van een id: alleen in conflicten
        st = archief.toestand(g.parent, pid)
        try:
            c = contract.opname(meta, archiefmap=g.parent.name, transcript=meta.get("transcript"), audio=meta.get("audio"),
                                bron=meta.get("bron") or "archief")
        except contract.Herstel as e:
            c = {"contract": contract.CONTRACT, "versie": contract.VERSIE, "plaud_id": pid,
                 "archief": {"plaats": "mac-dropbox", "map": g.parent.name}, "herstel": str(e)}
        transcript = dict(c.get("transcript") or {})
        if st["transcript"] in ("aanwezig", "online_only"):
            transcript["staat"] = "aanwezig"
        elif transcript.get("staat") != "wacht":
            transcript["staat"] = "onbekend" if st["transcript"] == "ontbreekt" else st["transcript"]
        c["transcript"] = transcript
        c["audio"] = {"staat": st["audio"], "bestand": st.get("audio_bestand", "")}
        c["toestand"] = st["staat"]
        c["redenen"] = st["redenen"]
        for k in ("benaming",):
            if k in meta:
                c[k] = meta[k]
        tellers[st["staat"]] = tellers.get(st["staat"], 0) + 1
        opnames.append(c)
    opnames.sort(key=lambda o: o.get("start_utc") or "", reverse=True)
    # id-conflict: de opname zelf krijgt herstel en toestand conflict, met alle mappen; nooit stil één map kiezen
    for pid, mappen in conflicten.items():
        for c in opnames:
            if c.get("plaud_id") == pid:
                tellers[c["toestand"]] = tellers.get(c["toestand"], 1) - 1
                if not tellers[c["toestand"]]:
                    tellers.pop(c["toestand"])
                c.update(toestand="conflict", herstel="id staat in meer dan één map: " + " | ".join(p.name for p in mappen),
                         mappen=[p.name for p in mappen])
        tellers["conflict"] = tellers.get("conflict", 0) + 1
    kort = sum(1 for c in opnames if c.get("toestand") == "wacht_op_transcript" and _minuten(c) < KORT_MINUTEN)
    m = {"meta": {"contract": contract.CONTRACT, "versie": contract.VERSIE,
                  "gemaakt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "aantal": len(opnames),
                  "toestanden": tellers, "kort_wachtend": kort,
                  "conflicten": {pid: [p.name for p in ps] for pid, ps in conflicten.items()}},
         "opnames": opnames}
    archief.schrijf_json(doel / NAAM, m)
    return m["meta"]


def lees(map_):
    data = archief.lees_json(Path(map_) / NAAM)
    return data if isinstance(data, dict) and isinstance(data.get("opnames"), list) else None


if __name__ == "__main__":
    import os
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ.get("PLAUD_DOEL", Path.home() / "TKN-buro Dropbox" / "Data uit Mehdi" / "Plaud"))
    print(json.dumps(bouw(d), ensure_ascii=False))

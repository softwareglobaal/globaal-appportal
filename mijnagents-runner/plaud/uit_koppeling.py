#!/usr/bin/env python3
"""Brug zolang de Plaud-aanmelding op de Mac ontbreekt: bouw opnames uit resultaten van de
Plaud-koppeling (MCP get_file, opgeslagen als bestand) met dezelfde bouwer als de ophaler.

    /usr/bin/python3 uit_koppeling.py <get_file-resultaat.json> [...]

Elke opname gaat door bouw_map.bouw (resolver op id, veilige links, atomair schrijven) en wordt
in de lijst aangevuld (gedeeltelijk: verse waarden winnen). Links worden niet getoond of bewaard;
de uitvoer noemt alleen id, status en map. Het resultaatbestand wordt na verwerking gewist,
omdat het getekende links bevat.

Python 3.9-compatibel.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import archief  # noqa: E402
import bouw_map  # noqa: E402
import lijst  # noqa: E402


def lees(pad):
    t = Path(pad).read_text(encoding="utf-8")
    d = json.loads(t[t.find("{"):t.rfind("}") + 1])
    return d.get("data") if isinstance(d.get("data"), dict) else d


def invoer(d):
    bron = {s.get("data_type"): s for s in d.get("source_list") or [] if isinstance(s, dict)}
    o = {"id": d["id"], "name": d.get("name"), "start_at": d.get("start_at"), "duration": d.get("duration"),
         "serial_number": d.get("serial_number"), "presigned_url": d.get("presigned_url") or "", "bron": "plaud-koppeling"}
    if (bron.get("transaction") or {}).get("data_link"):
        o["transcript_link"] = bron["transaction"]["data_link"]
    elif d.get("transcript_link"):                 # vlakke invoer: alleen de velden die de bouwer nodig heeft
        o["transcript_link"] = d["transcript_link"]
    return o


def main(paden):
    doel = bouw_map.DOEL
    idx = archief.Index(doel)
    ops = [invoer(lees(p)) for p in paden]
    lijst.schrijf(doel, [{k: v for k, v in o.items() if k not in ("presigned_url", "transcript_link", "bron")} for o in ops],
                  bron="plaud-koppeling", volledig=False)
    fout = 0
    for p, o in zip(paden, ops):
        r = bouw_map.bouw(o, doel, idx)
        ok = r["status"] in ("compleet", "wacht_op_transcript") and not r["fouten"]
        fout += 0 if ok else 1
        print(json.dumps({"plaud_id": r["plaud_id"], "status": r["status"], "map": Path(r["map"] or "").name,
                          "audio": r["audio"], "transcript": r["transcript"], "fouten": r["fouten"]}, ensure_ascii=False))
        if ok:
            os.remove(p)
    return 1 if fout else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

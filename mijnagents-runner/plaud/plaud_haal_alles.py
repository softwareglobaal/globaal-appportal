#!/usr/bin/env python3
"""Haalt het volledige Plaud-archief op met de eigen API van Plaud (geen MCP nodig).

Per opname een map in Dropbox: JJJJ-MM-DD UUMM <naam in Plaud>, met
transcript.md, transcript.json, gesprek.json en de geluidsopname.
Wat al compleet is wordt overgeslagen, dus opnieuw draaien mag altijd.

De aanmelding gebeurt eenmalig met plaud_login.py; het toegangsbewijs staat in
~/.config/plaud/token.json en komt nooit in code, chat of documentatie.

Gebruik:
    python3 plaud_haal_alles.py              alles
    python3 plaud_haal_alles.py --max 25     de nieuwste 25 (proef)
    python3 plaud_haal_alles.py --lijst      alleen tellen, niets ophalen
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bouw_map  # noqa: E402
from mapnaam import mapnaam  # noqa: E402
import mapnaam as mapnaam_mod  # noqa: E402

BASIS = "https://platform.plaud.ai/developer/api"
BEWIJS = Path.home() / ".config" / "plaud" / "token.json"
DOEL = Path.home() / "TKN-buro Dropbox" / "Data uit Mehdi" / "Plaud"
WERK = Path(__file__).parent / "invoer"


def _bearer() -> str:
    t = json.loads(BEWIJS.read_text(encoding="utf-8"))
    return t.get("access_token") or (t.get("data") or {}).get("access_token") or ""


def api(pad: str) -> dict:
    r = subprocess.run(["curl", "-sS", "--fail-with-body", f"{BASIS}{pad}",
                        "-H", f"Authorization: Bearer {_bearer()}",
                        "-H", "Accept: application/json",
                        "-A", "plaud-cli/0.3.14"], capture_output=True)
    tekst = r.stdout.decode("utf-8", "replace")
    if r.returncode != 0:
        raise RuntimeError(f"API-fout op {pad}: {tekst[:200]}")
    return json.loads(tekst or "{}")


def lijst_alles() -> list:
    uit, pagina = [], 1
    while True:
        d = api(f"/open/third-party/files/?page={pagina}&page_size=100")
        rij = d.get("data") or d.get("items") or []
        if not rij:
            break
        uit += rij
        print(f"  pagina {pagina}: {len(rij)} (samen {len(uit)})", flush=True)
        pagina += 1
        time.sleep(0.4)
    return uit


def compleet(m: Path) -> bool:
    if not m.is_dir():
        return False
    audio = [p for p in m.glob("opname.*") if p.stat().st_size > 1000]
    return bool(audio) and ((m / "transcript.json").exists() or (m / "geen-transcript.txt").exists())


def al_binnen(o) -> bool:
    """Op Plaud-id, niet op naam: een hernoemde map is dezelfde opname (mapnaam.map_van)."""
    return compleet(mapnaam_mod.map_van(o, DOEL))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--max", type=int, default=0)
    p.add_argument("--lijst", action="store_true")
    a = p.parse_args()
    WERK.mkdir(exist_ok=True)

    print("Lijst ophalen...", flush=True)
    alles = lijst_alles()
    alles.sort(key=lambda o: o.get("start_at", ""), reverse=True)
    uren = sum(o.get("duration", 0) for o in alles) / 3_600_000
    print(f"{len(alles)} opnames, samen {uren:.0f} uur audio", flush=True)
    (Path(__file__).parent / "plaud_lijst_api.json").write_text(
        json.dumps(alles, ensure_ascii=False), encoding="utf-8")
    if a.lijst:
        return 0

    te_doen = [o for o in alles if not al_binnen(o)]
    print(f"{len(alles) - len(te_doen)} al compleet; {len(te_doen)} te doen\n", flush=True)
    if a.max:
        te_doen = te_doen[:a.max]

    goed = mislukt = zonder = 0
    for i, o in enumerate(te_doen, 1):
        naam = mapnaam(o)
        try:
            d = api(f"/open/third-party/files/{o['id']}")
            bron = {s.get("data_type"): s for s in (d.get("source_list") or [])}
            invoer = {"id": o["id"], "name": o.get("name", ""), "start_at": o["start_at"],
                      "duration": o.get("duration", 0), "presigned_url": d.get("presigned_url", "")}
            tr = bron.get("transaction") or {}
            if tr.get("data_link"):
                invoer["transcript_link"] = tr["data_link"]
            pad = WERK / f"{o['id']}.json"
            pad.write_text(json.dumps(invoer, ensure_ascii=False), encoding="utf-8")
            bouw_map.main(str(pad))
            m = DOEL / naam
            if not invoer.get("transcript_link"):
                (m / "geen-transcript.txt").write_text(
                    "Deze opname is in Plaud nooit getranscribeerd.\n", encoding="utf-8")
                zonder += 1
            if compleet(m):
                goed += 1
            else:
                mislukt += 1
                print(f"  ONVOLLEDIG: {naam}", flush=True)
            pad.unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            mislukt += 1
            print(f"  FOUT bij {naam}: {type(e).__name__} {str(e)[:150]}", flush=True)
        if i % 10 == 0:
            print(f"[{i}/{len(te_doen)}] compleet {goed}, zonder transcript {zonder}, mislukt {mislukt}", flush=True)
        time.sleep(0.3)

    print(f"\nKlaar: {goed} compleet, waarvan {zonder} zonder transcript; {mislukt} mislukt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

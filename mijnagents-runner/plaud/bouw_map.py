#!/usr/bin/env python3
"""Bouwt één Plaud-gespreksmap uit de links die get_file teruggeeft.

Invoer: een JSON-bestand met
  id, name, start_at (UTC), duration (ms), presigned_url, transcript_link
Optioneel: outline_link, summary_link.

Uitvoer in <DOEL>/<JJJJ-MM-DD UUMM titel>/:
  transcript.md   leesbaar, [HH:MM:SS] Speaker N: tekst
  transcript.json de ruwe uitingen van Plaud (de bron)
  gesprek.json    metadata
  opname.<ext>    de geluidsopname

Afspraak D7: de samenvatting van Plaud halen we niet op. Het verslag schrijft
het systeem zelf uit het transcript.
"""
import gzip
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mapnaam import mapnaam, belgisch  # noqa: E402

DOEL = Path(os.environ.get("PLAUD_DOEL", Path.home() / "TKN-buro Dropbox" / "Data uit Mehdi" / "Plaud"))
CTX = ssl.create_default_context()
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}


def haal(url: str, tijdslimiet: int = 900) -> bytes:
    """Via curl: de systeem-Python op deze Mac heeft geen bruikbare rootstore."""
    import subprocess
    r = subprocess.run(["curl", "-sSL", "--fail", "--max-time", str(tijdslimiet),
                        "-A", UA["User-Agent"], url], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl {r.returncode}: {r.stderr.decode('utf-8', 'replace')[:150]}")
    return r.stdout


def uitpakken(rauw: bytes) -> str:
    if rauw[:2] == b"\x1f\x8b":
        return gzip.decompress(rauw).decode("utf-8", "replace")
    return rauw.decode("utf-8", "replace")


def klok(ms: int) -> str:
    s, ms = divmod(int(ms or 0), 1000)
    u, s = divmod(s, 60)
    h, u = divmod(u, 60)
    return f"{h:02d}:{u:02d}:{s:02d}"


def schrijf_transcript(uitingen: list, kop: dict) -> str:
    regels = ["---"]
    for k, v in kop.items():
        regels.append(f"{k}: {v}")
    regels += ["---", ""]
    for u in uitingen:
        spr = u.get("speaker") or u.get("original_speaker") or "Speaker ?"
        regels.append(f"[{klok(u.get('start_time'))}] {spr}: {(u.get('content') or '').strip()}")
    return "\n".join(regels) + "\n"


LIJST = Path(__file__).parent / "plaud_lijst.json"


def _vul_aan(op: dict) -> dict:
    """Naam, starttijd en duur komen uit de opgehaalde Plaud-lijst, niet uit
    overgetypte tekst: zo kan een tikfout de mapnaam niet meer bepalen."""
    if not LIJST.exists():
        return op
    for r in json.loads(LIJST.read_text(encoding="utf-8")):
        if r.get("id") == op.get("id"):
            for k in ("name", "start_at", "duration"):
                if r.get(k) is not None:
                    op[k] = r[k]
            break
    return op


def main(pad_invoer: str) -> int:
    op = _vul_aan(json.loads(Path(pad_invoer).read_text(encoding="utf-8")))
    naam = mapnaam(op)
    map_ = DOEL / naam
    map_.mkdir(parents=True, exist_ok=True)
    t_bel = belgisch(op["start_at"])
    duur_min = round((op.get("duration") or 0) / 60000, 1)
    verslag = {"map": str(map_), "audio": "", "transcript": "", "fouten": []}

    # transcript
    doel_json = map_ / "transcript.json"
    if doel_json.exists() and doel_json.stat().st_size > 2:
        verslag["transcript"] = "bestond al"
    elif op.get("transcript_link"):
        try:
            tekst = uitpakken(haal(op["transcript_link"], 300))
            data = json.loads(tekst)
            uitingen = data if isinstance(data, list) else (data.get("data") or data.get("result") or [])
            doel_json.write_text(json.dumps(uitingen, ensure_ascii=False, indent=1), encoding="utf-8")
            kop = {"plaud_id": op["id"], "naam_in_plaud": op.get("name", ""),
                   "start_utc": op["start_at"], "start_belgisch": t_bel.strftime("%Y-%m-%d %H:%M:%S %Z"),
                   "duur_minuten": duur_min, "uitingen": len(uitingen), "bron": "Plaud (block transaction)"}
            (map_ / "transcript.md").write_text(schrijf_transcript(uitingen, kop), encoding="utf-8")
            verslag["transcript"] = f"{len(uitingen)} uitingen"
        except Exception as e:
            verslag["fouten"].append(f"transcript: {type(e).__name__} {str(e)[:120]}")
    else:
        (map_ / "geen-transcript.txt").write_text(
            "Deze opname is in Plaud nooit getranscribeerd.\n", encoding="utf-8")
        verslag["transcript"] = "niet getranscribeerd in Plaud"

    # audio
    url = op.get("presigned_url") or ""
    ext = ".ogg" if ".ogg" in url.split("?")[0] else (".mp3" if ".mp3" in url.split("?")[0] else ".m4a" if ".m4a" in url.split("?")[0] else ".ogg")
    doel_audio = map_ / f"opname{ext}"
    bestaand = [p for p in map_.glob("opname.*")]
    if bestaand and bestaand[0].stat().st_size > 1000:
        verslag["audio"] = f"bestond al ({bestaand[0].stat().st_size // 1000} KB)"
    elif url:
        try:
            rauw = haal(url)
            doel_audio.write_bytes(rauw)
            verslag["audio"] = f"{len(rauw) // 1000} KB"
        except Exception as e:
            verslag["fouten"].append(f"audio: {type(e).__name__} {str(e)[:120]}")
    else:
        verslag["fouten"].append("audio: geen presigned_url meegegeven")

    (map_ / "gesprek.json").write_text(json.dumps({
        "plaud_id": op["id"], "naam_in_plaud": op.get("name", ""),
        "start_utc": op["start_at"], "start_belgisch": t_bel.isoformat(),
        "duur_minuten": duur_min, "opgehaald": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bron": "Plaud MCP get_file", "audio_bestand": doel_audio.name if doel_audio.exists() else "",
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps(verslag, ensure_ascii=False))
    return 1 if verslag["fouten"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

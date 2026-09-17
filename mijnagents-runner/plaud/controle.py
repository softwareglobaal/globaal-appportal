#!/usr/bin/env python3
"""Meet of het Plaud-archief volledig is: per opname uit de lijst de map,
het transcript en de geluidsopname. Schrijft ook 00 index.md in de doelmap."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mapnaam import mapnaam, belgisch, map_van  # noqa: E402

SP = Path(__file__).parent
DOEL = Path.home() / "TKN-buro Dropbox" / "Data uit Mehdi" / "Plaud"


def main() -> int:
    lijst = json.loads((SP / "plaud_lijst.json").read_text(encoding="utf-8"))
    lijst.sort(key=lambda o: o["start_at"], reverse=True)
    ontbreekt_map, zonder_audio, zonder_transcript, goed = [], [], [], []
    regels = ["# Plaud-archief: index", "",
              f"{len(lijst)} opnames in Plaud. Elke map heet `JJJJ-MM-DD UUMM <naam in Plaud>` in Belgische tijd,",
              "met `transcript.md` (leesbaar), `transcript.json` (de bron), `gesprek.json` en de geluidsopname.", "",
              "| datum | uur | duur | naam in Plaud | transcript | opname |", "|---|---|---|---|---|---|"]
    for op in lijst:
        naam = mapnaam(op)
        m = map_van(op, DOEL)
        naam = m.name
        t = belgisch(op["start_at"])
        duur = f"{round((op.get('duration') or 0) / 60000)} min"
        audio = [p for p in m.glob("opname.*") if p.stat().st_size > 1000]
        heeft_tr = (m / "transcript.json").exists()
        geen_tr = (m / "geen-transcript.txt").exists()
        if not m.is_dir():
            ontbreekt_map.append(naam)
            st_tr, st_au = "ontbreekt", "ontbreekt"
        else:
            if heeft_tr:
                st_tr = f"{len(json.loads((m / 'transcript.json').read_text(encoding='utf-8')))} uitingen"
            elif geen_tr:
                st_tr = "niet getranscribeerd"
            else:
                st_tr = "ONTBREEKT"; zonder_transcript.append(naam)
            if audio:
                st_au = f"{audio[0].stat().st_size // 1_000_000} MB" if audio[0].stat().st_size > 1_000_000 else f"{audio[0].stat().st_size // 1000} KB"
            else:
                st_au = "ONTBREEKT"; zonder_audio.append(naam)
            if (heeft_tr or geen_tr) and audio:
                goed.append(naam)
        naam_plaud = (op.get("name") or "").replace("|", "/")
        regels.append(f"| {t:%Y-%m-%d} | {t:%H:%M} | {duur} | {naam_plaud} | {st_tr} | {st_au} |")
    (DOEL / "00 index.md").write_text("\n".join(regels) + "\n", encoding="utf-8")
    uit = {"opnames_in_plaud": len(lijst), "compleet": len(goed),
           "map_ontbreekt": len(ontbreekt_map), "audio_ontbreekt": len(zonder_audio),
           "transcript_ontbreekt": len(zonder_transcript)}
    print(json.dumps(uit, ensure_ascii=False))
    for kop, rij in (("MAP ONTBREEKT", ontbreekt_map), ("AUDIO ONTBREEKT", zonder_audio), ("TRANSCRIPT ONTBREEKT", zonder_transcript)):
        if rij:
            print(f"\n{kop} ({len(rij)}):")
            for n in rij[:15]:
                print("  ", n)
            if len(rij) > 15:
                print(f"   ... en {len(rij) - 15} meer")
    return 0


if __name__ == "__main__":
    sys.exit(main())

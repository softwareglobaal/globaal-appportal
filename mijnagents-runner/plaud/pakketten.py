#!/usr/bin/env python3
"""Deelt de Plaud-lijst op in werkpakketten en slaat over wat al compleet is.

Compleet = de doelmap bestaat met transcript.json (of de melding dat er geen
transcript is) en een opnamebestand groter dan 1 kB.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mapnaam import mapnaam, compleet  # noqa: E402

SP = Path(__file__).parent
DOEL = Path.home() / "TKN-buro Dropbox" / "Data uit Mehdi" / "Plaud"
PER_PAKKET = int(sys.argv[1]) if len(sys.argv) > 1 else 12


def main() -> int:
    lijst = json.loads((SP / "plaud_lijst.json").read_text(encoding="utf-8"))
    # nieuwste eerst, zodat het recente werk het eerst binnen is
    lijst.sort(key=lambda o: o["start_at"], reverse=True)
    te_doen = []
    klaar = 0
    for op in lijst:
        if compleet(op, DOEL):
            klaar += 1
        else:
            te_doen.append({"id": op["id"], "name": op.get("name", ""),
                            "start_at": op["start_at"], "duration": op.get("duration", 0),
                            "map": mapnaam(op)})
    for p in SP.glob("pakket_*.json"):
        p.unlink()
    aantal = 0
    for i in range(0, len(te_doen), PER_PAKKET):
        aantal += 1
        (SP / f"pakket_{aantal:02d}.json").write_text(
            json.dumps(te_doen[i:i + PER_PAKKET], ensure_ascii=False, indent=1), encoding="utf-8")
    uren = sum(o["duration"] for o in te_doen) / 3_600_000
    print(json.dumps({"totaal": len(lijst), "al_klaar": klaar, "te_doen": len(te_doen),
                      "pakketten": aantal, "per_pakket": PER_PAKKET,
                      "uren_audio_te_halen": round(uren, 1),
                      "schatting_GB": round(uren * 0.015, 1)}, ensure_ascii=False))  # gemeten 15 MB per uur
    return 0


if __name__ == "__main__":
    sys.exit(main())

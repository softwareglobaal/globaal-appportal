"""Grendel op de samenvatting en de actiepunten van Fathom (T-0154, overleg 02-11-2026 X2, 3-0):

- de koppeling vraagt include_summary en include_action_items mee, en created_before als een einde gegeven is;
- bewaar schrijft samenvatting.md als de markdown van Fathom (niet str(dict)) en actiepunten.md als json;
- samenvatting_aanvullen vult een bestaand gesprek bij zonder de herkenning of iets anders in gesprek.json te raken,
  schrijft niets als er niets nieuws is, en nooit bij een ander recording_id;
- de inhaalronde (eenmalig/fathom_samenvatting_inhalen.py) telt droog en schrijft met --een precies één gesprek.
"""
import json
import os
import subprocess
import sys
import tempfile
import traceback
import urllib.parse

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
ARCHIEF = tempfile.mkdtemp()
os.environ["FATHOM_ARCHIEF_PAD"] = ARCHIEF
os.environ["FATHOM_API_KEYS"] = "proefsleutel"
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import fathom as F  # noqa: E402
import fathom_wacht as FW  # noqa: E402

SAMENVATTING = {"template_name": "Enhanced", "markdown_formatted": "## Doel van de Vergadering\n\n[Afstemmen.](https://fathom.video/share/x?timestamp=0.0)\n"}
ACTIES = [{"description": "Lijst doorsturen", "assignee": {"name": "Collega"}, "completed": False}]


def test_koppeling_vraagt_samenvatting_en_actiepunten():
    gezien = []

    def nep(sleutel, pad, params=None):
        gezien.append((pad, dict(params or {})))
        return {"items": [], "next_cursor": None}

    echt = F._haal
    F._haal = nep
    try:
        F.gesprekken("2026-10-01T00:00:00Z", met_transcript=False, tot_iso="2026-11-03T00:00:00Z")
    finally:
        F._haal = echt
    assert gezien and gezien[0][0] == "/meetings"
    p = gezien[0][1]
    assert p["include_summary"] == "true" and p["include_action_items"] == "true" and p["include_transcript"] == "false"
    assert p["created_before"] == "2026-11-03T00:00:00Z"
    assert "created_before" in urllib.parse.urlencode(p)


def test_samenvatting_md():
    assert F.samenvatting_md({"default_summary": SAMENVATTING}) == SAMENVATTING["markdown_formatted"]
    assert F.samenvatting_md({"default_summary": None}) == ""
    assert F.samenvatting_md({"default_summary": "losse tekst"}) == "losse tekst"


def _gesprek(rid=7, met=True):
    g = {"recording_id": rid, "title": "Proefoverleg", "recording_start_time": "2026-10-30T08:00:00Z",
         "recording_end_time": "2026-10-30T08:10:00Z", "url": "https://fathom.video/calls/7", "transcript": [], "calendar_invitees": []}
    if met:
        g["default_summary"], g["action_items"] = SAMENVATTING, ACTIES
    else:
        g["default_summary"], g["action_items"] = None, []
    return g


def test_bewaar_schrijft_markdown_en_json():
    map_, nieuw = FW.bewaar(_gesprek(), "Mehdi: tekst.", {"afdeling": "it", "prive": False})
    assert nieuw and os.path.isdir(map_)
    sm = open(os.path.join(map_, "samenvatting.md"), encoding="utf-8").read()
    assert sm.startswith("# Samenvatting van Fathom") and "## Doel van de Vergadering" in sm and "markdown_formatted" not in sm
    assert json.load(open(os.path.join(map_, "actiepunten.md"), encoding="utf-8")) == ACTIES
    gj = json.load(open(os.path.join(map_, "gesprek.json"), encoding="utf-8"))
    assert gj["default_summary"] == SAMENVATTING and gj["herkenning"] == {"afdeling": "it", "prive": False}


def test_bewaar_zonder_samenvatting_schrijft_die_bestanden_niet():
    map_, nieuw = FW.bewaar(_gesprek(rid=8, met=False), "", {"afdeling": "it"})
    assert nieuw and not os.path.exists(os.path.join(map_, "samenvatting.md"))
    assert not os.path.exists(os.path.join(map_, "actiepunten.md"))
    assert os.path.exists(os.path.join(map_, "geen-transcript.txt"))


def test_aanvullen_bestaand_gesprek_houdt_herkenning():
    map_, _ = FW.bewaar(_gesprek(rid=9, met=False), "tekst", {"afdeling": "regie", "waarom": "proef"})
    assert FW.samenvatting_aanvullen(map_, _gesprek(rid=9)) is True
    gj = json.load(open(os.path.join(map_, "gesprek.json"), encoding="utf-8"))
    assert gj["herkenning"] == {"afdeling": "regie", "waarom": "proef"} and gj["default_summary"] == SAMENVATTING
    assert gj["action_items"] == ACTIES and gj["title"] == "Proefoverleg"
    assert "## Doel" in open(os.path.join(map_, "samenvatting.md"), encoding="utf-8").read()
    # een tweede keer: niets nieuws, niets geschreven
    assert FW.samenvatting_aanvullen(map_, _gesprek(rid=9)) is False
    # een ander gesprek raakt deze map nooit
    assert FW.samenvatting_aanvullen(map_, _gesprek(rid=10)) is False
    # zonder samenvatting bij Fathom: niets te vullen
    map2, _ = FW.bewaar(_gesprek(rid=11, met=False), "tekst", {})
    assert FW.samenvatting_aanvullen(map2, _gesprek(rid=11, met=False)) is False


def test_inhaalronde_droog_en_een():
    FW._INDEX = None
    for rid in (21, 22, 23):
        FW.bewaar(_gesprek(rid=rid, met=False), "tekst", {"afdeling": "it"})
    lijst = [_gesprek(rid=21), _gesprek(rid=22), _gesprek(rid=23, met=False), _gesprek(rid=99)]
    omgeving = dict(os.environ, FATHOM_ARCHIEF_PAD=ARCHIEF, FATHOM_API_KEYS="proefsleutel", PROEF_LIJST=json.dumps(lijst))
    script = os.path.join(RUNNER, "eenmalig", "fathom_samenvatting_inhalen.py")
    stub = (f"import json, os, sys\nsys.path.insert(0, {RUNNER!r}); sys.path.insert(0, {os.path.join(RUNNER, 'koppelingen')!r})\nimport fathom\n"
            "fathom.gesprekken = lambda *a, **k: json.loads(os.environ['PROEF_LIJST'])\n"
            "sys.argv = ['x'] + sys.argv[1:]\n"
            f"exec(compile(open({script!r}).read(), {script!r}, 'exec'))\n")
    pad = os.path.join(ARCHIEF, "stub.py")
    open(pad, "w").write(stub)
    uit = subprocess.run([sys.executable, pad, "--droog"], capture_output=True, text=True, env=omgeving,
                         cwd=os.path.join(RUNNER, "koppelingen"))
    assert uit.returncode == 0, uit.stderr
    assert "droog: zou bijwerken" in uit.stdout and "bijgewerkt 2" in uit.stdout and "zonder_map 1" in uit.stdout, uit.stdout
    assert not os.path.exists(os.path.join(FW.bestaande_map(_gesprek(rid=21)), "samenvatting.md"))
    uit = subprocess.run([sys.executable, pad, "--een"], capture_output=True, text=True, env=omgeving,
                         cwd=os.path.join(RUNNER, "koppelingen"))
    assert uit.returncode == 0, uit.stderr
    assert "bijgewerkt 1" in uit.stdout, uit.stdout
    FW._INDEX = None
    m21, m22 = FW.bestaande_map(_gesprek(rid=21)), FW.bestaande_map(_gesprek(rid=22))
    assert os.path.exists(os.path.join(m21, "samenvatting.md")) != os.path.exists(os.path.join(m22, "samenvatting.md"))
    uit = subprocess.run([sys.executable, pad], capture_output=True, text=True, env=omgeving, cwd=os.path.join(RUNNER, "koppelingen"))
    assert uit.returncode == 0 and "bijgewerkt 1" in uit.stdout and "niets_nieuws 1" in uit.stdout, uit.stdout
    assert os.path.exists(os.path.join(m21, "samenvatting.md")) and os.path.exists(os.path.join(m22, "samenvatting.md"))


if __name__ == "__main__":
    fouten = 0
    for naam, f in sorted((k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)):
        try:
            f()
            print("ok   " + naam)
        except Exception:  # noqa: BLE001
            fouten += 1
            print("FOUT " + naam)
            traceback.print_exc()
    print("klaar" if not fouten else f"{fouten} fout(en)")
    sys.exit(1 if fouten else 0)

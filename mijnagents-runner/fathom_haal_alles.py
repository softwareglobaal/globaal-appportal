#!/usr/bin/env python3
"""Fathom: het volledige archief, plat, één map per gesprek. Draait op de VM.

Map: <DOEL>/JJJJ-MM-DD UUMM <titel in Fathom>/ (Belgische tijd; Fathom levert UTC).
Botst de naam met een ander gesprek, dan komt het recording_id erachter.

In elke map, zoals bij het Plaud-archief:
  transcript.md      leesbaar, kop met tijden, deelnemers en link, dan [tijd] spreker: tekst
  transcript.json    de ruwe uitingen van Fathom (de bron)
  gesprek.json       metadata van Fathom; met de herkenning van De Fathomwacht als die er al was
  video.md + video (Fathom).webloc   de link naar de opname (Fathom geeft geen videobestand)
  samenvatting.md / actiepunten.md / hoogtepunten.md   als Fathom ze heeft (niet als bron, D7)

Wat De Fathomwacht al had (oud archief fathom/<jaar> en fathom/Prive/<jaar>) wordt
overgenomen op recording_id, zodat zijn herkenning niet verloren gaat. Het transcript
uit de API is altijd leidend. Opnieuw draaien slaat over wat al compleet is.

Gebruik:  python3 fathom_haal_alles.py            alles
          python3 fathom_haal_alles.py --lijst    alleen tellen
"""
import json
import os
import plistlib
import re
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, "/home/ubuntu/appportal/mijnagents-runner/koppelingen")
import fathom  # noqa: E402

BE = ZoneInfo("Europe/Brussels")
OUD = os.path.expanduser("~/appportal/mijnagents-data/fathom")
DOEL = os.path.expanduser(os.environ.get("FATHOM_DATA_PAD", "~/appportal/mijnagents-data/fathom-data"))
SINDS = "2020-01-01T00:00:00Z"
MAX = 110
VERBODEN = re.compile(r'[/\\:*?"<>|\x00-\x1f]')
GENERIEK = re.compile(r"^(impromptu (zoom )?meeting|zoom meeting|meeting|gesprek|call)$", re.I)


def belgisch(iso):
    if not iso:
        return None
    d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(BE)


def titel_van(g):
    n = (g.get("title") or g.get("meeting_title") or "").strip()
    n = VERBODEN.sub(" ", n).replace("–", "-")
    n = re.sub(r"\s+", " ", n).strip(" .-")
    return n or "zonder titel"


def mapnaam(g, uniek=False):
    t = belgisch(g.get("recording_start_time") or g.get("created_at"))
    stempel = t.strftime("%Y-%m-%d %H%M") if t else "0000-00-00 0000"
    naam = f"{stempel} {titel_van(g)}"
    staart = f" [{g.get('recording_id')}]" if uniek else ""
    if len(naam) + len(staart) > MAX:
        naam = naam[:MAX - len(staart)].rstrip(" ,;-") + "…"
    return naam + staart


def oud_archief():
    """recording_id -> pad van de map die De Fathomwacht al maakte."""
    uit = {}
    for wortel, _, bestanden in os.walk(OUD):
        if "gesprek.json" in bestanden and "fathom-data" not in wortel:
            try:
                rid = json.load(open(os.path.join(wortel, "gesprek.json"))).get("recording_id")
                if rid:
                    uit[rid] = wortel
            except (OSError, ValueError):
                pass
    return uit


def transcript_regels(g):
    t = g.get("transcript")
    if not t or isinstance(t, str):
        return [], (t or "")
    regels = []
    for r in t:
        spr = r.get("speaker")
        spr = spr.get("display_name") if isinstance(spr, dict) else spr
        regels.append(f"[{r.get('timestamp', '')}] {spr or '?'}: {r.get('text', '')}")
    return t, "\n".join(regels)


def bewaar(g, map_, oud_pad):
    os.makedirs(map_, exist_ok=True)
    herk = None
    if oud_pad:
        try:
            herk = json.load(open(os.path.join(oud_pad, "gesprek.json"))).get("herkenning")
        except (OSError, ValueError):
            herk = None
    ruw, tekst = transcript_regels(g)
    start, eind = belgisch(g.get("recording_start_time")), belgisch(g.get("recording_end_time"))
    duur = round((eind - start).total_seconds() / 60) if start and eind else 0
    kop = (f"# {g.get('title') or g.get('meeting_title') or ''}\n\n"
           f"Belgische tijd: {start:%Y-%m-%d %H:%M} tot {eind:%H:%M}\n" if start and eind else f"# {g.get('title') or ''}\n\n")
    kop += (f"Fathom (UTC) {g.get('recording_start_time', '')} tot {g.get('recording_end_time', '')} · {g.get('url', '')}\n"
            f"Deellink: {g.get('share_url', '')}\n"
            f"Opgenomen door: {(g.get('recorded_by') or {}).get('name', '')} <{(g.get('recorded_by') or {}).get('email', '')}>\n"
            f"Deelnemers: " + ", ".join(f"{i.get('name', '')} <{i.get('email', '')}>" for i in (g.get("calendar_invitees") or []) if isinstance(i, dict))
            + f"\nDuur: {duur} min · uitingen: {len(ruw)}\n")
    if herk:
        kop += f"\nHerkenning (De Fathomwacht): {json.dumps(herk, ensure_ascii=False)}\n"
    open(os.path.join(map_, "transcript.md"), "w", encoding="utf-8").write(kop + "\n" + tekst + "\n")
    open(os.path.join(map_, "transcript.json"), "w", encoding="utf-8").write(json.dumps(ruw, ensure_ascii=False, indent=1))
    if not ruw and not tekst:
        open(os.path.join(map_, "geen-transcript.txt"), "w", encoding="utf-8").write("Fathom heeft voor dit gesprek geen transcript.\n")
    for veld, naam, kopje in (("default_summary", "samenvatting.md", "# Samenvatting van Fathom (niet als bron voor contract of verslag; het transcript telt)\n\n"),
                              ("action_items", "actiepunten.md", ""), ("highlights", "hoogtepunten.md", "")):
        if g.get(veld):
            inhoud = g[veld] if isinstance(g[veld], str) else json.dumps(g[veld], ensure_ascii=False, indent=1)
            open(os.path.join(map_, naam), "w", encoding="utf-8").write(kopje + inhoud + "\n")
    meta = {k: v for k, v in g.items() if k != "transcript"}
    meta["start_belgisch"] = start.isoformat() if start else ""
    meta["duur_minuten"] = duur
    meta["uitingen"] = len(ruw)
    meta["herkenning"] = herk
    meta["oud_archief"] = oud_pad or ""
    meta["opgehaald"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    open(os.path.join(map_, "gesprek.json"), "w", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False, indent=1))
    url = g.get("share_url") or g.get("url") or ""
    if url:
        with open(os.path.join(map_, "video (Fathom).webloc"), "wb") as f:
            plistlib.dump({"URL": url}, f)
        open(os.path.join(map_, "video.md"), "w", encoding="utf-8").write(
            f"Video van dit gesprek staat in Fathom (origineel blijft daar): {url}\n"
            "Fathom geeft via zijn API geen videobestand vrij; downloaden kan alleen met de hand op fathom.video.\n")


def bestaand_id(map_):
    try:
        return json.load(open(os.path.join(map_, "gesprek.json"))).get("recording_id")
    except (OSError, ValueError):
        return None


def main():
    alleen_lijst = "--lijst" in sys.argv
    os.makedirs(DOEL, exist_ok=True)
    log = open(os.path.join(DOEL, "00 opbouw.log"), "a", encoding="utf-8")

    def zeg(s):
        print(s, flush=True)
        log.write(f"{datetime.now():%H:%M:%S} {s}\n"); log.flush()

    oud = oud_archief()
    zeg(f"oud archief: {len(oud)} gesprekken met gesprek.json")
    gezien, rijen = set(), []
    tel = {"gezien": 0, "nieuw": 0, "bestond": 0, "uit_oud": 0, "zonder_transcript": 0, "generieke_titel": 0, "botsing": 0}
    for nr, s in enumerate(fathom.sleutels(), 1):
        cursor, pagina = None, 0
        while True:
            p = {"created_after": SINDS, "include_transcript": "false" if alleen_lijst else "true"}
            if cursor:
                p["cursor"] = cursor
            d = fathom._haal(s, "/meetings", p)
            items = d.get("items") or d.get("meetings") or []
            pagina += 1
            for g in items:
                rid = g.get("recording_id")
                if not rid or rid in gezien:
                    continue
                gezien.add(rid)
                tel["gezien"] += 1
                if GENERIEK.match(titel_van(g)):
                    tel["generieke_titel"] += 1
                t = belgisch(g.get("recording_start_time") or g.get("created_at"))
                rijen.append((t, g, nr))
                if alleen_lijst:
                    continue
                map_ = os.path.join(DOEL, mapnaam(g))
                ander = bestaand_id(map_)
                if ander and ander != rid:
                    map_ = os.path.join(DOEL, mapnaam(g, uniek=True)); tel["botsing"] += 1
                    ander = bestaand_id(map_)
                if ander == rid and os.path.exists(os.path.join(map_, "transcript.json")):
                    tel["bestond"] += 1
                    continue
                oud_pad = oud.get(rid, "")
                bewaar(g, map_, oud_pad)
                tel["nieuw"] += 1
                if oud_pad:
                    tel["uit_oud"] += 1
                if not g.get("transcript"):
                    tel["zonder_transcript"] += 1
            zeg(f"sleutel {nr} pagina {pagina}: {len(items)} items · " + ", ".join(f"{k} {v}" for k, v in tel.items()))
            cursor = d.get("next_cursor")
            if not cursor:
                break
            if not alleen_lijst:
                time.sleep(fathom.PAUZE)

    # index
    rijen.sort(key=lambda r: r[0] or datetime.min.replace(tzinfo=BE), reverse=True)
    regels = ["# Fathom-archief: index", "",
              f"{len(rijen)} gesprekken in Fathom. Elke map heet `JJJJ-MM-DD UUMM <titel in Fathom>` in Belgische tijd,",
              "met `transcript.md`, `transcript.json` (de bron), `gesprek.json` en de link naar de video in Fathom.", "",
              "| datum | uur | duur | titel in Fathom | opgenomen door | uitingen |", "|---|---|---|---|---|---|"]
    for t, g, nr in rijen:
        e = belgisch(g.get("recording_end_time"))
        duur = f"{round((e - t).total_seconds() / 60)} min" if t and e else ""
        n_uit = len(g.get("transcript") or []) if isinstance(g.get("transcript"), list) else ""
        regels.append(f"| {t:%Y-%m-%d} | {t:%H:%M} | {duur} | {titel_van(g).replace('|', '/')} | {(g.get('recorded_by') or {}).get('name', '')} | {n_uit} |"
                      if t else f"| ? | ? | | {titel_van(g)} | | |")
    open(os.path.join(DOEL, "00 index.md"), "w", encoding="utf-8").write("\n".join(regels) + "\n")
    zeg("KLAAR " + json.dumps(tel))
    return 0


if __name__ == "__main__":
    sys.exit(main())

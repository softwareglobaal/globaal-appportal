#!/usr/bin/env python3
"""Bouwt of herstelt één Plaud-gespreksmap uit de links van Plaud (verbeteropdracht v1.0, §5 en §6).

Invoer: id, presigned_url, transcript_link (optioneel), en zo nodig name, start_at, duration,
serial_number. Wat ontbreekt wordt aangevuld uit de lijst (lijst.py); verse waarden blijven staan.

De map komt uit archief.resolve: eerst op Plaud-id, dus een hernoemde map blijft dezelfde opname en
een botsing krijgt een eigen suffixmap. Volgorde, elk bestand atomair:

  1. gesprek.json met het contract, zodat het id de map meteen claimt
  2. transcript.json (de bron) en transcript.md (opnieuw te maken uit de bron)
  3. de geluidsopname; de extensie volgt uit de inhoud, niet uit de url
  4. gesprek.json bijgewerkt met de toestand

Zonder transcriptlink is de opname niet "nooit getranscribeerd" maar wacht ze: de volgende
controle volgt een vaste backoff (contract.WACHT_STAPPEN_UUR).

Het resultaat is gestructureerd en noemt het werkelijke pad. De aanroeper controleert alleen dat
resultaat en schrijft zelf niets in een map die hij zelf berekende.

Afspraak D7: de samenvatting van Plaud halen we niet op.

Python 3.9-compatibel.
"""
import gzip
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import archief  # noqa: E402
import contract  # noqa: E402
import lijst  # noqa: E402
import veilig  # noqa: E402

DOEL = Path(os.environ.get("PLAUD_DOEL", Path.home() / "TKN-buro Dropbox" / "Data uit Mehdi" / "Plaud"))
MAX_TRANSCRIPT = 60_000_000
MAX_AUDIO = 900_000_000


def _nu():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def uitpakken(rauw):
    if rauw[:2] == b"\x1f\x8b":
        return gzip.decompress(rauw).decode("utf-8", "replace")
    return rauw.decode("utf-8", "replace")


def _uitingen(tekst):
    data = json.loads(tekst)
    uit = data if isinstance(data, list) else (data.get("data") or data.get("result") or [])
    if not isinstance(uit, list) or not all(isinstance(u, dict) for u in uit):
        raise ValueError("transcript is geen lijst van uitingen")
    return uit


def bouw(op, doel=DOEL, idx=None, haler=None):
    """Bouw of herstel de map van één opname. Geeft een resultaat met het werkelijke pad."""
    haler = haler or veilig.haal
    doel = Path(doel)
    res = {"plaud_id": None, "map": None, "status": "fout", "audio": "", "transcript": "", "fouten": []}
    try:
        op = lijst.aanvul(op, doel)
        pid = contract.canon_id(op.get("id") or op.get("plaud_id") or "")
        res["plaud_id"] = pid
        idx = idx or archief.Index(doel)
        map_ = archief.resolve({**op, "plaud_id": pid}, doel, idx)
    except contract.Herstel as e:
        res.update(status="herstel", fouten=[str(e)])
        return res
    res["map"] = str(map_)
    oud = archief.lees_json(map_ / "gesprek.json") or {}
    vers = {k: v for k, v in op.items() if not k.endswith("_url") and k != "transcript_link"}
    samen = {**oud, **vers}
    if op.get("name") is not None:          # verse naam uit Plaud wint van wat er stond
        samen["naam_in_plaud"] = op["name"]
    if op.get("start_at"):                  # verse opnametijd wint ook
        for k in ("start_utc", "start_brussel", "start_belgisch"):
            samen.pop(k, None)
    try:
        c = contract.opname(samen, archiefmap=map_.name, transcript=oud.get("transcript"), audio=oud.get("audio"),
                            bron=op.get("bron", "plaud-api"))
    except contract.Herstel as e:
        res.update(status="herstel", fouten=[str(e)])
        return res
    # 1. claim de map met het id, maar laat benaming, herkenning en eerdere velden staan
    meta = {**oud, **c, "plaud_id": pid}
    for k in ("benaming", "herkenning"):
        if k in oud:
            meta[k] = oud[k]
    meta.setdefault("opgehaald", _nu())
    archief.schrijf_json(map_ / "gesprek.json", meta)
    idx.zet(pid, map_)

    # 2. transcript
    t = dict(oud.get("transcript") or {})
    huidig, _ = archief._transcript(map_)
    if op.get("transcript_link"):
        try:
            uitingen = _uitingen(uitpakken(haler(op["transcript_link"], MAX_TRANSCRIPT, 300)))
            archief.schrijf_json(map_ / "transcript.json", uitingen)
            t = {"staat": "aanwezig", "uitingen": len(uitingen), "laatste_controle": _nu(), "bron": "plaud transaction"}
            res["transcript"] = "%d uitingen" % len(uitingen)
        except (veilig.OnveiligeLink, veilig.DownloadFout, ValueError, OSError) as e:
            res["fouten"].append("transcript: %s %s" % (type(e).__name__, str(e)[:120]))
    elif huidig in ("aanwezig", "online_only"):
        t = {**t, "staat": "aanwezig"}
        res["transcript"] = "bestond al"
    else:
        pogingen = int(t.get("pogingen") or 0) + 1
        t = {"staat": "wacht", "pogingen": pogingen, "laatste_controle": _nu(),
             "volgende_controle": contract.volgende_controle(pogingen), "bron": "geen transcriptlink van Plaud"}
        res["transcript"] = "wacht (poging %d)" % pogingen
    vers_transcript = res["transcript"].endswith("uitingen")
    if archief._transcript(map_)[0] == "aanwezig" and (vers_transcript or not (map_ / "transcript.md").exists()):
        archief.maak_markdown(map_)

    # 3. audio
    bestand, a = archief._audio(map_)
    if a in ("aanwezig", "online_only"):
        res["audio"] = "bestond al" if a == "aanwezig" else "online-only in Dropbox"
        audio = {"staat": a, "bestand": bestand}
    elif op.get("presigned_url"):
        try:
            rauw = haler(op["presigned_url"], MAX_AUDIO, 1800)
            ext = veilig.audio_soort(rauw[:512])
            if not ext:
                raise ValueError("inhoud is geen herkende audio")
            if len(rauw) < archief.MIN_AUDIO:
                raise ValueError("audiobestand te klein")
            archief.schrijf_atomair(map_ / ("opname" + ext), rauw)
            audio = {"staat": "aanwezig", "bestand": "opname" + ext}
            res["audio"] = "%d KB" % (len(rauw) // 1000)
        except (veilig.OnveiligeLink, veilig.DownloadFout, ValueError, OSError) as e:
            audio = {"staat": "ontbreekt"}
            res["fouten"].append("audio: %s %s" % (type(e).__name__, str(e)[:120]))
    else:
        audio = {"staat": "ontbreekt"}
        res["fouten"].append("audio: geen link meegegeven")

    # 4. toestand vastleggen
    meta["transcript"], meta["audio"] = t, audio
    meta["bijgewerkt"] = _nu()
    archief.schrijf_json(map_ / "gesprek.json", meta)
    res["status"] = archief.toestand(map_, pid)["staat"]
    return res


def main(pad_invoer):
    op = json.loads(Path(pad_invoer).read_text(encoding="utf-8"))
    res = bouw(op)
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res["status"] in ("compleet", "wacht_op_transcript") and not res["fouten"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

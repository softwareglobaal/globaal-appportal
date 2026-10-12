#!/usr/bin/env python3
"""Reconciliatie van het Plaud-archief per Plaud-id (verbeteropdracht v1.0, §10).

Alleen lezen. Verwijdert, verplaatst en hernoemt niets. Schrijft één rapport:
`<archief>/00 reconciliatie.md` (en dezelfde gegevens als `00 reconciliatie.json`).

Per opname één categorie, met de reden:

    gearchiveerd              compleet volgens archief.toestand
    transcript_wacht          audio aanwezig, transcript bestaat (nog) niet; de ophaler vraagt het opnieuw
                              (de oude markering geen-transcript.txt is geen definitief einde)
    onvolledig                iets ontbreekt of is half geschreven (redenen)
    metadata_onvolledig       geen geldige opnametijd of id; staat op herstel, nooit een gegokte datum
    ontbreekt                 in de Plaud-lijst, maar geen map in het archief
    mogelijke_dubbel          een id in twee mappen, of twee ids met dezelfde minuut en duur
    oud_vm_archief            dezelfde opname staat ook in de oude VM-map `2026/` (overlap, niets doen)
    mogelijk_verkeerd_gekoppeld   een bordtaak of klaarzet-item dat volgens de oude regels gekoppeld werd

Gebruik:
    python3 reconciliatie.py [<archief>] [--bord plaud_klaarzet.json]

--bord: export van de bord-items rond Plaud ({"voor": [...], "van": [...]}), alleen lezen gemaakt.

Python 3.9-compatibel.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import archief  # noqa: E402
import contract  # noqa: E402
import lijst  # noqa: E402

VOLGORDE = ("gearchiveerd", "transcript_wacht", "onvolledig", "metadata_onvolledig", "ontbreekt",
            "mogelijke_dubbel", "oud_vm_archief", "mogelijk_verkeerd_gekoppeld")


def _inhoud(it):
    i = it.get("inhoud") or {}
    if isinstance(i, str):
        try:
            return json.loads(i) if i.startswith("{") else {}
        except ValueError:
            return {}
    return i


def reconcilieer(doel, bord=None):
    doel = Path(doel)
    idx, conflicten = archief.index(doel)
    rijen = {}

    def zet(pid, cat, reden, map_=""):
        rijen.setdefault(pid, {"plaud_id": pid, "categorieen": [], "redenen": [], "map": map_})
        r = rijen[pid]
        if cat not in r["categorieen"]:
            r["categorieen"].append(cat)
        if reden:
            r["redenen"].append(reden)
        if map_ and not r["map"]:
            r["map"] = map_

    starts = {}
    for pid, m in idx.items():
        st = archief.toestand(m, pid)
        meta = archief.lees_json(m / "gesprek.json") or {}
        oude_markering = (m / "geen-transcript.txt").exists()
        try:
            c = contract.opname(meta, archiefmap=m.name)
            starts.setdefault((c["start_utc"][:16], round(float(c.get("duur_minuten") or 0))), []).append(pid)
        except contract.Herstel as e:
            zet(pid, "metadata_onvolledig", str(e), m.name)
        if st["staat"] == "compleet":
            zet(pid, "gearchiveerd", "", m.name)
        elif st["staat"] == "wacht_op_transcript":
            zet(pid, "transcript_wacht", "oude markering geen-transcript.txt" if oude_markering else "", m.name)
        else:
            zet(pid, "onvolledig", "; ".join(st["redenen"]), m.name)
    for pid, mappen in conflicten.items():
        zet(pid, "mogelijke_dubbel", "id in meer mappen: " + " | ".join(p.name for p in mappen))
    for (minuut, duur), pids in starts.items():
        if len(pids) > 1 and duur > 0:
            for pid in pids:
                zet(pid, "mogelijke_dubbel", "zelfde minuut %s en duur %d min als %s" % (minuut, duur, ", ".join(p for p in pids if p != pid)))
    # in de Plaud-lijst maar niet in het archief
    for o in lijst.lees(doel)["opnames"]:
        try:
            pid = contract.canon_id(o.get("id") or "")
        except contract.Herstel:
            continue
        if pid not in idx:
            zet(pid, "ontbreekt", "in de Plaud-lijst (%s), geen map" % (o.get("start_at") or "?")[:16])
    # de oude VM-map (jaarmap 2026/) die de sync naar de Mac haalde
    for g in sorted(doel.glob("20[0-9][0-9]/*/gesprek.json")):
        meta = archief.lees_json(g) or {}
        try:
            pid = contract.canon_id(meta.get("plaud_id") or "")
        except contract.Herstel:
            continue
        zet(pid, "oud_vm_archief", "ook in %s/%s" % (g.parent.parent.name, g.parent.name) + ("" if pid in idx else "; NIET in het hoofdarchief"))
    # het bord: wat volgens de oude regels gekoppeld werd
    taken = []
    for it in (bord or {}).get("van", []):
        m = re.match(r"plaud:(.+)$", it.get("uniek") or "")
        if not m:
            continue
        try:
            pid = contract.canon_id(m.group(1))
        except contract.Herstel:
            continue
        sleutel = str(it.get("sleutel") or "")
        if it.get("soort") == "werfbezoek":
            zet(pid, "mogelijk_verkeerd_gekoppeld", "klaarzet %s als soort werfbezoek (onzichtbaar voor de werfverslagketen)" % it.get("id"))
        elif sleutel and not re.fullmatch(r"\d{4}", sleutel):
            zet(pid, "mogelijk_verkeerd_gekoppeld", "klaarzet %s met sleutel '%s' in plaats van een projectnummer" % (it.get("id"), sleutel[:60]))
    for it in (bord or {}).get("voor", []):
        i = _inhoud(it)
        taken.append({"id": it.get("id"), "soort": it.get("soort"), "status": it.get("status"), "van": it.get("van"),
                      "datum": i.get("datum") or "", "dossier": str(i.get("dossier") or it.get("sleutel") or ""),
                      "bezoekmap": i.get("bezoekmap") or "", "titel": it.get("titel", "")})
    # per open taak: welke opnames die dag in het archief staan (zelfde dag is geen bevestiging)
    per_dag = {}
    for pid, m in idx.items():
        meta = archief.lees_json(m / "gesprek.json") or {}
        try:
            c = contract.opname(meta)
        except contract.Herstel:
            continue
        per_dag.setdefault(c["start_brussel"][:10], []).append("%s %s" % (c["start_brussel"][11:16], m.name))
    for t in taken:
        t["opnames_die_dag"] = sorted(per_dag.get(t["datum"], []))
    tellers = {}
    for r in rijen.values():
        for c in r["categorieen"]:
            tellers[c] = tellers.get(c, 0) + 1
    return {"gemaakt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "archief_mappen": len(idx),
            "tellers": tellers, "opnames": sorted(rijen.values(), key=lambda r: r["map"] or r["plaud_id"]), "taken": taken}


def rapport(r):
    t = r["tellers"]
    regels = ["# Plaud-archief: reconciliatie per Plaud-id", "",
              "Gemaakt %s door plaud/reconciliatie.py (verbeteropdracht v1.0). Alleen gelezen; er is niets verwijderd, verplaatst" % r["gemaakt"][:16],
              "of hernoemd. Een opname kan in meer dan één categorie staan.", "",
              "| categorie | aantal | wat er gebeurt |", "|---|---|---|"]
    wat = {"gearchiveerd": "niets; compleet",
           "transcript_wacht": "de ophaler vraagt het transcript opnieuw met backoff (1 u, 6 u, 1 d, 3 d, wekelijks)",
           "onvolledig": "de ophaler herstelt de map op id bij de volgende ronde (audio of markdown opnieuw)",
           "metadata_onvolledig": "staat op herstel; Mehdi of de ophaler vult de opnametijd aan uit Plaud",
           "ontbreekt": "de ophaler bouwt de map bij de volgende ronde",
           "mogelijke_dubbel": "voorstel: Mehdi kijkt na welke map geldt; niets automatisch",
           "oud_vm_archief": "voorstel: de oude jaarmap 2026/ blijft staan tot Mehdi ja zegt; de sync haalt hem niet meer bij",
           "mogelijk_verkeerd_gekoppeld": "oude klaarzet-items blijven staan; nieuwe items krijgen het projectnummer als sleutel"}
    for c in VOLGORDE:
        regels.append("| %s | %d | %s |" % (c, t.get(c, 0), wat[c]))
    regels += ["", "Mappen in het archief (op id): %d" % r["archief_mappen"], ""]
    for c in VOLGORDE[1:]:
        lijst_ = [o for o in r["opnames"] if c in o["categorieen"]]
        if not lijst_:
            continue
        regels += ["## %s" % c, "", "| map | plaud_id | reden |", "|---|---|---|"]
        for o in lijst_[:400]:
            regels.append("| %s | %s | %s |" % (o["map"] or "-", o["plaud_id"], "; ".join(o["redenen"])[:200].replace("|", "/")))
        regels.append("")
    if r["taken"]:
        regels += ["## Bordtaken en verzoeken voor De Plaudwacht", "",
                   "Dezelfde dag is geen bevestiging: De Plaudwacht levert alleen bij één passende opname en een geldige bezoekmap.", "",
                   "| taak | soort | status | dossier | bezoekdag | opnames die dag in het archief |", "|---|---|---|---|---|---|"]
        for tk in sorted(r["taken"], key=lambda x: (x["status"] or "", x["datum"])):
            regels.append("| %s | %s | %s | %s | %s | %s |" % (tk["id"], tk["soort"], tk["status"], tk["dossier"], tk["datum"] or "-",
                                                             "; ".join(tk["opnames_die_dag"])[:220] or "geen"))
        regels.append("")
    return "\n".join(regels) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("archief", nargs="?", default=os.environ.get("PLAUD_DOEL", str(Path.home() / "TKN-buro Dropbox" / "Data uit Mehdi" / "Plaud")))
    p.add_argument("--bord")
    a = p.parse_args()
    bord = json.load(open(a.bord, encoding="utf-8")) if a.bord else None
    r = reconcilieer(a.archief, bord)
    archief.schrijf_atomair(Path(a.archief) / "00 reconciliatie.md", rapport(r))
    archief.schrijf_json(Path(a.archief) / "00 reconciliatie.json", r)
    print(json.dumps(r["tellers"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

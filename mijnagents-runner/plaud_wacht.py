#!/usr/bin/env python3
"""De Plaudwacht (Privé) — Plaud-transcripten die de claude.ai-routine in Dropbox
zet, herkennen, archiveren, loggen en klaarzetten. Werkwijze v2 op het bord
(werkwijze/plaud-wacht.md is het zaad); de routine-opdracht staat in
werkwijze/plaud-routine.md.

Elk uur en op verzoek. Leest de inbox en elke map "0 Plaud" in een salesmap;
herkent met dezelfde herkenning als De Fathomwacht (personentabel, agenda en
locatie op de starttijd, Pipedrive, openingszin); archief in
mijnagents-data/plaud; gesprekkentabel (bron plaud); klaarzetten per afdeling.
"""
import json
import os
import re
import sys
from datetime import datetime

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import bronnen  # noqa: E402
import dropbox_prive  # noqa: E402
import fathom_wacht as fw  # noqa: E402  (personen_uit_werkwijze, herken, deals_index, veilige_naam)

NAAM = "plaud-wacht"
ag = bord.Agent(NAAM)
INBOX = os.environ.get("PLAUD_INBOX", "/Work All/000 AI Opzet/Mehdi Agents/Plaud inbox")
ARCHIEF = os.path.expanduser(os.environ.get("PLAUD_ARCHIEF_PAD", "~/appportal/mijnagents-data/plaud"))
AFDELING_VAN_TITEL = re.compile(r"\[(HA|UNABO|HB|CONTRAX|PRIVE)", re.I)


def kop_van(tekst):
    """De kopregels uit een routinebestand (plaud_id, account, start, duur_minuten, naam_in_plaud)."""
    uit = {}
    for regel in tekst.splitlines()[:12]:
        m = re.match(r"^\s*([a-z_]+)\s*:\s*(.+?)\s*$", regel)
        if m:
            uit[m.group(1)] = m.group(2)
    return uit


def context_op(start_iso):
    """Wat de agenda en de locatie zeggen over dat moment (uit de bak klaargezet)."""
    dag = (start_iso or "")[:10]
    uur = (start_iso or "")[11:16]
    afspraken, plek = [], ""
    try:
        for it in bord.call(f"/api/klaarzet?status=alle&n=400").get("items", []):
            if it["soort"] == "afspraak" and it["titel"].startswith(dag):
                afspraken.append(it["titel"])
            if it["soort"] == "locatie" and it["sleutel"] == dag:
                for regel in (it["inhoud"] or "").splitlines():
                    if regel.startswith("| ") and "bezoek" in regel and uur:
                        van, tot = regel.split("|")[1].strip(), regel.split("|")[2].strip()
                        if van <= uur <= tot:
                            plek = regel.split("|")[5].strip()
    except Exception:  # noqa: BLE001
        pass
    return afspraken, plek


def verwerk_bestand(e, bron_map, personen, deals, gezien_ids):
    tekst = bronnen.download(e["path_lower"]).decode("utf-8", "replace")
    kop = kop_van(tekst)
    pid = kop.get("plaud_id") or e.get("id") or e.get("path_lower")
    if pid in gezien_ids:
        return None
    start = kop.get("start", "")[:16] or e.get("client_modified", "")[:16]
    afspraken, plek = context_op(start)
    g = {"title": kop.get("naam_in_plaud") or e["name"], "meeting_title": kop.get("naam_in_plaud") or e["name"],
         "recording_start_time": start, "recording_id": pid, "url": e.get("path_display", ""),
         "recorded_by": {"name": kop.get("account", "mehdi"), "email": ""},
         "calendar_invitees": [{"name": "Mehdi Chegini", "email": "mch@h-architects.be", "is_external": False}]}
    deal, hoe = fw.koppel_deal(g, deals)
    extra = (f"\n\n[context] agenda op {start[:10]}: " + "; ".join(afspraken[:6]) + (f"\n[context] locatie om {start[11:16]}: {plek}" if plek else "")
             + "\n[regel] Lees de eerste minuut op Mehdi's openingszin (waar, met wie, wat). Sprekers heten 'Speaker N'; herleid ze uit wat ze zeggen.")
    herk = fw.herken(g, tekst[:6000] + extra, personen, deal, hoe)
    # archief
    jaar = start[:4] or "onbekend"
    map_ = os.path.join(ARCHIEF, jaar, f"{start.replace('T', ' ').replace(':', '')} {fw.veilige_naam(herk.get('hoofdpersoon') or e['name'])}")
    if not os.path.exists(os.path.join(map_, "gesprek.json")):
        os.makedirs(map_, exist_ok=True)
        open(os.path.join(map_, "transcript.md"), "w", encoding="utf-8").write(tekst)
        open(os.path.join(map_, "gesprek.json"), "w", encoding="utf-8").write(json.dumps({"plaud_id": pid, "kop": kop, "bron_bestand": e.get("path_display"), "herkenning": herk}, ensure_ascii=False, indent=1))
    duur = int(float(kop.get("duur_minuten") or 0) or 0)
    prive = bool(herk.get("prive"))
    rij = {"uniek": f"plaud:{pid}", "datum": start[:10], "start": start[11:16], "minuten": duur, "personen": ", ".join(herk.get("personen") or []),
           "bedrijf": herk.get("bedrijf", ""), "afdeling": herk.get("afdeling", ""), "thema": herk.get("thema", ""),
           "project": herk.get("project", "") or (deal["titel"] if deal else ""), "prive": prive, "zekerheid": herk.get("zekerheid", ""),
           "waarom": herk.get("waarom", ""), "archief": map_, "link": e.get("path_display", ""), "opgenomen_door": kop.get("account", "mehdi"), "bron": "plaud"}
    pad = ""
    if deal and not prive:
        salesmap = bronnen.zoek_salesmap(re.sub(r"^\s*\d{4}\s+", "", deal["titel"]), deal["nummer"])
        if salesmap and not bron_map.startswith(salesmap):
            naam = f"{start[:10]} Plaud transcript - {fw.veilige_naam(herk.get('hoofdpersoon') or 'gesprek')}.md"
            if not any(x.get("name") == naam for x in (bronnen.lijst(f"{salesmap}/0 Plaud", recursief=False) or [])):
                pad = bronnen.upload(f"{salesmap}/0 Plaud/{naam}", tekst.encode("utf-8"))
                ag.log(f"opname {start}", "schrijf", f"kopie naar {pad} (origineel: {map_})")
    voor = "mehdi" if prive or herk.get("afdeling") in ("onbekend", "prive", "regie", "") else herk["afdeling"]
    soort = "werfbezoek" if re.search(r"werf|plaatsbezoek|oplevering", (herk.get("thema", "") + " " + tekst[:800]).lower()) else "transcript"
    klaar = {"voor": voor, "soort": soort, "sleutel": str(deal["id"]) if deal else (herk.get("project") or ""),
             "titel": f"{start} Plaud: {herk.get('hoofdpersoon') or e['name']} · {herk.get('thema', '')[:60]}" + (" · PRIVÉ" if prive else ""),
             "uniek": f"plaud:{pid}", "verwijzing": pad or e.get("path_display", ""),
             "inhoud": {**{k: v for k, v in rij.items() if k != "waarom"}, "waarom": herk.get("waarom", ""), "transcript_pad": os.path.join(map_, "transcript.md")}}
    ag.log(f"opname {start}", "bevinding", f"{herk.get('hoofdpersoon') or e['name']} · {herk.get('afdeling')} · {herk.get('thema', '')[:60]}" + (" · privé" if prive else "") + f" · zekerheid {herk.get('zekerheid')}", herk.get("waarom", ""))
    return rij, klaar


def main():
    ag.hartslag("actief", taak="Plaud-transcripten verwerken")
    try:
        gezien_ids = set()
        for wortel, _, bestanden in os.walk(ARCHIEF):
            for b in bestanden:
                if b == "gesprek.json":
                    try:
                        gezien_ids.add(json.load(open(os.path.join(wortel, b))).get("plaud_id"))
                    except Exception:  # noqa: BLE001
                        pass
        personen = fw.personen_uit_werkwijze(bord.call("/api/agent/fathom-wacht/werkwijze").get("werkwijze") or "")
        deals = fw.deals_index()
        bronmappen = [INBOX]
        for basis in bronnen.SALES_BASES:
            for e in bronnen.lijst(basis, recursief=False) or []:
                if e.get(".tag") == "folder":
                    bronmappen.append(f"{e['path_display']}/0 Plaud")
        rijen, klaar, gezien, nieuw = [], [], 0, 0
        for map_pad in bronmappen:
            for e in bronnen.lijst(map_pad, recursief=False) or []:
                if e.get(".tag") != "file" or not e.get("name", "").lower().endswith((".md", ".txt")) or e["name"].startswith("00 "):
                    continue
                gezien += 1
                uit = verwerk_bestand(e, map_pad, personen, deals, gezien_ids)
                if uit:
                    nieuw += 1
                    rijen.append(uit[0]); klaar.append(uit[1])
        if rijen:
            bord.call("/api/gesprekken", {"rijen": rijen})
        uit = ag.klaarzet(klaar)
        nood = [] if gezien else [{"tekst": "De Plaud-routine op claude.ai is nog niet ingepland (opdracht: werkwijze/plaud-routine.md); zonder haar zie ik niets", "wie": "mehdi"}]
        nood.append({"tekst": "Plaud-accounts van Angela, Siyan en Shaniel: elk een eigen connector en routine, of een Plaud-team", "wie": "mehdi"})
        ag.log("Plaud", "bron", f"{gezien} transcriptbestanden in inbox en salesmappen; {nieuw} nieuw verwerkt; {len(personen)} personen in de tabel")
        ag.log("Plaud", "schrijf", f"gesprekkentabel +{len(rijen)}; klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend")
        ag.log_verstuur()
        sp = dropbox_prive.spiegel_map(ARCHIEF, "/Plaud")
        if sp["verstuurd"] or sp["fout"]:
            ag.log("Plaud", "schrijf", f"Dropbox privé: {sp['verstuurd']} bestand(en) verstuurd" + (f"; fout: {sp['fout']}" if sp["fout"] else ""))
        ag.hartslag("waakt" if gezien else "rust", taak="wacht op Plaud-transcripten",
                    detail=(f"laatste ronde: {gezien} bestanden, {nieuw} nieuw" if gezien else "wacht op de Plaud-routine (claude.ai)"), nood=nood)
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()

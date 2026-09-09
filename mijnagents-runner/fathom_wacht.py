#!/usr/bin/env python3
"""De Fathomwacht (Privé) — nieuwe Fathom-gesprekken ophalen en klaarzetten.

Elk uur:
  1. gesprekken van de laatste 14 dagen (Fathom-API, met transcript);
  2. per gesprek: bij welke deal hoort het (projectnummer of naam in de titel,
     e-mail van een deelnemer die als persoon aan een deal hangt);
  3. het transcript als tekstbestand in de salesmap van dat dossier zetten
     (map "0 Fathom", nooit overschrijven) als het er nog niet staat;
  4. klaarzetten voor h-architects: transcript (met pad) en gesprek, één keer per gesprek.
Leest Fathom; schrijft alleen nieuwe tekstbestanden in de salesmap.
"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import bronnen  # noqa: E402
import fathom  # noqa: E402
import pipedrive  # noqa: E402

NAAM = "fathom-wacht"
ag = bord.Agent(NAAM)
DAGEN = int(os.environ.get("FATHOM_WACHT_DAGEN", "14"))


def deals_index():
    d = pipedrive.get("harchitects", "/deals", {"status": "open", "limit": 500})
    items = d if isinstance(d, list) else (d or {}).get("data") or []
    uit = []
    for x in items:
        titel = x.get("title", "")
        m = re.match(r"^\s*((?:26|56)\d\d)\b", titel)
        p = x.get("person_id") if isinstance(x.get("person_id"), dict) else {}
        mails = {e.get("value", "").lower() for e in (p.get("email") or []) if isinstance(e, dict)}
        uit.append({"id": x.get("id"), "titel": titel, "nummer": m.group(1) if m else "",
                    "delen": {w for w in re.split(r"[^a-z0-9]+", titel.lower()) if len(w) > 2 and not w.isdigit()},
                    "mails": mails})
    return uit


def koppel(g, deals):
    titel = g.get("title") or g.get("meeting_title") or ""
    m = re.search(r"\b((?:26|56)\d\d)\b", titel)
    if m:
        for d in deals:
            if d["nummer"] == m.group(1):
                return d, "projectnummer in de titel"
    mails = {(i.get("email") or "").lower() for i in (g.get("calendar_invitees") or g.get("invitees") or []) if isinstance(i, dict)}
    for d in deals:
        if d["mails"] & mails:
            return d, "e-mail van een deelnemer"
    delen = {w for w in re.split(r"[^a-z0-9]+", titel.lower()) if len(w) > 2}
    beste, score = None, 0
    for d in deals:
        s = len(d["delen"] & delen)
        if s > score:
            beste, score = d, s
    return (beste, f"naam in de titel ({score} woorden)") if beste and score >= 2 else (None, "")


def main():
    ag.hartslag("actief", taak="Fathom lezen")
    try:
        if not fathom.beschikbaar():
            ag.hartslag("fout", taak="geen Fathom-sleutel", detail="FATHOM_API_KEYS ontbreekt")
            return
        sinds = (datetime.now(timezone.utc) - timedelta(days=DAGEN)).strftime("%Y-%m-%dT%H:%M:%SZ")
        gesprekken = fathom.gesprekken(sinds, met_transcript=True)
        deals = deals_index()
        klaar, geplaatst, gekoppeld = [], 0, 0
        for g in gesprekken:
            gid = str(g.get("recording_id") or g.get("id") or g.get("url", "").rsplit("/", 1)[-1])
            titel = g.get("title") or g.get("meeting_title") or "(zonder titel)"
            start = (g.get("recording_start_time") or g.get("created_at") or "")[:16]
            deal, hoe = koppel(g, deals)
            tekst = fathom.transcript_tekst(g)
            pad = ""
            if deal and tekst:
                gekoppeld += 1
                salesmap = bronnen.zoek_salesmap(re.sub(r"^\s*\d{4}\s+", "", deal["titel"]), deal["nummer"])
                if salesmap:
                    naam = f"{start[:10]} Fathom transcript - {re.sub(r'[^\w\- ]+', '', titel)[:60]}.md"
                    doel = f"{salesmap}/0 Fathom/{naam}"
                    bestaand = [e for e in (bronnen.lijst(f"{salesmap}/0 Fathom", recursief=False) or []) if e.get("name") == naam]
                    if not bestaand:
                        kop = f"# {titel}\n\nFathom {start} · {g.get('url', '')}\nDossier: {deal['titel']} (deal {deal['id']}, {hoe})\n\n"
                        pad = bronnen.upload(doel, (kop + tekst).encode("utf-8"))
                        geplaatst += 1
                    else:
                        pad = doel
            klaar.append({"voor": "h-architects", "soort": "transcript", "sleutel": str(deal["id"]) if deal else "",
                          "titel": f"{start} Fathom: {titel}" + (f" · deal {deal['id']}" if deal else " · geen dossier gevonden"),
                          "uniek": f"fathom:{gid}", "verwijzing": pad or g.get("url", ""),
                          "inhoud": {"gesprek": titel, "start": start, "url": g.get("url", ""), "deal_id": deal["id"] if deal else None,
                                     "koppeling": hoe, "transcript_pad": pad, "transcript_tekens": len(tekst),
                                     "transcript": tekst[:20000] if not pad else ""}})
        uit = ag.klaarzet(klaar)
        ag.log("Fathom", "bron", f"{len(gesprekken)} gesprekken sinds {sinds[:10]}; {gekoppeld} aan een deal gekoppeld",
               "\n".join(f"{(g.get('recording_start_time') or '')[:16]} {g.get('title') or g.get('meeting_title')}" for g in gesprekken))
        ag.log("Fathom", "schrijf", f"{geplaatst} transcript(en) nieuw in een salesmap gezet; klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend")
        ag.log_verstuur()
        ag.hartslag("waakt", taak="wacht op nieuwe gesprekken", detail=f"laatste ronde: {len(gesprekken)} gesprekken, {geplaatst} transcripten geplaatst, {uit.get('nieuw', 0)} nieuw klaargezet")
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()

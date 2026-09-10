#!/usr/bin/env python3
"""De Plaudwacht (Privé) — Plaud-transcripten die in Dropbox verschijnen, klaarzetten.

De VM kan Mehdi's Plaud-opnames niet zelf oplijsten (de Plaud-koppeling is een
connector op zijn claude.ai-account). Daarom is de arbeidsverdeling:
  - een geplande Claude-routine met de Plaud- en Dropbox-connectors haalt elke
    dag de nieuwe transcripten (nooit de samenvatting) en zet ze als tekst
    (.md) in de salesmap onder "0 Plaud", of in de inbox-map als het dossier
    onduidelijk is;
  - deze runner (elk uur) ziet wat er nieuw staat, koppelt het aan de deal
    (uit het pad of de kop van het bestand) en zet het klaar voor h-architects.
Leest alleen.
"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import bronnen  # noqa: E402

NAAM = "plaud-wacht"
ag = bord.Agent(NAAM)
INBOX = os.environ.get("PLAUD_INBOX", "/Work All/000 AI Opzet/Mehdi Agents/Plaud inbox")


def main():
    ag.hartslag("actief", taak="Dropbox nakijken op Plaud-transcripten")
    try:
        klaar, gezien = [], 0
        # 1. de salesmappen: elke map "0 Plaud"
        for basis in bronnen.SALES_BASES:
            for e in bronnen.lijst(basis, recursief=False) or []:
                if e.get(".tag") != "folder":
                    continue
                map_pad = e.get("path_display")
                nummer = re.match(r"^\s*((?:26|56)\d\d)\b", e.get("name", ""))
                for f in bronnen.lijst(f"{map_pad}/0 Plaud", recursief=False) or []:
                    if f.get(".tag") != "file" or not f.get("name", "").lower().endswith((".md", ".txt")):
                        continue
                    gezien += 1
                    klaar.append({"voor": "h-architects", "soort": "transcript",
                                  "sleutel": "", "titel": f"Plaud: {f['name']} · {e.get('name')}",
                                  "uniek": f"plaud:{f.get('id') or f.get('path_lower')}",
                                  "verwijzing": f.get("path_display", ""),
                                  "inhoud": {"salesmap": map_pad, "nummer": nummer.group(1) if nummer else "",
                                             "bestand": f["name"], "gewijzigd": f.get("client_modified", "")[:16]}})
        # 2. de inbox: transcripten zonder dossier
        for f in bronnen.lijst(INBOX, recursief=False) or []:
            if f.get(".tag") != "file":
                continue
            gezien += 1
            klaar.append({"voor": "mehdi", "soort": "transcript", "sleutel": "",
                          "titel": f"Plaud zonder dossier: {f['name']}",
                          "uniek": f"plaud:{f.get('id') or f.get('path_lower')}",
                          "verwijzing": f.get("path_display", ""),
                          "inhoud": {"bestand": f["name"], "gewijzigd": f.get("client_modified", "")[:16],
                                     "actie": "zeg tegen De Regisseur bij welk dossier dit hoort"}})
        uit = ag.klaarzet(klaar)
        ag.log("Plaud", "bron", f"{gezien} transcriptbestanden gezien in de salesmappen en de inbox")
        ag.log("Plaud", "schrijf", f"klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend")
        ag.log_verstuur()
        detail = (f"laatste ronde: {gezien} bestanden, {uit.get('nieuw', 0)} nieuw" if gezien
                  else "wacht op de Plaud-routine: nog geen transcripten in 0 Plaud of de inbox")
        ag.hartslag("waakt" if gezien else "rust", taak="wacht op Plaud-transcripten", detail=detail,
                    nood=[] if gezien else [{"tekst": "De Plaud-routine op claude.ai (Plaud- en Dropbox-connector) is nog niet ingepland; zonder haar zie ik niets", "wie": "mehdi"}])
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()

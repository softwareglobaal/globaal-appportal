#!/usr/bin/env python3
"""Het Commandocentrum (Regie) — verbindt de agenda met de verslagagents.

Principe (Mehdi, 16-09-2026): een verslagagent zoekt niet achter zijn data. Het Commandocentrum leest de bak
van de Agendawacht, herkent per afspraak ter plaatse welke verslagsoort erbij hoort (werfverslag,
veiligheidscoördinatie, plaatsbeschrijving, barsten en scheuren) en stuurt op het juiste moment de impuls:

  1. zodra de afspraak bekend is  -> impuls `voorbereiding` naar de verslagagent: dossiermap zoeken, bezoekmap
                                     aanmaken, dossierkennis klaarleggen (agenda, adres, deal);
  2. na het bezoek (einde + 1 u)  -> taken voor de wachten: iCloud-wacht (foto's van die dag binnen 300 m van het
                                     adres, naar <bezoekmap>/fotos), Plaudwacht (opname en transcript, naar de
                                     bezoekmap);
  3. zodra het pakket vol is      -> impuls `verslag` naar de verslagagent: hij meldt "klaar voor verslag";
                                     de proef zelf start pas op Mehdi's knop (tokens).

De stand per bezoek staat op de pagina Commandocentrum van het bord (/commandocentrum). Het Commandocentrum
verandert nooit een afspraak, maakt zelf geen mappen en schrijft geen verslag.

Gebruik:
    commandocentrum.py             # ronde (cron elke 15 min op werkdagen)
    commandocentrum.py --droog     # alleen kijken en tonen, niets klaarzetten
    commandocentrum.py --sinds 2026-09-01   # ook oudere afspraken opnemen (standaard 21 dagen terug)
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Brussels")
except Exception:  # noqa: BLE001
    TZ = timezone(timedelta(hours=2))

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import verslagsoorten as vs  # noqa: E402

NAAM = "commandocentrum"
AFDELINGEN = ("h-architects", "unabo", "tkn", "harmoniebouw", "contrax", "elevait")
TERUG_DAGEN = int(os.environ.get("CC_TERUG_DAGEN", "21"))
VOORUIT_DAGEN = int(os.environ.get("CC_VOORUIT_DAGEN", "21"))
NA_BEZOEK_MIN = int(os.environ.get("CC_NA_BEZOEK_MIN", "60"))     # taken voor de wachten pas een uur na het einde
STRAAL_M = 300

ag = bord.Agent(NAAM)


def _tijd(iso):
    try:
        t = datetime.fromisoformat(iso)
        return t if t.tzinfo else t.replace(tzinfo=TZ)
    except (TypeError, ValueError):
        return None


def afspraken(sinds, tot):
    """Alle afspraken ter plaatse uit de bak van de Agendawacht (alle afdelingen, ook al opgepakte), in het venster."""
    uit, gezien = [], set()
    for afd in AFDELINGEN:
        try:
            items = bord.klaargezet_voor(afd, status="alle", n=500)
        except Exception as e:  # noqa: BLE001
            ag.log("bak", "fout", f"bak {afd} niet leesbaar: {type(e).__name__}")
            continue
        for it in items:
            if it.get("soort") != "afspraak" or it.get("van") != "agenda-wacht" or it["uniek"] in gezien:
                continue
            gezien.add(it["uniek"])
            try:
                d = json.loads(it.get("inhoud") or "{}")
            except ValueError:
                continue
            if not (sinds <= (d.get("datum") or "") <= tot):
                continue
            uit.append((it, d))
    return uit


def bord_rijen():
    try:
        return {r["uniek"]: r for r in bord.call("/api/verslagopdracht?open=alle").get("rijen", [])}
    except Exception:  # noqa: BLE001
        return {}


def bewaar(uniek, **velden):
    velden["_alleen"] = list(velden)
    bord.call("/api/verslagopdracht", {"rijen": [{"uniek": uniek, **velden}]})


def pakket_vol(pk):
    return bool(pk.get("bezoekmap")) and (pk.get("fotos") or 0) > 0 and (pk.get("transcripten") or 0) > 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--droog", action="store_true")
    p.add_argument("--sinds", default="")
    a = p.parse_args()
    nu = datetime.now(TZ)
    vandaag = nu.date().isoformat()
    sinds = a.sinds or (nu.date() - timedelta(days=TERUG_DAGEN)).isoformat()
    tot = (nu.date() + timedelta(days=VOORUIT_DAGEN)).isoformat()
    ag.hartslag("actief", taak="agenda-bak lezen", detail=f"{sinds} tot {tot}")
    try:
        lijst = afspraken(sinds, tot)
        bestaand = bord_rijen()
        nieuw, impulsen, taken, klaar, geen_soort, per_soort = [], [], [], 0, 0, {}
        noden = []
        for it, d in lijst:
            soort = vs.herken(d)
            if not soort:
                geen_soort += 1
                continue
            s = vs.SOORTEN[soort]
            per_soort[soort] = per_soort.get(soort, 0) + 1
            uniek = it["uniek"]
            klant = re.sub(r"^\s*(mehdi|siyan|shelton|angela)[^:]*:\s*", "", d.get("klant") or "", flags=re.I).strip(" -:")
            rij = {"uniek": uniek, "verslagsoort": soort, "agent": s["agent"], "afdeling": s["afdeling"],
                   "dossier": d.get("nummer") or "", "klant": klant, "adres": d.get("locatie") or "",
                   "datum": d.get("datum"), "start": d.get("start") or "", "einde": d.get("einde") or "",
                   "titel": d.get("titel") or "", "agenda": d.get("agenda") or "", "deal_id": d.get("deal_id") or ""}
            oud = bestaand.get(uniek)
            if not oud:
                nieuw.append(rij)
                oud = {**rij, "pakket": {}, "taken": [], "stand": "gepland", "dossiermap": "", "bezoekmap": "",
                       "impuls_voorbereiding_ts": "", "impuls_verslag_ts": "", "proef_pad": "", "open": 1}
            elif not oud.get("open"):
                continue
            einde = _tijd(oud.get("einde") or d.get("einde") or "")
            voorbij = bool(einde and nu >= einde + timedelta(minutes=NA_BEZOEK_MIN))
            pk = oud.get("pakket") or {}
            stand = oud.get("stand") or "gepland"
            # 1. impuls voorbereiding: één keer, meteen
            if not oud.get("impuls_voorbereiding_ts"):
                if s["eigen_keten"] and not rij["dossier"]:
                    noden.append({"tekst": f"{rij['datum']}: werfbezoek zonder dossiernummer in de titel ({rij['titel'][:60]}); "
                                           "de werfverslagketen kan zonder nummer niet volgen. Titel aanvullen.", "wie": "mehdi"})
                else:
                    impulsen.append({"voor": s["agent"], "soort": "impuls", "sleutel": rij["dossier"] or uniek,
                                     "titel": f"voorbereiding {s['label'].lower()} {rij['datum']} {rij['dossier'] or rij['klant']}"[:300],
                                     "inhoud": {"fase": "voorbereiding", "uniek": uniek, **rij, "straal_m": STRAAL_M},
                                     "verwijzing": it.get("verwijzing") or "", "uniek": f"cc:{uniek}:voorbereiding"})
                    if not a.droog:
                        bewaar(uniek, impuls_voorbereiding_ts=nu.isoformat(), stand="gepland" if rij["datum"] >= vandaag else stand)
            # 2. na het bezoek: taken voor de wachten, zodra de bezoekmap bekend is
            bezoekmap = oud.get("bezoekmap") or ""
            if voorbij and not s["eigen_keten"]:
                bestaande_taken = {t.get("voor") for t in (oud.get("taken") or [])}
                if bezoekmap:
                    nieuwe = []
                    if not pk.get("fotos") and "icloud-wacht" not in bestaande_taken:
                        nieuwe.append({"voor": "icloud-wacht", "soort": "taak", "sleutel": rij["dossier"] or uniek,
                                       "titel": f"Foto's van {rij['datum']} binnen {STRAAL_M} m van {rij['adres']} ({s['label'].lower()}) naar de bezoekmap"[:300],
                                       "inhoud": {"dossier": rij["dossier"] or rij["klant"], "datum": rij["datum"], "adres": rij["adres"],
                                                  "bezoekmap": bezoekmap, "van_tijd": rij["start"], "tot_tijd": rij["einde"], "verslagsoort": soort},
                                       "verwijzing": bezoekmap, "uniek": f"cc:{uniek}:icloud-wacht"})
                    if not pk.get("transcripten") and "plaud-wacht" not in bestaande_taken:
                        nieuwe.append({"voor": "plaud-wacht", "soort": "taak", "sleutel": rij["dossier"] or uniek,
                                       "titel": f"Plaud-opname van {rij['datum']} ({rij['adres']}, {s['label'].lower()}): transcript in de bezoekmap"[:300],
                                       "inhoud": {"dossier": rij["dossier"] or rij["klant"], "datum": rij["datum"], "adres": rij["adres"],
                                                  "bezoekmap": bezoekmap, "van_tijd": rij["start"], "tot_tijd": rij["einde"], "verslagsoort": soort},
                                       "verwijzing": bezoekmap, "uniek": f"cc:{uniek}:plaud-wacht"})
                    if nieuwe:
                        taken += nieuwe
                        if not a.droog:
                            bewaar(uniek, taken=(oud.get("taken") or []) + [{"voor": t["voor"], "uniek": t["uniek"], "titel": t["titel"]} for t in nieuwe],
                                   stand="verzamelen" if stand in ("gepland", "voorbereid") else stand)
                elif stand in ("gepland", "voorbereid") and oud.get("impuls_voorbereiding_ts"):
                    noden.append({"tekst": f"{rij['datum']} {s['label'].lower()} {rij['dossier'] or rij['klant']}: bezoek voorbij, maar nog geen "
                                           "bezoekmap (dossiermap niet gevonden?). Zet de dossiermap op de pagina Commandocentrum.", "wie": "mehdi"})
                # 3. pakket vol: impuls verslag, één keer
                if pakket_vol(pk) and not oud.get("impuls_verslag_ts") and not oud.get("proef_pad"):
                    impulsen.append({"voor": s["agent"], "soort": "impuls", "sleutel": rij["dossier"] or uniek,
                                     "titel": f"verslag {s['label'].lower()} {rij['datum']} {rij['dossier'] or rij['klant']}: pakket is vol"[:300],
                                     "inhoud": {"fase": "verslag", "uniek": uniek, **rij, "bezoekmap": bezoekmap, "pakket": pk},
                                     "verwijzing": bezoekmap, "uniek": f"cc:{uniek}:verslag"})
                    if not a.droog:
                        bewaar(uniek, impuls_verslag_ts=nu.isoformat(), stand="pakket klaar")
                    klaar += 1
                elif pakket_vol(pk) and stand == "verzamelen" and not a.droog:
                    bewaar(uniek, stand="pakket klaar")
        if a.droog:
            print(json.dumps({"nieuw": nieuw, "impulsen": impulsen, "taken": taken, "noden": noden}, ensure_ascii=False, indent=1))
            return
        if nieuw:
            bord.call("/api/verslagopdracht", {"rijen": nieuw})
        uit_i = ag.klaarzet(impulsen) if impulsen else {"nieuw": 0, "bestaand": 0}
        uit_t = ag.klaarzet(taken) if taken else {"nieuw": 0, "bestaand": 0}
        ag.log(f"ronde {vandaag}", "bron", f"{len(lijst)} afspraken in de bak ({sinds} tot {tot}); {sum(per_soort.values())} met een verslagsoort, "
               f"{geen_soort} zonder (online, intern of geen dienst): " + ", ".join(f"{k} {v}" for k, v in sorted(per_soort.items())),
               "\n".join(f"{d.get('datum')} {d.get('titel','')[:70]} -> {vs.herken(d) or '-'}" for _, d in lijst))
        ag.log(f"ronde {vandaag}", "schrijf", f"{len(nieuw)} nieuwe bezoeken op de pagina; impulsen {uit_i.get('nieuw', 0)} nieuw; "
               f"taken voor de wachten {uit_t.get('nieuw', 0)} nieuw; {klaar} pakket(ten) vol",
               "\n".join(f"{x['voor']}: {x['titel']}" for x in impulsen + taken))
        ag.log_verstuur()
        ag.hartslag("waakt", taak="agenda in het oog voor verslagen",
                    detail=f"{sum(per_soort.values())} bezoeken met verslag in het venster; {len(nieuw)} nieuw; {klaar} pakket(ten) vol",
                    nood=noden[:8])
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()

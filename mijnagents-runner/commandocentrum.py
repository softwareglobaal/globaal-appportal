#!/usr/bin/env python3
"""Het Commandocentrum (Regie) — verbindt de agenda met de verslagagents.

Principe (Mehdi, 16-09-2026): een verslagagent zoekt niet achter zijn data. Het Commandocentrum leest de bak
van de Agendawacht, herkent per afspraak ter plaatse welke verslagsoort erbij hoort (werfverslag,
veiligheidscoördinatie, plaatsbeschrijving, barsten en scheuren) en stuurt op het juiste moment de impuls:

  1. zodra de afspraak bekend is  -> impuls `voorbereiding` naar de verslagagent: dossiermap zoeken, bezoekmap
                                     aanmaken, dossierkennis klaarleggen (agenda, adres, deal);
  2. na het bezoek (einde + 1 u)  -> taken voor de wachten: iCloud-wacht (foto's van die dag binnen 300 m van het
                                     adres, naar <bezoekmap>/fotos), Plaudwacht (opname en transcript, naar de
                                     bezoekmap). Voor barsten en scheuren gaat Plaud na +1 uur; de iPhone-fototaak
                                     volgt na het fotovenster (agenda -30/+180 minuten) plus 15 minuten. Die taken
                                     wijzen naar de werkelijke TKN-submappen en volgen latere agendawijzigingen;
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
import posixpath
import re
import sys
import urllib.parse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Brussels")

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
WACHTRONDE_MIN = {"icloud-wacht": 30, "plaud-wacht": 60}

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


def taakinhoud(rij, oud, s, soort):
    """Inhoud voor (iCloud, Plaud), zonder bijwerkingen; None bij een onbruikbaar TKN-bezoek.

    Andere verslagsoorten behouden hun oorspronkelijke zeven velden en veldvolgorde. Het TKN-venster ligt
    op de lokale bezoekdag en sluit de andere kalenderdag uit, ook wanneer de agenda laat eindigt.
    """
    basis = {"dossier": rij["dossier"] or rij["klant"], "datum": rij["datum"], "adres": rij["adres"],
             "bezoekmap": oud.get("bezoekmap") or "", "van_tijd": rij["start"], "tot_tijd": rij["einde"],
             "verslagsoort": soort}
    if not s.get("submappen"):
        return basis.copy(), basis.copy()

    dossiermap = oud.get("dossiermap") or ""
    mapnr = vs.tkn_pad(dossiermap, (s.get("basismappen") or [""])[0]) if dossiermap else ""
    start, einde = _tijd(rij.get("start")), _tijd(rij.get("einde"))
    try:
        bezoekdag = date.fromisoformat(rij["datum"])
    except (TypeError, ValueError):
        return None
    if (not mapnr or not oud.get("id") or "T" not in str(rij.get("start") or "")
            or "T" not in str(rij.get("einde") or "") or not start or not einde):
        return None
    start, einde = start.astimezone(TZ), einde.astimezone(TZ)
    if einde <= start or start.date() != bezoekdag or einde.date() < bezoekdag:
        return None
    dag_start = datetime.combine(bezoekdag, datetime.min.time(), TZ)
    dag_einde = dag_start.replace(hour=23, minute=59, second=59)
    van = max(dag_start, start - timedelta(minutes=s.get("fotovenster_min", (30, 180))[0]))
    tot = min(dag_einde, einde + timedelta(minutes=s.get("fotovenster_min", (30, 180))[1]))
    if tot <= van:
        return None
    pk = oud.get("pakket") or {}
    submappen = s["submappen"].copy()
    submappen.update({k: v for k, v in (pk.get("submappen") or {}).items() if v})
    fotomap, plaudmap = submappen.get("fotos"), submappen.get("plaud")
    if not fotomap or not plaudmap:
        return None
    dossier = str(rij.get("dossier") or "")
    postcodes = re.findall(r",\s*(\d{4})\b", str(rij.get("adres") or ""))
    dossier_is_postcode = len(dossier) == 4 and dossier in postcodes
    basis.update({"dossier": dossier if re.fullmatch(r"[0-9]{4,6}", dossier) and not dossier_is_postcode else mapnr,
                  "mapnummer": mapnr, "projectmap": dossiermap, "bezoekmap": dossiermap,
                  "firma": rij.get("firma") or "",
                  "start": van.isoformat(), "einde": tot.isoformat(),
                  "reden": "barsten en scheuren: agendavenster -30/+180 min, vaste straal 300 m",
                  "doelmap": posixpath.join(dossiermap, fotomap, s["fotodatummap"].format(datum=rij["datum"])),
                  "plaud_doelmap": posixpath.join(dossiermap, plaudmap),
                  "transcriptnaam": s["transcriptnaam"].format(datum=rij["datum"]),
                  "fotoformaat": s["fotoformaat"], "project_ref": f"tkn:{mapnr}",
                  "bezoek_ref": f"verslagopdracht:{oud['id']}", "straal_m": STRAAL_M})
    return basis.copy(), basis.copy()


def bordtaak(uniek):
    """Lees ook een afgehandelde taak; alleen de status klaar verbergt een vroegere opdracht."""
    if not uniek:
        return None
    pad = "/api/klaarzet?" + urllib.parse.urlencode({"uniek": uniek, "status": "alle"})
    return next((it for it in bord.call(pad).get("items", [])
                 if it.get("uniek") == uniek and it.get("van") == NAAM), None)


def taak_bron_gewijzigd(oud_item, nieuwe_inhoud):
    """Een afgeronde levering vraagt alleen een nieuwe taak na een echte bronwijziging."""
    oude_inhoud = oud_item.get("inhoud") or {}
    if isinstance(oude_inhoud, str):
        try:
            oude_inhoud = json.loads(oude_inhoud)
        except ValueError:
            oude_inhoud = {}
    if not isinstance(oude_inhoud, dict):
        return True
    velden = ("datum", "adres", "dossier", "firma", "start", "einde", "van_tijd", "tot_tijd",
              "bezoekmap", "doelmap", "plaud_doelmap", "mapnummer")
    return any(oude_inhoud.get(k) != nieuwe_inhoud.get(k) for k in velden)


def _taakbesluit(taak, oude_taak, bord_item, bron_aanwezig, gemeten_ts="", nu=None):
    """Geef de taak of de reden waarom een ontbrekende bron niet meer heropent."""
    if not oude_taak:
        return taak, None
    basis = taak["uniek"]
    oud_uniek = oude_taak.get("uniek") or basis
    if not bord_item or bord_item.get("status") == "klaar":
        taak["uniek"] = oud_uniek
        return taak, None
    bron_gewijzigd = taak_bron_gewijzigd(bord_item, taak["inhoud"])
    if (bron_aanwezig and bord_item.get("status") == "opgepakt" and bord_item.get("opgepakt_door") == taak["voor"]
            and not bron_gewijzigd):
        return None, None
    if not bron_gewijzigd:
        afgevinkt = _tijd(bord_item.get("opgepakt_ts"))
        gemeten = _tijd(gemeten_ts)
        wachtduur = timedelta(minutes=WACHTRONDE_MIN[taak["voor"]])
        if bron_aanwezig or not gemeten:
            return None, None
        if not afgevinkt:
            return None, "tijdstip"
        if gemeten < afgevinkt + wachtduur:
            return None, None
    match = re.fullmatch(re.escape(basis) + r":([1-9][0-9]*)", oud_uniek)
    if oud_uniek != basis and not match:
        return None, "sleutel" if not bron_aanwezig else None
    nummer = int(match.group(1)) + 1 if match else 2
    if nummer > 4:
        return None, "limiet" if not bron_aanwezig else None
    if nummer > 2:
        # Oudere rijen hebben nog geen heropend_ts. Het bordtijdstip is dan de
        # beste bron; opgepakt_ts is een voorzichtige terugval voor oude taken.
        tijdstippen = (oude_taak.get("heropend_ts"), bord_item.get("ts"), bord_item.get("opgepakt_ts"))
        laatst = next((tijd for waarde in tijdstippen if (tijd := _tijd(waarde))), None)
        if not laatst:
            return None, "tijdstip" if not bron_aanwezig else None
        if laatst.astimezone(TZ).date() >= (nu or datetime.now(TZ)).astimezone(TZ).date():
            return None, None
    taak["uniek"] = f"{basis}:{nummer}"
    return taak, None


def taak_voor_nieuwe_ronde(taak, oude_taak, bord_item, bron_aanwezig, gemeten_ts="", nu=None):
    """Hergebruik open taken; heropen hoogstens eenmaal per Brusselse dag en driemaal in totaal."""
    return _taakbesluit(taak, oude_taak, bord_item, bron_aanwezig, gemeten_ts, nu)[0]


def heropennood(dossier, bron, blokkade):
    if blokkade == "limiet":
        return f"{dossier}: {bron} blijft ontbreken na 3 pogingen; kijk het na"
    if blokkade == "tijdstip":
        return f"{dossier}: {bron} blijft ontbreken; tijdstip van de vorige taak onbekend; kijk het na"
    return f"{dossier}: {bron} blijft ontbreken; taaknummer van de laatste heropening onbekend; kijk het na"


def gepauzeerde_taak(oude_taak, bord_item, reden):
    """Houd een TKN-taak open, maar maak het oude doel onbruikbaar zolang de agenda geen opdracht toelaat."""
    if not bord_item or bord_item.get("status") != "klaar":
        return None
    inhoud = bord_item.get("inhoud") or {}
    if isinstance(inhoud, str):
        try:
            inhoud = json.loads(inhoud)
        except ValueError:
            inhoud = {}
    if not isinstance(inhoud, dict):
        inhoud = {}
    inhoud = {**inhoud, "bezoekmap": "", "projectmap": "", "doelmap": "", "plaud_doelmap": "",
              "pauze_reden": reden}
    return {"voor": oude_taak["voor"], "soort": "taak", "sleutel": bord_item.get("sleutel") or "",
            "titel": bord_item.get("titel") or oude_taak.get("titel") or "Wacht op geldig bezoek",
            "inhoud": inhoud, "verwijzing": "", "uniek": oude_taak["uniek"]}


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
            if s.get("submappen"):
                # De map ligt bij TKN, maar de agendacode bepaalt de zakelijke firma van de opname.
                rij["firma"] = d.get("firma") or ""
            oud = bestaand.get(uniek)
            if not oud:
                nieuw.append(rij)
                oud = {**rij, "pakket": {}, "taken": [], "stand": "gepland", "dossiermap": "", "bezoekmap": "",
                       "impuls_voorbereiding_ts": "", "impuls_verslag_ts": "", "proef_pad": "", "open": 1}
                if not a.droog:
                    # de rij moet bestaan vóór de gerichte bijwerkingen hieronder (les van de eerste ronde: ts bleef leeg)
                    bord.call("/api/verslagopdracht", {"rijen": [rij]})
            elif not oud.get("open"):
                continue
            else:
                # agenda kan veranderd zijn (adres, titel, klant): de rij volgt de agenda
                bord.call("/api/verslagopdracht", {"rijen": [rij]}) if not a.droog else None
            einde = _tijd(rij["einde"] if s.get("submappen") else (oud.get("einde") or d.get("einde") or ""))
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
                        bewaar(uniek, impuls_voorbereiding_ts=nu.isoformat())   # de stand is van de verslagagent
            # 2. na het bezoek: taken voor de wachten, zodra de bezoekmap bekend is
            bezoekmap = oud.get("bezoekmap") or ""
            if voorbij and s["eigen_keten"] and stand in ("gepland", "voorbereid") and not a.droog:
                bewaar(uniek, stand="werfverslagketen")   # verder op de pagina Werfverslagen
            if voorbij and not s["eigen_keten"] and not s.get("submappen"):
                bestaande_taken = {t.get("voor") for t in (oud.get("taken") or [])}
                if bezoekmap:
                    nieuwe = []
                    inhoud_icloud, inhoud_plaud = taakinhoud(rij, oud, s, soort)
                    if not pk.get("fotos") and "icloud-wacht" not in bestaande_taken:
                        nieuwe.append({"voor": "icloud-wacht", "soort": "taak", "sleutel": rij["dossier"] or uniek,
                                       "titel": f"Foto's van {rij['datum']} binnen {STRAAL_M} m van {rij['adres']} ({s['label'].lower()}) naar de bezoekmap"[:300],
                                       "inhoud": inhoud_icloud,
                                       "verwijzing": bezoekmap, "uniek": f"cc:{uniek}:icloud-wacht"})
                    if not pk.get("transcripten") and "plaud-wacht" not in bestaande_taken:
                        nieuwe.append({"voor": "plaud-wacht", "soort": "taak", "sleutel": rij["dossier"] or uniek,
                                       "titel": f"Plaud-opname van {rij['datum']} ({rij['adres']}, {s['label'].lower()}): transcript in de bezoekmap"[:300],
                                       "inhoud": inhoud_plaud,
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
            if s.get("submappen") and not s["eigen_keten"]:
                inhoud = taakinhoud(rij, oud, s, soort)
                oude_taken = {t.get("voor"): t for t in (oud.get("taken") or []) if t.get("voor") in ("icloud-wacht", "plaud-wacht")}
                bord_taken = {wacht: bordtaak(taak.get("uniek")) for wacht, taak in oude_taken.items()}
                foto_nodig = bool(inhoud and nu >= _tijd(inhoud[0]["einde"]) + timedelta(minutes=s["fototaak_na_min"]))
                plaud_nodig = bool(inhoud and voorbij)
                # Een telling kan een gedeeltelijke levering zijn. De wachten ronden zelf af:
                # iCloud schrijft eerst 00 fotos.md, Plaud bevestigt de juiste opname.
                if not inhoud:
                    for wacht, oude_taak in oude_taken.items():
                        gepauzeerd = gepauzeerde_taak(oude_taak, bord_taken[wacht], "dossiermap of agendatijden onbruikbaar")
                        if gepauzeerd:
                            taken.append(gepauzeerd)
                    if voorbij or oude_taken:
                        noden.append({"tekst": f"{rij['datum']} barsten en scheuren: dossiermap of agendatijden onbruikbaar; "
                                               "geen taken voor de wachten", "wie": "mehdi"})
                    continue
                inhoud_foto, inhoud_plaud = inhoud
                nieuwe = []
                for wacht, nodig in (("icloud-wacht", foto_nodig), ("plaud-wacht", plaud_nodig)):
                    if not nodig and wacht in oude_taken:
                        gepauzeerd = gepauzeerde_taak(oude_taken[wacht], bord_taken[wacht], "agendavenster nog niet verstreken")
                        if gepauzeerd:
                            nieuwe.append(gepauzeerd)
                if foto_nodig:
                    taak = {"voor": "icloud-wacht", "soort": "taak", "sleutel": inhoud_foto["dossier"],
                            "titel": f"iPhone-foto's van {rij['datum']} binnen {STRAAL_M} m van {rij['adres']} ({s['label'].lower()}) naar {inhoud_foto['doelmap']}"[:300],
                            "inhoud": inhoud_foto, "verwijzing": inhoud_foto["doelmap"],
                            "uniek": f"cc:{uniek}:icloud-wacht"}
                    taak, blokkade = _taakbesluit(taak, oude_taken.get("icloud-wacht"), bord_taken.get("icloud-wacht"),
                                                  (pk.get("fotos_iphone") or 0) > 0, pk.get("gemeten_ts"), nu)
                    if taak:
                        nieuwe.append(taak)
                    elif blokkade:
                        noden.append({"tekst": heropennood(inhoud_foto["mapnummer"], "iPhone-fotolevering", blokkade),
                                      "wie": "mehdi"})
                if plaud_nodig:
                    taak = {"voor": "plaud-wacht", "soort": "taak", "sleutel": inhoud_plaud["dossier"],
                            "titel": f"Plaud-opname van {rij['datum']} ({rij['adres']}, {s['label'].lower()}): transcript in {inhoud_plaud['plaud_doelmap']}"[:300],
                            "inhoud": inhoud_plaud, "verwijzing": inhoud_plaud["plaud_doelmap"],
                            "uniek": f"cc:{uniek}:plaud-wacht"}
                    taak, blokkade = _taakbesluit(taak, oude_taken.get("plaud-wacht"), bord_taken.get("plaud-wacht"),
                                                  (pk.get("transcripten") or 0) > 0, pk.get("gemeten_ts"), nu)
                    if taak:
                        nieuwe.append(taak)
                    elif blokkade:
                        noden.append({"tekst": heropennood(inhoud_plaud["mapnummer"], "Plaud-opname", blokkade),
                                      "wie": "mehdi"})
                if nieuwe:
                    taken += nieuwe  # dezelfde uniek werkt een open taak bij; :2 herstelt een gesloten taak
                    ontbrekend = [t for t in nieuwe if t["voor"] not in oude_taken or
                                  t["uniek"] != oude_taken[t["voor"]].get("uniek")]
                    if ontbrekend and not a.droog:
                        bewaar(uniek, taken=(oud.get("taken") or []) +
                               [{"voor": t["voor"], "uniek": t["uniek"], "titel": t["titel"],
                                 **({"heropend_ts": nu.isoformat()} if re.search(r":[2-9][0-9]*$", t["uniek"]) else {})}
                                for t in ontbrekend],
                               stand="verzamelen" if stand in ("gepland", "voorbereid") else stand)
                vol = bool(oud.get("dossiermap") and (pk.get("fotos_iphone") or 0) > 0
                           and (pk.get("transcripten") or 0) > 0
                           and not any(t["voor"] == "icloud-wacht" for t in nieuwe)
                           and (bord_taken.get("icloud-wacht") or {}).get("status") == "opgepakt"
                           and (bord_taken.get("icloud-wacht") or {}).get("opgepakt_door") == "icloud-wacht"
                           and not taak_bron_gewijzigd(bord_taken["icloud-wacht"], inhoud_foto)
                           and not taak_bron_gewijzigd(bord_taken.get("plaud-wacht") or {}, inhoud_plaud))
                if voorbij and vol and not oud.get("impuls_verslag_ts") and not oud.get("proef_pad"):
                    impulsen.append({"voor": s["agent"], "soort": "impuls", "sleutel": rij["dossier"] or uniek,
                                     "titel": f"verslag {s['label'].lower()} {rij['datum']} {rij['dossier'] or rij['klant']}: pakket is vol"[:300],
                                     "inhoud": {"fase": "verslag", "uniek": uniek, **rij, "bezoekmap": oud.get("dossiermap"), "pakket": pk},
                                     "verwijzing": oud.get("dossiermap"), "uniek": f"cc:{uniek}:verslag"})
                    if not a.droog:
                        bewaar(uniek, impuls_verslag_ts=nu.isoformat(), stand="pakket klaar")
                    klaar += 1
                elif vol and stand == "verzamelen" and not a.droog:
                    bewaar(uniek, stand="pakket klaar")
        if a.droog:
            print(json.dumps({"nieuw": nieuw, "impulsen": impulsen, "taken": taken, "noden": noden}, ensure_ascii=False, indent=1))
            return
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

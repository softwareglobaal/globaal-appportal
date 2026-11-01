#!/usr/bin/env python3
"""De Plaudwacht (Privé), versie 3 (verbeteropdracht v1.0, 12-10-2026).

Elk uur op de VM. De opnames zelf staan in één archief op de Mac (Dropbox, `Data uit Mehdi/Plaud`),
opgehaald uit de Plaud-API door plaud/plaud_haal_alles.py. De Mac zet het manifest, de status en per
opname transcript.json in mijnagents-data/plaud-invoer (plaud/plaud_invoer_push.sh). Ik lees alleen
dat; geen audio, geen tweede archief, geen getekende links.

Per ronde:
  1. invoer lezen: manifest en status van de Mac; oude inboxbestanden van de claude.ai-routine alleen
     als hun Plaud-id niet in het manifest staat, en alleen via het opnamecontract (zonder opnametijd:
     herstel, nooit de wijzigingsdatum van het bestand)
  2. zoektaken van het Commandocentrum en de werfverslagvoorbereider: bezoekmap valideren uit de taak,
     opname zoeken op opnametijd (zie plaud/zoektaak.py)
  3. per opname: context (alleen overlappende agenda, gestructureerde locatie), herkenning door het
     model alleen bij een nieuw transcript, dossierbeslissing op bewijs (plaud/dossier.py), dan de
     publicaties eerst vastleggen in mijnagents-data/plaud-staat/<id>.json en pas daarna uitvoeren:
     gesprekkentabel, klaarzet, dossierkopie, bezoekmap. Een herstart doet alleen wat open staat.
  4. toezicht: leeftijd van de invoer, aanmelding op de Mac, wachtende transcripten, open publicaties
     en de oudste open zoektaak; noden zonder teller (N10)

Een zoektaak gaat pas op opgepakt na een bevestigde levering in de bezoekmap.

Foutcode: 0 alles goed, 3 invoer ontbreekt of is verouderd, 4 een of meer opnames of publicaties mislukt.
"""
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
sys.path.insert(0, os.path.join(HIER, "plaud"))
import bord  # noqa: E402
import bronnen  # noqa: E402
import locatiecontext as LC  # noqa: E402  gestructureerde locatiecontext, met startgrens (opdracht v1.4)
import verslagsoorten  # noqa: E402

import archief  # noqa: E402  (plaud/)
import context as CTX  # noqa: E402
import contract  # noqa: E402
import dossier  # noqa: E402
import manifest  # noqa: E402
import staat  # noqa: E402
import zoektaak  # noqa: E402

NAAM = "plaud-wacht"
ag = bord.Agent(NAAM)
DATA = os.path.expanduser(os.environ.get("MIJNAGENTS_DATA", "~/appportal/mijnagents-data"))
INVOER = os.environ.get("PLAUD_INVOER", os.path.join(DATA, "plaud-invoer"))
STAAT = os.environ.get("PLAUD_STAAT", os.path.join(DATA, "plaud-staat"))
INBOX = os.environ.get("PLAUD_INBOX", "/Work All/000 AI Opzet/Mehdi Agents/Plaud inbox")
# PLAUD-8: de laatst gemelde bevinding per open zoektaak; niet in STAAT, want daar is elk .json-bestand een opname
GEMELD = os.environ.get("PLAUD_GEMELD", os.path.join(DATA, "plaud-zoektaken-gemeld.json"))
# Opnames van vóór deze dag worden niet opnieuw herkend en gepubliceerd (geen volledige herverwerking);
# voor zoektaken blijven ze vindbaar.
SINDS = os.environ.get("PLAUD_WACHT_SINDS", "2026-10-01")
MAX_HERKENNING = int(os.environ.get("PLAUD_MAX_HERKENNING", "15"))
INVOER_MAX_UUR = 3
ARCHIEF_OP_MAC = "Data uit Mehdi/Plaud"

OK, INVOER_FOUT, DEELS = 0, 3, 4
# Versie van de herkenningsopdracht: verandert ze, dan is dat andere modelinput.
HERKEN_VERSIE = 2


def _nu():
    return datetime.now(timezone.utc)


def kop_van(tekst):
    """De kopregels uit een bestand van de oude routine (plaud_id, account, start, duur_minuten, naam_in_plaud, dossier)."""
    uit = {}
    for regel in tekst.splitlines()[:12]:
        m = re.match(r"^\s*([a-z_]+)\s*:\s*(.+?)\s*$", regel)
        if m:
            uit[m.group(1)] = m.group(2)
    return uit


# --------------------------------------------------------------- invoer ---
def lees_invoer():
    """(manifest of None, status van de Mac of {})."""
    return manifest.lees(INVOER), archief.lees_json(os.path.join(INVOER, "00 status.json")) or {}


def uitingen_van(o):
    data = archief.lees_json(os.path.join(INVOER, (o.get("archief") or {}).get("map") or "-", "transcript.json"))
    return data if isinstance(data, list) else None


def tekst_van(uitingen):
    def klok(ms):
        s = int(ms or 0) // 1000
        return "%02d:%02d:%02d" % (s // 3600, s // 60 % 60, s % 60)
    return "\n".join(f"[{klok(u.get('start_time'))}] {u.get('speaker') or 'Speaker ?'}: {(u.get('content') or '').strip()}"
                     for u in uitingen or [])


def oude_inbox(bekend):
    """Bestanden van de oude claude.ai-routine, alleen voor ids die niet in het manifest staan.
    Geeft (opnames, herstel). Een pad in de kop (bezoekmap:) is een aanwijzing, geen schrijfrecht."""
    uit, herstel = [], []
    for e in bronnen.lijst(INBOX, recursief=False) or []:
        if e.get(".tag") != "file" or not e.get("name", "").lower().endswith((".md", ".txt")) or e["name"].startswith("00 "):
            continue
        tekst = bronnen.download(e["path_lower"]).decode("utf-8", "replace")
        kop = kop_van(tekst)
        try:
            c = contract.opname({"plaud_id": kop.get("plaud_id"), "start": kop.get("start"), "duur_minuten": kop.get("duur_minuten"),
                                 "naam_in_plaud": kop.get("naam_in_plaud") or e["name"], "account": kop.get("account")},
                                transcript={"staat": "aanwezig"}, bron="oude-inbox")
        except contract.Herstel as ex:
            herstel.append({"bestand": e["name"], "reden": str(ex)})
            continue
        if c["plaud_id"] in bekend:
            continue
        kopregels = set(tekst.splitlines()[:12])
        romp = "\n".join(r for r in tekst.splitlines() if r not in kopregels or not re.match(r"^\s*[a-z_]+\s*:", r))
        c.update(toestand="alleen_transcript", bron_bestand=e.get("path_display", ""), kop_dossier=kop.get("dossier", ""))
        uit.append((c, romp.strip()))
    return uit, herstel


# -------------------------------------------------------------- context ---
def klaarzet_items():
    """De afspraken op het bord. Tot 12-10-2026 waren dit de 500 nieuwste items van álle agents, waardoor een
    afspraak van tien dagen eerder wegviel (1 oktober: UNAB 46118 overlapte de opname, maar werd niet gezien)."""
    try:
        items = bord.call("/api/klaarzet?status=alle&soort=afspraak&n=500").get("items", [])
        return [i for i in items if i.get("soort") == "afspraak"]
    except Exception:  # noqa: BLE001
        return []


def verzoeken_beoordelen(verzoeken, opnames, items):
    """Verzoeken van De Contractmaker (soort verzoek, uniek verzoek:<deal>:<datum>:<soort>) hebben geen
    bezoekmap en geen tijdvenster. Alleen een opname die een afspraak met de naam van de klant overlapt komt
    in aanmerking; dezelfde dag alleen is geen bevestiging. Ook dan levert De Plaudwacht niet zelf: de
    bestemming in de salesmap bevestigt Mehdi (nacontrole v1.1). Geeft uitkomsten."""
    uit = []
    for v in verzoeken:
        m = re.match(r"verzoek:(\d+):(\d{4}-\d{2}-\d{2}):(.+)$", v.get("uniek") or "")
        klant = (v.get("titel") or "").split(":")[0].strip()
        if not m or len(klant) < 3:
            uit.append({"verzoek": v.get("id"), "uitkomst": "onleesbaar", "reden": "geen deal, datum of klantnaam"})
            continue
        datum = m.group(2)
        vensters = []
        for it in items:
            i = zoektaak.inhoud_van(it)
            if (i.get("start") or "")[:10] == datum and klant.lower() in (i.get("titel") or it.get("titel") or "").lower():
                vensters.append((i["start"], i.get("einde") or i["start"]))
        if not vensters:
            uit.append({"verzoek": v.get("id"), "uitkomst": "niet_gevonden", "reden": f"geen afspraak met {klant} op {datum}"})
            continue
        kand = []
        for o in opnames:
            for a, b_ in vensters:
                taak = {"inhoud": {"datum": datum, "van_tijd": a, "tot_tijd": b_}}
                if zoektaak.beoordeel(taak, [o], {}, {}).get("uitkomst") in ("gevonden", "wacht_op_transcript"):
                    kand.append(o["plaud_id"])
        tijden = ", ".join(f"{a[11:16]}-{b_[11:16]}" for a, b_ in vensters)
        uit.append({"verzoek": v.get("id"), "uitkomst": "ter_beoordeling" if kand else "niet_gevonden", "kandidaten": sorted(set(kand)),
                    "reden": (f"opname overlapt de afspraak met {klant} ({tijden}); Mehdi bevestigt de bestemming" if kand
                              else f"geen Plaud-opname rond de afspraak met {klant} ({datum} {tijden})")})
    return uit


def context_op(start_iso, duur_minuten=0, items=None):
    """(overlappende afspraken, locatiezin) op het opnamemoment.

    Afspraken tellen alleen als ze de opname overlappen (plaud/context.py); dezelfde dag op een ander uur
    is geen bevestiging. De locatie komt uit de gestructureerde context van de tegel (koppelingen/
    locatiecontext.py): alleen dagen vanaf 3-10-2026, alleen 'auto bij project' met zekerheid en bewijs."""
    if not start_iso:
        return [], ""
    if items is None:
        items = klaarzet_items()
    try:
        t = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        if not t.tzinfo:
            t = t.replace(tzinfo=CTX.BRUSSEL)
        afspraken = CTX.afspraken_op(items, t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), duur_minuten)
    except ValueError:
        afspraken = []
    plek = LC.beschrijf(LC.verblijf_op(start_iso))
    return afspraken, plek


def verslagsoort_van(tekst, titel):
    t = f"{titel} {tekst[:1500]}".lower()
    for naam, s in verslagsoorten.SOORTEN.items():
        if any(w in t for w in s.get("trefwoorden") or ()):
            return naam
    return ""


# ------------------------------------------------------------ zoektaken ---
def tekst_en_uitingen(o, romp):
    """(uitingen of None, leesbare tekst). romp: de tekst van een oud inboxbestand, anders None."""
    if romp is not None:
        return None, romp
    uitingen = uitingen_van(o)
    return uitingen, tekst_van(uitingen) if uitingen else ""


def eigen_bewijs(o, uitingen, tekst, items):
    """(bewijzen, afspraken): bewijs uit de opname zelf, zonder zoektaak, model of locatie."""
    afspraken, _ = context_op(o["start_utc"], o.get("duur_minuten") or 0, items)
    b = (dossier.uit_tekst("titel", o.get("naam_in_plaud") or "", "vergadertitel")
         + (dossier.uit_tekst("openingszin", dossier.openingszin(uitingen) if uitingen else tekst[:600], "vergadertitel") if tekst else [])
         + dossier.uit_agenda(afspraken)
         # het veld dossier: in een kop is een uitdrukkelijk dossierveld: gecontroleerd, ook al leest de nummerlezer het als los nummer
         + ([dict(x, zeker=True) for x in dossier.uit_tekst("kop", o["kop_dossier"], "nummerveld")] if o.get("kop_dossier") else []))
    return b, afspraken


def zoektaken_beoordelen(taken, opnames, st_obj, items):
    """(per plaud_id: [taak], uitkomsten). opnames: [(contract, romp)]. Een ongeldige taak levert niets op.

    PLAUD-8 (T-0120): een bevinding komt alleen in het werkverslag als ze anders is dan de vorige keer (GEMELD). Op 29-10
    waren 384 van de 408 regels elk uur dezelfde 16 zoektaakbevindingen. De uitkomsten zelf veranderen niet."""
    per_id, uitkomsten = {}, []
    gemeld, nu_gemeld = archief.lees_json(GEMELD) or {}, {}
    contracten = [o for o, _ in opnames]
    beslissingen = {o["plaud_id"]: (st_obj.lees(o["plaud_id"]).get("beslissing") or {}) for o in contracten}
    dagen = {zoektaak.inhoud_van(t).get("datum") for t in taken}
    bewijs = {}
    for o, romp in opnames:
        if o["start_brussel"][:10] in dagen:
            uitingen, tekst = tekst_en_uitingen(o, romp)
            bewijs[o["plaud_id"]] = {b["nummer"] for b in eigen_bewijs(o, uitingen, tekst, items)[0]}
    for t in taken:
        ok, reden = zoektaak.valideer_bezoekmap(t, verslagsoorten.SOORTEN)
        if not ok:
            uitkomsten.append({"taak": t.get("id"), "uitkomst": "ongeldig", "reden": reden})
            ag.log(f"taak {t.get('id')}", "fout", f"zoektaak niet uitgevoerd: {reden}")
            continue
        r = zoektaak.beoordeel(t, contracten, beslissingen, bewijs)
        r["taak"] = t.get("id")
        uitkomsten.append(r)
        bevinding = f"{r['uitkomst']}: {r['reden']}" + (f" ({', '.join(r['kandidaten'])})" if r.get("kandidaten") else "")
        nu_gemeld[str(t.get("id"))] = bevinding
        if gemeld.get(str(t.get("id"))) != bevinding:
            ag.log(f"taak {t.get('id')}", "bevinding", bevinding)
        if r["uitkomst"] in ("gevonden", "wacht_op_transcript"):
            per_id.setdefault(r["plaud_id"], []).append(t)
    if nu_gemeld != gemeld:
        try:
            archief.schrijf_json(GEMELD, nu_gemeld)
        except OSError as e:          # dan meld ik de volgende ronde opnieuw; de beoordeling zelf hangt er niet van af
            ag.log("Plaud", "fout", f"gemelde zoektaken niet bewaard: {type(e).__name__}")
    return per_id, uitkomsten


# ---------------------------------------------------------- uitvoerders ---
def _tabel(payload):
    bord.call("/api/gesprekken", {"rijen": [payload]})
    return "rij bijgewerkt"


def _klaarzet(payload):
    """Zet klaar en bevestig de werkelijk opgeslagen versie (nacontrole v1.1, P1-5). Een API die 'bestaand'
    antwoordt zonder de nieuwe beoordeling op te slaan, is geen geslaagde publicatie. Een item dat al
    opgepakt was, wordt door het bord als revisie bijgewerkt (klaarzet_revisie); dat geven we door."""
    uit = ag.klaarzet([dict(payload)]) or {}
    gelezen = bord.call("/api/klaarzet?" + urllib.parse.urlencode({"uniek": payload["uniek"], "status": "alle", "n": 5})).get("items", [])
    item = next((i for i in gelezen if i.get("uniek") == payload["uniek"]), None)
    if not item:
        raise RuntimeError("klaarzet niet bevestigd: item niet terug te lezen")
    inhoud = item.get("inhoud") or ""
    try:
        inhoud = json.loads(inhoud) if isinstance(inhoud, str) else inhoud
    except ValueError:
        pass
    verwacht = json.loads(json.dumps(payload.get("inhoud"), ensure_ascii=False))
    if item.get("voor") != payload["voor"] or inhoud != verwacht or (item.get("titel") or "") != payload["titel"][:300]:
        raise RuntimeError("klaarzet niet bevestigd: de opgeslagen versie wijkt af van de nieuwe beoordeling")
    return {"bevestigd": True, "id": item.get("id"), "status": item.get("status"),
            "herzien": int(uit.get("zakelijk_herzien", uit.get("herzien")) or 0), "nieuw": int(uit.get("nieuw") or 0)}


def _dossierkopie(payload):
    salesmap = bronnen.zoek_salesmap(re.sub(r"^\s*\d{4}\s+", "", payload["deal_titel"]), payload["projectnummer"])
    if not salesmap:
        raise RuntimeError("geen salesmap voor dit dossier")
    r = zoektaak.lever(f"{salesmap}/0 Plaud", payload["plaud_id"], payload["tekst"], bronnen, naam=payload["naam"],
                       meld=lambda tekst: ag.log(f"opname {payload['plaud_id']}", "bevinding", tekst))
    if r["uitkomst"] == "conflict":
        raise RuntimeError(r["reden"])
    return {"bevestigd": True, "pad": r["pad"], "uitkomst": r["uitkomst"], "transcript_hash": r.get("transcript_hash")}


def _bezoekmap(payload):
    r = zoektaak.lever(payload["bezoekmap"], payload["plaud_id"], payload["tekst"], bronnen,
                       naam=payload.get("naam", "transcript.txt"), scan_alle=payload.get("scan_alle", False),
                       meld=lambda tekst: ag.log(f"taak {payload['taak_id']}", "bevinding", tekst))
    if r["uitkomst"] == "conflict":
        raise RuntimeError(r["reden"])
    bord.opgepakt(payload["taak_id"], NAAM)        # pas na de bevestigde levering (id en transcriptversie)
    return {"bevestigd": True, "pad": r["pad"], "uitkomst": r["uitkomst"], "transcript_hash": r.get("transcript_hash")}


UITVOERDERS = {"tabel": _tabel, "klaarzet": _klaarzet, "dossierkopie": _dossierkopie, "bezoekmap": _bezoekmap}


# ------------------------------------------------------------ verwerken ---
def herken(o, tekst, afspraken, locatie, bewijzen, personen):
    import fathom_wacht as fw
    g = {"title": o.get("naam_in_plaud") or "", "meeting_title": o.get("naam_in_plaud") or "",
         "recording_start_time": o["start_brussel"], "recording_id": o["plaud_id"],
         "recorded_by": {"name": o.get("opgenomen_door") or "onbekend", "email": ""}, "calendar_invitees": []}
    ctx = CTX.voor_herkenning(afspraken, locatie, bewijzen, o.get("toestel", "onbekend"), o.get("account", "onbekend"))
    return fw.herken(g, tekst, personen, None, "", context=ctx, bron="plaud")


def is_prive(herk, b=None):
    """RZ3-01 (besluit van de regie, 22-10-2026: de veilige kant), zoals is_prive in fathom_wacht.py. Een opname is privé
    als de herkenning prive zegt OF de dossierbeslissing (plaud/dossier.py) het privé noemt: afdeling prive, ook met
    prive=false. Tot dan las ik voor de gesprekkentabel en het klaarzet-item (titel, inhoud, verwijzing) alleen
    herkenning['prive'], en alleen het werkverslag de dossierbeslissing; zo kwamen naam en onderwerp alsnog in een bundel
    en in de export. Hier zelf geschreven, zodat ik fathom_wacht.py pas in de ronde laad, zoals voordien."""
    herk = herk or {}
    afdeling = str(herk.get("afdeling") or "").strip().lower()
    return bool(herk.get("prive")) or afdeling in ("prive", "privé") or bool((b or {}).get("prive"))


def opdrachten_voor(o, tekst, b, herk, deal, taken, verslagsoort):
    pid, start = o["plaud_id"], o["start_brussel"]
    prive = is_prive(herk, b)                  # RZ3-01: voor de tabel, de titel, de inhoud en de verwijzing
    map_ = (o.get("archief") or {}).get("map")
    pad_mac = f"{ARCHIEF_OP_MAC}/{map_}/transcript.md" if map_ else o.get("bron_bestand", "")
    rij = {"uniek": f"plaud:{pid}", "datum": start[:10], "start": start[11:16], "minuten": int(float(o.get("duur_minuten") or 0)),
           "personen": ", ".join(herk.get("personen") or []), "bedrijf": herk.get("bedrijf", ""), "afdeling": herk.get("afdeling", ""),
           "thema": herk.get("thema", ""), "project": b["dossier"] or herk.get("project", ""), "prive": prive,
           "zekerheid": b["zekerheid"], "waarom": herk.get("waarom", ""), "archief": pad_mac, "link": pad_mac,
           "opgenomen_door": o.get("opgenomen_door") or "onbekend", "bron": "plaud"}
    klaar = {"voor": b["voor"], "soort": "transcript", "sleutel": (b["projectnummer"] or "") if b["zekerheid"] != "laag" else "",
             "titel": f"{start[:16].replace('T', ' ')} Plaud: {herk.get('hoofdpersoon') or o.get('naam_in_plaud') or 'opname'} · {herk.get('thema', '')[:60]}"
                      + (" · PRIVÉ" if prive else "") + (" · NAKIJKEN" if b["conflict"] else ""),
             "uniek": f"plaud:{pid}", "verwijzing": pad_mac, "revisie": True,
             "inhoud": {"plaud_id": pid, "datum": start[:10], "start": start[11:16], "dossier": b["dossier"], "firma": b["firma"],
                        "projectnummer": b["projectnummer"], "deal_id": deal["id"] if deal else None, "verslagsoort": verslagsoort,
                        "zekerheid": b["zekerheid"], "conflict": b["conflict"], "redenen": b["redenen"], "prive": prive,
                        "afdeling": herk.get("afdeling", ""), "thema": herk.get("thema", ""), "personen": herk.get("personen") or [],
                        "toestel": o.get("toestel", "onbekend"), "account": o.get("account", "onbekend"),
                        "opgenomen_door": o.get("opgenomen_door") or "onbekend", "transcript_pad": pad_mac}}
    if prive:
        # RZ2-01 (M3), zoals De Fathomwacht: een privé-item draagt geen persoon, onderwerp of afdeling, ook niet in de
        # verwijzing (de archiefmap heet naar de naam in Plaud). Het gaat naar De Dagbundelaar, De Levenscoach en de
        # export van het bord; met wie en waarover staan in het archief en in de gesprekkentabel (alleen beheer).
        verwijzing = f"{ARCHIEF_OP_MAC}/{start[:10]} {start[11:16].replace(':', '')} (privé) [{pid}]"
        duur = f"{rij['minuten']} min" if rij["minuten"] > 0 else "duur onbekend"
        klaar.update(titel=f"{start[:16].replace('T', ' ')} Plaud: privégesprek, {duur} · PRIVÉ" + (" · NAKIJKEN" if b["conflict"] else ""),
                     verwijzing=verwijzing,
                     inhoud={"plaud_id": pid, "datum": start[:10], "start": start[11:16], "minuten": rij["minuten"], "prive": True,
                             "archief": verwijzing})
    uit = [{"sleutel": "tabel", "soort": "tabel", "payload": rij}, {"sleutel": "klaarzet", "soort": "klaarzet", "payload": klaar}]
    if b["kopie_toegestaan"] and deal and tekst:
        wie = re.sub(r"[^A-Za-z0-9À-ÿ ,.-]+", " ", herk.get("hoofdpersoon") or "gesprek").strip()[:60]
        uit.append({"sleutel": "dossierkopie", "soort": "dossierkopie",
                    "payload": {"plaud_id": pid, "deal_titel": deal["titel"], "projectnummer": b["projectnummer"],
                                "naam": f"{start[:10]} Plaud transcript - {wie} [{pid[3:9]}].txt", "tekst": tekst}})
    # Elke zakelijke bestemming, ook de bezoekmap van een zoektaak, volgt dezelfde publicatiebeslissing
    # (nacontrole v1.1, P1-2). Een afgewezen levering laat de taak open; de reden staat in het logboek.
    if b["kopie_toegestaan"]:
        for t in taken:
            inhoud = zoektaak.inhoud_van(t)
            payload = {"plaud_id": pid, "taak_id": t["id"], "bezoekmap": inhoud["bezoekmap"].rstrip("/"), "tekst": tekst}
            if inhoud.get("plaud_doelmap"):
                payload.update(bezoekmap=inhoud["plaud_doelmap"].rstrip("/"), naam=inhoud["transcriptnaam"], scan_alle=True)
            uit.append({"sleutel": f"bezoekmap:{t['id']}", "soort": "bezoekmap",
                        "payload": payload})
    else:
        for t in taken:
            ag.log(f"taak {t['id']}", "besluit", "transcript niet geleverd: geen zakelijke bestemming toegestaan ("
                   + ("; ".join(b["redenen"]) or "beslissing") + "); de taak blijft open")
    return uit


def verwerk(o, uitingen, tekst, st_obj, items, personen, deals, taken, budget):
    """Eén opname. Geeft {"uitkomst": gedaan|wacht_op_transcript|uitgesteld|ongewijzigd, "fouten": n}."""
    pid = o["plaud_id"]
    st = st_obj.lees(pid)
    if not tekst:
        return {"uitkomst": "wacht_op_transcript", "fouten": 0}
    eigen, afspraken = eigen_bewijs(o, uitingen, tekst, items)
    verblijf = LC.gestructureerd(LC.verblijf_op(o["start_utc"]))
    # een eerder geleverde zoektaak blijft bewijs, ook als de taak niet meer open staat
    for t in taken:
        z = zoektaak.bewijs_van(t, verslagsoorten.SOORTEN)
        if z:
            st.setdefault("zoektaken", {})[str(t["id"])] = {"firma": z[0], "nummer": z[1]}
    zoek = [(z["firma"], z["nummer"]) for z in (st.get("zoektaken") or {}).values()]
    locatie = dossier.uit_locatie(verblijf)
    bewijzen = eigen + locatie + [dossier.bewijs("zoektaak", f, n, "gevalideerde zoektaak") for f, n in zoek]
    th = staat.hash_van(tekst)
    locatiezin = LC.beschrijf(LC.verblijf_op(o["start_utc"]))
    # Twee vingerafdrukken (nacontrole v1.1, P2-8): wat het model te zien krijgt, en wat de deterministische
    # beslissing bepaalt. Een andere titel of context is andere modelinput; bronherstel (Pipedrive) alleen
    # herbeoordeelt zonder nieuwe modelvraag.
    model_vinger = staat.hash_van({"transcript": th, "naam": o.get("naam_in_plaud"), "start": o["start_utc"],
                                   "afspraken": afspraken, "locatie": locatiezin, "bewijs": eigen + locatie,
                                   "toestel": o.get("toestel"), "versie": HERKEN_VERSIE})
    bekend = None if deals is None else {("HARC", str(d["nummer"])) for d in deals if d.get("nummer")}
    relevant = sorted({(x["firma"], x["nummer"]) for x in bewijzen})
    vinger = staat.hash_van({"model": model_vinger, "bewijs": bewijzen, "taken": sorted(t["id"] for t in taken),
                             "regels": dossier.VERSIE, "bron_bekend": deals is not None,
                             "bekend": [k for k in relevant if bekend and k in bekend],
                             "deals": sorted(str(d.get("id")) for d in (deals or []) if ("HARC", str(d.get("nummer"))) in relevant)})
    if st.get("vingerafdruk") == vinger and not staat.open_opdrachten(st):
        # PLAUD-12, Codex-toets 2: ook een opname die al verwerkt was, krijgt één keer de reden, zonder modelvraag
        if not is_prive(st.get("herkenning"), st.get("beslissing")):
            meld_zonder_kopie(o, st, st_obj, reden_uit_staat(st, st.get("herkenning"), st.get("beslissing") or {}, deals, tekst))
        return {"uitkomst": "ongewijzigd", "fouten": 0}
    herk = st.get("herkenning") or {}
    if herk.get("model_vinger") != model_vinger:
        if budget["over"] <= 0:
            return {"uitkomst": "uitgesteld", "fouten": 0}
        budget["over"] -= 1
        herk = herken(o, tekst, afspraken, locatiezin, eigen + locatie, personen)
        herk["transcript_hash"] = th
        herk["model_vinger"] = model_vinger
        st["herkenning"] = herk
        st_obj.bewaar(pid, st)                 # een herstart vraagt het model niet opnieuw
    model = dossier.uit_tekst("model", herk.get("project") or "", "vergadertitel")
    b = dossier.beslis(bewijzen, herk, model, bekend=bekend)
    deal, passend = None, []
    if b["firma"] == "HARC" and b["projectnummer"] and deals:
        passend = [d for d in deals if str(d.get("nummer")) == b["projectnummer"]]
        deal = passend[0] if len(passend) == 1 else None
    st["beslissing"] = b
    st["vingerafdruk"] = vinger
    staat.plan(st, opdrachten_voor(o, tekst, b, herk, deal, taken, verslagsoort_van(tekst, o.get("naam_in_plaud") or "")))
    if not b["kopie_toegestaan"]:
        staat.trek_in(st, "nieuwe beslissing staat geen zakelijke kopie toe: " + ("; ".join(b["redenen"]) or "zie beslissing"))
    st_obj.bewaar(pid, st)                     # eerst vastleggen, dan pas extern schrijven
    gedaan, fouten = staat.voer_uit(st, lambda s: st_obj.bewaar(pid, s), UITVOERDERS)
    if is_prive(herk, b):                      # RZ3-01: dezelfde regel als het klaarzet-item
        # BAS-01 en RZ2-01: van een privé-opname alleen wanneer en hoe lang, zoals De Fathomwacht; het werkverslag leest
        # een taalmodel mee en gaat naar de export. Met wie, het dossier en de redenen staan in de staat van deze opname.
        minuten = int(float(o.get("duur_minuten") or 0))
        ag.log(f"opname {o['start_brussel'][:16]}", "bevinding",
               f"privégesprek · {f'{minuten} min' if minuten > 0 else 'duur onbekend'} · voor {b['voor']}"
               + f" · {gedaan} publicatie(s), {fouten} fout")
        return {"uitkomst": "gedaan", "fouten": fouten}
    ag.log(f"opname {o['start_brussel'][:16]}", "bevinding",
           f"{herk.get('hoofdpersoon') or o.get('naam_in_plaud')} · dossier {b['dossier'] or 'geen'} ({b['zekerheid']})"
           + (" · conflict" if b["conflict"] else "") + f" · voor {b['voor']}"
           + f" · {gedaan} publicatie(s), {fouten} fout", "; ".join(b["redenen"]))
    meld_zonder_kopie(o, st, st_obj, reden_uit_staat(st, herk, b, deals, tekst))
    return {"uitkomst": "gedaan", "fouten": fouten}


def reden_uit_staat(st, herk, b, deals, tekst):
    """PLAUD-12: de reden zonder dossierkopie voor één opname, uit haar staat: een geplande kopie die mislukte (met de
    fout), anders reden_zonder_dossierkopie. Dezelfde keuze van de deal als in verwerk."""
    mislukt = [x for x in st.get("opdrachten", []) if x.get("soort") == "dossierkopie" and not x.get("gedaan") and x.get("fout")]
    if mislukt:
        return f"de kopie mislukte ({mislukt[0]['fout'][:120]})"
    passend = ([d for d in deals if str(d.get("nummer")) == b.get("projectnummer")]
               if b.get("firma") == "HARC" and b.get("projectnummer") and deals else [])
    return reden_zonder_dossierkopie(b, herk, deals, passend, passend[0] if len(passend) == 1 else None, tekst)


def meld_zonder_kopie(o, st, st_obj, reden):
    """Eén bevinding per nieuwe reden (in de staat als zonder_kopie), dus niet elke ronde; een opname die alsnog haar
    kopie krijgt, verliest haar reden zonder regel."""
    if st.get("zonder_kopie") == reden:
        return
    if reden:
        ag.log(f"opname {o['start_brussel'][:16]}", "bevinding", f"geen dossierkopie: {reden}")
    st["zonder_kopie"] = reden
    st_obj.bewaar(o["plaud_id"], st)


def reden_zonder_dossierkopie(b, herk, deals, passend, deal, tekst):
    """PLAUD-12 (T-0120): waarom een opname van H-Architects geen dossierkopie krijgt, of None (er komt een kopie, of het
    is geen H-A-opname). In oktober mochten 7 HARC-opnames gekopieerd worden en kwam er geen, zonder reden in het
    werkverslag. Een kopie vraagt een beslissing die ze toestaat en precies één open Pipedrive-deal met dat nummer
    (fathom_wacht.deals_index leest alleen open deals). De regel zelf verandert niet: dit zegt alleen waarom. De
    aanroeper logt het alleen bij een nieuwe beslissing en nooit bij een privé-opname (BAS-01)."""
    afdeling = str((herk or {}).get("afdeling") or "").strip().lower()
    ha = b.get("firma") == "HARC" or (not b.get("firma") and afdeling == "h-architects")
    if not ha or (b.get("kopie_toegestaan") and deal and tekst):
        return None
    if deals is None:
        return "Pipedrive niet gelezen"
    if not b.get("projectnummer"):
        return "geen projectnummer"
    if not passend:
        return f"geen open Pipedrive-deal met nummer {b['projectnummer']}"
    if len(passend) > 1:
        return (f"meer dan één open Pipedrive-deal met nummer {b['projectnummer']} ("
                + ", ".join(str(d.get("id")) for d in passend) + ")")
    return (f"de beslissing staat geen zakelijke kopie toe (zekerheid {b.get('zekerheid')}"
            + (", conflict" if b.get("conflict") else "") + ")")


# ------------------------------------------------------------- toezicht ---
def toezicht(r, m, status, st_obj, uitkomsten, taken, tellers):
    if not m:
        r.nood("De Plaud-invoer van de Mac ontbreekt op de VM (launchd be.globaal.plaud.ophalen)", wie="claude-code")
        return INVOER_FOUT
    code = OK
    gemaakt = datetime.fromisoformat(m["meta"]["gemaakt"])
    if _nu() - gemaakt > timedelta(hours=INVOER_MAX_UUR):
        r.nood("De Plaud-invoer van de Mac is ouder dan drie uur; de Mac haalt niet op of zet niet door", wie="claude-code")
        code = INVOER_FOUT
    if status.get("uitkomst") == "authfout":
        r.nood("Plaud-aanmelding ontbreekt of is geweigerd: Mehdi meldt één keer aan met plaud_login.py op de Mac", wie="mehdi")
    elif status.get("uitkomst") == "bronfout":
        r.nood("De Plaud-API was bij de laatste ophaling niet bereikbaar", wie="claude-code")
    # PLAUD-5 (T-0120): van 28-10 tot 01-11 stond de Mac elk uur op 'deels' (foutcode 4) met vijf mappen zonder audio, en
    # hier kwam geen melding. Het aantal staat in het detail van de ronde, niet in de nood (N10).
    if status.get("uitkomst") == "deels" or int((m["meta"].get("toestanden") or {}).get("onvolledig") or 0) > 0:
        r.nood("De Plaud-ophaling op de Mac liep deels mis of het archief heeft onvolledige opnames (audio of transcript "
               "ontbreekt); zie 00 status.json en 00 manifest.json op de Mac", wie="claude-code")
    alle = st_obj.alle().values()
    if m["meta"].get("conflicten"):
        r.nood("Id-conflict in het Plaud-archief: een opname staat in meer dan één map; Mehdi kiest welke geldt "
               "(zie 00 reconciliatie.md); niets gepubliceerd", wie="mehdi")
    if any(staat.te_herstellen(s) for s in alle):
        r.nood("Een eerder verspreid Plaud-transcript is door een nieuwe beoordeling herzien; het herstelvoorstel staat "
               "in de staat van De Plaudwacht", wie="mehdi")
    vast = [o for s in alle for o in staat.open_opdrachten(s) if int(o.get("pogingen") or 0) >= 3]
    if vast:
        r.nood("Publicaties van Plaud-opnames mislukken herhaaldelijk; zie het logboek", wie="claude-code")
    if any(u["uitkomst"] == "conflict" for u in uitkomsten):
        r.nood("Een zoektaak voor een bezoek heeft meer passende opnames of tegenstrijdig dossierbewijs; Mehdi kiest", wie="mehdi")
    if any(u["uitkomst"] == "ongeldig" for u in uitkomsten):
        r.nood("Een zoektaak voor De Plaudwacht heeft een ongeldige bezoekmap; er is niets geleverd", wie="claude-code")
    oudste = min((t.get("aangemaakt") or t.get("ts") or "" for t in taken), default="")
    toest = m["meta"].get("toestanden") or {}
    # PLAUD-9 (T-0120): de korte wachtende (onder een minuut) apart, maar ook in de wachtteller; een ouder manifest
    # zonder die telling geeft onbekend, nooit 0
    tellers.update(manifest=m["meta"]["aantal"], wacht_op_transcript_archief=toest.get("wacht_op_transcript", 0),
                   kort_wachtend_archief=m["meta"].get("kort_wachtend", "onbekend"),
                   onvolledig_archief=toest.get("onvolledig", 0), open_zoektaken=len(taken), oudste_zoektaak=oudste[:10],
                   aanmelding_mac=status.get("uitkomst", "onbekend"), invoer_van=m["meta"]["gemaakt"][:16])
    return code


def personentabel(r, fw):
    """De tabel Betrokken personen van De Fathomwacht, van het bord (een plek, N6), of None. Onbekend is niet leeg, en een
    lege tabel is geen tabel (NA09-rest, overleg 12, 01-11-2026). Tot dan werd een antwoord zonder werkwijze een lege
    tabel, en herkende het model privé en afdeling zonder die voorkennis; een transcript in een verkeerde dossiermap is
    niet zomaar terug te halen. Dan een nood, en deze ronde geen opname: ze wacht ongemoeid op de volgende."""
    try:
        tekst = bord.Agent("fathom-wacht").werkwijze_lezen()
    except bord.WerkwijzeOnbekend as e:
        r.nood("Personentabel van De Fathomwacht niet gelezen", wie="claude-code")
        ag.log("Plaud", "fout", f"personentabel van De Fathomwacht niet gelezen ({e}); deze ronde geen opname herkend")
        return None
    personen = fw.personen_uit_werkwijze(tekst)
    if not personen:
        r.nood("Personentabel van De Fathomwacht leeg", wie="mehdi")
        ag.log("Plaud", "fout", "personentabel van De Fathomwacht leeg; deze ronde geen opname herkend")
        return None
    r.bron("werkwijze fathom-wacht (personentabel)", tekst)
    return personen


def ronde(r):
    tellers = {"gedaan": 0, "ongewijzigd": 0, "wacht_op_transcript": 0, "uitgesteld": 0, "fout": 0, "fouten": 0, "herstel": 0}
    m, status = lees_invoer()
    st_obj = staat.Staat(STAAT)
    opnames = []
    for o in (m or {}).get("opnames", []):
        if o.get("herstel") or not o.get("start_utc"):
            tellers["herstel"] += 1
            continue
        opnames.append((o, None))
    bekend = {o["plaud_id"] for o, _ in opnames}
    try:
        oud, herstel = oude_inbox(bekend)
    except Exception as e:  # noqa: BLE001  de oude inbox is een terugval, geen voorwaarde
        oud, herstel = [], []
        ag.log("Plaud", "fout", f"oude inbox niet gelezen: {type(e).__name__}")
    opnames += oud
    tellers["herstel"] += len(herstel)
    for h in herstel:
        ag.log("Plaud", "bevinding", f"oud inboxbestand op herstel: {h['bestand']}: {h['reden']}")
    try:
        open_items = bord.klaargezet_voor(NAAM, n=200)
    except Exception:  # noqa: BLE001
        open_items = []
    taken = [t for t in open_items if t.get("soort") == "taak"]
    # verzoeken (bv. van De Contractmaker) hebben geen bezoekmap en geen tijdvenster: niet automatisch, wel zichtbaar
    tellers["open_verzoeken"] = len([t for t in open_items if t.get("soort") == "verzoek"])
    verzoeken = [t for t in open_items if t.get("soort") == "verzoek"]
    items = klaarzet_items()
    per_id, uitkomsten = zoektaken_beoordelen(taken, opnames, st_obj, items)
    for u in verzoeken_beoordelen(verzoeken, [o for o, _ in opnames], items):
        ag.log(f"verzoek {u['verzoek']}", "bevinding", f"{u['uitkomst']}: {u['reden']}")
        if u["uitkomst"] == "ter_beoordeling":
            r.nood("Een Plaud-opname past bij een verzoek van De Contractmaker; Mehdi bevestigt de bestemming in de salesmap", wie="mehdi")
    import fathom_wacht as fw
    personen = personentabel(r, fw)
    try:
        deals = fw.deals_index()
    except Exception as e:  # noqa: BLE001  onvolledig bewijs, geen definitieve conclusie (nacontrole v1.1, P2-8)
        deals = None
        ag.log("Plaud", "fout", f"Pipedrive niet gelezen: {type(e).__name__}; dossierbewijs deze ronde onvolledig")
    budget = {"over": MAX_HERKENNING}
    for o, romp in (opnames if personen else []):     # zonder personentabel geen opname: ze wacht op de volgende ronde
        eigen = per_id.get(o["plaud_id"], [])
        if o["start_brussel"][:10] < SINDS and not eigen:
            continue
        try:
            uitingen, tekst = tekst_en_uitingen(o, romp)
            res = verwerk(o, uitingen, tekst, st_obj, items, personen, deals, eigen, budget)
        except Exception as e:  # noqa: BLE001  één opname mag de andere niet blokkeren
            res = {"uitkomst": "fout", "fouten": 1}
            ag.log(f"opname {o['plaud_id']}", "fout", f"{type(e).__name__}: {str(e)[:200]}")
        tellers[res["uitkomst"]] = tellers.get(res["uitkomst"], 0) + 1
        tellers["fouten"] += res["fouten"]
    code = toezicht(r, m, status, st_obj, uitkomsten, taken, tellers)
    if tellers["fouten"] or not personen:
        code = code or DEELS
    if budget["over"] <= 0:
        ag.log("Plaud", "bevinding", "herkenningsbudget van deze ronde op; de rest volgt in de volgende rondes")
    ag.log("Plaud", "bron", "ronde: " + ", ".join(f"{k} {v}" for k, v in tellers.items()))
    r.detail = (f"{tellers['gedaan']} verwerkt, {tellers['wacht_op_transcript']} wachten op transcript, "
                f"{tellers.get('open_zoektaken', 0)} open zoektaken, invoer van {tellers.get('invoer_van', 'nooit')}"
                + (f", {tellers['onvolledig_archief']} onvolledig in het archief" if tellers.get("onvolledig_archief") else "")
                + (", Mac: deels" if tellers.get("aanmelding_mac") == "deels" else ""))
    return code, tellers


def main():
    with ag.ronde("Plaud-opnames verwerken") as r:
        code, tellers = ronde(r)
    print(json.dumps(tellers, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Werfverslag voorbereider (H-Architects) — bereidt werfverslagen voor.

Hij verzamelt zelf niets en schrijft zelf geen verslag. Hij:
  1. neemt een opdracht (dossiernummer) aan, van Mehdi (--project) of uit zijn eigen tabel;
  2. zoekt de projectmap in Dropbox (standaard- én light-projecten);
  3. leest de bezoekmappen (Site Reports, Werfverslagen, momentmappen) en inventariseert
     per bezoek wat er ligt: foto's, opname, transcript, verslag, notities;
  4. verifieert per bezoek de controleposten W1-W9 tegen wat de andere agents klaarzetten
     (Agendawacht, Plaudwacht, Fathomwacht, iCloud-wacht);
  5. zet voor elke ontbrekende bron een taak klaar voor de agent die ze kan leveren
     (klaarzet soort `taak`), en meldt wat geen enkele agent kan als nood;
  6. schrijft de stand naar zijn pagina op het bord (/werfverslagen).

Gebruik:
    werfverslag_voorbereider.py                      # alle open dossiers uit de tabel opnieuw verifiëren
    werfverslag_voorbereider.py --project 2309 2324  # dossiers toevoegen en meteen verifiëren
    werfverslag_voorbereider.py --project 2416 --droog   # alleen kijken, niets klaarzetten
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import bronnen  # noqa: E402

NAAM = "werfverslag-voorbereider"
LIGHT_BASIS = "/Work All/01. H-A WORK/0 H-A Light projects/5. H-A light SITE VISITS"
STANDAARD_OUDER = "/Work All/01. H-A WORK/0 H-A Standaard projects"


def standaard_bases():
    """De STAN-fasemappen zoals ze nu heten (0. STAN Voorstudie ... 6.STAN Ready to Deliver), gemeten."""
    uit = []
    for e in bronnen.lijst(STANDAARD_OUDER, recursief=False) or []:
        if e.get(".tag") == "folder" and re.match(r"^\d\.?\s*STAN", e.get("name", "")):
            uit.append(e.get("path_display"))
    return sorted(uit)
# Mappen waarin een bezoek kan liggen (kleine letters, deel van het pad)
BEZOEK_ANKERS = ("site reports", "werfverslagen", "werf updates", "site visits", "communicat", "werfbezoek")
FOTO_EXT = (".heic", ".jpg", ".jpeg", ".png", ".webp")
OPNAME_EXT = (".mp3", ".m4a", ".wav", ".mp4", ".mov")
VERSLAG_PAT = re.compile(r"werf ?(verslag|update|rapport)|site ?report|verslag", re.I)
TRANSCRIPT_PAT = re.compile(r"transcri|00 verslag", re.I)
DATUM_PAT = re.compile(r"(20\d{2})[-_. ]?(\d{2})[-_. ]?(\d{2})")
# De Agendawacht zet pas klaar sinds deze dag; oudere bezoeken kan hij (nog) niet bevestigen.
AGENDAWACHT_SINDS = "2026-09-09"

ag = bord.Agent(NAAM)
DOSSIERS_PAD = os.path.expanduser("~/appportal/mijnagents-data/werfverslag_dossiers.json")


def dossiers_lezen():
    """Per dossier wat Mehdi vastlegde: werfstart (JJJJ-MM-DD). Bezoeken vóór de werfstart zijn plaatsbezoeken
    (PB1, PB2, ...) zonder werfverslagnummer (A7/A8); bezoeken vanaf de werfstart tellen als werfbezoek 1, 2, 3."""
    try:
        return json.load(open(DOSSIERS_PAD))
    except (OSError, ValueError):
        return {}


def dossiers_schrijven(d):
    json.dump(d, open(DOSSIERS_PAD, "w"), ensure_ascii=False, indent=1)


def nummer_bezoeken(bezoeken, werfstart):
    """Zet volgnr (uniek, oplopend), nr_label (PB1.. of 1..) en soort_bezoek."""
    pb, wb = 0, 0
    for b in sorted(bezoeken, key=lambda m: (m["datum"], m["map"])):
        if werfstart and b["datum"] < werfstart:
            pb += 1
            b["soort_bezoek"], b["nr_label"], b["werfnr"] = "plaatsbezoek", f"PB{pb}", 0
        else:
            wb += 1
            b["soort_bezoek"], b["nr_label"], b["werfnr"] = "werfbezoek", str(wb), wb
    return bezoeken


def verhuisde_rijen(bezoeken, projectmap, bord_rijen):
    """De projectmap verhuisde van fasemap (2145 op 24-09-2026: 4. STAN Execution waiting to start naar 5. STAN
    Execution ONGOING). Per bezoekmap van nu: de rijen op het bord met dezelfde datum en dezelfde bezoekmap binnen
    de projectmap, maar onder een ander pad. Oudste rij eerst, die draagt de gegevens van de schrijver.
    Hoofdletterongevoelig, zoals Dropbox: de fasemap heette zowel 'waiting to start' als 'Waiting to start'."""
    uit = {}
    for b in bezoeken:
        if not b["map"].startswith(projectmap + "/"):
            continue
        rel = b["map"][len(projectmap):].lower()
        oud = [r for r in bord_rijen
               if r.get("datum") == b["datum"] and r.get("projectmap") and r.get("bezoekmap") != b["map"]
               and (r.get("bezoekmap") or "").lower() == r["projectmap"].lower() + rel]
        if oud:
            uit[b["map"]] = sorted(oud, key=lambda r: r.get("id") or 0)
    return uit


def samengevoegd(rijen):
    """Eén bordrij uit de rij van het nieuwe pad en die van het oude: wat de schrijver al deed (gegevens, proef)
    telt ook in de controle van deze ronde, ook al staat het nog op de oude rij."""
    uit = {}
    for r in rijen:
        for k, v in (r or {}).items():
            if v and not uit.get(k):
                uit[k] = v
    return uit


def opruimvoorstel(dubbels):
    """Eén voorstel voor alle dubbele rijen na een verhuis. Mehdi beslist op het bord; het runbook
    werfbezoek-dubbels wist na zijn ja alleen rijen waarvan alles op de rij van het nieuwe pad staat."""
    if not dubbels:
        return None
    per = {}
    for x in dubbels:
        per.setdefault(x["dossier"], []).append(x)
    paren = sorted([x["dubbel"], x["id"]] for x in dubbels)
    botsing = [f"rij {x['dubbel']} ({', '.join(x['botsing'])})" for x in dubbels if x.get("botsing")]
    return {"actie": "Dubbele werfbezoek-rijen opruimen na verhuis van de projectmap: "
                     + ", ".join(f"dossier {d} ({len(v)} rij(en))" for d, v in sorted(per.items())),
            "doel": ", ".join(f"dossier {d}" for d in sorted(per)),
            "reden": ("De projectmap verhuisde naar een andere fasemap; per bezoek staat er een rij van het oude pad naast "
                      "de rij van het nieuwe. Gegevens, keuzes, bijlagen en proef van de oude rij zijn overgenomen. Na je ja "
                      f"wist het runbook alleen de oude rijen ({', '.join(str(p[0]) for p in paren)}), met een volledige kopie "
                      "in werfbezoek_gewist.jsonl."
                      + (f" Verschilt op beide rijen, de nieuwe wint: {'; '.join(botsing)}." if botsing else "")),
            "runbook": "werfbezoek-dubbels",
            "parameters": {"sleutel": "werfbezoek-dubbels", "paren": paren}}


# ------------------------------------------------------------- hulpjes ---
def datum_uit(naam):
    m = DATUM_PAT.search(naam)
    if not m:
        return ""
    j, ma, d = m.groups()
    try:
        return date(int(j), int(ma), int(d)).isoformat()
    except ValueError:
        return ""


def adres_uit_mapnaam(naam):
    """`2416 [ INT - EPB, ING, VC] Julien Breugelmansstraat 16, 2950 Kapellen` -> adres."""
    n = re.sub(r"^\s*\d{4}\s*", "", naam)
    n = re.sub(r"\[[^\]]*\]", "", n)
    n = re.sub(r"\([^)]*\)", "", n)
    n = n.split("_")[0]
    return re.sub(r"\s+", " ", n).strip(" -,")


def zoek_projectmap(nummer):
    """Eerst de standaardprojecten (STAN-fasen), dan de light-projecten."""
    for basis in standaard_bases():
        for e in bronnen.lijst(basis, recursief=False) or []:
            if e.get(".tag") == "folder" and e.get("name", "").startswith(str(nummer)):
                return e.get("path_display"), "standaard"
    for e in bronnen.lijst(LIGHT_BASIS, recursief=False) or []:
        if e.get(".tag") == "folder" and re.match(rf"\s*{nummer}\b", e.get("name", "")):
            return e.get("path_display"), "light"
    return None, ""


def bezoeken_in(projectmap):
    """Per bezoek een dict: map, datum, en de bestanden erin naar soort."""
    items = bronnen.lijst(projectmap, recursief=True) or []
    mappen = {}
    for e in items:
        if e.get(".tag") != "folder":
            continue
        pad = e.get("path_display") or ""
        rel = pad[len(projectmap):].lower()
        if not any(a in rel for a in BEZOEK_ANKERS):
            continue
        naam = e.get("name", "").lower()
        delen = rel.strip("/").split("/")
        d = datum_uit(naam)
        if not d or any(a in naam for a in ("foto", "photo", "mail", "offerte", "factu")):
            continue
        # een datummap ónder een fotomap is een fotoreeks van het bezoek, geen bezoek
        if any(("foto" in s or "photo" in s) for s in delen[:-1]):
            continue
        # in de communicatiemap telt alleen een momentmap (A3/A7) van een werf- of plaatsbezoek:
        # naam bevat 'bezoek', maar niet leverancier, toonzaal, online of tel
        if "communicat" in rel and ("bezoek" not in naam or any(x in naam for x in ("leverancier", "toonzaal", "online", "tel "))):
            continue
        if True:
            mappen[pad] = {"map": pad, "datum": d, "fotos": 0, "opnames": [], "transcripten": [],
                           "verslagen": [], "notities": [], "bestanden": 0, "bron_map": rel.strip("/").split("/")[0]}
    # losse verslagen buiten een bezoekmap (bv. `1. Werf updates/Werf update 2 - ... - 2026-06-02.docx`)
    losse = []
    for e in items:
        if e.get(".tag") != "file":
            continue
        pad, naam = e.get("path_display") or "", e.get("name", "")
        laag = naam.lower()
        if laag.startswith(".") or laag == ".ds_store":
            continue
        eigenaar = None
        for mp in sorted(mappen, key=len, reverse=True):
            if pad.startswith(mp + "/"):
                eigenaar = mappen[mp]
                break
        if eigenaar is None:
            if VERSLAG_PAT.search(naam) and laag.endswith((".docx", ".pdf", ".md")) and datum_uit(naam) \
                    and any(a in pad.lower() for a in BEZOEK_ANKERS):
                losse.append({"pad": pad, "datum": datum_uit(naam)})
            continue
        eigenaar["bestanden"] += 1
        if laag.endswith(FOTO_EXT):
            eigenaar["fotos"] += 1
        elif laag.endswith(OPNAME_EXT):
            eigenaar["opnames"].append(naam)
        elif TRANSCRIPT_PAT.search(naam) and laag.endswith((".md", ".txt", ".docx")) and not re.search(r"niet getranscribeerd|geen opname|00 fotos", laag):
            eigenaar["transcripten"].append(naam)
        elif VERSLAG_PAT.search(naam) and laag.endswith((".docx", ".pdf", ".md")):
            eigenaar["verslagen"].append(naam)
        elif laag.endswith((".docx", ".pdf", ".md", ".txt", ".xlsx", ".pptx")):
            eigenaar["notities"].append(naam)
    for v in losse:
        doel = next((m for m in mappen.values() if m["datum"] == v["datum"]), None)
        if doel:
            doel["verslagen"].append(os.path.basename(v["pad"]))
        else:
            mappen[v["pad"]] = {"map": os.path.dirname(v["pad"]), "datum": v["datum"], "fotos": 0, "opnames": [],
                                "transcripten": [], "verslagen": [os.path.basename(v["pad"])], "notities": [],
                                "bestanden": 1, "bron_map": "los verslag"}
    uit = sorted(mappen.values(), key=lambda m: (m["datum"], m["map"]))
    for i, m in enumerate(uit, 1):
        m["volgnr"] = i
    return uit


def klaargezet(nummer):
    """Wat de andere agents over dit dossier klaarzetten, per soort."""
    try:
        alles = bord.call("/api/klaarzet?status=alle&n=500").get("items", [])
    except Exception as e:  # noqa: BLE001
        ag.log(str(nummer), "fout", f"bord niet bereikbaar: {e}")
        return {}
    per = {"afspraak": [], "transcript": [], "foto": []}
    for it in alles:
        if it["soort"] not in per:
            continue
        tekst = f'{it.get("sleutel", "")} {it.get("titel", "")} {(it.get("inhoud") or "")[:400]}'
        if it["soort"] == "foto" or re.search(rf"\b{nummer}\b", tekst):
            per[it["soort"]].append(it)
    return per


def dag_van(it):
    inhoud = it.get("inhoud") or ""
    try:
        d = json.loads(inhoud) if inhoud.startswith("{") else {}
    except ValueError:
        d = {}
    return (d.get("datum") or d.get("start") or it.get("sleutel") or it.get("titel") or "")[:10]


# ------------------------------------------------------- controleposten ---
def controleer(nummer, adres, soort_project, projectmap, bezoek, bak, bord_rij=None):
    """Geeft (controles, taken, noden). controles: lijst {code, naam, stand, toelichting}.
    stand in ok | ontbreekt | onbekend | nvt."""
    d = bezoek["datum"]
    c, taken, noden = [], [], []

    def post(code, naam, stand, toel=""):
        c.append({"code": code, "naam": naam, "stand": stand, "toelichting": toel})

    # W1 agenda
    afspraken = [a for a in bak.get("afspraak", []) if dag_van(a) == d]
    if afspraken:
        post("W1", "afspraak in de agenda", "ok", afspraken[0].get("titel", "")[:120])
    elif d < AGENDAWACHT_SINDS:
        post("W1", "afspraak in de agenda", "onbekend", f"bezoek van vóór {AGENDAWACHT_SINDS}: de Agendawacht kijkt nog niet terug in de tijd")
        noden.append({"tekst": f"Agendawacht kan geen afspraken van vóór {AGENDAWACHT_SINDS} bevestigen; een ronde met --dag over het verleden is nodig", "wie": "claude-code"})
    else:
        post("W1", "afspraak in de agenda", "ontbreekt", "geen afspraak met dit nummer op die dag klaargezet")
        taken.append(("agenda-wacht", f"Zoek in alle agenda's de afspraak van dossier {nummer} op {d} ({adres}) en zet ze klaar met sleutel {nummer}"))
    # W2 projectmap, W3 bezoekmap
    post("W2", "projectmap gevonden", "ok" if projectmap else "ontbreekt", f"{soort_project}: {projectmap}" if projectmap else "")
    post("W3", "bezoekmap", "ok", bezoek["map"])
    # W4 foto's
    if bezoek["fotos"]:
        post("W4", "foto's", "ok", f"{bezoek['fotos']} in de bezoekmap")
    else:
        fotos = [f for f in bak.get("foto", []) if dag_van(f) == d]
        if fotos:
            post("W4", "foto's", "ontbreekt", f"niet in de map, wel {len(fotos)} reeks(en) van die dag bij de iCloud-wacht")
        else:
            post("W4", "foto's", "ontbreekt", "geen foto's in de map en niets van die dag bij de iCloud-wacht")
        taken.append(("icloud-wacht", f"Foto's van {d} binnen 300 m van {adres} (dossier {nummer}) klaarzetten voor de bezoekmap"))
    # W5 opname, W6 transcript
    transcripten_bak = [t for t in bak.get("transcript", []) if dag_van(t) == d]
    if bezoek["opnames"]:
        post("W5", "opname", "ok", "; ".join(bezoek["opnames"])[:160])
    elif bezoek["transcripten"]:
        post("W5", "opname", "ok", "opname bestaat in Plaud; het transcript staat in de map (audio pas na een ja van Mehdi)")
    elif transcripten_bak:
        post("W5", "opname", "ok", "opname bij de Plaud-/Fathomwacht, niet in de map")
    else:
        post("W5", "opname", "ontbreekt", "geen opname in de map en geen transcript van die dag klaargezet")
        taken.append(("plaud-wacht", f"Zoek een Plaud-opname van {d} voor dossier {nummer} ({adres}) en zet het transcript klaar met sleutel {nummer}"))
    if bezoek["transcripten"]:
        post("W6", "transcript", "ok", "; ".join(bezoek["transcripten"])[:160])
    elif transcripten_bak:
        post("W6", "transcript", "ok", f"klaargezet door {transcripten_bak[0].get('van')}: {transcripten_bak[0].get('titel', '')[:100]}")
    elif bezoek["opnames"]:
        post("W6", "transcript", "ontbreekt", "opname zonder transcript in de map")
        taken.append(("plaud-wacht", f"Transcript maken/ophalen van de opname in {bezoek['map']} (dossier {nummer}, {d})"))
    else:
        post("W6", "transcript", "ontbreekt", "geen opname, dus geen transcript")
    # W7 verslag; W11 nacontrole van de proef van Werfverslag schrijver
    br = bord_rij or {}
    if bezoek["verslagen"]:
        post("W7", "verslag of concept", "ok", "; ".join(bezoek["verslagen"])[:160])
    elif br.get("proef_pad"):
        post("W7", "verslag of concept", "ok", f"proef van Werfverslag schrijver: {os.path.basename(br['proef_pad'])}")
    else:
        post("W7", "verslag of concept", "ontbreekt", "nog geen verslag; Werfverslag schrijver maakt de proef na Keuzes en Proef op de bezoekpagina")
    if br.get("proef_pad"):
        info = br.get("proef_info") or {}
        if isinstance(info, str):
            try:
                info = json.loads(info or "{}")
            except ValueError:
                info = {}
        op = info.get("open") or {}
        n_open = sum(int(x or 0) for x in op.values()) if isinstance(op, dict) else 0
        post("W11", "proef nagekeken", "ok" if n_open == 0 else "onbekend",
             f"{info.get('punten', '?')} punten, {info.get('fotos', '?')} foto's; nog {op.get('in_te_vullen', '?')} in te vullen, "
             f"{op.get('na_te_kijken', '?')} na te kijken, {op.get('raming_open', '?')} ramingen open" if isinstance(op, dict) else "geen telling")
    elif not (br.get("gegevens") or {}).get("gegevens") if isinstance(br.get("gegevens"), dict) else not br.get("gegevens"):
        # Regel van Mehdi (13-09-2026): geen voorbereiding en geen proef zonder zijn knop; elke stap kost tokens.
        post("W11", "voorbereiding door de schrijver", "onbekend", "wacht op Mehdi: knop Voorbereiden op de bezoekpagina (kost tokens, dus nooit automatisch)")
    else:
        post("W11", "voorbereiding door de schrijver", "ok", "gegevens met herkomst staan op de bezoekpagina; Keuzes en Proef zijn aan Mehdi")
    # W8 verslagnummer
    if bezoek.get("soort_bezoek") == "plaatsbezoek":
        post("W8", "verslagnummer", "ok", f"{nummer}-{bezoek['nr_label']}: plaatsbezoek vóór de werfstart, geen werfverslagnummer (A7/A8)")
    else:
        post("W8", "verslagnummer", "ok", f"{nummer}-{bezoek.get('nr_label', bezoek['volgnr'])} (werfbezoek {bezoek.get('nr_label', bezoek['volgnr'])} sinds de werfstart)")
    # W9 verstuurd
    post("W9", "verstuurd aan de klant", "onbekend", "alleen uit de mail af te lezen; de Mailwacht mch@ koppelt nog niet aan dossiers")
    if bezoek["notities"]:
        post("W10", "notities in de map", "ok", "; ".join(bezoek["notities"])[:160])
    return c, taken, noden


def stand_van(controles):
    s = {x["code"]: x["stand"] for x in controles}
    bronnen_ok = all(s.get(k) == "ok" for k in ("W4", "W5", "W6"))
    if s.get("W7") == "ok":
        return "verslag aanwezig" if bronnen_ok else "verslag aanwezig, bronnen onvolledig"
    return "klaar voor verslag" if bronnen_ok else "te verzamelen"


# ------------------------------------------------------------- de ronde ---
def verwerk(nummer, droog=False):
    ag.log(str(nummer), "bron", f"dossier {nummer}: projectmap zoeken")
    projectmap, soort = zoek_projectmap(nummer)
    if not projectmap:
        ag.log(str(nummer), "fout", "geen projectmap gevonden in STAN-fasen of light SITE VISITS")
        return [], [{"tekst": f"Dossier {nummer}: geen projectmap gevonden; Mehdi geeft het pad", "wie": "mehdi"}], []
    adres = adres_uit_mapnaam(os.path.basename(projectmap))
    ag.log(str(nummer), "bron", f"projectmap ({soort}): {projectmap}", {"adres": adres})
    bezoeken = bezoeken_in(projectmap)
    werfstart = (dossiers_lezen().get(str(nummer)) or {}).get("werfstart", "")
    bezoeken = nummer_bezoeken(bezoeken, werfstart)
    ag.log(str(nummer), "bevinding", f"{len(bezoeken)} bezoek(en) in de mappen: " + ", ".join(f"{b['nr_label']} {b['datum']}" for b in bezoeken)
           + (f"; werfstart {werfstart}" if werfstart else "; geen werfstart bekend"))
    bak = klaargezet(nummer)
    try:
        alle_rijen = bord.call(f"/api/werfbezoek?dossier={nummer}").get("rijen", [])
    except Exception:  # noqa: BLE001
        alle_rijen = []
    bord_rijen = {r.get("bezoekmap"): r for r in alle_rijen}
    open_taken = {}
    for agent in ("icloud-wacht", "plaud-wacht"):
        try:
            open_taken[agent] = [it for it in bord.klaargezet_voor(agent, n=300) if it.get("soort") == "taak" and it.get("van") == NAAM]
        except Exception:  # noqa: BLE001
            open_taken[agent] = []
    rijen, alle_taken, noden, dubbels = [], [], [], []
    # verhuisde projectmap: de rij van het oude pad gaat mee naar het nieuwe, maar alleen als het oude pad echt weg
    # is; staat de bezoekmap op beide plaatsen, dan is het een kopie en beslist Mehdi welke geldt
    verhuisd = verhuisde_rijen(bezoeken, projectmap, alle_rijen)
    for mp, oude in list(verhuisd.items()):
        # verschilt alleen de schrijfwijze, dan is het voor Dropbox dezelfde map: geen kopie
        nog = [r for r in oude if r["bezoekmap"].lower() != mp.lower() and bronnen.bestaat(r["bezoekmap"])]
        if nog:
            noden.append({"tekst": f"Dossier {nummer}: bezoekmap staat zowel onder {nog[0]['projectmap'].split('/')[-2]} "
                                   f"als onder {projectmap.split('/')[-2]}; Mehdi zegt welke geldt", "wie": "mehdi"})
            verhuisd[mp] = [r for r in oude if r not in nog]
    verhuisd = {k: v for k, v in verhuisd.items() if v}
    if verhuisd:
        ag.log(str(nummer), "bevinding", f"projectmap verhuisd: {len(verhuisd)} bezoekmap(pen) hebben een rij op het oude pad "
               f"({next(iter(verhuisd.values()))[0]['projectmap'].split('/')[-2]}); die rij gaat mee naar het nieuwe pad")
    if not bezoeken:
        # dossier gevolgd zonder bezoek (bv. werf start binnenkort): een rij met volgnummer 0, zodat het op de pagina staat
        rijen.append({"dossier": str(nummer), "adres": adres, "soort_project": soort, "projectmap": projectmap, "bezoekmap": "",
                      "datum": "", "volgnr": 0, "bronnen": {"werfstart": werfstart}, "taken": [], "stand": "gevolgd, nog geen bezoekmap" + (f"; werfstart {werfstart}" if werfstart else ""),
                      "controles": [{"code": "W2", "naam": "projectmap gevonden", "stand": "ok", "toelichting": f"{soort}: {projectmap}"},
                                    {"code": "W3", "naam": "bezoekmap", "stand": "ontbreekt", "toelichting": "nog geen momentmap met een werf- of plaatsbezoek; na het eerste bezoek maakt de skill werfverslag de map aan"}]})
        ag.log(str(nummer), "bevinding", "nog geen bezoekmap; dossier wordt gevolgd tot het eerste bezoek")
    for b in bezoeken:
        oude = verhuisd.get(b["map"], [])
        controles, taken, n = controleer(nummer, adres, soort, projectmap, b, bak, samengevoegd([bord_rijen.get(b["map"])] + oude))
        # een taak die intussen vervuld is (foto's of transcript staan in de map) vink ik af, zodat de zoeklijst klopt
        st = {c["code"]: c["stand"] for c in controles}
        for code, agent in (("W4", "icloud-wacht"), ("W6", "plaud-wacht")):
            if st.get(code) == "ok":
                for it in open_taken.get(agent, []):
                    if it.get("uniek") == f"werf:{nummer}:{b['datum']}:{agent}":
                        try:
                            bord.opgepakt(it["id"], NAAM)
                            ag.log(str(nummer), "besluit", f"taak voor {agent} ({b['datum']}) afgevinkt: bron staat in de map")
                        except Exception:  # noqa: BLE001
                            pass
        noden += n
        taakrijen = []
        for voor, tekst in taken:
            uniek = f"werf:{nummer}:{b['datum']}:{voor}"
            # eigen naam: 'soort' is het soort project (standaard, light); overschrijven gaf 'taak-project' op de pagina
            taaksoort = "opdracht" if voor == "werfverslag-schrijver" else "taak"
            taakrijen.append({"voor": voor, "soort": taaksoort, "sleutel": (f"{nummer}-{b['volgnr']}" if taaksoort == "opdracht" else str(nummer)), "titel": tekst[:300],
                              "inhoud": {"dossier": nummer, "datum": b["datum"], "adres": adres, "bezoekmap": b["map"], "volgnr": b["volgnr"],
                                         "nr_label": b["nr_label"], "soort_bezoek": b["soort_bezoek"]},
                              "verwijzing": b["map"], "uniek": uniek})
        alle_taken += taakrijen
        rijen.append({"dossier": str(nummer), "adres": adres, "soort_project": soort, "projectmap": projectmap,
                      "bezoekmap": b["map"], "datum": b["datum"], "volgnr": b["volgnr"],
                      "bronnen": {**{k: b[k] for k in ("fotos", "opnames", "transcripten", "verslagen", "notities", "bestanden", "bron_map")},
                                  "nr_label": b["nr_label"], "soort_bezoek": b["soort_bezoek"], "werfstart": werfstart},
                      "controles": controles, "taken": [{"voor": t["voor"], "titel": t["titel"], "uniek": t["uniek"]} for t in taakrijen],
                      "stand": stand_van(controles)})
        if oude:
            rijen[-1]["vorige_bezoekmappen"] = [r["bezoekmap"] for r in oude]
        # het bezoeknummer (PB1.., 1..) is wat in het verslag komt; de rij telt alle bezoeken door en is alleen het adres op het bord
        ag.log(str(nummer), "bevinding", f"{b['soort_bezoek']} {b['nr_label']} (rij {b['volgnr']}, {b['datum']}): {rijen[-1]['stand']}; "
               + ", ".join(f"{x['code']} {x['stand']}" for x in controles))
    if droog:
        print(json.dumps(rijen, ensure_ascii=False, indent=1))
        return rijen, noden, dubbels
    if alle_taken:
        uit = ag.klaarzet(alle_taken)
        ag.log(str(nummer), "besluit", f"{len(alle_taken)} taak/taken uitgezet bij collega-agents", uit)
    try:
        uit = bord.call("/api/werfbezoek", {"rijen": rijen})
    except Exception as e:  # noqa: BLE001
        ag.log(str(nummer), "fout", f"stand niet naar het bord: {e}")
        uit = {}
    for h in uit.get("herkoppeld") or []:
        if h.get("wat") == "herkoppeld":
            ag.log(str(nummer), "besluit", f"rij {h['id']} met haar gegevens meegenomen naar het nieuwe pad (was {h['van']})")
            continue
        dubbels.append({"dossier": str(nummer), "dubbel": h["dubbel"], "id": h["id"], "botsing": h.get("botsing") or []})
        if h.get("kolommen") or h.get("omgezet"):
            ag.log(str(nummer), "besluit", f"rij {h['id']}: aangevuld met {', '.join(h.get('kolommen') or []) or 'niets'} van de oude rij "
                   f"{h['dubbel']}, paden naar het nieuwe pad in {', '.join(h.get('omgezet') or []) or 'niets'}; "
                   "de oude rij blijft tot Mehdi de opruiming goedkeurt")
    return rijen, noden, dubbels


GEZOCHT_PAD = "/Work All/000 AI Opzet/Mehdi Agents/Plaud inbox/00 gezocht.md"


def upload_overschrijf(pad, data):
    """Bestand in Dropbox schrijven of vervangen (mode overwrite); alleen voor mijn eigen zoeklijst."""
    import json as _j
    import urllib.request
    arg = _j.dumps({"path": pad, "mode": "overwrite", "mute": True})
    req = urllib.request.Request(f"{bronnen.INHOUD}/2/files/upload", data=data, method="POST",
                                 headers=bronnen._koppen({"Dropbox-API-Arg": arg, "Content-Type": "application/octet-stream"}))
    with urllib.request.urlopen(req, timeout=120) as r:
        return _j.load(r).get("path_display", pad)


def gezocht_schrijven():
    """De zoeklijst voor de Plaud-routine (claude.ai): elke open opname-taak als een regel met bezoekdag, dossier, adres
    en bezoekmap. De routine zoekt op OPNAMEDATUM (start_at, UTC), niet op uploaddatum, en zet het transcript in de inbox
    met de kop `bezoekmap:` zodat de Plaudwacht het in de bezoekmap zet. Les van 2309 (03-06, geüpload 21-08)."""
    try:
        # ook de opname-taken van het Commandocentrum (andere verslagsoorten) komen op dezelfde zoeklijst
        taken = [it for it in bord.klaargezet_voor("plaud-wacht", n=200) if it.get("soort") == "taak" and it.get("van") in (NAAM, "commandocentrum")]
    except Exception:  # noqa: BLE001
        return 0
    regels = ["# Gezochte Plaud-opnames (geschreven door de Werfverslag voorbereider)", "",
              "Voor de Plaud-routine: zoek per regel de opname(s) waarvan `start_at` (UTC, +2 u in de zomer) op de bezoekdag valt,",
              "haal het transcript (block transaction) op en zet het in deze inbox als `<datum> <UUMM> Plaud transcript - <id>.md`",
              "met in de kop `dossier:`, `bezoekmap:` en `audio_url:`. Zonder transcript in Plaud: meld `niet getranscribeerd`.", "",
              "| bezoekdag | dossier | adres | bezoekmap | taak |", "|---|---|---|---|---|"]
    n = 0
    for it in taken:
        try:
            d = json.loads(it.get("inhoud") or "{}")
        except ValueError:
            d = {}
        if not d.get("datum"):
            continue
        regels.append(f"| {d['datum']} | {d.get('dossier','')} | {d.get('adres','')} | {d.get('bezoekmap','')} | {it['id']} |")
        n += 1
    try:
        upload_overschrijf(GEZOCHT_PAD, ("\n".join(regels) + "\n").encode("utf-8"))
    except Exception as e:  # noqa: BLE001
        ag.log("plaud", "fout", f"zoeklijst niet geschreven: {e}")
    return n


def open_dossiers():
    try:
        return [r["dossier"] for r in bord.call("/api/werfbezoek?open=1").get("dossiers", [])]
    except Exception:  # noqa: BLE001
        return []


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", nargs="*", default=[], help="dossiernummers")
    p.add_argument("--droog", action="store_true")
    p.add_argument("--werfstart", nargs=2, metavar=("DOSSIER", "JJJJ-MM-DD"), help="werfstart van een dossier vastleggen")
    a = p.parse_args()
    if a.werfstart:
        d = dossiers_lezen(); d.setdefault(a.werfstart[0], {})["werfstart"] = a.werfstart[1]; dossiers_schrijven(d)
        print(f"werfstart {a.werfstart[0]} = {a.werfstart[1]}")
        if a.werfstart[0] not in a.project:
            a.project.append(a.werfstart[0])
    nummers = [n for n in a.project if re.fullmatch(r"\d{4}", n)]
    # impulsen van het Commandocentrum (16-09-2026): een werfbezoek in de agenda maakt het dossier vanzelf gevolgd
    try:
        for it in bord.klaargezet_voor(NAAM, n=50):
            if it.get("soort") != "impuls" or it.get("van") != "commandocentrum":
                continue
            try:
                d = json.loads(it.get("inhoud") or "{}")
            except ValueError:
                d = {}
            n = str(d.get("dossier") or "")
            if re.fullmatch(r"\d{4}", n) and n not in nummers:
                nummers.append(n)
                ag.log(n, "bron", f"impuls van het Commandocentrum: {it.get('titel', '')[:100]}")
            bord.opgepakt(it["id"], NAAM)
    except Exception as e:  # noqa: BLE001
        ag.log("bak", "fout", f"impulsen niet gelezen: {type(e).__name__}")
    nummers += [n for n in open_dossiers() if n not in nummers]
    ag.hartslag("actief", taak="ronde gestart", detail=f"{len(nummers)} dossier(s)")
    if not bronnen.dropbox_beschikbaar():
        ag.hartslag("fout", taak="geen Dropbox", detail="DROPBOX_APP_KEY/SECRET/REFRESH_TOKEN ontbreken",
                    nood=[{"tekst": "Dropbox-sleutels van de stack ontbreken in ~/appportal/.env", "wie": "mehdi"}])
        return
    totaal, noden, standen, dubbels = 0, [], {}, []
    for n in nummers:
        try:
            rijen, nd, db = verwerk(n, droog=a.droog)
        except Exception as e:  # noqa: BLE001
            ag.log(n, "fout", f"ronde voor {n} mislukt: {e}")
            rijen, nd, db = [], [{"tekst": f"Dossier {n}: ronde mislukt ({type(e).__name__})", "wie": "claude-code"}], []
        totaal += len(rijen)
        noden += nd
        dubbels += db
        for r in rijen:
            standen[r["stand"]] = standen.get(r["stand"], 0) + 1
    # vaste noden: wat structureel nog ontbreekt om zonder mens te werken
    noden += [
        {"tekst": "Agendawacht, Plaudwacht en iCloud-wacht lezen mijn taken (klaarzet soort taak) nog niet; Werfverslag schrijver leest zijn opdrachten wel", "wie": "claude-code"},
        {"tekst": "Verstuurd-status (W9) vraagt een koppeling mail -> dossier bij de Mailwacht mch@", "wie": "claude-code"},
    ]
    # dubbels weg, volgorde behouden
    gezien, uniek = set(), []
    for x in noden:
        if x["tekst"] not in gezien:
            gezien.add(x["tekst"]); uniek.append(x)
    if not a.droog:
        nz = gezocht_schrijven()
        ag.log("plaud", "schrijf", f"zoeklijst voor de Plaud-routine bijgewerkt: {nz} bezoekdag(en) zonder opname ({GEZOCHT_PAD})")
    # opruimen van dubbele rijen na een verhuis: een voorstel, nooit zelf wissen; hetzelfde voorstel zet het bord niet twee keer
    voorstel = opruimvoorstel(dubbels)
    if voorstel:
        ag.log("bord", "besluit", f"opruiming voorgesteld aan Mehdi: {voorstel['actie']}", voorstel["parameters"])
    ag.log_verstuur()
    detail = "; ".join(f"{k}: {v}" for k, v in sorted(standen.items())) or "geen bezoeken"
    if not a.droog:
        ag.hartslag("klaar" if totaal else "waakt", taak=f"{len(nummers)} dossier(s), {totaal} bezoek(en) geverifieerd", detail=detail[:200],
                    nood=uniek, voorstel=voorstel)
    print(f"klaar: {len(nummers)} dossier(s), {totaal} bezoek(en); {detail}")


if __name__ == "__main__":
    main()

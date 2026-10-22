#!/usr/bin/env python3
"""Werfverslag voorbereider (H-Architects): bereidt werfverslagen voor.

Hij verzamelt zelf niets en schrijft zelf geen verslag. Hij:
  1. neemt een opdracht (dossiernummer) aan, van Mehdi (--project) of uit zijn eigen tabel;
  2. zoekt de projectmap in Dropbox (standaard- én light-projecten);
  3. leest de bezoekmappen (Site Reports, Werfverslagen, momentmappen) en inventariseert
     per bezoek wat er ligt: foto's, opname, transcript, verslag, notities;
  4. verifieert per bezoek W1-W12 tegen agenda, locatie, bezoekmap, contract en werfapp;
     twijfel blijft zichtbaar als let_op, ontbreekt of onbekend;
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
import math
import os
import re
import sys
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import bronnen  # noqa: E402
import werfregister  # noqa: E402
import werfregistratie  # noqa: E402
import locatiecontext as LC  # noqa: E402  (de enige lezer van locatiegegevens: grens en rol)
import werfapp  # noqa: E402
import werfnamen  # noqa: E402  (dezelfde naamregel voor eigen transcripten als de schrijver)
import contracten_mcp  # noqa: E402

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
MOMENT_VORM_RE = re.compile(r"^(20\d{2}-\d{2}-\d{2}) (\d{2})(\d{2}) HARC (\d{4,6}) - ")
# De gewone Agendawachtronde zet sinds deze dag klaar; oudere dagen krijgen E1b-terugkijkbewijs op vraag.
AGENDAWACHT_SINDS = "2026-09-09"

ag = bord.Agent(NAAM)
vooraf_koppelen = werfregistratie.koppel_voor_nummering
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


def _is_dubbel(r):
    return str(r.get("stand", "")).startswith("dubbel")


def hernoemde_rijen(bezoeken, projectmap, bord_rijen, bestaat, al=()):
    """De bezoekmap kreeg binnen dezelfde projectmap een andere naam (2145 en 2405, oktober 2026: de
    communicatiemap ging naar de naamregel `JJJJ-MM-DD UUMM HARC nummer - met wie - onderwerp`).

    Een rij hoort bij een bezoek van nu als: dezelfde datum, het oude pad ligt in dezelfde projectmap, het
    oude pad bestaat niet meer, en er is precies één bezoek op die datum in de projectmap. Twee bezoeken op
    dezelfde dag: geen koppeling (de rij gaat dan naar verdwenen_rijen en Mehdi kijkt). Rijen die al als
    verhuis herkend zijn (al) of die al dubbel staan, tellen niet.
    """
    pm = projectmap.lower() + "/"
    per_dag = {}
    for b in bezoeken:
        per_dag.setdefault(b["datum"], []).append(b)
    gezien = {id(r) for oude in al for r in oude}
    huidig = {b["map"].lower() for b in bezoeken}
    uit = {}
    for r in sorted(bord_rijen, key=lambda r: r.get("id") or 0):
        pad = r.get("bezoekmap") or ""
        kandidaten = per_dag.get(r.get("datum"), [])
        if (id(r) in gezien or _is_dubbel(r) or not pad or pad.lower() in huidig
                or not pad.lower().startswith(pm) or len(kandidaten) != 1 or bestaat(pad)):
            continue
        uit.setdefault(kandidaten[0]["map"], []).append(r)
    return uit


def verdwenen_rijen(bezoeken, bord_rijen, bestaat, gekoppeld=()):
    """Rijen waarvan de bezoekmap niet meer bestaat en die bij geen bezoek van nu horen: die mogen hun oude
    stand (bv. 'klaar voor verslag') niet houden. Niets wordt gewist; ze krijgen een eerlijke stand."""
    gezien = {id(r) for oude in gekoppeld for r in oude}
    huidig = {b["map"].lower() for b in bezoeken}
    return [r for r in bord_rijen
            if r.get("bezoekmap") and id(r) not in gezien and not _is_dubbel(r)
            and r["bezoekmap"].lower() not in huidig and not str(r.get("stand", "")).startswith("bezoekmap niet meer gevonden")
            and not bestaat(r["bezoekmap"])]


VERDWENEN = "bezoekmap niet meer gevonden; nakijken"


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
    werfbezoek-dubbels voegt na zijn ja de oude rij in de nieuwe samen en bewaart een kopie.

    De tekst zegt eerst wat blijft en dan wat verandert. Gezien 24-09-2026: de woorden
    "opruimen" en "oude rijen" liet Mehdi lezen dat dossier 2145 verwijderd zou worden, terwijl
    het net het eerste testdossier van het nieuwe communicatiesysteem is. Gedeelde les L15."""
    if not dubbels:
        return None
    per = {}
    for x in dubbels:
        per.setdefault(x["dossier"], []).append(x)
    paren = sorted([x["dubbel"], x["id"]] for x in dubbels)
    botsing = [f"rij {x['dubbel']} ({', '.join(x['botsing'])})" for x in dubbels if x.get("botsing")]
    dossiers = ", ".join(f"dossier {d}" for d in sorted(per))
    return {"actie": "Dubbele werfbezoek-rijen samenvoegen na de verhuis van de projectmap: "
                     + ", ".join(f"dossier {d} ({len(v)} rij(en))" for d, v in sorted(per.items()))
                     + ". Het dossier en alle bezoeken blijven",
            "doel": dossiers,
            "reden": (f"{dossiers[0].upper() + dossiers[1:]} blijft volledig; er verdwijnt geen bezoek. "
                      "Na de verhuis van de projectmap staat elk bezoek twee keer: eenmaal met het oude pad, eenmaal met "
                      "het nieuwe. Gegevens, keuzes, bijlagen en proef staan al op de nieuwe rij. Na je ja worden de "
                      f"dubbels ({', '.join(str(p[0]) for p in paren)}) in de nieuwe rij samengevoegd; een volledige kopie "
                      "blijft in werfbezoek_gewist.jsonl."
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


def opnametijd_uit_naam(naam, dag):
    """Een expliciete datum en uur in de naam, nooit de Dropbox-wijzigingsdatum."""
    m = re.search(r"(20\d{2})[-_. ]?(\d{2})[-_. ]?(\d{2})[ T_-]+(\d{2})[:.]?(\d{2})\b", naam)
    if not m or "-".join(m.groups()[:3]) != dag:
        return None
    try:
        return datetime(*map(int, m.groups()), tzinfo=ZoneInfo("Europe/Brussels")).isoformat()
    except ValueError:
        return None


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


def bezoeken_in(projectmap, nummer=None):
    """Bezoeken en nieuwe momentmappen als kandidaten, met hun bestanden naar soort."""
    items = bronnen.lijst(projectmap, recursief=True) or []
    mappen = {}
    for e in items:
        if e.get(".tag") != "folder":
            continue
        pad = e.get("path_display") or ""
        rel = pad[len(projectmap):].lower()
        if not any(a in rel for a in BEZOEK_ANKERS):
            continue
        echte_naam = e.get("name", "")
        naam = echte_naam.lower()
        delen = rel.strip("/").split("/")
        d = datum_uit(naam)
        if not d or any(a in naam for a in ("foto", "photo", "mail", "offerte", "factu")):
            continue
        # een datummap ónder een fotomap is een fotoreeks van het bezoek, geen bezoek
        if any(("foto" in s or "photo" in s) for s in delen[:-1]):
            continue
        moment = MOMENT_VORM_RE.match(echte_naam)
        moment_uur = None
        if moment and moment.group(1) == d and moment.group(4) == str(nummer):
            try:
                moment_uur = datetime(int(d[:4]), int(d[5:7]), int(d[8:10]), int(moment.group(2)),
                                      int(moment.group(3)), tzinfo=ZoneInfo("Europe/Brussels")).isoformat()
            except ValueError:
                pass
        # De oude expliciete bezoeknaam blijft gelden. Een nieuwe naam is alleen kandidaat;
        # pas na agenda- of projectverblijfbewijs komt ze in de bezoekrijen.
        if "communicat" in rel:
            if "bezoek" in naam:
                if any(x in naam for x in ("leverancier", "toonzaal", "online", "tel ")):
                    continue
            elif moment_uur is None:
                continue
        mappen[pad] = {"map": pad, "datum": d, "fotos": 0, "foto_bestanden": [], "foto_manifest": "", "foto_manifest_versies": [], "opnames": [], "opname_starts": [], "transcripten": [], "transcript_bestanden": [],
                       "verslagen": [], "notities": [], "bestanden": 0, "bron_map": rel.strip("/").split("/")[0]}
        if "communicat" in rel and "bezoek" not in naam:
            mappen[pad]["kandidaat_uur"] = moment_uur
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
            # Een los verslag onder een onbewezen momentmap mag die map niet via de
            # oude regel voor losse verslagen alsnog als bezoek binnenbrengen.
            if "communicat" in pad.lower() and any(MOMENT_VORM_RE.match(deel) and "bezoek" not in deel.lower()
                                                  for deel in pad.split("/")):
                continue
            if VERSLAG_PAT.search(naam) and laag.endswith((".docx", ".pdf", ".md")) and datum_uit(naam) \
                    and any(a in pad.lower() for a in BEZOEK_ANKERS):
                losse.append({"pad": pad, "datum": datum_uit(naam)})
            continue
        eigenaar["bestanden"] += 1
        if laag.endswith(FOTO_EXT):
            eigenaar["fotos"] += 1
            eigenaar["foto_bestanden"].append(pad)
        elif laag == "00 fotos.md" and pad.lower().startswith(eigenaar["map"].lower() + "/fotos/"):
            eigenaar["foto_manifest"] = pad
        elif re.fullmatch(r"00 fotos \d{8}t\d{12}\.md", laag) and pad.lower().startswith(eigenaar["map"].lower() + "/fotos/"):
            eigenaar["foto_manifest_versies"].append(pad)
        elif laag.endswith(OPNAME_EXT):
            eigenaar["opnames"].append(naam)
            start = opnametijd_uit_naam(naam, eigenaar["datum"])
            if start:
                eigenaar["opname_starts"].append(start)
        elif TRANSCRIPT_PAT.search(naam) and laag.endswith((".md", ".txt", ".docx")) and not re.search(r"niet getranscribeerd|geen opname|00 fotos", laag):
            eigenaar["transcripten"].append(naam)
            eigenaar["transcript_bestanden"].append(pad)
        elif VERSLAG_PAT.search(naam) and laag.endswith((".docx", ".pdf", ".md")):
            eigenaar["verslagen"].append(naam)
        elif laag.endswith((".docx", ".pdf", ".md", ".txt", ".xlsx", ".pptx")):
            eigenaar["notities"].append(naam)
    for v in losse:
        doel = next((m for m in mappen.values() if m["datum"] == v["datum"]), None)
        if doel:
            doel["verslagen"].append(os.path.basename(v["pad"]))
        else:
            mappen[v["pad"]] = {"map": os.path.dirname(v["pad"]), "datum": v["datum"], "fotos": 0, "foto_bestanden": [], "foto_manifest": "", "foto_manifest_versies": [], "opnames": [], "opname_starts": [],
                                "transcripten": [], "transcript_bestanden": [], "verslagen": [os.path.basename(v["pad"])], "notities": [],
                                "bestanden": 1, "bron_map": "los verslag"}
    uit = sorted(mappen.values(), key=lambda m: (m["datum"], m["map"]))
    for i, m in enumerate(uit, 1):
        m["volgnr"] = i
    return uit


def taakdoel(b):
    """Waar een bron-agent (Plaud, iCloud) de stukken van dit bezoek neerzet.

    Een bezoek dat alleen als los verslag in een verzamelmap bestaat (`4. Werfverslagen`, `1. Werf updates`)
    heeft geen eigen momentmap. Die verzamelmap is geen bezoekmap: een transcript daarin hoort bij geen enkel
    bezoek (nacontrole Plaud v1.1, 12-10-2026). Het doel wordt dan een gedateerde momentmap eronder,
    `<verzamelmap>/JJJJMMDD`, het patroon dat in de light-projecten al bestaat (2416: `4. Werfverslagen/20260427`).
    De map ontstaat pas bij een echte levering; de bezoekrij op het bord blijft dezelfde."""
    if b.get("bron_map") == "los verslag" and b.get("datum"):
        return f'{b["map"].rstrip("/")}/{b["datum"].replace("-", "")}'
    return b["map"]


# Bestemmingen waar een zakelijk transcript voor de werfketen mag staan.
WERF_BESTEMMING = ("h-architects", NAAM)


def transcript_telt(it, d, nummer):
    """Telt dit klaargezette transcript voor H-Architects-dossier `nummer` (nacontrole Plaud v1.1, P1-3)?

    Gestructureerd (inhoud met firma): alleen firma HARC plus hetzelfde projectnummer, bestemming
    h-architects, geen privé, geen conflict en zekerheid hoog of middel. Een item voor Mehdi (beoordeling)
    voedt de werfketen nooit, ook niet bij hetzelfde nummer van een andere firma (UNAB:2531).
    Oud item zonder schema: alleen het nummer als los woord in sleutel of titel, en niet voor Mehdi,
    niet privé (veld of PRIVÉ in de titel); geen vrije zoektocht in de inhoud."""
    if "firma" in d:
        return (d.get("firma") == "HARC" and str(d.get("projectnummer") or "") == str(nummer)
                and it.get("voor") in WERF_BESTEMMING and not d.get("prive") and not d.get("conflict")
                and d.get("zekerheid") in ("hoog", "middel"))
    if it.get("voor") == "mehdi" or d.get("prive") or "PRIVÉ" in (it.get("titel") or "").upper():
        return False
    return bool(re.search(rf"\b{nummer}\b", f'{it.get("sleutel", "")} {it.get("titel", "")}'))


# H-Architects in een agendatitel: HARC, de oudere code HA ("[HA-KB]"), of leeg bij een titel zonder code (E1b).
HA_FIRMA = ("HARC", "HA", "")
BAK_SOORTEN = ("afspraak", "transcript", "werfbezoek", "foto")
BAK_PAGINAS = 12     # per soort hoogstens 12 x 500 items terug


def afspraak_op_dag(bak, nummer, dag):
    """Staat er voor die dag al een H-A-afspraak met dit nummer in de bak (gewone ronde of terugkijken)?"""
    for it in bak.get("afspraak", []):
        d = _inhoud(it)
        if (it.get("van") == "agenda-wacht" and it.get("voor") == "h-architects"
                and str(d.get("nummer") or "") == str(nummer)
                and (d.get("datum") or str(d.get("start") or "")[:10]) == dag):
            return True
    return False


def bak_items():
    """Alle items van de soorten die de voorbereider leest, per soort en terugbladerend.

    Tot 18-10-2026 las hij alleen de laatste 500 items van de hele bak (alle agents samen). De afspraak
    van 2145 werfbezoek 1 (15-09, item 447) viel daardoor weg terwijl de bak boven de 2.900 zat, en W1
    bleef 'ontbreekt'. Nu per soort, met tot_id, tot een pagina korter is dan 500.
    """
    gezien, uit = set(), []
    for soort in BAK_SOORTEN:
        tot = None
        for _ in range(BAK_PAGINAS):
            pad = f"/api/klaarzet?status=alle&soort={soort}&n=500" + (f"&tot_id={tot}" if tot else "")
            items = bord.call(pad).get("items", [])
            for it in items:
                if it.get("soort") != soort:
                    continue
                k = it.get("id") or it.get("uniek") or json.dumps(it, sort_keys=True, default=str)
                if k in gezien:
                    continue
                gezien.add(k)
                uit.append(it)
            ids = [it["id"] for it in items if isinstance(it.get("id"), int)]
            if len(items) < 500 or not ids:
                break
            tot = min(ids)
    return uit


def klaargezet(nummer):
    """Wat de andere agents over dit dossier klaarzetten, per soort."""
    try:
        alles = bak_items()
    except Exception as e:  # noqa: BLE001
        ag.log(str(nummer), "fout", f"bord niet bereikbaar: {e}")
        return {}
    per = {"afspraak": [], "transcript": [], "foto": []}
    for it in alles:
        # De Plaudwacht zette tot 12-10-2026 sommige transcripten klaar als soort "werfbezoek" (met de
        # deal-id als sleutel): die telden hier niet. Ze tellen nu als transcript (verbeteropdracht v1.0, §4).
        soort = "transcript" if it["soort"] == "werfbezoek" else it["soort"]
        if soort not in per:
            continue
        inhoud = it.get("inhoud") or ""
        try:
            d = json.loads(inhoud) if inhoud.startswith("{") else {}
        except ValueError:
            d = {}
        if soort == "transcript":
            if transcript_telt(it, d, nummer):
                per[soort].append(it)
            continue
        tekst = f'{it.get("sleutel", "")} {it.get("titel", "")} {inhoud[:400]}'
        if soort == "foto" or re.search(rf"\b{nummer}\b", tekst):
            per[soort].append(it)
    return per


def dag_van(it):
    inhoud = it.get("inhoud") or ""
    try:
        d = json.loads(inhoud) if inhoud.startswith("{") else {}
    except ValueError:
        d = {}
    return (d.get("datum") or d.get("start") or it.get("sleutel") or it.get("titel") or "")[:10]


def _inhoud(it):
    inhoud = it.get("inhoud") or {}
    if isinstance(inhoud, dict):
        return inhoud
    try:
        waarde = json.loads(inhoud) if isinstance(inhoud, str) else {}
        return waarde if isinstance(waarde, dict) else {}
    except ValueError:
        return {}


def tijdstip(waarde):
    try:
        t = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
        return t if t.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def kandidaatbewijs(bezoek, bak, nummer):
    """E1b: een nieuwe momentnaam bewijst zelf geen bezoek; tijd en project moeten kloppen."""
    moment = tijdstip(bezoek.get("kandidaat_uur"))
    if not moment:
        return None
    for it in bak.get("afspraak", []):
        d = _inhoud(it)
        if (it.get("van") != "agenda-wacht" or it.get("voor") != "h-architects"
                or (d.get("firma") or "") not in HA_FIRMA
                or it.get("soort") != "afspraak" or it.get("status") == "vervallen"
                or str(d.get("nummer") or "") != str(nummer) or d.get("buiten") is not True
                or d.get("geannuleerd") or d.get("status") in ("cancelled", "geannuleerd")
                or d.get("prive") or (d.get("datum") and d["datum"] != bezoek["datum"])):
            continue
        start, einde = tijdstip(d.get("start")), tijdstip(d.get("einde"))
        if (not start or not einde or einde <= start or einde - start > timedelta(days=1)
                or start.astimezone(ZoneInfo("Europe/Brussels")).date().isoformat() != bezoek["datum"]):
            continue
        if start - timedelta(minutes=30) <= moment <= einde + timedelta(minutes=60):
            return "agenda", d.get("titel") or it.get("titel") or "H-A-buitenafspraak"
    verblijven = LC.verblijven_in_venster((moment - timedelta(minutes=15)).isoformat(),
                                          (moment + timedelta(minutes=60)).isoformat(), "HARC", nummer)
    if verblijven:
        return "gps", LC.beschrijf(verblijven[0])
    return None


def teruggekeken_op_dag(bak, dag):
    """Een eerdere terugblik op deze dag herhalen levert geen nieuw agendabewijs op."""
    return any(it.get("van") == "agenda-wacht" and _inhoud(it).get("terugkijken") is True
               and dag_van(it) == dag for it in bak.get("afspraak", []))


def foto_momenten(bak, dag):
    """Alleen tijd en GPS uit de iCloud-wacht, niet een titel met dezelfde bezoekdag."""
    uit = []
    for it in bak.get("foto", []):
        if it.get("van") != "icloud-wacht" or dag_van(it) != dag:
            continue
        d = _inhoud(it)
        for f in d.get("fotos") or []:
            t = tijdstip(f.get("vastgelegd_utc") or f.get("tijdstip"))
            if t and isinstance(f.get("lat"), (int, float)) and isinstance(f.get("lon"), (int, float)):
                uit.append((t, f["lat"], f["lon"]))
        if not d.get("fotos"):
            t = tijdstip(d.get("vastgelegd_utc") or d.get("tijdstip"))
            if t and isinstance(d.get("lat"), (int, float)) and isinstance(d.get("lon"), (int, float)):
                uit.append((t, d["lat"], d["lon"]))
    return uit


def opname_momenten(bezoek, bak=None):
    """Alleen expliciete opname-start; een bestandsdatum is geen opnametijd."""
    tijden = list(bezoek.get("opname_starts", []))
    for it in (bak or {}).get("transcript", []):
        if it.get("van") == "plaud-wacht" and dag_van(it) == bezoek["datum"]:
            d = _inhoud(it)
            tijden.append(d.get("opname_start") or d.get("start_at"))
    return [t for t in (tijdstip(x) for x in tijden) if t]


def e4_venster(bezoek, bak, nummer=None, adres=""):
    fotos = foto_momenten(bak, bezoek["datum"])
    if fotos:
        coord = projectcoordinaten(nummer, adres, bak) if nummer and adres else None
        fotos = [(t, lat, lon) for t, lat, lon in fotos if coord and afstand_m(*coord, lat, lon) <= 300]
    momenten = [x[0] for x in fotos] + opname_momenten(bezoek, bak)
    if not momenten:
        return None
    return {"start": (min(momenten) - timedelta(minutes=15)).astimezone(ZoneInfo("Europe/Brussels")).isoformat(),
            "einde": (max(momenten) + timedelta(minutes=60)).astimezone(ZoneInfo("Europe/Brussels")).isoformat(),
            "reden": "E4, geen afspraak"}


def venster_voor(nummer, bezoek, bezoeken, bak, bezoek_id="", adres=""):
    try:
        return bevestigd_fotovenster(nummer, bezoek, bezoeken, bak, bezoek_id)
    except ValueError:
        return e4_venster(bezoek, bak, nummer, adres)


def in_venster(t, venster):
    return bool(t and venster and tijdstip(venster.get("start")) <= t < tijdstip(venster.get("einde")))


def afstand_m(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 12742000 * math.asin(min(1, math.sqrt(max(0, a))))


def projectcoordinaten(nummer, adres, bak):
    """Een expliciet coördinaat bij hetzelfde H-A-projectadres; onbekend blijft onbekend."""
    # Een foto meldt haar eigen GPS-plek; die mag niet tegelijk de bouwplaats bepalen.
    for it in bak.get("afspraak", []):
        d = _inhoud(it)
        if it.get("van") != "agenda-wacht" or it.get("soort", "afspraak") != "afspraak" or d.get("firma") != "HARC":
            continue
        plek = d.get("bouwplaats") if isinstance(d.get("bouwplaats"), dict) else d
        if (str(d.get("nummer") or d.get("projectnummer") or "") == str(nummer)
                and str(plek.get("adres") or "").casefold() == adres.casefold()
                and isinstance(plek.get("lat"), (int, float)) and isinstance(plek.get("lon"), (int, float))):
            return plek["lat"], plek["lon"]
    # De tegel koppelt verblijven aan exact deze projectplekken (binnen 300 m); via de gedeelde lezer.
    return LC.projectplek("HARC", nummer)


def aanwezigheidsbewijs(nummer, adres, bezoek, bak, venster):
    """W2: was Mehdi ter plaatse? Geeft (stand, toelichting).

    Een foto met GPS, opname-start of projectverblijf in het venster telt. Volgens E1b
    telt ook de auto bij het project als aanwezigheid van Mehdi. Locatie komt uitsluitend
    via locatiecontext (startgrens van de meetreeks, alleen positieve projectverblijven).
    """
    voor_meetreeks = not LC.bronbeleid.dag_toegestaan(bezoek["datum"])
    if not venster:
        if voor_meetreeks:
            return "onbekend", "vóór de GPS-meetreeks (03-10-2026) en zonder agendavenster"
        return "ontbreekt", "geen bezoekvenster om aanwezigheid in te toetsen"
    coord = projectcoordinaten(nummer, adres, bak) if bak.get("foto") else None
    if coord and any(in_venster(t, venster) and afstand_m(*coord, lat, lon) <= 300
                     for t, lat, lon in foto_momenten(bak, bezoek["datum"])):
        return "ok", "foto met GPS van de iCloud-wacht binnen 300 m in het bezoekvenster"
    if any(in_venster(t, venster) for t in opname_momenten(bezoek, bak)):
        return "ok", "opname met start in het bezoekvenster"
    verblijven = LC.verblijven_in_venster(venster["start"], venster["einde"], "HARC", nummer)
    persoon = [x for x in verblijven if x.get("rol") != "auto"]
    if persoon:
        return "ok", "gedragen tracker bij het project: " + LC.beschrijf(persoon[0])
    if verblijven:
        return "ok", "auto bij het project; Mehdi gaat altijd met de auto, E1b (" + LC.beschrijf(verblijven[0]) + ")"
    if voor_meetreeks:
        # Toen bestond de GPS-meting nog niet: dat is niet gekeken, geen bewijs van afwezigheid. Mehdi gaat altijd met de
        # auto; de buitenafspraak in de agenda (W1) is voor die dagen het bewijs (E1b, 18-10-2026).
        return "onbekend", "vóór de GPS-meetreeks (03-10-2026); de buitenafspraak in de agenda (W1) is het bewijs"
    return "ontbreekt", "geen GPS-foto, opname of projectverblijf binnen het venster"


def fotobewijs(bezoek, venster):
    paden = bezoek.get("foto_bestanden") or []
    in_map = [p for p in paden if p.lower().startswith(bezoek["map"].lower() + "/fotos/")]
    bruikbaar = [p for p in in_map if p.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    canoniek = bezoek.get("foto_manifest")
    manifest = max(bezoek.get("foto_manifest_versies") or [canoniek or ""])
    if not bruikbaar or not canoniek or not venster:
        return "let_op" if paden else "ontbreekt"
    try:
        inhoud = bronnen.download(manifest, maximum=100_000).decode("utf-8")
    except (OSError, UnicodeError, ValueError, AttributeError, TypeError):
        return "let_op"
    # De iCloud-wacht schrijft per geleverd bestand de opnametijd; een vensterregel alleen bewijst dat niet.
    tijden = {naam: tijdstip(t) for t, naam in re.findall(r"(?m)^- (\S+T\S+) \| ([^\r\n|]+)$", inhoud)}
    def opname_tijd(p):
        naam = os.path.basename(p)
        return tijden.get(naam) or tijden.get(os.path.splitext(naam)[0] + ".HEIC") or tijden.get(os.path.splitext(naam)[0] + ".heic")
    if not tijden or any(not in_venster(opname_tijd(p), venster) for p in bruikbaar):
        return "let_op"
    return "ok"


def contractbewijs(nummer):
    """Groen uitsluitend bij een getekend dossier met expliciete werfopvolging."""
    mcp_ontbreekt = False
    try:
        d = contracten_mcp.call("dossier", project_nummer=str(nummer), soort="architectuur")
    except contracten_mcp.ToolFout as ex:
        mcp_ontbreekt = "Geen dossier gevonden" in str(ex)
        d = None
    except Exception:  # noqa: BLE001
        d = None
    if d is None:
        try:
            d = werfapp.call(f"/projecten/{nummer}")
        except Exception:  # noqa: BLE001
            if mcp_ontbreekt:
                # Een project van vóór het contractsysteem (bv. 2173, 2021) staat er nooit in: dat is
                # onbekend, geen ontbrekend contract. Het getekende contract ligt dan in de projectmap.
                return "onbekend", "project niet in het contractdashboard (vermoedelijk van vóór het systeem); bekijk het getekende contract in de projectmap"
            return "onbekend", "contract-dashboard en werfapp niet bereikbaar"
    if not isinstance(d, dict):
        return "onbekend", "contractantwoord is niet toetsbaar"
    metadata = d.get("dossier") if isinstance(d.get("dossier"), dict) else d
    if not any(k in metadata for k in ("stand", "status", "velden", "keuzes")):
        return "onbekend", "geen contractgegevens in het antwoord"
    velden = d.get("velden") or metadata.get("velden") or metadata
    keuzes = d.get("keuzes") or metadata.get("keuzes") or velden
    if not isinstance(velden, dict) or not isinstance(keuzes, dict):
        return "onbekend", "contractvelden zijn niet toetsbaar"
    stand = str(metadata.get("stand") or metadata.get("status") or "").lower()
    scope = keuzes.get("architectuur_scope") or velden.get("architectuur_scope")
    opvolging = keuzes.get("werfopvolging_keuze") or velden.get("werfopvolging_keuze")
    if stand != "getekend" or not scope or str(opvolging).lower() not in ("ja", "inbegrepen", "true", "1"):
        return "ontbreekt", "geen getekend contract met uitdrukkelijke werfopvolging bewezen"
    return "ok", "getekend contract; werfopvolging inbegrepen"


def werfapp_bezoeken(nummer):
    teller = []
    try:
        project = werfapp.call(f"/projecten/{nummer}")
        if isinstance(project, dict):
            if re.fullmatch(r"\d+", str(project.get("werfbezoek_teller") or "")):
                teller = [{"werfbezoek_teller": project["werfbezoek_teller"]}]
            if isinstance(project.get("verslagen"), list):
                return project["verslagen"] + teller  # inclusief ArchiSnapper-historiek en verzendgeschiedenis
    except Exception:  # noqa: BLE001
        pass
    try:
        antwoord = werfapp.call(f"/projecten/{nummer}/bezoeken")
        bezoeken = antwoord if isinstance(antwoord, list) else antwoord.get("bezoeken") or []
        return bezoeken + teller
    except Exception:  # noqa: BLE001
        return teller or None


def bevestigd_fotovenster(nummer, bezoek, bezoeken, bak, bezoek_id):
    """Expliciet H-A-agendabewijs; bij meerdere bezoeken geen koppeling op alleen dag."""
    geldig = []
    for it in bak.get("afspraak", []):
        d = _inhoud(it)
        if (it.get("van") != "agenda-wacht" or it.get("soort") != "afspraak"
                or it.get("status") == "vervallen"
                # Altijd de afdeling H-Architects; de firma is HARC, of leeg bij een titel zonder code (E1b). Een andere
                # firma (UNAB, ...) of een andere afdeling is nooit H-A-bewijs (tests/test_werf_fotoproducent.py).
                or it.get("voor") != "h-architects" or (d.get("firma") or "") not in HA_FIRMA
                or str(d.get("nummer") or "") != str(nummer)
                or d.get("onzeker") is not False or d.get("buiten") is not True or not d.get("agenda")
                # E1b: elke buitenafspraak met dit nummer telt; een ingevuld type moet wel een bezoektype zijn.
                or (d.get("type") and d.get("type") not in ("WB", "PL", "PLB", "OP", "OPL", "VO", "DO"))
                or d.get("prive") or d.get("geannuleerd") or d.get("status") in ("cancelled", "geannuleerd")):
            continue
        try:
            start = datetime.fromisoformat(d["start"].replace("Z", "+00:00"))
            einde = datetime.fromisoformat(d["einde"].replace("Z", "+00:00"))
            if (start.tzinfo is None or einde.tzinfo is None or einde <= start or einde - start > timedelta(days=1)
                    or start.astimezone(ZoneInfo("Europe/Brussels")).date().isoformat() != bezoek["datum"]):
                continue
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if d.get("datum") and d["datum"] != bezoek["datum"]:
            continue
        if d.get("project_ref") and d["project_ref"] != "h-architects:" + str(nummer):
            continue
        # Een expliciete bezoek-ID of map wint; nooit de eerste afspraak van een dag kiezen.
        if d.get("bezoek_id") or d.get("bezoekmap"):
            if d.get("bezoek_id") and d["bezoek_id"] != bezoek_id:
                continue
            if d.get("bezoekmap") and (not isinstance(d["bezoekmap"], str)
                                      or d["bezoekmap"].casefold() not in (bezoek["map"].casefold(), taakdoel(bezoek).casefold())):
                continue
        elif sum(b["datum"] == bezoek["datum"] for b in bezoeken) != 1:
            continue
        geldig.append({"start": start.astimezone(ZoneInfo("Europe/Brussels")).isoformat(),
                       "einde": einde.astimezone(ZoneInfo("Europe/Brussels")).isoformat(),
                       "agenda_uniek": it.get("uniek"), "agenda": d["agenda"]})
    # Dezelfde afspraak staat soms twee keer in de bak (21-09-2026: één keer met firma HA, één keer met HARC):
    # hetzelfde tijdvak is hetzelfde bewijs, geen dubbelzinnigheid.
    per_venster = {}
    for g in geldig:
        per_venster.setdefault((g["start"], g["einde"]), g)
    geldig = list(per_venster.values())
    if len(geldig) != 1:
        raise ValueError("bezoekvenster_dubbelzinnig" if len(geldig) > 1 else "bezoekvenster_ontbreekt")
    return geldig[0]


def fototaak(nummer, adres, projectmap, bezoek, bezoeken, bak, registratie):
    bid = registratie.get("bezoek_id")
    try:
        if not isinstance(bid, str) or str(uuid.UUID(bid)) != bid:
            raise ValueError
    except ValueError:
        raise ValueError("bronregistratie_ontbreekt") from None
    venster = venster_voor(nummer, bezoek, bezoeken, bak, registratie["bezoek_id"], adres)
    if not venster:
        raise ValueError("bezoekvenster_ontbreekt")
    coord = projectcoordinaten(nummer, adres, bak)
    if not coord:
        raise ValueError("werfcoordinaten_ontbreken")
    project_ref = "h-architects:" + str(nummer)
    if registratie.get("project_ref") != project_ref:
        raise ValueError("projectidentiteit_ontbreekt")
    doel = taakdoel(bezoek)
    vensternaam = "E4-terugvalvenster" if venster.get("reden") == "E4, geen afspraak" else "H-A-bezoekvenster"
    return {"voor": "icloud-wacht", "soort": "taak", "sleutel": str(nummer),
            "titel": f"Foto's voor bezoek {registratie['bezoek_id']} van dossier {nummer} binnen het {vensternaam} en 300 m",
            "inhoud": {"dossier": str(nummer), "project_ref": project_ref, "bezoek_id": registratie["bezoek_id"],
                       "datum": bezoek["datum"], "adres": adres, "projectmap": projectmap, "bezoekmap": doel,
                       "volgnr": bezoek["volgnr"], "nr_label": bezoek["nr_label"], "soort_bezoek": bezoek["soort_bezoek"],
                       "lat": coord[0], "lon": coord[1], "straal": 300, "straal_m": 300, **venster,
                       "bezoeksleutel": f"{nummer}:{bezoek['datum']}:{doel}"}, "verwijzing": doel,
            "uniek": f"werf:{project_ref}:{registratie['bezoek_id']}:icloud-wacht"}


# ------------------------------------------------------- controleposten ---
def controleer(nummer, adres, soort_project, projectmap, bezoek, bak, bord_rij=None, bezoeken=None):
    """Geeft (controles, taken, noden). controles: lijst {code, naam, stand, toelichting}.
    stand in ok | ontbreekt | onbekend | nvt."""
    d = bezoek["datum"]
    c, taken, noden = [], [], []

    def post(code, naam, stand, toel=""):
        c.append({"code": code, "naam": naam, "stand": stand, "toelichting": toel})

    br = dict(bord_rij or {})
    # De koppeling uit deze ronde is al vastgelegd vóór de bordrij wordt bijgewerkt.
    # Een oud bordpad mag een agenda-item met het nieuwe bezoek-ID niet afwijzen.
    if bezoek.get("registratie"):
        br["registratie"] = bezoek["registratie"]
    try:
        venster = bevestigd_fotovenster(nummer, bezoek, bezoeken or [bezoek], bak,
                                         (br.get("registratie") or {}).get("bezoek_id", ""))
        post("W1", "afspraak in de agenda", "ok", "H-A-afspraak, dossier en buitenvenster bevestigd")
    except ValueError:
        venster = e4_venster(bezoek, bak, nummer, adres)
        if venster:
            post("W1", "afspraak in de agenda", "let_op", "bevestigd door foto's/opname, niet door de agenda")
        elif d < AGENDAWACHT_SINDS:
            post("W1", "afspraak in de agenda", "onbekend", f"bezoek van vóór {AGENDAWACHT_SINDS}: geen agendabewijs")
        else:
            post("W1", "afspraak in de agenda", "ontbreekt", "geen geldige H-A-buitenafspraak met dit dossier en venster")
    # W2 aanwezigheid, W3 de mappen.
    w2_stand, w2_toel = aanwezigheidsbewijs(nummer, adres, bezoek, bak, venster)
    post("W2", "aanwezigheid", w2_stand, w2_toel)
    post("W3", "projectmap en bezoekmap", "ok" if projectmap and bezoek.get("map") and bezoek.get("bron_map") != "los verslag" else "ontbreekt",
         f"{soort_project}: {projectmap}; {bezoek.get('map', '')}")
    # W4 foto's
    foto_stand = fotobewijs(bezoek, venster)
    if foto_stand != "ontbreekt":
        post("W4", "foto's", foto_stand, f"{bezoek['fotos']} foto('s); alleen fotos/ met tijdsbewijs in 00 fotos.md is volledig")
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
    directe_transcripten = [p for p in bezoek.get("transcript_bestanden", [])
                           if os.path.dirname(p).casefold() == bezoek["map"].casefold()
                           and (werfnamen.eigen_transcript(os.path.basename(p))
                                or os.path.basename(p).lower() == "01 transcript.md")]
    if directe_transcripten:
        post("W6", "transcript", "ok", "; ".join(os.path.basename(p) for p in directe_transcripten)[:160])
    elif transcripten_bak:
        post("W6", "transcript", "ontbreekt", "transcript staat alleen in de klaarzetbak, nog niet in de bezoekmap")
        taken.append(("plaud-wacht", f"Plaats het transcript in de bezoekmap {taakdoel(bezoek)} voor dossier {nummer}"))
    elif bezoek["opnames"]:
        post("W6", "transcript", "ontbreekt", "opname zonder transcript in de map")
        taken.append(("plaud-wacht", f"Transcript maken/ophalen van de opname in {bezoek['map']} (dossier {nummer}, {d})"))
    else:
        post("W6", "transcript", "ontbreekt", "geen eigen transcript in de bezoekmap (naamvormen in koppelingen/werfnamen.py)")
    # W7 verslag; W11 nacontrole van de proef van Werfverslag schrijver
    if bezoek["verslagen"]:
        post("W7", "verslag of concept", "ok", "; ".join(bezoek["verslagen"])[:160])
    elif br.get("proef_pad"):
        post("W7", "verslag of concept", "ok", f"proef van Werfverslag schrijver: {os.path.basename(br['proef_pad'])}")
    else:
        post("W7", "verslag of concept", "ontbreekt", "nog geen verslag; Werfverslag schrijver maakt het concept na Mehdi's klik Maak concept op de bezoekpagina")
    if br.get("proef_pad"):
        info = br.get("proef_info") or {}
        if isinstance(info, str):
            try:
                info = json.loads(info or "{}")
            except ValueError:
                info = {}
        op = info.get("open") or {}
        n_open = sum(int(x or 0) for x in op.values()) if isinstance(op, dict) else 0
        # CX3-16: dit is een automatische telling van open plaatshouders, geen menselijke lezing. Mehdi leest na in de
        # werfapp (nakijken per punt; versturen kan pas als alles nagekeken is).
        post("W11", "proef zonder open plaatshouders", "ok" if n_open == 0 else "onbekend",
             f"{info.get('punten', '?')} punten, {info.get('fotos', '?')} foto's; nog {op.get('in_te_vullen', '?')} in te vullen, "
             f"{op.get('na_te_kijken', '?')} na te kijken, {op.get('raming_open', '?')} ramingen open" if isinstance(op, dict) else "geen telling")
    elif not (br.get("gegevens") or {}).get("gegevens") if isinstance(br.get("gegevens"), dict) else not br.get("gegevens"):
        # Regel van Mehdi (13-09-2026): geen voorbereiding en geen proef zonder zijn knop; elke stap kost tokens.
        post("W11", "voorbereiding door de schrijver", "onbekend", "wacht op Mehdi: knop Maak concept op de bezoekpagina (kost tokens, dus nooit automatisch)")
    else:
        post("W11", "voorbereiding door de schrijver", "ok", "gegevens met herkomst staan op de bezoekpagina; Maak concept is aan Mehdi")
    # W8 verslagnummer
    app_bezoeken = werfapp_bezoeken(nummer)
    if bezoek.get("soort_bezoek") == "plaatsbezoek":
        post("W8", "verslagnummer", "ok", f"{nummer}-{bezoek['nr_label']}: plaatsbezoek vóór de werfstart, geen werfverslagnummer (A7/A8)")
    elif app_bezoeken is None:
        post("W8", "verslagnummer", "onbekend", "werfapp kent dit project niet of is niet bereikbaar; nummer niet geijkt")
    else:
        nummers = [int(str(v.get("volgnummer") or v.get("werfbezoek_teller") or v.get("weergave_nummer")))
                   for v in app_bezoeken if isinstance(v, dict)
                   and re.fullmatch(r"\d+", str(v.get("volgnummer") or v.get("werfbezoek_teller") or v.get("weergave_nummer") or ""))]
        lokaal = int(bezoek.get("werfnr") or 0)
        if not nummers:
            post("W8", "verslagnummer", "onbekend", "werfapp gaf geen toetsbaar bezoeknummer")
        else:
            hoogste = max(nummers)
            post("W8", "verslagnummer", "let_op" if hoogste > lokaal else "ok",
                 "nummer wijkt af van de werfapp" if hoogste > lokaal else f"{nummer}-{bezoek.get('nr_label', bezoek['volgnr'])}; geijkt op de werfapp")
    # W9 verstuurd
    app_id = ((br.get("proef_info") or {}).get("werfapp") or {}).get("id") if isinstance(br.get("proef_info"), dict) else None
    nummer_app = f"{nummer}-{bezoek.get('nr_label', bezoek['volgnr'])}"
    bewijs = [v for v in app_bezoeken or [] if isinstance(v, dict)
              and (v.get("bezoek_id") and v.get("bezoek_id") == (br.get("registratie") or {}).get("bezoek_id")
                   or app_id is not None and v.get("id") == app_id or v.get("nummer") == nummer_app)]
    verzonden = any(v.get("status") == "verzonden" or v.get("verstuurd") is True
                   or v.get("verzonden") is True
                   or isinstance(v.get("verzonden"), list) and any(isinstance(z, dict) and (z.get("status") or "verstuurd") == "verstuurd"
                                                              for z in v["verzonden"]) for v in bewijs)
    post("W9", "verstuurd aan de klant", "ok" if verzonden else "onbekend",
         "werfapp bevestigt verzonden verslag" if verzonden else "geen verzendbewijs uit de werfapp")
    contract_stand, contract_toel = contractbewijs(nummer)
    post("W12", "getekend contract en werfopvolging", contract_stand, contract_toel)
    if bezoek["notities"]:
        post("W10", "notities in de map", "ok", "; ".join(bezoek["notities"])[:160])
    return c, taken, noden


def stand_van(controles):
    s = {x["code"]: x["stand"] for x in controles}
    bronnen_ok = all(s.get(k) == "ok" for k in ("W2", "W3", "W4", "W5", "W6", "W12", "WERFSTART")) and s.get("W1") in ("ok", "let_op")
    if s.get("W7") == "ok":
        return "verslag aanwezig" if bronnen_ok else "verslag aanwezig, bronnen onvolledig"
    return "klaar voor verslag" if bronnen_ok else "te verzamelen"


def ontbrekende_posten(controles):
    nodig = ("W1", "W2", "W3", "W4", "W5", "W6", "W12", "WERFSTART")
    return [f"{x['code']} {x['naam']}" for x in controles
            if x["code"] in nodig and x["stand"] not in (("ok", "let_op") if x["code"] == "W1" else ("ok",))]


def bezoeksleutel(nummer, bezoek):
    return f"{nummer}:{bezoek['datum']}:{taakdoel(bezoek)}"


# ------------------------------------------------------------- de ronde ---
def verwerk(nummer, droog=False):
    ag.log(str(nummer), "bron", f"dossier {nummer}: projectmap zoeken")
    projectmap, soort = zoek_projectmap(nummer)
    if not projectmap:
        ag.log(str(nummer), "fout", "geen projectmap gevonden in STAN-fasen of light SITE VISITS")
        return [], [{"tekst": f"Dossier {nummer}: geen projectmap gevonden; Mehdi geeft het pad", "wie": "mehdi"}], []
    adres = adres_uit_mapnaam(os.path.basename(projectmap))
    ag.log(str(nummer), "bron", f"projectmap ({soort}): {projectmap}", {"adres": adres})
    bezoeken = bezoeken_in(projectmap, nummer)
    bak = klaargezet(nummer)
    terugkijk_taken, bewezen = [], []
    taakdagen = set()
    vandaag = datetime.now(ZoneInfo("Europe/Brussels")).date().isoformat()
    for b in bezoeken:
        if "kandidaat_uur" not in b:
            bewezen.append(b)
            # Ook een bezoek dat al aan zijn naam herkend is, heeft voor W1 de agenda van die dag nodig. Staat er voor
            # een oude dag niets in de bak, dan kijkt de Agendawacht alleen lezend terug (E1b, 18-10-2026).
            if (b["datum"] < vandaag and b["datum"] not in taakdagen and not teruggekeken_op_dag(bak, b["datum"])
                    and not afspraak_op_dag(bak, nummer, b["datum"])):
                taakdagen.add(b["datum"])
                terugkijk_taken.append({"voor": "agenda-wacht", "soort": "taak", "sleutel": str(nummer),
                                       "titel": f"Kijk alleen lezend terug op {b['datum']} voor dossier {nummer}",
                                       "inhoud": {"terugkijken": b["datum"], "dossier": str(nummer)},
                                       "uniek": f"werf:terugkijken:{nummer}:{b['datum']}"})
            continue
        bewijs = kandidaatbewijs(b, bak, nummer)
        if bewijs:
            b["herkend_via"], b["herkenning_bewijs"] = bewijs
            bewezen.append(b)
        elif b["datum"] < vandaag and b["datum"] not in taakdagen and not teruggekeken_op_dag(bak, b["datum"]):
            taakdagen.add(b["datum"])
            terugkijk_taken.append({"voor": "agenda-wacht", "soort": "taak", "sleutel": str(nummer),
                                   "titel": f"Kijk alleen lezend terug op {b['datum']} voor dossier {nummer}",
                                   "inhoud": {"terugkijken": b["datum"], "dossier": str(nummer)},
                                   "uniek": f"werf:terugkijken:{nummer}:{b['datum']}"})
    bezoeken = bewezen
    for i, b in enumerate(bezoeken, 1):
        b["volgnr"] = i
    werfstart = (dossiers_lezen().get(str(nummer)) or {}).get("werfstart", "")
    try:
        alle_rijen = bord.call(f"/api/werfbezoek?dossier={nummer}").get("rijen", [])
    except Exception:  # noqa: BLE001
        alle_rijen = []
    if not droog and bezoeken:
        try:
            bezoeken = vooraf_koppelen(bezoeken, str(nummer), projectmap, werfstart, alle_rijen)
        except werfregister.RegisterFout as ex:
            ag.log(str(nummer), "fout", f"werfapp-identiteit vóór nummering niet bevestigd: {ex}")
            for b in bezoeken:
                if not b.get("registratie"):
                    b["registratie_blokkade"] = True
    bezoeken = nummer_bezoeken(bezoeken, werfstart)
    ag.log(str(nummer), "bevinding", f"{len(bezoeken)} bezoek(en) in de mappen: " + ", ".join(f"{b['nr_label']} {b['datum']}" for b in bezoeken)
           + (f"; werfstart {werfstart}" if werfstart else "; geen werfstart bekend"))
    bord_rijen = {r.get("bezoekmap"): r for r in alle_rijen}
    open_taken = {}
    for agent in ("icloud-wacht", "plaud-wacht", "agenda-wacht"):
        try:
            open_taken[agent] = [it for it in bord.klaargezet_voor(agent, n=300) if it.get("soort") == "taak" and it.get("van") == NAAM]
        except Exception:  # noqa: BLE001
            open_taken[agent] = []
    rijen, alle_taken, noden, dubbels, fotowerk, gesloten_ids = [], [
        t for t in terugkijk_taken if not any(o.get("uniek") == t["uniek"] for o in open_taken["agenda-wacht"])
    ], [], [], [], set()
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
    # Kan niet worden nagegaan of een map bestaat, dan doen we niets: geen koppeling en geen "verdwenen".
    bestaat = getattr(bronnen, "bestaat", None) or (lambda _pad: True)
    hernoemd = hernoemde_rijen(bezoeken, projectmap, alle_rijen, bestaat, verhuisd.values())
    for mp, oude in hernoemd.items():
        verhuisd.setdefault(mp, []).extend(oude)
        ag.log(str(nummer), "bevinding", f"bezoekmap hernoemd: {', '.join(os.path.basename(r['bezoekmap']) for r in oude)} "
               f"heet nu {os.path.basename(mp)}; de rij gaat mee")
    verdwenen = verdwenen_rijen(bezoeken, alle_rijen, bestaat, verhuisd.values())
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
        controles, taken, n = controleer(nummer, adres, soort, projectmap, b, bak,
                                         samengevoegd([bord_rijen.get(b["map"])] + oude), bezoeken)
        st = {c["code"]: c["stand"] for c in controles}
        for code, agent in (("W6", "plaud-wacht"), ("W4", "icloud-wacht")):
            if st.get(code) == "ok":
                for it in open_taken.get(agent, []):
                    if (_inhoud(it).get("bezoeksleutel") == bezoeksleutel(nummer, b)
                            and it.get("id") not in gesloten_ids):
                        try:
                            bord.opgepakt(it["id"], NAAM)
                            gesloten_ids.add(it["id"])
                            ag.log(str(nummer), "besluit", f"taak voor {agent} ({b['datum']}) afgevinkt: bron staat in de map")
                        except Exception:  # noqa: BLE001
                            pass
        noden += n
        taakrijen = []
        for voor, tekst in taken:
            if voor == "icloud-wacht":
                continue  # pas publiceren na de opgeslagen bordrij en vaste bezoekregistratie
            uniek = f"werf:{bezoeksleutel(nummer, b)}:{voor}"
            # eigen naam: 'soort' is het soort project (standaard, light); overschrijven gaf 'taak-project' op de pagina
            taaksoort = "opdracht" if voor == "werfverslag-schrijver" else "taak"
            doel = taakdoel(b) if voor in ("plaud-wacht", "icloud-wacht") else b["map"]
            taakrijen.append({"voor": voor, "soort": taaksoort, "sleutel": (f"{nummer}-{b['volgnr']}" if taaksoort == "opdracht" else str(nummer)), "titel": tekst[:300],
                              "inhoud": {"dossier": nummer, "datum": b["datum"], "adres": adres, "bezoekmap": doel, "volgnr": b["volgnr"],
                                         "nr_label": b["nr_label"], "soort_bezoek": b["soort_bezoek"],
                                         "bezoeksleutel": bezoeksleutel(nummer, b),
                                         **({"verzamelmap": b["map"]} if doel != b["map"] else {})},
                              "verwijzing": doel, "uniek": uniek})
        alle_taken += [t for t in taakrijen if not any(o.get("uniek") == t["uniek"] for o in open_taken.get(t["voor"], []))]
        if not werfstart:
            controles.append({"code": "WERFSTART", "naam": "werfstart", "stand": "onbekend",
                              "toelichting": "werfstart ontbreekt; bezoektype en verslagnummer na te kijken"})
        ontbrekend = ontbrekende_posten(controles)
        if ontbrekend:
            controles.append({"code": "NODIG", "naam": "Nog te verzamelen", "stand": "let_op", "toelichting": ", ".join(ontbrekend)})
        rijen.append({"dossier": str(nummer), "adres": adres, "soort_project": soort, "projectmap": projectmap,
                      "bezoekmap": b["map"], "datum": b["datum"], "volgnr": b["volgnr"],
                      "registratie": b.get("registratie") or {},
                      "bronnen": {**{k: b[k] for k in ("fotos", "opnames", "transcripten", "verslagen", "notities", "bestanden", "bron_map")},
                                  "nr_label": b["nr_label"], "soort_bezoek": b["soort_bezoek"], "werfstart": werfstart,
                                  **({"herkend_via": b["herkend_via"], "herkenning_bewijs": b["herkenning_bewijs"]}
                                     if b.get("herkend_via") else {})},
                      "controles": controles, "taken": [{"voor": t["voor"], "titel": t["titel"], "uniek": t["uniek"]} for t in taakrijen],
                      "stand": stand_van(controles)})
        if oude:
            rijen[-1]["vorige_bezoekmappen"] = [r["bezoekmap"] for r in oude]
        fotowerk.append((b, rijen[-1], any(voor == "icloud-wacht" for voor, _ in taken)))
        # het bezoeknummer (PB1.., 1..) is wat in het verslag komt; de rij telt alle bezoeken door en is alleen het adres op het bord
        ag.log(str(nummer), "bevinding", f"{b['soort_bezoek']} {b['nr_label']} (rij {b['volgnr']}, {b['datum']}): {rijen[-1]['stand']}; "
               + ", ".join(f"{x['code']} {x['stand']}" for x in controles))
    for r in verdwenen:
        noden.append({"tekst": f"Dossier {nummer}: de bezoekmap van {r.get('datum')} ({os.path.basename(r['bezoekmap'])}) bestaat niet "
                               "meer en hoort bij geen bezoek van nu; Mehdi kijkt of het bezoek nog bestaat", "wie": "mehdi"})
    if droog:
        print(json.dumps(rijen, ensure_ascii=False, indent=1))
        if verdwenen:
            print("verdwenen:", json.dumps([{"id": r.get("id"), "datum": r.get("datum"), "bezoekmap": r["bezoekmap"]} for r in verdwenen], ensure_ascii=False))
        return rijen, noden, dubbels
    try:
        uit = bord.call("/api/werfbezoek", {"rijen": rijen})
        opgeslagen = bord.call(f"/api/werfbezoek?dossier={nummer}").get("rijen", [])
    except Exception:  # noqa: BLE001
        ag.log(str(nummer), "fout", "stand niet op het bord bevestigd; geen bronopdracht gepubliceerd")
        noden.append({"tekst": f"Dossier {nummer}: bordregistratie niet bevestigd; fotoaanvoer blijft open", "wie": "claude-code"})
        return rijen, noden, dubbels
    for b, rij, nodig in fotowerk:
        passend = [r for r in opgeslagen if r.get("datum") == b["datum"] and (r.get("bezoekmap") or "").casefold() == b["map"].casefold()
                   and not str(r.get("stand", "")).startswith("dubbel na verhuis")]
        try:
            if len(passend) != 1:
                raise ValueError("bordbezoek_dubbelzinnig")
            if b.get("registratie_blokkade"):
                raise werfregister.RegisterFout("werfapp-identiteit niet ondubbelzinnig bevestigd")
            registratie = werfregister.registreer(passend[0], str(nummer), b["volgnr"])
            rij["registratie"] = registratie
            bord.call("/api/werfbezoek", {"rijen": [{"dossier": str(nummer), "datum": b["datum"], "bezoekmap": b["map"],
                       "volgnr": b["volgnr"], "werfbezoek_id": passend[0]["id"], "_alleen": ["registratie"], "registratie": registratie}]})
            open_foto = [it for it in open_taken.get("icloud-wacht", [])
                         if it.get("id") not in gesloten_ids and
                         (_inhoud(it).get("bezoeksleutel") == bezoeksleutel(nummer, b)
                             or _inhoud(it).get("bezoek_id") == registratie["bezoek_id"]
                             or (str(_inhoud(it).get("dossier")) == str(nummer) and _inhoud(it).get("datum") == b["datum"]
                                 and _inhoud(it).get("bezoekmap") in (b["map"], taakdoel(b))))]
            for it in open_foto:
                rij["taken"].append({"voor": "icloud-wacht", "titel": it.get("titel", "Fotoaanvoer nog open"), "uniek": it.get("uniek")})
                if not (_inhoud(it).get("start") and _inhoud(it).get("einde")):
                    noden.append({"tekst": f"Dossier {nummer}, bezoek {b['nr_label']}: bestaande fototaak mist bezoekvenster en blijft open", "wie": "collega"})
            if nodig and not open_foto:
                taak = fototaak(nummer, adres, projectmap, b, bezoeken, bak, registratie)
                if not any(t.get("uniek") == taak["uniek"] for t in open_taken.get("icloud-wacht", [])):
                    alle_taken.append(taak)
                if not any(t.get("uniek") == taak["uniek"] for t in rij["taken"]):
                    rij["taken"].append({k: taak[k] for k in ("voor", "titel", "uniek")})
            bord.call("/api/werfbezoek", {"rijen": [{"dossier": str(nummer), "datum": b["datum"], "bezoekmap": b["map"],
                       "volgnr": b["volgnr"], "werfbezoek_id": passend[0]["id"], "_alleen": ["registratie", "taken", "controles", "stand"],
                       **{k: rij[k] for k in ("registratie", "taken", "controles", "stand")}}]})
        except (ValueError, werfregister.RegisterFout):
            noden.append({"tekst": f"Dossier {nummer}, bezoek {b['nr_label']}: geen ondubbelzinnig bevestigd H-A-bezoekvenster of vaste registratie; fototaak blijft open, tijden en identiteit bevestigen", "wie": "mehdi"})
    for r in verdwenen:
        try:
            bord.call("/api/werfbezoek", {"rijen": [{"dossier": str(nummer), "datum": r["datum"], "bezoekmap": r["bezoekmap"],
                       "volgnr": r.get("volgnr") or 0, "werfbezoek_id": r["id"], "_alleen": ["stand", "controles"], "stand": VERDWENEN,
                       "controles": [{"code": "W3", "naam": "projectmap en bezoekmap", "stand": "ontbreekt",
                                      "toelichting": "deze bezoekmap bestaat niet meer en hoort bij geen bezoek van nu"}]}]})
            ag.log(str(nummer), "besluit", f"rij {r['id']}: bezoekmap bestaat niet meer; stand '{VERDWENEN}' (niets gewist)")
        except Exception as ex:  # noqa: BLE001
            ag.log(str(nummer), "fout", f"rij {r.get('id')}: stand 'verdwenen' niet bevestigd: {ex}")
    if alle_taken:
        uit_taken = ag.klaarzet(alle_taken)
        ag.log(str(nummer), "besluit", f"{len(alle_taken)} taak/taken uitgezet bij collega-agents", uit_taken)
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
        raise RuntimeError("Dropbox niet beschikbaar; werfverslagronde gestopt")
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


def run():
    with ag.ronde("werfbezoeken verifiëren") as ronde:
        main()
        ronde.detail = "bezoekcontroles en bronopdrachten bijgewerkt"


if __name__ == "__main__":
    run()

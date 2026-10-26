#!/usr/bin/env python3
"""De Communicatiebundelaar (Privé · Communicatie): legt de kanalen naast elkaar.

Per Brusselse dag en per persoon: hoe vaak, hoe lang en langs welk kanaal Mehdi contact had, uit de gesprekkentabel
(`gesprek_log`) die De Zoomwacht, De Fathomwacht, De Plaudwacht en de mailwachten vullen. Tot 26-10-2026 draaide ik als
skelet en las niemand de uitvoer van De Zoomwacht (driehoeksoverleg Zoomwacht 2, X4/X5). Ontwerp en keuzes van Mehdi:
docs/codex/communicatie-bundelaar-ontwerp-v1.md.

Wat ik doe, elke ochtend na de kanaalagents:
  1. de rijen van de zeven dagen voor vandaag lezen, alleen lezend (bord.db_lees), zonder inhoudskolommen;
  2. per dag en persoon de contacten en minuten per kanaal tellen, met de telregel van het bord (dubbel_van) en de
     privéregel van De Regisseur (kolom prive of afdeling prive);
  3. per dag een klaarzet-item voor Mehdi (soort communicatie), dat De Levenscoach en De Dagbundelaar meelezen.

Grenzen (werkwijze op het bord, `## Wat ik nooit doe`): ik schrijf nooit in de gesprekkentabel, lees nooit thema,
waarom, link, archief of project, en een privérij is alleen een aantal, nooit een naam.

Draaien: python3 communicatie_bundelaar.py            (een ronde)
         python3 communicatie_bundelaar.py --droog    (geen ronde, geen klaarzet: toont wat ik zou klaarzetten)
         python3 communicatie_bundelaar.py --droog --zaad   (idem, met de werkwijze uit werkwijze/ in plaats van het bord)
"""
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import organisatie  # noqa: E402

NAAM = "communicatie-bundelaar"
ag = bord.Agent(NAAM)
BRUSSEL = ZoneInfo("Europe/Brussels")

VENSTER_DAGEN = 7    # de dagen die ik elke ronde opnieuw bundel; een item dat nog niet opgepakt is, volgt de bron
BEKEND_DAGEN = 90    # hoe ver terug iemand uit een gesprek telt als bekend persoon voor mail (keuze 1 van Mehdi)

# Kanaal uit het voorvoegsel van uniek (keuze 3 van Mehdi). zoom:chat: voor zoom:, het langste voorvoegsel wint.
KANALEN = (("zoom:chat:", "chat"), ("zoom:", "video"), ("fathom:", "video"), ("plaud:", "ter plaatse"), ("mail:", "mail"))
MET_DUUR = ("video", "ter plaatse")   # chat en mail hebben geen duur: weggelaten, nooit 0

# Alleen deze kolommen; thema, waarom, link, archief en project zijn inhoud en lees ik nooit.
SQL = ("SELECT uniek, datum, minuten, personen, prive, COALESCE(afdeling, '') AS afdeling, "
       "COALESCE(dubbel_van, '') AS dubbel_van FROM gesprek_log WHERE datum BETWEEN ? AND ?")

HAAKJES = re.compile(r"\s*\([^)]*\)?")
ONBEKEND = re.compile(r"^(speaker|spreker|deelnemer|externe?|onbekend|unknown)\b", re.I)


def kanaal(uniek):
    for voor, k in KANALEN:
        if (uniek or "").startswith(voor):
            return k
    return None


def is_prive(rij):
    """De regel van De Regisseur (RZ3-01): de kolom prive, of afdeling prive of privé."""
    return bool(rij.get("prive")) or str(rij.get("afdeling") or "").strip().casefold() in ("prive", "privé")


def namen(personen):
    """De namen uit de kolom personen. Eerst gaat alles tussen haakjes weg, want daar staan ook komma's in ("Speaker 1
    (onbekend, mogelijk X of Y)"); dan splitsen op komma, en van elke naam alleen het deel voor de eerste dubbelepunt
    (een Zoom-chat heet soms "Naam: FIRMA: Offerte", en dat label is geen naam)."""
    for deel in HAAKJES.sub("", personen or "").split(","):
        n = deel.split(":", 1)[0].strip()
        if n:
            yield n


def is_mehdi(naam, collega):
    if collega and str(collega.get("voornaam") or "").casefold() == "mehdi":
        return True
    return naam.split()[0].casefold() == "mehdi"


class Personen:
    """Een naam wordt een persoon: een collega krijgt zijn naam uit kern (dan zijn "Voornaam (Afdeling)" en "Voornaam"
    een persoon), een ander zijn naam zoals de bron hem gaf, samengevoegd zonder hoofdletterverschil."""

    def __init__(self, herken):
        self.herken = herken
        self._cache = {}

    def persoon(self, naam):
        """(soort, weergavenaam), soort is mehdi, onbekend, adres, collega of naam. Een adres dat geen collega is, voeg
        ik niet samen met een naam uit een gesprek: voor mail is het overige mail."""
        if naam not in self._cache:
            c = self.herken(naam)
            if is_mehdi(naam, c):
                uit = ("mehdi", "")
            elif c:
                uit = ("collega", c["naam"])
            elif ONBEKEND.match(naam):
                uit = ("onbekend", "")
            elif "@" in naam:
                uit = ("adres", naam)
            else:
                uit = ("naam", naam)
            self._cache[naam] = uit
        return self._cache[naam]


def bundel(rijen, eerste, laatste, herken):
    """Rijen uit gesprek_log naar {dag: inhoud}, plus wat er opviel. Alleen dagen in [eerste, laatste] met een rij die
    telt krijgen een inhoud; de oudere rijen dienen alleen om te weten wie bekend is voor mail."""
    p = Personen(herken)
    opgevallen = {"onbekend_kanaal": 0, "telt_niet": 0, "kanalen": set()}
    bekend = set()   # personen uit gesprekken die geen privé zijn, en collega's
    tellen = []
    for r in rijen:
        if r.get("dubbel_van"):
            opgevallen["telt_niet"] += 1   # telregel Z10: een dubbel of buiten:<reden> telt niet
            continue
        k = kanaal(r.get("uniek"))
        if k is None:
            opgevallen["onbekend_kanaal"] += 1
            continue
        prive = is_prive(r)
        if not prive and k != "mail":
            for n in namen(r.get("personen")):
                soort, wie = p.persoon(n)
                if soort in ("collega", "naam"):
                    bekend.add(wie.casefold())
        if eerste <= (r.get("datum") or "") <= laatste:
            tellen.append((r, k, prive))
    dagen = {}
    for r, k, prive in tellen:
        d = dagen.setdefault(r["datum"], {"datum": r["datum"], "personen": {}, "prive_per_kanaal": {}, "overige_mail": 0,
                                          "onbekende_deelnemers": 0, "contacten": 0, "kanalen": defaultdict(int)})
        d["contacten"] += 1
        d["kanalen"][k] += 1
        opgevallen["kanalen"].add(k)
        minuten = r.get("minuten") if k in MET_DUUR and isinstance(r.get("minuten"), int) and r["minuten"] > 0 else None
        if prive:
            _tel(d["prive_per_kanaal"], k, minuten)   # alleen een aantal: geen naam, ook niet van de andere deelnemers
            continue
        gezien = set()
        for n in namen(r.get("personen")):
            soort, wie = p.persoon(n)
            if soort == "mehdi":
                continue
            if soort == "onbekend":
                d["onbekende_deelnemers"] += 1
                continue
            if k == "mail" and (soort == "adres" or (soort == "naam" and wie.casefold() not in bekend)):
                d["overige_mail"] += 1   # keuze 1: mail alleen per persoon voor een collega of iemand uit een gesprek
                continue
            sleutel = wie.casefold()
            if sleutel in gezien:
                continue
            gezien.add(sleutel)
            pers = d["personen"].setdefault(sleutel, {"naam": wie, "kanalen": {}})
            _tel(pers["kanalen"], k, minuten)
    uit = {}
    for dag, d in dagen.items():
        personen = sorted(d["personen"].values(), key=lambda x: (-sum(c["aantal"] for c in x["kanalen"].values()),
                                                                 x["naam"].casefold()))
        uit[dag] = {"datum": dag, "contacten": d["contacten"], "kanalen": dict(sorted(d["kanalen"].items())),
                    "personen": personen, "prive_per_kanaal": d["prive_per_kanaal"], "overige_mail": d["overige_mail"],
                    "onbekende_deelnemers": d["onbekende_deelnemers"]}
    return uit, opgevallen


def _tel(per_kanaal, k, minuten):
    c = per_kanaal.setdefault(k, {"aantal": 0})
    c["aantal"] += 1
    if k in MET_DUUR:
        if minuten is None:
            c["zonder_duur"] = c.get("zonder_duur", 0) + 1
        else:
            c["minuten"] = c.get("minuten", 0) + minuten


def titel(inhoud):
    """Zonder namen: de titel komt in het dagverslag van De Dagbundelaar."""
    kanalen = ", ".join(inhoud["kanalen"])
    return (f"Communicatie {inhoud['datum']}: {inhoud['contacten']} contacten, {len(inhoud['personen'])} personen"
            + (f", privé {sum(c['aantal'] for c in inhoud['prive_per_kanaal'].values())}" if inhoud["prive_per_kanaal"] else "")
            + f" ({kanalen})")


def items(dagen):
    """Geen sleutel prive bovenaan de inhoud: De Dagbundelaar leest die als een privégesprek en toont dan alleen
    'privégesprek, duur onbekend' (dagbundelaar.py, prive)."""
    return [{"voor": "mehdi", "soort": "communicatie", "sleutel": dag, "uniek": f"communicatie:dag:{dag}",
             "titel": titel(inhoud), "inhoud": json.dumps(inhoud, ensure_ascii=False, separators=(",", ":"))}
            for dag, inhoud in sorted(dagen.items())]


def venster(vandaag=None):
    vandaag = vandaag or datetime.now(BRUSSEL).date()
    laatste = vandaag - timedelta(days=1)
    return (laatste - timedelta(days=VENSTER_DAGEN - 1)).isoformat(), laatste.isoformat(), \
        (laatste - timedelta(days=BEKEND_DAGEN - 1)).isoformat()


def werk(r, vandaag=None, lees=bord.db_lees, collegas=organisatie.collegas, herken=organisatie.herken, zet=None):
    nooit, mehdi_beslist = bord.grenzen(r.werkwijze)
    if not nooit or not mehdi_beslist:
        # N2: zonder grenzen geen werk. De vaste vorm staat in bord.grenzen.
        r.nood("Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist", wie="mehdi")
        r.detail = "geen werk gedaan, grenzen ontbreken in de werkwijze"
        return None
    eerste, laatste, van = venster(vandaag)
    try:
        rijen = lees(SQL, (van, laatste))
    except bord.BordOnbekend:
        # Onbekend is niet leeg (L29): geen item, want een leeg item zou zeggen dat er geen contact was.
        r.nood("Gesprekkentabel niet leesbaar", wie="claude-code")
        r.detail = f"gesprekkentabel niet gelezen, niets klaargezet ({eerste} tot {laatste})"
        return None
    if not collegas():
        r.nood("Collega's uit kern niet leesbaar, namen niet samengevoegd", wie="claude-code")
    dagen, opgevallen = bundel(rijen, eerste, laatste, herken)
    if opgevallen["onbekend_kanaal"]:
        r.nood("Rij met een onbekend kanaal in de gesprekkentabel", wie="claude-code")
    if len(opgevallen["kanalen"]) < 2:
        r.nood("Minder dan twee kanalen leverden rijen in de laatste zeven dagen", wie="claude-code")
    te_zetten = items(dagen)
    uit = (zet or ag.klaarzet)(te_zetten) if te_zetten else {}
    contacten = sum(d["contacten"] for d in dagen.values())
    prive = sum(c["aantal"] for d in dagen.values() for c in d["prive_per_kanaal"].values())
    r.detail = (f"{eerste} tot {laatste}: {len(dagen)} dagen, {contacten} contacten waarvan {prive} privé, "
                f"kanalen {', '.join(sorted(opgevallen['kanalen'])) or 'geen'}; {opgevallen['telt_niet']} rijen telden "
                f"niet (dubbel); klaargezet {uit.get('nieuw', 0)} nieuw, {uit.get('bijgewerkt', 0)} bijgewerkt")
    return dagen


def droog(zaad=False):
    """Geen ronde: geen hartslag, kennis of klaarzet. Toont de items zoals ze klaargezet zouden worden. Met zaad de
    werkwijze uit werkwijze/, om een nieuwe versie te proeven voor ze op het bord staat."""
    class Droog:
        werkwijze, detail = "", ""

        def nood(self, tekst, wie="mehdi"):
            print(f"(droog) nood voor {wie}: {tekst}")
    d = Droog()
    try:
        d.werkwijze = open(os.path.join(HIER, "werkwijze", f"{NAAM}.md"), encoding="utf-8").read() if zaad \
            else ag.werkwijze_lezen()
    except (OSError, bord.RondeGestopt) as e:
        print(f"(droog) werkwijze niet gelezen: {e}")
        return
    gezet = []
    werk(d, zet=lambda its: gezet.extend(its) or {})
    for it in gezet:
        print(it["titel"])
        print(json.dumps(json.loads(it["inhoud"]), ensure_ascii=False, indent=1))
    print(f"(droog) {d.detail}")


if __name__ == "__main__":
    if "--droog" in sys.argv:
        droog(zaad="--zaad" in sys.argv)
    else:
        with ag.ronde("communicatie bundelen") as r:
            werk(r)

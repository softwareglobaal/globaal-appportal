#!/usr/bin/env python3
"""De Communicatiebundelaar (Privé · Communicatie): legt de kanalen naast elkaar.

Per Brusselse dag en per persoon: hoe vaak, hoe lang en langs welk kanaal Mehdi contact had, uit de gesprekkentabel
(`gesprek_log`) die De Zoomwacht, De Fathomwacht, De Plaudwacht en de mailwachten vullen, en sinds T-0120 CB-1 ook De
WhatsApp-wacht, De Belwacht, De Sms-wacht en De Xelionwacht (privé, alleen aantallen). Tot 26-10-2026 draaide ik als
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
         python3 communicatie_bundelaar.py --van 2026-10-01 (eenmalig inhalen vanaf die dag, CB-4; ook met --droog)
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
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
INHAAL_DAGEN = 60    # CB-4: hoe ver een eenmalige inhaalronde (--van) hoogstens terug gaat

# Kanaal uit het voorvoegsel van uniek (keuze 3 van Mehdi). zoom:chat: voor zoom:, het langste voorvoegsel wint. CB-1
# (T-0120): de kanalen van de Mac en Xelion, zoals De WhatsApp-wacht, De Belwacht, De Sms-wacht en De Xelionwacht ze
# schrijven (mac_gesprekken.py). Hun rijen zijn privé: alleen een aantal en een duur per kanaal (tot de keuze CB-2).
KANALEN = (("zoom:chat:", "chat"), ("zoom:", "video"), ("fathom:", "video"), ("plaud:", "ter plaatse"), ("mail:", "mail"),
           ("whatsapp-oproep:", "whatsapp-oproep"), ("whatsapp:", "whatsapp"), ("telefoon:", "telefoon"), ("sms:", "sms"),
           ("xelion:", "xelion"))
MAC_CHATS = ("whatsapp:", "sms:")   # een groep van de Mac heet 'groep: naam' in personen
MAC = ("whatsapp-oproep:", "whatsapp:", "telefoon:", "sms:", "xelion:")
# chat, sms en mail hebben geen duur: weggelaten, nooit 0
MET_DUUR = ("video", "ter plaatse", "whatsapp-oproep", "telefoon", "xelion")

# Alleen deze kolommen; thema, waarom, link, archief en project zijn inhoud en lees ik nooit.
# De hele tabel, zonder datumgrens: privé geldt over een gesprek en over iemand heen, ook als een dubbel van de nacht
# ervoor of een privégesprek van maanden geleden buiten een venster valt (Codex CB17, CB18). Gemeten 26-10-2026: 1508 rijen.
SQL = ("SELECT uniek, datum, minuten, personen, prive, COALESCE(afdeling, '') AS afdeling, COALESCE(sessie, '') AS sessie, "
       "COALESCE(dubbel_van, '') AS dubbel_van FROM gesprek_log")

SQL_EERDER = "SELECT DISTINCT sleutel FROM klaarzet WHERE soort = 'communicatie' AND van = ?"

HAAKJES = re.compile(r"\s*\([^)]*\)?")
MEHDI = ("mehdi", "mehdi chegini")   # zoals de bronnen hem schrijven, naast zijn rij in kern
ONBEKEND = re.compile(r"^(speaker|spreker|deelnemer|externe?|onbekend|unknown)\b", re.I)


def is_groep(personen):
    """CB-1: een groep van de Mac ('groep: naam', of 'groep' bij een groepsoproep zonder naam) is nooit een persoon."""
    p = str(personen or "").strip()
    return p == "groep" or p.startswith("groep:")


def kanaal(uniek, personen=""):
    """Een Zoom-chat zonder adres in de sleutel (zoom:chat:<sleutel>:<dag>) is een kanaal met meer mensen: de naam in
    personen is dan de kanaalnaam, geen mens (Codex CB06). Die heet groepschat en is alleen een aantal. Zo ook een groep
    in WhatsApp of sms (CB-1)."""
    uniek = uniek or ""
    if (uniek.startswith("zoom:chat:") and "@" not in uniek) or (uniek.startswith(MAC_CHATS) and is_groep(personen)):
        return "groepschat"
    for voor, k in KANALEN:
        if uniek.startswith(voor):
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


class Personen:
    """Een naam wordt een persoon. Een collega uit kern krijgt zijn kernnaam, maar alleen op een exacte naam of een exact
    adres, of op een losse voornaam die maar een collega draagt: zo zijn "Voornaam (Afdeling)" en "Voornaam" een
    persoon, en wordt een vreemde met dezelfde voornaam en een achternaam geen collega (Codex CB07). Een ander houdt
    zijn naam zoals de bron hem gaf, samengevoegd zonder hoofdletterverschil."""

    def __init__(self, collegas):
        self.exact, voornamen = {}, defaultdict(list)
        for c in collegas:
            for sleutel in (c.get("naam"), c.get("email")):
                if sleutel:
                    self.exact[sleutel.strip().casefold()] = c
            if c.get("voornaam"):
                voornamen[c["voornaam"].strip().casefold()].append(c)
        self.voornaam = {v: lijst[0] for v, lijst in voornamen.items() if len(lijst) == 1}
        self._cache = {}

    def collega(self, naam):
        t = naam.strip().casefold()
        return self.exact.get(t) or (self.voornaam.get(t) if " " not in t else None)

    def persoon(self, naam):
        """(soort, weergavenaam), soort is mehdi, onbekend, adres, collega of naam. Een adres dat geen collega is, voeg
        ik niet samen met een naam uit een gesprek: voor mail is het overige mail."""
        if naam not in self._cache:
            c = self.collega(naam)
            if (c and str(c.get("voornaam") or "").strip().casefold() == "mehdi") or naam.casefold() in MEHDI:
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


def prive_gesprekken(rijen):
    """Privé is de OF over alle rijen van een gesprek, dubbels inbegrepen (De Regisseur, _prive_sessies, M1 en BAS-02):
    een Fathom-rij die zelf niet privé is, met een Zoom-dubbel die het wel is, is privé. Een gesprek is de hele groep
    rijen die via dubbel_van of dezelfde sessie aan elkaar hangen, ook over een keten van dubbels (Codex, controle 1:
    met alleen de directe voorganger lekte een naam). Een rij buiten:<reden> hoort niet bij Mehdi's gesprek en hangt
    nergens aan. Geeft een functie rij -> privé."""
    ouder = {}

    def wortel(x):
        while ouder.setdefault(x, x) != x:
            ouder[x] = ouder[ouder[x]]
            x = ouder[x]
        return x

    def koppel(a, b):
        ouder[wortel(a)] = wortel(b)

    for r in rijen:
        dv = str(r.get("dubbel_van") or "")
        if dv.startswith("buiten:"):
            continue
        u = "rij:" + str(r.get("uniek") or "")
        wortel(u)
        if dv:
            koppel(u, "rij:" + dv)
        if r.get("sessie"):
            koppel(u, "sessie:" + r["sessie"])
    prive = {wortel("rij:" + str(r.get("uniek") or "")) for r in rijen
             if is_prive(r) and not str(r.get("dubbel_van") or "").startswith("buiten:")}
    return lambda r: is_prive(r) or wortel("rij:" + str(r.get("uniek") or "")) in prive


def bundel(rijen, dagen_lijst, collegas, bekend_vanaf=""):
    """Rijen uit gesprek_log naar {dag: inhoud}, plus wat er opviel. Elke dag uit dagen_lijst krijgt een inhoud, ook een
    zonder contact: zo volgt een item dat eerder contacten toonde de bron, als een koppeling of privécorrectie ze
    weghaalt (Codex CB04, CB11). De andere rijen dienen om te weten wie privé is (de hele geschiedenis) en wie bekend is
    voor mail (gesprekken vanaf bekend_vanaf, Codex CB19)."""
    p = Personen(collegas)
    opgevallen = {"onbekend_kanaal": 0, "telt_niet": 0, "kanalen": set()}
    bekend, ooit_prive = set(), set()   # personen uit gesprekken die geen privé zijn; wie ooit in een privégesprek zat
    prive_groep = prive_gesprekken(rijen)
    dagen = {d: {"datum": d, "personen": {}, "prive_per_kanaal": {}, "overige_mail": 0, "onbekende_deelnemers": 0,
                 "contacten": 0, "kanalen": defaultdict(int)} for d in dagen_lijst}
    tellen = []
    for r in rijen:
        dubbel, in_dagen = str(r.get("dubbel_van") or ""), (r.get("datum") or "") in dagen
        if dubbel.startswith("buiten:"):
            opgevallen["telt_niet"] += in_dagen   # hoort niet bij Mehdi's gesprek: telt niet en maakt niemand bekend of privé
            continue
        k = kanaal(r.get("uniek"), r.get("personen"))
        # CB-1: een rij van de Mac of Xelion is privé, ook zonder vlag, tot de keuze CB-2 (Codex-toets 1). Laat CB-2
        # ooit werkcontacten bij naam toe, dan blijft een groep (is_groep, ook een groepsoproep) erbuiten.
        prive = prive_groep(r) or str(r.get("uniek") or "").startswith(MAC)
        if k != "mail":
            # Ook de namen van een dubbel: een privé Zoom-dubbel naast een Fathom-rij noemt dezelfde mensen (Codex CB14).
            # Een privérij van elk kanaal, ook een onbekend, maakt iemand privé (controle 5); bekend maakt alleen een
            # gesprek met mensen (video, chat, ter plaatse), geen kanaalnaam.
            for n in namen(r.get("personen")):
                soort, wie = p.persoon(n)
                if soort == "naam" and prive:
                    ooit_prive.add(wie.casefold())
                elif soort == "naam" and k in ("video", "chat", "ter plaatse") and (r.get("datum") or "") >= bekend_vanaf:
                    bekend.add(wie.casefold())
        if dubbel:
            opgevallen["telt_niet"] += in_dagen   # telregel Z10: een dubbel telt niet, de rij waarnaar hij wijst wel
            continue
        if k is None:
            opgevallen["onbekend_kanaal"] += in_dagen
            k = "overig"   # telt mee als aantal, zonder namen: wie weet wat dit kanaal in personen zet (Codex CB16)
        if in_dagen:
            tellen.append((r, k, prive))
    # Wie ooit in een privégesprek zat, is voor mail geen bekende, ook niet als hij ook in een gewoon gesprek zat: anders
    # staat zijn naam op de dag van een privégesprek (Codex CB10). Een collega uit kern blijft wel bekend: zijn mail is werk.
    bekend -= ooit_prive
    for r, k, prive in tellen:
        d = dagen[r["datum"]]
        d["contacten"] += 1
        d["kanalen"][k] += 1
        opgevallen["kanalen"].add(k)
        minuten = r.get("minuten") if k in MET_DUUR and isinstance(r.get("minuten"), int) and r["minuten"] > 0 else None
        if prive:
            _tel(d["prive_per_kanaal"], k, minuten)   # alleen een aantal: geen naam, ook niet van de andere deelnemers
            continue
        if k in ("groepschat", "overig"):
            continue   # de naam is die van een kanaal of onbekend van soort: alleen het aantal in kanalen
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
    """Zonder namen: een titel staat op plekken waar privé niet mag (lijst van de bak, werkverslag)."""
    if not inhoud["contacten"]:
        return f"Communicatie {inhoud['datum']}: geen contact in de gesprekkentabel"
    kanalen = ", ".join(inhoud["kanalen"])
    return (f"Communicatie {inhoud['datum']}: {inhoud['contacten']} contacten, {len(inhoud['personen'])} personen"
            + (f", privé {sum(c['aantal'] for c in inhoud['prive_per_kanaal'].values())}" if inhoud["prive_per_kanaal"] else "")
            + f" ({kanalen})")


def items(dagen):
    """Geen sleutel prive bovenaan de inhoud: wie de inhoud leest, zou die als een privégesprek kunnen nemen
    (zoals dagbundelaar.py, prive, Codex CB02)."""
    # vervang, geen revisie: het bord zet ook een opgepakt item terug op de bron, zonder kopie van de oude inhoud; een
    # revisie zou een naam die intussen privé werd in klaarzet_revisie bewaren (Codex CB04, CB12).
    return [{"voor": "mehdi", "soort": "communicatie", "sleutel": dag, "uniek": f"communicatie:dag:{dag}", "vervang": True,
             "titel": titel(inhoud), "inhoud": json.dumps(inhoud, ensure_ascii=False, separators=(",", ":"))}
            for dag, inhoud in sorted(dagen.items())]


def reeks(eerste, laatste):
    d, uit = date.fromisoformat(eerste), []
    while d.isoformat() <= laatste:
        uit.append(d.isoformat())
        d += timedelta(days=1)
    return uit


def venster(vandaag=None):
    vandaag = vandaag or datetime.now(BRUSSEL).date()
    laatste = vandaag - timedelta(days=1)
    return (laatste - timedelta(days=VENSTER_DAGEN - 1)).isoformat(), laatste.isoformat(), \
        (laatste - timedelta(days=BEKEND_DAGEN - 1)).isoformat()


def terug_lezen(gezet, lees=None):
    """Elk item terug van het bord, op uniek, en vergelijken met wat ik zette (na het masker van het bord). Geeft de
    unieke sleutels die ontbreken of anders zijn (Codex CB09)."""
    lees = lees or (lambda uniek: bord.call("/api/klaarzet?" + urllib.parse.urlencode({"uniek": uniek, "status": "alle"}))
                    .get("items") or [])
    fout = []
    for it in ag.maskeer(gezet):
        terug = lees(it["uniek"])
        # Status klaar: met vervang zet het bord een gewijzigd item altijd terug op klaar; staat het op opgepakt, dan
        # pakte iemand het op en hoort dat gemeld (Codex CB09, controle 5).
        if not any(all(t.get(k) == it[k] for k in ("uniek", "voor", "soort", "sleutel", "titel", "inhoud"))
                   and t.get("status") == "klaar" for t in terug):
            fout.append(it["uniek"])
    return fout


def werk(r, vandaag=None, lees=bord.db_lees, collegas=organisatie.collegas, zet=None, terug=None, van=None):
    """Een ronde. CB-3 (T-0120): elke ronde laat een regel in het werkverslag, alleen aantallen, ook een ronde die niets
    klaarzette (de wachtenpagina leest alleen het werkverslag en zei anders 'Geen ronde'); een ronde die breekt, een
    regel met stap fout, zonder de tekst van de fout (die kan een naam dragen). van: CB-4, eenmalig ook elke dag vanaf
    die dag bundelen."""
    try:
        dagen = _werk(r, vandaag, lees, collegas, zet, terug, inhaal=van)
    except Exception as e:
        ag.log("ronde", "fout", f"ronde gebroken ({type(e).__name__}); niets zeker klaargezet")
        raise
    ag.log("ronde", "bevinding", r.detail)
    return dagen


def _werk(r, vandaag, lees, collegas, zet, terug, inhaal=None):
    nooit, mehdi_beslist = bord.grenzen(r.werkwijze)
    if not nooit or not mehdi_beslist:
        # N2: zonder grenzen geen werk. De vaste vorm staat in bord.grenzen.
        r.nood("Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist", wie="mehdi")
        r.detail = "geen werk gedaan, grenzen ontbreken in de werkwijze"
        return None
    eerste, laatste, van = venster(vandaag)
    try:
        # Ook elke oudere dag waarvoor ik al een item zette, zodat een latere privécorrectie dat item bijwerkt (CB11).
        eerder = {x["sleutel"] for x in lees(SQL_EERDER, (NAAM,)) if x.get("sleutel") and x["sleutel"] < eerste}
        if inhaal:
            # CB-4: eenmalig inhalen; daarna heeft elke dag een item en herziet de gewone ronde hem zelf (CB11)
            eerder |= {d for d in reeks(inhaal, laatste) if d < eerste}
        dagen_lijst = sorted(eerder) + reeks(eerste, laatste)
        rijen = lees(SQL)
    except bord.BordOnbekend:
        # Onbekend is niet leeg (L29): geen item, want een leeg item zou zeggen dat er geen contact was.
        r.nood("Gesprekkentabel niet leesbaar", wie="claude-code")
        r.detail = f"gesprekkentabel niet gelezen, niets klaargezet ({eerste} tot {laatste})"
        return None
    lijst = collegas()
    if not lijst:
        # Zonder kern weet ik niet wie een collega is: namen zouden uit elkaar vallen en mail van een collega zou
        # overige mail worden. Dan geen uitkomst per persoon (Codex CB08).
        r.nood("Collega's uit kern niet leesbaar", wie="claude-code")
        r.detail = f"kern niet gelezen, niets klaargezet ({eerste} tot {laatste})"
        return None
    dagen, opgevallen = bundel(rijen, dagen_lijst, lijst, bekend_vanaf=van)
    if opgevallen["onbekend_kanaal"]:
        r.nood("Rij met een onbekend kanaal in de gesprekkentabel", wie="claude-code")
    te_zetten = items(dagen)
    uit = (zet or ag.klaarzet)(te_zetten)
    if (terug or terug_lezen)(te_zetten):
        r.nood("Een dagitem staat niet zo op het bord of werd opgepakt", wie="claude-code")
    r.detail = werkverslag(dagen, eerste, laatste, opgevallen, uit)
    return dagen


def werkverslag(dagen, eerste, laatste, opgevallen, uit):
    """Alleen aantallen. Het venster en de oudere dagen die ik herzag, apart (Codex, controle 5)."""
    venster_dagen = [d for dag, d in dagen.items() if eerste <= dag <= laatste]
    contacten = sum(d["contacten"] for d in venster_dagen)
    prive = sum(c["aantal"] for d in venster_dagen for c in d["prive_per_kanaal"].values())
    ouder = len(dagen) - len(venster_dagen)
    return (f"{eerste} tot {laatste}: {sum(1 for d in venster_dagen if d['contacten'])} dagen met contact, {contacten} "
            f"contacten waarvan {prive} privé, kanalen {', '.join(sorted(opgevallen['kanalen'])) or 'geen'}; "
            f"{opgevallen['telt_niet']} rijen telden niet (dubbel); {ouder} oudere dagen herzien; klaargezet "
            f"{uit.get('nieuw', 0)} nieuw, {uit.get('bijgewerkt', 0)} bijgewerkt")


def droog(zaad=False, van=None):
    """Geen ronde: geen hartslag, kennis of klaarzet. Toont de items zoals ze klaargezet zouden worden. Met zaad de
    werkwijze uit werkwijze/, om een nieuwe versie te proeven voor ze op het bord staat. Met van ook de dagen van een
    inhaalronde vanaf die dag (CB-4)."""
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
    werk(d, zet=lambda its: gezet.extend(its) or {}, terug=lambda its: [], van=van)
    for it in gezet:
        print(it["titel"])
        print(json.dumps(json.loads(it["inhoud"]), ensure_ascii=False, indent=1))
    print(f"(droog) {d.detail}")


def inhaal_van(tekst, vandaag=None):
    """CB-4: het argparse-type van --van JJJJ-MM-DD: een dag voor vandaag (Brussel), hoogstens INHAAL_DAGEN terug."""
    try:
        dag = date.fromisoformat(str(tekst))
    except ValueError:
        raise argparse.ArgumentTypeError("een dag als JJJJ-MM-DD") from None
    vandaag = vandaag or datetime.now(BRUSSEL).date()
    if not vandaag - timedelta(days=INHAAL_DAGEN) <= dag < vandaag:
        raise argparse.ArgumentTypeError(f"hoogstens {INHAAL_DAGEN} dagen terug en voor vandaag")
    return dag.isoformat()


def main(argv=None):
    p = argparse.ArgumentParser(description="De Communicatiebundelaar: de kanalen per dag naast elkaar.")
    p.add_argument("--droog", action="store_true", help="geen ronde, geen klaarzet: toont wat ik zou klaarzetten")
    p.add_argument("--zaad", action="store_true", help="met --droog: de werkwijze uit werkwijze/ in plaats van het bord")
    p.add_argument("--van", type=inhaal_van, metavar="JJJJ-MM-DD",
                   help="eenmalig ook elke dag vanaf die dag bundelen (hoogstens 60 dagen terug)")
    a = p.parse_args(argv)
    if a.droog:
        droog(zaad=a.zaad, van=a.van)
        return
    with ag.ronde("communicatie bundelen") as r:
        werk(r, van=a.van)


if __name__ == "__main__":
    main()

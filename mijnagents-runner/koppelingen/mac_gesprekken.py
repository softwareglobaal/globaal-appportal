"""Gedeelde leescode van De WhatsApp-wacht en De Belwacht op de Mac van Mehdi (ontwerp dagvaststelling v2.0, fase 2).

Mehdi, 26-10-2026: WhatsApp en telefoon met namen in de gesprekkentabel (alleen beheer), nooit de tekst van een
bericht; de WhatsApp-wacht mag de databank op de Mac automatisch lezen: wie, wanneer, hoeveel en hoe lang.

Waarom een helper: onder launchd weigert macOS deze databanken aan Python (toegangsproef 26-10-2026). Alleen de vaste
helper MacGesprekkenKopie (mac/kopie/macgesprekken_kopie.c) heeft Full Disk Access. Hij leest de bronnen met vaste
vragen en schrijft alleen de toegelaten kolommen weg (Codex P1): nooit ZTEXT, media of een andere tekst. Deze module
start hem via launchctl, zodat hij zelf het verantwoordelijke proces is, en leest daarna zijn uitvoer.

Twee delen:
  - pure functies: rijen voor de gesprekkentabel, namen, dekking, samenvatting. Geen netwerk, geen bord.
  - de Mac-kant die beide runners delen: slot, token, stand, ssh-tunnel naar het bord, de kopie vragen, schrijven en
    teruglezen via koppelingen/bordstand.py op de VM.

Het contract met De Dagbundelaar (dagbundelaar.kanaal_van_dag, dagvaststelling.soort): whatsapp:<sha1 jid>:<dag> per
gesprek per dag, whatsapp-oproep:<oproep-ID>, telefoon:<ZUNIQUE_ID>, en dekking:<kanaal>:<dag> met bron dekking. Alles
privé. Een oproep zonder duur staat er met dubbel_van buiten:gemist en telt dus niet als gesprek (Z10).
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import secrets
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from bordstand import vingerafdruk

BRUSSEL = ZoneInfo("Europe/Brussels")
APPLE = datetime(2001, 1, 1, tzinfo=timezone.utc)      # Core Data telt seconden sinds 1-1-2001 (UTC)
VENSTER = 14                                            # zoals de nachtronde van De Dagbundelaar
INHAAL = 60                                             # na een lange slaap leest een ronde tot zoveel dagen terug (P7)
KOPIE = Path.home() / "Library/Caches/mijnagents/mac-gesprekken"
STAAT = Path.home() / "Library/Application Support/mijnagents"
HELPER = {"whatsapp": "be.globaal.mijnagents.kopie-whatsapp", "telefoon": "be.globaal.mijnagents.kopie-telefoon",
          "sms": "be.globaal.mijnagents.kopie-sms"}
KOPIE_WACHT = 120
TOKEN_PAD = Path.home() / ".config/mijnagents/token"
VM = "globaal"
BORDSTAND = "~/agents/.venv/bin/python ~/appportal/mijnagents-runner/koppelingen/bordstand.py"
BORD_PUBLIEK = "https://mijnagents.globaal.be"
PER_KEER = 200                                          # rijen per oproep van /api/gesprekken
ZELFDE_OPROEP = timedelta(hours=6)                      # verder uit elkaar is een gelijke oproep-ID een andere oproep (P6)

# Berichtsoorten van WhatsApp die geen bericht van een mens zijn (bronproef 26-10-2026): 6 groepsmelding,
# 10 systeemmelding, 59 de melding van een oproep in het gesprek (ZSTANZAID is de oproep-ID).
GEEN_BERICHT = frozenset({6, 10, 59})
PERSOON, GROEP = 0, 1                                   # ZSESSIONTYPE; uitzendlijsten, status en kanalen tellen niet
GEMIST = "buiten:gemist"
DEKKING = "buiten:dekking"
VERVALLEN = "buiten:vervallen"
WA_STIL = timedelta(hours=48)
TEL_STIL = timedelta(days=7)
SMS_STIL = timedelta(days=7)
# Messages (chat.db): stijl 43 is een groepsgesprek, 45 een gesprek met een persoon (bronproef macOS 14 en 15).
SMS_GROEP = 43
# Alleen gewone oproepen en FaceTime (de hele geschiedenis op 26-10-2026: 630 en 11, niets anders): WhatsApp meldt De
# WhatsApp-wacht, en een andere app (Zoom, Teams) heeft zijn eigen wacht of hoort niet bij de telefoon.
TEL_DIENSTEN = {"com.apple.Telephony": "telefoon", "com.apple.FaceTime": "FaceTime"}

# De enige vragen aan de uitvoer van de helper (die zelf al alleen deze kolommen bevat).
SQL_GESPREKKEN = "SELECT Z_PK, ZCONTACTJID, ZPARTNERNAME, ZSESSIONTYPE FROM ZWACHATSESSION ORDER BY Z_PK"
SQL_BERICHTEN = ("SELECT ZCHATSESSION, ZMESSAGEDATE, ZISFROMME, ZMESSAGETYPE FROM ZWAMESSAGE "
                 "WHERE ZMESSAGEDATE >= ? AND ZMESSAGEDATE < ?")
SQL_OPROEPMELDINGEN = "SELECT ZSTANZAID, ZCHATSESSION FROM ZWAMESSAGE WHERE ZMESSAGETYPE = 59"
SQL_WA_OPROEPEN = ("SELECT e.Z_PK, e.ZCALLIDSTRING, e.ZDATE, e.ZDURATION, a.ZINCOMING, a.ZMISSED, a.ZVIDEO, "
                   "e.ZGROUPCALLCREATORUSERJIDSTRING, e.ZGROUPJIDSTRING FROM ZWACDCALLEVENT e "
                   "LEFT JOIN ZWAAGGREGATECALLEVENT a ON a.Z_PK = e.Z1CALLEVENTS ORDER BY e.ZDATE, e.Z_PK")
SQL_WA_DEELNEMERS = "SELECT Z1PARTICIPANTS, ZJIDSTRING FROM ZWACDCALLEVENTPARTICIPANT ORDER BY Z_PK"
SQL_CONTACTEN = "SELECT ZFULLNAME, ZWHATSAPPID, ZLID, ZPHONENUMBER FROM ZWAADDRESSBOOKCONTACT ORDER BY Z_PK"
SQL_TELEFOON = ("SELECT ZUNIQUE_ID, ZDATE, ZDURATION, ZORIGINATED, ZANSWERED, ZADDRESS, ZSERVICE_PROVIDER "
                "FROM ZCALLRECORD ORDER BY ZDATE, ZUNIQUE_ID")
# Sms en iMessage (31-10-2026): per bericht alleen gesprek, tijdstip (seconden sinds 2001), richting en dienst.
SQL_SMS_BERICHTEN = "SELECT gesprek, datum, van_mij, dienst FROM BERICHT WHERE datum >= ? AND datum < ?"
SQL_SMS_GESPREKKEN = "SELECT pk, ident, soort, naam FROM GESPREK ORDER BY pk"
SQL_SMS_DEELNEMERS = "SELECT gesprek, adres FROM DEELNEMER ORDER BY gesprek, adres"
SQL_NIEUWSTE = "SELECT waarde FROM META WHERE sleutel = 'nieuwste'"
SQL_AANVRAAG = "SELECT waarde FROM META WHERE sleutel = 'aanvraag'"
SQL_ANDERE_APPS = "SELECT COUNT(*) FROM ANDERE_APPS WHERE ZDATE >= ? AND ZDATE < ?"
SQL = (SQL_GESPREKKEN, SQL_BERICHTEN, SQL_OPROEPMELDINGEN, SQL_WA_OPROEPEN, SQL_WA_DEELNEMERS, SQL_CONTACTEN,
       SQL_TELEFOON, SQL_NIEUWSTE, SQL_AANVRAAG, SQL_ANDERE_APPS, SQL_SMS_BERICHTEN, SQL_SMS_GESPREKKEN, SQL_SMS_DEELNEMERS)
MIN_VERVALLEN = 5                                       # zoveel verdwenen rijen tegelijk is verdacht (Codex Q2)
NIET_BEVESTIGD = "Bord heeft de ronde niet bevestigd: hartslag of kennis ontbreekt"
BEZET = 75                                              # exit van een wacht die niet liep omdat er al een ronde liep


class MacFout(RuntimeError):
    """Een melding zonder naam, nummer of inhoud. nood: de vaste noodtekst (N10), wie: wie het oplost."""

    def __init__(self, tekst, nood=None, wie="claude-code"):
        super().__init__(tekst)
        self.nood = nood or tekst
        self.wie = wie


class Bezet(RuntimeError):
    """Er loopt al een ronde van deze agent op de Mac."""


# ------------------------------------------------------------------------------------------------- tijden ---
def tijd(apple):
    return APPLE + timedelta(seconds=float(apple))


def apple(t):
    return (t - APPLE).total_seconds()


def dag_van(t):
    return t.astimezone(BRUSSEL).date().isoformat()


def uur_van(t):
    return t.astimezone(BRUSSEL).strftime("%H:%M")


def start_van(t):
    """Het begin zoals de gesprekkentabel het kent (HH:MM in Brussel). In het uur dat bij de wintertijd twee keer
    voorkomt, met de UTC-afstand erbij ('02:30+01:00'), zodat dagvaststelling.gesprek_venster het juiste uur neemt (P5)."""
    lokaal = t.astimezone(BRUSSEL)
    if lokaal.replace(fold=1 - lokaal.fold).utcoffset() == lokaal.utcoffset():
        return lokaal.strftime("%H:%M")
    afstand = lokaal.strftime("%z")
    return f"{lokaal:%H:%M}{afstand[:3]}:{afstand[3:]}"


def daggrens(dag):
    """Middernacht in Brussel aan het begin van die dag (ook op de dagen van de zomertijdwissel)."""
    return datetime.fromisoformat(dag).replace(tzinfo=BRUSSEL)


def volgende(dag):
    return (date.fromisoformat(dag) + timedelta(days=1)).isoformat()


def dagen(nu, gedekt_tot=None, n=VENSTER):
    """De dagen van een ronde, oudste eerst, tot en met vandaag (Brussel): de laatste n, en na een lange slaap ook de
    dagen sinds de laatste gedekte dag, hoogstens INHAAL (P7)."""
    vandaag = nu.astimezone(BRUSSEL).date()
    eerste = vandaag - timedelta(days=n - 1)
    if gedekt_tot:
        try:
            eerste = min(eerste, max(date.fromisoformat(gedekt_tot) + timedelta(days=1),
                                     vandaag - timedelta(days=INHAAL - 1)))
        except ValueError:
            pass
    return [(eerste + timedelta(days=i)).isoformat() for i in range((vandaag - eerste).days + 1)]


def inhaal_vanaf(tekst, nu=None):
    """TEL-1: het argparse-type van --inhaal-vanaf JJJJ-MM-DD: een dag van vandaag tot hoogstens INHAAL dagen terug (zo
    ver leest een ronde, en de helper kopieert er 62)."""
    try:
        dag = date.fromisoformat(str(tekst))
    except ValueError:
        raise argparse.ArgumentTypeError("een dag als JJJJ-MM-DD") from None
    vandaag = (nu or datetime.now(timezone.utc)).astimezone(BRUSSEL).date()
    if not vandaag - timedelta(days=INHAAL - 1) <= dag <= vandaag:
        raise argparse.ArgumentTypeError(f"hoogstens {INHAAL} dagen terug en niet na vandaag")
    return dag.isoformat()


def inhaal_grens(gedekt_tot, vanaf=None):
    """TEL-1: een eenmalige inhaalronde vanaf een dag. De dag ervoor geldt dan als laatste gedekte dag, zodat dagen() vanaf
    daar leest, zoals na een lange slaap (P7). Nooit later dan de stand: een inhaalronde leest altijd minstens zoveel. De
    stand op de Mac zakt er niet door, want de wacht schrijft alleen een latere gedekte dag weg."""
    if not vanaf:
        return gedekt_tot
    grens = (date.fromisoformat(vanaf) - timedelta(days=1)).isoformat()
    return min(grens, str(gedekt_tot)) if gedekt_tot else grens


def minuten(seconden):
    """Een oproep met duur telt minstens een minuut; afgerond op de minuut."""
    s = float(seconden or 0)
    return max(1, int(s / 60 + 0.5)) if s > 0 else 0


# -------------------------------------------------------------------------------------------------- namen ---
def schoon(naam):
    """Een naam als gewone tekst: zonder stuurtekens, zonder komma (de kolom personen is een lijst), hoogstens 120."""
    tekst = "".join(" " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") else c for c in str(naam or ""))
    return re.sub(r"\s+", " ", tekst.replace(",", " ")).strip()[:120]


def nummer_sleutel(nummer):
    """Een telefoonnummer als sleutel: de laatste negen cijfers van het internationale nummer (+32 475 ..., 0475 ...
    en 475 ... zijn hetzelfde nummer). Zo kiest ook de helper de contacten (NORM in macgesprekken_kopie.c)."""
    tekst = str(nummer or "").strip()
    cijfers = re.sub(r"\D", "", tekst)
    if cijfers.startswith("00"):
        cijfers = cijfers[2:]
    elif tekst.startswith("0"):
        cijfers = "32" + cijfers[1:]
    return cijfers[-9:] if len(cijfers) >= 9 else cijfers


def nummer_van_jid(jid):
    """Het nummer in een klassiek WhatsApp-adres (32475...@s.whatsapp.net); een LID-adres draagt geen nummer."""
    m = re.fullmatch(r"(\d{6,15})@s\.whatsapp\.net", str(jid or ""))
    return "+" + m.group(1) if m else ""


class Adresboek:
    """Het adresboek dat WhatsApp van de iPhone overneemt (ContactsV2): naam per WhatsApp-adres, LID en nummer. Bij
    twee contacten met hetzelfde adres wint het oudste (Z_PK), zodat een naam niet van ronde tot ronde wisselt."""

    def __init__(self, rijen=()):
        self.jid, self.nummer = {}, {}
        for naam, wa, lid, nummer in rijen:
            naam = schoon(naam)
            if not naam:
                continue
            for j in (wa, lid):
                if j:
                    self.jid.setdefault(str(j), naam)
            sleutel = nummer_sleutel(nummer)
            if len(sleutel) >= 6:
                self.nummer.setdefault(sleutel, naam)

    def bij_jid(self, jid):
        return self.jid.get(str(jid or ""), "")

    def bij_nummer(self, nummer):
        sleutel = nummer_sleutel(nummer)
        return self.nummer.get(sleutel, "") if len(sleutel) >= 6 else ""


def maskerwoorden(rijen):
    """Wat het masker van de agent moet kennen (bord.Agent.prive): elke naam en elk nummer uit de rijen, zodat het nooit
    in een hartslag, nood of werkverslag terechtkomt. Geen zuivere hexcode: die kan in een ronde-ID staan."""
    uit = set()
    for r in rijen:
        for deel in re.split(r",\s*|^groep: ", str(r.get("personen") or "")):
            deel = deel.strip()
            if len(deel) >= 4 and not re.fullmatch(r"[0-9a-fA-F]+", deel):
                uit.add(deel)
    return uit


# ------------------------------------------------------------------------------------- de uitvoer lezen ---
def lees(pad, sql, args=()):
    """Een vraag aan de uitvoer van de helper, alleen lezend (immutable: het bestand verandert niet meer)."""
    if sql not in SQL:
        raise ValueError("onbekende vraag aan de kopie")
    con = sqlite3.connect(f"file:{urllib.parse.quote(str(pad))}?immutable=1", uri=True)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _venster(dagenlijst):
    return apple(daggrens(dagenlijst[0])), apple(daggrens(volgende(dagenlijst[-1])))


def _rij(uniek, dag, start, minuten_, personen, thema, bron, dubbel_van=""):
    return {"uniek": uniek, "datum": dag, "start": start, "minuten": minuten_, "personen": personen, "thema": thema,
            "prive": 1, "bron": bron, "dubbel_van": dubbel_van}


def _nieuwste(pad):
    rij = lees(pad, SQL_NIEUWSTE)
    return tijd(rij[0][0]) if rij and rij[0][0] else None


def whatsapp_rijen(pad, dagenlijst):
    """De rijen van WhatsApp voor de gegeven dagen. Geeft (rijen, info): info['nieuwste'] het nieuwste bericht in de
    hele databank, info['aanwezig'] de dagen met minstens een bericht of oproep (voor de dekking, P4)."""
    van, tot = _venster(dagenlijst)
    boek = Adresboek(lees(pad, SQL_CONTACTEN))
    sessies = {pk: (str(jid or ""), schoon(naam), soort) for pk, jid, naam, soort in lees(pad, SQL_GESPREKKEN)}
    per_jid = {}
    for pk, (jid, _, _) in sorted(sessies.items()):
        per_jid.setdefault(jid, pk)

    def wie(jid):
        pk = per_jid.get(str(jid or ""))
        return (boek.bij_jid(jid) or (sessies[pk][1] if pk is not None and sessies[pk][2] == PERSOON else "")
                or nummer_van_jid(jid) or "onbekend")

    def gespreksnaam(pk):
        jid, naam, soort = sessies.get(pk, ("", "", None))
        if soort == GROEP:
            return "groep: " + (naam or "zonder naam")
        return naam or wie(jid)

    per, aanwezig = {}, set()
    for pk, t, van_mij, soort in lees(pad, SQL_BERICHTEN, (van, tot)):
        moment = tijd(t)
        aanwezig.add(dag_van(moment))
        if soort in GEEN_BERICHT or sessies.get(pk, ("", "", None))[2] not in (PERSOON, GROEP):
            continue
        sleutel = (pk, dag_van(moment))
        x = per.setdefault(sleutel, {"in": 0, "uit": 0, "eerste": moment, "laatste": moment})
        x["uit" if van_mij else "in"] += 1
        x["eerste"], x["laatste"] = min(x["eerste"], moment), max(x["laatste"], moment)
    rijen = []
    for (pk, dag), x in sorted(per.items(), key=lambda kv: (kv[0][1], kv[1]["eerste"], kv[0][0])):
        jid = sessies[pk][0] or f"pk:{pk}"
        n = x["in"] + x["uit"]
        rijen.append(_rij(f"whatsapp:{hashlib.sha1(jid.encode()).hexdigest()}:{dag}", dag, start_van(x["eerste"]), 0,
                          gespreksnaam(pk), f"{n} berichten ({x['in']} in, {x['uit']} uit), {uur_van(x['eerste'])} tot "
                          f"{uur_van(x['laatste'])}", "whatsapp"))

    # Oproepen. Een oproep-ID kan twee gebeurtenissen hebben (opnieuw verbonden): binnen ZELFDE_OPROEP van de eerste
    # tellen ze samen; verder weg is het een andere oproep met dezelfde ID (P6). De sleutel draagt het begin van de
    # oproep en wordt bepaald over alles wat de helper gaf (62 dagen), ook buiten het venster: zo blijft ze dezelfde als
    # het venster opschuift (Codex R1). Rijen alleen voor een oproep die in het venster begint.
    meldingen = {str(s): pk for s, pk in lees(pad, SQL_OPROEPMELDINGEN) if s}
    deelnemers = defaultdict(list)
    for gebeurtenis, jid in lees(pad, SQL_WA_DEELNEMERS):
        if jid:
            deelnemers[gebeurtenis].append(str(jid))
    samen, begin_van = {}, {}
    for pk, ident, t, duur, inkomend, gemist, video, beller, groep in lees(pad, SQL_WA_OPROEPEN):
        moment = tijd(t)
        if van <= apple(moment) < tot:
            aanwezig.add(dag_van(moment))
        ident = re.sub(r"[^A-Za-z0-9-]", "", str(ident or "")) or f"pk{pk}"
        if ident not in begin_van or moment - begin_van[ident] > ZELFDE_OPROEP:
            begin_van[ident] = moment
        sleutel = f"{ident}-{int(apple(begin_van[ident]))}"
        x = samen.setdefault(sleutel, {"ident": ident, "begin": moment, "duur": 0.0, "inkomend": inkomend,
                                       "gemist": bool(gemist), "video": bool(video), "beller": beller, "groep": groep,
                                       "jids": []})
        x["begin"] = min(x["begin"], moment)
        x["duur"] += float(duur or 0)
        x["video"] |= bool(video)
        x["gemist"] &= bool(gemist)
        x["jids"] += [j for j in deelnemers.get(pk, []) if j not in x["jids"]]
    for sleutel, x in sorted(samen.items(), key=lambda kv: (kv[1]["begin"], kv[0])):
        if not van <= apple(x["begin"]) < tot:
            continue
        if x["groep"]:
            pk = per_jid.get(str(x["groep"]))
            persoon = gespreksnaam(pk) if pk is not None else "groep"
        elif x["jids"]:
            persoon = ", ".join(dict.fromkeys(wie(j) for j in x["jids"]))
        elif x["ident"] in meldingen:
            persoon = gespreksnaam(meldingen[x["ident"]])
        elif x["inkomend"] == 1 and x["beller"]:
            persoon = wie(x["beller"])
        else:
            persoon = "onbekend"
        richting = {1: "inkomend", 0: "uitgaand"}.get(x["inkomend"], "richting onbekend")
        thema = "WhatsApp-oproep, " + richting + (", video" if x["video"] else "")
        if x["duur"] <= 0:
            thema += ", gemist" if x["inkomend"] == 1 else ", niet beantwoord" if x["inkomend"] == 0 else ", zonder gesprek"
        rijen.append(_rij(f"whatsapp-oproep:{sleutel}", dag_van(x["begin"]), start_van(x["begin"]), minuten(x["duur"]),
                          persoon, thema, "whatsapp", "" if x["duur"] > 0 else GEMIST))
    return rijen, {"nieuwste": _nieuwste(pad), "aanwezig": aanwezig}


def telefoon_rijen(pad, dagenlijst, onbekend_als_nummer=True):
    """De oproepen van de iPhone voor de gegeven dagen, zonder WhatsApp en andere apps (TEL_DIENSTEN). Geeft (rijen,
    info): info['nieuwste'] de nieuwste oproep, info['aanwezig'] de dagen met minstens een oproep (welke dienst ook),
    info['overgeslagen'] het aantal oproepen van andere apps. onbekend_als_nummer: een nummer buiten het adresboek als
    nummer (Mehdi beslist)."""
    van, tot = _venster(dagenlijst)
    boek = Adresboek(lees(pad, SQL_CONTACTEN))
    rijen, aanwezig, overgeslagen = [], set(), 0
    for ident, t, duur, uitgaand, beantwoord, adres, dienst in lees(pad, SQL_TELEFOON):
        moment, duur = tijd(t), float(duur or 0)
        if not van <= apple(moment) < tot:
            continue
        aanwezig.add(dag_van(moment))
        soort = TEL_DIENSTEN.get(str(dienst or ""))
        ident = re.sub(r"[^A-Za-z0-9-]", "", str(ident or ""))
        if soort is None or not ident:
            overgeslagen += 1
            continue
        nummer = re.sub(r"[^\d+*#]", "", str(adres or ""))
        persoon = (boek.bij_nummer(nummer) or (nummer if onbekend_als_nummer else "onbekend nummer")) if nummer \
            else "nummer verborgen"
        thema = f"{soort}, {'uitgaand' if uitgaand else 'inkomend'}"
        if duur <= 0:
            thema += ", niet beantwoord" if uitgaand else ", gemist"
        # Codex Q1 en R1: de sleutel draagt de ID en het tijdstip van de oproep. Twee oproepen met dezelfde ID
        # overschrijven elkaar zo nooit, en de sleutel blijft dezelfde als het venster opschuift.
        rijen.append(_rij(f"telefoon:{ident}-{int(apple(moment))}", dag_van(moment), start_van(moment), minuten(duur), persoon, thema,
                          "telefoon", "" if duur > 0 else GEMIST))
    # de helper laat oproepen van andere apps al weg (Codex U1) en geeft alleen hun tijdstip: geteld in het venster (V3)
    try:
        overgeslagen += int(lees(pad, SQL_ANDERE_APPS, (van, tot))[0][0] or 0)
    except sqlite3.OperationalError:
        pass
    return rijen, {"nieuwste": _nieuwste(pad), "aanwezig": aanwezig, "overgeslagen": overgeslagen}


def sms_rijen(pad, dagenlijst, onbekend_als_nummer=True):
    """De sms en iMessages voor de gegeven dagen: per gesprek per dag een rij sms:<sha1 gesprek>:<dag>, zoals WhatsApp,
    nooit tekst. Geeft (rijen, info): info['nieuwste'] het nieuwste bericht in de hele databank, info['aanwezig'] de dagen
    met minstens een bericht (voor de dekking). Een adres buiten het adresboek staat er als nummer of mailadres."""
    van, tot = _venster(dagenlijst)
    boek = Adresboek(lees(pad, SQL_CONTACTEN))
    gesprekken = {pk: (str(ident or ""), soort, schoon(naam)) for pk, ident, soort, naam in lees(pad, SQL_SMS_GESPREKKEN)}
    deelnemers = defaultdict(list)
    for pk, adres in lees(pad, SQL_SMS_DEELNEMERS):
        if adres:
            deelnemers[pk].append(str(adres))

    def wie(adres):
        adres = str(adres or "")
        naam = boek.bij_nummer(adres) if "@" not in adres else ""
        if naam:
            return naam
        if not onbekend_als_nummer:
            return "onbekend"
        # TEL-3: een afzender in letters (een firmanaam) blijft als tekst; van een nummer alleen de cijfers
        tekst = "@" in adres or any(c.isalpha() for c in adres)
        return schoon(adres if tekst else re.sub(r"[^\d+*#]", "", adres)) or "onbekend"

    def gespreksnaam(pk):
        ident, soort, naam = gesprekken.get(pk, ("", None, ""))
        if soort == SMS_GROEP:
            return "groep: " + (naam or "zonder naam")
        leden = deelnemers.get(pk) or ([ident] if ident else [])
        return ", ".join(dict.fromkeys(wie(a) for a in leden)) or "onbekend"

    per, aanwezig = {}, set()
    for pk, t, van_mij, dienst in lees(pad, SQL_SMS_BERICHTEN, (van, tot)):
        moment = tijd(t)
        aanwezig.add(dag_van(moment))
        if pk not in gesprekken:
            continue
        x = per.setdefault((pk, dag_van(moment)), {"in": 0, "uit": 0, "eerste": moment, "laatste": moment, "diensten": {}})
        x["uit" if van_mij else "in"] += 1
        x["eerste"], x["laatste"] = min(x["eerste"], moment), max(x["laatste"], moment)
        d = "sms" if str(dienst or "").upper() in ("SMS", "RCS") else "iMessage"
        x["diensten"][d] = x["diensten"].get(d, 0) + 1
    rijen = []
    for (pk, dag), x in sorted(per.items(), key=lambda kv: (kv[0][1], kv[1]["eerste"], kv[0][0])):
        ident = gesprekken[pk][0] or f"pk:{pk}"
        n = x["in"] + x["uit"]
        diensten = ", ".join(f"{d} {k}" for d, k in sorted(x["diensten"].items()))
        rijen.append(_rij(f"sms:{hashlib.sha1(ident.encode()).hexdigest()}:{dag}", dag, start_van(x["eerste"]), 0,
                          gespreksnaam(pk), f"{n} berichten ({x['in']} in, {x['uit']} uit; {diensten}), "
                          f"{uur_van(x['eerste'])} tot {uur_van(x['laatste'])}", "sms"))
    return rijen, {"nieuwste": _nieuwste(pad), "aanwezig": aanwezig}


def dekking(kanaal, dagenlijst, gekopieerd, nieuwste, aanwezig):
    """F5 (contract met dagbundelaar.kanaal_van_dag) en Codex P4: een dag is gelezen als hij voorbij was toen de kopie
    gemaakt werd, de bron die dag zelf gegevens toont, en daarna nog iets nieuws kreeg. Een dag zonder enig bericht of
    enige oproep blijft dus onbekend, nooit nul: een Mac die sliep of een WhatsApp die niet draaide, toont niets."""
    vandaag = dag_van(gekopieerd)
    return [_rij(f"dekking:{kanaal}:{d}", d, "", 0, "", "gelezen", "dekking", DEKKING) for d in dagenlijst
            if d < vandaag and d in aanwezig and nieuwste is not None and nieuwste >= daggrens(volgende(d))]


def samenvatting(rijen, dag):
    """Aantallen voor een dag, zonder namen: voor de hartslag en het werkverslag."""
    rijen = [r for r in rijen if r["datum"] == dag and r["bron"] != "dekking"]
    chats = [r for r in rijen if r["uniek"].startswith(("whatsapp:", "sms:"))]
    oproepen = [r for r in rijen if not r["uniek"].startswith(("whatsapp:", "sms:"))]
    gesprek = [r for r in oproepen if not r["dubbel_van"]]
    return {"berichten": sum(int(r["thema"].split()[0]) for r in chats), "gesprekken": len(chats),
            "oproepen": len(gesprek), "minuten": sum(r["minuten"] for r in gesprek),
            "gemist": len(oproepen) - len(gesprek)}


# ------------------------------------------------------------------------------------------- de Mac-kant ---
def _prive_tekst(pad, grens=8 * 1024):
    fd = os.open(pad, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
            raise OSError("niet privé")
        return os.read(fd, grens + 1).decode("utf-8")
    finally:
        os.close(fd)


def lees_token(pad=TOKEN_PAD):
    try:
        token = _prive_tekst(pad).strip()
    except (OSError, UnicodeError):
        token = ""
    if not token or len(token) > 8 * 1024:
        raise MacFout("geen token", "Bordtoegang op de Mac ontbreekt of is niet privé", wie="mehdi")
    return token


def _privemap(pad):
    """Maak de map en elke ontbrekende bovenmap aan met 0700."""
    pad = Path(pad)
    for deel in reversed([pad, *pad.parents]):
        if not deel.exists():
            deel.mkdir(mode=0o700)
    return pad


def _schrijf_prive(pad, tekst):
    """Atomisch en privé (0600), zonder een bestaande symlink te volgen."""
    pad = Path(pad)
    fd, tijdelijk = tempfile.mkstemp(prefix=f".{pad.name}-", dir=pad.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(tekst)
        os.replace(tijdelijk, pad)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tijdelijk)
        raise


def stand_lezen(naam, map_=None):
    try:
        uit = json.loads(_prive_tekst(Path(map_ or STAAT / naam) / "stand.json"))
        return uit if isinstance(uit, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def stand_schrijven(naam, stand, map_=None):
    map_ = _privemap(Path(map_ or STAAT / naam))
    _schrijf_prive(map_ / "stand.json", json.dumps(stand, sort_keys=True))


@contextlib.contextmanager
def slot(naam, map_=None):
    """Een ronde tegelijk per agent op deze Mac."""
    map_ = _privemap(Path(map_ or STAAT / naam))
    fd = os.open(map_ / "ronde.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Bezet("er loopt al een ronde") from None
        yield
    finally:
        os.close(fd)


@contextlib.contextmanager
def tunnel(vm=VM):
    """ssh -L naar het bord op de VM (127.0.0.1:3022), zoals tekenaar.py. Geeft de url; sluit de tunnel na de ronde."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        poort = s.getsockname()[1]
    p = subprocess.Popen(["/usr/bin/ssh", "-N", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
                          "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=30",
                          "-L", f"127.0.0.1:{poort}:127.0.0.1:3022", vm],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if p.poll() is not None:
                raise MacFout("ssh-tunnel naar het bord kwam niet op", "De Mac bereikt het bord niet over ssh")
            with socket.socket() as s:
                s.settimeout(0.3)
                if s.connect_ex(("127.0.0.1", poort)) == 0:
                    break
            time.sleep(0.3)
        else:
            raise MacFout("ssh-tunnel naar het bord kwam niet op binnen dertig seconden",
                          "De Mac bereikt het bord niet over ssh")
        yield f"http://127.0.0.1:{poort}"
    finally:
        if p.poll() is None:
            p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()


def ssh_json(opdracht, vm=VM, timeout=120):
    """Een alleen-lezende opdracht van bordstand.py op de VM; het JSON-antwoord, of None. Geen ssh-uitvoer verder."""
    try:
        r = subprocess.run(["/usr/bin/ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", vm, opdracht],
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, check=False)
        return json.loads(r.stdout.decode("utf-8")) if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, UnicodeError, ValueError):
        return None


def bord_rijen(kanaal, van, tot):
    if kanaal not in HELPER or not all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) for d in (van, tot)):
        raise ValueError("geen kanaal of dag")
    uit = ssh_json(f"{BORDSTAND} --gesprekken {kanaal} {van} {tot}")
    if not isinstance(uit, dict):
        raise MacFout("bordstand.py gaf de gesprekken niet terug",
                      "Gesprekkentabel niet teruggelezen: bordstand.py op de VM antwoordt niet")
    return uit


def bord_stand(naam):
    uit = ssh_json(f"{BORDSTAND} {naam} --ronde", timeout=60)
    return uit if isinstance(uit, dict) else None


def bevestigd(stand, ronde_id):
    """Eindhartslag en kennis dragen allebei de eigen ronde-ID (N4, zoals de vorige WhatsApp-wacht)."""
    return (isinstance(stand, dict) and stand.get("status") in ("klaar", "waakt")
            and stand.get("status_ronde") == ronde_id and stand.get("kennis_ronde") == ronde_id)


def hartslag_publiek(naam, token, taak, detail):
    """Lukt de tunnel niet, dan via de publieke ingang een hartslag fout, zonder noodlijst (zoals tekenaar.py)."""
    try:
        req = urllib.request.Request(f"{BORD_PUBLIEK}/agent-status", method="POST",
                                     data=json.dumps({"naam": naam, "status": "fout", "taak": taak,
                                                      "detail": detail[:240]}).encode(),
                                     headers={"Content-Type": "application/json", "X-Agents-Token": token})
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:  # noqa: BLE001
        print(f"hartslag via de publieke ingang mislukt: {type(e).__name__}", flush=True)


def kopie_vragen(kanaal, wacht=KOPIE_WACHT, kopie=None, klok=time.time, slaap=time.sleep, start=None):
    """Vraag MacGesprekkenKopie een verse kopie: schrijf een nieuwe aanvraag-ID, start zijn launchd-taak (launchctl
    kickstart) en wacht op de status met precies die ID (P9). Geeft (pad van de uitvoer, tijdstip van de kopie)."""
    map_ = _privemap(Path(kopie or KOPIE) / kanaal)
    aanvraag = secrets.token_hex(16)
    _schrijf_prive(map_ / "aanvraag", aanvraag)
    t0 = klok()
    if start is None:
        r = subprocess.run(["/bin/launchctl", "kickstart", f"gui/{os.getuid()}/{HELPER[kanaal]}"],
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=30, check=False)
        gestart = r.returncode == 0
    else:
        gestart = start()
    if not gestart:
        raise MacFout("MacGesprekkenKopie niet gestart", "MacGesprekkenKopie staat niet in launchd op de Mac")
    status = None
    while klok() - t0 <= wacht:
        try:
            status = json.loads((map_ / "status.json").read_text(encoding="utf-8"))
            if isinstance(status, dict) and status.get("aanvraag") == aanvraag:
                break
        except (OSError, ValueError):
            pass
        status = None
        slaap(1)
    if status is None:
        raise MacFout("geen verse kopie binnen de wachttijd", "MacGesprekkenKopie gaf geen verse kopie")
    bronnen = status.get("bronnen") if isinstance(status.get("bronnen"), dict) else {}
    if status.get("uitkomst") == "geweigerd" or "geweigerd" in bronnen.values():
        raise MacFout("macOS weigert de databank", "MacGesprekkenKopie heeft geen volledige schijftoegang: "
                      "System Settings > Privacy & Security > Full Disk Access", wie="mehdi")
    if status.get("uitkomst") != "ok":
        slecht = ", ".join(sorted(f"{k} {v}" for k, v in bronnen.items() if v != "ok")) or status.get("uitkomst")
        raise MacFout(f"kopie mislukt: {slecht}", "Kopie van de databank op de Mac mislukt")
    # Codex R2: elke aanvraag heeft haar eigen uitvoer, en die gaat eerst naar een naam die alleen deze ronde kent;
    # een latere start van de helper kan ze dan niet meer vervangen terwijl ik lees.
    pad = map_ / f".lezen-{aanvraag}.sqlite"
    try:
        os.replace(map_ / f"gesprekken-{aanvraag}.sqlite", pad)
        merk = lees(pad, SQL_AANVRAAG)
    except (OSError, sqlite3.Error):
        merk = []
    if not merk or merk[0][0] != aanvraag:
        # Codex Q4: de status hoort bij mijn vraag, maar de uitvoer niet (een andere start schreef ze)
        raise MacFout("uitvoer hoort niet bij de aanvraag", "MacGesprekkenKopie gaf geen verse kopie")
    return pad, datetime.fromtimestamp(int(status["ts"]), timezone.utc)


def wis(pad):
    with contextlib.suppress(FileNotFoundError):
        os.unlink(pad)


def schrijf_en_lees_terug(kanaal, rijen, van, tot, call, terug=None):
    """Schrijf de rijen naar /api/gesprekken en lees ze terug langs een andere weg (bordstand.py over ssh): elke rij moet
    er staan zoals geschreven. Een rij van dit kanaal in het venster die de bron niet meer toont, wordt vervallen
    (dubbel_van buiten:vervallen); komt ze terug, dan zet de upsert dubbel_van weer leeg. De rem gaat voor het schrijven
    (Codex S1): toont de bron veel minder dan het bord kent, dan schrijft en markeert de ronde niets en stopt ze (Q2).
    Elke verdwenen rij telt mee, ook een met een andere sleutelvorm (T1): op 26-10-2026 stond er geen enkele
    WhatsApp-, telefoon- of dekkingsrij op het bord, dus een overstap is er niet; komt er ooit een, dan beslist een
    mens na de nood, nooit de ronde stil. Geeft het aantal vervallen rijen."""
    terug = terug or bord_rijen
    if len({r["uniek"] for r in rijen}) != len(rijen):
        raise MacFout("twee rijen met dezelfde sleutel", "Twee rijen met dezelfde sleutel: niets geschreven")
    verwacht = {r["uniek"]: vingerafdruk(r) for r in rijen}
    voor = terug(kanaal, van, tot)
    extra = sorted(u for u, x in voor.items() if u not in verwacht and (x or {}).get("d") != VERVALLEN)
    # Codex Q2: een bron die niets meer toont terwijl het bord rijen kent, of die in een keer minstens vijf rijen en
    # meer dan een vijfde van het bord kwijt is, is verdacht (een lege of halve databank).
    gegevens = [r for r in rijen if r["bron"] != "dekking"]
    if extra and (not gegevens or (len(extra) >= MIN_VERVALLEN and len(extra) * 5 > len(voor))):
        raise MacFout(f"bron toont veel minder rijen dan het bord ({len(extra)} zouden vervallen)",
                      "De bron toont veel minder rijen dan het bord kent: niets geschreven of gemarkeerd")
    for i in range(0, len(rijen), PER_KEER):
        antwoord = call("/api/gesprekken", {"rijen": rijen[i:i + PER_KEER]})
        if not isinstance(antwoord, dict) or not antwoord.get("ok"):
            raise MacFout("/api/gesprekken weigerde de rijen", "Gesprekkentabel nam de rijen niet aan")
    op_bord = terug(kanaal, van, tot)
    if any((op_bord.get(u) or {}).get("v") != v for u, v in verwacht.items()):
        raise MacFout("rijen niet teruggelezen zoals geschreven",
                      "Gesprekkentabel gaf de rijen niet terug zoals geschreven")
    if extra:
        call("/api/gesprekken/koppel", {"koppelingen": [{"uniek": u, "dubbel_van": VERVALLEN} for u in extra]})
        op_bord = terug(kanaal, van, tot)
        if any((op_bord.get(u) or {}).get("d") != VERVALLEN for u in extra):
            raise MacFout("vervallen rijen niet gemarkeerd", "Gesprekkentabel gaf de rijen niet terug zoals geschreven")
    return len(extra)


def lees_veilig(lezer, *args):
    """Codex Q5: een fout bij het lezen kan een waarde uit de bron in haar tekst dragen (een naam in een kapot
    tijdveld), en de ronde zet die tekst in de hartslag voor het masker de namen kent. Hier gaat alleen de soort fout
    verder."""
    try:
        return lezer(*args)
    except Exception as e:  # noqa: BLE001
        raise MacFout(f"uitvoer van MacGesprekkenKopie onleesbaar ({type(e).__name__})",
                      "Uitvoer van MacGesprekkenKopie onleesbaar") from None


def eindcontrole(ag, naam, taak, ronde_id, stand=None):
    """Na de ronde: staan eindhartslag en kennis met mijn ronde-ID op het bord? Zo niet (Codex Q6), dan een
    hartslag fout met een vaste nood, en die fout zelf ook teruglezen. Geeft True als de ronde bevestigd is."""
    stand = stand or bord_stand
    if bevestigd(stand(naam), ronde_id):
        return True
    lijst = ag.noden_bij_breuk([{"tekst": NIET_BEVESTIGD, "wie": "claude-code"}])
    # Codex R3: ook de fout draagt de ronde-ID, zodat het teruglezen een oude fout niet voor deze aanziet
    ag.hartslag("fout", taak=taak, detail=f"Bord heeft de ronde niet bevestigd; ronde-id:{ronde_id}", nood=lijst)
    na = stand(naam)
    if not (isinstance(na, dict) and na.get("status") == "fout" and na.get("status_ronde") == ronde_id
            and NIET_BEVESTIGD in (na.get("noden") or [])):
        print("ook de hartslag fout met de nood staat niet op het bord", flush=True)
    return False


def proefronde(runner, naam, python=None, stand=None):
    """Een ronde van een wacht als proef van de uitrol (Codex R5): ze moet zelf gelopen hebben (een bezette wacht
    eindigt met 75), slagen, en haar ronde-ID moet in eindhartslag en kennis op het bord staan. Geeft de ronde-ID."""
    r = subprocess.run([python or sys.executable, "-I", str(runner)], stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=900, check=False)
    ids = re.findall(r"ronde gelukt, ronde-id:([0-9a-f]{32})", r.stdout)
    if r.returncode != 0 or len(ids) != 1:
        raise MacFout(f"proefronde van {naam} niet gelukt (exit {r.returncode})")
    if not bevestigd((stand or bord_stand)(naam), ids[0]):
        raise MacFout(f"proefronde van {naam} niet bevestigd door het bord")
    return ids[0]


def grenzen_of_stop(werkwijze, grenzen):
    """De werkwijze moet zeggen wat ik nooit doe en wat Mehdi beslist (N2), anders lees ik niets."""
    nooit, beslist = grenzen(werkwijze)
    if not nooit or not beslist:
        raise MacFout("werkwijze zonder veiligheidsgrenzen", "Werkwijze op het bord mist de veiligheidsgrenzen",
                      wie="mehdi")

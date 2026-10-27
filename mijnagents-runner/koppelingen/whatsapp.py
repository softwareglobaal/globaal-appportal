"""WhatsApp tussen de agents en Mehdi: de Cloud API van Meta, via dezelfde koppeling als
whatsapp.globaal.be (softwareglobaal/globaal-whatsapp).

Mehdi, 30-09-2026: "de berichtgevingen die nu via Telegram komen, moeten via WhatsApp
komen." Bellen blijft via Twilio naar zijn telefoonnummer. Sinds 30-09-2026 schrijven de
agents van hun eigen nummer, UNABO Assistant (+32 460 23 30 42): WA_AFZENDER_PNID in
mijnagents-data/.env. Zonder die regel valt het terug op het nummer van WA_AFZENDER_FIRMA.

De regel van Meta: een bedrijfsnummer mag vrij schrijven binnen 24 uur nadat Mehdi dat
nummer iets stuurde. Daarbuiten alleen met een goedgekeurd sjabloon (WA_SJABLOON, bv.
agent_melding). Een vrij bericht buiten het venster geeft bij Meta geen fout terug maar
mislukt achteraf (131047); daarom lees ik het venster vooraf in whatsapp.gesprek, dat de
WhatsApp-app bij elk binnenkomend bericht bijwerkt.

Wat Mehdi naar het agentennummer stuurt, bewaart de WhatsApp-app in whatsapp.bericht,
maar Office ziet het niet: het nummer staat op in_inbox = false (migratie 178). Wat de
agents sturen, gaat buiten de app om.

Sleutel: META_WA_TOKEN in ~/appportal/.env, dezelfde als de WhatsApp-app. Nooit in code,
log of bord.
"""
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import organisatie

APPPORTAL_ENV = os.path.expanduser("~/appportal/.env")
AGENTS_ENV = os.path.expanduser("~/appportal/mijnagents-data/.env")
# Kostenrem (Shaniel, 01-10-2026: "door een klein foutje heel veel geld"). Alleen
# sjabloonberichten kosten geld; Meta kent voor WhatsApp geen bestedingsplafond. Daarom
# telt de code ze per Brusselse dag en stopt bij WA_SJABLOON_MAX_PER_DAG (standaard 10); daarna
# valt De Bode terug op Telegram tot de volgende dag. Vrije tekst binnen het venster is gratis.
# Van dat plafond blijven er WA_SJABLOON_RESERVE (standaard 2) vrij voor de vaste momenten van De Bode, het
# ochtendbericht en de avondbundel: die sturen met voorrang (B7, ontwerp regie-zoom v1.2).
TELLER = os.path.expanduser("~/appportal/mijnagents-data/wa_sjablonen.json")
MAX_SJABLONEN_STANDAARD = 10
RESERVE_STANDAARD = 2
# De VM draait op UTC: met date.today() begon de teller in de zomer om 02:00 Brussel (B7).
BRUSSEL = ZoneInfo("Europe/Brussels")
TIMEOUT = 20
MAX_TEKST = 3900            # Meta laat 4096 tekens toe per tekstbericht
MAX_PARAM = 900             # een sjabloonparameter: geen regeleinden, samen onder 1024
STANDAARD_KOP = "je agents"  # de eerste sjabloonparameter als de afzender geen eigen kop meegeeft


class NietBeschikbaar(RuntimeError):
    """WhatsApp kan nu niet: geen sleutel, geen nummer, of venster dicht zonder sjabloon."""


def _env():
    uit = {}
    for pad in (APPPORTAL_ENV, AGENTS_ENV):
        try:
            for regel in open(pad, encoding="utf-8"):
                regel = regel.strip()
                if regel and not regel.startswith("#") and "=" in regel:
                    k, v = regel.split("=", 1)
                    uit.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except OSError:
            pass
    for k, v in os.environ.items():
        uit[k] = v
    return uit


def e164(nummer):
    """'0486 33 35 21' of '+32486333521' -> '+32486333521' (Belgisch als er geen landcode is)."""
    cijfers = re.sub(r"[^\d+]", "", nummer or "")
    if cijfers.startswith("00"):
        cijfers = "+" + cijfers[2:]
    elif cijfers.startswith("0"):
        cijfers = "+32" + cijfers[1:]
    elif cijfers and not cijfers.startswith("+"):
        cijfers = "+" + cijfers
    return cijfers


def _sql_tekst(s):
    return "'" + str(s).replace("'", "''") + "'"


def instellingen():
    """Alles wat nodig is, zonder de sleutel zelf terug te geven aan de aanroeper."""
    env = _env()
    firma = env.get("WA_AFZENDER_FIRMA", "UNAB")
    pnid = env.get("WA_AFZENDER_PNID", "")
    nummer = ""
    waar = (f"meta_phone_number_id = {_sql_tekst(pnid)}" if pnid else
            f"firma_code = {_sql_tekst(firma)} and in_inbox and meta_phone_number_id is not null")
    try:
        rij = organisatie._psql(
            "select row_to_json(r) from (select meta_phone_number_id, nummer from whatsapp.nummer "
            f"where {waar} limit 1) r") or {}
        pnid = pnid or rij.get("meta_phone_number_id", "")
        nummer = rij.get("nummer", "")
    except Exception:  # noqa: BLE001
        pass
    return {"pnid": pnid, "afzender": nummer, "firma": firma,
            "mehdi": e164(env.get("WA_MEHDI") or env.get("ALARM_NUMMER", "")),
            "sjabloon": env.get("WA_SJABLOON", ""), "taal": env.get("WA_SJABLOON_TAAL", "nl"),
            "versie": env.get("META_GRAPH_VERSION", "v26.0"), "heeft_token": bool(env.get("META_WA_TOKEN"))}


def venster(ins=None):
    """(open, laatste bericht van Mehdi) voor het gesprek tussen het afzendnummer en Mehdi."""
    ins = ins or instellingen()
    if not (ins["pnid"] and ins["mehdi"]):
        return False, None
    rij = organisatie._psql(
        "select row_to_json(r) from (select g.laatste_binnen, "
        "g.laatste_binnen > now() - interval '23 hours 50 minutes' as open "
        "from whatsapp.gesprek g join whatsapp.nummer n on n.id = g.nummer_id "
        f"where n.meta_phone_number_id = {_sql_tekst(ins['pnid'])} and g.contact = {_sql_tekst(ins['mehdi'])} "
        "order by g.laatste_binnen desc nulls last limit 1) r") or {}
    return bool(rij.get("open")), rij.get("laatste_binnen")


def _post(ins, body):
    token = _env().get("META_WA_TOKEN", "")
    req = urllib.request.Request(f"https://graph.facebook.com/{ins['versie']}/{ins['pnid']}/messages",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.load(r)["messages"][0]["id"]
    except urllib.error.HTTPError as e:
        try:
            fout = json.load(e).get("error", {})
            detail = f"{fout.get('code')}: {fout.get('message')}"
        except ValueError:
            detail = str(e.code)
        raise RuntimeError(f"Meta weigerde het bericht ({detail})") from None


def plat(tekst, max_tekens=MAX_PARAM):
    """Een sjabloonparameter mag geen regeleinden of tabs bevatten (Meta-fout 132018). max_tekens None: niet afknippen,
    zodat een afzender kan meten of zijn tekst past (De Bode, de regel Gebundeld)."""
    delen = [d.strip(" -") for d in re.split(r"[\r\n\t]+", tekst or "") if d.strip(" -")]
    uit = re.sub(r" {4,}", "   ", " · ".join(delen))
    return uit if max_tekens is None else uit[:max_tekens]


def vandaag():
    """De Brusselse datum, als JJJJ-MM-DD: de dag waarop de kostenrem telt (B7)."""
    return datetime.now(BRUSSEL).date().isoformat()


def sjablonen_vandaag():
    """Hoeveel sjabloonberichten er vandaag (Brussel) al vertrokken (0 als de teller van gisteren is)."""
    try:
        with open(TELLER, encoding="utf-8") as f:
            t = json.load(f)
        return int(t.get("n", 0)) if t.get("datum") == vandaag() else 0
    except (OSError, ValueError):
        return 0


def _tel_sjabloon():
    n = sjablonen_vandaag() + 1
    try:
        with open(TELLER, "w", encoding="utf-8") as f:
            json.dump({"datum": vandaag(), "n": n}, f)
    except OSError as e:
        # zonder teller geen rem: dan liever geen betaald bericht
        raise NietBeschikbaar(f"sjabloonteller niet schrijfbaar ({e.strerror}); geen betaald bericht") from None
    return n


def max_sjablonen():
    try:
        return max(0, int(_env().get("WA_SJABLOON_MAX_PER_DAG", MAX_SJABLONEN_STANDAARD)))
    except ValueError:
        return MAX_SJABLONEN_STANDAARD


def reserve():
    """Hoeveel sjabloonberichten onder het plafond vrij blijven voor berichten met voorrang (WA_SJABLOON_RESERVE)."""
    try:
        return max(0, int(_env().get("WA_SJABLOON_RESERVE", RESERVE_STANDAARD)))
    except ValueError:
        return RESERVE_STANDAARD


def stuur(tekst, kop=STANDAARD_KOP, voorrang=False):
    """Naar Mehdi. Binnen het venster vrije tekst, daarbuiten het sjabloon. Geeft het kanaal terug.
    kop: de eerste sjabloonparameter; een eigen kop (het ochtendbericht) staat in vrije tekst als eerste regel.
    voorrang: buiten het venster stopt een gewoon bericht bij het plafond min de reserve, een bericht met voorrang pas
    bij het plafond (B7). Binnen het venster telt er niets: vrije tekst is gratis."""
    ins = instellingen()
    if not (ins["heeft_token"] and ins["pnid"] and ins["mehdi"]):
        raise NietBeschikbaar("WhatsApp niet ingesteld: META_WA_TOKEN, afzendnummer of Mehdi's nummer ontbreekt")
    try:
        open_, _ = venster(ins)
    except Exception as e:  # noqa: BLE001
        # de gespreksdatabank even weg (herstart, deploy): zeker niets verstuurd, later opnieuw (review PR 113)
        raise NietBeschikbaar(f"gesprek niet te lezen ({type(e).__name__})") from None
    naar = ins["mehdi"].lstrip("+")
    if open_:
        if kop and kop != STANDAARD_KOP and not tekst.lstrip().startswith(kop):
            tekst = f"{kop}\n\n{tekst}"
        for stuk in [tekst[i:i + MAX_TEKST] for i in range(0, len(tekst), MAX_TEKST)] or [""]:
            _post(ins, {"messaging_product": "whatsapp", "recipient_type": "individual", "to": naar,
                        "type": "text", "text": {"body": stuk, "preview_url": False}})
        return "whatsapp"
    if ins["sjabloon"]:
        plafond = max_sjablonen()
        if sjablonen_vandaag() >= plafond:
            raise NietBeschikbaar(f"dagplafond bereikt: {plafond} betaalde sjabloonberichten vandaag "
                                  "(WA_SJABLOON_MAX_PER_DAG); morgen weer via WhatsApp")
        if not voorrang and sjablonen_vandaag() >= plafond - reserve():
            raise NietBeschikbaar(f"dagplafond bereikt voor gewone berichten: {max(0, plafond - reserve())} van "
                                  f"{plafond} betaalde sjabloonberichten vandaag, de rest blijft voor de vaste "
                                  "momenten (WA_SJABLOON_RESERVE); morgen weer via WhatsApp")
        _tel_sjabloon()   # voor het versturen: een fout na de aanvraag telt beter mee dan niet
        _post(ins, {"messaging_product": "whatsapp", "to": naar, "type": "template",
                    "template": {"name": ins["sjabloon"], "language": {"code": ins["taal"]},
                                 "components": [{"type": "body", "parameters": [
                                     {"type": "text", "text": plat(kop)[:60]},
                                     {"type": "text", "text": plat(tekst)}]}]}})
        return "whatsapp-sjabloon"
    raise NietBeschikbaar("WhatsApp-venster dicht en nog geen goedgekeurd sjabloon")


def binnen(sinds_id=0):
    """Nieuwe berichten van Mehdi aan het afzendnummer, oudste eerst: [{id, tekst, tijd}]."""
    ins = instellingen()
    if not (ins["pnid"] and ins["mehdi"]):
        return []
    return organisatie._psql(
        "select coalesce(json_agg(r order by r.id), '[]'::json) from (select b.id, coalesce(b.tekst, '') as tekst, b.tijd "
        "from whatsapp.bericht b join whatsapp.gesprek g on g.id = b.gesprek_id "
        "join whatsapp.nummer n on n.id = g.nummer_id "
        f"where b.richting = 'in' and b.id > {int(sinds_id)} "
        f"and n.meta_phone_number_id = {_sql_tekst(ins['pnid'])} and g.contact = {_sql_tekst(ins['mehdi'])}) r") or []

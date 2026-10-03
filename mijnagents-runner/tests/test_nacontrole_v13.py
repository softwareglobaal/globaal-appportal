"""Gedragsproeven uit de nacontrole v1.3 (3 oktober 2026, op b230268): R1-R11, FR-119 tot FR-129.

Elke proef speelt een concreet geval uit de nacontrole na met fictieve brondata, tijdelijke SQLite en nagebootste
agenda- en bordaanroepen (geen oproep, geen mail, geen echte agendawijziging). R1 vangt de volledige uitgaande
payload van het bordtransport af. Een proef die crasht, telt als fout: zo faalt dit bestand op b230268 en slaagt
het na het herstel. Zonder netwerk en sleutels (ook CI).
"""
import json
import os
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="v13-")
os.environ.update({"BELLEN_UIT": "1", "TAKEN_DB": os.path.join(TMP, "taken.db"), "BORD_DB": os.path.join(TMP, "bord.db"),
                   "MAIL_AFSPRAKEN_DB": os.path.join(TMP, "mail.db"), "AGENDA_LEESSTAND": os.path.join(TMP, "geen", "leesstand.json")})
HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W          # noqa: E402
import bord                       # noqa: E402
import dagcontrole as D           # noqa: E402
import mail_afspraken as MA       # noqa: E402
import taken as T                 # noqa: E402
import regisseur as R             # noqa: E402

R.TAKEN_SLOT = os.path.join(TMP, "taken.slot")
LARA = next(k for k, n in W.KALENDERS.items() if n == "Lara")
PRIVE = "mehdipriveagena@gmail.com"
NU = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
ok = fout = 0


def proef(naam, fn):
    global ok, fout
    try:
        goed, extra = fn()
    except Exception as e:  # noqa: BLE001
        goed, extra = False, f"{type(e).__name__}: {e} | {traceback.format_exc().splitlines()[-3][:120]}"
    if goed:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {str(extra)[:500]}")


class Vervang:
    def __init__(self, *paren):
        self.paren = paren

    def __enter__(self):
        self.oud = [(o, n, getattr(o, n)) for o, n, _ in self.paren]
        for o, n, v in self.paren:
            setattr(o, n, v)

    def __exit__(self, *x):
        for o, n, v in self.oud:
            setattr(o, n, v)


def nieuwe_mail_db():
    MA.DB = os.path.join(tempfile.mkdtemp(prefix="mail-"), "mail.db")


def nieuwe_taken_db():
    T.DB = os.path.join(tempfile.mkdtemp(prefix="taak-"), "taken.db")


def _a(**k):
    basis = {"sleutel": "ics|u1|", "soort": "ics", "ics_uid": "u1", "recurrence_id": "", "sequence": 1, "dtstamp": "20261002T120000Z",
             "method": "REQUEST", "geannuleerd": False, "start": "2026-10-05T15:00:00+02:00", "einde": "2026-10-05T16:00:00+02:00",
             "titel": "Werfvergadering project Alfa", "locatie": "", "bron_mailbox": "mch@h-architects.be", "bron_message_id": "<a@x>",
             "bron_onderwerp": "Uitnodiging", "bron_ontvangen": "2026-10-02T14:00:00+02:00", "bron_afzender": "a@voorbeeld.be"}
    basis.update(k)
    return basis


# ---------------------------------------------------------------- R1: geen privédetail in welk bordbericht ook
def r1():
    dag = "2050-10-05"
    items = [{"id": "w", "kalender": W.WERKAGENDA, "titel": "!! Mehdi: [HA-KB] Werkvergadering TESTWERK", "start": f"{dag}T16:00:00+02:00",
              "einde": f"{dag}T17:00:00+02:00", "locatie": "Teststraat 1, 3000 Leuven", "deelnemers": [], "omschrijving": ""},
             {"id": "p", "kalender": PRIVE, "titel": "Medische controle TESTPRIVE", "start": f"{dag}T10:00:00+02:00",
              "einde": f"{dag}T11:00:00+02:00", "locatie": "Kliniekstraat 9 TESTADRES", "deelnemers": [], "omschrijving": ""},
             {"id": "l", "kalender": LARA, "titel": "Lara activiteit TESTLARA", "start": f"{dag}T16:00:00+02:00",
              "einde": f"{dag}T17:00:00+02:00", "locatie": "", "deelnemers": [], "omschrijving": ""}]
    verstuurd = []
    ag = bord.Agent("agenda-wacht-proef")
    with Vervang((W.agenda, "afspraken", lambda v, t: [dict(x) for x in items]), (W, "kalenders", lambda: [W.WERKAGENDA, PRIVE, LARA]),
                 (W, "ag", ag), (bord, "call", lambda pad, payload=None, method=None: verstuurd.append((pad, payload)) or {})):
        gelezen = W.afspraken(0, 1)
        regels = [f"{a['start'][11:16]} {a['titel']}" for a in gelezen]
        ag.klaarzet([{"voor": "mehdi", "soort": "dagplan", "sleutel": dag, "titel": f"Dagplan {dag}", "uniek": f"dagplan:{dag}",
                      "inhoud": "Vandaag:\n" + "\n".join("- " + r for r in regels)}])
        ag.log(f"dag {dag}", "bron", "synthetisch", "\n".join(a["titel"] + " " + a["locatie"] for a in gelezen))
        bev = D.dagcontrole(gelezen, dag)                 # een botsing werk-Lara draagt de tweede titel in de tekst
        ag.log(f"dag {dag}", "bevinding", "dagcontrole", "\n".join(b["tekst"] for b in bev))
        ag.hartslag("waakt", detail="; ".join(b["tekst"] for b in bev)[:200], nood=[{"tekst": b["tekst"], "wie": "mehdi"} for b in bev[:2]])
        ag.log_verstuur()
    blob = json.dumps(verstuurd, ensure_ascii=False)
    lekt = [t for t in ("TESTPRIVE", "TESTLARA", "TESTADRES") if t in blob]
    return (not lekt and "TESTWERK" in blob and any(p == "/api/klaarzet" for p, _ in verstuurd)
            and any(p == "/api/logboek" for p, _ in verstuurd) and any("botst met Lara" in json.dumps(x, ensure_ascii=False) for _, x in verstuurd)), (lekt, blob[:400])


proef("R1 dagplan, logboek, hartslag en een werk-Lara-botsing: geen privétitel of privé-adres in de uitgaande bordpayload", r1)


# ---------------------------------------------------------------- R2: een werkmail verlaagt privé niet
def r2():
    nieuwe_mail_db()
    k = {"map": "INBOX", "uid": 1, "van": "a@voorbeeld.be", "datum": "Fri, 02 Oct 2026 10:00:00 +0200", "tekst": "", "onderwerp": "Uitnodiging"}
    ics1 = ("BEGIN:VCALENDAR\nMETHOD:REQUEST\nBEGIN:VEVENT\nUID:m1\nSEQUENCE:1\nDTSTAMP:20261002T100000Z\nDTSTART:20501008T080000Z\n"
            "SUMMARY:Medische afspraak TESTMAIL\nEND:VEVENT\nEND:VCALENDAR\n")
    ics2 = ics1.replace("SEQUENCE:1", "SEQUENCE:2").replace("DTSTAMP:20261002T100000Z", "DTSTAMP:20261002T120000Z")
    MA.bewaar(MA.uit_kandidaat(dict(k, mailbox="mehdichegini@hotmail.com", message_id="<prive@x>", ics=[ics1])), NU)
    MA.bewaar(MA.uit_kandidaat(dict(k, mailbox="mch@h-architects.be", message_id="<werk@x>", ics=[ics2])), NU)
    rij = [a for a in MA.alle() if a["ics_uid"] == "m1"][0]
    MA.statussen_bewaren(MA.vergelijk(MA.alle(), [], NU), NU)
    bev = [b for b in D.dagcontrole([], "2050-10-08") if b["soort"] == "mail_ontbreekt"]
    tekst = " ".join(f"{b['a']['titel']} {b['tekst']}" for b in bev)
    return (rij["prive"] == 1 and rij["sequence"] == 2 and bev and "TESTMAIL" not in tekst), (rij["prive"], tekst)


proef("R2 dezelfde uitnodiging eerst uit Hotmail, daarna uit mch@: ze blijft privé en de dagcontrole toont geen titel", r2)


# ---------------------------------------------------------------- R3: verschillende uitnodigingen koppelen niet
def r3():
    uit = MA.vergelijk([_a()], [{"kalender": "werk", "id": "ander", "start": "2026-10-05T15:00:00+02:00", "einde": "2026-10-05T16:00:00+02:00",
                                 "_icaluid": "u2", "titel": "Werfvergadering project Beta"}], NU)[0]
    return uit["status"] in ("kandidaat", "ontbreekt"), uit["status"]


proef("R3 uitnodiging u1 'project Alfa' en agenda-uitnodiging u2 'project Beta' op hetzelfde uur: nooit gekoppeld", r3)


# ---------------------------------------------------------------- R4: buiten het venster is niet opgelost
def r4():
    nu = datetime(2026, 10, 2, 14, 0, tzinfo=timezone.utc)
    verplaatst = _a(start="2026-10-25T15:00:00+02:00", einde="2026-10-25T16:00:00+02:00", status="ontbreekt", detail="", melding="")
    gekoppeld = _a(sleutel="ics|u9|", ics_uid="u9", status="gekoppeld", detail="", melding="")
    meldingen = [{"kalender": W.PRIVE_AGENDA, "id": "oud", "start": "2026-10-05", "hele_dag": True, "titel": "VR Agendawacht: oud",
                  "_merk": {W.MAILMERK: MA.sleutel_kort(verplaatst)}},
                 {"kalender": W.PRIVE_AGENDA, "id": "klaar", "start": "2026-10-07", "hele_dag": True, "titel": "VR Agendawacht: klaar",
                  "_merk": {W.MAILMERK: MA.sleutel_kort(gekoppeld)}}]
    pat = []
    with Vervang((W, "_insert", lambda k, body, tok, toch=False: {}), (W, "_patch", lambda x, body, tok, toch=False: pat.append((x["id"], body)))):
        W.mail_meldingen([verplaatst, gekoppeld], meldingen, "t", nu)
    oud = [b for i, b in pat if i == "oud"]
    klaar = [b for i, b in pat if i == "klaar"]
    return (not any((b.get("summary") or "").startswith("Opgelost") for b in oud)
            and klaar and klaar[0]["summary"].startswith("Opgelost") and "staat nu in de agenda" in klaar[0]["description"]), pat


proef("R4 een vraag die naar 25 oktober (buiten 14 dagen) verhuist, blijft open; afronden alleen op bewijs, met de echte reden", r4)


# ---------------------------------------------------------------- R5-R7: taken en brondekking
def _ronde_log(log):
    def f(naam, inp):
        if naam == "agent_ronde":
            log.append(dict(inp))
            return {"exit": 0, "uitvoer": "klaar"}
        raise AssertionError(naam)
    return f


def r5():
    nieuwe_taken_db()
    log = []
    t = T.plannen("agent_ronde", "agenda-wacht", {"naam": "agenda-wacht", "dag": "2026-10-11"}, "2026-10-03T08:00:00+00:00",
                  afspraak_kalender="werk", afspraak_id="hele-dag", afspraak_start="2026-10-11")
    with Vervang((R, "voer_tool_uit", _ronde_log(log)), (R, "afspraak_nu", lambda k, i: ("er", "2026-10-21"))):
        R.taken_uitvoeren(datetime(2026, 10, 3, 8, 5, tzinfo=timezone.utc))
        voor = (T.haal(t["id"])["due_at"], T.haal(t["id"])["status"], list(log))
        R.taken_uitvoeren(datetime(2026, 10, 13, 8, 5, tzinfo=timezone.utc))
    na = T.haal(t["id"])
    return (voor[0] == "2026-10-13T08:00:00+00:00" and voor[1] == "gepland" and not voor[2]
            and na["status"] == "geverifieerd" and log == [{"naam": "agenda-wacht", "dag": "2026-10-21"}]), (voor, na["status"], log)


proef("R5 een hele-dag-afspraak verschuift van 11 naar 21 oktober: de taak gaat van 3 naar 13 oktober 08:00 UTC, niet eerder", r5)


def r6():
    nieuwe_taken_db()
    log, gevraagd = [], []
    ids = []
    for i in range(21):
        ids.append(T.plannen("agent_ronde", "agenda-wacht", {"naam": "agenda-wacht", "dag": "2026-10-31"}, "2026-10-23T08:00:00+00:00",
                             afspraak_kalender="werk", afspraak_id=f"event-{i:02d}", afspraak_start="2026-10-31T08:00:00+00:00")["id"])

    def nu_afspraak(k, aid):
        gevraagd.append(aid)
        return ("er", "2026-10-11T08:00:00+00:00") if aid == "event-20" else ("er", "2026-10-31T08:00:00+00:00")
    with Vervang((R, "voer_tool_uit", _ronde_log(log)), (R, "afspraak_nu", nu_afspraak)):
        for m in (0, 1, 2):
            R.taken_uitvoeren(datetime(2026, 10, 3, 8, 30 + m, tzinfo=timezone.utc))
    t21 = T.haal(ids[20])
    return ("event-20" in gevraagd and t21["due_at"] == "2026-10-03T08:00:00+00:00" and t21["status"] == "geverifieerd"
            and log == [{"naam": "agenda-wacht", "dag": "2026-10-11"}]), (t21["due_at"], t21["status"], log, sorted(set(gevraagd))[-2:])


proef("R6 met 21 open taken wordt ook de 21ste nagekeken: haar vervroegde afspraak maakt haar vandaag uitvoerbaar", r6)


def r7():
    nieuwe_mail_db()
    ruw = [{"kalender": W.WERKAGENDA, "id": "x", "titel": "synthetisch werk", "start": "2026-10-03T10:00:00+02:00", "einde": "2026-10-03T11:00:00+02:00"},
           {"kalender": "geweigerd@voorbeeld", "fout": "403"}]
    with Vervang((W, "afspraken", lambda v, t: [dict(x) for x in ruw]), (W, "kalenders", lambda: [W.WERKAGENDA, "geweigerd@voorbeeld"])):
        b = R.bronnen_lees("2026-10-03", "2026-10-03")
    dk = b.get("dekking") or {}
    per = dk.get("per_agenda") or {}
    return (dk.get("volledig") is False and any(v["status"] == "mislukt" and "403" in v["fout"] for v in per.values())
            and any(v["status"] == "geslaagd" for v in per.values()) and len(b["agenda"]) == 1), dk


proef("R7 een agenda die 403 geeft, staat als mislukt in de bronroute van de Regisseur; de dekking heet niet volledig", r7)


# ---------------------------------------------------------------- R8: [HARC-B2B] zonder bewijs schrijft niets
def r8():
    d = (W.nu_lokaal().date().toordinal() + 2)
    from datetime import date
    dag = date.fromordinal(d).isoformat()
    item = {"id": "b2b", "kalender": W.WERKAGENDA, "maker": W.WERKAGENDA, "titel": "Mehdi: [HARC-B2B] Fictieve Relatie", "start": f"{dag}T09:00:00+02:00",
            "einde": f"{dag}T10:00:00+02:00", "locatie": "", "deelnemers": [], "omschrijving": ""}
    geschreven = []
    with Vervang((W, "_patch", lambda a, body, tok, toch=False: geschreven.append(body.get("summary"))), (W.agenda, "_toegang", lambda: "t")):
        _, regels = W.titels_normaliseren([item])
    return (not geschreven and any("XB" in r and "XO" in r for r in regels)
            and W.canoniek("Mehdi: [HARC-B2B] Fictieve Relatie") == "Mehdi: [HARC-B2B] Fictieve Relatie"), (geschreven, regels)


proef("R8 [HARC-B2B] zonder bewijs van buiten of online: niets geschreven, de vraag XB of XO concreet", r8)


# ---------------------------------------------------------------- R9: een bron, geen strijdige opdrachten
def r9():
    import re
    t = json.loads((HIER / "werkwijze" / "agenda-taken.json").read_text(encoding="utf-8"))
    pijl = re.compile(r"->\s*(HARC|UNAB|TKNB|ENEF|ELEV|HARM|CONT|HINV|MELO|HDSI|HDSS|ALGE)\b|\[(HARC|UNAB|UNABO|TKNB|TKN|ALGE|ELEV)[-\]]")
    actief = [o["wat"][:60] for o in t["openstaand"] if o.get("status") != "vervangen" and pijl.search(o["wat"])]
    vervangen = [o for o in t["openstaand"] if o.get("status") == "vervangen"]
    gen = (HIER / "werkwijze" / "pdf" / "afspraken_pdf.py").read_text(encoding="utf-8")
    return (not actief and vervangen and all(o.get("vervangen_door") for o in vervangen) and "op_vervangen" in gen), actief


proef("R9 geen lopende open taak schrijft nog een oude code voor; de vervangen opdracht staat apart, met verwijzing", r9)


# ---------------------------------------------------------------- R10: een onbruikbare uitnodiging is geen volledige dekking
def r10():
    nieuwe_mail_db()
    slecht = {"mailbox": "mch@h-architects.be", "map": "INBOX", "uid": 7, "message_id": "<bad-date@x>", "van": "a@voorbeeld.be",
              "onderwerp": "Bijgewerkt: overleg", "datum": "Fri, 02 Oct 2026 12:00:00 +0000",
              "ics": ["BEGIN:VCALENDAR\nMETHOD:REQUEST\nBEGIN:VEVENT\nUID:bad-date\nDTSTART:20260231T090000Z\nSUMMARY:Overleg\nEND:VEVENT\nEND:VCALENDAR\n"],
              "tekst": ""}
    goed = dict(slecht, uid=8, message_id="<goed@x>", ics=[slecht["ics"][0].replace("bad-date", "goed-1").replace("20260231", "20261007")])
    with Vervang((MA, "lees", lambda sinds, mailboxen=MA.MAILBOXEN, maximaal=2000: ([slecht, goed], []))):
        MA.ronde([], "2026-09-20", NU)
    m = MA.leesstand()["mch@h-architects.be"]
    return (m["laatst_gelukt"] == "" and m.get("dekking") == "gedeeltelijk" and "<bad-date@x>" in m["laatste_fout"]
            and any(a["ics_uid"] == "goed-1" for a in MA.alle())), m


proef("R10 een uitnodiging met DTSTART 31 februari: verwerkingsfout met bericht-ID, dekking gedeeltelijk, de goede blijft bewaard", r10)


# ---------------------------------------------------------------- R11: een verplaatste reeksinstantie
def r11():
    mail = _a(recurrence_id="2026-10-05T15:00:00+02:00", method="CANCEL", geannuleerd=True)
    uit = MA.vergelijk([mail], [{"kalender": "werk", "id": "verplaatst", "start": "2026-10-06T15:00:00+02:00", "einde": "2026-10-06T16:00:00+02:00",
                                 "_icaluid": "u1", "_reeks": "reeks-1", "_origineel": "2026-10-05T15:00:00+02:00", "titel": "Werfvergadering project Alfa"}], NU)[0]
    src = (HIER / "koppelingen" / "agenda.py").read_text(encoding="utf-8")
    return (uit["status"] == "geannuleerd_staat_er" and '"_origineel"' in src and "originalStartTime" in src), uit["status"]


proef("R11 een annulering voor de instantie van 5 oktober, intussen verplaatst naar 6 oktober: ze staat er nog (vraag)", r11)

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

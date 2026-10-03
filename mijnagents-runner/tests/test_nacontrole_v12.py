"""Gedragsproeven uit 'Agendawacht - onderzoek en herstelvoorstel v1.2' (V1-V12, A5, A8, A11). FR-104 tot FR-115.

Elke proef speelt het gedrag na met fictieve brondata en nagebootste schrijfacties (geen oproep, geen mail, geen
echte agendawijziging). Een proef die crasht, telt als fout: zo faalt dit bestand op commit 3f5374c en slaagt het
na het herstel. Zonder netwerk en sleutels (ook CI).
"""
import json
import os
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="v12-")
os.environ.update({"BELLEN_UIT": "1", "TAKEN_DB": os.path.join(TMP, "taken.db"), "BORD_DB": os.path.join(TMP, "bord.db"),
                   "MAIL_AFSPRAKEN_DB": os.path.join(TMP, "mail.db")})
HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W          # noqa: E402
import dagcontrole as D           # noqa: E402
import mail_afspraken as MA       # noqa: E402
import taken as T                 # noqa: E402
import regisseur as R             # noqa: E402
import zelfcontrole as Z          # noqa: E402
import agenda_signaal as S        # noqa: E402

S.STAND = Path(TMP) / "agenda-signaal.json"
S.CONTROLEPUNTEN = Path(TMP) / "controlepunten.json"
R.TAKEN_SLOT = os.path.join(TMP, "taken.slot")
BRUSSEL = W.BRUSSEL if hasattr(W, "BRUSSEL") else timezone(timedelta(hours=2))
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
        print(f"  FOUT {naam} {str(extra)[:400]}")


class Vervang:
    """Tijdelijk een attribuut vervangen en daarna terugzetten."""
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


# ---------------------------------------------------------------- V1: een nieuwe titel krijgt nooit meer vier letters
def v1():
    import urllib.request
    d = (W.nu_lokaal() + timedelta(days=2)).date().isoformat()
    item = {"id": "f1", "kalender": W.WERKAGENDA, "maker": W.WERKAGENDA, "titel": "Mehdi: 2607 werfbezoek", "start": f"{d}T09:00:00+02:00",
            "einde": f"{d}T09:30:00+02:00", "locatie": "", "deelnemers": [], "omschrijving": ""}
    geschreven = []

    def nep_urlopen(req, timeout=30):
        geschreven.append(json.loads(req.data))
        import io
        return io.BytesIO(b"{}")
    with Vervang((W.projectadressen, "index", lambda *a, **k: {"2607": {"adres": "Teststraat 1, 3000 Leuven", "gemeente": "Leuven", "map": "x"}}),
                 (W, "klant_van_nummer", lambda nr: "Fictieve Klant" if nr == "2607" else ""), (W, "mag_schrijven", lambda k: True),
                 (W.agenda, "_toegang", lambda: "t"), (urllib.request, "urlopen", nep_urlopen)):
        for _ in range(2):          # twee volledige rondes, zoals de hoofdlus: eerst normaliseren, dan aanvullen
            W.titels_normaliseren([item])
            W.titels_aanvullen([item])
            if geschreven:
                item["titel"] = geschreven[-1].get("summary", item["titel"])
    titels = [g.get("summary", "") for g in geschreven]
    oud = [t for t in titels if any(c in t for c in ("[HARC", "[UNAB", "[TKN", "[ALGE"))]
    return (len(titels) == 1 and "[HA-KB]" in titels[0] and not oud), titels


proef("V1 een volledige schrijfroute levert [HA-KB], nooit [HARC-KB], en een tweede ronde verandert niets", v1)


# ---------------------------------------------------------------- V2: B2B zonder bewijs wordt geen XO
def v2():
    d = (W.nu_lokaal() + timedelta(days=2)).date().isoformat()
    uit = {}
    for naam, loc in (("zonder", ""), ("buiten", "Teststraat 1, 3000 Leuven"), ("online", "https://zoom.us/j/123")):
        item = {"id": naam, "kalender": W.WERKAGENDA, "maker": W.WERKAGENDA, "titel": "Mehdi: Harchitects B2B Fictieve Relatie",
                "start": f"{d}T09:00:00+02:00", "einde": f"{d}T10:00:00+02:00", "locatie": loc, "deelnemers": [], "omschrijving": ""}
        geschreven = []
        with Vervang((W, "_patch", lambda a, body, tok, toch=False: geschreven.append(body.get("summary"))), (W.agenda, "_toegang", lambda: "t")):
            _, regels = W.titels_normaliseren([item])
        uit[naam] = (geschreven, regels)
    zonder_gs, zonder_r = uit["zonder"]
    return (not zonder_gs and any("XB" in r and "XO" in r for r in zonder_r)
            and uit["buiten"][0] == ["Mehdi: [HA-XB] Fictieve Relatie"] and uit["online"][0] == ["Mehdi: [HA-XO] Fictieve Relatie"]), uit


proef("V2 B2B zonder bewijs van buiten of online: geen titel, een voorstel met XB en XO; met een adres XB, met een link XO", v2)


# ---------------------------------------------------------------- V3-V5: toezeggingen
def _nep_ronde(log):
    def f(naam, inp):
        if naam == "agent_ronde":
            log.append(dict(inp))
            return {"exit": 0, "uitvoer": "klaar"}
        raise AssertionError(naam)
    return f


def v3():
    nieuwe_taken_db()
    log = []
    t = T.plannen("agent_ronde", "agenda-wacht", {"naam": "agenda-wacht", "dag": "2026-10-10"}, "2026-10-02T10:00:00+02:00",
                  reden="acht dagen voor de afspraak de titel nakijken", afspraak_kalender="werk", afspraak_id="ev-a",
                  afspraak_start="2026-10-10T10:00:00+02:00")
    with Vervang((R, "voer_tool_uit", _nep_ronde(log)), (R, "afspraak_nu", lambda k, i: ("er", "2026-10-20T10:00:00+02:00"))):
        R.taken_uitvoeren(datetime(2026, 10, 2, 8, 5, tzinfo=timezone.utc))
        na1 = T.haal(t["id"])
        R.taken_uitvoeren(datetime(2026, 10, 12, 8, 5, tzinfo=timezone.utc))
        na2 = T.haal(t["id"])
    return (not log[:0] and na1["due_at"] == "2026-10-12T08:00:00+00:00" and na1["status"] == "gepland"
            and len(log) == 1 and log[0]["dag"] == "2026-10-20" and na2["status"] == "geverifieerd"), (na1["due_at"], na1["status"], log)


proef("V3 de afspraak verschuift van 10 naar 20 oktober: de taak 'acht dagen ervoor' schuift naar 12 oktober en draait dan voor 20 oktober", v3)


def v4():
    nieuwe_taken_db()
    log = []
    t = T.plannen("agent_ronde", "agenda-wacht", {"naam": "agenda-wacht", "dag": "2026-10-21"}, "2026-10-02T10:00:00+02:00")
    T.zet(t["id"], "bezig", "gestart", nu=datetime(2026, 10, 2, 8, 1, tzinfo=timezone.utc))      # de Regisseur crasht hier
    with Vervang((R, "voer_tool_uit", _nep_ronde(log))):
        R.taken_uitvoeren(datetime(2026, 10, 2, 8, 10, tzinfo=timezone.utc))        # lease loopt nog: niet dubbel draaien
        tussen = list(log)
        R.taken_uitvoeren(datetime(2026, 10, 2, 8, 40, tzinfo=timezone.utc))        # lease verlopen: opnieuw oppakken
    n = T.haal(t["id"])
    return (not tussen and len(log) == 1 and n["status"] == "geverifieerd"), (tussen, log, n["status"])


proef("V4 een taak die na een crash op 'bezig' bleef, wordt na haar lease opnieuw opgepakt, niet eerder", v4)


def v5():
    nieuwe_taken_db()
    log = []
    p = {"naam": "agenda-wacht", "dag": "2026-10-10"}
    a = T.plannen("agent_ronde", "agenda-wacht", p, "2026-10-02T10:00:00+02:00", afspraak_kalender="werk", afspraak_id="ev-A",
                  afspraak_start="2026-10-10T10:00:00+02:00")
    b = T.plannen("agent_ronde", "agenda-wacht", p, "2026-10-02T10:00:00+02:00", afspraak_kalender="werk", afspraak_id="ev-B",
                  afspraak_start="2026-10-10T10:00:00+02:00")
    with Vervang((R, "voer_tool_uit", _nep_ronde(log)),
                 (R, "afspraak_nu", lambda k, i: ("weg", None) if i == "ev-A" else ("er", "2026-10-10T10:00:00+02:00"))):
        R.taken_uitvoeren(datetime(2026, 10, 2, 8, 5, tzinfo=timezone.utc))
    return (a["id"] != b["id"] and T.haal(a["id"])["status"] == "vervallen" and T.haal(b["id"])["status"] == "geverifieerd"), \
        (a["id"], b["id"], T.haal(a["id"])["status"], T.haal(b["id"])["status"])


proef("V5 twee afspraken met dezelfde parameters en hetzelfde uur zijn twee taken; A geschrapt laat B staan", v5)


# ---------------------------------------------------------------- V6-V8: mail
def _a(**k):
    basis = {"sleutel": "ics|u1|", "soort": "ics", "ics_uid": "u1", "recurrence_id": "", "sequence": 1, "dtstamp": "20261002T120000Z",
             "method": "REQUEST", "geannuleerd": False, "start": "2026-10-05T15:00:00+02:00", "einde": "2026-10-05T16:00:00+02:00",
             "titel": "Werfvergadering Teststraat", "locatie": "", "bron_mailbox": "mch@h-architects.be", "bron_message_id": "<s@x>",
             "bron_onderwerp": "Uitnodiging", "bron_ontvangen": "2026-10-02T14:00:00+02:00", "bron_afzender": "a@voorbeeld.be"}
    basis.update(k)
    return basis


NU_MAIL = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)


def v6():
    zelfde_uid_ander_uur = MA.vergelijk([_a()], [{"kalender": "werk", "id": "g1", "start": "2026-10-05T09:00:00+02:00",
                                                   "einde": "2026-10-05T10:00:00+02:00", "_icaluid": "u1", "titel": "x"}], NU_MAIL)[0]
    ander_zelfde_uur = MA.vergelijk([_a(ics_uid="", sleutel="tekst|x")], [{"kalender": "prive", "id": "g2", "start": "2026-10-05T15:00:00+02:00",
                                                                           "titel": "Tandarts"}], NU_MAIL)[0]
    echt = MA.vergelijk([_a(ics_uid="", sleutel="tekst|y")], [{"kalender": "werk", "id": "g3", "start": "2026-10-05T15:02:00+02:00",
                                                               "titel": "!! Mehdi: [HA-KB] Werfvergadering 2607"}], NU_MAIL)[0]
    return (zelfde_uid_ander_uur["status"] == "afwijkend" and "09:00" in zelfde_uid_ander_uur["detail"]
            and ander_zelfde_uur["status"] == "kandidaat" and echt["status"] == "gekoppeld"), \
        (zelfde_uid_ander_uur["status"], ander_zelfde_uur["status"], echt["status"])


proef("V6 zelfde uitnodiging op een ander uur is afwijkend; een andere afspraak op hetzelfde uur is een kandidaat; woorden en uur samen is gekoppeld", v6)


def v7():
    nieuwe_mail_db()
    goed = {"mailbox": "mch@h-architects.be", "map": "INBOX", "uid": 1, "message_id": "<g@x>", "van": "a@voorbeeld.be",
            "onderwerp": "Uitnodiging: overleg", "datum": "Fri, 02 Oct 2026 10:00:00 +0200",
            "ics": ["BEGIN:VCALENDAR\nMETHOD:REQUEST\nBEGIN:VEVENT\nUID:goed-1\nDTSTART:20261007T080000Z\nSUMMARY:Overleg\nEND:VEVENT\nEND:VCALENDAR\n"],
            "tekst": ""}
    stuk = dict(goed, uid=2, message_id="<stuk@x>", ics=[None])          # dit bericht ontleedt niet
    lezer = lambda sinds, mailboxen=MA.MAILBOXEN, maximaal=2000: ([goed, stuk], [{"mailbox": "mch@h-architects.be", "map": "INBOX.Reizen",
                                                                                   "fout": "Map kan niet geopend worden"}])
    with Vervang((MA, "lees", lezer)):
        MA.ronde([], "2026-09-20", NU_MAIL)
    st = MA.leesstand()
    m, h = st["mch@h-architects.be"], st["mehdichegini@hotmail.com"]
    bewaard = any(a["ics_uid"] == "goed-1" for a in MA.alle())
    return (m["laatst_gelukt"] == "" and m.get("dekking") == "gedeeltelijk" and "INBOX.Reizen" in m["laatste_fout"]
            and "<stuk@x>" in m["laatste_fout"] and h["laatst_gelukt"] and bewaard), (m, h, bewaard)


proef("V7 een mislukte map of een bericht dat niet ontleedt: geen 'volledig gelezen', wel de fout met bron-ID; de rest wordt bewaard", v7)


def v8():
    nieuwe_mail_db()
    k = {"mailbox": "mch@h-architects.be", "map": "INBOX", "uid": 1, "van": "a@voorbeeld.be", "datum": "Fri, 02 Oct 2026 10:00:00 +0200", "tekst": ""}
    verzoek = "BEGIN:VCALENDAR\nMETHOD:REQUEST\nBEGIN:VEVENT\nUID:u2\nSEQUENCE:1\nDTSTAMP:20261002T100000Z\nDTSTART:20261007T080000Z\nSUMMARY:Werf\nEND:VEVENT\nEND:VCALENDAR\n"
    afgelast = "BEGIN:VCALENDAR\nMETHOD:CANCEL\nBEGIN:VEVENT\nUID:u2\nSEQUENCE:2\nDTSTAMP:20261002T130000Z\nEND:VEVENT\nEND:VCALENDAR\n"
    MA.bewaar(MA.uit_kandidaat(dict(k, message_id="<v@x>", onderwerp="Uitnodiging: Werf", ics=[verzoek])), NU_MAIL)
    ijl = MA.uit_kandidaat(dict(k, message_id="<c@x>", onderwerp="Geannuleerd: Werf", ics=[afgelast]))
    MA.bewaar(ijl, NU_MAIL)
    reg = [a for a in MA.alle() if a["ics_uid"] == "u2"]
    staat = MA.vergelijk(reg, [{"kalender": "werk", "id": "g", "start": "2026-10-07T10:00:00+02:00", "_icaluid": "u2", "titel": "Werf"}], NU_MAIL)[0]
    heledag = MA.vergelijk([_a(ics_uid="u3", sleutel="ics|u3|", geannuleerd=True, method="CANCEL", start="2026-10-05", einde="")],
                           [{"kalender": "werk", "id": "h", "start": "2026-10-05", "hele_dag": True, "_icaluid": "u3", "titel": "x"}], NU_MAIL)[0]
    return (len(ijl) == 1 and ijl[0]["method"] == "CANCEL" and ijl[0]["sequence"] == 2 and len(reg) == 1 and reg[0]["geannuleerd"]
            and reg[0]["start"].startswith("2026-10-07") and staat["status"] == "geannuleerd_staat_er"
            and heledag["status"] == "geannuleerd_staat_er"), (ijl, reg, staat["status"], heledag["status"])


proef("V8 een annulering zonder DTSTART houdt UID, SEQUENCE en METHOD; staat ze nog in de agenda, dan een vraag, ook bij een hele dag", v8)


def v9():
    nieuwe_mail_db()
    MA.bewaar([_a(sleutel="tekst|kine", ics_uid="", soort="tekst", start="2026-11-05T15:00:00+01:00", einde="", titel="Medische afspraak synthetisch",
                  bron_mailbox="mehdichegini@hotmail.com", prive=1)], NU_MAIL)
    MA.statussen_bewaren(MA.vergelijk(MA.alle(), [], NU_MAIL), NU_MAIL)
    bev = [b for b in D.dagcontrole([], "2026-11-05") if b["soort"] == "mail_ontbreekt"]
    tekst = " ".join(f"{b['a']['titel']} {b['tekst']}" for b in bev)
    bord = Z.voor_bord([{"controle": "op_vrije_dag", "titel": "Kapper", "tekst": "22:00 kapper", "prive": True},
                        {"controle": "rit_dubbel", "titel": "Rit", "tekst": "overlapt", "prive": False}])
    return (len(bev) == 1 and "Medische" not in tekst and "hotmail" not in tekst and W.is_prive({"kalender": "mehdipriveagena@gmail.com"})
            and bord[0]["titel"] == "(privé)" and "kapper" not in bord[0]["tekst"] and bord[1]["titel"] == "Rit"), (tekst, bord)


proef("V9 een privé-afspraak uit Hotmail komt zonder titel of adres in een bevinding; naar het bord gaat van privé alleen de soort", v9)


def v9b():
    import sqlite3
    nieuwe_mail_db()
    c = sqlite3.connect(MA.DB)
    for s in MA.SCHEMA:                 # een register zoals het er voor de privé-kolom uitzag
        c.execute(s)
    c.execute("INSERT INTO afspraak(sleutel, soort, bron_mailbox, bron_message_id) VALUES('zonder|<v@x>', 'zonder_tijd', "
              "'mehdichegini@hotmail.com', '<v@x>')")
    c.commit(); c.close()
    rij = [a for a in MA.alle() if a["sleutel"] == "zonder|<v@x>"]
    return (len(rij) == 1 and rij[0]["prive"] == 1), rij


proef("V9 een rij uit Hotmail van voor het privacylabel krijgt bij de upgrade alsnog het label privé", v9b)


# ---------------------------------------------------------------- V10-V12
def v10():
    items = [{"id": "m", "hele_dag": True, "titel": "geen afspraken", "start": "2026-10-06", "einde": "2026-10-07", "kalender": W.WERKAGENDA},
             {"id": "c", "titel": "Mehdi: [TK-PO]: Fictieve Prospect", "start": "2026-10-06T10:30:00+02:00", "einde": "2026-10-06T11:00:00+02:00",
              "kalender": W.WERKAGENDA, "deelnemers": ["p@voorbeeld.be"], "_merk": {W.JA_MERK: "2026-10-03"}, "omschrijving": "+32 470 00 00 00"}]
    bev = [b["soort"] for b in D.dagcontrole(items, "2026-10-06") if b["a"]["id"] == "c"]
    return "op_vrije_dag" in bev, bev


proef("V10 een ja voor 3 oktober geldt niet meer als de afspraak naar 6 oktober verhuist: de vraag komt terug", v10)


def v11():
    nieuwe_mail_db()
    nu = datetime(2026, 10, 2, 14, 0, tzinfo=BRUSSEL)
    a = _a(start="2026-10-06T15:00:00+02:00", einde="2026-10-06T16:00:00+02:00", status="ontbreekt", detail="", melding="")
    oud = {"kalender": W.PRIVE_AGENDA, "id": "n1", "start": "2026-10-05", "hele_dag": True, "titel": "VR Agendawacht: oud",
           "_merk": {W.MAILMERK: MA.sleutel_kort(a)}}
    ins, pat = [], []
    with Vervang((W, "_insert", lambda k, body, tok, toch=False: ins.append(body) or {}),
                 (W, "_patch", lambda x, body, tok, toch=False: pat.append((x["id"], body)))):
        W.mail_meldingen([a], [oud], "t", nu)
        z = _a(sleutel="zonder|<z@x>", soort="zonder_tijd", ics_uid="", start="", einde="", bron_onderwerp="Uitnodiging algemene vergadering")
        MA.bewaar([z], NU_MAIL)
        res = [dict(r, status="zonder_tijd") for r in MA.alle() if r["soort"] == "zonder_tijd"]
        W.mail_meldingen(res, [], "t", nu)
        res2 = [dict(r, status="zonder_tijd") for r in MA.alle() if r["soort"] == "zonder_tijd"]
        W.mail_meldingen(res2, [], "t", nu)
    verplaatst = [p for p in pat if p[0] == "n1" and p[1]["start"] == {"date": "2026-10-06"}]
    zonder = [b for b in ins if "zonder uur" in b["summary"]]
    return (len(verplaatst) == 1 and not [b for b in ins if "Werfvergadering" in b["summary"]] and len(zonder) == 1
            and res2[0]["melding"] == "2026-10-02"), (pat, [b["summary"] for b in ins], res2[0].get("melding"))


proef("V11 een mailmelding volgt haar afspraak naar een andere dag; een uitnodiging zonder uur krijgt een keer een blijvende vraag", v11)


def v12():
    gezet = []
    with Vervang((W, "_patch", lambda a, body, tok, toch=False: gezet.append(a["id"])), (W, "_transparantie", lambda a, tok: "transparent")):
        regels = W.markeringen_bezet([{"id": "z", "hele_dag": True, "_vrij": True, "titel": "geen afspraken", "start": "2026-10-05",
                                       "einde": "2026-10-06", "kalender": W.WERKAGENDA}], tok="t")
    goed, mis = W.bezet_splitsen(regels)
    return (gezet == ["z"] and goed == [] and len(mis) == 1), (regels, goed, mis)


proef("V12 een mislukte teruglezing van Bezet telt niet als 'op Bezet gezet', maar apart als mislukt", v12)


# ---------------------------------------------------------------- A5, A8: zichtbaar tot beoordeeld
def a5_a8():
    S.STAND.unlink(missing_ok=True)
    S.CONTROLEPUNTEN.unlink(missing_ok=True)
    dag = (datetime.now(timezone.utc) + timedelta(days=3)).date().isoformat()
    ev = {"id": "e1", "status": "confirmed", "summary": "Mehdi: [HA-IN] overleg", "start": {"dateTime": f"{dag}T10:00:00+02:00"},
          "end": {"dateTime": f"{dag}T11:00:00+02:00"}}
    weg = {"id": "onbekend-1", "status": "cancelled"}
    resultaat = {"lukt": False}
    with Vervang((S, "lees_wijzigingen", lambda kal, sinds, nu, kop: [ev, weg]), (S.W, "kalenders", lambda: ["werk"]),
                 (S.A, "_toegang", lambda: "t"),
                 (S, "draai_wacht", lambda d: (True, "ok") if resultaat["lukt"] else (False, "exitcode 1: proef"))):
        for _ in range(S.MAX_POGINGEN):
            S.ronde("proef")
        cp1 = S.controlepunten()
        resultaat["lukt"] = True
        ev["summary"] = "Mehdi: [HA-IN] overleg verzet"
        S.ronde("proef")
        cp2 = S.controlepunten()
    op1 = [c for c in cp1["opgegeven"] if c["dag"] == dag]
    op2 = [c for c in cp2["opgegeven"] if c["dag"] == dag]
    return (len(op1) == 1 and not op1[0]["beoordeeld"] and op2 and op2[0]["beoordeeld"]
            and [c["id"] for c in cp1["onbekend"]] == ["onbekend-1"] and not cp1["onbekend"][0]["beoordeeld"]), (cp1, cp2)


proef("A5/A8 een opgegeven dag en een annulering zonder bekende dag blijven staan tot beoordeeld; later slagen is beoordeeld", a5_a8)


def a11():
    a = "Versie 8.4 (03-10-2026)\nregel A\nregel B\n"
    return (Z.inhoud_hash(a) == Z.inhoud_hash("\n" + a.replace("regel A", "regel A   ") + "\n\n")
            and Z.inhoud_hash(a) != Z.inhoud_hash(a + "regel C, verkeerd\n")), None


proef("A11 borddrift wordt op inhoud vergeleken: dezelfde versie met een andere regel is drift, witruimte niet", a11)


def pdf():
    bron = (HIER / "werkwijze" / "pdf" / "afspraken_pdf.py").read_text(encoding="utf-8")
    return ("foutenregister v1.0" not in bron and "HDSS" not in bron and "foutenregister v{e(reg['versie'])}" in bron), None


proef("PDF-generator: de registerversie uit de bron, en geen interne code HDSS meer in de tekst", pdf)

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

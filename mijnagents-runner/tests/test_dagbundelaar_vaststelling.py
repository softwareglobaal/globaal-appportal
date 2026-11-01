"""Het vastleggen van De Dagbundelaar (dagbundelaar.vastleggen, ontwerp docs/ontwerp-dagvaststelling.md v1.2).

Legt vast, zonder netwerk en zonder de echte mappen (alles in een tijdelijke map):
- een eerste ronde schrijft versie 1: bestand, klaarzet-item voor mehdi met revisie, staat; bord en bestand dragen
  dezelfde tekst en worden teruggelezen (E6);
- een tweede ronde met dezelfde bronnen schrijft niets nieuws (geen versie 2, geen versies-map);
- een nieuwe bron geeft versie 2, met versie 1 in versies/ en 'herzien: ...' in het blok over de vaststelling (D9);
- toont het bord iets anders dan het bestand, dan faalt de ronde (teruglezen);
- een ontvangstbewijs van de Mac met dezelfde sha256 sluit de Dropbox-nood; zonder bewijs staat ze open, maar pas als de
  versie ouder is dan DROPBOX_TERMIJN (DB-1);
- de kanaalstand komt uit de hartslag van de wacht (D2): skelet is niet aangesloten, een verse databankronde wel, een
  oude is stil;
- het masker van het bord geldt al voor het schrijven: een privétekst staat nergens, ook niet in het bestand.
Draaien: python3 mijnagents-runner/tests/test_dagbundelaar_vaststelling.py
"""
import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
_argv, sys.argv = sys.argv, [sys.argv[0]]
import bord  # noqa: E402
import dagbundelaar as D  # noqa: E402
sys.argv = _argv

DAG = "2026-10-22"
NU = datetime.now(timezone.utc)


class NepRonde:
    def __init__(self):
        self.noden, self.bronnen = [], {}

    def nood(self, tekst, wie="mehdi"):
        self.noden.append(tekst)

    def bron(self, naam, inhoud):
        self.bronnen[naam] = inhoud


class Wereld:
    """De bronnen van een dag en een nagebootst bord dat klaarzet-items bewaart zoals het echte (uniek, revisie)."""

    def __init__(self, map_):
        self.map = map_
        self.rijen = [{"uniek": "zoom:meeting:a", "datum": DAG, "start": "10:24", "minuten": 6, "personen": "Mehdi, Ruben",
                       "afdeling": "", "thema": "", "prive": 0, "bron": "zoom", "dubbel_van": ""}]
        self.afspraken = [{"id": "t", "titel": "!! Mehdi: [UB-KB] PL 9001 - Pieter Claes, Geheime Straat 5, Proefdorp",
                           "start": f"{DAG}T14:15:00+02:00", "einde": f"{DAG}T15:15:00+02:00", "kalender": "werk",
                           "deelnemers": []}]
        self.status = {"whatsapp-wacht": {"naam": "whatsapp-wacht", "status": "rust", "taak": "", "ts": NU.isoformat()},
                       "belwacht": {"naam": "belwacht", "status": "rust", "taak": "", "ts": NU.isoformat()}}
        self.items, self.vervals = {}, None
        self.mailberichten, self.mailsql = None, ""                  # None: de twee rijen hieronder (db_lees)
        self.dagregel = json.dumps({"telling": "volledig", "stand": "definitief", "bronnen": {"rapport": "ok", "chat": "ok"},
                                    "chat": {"telling": "ondergrens"}})

    def db_lees(self, sql, args=()):
        if "FROM gesprek_log" in sql:
            return [dict(r) for r in self.rijen]
        if "FROM klaarzet" in sql:
            return [{"uniek": f"zoom:dag:{DAG}", "inhoud": self.dagregel}] if self.dagregel is not None else []
        if "FROM mailbericht" in sql:
            self.mailsql = sql
            if self.mailberichten is not None:
                return [dict(x) for x in self.mailberichten]
            return [{"postvak": "info@h-architects.be", "message_id": "<w1@x>", "datum": f"{DAG}T08:36:57+02:00", "soort": "koud"},
                    {"postvak": "info@h-architects.be", "message_id": "<w2@x>", "datum": f"{DAG}T09:00:00+02:00", "soort": "koud"}]
        if "FROM status" in sql:
            return list(self.status.values())
        raise AssertionError(sql)

    def klaarzet(self, items):
        for it in items:
            assert it["voor"] == "mehdi" and it["soort"] == "dagvaststelling" and it.get("revisie") is True, it
            self.items[it["uniek"]] = dict(it)
        return {"nieuw": len(items)}

    def call(self, pad, payload=None, method=None):
        assert pad.startswith("/api/klaarzet?uniek=vaststelling"), pad
        uniek = pad.split("uniek=")[1].split("&")[0].replace("%3A", ":")
        it = self.items.get(uniek)
        if it and self.vervals:
            it = dict(it, inhoud=self.vervals)
        return {"items": [it] if it else []}


def ronde(w, dagen=(DAG,), gisteren="2026-11-10", mail=None, logboek=None, open_noden=(), doe=None, **k):
    """Een ronde van vastleggen; gisteren ligt vast (standaard ruim na DAG, zodat Zoom niet meer voorlopig is). mail: een
    eigen lees_mail; logboek: een lijst die de regels van ag.log krijgt; open_noden: wat het bord als open noden geeft
    (None: onbekend); doe: in plaats van vastleggen, in dezelfde wereld (bv. main())."""
    oud = (D.DAGBOEK, D.STAAT, D.ONTVANGST, D.lees_agenda, D.lees_locatie, D.lees_mail, bord.db_lees, bord.call, D.V.gisteren)
    D.V.gisteren = lambda nu: gisteren
    D.DAGBOEK = os.path.join(w.map, "dagboek")
    D.STAAT = os.path.join(w.map, "staat.json")
    D.ONTVANGST = os.path.join(w.map, "ontvangst.txt")
    D.lees_agenda = lambda dagen_: ({DAG: list(w.afspraken)}, set(), lambda a: "[LA]" in a["titel"])
    D.lees_locatie = lambda dag, afspraken: ({"t": {"uitkomst": "doorgegaan", "tekst": "auto ter plaatse 14:31-16:07"}}, [],
                                             "afgesloten", "")
    D.lees_mail = mail or (lambda dagen_: ({"info@h-architects.be": {"berichten": [
        {"datum": f"{DAG}T08:36:57+02:00", "message_id": "<w1@x>"}], "onvolledig": []}}, {}, set()))
    bord.db_lees, bord.call = w.db_lees, w.call
    D.ag.klaarzet = w.klaarzet
    D.ag.log = (lambda *a, **k: logboek.append(a)) if logboek is not None else (lambda *a, **k: None)
    D.ag.open_noden = lambda: None if open_noden is None else [dict(n) for n in open_noden]
    r = NepRonde()
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            detail = doe() if doe else D.vastleggen(r, list(dagen), **k)
        return r, detail
    finally:
        D.DAGBOEK, D.STAAT, D.ONTVANGST, D.lees_agenda, D.lees_locatie, D.lees_mail, bord.db_lees, bord.call, D.V.gisteren = oud
        for naam in ("klaarzet", "log", "open_noden"):
            D.ag.__dict__.pop(naam, None)


def lees(pad):
    with open(pad, encoding="utf-8") as f:
        return f.read()


def test_versies_teruglezen_en_dropbox():
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        pad = os.path.join(m, "dagboek", "2026", f"{DAG}.md")
        r, detail = ronde(w)
        eerste = lees(pad)
        assert "versie 1" in eerste and "1 nieuw of herzien" in detail, detail
        assert w.items[f"vaststelling:{DAG}"]["inhoud"] == eerste, "bord en bestand dragen dezelfde tekst"
        assert "aanwijzing (auto ter plaatse 14:31-16:07" in eerste, eerste
        assert "info@h-architects.be: 2 binnen (2 koud)" in eerste, "gezien door de wachten telt mee, ontdubbeld"
        assert not any("Dropbox" in n for n in r.noden), "DB-1: een versie van deze ronde telt nog niet"
        assert any(n.startswith("WhatsApp:") for n in r.noden) and any(n.startswith("Telefoon:") for n in r.noden), r.noden
        assert not any(c.isdigit() for n in r.noden for c in n.split(":")[0]), "N10: geen aantal in een nood"
        # tweede ronde, zelfde bronnen: niets nieuws
        r, detail = ronde(w)
        assert lees(pad) == eerste and "0 nieuw of herzien" in detail, detail
        assert not os.path.exists(os.path.join(m, "dagboek", "2026", "versies")), "geen versie zonder wijziging"
        # een nagekomen gesprek: versie 2, versie 1 bewaard
        w.rijen.append(dict(w.rijen[0], uniek="zoom:meeting:b", start="20:00", minuten=30))
        r, detail = ronde(w)
        tweede = lees(pad)
        assert "versie 2" in tweede and "herzien: Niet gepland, Communicatie" in tweede, tweede
        assert lees(os.path.join(m, "dagboek", "2026", "versies", f"{DAG} v1.md")) == eerste
        assert w.items[f"vaststelling:{DAG}"]["inhoud"] == tweede and "(versie 2)" in w.items[f"vaststelling:{DAG}"]["titel"]
        # ontvangstbewijs van de Mac met dezelfde sha256: de Dropbox-nood sluit
        with open(D.ONTVANGST if False else os.path.join(m, "ontvangst.txt"), "w") as f:
            f.write(f"{D._sha(tweede)}  ./2026/{DAG}.md\n")
        r, _ = ronde(w)
        assert not any("Dropbox" in n for n in r.noden), r.noden
        # een bewijs van een oudere versie telt niet
        with open(os.path.join(m, "ontvangst.txt"), "w") as f:
            f.write(f"{D._sha(eerste)}  ./2026/{DAG}.md\n")
        _verouder(pad, 90)                                                  # DB-1: ouder dan de termijn
        r, _ = ronde(w)
        assert any("Dropbox" in n for n in r.noden), "oude versie in Dropbox"


def test_teruglezen_faalt_bij_verschil():
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        w.vervals = "# iets anders\n"
        try:
            ronde(w)
            raise AssertionError("een bord dat iets anders toont, moet de ronde laten falen")
        except RuntimeError as e:
            assert "niet teruggelezen" in str(e) and "bord" in str(e), e


def test_kanaalstand():
    nu = datetime(2026, 10, 26, 23, 30, tzinfo=timezone.utc)
    vers = {"status": "klaar", "taak": "databank lezen", "ts": (nu - timedelta(hours=2)).isoformat()}
    assert D.kanaalstand(vers, nu) == "aangesloten"
    assert D.kanaalstand(dict(vers, status="waakt"), nu) == "aangesloten"
    assert D.kanaalstand({"status": "rust", "taak": "", "ts": nu.isoformat()}, nu) == "niet aangesloten", "skelet"
    assert D.kanaalstand(None, nu) == "niet aangesloten"
    assert D.kanaalstand(dict(vers, ts=(nu - timedelta(hours=30)).isoformat()), nu).startswith("stil sinds")
    assert D.kanaalstand(dict(vers, status="fout"), nu).startswith("stil sinds")
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        w.status["whatsapp-wacht"] = dict(w.status["whatsapp-wacht"], status="klaar", taak="databank lezen", ts=NU.isoformat())
        w.rijen.append({"uniek": f"whatsapp:abc:{DAG}", "datum": DAG, "start": "08:01", "minuten": 0, "personen": "Broer Ali",
                        "afdeling": "", "thema": "14 berichten (5 van Mehdi)", "prive": 1, "bron": "whatsapp", "dubbel_van": ""})
        w.rijen.append({"uniek": f"dekking:whatsapp:{DAG}", "datum": DAG, "start": "00:00", "minuten": 0, "personen": "",
                        "afdeling": "", "thema": "gelezen", "prive": 0, "bron": "dekking", "dubbel_van": ""})
        r, _ = ronde(w)
        t = lees(os.path.join(m, "dagboek", "2026", f"{DAG}.md"))
        assert "WhatsApp: 14 berichten in 1 gesprekken" in t and "Broer Ali" not in t, t
        assert not any(n.startswith("WhatsApp:") for n in r.noden) and any(n.startswith("Telefoon:") for n in r.noden)


def test_masker_voor_het_schrijven():
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        D.ag.prive({"Geheime Straat 5"})
        try:
            ronde(w)
        finally:
            D.ag._prive.discard("Geheime Straat 5")
            D.ag._prive_re = None
        t = lees(os.path.join(m, "dagboek", "2026", f"{DAG}.md"))
        assert "Geheime Straat 5" not in t and "(privé)" in t, t
        assert w.items[f"vaststelling:{DAG}"]["inhoud"] == t


def test_f8_versie_uit_het_bestand_en_archief_nooit_overschreven():
    """F8: na een bordfout kan het bestand al versie 2 zijn terwijl de staat nog versie 1 zegt. De volgende versie volgt
    het bestand (3), en een bewaarde versie wordt nooit overschreven."""
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        pad = os.path.join(m, "dagboek", "2026", f"{DAG}.md")
        versies = os.path.join(m, "dagboek", "2026", "versies")
        ronde(w)
        w.rijen.append(dict(w.rijen[0], uniek="zoom:meeting:b", start="20:00", minuten=30))
        ronde(w)
        v1, v2 = lees(os.path.join(versies, f"{DAG} v1.md")), lees(pad)
        os.remove(os.path.join(m, "staat.json"))                      # de staat is weg of achter
        with open(os.path.join(versies, f"{DAG} v2.md"), "w") as f:  # en er staat al iets anders als v2
            f.write("een eerder bewaarde versie\n")
        w.rijen.append(dict(w.rijen[0], uniek="zoom:meeting:c", start="21:00", minuten=12))
        ronde(w)
        assert "versie 3" in lees(pad), lees(pad)
        assert lees(os.path.join(versies, f"{DAG} v1.md")) == v1, "v1 blijft"
        assert lees(os.path.join(versies, f"{DAG} v2.md")) == "een eerder bewaarde versie\n", "nooit overschreven"
        extra = [x for x in os.listdir(versies) if x.startswith(f"{DAG} v2 (")]
        assert len(extra) == 1 and lees(os.path.join(versies, extra[0])) == v2, os.listdir(versies)


def test_f8_letterlijk_teruglezen():
    """F8: het bord moet letterlijk dezelfde tekst tonen, ook het blok over de vaststelling."""
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        ronde(w)
        tekst = lees(os.path.join(m, "dagboek", "2026", f"{DAG}.md"))
        w.vervals = tekst.replace("versie 1", "versie 9")
        try:
            ronde(w)
            raise AssertionError("een ander versieblok op het bord moet de ronde laten falen")
        except RuntimeError as e:
            assert "bord" in str(e), e


def test_f5_dekking_per_dag():
    """F5: een aangesloten wacht bewijst alleen de dagen die ze als gelezen meldt (rij dekking:<kanaal>:<dag>)."""
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        w.status["whatsapp-wacht"] = dict(w.status["whatsapp-wacht"], status="klaar", taak="databank lezen", ts=NU.isoformat())
        r, _ = ronde(w)
        t = lees(os.path.join(m, "dagboek", "2026", f"{DAG}.md"))
        assert "WhatsApp: onbekend (onbekend voor deze dag)" in t, t
        w.rijen.append({"uniek": f"dekking:whatsapp:{DAG}", "datum": DAG, "start": "00:00", "minuten": 0, "personen": "",
                        "afdeling": "", "thema": "gelezen", "prive": 0, "bron": "dekking", "dubbel_van": ""})
        ronde(w)
        t = lees(os.path.join(m, "dagboek", "2026", f"{DAG}.md"))
        assert "WhatsApp: 0 berichten in 0 gesprekken" in t and "dekking" not in t.split("## Over")[0], t


class Module:
    def __init__(self, **k):
        self.__dict__.update(k)


def met_module(naam, module):
    oud = sys.modules.get(naam)
    sys.modules[naam] = module
    return lambda: sys.modules.__setitem__(naam, oud) if oud is not None else sys.modules.pop(naam, None)


def test_f1_privé_agenda_zonder_naam():
    W = Module(afspraken=lambda van, tot, alleen_lezen=True: [{"kalender": "gezin@x", "fout": "500"},
                                                              {"kalender": "werk@x", "fout": "500"}],
               archief_afspraken=lambda van, tot, alleen_lezen=True: [], ARCHIEF_FOUT="", PRIVE_KALENDERS={"gezin@x"},
               KALENDERS={"gezin@x": "Gezin", "werk@x": "H-Architects"}, prive_teksten=lambda x: set(),
               lees_titel=lambda t: {"reistijd": False}, is_prive=lambda a: False)
    herstel = met_module("agenda_wacht", W)
    try:
        _, ongelezen, _ = D.lees_agenda([DAG])
    finally:
        herstel()
    assert ongelezen == {"een privé-agenda", "H-Architects"}, ongelezen


def test_f1_f7_mail_privé_afzenders_en_plafond():
    """F1: een postvak van een wacht van afdeling privé is privé (mch@). F7: ook de adressen waaruit een wacht antwoordt,
    alleen hun verzonden post; een map op het plafond is onvolledig, ook bij verzonden."""
    gelezen = []

    def koppen(adres, m, sinds=None, plafond=1000, inhoud=None):
        gelezen.append((adres, m))
        return [{"datum": f"{DAG}T10:00:00+02:00", "message_id": f"<{adres}{m}{i}>", "van": "x@y"}
                for i in range(plafond if (adres, m) == ("light@h-architects.be", "INBOX.Sent") else 1)]
    PV = Module(wachten=lambda: {"mail-mch": {"postvakken": ["mch@h-architects.be"], "afdeling": "prive-communicatie",
                                              "firma": "MCH", "antwoord_vanuit": ["light@h-architects.be"]},
                                 "mail-info": {"postvakken": ["info@h-architects.be"], "firma": "HARC", "afdeling": "h-architects",
                                               "antwoord_vanuit": ["mch@h-architects.be"]}},
                postvak=lambda a: {"adres": a}, bron_uren_oud=lambda mb: None, BRON_VERS_UREN=3,
                mappen_van=lambda a: ["INBOX"], mapnamen=lambda mb: {"inbox", "inbox.sent"}, koppen=koppen,
                VERZONDEN=("INBOX.Sent", "Sent"))
    herstel = met_module("postvak", PV)
    try:
        o, u, prive = D._lees_mail([DAG])
    finally:
        herstel()
    assert prive == {"mch@h-architects.be", "light@h-architects.be"}, "H1: ook het antwoordadres van de privéwacht"
    assert ("light@h-architects.be", "INBOX.Sent") in gelezen and ("light@h-architects.be", "INBOX") not in gelezen, gelezen
    assert "light@h-architects.be" not in o and any("meer dan" in x for x in u["light@h-architects.be"]["onvolledig"]), u


def test_f4_locatie_met_dezelfde_afspraken_en_stand():
    """F4: De Locatiewacht krijgt dezelfde afsprakenlijst als de vaststelling; de stand van het dagboek gaat mee; een
    andere stand of een fout is 'niet gelezen'."""
    gezien = {}
    t = lambda uur: datetime.fromisoformat(f"{DAG}T{uur}:00+02:00").timestamp()  # noqa: E731

    def maak(dag, afspraken=None):
        gezien["afspraken"] = afspraken
        if gezien.get("stand") == "fout":
            raise ValueError("buiten de reeks")
        return {"status": gezien.get("stand", "voorlopig"), "geldig": 2,
                "meetpunten": [(t("14:20"), 51.0, 4.0, 0), (t("14:40"), 51.0, 4.0, 0)],
                "per_id": {"t": {"uitkomst": "niet_gezien", "lat": 51.0, "lon": 4.0}},
                "verblijven": [{"van": t("14:15"), "tot": t("14:45"), "lat": 51.0, "lon": 4.0, "waar": "project HARC 9004",
                                "project": {"nummer": "9004"}, "zekerheid": "waarschijnlijk"}],
                "werf": [], "twijfel": [], "elders": []}
    LW = Module(maak=maak, uur=lambda x: "00:00", online=lambda t: False, AFSPRAAK_M=300, MIN_BEZOEK=20,
                afstand_m=__import__("locatie_wacht").afstand_m, te_toetsen=__import__("locatie_wacht").te_toetsen)
    W = Module(lees_titel=lambda t: {"buiten": True, "soort": "KB"}, BUITEN_SOORTEN=("KB",))
    afs = [{"id": "t", "titel": "!! Mehdi: [UB-KB] x", "start": f"{DAG}T14:15:00+02:00", "einde": f"{DAG}T15:15:00+02:00"}]
    h1, h2 = met_module("locatie_wacht", LW), met_module("agenda_wacht", W)
    try:
        per_id, bezoeken, stand, reden = D.lees_locatie(DAG, afs)
        assert gezien["afspraken"] is afs and stand == "voorlopig" and not reden, (stand, reden)
        assert per_id["t"]["uitkomst"] == "doorgegaan" and bezoeken == [], (per_id, bezoeken)
        gezien["stand"] = "niet ingesteld"
        per_id, bezoeken, stand, reden = D.lees_locatie(DAG, afs)
        assert bezoeken is None and per_id["t"]["uitkomst"] == "onbekend" and "niet ingesteld" in reden, reden
        gezien["stand"] = "fout"
        per_id, bezoeken, stand, reden = D.lees_locatie(DAG, afs)
        assert bezoeken is None and reden == "ValueError", reden
    finally:
        h1()
        h2()


def test_f4_niet_gelezen_met_dezelfde_toetsregel_als_de_locatiewacht():
    """Codex, 26-10-2026: is de locatie niet te lezen, dan krijgt elke afspraak die De Locatiewacht zou toetsen
    'onbekend', ook een afspraak met een volledig adres alleen in de titel; hetzelfde gesprek online niet."""
    import locatie_wacht as LW

    def maak(dag, afspraken=None):
        raise ValueError("buiten de reeks")
    titel = "Mehdi: [HARC-IN] 9003 overleg, Proefplein 1, 3990 Proefstad"
    afs = [{"id": "adres", "titel": titel, "locatie": "", "start": f"{DAG}T10:00:00+02:00", "einde": f"{DAG}T11:00:00+02:00"},
           {"id": "online", "titel": titel, "locatie": "https://us06web.zoom.us/j/1", "start": f"{DAG}T14:00:00+02:00",
            "einde": f"{DAG}T15:00:00+02:00"},
           # Codex ronde 2: 9004 is een projectnummer, geen huisnummer; ook als maak() faalde voor de index geladen was
           {"id": "intern", "titel": "Mehdi: [HARC-IN] 9003 overleg Proefklant 9004, 3990 Proefstad", "locatie": "",
            "start": f"{DAG}T16:00:00+02:00", "einde": f"{DAG}T17:00:00+02:00"}]
    index = {"projectplekken": [{"sleutel": "HARC:9004", "nummer": "9004", "actief": True, "adres": "Proefweg 1, 3990 Proefstad"}]}
    gevraagd = []

    def haal(pad):
        gevraagd.append(pad)
        if gezien.get("tegel") == "traag":
            raise TimeoutError("de tegel antwoordt niet")
        return index

    def maak_na_index(dag, afspraken=None):
        LW.projectindex()
    gezien = {}
    oud, LW.maak = LW.maak, maak
    oud_haal, bekend, poging, LW.haal = LW.haal, set(LW.BEKENDE_NUMMERS), dict(LW.INDEX_POGING), haal
    LW.INDEX_POGING.update(per_nummer=None, mislukt=False)
    try:
        per_id, bezoeken, stand, reden = D.lees_locatie(DAG, afs)
        assert per_id == {"adres": {"uitkomst": "onbekend", "tekst": "locatie niet gelezen (ValueError)"}}, per_id
        assert bezoeken is None and reden == "ValueError" and len(gevraagd) == 1, (bezoeken, reden, gevraagd)
        # Codex ronde 3: faalde de index al in maak(), dan geen tweede lange poging in de terugval
        gezien["tegel"], LW.maak, gevraagd[:] = "traag", maak_na_index, []
        per_id, bezoeken, stand, reden = D.lees_locatie(DAG, afs)
        assert reden == "TimeoutError" and len(gevraagd) == 1, (reden, gevraagd)
        assert set(per_id) == {"adres"}, "de nummers van de vorige geslaagde index blijven gelden"
    finally:
        LW.maak, LW.haal = oud, oud_haal
        LW.BEKENDE_NUMMERS.clear()
        LW.BEKENDE_NUMMERS.update(bekend)
        LW.INDEX_POGING.clear()
        LW.INDEX_POGING.update(poging)


def test_g2_locatie_zonder_meting():
    """G2, J1 en K2 (ontwerp v1.7 en v1.8): het oordeel komt uit de ruwe meetpunten in het venster van de afspraak, met de
    plek van De Locatiewacht; de bezoeken zonder afspraak uit de verblijven met de echte meettijden en de eigen koppeling.
    Codex' tegenproef: de indeling voegde een parkeerstuk vanaf middernacht samen met een gemeten bezoek in de namiddag op
    dezelfde plek, en De Locatiewacht hing dat stuk aan de ochtendafspraak. Er is geen ochtendmeting."""
    t = lambda uur: datetime.fromisoformat(f"{DAG}T{uur}:00+02:00").timestamp()  # noqa: E731
    plek, elders, werf = (50.8790, 4.7010), (50.9300, 4.8000), (50.8500, 4.6500)
    gezien = {"punten": [(t("16:30"), *elders, 50), (t("17:05"), *plek, 0), (t("17:20"), *plek, 0), (t("19:58"), *elders, 40),
                         (t("20:05"), plek[0] + 0.001, plek[1], 30), (t("20:06"), *plek, 1), (t("20:08"), *plek, 25),
                         (t("20:10"), *elders, 50), (t("14:58"), *werf, 5), (t("15:40"), *werf, 8)]}

    def maak(dag, afspraken=None):
        return {"status": "afgesloten", "geldig": len(gezien["punten"]), "meetpunten": sorted(gezien["punten"]),
                "per_id": {"ochtend": {"uitkomst": "doorgegaan", "lat": werf[0], "lon": werf[1]},
                           "avond": {"uitkomst": "niet_gezien", "lat": plek[0], "lon": plek[1]},
                           "laat": {"uitkomst": "doorgegaan", "lat": plek[0], "lon": plek[1]},
                           "zonder": {"uitkomst": "zonder_adres", "tekst": "geen adres"}},
                "verblijven": [
                    # samengevoegd: vanaf middernacht tot 15:45 op de werf; gemeten is alleen 14:58 tot 15:40
                    {"van": t("00:00"), "tot": t("15:45"), "lat": werf[0], "lon": werf[1], "waar": "project HARC 9004",
                     "project": {"nummer": "9004"}, "zekerheid": "waarschijnlijk", "afspraak": "ochtend"},
                    # het gestopte bezoek bij de avondafspraak hoort bij die afspraak
                    {"van": t("17:00"), "tot": t("17:25"), "lat": plek[0], "lon": plek[1], "waar": "x", "zekerheid": None},
                    # een verblijf zonder meting valt weg; een vaste plek ook
                    {"van": t("21:00"), "tot": t("22:00"), "lat": 51.2, "lon": 4.4, "waar": "y", "zekerheid": None},
                    {"van": t("16:25"), "tot": t("16:59"), "lat": elders[0], "lon": elders[1], "waar": "Thuis", "vaste_plek": True}],
                "werf": [], "twijfel": [], "elders": []}
    LW = Module(maak=maak, uur=lambda x: "00:00", online=lambda t: False, AFSPRAAK_M=300, MIN_BEZOEK=20,
                afstand_m=__import__("locatie_wacht").afstand_m, te_toetsen=__import__("locatie_wacht").te_toetsen)
    W = Module(lees_titel=lambda t: {"buiten": True, "soort": "KB"}, BUITEN_SOORTEN=("KB",))
    a = lambda i, s_, e: {"id": i, "titel": "!! Mehdi: [HA] 9003", "start": f"{DAG}T{s_}:00+02:00", "einde": f"{DAG}T{e}:00+02:00"}  # noqa: E731
    afs = [a("ochtend", "10:00", "11:00"), a("avond", "17:00", "18:00"), a("laat", "20:00", "21:00"), a("zonder", "12:00", "13:00")]
    h1, h2 = met_module("locatie_wacht", LW), met_module("agenda_wacht", W)
    try:
        per_id, bezoeken, stand, reden = D.lees_locatie(DAG, afs)
        assert per_id["ochtend"] == {"uitkomst": "onbekend", "tekst": "auto zonder meting op dat uur"}, per_id
        assert per_id["avond"]["uitkomst"] == "doorgegaan" and "gestopt bij de plek 17:05 tot 17:20" in per_id["avond"]["tekst"], per_id
        assert per_id["laat"] == {"uitkomst": "niet_gezien", "tekst": "auto reed voorbij de plek 20:05, geen stop gemeten"}, per_id
        assert per_id["zonder"]["uitkomst"] == "zonder_adres", per_id
        # K2: het gemeten werfbezoek in de namiddag blijft, met de gemeten tijden; het avondbezoek hoort bij de afspraak
        assert bezoeken == [{"van": "14:58", "tot": "15:40", "minuten": 42, "waar": "project HARC 9004", "soort": "project"}], bezoeken
        gezien["punten"] = []
        per_id, bezoeken, stand, reden = D.lees_locatie(DAG, afs)
        assert bezoeken is None and reden == "geen meting die dag", (bezoeken, reden)
        assert all(u["uitkomst"] == "onbekend" for u in per_id.values()), per_id
    finally:
        h1()
        h2()


def test_g2_meetpunten():
    import locatie_wacht as LW
    db = {"punten": [{"tijd": f"{DAG}T10:42:00+02:00", "geldig": True, "lat": 50.1, "lon": 4.1, "snelheid": 12},
                     {"tijd": f"{DAG}T09:00:00+02:00", "geldig": False, "lat": 50.2, "lon": 4.2},
                     {"tijd": f"{DAG}T08:15:00+02:00", "geldig": True, "lat": 50.3, "lon": 4.3},
                     {"tijd": f"{DAG}T08:20:00+02:00", "geldig": True}, "rommel"]}
    assert LW.meetpunten(db) == [(datetime.fromisoformat(f"{DAG}T08:15:00+02:00").timestamp(), 50.3, 4.3, None),
                                 (datetime.fromisoformat(f"{DAG}T10:42:00+02:00").timestamp(), 50.1, 4.1, 12.0)]
    assert LW.meetpunten({}) == []


def test_g3_zoom_uit_de_dagregel():
    """G3 en J2 (ontwerp v1.7): de dagregel is het bewijs. Volledig alleen met telling volledig, stand definitief en elke
    bron ok; een exit van de keten verandert niets, en er blijft geen vlag in de staat."""
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        pad = os.path.join(m, "dagboek", "2026", f"{DAG}.md")

        def regel():
            return next(x for x in lees(pad).splitlines() if "Zoom, Fathom en Plaud" in x)
        for gelezen in (False, True, None):
            ronde(w, zoom_gelezen=gelezen)
            assert "De Zoomwacht: volledig gelezen" in regel(), (gelezen, regel())
        w.dagregel = json.dumps({"telling": "volledig", "stand": "definitief", "bronnen": {"rapport": "fout", "chat": "ok"}})
        ronde(w)
        assert "De Zoomwacht: onvolledig gelezen" in regel(), "een bron faalde in de ronde die de regel schreef"
        w.dagregel = json.dumps({"telling": "volledig", "stand": "voorlopig: 1 wacht", "bronnen": {"rapport": "ok"}})
        ronde(w)
        assert "De Zoomwacht: onvolledig gelezen" in regel(), "niet definitief"
        w.dagregel = None
        ronde(w)
        assert "gesprekken gezien" in regel() and "De Zoomwacht: stand onbekend" in regel(), regel()
        assert D.ZOOM_ONZEKER not in json.load(open(os.path.join(m, "staat.json")))


def test_k1_zoom_voorlopig_binnen_de_terugblik():
    """K1, L1, L2, L3: tot zes dagen na de dag heet de lezing van De Zoomwacht 'nog niet afgesloten', daarna geeft ze haar
    eigen oordeel. De vaststelling zelf telt altijd wat gezien is; een late Fathom-rij of een dagregel die na zeven dagen
    nog verandert (een item dat nog klaarstond), geeft een nieuwe versie, nooit een exact totaal."""
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        pad = os.path.join(m, "dagboek", "2026", f"{DAG}.md")

        def regel():
            return next(x for x in lees(pad).splitlines() if "Zoom, Fathom en Plaud" in x)
        ronde(w, gisteren="2026-10-22")
        assert "gezien" in regel() and "De Zoomwacht: nog niet afgesloten" in regel(), regel()
        ronde(w, gisteren="2026-10-27")                   # vandaag 28-10: zes dagen na de dag, nog niet afgesloten
        assert "nog niet afgesloten" in regel(), regel()
        ronde(w, gisteren="2026-10-28")                   # vandaag 29-10: zeven dagen, de regel is af
        assert "De Zoomwacht: volledig gelezen" in regel() and "versie 2" in lees(pad), regel()
        # L2: een late Fathom-rij na zeven dagen geeft een nieuwe versie met wat dan gezien is; nooit een exact totaal
        w.rijen.append({"uniek": "fathom:laat", "datum": DAG, "start": "21:00", "minuten": 12, "personen": "Ruben",
                        "afdeling": "", "thema": "", "prive": 0, "bron": "fathom", "dubbel_van": ""})
        ronde(w, gisteren="2026-11-01")
        assert "gesprekken gezien in Zoom, Fathom en Plaud: 2, 18 min" in regel() and "versie 3" in lees(pad), regel()
        # L3: een dagregel die na zeven dagen nog verandert (nog klaar, dus herzienbaar) geeft een nieuwe versie met het
        # oordeel van De Zoomwacht zoals het dan is
        w.dagregel = json.dumps({"telling": "ondergrens", "stand": "definitief", "bronnen": {"rapport": "ok", "chat": "ok"}})
        ronde(w, gisteren="2026-11-02")
        assert "De Zoomwacht: onvolledig gelezen" in regel() and "versie 4" in lees(pad), regel()


def test_g3_zoomstand_uit_de_dagregel():
    ok = {"a": "ok"}
    regel = json.dumps({"telling": "volledig", "stand": "definitief", "bronnen": ok})
    assert D.zoomstand(regel, "2026-10-22", "2026-10-28")[0] == "voorlopig"
    assert D.zoomstand(regel, "2026-10-22", "2026-10-29")[0] == "volledig"
    assert D.zoomstand(json.dumps({"telling": "volledig", "stand": "definitief", "bronnen": ok,
                                   "chat": {"telling": "ondergrens"}})) == ("volledig", "ondergrens")
    assert D.zoomstand(json.dumps({"telling": "volledig", "stand": "definitief"}))[0] == "ondergrens", "zonder bronnen"
    assert D.zoomstand(json.dumps({"telling": "volledig", "bronnen": ok}))[0] == "ondergrens", "zonder stand"
    assert D.zoomstand(json.dumps({"telling": "volledig", "stand": "definitief", "bronnen": {"a": "ok", "b": "geen recht: x"}}))[0] \
        == "ondergrens"
    assert D.zoomstand("") == ("onbekend", "onbekend") and D.zoomstand("{kapot") == ("onbekend", "onbekend")


def test_h1_antwoordadressen_van_een_privewacht():
    PV = Module(wachten=lambda: {"mail-mch": {"postvakken": ["mch@x.be"], "afdeling": "prive-communicatie",
                                              "antwoord_vanuit": ["info@x.be", "light@x.be"]},
                                 "mail-info": {"postvakken": ["info@x.be"], "firma": "HARC", "afdeling": "h-architects",
                                               "antwoord_vanuit": []},
                                 "mail-melo": {"postvakken": ["melo@x.be"], "firma": "MELO", "afdeling": "organisatie"}},
                postvak=lambda a: None, bron_uren_oud=lambda mb: None, BRON_VERS_UREN=3, mappen_van=lambda a: ["INBOX"],
                mapnamen=lambda mb: set(), koppen=lambda *a, **k: [], VERZONDEN=("Sent",))
    herstel = met_module("postvak", PV)
    try:
        _, _, prive = D._lees_mail([DAG])
    finally:
        herstel()
    assert prive == {"mch@x.be", "info@x.be", "light@x.be"}, prive
    import dagvaststelling as V
    u = {"light@x.be": {"berichten": [{"datum": f"{DAG}T10:00:00+02:00", "message_id": "<a@x>", "aan": ["Tante Mie <t@x.be>"]}]}}
    t = V.tekst(V.vaststellen(DAG, [], set(), [], {}, [], "volledig", V.mail_telling(DAG, {}, u), None, lambda a: False),
                prive_postvakken=prive)
    # MAIL-3 (T-0120): light@ wordt alleen voor verzonden gelezen; binnen is niet gelezen, geen nul
    assert "Tante Mie" not in t and "light@x.be: binnen: niet gelezen, 1 verzonden" in t, t


def test_g4_ontbrekend_postvak():
    PV = Module(wachten=lambda: {"mail-info": {"postvakken": ["info@x.be"], "firma": "HARC", "antwoord_vanuit": ["weg@x.be"]}},
                postvak=lambda a: None, bron_uren_oud=lambda mb: None, BRON_VERS_UREN=3, mappen_van=lambda a: ["INBOX"],
                mapnamen=lambda mb: set(), koppen=lambda *a, **k: [], VERZONDEN=("Sent",))
    herstel = met_module("postvak", PV)
    try:
        o, u, _ = D._lees_mail([DAG])
    finally:
        herstel()
    assert o["info@x.be"]["onvolledig"] == ["niet in de postbus"] and u["info@x.be"]["onvolledig"] == ["niet in de postbus"], (o, u)
    assert u["weg@x.be"]["onvolledig"] == ["niet in de postbus"], u
    import dagvaststelling as V
    t = V.tekst(V.vaststellen(DAG, [], set(), [], {}, [], "volledig", V.mail_telling(DAG, o, u), None, lambda a: False))
    assert "info@x.be: 0 binnen, 0 verzonden (onvolledig: niet in de postbus)" in t, t


def test_g7_vrije_archiefnaam():
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        pad = os.path.join(m, "dagboek", "2026", f"{DAG}.md")
        versies = os.path.join(m, "dagboek", "2026", "versies")
        ronde(w)
        eerste = lees(pad)
        os.makedirs(versies)
        for naam in (f"{DAG} v1.md", f"{DAG} v1 (2).md"):
            with open(os.path.join(versies, naam), "w") as f:
                f.write(f"bezet: {naam}\n")
        w.rijen.append(dict(w.rijen[0], uniek="zoom:meeting:b", start="20:00", minuten=30))
        ronde(w)
        assert lees(os.path.join(versies, f"{DAG} v1.md")) == f"bezet: {DAG} v1.md\n"
        assert lees(os.path.join(versies, f"{DAG} v1 (2).md")) == f"bezet: {DAG} v1 (2).md\n"
        assert lees(os.path.join(versies, f"{DAG} v1 (3).md")) == eerste, os.listdir(versies)


def test_f9_nachtketen_noden():
    """F9: in de nacht leest De Dagbundelaar de exit van De Zoomwacht uit nacht.json; faalde ze, dan een nood en is Zoom
    van gisteren hoogstens een ondergrens. Overdag: een nachtketen die niet liep, is een nood."""
    import ochtend
    uit = {}

    class R:
        def __init__(self):
            self.noden, self.detail = [], ""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def nood(self, t, wie="mehdi"):
            self.noden.append(t)

    oud = (D.NACHT, D.DAG_GEGEVEN, D.lees_nacht, D.vastleggen, D.bundelen, D.KETENBESTAND)
    D.KETENBESTAND = "/bestaat/niet/keten.json"
    D.vastleggen = lambda r, dagen, zoom_gelezen=None: uit.update(ok=zoom_gelezen) or ""
    D.bundelen = lambda dag=None: {"detail": "", "nood": [], "bronnen": 0}
    # Een leeg bord: zonder dit las de test op de VM de echte open noden (behoud in main) en faalde hij daar, terwijl hij
    # op de Mac en in CI slaagde omdat het bord er niet bereikbaar is (gezien 27-10-2026, sinds PR 103).
    D.ag.open_noden = lambda: []
    try:
        for nacht, nachtbestand, nood_deel, ok in (
                (True, {"start": NU.isoformat(), "einde": None, "stappen": {"zoom-wacht": {"exit": 0}}}, None, True),
                (True, {"start": NU.isoformat(), "einde": None, "stappen": {"zoom-wacht": {"exit": 124}}}, "Zoomwacht faalde", False),
                (True, {}, "buiten de nachtketen", None),
                (False, {"start": (NU - timedelta(hours=40)).isoformat()}, "nachtketen van de dagvaststelling liep niet", None),
                (False, {"start": (NU - timedelta(hours=8)).isoformat(), "einde": (NU - timedelta(hours=7)).isoformat(),
                         "stappen": {"zoom-wacht": {"exit": 0}, "dagbundelaar": {"exit": 0}}}, None, None),
                # G3: de nachtketen liep maar De Dagbundelaar faalde, of ze stopte halverwege
                (False, {"start": (NU - timedelta(hours=8)).isoformat(), "einde": (NU - timedelta(hours=7)).isoformat(),
                         "stappen": {"zoom-wacht": {"exit": 0}, "dagbundelaar": {"exit": 1}}}, "nachtketen van de dagvaststelling faalde", None),
                (False, {"start": (NU - timedelta(hours=8)).isoformat(), "einde": None,
                         "stappen": {"zoom-wacht": {"exit": 0}}}, "nachtketen van de dagvaststelling faalde", None)):
            r = R()
            D.NACHT, D.DAG_GEGEVEN, D.lees_nacht = nacht, True, (lambda b=nachtbestand: b)
            D.ag.ronde = lambda taak, **k: r
            D.main()
            assert (nood_deel is None and not r.noden) or any(nood_deel in n for n in r.noden), (nachtbestand, r.noden)
            assert uit["ok"] is ok, (nachtbestand, uit)
    finally:
        D.NACHT, D.DAG_GEGEVEN, D.lees_nacht, D.vastleggen, D.bundelen, D.KETENBESTAND = oud
        D.ag.__dict__.pop("ronde", None)
        D.ag.__dict__.pop("open_noden", None)
    assert ochtend.NACHTTAAK == "dagvaststelling"


def test_g3_zoom_van_de_ochtendketen():
    """G3: in de ochtendketen zegt keten.json of De Zoomwacht net slaagde; faalde ze, dan is Zoom een ondergrens."""
    uit = {}

    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def nood(self, t, wie="mehdi"):
            pass

    with tempfile.TemporaryDirectory() as m:
        kpad = os.path.join(m, "keten.json")
        oud = (D.NACHT, D.DAG_GEGEVEN, D.lees_nacht, D.vastleggen, D.bundelen, D.KETENBESTAND)
        D.NACHT, D.DAG_GEGEVEN, D.KETENBESTAND = False, True, kpad
        D.lees_nacht = lambda: {}
        D.vastleggen = lambda r, dagen, zoom_gelezen=None: uit.update(ok=zoom_gelezen) or ""
        D.bundelen = lambda dag=None: {"detail": "", "nood": [], "bronnen": 0}
        D.ag.ronde = lambda taak, **k: R()
        try:
            for exit_, ok in ((0, True), (124, False)):
                with open(kpad, "w") as f:
                    json.dump({"start": NU.isoformat(), "einde": None, "stappen": {"zoom-wacht": {"exit": exit_}}}, f)
                D.main()
                assert uit["ok"] is ok, (exit_, uit)
        finally:
            D.NACHT, D.DAG_GEGEVEN, D.lees_nacht, D.vastleggen, D.bundelen, D.KETENBESTAND = oud
            D.ag.__dict__.pop("ronde", None)


def test_c1_ochtend_sluit_geen_noden_als_de_vaststelling_faalt():
    """Codex-controle mailnood 2 en 3 (C1): in de ochtendketen vangt main een mislukte vaststelling op en de ronde eindigt
    gewoon. Dan blijven de noden van de vaststelling die open stonden open, naast "Dagvaststelling mislukt"; een
    bundelnood die bundelen() in dezelfde ronde niet meer gaf, sluit wel. Weet het bord niet wat open staat, dan breekt
    de ronde niet, want het ochtendbericht wacht op haar."""
    gemeld = []

    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def nood(self, t, wie="mehdi"):
            gemeld.append(t)

    def faal(r, dagen, zoom_gelezen=None):
        raise RuntimeError("mail niet gelezen en de open mailnoden op het bord onbekend")

    hot = f"{D.MAILNOOD}: mehdichegini@hotmail.com (kopie niet vers)"
    oud = (D.NACHT, D.DAG_GEGEVEN, D.lees_nacht, D.vastleggen, D.bundelen)
    D.NACHT, D.DAG_GEGEVEN = False, True
    D.lees_nacht = lambda: {"start": NU.isoformat(), "einde": NU.isoformat(),
                            "stappen": {"zoom-wacht": {"exit": 0}, "dagbundelaar": {"exit": 0}}}
    D.vastleggen = faal
    D.bundelen = lambda dag=None: {"detail": "", "nood": [], "bronnen": 0}
    D.ag.ronde = lambda taak, **k: R()
    D.ag.log = lambda *a, **k: None
    bundel = "Bron zonder dossier: een opname wacht op een toewijzing"
    try:
        D.ag.open_noden = lambda: [{"tekst": hot, "wie": "claude-code"}, {"tekst": bundel, "wie": "mehdi"},
                                   {"tekst": "WhatsApp: de WhatsApp-wacht leest de databank op de Mac nog niet (fase 2 "
                                             "van de dagvaststelling)", "wie": "claude-code"}]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            D.main()
        assert hot in gemeld and "Dagvaststelling mislukt in de ochtendronde, zie werkverslag" in gemeld, gemeld
        assert any(n.startswith("WhatsApp:") for n in gemeld), gemeld
        assert bundel not in gemeld, "de bundels liepen wel: hun opgeloste nood sluit"
        del gemeld[:]
        D.ag.open_noden = lambda: None
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            D.main()
        assert gemeld == ["Dagvaststelling mislukt in de ochtendronde, zie werkverslag"], gemeld
    finally:
        D.NACHT, D.DAG_GEGEVEN, D.lees_nacht, D.vastleggen, D.bundelen = oud
        for naam in ("ronde", "log", "open_noden"):
            D.ag.__dict__.pop(naam, None)


def test_vaststelling_noden_staan_in_de_lijst():
    """Codex-controle mailnood 3: VASTSTELLING_NODEN moet het begin van elke nood van vastleggen() kennen, anders sluit
    een mislukte ochtendvaststelling die nood toch."""
    import inspect
    import re
    bron = inspect.getsource(D.vastleggen)
    letterlijk = re.findall(r'r\.nood\(\s*"([^"]+)"', bron)
    assert len(letterlijk) >= 4, letterlijk
    for tekst in letterlijk:
        assert tekst.startswith(D.VASTSTELLING_NODEN), tekst
    constanten = set(re.findall(r'r\.nood\(\s*f?"?\{?([A-Z][A-Z_]+)', bron))
    assert constanten == {"MAIL_NIET_GELEZEN", "MAILNOOD", "LOCATIENOOD"}, constanten
    assert {getattr(D, c) for c in constanten} <= set(D.VASTSTELLING_NODEN)
    # en KETEN_NODEN het begin van elke nood die main() zelf geeft (de bundelnoden komen uit bundelen())
    eigen = re.findall(r'r\.nood\(\s*"([^"]+)"', inspect.getsource(D.main))
    assert len(eigen) >= 5, eigen
    for tekst in eigen:
        assert tekst.startswith(D.KETEN_NODEN), tekst

def _echte_ronde(nacht, open_noden, vastleggen, bundelnood=(), handmatig=False):
    """Een ronde van main() door de echte gedeelde Ronde (bord.py) met een nagebootst bord. open_noden: wat /api/nood
    geeft (None: onleesbaar). Geeft de laatste hartslag zoals die naar het bord ging."""
    gezet = []

    def call(pad, payload=None, method=None):
        if pad == f"/api/agent/{D.NAAM}/werkwijze" and payload is None:
            with open(os.path.join(os.path.dirname(D.__file__), "werkwijze", "dagbundelaar.md"), encoding="utf-8") as f:
                return {"werkwijze": f.read()}
        if pad == "/api/agents":
            return []
        if pad == "/api/nood":
            if open_noden is None:
                raise OSError("bord onbereikbaar")
            return {"nood": [dict(n, naam=D.NAAM) for n in open_noden]}
        if pad == "/agent-status":
            gezet.append(payload)
        return {}

    oud = (bord.call, D.NACHT, D.DAG_GEGEVEN, D.HANDMATIG, D.lees_nacht, D.vastleggen, D.bundelen)
    bord.call, D.NACHT, D.DAG_GEGEVEN, D.HANDMATIG = call, nacht, True, handmatig
    nu = datetime.now(timezone.utc).isoformat()
    D.lees_nacht = lambda: ({"start": nu, "stappen": {"zoom-wacht": {"exit": 0}}} if nacht else
                            {"start": nu, "einde": nu, "stappen": {"zoom-wacht": {"exit": 0}, "dagbundelaar": {"exit": 0}}})
    D.vastleggen = vastleggen
    D.bundelen = lambda dag=None: {"detail": "", "nood": [dict(n) for n in bundelnood], "bronnen": 0}
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            D.main()
    finally:
        bord.call, D.NACHT, D.DAG_GEGEVEN, D.HANDMATIG, D.lees_nacht, D.vastleggen, D.bundelen = oud
    return gezet[-1]


def test_c1_c4_echte_ronde_sluit_alleen_wat_ze_nakeek():
    """Codex-controle mailnood 4, met de echte Ronde: een mislukte ochtendvaststelling laat haar open noden open en
    sluit een opgeloste bundelnood; een geslaagde nacht sluit de vaststellingsnoden die ze niet meer geeft, maar laat de
    bundelnoden open (die kijkt alleen de ochtend na). Is het bord onleesbaar, dan gaat er geen noodlijst mee en sluit
    het bord niets; de ronde breekt niet, want het ochtendbericht wacht op haar."""
    hot = {"tekst": f"{D.MAILNOOD}: mehdichegini@hotmail.com (kopie niet vers)", "wie": "claude-code"}
    agenda = {"tekst": "Agenda niet volledig gelezen voor de dagvaststelling", "wie": "claude-code"}
    foto = {"tekst": "Foto's van gisteren wachten op validatie", "wie": "mehdi"}

    def faal(r, dagen, zoom_gelezen=None):
        raise RuntimeError("dagvaststelling niet teruggelezen")

    def goed(r, dagen, zoom_gelezen=None):
        return "1 dag(en) vastgesteld"

    def teksten(h):
        return {n["tekst"] for n in h["nood"]}

    h = _echte_ronde(False, [hot, foto], faal)
    assert teksten(h) == {hot["tekst"], "Dagvaststelling mislukt in de ochtendronde, zie werkverslag"}, h
    h = _echte_ronde(False, None, faal)
    assert h.get("nood_sluiten") is False and h["status"] in ("klaar", "waakt"), h
    assert teksten(h) == {"Dagvaststelling mislukt in de ochtendronde, zie werkverslag"}, "nieuwe noden komen er wel bij"
    h = _echte_ronde(True, [hot, agenda, foto], goed)
    assert teksten(h) == {foto["tekst"]}, h
    h = _echte_ronde(True, None, goed)
    assert h.get("nood_sluiten") is False and h["status"] in ("klaar", "waakt"), h
    h = _echte_ronde(False, [hot, foto], goed, bundelnood=[foto])
    assert teksten(h) == {foto["tekst"]}, "een geslaagde ochtend kijkt het lezen na: de oude mailnood sluit"
    assert "nood_sluiten" not in h, h
    # review 27-10-2026: wat van oudere dagen van het nachtvenster afhangt, kijkt alleen de nacht na
    locatie = {"tekst": D.LOCATIENOOD, "wie": "claude-code"}
    plafond = {"tekst": f"{D.MAILNOOD}: info@proef.test (te veel berichten)", "wie": "claude-code"}
    h = _echte_ronde(False, [locatie, plafond, agenda], goed)
    assert teksten(h) == {locatie["tekst"], plafond["tekst"]}, h
    h = _echte_ronde(True, [locatie, plafond], goed)
    assert teksten(h) == set(), "de nacht kijkt ze na en sluit ze"
    # Codex-controle mailnood 5: een ronde met de hand (--dag, --venster) kijkt niet alles na: ze sluit niets, voegt
    # nieuwe noden toe, en haar taak begint met de nachttaak, die het ochtendbericht nooit vrijgeeft
    import ochtend
    for nacht in (False, True):
        h = _echte_ronde(nacht, [hot, foto], goed, handmatig=True)
        assert teksten(h) == {hot["tekst"], foto["tekst"]}, (nacht, h)
        assert h["taak"].startswith(ochtend.NACHTTAAK), h
    h = _echte_ronde(False, [hot], faal, handmatig=True)
    assert teksten(h) == {hot["tekst"], "Dagvaststelling mislukt in de ochtendronde, zie werkverslag"}, h

def test_review_dropbox_ook_s_ochtends_over_het_venster():
    """Review 27-10-2026: de ochtend legt alleen gisteren vast, maar kijkt de Dropbox-ontvangst na over het hele
    nachtvenster. Anders sloot ze de nood "Dagboek nog niet bevestigd in Dropbox" elke werkdag zonder iets na te kijken,
    net voor het ochtendbericht; met het ontvangstbewijs gaat hij dicht."""
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        ronde(w, dagen=("2026-11-05",))                                     # de nacht schreef een oudere dag
        ronde(w, dagen=("2026-10-01",))                                     # en haalde een dag van zes weken terug in
        pad = os.path.join(m, "dagboek", "2026", "2026-11-05.md")
        oud_pad = os.path.join(m, "dagboek", "2026", "2026-10-01.md")
        _verouder(pad, 7 * 60), _verouder(oud_pad, 7 * 60)                  # DB-1: de nacht schreef ze uren geleden
        r, d = ronde(w, dagen=("2026-11-10",))                              # de ochtend: alleen gisteren
        dropbox = [n for n in r.noden if n.startswith("Dagboek nog niet bevestigd")]
        with open(os.path.join(m, "ontvangst.txt"), "w", encoding="utf-8") as f:
            f.write(f"{D._sha(lees(pad))}  ./2026/2026-11-05.md\n{D._sha(lees(oud_pad))}  ./2026/2026-10-01.md\n")
        r2, d2 = ronde(w, dagen=("2026-11-10",))
    assert dropbox and "Dropbox open: 2" in d, (r.noden, d)
    assert not [n for n in r2.noden if n.startswith("Dagboek nog niet bevestigd")] and "Dropbox open: 0" in d2, d2

def _kopie(pad, uren, vanaf):
    d = {"gemaakt": (datetime.now(timezone.utc) - timedelta(hours=uren)).isoformat(), "berichten": [
        {"map": "INBOX", "datum": f"{DAG}T08:00:00+00:00", "message_id": "<h1@x>", "van": "k@klant.test"},
        {"map": "Sent", "datum": f"{DAG}T09:00:00+00:00", "message_id": "<h2@x>", "van": "proef@hotmail.test",
         "aan": ["k@klant.test"]}]}
    if vanaf is not None:
        d["vanaf"] = vanaf
    with open(pad, "w", encoding="utf-8") as f:
        json.dump(d, f)


def test_o26_mail_kopie_vers_oud_en_venster():
    """Overleg 26-10-2026 (mailnood): de reden noemt de Mac niet meer (A); een verse kopie die de dagen niet dekt, of
    niet zegt vanaf wanneer, is onvolledig (X2), anders telde een oude dag stil nul; een verse kopie die ze dekt, is
    volledig. Elke reden heeft een vaste soort voor de nood (K2)."""
    import postvak as echt
    with tempfile.TemporaryDirectory() as m:
        pad = os.path.join(m, "koppen.json")
        PV = Module(wachten=lambda: {"mail-prive": {"postvakken": ["proef@hotmail.test"], "firma": "PRIV"}},
                    postvak=lambda a: {"adres": a, "bron": pad}, bron_uren_oud=echt.bron_uren_oud,
                    bron_vanaf=echt.bron_vanaf, momentopname=echt.momentopname, BRON_VERS_UREN=3,
                    mappen_van=lambda a: ["INBOX"], mapnamen=echt.mapnamen, VERZONDEN=echt.VERZONDEN,
                    koppen=lambda adres, m_, sinds=None, plafond=1000, inhoud=None:
                    echt.uit_bestand(pad, m_, sinds, inhoud=inhoud)[:plafond])
        herstel = met_module("postvak", PV)
        try:
            ruim = {"INBOX": "2026-09-01", "Sent": "2024-10-01"}
            uit = {}
            for naam, uren, vanaf in (("oud", 150, ruim), ("ouder", 174, ruim), ("vers", 0, ruim),
                                      ("kort", 0, {"INBOX": DAG, "Sent": "2024-10-01"}), ("zonder", 0, None)):
                _kopie(pad, uren, vanaf)
                o, u, _ = D._lees_mail([DAG])
                uit[naam] = (o["proef@hotmail.test"], u["proef@hotmail.test"])
        finally:
            herstel()
    o, u = uit["oud"]
    # lens 26-10 (4): de reden is vast, want ze telt mee in de hash van het dagbestand; de uren staan in het detail
    assert o["onvolledig"] == u["onvolledig"] == ["kopie ouder dan 3 uur"], (o, u)
    assert o["details"] == u["details"] == ["kopie 150 uur oud"], (o, u)
    assert o["soorten"] == u["soorten"] == ["kopie niet vers"], (o, u)
    assert uit["ouder"][0]["onvolledig"] == o["onvolledig"] and uit["ouder"][0]["details"] == ["kopie 174 uur oud"]
    o, u = uit["vers"]
    assert not o["onvolledig"] and not u["onvolledig"] and len(o["berichten"]) == len(u["berichten"]) == 1, (o, u)
    assert o["dekking"]["vanaf"] == "2026-09-01" and u["dekking"]["vanaf"] == "2024-10-01", (o, u)
    m = D.V.mail_telling(DAG, {"h": o}, {"h": u})
    assert not m["onvolledig"] and m["binnen"] == m["verzonden"] == 1, m
    o, u = uit["kort"]
    assert not o["onvolledig"] and o["dekking"]["vanaf"] == DAG, "de dekking toetst mail_telling per dag"
    m = D.V.mail_telling(DAG, {"h": o}, {"h": u})["postvakken"]["h"]
    assert m["onvolledig"] == ["kopie dekt deze dag niet"], m
    o, u = uit["zonder"]
    assert o["onvolledig"] == ["kopie van INBOX zegt niet vanaf wanneer"], o
    assert u["onvolledig"] == ["kopie van Sent zegt niet vanaf wanneer"], u
    assert o["soorten"] == ["kopie zegt niet vanaf wanneer"] and o["dekking"]["vanaf"] == "", o
    assert not any("Mac" in r for x in uit.values() for p in x for r in p["onvolledig"])


def test_o26_mailnood_per_postvak_stabiel_en_uren_in_het_logboek():
    """Overleg 26-10-2026 (K2, X3, C): een nood per postvak en soort, zonder getal, gelijk van ronde tot ronde ook als de
    uren veranderen of een ander postvak bijkomt; faalt het hele lezen, dan een vaste nood zonder fouttype. De volle
    reden met de uren staat in het logboek; een ronde die alles leest, meldt geen mailnood."""
    import subprocess
    hot = "mehdichegini@hotmail.com"

    def mail(uren, ook_info=False):
        def lees(dagen_):
            reden = {"berichten": [], "onvolledig": [f"kopie {uren} uur oud"], "soorten": ["kopie niet vers"]}
            o = {hot: json.loads(json.dumps(reden)), "info@h-architects.be": {"berichten": [], "onvolledig": []}}
            if ook_info:
                o["info@h-architects.be"] = {"berichten": [], "onvolledig": ["INBOX niet leesbaar (TimeoutError)"],
                                             "soorten": ["map niet leesbaar"]}
            return o, {hot: json.loads(json.dumps(reden))}, {hot}
        return lees

    def faal(fout):
        def lees(dagen_):
            raise fout
        return lees

    def mailnoden(r):
        return [n for n in r.noden if n.startswith("Mail")]

    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        log1, log2, log3 = [], [], []
        r1, _ = ronde(w, mail=mail(150), logboek=log1)
        r2, _ = ronde(w, mail=mail(151, ook_info=True), logboek=log2)
        r3, _ = ronde(w, mail=faal(RuntimeError("mailkoppen eindigde met 1")), logboek=log3)
        r4, _ = ronde(w, mail=faal(subprocess.TimeoutExpired("python", 900)))
        r5, _ = ronde(w)
    vast = f"Mail niet volledig gelezen voor de dagvaststelling: {hot} (kopie niet vers)"
    assert mailnoden(r1) == [vast], r1.noden
    assert vast in mailnoden(r2) and len(mailnoden(r2)) == 2, r2.noden
    assert "Mail niet volledig gelezen voor de dagvaststelling: info@h-architects.be (map niet leesbaar)" in mailnoden(r2)
    assert not any(c.isdigit() for n in mailnoden(r1) + mailnoden(r2) for c in n), "N10: geen getal in de nood"
    assert mailnoden(r3) == mailnoden(r4) == ["Mail niet gelezen voor de dagvaststelling"], (r3.noden, r4.noden)
    assert not mailnoden(r5), r5.noden
    assert ("mail", "bron", f"{hot} ontvangen onvolledig: kopie 150 uur oud") in log1, log1
    assert ("mail", "bron", f"{hot} verzonden onvolledig: kopie 151 uur oud") in log2, log2
    assert ("mail", "fout", "mail niet gelezen (RuntimeError)") in log3, log3


def test_c1_totale_mailfout_sluit_geen_postvaknood():
    """Codex-controle mailnood 1 (C1), overleg 26-10-2026: faalt het hele lezen, dan blijven de open mailnoden open (ook
    de algemene van voor 26-10), want deze ronde zag die postvakken niet; andere noden niet. Weet het bord niet welke
    open staan, dan breekt de ronde als laatste stap, nadat de dagen al vastliggen, zodat noden_bij_breuk niets sluit."""
    hot = f"{D.MAILNOOD}: mehdichegini@hotmail.com (kopie niet vers)"
    open_ = [{"tekst": hot, "wie": "claude-code"}, {"tekst": D.MAILNOOD, "wie": "claude-code"},
             {"tekst": "Agenda niet volledig gelezen voor de dagvaststelling", "wie": "claude-code"}]

    def faal(dagen_):
        raise RuntimeError("mailkoppen eindigde met 1")

    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        r1, _ = ronde(w, mail=faal, open_noden=open_)
        try:
            ronde(w, mail=faal, open_noden=None)
            gebroken = None
        except RuntimeError as e:
            gebroken = str(e)
        dag = os.path.exists(os.path.join(m, "dagboek", DAG[:4], f"{DAG}.md"))
    assert [n for n in r1.noden if n.startswith("Mail")] == [D.MAIL_NIET_GELEZEN, hot, D.MAILNOOD], r1.noden
    assert "Agenda niet volledig gelezen voor de dagvaststelling" not in r1.noden, "alleen mailnoden blijven staan"
    assert gebroken and "mailnoden" in gebroken, gebroken
    assert dag, "de dag ligt vast voor de ronde breekt"


def test_c2_kopie_uit_een_lezing():
    """Codex-controle mailnood 1 (C2): ouderdom, begindatum en koppen komen uit dezelfde lezing. Vervangt de server de
    kopie tijdens het lezen door een die de dag niet meer dekt, dan telt de ronde de versie die ze eerst las, volledig;
    een kopie die niet te lezen is, geeft een vaste reden en geen tweede lezing."""
    import postvak as echt
    with tempfile.TemporaryDirectory() as m:
        pad = os.path.join(m, "koppen.json")
        lezingen = []

        def foto(mb):
            d = echt.momentopname(mb)
            lezingen.append(d is not None)
            with open(pad, "w", encoding="utf-8") as f:      # de server vervangt het bestand meteen daarna
                json.dump({"gemaakt": datetime.now(timezone.utc).isoformat(), "vanaf": {"INBOX": "2026-11-01"},
                           "berichten": []}, f)
            return d

        def koppen(adres, m_, sinds=None, plafond=1000, inhoud=None):
            assert inhoud is not None, "geen tweede lezing van het bestand"
            return echt.uit_bestand(pad, m_, sinds, inhoud=inhoud)[:plafond]

        PV = Module(wachten=lambda: {"mail-prive": {"postvakken": ["proef@hotmail.test"], "firma": "PRIV"}},
                    postvak=lambda a: {"adres": a, "bron": pad}, bron_uren_oud=echt.bron_uren_oud,
                    bron_vanaf=echt.bron_vanaf, momentopname=foto, BRON_VERS_UREN=3, mappen_van=lambda a: ["INBOX"],
                    mapnamen=echt.mapnamen, VERZONDEN=echt.VERZONDEN, koppen=koppen)
        herstel = met_module("postvak", PV)
        try:
            _kopie(pad, 0, {"INBOX": "2026-09-01", "Sent": "2024-10-01"})
            o, u, _ = D._lees_mail([DAG])
            os.remove(pad)
            o2, u2, _ = D._lees_mail([DAG])
        finally:
            herstel()
    o, u = o["proef@hotmail.test"], u["proef@hotmail.test"]
    assert not o["onvolledig"] and not u["onvolledig"] and len(o["berichten"]) == len(u["berichten"]) == 1, (o, u)
    o2, u2 = o2["proef@hotmail.test"], u2["proef@hotmail.test"]
    assert o2["onvolledig"] == u2["onvolledig"] == ["kopie onleesbaar"], (o2, u2)
    assert o2["soorten"] == ["kopie onleesbaar"] and not o2["berichten"], o2
    assert lezingen == [True, False], lezingen


def test_c3_geen_eigen_mapnaam_in_de_reden():
    """Codex-controle mailnood 1 (C3): een eigen map kan een klantnaam dragen. De reden, die naar het dagbestand en het
    logboek gaat, noemt dan "een eigen map"; de vaste mappen (INBOX, Sent) blijven bij naam."""
    import postvak as echt

    def koppen(adres, m_, sinds=None, plafond=1000, inhoud=None):
        if m_ in ("INBOX.Klant Proefbedrijf", "INBOX.Klant Derde"):
            raise TimeoutError("traag")
        if m_ == "INBOX.Klant Testzaak":
            return [{"datum": f"{DAG}T08:00:00+00:00"}] * plafond
        if m_ == "INBOX":
            raise ConnectionError("weg")
        return []

    PV = Module(wachten=lambda: {"mail-info": {"postvakken": ["info@proef.test"], "firma": "HA"}},
                postvak=lambda a: {"adres": a}, mapnamen=lambda mb: {"inbox", "sent"}, VERZONDEN=echt.VERZONDEN,
                mappen_van=lambda a: ["INBOX", "INBOX.Klant Proefbedrijf", "INBOX.Klant Testzaak", "INBOX.Klant Derde"],
                koppen=koppen)
    herstel = met_module("postvak", PV)
    try:
        o, _, _ = D._lees_mail([DAG])
    finally:
        herstel()
    o = o["info@proef.test"]
    assert o["onvolledig"] == ["INBOX niet leesbaar", "een eigen map niet leesbaar",
                               f"een eigen map: meer dan {D.PLAFOND} berichten"], o
    # review 27-10-2026: twee eigen mappen die falen, geven een reden (anders een andere hash bij elk aantal), twee details
    assert o["details"] == ["INBOX: ConnectionError", "een eigen map: TimeoutError", "een eigen map: TimeoutError"], o
    assert not any("Klant" in r for r in o["onvolledig"] + o["details"]), o


def test_k5_hotmailkopie_dekt_de_nachtelijke_inhaal():
    """Overleg 26-10-2026 (K5): de nacht haalt tot INHAAL dagen terug in en leest vanaf de dag ervoor. De hotmailkopie,
    elk uur om :25 UTC ververst, moet die dagen dekken, ook op een avond waarop de UTC-dag en de Brusselse dag
    verschillen; anders blijft hotmail voor elke ingehaalde dag ouder dan de kopie onvolledig."""
    import hotmail_server
    from datetime import date
    for nacht in (datetime(2026, 10, 26, 23, 30, tzinfo=timezone.utc), datetime(2026, 7, 14, 22, 30, tzinfo=timezone.utc)):
        kopie = nacht - timedelta(minutes=5)
        vanaf = (kopie.date() - timedelta(days=hotmail_server.BINNEN_DAGEN)).isoformat()   # zoals hotmail_lezer
        oudste = date.fromisoformat(D.V.gisteren(nacht)) - timedelta(days=D.INHAAL - 1)    # zoals inhaaldagen
        sinds = (oudste - timedelta(days=1)).isoformat()                                  # zoals _lees_mail
        assert vanaf <= sinds, (nacht, vanaf, sinds)


def test_lens5_9_dekking_per_dag():
    """Lenzen 26-10-2026 (5 en 9): de dekking van een kopie geldt per dag. Een dag na de begindatum is gedekt, ook als
    een andere dag van dezelfde ronde dat niet is; de kopie zoekt op UTC-datum, dus de dag ervoor moet erin staan. Een
    kopie gemaakt voor het einde van de Brusselse dag mist het laatste stuk van die dag, stil; ook dat is onvolledig."""
    V = D.V

    def postvak(vanaf, gemaakt):
        return {"h": {"berichten": [], "onvolledig": [], "dekking": {"vanaf": vanaf, "gemaakt": gemaakt}}}

    nacht = "2026-10-22T23:25:00+00:00"                      # 01:25 in Brussel (zomeruur), na het einde van 22-10
    assert not V.mail_telling("2026-10-22", postvak("2026-10-20", nacht), {})["onvolledig"]
    assert not V.mail_telling("2026-10-21", postvak("2026-10-20", nacht), {})["onvolledig"]
    assert V.mail_telling("2026-10-20", postvak("2026-10-20", nacht), {})["postvakken"]["h"]["onvolledig"] == [
        "kopie dekt deze dag niet"]
    vroeg = "2026-10-22T21:30:00+00:00"                      # 23:30 in Brussel: het laatste half uur van 22-10 ontbreekt
    assert V.mail_telling("2026-10-22", postvak("2026-10-01", vroeg), {})["postvakken"]["h"]["onvolledig"] == [
        "kopie van voor het einde van de dag"]
    assert not V.mail_telling("2026-10-21", postvak("2026-10-01", vroeg), {})["onvolledig"]
    winter = "2026-10-26T23:25:00+00:00"                     # 00:25 in Brussel na de nacht van 26-10 (winteruur)
    assert not V.mail_telling("2026-10-26", postvak("2026-08-25", winter), {})["onvolledig"]
    assert not V.mail_telling("2026-10-26", {"h": {"berichten": [], "onvolledig": []}}, {})["onvolledig"], "geen kopie"


def test_lens4_8_oude_kopie_geeft_geen_nieuwe_versies_en_dekking_geen_nood():
    """Lenzen 26-10-2026 (4 en 8): blijft een kopie oud (bv. een verlopen token), dan krijgt een dag geen nieuwe versie
    per nacht, want de reden in het dagbestand is vast; de uren staan in het logboek. Een dag buiten de dekking van een
    kopie die zegt vanaf wanneer, is zo ontworpen: onvolledig in het dagbestand, maar geen nood die niemand kan oplossen."""
    hot = "proef@hotmail.test"

    def oud(uren):
        def lees(dagen_):
            p = {"berichten": [], "onvolledig": ["kopie ouder dan 3 uur"], "soorten": ["kopie niet vers"],
                 "details": [f"kopie {uren} uur oud"]}
            return {hot: json.loads(json.dumps(p))}, {hot: json.loads(json.dumps(p))}, {hot}
        return lees

    def buiten(dagen_):
        p = {"berichten": [], "onvolledig": [], "dekking": {"vanaf": "2026-11-01", "gemaakt": "2026-11-09T23:25:00+00:00"}}
        return {hot: json.loads(json.dumps(p))}, {hot: json.loads(json.dumps(p))}, {hot}

    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        log = []
        _, d1 = ronde(w, mail=oud(150))
        _, d2 = ronde(w, mail=oud(174), logboek=log)
        r3, _ = ronde(w, mail=buiten)
        tekst = lees(os.path.join(m, "dagboek", DAG[:4], f"{DAG}.md"))
    assert "1 nieuw of herzien" in d1 and "0 nieuw of herzien" in d2, (d1, d2)
    assert ("mail", "bron", f"{hot} ontvangen onvolledig: kopie ouder dan 3 uur (kopie 174 uur oud)") in log, log
    assert "kopie dekt deze dag niet" in tekst, tekst
    assert not [n for n in r3.noden if n.startswith("Mail")], r3.noden


def test_fase2_telling_naast_het_dagbestand():
    """Fase 2 (driehoeksoverleg 27-10-2026, Q2, X2, K5): naast het dagbestand de telling van de dag, met dezelfde versie
    en zonder naam; een tweede ronde laat ze staan; een dag waarvan het bestand niet veranderde maar de telling ontbreekt
    (van voor fase 2), krijgt ze alsnog."""
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        tpad = os.path.join(m, "dagboek", "2026", f"{DAG}.json")
        ronde(w)
        t1 = lees(tpad)
        x = json.loads(t1)
        assert x["dag"] == DAG and x["vastgesteld"] is True and x["dagversie"] == 1, x
        assert x["afspraken"]["totaal"] == 1 and x["gesprekken"]["aantal"] == 1, x
        for naam in ("Pieter", "Claes", "Geheime", "Ruben", "Proefdorp"):
            assert naam not in t1, f"K5: {naam} in de telling"
        _, detail = ronde(w)
        assert lees(tpad) == t1 and "0 nieuw of herzien" in detail, detail
        os.remove(tpad)
        _, detail = ronde(w)
        assert lees(tpad) == t1 and "0 nieuw of herzien" in detail, "zonder nieuwe versie toch de telling"
        w.rijen.append(dict(w.rijen[0], uniek="zoom:meeting:b", start="20:00", minuten=30))
        ronde(w)
        assert json.loads(lees(tpad))["dagversie"] == 2, "de telling volgt de versie van het dagbestand"


def _verouder(pad, minuten):
    """Het dagbestand alsof zijn huidige versie zoveel minuten geleden geschreven werd."""
    t = (datetime.now(timezone.utc) - timedelta(minutes=minuten)).timestamp()
    os.utime(pad, (t, t))


def _bewijs(m, *teksten_per_dag):
    with open(os.path.join(m, "ontvangst.txt"), "w", encoding="utf-8") as f:
        for dag, tekst in teksten_per_dag:
            f.write(f"{D._sha(tekst)}  ./{dag[:4]}/{dag}.md\n")


def test_db1_dropbox_termijn_per_bestandsversie():
    """DB-1 (T-0118, T-0120): een dag telt pas als niet in Dropbox als zijn huidige versie ouder is dan twee syncrondes
    (DROPBOX_TERMIJN) en het ontvangstbewijs een andere sha256 heeft. Tot 01-11-2026 vergeleek de nachtronde een dag die ze
    net herschreef met het bewijs van de vorige versie, en opende zo na elke nacht een vals alarm; in het weekend bleef
    het open, want daar is geen ochtendronde. De leeftijd van het ontvangstbewijs telt niet: de Mac schrijft het ook als
    de rsync van het dagboek faalde."""
    assert D.DROPBOX_TERMIJN == timedelta(minutes=75), D.DROPBOX_TERMIJN
    dropbox = lambda r: [n for n in r.noden if n.startswith("Dagboek nog niet bevestigd")]  # noqa: E731
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        pad = os.path.join(m, "dagboek", "2026", f"{DAG}.md")
        r, d = ronde(w)
        assert not dropbox(r) and "Dropbox open: 0" in d, "een versie die deze ronde schreef, kijkt de volgende na"
        _bewijs(m, (DAG, lees(pad)))
        _verouder(pad, 180)
        # Nacht (vrijdag): een nagekomen gesprek geeft een nieuwe versie; het bewijs is nog van de vorige
        w.rijen.append(dict(w.rijen[0], uniek="zoom:meeting:b", start="20:00", minuten=30))
        r, d = ronde(w)
        assert "versie 2" in lees(pad) and not dropbox(r) and "Dropbox open: 0" in d, (r.noden, d)
        # Werkdagochtend: de versie is ouder dan twee syncrondes en het bewijs is er niet: nood open
        _verouder(pad, 74)
        r, d = ronde(w, dagen=("2026-11-10",))
        assert not dropbox(r), "74 min is nog binnen de termijn"
        _verouder(pad, 76)
        r, d = ronde(w, dagen=("2026-11-10",))
        assert dropbox(r) and "Dropbox open: 1" in d, (r.noden, d)
        # Weekend: de Mac-sync liep (bewijs van versie 2); de nacht van zaterdag herschrijft de dag weer: geen nood
        _bewijs(m, (DAG, lees(pad)))
        w.rijen.append(dict(w.rijen[0], uniek="zoom:meeting:c", start="21:00", minuten=10))
        r, d = ronde(w)
        assert "versie 3" in lees(pad) and not dropbox(r), r.noden
        # Nacht van zondag: de Mac-sync liep weer (bewijs van versie 3), niets veranderd: geen nood
        _bewijs(m, (DAG, lees(pad)))
        _verouder(pad, 24 * 60)
        r, d = ronde(w)
        assert not dropbox(r) and "Dropbox open: 0" in d, (r.noden, d)
        # Liep de Mac-sync niet meer (bewijs bleef van versie 2), dan opent de nood na de termijn
        with open(os.path.join(m, "dagboek", "2026", "versies", f"{DAG} v2.md"), encoding="utf-8") as f:
            _bewijs(m, (DAG, f.read()))
        r, d = ronde(w)
        assert dropbox(r) and "Dropbox open: 1" in d, (r.noden, d)
        # Een vers ontvangstbewijs bewijst niets als zijn sha256 niet klopt (de rsync kan gefaald hebben)
        os.utime(os.path.join(m, "ontvangst.txt"))
        r, _ = ronde(w)
        assert dropbox(r), r.noden


def test_mail4_reservesleutel_voor_rijen_zonder_message_id():
    """MAIL-4 (T-0120): mailbericht kreeg pas op 19-10-2026 een kolom message_id; een oudere rij heeft ze leeg, maar draagt
    de sleutel van de wacht in uniek (postvak:Message-ID, of postvak:uid zonder Message-ID). De dagvaststelling nam alleen
    rijen met message_id, en telde zo 12-10 tot 19-10 te weinig (16-10 mch@: 6 in plaats van 12). Nu geldt een vaste
    reservesleutel; een oude rij wordt niet aangevuld. Dezelfde mail uit IMAP en uit mailbericht telt precies een keer."""
    pv = "proef@proef.test"
    imap = [{"datum": f"{DAG}T08:00:00+02:00", "message_id": "<a1@x>", "uid": 11, "map_": "INBOX"},   # nog in de map
            {"datum": f"{DAG}T09:00:00+02:00", "message_id": "", "uid": 12, "map_": "INBOX"},         # zonder Message-ID
            # Codex-toets 1: een ander bericht zonder Message-ID met dezelfde uid in een andere gelezen map
            {"datum": f"{DAG}T09:30:00+02:00", "message_id": "", "uid": 12, "map_": "INBOX.Werf"}]
    rijen = [{"uniek": f"{pv}:<a1@x>", "postvak": pv, "map": "INBOX", "message_id": "", "datum": f"{DAG}T08:00:00+02:00",
              "soort": "koud"},
             {"uniek": f"{pv}:12", "postvak": pv, "map": "INBOX", "message_id": "", "datum": f"{DAG}T09:00:00+02:00",
              "soort": "gewoon"},
             # weggesorteerd naar een map die de wachten niet lezen: alleen in mailbericht
             {"uniek": f"{pv}:<a3@x>", "postvak": pv, "map": "INBOX", "message_id": "", "datum": f"{DAG}T10:00:00+02:00",
              "soort": "melding"},
             {"uniek": f"{pv}:13", "postvak": pv, "map": "INBOX", "message_id": "", "datum": f"{DAG}T11:00:00+02:00",
              "soort": "melding"},
             # een nieuwe rij met message_id, ook nog in IMAP onder dezelfde sleutel
             {"uniek": f"{pv}:<a1@x>", "postvak": pv, "map": "INBOX", "message_id": "<a1@x>", "datum": f"{DAG}T08:00:00+02:00",
              "soort": "koud"}]
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        w.mailberichten = rijen
        ronde(w, mail=lambda dagen_: ({pv: {"berichten": [dict(k) for k in imap], "onvolledig": []}}, {}, set()))
        t = lees(os.path.join(m, "dagboek", "2026", f"{DAG}.md"))
    assert "message_id, '') != ''" not in w.mailsql and "uniek" in w.mailsql and "map" in w.mailsql, w.mailsql
    assert f"  - {pv}: 5 binnen (1 gewoon, 1 koud, 2 melding)" in t, t
    assert "- mail: 5 binnen" in t, t
    # de vaste sleutel zelf: Message-ID, anders uit uniek, anders de uid; een uid met postvak en map
    S = D.V.mail_sleutel
    assert S(pv, {"message_id": "<a1@x>", "uid": 5}) == "<a1@x>" == S(pv, {"uniek": f"{pv}:<a1@x>", "message_id": ""})
    assert S(pv, {"uid": 12, "map_": "INBOX"}) == S(pv, {"uniek": f"{pv}:12", "map_": "INBOX"}) == f"{pv}:INBOX:12"
    assert S(pv, {"uid": 12, "map_": "INBOX"}) != S(pv, {"uid": 12, "map_": "INBOX.Werf"}), "een uid is uniek per map"
    assert S(pv, {"uid": 12}) != S("ander@proef.test", {"uid": 12}), "en per postvak"
    assert S(pv, {"uid": ""}) is None and S(pv, {"uniek": "ander:12"}) is None


def test_mail4_de_vaststelling_leest_de_map_mee():
    """MAIL-4, Codex-toets 1: _lees_mail geeft elke kop de map waarin ze gelezen werd, zodat twee berichten zonder
    Message-ID met dezelfde uid in twee gelezen mappen twee keer tellen."""
    PV = Module(wachten=lambda: {"mail-info": {"postvakken": ["info@x.be"], "firma": "HARC", "antwoord_vanuit": []}},
                postvak=lambda a: {"adres": a}, bron_uren_oud=lambda mb: None, BRON_VERS_UREN=3,
                mappen_van=lambda a: ["INBOX", "INBOX.Werf"], mapnamen=lambda mb: {"inbox", "inbox.werf", "sent"},
                koppen=lambda a, m, **k: [{"datum": f"{DAG}T09:00:00+02:00", "message_id": "", "uid": 12, "van": "k@proef.test"}],
                VERZONDEN=("Sent",))
    herstel = met_module("postvak", PV)
    try:
        o, u, _ = D._lees_mail([DAG])
    finally:
        herstel()
    assert [k["map_"] for k in o["info@x.be"]["berichten"]] == ["INBOX", "INBOX.Werf"], o
    m = D.V.mail_telling(DAG, o, u)
    assert m["postvakken"]["info@x.be"]["binnen"] == 2, m


class HartRonde:
    """ag.ronde zonder bord: de taak, de noden en het detail na de ronde."""

    def __init__(self, taak):
        self.taak, self.noden, self.detail, self.noden_onbekend = taak, [], "", False

    def __enter__(self):
        return self

    def __exit__(self, *fout):
        return False

    def nood(self, tekst, wie="mehdi"):
        self.noden.append(tekst)

    def bron(self, naam, inhoud):
        pass


def _hand(w, argv, **k):
    """main() met de opties van argv (zoals de VM ze zou krijgen), in de wereld w; geeft de ronde of de fout van de
    opties. bundelen() en de lezing van de nachtketen mogen niet lopen."""
    rondes, geroepen = [], []
    namen = ("DAG", "DAG_GEGEVEN", "VENSTER", "WEEK", "NACHT", "ALLEEN_VASTSTELLEN", "HANDMATIG", "bundelen", "lees_nacht")
    oud = {n: getattr(D, n) for n in namen}
    D.DAG, D.DAG_GEGEVEN, D.VENSTER, D.WEEK, D.NACHT, D.ALLEEN_VASTSTELLEN, D.HANDMATIG = D.opties(argv, nu=NU)
    D.bundelen = lambda dag=None: geroepen.append("bundelen") or {"detail": "", "nood": [], "bronnen": 0}
    D.lees_nacht = lambda: geroepen.append("nacht.json") or {}
    D.ag.ronde = lambda taak, **kw: rondes.append(HartRonde(taak)) or rondes[-1]
    try:
        ronde(w, doe=D.main, **k)
    finally:
        for n, v in oud.items():
            setattr(D, n, v)
        D.ag.__dict__.pop("ronde", None)
    return rondes[-1], geroepen


def test_vol1_alleen_vaststellen_is_de_inhaalweg():
    """VOL-1 (T-0120, overleg X7 en X9): de inhaalweg van de dagbundel. --alleen-vaststellen stelt vast zonder bundelen() en
    zonder de controle van de nachtketen, dus zonder nood 'buiten de nachtketen'; het is een ronde met de hand, die geen
    noden sluit en het ochtendbericht niet vrijgeeft. --dag samen met --venster weigert de runner: tot 01-11-2026 won
    --dag dan stil (WISPR-2), en --venster zonder --nacht bundelde ook gisteren (DB-4, AG-1). Bouwen mag, draaien niet."""
    import ochtend
    for fout in (["--dag", "2026-10-05", "--venster", "32"], ["--nacht", "--alleen-vaststellen"],
                 ["--alleen-vaststellen", "--dag", "2026-10-05", "--venster", "32"]):
        try:
            D.opties(fout, nu=NU)
            raise AssertionError(f"{fout} moet geweigerd worden")
        except ValueError as e:
            assert "samen" in str(e), e
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        jaar = os.path.join(m, "dagboek", "2026")
        os.makedirs(jaar)
        with open(os.path.join(jaar, "2026-10-20.md"), "w", encoding="utf-8") as f:
            f.write("# Dag 2026-10-20 vastgesteld\n\noude versie\n")
        r, geroepen = _hand(w, ["--alleen-vaststellen", "--venster", "32"], dagen=())
        assert not geroepen, f"geen bundelen() en geen nachtketen: {geroepen}"
        assert r.taak == f"{ochtend.NACHTTAAK} met de hand", r.taak
        assert not [n for n in r.noden if "nachtketen" in n], r.noden
        tellingen = sorted(f for f in os.listdir(jaar) if f.endswith(".json"))
        assert len(tellingen) == 32 and tellingen[-1] == "2026-11-10.json" and tellingen[0] == "2026-10-10.json", tellingen
        assert os.path.exists(os.path.join(jaar, "versies", "2026-10-20 v1.md")), "de vorige versie blijft bewaard"
        assert "32 dag(en) vastgesteld" in r.detail, r.detail
        # --alleen-vaststellen --dag: precies die dag
        r, geroepen = _hand(w, ["--alleen-vaststellen", "--dag", "2026-09-30"], dagen=())
        assert not geroepen and os.path.exists(os.path.join(m, "dagboek", "2026", "2026-09-30.json")), geroepen
    # de runner zelf weigert de verkeerde combinatie voor hij iets leest of schrijft
    p = subprocess.run([sys.executable, os.path.join(RUNNER, "dagbundelaar.py"), "--dag", "2026-10-05", "--venster", "32"],
                       capture_output=True, text=True, timeout=60,
                       env=dict(os.environ, HOME=tempfile.gettempdir(), MIJNAGENTS_URL="http://127.0.0.1:9"))
    assert p.returncode == 2 and "samen" in p.stderr, (p.returncode, p.stderr[-300:])


def test_vol4_eigen_werk_en_gezondheid_standaard_uit():
    """VOL-4 (T-0120, overleg X2): het blok Eigen werk en gezondheid staat standaard uit, tot het bestaande ja op T-0079
    rij 7. Vlag uit: geen lezing, geen sleutel eigen in de .json van de dag en geen regels in de .md. Vlag aan: het blok
    staat er, zodat deze test de fout ook ziet."""
    assert D.EIGEN_AAN is False, "de vlag staat standaard uit"
    gelezen = []

    def lees_eigen(eerste):
        gelezen.append(eerste)
        return lambda dag: {"wispr": {"dictaten": 3, "woorden": 40, "seconden": 30}, "websites": None, "youtube": None,
                            "gezondheid": ["Stappen: 8234", "Rusthartslag: 58"]}

    oud = D.lees_eigen
    D.lees_eigen = lees_eigen
    try:
        with tempfile.TemporaryDirectory() as m:
            ronde(Wereld(m))
            md = lees(os.path.join(m, "dagboek", "2026", f"{DAG}.md"))
            x = json.loads(lees(os.path.join(m, "dagboek", "2026", f"{DAG}.json")))
        assert not gelezen, "vlag uit: de gegevens worden niet eens gelezen"
        assert "eigen" not in x and "Eigen werk" not in md and "Stappen" not in md and "Wispr" not in md, md
        D.EIGEN_AAN = True
        with tempfile.TemporaryDirectory() as m:
            ronde(Wereld(m))
            md = lees(os.path.join(m, "dagboek", "2026", f"{DAG}.md"))
        assert gelezen and "## Eigen werk en gezondheid" in md and "Stappen: 8234" in md, md
    finally:
        D.lees_eigen, D.EIGEN_AAN = oud, False


def test_fase2_telling_niet_teruggelezen():
    """X2: de dag komt pas op het bord als de telling teruggelezen is; anders faalt de ronde."""
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        echt = D._lees
        D._lees = lambda pad: "kapot" if str(pad).endswith(".json") and "/dagboek/" in str(pad) else echt(pad)
        try:
            ronde(w)
            raise AssertionError("een telling die niet terug te lezen is, moet de ronde laten falen")
        except RuntimeError as e:
            assert "niet teruggelezen" in str(e) and "telling" in str(e), e
        finally:
            D._lees = echt
        assert f"vaststelling:{DAG}" not in w.items, "geen item op het bord zonder teruggelezen telling"


def _week_wereld(m, w, gevangen, vervals=None):
    """De bronnen van weekoverzicht_maken: de telling van DAG uit een echte ronde, de agenda van de wereld, kern met een
    firmanaam, en een bord dat het weekitem bewaart."""
    import organisatie
    ronde(w)
    oud = (D.DAGBOEK, D.lees_agenda, organisatie.firmas, bord.call)
    D.DAGBOEK = os.path.join(m, "dagboek")
    D.lees_agenda = lambda dagen_: ({DAG: list(w.afspraken)}, set(), lambda a: "[LA]" in a["titel"])
    organisatie.firmas = lambda *a, **k: [{"code": "UNAB", "naam": "UNABO"}]

    def klaarzet(items):
        for it in items:
            assert it["voor"] == "mehdi" and it["soort"] == "weekoverzicht" and it.get("revisie") is True, it
            gevangen[it["uniek"]] = dict(it)
        return {"nieuw": len(items)}

    def call(pad, payload=None, method=None):
        assert pad.startswith("/api/klaarzet?uniek=weekoverzicht"), pad
        it = gevangen.get("weekoverzicht:2026-W43")
        return {"items": [dict(it, inhoud=vervals) if (it and vervals) else it] if it else []}

    D.ag.klaarzet = klaarzet
    bord.call = call
    return oud


def test_fase2_weekoverzicht_maken():
    """Q3, K2, K5: het weekoverzicht telt de dagtellingen op, zet bestand en item klaar met dezelfde inhoud, zonder naam;
    een tweede keer zonder verandering geeft geen nieuw tijdstip; een bord dat iets anders toont, laat het falen."""
    import organisatie
    with tempfile.TemporaryDirectory() as m:
        w, gevangen = Wereld(m), {}
        oud = _week_wereld(m, w, gevangen)
        try:
            detail = D.weekoverzicht_maken("2026-W43", datetime(2026, 10, 27, 0, 30, tzinfo=timezone.utc))
            jpad = os.path.join(m, "dagboek", "2026", "week", "2026-W43.json")
            inhoud = lees(jpad)
            x = json.loads(inhoud)
            assert detail == "week 2026-W43: 1 van 7 dagen vastgesteld", detail
            assert gevangen["weekoverzicht:2026-W43"]["inhoud"] == inhoud and x["week"] == "2026-W43", "bord = bestand"
            assert [d["dag"] for d in x["dagen"] if d["vastgesteld"]] == [DAG], x["dagen"]
            assert x["planning"]["afspraken"] == 1 and x["planning"]["minuten"] == 60, x["planning"]
            assert "datum" not in x and "start" not in x, "de dagenpagina leest dit niet als een dag"
            md = lees(os.path.join(m, "dagboek", "2026", "week", "2026-W43.md"))
            for naam in ("Pieter", "Claes", "Geheime", "Ruben", "Proefdorp"):
                assert naam not in inhoud and naam not in md, f"K5: {naam} in het weekoverzicht"
            D.weekoverzicht_maken("2026-W43", datetime(2026, 10, 28, 0, 30, tzinfo=timezone.utc))
            assert lees(jpad) == inhoud, "niets veranderd: geen nieuw tijdstip"
        finally:
            D.DAGBOEK, D.lees_agenda, organisatie.firmas, bord.call = oud
            D.ag.__dict__.pop("klaarzet", None)
    with tempfile.TemporaryDirectory() as m:
        w, gevangen = Wereld(m), {}
        oud = _week_wereld(m, w, gevangen, vervals="{}")
        try:
            D.weekoverzicht_maken("2026-W43", datetime(2026, 10, 27, 0, 30, tzinfo=timezone.utc))
            raise AssertionError("een bord dat iets anders toont, moet het weekoverzicht laten falen")
        except RuntimeError as e:
            assert "niet teruggelezen: bord" in str(e), e
        finally:
            D.DAGBOEK, D.lees_agenda, organisatie.firmas, bord.call = oud
            D.ag.__dict__.pop("klaarzet", None)


def test_fase2_weeknood_per_ronde():
    """K3: de nacht maakt de week in een eigen blok; lukt het, dan sluit de weeknood, mislukt het, dan staat ze open en
    breekt de nacht niet. De ochtend laat de weeknood open (ze kijkt de week niet na). Met de hand (--week) maakt alleen
    die week, zonder vaststelling, en sluit niets."""
    gemeld, gemaakt, vastgelegd = [], [], []

    class R:
        detail = ""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def nood(self, t, wie="mehdi"):
            gemeld.append(t)

    def faal(week, nu=None):
        gemaakt.append(week)
        raise RuntimeError("kapot")

    oud = (D.NACHT, D.DAG_GEGEVEN, D.VENSTER, D.WEEK, D.HANDMATIG, D.lees_nacht, D.vastleggen, D.bundelen,
           D.inhaaldagen, D.weekoverzicht_maken, D.KETENBESTAND, D.weken_voor_de_nacht, D.bundeldagen, D.WEEK_TIJDSLIMIET)
    D.KETENBESTAND = "/bestaat/niet/keten.json"
    D.bundeldagen = lambda nu: [D.V.gisteren(nu)]           # DB-3: zonder bord alleen gisteren
    D.weken_voor_de_nacht = lambda nu: ["2026-W43"]
    D.lees_nacht = lambda: {"start": NU.isoformat(), "einde": None, "stappen": {"zoom-wacht": {"exit": 0}}}
    D.vastleggen = lambda r, dagen, zoom_gelezen=None: vastgelegd.append(len(dagen)) or ""
    D.bundelen = lambda dag=None: {"detail": "", "nood": [], "bronnen": 0}
    D.inhaaldagen = lambda nu, dagen: []
    D.ag.ronde = lambda taak, **k: R()
    D.ag.log = lambda *a, **k: None
    D.ag.open_noden = lambda: [{"tekst": D.WEEKNOOD, "wie": "claude-code"}]
    try:
        D.NACHT, D.DAG_GEGEVEN, D.VENSTER, D.WEEK, D.HANDMATIG = True, False, None, None, False
        D.weekoverzicht_maken = lambda week, nu=None: gemaakt.append(week) or f"week {week}"
        D.main()
        assert gemaakt == ["2026-W43"] and D.WEEKNOOD not in gemeld, (gemaakt, gemeld)
        del gemeld[:], gemaakt[:]
        D.weekoverzicht_maken = faal
        D.main()
        assert gemaakt and gemeld.count(D.WEEKNOOD) == 1, ("mislukt: de weeknood staat open", gemeld)
        del gemeld[:], gemaakt[:]
        # Codex-controle fase 2, ronde 3 (K3): een vastgelopen weekstap stopt op haar eigen grens, de nacht loopt door
        import time
        D.WEEK_TIJDSLIMIET = 0.2
        D.weekoverzicht_maken = lambda week, nu=None: gemaakt.append(week) or time.sleep(3) or "te laat"
        begin = time.monotonic()
        D.main()
        assert time.monotonic() - begin < 2 and gemeld.count(D.WEEKNOOD) == 1, ("vastgelopen week: nood, nacht loopt door", gemeld)
        D.WEEK_TIJDSLIMIET = oud[-1]
        del gemeld[:], gemaakt[:]
        D.NACHT = False
        D.lees_nacht = lambda: {"start": NU.isoformat(), "einde": NU.isoformat(),
                                "stappen": {"zoom-wacht": {"exit": 0}, "dagbundelaar": {"exit": 0}}}
        D.main()
        assert not gemaakt and D.WEEKNOOD in gemeld, ("de ochtend laat de weeknood open en maakt geen week", gemeld)
        del gemeld[:], gemaakt[:], vastgelegd[:]
        D.WEEK, D.HANDMATIG = "2026-W43", True
        D.weekoverzicht_maken = lambda week, nu=None: gemaakt.append(week) or f"week {week}"
        D.main()
        assert gemaakt == ["2026-W43"] and not vastgelegd and D.WEEKNOOD in gemeld, (gemaakt, vastgelegd, gemeld)
        # met de hand mislukt: geen algemene weeknood (Codex-controle fase 2, ronde 3)
        del gemeld[:], gemaakt[:]
        D.ag.open_noden = lambda: []
        D.weekoverzicht_maken = faal
        with redirect_stderr(io.StringIO()):
            D.main()
        assert gemaakt == ["2026-W43"] and D.WEEKNOOD not in gemeld, gemeld
    finally:
        (D.NACHT, D.DAG_GEGEVEN, D.VENSTER, D.WEEK, D.HANDMATIG, D.lees_nacht, D.vastleggen, D.bundelen,
         D.inhaaldagen, D.weekoverzicht_maken, D.KETENBESTAND, D.weken_voor_de_nacht, D.bundeldagen, D.WEEK_TIJDSLIMIET) = oud
        for naam in ("ronde", "log", "open_noden"):
            D.ag.__dict__.pop(naam, None)


def test_fase2_dagbestand_teruggelezen_voor_het_bord():
    """X2 (Codex-controle fase 2, ronde 3): ook het dagbestand is teruggelezen voor het item naar het bord gaat."""
    with tempfile.TemporaryDirectory() as m:
        w = Wereld(m)
        echt = D._lees
        D._lees = lambda pad: "kapot" if str(pad).endswith(f"{DAG}.md") and "/dagboek/" in str(pad) else echt(pad)
        try:
            ronde(w)
            raise AssertionError("een dagbestand dat niet terug te lezen is, moet de ronde laten falen")
        except RuntimeError as e:
            assert "niet teruggelezen" in str(e) and "bestand" in str(e), e
        finally:
            D._lees = echt
        assert f"vaststelling:{DAG}" not in w.items, "geen item op het bord zonder teruggelezen dagbestand"


def test_fase2_weken_voor_de_nacht():
    """Codex-controle fase 2, ronde 3: de nacht maakt de laatst afgesloten week, en de week ervoor zolang die ontbreekt."""
    nu = datetime(2026, 11, 2, 0, 30, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as m:
        oud = D.DAGBOEK
        D.DAGBOEK = os.path.join(m, "dagboek")
        try:
            assert D.weken_voor_de_nacht(nu) == ["2026-W43", "2026-W44"], D.weken_voor_de_nacht(nu)
            os.makedirs(os.path.join(m, "dagboek", "2026", "week"))
            with open(os.path.join(m, "dagboek", "2026", "week", "2026-W43.json"), "w") as f:
                f.write("{}")
            assert D.weken_voor_de_nacht(nu) == ["2026-W44"], D.weken_voor_de_nacht(nu)
        finally:
            D.DAGBOEK = oud


def test_fase2_tijdslimiet_gaat_door_een_gewone_foutafhandeling():
    """Codex-controle fase 2, ronde 4 (K3): loopt de weekstap vast in een stuk met een gewone foutafhandeling (de
    firmanamen uit kern), dan stopt ze toch op haar grens en keert ze nooit terug als geslaagd."""
    import organisatie
    import signal
    import time
    with tempfile.TemporaryDirectory() as m:
        w, gevangen = Wereld(m), {}
        oud = _week_wereld(m, w, gevangen)
        organisatie.firmas = lambda *a, **k: time.sleep(3) or []
        vorige = signal.getsignal(signal.SIGALRM)
        begin = time.monotonic()
        try:
            D.met_tijdslimiet(D.weekoverzicht_maken, 0.2, "2026-W43", datetime(2026, 10, 27, 0, 30, tzinfo=timezone.utc))
            raise AssertionError("de tijdslimiet werd ingeslikt: de week keerde terug als geslaagd")
        except D.WeekTijdOp:
            pass
        finally:
            D.DAGBOEK, D.lees_agenda, organisatie.firmas, bord.call = oud
            D.ag.__dict__.pop("klaarzet", None)
        assert time.monotonic() - begin < 2, "de grens hield de week niet tegen"
        assert signal.getsignal(signal.SIGALRM) == vorige and signal.getitimer(signal.ITIMER_REAL)[0] == 0
        assert "weekoverzicht:2026-W43" not in gevangen, "een week die op haar grens stopte, staat niet op het bord"


def test_fase2_alarm_tijdens_het_uitzetten():
    """Codex-controle fase 2, ronde 5: gaat het alarm af net tijdens het uitzetten, dan komt de vorige
    alarmafhandeling toch terug."""
    import signal
    vorige = signal.getsignal(signal.SIGALRM)
    echt = signal.setitimer

    def setitimer(soort, seconden, *a):
        if seconden == 0:
            echt(soort, 0)
            raise D.WeekTijdOp("alarm tijdens het uitzetten")
        return echt(soort, seconden, *a)

    signal.setitimer = setitimer
    try:
        D.met_tijdslimiet(lambda: "klaar", 5)
        raise AssertionError("het nagebootste alarm moest doorkomen")
    except D.WeekTijdOp:
        pass
    finally:
        signal.setitimer = echt
    assert signal.getsignal(signal.SIGALRM) == vorige, "de vorige alarmafhandeling kwam niet terug"


if __name__ == "__main__":
    import traceback
    goed = fout = 0
    for naam, f in sorted(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                f()
                goed += 1
                print("   geslaagd ", naam)
            except Exception:  # noqa: BLE001
                fout += 1
                print("   MISLUKT  ", naam)
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)

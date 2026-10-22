"""Grendels op De Bode na het ontwerp regie-zoom v1.2 (fase 3; fase 5 met besluiten via WhatsApp is niet gebouwd).

- T61 tot T68 (B3, I6, G4): doel_van herkent "Naam, vraag" op een vaste regel, met de 40 labels van het bord. De
  uitkomst hangt niet af van de volgorde van de namen; een naam die op meer agents past, gaat naar De Regisseur.
- T69 (B4, J4): alleen ochtend_sturen verstuurt een ochtendbericht; melding_groep slaat het over en laatste_id schuift
  nooit voorbij een ochtendbericht dat nog niet weg is.
- T70 tot T75 (B5, M6, L8): het ochtendbericht met de regel Gebundeld binnen 900 tekens, een verkeerd item, de terugval
  om 11:00 aan beide kanten van 25-10, de bundelstand tegenover 'uit', alarm meteen, de avondbundel.
- T76 (FR-154, X4): een onleesbare werkwijze houdt het bellen niet tegen; de berichten wachten.
- T77: het zaad draagt de vaste regel BUNDELEN en de code leest de stand uit de werkwijze (RZ3-02); werkwijze 2.9 in de
  strikte vorm, met de regels van RZ4-03.
- RZ3-02 (Codex RZ3-herstelcontrole): de stand van BUNDELEN volgt uit de werkwijze op het bord. Werkwijze 2.5 zonder de
  regel geeft 'uit' en houdt niets vast; met de regel 'ochtend-avond'; terug naar 'uit' gaat langs de slotbundel.
- T99 (X4): de noden van het bellen en het alarm gaan als begin_noden mee, ook als de ronde stopt.
- T100 (H1, L2): geen vraag- of antwoordtekst in het werkverslag of de export; een antwoord nooit via Zoom-chat.
- REG-03 (R6): een lang antwoord gaat ingekort tot 800 tekens naar WhatsApp, met de verwijzing naar het bord en de regel
  Gelezen, met dezelfde regel als De Regisseur (ochtend.whatsapp_kort).
- BOD-1 tot BOD-5 (tegenlezing fase 3): de overgang naar de bundelstand en terug naar 'uit' verliest niets, een verkeerd
  of wachtend ochtendbericht houdt geen oproep tegen, een bundel noemt een item een keer, en een voorstel dat na het
  opstellen van het ochtendbericht bijkwam, blijft nieuw.
- RZ2-04 (Codex RZ2-bouwcontrole, patroon FR-179): stopt het proces na de aanvaarding van een ochtendbericht, terugval of
  avondbundel en voor de stand op schijf staat, dan gaat het niet nog eens weg; het verzendspoor zegt 'bezig', en dat
  wordt een nood voor claude-code. Een mislukte verzending blijft herkansbaar, zonder schrijfbaar spoor geen verzending.
- RZ4-03 (Codex RZ4-herstelcontrole): laatste_id schuift pas op als elk item erboven meegenomen is, verstuurd of in een
  bundel. Bij de omschakeling begint de bundel voor het oudste item dat nog niet weg is, ook als dat ouder is dan 24 uur;
  wat in geen bundel valt, gaat los; een item onder een volle pagina wordt opgehaald (tot_id), of de stand blijft staan.
  Tegenproef op RZ4-03: ook de lopende bundel wordt onder de pagina aangevuld; lukt dat niet, dan zegt het vaste moment
  "onbekend of meer" en schuift bundel_vanaf niet op.

Geen netwerk en geen sleutels: het bord, WhatsApp, Telegram, Zoom-chat, het bellen (BELLEN_UIT=1) en de klok zijn
nagebootst, de stand staat in een tijdelijke map, en de databank van het bord komt uit init_db van mijnagents/app.py als
Flask er is (in de CI altijd). Synthetische namen en nummers.
Draaien: python3 mijnagents-runner/tests/test_bode_regie.py
"""
import io
import json
import os
import random
import re
import shutil
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.parse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone

os.environ["BELLEN_UIT"] = "1"      # een test belt nooit echt (FR-55)
HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
REPO = os.path.dirname(RUNNER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import bode as B  # noqa: E402
import bord  # noqa: E402
import bord_export as E  # noqa: E402
import whatsapp as W  # noqa: E402

MAP = tempfile.mkdtemp(prefix="bode-regie-")
B.STAAT = os.path.join(MAP, "bode.json")
B.bellen.ROOSTER = os.path.join(MAP, "belrooster.json")
W.TELLER = os.path.join(MAP, "wa_sjablonen.json")
UTC = timezone.utc
ECHT = {n: getattr(B.bellen, n) for n in ("afspraken_bellen", "alarm_bellen", "afspraak_bellen_beschikbaar",
                                          "belafspraak_actueel", "bel_afspraak")}
WERKWIJZE = open(os.path.join(RUNNER, "werkwijze", "bode.md"), encoding="utf-8").read()
# RZ3-02 (besluit van de regie, 22-10-2026): de stand van BUNDELEN volgt uit de werkwijze op het bord. De vaste regel in
# het zaad zet de bundelstand aan; zonder die regel is de stand 'uit'. Een ronde met stand 'uit' krijgt dus het zaad
# zonder de regel, en een omschakeling is een andere werkwijze op het bord, zoals wanneer Mehdi een versie terugzet.
REGEL = "BUNDELEN: ochtend-avond"
WERKWIJZE_UIT = WERKWIJZE.replace("\n" + REGEL + "\n", "\n", 1)
# Zoals werkwijze 2.5 van 15-10-2026 (alleen de vorm): van voor het bundelen, zonder sectie over de stand van BUNDELEN.
WERKWIJZE_25 = ("# Werkwijze van De Bode (Regie)\n\nVersie 2.5 (15-10-2026, proefkopie van de vorm).\n\n"
                "## Wat ik doe, in deze volgorde\n\n1. Elke minuut lees ik het bord en stuur ik wat voor Mehdi klaarstaat.\n\n"
                "## Wat ik nooit doe\n\n- Iets versturen naar iemand anders dan Mehdi.\n- Vaker sturen dan de regels hierboven.\n\n"
                "## Wat Mehdi beslist\n\n- Welk kanaal.\n- Wat een alarm is dat 's nachts mag doorkomen.\n")

# De 40 actieve agents van het bord, gemeten op 21-10-2026 (naam en label; geen persoonsgegevens).
LABELS = {
    "contracten-agent": "De Contractmaker", "regisseur": "De Regisseur", "agenda-wacht": "De Agendawacht",
    "fathom-wacht": "De Fathomwacht", "plaud-wacht": "De Plaudwacht", "dagbundelaar": "De Dagbundelaar",
    "locatie-wacht": "De Locatiewacht", "ontwikkelaar": "De Ontwikkelaar", "icloud-wacht": "De iCloud-wacht",
    "levenscoach": "De Levenscoach", "gezondheid-wacht": "De Gezondheidswacht", "bode": "De Bode",
    "mail-mch": "De Mailwacht mch@", "mail-prive": "De Mailwacht hotmail", "zoom-wacht": "De Zoomwacht",
    "whatsapp-wacht": "De WhatsApp-wacht", "belwacht": "De Belwacht", "communicatie-bundelaar": "De Communicatiebundelaar",
    "archivaris": "De Archivaris", "wispr-wacht": "De Wispr-wacht", "licentiewacht": "De Licentiewacht",
    "werfverslag-voorbereider": "Werfverslag voorbereider", "werfverslag-schrijver": "Werfverslag schrijver",
    "commandocentrum": "Het Commandocentrum", "veiligheidscoordinatie-verslag": "Veiligheidscoördinatie verslag",
    "plaatsbeschrijving-verslag": "Plaatsbeschrijving verslag", "barsten-scheuren-verslag": "Barsten en scheuren verslag",
    "calendly-wacht": "De Calendlywacht", "normwacht": "De Normwacht", "werfverslag-dashboard": "Werfverslag dashboard",
    "mail-info-harc": "De Mailwacht info@ H-Architects", "mail-hinv": "De Mailwacht info@ H-Invest",
    "mail-regisseur": "De Mailregisseur", "wagenpark-wacht": "De Wagenparkwacht", "mail-melo": "De Mailwacht Melodie",
    "contactwacht": "De Contactwacht", "felix-wacht": "FelixArchief en Percelenpas Antwerpen",
    "benamingen-wacht": "Benamingenwacht", "mappen-wacht": "Mappenwacht", "tekenaar": "De Tekenaar",
}
MAILWACHTEN = ["mail-hinv", "mail-info-harc", "mail-mch", "mail-melo", "mail-prive"]


def http(code):
    return urllib.error.HTTPError("http://127.0.0.1:3022/api/agent/bode/werkwijze", code, "proef", None, None)


# ------------------------------------------------------------------------------------------- de databank ---
def bord_db(pad):
    """Een lege databank zoals het bord ze maakt (init_db van mijnagents/app.py)."""
    try:
        os.environ.setdefault("AGENTS_DB", os.path.join(MAP, "app-start.db"))
        sys.path.insert(0, os.path.join(REPO, "mijnagents"))
        import app  # noqa: PLC0415
        app.DB_PAD = pad
        app.init_db()
    except ImportError:
        # Lokaal zonder Flask: het schema uit de tekst van init_db zelf, plus de latere kolom werkwijze van agent.
        # In de CI is Flask er altijd (regie-grendels.yml installeert mijnagents/requirements.txt).
        assert not os.environ.get("CI"), "Flask ontbreekt in de CI: deze toets hoort de databank uit init_db te bouwen"
        bron = open(os.path.join(REPO, "mijnagents", "app.py"), encoding="utf-8").read()
        sql = re.search(r'def init_db\(\):.*?executescript\(\s*"""(.*?)"""', bron, re.S).group(1)
        c = sqlite3.connect(pad)
        c.executescript(sql)
        c.execute("ALTER TABLE agent ADD COLUMN werkwijze TEXT DEFAULT ''")
        c.commit()
        c.close()


SJABLOON_DB = os.path.join(MAP, "sjabloon.db")
with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
    bord_db(SJABLOON_DB)


# -------------------------------------------------------------------------------------------- de wereld ---
class Wereld:
    """Het bord, WhatsApp, Telegram, Zoom-chat, het alarm en de klok voor rondes van De Bode, zonder netwerk."""

    teller = 0

    def __init__(self, moment, stand="ochtend-avond", staat=None, werkwijze=WERKWIJZE, voorstellen=()):
        Wereld.teller += 1
        self.moment = moment
        self.items = []
        self.noden = []                       # /api/nood; None: het bord weet het niet
        # RZ3-02: de stand komt uit de werkwijze op het bord; 'uit' is het zaad zonder de vaste regel
        self.werkwijze = WERKWIJZE_UIT if stand == "uit" and werkwijze is WERKWIJZE else werkwijze
        self.gesprekken = {}
        self.gestuurd, self.hartslagen, self.wa, self.zoom, self.alarmen = [], [], [], [], []
        self.wa_fout = None                   # f(tekst, kop, voorrang) -> uitzondering of None
        self.wa_binnen = []
        self.oppakken_faalt = 0
        self.tot_id_negeren, self.tot_id_fout = False, False
        self.db = os.path.join(MAP, f"bord-{Wereld.teller}.db")
        shutil.copy(SJABLOON_DB, self.db)
        self.zet_voorstellen(voorstellen)
        for pad in (B.STAAT, B.STAAT + ".lock", B.belspoor(), B.verzendspoor()):
            if os.path.exists(pad):
                os.remove(pad)
        if staat is not None:
            with open(B.STAAT, "w") as f:
                json.dump(staat, f)
        bord.BORD_DB = self.db
        B.bord.call = self.call
        B.nu = lambda: self.moment
        B.whatsapp.stuur = self.wa_stuur
        B.whatsapp.binnen = lambda sinds=0: [m for m in self.wa_binnen if m["id"] > sinds]
        B.whatsapp.instellingen = lambda: {"sjabloon": "agent_melding"}
        B.whatsapp.venster = lambda ins=None: (False, None)
        B.TG_TOKEN, B.TG_CHAT = "proef", "1"
        B.tg = lambda methode, **p: {"result": []}
        B.stuur_telegram = self.telegram
        B.stuur_zoom = self.zoom_chat
        B.bellen.alarm_bellen = self.alarm
        B.bellen.afspraken_bellen = ECHT["afspraken_bellen"]

    # -------------------------------------------------------------- de bronnen
    def zet_voorstellen(self, voorstellen):
        c = sqlite3.connect(self.db)
        c.execute("DELETE FROM voorstel")
        c.executemany("INSERT INTO voorstel(id, naam, actie, status, ts) VALUES(?,?,?,?,?)",
                      [(i, naam, f"Proefvoorstel {i}", "open", "2026-10-20T08:00:00+00:00") for i, naam in voorstellen])
        c.commit()
        c.close()

    def zet(self, kid, soort, titel, van="normwacht", voor="mehdi", uniek="", inhoud="", ts=None, status="klaar"):
        self.items.append({"id": kid, "van": van, "voor": voor, "soort": soort, "sleutel": "", "titel": titel,
                           "inhoud": inhoud if isinstance(inhoud, str) else json.dumps(inhoud, ensure_ascii=False),
                           "verwijzing": "", "uniek": uniek, "status": status,
                           "ts": ts or self.moment.astimezone(UTC).isoformat(), "opgepakt_door": ""})

    def item(self, kid):
        return next(it for it in self.items if it["id"] == kid)

    # -------------------------------------------------------------- het bord
    def call(self, pad, payload=None, method=None):
        self.gestuurd.append((pad, payload))
        u = urllib.parse.urlparse(pad)
        q = dict(urllib.parse.parse_qsl(u.query))
        p = u.path
        if p == "/agent-status":
            self.hartslagen.append(payload)
            return {"ok": True}
        if p == "/api/logboek" or p.endswith("/kennis"):
            return {"ok": True}
        if p == "/api/agent/bode/werkwijze":
            if isinstance(self.werkwijze, Exception):
                raise self.werkwijze
            return {"werkwijze": self.werkwijze}
        if p == "/api/agents":
            return []
        if p == "/api/nood":
            if self.noden is None:
                raise OSError("noden nagebootst onbekend")
            return {"nood": list(self.noden)}
        if p == "/api/overzicht":
            return {"agents": [{"naam": n, "label": lab, "open_voorstellen": 0} for n, lab in LABELS.items()]}
        m = re.match(r"^/api/klaarzet/(\d+)/opgepakt$", p)
        if m:
            if self.oppakken_faalt:
                self.oppakken_faalt -= 1
                raise OSError("oppakken nagebootst onbereikbaar")
            it = self.item(int(m.group(1)))
            it["status"], it["opgepakt_door"] = "opgepakt", payload.get("door", "")
            return {"ok": True}
        if p == "/api/klaarzet" and payload is None:
            if self.tot_id_fout and q.get("tot_id"):
                raise OSError("terugbladeren nagebootst onbereikbaar")
            # tot_id zoals mijnagents/app.py (terugbladeren, sinds 18-10-2026); tot_id_negeren: een bord van daarvoor
            tot = int(q["tot_id"]) if (q.get("tot_id") or "").isdigit() and not self.tot_id_negeren else None
            rijen = [it for it in self.items
                     if (not q.get("voor") or it["voor"] == q["voor"]) and (not q.get("uniek") or it["uniek"] == q["uniek"])
                     and (not q.get("soort") or it["soort"] == q["soort"]) and (tot is None or it["id"] < tot)
                     and (q.get("status", "klaar") == "alle" or it["status"] == q.get("status", "klaar"))]
            rijen.sort(key=lambda it: -it["id"])
            return {"items": [dict(it) for it in rijen[:min(int(q.get("n", 100)), 500)]]}
        if p == "/api/gesprek" and payload:
            gid = 700 + sum(1 for k in self.gesprekken if k < 707)
            self.gesprekken[gid] = {"id": gid, "aan": payload["aan"], "tekst": payload["tekst"], "van": payload["van"],
                                    "status": "open", "antwoord": ""}
            return {"ok": True, "id": gid, "aan": payload["aan"]}
        m = re.match(r"^/api/gesprek/(\d+)$", p)
        if m:
            return {"gesprek": self.gesprekken[int(m.group(1))]}
        raise AssertionError(f"onverwachte bordaanroep {pad}")

    # -------------------------------------------------------------- de kanalen
    def wa_stuur(self, tekst, kop="je agents", voorrang=False):
        if self.wa_fout:
            fout = self.wa_fout(tekst, kop, voorrang)
            if fout:
                raise fout
        self.wa.append({"tekst": tekst, "kop": kop, "voorrang": voorrang})
        return "whatsapp-sjabloon"

    def telegram(self, tekst):
        raise RuntimeError("Telegram nagebootst uit")

    def zoom_chat(self, tekst):
        self.zoom.append(tekst)
        raise RuntimeError("Zoom-chat nagebootst uit")

    def alarm(self, staat, alarmen, log=None, spoor=None, nood=None):
        if alarmen:
            self.alarmen.append([it["id"] for it in alarmen])
            return "alarm gebeld"
        return ""

    # -------------------------------------------------------------- een ronde
    def ronde(self, moment=None):
        if moment is not None:
            self.moment = moment
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            B.main(droog=False)
        return self.staat()

    def staat(self):
        try:
            return json.load(open(B.STAAT))
        except (OSError, ValueError):
            return None

    def laatste(self):
        return self.hartslagen[-1] if self.hartslagen else {}

    def noodteksten(self):
        return [n["tekst"] for n in (self.laatste().get("nood") or [])]

    def logregels(self):
        return [r for pad, p in self.gestuurd if pad == "/api/logboek" for r in p["regels"]]


def utc(*a):
    return datetime(*a, tzinfo=UTC)


def ochtend_inhoud(tekst):
    return {"tekst": tekst, "punten": [
        {"nr": 1, "soort": "mail", "ref": "mail", "agent": "mail-regisseur", "link": "/mail"},
        {"nr": 2, "soort": "voorstel", "ref": 900, "agent": "ontwikkelaar", "link": "/agent/ontwikkelaar",
         "vingerafdruk": "abc123def456"}],
        "verder": "Verder: 12 voorstellen en 45 noden open", "bronnen": {}, "onbekend": []}


def ochtend_tekst(lengte=None):
    """Een ochtendbericht zoals De Regisseur het maakt; met lengte precies zoveel tekens in de vorm van een
    sjabloonparameter (de 720 van I1)."""
    regels = ["1. Twee dringende mails wachten op antwoord. Volgende stap: openen. mijnagents.globaal.be/mail",
              "2. Nieuw voorstel 900 van De Ontwikkelaar. Volgende stap: beslissen. mijnagents.globaal.be/agent/ontwikkelaar",
              "Verder: 12 voorstellen en 45 noden open. Alles op mijnagents.globaal.be"]
    tekst = "\n".join(regels)
    if lengte:
        tekst += " " + "x" * (lengte - len(W.plat(tekst, None)) - 1)
        assert len(W.plat(tekst, None)) == lengte, len(W.plat(tekst, None))
    return tekst


# ------------------------------------------------------------------------------------------ T61 tot T68 ---
GEVALLEN = [
    "Zoomwacht, wat is er vanochtend afgesproken?", "De Zoomwacht: wat zag je?", "zoom-wacht, wat zag je?",
    "Zoom wacht, wat zag je?", "@zoomwacht: wat zag je?", "Het Commandocentrum: x", "Mailregisseur, wat staat er open?",
    "Regisseur, wat staat er open?", "Mailwacht, wat kwam er binnen?", "Mailwacht hotmail: wat kwam er binnen?",
    "Mailwacht mch@, wat kwam er binnen?", "Mail: wat staat er open?", "Werfverslag, hoe ver sta je?", "Zoemwacht, x",
    "Noomwacht, x", "Ik denk, dat het goed is", "Ja, doe maar", "Goedemorgen, hoe gaat het", "Contractmaker: wat deed je",
    "Contractmaker - wat deed je", "Zoomwacht vandaag: wat is er?", "Mailwacht info@, wat kwam er binnen?",
]


def test_t61_zoomwacht_met_komma():
    assert B.doel_van("Zoomwacht, wat is er vanochtend afgesproken?", LABELS) == \
        ("zoom-wacht", "wat is er vanochtend afgesproken?")


def test_t62_vier_schrijfwijzen_en_het_lidwoord():
    for tekst in ("De Zoomwacht: wat zag je?", "zoom-wacht, wat zag je?", "Zoom wacht, wat zag je?", "@zoomwacht: wat zag je?"):
        assert B.doel_van(tekst, LABELS) == ("zoom-wacht", "wat zag je?"), (tekst, B.doel_van(tekst, LABELS))
    assert B.doel_van("Het Commandocentrum: x", LABELS) == ("commandocentrum", "x")


def test_t63_mailregisseur_en_regisseur():
    assert B.doel_van("Mailregisseur, wat staat er open?", LABELS) == ("mail-regisseur", "wat staat er open?")
    assert B.doel_van("Regisseur, wat staat er open?", LABELS) == ("regisseur", "wat staat er open?")


def test_t64_mailwacht_past_op_vijf():
    tekst = "Mailwacht, wat kwam er binnen?"
    aan, vraag, kandidaten = B.doel_en_kandidaten(tekst, LABELS)
    assert (aan, vraag) == ("regisseur", tekst), (aan, vraag)
    assert kandidaten == MAILWACHTEN and "mail-regisseur" not in kandidaten, kandidaten
    zin = B.bevestiging(tekst, LABELS)
    assert "Mailwacht past op 5 agents" in zin and "De Regisseur kijkt ernaar" in zin, zin


def test_t65_volle_naam_of_de_regisseur():
    assert B.doel_van("Mailwacht hotmail: wat kwam er binnen?", LABELS) == ("mail-prive", "wat kwam er binnen?")
    assert B.doel_van("Mailwacht mch@, wat kwam er binnen?", LABELS) == ("mail-mch", "wat kwam er binnen?")
    assert B.doel_van("Mail: wat staat er open?", LABELS) == ("regisseur", "Mail: wat staat er open?")
    assert B.doel_van("Werfverslag, hoe ver sta je?", LABELS) == ("regisseur", "Werfverslag, hoe ver sta je?")
    assert B.doel_van("Mailwacht info@, wat kwam er binnen?", LABELS)[0] == "regisseur", "info@ past op twee mailwachten"


def test_t66_bijna_match_alleen_bij_precies_een():
    assert B.doel_van("Zoemwacht, x", LABELS) == ("zoom-wacht", "x"), "spraakherkenning: een bijna-match"
    aan, vraag, kandidaten = B.doel_en_kandidaten("Noomwacht, x", LABELS)
    assert (aan, vraag) == ("regisseur", "Noomwacht, x") and kandidaten == ["normwacht", "zoom-wacht"], kandidaten
    # G4: een kop van minder dan vijf tekens krijgt geen bijna-match, ook niet als ze boven de grens zou liggen
    proef = {"proef-x": "Pluto"}
    assert B.doel_van("Plto, x", proef) == ("regisseur", "Plto, x")
    assert B.doel_van("Plutto, x", proef) == ("proef-x", "x")
    assert B.doel_van("Pluto, x", proef) == ("proef-x", "x")


def test_t67_geen_naam_en_de_oude_vorm():
    for tekst in ("Ik denk, dat het goed is", "Ja, doe maar", "Goedemorgen, hoe gaat het"):
        assert B.doel_van(tekst, LABELS) == ("regisseur", tekst), (tekst, B.doel_van(tekst, LABELS))
    assert B.doel_van("Contractmaker: wat deed je", LABELS) == ("contracten-agent", "wat deed je")
    assert B.doel_van("Contractmaker - wat deed je", LABELS) == ("contracten-agent", "wat deed je")
    assert B.doel_van("Zoomwacht, x", {}) == ("regisseur", "Zoomwacht, x"), "een lege namenlijst geeft geen fout"
    assert B.doel_van("Zoomwacht vandaag: wat is er?", LABELS) == ("zoom-wacht", "vandaag: wat is er?"), \
        "wat van de kop overblijft, komt vooraan de vraag"


def test_t68_volgorde_van_de_namen_maakt_niet_uit():
    basis = [(B.doel_en_kandidaten(g, LABELS), B.bevestiging(g, LABELS)) for g in GEVALLEN]
    rij = list(LABELS.items())
    rnd = random.Random(20261021)
    volgordes = [list(reversed(rij))]
    for _ in range(50):
        rnd.shuffle(rij)
        volgordes.append(list(rij))
    for volgorde in volgordes:
        namen = dict(volgorde)
        uit = [(B.doel_en_kandidaten(g, namen), B.bevestiging(g, namen)) for g in GEVALLEN]
        assert uit == basis, [(g, a, b) for g, a, b in zip(GEVALLEN, uit, basis) if a != b][:3]


# ------------------------------------------------------------------------------------------------- T69 ---
def t69_wereld(moment):
    w = Wereld(moment, stand="uit", staat={"laatste_id": 9, "voorstel_hoogste": 0, "ochtend": {}, "avond": {}})
    w.zet(10, "signaal", "Proefsignaal tien")
    w.zet(11, "ochtendbericht", "Ochtendbericht do 22-10, 2 beslissingen", van="regisseur", uniek="ochtendbericht:2026-10-22",
          inhoud=ochtend_inhoud(ochtend_tekst()))
    w.zet(12, "signaal", "Proefsignaal twaalf")
    return w


def test_t69_ochtendbericht_alleen_en_met_voorrang():
    """J4 (gaat voor op B4): ochtend_sturen stuurt 11 apart, met de titel als kop en met voorrang; de groep van 10 en
    12 bevat het nooit, en laatste_id eindigt op 12."""
    w = t69_wereld(utc(2026, 10, 22, 8, 0))
    staat = w.ronde()
    ochtend = [m for m in w.wa if m["kop"] == "Ochtendbericht do 22-10, 2 beslissingen"]
    assert len(ochtend) == 1 and ochtend[0]["voorrang"] and ochtend[0]["tekst"] == ochtend_tekst(), w.wa
    groep = [m for m in w.wa if m not in ochtend]
    assert len(groep) == 1 and "Proefsignaal tien" in groep[0]["tekst"] and "Proefsignaal twaalf" in groep[0]["tekst"], groep
    assert "Twee dringende mails" not in groep[0]["tekst"] and not groep[0]["voorrang"], groep
    assert staat["laatste_id"] == 12 and w.item(11)["status"] == "opgepakt" and w.item(11)["opgepakt_door"] == "bode", staat
    w.ronde()
    assert len(w.wa) == 2, f"een tweede ronde stuurt niets: {w.wa[2:]}"


def test_t69_mislukt_het_ochtendbericht_dan_blijft_laatste_id_ervoor():
    w = t69_wereld(utc(2026, 10, 22, 8, 0))
    w.wa_fout = lambda tekst, kop, voorrang: RuntimeError("Meta nagebootst 500") if voorrang else None
    staat = w.ronde()
    assert [("Proefsignaal tien" in m["tekst"], "Proefsignaal twaalf" in m["tekst"]) for m in w.wa] == [(True, False)], w.wa
    assert staat["laatste_id"] == 10 and w.item(11)["status"] == "klaar", (staat, w.item(11))
    assert not (staat.get("ochtend", {}).get("2026-10-22") or {}).get("verzonden"), staat
    w.wa_fout = None
    staat = w.ronde()
    assert [m["kop"] for m in w.wa[1:]] == ["Ochtendbericht do 22-10, 2 beslissingen", "je agents"], w.wa
    assert "Proefsignaal twaalf" in w.wa[2]["tekst"] and "Proefsignaal tien" not in w.wa[2]["tekst"], w.wa
    assert staat["laatste_id"] == 12 and w.item(11)["status"] == "opgepakt", staat


def test_t69_melding_groep_slaat_een_ochtendbericht_altijd_over():
    items = [{"id": 10, "soort": "signaal", "titel": "a", "van": "x"},
             {"id": 11, "soort": "ochtendbericht", "titel": "b", "van": "regisseur", "uniek": "ochtendbericht:2026-10-22",
              "status": "klaar"},
             {"id": 12, "soort": "signaal", "titel": "c", "van": "x"}]
    groep, tot, rest = B.melding_groep(items, False, {}, "uit")
    assert [it["id"] for it in groep] == [10] and tot == 10 and rest == 1, (groep, tot, rest)
    staat = {"ochtend": {"2026-10-22": {"verzonden": "2026-10-22T09:30:00+02:00", "klaarzet_id": 11}}}
    groep, tot, rest = B.melding_groep(items, False, staat, "uit")
    assert [it["id"] for it in groep] == [10, 12] and tot == 12 and rest == 0, (groep, tot, rest)


# ------------------------------------------------------------------------------------------------- T70 ---
def t70_wereld(tekst=None):
    w = Wereld(utc(2026, 10, 22, 7, 35), staat={"laatste_id": 99, "voorstel_hoogste": 900, "ochtend": {},
                                                 "avond": {"2026-10-21": {"verzonden": "2026-10-21T17:02:00+02:00"}},
                                                 "bundel_vanaf": "2026-10-21T15:05:00+00:00"})
    w.zet(100, "dagbundel", "Dagverslag 21-10", van="dagbundelaar", ts="2026-10-22T05:05:00+00:00")
    w.zet(101, "signaal", "Mail 08:00: open mch@ 3", van="mail-regisseur", uniek="mailupdate:2026-10-22:08:00",
          ts="2026-10-22T06:00:00+00:00")
    w.zet(102, "signaal", "Geen hartslag van een proefagent", van="normwacht", ts="2026-10-22T06:10:00+00:00")
    w.zet(103, "ochtendbericht", "Ochtendbericht do 22-10, 2 beslissingen", van="regisseur",
          uniek="ochtendbericht:2026-10-22", inhoud=ochtend_inhoud(tekst or ochtend_tekst(720)),
          ts="2026-10-22T07:30:00+00:00")
    return w


def test_t70_ochtendbericht_met_bundelregel_binnen_900():
    w = t70_wereld()
    staat = w.ronde()
    assert len(w.wa) == 1, f"precies een bericht: {w.wa}"
    m = w.wa[0]
    assert m["voorrang"] and m["kop"] == "Ochtendbericht do 22-10, 2 beslissingen", m
    assert m["tekst"].startswith(ochtend_tekst(720) + "\nGebundeld: "), m["tekst"][-200:]
    regel = m["tekst"].rsplit("\n", 1)[1]
    assert regel == "Gebundeld: dagverslag, mailupdate 08:00, signaal van De Normwacht; alles op het bord", regel
    assert len(W.plat(m["tekst"], None)) <= 900, len(W.plat(m["tekst"], None))
    assert w.item(103)["status"] == "opgepakt" and w.item(103)["opgepakt_door"] == "bode", w.item(103)
    assert any(r["onderwerp"] == "ochtendbericht 2026-10-22" and r["tekst"].startswith("ochtendbericht 2026-10-22")
               for r in w.logregels()), w.logregels()
    dag = staat["ochtend"]["2026-10-22"]
    assert dag["klaarzet_id"] == 103 and dag["verzonden"] and len(dag["sha"]) == 12, dag
    assert dag["punten"][1] == {"nr": 2, "soort": "voorstel", "ref": 900, "vingerafdruk": "abc123def456"}, dag["punten"]
    assert staat["laatste_id"] == 103 and staat["bundel_vanaf"] == "2026-10-22T07:35:00+00:00", staat
    w.ronde(utc(2026, 10, 22, 7, 40))
    assert len(w.wa) == 1, "een tweede ronde stuurt niets"


def test_t70_veel_bundelwerk_geeft_alleen_de_aantallen():
    w = t70_wereld()
    for i in range(30):
        w.zet(200 + i, "signaal", f"Proefsignaal {i}", van=f"proef-{i % 7}", ts="2026-10-22T06:30:00+00:00")
    w.item(103)["id"] = 300                   # het ochtendbericht blijft het jongste item
    w.ronde()
    regel = w.wa[0]["tekst"].rsplit("\n", 1)[1]
    assert regel == "Gebundeld: 33 berichten van 10 agents, op het bord", regel
    assert len(W.plat(w.wa[0]["tekst"], None)) <= 900


def test_t70_m6_verstuurd_is_verstuurd_ook_als_oppakken_faalt():
    w = t70_wereld()
    w.oppakken_faalt = 1
    staat = w.ronde()
    assert len(w.wa) == 1 and staat["ochtend"]["2026-10-22"]["verzonden"] and w.item(103)["status"] == "klaar"
    assert any("niet opgepakt" in t for t in w.noodteksten()), w.noodteksten()
    w.ronde(utc(2026, 10, 22, 7, 36))
    assert len(w.wa) == 1 and w.item(103)["status"] == "opgepakt", "M6: nooit een tweede keer, alleen opnieuw oppakken"


def test_t70_contract_alleen_tekst_punten_en_titel():
    """De Bode leest van het ochtendbericht alleen inhoud.tekst, inhoud.punten en de titel; wat De Regisseur verder in
    de inhoud zet (verder, bronnen, onbekend), stuurt hij niet."""
    w = t70_wereld(ochtend_tekst())
    inhoud = json.loads(w.item(103)["inhoud"])
    inhoud["verder"] = "Proefregel die niet mee mag"
    w.item(103)["inhoud"] = json.dumps(inhoud)
    w.ronde()
    assert "Proefregel die niet mee mag" not in w.wa[0]["tekst"], w.wa[0]["tekst"]


def test_t70_contract_met_het_ochtendbericht_zoals_de_regisseur_het_maakt():
    """Het item zoals koppelingen/ochtend.py van De Regisseur het echt maakt (4.2, I1, M6), in het slechtste geval: vijf
    volle punten, een lange regel Verder en een volle bundel. De Bode stuurt het een keer, met de titel als kop en met
    voorrang, blijft met de regel Gebundeld binnen 900 tekens, en houdt de punten vast zoals De Regisseur ze gaf. Tot
    21-10-2026 toetste elke kant dit contract alleen tegen een eigen, met de hand gemaakte versie."""
    import ochtend as O  # noqa: PLC0415
    moment = utc(2026, 10, 22, 7, 35)
    b = {"datum": "2026-10-22", "gisteren": "2026-10-21", "nu": moment, "vorig": {"hoogste_voorstel": 899}, "redenen": {},
         "voorstellen": [{"id": 900 + i, "naam": "werfverslag-voorbereider", "label": "Werfverslag voorbereider",
                          "actie": "Een lange voorgestelde actie met veel woorden " * 4, "parameters": f'{{"stap": {i}}}',
                          "ts": "2026-10-21T20:00:00+00:00"} for i in range(4)],
         "noden": [{"id": i, "naam": f"proef-{i % 6}", "label": "Een agent met een heel lang label op het bord", "tekst": f"Nood {i}",
                    "wie": "mehdi", "ts": "2026-10-20T08:00:00+00:00"} for i in range(30)],
         "dagverslag": {"zonder_dossier": 7}, "mail": {"dringend": 3},
         "gesprekken": {"fathom": {"tellend": 5, "prive": 1, "zonder_transcript": 0},
                        "plaud": {"tellend": 2, "prive": 0, "zonder_transcript": 1}},
         "zoom": {"telling": "ondergrens", "gesprekken": 16, "met_fathom": 14, "stand": "voorlopig: opname in verwerking"},
         "zoom_teksten": [1, 2], "gelezen": {"voorstellen": "22-10 09:35"},
         "onbekend": ["mail-stand", "dagverslag van een andere bron", "nog een onleesbare bron"]}
    item = O.item("2026-10-22", O.maak(b))
    # zes kandidaten: hoogstens vijf punten, en wat niet binnen 720 past, valt weg met '+n op het bord'
    assert 3 <= len(item["inhoud"]["punten"]) <= 5 and "op het bord\nVerder: " in item["inhoud"]["tekst"], item["inhoud"]["tekst"]
    # I1: De Regisseur blijft onder 720, zodat De Bode 180 tekens houdt voor de regel Gebundeld binnen de 900
    assert len(W.plat(item["inhoud"]["tekst"], None)) <= 720 and len(item["titel"]) <= 60, item
    w = Wereld(moment, staat={"laatste_id": 99, "voorstel_hoogste": 0, "ochtend": {}, "avond": {},
                              "bundel_vanaf": "2026-10-21T15:05:00+00:00"})
    for i in range(12):
        w.zet(100 + i, "signaal", f"Proefsignaal {i} met een titel die de bundelregel lang maakt", van=f"proef-{i % 5}",
              ts="2026-10-22T06:00:00+00:00")
    w.zet(200, item["soort"], item["titel"], van="regisseur", voor=item["voor"], uniek=item["uniek"], inhoud=item["inhoud"],
          ts="2026-10-22T07:30:00+00:00")
    staat = w.ronde()
    ochtend = [m for m in w.wa if m["kop"] == item["titel"]]
    assert len(ochtend) == 1 and ochtend[0]["voorrang"], w.wa
    tekst = ochtend[0]["tekst"]
    assert tekst.startswith(item["inhoud"]["tekst"] + "\nGebundeld: "), tekst[-200:]
    assert len(W.plat(tekst, None)) <= W.MAX_PARAM, len(W.plat(tekst, None))
    assert "Ochtendbericht past niet in een sjabloonbericht van WhatsApp" not in w.noodteksten(), w.noodteksten()
    assert w.item(200)["status"] == "opgepakt", w.item(200)
    dag = staat["ochtend"]["2026-10-22"]
    assert [(p["nr"], p["soort"], p["ref"], p["vingerafdruk"]) for p in dag["punten"]] == \
        [(p["nr"], p["soort"], p["ref"], p["vingerafdruk"]) for p in item["inhoud"]["punten"]], dag["punten"]


# ------------------------------------------------------------------------------------------------- T71 ---
def test_t71_verkeerd_ochtendbericht_niet_versturen():
    for van, uniek in (("ontwikkelaar", "ochtendbericht:2026-10-22"), ("regisseur", "ochtendbericht:2026-10-21")):
        w = Wereld(utc(2026, 10, 22, 8, 0), staat={"laatste_id": 49, "voorstel_hoogste": 0, "ochtend": {}, "avond": {}})
        w.zet(50, "ochtendbericht", "Ochtendbericht proef", van=van, uniek=uniek, inhoud=ochtend_inhoud("1. Verkeerd punt"))
        staat = w.ronde()
        assert not any("Verkeerd punt" in m["tekst"] for m in w.wa), (van, w.wa)
        assert w.item(50)["status"] == "opgepakt" and "verlopen" in w.item(50)["opgepakt_door"], (van, w.item(50))
        nood = [n for n in w.laatste()["nood"] if n["tekst"].startswith("Ochtendbericht niet verstuurd")]
        assert nood and nood[0]["wie"] == "claude-code", (van, w.laatste())
        assert staat["laatste_id"] == 50, staat
        w.ronde(utc(2026, 10, 22, 8, 5))
        assert any(t.startswith("Ochtendbericht niet verstuurd") for t in w.noodteksten()), "de nood blijft de dag staan"


# ------------------------------------------------------------------------------------------------- T72 ---
def test_t72_terugval_om_elf_uur_brussel_aan_beide_kanten_van_25_10():
    for voor, na_, datum in ((utc(2026, 10, 22, 8, 59), utc(2026, 10, 22, 9, 1), "22-10"),
                             (utc(2026, 10, 26, 9, 59), utc(2026, 10, 26, 10, 1), "26-10")):
        w = Wereld(voor, staat={"laatste_id": 1, "voorstel_hoogste": 3, "ochtend": {}, "avond": {},
                                "bundel_vanaf": voor.isoformat()}, voorstellen=[(1, "ontwikkelaar"), (2, "ontwikkelaar"),
                                                                                 (3, "contracten-agent")])
        w.noden = [{"naam": "normwacht", "tekst": "Proefnood een", "wie": "mehdi"},
                   {"naam": "zoom-wacht", "tekst": "Proefnood twee", "wie": "mehdi"},
                   {"naam": "zoom-wacht", "tekst": "Proefnood drie", "wie": "claude-code"}]
        w.ronde()
        assert not w.wa and not any(t.startswith("Geen ochtendbericht") for t in w.noodteksten()), (datum, w.wa)
        w.ronde(na_)
        assert len(w.wa) == 1 and w.wa[0]["voorrang"] and w.wa[0]["kop"].endswith("geen ochtendbericht"), (datum, w.wa)
        assert datum in w.wa[0]["kop"], w.wa[0]["kop"]
        tekst = w.wa[0]["tekst"]
        assert tekst.startswith("De Regisseur zette vandaag geen ochtendbericht klaar; 3 voorstellen en 2 noden voor jou open"), tekst
        assert not re.search(r"(?m)^\d+\. ", tekst), "een terugval heeft geen nummers"
        nood = [n for n in w.laatste()["nood"] if n["tekst"] == "Geen ochtendbericht van De Regisseur om 11:00"]
        assert nood and nood[0]["wie"] == "claude-code", w.laatste()
        w.ronde(na_ + timedelta(minutes=30))
        assert len(w.wa) == 1, "een terugval een keer per dag"


def test_t72_onbekend_is_nooit_nul():
    w = Wereld(utc(2026, 10, 22, 9, 1), staat={"laatste_id": 1, "ochtend": {}, "avond": {},
                                                "bundel_vanaf": "2026-10-22T07:00:00+00:00"})
    w.noden = None
    bord.BORD_DB = os.path.join(MAP, "bestaat-niet.db")
    w.ronde()
    tekst = w.wa[0]["tekst"]
    assert "voorstellen onbekend" in tekst and "noden onbekend" in tekst, tekst
    assert not re.search(r"\b0 (voorstellen|noden)", tekst), tekst


def test_t72_late_ochtendbericht_gaat_alsnog_zonder_bundelregel():
    w = Wereld(utc(2026, 10, 22, 9, 1), staat={"laatste_id": 1, "voorstel_hoogste": 0, "ochtend": {}, "avond": {},
                                                "bundel_vanaf": "2026-10-22T05:00:00+00:00"})
    w.zet(2, "signaal", "Proefsignaal voor de terugval", ts="2026-10-22T06:00:00+00:00")
    w.ronde()
    assert len(w.wa) == 1 and "Gebundeld: signaal van De Normwacht" in w.wa[0]["tekst"], w.wa
    w.zet(3, "ochtendbericht", "Ochtendbericht do 22-10, 2 beslissingen", van="regisseur",
          uniek="ochtendbericht:2026-10-22", inhoud=ochtend_inhoud(ochtend_tekst()))
    w.ronde(utc(2026, 10, 22, 9, 20))
    assert len(w.wa) == 2 and w.wa[1]["tekst"] == ochtend_tekst(), "met nummers, zonder bundelregel"
    assert not any(t.startswith("Geen ochtendbericht") for t in w.noodteksten()), w.noodteksten()


# ------------------------------------------------------------------------------------------------- T73 ---
def t73_wereld(stand):
    w = Wereld(utc(2026, 10, 22, 10, 0), stand=stand,
               staat={"laatste_id": 199, "voorstel_hoogste": 11, "avond": {}, "bundel_vanaf": "2026-10-22T07:40:00+00:00",
                      "ochtend": {"2026-10-22": {"verzonden": "2026-10-22T09:40:00+02:00", "klaarzet_id": 150, "opgepakt": True}}},
               voorstellen=[(i, "ontwikkelaar") for i in range(1, 12)])
    w.zet(200, "signaal", "Proefsignaal van De Normwacht om twaalf uur", ts="2026-10-22T10:00:00+00:00")
    return w


def test_t73_bundelstand_signaal_wacht_op_het_vaste_moment():
    w = t73_wereld("ochtend-avond")
    staat = w.ronde()
    assert not w.wa and staat["laatste_id"] == 200, (w.wa, staat)
    w.zet_voorstellen([(i, "ontwikkelaar") for i in range(1, 13)])
    w.ronde(utc(2026, 10, 22, 17, 0))            # 19:00 Brussel: de avondbundel
    assert len(w.wa) == 1 and w.wa[0]["kop"] == "Avondbundel do 22-10", w.wa
    assert "Proefsignaal van De Normwacht om twaalf uur" in w.wa[0]["tekst"], w.wa[0]["tekst"]
    assert "1 nieuw voorstel van De Ontwikkelaar wacht op je goedkeuring" in w.wa[0]["tekst"], w.wa[0]["tekst"]


def test_t73_stand_uit_alles_los_en_een_bericht_per_nieuw_voorstel():
    w = t73_wereld("uit")
    w.ronde()
    assert len(w.wa) == 1 and "Proefsignaal van De Normwacht om twaalf uur" in w.wa[0]["tekst"], w.wa
    w.ronde(utc(2026, 10, 22, 17, 0))            # 7 uur later, 11 voorstellen zoals voordien
    assert len(w.wa) == 1, f"geen herinnering meer: {w.wa[1:]}"
    w.zet_voorstellen([(i, "ontwikkelaar") for i in range(1, 13)])
    w.ronde(utc(2026, 10, 22, 17, 1))
    assert len(w.wa) == 2 and "1 nieuw voorstel van De Ontwikkelaar" in w.wa[1]["tekst"], w.wa
    w.ronde(utc(2026, 10, 22, 17, 2))
    assert len(w.wa) == 2, "hetzelfde nieuwe voorstel geeft maar een bericht"
    w.zet_voorstellen([(i, "ontwikkelaar") for i in range(2, 13)])
    w.ronde(utc(2026, 10, 22, 17, 3))
    assert len(w.wa) == 2, "L8: een gesloten voorstel geeft geen bericht"
    w.zet_voorstellen([(i, "ontwikkelaar") for i in range(2, 14)])
    w.ronde(utc(2026, 10, 22, 17, 4))
    assert len(w.wa) == 3, "L8: op het id, niet op het aantal (11 open, toch nieuw)"


# ------------------------------------------------------------------------------------------------- T74 ---
def test_t74_oproep_en_alarm_meteen_ook_in_de_stille_uren():
    w = Wereld(utc(2026, 10, 22, 10, 0), staat={"laatste_id": 299, "voorstel_hoogste": 0, "avond": {},
                                                 "bundel_vanaf": "2026-10-22T07:40:00+00:00",
                                                 "ochtend": {"2026-10-22": {"verzonden": "x", "opgepakt": True}}})
    w.zet(300, "oproep", "Dringende mail van een proefafzender", van="mail-regisseur")
    w.ronde()
    assert w.alarmen == [[300]] and len(w.wa) == 1 and "Dringende mail van een proefafzender" in w.wa[0]["tekst"], (w.alarmen, w.wa)
    w.zet(301, "signaal", "Proefagent stil sinds vanmiddag", ts="2026-10-22T21:00:00+00:00")
    w.ronde(utc(2026, 10, 22, 21, 0))            # 23:00 Brussel
    assert w.alarmen[-1] == [301] and len(w.wa) == 2 and "Proefagent stil" in w.wa[1]["tekst"], (w.alarmen, w.wa)
    staat = w.staat()
    bundel, _ = B.bundelwerk(w.items, staat | {"bundel_vanaf": "2026-10-22T07:40:00+00:00"})
    assert bundel == [], "een oproep of alarm staat nooit in de bundelregel"
    w.ronde(utc(2026, 10, 23, 15, 31))           # 17:31 de volgende dag: alleen alarmen in het venster, dus geen bundel
    assert len(w.wa) == 3 and w.wa[2]["kop"].endswith("geen ochtendbericht") and "Gebundeld" not in w.wa[2]["tekst"], w.wa[2:]


# ------------------------------------------------------------------------------------------------- T75 ---
def t75_wereld(moment):
    return Wereld(moment, staat={"laatste_id": 399, "voorstel_hoogste": 5, "avond": {},
                                 "bundel_vanaf": "2026-10-22T07:40:00+00:00",
                                 "ochtend": {"2026-10-22": {"verzonden": "x", "opgepakt": True}}},
                  voorstellen=[(i, "ontwikkelaar") for i in range(1, 6)])


def test_t75_avondbundel_bij_de_mailupdate_van_17_uur():
    w = t75_wereld(utc(2026, 10, 22, 15, 2))
    w.zet(400, "signaal", "Proefsignaal van de middag", ts="2026-10-22T10:00:00+00:00")
    w.zet(401, "signaal", "Mail 17:00: open mch@ 3; wachten werken", van="mail-regisseur",
          uniek="mailupdate:2026-10-22:17:00", ts="2026-10-22T15:01:00+00:00")
    staat = w.ronde()
    assert len(w.wa) == 1 and w.wa[0]["kop"] == "Avondbundel do 22-10" and w.wa[0]["voorrang"], w.wa
    regels = w.wa[0]["tekst"].split("\n\n")
    assert regels[0] == "- signaal: Mail 17:00: open mch@ 3; wachten werken (van De Mailregisseur)", regels
    assert regels[1] == "- signaal: Proefsignaal van de middag (van De Normwacht)" and regels[-1].startswith("Bord: "), regels
    assert staat["avond"]["2026-10-22"]["verzonden"] and staat["bundel_vanaf"] == "2026-10-22T15:02:00+00:00", staat
    w.ronde(utc(2026, 10, 22, 15, 40))
    assert len(w.wa) == 1, "een avondbundel per dag"


def test_t75_avondbundel_vanaf_half_zes_zonder_update():
    w = t75_wereld(utc(2026, 10, 22, 15, 20))
    w.zet(400, "signaal", "Proefsignaal van de middag", ts="2026-10-22T10:00:00+00:00")
    w.ronde()
    assert not w.wa, "17:20 zonder update: nog niets"
    w.ronde(utc(2026, 10, 22, 15, 31))
    assert len(w.wa) == 1 and "Proefsignaal van de middag" in w.wa[0]["tekst"] and "Mail 17:00" not in w.wa[0]["tekst"], w.wa


def test_t75_zonder_iets_geen_avondbundel():
    w = t75_wereld(utc(2026, 10, 22, 15, 31))
    w.ronde()
    assert not w.wa, w.wa


def test_t75_avondbundel_te_lang_blijft_binnen_900():
    w = t75_wereld(utc(2026, 10, 22, 15, 31))
    for i in range(40):
        w.zet(400 + i, "signaal", f"Proefsignaal {i} " + "lang " * 20, ts="2026-10-22T10:00:00+00:00")
    w.ronde()
    tekst = w.wa[0]["tekst"]
    assert len(W.plat(tekst, None)) <= 900 and re.search(r"- en nog \d+, die staan op het bord", tekst), tekst[-300:]


# ------------------------------------------------------------------------------------------------- T76 ---
def test_t76_onleesbare_werkwijze_belt_toch_en_berichten_wachten():
    w = Wereld(utc(2026, 10, 22, 10, 0), werkwijze=http(500), staat={"laatste_id": 499, "ochtend": {}, "avond": {}})
    w.zet(500, "signaal", "Proefsignaal dat moet wachten")
    oproepen = []
    nu_ = datetime.now().astimezone()
    with open(B.bellen.ROOSTER, "w") as f:
        json.dump({"geschreven": nu_.isoformat(), "regels": [{"sleutel": "proef-t76", "tijd": (nu_ - timedelta(minutes=1)).isoformat(),
                                                              "tekst": "Mehdi, over 5 minuten online: proefafspraak.",
                                                              "titel": "Proefafspraak"}]}, f)
    B.bellen.afspraak_bellen_beschikbaar = lambda: True
    B.bellen.belafspraak_actueel = lambda regel: (True, "")
    B.bellen.bel_afspraak = lambda tekst, slot="": oproepen.append(tekst) or [("twilio", "CA76")]
    try:
        staat = w.ronde()
    finally:
        for n in ("afspraak_bellen_beschikbaar", "belafspraak_actueel", "bel_afspraak"):
            setattr(B.bellen, n, ECHT[n])
        os.remove(B.bellen.ROOSTER)
    assert oproepen == ["Mehdi, over 5 minuten online: proefafspraak."], oproepen
    assert not w.wa and staat["laatste_id"] == 499 and "proef-t76" in staat.get("gebeld", {}), (w.wa, staat)
    assert w.laatste()["status"] == "fout" and "Werkwijze niet gelezen: bordfout" in w.noodteksten(), w.laatste()


# ------------------------------------------------------------------------------------------------- T77 ---
def test_t77_bundelen_en_werkwijze_zeggen_hetzelfde():
    """T77, sinds RZ3-02 (22-10-2026): de stand staat niet meer vast in de code. Het zaad draagt de vaste regel op een
    eigen regel in de sectie over de stand van BUNDELEN, en de code leest de stand uit de werkwijze die de ronde las.
    Tot dan toetste T77 dat een vaste waarde BUNDELEN in bode.py en de zin in de werkwijze gelijk waren; een push van de
    code bundelde dan al voor Mehdi de werkwijze met een klik op het bord zette."""
    bron = open(os.path.join(RUNNER, "bode.py"), encoding="utf-8").read()
    standen = re.search(r"^BUNDEL_STANDEN = (\(.*\))$", bron, re.M).group(1)
    assert standen == '("uit", "ochtend-avond")', "keuze 1 van Mehdi, 21-10-2026: optie A; optie C is niet gebouwd (13.4)"
    # geen vaste stand in de code: de regel staat in de werkwijze, de code kent alleen haar vorm
    assert not re.search(r"^BUNDELEN\s*=", bron, re.M) and not hasattr(B, "BUNDELEN"), "de stand staat niet vast in de code"
    assert re.search(rf'^BUNDELEN_REGEL = "{REGEL}"$', bron, re.M), "de vorm van de regel staat een keer in de code"
    # het zaad draagt de regel, op een eigen regel, in de sectie over de stand van BUNDELEN
    assert WERKWIJZE.count("\n## De stand van BUNDELEN\n") == 1, "de sectie staat er precies een keer"
    sectie = WERKWIJZE.split("\n## De stand van BUNDELEN\n", 1)[1].split("\n#", 1)[0]
    assert sectie.splitlines().count(REGEL) == 1 and WERKWIJZE.splitlines().count(REGEL) == 1, sectie
    assert B.stand_bundelen(WERKWIJZE) == "ochtend-avond" and B.stand_bundelen(WERKWIJZE_UIT) == "uit"
    # de code leest de stand uit de werkwijze van de ronde, en droog uit de werkwijze op het bord
    ronde = bron.split("\ndef ronde(", 1)[1].split("\ndef ", 1)[0]
    assert "stand = stand_bundelen(r.werkwijze)" in ronde and "stand_bundelen(ag.werkwijze_lezen" not in ronde, ronde[-600:]
    assert re.search(r"stand = stand_bundelen\(veilig\(nood, \"Werkwijze lezen\", ag\.werkwijze_lezen, None\)\)", ronde), \
        "droog leest de werkwijze zelf; onleesbaar is 'uit'"
    assert "Bij een omschakeling verdwijnt niets" in sectie and "slotbundel_sturen" in bron, \
        "BOD-1, BOD-2: code en werkwijze zeggen dat bij een omschakeling niets verdwijnt"
    # Tegenproef van 22-10-2026: de documentatie noemde nog een vaste waarde in bode.py, en T77 hield dat zelfs vast. Nu
    # moeten de norm, de docstring van mail_regisseur.py en TECHNICAL-REFERENCE.md de regel in de werkwijze noemen.
    regisseur = open(os.path.join(RUNNER, "mail_regisseur.py"), encoding="utf-8").read().split('"""')[1]
    regisseur = " ".join(regisseur.split())
    assert f"`{B.BUNDELEN_REGEL}`" in regisseur and "in bode.py" not in regisseur, "de docstring van mail_regisseur.py volgt mee"
    # G2 en L7: hoofdstuk 6 van AGENTNORM.md noemt de regel in de werkwijze, de terugval en de slotbundel
    norm = open(os.path.join(RUNNER, "AGENTNORM.md"), encoding="utf-8").read()
    hoofdstuk6 = norm.split("## 6.", 1)[1].split("\n## ", 1)[0]
    assert f"`{B.BUNDELEN_REGEL}`" in hoofdstuk6 and "`BUNDELEN = " not in hoofdstuk6, "AGENTNORM hoofdstuk 6 noemt de regel"
    assert "werkwijze van De Bode" in " ".join(hoofdstuk6.split()) and "slotbundel" in hoofdstuk6, hoofdstuk6[:400]
    assert "in het ochtendbericht, als punt of onder Verder" in hoofdstuk6, "L7: zo bereikt een nood voor Mehdi hem"
    referentie = open(os.path.join(os.path.dirname(RUNNER), "TECHNICAL-REFERENCE.md"), encoding="utf-8").read()
    assert 'BUNDELEN = "' not in referentie and f"`{B.BUNDELEN_REGEL}`" in referentie, "TECHNICAL-REFERENCE.md volgt mee"
    assert "HERINNERING_UREN" not in bron and not hasattr(B, "HERINNERING_UREN"), "geen herinnering om de zes uur (I7)"


def test_t77_werkwijze_29_in_de_strikte_vorm():
    regels = WERKWIJZE.splitlines()
    assert regels[2].startswith("Versie 2.9"), regels[2][:40]
    # RZ4-03 (22-10-2026): het zaad zegt wat de code doet met de leesstand en de lopende bundel
    tekst = " ".join(WERKWIJZE.split())
    assert "nooit na een bericht dat nog niet weg is" in tekst and '"onbekend of meer"' in tekst, "RZ4-03 in de werkwijze"
    nooit, beslist = bord.grenzen(WERKWIJZE)
    assert len(nooit) >= 3 and len(beslist) >= 3, (nooit, beslist)
    assert any(p.startswith("Keuze 1") and "21-10-2026" in p and "ochtend-avond" in p for p in beslist), beslist
    assert any(p.startswith("Keuze 2") and "21-10-2026" in p and "nog niet" in p for p in beslist), beslist
    assert len(WERKWIJZE) >= 500 and "```" not in WERKWIJZE and not bord.HTML.search(WERKWIJZE)


def test_t77_nergens_gedachtestreepjes():
    for pad in ("bode.py", "bord_export.py", "mail_regisseur.py", os.path.join("koppelingen", "whatsapp.py"),
                os.path.join("werkwijze", "bode.md"), os.path.join("tests", "test_bode_regie.py"),
                os.path.join("tests", "test_whatsapp.py"), os.path.join("tests", "test_codex_ronde2_bode.py")):
        tekst = open(os.path.join(RUNNER, pad), encoding="utf-8").read()
        assert chr(0x2014) not in tekst and chr(0x2013) not in tekst, pad


# ------------------------------------------------------------------------------------------------- T99 ---
def t99_wereld(werkwijze=WERKWIJZE):
    w = Wereld(utc(2026, 10, 22, 10, 0), werkwijze=werkwijze, staat={"laatste_id": 599, "voorstel_hoogste": 0, "avond": {},
                                                                     "ochtend": {"2026-10-22": {"verzonden": "x", "opgepakt": True}}})
    w.zet(600, "oproep", "Proefoproep")

    def afspraken(staat, log=None, bewaar=None, nood=None, spoor=None):
        nood.append({"tekst": "Afspraken bellen: proefnood", "wie": "claude-code"})
        return ""

    def alarm(staat, alarmen, log=None, spoor=None, nood=None):
        nood.append({"tekst": "Alarm bellen: proefnood", "wie": "claude-code"})
        return ""

    B.bellen.afspraken_bellen, B.bellen.alarm_bellen = afspraken, alarm
    return w


def test_t99_noden_van_het_bellen_in_een_gewone_ronde():
    w = t99_wereld()
    w.ronde()
    assert w.laatste()["status"] == "waakt", w.laatste()
    assert {"Afspraken bellen: proefnood", "Alarm bellen: proefnood"} <= set(w.noodteksten()), w.noodteksten()


def test_t99_noden_van_het_bellen_ook_als_de_ronde_stopt():
    w = t99_wereld(http(500))
    w.noden = [{"naam": "bode", "tekst": "Oude nood", "wie": "mehdi"}]
    w.ronde()
    assert w.laatste()["status"] == "fout", w.laatste()
    assert w.noodteksten() == ["Oude nood", "Afspraken bellen: proefnood", "Alarm bellen: proefnood",
                               "Werkwijze niet gelezen: bordfout"], w.noodteksten()
    assert not w.wa, "zonder regelboek geen berichten"


def test_t99_open_noden_onbekend_dan_in_het_detail():
    w = t99_wereld(http(500))
    w.noden = None
    w.ronde()
    laatste = w.laatste()
    assert laatste["status"] == "fout" and "nood" not in laatste, laatste
    assert "Afspraken bellen: proefnood" in laatste["detail"] and "Alarm bellen: proefnood" in laatste["detail"], laatste


def test_t99_de_bron_geeft_de_noden_door():
    bron = open(os.path.join(RUNNER, "bode.py"), encoding="utf-8").read()
    assert 'ag.ronde("berichten van en naar Mehdi", begin_noden=nood)' in bron
    assert bron.index("bellen.afspraken_bellen(") < bron.index("ag.ronde(") and bron.index("bellen.alarm_bellen(") < bron.index("ag.ronde(")


# ------------------------------------------------------------------------------------------ T100 en L2 ---
VRAAG = "Zoomwacht, wat zei de klant over de Proefstraat 12?"
ANTWOORD = "De klant wil de offerte voor de Proefstraat 12 dinsdag om tien uur ontvangen."


def test_t100_geen_vraag_of_antwoord_in_het_werkverslag():
    w = Wereld(utc(2026, 10, 22, 10, 0), staat={"laatste_id": 1, "wa_laatste_id": 5, "voorstel_hoogste": 0, "avond": {},
                                                 "ochtend": {"2026-10-22": {"verzonden": "x", "opgepakt": True}},
                                                 "wacht": [{"id": 707, "aan": "zoom-wacht"}]})
    w.gesprekken[707] = {"id": 707, "aan": "zoom-wacht", "status": "beantwoord", "antwoord": ANTWOORD}
    w.wa_binnen = [{"id": 6, "tekst": VRAAG}]
    w.ronde()
    assert any(ANTWOORD in m["tekst"] for m in w.wa), "het antwoord gaat naar Mehdi"
    assert any("Ontvangen, De Zoomwacht kijkt ernaar." in m["tekst"] for m in w.wa), w.wa
    assert w.gesprekken[700]["aan"] == "zoom-wacht" and w.gesprekken[700]["tekst"] == "wat zei de klant over de Proefstraat 12?"
    alles = json.dumps(w.logregels(), ensure_ascii=False) + json.dumps(w.hartslagen, ensure_ascii=False)
    assert "Proefstraat" not in alles, "geen vraag- of antwoordtekst in het werkverslag of de hartslag (H1)"
    assert any(r["tekst"] == f"antwoord van De Zoomwacht naar Mehdi, {len(ANTWOORD)} tekens" for r in w.logregels())
    assert any(r["tekst"] == f"uit WhatsApp aan De Zoomwacht, {len('wat zei de klant over de Proefstraat 12?')} tekens"
               for r in w.logregels()), w.logregels()


def test_l2_een_antwoord_nooit_via_zoom_chat():
    w = Wereld(utc(2026, 10, 22, 10, 0), staat={"laatste_id": 1, "voorstel_hoogste": 0, "avond": {},
                                                 "ochtend": {"2026-10-22": {"verzonden": "x", "opgepakt": True}},
                                                 "wacht": [{"id": 707, "aan": "zoom-wacht"}]})
    w.gesprekken[707] = {"id": 707, "aan": "zoom-wacht", "status": "beantwoord", "antwoord": ANTWOORD}
    w.wa_fout = lambda tekst, kop, voorrang: RuntimeError("Meta nagebootst 500")
    staat = w.ronde()
    assert not w.zoom, "een antwoord gaat nooit via Zoom-chat"
    assert staat["wacht"] == [{"id": 707, "aan": "zoom-wacht"}], "het antwoord wacht op een volgende ronde"
    bron = open(os.path.join(RUNNER, "bode.py"), encoding="utf-8").read()
    assert 'laad_env(ZOOM_ENV, zonder=("ZOOM_SENDER", "ZOOM_MELDING_CONTACT"))' in bron


def test_reg03_lang_antwoord_ingekort_met_verwijzing_en_gelezen():
    """REG-03 (R6, H1): De Regisseur bewaart het volle antwoord met de regel Gelezen in gesprek.antwoord; De Bode kort het
    voor WhatsApp in met dezelfde regel (ochtend.whatsapp_kort): hoogstens 800 tekens, dan de verwijzing naar de pagina
    van de agent en de regel Gelezen als laatste. Een kort antwoord gaat ongewijzigd. Tot 21-10-2026 ging het volle
    antwoord mee, zonder verwijzing naar het bord."""
    gelezen = "Gelezen: dossier van zoom-wacht (22-10 09:58); gesprekkentabel (Fathom gelezen tot 22-10 09:00)"
    lang = " ".join(f"Proefzin {i} over de werf." for i in range(90))
    assert len(lang) > 2000
    for aan, antwoord, verwacht_kort in (("zoom-wacht", f"{lang}\n\n{gelezen}", True), ("zoom-wacht", f"{ANTWOORD}\n\n{gelezen}", False)):
        w = Wereld(utc(2026, 10, 22, 10, 0), staat={"laatste_id": 1, "voorstel_hoogste": 0, "avond": {},
                                                     "ochtend": {"2026-10-22": {"verzonden": "x", "opgepakt": True}},
                                                     "wacht": [{"id": 707, "aan": aan}]})
        w.gesprekken[707] = {"id": 707, "aan": aan, "status": "beantwoord", "antwoord": antwoord}
        staat = w.ronde()
        assert staat["wacht"] == [] and len(w.wa) == 1, (w.wa, staat)
        kop, _, tekst = w.wa[0]["tekst"].partition(":\n\n")
        assert kop == "De Zoomwacht", kop
        if verwacht_kort:
            assert len(tekst) <= 800 and tekst.endswith("\n" + gelezen), tekst[-300:]
            assert f"Volledig op het bord: mijnagents.globaal.be/agent/{aan}\n{gelezen}" in tekst, tekst[-300:]
            assert tekst.startswith("Proefzin 0 over de werf.") and "Proefzin 89" not in tekst, tekst[:200]
        else:
            assert tekst == antwoord, tekst
        assert any(r["tekst"] == f"antwoord van De Zoomwacht naar Mehdi, {len(antwoord)} tekens" for r in w.logregels()), \
            "het werkverslag noemt de lengte van het volle antwoord (H1)"


def test_t100_export_zonder_gesprekstekst():
    pad = os.path.join(MAP, "export.db")
    shutil.copy(SJABLOON_DB, pad)
    nu_ = datetime.now(UTC).isoformat()
    c = sqlite3.connect(pad)
    for naam, label in (("bode", "De Bode"), ("regisseur", "De Regisseur")):
        c.execute("INSERT INTO agent(naam, label, werkwijze, actief, aangemaakt) VALUES(?,?,?,1,?)", (naam, label, "# proef", nu_))
    c.execute("INSERT INTO gesprek(id, aan, van, tekst, antwoord, status, ts, beantwoord_ts) VALUES(?,?,?,?,?,?,?,?)",
              (707, "zoom-wacht", "mehdi (whatsapp)", VRAAG, ANTWOORD, "beantwoord", nu_, nu_))
    c.executemany("INSERT INTO logboek(naam, onderwerp, stap, tekst, detail, ts) VALUES(?,?,?,?,?,?)", [
        # zo schreven De Bode en De Regisseur het tot 21-10-2026
        ("bode", "bericht 707", "bron", f"uit WhatsApp aan De Zoomwacht: {VRAAG}", "", nu_),
        ("bode", "bericht 707", "melding", "antwoord van De Zoomwacht naar Mehdi", ANTWOORD, nu_),
        ("regisseur", "bericht 707 aan zoom-wacht", "bron", f"vraag van mehdi (whatsapp): {VRAAG}", "", nu_),
        ("regisseur", "bericht 707 aan zoom-wacht", "melding", "beantwoord op het bord", ANTWOORD, nu_),
        ("bode", "bericht", "melding", "1 van 1 items via whatsapp", "Mehdi Agents, 10:00:\n- signaal: Proefmelding", nu_)])
    c.commit()
    c.close()
    E.DB, E.DATA, E.UIT = pad, MAP, os.path.join(MAP, "export")
    with redirect_stdout(io.StringIO()):
        E.main()
    gelezen = {}
    for wortel, _, bestanden in os.walk(E.UIT):
        for b in bestanden:
            gelezen[os.path.join(wortel, b)] = open(os.path.join(wortel, b), encoding="utf-8").read()
    assert gelezen and not [p for p, t in gelezen.items() if "Proefstraat" in t], \
        [p for p, t in gelezen.items() if "Proefstraat" in t]
    gesprekken = gelezen[os.path.join(E.UIT, "Regisseur", "gesprekken.md")]
    assert "| 707 |" in gesprekken and f"{len(VRAAG)} tekens | {len(ANTWOORD)} tekens |" in gesprekken, gesprekken
    bode = "".join(t for p, t in gelezen.items() if os.sep + "Bode" + os.sep + "werkverslag" in p)
    assert f"({len(ANTWOORD)} tekens, niet in de export)" in bode and "Mehdi Agents, 10:00" in bode, bode


def test_a54_zoom_account_export_bevat_alleen_delen_en_codes():
    pad = os.path.join(MAP, "export-account.db")
    shutil.copy(SJABLOON_DB, pad)
    ts = datetime.now(UTC).isoformat()
    c = sqlite3.connect(pad)
    c.execute("INSERT INTO agent(naam, label, werkwijze, actief, aangemaakt) VALUES(?,?,?,1,?)",
              ("zoom-wacht", "De Zoomwacht", "# proef", ts))
    inhoud = {"delen": {"beveiliging": "ok", "apps": "onbekend: gevoeligeredenproef"}, "adviezen": [{"code": "ZA-04"}],
              "beveiliging": {"tweestaps": "uitgevoeligeproef"}}
    c.execute("INSERT INTO klaarzet(van,voor,soort,sleutel,titel,inhoud,uniek,status,ts) VALUES(?,?,?,?,?,?,?,?,?)",
              ("zoom-wacht", "mehdi", "zoom-account", "", "Zoom-account proef", json.dumps(inhoud),
               "zoom-account:2026-W44", "klaar", ts))
    c.execute("INSERT INTO voorstel(naam,actie,doel,reden,parameters,runbook,ts) VALUES(?,?,?,?,?,?,?)",
              ("zoom-wacht", "Zoom: tweestapsverificatie aanzetten", "gevoeligdoelproef", "gevoeligredenproef",
               json.dumps({"zoom_advies": "ZA-04"}), "", ts))
    c.execute("INSERT INTO logboek(naam,onderwerp,stap,tekst,detail,ts) VALUES(?,?,?,?,?,?)",
              ("zoom-wacht", "Zoom-account", "bron", "gevoeligtekstproef", "gevoeligdetailproef", ts))
    c.commit()
    c.close()
    E.DB, E.DATA, E.UIT = pad, MAP, os.path.join(MAP, "export-account")
    with redirect_stdout(io.StringIO()):
        E.main()
    gelezen = []
    for wortel, _, bestanden in os.walk(E.UIT):
        for b in bestanden:
            if os.sep + "Zoomwacht" + os.sep in os.path.join(wortel, b):
                gelezen.append(open(os.path.join(wortel, b), encoding="utf-8").read())
    samen = "\n".join(gelezen)
    assert "ZA-04" in samen and "beveiliging: ok" in samen and "apps: onbekend" in samen
    assert all(x not in samen for x in ("uitgevoeligeproef", "gevoeligdoelproef", "gevoeligredenproef",
                                        "gevoeligeredenproef", "gevoeligtekstproef", "gevoeligdetailproef")), samen


# ----------------------------------------------------------------------------------- BOD-1 tot BOD-5 ---
# Bevestigde bevindingen van de tegenlezing van fase 3 (21-10-2026), elk eerst als falende toets op de code van toen.
def test_bod1_overgang_naar_de_bundelstand_verliest_niets():
    """BOD-1 (B4, B5, bij T73): bode.json van voor de bundelstand, zonder bundel_vanaf. Signaal 101 kwam om 23:00 Brussel
    en bleef in de stille uren liggen; de eerste ronde in 'ochtend-avond' is om 06:00. De bundel begint na het jongste
    item dat al los afgehandeld was (100), dus 101 staat in het ochtendbericht. Tot 21-10-2026 begon hij bij die eerste
    ronde zelf: 101 telde meteen als afgehandeld en bereikte Mehdi nooit."""
    w = Wereld(utc(2026, 10, 22, 4, 0), staat={"laatste_id": 100, "tg_offset": 0, "wacht": [], "laatste_herinnering": "",
                                                "laatste_voorstellen": 0})
    w.zet(100, "signaal", "Proefsignaal dat al los wegging", van="zoom-wacht", ts="2026-10-21T18:00:00+00:00")
    w.zet(101, "signaal", "Proefsignaal van gisteravond", ts="2026-10-21T21:00:00+00:00")
    staat = w.ronde()
    assert not w.wa and staat["laatste_id"] == 101, (w.wa, staat)
    assert staat["bundel_vanaf"] == "2026-10-21T18:00:00+00:00", staat
    w.zet(102, "ochtendbericht", "Ochtendbericht do 22-10, 2 beslissingen", van="regisseur",
          uniek="ochtendbericht:2026-10-22", inhoud=ochtend_inhoud(ochtend_tekst()), ts="2026-10-22T07:30:00+00:00")
    w.ronde(utc(2026, 10, 22, 7, 35))
    assert len(w.wa) == 1 and w.wa[0]["tekst"] == ochtend_tekst() + "\nGebundeld: signaal van De Normwacht; alles op het bord", w.wa
    # overdag: wat tussen de laatste losse ronde en de eerste bundelronde binnenkwam, staat in de avondbundel
    w = Wereld(utc(2026, 10, 22, 12, 5), staat={"laatste_id": 100, "voorstel_hoogste": 0, "wacht": [],
                                                 "ochtend": {"2026-10-22": {"verzonden": "x", "opgepakt": True}}})
    w.zet(100, "signaal", "Proefsignaal dat al los wegging", van="zoom-wacht", ts="2026-10-22T11:00:00+00:00")
    w.zet(101, "signaal", "Proefsignaal van vlak voor de uitrol", ts="2026-10-22T12:00:00+00:00")
    w.ronde()
    assert not w.wa, w.wa
    w.ronde(utc(2026, 10, 22, 15, 31))
    assert len(w.wa) == 1 and "Proefsignaal van vlak voor de uitrol" in w.wa[0]["tekst"], w.wa
    assert "al los wegging" not in w.wa[0]["tekst"], w.wa[0]["tekst"]
    # geen los afgehandeld item op de pagina: 24 uur terug, zoals lees_staat
    w = Wereld(utc(2026, 10, 22, 4, 0), staat={"laatste_id": 100, "wacht": []})
    w.zet(101, "signaal", "Proefsignaal van gisteravond", ts="2026-10-21T21:00:00+00:00")
    assert w.ronde()["bundel_vanaf"] == "2026-10-21T04:00:00+00:00", w.staat()


def test_bod2_terug_naar_uit_stuurt_eerst_de_slotbundel():
    """BOD-2 (B5, bij T73): het signaal van 12:00 telde in de bundelstand al als afgehandeld en wachtte op de avond. Gaat
    de stand terug naar 'uit', dan komt het eerst in een slotbundel; bundel_vanaf gaat pas weg na een geslaagde
    verzending. Wat na de omschakeling binnenkomt, gaat los en niet ook nog in de slotbundel. Tot 21-10-2026 gooide 'uit'
    bundel_vanaf meteen weg en bereikte het signaal Mehdi nooit."""
    w = t73_wereld("ochtend-avond")
    staat = w.ronde()
    assert not w.wa and staat["laatste_id"] == 200, (w.wa, staat)
    w.werkwijze = WERKWIJZE_UIT                 # RZ3-02: de werkwijze op het bord zonder de regel
    w.zet(201, "signaal", "Proefsignaal na de omschakeling", ts="2026-10-22T11:30:00+00:00")
    w.wa_fout = lambda tekst, kop, voorrang: RuntimeError("Meta nagebootst 500") if voorrang else None
    staat = w.ronde(utc(2026, 10, 22, 12, 0))   # 14:00 Brussel: de slotbundel mislukt, het losse bericht niet
    assert [m["kop"] for m in w.wa] == ["je agents"] and "Proefsignaal na de omschakeling" in w.wa[0]["tekst"], w.wa
    assert "om twaalf uur" not in w.wa[0]["tekst"], w.wa[0]["tekst"]
    assert staat["bundel_vanaf"] == "2026-10-22T07:40:00+00:00" and staat["bundel_tot"] == 200, staat
    w.wa_fout = None
    staat = w.ronde(utc(2026, 10, 22, 12, 1))
    assert len(w.wa) == 2 and w.wa[1]["kop"] == "Bundel do 22-10" and w.wa[1]["voorrang"], w.wa
    assert "Proefsignaal van De Normwacht om twaalf uur" in w.wa[1]["tekst"], w.wa[1]["tekst"]
    assert "na de omschakeling" not in w.wa[1]["tekst"] and w.wa[1]["tekst"].endswith(f"Bord: {B.BORD_URL}"), w.wa[1]
    assert "bundel_vanaf" not in staat and "bundel_tot" not in staat, staat
    w.ronde(utc(2026, 10, 22, 16, 0))
    assert len(w.wa) == 2, f"de slotbundel gaat een keer: {w.wa[2:]}"
    # in de stille uren wacht de slotbundel tot 07:00
    w = t73_wereld("ochtend-avond")
    w.ronde()
    w.werkwijze = WERKWIJZE_UIT
    staat = w.ronde(utc(2026, 10, 22, 21, 0))   # 23:00 Brussel
    assert not w.wa and staat["bundel_vanaf"], (w.wa, staat)
    w.ronde(utc(2026, 10, 23, 5, 1))            # 07:01 Brussel
    assert len(w.wa) == 1 and w.wa[0]["kop"] == "Bundel vr 23-10" and "om twaalf uur" in w.wa[0]["tekst"], w.wa


def test_bod3_verkeerd_ochtendbericht_na_het_verstuurde_houdt_geen_oproep_tegen():
    """BOD-3 (J4, bij T71 en T74): het ochtendbericht van vandaag is al weg. Een verkeerd ochtendbericht dat daarna komt,
    zet ik dezelfde ronde opzij en meld ik, en de oproep erachter krijgt meteen zijn bericht. Tot 21-10-2026 bleef het
    verkeerde item tot middernacht op klaar, en wachtte elk bericht erachter."""
    w = Wereld(utc(2026, 10, 22, 10, 0), staat={"laatste_id": 299, "voorstel_hoogste": 0, "avond": {},
                                                 "bundel_vanaf": "2026-10-22T07:40:00+00:00",
                                                 "ochtend": {"2026-10-22": {"verzonden": "2026-10-22T09:40:00+02:00",
                                                                            "klaarzet_id": 150, "opgepakt": True}}})
    w.zet(300, "ochtendbericht", "Ochtendbericht proef", van="ontwikkelaar", uniek="ochtendbericht:2026-10-23",
          inhoud=ochtend_inhoud("1. Proefpunt"))
    w.zet(301, "oproep", "Dringende mail van een proefafzender", van="mail-regisseur")
    staat = w.ronde()
    assert w.alarmen == [[301]] and len(w.wa) == 1 and "Dringende mail van een proefafzender" in w.wa[0]["tekst"], w.wa
    assert "Proefpunt" not in w.wa[0]["tekst"] and staat["laatste_id"] == 301, staat
    assert w.item(300)["status"] == "opgepakt" and "verlopen" in w.item(300)["opgepakt_door"], w.item(300)
    assert any(t.startswith("Ochtendbericht niet verstuurd") for t in w.noodteksten()), w.noodteksten()


def test_bod3_ochtendbericht_dat_in_de_stille_uren_wacht_houdt_geen_alarm_tegen():
    """BOD-3 (J4, T74): een geldig ochtendbericht van vandaag staat om 22:30 op klaar en wacht (stille uren). De oproep
    erachter gaat meteen, een keer; laatste_id blijft voor het ochtendbericht staan en de oproep onthoud ik apart. Een
    gewoon signaal erachter wacht tot de ochtend, ook als het ochtendbericht om middernacht verloopt."""
    w = Wereld(utc(2026, 10, 22, 20, 30), stand="uit", staat={"laatste_id": 299, "voorstel_hoogste": 0, "avond": {},
                                                               "ochtend": {"2026-10-22": {"terugval": "2026-10-22T11:00:00+02:00"}}})
    w.zet(300, "ochtendbericht", "Ochtendbericht do 22-10, 2 beslissingen", van="regisseur",
          uniek="ochtendbericht:2026-10-22", inhoud=ochtend_inhoud(ochtend_tekst()))
    w.zet(301, "signaal", "Proefsignaal dat tot morgen wacht")
    w.zet(302, "oproep", "Dringende mail van een proefafzender", van="mail-regisseur")
    staat = w.ronde()                            # 22:30 Brussel
    assert len(w.wa) == 1 and "Dringende mail van een proefafzender" in w.wa[0]["tekst"], w.wa
    assert "tot morgen wacht" not in w.wa[0]["tekst"] and "Twee dringende mails" not in w.wa[0]["tekst"], w.wa[0]["tekst"]
    assert staat["laatste_id"] == 299 and staat["alarm_gemeld"] == [302] and w.item(300)["status"] == "klaar", staat
    w.ronde(utc(2026, 10, 22, 20, 31))
    assert len(w.wa) == 1, f"de oproep krijgt een bericht: {w.wa[1:]}"
    w.ronde(utc(2026, 10, 22, 22, 1))            # 00:01 Brussel: het ochtendbericht van gisteren verloopt
    assert len(w.wa) == 1 and w.item(300)["status"] == "opgepakt", (w.wa, w.item(300))
    staat = w.ronde(utc(2026, 10, 23, 5, 1))     # 07:01 Brussel
    assert len(w.wa) == 2 and "tot morgen wacht" in w.wa[1]["tekst"] and "Dringende mail" not in w.wa[1]["tekst"], w.wa
    assert staat["laatste_id"] == 302 and "alarm_gemeld" not in staat, staat


def test_bod3_melding_groep_neemt_alarmen_mee_achter_een_open_ochtendbericht():
    items = [{"id": 10, "soort": "signaal", "titel": "a", "van": "x"},
             {"id": 11, "soort": "ochtendbericht", "titel": "b", "van": "regisseur", "uniek": "ochtendbericht:2026-10-22",
              "status": "klaar"},
             {"id": 12, "soort": "signaal", "titel": "c", "van": "x"},
             {"id": 13, "soort": "oproep", "titel": "d", "van": "mail-regisseur"}]
    groep, tot, rest = B.melding_groep(items, False, {}, "uit")
    assert [it["id"] for it in groep] == [10, 13] and tot == 10 and rest == 1, (groep, tot, rest)
    groep, tot, rest = B.melding_groep(items, False, {"alarm_gemeld": [13]}, "uit")
    assert [it["id"] for it in groep] == [10] and tot == 10 and rest == 1, (groep, tot, rest)


def test_bod4_wat_tijdens_het_bellen_binnenkomt_komt_een_keer():
    """BOD-4 (B4, bij T70): een signaal komt binnen terwijl de ronde belt, na het begin van de ronde en voor het bord
    gelezen is. Het staat in het ochtendbericht en niet nog eens in de avondbundel: de bundel begint opnieuw bij het
    lezen van het bord, niet bij het begin van de ronde."""
    w = t70_wereld()

    def afspraken(staat, log=None, bewaar=None, nood=None, spoor=None):
        w.moment = utc(2026, 10, 22, 7, 35, 50)
        w.zet(104, "signaal", "Proefsignaal tijdens het bellen", van="zoom-wacht", ts="2026-10-22T07:35:40+00:00")
        return ""

    B.bellen.afspraken_bellen = afspraken
    try:
        staat = w.ronde()
    finally:
        B.bellen.afspraken_bellen = ECHT["afspraken_bellen"]
    regel = w.wa[0]["tekst"].rsplit("\n", 1)[1]
    assert regel == ("Gebundeld: dagverslag, mailupdate 08:00, signaal van De Normwacht, signaal van De Zoomwacht; "
                     "alles op het bord"), regel
    assert staat["bundel_vanaf"] == "2026-10-22T07:35:50+00:00", staat
    w.ronde(utc(2026, 10, 22, 15, 31))
    assert len(w.wa) == 1, f"geen avondbundel met hetzelfde signaal: {w.wa[1:]}"


def bod5_wereld(stand, inhoud):
    w = Wereld(utc(2026, 10, 22, 7, 35), stand=stand, staat={"laatste_id": 99, "voorstel_hoogste": 899, "ochtend": {},
                                                              "avond": {}, "bundel_vanaf": "2026-10-22T07:00:00+00:00"},
               voorstellen=[(900, "ontwikkelaar"), (901, "normwacht")])
    w.zet(100, "ochtendbericht", "Ochtendbericht do 22-10, 2 beslissingen", van="regisseur",
          uniek="ochtendbericht:2026-10-22", inhoud=inhoud, ts="2026-10-22T07:30:00+00:00")
    return w


def test_bod5_voorstel_van_na_het_opstellen_blijft_nieuw():
    """BOD-5 (L8, bij T73): De Regisseur telde de voorstellen tot 900; 901 kwam erbij voor ik het ochtendbericht
    verstuurde. Na het versturen telt alleen wat hij telde als gemeld, dus 901 krijgt in 'uit' een bericht en staat in de
    bundelstand in de avondbundel. Zonder hoogste_voorstel in het ochtendbericht telt niets als gemeld."""
    inhoud = ochtend_inhoud(ochtend_tekst()) | {"bronnen": {"voorstellen": {"hoogste_voorstel": 900}}}
    w = bod5_wereld("uit", inhoud)
    staat = w.ronde()
    assert [m["kop"] for m in w.wa] == ["Ochtendbericht do 22-10, 2 beslissingen", "je agents"], w.wa
    assert "1 nieuw voorstel van De Normwacht wacht op je goedkeuring" in w.wa[1]["tekst"], w.wa[1]["tekst"]
    assert "De Ontwikkelaar" not in w.wa[1]["tekst"] and staat["voorstel_hoogste"] == 901, (w.wa[1], staat)
    w = bod5_wereld("ochtend-avond", inhoud)
    assert w.ronde()["voorstel_hoogste"] == 900 and len(w.wa) == 1, (w.staat(), w.wa)
    w.ronde(utc(2026, 10, 22, 15, 31))
    assert len(w.wa) == 2 and w.wa[1]["kop"] == "Avondbundel do 22-10", w.wa
    assert "1 nieuw voorstel van De Normwacht wacht op je goedkeuring" in w.wa[1]["tekst"], w.wa[1]["tekst"]
    w = bod5_wereld("ochtend-avond", ochtend_inhoud(ochtend_tekst()))
    assert w.ronde()["voorstel_hoogste"] == 899 and len(w.wa) == 1, (w.staat(), w.wa)


# --------------------------------------------------------------------------------------------- RZ2-04 ---
# Codex RZ2-bouwcontrole (21-10-2026): stopt het proces nadat WhatsApp een vast moment aanvaardde maar voor de stand op
# schijf staat, dan stuurde de volgende ronde hetzelfde bericht opnieuw. Nu het patroon van FR-179: voor het versturen
# een 'bezig'-record in het verzendspoor, na aanvaarding 'verzonden'.
class Gestopt(BaseException):
    """Het proces stopt (kill, stroom weg): wat hierna komt, loopt niet meer."""


def gestopte_ronde(w, moment, stop):
    """Een ronde die stopt zodra WhatsApp het bericht aanvaardde waarvan stop(kop) waar is: het bericht is weg, maar de
    stand komt niet meer op schijf (bewaar doet niets, zoals na een kill)."""
    echt_stuur, echt_bewaar = B.whatsapp.stuur, B.bewaar

    def stuur(tekst, kop="je agents", voorrang=False):
        uit = echt_stuur(tekst, kop, voorrang)
        if stop(kop):
            raise Gestopt()
        return uit

    B.whatsapp.stuur, B.bewaar = stuur, lambda staat: None
    try:
        w.ronde(moment)
        raise AssertionError("de ronde had moeten stoppen na de aanvaarding")
    except Gestopt:
        pass
    finally:
        B.whatsapp.stuur, B.bewaar = echt_stuur, echt_bewaar


def onzeker(w, wat):
    return [n for n in (w.laatste().get("nood") or []) if n["tekst"] == f"{wat} van 2026-10-22: aflevering onzeker, nakijken"]


def test_rz2_04_ochtendbericht_onderbroken_na_aanvaarding_niet_opnieuw():
    """Het ochtendbericht is door WhatsApp aanvaard, dan stopt het proces voor het item opgepakt en de stand bewaard is.
    De volgende ronde stuurt het niet opnieuw, zet een nood voor claude-code, telt het item als afgehandeld (opgepakt,
    laatste_id erover) en stuurt om 11:00 geen terugval, want er ging misschien wel een ochtendbericht weg."""
    w = t70_wereld()
    gestopte_ronde(w, utc(2026, 10, 22, 7, 35), lambda kop: kop.startswith("Ochtendbericht"))
    assert len(w.wa) == 1 and w.item(103)["status"] == "klaar", (w.wa, w.item(103))
    assert not (w.staat().get("ochtend") or {}).get("2026-10-22"), "de stand kwam niet op schijf"
    staat = w.ronde(utc(2026, 10, 22, 7, 36))
    assert len(w.wa) == 1, f"hetzelfde ochtendbericht opnieuw verstuurd: {w.wa[1:]}"
    nood = onzeker(w, "Ochtendbericht")
    assert nood and nood[0]["wie"] == "claude-code", w.noodteksten()
    assert w.item(103)["status"] == "opgepakt" and "onzeker" in w.item(103)["opgepakt_door"], w.item(103)
    assert staat["laatste_id"] == 103 and staat["ochtend"]["2026-10-22"]["onzeker"], staat
    w.ronde(utc(2026, 10, 22, 9, 1))             # 11:01 Brussel
    assert len(w.wa) == 1, f"geen terugval na een onzeker ochtendbericht: {w.wa[1:]}"
    assert onzeker(w, "Ochtendbericht") and "Geen ochtendbericht van De Regisseur om 11:00" not in w.noodteksten(), \
        w.noodteksten()


def test_rz2_04_terugval_onderbroken_na_aanvaarding_niet_opnieuw():
    w = Wereld(utc(2026, 10, 22, 9, 1), staat={"laatste_id": 1, "voorstel_hoogste": 0, "ochtend": {}, "avond": {},
                                                "bundel_vanaf": "2026-10-22T07:00:00+00:00"})
    gestopte_ronde(w, utc(2026, 10, 22, 9, 1), lambda kop: kop.endswith("geen ochtendbericht"))
    assert len(w.wa) == 1 and not (w.staat().get("ochtend") or {}).get("2026-10-22"), (w.wa, w.staat())
    staat = w.ronde(utc(2026, 10, 22, 9, 2))
    assert len(w.wa) == 1, f"dezelfde terugval opnieuw verstuurd: {w.wa[1:]}"
    nood = onzeker(w, "Terugval")
    assert nood and nood[0]["wie"] == "claude-code", w.noodteksten()
    assert staat["ochtend"]["2026-10-22"]["terugval_onzeker"], staat
    w.ronde(utc(2026, 10, 22, 12, 0))
    assert len(w.wa) == 1 and onzeker(w, "Terugval"), (w.wa, w.noodteksten())


def test_rz2_04_avondbundel_onderbroken_na_aanvaarding_niet_opnieuw():
    w = t75_wereld(utc(2026, 10, 22, 15, 2))
    w.zet(400, "signaal", "Proefsignaal van de middag", ts="2026-10-22T10:00:00+00:00")
    w.zet(401, "signaal", "Mail 17:00: open mch@ 3; wachten werken", van="mail-regisseur",
          uniek="mailupdate:2026-10-22:17:00", ts="2026-10-22T15:01:00+00:00")
    gestopte_ronde(w, utc(2026, 10, 22, 15, 2), lambda kop: kop.startswith("Avondbundel"))
    assert len(w.wa) == 1 and not w.staat()["avond"], (w.wa, w.staat())
    staat = w.ronde(utc(2026, 10, 22, 15, 3))
    assert len(w.wa) == 1, f"dezelfde avondbundel opnieuw verstuurd: {w.wa[1:]}"
    nood = onzeker(w, "Avondbundel")
    assert nood and nood[0]["wie"] == "claude-code", w.noodteksten()
    assert staat["avond"]["2026-10-22"]["onzeker"], staat
    assert staat["bundel_vanaf"] == "2026-10-22T07:40:00+00:00", "onzeker: de bundel schuift niet op, er verdwijnt niets"
    w.ronde(utc(2026, 10, 22, 15, 40))           # 17:40: zonder spoor ging hij hier zeker opnieuw
    assert len(w.wa) == 1 and onzeker(w, "Avondbundel"), (w.wa, w.noodteksten())


def test_rz2_04_slotbundel_onderbroken_na_aanvaarding_niet_opnieuw():
    """Tegenproef van 22-10-2026: de slotbundel (terug naar 'uit', BOD-2) is het vierde vaste moment en had hetzelfde
    venster. Aanvaard door WhatsApp, dan een stop voor de stand op schijf stond, en de volgende ronde stuurde hem opnieuw.
    Nu door hetzelfde verzendspoor, met de grens bundel_tot in de sleutel (een tweede omschakeling op dezelfde dag krijgt
    een eigen sleutel). 'bezig' wordt onzeker en een nood; in 'uit' draagt geen latere bundel bundel_vanaf nog, dus die
    gaat weg. 'verzonden' in het spoor zonder stand: ook weg, zonder nood."""
    w = t73_wereld("ochtend-avond")
    w.ronde()
    w.werkwijze = WERKWIJZE_UIT
    gestopte_ronde(w, utc(2026, 10, 22, 12, 1), lambda kop: kop.startswith("Bundel"))
    assert [m["kop"] for m in w.wa] == ["Bundel do 22-10"] and w.staat()["bundel_vanaf"], (w.wa, w.staat())
    staat = w.ronde(utc(2026, 10, 22, 12, 2))
    assert [m["kop"] for m in w.wa] == ["Bundel do 22-10"], f"dezelfde slotbundel opnieuw verstuurd: {w.wa[1:]}"
    nood = onzeker(w, "Slotbundel")
    assert nood and nood[0]["wie"] == "claude-code", w.noodteksten()
    assert "bundel_vanaf" not in staat and "bundel_tot" not in staat, staat
    w.ronde(utc(2026, 10, 22, 16, 0))
    assert len(w.wa) == 1 and onzeker(w, "Slotbundel"), (w.wa, w.noodteksten())
    # verzonden in het spoor, de stand verloren: niets opnieuw en niets onzeker
    w = t73_wereld("ochtend-avond")
    w.ronde()
    w.werkwijze = WERKWIJZE_UIT
    B.bellen.spoor_schrijven(B.verzendspoor(), "slotbundel:2026-10-22:200", "2026-10-22T12:01:00+00:00")
    staat = w.ronde(utc(2026, 10, 22, 12, 2))
    assert not w.wa and not onzeker(w, "Slotbundel") and "bundel_vanaf" not in staat, (w.wa, w.noodteksten(), staat)


def test_rz2_04_verzonden_in_het_spoor_ook_als_de_stand_verloren_is():
    """Het ochtendbericht is weg en 'verzonden' staat in het spoor; het proces stopt bij het oppakken op het bord, voor
    de stand bewaard is. De volgende ronde stuurt niets en meldt niets onzekers: het spoor zegt dat het aankwam."""
    w = t70_wereld()
    echt_call, echt_bewaar = w.call, B.bewaar

    def call(pad, payload=None, method=None):
        if pad.endswith("/opgepakt"):
            raise Gestopt()
        return echt_call(pad, payload, method)

    B.bord.call, B.bewaar = call, lambda staat: None
    try:
        w.ronde()
    except Gestopt:
        pass
    finally:
        B.bord.call, B.bewaar = echt_call, echt_bewaar
    assert len(w.wa) == 1 and w.item(103)["status"] == "klaar" and not w.staat()["ochtend"], (w.wa, w.staat())
    staat = w.ronde(utc(2026, 10, 22, 7, 36))
    assert len(w.wa) == 1 and not onzeker(w, "Ochtendbericht"), (w.wa, w.noodteksten())
    assert w.item(103)["status"] == "opgepakt" and w.item(103)["opgepakt_door"] == "bode", w.item(103)
    assert staat["laatste_id"] == 103 and staat["ochtend"]["2026-10-22"]["verzonden"], staat


def test_rz2_04_mislukt_versturen_is_niet_onzeker():
    """Weigeren alle kanalen een vast moment, dan staat 'mislukt' na het 'bezig'-record: de volgende ronde probeert
    opnieuw, zonder nood over een onzekere aflevering (T69 toetst hetzelfde voor het ochtendbericht)."""
    for moment, later, wat in ((utc(2026, 10, 22, 9, 1), utc(2026, 10, 22, 9, 2), "Terugval"),
                               (utc(2026, 10, 22, 15, 31), utc(2026, 10, 22, 15, 32), "Avondbundel")):
        w = t75_wereld(moment) if wat == "Avondbundel" else \
            Wereld(moment, staat={"laatste_id": 1, "voorstel_hoogste": 0, "ochtend": {}, "avond": {},
                                  "bundel_vanaf": "2026-10-22T07:00:00+00:00"})
        w.zet(400, "signaal", "Proefsignaal van de middag", ts="2026-10-22T08:00:00+00:00")
        w.wa_fout = lambda tekst, kop, voorrang: RuntimeError("Meta nagebootst 500")
        w.ronde()
        assert not w.wa and not onzeker(w, wat), (wat, w.noodteksten())
        w.wa_fout = None
        w.ronde(later)
        assert len(w.wa) == 1 and w.wa[0]["voorrang"] and not onzeker(w, wat), (wat, w.wa, w.noodteksten())


def test_rz2_04_zonder_schrijfbaar_spoor_geen_vast_moment():
    """Is het 'bezig'-record niet te schrijven, dan gaat het ochtendbericht niet weg (FR-179: zonder spoor niet bellen),
    met een nood; laatste_id blijft ervoor. Lukt het spoor weer, dan gaat het alsnog."""
    w = t70_wereld()
    echt = B.bellen.spoor_schrijven

    def kapot(pad, *a, **k):
        raise OSError("schijf nagebootst vol")

    B.bellen.spoor_schrijven = kapot
    try:
        staat = w.ronde()
    finally:
        B.bellen.spoor_schrijven = echt
    assert not w.wa and w.item(103)["status"] == "klaar" and staat["laatste_id"] == 102, (w.wa, staat)
    assert any("verzendspoor niet te schrijven" in t for t in w.noodteksten()), w.noodteksten()
    w.ronde(utc(2026, 10, 22, 7, 36))
    assert len(w.wa) == 1 and w.item(103)["status"] == "opgepakt", w.wa


def test_rz2_04_onleesbaar_spoor_is_geen_leeg_spoor():
    """Een verzendspoor dat er is maar niet te lezen valt (hier een map), kan een verzending bevatten (A33): geen
    ochtendbericht, geen terugval, geen avondbundel, wel een nood per vast moment."""
    echt = B.verzendspoor
    for moment, wat in ((utc(2026, 10, 22, 7, 35), "Ochtendbericht"), (utc(2026, 10, 22, 9, 1), "Terugval"),
                        (utc(2026, 10, 22, 15, 31), "Avondbundel")):
        w = t70_wereld() if wat == "Ochtendbericht" else t75_wereld(moment) if wat == "Avondbundel" else \
            Wereld(moment, staat={"laatste_id": 1, "voorstel_hoogste": 0, "ochtend": {}, "avond": {},
                                  "bundel_vanaf": "2026-10-22T07:00:00+00:00"})
        w.zet(400, "signaal", "Proefsignaal van de middag", ts="2026-10-22T08:00:00+00:00")
        B.verzendspoor = lambda: MAP
        try:
            w.ronde(moment)
        finally:
            B.verzendspoor = echt
        assert not w.wa, (wat, w.wa)
        assert f"{wat} van 2026-10-22 niet verstuurd: verzendspoor onleesbaar (IsADirectoryError); kijk de schijf van " \
               "mijnagents-data na" in w.noodteksten(), (wat, w.noodteksten())


def test_rz2_04_het_spoor_groeit_niet():
    """Het verzendspoor houdt alleen de laatste dagen (OCHTEND_DAGEN plus een), zoals de stand; ouder gaat weg."""
    w = t75_wereld(utc(2026, 10, 22, 10, 0))
    B.bellen.spoor_schrijven(B.verzendspoor(), "avondbundel:2026-10-15", "2026-10-15T15:02:00+00:00")
    B.bellen.spoor_schrijven(B.verzendspoor(), "avondbundel:2026-10-21", "2026-10-21T15:02:00+00:00")
    w.ronde()
    assert [json.loads(r)["sleutel"] for r in open(B.verzendspoor())] == ["avondbundel:2026-10-21"], \
        open(B.verzendspoor()).read()


# --------------------------------------------------------------------------------------------- RZ3-02 ---
# Codex RZ3-herstelcontrole (22-10-2026): BUNDELEN stond standaard op 'ochtend-avond' in de code. Een volledige push naar
# main kon berichten dus uitstellen voor Mehdi zijn nieuwe werkwijze goedkeurde. Besluit van de regie: de stand volgt
# uit de werkwijze op het bord, met een vaste regel; al het andere is 'uit', daar wordt niets vastgehouden.
def test_rz3_02_de_stand_komt_uit_de_werkwijze():
    assert B.stand_bundelen(WERKWIJZE) == "ochtend-avond"
    assert B.stand_bundelen(WERKWIJZE.replace("\n", "\r\n")) == "ochtend-avond", "regeleinden van Windows"
    kop = "## De stand van BUNDELEN"
    for naam, tekst in (("werkwijze 2.5", WERKWIJZE_25), ("zonder de regel", WERKWIJZE_UIT), ("leeg", ""),
                        ("onleesbaar", None), ("een andere stand", WERKWIJZE.replace(REGEL, "BUNDELEN: uit")),
                        ("optie C", WERKWIJZE.replace(REGEL, "BUNDELEN: ochtend")),
                        ("met een toevoeging", WERKWIJZE.replace(REGEL, REGEL + " vanaf maandag")),
                        ("als lijstpunt", WERKWIJZE.replace(REGEL, "- " + REGEL)),
                        ("ingesprongen", WERKWIJZE.replace(REGEL, "    " + REGEL)),
                        ("met een gelijkteken", WERKWIJZE.replace(REGEL, 'BUNDELEN = "ochtend-avond"')),
                        ("buiten de sectie", WERKWIJZE_UIT.rstrip("\n") + "\n\n" + REGEL + "\n"),
                        ("twee keer", WERKWIJZE.replace(REGEL, REGEL + "\n\n" + REGEL)),
                        ("tegenstrijdig", WERKWIJZE.replace(REGEL, REGEL + "\n\nBUNDELEN: uit")),
                        ("de kop twee keer", WERKWIJZE.rstrip("\n") + f"\n\n{kop}\n\n{REGEL}\n"),
                        ("de kop met opmaak", WERKWIJZE.replace(kop, kop.replace("BUNDELEN", "**BUNDELEN**"))),
                        ("in een HTML-commentaar", WERKWIJZE_UIT + f"\n<!--\n{REGEL}\n-->\n"),
                        ("in de sectie verborgen", WERKWIJZE.replace(REGEL, f"<!--\n{REGEL}\n-->")),
                        ("in een codeblok", WERKWIJZE.replace(REGEL, f"```\n{REGEL}\n```"))):
        assert B.stand_bundelen(tekst) == "uit", naam
    # Tegenproef van 22-10-2026: een tweede stand in een andere schrijfwijze telde niet mee, want alleen de letterlijke
    # tekst "BUNDELEN:" telde. Mehdi las dan twee standen terwijl de code bundelde: de onveilige kant. Nu telt elke regel
    # die BUNDELEN noemt, zoals hij ze op het bord leest: zonder entiteiten, onzichtbare tekens, hoofdletters of leestekens.
    tweede = {"in kleine letters": "Bundelen: uit", "met een spatie": "BUNDELEN : uit", "zonder dubbelepunt": "BUNDELEN uit",
              "met een HTML-entiteit": "&#66;UNDELEN: uit", "met een nulbreedteteken": "BUN​DELEN: uit",
              "met een volle-breedte dubbelepunt": "BUNDELEN：uit", "met spaties tussen de letters": "B U N D E L E N: uit",
              "in volle-breedte letters": "ＢＵＮＤＥＬＥＮ: uit",
              "als zin": "De stand van BUNDELEN is uit."}
    for naam, regel in tweede.items():
        assert B.stand_bundelen(WERKWIJZE.replace(REGEL, REGEL + "\n\n" + regel)) == "uit", f"tweede regel {naam}"
    voor_de_kop = "\n" + kop + "\n"
    for naam, tekst in (("een tweede kop in kleine letters", WERKWIJZE.rstrip("\n") + "\n\n## De stand van bundelen\n\nDe stand is uit.\n"),
                        ("een stand in een andere sectie, als lijstpunt",
                         WERKWIJZE.replace("\n## Wat ik nooit doe\n", "\n1. Bundelen: uit\n\n## Wat ik nooit doe\n", 1)),
                        ("een stand voor de kop", WERKWIJZE.replace(voor_de_kop, "\n> **BUNDELEN**: uit\n" + voor_de_kop, 1)),
                        ("een codeblok dat voor de kop opengaat", WERKWIJZE.replace(voor_de_kop, "\n```" + voor_de_kop, 1))):
        assert tekst != WERKWIJZE and B.stand_bundelen(tekst) == "uit", naam
    # wat Mehdi gewoon leest, blijft gewoon: een regel met tab of spaties achteraan, en de kop met spaties achteraan
    for naam, tekst in (("tab achteraan", WERKWIJZE.replace(REGEL, REGEL + "\t")),
                        ("kop met spaties achteraan", WERKWIJZE.replace(voor_de_kop, "\n" + kop + "  \n", 1))):
        assert B.stand_bundelen(tekst) == "ochtend-avond", naam


def rz3_02_wereld(werkwijze):
    w = Wereld(utc(2026, 10, 22, 10, 0), werkwijze=werkwijze,
               staat={"laatste_id": 199, "voorstel_hoogste": 11, "avond": {},
                      "ochtend": {"2026-10-22": {"verzonden": "2026-10-22T09:40:00+02:00", "klaarzet_id": 150, "opgepakt": True}}},
               voorstellen=[(i, "ontwikkelaar") for i in range(1, 12)])
    w.zet(200, "signaal", "Proefonderwerp Omega voor Proefpersoon Zeta", ts="2026-10-22T10:00:00+00:00")
    return w


def test_rz3_02_werkwijze_25_houdt_niets_vast_met_de_regel_wel():
    """Werkwijze 2.5 op het bord (van voor het bundelen) en de code van nu: het signaal gaat meteen los en De Bode houdt
    niets vast. Met de regel in de werkwijze wacht het op het vaste moment. Zo bundelt De Bode pas als Mehdi de nieuwe
    werkwijze met een klik op het bord zette, ook als de code al live staat. De gelezen stand gaat mee als bron (N4)."""
    w = rz3_02_wereld(WERKWIJZE_25)
    staat = w.ronde()
    assert [m["kop"] for m in w.wa] == ["je agents"] and "Proefonderwerp Omega" in w.wa[0]["tekst"], w.wa
    assert staat["laatste_id"] == 200 and "bundel_vanaf" not in staat, staat
    kennis = [p for pad, p in w.gestuurd if pad.endswith("/kennis")]
    assert kennis and "BUNDELEN" in kennis[-1]["bron"], kennis
    w.ronde(utc(2026, 10, 22, 15, 31))           # 17:31: geen avondbundel in 'uit'
    assert len(w.wa) == 1, w.wa[1:]
    # met de regel: hetzelfde signaal wacht en komt in de avondbundel
    w = rz3_02_wereld(WERKWIJZE)
    staat = w.ronde()
    assert not w.wa and staat["laatste_id"] == 200 and staat["bundel_vanaf"], (w.wa, staat)
    w.ronde(utc(2026, 10, 22, 15, 31))
    assert [m["kop"] for m in w.wa] == ["Avondbundel do 22-10"] and "Proefonderwerp Omega" in w.wa[0]["tekst"], w.wa


def test_rz3_02_terug_naar_uit_via_de_werkwijze_stuurt_de_slotbundel():
    """Mehdi zet op het bord een werkwijze zonder de regel terug (hier 2.5). Wat de bundelstand al vasthield, gaat eerst
    als slotbundel (BOD-2, de bestaande slotbundel_sturen); wat daarna binnenkomt, gaat los. Er verdwijnt niets."""
    w = rz3_02_wereld(WERKWIJZE)
    staat = w.ronde()
    assert not w.wa and staat["bundel_vanaf"], (w.wa, staat)
    w.werkwijze = WERKWIJZE_25
    w.zet(201, "signaal", "Proefsignaal na het terugzetten", ts="2026-10-22T11:30:00+00:00")
    staat = w.ronde(utc(2026, 10, 22, 12, 0))
    assert [m["kop"] for m in w.wa] == ["Bundel do 22-10", "je agents"], w.wa
    assert "Proefonderwerp Omega" in w.wa[0]["tekst"] and "na het terugzetten" not in w.wa[0]["tekst"], w.wa[0]
    assert "na het terugzetten" in w.wa[1]["tekst"] and "Proefonderwerp Omega" not in w.wa[1]["tekst"], w.wa[1]
    assert "bundel_vanaf" not in staat and "bundel_tot" not in staat and staat["laatste_id"] == 201, staat
    w.ronde(utc(2026, 10, 22, 12, 1))
    assert len(w.wa) == 2, f"de slotbundel gaat een keer: {w.wa[2:]}"


def test_rz3_02_droog_leest_de_stand_uit_de_werkwijze():
    """Droog leest de werkwijze zelf, alleen lezend, en zegt welke stand ze geeft; onleesbaar is 'uit', met een nood in
    de uitvoer. Droog schrijft nooit iets."""
    for werkwijze, stand in ((WERKWIJZE, "ochtend-avond"), (WERKWIJZE_25, "uit"), (http(500), "uit")):
        w = rz3_02_wereld(werkwijze)
        with redirect_stdout(io.StringIO()) as uit, redirect_stderr(io.StringIO()):
            B.main(droog=True)
        assert f"(droog) stand {stand};" in uit.getvalue(), (stand, uit.getvalue()[-400:])
        assert not w.wa and not w.hartslagen, (w.wa, w.hartslagen)
    assert "Werkwijze lezen mislukt" in uit.getvalue(), uit.getvalue()[-400:]


# --------------------------------------------------------------------------------------------- RZ4-03 ---
# Codex RZ4-herstelcontrole (22-10-2026): de leesstand (laatste_id) schuift pas op als elk item erboven meegenomen is,
# verstuurd of in een bundel. Elke toets hieronder faalde eerst op de code van 6dfbafa.
def test_rz4_03_omschakeling_met_een_onverstuurd_item_ouder_dan_24_uur():
    """Signaal 101 van eergisteravond ging nooit weg (zijn bericht mislukte, of het kwam na een verloren stand) en het
    laatst afgehandelde item 100 staat niet meer op de pagina van het bord. Bij de omschakeling naar 'ochtend-avond' zette
    bundel_begin de grens toen 24 uur terug, voorbij 101; melding_groep telde 101 als bundelwerk en laatste_id schoof
    erover: het bereikte Mehdi nooit. Nu begint de bundel voor het oudste item dat nog niet weg is."""
    w = Wereld(utc(2026, 10, 22, 4, 0), staat={"laatste_id": 100, "voorstel_hoogste": 0, "wacht": []})
    w.zet(101, "signaal", "Proefonderwerp Omega van eergisteravond", ts="2026-10-20T21:00:00+00:00")
    staat = w.ronde()                            # 06:00 Brussel, de eerste ronde in de bundelstand
    assert not w.wa, w.wa
    assert datetime.fromisoformat(staat["bundel_vanaf"]) < utc(2026, 10, 20, 21, 0), staat
    w.zet(102, "ochtendbericht", "Ochtendbericht do 22-10, 2 beslissingen", van="regisseur",
          uniek="ochtendbericht:2026-10-22", inhoud=ochtend_inhoud(ochtend_tekst()), ts="2026-10-22T07:30:00+00:00")
    staat = w.ronde(utc(2026, 10, 22, 7, 35))
    assert len(w.wa) == 1 and w.wa[0]["tekst"] == ochtend_tekst() + "\nGebundeld: signaal van De Normwacht; alles op het bord", w.wa
    assert staat["laatste_id"] == 102, staat
    w.ronde(utc(2026, 10, 22, 15, 31))
    assert len(w.wa) == 1, f"een keer, niet nog eens in de avondbundel: {w.wa[1:]}"


def test_rz4_03_melding_groep_schuift_niet_over_een_item_dat_in_geen_bundel_zit():
    """Een item boven laatste_id dat niet in de lopende bundel valt (ts voor bundel_vanaf, of geen leesbare ts) en ook in
    geen verstuurde bundel stond, telt in de bundelstand niet als afgehandeld: het gaat los, zoals in 'uit'. Wat in een
    verstuurde bundel stond (staat['gebundeld']) of in de lopende bundel valt, telt wel."""
    oud = {"id": 101, "soort": "signaal", "titel": "a", "van": "normwacht", "ts": "2026-10-20T21:00:00+00:00"}
    staat = {"laatste_id": 100, "bundel_vanaf": "2026-10-21T04:00:00+00:00"}
    groep, tot, rest = B.melding_groep([oud], False, staat, "ochtend-avond")
    assert [it["id"] for it in groep] == [101] and tot == 101 and rest == 0, (groep, tot, rest)
    groep, tot, _ = B.melding_groep([dict(oud, ts="")], False, staat, "ochtend-avond")
    assert [it["id"] for it in groep] == [101], "zonder leesbare ts komt het in geen bundel"
    groep, tot, _ = B.melding_groep([oud], False, staat | {"gebundeld": [101]}, "ochtend-avond")
    assert groep == [] and tot == 101, (groep, tot)
    groep, tot, _ = B.melding_groep([dict(oud, ts="2026-10-21T05:00:00+00:00")], False, staat, "ochtend-avond")
    assert groep == [] and tot == 101, "in de lopende bundel: afgehandeld tot het vaste moment"
    groep, tot, _ = B.melding_groep([oud], True, {"laatste_id": 0, "bundel_vanaf": staat["bundel_vanaf"]}, "ochtend-avond")
    assert groep == [] and tot == 101, "zonder stand blijft de eerste ronde zoals ze was (A31)"


def test_rz4_03_wat_in_een_verstuurde_bundel_stond_gaat_niet_nog_eens_los():
    """Het ochtendbericht van 06:30 wacht in de stille uren, dus blijft laatste_id ervoor staan; signaal 501 erachter komt
    om 07:01 in de regel Gebundeld en bundel_vanaf schuift erover. De Bode onthoudt 501 in staat['gebundeld'] tot
    laatste_id erover schuift, zodat het niet ook nog los gaat."""
    w = Wereld(utc(2026, 10, 22, 4, 30), staat={"laatste_id": 499, "voorstel_hoogste": 0, "avond": {}, "ochtend": {},
                                                 "bundel_vanaf": "2026-10-21T15:00:00+00:00"})
    w.zet(500, "ochtendbericht", "Ochtendbericht do 22-10, 2 beslissingen", van="regisseur",
          uniek="ochtendbericht:2026-10-22", inhoud=ochtend_inhoud(ochtend_tekst()), ts="2026-10-22T04:28:00+00:00")
    w.zet(501, "signaal", "Proefsignaal achter het ochtendbericht", ts="2026-10-22T04:29:00+00:00")
    staat = w.ronde()                            # 06:30 Brussel: het ochtendbericht wacht
    assert not w.wa and staat["laatste_id"] == 499, (w.wa, staat)
    staat = w.ronde(utc(2026, 10, 22, 5, 1))     # 07:01 Brussel
    assert len(w.wa) == 1 and w.wa[0]["tekst"].endswith("\nGebundeld: signaal van De Normwacht; alles op het bord"), w.wa
    assert staat["laatste_id"] == 501 and "gebundeld" not in staat, staat
    w.ronde(utc(2026, 10, 22, 5, 2))
    assert len(w.wa) == 1, f"niet nog eens los: {w.wa[1:]}"


def rz4_03_volle_pagina():
    """Een volle pagina (KLAARZET_N agendazaken, die niet naar Mehdi gaan) boven signaal 100, dat nog niet weg is."""
    w = Wereld(utc(2026, 10, 22, 10, 0), stand="uit", staat={"laatste_id": 99, "voorstel_hoogste": 0, "avond": {},
                                                              "ochtend": {"2026-10-22": {"verzonden": "x", "opgepakt": True}}})
    w.zet(100, "signaal", "Proefsignaal onder de pagina", ts="2026-10-22T09:00:00+00:00")
    for i in range(B.KLAARZET_N):
        w.zet(1000 + i, "signaal", f"Proefafspraak {i}", van="agenda-wacht", ts="2026-10-22T09:30:00+00:00")
    return w


def test_rz4_03_een_item_onder_de_volle_pagina_wordt_alsnog_opgehaald():
    """Het bord geeft de nieuwste KLAARZET_N items. Ligt zelfs het oudste daarvan boven laatste_id, dan blader ik terug
    met tot_id tot laatste_id. Tot 22-10-2026 schoof laatste_id over wat eronder viel (alleen een nood)."""
    w = rz4_03_volle_pagina()
    staat = w.ronde()
    assert len(w.wa) == 1 and "Proefsignaal onder de pagina" in w.wa[0]["tekst"], w.wa
    assert staat["laatste_id"] == 1000 + B.KLAARZET_N - 1, staat
    assert any("tot_id=1000" in pad for pad, _ in w.gestuurd), "teruggebladerd vanaf het oudste item op de pagina"
    assert not any("klaarzet-items" in t for t in w.noodteksten()), w.noodteksten()


def test_rz4_03_kan_ik_niet_terugbladeren_dan_blijft_de_leesstand_staan():
    """Geeft het bord de items onder de pagina niet (een fout, of een bord van voor tot_id), dan schuift laatste_id niet
    op en gaat er geen gewoon bericht weg dat de volgende ronde opnieuw zou komen; een oproep op de pagina gaat wel, een
    keer (alarm_gemeld). Lukt het daarna, dan komt het signaal eronder alsnog."""
    for kapot in ("tot_id_negeren", "tot_id_fout"):
        w = rz4_03_volle_pagina()
        w.zet(1000 + B.KLAARZET_N, "oproep", "Dringende mail van een proefafzender", van="mail-regisseur")
        setattr(w, kapot, True)
        staat = w.ronde()
        assert w.alarmen == [[1000 + B.KLAARZET_N]] and len(w.wa) == 1 and "Dringende mail" in w.wa[0]["tekst"], (kapot, w.wa)
        assert staat["laatste_id"] == 99 and staat["alarm_gemeld"] == [1000 + B.KLAARZET_N], (kapot, staat)
        assert any("klaarzet-items" in t for t in w.noodteksten()), (kapot, w.noodteksten())
        setattr(w, kapot, False)
        staat = w.ronde(utc(2026, 10, 22, 10, 1))
        assert len(w.wa) == 2 and "Proefsignaal onder de pagina" in w.wa[1]["tekst"], (kapot, w.wa)
        assert "Dringende mail" not in w.wa[1]["tekst"], (kapot, w.wa[1])
        assert staat["laatste_id"] == 1000 + B.KLAARZET_N and "alarm_gemeld" not in staat, (kapot, staat)


def rz4_03_lopende_bundel():
    """Signaal 100 valt in de lopende bundel (ts na bundel_vanaf), dus schuift laatste_id erover zonder bericht. Daarna
    zet De Agendawacht 250 items voor Mehdi klaar (die gaan niet naar hem), zodat 100 onder de pagina van het bord valt."""
    w = Wereld(utc(2026, 10, 22, 8, 0), staat={"laatste_id": 99, "voorstel_hoogste": 0, "avond": {},
                                                "ochtend": {"2026-10-22": {"verzonden": "x", "opgepakt": True}},
                                                "bundel_vanaf": "2026-10-22T05:00:00+00:00"})
    w.zet(100, "signaal", "Proefsignaal Zeta in de lopende bundel", ts="2026-10-22T07:59:00+00:00")
    staat = w.ronde()
    assert not w.wa and staat["laatste_id"] == 100, (w.wa, staat)
    for i in range(250):
        w.zet(1000 + i, "signaal", f"Proefafspraak {i}", van="agenda-wacht", ts="2026-10-22T12:00:00+00:00")
    staat = w.ronde(utc(2026, 10, 22, 12, 0))
    assert not w.wa and staat["laatste_id"] == 1249, (w.wa, staat)
    return w


def test_rz4_03_de_lopende_bundel_wordt_onder_de_pagina_aangevuld():
    """Tegenproef op RZ4-03 (22-10-2026): in_bundel telt een item met een ts na bundel_vanaf als 'in een bundel', en
    laatste_id schuift erover. Maar de bundel zelf kwam alleen uit de eerste pagina van het bord. Viel het item daar
    onder, dan ging om 17:31 geen avondbundel, had het ochtendbericht geen regel Gebundeld, en schoof bundel_vanaf er
    toch over: het signaal bereikte Mehdi nooit, stil. Nu bladert De Bode terug met tot_id tot de lopende bundel
    helemaal gelezen is, en noemt de avondbundel het signaal, een keer."""
    w = rz4_03_lopende_bundel()
    staat = w.ronde(utc(2026, 10, 22, 15, 31))   # 17:31 Brussel
    assert len(w.wa) == 1 and w.wa[0]["kop"] == "Avondbundel do 22-10", w.wa
    assert "Proefsignaal Zeta in de lopende bundel (van De Normwacht)" in w.wa[0]["tekst"], w.wa[0]["tekst"]
    assert "er kan meer zijn" not in w.wa[0]["tekst"], w.wa[0]["tekst"]
    assert datetime.fromisoformat(staat["bundel_vanaf"]) == utc(2026, 10, 22, 15, 31), staat
    assert any("tot_id=1050" in pad for pad, _ in w.gestuurd), "teruggebladerd onder de pagina"
    assert not any("lopende bundel" in t for t in w.noodteksten()), w.noodteksten()
    w.zet(2000, "ochtendbericht", "Ochtendbericht vr 23-10, 2 beslissingen", van="regisseur",
          uniek="ochtendbericht:2026-10-23", inhoud=ochtend_inhoud(ochtend_tekst()), ts="2026-10-23T05:30:00+00:00")
    w.ronde(utc(2026, 10, 23, 5, 35))
    assert len(w.wa) == 2 and w.wa[1]["tekst"] == ochtend_tekst(), f"niet nog eens in het ochtendbericht: {w.wa[1:]}"


def test_rz4_03_kan_ik_de_lopende_bundel_niet_aanvullen_dan_schuift_ze_niet_op():
    """Kan De Bode de lopende bundel niet helemaal lezen (het terugbladeren faalt), dan zegt een vast moment dat er meer
    kan zijn, en schuift bundel_vanaf niet over wat hij niet las; met een nood. Lukt het later, dan komt het signaal
    alsnog mee."""
    w = rz4_03_lopende_bundel()
    w.tot_id_fout = True
    staat = w.ronde(utc(2026, 10, 22, 15, 31))
    assert len(w.wa) == 1 and w.wa[0]["kop"] == "Avondbundel do 22-10" and "er kan meer zijn" in w.wa[0]["tekst"], w.wa
    assert staat["bundel_vanaf"] == "2026-10-22T05:00:00+00:00", staat
    assert any("lopende bundel" in t for t in w.noodteksten()), w.noodteksten()
    w.zet(2000, "ochtendbericht", "Ochtendbericht vr 23-10, 2 beslissingen", van="regisseur",
          uniek="ochtendbericht:2026-10-23", inhoud=ochtend_inhoud(ochtend_tekst()), ts="2026-10-23T05:30:00+00:00")
    staat = w.ronde(utc(2026, 10, 23, 5, 35))
    assert len(w.wa) == 2 and w.wa[1]["tekst"] == ochtend_tekst() + "\nGebundeld: onbekend of meer; alles op het bord", w.wa[1:]
    assert staat["bundel_vanaf"] == "2026-10-22T05:00:00+00:00", staat
    w.tot_id_fout = False
    staat = w.ronde(utc(2026, 10, 23, 15, 31))
    assert len(w.wa) == 3 and "Proefsignaal Zeta in de lopende bundel" in w.wa[2]["tekst"], w.wa[2:]
    assert datetime.fromisoformat(staat["bundel_vanaf"]) == utc(2026, 10, 23, 15, 31), staat
    assert not any("lopende bundel" in t for t in w.noodteksten()), w.noodteksten()


# ------------------------------------------------------------------------------------------------ droog ---
def test_a47_zoom_account_alleen_op_vaste_momenten():
    it = {"id": 481, "van": "zoom-wacht", "soort": "zoom-account", "titel": "Zoom-account week 44",
          "voor": "mehdi", "uniek": "zoom-account:2026-W44", "status": "klaar"}
    assert B.nieuwe_items([it], {"laatste_id": 480}, []) == [it]
    assert B.kort_item(it, LABELS) == "Zoom-account van De Zoomwacht"
    assert B.stand_bundelen(WERKWIJZE) == "ochtend-avond"
    assert B.is_bundelwerk(it) and not B.is_alarm(it)
    assert B.apart(it, "ochtend-avond") and not B.apart(it, "uit")


def test_droog_stuurt_niets_en_schrijft_niets():
    w = t70_wereld()
    voor = open(B.STAAT, "rb").read()
    with redirect_stdout(io.StringIO()) as uit, redirect_stderr(io.StringIO()):
        B.main(droog=True)
    assert not w.wa and not w.hartslagen and open(B.STAAT, "rb").read() == voor, (w.wa, w.hartslagen)
    assert w.item(103)["status"] == "klaar" and "zou het ochtendbericht 103 sturen" in uit.getvalue(), uit.getvalue()[-400:]
    assert not os.path.exists(B.verzendspoor()), "droog schrijft ook geen verzendspoor (RZ2-04)"


if __name__ == "__main__":
    import traceback
    goed = fout = 0
    for naam, f in sorted(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                with redirect_stderr(io.StringIO()):
                    f()
                goed += 1
                print(f"   geslaagd  {naam}")
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"   GEFAALD   {naam}")
                traceback.print_exc()
            finally:
                for n, fn in ECHT.items():
                    setattr(B.bellen, n, fn)
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)

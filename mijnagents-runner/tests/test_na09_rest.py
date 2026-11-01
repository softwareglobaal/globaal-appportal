"""NA09-rest (T-0075, 01-11-2026): de laatste plekken die een werkwijze van het bord met eigen code lazen, en de oudere
runners die buiten de gedeelde ronde liepen.

NA09 (16-10-2026) zette de regel in koppelingen/bord.py: zonder regelboek geen ronde, en onbekend is niet leeg. Bij het
nameten lazen nog zes plekken de werkwijze zelf, en maakten ze van onbekend een lege tekst; vier runners lazen streng,
maar buiten de ronde, zodat hun kennis (N4), de gedeelde lessen (N13) en de collega's (N14) ontbraken. Elke toets hier
faalt op de code van voor die datum (origin/main e3a3bbb).

Het bord is nagebootst op draadniveau: elke urllib.request.urlopen komt hier binnen, of een runner nu bord.call
gebruikt of zijn eigen urllib-code. Zo raakt dezelfde toets de oude en de nieuwe leesweg. Geen netwerk, geen taalmodel,
geen echte bestanden: HOME is een lege map.
Draaien: python3 mijnagents-runner/tests/test_na09_rest.py
"""
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
import types
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime

os.environ["HOME"] = tempfile.mkdtemp(prefix="na09-rest-thuis-")      # nooit een echt .env, slot of logboek
os.environ.setdefault("AGENDA_WHATSAPP_WACHTRIJ", os.path.join(tempfile.mkdtemp(prefix="aw-test-"), "agenda-whatsapp.json"))
HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
sys.path.insert(0, os.path.join(RUNNER, "mac"))
import bord  # noqa: E402

WW = "# Werkwijze\n\nRegel een.\n\n## Correcties van Mehdi\n\n## Afzenders met hoog belang\n"
ONBEKEND = "Werkwijze niet gelezen: onleesbaar antwoord van het bord"
NIET_OP_BORD = "Werkwijze niet gelezen: agent staat niet op het bord"
LEEG = "Werkwijze leeg op het bord"


def _http(code, pad="/api/agent/proef/werkwijze"):
    return urllib.error.HTTPError(f"http://127.0.0.1:3022{pad}", code, "proef", None, None)


class _Antwoord(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Draad:
    """Het bord zoals een runner het over de draad ziet.

    werkwijze: de tekst op het bord, een dict (rauw antwoord, {} is een antwoord zonder werkwijze) of een uitzondering;
    werkwijzen: per agent een afwijkende werkwijze; open_noden: wat /api/nood geeft (None: onbekend)."""

    def __init__(self, werkwijze=WW, werkwijzen=None, open_noden=(), agents=None):
        self.werkwijze = werkwijze
        self.werkwijzen = dict(werkwijzen or {})
        self.open_noden = None if open_noden is None else list(open_noden)
        self.agents = agents
        self.gestuurd = []
        self.fouten = {}            # pad -> lijst van uitzonderingen die de volgende oproepen op dat pad opwerpen
        self.na_fouten = {}         # idem, maar het bord nam het verzoek aan: het antwoord ging verloren
        self.gevraagd = []          # elk pad dat de runner probeerde, ook als het mislukte

    def urlopen(self, req, timeout=None, **_):
        url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
        deel = urllib.parse.urlsplit(url)
        pad = deel.path + (f"?{deel.query}" if deel.query else "")
        data = req.data if isinstance(req, urllib.request.Request) else None
        payload = json.loads(data.decode()) if data else None
        self.gevraagd.append(deel.path)
        antwoord = self.antwoord(deel.path, pad, payload)
        self.gestuurd.append((deel.path, payload))       # alleen wat het bord aannam
        if self.na_fouten.get(deel.path):
            raise self.na_fouten[deel.path].pop(0)
        return _Antwoord(json.dumps(antwoord).encode())

    def antwoord(self, pad, volledig, payload):
        if self.fouten.get(pad):
            fout = self.fouten[pad].pop(0)          # None: deze oproep lukt, de volgende uit de lijst niet
            if fout is not None:
                raise fout
        m = re.match(r"^/api/agent/([^/]+)/werkwijze$", pad)
        if m and payload is None:
            w = self.werkwijzen.get(m.group(1), self.werkwijze)
            if isinstance(w, Exception):
                raise w
            return w if isinstance(w, dict) else {"werkwijze": w}
        if pad == "/api/nood":
            if self.open_noden is None:
                raise urllib.error.URLError("noden onbekend (proef)")
            return {"nood": self.open_noden}
        if pad == "/api/agents":
            return [{"naam": n, "label": n, "type": "regie", "rol": "proef", "actief": 1}
                    for n in (self.agents if self.agents is not None else ["bode"])]
        if pad == "/api/klaarzet" and payload is None:
            return {"items": []}
        return {"ok": True, "nieuw": 0, "bestaand": 0}

    def statussen(self, naam=None):
        return [p for pad, p in self.gestuurd if pad == "/agent-status" and (naam is None or p.get("naam") == naam)]

    def kennis(self, naam):
        return [p for pad, p in self.gestuurd if pad == f"/api/agent/{naam}/kennis"]

    def logregels(self):
        return [r for pad, p in self.gestuurd if pad == "/api/logboek" for r in p["regels"]]


@contextmanager
def op_het_bord(draad):
    echt = urllib.request.urlopen
    urllib.request.urlopen = draad.urlopen
    try:
        with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            yield draad
    finally:
        urllib.request.urlopen = echt


@contextmanager
def vervangen(*drietallen):
    """(object, naam, waarde): tijdelijk vervangen, daarna terug zoals het was."""
    oud = [(o, n, o.__dict__.get(n, _GEEN) if isinstance(o, types.ModuleType) else getattr(o, n, _GEEN))
           for o, n, _ in drietallen]
    for o, n, w in drietallen:
        setattr(o, n, w)
    try:
        yield
    finally:
        for o, n, w in reversed(oud):
            if w is _GEEN:
                delattr(o, n)
            else:
                setattr(o, n, w)


_GEEN = object()


def _gestopt(draad, naam, nood, wie):
    laatste = draad.statussen(naam)[-1]
    assert laatste["status"] == "fout", f"{naam}: laatste hartslag {laatste['status']}, hoort fout (N11): {laatste}"
    met_nood = [s for s in draad.statussen(naam) if s.get("nood")]
    assert met_nood and {"tekst": nood, "wie": wie} in met_nood[-1]["nood"], f"{naam}: nood ontbreekt: {draad.statussen(naam)}"
    assert not draad.kennis(naam), f"{naam}: een ronde zonder regelboek meldt geen kennis (N4 slaagt anders voor niets)"


def _ronde_kennis(draad, naam):
    """De kennis die de gedeelde ronde meldt: werkwijze, gedeelde lessen en collega's (N4, N13, N14)."""
    k = draad.kennis(naam)
    assert k, f"{naam} meldde geen kennis: de gedeelde ronde liep niet (N4, N12)"
    bron = k[-1]["bron"]
    for stuk in ("werkwijze op het bord", "gedeelde lessen", "collega's op het bord"):
        assert stuk in bron, f"{naam}: '{stuk}' ontbreekt in de gemelde kennis ({bron}): de ronde liep niet (N13, N14)"
    return k[-1]


# ------------------------------------------------------------------------------------------------ De ronde zelf ---
def test_na49_stopsignaal_bij_het_afsluiten_blijft_niet_op_actief():
    """Codex NA49 (ronde 12): de ronde ving bij het afsluiten alleen Exception op. Kwam een SIGTERM (als SystemExit) of
    Ctrl-C binnen terwijl ze de kennis of het werkverslag verstuurde, dan ging de eindhartslag niet uit en bleef de agent
    op actief staan (N11). Voor De Fathomwacht ving haar eigen finally dat voordien op. Nu: fout, en het signaal gaat door
    (de exitcode van een time-out blijft 143)."""
    for onderbreking in (SystemExit(143), KeyboardInterrupt()):
        draad = Draad(open_noden=[{"naam": "proef", "tekst": "Oude nood", "wie": "mehdi"}])
        ag = bord.Agent("proef")

        def stop(*a, **k):
            raise onderbreking

        ag.kennis = stop
        with op_het_bord(draad):
            try:
                with ag.ronde("proef") as r:
                    r.nood("Nieuwe nood", wie="claude-code")
                doorgegaan = None
            except BaseException as e:  # noqa: BLE001
                doorgegaan = e
        assert doorgegaan is onderbreking, f"het signaal hoort door te gaan: {doorgegaan!r}"
        laatste = draad.statussen("proef")[-1]
        assert laatste["status"] == "fout" and type(onderbreking).__name__ in laatste["detail"], draad.statussen("proef")
        # na een signaal haalt de ronde de noodlijst niet meer op (overleg 13, X5): geen lijst, dus het bord sluit niets,
        # en wat ze vond staat in het detail
        assert "nood" not in laatste and "Nieuwe nood" in laatste["detail"], laatste


def test_na53_werkfout_en_stopsignaal_bij_het_afsluiten_blijven_allebei_zichtbaar():
    """Codex NA53 (ronde 13): brak het werk (ValueError) en kwam daarna bij het afsluiten een SIGTERM binnen, dan toonde
    de fouthartslag alleen het signaal, en ging het werkverslag niet weg. Nu noemt de hartslag beide, en gaat het verslag
    nog weg; het signaal gaat door."""
    draad = Draad(open_noden=[])
    ag = bord.Agent("proef")

    def stop(*a, **k):
        raise SystemExit(143)

    ag.kennis = stop
    with op_het_bord(draad):
        try:
            with ag.ronde("proef"):
                ag.log("proef", "fout", "halverwege stuk")
                raise ValueError("werk kapot")
        except BaseException as e:  # noqa: BLE001
            doorgegaan = e
    assert isinstance(doorgegaan, SystemExit) and doorgegaan.code == 143, repr(doorgegaan)
    laatste = draad.statussen("proef")[-1]
    assert laatste["status"] == "fout" and "ValueError: werk kapot" in laatste["detail"] \
        and "SystemExit" in laatste["detail"], laatste
    assert any(r["tekst"] == "halverwege stuk" for r in draad.logregels()), "het werkverslag ging niet weg"


def test_d1_werkverslag_in_hoogstens_een_poging():
    """Overleg 13, D1 (na Codex NA56 en NA60): het werkverslag gaat in hoogstens een poging naar het bord. Bewaren en
    opnieuw sturen (NA56) gaf een dubbel verslag als het antwoord verloren ging na een geslaagde boeking (NA60), want het
    bord herkent geen dubbels. Een mislukte of onderbroken poging wist de regels dus ook."""
    for fout, aangenomen in ((urllib.error.URLError("bord weg (proef)"), False), (TimeoutError("antwoord kwijt"), True),
                             (SystemExit(143), False)):
        draad = Draad()
        (draad.na_fouten if aangenomen else draad.fouten)["/api/logboek"] = [fout]
        ag = bord.Agent("proef")
        with op_het_bord(draad):
            ag.log("proef", "bron", "regel een")
            try:
                ag.log_verstuur()
            except SystemExit:
                pass
            assert not ag._log, f"na {fout!r} hoort de regel weg te zijn: geen tweede poging"
            ag.log("proef", "bron", "regel twee")
            ag.log_verstuur()
        verwacht = (["regel een"] if aangenomen else []) + ["regel twee"]
        assert [r["tekst"] for r in draad.logregels()] == verwacht, (fout, draad.logregels())



def test_na62_signaal_na_de_eerste_hartslag_blijft_niet_op_actief():
    """Codex NA62 (ronde 16): de eerste hartslag ("actief") stond voor de bescherming van de startfase. Nam het bord ze aan
    en kwam daarna, tijdens het antwoord, een signaal, dan volgde geen fouthartslag en bleef de agent op actief."""
    for signaal in (SystemExit(143), KeyboardInterrupt()):
        draad = Draad(open_noden=[])
        draad.na_fouten["/agent-status"] = [signaal]
        begonnen = []
        with op_het_bord(draad):
            try:
                with bord.Agent("proef").ronde("proef"):
                    begonnen.append(True)
                doorgegaan = None
            except BaseException as e:  # noqa: BLE001
                doorgegaan = e
        assert doorgegaan is signaal and not begonnen, (repr(doorgegaan), begonnen)
        assert [s["status"] for s in draad.statussen("proef")] == ["actief", "fout"], draad.statussen("proef")


def test_na63_werkverslag_los_voor_het_versturen():
    """Codex NA63 (ronde 16): log_verstuur wiste de buffer pas na het versturen. Een signaal tussen versturen en wissen liet
    aangenomen regels staan, en de ronde stuurde ze bij het afsluiten nog eens. Nu is de buffer leeg zodra het verzoek
    vertrekt, en komt een regel hoogstens een keer aan, ook met een signaal tijdens het werk en een tweede tijdens het
    verslag (dan gaat het signaal van het werk door)."""
    ag = bord.Agent("proef")
    tijdens = []
    draad = Draad()
    echt = draad.antwoord

    def antwoord(pad, volledig, payload):
        if pad == "/api/logboek":
            tijdens.append(list(ag._log))
        return echt(pad, volledig, payload)

    draad.antwoord = antwoord
    with op_het_bord(draad):
        ag.log("proef", "bron", "een regel")
        ag.log_verstuur()
    assert tijdens == [[]], f"de buffer hoort leeg te zijn zodra het verzoek vertrekt: {tijdens}"
    draad = Draad(open_noden=[])
    draad.na_fouten["/api/logboek"] = [SystemExit(143)]
    ag = bord.Agent("proef")
    with op_het_bord(draad):
        try:
            with ag.ronde("proef"):
                ag.log("proef", "bron", "een regel")
                raise SystemExit(130)
        except BaseException as e:  # noqa: BLE001
            doorgegaan = e
    assert isinstance(doorgegaan, SystemExit) and doorgegaan.code == 130, repr(doorgegaan)
    assert [r["tekst"] for r in draad.logregels()] == ["een regel"], draad.logregels()
    assert draad.statussen("proef")[-1]["status"] == "fout", draad.statussen("proef")

def test_x5_signaal_tijdens_het_melden_van_een_breuk():
    """Overleg 13, X2 en X5 (na Codex NA61): een tweede signaal terwijl de ronde haar breuk meldt (het werkverslag of de
    noodlijst ophalen) hield de fouthartslag tegen, en dan bleef de agent op actief staan. Dat geldt bij een fout tijdens
    het starten, bij stoppen zonder regelboek en bij het afsluiten. Nu gaat de fouthartslag altijd uit, zonder noodlijst
    als die niet op te halen was (het bord sluit dan niets), en gaat de oorspronkelijke oorzaak door."""
    gevallen = (
        # (wat, werkwijze, fout in het werk, signaal bij /api/nood, verwachte uitzondering)
        ("start: onverwachte fout bij het lezen", WW, None, KeyboardInterrupt(), RuntimeError),
        ("stop zonder regelboek", {}, None, SystemExit(143), SystemExit),
        ("afsluiten na een werkfout (NA61)", WW, ValueError("werk kapot"), SystemExit(143), SystemExit),
        ("afsluiten na een signaal in het werk", WW, SystemExit(130), KeyboardInterrupt(), SystemExit),
    )
    for wat, werkwijze, werkfout, signaal, verwacht in gevallen:
        draad = Draad(werkwijze=werkwijze, open_noden=[{"naam": "proef", "tekst": "Oude nood", "wie": "mehdi"}])
        draad.fouten["/api/nood"] = [signaal]
        if wat.startswith("start"):
            draad.fouten["/api/agent/proef/werkwijze"] = [RuntimeError("bord stuk (proef)")]
        ag = bord.Agent("proef")
        with op_het_bord(draad):
            try:
                with ag.ronde("proef") as r:
                    r.nood("Nieuwe nood", wie="claude-code")
                    if werkfout is not None:
                        raise werkfout
                doorgegaan = None
            except BaseException as e:  # noqa: BLE001
                doorgegaan = e
        assert isinstance(doorgegaan, verwacht), (wat, repr(doorgegaan))
        if werkfout is not None and not isinstance(werkfout, Exception):
            assert doorgegaan is werkfout, (wat, "het oorspronkelijke signaal hoort door te gaan", repr(doorgegaan))
        fouten = [s for s in draad.statussen("proef") if s["status"] == "fout"]
        assert len(fouten) == 1 and draad.statussen("proef")[-1]["status"] == "fout", (wat, draad.statussen("proef"))
        assert "nood" not in fouten[-1] and type(signaal).__name__ in fouten[-1]["detail"], (wat, fouten[-1])


def test_x5_na_een_signaal_bij_het_afsluiten_geen_noodlijst_meer():
    """Overleg 13, X5: kwam bij het afsluiten al een signaal (kennis of werkverslag), dan haalt de ronde de noodlijst niet
    meer op; de fouthartslag gaat meteen uit, zonder lijst."""
    draad = Draad(open_noden=[])
    draad.fouten["/api/logboek"] = [KeyboardInterrupt()]
    ag = bord.Agent("proef")
    ag.kennis = lambda *a, **k: (_ for _ in ()).throw(SystemExit(143))
    with op_het_bord(draad):
        try:
            with ag.ronde("proef"):
                ag.log("proef", "bron", "een regel")
        except BaseException as e:  # noqa: BLE001
            doorgegaan = e
    assert isinstance(doorgegaan, SystemExit), repr(doorgegaan)
    na_afsluiten = draad.gevraagd[draad.gevraagd.index("/api/logboek"):]
    assert "/api/nood" not in na_afsluiten and "nood" not in draad.statussen("proef")[-1], (draad.gevraagd, draad.statussen())


def test_na57_elk_signaal_bij_het_afsluiten_staat_in_de_fouthartslag():
    """Codex NA57 (ronde 14): kwam bij de kennis een SIGTERM en bij het werkverslag een Ctrl-C, dan verdween het tweede.
    Nu noemt de fouthartslag beide, en gaat het eerste signaal door. Ook een signaal alleen bij het werkverslag geeft
    een fouthartslag (de toetsen van NA49 en NA53 legden het signaal alleen bij de kennis)."""
    for kennis_fout, verslag_fout, eerst in ((SystemExit(143), KeyboardInterrupt(), SystemExit),
                                             (None, SystemExit(143), SystemExit)):
        draad = Draad(open_noden=[])
        if verslag_fout is not None:
            draad.fouten["/api/logboek"] = [verslag_fout]
        ag = bord.Agent("proef")
        if kennis_fout is not None:
            ag.kennis = lambda *a, _f=kennis_fout, **k: (_ for _ in ()).throw(_f)
        with op_het_bord(draad):
            try:
                with ag.ronde("proef"):
                    ag.log("proef", "bron", "een regel")
                doorgegaan = None
            except BaseException as e:  # noqa: BLE001
                doorgegaan = e
        assert isinstance(doorgegaan, eerst), repr(doorgegaan)
        laatste = draad.statussen("proef")[-1]
        verwacht = [type(x).__name__ for x in (kennis_fout, verslag_fout) if x is not None]
        assert laatste["status"] == "fout" and all(n in laatste["detail"] for n in verwacht), (verwacht, laatste)


# ------------------------------------------------------------------------------------------- De Contractmaker ---
import contracten_agent as CA  # noqa: E402


def _contractmaker(draad):
    """Een ronde van De Contractmaker zonder Pipedrive, dashboard of model. Geeft (uitkomst, gevraagde fasen)."""
    gevraagd = []

    def deals():
        gevraagd.append("fase")
        return []

    mcp = types.SimpleNamespace(call=lambda tool, **k: {"markdown": "# Werkinstructie\n\nStap een.", "versie": "v9"})
    with op_het_bord(draad), vervangen((CA, "mcp", mcp), (CA, "deals_in_startfase", deals), (CA, "laad_staat", dict),
                                       (CA, "bewaar_staat", lambda s: None),
                                       (CA.bronnen_mod, "dropbox_beschikbaar", lambda: False)):
        try:
            uit = CA._main_binnen_slot()
        except bord.RondeGestopt as e:
            uit = e
    return uit, gevraagd


def test_contractmaker_werkt_niet_zonder_regelboek():
    """Tot 01-11-2026 maakte werkwijze_van_bord van elke fout en van een antwoord zonder werkwijze een lege tekst, en
    werkte De Contractmaker door met alleen de Werkinstructie. Nu stopt de ronde voor ze een dossier opent."""
    for werkwijze, nood, wie in (({}, ONBEKEND, "claude-code"), (_http(404), NIET_OP_BORD, "claude-code"),
                                 ("  \n", LEEG, "mehdi")):
        draad = Draad(werkwijze=werkwijze)
        uit, gevraagd = _contractmaker(draad)
        assert not gevraagd, f"De Contractmaker opende dossiers zonder regelboek ({werkwijze!r})"
        assert uit in (1,) or isinstance(uit, bord.RondeGestopt), f"de ronde eindigt niet als gestopt: {uit!r}"
        _gestopt(draad, CA.NAAM, nood, wie)


def test_contractmaker_gaat_door_de_ronde():
    """N4, N12-N14: de werkwijze van het bord, de Werkinstructie, de lessen en de collega's staan in de gemelde kennis,
    en de prompt krijgt de werkwijze van het bord."""
    draad = Draad(werkwijze="# Contractmaker\n\nHet proces van Mehdi.")
    uit, gevraagd = _contractmaker(draad)
    assert gevraagd == ["fase"] and uit in (0, None), (uit, gevraagd)
    k = _ronde_kennis(draad, CA.NAAM)
    assert "Werkinstructie AI v9" in k["bron"], k["bron"]
    assert CA.WERKWIJZE == "# Contractmaker\n\nHet proces van Mehdi.", CA.WERKWIJZE
    assert draad.statussen(CA.NAAM)[-1]["status"] in ("klaar", "waakt"), draad.statussen(CA.NAAM)


def test_goudstandaard_bevriest_geen_lege_werkwijze():
    """goudstandaard.py bevriest de werkwijze als invoer van een proef. Een onbekende werkwijze mag daar nooit als lege
    tekst in belanden: dan zou de proef een agent zonder regels nameten."""
    for werkwijze in ({}, _http(500), ""):
        with op_het_bord(Draad(werkwijze=werkwijze)):
            try:
                tekst = CA.werkwijze_van_bord()
            except bord.RondeGestopt:
                tekst = None
        assert tekst is None, f"werkwijze_van_bord gaf {tekst!r} voor {werkwijze!r}, hoort te stoppen"
    with op_het_bord(Draad(werkwijze="# Regels\n\nEen.")):
        assert CA.werkwijze_van_bord() == "# Regels\n\nEen."


def test_goudstandaard_plant_niet_op_een_bevroren_invoer_zonder_werkwijze():
    """Overleg 12, K1: ook een eerder bevroren invoer zonder werkwijze meet een agent zonder regels; die stopt."""
    import goudstandaard as GS  # noqa: PLC0415
    gepland = []
    with vervangen((CA, "plan_met_model", lambda *a, **k: gepland.append(a) or ({}, 0, {}))):
        for werkwijze in (None, "", "  "):
            invoer = {"nummer": "2699", "soort": "proef", "werkinstructie": "", "deal": {}, "voorbereiding": {},
                      "controle": {}, "notities": [], "vrij_nummer": "", "bronnen": {}}
            if werkwijze is not None:
                invoer["werkwijze"] = werkwijze
            try:
                GS.plan_op_bevroren(invoer)
            except bord.RondeGestopt:
                pass
        assert not gepland, f"de proef plande op een invoer zonder werkwijze: {len(gepland)} keer"
        GS.plan_op_bevroren(dict(invoer, werkwijze="# Regels"))
    assert len(gepland) == 1 and CA.WERKWIJZE == "# Regels", (gepland, CA.WERKWIJZE)


# --------------------------------------------------------------------------- De naamstructuur installeren ---
def test_naamstructuur_installeren_zaait_nooit_over_een_onbekende_werkwijze():
    """planning/naamstructuur_installeren.py maakte van een antwoord zonder werkwijze een lege tekst, en zette dan het zaad
    op het bord alsof er nog niets stond. Nu stopt de installatie; een nieuwe agent leest ze pas na zijn registratie, en
    het zaad komt alleen op een bewezen lege werkwijze (overleg 12, X8)."""
    sys.path.insert(0, os.path.join(RUNNER, "planning"))
    import naamstructuur_installeren as NI  # noqa: PLC0415

    def gezaaid(d):
        return [pad for pad, p in d.gestuurd if pad.endswith("/werkwijze") and p is not None]

    draad = Draad(werkwijze={}, agents=["benamingen-wacht", "mappen-wacht"])
    with op_het_bord(draad):
        try:
            NI.registreer()
            gestopt = False
        except bord.WerkwijzeOnbekend:
            gestopt = True
    assert gestopt and not gezaaid(draad), f"het zaad ging over een onbekende werkwijze: {gezaaid(draad)}"
    draad = Draad(werkwijze="", agents=[])
    with op_het_bord(draad):
        NI.registreer()
    assert gezaaid(draad) == ["/api/agent/benamingen-wacht/werkwijze", "/api/agent/mappen-wacht/werkwijze"], draad.gestuurd


# ------------------------------------------------------------------------------------------ De Mailwacht (Mac) ---
import mail_wacht as MW  # noqa: E402


class _GeenImap:
    def __init__(self, *a, **k):
        raise AssertionError("de Mailwacht opende het postvak")


def _mailwacht(draad, imap=_GeenImap):
    with op_het_bord(draad), vervangen((MW, "wachtwoord", lambda account: "proef"), (MW.imaplib, "IMAP4_SSL", imap),
                                       (MW, "token", lambda: "proef"),
                                       (sys, "argv", ["mail_wacht.py", "--account", "proef@h-architects.be", "--naam", "mail-proef"])):
        try:
            return MW.main()
        except SystemExit as e:
            return e.code


def test_mac_mailwacht_leest_geen_mail_zonder_regelboek():
    """mac/mail_wacht.py maakte van elke fout een lege werkwijze en las dan het postvak zonder de afzenders met hoog
    belang. Nu: nood, hartslag fout en exit 1, voor het postvak opengaat. Het bord kent de open noden van een Mac-wacht
    niet (de publieke ingang laat /api/nood niet door): de nood sluit dan niets (nood_sluiten false)."""
    for werkwijze, nood, wie in (({}, ONBEKEND, "claude-code"), (_http(404), NIET_OP_BORD, "claude-code"),
                                 (_http(403), "Werkwijze niet gelezen: geen toegang tot het bord", "claude-code"),
                                 (urllib.error.URLError("weg"), "Werkwijze niet gelezen: bord onbereikbaar", "claude-code"),
                                 ("", LEEG, "mehdi")):
        draad = Draad(werkwijze=werkwijze)
        code = _mailwacht(draad)
        assert code == 1, f"exitcode {code!r} voor {werkwijze!r}, hoort 1"
        _gestopt(draad, "mail-proef", nood, wie)
        assert draad.statussen("mail-proef")[-1].get("nood_sluiten") is False, draad.statussen("mail-proef")[-1]


def test_mac_mailwacht_met_regelboek_leest_het_postvak():
    """Met een werkwijze gaat de wacht gewoon verder naar het postvak (hier nagebootst en leeg)."""
    geopend = []

    class Imap:
        def __init__(self, *a, **k):
            geopend.append(a)

        def login(self, *a):
            pass

        def select(self, *a, **k):
            pass

        def search(self, *a):
            return "OK", [b""]

        def logout(self):
            pass

    draad = Draad(werkwijze="# Mailwacht\n\n## Afzenders met hoog belang\n\n| Rol | Afzender |\n|---|---|\n| bank | proefbank |\n")
    code = _mailwacht(draad, Imap)
    assert code in (None, 0) and geopend, (code, geopend)
    assert draad.statussen("mail-proef")[-1]["status"] == "waakt", draad.statussen("mail-proef")


# ------------------------------------------------------------------------------- De zelfcontrole (Agendawacht) ---
import zelfcontrole as ZC  # noqa: E402


def test_zelfcontrole_noemt_onbekend_geen_drift():
    """Bord en repo dragen dezelfde werkwijze (A11). Een antwoord zonder werkwijze werd een lege tekst, en dan meldde de
    zelfcontrole 'werkwijze op het bord v? (<hash van niets>)', alsof er een oude werkwijze stond. Onbekend is een
    eigen bevinding, leeg ook."""
    nu = datetime(2026, 11, 2, 9, 0).astimezone()
    for werkwijze, verwacht in (({}, "niet te lezen"), (_http(404), "niet te lezen"), ("", "leeg")):
        with op_het_bord(Draad(werkwijze=werkwijze)):
            uit = [b for b in ZC.omgeving(nu) if b["controle"] == "bord_werkwijze_oud"]
        assert len(uit) == 1 and verwacht in uit[0]["tekst"] and "v?" not in uit[0]["tekst"], (werkwijze, uit)
    repo = (ZC.HIER / "werkwijze" / "agenda-wacht.md").read_text(encoding="utf-8")
    with op_het_bord(Draad(werkwijze=repo)):
        assert not [b for b in ZC.omgeving(nu) if b["controle"] == "bord_werkwijze_oud"], "gelijke werkwijze is geen drift"


# ---------------------------------------------------------------------------------------------- De Archivaris ---
import archivaris as AR  # noqa: E402


def _archivaris(draad):
    gelezen = []

    def db():
        gelezen.append("db")
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute("create table gesprek_log (bron, datum, start, uniek, archief, project, personen)")
        return con

    with op_het_bord(draad), vervangen((AR, "db", db), (AR, "afspraken", lambda van, tot: []),
                                       (AR.projectadressen, "index", lambda: {}), (sys, "argv", ["archivaris.py"])):
        try:
            uit = AR.main()
        except bord.RondeGestopt as e:
            uit = e
    return uit, gelezen


def test_archivaris_labelt_niet_zonder_regelboek_en_gaat_door_de_ronde():
    for werkwijze, nood, wie in (({}, ONBEKEND, "claude-code"), ("", LEEG, "mehdi")):
        draad = Draad(werkwijze=werkwijze)
        uit, gelezen = _archivaris(draad)
        assert not gelezen and (uit == 1 or isinstance(uit, bord.RondeGestopt)), (uit, gelezen)
        _gestopt(draad, "archivaris", nood, wie)
    draad = Draad()
    uit, gelezen = _archivaris(draad)
    assert gelezen == ["db"] and uit in (0, None), (uit, gelezen)
    _ronde_kennis(draad, "archivaris")


# --------------------------------------------------------------------------------------------- De Levenscoach ---
import levenscoach as LC  # noqa: E402


def _levenscoach(draad):
    gespiegeld = []

    def spiegel(dagen, bronnen, werkwijze, week=False):
        gespiegeld.append(werkwijze)
        return "Dagspiegel (proef)", 0

    with op_het_bord(draad), vervangen((LC, "spiegel", spiegel), (LC, "bronnen_van", lambda dagen: {d: [] for d in dagen})):
        try:
            uit = LC.main()
        except bord.RondeGestopt as e:
            uit = e
    return uit, gespiegeld


def test_levenscoach_spiegelt_niet_zonder_regelboek_en_gaat_door_de_ronde():
    for werkwijze, nood, wie in (({}, ONBEKEND, "claude-code"), ("", LEEG, "mehdi")):
        draad = Draad(werkwijze=werkwijze)
        uit, gespiegeld = _levenscoach(draad)
        assert not gespiegeld and (uit == 1 or isinstance(uit, bord.RondeGestopt)), (uit, gespiegeld)
        _gestopt(draad, "levenscoach", nood, wie)
    draad = Draad(werkwijze="# Levenscoach\n\nWarm maar nuchter.")
    uit, gespiegeld = _levenscoach(draad)
    assert gespiegeld == ["# Levenscoach\n\nWarm maar nuchter."] and uit in (0, None), (uit, gespiegeld)
    _ronde_kennis(draad, "levenscoach")
    laatste = draad.statussen("levenscoach")[-1]
    assert laatste["status"] == "waakt" and any("Gezondheidsgegevens" in n["tekst"] for n in laatste["nood"]), laatste


# --------------------------------------------------------------------------------------------- De Agendawacht ---
def test_agendawacht_hoofdronde_gaat_door_de_ronde_en_terugkijken_niet():
    """De volledige ronde van de Agendawacht las streng, maar buiten de ronde, met een eigen kennisregel zonder lessen of
    collega's. Nu neemt main() de gedeelde ronde en draait de romp (_ronde) erbinnen; zonder regelboek begint ze niet. De
    terugkijkstand blijft bewust buiten de ronde (overleg 12, X7): ze leest streng, maar zet geen hartslag en geen kennis,
    want die zouden de echte ronde overschrijven."""
    import agenda_wacht as AW  # noqa: PLC0415
    gedaan = []
    rust = ((AW.agenda, "beschikbaar", lambda: True), (AW, "slot_nemen", lambda *a, **k: None),
            (AW, "_wachtrij_begin", lambda: True), (AW, "_ronde", lambda rd: gedaan.append(rd.werkwijze)),
            (AW, "terugkijktaken", lambda: gedaan.append("terugkijktaken")))
    draad = Draad(werkwijze="# Agendawacht\n\nRegel.")
    with op_het_bord(draad), vervangen(*rust):
        uit = AW.main()
    assert uit == 0 and gedaan == ["# Agendawacht\n\nRegel."], (uit, gedaan)
    _ronde_kennis(draad, "agenda-wacht")
    gedaan.clear()
    draad = Draad(werkwijze={})
    with op_het_bord(draad), vervangen(*rust):
        uit = AW.main()
    assert uit == 1 and not gedaan, (uit, gedaan)
    _gestopt(draad, "agenda-wacht", ONBEKEND, "claude-code")
    draad = Draad(werkwijze="# Agendawacht\n\nRegel.")
    with op_het_bord(draad), vervangen(*rust):
        uit = AW.terugkijkstand(["--taken"])
    assert uit == 0 and gedaan == ["terugkijktaken"], (uit, gedaan)
    assert not draad.statussen("agenda-wacht") and not draad.kennis("agenda-wacht"), draad.gestuurd
    gedaan.clear()
    with op_het_bord(Draad(werkwijze={})), vervangen(*rust):
        try:
            AW.terugkijkstand(["--taken"])
            gestopt = False
        except bord.RondeGestopt:
            gestopt = True
    assert gestopt and not gedaan, "de terugkijkstand werkte zonder regelboek"


def test_na50_weggevallen_oproepen_zijn_elke_ronde_dezelfde_nood():
    """Codex NA50 (ronde 12): de nood over weggevallen oproepen begon met het aantal ("2 oproep(en) vielen weg"). Elke
    ronde was zo een andere nood (N10), en sinds de gedeelde ronde haalde r.nood het getal weg, zodat een open nood met
    getal een tweeling kreeg. Nu draagt de tekst geen aantal; dat staat in het werkverslag."""
    import agenda_wacht as AW  # noqa: PLC0415
    teksten = []
    for weg in (1, 3):
        noden = []
        with vervangen((AW, "afspraken", lambda v, t: (_ for _ in ()).throw(OSError("503"))),
                       (AW, "belrooster", lambda items, vandaag: [{"tijd": "2026-11-02T08:00", "sleutel": "k:a:1"}]),
                       (AW, "_nakijken", lambda regels, tok=None, ritten=(), noden=None, _w=weg: ([], _w))):
            AW.ONGELEZEN.clear()
            with redirect_stdout(io.StringIO()):
                AW.rooster_maken([], [], "2026-11-02", noden)
        teksten.append([n["tekst"] for n in noden if "vielen weg" in n["tekst"]])
    assert teksten[0] and teksten[0] == teksten[1], teksten
    assert not re.match(r"^\d", teksten[0][0]), teksten[0][0]



# ----------------------------------------------------------------- Overleg 14 en 15: kapotte foutuitvoer ---
class _GebrokenUitvoer(io.StringIO):
    def __init__(self, fout):
        super().__init__()
        self.fout = fout

    def write(self, *a):
        raise self.fout


def test_e2_kapotte_foutuitvoer_breekt_het_afsluiten_niet():
    """Codex NA65 en NA70: faalde het schrijven naar stderr in een foutpad (BrokenPipeError, of een vervangen stderr met een
    andere fout), dan brak het afsluiten af en bleef de agent op actief. Nu gaat de diagnose langs bord.diagnose, die
    elke fout van de uitvoer zelf negeert."""
    for stuk in (BrokenPipeError("uitvoer dicht (proef)"), RuntimeError("vervangen uitvoer (proef)")):
        _kapotte_uitvoer(stuk)


def _kapotte_uitvoer(stuk):
    draad = Draad(open_noden=[])
    draad.fouten["/api/logboek"] = [TimeoutError("traag (proef)")]
    ag = bord.Agent("proef")
    echt = urllib.request.urlopen
    urllib.request.urlopen = draad.urlopen
    oud_err = sys.stderr
    sys.stderr = _GebrokenUitvoer(stuk)
    try:
        try:
            with ag.ronde("proef"):
                ag._log.append({"naam": "proef", "onderwerp": "", "stap": "bron", "tekst": "een regel", "detail": ""})
                raise SystemExit(130)
        except BaseException as e:  # noqa: BLE001
            uit = e
    finally:
        sys.stderr = oud_err
        urllib.request.urlopen = echt
    assert isinstance(uit, SystemExit) and uit.code == 130, repr(uit)
    assert draad.statussen("proef")[-1]["status"] == "fout", draad.statussen("proef")


# ------------------------------------------------------------------------- Codex ronde 19: terugval tegenover main ---
def test_na73_fouthartslag_die_niet_aankwam_krijgt_een_tweede_poging():
    """Codex NA73: kwam de fouthartslag van de ronde niet aan (een tijdelijke verzendfout), dan bleef de agent op actief;
    op main stuurden De Archivaris, De Fathomwacht en De Levenscoach toevallig nog een tweede. Nu probeert de ronde het
    een tweede keer, zonder noodlijst. Zo bij stoppen zonder regelboek, bij een fout bij de start en bij het afsluiten."""
    weg = urllib.error.URLError("bord even weg (proef)")
    for wat, werkwijze, werkfout in (("zonder regelboek", "", None), ("start", {"raar": 1}, None),
                                    ("afsluiten", WW, ValueError("werk kapot"))):
        draad = Draad(werkwijze=werkwijze, open_noden=[])
        draad.fouten["/agent-status"] = [None, weg]          # actief komt aan, de eerste fouthartslag niet
        with op_het_bord(draad):
            try:
                with bord.Agent("proef").ronde("proef"):
                    if werkfout is not None:
                        raise werkfout
            except (bord.RondeGestopt, ValueError):
                pass
        statussen = draad.statussen("proef")
        assert [s["status"] for s in statussen] == ["actief", "fout"] and "nood" not in statussen[-1], (wat, statussen)
    draad = Draad(werkwijze="", open_noden=[])
    draad.fouten["/agent-status"] = [None, weg]
    uit, gelezen = _archivaris(draad)
    assert not gelezen and draad.statussen("archivaris")[-1]["status"] == "fout", draad.statussen("archivaris")


def test_na75_mac_mailwacht_zet_pas_actief_na_regelboek_en_wachtwoord():
    """Codex NA75: de Mac-mailwacht meldde actief voor de wachtwoordcontrole. Faalde daarna de melding "rust", dan bleef
    ze op actief; op main bleef de vorige status. Nu pas actief als regelboek en wachtwoord er zijn."""
    draad = Draad(werkwijze="# Mailwacht\n\nRegel.")
    echt = draad.antwoord

    def antwoord(pad, volledig, payload):
        if pad == "/agent-status" and payload.get("status") == "rust":
            raise urllib.error.URLError("bord even weg (proef)")
        return echt(pad, volledig, payload)

    draad.antwoord = antwoord
    with op_het_bord(draad), vervangen((MW, "wachtwoord", lambda account: ""), (MW.imaplib, "IMAP4_SSL", _GeenImap),
                                       (MW, "token", lambda: "proef"),
                                       (sys, "argv", ["mail_wacht.py", "--account", "proef@h-architects.be", "--naam", "mail-proef"])):
        try:
            MW.main()
        except (OSError, SystemExit):
            pass
    assert "actief" not in [s["status"] for s in draad.statussen("mail-proef")], draad.statussen("mail-proef")


def test_na76_agendawacht_zegt_geen_actief_zonder_regelboek():
    """Codex NA76: de Agendawacht las op main haar regelboek voor ze actief meldde. In de ronde kwam actief eerst; kwamen
    daarna beide fouthartslagen niet aan, dan bleef ze op actief, waar main de vorige status liet staan. Nu leest ze
    eerst streng het regelboek, zoals voordien."""
    import agenda_wacht as AW  # noqa: PLC0415
    draad = Draad(werkwijze="", open_noden=[])
    echt = draad.antwoord

    def antwoord(pad, volledig, payload):
        if pad == "/agent-status" and payload.get("status") == "fout":
            raise urllib.error.URLError("bord even weg (proef)")
        return echt(pad, volledig, payload)

    draad.antwoord = antwoord
    with op_het_bord(draad), vervangen((AW.agenda, "beschikbaar", lambda: True), (AW, "slot_nemen", lambda *a, **k: None),
                                       (AW, "_wachtrij_begin", lambda: True), (AW, "_ronde", lambda rd: None)):
        uit = AW.main()
    assert uit == 1 and "actief" not in [s["status"] for s in draad.statussen("agenda-wacht")], (uit, draad.statussen())


def test_na77_agendawacht_leest_haar_regelboek_een_keer():
    """Codex NA77: na NA76 las de Agendawacht haar regelboek twee keer; faalde alleen de tweede lezing even, dan stopte
    een geldige ronde. Nu krijgt de ronde de eerste lezing mee: een lezing, het werk begint, en de kennis noemt ze."""
    import agenda_wacht as AW  # noqa: PLC0415
    draad = Draad(werkwijze="# Agendawacht\n\nRegel.", open_noden=[])
    draad.fouten["/api/agent/agenda-wacht/werkwijze"] = [None, urllib.error.URLError("even weg (proef)")]
    gedaan = []
    with op_het_bord(draad), vervangen((AW.agenda, "beschikbaar", lambda: True), (AW, "slot_nemen", lambda *a, **k: None),
                                       (AW, "_wachtrij_begin", lambda: True),
                                       (AW, "_ronde", lambda rd: gedaan.append(rd.werkwijze))):
        uit = AW.main()
    assert uit == 0 and gedaan == ["# Agendawacht\n\nRegel."], (uit, gedaan, draad.statussen())
    assert draad.gevraagd.count("/api/agent/agenda-wacht/werkwijze") == 1, draad.gevraagd
    _ronde_kennis(draad, "agenda-wacht")
    draad = Draad(open_noden=[])
    with op_het_bord(draad):
        try:
            with bord.Agent("proef").ronde("proef", werkwijze="  "):
                gedaan.append("begonnen")
        except bord.RondeGestopt:
            pass
    assert "begonnen" not in gedaan and draad.statussen("proef")[-1]["status"] == "fout", draad.statussen("proef")

if __name__ == "__main__":
    import traceback
    goed = fout = 0
    for naam, f in list(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                f()
                goed += 1
                print(f"  OK   {naam}")
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"  FOUT {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)

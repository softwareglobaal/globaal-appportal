"""Het vastleggen van De Dagbundelaar (dagbundelaar.vastleggen, ontwerp docs/ontwerp-dagvaststelling.md v1.2).

Legt vast, zonder netwerk en zonder de echte mappen (alles in een tijdelijke map):
- een eerste ronde schrijft versie 1: bestand, klaarzet-item voor mehdi met revisie, staat; bord en bestand dragen
  dezelfde tekst en worden teruggelezen (E6);
- een tweede ronde met dezelfde bronnen schrijft niets nieuws (geen versie 2, geen versies-map);
- een nieuwe bron geeft versie 2, met versie 1 in versies/ en 'herzien: ...' in het blok over de vaststelling (D9);
- toont het bord iets anders dan het bestand, dan faalt de ronde (teruglezen);
- een ontvangstbewijs van de Mac met dezelfde sha256 sluit de Dropbox-nood; zonder bewijs staat ze open;
- de kanaalstand komt uit de hartslag van de wacht (D2): skelet is niet aangesloten, een verse databankronde wel, een
  oude is stil;
- het masker van het bord geldt al voor het schrijven: een privétekst staat nergens, ook niet in het bestand.
Draaien: python3 mijnagents-runner/tests/test_dagbundelaar_vaststelling.py
"""
import io
import os
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
        self.afspraken = [{"id": "t", "titel": "!! Mehdi: [UB-KB] PL 3846 - Pieter Claes, Geheime Straat 5, Ternat",
                           "start": f"{DAG}T14:15:00+02:00", "einde": f"{DAG}T15:15:00+02:00", "kalender": "werk",
                           "deelnemers": []}]
        self.status = {"whatsapp-wacht": {"naam": "whatsapp-wacht", "status": "rust", "taak": "", "ts": NU.isoformat()},
                       "belwacht": {"naam": "belwacht", "status": "rust", "taak": "", "ts": NU.isoformat()}}
        self.items, self.vervals = {}, None

    def db_lees(self, sql, args=()):
        if "FROM gesprek_log" in sql:
            return [dict(r) for r in self.rijen]
        if "FROM klaarzet" in sql:
            return [{"uniek": f"zoom:dag:{DAG}", "inhoud": '{"telling": "volledig"}'}]
        if "FROM mailbericht" in sql:
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


def ronde(w, dagen=(DAG,)):
    oud = (D.DAGBOEK, D.STAAT, D.ONTVANGST, D.lees_agenda, D.lees_locatie, D.lees_mail, bord.db_lees, bord.call)
    D.DAGBOEK = os.path.join(w.map, "dagboek")
    D.STAAT = os.path.join(w.map, "staat.json")
    D.ONTVANGST = os.path.join(w.map, "ontvangst.txt")
    D.lees_agenda = lambda dagen_: ({DAG: list(w.afspraken)}, set(), lambda a: "[LA]" in a["titel"])
    D.lees_locatie = lambda dag, afspraken: ({"t": {"uitkomst": "doorgegaan", "tekst": "auto ter plaatse 14:31-16:07"}}, [], "")
    D.lees_mail = lambda dagen_: ({"info@h-architects.be": {"berichten": [
        {"datum": f"{DAG}T08:36:57+02:00", "message_id": "<w1@x>"}], "onvolledig": []}}, {}, set())
    bord.db_lees, bord.call = w.db_lees, w.call
    D.ag.klaarzet = w.klaarzet
    D.ag.log = lambda *a, **k: None
    r = NepRonde()
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            detail = D.vastleggen(r, list(dagen))
        return r, detail
    finally:
        D.DAGBOEK, D.STAAT, D.ONTVANGST, D.lees_agenda, D.lees_locatie, D.lees_mail, bord.db_lees, bord.call = oud
        for naam in ("klaarzet", "log"):
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
        assert any("Dropbox" in n for n in r.noden), "zonder ontvangstbewijs staat de Dropbox-nood open"
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

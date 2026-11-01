"""De Belwacht Xelion (31-10-2026), zonder netwerk, zonder docker en zonder bord.

Legt vast: per oproep een privérij xelion:<oid>; een oproep zonder gesprek met buiten:gemist; een dekkingsrij alleen voor
een dag waarna de spiegel nog foutloos liep; geen naam of nummer in hartslag of werkverslag; de dagvaststelling telt
Xelion als oproep en zegt 'onbekend' zonder dekking.
Draaien: python3 mijnagents-runner/tests/test_xelion_wacht.py
"""
import io
import sys
import traceback
from contextlib import redirect_stderr
from datetime import datetime, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent
RUNNER = HIER.parent
sys.path.insert(0, str(RUNNER))
sys.path.insert(0, str(RUNNER / "koppelingen"))
_argv, sys.argv = sys.argv, [sys.argv[0]]
import bord  # noqa: E402
import bordstand  # noqa: E402
import dagbundelaar as D  # noqa: E402
import dagvaststelling as V  # noqa: E402
import mac_gesprekken as M  # noqa: E402
import xelion_wacht as X  # noqa: E402
sys.argv = _argv

NU = datetime(2026, 10, 31, 21, 0, tzinfo=timezone.utc)
DAG = "2026-10-30"


def spiegel(laatste_run="2026-10-31T20:55:00+00:00", ok=True):
    return {"gebruiker": "1", "lijn": "2", "sync": {"laatste_run": laatste_run, "ok": ok, "comm_fout": None},
            "rijen": [
                {"oid": "11", "datum": "2026-10-30T09:00:00Z", "richting": "uitgaand", "duur_sec": 125, "beantwoord": True,
                 "extern_nummer": "+32470000001", "extern_naam": "Jan Proef"},
                {"oid": "12", "datum": "2026-10-30T10:00:00Z", "richting": "inkomend", "duur_sec": 0, "beantwoord": False,
                 "extern_nummer": "+32470000002", "extern_naam": ""},
                {"oid": "13", "datum": "2026-10-30T11:00:00Z", "richting": "inkomend", "duur_sec": 30, "beantwoord": True,
                 "extern_nummer": "", "extern_naam": ""},
                {"oid": "14", "datum": "2026-09-01T11:00:00Z", "richting": "inkomend", "duur_sec": 30, "beantwoord": True,
                 "extern_nummer": "+32470000003", "extern_naam": "Buiten Venster"}]}


def test_rijen_gemist_en_dekking():
    dagen = M.dagen(NU)
    rijen, info = X.rijen_van(spiegel(), dagen)
    op = {r["uniek"]: r for r in rijen}
    assert op["xelion:11"]["personen"] == "Jan Proef" and op["xelion:11"]["minuten"] == 2
    assert op["xelion:11"]["thema"] == "Xelion, uitgaand" and op["xelion:11"]["prive"] == 1
    assert op["xelion:12"]["dubbel_van"] == M.GEMIST and op["xelion:12"]["personen"] == "+32470000002"
    assert op["xelion:12"]["thema"] == "Xelion, inkomend, gemist" and op["xelion:12"]["minuten"] == 0
    assert op["xelion:13"]["personen"] == "nummer verborgen"
    assert "xelion:14" not in op
    assert f"dekking:xelion:{DAG}" in op and "dekking:xelion:2026-10-31" not in op
    assert info["gemist"] == 1 and DAG in info["gedekt"]
    # een spiegel die faalde, dekt niets: onbekend, nooit nul
    _, info2 = X.rijen_van(spiegel(ok=False), dagen)
    assert info2["gedekt"] == []
    assert all(u.startswith(bordstand.KANALEN["xelion"]) for u in op)


def test_dagvaststelling_telt_xelion():
    rijen, _ = X.rijen_van(spiegel(), M.dagen(NU))
    gedekt = D.gedekte_dagen(rijen)
    kanalen = {"xelion": D.kanaal_van_dag("aangesloten", "xelion", DAG, gedekt)}
    v = V.vaststellen(DAG, [], set(), rijen, {}, [], "volledig", None, kanalen, lambda a: False)
    assert v["xelion"] == {"stand": "aangesloten", "oproepen": 2, "minuten": 3, "gemist": 1}, v["xelion"]
    tekst = V.tekst(v)
    assert "- Xelion: 2 oproepen, 3 min, 1 gemist gezien" in tekst, tekst
    assert "10:00 Xelion, 2 min, privé" in tekst and "Jan Proef" not in tekst, tekst
    leeg = {"xelion": D.kanaal_van_dag("aangesloten", "xelion", "2026-10-10", gedekt)}
    t2 = V.tekst(V.vaststellen("2026-10-10", [], set(), rijen, {}, [], "volledig", None, leeg, lambda a: False))
    assert "- Xelion: onbekend (onbekend voor deze dag)" in t2, t2
    assert D.kanaalstand({"status": "klaar", "taak": X.TAAK, "ts": NU.isoformat()}, NU) == "aangesloten"


class NepRonde:
    def __init__(self, werkwijze):
        self.werkwijze, self.noden, self.bronnen, self.detail = werkwijze, [], {}, ""

    def nood(self, tekst, wie="mehdi"):
        self.noden.append((tekst, wie))

    def bron(self, naam, inhoud):
        self.bronnen[naam] = inhoud


def test_ronde_zonder_namen():
    tabel = {}

    def call(pad, payload=None, method=None):
        if pad == "/api/gesprekken":
            for r in payload["rijen"]:
                tabel[r["uniek"]] = dict(r)
        return {"ok": True}

    def terug(kanaal, van, tot):
        return {u: {"v": bordstand.vingerafdruk(r), "d": r["dubbel_van"]} for u, r in tabel.items()
                if van <= r["datum"] <= tot and u.startswith(bordstand.KANALEN[kanaal])}
    log = []
    echt_call, echt_log = bord.call, X.ag.log
    bord.call, X.ag.log = call, lambda *x, **k: log.append(X.ag.maskeer(" ".join(map(str, x))))
    try:
        werkwijze = (RUNNER / "werkwijze" / "xelion-wacht.md").read_text(encoding="utf-8")
        r = NepRonde(werkwijze)
        X.werk(r, "c" * 32, lezer=lambda van, tot: spiegel(), terug=terug, nu=NU)
    finally:
        bord.call, X.ag.log = echt_call, echt_log
    gemeld = X.ag.maskeer(r.detail) + " ".join(log)
    for naam in ("Jan Proef", "+32470000002", "+32470000001"):
        assert naam not in gemeld, naam
    assert "gisteren 2 oproepen, 3 min, 1 gemist" in r.detail and r.detail.endswith("ronde-id:" + "c" * 32), r.detail
    assert "xelion:11" in tabel and not r.noden
    nooit, beslist = bord.grenzen(werkwijze)
    assert nooit and beslist and len(werkwijze) >= 500 and "—" not in werkwijze and "–" not in werkwijze


def test_tel2_inhaal_vanaf_01_10():
    """TEL-2: zonder inhaalweg las Xelion nooit voor de laatste 14 dagen, dus de oproep van 13-10 ontbrak. Met
    --inhaal-vanaf 2026-10-01 (of --van) leest een ronde op 01-11 eenmalig 32 dagen, met de dekking van elke voorbije
    dag; zonder optie blijven het 14 dagen."""
    nu = datetime(2026, 11, 1, 21, 0, tzinfo=timezone.utc)
    gevraagd, tabel = [], {}

    def lezer(van, tot):
        gevraagd.append((van, tot))
        return {"gebruiker": "1", "lijn": "2", "sync": {"laatste_run": "2026-11-01T20:55:00+00:00", "ok": True,
                                                        "comm_fout": None},
                "rijen": [{"oid": "21", "datum": "2026-10-13T08:00:00Z", "richting": "inkomend", "duur_sec": 90,
                           "beantwoord": True, "extern_nummer": "+32470000004", "extern_naam": "Proef Klant"}]}

    def call(pad, payload=None, method=None):
        for x in (payload or {}).get("rijen") or []:
            tabel[x["uniek"]] = dict(x)
        return {"ok": True}

    def terug(kanaal, van, tot):
        return {u: {"v": bordstand.vingerafdruk(x), "d": x["dubbel_van"]} for u, x in tabel.items()
                if van <= x["datum"] <= tot and u.startswith(bordstand.KANALEN[kanaal])}
    werkwijze = (RUNNER / "werkwijze" / "xelion-wacht.md").read_text(encoding="utf-8")
    echt_call, echt_log = bord.call, X.ag.log
    bord.call, X.ag.log = call, lambda *x, **k: None
    try:
        r = NepRonde(werkwijze)
        X.werk(r, "d" * 32, lezer=lezer, terug=terug, nu=nu, vanaf="2026-10-01")
        kort = NepRonde(werkwijze)
        X.werk(kort, "e" * 32, lezer=lezer, terug=terug, nu=nu)
    finally:
        bord.call, X.ag.log = echt_call, echt_log
    assert gevraagd[0][0] == M.daggrens("2026-10-01") and gevraagd[1][0] == M.daggrens("2026-10-19"), gevraagd
    assert "32 dagen gelezen (2026-10-01 tot 2026-11-01)" in r.detail, r.detail
    assert "14 dagen gelezen (2026-10-19 tot 2026-11-01)" in kort.detail, kort.detail
    assert tabel["xelion:21"]["datum"] == "2026-10-13" and tabel["xelion:21"]["minuten"] == 2
    assert all(f"dekking:xelion:2026-10-{d:02d}" in tabel for d in range(1, 32)), sorted(tabel)
    for optie in ("--inhaal-vanaf", "--van"):
        try:
            with redirect_stderr(io.StringIO()):
                X.main([optie, "gisteren"])
            raise AssertionError(optie)
        except SystemExit as e:
            assert e.code == 2


def test_zonder_grenzen_geen_lezing():
    gelezen = []
    r = NepRonde("# Werkwijze zonder grenzen\n")
    try:
        X.werk(r, "d" * 32, lezer=lambda *a: gelezen.append(a), nu=NU)
    except M.MacFout:
        pass
    else:
        raise AssertionError("ronde zonder grenzen ging door")
    assert not gelezen


if __name__ == "__main__":
    goed = fout = 0
    for naam, f in list(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                with redirect_stderr(io.StringIO()):
                    f()
                goed += 1
                print(f"   geslaagd  {naam}")
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"   FOUT      {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)

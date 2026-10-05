"""Grendels op het bronbeleid: de startgrens, het toestel, de dagranden en de planning.

Besluit van Mehdi (opdracht v1.2, 04-10-2026): alleen de reeks van de tracker in
de auto vanaf 3 oktober 2026 00:00 Belgische tijd telt, op de meettijd, en alleen
van het vastgelegde toestel. Breekt een van deze tests, dan kan oude of vreemde
bewegingsdata weer in de verwerking sluipen.

Eigen proefgegevens: een verzonnen IMEI, nooit het echte toestel.

Draaien: python3 locatie/test_bronbeleid.py
"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import bronbeleid as B  # noqa: E402

PROEF = "990000000000017"                 # verzonnen IMEI voor de tests
GRENS = 1790978400                        # 2026-10-02 22:00:00 UTC = 3-10 00:00 Brussel


class ProefToestel:
    """Zet even een proeftoestel in het beleid van de auto, en daarna weer terug."""
    def __enter__(self):
        self.oud = B.BRONNEN["auto"]["toestel_sha256"]
        B.BRONNEN["auto"]["toestel_sha256"] = B.vingerafdruk(PROEF)
        return {PROEF: "auto"}

    def __exit__(self, *a):
        B.BRONNEN["auto"]["toestel_sha256"] = self.oud


def test_de_grens_is_3_oktober_middernacht_in_brussel():
    assert B.moment(B.STARTGRENS) == GRENS
    assert datetime.fromtimestamp(GRENS, timezone.utc).isoformat() == "2026-10-02T22:00:00+00:00"
    assert B.eerste_dag() == "2026-10-03"
    assert B.ingang("auto") == GRENS


def test_een_meting_vlak_voor_de_grens_telt_niet_ook_als_ze_later_binnenkwam():
    with ProefToestel():
        voor = {"bron": "auto", "toestel": PROEF, "tst": GRENS - 1, "ontvangen": GRENS + 86400}
        op = {"bron": "auto", "toestel": PROEF, "tst": GRENS, "ontvangen": GRENS}
        assert B.telt_mee(voor) == (False, "meettijd voor de ingang van de bron")
        assert B.telt_mee(op) == (True, "")


def test_het_verkeerde_toestel_telt_niet_ook_met_de_juiste_bronnaam():
    """Een oude tracker of een ander toestel dat ook 'auto' heet, komt er niet in."""
    with ProefToestel():
        assert not B.telt_mee({"bron": "auto", "toestel": "123456789012345", "tst": GRENS + 10})[0]
        assert not B.telt_mee({"bron": "auto", "toestel": None, "tst": GRENS + 10})[0]
    # En het echte beleid kent het proeftoestel niet.
    assert not B.telt_mee({"bron": "auto", "toestel": PROEF, "tst": GRENS + 10})[0]


def test_de_telefoon_en_de_draagbare_tracker_tellen_niet():
    for bron in ("iphone", "draagbaar", "onbekend", None):
        ok, reden = B.telt_mee({"bron": bron, "toestel": "x", "tst": GRENS + 100})
        assert not ok, (bron, reden)
    assert B.actieve_bronnen() == ["auto"]
    assert B.BRONNEN["iphone"]["status"] == "uit_gebruik"
    assert B.BRONNEN["draagbaar"]["status"] == "niet_aangesloten"


def test_sql_en_python_zeggen_hetzelfde():
    """Twee uitvoeringen van één regel mogen nooit uit elkaar lopen."""
    import sqlite3
    with ProefToestel() as toestellen:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE punt (bron TEXT, toestel TEXT, tst INTEGER, verdacht TEXT)")
        gevallen = [("auto", PROEF, GRENS - 1), ("auto", PROEF, GRENS), ("auto", PROEF, GRENS + 9999),
                    ("auto", "123", GRENS + 5), ("iphone", PROEF, GRENS + 5), ("draagbaar", PROEF, GRENS + 5),
                    ("auto", None, GRENS + 5)]
        conn.executemany("INSERT INTO punt (bron, toestel, tst) VALUES (?,?,?)", gevallen)
        conn.execute("INSERT INTO punt VALUES ('auto', ?, ?, 'sprong')", (PROEF, GRENS + 7))
        clause, args = B.sql_actief(toestellen)
        via_sql = set(conn.execute(f"SELECT bron, toestel, tst FROM punt WHERE {clause}", args).fetchall())
        via_python = {g for g in gevallen if B.telt_mee({"bron": g[0], "toestel": g[1], "tst": g[2]})[0]}
        assert via_sql == via_python == {("auto", PROEF, GRENS), ("auto", PROEF, GRENS + 9999)}, (via_sql, via_python)
    # Zonder toegelaten toestel laat de SQL niets door, in plaats van alles.
    assert B.sql_actief({}) == ("0", [])


def test_het_imei_staat_nergens_in_de_code():
    """Het IMEI is het enige dat de open poort toelaat; het hoort alleen in .env.
    Getoetst op de vingerafdruk, zodat ook deze test het IMEI niet hoeft te bevatten."""
    echt = B.BRONNEN["auto"]["toestel_sha256"]
    for wortel in (HIER, os.path.join(HIER, "..", "mijnagents-runner")):
        if not os.path.isdir(wortel):
            continue
        for map_, _, bestanden in os.walk(wortel):
            for naam in bestanden:
                if not naam.endswith((".py", ".html", ".md", ".cron", ".json")):
                    continue
                try:
                    tekst = open(os.path.join(map_, naam), encoding="utf-8").read()
                except (OSError, UnicodeDecodeError):
                    continue
                for getal in set(re.findall(r"(?<!\d)\d{15}(?!\d)", tekst)):
                    assert B.vingerafdruk(getal) != echt, os.path.join(map_, naam)


def test_dagranden_van_23_en_25_uur():
    """25-10-2026 duurt 25 uur, 28-03-2027 23 uur; begin + 24 uur liet een uur vallen."""
    b, e = B.dagranden("2026-10-25")
    assert e - b == 25 * 3600, (e - b) / 3600
    b, e = B.dagranden("2027-03-28")
    assert e - b == 23 * 3600, (e - b) / 3600
    b, e = B.dagranden("2026-10-04")
    assert e - b == 24 * 3600
    # Aansluitend: het einde van de ene dag is het begin van de volgende.
    assert B.dagranden("2026-10-25")[1] == B.dagranden("2026-10-26")[0]
    assert B.dagranden("2027-03-28")[1] == B.dagranden("2027-03-29")[0]


def test_dagen_voor_de_grens_bestaan_niet_voor_de_verwerking():
    assert not B.dag_toegestaan("2026-10-02")
    assert B.dag_toegestaan("2026-10-03")
    assert B.dagen_vanaf_grens("2026-10-05") == ["2026-10-03", "2026-10-04", "2026-10-05"]
    assert B.dagen_vanaf_grens("2026-09-30") == []


def test_avondplanning_in_brusselse_tijd_zomer_en_winter():
    """De VM draait in UTC: 21:30 UTC was 23:30 in de zomer en 22:30 in de winter."""
    zomer = datetime(2026, 10, 4, 21, 35, tzinfo=B.BRUSSEL)
    winter = datetime(2026, 11, 4, 21, 35, tzinfo=B.BRUSSEL)
    for nu in (zomer, winter):
        assert B.binnen_venster("21:30", nu)
        assert not B.binnen_venster("21:30", nu + timedelta(hours=1))
        assert not B.binnen_venster("21:30", nu - timedelta(hours=1))
    v = B.volgende_uitvoering("dagboek", datetime(2026, 10, 4, 22, 0, tzinfo=B.BRUSSEL))
    assert v.strftime("%Y-%m-%d %H:%M") == "2026-10-05 21:30", v


def test_cronregels_dekken_de_brusselse_tijden_in_beide_seizoenen():
    """mijnagents-runner/planning/locatie.cron moet elke tijd uit PLANNING raken, in
    UTC+1 en in UTC+2, en elke regel moet de klokgrendel --om meegeven."""
    pad = os.path.join(HIER, "..", "mijnagents-runner", "planning", "locatie.cron")
    if not os.path.exists(pad):
        return            # in de container staat alleen locatie/; de CI draait dit in de repo
    regels = [r for r in open(pad, encoding="utf-8").read().splitlines() if r.strip() and not r.startswith("#")]
    for taak, plan in B.PLANNING.items():
        if plan["waar"].startswith("Mac"):
            continue
        sleutel = {"dagboek": "locatie_wacht.py --om", "controle": "locatie_wacht.py --controle",
                   "projectsync": "projectsync.py"}[taak]
        eigen = [r for r in regels if sleutel in r]
        assert eigen, f"geen cronregel voor {taak}"
        for hhmm in plan["tijden"]:
            u, m = (int(x) for x in hhmm.split(":"))
            for verschuiving in (1, 2):                    # winter, zomer
                utc_u = (u - verschuiving) % 24
                geraakt = False
                for r in eigen:
                    minuut, uur = r.split()[:2]
                    uren = set()
                    for stuk in uur.split(","):
                        if stuk == "*":
                            uren |= set(range(24))
                        elif "-" in stuk:
                            a, b = stuk.split("-")
                            uren |= set(range(int(a), int(b) + 1))
                        else:
                            uren.add(int(stuk))
                    if int(minuut) == m and utc_u in uren:
                        geraakt = True
                assert geraakt, f"{taak} {hhmm} wordt in UTC+{verschuiving} niet geraakt"
        for r in eigen:
            assert "--om" in r or "--controle" in r, f"cronregel zonder klokgrendel: {r}"


def test_planning_spreekt_niet_meer_van_de_telefoon():
    tekst = " ".join(str(v) for v in B.PLANNING.values())
    assert not re.search(r"telefoon|owntracks|iphone", tekst, re.I), tekst


if __name__ == "__main__":
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("   geslaagd  %s" % naam)
            except AssertionError as e:
                fouten += 1
                print("   MISLUKT   %s: %s" % (naam, e))
    print("%d van de %d grendels mislukt" % (fouten, sum(1 for n in globals() if n.startswith("test_"))))
    sys.exit(1 if fouten else 0)

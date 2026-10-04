"""Grendels op de dag van de tracker in de auto: parkeren, punten zonder fix, de
startgrens, twee sporen naast elkaar, de bronstatus en de context voor agents.

Elk geval komt uit de opdracht v1.2 of uit de eerste meetdagen (3 en 4-10-2026).
Nagebootste punten en een verzonnen IMEI; geen echte metingen, geen netwerk.

Draaien: python3 locatie/test_auto.py
"""
import json
import os
import sys
import tempfile
from datetime import datetime

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
PROEF, PROEF2 = "990000000000017", "990000000000025"
os.environ["LOCATIE_DB"] = os.path.join(tempfile.mkdtemp(), "start.db")
os.environ["ATRACK_IMEIS"] = f"{PROEF}:auto,{PROEF2}:draagbaar"
os.environ["TZ"] = "Europe/Brussels"

import app  # noqa: E402
import bronbeleid as B  # noqa: E402
import dagboek as D  # noqa: E402
import projectsync as P  # noqa: E402
import schema  # noqa: E402
import status as S  # noqa: E402

B.BRONNEN["auto"]["toestel_sha256"] = B.vingerafdruk(PROEF)

THUIS = (50.8000, 4.7000)
WERF = (50.9000, 4.6000)
VER = (51.0000, 4.4000)


def t(dag, u, m=0, s=0):
    return int(datetime(2026, 10, dag, u, m, s, tzinfo=B.BRUSSEL).timestamp())


def nieuwe_db():
    pad = os.path.join(tempfile.mkdtemp(), "locatie.db")
    app.DB_PAD = pad
    return schema.verbind(pad)


_teller = [0]


def punt(c, tst, plaats, soort="FRI", geb="vast interval", fix=1, vel=0, motion=None, verzonden=None,
         bron="auto", toestel=PROEF, dlat=0.0):
    """Eén punt plus zijn ruwe bericht, zoals de ontvanger het zou bewaren."""
    _teller[0] += 1
    motion = motion or ("automotive" if vel >= 5 else "stationary")
    c.execute("""INSERT INTO bericht (ontvangen, laatst_ontvangen, bron, toestel, protocol, soort, verzonden,
                                      posities_gemeld, posities_bewaard, verwerking, vingerafdruk, ruw)
                 VALUES (?, ?, ?, ?, 'atrack', ?, ?, 1, 1, 'punten', ?, 'proef')""",
              ((verzonden or tst) + 1, (verzonden or tst) + 1, bron, toestel, soort, verzonden or tst,
               "v%d" % _teller[0]))
    c.execute("""INSERT INTO punt (tst, lat, lon, vel, soort, motion, gebeurtenis, ontvangen, bron, hdop, fix,
                                   verzonden, gebufferd, toestel, berichtsoort, volgnr, teller)
                 VALUES (?, ?, ?, ?, 'location', ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 0, ?)""",
              (tst, plaats[0] + dlat, plaats[1], vel, motion, geb, (verzonden or tst) + 1, bron, 1 if fix else 0,
               fix, verzonden or tst, toestel, soort, "%04X" % _teller[0]))


def rit(c, van, tot, a, b, stap=30, **kw):
    n = max(1, (tot - van) // stap)
    for i in range(n + 1):
        f = i / n
        punt(c, van + i * stap, (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f), vel=50, **kw)


def parkeer(c, tst, plaats, **kw):
    """Aankomen, stilstaan en de motor uit, zoals op 03-10-2026."""
    punt(c, tst, plaats, vel=0, **kw)
    punt(c, tst + 30, plaats, soort="STT", geb="beweging", motion="stationary", **kw)
    punt(c, tst + 60, plaats, soort="VGF", geb="motor uit", **kw)


def vertrek(c, uit_tst, aan_tst, plaats, naar, **kw):
    """Motor aan zonder fix (meettijd van het 'motor uit', moment = verzendtijd), dan rijden."""
    punt(c, uit_tst, plaats, soort="VGN", geb="motor aan", fix=0, verzonden=aan_tst, motion="automotive", **kw)
    rit(c, aan_tst + 30, aan_tst + 30 + 600, (plaats[0] + 0.0015, plaats[1]), naar, **kw)


def soorten(ind):
    return [s["soort"] + ("/p" if s.get("parkeren") else "") for s in ind]


def test_parkeren_na_motor_uit_is_gemeten_stilstand_tot_motor_aan():
    """03-10-2026: na 'motor uit' kwam er 41 minuten niets; dat is geparkeerd, geen gat."""
    c = nieuwe_db()
    rit(c, t(5, 8), t(5, 8, 20), THUIS, WERF)
    parkeer(c, t(5, 8, 21), WERF)
    vertrek(c, t(5, 8, 22), t(5, 10, 30), WERF, VER)
    c.commit()
    g = app.dag_gegevens("2026-10-05", nu=t(5, 23))
    ind = g["sporen"]["auto"]["indeling"]
    park = [s for s in ind if s.get("parkeren") and s["van"] < t(5, 11)]
    assert park, soorten(ind)
    p = park[0]
    assert p["tot"] == t(5, 10, 30), "het verblijf loopt tot de motor aansloeg, niet tot het eerste punt"
    assert "motor uit" in p["bewijs"] and "motor aan om 10:30" in p["bewijs"], p["bewijs"]
    assert not any(s["soort"] == "gat" and s["van"] < t(5, 10, 30) and s["tot"] > t(5, 8, 22) for s in ind), \
        soorten(ind)


def test_motor_uit_en_daarna_ver_weg_blijft_een_gat():
    c = nieuwe_db()
    rit(c, t(5, 8), t(5, 8, 20), THUIS, WERF)
    parkeer(c, t(5, 8, 21), WERF)
    rit(c, t(5, 10, 30), t(5, 10, 50), VER, THUIS)       # eerste punt na de stilte 25 km verder
    c.commit()
    ind = app.dag_gegevens("2026-10-05", nu=t(5, 23))["sporen"]["auto"]["indeling"]
    gaten = [s for s in ind if s["soort"] == "gat" and not s.get("open") and not s.get("open_begin")]
    assert gaten and gaten[0]["van"] >= t(5, 8, 21), soorten(ind)


def test_punten_zonder_fix_bewijzen_geen_bezoek_en_geen_afstand():
    """In de audit kon een autopunt met fix 0 een bezoek worden."""
    c = nieuwe_db()
    rit(c, t(5, 8), t(5, 8, 20), THUIS, WERF)
    for i in range(12):                                   # 55 min 'aanwezig' op VER, maar zonder fix
        punt(c, t(5, 9) + i * 300, VER, fix=0, geb="vast interval")
    rit(c, t(5, 10), t(5, 10, 20), WERF, THUIS)
    c.commit()
    g = app.dag_gegevens("2026-10-05", nu=t(5, 23))
    ind = g["sporen"]["auto"]["indeling"]
    assert not any(s["soort"] == "bezoek" and app.afstand(s["lat"], s["lon"], *VER) < 1000 for s in ind), soorten(ind)
    for s in ind:
        for lat, lon in s.get("spoor") or []:
            assert app.afstand(lat, lon, *VER) > 1000, "een punt zonder fix telde mee in een rit"
    assert g["sporen"]["auto"]["zonder_fix"] == 12


def test_herhaald_verwerken_verandert_de_uitkomst_niet():
    c = nieuwe_db()
    rit(c, t(5, 8), t(5, 8, 20), THUIS, WERF)
    parkeer(c, t(5, 8, 21), WERF)
    vertrek(c, t(5, 8, 22), t(5, 10, 30), WERF, THUIS)
    c.commit()
    een = json.dumps(app.dag_gegevens("2026-10-05", nu=t(5, 23))["sporen"], sort_keys=True, default=str)
    twee = json.dumps(app.dag_gegevens("2026-10-05", nu=t(5, 23))["sporen"], sort_keys=True, default=str)
    assert een == twee


def test_een_verblijf_over_de_startgrens_krijgt_geen_ouder_bewijs():
    """Op 2-10 om 23:00 geparkeerd (oude reeks), op 3-10 om 7:00 het eerste nieuwe punt.
    Het verblijf voor 7:00 wordt niet gereconstrueerd uit het oude punt."""
    c = nieuwe_db()
    parkeer(c, int(datetime(2026, 10, 2, 22, 58, tzinfo=B.BRUSSEL).timestamp()), WERF)
    punt(c, t(3, 7), WERF, vel=0)
    rit(c, t(3, 7, 1), t(3, 7, 20), WERF, THUIS)
    c.commit()
    g = app.dag_gegevens("2026-10-03", nu=t(3, 23))
    ind = g["sporen"]["auto"]["indeling"]
    assert not any(s.get("parkeren") and s.get("open_begin") for s in ind), soorten(ind)
    assert ind[0]["soort"] == "gat" and ind[0].get("open_begin") and ind[0]["meter"] is None, ind[0]
    for s in ind[1:]:
        assert s["van"] >= t(3, 7), s
    assert all(p["tst"] >= B.moment(B.STARTGRENS) for p in g["punten"])
    vorig = app.dag_gegevens("2026-10-02", nu=t(3, 23))
    assert vorig["buiten_reeks"] and vorig["punten"] == [] and vorig["sporen"] == {}
    ctx = D.context("2026-10-03", g)
    assert all(v["aankomst"] >= "2026-10-03" for v in ctx["verblijven"]), ctx["verblijven"]


def test_een_dag_begint_geparkeerd_sinds_de_vorige_avond():
    """04-10-2026: de auto vertrok pas om 21:30; de dag begon geparkeerd sinds 3-10 19:14."""
    c = nieuwe_db()
    rit(c, t(5, 18, 50), t(5, 19, 10), WERF, THUIS)
    parkeer(c, t(5, 19, 12), THUIS)
    vertrek(c, t(5, 19, 13), t(6, 21, 30), THUIS, WERF)
    c.commit()
    ind = app.dag_gegevens("2026-10-06", nu=t(7, 9))["sporen"]["auto"]["indeling"]
    eerste = ind[0]
    assert eerste.get("parkeren") and eerste.get("open_begin"), soorten(ind)
    assert (eerste["van"], eerste["tot"]) == (B.dagranden("2026-10-06")[0], t(6, 21, 30)), eerste
    assert "motor uit op 05-10 19:13" in eerste["bewijs"], eerste["bewijs"]
    # De vorige dag eindigt geparkeerd tot middernacht, geen open gat.
    vorige = app.dag_gegevens("2026-10-05", nu=t(7, 9))["sporen"]["auto"]["indeling"]
    assert vorige[-1].get("parkeren") and vorige[-1].get("loopt_door"), soorten(vorige)
    # Een dag helemaal zonder punten terwijl de auto geparkeerd staat.
    c2 = nieuwe_db()
    parkeer(c2, t(5, 19, 12), THUIS)
    c2.commit()
    ind = app.dag_gegevens("2026-10-06", nu=t(6, 15))["sporen"]["auto"]["indeling"]
    assert len(ind) == 1 and ind[0].get("parkeren") and ind[0]["tot"] == t(6, 15) and ind[0].get("open"), ind


def test_auto_en_draagbare_tracker_blijven_twee_sporen():
    """Geparkeerde autopunten filteren geen persoonlijke metingen weg; de persoon volgt
    het gedragen toestel."""
    oud = dict(B.BRONNEN["draagbaar"])
    B.BRONNEN["draagbaar"].update(status="actief", ingang=B.STARTGRENS, toestel_sha256=B.vingerafdruk(PROEF2))
    try:
        c = nieuwe_db()
        parkeer(c, t(5, 7), WERF)                               # auto staat de hele dag op de werf
        for i in range(30):                                     # persoon loopt van de werf weg en terug
            f = i / 29
            punt(c, t(5, 9) + i * 120, (WERF[0] + 0.02 * (1 - abs(2 * f - 1)), WERF[1]), vel=6,
                 bron="draagbaar", toestel=PROEF2)
        c.commit()
        g = app.dag_gegevens("2026-10-05", nu=t(5, 23))
        assert set(g["sporen"]) == {"auto", "draagbaar"}, g["sporen"].keys()
        auto = g["sporen"]["auto"]["indeling"]
        assert [s["soort"] for s in auto if s["soort"] != "gat"] == ["bezoek"], soorten(auto)
        persoon = g["sporen"]["draagbaar"]["indeling"]
        assert any(s["soort"] == "verplaatsing" for s in persoon), soorten(persoon)
        assert all(s["bron"] == "draagbaar" for s in persoon)
        assert app.hoofdspoor(g)["bron"] == "draagbaar"
    finally:
        B.BRONNEN["draagbaar"].clear()
        B.BRONNEN["draagbaar"].update(oud)


def test_een_los_meetpunt_gaat_mee_naar_buiten():
    """De Mac-export sloeg een dag zonder indeling over, ook met punten."""
    c = nieuwe_db()
    punt(c, t(5, 12), WERF, vel=0)
    c.commit()
    client = app.app.test_client()
    d = client.get("/api/dag/2026-10-05").get_json()
    assert len(d["punten"]) == 1 and d["punten"][0]["bron"] == "auto", d
    assert d["punten"][0]["ontvangen"] and d["punten"][0]["fix"] == 1 and "verzonden" in d["punten"][0]


def test_de_dag_api_geeft_bron_fix_en_ontvangst_mee():
    c = nieuwe_db()
    punt(c, t(5, 12), WERF, vel=0)
    punt(c, t(5, 12, 1), WERF, fix=0, soort="VGN", geb="motor aan", verzonden=t(5, 13))
    c.commit()
    d = app.app.test_client().get("/api/dag/2026-10-05").get_json()
    velden = set(d["punten"][0])
    for v in ("bron", "toestel", "fix", "geldig", "hdop", "ontvangen", "verzonden", "nagestuurd", "berichtsoort"):
        assert v in velden, v
    assert d["punten"][0]["toestel"].startswith("…"), "het IMEI gaat niet voluit naar buiten"
    assert [p["geldig"] for p in d["punten"]] == [True, False]


def test_status_alleen_de_auto_actief_geen_telefoonalarm():
    c = nieuwe_db()
    st = S.overzicht(c, nu=t(5, 12))
    per = {b["bron"]: b for b in st["bronnen"]}
    assert per["iphone"]["alarm"] is None and per["iphone"]["toestand"] == "uit gebruik"
    assert per["draagbaar"]["alarm"] is None and per["draagbaar"]["toestand"] == "nog niet aangesloten"
    # Lege database: expliciet 'geen gegevens', nooit 'laatste punt 0 min geleden'.
    assert per["auto"]["toestand"] == "geen gegevens" and per["auto"]["laatste_geldige_positie"] is None
    g = app.app.test_client().get("/gezond").get_json()
    assert g["bronnen"]["auto"]["minuten_geleden"] is None and g["bronnen"]["auto"]["toestand"] == "geen gegevens"


def test_status_geparkeerd_is_geen_storing_wegvallen_tijdens_rijden_wel():
    c = nieuwe_db()
    rit(c, t(5, 8), t(5, 8, 20), THUIS, WERF)
    parkeer(c, t(5, 8, 21), WERF)
    c.commit()
    b = S.bron(c, "auto", nu=t(5, 23))                      # vijftien uur later
    assert b["toestand"] == "geparkeerd" and b["alarm"] is None, b
    b = S.bron(c, "auto", nu=t(9, 9))                       # vier dagen later: een vraag, geen alarm
    assert b["alarm"] is None and b.get("vraag"), b
    c2 = nieuwe_db()
    rit(c2, t(5, 8), t(5, 8, 20), THUIS, WERF)              # geen motor uit: valt weg tijdens het rijden
    c2.commit()
    b = S.bron(c2, "auto", nu=t(5, 9, 40))
    assert b["alarm"] and "stil" not in b["alarm"]["titel"].lower(), b
    b = S.bron(c2, "auto", nu=t(5, 8, 50))                  # half uur: nog binnen het nalevervenster
    assert b["alarm"] is None, b


def test_dagboek_en_context_met_een_project():
    c = nieuwe_db()
    P.synchroniseer(c, ha=[{"firma": "HARC", "nummer": "9604", "project_id": "u", "naam": "9604 Werfstraat",
                            "adres": "Werfstraat 1, 3999 Proefdorp", "adres_bron": "projectmap (A13)",
                            "bron": "ha-projecten", "link": "https://ha-projecten.globaal.be/project/9604"}],
                    mappen={}, geocodeer=lambda a: {"lat": WERF[0], "lon": WERF[1], "kwaliteit": "adres",
                                                    "bron": "proef"})
    c.execute("INSERT INTO plek (naam, lat, lon, straal, soort) VALUES ('Thuis', ?, ?, 150, 'thuis')", THUIS)
    rit(c, t(5, 8), t(5, 8, 20), THUIS, WERF)
    parkeer(c, t(5, 8, 21), WERF)
    vertrek(c, t(5, 8, 22), t(5, 10, 30), WERF, THUIS)
    parkeer(c, t(5, 10, 42), THUIS)
    c.commit()
    g = app.dag_gegevens("2026-10-05", nu=t(5, 23))
    tekst = D.markdown("2026-10-05", g)
    assert "project HARC 9604" in tekst and "waarschijnlijk" in tekst and "(voorlopig)" in tekst, tekst
    assert "Thuis" in tekst
    ctx = D.context("2026-10-05", g)
    assert len(ctx["verblijven"]) == 1 and ctx["verblijven"][0]["project"]["sleutel"] == "HARC:9604", ctx
    assert all("Thuis" not in r for r in ctx["tekst"]), "de context bevat alleen wat bij een project hoort"
    assert "ha-projecten.globaal.be/project/9604" in ctx["tekst"][0]
    assert app.dag_gegevens("2026-10-05", nu=t(6, 7))["status"] == "afgesloten"


def test_een_correctie_via_het_portaal_wordt_bewaard_en_toegepast():
    c = nieuwe_db()
    rit(c, t(5, 8), t(5, 8, 20), THUIS, WERF)
    parkeer(c, t(5, 8, 21), WERF)
    vertrek(c, t(5, 8, 22), t(5, 10, 30), WERF, THUIS)
    c.commit()
    klant = app.app.test_client()
    r = klant.post("/api/correctie", json={"bron": "auto", "van": t(5, 9), "tot": t(5, 9, 30), "wat": "niet_mehdi"})
    assert r.status_code == 403, "zonder portaal of wachtwoord geen correctie"
    r = klant.post("/api/correctie", json={"bron": "auto", "van": t(5, 9), "tot": t(5, 9, 30), "wat": "niet_mehdi",
                                           "reden": "uitgeleend"},
                   headers={"X-authentik-username": "mehdi", "Origin": "http://localhost"})
    assert r.status_code == 200, r.data
    ind = app.dag_gegevens("2026-10-05", nu=t(5, 23))["sporen"]["auto"]["indeling"]
    p = [s for s in ind if s.get("parkeren") and s["van"] < t(5, 10)][0]
    assert p["herkenning"]["zekerheid"] == "niet_mehdi" and p["herkenning"]["correctie"]["door"] == "mehdi"


def test_het_scherm_opent_op_vandaag_en_ververst_zichzelf():
    nieuwe_db()
    klant = app.app.test_client()
    html = klant.get("/").get_data(as_text=True)
    assert 'setInterval(ververs, 45000)' in html
    assert B.vandaag().isoformat() in html
    # De telefoon staat alleen nog als bron die uit gebruik is, nooit als meetbron.
    assert "laatste bericht van de telefoon" not in html and "Staat OwnTracks aan" not in html
    assert "Telefoon (OwnTracks)" not in html or "uit gebruik" in html
    deel = klant.get("/?deel=1").get_data(as_text=True)
    assert "<html" not in deel and "Tracker in de auto" in deel


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

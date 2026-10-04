"""Bronstatus: per tracker wat er binnenkomt, en wat een stilte betekent.

Tot 04-10-2026 keek de bewaking naar "minuten sinds het laatste punt", over alle
bronnen heen, en noemde de telefoon. Op 4-10 stond de auto de hele dag geparkeerd
en kwam er elke twee uur "tracker zwijgt sinds N min, kijk de OwnTracks-app na":
een vals alarm over een bron die bewust gestopt is. Een lege database gaf
"laatste punt 0 min geleden".

Nu, per bron uit het bronbeleid:
  - een bron die niet actief is (de telefoon, de draagbare tracker die nog niet
    gekocht is) geeft nooit alarm, alleen zijn status;
  - een actieve bron zonder gegevens heet "geen gegevens", nooit "0 min geleden";
  - na "motor uit" is stilte verwacht zolang het toestel in spaarstand 1 staat:
    geparkeerd, geen storing. Pas na een paar dagen is dat een vraag ("leeft hij
    nog?"), omdat er in deze stand geen levensteken bestaat;
  - stilte zonder "motor uit" ervoor, langer dan het rijritme en de buffer
    toelaten, is wel een alarm.
"""
import json
import time

import bronbeleid as B

# Berichten die zeggen dat de auto (weer) in gebruik is.
IN_GEBRUIK = ("FRI", "ERI", "STT", "VGN", "STR", "IDN", "IDF")


def _min(seconden):
    return None if seconden is None else round(seconden / 60)


def _uur(tst):
    return B.lokaal(tst).strftime("%d-%m %H:%M") if tst else None


def bron(conn, naam, nu=None, toestellen=None):
    nu = int(nu or time.time())
    beleid = B.BRONNEN[naam]
    uit = {"bron": naam, "label": beleid.get("label"), "rol": beleid.get("rol"), "status": beleid["status"],
           "toestel": beleid.get("toestel"), "ingang": beleid.get("ingang"), "alarm": None}
    if beleid["status"] != "actief":
        uit.update(toestand={"uit_gebruik": "uit gebruik", "niet_aangesloten": "nog niet aangesloten"}.get(
            beleid["status"], beleid["status"]), uitleg=beleid.get("reden"))
        return uit
    toestellen = B.toestellen_uit_env() if toestellen is None else toestellen
    imeis = sorted(i for i, n in toestellen.items() if n == naam and B.toestel_klopt(naam, i))
    uit["meetmodus"] = beleid.get("meetmodus")
    if not imeis:
        uit.update(toestand="niet ingesteld",
                   uitleg="het vastgelegde toestel van deze bron staat niet onder deze naam in ATRACK_IMEIS",
                   alarm={"titel": "Locatietracker niet ingesteld",
                          "tekst": "De bron %s is actief, maar zijn toestel staat niet (juist) in ATRACK_IMEIS." % naam,
                          "sleutel": "locatie-bron-niet-ingesteld-%s" % naam})
        return uit
    uit["toestel_kort"] = ", ".join(B.toestel_kort(i) for i in imeis)
    q = ",".join("?" * len(imeis))
    grens = B.ingang(naam)

    laatste = conn.execute(f"""SELECT id, ontvangen, soort, verzonden FROM bericht
                               WHERE bron = ? AND toestel IN ({q}) ORDER BY id DESC LIMIT 1""",
                           [naam] + imeis).fetchone()
    geldig = conn.execute(f"""SELECT tst, ontvangen, berichtsoort, gebeurtenis, gebufferd FROM punt
                              WHERE bron = ? AND toestel IN ({q}) AND tst >= ? AND fix = 1
                              ORDER BY tst DESC LIMIT 1""", [naam] + imeis + [grens]).fetchone()
    if not laatste and not geldig:
        uit.update(toestand="geen gegevens", laatste_ontvangst=None, laatste_geldige_positie=None,
                   uitleg="er is nog niets van dit toestel binnengekomen sinds de ingang",
                   alarm={"titel": "Locatietracker levert geen gegevens",
                          "tekst": "Van de actieve bron %s is nog geen enkel bericht binnengekomen." % naam,
                          "sleutel": "locatie-geen-gegevens-%s" % naam})
        return uit

    uit["laatste_ontvangst"] = {"tijd": _uur(laatste["ontvangen"]), "tst": laatste["ontvangen"],
                                "minuten_geleden": _min(nu - laatste["ontvangen"]), "soort": laatste["soort"]}
    if geldig:
        uit["laatste_geldige_positie"] = {"tijd": _uur(geldig["tst"]), "tst": geldig["tst"],
                                          "minuten_geleden": _min(nu - geldig["tst"]),
                                          "vertraging_s": (geldig["ontvangen"] - geldig["tst"])
                                          if geldig["ontvangen"] else None,
                                          "nagestuurd": bool(geldig["gebufferd"])}
    else:
        uit["laatste_geldige_positie"] = None
    begin, _ = B.dagranden(B.vandaag().isoformat())
    vert = [r[0] for r in conn.execute(f"""SELECT ontvangen - tst FROM punt WHERE bron = ? AND toestel IN ({q})
                                           AND tst >= ? AND fix = 1 AND ontvangen IS NOT NULL ORDER BY 1""",
                                       [naam] + imeis + [max(begin, grens)])]
    uit["vertraging_vandaag"] = {"punten": len(vert), "mediaan_s": vert[len(vert) // 2] if vert else None,
                                 "p95_s": vert[int(len(vert) * 0.95)] if vert else None}
    uit["nagestuurd_totaal"] = conn.execute(
        f"SELECT count(*) FROM punt WHERE bron = ? AND toestel IN ({q}) AND gebufferd = 1", [naam] + imeis
    ).fetchone()[0]
    # Een bericht zonder positie (hartslag, teruggelezen instellingen): in rapportagemodus 2 komt er geen.
    uit["levensteken"] = _uur(conn.execute(
        f"""SELECT max(ontvangen) FROM bericht WHERE bron = ? AND toestel IN ({q})
            AND COALESCE(posities_gemeld, 0) = 0""", [naam] + imeis).fetchone()[0])

    uit_id = conn.execute(f"SELECT max(id) FROM bericht WHERE bron = ? AND toestel IN ({q}) AND soort = 'VGF'",
                          [naam] + imeis).fetchone()[0]
    gebruik_id = conn.execute(f"""SELECT max(id) FROM bericht WHERE bron = ? AND toestel IN ({q})
                                  AND soort IN ({','.join('?' * len(IN_GEBRUIK))})""",
                              [naam] + imeis + list(IN_GEBRUIK)).fetchone()[0]
    stilte = nu - laatste["ontvangen"]
    if uit_id and (not gebruik_id or uit_id > gebruik_id):
        sinds = conn.execute("SELECT ontvangen FROM bericht WHERE id = ?", (uit_id,)).fetchone()[0]
        uren = (nu - sinds) / 3600
        uit.update(toestand="geparkeerd", geparkeerd_sinds=_uur(sinds),
                   uitleg=("geparkeerd sinds %s (motor uit). In spaarstand 1 meldt het toestel pas weer bij "
                           "vertrek; stilte is hier verwacht en geen storing." % _uur(sinds)))
        if uren > beleid.get("geparkeerd_onbekend_uren", 72):
            uit["vraag"] = ("De auto staat volgens de tracker al %d uur geparkeerd. Of het toestel nog leeft is in "
                            "spaarstand 1 niet te zien; spaarstand 2 (AT+GTCFG veld 9) geeft elke 15 minuten een "
                            "levensteken." % uren)
    elif stilte <= 10 * 60:
        uit.update(toestand="in gebruik", uitleg="de auto meldt zich; laatste bericht %s" % _uur(laatste["ontvangen"]))
    else:
        uit.update(toestand="geen bericht zonder motor uit",
                   uitleg=("sinds %s niets meer, en het laatste bericht was geen 'motor uit'. Rijdend komt er elke "
                           "30 s een punt; wat zonder netwerk gemeten is komt later na." % _uur(laatste["ontvangen"])))
        if stilte > beleid.get("stil_rijdend_minuten", 60) * 60:
            # Geen "stil" in de titel: daarop belt De Bode (AGENTNORM, hoofdstuk 6).
            uit["alarm"] = {"titel": "Locatietracker valt weg zonder motor uit",
                            "tekst": ("De tracker in de auto meldt al %d minuten niets, en het laatste bericht "
                                      "was geen 'motor uit'. Stroom, simkaart of netwerk nakijken."
                                      % _min(stilte)),
                            "sleutel": "locatie-wegval-%s" % naam}
    return uit


def taken(conn, nu=None):
    nu = nu or time.time()
    rijen = {r["taak"]: dict(r) for r in conn.execute("SELECT * FROM taakstatus")}
    rijen.setdefault("ontvangst", {"taak": "ontvangst"})
    laatste = conn.execute("SELECT max(ontvangen) FROM bericht").fetchone()[0]
    rijen["ontvangst"].update(laatst_geslaagd=laatste, laatst_geprobeerd=laatste)
    uit = []
    for taak in ("ontvangst", "projectsync", "dagboek", "export", "controle"):
        r = rijen.get(taak) or {"taak": taak}
        volgende = B.volgende_uitvoering(taak) if taak in B.PLANNING else None
        detail = r.get("detail")
        try:
            detail = json.loads(detail) if detail and detail.startswith("{") else detail
        except ValueError:
            pass
        uit.append({"taak": taak, "wat": (B.PLANNING.get(taak) or {}).get("wat", "berichten van de trackers"),
                    "laatst_geslaagd": _uur(r.get("laatst_geslaagd")),
                    "uren_geleden": round((nu - r["laatst_geslaagd"]) / 3600, 1) if r.get("laatst_geslaagd") else None,
                    "laatst_geprobeerd": _uur(r.get("laatst_geprobeerd")), "fout": r.get("fout"),
                    "volgende": volgende.strftime("%d-%m %H:%M") if volgende else None,
                    "waar": (B.PLANNING.get(taak) or {}).get("waar", "app-locatie-tracker"),
                    "detail": detail})
    return uit


def overzicht(conn, nu=None, toestellen=None):
    import projectsync  # noqa: PLC0415
    nu = int(nu or time.time())
    bronnen = [bron(conn, b, nu, toestellen) for b in B.BRONNEN]
    return {
        "gegenereerd": B.lokaal(nu).isoformat(),
        "beleid": {"versie": B.VERSIE, "startgrens": B.STARTGRENS, "eerste_dag": B.eerste_dag(),
                   "actief": B.actieve_bronnen()},
        "bronnen": bronnen,
        "alarmen": [b["alarm"] for b in bronnen if b.get("alarm")],
        "taken": taken(conn, nu),
        "projectdekking": projectsync.dekking(conn),
    }

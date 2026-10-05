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

import atrack as A
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
    imeis = B.toestellen_van(naam, toestellen)
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

    # Ontvangst: wanneer de server het laatst iets van dit toestel kreeg. Dat zegt alleen dat de
    # verbinding werkt, niets over waar of wanneer gemeten is.
    laatste = conn.execute(f"""SELECT id, ontvangen, soort, verzonden FROM bericht
                               WHERE bron = ? AND toestel IN ({q}) ORDER BY ontvangen DESC, id DESC LIMIT 1""",
                           [naam] + imeis).fetchone()
    geldig = conn.execute(f"""SELECT tst, ontvangen, berichtsoort, gebeurtenis, gebufferd FROM punt
                              WHERE bron = ? AND toestel IN ({q}) AND tst >= ? AND fix = 1 AND verdacht IS NULL
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
    verdacht = conn.execute(f"""SELECT count(*), max(ontvangen) FROM bericht WHERE bron = ? AND toestel IN ({q})
                                AND verdacht IS NOT NULL""", [naam] + imeis).fetchone()
    uit["verdacht"] = {"aantal": verdacht[0], "laatst": _uur(verdacht[1])}

    # Toestand: de laatste toestandsmelding volgens het toestel, op gebeurtenistijd (moment), binnen
    # de grens en van het toegelaten toestel. Nooit op ontvangstvolgorde: een ouder 'motor uit' dat
    # later uit de buffer komt, maakt een rijdende auto niet geparkeerd (controle 05-10-2026).
    soorten = ",".join("?" * len(IN_GEBRUIK + ("VGF",)))
    # Wat elke melding over de motor zegt komt uit atrack.motorstand: een GTSTT 11 naast een GTVGF
    # is eensgezind motor uit (rit van 05-10-2026), een GTSTT 41 zegt niets.
    rijen = conn.execute(f"""SELECT moment, berichtsoort, gebeurtenis, fix, bericht_id, ruw FROM punt
                             WHERE bron = ? AND toestel IN ({q}) AND moment IS NOT NULL AND moment >= ?
                             AND verdacht IS NULL AND berichtsoort IN ({soorten})
                             ORDER BY moment DESC, bericht_id DESC LIMIT 20""",
                         [naam] + imeis + [grens] + list(IN_GEBRUIK + ("VGF",))).fetchall()
    standen = [(r["moment"], s) for r in rijen if (s := A.motorstand(r["berichtsoort"], r["ruw"]))]
    stilte = nu - laatste["ontvangen"]
    if not standen:
        uit.update(toestand="onbekend",
                   uitleg="geen toestandsmelding met bekende gebeurtenistijd sinds de ingang; de toestand blijft onbekend")
        return uit
    hoogste = standen[0][0]
    gelijk = {s for m, s in standen if m == hoogste}
    if len(gelijk) > 1:
        uit.update(toestand="onbekend",
                   uitleg="motor uit en motor aan op hetzelfde moment (%s); de volgorde is niet vast te stellen"
                   % _uur(hoogste))
    elif gelijk == {"uit"}:
        uren = (nu - hoogste) / 3600
        uit.update(toestand="geparkeerd", geparkeerd_sinds=_uur(hoogste),
                   uitleg=("geparkeerd sinds %s (motor uit, tijd van het toestel). In spaarstand 1 meldt het toestel "
                           "pas weer bij vertrek; stilte is hier verwacht en geen storing." % _uur(hoogste)))
        if uren > beleid.get("geparkeerd_onbekend_uren", 72):
            uit["vraag"] = ("De auto staat volgens de tracker al %d uur geparkeerd. Of het toestel nog leeft is in "
                            "spaarstand 1 niet te zien; spaarstand 2 (AT+GTCFG veld 9) geeft elke 15 minuten een "
                            "levensteken." % uren)
    elif stilte <= 10 * 60:
        uit.update(toestand="in gebruik", uitleg="de auto meldt zich; laatste bericht %s" % _uur(laatste["ontvangen"]))
    else:
        uit.update(toestand="geen bericht zonder motor uit",
                   uitleg=("sinds %s niets meer, en de laatste toestandsmelding was geen 'motor uit'. Rijdend komt er "
                           "elke 30 s een punt; wat zonder netwerk gemeten is komt later na." % _uur(laatste["ontvangen"])))
        if stilte > beleid.get("stil_rijdend_minuten", 60) * 60:
            # Geen "stil" in de titel: daarop belt De Bode (AGENTNORM, hoofdstuk 6).
            uit["alarm"] = {"titel": "Locatietracker valt weg zonder motor uit",
                            "tekst": ("De tracker in de auto meldt al %d minuten niets, en de laatste toestandsmelding "
                                      "was geen 'motor uit'. Stroom, simkaart of netwerk nakijken." % _min(stilte)),
                            "sleutel": "locatie-wegval-%s" % naam}
    if verdacht[0] and verdacht[1] and nu - verdacht[1] < 7 * 86400 and not uit.get("alarm"):
        uit["alarm"] = {"titel": "Verdachte berichten van de locatietracker",
                        "tekst": ("Er kwamen %d bericht(en) binnen met het IMEI van de auto die niet kloppen "
                                  "(protocolversie, toestelnaam of een onmogelijke sprong). Ze tellen niet mee." % verdacht[0]),
                        "sleutel": "locatie-verdacht-%s" % naam}
    return uit


# Hoe oud een taak mag zijn voor ze een melding geeft (controle 05-10-2026: projectsync 48 uur en
# export 49 uur oud gaven een geslaagde controle).
VERSHEID_UREN = 36
VERSHEID_TITEL = {"projectsync": "Projectadressen van het locatielogboek niet bijgewerkt",
                  "dagboek": "Locatiedagboek loopt achter",
                  "export": "Export van het locatielogboek naar Dropbox loopt achter"}


def taakalarmen(taken_, nu=None):
    """Per taak een melding als ze faalde of langer dan VERSHEID_UREN niet meer slaagde."""
    nu = nu or time.time()
    uit = []
    for t in taken_:
        if t["taak"] not in VERSHEID_TITEL:
            continue
        oud = t.get("uren_geleden")
        if t.get("fout"):
            reden = "laatste poging mislukt: %s" % t["fout"]
        elif oud is None:
            reden = "nog nooit geslaagd"
        elif oud > VERSHEID_UREN:
            reden = "laatst geslaagd %s, %d uur geleden" % (t.get("laatst_geslaagd"), oud)
        else:
            continue
        uit.append({"titel": VERSHEID_TITEL[t["taak"]],
                    "tekst": "%s (%s). %s." % (t.get("wat") or t["taak"], t.get("waar") or "", reden),
                    "sleutel": "locatie-taak-%s" % t["taak"]})
    return uit


def taken(conn, nu=None):
    nu = nu or time.time()
    rijen = {r["taak"]: dict(r) for r in conn.execute("SELECT * FROM taakstatus")}
    rijen.setdefault("ontvangst", {"taak": "ontvangst"})
    # Ontvangst van de actieve trackers, niet van de telefoon die uit gebruik is.
    imeis = [i for b in B.actieve_bronnen() for i in B.toestellen_van(b)]
    laatste = conn.execute("SELECT max(ontvangen) FROM bericht WHERE toestel IN (%s)" % ",".join("?" * len(imeis)),
                           imeis).fetchone()[0] if imeis else None
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
    taken_ = taken(conn, nu)
    dekking = projectsync.dekking(conn)
    ps = next((t for t in taken_ if t["taak"] == "projectsync"), {})
    dekking["laatst_geslaagd"], dekking["uren_geleden"], dekking["fout"] = (
        ps.get("laatst_geslaagd"), ps.get("uren_geleden"), ps.get("fout"))
    dekking["verouderd"] = bool(ps.get("fout")) or ps.get("uren_geleden") is None or \
        (ps.get("uren_geleden") or 0) > VERSHEID_UREN
    return {
        "gegenereerd": B.lokaal(nu).isoformat(),
        "beleid": {"versie": B.VERSIE, "startgrens": B.STARTGRENS, "eerste_dag": B.eerste_dag(),
                   "actief": B.actieve_bronnen(), "ingesteld": B.ingesteld(toestellen)},
        "bronnen": bronnen,
        "alarmen": [b["alarm"] for b in bronnen if b.get("alarm")] + taakalarmen(taken_, nu),
        "taken": taken_,
        "projectdekking": dekking,
    }

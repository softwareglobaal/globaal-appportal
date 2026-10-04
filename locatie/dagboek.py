"""Het dagboek van een dag, en de locatiecontext voor agents. Eén generator.

Tot 04-10-2026 maakten twee scripts elk hun eigen dagboek uit dezelfde punten: De
Locatiewacht op de VM (met bouwplaatsen en de agenda) en het Mac-script (met
adressen). Ze liepen uit elkaar in wat een plek heette en wat een gat was. Nu
maakt deze module het dagboek; De Locatiewacht zet er de vergelijking met de
agenda onder en het Mac-script kopieert het resultaat. Alle drie dezelfde tekst.

De context voor agents bevat alleen wat bij een project hoort (auto bij project,
aankomst, vertrek, zekerheid, bewijs, link). Mehdi's volledige
bewegingsgeschiedenis gaat niet mee: wie de context leest ziet een dossier, geen
spoor.
"""
import time

import bronbeleid as B

WIJZE = {"automotive": "auto", "cycling": "fiets", "walking": "te voet", "running": "lopend"}
ZEKERHEID = {"bevestigd": "bevestigd door Mehdi", "waarschijnlijk": "waarschijnlijk", "kort": "kort gestopt",
             "onzeker": "onzeker, meerdere kandidaten", "geen": "", "niet_mehdi": "auto niet bij Mehdi"}
VASTE_PLEK_DAGEN = 5


def uur(tst):
    return B.lokaal(tst).strftime("%H:%M")


def duur(minuten):
    m = int(minuten or 0)
    return f"{m // 60}u{m % 60:02d}" if m >= 60 else f"{m} min"


def km(meter):
    return f"{(meter or 0) / 1000:.1f}".replace(".", ",")


def adres_sleutel(lat, lon):
    return f"{lat:.4f},{lon:.4f}"


def vul_adressen(conn, dag, verblijven, opzoeken=False, maximum=25):
    """Zet bij elk verblijf zonder plek of project een adres, uit de cache of (opzoeken)
    via Nominatim, en telt op hoeveel dagen er een verblijf op die plek was. Die telling
    begint bij de actieve reeks: niets geleerd uit de oude telefoonmetingen."""
    import geocode  # noqa: PLC0415
    gezocht = 0
    for s in verblijven:
        if s.get("lat") is None:
            continue
        sleutel = adres_sleutel(s["lat"], s["lon"])
        rij = conn.execute("SELECT adres FROM adrescache WHERE sleutel = ?", (sleutel,)).fetchone()
        if not rij and opzoeken and gezocht < maximum:
            gezocht += 1
            a = geocode.omgekeerd(s["lat"], s["lon"])
            if a:
                conn.execute("INSERT OR REPLACE INTO adrescache (sleutel, adres, volledig, bron, gezet) "
                             "VALUES (?, ?, ?, 'nominatim', ?)", (sleutel, a["adres"], a["volledig"], int(time.time())))
                rij = (a["adres"],)
        s["adres"] = rij[0] if rij else None
        if B.dag_toegestaan(dag):
            conn.execute("INSERT OR IGNORE INTO adresbezoek (sleutel, datum) VALUES (?, ?)", (sleutel, dag))
        n = conn.execute("SELECT count(*) FROM adresbezoek WHERE sleutel = ?", (sleutel,)).fetchone()[0]
        s["vaste_plek"] = n >= VASTE_PLEK_DAGEN
    conn.commit()


def waar(s):
    h = s.get("herkenning") or {}
    p = h.get("project")
    if h.get("zekerheid") == "onzeker":
        return "een van: " + ", ".join("%s %s (%d m)" % (k.get("firma") or "?", k["nummer"], k["afstand_m"])
                                       for k in h.get("kandidaten", []))
    if p:
        tekst = "project %s %s" % (p.get("firma") or "", p.get("nummer"))
        if p.get("adres"):
            tekst += ", " + p["adres"]
        if p.get("afstand_m") is not None:
            tekst += " (%d m)" % p["afstand_m"]
        return tekst
    if h.get("plek") or s.get("plek"):
        return h.get("plek") or s.get("plek")
    if s.get("adres"):
        return s["adres"] + (" (vaste plek)" if s.get("vaste_plek") else "")
    return "%.5f, %.5f" % (s["lat"], s["lon"])


def regel(s):
    tijd = f"| {uur(s['van'])} | {uur(s['tot'])} | {duur(s['minuten'])} |"
    if s["soort"] == "bezoek":
        h = s.get("herkenning") or {}
        wat = "geparkeerd" if s.get("parkeren") else ("stop" if s.get("stop") else "verblijf")
        if h.get("aard") == "kort_stoppen":
            wat = "kort " + ("geparkeerd" if s.get("parkeren") else "gestopt")
        if s.get("open_begin"):
            wat += " (al van daarvoor)"
        if s.get("open"):
            wat += " (loopt door)" if s.get("loopt_door") else " (nog niet vertrokken)"
        bewijs = s.get("bewijs") or ("%d punten" % s.get("punten", 0))
        zeker = ZEKERHEID.get(h.get("zekerheid"), h.get("zekerheid") or "")
        return f"{tijd} {wat} | {waar(s)} | {zeker} | {bewijs} |"
    if s["soort"] == "gat":
        if s.get("open"):
            return f"{tijd} geen meting | sindsdien niets meer binnen | | |"
        if s.get("open_begin"):
            return f"{tijd} geen meting | voor het eerste punt van de dag | | |"
        return f"{tijd} geen meting | {km(s.get('meter'))} km hemelsbreed tussen voor en na | | |"
    voorbij = s.get("voorbij") or []
    extra = ("; voorbij " + ", ".join("%s %s" % (v.get("firma") or "", v["nummer"]) for v in voorbij)) if voorbij else ""
    return f"{tijd} rit {WIJZE.get(s.get('wijze'), s.get('wijze') or '')} | {km(s.get('meter'))} km{extra} | | |"


def markdown(dag, gegevens):
    """Het dagboek als tekst. gegevens is wat app.dag_gegevens() teruggeeft."""
    titel = f"# Locatielogboek {dag}" + (" (voorlopig)" if gegevens.get("status") == "voorlopig" else "")
    r = [titel, ""]
    if gegevens.get("buiten_reeks"):
        r.append("Deze dag valt voor de start van de actieve meetreeks (%s). Er wordt niets getoond of "
                 "herberekend uit oudere metingen." % B.eerste_dag())
        return "\n".join(r) + "\n"
    for bron, spoor in (gegevens.get("sporen") or {}).items():
        ind = spoor["indeling"]
        verblijven = [s for s in ind if s["soort"] == "bezoek"]
        ritten = [s for s in ind if s["soort"] == "verplaatsing"]
        gaten = [s for s in ind if s["soort"] == "gat"]
        r.append("## %s" % (spoor.get("label") or bron))
        r.append("")
        r.append("Bron %s, rol %s: %s." % (bron, spoor.get("rol"), B.ROLLEN.get(spoor.get("rol"), "")))
        r.append("%d verblijven, %d ritten, %s km, %d geldige meetpunten%s." % (
            len(verblijven), len(ritten), km(sum(s.get("meter") or 0 for s in ritten)), spoor["geldig"],
            (", %d zonder fix niet gebruikt" % spoor["zonder_fix"]) if spoor.get("zonder_fix") else ""))
        if gaten:
            r.append("Zonder meting: %s, verspreid over %d stuk(ken)." % (duur(sum(s["minuten"] for s in gaten)),
                                                                        len(gaten)))
        r.append("")
        if not ind:
            r.append("Geen meting van deze tracker op deze dag." + (
                " %d losse punten zonder indeling, zie de JSON." % spoor["punten"] if spoor.get("punten") else ""))
            r.append("")
            continue
        r += ["| van | tot | duur | wat | waar | zekerheid | bewijs |", "|---|---|---|---|---|---|---|"]
        r += [regel(s) for s in ind]
        r.append("")
    r += ["---", "",
          "Een verblijf is minstens 8 minuten binnen 150 m; na 'motor uit' telt de stilte als geparkeerd tot de "
          "motor weer aanslaat. Een gat is een stilte waarvan niet gemeten is wat er gebeurde. Projectherkenning: "
          "binnen de straal van een projectadres (standaard 300 m); meer projecten in bereik blijven kandidaten. "
          "De tracker in de auto bewijst waar de auto stond, niet waar Mehdi was. Reeks sinds %s; bronbeleid v%s."
          % (B.eerste_dag(), B.VERSIE)]
    return "\n".join(r) + "\n"


def context(dag, gegevens, status=None):
    """De locatiecontext voor agents: alleen projectrelevante verblijven, met tijd en bron.

    Elke regel zegt van wanneer hij is, zodat oude context nooit als huidige locatie
    gelezen wordt. Onzekere herkenning blijft onzeker.
    """
    uit = {"dag": dag, "gemaakt": B.lokaal(time.time()).isoformat(), "status_dag": gegevens.get("status"),
           "bronbeleid": B.VERSIE, "regel": "auto bij project is geen bewijs dat Mehdi er was",
           "verblijven": [], "tekst": []}
    if gegevens.get("buiten_reeks"):
        uit["tekst"].append("Geen locatiecontext: de dag valt voor de start van de meetreeks.")
        return uit
    for bron, spoor in (gegevens.get("sporen") or {}).items():
        for s in spoor["indeling"]:
            h = s.get("herkenning") or {}
            if s["soort"] != "bezoek" or h.get("zekerheid") in (None, "geen"):
                continue
            p = h.get("project")
            item = {"bron": bron, "rol": spoor.get("rol"), "aankomst": B.lokaal(s["van"]).isoformat(),
                    "vertrek": None if s.get("open") and not s.get("loopt_door") else B.lokaal(s["tot"]).isoformat(),
                    "minuten": s["minuten"], "zekerheid": h.get("zekerheid"), "reden": h.get("reden"),
                    "formulering": h.get("formulering"), "aard": h.get("aard"),
                    "project": p, "kandidaten": h.get("kandidaten") if not p else None,
                    "bewijs": s.get("bewijs") or "%d meetpunten" % s.get("punten", 0),
                    "correctie": h.get("correctie")}
            uit["verblijven"].append(item)
            wie = (", ".join("%s %s" % (k.get("firma") or "?", k["nummer"]) for k in h.get("kandidaten", []))
                   if not p else "%s %s" % (p.get("firma") or "", p.get("nummer")))
            uit["tekst"].append("%s, %s %s, aankomst %s, %s, zekerheid %s, bewijs: %s%s" % (
                spoor.get("label") or bron, "projectkandidaat" if not p else "project", wie, uur(s["van"]),
                ("nog ter plaatse" if s.get("open") and not s.get("loopt_door") else "vertrek " + uur(s["tot"])),
                h.get("zekerheid"), item["bewijs"], (", link: " + p["link"]) if p and p.get("link") else ""))
    if status:
        for b in status.get("bronnen", []):
            if b.get("status") == "actief":
                lg = b.get("laatste_geldige_positie") or {}
                uit["tekst"].append("%s: %s; laatste geldige meting %s." % (
                    b.get("label"), b.get("toestand"), lg.get("tijd") or "geen"))
        uit["bronnen"] = [{k: b.get(k) for k in ("bron", "label", "rol", "status", "toestand", "laatste_geldige_positie")}
                          for b in status.get("bronnen", [])]
    return uit

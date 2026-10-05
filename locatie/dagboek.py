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


def lees_adressen(conn, verblijven):
    """Zet bij elk verblijf het adres uit de cache en of het een vaste plek is. Schrijft niets:
    een leesroute mag de database niet veranderen (controle 05-10-2026)."""
    for s in verblijven:
        if s.get("lat") is None:
            continue
        sleutel = adres_sleutel(s["lat"], s["lon"])
        rij = conn.execute("SELECT adres FROM adrescache WHERE sleutel = ?", (sleutel,)).fetchone()
        s["adres"] = rij[0] if rij else None
        n = conn.execute("SELECT count(*) FROM adresbezoek WHERE sleutel = ?", (sleutel,)).fetchone()[0]
        s["vaste_plek"] = n >= VASTE_PLEK_DAGEN


def verrijk_adressen(conn, dag, verblijven, opzoeken=None, maximum=25):
    """De verrijkingstaak: ontbrekende adressen opzoeken en de bezoekdagen tellen.

    Eerst alle netwerkverzoeken, zonder dat er een schrijftransactie openstaat; daarna alles in
    één korte transactie. Zo blijft de ontvanger van de tracker schrijven terwijl Nominatim
    traag is (tot 25 vragen van elk een seconde of meer). De telling begint bij de actieve
    reeks: niets geleerd uit de oude telefoonmetingen. Geeft het aantal nieuwe adressen."""
    import geocode  # noqa: PLC0415
    opzoeken = opzoeken or geocode.omgekeerd
    sleutels = []
    for s in verblijven:
        if s.get("lat") is not None:
            sleutels.append((adres_sleutel(s["lat"], s["lon"]), s["lat"], s["lon"]))
    bekend = {r[0] for r in conn.execute("SELECT sleutel FROM adrescache")}
    nieuw = {}
    for sleutel, lat, lon in sleutels:
        if sleutel in bekend or sleutel in nieuw or len(nieuw) >= maximum:
            continue
        a = opzoeken(lat, lon)
        if a:
            nieuw[sleutel] = a
    nu = int(time.time())
    conn.execute("BEGIN IMMEDIATE")
    try:
        for sleutel, a in nieuw.items():
            conn.execute("INSERT OR REPLACE INTO adrescache (sleutel, adres, volledig, bron, gezet) "
                         "VALUES (?, ?, ?, 'nominatim', ?)", (sleutel, a["adres"], a.get("volledig"), nu))
        if B.dag_toegestaan(dag):
            for sleutel, _, _ in sleutels:
                conn.execute("INSERT OR IGNORE INTO adresbezoek (sleutel, datum) VALUES (?, ?)", (sleutel, dag))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return len(nieuw)


def versie(dagboek):
    """Een vingerafdruk van wat een lezer van het dagboek te zien krijgt (tekst en indeling)."""
    import hashlib  # noqa: PLC0415
    import json  # noqa: PLC0415
    kern = {"markdown": dagboek.get("markdown"), "sporen": dagboek.get("sporen"), "status": dagboek.get("status")}
    return hashlib.sha256(json.dumps(kern, sort_keys=True, default=str).encode()).hexdigest()[:16]


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


POSITIEF = ("waarschijnlijk", "bevestigd")


def positief(s):
    """Is dit verblijf een positief projectverblijf voor agents? Alleen een verblijf met een
    project en zekerheid waarschijnlijk of bevestigd. Nooit Thuis of een andere benoemde plek
    zonder dossier, een rit, een meetgat, of een verblijf dat Mehdi als geen project of
    'auto niet bij mij' rechtzette (controle 05-10-2026)."""
    h = s.get("herkenning") or {}
    if s.get("soort") != "bezoek" or not h.get("project") or h.get("zekerheid") not in POSITIEF:
        return False
    # Door Mehdi bevestigd is positief, ook thuis; anders nooit op een benoemde plek zonder dossier.
    return bool(h.get("correctie")) or not h.get("plek")


def context(dag, gegevens, status=None):
    """De locatiecontext voor agents.

    verblijven: alleen positieve projectverblijven ('auto bij project'), met tijd, bron, rol,
    zekerheid, reden en bewijs. kandidaten: onzekere of korte projectrelaties, uitdrukkelijk niet
    positief. Thuis, ritten, meetgaten en rechtgezette verblijven gaan niet mee; ze blijven in
    het dagboek als bewijs. Elke regel zegt van wanneer hij is, zodat oude context nooit als
    huidige locatie gelezen wordt. Mehdi's volledige spoor gaat niet mee.
    """
    uit = {"dag": dag, "gemaakt": B.lokaal(time.time()).isoformat(), "status_dag": gegevens.get("status"),
           "bronbeleid": B.VERSIE, "grens": B.STARTGRENS,
           "regel": "auto bij project is geen bewijs dat Mehdi er was",
           "verblijven": [], "kandidaten": [], "tekst": []}
    if gegevens.get("buiten_reeks"):
        uit["tekst"].append("Geen locatiecontext: de dag valt voor de start van de meetreeks.")
        return uit
    for bron, spoor in (gegevens.get("sporen") or {}).items():
        for s in spoor["indeling"]:
            h = s.get("herkenning") or {}
            if s["soort"] != "bezoek" or h.get("correctie") and h.get("zekerheid") != "bevestigd":
                continue
            ja = positief(s)
            if not ja and not (h.get("zekerheid") in ("onzeker", "kort") and not h.get("correctie")):
                continue
            p = h.get("project") if ja else None
            item = {"bron": bron, "rol": spoor.get("rol"), "positief": ja,
                    "aankomst": B.lokaal(s["van"]).isoformat(),
                    "vertrek": None if s.get("open") and not s.get("loopt_door") else B.lokaal(s["tot"]).isoformat(),
                    "minuten": s["minuten"], "zekerheid": h.get("zekerheid"), "reden": h.get("reden"),
                    "formulering": h.get("formulering"), "aard": h.get("aard"),
                    "project": p, "kandidaten": None if ja else (h.get("kandidaten") or []),
                    "bewijs": s.get("bewijs") or "%d meetpunten" % s.get("punten", 0),
                    "correctie": h.get("correctie")}
            (uit["verblijven"] if ja else uit["kandidaten"]).append(item)
            if ja:
                uit["tekst"].append("%s, project %s %s, aankomst %s, %s, zekerheid %s, bewijs: %s%s" % (
                    spoor.get("label") or bron, p.get("firma") or "", p.get("nummer"), uur(s["van"]),
                    ("nog ter plaatse" if s.get("open") and not s.get("loopt_door") else "vertrek " + uur(s["tot"])),
                    h.get("zekerheid"), item["bewijs"], (", link: " + p["link"]) if p.get("link") else ""))
    if status:
        for b in status.get("bronnen", []):
            if b.get("status") == "actief":
                lg = b.get("laatste_geldige_positie") or {}
                uit["tekst"].append("%s: %s; laatste geldige meting %s." % (
                    b.get("label"), b.get("toestand"), lg.get("tijd") or "geen"))
        uit["bronnen"] = [{k: b.get(k) for k in ("bron", "label", "rol", "status", "toestand", "laatste_geldige_positie")}
                          for b in status.get("bronnen", [])]
    return uit

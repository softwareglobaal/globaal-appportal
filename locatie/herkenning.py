"""Projectherkenning: welk project of welke plek hoort bij een verblijf, en hoe zeker.

Eén regel voor het dashboard, het dagboek, de export en De Locatiewacht. Tot
04-10-2026 keek de tegel in zijn eigen plekken en de agent daarnaast in een los
register uit de agenda (werkwijze/projecten.json), met elk een eigen straal; een
project zonder afspraak bestond voor geen van beide.

Wat hier vastligt, elk uit de opdracht v1.2:
  - Een project is firma plus nummer (sleutel 'HARC:2604'). Hetzelfde nummer bij
    twee firma's blijft twee projecten.
  - Liggen er meer projecten binnen bereik, dan blijven het kandidaten. Er wordt
    nooit willekeurig een dossier gekozen.
  - De tracker in de auto bewijst waar de auto stond. Dus "auto bij project" of
    "mogelijk werfbezoek", nooit "Mehdi was op de werf".
  - Een correctie van Mehdi gaat voor alles en blijft herleidbaar (wie, wanneer, waarom).
  - Straal en minimale duur zijn per plek in te stellen (projectplek_override, plek).
"""
from math import asin, cos, radians, sin, sqrt

# Een projectadres is het adres van het perceel; de auto staat vaak verderop
# geparkeerd. Dezelfde 300 m als De Locatiewacht sinds 24-09-2026 voor een bouwplaats
# gebruikte, en als de foto's bij een werfbezoek.
PROJECT_STRAAL = 300
# Een verblijf korter dan dit heet "kort gestopt", langer "verblijf".
KORT_MINUTEN = 20
# Alleen een geocode op huisnummer mag herkennen; een straat of gemeente is te grof.
BRUIKBAAR = ("adres", "override")


def afstand(lat1, lon1, lat2, lon2):
    r = 6371000
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


# ------------------------------------------------------------ lezen

def projectplekken(conn, alles=False):
    """De projectplekken met de overrides van Mehdi erover gelegd.

    alles=False: alleen wat mag herkennen (actief, met een geocode op huisnummer of
    een override, en niet uitgesloten).
    """
    over = {r["sleutel"]: dict(r) for r in conn.execute("SELECT * FROM projectplek_override")}
    uit = []
    for r in conn.execute("SELECT * FROM projectplek ORDER BY firma, nummer"):
        p = dict(r)
        o = over.get(p["sleutel"])
        if o:
            if o.get("lat") is not None and o.get("lon") is not None:
                p.update(lat=o["lat"], lon=o["lon"], geocode_bron="override", geocode_kwaliteit="override")
            if o.get("straal"):
                p["straal"] = o["straal"]
            if o.get("min_minuten"):
                p["min_minuten"] = o["min_minuten"]
            p["uitgesloten"] = bool(o.get("uitsluiten"))
            p["override"] = {"reden": o["reden"], "door": o["door"], "wanneer": o["wanneer"]}
        if not alles:
            if not p.get("actief") or p.get("uitgesloten") or p.get("lat") is None:
                continue
            if p.get("geocode_kwaliteit") not in BRUIKBAAR:
                continue
        uit.append(p)
    return uit


def plekken(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM plek")]


def correcties(conn, bron=None):
    sql = "SELECT * FROM bezoekcorrectie WHERE ingetrokken IS NULL"
    args = []
    if bron:
        sql += " AND bron = ?"
        args.append(bron)
    return [dict(r) for r in conn.execute(sql + " ORDER BY wanneer", args)]


# ------------------------------------------------------------ herkennen

def _project_uit(p, d):
    return {"sleutel": p["sleutel"], "firma": p.get("firma"), "nummer": p.get("nummer"),
            "project_id": p.get("project_id"), "naam": p.get("naam"), "adres": p.get("adres"),
            "bron": p.get("bron"), "link": p.get("link"), "afstand_m": round(d),
            "straal_m": int(p.get("straal") or PROJECT_STRAAL),
            "min_minuten": int(p.get("min_minuten") or 8)}


def kandidaten(lat, lon, plek_lijst, project_lijst, marge=0):
    """(plek, projectkandidaten) voor een punt.

    plek: de dichtste benoemde plek zonder dossier binnen haar straal (Thuis), of None.
    projectkandidaten: elk project binnen zijn straal, dichtste eerst. Een benoemde plek
    met een dossiernummer telt als een tweede ligging van dat project, als het nummer
    eenduidig bij één project hoort; anders staat ze er apart in, met firma onbekend.
    """
    per_sleutel = {}
    for p in project_lijst:
        d = afstand(lat, lon, p["lat"], p["lon"])
        if d <= (p.get("straal") or PROJECT_STRAAL) + marge:
            k = _project_uit(p, d)
            if k["sleutel"] not in per_sleutel or d < per_sleutel[k["sleutel"]]["afstand_m"]:
                per_sleutel[k["sleutel"]] = k
    naam_plek, beste = None, None
    for p in plek_lijst:
        if p.get("lat") is None or p.get("lon") is None:
            continue
        d = afstand(lat, lon, p["lat"], p["lon"])
        if d > (p.get("straal") or 150) + marge:
            continue
        nr = str(p.get("dossier") or "").strip()
        if not nr:
            if beste is None or d < beste:
                naam_plek, beste = p["naam"], d
            continue
        zelfde = [q for q in project_lijst if str(q.get("nummer")) == nr
                  and (not p.get("firma") or q.get("firma") == p.get("firma"))]
        if len(zelfde) == 1:
            k = _project_uit(zelfde[0], d)
            k["via_plek"] = p["naam"]
            if k["sleutel"] not in per_sleutel or d < per_sleutel[k["sleutel"]]["afstand_m"]:
                per_sleutel[k["sleutel"]] = dict(per_sleutel.get(k["sleutel"], k), afstand_m=round(d),
                                                 via_plek=p["naam"])
        else:
            sleutel = ("%s:%s" % (p["firma"], nr)) if p.get("firma") else "plek:%s" % p["naam"]
            per_sleutel.setdefault(sleutel, {
                "sleutel": sleutel, "firma": p.get("firma"), "nummer": nr, "project_id": p.get("project_id"),
                "naam": p["naam"], "adres": None, "bron": "plek", "link": None, "afstand_m": round(d),
                "straal_m": int(p.get("straal") or 150), "min_minuten": int(p.get("min_minuten") or 8),
                "via_plek": p["naam"],
                "opmerking": "firma onbekend" if not p.get("firma") and len(zelfde) != 1 else None})
    return naam_plek, sorted(per_sleutel.values(), key=lambda k: (k["afstand_m"], k["sleutel"]))


def _overlapt(c, van, tot):
    return c["van"] < tot and c["tot"] > van


def beoordeel(verblijf, plek_lijst, project_lijst, correctie_lijst=(), rol="auto"):
    """De herkenning van één verblijf (bezoek of stop): wat, hoe zeker en waarom."""
    van, tot = verblijf["van"], verblijf["tot"]
    minuten = verblijf.get("minuten") or round((tot - van) / 60)
    naam_plek, kand = kandidaten(verblijf["lat"], verblijf["lon"], plek_lijst, project_lijst)
    onderwerp = "auto" if rol == "auto" else "tracker"
    uit = {"plek": naam_plek, "kandidaten": kand, "project": None,
           "aard": "kort_stoppen" if minuten < KORT_MINUTEN else "verblijf"}

    # Een correctie van Mehdi wint, als ze dit verblijf overlapt.
    for c in reversed(list(correctie_lijst)):
        if not _overlapt(c, van, tot):
            continue
        bron_c = {"door": c["door"], "wanneer": c["wanneer"], "reden": c.get("reden"), "id": c.get("id")}
        if c["wat"] == "project":
            gekozen = next((k for k in kand if k["sleutel"] == c["sleutel"]), None) or \
                next(({**_project_uit(p, afstand(verblijf["lat"], verblijf["lon"], p["lat"], p["lon"]))}
                      for p in project_lijst if p["sleutel"] == c["sleutel"]), None) or \
                {"sleutel": c["sleutel"], "firma": c["sleutel"].split(":")[0] if ":" in c["sleutel"] else None,
                 "nummer": c["sleutel"].split(":")[-1]}
            uit.update(project=gekozen, zekerheid="bevestigd", correctie=bron_c,
                       reden="bevestigd door %s" % c["door"],
                       formulering="%s bij project %s %s (bevestigd)" % (onderwerp, gekozen.get("firma") or "",
                                                                        gekozen.get("nummer") or ""))
        elif c["wat"] == "geen_project":
            uit.update(kandidaten=[], zekerheid="bevestigd", correctie=bron_c,
                       reden="volgens %s geen project" % c["door"],
                       formulering="%s niet bij een project (bevestigd)" % onderwerp)
        else:
            uit.update(kandidaten=[], zekerheid="niet_mehdi", correctie=bron_c,
                       reden="volgens %s reed iemand anders met de auto" % c["door"],
                       formulering="auto, niet bij Mehdi (bevestigd)")
        return uit

    if not kand:
        uit.update(zekerheid="geen", reden="geen bekend project binnen bereik",
                   formulering="%s %s" % (onderwerp, "bij " + naam_plek if naam_plek else "op een plek zonder project"))
        return uit
    if len(kand) > 1:
        lijst = ", ".join("%s %s (%d m)" % (k.get("firma") or "?", k.get("nummer"), k["afstand_m"]) for k in kand)
        uit.update(zekerheid="onzeker",
                   reden="%d projecten binnen bereik; niet te onderscheiden op afstand" % len(kand),
                   formulering="%s bij een van deze projecten: %s" % (onderwerp, lijst))
        return uit
    k = kand[0]
    if minuten < k["min_minuten"]:
        uit.update(project=k, zekerheid="kort",
                   reden="%d m van het projectadres, maar korter dan %d min" % (k["afstand_m"], k["min_minuten"]),
                   formulering="%s kort gestopt bij project %s %s" % (onderwerp, k.get("firma") or "", k["nummer"]))
        return uit
    uit.update(project=k, zekerheid="waarschijnlijk",
               reden="%d m van het projectadres (straal %d m), %d min" % (k["afstand_m"], k["straal_m"], minuten),
               formulering=("auto bij project %s %s, mogelijk werfbezoek" if rol == "auto"
                            else "mogelijk bij project %s %s") % (k.get("firma") or "", k["nummer"]))
    return uit


def voorbij(spoor, project_lijst):
    """Projecten waar een rit door hun straal reed zonder te stoppen. Geen bezoek."""
    gezien = {}
    for lat, lon in spoor or []:
        for p in project_lijst:
            if p["sleutel"] in gezien:
                continue
            if afstand(lat, lon, p["lat"], p["lon"]) <= (p.get("straal") or PROJECT_STRAAL):
                gezien[p["sleutel"]] = {"sleutel": p["sleutel"], "firma": p.get("firma"), "nummer": p.get("nummer")}
    return list(gezien.values())

#!/usr/bin/env python3
"""De dagcontrole (laag 2): kijkt een dag na zoals Mehdi hem ziet, over alle agenda's heen.

Mehdi, 30-09-2026: "ik begrijp niet waarom je na zoveel tijd nog altijd niet beter wordt". De fouten van
die week (overlappende ritten in Boechout, een omweg langs huis na Belauto, de zitting die botste met Lara)
zag geen enkele test, want die keken naar de code en niet naar de dag. Deze controle draait na elke ronde
en na elke wijziging (--dag), en ook met de hand:

    ~/agents/.venv/bin/python dagcontrole.py --dag 2026-09-30

Wat de agent zelf mag herstellen (ritten, kleuren, !! vooraan) doet de ronde al; wat overblijft, meldt
deze controle. Wat alleen Mehdi kan beslissen (twee plaatsen tegelijk, een botsing met Lara, een klant
zonder naam) wordt een vraag in de agenda en een oproep (FR-71).
"""
import sys
from datetime import datetime, timedelta


def _w():
    """De agent zelf, ook als hij als hoofdprogramma draait (geen tweede kopie inladen)."""
    for naam in ("agenda_wacht", "__main__"):
        m = sys.modules.get(naam)
        if m is not None and hasattr(m, "lees_titel") and hasattr(m, "KALENDERS"):
            return m
    import agenda_wacht
    return agenda_wacht

# Soorten die Mehdi moet beslissen; de rest herstelt de agent zelf of is een fout in de agent.
VRAGEN = {"buiten_botsing", "lara_botsing", "zonder_klant", "tegen_dagmarker"}
KLANTSOORTEN = {"KB", "KO", "PB", "PO"}


def _tijd(x, veld):
    try:
        return datetime.fromisoformat(x[veld])
    except (KeyError, ValueError, TypeError):
        return None


def _overlapt(a, b):
    s1, e1, s2, e2 = _tijd(a, "start"), _tijd(a, "einde"), _tijd(b, "start"), _tijd(b, "einde")
    return bool(s1 and e1 and s2 and e2 and s1 < e2 and s2 < e1)


def dagcontrole(items, dag):
    """Geeft [{'soort', 'a', 'tekst'}] voor één dag. items: alle afspraken van alle agenda's (ook ritten en archief)."""
    W = _w()
    lara = {k for k, n in W.KALENDERS.items() if n == "Lara"}
    dagitems = [x for x in items if (x.get("start") or "")[:10] == dag and "T" in (x.get("start") or "")
                and not x.get("hele_dag") and not (x.get("kalender") or "").startswith("en.be#")
                and not (x.get("titel") or "").lower().startswith("canceled")]
    ritten = [x for x in dagitems if W.lees_titel(x["titel"])["reistijd"]]
    afspraken = [x for x in dagitems if x not in ritten]

    def buiten(x):
        info = W.lees_titel(x["titel"])
        return info["buiten"] or info["soort"] in W.BUITEN_SOORTEN

    buitens = sorted([x for x in afspraken if buiten(x) and not x.get("_archief")], key=lambda x: x["start"])
    uit = []

    def meld(soort, a, tekst):
        uit.append({"soort": soort, "a": a, "tekst": tekst})

    # 1. twee ritten die elkaar overlappen, op welke agenda ook
    for i, x in enumerate(ritten):
        for y in ritten[i + 1:]:
            if _overlapt(x, y):
                meld("rit_overlap", x, f"rit {x['start'][11:16]}-{x['einde'][11:16]} overlapt met rit "
                                       f"{y['start'][11:16]}-{y['einde'][11:16]} ({y['titel'][:35]})")
    # 2. een rit die door een buitenafspraak loopt (niet ervoor of erna, maar erdoor)
    for x in ritten:
        for a in buitens:
            if not _overlapt(x, a):
                continue
            if a.get("kalender") in lara:
                # te laat voor Lara: dat beslist Mehdi (gezien 30-09-2026: zitting tot 16:00, Lara om 16:00)
                meld("lara_botsing", a, f"de rit {x['start'][11:16]}-{x['einde'][11:16]} ({x['titel'][:35]}) komt te laat "
                                        f"voor {a['start'][11:16]} {a['titel'][:35]}")
            else:
                meld("rit_door_afspraak", x, f"rit {x['start'][11:16]}-{x['einde'][11:16]} loopt door "
                                             f"{a['start'][11:16]} {a['titel'][:40]}")
    # 3. omweg langs huis: naar huis en weer weg, terwijl er minder dan 90 minuten tussen twee buitenafspraken zit
    for a, b in zip(buitens, buitens[1:]):
        ea, sb = _tijd(a, "einde"), _tijd(b, "start")
        if not (ea and sb) or sb - ea >= timedelta(minutes=90):
            continue
        naar_huis = [x for x in ritten if "→ thuis" in x["titel"] and ea <= _tijd(x, "start") < sb]
        van_huis = [x for x in ritten if "thuis →" in x["titel"] and ea <= _tijd(x, "einde") <= sb]
        if naar_huis or van_huis:
            meld("omweg_langs_huis", a, f"na {a['start'][11:16]} {a['titel'][:30]} een rit langs huis, terwijl "
                                        f"{b['start'][11:16]} {b['titel'][:30]} maar {int((sb - ea).total_seconds() // 60)} min later begint")
    # 4. twee buitenafspraken tegelijk: op twee plaatsen tegelijk kan niet
    for i, a in enumerate(buitens):
        for b in buitens[i + 1:]:
            if _overlapt(a, b):
                meld("buiten_botsing", a, f"{a['start'][11:16]} {a['titel'][:35]} valt samen met "
                                          f"{b['start'][11:16]} {b['titel'][:35]}: op twee plaatsen tegelijk kan niet")
    # 5. een buitenafspraak die botst met Lara (haar afspraak of de rit ernaartoe)
    for a in buitens:
        if a.get("kalender") in lara:
            continue
        for x in dagitems:
            if x.get("kalender") in lara and _overlapt(a, x):
                meld("lara_botsing", a, f"{a['start'][11:16]}-{a['einde'][11:16]} {a['titel'][:35]} botst met Lara: "
                                        f"{x['start'][11:16]} {x['titel'][:35]}")
                break
    # 6. !! niet vooraan (de ronde zet het zelf recht; staat het er nog, dan liep er iets mis)
    for a in afspraken:
        if not a.get("deelnemers") and W.tekens_vooraan(a["titel"]) != a["titel"]:
            meld("titel_uitroep", a, "!! staat niet vooraan")
    # 7. een klantafspraak zonder naam en zonder projectnummer: Mehdi kan de klant niet aanspreken
    for a in afspraken:
        info = W.lees_titel(a["titel"])
        if info.get("firma") and info["soort"] in KLANTSOORTEN and not info["nummer"] \
                and not (info.get("klant") or "").strip(" ,-"):
            meld("zonder_klant", a, "klantafspraak zonder naam: wie is de klant?")
    # 10. een afspraak tegen een hele-dag-markering van die dag (Geen buiten afspraken Lara ophalen, geen auto, Buitenland,
    #     geen afspraken): wat die dag niet mag, staat er toch (FR-83, gezien 01-10-2026 voor vrijdag 02-10)
    markers = W.markeringen_uit(items, dag)
    for a in afspraken:
        m = W.markering_tegen(a["titel"], dag, markers)
        if m:
            meld("op_vrije_dag" if any(t == m and wat == "alles" for t, wat in markers) else "tegen_dagmarker", a,
                 f"'{m}' staat die hele dag, en toch staat dit gepland")
    # 9. een klant waar Mehdi naartoe gaat zonder projectnummer, van welke firma ook (FR-80)
    for a in afspraken:
        info = W.lees_titel(a["titel"])
        if info["soort"] == "KB" and not info["nummer"] and not a.get("_archief"):
            meld("klant_zonder_nummer", a, "klantafspraak buiten zonder projectnummer")
    # 8. een afspraak met iemand van buiten zonder telefoonnummer: bij vertraging kan niemand de persoon bellen (FR-77)
    for a in afspraken:
        info = W.lees_titel(a["titel"])
        if info.get("firma") and info["soort"] in W.EXTERNE_SOORTEN and not a.get("_archief") \
                and not W.telefoon_in(f"{a.get('locatie') or ''} {a.get('omschrijving') or ''}"):
            meld("zonder_telefoon", a, "geen telefoonnummer in de afspraak: bij vertraging kan niemand de persoon bellen")
    return uit


def op_dag(x, dag):
    """Staat x op deze dag? Een hele-dag-marker over meerdere dagen ('Mehdi: Buitenland' van 04-10 tot 12-10) telt op
    elke dag die hij dekt, niet alleen op de eerste. Gezien 30-09-2026: Claude vroeg of het werfbezoek van 05-10
    bewust geschrapt was, terwijl Mehdi die week in het buitenland is; de dagcontrole van 05-10 toonde de marker niet (FR-74)."""
    s, e = (x.get("start") or "")[:10], (x.get("einde") or "")[:10]
    return s == dag or bool(x.get("hele_dag") and s <= dag < (e or s))


def samenvatting(items, dag):
    """Leesbare dag plus bevindingen, zoals Claude ze na elke wijziging aan Mehdi toont, met de hele-dag-markers
    die de dag dekken (buitenland, geen auto, Lara): wat daar staat, vraagt Claude Mehdi niet."""
    W = _w()
    regels = []
    for x in sorted([x for x in items if op_dag(x, dag)], key=lambda x: (not x.get("hele_dag"), x.get("start", ""))):
        naam = W.KALENDERS.get(x.get("kalender"), x.get("_archief") or x.get("kalender", ""))[:10]
        if x.get("hele_dag"):
            e = (x.get("einde") or "")[:10]
            tot = f" (tot {e[8:10]}-{e[5:7]})" if e and e > (datetime.fromisoformat(x["start"][:10]) + timedelta(days=1)).date().isoformat() else ""
            regels.append(f"  hele dag    {naam:10} {x['titel'][:80]}{tot}")
        else:
            regels.append(f"  {x['start'][11:16]}-{(x.get('einde') or '')[11:16]} {naam:10} {x['titel'][:80]}")
    b = dagcontrole(items, dag)
    regels.append(f"  dagcontrole {dag}: " + ("in orde" if not b else f"{len(b)} bevinding(en)"))
    regels += [f"    - {x['soort']}: {x['tekst']}" for x in b]
    return "\n".join(regels)


if __name__ == "__main__":
    W = _w()
    dag = sys.argv[sys.argv.index("--dag") + 1] if "--dag" in sys.argv else W.nu_lokaal().date().isoformat()
    offset = (datetime.fromisoformat(dag).date() - W.nu_lokaal().date()).days
    alles = [a for a in W.afspraken(offset - 1, offset + 2) if not a.get("fout")] + W.archief_afspraken(offset - 1, offset + 2)
    print(samenvatting(alles, dag))

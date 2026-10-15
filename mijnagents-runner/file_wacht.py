#!/usr/bin/env python3
"""De Filewacht: belt Mehdi als de file zijn buffer opeet.

Voor elke buitenafspraak die binnen twee uur begint vraagt hij de rijtijd opnieuw op
met het verkeer van dit moment, vanaf het vertrekpunt van haar heenblok (thuis of de
vorige buitenafspraak) en op het vertrekuur van dat blok. Duurt de rit meer dan de buffer
langer dan het heenblok dat in de agenda staat, dan haalt hij zijn afspraak niet en wordt
hij gebeld. Een afspraak wordt hoogstens één keer per twintig minuten nagerekend en
hoogstens twee keer gebeld, zodat de Google-aanroepen en de telefoon beperkt blijven.

Draaien:  ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/file_wacht.py
          --droog   alleen tonen, niet bellen, de stand niet bewaren
Alleen een geplande ronde (cron, met --ronde) belt; met de hand gestart gedraagt hij zich als --droog (Codex A19).
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W                      # noqa: E402
from koppelingen import agenda as A           # noqa: E402
from koppelingen import bellen                # noqa: E402

STAND = Path.home() / "appportal/mijnagents-data/file-wacht.json"
VOORUIT_MIN = 120      # zover vooruit kijken
HERTEST_MIN = 20       # niet vaker dan dit per afspraak narekenen
MAX_OPROEPEN = 1       # per afspraak per dag: een oproep volstaat (Mehdi, 25-09-2026)
DROOG = "--droog" in sys.argv
if DROOG:
    # Een proefronde mag de betaalde Google-aanroepen niet opeten. Op 20-09-2026 stond
    # de teller door mijn eigen proeven op 100 van 100 en viel alles terug op de filefactor.
    W.ROUTES_KEY = ""


def stand():
    try:
        d = json.loads(STAND.read_text())
        return d if d.get("dag") == datetime.now().strftime("%Y-%m-%d") else {"dag": datetime.now().strftime("%Y-%m-%d")}
    except (OSError, ValueError):
        return {"dag": datetime.now().strftime("%Y-%m-%d")}


def bewaar(d):
    STAND.parent.mkdir(parents=True, exist_ok=True)
    STAND.write_text(json.dumps(d, indent=0))


# De omschrijving van een ritblok van de agent eindigt op '; rit <van> → <naar>)'. Geen ';' in de groepen: zo neemt
# een titel met 'rit' erin het vertrekpunt niet over (Codex A12, 15-10-2026).
RIT_RE = re.compile(r"\brit ([^;]+?) → ([^;]+?)\)")


def is_buiten(info, soorten=("PB", "KB")):
    return not info["reistijd"] and bool(info["buiten"] or info["soort"] in soorten)


def adres_van(a, info, projecten):
    """Het adres van een buitenafspraak, gezocht zoals de agent het zoekt: de locatie, anders het projectadres, anders
    een benoemde plek, anders een vaste plek. Zo geeft ritlabel hier hetzelfde label als in het ritblok van de agent
    (Codex A12, 15-10-2026). Leeg als er geen is."""
    adres = a.get("locatie") or ""
    if adres and not adres.lower().startswith("http"):
        return adres
    if info["nummer"] and info["nummer"] in projecten:
        return projecten[info["nummer"]]["adres"]
    gevonden, _ = W.plek_zoeken(a["titel"] + " " + (a.get("omschrijving") or ""))
    if gevonden:
        return gevonden
    _, vp = W.vaste_plek(a["titel"])
    return (vp or {}).get("adres") or ""


def heenblok(a, start, reistijden):
    """Het heenblok van deze afspraak, gekozen zoals de agent het kiest: het reistijdblok op haar agenda dat eindigt op
    haar begin, of het blok dat haar titel draagt ('Reistijd voor: <titel>'). Tot 15-10-2026 nam ik het laatste
    reistijdblok binnen drie uur ervoor, ook de terugrit van een andere afspraak (Codex A12). Een terugrit
    ('Reistijd na:') is nooit een heenblok."""
    eigen = [x for x in reistijden if x.get("kalender") == a.get("kalender") and "T" in (x.get("start") or "")
             and "Reistijd na:" not in (x.get("omschrijving") or "")]
    for x in eigen:
        try:
            if datetime.fromisoformat(x["einde"]) == start:
                return x
        except (KeyError, ValueError):
            continue
    for x in eigen:
        if x["start"][:10] == a["start"][:10] and W.rit_hoort_bij(x, a["titel"], "voor"):
            return x
    return None


def vertrekpunt(a, adres, blok, items, thuis, cache, projecten):
    """Waar de rit naar deze afspraak vertrekt: (coördinaten, 'thuis' of 'vorige afspraak'), of (None, reden).
    Werkwijze: thuis, of de vorige buitenafspraak van dezelfde dag. Het ritblok van de agent zegt welke
    ('rit <van> → <naar>)'); <van> is ritlabel(adres van de vorige, adres van deze), zoals de agent het schreef.
    Tot 15-10-2026 rekende ik altijd vanaf thuis, ook als de rit van de vorige afspraak vertrok (Codex A12).
    Wat ik niet zeker weet, gok ik niet. De reden noemt geen plaats: die kan uit een privé-afspraak komen (A25)."""
    start = datetime.fromisoformat(a["start"])
    eerder = []
    for p in items:
        if p is a or p.get("fout") or p.get("hele_dag") or (p.get("start") or "")[:10] != a["start"][:10]:
            continue
        try:
            if datetime.fromisoformat(p["start"]) >= start:
                continue
        except (KeyError, ValueError):
            continue
        ip = W.lees_titel(p.get("titel") or "")
        if is_buiten(ip, W.BUITEN_SOORTEN):
            eerder.append((p, adres_van(p, ip, projecten)))
    thuis_ok = (thuis, "thuis") if thuis else (None, "het thuisadres is niet te vinden")
    gevonden = RIT_RE.findall((blok or {}).get("omschrijving") or "")
    if not gevonden:
        # geen ritblok van de agent met een vertrekpunt: alleen zeker als er die dag nog geen buitenafspraak was
        return thuis_ok if not eerder else (None, "geen ritblok met vertrekpunt, en er was die dag al een buitenafspraak")
    van = gevonden[-1][0].strip()
    if van == "thuis":
        return thuis_ok
    for p, p_adres in sorted(eerder, key=lambda z: z[0]["start"], reverse=True):
        if p_adres and W.ritlabel(p_adres, adres) == van:
            c = W.coord(p_adres, cache)
            return (c, "vorige afspraak") if c else (None, "het adres van de vorige afspraak is niet te vinden")
    return None, "het vertrekpunt in het ritblok is geen eerdere buitenafspraak van die dag"


def main():
    # Het masker van de agent zelf, geen eigen bord.Agent zonder masker: een titel of tekst uit een privébron
    # (privé-agenda, Lara, zorg) komt in geen enkele uitvoer (Codex A25, 15-10-2026).
    ag = W.ag
    # Alleen de geplande ronde belt (FR-59): '--ronde' en cron bij de voorouders. Met de hand gestart, ook met '--ronde',
    # is het een proefronde: rekenen en melden, niet bellen, de stand niet bewaren (Codex A19 en A27, 15-10-2026).
    proef = DROOG or not W.geplande_start()
    st = stand()
    nu = datetime.now().astimezone()
    grens = nu + timedelta(minutes=VOORUIT_MIN)
    items = W.afspraken(van_dagen=0, tot_dagen=1)
    ag.prive(W.prive_teksten(items))
    cache = W._cache_laden()
    thuis = W.coord(W.THUIS, cache)
    projecten = W.projectadressen.index()
    reistijden = [x for x in items if W.lees_titel(x["titel"])["reistijd"]]
    gemeld, gebeld = [], []

    for a in sorted(items, key=lambda x: x.get("start", "")):
        if a.get("fout") or a.get("hele_dag") or "T" not in (a.get("start") or ""):
            continue
        info = W.lees_titel(a["titel"])
        if not is_buiten(info):
            continue
        try:
            start = datetime.fromisoformat(a["start"])
        except ValueError:
            continue
        if not (nu < start <= grens):
            continue
        prive = W.is_prive(a)
        naam = "(privé)" if prive else a["titel"][:44]

        adres = adres_van(a, info, projecten)
        if not adres:
            continue

        sleutel = a.get("id") or a["titel"][:40]
        vorig = st.get(sleutel) or {}
        if vorig.get("laatst"):
            if (nu - datetime.fromisoformat(vorig["laatst"])).total_seconds() < HERTEST_MIN * 60:
                continue
        if vorig.get("oproepen", 0) >= MAX_OPROEPEN:
            continue

        doel = W.coord(adres, cache)
        if not doel:
            continue
        # het heenblok dat de wacht ervoor zette, is de planning: zijn vertrekpunt, zijn begin en zijn duur (A12)
        blok = heenblok(a, start, reistijden)
        van, waarvan = vertrekpunt(a, adres, blok, items, thuis, cache, projecten)
        if not van:
            print(ag.maskeer(f"  {naam} om {a['start'][11:16]}: niet nagerekend, {waarvan}"))
            continue
        try:
            b0 = datetime.fromisoformat(blok["start"]) if blok else None
            plan_min = (datetime.fromisoformat(blok["einde"]) - b0).total_seconds() / 60 if blok else None
        except (KeyError, ValueError):
            b0 = plan_min = None
        # vertrekken kan niet voor het heenblok begint (de vorige afspraak loopt dan nog), en niet in het verleden
        vertrek = max(nu, b0) if b0 else nu
        try:
            nodig, hoe = W.rijtijd_min(van, doel, vertrek)
        except Exception as e:  # noqa: BLE001
            print("rijtijd niet op te vragen:", type(e).__name__, file=sys.stderr)
            continue

        st[sleutel] = {"laatst": nu.isoformat(), "oproepen": vorig.get("oproepen", 0)}
        aankomst = vertrek + timedelta(minutes=nodig)
        te_laat = (aankomst - start).total_seconds() / 60
        verschil = (nodig - plan_min) if plan_min else None

        regel = (f"{naam} om {a['start'][11:16]}: vertrek {vertrek:%H:%M} van {waarvan}, nu {nodig} min rijden ({hoe})"
                 + (f", gepland {int(plan_min)} min" if plan_min else "")
                 + (f", je komt {int(te_laat)} min te laat" if te_laat > 0 else ", je haalt het"))
        print(ag.maskeer("  " + regel))

        moet_bellen = te_laat > 0 or (verschil is not None and verschil > W.BUFFER_MIN)
        if not moet_bellen:
            continue
        wat = "je afspraak" if prive else a["titel"][:60]
        tekst = (f"Mehdi, de rit naar {W.plaatsnaam(adres) or 'je afspraak'} duurt nu {nodig} minuten. "
                 + (f"Je komt ongeveer {int(te_laat)} minuten te laat voor {wat}. "
                    if te_laat > 0 else
                    f"Dat is {int(verschil)} minuten meer dan gepland voor {wat}. ")
                 + "Vertrek nu, of verwittig de klant.")
        gemeld.append(regel)
        if proef:
            print(ag.maskeer("     (" + ("droog" if DROOG else "niet gepland") + ") zou bellen: " + tekst[:90]))
            continue
        uit = bellen.bel_afspraak(tekst, W.AGENDA_SLOT)
        # alleen een oproep die echt vertrok telt; anders belt de volgende ronde opnieuw (Codex A13, 15-10-2026)
        if bellen.gelukt(uit):
            st[sleutel]["oproepen"] = vorig.get("oproepen", 0) + 1
            gebeld.append(regel)
            print("     gebeld:", uit)
        else:
            st[sleutel].pop("laatst", None)      # niet twintig minuten wachten: de volgende ronde (tien minuten) opnieuw
            print("     oproep mislukt, volgende ronde opnieuw:", str(uit)[:160], file=sys.stderr)

    # een proefronde laat geen spoor in de stand, anders sloeg de echte ronde de afspraak twintig minuten over (A27)
    if not proef:
        bewaar(st)
    dag = f"dag {datetime.now().strftime('%Y-%m-%d')}"
    if gebeld:
        ag.log(dag, "bevinding", "file eet de buffer op, Mehdi gebeld", "\n".join(gebeld))
    elif gemeld:
        ag.log(dag, "bevinding", "file eet de buffer op, " + ("proefronde, niemand opgeroepen" if proef
                                                             else "de oproep lukte niet"), "\n".join(gemeld))
    else:
        print("  geen enkele rit loopt uit")
    return 0


if __name__ == "__main__":
    # cron start dit om de 10 minuten, de klok rond; de filewacht werkt van 06:00 tot 21:59
    # Brusselse tijd. Gezien 24-09-2026: op UTC sliep hij tijdens de ochtendspits (06:00-08:00).
    if "--ronde" in sys.argv and not W.binnen_uren(6, 21):
        sys.exit(0)
    print(f"{W.nu_lokaal():%d-%m %H:%M} filewacht", flush=True)
    sys.exit(main())

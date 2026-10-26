"""De dagvaststelling van De Dagbundelaar: een vast overzicht van een Brusselse dag (ontwerp docs/ontwerp-dagvaststelling.md
v1.5, opdracht van Mehdi 26-10-2026). Wat gepland stond en wat er echt gebeurde, wat er gebeurde zonder gepland te zijn,
en de communicatie langs mail, Zoom, WhatsApp en telefoon.

Pure functies: de runner (dagbundelaar.py) haalt de bronnen op en geeft ze als gewone lijsten door. Geen netwerk, geen
bord, geen schijf; zo dekken de tests (tests/test_dagvaststelling.py) elke regel.

Bewijs per afspraak (D6, E3): 'bevestigd' alleen met een gesprek op dat uur waarin een persoon van de afspraak zit (de
klant of een gast van buiten, nooit Mehdi, een firma of de eigenaar van de agenda); 'aanwijzing' bij de auto ter plaatse
(die bewijst geen gesprek) of bij alleen overlap in tijd voor een afspraak die niet ter plaatse is; anders 'geen spoor',
met de vraag of het doorging. Nooit 'niet doorgegaan' als feit. Een gesprek hoort alleen bij een afspraak via die
persoon; al de rest staat onder niet gepland, ook als het op hetzelfde uur viel.
Dubbels (D7, E1): alleen leidende rijen van de gesprekkentabel (geen dubbel_van), alleen gespreksbronnen; chats en mail
tellen nooit als gesprek, en een Plaud-opname die grotendeels samenvalt met een Zoom- of Fathom-gesprek telt niet apart.
Privé (D5, RZ2-01, RZ3-01): een rij is privé als de bron ze zo markeert, en alles van WhatsApp en telefoon is privé.
Van privé staat er alleen 'privé' met aantal en minuten; de namen staan in de gesprekkentabel (alleen beheer). Mehdi weet
niet wie 'Data uit Mehdi' ziet (26-10-2026), dus ook het bestand in Dropbox draagt geen privénamen.
Een bron die onbekend of onvolledig is, staat er zo; nooit als nul.
"""
import hashlib
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BRUSSEL = ZoneInfo("Europe/Brussels")
MARGE = timedelta(minutes=15)          # een gesprek dat zo dicht bij een afspraak ligt, hoort er mogelijk bij
MIN_GESPREK = 2                        # kortere oproepen of sessies zijn geen ongepland gesprek
MAX_NAAR = 5                           # zoveel ontvangers per postvak staan er bij naam; de rest als aantal
PLAUD_SAMEN = 0.5                      # zoveel van een Plaud-opname valt in een Zoom- of Fathom-gesprek: een dubbel
# Woorden die in titels en namen staan maar geen persoon aanwijzen: Mehdi zelf, firma's, soorten afspraken.
STOP = {"mehdi", "chegini", "zoom", "meeting", "impromptu", "fathom", "overleg", "intern", "interne", "bespreking",
        "plaatsbezoek", "bezoek", "klant", "buiten", "online", "prospect", "architects", "architecture", "invest",
        "unabo", "harmoniebouw", "melodie", "reistijd", "rijden", "afspraak", "call", "gesprek", "team", "automation",
        "privé", "prive", "groep", "oproep", "vooroverleg", "werf", "werfbezoek", "stad", "huis", "thuis", "info",
        "noreply", "admin", "kantoor", "office", "mail", "gmail", "hotmail", "outlook"}
GESPREKSBRONNEN = ("zoom", "fathom", "plaud", "whatsapp", "telefoon")
CHAT_VOORVOEGSELS = ("zoom:chat:", "whatsapp:")
OPROEP_VOORVOEGSELS = ("whatsapp-oproep:", "telefoon:")
SECTIES = ("Gepland", "Niet gepland", "Communicatie")


# ------------------------------------------------------------------------------------------------- dagen ---
def gisteren(nu):
    """De Brusselse kalenderdag voor die van nu. De VM loopt in UTC: om 23:30 UTC is het in Brussel al de volgende dag."""
    if nu.tzinfo is None:
        raise ValueError("nu zonder tijdzone")
    return (nu.astimezone(BRUSSEL).date() - timedelta(days=1)).isoformat()


def venster(nu, dagen):
    """De dagen die een ronde vaststelt: gisteren en de dagen ervoor, nieuwste eerst (D10, E5). Geen watermerk op
    tijdstempels: elke dag van het venster wordt opnieuw berekend en alleen een andere inhoud geeft een nieuwe versie."""
    g = datetime.fromisoformat(gisteren(nu)).date()
    return [(g - timedelta(days=i)).isoformat() for i in range(max(int(dagen), 1))]


# ------------------------------------------------------------------------------------------------ tijden ---
def _tijd(iso):
    t = datetime.fromisoformat(str(iso))
    return t if t.tzinfo else t.replace(tzinfo=BRUSSEL)


def brusselse_dag(iso):
    return _tijd(iso).astimezone(BRUSSEL).date().isoformat()


def afspraak_venster(a):
    return _tijd(a["start"]), _tijd(a.get("einde") or a["start"])


def gesprek_venster(g):
    """Begin en einde van een rij uit de gesprekkentabel: datum en start (HH:MM) in Brussel, minuten (minstens een)."""
    uur, minuut = (int(x) for x in str(g.get("start") or "00:00")[:5].split(":"))
    begin = datetime.fromisoformat(str(g["datum"])[:10]).replace(hour=uur, minute=minuut, tzinfo=BRUSSEL)
    return begin, begin + timedelta(minutes=max(int(g.get("minuten") or 0), 1))


def overlapt(a, b, marge=MARGE):
    (s1, e1), (s2, e2) = a, b
    return s1 - marge < e2 and s2 < e1 + marge


def _samen(a, b):
    """Welk deel van a in b valt (0 tot 1)."""
    (s1, e1), (s2, e2) = a, b
    deel = (min(e1, e2) - max(s1, s2)).total_seconds()
    return max(deel, 0) / max((e1 - s1).total_seconds(), 60)


# ----------------------------------------------------------------------------------------------- soorten ---
def is_leidend(g):
    """Telregel Z10: een rij met dubbel_van telt niet (een gesprek in Zoom en Fathom is een gesprek)."""
    return not str(g.get("dubbel_van") or "").strip()


def soort(g):
    """'mail', 'chat', 'oproep', 'gesprek' of 'anders' voor een rij uit de gesprekkentabel (E1: alleen gespreksbronnen)."""
    u, bron = str(g.get("uniek") or ""), str(g.get("bron") or "")
    if bron == "mail" or u.startswith("mail:"):
        return "mail"
    if bron not in GESPREKSBRONNEN:
        return "anders"
    if u.startswith(OPROEP_VOORVOEGSELS):
        return "oproep"
    if u.startswith(CHAT_VOORVOEGSELS):
        return "chat"
    return "gesprek"


def is_prive(g):
    """RZ3-01 en D5: de privévlag of afdeling privé; alles van WhatsApp en telefoon is privé."""
    return bool(g.get("prive") or str(g.get("afdeling") or "").strip().casefold() in ("prive", "privé")
                or str(g.get("bron") or "") in ("whatsapp", "telefoon"))


PARTIKELS = {"de", "den", "der", "van", "von", "la", "le", "du", "del", "da", "di", "ten", "ter", "het", "en"}
MIN_GEDEELD = 2                        # zoveel naamdelen deelt een persoon van de afspraak met een gesprekspersoon (F3)


def naamdelen(tekst):
    """De naamdelen van een naam (minstens drie letters), zonder Mehdi, firma's, soortwoorden en partikels. Een
    e-mailadres geeft zijn lokale deel ('jan.peeters@x.be' wordt 'jan peeters')."""
    tekst = re.sub(r"([\w.+-]+)@[\w.-]+", lambda m: m.group(1).replace(".", " ").replace("_", " "), str(tekst or ""))
    return {w for w in (x.casefold() for x in re.findall(r"[^\W\d_]{3,}", tekst)) if w not in STOP and w not in PARTIKELS}


def namen(tekst):
    """De afzonderlijke namen in een tekst, elk als verzameling naamdelen: de stukken tussen komma's, streepjes en haakjes.
    Wat tussen haakjes staat (een afdeling, '(H-AI & ICT)') telt niet."""
    zonder = re.sub(r"\([^)]*\)|\[[^\]]*\]", ",", str(tekst or ""))
    stukken = re.split(r"[,;/+&]|\s[-\u2013]\s|:|\s(?:en|and|met|und|et)\s", zonder, flags=re.I)
    return [d for d in (naamdelen(x) for x in stukken) if d]


def personen_van_afspraak(a):
    """E3 en F3: de namen die de afspraak aanwijst: het stuk na de code tussen haken en de gasten van buiten, nooit wat
    voor de code staat ('Mehdi: Catalin: [HA-KB] ...' is de eigenaar van de agenda). Een lijst van namen."""
    titel = str(a.get("titel") or "")
    rest = titel.split("]", 1)[1] if "]" in titel else titel.split(":")[-1]
    uit = namen(rest)
    for d in a.get("deelnemers") or []:
        uit += namen(d)
    return uit


def zelfde_persoon(afspraak_namen, personen):
    """F3: alleen aantoonbaar dezelfde persoon: een naam van de afspraak en een gesprekspersoon delen minstens
    MIN_GEDEELD naamdelen (voornaam en familienaam). Een gedeelde voornaam of een plaatsnaam alleen volstaat niet."""
    return any(len(a & g) >= MIN_GEDEELD for a in afspraak_namen for g in namen(personen))


def bron_label(g):
    u, bron = str(g.get("uniek") or ""), str(g.get("bron") or "")
    if u.startswith("whatsapp-oproep:"):
        return "WhatsApp-oproep"
    if u.startswith("telefoon:"):
        return "telefoon"
    return {"zoom": "Zoom", "fathom": "Fathom", "plaud": "Plaud"}.get(bron, bron or "gesprek")


def gesprek_tekst(g):
    begin, _ = gesprek_venster(g)
    wie = "privé" if is_prive(g) else (g.get("personen") or "onbekend")
    return f"{begin:%H:%M} {bron_label(g)}, {int(g.get('minuten') or 0)} min, {wie}"


def gesprekken_van_dag(dag, rijen):
    """De leidende gesprekken en oproepen van de dag, zonder Plaud-dubbels van een Zoom- of Fathom-gesprek. Een Zoom-rij
    met zo'n Plaud-dubbel krijgt 'opname': 'plaud' (F6): het gesprek telt een keer, en wel als gesprek met opname."""
    praat = [dict(g) for g in rijen if str(g.get("datum") or "")[:10] == dag and is_leidend(g)
             and soort(g) in ("gesprek", "oproep")]
    vast = [g for g in praat if g.get("bron") in ("zoom", "fathom")]
    uit = []
    for g in praat:
        if g.get("bron") == "plaud":
            z = next((z for z in vast if _samen(gesprek_venster(g), gesprek_venster(z)) >= PLAUD_SAMEN), None)
            if z is not None:
                z["opname"] = "plaud"
                continue
        uit.append(g)
    return uit


# ------------------------------------------------------------------------------------------------- bewijs ---
def bewijs(a, gesprekken, locatie=None):
    """Het bewijs voor een afspraak. gesprekken: van gesprekken_van_dag. locatie: de uitkomst van
    locatie_wacht.vergelijk_agenda voor deze afspraak ({'uitkomst': 'doorgegaan'|'niet_gezien'|'zonder_adres'|'onbekend',
    'tekst': ...}), of None als het geen afspraak ter plaatse is (online, intern).
    Geeft {'uitkomst', 'grond', 'gesprekken': [uniek]}; alleen die gesprekken horen bij de afspraak (E3)."""
    venster_a = afspraak_venster(a)
    wie = personen_van_afspraak(a)
    op_uur = [g for g in gesprekken if overlapt(venster_a, gesprek_venster(g))]
    met_persoon = [g for g in op_uur if zelfde_persoon(wie, g.get("personen"))]
    if met_persoon:
        return {"uitkomst": "bevestigd", "grond": "; ".join(gesprek_tekst(g) for g in met_persoon),
                "gesprekken": [g["uniek"] for g in met_persoon]}
    ter_plaatse = locatie is not None
    locatie = locatie or {}
    if locatie.get("uitkomst") == "doorgegaan":
        return {"uitkomst": "aanwijzing", "grond": f"{locatie.get('tekst') or 'auto ter plaatse'}; geen gesprek als bewijs",
                "gesprekken": []}
    if op_uur and not ter_plaatse:
        return {"uitkomst": "aanwijzing", "grond": "op dat uur een gesprek zonder persoon van de afspraak: "
                + "; ".join(gesprek_tekst(g) for g in op_uur), "gesprekken": []}
    grond = {"niet_gezien": "auto niet gezien op de plek",
             "zonder_adres": "geen bruikbaar adres om de locatie te toetsen",
             "onbekend": locatie.get("tekst") or "locatie niet gelezen"}.get(locatie.get("uitkomst"),
                                                                        "geen gesprek, oproep of locatie")
    return {"uitkomst": "geen spoor", "grond": grond + ". Ging dit door?", "gesprekken": []}


# ------------------------------------------------------------------------------------------- vaststelling ---
def vaststellen(dag, afspraken, ongelezen, gesprekken, locatie_per_id, bezoeken, zoomstand, mail, kanalen,
                prive_afspraak, locatiestand=""):
    """De vaststelling van een dag als gewone gegevens.

    afspraken: de afspraken van die dag, met de archiefagenda's (zonder fout, hele dag of rit); ongelezen: de agenda's die
    niet gelezen konden worden (ook 'archief'), of None als de agenda helemaal niet gelezen werd.
    gesprekken: rijen uit de gesprekkentabel voor die datum (alle; hier worden de leidende gekozen).
    locatie_per_id: {afspraak-id: uitkomst} voor elke afspraak ter plaatse ({'uitkomst': 'onbekend'} als de locatie niet
    gelezen werd). bezoeken: projectbezoeken en verblijven zonder afspraak ({'van', 'tot', 'minuten', 'waar', 'soort'}
    met soort project, twijfel of elders), of None (locatie niet gelezen); locatiestand: de stand van het dagboek
    (afgesloten, voorlopig, ...).
    zoomstand: 'volledig', 'ondergrens' of 'onbekend'. mail: van mail_telling, of None. kanalen: {'whatsapp': stand,
    'telefoon': stand} voor deze dag, met stand 'aangesloten', 'niet aangesloten' of een andere tekst ('stil sinds ...',
    'onbekend voor deze dag'): D2 en F5, de hartslag van de wacht en haar dekking van die dag, niet het bestaan van rijen.
    prive_afspraak: functie afspraak -> bool (agenda_wacht.is_prive)."""
    praat = gesprekken_van_dag(dag, gesprekken)
    agenda_stand = "onbekend" if ongelezen is None else ("onvolledig" if ongelezen else "volledig")
    gepland, gebruikt = [], set()
    for a in sorted(afspraken, key=lambda x: x.get("start") or ""):
        loc = (locatie_per_id or {}).get(a.get("id"))
        b = bewijs(a, praat, loc)
        gebruikt.update(b["gesprekken"])
        gepland.append({"id": a.get("id"), "tijd": str(a.get("start") or "")[11:16], "titel": a.get("titel") or "",
                        "prive": bool(prive_afspraak(a)), "uitkomst": b["uitkomst"], "grond": b["grond"]})
    ongepland = [g for g in sorted(praat, key=lambda g: gesprek_venster(g)[0])
                 if g["uniek"] not in gebruikt and int(g.get("minuten") or 0) >= MIN_GESPREK]
    leidend = [g for g in gesprekken if str(g.get("datum") or "")[:10] == dag and is_leidend(g)]
    # Een Zoom-gesprek met een Fathom-opname staat in de tabel als leidende Fathom-rij (de Zoom-rij is dubbel_van):
    # daarom een totaal over Zoom, Fathom en Plaud, elk gesprek een keer, en geen aparte telling per bron als 'Zoom'.
    vergaderd = [g for g in praat if g.get("bron") in ("zoom", "fathom", "plaud")]
    met_opname = [g for g in vergaderd if g.get("bron") in ("fathom", "plaud") or g.get("opname")]
    gesprekken = {"aantal": len(vergaderd), "minuten": sum(int(g.get("minuten") or 0) for g in vergaderd),
                  "alleen_zoom": len(vergaderd) - len(met_opname), "met_opname": len(met_opname)}
    kanalen = kanalen or {}
    wa = [g for g in leidend if g.get("bron") == "whatsapp"]
    tel = [g for g in praat if g.get("bron") == "telefoon"]
    return {
        "dag": dag,
        "agenda": {"stand": agenda_stand, "ongelezen": sorted(ongelezen or []), "afspraken": gepland},
        "niet_gepland": {"voorbehoud": agenda_stand != "volledig", "gesprekken": ongepland, "bezoeken": bezoeken,
                         "locatiestand": locatiestand},
        "gesprekken": gesprekken,
        "zoom": {"stand": zoomstand or "onbekend",
                 "chats": len([g for g in leidend if str(g.get("uniek")).startswith("zoom:chat:")])},
        "whatsapp": {"stand": kanalen.get("whatsapp") or "niet aangesloten",
                     "gesprekken": len([g for g in wa if soort(g) == "chat"]),
                     "berichten": sum(_berichten(g) for g in wa if soort(g) == "chat"),
                     "oproepen": len([g for g in wa if soort(g) == "oproep"]),
                     "minuten": sum(int(g.get("minuten") or 0) for g in wa if soort(g) == "oproep")},
        "telefoon": {"stand": kanalen.get("telefoon") or "niet aangesloten", "oproepen": len(tel),
                     "minuten": sum(int(g.get("minuten") or 0) for g in tel)},
        "mail": mail,
    }


def _berichten(g):
    m = re.match(r"\s*(\d+)\s+bericht", str(g.get("thema") or ""))
    return int(m.group(1)) if m else 0


# --------------------------------------------------------------------------------------------------- mail ---
def mail_telling(dag, ontvangen, verzonden, soorten=None):
    """ontvangen en verzonden: {postvak: {'berichten': [koppen], 'onvolledig': [reden]}}, met koppen zoals de postbus ze
    geeft (datum, message_id, aan). De runner leest zelf de mappen, dus de leesdekking van deze ronde is gekend (E4).
    soorten: {message_id: soort} uit mailbericht, alleen om de soort te tonen. Geeft per postvak het aantal voor precies
    die Brusselse dag (binnen een postvak ontdubbeld), en een totaal ontdubbeld per Message-ID over alle postvakken (D8):
    een mail aan twee adressen van Mehdi telt in elk postvak, maar een keer in het totaal. Een postvak met een reden is
    onvolledig, en dan ook het totaal."""
    per, totaal = {}, {"in": set(), "uit": set()}
    soorten = soorten or {}
    for richting, bron in (("in", ontvangen), ("uit", verzonden)):
        for postvak, v in sorted((bron or {}).items()):
            p = per.setdefault(postvak, {"binnen": 0, "soorten": {}, "verzonden": 0, "naar": [], "onvolledig": []})
            p["onvolledig"] += [r for r in v.get("onvolledig") or [] if r not in p["onvolledig"]]
            hier = set()
            for k in v.get("berichten") or []:
                if not k.get("datum") or brusselse_dag(k["datum"]) != dag:
                    continue
                mid = (k.get("message_id") or "").strip() or hashlib.sha1(
                    f"{k.get('datum')}{k.get('onderwerp')}{k.get('aan')}".encode()).hexdigest()
                if mid in hier:
                    continue
                hier.add(mid)
                totaal[richting].add(mid)
                if richting == "in":
                    p["binnen"] += 1
                    s = soorten.get(mid)
                    if s:
                        p["soorten"][s] = p["soorten"].get(s, 0) + 1
                else:
                    p["verzonden"] += 1
                    p["naar"] += [_naam(x) for x in (k.get("aan") or [])[:3]]
    return {"postvakken": per, "binnen": len(totaal["in"]), "verzonden": len(totaal["uit"]),
            "onvolledig": any(p["onvolledig"] for p in per.values())}


def _naam(adresregel):
    naam = re.sub(r"\s*<[^>]*>\s*", "", str(adresregel)).strip().strip('"')
    return naam or re.sub(r".*<([^>]*)>.*", r"\1", str(adresregel)).strip()


# ----------------------------------------------------------------------------------------------- tekst ---
def tekst(v, prive_postvakken=(), over=None):
    """Het overzicht als markdown, zonder privénamen of privétitels: dezelfde tekst gaat naar het bord, het bestand en
    Dropbox (E6). over: regels voor het blok 'Over deze vaststelling' (versie, tijd, bronnen); dat blok telt niet mee in
    de hash."""
    d = v["dag"]
    r = [f"# Dag {d} vastgesteld", ""]
    ag = v["agenda"]
    kop = "## Gepland"
    if ag["stand"] == "onbekend":
        kop += " (agenda niet gelezen: onbekend)"
    elif ag["stand"] == "onvolledig":
        kop += " (agenda onvolledig, niet gelezen: " + ", ".join(ag["ongelezen"]) + ")"
    r += [kop, ""]
    if not ag["afspraken"]:
        r.append("- geen afspraken" if ag["stand"] == "volledig" else "- geen afspraken gelezen")
    for x in ag["afspraken"]:
        if x["prive"]:
            r.append(f"- {x['tijd']} (privé): {x['uitkomst']}" + (". Ging dit door?" if x["uitkomst"] == "geen spoor" else ""))
        else:
            r.append(f"- {x['tijd']} {x['titel']}: {x['uitkomst']} ({x['grond']})")
    ng = v["niet_gepland"]
    r += ["", "## Niet gepland" + (" (onder voorbehoud: agenda niet volledig gelezen)" if ng["voorbehoud"] else ""), ""]
    for g in ng["gesprekken"]:
        r.append(f"- {gesprek_tekst(g)}")
    if ng["bezoeken"] is None:
        r.append("- locatie: niet gelezen")
    else:
        if ng.get("locatiestand") and ng["locatiestand"] != "afgesloten":
            r.append(f"- locatie {ng['locatiestand']}: bezoeken kunnen nog veranderen")
        for b in ng["bezoeken"]:
            r.append(f"- {b.get('van')} tot {b.get('tot')} ({b.get('minuten')} min) {_plek(b)}")
    if not ng["gesprekken"] and ng["bezoeken"] == []:
        r.append("- niets gevonden")
    r += ["", "## Communicatie", ""]
    z, g = v["zoom"], v["gesprekken"]
    # F5: een Zoom-stand die niet volledig is, maakt elk getal van Zoom een ondergrens; zonder stand is de chat onbekend
    minstens = "" if z["stand"] == "volledig" else "minstens "
    stand = {"volledig": "", "ondergrens": "", "onbekend": " (Zoom-stand onbekend)"}.get(z["stand"], f" ({z['stand']})")
    if minstens:
        # G5: zonder volledige Zoom-stand is elk getal een ondergrens, en de verdeling is niet te kennen
        r.append(f"- gesprekken in Zoom, Fathom en Plaud: minstens {g['aantal']}, minstens {g['minuten']} min "
                 f"(verdeling onbekend){stand}")
    else:
        r.append(f"- gesprekken in Zoom, Fathom en Plaud: {g['aantal']}, {g['minuten']} min ({g['met_opname']} met "
                 f"opname, {g['alleen_zoom']} alleen in Zoom)")
    if z["stand"] == "onbekend" and not z["chats"]:
        r.append("- Zoom-chat: onbekend (Zoom-stand onbekend)")
    else:
        r.append(f"- Zoom-chat: {minstens}{z['chats']} chatgesprek(ken){stand}")
    w = v["whatsapp"]
    if w["stand"] == "niet aangesloten":
        r.append("- WhatsApp: nog niet aangesloten")
    elif w["stand"] != "aangesloten" and not (w["gesprekken"] or w["oproepen"]):
        r.append(f"- WhatsApp: onbekend ({w['stand']})")
    else:
        pre, extra = ("", "") if w["stand"] == "aangesloten" else ("minstens ", f" ({w['stand']})")
        r.append(f"- WhatsApp: {pre}{w['berichten']} berichten in {w['gesprekken']} gesprekken, {w['oproepen']} oproepen, "
                 f"{w['minuten']} min{extra}")
    t = v["telefoon"]
    if t["stand"] == "niet aangesloten":
        r.append("- telefoon: nog niet aangesloten")
    elif t["stand"] != "aangesloten" and not t["oproepen"]:
        r.append(f"- telefoon: onbekend ({t['stand']})")
    else:
        pre, extra = ("", "") if t["stand"] == "aangesloten" else ("minstens ", f" ({t['stand']})")
        r.append(f"- telefoon: {pre}{t['oproepen']} oproepen, {t['minuten']} min{extra}")
    if v["mail"] is None:
        r.append("- mail: niet gelezen")
    else:
        m = v["mail"]
        r.append(f"- mail: {m['binnen']} binnen, {m['verzonden']} verzonden (uniek over alle postvakken"
                 + ("; onvolledig)" if m["onvolledig"] else ")"))
        for postvak, p in sorted(m["postvakken"].items()):
            soorten = ", ".join(f"{n} {s}" for s, n in sorted(p["soorten"].items()))
            regel = f"  - {postvak}: {p['binnen']} binnen" + (f" ({soorten})" if soorten else "") + f", {p['verzonden']} verzonden"
            if p["onvolledig"]:
                regel += " (onvolledig: " + "; ".join(p["onvolledig"]) + ")"
            if p["naar"] and postvak not in prive_postvakken:
                naar = list(dict.fromkeys(p["naar"]))
                regel += "; naar " + ", ".join(naar[:MAX_NAAR]) + (f" en {len(naar) - MAX_NAAR} meer" if len(naar) > MAX_NAAR else "")
            r.append(regel)
    r += ["", "## Over deze vaststelling", ""]
    r += [f"- {x}" for x in over or []]
    return "\n".join(r).rstrip() + "\n"


def _plek(b):
    """F2: alleen een bevestigd of waarschijnlijk werkproject bij naam; een twijfelgeval of een andere plek niet (die kan
    privé zijn). De plek zelf staat in het locatielogboek."""
    if b.get("soort") == "project":
        return str(b.get("waar") or "projectbezoek")
    if b.get("soort") == "twijfel":
        return "projectbezoek, project onzeker (kies op het locatiedashboard)"
    return "verblijf zonder afspraak (plek in het locatielogboek)"


def versie_van(t):
    """Het versienummer uit het blok 'Over deze vaststelling' van een bestand, of None (F8: de versie volgt het bestand)."""
    t = t or ""
    if "\n## Over deze vaststelling" not in t:
        return None
    m = re.search(r"^- versie (\d+),", t.split("\n## Over deze vaststelling", 1)[1], re.M)
    return int(m.group(1)) if m else None


def kern(t):
    """De vaste inhoud: alles voor het blok 'Over deze vaststelling'."""
    return t.split("\n## Over deze vaststelling")[0]


def inhoud_hash(t):
    """De hash van de vaste inhoud (E6): gelijk bij bord, bestand en Dropbox-kopie van dezelfde versie."""
    return hashlib.sha256(kern(t).encode()).hexdigest()[:16]


def wijzigingen(oud, nieuw):
    """Welke secties van de vaste inhoud veranderden tegenover de vorige versie."""
    def secties(t):
        uit, naam = {}, ""
        for regel in kern(t or "").split("\n"):
            if regel.startswith("## "):
                # 'Niet gepland' eerst: anders valt het onder 'Gepland' niet, maar wel een kop als 'Gepland (agenda ...)'
                naam = next((s for s in ("Niet gepland", "Gepland", "Communicatie") if regel[3:].startswith(s)), regel[3:])
            uit[naam] = uit.get(naam, "") + regel + "\n"
        return uit
    a, b = secties(oud), secties(nieuw)
    return [s for s in SECTIES if a.get(s) != b.get(s)]

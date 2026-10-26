#!/usr/bin/env python3
"""De Dagbundelaar (Privé): legt per dag samen wat de bronnen-agents klaarzetten,
zegt per bundel bij welk dossier het hoort, en geeft het door. Sinds 26-10-2026 legt hij ook elke nacht de dag vast
(de dagvaststelling, ontwerp docs/ontwerp-dagvaststelling.md v1.5): wat gepland stond en of het doorging, wat er gebeurde
zonder gepland te zijn, en de communicatie. Nacht: --nacht om 23:30 UTC (planning/dagvaststelling.cron), alleen de
vaststelling over veertien dagen. Ochtend: hieronder, de bundels en daarna de vaststelling van gisteren. Beide gaan door
de gedeelde ronde (N12); de nachttaak geeft het ochtendbericht nooit vrij (koppelingen/ochtend.py, NACHTTAAK).

Elke werkdag (maandag tot vrijdag in Brussel), voor gisteren, als laatste stap van de ochtendketen: keten.py start me
om 07:00 UTC binnen /tmp/gesprekken.lock (planning/gesprekken.cron), na De Fathomwacht en De Zoomwacht, ook als een van
die faalde, met een time-out van 900 s; mijn uitvoer gaat naar dagbundelaar.log en mijn exit staat in keten.json
(RZ4-04). Tot 22-10-2026 had ik een eigen cronregel, vijf minuten na de keten, die op hetzelfde slot wachtte; een
handmatige ronde van een gesprekkenwacht kon me zo vóór de keten laten lopen, of me laten afhaken. Op verzoek
(--dag JJJJ-MM-DD), ook via De Regisseur, onder hetzelfde slot:
  1. alles wat klaargezet is met gisteren als dag: afspraken, transcripten, opnames,
     later ook locatie en foto's;
  2. per dossier (deal) één bundel: wat er gebeurde, welke bronnen erbij horen,
     wat ontbreekt (afspraak zonder opname, opname zonder dossier);
  3. de bundels klaarzetten voor de afdeling (h-architects) en het dagverslag voor Mehdi;
  4. wat om een keuze vraagt (bij welk dossier hoort dit?) gaat als vraag naar het bord.
Leest het bord; schrijft alleen op het bord. Verplaatst niets vóór Mehdi's ja.

De Zoom-dagregel en het lek naar de afdeling (ontwerp regie-zoom v1.2, Z14 en J14):
  - de dagregel van De Zoomwacht (soort zoom) komt niet in een bundel, maar als regel
    "Zoom: <titel>" in het Dagverslag; ontbreekt ze, dan zegt het Dagverslag dat;
  - een dagregel van de zes dagen ervoor die (weer) op klaar staat, nagekomen of herzien,
    komt onder "Nagekomen of herzien" en wordt daarna opgepakt: zo komen ook vrijdag en
    zaterdag op maandag mee;
  - zoom-tekst (voor De Regisseur) en het ochtendbericht bundel ik nooit;
  - een sleutel is alleen een dossier als hij niet leeg is en geen datum (JJJJ-MM-DD);
    een item voor mehdi gaat in een bundel voor mehdi (uniek bundel:<dag>:<sleutel>:mehdi),
    zodat een bundel voor h-architects nooit een item voor Mehdi of zonder dossier bevat.
Van een privé-item (inhoud.prive, PRIVÉ in de titel, of inhoud.afdeling prive: RZ3-01) zet ik alleen
"privégesprek, N min" in de bundel, het Dagverslag en mijn werkverslag (RZ2-01), zonder verwijzing, en nooit in een
bundel voor een afdeling.
"""
import json
import os
import sys
import hashlib
import shutil
import subprocess
import tempfile
import urllib.parse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import dagvaststelling as V  # noqa: E402  de dagvaststelling, pure functies (ontwerp dagvaststelling v1.7)
import locatiecontext as LC  # noqa: E402  dagboek voor precies de dag, met startgrens (opdracht v1.4)

NAAM = "dagbundelaar"
ag = bord.Agent(NAAM)
DAG = None
VENSTER = None
NACHT = "--nacht" in sys.argv          # alleen de dagvaststelling, geen bundels (keten.py --nacht, planning/gesprekken.cron)
for i, a in enumerate(sys.argv):
    if a == "--dag" and i + 1 < len(sys.argv):
        DAG = sys.argv[i + 1]
    if a == "--venster" and i + 1 < len(sys.argv):
        VENSTER = int(sys.argv[i + 1])
DAG_GEGEVEN = DAG is not None
# Gisteren is de Brusselse dag: de VM loopt in UTC, en om 23:30 UTC is het in Brussel al de volgende dag.
DAG = DAG or V.gisteren(datetime.now(timezone.utc))
DATA = os.path.expanduser("~/appportal/mijnagents-data")
DAGBOEK = os.path.join(DATA, "dagboek")                       # gaat naar Dropbox: Data uit Mehdi/Dagboek
STAAT = os.path.join(DATA, "dagvaststelling-staat.json")      # per dag versie en hash; niet in de map dagboek
ONTVANGST = os.path.join(DATA, "dagboek-ontvangst.txt")       # sha256 van de kopie in Dropbox, van de Mac-sync
NACHTVENSTER = 14                                             # zoveel dagen herberekent de nachtronde (D10, E5)
# Codex P7 (fase 2): een Mac die langer dan het venster sliep, leest bij het ontwaken tot zestig dagen terug. Een dag
# buiten het venster met een nieuwere dekkingsrij dan zijn laatste vaststelling haalt de nacht in, hoogstens zeven.
INHAAL = 60
INHAAL_PER_NACHT = 7
INHAALSTAAT = os.path.join(DATA, "dagvaststelling-inhaal.json")  # per ingehaalde dag het tijdstip
KANAAL_UREN = 26                                              # een wacht die langer zweeg, levert niet meer
KANAALWACHTEN = {"whatsapp": "whatsapp-wacht", "telefoon": "belwacht"}
ZOOM_ONZEKER = "_zoom_onzeker"                                # sleutel van v1.6 in de staat; wordt opgeruimd
ZOOM_TERUGBLIK = 6                                            # zoom_wacht.TERUGBLIK: zolang kan een dagregel nog herzien worden


def bundelen():
    """De bundels per dossier en het Dagverslag van DAG (de ochtendronde, werkwijze stap 1 tot 8). Geeft detail, noden en
    het aantal bronnen; de hartslag doet de ronde in main."""
    # bundelen staat op zichzelf, zonder hulpfuncties op moduleniveau: tests/test_locatielezers.py voert alleen deze
    # functie uit, met een nagebootst bord.
    from datetime import date, timedelta

    def is_datum(s):
        try:
            return len(s) == 10 and bool(date.fromisoformat(s))
        except ValueError:
            return False

    def prive(it):
        # RZ3-01: ook afdeling prive is privé, zoals de dossierbeslissing (plaud/dossier.py) het zegt, ook bij
        # prive=false; zo'n item van voor 22-10-2026 droeg naam en onderwerp in titel en verwijzing, zonder PRIVÉ
        d = it.get("_d") or {}
        return (bool(d.get("prive")) or "PRIVÉ" in (it.get("titel") or "")
                or str(d.get("afdeling") or "").strip().lower() in ("prive", "privé"))

    def naam_van(it):
        """RZ2-01: van een privé-item alleen 'privégesprek, N min', in de bundel, het Dagverslag en het werkverslag; met
        wie en waarover staan in het archief op de VM. Ook voor een item van voor 21-10-2026, dat de persoon en het
        onderwerp nog in de titel en de verwijzing droeg. Zonder minuten: duur onbekend, nooit 0."""
        if not prive(it):
            return it["titel"]
        n = (it.get("_d") or {}).get("minuten")
        return "privégesprek, " + (f"{n} min" if isinstance(n, int) and not isinstance(n, bool) else "duur onbekend")

    items = bord.call(f"/api/klaarzet?status=alle&n=500").get("items", [])
    # Z14: de Zoom-dagregels per soort lezen; n=500 over de hele bak dekt minder dan een week
    zoomlezing = bord.call("/api/klaarzet?status=klaar&soort=zoom&n=50").get("items", [])
    van_dag, zoom_dag, nagekomen, gezien = [], [], [], set()
    eerste = (date.fromisoformat(DAG) - timedelta(days=6)).isoformat()
    for it in items + [z for z in zoomlezing if z.get("soort") == "zoom"]:
        if it.get("id") is not None:
            if it["id"] in gezien:
                continue
            gezien.add(it["id"])
        inhoud = it.get("inhoud") or ""
        try:
            d = json.loads(inhoud) if inhoud.startswith("{") else {}
        except ValueError:
            d = {}
        dag = (d.get("datum") or d.get("start") or it.get("sleutel") or "")[:10]
        if it.get("soort") in ("dagplan", "dagbundel", "signaal", "oproep", "zoom-tekst", "ochtendbericht", "dagvaststelling",
                               "communicatie"):
            continue  # zoom-tekst is voor De Regisseur, het ochtendbericht voor De Bode (I2, Z14); de dagvaststelling is van
            # mij en blijft klaar voor Mehdi: nooit bundelen, nooit oppakken (Codex D2); de communicatie van De
            # Communicatiebundelaar is voor De Levenscoach: geen dossier, en nooit oppakken (CB02, CB04)
        if str(it.get("uniek") or "").startswith("cc:"):
            continue  # het Commandocentrum en de wachten sluiten hun eigen items (taken en impulsen)
        if "mail-regisseur" in (it.get("van"), it.get("voor")):
            continue  # mail volgt De Mailregisseur op; tot 19-10-2026 haalde ik hier elke nacht opvolgpunten weg (37 stuks)
        if it.get("soort") == "locatie" or it.get("van") == "locatie-wacht":
            continue  # het bewegingslogboek is alleen voor Mehdi; nooit in een bundel voor een afdeling
        if it.get("soort") == "zoom":
            # De dagregel van De Zoomwacht: een regel in het Dagverslag, nooit een bundel. Nagekomen of herzien
            # (weer op klaar) en van de zes dagen ervoor: ook mee, zo komen vrijdag en zaterdag op maandag mee.
            if dag == DAG:
                zoom_dag.append(it)
            elif eerste <= dag < DAG and it.get("status") == "klaar":
                nagekomen.append(it)
            continue
        if dag == DAG or (it.get("soort") == "transcript" and (d.get("start") or "")[:10] == DAG):
            it["_d"] = d
            van_dag.append(it)
    # Een sleutel is alleen een dossier als hij niet leeg is en geen datum: tot 21-10-2026 kwamen zo 31 bundels voor
    # h-architects met een datum als dossier (gezondheid, coaching, mail en de Zoom-dagregel). Een item voor mehdi
    # gaat in een bundel voor mehdi met dezelfde sleutel; alleen een bundel met een dossier en zonder item voor
    # mehdi gaat naar h-architects.
    per_deal = defaultdict(list)
    for it in van_dag:
        sleutel = (it.get("sleutel") or "").strip()
        dossier = sleutel if sleutel and not is_datum(sleutel) else "(zonder dossier)"
        # RZ3-01: een privé-item gaat nooit in een bundel voor een afdeling, ook niet als het voor een afdeling klaarstond
        per_deal[(dossier, dossier != "(zonder dossier)" and (it.get("voor") == "mehdi" or prive(it)))].append(it)
    bundels, vragen = [], []
    for (sleutel, voor_mehdi), lijst in per_deal.items():
        soorten = defaultdict(int)
        for it in lijst:
            soorten[it["soort"]] += 1
        afspraken = [it for it in lijst if it["soort"] == "afspraak"]
        transcripten = [it for it in lijst if it["soort"] == "transcript"]
        ontbreekt = []
        if afspraken and not transcripten:
            ontbreekt.append("afspraak zonder opname of transcript")
        if sleutel == "(zonder dossier)":
            ontbreekt.append("bronnen zonder dossier: Mehdi wijst ze toe")
            vragen += [naam_van(it) for it in lijst]
        regels = [f"- {it['soort']}: {naam_van(it)}" + (f" ({it['verwijzing']})" if it.get("verwijzing") and not prive(it) else "")
                  for it in lijst]
        tekst = f"Dossier {sleutel} op {DAG}: " + ", ".join(f"{n} {s}" for s, n in soorten.items()) + "\n" + "\n".join(regels) + \
                ("\nOntbreekt: " + "; ".join(ontbreekt) if ontbreekt else "")
        if sleutel == "(zonder dossier)":
            bundels.append({"voor": "mehdi", "soort": "dagbundel", "sleutel": DAG,
                            "titel": f"Bundel {DAG} · {sleutel}", "uniek": f"bundel:{DAG}:{sleutel}", "inhoud": tekst})
        elif voor_mehdi:
            # J14: een eigen uniek, anders overschrijft de bundel voor h-architects met dezelfde sleutel deze
            bundels.append({"voor": "mehdi", "soort": "dagbundel", "sleutel": sleutel,
                            "titel": f"Bundel {DAG} · {sleutel} · voor Mehdi", "uniek": f"bundel:{DAG}:{sleutel}:mehdi", "inhoud": tekst})
        else:
            bundels.append({"voor": "h-architects", "soort": "dagbundel", "sleutel": sleutel,
                            "titel": f"Bundel {DAG} · {sleutel}", "uniek": f"bundel:{DAG}:{sleutel}", "inhoud": tekst})
    zoomregels = [f"Zoom: {it['titel']}" for it in zoom_dag] or ["Zoom: dagregel ontbreekt (Zoomwacht niet klaar)"]
    if nagekomen:
        zoomregels.append("Nagekomen of herzien:")
        zoomregels += [f"- Zoom: {it['titel']}" for it in sorted(nagekomen, key=lambda x: x.get("uniek") or "")]
    verslag = f"Dagverslag {DAG}: {len(van_dag)} bronnen in {len(per_deal)} bundel(s)." + "\n" + "\n".join(zoomregels) + \
              ("\nToe te wijzen: " + "; ".join(vragen) if vragen else "")
    bundels.append({"voor": "mehdi", "soort": "dagbundel", "sleutel": DAG, "titel": f"Dagverslag {DAG}",
                    "uniek": f"dagverslag:{DAG}", "inhoud": verslag + "\n\n" + "\n\n".join(b["inhoud"] for b in bundels)})
    uit = ag.klaarzet(bundels)
    # Wat in een bundel of in het Dagverslag zit, is door de laag verwerkt: opgepakt markeren, zodat de bak
    # niet blijft groeien. Een afdelingsagent leest de bundel (met sleutel) verder.
    opgepakt = 0
    for it in van_dag + zoom_dag + nagekomen:
        if it.get("status") == "klaar":
            try:
                bord.opgepakt(it["id"], NAAM); opgepakt += 1
            except Exception:  # noqa: BLE001
                pass
    ag.log(f"dag {DAG}", "bevinding", f"{len(van_dag)} klaargezette bronnen, {len(per_deal)} bundel(s), {len(vragen)} toe te wijzen; "
           f"Zoom-dagregel {'gevonden' if zoom_dag else 'ontbreekt'}, {len(nagekomen)} nagekomen of herzien", verslag)
    ag.log(f"dag {DAG}", "schrijf", f"bundels klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend; {opgepakt} bronnen als opgepakt gemarkeerd")
    # Werkwijze stap 8: welke bronnen ontbraken, en wat ik nodig heb om ze te krijgen.
    # Een locatiedagboek telt alleen voor precies deze dag en uit de actieve reeks. Tot 05-10-2026
    # telde elk locatie-item, ook een oud telefoondagboek, en verborg zo een ontbrekend dagboek.
    soorten = {it.get("soort") for it in items if (it.get("sleutel") or "")[:10] == DAG and it.get("soort") != "locatie"}
    if LC.dag_heeft_dagboek(DAG, items):
        soorten.add("locatie")
    nood = []
    for soort, tekst, wie in (("gezondheid", "Apple Watch-gegevens (Gezondheidswacht op de Mac: Health Auto Export en iCloud moeten lopen)", "mehdi"),
                              ("foto", "Foto's van de dag (iCloud-wacht op de Mac moet om 21:15 gedraaid hebben)", "mehdi"),
                              ("locatie", "Locatiedagboek (Locatiewacht 21:30; tracker aan?)", "mehdi")):
        if soort not in soorten:
            nood.append({"tekst": f"Voor {DAG} geen {tekst}", "wie": wie})
    # WhatsApp en telefoon meldt de dagvaststelling zelf, op grond van de hartslag van hun wacht (Codex D2)
    nood.append({"tekst": "Plaud-opnames komen pas als de Plaud-routine op claude.ai draait", "wie": "mehdi"})
    return {"detail": f"{len(per_deal)} bundel(s), {len(vragen)} toe te wijzen", "nood": nood, "bronnen": len(van_dag)}


def main():
    """Een ronde door de gedeelde doorgang (N12). Ochtend (keten.py, werkdagen): bundels en de dagvaststelling van
    gisteren. Nacht (--nacht, elke dag, als stap van keten.py --nacht na De Zoomwacht): alleen de dagvaststelling, over
    NACHTVENSTER dagen. De taaknaam van de nacht (ochtend.NACHTTAAK) geeft het ochtendbericht nooit vrij (Codex D1)."""
    import ochtend
    with ag.ronde(ochtend.NACHTTAAK if NACHT else "bundels en dagvaststelling") as r:
        delen, nu = [], datetime.now(timezone.utc)
        nacht = lees_nacht()
        # G3: of De Zoomwacht in deze keten slaagde (True), faalde (False) of niet in deze keten liep (None)
        zoom_gelezen = None
        if NACHT:
            # F9: de nachtketen (keten.py --nacht) schrijft nacht.json voor ze mij start, met de exit van De Zoomwacht
            begin = ochtend.tijdstip(nacht.get("start"))
            zoom = (nacht.get("stappen") or {}).get("zoom-wacht") or {}
            if begin is None or nacht.get("einde") or nu - begin > timedelta(hours=3):
                r.nood("Nachtronde buiten de nachtketen: De Zoomwacht liep niet vooraf", wie="claude-code")
            elif zoom.get("exit") != 0:
                zoom_gelezen = False
                r.nood("De Zoomwacht faalde in de nachtketen: de Zoom-gesprekken van gisteravond kunnen ontbreken",
                       wie="claude-code")
            else:
                zoom_gelezen = True
        else:
            uit = bundelen()
            for n in uit["nood"]:
                r.nood(n["tekst"], wie=n["wie"])
            delen.append(uit["detail"])
            begin = ochtend.tijdstip(nacht.get("start"))
            stappen = nacht.get("stappen") or {}
            if begin is None or nu - begin > timedelta(hours=NACHT_UREN):
                # F9: een bezet slot of een cron die niet liep, zegt keten.log; hier wordt het een nood
                r.nood("De nachtketen van de dagvaststelling liep niet, zie keten.log", wie="claude-code")
            elif not nacht.get("einde") or any((stappen.get(n) or {}).get("exit") != 0 for n in ("zoom-wacht", "dagbundelaar")):
                # G3: ze liep, maar stopte halverwege of een stap faalde
                r.nood("De nachtketen van de dagvaststelling faalde, zie keten.log en dagbundelaar.log", wie="claude-code")
            # G3: in de ochtendketen zegt keten.json of De Zoomwacht net slaagde; faalde ze, dan is Zoom een ondergrens
            keten = lees_json(KETENBESTAND)
            kbegin = ochtend.tijdstip(keten.get("start"))
            if kbegin is not None and not keten.get("einde") and nu - kbegin <= timedelta(hours=3):
                zoom_gelezen = ((keten.get("stappen") or {}).get("zoom-wacht") or {}).get("exit") == 0
        dagen = [DAG] if DAG_GEGEVEN else V.venster(nu, VENSTER or (NACHTVENSTER if NACHT else 1))
        try:
            delen.append(vastleggen(r, dagen, zoom_gelezen=zoom_gelezen))
            if NACHT and not DAG_GEGEVEN:
                inhaal = inhaaldagen(nu, dagen)
                if inhaal:
                    delen.append("ingehaald: " + vastleggen(r, inhaal, zoom_gelezen=zoom_gelezen))
                    gedaan = lees_json(INHAALSTAAT)
                    gedaan.update({d: nu.isoformat() for d in inhaal})
                    _schrijf(INHAALSTAAT, json.dumps(gedaan, indent=1, sort_keys=True))
        except Exception as e:  # noqa: BLE001
            if NACHT:
                raise
            # In de ochtendketen houdt een mislukte dagvaststelling de bundels en het ochtendbericht niet tegen; de
            # nachtronde haalt de dag in, en de nood zegt het.
            ag.log(f"dag {DAG}", "fout", f"dagvaststelling mislukt: {type(e).__name__}: {str(e)[:200]}")
            r.nood("Dagvaststelling mislukt in de ochtendronde, zie werkverslag", wie="claude-code")
            # Codex-controle mailnood 2 (C1): deze ronde maakte de vaststelling niet af en sluit dus geen noden die ze
            # niet kon nakijken; wat open stond, blijft open (zoals noden_bij_breuk). Weet het bord niet wat open staat,
            # dan breekt de ronde toch, zodat het bord niets sluit; de bundels zijn dan al gemaakt.
            bestaand = ag.open_noden()
            if bestaand is None:
                raise
            for n in bestaand:
                r.nood(n["tekst"], wie=n["wie"])
        r.detail = "; ".join(d for d in delen if d)


# ------------------------------------------------------------------------------------------- dagvaststelling ---
NACHTBESTAND = os.path.join(DATA, "nacht.json")               # keten.py --nacht: start, einde, stappen met exit
KETENBESTAND = os.path.join(DATA, "keten.json")               # keten.py: de lopende ochtendketen, met de Zoomwacht
NACHT_UREN = 30                                               # zo oud mag de laatste nachtketen overdag zijn


def lees_json(pad):
    try:
        d = json.loads(_lees(pad) or "{}")
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def lees_nacht():
    return lees_json(NACHTBESTAND)


def _schrijf(pad, tekst):
    """Atomisch: een lezer (de Mac-sync) ziet altijd een heel bestand."""
    os.makedirs(os.path.dirname(pad), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(pad), prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(tekst)
    os.replace(tmp, pad)


def _lees(pad):
    try:
        with open(pad, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _sha(tekst):
    return hashlib.sha256(tekst.encode()).hexdigest()


def dagpad(dag):
    return os.path.join(DAGBOEK, dag[:4], f"{dag}.md")


def ontvangst():
    """De Mac-sync van Data uit Mehdi schrijft na de rsync per bestand de sha256 van de kopie in Dropbox (regels
    'sha256  ./JJJJ/JJJJ-MM-DD.md'). Geeft {dag: sha256}; leeg als er nog geen bewijs is."""
    uit = {}
    for regel in (_lees(ONTVANGST) or "").splitlines():
        delen = regel.split()
        if len(delen) == 2 and delen[1].endswith(".md") and "/versies/" not in delen[1]:
            uit[os.path.basename(delen[1])[:-3]] = delen[0]
    return uit


def inhaaldagen(nu, venster):
    """Codex P7 en W1: de dagen ouder dan het venster (tot INHAAL terug) waarvoor De WhatsApp-wacht of De Belwacht een
    dekkingsrij schreef of vervallen verklaarde na de laatste vaststelling of inhaalbeurt van die dag. Nieuwste eerst,
    hoogstens INHAAL_PER_NACHT, oplopend teruggegeven."""
    oudste = date.fromisoformat(min(venster))
    vroegste = date.fromisoformat(V.gisteren(nu)) - timedelta(days=INHAAL - 1)
    if vroegste >= oudste:
        return []
    # elke wijziging van een dekkingsrij telt, ook een die vervallen werd (Codex W1): dan is de dag niet meer gedekt
    # en moet zijn vaststelling 'onbekend' worden in plaats van de oude telling
    rijen = bord.db_lees("SELECT datum, MAX(ts) AS ts FROM gesprek_log WHERE bron = 'dekking' AND datum BETWEEN ? AND ? "
                         "GROUP BY datum", (vroegste.isoformat(), (oudste - timedelta(days=1)).isoformat()))
    try:
        staat = json.loads(_lees(STAAT) or "{}")
    except ValueError:
        staat = {}
    gedaan = lees_json(INHAALSTAAT)

    def tijd(x):
        try:
            t = datetime.fromisoformat(str(x))
            return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    uit = []
    for x in sorted(rijen, key=lambda x: x["datum"], reverse=True):
        nieuw = tijd(x["ts"])
        vorige = [v for v in (tijd((staat.get(x["datum"]) or {}).get("ts")), tijd(gedaan.get(x["datum"]))) if v]
        if nieuw is not None and (not vorige or nieuw > max(vorige)):
            uit.append(x["datum"])
    return sorted(uit[:INHAAL_PER_NACHT])


def gedekte_dagen(rijen):
    """F5: de (kanaal, dag) die een Mac-wacht als gelezen meldt: een dekkingsrij dekking:<kanaal>:<dag>. Een dekkingsrij
    die de wacht zelf vervallen verklaarde (de dag toont geen gegevens meer), bewijst niets meer: die dag is onbekend,
    nooit nul (Codex V1, fase 2)."""
    return {(str(x["uniek"]).split(":")[1], x["datum"]) for x in rijen
            if str(x["uniek"]).startswith("dekking:") and str(x["uniek"]).count(":") >= 2
            and str(x.get("dubbel_van") or "") != "buiten:vervallen"}


def kanaalstand(rij, nu):
    """D2: of WhatsApp of telefoon aangesloten is, zegt de hartslag van hun wacht, niet het bestaan van rijen. Alleen een
    wacht die de databank op de Mac leest (taak met 'databank', fase 2) en de laatste KANAAL_UREN klaar of waakt was,
    is aangesloten; zweeg ze langer of faalde ze, dan 'stil sinds ...'."""
    if not isinstance(rij, dict) or "databank" not in str(rij.get("taak") or ""):
        return "niet aangesloten"
    try:
        ts = datetime.fromisoformat(str(rij.get("ts")))
    except ValueError:
        return "stil sinds onbekend"
    if rij.get("status") in ("klaar", "waakt") and nu - ts <= timedelta(hours=KANAAL_UREN):
        return "aangesloten"
    return f"stil sinds {ts.astimezone(V.BRUSSEL):%d-%m %H:%M}"


def kanaal_van_dag(stand, kanaal, dag, gedekt):
    """F5: een aangesloten wacht bewijst alleen de dagen die ze zelf als gelezen meldt: een rij dekking:<kanaal>:<dag>
    (bron dekking) in de gesprekkentabel. Een dag zonder die rij is onbekend, nooit nul."""
    if stand != "aangesloten":
        return stand
    return "aangesloten" if (kanaal, dag) in gedekt else "onbekend voor deze dag"


def lees_agenda(dagen):
    """Alle afspraken van de dagen, met de archiefagenda's (Codex E2), per Brusselse dag; en welke agenda's niet gelezen
    werden (ook 'archief'; een privé-agenda zonder haar naam, F1). Alleen lezen. Ritten, hele dagen, feestdagen en
    geannuleerde vallen weg; dubbels een keer."""
    import agenda_wacht as W
    vandaag = datetime.now(timezone.utc).date()
    van = (date.fromisoformat(min(dagen)) - vandaag).days - 1
    tot = (date.fromisoformat(max(dagen)) - vandaag).days + 2
    ruw = W.afspraken(van, tot, alleen_lezen=True)
    archief = W.archief_afspraken(van, tot, alleen_lezen=True)
    ongelezen = {"een privé-agenda" if x["kalender"] in W.PRIVE_KALENDERS else W.KALENDERS.get(x["kalender"], x["kalender"])
                 for x in ruw if x.get("fout")}
    if W.ARCHIEF_FOUT:
        ongelezen.add("archief")
    ag.prive(W.prive_teksten(ruw + archief))       # het masker van het bord, als vangnet bovenop de eigen privéregel
    per_dag, gezien = defaultdict(list), set()
    for a in ruw + archief:
        if a.get("fout") or a.get("hele_dag") or "T" not in (a.get("start") or ""):
            continue
        if a.get("kalender", "").startswith("en.be#") or (a.get("titel") or "").lower().startswith("canceled"):
            continue
        if W.lees_titel(a.get("titel") or "")["reistijd"]:
            continue
        identiteit = (a.get("kalender"), a.get("id"), a.get("start"))
        if identiteit in gezien:
            continue
        gezien.add(identiteit)
        per_dag[a["start"][:10]].append(a)
    return per_dag, ongelezen, W.is_prive


MARGE_S = 1800                                                # zoveel voor en na een afspraak telt een meting mee


STIL_KMU = 3                                                  # zo traag is een meetpunt een stilstand
STOP_S = 600                                                  # zo lang bij de plek is een stop, ook zonder stilstand


def oordeel_uit_metingen(a, plek, punten, straal):
    """Het oordeel over een afspraak ter plaatse uit de ruwe meetpunten (dagvaststelling v1.7, Codex G2 en J1), niet uit de
    afgeleide indeling van het dagboek. plek: {'lat', 'lon'} van De Locatiewacht. In het venster van de afspraak (met
    MARGE_S ervoor en erna): een gemeten stop binnen `straal` meter (minstens twee punten van hoogstens STIL_KMU km/u, of
    punten bij de plek over minstens STOP_S seconden) is een aanwijzing; voorbijrijden of alleen metingen elders is niet
    gezien; geen meting is onbekend. Gemeten op 22-10-2026: bij een voorbijrit langs een project was er een punt op 1 km/u op 261 m
    en de rest rijdend, drie minuten; bij twee echte stops stond de auto minutenlang op 0 km/u binnen 40 m."""
    van, tot = (t.timestamp() for t in V.afspraak_venster(a))
    venster = [p for p in punten if van - MARGE_S <= p[0] <= tot + MARGE_S]
    if not venster:
        return {"uitkomst": "onbekend", "tekst": "auto zonder meting op dat uur"}
    bij = [p for p in venster if LW_afstand(plek["lat"], plek["lon"], p[1], p[2]) <= straal]
    stil = [p for p in bij if len(p) > 3 and p[3] is not None and p[3] <= STIL_KMU]
    if len(stil) >= 2 or (bij and bij[-1][0] - bij[0][0] >= STOP_S):
        return {"uitkomst": "doorgegaan", "tekst": f"auto gestopt bij de plek {V.uur_van(bij[0][0])} tot {V.uur_van(bij[-1][0])}"}
    if bij:
        return {"uitkomst": "niet_gezien", "tekst": f"auto reed voorbij de plek {V.uur_van(bij[0][0])}, geen stop gemeten"}
    return {"uitkomst": "niet_gezien", "tekst": f"auto gemeten elders, {V.uur_van(venster[0][0])} tot {V.uur_van(venster[-1][0])}"}


def bezoeken_zonder_afspraak(verblijven, punten, gekoppeld, straal, min_minuten):
    """K2: de bezoeken zonder afspraak, uit de verblijven van het dagboek maar met de echte meettijden en de eigen
    koppeling aan afspraken (niet die van De Locatiewacht, die een samengevoegd parkeerstuk aan een ochtendafspraak kan
    hangen). Een verblijf telt alleen met metingen binnen `straal` van zijn plek; van en tot zijn de eerste en de laatste
    van die metingen (aankomen en vertrekken). Het hoort bij een afspraak als het overlapt met het venster (met MARGE_S)
    van een afspraak die doorging volgens de metingen en binnen `straal` van haar plek ligt. Een project (waarschijnlijk of
    bevestigd) of een twijfelgeval altijd; een andere plek alleen vanaf `min_minuten` en nooit een vaste plek (thuis)."""
    uit = []
    for v in verblijven:
        if v.get("zekerheid") == "niet_mehdi" or v.get("lat") is None or v.get("lon") is None:
            continue
        gemeten = [p for p in punten if v["van"] - 300 <= p[0] <= v["tot"] + 300
                   and LW_afstand(v["lat"], v["lon"], p[1], p[2]) <= straal]
        if not gemeten:
            continue
        van, tot = gemeten[0][0], gemeten[-1][0]
        if any(g0 - MARGE_S <= tot and van <= g1 + MARGE_S and LW_afstand(lat, lon, v["lat"], v["lon"]) <= straal
               for g0, g1, lat, lon in gekoppeld):
            continue
        minuten = round((tot - van) / 60)
        if v.get("zekerheid") == "onzeker":
            soort = "twijfel"
        elif v.get("project") and v.get("zekerheid") in ("waarschijnlijk", "bevestigd"):
            soort = "project"
        elif v.get("vaste_plek") or minuten < min_minuten:
            continue
        else:
            soort = "elders"
        uit.append({"van": V.uur_van(van), "tot": V.uur_van(tot), "minuten": minuten, "waar": v.get("waar"), "soort": soort})
    return sorted(uit, key=lambda b: b["van"])


def LW_afstand(lat1, lon1, lat2, lon2):
    import locatie_wacht as LW
    return LW.afstand_m(lat1, lon1, lat2, lon2)


def lees_locatie(dag, afspraken):
    """Per afspraak ter plaatse het oordeel uit de ruwe meetpunten (oordeel_uit_metingen), met de plek die De
    Locatiewacht voor die afspraak bepaalt en dezelfde afsprakenlijst als de vaststelling (F4); de bezoeken zonder afspraak
    alleen als er een echte meting in valt; en de stand van het dagboek. Zonder geldige meting die dag, of als het dagboek
    niet afgesloten of voorlopig is of niet te lezen, krijgt elke afspraak ter plaatse 'onbekend' en zijn de bezoeken
    None."""
    import agenda_wacht as W
    import locatie_wacht as LW
    reden = ""
    try:
        d = LW.maak(dag, afspraken=afspraken)
        stand = str(d.get("status") or "")
        punten = d.get("meetpunten") or []
        if stand in ("afgesloten", "voorlopig") and not punten:
            stand, reden = "", "geen meting die dag"            # G2: afgesloten zegt alleen dat de tijd verstreek
        if stand in ("afgesloten", "voorlopig"):
            per_dag = {a.get("id"): a for a in afspraken}
            per_id = {}
            for aid, u in d["per_id"].items():
                a = per_dag.get(aid)
                if u.get("lat") is not None and u.get("lon") is not None and a is not None:
                    per_id[aid] = oordeel_uit_metingen(a, u, punten, LW.AFSPRAAK_M)
                else:
                    per_id[aid] = {"uitkomst": "zonder_adres" if u.get("uitkomst") == "zonder_adres" else "onbekend",
                                   "tekst": u.get("tekst") or "plek onbekend"}
            gekoppeld = [(V.afspraak_venster(per_dag[aid])[0].timestamp(), V.afspraak_venster(per_dag[aid])[1].timestamp(),
                          d["per_id"][aid]["lat"], d["per_id"][aid]["lon"])
                         for aid, u in per_id.items() if u["uitkomst"] == "doorgegaan"]
            bezoeken = bezoeken_zonder_afspraak(d.get("verblijven") or [], punten, gekoppeld, LW.AFSPRAAK_M, LW.MIN_BEZOEK)
            return per_id, bezoeken, stand, ""
        reden = reden or f"dagboek {stand or 'zonder stand'}"
    except Exception as e:  # noqa: BLE001
        reden = type(e).__name__
    # Dezelfde toetsregel als De Locatiewacht, met dezelfde projectnummers: faalde maak() voor de index geladen was, dan
    # las een projectnummer als huisnummer en werd een intern overleg 'niet gelezen' (Codex, 26-10-2026). De index van
    # maak() als die er is; de tegel alleen opnieuw vragen als maak() het nog niet probeerde, nooit na een mislukking.
    try:
        per_nummer = LW.INDEX_POGING["per_nummer"]
        if per_nummer is None and not LW.INDEX_POGING["mislukt"]:
            per_nummer = LW.projectindex()[1]
    except Exception:  # noqa: BLE001  de tegel zelf onbereikbaar: dan zonder index, liever 'onbekend' dan niets
        per_nummer = None
    per_id = {}
    for a in afspraken:
        info = W.lees_titel(a.get("titel") or "")
        if LW.te_toetsen(a, info, per_nummer):
            per_id[a.get("id")] = {"uitkomst": "onbekend", "tekst": f"locatie niet gelezen ({reden})"}
    return per_id, None, "", reden


SYSTEEMPYTHON = "/usr/bin/python3"
PLAFOND = 2000                                                # zoveel koppen per map; meer is niet volledig gelezen
MAILNOOD = "Mail niet volledig gelezen voor de dagvaststelling"  # + ": postvak (soort)"; zonder het staartje: voor 26-10
MAIL_NIET_GELEZEN = "Mail niet gelezen voor de dagvaststelling"


def lees_mail(dagen):
    """Ontvangen en verzonden mail per postvak over de dagen. De postbus (post/config.py) vraagt yaml, dat de mailwachten
    met de systeem-Python hebben en de omgeving van de keten (~/agents/.venv) niet: dan leest een kind met de
    systeem-Python (dagbundelaar.py --mailkoppen) en geeft het resultaat als bestand terug. Geeft (ontvangen, verzonden,
    privépostvakken)."""
    try:
        import yaml  # noqa: F401
    except ImportError:
        if not os.path.exists(SYSTEEMPYTHON) or "--mailkoppen" in sys.argv:
            raise                   # het kind zelf mist yaml: geen tweede kind (de venv en /usr/bin/python3 delen hun binaire)
        with tempfile.TemporaryDirectory() as m:
            uit = os.path.join(m, "mail.json")
            p = subprocess.run([SYSTEEMPYTHON, os.path.abspath(__file__), "--mailkoppen", ",".join(dagen), uit],
                               capture_output=True, text=True, timeout=900)
            if p.returncode != 0:
                raise RuntimeError(f"mailkoppen eindigde met {p.returncode}: {(p.stderr or '').strip()[-200:]}")
            d = json.loads(_lees(uit) or "{}")
        return d["ontvangen"], d["verzonden"], set(d["prive"])
    return _lees_mail(dagen)


def _lees_mail(dagen):
    """Rechtstreeks uit de mappen (Codex E4): zo is de leesdekking van deze ronde gekend. Alleen koppen, nooit inhoud.
    Ontvangen: de postvakken van de mailwachten, in de mappen die zij lezen. Verzonden: die postvakken en ook de adressen
    waaruit ze antwoorden (antwoord_vanuit, F7). Privé is een postvak van een wacht van firma PRIV of afdeling privé (F1)."""
    import postvak as PV
    sinds = (date.fromisoformat(min(dagen)) - timedelta(days=1)).isoformat()
    cfgs = [c for c in PV.wachten().values() if isinstance(c, dict) and "postvakken" in c]
    postvakken = list(dict.fromkeys(a for c in cfgs for a in c["postvakken"]))
    afzenders = [a for a in dict.fromkeys(a for c in cfgs for a in c.get("antwoord_vanuit") or []) if a not in postvakken]
    # H1: ook de adressen waaruit een privéwacht antwoordt (mch@ antwoordt uit info@, light@, standaard@): van daaruit kan
    # privépost vertrekken, dus geen ontvangers bij naam
    prive = {a for c in cfgs if c.get("firma") == "PRIV" or str(c.get("afdeling") or "").startswith("prive")
             for a in c["postvakken"] + list(c.get("antwoord_vanuit") or [])}
    ontvangen, verzonden = {}, {}

    def mis(waar, soort, reden, detail=""):
        # Overleg 26-10-2026 (K2): de soort is vast en geeft de nood (N10). De reden gaat naar het dagbestand en telt mee
        # in zijn hash, dus ook die is vast; wat wisselt (uren, fouttype) staat alleen in het detail, voor het logboek.
        # Anders kreeg elke dag van het venster elke nacht een nieuwe versie zolang een kopie oud bleef (lens 26-10).
        waar["onvolledig"].append(reden)
        waar.setdefault("soorten", []).append(soort)
        if detail:
            waar.setdefault("details", []).append(detail)

    vast = {"inbox", *(v.lower() for v in PV.VERZONDEN)}

    def naam(m):
        # Overleg 26-10-2026 (C3): een eigen map kan een klantnaam dragen; de reden gaat naar het dagbestand en het logboek
        return m if str(m).lower() in vast else "een eigen map"

    def lees(adres, m, waar, foto=None):
        try:
            deel = PV.koppen(adres, m, sinds=sinds, plafond=PLAFOND, inhoud=foto)
        except Exception as e:  # noqa: BLE001
            mis(waar, "map niet leesbaar", f"{naam(m)} niet leesbaar", f"{naam(m)}: {type(e).__name__}")
            return None
        if len(deel) >= PLAFOND:
            mis(waar, "te veel berichten", f"{naam(m)}: meer dan {PLAFOND} berichten")
        return deel

    for adres in postvakken + afzenders:
        u = verzonden.setdefault(adres, {"berichten": [], "onvolledig": []})
        o = ontvangen.setdefault(adres, {"berichten": [], "onvolledig": []}) if adres in postvakken else None
        mb = PV.postvak(adres)
        if not mb:
            for x in (o, u):
                if x is not None:
                    mis(x, "niet in de postbus", "niet in de postbus")      # G4: beide richtingen onbekend, nooit nul
            continue
        foto = None
        if mb.get("bron"):
            # De kopie komt sinds 26-10-2026 van de server (hotmail_server.py), daarvoor van de Mac. De server vervangt ze
            # elk uur: ouderdom, begindatum en koppen komen daarom uit een lezing (overleg 26-10-2026, C2).
            foto = PV.momentopname(mb)
            if foto is None:
                for x in (o, u):
                    if x is not None:
                        mis(x, "kopie onleesbaar", "kopie onleesbaar")
                continue
            oud = PV.bron_uren_oud(mb, inhoud=foto)
            for x in (o, u):
                if x is None:
                    continue
                if oud is None:
                    mis(x, "kopie niet vers", "kopie zonder tijdstip")
                elif oud > PV.BRON_VERS_UREN:
                    mis(x, "kopie niet vers", f"kopie ouder dan {PV.BRON_VERS_UREN} uur", f"kopie {oud:.0f} uur oud")
            # Overleg 26-10-2026 (X2): ook een verse kopie dekt maar een venster (hotmail_server.BINNEN_DAGEN), en ze loopt
            # tot ze gemaakt werd. Dat toetst mail_telling per dag (lens 26-10: per groep kreeg ook een gedekte dag
            # onvolledig). Zegt de kopie niet vanaf wanneer, dan is het voor elke dag onbekend: dat is een nood.
            vanaf = PV.bron_vanaf(mb, inhoud=foto)
            for x, mappen in ((o, PV.mappen_van(adres) if o is not None else []), (u, ["Sent"])):
                if x is None:
                    continue
                zonder = [m for m in mappen if not vanaf.get(m)]
                for m in zonder:
                    mis(x, "kopie zegt niet vanaf wanneer", f"kopie van {naam(m)} zegt niet vanaf wanneer")
                x["dekking"] = {"vanaf": max(vanaf[m] for m in mappen) if mappen and not zonder else "",
                                "gemaakt": str(foto.get("gemaakt") or "")}
        if o is not None:
            for m in PV.mappen_van(adres):
                deel = lees(adres, m, o, foto)
                # een kopie van eigen verzonden mail (Gmail: Alle e-mail) is geen ontvangen mail
                o["berichten"] += [b for b in deel or [] if (b.get("van") or "").lower() != adres.lower()]
        try:
            bestaand = PV.mapnamen(mb)
        except Exception as e:  # noqa: BLE001
            mis(u, "mappenlijst niet leesbaar", "mappenlijst niet leesbaar", f"mappenlijst: {type(e).__name__}")
            continue
        gelezen = False
        for m in PV.VERZONDEN:
            if (mb.get("mappen") and m not in mb["mappen"]) or (bestaand is not None and m.lower() not in bestaand):
                continue
            if bestaand is None and m != "Sent":
                continue        # een kopie (bestand) kent alleen INBOX en Sent
            deel = lees(adres, m, u, foto)
            if deel is not None:
                u["berichten"] += deel
                gelezen = True
        if not gelezen:
            mis(u, "geen map Verzonden leesbaar", "geen map Verzonden leesbaar")
    return ontvangen, verzonden, prive


def _telling(t):
    t = str(t or "")
    return "volledig" if t == "volledig" else ("ondergrens" if t.startswith(("ondergrens", "minstens", "laatst")) else "onbekend")


def zoomstand(inhoud, dag=None, vandaag=None):
    """(gesprekken, chat) uit de Zoom-dagregel van De Zoomwacht (dagvaststelling v1.7, Codex G3 en J2). De dagregel is het
    bewijs: De Zoomwacht schrijft ze alleen voor een afgelopen dag, met de bronstanden van de ronde die ze schreef
    (zoom_wacht.dag_inhoud), en verlaagt een opgepakte regel nooit tijdens een ronde met uitval (ZOO-01). Haar lezing heet
    dus 'volledig' als de telling volledig is, de stand definitief en elke bron 'ok'; anders een ondergrens of onbekend. De
    chat heeft haar eigen telling (meestal ondergrens). K1: 'ok' zegt dat een bron antwoordde, niet dat elke opname er al
    was; tot ZOOM_TERUGBLIK dagen na de dag (zoom_wacht.TERUGBLIK) heet een volledige regel 'voorlopig'. Dit is het oordeel
    van De Zoomwacht over haar eigen lezing; de vaststelling belooft zelf geen volledigheid (v1.9): ze telt wat gezien is,
    en een later gevonden gesprek geeft een nieuwe versie."""
    try:
        d = json.loads(inhoud or "{}") or {}
    except ValueError:
        return "onbekend", "onbekend"
    stand = _telling(d.get("telling"))
    bronnen = d.get("bronnen")
    if stand == "volledig" and not (isinstance(bronnen, dict) and bronnen and all(v == "ok" for v in bronnen.values())
                                    and d.get("stand") == "definitief"):
        stand = "ondergrens"
    if stand == "volledig" and dag and vandaag and (date.fromisoformat(vandaag) - date.fromisoformat(dag)).days <= ZOOM_TERUGBLIK:
        stand = "voorlopig"
    chat = d.get("chat")
    return stand, (_telling(chat.get("telling")) if isinstance(chat, dict) else "onbekend")


def vastleggen(r, dagen, zoom_gelezen=None):
    """De dagvaststelling van elke dag in `dagen` (ontwerp dagvaststelling v1.7). Leest agenda, locatie, gesprekkentabel,
    Zoom-dagregels, mail en de hartslag van de WhatsApp-wacht en de Belwacht; schrijft per dag het bestand (de vorige
    versie blijft in versies/, nooit overschreven), de staat en het klaarzet-item voor Mehdi, en leest bestand en item
    letterlijk terug (F8). zoom_gelezen: slaagde (True) of faalde (False) De Zoomwacht in deze keten, of liep ze niet mee
    (None); alleen voor het werkverslag. De Zoom-stand van een dag komt uit zijn dagregel (zoomstand, G3). Geeft het
    detail."""
    nu = datetime.now(timezone.utc)
    eerste, laatste = min(dagen), max(dagen)
    gisteren = V.gisteren(nu)
    per_dag, ongelezen, prive_afspraak = lees_agenda(dagen)
    rijen = bord.db_lees("SELECT uniek, datum, start, minuten, personen, afdeling, thema, prive, bron, "
                         "COALESCE(dubbel_van, '') AS dubbel_van FROM gesprek_log WHERE datum BETWEEN ? AND ?", (eerste, laatste))
    gedekt = gedekte_dagen(rijen)
    dagregels = {x["uniek"][9:]: x["inhoud"] or "" for x in bord.db_lees(
        "SELECT uniek, inhoud FROM klaarzet WHERE uniek BETWEEN ? AND ?", (f"zoom:dag:{eerste}", f"zoom:dag:{max(laatste, gisteren)}"))}
    vandaag = (date.fromisoformat(gisteren) + timedelta(days=1)).isoformat()
    zoom = {d: zoomstand(i, d, vandaag) for d, i in dagregels.items()}
    gezien_door_wachten = bord.db_lees("SELECT postvak, message_id, datum, soort FROM mailbericht WHERE dag BETWEEN ? AND ? "
                                       "AND COALESCE(message_id, '') != ''", (eerste, laatste))
    soorten = {x["message_id"]: x["soort"] for x in gezien_door_wachten}
    statussen = {x["naam"]: x for x in bord.db_lees(
        "SELECT naam, status, taak, ts FROM status WHERE naam IN ('whatsapp-wacht', 'belwacht')")}
    kanalen = {k: kanaalstand(statussen.get(w), nu) for k, w in KANAALWACHTEN.items()}
    try:
        ontvangen, verzonden, prive_postvakken = lees_mail(dagen)
        mailfout = ""
        # Wat de mailwachten al zagen en daarna naar een map buiten hun leeslijst sorteerden (Opgeruimd, Nieuwsbrieven),
        # staat niet meer in de gelezen mappen: die berichten tellen mee, ontdubbeld per Message-ID in mail_telling.
        # Ze voegen alleen toe; een onleesbare map blijft onvolledig (E4).
        for x in gezien_door_wachten:
            ontvangen.setdefault(x["postvak"], {"berichten": [], "onvolledig": []})["berichten"].append(
                {"datum": x["datum"], "message_id": x["message_id"]})
    except Exception as e:  # noqa: BLE001
        ontvangen = verzonden = None
        prive_postvakken, mailfout = set(), f"{type(e).__name__}"
    # Overleg 26-10-2026 (C): de volle reden, met de uren, staat in het logboek; de nood draagt alleen postvak en soort
    if ontvangen is None:
        ag.log("mail", "fout", f"mail niet gelezen ({mailfout})")
    else:
        for richting, x in (("ontvangen", ontvangen), ("verzonden", verzonden)):
            for adres, p in sorted(x.items()):
                if p.get("onvolledig"):
                    ag.log("mail", "bron", f"{adres} {richting} onvolledig: " + "; ".join(p["onvolledig"])
                           + (f" ({'; '.join(p['details'])})" if p.get("details") else ""))
    r.bron("kanaalstand", json.dumps(kanalen, sort_keys=True))
    try:
        staat = json.loads(_lees(STAAT) or "{}")
    except ValueError:
        staat = {}
    staat.pop(ZOOM_ONZEKER, None)                      # v1.6 hield hier vlaggen per keten bij; de dagregel volstaat
    if zoom_gelezen is False:
        ag.log("zoom", "bron", "De Zoomwacht faalde in deze keten; de stand per dag komt uit de dagregels")
    bewijs, nieuw, fouten, locatiefout = ontvangst(), [], [], set()
    for dag in sorted(dagen):
        afspraken = per_dag.get(dag, [])
        per_id, bezoeken, locatiestand, lf = lees_locatie(dag, afspraken)
        if lf:
            locatiefout.add(lf)
        mail = None if ontvangen is None else V.mail_telling(dag, ontvangen, verzonden, soorten)
        kanalen_dag = {k: kanaal_van_dag(s, k, dag, gedekt) for k, s in kanalen.items()}
        zoomdag, chatdag = zoom.get(dag, ("onbekend", "onbekend"))
        v = V.vaststellen(dag, afspraken, ongelezen, rijen, per_id, bezoeken, zoomdag, mail, kanalen_dag,
                          prive_afspraak, locatiestand, chatstand=chatdag)
        oud = _lees(dagpad(dag))
        # Het masker van het bord al voor het schrijven: bord, bestand en Dropbox dragen dezelfde tekst (E6)
        concept = ag.maskeer(V.tekst(v, prive_postvakken))
        if oud is not None and V.inhoud_hash(oud) == V.inhoud_hash(concept):
            tekst = oud                                   # niets veranderd: de vastgelegde versie blijft
        else:
            # F8: de versie volgt het bestand zelf; de staat is alleen een kopie
            basis = V.versie_van(oud) or int((staat.get(dag) or {}).get("versie") or 0) or (1 if oud is not None else 0)
            versie = basis + 1
            if oud is not None:
                archief = os.path.join(DAGBOEK, dag[:4], "versies", f"{dag} v{basis}.md")
                n = 1
                while _lees(archief) not in (None, oud):      # een bewaarde versie nooit overschrijven (F8, G7)
                    n += 1
                    archief = os.path.join(DAGBOEK, dag[:4], "versies", f"{dag} v{basis} ({n}).md")
                if _lees(archief) != oud:
                    _schrijf(archief, oud)
            over = [f"versie {versie}, gemaakt {nu.astimezone(V.BRUSSEL):%d-%m-%Y %H:%M}",
                    f"agenda: {v['agenda']['stand']}", f"Zoom: {v['zoom']['stand']}",
                    "locatie: " + (locatiestand if bezoeken is not None else f"niet gelezen ({lf})"),
                    # het fouttype staat in het logboek (Codex-controle mailnood 2)
                    "mail: " + ("alleen de mappen die de mailwachten lezen" if mail is not None else "niet gelezen"),
                    f"WhatsApp: {kanalen_dag['whatsapp']}", f"telefoon: {kanalen_dag['telefoon']}"]
            if oud is not None:
                over.append("herzien: " + (", ".join(V.wijzigingen(oud, concept)) or "opmaak"))
            tekst = ag.maskeer(V.tekst(v, prive_postvakken, over))
            _schrijf(dagpad(dag), tekst)
            staat[dag] = {"versie": versie, "hash": V.inhoud_hash(tekst), "ts": nu.isoformat()}
            _schrijf(STAAT, json.dumps(staat, ensure_ascii=False, indent=1, sort_keys=True))
            nieuw.append(f"{dag} v{versie}")
            ag.log(f"dag {dag}", "schrijf", f"vaststelling versie {versie}"
                   + (": " + ", ".join(V.wijzigingen(oud, tekst)) if oud is not None else ""))
        versie = V.versie_van(tekst) or 1
        titel = f"Dag {dag} vastgesteld" + (f" (versie {versie})" if versie > 1 else "")
        ag.klaarzet([{"voor": "mehdi", "soort": "dagvaststelling", "sleutel": dag, "titel": titel,
                      "uniek": f"vaststelling:{dag}", "inhoud": tekst, "revisie": True}])
        # Teruglezen (E6, F8): het bestand en het item tonen letterlijk de tekst die ik net vastlegde.
        terug = (bord.call("/api/klaarzet?" + urllib.parse.urlencode(
            {"uniek": f"vaststelling:{dag}", "status": "alle", "n": 5})) or {}).get("items") or []
        op_bord = next((x.get("inhoud") for x in terug if x.get("uniek") == f"vaststelling:{dag}"), None)
        if _lees(dagpad(dag)) != tekst:
            fouten.append(f"{dag}: bestand")
        if op_bord != tekst:
            fouten.append(f"{dag}: bord")
    if fouten:
        ag.log("teruglezen", "fout", "; ".join(fouten))
        raise RuntimeError("dagvaststelling niet teruggelezen: " + "; ".join(fouten[:5]))
    # Dropbox (D9, E6): een dag van eergisteren of ouder zonder ontvangstbewijs met dezelfde sha256 staat er niet.
    open_ = [d for d in dagen if d < gisteren and bewijs.get(d) != _sha(_lees(dagpad(d)) or "")]
    if open_:
        r.nood("Dagboek nog niet bevestigd in Dropbox: de sync van Data uit Mehdi op de Mac haalt het niet op", wie="mehdi")
    if ongelezen:
        r.nood("Agenda niet volledig gelezen voor de dagvaststelling", wie="claude-code")
    if locatiefout:
        r.nood("Locatie niet gelezen voor de dagvaststelling", wie="claude-code")
    if kanalen["whatsapp"] != "aangesloten":
        r.nood("WhatsApp: de WhatsApp-wacht leest de databank op de Mac nog niet (fase 2 van de dagvaststelling)",
               wie="claude-code")
    if kanalen["telefoon"] != "aangesloten":
        r.nood("Telefoon: de Belwacht leest de iPhone-oproepen op de Mac nog niet (fase 2 van de dagvaststelling)",
               wie="claude-code")
    # Overleg 26-10-2026 (K2): een nood per postvak en soort, nooit een wisselende lijst of een fouttype, zodat hij gelijk
    # blijft van ronde tot ronde (N10) en sluit zodra dat postvak weer leest
    if ontvangen is None:
        r.nood(MAIL_NIET_GELEZEN, wie="claude-code")
        # Overleg 26-10-2026 (C1): wat deze ronde niet kon nakijken, sluit ze niet. De open noden per postvak blijven
        # open; weet het bord niet welke open staan, dan breekt de ronde (als laatste), zodat noden_bij_breuk niets sluit.
        bestaand = ag.open_noden()
        if bestaand is None:
            raise RuntimeError("mail niet gelezen en de open mailnoden op het bord onbekend")
        for n in bestaand:
            if n["tekst"].startswith(MAILNOOD):
                r.nood(n["tekst"], wie=n["wie"])
    else:
        for adres, soort in sorted({(a, s) for x in (ontvangen, verzonden) for a, p in x.items()
                                    for s in p.get("soorten") or (["onvolledig"] if p.get("onvolledig") else [])}):
            r.nood(f"{MAILNOOD}: {adres} ({soort})", wie="claude-code")
    return (f"{len(dagen)} dag(en) vastgesteld, {len(nieuw)} nieuw of herzien"
            + (f" ({', '.join(nieuw[:4])})" if nieuw else "") + f"; Dropbox open: {len(open_)}")


if __name__ == "__main__":
    if "--mailkoppen" in sys.argv:
        # het kind van lees_mail: alleen koppen lezen en als bestand teruggeven; geen ronde, geen bord
        i = sys.argv.index("--mailkoppen")
        o, u, pr = _lees_mail(sys.argv[i + 1].split(","))
        _schrijf(sys.argv[i + 2], json.dumps({"ontvangen": o, "verzonden": u, "prive": sorted(pr)}, ensure_ascii=False,
                                             default=str))
        sys.exit(0)
    main()

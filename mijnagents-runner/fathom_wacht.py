#!/usr/bin/env python3
"""De Fathomwacht (Privé): haalt alles uit Fathom naar onze eigen plek, herkent
wie erbij was en waarover het ging, houdt een dagelijks logboek en een
gesprekkentabel bij, en zet klaar voor de afdelingen. Werkwijze v2 (10-09-2026):
het volledige proces staat op het bord (werkwijze/fathom-wacht.md is het zaad).

Twee keer per dag (07:00, 13:00) en op verzoek via De Regisseur (agent_ronde).
Archief: FATHOM_ARCHIEF_PAD (standaard mijnagents-data/fathom-data op de VM, plat:
één map per gesprek `JJJJ-MM-DD UUMM <titel in Fathom>`, sinds 18-09-2026 zonder
jaarmap en zonder Prive-submap; de privé-vlag staat in gesprek.json). De launchd-sync
op de Mac haalt die map naar Dropbox `Data uit Mehdi/Fathom data`. Nooit overschrijven,
nooit verwijderen. Het volledige archief (sinds 2024) is opgehaald door
fathom_haal_alles.py; dit script houdt het bij.
"""
import json
import os
import re
import signal
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
BE = ZoneInfo("Europe/Brussels")

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import sleutelbron  # noqa: E402  de Anthropic-sleutel alleen uit ~/appportal/.env (T-0064)
import bronnen  # noqa: E402
import dropbox_prive  # noqa: E402
import organisatie  # noqa: E402
import organisatie  # noqa: E402
import fathom  # noqa: E402
import pipedrive  # noqa: E402
import nummerlezer  # noqa: E402
sys.path.insert(0, os.path.join(HIER, "plaud"))
import dossier  # noqa: E402  dossierbeslissing op bewijs, gedeeld met De Plaudwacht (verbeteropdracht v1.0, §4)

NAAM = "fathom-wacht"
ag = bord.Agent(NAAM)
# Het gewone venster van de keten. Een echte ronde van De Regisseur leest alleen de laatste dag (FATHOM_WACHT_DAGEN=1, J1);
# wat een volledig venster veronderstelt (de nood over de eigen sleutel), doet zo'n korte ronde niet (BAS-04).
STANDAARD_DAGEN = 14
DAGEN = int(os.environ.get("FATHOM_WACHT_DAGEN", str(STANDAARD_DAGEN)))
ARCHIEF = os.path.expanduser(os.environ.get("FATHOM_ARCHIEF_PAD", "~/appportal/mijnagents-data/fathom-data"))
VERBODEN_TEKEN = re.compile(r'[/\\:*?"<>|\x00-\x1f]')
MODEL = os.environ.get("FATHOM_WACHT_MODEL", "claude-sonnet-5")
AFDELINGEN = ("h-architects", "unabo", "harmoniebouw", "contrax", "tkn", "elevait", "regie", "prive")
# Mehdi's eigen Fathom-sleutel herken ik aan een opname van zijn account: een exact adres uit fathom.MEHDI_FATHOM_ADRESSEN,
# dezelfde lijst als De Zoomwacht en De Regisseur (EIGEN-3, tegenproef 22-10-2026). Tot dan zocht ik op deelstukken
# ('h-architects', 'mch@'), en dan dempte een opname van een collega de nood hieronder.
SLEUTEL_NOOD = "Mehdi's eigen Fathom-sleutel ontbreekt op de VM (FATHOM_API_KEYS is nu van Shaniel); ik zie zijn gesprekken niet"
AANVUL_NOOD = "Fathom gaf deze ronde geen samenvatting en actiepunten: de aparte vraag faalde (werkverslag)"
# FATHOM-7: een archiefmap zonder herkenning (null) telt als privé, zoals een gesprek waarop het model niet antwoordde.
ONBEKENDE_HERKENNING = {"prive": True, "zekerheid": "laag", "waarom": "geen herkenning in het archief"}


def laad_env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


laad_env("~/agents/.env")
sleutelbron.zet_anthropic()                      # ANTHROPIC_API_KEY alleen uit ~/appportal/.env (T-0064)


# ----------------------------------------------------------- personen ---
def personen_uit_werkwijze(werkwijze):
    """De tabel 'Betrokken personen' uit de werkwijze op het bord: één plek."""
    uit = []
    blok = werkwijze.split("## Betrokken personen", 1)
    if len(blok) < 2:
        return uit
    for regel in blok[1].split("\n## ", 1)[0].splitlines():
        if not regel.startswith("|") or regel.startswith("|---") or regel.startswith("| Naam"):
            continue
        cellen = [c.strip() for c in regel.strip("|").split("|")]
        if len(cellen) >= 4 and cellen[0]:
            mails = [m.strip().lower() for m in re.split(r"[,;]", cellen[1]) if "@" in m]
            uit.append({"naam": cellen[0], "mails": mails, "afdeling": cellen[2], "rol": cellen[3],
                        "bijzonder": cellen[4] if len(cellen) > 4 else ""})
    return uit


def video_link(map_, g):
    """Fathom geeft via de API geen videobestand, alleen de link naar de opname. We zetten die
    als .webloc (dubbelklik opent de video in Fathom) en als regel in video.md in de map."""
    url = g.get("share_url") or g.get("url") or ""
    if not url or os.path.exists(os.path.join(map_, "video (Fathom).webloc")):
        return
    import plistlib
    with open(os.path.join(map_, "video (Fathom).webloc"), "wb") as f:
        plistlib.dump({"URL": url}, f)
    open(os.path.join(map_, "video.md"), "w", encoding="utf-8").write(
        f"Video van dit gesprek staat in Fathom (origineel blijft daar): {url}\n"
        "Fathom geeft via zijn API geen videobestand vrij; downloaden kan alleen met de hand op fathom.video.\n")


def deals_index():
    pipedrive.controleer_bedrijf("harchitects", 10068585)
    items = pipedrive.alles("harchitects", "/deals", {"status": "open"})     # alle pagina's, niet 500
    uit = []
    for x in items:
        titel = x.get("title", "")
        nummer = nummerlezer.ha_nummer(titel, "pipedrive_titel")
        p = x.get("person_id") if isinstance(x.get("person_id"), dict) else {}
        mails = {e.get("value", "").lower() for e in (p.get("email") or []) if isinstance(e, dict) and e.get("value")}
        uit.append({"id": x.get("id"), "titel": titel, "nummer": nummer, "mails": mails,
                    "delen": {w for w in re.split(r"[^a-z0-9]+", titel.lower()) if len(w) > 2 and not w.isdigit()}})
    return uit


def koppel_deal(g, deals):
    titel = g.get("title") or g.get("meeting_title") or ""
    code = nummerlezer.agendacode_van_titel(titel)
    if code and nummerlezer.firma_van_code(code) != "HARC":
        return None, "geen bewezen H-A-dossierkoppeling"
    # H1-2, driehoeksoverleg C2, 17-10-2026: een onzeker getal telt alleen bij een bestaande H-A-deal.
    nummers = {k.nummer for k in nummerlezer.lees(titel, "vergadertitel") if k.firma == "HARC"}
    if len(nummers) > 1:
        return None, "meer projectnummers in de titel; nakijken"
    bekend = {("HARC", str(d["nummer"])) for d in deals if d.get("nummer")}
    n = nummerlezer.ha_nummer(titel, "vergadertitel", bekend=bekend)
    if n:
        passend = [d for d in deals if d["nummer"] == n]
        if len(passend) == 1:
            return passend[0], "projectnummer in de titel"
        if len(passend) > 1:
            return None, "meer deals met hetzelfde projectnummer; nakijken"
        return None, "geen deal met het projectnummer; nakijken"
    mails = {(i.get("email") or "").lower() for i in (g.get("calendar_invitees") or []) if isinstance(i, dict)}
    passend = [d for d in deals if d["mails"] & mails]
    if len(passend) == 1:
        return passend[0], "e-mail van een deelnemer"
    if len(passend) > 1:
        return None, "meer deals met hetzelfde deelnemersadres; nakijken"
    delen = {w for w in re.split(r"[^a-z0-9]+", titel.lower()) if len(w) > 2}
    beste, score, gelijk = None, 0, False
    for d in deals:
        s = len(d["delen"] & delen)
        if s > score:
            beste, score, gelijk = d, s, False
        elif s == score and score >= 2:
            gelijk = True
    return (beste, f"naam in de titel ({score} woorden)") if beste and score >= 2 and not gelijk else (None, "")


# ------------------------------------------------------------- archief ---
def belgisch(iso):
    """UTC-tijd van Fathom naar Belgische tijd. Regel van Mehdi (12-09-2026): elk uur in het
    archief, de mapnamen, het logboek en de tabel is Belgisch, waar hij ook zit (Suriname, VS).
    Geeft 'JJJJ-MM-DDTUU:MM' of ''."""
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(BE).strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        return iso[:16]


def archiefmap(g, uniek=False):
    """`JJJJ-MM-DD UUMM <titel in Fathom>`, plat in het archief (Mehdi, 18-09-2026).

    Geen jaarmap en geen Prive-submap meer: de datum rangschikt zichzelf en de privé-vlag
    staat in gesprek.json. Botst de naam met een ander gesprek (uniek=True), dan komt het
    recording_id erachter. Dezelfde regel staat in fathom_haal_alles.py, dat het volledige
    archief ophaalde; wie er een verandert, verandert ze allebei.
    """
    start = belgisch(g.get("recording_start_time") or g.get("created_at") or "").replace("T", " ").replace(":", "")
    titel = VERBODEN_TEKEN.sub(" ", g.get("title") or g.get("meeting_title") or "").replace("\N{EN DASH}", "-")
    titel = re.sub(r"\s+", " ", titel).strip(" .-") or "zonder titel"
    staart = f" [{g.get('recording_id')}]" if uniek else ""
    naam = f"{start} {titel}"
    if len(naam) + len(staart) > 110:
        naam = naam[:110 - len(staart)].rstrip(" ,;-") + "…"
    return naam + staart


_INDEX = None


def bestaande_map(g):
    """De archiefmap van dit gesprek als ze al bestaat, gezocht op recording_id (één keer
    per ronde een index over alle mappen; de titel in Fathom kan later veranderd zijn)."""
    global _INDEX
    if _INDEX is None:
        _INDEX = {}
        for p in (os.listdir(ARCHIEF) if os.path.isdir(ARCHIEF) else []):
            gj = os.path.join(ARCHIEF, p, "gesprek.json")
            try:
                if os.path.exists(gj):
                    _INDEX[json.load(open(gj)).get("recording_id")] = os.path.join(ARCHIEF, p)
            except (OSError, ValueError):
                continue
    return _INDEX.get(g.get("recording_id"), "")


def veilige_naam(t):
    return re.sub(r"[^\w\- .,()]+", "", t or "").strip()[:70] or "gesprek"


def prive_verwijzing(map_, start, gid):
    """De verwijzing van een privé-item (RZ2-01): de archiefmap op de VM met '(privé)' in plaats van de titel in Fathom,
    die een naam of een onderwerp kan dragen, en het recording_id, waarop de map te vinden is (gesprek.json, zoals
    bestaande_map zoekt). Zoals verwijzing_van in zoom_wacht.py; de map zelf houdt haar naam."""
    return os.path.join(os.path.dirname(map_), f"{start[:10]} {start[11:16].replace(':', '')} (privé) [{gid}]")


def is_prive(herk, besl=None):
    """RZ3-01 (besluit van de regie, 22-10-2026: de veilige kant). Een gesprek is privé als de herkenning prive zegt OF de
    dossierbeslissing (plaud/dossier.py) het privé noemt: afdeling prive, ook met prive=false. Tot dan las ik voor de
    gesprekkentabel, het klaarzet-item (titel, inhoud, verwijzing) en het werkverslag alleen herkenning['prive'], terwijl
    de dossierbeslissing hetzelfde gesprek al privé noemde; zo kwamen naam en onderwerp alsnog in een bundel en in de
    export. Dezelfde regel staat in plaud_wacht.py; De Dagbundelaar en bord_export lezen inhoud.afdeling ook zo."""
    herk = herk or {}
    afdeling = str(herk.get("afdeling") or "").strip().lower()
    return bool(herk.get("prive")) or afdeling in ("prive", "privé") or bool((besl or {}).get("prive"))


def bewaar(g, tekst, herkenning):
    map_ = os.path.join(ARCHIEF, archiefmap(g))
    gj = os.path.join(map_, "gesprek.json")
    if os.path.exists(gj):
        try:
            ander = json.load(open(gj)).get("recording_id")
        except (OSError, ValueError):
            ander = None
        if ander == g.get("recording_id"):
            return map_, False
        map_ = os.path.join(ARCHIEF, archiefmap(g, uniek=True))   # naambotsing
        if os.path.exists(os.path.join(map_, "gesprek.json")):
            return map_, False
    os.makedirs(map_, exist_ok=True)
    ruw = g.get("transcript") if isinstance(g.get("transcript"), list) else []
    open(os.path.join(map_, "transcript.json"), "w", encoding="utf-8").write(json.dumps(ruw, ensure_ascii=False, indent=1))
    if not ruw and not tekst:
        open(os.path.join(map_, "geen-transcript.txt"), "w", encoding="utf-8").write("Fathom heeft voor dit gesprek geen transcript.\n")
    kop = (f"# {g.get('title') or g.get('meeting_title') or ''}\n\nBelgische tijd: {belgisch(g.get('recording_start_time', '')).replace('T', ' ')} tot {belgisch(g.get('recording_end_time', '')).replace('T', ' ')}\n"
           f"Fathom (UTC) {g.get('recording_start_time', '')} tot "
           f"{g.get('recording_end_time', '')} · {g.get('url', '')}\nDeellink: {g.get('share_url', '')}\n"
           f"Opgenomen door: {(g.get('recorded_by') or {}).get('name', '')}\nDeelnemers: "
           + ", ".join(f"{i.get('name', '')} <{i.get('email', '')}>" for i in (g.get("calendar_invitees") or []))
           + f"\n\nHerkenning: {json.dumps(herkenning, ensure_ascii=False)}\n\n")
    open(os.path.join(map_, "transcript.md"), "w", encoding="utf-8").write(kop + tekst)
    # ANGEL-8 en FATHOM-1: de samenvatting als markdown-tekst (tot T-0120 str() van het hele object) en de actiepunten in
    # onze vorm, alleen wat ontbreekt; de vraag met transcript levert ze niet, de aanvulvraag van deze ronde wel.
    fathom.vul_aan(map_, g)
    if g.get("highlights"):
        open(os.path.join(map_, "hoogtepunten.md"), "w", encoding="utf-8").write(json.dumps(g["highlights"], ensure_ascii=False, indent=1))
    meta = {k: v for k, v in g.items() if k != "transcript"}
    meta["herkenning"] = herkenning
    open(os.path.join(map_, "gesprek.json"), "w", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False, indent=1))
    video_link(map_, g)
    if _INDEX is not None:
        _INDEX[g.get("recording_id")] = map_       # zodat de aanvulvraag van deze ronde de nieuwe map ook vindt
    return map_, True


def aanvullen(sinds):
    """FATHOM-1 en ANGEL-8 (overleg T-0120, X9): de aparte vraag zonder transcript, met samenvatting en actiepunten, en
    per recording_id in de bestaande archiefmap alleen wat ontbreekt (fathom.vul_aan, nooit overschrijven). Niets naar
    het bord: geen klaarzet, geen rij, in het werkverslag alleen aantallen, ook van een privégesprek. Geeft de telling."""
    tel = {"gesprekken": 0, "samenvatting": 0, "actiepunten": 0, "zonder_map": 0}
    for g in fathom.samenvattingen(sinds):
        tel["gesprekken"] += 1
        map_ = bestaande_map(g)
        if not map_:
            tel["zonder_map"] += 1         # nog niet in het archief: de volgende ronde
            continue
        nieuw = fathom.vul_aan(map_, g)
        tel["samenvatting"] += "samenvatting.md" in nieuw
        tel["actiepunten"] += "actiepunten.json" in nieuw
    return tel


# ---------------------------------------------------------- herkennen ---
PLAUD_REGEL = (" Dit is een opname uit het gedeelde Plaud-account met meerdere toestellen: wie opnam en of Mehdi erbij was, "
               "is niet bewezen; leid het alleen af uit wat er gezegd wordt. Het veld 'context' bevat alleen afspraken die het "
               "opnametijdstip overlappen; een project dat je noemt is een kandidaat, het dossier beslist het bewijs.")


def herken(g, tekst, personen, deal, hoe, context=None, bron="fathom"):
    """Met het model: personen, bedrijf, afdeling, thema, project, privé. Deterministische
    voorkennis (personentabel, Pipedrive) gaat mee; het model vult aan en motiveert.

    context (verbeteropdracht v1.0, §7): agenda die het opnametijdstip overlapt, locatie,
    openingszinregel en bronbewijzen als eigen veld. Tot 12-10-2026 plakte De Plaudwacht die achter
    de tekst en ging bij een lang transcript alles na teken 6000 verloren. Alleen het transcript
    wordt nog begrensd."""
    from anthropic import Anthropic
    deelnemers = [{"naam": i.get("name"), "email": i.get("email"), "extern": i.get("is_external")} for i in (g.get("calendar_invitees") or [])]
    bekend = []
    for d in deelnemers:
        for p in personen:
            if (d.get("email") or "").lower() in p["mails"] or (d.get("naam") and p["naam"].lower().split()[0] in (d.get("naam") or "").lower()):
                bekend.append({"deelnemer": d.get("naam") or d.get("email"), "is": p["naam"], "afdeling": p["afdeling"], "rol": p["rol"], "bijzonder": p["bijzonder"]})
    schema = {"name": "herkenning", "description": "Herkenning van het gesprek", "input_schema": {"type": "object", "properties": {
        "personen": {"type": "array", "items": {"type": "string"}}, "hoofdpersoon": {"type": "string"},
        "bedrijf": {"type": "string"}, "afdeling": {"type": "string", "enum": list(AFDELINGEN) + ["onbekend"]},
        "thema": {"type": "string"}, "project": {"type": "string"}, "prive": {"type": "boolean"},
        "zekerheid": {"type": "string", "enum": ["hoog", "middel", "laag"]}, "waarom": {"type": "string"}},
        "required": ["personen", "hoofdpersoon", "bedrijf", "afdeling", "thema", "project", "prive", "zekerheid", "waarom"]}}
    system = ("Je herkent voor Mehdi Chegini (H-Architects) een " + ("Plaud-opname" if bron == "plaud" else "Fathom-gesprek")
              + ": wie erbij was, welk bedrijf, welke afdeling "
              "(h-architects, unabo, harmoniebouw, contrax, tkn, elevait, regie, prive), thema, project of dossier, en of het privé is. "
              "Elevait NV is het bedrijf van Mehdi met zijn partners Shaniel, Angela en Siyan (AI-trainingen en AI-toepassingen); gesprekken over de opbouw van Elevait, AI-trainingen of sollicitaties daar zijn afdeling elevait. TKN-Buro (partner Tom) doet engineering en stabiliteit. "
              "Privé: alleen Mehdi en Angela (zijn partner), Mehdi alleen, of een duidelijk persoonlijk onderwerp; bij twijfel privé. "
              "Raad geen afdeling voor een onbekende externe deelnemer: dan 'onbekend' en zekerheid laag. Nederlands, kort. "
              "Motiveer in 'waarom' waarop je je baseert (deelnemer, e-mail, titel, wat er gezegd werd), zodat Mehdi je redenering kan nalezen. "
              "De lijst 'collegas' (uit organisatie.globaal.be) zegt wie intern is, bij welke afdeling en firma; een gesprek van Mehdi met "
              "alleen collega's is intern (afdeling regie, of de afdeling van het onderwerp), niet een klant. Weeg personen op afdeling en functie, "
              "niet op firma: partners (Siyan, Shaniel, Angela, Tom, Catalin, Matthias) zitten in meerdere bedrijven, en een deskundige die "
              "erbij zit (Shaniel als AI/ICT bij een Energy-gesprek) verandert het onderwerp niet. Het thema en de afdeling volgen de inhoud."
              + (PLAUD_REGEL if bron == "plaud" else ""))
    user = json.dumps({"titel": g.get("title") or g.get("meeting_title"), "start": g.get("recording_start_time"),
                       "opgenomen_door": g.get("recorded_by"), "deelnemers": deelnemers, "herkend_uit_tabel": bekend,
                       "pipedrive_deal": ({"id": deal["id"], "titel": deal["titel"], "hoe": hoe} if deal else None),
                       "personentabel": personen, "collegas": organisatie.samenvatting(), "context": context or {},
                       "transcript_begin": tekst[:6000]}, ensure_ascii=False)
    resp = Anthropic().messages.create(model=MODEL, max_tokens=1200, system=system, messages=[{"role": "user", "content": user}],
                                       tools=[schema], tool_choice={"type": "tool", "name": "herkenning"})
    for b in resp.content:
        if getattr(b, "type", "") == "tool_use":
            h = dict(b.input)
            h["deal_id"] = deal["id"] if deal else None
            h["koppeling"] = hoe
            return h
    return {"personen": [], "hoofdpersoon": "", "bedrijf": "", "afdeling": "onbekend", "thema": "", "project": "", "prive": True,
            "zekerheid": "laag", "waarom": "model gaf geen herkenning", "deal_id": deal["id"] if deal else None, "koppeling": hoe}


# ----------------------------------------------------------------- main ---
def stop_bij_sigterm(signum, frame):
    """J1, K3 (ontwerp regie-zoom v1.2): timeout stopt een te lange ronde met SIGTERM (de cron na 2700 s, De Regisseur
    na 540 s). Zonder handler stierf het proces meteen en bleef de hartslag op actief staan (N11). Nu gaat het als
    SystemExit door main(), en sluit de finally daar de hartslag af."""
    raise SystemExit(128 + signum)


def nu_utc():
    return datetime.now(timezone.utc)


def eerste_volle_dag(begin):
    """De eerste Belgische dag die volledig in het venster valt, als 'JJJJ-MM-DD' (BAS-04). De dag waarin het venster
    begint, ziet de ronde maar voor een deel: haar logboek herschrijven zou het inkorten, ook in Dropbox, want spiegel_map
    stuurt elk gewijzigd bestand door. Dat gold voor de korte ronde van De Regisseur (J1) en voor de oudste dag van het
    gewone venster. Fathom geeft wat na het begin aangemaakt is (created_after); een opname bestaat niet voor ze begint."""
    b = begin.astimezone(BE)
    dag = b.date() if (b.hour, b.minute, b.second, b.microsecond) == (0, 0, 0, 0) else b.date() + timedelta(days=1)
    return dag.isoformat()


def sleutel_nood(gesprekken):
    """De nood over Mehdi's eigen Fathom-sleutel als lijst, of None als deze ronde de vorige stand niet kent (BAS-04).

    Een opname van zijn account bewijst de sleutel: geen nood. Geen opname in het volle venster (STANDAARD_DAGEN of meer):
    de nood. Geen opname in een kort venster, zoals de echte ronde die De Regisseur start (J1), bewijst niets: dan blijft
    de vorige stand, open als ze open stond en dicht als ze dicht was. Weet het bord die stand niet, dan None: onbekend is
    niet leeg."""
    eigenaars = {((g.get("recorded_by") or {}).get("email") or "").strip().lower() for g in gesprekken}
    # Mehdi's Fathom-account neemt op als zoomafspraken@gmail.com (sleutel MEHDI_FATHOM_API_KEY, ook in ~/elevait/.env);
    # alleen een exact adres telt, nooit een deel ervan (EIGEN-3)
    if eigenaars & fathom.MEHDI_FATHOM_ADRESSEN:
        return []
    if DAGEN >= STANDAARD_DAGEN:
        return [{"tekst": SLEUTEL_NOOD, "wie": "mehdi"}]
    vorig = ag.open_noden()
    if vorig is None:
        return None
    return [n for n in vorig if n["tekst"] == SLEUTEL_NOOD]


def main():
    afgesloten = False
    try:
        if not fathom.beschikbaar():
            ag.hartslag("actief", taak="Fathom ophalen")
            ag.hartslag("fout", taak="geen Fathom-sleutel", detail="FATHOM_API_KEYS ontbreekt")
            afgesloten = True
            # RZ2-02: een ronde die Fathom niet kon lezen, eindigt niet op 0. Met exit 0 schreef keten.py 'geslaagd' en
            # kon het ochtendbericht voor 10:30 vertrekken zonder Fathom-lezing. Een sleutel die faalt, gooit hieronder
            # een fout op en eindigt zo ook niet op 0.
            return 1
        # De gedeelde ronde (N12, NA09-rest 01-11-2026): de werkwijze met de personentabel, of geen ronde; en wat ik las
        # (N4), de lessen (N13) en de collega's (N14). Een fout of een stopsignaal (SIGTERM als SystemExit, Ctrl-C) zet
        # de ronde zelf op fout, en wat al open stond blijft open (N11, J1, K3).
        try:
            with ag.ronde("Fathom ophalen") as r:
                _ronde(r)
        except bord.RondeGestopt as e:
            afgesloten = True
            bord.diagnose(f"ronde gestopt: {e}")
            return 1
        afgesloten = True
        return 0
    finally:
        # Vangnet zoals voor 01-11 (overleg 15, F3; Codex NA74 ook voor het pad zonder sleutel): een signaal op een moment
        # dat de ronde het zelf niet meer kon melden (de time-out van de keten, een tweede signaal), liet de hartslag op
        # actief. Kwam haar fouthartslag niet aan, dan hier nog een, zonder noodlijst, zodat wat open stond open blijft.
        # Een eenmalige beste poging, zoals op main.
        if not afgesloten and ag.laatste_status != "fout":
            ag.hartslag("fout", taak="ronde afgebroken", detail="ronde afgebroken voor het einde (time-out of stopsignaal)")


def _ronde(r):
    try:
        werkwijze = r.werkwijze
        personen = personen_uit_werkwijze(werkwijze)
        begin = nu_utc() - timedelta(days=DAGEN)
        sinds = begin.strftime("%Y-%m-%dT%H:%M:%SZ")
        gesprekken = fathom.gesprekken(sinds, met_transcript=True)
        deals = deals_index()
        klaar, rijen, nieuw_archief, prive_n, logdag = [], [], 0, 0, {}
        for g in gesprekken:
            gid = str(g.get("recording_id") or g.get("url", "").rsplit("/", 1)[-1])
            tekst = fathom.transcript_tekst(g)
            deal, hoe = koppel_deal(g, deals)
            # herkenning alleen voor wat nog niet in het archief zit (kosten)
            al = bestaande_map(g)
            if al:
                # FATHOM-7: fathom_haal_alles.py schreef "herkenning": null (1960 mappen tot 17-09-2026); .get(.., {}) gaf
                # dan None en de ronde brak af (01-10-2026). Geen herkenning is privé, de veilige kant, zonder naam.
                herk = json.load(open(os.path.join(al, "gesprek.json"))).get("herkenning") or dict(ONBEKENDE_HERKENNING)
                map_, nieuw = al, False
            else:
                herk = herken(g, tekst, personen, deal, hoe)
                map_, nieuw = bewaar(g, tekst, herk)
            nieuw_archief += 1 if nieuw else 0
            start = belgisch(g.get("recording_start_time") or g.get("created_at") or "")
            duur = 0
            try:
                duur = int((datetime.fromisoformat(g["recording_end_time"].replace("Z", "+00:00")) - datetime.fromisoformat(g["recording_start_time"].replace("Z", "+00:00"))).total_seconds() / 60)
            except Exception:  # noqa: BLE001
                pass
            # dossier op bewijs: titel, of de e-mail van een deelnemer bij een deal met projectnummer;
            # het project dat het model noemt is een kandidaat, geen bewijs
            bewijzen = dossier.uit_tekst("titel", g.get("title") or g.get("meeting_title") or "")
            if deal and deal.get("nummer") and hoe == "e-mail van een deelnemer":
                bewijzen.append(dossier.bewijs("deelnemer", "HARC", deal["nummer"], hoe))
            # H1-2, driehoeksoverleg C2, 17-10-2026: dezelfde firmacomposiet als in koppel_deal.
            besl = dossier.beslis(bewijzen, herk, dossier.uit_tekst("model", herk.get("project") or ""),
                                  bekend={("HARC", str(d["nummer"])) for d in deals if d.get("nummer")})
            # RZ3-01: privé volgens de herkenning OF de dossierbeslissing, voor de tabel, het item en het werkverslag
            prive = is_prive(herk, besl)
            prive_n += 1 if prive else 0
            if deal and deal.get("nummer") != besl["projectnummer"]:
                deal = None                 # een deal die niet bij het beslist dossier hoort, krijgt geen kopie
            rij = {"uniek": f"fathom:{gid}", "datum": start[:10], "start": start[11:16], "minuten": duur,
                   "personen": ", ".join(herk.get("personen") or []), "bedrijf": herk.get("bedrijf", ""), "afdeling": herk.get("afdeling", ""),
                   "thema": herk.get("thema", ""), "project": herk.get("project", "") or (deal["titel"] if deal else ""),
                   "prive": prive, "zekerheid": herk.get("zekerheid", ""), "waarom": herk.get("waarom", ""), "archief": map_,
                   "link": g.get("url", ""), "opgenomen_door": (g.get("recorded_by") or {}).get("name", ""),
                   "bron": "fathom"}   # Z13: expliciet, niet de stille standaard van het bord
            rijen.append(rij)
            logdag.setdefault(start[:10], []).append(rij)
            # kopie naar de salesmap bij een H-A-dossier (nooit overschrijven), niet als privé
            pad = ""
            if deal and tekst and besl["kopie_toegestaan"]:
                salesmap = bronnen.zoek_salesmap(re.sub(r"^\s*\d{4}\s+", "", deal["titel"]), deal["nummer"])
                if salesmap:
                    naam = f"{start[:10]} Fathom transcript - {veilige_naam(g.get('title') or g.get('meeting_title') or hoofd_van(herk))}.md"
                    if not any(e.get("name") == naam for e in (bronnen.lijst(f"{salesmap}/0 Fathom", recursief=False) or [])):
                        pad = bronnen.upload(f"{salesmap}/0 Fathom/{naam}", open(os.path.join(map_, "transcript.md"), "rb").read())
                        ag.log(f"gesprek {start}", "schrijf", f"kopie naar {pad} (origineel: {map_})")
                    else:
                        pad = f"{salesmap}/0 Fathom/{naam}"
            voor = besl["voor"]
            dossiersleutel = (besl["projectnummer"] or "") if besl["zekerheid"] != "laag" else ""
            if prive:
                # RZ2-01 (M3): een privé-item draagt geen persoon, onderwerp of toelichting, ook niet in de verwijzing (de
                # archiefmap heet naar de titel in Fathom). Het gaat naar De Dagbundelaar, De Levenscoach en de export van
                # het bord; met wie en waarover staan in het archief op de VM.
                verwijzing = prive_verwijzing(map_, start, gid)
                klaar.append({"voor": voor, "soort": "transcript", "sleutel": dossiersleutel,
                              "titel": f"{start} Fathom: privégesprek, {duur} min · PRIVÉ", "uniek": f"fathom:{gid}", "verwijzing": verwijzing,
                              "inhoud": {"datum": start[:10], "start": start[11:16], "minuten": duur, "prive": True, "archief": verwijzing}})
            else:
                klaar.append({"voor": voor, "soort": "transcript", "sleutel": dossiersleutel,
                              "titel": f"{start} Fathom: {herk.get('hoofdpersoon') or g.get('title')} · {herk.get('thema', '')[:60]}",
                              "uniek": f"fathom:{gid}", "verwijzing": pad or map_,
                              "inhoud": {**{k: v for k, v in rij.items() if k not in ("waarom", "bron")}, "waarom": herk.get("waarom", ""), "transcript_pad": pad or os.path.join(map_, "transcript.md"),
                                         "dossier": besl["dossier"], "firma": besl["firma"], "projectnummer": besl["projectnummer"],
                                         "deal_id": deal["id"] if deal else None, "zekerheid_dossier": besl["zekerheid"],
                                         "conflict": besl["conflict"], "redenen": besl["redenen"]}})
            if prive:
                # BAS-01, M3 (ontwerp 13.2): met wie en waarover vallen weg bij een privégesprek, ook in het werkverslag.
                # Dat gaat naar een taalmodel (het dossier en agent_verslag van De Regisseur, De Ontwikkelaar), en het
                # masker van het bord kent deze namen niet. Wanneer en hoe lang blijft; de rest staat in het archief.
                ag.log(f"gesprek {start}", "bevinding", f"privégesprek · {duur} min · zekerheid {herk.get('zekerheid')}")
            else:
                ag.log(f"gesprek {start}", "bevinding",
                       f"{herk.get('hoofdpersoon') or g.get('title')} · {herk.get('afdeling')} · {herk.get('thema', '')[:60]} · zekerheid {herk.get('zekerheid')}",
                       herk.get("waarom", ""))
        # logboek per dag in het archief, alleen voor een dag die deze ronde volledig zag (BAS-04)
        volle = eerste_volle_dag(begin)
        geschreven = sorted(dag for dag in logdag if dag >= volle)
        os.makedirs(os.path.join(ARCHIEF, "logboek"), exist_ok=True)
        for dag in geschreven:
            lijst = logdag[dag]
            regels = [f"# Fathom-logboek {dag}", "", f"{len(lijst)} gesprek(ken), {sum(r['minuten'] for r in lijst)} minuten", "",
                      "| start | min | personen | bedrijf | afdeling | thema | project | privé |", "|---|---|---|---|---|---|---|---|"]
            regels += [f"| {r['start']} | {r['minuten']} | {r['personen']} | {r['bedrijf']} | {r['afdeling']} | {r['thema'][:50]} | {r['project'][:40]} | {'ja' if r['prive'] else ''} |" for r in sorted(lijst, key=lambda x: x["start"])]
            open(os.path.join(ARCHIEF, "logboek", f"{dag}.md"), "w", encoding="utf-8").write("\n".join(regels) + "\n")
        # FATHOM-1: samenvatting en actiepunten in een aparte vraag, voor de spiegel zodat ze deze ronde meegaan. Faalt
        # die vraag, dan blijft de rest van de ronde staan en is het een nood, geen stille nul; in het werkverslag
        # alleen de soort fout (de tekst van een fout kan uit het antwoord van Fathom komen).
        try:
            aan = aanvullen(sinds)
            ag.log("Fathom", "schrijf", f"samenvatting en actiepunten van Fathom: {aan['samenvatting']} samenvatting(en), "
                   f"{aan['actiepunten']} lijst(en) actiepunten aangevuld; {aan['gesprekken']} gesprekken gevraagd"
                   + (f", {aan['zonder_map']} nog zonder archiefmap" if aan["zonder_map"] else ""))
        except Exception as e:  # noqa: BLE001
            aan = None
            ag.log("Fathom", "bevinding", f"samenvatting en actiepunten niet aangevuld: {type(e).__name__}")
        # kopie van het archief naar Mehdi's eigen Dropbox (alleen wat nieuw is)
        sp = dropbox_prive.spiegel_map(ARCHIEF, "/Fathom data")
        if sp["verstuurd"] or sp["fout"]:
            ag.log("Fathom", "schrijf", f"Dropbox privé: {sp['verstuurd']} bestand(en) verstuurd, {sp['rest']} nog te gaan"
                   + (f"; fout: {sp['fout']}" if sp["fout"] else ""))
        bord.call("/api/gesprekken", {"rijen": rijen})
        uit = ag.klaarzet(klaar)
        # BAS-01: van een privérij alleen datum en start, zoals in de bevinding
        ag.log("Fathom", "bron", f"{len(gesprekken)} gesprekken sinds {sinds[:10]} van {len(fathom.sleutels())} sleutel(s); {nieuw_archief} nieuw in het archief; {prive_n} privé; {len(personen)} personen in de tabel",
               "\n".join(f"{r['datum']} {r['start']} (privé)" if r["prive"] else f"{r['datum']} {r['start']} {r['personen'][:40]} | {r['afdeling']} | {r['thema'][:50]}" for r in rijen))
        ag.log("Fathom", "schrijf", f"gesprekkentabel bijgewerkt ({len(rijen)} rijen); klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend; logboek voor {len(geschreven)} dag(en)")
        sleutel = sleutel_nood(gesprekken)
        nood = list(dropbox_prive.nood(wat="het Fathom-archief"))
        if any(len(p["mails"]) == 0 and "aan te vullen" in p.get("mails", []) for p in personen) or len([p for p in personen if p["mails"]]) < 6:
            nood.append({"tekst": "De tabel Betrokken personen mist e-mailadressen van collega's (dashboard van Mehdi)", "wie": "mehdi"})
        if aan is None:
            nood.append({"tekst": AANVUL_NOOD, "wie": "claude-code"})
        r.detail = f"laatste ronde: {len(gesprekken)} gesprekken, {nieuw_archief} nieuw, {prive_n} privé"
        if sleutel is None:
            # BAS-04: de vorige stand van de sleutelnood is onbekend. Dan sluit het bord niets (nood_sluiten false): wat
            # deze ronde vond komt erbij, wat open stond blijft open, ook de sleutelnood (overleg 12, X6). Tot 01-11-2026
            # ging er dan geen lijst mee en stond wat de ronde vond alleen in het detail.
            r.noden_onbekend = True
            r.detail += "; open noden onbekend: het bord sluit niets"
        for n in (sleutel or []) + nood:
            r.nood(n["tekst"], wie=n["wie"])
    except Exception as e:  # noqa: BLE001  de ronde zet de fouthartslag en houdt de open noden open
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        raise


def hoofd_van(herk):
    return herk.get("hoofdpersoon") or "gesprek"


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop_bij_sigterm)
    sys.exit(main())

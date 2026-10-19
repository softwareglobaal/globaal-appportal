#!/usr/bin/env python3
"""De Tekenaar (h-architects): elke week een normcontrole van de nieuwe bouwaanvraagplannen. Draait op de Mac van Mehdi.

Waarom op de Mac: daar staat het gereedschap van De Tekenaar (repo globaal-vectorworks-brug, normcontrole.py met
PyMuPDF), naast Vectorworks. Waarom toch via de VM:
  - het bord laat buiten de VM alleen hartslag, klaarzet en logboek door (nginx, 63-mijnagents); de werkwijze, de
    kennis, de noden en de collega's niet. Daarom praat deze runner met het bord via een ssh-tunnel naar
    127.0.0.1:3022 op de VM, zoals de runners daar, met het token uit ~/.config/mijnagents/token (dat de andere
    Mac-agents ook gebruiken). Zo gaat ook deze ronde door de gedeelde ag.ronde (N4, N10 tot N14);
  - de Mac heeft geen Dropbox-sleutel en zijn lokale Dropbox toont online-only bestanden als 0 bytes. De lijst en de
    PDF's komen van koppelingen/ba_plannen.py op de VM (ssh, zoals mac/hotmail_koppen.py), met de sleutel van de stack.

De normcontrole komt uit GitHub (origin/main van de brug), niet uit de werkmap: een andere sessie die daar half
bewerkt, raakt de weekronde niet.

launchd (mac/be.globaal.mijnagents.tekenaar.plist) start hem elke dag om 10:00 en bij het aanmelden. Hij werkt als de
vorige gelukte ronde zes dagen oud is, of als er nog plannen of meldingen wachten. Zo haalt hij in wat de Mac verslapen
heeft, geeft hij elke week een hartslag ook zonder nieuwe plannen (N11), en meldt hij binnen zeven dagen wat hij las (N4).

    tekenaar.py            de ronde, als die aan de beurt is
    tekenaar.py --nu       een ronde, ook als de vorige net gelukt is
    tekenaar.py --droog    lijst en controle tonen; niets naar het bord, de stand blijft gelijk
    tekenaar.py --droog --sinds 2026-10-05   idem, alsof alles vanaf die dag nieuw is (proef op echte plannen)

Hij leest alleen. Hij schrijft niets in Dropbox: de PDF's gaan naar een werkmap buiten Dropbox en worden na de controle
gewist; zijn stand (wat al bekeken is) staat in ~/Library/Application Support/mijnagents/tekenaar/. Naar het bord gaan
projectnummer, submap en bladcode, nooit de projectmap of de voorwerp-ID: daar staan adressen en namen in.
"""
import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402

NAAM = "tekenaar"
ag = bord.Agent(NAAM)
VM = os.environ.get("TEKENAAR_VM", "globaal")
BRUG = os.path.expanduser(os.environ.get("TEKENAAR_BRUG", "~/dev/globaal-vectorworks-brug"))
STAND = os.path.expanduser(os.environ.get("TEKENAAR_STAND", "~/Library/Application Support/mijnagents/tekenaar/stand.json"))
WERKMAP = os.path.expanduser(os.environ.get("TEKENAAR_WERKMAP", "~/Library/Caches/mijnagents/tekenaar"))
TOKEN_PAD = os.path.expanduser("~/.config/mijnagents/token")
DROPBOX = os.path.expanduser("~/TKN-buro Dropbox")
BORD_PUBLIEK = "https://mijnagents.globaal.be"
HULP = "~/agents/.venv/bin/python ~/appportal/mijnagents-runner/koppelingen/ba_plannen.py"
HULP_VERSIE = "4"
BORDSTAND = "~/agents/.venv/bin/python ~/appportal/mijnagents-runner/koppelingen/bordstand.py"
MAX_DETAIL = 15000          # het bord kapt het detail van een logboekregel af op 20.000 tekens (mijnagents/app.py)
MAX_INHOUD = 50000          # en de inhoud van een klaarzet-item op 60.000 (Codex DT16)
SSH_SOCKET = os.path.expanduser("~/.ssh/tekenaar-%C")
# De archiefcontrole van oktober 2026 (overleg/archiefcontrole-2026-10.md in de brug) mat de jongste versie van elk blad
# tot 18-10-2026: wat daarvoor laatst gewijzigd is, telt als vrijgesteld (basis), niet als stuk voor stuk gecontroleerd.
BASISDATUM = "2026-10-18T00:00:00+00:00"
# Zes dagen (min een marge voor de duur van een ronde): zo valt de volgende ronde altijd binnen de zeven dagen van N4,
# zolang de Mac op dag zes of zeven aan staat.
RITME = timedelta(days=6) - timedelta(hours=2)
MAX_PER_RONDE = 150
MAX_PER_MELDING = 100       # plannen per melding: het werkverslag blijft ruim onder de 300 regels die het bord teruggeeft
ID = re.compile(r"^id:[A-Za-z0-9_-]{6,}$")
BASISMAPPEN = ("0 H-A Standaard projects", "0 H-A Light projects")
SOORTEN = "O|ML|P|S|G|T|L|I|IB|PB|LB|SB|GB|TB|D|C|F|3D|V"

# Wat een fout betekent en wat De Tekenaar voorstelt; het besluit blijft bij Mehdi (werkwijze, "Wat Mehdi beslist").
LABEL = {"meetlijn": "meetlijn", "persoonsgegevens": "persoonsgegevens", "eenheid": "eenheid", "schaal": "schaal",
         "bestandsnaam": "bestandsnaam", "voorwerp_id": "voorwerp-ID", "gewest": "gewest", "noordpijl": "noordpijl",
         "ruimtefuncties": "ruimtebenamingen", "snede_aangeduid": "plaats van de snede", "maataanduiding": "maatcijfers",
         "toestanden": "toestanden B, V en N", "bladnummers": "dubbele bladcode", "dxf_maten": "maten DXF",
         "dxf_maatlabels": "maatlabels DXF"}
VOORSTEL = {
    "meetlijn": "schaalbalk laten volgen met de schaal van het blad (sjabloonherstel in de TODO van De Tekenaar)",
    "eenheid": "de eenheid (maten in centimeter) op het blad zetten",
    "schaal": "een normschaal vermelden (1/50, 1/100, 1/200 ...)",
    "bestandsnaam": "de naam volgens de loketcodering zetten voor het indienen",
    "gewest": "het normenboek B01 niet toepassen; Mehdi beslist welke regels gelden",
    "toestanden": "de vergunde toestand toevoegen of de samenvoeging uitdrukkelijk melden",
    "bladnummers": "de volgnummers herschikken zodat elke bladcode een keer voorkomt",
    "persoonsgegevens": "een keer het titelblok in het sjabloon herstellen (zonder bouwheer en rijksregisternummer, "
                        "besluit 18-10-2026); dan verdwijnt deze fout op elk nieuw blad",
}
# Woorden die in de vrije tekst van een bladnaam naar het bord mogen (Codex DT10, DT17, DT21): alleen namen van
# tekeningen en bouwdelen. Geen mapwoorden, geen namen; een vrije tekst met een ander woord wordt '(vrije tekst)'.
# Mapnamen gaan nooit naar het bord.
TEKENWOORDEN = set("""
gelijkvloers verdieping verdiepingen eerste tweede derde vierde vijfde kelder zolder zolderverdieping dak dakplan
dakverdieping bovenverdieping voorgevel achtergevel zijgevel zijgevels linker rechter linkergevel rechtergevel gevel
gevels kopgevel snede sneden doorsnede doorsneden inplanting inplantingsplan terreinprofiel terreinprofielen profiel
legende fundering funderingsplan funderingen garage berging tuinberging carport veranda terras aanbouw bijgebouw
uitbreiding woning appartement appartementen gebouw grondplan grondplannen situatie situering overzicht overzichtsplan
detail details constructie visualisatie wadi regenwater riolering afvoer put kap kapverdieping mezzanine foto fotos
foto's bestaand bestaande nieuw nieuwe vergund vergunde toestand en met van de het
""".split()) | set("abcdefghijklmnopqrstuvwxyz")     # een losse letter (toestand, gevelletter) noemt niemand
# Een fout die uit het sjabloon komt en op bijna elk blad staat: in de titel van het signaal gaan andere fouten voor
# (ontwerplezing Codex, weekronde 19-10-2026). Per blad blijft ze zichtbaar in het werkverslag.
SJABLOONFOUT = {"persoonsgegevens"}


def nu_utc():
    return datetime.now(timezone.utc)


def week(t=None):
    j, w, _ = (t or datetime.now().astimezone()).isocalendar()
    return f"{j}-W{w:02d}"


# ------------------------------------------------------------ werkmappen ---
def buiten_dropbox(pad):
    """Een map voor De Tekenaar zelf, gecontroleerd voor ze bestaat: nooit in Dropbox (geen projectmap)."""
    echt = os.path.realpath(pad)
    if echt == os.path.realpath(DROPBOX) or echt.startswith(os.path.realpath(DROPBOX) + os.sep):
        raise RuntimeError(f"map ligt in Dropbox; geweigerd: {pad}")
    os.makedirs(pad, mode=0o700, exist_ok=True)
    return pad


# ------------------------------------------------------------------ stand ---
def lege_stand():
    """bekend: de BA-plannen die nu in de projectmappen staan, per Dropbox-id (pad en inhoud), voor de set-controle.
    gezien: elke inhoud (content_hash) die De Tekenaar al kent: basis (archiefcontrole), wacht of gecontroleerd. Nieuw
    is een inhoud die hij nog niet zag; een kopie of een verplaatst plan (een project dat van fasemap verandert) niet.
    te_melden: gecontroleerde plannen waarvan werkverslag en signaal het bord nog niet bevestigd hebben."""
    return {"versie": 1, "cursors": {}, "bekend": {}, "gezien": {}, "wachtrij": [], "te_melden": [],
            "geen_toegang": {}, "laatste_week": None, "laatste_ronde": None}


def lees_stand(pad=None):
    pad = pad or STAND
    try:
        with open(pad, encoding="utf-8") as f:
            st = json.load(f)
    except FileNotFoundError:
        return lege_stand()
    except ValueError as e:
        raise RuntimeError(f"stand onleesbaar: {type(e).__name__}") from e
    if not isinstance(st, dict) or st.get("versie") != 1 or not all(
            isinstance(st.get(k), t) for k, t in (("bekend", dict), ("gezien", dict), ("wachtrij", list), ("cursors", dict))):
        raise RuntimeError("stand onleesbaar: onverwachte vorm")
    st.setdefault("te_melden", [])
    st.setdefault("geen_toegang", {})
    return st


def bewaar_stand(st, pad=None):
    """Atomair: eerst een tijdelijk bestand ernaast, dan os.replace, zodat een onderbroken ronde nooit een halve stand
    achterlaat."""
    pad = pad or STAND
    buiten_dropbox(os.path.dirname(pad))
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(pad), prefix=".stand-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)
    os.replace(tmp, pad)


def is_ba_pdf(naam):
    n = (naam or "").lower()
    return n.startswith("ba_") and n.endswith(".pdf")


def inhoud(b):
    """De sleutel van de inhoud: de content_hash van Dropbox (zelfde inhoud, zelfde sleutel)."""
    return b.get("hash") or f"{b.get('id')}@{b.get('rev')}"


def basis_van(pad):
    p = (pad or "").lower()
    return next((k for k, b in (("standaard", BASISMAPPEN[0]), ("light", BASISMAPPEN[1])) if "/" + b.lower() + "/" in p), None)


def selecteer(st, lijst, basisdatum=BASISDATUM):
    """Verwerkt de wijzigingen van ba_plannen.py in de stand, in de volgorde van Dropbox. Een plan is nieuw als De
    Tekenaar zijn inhoud nog niet zag. Bij de allereerste lijst telt een plan dat voor de basisdatum laatst gewijzigd
    is als vrijgesteld (archiefcontrole van oktober 2026). Een volledige lijst van een projectmap vervangt wat hij van
    die map kende: wat er niet meer in staat, is weg. Geeft (nieuw, weg)."""
    eerste = not st["gezien"]
    bekend, gezien, wacht = st["bekend"], st["gezien"], st["wachtrij"]
    nieuw = weg = 0
    gezien_ids = set()
    # Mappen zonder toegang voor de stack (Codex DT20, DT28, DT33), in de volgorde van Dropbox: een volledige lijst
    # van een basismap begint met een lege lijst dichte mappen en meldt ze opnieuw; 'dicht' sluit een map, 'map' (een
    # leesbare map in een deellijst) of een plan dat eronder zichtbaar wordt, opent ze. Wat onder een dichte map staat,
    # is niet weg: het wacht op toegang.
    toegang = st.setdefault("geen_toegang", {})
    volledig_lijst = lijst.get("volledig") or {}
    for basis, volledig in volledig_lijst.items():
        if volledig:
            toegang[basis] = []

    def dicht():
        return [d.lower() for d in blinde_vlekken(st)]

    def open_(pad):
        for basis, paden in toegang.items():
            blijft = [d for d in paden if not (pad == d.lower() or pad.startswith(d.lower() + "/"))]
            if len(blijft) != len(paden) and not volledig_lijst.get(basis):
                # DT37: wat er in de map gebeurde terwijl ze dicht was (een verwijderd blad), weet de Mac niet; een
                # volledige herlijst van die basismap in dezelfde ronde zet het recht, voor de set-controle
                st["herlijst"] = sorted(set(st.get("herlijst") or []) | {basis})
            toegang[basis] = blijft

    for w in lijst.get("wijzigingen", []):
        if w.get("soort") == "dicht":
            basis = w.get("basis") or basis_van(w.get("pad")) or "standaard"
            toegang[basis] = sorted(set(toegang.get(basis, [])) | {w["pad"]})
            continue
        if w.get("soort") == "map":
            open_((w.get("pad") or "").lower())
            continue
        if w.get("soort") == "weg":
            p = (w.get("pad") or "").lower()
            gesloten = dicht()
            for i, b in list(bekend.items()):
                q = (b.get("pad") or "").lower()
                if any(q.startswith(d + "/") for d in gesloten):
                    continue
                if p and (q == p or q.startswith(p + "/")):
                    del bekend[i]
                    weg += 1
            continue
        if w.get("soort") != "bestand" or not ID.match(w.get("id") or "") \
                or not is_ba_pdf(os.path.basename(w.get("pad") or "")):
            continue
        q = (w.get("pad") or "").lower()
        if any(q.startswith(d + "/") for d in dicht()):
            open_(q)
        sleutel = inhoud(w)
        bekend[w["id"]] = {"hash": sleutel, "pad": w["pad"]}
        gezien_ids.add(w["id"])
        if sleutel in gezien:
            continue
        if eerste and (w.get("gewijzigd") or "") and w["gewijzigd"].replace("Z", "+00:00") < basisdatum:
            gezien[sleutel] = {"status": "basis"}
            continue
        gezien[sleutel] = {"status": "wacht", "gewijzigd": w.get("gewijzigd")}
        wacht.append(w["id"])
        nieuw += 1
    gesloten = dicht()
    for basis, volledig in volledig_lijst.items():
        if volledig:      # Codex DT11: een volledige lijst ruimt op wat er niet meer staat
            for i, b in list(bekend.items()):
                q = (b.get("pad") or "").lower()
                if any(q.startswith(d + "/") for d in gesloten):
                    continue  # DT20: een map zonder toegang is niet leeg; wat daar wacht, blijft wachten
                if basis_van(b.get("pad")) == basis and i not in gezien_ids:
                    del bekend[i]
                    weg += 1
    herstel_wachtrij(st)
    st["cursors"].update(lijst.get("cursors") or {})
    return nieuw, weg


def bijwerken(st, basisdatum=BASISDATUM):
    """De lijst van de VM verwerken; ging er een map zonder toegang weer open, dan meteen een volledige lijst van die
    basismap (DT37). Geeft (nieuw, weg, lijst)."""
    lijst = lijst_van_vm(st["cursors"])
    nieuw, weg = selecteer(st, lijst, basisdatum)
    if st.get("herlijst"):
        for basis in st["herlijst"]:
            st["cursors"].pop(basis, None)
        st["herlijst"] = []
        n2, w2 = selecteer(st, lijst_van_vm(st["cursors"]), basisdatum)
        nieuw, weg = nieuw + n2, weg + w2
    return nieuw, weg, lijst


def wacht_op_toegang(st, ident):
    """Staat dit plan in een map zonder toegang? Dan wordt het niet opgehaald en blokkeert het de ronde niet (DT28)."""
    q = (st["bekend"].get(ident, {}).get("pad") or "").lower()
    return any(q.startswith(d.lower() + "/") for d in blinde_vlekken(st))


def verwerkbaar(st):
    """De plannen in de wachtrij die nu op te halen zijn."""
    return [i for i in st["wachtrij"] if not wacht_op_toegang(st, i)]


def blinde_vlekken(st):
    """De mappen onder de projectmappen die De Tekenaar niet kan lezen (gedeeld, zonder toegang voor de stack)."""
    return sorted(p for paden in (st.get("geen_toegang") or {}).values() for p in paden)


def herstel_wachtrij(st):
    """De wachtrij: per inhoud die nog wacht een plan dat er nu staat. Is het plan uit de wachtrij weg, dan neemt een
    ander plan met dezelfde inhoud zijn plaats; is er geen, dan valt de inhoud terug naar ongezien en telt ze als
    nieuw als ze terugkomt."""
    bekend, gezien = st["bekend"], st["gezien"]
    wachtend = {k for k, g in gezien.items() if g.get("status") == "wacht"}
    rij, gedekt = [], set()
    for i in list(st["wachtrij"]) + list(bekend):
        b = bekend.get(i)
        if b and b["hash"] in wachtend and b["hash"] not in gedekt:
            rij.append(i)
            gedekt.add(b["hash"])
    for k in wachtend - gedekt:
        del gezien[k]
    st["wachtrij"] = rij


# ------------------------------------------------------- paden en labels ---
def projectnummer(pad):
    """(nummer, projectmap): de eerste map onder de fasemap die met vier cijfers begint; anders 'zonder nummer'."""
    delen = (pad or "").split("/")
    for i, d in enumerate(delen):
        if d in BASISMAPPEN:
            for x in delen[i + 1:-1]:
                m = re.match(r"^(\d{4})\b", x)
                if m:
                    return m.group(1), x
            break
    # Codex DT30: twee mappen zonder nummer mogen niet hetzelfde label krijgen; een korte vaste code per map, zonder
    # de mapnaam zelf (die kan een naam of adres dragen)
    map_ = os.path.dirname(pad or "")
    return f"zonder nummer {hashlib.sha256(map_.lower().encode()).hexdigest()[:6]}", os.path.basename(map_)


def gevoelig(tekst):
    """Staat er een nummer van vijf of meer cijfers in, hoe ook geschreven? Elk stuk tekst zonder letters telt als een
    reeks, welke tekens er ook tussen de cijfers staan ("0499 (123) 456", "049_9_123_456", "0499–123–456",
    "0499:123:456", "84.03.21-411.65"): het kan een telefoon- of rijksregisternummer zijn (Codex DT31, DT35, DT36).
    Een versie (versieDDMMJJJJ) telt niet."""
    zonder_versie = re.sub(r"versie\d{8}", "x", tekst or "", flags=re.I)
    return any(len(re.sub(r"\D", "", r)) >= 5 for r in re.findall(r"[^A-Za-zÀ-ÿ]+", zonder_versie))


def toegelaten(tekst):
    """Mag deze vrije tekst van een bladnaam naar het bord: alleen woorden uit TEKENWOORDEN, getallen en korte codes
    (V3, A, 00). Een naam of een adres valt erbuiten (Codex DT10, DT21)."""
    if gevoelig(tekst):
        return False
    for woord in re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?|\w+", tekst or ""):
        w = woord.lower()
        # getallen tot vier cijfers (een niveau, een jaar); een langer getal kan een telefoon- of rijksregisternummer
        # zijn (Codex DT27)
        if w in TEKENWOORDEN or re.fullmatch(r"\d{1,4}|[a-z]?\d{1,3}[a-z]?", w):
            continue
        return False
    return True


def bladcode(naam):
    """De bestandsnaam zonder 'BA_' en zonder voorwerp-ID (daar staat het adres in): 'P_N_1_00_gelijkvloers.pdf'. Wat
    na de tekeningsoort komt, gaat alleen mee als het uit toegelaten woorden bestaat; anders '(vrije tekst)'."""
    m = re.match(rf"^BA_.+?_((?:{SOORTEN})_.*)$", naam or "", re.I) \
        or re.match(rf"^BA_.+?\s((?:{SOORTEN})_[BNVT]{{1,4}}(?:_.*|\.pdf))$", naam or "")   # spatie voor de soort
    if m:
        code = m.group(1)
    else:
        code = re.sub(r"^BA_.*?\b[1-9]\d{3}\s+[^_]*_?", "", naam or "", flags=re.I)
        if not code or code == naam or code.lower().startswith("ba_"):
            return "blad zonder tekeningsoort in de naam"
    stam, ext = os.path.splitext(code)
    delen = stam.split("_")
    vast = [delen[0]] if m else []
    rest = delen[1:] if m else delen
    # Alleen wat de loketcodering is, elk veld hoogstens een keer en in volgorde: toestand (B, V, N, T), deelset
    # (cijfers), volgnummer (cijfers, of een hoofdletter als gevel- of snedeletter), versie. Een kort woord zoals een
    # voornaam is geen code (Codex DT17), en een nummer in stukjes geen reeks codevelden (DT35).
    for veld in (r"[BNVT]{1,4}", r"\d{1,3}", r"\d{1,3}|[A-Z]'?|[A-Z]\d", r"versie\d{8}"):
        if rest and re.fullmatch(veld, rest[0]):
            vast.append(rest.pop(0))
    if gevoelig(stam):
        # DT35: de hele zichtbare naam getoetst; staat er ergens een lang nummer, dan alleen soort en toestand
        kop = [d for d in vast[:2] if not re.search(r"\d", d)]
        return "_".join(kop + ["(vrije tekst)"]) + ext
    vrij = "_".join(rest)
    if vrij and not toegelaten(vrij):
        vrij = "(vrije tekst)"
    return "_".join(vast + ([vrij] if vrij else [])) + ext


def blad_label(pad):
    """Wat er van een plan naar het bord gaat (Codex DT10, DT21): projectnummer en bladcode, niets anders. Geen
    mapnamen (daar staan adressen, klanten en medewerkers in) en geen voorwerp-ID."""
    return f"{projectnummer(pad)[0]} / {bladcode(os.path.basename(pad or ''))}"


def map_labels(mappen):
    """Een label per map zonder de mapnaam: projectnummer en een volgnummer binnen het project ('2610 map 2')."""
    uit, teller = {}, {}
    for m in sorted(mappen):
        nr = projectnummer(m + "/x.pdf")[0]
        teller[nr] = teller.get(nr, 0) + 1
        uit[m] = f"{nr} map {teller[nr]}"
    return uit


# ----------------------------------------------------------- VM via ssh ---
def vm(opdracht, invoer=None, timeout=600, hulp=HULP):
    """Een opdracht van ba_plannen.py op de VM. Geeft (code, stdout als bytes, stderr). Een gedeelde ssh-verbinding
    (ControlMaster, een minuut open na de laatste opdracht) houdt honderd plannen in een ronde onder de paar minuten."""
    # De socket in ~/.ssh met een korte naam: macOS laat 104 tekens toe en ssh plakt er bij het aanmaken nog 17 achter
    # (gemeten 19-10-2026: in de werkmap werd het pad te lang en faalde elke aanroep).
    r = subprocess.run(["/usr/bin/ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=30",
                        "-o", "ControlMaster=auto", "-o", f"ControlPath={SSH_SOCKET}",
                        "-o", "ControlPersist=60", VM, f"{hulp} {opdracht}"],
                       input=invoer, capture_output=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr.decode("utf-8", "replace").strip()[-300:]


def hulp_versie():
    code, uit, fout = vm("versie", timeout=60)
    return uit.decode().strip() if code == 0 else None


def bord_stand():
    """Wat het bord nu van De Tekenaar weet (bordstand.py op de VM, alleen lezen), of None."""
    code, uit, fout = vm(NAAM, hulp=BORDSTAND, timeout=60)
    try:
        return json.loads(uit.decode()) if code == 0 else None
    except ValueError:
        return None


def bevestigd(begin, stand=None):
    """Staan de hartslag (klaar of waakt) en de kennis van deze ronde echt op het bord? De gedeelde ronde slikt een
    mislukte melding; pas met deze bevestiging telt de ronde als gedaan (Codex DT09). Geeft (ja, waarom niet)."""
    stand = stand if stand is not None else bord_stand()
    if not stand:
        return False, "bordstand.py op de VM gaf geen antwoord"

    def van_deze_ronde(ts):
        try:
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            return False
        return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)) >= begin

    if not van_deze_ronde(stand.get("ts")) or stand.get("status") not in ("klaar", "waakt"):
        return False, f"de hartslag van deze ronde staat niet op het bord ({stand.get('status')}, {stand.get('ts')})"
    if not van_deze_ronde(stand.get("kennis_ts")):
        return False, "de kennis van deze ronde staat niet op het bord (N4)"
    return True, ""


def lijst_van_vm(cursors):
    code, uit, fout = vm("lijst", json.dumps({"cursors": cursors}).encode(), timeout=1800)
    if code != 0:
        raise RuntimeError(f"lijst van de VM mislukt (code {code}): {fout}")
    return json.loads(uit.decode("utf-8"))


def haal_van_vm(ident, doel):
    """Schrijft de PDF naar doel. Geeft 'ok', 'weg' (Dropbox kent het niet meer als BA-plan in de projectmappen) of
    'te_groot' (boven de grens van ba_plannen.py). Elke andere fout breekt de ronde: dan probeert de volgende het opnieuw."""
    if not ID.match(ident):
        raise ValueError("geen Dropbox-id")
    code, uit, fout = vm(f"haal {ident}", timeout=300)
    if code == 4:
        return "weg"
    if code == 5:
        return "te_groot"
    if code != 0 or not uit.startswith(b"%PDF"):
        raise RuntimeError(f"ophalen van een plan mislukt (code {code}): {fout}")
    with open(doel, "wb") as f:
        f.write(uit)
    return "ok"


@contextlib.contextmanager
def tunnel():
    """ssh -L naar het bord op de VM (127.0.0.1:3022). Geeft de url; sluit de tunnel na de ronde."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        poort = s.getsockname()[1]
    p = subprocess.Popen(["/usr/bin/ssh", "-N", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
                          "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=30",
                          "-L", f"127.0.0.1:{poort}:127.0.0.1:3022", VM],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        for _ in range(100):
            if p.poll() is not None:
                raise RuntimeError("ssh-tunnel naar het bord kwam niet op: "
                                   + p.stderr.read().decode("utf-8", "replace").strip()[-200:])
            with socket.socket() as s:
                s.settimeout(0.3)
                if s.connect_ex(("127.0.0.1", poort)) == 0:
                    break
            time.sleep(0.3)
        else:
            raise RuntimeError("ssh-tunnel naar het bord kwam niet op binnen dertig seconden")
        yield f"http://127.0.0.1:{poort}"
    finally:
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()


def hartslag_publiek(token, detail):
    """Lukt de tunnel niet, dan via de publieke ingang (/agent-status laat het token door): hartslag 'fout', zonder
    noodlijst, zodat het bord geen open nood sluit die deze ronde niet kon nakijken."""
    try:
        req = urllib.request.Request(f"{BORD_PUBLIEK}/agent-status", method="POST",
                                     data=json.dumps({"naam": NAAM, "status": "fout", "taak": "normcontrole",
                                                      "detail": detail[:240]}).encode(),
                                     headers={"Content-Type": "application/json", "X-Agents-Token": token})
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:  # noqa: BLE001
        print("hartslag via de publieke ingang mislukt:", e, file=sys.stderr)


# --------------------------------------------------------------- controle ---
def git(*args, timeout=60):
    r = subprocess.run(["git", "-C", BRUG, *args], capture_output=True, timeout=timeout)
    return r.returncode, r.stdout


def regelboek():
    """De normcontrole en de checklist van het normenboek zoals ze op GitHub staan (origin/main van de brug), niet de
    werkmap: een half bewerkte versie van een andere sessie raakt de weekronde niet. Geeft (bronnen voor N4, commit,
    pad van de normcontrole in de werkmap, of GitHub bereikt werd)."""
    opgehaald = git("fetch", "-q", "origin", "main")[0] == 0
    code, volledig = git("rev-parse", "origin/main^{commit}", timeout=20)
    if code != 0:
        raise RuntimeError(f"de brug-repo heeft geen origin/main: {BRUG}")
    volledig = volledig.decode().strip()
    commit = volledig[:7]
    bronnen = {}
    for pad in ("gereedschap/normcontrole.py", "kennis/normenboek-B01-checklist.md"):
        # beide bestanden van precies dezelfde commit, niet van de naam origin/main die intussen kan verschuiven (DT19)
        code, inhoud_ = git("show", f"{volledig}:{pad}", timeout=20)
        if code != 0:
            raise RuntimeError(f"{pad} niet in origin/main van de brug")
        bronnen[os.path.basename(pad)] = inhoud_.decode("utf-8")
    bronnen["globaal-vectorworks-brug"] = f"origin/main {commit}{'' if opgehaald else ', GitHub niet bereikt: laatst opgehaald'}"
    map_ = buiten_dropbox(os.path.join(WERKMAP, f"normcontrole-{commit}"))
    nc_pad = os.path.join(map_, "normcontrole.py")
    with open(nc_pad, "w", encoding="utf-8") as f:
        f.write(bronnen["normcontrole.py"])
    return bronnen, commit, nc_pad, opgehaald


def normcontrole(nc_pad):
    spec = importlib.util.spec_from_file_location("normcontrole_tekenaar", nc_pad)
    nc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nc)
    return nc


def beoordeel(nc, pdf, pad):
    """De normcontrole van een blad: oordeel en de bevindingen per soort, zonder inhoud uit het plan."""
    _, map_naam = projectnummer(pad)
    r = nc.controleer_pdf(pdf, naam=os.path.basename(pad), map_naam=map_naam)
    per = {"FOUT": [], "ONBEKEND": [], "LET OP": []}
    for k, v in r["uitkomsten"].items():
        if v["status"] in per:
            per[v["status"]].append(f"{LABEL.get(k, k)}: {v['reden']}")
    fout_reden = {k: v["reden"] for k, v in r["uitkomsten"].items() if v["status"] == "FOUT"}
    return {"oordeel": r.get("oordeel"), "fout": per["FOUT"], "onbekend": per["ONBEKEND"], "let_op": per["LET OP"],
            "fout_soorten": list(fout_reden), "fout_reden": fout_reden}


def onbekend(reden, niet_gecontroleerd=False):
    """Een plan dat niet (volledig) te controleren was. niet_gecontroleerd: te groot of onleesbaar; dat gaat ook naar
    het signaal, want Mehdi moet het zelf bekijken (Codex DT07)."""
    return {"oordeel": "ONBEKEND", "fout": [], "onbekend": [reden], "let_op": [], "fout_soorten": [], "fout_reden": {},
            "niet_gecontroleerd": niet_gecontroleerd}


def set_bevindingen(nc, st, meldingen):
    """Per map met een nieuw blad: de set over alle bekende bladen in die map (bladnummers alleen met een nieuw blad,
    B/V/N bij een regularisatie). Een regularisatie herkent hij ook aan de projectmap ('(reg)', '(regularisatie)'),
    niet alleen aan een V-blad (Codex DT08). Geeft {map: [(soort, reden)]} voor wat FOUT is."""
    mappen = {}
    for m in meldingen:
        mappen.setdefault(os.path.dirname(m["pad"]), set()).add(os.path.basename(m["pad"]))
    uit = {}
    for map_, nieuw in mappen.items():
        namen = [os.path.basename(b["pad"]) for b in st["bekend"].values() if os.path.dirname(b["pad"]) == map_]
        namen = sorted(set(namen) | nieuw)
        regularisatie = nc.is_regularisatie(projectnummer(map_ + "/x.pdf")[1])
        s = nc.controleer_set(namen, regularisatie=regularisatie, nieuw=sorted(nieuw))
        # De reden van een dubbele bladcode noemt volgnummers uit de bestandsnaam; naar het bord gaat ze in algemene
        # woorden (Codex DT35). De reden voor B, V en N komt uit vaste namen (grondplan, gevel ...).
        fout = [(k, "dezelfde bladcode op meer dan een blad in deze map, met een nieuw blad erbij" if k == "bladnummers"
                 else v["reden"]) for k, v in s["uitkomsten"].items() if v["status"] == "FOUT" and k != "gewest"]
        if fout:
            uit[map_] = fout
    return uit


def signaal(meldingen, sets, wk, commit):
    """Een klaarzet-item voor Mehdi (soort signaal) als er een bruikbare bevinding is: een FOUT op een nieuw blad of in
    de set van zijn map. Anders None. Gebundeld per project en per soort fout, met hoogstens drie voorbeelden; de lijst
    per blad staat in het werkverslag. Een fout uit het sjabloon (op bijna elk blad) komt in de titel na de andere.
    Het uniek draagt de week en een vingerafdruk van de gemelde plannen, geen aantal (N10): dezelfde melding twee keer
    klaarzetten (een herhaalde ronde) geeft geen tweede bericht; nieuwe bevindingen wel."""
    projecten, per_project = {}, {}

    def project(nr):
        return projecten.setdefault(nr, {"project": nr, "met_fout": 0, "fouten": {}, "set": [], "na_te_kijken": []})

    for m in meldingen:
        nr = projectnummer(m["pad"])[0]
        per_project[nr] = per_project.get(nr, 0) + 1
    for m in meldingen:
        u = m["uitslag"]
        if u.get("niet_gecontroleerd"):          # DT07: te groot of onleesbaar, Mehdi kijkt het zelf na
            p = project(projectnummer(m["pad"])[0])
            p["na_te_kijken"].append(f"{bladcode(os.path.basename(m['pad']))}: {u['onbekend'][0]}")
        if not u.get("fout_reden"):
            continue
        p = project(projectnummer(m["pad"])[0])
        p["met_fout"] += 1
        for soort, reden in u["fout_reden"].items():
            f = p["fouten"].setdefault(soort, {"wat": LABEL.get(soort, soort), "bladen": 0, "voorbeeld": [], "reden": reden})
            f["bladen"] += 1
            if len(f["voorbeeld"]) < 3:
                f["voorbeeld"].append(bladcode(os.path.basename(m["pad"])))
    labels = map_labels(sets)
    for map_, fout in sets.items():
        p = project(projectnummer(map_ + "/x.pdf")[0])
        p["set"].extend(f"{labels[map_]}: {LABEL.get(k, k)}: {reden}" for k, reden in fout)
        for k, _ in fout:
            p["fouten"].setdefault(k, {"wat": LABEL.get(k, k), "bladen": 0, "voorbeeld": [], "reden": "zie set"})
    if not projecten:
        return None
    gewicht = {}
    for p in projecten.values():
        for k, f in p["fouten"].items():
            gewicht[k] = gewicht.get(k, 0) + max(1, f["bladen"])
    soorten = sorted(gewicht, key=lambda k: (k in SJABLOONFOUT, -gewicht[k], k))
    nrs = sorted(projecten)
    wat = "Normfouten in" if soorten else "Na te kijken:"
    titel = f"{wat} nieuwe BA-plannen van {', '.join(nrs[:4])}{' en meer' if len(nrs) > 4 else ''}"
    extra = f" ({', '.join(LABEL.get(s, s) for s in soorten[:3])})" if soorten else ""
    if len(titel + extra) <= 110:           # De Bode toont 110 tekens op Telegram
        titel += extra
    titel = re.sub(r"(?i)stil", "rustig", titel)   # "stil" in een signaaltitel laat De Bode bellen (AGENTNORM 6)
    # DT14: de inhoud (content_hash) en de bevindingen van elk gemeld plan, niet alleen het Dropbox-id: een gewijzigd
    # blad met dezelfde id en een nieuwe fout krijgt zo in dezelfde week een nieuw signaal.
    vinger = hashlib.sha256(json.dumps(sorted(
        [[m.get("hash") or m["id"], sorted(m["uitslag"].get("fout_reden") or {}), bool(m["uitslag"].get("niet_gecontroleerd"))]
         for m in meldingen if m["uitslag"].get("fout_reden") or m["uitslag"].get("niet_gecontroleerd")])
        + sorted([k, sorted(f for f, _ in v)] for k, v in sets.items()), ensure_ascii=False).encode()).hexdigest()[:8]
    uit = []
    for n in nrs:
        p = projecten[n]
        uit.append({"project": n, "nieuwe_bladen": per_project.get(n, 0),
                    "met_fout": p["met_fout"],
                    "fouten": sorted(p["fouten"].values(), key=lambda f: (f["wat"] in SJABLOONFOUT, -f["bladen"])),
                    "set": p["set"], "na_te_kijken": p["na_te_kijken"][:10]})
    inhoud_ = {"projecten": uit,       # geen week of commit: dezelfde bevindingen geven dezelfde inhoud (DT22)
               "voorstel": ["Per project de bladen met een FOUT verbeteren in een kopie in de Teken-agent-map, "
                            "nooit in de projectmap; Mehdi zegt welk project eerst en geeft vrij."]
               + (["Wat na te kijken is (te groot of onleesbaar), bekijkt Mehdi zelf in het origineel."]
                  if any(p["na_te_kijken"] for p in projecten.values()) else [])
               + [f"{LABEL.get(s, s)}: {VOORSTEL[s]}" for s in soorten if s in VOORSTEL],
               "werkverslag": "de lijst per blad staat in het werkverslag van De Tekenaar op het bord"}
    # DT16: het bord kapt de inhoud af op 60.000 tekens; de laatste projecten gaan dan alleen in het werkverslag.
    weg = 0
    while len(json.dumps(inhoud_, ensure_ascii=False)) > MAX_INHOUD and len(inhoud_["projecten"]) > 1:
        inhoud_["projecten"].pop()
        weg += 1
        inhoud_["meer_projecten"] = f"nog {weg} projecten met een bevinding staan alleen in het werkverslag"
    # Het uniek is de vingerafdruk van alle gemelde plannen (inhoud en bevindingen) en van de volledige signaaltekst,
    # met de redenen van de sets, zonder week en zonder commit: dezelfde melding nooit twee keer, een andere melding
    # altijd een eigen uniek (N10, DT14, DT32).
    vinger = hashlib.sha256(json.dumps(
        {"plannen": sorted([m.get("hash") or m["id"], sorted((m["uitslag"].get("fout_reden") or {}).items()),
                            bool(m["uitslag"].get("niet_gecontroleerd"))] for m in meldingen),
         "titel": titel[:110], "inhoud": inhoud_}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
    return {"voor": "mehdi", "soort": "signaal", "sleutel": wk, "uniek": f"tekenaar-normcontrole-{vinger}",
            "titel": titel[:110], "inhoud": inhoud_}


# ------------------------------------------------------------------ ronde ---
def controleer_wachtrij(nc, st, bewaar=True, maximum=None, haal=None, commit=""):
    """Haalt en controleert de plannen uit de wachtrij, een voor een, en bewaart de stand na elk plan. Elk
    gecontroleerd plan gaat naar te_melden tot het bord werkverslag en signaal bevestigt (Codex DT06). Een plan dat te
    groot of onleesbaar is, wordt een melding 'na te kijken', nooit stil weggelaten (DT07). Geeft het aantal
    verdwenen plannen."""
    haal = haal or haal_van_vm
    maximum = MAX_PER_RONDE if maximum is None else maximum
    werk = tempfile.mkdtemp(prefix="ronde-", dir=buiten_dropbox(WERKMAP))
    verdwenen = 0
    try:
        for ident in verwerkbaar(st)[:maximum]:
            b = st["bekend"].get(ident)
            if b is None or st["gezien"].get(b["hash"], {}).get("status") != "wacht":
                continue
            pdf = os.path.join(werk, "blad.pdf")
            stand = haal(ident, pdf)
            if stand == "weg":
                del st["bekend"][ident]
                verdwenen += 1
            else:
                if stand == "te_groot":
                    uitslag = onbekend("plan groter dan de grens van 80 MB: niet automatisch gecontroleerd, nakijken", True)
                else:
                    try:
                        uitslag = beoordeel(nc, pdf, b["pad"])
                    except Exception as e:  # noqa: BLE001  een kapotte PDF stopt de ronde niet, maar wordt gemeld
                        uitslag = onbekend(f"blad niet te lezen ({type(e).__name__}): nakijken", True)
                    finally:
                        with contextlib.suppress(FileNotFoundError):
                            os.remove(pdf)
                st["gezien"][b["hash"]] = {"status": "gecontroleerd", "oordeel": uitslag["oordeel"],
                                           "fout": uitslag["fout_soorten"], "ts": nu_utc().isoformat(timespec="seconds")}
                st["te_melden"].append({"id": ident, "hash": b["hash"], "pad": b["pad"], "uitslag": uitslag,
                                        "commit": commit})          # DT24: met welke normcontrole gecontroleerd
            herstel_wachtrij(st)
            if bewaar:
                bewaar_stand(st)
    finally:
        shutil.rmtree(werk, ignore_errors=True)
    return verdwenen


def werkverslag(meldingen, sets, blind, merk=""):
    """De regels voor het logboek op het bord: per project de bladen met oordeel en bevindingen, de sets met een fout
    en het aantal mappen zonder toegang. Labels zonder mapnaam of voorwerp-ID (DT10, DT21). Elke regel draagt het
    kenmerk van de melding in het onderwerp, zodat een herhaling ziet wat er al staat (DT15)."""
    per_project = {}
    for m in meldingen:
        per_project.setdefault(projectnummer(m["pad"])[0], []).append(m)
    labels = map_labels(sets)
    kenmerk = f" (verslag {merk})" if merk else ""
    regels = []
    for nr, lijst in sorted(per_project.items()):
        tekst = []
        for m in lijst:
            u = m["uitslag"]
            tekst.append(f"{u['oordeel']}  {blad_label(m['pad'])}")
            tekst += [f"    FOUT {x}" for x in u["fout"]] + [f"    na te kijken: {x}" for x in u["onbekend"]] \
                + [f"    let op: {x}" for x in u["let_op"]]
        for map_, fout in sorted(sets.items()):
            if projectnummer(map_ + "/x.pdf")[0] == nr:
                tekst += [f"set {labels[map_]}: FOUT {LABEL.get(k, k)}: {reden}" for k, reden in fout]
        telling = ", ".join(f"{s} {sum(1 for m in lijst if m['uitslag']['oordeel'] == s)}"
                            for s in ("FOUT", "ONBEKEND", "LET OP", "OK"))
        commits = ", ".join(sorted({m.get("commit") or "onbekend" for m in lijst}))
        # DT13: het bord kapt het detail af op 20.000 tekens; in stukken onder MAX_DETAIL, niets afknippen
        stukken, stuk = [], []
        for lang in tekst:
            for regel in (lang[i:i + MAX_DETAIL] for i in range(0, max(len(lang), 1), MAX_DETAIL)):
                if stuk and len("\n".join(stuk + [regel])) > MAX_DETAIL:
                    stukken.append(stuk)
                    stuk = []
                stuk.append(regel)
        stukken.append(stuk)
        for i, stuk in enumerate(stukken, 1):
            deel = f" (deel {i} van {len(stukken)})" if len(stukken) > 1 else ""
            regels.append({"naam": NAAM, "onderwerp": f"project {nr}{kenmerk}", "stap": "controle",
                           "tekst": f"{len(lijst)} nieuwe of gewijzigde bladen; oordeel: {telling}; normcontrole "
                                    f"{commits}{deel}", "detail": "\n".join(stuk)})
    if blind:
        # Geen nood: of de stack daar mag lezen, is een keuze van Mehdi; een nood zou elke ronde open blijven (N7).
        regels.append({"naam": NAAM, "onderwerp": f"bronnen{kenmerk}", "stap": "bron",
                       "tekst": f"gedeelde mappen zonder toegang voor de koppeling: {len(blind)}; daar ziet De Tekenaar "
                                "geen nieuwe plannen", "detail": ""})
    return regels


def sleutel_van(m):
    return f"{m['id']}@{m.get('hash')}"


def bouw_melding(st, nc, wk, commit):
    """Een uitgaande melding voor wat nu te melden is: signaal en werkverslag, een keer opgebouwd en in de stand
    bewaard. Een herhaling stuurt precies dezelfde melding opnieuw, ook na een weekgrens of met een andere stand van de
    projectmap (Codex DT22, DT26)."""
    meldingen = list(st["te_melden"])[:MAX_PER_MELDING]       # DT29: hoogstens zoveel plannen per melding
    sets = set_bevindingen(nc, st, meldingen)
    item = signaal(meldingen, sets, wk, commit)
    if item:
        item["van"] = NAAM
        item = ag.maskeer(item)
    merk = hashlib.sha256(json.dumps(sorted(sleutel_van(m) for m in meldingen)).encode()).hexdigest()[:8]
    return {"sleutels": [sleutel_van(m) for m in meldingen], "merk": merk, "item": item,
            "regels": ag.maskeer(werkverslag(meldingen, sets, blinde_vlekken(st), merk)), "sets": len(sets)}


def verstuur(melding):
    """Stuurt een melding en leest ze terug. Het signaal: klaarzetten en op zijn uniek teruglezen; titel en volledige
    inhoud moeten kloppen (DT16). Het werkverslag: eerst kijken welke regels met dit kenmerk er al staan, alleen de
    ontbrekende sturen (een verloren antwoord geeft geen dubbel verslag, DT15), en daarna moet elke regel er staan
    (DT13, DT23). Breekt iets, dan een uitzondering: de melding blijft in de stand voor de volgende ronde."""
    item = melding.get("item")
    if item:
        bord.call("/api/klaarzet", {"items": [item]})
        terug = bord.call("/api/klaarzet?" + urllib.parse.urlencode({"uniek": item["uniek"], "status": "alle", "n": 5}))
        rijen = (terug or {}).get("items") or []
        try:
            ontvangen = (rijen[0]["titel"], json.loads(rijen[0]["inhoud"])) if rijen else None
        except (ValueError, KeyError, TypeError):
            ontvangen = None
        if ontvangen != (item["titel"], item["inhoud"]):
            raise RuntimeError("het bord heeft het signaal niet volledig ontvangen")
    schrijf_verslag(melding.get("regels") or [], melding["merk"])


def schrijf_verslag(regels, merk):
    """Werkverslag naar het bord: eerst kijken welke regels met dit kenmerk er al staan, alleen de ontbrekende sturen
    (een verloren antwoord geeft geen dubbel verslag, DT15), en daarna moet elke regel er staan (DT13, DT23)."""
    if not regels:
        return

    def op_het_bord():
        terug = bord.call(f"/api/logboek/{NAAM}?" + urllib.parse.urlencode({"onderwerp": f"(verslag {merk})", "n": 300}))
        return {(r.get("onderwerp"), r.get("tekst"), r.get("detail")) for r in (terug or {}).get("regels") or []}

    ontbrekend = [r for r in regels if (r["onderwerp"], r["tekst"], r["detail"]) not in op_het_bord()]
    if ontbrekend:
        uit = bord.call("/api/logboek", {"regels": ontbrekend})
        if not isinstance(uit, dict) or uit.get("geschreven") != len(ontbrekend):
            raise RuntimeError(f"het bord schreef niet elke regel van het werkverslag: {str(uit)[:100]}")
        staat = op_het_bord()
        if any((r["onderwerp"], r["tekst"], r["detail"]) not in staat for r in regels):
            raise RuntimeError("het werkverslag staat niet volledig op het bord")


def meld(st, nc, wk, commit):
    """Eerst een bewaarde melding die nog niet bevestigd was, dan een nieuwe voor wat er sindsdien bijkwam. Pas na
    bevestiging gaan de plannen uit te_melden (DT06). Geeft (signalen, sets met een fout)."""
    signalen, sets = 0, 0
    for _ in range(50):
        if not st.get("uitgaand"):
            if not st["te_melden"]:
                break
            st["uitgaand"] = bouw_melding(st, nc, wk, commit)
            bewaar_stand(st)
        verstuur(st["uitgaand"])
        klaar = set(st["uitgaand"]["sleutels"])
        signalen += 1 if st["uitgaand"].get("item") else 0
        sets += st["uitgaand"].get("sets", 0)
        st["te_melden"] = [m for m in st["te_melden"] if sleutel_van(m) not in klaar]
        st["uitgaand"] = None
        bewaar_stand(st)
    return signalen, sets


def werk(r, st, wk):
    """Een ronde. Geeft True als alles af is: lijst gelezen, wachtrij leeg en elke melding door het bord bevestigd."""
    nooit, mehdi_beslist = bord.grenzen(r.werkwijze)
    if not nooit or not mehdi_beslist:
        r.nood("Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist", wie="mehdi")
        r.detail = "geen werk gedaan, grenzen ontbreken in de werkwijze"
        return False
    bronnen, commit, nc_pad, opgehaald = regelboek()
    for naam, tekst in bronnen.items():
        r.bron(naam, tekst)
    if hulp_versie() != HULP_VERSIE or bord_stand() is None:
        r.nood("Hulpscript ba_plannen.py of bordstand.py staat niet of in een andere versie op de VM: git pull in "
               "~/appportal", wie="claude-code")
        r.detail = "geen lijst gelezen: een hulpscript op de VM ontbreekt"
        return False
    nc = normcontrole(nc_pad)
    nieuw, weg, _ = bijwerken(st)
    bewaar_stand(st)          # cursor en wachtrij samen: een onderbroken ronde gaat volgende keer verder
    verdwenen = controleer_wachtrij(nc, st, commit=commit)
    meldingen = list(st["te_melden"])
    signalen, sets = meld(st, nc, wk, commit)
    if verwerkbaar(st):
        # DT07: de ronde is niet af; launchd start me morgen opnieuw en dan gaat de wachtrij verder.
        r.nood("Meer nieuwe plannen dan een ronde aankan; de rest volgt bij de volgende start", wie="claude-code")
    tel = {s: sum(1 for m in meldingen if m["uitslag"]["oordeel"] == s) for s in ("FOUT", "ONBEKEND", "LET OP", "OK")}
    blind = blinde_vlekken(st)
    r.detail = (f"week {wk}: {len(meldingen)} nieuwe of gewijzigde BA-plannen gecontroleerd (FOUT {tel['FOUT']}, "
                f"na te kijken {tel['ONBEKEND']}, let op {tel['LET OP']}, OK {tel['OK']}); {sets} sets met een fout; "
                f"{'signaal voor Mehdi' if signalen else 'geen signaal'}; {len(verwerkbaar(st))} in de wachtrij, "
                f"{len(st['wachtrij']) - len(verwerkbaar(st))} wachten op toegang; "
                f"{len(st['bekend'])} plannen in de projectmappen, {nieuw} met nieuwe inhoud, {weg + verdwenen} weg; "
                f"normcontrole origin/main {commit}{'' if opgehaald else ' (GitHub niet bereikt)'}"
                + (f"; gedeelde mappen zonder toegang: {len(blind)}" if blind else ""))
    # DT34: elke ronde een eigen regel in het werkverslag, ook zonder nieuwe plannen, langs dezelfde gecontroleerde weg
    merk = hashlib.sha256(f"{NAAM} {nu_utc().isoformat()}".encode()).hexdigest()[:8]
    schrijf_verslag([ag.maskeer({"naam": NAAM, "onderwerp": f"ronde {wk} (verslag {merk})", "stap": "ronde",
                                 "tekst": r.detail[:1000], "detail": ""})], merk)
    return not verwerkbaar(st)


def aan_de_beurt(st, nu=None):
    """Een ronde is aan de beurt als de vorige gelukte ronde zes dagen oud is, of als er nog plannen of meldingen
    wachten (inhaalronde)."""
    if verwerkbaar(st) or st.get("te_melden") or st.get("uitgaand") or st.get("herhaal") or not st.get("laatste_ronde"):
        return True
    try:
        vorige = datetime.fromisoformat(st["laatste_ronde"])
    except ValueError:
        return True
    return (nu or nu_utc()) - vorige >= RITME


def droog(st, sinds=None):
    """Lijst en controle tonen zonder bord en zonder de stand te bewaren. sinds: een andere basisdatum (alleen hier),
    om de ronde op echte recente plannen te proberen."""
    if hulp_versie() != HULP_VERSIE:
        print("Het hulpscript ba_plannen.py staat niet (of in een andere versie) op de VM: git pull in ~/appportal.")
        return 1
    _, commit, nc_pad, _ = regelboek()
    nc = normcontrole(nc_pad)
    nieuw, weg, lijst = bijwerken(st, basisdatum=f"{sinds}T00:00:00+00:00" if sinds else BASISDATUM)
    tel = {}
    for g in st["gezien"].values():
        tel[g["status"]] = tel.get(g["status"], 0) + 1
    print(f"lijst: {len(lijst.get('wijzigingen', []))} wijzigingen (volledig: {lijst.get('volledig')}); "
          f"{len(st['bekend'])} BA-plannen in de projectmappen, inhoud {tel}; {nieuw} nieuw, {weg} weg; "
          f"wachtrij {len(st['wachtrij'])}; zonder toegang: {blinde_vlekken(st)}; normcontrole {commit}")
    controleer_wachtrij(nc, st, bewaar=False, maximum=int(os.environ.get("TEKENAAR_DROOG_MAX", "20")), commit=commit)
    meldingen = st["te_melden"]
    sets = set_bevindingen(nc, st, meldingen)
    for regel in werkverslag(meldingen, sets, blinde_vlekken(st)):
        print(f"[{regel['onderwerp']}] {regel['tekst']}\n{regel['detail']}")
    item = signaal(meldingen, sets, week(), commit)
    print("signaal:", json.dumps(item, ensure_ascii=False, indent=1) if item else "geen")
    return 0


def ronde_zonder_stand(token, reden):
    """De stand is onleesbaar: geen werk, wel een fout zichtbaar op het bord (hartslag en nood)."""
    with tunnel() as url:
        bord.PLATFORM, bord.TOKEN = url, token
        with ag.ronde("normcontrole nieuwe BA-plannen") as r:
            r.nood("Stand van De Tekenaar onleesbaar; nakijken voor de volgende ronde", wie="claude-code")
            r.detail = f"geen ronde: {reden}"


def main(argv=None):
    p = argparse.ArgumentParser(description="De Tekenaar: wekelijkse normcontrole van nieuwe bouwaanvraagplannen.")
    p.add_argument("--nu", action="store_true", help="een ronde, ook als de vorige net gelukt is")
    p.add_argument("--droog", action="store_true", help="tonen, niets naar het bord, stand ongewijzigd")
    p.add_argument("--sinds", help="alleen met --droog: alles vanaf deze dag (JJJJ-MM-DD) telt als nieuw")
    a = p.parse_args(argv)
    if a.sinds and (not a.droog or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.sinds)):
        p.error("--sinds alleen met --droog, als JJJJ-MM-DD")
    with open(os.path.join(buiten_dropbox(os.path.dirname(STAND)), ".slot"), "w") as slot:
        try:
            fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("er loopt al een ronde")
            return 0
        try:
            st = lees_stand()
        except RuntimeError as e:
            st, stand_fout = None, str(e)
        if a.droog:
            if st is None:
                print(stand_fout)
                return 1
            return droog(lege_stand() if a.sinds else st, a.sinds)
        if st is not None and not a.nu and not aan_de_beurt(st):
            return 0            # de vorige ronde is jonger dan zes dagen; launchd start me dagelijks voor de inhaalronde
        if st is not None:
            # DT18, DT25: een ronde die begint en niet slaagt (ook zonder token), moet de volgende start opnieuw, ook
            # kort na een gelukte ronde
            st["herhaal"] = True
            bewaar_stand(st)
        try:
            token = open(TOKEN_PAD).read().strip()
        except OSError:
            print(f"geen token in {TOKEN_PAD}", file=sys.stderr)
            return 2
        wk = week()
        gelukt = False
        begin = nu_utc()
        try:
            if st is None:
                ronde_zonder_stand(token, stand_fout)
                return 1
            with tunnel() as url:
                bord.PLATFORM, bord.TOKEN = url, token
                with ag.ronde("normcontrole nieuwe BA-plannen") as r:
                    gelukt = werk(r, st, wk)
        except bord.RondeGestopt as e:
            print(f"ronde gestopt: {e}", file=sys.stderr)
            return 1
        except RuntimeError as e:
            if "ssh-tunnel" in str(e):
                hartslag_publiek(token, f"De Mac bereikt de VM niet over ssh; ronde niet gedaan: {e}")
            print(f"ronde mislukt: {e}", file=sys.stderr)
            return 1
        if gelukt:
            # DT09: de gedeelde ronde slikt een mislukte kennis- of hartslagmelding; pas als het bord beide van deze
            # ronde heeft, is ze gedaan. Anders probeert de volgende start het opnieuw.
            ja, waarom = bevestigd(begin)
            if not ja:
                print(f"ronde niet bevestigd door het bord: {waarom}", file=sys.stderr)
                return 1
            st["laatste_week"], st["laatste_ronde"], st["herhaal"] = wk, nu_utc().isoformat(timespec="seconds"), False
            bewaar_stand(st)
        print(f"{datetime.now().isoformat(timespec='seconds')} De Tekenaar: ronde {wk} {'gelukt' if gelukt else 'niet af'}")
        return 0 if gelukt else 1


if __name__ == "__main__":
    sys.exit(main())

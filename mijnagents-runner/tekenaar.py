#!/usr/bin/env python3
"""De Tekenaar (h-architects): elke week een normcontrole van de nieuwe bouwaanvraagplannen. Draait op de Mac van Mehdi.

Waarom op de Mac: daar staat het gereedschap van De Tekenaar (repo globaal-vectorworks-brug, normcontrole.py met
PyMuPDF), naast Vectorworks. Waarom toch via de VM:
  - het bord laat buiten de VM alleen hartslag, klaarzet en logboek door (nginx, 63-mijnagents); de werkwijze, de
    kennis, de noden en de collega's niet. Daarom praat deze runner met het bord via een ssh-tunnel naar
    127.0.0.1:3022 op de VM, zoals de runners daar, met het token uit ~/.config/mijnagents/token. Zo gaat ook deze
    ronde door de gedeelde ag.ronde (N4, N10 tot N14);
  - de Mac heeft geen Dropbox-sleutel en zijn lokale Dropbox toont online-only bestanden als 0 bytes. De lijst en de
    PDF's komen van koppelingen/ba_plannen.py op de VM (ssh, zoals mac/hotmail_koppen.py), met de sleutel van de stack.

launchd (mac/be.globaal.mijnagents.tekenaar.plist) start hem elke dag om 10:00 en bij het aanmelden. Hij werkt alleen
als de ronde van deze week nog niet gelukt is: zo haalt hij een week in die de Mac verslapen heeft, en geeft hij elke
week een hartslag, ook zonder nieuwe plannen (N11).

    tekenaar.py            de ronde van deze week, als die nog niet gelukt is
    tekenaar.py --nu       een ronde, ook als deze week al gelukt is
    tekenaar.py --droog    lijst en controle tonen; niets naar het bord, de stand blijft gelijk
    tekenaar.py --droog --sinds 2026-10-05   idem, alsof alles vanaf die dag nieuw is (proef op echte plannen)

Hij leest alleen. Hij schrijft niets in Dropbox: de PDF's gaan naar een werkmap buiten Dropbox en worden na de controle
gewist; zijn stand (wat al bekeken is) staat in ~/Library/Application Support/mijnagents/tekenaar/.
"""
import argparse
import contextlib
import fcntl
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone

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
HULP_VERSIE = "2"
# De archiefcontrole van oktober 2026 (overleg/archiefcontrole-2026-10.md in de brug) mat alles tot 18-10-2026: wat
# daarvoor laatst gewijzigd is, telt als bekeken. Zo bouwt de eerste ronde daarop voort in plaats van alles opnieuw.
BASISDATUM = "2026-10-18T00:00:00+00:00"
MAX_PER_RONDE = 150
ID = re.compile(r"^id:[A-Za-z0-9_-]{6,}$")
BASISMAPPEN = ("0 H-A Standaard projects", "0 H-A Light projects")

# Wat een fout betekent en wat De Tekenaar voorstelt; het besluit blijft bij Mehdi (werkwijze, "Wat Mehdi beslist").
LABEL = {"meetlijn": "meetlijn", "persoonsgegevens": "persoonsgegevens", "eenheid": "eenheid", "schaal": "schaal",
         "bestandsnaam": "bestandsnaam", "voorwerp_id": "voorwerp-ID", "gewest": "gewest", "noordpijl": "noordpijl",
         "ruimtefuncties": "ruimtebenamingen", "snede_aangeduid": "plaats van de snede", "maataanduiding": "maatcijfers",
         "toestanden": "toestanden B, V en N", "bladnummers": "dubbele bladcode", "dxf_maten": "maten DXF"}
VOORSTEL = {
    "meetlijn": "schaalbalk laten volgen met de schaal van het blad (sjabloonherstel in de TODO van De Tekenaar)",
    "persoonsgegevens": "titelblok zonder bouwheer en rijksregisternummer opnieuw afdrukken (besluit 18-10-2026)",
    "eenheid": "de eenheid (maten in centimeter) op het blad zetten",
    "schaal": "een normschaal vermelden (1/50, 1/100, 1/200 ...)",
    "bestandsnaam": "de naam volgens de loketcodering zetten voor het indienen",
    "gewest": "het normenboek B01 niet toepassen; Mehdi beslist welke regels gelden",
    "toestanden": "de vergunde toestand toevoegen of de samenvoeging uitdrukkelijk melden",
    "bladnummers": "de volgnummers herschikken zodat elke bladcode een keer voorkomt",
}


def nu_utc():
    return datetime.now(timezone.utc)


def week(t=None):
    j, w, _ = (t or datetime.now().astimezone()).isocalendar()
    return f"{j}-W{w:02d}"


# ------------------------------------------------------------------ stand ---
def lege_stand():
    """bekend: de BA-plannen die nu in de projectmappen staan, per Dropbox-id (pad en inhoud), voor de set-controle.
    gezien: elke inhoud (content_hash) die De Tekenaar al kent: basis (archiefcontrole), wacht of gecontroleerd. Nieuw
    is een inhoud die hij nog niet zag; een kopie of een verplaatst plan (een project dat van fasemap verandert) niet."""
    return {"versie": 1, "cursors": {}, "bekend": {}, "gezien": {}, "wachtrij": [], "geen_toegang": {},
            "laatste_week": None, "laatste_ronde": None}


def lees_stand(pad=None):
    pad = pad or STAND
    try:
        with open(pad, encoding="utf-8") as f:
            st = json.load(f)
    except FileNotFoundError:
        return lege_stand()
    if not isinstance(st, dict) or st.get("versie") != 1 or not all(
            isinstance(st.get(k), t) for k, t in (("bekend", dict), ("gezien", dict), ("wachtrij", list), ("cursors", dict))):
        raise RuntimeError(f"stand onleesbaar: {pad}")
    return st


def bewaar_stand(st, pad=None):
    """Atomair: eerst een tijdelijk bestand ernaast, dan os.replace, zodat een onderbroken ronde nooit een halve stand
    achterlaat."""
    pad = pad or STAND
    os.makedirs(os.path.dirname(pad), mode=0o700, exist_ok=True)
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


def selecteer(st, lijst, basisdatum=BASISDATUM):
    """Verwerkt de wijzigingen van ba_plannen.py in de stand, in de volgorde van Dropbox. Een plan is nieuw als De
    Tekenaar zijn inhoud nog niet zag. Bij de allereerste lijst telt een plan dat voor de basisdatum laatst gewijzigd
    is als bekeken (archiefcontrole van oktober 2026). Geeft (nieuw, weg)."""
    eerste = not st["gezien"]
    bekend, gezien, wacht = st["bekend"], st["gezien"], st["wachtrij"]
    nieuw = weg = 0
    for w in lijst.get("wijzigingen", []):
        if w.get("soort") == "weg":
            p = (w.get("pad") or "").lower()
            for i, b in list(bekend.items()):
                q = (b.get("pad") or "").lower()
                if p and (q == p or q.startswith(p + "/")):
                    del bekend[i]
                    weg += 1
            continue
        if w.get("soort") != "bestand" or not ID.match(w.get("id") or "") \
                or not is_ba_pdf(os.path.basename(w.get("pad") or "")):
            continue
        sleutel = inhoud(w)
        bekend[w["id"]] = {"hash": sleutel, "pad": w["pad"]}
        if sleutel in gezien:
            continue
        if eerste and (w.get("gewijzigd") or "") and w["gewijzigd"].replace("Z", "+00:00") < basisdatum:
            gezien[sleutel] = {"status": "basis"}
            continue
        gezien[sleutel] = {"status": "wacht", "gewijzigd": w.get("gewijzigd")}
        wacht.append(w["id"])
        nieuw += 1
    herstel_wachtrij(st)
    st["cursors"].update(lijst.get("cursors") or {})
    # Gedeelde mappen zonder toegang voor de stack: alleen een volledige lijst ziet ze, en die vervangt wat er stond.
    toegang = st.setdefault("geen_toegang", {})
    for basis, volledig in (lijst.get("volledig") or {}).items():
        if volledig:
            toegang[basis] = sorted(g["pad"] for g in lijst.get("geen_toegang", []) if g.get("basis") == basis)
    return nieuw, weg


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


def projectnummer(pad):
    """Het projectnummer: de eerste map onder de fasemap die met vier cijfers begint; anders 'zonder nummer'."""
    delen = (pad or "").split("/")
    for i, d in enumerate(delen):
        if d in BASISMAPPEN:
            for x in delen[i + 1:-1]:
                m = re.match(r"^(\d{4})\b", x)
                if m:
                    return m.group(1), x
            break
    return "zonder nummer", os.path.basename(os.path.dirname(pad or ""))


def kort_pad(pad):
    """Het pad vanaf de projectmappen, zodat Mehdi het bestand terugvindt."""
    for b in BASISMAPPEN:
        if "/" + b + "/" in pad:
            return pad.split("/" + b + "/", 1)[1]
    return pad


# ----------------------------------------------------------- VM via ssh ---
def vm(opdracht, invoer=None, timeout=600):
    """Een opdracht van ba_plannen.py op de VM. Geeft (code, stdout als bytes, stderr). Een gedeelde ssh-verbinding
    (ControlMaster, een minuut open na de laatste opdracht) houdt honderd plannen in een ronde onder de paar minuten."""
    os.makedirs(WERKMAP, mode=0o700, exist_ok=True)
    r = subprocess.run(["/usr/bin/ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=30",
                        "-o", "ControlMaster=auto", "-o", f"ControlPath={os.path.join(WERKMAP, 's-%C')}",
                        "-o", "ControlPersist=60", VM, f"{HULP} {opdracht}"],
                       input=invoer, capture_output=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr.decode("utf-8", "replace").strip()[-300:]


def hulp_versie():
    code, uit, fout = vm("versie", timeout=60)
    return uit.decode().strip() if code == 0 else None


def lijst_van_vm(cursors):
    code, uit, fout = vm("lijst", json.dumps({"cursors": cursors}).encode(), timeout=1800)
    if code != 0:
        raise RuntimeError(f"lijst van de VM mislukt (code {code}): {fout}")
    return json.loads(uit.decode("utf-8"))


def haal_van_vm(ident, doel):
    """Schrijft de PDF naar doel. Geeft True, of False als Dropbox het bestand niet (meer) als BA-plan kent."""
    if not ID.match(ident):
        raise ValueError("geen Dropbox-id")
    code, uit, fout = vm(f"haal {ident}", timeout=300)
    if code == 4 or (code == 1 and ("PermissionError" in fout or "geen BA-plan" in fout)):
        return False
    if code != 0 or not uit.startswith(b"%PDF"):
        raise RuntimeError(f"ophalen van een plan mislukt (code {code}): {fout}")
    with open(doel, "wb") as f:
        f.write(uit)
    return True


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
def normcontrole():
    pad = os.path.join(BRUG, "gereedschap")
    if pad not in sys.path:
        sys.path.insert(0, pad)
    import normcontrole as nc  # noqa: PLC0415
    return nc


def regelboek():
    """Wat De Tekenaar deze ronde toepast, naast zijn werkwijze op het bord: de normcontrole en de checklist van het
    normenboek, met de commit van de brug (N4)."""
    bronnen = {}
    for naam in ("gereedschap/normcontrole.py", "kennis/normenboek-B01-checklist.md"):
        with open(os.path.join(BRUG, naam), encoding="utf-8") as f:
            bronnen[os.path.basename(naam)] = f.read()
    try:
        commit = subprocess.run(["git", "-C", BRUG, "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                timeout=20).stdout.strip()
        vuil = subprocess.run(["git", "-C", BRUG, "status", "--porcelain", "--", "gereedschap", "kennis"],
                              capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit, vuil = "", ""
    bronnen["globaal-vectorworks-brug"] = f"commit {commit or 'onbekend'}{', met lokale wijzigingen' if vuil else ''}"
    return bronnen, commit, bool(vuil)


def beoordeel(nc, pdf, pad):
    """De normcontrole van een blad: oordeel en de bevindingen per soort, zonder inhoud uit het plan."""
    nr, map_naam = projectnummer(pad)
    r = nc.controleer_pdf(pdf, naam=os.path.basename(pad), map_naam=map_naam)
    per = {"FOUT": [], "ONBEKEND": [], "LET OP": []}
    for k, v in r["uitkomsten"].items():
        if v["status"] in per:
            per[v["status"]].append(f"{LABEL.get(k, k)}: {v['reden']}")
    fout_reden = {k: v["reden"] for k, v in r["uitkomsten"].items() if v["status"] == "FOUT"}
    return {"oordeel": r.get("oordeel"), "fout": per["FOUT"], "onbekend": per["ONBEKEND"], "let_op": per["LET OP"],
            "fout_soorten": list(fout_reden), "fout_reden": fout_reden}


def set_bevindingen(nc, st, nieuwe_ids):
    """Per map met een nieuw blad: de set over alle bekende bladen in die map (bladnummers alleen met een nieuw blad,
    B/V/N bij een regularisatie). Geeft {map: [bevinding, ...]} voor wat FOUT is."""
    mappen = {}
    for i in nieuwe_ids:
        b = st["bekend"].get(i)
        if b:
            mappen.setdefault(os.path.dirname(b["pad"]), set()).add(os.path.basename(b["pad"]))
    uit = {}
    for m, nieuw in mappen.items():
        namen = [os.path.basename(b["pad"]) for b in st["bekend"].values() if os.path.dirname(b["pad"]) == m]
        s = nc.controleer_set(namen, nieuw=sorted(nieuw))
        fout = [(k, v["reden"]) for k, v in s["uitkomsten"].items() if v["status"] == "FOUT" and k != "gewest"]
        if fout:
            uit[m] = fout
    return uit


def signaal(gecontroleerd, sets, wk, commit):
    """Een klaarzet-item voor Mehdi (soort signaal) als er een bruikbare bevinding is: een FOUT op een nieuw blad of in
    de set van zijn map. Anders None. Gebundeld per project en per soort fout, met hoogstens drie voorbeelden; de lijst
    per blad staat in het werkverslag. Het uniek draagt de week, geen aantal (N10): een herhaalde ronde in dezelfde
    week zet niets dubbel klaar. LET OP en na te kijken blijven in het werkverslag."""
    projecten = {}

    def project(nr):
        return projecten.setdefault(nr, {"project": nr, "mappen": set(), "met_fout": 0, "fouten": {}, "set": []})

    per_project = {}
    for pad, _ in gecontroleerd:
        nr = projectnummer(pad)[0]
        per_project[nr] = per_project.get(nr, 0) + 1
    for pad, uitslag in gecontroleerd:
        if not uitslag.get("fout"):
            continue
        p = project(projectnummer(pad)[0])
        p["met_fout"] += 1
        p["mappen"].add(kort_pad(os.path.dirname(pad)))
        for soort, reden in (uitslag.get("fout_reden") or {}).items():
            f = p["fouten"].setdefault(soort, {"wat": LABEL.get(soort, soort), "bladen": 0, "voorbeeld": [], "reden": reden})
            f["bladen"] += 1
            if len(f["voorbeeld"]) < 3:
                f["voorbeeld"].append(os.path.basename(pad))
    for m, fout in sets.items():
        p = project(projectnummer(m + "/x.pdf")[0])
        p["mappen"].add(kort_pad(m))
        p["set"].extend(f"{LABEL.get(k, k)}: {reden}" for k, reden in fout)
        for k, _ in fout:
            p["fouten"].setdefault(k, {"wat": LABEL.get(k, k), "bladen": 0, "voorbeeld": [], "reden": "zie set"})
    if not projecten:
        return None
    gewicht = {}
    for p in projecten.values():
        for k, f in p["fouten"].items():
            gewicht[k] = gewicht.get(k, 0) + max(1, f["bladen"])
    soorten = sorted(gewicht, key=lambda k: (-gewicht[k], k))     # de meest voorkomende fout eerst
    nrs = sorted(projecten)
    titel = f"Normfouten in nieuwe BA-plannen van {', '.join(nrs[:4])}{' en meer' if len(nrs) > 4 else ''}"
    extra = f" ({', '.join(LABEL.get(s, s) for s in soorten[:3])})"
    if len(titel + extra) <= 110:           # De Bode toont 110 tekens op Telegram
        titel += extra
    titel = re.sub(r"(?i)stil", "rustig", titel)   # "stil" in een signaaltitel laat De Bode bellen (AGENTNORM 6)
    uit = []
    for n in nrs:
        p = projecten[n]
        uit.append({"project": n, "mappen": sorted(p["mappen"])[:3], "nieuwe_bladen": per_project.get(n, 0),
                    "met_fout": p["met_fout"], "fouten": sorted(p["fouten"].values(), key=lambda f: -f["bladen"]),
                    "set": p["set"]})
    return {"voor": "mehdi", "soort": "signaal", "sleutel": wk, "uniek": f"tekenaar-normcontrole-{wk}",
            "titel": titel[:110],
            "inhoud": {"week": wk, "projecten": uit,
                       "voorstel": ["Per project de bladen met een FOUT verbeteren in een kopie in de Teken-agent-map, "
                                    "nooit in de projectmap; Mehdi zegt welk project eerst en geeft vrij."]
                       + [f"{LABEL.get(s, s)}: {VOORSTEL[s]}" for s in soorten if s in VOORSTEL],
                       "werkverslag": "de lijst per blad staat in het werkverslag van De Tekenaar op het bord",
                       "regelboek": f"normcontrole uit globaal-vectorworks-brug, commit {commit or 'onbekend'}"}}


# ------------------------------------------------------------------ ronde ---
def veilige_werkmap():
    """Een eigen tijdelijke map buiten Dropbox: De Tekenaar schrijft nooit in een projectmap."""
    os.makedirs(WERKMAP, mode=0o700, exist_ok=True)
    werk = tempfile.mkdtemp(prefix="ronde-", dir=WERKMAP)
    if os.path.realpath(werk).startswith(os.path.realpath(DROPBOX) + os.sep):
        shutil.rmtree(werk, ignore_errors=True)
        raise RuntimeError("werkmap ligt in Dropbox; geweigerd")
    return werk


def controleer_wachtrij(nc, st, bewaar=True, maximum=MAX_PER_RONDE, haal=None):
    """Haalt en controleert de plannen uit de wachtrij, een voor een, en bewaart de stand na elk plan. Geeft
    (gecontroleerd: [(pad, uitslag)], ids van de gecontroleerde plannen, aantal verdwenen)."""
    haal = haal or haal_van_vm
    werk = veilige_werkmap()
    gecontroleerd, ids, verdwenen = [], [], 0
    try:
        for ident in list(st["wachtrij"])[:maximum]:
            b = st["bekend"].get(ident)
            if b is None or st["gezien"].get(b["hash"], {}).get("status") != "wacht":
                continue
            pdf = os.path.join(werk, "blad.pdf")
            if not haal(ident, pdf):
                del st["bekend"][ident]          # Dropbox kent het niet meer als BA-plan in de projectmappen
                verdwenen += 1
            else:
                try:
                    uitslag = beoordeel(nc, pdf, b["pad"])
                except Exception as e:  # noqa: BLE001  een kapotte PDF stopt de ronde niet
                    uitslag = {"oordeel": "ONBEKEND", "fout": [], "onbekend": [f"blad niet te lezen: {type(e).__name__}"],
                               "let_op": [], "fout_soorten": [], "fout_reden": {}}
                finally:
                    with contextlib.suppress(FileNotFoundError):
                        os.remove(pdf)
                st["gezien"][b["hash"]] = {"status": "gecontroleerd", "oordeel": uitslag["oordeel"],
                                           "fout": uitslag["fout_soorten"], "ts": nu_utc().isoformat(timespec="seconds")}
                gecontroleerd.append((b["pad"], uitslag))
                ids.append(ident)
            herstel_wachtrij(st)
            if bewaar:
                bewaar_stand(st)
    finally:
        shutil.rmtree(werk, ignore_errors=True)
    return gecontroleerd, ids, verdwenen


def werk(r, st, wk):
    nooit, mehdi_beslist = bord.grenzen(r.werkwijze)
    if not nooit or not mehdi_beslist:
        r.nood("Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist", wie="mehdi")
        r.detail = "geen werk gedaan, grenzen ontbreken in de werkwijze"
        return False
    bronnen, commit, vuil = regelboek()
    for naam, inhoud in bronnen.items():
        r.bron(naam, inhoud)
    if hulp_versie() != HULP_VERSIE:
        r.nood("Hulpscript ba_plannen.py staat niet of in een andere versie op de VM: git pull in ~/appportal",
               wie="claude-code")
        r.detail = "geen lijst gelezen: het hulpscript op de VM ontbreekt"
        return False
    nc = normcontrole()
    lijst = lijst_van_vm(st["cursors"])
    nieuw, weg = selecteer(st, lijst)
    bewaar_stand(st)          # cursor en wachtrij samen: een onderbroken ronde gaat volgende keer verder
    gecontroleerd, ids, verdwenen = controleer_wachtrij(nc, st)
    sets = set_bevindingen(nc, st, ids)
    tel = {s: sum(1 for _, u in gecontroleerd if u["oordeel"] == s) for s in ("FOUT", "ONBEKEND", "LET OP", "OK")}
    per_project = {}
    for pad, u in gecontroleerd:
        per_project.setdefault(projectnummer(pad)[0], []).append((pad, u))
    for nr, bladen in sorted(per_project.items()):
        regels = []
        for pad, u in bladen:
            regels.append(f"{u['oordeel']}  {kort_pad(pad)}")
            regels += [f"    FOUT {x}" for x in u["fout"]] + [f"    na te kijken: {x}" for x in u["onbekend"]] \
                + [f"    let op: {x}" for x in u["let_op"]]
        for m, fout in sets.items():
            if projectnummer(m + "/x.pdf")[0] == nr:
                regels += [f"set {kort_pad(m)}: FOUT {LABEL.get(k, k)}: {reden}" for k, reden in fout]
        ag.log(f"project {nr}", "controle", f"{len(bladen)} nieuwe of gewijzigde bladen; oordeel: "
               + ", ".join(f"{s} {sum(1 for _, u in bladen if u['oordeel'] == s)}" for s in ("FOUT", "ONBEKEND", "LET OP", "OK")),
               "\n".join(regels))
    blind = blinde_vlekken(st)
    if blind:
        # Geen nood: of de stack daar mag lezen, is een keuze van Mehdi; een nood zou elke ronde open blijven (N7).
        ag.log(f"week {wk}", "bron", "mappen zonder toegang voor de stack: daar ziet De Tekenaar geen nieuwe plannen",
               "\n".join(kort_pad(p) for p in blind))
    item = signaal(gecontroleerd, sets, wk, commit)
    if item:
        uit = ag.klaarzet([item])
        ag.log(f"week {wk}", "signaal", f"signaal voor Mehdi klaargezet ({uit.get('nieuw', 0)} nieuw)", item["titel"])
    if st["wachtrij"]:
        r.nood("Meer nieuwe plannen dan een ronde aankan; de rest volgt in de volgende ronde", wie="claude-code")
    if vuil:
        r.nood("Normcontrole draait met lokale wijzigingen in de brug-repo: committen en pushen", wie="claude-code")
    r.detail = (f"week {wk}: {len(gecontroleerd)} nieuwe of gewijzigde BA-plannen gecontroleerd (FOUT {tel['FOUT']}, "
                f"na te kijken {tel['ONBEKEND']}, let op {tel['LET OP']}, OK {tel['OK']}); {len(sets)} sets met een fout; "
                f"{'een signaal voor Mehdi' if item else 'geen signaal'}; {len(st['wachtrij'])} in de wachtrij; "
                f"{len(st['bekend'])} plannen in de projectmappen, {nieuw} met nieuwe inhoud, {weg + verdwenen} weg; "
                f"normcontrole {commit or 'onbekend'}"
                + (f"; niet leesbaar: {', '.join(kort_pad(p) for p in blind)}" if blind else ""))
    return True


def droog(st, sinds=None):
    """Lijst en controle tonen zonder bord en zonder de stand te bewaren. sinds: een andere basisdatum (alleen hier),
    om de ronde op echte recente plannen te proberen."""
    if hulp_versie() != HULP_VERSIE:
        print("Het hulpscript ba_plannen.py staat niet (of in een andere versie) op de VM: git pull in ~/appportal.")
        return 1
    nc = normcontrole()
    lijst = lijst_van_vm(st["cursors"])
    nieuw, weg = selecteer(st, lijst, basisdatum=f"{sinds}T00:00:00+00:00" if sinds else BASISDATUM)
    tel = {}
    for g in st["gezien"].values():
        tel[g["status"]] = tel.get(g["status"], 0) + 1
    print(f"lijst: {len(lijst.get('wijzigingen', []))} wijzigingen (volledig: {lijst.get('volledig')}); "
          f"{len(st['bekend'])} BA-plannen in de projectmappen, inhoud {tel}; {nieuw} nieuw, {weg} weg; "
          f"wachtrij {len(st['wachtrij'])}; zonder toegang: {blinde_vlekken(st)}")
    gecontroleerd, ids, verdwenen = controleer_wachtrij(nc, st, bewaar=False, maximum=int(os.environ.get("TEKENAAR_DROOG_MAX", "20")))
    for pad, u in gecontroleerd:
        print(f"{u['oordeel']:8} {projectnummer(pad)[0]}  {os.path.basename(pad)}")
        for x in u["fout"]:
            print(f"         FOUT {x}")
    sets = set_bevindingen(nc, st, ids)
    for m, fout in sets.items():
        print(f"set {kort_pad(m)}: {fout}")
    item = signaal(gecontroleerd, sets, week(), "droog")
    print("signaal:", json.dumps(item, ensure_ascii=False, indent=1) if item else "geen")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="De Tekenaar: wekelijkse normcontrole van nieuwe bouwaanvraagplannen.")
    p.add_argument("--nu", action="store_true", help="een ronde, ook als deze week al gelukt is")
    p.add_argument("--droog", action="store_true", help="tonen, niets naar het bord, stand ongewijzigd")
    p.add_argument("--sinds", help="alleen met --droog: alles vanaf deze dag (JJJJ-MM-DD) telt als nieuw")
    a = p.parse_args(argv)
    if a.sinds and (not a.droog or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.sinds)):
        p.error("--sinds alleen met --droog, als JJJJ-MM-DD")
    os.makedirs(os.path.dirname(STAND), mode=0o700, exist_ok=True)
    with open(os.path.join(os.path.dirname(STAND), ".slot"), "w") as slot:
        try:
            fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("er loopt al een ronde")
            return 0
        st = lees_stand()
        if a.droog:
            return droog(lege_stand() if a.sinds else st, a.sinds)
        wk = week()
        if st.get("laatste_week") == wk and not a.nu:
            return 0            # de ronde van deze week is al gelukt; launchd start me dagelijks voor de inhaalronde
        try:
            token = open(TOKEN_PAD).read().strip()
        except OSError:
            print(f"geen token in {TOKEN_PAD}", file=sys.stderr)
            return 2
        try:
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
            st["laatste_week"], st["laatste_ronde"] = wk, nu_utc().isoformat(timespec="seconds")
            bewaar_stand(st)
        print(f"{datetime.now().isoformat(timespec='seconds')} De Tekenaar: ronde {wk} {'gelukt' if gelukt else 'met nood'}")
        return 0 if gelukt else 1


if __name__ == "__main__":
    sys.exit(main())

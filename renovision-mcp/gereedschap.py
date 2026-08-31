"""Het gereedschap dat Claude in een RenoVision-werkruimte kan gebruiken.

Lezen en zoeken, code wijzigen, vastleggen in git, uitrollen en logs bekijken.
Elke functie krijgt de werkruimte van de ingelogde gebruiker mee en kan daar
niet buiten -- de begrenzing zit in `werkruimte.py`.

De teruggaven zijn gewone dicts; `mcp_server.py` maakt er JSON van. Fouten die
de gebruiker moet lezen worden als `Geweigerd` gegooid en komen als tekst
terug, niet als een protocolfout.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time

import werkruimte as wr
from werkruimte import Geweigerd, Werkruimte

MAX_TREFFERS = 200        # regels in een zoekresultaat
MAX_REGELS = 2000         # regels in een keer lezen
MAX_LOG = 400             # regels containerlog

# Een bouw op deze VM (2 vCPU) kost minuten en trekt de machine leeg. Boven
# deze belasting beginnen we er niet aan: in augustus 2026 lag het platform
# zeven minuten plat toen er te veel tegelijk draaide.
MAX_BELASTING = float(os.environ.get("RENOVISION_MAX_BELASTING", "25"))

# Bouwen doet er hooguit een tegelijk, over alle werkruimtes heen.
_bouwslot = threading.Lock()
_uitrol: dict[str, dict] = {}
_uitrol_slot = threading.Lock()


def _belasting() -> float:
    return os.getloadavg()[0]


# ---- Lezen ----------------------------------------------------------------
def werkruimte_info(ws: Werkruimte) -> dict:
    """Waar ben ik, wat staat er open, en draait het."""
    tak = wr.huidige_tak(ws)
    open_ = [r for r in wr.git(ws, "status", "--porcelain",
                               "--", "backend", "frontend", "tests"
                               ).splitlines() if r.strip()]
    try:
        voor = wr.git(ws, "rev-list", "--count", f"main..{tak}").strip()
    except Geweigerd:
        voor = "0"

    diensten = []
    r = subprocess.run(
        ["docker", "compose", "ps", "--format", "{{.Service}}\t{{.State}}"],
        cwd=ws.map, capture_output=True, text=True, timeout=60)
    for regel in r.stdout.splitlines():
        if "\t" in regel:
            dienst, staat = regel.split("\t", 1)
            diensten.append({"dienst": dienst, "staat": staat})

    uit = {
        "werkruimte": ws.naam,
        "app": ws.url,
        "tak": tak,
        "commits_op_je_tak": int(voor or 0),
        "bestanden_met_open_wijzigingen": len(open_),
        "containers": diensten,
        "uitrol": uitrol_stand(ws),
        "belasting_vm": round(_belasting(), 1),
    }
    if ws.autodeploy:
        uit["let_op"] = (
            f"Deze werkruimte staat onder {ws.autodeploy} en wordt elke twee "
            "minuten teruggezet op de versie uit GitHub. Wijzigen is daarom "
            "uitgeschakeld tot de beheerder die timer uitzet.")
    if not any(d["dienst"] == "mongo" for d in diensten):
        uit["let_op_database"] = (
            "Er draait geen mongo-container; de app kan zijn database niet "
            "bereiken en geeft fouten. 'uitrollen' start hem alsnog.")
    return uit


def bestanden(ws: Werkruimte, patroon: str = "") -> dict:
    """De bestanden van de app, eventueel gefilterd op een deel van het pad."""
    alles = wr.getrackte_bestanden(ws)
    p = (patroon or "").strip().lower()
    lijst = [b for b in alles if p in b.lower()] if p else alles
    return {"aantal": len(lijst), "van_totaal": len(alles), "bestanden": lijst}


def lees(ws: Werkruimte, pad: str, vanaf: int = 1, aantal: int = 0) -> dict:
    """Een bestand lezen, met regelnummers. Grote bestanden in stukken."""
    doel = wr.veilig_pad(ws, pad)
    rel = wr.relatief(ws, doel)
    if not wr.leesbaar(rel):
        raise Geweigerd(
            ".env bevat de API-sleutel en is afgeschermd. De instelbare "
            "waarden staan in .env.example.")
    if not doel.is_file():
        raise Geweigerd(f"'{rel}' bestaat niet. Zoek het met 'bestanden'.")
    ruw = doel.read_bytes()
    if b"\x00" in ruw[:8000]:
        raise Geweigerd(f"'{rel}' is geen tekstbestand.")
    regels = ruw.decode("utf-8", errors="replace").splitlines()

    vanaf = max(1, int(vanaf or 1))
    aantal = int(aantal or 0) or MAX_REGELS
    aantal = min(aantal, MAX_REGELS)
    deel = regels[vanaf - 1: vanaf - 1 + aantal]
    genummerd = "\n".join(f"{vanaf + i}\t{r}" for i, r in enumerate(deel))
    uit = {"pad": rel, "regels_totaal": len(regels),
           "getoond": f"{vanaf}-{vanaf + len(deel) - 1}" if deel else "leeg",
           "inhoud": genummerd}
    if vanaf - 1 + len(deel) < len(regels):
        uit["meer"] = (f"Nog {len(regels) - (vanaf - 1 + len(deel))} regels; "
                       f"lees verder met vanaf={vanaf + len(deel)}.")
    return uit


def zoek(ws: Werkruimte, patroon: str, bestanden_: str = "",
         hoofdletters: bool = False) -> dict:
    """Zoeken door de code met een reguliere expressie (via git grep)."""
    if not (patroon or "").strip():
        raise Geweigerd("Geef een zoekpatroon op.")
    args = ["grep", "-n", "-I", "--no-color"]
    if not hoofdletters:
        args.append("-i")
    args += ["-E", "-e", patroon]
    if (bestanden_ or "").strip():
        args += ["--", bestanden_.strip()]
    r = subprocess.run(["git", *args], cwd=ws.map, capture_output=True,
                       text=True, timeout=120)
    if r.returncode not in (0, 1):
        raise Geweigerd(f"Zoeken lukte niet: {r.stderr.strip()}")
    treffers = [t for t in r.stdout.splitlines() if wr.leesbaar(t.split(":", 1)[0])]
    uit = {"patroon": patroon, "treffers": len(treffers),
           "resultaat": treffers[:MAX_TREFFERS]}
    if len(treffers) > MAX_TREFFERS:
        uit["ingekort"] = (f"Alleen de eerste {MAX_TREFFERS} van "
                           f"{len(treffers)} regels; maak het patroon strakker.")
    return uit


# ---- Schrijven ------------------------------------------------------------
def schrijf(ws: Werkruimte, pad: str, inhoud: str) -> dict:
    """Een bestand volledig schrijven (nieuw of vervangen)."""
    doel, rel = wr.controleer_schrijfbaar(ws, pad)
    if not isinstance(inhoud, str):
        raise Geweigerd("inhoud moet tekst zijn.")
    if len(inhoud) > wr.MAX_SCHRIJF:
        raise Geweigerd(f"Te groot ({len(inhoud)} tekens); "
                        f"maximaal {wr.MAX_SCHRIJF}.")
    wr.zorg_voor_werktak(ws)
    bestond = doel.is_file()
    doel.parent.mkdir(parents=True, exist_ok=True)
    doel.write_text(inhoud, encoding="utf-8")
    return {"pad": rel, "actie": "vervangen" if bestond else "aangemaakt",
            "regels": inhoud.count("\n") + 1,
            "volgende_stap": "Leg het vast met 'vastleggen' en zet het daarna "
                             "live met 'uitrollen'."}


def vervang(ws: Werkruimte, pad: str, oud: str, nieuw: str,
            alles: bool = False) -> dict:
    """Een exact stuk tekst in een bestand vervangen.

    Moet uniek zijn, tenzij `alles`. Zo verandert er nooit per ongeluk een
    tweede plek die toevallig hetzelfde leest.
    """
    doel, rel = wr.controleer_schrijfbaar(ws, pad)
    if not doel.is_file():
        raise Geweigerd(f"'{rel}' bestaat niet.")
    if not isinstance(oud, str) or oud == "":
        raise Geweigerd("Geef in 'oud' de tekst die vervangen moet worden.")
    if not isinstance(nieuw, str):
        raise Geweigerd("nieuw moet tekst zijn.")
    tekst = doel.read_text(encoding="utf-8", errors="replace")
    aantal = tekst.count(oud)
    if aantal == 0:
        raise Geweigerd(
            f"Die tekst staat niet in '{rel}'. Let op inspringing en "
            "regeleinden; lees het bestand eerst met 'lees'.")
    if aantal > 1 and not alles:
        raise Geweigerd(
            f"Die tekst staat {aantal} keer in '{rel}'. Neem er meer omheen "
            "zodat het uniek is, of zet alles=true.")
    wr.zorg_voor_werktak(ws)
    doel.write_text(tekst.replace(oud, nieuw), encoding="utf-8")
    return {"pad": rel, "vervangen": aantal if alles else 1,
            "volgende_stap": "Leg het vast met 'vastleggen'."}


def verwijder(ws: Werkruimte, pad: str) -> dict:
    doel, rel = wr.controleer_schrijfbaar(ws, pad)
    if not doel.is_file():
        raise Geweigerd(f"'{rel}' bestaat niet.")
    wr.zorg_voor_werktak(ws)
    doel.unlink()
    return {"pad": rel, "actie": "verwijderd",
            "terug": "Terugdraaien kan met 'terugdraaien' zolang je het niet "
                     "hebt vastgelegd."}


# ---- Git ------------------------------------------------------------------
def wijzigingen(ws: Werkruimte, pad: str = "") -> dict:
    """Wat is er veranderd: nog niet vastgelegd, en je tak versus main."""
    paden = ["--", pad.strip()] if (pad or "").strip() else \
            ["--", "backend", "frontend", "tests"]
    open_ = wr.git(ws, "diff", *paden)
    tak = wr.huidige_tak(ws)
    try:
        vast = wr.git(ws, "diff", "--stat", f"main...{tak}").strip()
    except Geweigerd:
        vast = ""
    nieuw = [r[3:] for r in wr.git(ws, "status", "--porcelain",
                                   "--", "backend", "frontend", "tests"
                                   ).splitlines() if r.startswith("??")]
    return {"nog_niet_vastgelegd": open_[:60000] or "(niets)",
            "nieuwe_bestanden": nieuw,
            "jouw_tak_versus_main": vast or "(gelijk aan main)"}


def vastleggen(ws: Werkruimte, bericht: str, gebruiker: str) -> dict:
    """De wijzigingen vastleggen als commit op de werktak van de gebruiker."""
    if ws.autodeploy:
        raise Geweigerd(f"Deze werkruimte staat onder {ws.autodeploy}; "
                        "vastleggen heeft geen zin zolang die draait.")
    if not (bericht or "").strip():
        raise Geweigerd("Geef een korte omschrijving van wat je veranderd hebt.")
    tak = wr.zorg_voor_werktak(ws)
    # Bewust alleen de app-mappen: in elke kopie staat een losse, niet-getrackte
    # kopie van de repo, en die hoort niet in de geschiedenis.
    wr.git(ws, "add", "-A", "--", "backend", "frontend", "tests")
    if not wr.git(ws, "diff", "--cached", "--name-only").strip():
        return {"resultaat": "Er was niets om vast te leggen.", "tak": tak}
    wie = f"{gebruiker} via Claude <mcp@globaal.be>"
    wr.git(ws, "-c", f"user.name={gebruiker} via Claude",
           "-c", "user.email=mcp@globaal.be",
           "commit", "-q", "--author", wie, "-m", bericht.strip())
    kop = wr.git(ws, "log", "-1", "--format=%h %s").strip()
    return {"vastgelegd": kop, "tak": tak,
            "volgende_stap": "Zet het live met 'uitrollen'."}


def geschiedenis(ws: Werkruimte, aantal: int = 15) -> dict:
    n = max(1, min(int(aantal or 15), 50))
    regels = wr.git(ws, "log", f"-{n}", "--format=%h\t%ad\t%an\t%s",
                    "--date=short").splitlines()
    return {"tak": wr.huidige_tak(ws), "commits": regels}


def terugdraaien(ws: Werkruimte, pad: str = "", commit: str = "") -> dict:
    """Een wijziging ongedaan maken.

    Met `pad`: de nog niet vastgelegde wijzigingen in dat bestand weggooien.
    Met `commit`: een tegen-commit maken. Er wordt nooit geschiedenis gewist,
    zodat werk niet stil kan verdwijnen.
    """
    if ws.autodeploy:
        raise Geweigerd(f"Deze werkruimte staat onder {ws.autodeploy}.")
    if bool(pad.strip()) == bool(commit.strip()):
        raise Geweigerd("Geef of 'pad' (open wijzigingen weggooien) of "
                        "'commit' (een vastgelegde wijziging terugdraaien).")
    if pad.strip():
        doel, rel = wr.controleer_schrijfbaar(ws, pad)
        wr.git(ws, "checkout", "--", rel)
        return {"pad": rel, "resultaat": "Open wijzigingen zijn weggegooid."}
    kort = commit.strip()
    if not kort.isalnum():
        raise Geweigerd("Geef een commit-kenmerk zoals je het in "
                        "'geschiedenis' ziet.")
    wr.zorg_voor_werktak(ws)
    wr.git(ws, "-c", "user.name=Claude", "-c", "user.email=mcp@globaal.be",
           "revert", "--no-edit", kort)
    return {"resultaat": wr.git(ws, "log", "-1", "--format=%h %s").strip(),
            "volgende_stap": "Zet het live met 'uitrollen'."}


# ---- Uitrollen ------------------------------------------------------------
def uitrol_stand(ws: Werkruimte) -> dict:
    with _uitrol_slot:
        s = _uitrol.get(ws.project)
        return dict(s) if s else {"stand": "niets gedaan deze sessie"}


def _bouw(ws: Werkruimte) -> None:
    """Bouwen en herstarten. Draait in een aparte draad; duurt minuten."""
    begin = time.time()
    try:
        r = subprocess.run(["docker", "compose", "up", "-d", "--build"],
                           cwd=ws.map, capture_output=True, text=True,
                           timeout=2400)
        staart = (r.stdout + r.stderr).strip().splitlines()[-25:]
        with _uitrol_slot:
            _uitrol[ws.project] = {
                "stand": "klaar" if r.returncode == 0 else "mislukt",
                "duur_seconden": int(time.time() - begin),
                "uitvoer": staart,
            }
    except subprocess.TimeoutExpired:
        with _uitrol_slot:
            _uitrol[ws.project] = {"stand": "mislukt",
                                   "uitvoer": ["Het bouwen duurde te lang "
                                               "(40 minuten) en is afgebroken."]}
    except Exception as e:  # noqa: BLE001 - de stand moet altijd kloppen
        with _uitrol_slot:
            _uitrol[ws.project] = {"stand": "mislukt",
                                   "uitvoer": [f"{type(e).__name__}: {e}"]}
    finally:
        _bouwslot.release()


def uitrollen(ws: Werkruimte) -> dict:
    """De eigen containers opnieuw bouwen en herstarten.

    Loopt op de achtergrond: een bouw duurt hier minuten. De stand vraag je op
    met 'werkruimte'.
    """
    with _uitrol_slot:
        if (_uitrol.get(ws.project) or {}).get("stand") == "bezig":
            return {"resultaat": "Er loopt al een uitrol voor jouw werkruimte.",
                    "stand": "bezig"}
    belasting = _belasting()
    if belasting > MAX_BELASTING:
        raise Geweigerd(
            f"De VM staat nu te zwaar (belasting {belasting:.1f}, grens "
            f"{MAX_BELASTING:.0f}). Een bouw erbij legt het platform plat. "
            "Probeer het straks opnieuw.")
    if not _bouwslot.acquire(blocking=False):
        return {"resultaat": "Er wordt al ergens anders gebouwd; er kan er "
                             "maar een tegelijk. Probeer het zo opnieuw.",
                "stand": "wacht"}
    with _uitrol_slot:
        _uitrol[ws.project] = {"stand": "bezig", "gestart": time.strftime("%H:%M")}
    threading.Thread(target=_bouw, args=(ws,), daemon=True).start()
    return {"resultaat": "Het bouwen is gestart; dat duurt enkele minuten. "
                         "Vraag 'werkruimte' voor de stand.",
            "stand": "bezig", "app": ws.url}


def logboek(ws: Werkruimte, dienst: str = "backend", regels: int = 60) -> dict:
    """De laatste regels uit een containerlog (backend, web of mongo)."""
    dienst = (dienst or "backend").strip().lower()
    if dienst not in ("backend", "web", "mongo"):
        raise Geweigerd("Kies backend, web of mongo.")
    n = max(1, min(int(regels or 60), MAX_LOG))
    naam = f"{ws.project}-{dienst}-1"
    r = subprocess.run(["docker", "logs", "--tail", str(n), naam],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise Geweigerd(
            f"Geen log voor '{dienst}': die container draait niet. "
            + ("De mongo-container ontbreekt in alle kopieen; 'uitrollen' "
               "start hem alsnog." if dienst == "mongo" else ""))
    return {"dienst": dienst, "container": naam,
            "log": (r.stdout + r.stderr).splitlines()[-n:]}


def schijfruimte() -> str:
    t = shutil.disk_usage("/")
    return f"{t.used * 100 // t.total}% vol"

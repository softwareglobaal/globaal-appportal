"""Werkruimtes van RenoVision: welke kopie hoort bij wie, en wat mag daarin.

Elke collega heeft op de VM een eigen kopie van RenoVision staan
(`~/globaal-renovision-<naam>`, aangemaakt met `renovision-kopie.sh`): een
eigen map, eigen containers, eigen poort en een eigen mongo-volume. Die
scheiding is hier het beveiligingsmodel. De MCP-server leidt de werkruimte af
uit de ingelogde Authentik-gebruiker, en die keuze ligt daarna vast: er is geen
gereedschap waarmee je een andere werkruimte kunt aanwijzen.

Dit bestand bevat de dingen die fout kunnen gaan zonder dat je het merkt --
padbegrenzing, schrijfrechten, git -- los van de HTTP-laag, zodat ze te testen
zijn zonder Flask (`test_werkruimte.py`).
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Waar de kopieen staan. Instelbaar zodat de tests op een tijdelijke map kunnen.
BASISMAP = Path(os.environ.get("RENOVISION_BASISMAP", "/home/ubuntu"))
VOORVOEGSEL = "globaal-renovision"

# Beheerders krijgen de admin-kopie: die heeft geen eigen persoon en dient als
# de werkbank waar de reparaties op zijn beproefd.
BEHEERDERS = {"akadmin": "admin", "samad": "admin"}

# ---- Wat leesbaar en schrijfbaar is ---------------------------------------
#
# Schrijven mag alleen in de applicatie zelf. De manier waarop de app gebouwd
# en gedraaid wordt blijft eronderuit: docker-compose.yml kan een host-map in
# een container hangen en `deploy/*.sh` draait als de gebruiker ubuntu op de
# host -- via allebei zou een codewijziging de VM zelf kunnen overnemen. Dat
# hoort bij een beheerder, niet bij een tekstwijziging in Claude.
SCHRIJFBARE_WORTELS = ("backend/", "frontend/", "tests/")
SCHRIJFBARE_LOSSE = (".md",)          # losse documentatie in de wortel

# .env bevat de ANTHROPIC_API_KEY in platte tekst. Niet leesbaar, niet
# schrijfbaar: anders leest de eerste de beste vraag aan Claude hem uit.
# .env.example staat wel in git en mag wel (daar staan geen sleutels in).
GEHEIM = re.compile(r"(^|/)\.env($|\.)(?!example)")

MAX_LEES = 400_000        # tekens; grotere bestanden lees je met vanaf/aantal
MAX_SCHRIJF = 1_000_000   # tekens


class Geweigerd(ValueError):
    """Een verzoek dat we bewust niet uitvoeren; de tekst gaat naar Claude."""


@dataclass(frozen=True)
class Werkruimte:
    naam: str          # 'marise', 'admin', ...
    map: Path          # ~/globaal-renovision-marise
    project: str       # COMPOSE_PROJECT_NAME, bv. renovision-marise
    poort: str         # RENOVISION_PORT
    autodeploy: str    # naam van de systemd-timer die deze map overschrijft, of ""

    @property
    def url(self) -> str:
        deel = "renovision" if self.naam == "hoofd" else f"renovision-{self.naam}"
        return f"https://{deel}.globaal.be"

    @property
    def tak(self) -> str:
        """De werktak waarop de wijzigingen van deze gebruiker landen."""
        return f"werk/{self.naam}"


def _env_lezen(map_: Path) -> dict:
    """COMPOSE_PROJECT_NAME en RENOVISION_PORT uit .env halen.

    Alleen deze twee sleutels: de rest van .env bevat geheimen en heeft hier
    niets te zoeken.
    """
    uit = {}
    pad = map_ / ".env"
    if not pad.exists():
        return uit
    for regel in pad.read_text(encoding="utf-8", errors="replace").splitlines():
        regel = regel.strip()
        if regel.startswith(("COMPOSE_PROJECT_NAME=", "RENOVISION_PORT=")):
            sleutel, _, waarde = regel.partition("=")
            uit[sleutel] = waarde.strip()
    return uit


def _timer_actief(naam: str) -> str:
    """Naam van de auto-deploy-timer die deze map leegveegt, of "".

    `deploy/autodeploy.sh` doet `git reset --hard origin/<tak>`. Draait die
    timer, dan is elke wijziging in die map binnen twee minuten weg -- ook een
    vastgelegde commit. Voor zulke werkruimtes weigeren we te schrijven; dat is
    eerlijker dan werk laten verdampen.
    """
    unit = ("renovision-deploy.timer" if naam == "hoofd"
            else f"renovision-{naam}-deploy.timer")
    try:
        r = subprocess.run(["systemctl", "is-active", unit],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return unit if r.stdout.strip() == "active" else ""


def ontdek() -> dict[str, Werkruimte]:
    """Alle kopieen op de VM inlezen, met hun compose-project en poort.

    Nieuwe kopieen (`renovision-kopie.sh <naam> <poort>`) komen er vanzelf bij:
    er is geen lijst die je apart moet bijwerken.
    """
    uit: dict[str, Werkruimte] = {}
    if not BASISMAP.is_dir():
        return uit
    for map_ in sorted(BASISMAP.glob(VOORVOEGSEL + "*")):
        if not (map_ / ".git").is_dir():
            continue
        rest = map_.name[len(VOORVOEGSEL):]
        naam = rest.lstrip("-") or "hoofd"
        env = _env_lezen(map_)
        uit[naam] = Werkruimte(
            naam=naam,
            map=map_,
            project=env.get("COMPOSE_PROJECT_NAME", map_.name),
            poort=env.get("RENOVISION_PORT", ""),
            autodeploy=_timer_actief(naam),
        )
    return uit


def voor_gebruiker(gebruiker: str, ruimtes: dict[str, Werkruimte] | None = None):
    """De werkruimte van deze Authentik-gebruiker, of None.

    De regel is de naamconventie die `renovision-kopie.sh` al aanhoudt:
    gebruiker `marise` hoort bij `globaal-renovision-marise`. Beheerders komen
    op de admin-kopie uit. Wie geen eigen kopie heeft, krijgt geen toegang --
    we vallen nooit terug op de hoofdmap.
    """
    ruimtes = ontdek() if ruimtes is None else ruimtes
    naam = (gebruiker or "").strip().lower()
    return ruimtes.get(BEHEERDERS.get(naam, naam))


# ---- Padbegrenzing --------------------------------------------------------
def veilig_pad(ws: Werkruimte, pad: str) -> Path:
    """Een pad uit een verzoek omzetten naar een pad binnen de werkruimte.

    Weigert alles wat buiten de map uitkomt: `..`, absolute paden, en
    symlinks die naar buiten wijzen (vandaar realpath en niet alleen een
    tekstcontrole).
    """
    if not isinstance(pad, str) or not pad.strip():
        raise Geweigerd("Geef een pad op, relatief aan de wortel van de app.")
    schoon = pad.strip().replace("\\", "/")
    if "\x00" in schoon:
        raise Geweigerd("Ongeldig pad.")
    # Een absoluut pad weigeren we in plaats van het stil als relatief te
    # lezen: '/etc/passwd' zou anders '<werkruimte>/etc/passwd' worden en de
    # foutmelding ('bestaat niet') zou het echte bezwaar verbergen.
    if schoon.startswith("/") or os.path.isabs(schoon) or ":" in schoon.split("/")[0]:
        raise Geweigerd(
            f"'{pad}' is een absoluut pad. Paden zijn relatief aan de wortel "
            "van de app, bijvoorbeeld backend/routes.py.")
    wortel = Path(os.path.realpath(ws.map))
    doel = Path(os.path.realpath(wortel / schoon))
    if doel != wortel and wortel not in doel.parents:
        raise Geweigerd(
            f"'{pad}' ligt buiten je werkruimte. Paden zijn relatief aan de "
            "wortel van de app, bijvoorbeeld backend/routes.py.")
    return doel


def relatief(ws: Werkruimte, doel: Path) -> str:
    return doel.relative_to(Path(os.path.realpath(ws.map))).as_posix()


def leesbaar(rel: str) -> bool:
    """Of dit pad uberhaupt getoond of gelezen mag worden."""
    return not GEHEIM.search("/" + rel)


def mag_schrijven(rel: str) -> tuple[bool, str]:
    """(mag, reden). De reden gaat letterlijk naar Claude terug."""
    if not leesbaar(rel):
        return False, (".env bevat de API-sleutel en is afgeschermd. De "
                       "instelbare waarden staan in .env.example.")
    if rel.startswith(SCHRIJFBARE_WORTELS):
        return True, ""
    if "/" not in rel and rel.endswith(SCHRIJFBARE_LOSSE):
        return True, ""
    return False, (
        f"'{rel}' hoort bij hoe de app gebouwd en gedraaid wordt, niet bij de "
        "app zelf. Wijzigen mag in backend/, frontend/, tests/ en de "
        "documentatie in de wortel. Voor docker-compose.yml, deploy/ of .env "
        "moet je bij de beheerder zijn.")


def controleer_schrijfbaar(ws: Werkruimte, pad: str) -> tuple[Path, str]:
    """Pad valideren voor schrijven: binnen de map, toegestaan, geen timer."""
    if ws.autodeploy:
        raise Geweigerd(
            f"Deze werkruimte wordt elke twee minuten overschreven door "
            f"{ws.autodeploy} (die zet de map terug op wat er in GitHub staat). "
            "Wijzigingen zouden binnen twee minuten weg zijn. Vraag de beheerder "
            "die timer uit te zetten voordat je hier via Claude werkt.")
    doel = veilig_pad(ws, pad)
    rel = relatief(ws, doel)
    mag, reden = mag_schrijven(rel)
    if not mag:
        raise Geweigerd(reden)
    return doel, rel


# ---- Git ------------------------------------------------------------------
def git(ws: Werkruimte, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=ws.map, capture_output=True,
                       text=True, timeout=120)
    if check and r.returncode != 0:
        raise Geweigerd(f"git {' '.join(args)}: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def huidige_tak(ws: Werkruimte) -> str:
    return git(ws, "rev-parse", "--abbrev-ref", "HEAD").strip()


def zorg_voor_werktak(ws: Werkruimte) -> str:
    """Op de werktak van deze gebruiker gaan staan, en hem zo nodig maken.

    De wijzigingen van een collega blijven zo bij elkaar en zijn later als een
    nette reeks commits op te pakken. We laten `main` ongemoeid, zodat het
    verschil met de gedeelde versie altijd te zien is.
    """
    tak = ws.tak
    if huidige_tak(ws) == tak:
        return tak
    bestaat = subprocess.run(["git", "rev-parse", "--verify", "--quiet", tak],
                             cwd=ws.map, capture_output=True, text=True).returncode == 0
    git(ws, "checkout", "-q", tak) if bestaat else git(ws, "checkout", "-q", "-b", tak)
    return tak


def getrackte_bestanden(ws: Werkruimte) -> list[str]:
    """De bestanden van de app volgens git.

    Bewust via git en niet via een mapwandeling: dat houdt node_modules,
    __pycache__ en de losse kopie van de repo die in elke map is
    achtergebleven vanzelf buiten beeld.
    """
    uit = git(ws, "ls-files").splitlines()
    return sorted(p for p in uit if p and leesbaar(p))

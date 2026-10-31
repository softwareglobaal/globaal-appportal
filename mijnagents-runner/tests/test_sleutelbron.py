"""Grendel op de sleutelbron: de Anthropic-sleutel van elke agent komt alleen uit ~/appportal/.env.

T-0064 (31-10-2026): de ANTHROPIC_API_KEY in ~/agents/.env gaf sinds 14-10-2026 een 401, die in ~/appportal/.env
werkt. De Levenscoach, De Ontwikkelaar en de werfverslagschrijver namen de dode sleutel; De Contractmaker, De
Regisseur en de Fathomwacht werkten alleen omdat een geïmporteerde koppeling toevallig eerst ~/appportal/.env laadde.
Driehoeksoverleg 31-10 (X4, X5, G3, K3): alleen die ene naam uit ~/appportal/.env, de andere instellingen houden hun
bron, een ontbrekende sleutel faalt duidelijk, en de proef herkent elke schrijfwijze van het pad ~/agents/.env.
Alleen verzonnen sleutels in een verzonnen thuismap.

Draaien: python3 mijnagents-runner/tests/test_sleutelbron.py
"""
import ast
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1]
KOPPELINGEN = RUNNER / "koppelingen"
AGENTS_PAD = re.compile(r'agents(?:/|["\']\s*/\s*["\'])\.env')    # "~/agents/.env", Path.home() / "agents" / ".env"
ANTHROPIC = re.compile(r"ANTHROPIC_API_KEY|Anthropic\(")

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  goed  {naam}")
    else:
        fout += 1
        print(f"  FOUT  {naam} {extra}")


def thuismap(stack):
    """Een verzonnen thuismap: een dode sleutel en een eigen instelling in ~/agents/.env, `stack` in ~/appportal/.env."""
    thuis = tempfile.mkdtemp(prefix="thuis-")
    for pad, inhoud in (("agents/.env", 'ANTHROPIC_API_KEY="sleutel-dood"\nKENNIS_DSN=dsn-uit-agents\n'),
                        ("appportal/.env", stack)):
        (Path(thuis) / pad).parent.mkdir(parents=True, exist_ok=True)
        (Path(thuis) / pad).write_text(inhoud, encoding="utf-8")
    return thuis


def draai(code, thuis, omgeving=None):
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "KENNIS_DSN")} | {"HOME": thuis}
    kop = f"import os, sys\nsys.path.insert(0, {str(KOPPELINGEN)!r})\n"
    slot = "\nprint(repr(os.environ.get('ANTHROPIC_API_KEY')), repr(os.environ.get('KENNIS_DSN')))"
    return subprocess.run([sys.executable, "-c", kop + code + slot], capture_output=True, text=True,
                          env=env | (omgeving or {}), timeout=30)


MET = 'ANTHROPIC_API_KEY="sleutel-werkt"\n'
ZONDER = "AGENTS_TOKEN=iets-anders\n"
AGENTS_NA = (
    "import sleutelbron\nsleutelbron.zet_anthropic()\n"
    "for regel in open(os.path.expanduser('~/agents/.env')):\n"
    "    k, _, v = regel.strip().partition('=')\n"
    "    os.environ.setdefault(k, v.strip('\"'))\n")

print("De sleutelbron zelf")
uit = draai(AGENTS_NA, thuismap(MET))
check("de sleutel uit ~/appportal/.env wint van de dode in ~/agents/.env", uit.stdout.split()[:1] == ["'sleutel-werkt'"], uit.stdout + uit.stderr)
check("een instelling die alleen in ~/agents/.env staat, blijft van daar komen", "'dsn-uit-agents'" in uit.stdout, uit.stdout)
uit = draai(AGENTS_NA, thuismap(ZONDER))
check("zonder sleutel in ~/appportal/.env vult ~/agents/.env hem niet", uit.stdout.split()[:1] == ["''"], uit.stdout)
check("en dan staat er een duidelijke fout", "FOUT: geen ANTHROPIC_API_KEY in ~/appportal/.env" in uit.stderr, uit.stderr)
uit = draai(AGENTS_NA, thuismap(MET), {"ANTHROPIC_API_KEY": "sleutel-shell"})
check("een sleutel uit de shell wint", uit.stdout.split()[:1] == ["'sleutel-shell'"], uit.stdout)
bron = (KOPPELINGEN / "sleutelbron.py").read_text(encoding="utf-8")
check("de sleutelbron print of logt de waarde nooit", not re.search(r"print\([^)]*(waarde|environ\[NAAM\])", bron))


def is_laadoproep(knoop):
    """laad_env("~/agents/.env"), _env(...) of sleutelbron.zet_anthropic() op het bovenste niveau."""
    if not (isinstance(knoop, ast.Expr) and isinstance(knoop.value, ast.Call)):
        return False
    f = knoop.value.func
    if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
        return f.value.id == "sleutelbron" and f.attr == "zet_anthropic"
    args = knoop.value.args
    return isinstance(f, ast.Name) and bool(args) and isinstance(args[0], ast.Constant) and str(args[0].value).endswith("/.env")


def laadcode(bron):
    """Alleen de laadfuncties, de import van de sleutelbron en de laadoproepen van het bovenste niveau."""
    boom = ast.parse(bron)
    oproepen = [n for n in boom.body if is_laadoproep(n)]
    namen = {n.value.func.id for n in oproepen if isinstance(n.value.func, ast.Name)}
    functies = [n for n in boom.body if isinstance(n, ast.FunctionDef) and n.name in namen]
    imports = [n for n in boom.body if isinstance(n, ast.Import) and any(a.name == "sleutelbron" for a in n.names)]
    return ast.unparse(ast.Module(body=imports + functies + oproepen, type_ignores=[]))


print("Elke runner die ~/agents/.env leest en Claude gebruikt")
runners = sorted(p for p in RUNNER.rglob("*.py") if "tests" not in p.relative_to(RUNNER).parts and p != KOPPELINGEN / "sleutelbron.py"
                 and AGENTS_PAD.search(t := p.read_text(encoding="utf-8")) and ANTHROPIC.search(t))
check("de proef vindt de runners (anders meet ze niets)", len(runners) >= 7, str([p.name for p in runners]))
for p in runners:
    naam = str(p.relative_to(RUNNER))
    bron = p.read_text(encoding="utf-8")
    check(f"{naam}: gebruikt sleutelbron.zet_anthropic", "sleutelbron.zet_anthropic()" in bron)
    code = laadcode(bron)
    uit = draai(code, thuismap(MET))
    check(f"{naam}: de sleutel komt uit ~/appportal/.env", uit.stdout.split()[:1] == ["'sleutel-werkt'"],
          f"(kreeg {(uit.stdout or uit.stderr).strip()[-160:]!r})")
    uit = draai(code, thuismap(ZONDER))
    check(f"{naam}: zonder sleutel in ~/appportal/.env geen terugval op de dode", uit.stdout.split()[:1] == ["''"],
          f"(kreeg {uit.stdout.strip()!r})")

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

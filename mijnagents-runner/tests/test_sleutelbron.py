"""Grendel op de sleutelbron: de Anthropic-sleutel van elke agent komt alleen uit ~/appportal/.env.

T-0064 (31-10-2026): de ANTHROPIC_API_KEY in ~/agents/.env gaf sinds 14-10-2026 een 401, die in ~/appportal/.env
werkt. De Levenscoach, De Ontwikkelaar en de werfverslagschrijver namen de dode sleutel; De Contractmaker, De
Regisseur en de Fathomwacht werkten alleen omdat een geïmporteerde koppeling toevallig eerst ~/appportal/.env laadde.
Driehoeksoverleg 31-10 (X4, X5, G3, K3) en Codex-test 31-10 (1 tot 5): alleen die ene naam uit ~/appportal/.env, die
wint van elke eerder gezette waarde, de andere instellingen houden hun bron, een ontbrekende sleutel wordt leeg, en
elke runner met Claude en een eigen .env-lader zit in de proef. Alleen verzonnen sleutels in een verzonnen thuismap.

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
ANTHROPIC = re.compile(r"ANTHROPIC_API_KEY|Anthropic\(")
ENV_LADER = re.compile(r"\.env[\"']")                     # "~/agents/.env", "mijnagents-data/.env", Path(...) / ".env"
VOORAF = {"ANTHROPIC_API_KEY": "sleutel-dood-vooraf"}     # zoals een import, de shell of een ander .env-bestand

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
                        ("appportal/.env", stack), ("appportal/mijnagents-data/.env", 'ANTHROPIC_API_KEY="sleutel-data"\n')):
        (Path(thuis) / pad).parent.mkdir(parents=True, exist_ok=True)
        (Path(thuis) / pad).write_text(inhoud, encoding="utf-8")
    return thuis


def draai(code, thuis, omgeving=None, cwd=None):
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "KENNIS_DSN")} | {"HOME": thuis}
    kop = f"import os, sys\nsys.path.insert(0, {str(KOPPELINGEN)!r})\n"
    slot = "\nprint(repr(os.environ.get('ANTHROPIC_API_KEY')), repr(os.environ.get('KENNIS_DSN')))"
    return subprocess.run([sys.executable, "-c", kop + code + slot], capture_output=True, text=True,
                          env=env | (omgeving or {}), timeout=60, cwd=cwd)


def sleutel(uit):
    return (uit.stdout.split() or [""])[0]


MET = 'ANTHROPIC_API_KEY="sleutel-werkt"\n'
ZONDER = "AGENTS_TOKEN=iets-anders\n"
AGENTS_EERST = ("for regel in open(os.path.expanduser('~/agents/.env')):\n"
                "    k, _, v = regel.strip().partition('=')\n"
                "    os.environ.setdefault(k, v.strip('\"'))\n"
                "import sleutelbron\nsleutelbron.zet_anthropic()\n")

print("De sleutelbron zelf")
uit = draai(AGENTS_EERST, thuismap(MET))
check("de sleutel uit ~/appportal/.env wint van de dode uit ~/agents/.env", sleutel(uit) == "'sleutel-werkt'", uit.stdout + uit.stderr)
check("een instelling die alleen in ~/agents/.env staat, blijft van daar komen", "'dsn-uit-agents'" in uit.stdout, uit.stdout)
uit = draai(AGENTS_EERST, thuismap(MET), VOORAF)
check("hij wint ook van een sleutel die er vooraf al stond", sleutel(uit) == "'sleutel-werkt'", uit.stdout)
uit = draai(AGENTS_EERST, thuismap(ZONDER), VOORAF)
check("zonder sleutel in ~/appportal/.env wordt hij leeg, ook met een oude vooraf", sleutel(uit) == "''", uit.stdout)
check("en dan staat er een duidelijke fout", "FOUT: geen ANTHROPIC_API_KEY in ~/appportal/.env" in uit.stderr, uit.stderr)
uit = draai("import sleutelbron\nsleutelbron.zet_anthropic()\nos.environ.setdefault('ANTHROPIC_API_KEY', 'sleutel-later')\n", thuismap(MET))
check("een latere lader met setdefault raakt hem niet meer", sleutel(uit) == "'sleutel-werkt'", uit.stdout)
bron = (KOPPELINGEN / "sleutelbron.py").read_text(encoding="utf-8")
check("de sleutelbron print of logt de waarde nooit", not re.search(r"print\([^)]*(waarde|environ\[NAAM\])", bron))


def is_lader(knoop):
    """Een oproep op het bovenste niveau zoals laad_env("~/agents/.env") of _env("~/appportal/mijnagents-data/.env")."""
    if not (isinstance(knoop, ast.Expr) and isinstance(knoop.value, ast.Call) and isinstance(knoop.value.func, ast.Name)):
        return False
    args = knoop.value.args
    return bool(args) and isinstance(args[0], ast.Constant) and str(args[0].value).endswith("/.env")


def is_zet(knoop):
    f = knoop.value.func if isinstance(knoop, ast.Expr) and isinstance(knoop.value, ast.Call) else None
    return isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and (f.value.id, f.attr) == ("sleutelbron", "zet_anthropic")


print("Elke runner die Claude gebruikt en zelf een .env laadt")
runners = sorted(p for p in RUNNER.rglob("*.py") if "tests" not in p.relative_to(RUNNER).parts
                 and p != KOPPELINGEN / "sleutelbron.py"
                 and ANTHROPIC.search(t := p.read_text(encoding="utf-8")) and ENV_LADER.search(t))
namen = {str(p.relative_to(RUNNER)) for p in runners}
# prijsonderzoeker.py staat er sinds overleg 14 (01-11-2026) niet meer bij: die werkt met het Claude-abonnement en
# mag de API-sleutel juist niet laden (tests/test_aankoop_prijs.py houdt dat vast).
verwacht = {"archivaris.py", "contracten_agent.py", "fathom_wacht.py", "levenscoach.py", "ontwikkelaar.py",
            "regisseur.py", "weekconsolidatie.py", "werfverslag_proef.py"}
check("De Prijsonderzoeker gebruikt geen API-sleutel meer", "prijsonderzoeker.py" not in namen)
check("de proef vindt de runners (anders meet ze niets)", verwacht <= namen, str(sorted(verwacht - namen)))
for p in runners:
    naam, bron = str(p.relative_to(RUNNER)), p.read_text(encoding="utf-8")
    check(f"{naam}: gebruikt sleutelbron.zet_anthropic", "sleutelbron.zet_anthropic()" in bron)
    boom = ast.parse(bron)
    laders, zet = [n for n in boom.body if is_lader(n)], [n for n in boom.body if is_zet(n)]
    if not laders:
        continue                                          # laadt in een functie (weekconsolidatie.sleutel_laden)
    check(f"{naam}: de sleutelbron komt na elke eigen .env-lader", zet and zet[0].lineno > max(n.lineno for n in laders),
          f"(lader op regel {max(n.lineno for n in laders)}, sleutelbron op {zet[0].lineno if zet else 'geen'})")
    functies = {n.value.func.id for n in laders}
    code = ast.unparse(ast.Module(body=[n for n in boom.body if isinstance(n, ast.FunctionDef) and n.name in functies]
                                  + [ast.parse("import sleutelbron").body[0]] + laders + zet, type_ignores=[]))
    uit = draai(code, thuismap(MET), VOORAF)
    check(f"{naam}: de sleutel komt uit ~/appportal/.env, ook met een oude vooraf", sleutel(uit) == "'sleutel-werkt'",
          f"(kreeg {(uit.stdout or uit.stderr).strip()[-160:]!r})")
    uit = draai(code, thuismap(ZONDER), VOORAF)
    check(f"{naam}: zonder sleutel in ~/appportal/.env geen terugval", sleutel(uit) == "''", f"(kreeg {uit.stdout.strip()!r})")

print("De echte import, met alle imports ervoor (overgeslagen waar een pakket hier ontbreekt)")
for p in runners:
    if p.parent != RUNNER:
        continue
    naam = p.stem
    code = (f"sys.path[:0] = [{str(RUNNER)!r}]\nsys.argv = [{naam!r}]\nimport importlib, io, contextlib\n"
            f"with contextlib.redirect_stdout(io.StringIO()):\n    importlib.import_module({naam!r})\n")
    if naam == "weekconsolidatie":
        code += "importlib.import_module('weekconsolidatie').sleutel_laden()\n"
    uit = draai(code, thuismap(MET), VOORAF, cwd=RUNNER)
    ontbreekt = re.search(r"ModuleNotFoundError: No module named '([^']+)'", uit.stderr)
    if uit.returncode and ontbreekt:
        print(f"  over  {naam}: pakket {ontbreekt.group(1)} ontbreekt hier")
        continue
    check(f"{naam}: na de echte import komt de sleutel uit ~/appportal/.env", sleutel(uit) == "'sleutel-werkt'",
          f"(kreeg {(uit.stdout or uit.stderr).strip()[-160:]!r})")

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

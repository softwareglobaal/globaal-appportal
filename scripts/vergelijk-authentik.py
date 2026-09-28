#!/usr/bin/env python3
"""Vergelijkt de oude add-<app>-app.py scripts met wat apps.yaml voorschrijft.

Bedoeld om vóór het vervangen van de oude scripts te kunnen zien of de nieuwe
registratie exact hetzelfde oplevert. Het leest de oude scripts statisch, dus
het raakt Authentik niet aan en kan overal draaien.

    python3 scripts/vergelijk-authentik.py

Uitvoer per app: welke groepen het oude script bindt, wat apps.yaml zegt, en
welke groepen alleen worden aangemaakt zonder te binden. De afsluitcode is 1
als er voor een actieve app met tegel een verschil is, zodat dit in een controle
kan hangen.

Een verschil is niet automatisch een fout. Het betekent: iemand moet kiezen wat
klopt, want na de omzetting geldt apps.yaml.
"""
from __future__ import annotations

import ast
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from appcatalogus import AppFout, lees  # noqa: E402

WORTEL = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = WORTEL / "scripts"


class OudScript:
    """Haalt uit een add-*.py script welke groepen het bindt en aanmaakt."""

    def __init__(self, pad: pathlib.Path):
        self.pad = pad
        self.boom = ast.parse(pad.read_text(encoding="utf-8", errors="replace"))
        self.const: dict[str, object] = {}
        self.var2groep: dict[str, str] = {}
        self.gemaakt: list[str] = []
        self.gebonden: list[str] = []
        self.maakt_gebruiker = "User.objects" in ast.unparse(self.boom)
        self._constanten()
        self._groepen()
        self._bindingen()

    # -- hulpjes ----------------------------------------------------------
    def _tekst(self, n) -> str | None:
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            return n.value
        if isinstance(n, ast.Name):
            w = self.const.get(n.id)
            return w if isinstance(w, str) else None
        if isinstance(n, ast.JoinedStr):
            uit = ""
            for deel in n.values:
                if isinstance(deel, ast.Constant):
                    uit += str(deel.value)
                elif isinstance(deel, ast.FormattedValue):
                    t = self._tekst(deel.value)
                    uit += t if t else "?"
            return uit
        if isinstance(n, ast.Call) and len(n.args) == 2:
            return self._tekst(n.args[1])   # os.environ.get("X", "standaard")
        return None

    def _groepsnaam(self, call) -> str | None:
        for kw in call.keywords:
            if kw.arg == "name":
                return self._tekst(kw.value)
        return self._tekst(call.args[0]) if call.args else None

    # -- stappen ----------------------------------------------------------
    def _constanten(self) -> None:
        for n in self.boom.body:
            if not isinstance(n, ast.Assign) or len(n.targets) != 1:
                continue
            doel = n.targets[0]
            if isinstance(doel, ast.Tuple) and isinstance(n.value, (ast.Tuple, ast.List)):
                for naam_n, waarde_n in zip(doel.elts, n.value.elts):
                    if isinstance(naam_n, ast.Name):
                        self._zet(naam_n.id, waarde_n)
            elif isinstance(doel, ast.Name):
                self._zet(doel.id, n.value)

    def _zet(self, naam: str, waarde_n) -> None:
        if isinstance(waarde_n, (ast.Tuple, ast.List)):
            self.const[naam] = [self._tekst(e) for e in waarde_n.elts]
        else:
            t = self._tekst(waarde_n)
            if t is not None:
                self.const[naam] = t

    def _groepen(self) -> None:
        for n in ast.walk(self.boom):
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
                c = n.value
                gn = None
                if isinstance(c.func, ast.Attribute) and \
                   ast.unparse(c.func.value).startswith("Group"):
                    gn = self._groepsnaam(c)
                    if c.func.attr == "get_or_create" and gn:
                        self.gemaakt.append(gn)
                elif isinstance(c.func, ast.Attribute) and c.func.attr in ("first", "get"):
                    binnen = c.func.value
                    if isinstance(binnen, ast.Call) and isinstance(binnen.func, ast.Attribute) \
                       and ast.unparse(binnen.func.value).startswith("Group"):
                        gn = self._groepsnaam(binnen)
                if not gn:
                    continue
                doel = n.targets[0]
                if isinstance(doel, ast.Tuple) and isinstance(doel.elts[0], ast.Name):
                    self.var2groep[doel.elts[0].id] = gn
                elif isinstance(doel, ast.Name):
                    self.var2groep[doel.id] = gn
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
                c = n.value
                if isinstance(c.func, ast.Attribute) and c.func.attr == "get_or_create" \
                   and ast.unparse(c.func.value).startswith("Group"):
                    gn = self._groepsnaam(c)
                    if gn:
                        self.gemaakt.append(gn)

    def _bindingen(self) -> None:
        for n in ast.walk(self.boom):
            if isinstance(n, ast.For) and "PolicyBinding" in ast.unparse(n):
                it = n.iter
                waarden: list[str | None] = []
                if isinstance(it, (ast.Tuple, ast.List)):
                    waarden = [self._tekst(e) for e in it.elts]
                elif isinstance(it, ast.Name):
                    w = self.const.get(it.id)
                    if isinstance(w, list):
                        waarden = w
                echte = [w for w in waarden if w]
                self.gebonden += echte
                if "Group.objects.get_or_create" in ast.unparse(n):
                    self.gemaakt += echte
        for n in ast.walk(self.boom):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
               and ast.unparse(n.func.value).startswith("PolicyBinding"):
                for kw in n.keywords:
                    if kw.arg == "group" and isinstance(kw.value, ast.Name):
                        gn = self.var2groep.get(kw.value.id)
                        if gn:
                            self.gebonden.append(gn)

    # -- resultaat --------------------------------------------------------
    @property
    def slug(self) -> str:
        for sleutel in ("SLUG", "SUB"):
            w = self.const.get(sleutel)
            if isinstance(w, str):
                return w
        naam = self.pad.stem
        return naam[4:].removesuffix("-app") if naam.startswith("add-") else naam

    @property
    def bindt(self) -> list[str]:
        return sorted(set(self.gebonden))

    @property
    def extra(self) -> list[str]:
        return sorted(set(g for g in self.gemaakt if g and g not in self.bindt))


def registraties() -> dict[str, OudScript]:
    uit: dict[str, OudScript] = {}
    for pad in sorted(SCRIPTS.glob("add-*.py")):
        bron = pad.read_text(encoding="utf-8", errors="replace")
        if "ProxyProvider" not in bron or "Application" not in bron:
            continue
        try:
            oud = OudScript(pad)
        except SyntaxError:
            continue
        uit[oud.slug] = oud
    return uit


def main() -> int:
    try:
        apps = {a.id: a for a in lees()}
    except AppFout as fout:
        print(f"fout: {fout}", file=sys.stderr)
        return 2
    oud = registraties()

    kop = f"{'app':26} {'oud script bindt':44} {'apps.yaml roles':32} extra groepen"
    print(kop)
    print("-" * len(kop))

    verschillen = 0
    for app_id in sorted(set(apps) | set(oud)):
        a = apps.get(app_id)
        o = oud.get(app_id)
        bindt = o.bindt if o else []
        rollen = sorted(a.rollen) if a else []
        extra_oud = o.extra if o else []
        extra_yaml = sorted(a.extra_groepen) if a else []

        merk = ""
        if a and o:
            if bindt != rollen:
                merk, verschillen = "  VERSCHIL in toegang", verschillen + 1
            elif extra_oud != extra_yaml:
                merk = "  verschil in extra groepen"
            else:
                merk = "  gelijk"
        elif o and not a:
            merk = "  geen tegel in apps.yaml"
        elif a and not o:
            merk = "  geen registratiescript gevonden"

        print(f"{app_id:26} {','.join(bindt) or '-':44} {','.join(rollen) or '-':32} "
              f"{','.join(extra_oud or extra_yaml) or '-'}{merk}")

    maakt_gebruikers = sorted(s.slug for s in oud.values() if s.maakt_gebruiker)
    print()
    print(f"apps met tegel en registratiescript : "
          f"{len([i for i in apps if i in oud])}")
    print(f"verschillen in toegang              : {verschillen}")
    print(f"registraties zonder tegel           : "
          f"{len([i for i in oud if i not in apps])}")
    if maakt_gebruikers:
        print(f"oude scripts die ook gebruikers aanmaken: {', '.join(maakt_gebruikers)}")
        print("  die stap zit bewust NIET in app-registreren.py")
    return 1 if verschillen else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Configuratiegrendels voor het regiebord (regie.globaal.be, TECHNICAL-REFERENCE 14.17).

De app vertrouwt de X-authentik-*-headers die nginx meegeeft. Daarom zet deze test vast wat bij de review van
22-10-2026 is afgesproken, zodat een latere wijziging het niet ongemerkt breekt:
- POST /api/mac is de enige ingang buiten Authentik: alleen POST, hoogstens 256k, identiteitsheaders geleegd;
- app-regie heeft geen hostpoort, geen volume en hangt alleen aan appnet;
- de tegel opent alleen voor de groep regie-mehdi en heeft geen poort;
- migratie 197 maakt een rol zonder wachtwoord;
- de uitgecheckte repo (./regie) en het Mac-token staan in de gevolgde .gitignore, niet alleen in .git/info/exclude.

Geen verbinding met de VM of Authentik; geen .env of geheimen worden gelezen.
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from appcatalogus import lees  # noqa: E402

IDENTITEIT = ("username", "groups", "email", "name", "uid")
# Alleen de namen staan in git; de waarden staan op de VM in ~/appportal/.env.
GEHEIMEN = ("REGIE_DB_URL", "REGIE_SECRET_KEY", "REGIE_AGENTS_TOKEN", "REGIE_MAC_TOKEN")
WORKFLOW = ROOT / ".github/workflows/regiebord-grendels.yml"


def blok(tekst: str, kop: str) -> str:
    """De inhoud tussen de accolades na `kop`, met geneste blokken (zoals limit_except) erbij."""
    begin = tekst.index(kop) + len(kop)
    diepte = 1
    for positie in range(begin, len(tekst)):
        if tekst[positie] == "{":
            diepte += 1
        elif tekst[positie] == "}":
            diepte -= 1
            if diepte == 0:
                return tekst[begin:positie]
    raise AssertionError(f"blok {kop!r} sluit niet")


def zonder_commentaar(tekst: str) -> str:
    return "\n".join(regel.split("#", 1)[0] for regel in tekst.splitlines())


class RegieInfra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overlay = yaml.safe_load((ROOT / "docker-compose.regie.yml").read_text())
        cls.app = cls.overlay["services"]["app-regie"]
        cls.template = zonder_commentaar((ROOT / "nginx/templates/84-regie.conf.template").read_text())
        cls.snippet = zonder_commentaar((ROOT / "nginx/snippets/forward-auth.conf").read_text())
        cls.migratie = (ROOT / "db/migrations/197-regie.sql").read_text()
        cls.catalogus = next(app for app in lees() if app.id == "regie")

    # --- overlay docker-compose.regie.yml ---

    def test_overlay_raakt_alleen_app_regie(self):
        self.assertEqual(set(self.overlay["services"]), {"app-regie"})
        self.assertNotIn("volumes", self.overlay)

    def test_geen_hostpoort_geen_volume_alleen_appnet(self):
        for sleutel in ("ports", "network_mode", "privileged", "volumes", "cap_add", "extra_hosts"):
            self.assertNotIn(sleutel, self.app, sleutel)
        self.assertEqual(self.app["networks"], ["appnet"])
        self.assertEqual(self.app["environment"]["PORT"], "3042")

    def test_bouw_image_en_gezondheid(self):
        self.assertEqual(self.app["build"], {"context": "./regie", "dockerfile": "app/Dockerfile"})
        self.assertEqual(self.app["image"], "appportal-regie")
        self.assertEqual(self.app["restart"], "unless-stopped")
        self.assertIn("http://localhost:3042/healthz", self.app["healthcheck"]["test"][-1])
        self.assertGreaterEqual(self.app["healthcheck"]["retries"], 3)

    def test_geheimen_alleen_als_naam(self):
        env = self.app["environment"]
        for naam in GEHEIMEN:
            self.assertEqual(env[naam], f"${{{naam}:-}}", f"{naam} hoort zonder waarde in git")
        self.assertEqual(env["REGIE_GROUPS"], "${REGIE_GROUPS:-regie-mehdi}")
        # De bronnen alleen over het interne netwerk, nooit via een publieke host.
        self.assertEqual(env["MIJNAGENTS_URL"], "http://app-mijnagents:3022")
        self.assertEqual(env["HA_PROJECTEN_URL"], "http://app-ha-projecten:3140")

    # --- vhost 84-regie.conf.template ---

    def test_vhost_gaat_naar_app_regie_achter_forward_auth(self):
        self.assertEqual(len(list((ROOT / "nginx/templates").glob("*-regie.conf.template"))), 1)
        self.assertIn("server_name regie.${BASE_DOMAIN};", self.template)
        self.assertIn("include /etc/nginx/snippets/ssl.conf;", self.template)
        self.assertIn("set $app_upstream http://app-regie:3042;", self.template)
        self.assertEqual(self.template.count("include /etc/nginx/snippets/forward-auth.conf;"), 1)

    def test_api_mac_is_de_enige_eigen_locatie(self):
        locaties = re.findall(r"^\s*location\s+([^{]+?)\s*\{", self.template, re.M)
        self.assertEqual(locaties, ["= /api/mac"])

    def test_api_mac_alleen_post_klein_en_zonder_identiteit(self):
        mac = blok(self.template, "location = /api/mac {")
        self.assertRegex(mac, r"limit_except\s+POST\s*\{\s*deny\s+all;\s*\}")
        self.assertIn("limit_req zone=regie_mac_zone", mac)
        self.assertIn("client_max_body_size 256k;", mac)
        for identiteit in IDENTITEIT:
            self.assertIn(f'proxy_set_header X-authentik-{identiteit} "";', mac)
        self.assertIn("proxy_pass $app_upstream;", mac)
        self.assertNotIn("auth_request", mac)
        # Een grotere body op serverniveau zou ook voor de rest van het bord gelden.
        self.assertEqual(self.template.count("client_max_body_size"), 1)
        self.assertIn("zone=regie_mac_zone:1m rate=30r/m;", self.template)

    def test_forward_auth_zet_de_identiteit_uit_authentik(self):
        rest = blok(self.snippet, "location / {")
        self.assertIn("auth_request     /outpost.goauthentik.io/auth/nginx;", rest)
        for identiteit in IDENTITEIT:
            self.assertRegex(rest, rf"auth_request_set \$authentik_{identiteit}\s+"
                                   rf"\$upstream_http_x_authentik_{identiteit};")
            self.assertRegex(rest, rf"proxy_set_header X-authentik-{identiteit}\s+\$authentik_{identiteit};")
        self.assertIn("proxy_pass $app_upstream;", rest)

    # --- tegel in apps.yaml ---

    def test_tegel_alleen_voor_regie_mehdi_en_zonder_poort(self):
        self.assertEqual(self.catalogus.rollen, ["regie-mehdi"])
        self.assertEqual(self.catalogus.extra_groepen, [])
        self.assertEqual(self.catalogus.status, "active")
        self.assertEqual(self.catalogus.url, "https://regie.globaal.be")
        self.assertIsNone(self.catalogus.poort)
        resultaat = subprocess.run([sys.executable, str(ROOT / "scripts/apps-ontbrekend.py")],
                                   cwd=ROOT, text=True, capture_output=True, check=True)
        self.assertNotIn("regie", resultaat.stdout.splitlines())

    # --- migratie 197-regie.sql ---

    def test_migratie_rol_zonder_wachtwoord_en_eigen_schema(self):
        self.assertNotRegex(self.migratie, re.compile(r"password", re.I))
        self.assertIn("CREATE ROLE regie LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;", self.migratie)
        self.assertIn("CREATE SCHEMA IF NOT EXISTS regie AUTHORIZATION regie;", self.migratie)
        self.assertIn("REVOKE ALL ON SCHEMA regie FROM PUBLIC;", self.migratie)
        self.assertIn("ALTER ROLE regie SET search_path = regie;", self.migratie)
        # Geen rechten op andere schema's: elke GRANT gaat over schema regie naar de rol regie.
        grants = re.findall(r"^GRANT .*$", self.migratie, re.M)
        self.assertEqual(grants, ["GRANT USAGE, CREATE ON SCHEMA regie TO regie;"])

    # --- .gitignore: het live Mac-token mag nooit in deze publieke repo ---

    def test_gitignore_noemt_checkout_en_mac_token(self):
        regels = (ROOT / ".gitignore").read_text().splitlines()
        self.assertIn("/regie/", regels)
        self.assertIn("/regie-mac-token", regels)

    def test_git_negeert_via_de_gevolgde_gitignore(self):
        if not shutil.which("git") or subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT, capture_output=True).returncode:
            self.skipTest("geen git-werkboom (bijvoorbeeld een git archive)")
        for pad in ("regie-mac-token", "regie/app/__init__.py"):
            # -v noemt de bron van de regel: .gitignore, niet .git/info/exclude (die zit niet in versiebeheer).
            resultaat = subprocess.run(["git", "check-ignore", "-v", "--no-index", pad],
                                       cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(resultaat.returncode, 0, f"{pad} wordt niet genegeerd")
            self.assertTrue(resultaat.stdout.startswith(".gitignore:"), resultaat.stdout)
        gevolgd = subprocess.run(["git", "ls-files", "--", "regie", "regie-mac-token"],
                                 cwd=ROOT, text=True, capture_output=True, check=True)
        self.assertEqual(gevolgd.stdout, "")

    # --- de grendel zelf draait bij elke wijziging aan deze bestanden ---

    def test_workflow_bewaakt_alle_bestanden_van_deze_test(self):
        workflow = yaml.safe_load(WORKFLOW.read_text())
        # PyYAML leest de sleutel `on` als True (YAML 1.1).
        aanleiding = workflow.get("on", workflow.get(True))
        nodig = {".gitignore", "apps.yaml", "docker-compose.regie.yml", "nginx/templates/*-regie.conf.template",
                 "nginx/snippets/forward-auth.conf", "db/migrations/197-regie.sql", "scripts/appcatalogus.py",
                 "scripts/apps-ontbrekend.py", "scripts/test_regie_infra.py",
                 ".github/workflows/regiebord-grendels.yml"}
        for gebeurtenis in ("push", "pull_request"):
            self.assertEqual(nodig - set(aanleiding[gebeurtenis]["paths"]), set(), gebeurtenis)
        stappen = [stap.get("run", "") for job in workflow["jobs"].values() for stap in job["steps"]]
        self.assertIn("python3 scripts/test_regie_infra.py", stappen)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Configuratiegrendels voor het regiebord (regie.globaal.be, TECHNICAL-REFERENCE 14.17).

De app vertrouwt de X-authentik-*-headers die nginx meegeeft. Daarom zet deze test vast wat bij de reviews van
22-10-2026 is afgesproken, zodat een latere wijziging het niet ongemerkt breekt:
- POST /api/mac is de enige ingang buiten Authentik: alleen POST, hoogstens 256k, identiteitsheaders en
  proxygeheim geleegd;
- het proxygeheim (X-Regie-Proxy-Geheim) gaat alleen naar regie.<domain> en alleen na de forward-auth;
- app-regie heeft precies de afgesproken sleutels en omgeving (geen hostpoort, volume, env_file, ...), alleen appnet;
- de vhost bevat precies de afgesproken opdrachten, migratie 197 precies de afgesproken SQL;
- de tegel opent alleen voor de groep regie-mehdi en heeft geen poort;
- de uitgecheckte repo (./regie) en het Mac-token worden echt genegeerd via de gevolgde .gitignore.

Lijsten in plaats van verboden: wat erbij komt, moet hier bewust bij, in dezelfde review.
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
# Alleen de namen staan in git; de waarden staan op de VM in ~/appportal/.env. Per sleutel van app-regie de naam in
# .env waar de waarde vandaan komt: ha-projecten toetst tegen zijn eigen AGENTS_TOKEN, en die waarde staat al als
# HA_PROJECTEN_TOKEN in .env (voor app-locatie).
GEHEIMEN = {
    "REGIE_DB_URL": "REGIE_DB_URL",
    "REGIE_SECRET_KEY": "REGIE_SECRET_KEY",
    "REGIE_PROXY_GEHEIM": "REGIE_PROXY_GEHEIM",
    "REGIE_AGENTS_TOKEN": "REGIE_AGENTS_TOKEN",
    "REGIE_HA_PROJECTEN_TOKEN": "HA_PROJECTEN_TOKEN",
    "REGIE_MAC_TOKEN": "REGIE_MAC_TOKEN",
}
# De hele omgeving van app-regie. Wat geen vast intern adres, poort of domein is, staat er als ${NAAM:-}; een extra
# sleutel (een tweede geheim, een letterlijke waarde) valt hier op.
OMGEVING = {
    "PORT": "3042",
    **{sleutel: f"${{{bron}:-}}" for sleutel, bron in GEHEIMEN.items()},
    "REGIE_GROUPS": "${REGIE_GROUPS:-regie-mehdi}",
    "MIJNAGENTS_URL": "http://app-mijnagents:3022",
    "HA_PROJECTEN_URL": "http://app-ha-projecten:3140",
    "BASE_DOMAIN": "${BASE_DOMAIN:-globaal.be}",
}
# De sleutels van de dienst. Daarbuiten valt alles af: ports, volumes, env_file, secrets, devices, pid, ipc, user,
# privileged, cap_add, network_mode, extra_hosts.
DIENST = {"build", "image", "restart", "environment", "healthcheck", "networks"}
# De vhost 84-regie, opdracht per opdracht (zonder commentaar, witruimte genormaliseerd).
VHOST = [
    "map $host $regie_proxy_geheim {",
    'default "";',
    '"regie.${BASE_DOMAIN}" "${REGIE_PROXY_GEHEIM}";',
    "}",
    "limit_req_zone $binary_remote_addr zone=regie_mac_zone:1m rate=30r/m;",
    "server {",
    "listen 443 ssl;",
    "http2 on;",
    "server_name regie.${BASE_DOMAIN};",
    "include /etc/nginx/snippets/ssl.conf;",
    'add_header X-Robots-Tag "noindex, nofollow" always;',
    'add_header X-Content-Type-Options "nosniff" always;',
    "set $app_upstream http://app-regie:3042;",
    "location = /api/mac {",
    "limit_except POST {",
    "deny all;",
    "}",
    "limit_req zone=regie_mac_zone burst=10 nodelay;",
    "client_max_body_size 256k;",
    "proxy_set_header Host $host;",
    "proxy_set_header X-Forwarded-Proto https;",
    "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
    *[f'proxy_set_header X-authentik-{identiteit} "";' for identiteit in IDENTITEIT],
    'proxy_set_header X-Regie-Proxy-Geheim "";',
    "proxy_pass $app_upstream;",
    "}",
    "include /etc/nginx/snippets/forward-auth.conf;",
    "}",
]
# Migratie 197 zonder commentaar. Een GRANT, ALTER ROLE of ALTER DEFAULT PRIVILEGES erbij, in welke schrijfwijze ook,
# valt hier op.
MIGRATIE_197 = """
BEGIN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'regie') THEN
        CREATE ROLE regie LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS regie AUTHORIZATION regie;
REVOKE ALL ON SCHEMA regie FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA regie TO regie;
ALTER ROLE regie SET search_path = regie;
COMMIT;
"""
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


def opdrachten(tekst: str) -> list[str]:
    """De nginx-opdrachten op een rij: 'naam arg;', 'naam arg {' en '}', met ${NAAM} van envsubst als één stuk."""
    stukken = re.findall(r"(?:\$\{\w+\}|[^;{}])*[;{]|\}", tekst)
    return [" ".join(stuk.split()) for stuk in stukken if stuk.strip()]


def sql_genormaliseerd(tekst: str) -> str:
    return " ".join(re.sub(r"--[^\n]*", "", tekst).split())


class RegieInfra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overlay = yaml.safe_load((ROOT / "docker-compose.regie.yml").read_text())
        cls.app = cls.overlay["services"]["app-regie"]
        cls.stack = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]
        cls.nginx_env = cls.stack["nginx"]["environment"]
        cls.template = zonder_commentaar((ROOT / "nginx/templates/84-regie.conf.template").read_text())
        cls.snippet = zonder_commentaar((ROOT / "nginx/snippets/forward-auth.conf").read_text())
        cls.migratie = (ROOT / "db/migrations/197-regie.sql").read_text()
        cls.catalogus = next(app for app in lees() if app.id == "regie")

    # --- overlay docker-compose.regie.yml ---

    def test_overlay_raakt_alleen_app_regie(self):
        self.assertEqual(set(self.overlay), {"services"})
        self.assertEqual(set(self.overlay["services"]), {"app-regie"})

    def test_geen_hostpoort_geen_volume_alleen_appnet(self):
        self.assertEqual(set(self.app), DIENST, "andere sleutels op app-regie dan afgesproken")
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
        for sleutel, bron in GEHEIMEN.items():
            self.assertEqual(env.get(sleutel), f"${{{bron}:-}}", f"{sleutel} hoort zonder waarde in git")
        # De bronnen alleen over het interne netwerk, nooit via een publieke host; en verder niets.
        self.assertEqual(env, OMGEVING)

    def test_ha_projecten_heeft_een_eigen_token(self):
        # ha-projecten en mijnagents zetten hun AGENTS_TOKEN elk apart; één naam voor beide valt stil uit zodra er één
        # roteert. app-locatie leest dezelfde HA_PROJECTEN_TOKEN.
        env = self.app["environment"]
        self.assertNotEqual(env["REGIE_HA_PROJECTEN_TOKEN"], env["REGIE_AGENTS_TOKEN"])
        self.assertEqual(self.stack["app-locatie"]["environment"]["HA_PROJECTEN_TOKEN"],
                         env["REGIE_HA_PROJECTEN_TOKEN"])

    # --- vhost 84-regie.conf.template ---

    def test_vhost_precies_zoals_afgesproken(self):
        self.assertEqual(opdrachten(self.template), VHOST)

    def test_vhost_gaat_naar_app_regie_achter_forward_auth(self):
        self.assertEqual(len(list((ROOT / "nginx/templates").glob("*-regie.conf.template"))), 1)
        self.assertIn("server_name regie.${BASE_DOMAIN};", self.template)
        self.assertIn("set $app_upstream http://app-regie:3042;", self.template)
        insluitingen = [regel for regel in opdrachten(self.template) if regel.startswith("include ")]
        self.assertEqual(insluitingen, ["include /etc/nginx/snippets/ssl.conf;",
                                        "include /etc/nginx/snippets/forward-auth.conf;"])

    def test_api_mac_is_de_enige_eigen_locatie(self):
        locaties = re.findall(r"^\s*location\s+([^{]+?)\s*\{", self.template, re.M)
        self.assertEqual(locaties, ["= /api/mac"])

    def test_api_mac_alleen_post_klein_en_zonder_identiteit(self):
        mac = blok(self.template, "location = /api/mac {")
        self.assertRegex(mac, r"limit_except\s+POST\s*\{\s*deny\s+all;\s*\}")
        self.assertIn("limit_req zone=regie_mac_zone burst=10 nodelay;", mac)
        self.assertIn("client_max_body_size 256k;", mac)
        for identiteit in IDENTITEIT:
            # Precies één keer en leeg; HTTP-koppen zijn hoofdletterongevoelig, dus ook x-authentik-... telt mee.
            koppen = re.findall(rf"proxy_set_header\s+X-authentik-{identiteit}\s+([^;]*);", mac, re.I)
            self.assertEqual(koppen, ['""'], identiteit)
        self.assertEqual(re.findall(r"proxy_set_header\s+X-Regie-Proxy-Geheim\s+([^;]*);", mac, re.I), ['""'])
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
            koppen = re.findall(rf"proxy_set_header\s+X-authentik-{identiteit}\s+([^;]*);", rest, re.I)
            self.assertEqual(koppen, [f"$authentik_{identiteit}"], identiteit)
        self.assertIn("proxy_pass $app_upstream;", rest)

    def test_proxygeheim_alleen_naar_regie_en_alleen_na_forward_auth(self):
        kaart = opdrachten(blok(self.template, "map $host $regie_proxy_geheim {"))
        self.assertEqual(kaart, ['default "";', '"regie.${BASE_DOMAIN}" "${REGIE_PROXY_GEHEIM}";'])
        # In de template alleen in de map; de kop zelf zet forward-auth.conf, in location / en nergens anders.
        self.assertEqual(self.template.count("$regie_proxy_geheim"), 1)
        rest = blok(self.snippet, "location / {")
        self.assertIn("proxy_set_header X-Regie-Proxy-Geheim $regie_proxy_geheim;", rest)
        self.assertEqual(len(re.findall(r"X-Regie-Proxy-Geheim", self.snippet, re.I)), 1)
        # nginx en app-regie lezen dezelfde naam uit .env, zonder waarde in git.
        self.assertEqual(self.nginx_env.get("REGIE_PROXY_GEHEIM"), "${REGIE_PROXY_GEHEIM:-}")
        self.assertEqual(self.app["environment"]["REGIE_PROXY_GEHEIM"], "${REGIE_PROXY_GEHEIM:-}")

    def test_envsubst_kent_elke_naam_van_de_template(self):
        # De nginx-image vult alleen namen in die in zijn omgeving staan. Een onbekende ${NAAM} blijft staan, nginx leest
        # die als onbekende variabele en start niet; daarom staat REGIE_PROXY_GEHEIM bij nginx in docker-compose.yml,
        # dat altijd geladen wordt, en niet in de overlay.
        namen = set(re.findall(r"\$\{(\w+)\}", self.template))
        self.assertEqual(namen, {"BASE_DOMAIN", "REGIE_PROXY_GEHEIM"})
        self.assertEqual(namen - set(self.nginx_env), set())

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

    def test_migratie_precies_zoals_afgesproken(self):
        self.assertEqual(sql_genormaliseerd(self.migratie), sql_genormaliseerd(MIGRATIE_197))

    def test_migratie_rol_zonder_wachtwoord_en_eigen_schema(self):
        self.assertNotRegex(self.migratie, re.compile(r"password", re.I))
        sql = sql_genormaliseerd(self.migratie)
        self.assertIn("CREATE ROLE regie LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;", sql)
        self.assertIn("CREATE SCHEMA IF NOT EXISTS regie AUTHORIZATION regie;", sql)
        self.assertIn("REVOKE ALL ON SCHEMA regie FROM PUBLIC;", sql)
        # Geen rechten op andere schema's of rollen, in welke schrijfwijze of inspringing ook: één GRANT, over schema
        # regie naar de rol regie, en ALTER ROLE alleen voor het search_path.
        self.assertEqual(re.findall(r"\bgrant\b[^;]*;", sql, re.I), ["GRANT USAGE, CREATE ON SCHEMA regie TO regie;"])
        self.assertEqual(re.findall(r"\balter\s+role\b[^;]*;", sql, re.I), ["ALTER ROLE regie SET search_path = regie;"])
        self.assertNotRegex(sql, re.compile(r"default\s+privileges|pg_(read|write)_all_data", re.I))

    # --- .gitignore: het live Mac-token mag nooit in deze publieke repo ---

    def test_gitignore_noemt_checkout_en_mac_token(self):
        regels = (ROOT / ".gitignore").read_text().splitlines()
        self.assertIn("/regie/", regels)
        self.assertIn("/regie-mac-token", regels)
        self.assertEqual([regel for regel in regels if regel.lstrip().startswith("!") and "regie" in regel], [])

    def test_git_negeert_via_de_gevolgde_gitignore(self):
        if not shutil.which("git") or subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT, capture_output=True).returncode:
            self.skipTest("geen git-werkboom (bijvoorbeeld een git archive)")
        for pad in ("regie-mac-token", "regie/app/__init__.py"):
            # Zonder -v is rc 0 alleen als het pad echt genegeerd wordt. Met -v geeft ook een !-regel rc 0: die regel
            # past, maar heft het negeren op.
            genegeerd = subprocess.run(["git", "check-ignore", "-q", "--no-index", pad], cwd=ROOT)
            self.assertEqual(genegeerd.returncode, 0, f"{pad} wordt niet genegeerd")
            # -v noemt de bron van de regel: .gitignore, niet .git/info/exclude (die zit niet in versiebeheer).
            resultaat = subprocess.run(["git", "check-ignore", "-v", "--no-index", pad],
                                       cwd=ROOT, text=True, capture_output=True)
            bron, _, patroon = resultaat.stdout.split("\t", 1)[0].split(":", 2)
            self.assertEqual(bron, ".gitignore", resultaat.stdout)
            self.assertFalse(patroon.startswith("!"), resultaat.stdout)
        gevolgd = subprocess.run(["git", "ls-files", "--", "regie", "regie-mac-token"],
                                 cwd=ROOT, text=True, capture_output=True, check=True)
        self.assertEqual(gevolgd.stdout, "")

    # --- de grendel zelf draait bij elke wijziging aan deze bestanden, en blokkeert ---

    def test_workflow_bewaakt_alle_bestanden_van_deze_test(self):
        workflow = yaml.safe_load(WORKFLOW.read_text())
        # PyYAML leest de sleutel `on` als True (YAML 1.1).
        aanleiding = workflow.get("on", workflow.get(True))
        nodig = {".gitignore", "apps.yaml", "docker-compose.yml", "docker-compose.regie.yml",
                 "nginx/templates/*-regie.conf.template", "nginx/snippets/forward-auth.conf",
                 "db/migrations/197-regie.sql", "scripts/appcatalogus.py", "scripts/apps-ontbrekend.py",
                 "scripts/test_regie_infra.py", ".github/workflows/regiebord-grendels.yml"}
        for gebeurtenis in ("push", "pull_request"):
            self.assertEqual(nodig - set(aanleiding[gebeurtenis]["paths"]), set(), gebeurtenis)
        stappen = [stap for job in workflow["jobs"].values() for stap in job["steps"]]
        self.assertIn("python3 scripts/test_regie_infra.py", [stap.get("run", "") for stap in stappen])
        # Een rode grendel mag de CI niet groen laten: geen continue-on-error en geen voorwaarde op job of stap.
        for knoop in [*workflow["jobs"].values(), *stappen]:
            self.assertNotIn("continue-on-error", knoop)
            self.assertNotIn("if", knoop)


if __name__ == "__main__":
    unittest.main(verbosity=2)

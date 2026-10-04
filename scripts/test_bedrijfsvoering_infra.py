#!/usr/bin/env python3
"""Configuratiegrendels voor de additieve Bedrijfsvoering-aansluiting.

Geen verbinding met de VM of Authentik; geen .env of geheimen worden gelezen.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from appcatalogus import lees  # noqa: E402


class BedrijfsvoeringInfra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overlay = yaml.safe_load((ROOT / "docker-compose.bedrijfsvoering.yml").read_text())
        cls.app = cls.overlay["services"]["app-bedrijfsvoering"]
        cls.template = (ROOT / "nginx/templates/76-bedrijfsvoering.conf.template").read_text()
        cls.snippet = (ROOT / "nginx/snippets/forward-auth-bedrijfsvoering.conf").read_text()
        cls.catalogue = next(app for app in lees() if app.id == "bedrijfsvoering")

    def test_overlay_changes_only_new_app_and_nginx_environment(self):
        self.assertEqual(set(self.overlay["services"]), {"app-bedrijfsvoering", "nginx"})
        self.assertEqual(set(self.overlay["services"]["nginx"]), {"environment"})
        self.assertEqual(set(self.overlay["services"]["nginx"]["environment"]),
                         {"BEDRIJFSVOERING_PROXY_SECRET"})

    def test_application_has_no_public_ports_or_privileged_network(self):
        self.assertNotIn("ports", self.app)
        self.assertNotIn("network_mode", self.app)
        self.assertNotIn("privileged", self.app)
        self.assertEqual(self.app["networks"], ["appnet"])
        self.assertEqual(self.app["environment"]["PORT"], "3140")
        self.assertIn("http://app-bedrijfsvoering:3140", self.template)

    def test_virtual_machine_uses_only_the_prebuilt_runtime(self):
        self.assertEqual(self.app["build"]["context"], "./bedrijfsvoering")
        self.assertEqual(self.app["build"]["dockerfile"], "Dockerfile.prebuilt")

    def test_persistence_and_read_only_company_seed_are_mandatory(self):
        self.assertIn("bedrijfsvoering-data:/data", self.app["volumes"])
        self.assertIn("./bedrijfsvoering-config/company-seed.json:/config/companies.json:ro",
                      self.app["volumes"])
        self.assertIn("bedrijfsvoering-data", self.overlay["volumes"])
        self.assertEqual(self.app["environment"]["DATA_DIR"], "/data")
        self.assertEqual(self.app["environment"]["COMPANY_SEED_PATH"], "/config/companies.json")

    def test_owner_and_proxy_secret_have_no_silent_defaults(self):
        env = self.app["environment"]
        self.assertTrue(env["AUTHENTIK_OWNER_UID"].startswith("${BEDRIJFSVOERING_OWNER_UID:?"))
        self.assertTrue(env["BEDRIJFSVOERING_PROXY_SECRET"].startswith("${BEDRIJFSVOERING_PROXY_SECRET:?"))
        self.assertEqual(env["BEDRIJFSVOERING_PROXY_SECRET"],
                         self.overlay["services"]["nginx"]["environment"]["BEDRIJFSVOERING_PROXY_SECRET"])
        self.assertEqual(env["AUTH_PROVIDER"], "authentik")
        self.assertEqual(env["AUTHENTIK_REQUIRED_GROUP"], "bedrijfsvoering")
        self.assertEqual(env["PUBLIC_ORIGIN"], "https://bedrijfsvoering.${BASE_DOMAIN:-globaal.be}")

    def test_catalogue_opens_only_the_app_group_and_skips_generator(self):
        self.assertEqual(self.catalogue.rollen, ["bedrijfsvoering"])
        self.assertEqual(self.catalogue.status, "active")
        self.assertEqual(self.catalogue.url, "https://bedrijfsvoering.globaal.be")
        self.assertIsNone(self.catalogue.poort)
        result = subprocess.run([sys.executable, str(ROOT / "scripts/apps-ontbrekend.py")],
                                cwd=ROOT, text=True, capture_output=True, check=True)
        self.assertNotIn("bedrijfsvoering", result.stdout.splitlines())

    def test_template_uses_own_forward_auth_and_scoped_secret_map(self):
        self.assertIn("server_name bedrijfsvoering.${BASE_DOMAIN};", self.template)
        self.assertIn("include /etc/nginx/snippets/ssl.conf;", self.template)
        self.assertIn("include /etc/nginx/snippets/forward-auth-bedrijfsvoering.conf;", self.template)
        self.assertIn('default "";', self.template)
        self.assertIn('"bedrijfsvoering.${BASE_DOMAIN}" "${BEDRIJFSVOERING_PROXY_SECRET}";', self.template)
        self.assertNotIn("${BEDRIJFSVOERING_PROXY_SECRET}", self.snippet)
        self.assertEqual(len(list((ROOT / "nginx/templates").glob("*-bedrijfsvoering.conf.template"))), 1)

    def test_every_application_request_gets_authentik_identity_and_secret(self):
        location = re.search(r"location / \{(.*?)\n\}", self.snippet, re.S)
        self.assertIsNotNone(location)
        content = location.group(1)
        self.assertIn("auth_request /outpost.goauthentik.io/auth/nginx;", content)
        self.assertIn("error_page 401 = @goauthentik_proxy_signin;", content)
        for identity in ("username", "groups", "email", "name", "uid"):
            self.assertIn(f"auth_request_set $authentik_{identity} $upstream_http_x_authentik_{identity};", content)
            self.assertIn(f"proxy_set_header X-authentik-{identity} $authentik_{identity};", content)
        self.assertIn("proxy_set_header X-Bedrijfsvoering-Proxy-Secret $bedrijfsvoering_proxy_geheim;", content)
        self.assertIn("proxy_pass $app_upstream;", content)

    def test_former_sites_identity_headers_are_removed(self):
        for name in ("id", "email", "full-name", "full-name-encoding"):
            self.assertIn(f'proxy_set_header oai-authenticated-user-{name} "";', self.snippet)
        self.assertNotIn("$http_x_authentik", self.snippet)
        self.assertNotIn("$http_oai_authenticated", self.snippet)

    def test_authentication_redirect_and_outpost_preserve_the_url(self):
        self.assertIn("location /outpost.goauthentik.io {", self.snippet)
        self.assertIn("set $outpost_backend http://authentik-server:9000;", self.snippet)
        self.assertIn("proxy_set_header X-Original-URL $scheme://$http_host$request_uri;", self.snippet)
        self.assertIn("return 302 /outpost.goauthentik.io/start?rd=$sso_terug;", self.snippet)

    def test_health_checks_the_durable_runtime(self):
        self.assertEqual(self.app["restart"], "unless-stopped")
        self.assertEqual(self.app["healthcheck"]["test"][:2], ["CMD", "node"])
        self.assertIn("http://127.0.0.1:3140/api/health", self.app["healthcheck"]["test"][-1])
        self.assertGreaterEqual(self.app["healthcheck"]["retries"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)

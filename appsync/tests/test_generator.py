import yaml

import generator
from manifest import load_manifest


def _m(**over):
    base = {"id": "demo", "name": "Demo", "subdomain": "demo", "port": 8080}
    base.update(over)
    return load_manifest(base, repo_name="demo")


def test_app_entry():
    entry = generator.app_entry(_m(description="d", roles=["demo", "admin"]))
    assert entry["id"] == "demo"
    assert entry["status"] == "active"
    assert entry["generated_by"] == "appsync"
    assert entry["roles"] == ["demo", "admin"]


def test_app_entry_yaml_roundtrips():
    doc = yaml.safe_load(generator.app_entry_yaml(_m()))
    assert doc["apps"][0]["subdomain"] == "demo"


def test_nginx_block_shape():
    block = generator.nginx_block(_m(subdomain="stage", port=8501))
    assert "server_name stage.${BASE_DOMAIN};" in block
    assert "set $app_upstream http://app-demo:8501;" in block
    assert "include /etc/nginx/snippets/forward-auth.conf;" in block


def test_nginx_block_custom_upstream():
    block = generator.nginx_block(_m(upstream="host.docker.internal:5000"))
    assert "http://host.docker.internal:5000;" in block


def test_nginx_file_is_sorted_and_headed():
    out = generator.nginx_file([_m(id="zeta", subdomain="zeta"),
                                _m(id="alpha", subdomain="alpha")])
    assert out.startswith("# AUTO-GENERATED")
    assert out.index("alpha.${BASE_DOMAIN}") < out.index("zeta.${BASE_DOMAIN}")


def test_merge_subdomains_dedup_sorted():
    out = generator.merge_subdomains(
        ["omv", "stage"], [_m(id="a", subdomain="alpha"), _m(id="s", subdomain="stage")]
    )
    assert out == ["alpha", "omv", "stage"]  # deduped + sorted


def test_authentik_blueprint_valid_yaml():
    bp = generator.authentik_blueprint(_m(subdomain="stage", maker="angela"),
                                       base_domain="globaal.be")
    doc = yaml.safe_load(bp)
    models = [e["model"] for e in doc["entries"]]
    assert "authentik_providers_proxy.proxyprovider" in models
    assert "authentik_core.application" in models
    assert "authentik_policies.policybinding" in models
    assert "authentik_core.user" in models  # maker attached
    # Base domain is baked into the external host (no interpolation tags).
    proxy = next(e for e in doc["entries"]
                 if e["model"] == "authentik_providers_proxy.proxyprovider")
    assert proxy["attrs"]["external_host"] == "https://stage.globaal.be"


def test_authentik_blueprint_without_maker_has_no_user_entry():
    doc = yaml.safe_load(generator.authentik_blueprint(_m()))
    assert "authentik_core.user" not in [e["model"] for e in doc["entries"]]

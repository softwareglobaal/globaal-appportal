import yaml

from manifest import load_manifest
from register import Registry


def _m(**over):
    base = {"id": "demo", "name": "Demo", "subdomain": "demo", "port": 8080}
    base.update(over)
    return load_manifest(base, repo_name="demo")


def test_apply_writes_all_artifacts(tmp_path):
    reg = Registry(tmp_path)
    written = reg.apply(_m(maker="angela"))

    tile = tmp_path / "apps.d" / "demo.yaml"
    assert tile.is_file()
    doc = yaml.safe_load(tile.read_text())
    assert doc["apps"][0]["id"] == "demo"
    assert doc["apps"][0]["_appsync"]["port"] == 8080

    assert (tmp_path / "nginx/templates/50-autoapps.conf.template").is_file()
    assert "demo" in (tmp_path / "certs/extra-subdomains").read_text()
    assert (tmp_path / "authentik/blueprints/demo.yaml").is_file()
    assert written["tile"] == "apps.d/demo.yaml"


def test_apply_is_idempotent(tmp_path):
    reg = Registry(tmp_path)
    reg.apply(_m())
    first = (tmp_path / "nginx/templates/50-autoapps.conf.template").read_text()
    reg.apply(_m())  # same app again
    second = (tmp_path / "nginx/templates/50-autoapps.conf.template").read_text()
    assert first == second
    # exactly one app file
    assert len(list((tmp_path / "apps.d").glob("*.yaml"))) == 1


def test_two_apps_then_remove_one(tmp_path):
    reg = Registry(tmp_path)
    reg.apply(_m(id="alpha", subdomain="alpha"))
    reg.apply(_m(id="beta", subdomain="beta"))

    nginx = (tmp_path / "nginx/templates/50-autoapps.conf.template").read_text()
    assert "alpha.${BASE_DOMAIN}" in nginx and "beta.${BASE_DOMAIN}" in nginx
    sans = (tmp_path / "certs/extra-subdomains").read_text().split()
    assert sorted(sans) == ["alpha", "beta"]

    reg.remove("alpha")
    nginx = (tmp_path / "nginx/templates/50-autoapps.conf.template").read_text()
    assert "alpha.${BASE_DOMAIN}" not in nginx and "beta.${BASE_DOMAIN}" in nginx
    assert not (tmp_path / "apps.d/alpha.yaml").exists()
    assert (tmp_path / "certs/extra-subdomains").read_text().split() == ["beta"]


def test_round_trips_through_apps_d(tmp_path):
    # apply -> list_manifests reconstructs faithfully (port/upstream/maker survive).
    reg = Registry(tmp_path)
    reg.apply(_m(id="x", subdomain="x", port=9000, upstream="10.0.0.5:9000", maker="bob"))
    [m] = reg.list_manifests()
    assert m.id == "x" and m.port == 9000
    assert m.resolved_upstream() == "10.0.0.5:9000"
    assert m.maker == "bob"

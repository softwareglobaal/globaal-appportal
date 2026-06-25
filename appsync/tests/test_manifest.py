import pytest

from manifest import ManifestError, load_manifest, load_manifest_text, slugify


def test_slugify():
    assert slugify("Stage Beoordeling!") == "stage-beoordeling"
    assert slugify("My__Cool  App") == "my-cool-app"


def test_full_manifest():
    m = load_manifest(
        {
            "id": "stagebeoordeling",
            "name": "Stagebeoordeling",
            "subdomain": "stage",
            "port": 8080,
            "roles": ["stagebeoordeling", "admin"],
            "maker": "angela",
        },
        repo_name="stage-app",
    )
    assert m.id == "stagebeoordeling"
    assert m.subdomain == "stage"
    assert m.port == 8080
    assert m.maker == "angela"
    assert m.resolved_upstream() == "app-stagebeoordeling:8080"


def test_inference_from_repo_name():
    # No id/name/subdomain/roles given -> inferred from the repo name.
    m = load_manifest({"port": 3000}, repo_name="Cool-Tool")
    assert m.id == "cool-tool"
    assert m.subdomain == "cool-tool"
    assert m.name == "Cool Tool"
    assert m.roles == ["cool-tool", "admin"]  # maker group + admins


def test_missing_port_rejected():
    with pytest.raises(ManifestError):
        load_manifest({"id": "x"}, repo_name="x")


def test_reserved_subdomain_rejected():
    with pytest.raises(ManifestError):
        load_manifest({"subdomain": "auth", "port": 8080}, repo_name="x")


def test_invalid_id_rejected():
    with pytest.raises(ManifestError):
        load_manifest({"id": "Bad_Id", "port": 8080}, repo_name="x")


def test_empty_roles_rejected():
    with pytest.raises(ManifestError):
        load_manifest({"port": 8080, "roles": []}, repo_name="x")


def test_bad_yaml_text_rejected():
    with pytest.raises(ManifestError):
        load_manifest_text("just: [a, b", repo_name="x")  # unbalanced bracket


def test_text_must_be_mapping():
    with pytest.raises(ManifestError):
        load_manifest_text("- a\n- b\n", repo_name="x")

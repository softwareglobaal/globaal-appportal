import io
import urllib.error

import pytest

from deployer import GitHubDeployer, LoggingDeployer


def test_logging_deployer_fetch_is_none():
    assert LoggingDeployer().fetch_manifest("org/app", "main") is None


def test_github_deployer_builds_request_and_returns_body(monkeypatch):
    seen = {}

    class FakeResp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["auth"] = req.get_header("Authorization")
        return FakeResp(b"id: x\nport: 8080\n")

    monkeypatch.setattr("deployer.urllib.request.urlopen", fake_urlopen)
    out = GitHubDeployer("tok123").fetch_manifest("org/cool-app", "claude/edit")

    assert out == "id: x\nport: 8080\n"
    assert "/repos/org/cool-app/contents/appportal.yaml" in seen["url"]
    assert "ref=claude%2Fedit" in seen["url"]  # branch slash is encoded
    assert seen["auth"] == "Bearer tok123"


def test_github_deployer_404_returns_none(monkeypatch):
    def fake_urlopen(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr("deployer.urllib.request.urlopen", fake_urlopen)
    assert GitHubDeployer("t").fetch_manifest("org/app", "main") is None


def test_github_deployer_other_http_error_raises(monkeypatch):
    def fake_urlopen(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 500, "boom", {}, None)

    monkeypatch.setattr("deployer.urllib.request.urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError):
        GitHubDeployer("t").fetch_manifest("org/app", "main")

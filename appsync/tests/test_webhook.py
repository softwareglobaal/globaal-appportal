import hashlib
import hmac
import importlib
import json
import os

import pytest


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("APPSYNC_WEBHOOK_SECRET", "topsecret")
    monkeypatch.setenv("APPSYNC_REPO_ROOT", str(tmp_path))
    monkeypatch.delenv("APPSYNC_MODE", raising=False)
    import app as app_mod
    importlib.reload(app_mod)  # pick up the patched env
    app_mod.app.config["TESTING"] = True
    return app_mod.app.test_client()


def _sign(body: bytes, secret="topsecret"):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_rejects_bad_signature(client):
    body = json.dumps({"ref": "refs/heads/main"}).encode()
    r = client.post("/webhook", data=body,
                    headers={"X-Hub-Signature-256": "sha256=deadbeef",
                             "X-GitHub-Event": "push"})
    assert r.status_code == 401


def test_ping_pong(client):
    body = b"{}"
    r = client.post("/webhook", data=body,
                    headers={"X-Hub-Signature-256": _sign(body),
                             "X-GitHub-Event": "ping"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "pong"


def test_ignores_unwatched_branch(client):
    body = json.dumps(
        {"ref": "refs/heads/feature/x", "repository": {"full_name": "org/app"}}
    ).encode()
    r = client.post("/webhook", data=body,
                    headers={"X-Hub-Signature-256": _sign(body),
                             "X-GitHub-Event": "push"})
    assert r.get_json()["status"] == "ignored"


def test_queues_watched_push(client):
    body = json.dumps(
        {"ref": "refs/heads/claude/edit", "repository": {"full_name": "org/coolapp"}}
    ).encode()
    r = client.post("/webhook", data=body,
                    headers={"X-Hub-Signature-256": _sign(body),
                             "X-GitHub-Event": "push"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "queued"


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"

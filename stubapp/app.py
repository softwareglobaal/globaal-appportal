"""Minimal stub application.

Stands in for a real internal app to demonstrate the SSO click-through.
It never sees a login: Authentik's forward auth (via nginx auth_request)
guarantees every request is authenticated, and the identity arrives in
X-authentik-* headers.
"""
import os

from flask import Flask, render_template, request

app = Flask(__name__)

APP_NAME = os.environ.get("APP_NAME", "StubApp")
APP_DESCRIPTION = os.environ.get("APP_DESCRIPTION", "")
APP_STATUS = os.environ.get("APP_STATUS", "")
# Optional banner, e.g. for placeholder tiles whose real backend lives elsewhere.
APP_NOTE = os.environ.get("APP_NOTE", "")
BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "localhost")


@app.route("/")
def index():
    return render_template(
        "index.html",
        app_name=APP_NAME,
        app_description=APP_DESCRIPTION,
        app_status=APP_STATUS,
        app_note=APP_NOTE,
        portal_url=f"https://portal.{BASE_DOMAIN}/",
        username=request.headers.get("X-authentik-username", "unknown"),
        email=request.headers.get("X-authentik-email", ""),
        groups=request.headers.get("X-authentik-groups", ""),
    )


@app.route("/healthz")
def healthz():
    return {"status": "ok"}

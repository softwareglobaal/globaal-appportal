"""OMV Pipeline — small REAL test slice (no scraper/Dropbox/OpenAI/VPN).

It reproduces the exact auth structure of the real OMV dashboard
(v1/app.py): a `require_dashboard_login` before_request gate that checks
session["dashboard_auth"]. On top of that it applies the portal SSO bridge
(sso_auth.init_sso). The point is to prove, end to end, that:

  portal tile  ->  Authentik forward auth  ->  this app, already logged in
                   (the app's own login screen is skipped by the shim)

Flip AUTH_MODE=local in docker-compose to see the app's OWN login appear,
which proves the shim is what bridges the two.
"""
import os

from flask import Flask, redirect, render_template, request, session, url_for

from sso_auth import init_sso

app = Flask(__name__)
# Secrets are intentionally inline for now (team decision: wire a secrets
# manager later). Override via env when available.
app.secret_key = os.getenv("FLASK_SECRET_KEY", "omv-demo-dev-key-change-later")
DEMO_PASSWORD = os.getenv("OMV_LOCAL_PASSWORD", "omvdemo")
BASE_DOMAIN = os.getenv("BASE_DOMAIN", "localhost")


# --- this block is copied from the real OMV app (v1/app.py) verbatim --------
@app.before_request
def require_dashboard_login():
    if request.path.startswith("/static") or request.path == "/healthz":
        return None
    if request.path in ("/login", "/logout"):
        return None
    if session.get("dashboard_auth") is True:
        return None
    return redirect(url_for("login"))
# ---------------------------------------------------------------------------


@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        sso_user=session.get("sso_user"),
        sso_email=session.get("sso_email", ""),
        sso_groups=session.get("sso_groups", ""),
        auth_mode=(os.getenv("AUTH_MODE") or "sso"),
        portal_url=f"https://portal.{BASE_DOMAIN}/",
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    # Only ever reached in AUTH_MODE=local (the shim skips it under SSO).
    error = None
    if request.method == "POST":
        if request.form.get("password") == DEMO_PASSWORD:
            session["dashboard_auth"] = True
            return redirect(url_for("dashboard"))
        error = "Onjuist wachtwoord."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("dashboard"))


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


# One line — the whole portal SSO integration. Placed at the very bottom on
# purpose, to prove it works as a drop-in even after the gate is defined.
init_sso(app)

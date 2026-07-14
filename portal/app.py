"""AppPortal - the landing portal.

Authenticates users against Authentik via OIDC (Authlib) and shows the
application tiles the user's role (Authentik group) permits. All identity
management - passwords, TOTP, sessions, users - lives in Authentik.
"""
import logging
import os
from datetime import timedelta
from logging.handlers import RotatingFileHandler

import requests
import yaml
from authlib.integrations.flask_client import OAuth
from flask import Flask, abort, redirect, render_template, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

BASE_DOMAIN = os.environ["BASE_DOMAIN"]
AUTH_BASE = f"https://auth.{BASE_DOMAIN}"
AUTH_API = f"{AUTH_BASE}/api/v3"
APPS_FILE = os.environ.get("APPS_FILE", "/app/apps.yaml")
LOG_FILE = os.environ.get("PORTAL_LOG_FILE", "/var/log/portal/portal.log")
# Read-only Authentik API token (service account) used by the access overview.
# Empty = feature disabled (the page shows a "not configured" notice instead).
AUTHENTIK_API_TOKEN = os.environ.get("AUTHENTIK_API_TOKEN", "").strip()
# Only members of this Authentik group may open the access overview.
ADMIN_GROUP = os.environ.get("PORTAL_ADMIN_GROUP", "admin")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ["PORTAL_SECRET_KEY"],
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PREFERRED_URL_SCHEME="https",
)
# Trust X-Forwarded-* from nginx so url_for(_external=True) builds https URLs.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# --- logging: auth events and app redirects to a logfile (+ stdout) ---------
handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
handler.setFormatter(formatter)
stream = logging.StreamHandler()
stream.setFormatter(formatter)
events = logging.getLogger("portal.events")
events.setLevel(logging.INFO)
events.addHandler(handler)
events.addHandler(stream)

# --- OIDC client -------------------------------------------------------------
oauth = OAuth(app)
oauth.register(
    name="authentik",
    client_id=os.environ["OIDC_CLIENT_ID"],
    client_secret=os.environ["OIDC_CLIENT_SECRET"],
    server_metadata_url=f"{AUTH_BASE}/application/o/portal/.well-known/openid-configuration",
    client_kwargs={"scope": "openid profile email"},
)


def load_apps():
    with open(APPS_FILE, encoding="utf-8") as fh:
        return yaml.safe_load(fh)["apps"]


def current_user():
    return session.get("user")


def is_admin(user):
    return ADMIN_GROUP in set((user or {}).get("groups", []))


def fetch_group_members():
    """Map every Authentik group name to its member users.

    Returns {group_name: [{username, name, email, is_active}, ...]}.
    Raises requests.RequestException on transport/HTTP errors so the caller
    can show a clear message instead of a half-empty table.
    """
    headers = {"Authorization": f"Bearer {AUTHENTIK_API_TOKEN}"}
    members = {}
    page = 1
    while True:
        resp = requests.get(
            f"{AUTH_API}/core/groups/",
            headers=headers,
            params={"include_users": "true", "page": page, "page_size": 100},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        for group in data.get("results", []):
            members[group["name"]] = [
                {
                    "username": u.get("username"),
                    "name": u.get("name", ""),
                    "email": u.get("email", ""),
                    "is_active": u.get("is_active", True),
                }
                for u in group.get("users_obj", [])
            ]
        # Authentik paginates with a numeric next-page index (0 = last page).
        nxt = (data.get("pagination") or {}).get("next") or 0
        if not nxt:
            return members
        page = nxt


@app.route("/")
def index():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    groups = set(user.get("groups", []))
    tiles = [
        {**a, "url": f"https://{a['subdomain']}.{BASE_DOMAIN}/"}
        for a in load_apps()
        if groups & set(a.get("roles", []))
    ]
    return render_template("portal.html", user=user, tiles=tiles, is_admin=is_admin(user))


@app.route("/login")
def login():
    redirect_uri = url_for("auth_callback", _external=True)
    return oauth.authentik.authorize_redirect(redirect_uri)


@app.route("/auth/callback")
def auth_callback():
    token = oauth.authentik.authorize_access_token()
    claims = token.get("userinfo") or oauth.authentik.userinfo(token=token)
    user = {
        "username": claims.get("preferred_username") or claims.get("sub"),
        "name": claims.get("name", ""),
        "email": claims.get("email", ""),
        "groups": claims.get("groups", []) or [],
    }
    session.clear()
    session.permanent = True  # 8h cap via PERMANENT_SESSION_LIFETIME
    session["user"] = user
    events.info(
        "AUTH_LOGIN user=%s groups=%s", user["username"], ",".join(user["groups"])
    )
    return redirect(url_for("index"))


@app.route("/go/<app_id>")
def go(app_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    target = next((a for a in load_apps() if a["id"] == app_id), None)
    if target is None:
        abort(404)
    if not set(user.get("groups", [])) & set(target.get("roles", [])):
        events.info("ACCESS_DENIED user=%s app=%s", user["username"], app_id)
        abort(403)
    events.info("APP_REDIRECT user=%s app=%s", user["username"], app_id)
    # Plain redirect - SSO continuity comes from the Authentik session cookie
    # checked by forward auth on the app's subdomain. No tokens in URLs.
    return redirect(f"https://{target['subdomain']}.{BASE_DOMAIN}/")


@app.route("/access")
def access_overview():
    """Admin-only: per application, which users can access it.

    Authentik has no native "all effective users for app X" screen - access is
    expressed as group/user bindings. We reconstruct it from apps.yaml (the
    group(s) bound to each app) plus the live group membership from the
    Authentik API, and union the members per app.
    """
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    if not is_admin(user):
        events.info("ACCESS_DENIED user=%s app=access-overview", user["username"])
        abort(403)

    rows, error = [], None
    if not AUTHENTIK_API_TOKEN:
        error = (
            "AUTHENTIK_API_TOKEN is not set, so the portal cannot query "
            "Authentik. See the README (\"Access overview\") to create a "
            "read-only service-account token."
        )
    else:
        try:
            group_members = fetch_group_members()
        except requests.RequestException as exc:
            events.info("ACCESS_OVERVIEW_ERROR user=%s err=%s", user["username"], exc)
            error = f"Could not reach the Authentik API: {exc}"
        else:
            for a in load_apps():
                seen = {}
                for role in a.get("roles", []):
                    for member in group_members.get(role, []):
                        # Dedup across groups; a user in two bound groups counts once.
                        seen.setdefault(member["username"], member)
                rows.append(
                    {
                        "app": a,
                        "groups": a.get("roles", []),
                        "users": sorted(
                            seen.values(),
                            key=lambda m: (m["username"] or "").lower(),
                        ),
                    }
                )
        events.info("ACCESS_OVERVIEW_VIEW user=%s", user["username"])

    return render_template("access.html", user=user, rows=rows, error=error)


@app.route("/logout")
def logout():
    user = current_user()
    if user:
        events.info("AUTH_LOGOUT user=%s", user["username"])
    session.clear()
    # RP-initiated logout: end the Authentik session too (single logout).
    return redirect(f"{AUTH_BASE}/application/o/portal/end-session/")


@app.route("/healthz")
def healthz():
    return {"status": "ok"}

"""SSO shim — bridge Authentik forward-auth headers to an app's own session.

This is the DROP-IN file for the real OMV dashboard. Behind nginx forward auth,
every request to the app carries X-authentik-* headers that the Authentik
embedded outpost sets (and that cannot be spoofed from outside, because the app
is only reachable through nginx, which overwrites any client-supplied copies).
This shim reads those headers and marks the app's session authenticated, so the
app's own login + TOTP screens are skipped — true single sign-on.

How to use in the REAL OMV app (v1/app.py): add ONE block near the bottom,
after `app` and its routes/before_request gate are defined:

    # --- portal SSO bridge -------------------------------------------------
    from sso_auth import init_sso
    init_sso(app)               # session flag defaults to "dashboard_auth"

Nothing else in app.py needs to change. The bridge is controlled by an env var
so the app still runs standalone when you want it to:

    AUTH_MODE=sso     -> trust the headers, skip the app's own login (default)
    AUTH_MODE=local   -> do nothing; the app's own login + TOTP stay in charge

Optional env:
    SSO_SESSION_FLAG     session key the app's gate checks (default dashboard_auth)
    SSO_REQUIRED_GROUP   if set, only users in this Authentik group are let in
                         (the portal already enforces access via the outpost
                         binding, so this is an extra belt-and-braces check)
"""
import os

from flask import request, session

USER_HEADER = "X-authentik-username"
EMAIL_HEADER = "X-authentik-email"
GROUPS_HEADER = "X-authentik-groups"


def _groups_from_header(value):
    # Authentik may join groups with "|" or ","; accept both.
    raw = (value or "").replace(",", "|")
    return [g.strip() for g in raw.split("|") if g.strip()]


def init_sso(app, session_flag=None, required_group=None):
    mode = (os.getenv("AUTH_MODE") or "sso").strip().lower()
    if mode != "sso":
        app.logger.info("sso_auth: AUTH_MODE=%s -> SSO bridge OFF (own login active)", mode)
        return

    flag = session_flag or os.getenv("SSO_SESSION_FLAG", "dashboard_auth")
    req_group = required_group or (os.getenv("SSO_REQUIRED_GROUP") or "").strip()

    def _sso_bridge():
        user = request.headers.get(USER_HEADER)
        if not user:
            # Not behind the outpost (e.g. direct/local access): leave the
            # app's own login gate to handle it.
            return None
        if req_group and req_group not in _groups_from_header(request.headers.get(GROUPS_HEADER)):
            return None  # authenticated by Authentik, but not in the required group
        session[flag] = True
        session["sso_user"] = user
        session["sso_email"] = request.headers.get(EMAIL_HEADER, "")
        session["sso_groups"] = request.headers.get(GROUPS_HEADER, "")
        return None

    # Register, then move to the FRONT so it runs before the app's own auth
    # gate regardless of where init_sso() is called in the file.
    app.before_request(_sso_bridge)
    funcs = app.before_request_funcs.setdefault(None, [])
    funcs.insert(0, funcs.pop())
    app.logger.info("sso_auth: SSO bridge ON (session flag=%s)", flag)

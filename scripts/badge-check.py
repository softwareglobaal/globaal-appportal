"""Verify the maintenance stub renders a humanized badge from the canonical
APP_STATUS=in_development value. Hits the app directly (bypassing forward auth)
with a fake identity header, the way nginx would inject it.
Run: docker compose exec -T app-maintenance python < scripts/badge-check.py
"""
import os
import urllib.request

port = os.environ.get("PORT", "3004")
req = urllib.request.Request(
    f"http://127.0.0.1:{port}/", headers={"X-authentik-username": "probe"}
)
html = urllib.request.urlopen(req).read().decode()
print("APP_STATUS env:", repr(os.environ.get("APP_STATUS")))
print("badge 'in development' shown:", "in development" in html)
print("raw 'in_development' leaked to UI:", "in_development" in html)
print("BADGE_OK" if ("in development" in html and "in_development" not in html) else "BADGE_FAIL")

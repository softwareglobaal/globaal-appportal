"""Runbook 'docker-herstart': herstart één app-container. Zelfde grenzen als de
onderhoudsagent op agents.globaal.be: nooit de kern (postgres, authentik,
nginx, redis), alleen containers die met 'app-' beginnen.
Parameters: {"container": "app-xyz"}"""
import re
import subprocess

KERN = ("postgres", "authentik", "nginx", "redis", "certgen")


def voer_uit(p):
    naam = str(p.get("container", "")).strip()
    if not re.fullmatch(r"app-[a-z0-9-]+", naam):
        raise ValueError(f"'{naam}' is geen app-container (patroon app-<naam>)")
    if any(k in naam for k in KERN):
        raise ValueError(f"'{naam}' hoort bij de kern en wordt nooit herstart")
    uit = subprocess.run(["docker", "restart", naam], capture_output=True, text=True, timeout=120)
    if uit.returncode != 0:
        raise RuntimeError(uit.stderr.strip() or "docker restart mislukte")
    return f"container {naam} herstart", uit.stdout.strip()

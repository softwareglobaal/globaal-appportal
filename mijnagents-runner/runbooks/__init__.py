"""Allowlist van runbooks voor de uitvoerder. Alleen wat hier staat kan ooit
uitgevoerd worden, en dan nog alleen na goedkeuring op het bord.

Een runbook is een functie voer_uit(parameters: dict) -> (detail: str, bewijs: str).
Detail is de neutrale samenvatting voor het bord; bewijs mag technisch zijn.
Nieuw runbook: module hier naast zetten en in RUNBOEKEN opnemen.
"""
from . import notitie, docker_herstart, pipedrive_dealtitel

RUNBOEKEN = {
    "notitie": notitie.voer_uit,
    "docker-herstart": docker_herstart.voer_uit,
    "pipedrive-dealtitel": pipedrive_dealtitel.voer_uit,
}

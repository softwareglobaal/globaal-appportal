"""Runbook 'pipedrive-dealtitel': zet de titel van een H-Architects-deal, bv. om
het projectnummer vóór de klantnaam te zetten (D9: '2616 Kane Downs').
Alleen firma harchitects, alleen het veld title, alleen na goedkeuring op het bord.
Parameters: {"deal_id": 14411, "titel": "2616 Kane Downs"}"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "koppelingen"))
import pipedrive  # noqa: E402
import nummerlezer  # noqa: E402

H_A_BEDRIJF_ID = 10068585   # zelfde grendel als contract-systeem/webapp/pipedrive.py


def voer_uit(p):
    deal_id = int(p.get("deal_id") or 0)
    titel = str(p.get("titel", "")).strip()
    if not deal_id or not titel:
        raise ValueError("deal_id en titel zijn verplicht")
    if not nummerlezer.ha_nummer(titel, "pipedrive_titel") or not re.match(r"^\d{4}\s+\S", titel):
        raise ValueError(f"titel '{titel}' begint niet met een geldig H-A-projectnummer (D9: JJNN of (JJ+30)NN)")
    pipedrive.controleer_bedrijf("harchitects", H_A_BEDRIJF_ID)
    data, kort = pipedrive.schrijf("harchitects", "PUT", f"/deals/{deal_id}", body={"title": titel})
    return f"dealtitel gezet: {titel}", str(kort)[:500]

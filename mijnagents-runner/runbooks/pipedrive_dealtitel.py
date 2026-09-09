"""Runbook 'pipedrive-dealtitel': zet de titel van een H-Architects-deal, bv. om
het projectnummer vóór de klantnaam te zetten (D9: '2616 Kane Downs').
Alleen firma harchitects, alleen het veld title, alleen na goedkeuring op het bord.
Parameters: {"deal_id": 14411, "titel": "2616 Kane Downs"}"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "koppelingen"))
import pipedrive  # noqa: E402


def voer_uit(p):
    deal_id = int(p.get("deal_id") or 0)
    titel = str(p.get("titel", "")).strip()
    if not deal_id or not titel:
        raise ValueError("deal_id en titel zijn verplicht")
    if not re.match(r"^(26|56)\d\d\s+\S", titel):
        raise ValueError(f"titel '{titel}' begint niet met een projectnummer 26xx/56xx")
    data, kort = pipedrive.schrijf("harchitects", "PUT", f"/deals/{deal_id}", body={"title": titel})
    return f"dealtitel gezet: {titel}", str(kort)[:500]

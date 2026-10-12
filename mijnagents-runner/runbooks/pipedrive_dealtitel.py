"""Runbook 'pipedrive-dealtitel': zet de titel van een H-Architects-deal, bv. om
het projectnummer vóór de klantnaam te zetten (D9: '2616 Kane Downs').
Alleen firma harchitects, alleen het veld title, alleen na goedkeuring op het bord.
Parameters: {"deal_id": 14411, "titel": "2616 Kane Downs", "nummer": "2616", "firma": "harchitects"}

WP2b (12-10-2026): vlak vóór de PUT opnieuw op conflict controleren. Eerst het bord (het voorstel is nog
goedgekeurd, heeft een actieve reservering en geen andere deal houdt hetzelfde nummer vast), daarna de vier
vaste bronnen volledig (contractmappen, dashboard, voorbereidingen, Pipedrive). Een bronfout of een nummer
dat inmiddels elders gebruikt is, blokkeert met bewijs: dan volgt er geen schrijfactie. Een ander nummer
wordt een nieuw voorstel voor Mehdi; dit runbook verandert nooit zelf de parameters.
De uitvoerder geeft _voorstel_id en _bord (de bord-API) mee.

Reeds voldaan (12-10-2026): staat exact deze titel al op exact deze H-A-deal, dan volgt geen PUT; het runbook
meldt 'reeds voldaan' met de gelezen titel als bewijs. Een goedgekeurd voorstel van vóór WP2b zonder
reservering mag alleen zo afgesloten worden (reconciliatie); moet er werkelijk iets geschreven worden, dan
blokkeert het en noemt het de herstelactie (opnieuw voorleggen op het bord)."""
import os
import re
import sys

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import pipedrive  # noqa: E402
import nummerlezer  # noqa: E402

H_A_BEDRIJF_ID = 10068585   # zelfde grendel als contract-systeem/webapp/pipedrive.py


class NummerConflict(RuntimeError):
    """Het nummer mag niet (meer) gezet worden; het bewijs staat in de melding."""


def _agent():
    sys.path.insert(0, HIER)
    import contracten_agent  # noqa: E402  (laat: alleen nodig voor de broncontrole)
    return contracten_agent


def voer_uit(p):
    deal_id = int(p.get("deal_id") or 0)
    titel = str(p.get("titel", "")).strip()
    if not deal_id or not titel:
        raise ValueError("deal_id en titel zijn verplicht")
    if not nummerlezer.ha_nummer(titel, "pipedrive_titel") or not re.match(r"^\d{4}\s+\S", titel):
        raise ValueError(f"titel '{titel}' begint niet met een geldig H-A-projectnummer (D9: JJNN of (JJ+30)NN)")
    nummer = titel[:4]
    if p.get("nummer") not in (None, "") and str(p["nummer"]).strip() != nummer:
        raise ValueError(f"nummer {p['nummer']} verschilt van het nummer in de titel ({nummer})")
    if str(p.get("firma") or "harchitects") != "harchitects":
        raise ValueError(f"firma '{p.get('firma')}': dit runbook zet alleen H-Architects-dealtitels")
    vid, bord = p.get("_voorstel_id"), p.get("_bord")
    if not vid or not callable(bord):
        raise NummerConflict("zonder voorstel-id en bord geen controle op conflict: geen schrijfactie")
    try:
        controle = bord(f"/api/nummercontrole?voorstel_id={int(vid)}")
    except Exception as e:  # noqa: BLE001
        raise NummerConflict(f"bord niet bereikbaar voor de nummercontrole ({type(e).__name__}): geen schrijfactie") from e
    if not isinstance(controle, dict):
        raise NummerConflict(f"bord gaf geen geldige controle voor voorstel {vid}: geen schrijfactie")
    reconciliatie = controle.get("ok") is not True and controle.get("reconciliatie") is True
    if controle.get("ok") is not True and not reconciliatie:
        raise NummerConflict(f"bord blokkeert voorstel {vid}: {controle.get('reden', 'geen geldige controle')}")
    if controle.get("nummer") != nummer or str(controle.get("deal_id")) != str(deal_id):
        raise NummerConflict(f"bord kent voorstel {vid} als nummer {controle.get('nummer')} voor deal "
                             f"{controle.get('deal_id')}, niet {nummer} voor deal {deal_id}: geen schrijfactie")
    ca = _agent()
    bewijs = {}
    try:
        ca.nummer_vrij_voor_uitvoering(nummer, deal_id, bewijs)
    except ca.NummerFout as e:
        raise NummerConflict(f"nummer {nummer} niet gezet: {e}") from e
    pipedrive.controleer_bedrijf("harchitects", H_A_BEDRIJF_ID)
    per_bron = ", ".join(f"{k} {v}" for k, v in sorted((bewijs.get("per_bron") or {}).items()))
    deal = pipedrive.get("harchitects", f"/deals/{deal_id}") or {}
    if int(deal.get("id") or 0) != deal_id:
        raise NummerConflict(f"deal {deal_id} niet gelezen in het H-A-account: geen schrijfactie")
    huidig = str(deal.get("title") or "").strip()
    if huidig == titel:
        return (f"reeds voldaan: deal {deal_id} heet al '{titel}'; geen schrijfactie",
                f"controle vooraf: bord {'reconciliatie' if reconciliatie else 'ok'} (voorstel {vid}), bronnen volledig "
                f"gelezen ({per_bron or 'reeks leeg'}); gelezen titel: '{huidig}'")
    if reconciliatie:
        raise NummerConflict(
            f"voorstel {vid} is goedgekeurd zonder reservering (van vóór WP2b) en de titel van deal {deal_id} is "
            f"'{huidig}', niet '{titel}': geen schrijfactie. Herstel: 'Opnieuw voorleggen' op het bord, dan opnieuw "
            f"goedkeuren (dat legt de reservering vast).")
    data, kort = pipedrive.schrijf("harchitects", "PUT", f"/deals/{deal_id}", body={"title": titel})
    return f"dealtitel gezet: {titel}", (f"controle vooraf: bord ok (voorstel {vid}), bronnen volledig gelezen"
                                         f" ({per_bron or 'reeks leeg'}); vorige titel '{huidig}'; antwoord: {str(kort)[:400]}")

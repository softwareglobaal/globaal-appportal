"""Fathom (opnames van online gesprekken), alleen lezen, vanaf de host.
Sleutel(s) bij naam uit ~/appportal/.env: FATHOM_API_KEYS (komma-gescheiden). Mehdi's eigen account: de adressen in
FATHOM_MEHDI_ADRESSEN (komma-gescheiden, geen sleutel), in de code MEHDI_FATHOM_ADRESSEN.
Zelfde API als het contract-dashboard (webapp/fathom_api.py)."""
import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASIS = "https://api.fathom.ai/external/v1"
POGINGEN = int(os.environ.get("FATHOM_POGINGEN", "5"))
PAUZE = float(os.environ.get("FATHOM_PAUZE", "2.5"))  # s tussen pagina's met transcript


def _env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_env("~/appportal/.env")

# Mehdi's eigen Fathom-account (EIGEN-3, M2): alleen deze exacte adressen, in kleine letters, nooit een deel van een adres.
# Gemeten op de VM (21-10-2026): elke eigen opname heeft zoomafspraken@gmail.com, de andere 177 het adres van een ander
# account. Een deelstuk als 'h-architects' of 'mch@' paste ook op het adres van een collega. De Zoomwacht en De Regisseur
# lezen deze ene lijst; zonder waarde in FATHOM_MEHDI_ADRESSEN geldt de standaard.
MEHDI_FATHOM_ADRESSEN = frozenset(a.strip().lower() for a in (os.environ.get("FATHOM_MEHDI_ADRESSEN") or
                                                               "zoomafspraken@gmail.com,mch@h-architects.be").split(",") if a.strip())


def sleutels():
    return [s.strip() for s in os.environ.get("FATHOM_API_KEYS", "").split(",") if s.strip()]


def beschikbaar():
    return bool(sleutels())


def _haal(sleutel, pad, params=None):
    """Een GET met herkansing bij 429 (Fathom: circa 30 zware calls per minuut).
    Wacht de Retry-After af, anders oplopend 10, 20, 40, 80 s; daarna pas de fout doorgeven.
    Een afgebroken antwoord of verbinding (29-10-2026: IncompleteRead midden in een pagina van 600 kB) krijgt
    dezelfde herkansing, met de oplopende pauze."""
    url = f"{BASIS}{pad}" + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"X-Api-Key": sleutel, "Accept": "application/json"})
    wacht = 10
    for poging in range(POGINGEN):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or poging == POGINGEN - 1:
                raise
            try:
                pauze = max(int(e.headers.get("Retry-After", "0")), wacht)
            except ValueError:
                pauze = wacht
            time.sleep(min(pauze, 120))
            wacht *= 2
        except (http.client.IncompleteRead, ConnectionError, TimeoutError, urllib.error.URLError):
            if poging == POGINGEN - 1:
                raise
            time.sleep(wacht)
            wacht *= 2


def gesprekken(sinds_iso, met_transcript=False, tot_iso=None):
    """Alle gesprekken sinds een ISO-tijdstip (tot tot_iso als gegeven), over alle sleutels; met transcript als
    gevraagd. Altijd met de samenvatting en de actiepunten van Fathom (overleg T-0154, 02-11-2026, 3-0): die zijn de
    kern en de taken die Mehdi per gesprek wil zien, en ze kosten geen extra aanroep. default_summary is dan
    {template_name, markdown_formatted} of None, action_items een lijst {description, assignee{name}, completed,
    recording_timestamp, recording_playback_url} of leeg."""
    uit = []
    for s in sleutels():
        cursor = None
        while True:
            params = {"created_after": sinds_iso, "include_transcript": "true" if met_transcript else "false",
                      "include_summary": "true", "include_action_items": "true"}
            if tot_iso:
                params["created_before"] = tot_iso
            if cursor:
                params["cursor"] = cursor
            d = _haal(s, "/meetings", params)
            uit += d.get("items") or d.get("meetings") or []
            cursor = d.get("next_cursor")
            if not cursor:
                break
            if met_transcript:
                time.sleep(PAUZE)
    return uit


def samenvatting_md(g):
    """De samenvatting van Fathom als markdown (default_summary.markdown_formatted), of '' (ook als het veld een
    tekst is: dan die tekst)."""
    ds = g.get("default_summary")
    if isinstance(ds, dict):
        return str(ds.get("markdown_formatted") or "")
    return str(ds or "")


def transcript_tekst(g):
    """Het transcript van een gesprek als leesbare tekst (spreker: zin), of ''."""
    t = g.get("transcript")
    if not t:
        return ""
    if isinstance(t, str):
        return t
    regels = []
    for r in t:
        spreker = (r.get("speaker") or {}).get("display_name") if isinstance(r.get("speaker"), dict) else r.get("speaker")
        regels.append(f"[{r.get('timestamp', '')}] {spreker or '?'}: {r.get('text', '')}")
    return "\n".join(regels)

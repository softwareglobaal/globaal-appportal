"""Fathom (opnames van online gesprekken), alleen lezen, vanaf de host.
Sleutel(s) bij naam uit ~/appportal/.env: FATHOM_API_KEYS (komma-gescheiden). Mehdi's eigen account: de adressen in
FATHOM_MEHDI_ADRESSEN (komma-gescheiden, geen sleutel), in de code MEHDI_FATHOM_ADRESSEN.
Zelfde API als het contract-dashboard (webapp/fathom_api.py). In Fathom schrijf ik nooit; vul_aan schrijft alleen in
een bestaande map van ons eigen archief (FATHOM-1)."""
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


def _alle(sinds_iso, vlaggen, pauze):
    uit = []
    for s in sleutels():
        cursor = None
        while True:
            params = {"created_after": sinds_iso, **vlaggen}
            if cursor:
                params["cursor"] = cursor
            d = _haal(s, "/meetings", params)
            uit += d.get("items") or d.get("meetings") or []
            cursor = d.get("next_cursor")
            if not cursor:
                break
            if pauze:
                time.sleep(PAUZE)
    return uit


def gesprekken(sinds_iso, met_transcript=False):
    """Alle gesprekken sinds een ISO-tijdstip, over alle sleutels; met transcript als gevraagd."""
    return _alle(sinds_iso, {"include_transcript": "true" if met_transcript else "false"}, met_transcript)


def samenvattingen(sinds_iso):
    """FATHOM-1 en ANGEL-8 (overleg T-0120, X9): alle gesprekken sinds een ISO-tijdstip met de samenvatting en de
    actiepunten van Fathom (include_summary en include_action_items staan standaard uit), zonder transcript. Een aparte
    vraag, niet bij die met transcript: zo'n pagina was al 600 kB en brak af (29-10-2026). Gemeten 01-11-2026: met de
    twee vlaggen 18 van 18 samenvattingen, zonder 0."""
    return _alle(sinds_iso, {"include_transcript": "false", "include_summary": "true", "include_action_items": "true"},
                 True)


# --------------------------------------------- samenvatting en actiepunten in de archiefmap (FATHOM-1) ---
# Het contract met De Dagbundelaar: per gesprek in de archiefmap (gesprek_log.archief, op recording_id) staan
#   samenvatting.md    de kop hieronder en dan de markdown-tekst van Fathom (default_summary.markdown_formatted);
#   actiepunten.json   {"bron": "fathom", "recording_id": ..., "actiepunten": [{"tekst", "wie", "tijd", "klaar"}]}, met
#                      tekst de beschrijving, wie de naam van wie het moet doen ('' als niemand), tijd het moment in de
#                      opname ('UU:MM:SS' of ''), klaar of Fathom het afgevinkt ziet. Een lege lijst: Fathom verwerkte
#                      het gesprek en vond geen actiepunt. Geen bestand: onbekend, nooit nul;
#   actiepunten.md     dezelfde lijst om te lezen, voor Mehdi in Dropbox.
# Niet als bron voor contract of verslag: het transcript telt. Van een privégesprek staan ze ook in het archief, zoals
# het transcript; wie leest, volgt de privéregel van de rij in de gesprekkentabel.
SAMENVATTING_KOP = "# Samenvatting van Fathom (niet als bron voor contract of verslag; het transcript telt)\n\n"
ACTIEPUNTEN_KOP = "# Actiepunten van Fathom (niet als bron voor contract of verslag; het transcript telt)\n\n"


def samenvatting_tekst(g):
    """De samenvatting van Fathom als markdown-tekst, of ''. Fathom geeft default_summary als object met
    markdown_formatted (ANGEL-8: tot T-0120 schreef De Fathomwacht str() van het hele object, een Python-dict)."""
    s = g.get("default_summary")
    if isinstance(s, dict):
        s = s.get("markdown_formatted")
    return s.strip() if isinstance(s, str) else ""


def actiepunten(g):
    """De actiepunten van Fathom in onze vorm, of None als dat onbekend is: Fathom gaf geen lijst (niet gevraagd), het
    gesprek is nog niet verwerkt (een lege lijst zonder samenvatting), of de lijst heeft een vorm die we niet kennen."""
    punten = g.get("action_items")
    if not isinstance(punten, list) or (not punten and not samenvatting_tekst(g)):
        return None
    uit = []
    for p in punten:
        p = p if isinstance(p, dict) else {"description": p}
        tekst = str(p.get("description") or "").strip()
        if tekst:
            wie = p.get("assignee") if isinstance(p.get("assignee"), dict) else {}
            uit.append({"tekst": tekst, "wie": str(wie.get("name") or "").strip(),
                        "tijd": str(p.get("recording_timestamp") or ""), "klaar": bool(p.get("completed"))})
    return uit if uit or not punten else None


def _actiepunten_md(punten):
    if not punten:
        return ACTIEPUNTEN_KOP + "Fathom vond in dit gesprek geen actiepunt.\n"
    return ACTIEPUNTEN_KOP + "".join(
        f"- [{'x' if p['klaar'] else ' '}] {p['tekst']}" + (f" ({', '.join(x for x in (p['wie'], p['tijd']) if x)})"
                                                           if p["wie"] or p["tijd"] else "") + "\n" for p in punten)


def vul_aan(map_, g, droog=False):
    """FATHOM-1: schrijf in een bestaande archiefmap de samenvatting en de actiepunten van Fathom, alleen wat ontbreekt.
    Een bestand dat er al is, blijft byte voor byte gelijk (open met 'x': ook bij twee schrijvers tegelijk nooit
    overschrijven); een map die er niet is, maak ik niet. Geeft de namen van wat geschreven werd (droog: zou worden)."""
    if not os.path.isdir(map_):
        return []
    bestanden = []
    tekst = samenvatting_tekst(g)
    if tekst:
        bestanden.append(("samenvatting.md", SAMENVATTING_KOP + tekst + "\n"))
    punten = actiepunten(g)
    if punten is not None:
        bestanden.append(("actiepunten.json", json.dumps({"bron": "fathom", "recording_id": g.get("recording_id"),
                                                           "actiepunten": punten}, ensure_ascii=False, indent=1) + "\n"))
        bestanden.append(("actiepunten.md", _actiepunten_md(punten)))
    geschreven = []
    for naam, inhoud in bestanden:
        pad = os.path.join(map_, naam)
        if os.path.lexists(pad):
            continue
        if not droog:
            try:
                with open(pad, "x", encoding="utf-8") as f:
                    f.write(inhoud)
            except FileExistsError:
                continue
        geschreven.append(naam)
    return geschreven


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

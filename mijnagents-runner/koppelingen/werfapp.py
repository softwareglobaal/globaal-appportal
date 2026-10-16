"""Brug van de Werfverslag schrijver naar de werfapp (werf.globaal.be).

Een proef wordt daar een conceptverslag met de punten per categorie, de eigen foto's als Dropbox-verwijzing en de
herkomst. Mehdi leest het daar na, past aan en klikt zelf Versturen. De brug verstuurt nooit en overschrijft nooit:
per vast bezoek (bezoek_id) hooguit één concept; bestaat dat al, dan geeft de werfapp het terug zoals Mehdi het achterliet.
Zonder vast bezoek of tegen een werfapp die niet kan koppelen, maakt de brug niets (CX4-1, CX4-11).

Toegang: hetzelfde AGENTS_TOKEN als het bord (koppelingen/bord.py leest het uit mijnagents-data/.env); de werfapp
krijgt het uit hetzelfde bestand (docker-compose.override.yml, app-werfverslag). Naam en plaats, nooit de waarde.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

import bord

DOOR = "werfverslag-schrijver"
STATUS = {"ok": "OK"}                      # alleen een vastgestelde OK; al de rest blijft open (W3: open punten gaan mee)
TAGS = {"belangrijk": "Belangrijk", "dringend": "Dringend"}
FOTO = (".jpg", ".jpeg", ".png")


class WerfappFout(RuntimeError):
    def __init__(self, status, fout):
        self.status, self.fout = status, fout
        super().__init__(f"werfapp {status}: {fout}")


PRODUCTIE = "https://werf.globaal.be"


def basis():
    """Het token gaat alleen naar de exacte productie-origin of een lokale testserver (CX4-9), nooit naar een lookalike."""
    url = (os.environ.get("WERFAPP_URL") or PRODUCTIE).rstrip("/")
    if url != PRODUCTIE and not re.fullmatch(r"http://127\.0\.0\.1:[0-9]{2,5}", url):
        raise WerfappFout(0, f"werfapp alleen op {PRODUCTIE} of http://127.0.0.1:<poort>")
    return url


def conceptlink(vid):
    return f"{basis()}/verslag/{int(vid)}/bewerken"


_KAN = {}


def kan_koppelen():
    """De werfapp meldt bezoek_koppeling in GET /api/v1/ (W41). Een oudere werfapp negeert bezoek_id en zou een ongekoppeld
    concept maken; dan maakt de brug niets (CX4-11)."""
    if basis() not in _KAN:
        _KAN[basis()] = int((call("/") or {}).get("bezoek_koppeling") or 0) >= 1
    return _KAN[basis()]


class _GeenRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # een omleiding (Authentik-login) is een fout, nooit een stille tweede aanvraag


def call(pad, payload=None, method=None):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(basis() + "/api/v1" + pad, data=data, method=method or ("POST" if data is not None else "GET"),
                                 headers={"X-Agents-Token": getattr(bord, "TOKEN", ""), "Content-Type": "application/json"})
    try:
        with urllib.request.build_opener(_GeenRedirect()).open(req, timeout=45) as r:
            ruw = r.read()
    except urllib.error.HTTPError as ex:
        try:
            body = json.loads(ex.read().decode("utf-8"))
        except (ValueError, UnicodeError):
            body = {}
        raise WerfappFout(ex.code, body.get("fout") or "verzoek geweigerd") from None
    except (urllib.error.URLError, TimeoutError, OSError) as ex:
        raise WerfappFout(0, f"niet bereikbaar ({type(ex).__name__})") from None
    try:
        antwoord = json.loads(ruw.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise WerfappFout(0, "antwoord is geen JSON (loginpagina of proxy?)") from None
    if not isinstance(antwoord, (dict, list)):
        raise WerfappFout(0, "onverwacht antwoord")
    return antwoord



def volgnummer(nr_label):
    """Het werfverslagnummer van het bezoek (W8: <dossier>-<bezoek>). Een plaatsbezoek (PB2) heeft er geen."""
    s = str(nr_label or "").strip()
    return int(s) if re.fullmatch(r"[1-9][0-9]{0,4}", s) else None


def _per_naam(fotos):
    per = {}
    for f in fotos:
        if f.get("naam", "").lower().endswith(FOTO) and f.get("pad"):
            per.setdefault(f["naam"], f["pad"])
            per.setdefault(os.path.basename(f["pad"]), f["pad"])
    return per


def _fotopaden(namen, fotos):
    per = _per_naam(fotos)
    return list(dict.fromkeys(per[n] for n in namen if n in per))


def ontbrekende_fotos(verslag, fotos):
    """Foto's die de proef bij een punt noemt maar die niet als jpg/png in de bezoekmap staan (CX3-8): een dia uit een
    presentatie, een HEIC zonder jpeg-kopie of een verkeerde naam. Ze staan wel in de Word-proef als die ze vond."""
    per = _per_naam(fotos)
    return sorted({n for c in verslag.get("categorieen") or [] for p in c.get("punten") or [] for n in p.get("fotos") or [] if n not in per})


def opmerkingen(verslag, fotos):
    """De punten van de proef als werfapp-opmerkingen, in de volgorde van de proef. Foto's alleen uit de bezoekmap
    (jpg/png op bestandsnaam); een dia uit een presentatie heeft geen eigen pad en blijft in de Word-proef."""
    uit = []
    for cat in verslag.get("categorieen") or []:
        for p in cat.get("punten") or []:
            vlag = (p.get("vlag") or "").strip().lower()
            tekst = (p.get("tekst_nl") or "").strip()
            if (p.get("tekst_en") or "").strip():
                tekst += "\n\n" + p["tekst_en"].strip()
            uit.append({"categorie": cat.get("naam") or "Algemeen", "titel": (p.get("titel") or "Opmerking").strip(),
                        "omschrijving": tekst or None, "status": STATUS.get(vlag),
                        "datum": (p.get("datum") or verslag.get("datum") or "")[:10] or None,
                        "verantwoordelijken": [p["verantwoordelijke"].strip()] if (p.get("verantwoordelijke") or "").strip() else [],
                        "tags": ([TAGS[vlag]] if vlag in TAGS else []) + (["Vast punt"] if p.get("doorlopend") else []),
                        "fotos": _fotopaden(p.get("fotos") or [], fotos)})
    for a in verslag.get("acties") or []:
        if (a.get("wat") or "").strip():
            uit.append({"categorie": "Actiepunten", "titel": a["wat"].strip(), "status": None,
                        "omschrijving": f"Tegen: {a['tegen'].strip()}" if (a.get("tegen") or "").strip() else None,
                        "verantwoordelijken": [a["wie"].strip()] if (a.get("wie") or "").strip() else [], "tags": [], "fotos": []})
    return uit


def _ja(w):
    return str(w).strip().lower() in ("ja", "yes", "true", "1", "x", "aanwezig")


def payload(verslag, rij, fotos, proef_pad=""):
    """De body voor POST /api/v1/verslagen. Zuiver: geen netwerk, testbaar."""
    status = (verslag.get("status_nl") or "").strip()
    if (verslag.get("status_en") or "").strip():
        status += "\n\n" + verslag["status_en"].strip()
    inleiding = f"Volgend werfbezoek: {verslag['volgend'].strip()}" if (verslag.get("volgend") or "").strip() else None
    reg = rij.get("registratie") if isinstance(rij.get("registratie"), dict) else {}
    body = {"project": str(verslag["dossier"]), "datum": verslag.get("datum") or rij.get("datum"),
            "status_werf": status or None, "inleiding": inleiding, "opmerkingen": opmerkingen(verslag, fotos), "door": DOOR,
            "bron": {"soort": "werfverslag-proef", "verwijzing": proef_pad or rij.get("bezoekmap") or "", "agent": DOOR,
                     "detail": {"bordrij": rij.get("id"), "bezoek": verslag.get("bezoek"), "verslagtype": verslag.get("verslagtype"),
                                "fotos_niet_gevonden": ontbrekende_fotos(verslag, fotos)}}}
    if reg.get("bezoek_id") and reg.get("project_ref") == f"h-architects:{verslag['dossier']}":
        body["bezoek_id"] = reg["bezoek_id"]   # de werfapp koppelt en geeft bij herhaling hetzelfde verslag terug (CX3-4)
    nr = volgnummer(verslag.get("bezoek"))
    if nr:
        body["volgnummer"] = nr
    aanw = [{"naam": a["naam"].strip(), "rol": a.get("rol") or None, "firma": a.get("firma") or None, "aanwezig": _ja(a.get("aanwezig", ""))}
            for a in verslag.get("aanwezigen") or [] if (a.get("naam") or "").strip()]
    if aanw:
        body["aanwezigen"] = aanw   # zonder aanwezigen neemt de werfapp de projectcontacten (toon in verslag)
    return body


def _project(dossier, adres):
    try:
        return call(f"/projecten/{dossier}"), False
    except WerfappFout as ex:
        if ex.status != 404:
            raise
    naam = (adres or "").strip() or f"Project {dossier}"
    call("/projecten", {"nummer": str(dossier), "naam": naam[:200]})
    return call(f"/projecten/{dossier}"), True


def concept(verslag, rij, fotos, proef_pad=""):
    """Zet de proef als conceptverslag in de werfapp. Geeft {id, nummer, url, nieuw, project_nieuw, fotos_niet_gevonden}.
    Vereist een vast bezoek van hetzelfde project in rij['registratie']: de werfapp koppelt het verslag eraan en geeft bij
    elke herhaling (tweede klik, cron, verloren antwoord, --naar-werfapp) hetzelfde concept terug (W41, CX4-1/2)."""
    if verslag.get("soort_bezoek") == "plaatsbezoek" or not volgnummer(verslag.get("bezoek")):
        raise WerfappFout(0, "plaatsbezoek zonder werfverslagnummer: blijft een Word-proef (A7/A8)")
    body = payload(verslag, rij, fotos, proef_pad)
    if not body.get("bezoek_id"):
        raise WerfappFout(0, "geen vast bezoek (registratie) voor deze bordrij; niets aangemaakt")
    if not kan_koppelen():
        raise WerfappFout(0, "de werfapp kan nog geen bezoek koppelen (oudere versie); niets aangemaakt")
    _, project_nieuw = _project(verslag["dossier"], verslag.get("adres") or rij.get("adres"))
    try:
        r = call("/verslagen", body)
    except WerfappFout as ex:
        if ex.status == 409:
            raise WerfappFout(409, f"{ex.fout}; niets aangemaakt, kijk het na in de werfapp") from None
        raise
    if "bestond" not in r or not isinstance(r.get("id"), int):
        raise WerfappFout(0, "onverwacht antwoord van de werfapp (geen bezoekkoppeling bevestigd)")
    return {"id": r["id"], "nummer": r.get("nummer"), "url": conceptlink(r["id"]), "nieuw": not r["bestond"], "project_nieuw": project_nieuw,
            "fotos_niet_gevonden": ontbrekende_fotos(verslag, fotos)}

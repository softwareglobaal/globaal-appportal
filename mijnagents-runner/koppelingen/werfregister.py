"""Werfbroncache en kostenpoort in de werfapp, gedeeld door Mac en server.

Geen lokale tweede analysecache. Een betaalde start is eerst duurzaam geregistreerd;
onzekere uitkomsten blijven geblokkeerd. Tokens uitsluitend uit providerusage.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


class RegisterFout(RuntimeError):
    veilig_opnieuw = False


class WachtBudget(RegisterFout):
    veilig_opnieuw = True
    code = "wacht_op_budget"

    def __init__(self, hervat_utc):
        self.hervat_utc = hervat_utc
        super().__init__("tokenbudget bereikt; verwerking wacht tot " + hervat_utc)


class WachtBron(WachtBudget):
    code = "wacht_op_bron"

    def __init__(self):
        self.hervat_utc = (datetime.now(timezone.utc) + timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        RegisterFout.__init__(self, "dezelfde projectbron wordt al verwerkt; daarna hergebruik controleren")


def _http_fout(status, body):
    code, bericht = body.get("code", "fout"), body.get("fout", "verzoek geweigerd")
    details = body.get("details") or {}
    if status == 409 and code == "verwerking_onzeker" and details.get("status") == "gestart" and details.get("fase") == "bron-feiten":
        try:
            gestart = datetime.strptime(details["gestart_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            leeftijd = (datetime.now(timezone.utc) - gestart).total_seconds()
            if 0 <= leeftijd < 600:
                return WachtBron()
        except (ValueError, KeyError):
            pass
    return RegisterFout(f"werfregister {status} {code}: {bericht}")


class _GeenRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _json(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(o):
    return hashlib.sha256(_json(o).encode("utf-8")).hexdigest()


def _instelling(naam, default=""):
    if os.environ.get(naam):
        return os.environ[naam].strip().strip('"').strip("'")
    pad = os.path.expanduser(os.environ.get("WERFREGISTER_ENV_FILE", "~/appportal/.env"))
    try:
        with open(pad, encoding="utf-8") as f:
            for regel in f:
                if regel.startswith(naam + "="):
                    return regel.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return default


def call(pad, payload=None):
    token = _instelling("WERFREGISTER_TOKEN")
    if not token:
        raise RegisterFout("werfregister niet aangesloten: WERFREGISTER_TOKEN ontbreekt in ~/appportal/.env")
    basis = _instelling("WERFREGISTER_URL", "https://werf.globaal.be").rstrip("/")
    if not basis.startswith("https://") and not basis.startswith("http://127.0.0.1:"):
        raise RegisterFout("werfregister vereist HTTPS of de lokale testserver")
    req = urllib.request.Request(basis + "/api/v1" + pad,
                                 data=_json(payload).encode("utf-8") if payload is not None else None,
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.build_opener(_GeenRedirect()).open(req, timeout=45) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        try:
            body = json.loads(ex.read().decode("utf-8"))
        except (ValueError, UnicodeError):
            body = {}
        raise _http_fout(ex.code, body) from None
    except (urllib.error.URLError, TimeoutError) as ex:
        raise RegisterFout("werfregister niet bereikbaar; geen nieuwe modelaanroep toegestaan") from ex


def registreer(rij, dossier, volgnr):
    if not re.fullmatch(r"[0-9]{4,6}", str(dossier)) or str(rij.get("dossier")) != str(dossier):
        raise RegisterFout("dossier past niet bij de gekozen bezoekrij")
    if not isinstance(rij.get("id"), int) or rij["id"] < 1:
        raise RegisterFout("vaste bordrij-ID ontbreekt; geen willekeurige bezoekkoppeling")
    project = "h-architects:" + str(dossier)
    nr = (rij.get("bronnen") or {}).get("nr_label") or str(volgnr)
    soort = (rij.get("bronnen") or {}).get("soort_bezoek") or "werfbezoek"
    if soort not in ("werfbezoek", "plaatsbezoek", "oplevering", "overig"):
        soort = "overig"
    inhoud = {"alias": {"systeem": "bord", "account_ref": "mijnagents", "objecttype": "werfbezoek",
                         "externe_id": "rij:" + str(rij["id"]),
                         "weergave": {"rijvolgnr": str(volgnr), "datum": str(rij.get("datum") or "")}},
              "project_ref": project, "project_zekerheid": "zeker", "bezoektype": soort,
              "status": "onzeker", "gepland": None, "weergave_nummer": nr}
    antwoord = call("/bezoeken/upsert", {"schema_version": 1, "idempotency_key": "werfadapter:" + _hash(inhoud), **inhoud})
    bezoek = antwoord.get("bezoek") or {}
    bid = bezoek.get("bezoek_id")
    if not bid or bezoek.get("project_ref") != project:
        raise RegisterFout("werfregister gaf geen bezoek binnen het gevraagde project")
    return {"bezoek_id": bid, "project_ref": project, "bron": "bord", "bordrij_id": rij["id"],
            "status": bezoek.get("status"), "revisie": bezoek.get("revisie")}


def _manifest(items):
    uit = []
    for m in items:
        sha = m.get("sha256") or m.get("hash")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            if m.get("beeldanalyse") == "niet uitgevoerd" or m.get("audioanalyse"):
                continue  # Alleen de namen zijn context; claim geen hash van ongeziene media.
            raise RegisterFout("bron zonder gemeten inhoudshash; geen betaalde analyse")
        b = {"naam": str(m.get("naam") or m.get("name") or "bron")[:500], "sha256": sha}
        for oud, nieuw in (("file_id", "bestand_id"), ("bestand_id", "bestand_id"), ("bytes", "bytes"),
                          ("soort", "soort"), ("brontype", "brontype"), ("ai_toegestaan", "ai_toegestaan")):
            if m.get(oud) is not None:
                b[nieuw] = m[oud]
        if b.get("bytes") == 0:
            raise RegisterFout("broninhoud nog niet opgehaald; nulbytes zijn geen leesbare bron")
        if b.get("brontype") == "technisch" and not b.get("ai_toegestaan"):
            raise RegisterFout("technische bron zonder bevestigde AI-rechten")
        if b.get("soort") not in (None, "document", "transcript", "notitie", "foto", "audio"):
            b["soort"] = "document"
        uit.append(b)
    if not uit:
        raise RegisterFout("geen gehashte broninvoer; geen betaalde analyse")
    return uit


def _usage(usage):
    return {k: int(getattr(usage, k, 0) or 0) for k in
            ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}


def _antwoord_usage(meta, raw=None, cached=False):
    u = {k: 0 if cached else v for k, v in (raw or meta.get("usage") or {}).items()}
    for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
        u.setdefault(k, 0)
    m = dict(meta)
    m.update(input_tokens=m.get("tokens_in", 0), output_tokens=m.get("tokens_uit", 0),
             cost_usd=m.get("nieuwe_kosten_usd"), cached=cached)
    return SimpleNamespace(**u, hergebruikt=cached, verwerking=m)


def verwerk(rij, dossier, volgnr, fase, invoer, model, promptversie, schemaversie, taal,
            bronbeleid, bronmanifest, functie, max_tokens):
    registratie = registreer(rij, dossier, volgnr)
    bid = registratie["bezoek_id"]
    manifest = _manifest(bronmanifest)
    context = {"project_ref": registratie["project_ref"], "bronbeleid": str(bronbeleid), "adapter": "2"}
    if fase == "proef":
        context["bezoek_id"] = bid
    poging = "werfcalls:" + uuid.uuid4().hex
    v = {"schema_version": 1, "idempotency_key": poging + ":start", "fase": fase,
         "invoer_hash": _hash(invoer), "model": model, "prompt_versie": promptversie,
         "schema_versie": schemaversie, "taal": taal, "context_versies": context,
         "bronmanifest": manifest, "aanroep_sleutel": poging,
         # Eén token per UTF-8-byte is conservatief; ook het vaste systeem/toolgedeelte reserveren.
         "tokens_gereserveerd_in": len(_json(invoer).encode("utf-8")) + 6000,
         "tokens_gereserveerd_uit": max_tokens}
    start = call(f"/bezoeken/{bid}/handmatige-verwerking", v)
    if start.get("uitkomst") == "hergebruikt":
        return copy.deepcopy(start["resultaat"]), _antwoord_usage(start["verwerking"], cached=True)
    if start.get("uitkomst") == "wacht_op_budget":
        raise WachtBudget(start["hervat_utc"])
    if start.get("uitkomst") != "gestart" or not (start.get("verwerking") or {}).get("verwerking_id"):
        raise RegisterFout("geen bevestigde betaalreservering; model wordt niet aangeroepen")
    vid = start["verwerking"]["verwerking_id"]
    afgerond = {"schema_version": 1, "idempotency_key": poging + ":klaar", "verwerking_id": vid,
                "aanroep_sleutel": poging}
    usage = None
    try:
        resultaat, usage = functie()
        if not isinstance(resultaat, dict) or not resultaat or usage is None:
            raise RegisterFout("model leverde geen volledig controleerbaar resultaat")
    except Exception as ex:
        usage = getattr(ex, "usage", usage)
        # Providerexceptions kunnen broninhoud of HTTP-headers bevatten: alleen fouttype loggen.
        fout = {**afgerond, "uitkomst": "mislukt" if usage is not None else "onbekend",
                "fout": type(ex).__name__ + ": " + ("ongeldig modelresultaat" if usage is not None else "onzekere provideruitkomst")}
        if usage is not None:
            fout["usage"] = _usage(usage)
            fout["provider_request_id"] = getattr(usage, "request_id", None)
        try:
            call(f"/bezoeken/{bid}/handmatige-verwerking/afronden", fout)
        except RegisterFout:
            pass  # De duurzame gestart-registratie blijft conservatief geblokkeerd.
        raise
    raw = _usage(usage)
    einde = call(f"/bezoeken/{bid}/handmatige-verwerking/afronden",
                 {**afgerond, "uitkomst": "gelukt", "resultaat": resultaat, "usage": raw,
                  "provider_request_id": getattr(usage, "request_id", None)})
    return copy.deepcopy(resultaat), _antwoord_usage(einde["verwerking"], raw)

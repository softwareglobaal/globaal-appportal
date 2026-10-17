"""Werf-only opdrachtregister. Een onbekende uitvoering wordt nooit automatisch herhaald."""
import hashlib
import json
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone


class Conflict(Exception):
    def __init__(self, reden, code=409):
        self.reden, self.code = reden, code
        super().__init__(reden)


def nu():
    return datetime.now(timezone.utc).isoformat()


def _json(value, default=None):
    if isinstance(value, str):
        try:
            return json.loads(value) if value else ({} if default is None else default)
        except ValueError:
            return {} if default is None else default
    return value if value is not None else ({} if default is None else default)


def _zonder_verwerking(value):
    if isinstance(value, dict):
        return {k: _zonder_verwerking(v) for k, v in value.items() if k != "_verwerking"}
    if isinstance(value, list):
        return [_zonder_verwerking(v) for v in value]
    return value


def hash_van(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def invoer(rij, soort):
    r = dict(rij)
    keuzes = {k: v for k, v in _json(r.get("keuzes")).items() if k not in ("ts", "door")}
    result = {k: r.get(k) for k in ("id", "dossier", "datum", "volgnr", "adres", "soort_project", "projectmap", "bezoekmap", "keuzes_revisie")}
    result.update(recept="werfopdracht-v1", soort=soort, keuzes=keuzes, bronnen=_json(r.get("bronnen")))
    if soort == "proef":
        result["gegevens"] = _zonder_verwerking(_json(r.get("gegevens")))
    return result


def revisie(rij):
    return hash_van(invoer(rij, "proef"))


@contextmanager
def atomic(conn):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _event(conn, kid, status, detail=None):
    conn.execute("INSERT INTO werfopdracht_gebeurtenis(klaarzet_id,status,detail,ts) VALUES(?,?,?,?)",
                 (kid, status, json.dumps(detail or {}, ensure_ascii=False), nu()))


def _public(rij):
    r = dict(rij)
    r["id"] = r.pop("klaarzet_id")
    r.pop("lease_hash", None)
    r["invoer"] = _json(r["invoer"])
    r["bron"] = r["invoer"].get("bron") or {"soort": "bord"}
    r["verwerking"] = _json(r["verwerking"])
    r["veilig_opnieuw"] = bool(r["veilig_opnieuw"])
    if r["status"] == "actief" and r["lease_tot"] < nu():
        r["status"] = "onbekend"
        r["bewijs"] = "Claim verlopen; eerdere betaalde uitvoering eerst controleren"
    r["dossier"] = r["invoer"]["dossier"]
    r["volgnr"] = r["invoer"]["volgnr"]
    return r


def _opdracht(conn, kid):
    r = conn.execute("SELECT * FROM werfopdracht WHERE klaarzet_id=?", (kid,)).fetchone()
    if not r:
        raise Conflict("opdracht bestaat niet in het werfregister", 404)
    return r


def _verlopen(conn):
    ids = [r[0] for r in conn.execute("SELECT klaarzet_id FROM werfopdracht WHERE status='actief' AND lease_tot<?", (nu(),))]
    for kid in ids:
        conn.execute("UPDATE werfopdracht SET status='onbekend',bewijs=? WHERE klaarzet_id=?", (
            "Claim verlopen; eerdere betaalde uitvoering eerst controleren", kid))
        _event(conn, kid, "onbekend", {"reden": "claim verlopen"})


def _hervatten(conn):
    for rij in conn.execute("SELECT klaarzet_id FROM werfopdracht WHERE status='uitgesteld' AND hervat_utc<=?", (nu(),)).fetchall():
        kid = rij[0]
        conn.execute("UPDATE werfopdracht SET status='klaar',resultaat_bewaard='',poging=poging+1 WHERE klaarzet_id=?", (kid,))
        _event(conn, kid, "klaar", {"reden": "uitsteltermijn verstreken; claim moet de actuele invoer opnieuw toetsen"})


def _budgetmoment(value):
    try:
        tijd = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if tijd.tzinfo is None:
            raise ValueError("tijdzone ontbreekt")
        return tijd.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, AttributeError):
        raise Conflict("hervat_utc moet een datum en tijd met UTC-tijdzone zijn", 400)


def lijst(conn, bezoek_id=None, status=None, verlopen=True):
    if verlopen:
        with atomic(conn):
            _verlopen(conn)
            _hervatten(conn)
    q, args = "SELECT * FROM werfopdracht WHERE 1=1", []
    if bezoek_id is not None:
        q += " AND werfbezoek_id=?"; args.append(bezoek_id)
    if status:
        q += " AND status=?"; args.append(status)
    return [_public(r) for r in conn.execute(q + " ORDER BY klaarzet_id DESC", args)]


def maak(conn, bezoek_id, soort, door, verwacht=None, bron="bord", reden=""):
    if soort not in ("voorbereid", "proef"):
        raise Conflict("ongeldige opdrachtsoort", 400)
    if bron not in ("bord", "commandline"):
        raise Conflict("ongeldige opdrachtbron", 400)
    reden = str(reden or "").strip()
    if bron == "commandline" and not reden:
        raise Conflict("commandline-opdracht vereist de reden van Mehdi", 400)
    with atomic(conn):
        r = conn.execute("SELECT * FROM werfbezoek WHERE id=?", (bezoek_id,)).fetchone()
        if not r:
            raise Conflict("bezoek bestaat niet", 404)
        if verwacht and revisie(r) != verwacht:
            raise Conflict("bezoek of keuzes gewijzigd; herlaad de pagina")
        snapshot = invoer(r, soort)
        signature = hash_van(snapshot)
        oud = conn.execute("SELECT * FROM werfopdracht WHERE werfbezoek_id=? AND soort=? AND invoer_hash=?",
                           (bezoek_id, soort, signature)).fetchone()
        if oud:
            if bron == "commandline":
                vastgelegd = (json.loads(oud["invoer"] or "{}").get("bron") or {})
                if vastgelegd != {"soort": "commandline", "reden": reden[:500]}:
                    raise Conflict("identieke opdracht bestaat al met een andere bron of reden; gebruik de bestaande opdracht", 409)
                _event(conn, oud["klaarzet_id"], oud["status"], {"bron": "commandline", "reden": reden[:500], "hergebruikt": True})
            return _public(oud), False
        snapshot["bron"] = {"soort": bron, "reden": reden[:500] if bron == "commandline" else ""}
        ts = nu()
        cur = conn.execute("INSERT INTO klaarzet(van,voor,soort,sleutel,titel,inhoud,verwijzing,uniek,ts) VALUES(?,?,?,?,?,?,?,?,?)", (
            f"{bron}:{door}", "werfverslag-schrijver", "opdracht", f"{r['dossier']}-{r['volgnr']}",
            f"{soort} {r['dossier']} {r['volgnr']}", json.dumps({"door": door, "werfbezoek_id": bezoek_id, "bron": snapshot["bron"]}),
            "", f"werf:{bezoek_id}:{soort}:{signature}", ts))
        kid = cur.lastrowid
        conn.execute("INSERT INTO werfopdracht(klaarzet_id,werfbezoek_id,soort,invoer_hash,invoer) VALUES(?,?,?,?,?)",
                     (kid, bezoek_id, soort, signature, json.dumps(snapshot, ensure_ascii=False)))
        _event(conn, kid, "klaar", {"bron": snapshot["bron"]})
        return _public(_opdracht(conn, kid)), True


def claim(conn, kid, door, lease_seconden=1800):
    geweigerd = None
    with atomic(conn):
        _verlopen(conn)
        _hervatten(conn)
        op = _opdracht(conn, kid)
        if op["status"] != "klaar":
            geweigerd = "opdracht is " + op["status"]
        else:
            r = conn.execute("SELECT * FROM werfbezoek WHERE id=?", (op["werfbezoek_id"],)).fetchone()
            if not r or hash_van(invoer(r, op["soort"])) != op["invoer_hash"]:
                conn.execute("UPDATE werfopdracht SET status='verouderd',bewijs=? WHERE klaarzet_id=?", ("Invoer gewijzigd vóór de claim", kid))
                _event(conn, kid, "verouderd")
                geweigerd = "invoer gewijzigd; nieuwe opdracht nodig"
            elif conn.execute("SELECT 1 FROM werfopdracht WHERE werfbezoek_id=? AND status IN ('actief','onbekend')", (op["werfbezoek_id"],)).fetchone():
                geweigerd = "bezoek heeft een actieve of onbekende uitvoering"
            else:
                token = secrets.token_urlsafe(32)
                until = (datetime.now(timezone.utc) + timedelta(seconds=max(60, min(int(lease_seconden), 14400)))).isoformat()
                conn.execute("UPDATE werfopdracht SET status='actief',lease_hash=?,lease_tot=?,door=?,gestart=? WHERE klaarzet_id=?",
                             (hash_van(token), until, door, nu(), kid))
                _event(conn, kid, "actief", {"door": door, "lease_tot": until})
                result = {"ok": True, "geclaimd": True, "lease_token": token, "opdracht": _public(_opdracht(conn, kid))}
    if geweigerd:
        raise Conflict(geweigerd)
    return result


def controleer(conn, kid, token, signature=None):
    op = _opdracht(conn, kid)
    if not token or not secrets.compare_digest(op["lease_hash"], hash_van(token)):
        raise Conflict("claimtoken klopt niet", 403)
    if op["status"] not in ("actief", "onbekend"):
        raise Conflict("opdracht is niet actief")
    r = conn.execute("SELECT * FROM werfbezoek WHERE id=?", (op["werfbezoek_id"],)).fetchone()
    if signature is not None and signature != op["invoer_hash"]:
        raise Conflict("invoerhash klopt niet")
    if not r or hash_van(invoer(r, op["soort"])) != op["invoer_hash"]:
        raise Conflict("bezoek of keuzes gewijzigd tijdens uitvoering")
    return op


def resultaat(conn, kid, token, status, bewijs="", veilig_opnieuw=False, verwerking=None, hervat_utc=None):
    if status not in ("gelukt", "fout", "onbekend", "uitgesteld"):
        raise Conflict("ongeldige resultaatstatus", 400)
    moment = _budgetmoment(hervat_utc) if status == "uitgesteld" else ""
    with atomic(conn):
        op = _opdracht(conn, kid)
        if not token or not secrets.compare_digest(op["lease_hash"], hash_van(token)):
            raise Conflict("claimtoken klopt niet", 403)
        if op["status"] == status and status in ("gelukt", "fout"):
            return _public(op)
        if op["status"] not in ("actief", "onbekend"):
            raise Conflict("opdracht is niet actief")
        if status == "uitgesteld":
            if not veilig_opnieuw or op["status"] != "actief" or op["lease_tot"] < nu():
                raise Conflict("uitstel vraagt een actieve claim en bevestiging dat de volgende modelaanroep niet startte")
            conn.execute("UPDATE werfopdracht SET status='uitgesteld',hervat_utc=?,lease_hash='',lease_tot='',veilig_opnieuw=0,bewijs=?,verwerking=? WHERE klaarzet_id=?",
                         (moment, str(bewijs)[:2000], json.dumps(verwerking or {}, ensure_ascii=False), kid))
            _event(conn, kid, "uitgesteld", {"hervat_utc": moment, "bewijs": str(bewijs)[:2000]})
            return _public(_opdracht(conn, kid))
        if status == "gelukt":
            controleer(conn, kid, token)
            if not op["resultaat_bewaard"]:
                raise Conflict("geen bewaard resultaat voor deze uitvoering")
        veilig = status == "fout" and bool(veilig_opnieuw)
        conn.execute("UPDATE werfopdracht SET status=?,voltooid=?,bewijs=?,veilig_opnieuw=?,verwerking=? WHERE klaarzet_id=?", (
            status, nu(), str(bewijs)[:2000], int(veilig), json.dumps(verwerking or {}, ensure_ascii=False), kid))
        _event(conn, kid, status, {"bewijs": str(bewijs)[:2000], "veilig_opnieuw": veilig, "verwerking": verwerking or {}})
        # Alleen dit werf-item afvinken; algemene klaarzet/opgepakt-semantiek blijft gelijk.
        if status == "gelukt":
            conn.execute("UPDATE klaarzet SET status='opgepakt',opgepakt_door=?,opgepakt_ts=? WHERE id=?", (op["door"], nu(), kid))
        return _public(_opdracht(conn, kid))


def opnieuw(conn, kid, bezoek_id):
    with atomic(conn):
        op = _opdracht(conn, kid)
        if op["werfbezoek_id"] != bezoek_id:
            raise Conflict("opdracht hoort bij een ander bezoek", 403)
        if op["status"] == "klaar":
            return _public(op)
        if op["status"] != "fout" or not op["veilig_opnieuw"]:
            raise Conflict("eerdere betaalde uitvoering eerst controleren; herhaling niet vrijgegeven")
        r = conn.execute("SELECT * FROM werfbezoek WHERE id=?", (bezoek_id,)).fetchone()
        if not r or hash_van(invoer(r, op["soort"])) != op["invoer_hash"]:
            raise Conflict("invoer gewijzigd; maak een nieuwe opdracht")
        conn.execute("UPDATE werfopdracht SET status='klaar',lease_hash='',lease_tot='',resultaat_bewaard='',veilig_opnieuw=0,poging=poging+1 WHERE klaarzet_id=?", (kid,))
        _event(conn, kid, "klaar", {"reden": "handmatige veilige herhaling"})
        return _public(_opdracht(conn, kid))

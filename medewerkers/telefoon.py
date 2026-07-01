"""Telefoonnummers van een persoon voor het 360°-profiel.

Leest rechtstreeks uit het communicatie-schema (zelfde appportal-database; de
read-only portal-rol heeft SELECT op communicatie.*). Een persoon hangt aan een
nummer als verantwoordelijke of als gebruiker (belvolgorde-queue). Best-effort:
geen database of schema → lege lijst, het profiel toont een nette fallback.
"""
import models
from sqlalchemy import text

enabled = models.engine is not None

_QUERY = text("""
    SELECT n.id, n.telefoonnummer, n.doel, n.status,
           (n.verantwoordelijke_persoon_id = :pid) AS verantwoordelijk
      FROM communicatie.nummer n
     WHERE n.verantwoordelijke_persoon_id = :pid
        OR n.id IN (SELECT nummer_id FROM communicatie.nummer_gebruiker
                     WHERE persoon_id = :pid)
     ORDER BY (n.status <> 'Actief'), n.telefoonnummer
""")


def nummers_van(persoon_id):
    """Nummers waar de persoon verantwoordelijke of gebruiker van is; [] bij fout."""
    if not (enabled and persoon_id):
        return []
    try:
        with models.engine.connect() as conn:
            rows = conn.execute(_QUERY, {"pid": str(persoon_id)}).mappings().all()
        return [dict(r) for r in rows]
    except Exception:  # best-effort: profiel blijft werken zonder deze sectie
        return []


_TELLINGEN = text("""
    SELECT f.id::text AS id,
           (SELECT count(*) FROM communicatie.nummer n WHERE n.factuur_firma_id = f.id) AS nummers,
           (SELECT count(*) FROM communicatie.emailadres e WHERE e.firma_id = f.id) AS emails
      FROM kern.firma f
""")

_FIRMA_NUMMERS = text("""
    SELECT id, telefoonnummer, doel, status,
           (factuur_firma_id = :fid)     AS factuur,
           (doorfactuur_firma_id = :fid) AS doorfactuur
      FROM communicatie.nummer
     WHERE factuur_firma_id = :fid OR doorfactuur_firma_id = :fid
     ORDER BY telefoonnummer
""")

_FIRMA_EMAILS = text("""
    SELECT e.id, e.adres::text AS adres, e.actief,
           CASE WHEN p.id IS NULL THEN ''
                ELSE p.voornaam || ' (' || coalesce(a.naam, '') || ')' END AS verantwoordelijke
      FROM communicatie.emailadres e
      LEFT JOIN kern.persoon p ON p.id = e.verantwoordelijke_persoon_id
      LEFT JOIN kern.afdeling a ON a.id = p.afdeling_id
     WHERE e.firma_id = :fid
     ORDER BY e.adres
""")


def tellingen_per_firma():
    """{firma_id(str): {nummers, emails}} — voor de Firma's-tab; {} bij fout."""
    if not enabled:
        return {}
    try:
        with models.engine.connect() as conn:
            rows = conn.execute(_TELLINGEN).mappings().all()
        return {r["id"]: {"nummers": r["nummers"], "emails": r["emails"]} for r in rows}
    except Exception:
        return {}


def firma_koppelingen(firma_id):
    """Nummers (factuur/doorfactuur) en e-mailadressen van een firma; leeg bij fout."""
    leeg = {"factuur": [], "doorfactuur": [], "emails": []}
    if not (enabled and firma_id):
        return leeg
    try:
        with models.engine.connect() as conn:
            nums = [dict(r) for r in conn.execute(
                _FIRMA_NUMMERS, {"fid": str(firma_id)}).mappings().all()]
            mails = [dict(r) for r in conn.execute(
                _FIRMA_EMAILS, {"fid": str(firma_id)}).mappings().all()]
        return {
            "factuur": [n for n in nums if n["factuur"]],
            "doorfactuur": [n for n in nums if n["doorfactuur"]],
            "emails": mails,
        }
    except Exception:
        return leeg

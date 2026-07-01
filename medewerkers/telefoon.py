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

"""Maakt rol-appportal.sql uit de bronnenkaart.

  python3 genereer_rollen.py > rol-appportal.sql

Waarom gegenereerd en niet met de hand geschreven: de rechten in Postgres en de
kaart in `bronnen.py` moeten hetzelfde zeggen. Twee lijsten die met de hand
bijgehouden worden lopen uit elkaar, en dat merk je pas als iemand data ziet die
niet van hem is.

**Het idee.** `mcp_lezer` krijgt zelf geen enkel recht op de app-schema's. Per
app en per rechtenniveau bestaat er een rol die precies dat mag lezen, en
`mcp_lezer` is daar lid van. De server doet vlak voor een query
`SET LOCAL ROLE <die rol>`. Vanaf dat moment bewaakt Postgres de grens.

Dat is het verschil met een controle in de code: vergeet de server een keer om
van rol te wisselen, dan volgt "permission denied" en geen stille uitlevering
van andermans data. `NOINHERIT` op `mcp_lezer` is daarvoor de sleutel: zonder
dat zou lidmaatschap alleen al genoeg zijn om alles te mogen lezen.

**Twee niveaus.** Toegang tot een app is niet hetzelfde als toegang tot alles
eronder; zie de uitleg bij CATEGORIEEN in bronnen.py. De basisrol laat de
gevoelige tabellen weg. Voor elke combinatie van categorieen die een app raakt
komt er een rol bij, en die is lid van de basisrol.

**Geen ALTER DEFAULT PRIVILEGES.** Een tabel die er later bij komt is dus niet
meteen leesbaar; je draait dit bestand opnieuw. Dat is met opzet: een nieuwe
tabel met salarissen erin zou anders vanzelf meeliften.
"""
from itertools import combinations

from bronnen import (BRONNEN, CATEGORIEEN, GEDEELDE_DB, categorieen_in,
                     rolnaam)

# Alle app-schema's in de appportal-database, stand 10-09-2026. Deze lijst
# dient om `mcp_lezer` zijn eigen rechten af te nemen: die horen uitsluitend bij
# de per-app rollen te liggen. Een eerdere opzet gaf mcp_lezer rechtstreeks
# SELECT op alles, en dan is SET LOCAL ROLE een lege huls.
ALLE_SCHEMAS = (
    "angela, boekhouding, communicatie, draaiboek, elevait, finance, hr, "
    "intercompany, items, kern, kosten, monday, namen, omv, ontwikkeling, "
    "organisatie, quickbooks, schuldentracker, uitgaven, vermogen"
)

KOP = """\
-- GEGENEREERD door portal-mcp/genereer_rollen.py. Niet met de hand aanpassen:
-- wijzig bronnen.py en draai het script opnieuw.
--
-- Draaien vanuit ~/appportal (de rol mcp_lezer bestaat dan al uit
-- portal-mcp/rol-authentik.sql):
--   docker compose exec -T postgresql psql -U authentik -d appportal \\
--       -v ON_ERROR_STOP=1 -f - < portal-mcp/rol-appportal.sql
--
-- mcp_lezer krijgt hier bewust GEEN rechten op de app-schema's. Per app en per
-- rechtenniveau is er een rol; de server wisselt daar met SET LOCAL ROLE
-- naartoe. Vergeet hij dat, dan volgt permission denied.

GRANT CONNECT ON DATABASE appportal TO mcp_lezer;
ALTER ROLE mcp_lezer NOINHERIT;

-- mcp_lezer mag hier zelf niets. Rechten liggen bij de per-app rollen; alleen
-- na SET LOCAL ROLE komt er data. Deze intrekking staat er ook voor het geval
-- een eerdere opzet wel rechtstreeks rechten heeft gegeven.
ALTER DEFAULT PRIVILEGES IN SCHEMA {alle} REVOKE SELECT ON TABLES FROM mcp_lezer;
REVOKE ALL ON ALL TABLES IN SCHEMA {alle} FROM mcp_lezer;
REVOKE ALL ON SCHEMA {alle} FROM mcp_lezer;
"""

MAAK_ROL = """SELECT 'CREATE ROLE {rol} NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{rol}')
\\gexec
"""


def _tabellen_van(categorie, schemas):
    """De tabellen van deze categorie die in deze schema's vallen."""
    heel, los = [], []
    for tabel in CATEGORIEEN[categorie]["tabellen"]:
        schema, naam = tabel.split(".", 1)
        if schema not in schemas:
            continue
        (heel if naam == "*" else los).append((schema, naam))
    return heel, los


def _basis(slug, schemas):
    """De rol zonder de gevoelige tabellen."""
    rol = rolnaam(slug)
    cats = categorieen_in(schemas)
    # Schema's die in hun geheel gevoelig zijn krijgen hier geen enkel recht.
    heel_gevoelig = set()
    losse_gevoelig = []
    for cat in cats:
        heel, los = _tabellen_van(cat, schemas)
        heel_gevoelig.update(s for s, _ in heel)
        losse_gevoelig.extend(f"{s}.{n}" for s, n in los)

    open_schemas = [s for s in schemas if s not in heel_gevoelig]
    regels = [f"\n-- {slug}: {', '.join(schemas)}", MAAK_ROL.format(rol=rol),
              f"GRANT USAGE ON SCHEMA {', '.join(schemas)} TO {rol};"]
    if open_schemas:
        regels.append(
            f"GRANT SELECT ON ALL TABLES IN SCHEMA {', '.join(open_schemas)} "
            f"TO {rol};")
    # Intrekken, niet alleen weglaten. Een eerdere versie van dit bestand kan
    # rechten hebben gegeven die nu niet meer horen; niets doen laat die staan.
    # Precies daar ging het een keer mis: kosten.bank_transactie bleef leesbaar
    # voor wie alleen de Organisatie-tegel mag zien.
    for tabel in sorted(losse_gevoelig):
        regels.append(f"REVOKE ALL ON {tabel} FROM {rol};")
    for schema in sorted(heel_gevoelig):
        regels.append(f"-- {schema} is in zijn geheel gevoelig: alleen USAGE.")
        regels.append(
            f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {rol};")
    regels.append(f"GRANT {rol} TO mcp_lezer;")
    return "\n".join(regels) + "\n"


def _niveau(slug, schemas, keuze):
    """Een rol die er een of meer gevoelige categorieen bij mag."""
    rol = rolnaam(slug, keuze)
    uitleg = " + ".join(CATEGORIEEN[c]["uitleg"] for c in keuze)
    regels = [f"\n-- {slug} met {uitleg}", MAAK_ROL.format(rol=rol),
              f"GRANT {rolnaam(slug)} TO {rol};"]
    for cat in keuze:
        heel, los = _tabellen_van(cat, schemas)
        for schema, _ in heel:
            regels.append(f"GRANT USAGE ON SCHEMA {schema} TO {rol};")
            regels.append(
                f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {rol};")
        for schema, naam in los:
            regels.append(f"GRANT SELECT ON {schema}.{naam} TO {rol};")
    regels.append(f"GRANT {rol} TO mcp_lezer;")
    return "\n".join(regels) + "\n"


def genereer():
    stukken = [KOP.format(alle=ALLE_SCHEMAS)]
    for slug, bron in sorted(BRONNEN.items()):
        if bron.soort != GEDEELDE_DB or not bron.schemas:
            continue
        schemas = list(bron.schemas)
        stukken.append(_basis(slug, schemas))
        cats = categorieen_in(schemas)
        for aantal in range(1, len(cats) + 1):
            for keuze in combinations(cats, aantal):
                stukken.append(_niveau(slug, schemas, keuze))
    stukken.append(
        "\n-- Apps die hier niet staan zijn niet leesbaar via de gedeelde\n"
        "-- database. Waarom niet, staat per app in bronnen.py en komt terug in\n"
        "-- het antwoord van de tool `apps`.\n")
    return "".join(stukken)


if __name__ == "__main__":
    print(genereer(), end="")

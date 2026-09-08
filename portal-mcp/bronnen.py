"""Waar staat de data van elke applicatie.

De cataloog komt uit Authentik en is compleet. Waar de data van een app staat,
weet Authentik niet, en daar is geen betrouwbare automatische bron voor: apps
zetten hun schema in code, niet in een omgevingsvariabele. Deze kaart is dus
handwerk, en juist daarom staat bij elke regel hoe we het weten.

Drie soorten, en het verschil is bedoeld om zichtbaar te zijn:

  gedeelde_db  de data staat in de appportal-database, in deze schema's.
               Leesbaar via `schema` en `query`.
  elders       de data staat ergens anders (Mongo, de native Postgres op 5432,
               SQLite, een externe dienst). Nog niet leesbaar, met de reden erbij.
  onbekend     nog niet uitgezocht. Ook dat zeggen we hardop.

**Waarom `onbekend` een echte uitkomst is.** Een app die we stil overslaan leest
als een app die niet bestaat, en dan gaat iemand ervan uit dat er niets is. Elke
app uit Authentik komt hier langs, en wie er niet in staat krijgt automatisch
`onbekend` met een reden. Niets verdwijnt.

Een regel promoveren van `onbekend` naar `gedeelde_db` doe je niet op de naam
maar op bewijs: kijk in de broncode van de app welke schema's hij bevraagt
(`grep -rhoE '\\b(schema1|schema2)\\.[a-z_]+' <map>`), en zet dat commando in het
veld `bewijs`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

GEDEELDE_DB = "gedeelde_db"
ELDERS = "elders"
ONBEKEND = "onbekend"

NIET_UITGEZOCHT = ("Nog niet uitgezocht waar de data van deze app staat. "
                   "Zie portal-mcp/bronnen.py voor hoe je dat vaststelt.")


@dataclass(frozen=True)
class Bron:
    soort: str
    schemas: tuple = field(default=())
    reden: str = ""      # waarom niet leesbaar, bij elders en onbekend
    bewijs: str = ""     # hoe we weten dat dit klopt, bij gedeelde_db

    @property
    def leesbaar(self):
        return self.soort == GEDEELDE_DB and bool(self.schemas)

    def als_dict(self):
        uit = {"soort": self.soort}
        if self.schemas:
            uit["schemas"] = list(self.schemas)
        if self.reden:
            uit["reden"] = self.reden
        if self.bewijs:
            uit["vastgesteld_via"] = self.bewijs
        return uit


def _db(schemas, bewijs):
    return Bron(GEDEELDE_DB, tuple(schemas), bewijs=bewijs)


def _elders(reden):
    return Bron(ELDERS, reden=reden)


# Vastgesteld op 08-09-2026 door in de broncode op de VM te tellen welke
# schema's elke app bevraagt. Het getal tussen haakjes is het aantal
# schema-gekwalificeerde verwijzingen dat die telling opleverde.
GREP = "telling van schema-verwijzingen in de broncode op de VM, 08-09-2026"

BRONNEN = {
    # --- gedeelde database, met bewijs -------------------------------------
    "boekhouding": _db(("boekhouding", "monday"), f"{GREP}: boekhouding(37), monday(17)"),
    "communicatie": _db(("communicatie",), f"{GREP}: communicatie(9)"),
    "draaiboek": _db(("draaiboek", "kern"), f"{GREP}: draaiboek(48), kern(13)"),
    "hr": _db(("hr", "kern"), f"{GREP}: hr(112), kern(5)"),
    "intercompany": _db(("intercompany", "kern"), f"{GREP}: intercompany(26), kern(3)"),
    "kosten": _db(("kosten", "kern", "finance"), f"{GREP}: kosten(104), kern(28), finance(20)"),
    "medewerkers": _db(("kern", "organisatie", "kosten"), f"{GREP}: kern(153), kosten(96), organisatie(71)"),
    "monday": _db(("monday",), f"{GREP}: monday(26)"),
    "namen": _db(("namen", "organisatie", "kern"), f"{GREP}: organisatie(25), namen(13), kern(6)"),
    "omv": _db(("omv",), f"{GREP}: omv(269)"),
    "omv-v2": _db(("omv",), f"{GREP}: omv(269)"),
    "quickbooks": _db(("quickbooks",), f"{GREP}: quickbooks(11)"),
    "vermogen": _db(("vermogen", "kern"), f"{GREP}: vermogen(39), kern(2)"),
    "panden-dashboard": _db(("vermogen",), "pagina onder vermogen.globaal.be, zelfde app en schema"),
    "angela-sr": _db(("angela", "items"), f"{GREP}: angela(14), items(5), kosten(6)"),

    # --- staat elders, met de reden ----------------------------------------
    "renovision": _elders("Eigen Mongo-database per kopie. Vraagt een adapter (fase 3)."),
    "renovision-admin": _elders("Eigen Mongo-database per kopie. Vraagt een adapter (fase 3)."),
    "renovision-jean-charles": _elders("Eigen Mongo-database per kopie. Vraagt een adapter (fase 3)."),
    "renovision-marise": _elders("Eigen Mongo-database per kopie. Vraagt een adapter (fase 3)."),
    "renovision-mehdi": _elders("Eigen Mongo-database per kopie. Vraagt een adapter (fase 3)."),
    "renovision-mukesh": _elders("Eigen Mongo-database per kopie. Vraagt een adapter (fase 3)."),
    "renovision-raisha": _elders("Eigen Mongo-database per kopie. Vraagt een adapter (fase 3)."),
    "renovision-zjafhira": _elders("Eigen Mongo-database per kopie. Vraagt een adapter (fase 3)."),
    "staving": _elders("Native Postgres op poort 5432, eigen wachtwoord. Vraagt een adapter (fase 3)."),
    "stavingsstukken": _elders("Native Postgres op poort 5432, eigen wachtwoord. Vraagt een adapter (fase 3)."),
    "staving-review": _elders("Native Postgres op poort 5432, eigen wachtwoord. Vraagt een adapter (fase 3)."),
    "status": _elders("Uptime-Kuma houdt zijn eigen SQLite bij. Vraagt een adapter (fase 3)."),
    "schuldentracker": _elders(
        "Host-app met een eigen SQLite. Het schema `schuldentracker` in de "
        "gedeelde database heeft maar een tabel en is niet de bron. Vraagt een "
        "adapter (fase 3)."),
    "sales": _elders("Leest rechtstreeks uit Pipedrive, houdt zelf geen data. Zie de Pipedrive-MCP."),
    "renovision-mcp": _elders("Is zelf een MCP-server, geen gegevensbron."),
    "pipedrive-mcp": _elders("Is zelf een MCP-server, geen gegevensbron."),
    "boek-mcp": _elders("Is zelf een MCP-server, geen gegevensbron."),
}


# ---- Gevoelige tabellen -------------------------------------------------
#
# Toegang tot een app is niet hetzelfde als toegang tot alles wat eronder ligt.
# De apps weten dat zelf al: het Organisatie-dashboard laat de personeelskant
# alleen aan de hr-groep zien en de financiele kant aan admin of manager. Wie
# alleen de tegel mag openen, ziet daar dus geen salarissen.
#
# Zonder deze lijst zou de MCP dat onderscheid wegvagen. Vastgesteld op
# 08-09-2026: `sufa`, lid van alleen de groep `namenlijst`, kon via de app
# `medewerkers` bij `kern.persoon_beloning`. In de app zelf kan zij dat niet.
#
# Een categorie geldt voor de tabellen die erin staan, ongeacht via welke app
# je binnenkomt. `schema.*` betekent het hele schema.
CATEGORIEEN = {
    "personeel": {
        "groepen": ("hr", "admin", "manager"),
        "tabellen": ("hr.*",
                     "kern.persoon_beloning", "kern.persoon_hr",
                     "kern.persoon_afwezigheid", "kern.persoon_inzage",
                     "kern.persoon_dienstfirma"),
        "uitleg": "personeelsgegevens (beloning, verlof, hr-dossier)",
    },
    "financieel": {
        "groepen": ("kosten", "admin", "manager"),
        "tabellen": ("kosten.*", "kern.audit", "kern.audit_overzicht"),
        "uitleg": "financiele gegevens (banktransacties, kosten, audit)",
    },
}

# `kern.persoon` zelf staat er bewust NIET in: dat is de personeelslijst met
# naam, functie en afdeling, en die is platformbreed zichtbaar (telefoonregister,
# namenlijst). Het gevoelige zit in de tabellen eromheen.


def categorieen_in(schemas):
    """Welke gevoelige categorieen raken deze schema's."""
    uit = []
    for naam, cat in CATEGORIEEN.items():
        for tabel in cat["tabellen"]:
            if tabel.split(".")[0] in schemas:
                uit.append(naam)
                break
    return tuple(sorted(uit))


def categorieen_voor(groepen):
    """Welke categorieen deze groepen openen."""
    groepen = set(groepen or ())
    return tuple(sorted(naam for naam, cat in CATEGORIEEN.items()
                        if groepen & set(cat["groepen"])))


def ontbrekende_uitleg(schemas, groepen):
    """Wat deze gebruiker in deze app niet te zien krijgt, en waarom."""
    heeft = set(categorieen_voor(groepen))
    uit = []
    for naam in categorieen_in(schemas):
        if naam in heeft:
            continue
        cat = CATEGORIEEN[naam]
        uit.append(f"{cat['uitleg']}, alleen voor de groep "
                   f"{' of '.join(cat['groepen'])}")
    return uit


def rolnaam(slug, categorieen=()):
    """De Postgres-rol voor deze app op dit niveau.

    Staat hier zodat de generator en de server dezelfde naam maken; lopen die
    uiteen, dan kiest de server een rol die niet bestaat en valt alles stil, of
    erger: een rol die te veel mag.
    """
    naam = "mcp_app_" + str(slug).replace("-", "_")
    for cat in sorted(categorieen):
        naam += "_" + cat
    return naam


def bron_van(slug):
    """Waar de data van deze app staat. Onbekend is een geldig antwoord."""
    return BRONNEN.get(slug, Bron(ONBEKEND, reden=NIET_UITGEZOCHT))


def schemas_van(slug):
    """De schema's die deze app mag laten lezen, of niets."""
    bron = bron_van(slug)
    return bron.schemas if bron.leesbaar else ()


def overzicht(slugs):
    """Tel per soort, om te zien hoeveel er nog te doen staat."""
    telling = {GEDEELDE_DB: 0, ELDERS: 0, ONBEKEND: 0}
    for slug in slugs:
        telling[bron_van(slug).soort] += 1
    return telling

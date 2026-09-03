"""De Xelion-tools: wat Claude namens een ingelogde persoon mag doen.

Gescheiden van mcp_server.py zodat de OAuth-mantel (die identiek is aan die
van de Postbus) niet vermengd raakt met de inhoud.

Twee vaste regels in dit bestand:

1. Elke tool toetst zijn eigen recht met config.eisen(). Niet alleen bij het
   tonen van de rechten, maar bij elke aanroep. Een tool die dat vergeet is
   een gat.
2. Elke wijziging wordt geLOGd met wie, wat en welk object. Xelion kent geen
   prullenbak, dus het logboek is de enige weg terug naar wat er gebeurd is.
"""
import config
import xelionbron

BRON = xelionbron.BRON


def _oid(argumenten, sleutel="oid"):
    waarde = str(argumenten.get(sleutel) or "").strip()
    if not waarde:
        raise ValueError("'%s' is verplicht" % sleutel)
    return waarde


def bouw(log):
    """Geeft (tools, handlers). `log` is _log(wie, boodschap) uit mcp_server."""

    # ---- lezend ------------------------------------------------------
    def t_ik(wie, a):
        uit, fout = config.rechten(wie["gebruiker"], wie["groepen"])
        return {"gebruiker": wie["gebruiker"], "via": wie["bron"],
                "groepen": wie["groepen"], "rechten": uit,
                "let_op": fout,
                "nooit_mogelijk": [
                    "een verwijderd contact terughalen: Xelion heeft geen "
                    "prullenbak",
                    "iets doen waarvoor het recht hierboven op false staat"]}

    def t_contact_zoeken(wie, a):
        config.eisen(wie["gebruiker"], wie["groepen"], "lezen")
        naam = str(a.get("naam") or "").strip()
        if not naam:
            raise ValueError("'naam' is verplicht")
        rijen = BRON.zoek_contacten(naam, a.get("limiet") or 10)
        return {"gezocht": naam, "aantal": len(rijen), "contacten": rijen}

    def t_contact(wie, a):
        config.eisen(wie["gebruiker"], wie["groepen"], "lezen")
        oid = _oid(a)
        uit = BRON.contact(oid)
        try:
            uit["telecom_labels"] = BRON.labels(oid)
        except Exception:
            pass
        return uit

    def t_lijsten(wie, a):
        config.eisen(wie["gebruiker"], wie["groepen"], "lezen")
        rijen = BRON.lijsten(a.get("naam"))
        return {"aantal": len(rijen), "lijsten": rijen}

    def t_gesprekken(wie, a):
        config.eisen(wie["gebruiker"], wie["groepen"], "lezen")
        rijen = BRON.gesprekken(a.get("limiet") or 25)
        return {"aantal": len(rijen), "gesprekken": rijen}

    # ---- wijzigend ---------------------------------------------------
    def t_contact_aanmaken(wie, a):
        config.eisen(wie["gebruiker"], wie["groepen"], "aanmaken")
        naam = str(a.get("weergavenaam") or "").strip()
        if not naam:
            raise ValueError("'weergavenaam' is verplicht")
        oid = BRON.contact_aanmaken(
            naam, telefoons=a.get("telefoons"), emails=a.get("emails"),
            roepnaam=a.get("roepnaam"))
        log(wie, "maakte contact %s aan (%s)" % (oid, naam))
        return {"gedaan": "contact aangemaakt", "oid": oid, "weergavenaam": naam,
                "let_op": "Xelion toont deze naam op het belscherm."}

    def t_contact_bijwerken(wie, a):
        config.eisen(wie["gebruiker"], wie["groepen"], "bijwerken")
        oid = _oid(a)
        operaties = a.get("operaties")
        if not isinstance(operaties, list) or not operaties:
            raise ValueError(
                "'operaties' is een lijst JSON-Patch-stappen, bijvoorbeeld "
                '[{"op": "replace", "path": "/givenName", "value": "Nieuwe Naam"}]')
        voor = {}
        try:
            voor = BRON.contact(oid)
        except Exception:
            pass
        BRON.contact_bijwerken(oid, operaties)
        log(wie, "wijzigde contact %s: %s" % (oid, operaties))
        return {"gedaan": "contact bijgewerkt", "oid": oid,
                "was": voor, "operaties": operaties}

    def t_contact_verwijderen(wie, a):
        config.eisen(wie["gebruiker"], wie["groepen"], "verwijderen")
        oid = _oid(a)
        # Eerst ophalen, zodat het logboek vastlegt wat er verdween. Dit is de
        # enige vorm van terugvinden die er is.
        was = {}
        try:
            was = BRON.contact(oid)
        except Exception:
            pass
        if not a.get("bevestigd"):
            raise ValueError(
                "Verwijderen is definitief; Xelion heeft geen prullenbak. "
                "Toon de gebruiker eerst dit contact en roep opnieuw aan met "
                "bevestigd=true als hij het echt wil. Contact: %s" % (was or oid))
        BRON.contact_verwijderen(oid)
        log(wie, "VERWIJDERDE contact %s definitief: %s" % (oid, was))
        return {"gedaan": "contact definitief verwijderd", "oid": oid,
                "was": was,
                "let_op": "Dit is niet terug te draaien."}

    def t_lijst_aanmaken(wie, a):
        config.eisen(wie["gebruiker"], wie["groepen"], "aanmaken")
        naam = str(a.get("naam") or "").strip()
        if not naam:
            raise ValueError("'naam' is verplicht")
        oid = BRON.lijst_aanmaken(naam)
        log(wie, "maakte lijst %s aan (%s)" % (oid, naam))
        return {"gedaan": "lijst aangemaakt", "oid": oid, "naam": naam}

    def t_lijst_toevoegen(wie, a):
        config.eisen(wie["gebruiker"], wie["groepen"], "bijwerken")
        lijst, contact = _oid(a, "lijst_oid"), _oid(a, "contact_oid")
        BRON.lijst_toevoegen(lijst, contact)
        log(wie, "zette contact %s op lijst %s" % (contact, lijst))
        return {"gedaan": "contact aan lijst toegevoegd",
                "lijst_oid": lijst, "contact_oid": contact}

    def t_lijst_afhalen(wie, a):
        config.eisen(wie["gebruiker"], wie["groepen"], "bijwerken")
        lijst, contact = _oid(a, "lijst_oid"), _oid(a, "contact_oid")
        BRON.lijst_verwijderen_uit(lijst, contact)
        log(wie, "haalde contact %s van lijst %s" % (contact, lijst))
        return {"gedaan": "contact van lijst gehaald",
                "lijst_oid": lijst, "contact_oid": contact,
                "let_op": "Het contact zelf bestaat nog."}

    tools = [
        dict(name="ik",
             description="Wie ben ik voor Xelion en wat mag ik: lezen, "
                         "aanmaken, bijwerken, verwijderen. Begin hiermee.",
             inputSchema={"type": "object", "properties": {}}),
        dict(name="contact_zoeken",
             description="Zoek contacten op naam in de telefooncentrale.",
             inputSchema={"type": "object", "properties": {
                 "naam": {"type": "string"},
                 "limiet": {"type": "integer",
                            "description": "1 tot 100, standaard 10"}},
                 "required": ["naam"]}),
        dict(name="contact",
             description="Alle gegevens van een contact, inclusief de "
                         "telecomlabels. Het oid komt uit contact_zoeken.",
             inputSchema={"type": "object", "properties": {
                 "oid": {"type": "string"}}, "required": ["oid"]}),
        dict(name="lijsten",
             description="De lijsten in Xelion; met 'naam' filter je erop.",
             inputSchema={"type": "object", "properties": {
                 "naam": {"type": "string"}}}),
        dict(name="gesprekken",
             description="De recentste telefoongesprekken.",
             inputSchema={"type": "object", "properties": {
                 "limiet": {"type": "integer",
                            "description": "1 tot 100, standaard 25"}}}),
        dict(name="contact_aanmaken",
             description="Maak een nieuw contact aan. WIJZIGT DE CENTRALE. De "
                         "weergavenaam is wat op het belscherm verschijnt.",
             inputSchema={"type": "object", "properties": {
                 "weergavenaam": {"type": "string"},
                 "roepnaam": {"type": "string"},
                 "telefoons": {"type": "array", "items": {"type": "object"},
                               "description": "[{\"nummer\": \"+32...\", "
                                              "\"label\": \"mobiel\"}]"},
                 "emails": {"type": "array", "items": {"type": "string"}}},
                 "required": ["weergavenaam"]}),
        dict(name="contact_bijwerken",
             description="Wijzig een bestaand contact met JSON-Patch-operaties. "
                         "WIJZIGT DE CENTRALE. Het antwoord bevat de oude "
                         "waarden onder 'was'.",
             inputSchema={"type": "object", "properties": {
                 "oid": {"type": "string"},
                 "operaties": {"type": "array", "items": {"type": "object"}}},
                 "required": ["oid", "operaties"]}),
        dict(name="contact_verwijderen",
             description="Verwijder een contact DEFINITIEF. Xelion heeft geen "
                         "prullenbak, dit is niet terug te draaien. Roep eerst "
                         "aan zonder bevestigd, toon de gebruiker wat er weg "
                         "gaat, en pas daarna met bevestigd=true.",
             inputSchema={"type": "object", "properties": {
                 "oid": {"type": "string"},
                 "bevestigd": {"type": "boolean"}}, "required": ["oid"]}),
        dict(name="lijst_aanmaken",
             description="Maak een nieuwe lijst. WIJZIGT DE CENTRALE.",
             inputSchema={"type": "object", "properties": {
                 "naam": {"type": "string"}}, "required": ["naam"]}),
        dict(name="lijst_toevoegen",
             description="Zet een bestaand contact op een lijst. WIJZIGT DE "
                         "CENTRALE.",
             inputSchema={"type": "object", "properties": {
                 "lijst_oid": {"type": "string"},
                 "contact_oid": {"type": "string"}},
                 "required": ["lijst_oid", "contact_oid"]}),
        dict(name="lijst_afhalen",
             description="Haal een contact van een lijst. Het contact zelf "
                         "blijft bestaan. WIJZIGT DE CENTRALE.",
             inputSchema={"type": "object", "properties": {
                 "lijst_oid": {"type": "string"},
                 "contact_oid": {"type": "string"}},
                 "required": ["lijst_oid", "contact_oid"]}),
    ]

    handlers = {
        "ik": t_ik,
        "contact_zoeken": t_contact_zoeken,
        "contact": t_contact,
        "lijsten": t_lijsten,
        "gesprekken": t_gesprekken,
        "contact_aanmaken": t_contact_aanmaken,
        "contact_bijwerken": t_contact_bijwerken,
        "contact_verwijderen": t_contact_verwijderen,
        "lijst_aanmaken": t_lijst_aanmaken,
        "lijst_toevoegen": t_lijst_toevoegen,
        "lijst_afhalen": t_lijst_afhalen,
    }
    return tools, handlers

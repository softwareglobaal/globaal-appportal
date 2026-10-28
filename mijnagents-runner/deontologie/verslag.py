"""Het toetsverslag van De Deontologiewacht, met de kleuren (opdrachtkaart v0.3, stap 3 van de bouw).

De harde controles zelf komen in de volgende stappen (masters, werfverslagen, budget). Deze module krijgt hun uitkomst per
regel en maakt er het verslag van, met de kleurregels van de ontwerplezing (driehoeksoverleg 27-10-2026, 3-0, voorwaarden
2 en 5):

- rood alleen uit een harde, letterlijke regel die faalt;
- een oordeel of afgeleide regel die faalt, ontbrekende gegevens of "niet getoetst" is hoogstens oranje; een oordeel
  dat in orde is, is groen (OORDEEL_IN_ORDE_IS_GROEN, keuze aan Mehdi van 28-10-2026);
- een regel van het register die voor deze documentsoort geldt maar geen uitkomst kreeg, staat er als niet getoetst
  (oranje): wat niet bekeken is, kan niet stil groen worden;
- de bibliotheek ouder dan BIBLIOTHEEK_MAX_DAGEN of een register dat niet door valideer() komt: alles hoogstens oranje,
  ook wat rood zou zijn, met de reden bovenaan;
- het verslag noemt altijd de bronversie, de datum van de bibliotheek en de zin VOORBEHOUD.

Een uitkomst is een `Bevinding`: de regelcode, of de regel slaagt (SLAAGT, FAALT, ONBEKEND), de plaats in het document en
het voorstel (de zin zoals ze er volgens het reglement moet staan, of de handeling die ontbreekt). De totale kleur is de
ergste kleur van de punten. Oranje en rood vertrekken pas na een bevestiging van Mehdi; dat bewaakt de grendel (stap 5),
niet dit verslag.

Gebruik: `maak("contract", bevindingen)` geeft een `Verslag`; `.markdown()` is de tekst voor het bord.
"""
from dataclasses import dataclass, field
from datetime import date

from . import register as R

GROEN, ORANJE, ROOD = "groen", "oranje", "rood"
ERNST = {GROEN: 0, ORANJE: 1, ROOD: 2}
SLAAGT, FAALT, ONBEKEND = "slaagt", "faalt", "onbekend"
NIET_GETOETST = "niet getoetst"
# Een oordeel of afgeleide regel die slaagt (of niet van toepassing is), telt als groen; oranje blijft voor twijfel en
# voor een oordeel dat faalt. Aanbevolen keuze aan Mehdi op 28-10-2026: letterlijk volgens de ontwerplezing ("groen
# alleen uit een harde regel") werd elk werfverslag oranje en wachtte het op zijn klik. Kiest Mehdi daarvoor, dan False.
OORDEEL_IN_ORDE_IS_GROEN = True
BIBLIOTHEEK_MAX_DAGEN = 45
VOORBEHOUD = "Dit is een toets, geen juridisch advies."


@dataclass(frozen=True)
class Bevinding:
    code: str
    uitkomst: str  # SLAAGT, FAALT of ONBEKEND
    plaats: str = ""  # waar in het document: artikel, pagina, alinea
    voorstel: str = ""  # de zin zoals ze er moet staan, of de handeling die ontbreekt
    toelichting: str = ""


@dataclass
class Punt:
    code: str
    titel: str
    artikel: str
    kleur: str
    uitkomst: str
    plaats: str
    voorstel: str
    waarom: str


@dataclass
class Verslag:
    documentsoort: str
    kleur: str
    punten: list
    bron: str
    bibliotheek: str
    waarschuwingen: list = field(default_factory=list)
    notities: list = field(default_factory=list)

    def markdown(self):
        regels = [f"**Toets: {self.kleur.upper()}** ({self.documentsoort})", "",
                  f"Bron: {self.bron}, bibliotheek van {self.bibliotheek}. {VOORBEHOUD}"]
        for w in self.waarschuwingen:
            regels.append(f"Let op: {w}")
        for n in self.notities:
            regels.append(f"Noot: {n}")
        regels.append("")
        for p in sorted(self.punten, key=lambda p: (-ERNST[p.kleur], p.code)):
            regels.append(f"- {p.kleur.upper()} {p.code} {p.titel} (art. {p.artikel}): {p.waarom}")
            if p.plaats:
                regels.append(f"  Plaats: {p.plaats}")
            if p.voorstel and p.kleur != GROEN:
                regels.append(f"  Voorstel: {p.voorstel}")
        return "\n".join(regels)


def _kleur(regel, uitkomst):
    """De kleur van een punt, uit de regel van het register en de uitkomst van de controle."""
    hard = regel["type"] == "HARD" and regel["status"] == "LETTERLIJK" and regel["max_kleur"] == ROOD
    if uitkomst == SLAAGT:
        if hard:
            return GROEN, "voldoet"
        return (GROEN, "in orde (oordeel)") if OORDEEL_IN_ORDE_IS_GROEN else (ORANJE, "oordeel of afgeleide regel: Mehdi kijkt na")
    if uitkomst == FAALT:
        return (ROOD, "voldoet niet") if hard else (ORANJE, "lijkt niet te voldoen, oordeel van Mehdi nodig")
    if uitkomst == NIET_GETOETST:
        return ORANJE, "niet getoetst"
    return ORANJE, "gegevens ontbreken om te toetsen"


def _bibliotheek(register, vandaag, basis):
    """Waarschuwingen over de bibliotheek; een niet-lege lijst maakt alles hoogstens oranje."""
    w = []
    fouten = R.valideer(register, basis)
    if fouten:
        w.append(f"het regelregister komt niet door de controle ({len(fouten)} fouten), alles is hoogstens oranje")
    try:
        stand = date.fromisoformat(register.get("stand", ""))
    except ValueError:
        w.append("de datum van de bibliotheek ontbreekt, alles is hoogstens oranje")
    else:
        if (vandaag - stand).days > BIBLIOTHEEK_MAX_DAGEN:
            w.append(f"de bibliotheek is ouder dan {BIBLIOTHEEK_MAX_DAGEN} dagen, alles is hoogstens oranje")
    return w


def maak(documentsoort, bevindingen, register=None, vandaag=None, basis=R.HIER, elders=()):
    """Het verslag voor een document. Elke regel van het register voor deze soort krijgt een punt, behalve de regels in
    `elders`: die horen bij het dossier (zoals C4, een verslag bij elke kritieke fase) en staan apart vermeld."""
    if documentsoort not in R.DOCUMENTEN:
        raise ValueError(f"onbekende documentsoort {documentsoort!r}")
    register = register or R.laad()
    vandaag = vandaag or date.today()
    van_toepassing = {r["code"]: r for r in R.regels(documentsoort, register) if r["code"] not in elders}
    per_code = {}
    for b in bevindingen:
        if b.code not in van_toepassing:
            raise ValueError(f"regel {b.code!r} geldt niet voor {documentsoort} of staat niet in het register")
        if b.uitkomst not in (SLAAGT, FAALT, ONBEKEND):
            raise ValueError(f"onbekende uitkomst {b.uitkomst!r} bij {b.code}")
        if b.code in per_code:
            raise ValueError(f"regel {b.code} kreeg twee uitkomsten")
        per_code[b.code] = b
    waarschuwingen = _bibliotheek(register, vandaag, basis)
    notities = [f"op dossierniveau getoetst, niet in dit verslag: {', '.join(sorted(elders))}"] if elders else []
    punten = []
    for code, regel in van_toepassing.items():
        b = per_code.get(code) or Bevinding(code, NIET_GETOETST)
        kleur, waarom = _kleur(regel, b.uitkomst)
        if waarschuwingen and kleur != ORANJE:
            kleur, waarom = ORANJE, f"{waarom}, maar de bibliotheek is niet betrouwbaar"
        if b.toelichting:
            waarom = f"{waarom}; {b.toelichting}"
        punten.append(Punt(code, regel["titel"], regel["artikel"], kleur, b.uitkomst, b.plaats,
                           b.voorstel or regel.get("toets", ""), waarom))
    totaal = max((p.kleur for p in punten), key=ERNST.get, default=ORANJE)
    bron = ", ".join(sorted({regel["bron"] for regel in van_toepassing.values()})) or "geen regels"
    return Verslag(documentsoort, totaal, punten, f"{bron} (register {register.get('versie', '?')})",
                   register.get("stand", "onbekend"), waarschuwingen, notities)

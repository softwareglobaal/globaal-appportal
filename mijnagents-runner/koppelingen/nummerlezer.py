"""De gedeelde nummerlezer: dossiernummers lezen uit hun bron, nooit uit een los getal.

Codering WP1 (opdracht van 05-10-2026, voorstel v0.3). Vervangt de vaste patronen ^(26|56)xx die in
de runbook-, Contracten-, Fathom-, Agenda- en Archivaris-routes stonden en in 2027 nieuwe H-A-nummers
zouden missen of weigeren.

Grondregel: een getal is pas een dossiernummer als de BRON zegt dat er op die plaats een nummer staat.
Een los getal van vier cijfers kan een postcode (2800 Mechelen), een huisnummer (Teststraat 2603), een
datum of een jaartal zijn. Bij meer kandidaten kiest deze lezer niets: dat doet de aanroeper, met bewijs.

Firmacodes komen uit het bestaande register (kern.firma via koppelingen/organisatie.py) en de bestaande
aliasbron (werkwijze/agenda-taken.json, titelconventie.oude_codes). Er is hier geen eigen firmalijst.
Is het register niet bereikbaar, dan valt de lezer terug op de master van de agenda (zelfde bestand).

WAT DEZE HERSTELRONDE ONDERSTEUNT (uitdrukkelijk):
  * HARC (H-Architects): nummerregel BEVESTIGD (werkinstructie contracten D9, H-A Projecten P11):
      JJNN     architectuur, voorstudie en addendum van 20JJ          (2603 = 2026)
      (JJ+30)NN regularisatie van 20JJ                                (5603 = 2026, 6003 = 2030)
    Geen ondergrens (een oud dossier blijft leesbaar); bovengrens: het lopende jaar + 1 (een nummer voor
    volgend jaar kan in december al bestaan). Passen beide lezingen (vanaf 2029: 3003 = 2030 of 2000),
    dan zijn beide lezingen er en is het jaar onbepaald tot de context het zegt.
  * UNAB, TKNB, ENEF: het nummer wordt gelezen in zijn eigen bron (agendatitel van die firma,
    TKN-projectmap, factuur van die administratie) als 'engineering', zonder jaar en zonder
    dossierhouder: de regel is waargenomen, niet bevestigd.
  * Elke andere firma in kern.firma (HI, HB, CX, ...): de code wordt herkend, een nummer niet bevestigd.
  * Een code die in register noch aliasbron staat (ZZ): blijft onbekend, nooit een firma.
  * AL, PR en LA (algemeen, prive, Lara) zijn geen firma's: daaraan hangt geen dossier.

Gebruik:
    lees(tekst, bron, jaar_nu=None, jaarmap=None, register=None) -> [Kandidaat]
    ha_nummer(tekst, bron, jaar_nu=None)  -> '2603' of '' (een H-A-nummer, alleen als er precies een is)
    ha_lezingen('5603', 2026)              -> ((2026, 'regularisatie'),)
    ha_voorvoegsel('regularisatie', 2027)  -> '57'
"""
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
    _BRUSSEL = ZoneInfo("Europe/Brussels")
except Exception:  # noqa: BLE001
    _BRUSSEL = None

HIER = os.path.dirname(os.path.abspath(__file__))
AGENDA_MASTER = os.path.join(os.path.dirname(HIER), "werkwijze", "agenda-taken.json")

NUMMERREGEL_BEVESTIGD = {"HARC"}             # D9 en P11; elke andere firma: geen bevestigde regel
ENGINEERING = {"UNAB", "TKNB", "ENEF"}       # TKN-nummers, waargenomen (46118, 4437, 260009)

BRONNEN = ("pipedrive_titel", "contractbestand", "mapnaam_ha", "mapnaam_tkn", "agenda_titel",
           "vergadertitel", "factuur", "contactnaam", "vrije_tekst", "nummerveld")

STRAATWOORD = re.compile(r"(straat|laan|weg|plein|dreef|steenweg|lei|baan|kaai|kade|berg|hof|pad|singel|dijk|"
                         r"markt|veld|ring|dam|park|wijk|vest|gang|hoek|heide|bos|velden|weide)$", re.I)
# Een dossiercode: twee hoofdletters aan het nummer geplakt (HA2603, UN3782, TK46118, UB260009). Of die
# twee letters een firma zijn, zegt het register, niet dit patroon.
DOSSIERCODE = re.compile(r"\b([A-Z]{2})(\d{3,6})\b")
AGENDACODE = re.compile(r"\[\s*([A-Za-zÀ-ÿ]{2,14})\s*-\s*([A-Za-z]{2})\s*\]")
TREFWOORD = re.compile(r"\b(?:dossier|project|projectnummer|projectnr\.?|nr\.?)\s*(\d{4,6})\b", re.I)


@dataclass(frozen=True)
class Kandidaat:
    nummer: str
    firma: str | None          # interne code uit kern.firma (HARC, UNAB, ...); None = niet vastgesteld
    code: str                  # zoals geschreven: 'HA', 'HARMONIEBOUW', 'ZZ', of ''
    rol: str                   # wat de firma hier betekent: agendafirma, facturerende_firma, contactfirma,
                               # dossierhouder, of '' als de bron het niet zegt
    lezingen: tuple            # ((jaar, reeks), ...) volgens een BEVESTIGDE regel; leeg = geen regel
    bron: str
    reden: str
    zeker: bool

    @property
    def jaar(self):
        return self.lezingen[0][0] if len(self.lezingen) == 1 else None

    @property
    def reeks(self):
        return self.lezingen[0][1] if len(self.lezingen) == 1 else None


# ------------------------------------------------------------------ H-A-regel ---

def jaar_nu_brussel():
    return datetime.now(_BRUSSEL).year if _BRUSSEL else datetime.now().year


def ha_lezingen(nummer, jaar_nu=None):
    """Alle lezingen van een H-A-nummer volgens D9/P11. Leeg = geen geldig H-A-nummer."""
    nummer = str(nummer or "").strip()
    if not re.fullmatch(r"\d{4}", nummer):
        return ()
    jaar_nu = jaar_nu or jaar_nu_brussel()
    jj = int(nummer[:2])
    uit = []
    if 2000 + jj <= jaar_nu + 1:
        uit.append((2000 + jj, "architectuur"))
    if jj >= 30 and 2000 + jj - 30 <= jaar_nu + 1:
        uit.append((2000 + jj - 30, "regularisatie"))
    return tuple(uit)


def ha_voorvoegsel(soort, jaar):
    """De twee eerste cijfers van de H-A-reeks voor een volledig jaar (D9): architectuur, voorstudie en
    addendum JJ; regularisatie JJ+30. Een fout als de regel voor dat jaar geen twee cijfers meer geeft."""
    if soort not in ("architectuur", "voorstudie", "addendum", "regularisatie"):
        raise ValueError(f"onbekende H-A-contractsoort: {soort}")
    jaar = int(jaar)
    if not 2000 <= jaar <= 2099:
        raise ValueError(f"jaar {jaar} valt buiten de H-A-regel")
    jj = jaar % 100
    p = jj + 30 if soort == "regularisatie" else jj
    if p > 99:
        raise ValueError(f"regularisatiereeks voor {jaar} heeft geen twee cijfers meer (JJ+30 = {p})")
    return f"{p:02d}"


# ------------------------------------------------------------------ codes ---

_standaard = {"ts": 0.0, "codes": None}
CACHE_SECONDEN = 3600


def _master():
    try:
        return json.load(open(AGENDA_MASTER, encoding="utf-8")).get("titelconventie", {})
    except (OSError, ValueError):
        return {}


def codes(register=None):
    """De codetabellen uit register en aliasbron. register = lijst zoals organisatie.firmas() (voor tests
    of als de aanroeper hem al heeft); zonder register wordt organisatie.firmas() gelezen (een uur bewaard).

    Geeft {'agenda': {code: intern}, 'contact': {code: intern}, 'alias': {oud: intern},
           'niet_firma': {code}, 'bron': 'register' | 'aliasbron (register niet bereikbaar)',
           'dubbel': {code: [intern, ...]}}"""
    if register is None:
        import time
        if _standaard["codes"] is not None and time.time() - _standaard["ts"] < CACHE_SECONDEN:
            return _standaard["codes"]
        try:
            import organisatie  # alleen op de host; tests geven een register mee
            gelezen = organisatie.firmas()
        except Exception:  # noqa: BLE001
            gelezen = []
        _standaard["codes"], _standaard["ts"] = _bouw_codes(gelezen), time.time()
        return _standaard["codes"]
    return _bouw_codes(register)


def _bouw_codes(register):
    t = _master()
    oud = (t.get("oude_codes") or {}).get("firma") or {}
    niet_firma = set((t.get("niet_firma") or {}).keys()) | {o for o, n in oud.items() if n in (t.get("niet_firma") or {})}
    agenda, contact, bron = {}, {}, "register"
    for f in register or []:
        if not f.get("code"):
            continue
        if f.get("code_agenda"):
            agenda.setdefault(f["code_agenda"], set()).add(f["code"])
        if f.get("code_contact"):
            contact.setdefault(f["code_contact"], set()).add(f["code"])
    if not agenda:
        # Terugval: de master van de agenda kent elke interne code (oude_codes: HARC -> HA, ...).
        bron = "aliasbron (register niet bereikbaar)"
        for o, n in oud.items():
            if len(o) == 4 and o.isalpha() and n not in niet_firma:
                agenda.setdefault(n, set()).add(o)
    dubbel = {c: sorted(v) for tabel in (agenda, contact) for c, v in tabel.items() if len(v) > 1}
    agenda = {c: next(iter(v)) for c, v in agenda.items() if len(v) == 1}
    contact = {c: next(iter(v)) for c, v in contact.items() if len(v) == 1}
    alias = {}
    for o, n in oud.items():
        if n in agenda:
            alias[o] = agenda[n]
    for intern in set(agenda.values()):
        alias.setdefault(intern, intern)          # de interne code zelf (oude titels: [HARC-KB])
    return {"agenda": agenda, "contact": contact, "alias": alias, "niet_firma": niet_firma, "bron": bron,
            "dubbel": dubbel}


def opdrachtcodes():
    """De opdrachtcodes van een agendatitel ('[HA-KB] WB 2603'): de types uit de master van de agenda en hun
    oude schrijfwijzen (oude_codes.opdracht). Uit hetzelfde bestand als de aliassen; geen eigen lijst."""
    t = _master()
    return set((t.get("types") or {}).keys()) | set(((t.get("oude_codes") or {}).get("opdracht") or {}).keys())


def firma_van_code(code, soort="agenda", register=None):
    """Interne firmacode voor een geschreven code, of None (onbekend of geen firma)."""
    c = codes(register)
    code = (code or "").upper()
    if code in c["niet_firma"]:
        return None
    if soort == "contact":
        return c["contact"].get(code)
    return c["agenda"].get(code) or c["alias"].get(code)


def agendacode_van_titel(tekst):
    """De geschreven firmacode, ook als hij onbekend is. Onbekend is geen toestemming voor H-A."""
    m = AGENDACODE.search(tekst or "")
    return m.group(1).upper() if m else ""


# ------------------------------------------------------------------ lezen ---

def _ha_kandidaat(nummer, code, rol, bron, reden, jaar_nu, zeker=True):
    lez = ha_lezingen(nummer, jaar_nu)
    if not lez:
        return None
    if len(lez) > 1:
        reden += "; jaar onbepaald: " + " of ".join(f"{j} ({r})" for j, r in lez)
    return Kandidaat(nummer, "HARC", code, rol, lez, bron, reden, zeker)


def _met_firma(nummer, firma, code, rol, bron, reden, jaar_nu, jaarmap=None):
    """Kandidaat voor een firma die de bron noemt; de nummerregel bepaalt jaar en zekerheid."""
    if firma in NUMMERREGEL_BEVESTIGD:
        return _ha_kandidaat(nummer, code, rol, bron, reden, jaar_nu)
    lez = ((jaarmap, "engineering"),) if (jaarmap and firma in ENGINEERING) else ()
    if firma in ENGINEERING:
        reden += "; engineeringnummer: regel waargenomen, niet bevestigd; geen dossierhouder"
    elif firma:
        reden += f"; geen bevestigde nummerregel voor {firma}"
    else:
        reden += "; firma niet vastgesteld"
    return Kandidaat(nummer, firma, code, rol, lez, bron, reden, False)


def _midden_ok(tekst, start, eind, nummer, jaar_nu):
    """Mag een getal midden in een titel gelezen worden? Niet als het een postcode, huisnummer, datum of
    kaal jaartal is."""
    voor, na = tekst[:start], tekst[eind:]
    voor_s = voor.rstrip()
    gemeente_na = bool(re.match(r"\s+[A-ZÀ-Ý][a-zà-ÿ]", na))
    if voor_s.endswith(","):                                           # ..., 2800 Mechelen
        return False
    if gemeente_na and re.search(r"\b\d+[a-zA-Z]?$", voor_s):          # Teststraat 1 2800 Mechelen
        return False
    if re.search(r"(?i)\bpostcode$", voor_s):                          # postcode 2500
        return False
    vorige = re.search(r"([A-Za-zÀ-ÿ'-]+)\s*$", voor)
    if vorige and STRAATWOORD.search(vorige.group(1)):                 # Teststraat 2603
        return False
    if re.search(r"\d[-/.]\s*$", voor) or re.match(r"\s*[-/.]\d", na):  # 17-09-2026, 2026-09-17
        return False
    if 1990 <= int(nummer) <= jaar_nu + 5:                            # in 2026, 2030
        return False
    return True


def _glued(tekst, c, bron, rol, jaar_nu, soorten=("agenda", "contact")):
    """Dossiercodes zoals HA2603, UN3782, TK46118: twee letters aan het nummer geplakt."""
    uit = []
    for m in DOSSIERCODE.finditer(tekst):
        code, nummer = m.group(1), m.group(2)
        if code in c["niet_firma"]:
            continue
        firma = None
        for s in soorten:
            firma = firma or (c["contact"].get(code) if s == "contact" else c["agenda"].get(code))
        if firma is None:
            uit.append(Kandidaat(nummer, None, code, "", (), bron, f"onbekende code {code}: geen firma", False))
            continue
        k = _met_firma(nummer, firma, code, rol, bron, "dossiercode", jaar_nu)
        if k:
            uit.append(k)
    return uit


def lees(tekst, bron, jaar_nu=None, jaarmap=None, register=None, administratie=None):
    """Kandidaten met hun reden. bron is een van BRONNEN; administratie = code van de facturerende
    administratie bij 'factuur' (interne code of agendacode)."""
    if bron not in BRONNEN:
        raise ValueError(f"onbekende bron: {bron}")
    tekst = tekst or ""
    jaar_nu = jaar_nu or jaar_nu_brussel()
    c = codes(register)

    if bron in ("pipedrive_titel", "contractbestand"):
        # Alleen het H-A-account (bedrijf-id 10068585): het nummer staat vooraan (D9).
        m = re.match(r"^\s*(\d{4})(?=\s|\.|$)", tekst)
        k = _ha_kandidaat(m.group(1), "", "dossierhouder", bron, f"{bron}: nummer vooraan (D9)", jaar_nu) if m else None
        return [k] if k else []

    if bron == "mapnaam_ha":
        if re.match(r"^\s*\d{4}-\d{2}-\d{2}", tekst):
            return []                                    # momentmap of opname, geen projectmap
        m = re.match(r"^\s*(\d{4})(?:\(\d{4}\))?\s+(?=\D)", tekst)
        k = _ha_kandidaat(m.group(1), "", "dossierhouder", bron, "projectmap H-A (A13)", jaar_nu) if m else None
        return [k] if k else []

    if bron == "mapnaam_tkn":
        m = re.match(r"^\s*(\d{4,6})[_ ]", tekst)
        if not m:
            return []
        reden = "projectmap in de TKN-boom; de map zegt niet welke firma dossierhouder is"
        lez = ((jaarmap, "engineering"),) if jaarmap else ()
        if jaarmap:
            reden += f"; jaar uit de jaarmap {jaarmap}"
        return [Kandidaat(m.group(1), None, "", "", lez, bron, reden, False)]

    if bron in ("agenda_titel", "vergadertitel"):
        m = re.search(AGENDACODE.pattern + r"\s*(?:([A-Z]{2,4})\s+)?(\d{4,6})\b", tekst)
        if m:
            code = m.group(1).upper()
            if code in c["niet_firma"]:
                return []
            firma = firma_van_code(code, "agenda", register)
            if firma is None:
                return [Kandidaat(m.group(4), None, code, "", (), bron, f"onbekende code {code}: geen firma", False)]
            k = _met_firma(m.group(4), firma, code, "agendafirma", bron,
                           "agendatitel: de firma tussen haken is de agendafirma, niet noodzakelijk de dossierhouder",
                           jaar_nu)
            return [k] if k else []
        if bron == "agenda_titel":
            return []
        # vergadertitel zonder agendacode: nummer vooraan, een dossiercode, of een getal midden in de titel
        uit = []
        m = re.match(r"^\s*(\d{4,6})(?=\s|$|\W)", tekst)
        if m and _midden_ok(tekst, m.start(1), m.end(1), m.group(1), jaar_nu):
            n = m.group(1)
            k = (_ha_kandidaat(n, "", "", bron, "nummer vooraan een vergadertitel", jaar_nu, zeker=False)
                 if len(n) == 4 else None)
            uit.append(k or Kandidaat(n, None, "", "", (), bron, "nummer vooraan; firma niet vastgesteld", False))
        uit += _glued(tekst, c, bron, "", jaar_nu)
        if not uit:
            for mm in re.finditer(r"(?<![\w-])(\d{4})(?![\w-])", tekst):
                n = mm.group(1)
                if _midden_ok(tekst, mm.start(1), mm.end(1), n, jaar_nu):
                    k = _ha_kandidaat(n, "", "", bron, "getal midden in een vergadertitel", jaar_nu, zeker=False)
                    if k:
                        uit.append(k)
        return uit

    if bron == "factuur":
        if re.match(r"^\s*[A-Z]{2,3}-\d{4,6}\b", tekst):
            return []                                    # factuurnummer (HA-26021), geen dossier
        m = re.match(r"^\s*(\d{4,6})\b", tekst)
        if not m:
            return []
        adm = (administratie or "").upper()
        firma = adm if adm in set(c["agenda"].values()) else firma_van_code(adm, "agenda", register)
        k = _met_firma(m.group(1), firma, adm, "facturerende_firma", bron,
                       "factuuromschrijving: de administratie is de facturerende firma, niet noodzakelijk de dossierhouder",
                       jaar_nu)
        return [k] if k else []

    if bron == "contactnaam":
        return _glued(tekst, c, bron, "contactfirma", jaar_nu, soorten=("contact",))

    if bron == "nummerveld":
        n = tekst.strip()
        if re.fullmatch(r"\d{4}", n):
            k = _ha_kandidaat(n, "", "", bron, "nummerveld", jaar_nu, zeker=False)
            return [k] if k else [Kandidaat(n, None, "", "", (), bron, "nummerveld; geen H-A-lezing", False)]
        if re.fullmatch(r"\d{5,6}", n):
            return [Kandidaat(n, None, "", "", (), bron, "nummerveld; firma niet vastgesteld", False)]
        return []

    # vrije tekst: een dossiercode of een getal na een trefwoord; nooit een kaal getal
    uit = _glued(tekst, c, bron, "", jaar_nu)
    for m in TREFWOORD.finditer(tekst):
        uit.append(Kandidaat(m.group(1), None, "", "", (), bron, "trefwoord voor het getal; firma onbekend", False))
    return uit


def ha_nummer(tekst, bron, jaar_nu=None, register=None):
    """Het H-A-nummer in deze tekst, alleen als er precies een is; anders ''."""
    nummers = {k.nummer for k in lees(tekst, bron, jaar_nu, register=register) if k.firma == "HARC"}
    return nummers.pop() if len(nummers) == 1 else ""


def enig(kandidaten, firma=None):
    """De enige kandidaat (eventueel van een firma), of None als er geen of meer zijn."""
    lijst = [k for k in kandidaten if firma is None or k.firma == firma]
    sleutels = {(k.firma, k.nummer) for k in lijst}
    return lijst[0] if len(sleutels) == 1 else None

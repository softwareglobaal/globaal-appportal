"""Postbus: de IMAP-laag. Lezen en opruimen, nooit verwijderen of verzenden.

Vier regels die hier hard in de code zitten, niet in een afspraak:

1. **Nooit verwijderen, nooit verzenden.** In dit bestand staat geen EXPUNGE,
   de vlag \\Deleted wordt nergens gezet, en er is geen SMTP: `smtplib` wordt
   niet geimporteerd en er is geen enkele functie die post de deur uit doet.
   Verplaatsen naar een prullenbak- of spammap wordt geweigerd, want dat is
   verwijderen met een omweg: die mappen worden vanzelf leeggemaakt.
2. **Lezen verandert niets.** Ophalen gebeurt altijd met BODY.PEEK en met een
   readonly-select, dus wie alleen leest raakt de leesstatus niet aan. Alleen
   de wijzigfuncties openen een map schrijfbaar, en die staan hieronder apart.
3. **Niets wordt stil afgekapt.** Elke lijst meldt hoeveel er in totaal zijn en
   hoeveel je ziet; een lange berichttekst wordt in genummerde delen gegeven,
   met het totaal erbij. Een preview die zich voordoet als het geheel heeft ons
   al eens weken de verkeerde kant op gestuurd.
4. **Zoeken gebeurt op de server** (IMAP SEARCH), niet door alles binnen te
   halen en hier te filteren.
"""
import email
import html as htmlmod
import imaplib
import re
import threading
import time
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parsedate_to_datetime, parseaddr

TIMEOUT = 30            # seconden per IMAP-verbinding
HERGEBRUIK_S = 120      # een verbinding korter dan dit oud gebruiken we opnieuw
MAX_RESULTATEN = 200    # bovengrens per zoekopdracht
TEKENS_PER_DEEL = 40000  # opdeling van een lange berichttekst

MAANDEN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# Mappen waar niets naartoe verplaatst mag worden. Een bericht in de
# prullenbak of de spammap wordt na verloop van tijd door de provider
# opgeruimd, dus verplaatsen naar zo'n map is verwijderen met uitstel.
VERBODEN_BESTEMMING = ("trash", "prullenbak", "prullenmand", "deleted",
                       "verwijderd", "bin", "junk", "spam", "ongewenst")
# Vlaggen die gezet mogen worden. \Deleted staat hier bewust niet tussen.
VLAGGEN = {"gelezen": "\\Seen", "gemarkeerd": "\\Flagged",
           "beantwoord": "\\Answered"}

_slot = threading.Lock()
_pool = {}   # sleutel -> (verbinding, laatst_gebruikt)


# ---- verbindingen ----------------------------------------------------
class _Sessie:
    """Een IMAP-verbinding die zichzelf na gebruik terugzet in de pool.

    IMAP-objecten zijn niet draadveilig; door de verbinding uit de pool te
    halen en pas na afloop terug te geven, kan er nooit meer dan één
    aanvraag tegelijk op dezelfde verbinding zitten.
    """

    def __init__(self, mailbox):
        self.sleutel = (mailbox["imap_host"], mailbox["imap_poort"],
                        mailbox["gebruiker"])
        self.mailbox = mailbox
        self.M = None

    def __enter__(self):
        with _slot:
            bestaand = _pool.pop(self.sleutel, None)
        if bestaand:
            M, laatst = bestaand
            if time.time() - laatst < HERGEBRUIK_S:
                try:
                    if M.noop()[0] == "OK":
                        self.M = M
                        return M
                except Exception:
                    pass
            try:
                M.logout()
            except Exception:
                pass
        m = self.mailbox
        try:
            M = imaplib.IMAP4_SSL(m["imap_host"], m["imap_poort"],
                                  timeout=TIMEOUT)
        except Exception as e:
            raise ValueError(f"Geen verbinding met {m['imap_host']}:"
                             f"{m['imap_poort']} ({type(e).__name__}: {e})")
        try:
            M.login(m["gebruiker"], m["wachtwoord"])
        except imaplib.IMAP4.error as e:
            try:
                M.logout()
            except Exception:
                pass
            raise ValueError(f"Inloggen op {m['adres']} lukt niet: {e}. "
                             "Controleer gebruiker en wachtwoord in "
                             "mailboxen.yaml.")
        self.M = M
        return M

    def __exit__(self, soort, waarde, sporen):
        if self.M is None:
            return False
        if soort is not None:
            try:
                self.M.logout()
            except Exception:
                pass
            return False
        with _slot:
            _pool[self.sleutel] = (self.M, time.time())
        return False


def _selecteer(M, mapnaam):
    ok, gegevens = M.select(f'"{mapnaam}"', readonly=True)
    if ok != "OK":
        raise ValueError(f"Map '{mapnaam}' kan niet geopend worden: "
                         + _leesbaar(gegevens))
    try:
        return int(gegevens[0])
    except (TypeError, ValueError, IndexError):
        return 0


def _leesbaar(gegevens):
    if isinstance(gegevens, (list, tuple)) and gegevens:
        gegevens = gegevens[0]
    if isinstance(gegevens, bytes):
        return gegevens.decode("utf-8", errors="replace")
    return str(gegevens)


# ---- tekst en koppen -------------------------------------------------
def _kop(waarde):
    """(=?utf-8?...)-koptekst naar leesbare tekst."""
    if not waarde:
        return ""
    try:
        return str(make_header(decode_header(waarde))).strip()
    except Exception:
        return str(waarde).strip()


def _adressen(waarde):
    """Adresregel naar 'Naam <adres>'-lijst, ontdaan van codering."""
    schoon = _kop(waarde)
    if not schoon:
        return []
    delen = [d.strip() for d in re.split(r",(?![^<]*>)", schoon) if d.strip()]
    return delen[:20]


def _html_naar_tekst(ruw):
    tekst = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", ruw)
    tekst = re.sub(r"(?i)<br\s*/?>", "\n", tekst)
    tekst = re.sub(r"(?i)</(p|div|tr|li|h[1-6])>", "\n", tekst)
    tekst = re.sub(r"<[^>]+>", " ", tekst)
    return htmlmod.unescape(tekst)


def _deel_tekst(deel):
    ruw = deel.get_payload(decode=True)
    if ruw is None:
        return ""
    try:
        return ruw.decode(deel.get_content_charset() or "utf-8",
                          errors="replace")
    except (LookupError, UnicodeDecodeError):
        return ruw.decode("utf-8", errors="replace")


def _is_bijlage(deel):
    dispositie = (deel.get("Content-Disposition") or "").lower()
    return "attachment" in dispositie or bool(deel.get_filename())


def _tekst_en_bijlagen(bericht):
    """Leesbare tekst (platte tekst voorkeur, anders HTML) plus bijlagelijst."""
    plat, html_delen, bijlagen = [], [], []
    for deel in bericht.walk():
        if deel.get_content_maintype() == "multipart":
            continue
        if _is_bijlage(deel):
            inhoud = deel.get_payload(decode=True) or b""
            bijlagen.append({
                "naam": _kop(deel.get_filename()) or "(zonder naam)",
                "type": deel.get_content_type(),
                "bytes": len(inhoud),
            })
            continue
        if deel.get_content_maintype() != "text":
            continue
        if deel.get_content_subtype() == "html":
            html_delen.append(_deel_tekst(deel))
        else:
            plat.append(_deel_tekst(deel))
    heel = "\n".join(plat).strip()
    if not heel and html_delen:
        heel = _html_naar_tekst("\n".join(html_delen))
    heel = re.sub(r"[ \t]+", " ", heel)
    heel = re.sub(r"\n{3,}", "\n\n", heel)
    return heel.strip(), bijlagen


# ---- zoeken ----------------------------------------------------------
def _q(waarde):
    """IMAP-string: altijd tussen aanhalingstekens, als utf-8 bytes."""
    schoon = str(waarde).replace("\\", "\\\\").replace('"', '\\"')
    schoon = schoon.replace("\r", " ").replace("\n", " ")
    return ('"' + schoon + '"').encode("utf-8")


def _imap_datum(waarde, veld):
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(waarde).strip())
    if not m:
        raise ValueError(f"{veld} moet een datum JJJJ-MM-DD zijn, niet {waarde!r}")
    jaar, maand, dag = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not 1 <= maand <= 12:
        raise ValueError(f"{veld}: maand {maand} bestaat niet")
    return f"{dag:02d}-{MAANDEN[maand - 1]}-{jaar}"


def _criteria(van, aan, onderwerp, bevat, sinds, tot, ongelezen):
    args = []
    if van:
        args += [b"FROM", _q(van)]
    if aan:
        args += [b"TO", _q(aan)]
    if onderwerp:
        args += [b"SUBJECT", _q(onderwerp)]
    if bevat:
        args += [b"TEXT", _q(bevat)]
    if sinds:
        args += [b"SINCE", _imap_datum(sinds, "sinds").encode()]
    if tot:
        args += [b"BEFORE", _imap_datum(tot, "tot").encode()]
    if ongelezen:
        args += [b"UNSEEN"]
    return args or [b"ALL"]


def zoek_uids(M, args):
    """UID's van de treffers, nieuwste eerst."""
    niet_ascii = any(isinstance(a, bytes) and any(b > 127 for b in a)
                     for a in args)
    pogingen = [(("CHARSET", "UTF-8") + tuple(args)) if niet_ascii
                else tuple(args)]
    if niet_ascii:
        pogingen.append(tuple(args))  # server zonder CHARSET-ondersteuning
    laatste = ""
    for poging in pogingen:
        try:
            ok, gegevens = M.uid("SEARCH", *poging)
        except imaplib.IMAP4.error as e:
            laatste = str(e)
            continue
        if ok == "OK":
            if not gegevens or not gegevens[0]:
                return []
            return sorted((int(u) for u in gegevens[0].split()), reverse=True)
        laatste = _leesbaar(gegevens)
    raise ValueError(f"Zoeken mislukt op de mailserver: {laatste}")


# ---- ophalen ---------------------------------------------------------
_UID = re.compile(rb"UID (\d+)")
_GROOTTE = re.compile(rb"RFC822\.SIZE (\d+)")
_VLAGGEN = re.compile(rb"FLAGS \(([^)]*)\)")


def _fetch_koppen(M, uids):
    """Koppen van een reeks UID's in één FETCH; geeft {uid: (prefix, ruw)}."""
    if not uids:
        return {}
    reeks = ",".join(str(u) for u in uids)
    ok, gegevens = M.uid("FETCH", reeks,
                         "(UID RFC822.SIZE FLAGS BODY.PEEK[HEADER.FIELDS "
                         "(FROM TO CC SUBJECT DATE MESSAGE-ID)])")
    if ok != "OK":
        raise ValueError("Koppen ophalen mislukt: " + _leesbaar(gegevens))
    uit, laatste = {}, None
    for element in gegevens or []:
        if isinstance(element, tuple):
            prefix, ruw = element[0] or b"", element[1] or b""
            m = _UID.search(prefix)
            laatste = int(m.group(1)) if m else None
            if laatste is not None:
                uit[laatste] = [prefix, ruw]
        elif isinstance(element, bytes) and laatste in uit:
            uit[laatste][0] += b" " + element
    return uit


def lijst(mailbox, mapnaam, van=None, aan=None, onderwerp=None, bevat=None,
          sinds=None, tot=None, ongelezen=False, maximaal=25, vanaf=0):
    """Zoekresultaat als koplijst, nieuwste eerst, met eerlijke telling."""
    maximaal = max(1, min(int(maximaal or 25), MAX_RESULTATEN))
    vanaf = max(0, int(vanaf or 0))
    args = _criteria(van, aan, onderwerp, bevat, sinds, tot, ongelezen)
    with _Sessie(mailbox) as M:
        in_map = _selecteer(M, mapnaam)
        uids = zoek_uids(M, args)
        venster = uids[vanaf:vanaf + maximaal]
        rauw = _fetch_koppen(M, venster)

    berichten = []
    for uid in venster:
        gegevens = rauw.get(uid)
        if not gegevens:
            continue
        prefix, ruw = gegevens
        kop = email.message_from_bytes(ruw)
        grootte = _GROOTTE.search(prefix)
        vlaggen = _VLAGGEN.search(prefix)
        vlaggenlijst = (vlaggen.group(1).decode("ascii", "replace").split()
                        if vlaggen else [])
        try:
            datum = parsedate_to_datetime(kop.get("Date"))
            datum = datum.isoformat() if datum else None
        except (TypeError, ValueError):
            datum = None
        naam, adres = parseaddr(_kop(kop.get("From")))
        berichten.append({
            "uid": uid,
            "van": adres.lower(),
            "van_naam": naam,
            "aan": _adressen(kop.get("To")),
            "cc": _adressen(kop.get("Cc")),
            "onderwerp": _kop(kop.get("Subject")),
            "datum": datum,
            "bytes": int(grootte.group(1)) if grootte else None,
            "gelezen": "\\Seen" in vlaggenlijst,
            "message_id": _kop(kop.get("Message-ID")),
        })

    return {
        "mailbox": mailbox["adres"],
        "map": mapnaam,
        "berichten_in_map": in_map,
        "treffers": len(uids),
        "getoond": len(berichten),
        "vanaf": vanaf,
        "meer": len(uids) > vanaf + len(venster),
        "volgende_vanaf": (vanaf + len(venster)
                           if len(uids) > vanaf + len(venster) else None),
        "berichten": berichten,
    }


def bericht(mailbox, mapnaam, uid, deel=1):
    """Eén bericht volledig; lange tekst in genummerde delen, nooit stil gekapt."""
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        raise ValueError(f"uid moet een getal zijn, niet {uid!r}")
    deel = max(1, int(deel or 1))

    with _Sessie(mailbox) as M:
        _selecteer(M, mapnaam)
        ok, gegevens = M.uid("FETCH", str(uid), "(BODY.PEEK[])")
        if ok != "OK":
            raise ValueError("Ophalen mislukt: " + _leesbaar(gegevens))
        ruw = next((el[1] for el in (gegevens or []) if isinstance(el, tuple)),
                   None)
    if not ruw:
        raise ValueError(f"Geen bericht met uid {uid} in {mapnaam}. "
                         "UID's zijn per map; zoek eerst met de tool zoek.")

    bron = email.message_from_bytes(ruw)
    tekst, bijlagen = _tekst_en_bijlagen(bron)
    aantal_delen = max(1, -(-len(tekst) // TEKENS_PER_DEEL))
    if deel > aantal_delen:
        raise ValueError(f"Deel {deel} bestaat niet; dit bericht heeft "
                         f"{aantal_delen} deel(en)")
    stuk = tekst[(deel - 1) * TEKENS_PER_DEEL: deel * TEKENS_PER_DEEL]
    try:
        datum = parsedate_to_datetime(bron.get("Date"))
        datum = datum.isoformat() if datum else None
    except (TypeError, ValueError):
        datum = None
    naam, adres = parseaddr(_kop(bron.get("From")))

    uit = {
        "mailbox": mailbox["adres"],
        "map": mapnaam,
        "uid": uid,
        "van": adres.lower(),
        "van_naam": naam,
        "aan": _adressen(bron.get("To")),
        "cc": _adressen(bron.get("Cc")),
        "antwoord_aan": _kop(bron.get("Reply-To")),
        "onderwerp": _kop(bron.get("Subject")),
        "datum": datum,
        "message_id": _kop(bron.get("Message-ID")),
        "in_antwoord_op": _kop(bron.get("In-Reply-To")),
        "bijlagen": bijlagen,
        "tekens_totaal": len(tekst),
        "deel": deel,
        "aantal_delen": aantal_delen,
        "tekst": stuk,
    }
    if aantal_delen > 1:
        uit["let_op"] = (f"Dit is deel {deel} van {aantal_delen}. Roep dezelfde "
                         f"tool opnieuw aan met deel={deel + 1} voor de rest."
                         if deel < aantal_delen else
                         f"Dit is het laatste deel ({deel} van {aantal_delen}).")
    if bijlagen:
        uit.setdefault("let_op_bijlagen",
                       "Bijlagen worden alleen benoemd, niet ingelezen.")
    return uit


def _lijst_mappen(M):
    """[(attributen, naam)] uit een LIST-antwoord."""
    ok, gegevens = M.list()
    if ok != "OK":
        raise ValueError("Mappenlijst ophalen mislukt: " + _leesbaar(gegevens))
    uit = []
    for regel in gegevens or []:
        if not isinstance(regel, bytes):
            continue
        tekst = regel.decode("utf-8", errors="replace")
        m = re.match(r'\(([^)]*)\) "?[^" ]*"? (.+)$', tekst)
        if not m:
            continue
        naam = m.group(2).strip()
        if naam.startswith('"') and naam.endswith('"'):
            naam = naam[1:-1]
        uit.append(([a.lower() for a in m.group(1).split()], naam))
    return uit


def mappen(mailbox):
    """Alle mappen die deze mailbox heeft, met de toegestane gemarkeerd."""
    with _Sessie(mailbox) as M:
        namen = [naam for _, naam in _lijst_mappen(M)]
    toegestaan = [t.lower() for t in mailbox["mappen"]]
    return {
        "mailbox": mailbox["adres"],
        "alle_mappen": namen,
        "leesbaar": [n for n in namen
                     if not toegestaan or n.lower() in toegestaan],
        "beperkt_tot": mailbox["mappen"] or None,
        "schrijven": bool(mailbox.get("schrijven")),
    }


# ---- wijzigen --------------------------------------------------------
# Alles hieronder verandert iets in de mailbox. Wat er NIET tussen staat is
# net zo belangrijk: geen verwijderen, geen legen, geen verzenden.
def _selecteer_schrijfbaar(M, mapnaam):
    ok, gegevens = M.select(f'"{mapnaam}"', readonly=False)
    if ok != "OK":
        raise ValueError(f"Map '{mapnaam}' kan niet geopend worden om te "
                         "wijzigen: " + _leesbaar(gegevens))


def _bestemming_ok(naam):
    """Weigert prullenbak- en spammappen als doel van een verplaatsing."""
    woorden = set(re.split(r"[^a-z0-9]+", str(naam).lower()))
    gevonden = woorden & set(VERBODEN_BESTEMMING)
    if gevonden:
        raise ValueError(
            f"Verplaatsen naar '{naam}' gaat niet. Die map wordt vanzelf "
            "leeggemaakt, dus dat komt neer op verwijderen, en verwijderen "
            "kan deze koppeling niet. Zet het bericht in een gewone map, of "
            "laat het staan.")


def markeren(mailbox, mapnaam, uid, gelezen=None, gemarkeerd=None,
             beantwoord=None):
    """Zet of haalt de vlaggen gelezen, gemarkeerd en beantwoord."""
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        raise ValueError(f"uid moet een getal zijn, niet {uid!r}")
    gevraagd = {"gelezen": gelezen, "gemarkeerd": gemarkeerd,
                "beantwoord": beantwoord}
    if all(w is None for w in gevraagd.values()):
        raise ValueError("Geef minstens een van gelezen, gemarkeerd of "
                         "beantwoord op (true of false)")

    with _Sessie(mailbox) as M:
        _selecteer_schrijfbaar(M, mapnaam)
        for naam, waarde in gevraagd.items():
            if waarde is None:
                continue
            richting = "+FLAGS" if waarde else "-FLAGS"
            ok, gegevens = M.uid("STORE", str(uid), richting,
                                 f"({VLAGGEN[naam]})")
            if ok != "OK":
                raise ValueError(f"{naam} zetten mislukt: " + _leesbaar(gegevens))
        ok, gegevens = M.uid("FETCH", str(uid), "(FLAGS)")
    vlaggen = []
    for element in gegevens or []:
        ruw = element[0] if isinstance(element, tuple) else element
        m = _VLAGGEN.search(ruw or b"")
        if m:
            vlaggen = m.group(1).decode("ascii", "replace").split()
    return {"mailbox": mailbox["adres"], "map": mapnaam, "uid": uid,
            "gelezen": "\\Seen" in vlaggen,
            "gemarkeerd": "\\Flagged" in vlaggen,
            "beantwoord": "\\Answered" in vlaggen,
            "vlaggen": vlaggen}


def verplaatsen(mailbox, van_map, uid, naar_map):
    """Verplaatst een bericht naar een andere map van dezelfde mailbox."""
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        raise ValueError(f"uid moet een getal zijn, niet {uid!r}")
    _bestemming_ok(naar_map)
    if str(van_map).strip().lower() == str(naar_map).strip().lower():
        raise ValueError("Herkomst en bestemming zijn dezelfde map")

    with _Sessie(mailbox) as M:
        bestaand = [naam.lower() for _, naam in _lijst_mappen(M)]
        if naar_map.lower() not in bestaand:
            raise ValueError(f"Map '{naar_map}' bestaat niet. Maak hem eerst "
                             "aan met de tool map_aanmaken, of kies een "
                             "bestaande map uit de tool mappen.")
        # MOVE (RFC 6851) verplaatst in een keer. Kan de server het niet, dan
        # stoppen we: de klassieke omweg is kopieren, \Deleted zetten en
        # expunge, en die machinerie hoort hier niet thuis.
        kan = [str(c, "ascii", "replace").upper() if isinstance(c, bytes)
               else str(c).upper() for c in (M.capabilities or ())]
        if "MOVE" not in kan:
            raise ValueError("Deze mailserver ondersteunt MOVE niet. "
                             "Verplaatsen zou dan neerkomen op kopieren en "
                             "verwijderen, en verwijderen doet deze "
                             "koppeling niet.")
        _selecteer_schrijfbaar(M, van_map)
        ok, gegevens = M.uid("MOVE", str(uid), f'"{naar_map}"')
        if ok != "OK":
            raise ValueError("Verplaatsen mislukt: " + _leesbaar(gegevens))
    return {"mailbox": mailbox["adres"], "uid": uid, "van": van_map,
            "naar": naar_map, "verplaatst": True,
            "let_op": "Het bericht staat nu in de doelmap; het uid verandert "
                      "daarbij. Zoek opnieuw in de doelmap om het terug te "
                      "vinden."}


def map_aanmaken(mailbox, naam):
    """Maakt een map aan en abonneert erop, zodat hij in de webmail verschijnt."""
    with _Sessie(mailbox) as M:
        bestaand = [n.lower() for _, n in _lijst_mappen(M)]
        if naam.lower() in bestaand:
            return {"mailbox": mailbox["adres"], "map": naam,
                    "aangemaakt": False, "melding": "Bestond al"}
        ok, gegevens = M.create(f'"{naam}"')
        if ok != "OK":
            raise ValueError(f"Map '{naam}' aanmaken mislukt: "
                             + _leesbaar(gegevens))
        M.subscribe(f'"{naam}"')
    return {"mailbox": mailbox["adres"], "map": naam, "aangemaakt": True,
            "let_op": "Mapnamen zijn hier hierarchisch met een punt, "
                      "bijvoorbeeld INBOX.Projecten.2026."}


def _conceptenmap(M):
    """De map voor concepten: eerst op de \\Drafts-eigenschap, dan op naam."""
    lijst = _lijst_mappen(M)
    for attrs, naam in lijst:
        if "\\drafts" in attrs:
            return naam
    for _, naam in lijst:
        kaal = naam.lower().rsplit(".", 1)[-1]
        if kaal in ("drafts", "concepten", "concept", "kladversies"):
            return naam
    raise ValueError("Geen conceptenmap gevonden in deze mailbox. Maak er een "
                     "aan (bijvoorbeeld INBOX.Drafts) met de tool map_aanmaken.")


def concept_opslaan(mailbox, aan, onderwerp, tekst, cc=None, antwoord_op=None,
                    van_map="INBOX"):
    """Legt een concept in de conceptenmap. Verstuurt niets.

    Met antwoord_op (een uid) worden de kopvelden van een antwoord ingevuld:
    ontvanger, onderwerp met Re: en de verwijzing naar het oorspronkelijke
    bericht, zodat het in de webmail als antwoord in de conversatie hangt.
    """
    bericht = EmailMessage()
    ontvangers = [a.strip() for a in str(aan or "").split(",") if a.strip()]
    kopie = [c.strip() for c in str(cc or "").split(",") if c.strip()]
    verwijzing = None

    with _Sessie(mailbox) as M:
        if antwoord_op is not None:
            _selecteer(M, van_map)
            ok, gegevens = M.uid(
                "FETCH", str(int(antwoord_op)),
                "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT MESSAGE-ID REFERENCES "
                "REPLY-TO)])")
            ruw = next((el[1] for el in (gegevens or [])
                        if isinstance(el, tuple)), None)
            if not ruw:
                raise ValueError(f"Geen bericht met uid {antwoord_op} in "
                                 f"{van_map} om op te antwoorden")
            bron = email.message_from_bytes(ruw)
            verwijzing = _kop(bron.get("Message-ID"))
            if not ontvangers:
                antwoord_naar = (_kop(bron.get("Reply-To"))
                                 or _kop(bron.get("From")))
                ontvangers = [antwoord_naar] if antwoord_naar else []
            if not onderwerp:
                oud = _kop(bron.get("Subject"))
                onderwerp = oud if oud.lower().startswith("re:") else "Re: " + oud
            if verwijzing:
                eerder = _kop(bron.get("References"))
                bericht["In-Reply-To"] = verwijzing
                bericht["References"] = (eerder + " " + verwijzing).strip()

        if not ontvangers:
            raise ValueError("Geef een ontvanger op in 'aan', of een uid in "
                             "'antwoord_op' zodat de afzender daarvan wordt "
                             "overgenomen")

        bericht["From"] = mailbox["adres"]
        bericht["To"] = ", ".join(ontvangers)
        if kopie:
            bericht["Cc"] = ", ".join(kopie)
        bericht["Subject"] = onderwerp or "(geen onderwerp)"
        bericht["Date"] = formatdate(localtime=True)
        bericht["Message-ID"] = make_msgid()
        bericht.set_content(str(tekst or ""))

        doelmap = _conceptenmap(M)
        ok, gegevens = M.append(f'"{doelmap}"', "(\\Draft)",
                                imaplib.Time2Internaldate(time.time()),
                                bericht.as_bytes())
        if ok != "OK":
            raise ValueError("Concept opslaan mislukt: " + _leesbaar(gegevens))

    return {"mailbox": mailbox["adres"], "map": doelmap, "opgeslagen": True,
            "aan": ontvangers, "cc": kopie,
            "onderwerp": bericht["Subject"],
            "antwoord_op": verwijzing,
            "let_op": "Dit is een concept. Er is niets verstuurd en deze "
                      "koppeling kan ook niet versturen: open het in de "
                      "webmail, lees het na en verstuur het zelf."}

"""Postbus: de IMAP-laag. Uitsluitend lezen.

Drie regels die hier hard in de code zitten, niet in een afspraak:

1. **Alleen lezen.** Elke SELECT gebeurt met readonly=True en elke FETCH met
   BODY.PEEK, dus de leesstatus in de webmail blijft onaangeroerd. Er zit geen
   STORE, EXPUNGE, APPEND of COPY in dit bestand, en geen SMTP.
2. **Niets wordt stil afgekapt.** Elke lijst meldt hoeveel er in totaal zijn en
   hoeveel je ziet; een lange berichttekst wordt in genummerde delen gegeven,
   met het totaal erbij. Een preview die zich voordoet als het geheel heeft ons
   al eens weken de verkeerde kant op gestuurd.
3. **Zoeken gebeurt op de server** (IMAP SEARCH), niet door alles binnen te
   halen en hier te filteren.
"""
import email
import html as htmlmod
import imaplib
import re
import threading
import time
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime, parseaddr

TIMEOUT = 30            # seconden per IMAP-verbinding
HERGEBRUIK_S = 120      # een verbinding korter dan dit oud gebruiken we opnieuw
MAX_RESULTATEN = 200    # bovengrens per zoekopdracht
TEKENS_PER_DEEL = 40000  # opdeling van een lange berichttekst

MAANDEN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

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


def mappen(mailbox):
    """Alle mappen die deze mailbox heeft, met de toegestane gemarkeerd."""
    with _Sessie(mailbox) as M:
        ok, gegevens = M.list()
        if ok != "OK":
            raise ValueError("Mappenlijst ophalen mislukt: " + _leesbaar(gegevens))
        namen = []
        for regel in gegevens or []:
            if not isinstance(regel, bytes):
                continue
            tekst = regel.decode("utf-8", errors="replace")
            m = re.match(r'\([^)]*\) "?[^" ]*"? (.+)$', tekst)
            if not m:
                continue
            naam = m.group(1).strip()
            if naam.startswith('"') and naam.endswith('"'):
                naam = naam[1:-1]
            namen.append(naam)
    toegestaan = [t.lower() for t in mailbox["mappen"]]
    return {
        "mailbox": mailbox["adres"],
        "alle_mappen": namen,
        "leesbaar": [n for n in namen
                     if not toegestaan or n.lower() in toegestaan],
        "beperkt_tot": mailbox["mappen"] or None,
    }

"""Gedeelde mailwacht op de VM: een of meer postvakken lezen, trieren en opvolgen.

Mandaat van Mehdi, 25-09-2026: "voor de e-mailadressen beheert momenteel niemand dit.
Aparte agents, vooral mch@, info@ H-Architects, Melodie en info@ H-Invest, zodat elke
agent apart kan toezien en de belangrijke e-mails kan opvolgen, zodat het niet allemaal
bij mij komt en ik niet alles moet onthouden. Geen spam, geen rommelinformatie."

Een mailwacht per postvak (of per firma), allemaal met deze ene module, zodat de regels
niet uit elkaar lopen. Welke wacht welke postvakken leest, staat in
werkwijze/mailwachten.json. De wachten melden niet elk bericht aan Mehdi: wat opvolging
vraagt, zetten ze klaar voor De Mailregisseur, die bundelt en doorgeeft aan De Regisseur.

Lezen gaat via de postbus (post/imapbron.py): alleen koppen, readonly-select en
BODY.PEEK, dus niets wordt als gelezen gemarkeerd, niets verplaatst, niets verstuurd.
De wachtwoorden blijven in ~/post-config/mailboxen.yaml; deze module leest ze daar en
schrijft ze nergens heen.

De soorten, van stil naar luid:
  verdacht  lijkt phishing (bank of overheid vanaf een gratis adres): alleen geteld
  rommel    reclame, nieuwsbrief, afmeldbevestiging: alleen geteld
  koud      een mens die we niet kennen, zonder aanvraag (koude verkoop): alleen geteld
  melding   automatisch bericht zonder gevolg (pakje, bestelling): alleen geteld
  actie     automatisch bericht met gevolg (betaling mislukt, e-Box): zeven dagen op de lijst
  midden    een bekend contact, een lopend gesprek of een aanvraag: opvolgen na twee werkdagen
  hoog      een mens met een rol of woord met gevolg (bank, overheid, aanmaning): meteen opvolgen
"""
import email
import json
import os
import re
import sys
from datetime import datetime, timedelta
from email.utils import parseaddr
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
POST = os.path.join(os.path.dirname(RUNNER), "post")
os.environ.setdefault("POSTBUS_CONFIG", os.path.expanduser("~/post-config/mailboxen.yaml"))
BRUSSEL = ZoneInfo("Europe/Brussels")
WACHTEN = os.path.join(RUNNER, "werkwijze", "mailwachten.json")

OPVOLGEN_NA_WERKDAGEN = 2   # een gewoon bericht zonder antwoord wordt na zoveel werkdagen een opvolgpunt
TERUG_DAGEN = 30            # zover kijken we terug: naar berichten die op antwoord wachten, en voor de cijfers
ACTIE_DAGEN = 7             # zolang blijft een automatisch bericht met gevolg op de lijst
BEKEND_DAGEN = 180          # wie we in deze periode mailden, is een bekend contact

# Rollen en woorden, overgenomen van de Mac-mailwacht (mac/mail_wacht.py), uitgebreid met
# wat op 25-09-2026 in info@ H-Architects en info@ H-Invest binnenkwam.
ROLLEN = {
    "boekhouder": ["octopus", "boekhoud", "accountant", "fiscal", "liantis", "din consulting"],
    # "@ing.be" en ".ing.be", niet "ing.be": dat laatste zit ook in valoprojectontwikkeling.be (gezien 25-09-2026)
    "bank": ["kbc", "belfius", "bnp", "@ing.be", ".ing.be", "argenta", "crelan", "alpha credit", "alphacredit"],
    "overheid": ["belgium.be", "vlaanderen.be", "minfin", "fod", "rsz", "onss", "socialsecurity", "gemeente", "stad.",
                 "omgevingsloket", "vlabel", "belastingdienst", "architect.be", "orde van architecten"],
    "notaris": ["notaris"], "advocaat": ["advoca", "law firm", "lawfirm", "legaloffice", "@law", ".law"], "deurwaarder": ["deurwaarder", "gerechtsdeurwaarder"],
    "verzekering": ["verzeker", "insurance", "ethias", "axa", "@ag.be", ".ag.be", "baloise", "arcoinsurance"],
}
HOOG_ROLLEN = {"boekhouder", "bank", "overheid", "notaris", "advocaat", "deurwaarder", "verzekering"}
# "herinnering" telt niet in "herinneringen" (25-09-2026: "75 jaar Oase ... mooie herinneringen"); zie _woord.
HOOG = ["factuur", "betaling", "betalen", "betalingsuitnodiging", "herinnering", "aanmaning", "achterstal", "overschrijding", "deadline", "uiterlijk",
        "dringend", "urgent", "ingebrekestelling", "vervaldag", "vervalt", "verloopt", "contract", "vergunning",
        "belasting", "aanslag", "schorsing", "opzeg", "openstaande", "bijdragenota", "action needed", "action required",
        "payment", "overdue", "deactivated", "suspended", "paused", "mislukt", "failed", "e-box"]
AANVRAAG = ["offerteaanvraag", "offerte aanvraag", "aanvraag voor", "prijsaanvraag", "bouwaanvraag", "renovatie",
            "verbouwing", "nieuwbouw", "stedenbouw", "omgevingsvergunning", "epb", "werf ", "plaatsbezoek"]
ROMMEL = ["nieuwsbrief", "newsletter", "unsubscribe", "uitschrijven", "afgemeld", "aanbieding", "korting", "promo",
          "webinar", "masterclass", "gratis", "free publication", "offres", "points", "word dealer", "ontdek", "visit",
          "stand at", "proposition", "partenariat", "infogids", "mening wordt gevraagd", "posted a story", "win ",
          "interessante projecten", "sparren", "apart gehouden", "stellen u met veel plezier", "aanbestedingen voor",
          "verkiezingen", "benchmarking"]
ROMMEL_DOMEINEN = ["klaviyomail", "mailjet", "emlmkt", "smile.io", "sendgrid", "mailchimp", "mcsv.net", "hubspot",
                   "newsletter", "nieuws.", "beemailing", "customer-mail", "-mkt.", "facebookmail"]
MELDING_AFZENDERS = ["noreply", "no-reply", "donotreply", "robot@", "notification", "notificatie", "alerts",
                     "mailer-daemon", "postmaster", "bpost", "dpdgroup", "postnl", "shopify", "zendesk", "sales@one.com",
                     "statement", "billing@", "invoice@", "facturatie@"]
MELDING_ONDERWERPEN = ["order overview", "order is being processed", "bestelling", "verzending", "pakje", "pakket",
                       "statement", "welcome to", "password", "wachtwoord", "import rapport", "uitgavenstaat"]
# Automatische antwoorden. Vooraan in het onderwerp: afwezigheid. Overal: ontvangstbevestigingen van een loket.
AUTO_BEGIN = re.compile(r"^\s*(automatisch antwoord|automatic reply|auto(matic)?[- ]?reply|out of office|afwezig|absence|"
                        r"r[ée]ponse automatique|automatische antwort)", re.I)
AUTO_OVERAL = re.compile(r"(bedankt voor uw e-?mail|ontvangstbevestiging|accus[ée] de r[ée]ception|"
                         r"we hebben je vraag goed ontvangen|we have received your)", re.I)
# Een herinnering aan een afspraak (kinesist, garage) is een melding, geen betalingsherinnering.
AFSPRAAK = re.compile(r"((herinnering|reminder)\W+(uw |je |your )?(afspraak|appointment)|afspraakherinnering|"
                      r"appointment reminder)", re.I)
# Een bericht van de mailserver gaat over onze eigen verzonden mail; het onderwerp is dat van onze mail.
MAILSERVER = ("postmaster@", "mailer-daemon@")
NIET_BEZORGD = re.compile(r"(undeliver|niet (be)?bezorgd|onbestelbaar|delivery (status notification \()?fail|returned mail)", re.I)
# Een afzender die zich voordoet als bank of overheid vanaf een gratis mailadres is verdacht:
# nooit doorgeven als belangrijk, wel tellen. Gezien 25-09-2026: "My MINFIN" van een gmail-adres.
GRATIS = ("gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "live.com", "icloud.com")
VERDACHTE_NAMEN = ["minfin", "fod financi", "belastingdienst", "kbc", "belfius", "ing ", "itsme", "politie", "bpost"]
GESPREK = re.compile(r"^\s*(re|antw|aw|sv|fw|fwd|tr)\s*:", re.I)


def wachten():
    """De configuratie van alle mailwachten: {naam: {postvakken, antwoord_vanuit, firma, ...}}."""
    with open(WACHTEN, encoding="utf-8") as f:
        return json.load(f)


VERZONDEN = ("INBOX.Sent", "INBOX.Sent Messages", "INBOX.Sent Items", "Sent", "[Gmail]/Verzonden berichten", "[Gmail]/Sent Mail")
DATA = os.path.expanduser("~/appportal/mijnagents-data")
BRON_VERS_UREN = 3          # een kopie van de Mac die ouder is dan dit, meld ik als niet vers


def mappen_van(adres):
    """De mappen die van dit postvak gelezen worden; standaard alleen INBOX (zie mailwachten.json, 'mappen')."""
    try:
        return wachten().get("mappen", {}).get(adres) or ["INBOX"]
    except (OSError, ValueError):
        return ["INBOX"]


def koppen_mappen(adres, mappen, sinds, ag=None, plafond=1000):
    """Koppen uit meerdere mappen; een map die niet bestaat of niet leesbaar is, wordt overgeslagen en gelogd."""
    uit, gelukt = [], 0
    for m in mappen:
        try:
            uit += [dict(b, map_=m) for b in koppen(adres, m, sinds=sinds, plafond=plafond)]
            gelukt += 1
        except Exception as e:  # noqa: BLE001
            if ag:
                ag.log("mappen", "bron", f"{adres} {m} niet leesbaar: {type(e).__name__}")
    if not gelukt:
        raise LookupError(f"geen enkele map van {adres} leesbaar")
    return uit


def _postbus():
    if POST not in sys.path:
        sys.path.insert(0, POST)
    import config  # noqa: E402  (post/config.py)
    import imapbron  # noqa: E402  (post/imapbron.py)
    return config, imapbron


def postvak(adres):
    """Het postvak uit de postbus, met zijn gegevens; None als het er niet in staat.
    Een postvak dat de server niet zelf kan lezen (mailwachten.json, 'bronnen') komt uit een bestand
    dat de Mac aanlevert: dan {'adres', 'bron'}."""
    try:
        bron = wachten().get("bronnen", {}).get(adres.lower())
    except (OSError, ValueError):
        bron = None
    if bron:
        return {"adres": adres, "bron": os.path.join(DATA, bron)}
    config, _ = _postbus()
    mailboxen, _fouten = config.alles()
    return next((m for m in mailboxen if m["adres"].lower() == adres.lower()), None)


def uit_bestand(pad, mapnaam, sinds=None):
    """Koppen uit een bestand van de Mac (mac/hotmail_koppen.py), zelfde vorm als imapbron.lijst, nieuwste eerst."""
    with open(pad, encoding="utf-8") as f:
        d = json.load(f)
    uit = [b for b in d.get("berichten", []) if b.get("map") == mapnaam and (not sinds or (b.get("datum") or "")[:10] >= sinds)]
    return sorted(uit, key=lambda b: b.get("datum") or "", reverse=True)


def bron_uren_oud(mb, nu=None):
    """Hoe oud de kopie van de Mac is, in uren; None als het geen bestand is of het niet leesbaar is."""
    if not mb or not mb.get("bron"):
        return None
    try:
        with open(mb["bron"], encoding="utf-8") as f:
            gemaakt = datetime.fromisoformat(json.load(f)["gemaakt"])
    except (OSError, ValueError, KeyError):
        return None
    return ((nu or datetime.now(BRUSSEL)) - gemaakt).total_seconds() / 3600


def koppen(adres, mapnaam="INBOX", sinds=None, maximaal=200, plafond=1000):
    """Koppen van een postvak via de postbus (of het bestand van de Mac): alleen lezen, nieuwste eerst."""
    mb = postvak(adres)
    if not mb:
        raise LookupError(f"{adres} staat niet in de postbus")
    if mb.get("bron"):
        return uit_bestand(mb["bron"], mapnaam, sinds)[:plafond]
    _, imapbron = _postbus()
    uit, vanaf = [], 0
    while True:
        r = imapbron.lijst(mb, mapnaam, sinds=sinds, maximaal=maximaal, vanaf=vanaf)
        uit += r["berichten"]
        if not r["meer"] or len(uit) >= plafond:
            return uit
        vanaf = r["volgende_vanaf"]


def _domein(adres):
    return adres.rsplit("@", 1)[-1].lower() if "@" in adres else ""


def schoon(tekst):
    """Een onderwerp op een regel: IMAP vouwt lange koppen over meerdere regels."""
    return re.sub(r"\s+", " ", tekst or "").strip()


def _adres(veld):
    m = re.search(r"[\w.+'-]+@[\w-]+(\.[\w-]+)+", veld or "")
    return m.group(0).lower() if m else ""


def _woord(o):
    """Het eerste woord met gevolg in dit onderwerp (kleine letters), of ''."""
    o = o.replace("no action required", "")  # "[No Action Required:]" van Claude Team, gezien 25-09-2026
    for w in HOOG:
        if w == "herinnering":
            if re.search(r"herinnering(?!en)", o):
                return w
        elif w in o:
            return w
    return ""


def automatisch_antwoord(onderwerp):
    o = schoon(onderwerp)
    return bool(AUTO_BEGIN.match(o) or AUTO_OVERAL.search(o))


def regel_voor(regels, postvak_adres, van):
    """De beslissing van Mehdi over deze afzender (op het maildashboard): 'belangrijk', 'ruis' of 'opruimen',
    of ''. Een regel op het adres gaat voor een regel op het domein (@domein); een regel voor dit postvak
    gaat voor een regel voor alle postvakken (*)."""
    van = (van or "").lower()
    for pv in ((postvak_adres or "").lower(), "*"):
        for wie in (van, "@" + _domein(van)):
            actie = (regels or {}).get((pv, wie))
            if actie:
                return actie
    return ""


def trieer(b, eigen_domeinen=(), bekend=frozenset(), regel=""):
    """(soort, waarom) voor een kop uit imapbron.lijst; zie de lijst bovenaan dit bestand.
    Een bron mag zelf zeggen dat een bericht automatisch is ('automatisch', zoals Mail op de Mac dat bijhoudt)
    of van een mailinglijst komt ('lijst'). `regel` is wat Mehdi over deze afzender besliste (regel_voor)."""
    van, naam, ond = (b.get("van") or "").lower(), (b.get("van_naam") or "").lower(), schoon(b.get("onderwerp"))
    o = ond.lower()
    dom = _domein(van)
    if dom.endswith(GRATIS) and any(v in naam for v in VERDACHTE_NAMEN):
        return "verdacht", f"'{b.get('van_naam')}' vanaf een gratis adres ({dom})"
    if regel == "belangrijk":
        return "hoog", "Mehdi zette deze afzender op belangrijk"
    if regel in ("ruis", "opruimen"):
        return "rommel", "Mehdi zette deze afzender op ruis"
    if automatisch_antwoord(ond):
        return "melding", "automatisch antwoord of ontvangstbevestiging"
    if van.startswith(MAILSERVER) or naam in ("postmaster", "mail delivery subsystem", "mail delivery system"):
        return (("actie", "onze mail kwam niet aan") if NIET_BEZORGD.search(o)
                else ("melding", "bericht van de mailserver over onze eigen mail"))
    if AFSPRAAK.search(o):
        return "melding", "herinnering aan een afspraak"
    rol = next((r for r, delen in ROLLEN.items() if any(d in f"{van} {naam} {o}" for d in delen)), "")
    woord = _woord(o)
    automatisch = (bool(b.get("automatisch")) or any(a in van or a in naam for a in MELDING_AFZENDERS)
                   or any(m in o for m in MELDING_ONDERWERPEN))
    reclame = any(d in van for d in ROMMEL_DOMEINEN) or any(w in o for w in ROMMEL)
    if reclame and not woord:
        return "rommel", "reclame, nieuwsbrief of afmelding"
    if b.get("lijst") and rol not in HOOG_ROLLEN and not woord:
        return "melding", "mailinglijst of nieuwsbrief"
    if automatisch:
        return ("actie", f"automatisch, woord '{woord}'") if woord else ("melding", "automatisch bericht")
    if rol in HOOG_ROLLEN or woord:
        return "hoog", ", ".join(x for x in (f"rol {rol}" if rol else "", f"woord '{woord}'" if woord else "") if x)
    if dom in eigen_domeinen:
        return "midden", "collega uit de groep"
    kent = van in bekend or dom in {_domein(a) for a in bekend if not _domein(a).endswith(GRATIS)}
    aanvraag = next((w for w in AANVRAAG if w in o), "")
    if kent or GESPREK.match(ond) or aanvraag:
        return "midden", "bekend contact" if kent else ("lopend gesprek" if GESPREK.match(ond) else f"aanvraag ('{aanvraag}')")
    return "koud", "onbekende afzender zonder aanvraag"


def werkdagen_tussen(van, tot):
    """Aantal werkdagen (ma-vr) na de dag van `van`, tot en met de dag van `tot`."""
    d, n = van.date(), 0
    while d < tot.date():
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def _datum(b):
    try:
        return datetime.fromisoformat(b["datum"]).astimezone(BRUSSEL)
    except (KeyError, TypeError, ValueError):
        return None


def beantwoord(van_adres, na, verzonden, afwezig=None):
    """Is er na dit moment iets verstuurd naar deze afzender, vanuit een van de postvakken van de firma?
    Een afwezigheidsbericht van die afzender na dit moment telt ook: dan heeft iemand hem gemaild,
    misschien vanuit een postvak dat ik niet lees (gezien 23-09-2026 bij KBC Verzekeringen)."""
    if afwezig and any(d >= na for d in afwezig.get(van_adres, [])):
        return True
    for s in verzonden:
        d = _datum(s)
        if d and d >= na and any(van_adres == _adres(a) for a in (s.get("aan") or []) + (s.get("cc") or [])):
            return True
    return False


def ronde(naam, ag, r, nu=None, regels=None):
    """Een ronde van mailwacht `naam`. `ag` is de bord.Agent (of iets met log), `r` de lopende Ronde.
    Geeft (items voor de Mailregisseur, telling, rijen voor de gesprekkentabel, alle beoordeelde berichten
    voor het maildashboard)."""
    nu = nu or datetime.now(BRUSSEL)
    cfg = wachten()[naam]
    r.bron("mailwachten.json", json.dumps(cfg, ensure_ascii=False, sort_keys=True))
    eigen = tuple(cfg.get("eigen_domeinen") or ())
    sinds = (nu - timedelta(days=TERUG_DAGEN)).date().isoformat()
    tel = {s: 0 for s in ("hoog", "midden", "actie", "melding", "koud", "rommel", "verdacht")}
    tel["open"] = 0
    verzonden = []
    for adres in dict.fromkeys(cfg.get("antwoord_vanuit", []) + cfg["postvakken"]):
        mb = postvak(adres)
        if not mb:
            continue
        for m in VERZONDEN:
            if mb.get("mappen") and m not in mb["mappen"]:
                continue
            try:
                verzonden += koppen(adres, m, sinds=(nu - timedelta(days=BEKEND_DAGEN)).date().isoformat(), plafond=1500)
            except Exception:  # noqa: BLE001
                pass  # niet elk postvak heeft elke variant van Verzonden
    bekend = frozenset(_adres(a) for s in verzonden for a in (s.get("aan") or []) + (s.get("cc") or []) if _adres(a))
    tel["verzonden_gelezen"], tel["bekende_contacten"] = len(verzonden), len(bekend)
    items, rijen, alle = [], [], []
    for adres in cfg["postvakken"]:
        mb = postvak(adres)
        if not mb:
            r.nood(f"{adres} staat niet in de postbus: de wacht kan het niet lezen", wie="claude-code")
            continue
        oud = bron_uren_oud(mb, nu)
        if mb.get("bron") and (oud is None or oud > BRON_VERS_UREN):
            r.nood(f"De kopie van {adres} van de Mac is niet vers: de Mac slaapt, of Mail staat uit", wie="mehdi")
        try:
            berichten = koppen_mappen(adres, mappen_van(adres), sinds, ag)
        except Exception as e:  # noqa: BLE001
            r.nood(f"{adres} niet leesbaar via de postbus", wie="claude-code")
            ag.log("inbox", "bron", f"{adres}: {type(e).__name__}: {str(e)[:120]}")
            continue
        # Wat het postvak zelf verstuurde, is geen opvolgpunt (Gmail 'Alle e-mail' bevat ook de verzonden post).
        berichten = [b for b in berichten if (b.get("van") or "").lower() != adres.lower()]
        afwezig = {}
        for b in berichten:
            if automatisch_antwoord(b.get("onderwerp")) and _datum(b):
                afwezig.setdefault(b.get("van", ""), []).append(_datum(b))
        for b in berichten:
            d = _datum(b)
            if not d:
                continue
            soort, waarom = trieer(b, eigen, bekend, regel_voor(regels, adres, b.get("van")))
            ond = schoon(b.get("onderwerp"))
            antw = (soort in ("hoog", "midden") and _domein(b.get("van", "")) not in eigen
                    and beantwoord(b.get("van", ""), d, verzonden, afwezig))
            alle.append({"uniek": f"{adres}:{(b.get('message_id') or b.get('uid'))}"[:250], "wacht": naam, "postvak": adres,
                         "map": b.get("map_") or "", "datum": d.isoformat(), "van": (b.get("van") or "").lower(),
                         "van_naam": (b.get("van_naam") or "")[:120], "onderwerp": ond[:300], "soort": soort,
                         "waarom": kort_waarom(waarom), "lijst": 1 if b.get("lijst") else 0, "beantwoord": 1 if antw else 0})
            if d >= nu - timedelta(days=1):
                tel[soort] += 1
                if soort in ("hoog", "midden", "actie"):
                    rijen.append({"uniek": f"mail:{(b.get('message_id') or f'{adres}:{b['uid']}')[:150]}",
                                  "datum": d.strftime("%Y-%m-%d"), "start": d.strftime("%H:%M"), "minuten": 0,
                                  "personen": (b.get("van_naam") or b.get("van") or "")[:80], "bedrijf": _domein(b.get("van", "")),
                                  "afdeling": cfg.get("afdeling", ""), "thema": ond[:90], "project": "", "prive": 0,
                                  "zekerheid": "middel", "waarom": f"{soort}; {waarom}", "archief": "", "link": "",
                                  "opgenomen_door": adres, "bron": "mail"})
            wacht = werkdagen_tussen(d, nu)
            if soort == "actie":
                if d < nu - timedelta(days=ACTIE_DAGEN):
                    continue
            elif soort == "hoog":
                if _domein(b.get("van", "")) in eigen or beantwoord(b.get("van", ""), d, verzonden, afwezig):
                    continue
            elif soort == "midden":
                if (wacht < OPVOLGEN_NA_WERKDAGEN or _domein(b.get("van", "")) in eigen
                        or beantwoord(b.get("van", ""), d, verzonden, afwezig)):
                    continue
            else:
                continue
            tel["open"] += 1
            mid = (b.get("message_id") or f"{adres}:{b['uid']}")[:150]
            items.append({"voor": "mail-regisseur", "soort": "mail", "sleutel": cfg.get("firma", ""),
                          "titel": f"{cfg.get('firma', '')}: {(b.get('van_naam') or b.get('van') or '').strip()[:40]} · {ond[:80]}",
                          "uniek": f"opvolgen:{naam}:{mid}",
                          "inhoud": {"postvak": adres, "van": b.get("van"), "van_naam": b.get("van_naam"), "onderwerp": ond,
                                     "datum": d.isoformat(), "uid": b.get("uid"), "soort": soort, "waarom": waarom,
                                     "werkdagen_zonder_antwoord": wacht,
                                     "voorstel": {"actie": "nakijken en regelen (automatisch bericht, geen antwoord mogelijk)",
                                                  "hoog": "beantwoorden of regelen",  # het waarom staat er al naast
                                                  "midden": "beantwoorden of doorzetten naar wie het opvolgt"}[soort]}})
    return items, tel, rijen, alle


def kort_waarom(w):
    return (w or "")[:200]


class _Droog:
    """Een ronde die niets naar het bord schrijft: voor een proef op de VM."""

    def __init__(self):
        self.noden, self.detail = [], ""

    def bron(self, naam, inhoud):
        pass

    def nood(self, tekst, wie="mehdi"):
        self.noden.append((tekst, wie))


class _DroogAgent:
    def log(self, *a):
        print("  [log]", " | ".join(str(x)[:160] for x in a[:3]))


def afsluiten(naam, items, bord, ag, nu):
    """Wat ik vorige keer klaarzette en nu niet meer meld, is beantwoord of afgelopen: dan haal ik
    het van de lijst van de Mailregisseur. Een bericht ouder dan mijn venster laat ik staan, want
    daarvan weet ik niet of het beantwoord is; wat blijft staan, wordt niet vergeten."""
    nu_uniek = {it["uniek"] for it in items}
    grens = (nu - timedelta(days=TERUG_DAGEN - 1)).isoformat()
    n = 0
    for it in bord.klaargezet_voor("mail-regisseur", n=500):
        if it.get("van") != naam or it.get("uniek") in nu_uniek:
            continue
        try:
            datum = json.loads(it.get("inhoud") or "{}").get("datum", "")
        except ValueError:
            datum = ""
        if datum and datum >= grens:
            bord.opgepakt(it["id"], f"{naam}: beantwoord of afgelopen")
            n += 1
    if n:
        ag.log("opvolgen", "schrijf", f"{n} opvolgpunten beantwoord of afgelopen, van de lijst gehaald")
    return n


def droog(naam):
    """Alleen lezen en tonen wat er klaargezet zou worden, niets naar het bord."""
    nu = datetime.now(BRUSSEL)
    r = _Droog()
    items, tel, _, _ = ronde(naam, _DroogAgent(), r, nu)
    print(json.dumps(tel, ensure_ascii=False))
    for it in items:
        i = it["inhoud"]
        print(f"  opvolgen: {i['datum'][:10]} ({i['werkdagen_zonder_antwoord']} wd) {i['soort']:6} {it['titel'][:105]}  [{i['waarom']}]")
    for t, w in r.noden:
        print(f"  nood ({w}): {t}")
    return items, tel


def opruimmap(mb):
    """De map voor wat Mehdi liet opruimen: one.com gebruikt een punt als scheiding, Gmail een label."""
    return "Opgeruimd" if "gmail" in (mb.get("imap_host") or "") else "INBOX.Opgeruimd"


def past(van, wie):
    """Past dit afzenderadres bij een regel op een adres of op @domein (ook een subdomein)?"""
    van, wie = (van or "").lower(), (wie or "").lower()
    if wie.startswith("@"):
        dom = _domein(van)
        return dom == wie[1:] or dom.endswith("." + wie[1:])
    return van == wie


def opruimen(mb, wie):
    """Verplaatst alle post van `wie` (adres of @domein) uit de INBOX naar de map Opgeruimd, op beslissing van
    Mehdi. Alleen als de postbus dit postvak laat schrijven (mailboxen.yaml, 'schrijven'). Niets wordt verwijderd:
    de map staat gewoon in de webmail. Geeft de Message-ID's (of uid's) van wat verplaatst werd."""
    if not mb or mb.get("bron") or not mb.get("schrijven"):
        return []
    _, imapbron = _postbus()
    doel = opruimmap(mb)
    with imapbron._Sessie(mb) as M:
        if doel.lower() not in [n.lower() for _, n in imapbron._lijst_mappen(M)]:
            M.create(f'"{doel}"')
            M.subscribe(f'"{doel}"')
        if "MOVE" not in imapbron.capabilities(M):
            raise ValueError("deze mailserver kan niet verplaatsen (geen MOVE)")
        imapbron._selecteer_schrijfbaar(M, "INBOX")
        uids = imapbron.zoek_uids(M, [b"FROM", imapbron._q(wie.lstrip("@"))])[:500]
        # IMAP zoekt op een deel van het adres; ik controleer het echte adres voor ik iets verplaats.
        weg = []
        for uid, (_prefix, ruw) in imapbron._fetch_koppen(M, uids).items():
            kop = email.message_from_bytes(ruw)
            if past(parseaddr(imapbron._kop(kop.get("From")))[1], wie):
                weg.append((uid, imapbron._kop(kop.get("Message-ID")) or str(uid)))
        if weg:
            ok, gegevens = M.uid("MOVE", ",".join(str(u) for u, _ in weg), f'"{doel}"')
            if ok != "OK":
                raise ValueError("verplaatsen mislukt: " + imapbron._leesbaar(gegevens))
    return [mid for _, mid in weg]


def aan_de_beurt(nu=None):
    """Cadans van de mailwachten: elk uur tussen 07:00 en 21:00 Brusselse tijd."""
    nu = nu or datetime.now(BRUSSEL)
    return 7 <= nu.hour < 21


def werk(naam, ag, r):
    """Het werk van een mailwacht binnen zijn ronde (de runner opent de ronde: N12)."""
    sys.path.insert(0, HIER)
    import bord  # noqa: E402
    nu = datetime.now(BRUSSEL)
    cfg = wachten()[naam]
    # Wat Mehdi op het maildashboard over afzenders besliste: belangrijk, ruis of opruimen.
    try:
        lijst = bord.call("/api/mailregels").get("regels", [])
    except Exception as e:  # noqa: BLE001
        lijst = []
        ag.log("regels", "bron", f"regels van het maildashboard niet gelezen: {type(e).__name__}")
    regels = {((x.get("postvak") or "*").lower(), (x.get("wie") or "").lower()): x.get("actie") for x in lijst}
    r.bron("mailregels", json.dumps(sorted(f"{k[0]} {k[1]} {v}" for k, v in regels.items()), ensure_ascii=False))
    items, tel, rijen, alle = ronde(naam, ag, r, nu, regels)
    opgeruimd, postvakken = [], []
    for adres in cfg["postvakken"]:
        mb = postvak(adres)
        schrijven = bool(mb and mb.get("schrijven") and not mb.get("bron"))
        postvakken.append({"postvak": adres, "wacht": naam, "schrijven": 1 if schrijven else 0})
        for (pv, wie), actie in regels.items():
            if actie == "opruimen" and pv in (adres.lower(), "*") and schrijven:
                try:
                    opgeruimd += [f"{adres}:{mid}" for mid in opruimen(mb, wie)]
                except Exception as e:  # noqa: BLE001
                    ag.log("opruimen", "fout", f"{adres} {wie}: {type(e).__name__}: {str(e)[:120]}")
    tel["opgeruimd"] = len(opgeruimd)
    try:
        bord.call("/api/mail", {"wacht": naam, "rijen": alle, "opgeruimd": opgeruimd, "postvakken": postvakken})
    except Exception as e:  # noqa: BLE001
        r.nood("Het maildashboard kreeg de berichten van deze ronde niet", wie="claude-code")
        ag.log("dashboard", "schrijf", f"/api/mail: {type(e).__name__}: {str(e)[:120]}")
    for it in items:
        it["van"] = naam
        if "stil" in it["titel"].lower():  # het woord stil laat De Bode bellen (AGENTNORM 6)
            it["titel"] = re.sub("stil", "st.l", it["titel"], flags=re.I)
    uit = ag.klaarzet(items) if items else {"nieuw": 0}
    afsluiten(naam, items, bord, ag, nu)
    if rijen:
        try:
            bord.call("/api/gesprekken", {"rijen": rijen})
        except Exception as e:  # noqa: BLE001
            ag.log("gesprekken", "schrijf", f"gesprekkentabel niet bijgewerkt: {type(e).__name__}")
    r.detail = (f"laatste 24 u: hoog {tel['hoog']}, gewoon {tel['midden']}, actie {tel['actie']}, meldingen {tel['melding']}, "
                f"koud {tel['koud']}, rommel {tel['rommel']}, verdacht {tel['verdacht']}; op de lijst van de "
                f"Mailregisseur: {tel['open']} (nieuw {uit.get('nieuw', 0)}); opgeruimd {tel['opgeruimd']}")
    ag.log(f"dag {nu.date().isoformat()}", "ronde", r.detail,
           "\n".join(f"{i['inhoud']['datum'][:16]} {i['inhoud']['soort']} {i['titel']}" for i in items[:80]))

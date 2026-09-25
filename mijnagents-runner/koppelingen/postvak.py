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
import json
import os
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
POST = os.path.join(os.path.dirname(RUNNER), "post")
os.environ.setdefault("POSTBUS_CONFIG", os.path.expanduser("~/post-config/mailboxen.yaml"))
BRUSSEL = ZoneInfo("Europe/Brussels")
WACHTEN = os.path.join(RUNNER, "werkwijze", "mailwachten.json")

OPVOLGEN_NA_WERKDAGEN = 2   # een gewoon bericht zonder antwoord wordt na zoveel werkdagen een opvolgpunt
TERUG_DAGEN = 21            # zover kijken we terug naar berichten die op antwoord wachten
ACTIE_DAGEN = 7             # zolang blijft een automatisch bericht met gevolg op de lijst
BEKEND_DAGEN = 180          # wie we in deze periode mailden, is een bekend contact

# Rollen en woorden, overgenomen van de Mac-mailwacht (mac/mail_wacht.py), uitgebreid met
# wat op 25-09-2026 in info@ H-Architects en info@ H-Invest binnenkwam.
ROLLEN = {
    "boekhouder": ["octopus", "boekhoud", "accountant", "fiscal", "liantis", "din consulting"],
    "bank": ["kbc", "belfius", "bnp", "ing.be", "argenta", "crelan", "alpha credit", "alphacredit"],
    "overheid": ["belgium.be", "vlaanderen.be", "minfin", "fod", "rsz", "onss", "socialsecurity", "gemeente", "stad.",
                 "omgevingsloket", "vlabel", "belastingdienst", "architect.be", "orde van architecten"],
    "notaris": ["notaris"], "advocaat": ["advoca", "law"], "deurwaarder": ["deurwaarder", "gerechtsdeurwaarder"],
    "verzekering": ["verzeker", "insurance", "ethias", "axa", "ag.be", "baloise", "arcoinsurance"],
}
HOOG_ROLLEN = {"boekhouder", "bank", "overheid", "notaris", "advocaat", "deurwaarder", "verzekering"}
HOOG = ["factuur", "betaling", "betalen", "betalingsuitnodiging", "herinnering", "aanmaning", "deadline", "uiterlijk",
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
                       "statement", "welcome to", "password", "wachtwoord"]
# Een afzender die zich voordoet als bank of overheid vanaf een gratis mailadres is verdacht:
# nooit doorgeven als belangrijk, wel tellen. Gezien 25-09-2026: "My MINFIN" van een gmail-adres.
GRATIS = ("gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "live.com", "icloud.com")
VERDACHTE_NAMEN = ["minfin", "fod financi", "belastingdienst", "kbc", "belfius", "ing ", "itsme", "politie", "bpost"]
GESPREK = re.compile(r"^\s*(re|antw|aw|sv|fw|fwd|tr)\s*:", re.I)


def wachten():
    """De configuratie van alle mailwachten: {naam: {postvakken, antwoord_vanuit, firma, ...}}."""
    with open(WACHTEN, encoding="utf-8") as f:
        return json.load(f)


VERZONDEN = ("INBOX.Sent", "INBOX.Sent Messages", "INBOX.Sent Items", "Sent")


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
            uit += koppen(adres, m, sinds=sinds, plafond=plafond)
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
    """Het postvak uit de postbus, met zijn gegevens; None als het er niet in staat."""
    config, _ = _postbus()
    mailboxen, _fouten = config.alles()
    return next((m for m in mailboxen if m["adres"].lower() == adres.lower()), None)


def koppen(adres, mapnaam="INBOX", sinds=None, maximaal=200, plafond=1000):
    """Koppen van een postvak via de postbus: alleen lezen, nieuwste eerst."""
    _, imapbron = _postbus()
    mb = postvak(adres)
    if not mb:
        raise LookupError(f"{adres} staat niet in de postbus")
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


def trieer(b, eigen_domeinen=(), bekend=frozenset()):
    """(soort, waarom) voor een kop uit imapbron.lijst; zie de lijst bovenaan dit bestand."""
    van, naam, ond = (b.get("van") or "").lower(), (b.get("van_naam") or "").lower(), schoon(b.get("onderwerp"))
    o = ond.lower()
    dom = _domein(van)
    if dom.endswith(GRATIS) and any(v in naam for v in VERDACHTE_NAMEN):
        return "verdacht", f"'{b.get('van_naam')}' vanaf een gratis adres ({dom})"
    if re.match(r"(automatisch antwoord|automatic reply|auto(matic)?[- ]?reply|out of office|afwezig|absence)", o):
        return "melding", "automatisch afwezigheidsbericht"
    rol = next((r for r, delen in ROLLEN.items() if any(d in f"{van} {naam} {o}" for d in delen)), "")
    woord = next((w for w in HOOG if w in o), "")
    automatisch = any(a in van or a in naam for a in MELDING_AFZENDERS) or any(m in o for m in MELDING_ONDERWERPEN)
    reclame = any(d in van for d in ROMMEL_DOMEINEN) or any(w in o for w in ROMMEL)
    if reclame and not woord:
        return "rommel", "reclame, nieuwsbrief of afmelding"
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


def ronde(naam, ag, r, nu=None):
    """Een ronde van mailwacht `naam`. `ag` is de bord.Agent (of iets met log), `r` de lopende Ronde.
    Geeft (items voor de Mailregisseur, telling, rijen voor de gesprekkentabel)."""
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
    items, rijen = [], []
    for adres in cfg["postvakken"]:
        if not postvak(adres):
            r.nood(f"{adres} staat niet in de postbus: de wacht kan het niet lezen", wie="claude-code")
            continue
        try:
            berichten = koppen_mappen(adres, mappen_van(adres), sinds, ag)
        except Exception as e:  # noqa: BLE001
            r.nood(f"{adres} niet leesbaar via de postbus", wie="claude-code")
            ag.log("inbox", "bron", f"{adres}: {type(e).__name__}: {str(e)[:120]}")
            continue
        afwezig = {}
        for b in berichten:
            if re.match(r"(automatisch antwoord|automatic reply|auto(matic)?[- ]?reply|out of office|afwezig|absence)",
                        schoon(b.get("onderwerp")).lower()) and _datum(b):
                afwezig.setdefault(b.get("van", ""), []).append(_datum(b))
        for b in berichten:
            d = _datum(b)
            if not d:
                continue
            soort, waarom = trieer(b, eigen, bekend)
            ond = schoon(b.get("onderwerp"))
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
                                                  "hoog": "beantwoorden of regelen: " + waarom,
                                                  "midden": "beantwoorden of doorzetten naar wie het opvolgt"}[soort]}})
    return items, tel, rijen


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
    items, tel, _ = ronde(naam, _DroogAgent(), r, nu)
    print(json.dumps(tel, ensure_ascii=False))
    for it in items:
        i = it["inhoud"]
        print(f"  opvolgen: {i['datum'][:10]} ({i['werkdagen_zonder_antwoord']} wd) {i['soort']:6} {it['titel'][:105]}  [{i['waarom']}]")
    for t, w in r.noden:
        print(f"  nood ({w}): {t}")
    return items, tel


def aan_de_beurt(nu=None):
    """Cadans van de mailwachten: elk uur tussen 07:00 en 21:00 Brusselse tijd."""
    nu = nu or datetime.now(BRUSSEL)
    return 7 <= nu.hour < 21


def werk(naam, ag, r):
    """Het werk van een mailwacht binnen zijn ronde (de runner opent de ronde: N12)."""
    sys.path.insert(0, HIER)
    import bord  # noqa: E402
    nu = datetime.now(BRUSSEL)
    items, tel, rijen = ronde(naam, ag, r, nu)
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
                f"Mailregisseur: {tel['open']} (nieuw {uit.get('nieuw', 0)})")
    ag.log(f"dag {nu.date().isoformat()}", "ronde", r.detail,
           "\n".join(f"{i['inhoud']['datum'][:16]} {i['inhoud']['soort']} {i['titel']}" for i in items[:80]))

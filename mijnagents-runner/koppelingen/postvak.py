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
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
POST = os.path.join(os.path.dirname(RUNNER), "post")
os.environ.setdefault("POSTBUS_CONFIG", os.path.expanduser("~/post-config/mailboxen.yaml"))
STAAT = os.path.expanduser("~/appportal/mijnagents-data/postvak")
BRUSSEL = ZoneInfo("Europe/Brussels")
WACHTEN = os.path.join(RUNNER, "werkwijze", "mailwachten.json")

# Na zoveel werkdagen zonder antwoord wordt een bericht een opvolgpunt.
OPVOLGEN_NA_WERKDAGEN = 2
# Zover kijken we terug naar berichten die nog op antwoord wachten.
TERUG_DAGEN = 21

# Rollen en woorden, overgenomen van de Mac-mailwacht (mac/mail_wacht.py), uitgebreid met
# de Engelse meldingen die in info@ binnenkomen (Dropbox gepauzeerd, betaalmethode).
ROLLEN = {
    "boekhouder": ["octopus", "boekhoud", "accountant", "fiscal", "liantis"],
    "bank": ["kbc", "belfius", "bnp", "ing.be", "argenta", "crelan", "alpha credit", "alphacredit"],
    "overheid": ["belgium.be", "vlaanderen.be", "minfin", "fod", "rsz", "onss", "socialsecurity", "gemeente", "stad.",
                 "omgevingsloket", "vlabel", "belastingdienst"],
    "notaris": ["notaris"], "advocaat": ["advoca", "law"], "deurwaarder": ["deurwaarder", "gerechtsdeurwaarder"],
    "verzekering": ["verzeker", "insurance", "ethias", "axa", "ag.be", "baloise", "arcoinsurance"],
}
HOOG_ROLLEN = {"boekhouder", "bank", "overheid", "notaris", "advocaat", "deurwaarder", "verzekering"}
HOOG = ["factuur", "betaling", "betalen", "betalingsuitnodiging", "herinnering", "aanmaning", "deadline", "uiterlijk",
        "dringend", "urgent", "ingebrekestelling", "vervaldag", "vervalt", "verloopt", "contract", "vergunning",
        "belasting", "aanslag", "schorsing", "opzeg", "action needed", "action required", "payment", "overdue",
        "deactivated", "suspended", "paused", "expire", "e-box"]
ROMMEL = ["nieuwsbrief", "newsletter", "unsubscribe", "uitschrijven", "aanbieding", "korting", "promo", "webinar",
          "gratis", "free publication", "offres", "points", "word dealer", "ontdek", "visit", "stand at",
          "proposition", "partenariat", "infogids", "mening wordt gevraagd"]
ROMMEL_DOMEINEN = ["klaviyomail", "mailjet", "emlmkt", "smile.io", "sendgrid", "mailchimp", "mcsv.net", "hubspot",
                   "newsletter", "nieuws.", "beemailing", "customer-mail", "-mkt."]
MELDING_AFZENDERS = ["noreply", "no-reply", "donotreply", "robot@", "notification", "notificatie", "alerts",
                     "mailer-daemon", "postmaster", "bpost", "dpdgroup", "postnl", "shopify", "zendesk"]
# Een afzender die zich voordoet als bank of overheid vanaf een gratis mailadres is verdacht:
# nooit doorgeven als belangrijk, wel tellen. Gezien 25-09-2026: "My MINFIN" van een gmail-adres.
GRATIS = ("gmail.com", "hotmail.com", "outlook.com", "yahoo.", "live.com", "icloud.com")
VERDACHTE_NAMEN = ["minfin", "fod financi", "belastingdienst", "kbc", "belfius", "ing ", "itsme", "politie", "bpost"]


def wachten():
    """De configuratie van alle mailwachten: {naam: {postvakken, antwoord_vanuit, firma, ...}}."""
    with open(WACHTEN, encoding="utf-8") as f:
        return json.load(f)


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


def koppen(adres, mapnaam="INBOX", sinds=None, aan=None, maximaal=200):
    """Koppen van een postvak via de postbus: alleen lezen. Geeft de lijst uit imapbron.lijst."""
    _, imapbron = _postbus()
    mb = postvak(adres)
    if not mb:
        raise LookupError(f"{adres} staat niet in de postbus")
    uit, vanaf = [], 0
    while True:
        r = imapbron.lijst(mb, mapnaam, sinds=sinds, aan=aan, maximaal=maximaal, vanaf=vanaf)
        uit += r["berichten"]
        if not r["meer"] or len(uit) >= 1000:
            return uit
        vanaf = r["volgende_vanaf"]


def _domein(adres):
    return adres.rsplit("@", 1)[-1].lower() if "@" in adres else ""


def trieer(b, eigen_domeinen=()):
    """(belang, soort, waarom) voor een kop uit imapbron.lijst.

    belang: rommel (reclame, nieuwsbrief), verdacht (lijkt phishing), melding (automatisch
    bericht zonder vraag), midden (een mens), hoog (rol of woord met gevolg).
    Rommel en verdacht komen nooit bij Mehdi; ze worden alleen geteld."""
    van, naam, ond = (b.get("van") or "").lower(), (b.get("van_naam") or "").lower(), schoon(b.get("onderwerp"))
    laag = f"{van} {naam} {ond}".lower()
    dom = _domein(van)
    if re.match(r"(automatisch antwoord|automatic reply|auto(matic)?[- ]?reply|out of office|afwezig|absence)", ond, re.I):
        return "melding", "afwezig", "automatisch afwezigheidsbericht"
    if dom.endswith(GRATIS) and any(v in naam for v in VERDACHTE_NAMEN):
        return "verdacht", "phishing", f"'{b.get('van_naam')}' vanaf een gratis adres ({dom})"
    rol = next((r for r, delen in ROLLEN.items() if any(d in laag for d in delen)), "")
    woord = next((w for w in HOOG if w in ond.lower()), "")
    automatisch = any(a in van for a in MELDING_AFZENDERS)
    reclame = any(d in dom or d in van for d in ROMMEL_DOMEINEN) or any(w in ond.lower() for w in ROMMEL)
    eigen = dom in eigen_domeinen
    if reclame and not (rol in HOOG_ROLLEN and woord):
        return "rommel", "reclame", "reclame of nieuwsbrief"
    if (rol in HOOG_ROLLEN or woord) and not eigen:
        return "hoog", ("factuur" if re.search(r"factuur|invoice|betal|payment|aanrekening", ond, re.I) else "bericht"), \
            ", ".join(x for x in (f"rol {rol}" if rol else "", f"woord '{woord}'" if woord else "") if x)
    if automatisch:
        return "melding", "melding", "automatisch bericht"
    return "midden", "bericht", "geschreven door een mens" + (" (eigen domein)" if eigen else "")


def schoon(tekst):
    """Een onderwerp op een regel: IMAP vouwt lange koppen over meerdere regels."""
    return re.sub(r"\s+", " ", tekst or "").strip()


def werkdagen_tussen(van, tot):
    """Aantal volle werkdagen (ma-vr) tussen twee momenten."""
    d, n = van.date(), 0
    while d < tot.date():
        d += timedelta(days=1)
        if d.weekday() < 5 and d <= tot.date():
            n += 1
    return max(0, n - (1 if tot.date() > van.date() and tot.weekday() >= 5 else 0))


def _datum(b):
    try:
        return datetime.fromisoformat(b["datum"]).astimezone(BRUSSEL)
    except (KeyError, TypeError, ValueError):
        return None


def beantwoord(van_adres, na, verzonden):
    """Is er na dit moment iets verstuurd naar deze afzender, vanuit een van de postvakken van de firma?"""
    for s in verzonden:
        d = _datum(s)
        if d and d >= na and any(van_adres in a.lower() for a in (s.get("aan") or []) + (s.get("cc") or [])):
            return True
    return False


def ronde(naam, ag, r, nu=None):
    """Een ronde van mailwacht `naam`. `ag` is de bord.Agent, `r` de lopende Ronde.
    Geeft (items voor de Mailregisseur, telling, rijen voor de gesprekkentabel)."""
    nu = nu or datetime.now(BRUSSEL)
    cfg = wachten()[naam]
    r.bron("mailwachten.json", json.dumps(cfg, ensure_ascii=False, sort_keys=True))
    eigen = tuple(cfg.get("eigen_domeinen") or ())
    sinds = (nu - timedelta(days=TERUG_DAGEN)).date().isoformat()
    tel = {"hoog": 0, "midden": 0, "melding": 0, "rommel": 0, "verdacht": 0, "open": 0}
    verzonden = []
    for adres in cfg.get("antwoord_vanuit", []) + cfg["postvakken"]:
        mb = postvak(adres)
        if not mb:
            continue
        mappen = [m for m in ("INBOX.Sent", "Sent", "INBOX.Verzonden") if not mb.get("mappen") or m in mb["mappen"]]
        for m in mappen[:1]:
            try:
                verzonden += koppen(adres, m, sinds=sinds)
            except Exception as e:  # noqa: BLE001
                ag.log("verzonden", "bron", f"{adres} {m} niet leesbaar: {type(e).__name__}")
    tel["verzonden_gelezen"] = len(verzonden)
    items, rijen = [], []
    for adres in cfg["postvakken"]:
        if not postvak(adres):
            r.nood(f"{adres} staat niet in de postbus: de wacht kan het niet lezen", wie="claude-code")
            continue
        try:
            berichten = koppen(adres, "INBOX", sinds=sinds)
        except Exception as e:  # noqa: BLE001
            r.nood(f"{adres} niet leesbaar via de postbus", wie="claude-code")
            ag.log("inbox", "bron", f"{adres}: {type(e).__name__}: {str(e)[:120]}")
            continue
        for b in berichten:
            d = _datum(b)
            if not d:
                continue
            belang, soort, waarom = trieer(b, eigen)
            if d >= nu - timedelta(days=1):
                tel[belang] += 1
                if belang in ("hoog", "midden"):
                    rijen.append({"uniek": f"mail:{(b.get('message_id') or f'{adres}:{b['uid']}')[:150]}",
                                  "datum": d.strftime("%Y-%m-%d"), "start": d.strftime("%H:%M"), "minuten": 0,
                                  "personen": (b.get("van_naam") or b.get("van") or "")[:80], "bedrijf": _domein(b.get("van", "")),
                                  "afdeling": cfg.get("afdeling", ""), "thema": f"{soort}: {schoon(b.get('onderwerp'))[:90]}",
                                  "project": "", "prive": 0, "zekerheid": "middel", "waarom": f"belang {belang}; {waarom}",
                                  "archief": "", "link": "", "opgenomen_door": adres, "bron": "mail"})
            if belang not in ("hoog", "midden") or _domein(b.get("van", "")) in eigen:
                continue
            wacht = werkdagen_tussen(d, nu)
            if wacht < OPVOLGEN_NA_WERKDAGEN and belang != "hoog":
                continue
            if beantwoord(b.get("van", ""), d, verzonden):
                continue
            tel["open"] += 1
            mid = (b.get("message_id") or f"{adres}:{b['uid']}")[:150]
            items.append({"voor": "mail-regisseur", "soort": "mail", "sleutel": cfg.get("firma", ""),
                          "titel": f"{cfg.get('firma', '')}: {(b.get('van_naam') or b.get('van'))[:40]} · {schoon(b.get('onderwerp'))[:80]}",
                          "uniek": f"opvolgen:{naam}:{mid}",
                          "inhoud": {"postvak": adres, "van": b.get("van"), "van_naam": b.get("van_naam"),
                                     "onderwerp": schoon(b.get("onderwerp")), "datum": d.isoformat(), "uid": b.get("uid"),
                                     "belang": belang, "waarom": waarom, "werkdagen_zonder_antwoord": wacht,
                                     "voorstel": ("antwoorden of doorzetten naar wie het opvolgt" if belang == "midden"
                                                  else "nakijken: " + waarom)}})
    return items, tel, rijen


class _Droog:
    """Een ronde die niets naar het bord schrijft: voor een proef op de VM."""

    def __init__(self):
        self.noden, self.bronnen, self.detail = [], {}, ""

    def bron(self, naam, inhoud):
        self.bronnen[naam] = len(inhoud)

    def nood(self, tekst, wie="mehdi"):
        self.noden.append((tekst, wie))


class _DroogAgent:
    def log(self, *a):
        print("  [log]", " | ".join(str(x)[:160] for x in a[:3]))


def afsluiten(naam, items, bord, ag, nu):
    """Wat ik vorige keer klaarzette en nu niet meer meld, is beantwoord: dan haal ik het van de
    lijst van de Mailregisseur. Een bericht ouder dan mijn venster laat ik staan, want daarvan
    weet ik niet of het beantwoord is; wat blijft staan, wordt niet vergeten."""
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
            bord.opgepakt(it["id"], f"{naam}: beantwoord")
            n += 1
    if n:
        ag.log("opvolgen", "schrijf", f"{n} opvolgpunten beantwoord en van de lijst gehaald")
    return n


def draai(naam, droog=False):
    """Volledige ronde van een mailwacht, via de gedeelde ronde (N4, N10, N11, N13, N14).
    droog: alleen lezen en tonen wat er klaargezet zou worden, niets naar het bord."""
    sys.path.insert(0, HIER)
    import bord  # noqa: E402
    nu = datetime.now(BRUSSEL)
    if droog:
        r = _Droog()
        items, tel, rijen = ronde(naam, _DroogAgent(), r, nu)
        print(json.dumps(tel, ensure_ascii=False))
        for it in items:
            print(f"  opvolgen: {it['inhoud']['datum'][:10]} ({it['inhoud']['werkdagen_zonder_antwoord']} wd) "
                  f"{it['inhoud']['belang']:6} {it['titel'][:110]}  [{it['inhoud']['waarom']}]")
        for t, w in r.noden:
            print(f"  nood ({w}): {t}")
        return items, tel
    ag = bord.Agent(naam)
    if nu.hour < 7 or nu.hour >= 21:
        return  # stille uren: geen ronde, geen hartslag nodig (cadans: elk uur 07-21)
    with ag.ronde("postvak in het oog") as r:
        items, tel, rijen = ronde(naam, ag, r, nu)
        for it in items:
            it["van"] = naam
            if "stil" in it["titel"].lower():  # het woord stil laat De Bode bellen (AGENTNORM 6)
                it["titel"] = it["titel"].replace("stil", "st.l")
        uit = ag.klaarzet(items) if items else {"nieuw": 0}
        afsluiten(naam, items, bord, ag, nu)
        if rijen:
            try:
                bord.call("/api/gesprekken", {"rijen": rijen})
            except Exception as e:  # noqa: BLE001
                ag.log("gesprekken", "schrijf", f"gesprekkentabel niet bijgewerkt: {type(e).__name__}")
        r.detail = (f"laatste 24 u: hoog {tel['hoog']}, gewoon {tel['midden']}, meldingen {tel['melding']}, "
                    f"rommel {tel['rommel']}, verdacht {tel['verdacht']}; wacht op antwoord: {tel['open']} "
                    f"(nieuw klaargezet voor de Mailregisseur: {uit.get('nieuw', 0)})")
        ag.log(f"dag {nu.date().isoformat()}", "ronde", r.detail,
               "\n".join(f"{i['inhoud']['datum'][:16]} {i['titel']}" for i in items[:60]))

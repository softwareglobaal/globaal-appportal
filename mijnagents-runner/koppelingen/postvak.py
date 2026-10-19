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
  midden    een bekend contact, een lopend gesprek of een aanvraag: opvolgen na een werkdag
  hoog      een mens met een rol of woord met gevolg (bank, overheid, aanmaning): meteen opvolgen

Een bron voor wat openstaat (driehoeksoverleg 19-10-2026, 3-0): elke wacht geeft per bericht zijn opvolging door aan
de bord-tabel mailbericht (/api/mail): open, onzeker, beantwoord, doorgezet, wacht, verlopen of geen. Wat Mehdi op
/mail beslist (afgehandeld, doorgezet, ruis) staat ernaast en overschrijft de wacht nooit. Het maildashboard, De
Mailregisseur, zijn 08:00-bericht en het werkverslag van de wacht tellen alleen daaruit. Beantwoord betekent: een
verzonden bericht verwijst in zijn draad (In-Reply-To of References) naar dit bericht, uit welk postvak ook.
"""
import email
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timedelta
from email.utils import parseaddr, parsedate_to_datetime
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
POST = os.path.join(os.path.dirname(RUNNER), "post")
os.environ.setdefault("POSTBUS_CONFIG", os.path.expanduser("~/post-config/mailboxen.yaml"))
BRUSSEL = ZoneInfo("Europe/Brussels")
WACHTEN = os.path.join(RUNNER, "werkwijze", "mailwachten.json")

OPVOLGEN_NA_WERKDAGEN = 1   # een gewoon bericht zonder antwoord wordt na zoveel werkdagen een opvolgpunt (2 tot 19-10-2026)
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
                       "statement", "welcome to", "password", "wachtwoord", "import rapport", "uitgavenstaat",
                       # 19-10-2026: kwamen boven toen gewone mail na een werkdag op de lijst kwam (KLM, stadsarchief)
                       "boeking is bevestigd", "check-in is begonnen", "uw download van"]
# De kopieermachine (Konica Minolta bizhub C258) mailt scans als "Message from KM_C258". Gemeten 19-10-2026: 38 berichten
# in mailbericht, 11 van de 26 berichten van een eigen domein bij mch@ in twee weken. Alleen op het exacte adres, niet op
# het onderwerp (dat kan iedereen nabootsen). Een collega die een scan doorstuurt ("Fwd: Message from KM_C258") is een
# mens en blijft een gewoon bericht.
SCANNERS = ("scan@harmoniebouw.be",)
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
# Gratis maildiensten en providers: een heel domein daarvan raakt iedereen. Nooit automatisch opruimen op zo'n domein
# (zelfde lijst als MAIL_GEEN_DOMEIN op het bord, zonder de eigen groep).
GRATIS_DIENSTEN = ("gmail.com", "googlemail.com", "hotmail.com", "hotmail.be", "outlook.com", "outlook.be", "live.com",
                   "live.be", "yahoo.com", "icloud.com", "me.com", "telenet.be", "skynet.be", "proximus.be")
VERDACHTE_NAMEN = ["minfin", "fod financi", "belastingdienst", "kbc", "belfius", "ing ", "itsme", "politie", "bpost"]
GESPREK = re.compile(r"^\s*(re|antw|aw|sv|fw|fwd|tr)\s*:", re.I)
# Dringend: hiervoor mag De Mailregisseur De Bode vragen Mehdi te bellen (Mehdi, 26-09-2026: "voor de urgente zaken kan
# de agent mijn andere agent vragen mij te bellen"). Alleen bij belangrijk zonder antwoord; bewust smal, anders is het ruis.
DRINGEND = re.compile(r"(gerechts)?deurwaarder|ingebrekestelling|dagvaarding|\bbeslag|laatste (aanmaning|herinnering|verwittiging)|"
                      r"tweede aanmaning|derde aanmaning|\bafsluiting|schorsing|tuchtprocedure|vonnis|mise en demeure|dernier rappel|"
                      r"final notice|account (is )?(suspended|deactivated|gepauzeerd|paused)", re.I)


def wachten():
    """De configuratie van alle mailwachten: {naam: {postvakken, antwoord_vanuit, firma, ...}}."""
    with open(WACHTEN, encoding="utf-8") as f:
        return json.load(f)


VERZONDEN = ("INBOX.Sent", "INBOX.Sent Messages", "INBOX.Sent Items", "Sent", "[Gmail]/Verzonden berichten", "[Gmail]/Sent Mail")
DATA = os.path.expanduser("~/appportal/mijnagents-data")
REGELMAP = os.path.join(RUNNER, "mailregels")   # sorteerregels per postvak; ook de Mac-tools lezen hier (26-9-2026)
SORTEER_DAGEN = 3           # de nieuwe mail van zoveel dagen wordt elke ronde gesorteerd, zoals de ochtendtaak van 24-9
BRON_VERS_UREN = 3          # een kopie van de Mac die ouder is dan dit, meld ik als niet vers
VERZONDEN_PLAFOND = 5000    # zoveel verzonden berichten per map lees ik hoogstens; meer is niet volledig gelezen


def mappen_van(adres):
    """De mappen die van dit postvak gelezen worden; standaard alleen INBOX (zie mailwachten.json, 'mappen')."""
    try:
        return wachten().get("mappen", {}).get(adres) or ["INBOX"]
    except (OSError, ValueError):
        return ["INBOX"]


def koppen_mappen(adres, mappen, sinds, ag=None, plafond=1000, fouten=None):
    """Koppen uit meerdere mappen; een map die niet bestaat of niet leesbaar is, wordt overgeslagen en gelogd. Wat niet
    volledig gelezen werd (onleesbaar, of het plafond bereikt), komt in `fouten`."""
    uit, gelukt = [], 0
    for m in mappen:
        try:
            deel = koppen(adres, m, sinds=sinds, plafond=plafond)
            uit += [dict(b, map_=m) for b in deel]
            gelukt += 1
            if fouten is not None and len(deel) >= plafond:
                fouten.append(f"{adres} {m}: meer dan {plafond} berichten")
        except Exception as e:  # noqa: BLE001
            if fouten is not None:
                fouten.append(f"{adres} {m}: {type(e).__name__}")
            if ag:
                ag.log("mappen", "bron", f"{adres} {m} niet leesbaar: {type(e).__name__}")
    if not gelukt:
        raise LookupError(f"geen enkele map van {adres} leesbaar")
    return uit


def mapnamen(mb):
    """De mappen van een postvak in kleine letters (alleen lezen); None voor een bestand van de Mac."""
    if mb.get("bron"):
        return None
    _, imapbron = _postbus()
    with imapbron._Sessie(mb) as M:
        return {n.lower() for _, n in imapbron._lijst_mappen(M)}


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


def automatisch(b):
    """Is dit een automatisch bericht (geen mens)? Volgens de bron zelf ('automatisch', Mail op de Mac), de afzender
    (noreply, scan@, ...) of het onderwerp (bestelling, pakje, de kopieermachine)."""
    van, naam = (b.get("van") or "").lower(), (b.get("van_naam") or "").lower()
    o = schoon(b.get("onderwerp")).lower()
    return (bool(b.get("automatisch")) or any(a in van or a in naam for a in MELDING_AFZENDERS)
            or any(m in o for m in MELDING_ONDERWERPEN) or van in SCANNERS)


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
    reclame = any(d in van for d in ROMMEL_DOMEINEN) or any(w in o for w in ROMMEL)
    if reclame and not woord:
        return "rommel", "reclame, nieuwsbrief of afmelding"
    if b.get("lijst") and rol not in HOOG_ROLLEN and not woord:
        return "melding", "mailinglijst of nieuwsbrief"
    if automatisch(b):
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


# Beantwoord via de draad (driehoeksoverleg 19-10-2026, 3-0). Tot dan gold "na de ontvangst iets verstuurd naar dat
# adres" als beantwoord, los van het onderwerp: een belangrijk bericht verdween van de lijst zodra iemand die afzender
# om een andere reden mailde. Nu sluit alleen een verzonden bericht dat rechtstreeks op dit bericht antwoordt
# (In-Reply-To). References bevat de hele draad: een antwoord op een later bericht in dezelfde draad zegt niet dat deze
# vraag beantwoord is, dus dat wordt onzeker (ontwerptoets 19-10-2026, Claude O5, 3-0).
VOORVOEGSEL = re.compile(r"^\s*((re|antw|aw|sv|fw|fwd|tr|wg|doorgestuurd|forwarded)\s*(\[\d+\])?\s*:\s*)+", re.I)
DOORGESTUURD = re.compile(r"^\s*(fw|fwd|tr|wg|doorgestuurd|forwarded)\s*:", re.I)
MSGID = re.compile(r"<[^<>\s]+>")


def kern(onderwerp):
    """Het onderwerp zonder Re:, Antw:, Fwd: en dergelijke, in kleine letters, met enkele spaties."""
    return VOORVOEGSEL.sub("", schoon(onderwerp)).strip().lower()


def wie_is(b):
    """De sleutels waarmee een antwoord naar dit bericht kan verwijzen: de Message-ID, of de hash van Mail op de Mac."""
    k = {m.lower() for m in MSGID.findall(b.get("message_id") or "")}
    if b.get("draad"):
        k.add("#" + str(b["draad"]))
    return k


def antwoordt_op(s):
    """Waarop dit (verzonden) bericht rechtstreeks antwoordt: In-Reply-To. Van de Mac komt alleen de reeks verwijzingen
    (message_references, in de volgorde van de kop); de laatste daarvan is volgens RFC 5322 het bericht waarop geantwoord
    wordt."""
    k = {m.lower() for m in MSGID.findall(s.get("in_antwoord_op") or "")}
    if s.get("verwijst"):
        k.add("#" + str(list(s["verwijst"])[-1]))
    return k


def in_draad(s):
    """Alles waarnaar dit bericht in zijn draad verwijst: In-Reply-To en References (of de hashes van de Mac)."""
    k = {m.lower() for m in MSGID.findall(" ".join([s.get("in_antwoord_op") or ""] + list(s.get("verwijzingen") or [])))}
    return k | {"#" + str(h) for h in s.get("verwijst") or []}


def antwoord_index(verzonden):
    """Een keer per ronde: de verzonden post, op rechtstreeks antwoord, op draad en op ontvanger."""
    antw, draad, aan = {}, {}, {}
    for s in verzonden:
        d = _datum(s)
        if not d:
            continue
        for k in antwoordt_op(s):
            antw.setdefault(k, []).append((d, s))
        for k in in_draad(s):
            draad.setdefault(k, []).append((d, s))
        for a in (s.get("aan") or []) + (s.get("cc") or []):
            if _adres(a):
                aan.setdefault(_adres(a), []).append((d, kern(s.get("onderwerp")), s))
    return {"antw": antw, "draad": draad, "aan": aan}


def _eerste(index, sleutels):
    return sorted({id(s): (ds, s) for k in sleutels for ds, s in index.get(k, [])}.values(), key=lambda x: x[0])


def antwoord(b, d, index, afwezig=None):
    """(opvolging, door, wanneer, naar) voor een ontvangen bericht b met datum d.
      beantwoord  een verzonden bericht antwoordt rechtstreeks op b (In-Reply-To); door = het postvak dat antwoordde,
                  ook een ander dan dat van b
      doorgezet   idem, maar doorgestuurd (Fwd:, TR:, ...); naar = de eerste ontvanger
      onzeker     geen rechtstreeks antwoord, maar een verzonden bericht noemt b in zijn draad (References), of na d ging
                  er een mail met hetzelfde onderwerp naar die afzender, of hij stuurde een afwezigheidsbericht op zo'n
                  mail: misschien beantwoord; blijft op de lijst, met wie en wanneer
      open        anders. Een ander onderwerp naar dezelfde afzender sluit niets."""
    sleutels = wie_is(b)
    rechtstreeks = _eerste(index["antw"], sleutels)
    antw = [(ds, s) for ds, s in rechtstreeks if not DOORGESTUURD.match(schoon(s.get("onderwerp")))]
    if antw:
        ds, s = antw[0]
        return "beantwoord", (s.get("van") or "").lower(), ds.isoformat(), ""
    if rechtstreeks:
        ds, s = rechtstreeks[0]
        naar = next((_adres(a) for a in (s.get("aan") or []) if _adres(a)), "")
        return "doorgezet", (s.get("van") or "").lower(), ds.isoformat(), naar
    in_dezelfde = _eerste(index["draad"], sleutels)
    if in_dezelfde:
        ds, s = in_dezelfde[0]
        return "onzeker", (s.get("van") or "").lower(), ds.isoformat(), ""
    van, onder = (b.get("van") or "").lower(), kern(b.get("onderwerp"))
    if len(onder) >= 4:
        for ds, k, s in sorted(index["aan"].get(van, []), key=lambda x: x[0]):
            if ds >= d and k == onder:
                return "onzeker", (s.get("van") or "").lower(), ds.isoformat(), ""
        for ds, ond in sorted((afwezig or {}).get(van, [])):
            if ds >= d and onder in kern(ond):
                return "onzeker", "afwezigheidsbericht van de afzender", ds.isoformat(), ""
    return "open", "", "", ""


def ronde(naam, ag, r, nu=None, regels=None, oude=None, veilig=frozenset()):
    """Een ronde van mailwacht `naam`. `ag` is de bord.Agent (of iets met log), `r` de lopende Ronde.
    `oude`: wat volgens het bord voor deze wacht openstaat (/api/mail/open); wat ouder is dan mijn venster, toets ik ook
    aan de verzonden post, zodat een laat antwoord het nog sluit. `veilig`: domeinen die volgens het bord ooit iets
    belangrijks stuurden of beantwoord werden (/api/mail/veilig); die ruim ik nooit automatisch op.
    Geeft (wat openstaat, telling, rijen voor de gesprekkentabel, alle beoordeelde berichten voor het maildashboard)."""
    nu = nu or datetime.now(BRUSSEL)
    cfg = wachten()[naam]
    r.bron("mailwachten.json", json.dumps(cfg, ensure_ascii=False, sort_keys=True))
    eigen = tuple(cfg.get("eigen_domeinen") or ())
    sinds = (nu - timedelta(days=TERUG_DAGEN)).date().isoformat()
    tel = {s: 0 for s in ("hoog", "midden", "actie", "melding", "koud", "rommel", "verdacht")}
    tel["open"] = 0
    # De verzonden post van elk postvak dat kan antwoorden. Is die niet volledig gelezen (een map onleesbaar, of meer dan
    # het plafond), dan zegt het bord een eerder gevonden antwoord niet af (verzonden_volledig) en ruim ik geen reclame op:
    # een contact dat ik niet zag, is nog geen onbekende (ontwerptoets 19-10-2026, Codex O1 en O3).
    verzonden, onvolledig = [], []
    for adres in dict.fromkeys(cfg.get("antwoord_vanuit", []) + cfg["postvakken"]):
        mb = postvak(adres)
        if not mb:
            onvolledig.append(f"{adres} staat niet in de postbus")
            continue
        gelezen = False
        try:
            bestaand = mapnamen(mb)
        except Exception as e:  # noqa: BLE001
            onvolledig.append(f"{adres}: mappenlijst niet leesbaar ({type(e).__name__})")
            continue
        for m in VERZONDEN:
            if (mb.get("mappen") and m not in mb["mappen"]) or (bestaand is not None and m.lower() not in bestaand):
                continue  # niet elk postvak heeft elke variant van Verzonden
            try:
                deel = koppen(adres, m, sinds=(nu - timedelta(days=BEKEND_DAGEN)).date().isoformat(), plafond=VERZONDEN_PLAFOND)
            except Exception as e:  # noqa: BLE001
                onvolledig.append(f"{adres} {m}: bestaat maar is niet leesbaar ({type(e).__name__})")  # resultaattoets K2
                continue
            gelezen = True
            verzonden += deel
            if len(deel) >= VERZONDEN_PLAFOND:
                onvolledig.append(f"{adres} {m}: meer dan {VERZONDEN_PLAFOND} verzonden berichten in {BEKEND_DAGEN} dagen")
        if not gelezen:
            onvolledig.append(f"{adres}: geen map Verzonden leesbaar")
    if onvolledig:
        r.nood("Verzonden post niet volledig gelezen: gevonden antwoorden blijven staan, reclame wordt niet opgeruimd",
               wie="claude-code")
        ag.log("verzonden", "bron", "; ".join(onvolledig))
    bekend = frozenset(_adres(a) for s in verzonden for a in (s.get("aan") or []) + (s.get("cc") or []) if _adres(a))
    tel["verzonden_gelezen"], tel["bekende_contacten"] = len(verzonden), len(bekend)
    tel["verzonden_volledig"] = not onvolledig
    index = antwoord_index(verzonden)
    rijen, alle, volledig = [], [], set()
    for adres in cfg["postvakken"]:
        mb = postvak(adres)
        if not mb:
            r.nood(f"{adres} staat niet in de postbus: de wacht kan het niet lezen", wie="claude-code")
            continue
        oud = bron_uren_oud(mb, nu)
        if mb.get("bron") and (oud is None or oud > BRON_VERS_UREN):
            r.nood(f"De kopie van {adres} van de Mac is niet vers: de Mac slaapt, of Mail staat uit", wie="mehdi")
        fouten = []
        try:
            berichten = koppen_mappen(adres, mappen_van(adres), sinds, ag, fouten=fouten)
            if not fouten and not (mb.get("bron") and (oud is None or oud > BRON_VERS_UREN)):
                volledig.add(adres.lower())
        except Exception as e:  # noqa: BLE001
            r.nood(f"{adres} niet leesbaar via de postbus", wie="claude-code")
            ag.log("inbox", "bron", f"{adres}: {type(e).__name__}: {str(e)[:120]}")
            continue
        # Wat het postvak zelf verstuurde, is geen opvolgpunt (Gmail 'Alle e-mail' bevat ook de verzonden post).
        berichten = [b for b in berichten if (b.get("van") or "").lower() != adres.lower()]
        afwezig = {}
        for b in berichten:
            if automatisch_antwoord(b.get("onderwerp")) and _datum(b):
                afwezig.setdefault((b.get("van") or "").lower(), []).append((_datum(b), b.get("onderwerp") or ""))
        for b in berichten:
            d = _datum(b)
            if not d or not (b.get("message_id") or b.get("uid")):
                continue  # zonder datum of zonder sleutel kan ik het niet volgen (resultaattoets K5)
            regel = regel_voor(regels, adres, b.get("van"))
            soort, waarom = trieer(b, eigen, bekend, regel)
            ond = schoon(b.get("onderwerp"))
            wacht = werkdagen_tussen(d, nu)
            opvolging, door, wanneer, naar = "geen", "", "", ""
            if soort == "actie":
                opvolging = "verlopen" if d < nu - timedelta(days=ACTIE_DAGEN) else "open"
            elif soort in ("hoog", "midden"):
                # Eigen domein: alleen een automatisch bericht is geen opvolgpunt; een collega die iets vraagt wel (19-10-2026).
                if _domein(b.get("van", "")) in eigen and automatisch(b) and regel != "belangrijk":
                    opvolging = "geen"
                else:
                    opvolging, door, wanneer, naar = antwoord(b, d, index, afwezig)
                    if opvolging in ("open", "onzeker") and soort == "midden" and wacht < OPVOLGEN_NA_WERKDAGEN:
                        opvolging = "wacht"
            dringend = bool(soort in ("hoog", "actie") and DRINGEND.search(f"{ond} {b.get('van_naam') or ''}"))
            alle.append({"uniek": f"{adres}:{(b.get('message_id') or b.get('uid'))}"[:250], "wacht": naam, "postvak": adres,
                         "map": b.get("map_") or "", "datum": d.isoformat(), "van": (b.get("van") or "").lower(),
                         "van_naam": (b.get("van_naam") or "")[:120], "onderwerp": ond[:300], "soort": soort,
                         "waarom": kort_waarom(waarom), "mailinglijst": 1 if b.get("lijst") else 0,
                         "beantwoord": 1 if opvolging in ("beantwoord", "doorgezet") else 0,
                         "message_id": (b.get("message_id") or "")[:250], "opvolging": opvolging,
                         "antwoord_door": door[:120], "antwoord_ts": wanneer, "antwoord_naar": naar[:120],
                         "stap": stap(soort, opvolging, door, wanneer, naar), "dringend": 1 if dringend else 0,
                         "werkdagen": wacht, "regel": regel, "auto_opruimen": ""})
            if d >= nu - timedelta(days=1):
                tel[soort] += 1
                if soort in ("hoog", "midden", "actie"):
                    sleutel = b.get("message_id") or f"{adres}:{b.get('uid')}"
                    rijen.append({"uniek": f"mail:{sleutel[:150]}",
                                  "datum": d.strftime("%Y-%m-%d"), "start": d.strftime("%H:%M"), "minuten": 0,
                                  "personen": (b.get("van_naam") or b.get("van") or "")[:80], "bedrijf": _domein(b.get("van", "")),
                                  "afdeling": cfg.get("afdeling", ""), "thema": ond[:90], "project": "", "prive": 0,
                                  "zekerheid": "middel", "waarom": f"{soort}; {waarom}", "archief": "", "link": "",
                                  "opgenomen_door": adres, "bron": "mail"})
    # Een open punt ouder dan mijn venster: komt er nog een antwoord, dan sluit het ook (ontwerptoets 19-10-2026, Codex O4).
    # Een open punt binnen mijn venster dat ik niet meer zie terwijl ik het postvak volledig las, is verplaatst of
    # verwijderd: dan 'verdwenen', zichtbaar bij Afgesloten met Toch open (resultaattoets 19-10-2026, K4, 2-1).
    mijn = {a.lower() for a in cfg["postvakken"]}
    gezien = {a["uniek"] for a in alle}
    for p in oude or []:
        if p.get("uniek") in gezien or (p.get("postvak") or "").lower() not in mijn:
            continue
        if (p.get("datum_iso") or "") >= sinds:
            if (p.get("postvak") or "").lower() in volledig and p.get("soort") in ("hoog", "midden", "actie"):
                alle.append(_rij_van_punt(p, naam, "verdwenen", werkdagen_tussen(_datum({"datum": p["datum_iso"]}) or nu, nu)))
            continue
        try:
            d = datetime.fromisoformat(p["datum_iso"]).astimezone(BRUSSEL)
        except (KeyError, TypeError, ValueError):
            continue
        opvolging, door, wanneer, naar = antwoord({"message_id": p.get("message_id"), "van": p.get("van"),
                                                   "onderwerp": p.get("onderwerp")}, d, index)
        if opvolging == "open" or p.get("soort") not in ("hoog", "midden"):
            continue
        alle.append(_rij_van_punt(p, naam, opvolging, werkdagen_tussen(d, nu), door, wanneer, naar))
    if tel["verzonden_volledig"]:
        for a in rommel_kandidaten(alle, eigen, bekend, veilig):
            a["auto_opruimen"] = "kandidaat"
    items = [a for a in alle if a["opvolging"] in ("open", "onzeker")]
    items.sort(key=lambda a: ({"hoog": 0, "actie": 1, "midden": 2}.get(a["soort"], 9), -a["werkdagen"], a["datum"]))
    tel["open"] = len(items)
    tel["rommel_kandidaten"] = sum(1 for a in alle if a["auto_opruimen"])
    return items, tel, rijen, alle


def _rij_van_punt(p, naam, opvolging, wacht, door="", wanneer="", naar=""):
    """Een rij voor het bord uit een punt dat het bord gaf (/api/mail/open): alleen de opvolging verandert."""
    return {"uniek": p["uniek"], "wacht": naam, "postvak": p["postvak"], "map": p.get("map") or "",
            "datum": p["datum_iso"], "van": p.get("van") or "", "van_naam": p.get("van_naam") or "",
            "onderwerp": p.get("onderwerp") or "", "soort": p["soort"], "waarom": p.get("waarom") or "",
            "mailinglijst": 0, "beantwoord": 1 if opvolging in ("beantwoord", "doorgezet") else 0,
            "message_id": p.get("message_id") or "", "opvolging": opvolging, "antwoord_door": door[:120],
            "antwoord_ts": wanneer, "antwoord_naar": naar[:120], "stap": stap(p["soort"], opvolging, door, wanneer, naar),
            "dringend": 1 if p.get("dringend") else 0, "werkdagen": wacht, "regel": "", "auto_opruimen": ""}


STAP = {"actie": "nakijken en regelen (automatisch bericht, geen antwoord mogelijk)",
        "hoog": "beantwoorden of regelen",
        "midden": "beantwoorden of doorzetten naar wie het opvolgt"}


def _dag(ts):
    try:
        return datetime.fromisoformat(ts).astimezone(BRUSSEL).strftime("%d-%m")
    except (TypeError, ValueError):
        return ""


def stap(soort, opvolging, door="", wanneer="", naar=""):
    """De volgende stap in woorden, zoals Mehdi ze op /mail en in het overzicht van De Mailregisseur leest."""
    if opvolging == "open":
        return STAP.get(soort, "")
    if opvolging == "onzeker":
        wie = door if "@" in door else (door or "iemand")
        return (f"nakijken: {wie} op {_dag(wanneer)} bij dezelfde afzender, hetzelfde onderwerp maar zonder draad; "
                "is het daarmee geregeld, klik Afgehandeld")
    if opvolging == "doorgezet":
        return f"opvolgen bij {naar or 'wie het kreeg'}"
    if opvolging == "wacht":
        return "nog geen werkdag oud; komt op de lijst als er morgen geen antwoord is"
    if opvolging == "verdwenen":
        return "niet meer in de mappen die ik lees (verplaatst of verwijderd); moet het toch opgevolgd worden, klik Toch open"
    return ""


# Rommel naar Opgeruimd (driehoeksoverleg 19-10-2026, 3-0): alleen de soort rommel, met een exacte domeinvergelijking.
# De lijsten bovenaan zoeken op een stuk tekst ("ing.be" zat in valoprojectontwikkeling.be, "law" in Lawrence); voor
# verplaatsen geldt daarom een tweede, strikte toets op het hele domein. Nooit verwijderen; terugzetten kan op /mail.
def zelfde_domein(dom, lijst, beide=False):
    """Is dit domein (exact) een van de lijst, of een subdomein ervan? Nooit een stuk van een woord: valoprojectontwikkeling.be
    is geen ing.be. Met beide=True telt ook het omgekeerde (news.kbc.be tegenover kbc.be): voor wat ik nooit wil raken."""
    dom = (dom or "").lower().strip(".")
    return any(dom == x or dom.endswith("." + x) or (beide and x.endswith("." + dom))
               for x in (y.lower().strip(".") for y in lijst) if x)


def rommel_kandidaten(alle, eigen=(), bekend=frozenset(), veilig=frozenset()):
    """De berichten die de wacht naar Opgeruimd mag zetten: soort rommel volgens de regels (niet omdat Mehdi de afzender
    op ruis zette: ruis is tellen, niet verplaatsen), in INBOX, met een Message-ID, geen regel van Mehdi op de afzender,
    minstens twee rommelberichten van hetzelfde domein in dit venster, en een afzenderdomein dat geen eigen domein en
    geen gratis maildienst is, dat we het laatste half jaar nooit mailden, dat in dit venster geen belangrijk, gewoon of
    actiebericht stuurde, en dat volgens het bord nooit iets belangrijks stuurde of beantwoord werd (`veilig`)."""
    gemaild = {_domein(a) for a in bekend if _domein(a)}
    belangrijk = {_domein(a["van"]) for a in alle if a["soort"] in ("hoog", "midden", "actie")} | set(veilig or ())
    per_domein = {}
    for a in alle:
        if a["soort"] == "rommel":
            per_domein[_domein(a["van"])] = per_domein.get(_domein(a["van"]), 0) + 1
    uit = []
    for a in alle:
        dom = _domein(a["van"])
        if (a["soort"] != "rommel" or a.get("regel") or a.get("map") != "INBOX" or not MSGID.search(a.get("message_id") or "")
                or per_domein.get(dom, 0) < 2
                or not dom or zelfde_domein(dom, eigen, True) or zelfde_domein(dom, GRATIS_DIENSTEN)
                or zelfde_domein(dom, gemaild, True) or zelfde_domein(dom, belangrijk, True)):
            continue
        uit.append(a)
    return uit


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


def droog(naam):
    """Alleen lezen en tonen wat openstaat en wat naar Opgeruimd zou gaan, niets naar het bord en niets verplaatst."""
    nu = datetime.now(BRUSSEL)
    r = _Droog()
    oude, veilig, gelezen = [], frozenset(), False
    try:  # alleen lezen van het bord, zoals de echte ronde
        sys.path.insert(0, HIER)
        import bord  # noqa: E402
        oude = bord.call("/api/mail/open?" + urllib.parse.urlencode({"wacht": naam})).get("punten", [])
        veilig = frozenset(bord.call("/api/mail/veilig").get("domeinen", []))
        gelezen = True
    except Exception as e:  # noqa: BLE001
        print(f"  (bord niet gelezen: {type(e).__name__}; ik toon geen reclame om op te ruimen)")
    items, tel, _, alle = ronde(naam, _DroogAgent(), r, nu, None, oude, veilig)
    if not gelezen:
        for a in alle:
            a["auto_opruimen"] = ""
    print(json.dumps(tel, ensure_ascii=False))
    for a in items:
        print(f"  {a['opvolging']:8} {a['datum'][:10]} ({a['werkdagen']} wd) {a['soort']:6} {a['van'][:40]} · {a['onderwerp'][:70]}"
              f"  [{a['waarom']}]")
    for a in alle:
        if a["opvolging"] in ("beantwoord", "doorgezet"):
            print(f"  {a['opvolging']:8} {a['datum'][:10]} {a['soort']:6} {a['van'][:40]} · {a['onderwerp'][:60]} "
                  f"door {a['antwoord_door']} {a['antwoord_ts'][:16]}")
    for a in alle:
        if a["auto_opruimen"]:
            print(f"  opruimen? {a['datum'][:10]} {a['van'][:45]} · {a['onderwerp'][:70]}")
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


def _sorteren():
    """mailregels/sorteren.py: laad_regels, bestemming, imapnaam. Een bron voor de Mac en de VM."""
    if REGELMAP not in sys.path:
        sys.path.insert(0, REGELMAP)
    import sorteren  # noqa: E402
    return sorteren


def sorteerregels_van(adres):
    """Het regelbestand van dit postvak (mailwachten.json, 'sorteerregels'), of None."""
    try:
        naam = wachten().get("sorteerregels", {}).get(adres.lower())
    except (OSError, ValueError):
        return None
    return os.path.join(REGELMAP, naam) if naam else None


def gmailnaam(mb, mapnaam):
    """INBOX.Bank en verzekering is op Gmail het label 'Bank en verzekering' (een punt wordt een schuine streep)."""
    if "gmail" in (mb.get("imap_host") or "") and mapnaam.startswith("INBOX."):
        return mapnaam[6:].replace(".", "/")
    return mapnaam


def sorteer(mb, regelpad, nu, dagen=SORTEER_DAGEN, doe=True, houden=frozenset()):
    """Past het regelbestand toe op de INBOX, zoals sorteren.py --sinds 3d --nieuwe-reclame --doe op de Mac: de nieuwe
    mail van de laatste dagen, en wat in INBOX ouder is dan een jaar naar het jaararchief. Alleen UID MOVE: niets
    verwijderd, niets als gelezen gemarkeerd. Alleen als de postbus dit postvak laat schrijven.
    doe=False: alleen tonen wat er zou gebeuren (ook zonder schrijfrecht). dagen=None: de hele INBOX (eenmalig opruimen).
    houden: afzenders die Mehdi op /mail terugzette of op Niet opruimen zette; die gaan nooit naar Opgeruimd (19-10-2026).
    Geeft [(message_id, afzender, onderwerp, naar, reden)]."""
    if not mb or mb.get("bron") or (doe and not mb.get("schrijven")) or not regelpad or not os.path.exists(regelpad):
        return []
    s = _sorteren()
    regels = s.laad_regels(regelpad)
    dagen_archief = regels["archief"]["dagen"]
    grens = nu - timedelta(days=dagen_archief) if dagen_archief else None
    _, imapbron = _postbus()
    per_doel, uit = {}, []
    with imapbron._Sessie(mb) as M:
        (imapbron._selecteer_schrijfbaar if doe else imapbron._selecteer)(M, "INBOX")
        sinds = (nu - timedelta(days=dagen)).date().isoformat() if dagen else None
        uids = set(imapbron.zoek_uids(M, imapbron._criteria(None, None, None, None, sinds, None, False)))
        if grens:
            uids |= set(imapbron.zoek_uids(M, imapbron._criteria(None, None, None, None, None, grens.date().isoformat(), False)))
        uids = sorted(uids)
        for i in range(0, len(uids), 200):
            ok, data = M.uid("FETCH", ",".join(str(u) for u in uids[i:i + 200]),
                             "(UID BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE LIST-UNSUBSCRIBE MESSAGE-ID)])")
            for el in data or []:
                if not isinstance(el, tuple):
                    continue
                m = re.search(rb"UID (\d+)", el[0] or b"")
                if not m:
                    continue
                kop = email.message_from_bytes(el[1] or b"")
                naam, adres = parseaddr(imapbron._kop(kop.get("From")))
                try:
                    datum = parsedate_to_datetime(kop.get("Date"))
                    datum = datum if datum.tzinfo else datum.replace(tzinfo=BRUSSEL)
                except Exception:  # noqa: BLE001
                    datum = None
                rij = {"addr": adres.lower(), "name": naam, "subject": imapbron._kop(kop.get("Subject"))[:120],
                       "datum": datum, "unsub": bool(kop.get("List-Unsubscribe"))}
                doel, reden = s.bestemming(rij, regels, True, grens)
                if doel and "opgeruimd" in doel.lower() and any(past(rij["addr"], h) for h in houden):
                    doel = None
                if doel:
                    doel = gmailnaam(mb, doel)
                    per_doel.setdefault(doel, []).append(m.group(1).decode())
                    uit.append((imapbron._kop(kop.get("Message-ID")) or m.group(1).decode(), adres.lower(), rij["subject"], doel, reden))
        if per_doel and doe:
            if "MOVE" not in imapbron.capabilities(M):
                raise ValueError("deze mailserver kan niet verplaatsen (geen MOVE)")
            bestaand = {n.lower() for _, n in imapbron._lijst_mappen(M)}
            for doel, lijst in per_doel.items():
                if doel.lower() not in bestaand:
                    M.create(s.imapnaam(doel))
                    M.subscribe(s.imapnaam(doel))
                for i in range(0, len(lijst), 100):
                    ok, gegevens = M.uid("MOVE", ",".join(lijst[i:i + 100]), s.imapnaam(doel))
                    if ok != "OK":
                        raise ValueError(f"verplaatsen naar {doel} mislukt: " + imapbron._leesbaar(gegevens))
    return uit


def aan_de_beurt(nu=None):
    """Cadans van de mailwachten: elk uur tussen 07:00 en 21:00 Brusselse tijd."""
    nu = nu or datetime.now(BRUSSEL)
    return 7 <= nu.hour < 21


def rommel_echt(nu, cfg=None):
    """Verplaatst de wacht rommel echt, of toont hij alleen wat hij zou verplaatsen? Mailwachten.json, 'rommel_opruimen':
    tot 'echt_vanaf' alleen tonen (de proefweek van 19 tot 26-10-2026), daarna echt."""
    try:
        vanaf = ((cfg or wachten()).get("rommel_opruimen") or {}).get("echt_vanaf") or ""
    except (OSError, ValueError):
        return False
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", vanaf)) and nu.date().isoformat() >= vanaf


def verplaats_op_id(mb, mids, van_map, naar_map):
    """Verplaatst de berichten met deze Message-ID's van van_map naar naar_map (UID MOVE), zoals rommel naar Opgeruimd en
    terug naar INBOX. Elke treffer krijgt eerst een controle op zijn echte Message-ID. Alleen als de postbus dit postvak
    laat schrijven; nooit naar een prullenbak (imapbron weigert dat); niets verwijderd, niets als gelezen gemarkeerd.
    Een Message-ID die niet precies een keer in van_map staat, slaat hij over: nooit gokken (ontwerptoets 19-10-2026,
    Claude O4). Geeft de Message-ID's die verplaatst werden."""
    mids = [m for m in dict.fromkeys(mids) if MSGID.fullmatch((m or "").strip())]
    if not mb or mb.get("bron") or not mb.get("schrijven") or not mids:
        return []
    _, imapbron = _postbus()
    imapbron._bestemming_ok(naar_map)
    gevonden = {}
    with imapbron._Sessie(mb) as M:
        if naar_map.lower() not in [n.lower() for _, n in imapbron._lijst_mappen(M)]:
            M.create(f'"{naar_map}"')
            M.subscribe(f'"{naar_map}"')
        if "MOVE" not in imapbron.capabilities(M):
            raise ValueError("deze mailserver kan niet verplaatsen (geen MOVE)")
        imapbron._selecteer_schrijfbaar(M, van_map)
        for mid in mids:
            uids = imapbron.zoek_uids(M, [b"HEADER", b"Message-ID", imapbron._q(mid.strip())])[:5]
            echt = [uid for uid, (_prefix, ruw) in imapbron._fetch_koppen(M, uids).items()
                    if imapbron._kop(email.message_from_bytes(ruw).get("Message-ID")).strip().lower() == mid.strip().lower()]
            if len(echt) == 1:
                gevonden[mid] = echt
        uids = [u for lijst in gevonden.values() for u in lijst]
        if uids:
            ok, gegevens = M.uid("MOVE", ",".join(str(u) for u in uids), f'"{naar_map}"')
            if ok != "OK":
                raise ValueError(f"verplaatsen naar {naar_map} mislukt: " + imapbron._leesbaar(gegevens))
    return list(gevonden)


def staat_in(mb, mids, mapnaam):
    """Welke van deze Message-ID's staan (alleen lezen) in deze map? Voor de bevestiging van terugzetten: stond het al in
    INBOX, dan is het teruggezet, ook als de melding daarvan de vorige keer niet aankwam (ontwerptoets 19-10-2026, Codex O13)."""
    mids = [m for m in dict.fromkeys(mids) if MSGID.fullmatch((m or "").strip())]
    if not mb or mb.get("bron") or not mids:
        return []
    _, imapbron = _postbus()
    uit = []
    with imapbron._Sessie(mb) as M:
        imapbron._selecteer(M, mapnaam)
        for mid in mids:
            if imapbron.zoek_uids(M, [b"HEADER", b"Message-ID", imapbron._q(mid.strip())]):
                uit.append(mid)
    return uit


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
    # Wat volgens het bord openstaat (ook ouder dan mijn venster) en welke domeinen nooit automatisch opgeruimd worden.
    try:
        oude = bord.call("/api/mail/open?" + urllib.parse.urlencode({"wacht": naam})).get("punten", [])
        veilig = frozenset(bord.call("/api/mail/veilig").get("domeinen", []))
        gelezen_bord = True
    except Exception as e:  # noqa: BLE001
        oude, veilig, gelezen_bord = [], frozenset(), False
        ag.log("bord", "bron", f"/api/mail/open of /api/mail/veilig niet gelezen: {type(e).__name__}: {str(e)[:120]}")
    r.bron("mail-veilig", json.dumps(sorted(veilig)))
    items, tel, rijen, alle = ronde(naam, ag, r, nu, regels, oude, veilig)
    if not gelezen_bord:  # zonder de lijst van het bord weet ik niet welke domeinen veilig zijn: niets opruimen
        for a in alle:
            a["auto_opruimen"] = ""
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
    # De sorteerregels van het postvak (mailregels/regels_<alias>.txt), elke ronde op de nieuwe mail: Mehdi, 26-9-2026:
    # "laat elke door de toepasselijke agent doen en dat we deze ook in de toekomst blijven handhaven".
    verplaatst, gesorteerd = [], []
    for adres in cfg["postvakken"]:
        mb = postvak(adres)
        pad = sorteerregels_van(adres)
        if not pad or not mb or mb.get("bron"):
            continue
        if not mb.get("schrijven"):
            r.nood(f"{adres} heeft sorteerregels, maar de postbus laat dit postvak niet schrijven", wie="mehdi")
            continue
        r.bron(os.path.basename(pad), open(pad, encoding="utf-8").read())
        houden = frozenset(wie for (pv, wie), actie in regels.items() if actie == "houden" and pv in (adres.lower(), "*"))
        try:
            for mid, van, ond, naar, reden in sorteer(mb, pad, nu, houden=houden):
                gesorteerd.append(f"{van} | {ond[:70]} -> {naar} ({reden})")
                verplaatst.append({"uniek": f"{adres}:{mid}", "naar": naar})
        except Exception as e:  # noqa: BLE001
            r.nood(f"Sorteren van {adres} lukte niet", wie="claude-code")
            ag.log("sorteren", "fout", f"{adres}: {type(e).__name__}: {str(e)[:160]}")
    tel["gesorteerd"] = len(gesorteerd)
    if gesorteerd:
        ag.log(f"dag {nu.date().isoformat()}", "sorteren", f"{len(gesorteerd)} berichten uit de INBOX gesorteerd", "\n".join(gesorteerd))
    # Terugzetten: wat Mehdi op /mail uit Opgeruimd terugvroeg, op Message-ID terug naar INBOX.
    teruggezet = []
    try:
        terug = bord.call("/api/mail/terug?" + urllib.parse.urlencode({"wacht": naam})).get("berichten", [])
    except Exception as e:  # noqa: BLE001
        terug = []
        ag.log("terugzetten", "bron", f"/api/mail/terug: {type(e).__name__}: {str(e)[:120]}")
    for adres in cfg["postvakken"]:
        vraag = {t.get("message_id"): t.get("uniek") for t in terug if t.get("postvak") == adres and t.get("message_id")}
        if not vraag:
            continue
        mb = postvak(adres)
        try:
            gedaan = set(verplaats_op_id(mb, list(vraag), opruimmap(mb), "INBOX"))
            gedaan |= set(staat_in(mb, [m for m in vraag if m not in gedaan], "INBOX"))
            teruggezet += [vraag[mid] for mid in gedaan]
        except Exception as e:  # noqa: BLE001
            r.nood(f"Terugzetten naar de inbox van {adres} lukte niet", wie="claude-code")
            ag.log("terugzetten", "fout", f"{adres}: {type(e).__name__}: {str(e)[:160]}")
    tel["teruggezet"] = len(teruggezet)
    # Rommel naar Opgeruimd (19-10-2026): de eerste week alleen tonen, daarna echt (rommel_echt). Wat de sorteerregels deze
    # ronde al verplaatsten, laat ik.
    echt = rommel_echt(nu)
    al_weg = {v["uniek"] for v in verplaatst} | set(opgeruimd)
    kan = {pv["postvak"] for pv in postvakken if pv["schrijven"]}  # hotmail (een bestand van de Mac) kan ik niet opruimen
    kandidaten = [a for a in alle if a["auto_opruimen"] and a["uniek"] not in al_weg and a["postvak"] in kan]
    for a in alle:
        a["auto_opruimen"] = ""
    for a in kandidaten:
        a["auto_opruimen"] = "droog"
    if echt:
        for adres in cfg["postvakken"]:
            deze = {a["message_id"]: a for a in kandidaten if a["postvak"] == adres}
            if not deze:
                continue
            mb = postvak(adres)
            try:
                weg = set(verplaats_op_id(mb, list(deze), "INBOX", opruimmap(mb)))
            except Exception as e:  # noqa: BLE001
                weg = set()
                r.nood(f"Rommel naar Opgeruimd in {adres} lukte niet", wie="claude-code")
                ag.log("rommel", "fout", f"{adres}: {type(e).__name__}: {str(e)[:160]}")
            for mid, a in deze.items():
                a["auto_opruimen"] = "verplaatst" if mid in weg else ""
                if mid in weg:
                    opgeruimd.append(a["uniek"])
        kandidaten = [a for a in kandidaten if a["auto_opruimen"] == "verplaatst"]
    tel["rommel_opruimen"] = len(kandidaten)
    if kandidaten:
        ag.log(f"dag {nu.date().isoformat()}", "rommel",
               f"{len(kandidaten)} reclameberichten {'naar Opgeruimd verplaatst' if echt else 'zou ik naar Opgeruimd zetten (proefweek, niets verplaatst)'}",
               "\n".join(f"{a['postvak']} | {a['van']} | {a['onderwerp'][:80]}" for a in kandidaten))
    # Een bron: het bord bewaart elk bericht met zijn opvolging en geeft terug hoeveel er voor mij openstaat. Dat getal
    # staat in mijn werkverslag, hetzelfde als op /mail en bij De Mailregisseur.
    open_bord = None
    try:
        antw = bord.call("/api/mail", {"wacht": naam, "rijen": alle, "opgeruimd": opgeruimd, "postvakken": postvakken,
                                       "verplaatst": verplaatst, "teruggezet": teruggezet,
                                       "verzonden_volledig": tel["verzonden_volledig"]})
        open_bord = antw.get("open")
    except Exception as e:  # noqa: BLE001
        r.nood("Het maildashboard kreeg de berichten van deze ronde niet", wie="claude-code")
        ag.log("dashboard", "schrijf", f"/api/mail: {type(e).__name__}: {str(e)[:120]}")
    if rijen:
        try:
            bord.call("/api/gesprekken", {"rijen": rijen})
        except Exception as e:  # noqa: BLE001
            ag.log("gesprekken", "schrijf", f"gesprekkentabel niet bijgewerkt: {type(e).__name__}")
    r.detail = (f"laatste 24 u: hoog {tel['hoog']}, gewoon {tel['midden']}, actie {tel['actie']}, meldingen {tel['melding']}, "
                f"koud {tel['koud']}, rommel {tel['rommel']}, verdacht {tel['verdacht']}; op te volgen (zoals op /mail): "
                f"{'onbekend' if open_bord is None else open_bord}; gesorteerd {tel['gesorteerd']}, opgeruimd {tel['opgeruimd']}, "
                f"reclame {'naar Opgeruimd' if echt else 'voor Opgeruimd (proefweek)'} {tel['rommel_opruimen']}, teruggezet {tel['teruggezet']}")
    ag.log(f"dag {nu.date().isoformat()}", "ronde", r.detail,
           "\n".join(f"{a['datum'][:16]} {a['soort']} {a['opvolging']} {a['van']} · {a['onderwerp'][:90]}" for a in items[:80]))

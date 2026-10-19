"""Automatisch uitschrijven via de officiele uitschrijfknop (RFC 8058), voor elke mailwacht.

Beslissing van Mehdi, 20-10-2026: "Uitschrijven mag meteen automatisch, zonder lijst vooraf. Alleen via de officiele
uitschrijfknop, nooit via links in de tekst of mailto, en nooit bij bank, overheid, verzekeraar, notaris of klant. Zet
wel elk uitschrijven in een logboek dat ik op het dashboard zie."

De officiele knop is RFC 8058 one-click: de kop List-Unsubscribe bevat een https-adres en List-Unsubscribe-Post zegt
"List-Unsubscribe=One-Click". Dan, en alleen dan, een POST met precies die tekst. Nooit een GET (dat is geen knop en
bevestigt het adres bij een spammer), nooit mailto (dat is versturen), nooit een link uit de tekst (die lees ik niet
eens: alleen koppen, BODY.PEEK, niets als gelezen gemarkeerd).

Wanneer (ontwerptoets 19/20-10-2026, elke regel heeft een test in tests/test_postvak.py):
  - soort rommel volgens postvak.trieer; koud alleen van een terugkerende verzender (minstens twee berichten met de knop,
    het eerste minstens zeven dagen oud: een nieuwe klant die voor het eerst mailt, valt zo nooit, K4); nooit hoog,
    midden, actie, melding (bestellingen, facturen) of verdacht;
  - geen rol uit postvak.ROLLEN (bank, overheid, verzekering, notaris, boekhouder, advocaat, deurwaarder) in afzender,
    naam of onderwerp, geen dringend woord; een stuk tekst volstaat hier, want te veel uitsluiten is veilig (K2);
  - geen klant: het adres en het domein staan niet in de verzonden post van 180 dagen (bekend) en niet in
    /api/mail/veilig (ooit belangrijk, gewoon, met gevolg, beantwoord of beslist), geen eigen domein, geen gratis
    maildienst, geen regel belangrijk of houden (houden zet /mail bij Niet opruimen en Terugzetten, K3);
  - de knop is van de afzender: de bovenste Authentication-Results komt van onze eigen ontvangende server (one.com of
    mx.google.com, C3) en zegt dkim=pass voor domein D; een DKIM-Signature met d=D dekt list-unsubscribe en
    list-unsubscribe-post (RFC 8058, punt 4); D hoort bij het domein van de afzender en de knop hoort bij D (K1);
  - het adres van de knop is https op poort 443 met een hostnaam; ik zoek die een keer op, elk IP moet publiek zijn, en
    ik verbind met precies dat IP (geen tweede opzoeking, C4, G1, K6): nooit iets op de VM of in het netwerk;
  - een keer per afzender en knop (C5): na een antwoord (aanvaard of geweigerd) nooit meer; een fout zonder antwoord,
    of een poging die stopte tussen POST en logboek, mag na 24 uur opnieuw, hoogstens drie keer (K5);
  - hoogstens per_ronde pogingen per wacht per ronde; geen doorverwijzing gevolgd; tijdslimiet 10 seconden.
Logboek: op het bord (tabel mailuitschrijving, /mail, blok Uitgeschreven), met een vaste gebeurtenis-id zodat opnieuw
sturen nooit dubbel telt (C6), en als grendel in mijnagents-data/mail-uitschrijven.jsonl op de VM; wat het bord nog
niet heeft, stuurt de volgende ronde na. Nooit de URL van de knop: die bevat persoonlijke sleutels; alleen het
hoofddomein van de knop (K8).
"""
import email
import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import urllib.parse
from datetime import datetime, timedelta
from email.utils import parseaddr, parsedate_to_datetime

import postvak

ONE_CLICK = "list-unsubscribe=one-click"
BODY = b"List-Unsubscribe=One-Click"
TIJDSLIMIET = 10            # seconden per POST
PER_RONDE = 5               # pogingen per wacht per ronde
FOUT_OPNIEUW_UUR = 24       # een fout zonder antwoord mag na zoveel uur opnieuw
FOUT_MAX = 3                # hoogstens zoveel pogingen met een fout
KOUD_MIN_BERICHTEN = 2      # koud alleen van een terugkerende verzender ...
KOUD_MIN_DAGEN = 7          # ... die al zo lang mailt
DAGEN = postvak.TERUG_DAGEN
LOG = os.path.join(postvak.DATA, "mail-uitschrijven.jsonl")
KOPPEN = ("(UID BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID LIST-UNSUBSCRIBE LIST-UNSUBSCRIBE-POST "
          "AUTHENTICATION-RESULTS DKIM-SIGNATURE)])")
# Domeinsuffixen van twee delen: dan is het hoofddomein drie delen (bv. bedrijf.co.uk). Kort, want onze afzenders zijn
# vooral .be, .nl, .com; een onbekend geval maakt het hoofddomein langer, nooit korter, en dus strenger.
DUBBEL = {"co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au", "co.nz", "com.br", "co.za", "com.sr",
          "co.jp", "com.tr", "com.mx", "com.cn", "co.in", "com.sg", "com.hk"}


def instellingen(cfg_alles=None):
    """mailwachten.json, 'uitschrijven': {'aan': true, 'per_ronde': 5, 'extra_mappen': [...]}. Ontbreekt het, dan uit."""
    try:
        u = (cfg_alles or postvak.wachten()).get("uitschrijven") or {}
    except (OSError, ValueError):
        u = {}
    return {"aan": u.get("aan") is True, "per_ronde": max(0, min(int(u.get("per_ronde") or PER_RONDE), 20)),
            "extra_mappen": list(u.get("extra_mappen") or ["INBOX.Opgeruimd", "INBOX.Nieuwsbrieven"])}


def hoofddomein(host):
    """Het geregistreerde domein: nieuws.kmoinsider.be -> kmoinsider.be, mail.bedrijf.co.uk -> bedrijf.co.uk."""
    delen = [d for d in (host or "").lower().strip(".").split(".") if d]
    if len(delen) >= 3 and ".".join(delen[-2:]) in DUBBEL:
        return ".".join(delen[-3:])
    return ".".join(delen[-2:])


def knop(list_unsubscribe, list_unsubscribe_post):
    """Het https-adres van de one-click-knop, of None. Alleen als List-Unsubscribe-Post precies one-click zegt."""
    if " ".join((list_unsubscribe_post or "").split()).lower() != ONE_CLICK:
        return None
    for u in re.findall(r"<([^<>]+)>", list_unsubscribe or ""):
        u = "".join(u.split())
        if u.lower().startswith("https://"):
            return u
    return None


def _ip_publiek(waarde):
    try:
        return ipaddress.ip_address(waarde.split("%")[0]).is_global
    except ValueError:
        return False


def adres_ok(url, opzoeken=socket.getaddrinfo):
    """(host, ip, '') als de knop veilig te raken is: https, poort 443, een hostnaam (geen IP), geen gebruiker, en elk IP
    van die host is publiek. Het eerste IP is waarmee ik straks verbind. Anders (host, None, reden)."""
    try:
        p = urllib.parse.urlsplit(url)
        poort = p.port
    except ValueError:
        return "", None, "onleesbaar adres"
    host = (p.hostname or "").lower()
    if p.scheme != "https":
        return host, None, "geen https"
    if not host or "." not in host:
        return host, None, "geen hostnaam"
    if p.username or p.password or "@" in (p.netloc or ""):
        return host, None, "gebruiker in het adres"
    if poort not in (None, 443):
        return host, None, f"poort {poort}"
    try:
        ipaddress.ip_address(host.strip("[]"))
        return host, None, "IP-adres in plaats van een naam"
    except ValueError:
        pass
    try:
        ips = [a[4][0] for a in opzoeken(host, 443, proto=socket.IPPROTO_TCP)]
    except (OSError, UnicodeError):
        return host, None, "host niet gevonden"
    if not ips or not all(_ip_publiek(i) for i in ips):
        return host, None, "host wijst naar een niet-publiek adres"
    return host, ips[0], ""


def _eigen_server(dienst):
    """De authserv-id van onze eigen ontvangende servers: one.com (mx3.cst.mailpod8-cph3.one.com) en Gmail."""
    dienst = (dienst or "").strip().lower()
    return dienst == "mx.google.com" or dienst.endswith(".one.com")


def ondertekend(authentication_results, dkim_signatures):
    """De domeinen D waarvoor de knop ondertekend is: de bovenste Authentication-Results (die zet onze eigen server; een
    afzender kan er alleen onder schrijven) komt van one.com of Gmail en zegt dkim=pass voor D, en een DKIM-Signature met
    d=D dekt in h= list-unsubscribe en list-unsubscribe-post. Leeg als dat niet zo is."""
    if not authentication_results:
        return set()
    boven = " ".join((authentication_results[0] or "").split())
    if not _eigen_server(boven.split(";", 1)[0]):
        return set()
    goed = {m.group(1).lower() for m in re.finditer(r"dkim=pass\b[^;]*?header\.d=([^\s;]+)", boven, re.I)}
    uit = set()
    for s in dkim_signatures or []:
        s = " ".join((s or "").split())
        d = re.search(r"(?:^|;)\s*d=([^;\s]+)", s)
        h = re.search(r"(?:^|;)\s*h=([^;]+)", s)
        if d and h and d.group(1).lower() in goed:
            velden = {x.strip().lower() for x in h.group(1).split(":")}
            if {"list-unsubscribe", "list-unsubscribe-post"} <= velden:
                uit.add(d.group(1).lower())
    return uit


def rol_of_dringend(van, naam, onderwerp):
    """Een rol uit postvak.ROLLEN of een dringend woord: dan nooit uitschrijven. Een stuk tekst volstaat hier."""
    tekst = f"{van} {naam} {onderwerp}".lower()
    rol = next((r for r, delen in postvak.ROLLEN.items() if any(d in tekst for d in delen)), "")
    if rol:
        return f"rol {rol}"
    if postvak.DRINGEND.search(onderwerp or ""):
        return "dringend"
    return ""


def terugkerend(berichten_van, nu):
    """Een terugkerende verzender: minstens KOUD_MIN_BERICHTEN berichten met de knop, het eerste KOUD_MIN_DAGEN oud."""
    data = [b["datum"] for b in berichten_van if b.get("datum")]
    return len(data) >= KOUD_MIN_BERICHTEN and min(data) <= nu - timedelta(days=KOUD_MIN_DAGEN)


def beoordeel(b, soort, regel, eigen, bekend, veilig, terugkerende=False):
    """(url, '') als dit bericht mag leiden tot uitschrijven, anders (None, reden)."""
    van = (b.get("van") or "").lower()
    dom = postvak._domein(van)
    if soort == "koud" and not terugkerende:
        return None, "koud en geen terugkerende verzender"
    if soort not in ("rommel", "koud"):
        return None, f"soort {soort}"
    if regel in ("belangrijk", "houden"):
        return None, f"regel {regel} van Mehdi"
    reden = rol_of_dringend(van, b.get("van_naam") or "", b.get("onderwerp") or "")
    if reden:
        return None, reden
    if not dom or postvak.zelfde_domein(dom, eigen, True):
        return None, "eigen domein"
    if postvak.zelfde_domein(dom, postvak.GRATIS_DIENSTEN):
        return None, "gratis maildienst"
    gemaild = {postvak._domein(a) for a in bekend if postvak._domein(a)}
    if van in bekend or postvak.zelfde_domein(dom, gemaild, True):
        return None, "klant: we mailden dit adres of domein"
    if postvak.zelfde_domein(dom, veilig, True):
        return None, "klant: ooit belangrijk, gewoon, met gevolg of beantwoord"
    url = knop(b.get("list_unsubscribe"), b.get("list_unsubscribe_post"))
    if not url:
        return None, "geen one-click-knop"
    domeinen = ondertekend(b.get("authentication_results"), b.get("dkim_signatures"))
    if not domeinen:
        return None, "knop niet ondertekend"
    knophost = (urllib.parse.urlsplit(url).hostname or "").lower()
    if not any(hoofddomein(d) == hoofddomein(dom) and hoofddomein(knophost) == hoofddomein(d) for d in domeinen):
        return None, "handtekening of knop hoort niet bij de afzender"
    return url, ""


def gebeurtenis(wacht, van, knophost, ts):
    """Een vaste id per poging: hetzelfde logboek opnieuw naar het bord sturen telt nooit dubbel (C6)."""
    return hashlib.sha256(f"{wacht}|{van}|{knophost}|{ts}".encode()).hexdigest()[:24]


def lees_log(pad=LOG):
    """Het lokale logboek. None als het bestaat maar onleesbaar is: dan doe ik deze ronde niets (K5)."""
    if not os.path.exists(pad):
        return []
    try:
        with open(pad, encoding="utf-8") as f:
            return [json.loads(r) for r in f if r.strip()]
    except (OSError, ValueError):
        return None


def schrijf_log(regel, pad=LOG):
    os.makedirs(os.path.dirname(pad), exist_ok=True)
    with open(pad, "a", encoding="utf-8") as f:
        f.write(json.dumps(regel, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def sleutel(van, knop_domein):
    return f"{(van or '').lower()}|{(knop_domein or '').lower()}"


def staat_per_sleutel(regels):
    """{afzender|knopdomein: {'antwoord': bool, 'pogingen': n, 'laatste': ts}} uit het lokale logboek en dat van het bord.
    antwoord: aanvaard, geweigerd of overgeslagen (nooit meer). pogingen: fouten zonder antwoord, en een 'bezig' zonder
    latere uitslag (de wacht stopte tussen POST en logboek) telt ook als fout (K5)."""
    per = {}
    for x in regels:
        if x.get("van"):
            per.setdefault(sleutel(x.get("van"), x.get("knop_domein")), {})[x.get("gebeurtenis") or id(x)] = x
    uit = {}
    for k, gebeurtenissen in per.items():
        antwoord, fouten, laatste = False, 0, ""
        for g in {}.fromkeys(gebeurtenissen):
            rs = [x for x in regels if (x.get("gebeurtenis") or id(x)) == g]
            uitslagen = {x.get("uitslag") for x in rs}
            if uitslagen & {"aanvaard", "geweigerd", "overgeslagen"}:
                antwoord = True
            elif uitslagen & {"fout", "bezig"}:
                fouten += 1
            laatste = max([laatste] + [x.get("ts") or "" for x in rs])
        uit[k] = {"antwoord": antwoord, "pogingen": fouten, "laatste": laatste}
    return uit


def mag_poging(van, knop_domein, staat, nu):
    s = staat.get(sleutel(van, knop_domein))
    if not s:
        return True
    if s["antwoord"] or s["pogingen"] >= FOUT_MAX:
        return False
    try:
        laatste = datetime.fromisoformat(s["laatste"])
    except ValueError:
        return False
    return nu - laatste >= timedelta(hours=FOUT_OPNIEUW_UUR)


class _VastIP(http.client.HTTPSConnection):
    """Verbind met het IP dat ik al controleerde (geen tweede DNS-opzoeking), met de hostnaam voor SNI, het certificaat
    en de Host-kop. Zo kan een naam die intussen naar de VM wijst, niets raken."""

    def __init__(self, host, ip, timeout):
        super().__init__(host, 443, timeout=timeout, context=ssl.create_default_context())
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, 443), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def post(url, ip, verbinding=_VastIP):
    """De POST van RFC 8058 naar precies dat adres, via het gecontroleerde IP. Geen cookies, geen aanmelding, geen
    doorverwijzing (http.client volgt er nooit een). Geeft (uitslag, code): aanvaard (2xx), geweigerd (3xx, 4xx, 5xx)
    of fout (geen antwoord: time-out, TLS, verbinding)."""
    p = urllib.parse.urlsplit(url)
    pad = (p.path or "/") + (("?" + p.query) if p.query else "")
    try:
        c = verbinding(p.hostname, ip, TIJDSLIMIET)
        try:
            c.request("POST", pad, body=BODY, headers={"Content-Type": "application/x-www-form-urlencoded",
                                                         "User-Agent": "mijnagents-uitschrijven/1.0 (RFC 8058 one-click)"})
            antw = c.getresponse()
            code = antw.status
            antw.read(4096)
        finally:
            c.close()
    except Exception:  # noqa: BLE001
        return "fout", 0
    return ("aanvaard" if 200 <= code < 300 else "geweigerd"), code


def _datum(kop):
    try:
        d = parsedate_to_datetime(kop)
        return d if d.tzinfo else d.replace(tzinfo=postvak.BRUSSEL)
    except (TypeError, ValueError):
        return None


def koppen_lezen(mb, mappen, sinds):
    """Alleen lezen: per map de koppen van de berichten sinds `sinds` met een kop List-Unsubscribe-Post. BODY.PEEK, dus
    niets wordt als gelezen gemarkeerd."""
    _, imapbron = postvak._postbus()
    uit = []
    with imapbron._Sessie(mb) as M:
        bestaand = {n.lower() for _, n in imapbron._lijst_mappen(M)}
        for m in dict.fromkeys(mappen):
            if m.lower() not in bestaand:
                continue
            imapbron._selecteer(M, m)
            uids = imapbron.zoek_uids(M, imapbron._criteria(None, None, None, None, sinds, None, False))
            for i in range(0, len(uids), 200):
                ok, data = M.uid("FETCH", ",".join(str(u) for u in uids[i:i + 200]), KOPPEN)
                for el in data or []:
                    if not isinstance(el, tuple):
                        continue
                    k = email.message_from_bytes(el[1] or b"")
                    if not k.get("List-Unsubscribe-Post"):
                        continue
                    naam, van = parseaddr(imapbron._kop(k.get("From")))
                    uit.append({"map": m, "van": van.lower(), "van_naam": naam, "onderwerp": imapbron._kop(k.get("Subject")),
                                "message_id": imapbron._kop(k.get("Message-ID")), "datum": _datum(k.get("Date")),
                                "list_unsubscribe": k.get("List-Unsubscribe") or "",
                                "list_unsubscribe_post": k.get("List-Unsubscribe-Post") or "",
                                "authentication_results": [str(x) for x in (k.get_all("Authentication-Results") or [])],
                                "dkim_signatures": [str(x) for x in (k.get_all("DKIM-Signature") or [])]})
    return uit


def mappen_voor(adres, mb, inst):
    """De gewone mappen van de wacht, plus de mappen waar de sortering reclame zet (mailwachten.json, uitschrijven.
    extra_mappen; bij Gmail als label). Die lees ik alleen hiervoor, niet voor de opvolging (C1, G2, K3)."""
    return list(dict.fromkeys(postvak.mappen_van(adres) + [postvak.gmailnaam(mb, m) if m.startswith("INBOX.") else m
                                                          for m in inst["extra_mappen"]]))


def kandidaten(cfg, nu, bekend, veilig, regels, staat, lezen=koppen_lezen, inst=None):
    """Lezen en beoordelen, zonder iets te doen. Geeft ({sleutel: (bericht, url, postvak)}, {reden: aantal})."""
    inst = inst or instellingen()
    eigen = tuple(cfg.get("eigen_domeinen") or ())
    sinds = (nu - timedelta(days=DAGEN)).date().isoformat()
    uit, redenen = {}, {}

    def tel(reden):
        redenen[reden] = redenen.get(reden, 0) + 1

    for adres in cfg["postvakken"]:
        mb = postvak.postvak(adres)
        if not mb or mb.get("bron"):
            tel("postvak zonder uitschrijfkoppen (hotmail van de Mac)")
            continue
        berichten = lezen(mb, mappen_voor(adres, mb, inst), sinds)
        per_van = {}
        for b in berichten:
            per_van.setdefault(b["van"], []).append(b)
        for b in berichten:
            regel = postvak.regel_voor(regels, adres, b["van"])
            soort, _waarom = postvak.trieer(b, eigen, bekend, regel)
            url, reden = beoordeel(b, soort, regel, eigen, bekend, veilig, terugkerend(per_van[b["van"]], nu))
            if not url:
                tel(reden)
                continue
            k = sleutel(b["van"], hoofddomein(urllib.parse.urlsplit(url).hostname))
            if not mag_poging(b["van"], hoofddomein(urllib.parse.urlsplit(url).hostname), staat, nu):
                tel("al eens geprobeerd")
                continue
            oud = uit.get(k)
            if not oud or (b["datum"] and oud[0]["datum"] and b["datum"] > oud[0]["datum"]):
                uit[k] = (b, url, adres)
    return uit, redenen


def ronde(naam, cfg, ag, r, nu, bekend, veilig, regels, klaar_voor, bord, lezen=koppen_lezen, posten=post,
          opzoeken=socket.getaddrinfo, logpad=LOG):
    """Een ronde uitschrijven voor wacht `naam`. `klaar_voor` is False als de verzonden post of de lijst van het bord
    niet volledig gelezen is: dan niets. Geeft de logregels van deze ronde (zonder URL)."""
    inst = instellingen()
    if not inst["aan"]:
        return []
    if not klaar_voor:
        ag.log("uitschrijven", "bron", "niet volledig gelezen (verzonden post of het bord): deze ronde schrijf ik niemand uit")
        return []
    lokaal = lees_log(logpad)
    if lokaal is None:
        r.nood("Het logboek uitschrijven op de VM is onleesbaar: uitschrijven staat stil", wie="claude-code")
        return []
    try:
        van_bord = bord.call("/api/mail/uitschrijvingen?" + urllib.parse.urlencode({"n": 20000})).get("uitschrijvingen", [])
    except Exception as e:  # noqa: BLE001
        ag.log("uitschrijven", "bron", f"logboek van het bord niet gelezen: {type(e).__name__}; deze ronde niets")
        return []
    # Wat lokaal staat maar nog niet op het bord (het bord was onbereikbaar), stuur ik na; de id voorkomt dubbels.
    op_bord = {x.get("gebeurtenis") for x in van_bord}
    na = [x for x in lokaal if x.get("uitslag") in ("aanvaard", "geweigerd", "fout", "overgeslagen")
          and x.get("gebeurtenis") and x.get("gebeurtenis") not in op_bord and x.get("wacht") == naam]
    staat = staat_per_sleutel(lokaal + van_bord)
    try:
        kand, redenen = kandidaten(cfg, nu, bekend, veilig, regels, staat, lezen, inst)
    except Exception as e:  # noqa: BLE001
        r.nood("Uitschrijfkoppen niet leesbaar", wie="claude-code")
        ag.log("uitschrijven", "bron", f"{type(e).__name__}: {str(e)[:160]}")
        return []
    gedaan = []
    volgorde = sorted(kand.values(), key=lambda x: x[0]["datum"] or nu, reverse=True)
    for b, url, adres in volgorde[:inst["per_ronde"]]:
        host, ip, reden = adres_ok(url, opzoeken)
        start = datetime.now(postvak.BRUSSEL).isoformat()
        regel = {"gebeurtenis": gebeurtenis(naam, b["van"], host, start), "ts": start, "wacht": naam, "postvak": adres,
                 "van": b["van"], "onderwerp": (b["onderwerp"] or "")[:200], "map": b["map"],
                 "message_id": (b["message_id"] or "")[:250], "datum": b["datum"].isoformat() if b["datum"] else "",
                 "knop_domein": hoofddomein(host)}
        if not ip:
            regel.update(uitslag="overgeslagen", code=0, reden=reden)
        else:
            schrijf_log(dict(regel, uitslag="bezig", code=0, reden=""), logpad)
            uitslag, code = posten(url, ip)
            regel.update(uitslag=uitslag, code=code, reden="")
            regel["ts"] = datetime.now(postvak.BRUSSEL).isoformat()
        schrijf_log(regel, logpad)
        gedaan.append(regel)
    if gedaan or na:
        try:
            bord.call("/api/mail/uitschrijving", {"wacht": naam, "regels": na + gedaan})
        except Exception as e:  # noqa: BLE001
            r.nood("Het logboek uitschrijven kwam niet op het bord", wie="claude-code")
            ag.log("uitschrijven", "schrijf", f"/api/mail/uitschrijving: {type(e).__name__}: {str(e)[:120]}")
    if gedaan or kand:
        ag.log(f"dag {nu.date().isoformat()}", "uitschrijven",
               f"{len(gedaan)} uitschrijvingen ({', '.join(sorted({g['uitslag'] for g in gedaan})) or 'geen'}), "
               f"nog {max(0, len(kand) - len(gedaan))} voor een volgende ronde",
               "\n".join(f"{g['postvak']} | {g['van']} | {g['knop_domein']} | {g['uitslag']} {g['code'] or ''}" for g in gedaan)
               + "\nniet uitgeschreven: " + ", ".join(f"{k} {v}" for k, v in sorted(redenen.items())))
    return gedaan


def droog(naam):
    """Tonen wie de wacht zou uitschrijven en waarom anderen niet, zonder POST, zonder logboek (alleen lezen)."""
    import sys
    sys.path.insert(0, postvak.HIER)
    import bord  # noqa: E402
    nu = datetime.now(postvak.BRUSSEL)
    cfg = postvak.wachten()[naam]
    lijst = bord.call("/api/mailregels").get("regels", [])
    regels = {((x.get("postvak") or "*").lower(), (x.get("wie") or "").lower()): x.get("actie") for x in lijst}
    veilig = frozenset(bord.call("/api/mail/veilig").get("domeinen", []))
    r = postvak._Droog()
    _, tel, _, _ = postvak.ronde(naam, postvak._DroogAgent(), r, nu, regels, [], veilig)
    lokaal = lees_log() or []
    try:
        van_bord = bord.call("/api/mail/uitschrijvingen?n=20000").get("uitschrijvingen", [])
    except Exception as e:  # noqa: BLE001
        print(f"  (logboek van het bord niet gelezen: {type(e).__name__})")
        van_bord = []
    kand, redenen = kandidaten(cfg, nu, tel["_bekend"], veilig, regels, staat_per_sleutel(lokaal + van_bord))
    print(f"{naam}: verzonden volledig {tel['verzonden_volledig']}; {len(kand)} zou ik uitschrijven "
          f"(hoogstens {instellingen()['per_ronde']} per ronde)")
    for b, url, adres in sorted(kand.values(), key=lambda x: x[0]["datum"] or nu, reverse=True):
        print(f"  uitschrijven? {adres} | {b['van']} | {hoofddomein(urllib.parse.urlsplit(url).hostname)} | {(b['onderwerp'] or '')[:70]}")
    print("  niet: " + ", ".join(f"{k} {v}" for k, v in sorted(redenen.items())))
    return kand, redenen


if __name__ == "__main__":
    # uitschrijven.py mail-mch   toont wie de wacht zou uitschrijven en waarom anderen niet; doet niets
    import sys
    droog(sys.argv[1] if len(sys.argv) > 1 else "mail-mch")

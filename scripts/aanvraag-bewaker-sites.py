#!/usr/bin/env python3
"""Bewaakt de aanvragen van ALLE eigen websites, niet alleen die van UNABO.

WAAROM DIT BESTAAT
Tussen 30 sep en 19 okt 2026 raakten vijf UNABO-aanvragen nooit bij sales. De
oude bewaker (aanvraag-bewaker.py) zag ze wel, maar meldde dat elke zes uur in
een privébericht dat niemand las. Bij Stychin Tyme mislukte elke boeking omdat
/api/book nooit bestaan heeft, en epb-boete.be mailde naar de verkeerde firma.
Siyan: "dit mag niet gebeuren, nooit meer".

Dus: één bewaker over alle innamepunten, en een melding die opvalt:
  - in het Zoom-kanaal "Binnengekomen leads-Automation" (3-CPO is lid), en
  - per mail aan de firma waar de aanvraag bij hoort, met Siyan in kopie.

WAT ER GECONTROLEERD WORDT
  1. De wachtrij aanvragen.db (UNABO en TKN): status vast, te lang op wacht,
     verwerkt zonder meldingsmail.
  2. De tabel `lead` van agents.globaal.be (epb-boete, regulariseren,
     mijnregularisatie, stychintyme): een aanvraag die lead-melding.py na een
     half uur nog niet mailde.
  3. De jsonl-bestanden van de sites die zelf bewaren en mailen (Energie
     Efficiënt, Harmoniebouw, H-Architects-proef, HDS): mailfouten in de
     containerlog, en voor HDS de uitkomstregel per aanvraag.
  4. De jsonl van UNABO en TKN tegenover de wachtrij: staat iets op de site
     maar nooit in de wachtrij, dan is de doorgifte stuk.
  5. Of de formulieren en de centrale inname nog antwoorden.

Cron (elke tien minuten):
  */10 * * * * /usr/bin/flock -n /tmp/aanvraag-bewaker-sites.lock /usr/bin/python3 \
      /home/ubuntu/appportal/scripts/aanvraag-bewaker-sites.py >> /home/ubuntu/aanvraag-bewaker-sites.log 2>&1

Droogdraaien (toont het oordeel, meldt niets en onthoudt niets):
  /usr/bin/python3 ~/appportal/scripts/aanvraag-bewaker-sites.py --droog
"""
import json
import os
import re
import smtplib
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

import yaml

THUIS = os.path.expanduser("~")
STAND = f"{THUIS}/appportal/aanvraag-data/bewaker-sites.state"
WACHTRIJ = f"{THUIS}/appportal/aanvraag-data/aanvragen.db"
AGENTS_DB = f"{THUIS}/appportal/agents-data/agents.db"
LEAD_MELDING_STAND = f"{THUIS}/appportal/agents-data/lead-melding.state"
MAILBOXEN = f"{THUIS}/post-config/mailboxen.yaml"
ZOOM_ENV = f"{THUIS}/pipedrive-won-deals/.env"
ZOOM_KANAAL_SCRIPT = f"{THUIS}/zoom-dossier/scripts/zoom_kanaal.mjs"
KANAAL = "Binnengekomen leads-Automation"
AFZENDER = "standaard@h-architects.be"
SIYAN = "sls.siyan@globaal.be"

GEDULD = 30 * 60               # na een half uur zonder verwerking of mail: alarm
HERHAAL_NA = 3 * 3600          # zelfde probleem hoogstens om de drie uur opnieuw
# Aanvragen van vóór deze bewaker zijn al nagekeken (rapport 27-28 okt 2026); die
# laten we buiten beschouwing, anders blijft het alarm eeuwig afgaan.
VANAF = "2026-10-28T00:00:00+00:00"

# Waar een melding over een firma heen moet, naast het Zoom-kanaal.
FIRMA_MAIL = {
    "UNABO": "sales@unabo.be",
    "TKN-Buro": "offerte@tkn-buro.be",
    "Energie Efficiënt": "offerte@energie-efficient.be",
    "Harmoniebouw": "offerte@harmoniebouw.be",
    "H-Architects": "info@h-architects.be",
    "High Design Studio": "info@hdssr.com",
    "Regulariseren.be": "info@regulariseren.be",
    "Mijnregularisatie.be": "info@mijnregularisatie.be",
    "Stychin Tyme": "info@elevaitservices.com",
}
BRON_FIRMA = {"unabo-site": "UNABO", "wpforms": "UNABO", "tkn-site": "TKN-Buro"}
LEAD_SITE_FIRMA = {
    "epbboete": "Energie Efficiënt", "regulariseren": "Regulariseren.be",
    "mijnregularisatie": "Mijnregularisatie.be", "stychintyme": "Stychin Tyme",
}

# Sites die zelf bewaren (jsonl in de container) en zelf mailen.
#   uitkomst=True: de site schrijft per aanvraag een tweede regel {id, mail}.
#   wachtrij=bron: de site zet door naar aanvragen.db; dan vergelijken we.
JSONL_SITES = [
    {"firma": "UNABO", "container": "unabo-web", "pad": "/data/aanvragen.jsonl", "wachtrij": "unabo-site"},
    {"firma": "TKN-Buro", "container": "tkn-web", "pad": "/data/aanvragen.jsonl", "wachtrij": "tkn-site"},
    {"firma": "Energie Efficiënt", "container": "ee-site-web", "pad": "/data/leads.jsonl"},
    {"firma": "Harmoniebouw", "container": "harmoniebouw-web", "pad": "/data/aanvragen.jsonl"},
    {"firma": "H-Architects", "container": "harchitects-web", "pad": "/data/leads.jsonl"},
    {"firma": "High Design Studio", "container": "hdssr-web", "pad": "/data/aanvragen.jsonl", "uitkomst": True},
]
# Woorden waarmee de sites een mislukte mail of opslag in hun log schrijven.
LOGFOUT = re.compile(r"(mislukt|niet verstuurd|SMTP niet|EAUTH|ECONNREFUSED|ETIMEDOUT|Invalid login)", re.I)

# Formulieren en de centrale inname: antwoorden ze nog?
CONTROLES = [
    ("UNABO", "GET", "https://unabo.be/contacteer-ons/", (200,)),
    ("TKN-Buro", "GET", "https://tkn-buro.be/contact/", (200,)),
    ("Energie Efficiënt", "GET", "https://energie-efficient.be/contact/", (200,)),
    ("Harmoniebouw", "GET", "https://harmoniebouw.be/contact/", (200,)),
    ("High Design Studio", "GET", "https://hdssr.com/contact", (200,)),
    ("Stychin Tyme", "GET", "https://stychintyme.com/book/", (200,)),
    ("Energie Efficiënt", "OPTIONS", "https://agents.globaal.be/website-aanvraag", (200, 204)),
]


def nu():
    return datetime.now(timezone.utc)


def tijd(t):
    if not t:
        return None
    try:
        d = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def ouder_dan(t, sec):
    d = tijd(t)
    return bool(d) and (nu() - d).total_seconds() > sec


def t_van(a):
    """Tijdstip van een jsonl-regel: UNABO schrijft 'tijdstip', de andere sites 'ontvangen'."""
    return a.get("tijdstip") or a.get("ontvangen")


def na_vanaf(t):
    d = tijd(t)
    return bool(d) and d >= tijd(VANAF)


# ---------- de innamepunten uitlezen ----------

def wachtrij():
    """Alle rijen, ook de bewust stopgezette: die tellen wel als 'aangekomen'."""
    conn = sqlite3.connect(WACHTRIJ, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM aanvraag ORDER BY id")]
    finally:
        conn.close()


def jsonl(container, pad):
    """Regels uit het aanvraagbestand in de container, of None als dat niet lukt."""
    try:
        uit = subprocess.run(["/usr/bin/docker", "exec", container, "cat", pad],
                             timeout=30, capture_output=True, text=True)
    except Exception:  # noqa: BLE001
        return None
    if uit.returncode != 0:
        # Nog geen enkele aanvraag = nog geen bestand; dat is geen storing.
        return [] if "No such file" in (uit.stderr or "") else None
    rijen = []
    for regel in uit.stdout.splitlines():
        try:
            rijen.append(json.loads(regel))
        except ValueError:
            pass
    return rijen


def logfouten(container, sinds_sec):
    try:
        uit = subprocess.run(["/usr/bin/docker", "logs", "--since", f"{int(sinds_sec)}s", container],
                             timeout=30, capture_output=True, text=True)
    except Exception:  # noqa: BLE001
        return []
    return [r for r in (uit.stdout + uit.stderr).splitlines() if LOGFOUT.search(r)][:5]


# ---------- het onderzoek ----------

def bevindingen(vorige_ronde_sec):
    """Lijst van (sleutel, firma, tekst). Leeg = alles in orde."""
    uit = []

    # 1. Wachtrij UNABO/TKN
    try:
        rijen = wachtrij()
    except Exception as e:  # noqa: BLE001
        rijen = None
        uit.append(("wachtrij-weg", "UNABO", f"De wachtrij {WACHTRIJ} is niet leesbaar: {e}"))
    for r in rijen or []:
        if not na_vanaf(r["ontvangen"]) or r["status"] in ("afgebroken", "overgeslagen"):
            continue
        firma = BRON_FIRMA.get(r["bron"], "UNABO")
        if r["status"] == "vast":
            uit.append((f"wachtrij-vast-{r['id']}", firma,
                        f"Aanvraag #{r['id']} ({r['bron']}) is vastgelopen en staat NIET in Pipedrive. "
                        f"Fout: {(r.get('laatste_fout') or '')[:160]}"))
        elif r["status"] == "wacht" and ouder_dan(r["ontvangen"], GEDULD):
            uit.append((f"wachtrij-wacht-{r['id']}", firma,
                        f"Aanvraag #{r['id']} ({r['bron']}) staat al meer dan een half uur onverwerkt. "
                        f"Laatste fout: {(r.get('laatste_fout') or 'geen')[:160]}"))
        elif r["status"] == "klaar" and not r.get("mail_verstuurd") and ouder_dan(r["verwerkt"], GEDULD):
            uit.append((f"wachtrij-mail-{r['id']}", firma,
                        f"Aanvraag #{r['id']} staat in Pipedrive (deal {r['deal_id']}) maar sales kreeg geen mail."))

    # 2. Centrale inname (tabel lead) tegenover lead-melding.py
    try:
        gemeld = int(open(LEAD_MELDING_STAND).read().strip() or 0)
        conn = sqlite3.connect(AGENTS_DB, timeout=30)
        conn.row_factory = sqlite3.Row
        open_leads = [dict(r) for r in conn.execute(
            "SELECT id, site, ontvangen FROM lead WHERE id > ? ORDER BY id", (gemeld,))]
        conn.close()
        for l in open_leads:
            if na_vanaf(l["ontvangen"]) and ouder_dan(l["ontvangen"], GEDULD):
                firma = LEAD_SITE_FIRMA.get(l["site"] or "", "H-Architects")
                uit.append((f"lead-mail-{l['id']}", firma,
                            f"Aanvraag {l['id']} via {l['site'] or 'onbekende site'} is bewaard maar na een "
                            "half uur nog niet gemaild. Kijk in ~/lead-melding.log."))
    except Exception as e:  # noqa: BLE001
        uit.append(("lead-weg", "H-Architects", f"De centrale inname is niet te controleren: {e}"))

    # 3 en 4. Sites met een eigen jsonl
    in_rij = {}
    for r in rijen or []:
        try:
            in_rij.setdefault(r["bron"], set()).add(json.loads(r["payload"]).get("tijdstip"))
        except (ValueError, TypeError):
            pass
    for s in JSONL_SITES:
        regels = jsonl(s["container"], s["pad"])
        if regels is None:
            uit.append((f"jsonl-weg-{s['container']}", s["firma"],
                        f"Het aanvraagbestand van {s['container']} is niet leesbaar. "
                        "Draait de site nog, en worden aanvragen nog bewaard?"))
            continue
        if s.get("wachtrij") and rijen is not None:
            bekend = in_rij.get(s["wachtrij"], set())
            kwijt = [a for a in regels if na_vanaf(t_van(a)) and t_van(a) not in bekend
                     and ouder_dan(t_van(a), GEDULD)]
            if kwijt:
                uit.append((f"doorgifte-{s['container']}", s["firma"],
                            f"{len(kwijt)} aanvraag/aanvragen staan op de website maar kwamen nooit in de "
                            f"wachtrij (oudste {t_van(kwijt[0])}). Ze staan dus NIET in Pipedrive."))
        # H-Architects schrijft zelf of de mail vertrok.
        for a in regels:
            if a.get("gemaild") is False and na_vanaf(t_van(a)):
                uit.append((f"gemaild-{s['container']}-{t_van(a)}", s["firma"],
                            f"Aanvraag van {str(t_van(a))[:16]} op {s['container']} is bewaard maar niet gemaild."))
        if s.get("uitkomst"):
            uitkomst = {a["id"]: a.get("mail") for a in regels if a.get("id") and "tijdstip" not in a}
            for a in regels:
                if "tijdstip" not in a or not na_vanaf(a["tijdstip"]):
                    continue
                stand = uitkomst.get(a.get("id"))
                if stand == "mislukt" or (stand is None and ouder_dan(a["tijdstip"], GEDULD)):
                    uit.append((f"mail-{s['container']}-{a.get('id')}", s["firma"],
                                f"Aanvraag van {a['tijdstip'][:16]} op {s['container']} is bewaard maar "
                                f"{'de mail mislukte' if stand else 'er vertrok geen mail'}. "
                                f"De gegevens staan in {s['pad']} in de container."))
        fouten = logfouten(s["container"], vorige_ronde_sec)
        if fouten:
            uit.append((f"log-{s['container']}", s["firma"],
                        f"{s['container']} meldt een fout bij een aanvraag: {fouten[0][:200]}"))

    # 5. Antwoorden de formulieren nog?
    def status_van(methode, url):
        try:
            req = urllib.request.Request(url, method=methode, headers={"User-Agent": "aanvraag-bewaker"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception as e:  # noqa: BLE001
            return type(e).__name__

    for firma, methode, url, goed in CONTROLES:
        status = status_van(methode, url)
        if status not in goed:
            # Een uitrol herstart de container even (502): pas alarm als het na
            # een halve minuut nog steeds mis is.
            time.sleep(30)
            status = status_van(methode, url)
        if status not in goed:
            uit.append((f"site-{url}", firma, f"{url} antwoordt met {status}: het formulier is niet bereikbaar."))

    return uit


# ---------- melden ----------

def zoom_kanaal(tekst):
    env = dict(os.environ)
    try:
        for regel in open(ZOOM_ENV):
            if regel.startswith("ZOOM_") and "=" in regel:
                k, v = regel.strip().split("=", 1)
                env[k] = v.strip().strip('"').strip("'")
        subprocess.run(["/usr/bin/node", ZOOM_KANAAL_SCRIPT, KANAAL, tekst], env=env,
                       check=True, timeout=60, capture_output=True, text=True)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"Zoom-melding mislukt: {e}")
        return False


def mailbox(adres):
    cfg = yaml.safe_load(open(MAILBOXEN)) or {}
    std = cfg.get("standaard") or {}
    for mb in cfg.get("mailboxen") or []:
        if (mb.get("adres") or "").lower() == adres.lower():
            return {"adres": mb["adres"], "gebruiker": mb.get("gebruiker") or mb["adres"],
                    "wachtwoord": mb.get("wachtwoord") or "",
                    "host": mb.get("smtp_host") or std.get("smtp_host"),
                    "poort": int(mb.get("smtp_poort") or std.get("smtp_poort") or 465)}
    raise RuntimeError(f"afzender {adres} niet in {MAILBOXEN}")


def mail(naar, onderwerp, tekst):
    afz = mailbox(AFZENDER)
    b = EmailMessage()
    b["From"] = f"Aanvraagbewaker <{afz['adres']}>"
    b["To"] = naar
    b["Cc"] = SIYAN
    b["Subject"] = onderwerp
    b["Date"] = formatdate(localtime=True)
    b["Message-ID"] = make_msgid()
    b.set_content(tekst)
    rijen = "".join(
        f'<tr><td style="padding:14px 0;border-bottom:1px solid #e5e5e5;font:400 15px/1.5 Arial,sans-serif;'
        f'color:#222;white-space:pre-wrap;">{regel.replace("&", "&amp;").replace("<", "&lt;")}</td></tr>'
        for regel in tekst.split("\n\n") if regel.strip())
    b.add_alternative(
        '<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;background:#f2f2f2;">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#f2f2f2;padding:24px 0;"><tr><td align="center">'
        '<table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:10px;padding:8px 28px 20px;">'
        f'<tr><td style="padding:18px 0 6px;font:700 18px/1.3 Arial,sans-serif;color:#b42318;">{onderwerp}</td></tr>'
        f'{rijen}</table></td></tr></table></body></html>', subtype="html")
    with smtplib.SMTP_SSL(afz["host"], afz["poort"], timeout=60) as s:
        s.login(afz["gebruiker"], afz["wachtwoord"])
        s.send_message(b)


def main(argv):
    droog = "--droog" in argv
    try:
        stand = json.load(open(STAND))
    except (OSError, ValueError):
        stand = {}
    vorige = stand.get("laatste_ronde", time.time() - 600)
    gevonden = bevindingen(max(60, time.time() - vorige + 30))
    tijdstip = nu().isoformat(timespec="seconds")

    nieuw = [(k, f, t) for k, f, t in gevonden if time.time() - stand.get("gemeld", {}).get(k, 0) > HERHAAL_NA]
    print(f"{tijdstip} {len(gevonden)} bevinding(en), {len(nieuw)} te melden")
    for k, f, t in gevonden:
        print(f"  [{f}] {t}")

    if nieuw and not droog:
        per_firma = {}
        for k, f, t in nieuw:
            per_firma.setdefault(f, []).append(t)
        kanaal = ["⚠️ Aanvragen van de websites: dit vraagt actie"]
        for f, teksten in per_firma.items():
            kanaal.append(f"\n{f}:\n" + "\n".join(f"• {t}" for t in teksten))
        zoom_ok = zoom_kanaal("\n".join(kanaal))
        mail_ok = True
        for f, teksten in per_firma.items():
            try:
                mail(FIRMA_MAIL.get(f, SIYAN), f"LET OP: aanvraag van de website niet goed aangekomen ({f})",
                     "\n\n".join(teksten) + "\n\nDeze melding komt van de aanvraagbewaker op de server. "
                     "Behandel de aanvraag met de hand en laat Siyan weten dat de keten hapert.")
            except Exception as e:  # noqa: BLE001
                mail_ok = False
                print(f"mail naar {f} mislukt: {e}")
        if zoom_ok or mail_ok:
            stand.setdefault("gemeld", {})
            for k, _, _ in nieuw:
                stand["gemeld"][k] = time.time()
    elif nieuw:
        print("(droog: niets gemeld)")

    if not droog:
        # Opgeloste problemen vergeten, zodat ze bij een nieuwe storing meteen weer melden.
        actief = {k for k, _, _ in gevonden}
        stand["gemeld"] = {k: v for k, v in stand.get("gemeld", {}).items() if k in actief}
        stand["laatste_ronde"] = time.time()
        os.makedirs(os.path.dirname(STAND), exist_ok=True)
        json.dump(stand, open(STAND, "w"), indent=1)
    return 1 if gevonden else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

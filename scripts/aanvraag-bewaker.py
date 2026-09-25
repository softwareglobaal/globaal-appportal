#!/usr/bin/env python3
"""Bewaakt de keten van website-aanvraag tot Pipedrive-deal.

WAAROM DIT BESTAAT
De keten heeft vier schakels: de website schrijft de aanvraag weg, zet ze door
naar de inname, de verwerker maakt er een deal van, en koppelt de meldingsmail
aan die deal. Elke schakel kan stilvallen. Het gevaar is niet dat er iets
kapotgaat, maar dat het STIL kapotgaat: dan blijft alles er rustig uitzien
terwijl er aanvragen blijven liggen.

Daarom vergelijkt dit script de schakels met elkaar in plaats van te vertrouwen
op wat één schakel over zichzelf zegt:

    bestand op de website  ->  wachtrij  ->  deal in Pipedrive  ->  mail gekoppeld

Alles wat links wél staat en rechts niet, na een redelijke tijd, is een gat.

STILTE IS OOK EEN ALARM
Eén keer per dag gaat er een bericht uit, ook als alles in orde is. Blijft dat
bericht weg, dan weet je dat de bewaker zelf niet meer draait. Zonder dat
dagbericht is 'geen nieuws' niet te onderscheiden van 'de bewaker ligt plat'.

Cron (elk kwartier):
  */15 * * * * /usr/bin/flock -n /tmp/aanvraag-bewaker.lock /usr/bin/python3 \
      /home/ubuntu/appportal/scripts/aanvraag-bewaker.py >> /home/ubuntu/aanvraag-bewaker.log 2>&1

Droogdraaien (toont het oordeel, meldt niets en onthoudt niets):
  /usr/bin/python3 ~/appportal/scripts/aanvraag-bewaker.py --droog
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DB = os.path.expanduser("~/appportal/aanvraag-data/aanvragen.db")
# Het aanvraagbestand staat in een docker-volume dat alleen root kan lezen; via
# de container zelf lukt het wel, en deze gebruiker zit in de docker-groep.
LEADS_CONTAINER = "unabo-web"
LEADS_PAD = "/data/aanvragen.jsonl"
STAND = os.path.expanduser("~/appportal/aanvraag-data/bewaker.state")
ZOOMPROJECT = os.path.expanduser("~/pipedrive-won-deals")
SITE = "https://unabo.globaal.be"

# Hoe lang een schakel mag achterlopen voor wij het een probleem noemen. Ruim
# genomen: de verwerker draait elke minuut, maar wacht zelf tot tien minuten op
# de Google->Pipedrive-sync van een nieuw contact.
GEDULD_WACHTRIJ = 20 * 60      # aanvraag staat nog op 'wacht'
GEDULD_DEAL = 30 * 60          # aanvraag heeft nog geen deal
GEDULD_MAIL = 30 * 60          # deal heeft nog geen meldingsmail
GEDULD_KOPPELING = 3 * 3600    # mail hangt nog niet aan de deal
GEDULD_INNAME = 30 * 60        # staat op de website maar niet in de wachtrij

# De meldingsmail en de dealkoppeling bestaan pas sinds deze datum. Aanvragen
# van daarvoor missen die velden zonder dat er iets mis is; die overslaan wij,
# anders meldt de bewaker eeuwig een probleem dat niet bestaat.
VANAF = "2026-09-03T18:00:00+00:00"

# Niet blijven herhalen: eenzelfde probleem meldt zich hoogstens om de zes uur.
HERHAAL_NA = 6 * 3600
DAGBERICHT_UUR = 8             # lokale tijd van de server (UTC)


def nu():
    return datetime.now(timezone.utc)


def _laad_env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k, v.strip().strip("\"").strip("'"))
    except OSError:
        pass


_laad_env("~/appportal/.env")
PD_TOKEN = os.environ.get("PIPEDRIVE_TOKEN_UNABO", "")


def stand_lees():
    try:
        return json.load(open(STAND))
    except (OSError, ValueError):
        return {}


def stand_schrijf(d):
    os.makedirs(os.path.dirname(STAND), exist_ok=True)
    json.dump(d, open(STAND, "w"), indent=1)


def ouder_dan(tijdstip, seconden):
    """Is dit ISO-tijdstip langer dan `seconden` geleden?"""
    if not tijdstip:
        return False
    try:
        t = datetime.fromisoformat(str(tijdstip).replace("Z", "+00:00"))
    except ValueError:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (nu() - t).total_seconds() > seconden


# ---------- de vier schakels uitlezen ----------

def na_vanaf(tijdstip):
    """Valt dit tijdstip binnen de periode waarin mail en koppeling bestaan?"""
    return bool(tijdstip) and str(tijdstip) >= VANAF


def website_aanvragen():
    """Wat de website zelf heeft weggeschreven. Dit is de eerste waarheid:
    hier staat de aanvraag al vóór er iets kan misgaan met doorsturen."""
    try:
        uit = subprocess.run(
            ["/usr/bin/docker", "exec", LEADS_CONTAINER, "cat", LEADS_PAD],
            check=True, timeout=30, capture_output=True, text=True).stdout
    except Exception:  # noqa: BLE001
        return None            # onbereikbaar is zelf een bevinding
    rijen = []
    for regel in uit.splitlines():
        regel = regel.strip()
        if not regel:
            continue
        try:
            rijen.append(json.loads(regel))
        except ValueError:
            continue
    return rijen


def wachtrij():
    if not os.path.exists(DB):
        return None
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        # Bewust stopgezette aanvragen (testaanvragen van een nieuwe site staan op
        # 'afgebroken', oude WordPress-inzendingen op 'overgeslagen') tellen niet
        # mee: anders meldt de bewaker eeuwig een probleem dat er niet is.
        return [dict(r) for r in conn.execute(
            "SELECT * FROM aanvraag WHERE status NOT IN ('afgebroken', 'overgeslagen') "
            "ORDER BY id")]
    finally:
        conn.close()


def pd(pad, **params):
    params["api_token"] = PD_TOKEN
    url = f"https://unabo.pipedrive.com/v1{pad}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=45) as r:
        return json.loads(r.read().decode())


# ---------- het onderzoek ----------

def bevindingen():
    """Levert een lijst (sleutel, tekst). Leeg betekent: alles in orde."""
    uit = []

    rijen = wachtrij()
    if rijen is None:
        uit.append(("db-weg", f"De wachtrij bestaat niet meer op {DB}. "
                              "Nieuwe aanvragen kunnen niet verwerkt worden."))
        return uit

    # 1. De verwerker draait niet meer.
    #    Zichtbaar aan aanvragen die blijven staan, niet aan het cron-logboek:
    #    een cron die start maar meteen faalt, schrijft ook regels.
    for r in rijen:
        if r["status"] == "wacht" and ouder_dan(r["ontvangen"], GEDULD_WACHTRIJ):
            uit.append(("wachtrij-stil",
                        f"Aanvraag #{r['id']} staat al langer dan "
                        f"{GEDULD_WACHTRIJ // 60} minuten onverwerkt in de wachtrij. "
                        "Draait de verwerker nog?"))
            break

    # 2. Vastgelopen aanvragen: die komen er zonder ingrijpen nooit meer in.
    vast = [r for r in rijen if r["status"] == "vast"]
    if vast:
        nrs = ", ".join(f"#{r['id']}" for r in vast[:5])
        uit.append(("vastgelopen",
                    f"{len(vast)} aanvraag/aanvragen zijn vastgelopen ({nrs}). "
                    f"Laatste fout: {(vast[0].get('laatste_fout') or '')[:160]}"))

    # 3. Klaar maar zonder deal: mag niet kunnen, wijst op een half afgebroken run.
    for r in rijen:
        if r["status"] == "klaar" and not r["deal_id"]:
            uit.append(("klaar-zonder-deal",
                        f"Aanvraag #{r['id']} staat op 'klaar' maar heeft geen deal. "
                        "Die aanvraag zit nergens."))
            break

    # 4. Deal zonder meldingsmail: de collega weet van niets. Alle gevallen
    #    tellen, niet alleen het eerste: op 24 sep 2026 meldde dit één deal
    #    terwijl er al zeven zonder mail zaten.
    zonder = [r for r in rijen
              if r["deal_id"] and not r.get("mail_verstuurd") and na_vanaf(r["verwerkt"])
              and ouder_dan(r["verwerkt"], GEDULD_MAIL)]
    if zonder:
        deals = ", ".join(str(r["deal_id"]) for r in zonder[:8])
        uit.append(("mail-uit",
                    f"{len(zonder)} deal(s) zonder meldingsmail naar sales ({deals}). "
                    "Het salesteam weet van deze aanvragen niets. Kijk in "
                    "~/agents/aanvraag_verwerk.log waarom de mail niet vertrok."))

    # 5. Mail niet aan de deal gehangen: minder erg, wel het opvolgen waard.
    hangt = [r for r in rijen
             if r.get("mail_verstuurd") and not r.get("mail_gekoppeld")
             # Alleen UNABO: de koppeling zoekt in de Pipedrive-inbox van UNABO,
             # andere firma's hebben een eigen account en worden niet gekoppeld.
             and r.get("bron") not in ("tkn-site",)
             and ouder_dan(r["mail_verstuurd"], GEDULD_KOPPELING)]
    if hangt:
        uit.append(("koppeling-uit",
                    f"{len(hangt)} meldingsmail(s) hangen nog niet aan hun deal in de "
                    "Sales Inbox. De aanvragen zelf staan wel goed in Pipedrive."))

    # 6. De belangrijkste controle: staat er iets op de website dat de wachtrij
    #    nooit heeft bereikt? Dan is de doorgifte stuk en merkt niemand het,
    #    want de bezoeker kreeg gewoon een bedankpagina te zien.
    site = website_aanvragen()
    if site is None:
        uit.append(("leadbestand-weg",
                    "Het aanvraagbestand van de website is niet leesbaar. Daardoor kan "
                    "niet worden gecontroleerd of alles is doorgekomen."))
    else:
        in_rij = set()
        for r in rijen:
            try:
                in_rij.add(json.loads(r["payload"]).get("tijdstip"))
            except (ValueError, TypeError):
                pass
        kwijt = [a for a in site
                 if na_vanaf(a.get("tijdstip")) and a["tijdstip"] not in in_rij
                 and ouder_dan(a["tijdstip"], GEDULD_INNAME)]
        if kwijt:
            eerste = kwijt[0]
            uit.append(("niet-doorgekomen",
                        f"{len(kwijt)} aanvraag/aanvragen staan wel op de website maar "
                        f"NIET in de wachtrij. Oudste: {eerste.get('tijdstip')} "
                        f"({eerste.get('email') or 'geen e-mail'}). "
                        "Die zijn nooit in Pipedrive geraakt."))

    # 7. Neemt de website nog aanvragen aan? Een stuk formulier is even erg als
    #    een stuk koppeling, en valt van buitenaf te controleren.
    try:
        req = urllib.request.Request(SITE + "/contacteer-ons/", method="HEAD")
        with urllib.request.urlopen(req, timeout=20) as r:
            if r.status >= 400:
                uit.append(("site-stuk", f"Het contactformulier geeft status {r.status}."))
    except Exception as e:  # noqa: BLE001
        uit.append(("site-stuk", f"De website is niet bereikbaar: {type(e).__name__}."))

    return uit


def samenvatting(rijen):
    klaar = sum(1 for r in rijen if r["status"] == "klaar")
    gekoppeld = sum(1 for r in rijen if r.get("mail_gekoppeld"))
    return (f"{len(rijen)} aanvragen in totaal, {klaar} verwerkt tot een deal, "
            f"{gekoppeld} met de mail aan de deal gehangen.")


# ---------- melden ----------

def meld(tekst, droog=False):
    """Meldt in Zoom, via het script dat daar al voor bestaat."""
    if droog:
        print("ZOU MELDEN:\n" + tekst)
        return True
    js = ("import('./src/zoomdm.js').then(m=>m.stuurDM(process.argv[1]))"
          ".catch(e=>{console.error(e.message);process.exit(1)})")
    try:
        subprocess.run(["/usr/bin/node", "--input-type=module", "-e", js, tekst],
                       cwd=ZOOMPROJECT, check=True, timeout=60,
                       capture_output=True, text=True)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"melden via Zoom mislukt: {e}")
        return False


def main(argv):
    droog = "--droog" in argv
    stand = stand_lees()
    gevonden = bevindingen()
    rijen = wachtrij() or []

    if gevonden:
        print(f"{nu().isoformat(timespec='seconds')} {len(gevonden)} bevinding(en)")
        te_melden = []
        for sleutel, tekst in gevonden:
            print(f"  [{sleutel}] {tekst}")
            vorige = stand.get("gemeld", {}).get(sleutel, 0)
            if time.time() - vorige > HERHAAL_NA:
                te_melden.append((sleutel, tekst))
        if te_melden:
            bericht = ("UNABO — aanvragen van de website\n\n"
                       + "\n\n".join(t for _, t in te_melden)
                       + f"\n\n{samenvatting(rijen)}")
            if meld(bericht, droog) and not droog:
                stand.setdefault("gemeld", {})
                for sleutel, _ in te_melden:
                    stand["gemeld"][sleutel] = time.time()
                stand_schrijf(stand)
    else:
        print(f"{nu().isoformat(timespec='seconds')} alles in orde. {samenvatting(rijen)}")
        if stand.get("gemeld"):
            # Herstel is net zo goed nieuws als een storing.
            if meld("UNABO — aanvragen: alles loopt weer.\n\n" + samenvatting(rijen), droog) \
                    and not droog:
                stand["gemeld"] = {}
                stand_schrijf(stand)

    # Het dagbericht: zonder dit is stilte niet te onderscheiden van een
    # bewaker die zelf is uitgevallen.
    vandaag = nu().strftime("%Y-%m-%d")
    if not droog and nu().hour >= DAGBERICHT_UUR and stand.get("dagbericht") != vandaag:
        staat = "Alles in orde." if not gevonden else f"LET OP: {len(gevonden)} bevinding(en)."
        if meld(f"UNABO — dagelijkse controle aanvragen\n\n{staat}\n{samenvatting(rijen)}"):
            stand["dagbericht"] = vandaag
            stand_schrijf(stand)

    return 1 if gevonden else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

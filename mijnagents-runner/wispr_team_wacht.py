#!/usr/bin/env python3
"""De Wispr-wacht, serverkant: logt in op het beheerportaal van Wispr Flow (admin.wisprflow.ai)
met het beheerdersaccount, leest de ledenlijst, de zetels, het totale gebruik en de facturatie,
en legt dat naast de boekhouding, het kostendashboard van Shaniel en de organisatiedatabase.
Per persoon gebruik komt van het pc-script (mac/wispr_wacht.py) dat Shaniel uitrolt; hier komt
het samen. Beslissing van Mehdi (13-09-2026): geen duurder plan; controle stuk per stuk.

Sleutels bij naam in ~/appportal/mijnagents-data/.env: WISPR_ADMIN_USER, WISPR_ADMIN_PW.
Gebruik: wispr_team_wacht.py [--toon]   (--toon: geen hartslag, alleen afdrukken)
"""
import json
import os
import re
import sqlite3
import sys
from datetime import date, datetime

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import organisatie  # noqa: E402
import boekhouding  # noqa: E402

DB = os.path.expanduser("~/appportal/mijnagents-data/mijnagents.db")
UIT = os.path.expanduser("~/appportal/mijnagents-data/export/Wispr-wacht")
STAAT = os.path.expanduser("~/appportal/mijnagents-data/wispr-team.json")
ag = bord.Agent("wispr-wacht")
TOON = "--toon" in sys.argv


def _env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_env("~/appportal/mijnagents-data/.env")
GEBRUIKER, WACHTWOORD = os.environ.get("WISPR_ADMIN_USER", "").strip(), os.environ.get("WISPR_ADMIN_PW", "").strip()
ROL = ("Admin", "Member", "IT Admin", "Owner")


def portaal_lezen():
    """Logt in en geeft {leden, zetels, gebruik, facturatie, tekst_team, tekst_billing}."""
    from playwright.sync_api import sync_playwright
    uit = {"leden": [], "zetels": "", "gebruik": {}, "facturatie": {}}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page()
        pg.goto("https://admin.wisprflow.ai/", timeout=60000)
        pg.fill("input[type=email]", GEBRUIKER)
        pg.fill("input[type=password]", WACHTWOORD)
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(6000)
        if pg.locator("input[type=password]").count():
            raise RuntimeError("inloggen mislukt: nog op de loginpagina (wachtwoord of extra stap)")
        # team
        pg.goto("https://admin.wisprflow.ai/app/team", timeout=60000)
        pg.wait_for_timeout(4000)
        team = pg.inner_text("body")
        # gebruik
        pg.goto("https://admin.wisprflow.ai/app/usage", timeout=60000)
        pg.wait_for_timeout(4000)
        usage = pg.inner_text("body")
        # facturatie
        pg.goto("https://admin.wisprflow.ai/app/settings/billing", timeout=60000)
        pg.wait_for_timeout(4000)
        billing = pg.inner_text("body")
        b.close()
    regels = [r.strip() for r in team.splitlines() if r.strip()]
    for i, r in enumerate(regels):
        if re.fullmatch(r"[\w.+-]+@[\w.-]+\.\w+", r):
            naam = regels[i - 1] if i > 0 and regels[i - 1] not in ("You",) else (regels[i - 2] if i > 1 else "")
            if naam == "You":
                naam = regels[i - 2]
            status, rol = "", ""
            for x in regels[i + 1:i + 5]:
                if x in ROL:
                    rol = x
                    break
                if not status and x != "You":
                    status = x
            uit["leden"].append({"naam": naam, "email": r.lower(), "status": status, "rol": rol})
    m = re.search(r"(\d+) of (\d+) billed seats in use across (\d+) members", team)
    if m:
        uit["zetels"] = {"in_gebruik": int(m.group(1)), "betaald": int(m.group(2)), "leden": int(m.group(3))}
    m = re.search(r"([\d,.]+) words dictated", usage)
    if m:
        uit["gebruik"]["woorden_totaal"] = int(m.group(1).replace(",", "").replace(".", ""))
    m = re.search(r"([\d.,]+)% from prior 7 days", usage)
    if m:
        uit["gebruik"]["verschil_7d_pct"] = m.group(1)
    uit["facturatie"]["geannuleerd"] = "Subscription Cancelled" in billing
    m = re.search(r"end on ([^.\n]+)", billing)
    if m:
        uit["facturatie"]["einddatum"] = m.group(1).strip()
    m = re.search(r"You are on the ([^\n(]+)\((\d+) active seats\)", billing)
    if m:
        uit["facturatie"]["plan"] = m.group(1).strip()
        uit["facturatie"]["actieve_zetels"] = int(m.group(2))
    m = re.search(r"New seats \(prorated\)\s*\n?\s*(US\$ ?[\d.,]+)\s*\n?\s*Charge date\s*\n?\s*([^\n]+)", billing)
    if m:
        uit["facturatie"]["volgende_afrekening"] = f"{m.group(1)} op {m.group(2).strip()}"
    m = re.search(r"€ ?(\d+) per user/month\s*\n?\s*Billed annually[\s\S]{0,400}?Current plan", billing)
    if m:
        uit["facturatie"]["prijs_per_zetel_maand"] = int(m.group(1))
    return uit


def kruiscontrole(portaal):
    collegas = organisatie.collegas(alleen_in_dienst=False)
    per_mail = {c["email"].lower(): c for c in collegas if c.get("email")}
    per_voornaam = {}
    for c in collegas:
        per_voornaam.setdefault(c["voornaam"].lower(), []).append(c)
    # kostendashboard van Shaniel (kosten.software) en uitgavenlijst (uitgaven.abonnement)
    dash = boekhouding._psql("select coalesce(json_agg(json_build_object('firma', firma_id, 'zetels', seats_owned, 'betaalwijze', payment_method, 'notitie', note, 'melding', notice, 'bijgewerkt', updated_at)), '[]'::json) from kosten.software where vendor ~* 'wispr'")
    abo = boekhouding._psql("select coalesce(json_agg(json_build_object('plan', plan, 'firma', firma, 'bedrag', bedrag, 'valuta', valuta, 'ritme', ritme, 'account', account, 'laatste_betaling', laatste_betaling, 'notitie', notitie)), '[]'::json) from uitgaven.abonnement where sleutel ~* 'wispr'")
    visa = boekhouding._psql("select coalesce(json_agg(json_build_object('firma', firma_code, 'datum', datum, 'bedrag', bedrag, 'omschrijving', omschrijving) order by datum), '[]'::json) from kosten.bank_transactie where vendor ~* 'wispr' or omschrijving ~* 'wispr'")
    # gebruik per persoon van de pc-scripts (klaarzet soort gebruik, dienst Wispr Flow)
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    gebruik = {}
    for r in c.execute("select sleutel, inhoud, ts from klaarzet where soort='gebruik' order by ts"):
        try:
            d = json.loads(r[1])
        except ValueError:
            continue
        if d.get("dienst") == "Wispr Flow":
            gebruik[(d.get("gebruiker") or r[0]).lower()] = d
    rijen, afwijkingen = [], []
    for l in portaal["leden"]:
        email = l["email"]
        lokaal = email.split("@")[0]
        voornaam = re.sub(r"^(ai|ee|ha|hb|hr|qa|sls|tkn|dat)\.", "", lokaal).split(".")[0].split("-")[0]
        persoon = per_mail.get(email)
        if not persoon:
            kand = per_voornaam.get(voornaam.lower(), [])
            persoon = kand[0] if len(kand) == 1 else None
        gedeeld = lokaal.startswith(("ai.", "hr")) or "admin" in l["naam"].lower()
        g = gebruik.get(voornaam.lower()) or gebruik.get(l["naam"].split()[0].lower()) or {}
        rijen.append({"naam": l["naam"], "email": email, "status": l["status"], "rol": l["rol"],
                      "persoon": (persoon["naam"] if persoon else ("gedeeld account" if gedeeld else "NIET in organisatiedatabase")),
                      "afdeling": persoon["afdeling"] if persoon else "", "firma": persoon["firma"] if persoon else "",
                      "in_dienst": (("ja" if persoon.get("in_dienst") else "NEE") if persoon else ""),
                      "gebruik_week": g.get("week_woorden", ""), "oordeel": g.get("oordeel", "nog geen pc-script")})
        if l["status"].lower().startswith("expired") or "expired" in l["status"].lower():
            afwijkingen.append(f"{email}: uitnodiging vervallen, opruimen")
        elif not persoon and not gedeeld:
            afwijkingen.append(f"{email} ({l['naam']}): staat niet in de organisatiedatabase")
        elif persoon and not persoon.get("in_dienst"):
            afwijkingen.append(f"{email}: persoon is uit dienst maar heeft nog een zetel")
    z = portaal.get("zetels") or {}
    if dash and z:
        d0 = dash[0]
        if int(d0.get("zetels") or 0) != z.get("betaald"):
            afwijkingen.append(f"kostendashboard zegt {d0.get('zetels')} zetels, portaal zegt {z.get('betaald')} betaald ({z.get('in_gebruik')} in gebruik, {z.get('leden')} leden)")
        if (d0.get("firma") or "") and abo and abo[0].get("firma") and d0["firma"] != abo[0]["firma"]:
            afwijkingen.append(f"kostendashboard boekt Wispr bij {d0['firma']}, de uitgavenlijst bij {abo[0]['firma']}; de Visa-lijn staat bij {visa[-1]['firma'] if visa else '?'}")
    f = portaal.get("facturatie") or {}
    if f.get("geannuleerd"):
        afwijkingen.append(f"abonnement staat op GEANNULEERD, loopt af op {f.get('einddatum', '?')}: bevestigen of terugdraaien")
    if f.get("actieve_zetels") and z and f["actieve_zetels"] != z.get("betaald"):
        afwijkingen.append(f"facturatie zegt {f['actieve_zetels']} actieve zetels, ledenpagina {z.get('betaald')} betaald")
    return rijen, afwijkingen, dash, abo, visa


def main():
    if not TOON:
        ag.hartslag("actief", taak="beheerportaal Wispr Flow lezen")
    nood = []
    try:
        if not (GEBRUIKER and WACHTWOORD):
            nood.append({"tekst": "WISPR_ADMIN_USER en WISPR_ADMIN_PW ontbreken in mijnagents-data/.env; zonder kan ik het beheerportaal niet lezen", "wie": "mehdi"})
            raise RuntimeError("geen inloggegevens")
        portaal = portaal_lezen()
        rijen, afwijkingen, dash, abo, visa = kruiscontrole(portaal)
        zonder_script = [r for r in rijen if r["oordeel"] == "nog geen pc-script" and not r["persoon"].startswith("gedeeld") and "expired" not in r["status"].lower()]
        vandaag = date.today().isoformat()
        z = portaal.get("zetels") or {}
        f = portaal.get("facturatie") or {}
        regels = [f"# Wispr Flow, controle van {vandaag}", "",
                  f"Beheerportaal gelezen als {GEBRUIKER}. Plan: {f.get('plan', '?')}, {f.get('actieve_zetels', '?')} actieve zetels, "
                  f"{f.get('prijs_per_zetel_maand', '?')} euro per zetel per maand (jaarlijks). "
                  + ("**GEANNULEERD, loopt af op " + f.get("einddatum", "?") + ".** " if f.get("geannuleerd") else "")
                  + f"Volgende afrekening: {f.get('volgende_afrekening', '-')}. Zetels: {z.get('in_gebruik', '?')} van {z.get('betaald', '?')} in gebruik, {z.get('leden', '?')} leden. "
                  f"Totaal gedicteerd: {portaal['gebruik'].get('woorden_totaal', '?')} woorden ({portaal['gebruik'].get('verschil_7d_pct', '?')}% tegenover de 7 dagen ervoor).", "",
                  "## Leden, naast de organisatiedatabase en het pc-script", "",
                  "| naam in Wispr | e-mail | status | rol | persoon (organisatie) | afdeling | firma | in dienst | woorden/week | oordeel |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for r in rijen:
            regels.append(f"| {r['naam']} | {r['email']} | {r['status']} | {r['rol']} | {r['persoon']} | {r['afdeling']} | {r['firma']} | {r['in_dienst']} | {r['gebruik_week']} | {r['oordeel']} |")
        regels += ["", "## Boekhouding, kostendashboard (Shaniel) en Visa", ""]
        for d in dash:
            regels.append(f"- Kostendashboard: firma {d.get('firma')}, {d.get('zetels')} zetels, betaalwijze {d.get('betaalwijze')}, bijgewerkt {str(d.get('bijgewerkt', ''))[:10]}. Notitie: {d.get('notitie', '')}")
        for a in abo:
            regels.append(f"- Uitgavenlijst: {a.get('plan')} bij {a.get('firma')}, {a.get('bedrag')} {a.get('valuta')} {a.get('ritme')}, account {a.get('account')}, laatste betaling {a.get('laatste_betaling')}.")
        for v in visa:
            regels.append(f"- Visa-lijn: {v.get('datum')} {v.get('firma')} {v.get('bedrag')} euro ({v.get('omschrijving')}).")
        regels += ["- Bitwarden: nog niet gekoppeld (Shaniel: toegang voor de agent, of een export van de Wispr-items).", "",
                   "## Afwijkingen die opgelost moeten worden", ""] + ([f"- {x}" for x in afwijkingen] or ["- geen"])
        regels += ["", "## Pc-script nog niet actief bij", ""] + ([f"- {r['naam']} ({r['email']})" for r in zonder_script] or ["- niemand: overal actief"])
        os.makedirs(UIT, exist_ok=True)
        tekst = "\n".join(regels) + "\n"
        open(os.path.join(UIT, f"Wispr Flow controle {vandaag}.md"), "w", encoding="utf-8").write(tekst)
        open(os.path.join(UIT, "team.md"), "w", encoding="utf-8").write(tekst)
        json.dump({"stand": vandaag, "portaal": portaal, "rijen": rijen, "afwijkingen": afwijkingen}, open(STAAT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if TOON:
            print(tekst)
            return
        ag.klaarzet([{"voor": "licentiewacht", "soort": "gebruik", "sleutel": "team", "uniek": f"wispr-team:{vandaag}",
                      "titel": f"Wispr Flow team {vandaag}: {z.get('betaald', '?')} zetels, {len(afwijkingen)} afwijkingen" + (", GEANNULEERD" if f.get("geannuleerd") else ""),
                      "inhoud": {"dienst": "Wispr Flow", "gebruiker": "team", "stand": vandaag, "zetels": z, "facturatie": f, "gebruik": portaal["gebruik"], "afwijkingen": afwijkingen}},
                     {"voor": "mehdi", "soort": "signaal", "sleutel": vandaag, "uniek": f"wispr-afwijkingen:{vandaag}:{len(afwijkingen)}",
                      "titel": f"Wispr Flow: {len(afwijkingen)} afwijkingen, {len(zonder_script)} pc's zonder script",
                      "inhoud": "\n".join("- " + x for x in afwijkingen) + "\n\nPc-script nog uit te rollen (Shaniel): " + ", ".join(r["naam"] for r in zonder_script)}])
        ag.log(f"controle {vandaag}", "bron", f"portaal: {len(rijen)} leden, zetels {z}, facturatie {f.get('plan', '?')}" + (" GEANNULEERD" if f.get("geannuleerd") else ""), tekst[:6000])
        ag.log(f"controle {vandaag}", "bevinding", f"{len(afwijkingen)} afwijkingen; {len(zonder_script)} personen zonder pc-script", "\n".join(afwijkingen))
        if zonder_script:
            nood.append({"tekst": f"Pc-script (Wispr-wacht) nog uit te rollen bij {len(zonder_script)} personen: " + ", ".join(r["naam"] for r in zonder_script[:8]) + ("..." if len(zonder_script) > 8 else ""), "wie": "shaniel"})
        nood.append({"tekst": "Bitwarden nog niet gekoppeld: toegang voor de agent (Bitwarden CLI met een alleen-lezen API-sleutel van de organisatie) of een export van de Wispr-items", "wie": "shaniel"})
        ag.log_verstuur()
        ag.hartslag("waakt", taak="wacht op de volgende avondronde", detail=f"{z.get('betaald', '?')} zetels, {len(afwijkingen)} afwijkingen" + (", GEANNULEERD" if f.get("geannuleerd") else ""), nood=nood)
        print(f"{len(rijen)} leden, {len(afwijkingen)} afwijkingen, rapport in {UIT}")
    except Exception as e:  # noqa: BLE001
        if TOON:
            raise
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="portaal niet gelezen", detail=f"{type(e).__name__}: {str(e)[:120]}", nood=nood)
        raise


if __name__ == "__main__":
    main()

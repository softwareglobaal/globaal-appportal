#!/usr/bin/env python3
"""De Mailregisseur: bundelt wat de mailwachten klaarzetten en geeft het door aan De Regisseur.

Mandaat van Mehdi, 25-09-2026: "een regisseur van de e-mails die de antwoorden geeft aan de
hoofdregisseur, anders ga ik al die e-mails vergeten. Geen spam, geen rommelinformatie."

Elke mailwacht (koppelingen/postvak.py) zet per bericht dat opvolging vraagt een item klaar
voor mail-regisseur. Ik lees die lijst drie keer per werkdag, maak er per firma een overzicht
van (hoog eerst, dan wat het langst wacht) en:
  - schrijf het in mijn werkverslag, waar De Regisseur het leest (agent_verslag);
  - zet het klaar voor De Regisseur;
  - stuur Mehdi hoogstens een signaal per dag, om 08:00, en alleen als er iets van hoog belang
    of een automatisch bericht met gevolg op hem wacht.
Ik lees geen mail zelf, verstuur niets en beantwoord niets.

    mail_regisseur.py            een ronde, als het een van mijn momenten is
    mail_regisseur.py --nu       nu een ronde, los van de momenten
    mail_regisseur.py --droog    het overzicht tonen, niets naar het bord
"""
import json
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import postvak  # noqa: E402

NAAM = "mail-regisseur"
BRUSSEL = ZoneInfo("Europe/Brussels")
MOMENTEN = ("08:00", "12:30", "17:00")
STAAT = os.path.expanduser("~/appportal/mijnagents-data/mail-regisseur.json")
UIT = os.path.expanduser("~/appportal/mijnagents-data/export/Mailregisseur")  # komt via de Mac-sync in Data uit Mehdi
VOLGORDE = {"hoog": 0, "actie": 1, "midden": 2}
FIRMANAMEN = {"HINV": "info@ H-Invest", "MCH": "mch@ (Mehdi)", "PRIV": "hotmail (privé)", "MELO": "Melodie",
              "HARC": "H-Architects", "HARM": "Harmoniebouw", "UNAB": "UNABO", "TKNB": "TKN-Buro",
              "ENEF": "Energie Efficiënt", "HDSS": "HDS Suriname"}


def moment(nu, staat):
    """Het moment dat nu aan de beurt is (binnen 90 minuten na het tijdstip, nog niet gedaan), of ''."""
    if nu.weekday() >= 5:
        return ""
    for m in reversed(MOMENTEN):
        uur, minuut = map(int, m.split(":"))
        t = nu.replace(hour=uur, minute=minuut, second=0, microsecond=0)
        if t <= nu and (nu - t).total_seconds() < 90 * 60:
            return "" if staat.get(nu.date().isoformat(), {}).get(m) else m
    return ""


def punten(items):
    """De klaargezette items, gelezen en gesorteerd: per firma, hoog eerst, dan wat het langst wacht."""
    uit = []
    for it in items:
        try:
            i = json.loads(it.get("inhoud") or "{}")
        except ValueError:
            continue
        i["firma"] = it.get("sleutel") or ""
        i["wacht"] = it.get("van") or ""
        i["id"] = it.get("id")
        uit.append(i)
    uit.sort(key=lambda i: (i["firma"], VOLGORDE.get(i.get("soort"), 9), -int(i.get("werkdagen_zonder_antwoord") or 0)))
    return uit


def overzicht(lijst, nu):
    """Een leesbaar overzicht per firma. Zegt eerst wat blijft (niets wordt verwijderd), dan wat wacht (L15)."""
    regels = [f"# Mail die op opvolging wacht, {nu.strftime('%d-%m-%Y %H:%M')}", "",
              "Niets hiervan is verwijderd of verplaatst; dit is alleen wat nog een antwoord of een handeling vraagt.",
              "Rommel, koude verkoop, meldingen en verdachte berichten staan er niet in (de mailwachten tellen ze).", ""]
    if not lijst:
        return "\n".join(regels + ["Er wacht niets."])
    firma = None
    for i in lijst:
        if i["firma"] != firma:
            firma = i["firma"]
            regels += ["", f"## {FIRMANAMEN.get(firma, firma)}", ""]
        wd = int(i.get("werkdagen_zonder_antwoord") or 0)
        regels.append(f"- {i.get('soort')}: {i.get('van_naam') or i.get('van')}, {i.get('onderwerp', '')[:100]} "
                      f"({i.get('datum', '')[:10]}, {wd} werkdagen, {i.get('postvak')}). Voorstel: {i.get('voorstel')}.")
    return "\n".join(regels)


def dringend(lijst):
    return [i for i in lijst if i.get("soort") in ("hoog", "actie")
            or int(i.get("werkdagen_zonder_antwoord") or 0) >= 5]


def main():
    droog, forceer = "--droog" in sys.argv, "--nu" in sys.argv
    nu = datetime.now(BRUSSEL)
    try:
        staat = json.load(open(STAAT))
    except (OSError, ValueError):
        staat = {}
    m = moment(nu, staat) or (nu.strftime("%H:%M") if (forceer or droog) else "")
    if not m:
        return
    if droog:
        lijst = punten(bord.klaargezet_voor(NAAM, n=500))
        print(overzicht(lijst, nu))
        print(f"\ndringend: {len(dringend(lijst))}")
        return
    ag = bord.Agent(NAAM)
    with ag.ronde(f"mail bundelen ({m})") as r:
        cfg = postvak.wachten()
        r.bron("mailwachten.json", json.dumps(cfg, ensure_ascii=False, sort_keys=True))
        lijst = punten(bord.klaargezet_voor(NAAM, n=500))
        tekst = overzicht(lijst, nu)
        vandaag = nu.date().isoformat()
        os.makedirs(UIT, exist_ok=True)
        with open(os.path.join(UIT, f"{vandaag}.md"), "w", encoding="utf-8") as f:
            f.write(tekst + "\n")
        per_firma = {}
        for i in lijst:
            per_firma[i["firma"]] = per_firma.get(i["firma"], 0) + 1
        samen = ", ".join(f"{FIRMANAMEN.get(k, k)} {v}" for k, v in sorted(per_firma.items())) or "niets"
        ag.log(f"dag {vandaag}", "overzicht", f"{m}: wacht op opvolging: {samen}", tekst)
        items = [{"voor": "regisseur", "soort": "verslag", "sleutel": vandaag, "titel": f"Mail {vandaag} {m}: {samen}",
                  "uniek": f"mailregisseur:{vandaag}:{m}", "inhoud": tekst}]
        d = dringend(lijst)
        # Dringend (postvak.DRINGEND: deurwaarder, ingebrekestelling, laatste aanmaning, schorsing, ...): De Bode laten
        # bellen, een keer per bericht, op een van mijn momenten (werkdagen 08:00, 12:30, 17:00). Nooit het woord stil.
        for i in (x for x in lijst if x.get("dringend")):
            # een oproep per bericht (uniek op het item), dus nooit twee keer gebeld voor hetzelfde; De Bode bundelt
            # wat tegelijk binnenkomt in een gesprek
            items.append({"voor": "mehdi", "soort": "oproep", "sleutel": vandaag,
                          "titel": re.sub("stil", "st.l", f"Dringende mail van {i.get('van_naam') or i.get('van')}: "
                                                          f"{i.get('onderwerp', '')[:90]}", flags=re.I)[:280],
                          "uniek": f"mailoproep:{i.get('id')}",
                          "inhoud": f"{FIRMANAMEN.get(i['firma'], i['firma'])}, {i.get('postvak')}: {i.get('van_naam') or i.get('van')}, "
                                    f"{i.get('onderwerp', '')[:140]} ({i.get('werkdagen_zonder_antwoord')} werkdagen zonder antwoord). "
                                    "Staat op mijnagents.globaal.be/mail."})
        if m == MOMENTEN[0] and d:
            # Een bericht per dag, zonder aantal in de sleutel (N10), zonder het woord stil (AGENTNORM 6).
            items.append({"voor": "mehdi", "soort": "signaal", "sleutel": vandaag,
                          "titel": f"Mail: {len(d)} zaken wachten op jou ({samen}); overzicht bij De Mailregisseur",
                          "uniek": f"mailregisseur:{vandaag}",
                          "inhoud": "\n".join(f"- {FIRMANAMEN.get(i['firma'], i['firma'])}: {i.get('van_naam') or i.get('van')}, "
                                              f"{i.get('onderwerp', '')[:90]} ({i.get('werkdagen_zonder_antwoord')} wd)" for i in d[:15])})
        ag.klaarzet(items)
        zonder = [z["postvak"] for z in cfg.get("zonder_wacht", [])]
        if zonder:
            r.nood("Postvakken zonder mailwacht: " + ", ".join(zonder) + ". Wat nodig is staat in werkwijze/mailwachten.json",
                   wie="mehdi")
        r.detail = f"{m}: {len(lijst)} op de lijst ({samen}), dringend {len(d)}"
        staat.setdefault(vandaag, {})[m] = nu.isoformat()
        for k in [k for k in staat if k < vandaag]:
            staat.pop(k)
        json.dump(staat, open(STAAT, "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()

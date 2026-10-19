#!/usr/bin/env python3
"""De Mailregisseur: bundelt wat de mailwachten klaarzetten en geeft het door aan De Regisseur.

Mandaat van Mehdi, 25-09-2026: "een regisseur van de e-mails die de antwoorden geeft aan de
hoofdregisseur, anders ga ik al die e-mails vergeten. Geen spam, geen rommelinformatie."

Elke mailwacht (koppelingen/postvak.py) geeft per bericht zijn opvolging door aan het bord (tabel mailbericht). Sinds
19-10-2026 (driehoeksoverleg, 3-0) lees ik wat openstaat daar, via /api/mail/open: dezelfde lijst als op /mail en in
het werkverslag van de wachten, een bron. Ik lees die lijst drie keer per werkdag, maak er per firma een overzicht
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
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import postvak  # noqa: E402

NAAM = "mail-regisseur"
BRUSSEL = ZoneInfo("Europe/Brussels")
MOMENTEN = ("08:00", "12:30", "17:00")
BELVENSTER_MIN = 15  # bellen alleen zo kort na een vast moment, en nooit bij --nu (resultaattoets 19-10-2026, C2)
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


def uitschrijvingen(nu):
    """Het logboek uitschrijven van de laatste 24 uur (Mehdi, 20-10-2026: in een logboek op het dashboard). Ik noem het
    aantal in mijn overzicht; Mehdi krijgt er geen apart bericht over."""
    try:
        rijen = bord.call("/api/mail/uitschrijvingen?" + urllib.parse.urlencode(
            {"sinds": (nu - timedelta(hours=24)).isoformat(), "n": 5000})).get("uitschrijvingen", [])
    except Exception:  # noqa: BLE001
        return None
    tel = {}
    for x in rijen:
        tel[x.get("uitslag")] = tel.get(x.get("uitslag"), 0) + 1
    return tel


def uitschrijfzin(tel):
    if tel is None:
        return "Uitgeschreven de laatste 24 uur: onbekend (logboek niet gelezen)."
    if not tel:
        return "Uitgeschreven de laatste 24 uur: niemand."
    return ("Uitgeschreven de laatste 24 uur via de officiele knop: " + ", ".join(f"{k} {v}" for k, v in sorted(tel.items()))
            + ". Het logboek staat op mijnagents.globaal.be/mail, blok Uitgeschreven.")


def mag_bellen(nu, staat, forceer=False):
    """Mag deze ronde De Bode laten bellen? Alleen een gewone ronde (geen --nu) op een werkdag, binnen een kwartier na
    08:00, 12:30 of 17:00. Een ronde om 18:29 hoort nog bij het moment van 17:00 voor het overzicht, maar belt niet."""
    m = moment(nu, staat)
    if forceer or not m:
        return False
    uur, minuut = map(int, m.split(":"))
    return (nu - nu.replace(hour=uur, minute=minuut, second=0, microsecond=0)).total_seconds() < BELVENSTER_MIN * 60


def punten(open_punten, cfg):
    """Wat het bord als open geeft (/api/mail/open), per firma, hoog eerst, dan wat het langst wacht. De firma komt uit
    mailwachten.json (de wacht die het bericht las). Elk punt houdt zijn sleutel voor een oproep: wat voor 19-10-2026 al
    een klaarzet-item was, houdt mailoproep:<id>, zodat De Bode nooit twee keer belt voor hetzelfde bericht."""
    uit = []
    for p in open_punten:
        i = dict(p)
        w = cfg.get(i.get("wacht") or "")
        i["firma"] = w.get("firma", "") if isinstance(w, dict) else ""
        i["werkdagen_zonder_antwoord"] = int(i.get("werkdagen") or 0)
        i["voorstel"] = i.get("stap") or ""
        i["datum"] = i.get("datum_iso") or ""
        i["oproep"] = f"mailoproep:{i['klaarzet_id']}" if i.get("klaarzet_id") else f"mailoproep:{i.get('uniek')}"
        uit.append(i)
    uit.sort(key=lambda i: (i["firma"], VOLGORDE.get(i.get("soort"), 9), -i["werkdagen_zonder_antwoord"]))
    return uit


def lees_open(cfg):
    """De open punten van het bord, de enige telling (een bron, 19-10-2026)."""
    antw = bord.call("/api/mail/open")
    lijst = punten(antw.get("punten", []), cfg)
    if len(lijst) != antw.get("aantal", len(lijst)):
        raise ValueError(f"het bord gaf {antw.get('aantal')} als aantal maar {len(lijst)} punten")
    return lijst


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
        twijfel = " Mogelijk al beantwoord, nakijken." if i.get("opvolging") == "onzeker" else ""
        regels.append(f"- {i.get('soort')}: {i.get('van_naam') or i.get('van')}, {i.get('onderwerp', '')[:100]} "
                      f"({i.get('datum', '')[:10]}, {wd} werkdagen, {i.get('postvak')}). Voorstel: {i.get('voorstel')}.{twijfel}")
    return "\n".join(regels)


def dringend(lijst):
    return [i for i in lijst if i.get("soort") in ("hoog", "actie")
            or int(i.get("werkdagen_zonder_antwoord") or 0) >= 5]


def titel_0800(lijst, samen):
    """Het 08:00-bericht noemt het aantal open punten, hetzelfde getal als de tegel Op te volgen op /mail."""
    hoog = sum(1 for i in lijst if i.get("soort") == "hoog")
    return f"Mail: {len(lijst)} op te volgen, waarvan {hoog} belangrijk ({samen}); lijst op mijnagents.globaal.be/mail"


def oude_oproepen(lijst, klaargezet):
    """Oproepen die nog niet gebeld zijn (klaar) voor een bericht dat niet meer openstaat: die haal ik weg, zodat De Bode
    niet belt over mail die intussen beantwoord of afgehandeld is (ontwerptoets 19-10-2026, Codex O6)."""
    nog = {i["oproep"] for i in lijst if i.get("dringend")}
    return [it for it in klaargezet if it.get("soort") == "oproep" and str(it.get("uniek") or "").startswith("mailoproep:")
            and it.get("uniek") not in nog]


def main():
    droog, forceer = "--droog" in sys.argv, "--nu" in sys.argv
    nu = datetime.now(BRUSSEL)
    try:
        staat = json.load(open(STAAT))
    except (OSError, ValueError):
        staat = {}
    echt = mag_bellen(nu, staat, forceer)  # alleen dan laat ik bellen
    m = moment(nu, staat) or (nu.strftime("%H:%M") if (forceer or droog) else "")
    if not m:
        return
    if droog:
        lijst = lees_open(postvak.wachten())
        print(overzicht(lijst, nu))
        print(f"\nop te volgen: {len(lijst)}; dringend: {len(dringend(lijst))}; "
              f"zou bellen voor: {len([i for i in lijst if i.get('dringend')]) if echt else 0} (alleen op een vast moment)")
        return
    ag = bord.Agent(NAAM)
    with ag.ronde(f"mail bundelen ({m})") as r:
        cfg = postvak.wachten()
        r.bron("mailwachten.json", json.dumps(cfg, ensure_ascii=False, sort_keys=True))
        lijst = lees_open(cfg)
        uit = uitschrijvingen(nu)
        tekst = overzicht(lijst, nu) + "\n\n" + uitschrijfzin(uit)
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
        # bellen, een keer per bericht, alleen op een van mijn vaste momenten (werkdagen 08:00, 12:30, 17:00), nooit bij een
        # ronde met --nu daarbuiten (ontwerptoets 19-10-2026, Claude O8). Nooit het woord stil.
        for i in (x for x in lijst if x.get("dringend") and echt):
            # een oproep per bericht (uniek op het item), dus nooit twee keer gebeld voor hetzelfde; De Bode bundelt
            # wat tegelijk binnenkomt in een gesprek
            items.append({"voor": "mehdi", "soort": "oproep", "sleutel": vandaag,
                          "titel": re.sub("stil", "st.l", f"Dringende mail van {i.get('van_naam') or i.get('van')}: "
                                                          f"{i.get('onderwerp', '')[:90]}", flags=re.I)[:280],
                          "uniek": i["oproep"],
                          "inhoud": f"{FIRMANAMEN.get(i['firma'], i['firma'])}, {i.get('postvak')}: {i.get('van_naam') or i.get('van')}, "
                                    f"{i.get('onderwerp', '')[:140]} ({i.get('werkdagen_zonder_antwoord')} werkdagen zonder antwoord). "
                                    "Staat op mijnagents.globaal.be/mail."})
        if m == MOMENTEN[0] and d:
            # Een bericht per dag, zonder aantal in de sleutel (N10), zonder het woord stil (AGENTNORM 6).
            items.append({"voor": "mehdi", "soort": "signaal", "sleutel": vandaag,
                          "titel": titel_0800(lijst, samen),
                          "uniek": f"mailregisseur:{vandaag}",
                          "inhoud": "\n".join(f"- {FIRMANAMEN.get(i['firma'], i['firma'])}: {i.get('van_naam') or i.get('van')}, "
                                              f"{i.get('onderwerp', '')[:90]} ({i.get('werkdagen_zonder_antwoord')} wd)" for i in d[:15])})
        ag.klaarzet(items)
        try:
            for it in oude_oproepen(lijst, bord.klaargezet_voor("mehdi", n=500)):
                bord.opgepakt(it["id"], f"{NAAM}: niet meer open, niet bellen")
        except Exception as e:  # noqa: BLE001
            ag.log("oproepen", "fout", f"oude oproepen niet nagekeken: {type(e).__name__}: {str(e)[:120]}")
        zonder = [z["postvak"] for z in cfg.get("zonder_wacht", [])]
        if zonder:
            r.nood("Postvakken zonder mailwacht: " + ", ".join(zonder) + ". Wat nodig is staat in werkwijze/mailwachten.json",
                   wie="mehdi")
        r.detail = (f"{m}: {len(lijst)} op te volgen, zoals op /mail ({samen}), dringend {len(d)}; uitgeschreven 24 u: "
                    f"{'onbekend' if uit is None else (sum(uit.values()) or 0)}")
        staat.setdefault(vandaag, {})[m] = nu.isoformat()
        for k in [k for k in staat if k < vandaag]:
            staat.pop(k)
        json.dump(staat, open(STAAT, "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()

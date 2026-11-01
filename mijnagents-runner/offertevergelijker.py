#!/usr/bin/env python3
"""De Offertevergelijker (afdeling bouw): legt op verzoek de offertes van een lot naast elkaar, voor precies een
firma (H-Architects of Harmonie Bouw), en zet de vergelijking op het bord. Geen gunning: Mehdi beslist.

Een vraag komt binnen als klaargezet item (voor: offertevergelijker, soort: vraag) of met de hand:
    offertevergelijker.py --vraag "firma: HA; project: 2145; lot: 06"

Per vraag: de vraag ontleden (zonder firma geen werk), de lotmap van die firma zoeken (bouw/mappen.py), de PDF's lokaal
lezen met pypdf en een scan met OCR (bouw/offertes.py), fiches en andere stukken zonder totaal weglaten, de totalen en
voorwaarden vergelijken, en per post via Claude op het abonnement van Mehdi (OFFERTE_NAAR_AI, ja op X5 van 01-11-2026),
op geredigeerde tekst. De inschrijvers heten
A, B, C; de naam van de andere firma komt nooit in de vergelijking. Leest Dropbox, schrijft er niets in.

Overleg 30-10-2026 (docs/bouw/rapport-1-ontwerp.md, verwerking in verwerkt-1-ontwerp.md).
--droog: zegt welke vragen klaarstaan en leest geen offertes.
"""
import argparse
import os
import re
import sys
import time
from datetime import date

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
sys.path.insert(0, HIER)
import bord  # noqa: E402
import claude_abonnement  # noqa: E402
from bouw import mappen as MP  # noqa: E402
from bouw import offertes as F  # noqa: E402
from bouw import scheiding as S  # noqa: E402
from bouw import vraag as Q  # noqa: E402
from bouw import verslag as V  # noqa: E402

NAAM = "offertevergelijker"
ag = bord.Agent(NAAM)
MAX_VRAGEN = 2
MAX_OFFERTES = 8
RONDE_SECONDEN = 420            # een download kan 120 s duren; zo blijft de ronde binnen de 600 s van De Regisseur (X11)
SOORT = "offertevergelijking"


def laad_env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


# Instellingen uit ~/appportal/.env en ~/agents/.env (setdefault: het eerste bestand met een waarde wint). Claude draait
# op het abonnement van Mehdi (koppelingen/claude_abonnement.py): een API-sleutel bereikt het model nooit.
laad_env("~/appportal/.env")
laad_env("~/agents/.env")


def laad_kern(r):
    """Het ondernemingsnummer en adres van beide firma's uit kern, voor de scheiding (Codex X1, controle 3). Zonder kern
    werk ik niet: dan kan de toets het adres en het nummer van de andere firma niet herkennen (Codex X1, controle 4)."""
    try:
        if S.laad_kern():
            return True
        r.nood("Ondernemingsnummer of adres van een firma ontbreekt in kern: geen bouwwerk tot ze er staan", wie="mehdi")
    except Exception:  # noqa: BLE001
        r.nood("Kern niet gelezen: geen bouwwerk tot kern leesbaar is", wie="claude-code")
    return False


def open_vragen():
    items = bord.klaargezet_voor(NAAM, status="klaar")
    vragen = [it for it in items if it.get("soort") == "vraag" and (it.get("inhoud") or it.get("titel"))]
    return sorted(vragen, key=lambda it: it.get("id") or 0)


def zet_klaar(tekst_vraag, titel, inhoud, vandaag, firma=None):
    """Klaarzetten voor Mehdi; met een firma eerst de scheiding (geen kenmerk van de andere firma)."""
    if firma:
        weg = S.kruis(titel + "\n" + inhoud, firma)
        if weg:
            raise ValueError("; ".join(weg))
    ag.klaarzet([{"voor": "mehdi", "soort": SOORT, "sleutel": Q.sleutel(tekst_vraag, vandaag), "titel": titel,
                  "uniek": f"offertes:{Q.vingerafdruk(tekst_vraag, vandaag)}", "inhoud": inhoud}])


def lotnaam(pad, firma):
    """De naam van de lotmap voor het verslag; noemt die de andere firma, dan alleen het nummer van het lot."""
    naam = (pad or "").rsplit("/", 1)[-1]
    if S.is_andere_firma(naam, firma):
        m = re.match(r"\s*(\d{1,3})", naam)
        return f"lot {m.group(1)}" if m else "dit lot"
    return naam


def werfstraat(v):
    """De straat en het huisnummer van de werf bij H-Architects (uit de projectmap), om weg te halen voor het model."""
    if v.get("firma") != S.HA or not v.get("project"):
        return ""
    try:
        import projectadressen
        return (projectadressen.adres(v["project"]) or "").split(",")[0].strip()
    except Exception:  # noqa: BLE001  zonder index: de algemene adresregel in redigeer() blijft gelden
        return ""


def een_vraag(r, tekst, vandaag, deadline=None):
    import bronnen
    va = Q.vingerafdruk(tekst, vandaag)
    v = Q.ontleed(tekst)
    blok = Q.ontbreekt_vergelijker(v)
    if blok:
        zet_klaar(tekst, "Offertevergelijking niet gestart: vraag onvolledig", V.onvolledig(NAAM, v.get("firma"), blok),
                  vandaag, v.get("firma"))
        return 0
    firma = v["firma"]
    try:
        pad, lots = MP.offertemap(v, bronnen.lijst, MP.projectmap)
    except MP.MapFout as e:
        zet_klaar(tekst, "Offertevergelijking niet gestart", f"**Niet gestart:** {e}. Ik las geen offerte.", vandaag, firma)
        return 0
    if not pad:
        zet_klaar(tekst, "Offertevergelijking: kies een lot", V.lotkeuze(v, lots), vandaag, firma)
        return 0
    naam = lotnaam(pad, firma)
    alle = MP.offertebestanden(pad, bronnen.lijst)
    # Een fiche of brochure volgens de bestandsnaam neemt geen plaats van een offerte in (gemeten 01-11-2026)
    bestanden = [b for b in alle if not F.fiche_naam(b["naam"])][:MAX_OFFERTES]
    overgeslagen = sum(1 for b in alle if F.fiche_naam(b["naam"]))
    r.bron(f"lotmap {S.FIRMANAMEN[firma]}", f"{len(bestanden)} PDF's, {overgeslagen} fiches volgens de naam overgeslagen")
    if not bestanden:
        zet_klaar(tekst, f"Offertes {naam}: geen PDF", f"**Niet vergeleken:** in {naam} staat geen offerte als PDF.",
                  vandaag, firma)
        return 0
    letters = F.letters(bestanden, firma)
    gelezen, teksten = F.lees_bestanden(letters, bronnen.download, deadline)
    uit = F.vergelijk(gelezen, vandaag)
    per_post, post_redenen = None, {}
    offerte_teksten = F.voor_claude(gelezen, teksten)     # minstens twee echte offertes, anders leeg
    if F.OFFERTE_NAAR_AI and offerte_teksten:
        extra = [x for x in (v.get("project"), werfstraat(v)) if x]
        geredigeerd = {l: F.redigeer(t, extra) for l, t in offerte_teksten.items()}
        try:
            gegevens = F.posten_uit_model(geredigeerd)
            totalen = {g["letter"]: g["lees"].get("excl") for g in gelezen}
            posten, post_redenen = F.keur_posten(gegevens, teksten, totalen)
            if any(posten.values()):
                per_post = F.per_post((gegevens or {}).get("rijen"), {l: p for l, p in posten.items() if p})
        except claude_abonnement.Fout as e:     # zonder Claude blijft de vergelijking van de totalen staan
            ag.log("offertes", "fout", f"vraag {va}: posten niet uitgelezen: {str(e)[:200]}")
            if e.soort in ("aanmelden", "limiet"):
                r.nood(claude_abonnement.AANMELDEN_NOOD if e.aanmelden else claude_abonnement.LIMIET_NOOD, wie="mehdi")
            elif e.soort == "bron":
                r.nood(claude_abonnement.BRON_NOOD, wie="claude-code")
            elif e.soort is None:
                r.nood("Offerteposten niet uitgelezen door Claude op het abonnement", wie="claude-code")
        except Exception as e:  # noqa: BLE001  zonder model blijft de vergelijking van de totalen staan
            ag.log("offertes", "fout", f"vraag {va}: posten niet uitgelezen: {type(e).__name__}: {str(e)[:200]}")
            r.nood("Offerteposten niet uitgelezen door het model", wie="claude-code")
    inhoud = V.vergelijkingsverslag(v, naam, letters, uit, per_post, post_redenen, vandaag.isoformat(),
                                    F.OFFERTE_NAAR_AI, overgeslagen)
    try:
        zet_klaar(tekst, V.vergelijkingstitel(v, naam), inhoud, vandaag, firma)
    except ValueError as e:
        ag.log("offertes", "fout", f"vraag {va}: verslag geweigerd door de scheiding")
        r.nood("Vergelijking geweigerd door de scheidingsgrendel", wie="claude-code")
        return 0
    ag.log("offertes", "melding", f"vergelijking {va} klaargezet voor Mehdi: {len(bestanden)} offertes (de inhoud staat op het bord)")
    return len(bestanden)


def werk(r, hand_vraag=None, droog=False):
    nooit, mehdi_beslist = bord.grenzen(r.werkwijze)
    if not nooit or not mehdi_beslist:
        r.nood("Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist", wie="mehdi")
        r.detail = "geen werk gedaan, grenzen ontbreken in de werkwijze"
        return
    vragen = [{"id": None, "inhoud": hand_vraag}] if hand_vraag else open_vragen()
    if not vragen:
        r.detail = "geen open vraag om offertes te vergelijken"
        return
    if droog:
        r.detail = f"droog: {len(vragen)} vragen klaar, geen offerte gelezen"
        return
    vandaag = date.today()
    deadline = time.monotonic() + RONDE_SECONDEN
    if not laad_kern(r):
        r.detail = "niet gewerkt: de firmagegevens uit kern ontbreken; de vragen blijven klaarstaan"
        return
    gedaan = offertes = 0
    for v in vragen[:MAX_VRAGEN]:
        if time.monotonic() > deadline:
            break                                   # blijft klaarstaan voor de volgende ronde
        tekst = str(v.get("inhoud") or v.get("titel")).strip()
        try:
            offertes += een_vraag(r, tekst, vandaag, deadline)
        except Exception as e:  # noqa: BLE001
            ag.log("offertes", "fout", f"vraag {Q.vingerafdruk(tekst, vandaag)}: {type(e).__name__}: {str(e)[:300]}")
            r.nood("Offertevergelijking mislukt", wie="claude-code")
        gedaan += 1
        if v.get("id"):
            bord.opgepakt(v["id"], NAAM)
    rest = len(vragen) - gedaan
    r.detail = f"{gedaan} vergelijkingen afgewerkt, {offertes} offertes bekeken" + (f", {rest} wachten" if rest else "")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="De Offertevergelijker")
    p.add_argument("--vraag", help="een vraag met de hand: firma: HA; project: 2145; lot: 06")
    p.add_argument("--droog", action="store_true", help="geen offertes lezen; zeggen wat klaarstaat")
    a = p.parse_args()
    with ag.ronde("offertevraag" if a.vraag else "offertevragen afwerken") as r:
        werk(r, a.vraag, a.droog)

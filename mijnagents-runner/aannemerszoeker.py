#!/usr/bin/env python3
"""De Aannemerszoeker (afdeling bouw): zoekt op verzoek firma's die een werk kunnen uitvoeren in een gebied, voor
precies een firma: H-Architects (een uitvoerder voor een bouwheer) of Harmonie Bouw (een onderaannemer). Per kandidaat
zet hij een prijsaanvraag klaar vanuit die ene firma. Hij verstuurt niets.

Een vraag komt op twee manieren binnen:
  - als klaargezet item voor deze agent (voor: aannemerszoeker, soort: vraag), van De Regisseur of een collega;
  - met de hand: aannemerszoeker.py --vraag "firma: HB; werk: ...; gemeente: ...".

Per vraag: de vraag ontleden (bouw/vraag.py; zonder firma geen werk), eerst de eigen mappen en boekhouding van die
firma (bouw/eigen.py), dan het web (bouw/zoeken.py), de code keurt elke kandidaat, bouwt de mails uit het sjabloon
van de firma (bouw/mail.py) en toetst alles aan de scheiding (bouw/scheiding.py). Het verslag gaat naar het bord.

Overleg 30-10-2026 (docs/bouw/rapport-1-ontwerp.md, verwerking in verwerkt-1-ontwerp.md).
--droog: zegt welke vragen klaarstaan en roept het model niet aan.
"""
import argparse
import os
import sys
import time
from datetime import date

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
sys.path.insert(0, HIER)
import bord  # noqa: E402
import claude_abonnement  # noqa: E402
from bouw import eigen as E  # noqa: E402
from bouw import mail as M  # noqa: E402
from bouw import scheiding as S  # noqa: E402
from bouw import vakwoorden as W  # noqa: E402
from bouw import vraag as Q  # noqa: E402
from bouw import verslag as V  # noqa: E402
from bouw import zoeken as Z  # noqa: E402

NAAM = "aannemerszoeker"
ag = bord.Agent(NAAM)
MAX_VRAGEN = 2
RONDE_SECONDEN = 480            # binnen de 600 s die De Regisseur op een ronde wacht
MIN_SECONDEN_PER_VRAAG = 150
SOORT = "aannemersverslag"      # niet 'verslag' of 'signaal': die stuurt De Bode vanzelf door


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
    if firma and S.kruis(titel + "\n" + inhoud, firma):
        raise M.MailGeweigerd(S.kruis(titel + "\n" + inhoud, firma))
    ag.klaarzet([{"voor": "mehdi", "soort": SOORT, "sleutel": Q.sleutel(tekst_vraag, vandaag), "titel": titel,
                  "uniek": f"aannemers:{Q.vingerafdruk(tekst_vraag, vandaag)}", "inhoud": inhoud}])


def gemeente_en_project(v):
    """(gemeente, projectregel) Bij H-Architects mag het project de gemeente geven: de projectmap draagt het adres
    (koppelingen/projectadressen.py). Het adres gaat alleen in de mail, nooit naar het model."""
    gemeente, project = v.get("gemeente") or "", ""
    if v["firma"] == S.HA and v.get("project"):
        try:
            import projectadressen
            adres = projectadressen.adres(v["project"])
        except Exception:  # noqa: BLE001  zonder Dropbox: geen projectregel, de gemeente moet dan in de vraag staan
            adres = ""
        if adres:
            project = f"{v['project']} - {adres}"
            if not gemeente and "," in adres:
                gemeente = adres.rsplit(",", 1)[1].strip()
    return gemeente, project


def een_vraag(r, tekst, vandaag, deadline):
    va = Q.vingerafdruk(tekst, vandaag)
    v = Q.ontleed(tekst)
    blok, aan_te_vullen = Q.ontbreekt_zoeker(v)
    if blok:
        ag.log("aannemersvraag", "beslissing", f"vraag {va} niet gestart: ontbreekt {', '.join(blok)}")
        zet_klaar(tekst, "Aannemersvraag niet gestart: vraag onvolledig", V.onvolledig(NAAM, v.get("firma"), blok), vandaag,
                  v.get("firma"))
        return 0
    firma = v["firma"]
    gemeente, project = gemeente_en_project(v)
    v["gemeente"] = gemeente
    if not gemeente:
        zet_klaar(tekst, "Aannemersvraag niet gestart: geen gemeente", V.onvolledig(NAAM, firma, ["gemeente"]), vandaag,
                  firma)
        return 0
    # Alles wat naar buiten gaat, wordt getoetst: werk, omvang en gemeente (Codex X5, controle 2)
    soorten = Q.naar_buiten_fouten(v)
    if soorten:
        ag.log("aannemersvraag", "beslissing", f"vraag {va} niet verstuurd: persoonsgegevens", ", ".join(soorten))
        zet_klaar(tekst, "Aannemersvraag niet gestart: persoonsgegevens", V.tegengehouden(soorten), vandaag, firma)
        return 0
    # Naar buiten gaan alleen vakwoorden, getallen en eenheden (bouw/vakwoorden.py, controle 5): de rest valt weg en het
    # verslag zegt welke woorden. Ook de mail gebruikt alleen het gefilterde werk.
    werk, weg_werk = W.filter_tekst(v["werk"])
    omvang, weg_omvang = W.filter_tekst(v.get("omvang") or "")
    v["weggelaten"] = weg_werk + weg_omvang
    if not werk:
        zet_klaar(tekst, "Aannemersvraag niet gestart: geen vakwoord", V.onvolledig(NAAM, firma, ["een vakwoord in het werk"]),
                  vandaag, firma)
        return 0
    v["werk"], v["omvang"] = werk, omvang
    # Codex X1 (controle 6): naar buiten gaat niet de tekst van de vraag maar de officiele postcode en gemeente van
    # Geopunt; wat Geopunt niet als gemeente kent, gaat niet weg.
    from adresregister import lokaliseer, postinfo_gemeente
    try:
        centrum = Q.met_postcode(lokaliseer(gemeente), gemeente, postinfo_gemeente)
    except Exception:  # noqa: BLE001
        centrum = None
        r.nood("Geopunt of het postinfo-register niet bereikbaar: geen aannemersvraag zonder officiele gemeente",
               wie="claude-code")
    officieel = Q.officiele_gemeente(centrum)
    if not officieel:
        zet_klaar(tekst, "Aannemersvraag niet gestart: gemeente niet gevonden",
                  V.onvolledig(NAAM, firma, ["een gemeente die Geopunt kent (postcode en naam)"]), vandaag, firma)
        return 0
    gemeente = v["gemeente"] = officieel
    try:
        eigen = E.in_mappen(firma, v["werk"], deadline=min(deadline, time.monotonic() + 60))
        r.bron(f"eigen mappen {S.FIRMANAMEN[firma]}", f"{len(eigen)} treffers onder {E.BASIS[firma]}")
    except Exception as e:  # noqa: BLE001  de eigen mappen zijn een aanvulling; het webzoeken gaat door
        eigen = []
        ag.log("aannemersvraag", "fout", f"vraag {va}: eigen mappen niet gelezen: {type(e).__name__}")
        r.nood("Eigen mappen van de firma niet doorzocht", wie="claude-code")
    soort = "uitvoering" if firma == S.HA else "onderaanneming"
    kennis = Z.kennis_voor_model(bord.collega_tekst(r.collegas) if r.collegas else "", getattr(r, "lessen", []))
    uit = Z.zoek(r.werkwijze, v["werk"], gemeente, v["straal"], soort, vandaag.isoformat(), deadline,
                 omvang=v.get("omvang") or "", kennis=kennis)
    ag.log("aannemersvraag", "bron", f"vraag {va}: op het abonnement, {uit['zoekopdrachten']} zoekopdrachten, "
                                     f"{uit['leesbeurten']} keer WebFetch, {len(uit['gelezen'])} pagina's door de code "
                                     f"gelezen, {uit['tokens']} tokens in {uit['beurten']} beurten, model {uit['model']}")
    g = uit["gegevens"]
    if g is None:
        ag.log("aannemersvraag", "fout", f"vraag {va}: het model gaf geen leesbare gegevens", uit["tekst"][:3000])
        r.nood("Aannemersvraag zonder leesbaar antwoord van het model", wie="claude-code")
        zet_klaar(tekst, "Aannemersvraag zonder antwoord", "**Geen antwoord:** het zoeken gaf geen bruikbare gegevens. "
                  "Ik contacteerde niemand en verstuurde niets.", vandaag, firma)
        return 0
    firmas = [f for f in (g.get("firmas") or []) if isinstance(f, dict)]
    # De andere firma is nooit een kandidaat: geen mail van de ene firma aan de andere (harde regel van Mehdi).
    firmas = [f for f in firmas if not S.is_andere_firma(f"{f.get('naam')} {f.get('url')} {f.get('email')}", firma)
              and not S.schendingen(str(f.get("naam") or ""), firma)]
    from bouw.kern_adres import haal as kbo_haal
    # De code leest de KBO zelf: web_fetch van het model opent ze niet (gemeten 01-11-2026)
    kbo = Z.lees_kbo(firmas, lambda url: kbo_haal(url, timeout=Z.KBO_TIMEOUT), deadline)
    r.bron("KBO door de code", f"{len(kbo)} ondernemingsnummers gelezen")
    res = Z.keur(firmas, uit["gelezen"], centrum, v["straal"], lokaliseer, kbo)
    nummers = [f.get("ondernemingsnummer") for f in res["goed"] + res["na_te_kijken"] + res["buiten"]]
    try:
        eerder, boekhouding_bekend = E.eerder_leverancier(firma, nummers)
    except Exception:  # noqa: BLE001  zonder kern: "boekhouding niet nagekeken", nooit "nee"
        eerder, boekhouding_bekend = {}, False
    mails, geweigerd = {}, 0
    for f in res["goed"] + res["na_te_kijken"]:
        try:
            mails[f["url"]] = M.maak(firma, v["werk"], g.get("werkomschrijving") or "", gemeente, v.get("tegen"),
                                     project, aanhef=f"Beste {f.get('naam') or ''},".replace(" ,", ","))
        except M.MailGeweigerd as e:
            mails[f["url"]] = None
            geweigerd += 1
            ag.log("aannemersvraag", "beslissing", f"vraag {va}: mail geweigerd door de scheiding ({len(e.redenen)} kenmerken)")
    if geweigerd:
        r.nood("Prijsaanvraag geweigerd door de scheidingsgrendel", wie="claude-code")
    inhoud = V.zoekverslag(v, g, res, eigen, mails, eerder, boekhouding_bekend, aan_te_vullen, vandaag.isoformat())
    try:
        zet_klaar(tekst, V.zoektitel(v, res), inhoud, vandaag, firma)
    except M.MailGeweigerd as e:
        ag.log("aannemersvraag", "fout", f"vraag {va}: verslag geweigerd door de scheiding ({len(e.redenen)} kenmerken)")
        r.nood("Verslag geweigerd door de scheidingsgrendel", wie="claude-code")
        return 0
    ag.log("aannemersvraag", "beslissing",
           f"vraag {va}: {len(res['goed'])} klaar, {len(res['na_te_kijken'])} na te kijken, {len(res['buiten'])} buiten, "
           f"{len(res['afgewezen'])} weggelaten, {len(eigen)} eigen treffers",
           [{"url": x["aanbod"].get("url"), "redenen": x["redenen"]} for x in res["afgewezen"]])
    ag.log("aannemersvraag", "melding", f"aannemersverslag {va} klaargezet voor Mehdi (de inhoud staat op het bord)")
    return len(res["goed"])


def werk(r, hand_vraag=None, droog=False, begin=None):
    nooit, mehdi_beslist = bord.grenzen(r.werkwijze)
    if not nooit or not mehdi_beslist:
        r.nood("Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist", wie="mehdi")
        r.detail = "geen werk gedaan, grenzen ontbreken in de werkwijze"
        return
    vragen = [{"id": None, "inhoud": hand_vraag}] if hand_vraag else open_vragen()
    if not vragen:
        r.detail = "geen open aannemersvraag"
        return
    if droog:
        r.detail = f"droog: {len(vragen)} aannemersvragen klaar, model niet aangeroepen"
        return
    deadline = (begin or time.monotonic()) + RONDE_SECONDEN
    vandaag = date.today()
    if not laad_kern(r):
        r.detail = "niet gewerkt: de firmagegevens uit kern ontbreken; de vragen blijven klaarstaan"
        return
    gedaan = klaar = 0
    for v in vragen[:MAX_VRAGEN]:
        if deadline - time.monotonic() < MIN_SECONDEN_PER_VRAAG:
            break
        tekst = str(v.get("inhoud") or v.get("titel")).strip()
        try:
            klaar += een_vraag(r, tekst, vandaag, deadline)
        except claude_abonnement.Fout as e:
            ag.log("aannemersvraag", "fout", f"vraag {Q.vingerafdruk(tekst, vandaag)}: {str(e)[:300]}")
            if e.aanmelden or e.limiet:     # de vraag blijft klaarstaan tot Claude weer kan, zonder extra verbruik
                r.nood(claude_abonnement.AANMELDEN_NOOD if e.aanmelden else claude_abonnement.LIMIET_NOOD, wie="mehdi")
                break
            r.nood("Aannemersvraag mislukt bij Claude op het abonnement", wie="claude-code")
        except Exception as e:  # noqa: BLE001  een mislukte vraag komt niet vanzelf terug
            ag.log("aannemersvraag", "fout", f"vraag {Q.vingerafdruk(tekst, vandaag)}: {type(e).__name__}: {str(e)[:300]}")
            r.nood("Aannemersvraag mislukt bij het zoeken", wie="claude-code")
        gedaan += 1
        if v.get("id"):
            bord.opgepakt(v["id"], NAAM)
    rest = len(vragen) - gedaan
    r.detail = (f"{gedaan} aannemersvragen afgewerkt, {klaar} firma's klaar om aan te schrijven"
                + (f", {rest} wachten" if rest else ""))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="De Aannemerszoeker")
    p.add_argument("--vraag", help="een vraag met de hand, als velden: firma: HB; werk: ...; gemeente: ...")
    p.add_argument("--droog", action="store_true", help="niet zoeken; zeggen wat klaarstaat")
    a = p.parse_args()
    begin = time.monotonic()
    with ag.ronde("aannemersvraag" if a.vraag else "aannemersvragen afwerken") as r:
        werk(r, a.vraag, a.droog, begin)

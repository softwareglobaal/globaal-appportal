#!/usr/bin/env python3
"""De WhatsApp-wacht (privé-communicatie): leest elk uur de WhatsApp-databank op de Mac van Mehdi en schrijft per
gesprek per dag en per oproep een privérij in de gesprekkentabel, met namen, nooit berichttekst (werkwijze v3.0,
ontwerp dagvaststelling v2.0, fase 2; beslissing Mehdi 26-10-2026). Vervangt mac/whatsapp_wacht.py (gekozen exports).

Draait op de Mac (launchd: mac/be.globaal.mijnagents.whatsapp-wacht.plist, elk uur, bij het ontwaken na slaap). De
databank zelf leest alleen MacGesprekkenKopie (Full Disk Access); deze runner leest zijn kopie
(koppelingen/mac_gesprekken.py) en praat met het bord via een ssh-tunnel naar 127.0.0.1:3022, zoals tekenaar.py, door
de gedeelde ronde (N4, N10 tot N14). Daarna leest hij de rijen, de hartslag en de kennis terug op de VM
(koppelingen/bordstand.py); zonder dat is de ronde niet geslaagd.

    whatsapp_wacht.py           een ronde
    whatsapp_wacht.py --droog   de bestaande kopie lezen en per dag de aantallen tonen; niets naar het bord
"""
import argparse
import os
import secrets
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import mac_gesprekken as M  # noqa: E402

NAAM = "whatsapp-wacht"
KANAAL = "whatsapp"
TAAK = "WhatsApp-databank lezen"          # met 'databank': zo ziet De Dagbundelaar dat WhatsApp aangesloten is
ag = bord.Agent(NAAM)


def werk(r, ronde_id, gedekt_tot=None, kopie_vragen=M.kopie_vragen, terug=None):
    """Een ronde: kopie vragen, lezen, schrijven en teruglezen. Geeft de laatste gedekte dag (voor de stand op de Mac:
    na een lange slaap leest de volgende ronde vanaf daar, P7), of None."""
    try:
        M.grenzen_of_stop(r.werkwijze, bord.grenzen)
        r.bron(f"ronde-id-{ronde_id}", "")
        kopie, gekopieerd = kopie_vragen(KANAAL)
        dagen = M.dagen(gekopieerd, gedekt_tot)
        try:
            rijen, info = M.whatsapp_rijen(kopie, dagen)
        finally:
            M.wis(kopie)
        ag.prive(M.maskerwoorden(rijen))
        rijen += M.dekking(KANAAL, dagen, gekopieerd, info["nieuwste"], info["aanwezig"])
        vervallen = M.schrijf_en_lees_terug(KANAAL, rijen, dagen[0], dagen[-1], bord.call, terug)
    except M.MacFout as e:
        r.nood(e.nood, wie=e.wie)
        raise
    nieuwste = info["nieuwste"]
    if nieuwste is None or gekopieerd - nieuwste > M.WA_STIL:
        r.nood("WhatsApp op de Mac ontving al twee dagen niets nieuws: staat de app aan?", wie="mehdi")
    gedekt = [x["datum"] for x in rijen if x["bron"] == "dekking"]
    gisteren = dagen[-2]
    s = M.samenvatting(rijen, gisteren)
    for dag in dagen[-2:]:
        d = M.samenvatting(rijen, dag)
        ag.log(f"dag {dag}", "gelezen", f"{d['berichten']} berichten in {d['gesprekken']} gesprekken, {d['oproepen']} "
               f"oproepen ({d['minuten']} min), {d['gemist']} zonder gesprek")
    r.detail = (f"privé; {len(dagen)} dagen gelezen ({dagen[0]} tot {dagen[-1]}); nieuwste bericht "
                f"{M.uur_van(nieuwste) if nieuwste else 'geen'} op {M.dag_van(nieuwste) if nieuwste else '-'}; "
                f"gisteren {s['berichten']} berichten in {s['gesprekken']} gesprekken, {s['oproepen']} oproepen, "
                f"{s['minuten']} min; dekking tot {max(gedekt) if gedekt else 'geen'}; {len(rijen)} rijen, "
                f"{vervallen} vervallen; ronde-id:{ronde_id}")
    return max(gedekt) if gedekt else None


def droog():
    """Zonder bord en zonder nieuwe kopie: wat de bestaande kopie per dag zou geven, alleen aantallen."""
    kopie = M.KOPIE / KANAAL / "gesprekken.sqlite"
    if not kopie.exists():
        print("geen kopie; maak er eerst een met MacGesprekkenKopie whatsapp")
        return 1
    nu = datetime.now(timezone.utc)
    dagen = M.dagen(nu)
    rijen, info = M.whatsapp_rijen(kopie, dagen)
    rijen += M.dekking(KANAAL, dagen, nu, info["nieuwste"], info["aanwezig"])
    for dag in dagen:
        s = M.samenvatting(rijen, dag)
        gedekt = any(x["uniek"] == f"dekking:{KANAAL}:{dag}" for x in rijen)
        print(f"{dag}: {s['berichten']} berichten in {s['gesprekken']} gesprekken, {s['oproepen']} oproepen "
              f"({s['minuten']} min), {s['gemist']} zonder gesprek{'' if gedekt else ', niet gedekt'}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="De WhatsApp-wacht: de WhatsApp-databank op de Mac lezen.")
    p.add_argument("--droog", action="store_true", help="de bestaande kopie lezen, niets naar het bord")
    a = p.parse_args(argv)
    if a.droog:
        return droog()
    ronde_id = secrets.token_hex(16)
    try:
        with M.slot(NAAM):
            token = M.lees_token()
            stand = M.stand_lezen(NAAM)
            try:
                with M.tunnel() as url:
                    bord.PLATFORM, bord.TOKEN = url, token
                    with ag.ronde(TAAK) as r:
                        gedekt = werk(r, ronde_id, stand.get("gedekt_tot"))
                    if not M.bevestigd(M.bord_stand(NAAM), ronde_id):
                        # P8: het slot houdt een tweede ronde van mij op deze Mac tegen, dus de status op het bord is
                        # van mij; zonder bevestiging staat ze op fout, nooit op een oude klaar.
                        ag.hartslag("fout", taak=TAAK, detail="Bord heeft de ronde niet bevestigd")
                        print("ronde niet bevestigd door het bord", file=sys.stderr)
                        return 1
                    if gedekt:
                        M.stand_schrijven(NAAM, {**stand, "gedekt_tot": gedekt})
            except M.MacFout as e:
                if "ssh-tunnel" in str(e):
                    M.hartslag_publiek(NAAM, token, TAAK, f"De Mac bereikt het bord niet over ssh; ronde niet gedaan: {e}")
                raise
    except M.Bezet:
        print("er loopt al een ronde van De WhatsApp-wacht")
        return 0
    except (M.MacFout, bord.RondeGestopt) as e:
        print(f"ronde mislukt: {e}", file=sys.stderr)
        return 1
    print(f"{datetime.now().isoformat(timespec='seconds')} De WhatsApp-wacht: ronde gelukt")
    return 0


if __name__ == "__main__":
    sys.exit(main())

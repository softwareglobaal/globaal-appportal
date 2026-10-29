#!/usr/bin/env python3
"""Twee controleagents, één index en één bordoverzicht; nooit bronmutaties."""
import argparse
import fcntl
import json
import os
import sys
from contextlib import contextmanager

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord
import naamstructuur as N
import organisatie


@contextmanager
def vergrendeling(data):
    os.makedirs(data, mode=0o700, exist_ok=True)
    with open(os.path.join(data, "ronde.lock"), "a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def werk(agent, r, regels, data):
    c = N.open_db(os.path.join(data, "index.sqlite3"))
    try:
        r.bron("naamstructuur-regels.json", regels)
        r.bron("firmaregister kern via bestaande organisatiekoppeling", organisatie.firmas())
        if not r.werkwijze:
            raise RuntimeError("werkwijze niet beschikbaar op het bord")
        regels_gewijzigd = N.hercontrole_regels(c, regels)
        gelezen = 0
        if agent == "benamingen-wacht":
            try:
                ruleclient = N.lezer_van(regels["regelbron"], regels)
                dagmoment = N.instelling(c, "dagcontrole") != N.nu()[:10]
                bron = N.controleer_regelbron(c, regels, ruleclient.rpc, ruleclient.download,
                                              force=regels_gewijzigd or dagmoment)
            except Exception:
                bron = {"geldig": False, "status": "accountroot niet vastgesteld; H-A-toetsing gepauzeerd"}
                with c:
                    N.instelling(c, "regelbron", bron)
            r.bron("H-A regelbroncontrole", bron)
            if not bron.get("geldig"):
                if bron.get("gevonden"):
                    # T-0028, overleg 29-10 (K5): Mehdi keurt het boek zelf goed; de
                    # vertaling nakijken en de pin bijwerken is werk voor Claude. Tot
                    # 29-10 ging hier "Welke versie geldt?" naar Mehdi en lag de
                    # H-A-toetsing van 18-10 tot 29-10 stil.
                    r.nood(f"{bron['gevonden']} gevonden, nog niet vastgepind (nu {bron['versie']}). "
                           "Hoofdstuk A en B vergelijken, vertaling in naamstructuur-regels.json nakijken "
                           "en versie, pad en sha256 bijwerken", "claude-code")
                else:
                    r.nood("Bevestigd H-A-regelboek niet beschikbaar of gewijzigd", "claude-code")
            ha_bereiken = N.ha_bereiken(regels)
            for root in regels["roots"]:
                try:
                    client = N.lezer_van(root, regels)
                    overslaan = [h["pad"] for h, opslag in ha_bereiken if opslag == root["id"]]
                    gelezen += N.synchroniseer(c, root, client.namespace, client.rpc, regels, overslaan=overslaan)
                except Exception as e:
                    fout = "Bron niet leesbaar of namespace niet bevestigd"
                    if isinstance(e, ValueError) and "nieuwe indexidentiteit" in str(e):
                        fout = "Bronverbinding of accountroot gewijzigd; nieuwe scope-identiteit en rescan nodig"
                    with c:
                        c.execute("INSERT OR IGNORE INTO scope(id,pad,namespace,verbinding) VALUES(?,?,?,?)",
                                  (root["id"], root["pad"], str(root["namespace"]), root["verbinding"]))
                        c.execute("UPDATE scope SET fout=?,poging=? WHERE id=?",
                                  (fout, N.nu(), root["id"]))
                    r.nood("Dropbox-controlebereik niet volledig bereikbaar", "claude-code")
            for bereik, opslag in ha_bereiken:
                try:
                    client = N.lezer_van(bereik, regels)
                    gelezen += N.synchroniseer(c, bereik, client.namespace, client.rpc, regels,
                                                 opslag_scope=opslag)
                except Exception:
                    with c:
                        c.execute("INSERT OR IGNORE INTO scope(id,pad,namespace,verbinding) VALUES(?,?,?,?)",
                                  (bereik["id"], bereik["pad"], str(bereik["namespace"]), bereik["verbinding"]))
                        c.execute("UPDATE scope SET fout=?,poging=? WHERE id=?",
                                  ("H-A-bereik niet leesbaar", N.nu(), bereik["id"]))
                    r.nood("H-A-metadata niet volledig bereikbaar", "claude-code")
            try:
                gelezen += N.lees_lokale_metadata(c, os.path.expanduser("~/appportal/mijnagents-data/mijnagents.db"))
            except Exception:
                c.rollback()
                with c:
                    for soort in ("agenda", "gesprekken"):
                        scope = "lokaal:" + soort
                        c.execute("INSERT OR IGNORE INTO scope(id,pad,namespace) VALUES(?,?,?)", (scope, soort, "bestaande bordindex"))
                    c.execute("UPDATE scope SET fout=?,poging=? WHERE id LIKE 'lokaal:%'",
                              ("Bestaande index niet volledig leesbaar", N.nu()))
                r.nood("Bestaande agenda- of gespreksindex niet leesbaar", "claude-code")
            N.dagelijkse_dekking(c, regels, lambda root: N.lezer_van(root, regels))
        getoetst = N.toets_index(c, agent, regels)
        with c:
            N.instelling(c, "ronde:" + agent, {"tijd": N.nu(), "gelezen": gelezen, "getoetst": getoetst})
        verslag = N.overzicht(c, regels, agent)
        onvolledig = [s for s in verslag["scopes"] if s["ingesteld"] and (not s["compleet"] or s["meer"] or s["fout"])]
        if onvolledig:
            r.nood("Metadata-dekking nog niet volledig of actueel", "claude-code")
        if verslag["tellingen"][agent]:
            r.nood("Naam- en structuurvoorstellen wachten op beoordeling in het overzicht", "mehdi")
        r.detail = f"{gelezen} metadata-items gelezen, {getoetst} getoetst; {verslag['tellingen'][agent]} open punten; {len(onvolledig)} bereiken onvolledig. Overzicht: /naamstructuur."
        # Volledige inhoud blijft in het beheerbestand. Geen klaarzet/signaal/Bode.
        doel = os.path.join(data, "overzicht.json")
        tijdelijk = doel + ".nieuw"
        with open(tijdelijk, "w", encoding="utf-8") as f:
            json.dump(verslag, f, ensure_ascii=False, indent=2)
        os.chmod(tijdelijk, 0o600)
        os.replace(tijdelijk, doel)
        stand = (verslag.get("regelbron") or {}).get("status", "nog niet gecontroleerd")
        print(f"Naamstructuur: {gelezen} gelezen, {getoetst} getoetst, "
              f"{verslag['tellingen'][agent]} open punten; regelbron: {stand}")
    finally:
        c.close()


def main(agent, ronde=None):
    p = argparse.ArgumentParser()
    p.add_argument("--regels", default=os.environ.get("NAAMSTRUCTUUR_REGELS", N.REGELS))
    p.add_argument("--data", default=os.environ.get("NAAMSTRUCTUUR_DATA", N.DATA))
    a = p.parse_args()
    regels = N.lees_regels(a.regels)
    with vergrendeling(a.data) as vrij:
        if not vrij:
            print("Andere naam- of structuurcontrole loopt; volgende kwartier hervatten.")
            return 0
        ag = bord.Agent(agent)
        with (ronde(ag) if ronde else ag.ronde("naam- en structuurcontrole")) as r:
            werk(agent, r, regels, a.data)
    return 0

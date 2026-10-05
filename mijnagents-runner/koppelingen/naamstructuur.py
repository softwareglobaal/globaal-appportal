"""Gedeelde metadata-index voor Benamingenwacht en Mappenwacht, versie 1.0.

Alleen Dropbox-leesroutes. Elke pagina en cursor worden samen gecommit. Een
onvolledige basis, ontbrekende bron of verouderd regelboek is geen geslaagde scan.
De SQLite en het volledige overzicht zijn alleen voor bestaand bordbeheer.
"""
import hashlib
import json
import os
import re
import sqlite3
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import PurePosixPath

HIER = os.path.dirname(os.path.abspath(__file__))
REGELS = os.path.join(os.path.dirname(HIER), "werkwijze", "naamstructuur-regels.json")
DATA = os.path.expanduser("~/appportal/mijnagents-data/naamstructuur")


def nu():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def onder(pad, basis):
    return pad.casefold() == basis.casefold() or pad.casefold().startswith(basis.casefold().rstrip("/") + "/")


def lees_regels(pad=REGELS):
    with open(pad, encoding="utf-8") as f:
        regels = json.load(f)
    roots = regels["roots"]
    if len({r["id"] for r in roots}) != len(roots):
        raise ValueError("dubbele rootidentiteit")
    for i, r in enumerate(roots):
        if not r["pad"].startswith("/") or r["pad"] == "/":
            raise ValueError("alleen expliciete Dropbox-roots")
        if any(r.get("namespace_env", "") == a.get("namespace_env", "") and
               (onder(r["pad"], a["pad"]) or onder(a["pad"], r["pad"])) for a in roots[:i]):
            raise ValueError("overlappende Dropbox-roots")
    return regels


class DropboxLezer:
    """Bestaande stack-accountrechten, expliciete namespace, uitsluitend lezen."""
    LEESROUTES = {"files/list_folder", "files/list_folder/continue", "files/get_metadata"}

    def __init__(self, namespace):
        if not namespace or not str(namespace).isdigit():
            raise ValueError("bevestigde Dropbox-namespace ontbreekt")
        self.namespace = str(namespace)

    def koppen(self, extra):
        import bronnen
        return {"Authorization": "Bearer " + bronnen._toegang(),
                "Dropbox-API-Path-Root": json.dumps(self.pathroot()), **extra}

    def pathroot(self):
        # namespace_id is geldig voor een bestaande account- of gedeelde namespace;
        # root/root is alleen geldig voor de root_namespace_id van het account.
        return {".tag": "namespace_id", "namespace_id": self.namespace}

    def rpc(self, route, inhoud):
        if route not in self.LEESROUTES:
            raise ValueError("uitsluitend metadata-leesroutes toegestaan")
        req = urllib.request.Request("https://api.dropboxapi.com/2/" + route,
                                     json.dumps(inhoud).encode(), self.koppen({"Content-Type": "application/json"}))
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.load(r)

    def download(self, pad, maximum=500001):
        # Alleen de expliciet opgegeven regelbron wordt hiermee gelezen.
        req = urllib.request.Request("https://content.dropboxapi.com/2/files/download", method="POST",
                                     headers=self.koppen({"Dropbox-API-Arg": json.dumps({"path": pad})}))
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.read(maximum)


def open_db(pad):
    os.makedirs(os.path.dirname(os.path.abspath(pad)), mode=0o700, exist_ok=True)
    c = sqlite3.connect(pad, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS scope (
      id TEXT PRIMARY KEY, pad TEXT, namespace TEXT, cursor TEXT DEFAULT '',
      compleet INTEGER DEFAULT 0, meer INTEGER DEFAULT 1, poging TEXT DEFAULT '',
      gelukt TEXT DEFAULT '', fout TEXT DEFAULT '', controle TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS item (
      scope TEXT, identiteit TEXT, pad TEXT, naam TEXT, soort TEXT, firma TEXT,
      profiel TEXT, gegevens TEXT DEFAULT '{}', actief INTEGER DEFAULT 1,
      naam_vuil INTEGER DEFAULT 1, structuur_vuil INTEGER DEFAULT 1,
      PRIMARY KEY(scope,identiteit));
    CREATE INDEX IF NOT EXISTS item_pad ON item(scope,pad);
    CREATE INDEX IF NOT EXISTS item_naam_vuil ON item(naam_vuil,actief);
    CREATE INDEX IF NOT EXISTS item_structuur_vuil ON item(structuur_vuil,actief);
    CREATE TABLE IF NOT EXISTS bevinding (
      agent TEXT, scope TEXT, identiteit TEXT, regel TEXT, bron TEXT, firma TEXT,
      naam TEXT, pad TEXT, voorstel TEXT, status TEXT DEFAULT 'open',
      eerste TEXT, laatste TEXT, PRIMARY KEY(agent,scope,identiteit,regel));
    CREATE TABLE IF NOT EXISTS instelling (sleutel TEXT PRIMARY KEY, waarde TEXT);
    CREATE TABLE IF NOT EXISTS lokaal_cursor (bron TEXT PRIMARY KEY, ts TEXT DEFAULT '', rij INTEGER DEFAULT 0);
    """)
    os.chmod(pad, 0o600)
    return c


def instelling(c, sleutel, waarde=None):
    if waarde is not None:
        c.execute("INSERT INTO instelling VALUES(?,?) ON CONFLICT(sleutel) DO UPDATE SET waarde=excluded.waarde",
                  (sleutel, json.dumps(waarde, ensure_ascii=False)))
        return waarde
    rij = c.execute("SELECT waarde FROM instelling WHERE sleutel=?", (sleutel,)).fetchone()
    return json.loads(rij[0]) if rij else None


def profiel_van(pad, regels):
    for p in sorted(regels["profielen"], key=lambda p: len(p["prefix"]), reverse=True):
        if onder(pad, p["prefix"]):
            return p["firma"], p["profiel"]
    return "onbekend", "algemeen"


def markeer_ouders(c, scope, pad):
    ouder = str(PurePosixPath(pad).parent).casefold()
    c.execute("UPDATE item SET structuur_vuil=1 WHERE scope=? AND lower(pad)=?", (scope, ouder))


def verwerk_pagina(c, scope, pagina, regels):
    for e in pagina["entries"]:
        pad = e.get("path_display") or e.get("path_lower") or ""
        if not pad or not onder(pad, scope["pad"]):
            raise ValueError("Dropbox-item buiten de ingestelde root")
        if e.get(".tag") == "deleted":
            # Een Dropbox-tombstone deactiveert alleen metadata, nooit een bronbestand.
            p = pad.casefold()
            ids = c.execute("SELECT identiteit FROM item WHERE scope=? AND (lower(pad)=? OR substr(lower(pad),1,?)=?)",
                            (scope["id"], p, len(p) + 1, p + "/")).fetchall()
            for r in ids:
                c.execute("UPDATE item SET actief=0 WHERE scope=? AND identiteit=?", (scope["id"], r[0]))
                c.execute("UPDATE bevinding SET status='bron niet meer aanwezig',laatste=? WHERE scope=? AND identiteit=?",
                          (nu(), scope["id"], r[0]))
            markeer_ouders(c, scope["id"], pad)
            continue
        identiteit = e.get("id")
        if not identiteit or e.get(".tag") not in ("file", "folder"):
            raise ValueError("Dropbox-metadata zonder stabiele identiteit")
        oud = c.execute("SELECT pad FROM item WHERE scope=? AND identiteit=?", (scope["id"], identiteit)).fetchone()
        firma, profiel = profiel_van(pad, regels)
        c.execute("""INSERT INTO item(scope,identiteit,pad,naam,soort,firma,profiel)
          VALUES(?,?,?,?,?,?,?) ON CONFLICT(scope,identiteit) DO UPDATE SET
          pad=excluded.pad,naam=excluded.naam,soort=excluded.soort,firma=excluded.firma,
          profiel=excluded.profiel,actief=1,naam_vuil=1,structuur_vuil=1""",
                  (scope["id"], identiteit, pad, e["name"], e[".tag"], firma, profiel))
        markeer_ouders(c, scope["id"], pad)
        if oud and oud[0] != pad:
            markeer_ouders(c, scope["id"], oud[0])


def synchroniseer(c, root, namespace, rpc, regels, budget=None):
    if not namespace:
        raise ValueError("Dropbox-accountroot niet vastgesteld")
    oud = c.execute("SELECT * FROM scope WHERE id=?", (root["id"],)).fetchone()
    if oud and oud["namespace"] == "niet vastgesteld" and not oud["cursor"]:
        c.execute("UPDATE scope SET namespace=? WHERE id=?", (namespace, root["id"]))
        oud = c.execute("SELECT * FROM scope WHERE id=?", (root["id"],)).fetchone()
    if oud and (oud["namespace"] != namespace or oud["pad"] != root["pad"]):
        raise ValueError("accountroot of bereik gewijzigd; nieuwe indexidentiteit nodig")
    c.execute("INSERT OR IGNORE INTO scope(id,pad,namespace) VALUES(?,?,?)", (root["id"], root["pad"], namespace))
    c.commit()
    aantal = 0
    for _ in range(budget or regels["pagina_budget_per_root"]):
        s = dict(c.execute("SELECT * FROM scope WHERE id=?", (root["id"],)).fetchone())
        c.execute("UPDATE scope SET poging=? WHERE id=?", (nu(), s["id"]))
        c.commit()
        try:
            if s["cursor"]:
                pagina = rpc("files/list_folder/continue", {"cursor": s["cursor"]})
            else:
                pagina = rpc("files/list_folder", {"path": s["pad"], "recursive": True,
                                                   "include_deleted": True, "limit": 500})
            if (not isinstance(pagina, dict) or not isinstance(pagina.get("cursor"), str)
                    or not pagina["cursor"] or not isinstance(pagina.get("entries"), list)
                    or type(pagina.get("has_more")) is not bool):
                raise RuntimeError("Dropbox-bereik of cursor niet leesbaar; basis blijft onvolledig")
            with c:
                verwerk_pagina(c, s, pagina, regels)
                meer = bool(pagina.get("has_more"))
                c.execute("UPDATE scope SET cursor=?,meer=?,compleet=?,gelukt=?,fout='' WHERE id=?",
                          (pagina["cursor"], int(meer), int(s["compleet"] or not meer), nu(), s["id"]))
            aantal += len(pagina["entries"])
            if not meer:
                break
        except Exception as e:
            c.rollback()
            with c:
                # Geen API-body of credentials in het verslag.
                c.execute("UPDATE scope SET fout=? WHERE id=?", (type(e).__name__ + ": bron niet leesbaar", s["id"]))
            raise
    return aantal


def controleer_regelbron(c, regels, rpc, download, force=False):
    stand = instelling(c, "regelbron") or {}
    if not force and time.time() - stand.get("ts", 0) < 86400:
        return stand
    bron = regels["regelbron"]
    stand = {"ts": time.time(), "versie": bron["versie"], "pad": bron["pad"], "geldig": False}
    try:
        meta = rpc("files/get_metadata", {"path": bron["pad"]})
        if not meta or meta.get(".tag") != "file" or meta.get("size", 0) > 500000:
            raise ValueError("regelboek niet beschikbaar")
        inhoud = download(bron["pad"], maximum=500001)
        stand["sha256"] = hashlib.sha256(inhoud).hexdigest()
        stand["rev"] = meta.get("rev", "")
        stand["geldig"] = stand["sha256"] == bron["sha256"]
        stand["status"] = "bevestigde bron gelezen" if stand["geldig"] else "regelboek gewijzigd; H-A-toetsing gepauzeerd"
    except Exception as e:
        stand["status"] = type(e).__name__ + ": regelboek niet leesbaar; H-A-toetsing gepauzeerd"
    with c:
        instelling(c, "regelbron", stand)
    return stand


def kinderen(c, rij):
    prefix = rij["pad"].rstrip("/") + "/"
    return [dict(x) for x in c.execute("SELECT * FROM item WHERE scope=? AND actief=1 AND substr(lower(pad),1,?)=?",
                                     (rij["scope"], len(prefix), prefix.casefold()))
            if "/" not in x["pad"][len(prefix):]]


def momentnaam(naam, regels):
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2}) (\S+) (\S+) - (.+)", naam)
    if not m:
        return False
    try:
        datetime.strptime(m[1], "%Y-%m-%d")
    except ValueError:
        return False
    return m[2] in regels["ha"]["kanalen"] and m[3] in regels["ha"]["partijen"]


def is_projectmap(rij, regels):
    ouder = str(PurePosixPath(rij["pad"]).parent).casefold()
    return (rij["profiel"] == "ha_project" and rij["soort"] == "folder"
            and ouder in {p.casefold() for p in regels["ha"]["projectfasen"]}
            and bool(re.match(r"^\d{4}\b", rij["naam"])))


def naamtoets(rij, regels, ha_geldig=True):
    fouten = []
    naam, pad = rij["naam"], rij["pad"]
    if re.search(r'[\\:*?"<>|\x00-\x1f]', naam) or naam != naam.strip() or naam.endswith("."):
        veilig = re.sub(r'[\\:*?"<>|\x00-\x1f]', " ", naam)
        veilig = re.sub(r"\s+", " ", veilig).strip().rstrip(".").strip()
        voorstel = str(PurePosixPath(pad).parent / veilig) if veilig else "Geen veilige naam afleidbaar; naam door Mehdi laten bepalen"
        fouten.append(("bestandsnaam", "Naam bevat een teken of randspatie die uitwisseling tussen systemen hindert. Voorgesteld pad: " + voorstel + ". Controleer bestaand doel en betekenis; wijzig de bron pas na besluit."))
    if not ha_geldig or not rij["profiel"].startswith("ha_"):
        return fouten
    parent = PurePosixPath(pad).parent.name
    if rij["profiel"] == "ha_project" and parent == regels["ha"]["communicatie"]:
        if rij["soort"] == "folder" and not momentnaam(naam, regels):
            fouten.append(("HA A3-A6", "Gebruik datum, vastgesteld kanaal en partij: JJJJ-MM-DD kanaal partij - onderwerp. Bepaal de ontbrekende delen uit de bron; geen recorder als kanaal."))
        elif rij["soort"] == "file" and not re.match(r"\d{4}-\d{2}-\d{2} mail (klant|aannemer|leverancier|gemeente|studie|intern)(?: - .+)?\.[^.]+$", naam):
            fouten.append(("HA A2-A3", "Controleer of dit losse bestand een gewone mail zonder bijlagen is; ander contactmateriaal hoort in een momentmap."))
    # Alleen rechtstreeks onder bekende projectfasen, niet willekeurige numerieke submappen.
    is_project = is_projectmap(rij, regels)
    if is_project:
        import nummerlezer
        if not nummerlezer.ha_nummer(naam, "mapnaam_ha"):
            fouten.append(("HA A13 nummer", "Controleer het dossiernummer via de bestaande bronlezer; leid geen nieuw nummer uit deze map af."))
        if not re.fullmatch(r"\d{4} .+ \d+[A-Za-z]?, \d{4} [^()]+ \((stan|light|voorstudie|reg|onderzoek)\)(?:\((ww|volledig|ww\+tech)\))?(?: ?\([^()]+\))*", naam):
            fouten.append(("HA A13 naam", "Controleer nummer, bouwplaatsadres en vastgelegd type; voorstel pas invullen met contract- en adresbewijs."))
    return fouten


def structuurtoets(c, rij, regels, ha_geldig=True):
    if not ha_geldig or rij["soort"] != "folder" or not rij["profiel"].startswith("ha_"):
        return []
    fouten = []
    naam, parent = rij["naam"], PurePosixPath(rij["pad"]).parent.name
    kind = kinderen(c, rij)
    namen = {e["naam"] for e in kind}
    is_project = is_projectmap(rij, regels)
    if is_project:
        if regels["ha"]["communicatie"] not in namen:
            fouten.append(("HA A1", "Centrale communicatiemap ontbreekt. Voorgesteld doel: " + rij["pad"] + "/_00. Communication. Maak eerst een samenvoegvoorstel met bestaande bronmappen; verplaats niets automatisch."))
        if namen & set(regels["ha"]["oude_communicatie"]):
            fouten.append(("HA A1 oude indeling", "Oude communicatie-indeling aanwezig. Laat Benamingenwacht en Mappenwacht samen het doelpad voorstellen; behoud alle bronbestanden."))
    if rij["profiel"] == "ha_project" and parent == regels["ha"]["communicatie"] and momentnaam(naam, regels):
        if "00 verslag.md" not in namen:
            fouten.append(("HA B1", "Verplicht verslag ontbreekt volgens de volledige metadata-index. Voorgesteld doel: " + rij["pad"] + "/00 verslag.md. Stel verwerking van bestaand momentmateriaal voor, zonder inhoud te verzinnen."))
    if rij["profiel"] == "ha_sales":
        bases = [p["prefix"] for p in regels["profielen"] if p["profiel"] == "ha_sales"]
        if any(str(PurePosixPath(rij["pad"]).parent).casefold() == b.casefold() for b in bases):
            if "00 DOSSIER.md" not in namen:
                fouten.append(("HA A14 fiche", "Salesdossier mist 00 DOSSIER.md. Stel een fiche met bewijs en bronnenregister voor."))
            oud = namen & {"00 Fathom", "0 Xelion recording & transcript"}
            if oud:
                doelen = [rij["pad"] + "/" + ("0 Fathom" if n == "00 Fathom" else "0 Xelion") for n in sorted(oud)]
                fouten.append(("HA A14 bronmap", "Oude bronmapbenaming aangetroffen. Voorgesteld doel: " + "; ".join(doelen) + ". Controleer bestaand doel en doublures; behoud alle bronbestanden."))
    return fouten


def zet_bevindingen(c, agent, rij, fouten, bron):
    moment = nu()
    c.execute("UPDATE bevinding SET status='opgelost in bron',laatste=? WHERE agent=? AND scope=? AND identiteit=? AND status='open'",
              (moment, agent, rij["scope"], rij["identiteit"]))
    for regel, voorstel in fouten:
        c.execute("""INSERT INTO bevinding(agent,scope,identiteit,regel,bron,firma,naam,pad,voorstel,status,eerste,laatste)
          VALUES(?,?,?,?,?,?,?,?,?,'open',?,?) ON CONFLICT(agent,scope,identiteit,regel) DO UPDATE SET
          bron=excluded.bron,firma=excluded.firma,naam=excluded.naam,pad=excluded.pad,
          voorstel=excluded.voorstel,status='open',laatste=excluded.laatste""",
                  (agent, rij["scope"], rij["identiteit"], regel, bron, rij["firma"], rij["naam"], rij["pad"], voorstel, moment, moment))


def toets_index(c, agent, regels, budget=None):
    veld = "naam_vuil" if agent == "benamingen-wacht" else "structuur_vuil"
    ha = bool((instelling(c, "regelbron") or {}).get("geldig"))
    alleen_geldig = "" if ha else " AND i.profiel NOT LIKE 'ha_%'"
    rows = c.execute(f"SELECT i.* FROM item i JOIN scope s ON s.id=i.scope WHERE i.actief=1 AND i.{veld}=1 "
                     "AND s.fout='' AND (i.scope LIKE 'lokaal:%' OR (s.compleet=1 AND s.meer=0))" + alleen_geldig + " LIMIT ?",
                     (budget or regels["item_budget_per_agent"],)).fetchall()
    gedaan = 0
    for row in rows:
        rij = dict(row)
        if not ha and rij["profiel"].startswith("ha_"):
            continue
        if rij["scope"].startswith("lokaal:"):
            fouten, bron = lokale_naamtoets(rij) if agent == "benamingen-wacht" else ([], "lokale metadata")
        else:
            fouten = naamtoets(rij, regels, ha) if agent == "benamingen-wacht" else structuurtoets(c, rij, regels, ha)
            bron = regels["regelbron"]["versie"] if rij["profiel"].startswith("ha_") and ha else "algemene uitwisselbaarheid; firma-/structuurregel niet bevestigd"
        # Pauzeren van de regelbron mag bestaande H-A-bevindingen niet als opgelost markeren.
        if ha or not rij["profiel"].startswith("ha_"):
            with c:
                zet_bevindingen(c, agent, rij, fouten, bron)
                c.execute(f"UPDATE item SET {veld}=0 WHERE scope=? AND identiteit=?", (rij["scope"], rij["identiteit"]))
                gedaan += 1
    return gedaan


def lokale_naamtoets(rij):
    d = json.loads(rij["gegevens"])
    if d.get("_niet_leesbaar"):
        return [("gespreksbron ontbreekt", "Geregistreerd gesprek.json is niet leesbaar; de naamcontrole is niet uitgevoerd.")], "geregistreerd gesprek; bron niet leesbaar"
    if rij["scope"] == "lokaal:agenda":
        import agenda_wacht
        info = agenda_wacht.lees_titel(rij["naam"])
        import nummerlezer
        rij["firma"] = nummerlezer.firma_van_code(info.get("firma") or "") or "onbekend"
        if not info["conform"] and not d.get("hele_dag"):
            return [("agendatitel", "Agendawacht herkent de titelconventie niet. Leg de firmacode, soort en eventuele opdracht vast met de oorspronkelijke afspraak als bewijs.")], "Agendawacht lees_titel; geïndexeerde afspraak"
        kandidaten = nummerlezer.lees(rij["naam"], "agenda_titel")
        if any(k.firma is None for k in kandidaten):
            return [("agendafirma onbekend", "Een geschreven firmacode is niet bevestigd in het register; laat de dossierhouder bevestigen zonder het nummer te wijzigen.")], "gedeelde nummerlezer; geïndexeerde afspraak"
        return [], "Agendawacht + gedeelde nummerlezer; geïndexeerde afspraak"
    import benaming
    b = benaming.benoem(d)
    rij["firma"] = b.get("firma") or "onbekend"
    if b.get("ontbreekt"):
        return [("gespreksnaam", "Ontbrekende delen volgens Benaming: " + ", ".join(b["ontbreekt"]) + ". Vul alleen aan uit agenda, dossier en gesprek; geen titel verzinnen.")], "benaming.benoem; geregistreerd gesprek"
    return [], "benaming.benoem; geregistreerd gesprek"


def lees_lokale_metadata(c, borddb, budget=1000):
    """Reeds geïndexeerde metadata; geen zelfstandige externe accountscan."""
    if not os.path.isfile(borddb):
        raise RuntimeError("bordindex niet beschikbaar")
    bron = sqlite3.connect(f"file:{borddb}?mode=ro", uri=True)
    bron.row_factory = sqlite3.Row
    aantal = 0
    try:
        for soort in ("agenda", "gesprekken"):
            scope = "lokaal:" + soort
            c.execute("INSERT OR IGNORE INTO scope(id,pad,namespace,compleet,meer) VALUES(?,?,?,0,1)", (scope, soort, "bestaande bordindex"))
            cur = c.execute("SELECT * FROM lokaal_cursor WHERE bron=?", (soort,)).fetchone()
            ts, rid = (cur["ts"], cur["rij"]) if cur else ("", 0)
            tabel = "klaarzet" if soort == "agenda" else "gesprek_log"
            where = "AND soort='afspraak'" if soort == "agenda" else "AND bron IN ('fathom','plaud')"
            rows = bron.execute(f"SELECT rowid AS rij,* FROM {tabel} WHERE (ts>? OR (ts=? AND rowid>?)) {where} ORDER BY ts,rowid LIMIT ?", (ts, ts, rid, budget + 1)).fetchall()
            meer = len(rows) > budget
            rows = rows[:budget]
            with c:
                for x in rows:
                    d = dict(x)
                    identiteit = str(d["uniek"] or d["rij"])
                    if soort == "agenda":
                        info = json.loads(d.get("inhoud") or "{}")
                        if not isinstance(info, dict):
                            raise ValueError("afspraakmetadata geen object")
                        naam = info.get("titel") or d.get("titel") or ""
                        pad = info.get("link") or f"bord:afspraak:{d['rij']}"
                    else:
                        pad = d.get("archief") or ""
                        try:
                            with open(os.path.join(pad, "gesprek.json"), encoding="utf-8") as f:
                                info = json.load(f)
                        except (OSError, ValueError):
                            info = {"title": "", "_niet_leesbaar": True}
                        naam = info.get("title") or info.get("meeting_title") or PurePosixPath(pad).name
                    c.execute("""INSERT INTO item(scope,identiteit,pad,naam,soort,firma,profiel,gegevens)
                      VALUES(?,?,?,?,'metadata','onbekend','lokale metadata',?) ON CONFLICT(scope,identiteit)
                      DO UPDATE SET pad=excluded.pad,naam=excluded.naam,gegevens=excluded.gegevens,actief=1,naam_vuil=1""",
                              (scope, identiteit, pad, naam, json.dumps(info, ensure_ascii=False)))
                    ts, rid = d["ts"], d["rij"]
                    aantal += 1
                c.execute("INSERT INTO lokaal_cursor VALUES(?,?,?) ON CONFLICT(bron) DO UPDATE SET ts=excluded.ts,rij=excluded.rij", (soort, ts, rid))
                c.execute("UPDATE scope SET gelukt=?,fout='',meer=?,compleet=CASE WHEN ? THEN compleet ELSE 1 END WHERE id=?",
                          (nu(), int(meer), int(meer), scope))
    finally:
        bron.close()
    return aantal


def dagelijkse_dekking(c, regels, lezer_van):
    vandaag = nu()[:10]
    if instelling(c, "dagcontrole") == vandaag:
        return
    for root in regels["roots"]:
        s = c.execute("SELECT * FROM scope WHERE id=?", (root["id"],)).fetchone()
        if not s:
            continue
        try:
            meta = lezer_van(root).rpc("files/get_metadata", {"path": root["pad"]})
            if not meta or meta.get(".tag") != "folder":
                raise ValueError("root niet beschikbaar")
            stand = "basis volledig, wijzigingen bijgewerkt" if s["compleet"] and not s["meer"] and not s["fout"] else "dekking onvolledig; hervat vanaf cursor"
        except Exception:
            stand = "root niet leesbaar; dekking niet bevestigd"
        with c:
            c.execute("UPDATE scope SET controle=? WHERE id=?", (vandaag + ": " + stand, root["id"]))
    with c:
        instelling(c, "dagcontrole", vandaag)


def overzicht(c, regels, agent):
    scopes = [dict(r) for r in c.execute("SELECT id,pad,namespace,compleet,meer,poging,gelukt,fout,controle FROM scope ORDER BY id")]
    telling = {a: c.execute("SELECT count(*) FROM bevinding WHERE agent=? AND status='open'", (a,)).fetchone()[0]
               for a in ("benamingen-wacht", "mappen-wacht")}
    for s in scopes:
        s["items"] = c.execute("SELECT count(*) FROM item WHERE scope=? AND actief=1", (s["id"],)).fetchone()[0]
        s["achterstand_naam"] = c.execute("SELECT count(*) FROM item WHERE scope=? AND actief=1 AND naam_vuil=1", (s["id"],)).fetchone()[0]
        s["achterstand_structuur"] = c.execute("SELECT count(*) FROM item WHERE scope=? AND actief=1 AND structuur_vuil=1", (s["id"],)).fetchone()[0]
    out = {"versie": "1.0", "gemaakt": nu(), "laatste_agent": agent, "scopes": scopes,
           "regelbron": instelling(c, "regelbron"), "tellingen": telling, "niet_gecontroleerd": regels["niet_gecontroleerd"]}
    for a in ("benamingen-wacht", "mappen-wacht"):
        stand = instelling(c, "ronde:" + a)
        if stand:
            out.setdefault("rondes", {})[a] = stand
    return out

"""Gedeelde metadata-index voor Benamingenwacht en Mappenwacht, versie 1.1.

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
import unicodedata
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from pathlib import PurePosixPath

HIER = os.path.dirname(os.path.abspath(__file__))
REGELS = os.path.join(os.path.dirname(HIER), "werkwijze", "naamstructuur-regels.json")
DATA = os.path.expanduser("~/appportal/mijnagents-data/naamstructuur")
_VERBINDINGEN = {}


def nu():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def onder(pad, basis):
    return pad.casefold() == basis.casefold() or pad.casefold().startswith(basis.casefold().rstrip("/") + "/")


def lees_regels(pad=REGELS):
    with open(pad, encoding="utf-8") as f:
        regels = json.load(f)
    roots = regels["roots"]
    verbindingen = regels.get("verbindingen") or {}
    for naam, v in verbindingen.items():
        if set(v) != {"type", "configpad"} or v["type"] != "omv-v2" or not v["configpad"]:
            raise ValueError("onbekende verbinding of geheimvelden in bronconfiguratie")
    for r in roots + [regels["regelbron"]]:
        if r.get("verbinding") not in verbindingen or not str(r.get("namespace", "")).isdigit():
            raise ValueError("expliciete verbinding en namespace vereist")
    if len({r["id"] for r in roots}) != len(roots):
        raise ValueError("dubbele rootidentiteit")
    for i, r in enumerate(roots):
        if not r["pad"].startswith("/") or r["pad"] == "/":
            raise ValueError("alleen expliciete Dropbox-roots")
        if any(r["verbinding"] == a["verbinding"] and r["namespace"] == a["namespace"] and
               (onder(r["pad"], a["pad"]) or onder(a["pad"], r["pad"])) for a in roots[:i]):
            raise ValueError("overlappende Dropbox-roots")
    return regels


class OMVVerbinding:
    """Hergebruik van de bestaande OMV-v2-configuratie, geen credentialkopie."""
    def __init__(self, configpad):
        self.configpad = os.path.abspath(os.path.expanduser(configpad))
        self._token = ""
        self._tot = 0

    def toegang(self):
        if self._token and time.time() < self._tot:
            return self._token
        try:
            with open(self.configpad, encoding="utf-8") as f:
                regels = f.read().splitlines()
            env = {}
            for regel in regels:
                if "=" in regel and not regel.lstrip().startswith("#"):
                    key, value = regel.split("=", 1)
                    env[key.strip()] = value.strip().strip('"').strip("'")
            appkey = env["DROPBOX_APP_KEY"]
            appsecret = env["DROPBOX_APP_SECRET"]
            tokenpad = os.path.expanduser(env["DROPBOX_TOKEN_FILE"])
            basis = os.path.dirname(self.configpad)
            if tokenpad.startswith("/data/"):
                # De bestaande OMV-v2-container mount omv-v2-data als /data.
                rel = PurePosixPath(tokenpad).relative_to("/data")
                if ".." in rel.parts:
                    raise ValueError("ongeldig tokenbestandpad")
                tokenpad = os.path.join(basis, str(rel))
            elif not os.path.isabs(tokenpad):
                tokenpad = os.path.join(basis, tokenpad)
            with open(tokenpad, encoding="utf-8") as f:
                tokens = json.load(f)
            refresh = tokens["DROPBOX_REFRESH_TOKEN"]
            if not all(isinstance(v, str) and v.strip() for v in (appkey, appsecret, refresh)):
                raise ValueError("onvolledig configuratiepaar")
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise RuntimeError("Bestaande OMV-v2-configuratie of tokenbestand niet bruikbaar") from None
        req = urllib.request.Request("https://api.dropboxapi.com/oauth2/token", urllib.parse.urlencode({
            "grant_type": "refresh_token", "client_id": appkey.strip(),
            "client_secret": appsecret.strip(), "refresh_token": refresh.strip()}).encode())
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                uit = json.load(r)
            token = uit["access_token"]
            duur = int(uit.get("expires_in", 14400))
            if not isinstance(token, str) or not token or duur <= 0:
                raise ValueError("ongeldig authenticatieantwoord")
        except urllib.error.HTTPError as e:
            e.close()
            raise RuntimeError("Bestaande OMV-v2-authenticatie niet beschikbaar") from None
        except Exception:
            raise RuntimeError("Bestaande OMV-v2-authenticatie niet beschikbaar") from None
        # Alleen procesgeheugen; het gedeelde OMV-tokenbestand blijft ongewijzigd.
        self._token, self._tot = token, time.time() + max(duur - 300, 1)
        return token


def lezer_van(root, regels):
    naam = root.get("verbinding")
    config = (regels.get("verbindingen") or {}).get(naam)
    namespace = root.get("namespace")
    if not config or config.get("type") != "omv-v2" or not str(namespace or "").isdigit():
        raise ValueError("bevestigde bronverbinding of namespace ontbreekt")
    pad = os.path.abspath(os.path.expanduser(config["configpad"]))
    bron = _VERBINDINGEN.setdefault(pad, OMVVerbinding(pad))
    return DropboxLezer(namespace, verbinding=naam, toegang=bron.toegang, bronconfig=pad)


class DropboxLezer:
    """Bestaande bronrechten, expliciete verbinding en namespace, uitsluitend lezen."""
    LEESROUTES = {"files/list_folder", "files/list_folder/continue", "files/get_metadata"}

    def __init__(self, namespace, verbinding="stack", toegang=None, bronconfig=""):
        if not namespace or not str(namespace).isdigit():
            raise ValueError("bevestigde Dropbox-namespace ontbreekt")
        self.namespace = str(namespace)
        self.verbinding = verbinding
        self.bronconfig = bronconfig
        self._toegang = toegang

    def koppen(self, extra):
        if self._toegang:
            token = self._toegang()
        else:
            import bronnen
            token = bronnen._toegang()
        return {"Authorization": "Bearer " + token,
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
      scope TEXT, identiteit TEXT, pad TEXT, pad_sleutel TEXT, naam TEXT, soort TEXT, firma TEXT,
      profiel TEXT, gegevens TEXT DEFAULT '{}', actief INTEGER DEFAULT 1,
      naam_vuil INTEGER DEFAULT 1, structuur_vuil INTEGER DEFAULT 1,
      ha_gezien TEXT DEFAULT '',
      PRIMARY KEY(scope,identiteit));
    CREATE INDEX IF NOT EXISTS item_pad ON item(scope,pad);
    CREATE INDEX IF NOT EXISTS item_naam_vuil ON item(naam_vuil,actief);
    CREATE INDEX IF NOT EXISTS item_structuur_vuil ON item(structuur_vuil,actief);
    CREATE INDEX IF NOT EXISTS item_ha_naam_vuil ON item(naam_vuil,actief) WHERE profiel GLOB 'ha_*';
    CREATE INDEX IF NOT EXISTS item_ha_structuur_vuil ON item(structuur_vuil,actief) WHERE profiel GLOB 'ha_*';
    CREATE TABLE IF NOT EXISTS bevinding (
      agent TEXT, scope TEXT, identiteit TEXT, regel TEXT, bron TEXT, firma TEXT,
      naam TEXT, pad TEXT, voorstel TEXT, status TEXT DEFAULT 'open',
      eerste TEXT, laatste TEXT, PRIMARY KEY(agent,scope,identiteit,regel));
    CREATE INDEX IF NOT EXISTS bevinding_scope_identiteit ON bevinding(scope,identiteit);
    CREATE TABLE IF NOT EXISTS instelling (sleutel TEXT PRIMARY KEY, waarde TEXT);
    CREATE TABLE IF NOT EXISTS lokaal_cursor (bron TEXT PRIMARY KEY, ts TEXT DEFAULT '', rij INTEGER DEFAULT 0);
    """)
    if "verbinding" not in {r[1] for r in c.execute("PRAGMA table_info(scope)")}:
        c.execute("ALTER TABLE scope ADD COLUMN verbinding TEXT DEFAULT ''")
    if "ha_gezien" not in {r[1] for r in c.execute("PRAGMA table_info(item)")}:
        c.execute("ALTER TABLE item ADD COLUMN ha_gezien TEXT DEFAULT ''")
    nieuw_padveld = "pad_sleutel" not in {r[1] for r in c.execute("PRAGMA table_info(item)")}
    if nieuw_padveld:
        c.execute("ALTER TABLE item ADD COLUMN pad_sleutel TEXT")
    # SQLite lower() verwerkt alleen ASCII. Dezelfde Python-casefold als de
    # bronregels geldt ook voor geïndexeerde Unicodepaden, inclusief oude items.
    # Een migratiemarkering voorkomt een volledige scan bij iedere hartslag.
    if nieuw_padveld or instelling(c, "pad_sleutel_versie") != 1:
        laatst = 0
        while True:
            rows = c.execute("SELECT rowid,pad FROM item WHERE rowid>? AND pad_sleutel IS NULL ORDER BY rowid LIMIT 1000",
                             (laatst,)).fetchall()
            if not rows:
                break
            c.executemany("UPDATE item SET pad_sleutel=?,structuur_vuil=1 WHERE rowid=?",
                          [(str(r["pad"] or "").casefold(), r["rowid"]) for r in rows])
            laatst = rows[-1]["rowid"]
            c.commit()
        instelling(c, "pad_sleutel_versie", 1)
    c.execute("CREATE INDEX IF NOT EXISTS item_pad_sleutel ON item(scope,pad_sleutel)")
    nieuwe_overzichtindex = "item_scope_actief_profiel_vuil" not in {
        r[1] for r in c.execute("PRAGMA index_list(item)")}
    c.execute("CREATE INDEX IF NOT EXISTS item_scope_actief_profiel_vuil "
              "ON item(scope,actief,profiel,naam_vuil,structuur_vuil)")
    if nieuwe_overzichtindex:
        c.execute("ANALYZE item")
    c.commit()
    os.chmod(pad, 0o600)
    return c


def instelling(c, sleutel, waarde=None):
    if waarde is not None:
        c.execute("INSERT INTO instelling VALUES(?,?) ON CONFLICT(sleutel) DO UPDATE SET waarde=excluded.waarde",
                  (sleutel, json.dumps(waarde, ensure_ascii=False)))
        return waarde
    rij = c.execute("SELECT waarde FROM instelling WHERE sleutel=?", (sleutel,)).fetchone()
    return json.loads(rij[0]) if rij else None


def regelvingerafdruk(waarde):
    return hashlib.sha256(json.dumps(waarde, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def hercontrole_regels(c, regels):
    """H1-4, driehoeksoverleg C2, 17-10-2026: hercontrole per geraakt deel."""
    delen = {"ha": regels["ha"], "regelbron": regels["regelbron"]}
    delen.update({"root:" + r["id"]: r for r in regels["roots"]})
    delen.update({"profiel:" + p["prefix"].casefold(): p for p in regels["profielen"]})
    # Administratieve velden veranderen geen toets; onbekende regels raken mogelijk alles.
    bekend = {"ha", "regelbron", "roots", "profielen", "versie", "verbindingen",
              "pagina_budget_per_root", "item_budget_per_agent", "niet_gecontroleerd"}
    delen["overig"] = {k: v for k, v in regels.items() if k not in bekend}
    nieuw = {k: regelvingerafdruk(v) for k, v in delen.items()}
    oud = instelling(c, "regelvingerafdrukken")
    if oud is None:
        # De oude formule gebruikte json.dumps zonder ensure_ascii=False.
        oude_globale = hashlib.sha256(json.dumps(regels, sort_keys=True).encode()).hexdigest()
        gelijk = instelling(c, "regelsvingerafdruk") == oude_globale
        with c:
            if not gelijk:
                c.execute("UPDATE item SET naam_vuil=1,structuur_vuil=1")
            instelling(c, "regelvingerafdrukken", nieuw)
            c.execute("DELETE FROM instelling WHERE sleutel='regelsvingerafdruk'")
        return not gelijk
    geraakt = {k for k in set(oud) | set(nieuw) if oud.get(k) != nieuw.get(k)}
    if not geraakt:
        return False
    with c:
        if "overig" in geraakt:
            # Onbekende semantische regel: het bereik is niet te bewijzen; alles vuil.
            c.execute("UPDATE item SET naam_vuil=1,structuur_vuil=1")
        if "ha" in geraakt or "regelbron" in geraakt:
            c.execute("UPDATE item SET naam_vuil=1,structuur_vuil=1 WHERE profiel GLOB 'ha_*'")
        for sleutel in geraakt:
            if sleutel.startswith("root:"):
                c.execute("UPDATE item SET naam_vuil=1,structuur_vuil=1 WHERE scope=?", (sleutel[5:],))
        prefixes = {k[8:] for k in geraakt if k.startswith("profiel:")}
        if prefixes:
            for p in set(prefixes):
                rows = c.execute("SELECT scope,identiteit,pad FROM item WHERE pad_sleutel=? OR (pad_sleutel>=? AND pad_sleutel<?)",
                                 (p, p + "/", p + "0")).fetchall()
                for rij in rows:
                    firma, profiel = profiel_van(rij["pad"], regels)
                    c.execute("UPDATE item SET firma=?,profiel=?,naam_vuil=1,structuur_vuil=1 WHERE scope=? AND identiteit=?",
                              (firma, profiel, rij["scope"], rij["identiteit"]))
        instelling(c, "regelvingerafdrukken", nieuw)
    return bool(geraakt)


def ha_bereiken(regels):
    """H1-4, driehoeksoverleg C2, 17-10-2026: aparte prefixcursors, bestaande item-ID's.

    De Work All-cursor blijft staan. Zijn pagina's slaan H-A-rijen over; de
    prefixcursor schrijft die rijen onder dezelfde Work All-scope. Daardoor
    blijven bestaande bevindingen bruikbaar en kan een prefix apart voltooid zijn.
    """
    uit = []
    for p in regels["profielen"]:
        if not p["profiel"].startswith("ha_"):
            continue
        root = next((r for r in regels["roots"] if r.get("verbinding") == regels["regelbron"]["verbinding"]
                     and r.get("namespace") == regels["regelbron"]["namespace"] and onder(p["prefix"], r["pad"])), None)
        if root:
            sleutel = hashlib.sha256(p["prefix"].casefold().encode()).hexdigest()[:16]
            uit.append(({**root, "id": "ha:" + root["id"] + ":" + sleutel, "pad": p["prefix"]}, root["id"]))
    return uit


def profiel_van(pad, regels):
    for p in sorted(regels["profielen"], key=lambda p: len(p["prefix"]), reverse=True):
        if onder(pad, p["prefix"]):
            return p["firma"], p["profiel"]
    return "onbekend", "algemeen"


def markeer_ouders(c, scope, pad):
    ouder = str(PurePosixPath(pad).parent).casefold()
    c.execute("UPDATE item SET structuur_vuil=1 WHERE scope=? AND pad_sleutel=?", (scope, ouder))


def verwerk_pagina(c, scope, pagina, regels, opslag_scope=None, overslaan=(), eerste_ha_lezing=False):
    opslag = opslag_scope or scope["id"]
    aantal = 0
    for e in pagina["entries"]:
        pad = e.get("path_display") or e.get("path_lower") or ""
        if not pad or not onder(pad, scope["pad"]):
            raise ValueError("Dropbox-item buiten de ingestelde root")
        if any(onder(pad, prefix) for prefix in overslaan):
            continue
        aantal += 1
        if e.get(".tag") == "deleted":
            # Een Dropbox-tombstone deactiveert alleen metadata, nooit een bronbestand.
            p = pad.casefold()
            ids = c.execute("SELECT identiteit FROM item WHERE scope=? AND pad_sleutel=? UNION "
                            "SELECT identiteit FROM item WHERE scope=? AND pad_sleutel>=? AND pad_sleutel<?",
                            (opslag, p, opslag, p + "/", p + "0")).fetchall()
            for r in ids:
                c.execute("UPDATE item SET actief=0 WHERE scope=? AND identiteit=?", (opslag, r[0]))
                c.execute("UPDATE bevinding SET status='bron niet meer aanwezig',laatste=? WHERE scope=? AND identiteit=?",
                          (nu(), opslag, r[0]))
            markeer_ouders(c, opslag, pad)
            continue
        identiteit = e.get("id")
        if not identiteit or e.get(".tag") not in ("file", "folder"):
            raise ValueError("Dropbox-metadata zonder stabiele identiteit")
        oud = c.execute("SELECT pad,naam,soort,firma,profiel,actief FROM item WHERE scope=? AND identiteit=?",
                        (opslag, identiteit)).fetchone()
        firma, profiel = profiel_van(pad, regels)
        # H1-4, driehoeksoverleg C2, 17-10-2026: een bestaande Work All-rij
        # blijft bruikbaar; ongewijzigde metadata vraagt geen tweede toets.
        if oud and (oud["pad"], oud["naam"], oud["soort"], oud["firma"], oud["profiel"], oud["actief"]) == (
                pad, e["name"], e[".tag"], firma, profiel, 1):
            if eerste_ha_lezing:
                c.execute("UPDATE item SET ha_gezien=? WHERE scope=? AND identiteit=?",
                          (scope["id"], opslag, identiteit))
            continue
        c.execute("""INSERT INTO item(scope,identiteit,pad,pad_sleutel,naam,soort,firma,profiel,ha_gezien)
          VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(scope,identiteit) DO UPDATE SET
          pad=excluded.pad,pad_sleutel=excluded.pad_sleutel,naam=excluded.naam,soort=excluded.soort,firma=excluded.firma,
          profiel=excluded.profiel,ha_gezien=excluded.ha_gezien,actief=1,naam_vuil=1,structuur_vuil=1""",
                  (opslag, identiteit, pad, pad.casefold(), e["name"], e[".tag"], firma, profiel,
                   scope["id"] if eerste_ha_lezing else ""))
        markeer_ouders(c, opslag, pad)
        if oud and oud["pad"] != pad:
            markeer_ouders(c, opslag, oud["pad"])
    return aantal


def sluit_eerste_ha_lezing(c, bereik, opslag):
    """Ruim alleen na het laatste geldige eerste H-A-blad oude indexrijen op."""
    prefix = bereik["pad"].casefold()
    grens = (opslag, prefix, prefix + "/", prefix + "0", bereik["id"])
    laatst = 0
    while True:
        rows = c.execute("SELECT rowid,identiteit,pad FROM item WHERE scope=? AND actief=1 "
                         "AND (pad_sleutel=? OR (pad_sleutel>=? AND pad_sleutel<?)) "
                         "AND COALESCE(ha_gezien,'')<>? AND rowid>? ORDER BY rowid LIMIT 1000",
                         grens + (laatst,)).fetchall()
        if not rows:
            break
        moment = nu()
        c.executemany("UPDATE bevinding SET status='bron niet meer aanwezig',laatste=? "
                      "WHERE scope=? AND identiteit=?",
                      [(moment, opslag, r["identiteit"]) for r in rows])
        c.executemany("UPDATE item SET actief=0 WHERE rowid=?", [(r["rowid"],) for r in rows])
        ouders = {str(PurePosixPath(r["pad"]).parent).casefold() for r in rows}
        c.executemany("UPDATE item SET structuur_vuil=1 WHERE scope=? AND pad_sleutel=?",
                      [(opslag, ouder) for ouder in ouders])
        laatst = rows[-1]["rowid"]


def synchroniseer(c, root, namespace, rpc, regels, budget=None, opslag_scope=None, overslaan=()):
    if not namespace:
        raise ValueError("Dropbox-accountroot niet vastgesteld")
    oud = c.execute("SELECT * FROM scope WHERE id=?", (root["id"],)).fetchone()
    verbinding = root.get("verbinding", "stack")
    if oud and oud["namespace"] == "niet vastgesteld" and not oud["cursor"]:
        if c.execute("SELECT count(*) FROM item WHERE scope=?", (root["id"],)).fetchone()[0]:
            raise ValueError("bronbewijs aanwezig; nieuwe indexidentiteit nodig")
        c.execute("UPDATE scope SET namespace=?,verbinding=? WHERE id=?", (namespace, verbinding, root["id"]))
        oud = c.execute("SELECT * FROM scope WHERE id=?", (root["id"],)).fetchone()
    if oud and (oud["namespace"] != namespace or oud["pad"] != root["pad"] or oud["verbinding"] != verbinding):
        raise ValueError("verbinding, accountroot of bereik gewijzigd; nieuwe indexidentiteit en rescan nodig")
    c.execute("INSERT OR IGNORE INTO scope(id,pad,namespace,verbinding) VALUES(?,?,?,?)", (root["id"], root["pad"], namespace, verbinding))
    c.commit()
    aantal = 0
    for _ in range(budget or regels["pagina_budget_per_root"]):
        s = dict(c.execute("SELECT * FROM scope WHERE id=?", (root["id"],)).fetchone())
        c.execute("UPDATE scope SET poging=? WHERE id=?", (nu(), s["id"]))
        c.commit()
        try:
            # H1-4, driehoeksoverleg C2, 17-10-2026: de prefixmap zelf staat
            # niet in list_folder; lees haar eenmaal via dezelfde cursorstart.
            zelf = None
            if opslag_scope and not s["cursor"]:
                zelf = rpc("files/get_metadata", {"path": s["pad"]})
                if not isinstance(zelf, dict) or zelf.get(".tag") != "folder" or not zelf.get("id"):
                    raise RuntimeError("H-A-prefix niet leesbaar")
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
                eerste = bool(opslag_scope and not s["compleet"])
                if zelf:
                    aantal += verwerk_pagina(c, s, {"entries": [zelf]}, regels, opslag_scope,
                                             eerste_ha_lezing=eerste)
                aantal += verwerk_pagina(c, s, pagina, regels, opslag_scope, overslaan,
                                         eerste_ha_lezing=eerste)
                meer = bool(pagina.get("has_more"))
                if eerste and not meer:
                    sluit_eerste_ha_lezing(c, s, opslag_scope)
                c.execute("UPDATE scope SET cursor=?,meer=?,compleet=?,gelukt=?,fout='' WHERE id=?",
                          (pagina["cursor"], int(meer), int(s["compleet"] or not meer), nu(), s["id"]))
            if not meer:
                break
        except Exception as e:
            c.rollback()
            with c:
                # Geen API-body of credentials in het verslag.
                c.execute("UPDATE scope SET fout=? WHERE id=?", (type(e).__name__ + ": bron niet leesbaar", s["id"]))
            raise
    return aantal


def hoofdstukken(tekst, letters):
    """De tekst van de hoofdstukken die deze agents vertalen, bv. A en B.

    Een hoofdstuk loopt van een kop 'A. ...' van niveau 1 of 2 tot de volgende
    kop van niveau 1 of 2, met de Markdown-regels: tot drie spaties ervoor, een
    spatie of tab erna. Koppen in een codeblok (``` of ~~~) tellen niet, zodat
    een sjabloon geen grens maakt. Alleen een kop die precies 'B. tekst' is,
    telt als hoofdstuk. Een gevraagd hoofdstuk dat ontbreekt of twee keer
    voorkomt, een andere kop met 'B.' erin, of een gewone regel die na het
    weghalen van HTML en tekens vooraan met 'B.' begint, maakt de bron
    onbruikbaar: dan pauzeert de toetsing liever dan een regel te missen. Het
    boek heeft zulke regels alleen als hoofdstukkop.
    """
    uit, huidig, gezien, hek = [], None, [], ""
    # Elke letter in elk schrift (ook een Griekse of brede B), niet in een afkorting als 'o.a.'.
    verdacht = re.compile(r"(?<![\w.])[^\W\d_]\.(?![\w.])")
    for regel in tekst.splitlines():
        rand = re.match(r" {0,3}(`{3,}|~{3,})", regel)
        if hek:
            if rand and rand[1][0] == hek[0] and len(rand[1]) >= len(hek) and not regel.strip(" `~"):
                hek = ""
        elif rand:
            hek = rand[1]
        else:
            vorm = unicodedata.normalize("NFKC", regel)
            kop = re.match(r" {0,3}(#{1,2})(?:[ \t]+(.*))?$", vorm)
            if kop:
                letter = re.fullmatch(r"([A-Z])\.[ \t]+\S.*", (kop[2] or "").strip())
                huidig = letter[1] if letter else None
                if huidig:
                    gezien.append(huidig)
                elif verdacht.search(re.sub(r"<[^>]*>", "", kop[2] or "")):
                    raise ValueError("onduidelijke hoofdstukkop in het regelboek")
            elif verdacht.match(re.sub(r"^[\W_]+", "", re.sub(r"<[^>]*>", "", vorm))):
                raise ValueError("onduidelijke hoofdstukkop in het regelboek")
        if huidig in letters:
            uit.append(regel.rstrip())
    if any(gezien.count(x) != 1 for x in letters):
        raise ValueError("hoofdstuk ontbreekt of staat dubbel in het regelboek")
    return "\n".join(uit)


def controleer_regelbron(c, regels, rpc, download, force=False):
    vorige = instelling(c, "regelbron") or {}
    bron = regels["regelbron"]
    stand = {"ts": time.time(), "versie": bron["versie"], "pad": bron["pad"], "geldig": False,
             "verbinding": bron.get("verbinding"), "namespace": bron.get("namespace")}
    try:
        # T-0028, 29-10-2026: de agents vertalen alleen hoofdstuk A en B. Een
        # nieuwere versie van het boek is geldig zolang die hoofdstukken gelijk
        # zijn aan wat vastgepind is; wijzigen ze, dan pauzeert de H-A-toetsing.
        # Zo breekt een verhuizing van de oude versie naar archief/ niets meer.
        map_pad = str(PurePosixPath(bron["pad"]).parent)
        naam = PurePosixPath(bron["pad"]).name
        match = re.fullmatch(r"(.+ v)(\d+(?:\.\d+)*)\.md", naam, re.I)
        if not match:
            raise ValueError("vastgepinde versie niet herkenbaar")
        gepind = tuple(int(x) for x in match[2].split("."))
        hoogste = None
        vervolg = None
        while True:
            pagina = (rpc("files/list_folder/continue", {"cursor": vervolg}) if vervolg else
                      rpc("files/list_folder", {"path": map_pad, "recursive": False, "limit": 500}))
            if (not isinstance(pagina, dict) or not isinstance(pagina.get("entries"), list)
                    or type(pagina.get("has_more")) is not bool):
                raise RuntimeError("regelboekmap niet leesbaar")
            for e in pagina["entries"]:
                n = e.get("name", "")
                kandidaat = re.fullmatch(re.escape(match[1]) + r"(\d+(?:\.\d+)*)\.md", n, re.I)
                if e.get(".tag") == "file" and kandidaat:
                    versie = tuple(int(x) for x in kandidaat[1].split("."))
                    if hoogste is None or versie > hoogste[0]:
                        hoogste = (versie, n)
            if not pagina["has_more"]:
                break
            vervolg = pagina.get("cursor")
            if not vervolg:
                raise RuntimeError("regelboekmapcursor ontbreekt")
        if hoogste is None or hoogste[0] < gepind:
            raise ValueError("regelboek niet beschikbaar")
        gelezen = match[1] + ".".join(str(x) for x in hoogste[0])
        pad = map_pad + "/" + hoogste[1]
        stand.update({"gelezen": gelezen, "pad": pad})
        meta = rpc("files/get_metadata", {"path": pad})
        if not meta or meta.get(".tag") != "file" or meta.get("size", 0) > 500000:
            raise ValueError("regelboek niet beschikbaar")
        if (not force and vorige.get("geldig") and vorige.get("rev") and
                vorige["rev"] == meta.get("rev") and vorige.get("pad") == pad and
                vorige.get("hoofdstukken_sha256") == bron["hoofdstukken_sha256"] and
                time.time() - vorige.get("ts", 0) < 86400):
            return vorige
        inhoud = download(pad, maximum=500001)
        stand["sha256"] = hashlib.sha256(inhoud).hexdigest()
        stand["rev"] = meta.get("rev", "")
        deel = hoofdstukken(inhoud.decode("utf-8"), bron["hoofdstukken"])
        stand["hoofdstukken_sha256"] = hashlib.sha256(deel.encode("utf-8")).hexdigest()
        stand["geldig"] = stand["hoofdstukken_sha256"] == bron["hoofdstukken_sha256"]
        letters = " en ".join(bron["hoofdstukken"])
        if stand["geldig"]:
            stand["status"] = ("bevestigde bron gelezen" if hoogste[0] == gepind else
                               f"{gelezen} gelezen; hoofdstuk {letters} gelijk aan vastgepinde {bron['versie']}")
        elif hoogste[0] > gepind:
            stand["gevonden"] = gelezen
            stand["status"] = f"{gelezen} gevonden, niet bevestigd; vastgepind {bron['versie']}; hoofdstuk {letters} gewijzigd"
        else:
            stand["status"] = "regelboek gewijzigd; H-A-toetsing gepauzeerd"
    except Exception as e:
        stand["status"] = type(e).__name__ + ": regelboek niet leesbaar; H-A-toetsing gepauzeerd"
    with c:
        instelling(c, "regelbron", stand)
    return stand


def kinderen(c, rij):
    prefix = rij["pad"].rstrip("/") + "/"
    ondergrens = prefix.casefold()
    bovengrens = ondergrens[:-1] + "0"
    return [dict(x) for x in c.execute("SELECT * FROM item WHERE scope=? AND actief=1 AND pad_sleutel>=? AND pad_sleutel<?",
                                     (rij["scope"], ondergrens, bovengrens))
            if "/" not in x["pad_sleutel"][len(ondergrens):]]


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
    is_project = is_projectmap(rij, regels)
    is_moment = rij["profiel"] == "ha_project" and parent == regels["ha"]["communicatie"] and momentnaam(naam, regels)
    bases = [p["prefix"] for p in regels["profielen"] if p["profiel"] == "ha_sales"]
    is_sales = rij["profiel"] == "ha_sales" and any(str(PurePosixPath(rij["pad"]).parent).casefold() == b.casefold() for b in bases)
    if not (is_project or is_moment or is_sales):
        return []
    namen = {e["naam"] for e in kinderen(c, rij)}
    if is_project:
        if regels["ha"]["communicatie"] not in namen:
            fouten.append(("HA A1", "Centrale communicatiemap ontbreekt. Voorgesteld doel: " + rij["pad"] + "/_00. Communication. Maak eerst een samenvoegvoorstel met bestaande bronmappen; verplaats niets automatisch."))
        if namen & set(regels["ha"]["oude_communicatie"]):
            fouten.append(("HA A1 oude indeling", "Oude communicatie-indeling aanwezig. Laat Benamingenwacht en Mappenwacht samen het doelpad voorstellen; behoud alle bronbestanden."))
    if is_moment:
        if "00 verslag.md" not in namen:
            fouten.append(("HA B1", "Verplicht verslag ontbreekt volgens de volledige metadata-index. Voorgesteld doel: " + rij["pad"] + "/00 verslag.md. Stel verwerking van bestaand momentmateriaal voor, zonder inhoud te verzinnen."))
    if is_sales:
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
    alleen_geldig = "" if ha else " AND i.profiel NOT GLOB 'ha_*'"
    actief = [r["id"] for r in regels["roots"]] + ["lokaal:agenda", "lokaal:gesprekken"]
    bronfilter = " AND i.scope IN (" + ",".join("?" for _ in actief) + ")"
    bereiken = ha_bereiken(regels)
    ha_filter = ""
    ha_params = []
    if bereiken:
        voorwaarden = []
        for b, opslag in bereiken:
            p = b["pad"].casefold()
            voorwaarden.append("(i.scope=? AND (i.pad_sleutel=? OR (i.pad_sleutel>=? AND i.pad_sleutel<?)) "
                               "AND EXISTS(SELECT 1 FROM scope h WHERE h.id=? AND h.compleet=1 AND h.meer=0 AND h.fout=''))")
            ha_params.extend((opslag, p, p + "/", p + "0", b["id"]))
        ha_filter = " AND (i.profiel NOT GLOB 'ha_*' OR (" + " OR ".join(voorwaarden) + "))"
        dekking = "(i.scope LIKE 'lokaal:%' OR (i.profiel NOT GLOB 'ha_*' AND s.compleet=1 AND s.meer=0) OR i.profiel GLOB 'ha_*')"
        bron_ok = "(s.fout='' OR i.profiel GLOB 'ha_*')"
    else:
        dekking = "(i.scope LIKE 'lokaal:%' OR (s.compleet=1 AND s.meer=0))"
        bron_ok = "s.fout=''"
    basis = (f"SELECT i.* FROM item i JOIN scope s ON s.id=i.scope WHERE i.actief=1 AND i.{veld}=1 "
             "AND " + bron_ok + " AND " + dekking + alleen_geldig + bronfilter + ha_filter)
    limiet = budget or regels["item_budget_per_agent"]
    # H1-4, driehoeksoverleg C2, 17-10-2026: twee begrensde queries geven
    # H-A voorrang zonder alle vuile items voor één globale sortering te lezen.
    rows = c.execute(basis + " AND i.profiel GLOB 'ha_*' ORDER BY i.rowid LIMIT ?",
                     actief + ha_params + [limiet]).fetchall() if ha else []
    if len(rows) < limiet:
        rows += c.execute(basis + " AND i.profiel NOT GLOB 'ha_*' ORDER BY i.rowid LIMIT ?",
                          actief + ha_params + [limiet - len(rows)]).fetchall()
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
                    c.execute("""INSERT INTO item(scope,identiteit,pad,pad_sleutel,naam,soort,firma,profiel,gegevens)
                      VALUES(?,?,?,?,?,'metadata','onbekend','lokale metadata',?) ON CONFLICT(scope,identiteit)
                      DO UPDATE SET pad=excluded.pad,pad_sleutel=excluded.pad_sleutel,naam=excluded.naam,gegevens=excluded.gegevens,actief=1,naam_vuil=1""",
                              (scope, identiteit, pad, pad.casefold(), naam, json.dumps(info, ensure_ascii=False)))
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
    scopes = [dict(r) for r in c.execute("SELECT id,pad,namespace,verbinding,compleet,meer,poging,gelukt,fout,controle FROM scope ORDER BY id")]
    actief = {r["id"] for r in regels["roots"]} | {"lokaal:agenda", "lokaal:gesprekken"}
    bereiken = ha_bereiken(regels)
    ingestelde_bereiken = actief | {b["id"] for b, _ in bereiken}
    bronfilter = "scope IN (" + ",".join("?" for _ in actief) + ")"
    telling = {a: c.execute("SELECT count(*) FROM bevinding WHERE agent=? AND status='open' AND " + bronfilter, [a] + sorted(actief)).fetchone()[0]
               for a in ("benamingen-wacht", "mappen-wacht")}
    for s in scopes:
        s["ingesteld"] = s["id"] in ingestelde_bereiken
        # Virtuele H-A-bereiken bezitten de cursor; items blijven in Work All.
        opslag = next((ouder for b, ouder in bereiken if b["id"] == s["id"]), s["id"])
        prefix = next((b["pad"].casefold() for b, _ in bereiken if b["id"] == s["id"]), None)
        grens = " AND (pad_sleutel=? OR (pad_sleutel>=? AND pad_sleutel<?))" if prefix else ""
        args = (opslag, prefix, prefix + "/", prefix + "0") if prefix else (opslag,)
        if not prefix and any(ouder == s["id"] for _, ouder in bereiken):
            grens = " AND profiel NOT GLOB 'ha_*'"
        s["items"] = c.execute("SELECT count(*) FROM item WHERE scope=? AND actief=1" + grens, args).fetchone()[0]
        s["achterstand_naam"] = c.execute("SELECT count(*) FROM item WHERE scope=? AND actief=1 AND naam_vuil=1" + grens, args).fetchone()[0]
        s["achterstand_structuur"] = c.execute("SELECT count(*) FROM item WHERE scope=? AND actief=1 AND structuur_vuil=1" + grens, args).fetchone()[0]
    out = {"versie": "1.1", "gemaakt": nu(), "laatste_agent": agent, "scopes": scopes,
           "regelbron": instelling(c, "regelbron"), "tellingen": telling, "niet_gecontroleerd": regels["niet_gecontroleerd"]}
    for a in ("benamingen-wacht", "mappen-wacht"):
        stand = instelling(c, "ronde:" + a)
        if stand:
            out.setdefault("rondes", {})[a] = stand
    return out

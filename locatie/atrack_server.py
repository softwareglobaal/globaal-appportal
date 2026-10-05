"""Ontvanger voor de GPS-tracker in de auto (@Track over TCP).

De telefoon stuurt HTTPS naar /pub; die weg loopt langs de webserver en de
inlogbeveiliging. Een tracker kan dat niet: hij spreekt zijn eigen protocol over
een kale TCP-verbinding. Daarom dit tweede, kleine proces naast de webapp. Het
schrijft in dezelfde database, zodat de dagindeling beide bronnen samen leest.

Vijf afspraken die hier worden nagekomen, elk uit een eerdere fout of eis:

1. **Pas bevestigen nadat het punt in de database staat.** Het toestel wacht op
   `+SACK` en stuurt het bericht anders opnieuw. Zouden we meteen bevestigen,
   dan is een punt kwijt zodra het schrijven misgaat.
2. **De HDOP is geen onzekerheid in meter.** Hij gaat in een eigen kolom; de
   kolom `acc` blijft leeg voor deze bron.
3. **Meettijd en verzendtijd blijven apart.** Bij een nagestuurd bericht
   (`+BUFF`) liggen die ver uit elkaar; `gebufferd` markeert dat.
4. **Alleen bekende toestellen.** De poort staat open op het internet, dus een
   bericht van een onbekend IMEI wordt geteld en weggegooid.
5. **Elk bericht één keer, herleidbaar.** Het ruwe bericht gaat eerst naar de tabel
   `bericht` (met toestel, soort, teller en hoe vaak het binnenkwam), daarna elk
   positieblok als punt met sleutel (bron, tst, berichtsoort, volgnr). Tot
   04-10-2026 was de sleutel (bron, tst): een "motor aan" zonder fix draagt de
   meettijd van het "motor uit" ervoor en verdween stil, terwijl de log "bewaard"
   zei (gemeten: 27 in de log, 5 in de database). "bewaard" betekent nu dat het
   bericht er na de commit echt staat.

Of een punt meetelt (startgrens, toegestaan toestel) beslist niet deze ontvanger
maar het bronbeleid bij het lezen: hier wordt alles van een bekend toestel bewaard.

Starten:  ATRACK_IMEIS="<imei>:auto" python3 atrack_server.py   (het echte IMEI staat alleen in .env)
"""
import os
import re
import socketserver
import sqlite3
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atrack  # noqa: E402

POORT = int(os.environ.get("ATRACK_POORT", "5027"))
DB_PAD = os.environ.get("LOCATIE_DB", "/data/locatie.db")
# "imei:naam,imei:naam". De naam komt in de kolom bron te staan. Wie hier mag
# schrijven bepaalt ATRACK_IMEIS; wat daarvan meetelt bepaalt bronbeleid.py.
import bronbeleid  # noqa: E402
TOESTELLEN = bronbeleid.toestellen_uit_env()

_slot = threading.Lock()


def schema_klaar():
    """Zorgt dat het schema op de laatste versie staat voor het eerste bericht.

    De webapp draait in een andere container en kan net herstart zijn zonder dat er
    al een verzoek binnenkwam. 03-10-2026 stond de ontvanger te luisteren terwijl een
    kolom nog niet bestond. De upgrade zelf staat in schema.py: één transactie, met
    een kopie vooraf, en veilig als de webapp hem tegelijk probeert.
    """
    import schema                 # noqa: PLC0415
    return schema.migreer(DB_PAD)


def _verbinding():
    conn = sqlite3.connect(DB_PAD, timeout=30, isolation_level=None)
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


IMEI_RE = re.compile(r"(?<!\d)(\d{11})(\d{4})(?!\d)")


def gemaskeerd(tekst):
    """Een toestelidentiteit hoort niet in een gewone log (controle 05-10-2026): alleen de laatste vier cijfers."""
    return IMEI_RE.sub(lambda m: "…" + m.group(2), tekst or "")


def verdacht_reden(conn, bron, bericht, positie):
    """Waarom dit bericht van een toegelaten IMEI toch niet vertrouwd wordt, of None.

    Het IMEI is geen geheim (het stond in de publieke geschiedenis van de repo), dus dit
    zijn aanwijzingen, geen authenticatie: een andere protocolversie dan het echte toestel
    meldt, een toestelnaam die niet klopt (als het beleid er een vastlegt), of een sprong die
    geen auto kan maken. Verdacht wordt bewaard en getoond, maar telt nergens mee.
    """
    import bronbeleid as B         # noqa: PLC0415
    beleid = B.BRONNEN.get(bron) or {}
    verwacht = beleid.get("protocolversie")
    if verwacht and bericht.get("protocol") and bericht["protocol"] != verwacht:
        return "protocolversie %s, verwacht %s" % (bericht["protocol"], verwacht)
    naam = beleid.get("toestelnaam_sha256")
    if naam and B.vingerafdruk(bericht.get("naam") or "") != naam:
        return "toestelnaam klopt niet"
    if positie and positie.get("fix_geldig") and positie.get("tst"):
        vorig = conn.execute(
            """SELECT tst, lat, lon FROM punt WHERE toestel = ? AND fix = 1 AND verdacht IS NULL AND tst < ?
               ORDER BY tst DESC LIMIT 1""", (bericht.get("imei"), positie["tst"])).fetchone()
        if vorig:
            meter = B_afstand(vorig[1], vorig[2], positie["lat"], positie["lon"])
            seconden = max(positie["tst"] - vorig[0], 1)
            if meter > 5000 and meter / seconden * 3.6 > 300:
                return "sprong van %d km in %d s" % (meter // 1000, seconden)
    return None


def B_afstand(lat1, lon1, lat2, lon2):
    from math import asin, cos, radians, sin, sqrt  # noqa: PLC0415
    a = sin(radians(lat2 - lat1) / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * asin(sqrt(a))


def schrijf(bericht):
    """Eén bericht opslaan: het ruwe bericht en elk positieblok erin.

    Geeft (status, aantal_nieuwe_punten). status is 'bewaard' (alle posities staan erin),
    'deels' (het ruwe bericht staat erin, niet alle posities), 'dubbel' (exact dit bericht
    stond er al: opnieuw verstuurd of uit de buffer), 'geen meting' (geen positie) of
    'onvolledig' (minder posities herkend dan het bericht meldt). Gooit een fout als het
    schrijven mislukt; dan vertrekt er geen bevestiging en stuurt het toestel opnieuw.

    Elk positieblok krijgt sleutel (bericht_id, volgnr): twee verschillende meldingen met
    dezelfde oude fixtijd blijven twee punten (controle 05-10-2026). De gebeurtenistijd
    (moment) staat apart van de fixtijd (tst) en de ontvangsttijd.
    """
    import schema                 # noqa: PLC0415
    bron = TOESTELLEN.get(bericht.get("imei") or "")
    if not bron:
        return "onbekend toestel", 0
    ruw = bericht["ruw"]
    afdruk = schema.vingerafdruk_bericht(ruw)
    posities = bericht.get("posities") or []
    nu = int(time.time())
    herkend = bericht.get("posities_volledig", True)

    with _slot:
        conn = _verbinding()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                rij = conn.execute("SELECT id FROM bericht WHERE vingerafdruk = ?", (afdruk,)).fetchone()
                if not rij and bericht.get("teller") and bericht.get("verzonden"):
                    # Dezelfde melding met een andere kop (+RESP of +BUFF) of een kleine afwijking:
                    # zelfde toestel, soort, teller en verzendtijd is hetzelfde bericht.
                    rij = conn.execute("""SELECT id FROM bericht WHERE toestel = ? AND soort = ? AND teller = ?
                                          AND verzonden = ?""",
                                       (bericht.get("imei"), bericht.get("soort"), bericht["teller"],
                                        bericht["verzonden"])).fetchone()
                if rij:
                    conn.execute("UPDATE bericht SET aantal = aantal + 1, laatst_ontvangen = ? WHERE id = ?",
                                 (nu, rij[0]))
                    conn.execute("COMMIT")
                    return "dubbel", 0
                reden = verdacht_reden(conn, bron, bericht, posities[0] if posities else None)
                cur = conn.execute(
                    """INSERT INTO bericht (ontvangen, laatst_ontvangen, bron, toestel, protocol, kop, soort,
                                            protocolversie, teller, verzonden, posities_gemeld, verwerking,
                                            vingerafdruk, ruw, verdacht)
                       VALUES (?, ?, ?, ?, 'atrack', ?, ?, ?, ?, ?, ?, '', ?, ?, ?)""",
                    (nu, nu, bron, bericht.get("imei"), bericht.get("kop"), bericht.get("soort"),
                     bericht.get("protocol"), bericht.get("teller"), bericht.get("verzonden"),
                     bericht.get("posities_gemeld") or 0, afdruk, ruw[:8000], reden))
                bid = cur.lastrowid
                nieuw = 0
                for volgnr, p in enumerate(posities):
                    if not p.get("tst") or p.get("lat") is None or p.get("lon") is None:
                        continue
                    fix = 1 if p.get("fix_geldig") else 0
                    moment = p["tst"] if fix else bericht.get("verzonden")     # onbekend blijft onbekend
                    c = conn.execute(
                        """INSERT INTO punt (tst, lat, lon, alt, vel, soort, ruw, motion, gebeurtenis, ontvangen,
                                             bron, hdop, satellieten, fix, verzonden, gebufferd,
                                             toestel, berichtsoort, volgnr, bericht_id, teller, moment, verdacht)
                           VALUES (?, ?, ?, ?, ?, 'location', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(bericht_id, volgnr) DO NOTHING""",
                        (p["tst"], p["lat"], p["lon"],
                         int(p["hoogte"]) if p.get("hoogte") is not None else None,
                         int(p.get("snelheid") or 0), ruw[:4000], p.get("motion"), bericht.get("gebeurtenis"),
                         nu, bron, p.get("hdop"), p.get("satellieten"), fix,
                         bericht.get("verzonden"), 1 if bericht.get("gebufferd") else 0,
                         bericht.get("imei"), bericht.get("soort") or "", volgnr, bid, bericht.get("teller"),
                         moment, reden))
                    nieuw += c.rowcount
                if not bericht.get("positie"):
                    verwerking = "geen positie"
                elif not herkend:
                    verwerking = "onvolledig: %d van de %d posities herkend" % (len(posities),
                                                                               bericht.get("posities_gemeld") or 0)
                elif nieuw < len(posities):
                    verwerking = "deels: %d van de %d posities bewaard" % (nieuw, len(posities))
                else:
                    verwerking = "punten"
                conn.execute("UPDATE bericht SET posities_bewaard = ?, verwerking = ? WHERE id = ?",
                             (nieuw, verwerking, bid))
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()
    if not bericht.get("positie"):
        return "geen meting", 0
    if not herkend:
        return "onvolledig", nieuw
    if nieuw < len(posities):
        return "deels", nieuw
    return ("verdacht" if reden else "bewaard"), nieuw


def antwoord(bericht):
    """Het bevestigingsbericht dat het toestel verwacht, of niets.

    Vorm uit de handleiding: `+SACK:<teller>$`, en voor een hartslag
    `+SACK:GTHBD,<protocolversie>,<teller>$`.
    """
    teller = bericht.get("teller")
    if not teller:
        return None
    if bericht.get("soort") == "HBD":
        return "+SACK:GTHBD,%s,%s$" % (bericht.get("protocol") or "", teller)
    return "+SACK:%s$" % teller


def verwerk(regel):
    """Eén regel binnen: opslaan, en teruggeven wat terug moet.

    Een bericht dat al binnen was (opnieuw verstuurd, of nagestuurd uit de buffer)
    wordt opnieuw bevestigd, anders blijft het toestel het sturen; het wordt niet
    nog eens bewaard. Een onvolledig ontleed bericht wordt bevestigd omdat het ruwe
    bericht veilig staat; het staat in `bericht` met verwerking 'onvolledig'.
    """
    bericht = atrack.ontleed(regel)
    if not bericht:
        return None, "onleesbaar"
    if bericht.get("imei") not in TOESTELLEN:
        return None, "onbekend toestel"
    wat, _ = schrijf(bericht)
    # Bevestigen pas hierna: het toestel mag zijn kopie niet wissen voordat
    # onze database het bericht heeft.
    return antwoord(bericht), wat


class Verbinding(socketserver.StreamRequestHandler):
    timeout = 180

    def handle(self):
        buffer = ""
        while True:
            try:
                brok = self.connection.recv(4096)
            except OSError:
                return
            if not brok:
                return
            buffer += brok.decode("latin-1", "replace")
            # Berichten eindigen op $; alles daarvoor is één regel.
            while "$" in buffer:
                regel, buffer = buffer.split("$", 1)
                regel = (regel + "$").strip()
                if not regel.startswith("+"):
                    continue
                terug, wat = verwerk(regel)
                # Alles staat voluit in de tabel bericht; de log toont een begin, zonder toestelidentiteit.
                print("%s %s %s" % (time.strftime("%Y-%m-%dT%H:%M:%S"), wat,
                                    gemaskeerd(regel[:90] if wat in ("bewaard", "dubbel") else regel)),
                      flush=True)
                if terug:
                    try:
                        self.connection.sendall(terug.encode("ascii"))
                    except OSError:
                        return
            if len(buffer) > 65536:        # onzin: gooi weg, houd de poort open
                buffer = ""


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    if not TOESTELLEN:
        print("ATRACK_IMEIS is leeg: elk bericht zou geweigerd worden", flush=True)
    schema_klaar()
    print("luistert op poort %d, database %s, toestellen: %s"
          % (POORT, DB_PAD, ", ".join("%s (%s)" % (bronbeleid.toestel_kort(i), n) for i, n in TOESTELLEN.items())
             or "geen"), flush=True)
    Server(("0.0.0.0", POORT), Verbinding).serve_forever()

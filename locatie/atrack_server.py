"""Ontvanger voor de GPS-tracker in de auto (@Track over TCP).

De telefoon stuurt HTTPS naar /pub; die weg loopt langs de webserver en de
inlogbeveiliging. Een tracker kan dat niet: hij spreekt zijn eigen protocol over
een kale TCP-verbinding. Daarom dit tweede, kleine proces naast de webapp. Het
schrijft in dezelfde database, zodat de dagindeling beide bronnen samen leest.

Vier afspraken die hier worden nagekomen, elk uit een eerdere fout of eis:

1. **Pas bevestigen nadat het punt in de database staat.** Het toestel wacht op
   `+SACK` en stuurt het bericht anders opnieuw. Zouden we meteen bevestigen,
   dan is een punt kwijt zodra het schrijven misgaat.
2. **De HDOP is geen onzekerheid in meter.** Hij gaat in een eigen kolom; de
   kolom `acc` blijft leeg voor deze bron.
3. **Meettijd en verzendtijd blijven apart.** Bij een nagestuurd bericht
   (`+BUFF`) liggen die ver uit elkaar; `gebufferd` markeert dat.
4. **Alleen bekende toestellen.** De poort staat open op het internet, dus een
   bericht van een onbekend IMEI wordt geteld en weggegooid.

Starten:  ATRACK_IMEIS="869226070029427:auto" python3 atrack_server.py
"""
import os
import socketserver
import sqlite3
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atrack  # noqa: E402

POORT = int(os.environ.get("ATRACK_POORT", "5027"))
DB_PAD = os.environ.get("LOCATIE_DB", "/data/locatie.db")
# "imei:naam,imei:naam". De naam komt in de kolom bron te staan.
TOESTELLEN = {}
for stuk in os.environ.get("ATRACK_IMEIS", "").split(","):
    if ":" in stuk:
        imei, naam = stuk.split(":", 1)
        TOESTELLEN[imei.strip()] = naam.strip() or "auto"

_slot = threading.Lock()


def schrijf(bericht):
    """Eén bericht opslaan. Geeft True als het punt er daarna staat.

    Niet elk bericht is een meting: een hartslag of een bevestiging heeft geen
    positie. Die worden wel beantwoord, maar niet bewaard.
    """
    bron = TOESTELLEN.get(bericht.get("imei") or "")
    if not bron or not bericht.get("positie") or not bericht.get("tst"):
        return False
    # Wat de telefoon als motion meestuurt, moet hier afgeleid worden: de
    # dagindeling breekt een verblijf op 'automotive'. Rijden is het enige wat
    # deze bron kan zien, en stilstand herkennen we aan de snelheid en aan de
    # gebeurtenis 'motor uit'.
    snelheid = bericht.get("snelheid") or 0
    if bericht.get("gebeurtenis") == "motor uit":
        motion = "stationary"
    elif snelheid >= 5 or bericht.get("gebeurtenis") == "motor aan":
        motion = "automotive"
    else:
        motion = "stationary"

    with _slot:
        conn = sqlite3.connect(DB_PAD, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                """INSERT INTO punt (tst, lat, lon, alt, vel, soort, ruw, motion,
                                     gebeurtenis, ontvangen, bron,
                                     hdop, satellieten, fix, verzonden, gebufferd)
                   VALUES (:tst, :lat, :lon, :alt, :vel, 'location', :ruw, :motion,
                           :gebeurtenis, :ontvangen, :bron,
                           :hdop, :satellieten, :fix, :verzonden, :gebufferd)
                   ON CONFLICT(bron, tst) DO NOTHING""",
                {"tst": bericht["tst"], "lat": bericht["lat"], "lon": bericht["lon"],
                 "alt": int(bericht["hoogte"]) if bericht.get("hoogte") is not None else None,
                 "vel": int(snelheid), "ruw": bericht["ruw"][:4000],
                 "motion": motion, "gebeurtenis": bericht.get("gebeurtenis"),
                 "ontvangen": int(time.time()), "bron": bron,
                 "hdop": bericht.get("hdop"), "satellieten": bericht.get("satellieten"),
                 "fix": 1 if bericht.get("fix_geldig") else 0,
                 "verzonden": bericht.get("verzonden"),
                 "gebufferd": 1 if bericht.get("gebufferd") else 0})
            conn.commit()
            return True
        finally:
            conn.close()


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
    """Eén regel binnen: opslaan waar nodig, en teruggeven wat terug moet."""
    bericht = atrack.ontleed(regel)
    if not bericht:
        return None, "onleesbaar"
    if bericht.get("imei") not in TOESTELLEN:
        return None, "onbekend toestel"
    bewaard = schrijf(bericht)
    # Bevestigen pas hierna: het toestel mag zijn kopie niet wissen voordat
    # onze database het punt heeft.
    return antwoord(bericht), ("bewaard" if bewaard else "geen meting")


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
                print("%s %s %s" % (time.strftime("%H:%M:%S"), wat, regel[:90]),
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
    print("luistert op poort %d, database %s, toestellen: %s"
          % (POORT, DB_PAD, ", ".join(TOESTELLEN) or "geen"), flush=True)
    Server(("0.0.0.0", POORT), Verbinding).serve_forever()

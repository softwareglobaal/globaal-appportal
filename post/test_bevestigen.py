"""Controle op de tweestapsverzending: niets vertrekt zonder bevestiging.

Draait zonder mailserver: het echte versturen is vervangen door een teller.

    python post/test_bevestigen.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

TMP = tempfile.mkdtemp()
with open(os.path.join(TMP, "mailboxen.yaml"), "w", encoding="utf-8") as f:
    f.write("mailboxen:\n"
            "  - adres: test@voorbeeld.be\n"
            "    imap_host: imap.voorbeeld.be\n"
            "    wachtwoord: x\n"
            "    groepen: [proef]\n"
            "    verzenden: ja\n"
            "    doorsturen: [boekhouding@voorbeeld.be]\n"
            "    smtp_host: smtp.voorbeeld.be\n")
os.environ.update(POSTBUS_CONFIG=os.path.join(TMP, "mailboxen.yaml"),
                  POSTBUS_WACHT_MAP=os.path.join(TMP, "wacht"),
                  MCP_TOKEN="proeftoken", POSTBUS_TOKEN_GROEPEN="proef")

import app as appmod     # noqa: E402
import verzenden         # noqa: E402

verstuurd, doorgestuurd = [], []


def nep_voorbereiden(mailbox, aan, onderwerp, tekst, cc=None,
                     antwoord_op=None, van_map="INBOX", wie=None):
    return {"van": mailbox["adres"], "aan": [aan], "cc": [],
            "onderwerp": onderwerp, "tekst": tekst, "antwoord_op": antwoord_op,
            "antwoord_op_bericht": None, "map": van_map}


def nep_verstuur(mailbox, aan, onderwerp, tekst, cc=None, antwoord_op=None,
                 van_map="INBOX", wie=None, verwacht=None):
    verstuurd.append({"aan": aan, "onderwerp": onderwerp, "tekst": tekst,
                      "verwacht": verwacht is not None})
    return {"aan": [aan], "vandaag_verstuurd": 1, "dagplafond": 100}


def nep_doorsturen_voorbereiden(mailbox, mapnaam, uid, naar, notitie=None):
    return {"van": mailbox["adres"], "naar": naar, "onderwerp": "Fwd: x",
            "notitie": notitie or "", "origineel": {}, "map": mapnaam,
            "uid": int(uid)}


def nep_doorsturen(mailbox, mapnaam, uid, naar, notitie=None):
    doorgestuurd.append({"uid": uid, "naar": naar})
    return {"map": mapnaam, "uid": uid, "naar": naar,
            "vandaag_verstuurd": 1, "dagplafond": 100}


ECHT_VERSTUUR = verzenden.verstuur
verzenden.verstuur_voorbereiden = nep_voorbereiden
verzenden.verstuur = nep_verstuur
verzenden.doorsturen_voorbereiden = nep_doorsturen_voorbereiden
verzenden.doorsturen = nep_doorsturen

client = appmod.app.test_client()
KOP = {"Authorization": "Bearer proeftoken"}


def roep(tool, **args):
    r = client.post("/mcp", headers=KOP, json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool, "arguments": args}})
    res = r.get_json()["result"]
    tekst = res["content"][0]["text"]
    return res["isError"], (tekst if res["isError"] else json.loads(tekst))


def gelijk(gekregen, verwacht, wat):
    if gekregen != verwacht:
        raise AssertionError(f"{wat}: verwacht {verwacht!r}, kreeg {gekregen!r}")
    print(f"  ok  {wat}")


print("versturen")
fout, uit = roep("versturen", mailbox="test@voorbeeld.be",
                 aan="klant@elders.be", onderwerp="Offerte", tekst="Beste,")
gelijk(fout, False, "eerste aanroep lukt")
gelijk(uit["status"], "WACHT_OP_TOESTEMMING", "eerste aanroep geeft een concept")
gelijk(verstuurd, [], "eerste aanroep verstuurt niets")
gelijk(uit["concept"]["aan"], ["klant@elders.be"], "concept toont de ontvanger")
gelijk(uit["concept"]["van"], "test@voorbeeld.be", "concept toont de afzender")
code = uit["bevestig"]

fout, _ = roep("versturen", mailbox="test@voorbeeld.be", bevestig=code)
gelijk(fout, False, "bevestigen lukt")
gelijk(len(verstuurd), 1, "na bevestigen is er precies een bericht weg")
gelijk(verstuurd[0]["aan"], "klant@elders.be", "het getoonde adres is gebruikt")
gelijk(verstuurd[0]["verwacht"], True, "verstuur toetst tegen het concept")

fout, tekst = roep("versturen", mailbox="test@voorbeeld.be", bevestig=code)
gelijk(fout, True, "dezelfde code nog eens werkt niet")
gelijk(len(verstuurd), 1, "er vertrekt geen tweede bericht")

fout, tekst = roep("versturen", mailbox="test@voorbeeld.be",
                   bevestig="deadbeef")
gelijk(fout, True, "een verzonnen code werkt niet")

fout, tekst = roep("versturen", mailbox="test@voorbeeld.be", aan="x@y.be",
                   onderwerp="zonder tekst")
gelijk(fout, True, "zonder tekst geen concept")

print("doorsturen")
fout, uit = roep("doorsturen", mailbox="test@voorbeeld.be", uid=7,
                 naar="boekhouding@voorbeeld.be")
gelijk(uit["status"], "WACHT_OP_TOESTEMMING", "doorsturen geeft eerst een concept")
gelijk(doorgestuurd, [], "en stuurt nog niets door")
fout, tekst = roep("versturen", mailbox="test@voorbeeld.be",
                   bevestig=uit["bevestig"])
gelijk(fout, True, "een doorstuurcode werkt niet bij versturen")
gelijk(verstuurd[1:], [], "en verstuurt dus ook niets")

fout, uit = roep("doorsturen", mailbox="test@voorbeeld.be", uid=7,
                 naar="boekhouding@voorbeeld.be")
fout, _ = roep("doorsturen", mailbox="test@voorbeeld.be", bevestig=uit["bevestig"])
gelijk(doorgestuurd, [{"uid": 7, "naar": "boekhouding@voorbeeld.be"}],
       "na bevestigen is het doorgestuurd, naar het getoonde adres")

print("afwijking na toestemming")
import contextlib            # noqa: E402
from email.message import EmailMessage  # noqa: E402
import config                # noqa: E402
import imapbron              # noqa: E402
import wachtrij              # noqa: E402

afgeleverd = []


@contextlib.contextmanager
def nep_sessie(mailbox):
    yield None


def bouw_met_ander_adres(M, mailbox, aan, onderwerp, tekst, cc=None,
                         antwoord_op=None, van_map="INBOX"):
    b = EmailMessage()
    b["Subject"] = onderwerp
    return b, ["iemand-anders@elders.be"], [], None


imapbron._Sessie = nep_sessie
imapbron.bouw_bericht = bouw_met_ander_adres
verzenden._afleveren = lambda mailbox, bericht: afgeleverd.append(bericht)
verzenden.ACTIEF_VERZENDEN = True   # noodrem open, zodat de concept-check telt
mb = config.zoek("test@voorbeeld.be", {"gebruiker": "x", "groepen": ["proef"]})
concept = {"van": mb["adres"], "aan": ["klant@elders.be"], "cc": [],
           "onderwerp": "Offerte", "tekst": "Beste,"}
try:
    ECHT_VERSTUUR(mb, "klant@elders.be", "Offerte", "Beste,", verwacht=concept)
    raise AssertionError("een afwijkend bericht had geweigerd moeten worden")
except ValueError as e:
    gelijk("anders vertrekken" in str(e), True,
           "wijkt de ontvanger af van het concept, dan weigert verstuur")
gelijk(afgeleverd, [], "en er is niets afgeleverd")

print("code van een ander")
code, _ = wachtrij.zet({"gebruiker": "mehdi"}, "versturen", {"van": "a"})
try:
    wachtrij.neem({"gebruiker": "angela"}, "versturen", code)
    raise AssertionError("een ander had deze code niet mogen gebruiken")
except ValueError as e:
    gelijk("andere gebruiker" in str(e), True,
           "een code van mehdi werkt niet voor angela")

print("\nalles in orde.")

"""Controle op de doorstuuragent, zonder mailserver en zonder echte verzending.

De twee dingen die hier fout mogen gaan met de grootste gevolgen:

1. Bij de eerste start alsnog de hele geschiedenis doorsturen. Dat zou honderden
   facturen in een keer naar de boekhouding jagen. De agent hoort bestaande
   berichten te onthouden en alleen nieuwe door te sturen.
2. Een bericht twee keer doorsturen na een herstart.

Beide worden hier nagespeeld met een nep-inbox en een nep-verzender, zodat er
niets verbonden of verstuurd wordt.

    python post/test_agent.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def maak_agent(tmp, onderwerp="Your receipt from Anthropic, PBC",
               naar="ap@unabo.be", backfill=False, regels=None):
    """Laadt doorstuuragent met de omgeving vooraf gezet, en vervangt de twee
    plekken die naar buiten reiken door nepversies. Met regels gelden die
    (POSTBUS_AGENT_REGELS), anders de losse variabelen."""
    import os
    os.environ["POSTBUS_AGENT_MAILBOX"] = "mch@h-architects.be"
    os.environ["POSTBUS_AGENT_ONDERWERP"] = onderwerp
    os.environ["POSTBUS_AGENT_NAAR"] = naar
    os.environ["POSTBUS_AGENT_STATE"] = str(Path(tmp) / "status.json")
    os.environ["POSTBUS_AGENT_BACKFILL"] = "ja" if backfill else ""
    os.environ["POSTBUS_AGENT_PAUZE"] = "0"   # geen wachttijd in de test
    os.environ["POSTBUS_DOORSTUREN"] = "ja"   # noodrem aan voor de test
    if regels:
        os.environ["POSTBUS_AGENT_REGELS"] = json.dumps(regels)
    else:
        os.environ.pop("POSTBUS_AGENT_REGELS", None)
    for mod in ("doorstuuragent", "verzenden"):
        sys.modules.pop(mod, None)
    import doorstuuragent as agent
    return agent


class NepInbox:
    """Een paar berichten met onderwerp en message-id. Speelt imapbron.lijst na
    zodat we de agent kunnen draaien zonder mailserver. Filtert bewust niet:
    de zoekopdracht op de server is ruimer dan de regel, en de agent moet zelf
    op onderwerp en afzender nakijken."""

    def __init__(self, berichten):
        self.berichten = berichten          # lijst dicts, nieuwste eerst
        self.doorgestuurd = []              # (uid, naar) die 'verstuurd' zijn

    def lijst(self, mailbox, mapnaam, van=None, onderwerp=None, maximaal=100,
              vanaf=0):
        treffers = list(self.berichten)
        venster = treffers[vanaf:vanaf + maximaal]
        return {"berichten": venster,
                "meer": len(treffers) > vanaf + len(venster),
                "volgende_vanaf": vanaf + len(venster)}

    def verstuur(self, mailbox, mapnaam, uid, naar, notitie=None):
        self.doorgestuurd.append((uid, naar))
        return {"verstuurd": True, "kopie_in_verzonden": True, "naar": naar}


def bericht(uid, mid, onderwerp, van="invoice@voorbeeld.test"):
    return {"uid": uid, "message_id": mid, "onderwerp": onderwerp, "van": van}


def gelijk(gekregen, verwacht, wat):
    if gekregen != verwacht:
        raise AssertionError(f"{wat}: verwacht {verwacht!r}, "
                             f"gekregen {gekregen!r}")
    print(f"  ok  {wat}")


def draai(agent, inbox):
    mailbox = {"adres": "mch@h-architects.be", "doorsturen": ["ap@unabo.be"],
               "smtp_host": "send.one.com"}
    agent.imapbron.lijst = inbox.lijst
    agent.verzenden.doorsturen = inbox.verstuur
    regel = agent._regels()[0]              # de regel uit de losse variabelen
    agent._ronde(mailbox, regel, eerste_regel=True)


ANT = "Your receipt from Anthropic, PBC #{}"


def test_eerste_start_stuurt_geschiedenis_niet_door():
    with tempfile.TemporaryDirectory() as tmp:
        agent = maak_agent(tmp)
        inbox = NepInbox([bericht(3, "<c@x>", ANT.format(3)),
                          bericht(2, "<b@x>", ANT.format(2)),
                          bericht(1, "<a@x>", ANT.format(1))])
        draai(agent, inbox)
        gelijk(inbox.doorgestuurd, [],
               "bestaande facturen worden bij de eerste start niet verstuurd")
        status = json.load(open(agent.STATUSPAD, encoding="utf-8"))
        regelstatus = list(status["regels"].values())
        gelijk(len(regelstatus[0]["gezien"]), 3, "ze zijn wel als gezien vastgelegd")


def test_oude_status_gaat_naar_de_eerste_regel():
    # Status van voor de meerdere regels (8-9-2026): plat, zonder 'regels'.
    with tempfile.TemporaryDirectory() as tmp:
        agent = maak_agent(tmp)
        with open(agent.STATUSPAD, "w", encoding="utf-8") as f:
            json.dump({"gestart": "2026-09-01T00:00:00+00:00",
                       "gezien": ["<a@x>"]}, f)
        inbox = NepInbox([bericht(2, "<b@x>", ANT.format(2)),
                          bericht(1, "<a@x>", ANT.format(1))])
        draai(agent, inbox)
        gelijk(inbox.doorgestuurd, [(2, "ap@unabo.be")],
               "na de omzetting gaat alleen het nieuwe bericht door")
        status = json.load(open(agent.STATUSPAD, encoding="utf-8"))
        gelijk("__oud__" in status["regels"], False,
               "de oude status hangt nu aan de regel")
        gelijk(list(status["regels"].values())[0]["gestart"],
               "2026-09-01T00:00:00+00:00", "met het oude starttijdstip")


def test_nieuwe_na_de_start_gaat_wel_door():
    with tempfile.TemporaryDirectory() as tmp:
        agent = maak_agent(tmp)
        inbox = NepInbox([bericht(1, "<a@x>", ANT.format(1))])
        draai(agent, inbox)                 # eerste start: a wordt onthouden
        inbox.berichten.insert(0, bericht(2, "<b@x>", ANT.format(2)))
        draai(agent, inbox)                 # b is nieuw
        gelijk(inbox.doorgestuurd, [(2, "ap@unabo.be")],
               "alleen het nieuwe bericht wordt doorgestuurd")


def test_niet_twee_keer_na_herstart():
    with tempfile.TemporaryDirectory() as tmp:
        agent = maak_agent(tmp)
        inbox = NepInbox([bericht(1, "<a@x>", ANT.format(1))])
        draai(agent, inbox)
        inbox.berichten.insert(0, bericht(2, "<b@x>", ANT.format(2)))
        draai(agent, inbox)
        # Herstart: nieuwe agent, zelfde statusbestand, zelfde inbox.
        agent2 = maak_agent(tmp)
        draai(agent2, inbox)
        gelijk(inbox.doorgestuurd, [(2, "ap@unabo.be")],
               "na een herstart wordt niets herhaald")


def test_ander_onderwerp_blijft_liggen():
    with tempfile.TemporaryDirectory() as tmp:
        agent = maak_agent(tmp)
        inbox = NepInbox([bericht(1, "<a@x>", ANT.format(1))])
        draai(agent, inbox)                 # a onthouden
        inbox.berichten.insert(0, bericht(9, "<cal@x>",
                                          "Your receipt from Calendly LLC #9"))
        inbox.berichten.insert(0, bericht(2, "<b@x>", ANT.format(2)))
        draai(agent, inbox)
        gelijk(inbox.doorgestuurd, [(2, "ap@unabo.be")],
               "Calendly valt buiten de regel en blijft liggen")


def test_andere_afzender_blijft_liggen():
    regel = {"mailbox": "mch@h-architects.be", "onderwerp": "domeinnaam",
             "van": "one.com", "naar": "ap@unabo.be"}
    with tempfile.TemporaryDirectory() as tmp:
        agent = maak_agent(tmp, regels=[regel])
        inbox = NepInbox([bericht(1, "<a@x>", "domeinnaam #1", van="noreply@one.com")])
        draai(agent, inbox)                 # a onthouden
        inbox.berichten.insert(0, bericht(3, "<c@x>", "domeinnaam #3",
                                          van="iemand@voorbeeld.test"))
        inbox.berichten.insert(0, bericht(2, "<b@x>", "domeinnaam #2",
                                          van="noreply@one.com"))
        draai(agent, inbox)
        gelijk(inbox.doorgestuurd, [(2, "ap@unabo.be")],
               "een ander afzenderadres valt buiten de regel en blijft liggen")


def test_backfill_stuurt_de_geschiedenis_wel():
    with tempfile.TemporaryDirectory() as tmp:
        agent = maak_agent(tmp, backfill=True)
        inbox = NepInbox([bericht(3, "<c@x>", ANT.format(3)),
                          bericht(2, "<b@x>", ANT.format(2)),
                          bericht(1, "<a@x>", ANT.format(1))])
        draai(agent, inbox)
        gelijk(inbox.doorgestuurd,
               [(1, "ap@unabo.be"), (2, "ap@unabo.be"), (3, "ap@unabo.be")],
               "met backfill gaan de bestaande facturen alsnog door, op volgorde")


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        print(f"\n{test.__name__}")
        test()
    print(f"\n{len(tests)} onderdelen doorlopen, alles in orde.")


if __name__ == "__main__":
    main()

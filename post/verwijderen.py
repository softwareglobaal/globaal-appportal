"""Postbus: verwijderen, naar de prullenbak van de mailbox zelf.

Dit staat bewust in een eigen bestand, los van imapbron (de leesmodule, die
blijft zonder EXPUNGE en zonder \\Deleted). Verwijderen betekent hier: het
bericht gaat naar de prullenbakmap van dezelfde mailbox. Daar kan de eigenaar
het in zijn webmail nog terugzetten; de provider ruimt de prullenbak na
verloop van tijd zelf op. De server leegt de prullenbak niet en zet zelf geen
\\Deleted: er wordt dus nooit onherstelbaar iets weggegooid vanuit deze koppeling.

Twee sloten, net als bij uitgaande post:

1. De mailbox moet 'verwijderen: ja' hebben (config.vereis_verwijderen).
2. De server-noodrem POSTBUS_VERWIJDEREN moet aanstaan. Staat die uit, dan
   verwijdert de server niets, ook niet als het bestand het toestaat.
"""
import os

import config
import imapbron

JA = {"ja", "yes", "waar", "true", "aan"}
ACTIEF = os.environ.get("POSTBUS_VERWIJDEREN", "").strip().lower() in JA

# Namen waaronder providers de prullenbak kennen (naast de \\Trash-eigenschap).
PRULLENBAK_NAMEN = ("trash", "prullenbak", "prullenmand", "deleted",
                    "verwijderd", "bin")


def _prullenbak(M):
    """De prullenbakmap: eerst op de \\Trash-eigenschap, dan op naam."""
    lijst = imapbron._lijst_mappen(M)
    for attrs, naam in lijst:
        if "\\trash" in attrs:
            return naam
    for _, naam in lijst:
        kaal = naam.lower().rsplit(".", 1)[-1]
        if kaal in PRULLENBAK_NAMEN:
            return naam
    return None


def verwijderen(mailbox, mapnaam, uid):
    """Verplaatst een bericht naar de prullenbak van dezelfde mailbox."""
    config.vereis_verwijderen(mailbox)

    if not ACTIEF:
        raise ValueError(
            "Verwijderen staat uit op deze server (POSTBUS_VERWIJDEREN). De "
            "mailbox staat het toe, de server niet. Vraag de beheerder de "
            "schakelaar om te zetten.")
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        raise ValueError(f"uid moet een getal zijn, niet {uid!r}")

    bron_map = config.map_toegestaan(mailbox, mapnaam)

    with imapbron._Sessie(mailbox) as M:
        prullenbak = _prullenbak(M)
        if not prullenbak:
            raise ValueError(
                "Geen prullenbakmap gevonden in deze mailbox, dus verwijderen "
                "kan niet veilig. Maak er eerst een aan of laat het bericht "
                "staan.")
        if bron_map.lower() == prullenbak.lower():
            raise ValueError(
                "Dit bericht staat al in de prullenbak. Definitief legen doet "
                "deze koppeling niet; dat doe je zelf in de webmail.")
        # MOVE (RFC 6851) verplaatst in een keer naar de prullenbak. Kan de
        # server het niet, dan stoppen we: kopieren, \\Deleted zetten en
        # expunge hoort hier niet, want dat zou onherstelbaar verwijderen zijn.
        if "MOVE" not in imapbron.capabilities(M):
            raise ValueError("Deze mailserver ondersteunt MOVE niet, dus naar "
                             "de prullenbak verplaatsen kan niet zonder "
                             "onherstelbaar te verwijderen. Overgeslagen.")
        imapbron._selecteer_schrijfbaar(M, bron_map)
        ok, gegevens = M.uid("MOVE", str(uid), f'"{prullenbak}"')
        if ok != "OK":
            raise ValueError("Naar de prullenbak verplaatsen mislukt: "
                             + imapbron._leesbaar(gegevens))

    print(f"[postbus] verwijderd (naar prullenbak) {mailbox['adres']} "
          f"{bron_map} uid {uid} -> {prullenbak}", flush=True)

    return {"mailbox": mailbox["adres"], "uid": uid, "van": bron_map,
            "prullenbak": prullenbak, "verwijderd": True,
            "let_op": "Het bericht staat nu in de prullenbak; het uid verandert "
                      "daarbij. De eigenaar kan het daar nog terugzetten tot de "
                      "provider de prullenbak opruimt."}

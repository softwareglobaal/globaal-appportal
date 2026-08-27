"""Controle op de grenzen van de Postbus: wie wat mag, en wat nooit kan.

De README stelde jarenlang dat een testset de leesgarantie bewaakte. Die
testset bestond niet. Nu doorsturen erbij komt, is dat niet langer houdbaar:
de grens tussen "leest mee" en "stuurt iets de organisatie uit" hoort
gecontroleerd te worden en niet alleen opgeschreven.

Draaien kan zonder pytest en zonder mailserver:

    python post/test_rechten.py

Er wordt niets verbonden en er gaat niets uit: alles hieronder werkt op de
ontleedfunctie en op de controles eromheen.
"""
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config          # noqa: E402
import verwijderen     # noqa: E402
import verzenden      # noqa: E402

BASIS = {
    "standaard": {"imap_host": "imap.one.com", "imap_poort": 993,
                  "smtp_host": "send.one.com", "smtp_poort": 465},
}


def ontleed(*mailboxen):
    ruw = dict(BASIS, mailboxen=list(mailboxen))
    return config._ontleed(ruw)


def rij(**extra):
    kaal = {"adres": "mch@h-architects.be", "wachtwoord": "geheim",
            "personen": ["mehdi"]}
    kaal.update(extra)
    return kaal


def gelijk(gekregen, verwacht, wat):
    if gekregen != verwacht:
        raise AssertionError(f"{wat}: verwacht {verwacht!r}, "
                             f"gekregen {gekregen!r}")
    print(f"  ok  {wat}")


def weigert(functie, stuk, wat):
    """De aanroep hoort te mislukken, met 'stuk' in de melding."""
    try:
        functie()
    except ValueError as e:
        if stuk.lower() not in str(e).lower():
            raise AssertionError(
                f"{wat}: geweigerd, maar de melding noemt '{stuk}' niet: {e}")
        print(f"  ok  {wat}")
        return
    raise AssertionError(f"{wat}: dit had geweigerd moeten worden")


def test_zonder_doorsturen_geen_recht():
    boxen, fouten = ontleed(rij())
    gelijk(boxen[0]["doorsturen"], [], "mailbox zonder regel stuurt niets door")
    gelijk(config.rechten(boxen[0]), ["lezen"], "rechten zijn alleen lezen")
    weigert(lambda: config.vereis_doorsturen(boxen[0], "ap@unabo.be"),
            "geen enkele bestemming", "doorsturen zonder lijst wordt geweigerd")


def test_alleen_wat_er_letterlijk_staat():
    boxen, _ = ontleed(rij(doorsturen=["ap@unabo.be"], schrijven="ja"))
    m = boxen[0]
    gelijk(config.rechten(m), ["lezen", "ordenen", "doorsturen"],
           "drie rechten staan er")
    gelijk(config.vereis_doorsturen(m, "AP@Unabo.BE"), "ap@unabo.be",
           "hoofdletters maken niet uit")
    weigert(lambda: config.vereis_doorsturen(m, "iemand@elders.be"),
            "staat niet open", "een ander adres wordt geweigerd")
    # Geen jokertekens: wie het hele domein wil, zet elk adres apart neer.
    weigert(lambda: config.vereis_doorsturen(m, "boekhouding@unabo.be"),
            "staat niet open", "zelfde domein is nog geen toestemming")
    weigert(lambda: config.vereis_doorsturen(m, ""),
            "staat niet open", "leeg adres wordt geweigerd")


def test_onbruikbare_bestemming_wordt_geweerd():
    for slecht in ["ap@unabo.be, stiekem@elders.be",
                   "ap@unabo.be\nBcc: stiekem@elders.be",
                   "geen-adres",
                   "<ap@unabo.be>"]:
        boxen, fouten = ontleed(rij(doorsturen=[slecht]))
        gelijk(boxen[0]["doorsturen"], [],
               f"geweerd bij het inlezen: {slecht!r}")
        if not any("doorstuuradres" in f for f in fouten):
            raise AssertionError(f"geen foutmelding voor {slecht!r}")


def test_doorsturen_vraagt_een_verzendserver():
    ruw = {"standaard": {"imap_host": "imap.one.com", "imap_poort": 993},
           "mailboxen": [rij(doorsturen=["ap@unabo.be"])]}
    boxen, fouten = config._ontleed(ruw)
    gelijk(boxen[0]["doorsturen"], [],
           "zonder smtp_host vervalt het doorsturen")
    gelijk(config.rechten(boxen[0]), ["lezen"],
           "en dan staat het recht er ook niet meer")
    if not any("smtp_host" in f for f in fouten):
        raise AssertionError("de beheerder wordt niet gewaarschuwd")
    print("  ok  de mailbox blijft wel gewoon leesbaar")


def test_mislukte_verzending_eet_het_plafond_niet():
    """Een mislukte poging (mailserver knijpt af) mag het dagplafond niet
    opsouperen; anders legt een tijdelijke storing de rest van de dag stil."""
    verzenden._teller.update(dag=None, aantal=0)
    for _ in range(5):
        verzenden._mag_nog()          # alleen kijken telt niet mee
    gelijk(verzenden._huidige_dag()["aantal"], 0,
           "kijken naar de ruimte verbruikt geen ruimte")
    verzenden._tel_succes()
    verzenden._tel_succes()
    gelijk(verzenden._huidige_dag()["aantal"], 2,
           "alleen geslaagde verzendingen tellen mee")


def test_verwijderen_en_verzenden_staan_standaard_uit():
    boxen, _ = ontleed(rij())
    m = boxen[0]
    gelijk(m["verwijderen"], False, "verwijderen is standaard uit")
    gelijk(m["verzenden"], False, "verzenden is standaard uit")
    gelijk(config.rechten(m), ["lezen"], "zonder vlaggen alleen lezen")
    weigert(lambda: config.vereis_verwijderen(m),
            "staat daar niet op", "verwijderen wordt geweigerd zonder vlag")
    weigert(lambda: config.vereis_verzenden(m),
            "staat daar niet op", "versturen wordt geweigerd zonder vlag")


def test_verwijderen_en_verzenden_als_ze_aanstaan():
    boxen, _ = ontleed(rij(schrijven="ja", verwijderen="ja", verzenden="ja"))
    m = boxen[0]
    gelijk(m["verwijderen"], True, "verwijderen: ja wordt gelezen")
    gelijk(m["verzenden"], True, "verzenden: ja wordt gelezen")
    gelijk(config.rechten(m),
           ["lezen", "ordenen", "verwijderen", "versturen"],
           "de rechten staan er allemaal")
    # De guards laten dit nu wel door (geen ValueError).
    config.vereis_verwijderen(m)
    config.vereis_verzenden(m)
    print("  ok  de guards laten een opengezette mailbox door")


def test_verzenden_vraagt_een_verzendserver():
    ruw = {"standaard": {"imap_host": "imap.one.com", "imap_poort": 993},
           "mailboxen": [rij(verzenden="ja")]}
    boxen, fouten = config._ontleed(ruw)
    gelijk(boxen[0]["verzenden"], False,
           "zonder smtp_host vervalt het verzenden")
    if not any("smtp_host" in f for f in fouten):
        raise AssertionError("de beheerder wordt niet gewaarschuwd")
    print("  ok  verzenden zonder smtp_host valt weg, mailbox blijft bruikbaar")


def test_noodrem_verzenden_gaat_voor_het_bestand():
    boxen, _ = ontleed(rij(verzenden="ja"))
    if verzenden.ACTIEF_VERZENDEN:
        print("  --  overgeslagen: POSTBUS_VERZENDEN staat aan in deze omgeving")
        return
    weigert(lambda: verzenden.verstuur(boxen[0], "iemand@elders.be", "hoi", "x"),
            "staat uit", "noodrem blokkeert versturen ook bij 'verzenden: ja'")


def test_noodrem_verwijderen_gaat_voor_het_bestand():
    boxen, _ = ontleed(rij(verwijderen="ja"))
    if verwijderen.ACTIEF:
        print("  --  overgeslagen: POSTBUS_VERWIJDEREN staat aan in deze omgeving")
        return
    weigert(lambda: verwijderen.verwijderen(boxen[0], "INBOX", 1),
            "staat uit", "noodrem blokkeert verwijderen ook bij 'verwijderen: ja'")


def test_verwijdermodule_verwijdert_niet_onherstelbaar():
    """De verwijdermodule mag naar de prullenbak verplaatsen (MOVE), maar zelf
    geen \\Deleted zetten of expunge doen: dat zou onherstelbaar zijn."""
    bron = (Path(__file__).resolve().parent / "verwijderen.py").read_text(
        encoding="utf-8")
    boom = ast.parse(bron)
    for knoop in ast.walk(boom):
        if isinstance(knoop, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef)):
            eerste = knoop.body[0] if knoop.body else None
            if (isinstance(eerste, ast.Expr)
                    and isinstance(eerste.value, ast.Constant)
                    and isinstance(eerste.value.value, str)):
                knoop.body.pop(0)
    code = ast.unparse(boom)
    for verboden in ("EXPUNGE", "\\Deleted"):
        if verboden in code:
            raise AssertionError(
                f"verwijderen.py bevat {verboden!r} in de uitvoerbare code")
    print("  ok  verwijderen.py zet geen \\Deleted en doet geen expunge")


def test_rechten_per_persoon():
    """Een rechtenveld als lijst geldt alleen voor wie erin staat."""
    boxen, _ = ontleed(rij(personen=["ultischa", "joan"],
                           schrijven=["ultischa"], verwijderen=["ultischa"]))
    m = boxen[0]
    ultischa = {"gebruiker": "ultischa", "groepen": []}
    joan = {"gebruiker": "joan", "groepen": []}
    gelijk(config.mag(m, "schrijven", ultischa), True,
           "ultischa mag schrijven")
    gelijk(config.mag(m, "verwijderen", ultischa), True,
           "ultischa mag verwijderen")
    gelijk(config.mag(m, "schrijven", joan), False, "joan mag niet schrijven")
    gelijk(config.mag(m, "verwijderen", joan), False,
           "joan mag niet verwijderen")
    gelijk(config.rechten(m, joan), ["lezen"], "joan ziet alleen lezen")
    gelijk(config.rechten(m, ultischa), ["lezen", "ordenen", "verwijderen"],
           "ultischa ziet haar rechten")
    gelijk(config.rechten(m), ["lezen", "ordenen (ultischa)",
                               "verwijderen (ultischa)"],
           "de beheerkolom toont de namen erbij")
    config.vereis_schrijven(m, "Markeren", ultischa)
    weigert(lambda: config.vereis_schrijven(m, "Markeren", joan),
            "alleen voor", "de guard weigert joan met de namenlijst erbij")
    print("  ok  de guards volgen de lijst")


def test_recht_via_groep():
    boxen, _ = ontleed(rij(groepen=["boekhouding"], personen=[],
                           verwijderen=["finance"]))
    m = boxen[0]
    lid = {"gebruiker": "piet", "groepen": ["boekhouding", "finance"]}
    geen_lid = {"gebruiker": "joan", "groepen": ["boekhouding"]}
    gelijk(config.mag(m, "verwijderen", lid), True,
           "een groep in de lijst geeft het recht")
    gelijk(config.mag(m, "verwijderen", geen_lid), False,
           "zonder die groep niet")


def test_ja_blijft_voor_iedereen():
    boxen, _ = ontleed(rij(personen=["ultischa", "joan"], schrijven="ja"))
    m = boxen[0]
    gelijk(config.mag(m, "schrijven", {"gebruiker": "joan", "groepen": []}),
           True, "ja betekent iedereen met toegang, zoals altijd")


def test_lege_rechtenlijst_valt_op():
    boxen, fouten = ontleed(rij(verwijderen=[]))
    gelijk(boxen[0]["verwijderen"], False, "een lege lijst wordt nee")
    if not any("lege" in f for f in fouten):
        raise AssertionError("de beheerder wordt niet gewaarschuwd")
    print("  ok  een lege lijst geeft een melding")


def test_onbekende_sleutel_valt_op():
    _, fouten = ontleed(rij(doorstuur=["ap@unabo.be"]))
    if not any("onbekende sleutels" in f for f in fouten):
        raise AssertionError("een typefout in de sleutel glipt erdoor")
    print("  ok  een typefout als 'doorstuur' wordt gemeld")


def test_noodrem_gaat_voor_het_bestand():
    """Staat de server-schakelaar uit, dan gaat er niets uit. Ook niet als de
    mailbox het toestaat: dat is het hele punt van een noodrem."""
    boxen, _ = ontleed(rij(doorsturen=["ap@unabo.be"]))
    if verzenden.ACTIEF:
        print("  --  overgeslagen: POSTBUS_DOORSTUREN staat aan in deze omgeving")
        return
    weigert(lambda: verzenden.doorsturen(boxen[0], "INBOX", 1, "ap@unabo.be"),
            "staat uit", "noodrem blokkeert ook een toegestane bestemming")


def test_leesmodule_blijft_zonder_smtp():
    """imapbron is de leesmodule en hoort dat te blijven. Uitgaande post staat
    in verzenden.py, zodat je aan een bestand genoeg hebt om te zien wat er
    naar buiten kan."""
    bron = (Path(__file__).resolve().parent / "imapbron.py").read_text(
        encoding="utf-8")
    # Alleen de uitvoerbare code toetsen. Commentaar en docstrings noemen deze
    # woorden juist om uit te leggen dat ze er niet zijn; die meerekenen zou
    # de documentatie afrekenen in plaats van de code.
    boom = ast.parse(bron)
    for knoop in ast.walk(boom):
        if isinstance(knoop, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef)):
            eerste = knoop.body[0] if knoop.body else None
            if (isinstance(eerste, ast.Expr)
                    and isinstance(eerste.value, ast.Constant)
                    and isinstance(eerste.value.value, str)):
                knoop.body.pop(0)
    code = ast.unparse(boom)
    for verboden in ("smtplib", "EXPUNGE", "\\Deleted"):
        if verboden in code:
            raise AssertionError(
                f"imapbron.py bevat {verboden!r} in de uitvoerbare code")
    print("  ok  imapbron.py heeft geen SMTP en verwijdert niets")


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        print(f"\n{test.__name__}")
        test()
    print(f"\n{len(tests)} onderdelen doorlopen, alles in orde.")


if __name__ == "__main__":
    main()

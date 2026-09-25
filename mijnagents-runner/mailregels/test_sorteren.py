#!/usr/bin/env python3
"""Grendel op sorteren.py (bron: repo globaal-appportal, mijnagents-runner/mailregels/): de regels van het regelbestand en de vier harde regels van de code.
Draait zonder mailserver:  python3 test_sorteren.py
De launchd-taak roept dit eerst aan; faalt het, dan wordt er niets verplaatst."""
import ast
import datetime as dt
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.argv = ["sorteren", "info", "x"]
import sorteren  # noqa: E402

REGELS = os.path.join(HIER, "regels_hinvest.txt")
NU = dt.datetime.now(dt.timezone.utc)


def rij(addr, name="", subject="", dagen=0, unsub=False):
    return dict(addr=addr, name=name, subject=subject, datum=NU - dt.timedelta(days=dagen), unsub=unsub)


def test_regels_laden():
    r = sorteren.laad_regels(REGELS)
    assert r["archief"]["dagen"] == 365 and "{jaar}" in r["archief"]["map"]
    assert "h-invest.be" in r["eigen"]
    assert any(m == "kbo" for m, _ in r["oplichting"])
    print("  ok  regelbestand laadt: archief, eigen domeinen, merken")


def test_echte_afzenders_zijn_geen_oplichting():
    """26-9-2026: in info@h-architects vielen Telenet, FOD Financien, NAV en de one.com-registrar als oplichting."""
    r = sorteren.laad_regels(REGELS)
    assert not sorteren.is_oplichting("Telenet Business", "b2b@telenetgroup.be", r)
    assert not sorteren.is_oplichting(" FOD Financi\u00ebn ", "info@news.minfin.fed.be", r)
    assert not sorteren.is_oplichting("NAV vzw, Netwerk Architecten Vlaanderen", "danny@nav.be", r)
    assert not sorteren.is_oplichting("one.com", "reminder@ascio.com", r)
    assert not sorteren.is_oplichting("Asbestattesten Vlaanderen BV", "c3e7@fw.eenvoudigfactureren.be", r)
    assert sorteren.is_oplichting("Vlaamse overheid", "info@vlaanderen-premie.com", r)
    assert sorteren.is_oplichting("My MINFIN", "anonymusss279@gmail.com", r)
    assert sorteren.is_oplichting("Proximus", "contact@mailers.com", r)
    assert sorteren.is_oplichting("VLAIO Vlaanderen", "atamboura@inter-mining.com", r)
    print("  ok  echte afzenders (Telenet, FOD, NAV, one.com-registrar) zijn geen oplichting; nep blijft nep")


def test_mapnamen_met_spatie_tussen_aanhalingstekens():
    """26-9-2026: MOVE naar 'INBOX.Bank en verzekering' zonder aanhalingstekens maakte de map INBOX.Bank."""
    assert sorteren.imapnaam("INBOX.Bank en verzekering") == '"INBOX.Bank en verzekering"'
    bron = open(os.path.join(HIER, "sorteren.py"), encoding="utf-8").read()
    assert 'm.uid("MOVE", ",".join(uids[i:i + 100]), imapnaam(doel))' in bron
    assert "m.create(imapnaam(naam))" in bron and "m.subscribe(imapnaam(naam))" in bron
    print("  ok  mapnamen met een spatie gaan tussen aanhalingstekens naar de server")


def test_afgeleide_regels_zijn_bij():
    """regels_info.txt en regels_mch.txt worden gemaakt uit regels_hinvest.txt plus toevoegingen_<alias>.txt (maak_regels.py).
    Wie de basis aanpast zonder opnieuw te maken, laat een postvak met oude regels werken: dan faalt dit."""
    import subprocess
    import tempfile
    for alias in ("info", "mch", "melo"):
        uit = os.path.join(tempfile.mkdtemp(), f"regels_{alias}.txt")
        subprocess.run([sys.executable, os.path.join(HIER, "maak_regels.py"), REGELS,
                        os.path.join(HIER, f"toevoegingen_{alias}.txt"), uit], check=True, capture_output=True)
        assert open(uit, encoding="utf-8").read() == open(os.path.join(HIER, f"regels_{alias}.txt"), encoding="utf-8").read(), \
            f"regels_{alias}.txt is niet bij: python3 maak_regels.py regels_hinvest.txt toevoegingen_{alias}.txt regels_{alias}.txt"
    ri = sorteren.laad_regels(os.path.join(HIER, "regels_info.txt"))
    rm = sorteren.laad_regels(os.path.join(HIER, "regels_mch.txt"))
    assert sorteren.bestemming(rij("e-box.noreply@socialsecurity.be"), ri, False, None)[0] == "INBOX.BOEKHOUDING.E-Box"
    assert sorteren.bestemming(rij("raad.brabant@ordevanarchitecten.be"), ri, False, None)[0] == "INBOX.ORDE"
    assert sorteren.bestemming(rij("scannerbizhubc250i@gmail.com"), rm, False, None)[0] == "INBOX.Scans"
    assert sorteren.bestemming(rij("info@nav.be"), rm, False, None)[0] == "INBOX.Nieuwsbrieven"
    assert sorteren.bestemming(rij("peter.coeckelberghs@kbc.be"), rm, False, None)[0] is None, "de KBC-adviseur blijft in INBOX"
    assert sorteren.bestemming(rij("flyingbluecrm@service-flyingblue.com"), rm, False, None)[0] is None, "beveiliging blijft zichtbaar"
    print("  ok  afgeleide regels zijn bij; info@ en mch@ sturen de vaste afzenders naar de juiste map")


def test_voorrang():
    r = sorteren.laad_regels(REGELS)
    grens = NU - dt.timedelta(days=365)
    assert sorteren.bestemming(rij("jouwmening@feedback.bol.com"), r, False, grens)[0] == "INBOX.Opgeruimd"
    assert sorteren.bestemming(rij("automail@bol.com"), r, False, grens)[0] == "INBOX.Bestellingen"
    assert sorteren.bestemming(rij("hi@eccellente.nl"), r, False, grens)[0] == "INBOX.Opgeruimd"
    assert sorteren.bestemming(rij("hallo@eccellente.nl"), r, False, grens)[0] == "INBOX.Bestellingen"
    assert sorteren.bestemming(rij("x@mail.troostwijkauctions.com"), r, False, grens)[0] == "INBOX.Veilingen"
    print("  ok  voorrang: exact adres > @domein > .domein")


def test_mensen_blijven():
    r = sorteren.laad_regels(REGELS)
    grens = NU - dt.timedelta(days=365)
    for a, n in (("vincent.vleugels2@verz.kbc.be", "Vincent Vleugels"), ("info@carrect.be", "Info Carrect"),
                 ("joan@globaal.be", "Joan"), ("hanna.rottiers@assaabloy.com", "Rottiers, Hanna")):
        doel, reden = sorteren.bestemming(rij(a, n, "Re: dossier", dagen=10), r, True, grens)
        assert doel is None, (a, doel)
    print("  ok  adviseurs, leveranciers en collega's blijven in INBOX")


def test_oplichting():
    r = sorteren.laad_regels(REGELS)
    assert sorteren.is_oplichting("KBO (Kruispuntbank)", "admin@geoset.kz", r)
    assert sorteren.is_oplichting("Аrɡеntа", "digipas@update-pro.be", r)
    assert sorteren.is_oplichting("ｏｎｅ.ｃｏｍ", "info@asl-one.com", r)
    assert sorteren.is_oplichting("CM Gezondheidsfonds", "110599@stud.uz.zgora.pl", r)
    assert not sorteren.is_oplichting("KBC Bank & Verzekering", "info-kbc@mail-kbc.be", r)
    assert not sorteren.is_oplichting("Kingsberry", "ellen@kingsberry.be", r), "ING mag Kingsberry niet raken"
    assert not sorteren.is_oplichting("Microsoft Outlook", "info@h-invest.be", r), "eigen domein is nooit oplichting"
    assert not sorteren.is_oplichting("Shaniel (via Google Drive)", "x@gmail.com", r)
    print("  ok  oplichting: merknaam op vreemd domein, homoglyfen, geen valse treffers")


def test_archief_en_nieuwe_reclame():
    r = sorteren.laad_regels(REGELS)
    grens = NU - dt.timedelta(days=365)
    doel, reden = sorteren.bestemming(rij("iemand@voorbeeld.be", "Iemand", "Vraag", dagen=400), r, False, grens)
    assert doel == "INBOX.Archief." + str((NU - dt.timedelta(days=400)).year) and reden == "archief"
    doel, reden = sorteren.bestemming(rij("news@nieuw.be", "Nieuw", "Onze zomeractie", dagen=1, unsub=True), r, True, grens)
    assert doel == "INBOX.Opgeruimd" and reden == "nieuwe reclame"
    doel, reden = sorteren.bestemming(rij("shop@nieuw.be", "Nieuw", "Order 123 confirmed", dagen=1, unsub=True), r, True, grens)
    assert doel is None, "een bestelling met List-Unsubscribe blijft staan"
    doel, reden = sorteren.bestemming(rij("news@nieuw.be", "Nieuw", "Onze zomeractie", dagen=1, unsub=True), r, False, grens)
    assert doel is None, "zonder --nieuwe-reclame blijft een onbekende afzender staan"
    print("  ok  jaararchief en nieuwe reclame")


def test_code_verwijdert_niets():
    bron = open(os.path.join(HIER, "sorteren.py"), encoding="utf-8").read()
    boom = ast.parse(bron)
    docs = {ast.get_docstring(n, clean=False) for n in ast.walk(boom) if isinstance(n, (ast.Module, ast.FunctionDef))}
    for n in ast.walk(boom):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value not in docs:
            v = n.value.upper()
            assert "EXPUNGE" not in v and "\\DELETED" not in v and "STORE" not in v.split(), n.value
    assert "smtplib" not in bron
    for n in ast.walk(boom):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "uid":
            cmd = n.args[0]
            assert isinstance(cmd, ast.Constant) and cmd.value.upper() in ("SEARCH", "FETCH", "MOVE"), ast.dump(cmd)
    print("  ok  code kent alleen SEARCH, FETCH en MOVE; geen EXPUNGE, geen \\Deleted, geen SMTP")


if __name__ == "__main__":
    print("Mailwacht, sorteren.py:")
    for naam, f in list(globals().items()):
        if naam.startswith("test_") and callable(f):
            f()
    print("alles in orde")

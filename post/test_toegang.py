"""Controle op /toegang: een mailbox-beheerder wijzigt wie erbij mag, en niets meer.

Draaien kan zonder pytest en zonder mailserver:

    python post/test_toegang.py

Alles werkt op tijdelijke bestanden; mailboxen.yaml en de laag op de VM worden
niet aangeraakt.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml            # noqa: E402

import config          # noqa: E402

MAP = tempfile.mkdtemp(prefix="postbus-toegang-")
config.PAD = os.path.join(MAP, "mailboxen.yaml")
config.TOEGANG_PAD = os.path.join(MAP, "toegang", "toegang.yaml")
config.LOG_PAD = os.path.join(MAP, "toegang", "wijzigingen.jsonl")

MUKESH = {"gebruiker": "mukesh", "groepen": ["postbus", "energie"]}
JOAN = {"gebruiker": "joan", "groepen": ["postbus"]}

BASIS = {
    "standaard": {"imap_host": "imap.one.com", "smtp_host": "send.one.com"},
    "mailboxen": [
        {"adres": "info@energie-efficient.be", "wachtwoord": "geheim",
         "personen": ["joan", "mukesh", "mehdi"], "schrijven": ["mehdi"],
         "verwijderen": ["mehdi"], "verzenden": ["mehdi"],
         "beheer": ["mukesh"]},
        {"adres": "ap@energie-efficient.be", "wachtwoord": "geheim",
         "personen": ["joan", "amy"]},
        {"adres": "office@energie-efficient.be", "wachtwoord": "geheim",
         "personen": ["joan"], "beheer": "ja"},
    ],
}


def schrijf_basis(ruw=BASIS):
    os.makedirs(MAP, exist_ok=True)
    with open(config.PAD, "w", encoding="utf-8") as f:
        yaml.safe_dump(ruw, f)
    config._vergeet()


def box(adres):
    alle, _ = config.alles()
    return next(m for m in alle if m["adres"] == adres)


def gelijk(gekregen, verwacht, wat):
    if gekregen != verwacht:
        raise AssertionError(f"{wat}: verwacht {verwacht!r}, "
                             f"gekregen {gekregen!r}")
    print(f"  ok  {wat}")


def weigert(functie, stuk, wat):
    try:
        functie()
    except ValueError as e:
        if stuk.lower() not in str(e).lower():
            raise AssertionError(
                f"{wat}: geweigerd, maar de melding noemt '{stuk}' niet: {e}")
        print(f"  ok  {wat}")
        return
    raise AssertionError(f"{wat}: dit had geweigerd moeten worden")


def opnieuw():
    schrijf_basis()
    for pad in (config.TOEGANG_PAD, config.LOG_PAD):
        if os.path.exists(pad):
            os.remove(pad)
    config._vergeet()


GOED = {"personen": "joan, mukesh, mehdi, ashvand", "groepen": "",
        "schrijven": ["mehdi", "joan"], "verwijderen": ["mehdi"]}


def test_alleen_eigen_mailboxen():
    opnieuw()
    gelijk([m["adres"] for m in config.beheerbaar(MUKESH)],
           ["info@energie-efficient.be"], "mukesh beheert alleen info@")
    gelijk(config.beheerbaar(JOAN), [], "joan beheert niets")
    weigert(lambda: config.zet_toegang("ap@energie-efficient.be", GOED, MUKESH),
            "beheert de toegang", "andere mailbox wordt geweigerd")
    weigert(lambda: config.zet_toegang("info@energie-efficient.be", GOED, JOAN),
            "beheert de toegang", "niet-beheerder wordt geweigerd")


def test_beheer_ja_telt_niet():
    opnieuw()
    gelijk(box("office@energie-efficient.be")["beheer"], [],
           "beheer: ja geeft niemand beheer")
    alle, fouten = config.alles()
    gelijk(any("beheer moet een lijst" in f for f in fouten), True,
           "beheer: ja staat bij de aandachtspunten")


def test_wijziging_geldt_en_wordt_gelogd():
    opnieuw()
    oud, nieuw = config.zet_toegang("info@energie-efficient.be", GOED, MUKESH)
    m = box("info@energie-efficient.be")
    gelijk(m["personen"], ["joan", "mukesh", "mehdi", "ashvand"],
           "ashvand staat erbij")
    gelijk(m["schrijven"], ["mehdi", "joan"], "ordenen voor mehdi en joan")
    gelijk(m["verzenden"], ["mehdi"], "verzenden onveranderd")
    gelijk(m["wachtwoord"], "geheim", "wachtwoord onveranderd")
    gelijk(m["aangepast"]["door"], "mukesh", "wie het deed staat erbij")
    regels = Path(config.LOG_PAD).read_text(encoding="utf-8").splitlines()
    gelijk(len(regels), 1, "een regel in het logboek")
    w = json.loads(regels[0])
    gelijk((w["door"], w["oud"]["personen"], w["nieuw"]["schrijven"]),
           ("mukesh", ["joan", "mukesh", "mehdi"], ["mehdi", "joan"]),
           "logboek heeft oud en nieuw")
    gelijk("geheim" in Path(config.TOEGANG_PAD).read_text(encoding="utf-8"),
           False, "geen wachtwoord in de laag")
    config.zet_toegang("info@energie-efficient.be", GOED, MUKESH)
    gelijk(len(Path(config.LOG_PAD).read_text(encoding="utf-8").splitlines()),
           1, "zelfde invoer nog eens logt niets")


def test_uitgaande_post_blijft_dicht():
    opnieuw()
    for veld in ("verzenden", "doorsturen", "beheer", "wachtwoord", "mappen"):
        weigert(lambda: config.zet_toegang(
            "info@energie-efficient.be", dict(GOED, **{veld: ["mukesh"]}),
            MUKESH), "niet wijzigen", f"{veld} kan niet via /toegang")
    # Ook een met de hand bijgewerkte laag kan verzenden niet openzetten.
    os.makedirs(os.path.dirname(config.TOEGANG_PAD), exist_ok=True)
    with open(config.TOEGANG_PAD, "w", encoding="utf-8") as f:
        yaml.safe_dump({"mailboxen": {"info@energie-efficient.be": {
            "door": "x", "op": "x", "waarden": {
                "personen": ["mukesh"], "verzenden": ["mukesh"],
                "doorsturen": ["iemand@elders.be"]}}}}, f)
    config._vergeet()
    m = box("info@energie-efficient.be")
    gelijk((m["verzenden"], m["doorsturen"], m["personen"]),
           (["mehdi"], [], ["mukesh"]),
           "laag negeert verzenden en doorsturen")


def test_ongeldige_invoer():
    opnieuw()
    weigert(lambda: config.zet_toegang(
        "info@energie-efficient.be", dict(GOED, personen="", groepen=""),
        MUKESH), "minstens een", "niemand overlaten wordt geweigerd")
    weigert(lambda: config.zet_toegang(
        "info@energie-efficient.be", dict(GOED, personen="joan, <script>"),
        MUKESH), "geen geldige", "rare naam wordt geweigerd")
    gelijk(config.normaliseer(dict(GOED, verwijderen=""))["verwijderen"],
           "nee", "lege namenlijst wordt nee")


def test_beheer_intrekken():
    opnieuw()
    config.zet_toegang("info@energie-efficient.be", GOED, MUKESH)
    ruw = json.loads(json.dumps(BASIS))
    del ruw["mailboxen"][0]["beheer"]
    schrijf_basis(ruw)
    m = box("info@energie-efficient.be")
    gelijk(m["personen"], ["joan", "mukesh", "mehdi"],
           "zonder beheer: geldt mailboxen.yaml weer")
    gelijk(config.beheerbaar(MUKESH), [], "mukesh beheert dan niets meer")


def test_kapotte_laag():
    opnieuw()
    os.makedirs(os.path.dirname(config.TOEGANG_PAD), exist_ok=True)
    with open(config.TOEGANG_PAD, "w", encoding="utf-8") as f:
        f.write("mailboxen: [onaf\n")
    config._vergeet()
    m = box("info@energie-efficient.be")
    gelijk(m["personen"], ["joan", "mukesh", "mehdi"],
           "kapotte laag: mailboxen.yaml geldt")
    weigert(lambda: config.zet_toegang("info@energie-efficient.be", GOED,
                                       MUKESH),
            "onleesbaar", "kapotte laag wordt niet overschreven")


def test_formulier():
    opnieuw()
    import app as webapp
    c = webapp.app.test_client()
    kop = {"X-Authentik-Username": "mukesh",
           "X-Authentik-Groups": "postbus|energie"}
    gelijk(c.get("/toegang", headers={"X-Authentik-Username": "joan",
                                      "X-Authentik-Groups": "postbus"}
                 ).status_code, 403, "joan krijgt 403 op /toegang")
    r = c.get("/toegang", headers=kop)
    gelijk((r.status_code, b"info@energie-efficient.be" in r.data,
            b"ap@energie-efficient.be" in r.data),
           (200, True, False), "mukesh ziet alleen info@")
    vorm = {"adres": "info@energie-efficient.be", "personen": "joan, mukesh",
            "groepen": "energie", "schrijven": "namen",
            "schrijven_namen": "joan", "verwijderen": "nee"}
    gelijk(c.post("/toegang", data=vorm, headers=kop).status_code, 403,
           "zonder Origin geweigerd")
    gelijk(c.post("/toegang", data=vorm, headers=dict(
        kop, Origin="https://kwaad.example")).status_code, 403,
        "andere Origin geweigerd")
    r = c.post("/toegang", data=vorm, headers=dict(
        kop, Origin="http://localhost"))
    gelijk(r.status_code, 303, "eigen Origin opgeslagen")
    m = box("info@energie-efficient.be")
    gelijk((m["groepen"], m["schrijven"], m["verwijderen"]),
           (["energie"], ["joan"], False), "formulier komt goed door")


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        print(f"\n{test.__name__}")
        test()
    print(f"\n{len(tests)} onderdelen doorlopen, alles in orde.")


if __name__ == "__main__":
    main()

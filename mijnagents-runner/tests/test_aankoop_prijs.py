"""Grendels van De Prijsonderzoeker: wat nooit in een prijsverslag mag, en hoe het totaal en de rangorde ontstaan.

Alleen verzonnen aanbiedingen en voorbeeld.com-links; geen echte bestellingen of personen.

Draaien: python3 mijnagents-runner/tests/test_aankoop_prijs.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aankoop import aanbod as A  # noqa: E402
from aankoop import koersen as K  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  goed  {naam}")
    else:
        fout += 1
        print(f"  FOUT  {naam} {extra}")


VANDAAG = date(2026, 10, 30)
KOERSEN = {"USD": 1.10, "GBP": 0.85, "SRD": 40.0}


def aanbod(**over):
    basis = {"titel": "Vloerwasser X1", "url": "https://winkel.voorbeeld.com/x1", "winkel": "Winkel", "land": "BE",
             "soort": "nieuw", "prijs": 500, "munt": "EUR", "verzending": 0, "gezien_op": "2026-10-30",
             "beschikbaar": True}
    basis.update(over)
    return basis


print("Wat nooit in het verslag mag")
check("een aanbod zonder link", "geen werkende link" in A.keur(aanbod(url=""), VANDAAG))
check("een link zonder http", "geen werkende link" in A.keur(aanbod(url="winkel.voorbeeld.com/x1"), VANDAAG))
check("een aanbod zonder prijs", "geen prijs" in A.keur(aanbod(prijs=None), VANDAAG))
check("een prijs van nul", "geen prijs" in A.keur(aanbod(prijs=0), VANDAAG))
check("zonder datum gezien", "geen datum gezien" in A.keur(aanbod(gezien_op=None), VANDAAG))
check("een prijs van vorige week is te oud", "prijs te oud" in A.keur(aanbod(gezien_op="2026-10-20"), VANDAAG))
check("een datum in de toekomst", "datum gezien ligt in de toekomst" in A.keur(aanbod(gezien_op="2026-11-02"), VANDAAG))
check("uitverkocht", "niet meer beschikbaar" in A.keur(aanbod(beschikbaar=False), VANDAAG))
check("een onbekende soort", "soort onbekend" in A.keur(aanbod(soort="koopje"), VANDAAG))
check("een volledig aanbod mag", A.keur(aanbod(), VANDAAG) == [])

print("Bedragen en omrekening")
check("Belgische schrijfwijze", A._getal("1.299,00") == 1299.0)
check("Engelse schrijfwijze", A._getal("1,299.00") == 1299.0)
check("decimale komma", A._getal("49,95") == 49.95)
check("een boolean is geen bedrag", A._getal(True) is None)
check("dollar naar euro met de ECB-koers", round(A.in_euro(110, "USD", KOERSEN), 2) == 100.0)
check("zonder koers geen bedrag", A.in_euro(100, "CNY", KOERSEN) is None)

print("Totaalprijs")
check("binnen de EU: prijs plus verzending", A.totaal(aanbod(prijs=500, verzending=25), KOERSEN) == (525.0, []))
check("zonder verzending is het totaal onvolledig", A.totaal(aanbod(verzending=None), KOERSEN) == (None, ["verzending"]))
v = A.totaal(aanbod(soort="veiling", prijs=1000, verzending=50, veilingkosten=0), KOERSEN)
check("een veilingprijs zonder opgeld is geen totaalprijs", v == (None, ["opgeld"]), str(v))
v = A.totaal(aanbod(soort="veiling", prijs=1000, verzending=50, opgeld_pct=18), KOERSEN)
check("onbekende vaste veilingkosten tellen niet als nul (overleg K3)", v == (None, ["veilingkosten"]), str(v))
v = A.totaal(aanbod(soort="veiling", prijs=1000, verzending=50, opgeld_pct=18, veilingkosten=0), KOERSEN)
check("veilingkosten 0 als de voorwaarden er geen noemen", v == (1230.0, []), str(v))
v = A.totaal(aanbod(soort="veiling", prijs=1000, verzending=50, opgeld_pct=18, veilingkosten=10), KOERSEN)
check("veiling met opgeld en kosten", v == (1240.0, []), str(v))
v = A.totaal(aanbod(land="US", munt="USD", prijs=550, verzending=55), KOERSEN)
check("buiten de EU zonder invoer is onvolledig", v == (None, ["invoer"]), str(v))
v = A.totaal(aanbod(land="US", munt="USD", prijs=550, verzending=55, invoer=132), KOERSEN)
check("buiten de EU met invoer, in euro", v == (670.0, []), str(v))
check("zonder land geldt het als buiten de EU", A.totaal(aanbod(land=""), KOERSEN) == (None, ["land"]))

print("Compatibiliteit (Suriname: 127/220 V, 60 Hz)")
eisen = ["spanning 220 V 60 Hz", "stekker type A/B"]
eu_model = aanbod(compatibiliteit={"spanning 220 V 60 Hz": "nee", "stekker type A/B": "nee"})
us_model = aanbod(url="https://winkel.voorbeeld.com/x1-us", compatibiliteit={"spanning 220 V 60 Hz": "ja", "stekker type A/B": "ja"})
half = aanbod(url="https://winkel.voorbeeld.com/x1-half", compatibiliteit={"spanning 220 V 60 Hz": "ja"})
check("een eis die nee is maakt het niet compatibel", A.compatibel(eu_model, eisen) == "nee")
check("alle eisen ja", A.compatibel(us_model, eisen) == "ja")
check("een eis zonder oordeel is onbekend", A.compatibel(half, eisen) == "onbekend")
check("zonder eisen altijd compatibel", A.compatibel(aanbod(), []) == "ja")

print("Rangorde en beste aanbod")
r = A.verwerk([
    aanbod(prijs=300, compatibiliteit={e: "nee" for e in eisen}),                                   # goedkoopst maar past niet
    aanbod(url="https://b.voorbeeld.com/1", prijs=450, compatibiliteit={e: "ja" for e in eisen}),
    aanbod(url="https://c.voorbeeld.com/1", prijs=400, verzending=None, compatibiliteit={e: "ja" for e in eisen}),
    aanbod(url="https://d.voorbeeld.com/1", prijs=420, compatibiliteit={eisen[0]: "ja"}),
    aanbod(url="", prijs=100),                                                                        # zonder link
    aanbod(url="https://b.voorbeeld.com/1/", prijs=450, compatibiliteit={e: "ja" for e in eisen}),  # dubbel
], VANDAAG, KOERSEN, eisen)
check("het goedkoopste maar niet compatibele aanbod staat apart", len(r["niet_compatibel"]) == 1
      and r["niet_compatibel"][0]["prijs"] == 300)
check("het beste is compatibel en volledig", r["beste"] is not None and r["beste"]["url"] == "https://b.voorbeeld.com/1")
check("onvolledig totaal komt achteraan", r["goed"][-1]["url"] == "https://c.voorbeeld.com/1")
check("een reserve naast het beste, ook compatibel en volledig", r["reserve"] is None)
check("een compatibel aanbod gaat voor een onbekend", [g["url"] for g in r["goed"][:2]]
      == ["https://b.voorbeeld.com/1", "https://d.voorbeeld.com/1"], str([g["url"] for g in r["goed"]]))
check("zonder link afgewezen, met reden", any("geen werkende link" in a["redenen"] for a in r["afgewezen"]))
check("dezelfde link twee keer telt een keer", any(a["redenen"] == ["dubbel"] for a in r["afgewezen"]))
r = A.verwerk([aanbod(soort="veiling", prijs=100)], VANDAAG, KOERSEN)
check("een veiling zonder opgeld wordt nooit het beste aanbod", r["beste"] is None and len(r["goed"]) == 1)

print("Koersen van de ECB")
XML = """<gesmes:Envelope><Cube><Cube time='2026-10-30'>
<Cube currency='USD' rate='1.0812'/><Cube currency='GBP' rate='0.8461'/></Cube></Cube></gesmes:Envelope>"""
datum, k = K.lees(XML)
check("datum en koersen gelezen", datum == "2026-10-30" and k == {"USD": 1.0812, "GBP": 0.8461}, str(k))
check("onleesbaar geeft niets", K.lees("geen xml") == (None, {}))

print("Alleen gelezen pagina's (onderzoek)")
from aankoop import onderzoek as O  # noqa: E402
from aankoop import verslag as V  # noqa: E402

check("www, http en fragment tellen niet", O.schoon_url("http://WWW.Winkel.voorbeeld.com/x1/#foto")
      == "https://winkel.voorbeeld.com/x1")
check("de query telt wel (product-id)", O.schoon_url("https://w.voorbeeld.com/p?id=1") != O.schoon_url("https://w.voorbeeld.com/p?id=2"))
BLOKKEN = [
    {"type": "server_tool_use", "name": "web_search", "input": {"query": "vloerwasser x1"}},
    {"type": "web_search_tool_result", "content": [{"type": "web_search_result", "url": "https://zoek.voorbeeld.com/a"}]},
    {"type": "server_tool_use", "name": "web_fetch", "input": {"url": "https://winkel.voorbeeld.com/x1"}},
    {"type": "web_fetch_tool_result", "content": {"type": "web_fetch_result", "url": "https://winkel.voorbeeld.com/x1"}},
    {"type": "web_fetch_tool_result", "content": {"type": "web_fetch_tool_error", "error_code": "url_not_accessible"}},
]
BLOKKEN[3]["content"]["content"] = {"type": "document", "source": {"type": "text", "media_type": "text/plain",
                                                                       "data": "X1 499 euro ![X1](https://cdn.voorbeeld.com/x1.jpg)"}}
gelezen = O.gelezen_paginas(BLOKKEN)
check("alleen een geslaagde web_fetch telt als gelezen", set(gelezen) == {"https://winkel.voorbeeld.com/x1"}, str(gelezen))
check("met de tekst van de pagina", "499 euro" in gelezen["https://winkel.voorbeeld.com/x1"])
goed, _ = O.alleen_gelezen([aanbod(foto="https://cdn.voorbeeld.com/x1.jpg")], gelezen)
check("een foto die op de gelezen pagina staat, blijft", goed[0]["foto"] == "https://cdn.voorbeeld.com/x1.jpg")
goed, _ = O.alleen_gelezen([aanbod(foto="https://cdn.voorbeeld.com/verzonnen.jpg")], gelezen)
check("een foto die niet op de pagina staat, wordt nooit getoond (overleg X5)", goed[0]["foto"] is None)
goed, weg = O.alleen_gelezen([aanbod(), aanbod(url="https://zoek.voorbeeld.com/a"), aanbod(url="https://verzonnen.voorbeeld.com/z")], gelezen)
check("een link uit een zoekresultaat alleen gaat er niet in", len(goed) == 1 and len(weg) == 2
      and all(w["redenen"] == ["pagina niet gelezen in deze ronde"] for w in weg))
check("JSON uit een ```json-blok", O.json_uit('Uitleg\n```json\n{"eisen": []}\n```') == {"eisen": []})
check("het laatste blok telt", O.json_uit('```json\n{"a": 1}\n```\n```json\n{"a": 2}\n```') == {"a": 2})
check("geen JSON geeft None", O.json_uit("ik vond niets") is None)


class NepAntwoord:
    def __init__(self, inhoud, stop):
        self.content, self.stop_reason = inhoud, stop
        self.usage = {"input_tokens": 1000, "output_tokens": 200}


class NepClient:
    """Bootst de Messages-API na: eerst een gepauzeerde beurt met een gelezen pagina, dan het antwoord."""
    def __init__(self, antwoorden):
        self.antwoorden, self.vragen = list(antwoorden), []
        self.messages = self

    def create(self, **kw):
        self.vragen.append(kw)
        return self.antwoorden.pop(0)


JSON = ('```json\n{"vraag_kort": "vloerwasser X1 voor Suriname", "eisen": ["spanning 220 V 60 Hz"], '
        '"aanbiedingen": [{"titel": "X1", "url": "https://winkel.voorbeeld.com/x1", "winkel": "W", "land": "BE", '
        '"soort": "nieuw", "prijs": 499, "munt": "EUR", "verzending": 0, "beschikbaar": true, '
        '"compatibiliteit": {"spanning 220 V 60 Hz": "ja"}}, {"titel": "X1 verzonnen", '
        '"url": "https://verzonnen.voorbeeld.com/z", "soort": "nieuw", "prijs": 10, "munt": "EUR", "land": "BE", '
        '"verzending": 0}], "advies": "Neem X1.", "volgende_stap": "Bestel zelf bij W."}\n```')
nep = NepClient([NepAntwoord(BLOKKEN[:4], "pause_turn"), NepAntwoord([{"type": "text", "text": JSON}], "end_turn")])
uit = O.onderzoek("Vloerwasser X1 voor Suriname", "werkwijze", "collega's", "", "2026-10-30", client=nep)
check("na pause_turn gaat de beurt verder", len(nep.vragen) == 2 and nep.vragen[1]["messages"][-1]["role"] == "assistant")
check("webzoeken en webpagina's lezen staan aan, met een plafond",
      {t["name"] for t in nep.vragen[0]["tools"]} == {"web_search", "web_fetch"}
      and all(t.get("max_uses") for t in nep.vragen[0]["tools"]))
check("de werkwijze gaat letterlijk mee", "werkwijze" in nep.vragen[0]["system"] and "collega's" in nep.vragen[0]["system"])
check("gegevens, gelezen pagina's en tellers terug", uit["gegevens"]["vraag_kort"] == "vloerwasser X1 voor Suriname"
      and set(uit["gelezen"]) == {"https://winkel.voorbeeld.com/x1"} and uit["zoekopdrachten"] == 1 and uit["tokens"] == 2400)
goed, weg = O.alleen_gelezen(uit["gegevens"]["aanbiedingen"], uit["gelezen"])
for a in goed:
    a["gezien_op"] = "2026-10-30"
r = A.verwerk(goed, VANDAAG, KOERSEN, uit["gegevens"]["eisen"])
r["afgewezen"] = weg + r["afgewezen"]
tekst = V.maak("Vloerwasser X1 voor Suriname", uit["gegevens"], r, "2026-10-30", "2026-10-30")
check("het verslag begint met de aanbeveling", tekst.startswith("**Aanbevolen:** [X1](https://winkel.voorbeeld.com/x1)"))
check("het verzonnen aanbod staat niet in het verslag", "verzonnen" not in tekst)
check("het verslag zegt dat er niets gekocht is", "Ik kocht, bood en contacteerde niets." in tekst)
check("bedrag in Belgische schrijfwijze", V.euro(1299.5) == "1.299,50 euro")
check("titel met het beste totaal", V.titel(uit["gegevens"], r) == "Prijsonderzoek: vloerwasser X1 voor Suriname (beste 499,00 euro)")
leeg = A.verwerk([], VANDAAG, KOERSEN)
check("zonder goed aanbod geen aanbeveling", V.maak("v", {}, leeg, None, "2026-10-30").startswith("**Geen aanbeveling:**"))

print("Plafond, reservemodel en reserve-aanbod")
O.MAX_TOKENS = 1000
nep = NepClient([NepAntwoord(BLOKKEN[:4], "pause_turn"), NepAntwoord([{"type": "text", "text": JSON}], "end_turn")])
uit = O.onderzoek("Vloerwasser X1", "w", "", "", "2026-10-30", client=nep)
check("boven het tokenplafond geen nieuwe beurt", len(nep.vragen) == 1 and uit["stop"] == "plafond")
O.MAX_TOKENS = 150000


class NotFoundError(Exception):
    pass


class NepOnbekendModel(NepClient):
    def create(self, **kw):
        if kw["model"] == O.MODEL:
            self.vragen.append(kw)
            raise NotFoundError("model niet gevonden")
        return NepClient.create(self, **kw)


nep = NepOnbekendModel([NepAntwoord([{"type": "text", "text": JSON}], "end_turn")])
uit = O.onderzoek("Vloerwasser X1", "w", "", "", "2026-10-30", client=nep)
check("een onbekende modelnaam valt terug op het model van De Ontwikkelaar (K5)", uit["model"] == O.RESERVE_MODEL
      and nep.vragen[-1]["model"] == O.RESERVE_MODEL and uit["gegevens"] is not None)
r = A.verwerk([aanbod(prijs=500), aanbod(url="https://b.voorbeeld.com/2", prijs=520), aanbod(url="https://c.voorbeeld.com/3", prijs=480)],
              VANDAAG, KOERSEN)
check("een beste keuze en een reserve (overleg X2)", r["beste"]["prijs"] == 480 and r["reserve"]["prijs"] == 500)
tekst = V.maak("v", {"vervolgvraag": "Is het voor privé of voor een firma?"}, r, "2026-10-30", "2026-10-30")
check("de reserve en de vervolgvraag staan bovenaan", "**Reserve:**" in tekst.split("## Aanbiedingen")[0]
      and "**Vraag aan jou:** Is het voor privé of voor een firma?" in tekst)

print("Alleen de productvraag naar de AI (overleg X4 en K6)")
from aankoop import privacy as P  # noqa: E402

check("een gewone productvraag gaat door", P.gevonden(
    "Livox Mid-360 lidar, nieuw of tweedehands, levering in Belgie, voor een firma, voor half november, budget 900 euro") == [])
check("spanning, frequentie en modelnummers zijn geen persoonsgegevens",
      P.gevonden("MOVA V70 vloerwasser voor Suriname, 220 V 60 Hz, stekker type A/B, model RX-7900 XTX") == [])
check("een e-mailadres houdt de vraag tegen", P.gevonden("stuur naar iemand@voorbeeld.com") == ["e-mailadres"])
check("een telefoonnummer", P.gevonden("bel 0470 12 34 56") == ["telefoonnummer"])
check("een rekeningnummer", P.gevonden("betaal met BE68 5390 0754 7034") == ["rekeningnummer"])
check("een ondernemingsnummer", P.gevonden("factuur op 0123.456.789") == ["ondernemingsnummer"])
check("een adres", P.gevonden("leveren in de Voorbeeldstraat 12") == ["adres"])
check("het korte verslag zegt wat het zag, niet de gegevens zelf",
      "e-mailadres" in V.tegengehouden(["e-mailadres"]) and "@" not in V.tegengehouden(["e-mailadres"]))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

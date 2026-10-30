"""Grendels van De Prijsonderzoeker: wat nooit in een prijsverslag mag, en hoe het totaal en de rangorde ontstaan.

Driehoeksoverleg 30-10-2026 (ontwerp) en de controle van Codex daarna (X1 tot X9). Alleen verzonnen aanbiedingen en
voorbeeld.com-links; geen echte bestellingen of personen.

Draaien: python3 mijnagents-runner/tests/test_aankoop_prijs.py
"""
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "koppelingen"))
from aankoop import aanbod as A  # noqa: E402
from aankoop import koersen as K  # noqa: E402
from aankoop import onderzoek as O  # noqa: E402
from aankoop import privacy as P  # noqa: E402
from aankoop import verslag as V  # noqa: E402

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
VULLING = " Productomschrijving, specificaties, levering en retour volgens de voorwaarden van de winkel." * 4


def aanbod(**over):
    basis = {"titel": "Vloerwasser X1", "url": "https://winkel.voorbeeld.com/x1", "winkel": "Winkel", "land": "BE",
             "soort": "nieuw", "prijs": 500, "munt": "EUR", "btw_inbegrepen": True, "verzending": 0,
             "gezien_op": "2026-10-30", "beschikbaar": True}
    basis.update(over)
    return basis


def pagina(*stukken):
    return " ".join(stukken) + VULLING


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

print("De prijs staat op de gelezen pagina (Codex X1)")
check("een lege pagina telt niet als gelezen", "pagina zonder leesbare tekst" in A.keur(aanbod(), VANDAAG, ""))
check("een pagina met alleen een titel telt niet", "pagina zonder leesbare tekst" in A.keur(aanbod(), VANDAAG, "Vloerwasser X1 500"))
check("een prijs die niet op de pagina staat", "prijs niet op de gelezen pagina" in
      A.keur(aanbod(prijs=450), VANDAAG, pagina("Vloerwasser X1 voor 500,00 euro")))
check("Belgische schrijfwijze op de pagina", A.keur(aanbod(prijs=1299), VANDAAG, pagina("Prijs: 1.299,00 €")) == [])
check("Engelse schrijfwijze op de pagina", A.keur(aanbod(prijs=1299, munt="USD", land="US"), VANDAAG, pagina("$1,299.00")) == [])
check("schrijfwijze met streepje", A.keur(aanbod(prijs=1299), VANDAAG, pagina("nu 1299,-")) == [])
check("met centen", A.keur(aanbod(prijs=499.95), VANDAAG, pagina("€ 499,95")) == [])
check("499 is niet 1499", not A.bedrag_op_pagina(499, "1499 euro"))
check("499 is niet 499,99", not A.bedrag_op_pagina(499, "499,99 euro"))
check("procent op de pagina", A.procent_op_pagina(18, "opgeld 18 % excl. btw") and not A.procent_op_pagina(8, "opgeld 18%"))

print("Bedragen en omrekening")
check("Belgische schrijfwijze", A._getal("1.299,00") == 1299.0)
check("Engelse schrijfwijze", A._getal("1,299.00") == 1299.0)
check("decimale komma", A._getal("49,95") == 49.95)
check("een boolean is geen bedrag", A._getal(True) is None)
check("dollar naar euro met de ECB-koers", round(A.in_euro(110, "USD", KOERSEN), 2) == 100.0)
check("zonder koers geen bedrag", A.in_euro(100, "CNY", KOERSEN) is None)

print("Totaalprijs, btw en invoer (Codex X9)")
check("binnen de EU met btw: prijs plus verzending", A.totaal(aanbod(prijs=500, verzending=25), KOERSEN)[:2] == (525.0, []))
check("zonder verzending is het totaal onvolledig", A.totaal(aanbod(verzending=None), KOERSEN)[:2] == (None, ["verzending"]))
check("onbekend of de btw erin zit: onvolledig", A.totaal(aanbod(btw_inbegrepen=None), KOERSEN)[:2] == (None, ["btw"]))
t = A.totaal(aanbod(prijs=1000, verzending=0, btw_inbegrepen=False), KOERSEN)
check("een prijs zonder btw krijgt 21 procent erbij", t[0] == 1210.0 and "21 procent btw bijgeteld" in t[2], str(t))
t = A.totaal(aanbod(soort="veiling", prijs=1000, verzending=50, veilingkosten=0), KOERSEN)
check("een veilingprijs zonder opgeld is geen totaalprijs", t[:2] == (None, ["opgeld"]), str(t))
t = A.totaal(aanbod(soort="veiling", prijs=1000, verzending=50, opgeld_pct=18), KOERSEN)
check("onbekende vaste veilingkosten tellen niet als nul (overleg K3)", t[:2] == (None, ["veilingkosten"]), str(t))
t = A.totaal(aanbod(soort="veiling", prijs=1000, verzending=50, opgeld_pct=18, veilingkosten=10), KOERSEN)
check("veiling met opgeld en kosten", t[:2] == (1240.0, []), str(t))
tekst = pagina("Hamerprijs 1.000 euro; verzending 50 euro; kosten 10 euro")
t = A.totaal(aanbod(soort="veiling", prijs=1000, verzending=50, opgeld_pct=18, veilingkosten=10), KOERSEN, tekst)
check("opgeld dat op geen gelezen pagina staat, maakt het totaal onvolledig", t[:2] == (None, ["opgeld niet op een gelezen pagina"]), str(t))
t = A.totaal(aanbod(soort="veiling", prijs=1000, verzending=50, opgeld_pct=18, veilingkosten=10), KOERSEN, tekst + " opgeld 18%")
check("met de veilingvoorwaarden gelezen is het totaal volledig", t[:2] == (1240.0, []), str(t))
t = A.totaal(aanbod(prijs=500, verzending=25), KOERSEN, pagina("500 euro"))
check("een verzendprijs die nergens staat, is niet bewezen", t[:2] == (None, ["verzending niet op een gelezen pagina"]), str(t))
t = A.totaal(aanbod(land="US", munt="USD", prijs=550, verzending=55), KOERSEN)
check("buiten de EU zonder douane is onvolledig", t[:2] == (None, ["invoer"]), str(t))
t = A.totaal(aanbod(land="US", munt="USD", prijs=550, verzending=55, douane=22), KOERSEN)
check("buiten de EU: douane en 21 procent btw door de code", t[0] == 689.7 and "invoer" in t[2][0], str(t))
check("zonder land geldt het als onvolledig", A.totaal(aanbod(land=""), KOERSEN)[:2] == (None, ["land"]))

print("Eisen uit de vraag, niet alleen van het model (Codex X2)")
check("Suriname wordt 60 Hz", A.eisen_uit_vraag("vloerwasser MOVA V70 voor Suriname") == ["netfrequentie 60 Hz"])
check("spanning en frequentie letterlijk", A.eisen_uit_vraag("toestel op 220 V en 60 Hz")
      == ["netfrequentie 60 Hz", "netspanning 220 V"])
check("een lidar zonder bestemming heeft geen vaste eisen", A.eisen_uit_vraag("Livox Mid-360 lidar, levering in Belgie") == [])
eisen = A.eisen_uit_vraag("vloerwasser voor Suriname")
r = A.verwerk([aanbod(prijs=300), aanbod(url="https://b.voorbeeld.com/1", prijs=450,
                                          compatibiliteit={"netfrequentie 60 Hz": "nee"})], VANDAAG, KOERSEN, eisen)
check("model vergat de eis: het goedkope toestel is onbekend en nooit de beste", r["beste"] is None
      and r["goed"][0]["compatibel"] == "onbekend")
check("een toestel op 50 Hz staat apart als niet compatibel", len(r["niet_compatibel"]) == 1)

print("Compatibiliteit en rangorde")
eisen = ["netfrequentie 60 Hz", "stekker type A/B"]
check("een eis die nee is maakt het niet compatibel", A.compatibel(aanbod(compatibiliteit={e: "nee" for e in eisen}), eisen) == "nee")
check("alle eisen ja", A.compatibel(aanbod(compatibiliteit={e: "ja" for e in eisen}), eisen) == "ja")
check("een eis zonder oordeel is onbekend", A.compatibel(aanbod(compatibiliteit={eisen[0]: "ja"}), eisen) == "onbekend")
check("zonder eisen altijd compatibel", A.compatibel(aanbod(), []) == "ja")
r = A.verwerk([
    aanbod(prijs=300, compatibiliteit={e: "nee" for e in eisen}),
    aanbod(url="https://b.voorbeeld.com/1", prijs=450, compatibiliteit={e: "ja" for e in eisen}),
    aanbod(url="https://c.voorbeeld.com/1", prijs=400, verzending=None, compatibiliteit={e: "ja" for e in eisen}),
    aanbod(url="https://d.voorbeeld.com/1", prijs=420, compatibiliteit={eisen[0]: "ja"}),
    aanbod(url="", prijs=100),
    aanbod(url="https://b.voorbeeld.com/1/", prijs=450, compatibiliteit={e: "ja" for e in eisen}),
], VANDAAG, KOERSEN, eisen)
check("het goedkoopste maar niet compatibele aanbod staat apart", [a["prijs"] for a in r["niet_compatibel"]] == [300])
check("het beste is compatibel en volledig", r["beste"]["url"] == "https://b.voorbeeld.com/1")
check("geen reserve als er maar een volledig en compatibel aanbod is", r["reserve"] is None)
check("onvolledig totaal komt achteraan", r["goed"][-1]["url"] == "https://c.voorbeeld.com/1")
check("zonder link afgewezen, met reden", any("geen werkende link" in a["redenen"] for a in r["afgewezen"]))
check("dezelfde link twee keer telt een keer", any(a["redenen"] == ["dubbel"] for a in r["afgewezen"]))
r = A.verwerk([aanbod(prijs=500), aanbod(url="https://b.voorbeeld.com/2", prijs=520),
               aanbod(url="https://c.voorbeeld.com/3", prijs=480)], VANDAAG, KOERSEN)
check("een beste keuze en een reserve (overleg X2)", r["beste"]["prijs"] == 480 and r["reserve"]["prijs"] == 500)
r = A.verwerk([aanbod(soort="veiling", prijs=100, veilingkosten=0)], VANDAAG, KOERSEN)
check("een veiling zonder opgeld wordt nooit het beste aanbod", r["beste"] is None and len(r["goed"]) == 1)
paginas = {"https://winkel.voorbeeld.com/x1": pagina("X1 nu 500,00 euro")}
r = A.verwerk([aanbod(), aanbod(url="https://andere.voorbeeld.com/x1")], VANDAAG, KOERSEN, paginas=paginas)
check("met de gelezen pagina's: alleen het aanbod met bewezen prijs gaat door", len(r["goed"]) == 1
      and r["afgewezen"][0]["redenen"] == ["pagina zonder leesbare tekst"], str(r["afgewezen"]))

print("Alleen gelezen pagina's (onderzoek)")
check("www, http en fragment tellen niet", O.schoon_url("http://WWW.Winkel.voorbeeld.com/x1/#foto")
      == "https://winkel.voorbeeld.com/x1")
check("de query telt wel (product-id)", O.schoon_url("https://w.voorbeeld.com/p?id=1") != O.schoon_url("https://w.voorbeeld.com/p?id=2"))
PAGINA_X1 = pagina("X1 499,00 euro ![X1](https://cdn.voorbeeld.com/x1.jpg)")
BLOKKEN = [
    {"type": "server_tool_use", "name": "web_search", "input": {"query": "vloerwasser x1"}},
    {"type": "web_search_tool_result", "content": [{"type": "web_search_result", "url": "https://zoek.voorbeeld.com/a"}]},
    {"type": "server_tool_use", "name": "web_fetch", "input": {"url": "https://winkel.voorbeeld.com/x1"}},
    {"type": "web_fetch_tool_result", "content": {"type": "web_fetch_result", "url": "https://winkel.voorbeeld.com/x1",
                                                  "content": {"type": "document", "source": {"type": "text", "data": PAGINA_X1}}}},
    {"type": "web_fetch_tool_result", "content": {"type": "web_fetch_tool_error", "error_code": "url_not_accessible"}},
]
gelezen = O.gelezen_paginas(BLOKKEN)
check("alleen een geslaagde web_fetch telt als gelezen", set(gelezen) == {"https://winkel.voorbeeld.com/x1"}, str(gelezen))
check("met de tekst van de pagina", "499,00 euro" in gelezen["https://winkel.voorbeeld.com/x1"])
goed, weg = O.alleen_gelezen([aanbod(), aanbod(url="https://zoek.voorbeeld.com/a"), aanbod(url="https://verzonnen.voorbeeld.com/z")], gelezen)
check("een link uit een zoekresultaat alleen gaat er niet in", len(goed) == 1 and len(weg) == 2
      and all(w["redenen"] == ["pagina niet gelezen in deze ronde"] for w in weg))
goed, _ = O.alleen_gelezen([aanbod(foto="https://cdn.voorbeeld.com/x1.jpg")], gelezen)
check("een foto die op de gelezen pagina staat, blijft", goed[0]["foto"] == "https://cdn.voorbeeld.com/x1.jpg")
goed, _ = O.alleen_gelezen([aanbod(foto="https://cdn.voorbeeld.com/verzonnen.jpg")], gelezen)
check("een foto die niet op de pagina staat, wordt nooit getoond (overleg X5)", goed[0]["foto"] is None)
check("JSON uit een ```json-blok", O.json_uit('Uitleg\n```json\n{"eisen": []}\n```') == {"eisen": []})
check("het laatste blok telt", O.json_uit('```json\n{"a": 1}\n```\n```json\n{"a": 2}\n```') == {"a": 2})
check("geen JSON geeft None", O.json_uit("ik vond niets") is None)


class NepAntwoord:
    def __init__(self, inhoud, stop, tokens=(1000, 200)):
        self.content, self.stop_reason = inhoud, stop
        self.usage = {"input_tokens": tokens[0], "output_tokens": tokens[1]}


class NepClient:
    """Bootst de Messages-API na; bewaart een kopie van elke vraag."""
    def __init__(self, antwoorden):
        self.antwoorden, self.vragen = list(antwoorden), []
        self.messages = self

    def create(self, **kw):
        kw = dict(kw, messages=[dict(m, content=list(m["content"]) if isinstance(m["content"], list) else m["content"])
                                for m in kw["messages"]])
        self.vragen.append(kw)
        return self.antwoorden.pop(0)


JSON = ('```json\n{"vraag_kort": "vloerwasser X1 voor Suriname", "eisen": [], '
        '"aanbiedingen": [{"titel": "X1", "url": "https://winkel.voorbeeld.com/x1", "winkel": "W", "land": "BE", '
        '"soort": "nieuw", "prijs": 499, "munt": "EUR", "btw_inbegrepen": true, "verzending": 0, "beschikbaar": true, '
        '"compatibiliteit": {"netfrequentie 60 Hz": "ja"}, "waarom": "60 Hz-versie, officiele dealer."}, '
        '{"titel": "X1 verzonnen", "url": "https://verzonnen.voorbeeld.com/z", "soort": "nieuw", "prijs": 10, "munt": "EUR", '
        '"land": "BE", "verzending": 0}], "advies": "Koop X1 verzonnen, die is het goedkoopst."}\n```')
STUK1 = BLOKKEN[:2]
STUK2 = BLOKKEN[2:4]
nep = NepClient([NepAntwoord(STUK1, "pause_turn"), NepAntwoord(STUK2, "pause_turn"),
                 NepAntwoord([{"type": "text", "text": JSON}], "end_turn")])
uit = O.onderzoek("Vloerwasser X1 voor Suriname", "WERKWIJZE", "2026-10-30", ["netfrequentie 60 Hz"], client=nep)
check("na twee pauzes gaat de hele beurt mee, niet alleen het laatste stuk (Codex X8)",
      len(nep.vragen) == 3 and nep.vragen[2]["messages"][-1]["content"] == STUK1 + STUK2, str([len(v["messages"]) for v in nep.vragen]))
check("de plafonds tellen over alle beurten (Codex X7)",
      [t["max_uses"] for t in nep.vragen[0]["tools"]] == [O.MAX_ZOEKEN, O.MAX_LEZEN]
      and [t["max_uses"] for t in nep.vragen[2]["tools"]] == [O.MAX_ZOEKEN - 1, O.MAX_LEZEN - 1])
check("de werkwijze gaat mee, maar geen naam, collega's of lessen (Codex X4)", "WERKWIJZE" in nep.vragen[0]["system"]
      and "Mehdi" not in nep.vragen[0]["system"] and "collega" not in nep.vragen[0]["system"].lower())
check("de vaste eisen staan in de vraag aan het model", "VASTE EISEN" in nep.vragen[0]["messages"][0]["content"]
      and "netfrequentie 60 Hz" in nep.vragen[0]["messages"][0]["content"])
check("gegevens, gelezen pagina's en tellers terug", uit["gegevens"]["vraag_kort"] == "vloerwasser X1 voor Suriname"
      and set(uit["gelezen"]) == {"https://winkel.voorbeeld.com/x1"} and uit["zoekopdrachten"] == 1 and uit["tokens"] == 3600)
goed, weg = O.alleen_gelezen(uit["gegevens"]["aanbiedingen"], uit["gelezen"])
for a in goed:
    a["gezien_op"] = "2026-10-30"
r = A.verwerk(goed, VANDAAG, KOERSEN, ["netfrequentie 60 Hz"], paginas=uit["gelezen"])
r["afgewezen"] = weg + r["afgewezen"]
tekst = V.maak("Vloerwasser X1 voor Suriname", uit["gegevens"], r, "2026-10-30", "2026-10-30")
check("het verslag begint met de aanbeveling", tekst.startswith("**Aanbevolen:** [X1](https://winkel.voorbeeld.com/x1)"), tekst[:120])
check("het verzonnen aanbod staat nergens in het verslag, ook niet via vrij advies (Codex X2)", "verzonnen" not in tekst)
check("de uitleg van het model staat bij het aanbod", "60 Hz-versie, officiele dealer." in tekst)
check("het verslag zegt dat er niets gekocht is", "Ik kocht, bood en contacteerde niets." in tekst)
check("bedrag in Belgische schrijfwijze", V.euro(1299.5) == "1.299,50 euro")
check("titel met het beste totaal", V.titel(uit["gegevens"], r) == "Prijsonderzoek: vloerwasser X1 voor Suriname (beste 499,00 euro)")
check("zonder goed aanbod geen aanbeveling", V.maak("v", {}, A.verwerk([], VANDAAG, KOERSEN), None, "2026-10-30")
      .startswith("**Geen aanbeveling:**"))
r = A.verwerk([aanbod(prijs=500), aanbod(url="https://b.voorbeeld.com/2", prijs=520)], VANDAAG, KOERSEN)
tekst = V.maak("v", {"vervolgvraag": "Is het voor privé of voor een firma?"}, r, "2026-10-30", "2026-10-30")
check("de reserve en de vervolgvraag staan bovenaan", "**Reserve:**" in tekst.split("## Aanbiedingen")[0]
      and "**Vraag aan jou:** Is het voor privé of voor een firma?" in tekst)

print("Plafonds en reservemodel")
nep = NepClient([NepAntwoord(STUK1, "pause_turn", (200000, 100)), NepAntwoord([{"type": "text", "text": JSON}], "end_turn")])
uit = O.onderzoek("Vloerwasser X1", "w", "2026-10-30", client=nep)
check("boven het tokenplafond geen nieuwe beurt", len(nep.vragen) == 1 and uit["stop"] == "plafond")
nep = NepClient([NepAntwoord(STUK1, "pause_turn"), NepAntwoord([{"type": "text", "text": JSON}], "end_turn")])
uit = O.onderzoek("Vloerwasser X1", "w", "2026-10-30", deadline=time.monotonic() + 10, client=nep)
check("na de deadline van de ronde geen nieuwe beurt (Codex X6)", len(nep.vragen) == 1 and uit["stop"] == "plafond")
check("de wachttijd van een beurt blijft binnen de deadline", nep.vragen[0]["timeout"] <= 30.0)


class NotFoundError(Exception):
    pass


class NepOnbekendModel(NepClient):
    def create(self, **kw):
        if kw["model"] == O.MODEL:
            self.vragen.append(kw)
            raise NotFoundError("model niet gevonden")
        return NepClient.create(self, **kw)


nep = NepOnbekendModel([NepAntwoord([{"type": "text", "text": JSON}], "end_turn")])
uit = O.onderzoek("Vloerwasser X1", "w", "2026-10-30", client=nep)
check("een onbekende modelnaam valt terug op het model van De Ontwikkelaar (K5)", uit["model"] == O.RESERVE_MODEL
      and nep.vragen[-1]["model"] == O.RESERVE_MODEL and uit["gegevens"] is not None)

print("Alleen de productvraag naar de AI (overleg X4 en K6, Codex X3)")
check("een gewone productvraag gaat door", P.gevonden(
    "Livox Mid-360 lidar, nieuw of tweedehands, levering in Belgie, voor een firma, voor half november, budget 900 euro") == [])
check("spanning, frequentie, merken en modelnummers zijn geen persoonsgegevens",
      P.gevonden("MOVA V70 vloerwasser voor Suriname, 220 V 60 Hz, stekker type A/B, bandje voor Apple Watch, "
                 "voor Harmonie Bouw, monitor 1 ms Reactietijd, model RX-7900 XTX") == [])
check("een e-mailadres houdt de vraag tegen", P.gevonden("stuur naar iemand@voorbeeld.com") == ["e-mailadres"])
check("een telefoonnummer", P.gevonden("bel 0470 12 34 56") == ["telefoonnummer"])
check("een rekeningnummer", P.gevonden("betaal met BE68 5390 0754 7034") == ["rekeningnummer"])
check("een ondernemingsnummer", P.gevonden("factuur op 0123.456.789") == ["ondernemingsnummer"])
check("een adres", P.gevonden("leveren in de Voorbeeldstraat 12") == ["adres"])
check("een naam met aanspreking", P.gevonden("droger voor mevrouw Proefnaam") == ["naam"])
check("een klant met voor- en achternaam", P.gevonden("klant Jan Proefnaam wil een droger") == ["naam"])
check("het korte verslag zegt wat het zag, niet de gegevens zelf",
      "e-mailadres" in V.tegengehouden(["e-mailadres"]) and "@" not in V.tegengehouden(["e-mailadres"]))

print("De runner: geen vraag in het logboek, een deadline per ronde")
import prijsonderzoeker as PO  # noqa: E402

logboek, klaar, opgepakt, noden = [], [], [], []
PO.ag.log = lambda *a: logboek.append(a)
PO.ag.klaarzet = lambda items: klaar.extend(items)
PO.bord.opgepakt = lambda kid, door: opgepakt.append(kid)
PO.K.haal = lambda: ("2026-10-30", KOERSEN)


class NepRonde:
    werkwijze = "## Wat ik nooit doe\n\n- nooit kopen\n\n## Wat Mehdi beslist\n\n- de aankoop\n"
    detail = ""

    def nood(self, tekst, wie="mehdi"):
        noden.append(tekst)

    def bron(self, naam, inhoud):
        pass


GEHEIM = "Proefvraag-zeven-zeven"
PO.O.onderzoek = lambda *a, **k: {"gegevens": None, "gelezen": {}, "tekst": "", "tokens": 10, "zoekopdrachten": 0,
                                  "stop": "end_turn", "model": "m"}
PO.werk(NepRonde(), f"vloerwasser {GEHEIM}")
check("de vraag staat nooit in het logboek, ook niet bij een fout (Codex X3)",
      logboek and not any(GEHEIM in str(x) for x in logboek), str(logboek)[:300])
check("ook zonder antwoord krijgt Mehdi een verslag", klaar and klaar[-1]["soort"] == "prijsverslag")
logboek.clear()
PO.werk(NepRonde(), "droger voor mevrouw Proefnaam")
check("een vraag met persoonsgegevens gaat niet naar het model", klaar[-1]["titel"] == "Prijsvraag niet verstuurd: persoonsgegevens"
      and not any("Proefnaam" in str(x) for x in logboek))
PO.open_vragen = lambda: [{"id": 7, "inhoud": "lidar"}, {"id": 8, "inhoud": "drone"}]
r = NepRonde()
PO.werk(r, None, False, begin=time.monotonic() - PO.RONDE_SECONDEN)
check("zonder tijd over blijft een klaargezette vraag staan (Codex X6)", opgepakt == [] and "2 wachten" in r.detail, r.detail)

print("Koersen van de ECB")
XML = """<gesmes:Envelope><Cube><Cube time='2026-10-30'>
<Cube currency='USD' rate='1.0812'/><Cube currency='GBP' rate='0.8461'/></Cube></Cube></gesmes:Envelope>"""
datum, k = K.lees(XML)
check("datum en koersen gelezen", datum == "2026-10-30" and k == {"USD": 1.0812, "GBP": 0.8461}, str(k))
check("onleesbaar geeft niets", K.lees("geen xml") == (None, {}))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

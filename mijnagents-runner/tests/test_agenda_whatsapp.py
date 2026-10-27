"""Grendel: WhatsApp-melding als de Agendawacht een afspraak uit mail zet (Mehdi, 27-10-2026; driehoeksoverleg W1-W10).

Een nieuw of verschoven zorgblok uit mail geeft eenmaal een korte WhatsApp (wat, wanneer, agenda, botsing). Bij een
botsing, ook met een hele-dag-blok zoals 'ANTWERK vakbeurs', staat het blok op '??' tot Mehdi antwoordt met de code
('A1 ja' of 'A1 vervalt'). Alleen De Bode verstuurt, alleen via WhatsApp, nooit in de stille uren. Geen netwerk.
"""
import json
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

os.environ["BELLEN_UIT"] = "1"
HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W          # noqa: E402
import agenda_whatsapp as AW      # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw-")) / "agenda-whatsapp.json")
_nu = W.nu_lokaal()
d0 = (_nu + timedelta(days=9)).date().isoformat()
d1 = (_nu + timedelta(days=8)).date().isoformat()
d2 = (_nu + timedelta(days=10)).date().isoformat()


def item(i, titel, start, einde, kal=W.PRIVE_AGENDA, hele_dag=False, vrij=False, merk=None, locatie=""):
    return {"kalender": kal, "id": i, "titel": titel, "start": start, "einde": einde, "hele_dag": hele_dag,
            "_vrij": vrij, "_merk": merk or {}, "locatie": locatie, "omschrijving": "", "deelnemers": [],
            "_agendagasten": [], "maker": W.WERKAGENDA}


ecg = item("ecg", "!! [PR] Huisarts - Praktijk Verpleegkundigen", f"{d0}T10:15:00+01:00", f"{d0}T10:30:00+01:00",
           merk={W.ZORGMERK: "z1"}, locatie="Diestsesteenweg 49, 3010 Kessel-Lo")
antwerk = item("aw", "! Mehdi: ANTWERK vakbeurs (te verifiëren wo/do)", d1, d2, hele_dag=True)
vakantie = item("lv", "Lara: schoolvakantie Herfst", d1, d2, kal=W.KALENDERS and list(W.KALENDERS)[3], hele_dag=True, vrij=True)
heen = item("r1", "\U0001F697 Reistijd: thuis → Kessel-Lo", f"{d0}T10:00:00+01:00", f"{d0}T10:15:00+01:00")
klant = item("k1", "Mehdi: [HA-KB] klant", f"{d0}T10:20:00+01:00", f"{d0}T11:00:00+01:00", kal=W.WERKAGENDA)
vervallen = item("vv", "vervalt Mehdi: [HA-KB] oud", f"{d0}T10:00:00+01:00", f"{d0}T11:00:00+01:00", kal=W.WERKAGENDA)

# --- W3: de botsingscontrole telt hele-dag-blokken die Bezet staan ---------------------------------------------------
b = W.botst_met(ecg, [ecg, antwerk, vakantie, heen, vervallen])
check("het ECG botst met de ANTWERK-blokkade (hele dag, Bezet)", [y["id"] for y in b] == ["aw"], str([y["id"] for y in b]))
check("Beschikbaar (Lara-vakantie), de eigen rit en een vervallen afspraak tellen niet",
      not W.botst_met(ecg, [ecg, vakantie, heen, vervallen]))
check("een afspraak met een uur die overlapt, telt", [y["id"] for y in W.botst_met(ecg, [ecg, klant])] == ["k1"])
_bs = W.botsingen([ecg, antwerk, klant])
check("het bordsignaal telt het hele-dag-blok eenmaal per dag en toont geen privétitels",
      sum("(hele dag)" in r for r in _bs) == 1 and not any("Huisarts" in r for r in _bs) and "(privé)" in " ".join(_bs),
      str(_bs))

# --- W1, W2, W4, W8: de melding en '??' ------------------------------------------------------------------------
_pat, _gelezen = [], {}
_o = (W._patch, W._lees_event)
W._patch = lambda a, body, tok, **kw: _pat.append((a["id"], body)) or _gelezen.__setitem__(a["id"], body)
W._lees_event = lambda kal, eid, tok: {"summary": (_gelezen.get(eid) or {}).get("summary", ""), "description": "oud",
                                       "transparency": (_gelezen.get(eid) or {}).get("transparency")}
rust = item("rust", "!! [PR] Kine - Praktijk X", f"{d2}T09:00:00+01:00", f"{d2}T09:30:00+01:00", merk={W.ZORGMERK: "z2"})
try:
    r1 = W.zorg_whatsapp([ecg, antwerk, rust], "tok")
    d = AW._lees()
    r2 = W.zorg_whatsapp([ecg, antwerk, rust], "tok")
    nieuw = item("nieuw", "!! [PR] Tandarts - Praktijk Y", f"{d2}T14:00:00+01:00", f"{d2}T14:30:00+01:00",
                 merk={W.ZORGMERK: "z3"})
    r3 = W.zorg_whatsapp([ecg, antwerk, rust, nieuw], "tok")
    rust_later = dict(rust, start=f"{d2}T11:00:00+01:00", einde=f"{d2}T11:30:00+01:00")
    r4 = W.zorg_whatsapp([ecg, antwerk, rust_later, nieuw], "tok")
finally:
    W._patch, W._lees_event = _o
m = {k: v for k, v in AW._lees()["meldingen"].items() if v.get("status") != "basis"}
ecg_m = next(v for k, v in m.items() if k.startswith("zorg:ecg:"))
check("eerste ronde: alleen het blok dat nu botst (het ECG) krijgt een melding; de rest wordt stil bekend (W8)",
      len([k for k in d["meldingen"] if d["meldingen"][k].get("status") == "klaar"]) == 1
      and d["meldingen"].get(f"zorg:rust:{rust['start']}:{rust['einde']}", {}).get("status") == "basis", str(d))
check("het ECG staat op ?? (na !!), met de botsing bovenaan de omschrijving, en wacht op antwoord (W4)",
      _pat and _pat[0][1]["summary"].startswith("!! ?? [PR] Huisarts") and "ANTWERK" in _pat[0][1]["description"]
      and ecg_m.get("vraag") == {"id": "ecg"}, str(_pat[:1]))
check("de ??-titel blijft geldig voor de zorgcontrole (nog [PR], niet VR, geen 'Agendawacht vraagt')",
      "[PR]" in _pat[0][1]["summary"] and not _pat[0][1]["summary"].startswith("VR")
      and "Agendawacht vraagt" not in _pat[0][1]["description"])
check("en de volgorde van tekens_vooraan blijft (geen gevecht met '!! vooraan')",
      W.tekens_vooraan(_pat[0][1]["summary"]) == _pat[0][1]["summary"])
t = ecg_m["tekst"]
check("de melding zegt wat, wanneer, welke agenda en de botsing, met de code (W2)",
      "Wat: Huisarts - Praktijk Verpleegkundigen" in t and f"Wanneer: {W.WEEKDAG[W.datetime.fromisoformat(ecg['start']).weekday()]}" in t
      and "10:15-10:30" in t and "Agenda: privé" in t and "Botsing: ANTWERK vakbeurs" in t and "(hele dag" in t
      and f"'{ecg_m['code']} ja'" in t and f"'{ecg_m['code']} vervalt'" in t, t)
check("geen adres en geen mailinhoud in de melding", "Diestsesteenweg" not in t and "Kessel-Lo" not in t)
check("de tweede ronde zet niets opnieuw klaar (eenmaal per versie)", not r2, str(r2))
check("na de basislijn krijgt een nieuw zorgblok zonder botsing een melding zonder vraag",
      any("klaargezet" in r for r in r3) and next(v for k, v in AW._lees()["meldingen"].items() if k.startswith("zorg:nieuw:"))
      .get("vraag") is None and "Botsing: geen" in next(v for k, v in AW._lees()["meldingen"].items()
                                                         if k.startswith("zorg:nieuw:"))["tekst"], str(r3))
check("een verschoven zorgblok krijgt een nieuwe melding 'verschoven'",
      any("verschoven" in v.get("tekst", "") for k, v in AW._lees()["meldingen"].items() if k.startswith("zorg:rust:")), str(r4))
check("het werkverslag noemt geen titel (medisch is privé)", not any("Huisarts" in r or "Kine" in r for r in r1 + r3 + r4))

# --- W6, W7, W1: versturen door De Bode ------------------------------------------------------------------------
class Plafond(Exception):
    pass


gestuurd = []
nood = []
check("in de stille uren gaat er niets", AW.versturen(lambda t, kop: gestuurd.append(t), nood, True, (Plafond,)) == 0
      and not gestuurd)
n = AW.versturen(lambda t, kop: gestuurd.append((kop, t)) or "whatsapp-sjabloon", nood, False, (Plafond,))
check("buiten de stille uren gaan de klaarstaande meldingen via WhatsApp, met de kop Agendawacht",
      n == len(gestuurd) >= 3 and all(k == "Agendawacht" for k, _ in gestuurd), str(gestuurd[:1]))
check("een verzonden melding gaat geen tweede keer", AW.versturen(lambda t, kop: gestuurd.append(t), nood, False, (Plafond,)) == 0)
AW.klaarzetten("proef:plafond", "x")
nood = []
AW.versturen(lambda t, kop: (_ for _ in ()).throw(Plafond("dagplafond")), nood, False, (Plafond,))
check("bij een vol dagplafond blijft de melding klaar staan en komt er een nood zonder teller (W7)",
      AW._lees()["meldingen"]["proef:plafond"]["status"] == "klaar" and nood and not any(c.isdigit() for c in nood[0]["tekst"]),
      str(nood))
for _ in range(AW.MAX_POGINGEN):
    AW.versturen(lambda t, kop: (_ for _ in ()).throw(RuntimeError("Meta weigerde het bericht")), [], False, (Plafond,))
check("weigert Meta het bericht drie keer, dan 'mislukt' met een nood", AW._lees()["meldingen"]["proef:plafond"]["status"] == "mislukt")
AW.klaarzetten("proef:tijd", "x")
nood = []
AW.versturen(lambda t, kop: (_ for _ in ()).throw(TimeoutError()), nood, False, (Plafond,))
check("een time-out: misschien vertrokken, dus 'onzeker' en niet opnieuw (W1)",
      AW._lees()["meldingen"]["proef:tijd"]["status"] == "onzeker" and nood)
AW.klaarzetten("proef:bezig", "x")
with AW._bewerk() as _d:
    _d["meldingen"]["proef:bezig"]["status"] = "bezig"          # een vorige ronde stopte tijdens het versturen
gestuurd2, nood = [], []
AW.versturen(lambda t, kop: gestuurd2.append(t), nood, False, (Plafond,))
check("een melding die 'bezig' bleef (onderbroken), wordt niet blind opnieuw gestuurd maar onzeker en een nood",
      not gestuurd2 and AW._lees()["meldingen"]["proef:bezig"]["status"] == "onzeker" and nood)

# --- W5: het antwoord met code ---------------------------------------------------------------------------------
code = ecg_m["code"]
check("een los 'ja' is geen agendaantwoord: het gaat gewoon naar De Regisseur", AW.antwoord_herkennen("ja") is None)
check("'A4 papier' is geen agendaantwoord", AW.antwoord_herkennen("A4 papier graag") is None)
check("een onbekende code krijgt uitleg", "ken geen vraag" in (AW.antwoord_herkennen("A999 ja") or ""))
check("'A1 nee' telt niet; ik leg uit welke antwoorden kunnen", "vervalt" in (AW.antwoord_herkennen(f"{code} nee") or "")
      and not ecg_m.get("antwoord") and not AW.open_antwoorden())
zin = AW.antwoord_herkennen(f"{code.lower()} Ja")
check("'a1 Ja' wordt herkend en vastgelegd, met een ontvangstbevestiging in de wachtrij",
      "ontvangen" in (zin or "") and AW.open_antwoorden() and AW.open_antwoorden()[0][1]["antwoord"] == "ja"
      and any(k.startswith(f"ontvangst:{code}:") for k in AW._lees()["meldingen"]), str(zin))
check("een tweede antwoord op dezelfde vraag verandert niets", "al beantwoord" in (AW.antwoord_herkennen(f"vervalt {code}") or ""))

# --- W5: verwerken door de Agendawacht, teruggelezen, dan bevestigd ---------------------------------------------
_pat2, _bewaard = [], {"summary": "!! ?? [PR] Huisarts - Praktijk Verpleegkundigen", "transparency": None}
_o2 = (W._patch, W._lees_event, W._prive_item_lezen)
W._prive_item_lezen = lambda eid, tok: dict(ecg, titel=_bewaard["summary"]) if eid == "ecg" else None
W._patch = lambda a, body, tok, **kw: _pat2.append(body) or _bewaard.update(body)
W._lees_event = lambda kal, eid, tok: dict(_bewaard)
try:
    rv = W.whatsapp_antwoorden_verwerken("tok")
    AW.klaarzetten("zorg:ecg:later", "x", {"id": "ecg"})
    c2 = AW._lees()["meldingen"]["zorg:ecg:later"]["code"]
    AW.antwoord_herkennen(f"{c2} vervalt")
    rv2 = W.whatsapp_antwoorden_verwerken("tok")
    AW.klaarzetten("zorg:weg:1", "x", {"id": "weg"})
    AW.antwoord_herkennen(f"{AW._lees()['meldingen']['zorg:weg:1']['code']} ja")
    rv3 = W.whatsapp_antwoorden_verwerken("tok")
finally:
    W._patch, W._lees_event, W._prive_item_lezen = _o2
check("'ja': ?? weg, de afspraak blijft staan, teruggelezen en bevestigd",
      _pat2[0] == {"summary": "!! [PR] Huisarts - Praktijk Verpleegkundigen"} and "vastgelegd" in rv[0]
      and any("blijft staan" in v.get("tekst", "") for v in AW._lees()["meldingen"].values()), str((_pat2[:1], rv)))
check("'vervalt': 'vervalt' vooraan en Beschikbaar, nooit gewist, en Mehdi belt zelf de praktijk",
      _pat2[1]["summary"].startswith("vervalt !! [PR] Huisarts") and _pat2[1]["transparency"] == "transparent"
      and any("Bel zelf de praktijk" in v.get("tekst", "") for v in AW._lees()["meldingen"].values()), str((_pat2[1:], rv2)))
check("een vervallen zorgblok krijgt geen rit en botst met niets meer", W.lara_vervalt({"titel": _pat2[1]["summary"]}))
check("staat de afspraak er niet meer, dan verandert er niets en zegt de bevestiging dat", "niets veranderd" in rv3[0], str(rv3))

# --- De Bode en het agendasignaal: de draden --------------------------------------------------------------------
bode = (HIER / "bode.py").read_text(encoding="utf-8")
check("De Bode verstuurt de agendameldingen met whatsapp.stuur zelf, dus nooit via Telegram (W6)",
      "agenda_whatsapp.versturen(\n        whatsapp.stuur, nood, stil" in bode)
check("De Bode herkent een agendaantwoord voor hij een bericht naar het bord stuurt",
      bode.index("agenda_whatsapp.antwoord_herkennen") < bode.index('uit = bord.call("/api/gesprek", {"aan": aan, "tekst": vraag, "van": "mehdi (whatsapp)"})'))
sig = (HIER / "agenda_signaal.py").read_text(encoding="utf-8")
check("het agendasignaal verwerkt de antwoorden om de 12 minuten", "W.whatsapp_antwoorden_verwerken()" in sig)
check("de wachtrij staat in mijnagents-data, niet op het bord of in de export",
      "mijnagents-data/agenda-whatsapp.json" in (HIER / "koppelingen" / "agenda_whatsapp.py").read_text(encoding="utf-8")
      and "klaarzet" not in (HIER / "koppelingen" / "agenda_whatsapp.py").read_text(encoding="utf-8").replace("klaarzetten", ""))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

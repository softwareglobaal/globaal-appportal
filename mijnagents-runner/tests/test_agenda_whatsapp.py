"""Grendel: WhatsApp-melding als de Agendawacht een afspraak uit mail zet (Mehdi, 27-10-2026; driehoeksoverleg W1-W10).

Een nieuw of verschoven zorgblok uit mail geeft eenmaal een korte WhatsApp (wat, wanneer, agenda, botsing). Bij een
botsing, ook met een hele-dag-blok zoals 'ANTWERK vakbeurs', staat het blok op '??' tot Mehdi antwoordt met de code
('A1 ja' of 'A1 vervalt'). Alleen De Bode verstuurt, alleen via WhatsApp, nooit in de stille uren. Geen netwerk.
"""
import json
import os
os.environ.setdefault("AGENDA_WHATSAPP_WACHTRIJ", os.path.join(__import__("tempfile").mkdtemp(prefix="aw-test-"), "agenda-whatsapp.json"))  # nooit de echte wachtrij
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
      and (d.get("laatste") or {}).get("rust") == [rust["start"], rust["einde"]]
      and not any(k.startswith("zorg:rust:") for k in d["meldingen"]), str(d))
check("het ECG staat op ?? (na !!), met de botsing bovenaan de omschrijving, en wacht op antwoord (W4)",
      _pat and _pat[0][1]["summary"].startswith("!! ?? [PR] Huisarts") and "ANTWERK" in _pat[0][1]["description"]
      and ecg_m.get("vraag") == {"id": "ecg", "start": ecg["start"], "einde": ecg["einde"]}, str(_pat[:1]))
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
check("'A999 ja' zonder zo'n vraag gaat gewoon naar het bord (review PR 113)", AW.antwoord_herkennen("A999 ja") is None)
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
    AW.klaarzetten("zorg:ecg:later", "x", {"id": "ecg", "start": ecg["start"], "einde": ecg["einde"]})
    c2 = AW._lees()["meldingen"]["zorg:ecg:later"]["code"]
    AW.antwoord_herkennen(f"{c2} vervalt")
    rv2 = W.whatsapp_antwoorden_verwerken("tok")
    AW.klaarzetten("zorg:weg:1", "x", {"id": "weg", "start": "", "einde": ""})
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

# --- Codex-controle PR 113 -----------------------------------------------------------------------------------
# punt 1: een antwoord over het oude uur verandert een verschoven afspraak niet
AW.klaarzetten("zorg:ecg:oud", "x", {"id": "ecg", "start": f"{d0}T09:00:00+01:00", "einde": f"{d0}T09:15:00+01:00"})
_c31 = AW._lees()["meldingen"]["zorg:ecg:oud"]["code"]
AW.antwoord_herkennen(f"{_c31} vervalt")
_pat31 = []
_o31 = (W._patch, W._prive_item_lezen)
W._prive_item_lezen = lambda eid, tok: dict(ecg, titel="!! ?? [PR] Huisarts - Praktijk Verpleegkundigen")
W._patch = lambda a, body, tok, **kw: _pat31.append(body)
try:
    _rv31 = W.whatsapp_antwoorden_verwerken("tok")
finally:
    W._patch, W._prive_item_lezen = _o31
check("een antwoord over het oude uur van een intussen verschoven afspraak verandert niets (punt 1)",
      not _pat31 and any("verschoven" in r for r in _rv31)
      and any("intussen verschoven" in v.get("tekst", "") for v in AW._lees()["meldingen"].values()), str(_rv31))

# punt 2: alleen het bericht dat nu vertrekt staat op 'bezig'
for i in range(3):
    AW.klaarzetten(f"proef:rij{i}", f"rij {i}")
_staten = []


def _kijk(t, kop):
    _staten.append(sorted(m["status"] for k, m in AW._lees()["meldingen"].items() if k.startswith("proef:rij")))
    return "whatsapp"


AW.versturen(_kijk, [], False, (Plafond,))
check("bij het versturen staat telkens alleen het vertrekkende bericht op 'bezig' (punt 2)",
      all(st.count("bezig") <= 1 for st in _staten) and sum(st.count("bezig") for st in _staten) == 3
      and all(m["status"] == "verzonden" for k, m in AW._lees()["meldingen"].items() if k.startswith("proef:rij")),
      str(_staten[-4:]))

# punt 3: een blok dat in de eerste ronde zelf gemaakt werd, krijgt zijn melding
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw3-")) / "agenda-whatsapp.json")
_vers = item("vers", "!! [PR] Tandarts - Praktijk Z", f"{d2}T15:00:00+01:00", f"{d2}T15:30:00+01:00",
             merk={W.ZORGMERK: "z9"})
_vers["_gemaakt"] = (W.nu_lokaal() + timedelta(seconds=5)).astimezone(W.ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S.000Z")
_oud = dict(item("oud", "!! [PR] Kine - Praktijk Q", f"{d2}T08:00:00+01:00", f"{d2}T08:30:00+01:00",
                 merk={W.ZORGMERK: "z8"}), _gemaakt="2026-01-01T00:00:00.000Z")
_r33 = W.zorg_whatsapp([_vers, _oud], "tok")
_m33 = AW._lees()["meldingen"]
check("eerste ronde: een zorgblok dat deze ronde gemaakt werd, krijgt toch zijn melding; een oud blok niet (punt 3)",
      any(k.startswith("zorg:vers:") and v.get("status") == "klaar" for k, v in _m33.items())
      and not any(k.startswith("zorg:oud:") for k in _m33) and AW.laatste("oud") == [_oud["start"], _oud["einde"]], str(_m33))

# punt 4: de archiefagenda's tellen mee, en een onleesbaar archief stopt de melding
_hoofd = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
_aanroep = _hoofd[_hoofd.index("een WhatsApp-melding per nieuw of verschoven zorgblok uit mail"):][:900]
_stap = _hoofd[_hoofd.index("def zorg_whatsapp_stap():"):][:1200]
check("de WhatsApp-controle leest ook de archiefagenda's en wacht als die niet te lezen zijn (punt 4)",
      "archief_afspraken(0, ZORG_WHATSAPP_DAGEN, alleen_lezen=True)" in _stap and "ARCHIEF_FOUT" in _stap
      and "zorg_whatsapp_stap()" in _aanroep)
_zr = _hoofd[_hoofd.index("def zorgronde():"):][:1500]
check("ook de zorgronde (--zorg) roept de meldstap aan, zodat geen blok zonder melding blijft (hertest PR 113, 1)",
      "zorg_whatsapp_stap()" in _zr and _zr.index("zorg_afspraken_zetten(") < _zr.index("zorg_whatsapp_stap()"))
check("de meldstap leest even ver als de zorgroute zet (een jaar en meer; hertest PR 113, 2)", W.ZORG_WHATSAPP_DAGEN >= 365)
_o9 = (W.afspraken, W.archief_afspraken, W.agenda._toegang)
W.agenda._toegang = lambda: "tok"
_ver = item("ver", "!! [PR] Tandarts - Praktijk V", "2027-05-04T09:00:00+02:00", "2027-05-04T09:30:00+02:00",
            merk={W.ZORGMERK: "zv"})
_vensters = []
W.afspraken = lambda van=-1, tot=8, alleen_lezen=False: _vensters.append((van, tot)) or [_ver]
W.archief_afspraken = lambda van=-1, tot=8, alleen_lezen=False: []
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw9-")) / "agenda-whatsapp.json")
AW.basislijn([])
try:
    _rz, _nz = W.zorg_whatsapp_stap()
finally:
    W.afspraken, W.archief_afspraken, W.agenda._toegang = _o9
check("een zorgblok over zes maanden krijgt zijn melding nu", any(k.startswith("zorg:ver:") for k in AW._lees()["meldingen"])
      and _vensters and _vensters[0][1] >= 365, str((_rz, _nz, _vensters)))

# --- review met meerdere agents (PR 113) -----------------------------------------------------------------------
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw4-")) / "agenda-whatsapp.json")
# een onzekere of mislukte melding blijft een nood, elke ronde, tot ze nagekeken is
AW.klaarzetten("r:onz", "x")
with AW._bewerk() as _d:
    _d["meldingen"]["r:onz"]["status"] = "onzeker"
_n1, _n2 = [], []
AW.versturen(lambda t, kop: "whatsapp", _n1, False, (Plafond,))
AW.versturen(lambda t, kop: "whatsapp", _n2, True, (Plafond,))
AW.nagekeken("r:onz")
_n3 = []
AW.versturen(lambda t, kop: "whatsapp", _n3, False, (Plafond,))
check("een onzekere melding geeft elke ronde dezelfde nood (ook in de stille uren) tot ze nagekeken is",
      _n1 and _n2 and _n1[0]["tekst"] == _n2[0]["tekst"] and not _n3, str((_n1, _n2, _n3)))
# een storing voor het versturen telt niet als weigering van Meta
AW.klaarzetten("r:db", "x")
for _ in range(4):
    AW.versturen(lambda t, kop: (_ for _ in ()).throw(RuntimeError("psql: could not connect to server")), [], False, (Plafond,))
check("een databank- of dockerstoring voor het versturen laat de melding klaar staan, zonder poging te tellen",
      AW._lees()["meldingen"]["r:db"]["status"] == "klaar" and not AW._lees()["meldingen"]["r:db"].get("pogingen"))
import socket  # noqa: E402
import urllib.error  # noqa: E402
AW.versturen(lambda t, kop: (_ for _ in ()).throw(urllib.error.URLError(socket.gaierror("dns"))), [], False, (Plafond,))
check("een DNS-fout: zeker niet vertrokken, de melding blijft klaar", AW._lees()["meldingen"]["r:db"]["status"] == "klaar")
AW.versturen(lambda t, kop: (_ for _ in ()).throw(urllib.error.URLError(TimeoutError())), [], False, (Plafond,))
check("een time-out: misschien vertrokken, dus onzeker", AW._lees()["meldingen"]["r:db"]["status"] == "onzeker")
_wa = (HIER / "koppelingen" / "whatsapp.py").read_text(encoding="utf-8")
check("whatsapp.stuur maakt van een onleesbaar gesprek 'nu niet beschikbaar'",
      "raise NietBeschikbaar(f\"gesprek niet te lezen" in _wa)
# een oude code in een gewoon bericht gaat naar het bord
AW.klaarzetten("zorg:oud:1", "x", {"id": "o", "start": ecg["start"], "einde": ecg["einde"]})
_co = AW._lees()["meldingen"]["zorg:oud:1"]["code"]
AW.antwoord_herkennen(f"{_co} ja")
AW.verwerkt("zorg:oud:1", "ja")
check("een bericht dat met een oude, beantwoorde code begint, gaat naar het bord",
      AW.antwoord_herkennen(f"{_co} formaat voor de BA-set graag") is None)
check("een exact 'Ax ja' op een beantwoorde vraag krijgt 'al beantwoord'", "al beantwoord" in (AW.antwoord_herkennen(f"{_co} ja") or ""))
AW.verwerkt("zorg:oud:1", "mislukt")
check("na een mislukte verwerking mag Mehdi opnieuw antwoorden", "ontvangen" in (AW.antwoord_herkennen(f"{_co} ja") or "")
      and AW.open_antwoorden())

# een tijdelijke fout bij het vastleggen: opnieuw proberen; een gemiste teruglezing is geen ja
_st = {"summary": "!! ?? [PR] Huisarts - Praktijk Verpleegkundigen"}
_o5 = (W._patch, W._lees_event, W._prive_item_lezen)
W._prive_item_lezen = lambda eid, tok: dict(ecg, id="o", titel=_st["summary"])
W._patch = lambda a, body, tok, **kw: _st.update(body)
W._lees_event = lambda kal, eid, tok: None                  # de teruglezing mislukt
try:
    _rr1 = W.whatsapp_antwoorden_verwerken("tok")
    _open1 = bool(AW.open_antwoorden())
    W._lees_event = lambda kal, eid, tok: dict(_st)
    _rr2 = W.whatsapp_antwoorden_verwerken("tok")
finally:
    W._patch, W._lees_event, W._prive_item_lezen = _o5
check("lukt de teruglezing niet, dan geen bevestiging en de volgende ronde opnieuw; daarna wel vastgelegd",
      _open1 and "volgende ronde opnieuw" in " ".join(_rr1) and any("vastgelegd en teruggelezen" in r for r in _rr2)
      and not AW.open_antwoorden(), str((_rr1, _rr2)))

# _te_valideren wist nooit de omschrijving als ze niet te lezen is; een blijvende weigering geeft toch een melding
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw5-")) / "agenda-whatsapp.json")
AW.basislijn([])
_p6 = []
_o6 = (W._patch, W._lees_event)
W._patch = lambda a, body, tok, **kw: _p6.append(body)
W._lees_event = lambda kal, eid, tok: None
try:
    _r6 = W.zorg_whatsapp([dict(ecg, titel="!! [PR] Huisarts - Praktijk Verpleegkundigen"), antwerk], "tok")
finally:
    W._patch, W._lees_event = _o6
check("is de omschrijving niet te lezen, dan schrijf ik niets (geen gewiste praktijkgegevens) en probeer ik later",
      not _p6 and any("volgende ronde opnieuw" in r for r in _r6) and not any(k.startswith("zorg:ecg:") for k in AW._lees()["meldingen"]))
_o7 = W._patch
W._patch = lambda a, body, tok, **kw: (_ for _ in ()).throw(W.TitelVoorstel("door een ander gemaakt"))
_o7b = W._lees_event
W._lees_event = lambda kal, eid, tok: {"summary": ecg["titel"], "description": "praktijk"}
try:
    _r7 = W.zorg_whatsapp([dict(ecg, titel="!! [PR] Huisarts - Praktijk Verpleegkundigen"), antwerk], "tok")
finally:
    W._patch, W._lees_event = _o7, _o7b
_m7 = next((v for k, v in AW._lees()["meldingen"].items() if k.startswith("zorg:ecg:")), {})
check("mag ik het blok niet op ?? zetten (niet door mij gemaakt), dan toch de melding, zonder code en met uitleg",
      _m7.get("status") == "klaar" and _m7.get("vraag") is None and "niet op ?? zetten" in _m7.get("tekst", ""), str(_m7))

# een blok dat naar een vrij uur verschoof, verliest mijn '??'
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw6-")) / "agenda-whatsapp.json")
AW.basislijn([])
AW.klaarzetten(f"zorg:ecg:{ecg['start']}:{ecg['einde']}", "x", {"id": "ecg", "start": ecg["start"], "einde": ecg["einde"]})
_vrij_uur = dict(ecg, titel="!! ?? [PR] Huisarts - Praktijk Verpleegkundigen", start=f"{d2}T16:00:00+01:00", einde=f"{d2}T16:15:00+01:00")
_p8, _ev8 = [], {"summary": _vrij_uur["titel"], "description": "Te valideren (27-10-2026): botst met ANTWERK.\n\npraktijk"}
_o8 = (W._patch, W._lees_event)
W._patch = lambda a, body, tok, **kw: _p8.append(body) or _ev8.update(body)
W._lees_event = lambda kal, eid, tok: dict(_ev8)
try:
    W.zorg_whatsapp([_vrij_uur, antwerk], "tok")
finally:
    W._patch, W._lees_event = _o8
check("verschuift een blok op ?? naar een vrij uur, dan gaan ?? en de regel 'Te valideren' weg (de praktijkgegevens blijven)",
      _p8 and "??" not in _p8[0]["summary"] and _p8[0]["description"] == "praktijk", str(_p8))

# de schaduw van dezelfde zorgafspraak op werk is geen botsing
_sch = item("sch", "Mehdi: kine Praktijk X", ecg["start"], ecg["einde"], kal=W.WERKAGENDA)
_sch["_zorg_schaduw"] = True
check("de schaduw van dezelfde zorgafspraak op de werkagenda telt niet als botsing", not W.botst_met(ecg, [ecg, _sch]))

# --- Codex-hertest 2 (PR 113) ---------------------------------------------------------------------------------
# een mislukte eerste meldstap: de volgende ronde ziet het blok van toen nog als nieuw
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw10-")) / "agenda-whatsapp.json")
_t0 = W.nu_lokaal() - timedelta(hours=2)
AW.sinds_zetten(_t0)                                         # de eerste ronde begon twee uur geleden
AW.sinds_zetten(W.nu_lokaal())                               # een latere ronde verandert dat niet
_toen = dict(item("toen", "!! [PR] Kine - Praktijk T", f"{d2}T13:00:00+01:00", f"{d2}T13:30:00+01:00", merk={W.ZORGMERK: "zt"}),
             _gemaakt=(_t0 + timedelta(minutes=1)).astimezone(W.ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S.000Z"))
W.zorg_whatsapp([_toen], "tok", sinds=None)
check("een blok uit de eerste ronde waarvan de meldstap mislukte, krijgt de volgende ronde toch zijn melding",
      AW.sinds() == _t0.isoformat() and any(k.startswith("zorg:toen:") and v.get("status") == "klaar"
                                            for k, v in AW._lees()["meldingen"].items()), str(AW._lees()))
# een blok verder dan het venster dat deze ronde gezet werd: die dag wordt gelezen en gemeld
_o11 = (W.afspraken, W.archief_afspraken, W.agenda._toegang, list(W.ZORG_GEZET))
_heel_ver = item("hv", "!! [PR] Tandarts - Praktijk H", "2028-03-07T09:00:00+01:00", "2028-03-07T09:30:00+01:00",
                 merk={W.ZORGMERK: "zh"})
_lezingen = []
W.afspraken = lambda van=-1, tot=8, alleen_lezen=False: _lezingen.append((van, tot)) or ([_heel_ver] if van > 400 else [])
W.archief_afspraken = lambda van=-1, tot=8, alleen_lezen=False: []
W.agenda._toegang = lambda: "tok"
W.ZORG_GEZET[:] = [("2028-03-07", "hv")]
try:
    _r11, _n11 = W.zorg_whatsapp_stap()
finally:
    W.afspraken, W.archief_afspraken, W.agenda._toegang = _o11[:3]
    W.ZORG_GEZET[:] = _o11[3]
check("een zorgblok dat deze ronde ver voorbij het venster gezet werd, wordt meteen gemeld (die dag gelezen)",
      any(k.startswith("zorg:hv:") for k in AW._lees()["meldingen"]) and any(v > 400 for v, _ in _lezingen),
      str((_r11, _n11, _lezingen)))
_hoofd2 = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
check("de eerste ronde legt haar begin vast voor de zorgroute iets zet (main en zorgronde)",
      "WACHTRIJ_KLAAR = _wachtrij_begin()" in _hoofd2.split("def main():")[1][:400]
      and _hoofd2.split("def zorgronde():")[1][:600].count("AW.sinds_zetten(RONDE_START)") == 1)

# --- Codex-hertest 3 (PR 113) ---------------------------------------------------------------------------------
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw12-")) / "agenda-whatsapp.json")
AW.basislijn([])
_A = dict(ecg, titel="!! ?? [PR] Huisarts - Praktijk Verpleegkundigen")
_B = dict(_A, start=f"{d0}T15:00:00+01:00", einde=f"{d0}T15:15:00+01:00")
_o12 = (W._patch, W._lees_event)
W._patch = lambda a, body, tok, **kw: None
W._lees_event = lambda kal, eid, tok: {"summary": _A["titel"], "description": ""}
try:
    W.zorg_whatsapp([_A, antwerk], "tok")
    _code_A = next(v["code"] for k, v in AW._lees()["meldingen"].items() if k.startswith("zorg:ecg:"))
    W.zorg_whatsapp([_B, antwerk], "tok")
    W.zorg_whatsapp([_A, antwerk], "tok")
finally:
    W._patch, W._lees_event = _o12
_ecgs = [k for k in AW._lees()["meldingen"] if k.startswith("zorg:ecg:")]
check("verschuift een afspraak van A naar B en terug naar A, dan krijgt elke verschuiving een melding (hertest 3)",
      len(_ecgs) == 3, str(_ecgs))
check("en een code over een vorig uur geldt niet meer", "geldt niet meer" in (AW.antwoord_herkennen(f"{_code_A} ja") or ""))
# de verre dagen blijven bewaard tot hun melding klaarstaat
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw13-")) / "agenda-whatsapp.json")
_o13 = (W.afspraken, W.archief_afspraken, W.agenda._toegang, list(W.ZORG_GEZET))
W.afspraken = lambda van=-1, tot=8, alleen_lezen=False: [{"fout": True, "kalender": "x"}]     # de lezing mislukt
W.archief_afspraken = lambda van=-1, tot=8, alleen_lezen=False: []
W.agenda._toegang = lambda: "tok"
W.ZORG_GEZET[:] = [("2028-03-07", "x1")]
try:
    W.zorg_whatsapp_stap()
    W.ZORG_GEZET[:] = []                        # een nieuw proces: het geheugen is leeg
    _bewaard = AW.verre_dagen()
finally:
    W.afspraken, W.archief_afspraken, W.agenda._toegang = _o13[:3]
    W.ZORG_GEZET[:] = _o13[3]
check("mislukt de meldstap, dan blijft een verre dag bewaard voor de volgende ronde (hertest 3)", _bewaard == {"2028-03-07": ["x1"]},
      str(_bewaard))
_st = (HIER / "agenda_wacht.py").read_text(encoding="utf-8").split("def zorg_whatsapp_stap():")[1][:2600]
check("de meldstap markeert de zorgschaduwen op haar eigen lijst en houdt die van de ronde",
      "markeer_zorgschaduwen(items)" in _st and "ZORG_SCHADUW_IDS.update(bewaard)" in _st)

# --- Codex-hertest 4 (PR 113) ---------------------------------------------------------------------------------
_h4 = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
_z4 = _h4[_h4.index("zst = zorg_afspraken_zetten(mres, rit_items"):][:10]
_voor = _h4[:_h4.index("zst = zorg_afspraken_zetten(mres, rit_items")][-400:]
check("zonder bewaard begin van de ronde zet de zorgroute niets (hertest 4, punt 1)",
      "if not WACHTRIJ_KLAAR:" in _voor and "raise _Onvolledig" in _voor
      and "return 1" in _h4.split("def zorgronde():")[1][:700])
_stap4 = _h4.split("def zorg_whatsapp_stap():")[1][:2500]
check("de verre dagen worden bewaard voor er gelezen wordt (punt 2)",
      _stap4.index("AW.verre_dagen(") < _stap4.index("afspraken(0, ZORG_WHATSAPP_DAGEN)"))
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw14-")) / "agenda-whatsapp.json")
_o14 = (W.afspraken, W.archief_afspraken, W.agenda._toegang, list(W.ZORG_GEZET))
W.afspraken = lambda van=-1, tot=8, alleen_lezen=False: []          # een lege lezing: het blok is (nog) niet te zien
W.archief_afspraken = lambda van=-1, tot=8, alleen_lezen=False: []
W.agenda._toegang = lambda: "tok"
W.ZORG_GEZET[:] = [("2028-03-07", "x2")]
try:
    W.zorg_whatsapp_stap()
finally:
    W.afspraken, W.archief_afspraken, W.agenda._toegang = _o14[:3]
    W.ZORG_GEZET[:] = _o14[3]
check("na een lege lezing blijft de verre dag staan tot haar blok gemeld is (punt 2)", AW.verre_dagen() == {"2028-03-07": ["x2"]})
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw15-")) / "agenda-whatsapp.json")
AW.versie_melden("blk", "s1", "e1", "oud uur {code}", {"id": "blk", "start": "s1", "einde": "e1"})
_k1 = next(iter(AW._lees()["meldingen"]))
with AW._bewerk() as _d:
    _d["meldingen"][_k1]["antwoord"] = "vervalt"
    _d["meldingen"][_k1]["verwerkt"] = {"uitkomst": "mislukt"}
AW.versie_melden("blk", "s2", "e2", "nieuw uur {code}", None)
_m15 = AW._lees()["meldingen"][_k1]
check("een nog niet verstuurd bericht over het oude uur gaat niet meer weg (punt 3)", _m15["status"] == "vervangen")
check("ook een mislukte oude vraag geldt niet meer na een verschuiving (punt 4)",
      _m15["verwerkt"]["uitkomst"] == "vervangen" and not AW.open_antwoorden()
      and "ontvangen" not in (AW.antwoord_herkennen(f"{_m15['code']} vervalt") or ""))

# --- Codex-hertest 5 (PR 113): een zorgafspraak voorbij dag 120 krijgt geen tweede blok -------------------------
import mail_afspraken as _MA  # noqa: E402
_ins16, _gevonden = [], {}
_o16 = (W._insert, W._zorg_teruglezen, W._zorg_blok_met_merk, _MA._zorg_json, _MA.zorgprofielen, W._prive_item_lezen)
W._insert = lambda kal, body, tok, toch=False: _ins16.append(body) or _gevonden.__setitem__("s16", "nieuw1") or {"id": "nieuw1"}
W._zorg_teruglezen = lambda kal, eid, body, tok, gelezen=None: ""
W._zorg_blok_met_merk = lambda sleutel, tok: _gevonden.get(sleutel, "")
_MA._zorg_json = lambda a: a["zorg"]
_MA.zorgprofielen = lambda: [{"id": "p", "soort": "tandarts"}]
_ver_start = (W.nu_lokaal() + timedelta(days=200)).replace(hour=9, minute=0, second=0, microsecond=0)
W._prive_item_lezen = lambda eid, tok: {"id": eid, "start": _ver_start.isoformat(),
                                        "einde": (_ver_start + timedelta(minutes=30)).isoformat()}


def _mail16():
    return [{"soort": "zorg", "status": "ontbreekt", "sleutel": "s16", "titel": "Tandarts Proef", "start": _ver_start.isoformat(),
             "einde": (_ver_start + timedelta(minutes=30)).isoformat(), "geannuleerd": 0, "ics_uid": "", "locatie": "",
             "bron_ontvangen": "2026-10-27T10:00:00+01:00", "bron_mailbox": "proef@voorbeeld.be", "bron_onderwerp": "Afspraak",
             "bron_afzender": "info@tandarts-voorbeeld.test", "bron_message_id": "<zorg@proef>",
             "zorg": {"praktijk": "p", "gebeurtenis": "bevestiging", "mehdi": True, "behandelaar": "Proef"}}]
try:
    _rz1 = W.zorg_afspraken_zetten(_mail16(), [], "tok")
    _rz2 = W.zorg_afspraken_zetten(_mail16(), [], "tok")       # de volgende ronde: weer 'ontbreekt' (buiten 120 dagen)
except Exception as _e:  # noqa: BLE001
    _rz1 = _rz2 = {"prive": [repr(_e)]}
finally:
    W._insert, W._zorg_teruglezen, W._zorg_blok_met_merk, _MA._zorg_json, _MA.zorgprofielen, W._prive_item_lezen = _o16
check("een zorgafspraak voorbij dag 120: de tweede ronde koppelt het bestaande blok, geen tweede blok (hertest 5)",
      len(_ins16) == 1 and any("stond er al" in r for r in _rz2.get("prive", [])), str((len(_ins16), _rz1.get("prive"), _rz2.get("prive"))))

# --- Codex-hertest 6 (PR 113) ---------------------------------------------------------------------------------
# een blok voorbij dag 120 op een ander uur: het verschuift mee
_pat17 = []
_o17 = (W._insert, W._zorg_blok_met_merk, W._prive_item_lezen, W._patch, W._zorg_nalezen, _MA._zorg_json, _MA.zorgprofielen,
        list(W.ZORG_GEZET), W._lees_event)
W._lees_event = lambda kal, eid, tok: {"description": "praktijk, volledig"}
W._insert = lambda *a, **k: (_ for _ in ()).throw(AssertionError("geen nieuw blok"))
W._zorg_blok_met_merk = lambda sleutel, tok: "bestaand17"
W._prive_item_lezen = lambda eid, tok: {"id": eid, "kalender": W.PRIVE_AGENDA, "titel": "!! [PR] Tandarts - Proef",
                                        "start": (_ver_start - timedelta(days=7)).isoformat(),
                                        "einde": (_ver_start - timedelta(days=7) + timedelta(minutes=30)).isoformat(),
                                        "omschrijving": "praktijk", "deelnemers": [], "maker": W.WERKAGENDA, "_merk": {}}
W._patch = lambda x, body, tok, **kw: _pat17.append(body)
W._zorg_nalezen = lambda *a, **k: ""
_MA._zorg_json = lambda a: a["zorg"]
_MA.zorgprofielen = lambda: [{"id": "p", "soort": "tandarts"}]
W.ZORG_GEZET[:] = []
try:
    _rz17 = W.zorg_afspraken_zetten(_mail16(), [], "tok")
    _gezet17 = list(W.ZORG_GEZET)
finally:
    (W._insert, W._zorg_blok_met_merk, W._prive_item_lezen, W._patch, W._zorg_nalezen, _MA._zorg_json, _MA.zorgprofielen) = _o17[:7]
    W.ZORG_GEZET[:] = _o17[7]
    W._lees_event = _o17[8]
check("een zorgblok voorbij dag 120 op een ander uur dan de mail: niet zelf verzet (misschien met de hand gecorrigeerd), "
      "maar een open punt (hertest 10)",
      not _pat17 and not _gezet17 and any("open punt, niet verzet" in r for r in _rz17["prive"]), str((_pat17[:1], _gezet17, _rz17["prive"])))
_afw = [v for k, v in AW._lees()["meldingen"].items() if k.startswith("afwijkend:")]
check("en dat open punt gaat meteen als WhatsApp naar Mehdi, een keer, zonder adres (hertest 11)",
      len(_afw) == 1 and "Welk uur klopt?" in _afw[0]["tekst"] and "Bondgenoten" not in _afw[0]["tekst"], str(_afw))
# een verre dag blijft tot elk nieuw blok gemeld is, ook als een ander blok van die dag al gemeld was
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw17-")) / "agenda-whatsapp.json")
AW.basislijn([("oud18", "2028-03-07T08:00:00+01:00", "2028-03-07T08:30:00+01:00")])
_oud18 = item("oud18", "!! [PR] Kine - Q", "2028-03-07T08:00:00+01:00", "2028-03-07T08:30:00+01:00", merk={W.ZORGMERK: "q"})
_o18 = (W.afspraken, W.archief_afspraken, W.agenda._toegang, list(W.ZORG_GEZET))
W.afspraken = lambda van=-1, tot=8, alleen_lezen=False: [_oud18] if van > 400 else []   # het nieuwe blok is nog niet te zien
W.archief_afspraken = lambda van=-1, tot=8, alleen_lezen=False: []
W.agenda._toegang = lambda: "tok"
W.ZORG_GEZET[:] = [("2028-03-07", "nieuw18")]
try:
    W.zorg_whatsapp_stap()
finally:
    W.afspraken, W.archief_afspraken, W.agenda._toegang = _o18[:3]
    W.ZORG_GEZET[:] = _o18[3]
check("een verre dag blijft bewaard zolang het nieuwe blok niet gevonden en gemeld is (hertest 6)",
      AW.verre_dagen() == {"2028-03-07": ["nieuw18"]}, str(AW.verre_dagen()))

# --- Codex-hertest 7 (PR 113) ---------------------------------------------------------------------------------
_o19 = (W._zorg_blok_met_merk, W._prive_item_lezen, _MA._zorg_json, _MA.zorgprofielen, list(W.ZORG_GEZET), W._insert)
W._zorg_blok_met_merk = lambda sleutel, tok: "al19"
W._prive_item_lezen = lambda eid, tok: {"id": eid, "start": _ver_start.isoformat(),
                                        "einde": (_ver_start + timedelta(minutes=30)).isoformat()}
W._insert = lambda *a, **k: (_ for _ in ()).throw(AssertionError("geen nieuw blok"))
_MA._zorg_json = lambda a: a["zorg"]
_MA.zorgprofielen = lambda: [{"id": "p", "soort": "tandarts"}]
W.ZORG_GEZET[:] = []
try:
    W.zorg_afspraken_zetten(_mail16(), [], "tok")
    _gez19 = list(W.ZORG_GEZET)
finally:
    W._zorg_blok_met_merk, W._prive_item_lezen, _MA._zorg_json, _MA.zorgprofielen = _o19[:4]
    W.ZORG_GEZET[:] = _o19[4]
    W._insert = _o19[5]
check("een blok dat na een herstart via zijn merk gekoppeld wordt, meldt zich voor de meldstap (hertest 7, punt 1)",
      _gez19 == [(_ver_start.date().isoformat(), "al19")], str(_gez19))
check("een vervallen zorgblok dat de praktijk verzet, wordt weer een gewone afspraak (vervalt weg, Bezet; punt 2)",
      W._niet_meer_vervallen({"titel": "vervalt !! [PR] Tandarts - Proef"}) == {"summary": "!! [PR] Tandarts - Proef",
                                                                                "transparency": "opaque"}
      and W._niet_meer_vervallen({"titel": "!! [PR] Tandarts - Proef"}) == {})
_h7 = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
check("en beide verschuifroutes van de zorgstap gebruiken dat", _h7.count("**_niet_meer_vervallen(x)}, tok)") == 2)
check("ook 'vervalt:' gaat weg, dezelfde vormen als de herkenning (hertest 10)",
      W._niet_meer_vervallen({"titel": "vervalt: !! [PR] Kine - X"})["summary"] == "!! [PR] Kine - X"
      and W._niet_meer_vervallen({"titel": "!! vervalt - [PR] Kine - X"})["summary"] == "!! [PR] Kine - X")
_mv10 = _h7[_h7.index("volledig = _lees_event(kal, eid, tok)"):][:900]
check("de verschuiving wordt voor de meldstap onthouden voor ze geschreven en teruggelezen wordt (hertest 10)",
      _mv10.index("_zorg_gezet(") < _mv10.index("_patch(x,"))

# --- Codex-hertest 8 (PR 113) ---------------------------------------------------------------------------------
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw20-")) / "agenda-whatsapp.json")
AW.sinds_zetten(W.nu_lokaal())
_mv = dict(item("mv20", "!! [PR] Kine - Praktijk M", f"{d2}T17:00:00+01:00", f"{d2}T17:30:00+01:00", merk={W.ZORGMERK: "m"}),
           _gemaakt="2026-01-01T00:00:00.000Z")          # een oud blok, deze ronde verschoven
W._zorg_gezet(_mv["start"][:10], "mv20")
W.ZORG_GEZET[:] = []
W.zorg_whatsapp([_mv], "tok")
check("eerste ronde: een oud blok dat deze ronde verschoven werd, krijgt toch zijn melding (hertest 8, punt 1)",
      any(k.startswith("zorg:mv20:") for k in AW._lees()["meldingen"]) and not AW.eerste_ids(), str(AW._lees()))
check("'vervalt' gaat weg in elke herkende vorm (punt 3)",
      W._niet_meer_vervallen({"titel": "!! vervalt [PR] Kine - X"})["summary"] == "!! [PR] Kine - X"
      and W._niet_meer_vervallen({"titel": "VR vervalt !! [PR] Kine - X"})["summary"] == "VR !! [PR] Kine - X"
      and W._niet_meer_vervallen({"titel": "VR !! vervalt [PR] Kine - X"})["summary"] == "VR !! [PR] Kine - X")

# --- Codex-hertest 11 (PR 113): de verre dag gaat samen met het id meteen in de wachtrij ---------------------------
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw21-")) / "agenda-whatsapp.json")
W._zorg_gezet("2028-06-01", "ver21")
W.ZORG_GEZET[:] = []
check("een blok voorbij het venster wordt bij het zetten meteen met dag en id bewaard (hertest 11)",
      AW.verre_dagen() == {"2028-06-01": ["ver21"]}, str(AW.verre_dagen()))

# --- Codex-hertest 12 (PR 113): een door de mail bevestigde verschuiving voorbij dag 120 verzet het blok wel -------
_oud_uur = (_ver_start - timedelta(days=7))
_pat22 = []
_o22 = (W._insert, W._zorg_blok_met_merk, W._prive_item_lezen, W._patch, W._zorg_nalezen, _MA._zorg_json, _MA.zorgprofielen,
        list(W.ZORG_GEZET), W._lees_event)
W._insert = lambda *a, **k: (_ for _ in ()).throw(AssertionError("geen nieuw blok"))
W._zorg_blok_met_merk = lambda sleutel, tok: "b22"
W._prive_item_lezen = lambda eid, tok: {"id": eid, "kalender": W.PRIVE_AGENDA, "titel": "!! [PR] Tandarts - Proef",
                                        "start": _oud_uur.isoformat(), "einde": (_oud_uur + timedelta(minutes=30)).isoformat(),
                                        "hele_dag": False, "omschrijving": "", "deelnemers": [], "maker": W.WERKAGENDA, "_merk": {}}
W._lees_event = lambda kal, eid, tok: {"description": "praktijk"}
W._patch = lambda x, body, tok, **kw: _pat22.append(body)
W._zorg_nalezen = lambda *a, **k: ""
_MA._zorg_json = lambda a: a["zorg"]
_MA.zorgprofielen = lambda: [{"id": "p", "soort": "tandarts"}]
W.ZORG_GEZET[:] = []
try:
    _m22 = _mail16()
    _m22[0]["zorg"] = dict(_m22[0]["zorg"], historie=[{"van": _oud_uur.isoformat(), "naar": _ver_start.isoformat(), "bron": "mail 2"}])
    _rz22 = W.zorg_afspraken_zetten(_m22, [], "tok")
    _rz22b = W.zorg_afspraken_zetten(_mail16(), [], "tok")       # zonder historie: open punt
finally:
    (W._insert, W._zorg_blok_met_merk, W._prive_item_lezen, W._patch, W._zorg_nalezen, _MA._zorg_json, _MA.zorgprofielen) = _o22[:7]
    W.ZORG_GEZET[:] = _o22[7]
    W._lees_event = _o22[8]
check("bevestigt de mailhistorie de verschuiving voorbij dag 120, dan verzet het blok mee, teruggelezen (hertest 12)",
      _rz22["verzet"] == 1 and len(_pat22) == 1 and _pat22[0]["start"]["dateTime"] == _ver_start.isoformat()
      and _pat22[0]["description"].startswith("praktijk"), str((_rz22["prive"], _pat22)))
check("zonder die bevestiging blijft het een open punt, niets verzet", _rz22b["open"] == 1 and len(_pat22) == 1, str(_rz22b["prive"]))

# --- Codex-hertest 13 (PR 113) --------------------------------------------------------------------------------
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw23-")) / "agenda-whatsapp.json")
W._zorg_gezet((_ver_start + timedelta(days=1)).date().isoformat(), "gekoppeld23", nieuw=False)
W.ZORG_GEZET[:] = []
check("een blok dat alleen gekoppeld wordt, telt in de eerste ronde niet als nieuw gezet (hertest 13, punt 1)",
      "gekoppeld23" not in AW.eerste_ids())
_ins24 = []
_o24 = (W._insert, AW.gezet_onthouden, _MA._zorg_json, _MA.zorgprofielen, W._zorg_blok_met_merk, list(W.ZORG_GEZET))
W._insert = lambda kal, body, tok, toch=False: _ins24.append(body) or {"id": "nee"}
AW.gezet_onthouden = lambda dag, ident: (_ for _ in ()).throw(OSError("wachtrij niet schrijfbaar"))
_MA._zorg_json = lambda a: a["zorg"]
_MA.zorgprofielen = lambda: [{"id": "p", "soort": "tandarts"}]
W._zorg_blok_met_merk = lambda sleutel, tok: ""
try:
    _r24 = W.zorg_afspraken_zetten(_mail16(), [], "tok")
finally:
    W._insert, AW.gezet_onthouden, _MA._zorg_json, _MA.zorgprofielen, W._zorg_blok_met_merk = _o24[:5]
    W.ZORG_GEZET[:] = _o24[5]
check("lukt het vastleggen in de wachtrij niet, dan zet de zorgroute het blok niet (hertest 13, punt 2)",
      not _ins24 and any("niet gezet" in r for r in _r24["prive"]), str((_ins24, _r24["prive"])))
AW.WACHTRIJ = str(Path(tempfile.mkdtemp(prefix="aw25-")) / "agenda-whatsapp.json")
AW.sinds_zetten(W.nu_lokaal())
W._zorg_gezet(d2, "zorg|nieuw-sleutel")
W.ZORG_GEZET[:] = []
_nb25 = dict(item("nb25", "!! [PR] Kine - Praktijk N", f"{d2}T18:00:00+01:00", f"{d2}T18:30:00+01:00",
                  merk={W.ZORGMERK: "zorg|nieuw-sleutel"}), _gemaakt="2026-01-01T00:00:00.000Z")
W.zorg_whatsapp([_nb25], "tok")
check("een nieuw blok, vooraf vastgelegd op zijn zorgsleutel, krijgt in de eerste ronde zijn melding",
      any(k.startswith("zorg:nb25:") for k in AW._lees()["meldingen"]), str(AW._lees()))

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

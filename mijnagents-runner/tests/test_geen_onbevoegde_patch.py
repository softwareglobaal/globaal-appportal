"""H1-1, driehoeksoverleg C2, 17-10-2026: geen titel-PATCH zonder bewezen recht.

Gewoon script voor CI. Synthetische afspraken en een nagebootste Google API; AGENDA_WACHT_BRON
kan naar een kopie van de oude bron wijzen voor de verplichte tegenproef.
"""
import ast
import importlib.util
import io
import json
import os
os.environ.setdefault("AGENDA_WHATSAPP_WACHTRIJ", os.path.join(__import__("tempfile").mkdtemp(prefix="aw-test-"), "agenda-whatsapp.json"))  # nooit de echte wachtrij
import re
import sys
import time
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ["TZ"] = "UTC"
time.tzset()
os.environ.setdefault("BELLEN_UIT", "1")
HIER = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(HIER), str(HIER / "koppelingen")]
BRON = Path(os.environ.get("AGENDA_WACHT_BRON") or HIER / "agenda_wacht.py")
spec = importlib.util.spec_from_file_location("agenda_wacht_h1_test", BRON)
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam}: {extra}")


class Verslag:
    def __init__(self):
        self.regels = []

    def log(self, onderwerp, stap, tekst, detail=""):
        self.regels.append((onderwerp, stap, tekst, detail))

    def voorstel(self):
        return any("VOORSTEL" in str(r) for r in self.regels)


class API:
    def __init__(self):
        self.patch = []
        self.reeks = {}
        self.get = 0

    def open(self, req, timeout=30):
        if req.get_method() == "PATCH":
            self.patch.append(json.loads(req.data))
            return io.BytesIO(b"{}")
        self.get += 1
        return io.BytesIO(json.dumps(self.reeks).encode())

    def titels(self):
        return [p["summary"] for p in self.patch if "summary" in p]


@contextmanager
def omgeving():
    api, verslag = API(), Verslag()
    with patch.object(W, "mag_schrijven", return_value=True), patch.object(W.agenda, "_toegang", return_value="nep"), \
            patch("urllib.request.urlopen", side_effect=api.open), patch.object(W, "ag", verslag):
        yield api, verslag


LATER = (W.nu_lokaal() + timedelta(days=4)).replace(hour=14, minute=0, second=0, microsecond=0)
mailmerk = "0123456789abcdef"  # sleutel_kort: eerste 16 hextekens van SHA-256
zorgmerk = "zorg|proef|2026-10-21T08:30:00+02:00"


def afspraak(titel="Mehdi: [HA-KB] Proef", **extra):
    return {"kalender": W.WERKAGENDA, "id": "nep-1", "titel": titel, "start": LATER.isoformat(),
            "einde": (LATER + timedelta(minutes=30)).isoformat(), "hele_dag": False,
            "locatie": "Proefstraat 1, 3000 Leuven", "omschrijving": "", "maker": W.WERKAGENDA,
            "deelnemers": [], "_agendagasten": [], "_kleur": "6", **extra}


def veilig(actie):
    try:
        return actie()
    except Exception as e:  # noqa: BLE001
        return e


# Drie onafhankelijke Calendly-signalen; projectnummers_zetten miste deze controle op HEAD.
for kenmerk, velden in (("account", {"kalender": "zoomafspraken@gmail.com"}),
                        ("maker", {"maker": "unabosdp@gmail.com"}),
                        ("link", {"omschrijving": "https://calendly.com/proef/annuleer"})):
    a = afspraak(**velden)
    with omgeving() as (api, verslag), patch.object(W, "projectnummer_zoeken", return_value=("2601", "nepbron")):
        resultaat = veilig(lambda: W.projectnummers_zetten([a]))
    regels = resultaat[1] if isinstance(resultaat, tuple) else []
    check(f"Calendly {kenmerk}: projectnummer blijft VOORSTEL, nul titel-PATCH",
          not api.titels() and (verslag.voorstel() or any("VOORSTEL" in r for r in regels)), str(resultaat))

# Tweede titelroute: de uitroep naar voren halen; de oude code deed hier wel een PATCH.
for kenmerk, velden in (("account", {"kalender": "zoomafspraken@gmail.com"}),
                        ("maker", {"maker": "unabosdp@gmail.com"}),
                        ("link", {"omschrijving": "https://calendly.com/proef/verzetten"})):
    a = afspraak("Mehdi: [HA-KB] 2601 - Proef !!", **velden)
    with omgeving() as (api, verslag):
        resultaat = veilig(lambda: W.uitroep_vooraan([a]))
    regels = resultaat[1] if isinstance(resultaat, tuple) else []
    check(f"Calendly {kenmerk}: uitroep blijft VOORSTEL, nul titel-PATCH",
          not api.titels() and (verslag.voorstel() or any("VOORSTEL" in r for r in regels)), str(resultaat))

# Derde route: de reeks krijgt haar maker en Calendly-link uit het echt gelezen hoofditem.
a = afspraak("Mehdi: [HARC-KB] 2601 - Proef", _reeks="nep-reeks", _terugkerend=True)
with omgeving() as (api, verslag):
    api.reeks = {"summary": a["titel"], "description": "https://calendly.com/proef/annuleer",
                 "creator": {"email": W.WERKAGENDA}, "attendees": []}
    resultaat = veilig(lambda: W.codes_reeksen([a]))
check("Calendly-link in hoofditem: reeks wordt voorstel, nul titel-PATCH",
      not api.titels() and verslag.voorstel(), str(resultaat))

a = afspraak("Mehdi: [HARC-KB] 2601 - Proef", _reeks="nep-reeks", _terugkerend=True)
with omgeving() as (api, verslag):
    api.reeks = {"summary": a["titel"], "description": "", "creator": {"email": W.WERKAGENDA}, "attendees": []}
    resultaat = veilig(lambda: W.codes_reeksen([a]))
check("eigen reeks met volledig bewijs: titel-PATCH slaagt", len(api.titels()) == 1, str(resultaat))

a.pop("deelnemers")
with omgeving() as (api, verslag):
    api.reeks = {"summary": a["titel"], "description": "", "creator": {"email": W.WERKAGENDA}, "attendees": []}
    resultaat = veilig(lambda: W.codes_reeksen([a]))
check("reeks met onvolledige instantie: VOORSTEL, nul titel-PATCH",
      not api.titels() and verslag.voorstel(), str(resultaat))

a = afspraak("Mehdi: [HARC-KB] 2601 - Proef", _reeks="nep-reeks", _terugkerend=True)
with omgeving() as (api, verslag):
    api.reeks = {"summary": a["titel"], "description": "", "creator": {"email": W.WERKAGENDA},
                 "attendees": [{"responseStatus": "accepted"}]}
    resultaat = veilig(lambda: W.codes_reeksen([a]))
check("reeks met gast zonder adres: VOORSTEL, nul titel-PATCH",
      not api.titels() and verslag.voorstel(), str(resultaat))

a = afspraak(deelnemers=["klant@buiten.test"])
with omgeving() as (api, verslag):
    resultaat = veilig(lambda: W._patch(a, {"summary": "Mehdi: [HA-KB] 2601 - Proef"}, "nep"))
check("externe gast: nul titel-PATCH en VOORSTEL", not api.titels() and verslag.voorstel(), str(resultaat))

with omgeving() as (api, verslag):
    kaal = {"kalender": W.WERKAGENDA, "id": "nep-reeks", "titel": "Mehdi: [HA-KB] Proef"}
    resultaat = veilig(lambda: W._patch(kaal, {"summary": "Mehdi: [HA-KB] 2601 - Proef"}, "nep"))
check("kaal reeks-dict: onbekende gasten blijven VOORSTEL, nul titel-PATCH",
      not api.titels() and verslag.voorstel(), str(resultaat))

with omgeving() as (api, verslag):
    a = afspraak(maker=None)
    resultaat = veilig(lambda: W._patch(a, {"summary": "Mehdi: [HA-KB] 2601 - Proef"}, "nep"))
check("onbekende maker is niet leeg: VOORSTEL, nul titel-PATCH",
      not api.titels() and verslag.voorstel(), str(resultaat))

gemengd = "Mehdi: [HA-KB] Proef [UB-PO]"
info = W.lees_titel(gemengd)
check("twee firma's: conflict met alle firma's, geen gekozen firma",
      info.get("firma_conflict") is True and set(info.get("firmas", [])) == {"HARC", "UNAB"} and not info["firma"], str(info))
with omgeving() as (api, verslag):
    a = afspraak(gemengd)
    resultaat = veilig(lambda: W._patch(a, {"summary": gemengd + " 2601"}, "nep"))
    kleur = veilig(lambda: W.kleuren_zetten([a]))
check("firmaconflict: nul titel-PATCH, kleur blijft staan, VOORSTEL",
      not api.patch and a["_kleur"] == "6" and verslag.voorstel(), f"{resultaat} {kleur}")

with omgeving() as (api, verslag):
    rit = afspraak("🚗 Reistijd: [HA-KB] Proef [UB-PO]", _kleur="6")
    kleur = veilig(lambda: W.kleuren_zetten([rit]))
check("ook een reistijdtitel met twee firma's behoudt zijn kleur", not api.patch and rit["_kleur"] == "6", str(kleur))

with omgeving() as (api, verslag):
    a = afspraak()
    resultaat = veilig(lambda: W._patch(a, {"summary": "Mehdi: [UB-PO] Proef"}, "nep"))
check("firmawissel: nul titel-PATCH en VOORSTEL", not api.titels() and verslag.voorstel(), str(resultaat))

with omgeving() as (api, verslag):
    a = afspraak()
    resultaat = veilig(lambda: W._patch(a, {"summary": "Mehdi: Proef"}, "nep"))
check("oude firma weghalen: nul titel-PATCH en VOORSTEL", not api.titels() and verslag.voorstel(), str(resultaat))

with omgeving() as (api, verslag):
    a = afspraak(kalender="zoomafspraken@gmail.com")
    resultaat = veilig(lambda: W._patch(a, {"summary": "Mehdi: [HA-KB] 2601 - Proef"}, "nep", toch=True))
check("toch voor dagmarkeringen omzeilt de titelgrendel niet", not api.titels() and verslag.voorstel(), str(resultaat))

with omgeving() as (api, verslag):
    a = afspraak()
    resultaat = veilig(lambda: W._patch(a, {"summary": "Mehdi: [HA-KB] 2601 - Proef"}, "nep"))
check("eigen afspraak met bewezen lege gasten: titel-PATCH slaagt", len(api.titels()) == 1 and resultaat is None,
      f"{resultaat} {api.patch}")

info = W.lees_titel("Mehdi: [HA-KB] en [HARC-IN] overleg")
check("twee schrijfwijzen van dezelfde firma blijven eenduidig", not info.get("firma_conflict") and info["firma"] == "HARC", str(info))


# H1-1b, driehoeksoverleg C3, 17-10-2026: de vier reparaties moeten op de eerste ronde falen.
un = W.lees_titel("Mehdi: [UN-PO] Proef")
check("A1: UN is geen firmacode", not un.get("firma") and "UN" not in W.AGENDACODE_NAAR_FIRMA, str(un))

with omgeving() as (api, verslag):
    rit = afspraak("🚗 Reistijd: [HA-KB] Oud", id="rit-proef", _merk={W.RITMERK: "rit-proef"})
    rit["omschrijving"] = "Reistijd voor: Proef; OSRM"
    nieuw = {"summary": "🚗 Reistijd: thuis → Proefstraat", "start": {"dateTime": LATER.isoformat()},
             "end": {"dateTime": (LATER + timedelta(minutes=40)).isoformat()}}
    resultaat = veilig(lambda: W._patch(rit, nieuw, "nep"))
check("A2: gemerkte rit krijgt titel en tijden", resultaat is None and len(api.patch) == 1
      and all(k in api.patch[0] for k in ("summary", "start", "end")), str(resultaat))

with omgeving() as (api, verslag):
    mail = afspraak("VR Agendawacht: [HA-KB] Mail", kalender=W.PRIVE_AGENDA,
                    omschrijving="https://calendly.com/proef", _merk={W.MAILMERK: mailmerk})
    resultaat = veilig(lambda: W._eigen_melding_opgelost(mail, mailmerk, "nep", LATER, "opgelost"))
check("A2: gemerkte mailmelding wordt opgelost ondanks Calendly-link", resultaat is True and
      len(api.titels()) == 1 and api.titels()[0].startswith("Opgelost:"), str(resultaat))

with omgeving() as (api, verslag):
    mail_met_gast = afspraak("VR Agendawacht: [HA-KB] Mail", kalender=W.PRIVE_AGENDA,
                            _merk={W.MAILMERK: "abcdef0123456789"}, deelnemers=["mehdi@voorbeeld.test"])
    resultaat = veilig(lambda: W._patch(mail_met_gast, {"summary": "Opgelost: Mail"}, "nep"))
check("A2: ook een eigen blok met externe gast krijgt geen titelwijziging", not api.titels() and verslag.voorstel(),
      str(resultaat))

with omgeving() as (api, verslag):
    zorg = afspraak("Mehdi: [HA-KB] Kine", kalender=W.PRIVE_AGENDA, _merk={W.ZORGMERK: zorgmerk})
    resultaat = veilig(lambda: W._patch(zorg, {"summary": "!! [PR] Kine - Proef"}, "nep"))
check("A8: geldig zorgmerk alleen geeft gewone privéafspraak geen titelrecht",
      not api.titels() and verslag.voorstel(),
      str(resultaat))

import mail_afspraken as MA  # noqa: E402
zorg_mail = {"soort": "zorg", "status": "gekoppeld", "google": W.WERKAGENDA + "|zorg-route",
             "start": LATER.isoformat(), "titel": "Kine - Proef", "sleutel": zorgmerk}
zorg_werk = afspraak("Mehdi: [HA-KB] Kine", id="zorg-route")
with omgeving() as (api, verslag), patch.object(MA, "zorgprofielen", return_value=[]), \
        patch.object(MA, "_zorg_json", return_value={}), patch.object(MA, "_ander_zorgitem", return_value=False), \
        patch.object(W, "_zorg_body", return_value={"summary": "!! [PR] Kine - Proef", "location": "",
                                                    "extendedProperties": {"private": {W.ZORGMERK: zorgmerk}}}), \
        patch.object(W, "_verplaats_naar") as verhuis, patch.object(W, "_zorg_nalezen", return_value=""):
    resultaat = veilig(lambda: W.zorg_afspraken_zetten([zorg_mail], [zorg_werk], "nep"))
check("A2: zorgroute verhuist ongemerkt werkblok en zet daarna de privétitel", isinstance(resultaat, dict)
      and resultaat["verhuisd"] == 1 and verhuis.call_count == 1 and len(api.titels()) == 1, str(resultaat))

# H1-1c, driehoeksoverleg C4: de routevlag is beperkt tot de verhuizing van werk naar privé.
zorg_na_verhuis = dict(zorg_werk, kalender=W.PRIVE_AGENDA, _titel_bronkalender=W.WERKAGENDA)
for vlag, gasten, calendly, toegestaan in ((False, [], "", False), (True, [], "", True),
                                          (True, ["gast@extern.test"], "", False),
                                          (True, [], "https://calendly.com/proef", False)):
    with omgeving() as (api, verslag):
        blok = dict(zorg_na_verhuis, deelnemers=gasten, omschrijving=calendly)
        resultaat = veilig(lambda: W._patch(blok, {"summary": "!! [PR] Kine - Proef"}, "nep",
                                          eigen_zorgverhuis=vlag))
    check(f"A6: zorgverhuis vlag={vlag}, gasten={bool(gasten)}, Calendly={bool(calendly)}",
          (api.titels() == ["!! [PR] Kine - Proef"] and resultaat is None) if toegestaan
          else (not api.titels() and verslag.voorstel()), str(resultaat))

for oud, nieuw in ((gemengd, "VR " + gemengd), ("VR " + gemengd, gemengd)):
    with omgeving() as (api, verslag):
        resultaat = veilig(lambda: W._patch(afspraak(oud), {"summary": nieuw}, "nep"))
    check("A2: alleen VR vooraan wijzigen bij firmaconflict", resultaat is None and api.titels() == [nieuw],
          f"{oud}: {resultaat}")

with omgeving() as (api, verslag):
    calendly_vraag = afspraak(gemengd, omschrijving="https://calendly.com/proef")
    resultaat = veilig(lambda: W._patch(calendly_vraag, {"summary": "VR " + gemengd}, "nep"))
check("A2: VR-route behoudt haar oude Calendly-gedrag", resultaat is None and len(api.titels()) == 1,
      str(resultaat))

with omgeving() as (api, verslag):
    gast_vraag = afspraak(gemengd, deelnemers=["gast@extern.test"])
    resultaat = veilig(lambda: W._patch(gast_vraag, {"summary": "VR " + gemengd}, "nep"))
check("A2: VR-vrijstelling geldt niet voor externe gasten", not api.titels() and verslag.voorstel(),
      str(resultaat))

with omgeving() as (api, verslag):
    nagebootst = afspraak("🚗 Reistijd: [HA-KB] Oud", omschrijving="Reistijd voor: Proef; OSRM")
    resultaat = veilig(lambda: W._patch(nagebootst, {"summary": "🚗 Reistijd: thuis → Proefstraat"}, "nep"))
check("A2: ritachtige titel zonder privaat merk geeft geen vrijstelling", not api.titels() and verslag.voorstel(),
      str(resultaat))

with omgeving() as (api, verslag):
    oude_rit = afspraak("🚗 Reistijd: [HA-KB] Oud", omschrijving="Reistijd voor: Proef; OSRM")
    resultaat = veilig(lambda: W._patch(oude_rit, {"summary": "🚗 Reistijd: thuis → Proefstraat"},
                                      "nep", eigen_rit=True))
check("A2: de bestaande ritroute mag een herkende oude OSRM-rit bijwerken", resultaat is None
      and len(api.titels()) == 1, str(resultaat))

with omgeving() as (api, verslag):
    a = afspraak(maker="")
    resultaat = veilig(lambda: W._patch(a, {"summary": "Mehdi: [HA-KB] 2601 - Proef"}, "nep"))
check("A3: lege maker geeft geen titelrecht", not api.titels() and verslag.voorstel(), str(resultaat))

with omgeving() as (api, verslag):
    a = afspraak(maker="vreemd@extern.test")
    resultaat = veilig(lambda: W._patch(a, {"summary": "Mehdi: [HA-KB] 2601 - Proef"}, "nep"))
check("A3: maker van buiten geeft geen titelrecht", not api.titels() and verslag.voorstel(), str(resultaat))

# H1-1c, driehoeksoverleg C4, 17-10-2026: alleen volledige eigen accounts geven titelrecht.
for maker in ("iemand.mehdi@extern.example", "info@h-architects-nep.example", "collega@intern.test"):
    with omgeving() as (api, verslag), patch.object(W.agenda, "interne_adressen", return_value={"collega@intern.test"}):
        resultaat = veilig(lambda: W._patch(afspraak(maker=maker),
                                           {"summary": "Mehdi: [HA-KB] 2601 - Proef"}, "nep"))
    check(f"A5: maker {maker} geeft één voorstel en nul titel-PATCH",
          not api.titels() and len(verslag.regels) == 1 and verslag.voorstel(), str(resultaat))

with omgeving() as (api, verslag):
    resultaat = veilig(lambda: W._patch(afspraak(deelnemers=["mehdi@extern.example"]),
                                       {"summary": "Mehdi: [HA-KB] 2601 - Proef"}, "nep"))
check("A5: vreemde gast met mehdi in adres geeft één voorstel en nul titel-PATCH",
      not api.titels() and len(verslag.regels) == 1 and verslag.voorstel(), str(resultaat))

with omgeving() as (api, verslag):
    resultaat = veilig(lambda: W._patch(afspraak(maker=" " + W.WERKAGENDA.upper() + " "),
                                       {"summary": "Mehdi: [HARC-KB] 2601 - Proef"}, "nep"))
check("A5: eigen maker als volledig genormaliseerd adres krijgt canonieke code",
      resultaat is None and api.titels() == ["Mehdi: [HA-KB] 2601 - Proef"], str(resultaat))

for oud, nieuw in (("Mehdi: [HARC-PO] Proef", "VR Mehdi: [HARC-PO] Proef"),
                  ("VR Mehdi: [HARC-PO] Proef", "Mehdi: [HARC-PO] Proef")):
    with omgeving() as (api, verslag):
        resultaat = veilig(lambda: W._patch(afspraak(oud, omschrijving="https://calendly.com/proef"),
                                           {"summary": nieuw}, "nep"))
    check("A6: alleen VR wijzigen bij oude vierlettercode en Calendly-link", resultaat is None
          and api.titels() == [W.canoniek(nieuw)], f"{oud}: {resultaat}")

with omgeving() as (api, verslag):
    oud = "Mehdi: [HARC-PO] Proef"
    resultaat = veilig(lambda: W._patch(afspraak(oud), {"summary": "VR Mehdi: [HARC-PO] Andere proef"}, "nep"))
check("A6: VR met andere titelwijziging is geen vrijstelling", not api.titels() and verslag.voorstel(), str(resultaat))

for velden in ({"maker": "vreemd@extern.test"}, {"deelnemers": ["gast@extern.test"]}):
    with omgeving() as (api, verslag):
        blok = afspraak("VR Agendawacht: [HA-KB] Mail", kalender=W.PRIVE_AGENDA,
                        _merk={W.MAILMERK: mailmerk}, **velden)
        resultaat = veilig(lambda: W._patch(blok, {"summary": "Opgelost: Mail"}, "nep"))
    check(f"A6: privaat mailmerk met {next(iter(velden))} weigert",
          not api.titels() and verslag.voorstel(), str(resultaat))

with omgeving() as (api, verslag):
    blok = afspraak("VR Agendawacht: [HA-KB] Mail", kalender=W.PRIVE_AGENDA,
                    maker=W.PRIVE_AGENDA, _merk={W.MAILMERK: mailmerk})
    resultaat = veilig(lambda: W._patch(blok, {"summary": "Opgelost: Mail"}, "nep"))
check("A6: eigen mailblok van exact agentaccount wordt bijgewerkt", resultaat is None
      and api.titels() == ["Opgelost: Mail"], str(resultaat))

with omgeving() as (api, verslag):
    blok = afspraak("Mehdi: [HA-KB] Kine", kalender=W.PRIVE_AGENDA,
                    _merk={W.ZORGMERK: "willekeurige-tekst"})
    resultaat = veilig(lambda: W._patch(blok, {"summary": "!! [PR] Kine - Proef"}, "nep"))
check("A6: zorgmerk met vreemd formaat geeft geen vrijstelling", not api.titels() and verslag.voorstel(),
      str(resultaat))

# H1-1d, C5: een onderzoeksuitkomst mag VR oplossen, maar de route mag geen ander titelrecht geven.
def onderzoek_blok(**extra):
    return afspraak("VR Mehdi: 2607", **extra)


projecten_2607 = {"2607": {"adres": "Proefstraat 1, 3000 Leuven"}}
a7_resultaten = {}
for naam, extra in (("eigen", {}), ("Calendly", {"omschrijving": "https://calendly.com/proef"}),
                    ("externe gast", {"deelnemers": ["gast@extern.test"]}),
                    ("vreemde maker", {"maker": "vreemd@extern.test"})):
    with omgeving() as (api, verslag), patch.object(W.projectadressen, "index", return_value=projecten_2607), \
            patch.object(W, "klant_van_nummer", return_value="Klant Proef"):
        resultaat = veilig(lambda: W.titels_aanvullen([onderzoek_blok(**extra)]))
    regels = resultaat[1] if isinstance(resultaat, tuple) else []
    verwacht = "Mehdi: [HA-KO] 2607 - Klant Proef"
    a7_resultaten[naam] = (((api.titels() == [verwacht] and resultaat[0] == 1) if naam == "eigen"
                           else (not api.titels() and any("VOORSTEL" in r for r in regels))),
                          f"{resultaat}; PATCH={api.patch}")

with omgeving() as (api, verslag), patch.object(W, "titel_uit_onderzoek",
                                                return_value=("Mehdi: [HA-KB] [UB-PO] 2607 - Proef", "onderzoek")):
    resultaat = veilig(lambda: W.titels_aanvullen([onderzoek_blok()]))
regels = resultaat[1] if isinstance(resultaat, tuple) else []
a7_resultaten["firmaconflict"] = (not api.titels() and any("VOORSTEL" in r for r in regels), str(resultaat))

with omgeving() as (api, verslag):
    resultaat = veilig(lambda: W._patch(onderzoek_blok(),
                                       {"summary": "Mehdi: [HA-KO] 2607 - Klant Proef"}, "nep"))
a7_resultaten["zonder routevlag"] = (not api.titels() and verslag.voorstel(), str(resultaat))
check("A7: onderzoek lost VR op; Calendly, conflict, gast, maker en willekeurige wijziging blijven dicht",
      all(goed for goed, _ in a7_resultaten.values()),
      "; ".join(f"{naam}: {detail}" for naam, (goed, detail) in a7_resultaten.items() if not goed))

with omgeving() as (api, verslag):
    zorg = afspraak("Mehdi: [HA-KB] Kine", kalender=W.PRIVE_AGENDA, _merk={W.ZORGMERK: zorgmerk})
    resultaat = veilig(lambda: W._patch(zorg, {"summary": "Mehdi: [UB-PO] Kine"}, "nep"))
check("A8: geldig zorgmerk op gewone privéafspraak laat geen firmawissel door",
      not api.titels() and verslag.voorstel(), str(resultaat))

mail_resultaten = {}
for nieuw, toegestaan in (("Opgelost: Mail", True), ("VR Agendawacht: vernieuwde vraag", True),
                          ("Mehdi: willekeurig", False)):
    with omgeving() as (api, verslag):
        mail = afspraak("VR Agendawacht: Mail", kalender=W.PRIVE_AGENDA,
                        _merk={W.MAILMERK: mailmerk})
        resultaat = veilig(lambda: W._patch(mail, {"summary": nieuw}, "nep"))
    mail_resultaten[nieuw] = (((api.titels() == [nieuw] and resultaat is None) if toegestaan
                              else (not api.titels() and verslag.voorstel())), str(resultaat))
check("A8: mailmerk laat alleen Agendawacht en Opgelost toe",
      all(goed for goed, _ in mail_resultaten.values()),
      "; ".join(f"{naam}: {detail}" for naam, (goed, detail) in mail_resultaten.items() if not goed))

rit_resultaten = {}
for nieuw, vlag, toegestaan in (("🚗 Reistijd: thuis → Proefstraat", False, True),
                                ("Mehdi: willekeurig", False, False),
                                ("🚗 Reistijd: thuis → Proefstraat", True, True),
                                ("Mehdi: willekeurig", True, False)):
    with omgeving() as (api, verslag):
        rit = afspraak("🚗 Reistijd: [HA-KB] Oud", id="rit-c5",
                       omschrijving="Reistijd voor: Proef; OSRM",
                       _merk={W.RITMERK: "rit-c5"} if not vlag else {})
        resultaat = veilig(lambda: W._patch(rit, {"summary": nieuw}, "nep", eigen_rit=vlag))
    rit_resultaten[(nieuw, vlag)] = (((api.titels() == [nieuw] and resultaat is None) if toegestaan
                                     else (not api.titels() and verslag.voorstel())), str(resultaat))
check("A8: gemerkte en oude OSRM-rit krijgen alleen een rittitel",
      all(goed for goed, _ in rit_resultaten.values()),
      "; ".join(f"{naam}: {detail}" for naam, (goed, detail) in rit_resultaten.items() if not goed))

with omgeving() as (api, verslag), patch.object(W.agenda, "interne_adressen", return_value={"collega@intern.test"}):
    a = afspraak("Mehdi: [HARC-KB] 2601 - Proef", _reeks="nep-reeks", _terugkerend=True,
                _agendagasten=["collega@intern.test"])
    api.reeks = {"summary": a["titel"], "description": "", "creator": {"email": W.WERKAGENDA},
                 "attendees": [{"email": "collega@intern.test"}]}
    resultaat = veilig(lambda: W.codes_reeksen([a]))
check("A3: collega als agendagast blokkeert reeks niet", api.titels() and resultaat[0] == 1, str(resultaat))

for route in ("codes_reeksen", "uitroep_vooraan"):
    with omgeving() as (api, verslag):
        a = afspraak("Mehdi: [HARC-KB] 2601 - Proef !!", _reeks="nep-reeks", _terugkerend=True,
                    deelnemers=["gast@extern.test"])
        resultaat = veilig(lambda: getattr(W, route)([a]))
    regels = resultaat[1] if isinstance(resultaat, tuple) else []
    check(f"A4: {route} slaat gastenreeks voor GET over en geeft één voorstel",
          api.get == 0 and not api.patch and len(regels) == 1 and "VOORSTEL" in regels[0],
          f"{resultaat}; GET={api.get}; PATCH={api.patch}")

with omgeving() as (api, verslag):
    a = afspraak("Mehdi: [HARC-KB] 2601 - Proef", _reeks="nep-reeks", _terugkerend=True,
                omschrijving="https://calendly.com/proef")
    resultaat = veilig(lambda: W.codes_reeksen([a]))
regels = resultaat[1] if isinstance(resultaat, tuple) else []
check("A4: bekende Calendly-reeks geeft geen GET en één voorstel", api.get == 0 and not api.patch
      and len(regels) == 1 and "VOORSTEL" in regels[0], f"{resultaat}; GET={api.get}")


# Voer het afsluitende deel van main uit met nagebootste stappen. Op HEAD staat de verzending vóór dit deel.
bronboom = ast.parse(BRON.read_text(encoding="utf-8"))
main = next(n for n in bronboom.body if isinstance(n, ast.FunctionDef) and n.name == "main")
ronde = next(n for n in main.body if isinstance(n, ast.Try))

# A9: drie werkelijke weigeringen worden elk als voorstel door de signaalstap van main gelezen.
with omgeving() as (api, verslag):
    uitroep = veilig(lambda: W.uitroep_vooraan([
        afspraak("Mehdi: [HA-KB] 2601 - Proef !!", maker="vreemd@extern.test")]))
    uitroep_patches = api.titels()
with omgeving() as (api, verslag), patch.object(W.projectadressen, "index", return_value={}), \
        patch.object(W, "klant_van_nummer", return_value="Klant Proef"):
    aanvullen = veilig(lambda: W.titels_aanvullen([
        afspraak("Mehdi: [HA-KB] 2601", maker="vreemd@extern.test")]))
    aanvullen_patches = api.titels()
with omgeving() as (api, verslag), patch.object(W, "projectnummer_zoeken", return_value=("2601", "nepbron")):
    project = veilig(lambda: W.projectnummers_zetten([
        afspraak("Mehdi: [HA-KB] Proef", maker="vreemd@extern.test")]))
    project_patches = api.titels()

signaal_if = next(n for n in ronde.body if isinstance(n, ast.If)
                 and "zregels" in ast.unparse(n.test) and "ag.klaarzet" in ast.unparse(n))
voorstellen_assign = [n for n in ronde.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "voorstellen" for t in n.targets)]
signaal_code = compile(ast.fix_missing_locations(ast.Module(body=voorstellen_assign + [signaal_if], type_ignores=[])),
                      str(BRON), "exec")
for naam, resultaat, patches in (("uitroep_vooraan", uitroep, uitroep_patches),
                                ("titels_aanvullen", aanvullen, aanvullen_patches),
                                ("projectnummers_zetten", project, project_patches)):
    regels = resultaat[1] if isinstance(resultaat, tuple) else []
    signalen = []
    omgeving_main = {"ag": SimpleNamespace(klaarzet=lambda x: signalen.extend(x)),
                    "nregels": regels if naam != "projectnummers_zetten" else [],
                    "pregels": regels if naam == "projectnummers_zetten" else [],
                    "zregels": [], "vandaag": "2026-10-17", "dag_grens": None}
    doorgifte = veilig(lambda: exec(signaal_code, omgeving_main))
    check(f"A9: {naam} geeft VOORSTEL met reden in Mehdi's main-signaal",
          isinstance(resultaat, tuple) and len(regels) == 1 and not patches
          and bool(re.search(r"VOORSTEL '[^']+' \([^)]+\)", regels[0]))
          and "niet gezet (TitelVoorstel)" not in regels[0]
          and doorgifte is None and len(signalen) == 1
          and regels[0] in signalen[0]["inhoud"], f"{resultaat}; signaal={signalen}; {doorgifte}")

begin = next(i for i, n in enumerate(ronde.body) if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Tuple) and [e.id for e in t.elts] == ["vg", "vw"]
                     for t in n.targets))
staart = ast.fix_missing_locations(ast.Module(body=ronde.body[begin:], type_ignores=[]))
volgorde = []


class Rondeverslag:
    def log(self, onderwerp, stap, tekst, detail=""):
        volgorde.append(("log", tekst))

    def log_verstuur(self):
        volgorde.append(("verstuur", ""))

    def hartslag(self, *args, **kwargs):
        pass


def vragen(items, **_kwargs):
    volgorde.append(("stap", "vragen"))
    return 1, 0


def bellen(items):
    volgorde.append(("stap", "bellen"))
    return "nepoproep"


dummy = {"ag": Rondeverslag(), "vragen_in_agenda": vragen, "bel_als_vastgelopen": bellen,
         "kort_items": [], "rit_items": [], "niet_op_kaart": set(),
         "adres_vraag_noden": lambda _items, **_kwargs: [], "items": [], "archief": [],
         "vandaag": "2026-10-17", "DAG_ARG": None,
         "geplande_start": lambda: True, "HANDKLEUREN": [], "open_na": [], "ROUTES_GESTOPT": False,
         "fouten": [], "noden": [], "locatiebeweging": SimpleNamespace(kort=lambda x: "", lees=lambda: {}),
         "dagplan": [], "gekoppeld": 0, "niet_conform": [], "onvolledig": []}
# fase 1 (overleg 27-10-2026): de weeknood en de noodlijst van een dagronde staan nu ook aan het einde van de ronde
dummy.update({"weekconsolidatie_noden": lambda: [], "weekconsolidatie_fout": lambda: "",
              "noden_voor_hartslag": lambda noden, _dag: noden})
resultaat = veilig(lambda: exec(compile(staart, str(BRON), "exec"), dummy))
namen = [x[0] if x[0] == "verstuur" else x[1] for x in volgorde]
check("rondeverslag gaat na vragen en vastgelopen-oproep weg",
      resultaat is None and volgorde and volgorde[-1][0] == "verstuur"
      and any("vragen in de agenda" in x for x in namen) and any("vastgelopen" in x for x in namen),
      f"{resultaat} {volgorde}")

handler = ronde.handlers[0]
foutpad = ast.fix_missing_locations(ast.Module(body=[ast.Try(body=[ast.Raise(exc=ast.Call(
    func=ast.Name(id="RuntimeError", ctx=ast.Load()), args=[ast.Constant(value="proef")], keywords=[]), cause=None)],
    handlers=[ast.ExceptHandler(type=ast.Name(id="Exception", ctx=ast.Load()), name="e",
                                body=[n for n in handler.body if not isinstance(n, ast.Raise)])],
    orelse=[], finalbody=[])], type_ignores=[]))
volgorde.clear()
resultaat = veilig(lambda: exec(compile(foutpad, str(BRON), "exec"), dummy))
check("foutpad verstuurt de foutlog", resultaat is None and [x[0] for x in volgorde] == ["log", "verstuur"],
      f"{resultaat} {volgorde}")

print(f"H1-1: {ok} goed, {fout} fout")
sys.exit(1 if fout else 0)

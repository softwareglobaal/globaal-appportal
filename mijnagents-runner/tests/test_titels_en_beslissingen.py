"""Grendels op de aanspreektitel en op Mehdi's beslissingen in de Contracten-agent (D53, 13-10-2026).

Aanleiding: dossier 2618 (BRONIUS AND BRO Sp. z o.o., deal 14566). Mehdi koos in een Claude-sessie voor geen
titel bij de vertegenwoordiger; om 14:32 zette de agent "de heer", met de aanvraagmail ("De zaakvoerder ... Hij
kan aanwezig zijn") en de naam Serhii Kovalenko als bron. Het citaat stond letterlijk in de mail, dus de
citaatcontrole liet het door. Deze test faalt zodra een titel weer uit een voornaam, "hij/zij" of een aanhef
mag komen, of zodra de agent een beslissing van Mehdi (ook een lege) kan overschrijven.

Draaien, zonder pytest:   python3 mijnagents-runner/tests/test_titels_en_beslissingen.py
Geen netwerk, geen dashboard, geen model. De mailteksten zijn nagemaakt in de vorm van de echte.
"""
import inspect
import os
import sys
import tempfile

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
os.environ.setdefault("HOME", tempfile.mkdtemp(prefix="titels_"))
import herhaalbaar as hh  # noqa: E402
import contracten_agent as ca  # noqa: E402
import goudstandaard as gs  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  OK   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} -> {extra}")


DOSSIER = {"vertegenwoordiger_voornaam": "Serhii",
           "vertegenwoordiger_naam": "Kovalenko, voorzitter van het bestuur (Prezes Zarządu)",
           "contactpersoon_voornaam": "Paulina", "contactpersoon_naam": "Andrzejczyk",
           "opdrachtgever_1_voornaam": "Paulina", "opdrachtgever_1_naam": "Andrzejczyk",
           "vertegenwoordiger_titel": ""}

print("\n1. een aanspreektitel alleen uit een expliciete bron")
GEWEIGERD = [
    ("vertegenwoordiger_titel", "de heer", "De zaakvoerder van de vennootschap is de eigenaar. Hij kan aanwezig zijn bij het plaatsbezoek.",
     "2618: 'hij' in de aanvraagmail"),
    ("vertegenwoordiger_titel", "de heer", "Zaakvoerder: KOVALENKO Serhii", "2618: naam en voornaam in het proces-verbaal"),
    ("opdrachtgever_1_titel", "mevrouw", "Geachte mevrouw Andrzejczyk,", "2618: Mehdi's aanhef"),
    ("contactpersoon_titel", "mevrouw", "Geachte mevrouw Andrzejczyk,", "2618: dezelfde aanhef voor de contactpersoon"),
    ("vertegenwoordiger_titel", "de heer", "Dear Mr Kovalenko, thank you for the documents", "Engelse aanhef"),
    ("vertegenwoordiger_titel", "de heer", "Szanowny Panie Kovalenko,", "Poolse aanhef"),
    ("vertegenwoordiger_titel", "mevrouw", "Naam: KOVALENKO Voornamen: Serhii Geslacht / Sexe: M", "geslacht spreekt de titel tegen"),
    ("vertegenwoordiger_titel", "de heer", "Ons contact is de heer Jansens, en de zaakvoerder Serhii Kovalenko tekent.", "titel bij een andere naam"),
    ("contactpersoon_titel", "de heer", "Mevr. Paulina Andrzejczyk en de heer Serhii Kovalenko komen samen.", "titel van de ander"),
    ("opdrachtgever_2_titel", "mevrouw", "Mevrouw Peeters komt ook.", "geen naam van die persoon in het dossier"),
]
for veld, w, citaat, waarom in GEWEIGERD:
    reden = hh.titel_bewezen(veld, w, citaat, DOSSIER)
    check(f"geweigerd: {waarom}", bool(reden), (veld, w, citaat))
check("de aanhef krijgt zijn eigen reden",
      "aanhef" in hh.titel_bewezen("opdrachtgever_1_titel", "mevrouw", "Geachte mevrouw Andrzejczyk,", DOSSIER))

BEWEZEN = [
    ("contactpersoon_titel", "mevrouw", "Met vriendelijke groeten,\nMevr. Paulina Andrzejczyk\n+48 666 38 30 30", "handtekening van de persoon zelf"),
    ("vertegenwoordiger_titel", "de heer", "Naam: KOVALENKO Voornamen: Serhii Geslacht / Sexe: M Nationaliteit: UKR", "geslacht in een document"),
    ("vertegenwoordiger_titel", "De heer", "Mevr. Paulina Andrzejczyk en de heer Serhii Kovalenko komen samen.", "titel direct voor zijn naam"),
    ("vertegenwoordiger_titel", "de heer", "Pan Serhii Kovalenko, Prezes Zarządu, reprezentuje spółkę", "Poolse titel voor de naam"),
    ("vertegenwoordiger_titel", "Dhr.", "Getekend: dhr. S. Kovalenko", "afkorting met initiaal"),
]
for veld, w, citaat, waarom in BEWEZEN:
    reden = hh.titel_bewezen(veld, w, citaat, DOSSIER)
    check(f"bewezen: {waarom}", not reden, reden)

print("\n2. toets_post: het geval 2618 letterlijk")
MAIL = ("Goedendag, wij willen een vergunning voor de aanbouw. De zaakvoerder van de vennootschap is de eigenaar. "
        "Hij kan aanwezig zijn bij het plaatsbezoek. Met vriendelijke groeten, Paulina Andrzejczyk")
TEKSTEN = [("mail 2026-09-25 Regularisatie aanbouw", MAIL),
           ("salesmap: pismo BRONIUS.pdf", "Zaakvoerder: KOVALENKO Serhii"),
           ("salesmap: handtekening.md", "Mevr. Paulina Andrzejczyk, vennoot"),
           ("salesmap: identiteitskaart.md", "Naam: KOVALENKO Voornamen: Serhii Geslacht / Sexe: M")]
POST_2618 = {"velden": {"vertegenwoordiger_titel": "de heer"},
             "bron": "aanvraagmail 25-09-2026 en de naam Serhii Kovalenko in het proces-verbaal",
             "citaat": "De zaakvoerder van de vennootschap is de eigenaar. Hij kan aanwezig zijn"}
BESCHERMD = {"vertegenwoordiger_titel": "beslissing van Mehdi: bewust leeg"}
_, goed, weg = hh.toets_post(POST_2618, TEKSTEN, None, DOSSIER, {})
check("het citaat staat letterlijk in de mail, toch geen titel", not goed and weg and weg[0][0] == "vertegenwoordiger_titel", (goed, weg))
_, goed, weg = hh.toets_post(POST_2618, TEKSTEN, None, DOSSIER, BESCHERMD)
check("en met Mehdi's lege beslissing erbij: zeker niet", not goed, (goed, weg))
_, goed, weg = hh.toets_post({"velden": {"vertegenwoordiger_titel": "de heer"}, "bron": "pismo BRONIUS.pdf",
                              "citaat": "Zaakvoerder: KOVALENKO Serhii"}, TEKSTEN, None, DOSSIER, {})
check("de naam in het proces-verbaal is geen titel", not goed, (goed, weg))
_, goed, weg = hh.toets_post({"velden": {"contactpersoon_titel": "mevrouw"}, "bron": "handtekening 12-10-2026",
                              "citaat": "Mevr. Paulina Andrzejczyk, vennoot"}, TEKSTEN, None, DOSSIER, {})
check("een titel die de persoon zelf voert, mag wel", goed == {"contactpersoon_titel": "mevrouw"}, (goed, weg))
POST_ID = {"velden": {"vertegenwoordiger_titel": "de heer"}, "bron": "identiteitskaart in de salesmap",
           "citaat": "Naam: KOVALENKO Voornamen: Serhii Geslacht / Sexe: M"}
_, goed, weg = hh.toets_post(POST_ID, TEKSTEN, None, DOSSIER, {})
check("een document met geslacht bewijst de titel", goed == {"vertegenwoordiger_titel": "de heer"}, (goed, weg))
_, goed, weg = hh.toets_post(POST_ID, TEKSTEN, None, DOSSIER, BESCHERMD)
check("maar ook een bewezen titel gaat niet over Mehdi's lege beslissing",
      not goed and any("niet overschreven" in r for _, _, r in weg), weg)
_, goed, weg = hh.toets_post({"velden": {"vertegenwoordiger_voornaam": "Serhii", "vertegenwoordiger_titel": "de heer"},
                              "bron": "handtekening", "citaat": "Mevr. Paulina Andrzejczyk, vennoot"},
                             TEKSTEN, None, {}, {})
check("andere velden in dezelfde post blijven, alleen de titel valt weg",
      goed == {"vertegenwoordiger_voornaam": "Serhii"} and [w[0] for w in weg] == ["vertegenwoordiger_titel"], (goed, weg))
_, goed, weg = hh.toets_post({"velden": {"gespecialiseerde_studies_benoeming": "stabiliteit"},
                              "bron": "beslissing Mehdi 13-10-2026", "citaat": "Zaakvoerder: KOVALENKO Serhii"},
                             TEKSTEN, None, DOSSIER, {})
check("de agent claimt geen beslissing van Mehdi", not goed and "beslissing van Mehdi" in weg[0][2], weg)

print("\n3. wat beschermd is, ook leeg")
VOORB = {"velden": {"bouwbudget_bedrag_euro": "50.000,00", "vertegenwoordiger_titel": "",
                    "uitvoeringswijze_label": "algemene aanneming", "opdrachtgever_1_naam": "Andrzejczyk"},
         "herkomst": {"gevuld": [
             {"sleutel": "bouwbudget_bedrag_euro", "soort": "afgeleid",
              "bron": "via de connector: beslissing Mehdi 13-10-2026 in Claude-sessie: vooropgesteld bouwbudget"},
             {"sleutel": "opmeting_inbegrepen", "soort": "afgeleid", "bron": "via de connector: D51 goedgekeurd door Mehdi 13-10-2026"},
             {"sleutel": "uitvoeringswijze_label", "soort": "afgeleid", "bron": "Mehdi beslist of het een aannemer is"},
             {"sleutel": "opdrachtgever_1_naam", "soort": "crm", "bron": "Pipedrive"},
             {"sleutel": "project_beschrijving", "soort": "dashboard", "bron": "ingevuld in het dashboard",
              "zekerheid": "ingevuld in het dashboard"}]},
         "beschermd": [{"sleutel": "vertegenwoordiger_titel", "waarde": "", "reden": "beslissing van Mehdi: bewust leeg"}]}
b = hh.beschermde_velden(VOORB)
check("de lijst van het dashboard telt, ook het lege veld", b.get("vertegenwoordiger_titel") == "beslissing van Mehdi: bewust leeg", b)
check("een beslissing van Mehdi uit herkomst.gevuld", b.get("bouwbudget_bedrag_euro") == "beslissing van Mehdi", b)
check("'goedgekeurd door Mehdi' is ook een beslissing", "opmeting_inbegrepen" in b, b)
check("ingevuld in het dashboard", "project_beschrijving" in b, b)
check("'Mehdi beslist' (nog te doen) beschermt niets", "uitvoeringswijze_label" not in b, b)
check("uit Pipedrive is niet beschermd", "opdrachtgever_1_naam" not in b, b)
goed, weg = hh.zonder_beschermd({"bouwbudget_bedrag_euro": "60.000,00", "vertegenwoordiger_titel": "de heer",
                                 "uitvoeringswijze_label": "regie"}, VOORB["velden"], b)
check("andere waarde: geweigerd met de reden", {w[0] for w in weg} == {"bouwbudget_bedrag_euro", "vertegenwoordiger_titel"}, weg)
check("niet beschermd: gaat door", goed == {"uitvoeringswijze_label": "regie"}, goed)
goed, weg = hh.zonder_beschermd({"bouwbudget_bedrag_euro": "50.000,00"}, VOORB["velden"], b)
check("zelfde waarde: stil weg, geen weigering in de melding", not goed and not weg, (goed, weg))

print("\n4. de runner en de goudstandaard gebruiken deze toets, niet een eigen")
bron_verwerk = inspect.getsource(ca.verwerk)
check("verwerk toetst elke post met hh.toets_post", "hh.toets_post(" in bron_verwerk)
check("verwerk valideert niet meer buiten de toets om", "hh.valideer_gegevens(" not in bron_verwerk
      and "hh.pas_citaat_toe(" not in bron_verwerk)
check("verwerk haalt beschermde keuzes eruit", "hh.zonder_beschermd(" in bron_verwerk)
check("verwerk leest niet_overschreven uit het antwoord van het dashboard", bron_verwerk.count("niet_overschreven") >= 2)
bron_gs = inspect.getsource(gs.uitkomst_van)
check("de goudstandaard toetst met dezelfde functie", "hh.toets_post(" in bron_gs and "hh.zonder_beschermd(" in bron_gs)
check("het model krijgt de beschermde velden, ook de lege", "beschermde_velden" in inspect.getsource(ca.plan_met_model))
check("de prompt verbiedt een titel uit een voornaam, 'hij/zij' of een aanhef",
      all(s in ca.SCHEMA_UITLEG for s in ("aanspreektitel", "voornaam", "aanhef", "beslissing Mehdi")))

print("\n5. een voorstel voor een leeg veld uit het dashboard gaat mee als voorstel (D64, 5610)")
PV = "In het appartement op de zolderverdieping werd aan de voorzijde in het zadeldak een inpandig dakterras gecreëerd"
TEKSTEN_PV = [("salesmap: 11002_2024_18344_VPV_anoniem.pdf", PV)]
POST_PV = {"velden": {"regularisatiewerken_bullets": "Inpandig dakterras in het zadeldak aan de voorzijde"},
           "bron": "proces-verbaal 11002_2024_18344_VPV", "citaat": PV}
LEEG_DASHBOARD = {"regularisatiewerken_bullets": "bewust leeggemaakt in het dashboard"}
_, goed, weg = hh.toets_post(POST_PV, TEKSTEN_PV, None, {"regularisatiewerken_bullets": ""}, LEEG_DASHBOARD)
check("toets_post zelf schrijft het beschermde veld niet (D53 blijft)", not goed, (goed, weg))
check("maar het gaat mee als voorstel", hh.voorstellen_voor_leeg(POST_PV, TEKSTEN_PV, None,
      {"regularisatiewerken_bullets": ""}, LEEG_DASHBOARD) == POST_PV["velden"])
check("niet als het citaat niet in de bron staat", not hh.voorstellen_voor_leeg(
      {**POST_PV, "citaat": "verzonnen zin"}, TEKSTEN_PV, None, {"regularisatiewerken_bullets": ""}, LEEG_DASHBOARD))
check("niet bij een beslissing van Mehdi (bewust leeg, zoals de titel bij 2618)",
      not hh.voorstellen_voor_leeg(POST_ID, TEKSTEN, None, DOSSIER, BESCHERMD))
check("niet als het veld al gevuld is", not hh.voorstellen_voor_leeg(POST_PV, TEKSTEN_PV, None,
      {"regularisatiewerken_bullets": "Terras"}, {"regularisatiewerken_bullets": "ingevuld in het dashboard"}))
check("de runner stuurt het voorstel en meldt het niet als geschreven",
      "voorstellen_voor_leeg" in inspect.getsource(ca) and "voorstel_klaargezet" in inspect.getsource(ca))

print("\n6. de proef komt er altijd, ook met tijdlijngaten (D66, Mehdi 20-10-2026)")
_bron = inspect.getsource(ca)
check("de runner houdt de proef niet meer tegen bij een tijdlijngat",
      'raise mcp.ToolFout("tijdlijn niet volledig (D37)")' not in _bron and 'mcp_call("proef_maken", deal_id=deal_id)' in _bron)
_m = ca.melding_tekst({"melding": {}}, "PROEF-5610.docx", None, proefpunten=["Tijdlijn niet volledig <b>"])
check("de melding noemt de aandachtspunten, veilig als tekst", "1 punt(en) om na te kijken" in _m and "&lt;b&gt;" in _m, _m[-300:])

print(f"\n{'=' * 50}\n{ok} geslaagd, {fout} gefaald\n{'=' * 50}")
sys.exit(1 if fout else 0)

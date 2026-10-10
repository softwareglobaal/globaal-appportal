#!/usr/bin/env python3
"""Bericht aan de collega's over de agenda's (v2.0 sinds 11-10-2026, vervangt v1.1 van 20-09-2026).

Het blad dat Mehdi zelf aan de collega's geeft die zijn agenda plannen. Alles komt uit de master
(werkwijze/agenda-taken.json); de firmacodes komen live van organisatie.globaal.be via de VM en moeten
gelijk zijn aan de master, anders stopt de bouw. Draait op de Mac (Chrome maakt de PDF).
Uitvoer: Dropbox 'private/0 Chegini Mehdi/Prive met Claude'; een oudere versie gaat naar 'Agenda archief/oude documenten'.
De grendel is tests/test_collegas_pdf.py: elk voorbeeld hieronder wordt door de agent zelf gelezen zoals bedoeld.
Nieuwe versie: 'collegadocument.versie' in de master ophogen. Dit script verstuurt niets.
"""
import datetime
import html
import json
import pathlib
import re
import subprocess
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
UIT = pathlib.Path.home() / "TKN-buro Dropbox/private/0 Chegini Mehdi/Prive met Claude"
ARCHIEF = UIT / "Agenda archief" / "oude documenten"
NIET_VOOR_COLLEGAS = {"PR", "LA"}     # privé en Lara: daar plant geen collega in
e = html.escape

# Elk voorbeeld met wat de agent eruit moet lezen; de test legt het naast lees_titel, canoniek en agendagasten_voor.
VOORBEELDEN = [
    {"titel": "!! Mehdi: [HA-KB] WB 2607 - Jan Peeters, Dorpstraat 5, 2800 Mechelen",
     "uitleg": "Werfbezoek bij een klant van H-Architects, buiten, met projectnummer en volledig adres.",
     "firma": "HA", "soort": "KB", "type": "WB", "nummer": "2607", "buiten": True, "onzeker": False},
    {"titel": "!! ?? Mehdi: [UB-PB] PS - Sara Claes, Kerkstraat 12, 3000 Leuven",
     "uitleg": "Plaatsbeschrijving bij een prospect van UnaBo, buiten, nog niet bevestigd. Een prospect heeft nog geen projectnummer.",
     "firma": "UB", "soort": "PB", "type": "PS", "nummer": "", "buiten": True, "onzeker": True},
    {"titel": "Mehdi: [TK-KO] SD 260009 - Lien Maes",
     "uitleg": "Online gesprek over het schetsontwerp met een klant van TKN-Buro (nummer van TKN-Buro, zes cijfers vanaf 2026).",
     "firma": "TK", "soort": "KO", "type": "SD", "nummer": "260009", "buiten": False, "onzeker": False},
    {"titel": "Mehdi: [UB-PO] EP - Tom Janssens",
     "uitleg": "Online gesprek over EPB met een prospect van UnaBo. Zo komt ook een boeking van Calendly binnen.",
     "firma": "UB", "soort": "PO", "type": "EP", "nummer": "", "buiten": False, "onzeker": False},
    {"titel": "!! Mehdi & Catalin: [HB-AB] WB - Bouwbedrijf De Smet, Molenstraat 8, 9200 Dendermonde",
     "uitleg": "Werfbezoek met de aannemer voor Harmoniebouw. Catalin staat na Mehdi en krijgt de afspraak in de eigen agenda.",
     "firma": "HB", "soort": "AB", "type": "WB", "nummer": "", "buiten": True, "onzeker": False, "gast": "Catalin"},
    {"titel": "Mehdi & Shaniel: [HA-IN] AI - opvolging agenda's",
     "uitleg": "Interne bespreking over AI en automatisering. Shaniel krijgt ze in de eigen agenda.",
     "firma": "HA", "soort": "IN", "type": "AI", "nummer": "", "buiten": False, "onzeker": False, "gast": "Shaniel"},
]
TEL_VOORBEELD = "Tel. Jan Peeters: 0470 12 34 56"


def su(x):
    """Nooit de volledige landnaam van SU tonen (regel van Mehdi)."""
    return re.sub(r"[Ss]uriname", "SU", x)


def master():
    return json.loads((REPO / "werkwijze/agenda-taken.json").read_text(encoding="utf-8"))


def firmas_master(t):
    return [(k, su(v)) for k, v in t["titelconventie"]["codes_twee_letters"]["firmas"].items() if k not in NIET_VOOR_COLLEGAS]


def firmas_live(t):
    """De firma's live van organisatie.globaal.be (via de agent op de VM), in de volgorde van de master.
    Wijkt de lijst af van de master, dan stopt de bouw: een blad voor de collega's met een verkeerde code is erger dan geen blad."""
    snap = json.loads(subprocess.run(["ssh", "globaal", "~/agents/.venv/bin/python", "-"],
                                     stdin=open(pathlib.Path(__file__).with_name("momentopname.py")),
                                     capture_output=True, text=True, timeout=180, check=True).stdout)
    ac = snap.get("agendacodes") or {}
    live = {ac.get(k, k): su(v) for k, v in snap["firmacodes"].items()}
    live.update({ac.get(k, k): "Algemeen (geen firma)" for k in snap["externe_firmas"]})
    verwacht = [k for k, _ in firmas_master(t)]
    if set(live) != set(verwacht):
        raise SystemExit(f"firmacodes live en master lopen uit elkaar: live {sorted(live)}, master {sorted(verwacht)}")
    return [(k, live[k]) for k in verwacht]


def google_instelling(t):
    m = re.search(r"Google: '([^']+)'", t["agendagasten"]["zonder_mail"])
    return m.group(1) if m else "Uitnodigingen toevoegen aan mijn agenda"


def bericht(t, firmas, bouwdatum, commit):
    """De HTML van het blad. Zuiver: geen netwerk, zodat de test (ook in de CI) precies dit blad nakijkt."""
    tc = t["titelconventie"]
    cd = t["collegadocument"]
    werk = next(a for a in t["agendas"] if a["rol"] == "werk")
    oud = [a["naam"] for a in t["agendas"] if a["rol"] in ("firma", "sales")]
    buiten = set(tc["activiteiten"]["altijd_buiten"])
    naam = f"{cd['naam']} v{cd['versie']}"

    def twee_kolommen(rijen, breed="12mm"):
        h = (len(rijen) + 1) // 2
        return "".join(f"<tr><td class=c style='width:{breed}'><b>{e(a[0])}</b></td><td>{e(a[1])}</td>"
                       + (f"<td class=c style='width:{breed}'><b>{e(b[0])}</b></td><td>{e(b[1])}</td>" if b else "<td></td><td></td>")
                       + "</tr>" for a, b in zip(rijen[:h], rijen[h:] + [None]))

    fi = twee_kolommen([(k, su(n)) for k, n in firmas])     # ook hier: de live naam van organisatie draagt de volledige landnaam
    so = twee_kolommen(list(tc["soorten"].items()))
    ty = twee_kolommen([(k, v + (" (altijd buiten: !!)" if k in buiten else "")) for k, v in tc["types"].items()])
    per_nieuw = {}
    for o, n in tc["oude_codes"]["firma"].items():
        if n not in NIET_VOOR_COLLEGAS:
            per_nieuw.setdefault(n, []).append(o)
    ou_f = twee_kolommen([(n, "was " + ", ".join(v)) for n, v in per_nieuw.items()])
    ou_o = ", ".join(f"{o} wordt <b>{e(n)}</b>" for o, n in tc["oude_codes"]["opdracht"].items())
    vb = "".join(f"<tr><td><code>{e(v['titel'])}</code><div class=kl>{e(v['uitleg'])}</div></td></tr>" for v in VOORBEELDEN)
    nrs = tc["projectnummer_alle_firmas"]["nummers"]

    return f"""<!doctype html><html lang=nl><meta charset=utf-8><title>{e(naam)}</title>
<style>
@page{{size:A4;margin:14mm}}
body{{font:9.9pt/1.45 -apple-system,"Helvetica Neue",Arial,sans-serif;color:#14181f}}
h1{{font-size:17pt;margin:0 0 2mm}} h2{{font-size:11.8pt;margin:6mm 0 2mm;border-bottom:1.5px solid #14181f;padding-bottom:1mm;break-after:avoid}}
p{{margin:0 0 2.6mm}} ul{{margin:0 0 3mm;padding-left:5mm}} li{{margin-bottom:1.2mm}}
code{{font:8.8pt ui-monospace,Menlo,monospace;background:#eef1f5;padding:.3mm 1.2mm}}
table{{border-collapse:collapse;width:100%;font-size:8.9pt;margin-bottom:3mm}}
td{{border-bottom:.4px solid #d6dae1;padding:1.3mm 2mm;vertical-align:top}}
tr{{break-inside:avoid}} .c{{text-align:center;white-space:nowrap}}
.kl{{color:#5d6673;font-size:8.2pt;margin-top:.6mm}}
.kader{{border:1px solid #14181f;padding:3mm 4mm;margin:0 0 4mm;background:#f7f8fa}}
.vorm{{font:10.5pt ui-monospace,Menlo,monospace;border:1.5px solid #14181f;padding:2.5mm 3mm;margin:0 0 3mm}}
.top{{color:#5d6673;font-size:8pt;margin-bottom:3mm}}
.regel{{border-left:3px solid #14181f;padding:1mm 0 1mm 3mm;margin:0 0 3mm}}
</style>
<div class=top>Voor de collega's die Mehdi's agenda plannen &nbsp;|&nbsp; versie {e(cd['versie'])}, vervangt v1.1 van 20-09-2026 &nbsp;|&nbsp;
gemaakt {e(bouwdatum)} &nbsp;|&nbsp; bron: agenda-taken.json v{e(t['versie'])}, commit {e(commit)}</div>
<h1>Afspraken in mijn agenda</h1>

<div class=kader>
Dag allemaal,<br><br>
Al mijn werk, van elke firma, staat in één agenda: <b>{e(werk['naam'])}</b> ({e(werk['adres'])}). Sinds 2 oktober gebruiken we in de titel
overal codes van <b>twee letters</b>; de langere codes van het vorige bericht (UNABO, CONTRAX, TKN, ELEVAIT) en de codes van vier letters
gelden niet meer. HA en HB blijven. Mijn assistent, de Agendawacht, leest de agenda elke dag: hij zet de kleuren, de reistijd en de herinneringen en
belt mij als het nodig is. Dat lukt alleen als de titel klopt en het adres en het telefoonnummer erin staan. Hieronder staat alles wat je nodig hebt.
<br><br>Mehdi
</div>

<h2>1. Welke agenda</h2>
<ul>
<li>Elke afspraak voor mij komt in <b>{e(werk['naam'])}</b>, van welke firma ook.</li>
<li>Niet meer gebruiken: {e(', '.join(oud))} en elke agenda die met <b>ZZ ARCHIEF</b> begint. Die blijven leeg.</li>
<li>In mijn privé-agenda en in die van Lara zet je niets. Kijk wel naar de hele-dag-items op die van Lara (zie punt 5).</li>
<li>Online afspraken die een klant zelf boekt via Calendly komen vanzelf in de werkagenda, met de Zoom-link. Daar hoef je niets aan te doen.
Buitenafspraken en werfbezoeken gaan niet via Calendly: die zet je met de hand.</li>
</ul>

<h2>2. De titel</h2>
<div class=vorm>!! Mehdi: [FF-SS] TT nummer - klant, straat nummer, postcode gemeente</div>
<ul>
<li><b>FF</b> de firma, <b>SS</b> de soort afspraak, <b>TT</b> de opdracht: telkens twee hoofdletters (tabellen in punt 4).</li>
<li><b>!!</b> helemaal vooraan als ik naar buiten moet (ik heb reistijd nodig). <b>??</b> erna als de afspraak nog niet bevestigd is;
haal de vraagtekens weg zodra ze vaststaat.</li>
<li><b>nummer</b>: bij een klant altijd het projectnummer. H-Architects: {e(nrs['HARC'])}. UnaBo, TKN-Buro en Energie Efficiënt:
{e(nrs['UNAB, TKNB, ENEF'])}. Een prospect heeft nog geen nummer.</li>
<li><b>Buiten</b> altijd het volledige adres: straat, huisnummer, postcode en gemeente. Zonder adres kan de reistijd niet berekend worden.</li>
</ul>
<table><tbody>{vb}</tbody></table>

<h2>3. Het telefoonnummer</h2>
<div class=regel>Bij elke afspraak met iemand van buiten staat <b>bovenaan de omschrijving</b> het telefoonnummer van die persoon:
<code>{e(TEL_VOORBEELD)}</code>. Zo kunnen ik en mijn assistent bellen als er iets verandert. Telefoon, adres en projectnummer horen
altijd in de afspraak.</div>
<p>Zet je zelf een online afspraak met iemand van buiten, plak dan de volledige Zoom-link mét wachtwoord in de afspraak. Heb je geen link,
laat het zo: de assistent zet <b>ZL</b> vooraan en ik stuur de link zelf.</p>

<h2>4. De codes</h2>
<p><b>Firma (FF)</b></p>
<table><tbody>{fi}</tbody></table>
<p><b>Soort (SS)</b>. Klant: er is getekend en er is een projectnummer. Prospect: nog niet getekend. Leverancier: wij kopen.
Aannemer: de aannemer van een klant. Een leverancier voor de hele groep (bijvoorbeeld de boekhouder) krijgt firma AL.</p>
<table><tbody>{so}</tbody></table>
<p><b>Opdracht (TT)</b>. Bij de opdrachten die altijd buiten zijn, staat !! vooraan.</p>
<table><tbody>{ty}</tbody></table>
<p><b>Oude codes.</b> De assistent leest ze nog, maar schrijf ze niet meer.</p>
<table><tbody>{ou_f}</tbody></table>
<p class=kl>Opdrachten: {ou_o}. B2B wordt XB (buiten) of XO (online).</p>

<h2>5. Een hele-dag-item is een stop</h2>
<p>Staat er een hele dag een melding op de werkagenda of op de agenda van Lara, dan plan je die dag niets wat ertegen ingaat:</p>
<ul>
<li><b>Geen buiten afspraken</b> (bijvoorbeeld Lara ophalen) en <b>geen auto</b>: die dag niets buiten. Online kan wel.</li>
<li><b>Geen afspraken</b> en <b>Buitenland</b>: die dag of die dagen helemaal niets.</li>
</ul>
<p>Twijfel je, vraag het eerst. Staat er toch iets, dan meldt de assistent het aan mij.</p>

<h2>6. De afspraak ook in je eigen agenda</h2>
<p>Ga je mee of hoor je erbij, zet dan je naam na de mijne, voor de dubbele punt: <code>Mehdi &amp; Catalin:</code>,
<code>Mehdi, Siyan &amp; Shaniel:</code> of <code>Mehdi en Angela:</code>. De assistent zet je dan als gast op de afspraak en ze verschijnt
in je eigen agenda. Er gaat geen mail uit, ook niet naar de klant. Een afspraak van Harmoniebouw (HB) komt altijd ook bij Catalin.</p>
<ul>
<li>Je agenda-adres moet bij jouw naam staan op organisatie.globaal.be. Weet je niet of dat zo is, vraag het aan Shaniel.</li>
<li>Zet in Google Agenda bij Instellingen, Algemeen, Gebeurtenisinstellingen: <b>{e(google_instelling(t))}</b> op <b>Van iedereen</b>.
Anders komt de afspraak niet vanzelf in je agenda.</li>
<li>Gebruik je voornaam zoals op organisatie.globaal.be. Delen twee collega's dezelfde voornaam, schrijf dan de volledige naam.</li>
<li>Hoor je er niet meer bij, haal dan je naam uit de titel. Jezelf als gast weghalen helpt niet: de assistent zet je terug.</li>
</ul>

<h2>7. Wat de assistent zelf doet</h2>
<ul>
<li>Kleuren, reistijd voor en na een buitenafspraak, en herinneringen. Die zet je dus niet zelf.</li>
<li>Ontbreekt een projectnummer, een klantnaam of een telefoonnummer en vindt hij het zeker, dan vult hij het aan. Een oude code zet hij om.</li>
<li><b>VR</b> vooraan is een vraag van de assistent aan mij, <b>ZL</b> een online afspraak zonder link. Die zet en haalt hij zelf; laat ze staan.</li>
<li>Hij verplaatst en verwijdert nooit een afspraak, en verandert geen titel van een afspraak met gasten: dan doet hij mij een voorstel.</li>
</ul>

<h2>8. Vragen</h2>
<p>Is iets niet duidelijk of past een afspraak in geen enkele code, geef het door aan Shaniel.</p>
<p>Mehdi</p>
</html>"""


def main():
    t = master()
    cd = t["collegadocument"]
    naam = f"{cd['naam']} v{cd['versie']}"
    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() or "?"
    doc = bericht(t, firmas_live(t), datetime.date.today().strftime("%d-%m-%Y"), commit)
    assert "urinam" not in doc, "de volledige landnaam staat in het blad"
    pdf = UIT / f"{naam}.pdf"
    with tempfile.TemporaryDirectory() as d:
        h = pathlib.Path(d) / "collegas.html"
        h.write_text(doc, encoding="utf-8")
        subprocess.run(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--headless", "--disable-gpu",
                        "--no-pdf-header-footer", f"--print-to-pdf={pdf}", f"file://{h}"], capture_output=True, timeout=180, check=True)
    print("pdf:", pdf.name, pdf.stat().st_size)
    # oudere versies naar het archief: verplaatsen, nooit verwijderen of overschrijven
    for oud in sorted(UIT.glob(f"{cd['naam']} v*.pdf")):
        if oud != pdf:
            doel = ARCHIEF / oud.name
            if doel.exists():
                print("al in het archief, blijft staan:", oud.name)
            else:
                ARCHIEF.mkdir(parents=True, exist_ok=True)
                oud.rename(doel)
                print("naar het archief:", oud.name)


if __name__ == "__main__":
    main()

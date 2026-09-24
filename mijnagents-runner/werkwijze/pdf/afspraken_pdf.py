#!/usr/bin/env python3
"""Agendawacht - afspraken kleuren en taken (definitief, v2.0 sinds 24-09-2026).

Draait op de Mac (Chrome maakt de PDF) en leest rechtstreeks uit de repo, zodat de PDF nooit
afwijkt van het systeem. Uitvoer: Dropbox 'private/0 Chegini Mehdi/Prive met Claude'.
Alleen de regels zoals ze nu gelden, geen verloop per dag: dat staat in git en in het foutenregister.
Nieuwe versie: VERSIE hieronder ophogen.
"""
import html
import json
import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]
UIT = pathlib.Path.home() / "TKN-buro Dropbox/private/0 Chegini Mehdi/Prive met Claude"
t = json.loads((REPO / "werkwijze/agenda-taken.json").read_text(encoding="utf-8"))
reg = json.loads((REPO / "werkwijze/foutenregister.json").read_text(encoding="utf-8"))
# de firmacodes live van organisatie.globaal.be, via de agent op de VM
snap = json.loads(subprocess.run(["ssh", "globaal", "~/agents/.venv/bin/python", "-"],
                                 stdin=open(pathlib.Path(__file__).with_name("momentopname.py")),
                                 capture_output=True, text=True, timeout=180, check=True).stdout)
assert t["versie"] == "4.1", t["versie"]
VERSIE = "2.1"
NAAM = f"Agendawacht - afspraken kleuren en taken v{VERSIE}"
e = html.escape


def su(x):
    """Nooit de volledige landnaam van SU tonen (regel van Mehdi)."""
    return x.replace("Suriname", "SU").replace("suriname", "SU")


KL = {"11": ("#d50000", "tomaat, rood"), "4": ("#e67c73", "flamingo, roze"), "6": ("#f4511e", "mandarijn, oranje"),
      "5": ("#f6bf26", "banaan, geel"), "2": ("#33b679", "salie"), "10": ("#0b8043", "basilicum, groen"),
      "7": ("#039be5", "pauw, blauw"), "1": ("#7986cb", "lavendel"), "3": ("#8e24aa", "druif, paars"),
      "zwart": ("#000000", "zwart")}


def bol(k):
    return f"<span class=bol style='background:{KL[k][0]}'></span>"


KLEUREN = [
    ("4", "Agenda Lara", "Altijd roze, de kleur van de agenda. Ook buiten, ook de ritten."),
    ("zwart", "Privé-agenda", "Altijd zwart, de kleur van de agenda. Ook buiten, ook de ritten."),
    ("11", "Werk buiten", "!!, een dienst die per definitie buiten is (WB, OPL, PLB, SCN, OPM, BS), of soort KB, PB, LB of AB. En de rit ervoor en erna."),
    ("5", "Nog niet bevestigd", "?? in de titel. Gaat voor alles behalve Lara, privé en ritten."),
    ("7", "Klant online", "KO"),
    ("6", "Prospect online", "PO"),
    ("3", "Leverancier online", "LO: wij kopen, geld dat buitengaat"),
    ("1", "B2B", "professioneel extern, wij zijn nog geen klant"),
    ("2", "Aannemer online", "AO: de aannemer van een klant"),
    ("10", "Intern", "IN"),
]
kl = "".join(f"<tr><td class=c>{bol(k)}</td><td><b>{e(n)}</b></td><td>{e(w)}</td><td class=kl>{e(KL[k][1])}</td></tr>"
             for k, n, w in KLEUREN)

wa = "".join(f"<tr><td><b>{e(w['naam'])}</b></td><td class=kl>{e(w['bestand'])}</td><td class=kl>{e(w['wanneer'])}</td>"
             f"<td>{e(w['wat'])}" + (f"<div class=kl>{e(w['grenzen'])}</div>" if w.get('grenzen') else "")
             + (f"<div class=kl>Ontbreekt nog: {e(w['ontbreekt'])}</div>" if w.get('ontbreekt') else "") + "</td></tr>"
             for w in t["wachten"])
ag = "".join(f"<tr><td><b>{e(a['naam'])}</b></td><td class=c>{e(a['rol'])}</td><td>{e(a['waarover'])}</td>"
             f"<td class=kl>{e(a.get('wie_schrijft', ''))}</td></tr>" for a in t["agendas"])
_fl = [(k, su(v)) for k, v in sorted(snap["firmacodes"].items())]
_fl += [(k, "Algemeen, voor de hele groep") for k in snap["externe_firmas"]]
_h = (len(_fl) + 1) // 2
fi = "".join(f"<tr><td class=c style='width:12mm'><b>{e(a[0])}</b></td><td>{e(a[1])}</td>"
             + (f"<td class=c style='width:12mm'><b>{e(b[0])}</b></td><td>{e(b[1])}</td>" if b else "<td></td><td></td>") + "</tr>"
             for a, b in zip(_fl[:_h], _fl[_h:] + [None]))
so = "".join(f"<tr><td class=c><b>{e(k)}</b></td><td>{e(v)}</td></tr>" for k, v in t["titelconventie"]["soorten"].items())
ty = "".join(f"<tr><td class=c><b>{e(k)}</b></td><td>{e(v)}</td></tr>" for k, v in t["titelconventie"]["types"].items())
ou = ", ".join(f"<code>{e(k)}</code> = <code>{e(v)}</code>" for k, v in t["titelconventie"]["oude_codes"].items())
tk = "".join(f"<tr><td class=nr>{x['nr']}</td><td><b>{e(x['naam'])}</b></td><td>{e(x['wat'])}</td></tr>" for x in t["taken"])
op = "".join(f"<tr><td>{e(su(x['wat']))}</td><td class=c>{e(x['wie'])}</td><td class=c>{e(x['wanneer'])}</td><td class=vak></td></tr>"
             for x in t["openstaand"])
bu = "".join(f"<tr><td><b>{e(x['agent'])}</b></td><td class=kl>{e(x['wanneer'])}</td><td>{e(x['wat'])}</td><td>{e(x['afspraak'])}</td></tr>"
             for x in t["buren"])
tel = {s: sum(1 for f in reg["fouten"] if f["status"] == s) for s in reg["statussen"]}

HTML = f"""<!doctype html><html lang=nl><meta charset=utf-8><title>{NAAM}</title>
<style>
@page{{size:A4;margin:14mm}}
body{{font:9.7pt/1.45 -apple-system,"Helvetica Neue",Arial,sans-serif;color:#14181f}}
h1{{font-size:17pt;margin:0 0 2mm}} h2{{font-size:11.8pt;margin:7mm 0 2mm;border-bottom:1.5px solid #14181f;padding-bottom:1mm;break-after:avoid}}
h3{{font-size:10pt;margin:4mm 0 1.5mm;break-after:avoid}}
p{{margin:0 0 2.6mm}} ul{{margin:0 0 3mm;padding-left:5mm}} li{{margin-bottom:1.2mm}}
code{{font:8.6pt ui-monospace,Menlo,monospace;background:#eef1f5;padding:.3mm 1.2mm}}
table{{border-collapse:collapse;width:100%;font-size:8.7pt;margin-bottom:3mm}}
th{{text-align:left;border-bottom:1px solid #14181f;padding:1.3mm 2mm}}
td{{border-bottom:.4px solid #d6dae1;padding:1.4mm 2mm;vertical-align:top}}
tr{{break-inside:avoid}}
.nr{{text-align:center;font-weight:700;width:7mm}} .c{{text-align:center;white-space:nowrap}}
.kl{{color:#5d6673;font-size:7.9pt}} .vak{{width:20mm;border-left:.4px solid #d6dae1;background:#fafbfc}}
.bol{{display:inline-block;width:4.4mm;height:4.4mm;border-radius:50%;border:.4px solid #9aa3b0;vertical-align:middle}}
.kader{{border:1px solid #14181f;padding:3mm 4mm;margin:0 0 4mm;background:#f7f8fa}}
.top{{color:#5d6673;font-size:8pt;margin-bottom:3mm}}
.regel{{border-left:3px solid #14181f;padding:1mm 0 1mm 3mm;margin:0 0 3mm}}
.twee{{column-count:2;column-gap:7mm}} .twee table{{break-inside:avoid}}
</style>
<div class=top>Voor Mehdi Chegini &nbsp;|&nbsp; 24 september 2026 &nbsp;|&nbsp; versie {VERSIE}, <b>definitief</b> &nbsp;|&nbsp;
bron: werkwijze/agenda-taken.json v{t['versie']} en werkwijze v7.0 op de server</div>
<h1>De Agendawacht: afspraken, kleuren en taken</h1>

<div class=kader>
Dit document zegt hoe de Agendawacht nu werkt. Het vervangt versie 2.0, 1.7 en het voorlopige blad 'nieuwe afspraken' (0.5 tot 0.16).
Wat hier staat, staat ook in <code>werkwijze/agenda-taken.json</code> op de server. De test <code>tests/test_agenda_taken.py</code>
vergelijkt dat bestand met de code en faalt zodra ze uit elkaar lopen. Firma's en mensen komen live van
<b>organisatie.globaal.be</b>; de agent houdt er geen eigen lijst van bij.<br><br>
Hoe de regels zo gegroeid zijn, staat niet hier. De fouten, waarom ze niet eerder gezien werden en wat ze nu tegenhoudt,
staan in een apart document: <b>Agendawacht - foutenregister v1.0</b>.
</div>

<h2>1. De grondregels</h2>
<div class=regel><b>Bij twijfel vraagt hij, hij gokt nooit.</b> Ontbreekt een adres, een firma of een rijtijd, dan meldt hij het.
Hij vult een gat nooit op met een aanname. Maar eerst meet hij de bron: wat de agenda, de projectmap of organisatie.globaal.be
al zegt, vraagt hij niet.</div>
<ul>
<li><b>Hij verplaatst, verwijdert en hernoemt nooit een afspraak.</b> Hij zet kleuren, meldingen en zijn eigen ritten; een eigen
rit verhuist mee met zijn afspraak. Een titel zet hij
alleen recht bij een afspraak van Mehdi zelf, zonder gasten, uit zijn eigen vrije tekst; anders doet hij een voorstel.</li>
<li><b>Gasten krijgen nooit een mail</b> omdat de agent iets bijzet.</li>
<li><b>Wat een mens zette, blijft staan.</b> Een melding die iemand koos, en een kleur die iemand met de hand zette.
Past het niet bij de titel, dan vraagt hij of het bewust is.</li>
<li><b>Een grendel gaat nooit open</b>, ook niet even voor een proef. Proefrondes draaien droog.</li>
<li><b>SU.</b> Klanten en prospecten zien nooit de volledige landnaam; alleen SU of de code HDSS.</li>
<li><b>Het verleden wordt niet herschreven</b>, wel nagekeken. Een fout van gisteren komt in het register.</li>
</ul>

<h2>2. De wachten, en wanneer ze draaien</h2>
<p>Alle tijden zijn <b>Brusselse tijd</b>, in de zomer en in de winter. De server draait op UTC. Cron start de scripts
daarom vaker, en elk script beslist zelf of het zijn beurt is. Elke ronde begint in het logboek met haar tijdstip.</p>
<table><thead><tr><th style="width:24mm">Wacht</th><th style="width:28mm">Bestand</th><th style="width:40mm">Wanneer</th><th>Wat</th></tr></thead>
<tbody>{wa}</tbody></table>
<p><b>Bellen.</b> {e(t['bellen']['kanaal'])}. {e(t['bellen']['wanneer_nu'][0].upper() + t['bellen']['wanneer_nu'][1:])}.
De filewacht belt extra zodra de file de buffer van {t['bellen']['buffer_minuten']} minuten opeet.</p>

<h2>3. De agenda's die hij leest</h2>
<table><thead><tr><th style="width:34mm">Agenda</th><th>Rol</th><th>Waarover</th><th style="width:40mm">Wie schrijft</th></tr></thead>
<tbody>{ag}</tbody></table>

<h2>4. De titel</h2>
<p><b>Archiefagenda's.</b> Een agenda die op ZZ ARCHIEF staat, leest de agent mee maar beschrijft hij nooit. Een komende afspraak daar komt
in het dagplan, het belrooster en de botsingen, en als signaal: hoort op werk.</p>
<p>De vorm: <code>{e(t['titelconventie']['vorm'])}</code><br>Voorbeeld: <code>{e(t['titelconventie']['voorbeeld'])}</code></p>
<h3>De tekens vooraan</h3>
<table><tbody>
<tr><td class=c style="width:14mm"><b>ZL</b></td><td><b>Zonder link.</b> Een online gesprek met een externe partij zonder link. ZL staat
<b>helemaal vooraan</b>, voor ?? en voor alles: <code>ZL ?? Mehdi en Shaniel: [ELEV-LO] Robby</code>. De agent zet er de notitie
'Online. Mehdi stuurt de link naar ...' bij. Staat er later een link, dan gaan ZL en de notitie er weer af. <b>De agent zet zelf nooit
een link.</b> Niet bij bellen, Calendly-boekingen, intern overleg of terugkerende overleggen.</td></tr>
<tr><td class=c><b>!!</b></td><td><b>Buiten</b>, op het adres van de afspraak. Er komt een rit voor en na.</td></tr>
<tr><td class=c><b>??</b></td><td><b>Nog niet bevestigd.</b> Geel. Is de afspraak voorbij en staat ?? er nog, dan vraagt de agent of ze
doorging.</td></tr></tbody></table>
<table class=naast><tr><td style="width:50%;padding:0 4mm 0 0;border:0"><h3>De soorten</h3><table><tbody>{so}</tbody></table></td>
<td style="width:50%;padding:0 0 0 4mm;border:0"><h3>De diensten (type)</h3><table><tbody>{ty}</tbody></table></td></tr></table>
<p class=kl>De eerste letter van een soort zegt wie het is (klant, prospect, leverancier, aannemer), de tweede waar: buiten of online.
Een leverancier (LB/LO): daar zijn wij al klant. B2B: een professionele partij waar wij nog geen klant van zijn.
Een aannemer (AB/AO): de aannemer van een klant.</p>
<h3>De firmacodes</h3>
<p>Vier letters, van organisatie.globaal.be. Daar kijkt de agent, live. Stand op 24 september 2026:</p>
<table><tbody>{fi}</tbody></table>
<ul>
<li><b>ALGE</b> is voor een leverancier of afspraak die voor de hele groep geldt, niet voor een firma. Externe partijen staan
bewust niet op het dashboard maar in <code>externe-relaties.json</code>: de boekhouder Nadien (ook geschreven Nadine) en Wally
(AI-software), allebei leverancier, allebei ALGE.</li>
<li><b>HDS is HDSS.</b> HDSI is momenteel niet actief.</li>
<li><b>Vanaf 21 september 2026</b> draagt elke nieuwe afspraak de code van vier letters. Oudere afspraken houden hun oude code
en blijven geldig; de agent vertaalt: {ou}.</li>
<li><b>Vrije tekst wordt een code.</b> Mehdi typt bijvoorbeeld <code>!! Mehdi &amp; Catalin: Harchitects-KB 2505</code>; de agent maakt er
<code>!! Mehdi &amp; Catalin: [HARC-KB] 2505</code> van. Alleen bij zijn eigen afspraken zonder gasten, en alleen als firma en soort
eenduidig zijn. Anders een voorstel.</li>
<li><b>Geen firmacode:</b> de agent stelt er een voor. Een projectnummer uit de H-Architects-projectmap wordt HARC; een leverancier uit
de lijst wordt ALGE; anders de firma waarvoor de genoemde mensen werken ('diensten voor').</li>
<li><b>Een titel met een projectnummer is pas volledig met de klant en, buiten, het adres</b>:
<code>!! Mehdi &amp; Catalin: [HARC-KB] 2505 - Norma Gleeson, Aarschotsesteenweg 252, 3012 Wilsele</code>. De klant komt uit Pipedrive (de persoon van
de deal), het adres uit de agenda of de projectmap. Zonder gasten vult de agent het zelf aan, ook als een collega de afspraak zette; met
gasten, van Calendly of in een reeks doet hij een voorstel.</li>
<li><b>Een firmacode zonder soort</b> ('[HARC] Rechtbank') wordt gemeld. Een gemeente of rechtbank past nog in geen soort; dat staat open.</li>
</ul>

<h2>5. Kleuren</h2>
<p>De kleur zegt waarvóór Mehdi ergens is, de twee uitroeptekens zeggen dát hij naar buiten gaat. Van boven naar onder: de eerste
regel die past, wint.</p>
<table><thead><tr><th style="width:9mm"></th><th style="width:36mm">Wat</th><th>Wanneer</th><th style="width:30mm">Google</th></tr></thead>
<tbody>{kl}</tbody></table>
<ul>
<li>Een afspraak op de werkagenda zonder firmacode krijgt geen kleur: dat is een fout, en die wordt gemeld.</li>
<li><b>Een kleur die een mens zette, blijft staan.</b> Bij elke kleur die de agent zet, laat hij een onzichtbaar merk achter. Een kleur
zonder zijn merk komt van een mens; dan vraagt hij of het bewust is. Is het bewust, dan hoort de titel mee te veranderen.</li>
</ul>

<h2>6. Waar een afspraak plaatsvindt</h2>
<ul>
<li><b>Met !!</b> is buiten, op haar adres. <b>Zonder !!</b> is achter een bureau: thuis, op kantoor of in de auto.</li>
<li><b>Mehdi heeft een volwaardig bureau in zijn auto</b>: wifi, verlichting, camera, stuurtafel, koptelefoon. Een online afspraak hoeft
dus niet thuis. Klaarzitten in de auto kost vijf minuten.</li>
<li><b>Een intern overleg mag rijdend; een extern gesprek alleen geparkeerd.</b> Valt een extern gesprek tijdens de heenrit, dan komt
Mehdi aan voor het begint en doet hij het geparkeerd ter plaatse. Op de terugweg vertrekt hij pas na het gesprek.</li>
<li>Zit de andere persoon in een ander land, dan is het per definitie online.</li>
</ul>

<h2>7. Reistijd</h2>
<ul>
<li><b>Elke buitenafspraak krijgt een rit ervoor en erna</b>, met het autootje: <code>🚗 Reistijd: van → naar</code>. Thuis heet thuis;
in dezelfde gemeente de straat.</li>
<li><b>Een rit staat op dezelfde agenda en in dezelfde kleur als zijn afspraak.</b> Een rit voor Lara is roze op de agenda van Lara, een
privérit zwart op privé. Alleen werk is rood. Verhuist de afspraak naar een andere agenda, dan verhuist de rit mee; krijgt ze een
andere titel, dan volgt de rit.</li>
<li><b>Het uur is het uur van aankomst.</b> De rit ligt voor de afspraak, nooit erin.</li>
<li><b>Een keten per dag.</b> Van thuis, of van de vorige buitenafspraak. Naar huis na de laatste buitenafspraak, als er al een rit naar
huis staat, of als er tussen twee buitenafspraken iets achter het bureau staat: dan rekent de agent dat Mehdi naar huis gaat en vraagt
hij of het klopt.</li>
<li><b>Nooit vertrekken voor de vorige afspraak gedaan is.</b> Past de rit niet, dan toont hij de echte rijtijd en dus de late aankomst,
en komt <b>'Te krap: je komt te laat'</b> op het bord.</li>
<li><b>Een rit hoort bij precies één afspraak.</b> Een rit die iemand met de hand zette ('Rijden naar huis') telt mee.
'naar huis' in een titel is een rit, en <b>elke rit draagt het autootje</b>, ook een handmatige.</li>
<li><b>Het adres</b>: eerst de agenda, dan de projectmap (het projectnummer), dan de benoemde plekken uit locatie.globaal.be. Thuis komt
nooit uit een titel. Komt het adres uit de projectmap, dan zet de agent het ook in de afspraak. Geen adres: geen rit, wel een melding.</li>
<li><b>Rijtijd.</b> Google met het echte verkeer, alleen voor ritten binnen 48 uur; verder vooruit de gratis routeplanner maal een
spitsfactor. Plus {snap['buffer']} minuten buffer, naar boven afgerond op vijf. Een schatting overschrijft nooit een echte meting.
<b>Google heeft een hard plafond van {snap['plafond']} aanvragen per dag</b>; dat gaat alleen omhoog in de code.</li>
<li>Werkafspraken krijgen hun rit acht dagen vooruit; de agenda van Lara het hele schooljaar.</li>
</ul>

<h2>8. Lara</h2>
<table><tbody>
<tr><td style="width:30mm"><b>Maandag en vrijdag</b></td><td>16:00 ophalen op De Speelkriebel (Jozef Pierrestraat 104, 3010 Kessel-Lo) en thuis
afzetten. Rit 15:45 heen, 17:00 terug.</td></tr>
<tr><td><b>Dinsdag</b></td><td>17:10 rit naar oma (Wilselsesteenweg 57), 17:30 tot 17:40 ophalen bij oma, 17:40 rit naar het zwembad
(Stadionlaan 4), 18:00 tot 19:00 zwemles, 19:00 tot 19:30 <code>🚗 Reistijd: Stadionlaan 4 → thuis (Lara naar huis brengen)</code>: de rit naar
huis, tot 19:30 geblokkeerd zodat er tijd is om Lara van de les naar huis te brengen, zonder melding.</td></tr>
<tr><td><b>Donderdag</b></td><td>17:45 Lara ophalen bij oma en thuis afzetten, <b>optioneel</b>: als Mehdi kan. Zo afgesproken met Leen.</td></tr>
<tr><td><b>Maandag, werf</b></td><td>Na het wekelijkse werfbezoek 2145 (09:30 tot 11:30) gaat Mehdi naar huis.</td></tr>
<tr><td><b>Schoolvakantie en feestdag</b></td><td>Geen ophaling, geen rit, en ook geen marker 'Geen buiten afspraken Lara ophalen': die dag
mogen collega's juist wel buiten plannen. De agent leest de vakanties uit de agenda van Lara.</td></tr>
<tr><td><b>Per schooljaar</b></td><td>De reeksen lopen per schooljaar. Na elk schooljaar worden ze bijgesteld.</td></tr>
</tbody></table>

<h2>9. Hele-dag markers, geen auto, en wie buiten inplant</h2>
<ul>
<li><b>Een hele-dag marker is een signaal aan de collega's</b>, geen afspraak: geen kleur, geen melding, geen rit, geen titelfout.
'!! Mehdi: Geen buiten afspraken Lara ophalen' (agenda Lara) zegt: die dag geen verre buitenafspraken plannen.</li>
<li><b>Geen auto.</b> Mehdi of Chilton zet een hele-dag marker met 'geen auto' op de werkagenda. De agent maakt die dag geen rit en meldt
een buitenafspraak die er toch staat, met wie ze zette.</li>
<li><b>Buitenafspraken en werfbezoeken worden met de hand ingepland</b>, door Mehdi of Chilton. Calendly boekt alleen online.</li>
<li><b>Wie een afspraak maakte</b>, leest de agent uit Google. Een Calendly-boeking herkent hij aan de Calendly-links in de omschrijving,
niet aan het account. Een persoon zoekt hij op in organisatie.globaal.be.</li>
</ul>

<h2>10. Meldingen</h2>
<table><tbody>
<tr><td style="width:44mm"><b>Wie een melding krijgt</b></td><td>Elke afspraak met iemand van buiten: klant, prospect, leverancier, B2B, aannemer.
Ook terugkerend. Niet: intern, hele dag.</td></tr>
<tr><td><b>Online</b></td><td>5 minuten vooraf.</td></tr>
<tr><td><b>Buiten</b></td><td>Op het vertrekmoment plus 5 minuten, uit de echte rijtijd. Kan de rijtijd niet berekend worden, dan is dat een melding
op het bord.</td></tr>
<tr><td><b>Ritten</b></td><td>Heen 5 minuten vooraf, naar huis stil. Ook voor een rit die iemand met de hand zette.</td></tr>
<tr><td><b>Stil</b></td><td>Stil is echt stil: expliciet geen melding, niet de standaard van de agenda (die is op werk 30 minuten, op Lara 10).</td></tr>
<tr><td><b>Van een mens</b></td><td>Een melding die iemand zelf koos, blijft staan.</td></tr>
<tr><td><b>Bellen</b></td><td>De Bode belt volgens het belrooster: online 5 minuten vooraf, buiten op het vertrekmoment.</td></tr>
</tbody></table>

<h2>11. Wat hij op het bord zet</h2>
<p>Het dagplan en, telkens met de afspraak erbij: titels zonder code of zonder soort (met een voorstel), buitenafspraken zonder adres of zonder
rit, te krap, botsingen, kleuren die iemand met de hand zette, afspraken die voorbij zijn met ??, ritten zonder afspraak, en een
buitenafspraak op een dag zonder auto. Wat hij zelf niet kan oplossen, komt als nood.</p>
<table><thead><tr><th style="width:7mm">#</th><th style="width:30mm">Taak</th><th>Wat</th></tr></thead><tbody>{tk}</tbody></table>

<h2>12. Leren van fouten</h2>
<p>Elke fout komt in het <b>foutenregister</b> (<code>werkwijze/foutenregister.json</code>, aparte PDF): wat er gebeurde, waarom het niet eerder
gezien werd, de oorzaak, de oplossing en de grendel die het voortaan tegenhoudt. Eerst registreren, dan oplossen. Nu:
{len(reg['fouten'])} fouten, {tel['opgelost']} opgelost, {tel['bewaakt']} bewaakt, {tel['open']} open en {tel['vraag']} met een vraag aan Mehdi.</p>
<p>Elke werkdag om 07:00 kijkt de <b>zelfcontrole</b> in de agenda zelf of klopt wat de agent beweert, van zeven dagen terug tot zeven
dagen vooruit. Komt een opgeloste fout terug, dan staat TERUGGEKEERD bovenaan op het bord: dan werkt de grendel niet.</p>

<h2>13. Zijn buren</h2>
<table><thead><tr><th style="width:26mm">Agent</th><th style="width:30mm">Wanneer</th><th>Wat</th><th>Afspraak</th></tr></thead><tbody>{bu}</tbody></table>

<h2>14. Wat nog openstaat</h2>
<table><thead><tr><th>Wat</th><th style="width:22mm">Wie</th><th style="width:24mm">Wanneer</th><th style="width:20mm">Gedaan</th></tr></thead>
<tbody>{op}</tbody></table>
</html>"""
assert "Surinam" not in HTML, "de volledige landnaam staat in de PDF"
h = pathlib.Path("/tmp/agendawacht-afspraken.html")
h.write_text(HTML, encoding="utf-8")
pdf = UIT / f"{NAAM}.pdf"
subprocess.run(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--headless", "--disable-gpu",
                "--no-pdf-header-footer", f"--print-to-pdf={pdf}", f"file://{h}"], capture_output=True, timeout=180, check=True)
print("pdf:", pdf.name, pdf.stat().st_size)

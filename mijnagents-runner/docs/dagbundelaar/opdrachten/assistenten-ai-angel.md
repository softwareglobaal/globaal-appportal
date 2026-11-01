# Opdrachtkaarten: de zes assistenten van Ai Angel

Versie 1.0, 01-11-2026 (T-0120, Tranche A). Ingevuld uit de meting van 01-10 tot 01-11 (`assistenten.json` van de
meetronde) en de besluiten van het driehoeksoverleg (X3, X5, X8, X9). Geen echte namen: personen heten hier naar hun
rol, voorbeelden zijn verzonnen.

De vorm is de opdrachtkaart van elf vragen uit de Werkafspraken Claude en Codex (punt 4a) en AGENTNORM.md hoofdstuk 8:
Mehdi geeft het doel en de grenzen, niet de stappen. Wat hij nog niet besliste, staat er als **open (Mehdi)**; dat
vraagt een agent nooit in een chat, het staat als wacht in de werkstand. Eerst kijken wat er al is: vijf van de zes
zijn een uitbreiding van een bestaande agent, en een is alleen een kaart.

| Assistent | Soort | Stand op 01-11-2026 |
|---|---|---|
| De Gespreksanalist | uitbreiding van De Archivaris (versie 3) | gebouwd en getest op tak `t0120-gespreksanalist`, beide vlaggen uit, proef niet gedraaid |
| De Opvolger | geen nieuwe agent: een weg naar de dagbundel | kaart; de bronnen bestaan |
| De Doorgever | uitbreiding van Ai Angel (M10) | kaart; ANGEL-9 bij de groep mehdi-agent |
| De Conceptbezorger | alleen kaart, geen code | kaart; elke stap is een handeling in Mehdi's naam |
| WhatsApp werk en opvolging | uitbreiding van De WhatsApp-wacht | kaart; hangt aan VOL-7 en de keuze CB-2 met WA-4 |
| Fotowacht-indeling | uitbreiding van De Fotowacht | kaart |

Grenzen voor alle zes: nooit versturen, wissen of verplaatsen; alleen het Claude-abonnement van Mehdi, nooit de API;
privé blijft bij Mehdi en draagt geen naam; geen naam in titels, werkverslag of git; nooit berichttekst van WhatsApp,
sms of iMessage lezen of bewaren (X8); niets nieuws in Dropbox (de uitvoer staat op de VM).

---

## 1. De Gespreksanalist

Uitbreiding van De Archivaris (versie 3), code `gespreksanalist.py`, proef `gespreksanalist_proef.py`, werkwijze
`werkwijze/archivaris.md` (sectie Versie 3).

1. **Welk probleem?** Ai Angel weet niet wat er in gesprekken werd afgesproken: de dagbundel draagt per gesprek alleen
   tijd, bron, minuten en met wie; samenvatting en actiepunten bestaan nergens (afspraak P2 van T-0081 rekent erop).
2. **Voor welke firma of afdeling?** Alle firma's; het firmalabel van De Archivaris wordt firma en soort (VOL-5), het
   bewezen H-A-nummer of het enige nummer van de agendafirma wordt het dossier.
3. **Wat gebeurt er nu, en wat gaat mis?** De Archivaris las alleen de eerste 5.000 tekens voor een label, via de API.
   Fathom gaf zijn eigen samenvatting en actiepunten niet mee (FATHOM-1). Plaud en Zoom-tekst hebben geen samenvatting.
4. **Waar staat de juiste informatie?** Het volledige transcript: `fathom-data/<map>/transcript.json`,
   `plaud-invoer/<map>/transcript.json`, `zoom-data/<map>/transcript.json`; de gesprekkentabel `gesprek_log`; voor Fathom
   `samenvatting.md` en `actiepunten.md`.
5. **Wat is er al gemaakt?** De Archivaris (label, agenda, locatie, dossier), De Fathomwacht (ophalen), de koppeling
   `claude_abonnement` (abonnement zonder API-sleutel), de controle `bron_in` van Ai Angel als voorbeeld.
6. **Goed en verkeerd voorbeeld.** Goed: "plan naar de klant sturen, wie: de architect, tegen vrijdag, voor: klant,
   citaat: 'ik stuur het aangepaste plan vrijdag naar de klant'". Verkeerd: een actiepunt met een citaat dat niet
   letterlijk in het transcript staat, of een samenvatting van een privégesprek.
7. **Wat te zien, en waar?** Per gesprek twee zinnen en de actiepunten in `mijnagents-data/gespreksanalist/` op de VM;
   De Dagbundelaar zet ze later per dossier in de bundel, Ai Angel leest ze daar. Een privégesprek toont alleen
   "privégesprek, N min".
8. **Welke volgende stap?** Een actiepunt voor Mehdi wordt een taak in de lijst van Ai Angel; een punt voor een agent
   gaat via De Doorgever. Oude punten uit oktober komen als "na te kijken", nooit als open taak.
9. **Wat mag hij zelf, wat nooit?** Mag: transcripten van werkgesprekken lezen, samenvatten, actiepunten met citaat
   bewaren. Nooit: een privégesprek lezen of naar een model sturen; een actiepunt zonder letterlijk citaat; de API; een
   betaalde uitwijking; iets op het bord, in gesprek.json of in Dropbox.
10. **Welke beslissing blijft bij Mehdi?** Of Plaud en Zoom-tekst naar het model mogen, hoogstens vijf per nacht, nadat
    Extra usage uit staat (T-0122 keuze 1): **open (Mehdi)**. Of samenvattingen later in de Dropbox-kopie mogen:
    **open (Mehdi)**.
11. **Wanneer kijken of melden?** Elke ronde van De Archivaris; het model hoogstens vijf gesprekken per dag, nooit vanaf
    60 procent van het weekvenster. Een nood alleen bij een fout van het abonnement (de bestaande noden).

Eerste proef (X5): droog op zes gesprekken uit oktober: twee Fathom (een zonder actiepunt), twee Plaud, een Zoom-tekst en
een privégesprek dat alleen "privégesprek, N min" mag geven; uitvoer alleen een proefbestand (600) op de VM. Meten:
actiepunten, aandeel met letterlijk citaat (doel 100 procent), tokens, duur. Codex leest het resultaat.

## 2. De Opvolger (wie wacht op antwoord)

Geen nieuwe agent. De weg van De Mailregisseur, De Belwacht (iPhone), De Belwacht Xelion en De Communicatiebundelaar
naar de dagbundel (P7 van T-0081).

1. **Welk probleem?** Ai Angel weet niet wie op een antwoord of een terugbelactie van Mehdi wacht: in zijn lijsten komt 0
   taak uit mail, WhatsApp of telefoon.
2. **Voor welke firma of afdeling?** Alle werkpostvakken en werknummers; privé blijft "privé".
3. **Wat gebeurt er nu, en wat gaat mis?** De Mailregisseur kent de open mailpunten (`/api/mail/open`, al gebruikt door De
   Regisseur) en de belwachten de gemiste oproepen, maar niets daarvan bereikt de dagbundel.
4. **Waar staat de juiste informatie?** Het bord: `/api/mail/open`, `gesprek_log` (telefoon, xelion), de kanaalwachten.
5. **Wat is er al gemaakt?** De Mailregisseur, De Communicatiebundelaar, De Belwacht iPhone en De Belwacht Xelion.
6. **Goed en verkeerd voorbeeld.** Goed: "werkpostvak: 3 mails wachten langer dan 2 werkdagen op antwoord; 1 gemiste
   oproep van een werknummer zonder terugbellen". Verkeerd: de tekst van de mail of de naam bij een privénummer.
7. **Wat te zien, en waar?** Een blok "wacht op jou" in de dagbundel, per kanaal, dat Ai Angel als taak overneemt.
8. **Welke volgende stap?** Antwoorden of terugbellen als taak voor Mehdi, met een verwijzing naar de bron.
9. **Wat mag hij zelf, wat nooit?** Mag: tellen en verwijzen. Nooit: berichttekst lezen, iets versturen, een nieuwe agent.
10. **Welke beslissing blijft bij Mehdi?** Niets nieuws; berichttekst lezen blijft zijn keuze (T-0079 rij 6).
11. **Wanneer kijken of melden?** Bij elke bundel (ochtend en avond); geen eigen melding.

Eerste proef: alleen lezend tellen hoeveel open mailpunten en gemiste oproepen zonder terugbellen er op een werkdag
waren, tegen wat het dagbestand van die dag toont (nu 0).

## 3. De Doorgever (dispatchen versie 2, M10)

Uitbreiding van Ai Angel; herstelpunt ANGEL-9 (groep mehdi-agent).

1. **Welk probleem?** Een taak die bij een bestaande agent hoort, blijft bij Mehdi liggen: sinds 31-10 waren 2 van de
   ongeveer 10 taken voor een agent, en beide vervielen zonder doorgegeven te zijn (T-0082).
2. **Voor welke firma of afdeling?** Alle; de ontvanger hangt af van de soort taak, niet van de firma.
3. **Wat gebeurt er nu, en wat gaat mis?** Het voor-veld van Ai Angel bestaat, maar er gaat niets naar de ontvanger.
4. **Waar staat de juiste informatie?** De open taken van Ai Angel (staat.json), de agents op het bord en de
   klaarzet-status van de ontvanger.
5. **Wat is er al gemaakt?** De Werfverslag voorbereider en Het Commandocentrum zetten al zo een soort taak bij De
   Plaudwacht, De Agendawacht en De Fotowacht.
6. **Goed en verkeerd voorbeeld.** Goed: "afspraak plannen voor het plaatsbezoek gaat als voorstel naar De Agendawacht".
   Verkeerd: een privétaak doorgeven, of een vrije tekst als zoektaak naar De Plaudwacht.
7. **Wat te zien, en waar?** In de lijst van Ai Angel per taak "doorgegeven aan X" of "blijft bij jou: geen ontvanger".
8. **Welke volgende stap?** Na 3 dagen zonder beweging gaat de taak terug naar de lijst van Mehdi.
9. **Wat mag hij zelf, wat nooit?** Mag: naar een ontvanger op de witte lijst, alleen soorten die die ontvanger aanvaardt,
   hoogstens 5 per ronde, elke taak een keer. Nooit: privé, laten versturen, De Plaudwacht zolang ze vrije taken niet
   kan weigeren.
10. **Welke beslissing blijft bij Mehdi?** Per soort taak of Ai Angel ze zelf mag doorgeven, en naar wie: **open
    (Mehdi)**.
11. **Wanneer kijken of melden?** Bij elke ronde van Ai Angel; geen eigen melding.

Eerste proef: in `--droog` per open taak "zou naar X, soort Y" of "blijft bij Mehdi", zonder iets op het bord; daarna een
echte ontvanger: De Agendawacht, alleen als voorstel, op een werkdag.

## 4. De Conceptbezorger

Alleen deze kaart, geen code: een concept in Mehdi's postvak is een handeling in zijn naam.

1. **Welk probleem?** Ai Angel schrijft concepten (3 per lijst sinds 31-10), maar geen enkel staat klaar waar Mehdi het
   met een tik verstuurt.
2. **Voor welke firma of afdeling?** Alleen werkpostvakken; privé alleen voor Mehdi zelf.
3. **Wat gebeurt er nu, en wat gaat mis?** Het concept staat alleen in de lijst; Mehdi moet het zelf overnemen.
4. **Waar staat de juiste informatie?** De concepten in de lijst van Ai Angel en de mailbericht-tabel voor de draad.
5. **Wat is er al gemaakt?** De mailkoppeling "concept als antwoord" (T-0074), voorstellen met runbooks op het bord, en
   De Bode voor WhatsApp.
6. **Goed en verkeerd voorbeeld.** Goed: een concept-antwoord in de bestaande draad van een werkpostvak, als voorstel.
   Verkeerd: een nieuwe ontvanger, een bijlage, of een concept dat zonder klik in het postvak komt.
7. **Wat te zien, en waar?** Een voorstel op het bord met het runbook "concept opslaan als antwoord in postvak X".
8. **Welke volgende stap?** Na de klik van Mehdi het concept in de draad; daarna volgen of het verstuurd werd.
9. **Wat mag hij zelf, wat nooit?** Mag: een voorstel klaarzetten. Nooit: zelf versturen, een concept opslaan zonder
   klik, een bijlage, een ontvanger die niet in de draad staat.
10. **Welke beslissing blijft bij Mehdi?** Elk versturen; en of een concept zonder klik in zijn postvak mag: **open
    (Mehdi)**. Tot hij dat zegt, wordt er niets gebouwd.
11. **Wanneer kijken of melden?** Alleen als Ai Angel een concept maakt; geen eigen melding.

Eerste proef (pas na het ja van Mehdi): een concept van een werkdag als voorstel op het bord, niet uitgevoerd; Codex kijkt
of draad en postvak kloppen.

## 5. WhatsApp werk en opvolging

Uitbreiding van De WhatsApp-wacht. Hangt aan VOL-7 (een gegeven werk of privé en firma per contact, uit kern via De
Contactwacht) en de keuze CB-2 samen met WA-4.

1. **Welk probleem?** Ai Angel weet niet welke WhatsApp-gesprekken werk zijn en welke op een antwoord van Mehdi wachten.
2. **Voor welke firma of afdeling?** Alle firma's, per gesprek uit het projectregister en kern.
3. **Wat gebeurt er nu, en wat gaat mis?** Ai Angel leest zelf geen WhatsApp en De Communicatiebundelaar kent het kanaal
   niet. Sinds 01-10: 628 inkomende reeksen in persoonsgesprekken, waarvan 85 zonder uitgaand bericht binnen 24 uur.
4. **Waar staat de juiste informatie?** `gesprek_log` (rijen van De WhatsApp-wacht, alleen tijd en richting), het
   projectregister, kern (organisatie.globaal.be) via De Contactwacht.
5. **Wat is er al gemaakt?** De WhatsApp-wacht (tellen zonder tekst), De Contactwacht, het projectregister.
6. **Goed en verkeerd voorbeeld.** Goed: "werkgesprek van een project: laatste bericht inkomend, ouder dan 24 uur: wacht
   op jou". Verkeerd: een voorbeeldtekst van het bericht, of een privégesprek met een naam.
7. **Wat te zien, en waar?** Per bevestigd werkgesprek afdeling, firma en project, en de lijst "wacht op jou" op de
   wachtenpagina en in de dossierbundel.
8. **Welke volgende stap?** Een taak "antwoorden" voor Mehdi bij Ai Angel, met de verwijzing naar het gesprek.
9. **Wat mag hij zelf, wat nooit?** Mag: werk of privé voorstellen, tijd en richting tellen. Nooit: tekst, media of een
   voorbeeldtekst; iets versturen; privégesprekken anders dan als aantal.
10. **Welke beslissing blijft bij Mehdi?** Of werkgesprekken uit de privéregel mogen en of werkcontacten bij naam in het
    communicatie-item mogen (CB-2 met WA-4, een keuze in de werkstand); per voorgesteld gesprek werk of privé; later of
    foto's en bestanden uit werkgesprekken meekomen (WA-5): **open (Mehdi)**.
11. **Wanneer kijken of melden?** Bij elke ronde van De WhatsApp-wacht; geen eigen melding.

Eerste proef (na VOL-7 en de keuze): een week alleen lezend het voorstel werk of privé tonen voor de groepen met een
projectteken, en meten hoeveel voorstellen Mehdi juist vindt en hoeveel open gesprekken echt open waren.

## 6. Fotowacht-indeling

Uitbreiding van De Fotowacht.

1. **Welk probleem?** Projectfoto's komen niet met hun project op het Dagboek, en Ai Angel weet per bezoek niet welke
   foto's er zijn.
2. **Voor welke firma of afdeling?** Eerst H-Architects; welke firma's erbij komen: **open (Mehdi)**.
3. **Wat gebeurt er nu, en wat gaat mis?** Sinds 01-10: 1.369 foto's en video's, waarvan 360 binnen 150 m van een project
   of agendabezoek, 245 met vooral mensen en 216 schermafbeeldingen; ze worden niet ingedeeld.
4. **Waar staat de juiste informatie?** Photos.sqlite op de laptop (alleen metadata), de projectplekken en de context van
   De Locatiewacht, de afspraken van De Agendawacht.
5. **Wat is er al gemaakt?** De iCloud-wacht (metadata), De Locatiewacht (projectplekken, auto bij project), De
   Dagbundelaar (bronnen samen).
6. **Goed en verkeerd voorbeeld.** Goed: "werf zeker: 10 foto's bij het agendabezoek van een project, met link". Verkeerd:
   een foto met mensen of een privéplaats op de pagina.
7. **Wat te zien, en waar?** Per werfgroep een item met project en link op het Dagboek; werkkandidaten als vraag op het
   bord.
8. **Welke volgende stap?** Per werkkandidaat "dit was werk voor project X" of niet; daarna de originelen.
9. **Wat mag hij zelf, wat nooit?** Mag: indelen op metadata (werf zeker, werkkandidaat, mensen, privé, scherm). Nooit:
   een beeld lezen of tonen buiten werkfoto's, een gezicht herkennen, iets verplaatsen of wissen in Photos of Dropbox.
10. **Welke beslissing blijft bij Mehdi?** Per werkkandidaat werk of niet; welke firma's naast H-Architects meedoen:
    **open (Mehdi)**.
11. **Wanneer kijken of melden?** Bij elke ronde van De Fotowacht; geen eigen melding.

Eerste proef: met de metadata van drie opeenvolgende dagen alleen lezend; verwacht per dag het aantal werkfoto's dat de
meting gaf, en 0 privéplaatsen op de pagina.

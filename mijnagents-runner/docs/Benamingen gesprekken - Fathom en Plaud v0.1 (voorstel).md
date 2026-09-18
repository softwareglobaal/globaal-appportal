# Benamingen van gesprekken: Fathom en Plaud (v0.1, voorstel van 18-09-2026)

Eén regel voor elke gespreksmap, Fathom en Plaud tegelijk, zodat Mehdi geen naam meer met de
hand hoeft te maken. Wordt v1.0 zodra Mehdi de regel goedkeurt; dan komt hij als apart tabblad
op het dashboard als de referentie waar alles naar verwijst.

## De regel

    JJJJ-MM-DD UUMM FIRMA dossier - met wie - onderwerp

| Deel | Wat | Uniek? | Bron, in deze volgorde |
|---|---|---|---|
| `JJJJ-MM-DD UUMM` | start in Belgische tijd | ja, samen met de firma | Fathom of Plaud |
| `FIRMA` | de viertekencode van het Organisatie-dashboard (`kern.firma`) | ja | dossier, agenda, deelnemers, transcript |
| `dossier` | het dossier van die firma, zie hieronder | ja binnen de firma | transcript, agenda, Pipedrive |
| `met wie` | de gesprekspartner(s), voornaam en naam, hoogstens twee met `&` | nee | deelnemers, transcript, personentabel |
| `onderwerp` | waar het over ging, hoogstens 50 tekens, kleine letters | nee | transcript |

Scheiding: één spatie tussen tijd, firma en dossier; ` - ` (spatie, streepje, spatie) vóór met wie
en vóór onderwerp, zoals in A3 van de H-A-afspraken. Tekens die Dropbox niet in een naam wil
(`: / \ * ? " < > |`) worden een spatie. Langer dan 120 tekens wordt het onderwerp ingekort.

## De zeventien firma's (uit het Organisatie-dashboard, 18-09-2026)

| Code | Firma | | Code | Firma |
|---|---|---|---|---|
| BFUT | Build for Future | | HDSI | High Design Studio (India) |
| CONT | Contrax | | HDSS | High Design Studio (Suriname) |
| CORE | Corenbo | | MELO | Melodie |
| ELEV | Elevait NV | | ORVA | Orvantis |
| ENEF | Energie Efficiënt | | QOPP | Qoppa |
| ENST | ENSTACO | | TKNB | TKN-Buro |
| HARC | H-Architects | | UNAB | UnaBo |
| HARM | Harmoniebouw | | ZIDI | Zidi Construct |
| HINV | H-Invest | | | |

De codes bestaan al; er komen geen nieuwe afkortingen bij. Verandert er een in het dashboard, dan
verandert hij overal, want het script leest ze daar.

## Het dossier per firma

Het dossier is wat die firma zelf als dossier gebruikt, zodat de naam in de gespreksmap dezelfde is
als in Pipedrive en in de dossiermap:

| Firma | Dossier in de naam | Voorbeeld |
|---|---|---|
| HARC | projectnummer en klantnaam, zoals de deal en de salesmap (A13: 26xx architectuur, 56xx regularisatie) | `2612 Salima Zekhnini` |
| UNAB, TKNB | het adres, zoals de dealtitel | `Kapelseweg 155 Mechelen` |
| ENEF, HARM, CONT | de bedrijfsnaam van de klant, zoals de dealtitel | `Verbraecken & Co` |
| andere firma's | de klantnaam, of `intern` | `intern` |

**Sales zonder dossier (regel van Mehdi, 18-09-2026).** Is er nog geen nummer, dan is de naam van
de persoon het dossier, en die naam staat dan ook bij "met wie":
`2026-09-17 1403 UNAB Jessica Overtveldt - Jessica Overtveldt - plaatsing trap`.
Wordt Jessica klant en krijgt ze een nummer of adres, dan vervangt het script het eerste
voorkomen door dat nummer; de tweede blijft, want daar hebben we met haar gesproken. De oude naam
blijft altijd in `gesprek.json`.

**Intern en privé.** Een gesprek zonder klantdossier krijgt `intern` als dossier bij de firma waar
het over gaat (`ELEV intern - Shaniel - agent voor telefonie en Fathom`). Privé blijft `prive: true`
in `gesprek.json`; welke code een privégesprek in de naam krijgt, beslist Mehdi (voorstel: `PRIV`).

## Hoe het script aan de delen komt

1. **Het transcript zelf**: projectnummer, adres of klantnaam die genoemd wordt; wie er spreekt.
2. **De agenda op dat tijdstip** (Agendawacht, negen agenda's): een afspraak met code en nummer op
   de starttijd is de sterkste aanwijzing voor firma en dossier.
3. **Pipedrive** van die firma: deelnemer, e-mailadres of adres koppelt aan een deal.
4. **De Locatiewacht** (alleen Plaud): waar Mehdi stond toen hij opnam, dus welke werf.
5. **De personentabel en het Organisatie-dashboard**: een collega hoort bij een firma.
6. **De herkenning die De Fathomwacht al maakte** (288 gesprekken): personen, afdeling, project, thema.

Elke naam krijgt in `gesprek.json` een `benaming` met de delen, de bron per deel, de zekerheid en
de vorige naam. Bij twijfel over firma of dossier krijgt het gesprek wel een naam, maar komt het op
de twijfellijst `00 twijfel.md` in de map, zodat Mehdi alleen die hoeft na te kijken. Hernoemen is
omkeerbaar: de oude naam staat in de metadata.

## Voorbeelden uit het archief van 17-09-2026

| Nu | Wordt |
|---|---|
| `2026-09-17 1434 Impromptu Zoom Meeting` | `2026-09-17 1434 HARC 2145 Vertommensberg - Tom - stabiliteit balk in vloer` |
| `2026-09-17 1403 Mehdi [UNABO-PO] Alexander Symons - Stabiliteit` | `2026-09-17 1403 UNAB Alexander Symons - Alexander Symons - plaatsing trap` |
| `2026-09-16 2102 Gerrit Van Onsem HA Klant` | `2026-09-16 2102 HARC Gerrit Van Onsem - Gerrit Van Onsem - dakvenster en gevelafwerking` |
| `2026-09-17 1100 Impromptu Zoom Meeting` | `2026-09-17 1100 ELEV intern - Shaniel - agent voor telefonie en Fathom` |
| `2025-10-09 0807 2282 WB en Oplvering 2025-10-09 08 07 43` (Plaud) | `2025-10-09 0807 HARC 2282 - aannemer - werfbezoek en oplevering` |

## Wat Mehdi beslist vóór v1.0

1. Klopt de volgorde en de scheiding zoals hierboven?
2. Welke code voor privégesprekken: `PRIV`, of geen code en alleen de vlag?
3. Bij een dossier waar twee firma's aan werken (H-A-dossier, TKN doet de stabiliteit): de firma
   van het dossier (HARC), of de firma van het gesprek (TKNB)? Voorstel: van het dossier.
4. Waar het tabblad komt: op contracten.globaal.be naast Masterregels en Systeemkaart, of op het
   Organisatie-dashboard bij de firma's.

Daarna: eerst honderd gesprekken hernoemen als proef, Mehdi kijkt na, dan alle 3.021.

# Ontwerp — datamodel draaiboek-platform (v2, verfijnd met deep-research)

> **Status: TER REVIEW** (Shaniel/Mehdi) — v1-concept getoetst aan de deep-research
> van 2026-07-03 (Toolmaster, Monday, referentieklasse Process Street/Tallyfy/
> Pipefy, wettelijk kader veiligheidscoördinatie). Na akkoord: migratie + MVP
> volgens het vermogen-recept. Terminologie: `kern.definitie` (migratie 021).

## Wat de research bevestigde en veranderde

**Bevestigd (bouwen zoals gedacht):**
- **Sjabloon ↔ run-splitsing met bescherming tegen sjabloon-wijzigingen** — bij
  álle referentiespelers expliciet ("runs protected from template changes").
  Ons snapshot-model is precies dat.
- **Append-only audit-trail** per stap (wie/wanneer) — overal de kern van de waarde.
- **Fase-laag** — matcht bovendien exact de wettelijke structuur van
  veiligheidscoördinatie (ontwerpfase / verwezenlijkingsfase).
- **Relatieve deadlines per stap** (`termijn_dagen`) — standaardpatroon.

**Veranderd t.o.v. v1 (de research was hier beter):**
1. **Kickoff-formulier i.p.v. losse kenmerk-labels.** De referentieklasse stuurt
   adaptiviteit via een startformulier (bij VC: oppervlakte m², aantal aannemers,
   verhoogd risico art. 26…), waaruit régels de conditie-labels afleiden
   (≥ 500 m² → `groot_project`). Dat is objectiever dan handmatig labels
   aanvinken én de antwoorden zijn straks herbruikbaar voor documentgeneratie.
2. **Dossier als bovenliggende entiteit.** In v1 bewust weggelaten, maar de
   research toont dat één VC-dossier standaard twéé runs draagt (VC-ontwerp en
   VC-verwezenlijking) — het Toolmaster-dossiermodel + de twee wettelijke fases.
   Dus: een lícht `dossier` in het draaiboek-schema (naam, adres, firma), dat
   later opgaat in de kern-projectentiteit (TODO) zonder breuk.
3. **Stap-soorten**: taak / goedkeuring / document / mijlpaal. Goedkeuringsstappen
   zijn native bij alle referentiespelers en nodig voor VC (overdrachten,
   advies aan opdrachtgever).
4. **Statusset verruimd** naar open / bezig / klaar / overgeslagen ('geblokkeerd'
   is afgeleid uit afhankelijkheden, geen aparte status).
5. **Velden/waarden generiek (EAV-licht)**: velddefinities bij het sjabloon
   (kickoff) of bij een stap, waarden bij de run — het Pipefy-patroon
   (definitie op phase, waarde op card). Valkuil 3 uit de research: dit vanaf
   dag één, anders zit je vast bij het tweede draaiboek (EPB, keuring…).

**Bewust fase 2 (research zegt "beter doen", maar niet in het MVP-model):**
documentgeneratie (VGP/PID met conditionele blokken — dé Toolmaster-vervanger),
referentietabellen (standaard risicoanalyses), klantenportaal, dynamische
toewijzingsregels. De hooks zitten in het model (resultaat-verwijzing,
veld/waarde), de tabellen komen als het MVP staat.

## Het model

```
dossier ──┬─ run (VC-ontwerp) ────┬─ run_stap ─── run_stap_log (append-only)
          └─ run (VC-verwezenl.)  └─ veldwaarde (kickoff-antwoorden)

draaiboek ─┬─ fase ─┬─ stap (soort, volgorde, afhankelijkheid, conditie, termijn)
           ├─ veld (kickoff- en stapvelden)
           └─ conditie_regel (veld + operator + waarde → conditie-label)
```

Run-aanmaak = kickoff invullen → regels evalueren → labels bepalen → stappen
zonder matchende conditie worden niet meegekopieerd → run_stappen zijn snapshots.

## Tabellen (schema `draaiboek`)

### Sjabloon-kant (groep `draaiboek-editors`)

**`draaiboek`** — id, naam, omschrijving, proces_eigenaar_persoon_id → kern.persoon,
actief, bijgewerkt_op/door.

**`fase`** — id, draaiboek_id FK, naam, volgorde.

**`stap`** — id, fase_id FK, naam, omschrijving (de instructie), volgorde,
soort (`taak`/`goedkeuring`/`document`/`mijlpaal`), hangt_af_van_stap_id (nullable,
zelfverwijzend — één afhankelijkheid in v1), conditie (text, leeg = altijd),
resultaat (op te leveren, bv. "werfverslag"), rol_hint, termijn_dagen (nullable,
t.o.v. run-start), verplicht (boolean — overslaan vraagt notitie).

**`veld`** — id, draaiboek_id FK, stap_id (nullable: leeg = kickoff-veld), naam,
label, type (`tekst`/`getal`/`ja_nee`/`keuze`/`datum`), opties (text[], voor keuze),
verplicht, volgorde.

**`conditie_regel`** — id, draaiboek_id FK, veld_id FK, operator
(`>=`/`<=`/`=`/`bevat`), waarde (text), label (het conditie-label dat waar wordt,
bv. `groot_project`). Bij run-start geëvalueerd; labels sturen welke stappen meegaan.

### Run-kant (alle gebruikers)

**`dossier`** — id, naam, adres, firma_id → kern.firma, actief, aangemaakt_op/door.
*(Licht; gaat later op in de kern-projectentiteit — run krijgt dan een extra FK,
geen breuk.)*

**`run`** — id, dossier_id FK, draaiboek_id FK (afkomst), verantwoordelijke_persoon_id
→ kern.persoon, labels (text[] — de geëvalueerde condities, vastgelegd), status
(`lopend`/`afgerond`/`gestopt`), gestart_op, afgerond_op, aangemaakt_door.

**`run_stap`** — id, run_id FK, stap_id (nullable — afkomst/lineage),
fase_naam / naam / omschrijving / soort / resultaat (snapshot), volgorde,
hangt_af_van_run_stap_id (nullable), toegewezen_aan_persoon_id (nullable),
deadline (date, uit termijn_dagen of handmatig), status
(`open`/`bezig`/`klaar`/`overgeslagen`), resultaat_verwijzing (waar het opgeleverde
staat), notitie.

**`veldwaarde`** — id, run_id FK, veld_id FK, run_stap_id (nullable), waarde (text).
*(Kickoff-antwoorden + latere stap-invoer; brandstof voor condities nu en
documentgeneratie in fase 2.)*

**`run_stap_log`** — id, run_stap_id FK, status, door, op (default now()), notitie.
*(Append-only; alleen INSERT voor de schrijfrol — het finalisatie-patroon. Ook de
event-bron voor automatisering later.)*

## Rechten & integratie (bestaand patroon)

- DB-rol `draaiboek`: leest kern (+ definitie), schrijft eigen schema;
  `run_stap_log` alleen INSERT. `portal` leest mee.
- App: eigen repo `globaal-draaiboek`, subdomein, vermogen-recept (compose,
  nginx, Authentik-tegel, auto-deploy). Sjabloonbeheer = groep `draaiboek-editors`.
- Second Brain: dossiers/runs als knopen aan firma + verantwoordelijke; signalen
  "run X dagen stil", "stap over deadline", "run zonder verantwoordelijke".
- Fathom-koppeling later: kolom `run_stap_id` op `organisatie.meeting_actiepunt`.

## MVP-inhoud: veiligheidscoördinatie (uit de research, wettelijk kader KB 25/01/2001)

Kickoff-velden: oppervlakte (m²), aantal aannemers, verhoogd risico (art. 26 §1),
duur + aantal werknemers, mandagen, architect betrokken, bestemming.
Kern-regel: `oppervlakte >= 500` → label `groot_project` (afdeling III).

| Fase | Kern-stappen (samengevat) | Op te leveren |
|---|---|---|
| 0. Intake & aanstelling | overeenkomst; aanstelling VC-ontwerp (< 500 m² door architect, ≥ 500 m² door opdrachtgever); dossier openen | overeenkomst |
| 1. Ontwerp (VC-ontwerp) | plananalyse; risicoanalyse; VGP opstellen (volledig ↔ vereenvoudigd = conditie); PID openen; coördinatiedagboek openen (alleen `groot_project`); VGP in bestek; advies offertes; overdracht (= goedkeuringsstap) | VGP, geopend PID, (groot) dagboek |
| 2. Aanbesteding | aannemersdocumenten + prijsberekening preventie nazien; werfmelding (≥ 15 dagen vooraf, conditie grote werf) | werfmelding |
| 3. Verwezenlijking | aanstelling VC-verwezenlijking (vóór start werken!); VGP aanpassen; periodieke werfbezoeken → werfverslagen (herhalende stap); dagboek bijhouden; tekortkomingen melden; PID aanvullen; coördinatiestructuur (conditie: > 5000 mandagen / > €2,5 mln + ≥ 3 aannemers) | werfverslagen |
| 4. Oplevering | geactualiseerd VGP + dagboek + PID overdragen tegen ontvangstbewijs (goedkeuringsstap) | overdrachtsbewijs |

**Openstaand modelpunt** (bewust v2 van de app, niet van het schema): *herhalende
stappen* ("werfbezoek + verslag, telkens opnieuw"). MVP-aanpak: de stap dupliceren
in de run ("verslag 2 klaar → maak verslag 3 aan") — past in het model; een
nette herhaal-definitie op de sjabloon-stap kan later als kolom erbij.

## Valkuilen uit de research → hoe dit ontwerp ze vermijdt

1. *Slecht proces automatiseren* → het MVP-draaiboek wordt eerst met de echte
   coördinator (Ashwent) gevalideerd vóór de bouw van de app-flows.
2. *Te rigide sjablonen* → per run stappen kunnen toevoegen/overslaan (run_stap
   zonder stap_id = handmatig toegevoegd; overslaan = status + notitie), zonder
   het sjabloon te raken.
3. *Inflexibel datamodel* → veld/veldwaarde-patroon vanaf dag één; snapshots.
4. *Adoptie* → één proces als MVP, meetbare winst (VGP-tijd, geen gemiste stappen).
5. *Lock-in* → eigen Postgres is de bron; export is een SELECT. Monday hooguit
   als weergavelaag, nooit als engine (geen two-way sync, automation-caps).

## Beslispunten voor de review (Mehdi/Shaniel)

1. Akkoord met **dossier → meerdere runs** (VC-ontwerp + VC-verwezenlijking apart)?
2. Goedkeuringsstap-gedrag: volstaat "andere persoon dan de uitvoerder vinkt af"?
3. Documentgeneratie (VGP/PID — de Toolmaster-vervanger) bevestigen als **fase 2**?
4. Toolmaster-kostenclaim (~€70/gebruiker) is **onbevestigd** — vóór een
   vervangingsbeslissing een echte offerte vragen (met prijs p.g., setup,
   data-export). De businesscase voor zelf bouwen staat los daarvan sterk
   (30+ gebruikers, meerdere processen: EPB, keuring…).

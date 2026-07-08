# Ontwerp: meerdere kostregels per nummer + AI-kostenadviseur

> Status: GOEDGEKEURD door Shaniel (2026-07-07). Beslispunten beantwoord:
> (1) optie B nu, A later; (2) per-minuut-kostregels volwaardig zichtbaar,
> inclusief bedrag; (3) advieslijst on-demand in het dashboard; (4) de
> adviseur mag opzegtermijn en contracttype als harde blokkade gebruiken.
> Fase 1 (kostregels) gebouwd via migratie 053; fase 2a (regels-adviseur +
> advies_log, migratie 060) en fase 2b (AI-gewogen advies met één advies per
> nummer, exacte kostopbouw en regels-terugval) gebouwd op 2026-07-08.
> Bron: meeting Mehdi 2026-07-07 ("een nummer wordt twee keer berekend,
> een keer bij Proximus en een keer voor spoofing") en de beleidslijn
> kanalen afbouwen (de 99-auto's-analogie).

## 1. Probleem

Een nummer heeft vandaag een kostprijs (migratie 044: bedrag, prijstype,
peildatum). De werkelijkheid: een nummer kan bij meerdere partijen tegelijk
geld kosten. Mehdi's 0486 betaalt Proximus voor het abonnement en Xelion
(Close Call) voor de spoofing-dienst op datzelfde nummer. Met een enkel
kostveld is de totale kost per nummer en per leverancier niet te
controleren, en "niemand kan dat controleren" is precies wat we oplossen.

## 2. Ontwerp datamodel

Nieuwe tabel `communicatie.nummer_kost`:

| kolom          | type                        | betekenis                                    |
|----------------|-----------------------------|----------------------------------------------|
| id             | uuid PK                     |                                              |
| nummer_id      | uuid FK nummer, NOT NULL    | het nummer waar de kost op drukt             |
| leverancier_id | uuid FK kern.leverancier    | wie factureert (Proximus, Close Call, Mega)  |
| omschrijving   | text                        | wat het is: "abonnement", "spoofing", ...    |
| bedrag         | numeric                     | excl. BTW, van de laatste factuur            |
| prijs_type     | text                        | per maand / per minuut (zelfde waarden als nu)|
| peildatum      | date                        | factuurdatum; 2-maanden-waarschuwing geldt   |
| bijgewerkt_door/op | text/timestamptz        | zelfde spoor als nummer                      |

Principes die meegaan: kostprijs excl. BTW van de laatste factuur, de
factuur blijft de bron, peildatum-veroudering geeft het rode uitroepteken.

## 3. Migratiepad (beslispunt A)

- **Optie B (voorstel): vaste_prijs blijft de hoofdregel.** De bestaande
  kostprijs op het nummer blijft "het abonnement bij de eigen leverancier";
  kostregels zijn de extra diensten (spoofing bij Close Call). Minst
  breekwerk: views, exports en de leverancier-totalen blijven werken; de
  register-kolom Kostprijs toont de som met de uitsplitsing in de hover.
- **Optie A: alles wordt kostregel.** Schoner model (een nummer heeft n
  kostregels, punt), maar vraagt een backfill van elke bestaande kostprijs
  naar een regel en aanpassing van alle plekken die vaste_prijs lezen.
  Voorstel: pas doen bij de dropdown-only-slag van het register.

## 4. UI

- Detailpaneel: blok "Kosten" met een regel per kost (leverancier-dropdown,
  omschrijving, bedrag, prijstype, peildatum) en een plus-knop, zelfde
  patroon als de meerdere doelen. Hoofdkostprijs blijft waar hij staat.
- Register-kolom Kostprijs: toont het maandtotaal (som hoofdprijs + regels
  met prijstype per maand); hover toont de uitsplitsing per leverancier.
  Per-minuut-regels tellen niet mee in het totaal (bestaande regel).
- Leverancier-detail: telt naast de eigen nummers ook de kostregels mee in
  het maandtotaal, zodat "wat kost Close Call ons" klopt.

## 5. AI-kostenadviseur (fase 2, na de kostregels)

Aanpak in drie lagen, conform het meeting-gesprek (AI stelt voor, mens
accepteert):

1. **Feiten verzamelen (bestaat grotendeels):** per nummer de usage uit het
   90-dagen-archief (oproepen, minuten, laatste oproep), de totale kost uit
   de kostregels, status, doelen en gebruikt-voor.
2. **Regels-signalen (deterministisch, geen AI nodig):**
   - kost > 0 en nul usage in 90 dagen: afbouw-kandidaat;
   - dubbele dienst op een persoon (meerdere actieve persoonlijke nummers);
   - spoofing-kost zonder recent gebruik van de spoofing-richting;
   - prijs 2+ maanden niet bijgewerkt (bestaat al als waarschuwing).
   Geen usage is niet automatisch opzeggen: de andere factoren (doel
   WhatsApp/ItsMe/datasim, buitenland-gebruik, wettelijke of contractuele
   binding, opzegtermijn) wegen mee; die staan in het register.
3. **AI-advies met verantwoording:** de adviseur krijgt aggregaten (nooit
   ruwe gesprekslogs) plus de registercontext en formuleert per kandidaat
   een advies: afbouwen, behouden of navragen, met de redenering erbij en
   een geschatte besparing per maand. Weergave als lijst in het
   communicatie-dashboard met accepteer/afwijs-knoppen; elke beslissing
   wordt gelogd (wie, wanneer, waarom) zodat het beleid controleerbaar is.
   Later voeden Mehdi's meeting-transcripts de context ("hoe denkt Mehdi"),
   dat spoor is geparkeerd.

## 6. Beslispunten

1. Migratiepad: optie B nu en A later (voorstel), of direct A?
2. Tellen per-minuut-kostregels ergens mee (aparte weergave) of alleen tonen?
3. Adviseur-cadans: advieslijst on-demand in het dashboard (voorstel) of ook
   wekelijks in de briefing van de Organisatie-app?
4. Mag de adviseur opzegtermijn/contracttype als harde blokkade gebruiken
   (advies "kan pas per datum X")? Vereist dat die velden gevuld worden.

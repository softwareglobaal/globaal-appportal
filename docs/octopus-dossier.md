# Octopus-dossier - verwerkingsstand van Joan's aanlevering

> Bron: `Octopus.zip` (Joan, 2026-07-08). Dit document is de leeswijzer:
> wat erin zit, wat verwerkt is en waar, en wat bewust geparkeerd staat.
> Octopus blijft voor dit alles de **source of truth**: wij linken en
> spiegelen, wij beheren het niet.

## Verwerkt

| Onderdeel | Waarheen | Wanneer |
|---|---|---|
| Relaties-exports (8 firma's, 2313 vlakken) | `kosten.octopus_relatie` (migratie 056, seed octopus-import) | 2026-07-08 |
| Grootboekrekeningen per firma (xlsx) | `kosten.octopus_grootboek` (migratie 056) | 2026-07-08 |
| Boekhouding-naar-firma-mapping | `kosten.octopus_boekhouding` (migratie 059, expliciet - nooit naam-prefix raden) | 2026-07-08 |
| Partij-laag bovenop de relaties | `kern.partij` (migratie 058, 1828 partijen; seed partijen-opbouw) | 2026-07-08 |
| Dagboek-structuur per firma (8 screenshots) | dit document, tabel hieronder | 2026-07-08 |
| Grootboek-analyses (2 docx) | samenvatting hieronder | 2026-07-08 |
| Voorbeeld-facturatievoorstel (pdf) | lessen hieronder, voor de facturatievoorstel-workflow | 2026-07-08 |

**Herimport-flow**: eerst de octopus-import-seed, daarna de
partijen-opbouw-seed (beide idempotent, `db/seeds/`).

## Dagboek-structuur per firma

Octopus nummert dagboeken per type: **A** = aankopen, **V** = verkoop,
**F** = financieel (een dagboek per bankrekening), **D** = diverse posten,
**L** = leveringsbonnen/facturatievoorstellen. De inrichting verschilt per
firma; dit is de stand van de screenshots (boekjaar 2025-2027):

| Firma (BTW) | Aankoop | Verkoop | Financieel | Divers | Bijzonder |
|---|---|---|---|---|---|
| H-Architects (BE0646.974.162) | A1-A4 | V1-V6 | F1 moeder, F2 KBC, F3 BTW | D1-D6 | aparte creditnota- en oude-facturen-dagboeken |
| Energie-Efficient (BE1011.824.123) | A1-A3 | V1-V4 | F1 | D1-D3 (kredietkaart) | **L1 Leveringsbonnen, L2/L3 Facturatievoorstellen** - de enige firma met L-dagboeken |
| UNABO (BE1008.337.269) | A1-A3 | V1-V2 | F1 | D1-D2 | compact profiel |
| Contrax (BE1020.661.021) | A1 | V1-V3 | F1 KBC | D1 | V3 = interne correctie dubbele verkoopfacturen |
| Harmonie Bouw (BE0537.405.239) | A1-A3 | V1-V3 | **F1-F7** (moeder, ROEM, AN, Proj, SPAAR, ...) | D1-D5 | veruit de meeste bankrekeningen |
| H-Invest (BE0660.838.333, voordien H-Aannemingen) | A1-A3 | V1-V4 | F1-F4 (een KBC "niet gebruiken") | D1-D6 | Mastercard-dagboeken |
| TKN-Buro (BE0792.656.680) | A1-A3 | V1-V7 | F1-F3 (aparte BIM- en BTW-rekening) | D1-D6 | aparte verkoopdagboeken **BIM** (V4) en **Engineering** (V6) |
| Zidi Construct (BE0536.697.832) | A1-A2 | V1-V3 | F1 | D1-D5 | - |

## Grootboek-analyse (samenvatting van Joan's twee documenten)

**Gemeenschappelijk bij alle firma's** - verkoop: 400000 handelsdebiteuren,
451000 te betalen BTW, minstens een 700xxx/703xxx-omzetrekening; aankoop:
440000 leveranciers, 411000/410000 terug te vorderen BTW, 60xx-63xx
kostenrekeningen.

**Uniek per firma** (het vingerafdruk-lijstje): Zidi 700500 medecontractant
plus 499000 wachtrekening; H-Invest 700900 export, 746300 recuperaties en
230000/412000/613200; Harmonie 700100 (6% verkopen, nergens anders) en
240xxx/248xxx bouwkosten; Energie-Efficient 700300 als primaire
omzetrekening; H-Architects 700000+703000 en 411002 intracom; UNABO 703000
en 613200/616000; TKN-Buro 700700 (enige firma) en 611900 software/licenties,
613700 BA-verzekering, 648010/648020 bijdragen; Melodie 800xxx subsidies.

De volledige detail-analyses (per dagboek, per jaar, met uitzonderingen als
creditnota's en intracom) staan in de twee docx-bestanden in de zip; de
grootboek-PDF's per firma zijn het brondetail.

## Facturatievoorstel: lessen uit het voorbeeld (Energie-Efficient)

Voor de facturatievoorstel-workflow (wacht op de Octopus-API, gate G1):

1. Het voorstel heeft een **eigen nummerreeks** (voorbeeld: "Nr: 1"), los
   van de factuurnummers - Joan past de Delivery-Note-nummering aan zodat
   die niet gelijk loopt met factuurnummers.
2. Er is een **gestructureerde referentie** (+++145/2020/00135+++).
3. **Percentage-facturatie** is de kern: aantal 0,75 met omschrijving "75%
   EPB-Verslaggeving" tegen de volle eenheidsprijs - per projectfase een
   percentage van het afgesproken bedrag.
4. Het **dossiernummer plus projectadres** staat in de omschrijvingsregel
   ("46095 - EPB IER - Casinostraat 16, 9100 Sint-Niklaas") - dat is de
   koppelsleutel naar dashboard/Monday.
5. Opbouw verder identiek aan een factuur (BTW-blok, te betalen), maar het
   is er geen: geen BTW-verplichting zolang het een voorstel is.
6. In Octopus leven deze in de **L-dagboeken** (zie tabel: alleen bij
   Energie-Efficient ingericht; uitrol naar andere firma's is een
   inrichtingskeuze).

## Bewust geparkeerd

- **Aankoop- en verkoopdagboeken als PDF** (32 stuks, transactieniveau,
  2021-2026): niet handmatig verwerken; dit is precies wat de Octopus-API
  straks levert. Tot die tijd alleen als naslagwerk.
- **Grootboek-PDF's per firma**: detail achter de xlsx die al in
  `kosten.octopus_grootboek` zit.

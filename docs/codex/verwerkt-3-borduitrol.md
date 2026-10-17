# Verwerking ronde 3: bewaakte borduitrol mijnagents

Door Claude, 16-10-2026. Codex: niet klaar, 0 hoog en 4 middel (BU-14 tot BU-17), 1 laag (BU-18). BU-10 en BU-12
volstaan, BU-11 en BU-13 deels. BU-9 als aparte taak aanvaard.

## Stopregel

Verloop hoog+middel: 8, 4, 4. De laatste herstelronde gaf geen daling. Drie van de vier nieuwe punten (BU-14, 15, 16)
komen uit één keuze van ronde 2: `bewaak` zette zelf `.built` om en startte een uitrol. Dat is een ontwerpfout, geen
reeks losse randgevallen. Daarom geen nieuwe laag erbovenop, maar twee vereenvoudigingen:

1. **`bewaak` neemt alleen waar.** Het vergelijkt het draaiende image-ID met `.built_id` (nieuw: het na de uitrol
   nagekeken ID) of, voor een uitrol van voor 16-10-2026 zonder `.built_id`, het label met `.built`, en doet één probe.
   Een afwijking komt één keer in het log en in `.afwijking`. `.built` verandert niet; er wordt niets uitgerold,
   herstart of teruggezet. Een handmatige toestand blijft zo staan tot een nieuwe revisie of een bewuste ingreep.
   Daarbij een expliciete **pauze**: zolang `.pauze` bestaat doet het script niets (ook geen herstel), met één logregel
   bij het begin en bij het opheffen.
2. **Bouwen onder `:kandidaat`.** `:latest` en de container blijven onaangeroerd tot de wissel. `.herstel` bestaat
   alleen rond de wissel. Een mislukte bouw, een kopiefout of een veranderde image raakt het draaiende bord niet.

Komt ronde 4 niet lager uit dan ronde 3, dan volgt een ontwerpronde met Codex en een keuze van Mehdi.

| Punt | Oordeel | Nameting | Herstel | Test |
|---|---|---|---|---|
| BU-14 middel | gelijk | `bewaak` zette tijdens de afkoeling het label van een ongezonde image in `.built` | `bewaak` verandert `.built` niet meer | `test_ongezonde_image_met_het_head_label_tijdens_afkoeling_wordt_niet_gemarkeerd` |
| BU-15 middel | gelijk | een handmatige terugrol werd in dezelfde ronde ongedaan gemaakt | alleen melden; `.pauze` als expliciete pauzestand, onder hetzelfde slot te zetten (kop van het script) | `test_verkeerde_image_wordt_gemeld_en_niet_overschreven`, `test_pauze_doet_niets_tot_ze_opgeheven_is` |
| BU-16 middel | gelijk | alleen het label werd vergeleken | `.built_id` bij elke geslaagde uitrol (ook bij voltooien en herstel), `bewaak` vergelijkt het ID | `test_zelfde_label_ander_image_id_wordt_gemeld` |
| BU-17 middel | gelijk | de bouw tagde `:latest`; de kopiefout riep `herstel` aan, dat de container kon herstarten | bouw als `:kandidaat`; kopiefout en veranderde image breken af zonder de container aan te raken; `afbreken` zet alleen een halverwege mislukte wisseltag terug en laat een `.herstel` uit een eerdere ronde staan | `test_mislukte_bouw_laat_het_bord_draaien_zonder_herstart` (geen `:latest`), `test_kopie_mislukt_start_niet_en_blokkeert_niet`, `test_wisseltag_faalt_raakt_het_bord_niet`, `test_andere_image_na_de_bouw_geeft_geen_wissel`, `test_kopiefout_laat_een_eerdere_herstelmarkering_staan` |
| BU-18 laag | gelijk | ruimtegebrek werd pas na de bouw vastgesteld | ruimte (en databank) voor de bouw | `test_te_weinig_ruimte_voor_de_kopie_bouwt_niet` (twee rondes, geen bouw) |
| BU-12 opmerking | aanvaard | een agent bewijst niet dat alle agents er zijn | bij de eerste live controle vergelijkt Claude het aantal uit `/gezondheid` met dat uit de logregel van de kopie | — |

Valse melding voorkomen: een image van het oude script zonder label en zonder `.built_id` geeft geen afwijking
(`test_image_van_het_oude_script_zonder_label_geeft_geen_vals_alarm`).

Grendelproef: de tests falen op de versie van ronde 3 (`88b0f5c`, 19 tests) en op elke gerichte mutatie: geen ID-vergelijking, bouw als `:latest`, `afbreken` wist een eerdere `.herstel`, geen terugzetten van de wisseltag, geen nacontrole van de draaiende image, geen ruimtecontrole vooraf, pauze genegeerd, elke ronde een melding, vals alarm op een image zonder label.

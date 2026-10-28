# Opdracht: werfverslagketen als één geheel (28-10-2026)

Mehdi vraagt: zijn twee agents (Werfverslag voorbereider en Werfverslag schrijver) nodig, ja of nee? Houd rekening met
de app werf.globaal.be en de pagina Werfverslagen op het bord. Zorg dat ze één geheel vormen, samenwerken en elkaar
niet tegenwerken. Kernoorzaak eerst, kleinste oplossing. Regels in code en tests, niet in tekst.

## Gemeten op de VM vandaag (alleen gelezen)

- Voorbereider (cron werkdagen elke 2 uur): 7 dossiers, 30 bezoeken. 26 "te verzamelen", 4 "verslag aanwezig, bronnen
  onvolledig", 0 "klaar voor verslag". Schrijver: 0 opdrachten (wacht op de knop, zoals bedoeld).
- Redenen in de tabel werfbezoek (30 rijen):
  - W12 onbekend 29x: "project niet in het contractdashboard (vermoedelijk van vóór het systeem); bekijk het getekende
    contract in de projectmap". `stand_van()` in `mijnagents-runner/werfverslag_voorbereider.py` eist W12 == ok.
    Gevolg: geen enkel bezoek kan ooit "klaar voor verslag" worden. Voorbeeld: bezoek van 18-10-2026 met W1 tot W6 ok
    blijft "te verzamelen" alleen door W12.
  - W2 onbekend 27x: "vóór de GPS-meetreeks (03-10-2026)". De werkwijze zegt dat W1 (buitenafspraak) voor die dagen
    het bewijs is, maar `stand_van()` eist W2 == ok. Tekst en code spreken elkaar tegen.
  - W8 onbekend 23x: "werfapp kent dit project niet". Oorzaak: sinds PR 8 van globaal-werfverslag (27-10) bestaat een
    project in de werfapp pas na "Werfdossier openen". `GET /api/v1/projecten/2145` geeft 404, 2513 geeft 200.
    `POST /api/v1/projecten {"nummer": ...}` in globaal-werfverslag `app/api.py:259` opent het werfdossier met naam en
    adres uit H-A Projecten en overschrijft nooit iets; maar voor een nummer dat niet in H-A Projecten staat maakt
    dezelfde route een vrij project aan.
  - W4: 10x ontbreekt (geen foto's), 10x let_op (foto's zonder 00 fotos.md). Dat is echte bronlevering (iCloud-wacht).
- Runner `werfverslag_dashboard.py` (cron elke 15 min) crasht soms met een onopgevangen TimeoutError op werf.globaal.be
  (4 tracebacks in de log). De API antwoordt nu in 0,1 s.
- Tegenspraak in de werkwijzen (`mijnagents-runner/werkwijze/werfverslag-*.md`):
  - W2 auto bij het project: voorbereider en code zeggen ok (E1b); dashboard-werkwijze zegt let_op; koppelfiche van de
    schrijver zegt "auto alleen: W2 ontbreekt".
  - Norm: voorbereider v1.10, schrijver en dashboard v1.9.
  - Voorbereider: "Later: elke afspraak WB/PLB wordt vanzelf een opdracht". Dat doet het Commandocentrum al (impuls,
    `werfverslag_voorbereider.py:1240`).

## Voorstellen om over te stemmen

P1. Twee agents blijven: voorbereider (tokenvrij, bronnen en controles) en schrijver (betaald, alleen op Mehdi's knop).
    Niet samenvoegen; de grens "geen tokens zonder knop" valt samen met de grens tussen de twee.
P2. W12 "onbekend" blokkeert de stand niet meer; alleen W12 "ontbreekt" (contract gevonden zonder werfopvolging)
    blokkeert. Onbekend blijft zichtbaar op de bezoekpagina als aandachtspunt. Grendeltest.
P3. W2 "onbekend" vóór de GPS-meetreeks blokkeert niet als W1 "ok" is (zoals de werkwijze al zegt). Na de meetreeks
    blijft W2 ok verplicht. Grendeltest.
P4. De voorbereider opent voor elk gevolgd dossier het werfdossier in de werfapp als het daar ontbreekt, via
    `POST /api/v1/projecten` met een nieuwe vlag `alleen_ha: true`: staat het nummer niet in H-A Projecten, dan 404
    en wordt er niets aangemaakt. Idempotent (409 = bestaat al). Tests in beide repos.
P5. `werfverslag_dashboard.py` vangt netwerkfouten op: één hartslag "fout" met reden, geen traceback.
P6. Eén tekst voor W2 en de norm in alle drie de werkwijzen (auto telt volgens E1b, norm v1.10); de zin "Later: ..."
    wordt "het Commandocentrum zet elke WB/OPL-afspraak als impuls klaar".
P7. Geen nieuw scherm of nieuwe agent: werf.globaal.be blijft de plek van verslag, nummer en verzending; de bordpagina
    blijft de werkvoorraad. Dat staat al zo in de werkwijzen.

Lees zelf de code na (`werfverslag_voorbereider.py` stand_van, ontbrekende_posten, contractbewijs, aanwezigheidsbewijs;
`mijnagents/app.py` waar de bord-pagina de stand toont; globaal-werfverslag `app/api.py`). Zeg per punt eens of oneens
met bestand:regel. Wijs Claude aan als maker en Codex als tester.

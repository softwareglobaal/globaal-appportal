# Opdracht 12, uitvoeringsverslag (18-10-2026)

Beslissing: klaar voor Claude's onafhankelijke controle. Er is niets gecommit, gepusht, uitgerold of in een echte agenda of crontab gewijzigd.
Bij aanvang stond de tak op `9801de6` in plaats van het genoemde `1c0904d`; reeds aanwezige niet-gevolgde rondebestanden bleven ongemoeid.

## 1. Agendawacht kijkt alleen lezend terug

`agenda_wacht.py:316`, `:333` en `:393` lezen actieve en archiefagenda's met `alleen_lezen`; `koppelingen/agenda.py:97` slaat dan zelfs de lokale leesstandschrijfroute over. `agenda_wacht.py:510` maakt voor gewone en historische rondes hetzelfde afspraakitem; `:4369`, `:4434` en `:4473` verwerken oude dagen, maximaal veertig unieke taakdagen, en vinken pas na een volledige lezing af. `planning/agenda-terugkijken.cron:1` en `planning/agenda_terugkijken_cron_zetten.py:17` beheren een eigen cronblok; `werkwijze/agenda-wacht.md:650` en `werkwijze/agenda-taken.json:994` leggen de stand vast.

Grendel: `tests/test_agenda_terugkijken.py:102` vervangt agendaschrijfroutes en Google-schrijfmethode door een val; `:123` houdt taken open bij een onvolledige bron; `:139` toetst de daglimiet; `:180` en `:202` toetsen cronvoorbeeld en gesimuleerd zetten. CI: `.github/workflows/agenda-grendels.yml:45`.

Bewust niet gedaan: `--dag` op historische afspraken, echte Google-mutaties, bellen, mailen en crontab zetten. Een dag zonder zakelijke afspraak levert geen afspraakitem met terugkijkmerk op; de unieke taak blijft na afvinken wel duurzaam opgepakt.

## 2. Voorbereider herkent een bewezen bezoek

`werfverslag_voorbereider.py:242` maakt van de nieuwe naamvorm een kandidaat; `:431` toetst op het mapuur exact dossier en buitenafspraak of een projectverblijf via locatiecontext. `:859` filtert vóór registratie en nummering, maakt per oude dossierdag één terugkijktaak en schrijft het bewijs in `bronnen` (`:984`). W1 accepteert ook de H-A-afdeling bij een ongecodeerde bezoektitel (`:638`); W2 telt de auto bij dit project als ok (`:537`).

Grendel: `tests/test_werf_agenda_bezoek_12.py:46`, `:68`, `:81`, `:95`, `:108` en `:119` toetsen onder meer een verkeerd nummer, verkeerd uur, ontbrekend bewijs, GPS en W1. `tests/test_werfketen_controles_11.py:124` en `:130` toetsen de auto binnen én buiten het juiste venster. CI: `.github/workflows/werfverslag-grendels.yml:31`.

Bewust niet gedaan: een kandidaat zonder bewijs meetellen, GPS vóór de meetgrens afleiden of locatie rechtstreeks buiten `locatiecontext` lezen.

## 3. Werkwijze en norm

`werkwijze/werfverslag-voorbereider.md:7` verwijst naar `H-A vaste afspraken v1.10`; de stappen, koppelfiches en lessen 26-28 (`:195`) leggen E1b, W1, W2 en de terugkijktaak vast. De nieuwe tests staan in beide CI-grendels. Bewust niet gedaan: de externe norm zelf of live werkwijze wijzigen; dit zijn de zaden voor Claude's controle en uitrol.

Gedaan: code, zaden, planning en tests in deze worktree. Nagekeken: 7 nieuwe agendatests, 74 werfpytests, 244 bestaande agendacontroles, 8 locatiegrendels, 17 nummertests en 6 hernoemingstests groen. Open: Claude controleert en beslist daarna over commit en ingebruikname.

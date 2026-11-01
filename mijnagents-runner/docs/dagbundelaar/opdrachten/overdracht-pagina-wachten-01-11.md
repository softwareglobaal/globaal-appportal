# Overdracht: pagina Wachten in het Dagboek (01-11-2026)

Van Claude 2 (cloud) aan Claude 1 (laptop). Mehdi neemt het over via Claude 1.

## Wat klaar is

- De pagina Wachten staat live: dagboek.globaal.be/wachten. Op de startpagina van het Dagboek staat bovenaan de
  link "wat de wachten kregen".
- Drie knoppen: vrijdag 30-10, zaterdag 31-10 en vandaag. Per wacht een blok met een kleur, het aantal items, de
  items (tijd, van wie of wat, kort) en het werkverslag van die dag. Een wacht met een fout staat open.
- Live gezet op 01-11 om 16:27 na de ja van Mehdi ("doe in gods naam de nodige"), via globaal-vm-beheer
  (commit f6e471b). Nagekeken op de server: 30-10 heeft 318 items, 31-10 heeft 122, 01-11 heeft 45. Alle drie de
  dagen laden.
- Code in globaal-appportal: `dagboek/app.py` (route `/wachten`), `dagboek/templates/wachten.html`,
  `mijnagents/wachten_dag.py` en de route `/api/wachten/dag` in `mijnagents/app.py`. Tests:
  `dagboek/test_dagboek.py` (D14) en `mijnagents/test_wachten_dag.py`. Commits e3a3bbb en b572132.

## Wat rood staat op de echte gegevens

- De Fotowacht (alle drie de dagen): "fotoaanvoer: fototaak blijft open". Dat zijn de oude werfverslagtaken
  (zie T-0042).
- De Wispr-wacht (30-10 en 31-10): "RuntimeError: geen inloggegevens" (zie T-0077).
- De YouTube-wacht en de Wispr-wacht op 01-11: rood (zie T-0088 en T-0077).
- Grijs (geen ronde): Websitewacht, YouTube-wacht, Belwacht Xelion op 30-10 en 31-10.

## Wat Claude 1 doet

1. Repo ophalen: `git -C ~/dev/globaal-appportal pull --rebase origin main`.
2. In de werkstand (Claude 2 in de cloud heeft nog geen eigen id, T-0085, en kon daar niet schrijven):
   - T-0087: het antwoord van Mehdi zetten (vraag_id 4f9679): "Ja, in de chat op 01-11 16:26". Daarna klaar met
     als bewijs: live sinds 01-11 16:27, commit f6e471b in globaal-vm-beheer, deze overdracht.
   - Een nieuwe taak: "Pagina Wachten met Mehdi nakijken en verbeteren", project P-08, gebied
     globaal-appportal:dagboek.
3. Met Mehdi de pagina openen en zijn opmerkingen noteren. Een wijziging aan de pagina: in de repo, tests draaien
   (`python3 dagboek/test_dagboek.py` en `python3 mijnagents/test_wachten_dag.py`), pushen naar main.
4. Live zetten (na een ja van Mehdi): `opdracht.sh` in globaal-vm-beheer laat de server de code ophalen en
   `docker compose up -d --build app-mijnagents app-dagboek` draaien, met een controle erna. Een voorbeeld staat in
   die repo (commit f6e471b).

## Meer dagen tonen

Het aantal dagen is `WACHT_DAGEN` in `dagboek/app.py` (nu 3). Hoger zetten en live zetten zoals in stap 4.

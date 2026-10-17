# Opdracht 12: een bezoek herkennen via agenda en GPS-tracker; auto telt; Agendawacht kijkt alleen lezend terug

Je werkt in deze worktree (tak `werf-agenda-bezoek`, vanaf main 1c0904d) met schrijfrecht. Je wijzigt code, tests,
cron-planning en werkwijze-zaden; je commit niets en je pusht niets. Claude controleert en commit.
Nederlands in commentaar en meldingen, geen emoji, geen kastlijntjes. Geen netwerk in tests (stubs zoals bestaande tests).
Elke wijziging krijgt een test die het foutgeval dekt. Noteer per punt in
`docs/codex/codex-12-bezoek-via-agenda-verslag.md`: bestand:regel, test, en wat je bewust niet deed.

## De beslissing van Mehdi (18-10-2026), nu afspraak E1b van H-A vaste afspraken v1.10

> Sinds de communicatiemap de naamregel `JJJJ-MM-DD UUMM HARC nummer - met wie - onderwerp` volgt, staat het kanaal niet
> meer in de mapnaam. Of een momentmap een werf- of plaatsbezoek is, beslist het bewijs van dat moment:
> - de agenda: op die dag een buitenafspraak (`!!`) in een H-A-agenda met dit projectnummer, waarvan het tijdvak het uur
>   `UUMM` van de mapnaam bevat; of
> - de GPS-tracker: op dat uur een verblijf bij dit project. Mehdi gaat altijd met de auto, dus de auto bij het project
>   telt als zijn aanwezigheid.
> Een map met "bezoek" of "werfbezoek N" in de naam blijft een bezoek zoals voorheen. Een map zonder agenda- of
> trackerbewijs is geen bezoek. Voor dagen van vóór de huidige meting kijkt De Agendawacht op vraag terug in de agenda,
> alleen lezend: hij verandert dan niets aan kleuren, ritten of gasten van oude afspraken.

Gemeten op de VM (17-10): dossier 2145 heeft in `_00. Communication` 55 momentmappen in de nieuwe naamvorm; de
plaatsbezoeken van 06-06, 24-06, 29-06, 03-07 en 28-08-2026 heten nu bv. `2026-06-06 1030 HARC 2145 - klant - ramen,
pergola en terras` en worden niet meer als bezoek herkend (de voorbereider eist "bezoek" in de naam). De Agendawacht zet
afspraken alleen klaar voor `dag >= vandaag` (`agenda_wacht.py`, rond `klaar.append({"voor": afdeling, "soort": "afspraak"`),
dus voor juni tot begin september bestaat er geen agendabewijs in de bak. Zijn `--dag` schrijft (kleuren, ritten, gasten,
titels): die mag je voor oude dagen NIET gebruiken. De GPS-meetreeks start op 03-10-2026 (`locatie/bronbeleid.py`
STARTGRENS); daarvoor geeft `locatiecontext` terecht niets.

Ook gemeten: het klaarzet-item van de Agendawacht voor `!! Mehdi: 2405 plaatsbezoek (meetstaten bespreken)` heeft
`"firma": "", "soort": "", "type": ""` en `"nummer": "2405"`, `voor` = `h-architects` (afdeling via de agenda
"H-Architects"). `bevestigd_fotovenster` in `werfverslag_voorbereider.py` eist `firma == "HARC"` en een type uit een lijst;
zulke titels (de meeste van Mehdi, "43 zonder code") geven dus nooit W1 ok.

## Punt 1: De Agendawacht kijkt alleen lezend terug (`mijnagents-runner/agenda_wacht.py`)
- Nieuwe stand `--terugkijken JJJJ-MM-DD [JJJJ-MM-DD ...]` en `--taken`: leest met `afspraken_dag(dag)` de afspraken van die
  dagen (alle agenda's die hij leest, archief alleen lezen zoals nu), ontleedt de titel (`lees_titel`), koppelt aan een deal
  (`koppel`) en zet voor elke niet-privé afspraak hetzelfde klaarzet-item `soort: afspraak` als de gewone ronde (zelfde
  `uniek` `agenda:<kalender>:<id>`, zodat er geen dubbel ontstaat), met in de inhoud `"terugkijken": true`.
  Geen kleuren, ritten, gasten, titels, Zoom, markeringen, bellen of mail: de stand roept GEEN enkele schrijffunctie van de
  agenda aan. Grendel: een test die alle schrijfroutes van `agenda.py` en de Google-API vervangt door een val die faalt en
  bewijst dat `--terugkijken` en `--taken` er nooit langs komen.
- `--taken`: leest de klaarzet-items `soort: taak`, `voor: agenda-wacht`, `van: werfverslag-voorbereider` met in de inhoud
  `"terugkijken": "JJJJ-MM-DD"` (punt 2), voert per unieke dag `--terugkijken` uit, en meldt elke taak als opgepakt
  (bestaande bord-API voor opgepakt). Een dag in de toekomst of vandaag slaat hij over (dat doet de gewone ronde al).
  Hoogstens 40 dagen per ronde; de rest volgende ronde.
- Planning: `mijnagents-runner/planning/agenda-terugkijken.cron` met één regel (elke 2 uur op :40, flock + timeout zoals
  `plaud.cron`) en een `agenda_terugkijken_cron_zetten.py` naar het model van `plaud_cron_zetten.py` (alleen het eigen
  blok tussen `# >>>` en `# <<<` beheren; zonder `--zet` alleen tonen).
- Werkwijze-zaad `mijnagents-runner/werkwijze/agenda-wacht.md`: korte sectie "Terugkijken op vraag (E1b, 18-10-2026)" en een
  regel in de lessentabel; `agenda-taken.json` alleen als dat bestand de standen opsomt (kijk na).

## Punt 2: De voorbereider herkent een bezoek via agenda en tracker (`mijnagents-runner/werfverslag_voorbereider.py`)
- `bezoeken_in`: een momentmap in de communicatiemap met naam `^JJJJ-MM-DD UUMM HARC <dit nummer> - ` die geen "bezoek" in de
  naam draagt, is een **kandidaat** (datum + uur uit de naam), geen bezoek.
- In `verwerk`, na `klaargezet(nummer)`: een kandidaat wordt een bezoek als (a) er in de bak een `afspraak` van
  `agenda-wacht` voor `h-architects` is met hetzelfde projectnummer, `buiten` waar, niet geannuleerd, waarvan [start, einde]
  het uur van de mapnaam bevat (marge 30 minuten voor de start en 60 na het einde); of (b)
  `LC.verblijven_in_venster(uur-15min, uur+60min, "HARC", nummer)` een verblijf geeft (auto of tracker). Het bewijs komt in
  de rij (`bronnen.herkend_via`: "agenda" of "gps", met de agenda-titel of `LC.beschrijf`). De soort (plaatsbezoek of
  werfbezoek) en de nummering volgen de bestaande regels (`nummer_bezoeken`, werfstart).
- Een kandidaat zonder bewijs en met datum vóór vandaag krijgt één taak voor de Agendawacht: klaarzet `soort: taak`,
  `voor: agenda-wacht`, inhoud `{"terugkijken": "<datum>", "dossier": "<nummer>"}`, `uniek`
  `werf:terugkijken:<nummer>:<datum>`, één keer per dossier en dag (bestaande `uniek`-ontdubbeling). Geen taak als de bak al
  een terugkijk-item (`"terugkijken": true`) voor die dag bevat: dan was er die dag gewoon geen buitenafspraak.
- W1 (`bevestigd_fotovenster`): een agenda-item telt als H-A-buitenafspraak als `firma == "HARC"` OF `voor == "h-architects"`
  (afdeling uit de agenda), met hetzelfde nummer, `buiten` waar, `onzeker` niet waar, niet geannuleerd, geldig venster. Het
  type mag leeg zijn als de titel "bezoek" bevat; anders blijft de typelijst gelden. Een ander nummer op dezelfde dag blijft
  geen bewijs (bestaande test moet blijven slagen).
- W2 (`aanwezigheidsbewijs`): een verblijf van de auto bij het project telt nu als **ok** ("auto bij het project; Mehdi gaat
  altijd met de auto, E1b"), niet meer als let_op. Pas de bestaande test `test_w2_alleen_de_auto_bij_het_project_is_let_op`
  aan naar de nieuwe regel en houd de test dat een verblijf buiten het venster of bij een ander project niet telt.
- De locatiegrendel (`tests/test_locatielezers.py`) moet groen blijven: locatie alleen via `locatiecontext`.

## Punt 3: werkwijze en norm
- `werkwijze/werfverslag-voorbereider.md`: de bezoekherkenning (E1b), W1 met afdeling, W2 met de auto, de terugkijktaak;
  verwijzing naar `H-A vaste afspraken v1.10`; lessentabel aanvullen (18-10-2026, oorzaak, fix, vindplaats).
- CI: voeg de nieuwe tests toe aan de juiste workflow (`werfverslag-grendels.yml` voor de voorbereider; de grendel van de
  Agendawacht staat in `agenda-grendels.yml`: voeg de nieuwe agendatest daar toe).

## Wat je niet doet
Geen commit, push, crontab-wijziging op een echte machine, netwerk, of wijziging aan de agenda. Geen andere standen van de
Agendawacht veranderen dan wat hier staat. Twijfel: kies de veiligste lezing (nooit een bezoek zonder bewijs, nooit een
schrijfactie in de agenda) en noteer de twijfel.

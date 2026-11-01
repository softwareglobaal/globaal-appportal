# Fathom: samenvatting en actiepunten per gesprek (contract)

Versie 1.0, 01-11-2026 (T-0120, FATHOM-1 en ANGEL-8). Voor wie ze leest: De Dagbundelaar, later Ai Angel.
De code is de bron: `mijnagents-runner/koppelingen/fathom.py` (samenvattingen, samenvatting_tekst, actiepunten,
vul_aan). Verandert de vorm, dan veranderen dit blad en de test `tests/test_fathom_wacht.py` mee.

## Waar het staat

Niet op het bord en niet in de gesprekkentabel: alleen in de archiefmap van het gesprek op de VM.

- De map: kolom `archief` van de rij in `gesprek_log` (uniek `fathom:<recording_id>`), bv.
  `~/appportal/mijnagents-data/fathom-data/2026-10-21 1000 <titel in Fathom>/`.
- `samenvatting.md`: de kopregel `# Samenvatting van Fathom (niet als bron voor contract of verslag; het transcript
  telt)`, een lege regel, dan de markdown-tekst van Fathom (`default_summary.markdown_formatted`).
- `actiepunten.json`: `{"bron": "fathom", "recording_id": <getal>, "actiepunten": [...]}`. Elk actiepunt is
  `{"tekst": str, "wie": str, "tijd": str, "klaar": bool}`:
  - `tekst`: wat er moet gebeuren (de beschrijving van Fathom);
  - `wie`: de naam van wie het moet doen, `""` als Fathom niemand noemt;
  - `tijd`: het moment in de opname, `"UU:MM:SS"`, of `""`;
  - `klaar`: of het in Fathom afgevinkt is.
- `actiepunten.md`: dezelfde lijst om te lezen (`- [ ] tekst (wie, tijd)`), voor Mehdi in Dropbox. Lees de json.

## Wat een ontbrekend bestand betekent

- Geen `actiepunten.json`: **onbekend** (nog niet gevraagd, of Fathom verwerkte het gesprek nog niet). Nooit 0.
- `"actiepunten": []`: Fathom verwerkte het gesprek (er is een samenvatting) en vond geen actiepunt.
- Geen `samenvatting.md`: onbekend of geen samenvatting; zeg nooit "geen samenvatting".
- Een bestand dat er staat, wordt nooit overschreven: wat Fathom later anders zegt, komt er niet in.

## Wanneer het er komt

- Elke ronde van De Fathomwacht (07:00 en 13:00 UTC), voor de gesprekken van haar venster (14 dagen), in een aparte
  vraag zonder transcript, na de gesprekkentabel en de klaarzet-items. Een nieuwe opname krijgt de bestanden dus in
  dezelfde ronde of de volgende. Faalt die vraag, dan staat er een nood en schrijft de ronde geen dekking.
- Oktober eenmalig: `fathom_haal_alles.py --aanvullen 2026-10-01`, eerst met `--droog` (uitrolstap, niet gedraaid).

## Privé

Ook een privégesprek krijgt de bestanden in het archief, zoals zijn transcript. Wie leest, volgt de privéregel van
de rij: `prive = 1` of afdeling `prive`/`privé` betekent bij Fathom privé. Lees dan niets uit de map en toon alleen
"privégesprek, N min". Lees ook niets voor een rij met `dubbel_van`: de leidende rij telt.

## De link naar Fathom

Kolom `link` van de rij: bij een werkgesprek de deellink (`share_url`, opent zonder aanmelden), anders de gewone link
(`fathom.video/calls/...`, vraagt aanmelden); een privégesprek krijgt nooit de deellink. Zet hem niet in een bestand
in Dropbox: de link gaat via een route achter Authentik (VOL-19).

# Werkwijze: eerst een slimme agent, dan een programma

Besluit van Mehdi, 31-10-2026.

## De regel

1. Een nieuwe taak begint als slimme agent (met Claude). Die mag zoeken, twijfelen en vragen.
2. Elke ronde schrijft de agent op wat hij deed en waarom (werkverslag op het bord).
3. Een stap die drie weken lang elke keer op dezelfde manier gaat, zonder correctie van Mehdi, is "stabiel en bekend".
4. Alleen zo'n stap wordt een gewoon programma (vaste code, geen AI, geen tokens). De agent houdt alleen wat nog oordeel vraagt.
5. Faalt het programma op iets nieuws, dan gaat dat geval terug naar de agent. Niet het programma uitbreiden met gokwerk.

## Waarom

- Snel starten: een agent werkt de eerste dag al, ook als we nog niet alles weten.
- Goedkoop en betrouwbaar op termijn: wat vast ligt, kost geen tokens en geeft altijd hetzelfde resultaat.

## Eén plek

Alle agents van het dagboek staan op het bord in één groep: Dagbundelaar. De lijst staat op één plek in de code:
`DAGBUNDELAAR_AGENTS` in `mijnagents/app.py`. Een agent staat nooit in twee groepen. Een nieuwe agent voor het
dagboek komt in die lijst, nergens anders.

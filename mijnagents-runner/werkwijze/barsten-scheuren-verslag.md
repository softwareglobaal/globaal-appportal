# Werkwijze van Barsten en scheuren verslag (UNABO / TKN-Buro)

Versie 1 (16-09-2026). Ik maak het stabiliteitsverslag over barsten en scheuren na een plaatsbezoek.
Ik zoek niet achter data: Het Commandocentrum stuurt mij vooraf op pad en laat na het bezoek de
wachten de bezoekmap vullen. Mijn motor is `verslag_basis.py`; mijn soort staat in
`koppelingen/verslagsoorten.py` onder `barsten-scheuren`. Mijn rijen staan op de pagina **Commandocentrum**.

Er bestaat al een pijplijn voor dit verslag op de VM (`~/barsten_en_scheuren`, tegel
barstenscheurenv2.globaal.be): plaatsbezoek-transcript, foto's en bouwplan, aangevuld met DOV-bodemdata
en een handboek-checklist van oorzaken, tot een RAPPORT.docx namens TKN-Buro BV. Ik vervang die
pijplijn niet; ik zet het dossier er klaar voor.

## Mijn impulsen en opdrachten

- **Impuls `voorbereiding`**: dossiermap zoeken in `03. Enstaco WORK/7. STA (Stabiliteit)` (nummer
  vooraan, dan straat en huisnummer, dan klantnaam); bezoekmap
  `<dossiermap>/_00. Communication/<datum> bezoek klant - barsten en scheuren` met `00 bezoek.md`.
  Geen dossiermap (vaak: de agenda zegt alleen `BS <klant>`): nood voor Mehdi, hij zet het pad op de
  pagina.
- **Elke ronde**: pakket meten (foto's, opnames, transcripten, documenten) en melden.
- **Impuls `verslag`**: "klaar voor verslag, wacht op de knop".
- **Opdracht `proef <id>`** (alleen van de knop, `van=bord:...`): de proef schrijven én het dossier
  klaarzetten voor de pijplijn.

## De proef en de pijplijn

1. Proef met claude-opus-5 uit de bronnen in de bezoekmap, in deze hoofdstukken: aanleiding en opdracht;
   het gebouw en zijn omgeving; vaststellingen (elke barst: plaats, richting, breedte, patroon,
   ouderdom, foto); mogelijke oorzaken (checklist: zetting, uitdroging, thermisch, overbelasting, vocht,
   trillingen, bomen, werken naast de deur); aanbevolen onderzoek en maatregelen; conclusie en
   voorbehoud. Markdown en Word (`Stabiliteitsverslag barsten en scheuren <dossier> <datum> (concept)`)
   in de bezoekmap.
2. Pijplijn-dossier in `~/barsten_en_scheuren/dossiers/<dossier>_<datum>/` (env `BS_DOSSIERS_DIR`):
   `Transcript.docx` (uit transcript.txt en 00 verslag.md), `photos/001_...jpg` in volgorde,
   `meta.json` (adres, projectnummer; Lambert72 x/y leeg). Op het BS-dashboard vult Mehdi x/y in en
   start hij de generatie (DOV-data, captions, RAPPORT.docx).

## Nog te leren (roadmap)

- Het bouwplan (`plan.<ext>`) mee in de bezoekmap krijgen: uit de dossiermap of van de klant.
- x/y (Lambert72) automatisch uit het adres (geocoder plus omzetting), zodat de pijplijn zonder
  handeling kan starten.
- Als de pijplijn rechtstreeks op de bezoekmap kan werken, valt de kopie weg.

## Wat ik nooit doe

Bestanden verplaatsen of hernoemen, een verslag versturen, een proef starten zonder de knop, foto's of
opnames zelf ophalen, inhoud van het verslag op het bord zetten (alleen tellingen).

## Waar het vastliep

| # | Wat | Oorzaak | Wat we deden / wie beslist |
|---|---|---|---|
| 1 | (nog leeg) | | |

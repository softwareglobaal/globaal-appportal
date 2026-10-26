# WhatsApp-wacht op de Mac

> Vervangen op 26-10-2026 door werkwijze v3.0: De WhatsApp-wacht leest de databank op de Mac via MacGesprekkenKopie (ontwerp dagvaststelling v2.0, fase 2). `mac/whatsapp_wacht.py` bestaat niet meer.

Versie 2.0, 23-10-2026. De WhatsApp-wacht leest alleen door Mehdi afzonderlijk
gekozen exports van zijn persoonlijke WhatsApp. Een export blijft een
momentopname. Nieuwe berichten komen pas mee na een nieuwe export van dat
gesprek. De wacht gebruikt de lokale WhatsApp-database niet.

## Bron en selectie

1. Gebruik uitsluitend `~/.local/share/mijnagents/whatsapp-wacht/exports` op
   deze Mac. Zet zowel deze map als de bovenliggende `whatsapp-wacht` map op
   rechten `700`; een andere map of een symlink wordt geweigerd. Zet daarin
   uitsluitend de gekozen exports, zonder media. Het bestand zelf krijgt
   `chmod 600`.
2. WhatsApp levert vaak een ZIP. De wacht leest daar rechtstreeks alleen
   `_chat.txt` uit. Een ZIP met media of een tweede bestand wordt geweigerd.
   Een losse `.txt` export kan ook.
3. Zet de selectie in `~/.config/mijnagents/whatsapp-wacht.json` en geef dat
   bestand `chmod 600`. Zet de bestaande instellingenmap eerst privé met
   `chmod 700 ~/.config/mijnagents`; deze map mag niet in Dropbox staan. Vul per
   gesprek de exacte bestandsnaam en de twee afzendernamen in zoals ze vóór de
   dubbele punt in de export staan. Gebruik
   geen echte namen in de repo, tests of werkverslagen. Voorbeeld met verzonnen
   namen:

```json
{
  "versie": 1,
  "export_map": "/Users/voorbeeld/.local/share/mijnagents/whatsapp-wacht/exports",
  "gesprekken": [
    {
      "bestand": "gekozen-gesprek.zip",
      "eigen_afzender": "Eigen",
      "andere_afzender": "Ander",
      "datumvolgorde": "DMY"
    }
  ]
}
```

`datumvolgorde` is `DMY` voor dag/maand/jaar of `MDY` voor
maand/dag/jaar. De map mag geen extra bestanden bevatten, behalve `.DS_Store`.
Zo kan een tweede export met een bijna gelijke naam geen onduidelijke telling
geven. Kies per gesprek en per afzenderpaar precies één momentopname. Vervang
bij een nieuwe export de oude momentopname; selecteer oude en nieuwe exports
nooit tegelijk. Ook een omgewisselde volgorde van dezelfde twee afzenders
wordt geweigerd. De wacht volgt nooit automatisch een nieuw bestand.
Een onbekende regel in de vorm `Naam: bericht` wordt geweigerd. Sommige
systeemregels met een dubbele punt en groepsgesprekken kunnen daarom een veilige
foutstatus geven; ondersteuning daarvoor vraagt eerst een bewezen exportformaat.

## Ronde en resultaat

De runner staat in `mijnagents-runner/mac/whatsapp_wacht.py`. Hij gebruikt het
bestaande bordtoken in `~/.config/mijnagents/token` met rechten `600` en leest
eerst de live werkwijze van zijn bordkaart via een tijdelijke SSH-tunnel naar
`127.0.0.1:3022` op de VM. De tunnel gebruikt de bestaande SSH-host `globaal`
op de Mac. Zonder tunnel of met ontbrekende veiligheidsgrenzen op de bordkaart
opent hij geen export. Daarna telt hij de gekozen exports
volledig opnieuw. Anonieme totalen per dag staan in
`~/.local/share/mijnagents/whatsapp-wacht/dagen.json` met rechten `600`. Een
ongewijzigde export verandert dat bestand niet. Een herexport met late
berichten vervangt de oude dagtelling, zonder dubbels.
Een privé-rondeslot in dezelfde lokale staatmap (`ronde.lock`, rechten `600`)
blijft vast tot na de bordbevestiging. Een tweede handmatige start stopt
meteen zonder nieuwe bordronde.

Op het bord staat alleen de status met de laatste berichtdag en het totale
aantal berichten op die dag, zonder namen, nummers, bestandsnamen of inhoud.
Na de ronde leest hij via SSH met `bordstand.py` terug of de eindhartslag en
kennismelding met dezelfde unieke ronde-ID echt op het bord staan. Hij
weigert ongeldige of onwaarschijnlijk toekomstige tijdstempels. Zonder beide
bevestigingen meldt de runner geen succes. Hij probeert een neutrale
fouthartslag alleen als de actuele bordstatus nog van zijn eigen ronde is;
een latere ronde blijft ongemoeid. Een volgende handmatige start telt opnieuw.
Een ontbrekende, te open opgeslagen of dubbelzinnige bron geeft een foutstatus.
De vorige lokale dagtelling blijft dan staan, maar is niet bevestigd voor de
nieuwe ronde. Er gaan geen berichten naar WhatsApp, andere agents of een
taalmodel. De huidige versie telt geen oproepen en doet geen inhoudsanalyse.

Een eerste proef op synthetische bestanden:

```sh
python3 mijnagents-runner/tests/test_whatsapp_wacht.py
```

Een live ronde, pas nadat de bordwerkwijze versie 2.0 is geplaatst en de
configuratie op de Mac klaarstaat:

```sh
python3 mijnagents-runner/mac/whatsapp_wacht.py
```

Lees daarna de anonieme status en `dagen.json` terug. Deze opdracht blijft
eenmalig; er wordt geen dagelijkse planning ingesteld. Een export is een
momentopname en de hartslag is een meting van de laatste geslaagde ronde, geen
garantie dat er vandaag geen nieuwe WhatsApp-berichten zijn.

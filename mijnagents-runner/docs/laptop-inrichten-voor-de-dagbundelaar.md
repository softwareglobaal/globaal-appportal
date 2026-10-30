# Laptop inrichten voor De Dagbundelaar

Versie 1.0 (28-10-2026). Opdracht voor Claude 1 op Mehdi's laptop. Doel: de wachten
die op een Mac moeten draaien (WhatsApp, telefoon iPhone, foto's, Plaud, Dropbox-sync)
draaien voortaan op de laptop, zodat de zware pc niet meer nodig is.

Vaste regels bij deze opdracht:

- Nooit uitloggen of opnieuw inloggen bij Claude. Werk met het account dat er is.
- Niets wissen, niets versturen, niets betalen. Twijfel: stop en meld.
- Geen wachtwoord, sleutel of token in chat, git of dit document.
- De oude Mac blijft aan tot stap 8 op de laptop groen is.
- Wat alleen Mehdi kan (een schakelaar in Systeeminstellingen, een aanmelding bij
  Plaud in de browser), staat als "Mehdi:" en is één klik of één aanmelding.

Melding achteraf: zet per stap ok of fout, met de foutregel, op het bord als
werkverslag, of geef het terug aan Mehdi in vijf regels.

## Stap 1. Rondkijken, nog niets wijzigen

Controleer en noteer:

- `sw_vers`, vrije schijfruimte (`df -h ~`).
- Bestaan `~/dev/globaal-appportal` en `~/dev/driehoeksoverleg`? Zo niet: klonen
  uit github.com/softwareglobaal (gh is aangemeld als Mehdi; `gh auth status`).
- Staan er al taken in `~/Library/LaunchAgents` die beginnen met `be.globaal.`?
- Zijn WhatsApp (Mac-app), Foto's met iCloud-fotobibliotheek en Dropbox aanwezig,
  en staat de map `~/TKN-buro Dropbox/Data uit Mehdi` er?
- Python 3.14 op `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`,
  de Command Line Tools (`xcode-select -p`), Homebrew en `/opt/homebrew/bin/gh`.
- Werkt `ssh -o BatchMode=yes globaal true` (de VM-toegang die alle wachten gebruiken)?

## Stap 2. Wat ontbreekt aanvullen

- Repo's: `git -C ~/dev/globaal-appportal pull --rebase origin main`.
- Python 3.14 of Command Line Tools ontbreken: installeer ze (python.org-installer,
  `xcode-select --install`).
- VM-toegang ontbreekt: de sleutel staat op de oude Mac (`~/.ssh`, regel `Host globaal`
  in `~/.ssh/config`). Mehdi: zet die twee bestanden met AirDrop over. Claude 1 zet
  daarna de rechten op 600 en test opnieuw. De sleutel nooit in chat plakken.

## Stap 3. WhatsApp en telefoon iPhone

- Mehdi, eenmalig op de iPhone: Instellingen, Telefoon, Bellen op andere apparaten,
  aan, en de laptop aanvinken. Zo komen de iPhone-oproepen in de oproepgeschiedenis
  van de laptop.
- WhatsApp op de laptop openen en aangemeld laten.
- `zsh ~/dev/globaal-appportal/mijnagents-runner/mac/uitrol_mac_gesprekken.sh`
  (installeert de helper MacGesprekkenKopie, de wachten blijven nog uit).
- Mehdi: Systeeminstellingen, Privacy en beveiliging, Volledige schijftoegang,
  MacGesprekkenKopie aanzetten (het pad meldt het script).
- `... uitrol_mac_gesprekken.sh proef`, en pas bij ok `... uitrol_mac_gesprekken.sh aan`.
- Controle: `... uitrol_mac_gesprekken.sh controleer`.

## Stap 4. Foto's (iCloud-wacht)

- `zsh ~/dev/globaal-appportal/mijnagents-runner/mac/uitrol_icloud_wacht.sh`
  (vraagt het Mac-wachtwoord voor sudo; dat typt Mehdi zelf).
- `... uitrol_icloud_wacht.sh --controleer` moet "gelijk" melden.
- Mehdi: Volledige schijftoegang voor iCloudWacht.app aanzetten
  (`/Library/Application Support/iCloudWacht/iCloudWacht.app`).

## Stap 5. Plaud

- `python3 ~/dev/globaal-appportal/mijnagents-runner/plaud/plaud_login.py`
- Mehdi: in het browservenster dat opengaat aanmelden bij Plaud (alleen Plaud, niet Claude).
- `zsh ~/dev/globaal-appportal/mijnagents-runner/planning/mac/plaud_launchd_zetten.sh`

## Stap 6. Dropbox-sync (Data uit Mehdi)

- Kopieer `mijnagents-runner/planning/mac/data_uit_mehdi_sync.sh` naar
  `~/bin/data_uit_mehdi_sync.sh` (uitvoerbaar) en neem de launchd-taak
  `be.globaal.mijnagents.data-uit-mehdi` over van de oude Mac (elke 30 minuten).
- Eén keer met de hand draaien en het logboek
  `~/Library/Logs/mijnagents-data-uit-mehdi.log` nakijken.

## Stap 7. Laptop wakker houden

Niet verplicht: de wachten halen na een slaap tot zestig dagen in. Wil Mehdi het toch:
`sudo pmset -c sleep 0` (alleen op netstroom).

## Stap 8. Proef en overdracht

- Op mijnagents.globaal.be, knop Bronnen: WhatsApp, Telefoon iPhone en Foto's
  moeten groen staan met een hartslag van de laptop.
- Pas dan op de oude Mac dezelfde taken uitzetten (`launchctl bootout`, niet wissen),
  na ja van Mehdi.
- Gedaan op 30-10-2026 (Claude 2): de VM-cronregels die `wacht_skelet.py` voor
  belwacht en whatsapp-wacht om 07:12 en 07:14 draaiden, staan in commentaar. Ze
  zetten elke ochtend de echte wachten van de laptop op rust met oude noden. Kopie
  van de vorige crontab: `~/crontab.voor-skelet-uit-20261030` op de VM.

## Stap 9. Driehoeksoverleg

Draai op de laptop het overleg over de bronnen (opdracht staat naast dit document):
`cd ~/dev/driehoeksoverleg && ./overleg.sh -C ~/dev/globaal-appportal -o ~/dev/samenwerking-codex/bronnen-20261028/rapport.md -t "Bronnen Dagbundelaar" < ~/dev/globaal-appportal/mijnagents-runner/docs/opdracht-driehoeksoverleg-bronnen.md`. Het verslag gaat
terug naar Mehdi, beslissing bovenaan, hoogstens vijf regels.

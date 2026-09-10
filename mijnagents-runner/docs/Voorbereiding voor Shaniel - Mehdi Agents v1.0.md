# Voorbereiding voor Shaniel: Mehdi Agents

Versie 1.0, 10-09-2026. Opgesteld door Claude Code op vraag van Mehdi.

Dit document bevat alles wat de agents op **mijnagents.globaal.be** nodig hebben
en wat alleen een mens kan doen: sleutels zetten, accounts koppelen, keuzes
maken. Elk punt zegt wat, waarom, waar het landt (naam van de instelling, nooit
de waarde), wie het kan, en hoe je nagaat dat het werkt. Sleutels komen nooit in
chat, mail of dit document; alleen in `~/appportal/.env` of
`~/appportal/mijnagents-data/.env` op de VM, of in de Keychain van Mehdi's Mac.

De stand van elk punt staat live op het bord onder "Wat de agents nodig hebben".
Zodra het punt opgelost is, verdwijnt het daar vanzelf bij de volgende ronde van
de agent.

## A. Sleutels en toegangen (Shaniel bereidt voor, Mehdi keurt goed)

| # | Wat | Waarom | Waar | Hoe nakijken |
|---|---|---|---|---|
| A1 | **Fathom-sleutel van Mehdi** | de sleutel op de VM is van Shaniel; Mehdi's eigen gesprekken zijn onzichtbaar | `FATHOM_API_KEYS` in `~/appportal/.env`, komma-gescheiden, Mehdi's sleutel erbij (Fathom: Settings, API) | Fathomwacht-kaart: nood verdwijnt; "Gesprekken" toont zijn gesprekken |
| A2 | **Privé-Dropbox voor het archief** | het Dropbox-token van de stack is Siyans account en ziet Mehdi's privémap niet; archieven (Fathom, Plaud, locatie) staan nu op de VM | een Dropbox-app op Mehdi's eigen account; `DROPBOX_PRIVE_APP_KEY`, `DROPBOX_PRIVE_APP_SECRET`, `DROPBOX_PRIVE_REFRESH_TOKEN` en `FATHOM_ARCHIEF_PAD` in `~/appportal/.env` | Fathomwacht en Locatiewacht: nood "geen privé-Dropbox" verdwijnt |
| A3 | **Dropbox-app van de stack opnieuw autoriseren** met scope `account_info.read` | het token mist die scope; het contract-dashboard werkt nu via een omweg (`DROPBOX_PATH_ROOT_NS`) | Dropbox App Console, Permissions, dan nieuwe autorisatie; nieuw `DROPBOX_REFRESH_TOKEN` in `~/appportal/.env` | Contractmaker-kaart: nood verdwijnt |
| A4 | **Hotmail app-wachtwoord** | de privé-mailwacht kan niet inloggen zonder | Microsoft-account, Beveiliging, App-wachtwoorden (vereist tweestapsverificatie); op Mehdi's Mac: `security add-generic-password -s onemail -a mehdichegini@hotmail.com -w` | Mailwacht privé: status van rust naar waakt |
| A5 | **Telegram-bot** voor De Bode | Mehdi wil berichten op zijn telefoon en wil kunnen antwoorden; Zoom-chat werkt nu al | BotFather op Telegram: bot aanmaken; `TELEGRAM_BOT_TOKEN` en `TELEGRAM_CHAT_ID` in `~/appportal/mijnagents-data/.env`; Mehdi stuurt één keer /start | Bode-kaart: "via telegram" in de status |
| A6 | **Zoom-scopes lezen** | de Zoomwacht wil chat en meetings lezen; de koppeling mag nu alleen chat sturen | Zoom Marketplace, de Server-to-Server-app van de stack: scopes `chat_message:read:admin`, `meeting:read:admin` (of gebruikersvarianten) erbij | Zoomwacht: nood verdwijnt na de eerste run |
| A7 | **Xelion-lijnen** | de Belwacht moet weten welke lijnen van Mehdi zijn (werk en privé) en of de gesprekslijst leesbaar is | bevestigen in Xelion; sleutels `XELION_*` staan al in `~/appportal/.env` | Belwacht: nood verdwijnt |
| A8 | **Plaud-routine** op claude.ai | de VM kan Plaud niet oplijsten; een geplande Claude-taak met de Plaud- en Dropbox-connector moet de transcripten in Dropbox zetten | opdracht staat letterlijk in `mijnagents-runner/werkwijze/plaud-routine.md`; inplannen op Mehdi's claude.ai-account, 06:30 en 12:30 | inbox-map `Work All/000 AI Opzet/Mehdi Agents/Plaud inbox` vult; Plaudwacht van rust naar waakt |
| A9 | **Plaud-accounts van Angela, Siyan en Shaniel** | ook die opnames moeten in het logboek | per account een eigen connector en routine, of een Plaud-team; keuze van Mehdi | Plaudwacht: nood verdwijnt |
| A10 | **Health Auto Export** | de Gezondheidswacht ziet geen Apple Watch-gegevens | app op de iPhone: export naar iCloud Drive aanzetten (map die `~/bin/gezondheid.py` leest); iCloud Drive op de Mac synct | Gezondheidswacht: "gegevens aanwezig" |
| A11 | **WhatsApp-exports** | geen API; alleen exports | WhatsApp, gesprek, "Chat exporteren" zonder media, naar `~/Documents/WhatsApp exports` op de Mac; Mehdi kiest welke gesprekken | WhatsApp-wacht: nood verdwijnt zodra de Mac-runner er is |
| A12 | **Bellen bij alarm** | Mehdi wil gebeld worden bij iets dringends | dienst kiezen: Twilio (nummer + sleutels) of de Xelion-API; daarna bouwt Claude Code het in De Bode | Bode: nood "bellen" verdwijnt |

## B. Kennis die alleen Mehdi heeft (Shaniel verzamelt, Mehdi bevestigt)

| # | Wat | Waar het landt |
|---|---|---|
| B1 | **Tabel Betrokken personen**: naam, e-mail, afdeling, rol, bijzonderheden van alle collega's en vaste contacten (het dashboard met namen per afdeling) | de werkwijze van De Fathomwacht op het bord (knop "Werkwijze bewerken"); één plek, alle agents lezen ze daar |
| B2 | **Afzenders met hoog belang** voor de mailwachten: boekhouder, bank, notaris, advocaat, verzekeraar, overheid, arts | de werkwijze van De Mailwacht mch@ |
| B3 | **43 agenda-afspraken zonder Nova-code** | titels rechtzetten volgens de afspraak met Nova (`[HA-KB]` enz.); lijst staat als signaal op het bord |

## C. Keuzes die Mehdi maakt (uit het ontwikkelverslag van De Ontwikkelaar, W37)

| # | Keuze | Advies |
|---|---|---|
| C1 | Tokenplafond per agent (de eerste ronde van De Ontwikkelaar kostte 452.000 tokens) | ja: plafond per ronde in de omgeving van elke runner |
| C2 | MCP Apps in het contract-dashboard (keuzes en herkomst rechtstreeks bevestigbaar) | later; eerst de bronnen op orde |
| C3 | Wekelijkse opruimbeurt van de Docker-cache op de VM (schijf stond op 100 %, nu 94 %) | ja: cronregel `docker image prune -f; docker builder prune -f` elke zondag |
| C4 | Wie de Plaud-routine en de Telegram-bot beheert | Shaniel bereidt voor, Mehdi koppelt op zijn account |

## D. Hoe de agents werken (om te begrijpen wat je voorbereidt)

- Elke agent heeft op zijn kaart een **werkwijze**: wat hij weet, wat hij doet
  in volgorde, wat hij nooit doet, wat Mehdi beslist, en wat hij nodig heeft.
  Dat is de waarheid; code volgt de werkwijze.
- **Noden**: elke agent meldt zelf bij zijn hartslag wat bij hem niet werkt; het
  bord toont dat in één sectie. Opgelost is opgelost, zonder handwerk.
- **Niets verandert zonder Mehdi's ja**: een agent stelt voor, Mehdi keurt goed
  op het bord, de uitvoerder doet het.
- **Privé blijft privé**: agents met de privé-vlag en alles wat ze maken
  bestaan alleen voor Mehdi; collega's zien ze niet.
- Runners draaien op de VM (cron) of op Mehdi's Mac (launchd) als de bron
  alleen daar staat (foto's, gezondheid, mail via Keychain). Mac-runners praten
  met het bord over https met een token in `~/.config/mijnagents/token`.

## E. Volgorde die het meeste oplevert

1. A1 (Fathom-sleutel) en B1 (personentabel): daarna herkent de Fathomwacht wie
   wie is en komen gesprekken in het logboek en bij de Contractmaker.
2. A8 (Plaud-routine): werfbezoeken en plaatsbezoeken komen binnen.
3. A5 (Telegram): Mehdi krijgt de Bode op zijn telefoon en kan antwoorden.
4. A4 (hotmail) en A10 (Health Auto Export): privé-mail en lichaam in het logboek.
5. A2 en A3 (Dropbox): archieven op de juiste plek en het contract-dashboard zonder omweg.
6. De rest.

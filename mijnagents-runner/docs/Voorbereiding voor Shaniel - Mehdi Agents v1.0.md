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
| B3 | **43 agenda-afspraken zonder code** | titels rechtzetten volgens Mehdi's titelconventie (`[HA-KB]` enz.); lijst staat als signaal op het bord |
| B4 | **Live verkeersinfo voor de reistijdblokken** (code voor Google Routes staat klaar; kost 0 euro bij ons gebruik, 5.000 gratis aanvragen per maand) | Shaniel volgt "Handleiding Google Routes-sleutel voor Shaniel v1.0.md" (zelfde map). Project onder mehdiprivewerkagenda@gmail.com, niet onder hr-assistant-calendar. Sleutel als GOOGLE_ROUTES_KEY in ~/appportal/.env |
| B5 | **Projectnummer op elke klantafspraak, adres bij elke buitenafspraak** (adres komt uit de H-A projectmapnaam, regel A13) | Mehdi past titels aan; UNABO/Harmoniebouw/Contrax-mappen krijgen dezelfde naamregel als ze meegelezen moeten worden |

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

## F. Stand op 11-09-2026 (gemeten op de server, alleen namen van sleutels)

**Gedaan:** B4 Google Routes (11-09), A1 Fathom (twee sleutels), A2 prive-Dropbox (DROPBOX_PRIVE_*), A5 Telegram (bot + chat-id, tweerichting werkt), C3 Docker-opruimbeurt (cron zondag 04:30), C4 (Telegram).

**Open, in volgorde van opbrengst:**

1. B4 Google Routes: GEDAAN op 11-09 (sleutel staat op de server, blokken zeggen "live verkeer Google").
2. A3 Dropbox-app van de stack opnieuw autoriseren met scope account_info.read (de omweg DROPBOX_PATH_ROOT_NS staat nog).
3. A4 Hotmail app-wachtwoord in de Keychain van de Mac van Mehdi (Mailwacht prive staat stil).
4. A10 Health Auto Export op de iPhone naar iCloud Drive (Gezondheidswacht ziet niets).
5. A8 en A9 Plaud-routine op claude.ai, daarna de accounts van Angela, Siyan en Shaniel.
6. A6 Zoom-scopes lezen (chat_message:read:admin, meeting:read:admin) op de Server-to-Server-app.
7. A7 Xelion: bevestigen welke van de vijf lijnen van Mehdi zijn (werk en prive).
8. A12 Bellen bij alarm: Twilio-account met nummer; sleutels in mijnagents-data/.env.
9. A11 WhatsApp-exports in ~/Documents/WhatsApp exports op de Mac (Mehdi kiest de gesprekken).
10. B1 Tabel Betrokken personen aanvullen in de werkwijze van De Fathomwacht; B2 afzenders met hoog belang.
11. B3 en B5: 43 afspraken zonder code en de titels zonder projectnummer of adres (signaal op het bord); dit is de agenda van Mehdi, Shaniel kan de lijst voorbereiden.

## G. Data uit Mehdi (12-09-2026)

Alle data van de agents komt samen in de Dropbox-map **Data uit Mehdi** (hoogste niveau van Mehdi's Dropbox):
submappen Fathom, Plaud, Locatie en Bord. De server-tokens komen daar niet bij (Siyans account ziet de map niet,
Mehdi's app heeft alleen een app-map); daarom haalt een taak op Mehdi's Mac (launchd
be.globaal.mijnagents.data-uit-mehdi, script ~/bin/data_uit_mehdi_sync.sh) elke 30 minuten het archief van de
VM (mijnagents-data) op, alleen toevoegen, nooit wissen. Mehdi besliste: alles erin, ook privé. Delen met Shaniel
gebeurt later per submap (Fathom, Plaud, Bord wel; Locatie en gezondheid niet), en niet met Siyans account.
Wil Mehdi later dat de VM rechtstreeks schrijft: Dropbox-app met Full Dropbox aanmaken en
`dropbox_prive_koppelen.py --nieuw --basis "/Data uit Mehdi"` draaien (code staat klaar).

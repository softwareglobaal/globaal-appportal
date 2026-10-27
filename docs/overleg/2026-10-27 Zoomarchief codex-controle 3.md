**Voor Mehdi: niet klaar.** De zes suites slagen volgens jouw Mac-meting, maar mijn geheugenproeven krijgen nog `dekking: ja` terwijl een opname niet bewezen in Dropbox staat. Voorstel 40 blijft een risico van ernst **hoog**: goedkeuren wijzigt Zoom niet automatisch, maar het open voorstel geeft nog steeds de oude handmatige wisinstructie.

**Voor Claude en Shaniel**

- **3 — blokkerend, niet hersteld.** `zoom_archief.py:467`: een bestand zonder id én status geeft direct `dekking: ja`. Registreer elk gezien bestand met een stabiele sleutel; kopieer het of blokkeer dekking.
- **5 — hoog, deels.** `zoom_account.py:634`: bij actuele dekking `nee` is ZA-01 onbekend. Na een vroege archieffout blijft een eerder `ja` maximaal 48 uur geldig. Trek dat `ja` bij een mislukte ronde direct in.
- **6 — hoog, hersteld in code.** `zoom_archief.py:223`: zonder vastgelegd account-id schrijft de agent niet; een ander id wordt geweigerd. Verifieer de pin bij uitrol.
- **7 — hoog, deels.** `zoom_archief.py:303`: de Dropbox-lijst krijgt geen harde deadline. Mijn proef liet de klok de grens passeren; de ronde schreef toch `dekking: ja`. Begrens elke netwerkaanroep.
- **11 — blokkerend, deels.** `zoom_archief.py:336`: een eerder als gemist aanvaarde opname kan terugkeren, gekopieerd worden en opnieuw verdwijnen. De oude goedkeuring geldt dan opnieuw; de volgende dag volgt `ja`. Bind goedkeuring aan één verliesgeval.
- **12 — hoog, deels.** `zoom_account.py:859`, `app.py:2285`: voorstel 40 blijft open; de besluitknop toetst dekking niet. Laat 40 weigeren en controleer actuele dekking bij een nieuw besluit.
- **13 — middel, deels.** `zoom_archief.py:323`: mislukte verzending wordt terecht herhaald. Werkt de bord-API terwijl de lokale bordlezing faalt, dan kunnen elk uur dubbele voorstellen ontstaan. Verzend pas na geslaagde lezing.
- **14 — laag, deels.** `zoom_archief.py:328`: gelijktijdige sleutelbotsingen worden geweigerd; een latere botsing kan een oude goedkeuring erven. Bewaar welke id bij de sleutel hoort.
- **15 — blokkerend, deels.** `zoom.py:528`, `zoom_archief.py:470`: een lege bestandslijst blokkeert nu. Verdwijnt die meeting vóór de volgende volledige ronde, dan volgt alsnog `ja`. Bewaar onopgeloste meetings.
- **16 — hoog, hersteld onder voorwaarde.** `zoom_archief.py:223`: een vreemd account met `/Fathom data` passeert de pin niet. De pin moet bij uitrol aantoonbaar ingesteld zijn.
- **17 — hoog, deels.** `zoom_archief.py:469`: korte rondes bewaren onvolledigheid, maar een volledige ronde wist een inmiddels verdwenen geval. Ook `opname.json` mist de harde deadline. Herstel dit samen met 15 en 7.

Gedaan: diff en eerdere bevindingen gelezen; niets gewijzigd.  
Nagekeken: hier namen 3/3 en agentnorm 28/28; jouw Mac-uitslagen voor de vier Zoom-suites zijn 38/12/113/63. Gerichte geheugenproeven braken de huidige code.  
Open: dekking, voorstel 40 en deadlines herstellen en hertesten.

**BESLISSING: niet klaar.**
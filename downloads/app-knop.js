// Zet in de Authentik-launcher een knop "Download de app" in de kopbalk, links
// naast het belletje van de notificatielade. Wordt door nginx in de HTML van
// /if/user/ geinjecteerd (sub_filter).
//
// De knop wijst altijd naar /app/download; nginx kiest daar het juiste bestand
// op basis van het besturingssysteem, zodat de gebruiker niets hoeft te kiezen.
//
// De kopbalk zit in de shadow DOM van <ak-nav-buttons> en wordt door lit
// opnieuw getekend (bijvoorbeeld als het aantal meldingen verandert). Daarom
// zoeken we door shadow roots heen en zetten we de knop terug als lit hem
// weghaalt. We gebruiken de eigen PatternFly-klassen van Authentik, zodat de
// knop dezelfde vorm en kleur krijgt als de knop "Admin interface" ernaast.
(function () {
  "use strict";

  var ID = "globaal-app-knop";
  var MAX_POGINGEN = 40; // ongeveer 20 seconden; daarna is de kopbalk er niet.

  function inApp() {
    return !!window.__GLOBAAL_APP__;
  }

  function mobiel() {
    return /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
  }

  // Zoekt door gewone DOM en shadow roots heen naar het eerste element dat past.
  function zoekDiep(wortel, selector) {
    var gevonden = wortel.querySelector(selector);
    if (gevonden) return gevonden;

    var kinderen = wortel.querySelectorAll("*");
    for (var i = 0; i < kinderen.length; i++) {
      if (kinderen[i].shadowRoot) {
        var dieper = zoekDiep(kinderen[i].shadowRoot, selector);
        if (dieper) return dieper;
      }
    }
    return null;
  }

  function maakItem() {
    var item = document.createElement("div");
    item.id = ID;
    item.className = "pf-c-page__header-tools-item";

    var link = document.createElement("a");
    link.className = "pf-c-button pf-m-secondary";
    link.href = "/app/download";
    link.title = "Globaal als programma op je computer";

    var icoon = document.createElement("i");
    icoon.className = "fas fa-download";
    icoon.setAttribute("aria-hidden", "true");
    icoon.style.marginRight = "0.5rem";

    link.appendChild(icoon);
    link.appendChild(document.createTextNode("Download de app"));
    item.appendChild(link);
    return item;
  }

  // Plaatst de knop links van het belletje; is de notificatielade uitgeschakeld,
  // dan vooraan in de knoppenrij.
  function plaats(bel) {
    var groep = bel.parentElement;
    if (!groep || groep.querySelector("#" + ID)) return;
    groep.insertBefore(maakItem(), bel);
    return groep;
  }

  function bewaak(groep, bel) {
    var waarnemer = new MutationObserver(function () {
      if (!groep.querySelector("#" + ID) && groep.contains(bel)) {
        groep.insertBefore(maakItem(), bel);
      }
    });
    waarnemer.observe(groep, { childList: true });
  }

  function probeer(pogingen) {
    var knop = zoekDiep(document, "#notification-drawer-toggle-button");
    var anker = knop ? knop.closest(".pf-c-page__header-tools-item") : null;

    if (!anker) {
      // Geen belletje: dan naast de instellingen of vooraan in de rij.
      var groep = zoekDiep(document, ".pf-c-page__header-tools-group");
      if (groep && !groep.querySelector("#" + ID)) {
        groep.insertBefore(maakItem(), groep.firstChild);
        bewaak(groep, groep.children[1]);
        return;
      }
    } else {
      var rij = plaats(anker);
      if (rij) bewaak(rij, anker);
      return;
    }

    if (pogingen < MAX_POGINGEN) {
      setTimeout(function () {
        probeer(pogingen + 1);
      }, 500);
    } else {
      console.warn("Globaal: kopbalk van de launcher niet gevonden, geen downloadknop geplaatst.");
    }
  }

  function start() {
    // In de app zelf heeft de knop geen zin: die is al gedownload.
    if (inApp() || mobiel()) return;
    probeer(0);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();

// Zet rechtsboven in de Authentik-launcher een knop "Download de app".
// Wordt door nginx in de HTML van /if/user/ geinjecteerd (sub_filter).
// De knop wijst altijd naar /app/download; nginx kiest daar het juiste bestand
// op basis van het besturingssysteem, zodat de gebruiker niets hoeft te kiezen.
(function () {
  "use strict";

  var ID = "globaal-app-knop";
  if (document.getElementById(ID)) return;

  function mobiel() {
    return /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
  }

  function maak() {
    if (document.getElementById(ID)) return;

    var link = document.createElement("a");
    link.id = ID;
    link.href = "/app/download";
    link.textContent = "Download de app";
    link.title = "Globaal als programma op je computer";

    link.style.cssText = [
      "position:fixed",
      "top:12px",
      "right:16px",
      "z-index:2147483647",
      "display:inline-flex",
      "align-items:center",
      "gap:7px",
      "height:30px",
      "padding:0 13px",
      "border-radius:15px",
      "background:#059669",
      "color:#fff",
      "font:600 13px/1 -apple-system,'Segoe UI',system-ui,sans-serif",
      "text-decoration:none",
      "box-shadow:0 2px 8px rgba(0,0,0,.28)",
    ].join(";");

    // Pijl-omlaag-icoon, meegetekend zodat we geen externe bron nodig hebben.
    var icoon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icoon.setAttribute("viewBox", "0 0 24 24");
    icoon.setAttribute("width", "14");
    icoon.setAttribute("height", "14");
    icoon.setAttribute("fill", "none");
    icoon.setAttribute("stroke", "currentColor");
    icoon.setAttribute("stroke-width", "2.2");
    icoon.setAttribute("stroke-linecap", "round");
    icoon.setAttribute("stroke-linejoin", "round");
    var pad = document.createElementNS("http://www.w3.org/2000/svg", "path");
    pad.setAttribute("d", "M12 4v11m0 0l-4.5-4.5M12 15l4.5-4.5M4 20h16");
    icoon.appendChild(pad);
    link.insertBefore(icoon, link.firstChild);

    document.body.appendChild(link);
  }

  function start() {
    // In de app zelf heeft de knop geen zin: die is al gedownload. De desktop-app
    // zet deze vlag in elke pagina die ze laadt.
    if (window.__GLOBAAL_APP__) return;
    if (mobiel()) return;
    maak();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();

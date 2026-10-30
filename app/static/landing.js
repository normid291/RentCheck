/* Tenura landing page.
 *
 * The page is static on purpose: the only state-dependent part is the hero CTA,
 * which changes once common.js has resolved the session. Everything else is
 * native HTML (details/summary for the FAQ, anchor links for the sections).
 */
(function () {
  "use strict";

  Tenura.ready.then(function (user) {
    if (!user) return;

    var primary = document.getElementById("heroPrimary");
    if (primary) primary.textContent = "Go to analyser";

    var secondary = document.getElementById("heroSecondary");
    if (secondary) {
      secondary.textContent = "View your history";
      secondary.setAttribute("href", "/history");
    }
  });
})();

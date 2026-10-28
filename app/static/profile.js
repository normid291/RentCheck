/* Tenura — the signed-in user's profile.
 *
 * Read-only view of the account: identity, how it signs in, and a way into
 * History. It uses the session already resolved by common.js (Tenura.ready), so
 * there is no extra request and nothing here can change server state — password
 * changes deliberately route through the existing "Forgot password" flow rather
 * than inventing a new endpoint.
 */
(function () {
  "use strict";

  var esc = Tenura.escapeHtml;
  var root = document.getElementById("profileRoot");

  var GOOGLE_MARK =
    '<span class="google-mark" aria-hidden="true">' +
    '<svg viewBox="0 0 18 18" width="16" height="16">' +
    '<path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"/>' +
    '<path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z"/>' +
    '<path fill="#FBBC05" d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33z"/>' +
    '<path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"/>' +
    "</svg></span>";

  var CHECK_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6L9 17l-5-5"/></svg>';

  function signInMethodLabel(user) {
    if (user.has_password && user.google_linked) return "Email & password · Google";
    if (user.google_linked) return "Google";
    return "Email & password";
  }

  function identityCard(user) {
    var verified = user.is_verified
      ? '<span class="pill ok">' + CHECK_SVG + "Verified</span>"
      : '<span class="pill warn">Unverified</span>';

    var memberSince = user.created_at
      ? '<span class="identity-meta">Member since ' + esc(Tenura.formatDate(user.created_at)) + "</span>"
      : "";

    return (
      '<div class="panel profile-card identity-card">' +
      '<div class="identity-main">' +
      Tenura.avatarHtml(user, "avatar-xl") +
      '<div class="identity-id">' +
      '<h2 class="identity-name">' + esc(Tenura.displayName(user)) + "</h2>" +
      '<span class="identity-email" title="' + esc(user.email) + '">' + esc(user.email) + "</span>" +
      '<div class="identity-pills">' + verified + memberSince + "</div>" +
      "</div>" +
      "</div>" +
      '<p class="identity-method">Signed in with <strong>' + esc(signInMethodLabel(user)) + "</strong>.</p>" +
      "</div>"
    );
  }

  function passwordRow(user) {
    if (user.has_password) {
      return (
        '<div class="setting-row">' +
        '<span class="setting-icon" aria-hidden="true">' + keyIcon() + "</span>" +
        '<div class="setting-body">' +
        '<div class="setting-title">Password</div>' +
        '<p class="setting-desc">You sign in with an email address and a password.</p>' +
        "</div>" +
        '<a class="setting-action" href="/login?next=' + encodeURIComponent("/profile") + '">Change password</a>' +
        "</div>"
      );
    }
    return (
      '<div class="setting-row">' +
      '<span class="setting-icon" aria-hidden="true">' + keyIcon() + "</span>" +
      '<div class="setting-body">' +
      '<div class="setting-title">No password set</div>' +
      '<p class="setting-desc">This account signs in with Google. You can add a password any time.</p>' +
      "</div>" +
      '<a class="setting-action" href="/login?next=' + encodeURIComponent("/profile") + '">Set a password</a>' +
      "</div>"
    );
  }

  function googleRow(user) {
    var connected = user.google_linked;
    var action;
    if (connected) {
      action = '<span class="pill ok">' + CHECK_SVG + "Connected</span>";
    } else if (Tenura.googleEnabled()) {
      action = '<button class="setting-action" id="connectGoogle" type="button">Connect</button>';
    } else {
      action = '<span class="pill muted">Not connected</span>';
    }
    return (
      '<div class="setting-row">' +
      '<span class="setting-icon google" aria-hidden="true">' + GOOGLE_MARK + "</span>" +
      '<div class="setting-body">' +
      '<div class="setting-title">Google</div>' +
      '<p class="setting-desc">' +
      (connected
        ? "Google sign-in is linked to this account."
        : "Link Google to sign in with one tap next time.") +
      "</p>" +
      "</div>" +
      action +
      "</div>"
    );
  }

  function securityCard(user) {
    return (
      '<div class="panel profile-card">' +
      '<div class="card-head"><h2>Sign-in &amp; security</h2>' +
      '<p class="card-sub">How you get into your account.</p></div>' +
      passwordRow(user) +
      googleRow(user) +
      "</div>"
    );
  }

  function activityCard() {
    return (
      '<div class="panel profile-card">' +
      '<div class="card-head"><h2>Your activity</h2>' +
      '<p class="card-sub">Agreements you have analysed while signed in.</p></div>' +
      '<div class="setting-row">' +
      '<span class="setting-icon" aria-hidden="true">' + clockIcon() + "</span>" +
      '<div class="setting-body">' +
      '<div class="setting-title">Analysis history</div>' +
      '<p class="setting-desc">Open, rename, or delete a saved analysis.</p>' +
      "</div>" +
      '<a class="setting-action" href="/history">View history</a>' +
      "</div>" +
      '<div class="setting-row">' +
      '<span class="setting-icon" aria-hidden="true">' + searchIcon() + "</span>" +
      '<div class="setting-body">' +
      '<div class="setting-title">Analyse an agreement</div>' +
      '<p class="setting-desc">Paste text or upload a document to check it.</p>' +
      "</div>" +
      '<a class="setting-action" href="/">New analysis</a>' +
      "</div>" +
      "</div>"
    );
  }

  function sessionCard() {
    return (
      '<div class="panel profile-card session-card">' +
      '<div class="setting-body">' +
      '<div class="setting-title">Sign out</div>' +
      '<p class="setting-desc">End your session on this device.</p>' +
      "</div>" +
      '<button class="btn btn-ghost" id="signOutBtn" type="button">Log out</button>' +
      "</div>"
    );
  }

  function keyIcon() {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="15" r="4"/><path d="M10.85 12.15 19 4"/><path d="M18 5l2 2"/><path d="M15 8l2 2"/></svg>';
  }
  function clockIcon() {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>';
  }
  function searchIcon() {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M16.5 16.5 20.5 20.5"/></svg>';
  }

  function render(user) {
    root.innerHTML =
      identityCard(user) +
      securityCard(user) +
      activityCard() +
      sessionCard();

    var signOut = document.getElementById("signOutBtn");
    if (signOut) signOut.addEventListener("click", Tenura.logout);

    var connect = document.getElementById("connectGoogle");
    if (connect) {
      connect.addEventListener("click", function () {
        connect.disabled = true;
        Tenura.startGoogleSignIn();
      });
    }
  }

  Tenura.ready.then(function (user) {
    if (!user) {
      window.location.href = "/login?next=" + encodeURIComponent("/profile");
      return;
    }
    render(user);
  });
})();

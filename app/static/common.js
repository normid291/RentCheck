/* Tenura — shared front-end helpers.
 *
 * Loaded before any page script and exposed as window.Tenura. Three jobs:
 *
 *   1. apiFetch() — every call to our API goes through this. It exists because
 *      the host can cold-start and answer with a 503 (or an HTML error page
 *      from its proxy) instead of JSON. Instead of dumping that on the user, it
 *      retries with a short backoff and says "Waking up the server…" while it
 *      does. Genuine errors (400/401/403/404/429) are NOT retried — they are
 *      real answers and are surfaced immediately.
 *   2. The header's session state (Log in / Sign up, or History / Log out).
 *   3. Small formatting helpers shared by the pages.
 *
 * No tokens are ever kept here. The session is an httpOnly cookie the page
 * cannot read, which is the point.
 */
(function () {
  "use strict";

  var MAX_ATTEMPTS = 5;
  var STATUS_ID = "tenuraStatus";

  /* ---------- status banner (injected once, used by apiFetch) ---------- */

  function statusEl() {
    var el = document.getElementById(STATUS_ID);
    if (el) return el;
    el = document.createElement("div");
    el.id = STATUS_ID;
    el.className = "tenura-status";
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    el.hidden = true;
    document.body.appendChild(el);
    return el;
  }

  function setStatus(message) {
    var el = statusEl();
    if (!message) {
      el.hidden = true;
      el.textContent = "";
      return;
    }
    el.textContent = message;
    el.hidden = false;
  }

  /* ---------- errors ---------- */

  function ApiError(message, status, body) {
    this.name = "ApiError";
    this.message = message;
    this.status = status;
    this.body = body || null;
  }
  ApiError.prototype = Object.create(Error.prototype);
  ApiError.prototype.constructor = ApiError;

  // Marker for "the answer was not usable — try again" (503, HTML instead of
  // JSON, or the request never reached the server at all).
  function RetryableError(message) {
    this.name = "RetryableError";
    this.message = message;
  }
  RetryableError.prototype = Object.create(Error.prototype);
  RetryableError.prototype.constructor = RetryableError;

  function messageFromBody(body, status) {
    if (body) {
      var detail = body.detail;
      if (typeof detail === "string" && detail) return detail;
      if (detail && typeof detail === "object") {
        if (typeof detail.message === "string" && detail.message) return detail.message;
      }
      if (typeof body.message === "string" && body.message) return body.message;
      if (typeof body.error === "string" && body.error) return body.error;
    }
    return "Request failed (HTTP " + status + ").";
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  /* ---------- apiFetch ---------- */

  function apiFetch(path, options) {
    var opts = Object.assign({ credentials: "same-origin" }, options || {});
    var headers = Object.assign({}, opts.headers || {});
    var isForm = typeof FormData !== "undefined" && opts.body instanceof FormData;
    if (opts.body && !isForm && typeof opts.body === "string" && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    opts.headers = headers;

    var attempt = 0;

    function next() {
      attempt += 1;
      return fetch(path, opts)
        .then(function (res) {
          var type = (res.headers.get("content-type") || "").toLowerCase();
          var isJson = type.indexOf("application/json") !== -1;

          if (res.status === 503) {
            throw new RetryableError("The server is waking up.");
          }
          if (res.ok && !isJson) {
            // A 200 that is not JSON means something upstream answered for us.
            throw new RetryableError("The server returned an unexpected page.");
          }
          if (res.ok) return res.json();

          if (!isJson) throw new RetryableError("The server returned an unexpected page.");
          return res
            .json()
            .catch(function () {
              return null;
            })
            .then(function (body) {
              throw new ApiError(messageFromBody(body, res.status), res.status, body);
            });
        })
        .catch(function (err) {
          var retryable =
            err instanceof RetryableError ||
            err.name === "TypeError" || // fetch rejects on network failure
            err.name === "AbortError";

          if (!retryable || attempt >= MAX_ATTEMPTS) throw err;

          setStatus(
            "Waking up the server, retrying… (" + attempt + " of " + (MAX_ATTEMPTS - 1) + ")"
          );
          return sleep(Math.min(1000 * Math.pow(2, attempt - 1), 5000)).then(next);
        });
    }

    return next()
      .then(function (data) {
        setStatus(null);
        return data;
      })
      .catch(function (err) {
        setStatus(null);
        if (err instanceof ApiError) throw err;
        throw new ApiError(
          "We couldn't reach the server. Please check your connection and try again.",
          0,
          null
        );
      });
  }

  /* ---------- small helpers ---------- */

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function titleCase(type) {
    return String(type || "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, function (c) {
        return c.toUpperCase();
      });
  }

  // Same thresholds the server uses (app/services/analysis_store.py).
  function riskFor(score) {
    var n = Number(score) || 0;
    if (n >= 55) return { key: "high", label: "High risk", cls: "risk-high", color: "var(--high)" };
    if (n >= 25) return { key: "medium", label: "Moderate risk", cls: "risk-medium", color: "var(--medium)" };
    return { key: "low", label: "Low risk", cls: "risk-low", color: "var(--brand)" };
  }

  // Mirrors app/services/scoring.py: a run is only banded low/moderate/high
  // when enough clauses were actually checked. A thin or degraded run is
  // "unknown" — never "low risk".
  var MIN_COVERAGE = 0.6;

  function bandFor(score, coverage, degraded) {
    var cov = coverage == null ? null : Number(coverage);
    var trustworthy = cov !== null && !isNaN(cov) && cov >= MIN_COVERAGE && !degraded;
    if (!trustworthy) return "unknown";
    var n = Number(score) || 0;
    if (n >= 40) return "high";
    if (n >= 15) return "moderate";
    return "low";
  }

  function riskForBand(band) {
    if (band === "high") return { key: "high", label: "High risk", cls: "risk-high", color: "var(--high)" };
    if (band === "moderate") return { key: "moderate", label: "Moderate risk", cls: "risk-medium", color: "var(--medium)" };
    if (band === "low") return { key: "low", label: "Low risk", cls: "risk-low", color: "var(--brand)" };
    return { key: "unknown", label: "Review needed", cls: "risk-unknown", color: "var(--medium)" };
  }

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function formatDate(iso) {
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return d.getDate() + " " + MONTHS[d.getMonth()] + " " + d.getFullYear();
  }

  function formatDateTime(iso) {
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return formatDate(iso) + ", " + String(d.getHours()).padStart(2, "0") + ":" +
      String(d.getMinutes()).padStart(2, "0");
  }

  function param(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  /* Where to send someone after signing in. Only same-site paths are honoured,
   * so a crafted ?next= cannot bounce a user to another host. This mirrors
   * app/services/redirects.py exactly; keep the two in step. */
  function safeNextPath(value, fallback) {
    fallback = fallback || "/";
    if (!value) return fallback;
    var v = String(value).trim();
    if (!v) return fallback;
    // Control characters (CRLF/header smuggling, odd URL handling).
    if (/[\u0000-\u001f\u007f]/.test(v)) return fallback;
    // Backslashes, raw or percent-encoded: browsers read "/\evil.com" as "//evil.com".
    if (/\\|%5c/i.test(v)) return fallback;
    // Must be a single-slash path, never scheme-relative.
    if (v.charAt(0) !== "/" || v.charAt(1) === "/") return fallback;
    // Reject anything that resolves off-origin.
    try {
      var resolved = new URL(v, window.location.origin);
      if (resolved.origin !== window.location.origin) return fallback;
    } catch (e) {
      return fallback;
    }
    return v;
  }

  function safeNext(fallback) {
    return safeNextPath(param("next"), fallback || "/");
  }

  /* ---------- header session state ---------- */

  var currentUser = null;
  var googleReady = false;
  // Whether the last /api/auth/me answer was actually received. false means the
  // server could not be reached, which is NOT the same as being signed out.
  var sessionKnown = false;

  /* ---------- identity helpers ---------- */

  function emailLocalPart(email) {
    return String(email || "").split("@")[0] || "";
  }

  /* A friendly display name. The app never asked for one, and Google's `name`
   * claim is not stored server-side, so we fall back to the email's local part,
   * tidied into words. `user.name` is honoured if a deployment ever supplies it. */
  function displayName(user) {
    if (!user) return "";
    if (user.name && String(user.name).trim()) return String(user.name).trim();
    var local = emailLocalPart(user.email);
    if (!local) return "Your account";
    return local
      .replace(/[._-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/\b\w/g, function (c) {
        return c.toUpperCase();
      });
  }

  function initials(user) {
    var source = displayName(user);
    var parts = source.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
      return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
    }
    if (source.length >= 2) return source.slice(0, 2).toUpperCase();
    return (source.charAt(0) || "?").toUpperCase();
  }

  /* An avatar. `user.picture` is used when present (a deployment may expose a
   * Google photo URL), otherwise a tinted initials chip. */
  function avatarHtml(user, extraClass) {
    var cls = "avatar" + (extraClass ? " " + extraClass : "");
    if (user && user.picture) {
      return (
        '<span class="' + cls + '" aria-hidden="true">' +
        '<img src="' + escapeHtml(user.picture) + '" alt="" loading="lazy" referrerpolicy="no-referrer" />' +
        "</span>"
      );
    }
    return (
      '<span class="' + cls + '" aria-hidden="true">' + escapeHtml(initials(user)) + "</span>"
    );
  }

  /* ---------- header account dropdown ---------- */

  var acctController = null;

  var CHEVRON =
    '<svg class="acct-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M6 9l6 6 6-6"/></svg>';

  function renderAuthSlot() {
    var slot = document.getElementById("authSlot");
    if (!slot) return;

    if (acctController) {
      acctController.destroy();
      acctController = null;
    }

    if (currentUser) {
      var email = currentUser.email || "";
      slot.innerHTML =
        '<div class="acct">' +
        '<button class="acct-btn" id="acctBtn" type="button" aria-haspopup="menu" ' +
        'aria-expanded="false" aria-controls="acctMenu" aria-label="Account menu for ' +
        escapeHtml(email) + '">' +
        avatarHtml(currentUser) +
        '<span class="acct-name">' + escapeHtml(displayName(currentUser)) + "</span>" +
        CHEVRON +
        "</button>" +
        '<div class="acct-menu" id="acctMenu" role="menu" aria-label="Account" hidden>' +
        '<div class="acct-menu-head">' +
        avatarHtml(currentUser, "avatar-lg") +
        '<span class="acct-menu-id">' +
        '<strong class="acct-menu-name">' + escapeHtml(displayName(currentUser)) + "</strong>" +
        '<span class="acct-menu-email" title="' + escapeHtml(email) + '">' +
        escapeHtml(email) + "</span>" +
        "</span>" +
        "</div>" +
        '<a class="acct-item" role="menuitem" href="/profile">Profile</a>' +
        '<a class="acct-item" role="menuitem" href="/history">History</a>' +
        '<button class="acct-item acct-item-danger" role="menuitem" id="logoutBtn" type="button">' +
        "Log out</button>" +
        "</div></div>";
    } else {
      slot.innerHTML =
        '<div class="acct">' +
        '<button class="acct-btn acct-btn-cta" id="acctBtn" type="button" aria-haspopup="menu" ' +
        'aria-expanded="false" aria-controls="acctMenu">' +
        '<span class="acct-name">Log in / Sign up</span>' +
        CHEVRON +
        "</button>" +
        '<div class="acct-menu" id="acctMenu" role="menu" aria-label="Account" hidden>' +
        '<a class="acct-item" role="menuitem" href="/login">Log in</a>' +
        '<a class="acct-item" role="menuitem" href="/signup">Sign up</a>' +
        "</div></div>";
    }

    var btn = document.getElementById("acctBtn");
    var menu = document.getElementById("acctMenu");
    if (btn && menu) acctController = mountAccountMenu(btn, menu);

    var logoutBtn = document.getElementById("logoutBtn");
    if (logoutBtn) logoutBtn.addEventListener("click", logout);
  }

  function closeAccountMenu() {
    if (acctController) acctController.close(false);
  }

  /* A small, self-contained menu controller: click or keys open it, arrow keys
   * move between items, Escape closes and returns focus to the button, and a
   * click (or Tab) anywhere else dismisses it. */
  function mountAccountMenu(btn, menu) {
    var items = [];
    var open = false;

    function refreshItems() {
      items = Array.prototype.slice.call(menu.querySelectorAll('[role="menuitem"]'));
    }

    function setOpen(next) {
      open = next;
      menu.hidden = !next;
      btn.setAttribute("aria-expanded", next ? "true" : "false");
      btn.classList.toggle("is-open", next);
      if (next) refreshItems();
    }

    function focusItem(index) {
      if (!items.length) return;
      var i = ((index % items.length) + items.length) % items.length;
      items[i].focus();
    }

    function close(returnFocus) {
      if (!open) return;
      setOpen(false);
      if (returnFocus) btn.focus();
    }

    function onButtonClick(event) {
      event.preventDefault();
      if (open) {
        close(false);
      } else {
        setOpen(true);
        focusItem(0);
      }
    }

    function onButtonKeydown(event) {
      if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        if (!open) setOpen(true);
        focusItem(0);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        if (!open) setOpen(true);
        focusItem(items.length - 1);
      }
    }

    function onMenuKeydown(event) {
      var current = items.indexOf(document.activeElement);
      if (event.key === "ArrowDown") {
        event.preventDefault();
        focusItem(current + 1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        focusItem(current - 1);
      } else if (event.key === "Home") {
        event.preventDefault();
        focusItem(0);
      } else if (event.key === "End") {
        event.preventDefault();
        focusItem(items.length - 1);
      } else if (event.key === "Escape") {
        event.preventDefault();
        close(true);
      } else if (event.key === "Tab") {
        close(false);
      }
    }

    function onDocumentClick(event) {
      if (!menu.contains(event.target) && !btn.contains(event.target)) close(false);
    }

    function onDocumentKeydown(event) {
      if (event.key === "Escape" && open) close(true);
    }

    btn.addEventListener("click", onButtonClick);
    btn.addEventListener("keydown", onButtonKeydown);
    menu.addEventListener("keydown", onMenuKeydown);
    document.addEventListener("click", onDocumentClick);
    document.addEventListener("keydown", onDocumentKeydown);

    return {
      close: close,
      destroy: function () {
        btn.removeEventListener("click", onButtonClick);
        btn.removeEventListener("keydown", onButtonKeydown);
        menu.removeEventListener("keydown", onMenuKeydown);
        document.removeEventListener("click", onDocumentClick);
        document.removeEventListener("keydown", onDocumentKeydown);
      },
    };
  }

  function loadSession() {
    return apiFetch("/api/auth/me")
      .then(function (data) {
        currentUser = data && data.user ? data.user : null;
        googleReady = !!(data && data.google);
        sessionKnown = true;
        renderAuthSlot();
        return currentUser;
      })
      .catch(function () {
        // A header that cannot load must not break the page. But it must also
        // not claim the visitor is signed out: that would bounce a logged-in
        // user to /login during a cold start. sessionKnown records the doubt.
        sessionKnown = false;
        renderAuthSlot();
        return null;
      });
  }

  /* Kept as the name boot() calls; the two are the same job. */
  function mountHeader() {
    return loadSession();
  }

  /* For pages that must have a session: resolves with the user, or sends them
   * to /login?next=... and resolves null. A transient failure is retried rather
   * than mistaken for a signed-out visitor, and if the server stays unreachable
   * it rejects so the page can show "try again" instead of logging them out. */
  function requireSession(nextPath) {
    function attempt(n, user) {
      if (user) return user;
      if (sessionKnown) {
        window.location.href = "/login?next=" + encodeURIComponent(nextPath);
        return null;
      }
      if (n >= 4) {
        throw new ApiError(
          "We couldn't confirm your session. Please check your connection and try again.",
          0,
          null
        );
      }
      return sleep(1000 * n).then(function () {
        return loadSession().then(function (u) {
          return attempt(n + 1, u);
        });
      });
    }
    return ready.then(function (user) {
      return attempt(1, user);
    });
  }

  /* Whether the server has Google sign-in configured. Read from /api/auth/me, so
   * a button is never shown on a deployment that cannot honour it. */
  function googleEnabled() {
    return googleReady;
  }

  /* The specific message for a Google failure, keyed by the short code the
   * callback puts in ?error=. Shared by /login and /signup so the two pages can
   * never show different things for the same failure. An unknown or absent code
   * is empty: no banner (a plain cancellation carries no code at all). */
  var GOOGLE_ERRORS = {
    google: "We couldn't complete that Google sign-in. Please try again.",
    google_unavailable:
      "We couldn't reach Google just now. Please check your connection and try again.",
    google_conflict:
      "That email is already linked to a different Google account. Please sign in the way you did before.",
  };

  function googleError() {
    return GOOGLE_ERRORS[param("error")] || "";
  }

  /* Which page hosts the button the visitor pressed, so the callback can return
   * them to it. Anything other than the sign-up page is treated as log-in. */
  function googleOrigin() {
    var path = String(window.location.pathname || "").replace(/\/+$/, "");
    return path === "/signup" ? "/signup" : "/login";
  }

  /* Hand the browser to Google. This is a full-page navigation, so the retry
   * logic in apiFetch cannot cover it — which is why we ping the server first.
   * Waking it now, while the user is still here, means the callback has a warm
   * container to land on. */
  function startGoogleSignIn() {
    return apiFetch("/api/auth/me")
      .catch(function () {
        /* Even if the warm-up fails, the redirect is still worth trying. */
      })
      .then(function () {
        window.location.href =
          "/api/auth/google/start?from=" +
          encodeURIComponent(googleOrigin()) +
          "&next=" +
          encodeURIComponent(safeNext("/analyse"));
      });
  }

  function logout() {
    apiFetch("/api/auth/logout", { method: "POST" })
      .catch(function () {
        /* even if it fails, sending them home is the least confusing option */
      })
      .then(function () {
        currentUser = null;
        window.location.href = "/";
      });
  }

  /* ---------- pending guest analysis ---------- */
  /* A guest's analysis is never stored on the server. To be able to offer
   * "save that one" after they sign up, the TEXT they submitted is kept in
   * sessionStorage: this tab only, gone when the tab closes, and cleared the
   * moment it is used or dismissed. Files are not kept (a File cannot be
   * round-tripped through sessionStorage), so for uploads the offer is simply
   * to save the next one. */

  var PENDING_KEY = "tenura_pending_analysis";

  var pending = {
    save: function (text) {
      try {
        sessionStorage.setItem(PENDING_KEY, JSON.stringify({ text: text, at: Date.now() }));
      } catch (e) {
        /* private mode / quota: the offer just will not appear */
      }
    },
    get: function () {
      try {
        var raw = sessionStorage.getItem(PENDING_KEY);
        if (!raw) return null;
        var value = JSON.parse(raw);
        if (!value || !value.text) return null;
        return value;
      } catch (e) {
        return null;
      }
    },
    clear: function () {
      try {
        sessionStorage.removeItem(PENDING_KEY);
      } catch (e) {
        /* nothing to do */
      }
    },
  };

  /* ---------- app shell (sidebar + topbar) ---------- */
  /* Signed-in pages carry empty [data-shell] placeholders; this fills them so
   * the sidebar and top bar are defined in exactly one place. Pages that do not
   * opt in (the landing page, log in, sign up) are untouched. */

  var ICON = {
    dashboard:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.6"/><rect x="14" y="3" width="7" height="7" rx="1.6"/><rect x="14" y="14" width="7" height="7" rx="1.6"/><rect x="3" y="14" width="7" height="7" rx="1.6"/></svg>',
    search:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M16.5 16.5 20.5 20.5"/></svg>',
    file:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>',
    user:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg>',
    shield:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v6c0 4.2-3 7.4-7 9-4-1.6-7-4.8-7-9V6z"/><path d="M9.5 12l1.8 1.8 3.4-3.6"/></svg>',
    doc:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6l4 4v14H9z"/><path d="M15 3v5h4"/><path d="M12 13h4M12 17h4"/></svg>',
    plus:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>',
  };

  function shellItem(href, key, label, icon, active) {
    var isActive = active === key;
    return (
      '<a class="side-item' + (isActive ? " is-active" : "") + '" href="' + href + '"' +
      (isActive ? ' aria-current="page"' : "") + ">" + icon + "<span>" + label + "</span></a>"
    );
  }

  function mountShell() {
    var side = document.querySelector('[data-shell="sidebar"]');
    var top = document.querySelector('[data-shell="topbar"]');
    if (!side && !top) return;

    var active = (document.body.getAttribute("data-app") || "").trim();

    if (side) {
      side.innerHTML =
        '<a class="side-brand" href="/" aria-label="Tenura home">' +
        '<svg class="brand-mark" viewBox="0 0 32 32" aria-hidden="true">' +
        '<rect x="1" y="1" width="30" height="30" rx="9" fill="currentColor"/>' +
        '<path d="M10.5 9.5h7l4 4v9a1.5 1.5 0 0 1-1.5 1.5h-9.5A1.5 1.5 0 0 1 9 22.5v-11a2 2 0 0 1 1.5-2z" fill="none" stroke="#fff" stroke-width="1.7" stroke-linejoin="round"/>' +
        '<path d="M17.5 9.5v4h4" fill="none" stroke="#fff" stroke-width="1.7" stroke-linejoin="round"/>' +
        '<path d="M12.4 18.4l1.9 1.9 3.7-3.9" fill="none" stroke="#8fd3c8" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>' +
        '</svg><span class="brand-word">Tenura</span></a>' +
        '<nav class="side-nav" aria-label="Primary">' +
        '<p class="side-label">Main</p>' +
        shellItem("/dashboard", "dashboard", "Dashboard", ICON.dashboard, active) +
        shellItem("/history", "analyses", "My analyses", ICON.file, active) +
        shellItem("/analyse", "new", "New analysis", ICON.search, active) +
        shellItem("/profile", "profile", "Profile", ICON.user, active) +
        '<p class="side-label">Others</p>' +
        shellItem("/privacy", "privacy", "Privacy", ICON.shield, active) +
        shellItem("/terms", "terms", "Terms", ICON.doc, active) +
        "</nav>" +
        '<div class="side-card">' +
        "<strong>Your analyses are private</strong>" +
        "<p>Saved agreements are visible only to you. Delete any of them at any time.</p>" +
        '<a class="side-cta" href="/analyse">' + ICON.plus + " Analyse an agreement</a>" +
        "</div>";
    }

    if (top) {
      var search = top.getAttribute("data-shell-search");
      top.innerHTML =
        (search
          ? '<label class="top-search">' + ICON.search +
            '<input type="search" id="shellSearch" placeholder="' + escapeHtml(search) +
            '" aria-label="Search" autocomplete="off" />' +
            '<span class="key">\u2318K</span></label>'
          : "") +
        '<span class="nav-spacer"></span>' +
        '<div class="top-actions">' +
        '<a class="icon-btn" href="/privacy" title="Privacy and data" aria-label="Privacy and data">' +
        ICON.shield + "</a>" +
        '<div class="auth-slot" id="authSlot"></div>' +
        "</div>";
    }
  }

  /* ---------- ready ---------- */

  function boot() {
    mountShell();
    return mountHeader();
  }

  var ready = document.readyState === "loading"
    ? new Promise(function (resolve) {
        document.addEventListener("DOMContentLoaded", function () {
          resolve(boot());
        });
      })
    : boot();

  /* ---------- analysis rendering ---------- */
  /* Shared so a saved analysis opened from History looks exactly like the one
   * shown right after an analysis. */

  function severityRank(sev) {
    return sev === "high" ? 3 : sev === "medium" ? 2 : 1;
  }

  function renderFinding(c) {
    var sev = (c.severity || "low").toLowerCase();
    var src =
      c.source === "rule"
        ? '<span class="badge src-rule">Rule</span>'
        : '<span class="badge src-ai">AI suggestion</span>';
    var evidence = c.evidence
      ? '<div class="evidence">Based on: <b>&ldquo;' + escapeHtml(c.evidence) + "&rdquo;</b></div>"
      : "";
    var clause = c.clause
      ? '<details><summary><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>View original clause</summary><blockquote>' +
        escapeHtml(c.clause) +
        "</blockquote></details>"
      : "";
    var consequence = c.consequence
      ? '<p class="consequence"><strong>What this could mean:</strong> ' + escapeHtml(c.consequence) + "</p>"
      : "";
    var counter = c.counter_clause
      ? '<p class="counter"><strong>You could ask for:</strong> ' + escapeHtml(c.counter_clause) + "</p>"
      : "";
    var question = c.tenant_question
      ? '<p class="ask"><strong>Ask:</strong> ' + escapeHtml(c.tenant_question) + "</p>"
      : "";

    return (
      '<article class="finding sev-' + escapeHtml(sev) + '">' +
      '<div class="finding-top">' +
      '<span class="finding-title">' + escapeHtml(titleCase(c.clause_type)) + "</span>" +
      '<span class="badge sev-' + escapeHtml(sev) + '">' + escapeHtml(sev) + "</span>" +
      src +
      "</div>" +
      '<p class="reason">' + escapeHtml(c.reason || "") + "</p>" +
      consequence +
      counter +
      question +
      evidence +
      clause +
      "</article>"
    );
  }

  function renderMissing(m) {
    return (
      '<div class="missing-item">' +
      '<div class="m-title">' + escapeHtml(m.label || titleCase(m.clause_type)) +
      '<span class="m-tag">not addressed</span></div>' +
      '<div class="m-why">' + escapeHtml(m.why || "") + "</div>" +
      "</div>"
    );
  }

  function sortFindings(list) {
    return (list || [])
      .slice()
      .sort(function (a, b) {
        return severityRank(b.severity) - severityRank(a.severity);
      });
  }

  window.Tenura = {
    apiFetch: apiFetch,
    ApiError: ApiError,
    setStatus: setStatus,
    escapeHtml: escapeHtml,
    titleCase: titleCase,
    riskFor: riskFor,
    bandFor: bandFor,
    riskForBand: riskForBand,
    formatDate: formatDate,
    formatDateTime: formatDateTime,
    param: param,
    safeNext: safeNext,
    safeNextPath: safeNextPath,
    pending: pending,
    logout: logout,
    ready: ready,
    requireSession: requireSession,
    sessionKnown: function () {
      return sessionKnown;
    },
    user: function () {
      return currentUser;
    },
    displayName: displayName,
    initials: initials,
    avatarHtml: avatarHtml,
    closeAccountMenu: closeAccountMenu,
    googleEnabled: googleEnabled,
    googleError: googleError,
    startGoogleSignIn: startGoogleSignIn,
    renderFinding: renderFinding,
    renderMissing: renderMissing,
    sortFindings: sortFindings,
  };
})();

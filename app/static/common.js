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
   * so a crafted ?next= cannot bounce a user to another host. */
  function safeNext(fallback) {
    var next = param("next");
    if (next && next.charAt(0) === "/" && next.charAt(1) !== "/") return next;
    return fallback || "/";
  }

  /* ---------- header session state ---------- */

  var currentUser = null;

  function renderAuthSlot() {
    var slot = document.getElementById("authSlot");
    if (!slot) return;

    if (currentUser) {
      var email = currentUser.email || "";
      slot.innerHTML =
        '<a class="auth-link" href="/history">History</a>' +
        '<span class="auth-user" title="' + escapeHtml(email) + '">' + escapeHtml(email) + "</span>" +
        '<button class="auth-link auth-btn" type="button" id="logoutBtn">Log out</button>';
      var btn = document.getElementById("logoutBtn");
      if (btn) btn.addEventListener("click", logout);
    } else {
      slot.innerHTML =
        '<a class="auth-link" href="/login">Log in</a>' +
        '<a class="auth-link auth-cta" href="/signup">Sign up</a>';
    }
  }

  function mountHeader() {
    if (!document.getElementById("authSlot")) return Promise.resolve(null);
    return apiFetch("/api/auth/me")
      .then(function (data) {
        currentUser = data && data.user ? data.user : null;
        renderAuthSlot();
        return currentUser;
      })
      .catch(function () {
        // A header that cannot load must not break the page; show signed-out.
        currentUser = null;
        renderAuthSlot();
        return null;
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

  /* ---------- ready ---------- */

  var ready = document.readyState === "loading"
    ? new Promise(function (resolve) {
        document.addEventListener("DOMContentLoaded", function () {
          resolve(mountHeader());
        });
      }).then(function (v) {
        return v;
      })
    : mountHeader();

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

    return (
      '<article class="finding sev-' + escapeHtml(sev) + '">' +
      '<div class="finding-top">' +
      '<span class="finding-title">' + escapeHtml(titleCase(c.clause_type)) + "</span>" +
      '<span class="badge sev-' + escapeHtml(sev) + '">' + escapeHtml(sev) + "</span>" +
      src +
      "</div>" +
      '<p class="reason">' + escapeHtml(c.reason || "") + "</p>" +
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
    formatDate: formatDate,
    formatDateTime: formatDateTime,
    param: param,
    safeNext: safeNext,
    pending: pending,
    logout: logout,
    ready: ready,
    user: function () {
      return currentUser;
    },
    renderFinding: renderFinding,
    renderMissing: renderMissing,
    sortFindings: sortFindings,
  };
})();

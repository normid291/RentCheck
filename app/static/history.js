/* Tenura — the account holder's own analyses.
 *
 * Two views in one page, driven by the URL hash so the back button and a
 * refresh both behave:
 *   #            -> the list
 *   #id=<uuid>   -> one saved analysis
 *
 * The server already refuses to return another account's analysis (it answers
 * 404), so this page never has to make an ownership decision of its own.
 */
(function () {
  "use strict";

  var $ = function (id) {
    return document.getElementById(id);
  };
  var esc = Tenura.escapeHtml;

  var els = {
    viewList: $("view-list"),
    viewDetail: $("view-detail"),
    listContainer: $("listContainer"),
    detailContainer: $("detailContainer"),
    loading: $("loading"),
    backBtn: $("backBtn"),
  };

  var cache = {};
  var flashTimer = null;

  /* ---------- helpers ---------- */

  // A 401 means the session ended (expired, or signed out elsewhere).
  function api(path, options) {
    return Tenura.apiFetch(path, options).catch(function (err) {
      if (err && err.status === 401) {
        window.location.href = "/login?next=" + encodeURIComponent("/history");
      }
      throw err;
    });
  }

  function flash(message) {
    Tenura.setStatus(message);
    clearTimeout(flashTimer);
    flashTimer = setTimeout(function () {
      Tenura.setStatus(null);
    }, 5000);
  }

  function bandOf(a) {
    if (a && a.risk_level) return a.risk_level;
    return Tenura.bandFor(a && a.risk_score, a && a.coverage, a && a.degraded);
  }

  function riskBadge(a) {
    var risk = Tenura.riskForBand(bandOf(a));
    var score = Number(a && a.risk_score) || 0;
    return (
      '<span class="risk-level ' + risk.cls + '">' +
      '<span class="risk-dot"></span>' + esc(risk.label) +
      " <b>" + score + "/100</b></span>"
    );
  }

  function stat(value, label, cls) {
    var tone =
      cls === "is-high" ? "is-danger" : cls === "is-medium" ? "is-warn" : "is-brand";
    var icon =
      tone === "is-brand"
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l9 16H3z"/><path d="M12 9v5M12 17h.01"/></svg>';
    return (
      '<div class="stat-card ' + tone + '">' +
      '<span class="sc-ico" aria-hidden="true">' + icon + "</span>" +
      '<div><div class="sc-label">' + esc(label) + "</div>" +
      '<div class="sc-value">' + value + "</div></div></div>"
    );
  }

  function section(heading, count, sub, body) {
    return (
      '<div class="result-section">' +
      '<div class="section-head">' +
      "<h2>" + esc(heading) + "</h2>" +
      '<span class="count">' + count + "</span>" +
      '<span class="sub">' + esc(sub) + "</span>" +
      "</div>" + body + "</div>"
    );
  }

  /* ---------- list ---------- */

  function renderList(analyses) {
    if (!analyses.length) {
      els.listContainer.innerHTML =
        '<div class="panel empty-state">' +
        '<span class="empty-icon" aria-hidden="true">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>' +
        "</span>" +
        "<h2>No analyses yet</h2>" +
        "<p>Upload your first tenancy agreement and Tenura will flag the risky " +
        "clauses, call out the protections that are missing, and give you the " +
        "questions to ask before you sign.</p>" +
        '<a class="btn btn-primary" href="/analyse">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M4 20h16"/></svg>' +
        "Upload your first agreement</a>" +
        "</div>";
      return;
    }

    els.listContainer.innerHTML = analyses
      .map(function (a) {
        var risk = Tenura.riskForBand(bandOf(a));
        var flagged = Number(a.flagged_count) || 0;
        var missing = Number(a.missing_count) || 0;
        return (
          '<a class="history-item" href="#id=' + esc(a.id) + '">' +
          '<span class="hi-main">' +
          '<span class="hi-title">' + esc(a.title) + "</span>" +
          '<span class="hi-meta">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>' +
          esc(Tenura.formatDate(a.created_at)) + "</span>" +
          '<span class="hi-reco">' + esc(a.recommendation) + "</span>" +
          '<span class="hi-badges">' +
          '<span class="count-badge' + (flagged ? " is-flagged" : " is-clear") + '">' +
          (flagged ? flagged + (flagged === 1 ? " flagged clause" : " flagged clauses") : "No flagged clauses") +
          "</span>" +
          '<span class="count-badge' + (missing ? " is-missing" : " is-clear") + '">' +
          (missing ? missing + " missing" + (missing === 1 ? " protection" : " protections") : "All protections present") +
          "</span>" +
          "</span>" +
          "</span>" +
          '<span class="hi-risk ' + risk.cls + '">' +
          '<span class="risk-dot"></span>' +
          "<b>" + (Number(a.risk_score) || 0) + "</b>" +
          "<small>" + esc(risk.label) + "</small>" +
          "</span>" +
          "</a>"
        );
      })
      .join("");
  }

  function skeletonList(count) {
    var card =
      '<div class="panel history-skeleton" aria-hidden="true">' +
      '<span class="sk sk-line" style="width: 42%"></span>' +
      '<span class="sk sk-line" style="width: 26%; margin-top: 12px"></span>' +
      '<span class="sk sk-line" style="width: 68%; margin-top: 12px"></span>' +
      "</div>";
    return new Array(count || 3).join(card) + card;
  }

  function loadList() {
    els.loading.hidden = true;
    els.listContainer.innerHTML = skeletonList(3);
    return api("/api/analyses")
      .then(function (data) {
        renderList((data && data.analyses) || []);
      })
      .catch(function (err) {
        els.listContainer.innerHTML =
          '<div class="panel empty-state"><h2>We could not load your history</h2>' +
          "<p>" + esc(err.message) + "</p>" +
          '<button class="btn btn-primary" id="retryLoad" type="button">Try again</button></div>';
        var retry = $("retryLoad");
        if (retry) retry.addEventListener("click", loadList);
      });
  }

  /* ---------- detail ---------- */

  function renderDetail(analysis) {
    var flagged = Tenura.sortFindings(analysis.flagged_clauses);
    var missing = analysis.missing_protections || [];
    var questions = analysis.questions_to_ask || [];
    var risk = Tenura.riskForBand(bandOf(analysis));

    var html = "";

    html += '<div class="detail-title-row">';
    html += '<h1 id="detailTitle">' + esc(analysis.title) + "</h1>";
    html += '<div class="detail-actions">';
    html += '<button class="ghost-btn" id="renameBtn" type="button">Rename</button>';
    html += '<button class="ghost-btn danger" id="deleteBtn" type="button">Delete</button>';
    html += "</div></div>";

    html += '<p class="detail-meta">Analysed ' + esc(Tenura.formatDateTime(analysis.created_at)) +
      " · " + riskBadge(analysis) + "</p>";

    html += '<div class="panel detail-score">';
    html += '<div class="stat-row">';
    html += stat(flagged.length, "flagged clauses",
      flagged.length === 0 ? "is-low" : risk.key === "high" ? "is-high" : "is-medium");
    html += stat(missing.length, "missing protections", missing.length === 0 ? "is-low" : "is-medium");
    html += "</div>";
    html += '<p class="detail-reco">' + esc(analysis.recommendation) + "</p>";
    html += '<p class="score-summary">' + esc(analysis.summary) + "</p>";
    html += "</div>";

    html += section(
      "Flagged clauses", flagged.length, "Terms that may work against you",
      flagged.length
        ? flagged.map(Tenura.renderFinding).join("")
        : '<div class="empty">No flagged clauses found — the clauses we checked look broadly reasonable.</div>'
    );

    html += section(
      "Missing protections", missing.length, "Not clearly addressed in the agreement",
      missing.length
        ? missing.map(Tenura.renderMissing).join("")
        : '<div class="empty">All expected protections appear to be present.</div>'
    );

    if (questions.length) {
      html +=
        '<div class="result-section">' +
        '<div class="questions-head"><h2>Questions to ask before signing</h2></div>' +
        '<ul class="questions-list">' +
        questions
          .map(function (q, i) {
            return '<li><span class="q-check">' + (i + 1) + "</span><p>" + esc(q) + "</p></li>";
          })
          .join("") +
        "</ul></div>";
    }

    if (analysis.agreement_preview) {
      html +=
        '<details class="agreement-preview">' +
        "<summary>View the start of the agreement text</summary>" +
        "<pre>" + esc(analysis.agreement_preview) +
        (analysis.agreement_truncated ? "\n…" : "") + "</pre></details>";
    }

    els.detailContainer.innerHTML = html;

    var renameBtn = $("renameBtn");
    var deleteBtn = $("deleteBtn");
    if (renameBtn) renameBtn.addEventListener("click", function () { startRename(analysis); });
    if (deleteBtn) deleteBtn.addEventListener("click", function () { removeAnalysis(analysis); });
  }

  function setDetailBusy(message) {
    els.detailContainer.innerHTML = message
      ? '<div class="history-loading"><span class="spinner" aria-hidden="true"></span><span>' +
        esc(message) + "</span></div>"
      : "";
  }

  function openAnalysis(id) {
    if (cache[id]) {
      renderDetail(cache[id]);
    } else {
      setDetailBusy("Opening…");
    }

    api("/api/analyses/" + encodeURIComponent(id))
      .then(function (data) {
        var analysis = data && data.analysis;
        if (!analysis) throw new Error("That analysis could not be found.");
        cache[id] = analysis;
        renderDetail(analysis);
      })
      .catch(function (err) {
        if (err && err.status === 401) return;
        setDetailBusy(null);
        els.detailContainer.innerHTML =
          '<div class="panel empty-state"><h2>We could not open that analysis</h2>' +
          "<p>" + esc(err.message) + "</p>" +
          '<a class="btn btn-primary" href="#list">Back to history</a></div>';
      });
  }

  function startRename(analysis) {
    var titleEl = $("detailTitle");
    var actions = document.querySelector(".detail-actions");
    if (!titleEl || !actions) return;

    var input = document.createElement("input");
    input.type = "text";
    input.className = "rename-input";
    input.value = analysis.title;
    input.maxLength = 120;
    input.setAttribute("aria-label", "Analysis title");

    titleEl.replaceWith(input);
    actions.innerHTML =
      '<button class="ghost-btn primary" id="saveRename" type="button">Save</button>' +
      '<button class="ghost-btn" id="cancelRename" type="button">Cancel</button>';
    input.focus();
    input.select();

    function cancel() {
      renderDetail(analysis);
    }

    function save() {
      var value = (input.value || "").trim() || analysis.title;
      input.disabled = true;
      api("/api/analyses/" + encodeURIComponent(analysis.id), {
        method: "PATCH",
        body: JSON.stringify({ title: value }),
      })
        .then(function (data) {
          analysis.title = (data && data.analysis && data.analysis.title) || value;
          cache[analysis.id] = analysis;
          renderDetail(analysis);
          flash("Renamed.");
        })
        .catch(function (err) {
          input.disabled = false;
          flash(err.message);
        });
    }

    $("cancelRename").addEventListener("click", cancel);
    $("saveRename").addEventListener("click", save);
    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        save();
      } else if (event.key === "Escape") {
        event.preventDefault();
        cancel();
      }
    });
  }

  function removeAnalysis(analysis) {
    var ok = window.confirm(
      "Delete this analysis?\n\n" +
        "The agreement text saved with it is removed permanently. " +
        "This cannot be undone."
    );
    if (!ok) return;

    api("/api/analyses/" + encodeURIComponent(analysis.id), { method: "DELETE" })
      .then(function () {
        delete cache[analysis.id];
        flash("Analysis deleted.");
        window.location.hash = "";
      })
      .catch(function (err) {
        flash(err.message);
      });
  }

  /* ---------- routing ---------- */

  function route() {
    var match = /^#id=([0-9a-fA-F-]{8,36})$/.exec(window.location.hash || "");
    els.viewList.hidden = !!match;
    els.viewDetail.hidden = !match;
    if (match) els.loading.hidden = true;

    if (match) {
      openAnalysis(match[1]);
    } else {
      loadList();
    }

    window.scrollTo({ top: 0, behavior: "auto" });
  }

  els.backBtn.addEventListener("click", function () {
    window.location.hash = "";
  });

  /* ---------- start ---------- */

  Tenura.requireSession("/history")
    .then(function (user) {
      if (!user) return; // already redirecting to log in
      window.addEventListener("hashchange", route);
      route();
    })
    .catch(function (err) {
      els.viewList.hidden = false;
      els.loading.hidden = true;
      els.listContainer.innerHTML =
        '<div class="panel empty-state">' +
        "<h2>We couldn't load your analyses</h2>" +
        "<p>" + esc(err.message) + "</p>" +
        '<button class="btn btn-primary" id="retrySession" type="button">Try again</button>' +
        "</div>";
      var retry = document.getElementById("retrySession");
      if (retry) retry.addEventListener("click", function () { window.location.reload(); });
    });
})();

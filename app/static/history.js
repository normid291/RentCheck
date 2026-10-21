/* RentCheck — the account holder's own analyses.
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
  var esc = RC.escapeHtml;

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
    return RC.apiFetch(path, options).catch(function (err) {
      if (err && err.status === 401) {
        window.location.href = "/login?next=" + encodeURIComponent("/history");
      }
      throw err;
    });
  }

  function flash(message) {
    RC.setStatus(message);
    clearTimeout(flashTimer);
    flashTimer = setTimeout(function () {
      RC.setStatus(null);
    }, 5000);
  }

  function riskBadge(score) {
    var risk = RC.riskFor(score);
    return (
      '<span class="risk-level ' + risk.cls + '">' +
      '<span class="risk-dot"></span>' + esc(risk.label) +
      " <b>" + (Number(score) || 0) + "/100</b></span>"
    );
  }

  function stat(value, label, cls) {
    return (
      '<div class="stat ' + (cls || "") + '"><b>' + value + "</b><span>" +
      esc(label) + "</span></div>"
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
        "<h2>Nothing saved yet</h2>" +
        "<p>Analyse a tenancy agreement while you are signed in and it will " +
        "appear here.</p>" +
        '<a class="btn btn-primary" href="/">Analyse an agreement</a>' +
        "</div>";
      return;
    }

    els.listContainer.innerHTML = analyses
      .map(function (a) {
        var risk = RC.riskFor(a.risk_score);
        return (
          '<a class="history-item" href="#id=' + esc(a.id) + '">' +
          '<span class="hi-main">' +
          '<span class="hi-title">' + esc(a.title) + "</span>" +
          '<span class="hi-meta">' + esc(RC.formatDate(a.created_at)) + " · " +
          a.flagged_count + " flagged · " + a.missing_count + " missing</span>" +
          '<span class="hi-reco">' + esc(a.recommendation) + "</span>" +
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

  function loadList() {
    els.loading.hidden = false;
    els.listContainer.innerHTML = "";
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
      })
      .then(function () {
        els.loading.hidden = true;
      });
  }

  /* ---------- detail ---------- */

  function renderDetail(analysis) {
    var flagged = RC.sortFindings(analysis.flagged_clauses);
    var missing = analysis.missing_protections || [];
    var questions = analysis.questions_to_ask || [];
    var risk = RC.riskFor(analysis.risk_score);

    var html = "";

    html += '<div class="detail-title-row">';
    html += '<h1 id="detailTitle">' + esc(analysis.title) + "</h1>";
    html += '<div class="detail-actions">';
    html += '<button class="ghost-btn" id="renameBtn" type="button">Rename</button>';
    html += '<button class="ghost-btn danger" id="deleteBtn" type="button">Delete</button>';
    html += "</div></div>";

    html += '<p class="detail-meta">Analysed ' + esc(RC.formatDateTime(analysis.created_at)) +
      " · " + riskBadge(analysis.risk_score) + "</p>";

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
        ? flagged.map(RC.renderFinding).join("")
        : '<div class="empty">No flagged clauses found — the clauses we checked look broadly reasonable.</div>'
    );

    html += section(
      "Missing protections", missing.length, "Not clearly addressed in the agreement",
      missing.length
        ? missing.map(RC.renderMissing).join("")
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

  RC.ready.then(function (user) {
    if (!user) {
      window.location.href = "/login?next=" + encodeURIComponent("/history");
      return;
    }
    window.addEventListener("hashchange", route);
    route();
  });
})();

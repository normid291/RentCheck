/* Tenura — owner dashboard.
 *
 * Reads only /api/admin/metrics and /api/admin/users. The server has already
 * checked the verified ADMIN_EMAILS allowlist before serving this page or any
 * JSON, so this file never decides whether a visitor is an admin. It also never
 * renders agreement text or model output: the API does not return any.
 */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var esc = Tenura.escapeHtml;
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var STATUS_COLORS = {
    success: "#8fcbb3",
    failed: "#e6a6a6",
    rejected: "#e5c58e",
  };

  var state = {
    range: "7d",
    metrics: null,
    metricsLoading: false,
    metricsError: "",
    users: {
      q: "",
      sort: "joined_desc",
      page: 1,
      total: 0,
      pages: 1,
      items: [],
      loading: false,
      error: "",
    },
  };

  /* ---------- formatting ---------- */

  function fmtInt(value) {
    var n = Number(value) || 0;
    try {
      return n.toLocaleString();
    } catch (e) {
      return String(n);
    }
  }

  function fmtPct(value) {
    var n = Number(value) || 0;
    return (Math.round(n * 10) / 10) + "%";
  }

  function fmtDuration(ms) {
    if (ms === null || ms === undefined) return "—";
    var n = Number(ms);
    if (!isFinite(n) || n < 0) return "—";
    if (n < 1000) return Math.round(n) + " ms";
    return (Math.round((n / 1000) * 10) / 10) + " s";
  }

  function dayLabel(iso) {
    var parts = String(iso || "").split("-");
    var m = Number(parts[1]);
    var d = Number(parts[2]);
    if (!m || !d) return esc(iso || "");
    return d + " " + MONTHS[m - 1];
  }

  function setText(id, value) {
    var el = $(id);
    if (el) el.textContent = value;
  }

  /* ---------- shared states ---------- */

  function showError(message) {
    var box = $("adminError");
    if (!box) return;
    box.innerHTML = "";
    box.hidden = false;
    box.appendChild(document.createTextNode(message + " "));
    var retry = document.createElement("button");
    retry.type = "button";
    retry.className = "admin-retry";
    retry.textContent = "Try again";
    retry.addEventListener("click", function () { loadAll(true); });
    box.appendChild(retry);
  }

  function hideError() {
    var box = $("adminError");
    if (!box) return;
    box.hidden = true;
    box.textContent = "";
  }

  function skeletonStats() {
    ["statUsers", "statSaved", "statRuns", "statSplit", "statFailed", "statDuration"].forEach(function (id) {
      var el = $(id);
      if (el) el.innerHTML = '<span class="skeleton skeleton-value"></span>';
    });
    ["statNewUsers", "statSuccess", "statSplitSub", "statRejected", "statDurationSub"].forEach(function (id) {
      var el = $(id);
      if (el) el.innerHTML = '<span class="skeleton skeleton-line sm"></span>';
    });
  }

  function skeletonCharts() {
    ["runsChart", "usersChart", "methodChart", "sourceChart"].forEach(function (id) {
      var el = $(id);
      if (el) el.innerHTML = '<div class="skeleton skeleton-chart"></div>';
    });
  }

  function skeletonUsers() {
    var body = $("userRows");
    if (!body) return;
    var rows = [];
    for (var i = 0; i < 6; i++) {
      rows.push('<tr><td colspan="6"><span class="skeleton skeleton-line"></span></td></tr>');
    }
    body.innerHTML = rows.join("");
    var pager = $("userPager");
    if (pager) pager.innerHTML = '<span class="skeleton skeleton-line sm"></span>';
  }

  /* ---------- metrics ---------- */

  function loadMetrics(force) {
    state.metricsLoading = true;
    hideError();
    var refresh = $("refreshBtn");
    if (refresh) {
      refresh.disabled = true;
      refresh.classList.add("is-spinning");
    }
    var url = "/api/admin/metrics?range=" + encodeURIComponent(state.range) +
      (force ? "&refresh=1" : "");
    return Tenura.apiFetch(url)
      .then(function (data) {
        state.metrics = data;
        state.metricsError = "";
        renderMetrics(data);
      })
      .catch(function (err) {
        state.metrics = null;
        state.metricsError = err && err.status === 404
          ? "This dashboard is not available for this account."
          : "We couldn't load the metrics. Please try again.";
        showError(state.metricsError);
        renderMetricsEmpty();
      })
      .finally(function () {
        state.metricsLoading = false;
        if (refresh) {
          refresh.disabled = false;
          refresh.classList.remove("is-spinning");
        }
      });
  }

  function renderMetrics(m) {
    var t = m.totals || {};
    setText("statUsers", fmtInt(t.users));
    setText("statNewUsers", fmtInt(t.new_users) + " new in this range");
    setText("statSaved", fmtInt(t.saved_analyses));
    setText("statRuns", fmtInt(t.runs));
    setText("statSuccess", fmtPct(t.success_rate) + " success rate");
    setText("statSplit", fmtInt(t.guest_runs) + " / " + fmtInt(t.logged_in_runs));
    setText("statSplitSub", "guest / signed-in");
    setText("statFailed", fmtInt(t.failed_runs));
    setText("statRejected", fmtInt(t.rejected_runs) + " rejected as non-Nigerian");
    setText("statDuration", fmtDuration(t.avg_duration_ms));
    setText("statDurationSub", t.avg_duration_ms === null ? "No completed timings yet" : "Selected range");

    var updated = $("lastUpdated");
    if (updated) updated.textContent = m.generated_at ? Tenura.formatDateTime(m.generated_at) : "—";

    drawRunsChart(m.ai_runs_daily || []);
    drawUsersChart(m.new_users_daily || []);
    drawMethodChart(m.signup_methods || {});
    drawSourceChart(m.sources || {});
  }

  function renderMetricsEmpty() {
    ["statUsers", "statSaved", "statRuns", "statSplit", "statFailed", "statDuration"].forEach(function (id) {
      setText(id, "—");
    });
    ["statNewUsers", "statSuccess", "statSplitSub", "statRejected", "statDurationSub"].forEach(function (id) {
      setText(id, "—");
    });
    ["runsChart", "usersChart", "methodChart", "sourceChart"].forEach(function (id) {
      var el = $(id);
      if (el) el.innerHTML = '<div class="chart-empty">Metrics unavailable.</div>';
    });
    var legend = $("runsLegend");
    if (legend) legend.innerHTML = "";
  }

  /* ---------- SVG chart helpers ---------- */

  function svgOpen(w, h, label) {
    return '<svg viewBox="0 0 ' + w + " " + h + '" role="img" aria-label="' + esc(label) + '">';
  }

  function drawRunsChart(rows) {
    var container = $("runsChart");
    var legend = $("runsLegend");
    if (!container) return;

    var total = rows.reduce(function (sum, r) {
      return sum + Number(r.success || 0) + Number(r.failed || 0) + Number(r.rejected || 0);
    }, 0);

    if (legend) {
      legend.innerHTML =
        '<span><i style="background:' + STATUS_COLORS.success + '"></i>Success</span>' +
        '<span><i style="background:' + STATUS_COLORS.failed + '"></i>Failed</span>' +
        '<span><i style="background:' + STATUS_COLORS.rejected + '"></i>Rejected</span>';
    }

    if (!rows.length || !total) {
      container.innerHTML = '<div class="chart-empty">No AI runs in this range yet.</div>';
      return;
    }

    var W = 560, H = 250, padL = 36, padR = 14, padT = 18, padB = 36;
    var plotW = W - padL - padR, plotH = H - padT - padB;
    var base = padT + plotH;
    var ticks = 4;
    var rawMax = Math.max.apply(null, rows.map(function (r) {
      return Number(r.success || 0) + Number(r.failed || 0) + Number(r.rejected || 0);
    }));
    var maxVal = Math.max(ticks, Math.ceil(rawMax / ticks) * ticks);
    var step = plotW / Math.max(1, rows.length);
    var bw = Math.min(34, Math.max(3, step * 0.62));
    var parts = [];
    var t, i;

    for (t = 0; t <= ticks; t++) {
      var y = base - (plotH * t) / ticks;
      parts.push('<line class="grid-line" x1="' + padL + '" y1="' + y + '" x2="' + (W - padR) + '" y2="' + y + '"/>');
      parts.push('<text class="axis-label" x="' + (padL - 7) + '" y="' + (y + 3) + '" text-anchor="end">' +
        Math.round((maxVal * t) / ticks) + "</text>");
    }

    var labelEvery = Math.max(1, Math.ceil(rows.length / 6));
    rows.forEach(function (r, idx) {
      var x = padL + step * idx + (step - bw) / 2;
      var cursor = base;
      var values = [
        ["success", Number(r.success || 0)],
        ["failed", Number(r.failed || 0)],
        ["rejected", Number(r.rejected || 0)]
      ];
      values.forEach(function (pair) {
        var value = pair[1];
        if (!value) return;
        var h = (plotH * value) / maxVal;
        cursor -= h;
        parts.push('<rect x="' + x.toFixed(1) + '" y="' + cursor.toFixed(1) + '" width="' + bw.toFixed(1) +
          '" height="' + h.toFixed(1) + '" rx="2" fill="' + STATUS_COLORS[pair[0]] + '">' +
          "<title>" + esc(dayLabel(r.date)) + ": " + value + " " + pair[0] + "</title></rect>");
      });
      if (idx % labelEvery === 0 || idx === rows.length - 1) {
        parts.push('<text class="axis-label" x="' + (x + bw / 2).toFixed(1) + '" y="' + (H - 16) +
          '" text-anchor="middle">' + esc(dayLabel(r.date)) + "</text>");
      }
    });

    container.innerHTML = svgOpen(W, H, "AI runs per day, stacked by status") + parts.join("") + "</svg>";
  }

  function drawUsersChart(rows) {
    var container = $("usersChart");
    if (!container) return;
    var total = rows.reduce(function (sum, r) { return sum + Number(r.count || 0); }, 0);
    if (!rows.length || !total) {
      container.innerHTML = '<div class="chart-empty">No new users in this range yet.</div>';
      return;
    }

    var W = 560, H = 250, padL = 36, padR = 14, padT = 18, padB = 36;
    var plotW = W - padL - padR, plotH = H - padT - padB;
    var base = padT + plotH;
    var ticks = 4;
    var rawMax = Math.max.apply(null, rows.map(function (r) { return Number(r.count || 0); }));
    var maxVal = Math.max(ticks, Math.ceil(rawMax / ticks) * ticks);
    var step = plotW / Math.max(1, rows.length);
    var bw = Math.min(34, Math.max(3, step * 0.58));
    var parts = [];
    var t;

    for (t = 0; t <= ticks; t++) {
      var y = base - (plotH * t) / ticks;
      parts.push('<line class="grid-line" x1="' + padL + '" y1="' + y + '" x2="' + (W - padR) + '" y2="' + y + '"/>');
      parts.push('<text class="axis-label" x="' + (padL - 7) + '" y="' + (y + 3) + '" text-anchor="end">' +
        Math.round((maxVal * t) / ticks) + "</text>");
    }

    var labelEvery = Math.max(1, Math.ceil(rows.length / 6));
    rows.forEach(function (r, idx) {
      var value = Number(r.count || 0);
      var x = padL + step * idx + (step - bw) / 2;
      var h = (plotH * value) / maxVal;
      if (value) {
        parts.push('<rect x="' + x.toFixed(1) + '" y="' + (base - h).toFixed(1) + '" width="' + bw.toFixed(1) +
          '" height="' + h.toFixed(1) + '" rx="5" fill="#8fb9c9">' +
          "<title>" + esc(dayLabel(r.date)) + ": " + value + " new user" + (value === 1 ? "" : "s") + "</title></rect>");
      }
      if (idx % labelEvery === 0 || idx === rows.length - 1) {
        parts.push('<text class="axis-label" x="' + (x + bw / 2).toFixed(1) + '" y="' + (H - 16) +
          '" text-anchor="middle">' + esc(dayLabel(r.date)) + "</text>");
      }
    });

    container.innerHTML = svgOpen(W, H, "New users per day") + parts.join("") + "</svg>";
  }

  function drawMethodChart(methods) {
    var container = $("methodChart");
    if (!container) return;
    var google = Number(methods.google || 0);
    var email = Number(methods.email || 0);
    var total = google + email;
    if (!total) {
      container.innerHTML = '<div class="chart-empty">No sign-ups in this range yet.</div>';
      return;
    }

    var colors = { Google: "#0f4c6b", "Email / OTP": "#8fcbb3" };
    var items = [
      { label: "Google", value: google },
      { label: "Email / OTP", value: email }
    ];
    var r = 70, cx = 110, cy = 110, circ = 2 * Math.PI * r;
    var offset = 0;
    var circles = items.map(function (item) {
      var length = (item.value / total) * circ;
      var dash = Math.max(0, length - 2);
      var el = '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="' +
        colors[item.label] + '" stroke-width="28" stroke-dasharray="' + dash.toFixed(2) + " " +
        (circ - dash).toFixed(2) + '" stroke-dashoffset="' + (-offset).toFixed(2) + '"/>';
      offset += length;
      return el;
    }).join("");

    var legend = items.map(function (item) {
      return '<span><i style="background:' + colors[item.label] + '"></i>' +
        esc(item.label) + " <b>" + fmtInt(item.value) + "</b></span>";
    }).join("");

    container.innerHTML =
      '<div class="admin-donut-wrap">' +
      '<svg viewBox="0 0 220 220" role="img" aria-label="Sign-ups by method">' +
      '<g transform="rotate(-90 110 110)">' + circles + "</g>" +
      '<text x="110" y="106" text-anchor="middle" class="admin-donut-value">' + fmtInt(total) + "</text>" +
      '<text x="110" y="126" text-anchor="middle" class="admin-donut-label">sign-ups</text>' +
      "</svg>" +
      '<div class="admin-donut-legend">' + legend + "</div>" +
      "</div>";
  }

  function drawSourceChart(sources) {
    var container = $("sourceChart");
    if (!container) return;
    var items = [
      { key: "paste", label: "Paste", color: "#0f4c6b" },
      { key: "upload", label: "Upload", color: "#8fb9c9" },
      { key: "sample", label: "Sample", color: "#c9a86a" }
    ].map(function (item) {
      return Object.assign({}, item, { value: Number(sources[item.key] || 0) });
    });
    var total = items.reduce(function (sum, item) { return sum + item.value; }, 0);
    if (!total) {
      container.innerHTML = '<div class="chart-empty">No runs in this range yet.</div>';
      return;
    }
    var max = Math.max.apply(null, items.map(function (item) { return item.value; })) || 1;

    container.innerHTML = '<div class="admin-source-list">' + items.map(function (item) {
      var pct = Math.round((item.value / max) * 100);
      return '<div class="admin-source-row">' +
        '<div class="admin-source-head"><span>' + esc(item.label) + "</span><b>" + fmtInt(item.value) + "</b></div>" +
        '<div class="admin-source-track"><span style="width:' + pct + "%;background:" + item.color + '"></span></div>' +
        "</div>";
    }).join("") + "</div>";
  }

  /* ---------- users table ---------- */

  function loadUsers() {
    state.users.loading = true;
    hideError();
    var params = new URLSearchParams();
    params.set("q", state.users.q);
    params.set("sort", state.users.sort);
    params.set("page", String(state.users.page));
    return Tenura.apiFetch("/api/admin/users?" + params.toString())
      .then(function (data) {
        state.users.items = data.items || [];
        state.users.page = data.page || 1;
        state.users.pages = data.pages || 1;
        state.users.total = data.total || 0;
        state.users.q = data.query || state.users.q;
        state.users.error = "";
        renderUsers();
      })
      .catch(function (err) {
        state.users.items = [];
        state.users.error = err && err.status === 404
          ? "This dashboard is not available for this account."
          : "We couldn't load users. Please try again.";
        showError(state.users.error);
        renderUsersError();
      })
      .finally(function () {
        state.users.loading = false;
      });
  }

  function renderUsersError() {
    var body = $("userRows");
    if (body) {
      body.innerHTML = '<tr><td colspan="6"><div class="admin-empty-row">' +
        esc(state.users.error) + "</div></td></tr>";
    }
    var pager = $("userPager");
    if (pager) pager.innerHTML = "";
  }

  function renderUsers() {
    var body = $("userRows");
    if (!body) return;
    if (!state.users.items.length) {
      body.innerHTML = '<tr><td colspan="6"><div class="admin-empty-row">' +
        (state.users.q ? "No accounts match that search." : "No accounts yet.") +
        "</div></td></tr>";
    } else {
      body.innerHTML = state.users.items.map(function (user) {
        var method = user.sign_up_method === "google" ? "Google" : "Email / OTP";
        var joined = user.joined_at ? Tenura.formatDate(user.joined_at) : "—";
        var active = user.last_active ? Tenura.formatDateTime(user.last_active) : "—";
        var avatar = Tenura.avatarHtml({ name: user.name, email: user.email }, "avatar-sm");
        return "<tr>" +
          '<td><div class="admin-user-cell">' + avatar + "<strong>" + esc(user.name || "Account") +
          "</strong></div></td>" +
          '<td><span class="admin-email">' + esc(user.email) + "</span></td>" +
          '<td><span class="tag t-plain">' + esc(method) + "</span></td>" +
          "<td>" + esc(joined) + "</td>" +
          "<td>" + fmtInt(user.analysis_count) + "</td>" +
          "<td>" + esc(active) + "</td>" +
          "</tr>";
      }).join("");
    }
    renderPager();
  }

  function pageList(current, pages) {
    if (pages <= 7) {
      var all = [];
      for (var p = 1; p <= pages; p++) all.push(p);
      return all;
    }
    var list = [1];
    var start = Math.max(2, current - 1);
    var end = Math.min(pages - 1, current + 1);
    if (start > 2) list.push("…");
    for (var i = start; i <= end; i++) list.push(i);
    if (end < pages - 1) list.push("…");
    list.push(pages);
    return list;
  }

  function renderPager() {
    var pager = $("userPager");
    if (!pager) return;
    var u = state.users;
    var pages = Math.max(1, u.pages || 1);
    var buttons = pageList(u.page, pages).map(function (p) {
      if (p === "…") return '<span class="ellipsis">…</span>';
      return '<button type="button" data-page="' + p + '"' +
        (p === u.page ? ' class="is-active" aria-current="page"' : "") + ">" + p + "</button>";
    }).join("");

    pager.innerHTML =
      "<span>" + fmtInt(u.total) + (u.total === 1 ? " user" : " users") + "</span>" +
      '<span class="pager-spacer"></span>' +
      '<div class="pager-pages">' +
      '<button type="button" data-page="' + (u.page - 1) + '"' +
      (u.page <= 1 ? " disabled" : "") + ' aria-label="Previous page">‹</button>' +
      buttons +
      '<button type="button" data-page="' + (u.page + 1) + '"' +
      (u.page >= pages ? " disabled" : "") + ' aria-label="Next page">›</button>' +
      "</div>";

    pager.querySelectorAll("button[data-page]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var p = Number(btn.getAttribute("data-page"));
        if (!p || p < 1 || p > pages || p === state.users.page) return;
        state.users.page = p;
        loadUsers();
      });
    });
  }

  /* ---------- wiring ---------- */

  function wireRange() {
    var chips = document.querySelectorAll(".admin-range .chip");
    chips.forEach(function (chip) {
      chip.setAttribute("aria-pressed", chip.classList.contains("is-active") ? "true" : "false");
      chip.addEventListener("click", function () {
        var next = chip.getAttribute("data-range");
        if (!next || next === state.range) return;
        state.range = next;
        chips.forEach(function (c) {
          var active = c === chip;
          c.classList.toggle("is-active", active);
          c.setAttribute("aria-pressed", active ? "true" : "false");
        });
        var updated = $("lastUpdated");
        if (updated) updated.textContent = "Updating…";
        loadMetrics(false);
      });
    });
  }

  function wireUsers() {
    var search = $("userSearch");
    var sort = $("userSort");
    var timer = null;
    if (search) {
      search.addEventListener("input", function () {
        window.clearTimeout(timer);
        timer = window.setTimeout(function () {
          state.users.q = search.value.trim();
          state.users.page = 1;
          loadUsers();
        }, 260);
      });
    }
    if (sort) {
      sort.addEventListener("change", function () {
        state.users.sort = sort.value;
        state.users.page = 1;
        loadUsers();
      });
    }
  }

  function loadAll(force) {
    hideError();
    return Promise.all([
      loadMetrics(!!force),
      loadUsers()
    ]);
  }

  function init() {
    skeletonStats();
    skeletonCharts();
    skeletonUsers();
    wireRange();
    wireUsers();

    var refresh = $("refreshBtn");
    if (refresh) refresh.addEventListener("click", function () { loadAll(true); });

    Tenura.ready.then(function (user) {
      if (!user) {
        showError("Your session has ended. Please sign in again.");
        return;
      }
      if (!user.is_admin) {
        showError("This dashboard is not available for this account.");
        return;
      }
      loadAll(false);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

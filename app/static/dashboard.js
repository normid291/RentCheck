/* Tenura — the dashboard.
 *
 * One screen that mirrors the reference layout: four stat cards, two charts
 * (analyses by risk, risk score over time) and a paginated table of every saved
 * analysis. All of it is derived from the real /api/analyses payload — nothing
 * here is invented; when there is no data it says so.
 */
(function () {
  "use strict";

  var $ = function (id) {
    return document.getElementById(id);
  };
  var esc = Tenura.escapeHtml;

  var BAND_ORDER = ["high", "moderate", "low", "unknown"];
  var BAND = {
    high: { label: "High risk", cls: "t-high", color: "#dc2626", bar: "#ffc4c4", short: "High" },
    moderate: { label: "Moderate risk", cls: "t-moderate", color: "#d9820b", bar: "#ffd9ad", short: "Moderate" },
    low: { label: "Low risk", cls: "t-low", color: "#2563eb", bar: "#c3d4ff", short: "Low" },
    unknown: { label: "Review needed", cls: "t-unknown", color: "#6b7280", bar: "#d7dae1", short: "Review" },
  };

  var state = { all: [], q: "", band: "all", page: 1, per: 8 };

  /* ---------- data helpers ---------- */

  function bandOf(a) {
    if (a && a.risk_level) return a.risk_level;
    return Tenura.bandFor(a && a.risk_score, a && a.coverage, a && a.degraded);
  }

  function bandMeta(band) {
    return BAND[band] || BAND.unknown;
  }

  function api(path, options) {
    return Tenura.apiFetch(path, options).catch(function (err) {
      if (err && err.status === 401) {
        window.location.href = "/login?next=" + encodeURIComponent("/dashboard");
      }
      throw err;
    });
  }

  function filtered() {
    var list = state.all.slice();
    var q = state.q.trim().toLowerCase();
    if (q) {
      list = list.filter(function (a) {
        return String(a.title || "").toLowerCase().indexOf(q) !== -1;
      });
    }
    if (state.band !== "all") {
      list = list.filter(function (a) {
        return bandOf(a) === state.band;
      });
    }
    return list;
  }

  /* ---------- stat cards ---------- */

  function renderStats(list) {
    var now = new Date();
    var high = 0;
    var review = 0;
    var month = 0;
    list.forEach(function (a) {
      var b = bandOf(a);
      if (b === "high") high += 1;
      if (b === "unknown") review += 1;
      var d = new Date(a.created_at);
      if (!isNaN(d.getTime()) && d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()) {
        month += 1;
      }
    });
    $("statTotal").textContent = list.length;
    $("statHigh").textContent = high;
    $("statReview").textContent = review;
    $("statMonth").textContent = month;
  }

  /* ---------- charts (hand-drawn SVG, no libraries) ---------- */

  function svgOpen(w, h, label) {
    return (
      '<svg viewBox="0 0 ' + w + " " + h + '" role="img" aria-label="' + esc(label) + '">'
    );
  }

  function positionTip(tip, container, el, html) {
    tip.innerHTML = html;
    var cr = container.getBoundingClientRect();
    var er = el.getBoundingClientRect();
    tip.style.left = er.left - cr.left + er.width / 2 + "px";
    tip.style.top = er.top - cr.top + "px";
    tip.classList.add("show");
  }

  function renderRiskChart(list) {
    var container = $("riskChart");
    if (!list.length) {
      container.innerHTML = '<div class="chart-empty">No analyses yet.</div>';
      $("riskLegend").innerHTML = "";
      return;
    }
    var counts = { high: 0, moderate: 0, low: 0, unknown: 0 };
    list.forEach(function (a) {
      counts[bandOf(a)] += 1;
    });
    var items = BAND_ORDER.map(function (b) {
      return { band: b, label: bandMeta(b).label, short: bandMeta(b).short, value: counts[b], color: bandMeta(b).bar };
    });

    var W = 560, H = 250, padL = 30, padR = 14, padT = 18, padB = 44;
    var plotW = W - padL - padR, plotH = H - padT - padB;
    var ticks = 4;
    var rawMax = Math.max.apply(null, items.map(function (i) { return i.value; }));
    // Round the axis top up to a multiple of the tick count so the gridline
    // labels stay whole numbers instead of colliding (e.g. two "2"s).
    var maxVal = Math.max(ticks, Math.ceil(rawMax / ticks) * ticks);
    var step = plotW / items.length;
    var bw = Math.min(70, step * 0.52);
    var base = padT + plotH;
    var p = [];

    for (var t = 0; t <= ticks; t++) {
      var y = base - (plotH * t) / ticks;
      p.push('<line class="grid-line" x1="' + padL + '" y1="' + y + '" x2="' + (W - padR) + '" y2="' + y + '"/>');
      p.push('<text class="axis-label" x="' + (padL - 7) + '" y="' + (y + 3) + '" text-anchor="end">' +
        Math.round((maxVal * t) / ticks) + "</text>");
    }
    items.forEach(function (it, i) {
      var cx = padL + step * i + step / 2;
      var h = it.value <= 0 ? 0 : (plotH * it.value) / maxVal;
      p.push('<rect class="bar" x="' + (cx - bw / 2) + '" y="' + (base - h) + '" width="' + bw +
        '" height="' + h + '" rx="6" fill="' + it.color + '" data-i="' + i + '"/>');
      p.push('<text class="axis-label" x="' + cx + '" y="' + (H - 22) + '" text-anchor="middle">' + esc(it.short) + "</text>");
      p.push('<text class="axis-label" x="' + cx + '" y="' + (base - h - 7) + '" text-anchor="middle" style="fill:#6b7280;font-weight:700">' +
        (it.value || "") + "</text>");
    });

    container.innerHTML = svgOpen(W, H, "Analyses by risk band") + p.join("") + "</svg>" +
      '<div class="chart-tip"></div>';

    var tip = container.querySelector(".chart-tip");
    container.querySelectorAll(".bar").forEach(function (bar) {
      bar.addEventListener("mousemove", function () {
        var it = items[Number(bar.getAttribute("data-i"))];
        positionTip(tip, container, bar,
          "<b>" + esc(it.label) + "</b>" + it.value + (it.value === 1 ? " analysis" : " analyses"));
      });
      bar.addEventListener("mouseleave", function () { tip.classList.remove("show"); });
    });

    $("riskLegend").innerHTML = items.map(function (it) {
      return '<span><i style="background:' + it.color + '"></i>' + esc(it.label) + "</span>";
    }).join("");
  }

  function renderTrendChart(list) {
    var container = $("trendChart");
    var pts = list
      .slice()
      .reverse()
      .slice(-12)
      .map(function (a) {
        return { value: Number(a.risk_score) || 0, date: a.created_at };
      });

    if (pts.length < 2) {
      container.innerHTML = '<div class="chart-empty">Analyse at least two agreements to see a trend.</div>';
      return;
    }

    var W = 560, H = 250, padL = 36, padR = 16, padT = 18, padB = 40;
    var plotW = W - padL - padR, plotH = H - padT - padB;
    var n = pts.length;
    var base = padT + plotH;
    var xFor = function (i) { return padL + (plotW * i) / (n - 1); };
    var yFor = function (v) { return base - (plotH * Math.max(0, Math.min(100, v))) / 100; };
    var coords = pts.map(function (pt, i) { return [xFor(i), yFor(pt.value)]; });
    var p = [];

    for (var t = 0; t <= 4; t++) {
      var v = t * 25;
      var y = yFor(v);
      p.push('<line class="grid-line" x1="' + padL + '" y1="' + y + '" x2="' + (W - padR) + '" y2="' + y + '"/>');
      p.push('<text class="axis-label" x="' + (padL - 7) + '" y="' + (y + 3) + '" text-anchor="end">' + v + "</text>");
    }

    var line = coords.map(function (c, i) { return (i ? "L" : "M") + c[0].toFixed(1) + " " + c[1].toFixed(1); }).join(" ");
    var area = "M" + coords[0][0] + " " + base + " " +
      coords.map(function (c) { return "L" + c[0].toFixed(1) + " " + c[1].toFixed(1); }).join(" ") +
      " L" + coords[n - 1][0] + " " + base + " Z";
    p.push('<path d="' + area + '" fill="rgba(47,92,246,0.07)"/>');
    p.push('<path d="' + line + '" fill="none" stroke="#2f5cf6" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>');
    coords.forEach(function (c, i) {
      p.push('<circle class="pt" cx="' + c[0].toFixed(1) + '" cy="' + c[1].toFixed(1) +
        '" r="4.5" fill="#fff" stroke="#2f5cf6" stroke-width="2.4" data-i="' + i + '"/>');
    });

    // first / middle / last date labels
    [0, Math.floor((n - 1) / 2), n - 1].forEach(function (i) {
      p.push('<text class="axis-label" x="' + xFor(i) + '" y="' + (H - 18) + '" text-anchor="middle">' +
        esc(Tenura.formatDate(pts[i].date)) + "</text>");
    });

    container.innerHTML = svgOpen(W, H, "Risk score over time") + p.join("") + "</svg>" +
      '<div class="chart-tip"></div>';

    var tip = container.querySelector(".chart-tip");
    container.querySelectorAll(".pt").forEach(function (dot) {
      dot.addEventListener("mousemove", function () {
        var pt = pts[Number(dot.getAttribute("data-i"))];
        positionTip(tip, container, dot,
          "<b>" + esc(Tenura.formatDate(pt.date)) + "</b>Risk score " + pt.value + "/100");
      });
      dot.addEventListener("mouseleave", function () { tip.classList.remove("show"); });
    });
  }

  /* ---------- table ---------- */

  function riskTag(band) {
    var m = bandMeta(band);
    return '<span class="tag ' + m.cls + '"><span class="dot"></span>' + esc(m.label) + "</span>";
  }

  function coverageCell(a) {
    var c = a.coverage;
    if (c === null || c === undefined || isNaN(Number(c))) return "—";
    return Math.round(Number(c) * 100) + "%";
  }

  function renderTable() {
    var rows = filtered();
    var body = $("tableBody");
    var total = rows.length;
    var pages = Math.max(1, Math.ceil(total / state.per));
    if (state.page > pages) state.page = pages;
    var start = (state.page - 1) * state.per;
    var pageRows = rows.slice(start, start + state.per);

    if (!pageRows.length) {
      body.innerHTML =
        '<tr><td colspan="9"><div class="empty-block"><h2>' +
        (state.all.length ? "Nothing matches that search" : "No analyses yet") +
        "</h2><p>" +
        (state.all.length
          ? "Try a different search or filter."
          : "Analyse a tenancy agreement and it will appear here, private to your account.") +
        "</p>" +
        (state.all.length
          ? ""
          : '<a class="btn-new" href="/analyse">New analysis</a>') +
        "</div></td></tr>";
    } else {
      body.innerHTML = pageRows.map(function (a) {
        var band = bandOf(a);
        return (
          "<tr>" +
          '<td class="col-check"><input type="checkbox" aria-label="Select ' + esc(a.title) + '" /></td>' +
          '<td><span class="cell-title"><a href="/history#id=' + encodeURIComponent(a.id) + '">' + esc(a.title) + "</a></span></td>" +
          "<td>" + riskTag(band) + "</td>" +
          '<td><span class="value-chip">' + (Number(a.risk_score) || 0) + "</span></td>" +
          "<td>" + (Number(a.flagged_count) || 0) + "</td>" +
          "<td>" + (Number(a.missing_count) || 0) + "</td>" +
          '<td><span class="tag t-plain">' + esc(a.jurisdiction || "—") + "</span></td>" +
          "<td>" + esc(Tenura.formatDate(a.created_at)) + "</td>" +
          "<td>" + coverageCell(a) + "</td>" +
          "</tr>"
        );
      }).join("");
    }

    renderPager(total, pages);
  }

  function pageList(current, pages) {
    var out = [];
    var push = function (v) { out.push(v); };
    if (pages <= 7) {
      for (var i = 1; i <= pages; i++) push(i);
      return out;
    }
    push(1);
    if (current > 3) push("…");
    for (var j = Math.max(2, current - 1); j <= Math.min(pages - 1, current + 1); j++) push(j);
    if (current < pages - 2) push("…");
    push(pages);
    return out;
  }

  function renderPager(total, pages) {
    var pager = $("pager");
    var nums = pageList(state.page, pages).map(function (p) {
      if (p === "…") return '<span class="ellipsis">…</span>';
      return '<button type="button" data-page="' + p + '"' +
        (p === state.page ? ' class="is-active" aria-current="page"' : "") + ">" + p + "</button>";
    }).join("");

    pager.innerHTML =
      "<span>Items per page</span>" +
      '<select id="perSelect" aria-label="Items per page">' +
      [4, 8, 12, 20].map(function (n) {
        return '<option value="' + n + '"' + (n === state.per ? " selected" : "") + ">" +
          String(n).padStart(2, "0") + "</option>";
      }).join("") +
      "</select>" +
      '<span class="pager-spacer"></span>' +
      '<span>' + total + (total === 1 ? " analysis" : " analyses") + "</span>" +
      '<div class="pager-pages">' +
      '<button type="button" data-page="' + (state.page - 1) + '"' +
      (state.page <= 1 ? " disabled" : "") + ' aria-label="Previous page">‹</button>' +
      nums +
      '<button type="button" data-page="' + (state.page + 1) + '"' +
      (state.page >= pages ? " disabled" : "") + ' aria-label="Next page">›</button>' +
      "</div>";

    pager.querySelectorAll("button[data-page]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var p = Number(btn.getAttribute("data-page"));
        if (p < 1 || p > pages || p === state.page) return;
        state.page = p;
        renderTable();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    });
    var sel = $("perSelect");
    if (sel) {
      sel.addEventListener("change", function () {
        state.per = Number(sel.value) || 8;
        state.page = 1;
        renderTable();
      });
    }
  }

  /* ---------- toolbar wiring ---------- */

  function setQuery(value) {
    state.q = value || "";
    state.page = 1;
    renderTable();
  }

  function wireToolbar() {
    var tableSearch = $("tableSearch");
    var shellSearch = $("shellSearch");
    if (tableSearch) {
      tableSearch.addEventListener("input", function () {
        if (shellSearch) shellSearch.value = tableSearch.value;
        setQuery(tableSearch.value);
      });
    }
    if (shellSearch) {
      shellSearch.addEventListener("input", function () {
        if (tableSearch) tableSearch.value = shellSearch.value;
        setQuery(shellSearch.value);
      });
    }

    var filterBtn = $("filterBtn");
    var filterMenu = $("filterMenu");
    if (filterBtn && filterMenu) {
      filterBtn.addEventListener("click", function (e) {
        e.preventDefault();
        var open = filterMenu.hidden;
        filterMenu.hidden = !open;
        filterBtn.setAttribute("aria-expanded", open ? "true" : "false");
        filterBtn.classList.toggle("is-active", open);
      });
      filterMenu.querySelectorAll(".filter-opt").forEach(function (opt) {
        opt.addEventListener("click", function () {
          state.band = opt.getAttribute("data-band");
          state.page = 1;
          filterMenu.querySelectorAll(".filter-opt").forEach(function (o) {
            var on = o === opt;
            o.classList.toggle("is-active", on);
            o.setAttribute("aria-checked", on ? "true" : "false");
          });
          filterMenu.hidden = true;
          filterBtn.classList.remove("is-active");
          filterBtn.setAttribute("aria-expanded", "false");
          renderTable();
        });
      });
      document.addEventListener("click", function (e) {
        if (!filterMenu.hidden && !filterMenu.contains(e.target) && !filterBtn.contains(e.target)) {
          filterMenu.hidden = true;
          filterBtn.classList.remove("is-active");
          filterBtn.setAttribute("aria-expanded", "false");
        }
      });
    }

    var checkAll = $("checkAll");
    if (checkAll) {
      checkAll.addEventListener("change", function () {
        $("tableBody").querySelectorAll('input[type="checkbox"]').forEach(function (cb) {
          cb.checked = checkAll.checked;
        });
      });
    }

    var exportBtn = $("exportBtn");
    if (exportBtn) {
      exportBtn.addEventListener("click", function () {
        exportCsv(filtered());
      });
    }
  }

  function exportCsv(rows) {
    if (!rows.length) {
      Tenura.setStatus("Nothing to export yet.");
      setTimeout(function () { Tenura.setStatus(null); }, 3000);
      return;
    }
    var head = ["Agreement", "Risk", "Score", "Flagged", "Missing", "Jurisdiction", "Analysed", "Coverage"];
    var lines = [head.join(",")];
    rows.forEach(function (a) {
      lines.push([
        a.title, bandMeta(bandOf(a)).label, Number(a.risk_score) || 0,
        Number(a.flagged_count) || 0, Number(a.missing_count) || 0,
        a.jurisdiction || "", Tenura.formatDate(a.created_at), coverageCell(a),
      ].map(function (v) {
        return '"' + String(v).replace(/"/g, '""') + '"';
      }).join(","));
    });
    var blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = "tenura-analyses.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  /* ---------- load ---------- */

  function load() {
    wireToolbar();
    return api("/api/analyses")
      .then(function (data) {
        state.all = (data && data.analyses) || [];
        renderStats(state.all);
        renderRiskChart(state.all);
        renderTrendChart(state.all);
        renderTable();
      })
      .catch(function (err) {
        $("tableBody").innerHTML =
          '<tr><td colspan="9"><div class="empty-block"><h2>We could not load your dashboard</h2>' +
          "<p>" + esc(err.message) + "</p>" +
          '<button class="btn-new" id="retryLoad" type="button">Try again</button></div></td></tr>';
        var retry = $("retryLoad");
        if (retry) retry.addEventListener("click", load);
      });
  }

  Tenura.requireSession("/dashboard")
    .then(function (user) {
      if (!user) return; // already redirecting to log in
      load();
    })
    .catch(function (err) {
      $("tableBody").innerHTML =
        '<tr><td colspan="9"><div class="empty-block"><h2>We couldn\'t confirm your session</h2>' +
        "<p>" + esc(err.message) + "</p>" +
        '<button class="btn-new" id="retrySession" type="button">Try again</button></div></td></tr>';
      var r = $("retrySession");
      if (r) r.addEventListener("click", function () { window.location.reload(); });
    });
})();

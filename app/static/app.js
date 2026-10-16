/* RentCheck — front-end logic.
   Talks to /api/agreements/analyze (paste) and /api/agreements/analyze-upload (file). */

(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const els = {
    tabs: document.querySelectorAll(".tab"),
    panelPaste: $("panel-paste"),
    panelUpload: $("panel-upload"),
    text: $("agreementText"),
    charCount: $("charCount"),
    sampleBtn: $("sampleBtn"),
    dropzone: $("dropzone"),
    fileInput: $("agreementFile"),
    fileChip: $("fileChip"),
    fileName: $("fileName"),
    clearFile: $("clearFile"),
    analyzeBtn: $("analyzeBtn"),
    analyzeBtnLabel: $("analyzeBtnLabel"),
    loading: $("loading"),
    loadingSub: $("loadingSub"),
    error: $("error"),
    errorMsg: $("errorMsg"),
    results: $("results"),
    ringFg: $("ringFg"),
    scoreValue: $("scoreValue"),
    riskLevel: $("riskLevel"),
    riskLabel: $("riskLabel"),
    scoreSummary: $("scoreSummary"),
    statFlagged: $("statFlagged"),
    statFlaggedVal: $("statFlaggedVal"),
    statMissing: $("statMissing"),
    statMissingVal: $("statMissingVal"),
    statCheckedVal: $("statCheckedVal"),
    flaggedList: $("flaggedList"),
    flaggedCount: $("flaggedCount"),
    missingList: $("missingList"),
    missingCount: $("missingCount"),
    questionsList: $("questionsList"),
    questionsSection: $("questionsSection"),
    copyQuestions: $("copyQuestions"),
    copyLabel: $("copyLabel"),
  };

  const RING_CIRCUMFERENCE = 2 * Math.PI * 64;
  els.ringFg.style.strokeDasharray = String(RING_CIRCUMFERENCE);
  els.ringFg.style.strokeDashoffset = String(RING_CIRCUMFERENCE);

  let mode = "paste";
  let lastQuestions = [];

  /* ---------- helpers ---------- */

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function titleCase(type) {
    return String(type || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function riskFor(score) {
    if (score >= 55) return { key: "high", label: "High risk", cls: "risk-high", color: "var(--high)" };
    if (score >= 25) return { key: "medium", label: "Moderate risk", cls: "risk-medium", color: "var(--medium)" };
    return { key: "low", label: "Low risk", cls: "risk-low", color: "var(--brand)" };
  }

  function severityRank(sev) {
    return sev === "high" ? 3 : sev === "medium" ? 2 : 1;
  }

  /* ---------- tabs ---------- */

  function setMode(next) {
    mode = next;
    els.tabs.forEach((tab) => {
      const active = tab.dataset.mode === next;
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    els.panelPaste.hidden = next !== "paste";
    els.panelUpload.hidden = next !== "upload";
    els.analyzeBtnLabel.textContent = next === "paste" ? "Analyse agreement" : "Analyse file";
  }

  els.tabs.forEach((tab) => {
    tab.addEventListener("click", () => setMode(tab.dataset.mode));
  });

  /* ---------- paste: char count + sample ---------- */

  function updateCharCount() {
    const n = els.text.value.length;
    els.charCount.textContent = n.toLocaleString() + " character" + (n === 1 ? "" : "s");
  }
  els.text.addEventListener("input", updateCharCount);

  const SAMPLE = [
    "1. TERM. The tenancy is for a term of two (2) years from the date of this agreement.",
    "2. TO PAY all taxes, rates, duties, assessments and outgoings whatsoever in respect of the demised premises.",
    "3. Provided that if any part of the rent hereby reserved is in arrears for 21 days, whether or not lawfully",
    "demanded, the Landlord may re-enter the demised premises and the term shall absolutely cease and determine.",
  ].join("\n");

  els.sampleBtn.addEventListener("click", () => {
    setMode("paste");
    els.text.value = SAMPLE;
    updateCharCount();
    els.text.focus();
  });

  /* ---------- upload: drag & drop ---------- */

  function showFile(file) {
    if (!file) {
      els.fileChip.classList.remove("show");
      els.fileName.textContent = "";
      return;
    }
    els.fileName.textContent = file.name;
    els.fileChip.classList.add("show");
  }

  els.fileInput.addEventListener("change", () => showFile(els.fileInput.files[0]));
  els.clearFile.addEventListener("click", (e) => {
    e.preventDefault();
    els.fileInput.value = "";
    showFile(null);
  });

  ["dragenter", "dragover"].forEach((evt) =>
    els.dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      els.dropzone.classList.add("dragover");
    })
  );
  ["dragleave", "drop"].forEach((evt) =>
    els.dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      els.dropzone.classList.remove("dragover");
    })
  );
  els.dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer && e.dataTransfer.files;
    if (files && files.length) {
      els.fileInput.files = files;
      showFile(files[0]);
    }
  });

  /* ---------- state ---------- */

  function setBusy(busy) {
    els.analyzeBtn.disabled = busy;
    els.loading.hidden = !busy;
    if (busy) {
      els.error.hidden = true;
      els.results.hidden = true;
      startLoadingSteps();
    }
  }

  let loadingTimer = null;
  const LOADING_STEPS = [
    "Splitting your agreement into clauses…",
    "Matching clauses against Nigerian rental norms…",
    "Checking each clause and verifying evidence…",
    "Putting your report together…",
  ];
  function startLoadingSteps() {
    let i = 0;
    els.loadingSub.textContent = LOADING_STEPS[0];
    clearInterval(loadingTimer);
    loadingTimer = setInterval(() => {
      i = (i + 1) % LOADING_STEPS.length;
      els.loadingSub.textContent = LOADING_STEPS[i];
    }, 2600);
  }
  function stopLoadingSteps() {
    clearInterval(loadingTimer);
    loadingTimer = null;
  }

  function showError(message) {
    els.errorMsg.textContent = String(message || "Something went wrong.");
    els.error.hidden = false;
  }

  async function handleResponse(res) {
    if (res.ok) return res.json();
    let detail = "Request failed (HTTP " + res.status + ")";
    try {
      const ct = res.headers.get("content-type") || "";
      if (ct.includes("application/json")) {
        const body = await res.json();
        if (body) {
          if (typeof body.detail === "string") detail = body.detail;
          else if (body.detail) detail = JSON.stringify(body.detail);
          else if (body.error) detail = "Server error (" + body.error + "). Please try again.";
        }
      } else {
        const text = (await res.text()).trim();
        if (text) detail = "Request failed (HTTP " + res.status + "): " + text.slice(0, 300);
      }
    } catch (e) {
      /* keep default */
    }
    throw new Error(detail);
  }

  /* ---------- render ---------- */

  function render(data) {
    const score = Math.max(0, Math.min(100, Number(data.risk_score) || 0));
    const risk = riskFor(score);

    // Ring
    els.ringFg.style.stroke = risk.color;
    const offset = RING_CIRCUMFERENCE * (1 - score / 100);
    requestAnimationFrame(() => {
      els.ringFg.style.strokeDashoffset = String(offset);
    });
    els.scoreValue.textContent = String(score);
    els.riskLevel.className = "risk-level " + risk.cls;
    els.riskLabel.textContent = risk.label;
    els.scoreSummary.textContent = data.summary || "";

    const flagged = (data.flagged_clauses || []).slice().sort((a, b) => severityRank(b.severity) - severityRank(a.severity));
    const missing = data.missing_protections || [];
    const questions = data.questions_to_ask || [];
    lastQuestions = questions;

    // Stats
    els.statFlaggedVal.textContent = String(flagged.length);
    els.statFlagged.className = "stat " + (flagged.length === 0 ? "is-low" : risk.key === "high" ? "is-high" : "is-medium");
    els.statMissingVal.textContent = String(missing.length);
    els.statMissing.className = "stat " + (missing.length === 0 ? "is-low" : "is-medium");
    els.statCheckedVal.textContent = String(extractChecked(data.summary));

    // Flagged
    els.flaggedCount.textContent = String(flagged.length);
    if (flagged.length === 0) {
      els.flaggedList.innerHTML =
        '<div class="empty">No flagged clauses found — the clauses we checked look broadly reasonable.</div>';
    } else {
      els.flaggedList.innerHTML = flagged.map(renderFinding).join("");
    }

    // Missing protections
    els.missingCount.textContent = String(missing.length);
    els.missingList.innerHTML = missing.length
      ? missing.map(renderMissing).join("")
      : '<div class="empty">All expected protections appear to be present.</div>';

    // Questions
    if (questions.length) {
      els.questionsSection.hidden = false;
      els.questionsList.innerHTML = questions
        .map(
          (q, i) =>
            '<li><span class="q-check">' + (i + 1) + '</span><p>' + escapeHtml(q) + "</p></li>"
        )
        .join("");
    } else {
      els.questionsSection.hidden = true;
      els.questionsList.innerHTML = "";
    }

    els.results.hidden = false;
    els.results.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function extractChecked(summary) {
    const m = /of\s+(\d+)\s+checked/i.exec(summary || "");
    return m ? m[1] : "—";
  }

  function renderFinding(c) {
    const sev = (c.severity || "low").toLowerCase();
    const src = c.source === "rule"
      ? '<span class="badge src-rule">Rule</span>'
      : '<span class="badge src-ai">AI suggestion</span>';
    const evidence = c.evidence
      ? '<div class="evidence">Based on: <b>&ldquo;' + escapeHtml(c.evidence) + '&rdquo;</b></div>'
      : "";
    const clause = c.clause
      ? '<details><summary><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>View original clause</summary><blockquote>' +
        escapeHtml(c.clause) + "</blockquote></details>"
      : "";

    return (
      '<article class="finding sev-' + sev + '">' +
      '<div class="finding-top">' +
      '<span class="finding-title">' + escapeHtml(titleCase(c.clause_type)) + "</span>" +
      '<span class="badge sev-' + sev + '">' + escapeHtml(sev) + "</span>" +
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

  /* ---------- run ---------- */

  async function run() {
    if (mode === "paste") {
      const text = els.text.value.trim();
      if (!text) {
        showError("Please paste a tenancy agreement first, or switch to Upload file.");
        return;
      }
      setBusy(true);
      try {
        const res = await fetch("/api/agreements/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: text }),
        });
        render(await handleResponse(res));
      } catch (err) {
        showError(err.message);
      } finally {
        stopLoadingSteps();
        setBusy(false);
      }
      return;
    }

    // upload mode
    const file = els.fileInput.files && els.fileInput.files[0];
    if (!file) {
      showError("Please choose a file to upload first, or switch to Paste text.");
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/agreements/analyze-upload", { method: "POST", body: form });
      render(await handleResponse(res));
    } catch (err) {
      showError(err.message);
    } finally {
      stopLoadingSteps();
      setBusy(false);
    }
  }

  els.analyzeBtn.addEventListener("click", run);
  els.text.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") run();
  });

  /* ---------- copy questions ---------- */

  els.copyQuestions.addEventListener("click", async () => {
    const text = lastQuestions.map((q, i) => i + 1 + ". " + q).join("\n");
    try {
      await navigator.clipboard.writeText(text);
      els.copyLabel.textContent = "Copied!";
    } catch (e) {
      els.copyLabel.textContent = "Copy failed";
    }
    setTimeout(() => (els.copyLabel.textContent = "Copy"), 1800);
  });

  updateCharCount();
})();

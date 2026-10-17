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
    dzEmpty: $("dzEmpty"),
    dzFile: $("dzFile"),
    fileName: $("fileName"),
    fileSize: $("fileSize"),
    fileError: $("fileError"),
    removeFile: $("removeFile"),
    replaceFile: $("replaceFile"),

    analyzeBtn: $("analyzeBtn"),
    analyzeBtnLabel: $("analyzeBtnLabel"),
    btnIcon: document.querySelector("#analyzeBtn .btn-icon"),
    btnSpinner: $("btnSpinner"),

    loading: $("loading"),
    loadingSub: $("loadingSub"),
    error: $("error"),
    errorMsg: $("errorMsg"),
    notice: $("notice"),
    noticeTitle: $("noticeTitle"),
    noticeMessage: $("noticeMessage"),
    noticeAction: $("noticeAction"),
    inputPanel: $("inputPanel"),
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

  const MAX_BYTES = 15 * 1024 * 1024; // 15 MB
  const DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  const ALLOWED_EXT = ["pdf", "docx", "txt", "md", "markdown", "png", "jpg", "jpeg", "webp", "bmp", "tiff"];
  const ALLOWED_MIME = [
    "application/pdf",
    DOCX_MIME,
    "text/plain",
    "text/markdown",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/bmp",
    "image/tiff",
  ];

  let mode = "paste";
  let busy = false;
  let validFile = null;
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

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function riskFor(score) {
    if (score >= 55) return { key: "high", label: "High risk", cls: "risk-high", color: "var(--high)" };
    if (score >= 25) return { key: "medium", label: "Moderate risk", cls: "risk-medium", color: "var(--medium)" };
    return { key: "low", label: "Low risk", cls: "risk-low", color: "var(--brand)" };
  }

  function severityRank(sev) {
    return sev === "high" ? 3 : sev === "medium" ? 2 : 1;
  }

  /* ---------- tabs / mode ---------- */

  function setMode(next) {
    mode = next;
    els.tabs.forEach((tab) => {
      tab.setAttribute("aria-selected", tab.dataset.mode === next ? "true" : "false");
    });
    els.panelPaste.hidden = next !== "paste";
    els.panelUpload.hidden = next !== "upload";
    if (!busy) {
      els.analyzeBtnLabel.textContent = next === "paste" ? "Analyse agreement" : "Analyse file";
    }
    refreshButtonState();
  }

  els.tabs.forEach((tab) => {
    tab.addEventListener("click", () => setMode(tab.dataset.mode));
  });

  function refreshButtonState() {
    els.analyzeBtn.disabled = busy || (mode === "upload" && !validFile);
  }

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

  /* ---------- upload: validation + state ---------- */

  function validateFile(file) {
    if (!file) return "Please choose a file.";
    if (file.size === 0) return "That file is empty. Please choose a document that has content.";
    if (file.size > MAX_BYTES) {
      return "That file is " + formatSize(file.size) + ". The maximum upload size is 15 MB.";
    }
    const ext = (file.name.split(".").pop() || "").toLowerCase();
    const type = (file.type || "").toLowerCase();
    const okExt = ALLOWED_EXT.indexOf(ext) !== -1;
    const okMime = ALLOWED_MIME.indexOf(type) !== -1;
    if (!okExt && !okMime) {
      return "Unsupported file type. Please upload a PDF, a Word document (.docx), an image (PNG/JPG/WEBP), or a .txt file.";
    }
    return null;
  }

  function setFileError(message) {
    if (message) {
      els.fileError.textContent = message;
      els.fileError.hidden = false;
    } else {
      els.fileError.textContent = "";
      els.fileError.hidden = true;
    }
  }

  function renderEmptyState() {
    validFile = null;
    els.dzEmpty.hidden = false;
    els.dzFile.hidden = true;
    els.dropzone.classList.remove("has-file");
    els.dropzone.setAttribute(
      "aria-label",
      "Drop your file here, or click to browse. Upload a tenancy agreement to analyse."
    );
    els.fileInput.value = "";
    refreshButtonState();
  }

  function renderFileState(file) {
    validFile = file;
    els.fileName.textContent = file.name;
    els.fileName.title = file.name;
    els.fileSize.textContent = formatSize(file.size);
    els.dzEmpty.hidden = true;
    els.dzFile.hidden = false;
    els.dropzone.classList.add("has-file");
    els.dropzone.setAttribute(
      "aria-label",
      "Selected file " + file.name + ", " + formatSize(file.size) + ". Activate to replace the file."
    );
    refreshButtonState();
  }

  function acceptFile(file) {
    const error = validateFile(file);
    if (error) {
      setFileError(error);
      renderEmptyState();
      return false;
    }
    setFileError(null);
    renderFileState(file);
    return true;
  }

  // Opens the native file picker.
  function openPicker() {
    els.fileInput.click();
  }

  els.fileInput.addEventListener("change", () => {
    const file = els.fileInput.files && els.fileInput.files[0];
    if (file) acceptFile(file);
  });

  // Dropzone acts as a button: click opens picker (unless a child button was hit).
  els.dropzone.addEventListener("click", (e) => {
    if (e.target.closest(".file-btn, .file-remove")) return;
    openPicker();
  });

  els.dropzone.addEventListener("keydown", (e) => {
    if (e.target !== els.dropzone) return; // let inner buttons handle their own keys
    if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
      e.preventDefault();
      openPicker();
    }
  });

  els.replaceFile.addEventListener("click", (e) => {
    e.stopPropagation();
    openPicker();
  });

  els.removeFile.addEventListener("click", (e) => {
    e.stopPropagation();
    setFileError(null);
    renderEmptyState();
    els.dropzone.focus();
  });

  // Drag & drop
  ["dragenter", "dragover"].forEach((evt) =>
    els.dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      els.dropzone.classList.add("dragover");
    })
  );
  ["dragleave", "dragend", "drop"].forEach((evt) =>
    els.dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      els.dropzone.classList.remove("dragover");
    })
  );
  els.dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer && e.dataTransfer.files;
    if (files && files.length) acceptFile(files[0]);
  });

  /* ---------- busy / loading ---------- */

  const LOADING_STEPS = [
    "Splitting your agreement into clauses…",
    "Matching clauses against Nigerian rental norms…",
    "Checking each clause and verifying evidence…",
    "Putting your report together…",
  ];
  let loadingTimer = null;

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

  function setBusy(value) {
    busy = value;
    els.loading.hidden = !value;
    if (value) {
      els.error.hidden = true;
      els.notice.hidden = true;
      els.results.hidden = true;
      els.btnIcon.hidden = true;
      els.btnSpinner.hidden = false;
      els.analyzeBtnLabel.textContent = "Analysing…";
      startLoadingSteps();
    } else {
      els.btnIcon.hidden = false;
      els.btnSpinner.hidden = true;
      els.analyzeBtnLabel.textContent = mode === "paste" ? "Analyse agreement" : "Analyse file";
      stopLoadingSteps();
    }
    refreshButtonState();
  }

  function showError(message) {
    els.errorMsg.textContent = String(message || "Something went wrong.");
    els.error.hidden = false;
  }

  async function handleResponse(res) {
    if (res.ok) return res.json();
    let detail = "Request failed (HTTP " + res.status + ").";
    try {
      const ct = res.headers.get("content-type") || "";
      if (ct.indexOf("application/json") !== -1) {
        const body = await res.json();
        if (body) {
          if (typeof body.detail === "string") detail = body.detail;
          else if (body.detail) detail = JSON.stringify(body.detail);
          else if (typeof body.error === "string") detail = body.error;
          else if (typeof body.message === "string") detail = body.message;
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

  /* ---------- render results ---------- */

  function handleResult(data) {
    if (data && data.status && data.status !== "ok") {
      renderNotice(data);
    } else {
      render(data);
    }
  }

  function renderNotice(data) {
    const unreadable =
      data.status === "unreadable" || data.document_type === "unreadable";

    if (unreadable) {
      els.noticeTitle.textContent = "We couldn't read this file";
    } else {
      els.noticeTitle.textContent = "This doesn't look like a tenancy agreement";
    }

    // Prefer the server's composed message; fall back to building it here.
    let message = (data.message || "").trim();
    if (!message) {
      if (unreadable) {
        message =
          "We couldn't read this file clearly. Please upload a sharper photo or a PDF/text version of your tenancy agreement.";
      } else {
        const reason = (data.reason || "").trim().replace(/\.$/, "");
        message = "This doesn't look like a tenancy agreement.";
        if (reason) message += " It looks like " + reason + ".";
        message += " Please upload your actual tenancy agreement, lease, or rental contract.";
      }
    }

    els.noticeMessage.textContent = message;
    els.results.hidden = true;
    els.error.hidden = true;
    els.notice.hidden = false;
    els.notice.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function render(data) {
    const score = Math.max(0, Math.min(100, Number(data.risk_score) || 0));
    const risk = riskFor(score);

    els.ringFg.style.stroke = risk.color;
    const offset = RING_CIRCUMFERENCE * (1 - score / 100);
    requestAnimationFrame(() => {
      els.ringFg.style.strokeDashoffset = String(offset);
    });
    els.scoreValue.textContent = String(score);
    els.riskLevel.className = "risk-level " + risk.cls;
    els.riskLabel.textContent = risk.label;
    els.scoreSummary.textContent = data.summary || "";

    const flagged = (data.flagged_clauses || [])
      .slice()
      .sort((a, b) => severityRank(b.severity) - severityRank(a.severity));
    const missing = data.missing_protections || [];
    const questions = data.questions_to_ask || [];
    lastQuestions = questions;

    els.statFlaggedVal.textContent = String(flagged.length);
    els.statFlagged.className =
      "stat " + (flagged.length === 0 ? "is-low" : risk.key === "high" ? "is-high" : "is-medium");
    els.statMissingVal.textContent = String(missing.length);
    els.statMissing.className = "stat " + (missing.length === 0 ? "is-low" : "is-medium");
    els.statCheckedVal.textContent = String(extractChecked(data.summary));

    els.flaggedCount.textContent = String(flagged.length);
    els.flaggedList.innerHTML = flagged.length
      ? flagged.map(renderFinding).join("")
      : '<div class="empty">No flagged clauses found — the clauses we checked look broadly reasonable.</div>';

    els.missingCount.textContent = String(missing.length);
    els.missingList.innerHTML = missing.length
      ? missing.map(renderMissing).join("")
      : '<div class="empty">All expected protections appear to be present.</div>';

    if (questions.length) {
      els.questionsSection.hidden = false;
      els.questionsList.innerHTML = questions
        .map((q, i) => '<li><span class="q-check">' + (i + 1) + '</span><p>' + escapeHtml(q) + "</p></li>")
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
    const src =
      c.source === "rule"
        ? '<span class="badge src-rule">Rule</span>'
        : '<span class="badge src-ai">AI suggestion</span>';
    const evidence = c.evidence
      ? '<div class="evidence">Based on: <b>&ldquo;' + escapeHtml(c.evidence) + "&rdquo;</b></div>"
      : "";
    const clause = c.clause
      ? '<details><summary><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>View original clause</summary><blockquote>' +
        escapeHtml(c.clause) +
        "</blockquote></details>"
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
        handleResult(await handleResponse(res));
      } catch (err) {
        showError(err.message);
      } finally {
        setBusy(false);
      }
      return;
    }

    // upload mode
    if (!validFile) {
      const err = validateFile(null);
      setFileError(err);
      refreshButtonState();
      return;
    }
    const revalidate = validateFile(validFile);
    if (revalidate) {
      setFileError(revalidate);
      renderEmptyState();
      return;
    }

    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", validFile, validFile.name);
      const res = await fetch("/api/agreements/analyze-upload", { method: "POST", body: form });
      handleResult(await handleResponse(res));
    } catch (err) {
      showError(err.message);
    } finally {
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

  /* ---------- notice action (upload another / paste) ---------- */

  els.noticeAction.addEventListener("click", () => {
    els.notice.hidden = true;
    if (els.inputPanel) {
      els.inputPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (mode === "upload") {
      els.dropzone.focus();
    } else {
      els.text.focus();
    }
  });

  /* ---------- init ---------- */

  renderEmptyState();
  setMode("paste");
  updateCharCount();
})();

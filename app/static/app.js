/* Tenura — front-end logic for the analyser.
   Talks to /api/agreements/analyze (paste) and /api/agreements/analyze-upload
   (file), through Tenura.apiFetch in common.js (which handles the host's cold-start
   503s and retries). */

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
    loadingTitle: $("loadingTitle"),
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
    coverageBanner: $("coverageBanner"),
    coverageTitle: $("coverageTitle"),
    coverageNote: $("coverageNote"),
    statFlagged: $("statFlagged"),
    statFlaggedVal: $("statFlaggedVal"),
    statMissing: $("statMissing"),
    statMissingVal: $("statMissingVal"),
    statCheckedVal: $("statCheckedVal"),
    flaggedList: $("flaggedList"),
    flaggedCount: $("flaggedCount"),
    flaggedFilters: $("flaggedFilters"),
    missingList: $("missingList"),
    missingCount: $("missingCount"),
    questionsList: $("questionsList"),
    questionsSection: $("questionsSection"),
    copyQuestions: $("copyQuestions"),
    copyLabel: $("copyLabel"),

    saveBanner: $("saveBanner"),
    saveTitle: $("saveTitle"),
    saveText: $("saveText"),
    saveActions: $("saveActions"),
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
  let lastFlagged = [];
  let severityFilter = "all";

  /* ---------- helpers ---------- */
  /* escapeHtml / titleCase / riskFor live in common.js, so a saved analysis
     opened from History renders exactly the way it does here. */

  const escapeHtml = Tenura.escapeHtml;
  const titleCase = Tenura.titleCase;

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
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

  function startLoadingSteps(initial) {
    let i = 0;
    els.loadingSub.textContent = initial || LOADING_STEPS[0];
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
      hideSaveBanner();
      els.btnIcon.hidden = true;
      els.btnSpinner.hidden = false;
      els.analyzeBtnLabel.textContent = "Analysing…";
      if (els.loadingTitle) {
        els.loadingTitle.textContent =
          mode === "upload" ? "Uploading and analysing…" : "Analysing your agreement…";
      }
      els.loading.classList.toggle("is-upload", mode === "upload");
      startLoadingSteps(mode === "upload" ? "Uploading your file securely…" : LOADING_STEPS[0]);
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

  /* ---------- render results ---------- */

  function handleResult(data, context) {
    if (data && data.status && data.status !== "ok") {
      renderNotice(data);
      hideSaveBanner();
    } else {
      render(data);
      afterResult(data, context || {});
    }
  }

  /* ---------- saving: the guest prompt and the "save that one" offer ---------- */

  function hideSaveBanner() {
    if (els.saveBanner) els.saveBanner.hidden = true;
  }

  function renderSaveBanner(config) {
    if (!els.saveBanner) return;
    els.saveTitle.textContent = config.title;
    els.saveText.textContent = config.text || "";
    els.saveActions.innerHTML = "";

    (config.actions || []).forEach((action) => {
      let element;
      if (action.href) {
        element = document.createElement("a");
        element.href = action.href;
        element.className = "btn " + (action.primary ? "btn-primary" : "btn-ghost");
      } else {
        element = document.createElement("button");
        element.type = "button";
        element.className = "btn " + (action.primary ? "btn-primary" : "btn-ghost");
        element.addEventListener("click", () => runBannerAction(action.action, element));
      }
      element.textContent = action.label;
      els.saveActions.appendChild(element);
    });

    els.saveBanner.hidden = false;
  }

  function runBannerAction(action, element) {
    if (action === "dismiss" || action === "discard-pending") {
      // Declining means declining for this session; the held text goes with it.
      Tenura.pending.clear();
      hideSaveBanner();
      return;
    }
    if (action === "save-pending") {
      savePendingAnalysis(element);
    }
  }

  // The analysis the user ran as a guest is re-run under their new session so
  // the server stores it properly — we never trust a client-supplied result.
  async function savePendingAnalysis(button) {
    const pending = Tenura.pending.get();
    if (!pending) {
      hideSaveBanner();
      return;
    }

    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Saving…";

    try {
      await Tenura.apiFetch("/api/agreements/analyze", {
        method: "POST",
        body: JSON.stringify({ text: pending.text }),
      });
      Tenura.pending.clear();
      window.location.href = "/history";
    } catch (err) {
      button.disabled = false;
      button.textContent = original;
      Tenura.setStatus("Could not save that analysis: " + err.message);
      setTimeout(() => Tenura.setStatus(null), 6000);
    }
  }

  function afterResult(data, context) {
    if (data.saved) {
      Tenura.pending.clear();
      renderSaveBanner({
        title: "Saved to your history",
        text:
          "This analysis is in your account. You can rename it or delete it, " +
          "and the agreement text with it, whenever you like.",
        actions: [{ label: "View in history", href: "/history", primary: true }],
      });
      return;
    }

    // Guest: the result is not stored anywhere. Offer to keep it — the text is
    // held in this tab only, and only if we have it (paste, not upload).
    if (context.text) Tenura.pending.save(context.text);

    renderSaveBanner({
      title: "Keep this analysis?",
      text: context.text
        ? "Create a free account and we'll save this analysis to your history, so you can come back to it."
        : "Create a free account and future analyses are saved to your history automatically.",
      actions: [
        { label: "Create a free account", href: "/signup", primary: true },
        { label: "Not now", action: "dismiss" },
      ],
    });
  }

  function renderNotice(data) {
    const unreadable =
      data.status === "unreadable" || data.document_type === "unreadable";
    const outOfScope = data.status === "out_of_scope";
    const needsJurisdiction = data.status === "needs_jurisdiction";

    if (unreadable) {
      els.noticeTitle.textContent = "We couldn't read this file";
    } else if (outOfScope) {
      els.noticeTitle.textContent = "This looks like a non-Nigerian agreement";
    } else if (needsJurisdiction) {
      els.noticeTitle.textContent = "Which country is this agreement for?";
    } else {
      els.noticeTitle.textContent = "This doesn't look like a tenancy agreement";
    }

    // Prefer the server's composed message; fall back to building it here.
    let message = (data.message || "").trim();
    if (!message) {
      if (unreadable) {
        message =
          "We couldn't read this file clearly. Please upload a sharper photo or a PDF/text version of your tenancy agreement.";
      } else if (outOfScope || needsJurisdiction) {
        message =
          "Tenura only reviews Nigerian tenancy agreements, and judging a foreign one against Nigerian rules would be misleading.";
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
    // The server decides the band (it knows the coverage). Fall back to the
    // shared client mirror if an older response omits it.
    const band =
      data.risk_band ||
      Tenura.bandFor(score, data.coverage, !!data.degraded);
    const risk = Tenura.riskForBand(band);

    els.ringFg.style.stroke = risk.color;
    const offset = RING_CIRCUMFERENCE * (1 - score / 100);
    requestAnimationFrame(() => {
      els.ringFg.style.strokeDashoffset = String(offset);
    });
    els.scoreValue.textContent = String(score);
    els.riskLevel.className = "risk-level " + risk.cls;
    els.riskLabel.textContent = risk.label;
    els.scoreSummary.textContent = data.summary || "";

    // Coverage banner: explain a thin/degraded run in plain language so a
    // score of 0 can never read as "nothing to worry about".
    if (els.coverageBanner) {
      const note = (data.coverage_note || "").trim();
      if (data.degraded || (typeof data.coverage === "number" && data.coverage < 0.6)) {
        els.coverageTitle.textContent = "How much of this agreement we checked";
        els.coverageNote.textContent = note || "We could not check enough of this agreement to rate it.";
        els.coverageBanner.hidden = false;
      } else if (note) {
        els.coverageTitle.textContent = "How much of this agreement we checked";
        els.coverageNote.textContent = note;
        els.coverageBanner.hidden = false;
      } else {
        els.coverageBanner.hidden = true;
      }
    }

    const flagged = Tenura.sortFindings(data.flagged_clauses);
    const missing = data.missing_protections || [];
    const questions = data.questions_to_ask || [];
    lastQuestions = questions;

    els.statFlaggedVal.textContent = String(flagged.length);
    els.statFlagged.className =
      "stat " + (flagged.length === 0 ? "is-low" : risk.key === "high" ? "is-high" : "is-medium");
    els.statMissingVal.textContent = String(missing.length);
    els.statMissing.className = "stat " + (missing.length === 0 ? "is-low" : "is-medium");
    els.statCheckedVal.textContent = String(extractChecked(data.summary));

    lastFlagged = flagged;
    els.flaggedCount.textContent = String(flagged.length);
    const distinctSeverities = new Set(
      flagged.map((c) => (c.severity || "low").toLowerCase())
    );
    if (els.flaggedFilters) {
      els.flaggedFilters.hidden = distinctSeverities.size < 2;
    }
    setSeverityFilter("all");

    els.missingCount.textContent = String(missing.length);
    els.missingList.innerHTML = missing.length
      ? missing.map((m) => Tenura.renderMissing(m)).join("")
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

  function renderFlagged() {
    if (!lastFlagged.length) {
      els.flaggedList.innerHTML =
        '<div class="empty">No flagged clauses found — the clauses we checked look broadly reasonable.</div>';
      return;
    }
    const shown =
      severityFilter === "all"
        ? lastFlagged
        : lastFlagged.filter((c) => (c.severity || "low").toLowerCase() === severityFilter);
    els.flaggedList.innerHTML = shown.length
      ? shown.map((c) => Tenura.renderFinding(c)).join("")
      : '<div class="empty">No clauses were flagged at ' + escapeHtml(severityFilter) + " severity.</div>";
  }

  function setSeverityFilter(next) {
    severityFilter = next;
    if (els.flaggedFilters) {
      els.flaggedFilters.querySelectorAll(".chip").forEach((chip) => {
        const active = chip.dataset.sev === next;
        chip.classList.toggle("is-active", active);
        chip.setAttribute("aria-pressed", active ? "true" : "false");
      });
    }
    renderFlagged();
  }

  if (els.flaggedFilters) {
    els.flaggedFilters.addEventListener("click", (e) => {
      const chip = e.target.closest(".chip");
      if (chip && chip.dataset.sev) setSeverityFilter(chip.dataset.sev);
    });
  }

  function extractChecked(summary) {
    const m = /of\s+(\d+)\s+checked/i.exec(summary || "");
    return m ? m[1] : "—";
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
        const data = await Tenura.apiFetch("/api/agreements/analyze", {
          method: "POST",
          body: JSON.stringify({ text: text }),
        });
        handleResult(data, { text: text });
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
      const data = await Tenura.apiFetch("/api/agreements/analyze-upload", {
        method: "POST",
        body: form,
      });
      handleResult(data, {});
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

  // Once the header knows who is signed in, offer to save a guest analysis that
  // is still waiting in this tab (they ran it, then created an account).
  Tenura.ready.then((user) => {
    const pending = Tenura.pending.get();
    if (!user || !pending) return;
    renderSaveBanner({
      title: "Save the analysis you just ran?",
      text:
        "You analysed an agreement before signing in. Add it to your account and " +
        "it will be waiting for you next time.",
      actions: [
        { label: "Save it to my account", action: "save-pending", primary: true },
        { label: "Discard", action: "discard-pending" },
      ],
    });
  });
})();

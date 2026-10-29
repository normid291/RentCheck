/* Tenura — log in, plus the two flows that reuse the email code:
 *   - an account that was never verified (the password was right, so offering
 *     to send a code reveals nothing to anyone who does not already know it)
 *   - a forgotten password
 *
 * All three end in the same code screen, which is why there is one here.
 */
(function () {
  "use strict";

  var $ = function (id) {
    return document.getElementById(id);
  };

  var els = {
    viewLogin: $("view-login"),
    viewForgot: $("view-forgot"),
    viewCode: $("view-code"),

    loginForm: $("loginForm"),
    email: $("email"),
    password: $("password"),
    loginError: $("loginError"),
    loginBtn: $("loginBtn"),
    loginSpinner: $("loginSpinner"),
    loginLabel: $("loginLabel"),
    verifyPrompt: $("verifyPrompt"),
    sendVerifyBtn: $("sendVerifyBtn"),
    forgotBtn: $("forgotBtn"),

    googleWrap: $("googleWrap"),
    googleBtn: $("googleBtn"),

    forgotForm: $("forgotForm"),
    forgotEmail: $("forgotEmail"),
    forgotError: $("forgotError"),
    forgotBtn2: $("forgotBtn2"),
    forgotSpinner: $("forgotSpinner"),
    forgotLabel: $("forgotLabel"),
    backToLogin: $("backToLogin"),

    codeTitle: $("codeTitle"),
    codeEmail: $("codeEmail"),
    codeForm: $("codeForm"),
    code: $("code"),
    codeError: $("codeError"),
    codeBtn: $("codeBtn"),
    codeSpinner: $("codeSpinner"),
    codeLabel: $("codeLabel"),
    newPasswordWrap: $("newPasswordWrap"),
    newPassword: $("newPassword"),
    newConfirm: $("newConfirm"),
    resendBtn: $("resendBtn"),
    resendHint: $("resendHint"),
    codeBack: $("codeBack"),
  };

  var email = "";
  var mode = "verify"; // "verify" | "reset"
  var cooldownTimer = null;

  function showError(el, message) {
    if (!message) {
      el.textContent = "";
      el.hidden = true;
      return;
    }
    el.textContent = message;
    el.hidden = false;
  }

  function setBusy(btn, spinner, label, busy, idle) {
    btn.disabled = busy;
    spinner.hidden = !busy;
    label.textContent = busy ? "Please wait…" : idle;
  }

  function showView(name) {
    els.viewLogin.hidden = name !== "login";
    els.viewForgot.hidden = name !== "forgot";
    els.viewCode.hidden = name !== "code";
    if (name === "login") showError(els.loginError, null);
    if (name === "forgot") showError(els.forgotError, null);
    if (name === "code") showError(els.codeError, null);
  }

  function startCooldown(seconds) {
    var remaining = Math.max(0, Math.floor(seconds || 60));
    clearInterval(cooldownTimer);
    els.resendBtn.disabled = true;
    els.resendHint.hidden = false;

    function tick() {
      if (remaining <= 0) {
        clearInterval(cooldownTimer);
        cooldownTimer = null;
        els.resendBtn.disabled = false;
        els.resendHint.hidden = true;
        els.resendHint.textContent = "";
        return;
      }
      els.resendHint.textContent = "You can resend in " + remaining + "s.";
      remaining -= 1;
    }

    tick();
    cooldownTimer = setInterval(tick, 1000);
  }

  function goToCode(nextMode, address) {
    mode = nextMode;
    email = address;
    els.codeEmail.textContent = address;
    els.codeTitle.textContent = mode === "reset" ? "Reset your password" : "Verify your email";
    els.codeLabel.textContent = mode === "reset" ? "Set new password" : "Continue";
    els.newPasswordWrap.hidden = mode !== "reset";
    els.code.value = "";
    if (mode === "reset") els.newPassword.value = "";
    if (els.newConfirm) els.newConfirm.value = "";
    showView("code");
    els.code.focus();
    startCooldown(60);
  }

  /* ---------- log in ---------- */

  els.loginForm.addEventListener("submit", function (event) {
    event.preventDefault();
    showError(els.loginError, null);
    els.verifyPrompt.hidden = true;

    var address = els.email.value.trim();
    if (!address || !els.password.value) {
      showError(els.loginError, "Enter your email and password.");
      return;
    }

    setBusy(els.loginBtn, els.loginSpinner, els.loginLabel, true, "Log in");
    Tenura.apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: address, password: els.password.value }),
    })
      .then(function () {
        window.location.href = Tenura.safeNext("/history");
      })
      .catch(function (err) {
        showError(els.loginError, err.message);
        var body = err.body || {};
        if (body.code === "unverified") {
          // Correct password, unfinished account: offer the code, but keep the
          // address the server named.
          email = body.email || address;
          els.verifyPrompt.hidden = false;
        }
      })
      .then(function () {
        setBusy(els.loginBtn, els.loginSpinner, els.loginLabel, false, "Log in");
      });
  });

  els.sendVerifyBtn.addEventListener("click", function () {
    showError(els.loginError, null);
    els.sendVerifyBtn.disabled = true;
    Tenura.apiFetch("/api/auth/resend-otp", {
      method: "POST",
      body: JSON.stringify({ email: email }),
    })
      .then(function () {
        goToCode("verify", email);
      })
      .catch(function (err) {
        showError(els.loginError, err.message);
      })
      .then(function () {
        els.sendVerifyBtn.disabled = false;
      });
  });

  /* ---------- forgot password ---------- */

  els.forgotBtn.addEventListener("click", function () {
    els.forgotEmail.value = els.email.value.trim() || email;
    showView("forgot");
    els.forgotEmail.focus();
  });

  els.backToLogin.addEventListener("click", function () {
    showView("login");
  });

  els.forgotForm.addEventListener("submit", function (event) {
    event.preventDefault();
    showError(els.forgotError, null);

    var address = els.forgotEmail.value.trim();
    if (!address) {
      showError(els.forgotError, "Please enter your email address.");
      return;
    }

    setBusy(els.forgotBtn2, els.forgotSpinner, els.forgotLabel, true, "Send reset code");
    Tenura.apiFetch("/api/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email: address }),
    })
      .then(function (data) {
        goToCode("reset", (data && data.email) || address);
      })
      .catch(function (err) {
        showError(els.forgotError, err.message);
      })
      .then(function () {
        setBusy(els.forgotBtn2, els.forgotSpinner, els.forgotLabel, false, "Send reset code");
      });
  });

  /* ---------- the code ---------- */

  els.codeForm.addEventListener("submit", function (event) {
    event.preventDefault();
    showError(els.codeError, null);

    var code = els.code.value.replace(/\D/g, "");
    if (code.length !== 6) {
      showError(els.codeError, "Enter the 6-digit code from your email.");
      els.code.focus();
      return;
    }

    if (mode === "reset") {
      if (els.newPassword.value.length < 8) {
        showError(els.codeError, "Your new password must be at least 8 characters.");
        els.newPassword.focus();
        return;
      }
      if (els.newPassword.value !== els.newConfirm.value) {
        showError(els.codeError, "Those passwords don't match.");
        els.newConfirm.focus();
        return;
      }
    }

    var idle = mode === "reset" ? "Set new password" : "Continue";
    setBusy(els.codeBtn, els.codeSpinner, els.codeLabel, true, idle);

    var request =
      mode === "reset"
        ? Tenura.apiFetch("/api/auth/reset-password", {
            method: "POST",
            body: JSON.stringify({
              email: email,
              code: code,
              password: els.newPassword.value,
            }),
          })
        : Tenura.apiFetch("/api/auth/verify-otp", {
            method: "POST",
            body: JSON.stringify({ email: email, code: code }),
          });

    request
      .then(function () {
        window.location.href = Tenura.safeNext("/history");
      })
      .catch(function (err) {
        showError(els.codeError, err.message);
      })
      .then(function () {
        setBusy(els.codeBtn, els.codeSpinner, els.codeLabel, false, idle);
      });
  });

  els.code.addEventListener("input", function () {
    els.code.value = els.code.value.replace(/\D/g, "").slice(0, 6);
  });

  els.resendBtn.addEventListener("click", function () {
    showError(els.codeError, null);
    els.resendBtn.disabled = true;

    var path = mode === "reset" ? "/api/auth/forgot-password" : "/api/auth/resend-otp";
    Tenura.apiFetch(path, { method: "POST", body: JSON.stringify({ email: email }) })
      .then(function (data) {
        startCooldown((data && data.resend_in) || 60);
        els.resendHint.textContent = "A new code is on its way.";
        els.resendHint.hidden = false;
      })
      .catch(function (err) {
        showError(els.codeError, err.message);
        startCooldown(err.status === 429 ? 60 : 5);
      });
  });

  els.codeBack.addEventListener("click", function () {
    clearInterval(cooldownTimer);
    els.resendHint.hidden = true;
    showView("login");
  });

  /* ---------- Google ---------- */

  Tenura.ready.then(function () {
    if (els.googleWrap && els.googleBtn && Tenura.googleEnabled()) {
      els.googleWrap.hidden = false;
      els.googleBtn.addEventListener("click", function () {
        els.googleBtn.disabled = true;
        Tenura.startGoogleSignIn();
      });
    }
    // A real failure comes back here with a specific code. A cancellation does
    // not: it returns with no code, so nothing is shown and the person can just
    // try again.
    var googleMessage = Tenura.googleError();
    if (googleMessage) {
      showError(els.loginError, googleMessage);
    }
  });

  els.email.focus();
})();

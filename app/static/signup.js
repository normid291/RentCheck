/* RentCheck — sign up: email + password, then the 6-digit code.
 *
 * The server answers the same way whether or not the address already had an
 * account, so this page always moves to the code step. That is deliberate: it
 * is what stops the sign-up form from being a way to check which emails are
 * registered.
 */
(function () {
  "use strict";

  var $ = function (id) {
    return document.getElementById(id);
  };

  var els = {
    viewSignup: $("view-signup"),
    viewOtp: $("view-otp"),
    form: $("signupForm"),
    email: $("email"),
    password: $("password"),
    confirm: $("confirm"),
    error: $("signupError"),
    btn: $("signupBtn"),
    spinner: $("signupSpinner"),
    label: $("signupLabel"),

    otpForm: $("otpForm"),
    otpEmail: $("otpEmail"),
    code: $("code"),
    otpError: $("otpError"),
    verifyBtn: $("verifyBtn"),
    verifySpinner: $("verifySpinner"),
    verifyLabel: $("verifyLabel"),

    resendBtn: $("resendBtn"),
    resendHint: $("resendHint"),
    changeEmail: $("changeEmail"),
  };

  var email = "";
  var cooldownTimer = null;

  /* ---------- small ui helpers ---------- */

  function showError(el, message) {
    if (!message) {
      el.textContent = "";
      el.hidden = true;
      return;
    }
    el.textContent = message;
    el.hidden = false;
  }

  function setBusy(btn, spinner, label, busy, idleLabel) {
    btn.disabled = busy;
    spinner.hidden = !busy;
    label.textContent = busy ? "Please wait…" : idleLabel;
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

  function goToOtp(sentEmail) {
    email = sentEmail;
    els.otpEmail.textContent = sentEmail;
    els.viewSignup.hidden = true;
    els.viewOtp.hidden = false;
    showError(els.otpError, null);
    els.code.value = "";
    els.code.focus();
    startCooldown(60);
  }

  /* ---------- step 1: sign up ---------- */

  els.form.addEventListener("submit", function (event) {
    event.preventDefault();
    showError(els.error, null);

    var value = els.email.value.trim();
    if (!value) {
      showError(els.error, "Please enter your email address.");
      els.email.focus();
      return;
    }
    if (value.indexOf("@") < 1 || value.indexOf(".") < 0) {
      showError(els.error, "Please enter a valid email address.");
      els.email.focus();
      return;
    }
    if (els.password.value.length < 8) {
      showError(els.error, "Your password must be at least 8 characters.");
      els.password.focus();
      return;
    }
    if (els.password.value !== els.confirm.value) {
      showError(els.error, "Those passwords don't match.");
      els.confirm.focus();
      return;
    }

    setBusy(els.btn, els.spinner, els.label, true, "Create account");
    RC.apiFetch("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email: value, password: els.password.value }),
    })
      .then(function (data) {
        goToOtp((data && data.email) || value);
      })
      .catch(function (err) {
        showError(els.error, err.message);
      })
      .then(function () {
        setBusy(els.btn, els.spinner, els.label, false, "Create account");
      });
  });

  /* ---------- step 2: the code ---------- */

  els.otpForm.addEventListener("submit", function (event) {
    event.preventDefault();
    showError(els.otpError, null);

    var code = els.code.value.replace(/\D/g, "");
    if (code.length !== 6) {
      showError(els.otpError, "Enter the 6-digit code from your email.");
      els.code.focus();
      return;
    }

    setBusy(els.verifyBtn, els.verifySpinner, els.verifyLabel, true, "Verify and continue");
    RC.apiFetch("/api/auth/verify-otp", {
      method: "POST",
      body: JSON.stringify({ email: email, code: code }),
    })
      .then(function () {
        window.location.href = RC.safeNext("/");
      })
      .catch(function (err) {
        showError(els.otpError, err.message);
        els.code.select();
      })
      .then(function () {
        setBusy(els.verifyBtn, els.verifySpinner, els.verifyLabel, false, "Verify and continue");
      });
  });

  // Only digits, and submit automatically once six have been typed.
  els.code.addEventListener("input", function () {
    els.code.value = els.code.value.replace(/\D/g, "").slice(0, 6);
    if (els.code.value.length === 6) els.otpForm.requestSubmit();
  });

  els.resendBtn.addEventListener("click", function () {
    showError(els.otpError, null);
    els.resendBtn.disabled = true;

    RC.apiFetch("/api/auth/resend-otp", {
      method: "POST",
      body: JSON.stringify({ email: email }),
    })
      .then(function (data) {
        startCooldown((data && data.resend_in) || 60);
        showError(els.otpError, null);
        els.resendHint.textContent = "A new code is on its way.";
        els.resendHint.hidden = false;
      })
      .catch(function (err) {
        showError(els.otpError, err.message);
        // A 429 carries the wait; honour it rather than letting them hammer it.
        startCooldown(err.status === 429 ? 60 : 5);
      });
  });

  els.changeEmail.addEventListener("click", function () {
    clearInterval(cooldownTimer);
    els.viewOtp.hidden = true;
    els.viewSignup.hidden = false;
    showError(els.error, null);
    els.email.focus();
  });

  els.email.focus();
})();

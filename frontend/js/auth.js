/* ============================================================
   auth.js — Login & Register form logic
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
  // If already logged in, skip to dashboard
  if (getToken()) {
    window.location.href = "dashboard.html";
    return;
  }

  const loginForm    = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");

  // ── Login ──────────────────────────────────────────────────
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = loginForm.querySelector(".btn-primary");
      const errEl = document.getElementById("login-error");
      const email    = document.getElementById("login-email").value.trim();
      const password = document.getElementById("login-password").value;

      errEl.classList.remove("show");
      setLoading(btn, true);

      try {
        const data = await api.login(email, password);
        setToken(data.access_token);
        window.location.href = "dashboard.html";
      } catch (err) {
        errEl.textContent = err.message || "Login failed. Check your credentials.";
        errEl.classList.add("show");
        setLoading(btn, false);
      }
    });
  }

  // ── Register ───────────────────────────────────────────────
  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = registerForm.querySelector(".btn-primary");
      const errEl = document.getElementById("register-error");
      const email    = document.getElementById("reg-email").value.trim();
      const password = document.getElementById("reg-password").value;
      const confirm  = document.getElementById("reg-confirm").value;

      errEl.classList.remove("show");

      if (password !== confirm) {
        errEl.textContent = "Passwords do not match.";
        errEl.classList.add("show");
        return;
      }
      if (password.length < 8) {
        errEl.textContent = "Password must be at least 8 characters.";
        errEl.classList.add("show");
        return;
      }

      setLoading(btn, true);
      try {
        const data = await api.register(email, password);
        setToken(data.access_token);
        window.location.href = "dashboard.html";
      } catch (err) {
        errEl.textContent = err.message || "Registration failed.";
        errEl.classList.add("show");
        setLoading(btn, false);
      }
    });
  }
});

function setLoading(btn, loading) {
  if (loading) {
    btn.disabled = true;
    btn.dataset.originalText = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span> Please wait…`;
  } else {
    btn.disabled = false;
    btn.innerHTML = btn.dataset.originalText;
  }
}

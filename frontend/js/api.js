/* ============================================================
   api.js — All fetch() wrappers for Keep an Eye
   ============================================================ */

// When served via FastAPI's StaticFiles at /ui, the API lives at the same origin.
// When opened directly as a file (file://), fall back to localhost:8000.
const BASE = location.protocol === "file:"
  ? "http://localhost:8000"
  : `${location.protocol}//${location.host}`;

// ── Auth ──────────────────────────────────────────────────────
const api = {
  register(email, password) {
    return fetch(`${BASE}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }).then(handleResponse);
  },

  login(email, password) {
    // Backend uses OAuth2PasswordRequestForm → must send form-urlencoded,
    // with field named "username" (OAuth2 spec), not JSON.
    const body = new URLSearchParams({ username: email, password });
    return fetch(`${BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    }).then(handleResponse);
  },

  me(token) {
    return fetch(`${BASE}/api/auth/me`, {
      headers: authHeader(token),
    }).then(handleResponse);
  },

  // ── Monitors ────────────────────────────────────────────────
  getMonitors(token) {
    return fetch(`${BASE}/api/monitors`, {
      headers: authHeader(token),
    }).then(handleResponse);
  },

  getMonitor(token, id) {
    return fetch(`${BASE}/api/monitors/${id}`, {
      headers: authHeader(token),
    }).then(handleResponse);
  },

  createMonitor(token, data) {
    return fetch(`${BASE}/api/monitors`, {
      method: "POST",
      headers: { ...authHeader(token), "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(handleResponse);
  },

  updateMonitor(token, id, data) {
    return fetch(`${BASE}/api/monitors/${id}`, {
      method: "PATCH",
      headers: { ...authHeader(token), "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(handleResponse);
  },

  deleteMonitor(token, id) {
    return fetch(`${BASE}/api/monitors/${id}`, {
      method: "DELETE",
      headers: authHeader(token),
    }).then((r) => {
      if (!r.ok) throw new Error("Delete failed");
      return null;
    });
  },

  pauseMonitor(token, id) {
    return fetch(`${BASE}/api/monitors/${id}/pause`, {
      method: "POST",
      headers: authHeader(token),
    }).then(handleResponse);
  },

  resumeMonitor(token, id) {
    return fetch(`${BASE}/api/monitors/${id}/resume`, {
      method: "POST",
      headers: authHeader(token),
    }).then(handleResponse);
  },

  // ── Logs ────────────────────────────────────────────────────
  getLogs(token, monitorId, limit = 50) {
    return fetch(`${BASE}/api/monitors/${monitorId}/logs?limit=${limit}`, {
      headers: authHeader(token),
    }).then(handleResponse);
  },

  getStats(token, monitorId) {
    return fetch(`${BASE}/api/monitors/${monitorId}/logs/stats`, {
      headers: authHeader(token),
    }).then(handleResponse);
  },

  // ── Alert Channels ──────────────────────────────────────────
  getAlertChannels(token, monitorId) {
    return fetch(`${BASE}/api/monitors/${monitorId}/alerts`, {
      headers: authHeader(token),
    }).then(handleResponse);
  },

  createAlertChannel(token, monitorId, data) {
    return fetch(`${BASE}/api/monitors/${monitorId}/alerts`, {
      method: "POST",
      headers: { ...authHeader(token), "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(handleResponse);
  },

  deleteAlertChannel(token, monitorId, channelId) {
    return fetch(`${BASE}/api/monitors/${monitorId}/alerts/${channelId}`, {
      method: "DELETE",
      headers: authHeader(token),
    }).then((r) => {
      if (!r.ok) throw new Error("Delete failed");
      return null;
    });
  },

  // ── Trigger (Phase 4) ────────────────────────────────────────
  triggerCheck(token, monitorId) {
    return fetch(`${BASE}/api/monitors/${monitorId}/trigger`, {
      method: "POST",
      headers: authHeader(token),
    }).then(handleResponse);
  },
};

// ── Helpers ───────────────────────────────────────────────────
function authHeader(token) {
  return { Authorization: `Bearer ${token}` };
}

async function handleResponse(r) {
  const text = await r.text();
  let data;
  try { data = JSON.parse(text); } catch { data = text; }

  if (!r.ok) {
    // Extract a human-readable message from the response body.
    const msg = (data && data.detail) ? data.detail : `HTTP ${r.status}`;
    // Throw the error — callers (dashboard.js, monitor.js) will show a toast.
    // We do NOT redirect on 401 here because a single transient 401 from any
    // API call (save channel, create monitor, etc.) must NOT log the user out.
    // Session expiry is handled exclusively by verifySession() on page load.
    throw new Error(msg);
  }
  return data;
}

// ── Token helpers ─────────────────────────────────────────────
function getToken()   { return localStorage.getItem("kae_token"); }
function setToken(t)  { localStorage.setItem("kae_token", t); }
function clearToken() { localStorage.removeItem("kae_token"); }

/**
 * requireAuth — called at the top of every protected page.
 * Returns the stored token synchronously, or redirects to login if absent.
 * Does NOT make a network call — use verifySession() for that.
 */
function requireAuth() {
  const t = getToken();
  if (!t) { window.location.href = "index.html"; return null; }
  return t;
}

/**
 * verifySession — optionally call this once per page load to confirm the
 * stored token is still accepted by the server.  Only redirects on a
 * genuine 401 from /api/auth/me (i.e. truly expired / revoked token).
 * All other errors (network down, 5xx) are silently ignored so the user
 * stays on the page.
 */
async function verifySession(token) {
  try {
    const r = await fetch(`${BASE}/api/auth/me`, { headers: authHeader(token) });
    if (r.status === 401) {
      clearToken();
      window.location.href = "index.html";
    }
    // 2xx → still valid; 4xx/5xx other than 401 → ignore
  } catch {
    // Network error — don't log the user out, just carry on
  }
}

// ── Toast utility ─────────────────────────────────────────────
function toast(msg, type = "default", duration = 3000) {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.appendChild(container);
  }
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => { el.remove(); }, duration);
}

// ── Relative time ─────────────────────────────────────────────
function timeAgo(dateStr) {
  if (!dateStr) return "—";
  const diff = Math.floor((Date.now() - new Date(dateStr)) / 1000);
  if (diff < 60)   return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

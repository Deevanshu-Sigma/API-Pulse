/* ============================================================
   dashboard.js — Monitor cards, B2B modal (auth/body/assertions)
   ============================================================ */

let TOKEN = null;
let allMonitors = [];

document.addEventListener("DOMContentLoaded", async () => {
  TOKEN = requireAuth();
  if (!TOKEN) return;

  // Verify the token is still valid with the server once per page load.
  // This is the ONLY place we'll force a logout — not inside individual API calls.
  await verifySession(TOKEN);

  await loadUser();
  await loadMonitors();
  setupModal();
  setupLogout();

  // Auto-refresh every 30 seconds
  setInterval(loadMonitors, 30_000);
});

// ── User ───────────────────────────────────────────────────────
async function loadUser() {
  try {
    const user = await api.me(TOKEN);
    document.getElementById("user-email").textContent = user.email;
  } catch {
    // Silent — not critical
  }
}

// ── Monitors ───────────────────────────────────────────────────
async function loadMonitors() {
  try {
    allMonitors = await api.getMonitors(TOKEN);
    renderStats(allMonitors);
    renderCards(allMonitors);
  } catch (err) {
    console.error("Failed to load monitors:", err);
    toast("Failed to load monitors.", "error");
  }
}

function renderStats(monitors) {
  const up      = monitors.filter((m) => m.status === "up").length;
  const down    = monitors.filter((m) => m.status === "down").length;
  const pending = monitors.filter((m) => m.status === "pending").length;
  document.getElementById("stat-total").textContent   = monitors.length;
  document.getElementById("stat-up").textContent      = up;
  document.getElementById("stat-down").textContent    = down;
  document.getElementById("stat-pending").textContent = pending;
}

function renderCards(monitors) {
  const grid = document.getElementById("monitors-grid");

  if (!monitors.length) {
    grid.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📡</div>
        <h3>No monitors yet</h3>
        <p>Add your first monitor to start tracking uptime.</p>
        <button class="btn btn-primary" onclick="openModal()">+ Add Monitor</button>
      </div>`;
    return;
  }

  grid.innerHTML = monitors.map((m) => monitorCardHTML(m)).join("");

  // Wire action buttons
  grid.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", handleCardAction);
  });
}

function monitorCardHTML(m) {
  const isActive  = m.is_active;
  const cardClass = isActive ? (m.status || "pending") : "paused";
  const badgeText = isActive ? (m.status || "pending").toUpperCase() : "PAUSED";
  const checked   = timeAgo(m.last_checked_at);

  const pauseAction   = isActive ? "pause" : "resume";
  const pauseLabel    = isActive ? "⏸ Pause" : "▶ Resume";
  const pauseBtnClass = isActive ? "btn btn-sm btn-secondary" : "btn btn-sm btn-resume";

  // B2B feature badges
  const authBadge  = m.has_auth       ? `<span class="feature-badge auth-badge"  title="Auth configured">🔐 Auth</span>`  : "";
  const assertBadge= m.has_assertions ? `<span class="feature-badge assert-badge" title="Assertions configured">✅ Rules</span>` : "";
  const methodBadge = m.method !== "GET" ? `<span class="feature-badge method-badge">${escapeHTML(m.method)}</span>` : "";

  return `
  <article class="monitor-card ${cardClass}" id="card-${m.id}">
    <div class="monitor-card-header">
      <span class="status-dot ${isActive ? (m.status || 'pending') : 'paused'}" style="margin-top:5px;"></span>
      <div style="flex:1;min-width:0;">
        <div class="monitor-card-title">${escapeHTML(m.name)}</div>
        <div class="monitor-card-url" title="${escapeHTML(m.url)}">${escapeHTML(m.url)}</div>
      </div>
      <span class="status-badge ${isActive ? (m.status || 'pending') : 'paused'}">${badgeText}</span>
    </div>

    <div class="monitor-card-meta">
      <span title="Response time">⚡ ${m.last_response_ms != null ? m.last_response_ms + " ms" : "—"}</span>
      <span title="Last checked">🕒 ${checked}</span>
      <span title="Check interval">⏱ ${m.interval_minutes}m</span>
    </div>

    ${(authBadge || assertBadge || methodBadge) ? `
    <div class="feature-badges">
      ${methodBadge}${authBadge}${assertBadge}
    </div>` : ""}

    <div class="monitor-card-actions">
      <button
        class="${pauseBtnClass}"
        data-action="${pauseAction}"
        data-id="${m.id}"
        title="${isActive ? 'Pause this monitor' : 'Resume this monitor'}">
        ${pauseLabel}
      </button>
      <button class="btn btn-sm btn-secondary" data-action="edit" data-id="${m.id}" title="Edit">
        ✏️ Edit
      </button>
      <button class="btn btn-sm btn-danger" data-action="delete" data-id="${m.id}" title="Delete">
        🗑 Delete
      </button>
      <a class="btn btn-sm btn-secondary" href="monitor.html?id=${m.id}" title="View detail">
        View →
      </a>
    </div>
  </article>`;
}

// ── Card Actions ───────────────────────────────────────────────
async function handleCardAction(e) {
  const action = e.currentTarget.dataset.action;
  const id     = e.currentTarget.dataset.id;

  if (action === "edit") {
    const monitorToEdit = allMonitors.find(m => m.id === id);
    if (monitorToEdit) openModal(monitorToEdit);
    return;
  }

  if (action === "delete") {
    if (!confirm("Delete this monitor? This cannot be undone.")) return;
    try {
      await api.deleteMonitor(TOKEN, id);
      document.getElementById(`card-${id}`)?.remove();
      allMonitors = allMonitors.filter((m) => m.id !== id);
      renderStats(allMonitors);
      toast("Monitor deleted.", "success");
    } catch (err) {
      toast("Could not delete: " + err.message, "error");
    }
    return;
  }

  if (action === "pause" || action === "resume") {
    const card = document.getElementById(`card-${id}`);
    if (card) {
      const actionsEl = card.querySelector(".monitor-card-actions");
      if (actionsEl) {
        actionsEl.innerHTML = `
          <span style="font-size:0.8rem;color:var(--muted);display:flex;align-items:center;gap:6px;">
            <span class="spinner" style="width:13px;height:13px;border-width:1.5px;border-color:rgba(0,0,0,0.15);border-top-color:var(--accent);"></span>
            ${action === "pause" ? "Pausing…" : "Resuming…"}
          </span>`;
      }
    }

    const idx      = allMonitors.findIndex((m) => m.id === id);
    const snapshot = idx !== -1 ? { ...allMonitors[idx] } : null;

    try {
      const updated = action === "pause"
        ? await api.pauseMonitor(TOKEN, id)
        : await api.resumeMonitor(TOKEN, id);

      if (idx !== -1) allMonitors[idx] = updated;
      renderCards(allMonitors);
      renderStats(allMonitors);
      toast(action === "pause" ? "Monitor paused." : "Monitor resumed.", "success");
    } catch (err) {
      if (snapshot && idx !== -1) allMonitors[idx] = snapshot;
      renderCards(allMonitors);
      toast("Action failed: " + err.message, "error");
    }
  }
}

// ── Modal ──────────────────────────────────────────────────────
let editingMonitorId = null;
let currentAuthTab   = "none";
let assertionCount   = 0;

function setupModal() {
  const overlay   = document.getElementById("add-modal");
  const openBtn   = document.getElementById("add-monitor-btn");
  const closeBtn  = document.getElementById("modal-close");
  const cancelBtn = document.getElementById("modal-cancel");
  const submitBtn = document.getElementById("modal-submit");

  openBtn.addEventListener("click", () => openModal());
  closeBtn.addEventListener("click", closeModal);
  cancelBtn.addEventListener("click", closeModal);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
  submitBtn.addEventListener("click", handleAddMonitor);
}

// ── Auth tab switching ─────────────────────────────────────────
function setAuthTab(type) {
  currentAuthTab = type;
  document.querySelectorAll(".auth-tab").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.authType === type);
  });
  document.getElementById("auth-bearer").style.display = type === "bearer"  ? "block" : "none";
  document.getElementById("auth-apikey").style.display = type === "api_key" ? "block" : "none";
  document.getElementById("auth-basic").style.display  = type === "basic"   ? "block" : "none";
}

// ── Method change — show/hide body section ─────────────────────
function onMethodChange() {
  const method = document.getElementById("m-method").value;
  const bodySection = document.getElementById("body-section");
  bodySection.style.display = ["POST", "PUT", "PATCH"].includes(method) ? "block" : "none";
}

// ── Assertions builder ─────────────────────────────────────────
function addAssertion(prefill = null) {
  assertionCount++;
  const id  = assertionCount;
  const list = document.getElementById("assertions-list");
  const hint = document.getElementById("assertions-hint");
  hint.style.display = "none";

  const type     = prefill?.type     || "json_field";
  const path     = prefill?.path     || "";
  const operator = prefill?.operator || "eq";
  const value    = prefill?.value    != null ? prefill.value : "";

  const row = document.createElement("div");
  row.className = "assertion-row";
  row.id = `assertion-${id}`;
  row.innerHTML = `
    <select class="form-select assert-type-sel" data-id="${id}" onchange="onAssertTypeChange(${id})" style="flex:0 0 150px;">
      <option value="json_field"       ${type==="json_field"?"selected":""}>JSON Field</option>
      <option value="response_time_ms" ${type==="response_time_ms"?"selected":""}>Response Time</option>
      <option value="status_code"      ${type==="status_code"?"selected":""}>Status Code</option>
      <option value="header"           ${type==="header"?"selected":""}>Header</option>
    </select>
    <input class="form-input assert-path" data-id="${id}" type="text" placeholder="path / header name"
      style="flex:1;" value="${escapeHTML(path)}" />
    <select class="form-select assert-op-sel" data-id="${id}" style="flex:0 0 110px;">
      <option value="eq"       ${operator==="eq"?"selected":""}>= equals</option>
      <option value="neq"      ${operator==="neq"?"selected":""}>≠ not eq</option>
      <option value="contains" ${operator==="contains"?"selected":""}>contains</option>
      <option value="exists"   ${operator==="exists"?"selected":""}>exists</option>
      <option value="lt"       ${operator==="lt"?"selected":""}>less than</option>
      <option value="gt"       ${operator==="gt"?"selected":""}>greater than</option>
    </select>
    <input class="form-input assert-val" data-id="${id}" type="text" placeholder="expected value"
      style="flex:1;" value="${escapeHTML(String(value))}" />
    <button class="btn btn-sm btn-danger" type="button" onclick="removeAssertion(${id})" title="Remove">✕</button>`;

  list.appendChild(row);
  onAssertTypeChange(id);
}

function onAssertTypeChange(id) {
  const type    = document.querySelector(`.assert-type-sel[data-id="${id}"]`).value;
  const pathEl  = document.querySelector(`.assert-path[data-id="${id}"]`);
  const valEl   = document.querySelector(`.assert-val[data-id="${id}"]`);
  const opEl    = document.querySelector(`.assert-op-sel[data-id="${id}"]`);

  if (type === "response_time_ms" || type === "status_code") {
    pathEl.style.display = "none";
    // Restrict to numeric operators
    opEl.querySelectorAll("option").forEach(o => {
      o.disabled = !["eq","neq","lt","gt"].includes(o.value);
    });
    valEl.placeholder = type === "response_time_ms" ? "ms e.g. 2000" : "e.g. 200";
  } else if (type === "header") {
    pathEl.style.display = "block";
    pathEl.placeholder = "header name e.g. content-type";
    opEl.querySelectorAll("option").forEach(o => {
      o.disabled = !["eq","contains","exists"].includes(o.value);
    });
    valEl.placeholder = "expected value";
  } else {
    // json_field
    pathEl.style.display = "block";
    pathEl.placeholder = "dot-path e.g. data.status";
    opEl.querySelectorAll("option").forEach(o => { o.disabled = false; });
    valEl.placeholder = "expected value";
  }
}

function removeAssertion(id) {
  document.getElementById(`assertion-${id}`)?.remove();
  // Show hint again if empty
  if (!document.querySelector(".assertion-row")) {
    document.getElementById("assertions-hint").style.display = "block";
  }
}

function collectAssertions() {
  const rows = document.querySelectorAll(".assertion-row");
  const result = [];
  rows.forEach(row => {
    const id       = row.id.replace("assertion-", "");
    const type     = document.querySelector(`.assert-type-sel[data-id="${id}"]`).value;
    const path     = document.querySelector(`.assert-path[data-id="${id}"]`).value.trim();
    const operator = document.querySelector(`.assert-op-sel[data-id="${id}"]`).value;
    const rawVal   = document.querySelector(`.assert-val[data-id="${id}"]`).value.trim();

    // Coerce value: if numeric and operator is gt/lt/eq/neq, parse as number
    let value = rawVal;
    if (rawVal !== "" && operator !== "exists") {
      const num = Number(rawVal);
      if (!isNaN(num) && rawVal !== "") value = num;
    }

    const rule = { type, operator };
    if (path && type !== "response_time_ms" && type !== "status_code") rule.path = path;
    if (operator !== "exists" && rawVal !== "") rule.value = value;
    result.push(rule);
  });
  return result.length ? result : null;
}

// ── Build auth payload from current tab ───────────────────────
function collectAuth() {
  const t = currentAuthTab;
  if (t === "none") return null;

  if (t === "bearer") {
    const token = document.getElementById("auth-token").value.trim();
    return token ? { type: "bearer", token } : null;
  }
  if (t === "api_key") {
    const key_name  = document.getElementById("auth-key-name").value.trim();
    const key_value = document.getElementById("auth-key-value").value.trim();
    return (key_name && key_value) ? { type: "api_key", key_name, key_value } : null;
  }
  if (t === "basic") {
    const username = document.getElementById("auth-username").value.trim();
    const password = document.getElementById("auth-password").value.trim();
    // Allow empty password if they just want username, but username is required
    return (username) ? { type: "basic", username, password } : null;
  }
  return null;
}

function resetModal() {
  editingMonitorId = null;
  assertionCount   = 0;
  currentAuthTab   = "none";

  ["m-name","m-url"].forEach(id => document.getElementById(id).value = "");
  document.getElementById("m-method").value   = "GET";
  document.getElementById("m-interval").value = "5";
  document.getElementById("m-timeout").value  = "10";
  document.getElementById("m-status").value   = "200";

  // Auth
  setAuthTab("none");
  ["auth-token","auth-key-name","auth-key-value","auth-username","auth-password"].forEach(id => {
    document.getElementById(id).value = "";
  });

  // Body
  document.getElementById("m-body").value = "";
  document.getElementById("body-section").style.display = "none";

  // Assertions
  document.getElementById("assertions-list").innerHTML = "";
  document.getElementById("assertions-hint").style.display = "block";
}

function openModal(monitor = null) {
  document.getElementById("add-modal").classList.add("open");
  document.getElementById("modal-error").classList.remove("show");
  resetModal();

  if (monitor) {
    editingMonitorId = monitor.id;
    document.getElementById("modal-title").textContent  = "Edit Monitor";
    document.getElementById("modal-submit").textContent = "Save Changes";

    document.getElementById("m-name").value     = monitor.name;
    document.getElementById("m-url").value      = monitor.url;
    document.getElementById("m-method").value   = monitor.method;
    document.getElementById("m-interval").value = monitor.interval_minutes;
    document.getElementById("m-timeout").value  = monitor.timeout_seconds;
    document.getElementById("m-status").value   = monitor.expected_status;

    // Show body section if method needs it
    if (["POST","PUT","PATCH"].includes(monitor.method)) {
      document.getElementById("body-section").style.display = "block";
      if (monitor.body) {
        document.getElementById("m-body").value = JSON.stringify(monitor.body, null, 2);
      }
    }

    // Auth — we can't show the token (encrypted), just show a hint
    if (monitor.has_auth) {
      setAuthTab(monitor.auth_type || "bearer");
      
      // Clean up any existing hints first to avoid duplicates across multiple edits
      document.querySelectorAll(".auth-hint-msg").forEach(e => e.remove());

      const hint = document.createElement("p");
      hint.className = "form-hint auth-hint-msg";
      hint.style.color = "var(--up)";
      hint.textContent = "🔐 Auth is configured. Fill in new values to replace, or leave blank to keep existing.";
      
      // Append to the currently active auth field container
      const activeContainer = document.getElementById(`auth-${monitor.auth_type === 'api_key' ? 'apikey' : (monitor.auth_type || 'bearer')}`);
      if (activeContainer) {
          activeContainer.appendChild(hint);
      }
    }

    // Assertions
    if (monitor.assertions && monitor.assertions.length > 0) {
      document.getElementById("assertions-hint").style.display = "none";
      monitor.assertions.forEach(rule => addAssertion(rule));
    } else if (monitor.has_assertions) {
      // Fallback if older data without the full array
      const hintEl = document.getElementById("assertions-hint");
      hintEl.textContent = "This monitor has assertion rules configured. Add new ones below to replace.";
      hintEl.style.display = "block";
    }

  } else {
    document.getElementById("modal-title").textContent  = "Add New Monitor";
    document.getElementById("modal-submit").textContent = "Add Monitor";
  }

  document.getElementById("m-name").focus();
}

function closeModal() {
  document.getElementById("add-modal").classList.remove("open");
}

async function handleAddMonitor() {
  const errEl     = document.getElementById("modal-error");
  const submitBtn = document.getElementById("modal-submit");
  errEl.classList.remove("show");

  const name     = document.getElementById("m-name").value.trim();
  const url      = document.getElementById("m-url").value.trim();
  const method   = document.getElementById("m-method").value;
  const interval = parseInt(document.getElementById("m-interval").value, 10);
  const timeout  = parseInt(document.getElementById("m-timeout").value, 10);
  const expected = parseInt(document.getElementById("m-status").value, 10);

  if (!name || !url) {
    errEl.textContent = "Name and URL are required.";
    errEl.classList.add("show");
    return;
  }
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    errEl.textContent = "URL must start with http:// or https://";
    errEl.classList.add("show");
    return;
  }

  // Collect auth
  const auth = collectAuth();

  // Collect body
  let body = null;
  let hasExplicitBody = false;
  if (["POST","PUT","PATCH"].includes(method)) {
    const rawBody = document.getElementById("m-body").value.trim();
    if (rawBody) {
      try { 
        body = JSON.parse(rawBody); 
        hasExplicitBody = true;
      }
      catch {
        errEl.textContent = "Request Body must be valid JSON.";
        errEl.classList.add("show");
        return;
      }
    }
  }

  // Collect assertions
  const assertions = collectAssertions();

  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span class="spinner"></span> ${editingMonitorId ? "Saving…" : "Adding…"}`;

  try {
    const payload = {
      name, url, method,
      interval_minutes: interval,
      timeout_seconds:  timeout,
      expected_status:  expected,
    };

    // When editing: ALWAYS send auth so the backend knows whether to clear it.
    //   - null  → user chose "None" tab → backend wipes existing auth
    //   - {...} → user entered new credentials → backend replaces auth
    // When creating: only include auth if the user provided it (omitting = no auth).
    if (editingMonitorId) {
      payload.auth = auth;   // may be null — that's intentional (clear auth)
      payload.body = hasExplicitBody ? body : null; // explicitly clear body if empty or wrong method
    } else {
      if (auth) payload.auth = auth;
      if (hasExplicitBody) payload.body = body;
    }

    if (assertions) payload.assertions = assertions;

    if (editingMonitorId) {
      const updated = await api.updateMonitor(TOKEN, editingMonitorId, payload);
      const idx = allMonitors.findIndex(m => m.id === editingMonitorId);
      if (idx !== -1) allMonitors[idx] = updated;
      toast("Monitor updated successfully.", "success");
    } else {
      const monitor = await api.createMonitor(TOKEN, payload);
      allMonitors.unshift(monitor);
      toast("Monitor added! First check will run shortly.", "success");
    }

    renderCards(allMonitors);
    renderStats(allMonitors);
    closeModal();
  } catch (err) {
    errEl.textContent = err.message || (editingMonitorId ? "Failed to update monitor." : "Failed to add monitor.");
    errEl.classList.add("show");
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = editingMonitorId ? "Save Changes" : "Add Monitor";
  }
}

// ── Logout ─────────────────────────────────────────────────────
function setupLogout() {
  document.getElementById("logout-btn").addEventListener("click", () => {
    clearToken();
    window.location.href = "index.html";
  });
}

// ── Utilities ──────────────────────────────────────────────────
function escapeHTML(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

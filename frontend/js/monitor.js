/* ============================================================
   monitor.js — Detail page: stats, chart, 90-day bar,
                alert channels, check log table
   ============================================================ */

let TOKEN     = null;
let MONITOR_ID = null;
let monitor   = null;
let chartInst = null;

document.addEventListener("DOMContentLoaded", async () => {
  TOKEN = requireAuth();
  if (!TOKEN) return;

  // Verify the token is still valid once on page load.
  await verifySession(TOKEN);

  const params = new URLSearchParams(window.location.search);
  MONITOR_ID = params.get("id");
  if (!MONITOR_ID) {
    alert("No monitor ID in URL.");
    window.location.href = "dashboard.html";
    return;
  }

  // Run all four loads in parallel; use allSettled so a failing secondary
  // request (stats/logs/alerts) doesn't abort the whole page.
  await Promise.allSettled([
    loadMonitorDetail(),
    loadStats(),
    loadLogs(),
    loadAlertChannels(),
  ]);

  setupHeaderActions();
  setupAlertForm();
  setupLogout();
});

// ── Load Monitor ──────────────────────────────────────────────
async function loadMonitorDetail() {
  try {
    monitor = await api.getMonitor(TOKEN, MONITOR_ID);
    renderHeader(monitor);
  } catch (err) {
    // Only show a toast for genuine 404s; suppress transient network errors
    // on first load (they appear as a flashing snackbar and then disappear).
    const msg = err.message || "";
    if (msg.includes("404") || msg.toLowerCase().includes("not found")) {
      toast("Monitor not found. It may have been deleted.", "error");
      setTimeout(() => { window.location.href = "dashboard.html"; }, 2000);
    }
    // For all other errors, fail silently — the page will show dashes.
  }
}

function renderHeader(m) {
  document.title = `${m.name} — Keep an Eye`;

  document.getElementById("monitor-name").textContent  = m.name;
  document.getElementById("monitor-url").textContent   = m.url;
  document.getElementById("stat-interval").textContent = m.interval_minutes;

  const badge = document.getElementById("status-badge");
  badge.textContent  = (m.status || "pending").toUpperCase();
  badge.className    = `status-badge ${m.status || "pending"}`;

  const pauseBtn = document.getElementById("pause-btn");
  pauseBtn.textContent = m.is_active ? "⏸ Pause" : "▶ Resume";
  pauseBtn.dataset.active = m.is_active ? "1" : "0";
}

// ── Stats ─────────────────────────────────────────────────────
async function loadStats() {
  try {
    const s = await api.getStats(TOKEN, MONITOR_ID);
    document.getElementById("stat-uptime").textContent = s.uptime_percent + "%";
    document.getElementById("stat-resp").textContent   = s.avg_response_ms + " ms";
    document.getElementById("stat-checks").textContent = s.total_checks + " total checks";
  } catch {
    // Silently show dashes if no data yet
  }
}

// ── Logs ──────────────────────────────────────────────────────
async function loadLogs() {
  try {
    const logs = await api.getLogs(TOKEN, MONITOR_ID, 50);
    renderLogTable(logs);
    render90DayBar(logs);
    renderChart(logs);
  } catch (err) {
    console.error("Logs error:", err);
  }
}

function renderLogTable(logs) {
  const tbody = document.getElementById("log-tbody");
  if (!logs.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-muted" style="text-align:center;padding:32px;">No checks recorded yet.</td></tr>`;
    return;
  }
  tbody.innerHTML = logs.map((l) => {
    const resultIcon = l.is_up
      ? `<span style="color:var(--up);font-weight:600;">✅ Up</span>`
      : `<span style="color:var(--down);font-weight:600;">❌ Down</span>`;

    // Assertions column — show compact chips
    let assertCell = `<span style="color:var(--muted-light);font-size:0.78rem;">—</span>`;
    if (l.assertion_results && l.assertion_results.length) {
      const pass = l.assertion_results.filter(a => a.passed).length;
      const total = l.assertion_results.length;
      const allPass = pass === total;
      const chips = l.assertion_results.map(a => {
        const color = a.passed ? "var(--up)" : "var(--down)";
        const icon  = a.passed ? "✓" : "✗";
        const tip   = a.detail ? escapeHTML(a.detail) : (a.passed ? "Passed" : "Failed");
        const ruleType = (a.rule && a.rule.type) ? a.rule.type.replace(/_/g, " ") : "rule";
        return `<span class="assert-chip" style="border-color:${color};color:${color};" title="${tip}">${icon} ${ruleType}</span>`;
      }).join("");
      assertCell = `<div class="assert-chips">${chips}</div>`;
    }

    return `
    <tr>
      <td>${timeAgo(l.checked_at)}</td>
      <td><code style="font-size:0.82rem;">${l.status_code ?? "—"}</code></td>
      <td>${l.response_time_ms != null ? l.response_time_ms + " ms" : "—"}</td>
      <td>${resultIcon}</td>
      <td>${assertCell}</td>
      <td style="color:var(--muted);font-size:0.8rem;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHTML(l.error_message || "")}">
        ${l.error_message ? escapeHTML(l.error_message) : "—"}
      </td>
    </tr>`;
  }).join("");
}

// ── 90-day bar ────────────────────────────────────────────────
function render90DayBar(logs) {
  const bar = document.getElementById("uptime-bar");
  const now = new Date();

  // Build a map: "YYYY-MM-DD" -> { up: n, total: n }
  const dayMap = {};
  for (let i = 89; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    dayMap[key] = { up: 0, total: 0 };
  }

  logs.forEach((l) => {
    const key = (l.checked_at || "").slice(0, 10);
    if (dayMap[key]) {
      dayMap[key].total++;
      if (l.is_up) dayMap[key].up++;
    }
  });

  const days = Object.entries(dayMap);
  let totalUp = 0, totalAll = 0;

  bar.innerHTML = days.map(([date, d]) => {
    totalUp  += d.up;
    totalAll += d.total;
    let cls = "day-no-data";
    if (d.total > 0) cls = d.up === d.total ? "day-up" : "day-down";
    const pct = d.total ? Math.round((d.up / d.total) * 100) : null;
    const tip = pct !== null ? `${date}: ${pct}% up (${d.total} checks)` : `${date}: no data`;
    return `<div class="day-pill ${cls}" data-tip="${tip}" title="${tip}"></div>`;
  }).join("");

  // Overall uptime label
  if (totalAll > 0) {
    const overall = ((totalUp / totalAll) * 100).toFixed(2);
    document.getElementById("uptime-percent-label").textContent = `${overall}% uptime`;
  }
}

// ── Chart.js ──────────────────────────────────────────────────
function renderChart(logs) {
  const ctx = document.getElementById("response-chart").getContext("2d");
  // Chronological order for chart
  const ordered = [...logs].reverse();

  const labels = ordered.map((l) => timeAgo(l.checked_at));
  const data   = ordered.map((l) => l.response_time_ms ?? null);
  const colors = ordered.map((l) =>
    l.is_up ? "rgba(16,185,129,0.85)" : "rgba(239,68,68,0.85)"
  );

  if (chartInst) chartInst.destroy();

  chartInst = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Response Time (ms)",
        data,
        fill: true,
        backgroundColor: "rgba(59,130,246,0.06)",
        borderColor: "#3B82F6",
        borderWidth: 2,
        pointBackgroundColor: colors,
        pointRadius: 4,
        pointHoverRadius: 6,
        tension: 0.35,
        spanGaps: true,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.parsed.y ?? "—"} ms`,
          },
        },
      },
      scales: {
        x: {
          ticks: {
            maxTicksLimit: 10,
            color: "#64748B",
            font: { size: 11, family: "Inter, sans-serif" },
          },
          grid: { color: "#F1F5F9" },
        },
        y: {
          beginAtZero: true,
          ticks: {
            color: "#64748B",
            font: { size: 11, family: "Inter, sans-serif" },
            callback: (v) => v + " ms",
          },
          grid: { color: "#F1F5F9" },
        },
      },
    },
  });
}

// ── Header Actions (Pause / Delete / Trigger) ────────────────
function setupHeaderActions() {
  document.getElementById("pause-btn").addEventListener("click", async () => {
    const pauseBtn = document.getElementById("pause-btn");
    const isActive = pauseBtn.dataset.active === "1";
    try {
      const updated = isActive
        ? await api.pauseMonitor(TOKEN, MONITOR_ID)
        : await api.resumeMonitor(TOKEN, MONITOR_ID);
      monitor = updated;
      renderHeader(updated);
      toast(isActive ? "Monitor paused." : "Monitor resumed.", "success");
    } catch (err) {
      toast("Action failed: " + err.message, "error");
    }
  });

  document.getElementById("delete-btn").addEventListener("click", async () => {
    if (!confirm("Delete this monitor? This cannot be undone.")) return;
    try {
      await api.deleteMonitor(TOKEN, MONITOR_ID);
      toast("Monitor deleted.", "success");
      setTimeout(() => { window.location.href = "dashboard.html"; }, 800);
    } catch (err) {
      toast("Delete failed: " + err.message, "error");
    }
  });

  // ── Test Now (trigger) button ──
  const triggerBtn = document.getElementById("trigger-btn");
  triggerBtn.addEventListener("click", async () => {
    triggerBtn.disabled = true;
    triggerBtn.innerHTML = `<span class="spinner" style="width:13px;height:13px;border-color:rgba(0,0,0,0.15);border-top-color:var(--accent);"></span> Testing…`;
    try {
      const result = await api.triggerCheck(TOKEN, MONITOR_ID);
      // Reload stats and logs to reflect the new check
      await Promise.allSettled([loadStats(), loadLogs(), loadMonitorDetail()]);
      const status = result.is_up ? "✅ Up" : "❌ Down";
      const ms     = result.response_time_ms != null ? ` · ${result.response_time_ms} ms` : "";
      toast(`Test complete: ${status}${ms}`, result.is_up ? "success" : "error");
    } catch (err) {
      toast("Test failed: " + err.message, "error");
    } finally {
      triggerBtn.disabled = false;
      triggerBtn.innerHTML = "⚡ Test Now";
    }
  });
}

// ── Alert Channels ────────────────────────────────────────────
async function loadAlertChannels() {
  try {
    const channels = await api.getAlertChannels(TOKEN, MONITOR_ID);
    renderAlertChannels(channels);
  } catch {
    // No channels or error — show empty state
  }
}

function renderAlertChannels(channels) {
  const list  = document.getElementById("alert-channels-list");
  const noMsg = document.getElementById("no-channels-msg");

  if (!channels || !channels.length) {
    if (noMsg) noMsg.style.display = "block";
    if (list) list.innerHTML = "";
    return;
  }
  if (noMsg) noMsg.style.display = "none";

  const icons = { slack: "💬", discord: "🎮", email: "📧" };

  list.innerHTML = channels.map((ch) => {
    const icon = icons[ch.channel_type] || "🔔";
    const detail = ch.config.webhook_url
      ? truncate(ch.config.webhook_url, 50)
      : (ch.config.to || "");
    return `
    <div class="alert-channel-item" id="ch-${ch.id}">
      <div style="display:flex;align-items:center;gap:10px;">
        <span class="channel-type-badge">${icon} ${ch.channel_type}</span>
        <span class="text-sm text-muted" title="${escapeHTML(detail)}">${escapeHTML(detail)}</span>
      </div>
      <button class="btn btn-danger btn-sm" onclick="deleteChannel('${ch.id}')">Remove</button>
    </div>`;
  }).join("");
}

async function deleteChannel(channelId) {
  if (!confirm("Remove this alert channel?")) return;
  try {
    await api.deleteAlertChannel(TOKEN, MONITOR_ID, channelId);
    document.getElementById(`ch-${channelId}`)?.remove();
    toast("Alert channel removed.", "success");
    // Show empty msg if none left
    const list = document.getElementById("alert-channels-list");
    if (!list.querySelector(".alert-channel-item")) {
      document.getElementById("no-channels-msg").style.display = "block";
    }
  } catch (err) {
    toast("Remove failed: " + err.message, "error");
  }
}

function setupAlertForm() {
  const addBtn    = document.getElementById("add-alert-btn");
  const formWrap  = document.getElementById("alert-form-wrap");
  const cancelBtn = document.getElementById("alert-cancel-btn");
  const saveBtn   = document.getElementById("alert-save-btn");

  addBtn.addEventListener("click", () => {
    formWrap.style.display = "block";
    addBtn.style.display   = "none";
  });

  cancelBtn.addEventListener("click", () => {
    formWrap.style.display = "none";
    addBtn.style.display   = "inline-flex";
    document.getElementById("alert-error").classList.remove("show");
  });

  saveBtn.addEventListener("click", handleAddChannel);
}

function toggleAlertFields() {
  const type = document.getElementById("alert-type").value;
  document.getElementById("alert-webhook-group").style.display = type === "email" ? "none" : "block";
  document.getElementById("alert-email-group").style.display   = type === "email" ? "block" : "none";
}

async function handleAddChannel() {
  const errEl   = document.getElementById("alert-error");
  const saveBtn = document.getElementById("alert-save-btn");
  errEl.classList.remove("show");

  const type = document.getElementById("alert-type").value;
  let config = {};

  if (type === "email") {
    const emailVal = document.getElementById("alert-email").value.trim();
    if (!emailVal) {
      errEl.textContent = "Email address is required.";
      errEl.classList.add("show");
      return;
    }
    config = { to: emailVal };
  } else {
    const webhookVal = document.getElementById("alert-webhook").value.trim();
    if (!webhookVal || !webhookVal.startsWith("http")) {
      errEl.textContent = "A valid webhook URL is required.";
      errEl.classList.add("show");
      return;
    }
    config = { webhook_url: webhookVal };
  }

  saveBtn.disabled = true;
  saveBtn.innerHTML = `<span class="spinner" style="width:14px;height:14px;border-color:rgba(0,0,0,0.2);border-top-color:#333;"></span>`;

  try {
    await api.createAlertChannel(TOKEN, MONITOR_ID, { channel_type: type, config });
    toast("Alert channel added!", "success");
    await loadAlertChannels();
    // Reset form
    document.getElementById("alert-form-wrap").style.display = "none";
    document.getElementById("add-alert-btn").style.display   = "inline-flex";
    document.getElementById("alert-webhook").value = "";
    document.getElementById("alert-email").value   = "";
  } catch (err) {
    errEl.textContent = err.message || "Failed to add channel.";
    errEl.classList.add("show");
  } finally {
    saveBtn.disabled = false;
    saveBtn.innerHTML = "Save";
  }
}

// ── Logout ─────────────────────────────────────────────────────
function setupLogout() {
  document.getElementById("logout-btn").addEventListener("click", () => {
    clearToken();
    window.location.href = "index.html";
  });
  // Load user email
  api.me(TOKEN).then((u) => {
    document.getElementById("user-email").textContent = u.email;
  }).catch(() => {});
}

// ── Utilities ──────────────────────────────────────────────────
function escapeHTML(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
function truncate(str, n) {
  return str.length > n ? str.slice(0, n) + "…" : str;
}

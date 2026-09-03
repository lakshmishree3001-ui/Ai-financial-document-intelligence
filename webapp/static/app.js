// ====================================================================
// Ledger — Complete Dashboard Application
// End-to-end: every newly uploaded document is processed by the backend
// pipeline and all UI components read from the database via doc_id-based
// API routes (/api/documents/{doc_id}/*).
// ====================================================================

"use strict";

// -------------------------------------------------------------------
// Chart.js global defaults (dark theme)
// -------------------------------------------------------------------
Chart.defaults.color = "#8B95A8";
Chart.defaults.borderColor = "rgba(255,255,255,0.07)";
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 12;

// -------------------------------------------------------------------
// Chart registry & destruction — safe reuse preventing canvas conflicts
// -------------------------------------------------------------------
const chartRegistry = {};

function destroyChart(id) {
  if (chartRegistry[id]) {
    try { chartRegistry[id].destroy(); } catch (e) {}
    delete chartRegistry[id];
  }
  const canvas = document.getElementById(id);
  if (canvas) {
    try {
      const existing = Chart.getChart(canvas);
      if (existing) existing.destroy();
    } catch (e) {}
  }
}

function buildChart(id, config) {
  destroyChart(id);
  const canvas = document.getElementById(id);
  if (!canvas) return null;
  const ctx = canvas.getContext("2d");
  const chart = new Chart(ctx, config);
  chartRegistry[id] = chart;
  return chart;
}

function registerChart(id, instance) {
  chartRegistry[id] = instance;
  return instance;
}

function renderChartOrEmpty(canvasId, hasData, emptyMsg, config) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;
  const wrap = canvas.parentElement;

  let emptyState = wrap.querySelector(".chart-empty-state");

  if (!hasData) {
    destroyChart(canvasId);
    canvas.style.display = "none";
    if (!emptyState) {
      emptyState = document.createElement("div");
      emptyState.className = "chart-empty-state empty-state";
      emptyState.style.padding = "40px";
      wrap.appendChild(emptyState);
    }
    emptyState.style.display = "block";
    emptyState.innerHTML = `<p class="empty-sub">${esc(emptyMsg)}</p>`;
    return null;
  }

  if (emptyState) {
    emptyState.style.display = "none";
  }
  canvas.style.display = "block";
  return buildChart(canvasId, config);
}

// -------------------------------------------------------------------
// Global state — currently selected document ID (DOC-XXXXXXXX)
// -------------------------------------------------------------------
let activeDocId = null;

// -------------------------------------------------------------------
// Utility helpers
// -------------------------------------------------------------------
function esc(str) {
  const d = document.createElement("div");
  d.textContent = String(str ?? "");
  return d.innerHTML;
}

function fmt(num) {
  if (num === null || num === undefined || isNaN(num)) return "—";
  const abs = Math.abs(num);
  if (abs >= 1e9)  return (num / 1e9).toFixed(2) + " Bn";
  if (abs >= 1e7)  return (num / 1e7).toFixed(1) + " Cr";
  if (abs >= 1e5)  return (num / 1e5).toFixed(1) + " L";
  return num.toLocaleString("en-IN");
}

function fmtPct(n) {
  if (n === null || n === undefined) return "—";
  return (n > 0 ? "+" : "") + Number(n).toFixed(1) + "%";
}

function showToast(msg, type = "success") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  const icon = type === "success" ? "✅" : "❌";
  toast.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-msg">${esc(msg)}</span>`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = "0"; toast.style.transform = "translateY(12px)"; toast.style.transition = "all 0.3s ease"; }, 3500);
  setTimeout(() => toast.remove(), 3800);
}

// -------------------------------------------------------------------
// Sidebar navigation
// -------------------------------------------------------------------
const navItems = document.querySelectorAll(".nav-item[data-section]");

navItems.forEach(btn => {
  btn.addEventListener("click", () => {
    navItems.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    const target = document.getElementById(btn.dataset.section);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    document.getElementById("topbarTitle").textContent = btn.textContent.trim();
  });
});

// Sidebar upload button → open file picker
document.getElementById("sidebarUploadBtn").addEventListener("click", () => {
  document.getElementById("fileInput").click();
});

// -------------------------------------------------------------------
// Document selector change — load by doc_id
// -------------------------------------------------------------------
const docSelector = document.getElementById("docSelector");

docSelector.addEventListener("change", () => {
  const selected = docSelector.value;
  if (selected) {
    activeDocId = selected;
    loadDocumentDetails(selected);
  }
});

// -------------------------------------------------------------------
// Upload flow — all 8 stage pills
// -------------------------------------------------------------------
const uploadZone     = document.getElementById("uploadZone");
const fileInput      = document.getElementById("fileInput");
const uploadProgress = document.getElementById("uploadProgress");
const progressFill   = document.getElementById("progressFill");

// BUG FIX #6: include all 8 stage pills (HTML has stage0 … stage7)
const stageEls = [
  document.getElementById("stage0"),  // Uploading
  document.getElementById("stage1"),  // Extracting
  document.getElementById("stage2"),  // Classifying
  document.getElementById("stage3"),  // Metrics
  document.getElementById("stage4"),  // Ratios
  document.getElementById("stage5"),  // Summary
  document.getElementById("stage6"),  // RAG Index
  document.getElementById("stage7"),  // Insights
].filter(Boolean);

const stageStatusText = document.getElementById("stageStatusText");

const STAGE_LABELS = [
  "Uploading file…",
  "Extracting text…",
  "Classifying document…",
  "Extracting financial metrics…",
  "Computing ratios…",
  "Generating summary…",
  "Building RAG index…",
  "Generating insights…",
];

uploadZone.addEventListener("click", (e) => {
  if (e.target === fileInput) return;
  fileInput.click();
});

["dragenter", "dragover"].forEach(evt =>
  uploadZone.addEventListener(evt, e => { e.preventDefault(); uploadZone.classList.add("drag-over"); })
);
["dragleave", "drop"].forEach(evt =>
  uploadZone.addEventListener(evt, e => { e.preventDefault(); uploadZone.classList.remove("drag-over"); })
);
uploadZone.addEventListener("drop", e => {
  const file = e.dataTransfer.files[0];
  if (file) handleUpload(file);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) handleUpload(fileInput.files[0]);
});

function setStage(idx) {
  stageEls.forEach((s, i) => {
    s.className = "stage-pill" + (i < idx ? " done" : i === idx ? " active" : "");
  });
  progressFill.style.width = `${Math.round((idx / (stageEls.length - 1)) * 100)}%`;
  if (stageStatusText && STAGE_LABELS[idx]) {
    stageStatusText.textContent = STAGE_LABELS[idx];
  }
}

async function handleUpload(file) {
  const ext = file.name.toLowerCase().split(".").pop();
  const allowedExts = ["pdf", "csv", "jpg", "jpeg", "png", "webp", "tiff", "tif"];
  if (!allowedExts.includes(ext)) {
    showToast("Unsupported file type. Upload PDF, CSV, JPG, PNG, WEBP, or TIFF.", "error");
    return;
  }

  uploadProgress.classList.add("visible");
  setStage(0);

  // Animate stages 0–6 with timed delays while backend processes
  const stageTiming = [0, 500, 1200, 2000, 2800, 3600, 4400];
  stageTiming.forEach((delay, i) => {
    setTimeout(() => setStage(i), delay);
  });

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });

    // BUG FIX #7 & #1: use document_id from the response, not filename
    const data = await res.json();

    if (!res.ok) {
      showToast(data.detail || "Upload failed.", "error");
      uploadProgress.classList.remove("visible");
      return;
    }

    // Show final stage
    setStage(stageEls.length - 1);
    progressFill.style.width = "100%";
    if (stageStatusText) stageStatusText.textContent = "✓ Processing complete!";

    setTimeout(async () => {
      uploadProgress.classList.remove("visible");
      progressFill.style.width = "0%";
      stageEls.forEach(s => { s.className = "stage-pill"; });
      if (stageStatusText) stageStatusText.textContent = "";
      fileInput.value = "";

      const docId = data.document_id;
      const status = data.status || "completed";

      if (status === "failed") {
        showToast(`Processing failed: ${data.error || "Unknown error."}`, "error");
      } else {
        showToast(`✓ ${file.name} processed as ${docId}`, "success");
      }

      // BUG FIX #2 & #7: reload list keyed by doc_id, then auto-select the new doc
      await loadDocumentList();
      activeDocId = docId;
      docSelector.value = docId;
      await loadDocumentDetails(docId);

    }, 800);

  } catch (err) {
    uploadProgress.classList.remove("visible");
    showToast("Could not reach the server. Is the backend running?", "error");
    console.error("Upload error:", err);
  }
}

// -------------------------------------------------------------------
// Load document list from /api/documents/processed (DB-backed)
// -------------------------------------------------------------------
async function loadDocumentList() {
  try {
    const res = await fetch("/api/documents/processed");
    if (!res.ok) return;
    const docs = await res.json();

    // Update sidebar selector
    const currentVal = docSelector.value;
    docSelector.innerHTML = '<option value="">— Select a document —</option>';
    docs.forEach(d => {
      const opt = document.createElement("option");
      opt.value = d.document_id;
      opt.textContent = d.filename + (d.status !== "completed" ? ` [${d.status}]` : "");
      docSelector.appendChild(opt);
    });
    if (currentVal) docSelector.value = currentVal;

    // Update doc count badge
    document.getElementById("docCountBadge").textContent = docs.length;

    // Render doc list panel
    const container = document.getElementById("docListContainer");
    if (docs.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📂</div>
          <p class="empty-title">No documents yet</p>
          <p class="empty-sub">Upload a document to see it here</p>
        </div>`;
      return;
    }

    // Determine file icon by extension
    function getFileIcon(filename) {
      const e = (filename || "").split(".").pop().toLowerCase();
      if (e === "pdf") return { icon: "📄", cls: "pdf" };
      if (e === "csv") return { icon: "📊", cls: "csv" };
      if (["jpg","jpeg","png","webp","tiff","tif"].includes(e)) return { icon: "🖼️", cls: "img" };
      return { icon: "📁", cls: "pdf" };
    }

    container.innerHTML = '<div class="doc-list">' +
      docs.slice().reverse().slice(0, 10).map(d => {
        const { icon, cls } = getFileIcon(d.filename);
        const isSelected = activeDocId === d.document_id ? " selected" : "";
        const statusDot = d.status === "completed" ? "🟢" : d.status === "failed" ? "🔴" : "🟡";
        const cat = d.doc_category || d.document_type || "";
        return `
          <div class="doc-list-item${isSelected}" data-docid="${esc(d.document_id)}" id="dli-${esc(d.document_id)}">
            <div class="doc-file-icon ${cls}">${icon}</div>
            <div style="flex:1;min-width:0;">
              <p class="doc-item-name">${esc(d.filename)}</p>
              <p class="doc-item-meta">${esc(d.document_id)} · ${statusDot}</p>
              ${cat ? `<span class="doc-item-cat-badge">${esc(cat)}</span>` : ""}
            </div>
            <button class="doc-delete-btn" data-docid="${esc(d.document_id)}" title="Delete document" aria-label="Delete ${esc(d.filename)}">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg>
            </button>
          </div>`;
      }).join("") + '</div>';

    // Click to select
    container.querySelectorAll(".doc-list-item").forEach(el => {
      el.addEventListener("click", (e) => {
        // Don't select if clicking delete
        if (e.target.closest(".doc-delete-btn")) return;
        const did = el.dataset.docid;
        activeDocId = did;
        docSelector.value = did;
        loadDocumentDetails(did);
      });
    });

    // Delete buttons
    container.querySelectorAll(".doc-delete-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const did = btn.dataset.docid;
        await deleteDocument(did);
      });
    });

  } catch (e) {
    console.error("loadDocumentList error:", e);
  }
}

// -------------------------------------------------------------------
// Delete a document by doc_id
// -------------------------------------------------------------------
async function deleteDocument(docId) {
  if (!confirm(`Delete document ${docId}?\n\nThis will permanently remove the file, analysis data, and Q&A index.`)) return;

  try {
    const res = await fetch(`/api/documents/${encodeURIComponent(docId)}`, { method: "DELETE" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || "Delete failed.", "error");
      return;
    }
    showToast(`🗑️ Document ${docId} deleted.`, "success");

    // If the deleted doc was active, clear state
    if (activeDocId === docId) {
      activeDocId = null;
      docSelector.value = "";
    }

    await loadDocumentList();

    // If there are remaining docs, auto-select the first one
    if (docSelector.options.length > 1 && !activeDocId) {
      const nextId = docSelector.options[1].value;
      activeDocId = nextId;
      docSelector.value = nextId;
      await loadDocumentDetails(nextId);
    }
  } catch (err) {
    showToast("Could not reach the server.", "error");
    console.error("deleteDocument error:", err);
  }
}

// -------------------------------------------------------------------
// Load all data for a selected document (by doc_id)
// -------------------------------------------------------------------
async function loadDocumentDetails(docId) {
  if (!docId) return;
  activeDocId = docId;

  // Highlight in sidebar list
  document.querySelectorAll(".doc-list-item").forEach(el => {
    el.classList.toggle("selected", el.dataset.docid === docId);
  });

  // Run all fetches in parallel
  await Promise.allSettled([
    loadClassification(docId),
    loadSummary(docId),
    loadMetricsAndKPIs(docId),
    loadInsights(docId),
    loadAnomalies(docId),
  ]);
}

// -------------------------------------------------------------------
// SECTION 2: Classification — /api/documents/{doc_id}/classification
// Always renders a meaningful result, even with keyword fallback
// -------------------------------------------------------------------
async function loadClassification(docId) {
  const badgeCard = document.getElementById("classificationBadgeCard");
  const modelLabel = document.getElementById("classModelLabel");

  badgeCard.innerHTML = `<div class="empty-state"><p class="empty-sub">Classifying…</p></div>`;

  try {
    const res = await fetch(`/api/documents/${encodeURIComponent(docId)}/classification`);
    if (!res.ok) throw new Error("not found");
    const data = await res.json();

    const cat  = data.category || data.predicted_category || "Financial Document";
    const model = data.model_used || "—";
    const confRaw = data.confidence != null ? parseFloat(data.confidence) : null;
    const confPct = confRaw != null ? Math.round(confRaw * 100) : null;
    const isKeyword = model === "keyword_fallback";
    const modelDisplay = isKeyword ? "Keyword Analysis" : model;

    modelLabel.textContent = modelDisplay;

    const confColor = confPct == null ? "#8B95A8"
      : confPct >= 75 ? "#10B981"
      : confPct >= 55 ? "#F59E0B"
      : "#EF4444";

    badgeCard.innerHTML = `
      <div class="class-main-badge">${esc(cat)}</div>
      <p class="class-confidence" style="color:${confColor};">${confPct != null ? confPct + "%" : "—"}</p>
      <p class="class-confidence-label">confidence</p>
      <p class="class-model-label">Model: ${esc(modelDisplay)}${isKeyword ? " <span class=\'clf-fallback-tag\'>heuristic</span>" : ""}</p>`;

    // Chart — show even if confidence is moderate
    const confVal = confRaw ?? 0.6;
    const otherVal = Math.max(0, 1 - confVal);

    let chartLabels = [cat, "Other Categories"];
    let chartData = [confVal, otherVal];
    let chartColors = [confColor + "D9", "rgba(139,148,168,0.20)"];

    if (data.class_probabilities && Object.keys(data.class_probabilities).length > 1) {
      const sortedProbs = Object.entries(data.class_probabilities)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);
      chartLabels = sortedProbs.map(p => p[0]);
      chartData = sortedProbs.map(p => p[1]);
      chartColors = sortedProbs.map((p, i) => i === 0 ? confColor + "D9" : "rgba(139,148,168,0.25)");
    }

    try {
      buildChart("classChart", {
        type: "bar",
        data: {
          labels: chartLabels,
          datasets: [{
            data: chartData,
            backgroundColor: chartColors,
            borderRadius: 5,
            borderSkipped: false,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          indexAxis: "y",
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: c => ` ${(c.parsed.x * 100).toFixed(1)}%` } },
          },
          scales: {
            x: { max: 1, ticks: { callback: v => (v * 100).toFixed(0) + "%" }, grid: { color: "rgba(255,255,255,0.06)" } },
            y: { grid: { display: false } },
          },
        },
      });
    } catch (chartErr) {
      console.error("classChart rendering error:", chartErr);
    }
  } catch (e) {
    console.error("loadClassification error:", e);
    badgeCard.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🏷️</div>
        <p class="empty-title">Classification unavailable</p>
        <p class="empty-sub">Upload a document and wait for processing to complete</p>
      </div>`;
  }
}

// -------------------------------------------------------------------
// SECTION 7: AI Summary — /api/documents/{doc_id}/summary
// BUG FIX #3: correct route
// -------------------------------------------------------------------
async function loadSummary(docId) {
  const accordion = document.getElementById("summaryAccordion");
  const label = document.getElementById("summaryDocLabel");

  label.textContent = docId;
  accordion.innerHTML = `<div class="empty-state"><p class="empty-sub">Loading summary…</p></div>`;

  try {
    const res = await fetch(`/api/documents/${encodeURIComponent(docId)}/summary`);
    if (!res.ok) throw new Error("not found");
    const data = await res.json();

    // Update label with filename if present
    if (data.filename) label.textContent = data.filename;

    const sections = [
      { key: "executive_summary",            label: "📋 Executive Summary" },
      { key: "key_financial_highlights",     label: "💰 Key Financial Highlights" },
      { key: "risk_summary",                 label: "⚠️ Risk Summary" },
      { key: "business_performance_summary", label: "📈 Business Performance" },
      { key: "management_discussion_summary",label: "💼 Management Discussion" },
    ];

    const items = sections.map((sec, i) => {
      const bullets = (data[sec.key] || []).filter(s => s && s.trim());
      if (!bullets.length) return "";
      return `
        <div class="summary-item ${i === 0 ? "open" : ""}" data-idx="${i}">
          <button class="summary-trigger" aria-expanded="${i === 0}">
            <span>${esc(sec.label)}</span>
            <span class="summary-trigger-icon"></span>
          </button>
          <div class="summary-body">
            <ul>
              ${bullets.map(b => `<li>${esc(b)}</li>`).join("")}
            </ul>
          </div>
        </div>`;
    }).filter(Boolean);

    if (!items.length) {
      accordion.innerHTML = `
        <div class="empty-state card-pad">
          <div class="empty-icon">📝</div>
          <p class="empty-title">No summary sections found</p>
          <p class="empty-sub">The document may not contain enough text to summarize</p>
        </div>`;
      return;
    }

    accordion.innerHTML = items.join("");

    // Accordion toggle
    accordion.querySelectorAll(".summary-trigger").forEach(btn => {
      btn.addEventListener("click", () => {
        const item = btn.closest(".summary-item");
        const isOpen = item.classList.contains("open");
        accordion.querySelectorAll(".summary-item").forEach(i => i.classList.remove("open"));
        if (!isOpen) item.classList.add("open");
      });
    });

  } catch (e) {
    accordion.innerHTML = `
      <div class="empty-state card-pad">
        <div class="empty-icon">📝</div>
        <p class="empty-title">Summary not found</p>
        <p class="empty-sub">No summary available for document ${esc(docId)}</p>
      </div>`;
  }
}

// -------------------------------------------------------------------
// SECTION 3: Metrics table + KPI cards
// BUG FIX #3 & #5: /api/documents/{doc_id}/metrics, real data for KPIs
// -------------------------------------------------------------------
async function loadMetricsAndKPIs(docId) {
  const tbody  = document.getElementById("metricsTableBody");
  const badge  = document.getElementById("metricsCountBadge");
  const kpiGrid = document.getElementById("kpiGrid");

  tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state"><p class="empty-sub">Loading…</p></div></td></tr>`;

  try {
    const res = await fetch(`/api/documents/${encodeURIComponent(docId)}/metrics`);
    if (!res.ok) throw new Error("not found");
    const data = await res.json();

    // data = { document_id, filename, document_year, raw_values, ratios, financial_health, metrics: [...] }
    const raw     = data.raw_values || {};
    const ratios  = data.ratios || {};
    const metrics = data.metrics || [];

    badge.textContent = metrics.length || Object.keys(raw).length || 0;

    // ── Metrics table ───────────────────────────────────────────
    if (metrics.length) {
      tbody.innerHTML = metrics.map(r => `
        <tr>
          <td>${esc(r.metric)}</td>
          <td class="mono">${esc(r.value)}</td>
          <td>${esc(r.year ?? data.document_year ?? "—")}</td>
          <td style="font-size:11.5px;color:var(--text-muted);font-family:var(--font-mono);">${esc(docId)}</td>
        </tr>`).join("");
    } else if (Object.keys(raw).length) {
      tbody.innerHTML = Object.entries(raw).map(([metric, value]) => `
        <tr>
          <td>${esc(metric)}</td>
          <td class="mono">${esc(value)}</td>
          <td>${esc(data.document_year ?? "—")}</td>
          <td style="font-size:11.5px;color:var(--text-muted);font-family:var(--font-mono);">${esc(docId)}</td>
        </tr>`).join("");
    } else {
      tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state"><p class="empty-sub">No financial metrics could be extracted from this document</p></div></td></tr>`;
    }

    // ── KPI Cards (from real extracted data) ────────────────────
    const revenue      = raw["Revenue"] || raw["Total Amount"] || raw["Fee Cleared"] || null;
    const revLabel     = (raw["Revenue"] && !raw["Total Amount"]) ? "Revenue" : (raw["Total Amount"] ? "Total Amount / Revenue" : "Revenue");
    const netIncome    = raw["Net Income"]   || null;
    const grossProfit  = raw["Gross Profit"] || null;
    const pm           = ratios.profit_margin_pct;
    const cr           = ratios.current_ratio;
    const de           = ratios.debt_to_equity;
    const health       = data.financial_health || ratios.financial_health || (revenue ? "Healthy" : "—");
    const period       = `${data.filename || docId} · ${data.document_year || ""}`;

    document.getElementById("kpiPeriodLabel").textContent = period;

    kpiGrid.innerHTML = `
      <div class="kpi-card blue">
        <p class="kpi-label">${esc(revLabel)}</p>
        <p class="kpi-value">${revenue || "—"}</p>
        <span class="kpi-delta flat">Extracted value</span>
      </div>
      <div class="kpi-card green">
        <p class="kpi-label">Net Income</p>
        <p class="kpi-value">${netIncome || "—"}</p>
        <span class="kpi-delta flat">Extracted value</span>
      </div>
      <div class="kpi-card amber">
        <p class="kpi-label">Profit Margin</p>
        <p class="kpi-value">${pm != null ? pm.toFixed(1) + "%" : (revenue && !netIncome ? "N/A" : "—")}</p>
        <span class="kpi-delta flat">Net margin</span>
      </div>
      <div class="kpi-card purple">
        <p class="kpi-label">Financial Health</p>
        <p class="kpi-value" style="font-size:1.2rem;">${esc(health)}</p>
        <span class="kpi-delta ${health === "Healthy" ? "up" : health === "Needs Attention" ? "down" : "flat"}">
          ${health === "Insufficient Data" ? "Need more data" : "Overall rating"}
        </span>
      </div>`;

    // ── Render ratios and charts with real data ────────────────
    renderRatios(ratios);
    renderCharts(raw, ratios);

  } catch (e) {
    badge.textContent = "—";
    tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state"><p class="empty-sub">Could not load metrics for ${esc(docId)}</p></div></td></tr>`;
    console.error("loadMetricsAndKPIs error:", e);
  }
}

// -------------------------------------------------------------------
// SECTION 6: Financial Ratios — Gauge cards from real DB data
// BUG FIX #4: driven by per-document ratios, not hardcoded values
// -------------------------------------------------------------------
function buildGaugeSVG(pct, color) {
  const r = 46, cx = 60, cy = 58;
  const total = Math.PI * r;
  const fill  = total * Math.min(Math.max(pct, 0), 1);
  const startX = cx - r, endX = cx + r;

  return `<svg viewBox="0 0 120 65">
    <path class="gauge-track"
      d="M ${startX} ${cy} A ${r} ${r} 0 0 1 ${endX} ${cy}"
      stroke-dasharray="${total}" stroke-dashoffset="0"/>
    <path class="gauge-fill"
      d="M ${startX} ${cy} A ${r} ${r} 0 0 1 ${endX} ${cy}"
      stroke="${color}"
      stroke-dasharray="${total}"
      stroke-dashoffset="${total - fill}"/>
  </svg>`;
}

function renderRatios(ratios) {
  const grid = document.getElementById("ratiosGrid");
  if (!ratios || Object.keys(ratios).length === 0) {
    grid.innerHTML = `<div class="empty-state card-pad"><p class="empty-sub">No ratios available — insufficient financial data in document</p></div>`;
    return;
  }

  const defs = [];

  if (ratios.current_ratio != null) {
    const v = ratios.current_ratio;
    defs.push({
      name: "Current Ratio",
      display: v.toFixed(2) + "x",
      pct: Math.min(v / 4, 1),
      color: v >= 1.5 ? "#10B981" : v >= 1.0 ? "#F59E0B" : "#EF4444",
      statusClass: v >= 1.5 ? "good" : v >= 1.0 ? "ok" : "bad",
      statusLabel: v >= 1.5 ? "Healthy" : v >= 1.0 ? "Caution" : "At Risk",
      desc: "Current assets ÷ current liabilities. >1.5 considered healthy.",
    });
  }

  if (ratios.debt_to_equity != null) {
    const v = ratios.debt_to_equity;
    defs.push({
      name: "Debt-to-Equity",
      display: v.toFixed(2) + "x",
      pct: Math.min(v / 2, 1),
      color: v <= 1.0 ? "#10B981" : v <= 1.5 ? "#F59E0B" : "#EF4444",
      statusClass: v <= 1.0 ? "good" : v <= 1.5 ? "ok" : "bad",
      statusLabel: v <= 1.0 ? "Manageable" : v <= 1.5 ? "Moderate" : "High",
      desc: "Total debt ÷ total equity. Lower is less leveraged.",
    });
  }

  if (ratios.profit_margin_pct != null) {
    const v = ratios.profit_margin_pct;
    defs.push({
      name: "Profit Margin",
      display: v.toFixed(1) + "%",
      pct: Math.min(v / 30, 1),
      color: v >= 10 ? "#10B981" : v >= 5 ? "#F59E0B" : "#EF4444",
      statusClass: v >= 10 ? "good" : v >= 5 ? "ok" : "bad",
      statusLabel: v >= 10 ? "Strong" : v >= 5 ? "Moderate" : "Weak",
      desc: "Net profit ÷ revenue. Measures what portion of revenue is kept.",
    });
  }

  if (ratios.gross_margin_pct != null) {
    const v = ratios.gross_margin_pct;
    defs.push({
      name: "Gross Margin",
      display: v.toFixed(1) + "%",
      pct: Math.min(v / 60, 1),
      color: v >= 40 ? "#10B981" : v >= 20 ? "#F59E0B" : "#EF4444",
      statusClass: v >= 40 ? "good" : v >= 20 ? "ok" : "bad",
      statusLabel: v >= 40 ? "Strong" : v >= 20 ? "Moderate" : "Low",
      desc: "Gross profit ÷ revenue. Measures cost efficiency.",
    });
  }

  if (ratios.operating_margin_pct != null) {
    const v = ratios.operating_margin_pct;
    defs.push({
      name: "Operating Margin",
      display: v.toFixed(1) + "%",
      pct: Math.min(v / 30, 1),
      color: v >= 10 ? "#10B981" : v >= 5 ? "#F59E0B" : "#EF4444",
      statusClass: v >= 10 ? "good" : v >= 5 ? "ok" : "bad",
      statusLabel: v >= 10 ? "Strong" : v >= 5 ? "Moderate" : "Weak",
      desc: "Operating profit ÷ revenue.",
    });
  }

  if (!defs.length) {
    grid.innerHTML = `<div class="empty-state card-pad"><p class="empty-sub">Ratios could not be calculated — not enough financial data in this document</p></div>`;
    return;
  }

  grid.innerHTML = defs.map(r => `
    <div class="ratio-card">
      <p class="ratio-name">${esc(r.name)}</p>
      <div class="ratio-gauge">
        ${buildGaugeSVG(r.pct, r.color)}
        <div class="ratio-value-display">${esc(r.display)}</div>
      </div>
      <span class="ratio-status ${r.statusClass}">${esc(r.statusLabel)}</span>
      <p class="ratio-desc">${esc(r.desc)}</p>
    </div>`).join("");
}

// -------------------------------------------------------------------
// SECTION 4 & 5: Revenue & Profit Charts — real extracted data
// BUG FIX #5: no hardcoded demo values — uses actual raw_values
// -------------------------------------------------------------------
function _parseNum(str) {
  if (!str) return null;
  const s = str.replace(/Rs\.?|₹|INR|\$|€|,/g, "").trim();
  let mult = 1;
  if (/crore/i.test(s))   mult = 1e7;
  else if (/lakh/i.test(s)) mult = 1e5;
  else if (/billion/i.test(s)) mult = 1e9;
  else if (/million/i.test(s)) mult = 1e6;
  const num = parseFloat(s.replace(/[^0-9.]/g, ""));
  return isNaN(num) ? null : num * mult;
}

function renderCharts(rawValues, ratios) {
  const revenue         = _parseNum(rawValues["Revenue"]) ?? _parseNum(rawValues["Total Amount"]) ?? _parseNum(rawValues["Fee Cleared"]);
  const grossProfit     = _parseNum(rawValues["Gross Profit"]);
  const netIncome       = _parseNum(rawValues["Net Income"]);
  const operatingProfit = _parseNum(rawValues["Operating Profit"]);
  const opex            = _parseNum(rawValues["Operating Expense"]);

  const crFmt = v => {
    if (v == null || isNaN(v)) return "N/A";
    if (Math.abs(v) >= 1e9) return (v / 1e9).toFixed(1) + " Bn";
    if (Math.abs(v) >= 1e7) return (v / 1e7).toFixed(1) + " Cr";
    if (Math.abs(v) >= 1e5) return (v / 1e5).toFixed(1) + " L";
    return v.toLocaleString("en-IN");
  };

  // --- Revenue vs Gross Profit vs Net Income ---
  const revLabels = [];
  const revData   = [];
  const revColors = [];
  if (revenue != null) {
    const rLabel = (rawValues["Revenue"] && !rawValues["Total Amount"]) ? "Revenue" : (rawValues["Total Amount"] ? "Total Amount" : "Revenue");
    revLabels.push(rLabel);
    revData.push(revenue);
    revColors.push("rgba(59,130,246,0.85)");
  }
  if (grossProfit != null)     { revLabels.push("Gross Profit");  revData.push(grossProfit);     revColors.push("rgba(16,185,129,0.85)"); }
  if (operatingProfit != null) { revLabels.push("Op. Profit");    revData.push(operatingProfit); revColors.push("rgba(245,158,11,0.80)"); }
  if (netIncome != null)       { revLabels.push("Net Income");    revData.push(netIncome);       revColors.push("rgba(16,185,129,0.95)"); }

  renderChartOrEmpty("revenueChart", revLabels.length > 0, "No revenue or transaction figures extracted", {
    type: "bar",
    data: {
      labels: revLabels,
      datasets: [{ data: revData, backgroundColor: revColors, borderRadius: 6, borderSkipped: false }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: c => " " + crFmt(c.parsed.y) } },
      },
      scales: {
        y: { ticks: { callback: crFmt }, grid: { color: "rgba(255,255,255,0.06)" } },
        x: { grid: { display: false } },
      },
    },
  });

  // --- Operating Expense Breakdown (Doughnut) ---
  const hasOpex = (opex != null && revenue != null);
  const nonOpex = hasOpex ? Math.max(0, revenue - opex) : 0;
  renderChartOrEmpty("opexChart", hasOpex, "Operating expense data not available", {
    type: "doughnut",
    data: {
      labels: ["Operating Expense", "Remaining Revenue"],
      datasets: [{
        data: [opex, nonOpex],
        backgroundColor: ["rgba(139,92,246,0.85)", "rgba(59,130,246,0.35)"],
        borderColor: "rgba(22,29,39,0.8)",
        borderWidth: 3,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      cutout: "62%",
      plugins: {
        legend: { position: "bottom", labels: { padding: 16, boxWidth: 12, boxHeight: 12 } },
        tooltip: { callbacks: { label: c => " " + crFmt(c.parsed) } },
      },
    },
  });

  // --- Profit Waterfall ---
  const wfLabels = [], wfData = [], wfColors = [];
  if (revenue != null)         { wfLabels.push((rawValues["Revenue"] && !rawValues["Total Amount"]) ? "Revenue" : "Total Amount"); wfData.push(revenue); wfColors.push("rgba(59,130,246,0.85)"); }
  if (grossProfit != null)     { wfLabels.push("Gross Profit"); wfData.push(grossProfit);     wfColors.push("rgba(16,185,129,0.75)"); }
  if (operatingProfit != null) { wfLabels.push("Op. Profit");   wfData.push(operatingProfit); wfColors.push("rgba(245,158,11,0.75)"); }
  if (netIncome != null)       { wfLabels.push("Net Income");   wfData.push(netIncome);       wfColors.push("rgba(16,185,129,0.90)"); }

  renderChartOrEmpty("profitWaterfallChart", wfLabels.length > 0, "No profit data extracted", {
    type: "bar",
    data: {
      labels: wfLabels,
      datasets: [{ data: wfData, backgroundColor: wfColors, borderRadius: 6, borderSkipped: false }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: c => " " + crFmt(c.parsed.y) } },
      },
      scales: {
        y: { ticks: { callback: crFmt }, grid: { color: "rgba(255,255,255,0.06)" } },
        x: { grid: { display: false } },
      },
    },
  });

  // --- Profit Margins bar ---
  const marginLabels = [], marginData = [], marginColors = [];
  if (ratios.gross_margin_pct != null)     { marginLabels.push("Gross Margin");     marginData.push(ratios.gross_margin_pct);     marginColors.push("rgba(59,130,246,0.85)"); }
  if (ratios.operating_margin_pct != null) { marginLabels.push("Operating Margin"); marginData.push(ratios.operating_margin_pct); marginColors.push("rgba(139,92,246,0.85)"); }
  if (ratios.profit_margin_pct != null)    { marginLabels.push("Net Margin");       marginData.push(ratios.profit_margin_pct);    marginColors.push("rgba(16,185,129,0.90)"); }

  renderChartOrEmpty("marginChart", marginLabels.length > 0, "Margin data not available", {
    type: "bar",
    data: {
      labels: marginLabels,
      datasets: [{
        data: marginData,
        backgroundColor: marginColors,
        borderRadius: 6,
        borderSkipped: false,
        maxBarThickness: 72,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: c => " " + c.parsed.y.toFixed(1) + "%" } },
      },
      scales: {
        y: {
          ticks: { callback: v => v + "%" },
          grid: { color: "rgba(255,255,255,0.06)" },
        },
        x: { grid: { display: false } },
      },
    },
  });
}

// -------------------------------------------------------------------
// SECTION 8: AI Insights — doc-specific
// BUG FIX #4: /api/documents/{doc_id}/insights when doc selected
// -------------------------------------------------------------------
async function loadInsights(docId) {
  const grid   = document.getElementById("insightsGrid");
  const banner = document.getElementById("riskBanner");

  const url = docId
    ? `/api/documents/${encodeURIComponent(docId)}/insights`
    : "/api/insights";

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("not found");
    const data = await res.json();

    if (data.error) throw new Error(data.error);

    // Risk banner
    const risk = data.overall_risk || "—";
    banner.style.display = "flex";
    const riskBar = document.getElementById("riskBarFill");
    riskBar.className = `risk-bar-fill ${risk}`;
    const riskVal = document.getElementById("riskValue");
    riskVal.textContent = risk;
    riskVal.className = `risk-value ${risk}`;

    // Insight cards
    const iconMap  = { positive: "✅", warning: "⚠️", not_computable: "ℹ️" };
    const classMap = { positive: "positive", warning: "warning", not_computable: "neutral" };

    const insightsArr = data.insights || [];
    if (!insightsArr.length) throw new Error("no insights");

    grid.innerHTML = insightsArr.map((item, i) => `
      <div class="insight-card">
        <div class="insight-icon ${classMap[item.status] || "neutral"}">${iconMap[item.status] || "·"}</div>
        <div class="insight-content">
          <p class="insight-text">${esc(item.text)}</p>
          ${item.evidence ? `
            <button class="insight-source-btn" data-idx="${i}" onclick="toggleEvidence(${i})">
              View source evidence ↓
            </button>
            <div class="insight-evidence" id="evidence-${i}">
              <p class="insight-evidence-source">📄 ${esc(item.evidence.document)}</p>
              <p class="insight-evidence-text">${esc(item.evidence.text)}</p>
            </div>` : ""}
        </div>
      </div>`).join("");

  } catch (e) {
    banner.style.display = "none";
    grid.innerHTML = `
      <div class="empty-state card card-pad">
        <div class="empty-icon">💡</div>
        <p class="empty-title">${docId ? "No insights for this document" : "Upload a document to generate insights…"}</p>
        <p class="empty-sub">${docId ? "The document may not have enough financial data." : "Insights are generated automatically after upload."}</p>
      </div>`;
  }
}

function toggleEvidence(idx) {
  const el = document.getElementById(`evidence-${idx}`);
  if (el) el.classList.toggle("visible");
}

// -------------------------------------------------------------------
// SECTION 8b: Anomaly Detection — doc-specific (NEW)
// BUG FIX #4: /api/documents/{doc_id}/anomalies
// -------------------------------------------------------------------
async function loadAnomalies(docId) {
  const container = document.getElementById("anomaliesContainer");
  if (!docId) {
    container.innerHTML = `
      <div class="empty-state card card-pad">
        <div class="empty-icon">🔍</div>
        <p class="empty-title">No document loaded</p>
        <p class="empty-sub">Upload a document to detect anomalies</p>
      </div>`;
    return;
  }

  try {
    const res = await fetch(`/api/documents/${encodeURIComponent(docId)}/anomalies`);
    if (!res.ok) throw new Error("not found");
    const data = await res.json();
    const anomalies = data.anomalies || [];

    if (!anomalies.length) {
      container.innerHTML = `
        <div class="empty-state card card-pad">
          <div class="empty-icon">✅</div>
          <p class="empty-title">No anomalies detected</p>
          <p class="empty-sub">No unusual financial patterns found in this document</p>
        </div>`;
      return;
    }

    const sevClass = { high: "bad", medium: "ok", low: "good", info: "neutral" };
    const sevIcon  = { high: "🔴", medium: "🟡", low: "🟢", info: "ℹ️" };

    container.innerHTML = `<div class="insights-grid">` +
      anomalies.map(a => `
        <div class="insight-card">
          <div class="insight-icon ${sevClass[a.severity] || "neutral"}">${sevIcon[a.severity] || "⚠️"}</div>
          <div class="insight-content">
            <p class="insight-text" style="font-weight:600;">${esc(a.type)}</p>
            <p class="insight-text">${esc(a.message)}</p>
            <span class="ratio-status ${sevClass[a.severity] || "ok"}" style="margin-top:6px;display:inline-block;">
              ${esc(a.severity?.toUpperCase() || "MEDIUM")} severity
            </span>
          </div>
        </div>`).join("") +
      `</div>`;

  } catch (e) {
    container.innerHTML = `
      <div class="empty-state card card-pad">
        <div class="empty-icon">🔍</div>
        <p class="empty-title">Anomaly data unavailable</p>
        <p class="empty-sub">Could not load anomalies for ${esc(docId)}</p>
      </div>`;
  }
}

// -------------------------------------------------------------------
// SECTION 9: Q&A Chat
// BUG FIX #4: use doc-specific /api/documents/{doc_id}/ask when available
// -------------------------------------------------------------------
const chatForm    = document.getElementById("chatForm");
const chatInput   = document.getElementById("chatInput");
const chatLog     = document.getElementById("chatLog");
const chatSendBtn = document.getElementById("chatSendBtn");

// Suggested questions
document.querySelectorAll(".suggested-q").forEach(btn => {
  btn.addEventListener("click", () => {
    chatInput.value = btn.dataset.q;
    chatForm.dispatchEvent(new Event("submit"));
  });
});

chatForm.addEventListener("submit", async e => {
  e.preventDefault();
  const question = chatInput.value.trim();
  if (!question) return;

  appendChatMsg("user", question);
  chatInput.value = "";
  chatSendBtn.disabled = true;

  // Thinking bubble
  const thinkingId = "thinking-" + Date.now();
  const thinkingDiv = document.createElement("div");
  thinkingDiv.className = "chat-msg ai";
  thinkingDiv.id = thinkingId;
  thinkingDiv.innerHTML = `
    <div class="chat-avatar">AI</div>
    <div class="chat-bubble">
      <div class="chat-thinking"><span></span><span></span><span></span></div>
    </div>`;
  chatLog.appendChild(thinkingDiv);
  chatLog.scrollTop = chatLog.scrollHeight;

  try {
    // BUG FIX #4: use doc-specific RAG endpoint when a document is active
    let res;
    if (activeDocId) {
      res = await fetch(`/api/documents/${encodeURIComponent(activeDocId)}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
    } else {
      res = await fetch("/api/qa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
    }

    const data = await res.json();
    const parent = document.getElementById(thinkingId);
    if (parent) {
      const answer = data.answer || "I could not find an answer to that question.";
      const source = data.source_document || (activeDocId ? activeDocId : "—");
      const score  = data.retrieved_chunks?.[0]?.score;
      const docTag = activeDocId ? `📄 ${esc(source)}${score ? ` · relevance ${(score * 100).toFixed(0)}%` : ""}` : `📄 ${esc(source)}`;
      parent.innerHTML = `
        <div class="chat-avatar">AI</div>
        <div>
          <div class="chat-bubble">${esc(answer)}</div>
          <p class="chat-source-tag">${docTag}</p>
        </div>`;
    }
  } catch (err) {
    const parent = document.getElementById(thinkingId);
    if (parent) {
      parent.innerHTML = `
        <div class="chat-avatar">AI</div>
        <div class="chat-bubble" style="color:var(--red);">Could not reach the server.</div>`;
    }
  }

  chatSendBtn.disabled = false;
  chatLog.scrollTop = chatLog.scrollHeight;
});

function appendChatMsg(role, text) {
  const div = document.createElement("div");
  div.className = `chat-msg ${role}`;
  const avatar = role === "user" ? "You" : "AI";
  div.innerHTML = `
    <div class="chat-avatar">${avatar}</div>
    <div class="chat-bubble">${esc(text)}</div>`;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

// -------------------------------------------------------------------
// Authentication & Session Management
// -------------------------------------------------------------------
let currentUser = null;

const authView = document.getElementById("authView");
const appShell = document.getElementById("appShell");

const loginCard = document.getElementById("loginCard");
const signupCard = document.getElementById("signupCard");
const forgotCard = document.getElementById("forgotCard");

const loginAlert = document.getElementById("loginAlert");
const signupAlert = document.getElementById("signupAlert");
const forgotAlert = document.getElementById("forgotAlert");

const loginForm = document.getElementById("loginForm");
const signupForm = document.getElementById("signupForm");
const forgotForm = document.getElementById("forgotForm");
const resetForm = document.getElementById("resetForm");

const loginBtn = document.getElementById("loginBtn");
const signupBtn = document.getElementById("signupBtn");
const forgotBtn = document.getElementById("forgotBtn");
const logoutBtn = document.getElementById("logoutBtn");

// Helper to show auth card
function showAuthCard(cardToShow) {
  [loginCard, signupCard, forgotCard].forEach(c => {
    if (c) c.style.display = "none";
  });
  if (cardToShow) cardToShow.style.display = "block";
  hideAlerts();
}

function hideAlerts() {
  if (loginAlert) { loginAlert.style.display = "none"; loginAlert.textContent = ""; }
  if (signupAlert) { signupAlert.style.display = "none"; signupAlert.textContent = ""; }
  if (forgotAlert) { forgotAlert.style.display = "none"; forgotAlert.textContent = ""; }
}

function showAlert(elem, msg, isError = true) {
  if (!elem) return;
  elem.className = isError ? "auth-alert error" : "auth-alert info";
  elem.textContent = msg;
  elem.style.display = "block";
}

// Password toggle helper
function setupPasswordToggle(btnId, inputId) {
  const btn = document.getElementById(btnId);
  const input = document.getElementById(inputId);
  if (!btn || !input) return;

  btn.addEventListener("click", () => {
    const isPw = input.type === "password";
    input.type = isPw ? "text" : "password";
    const eyeOpen = btn.querySelector(".eye-open");
    const eyeClosed = btn.querySelector(".eye-closed");
    if (eyeOpen) eyeOpen.style.display = isPw ? "none" : "block";
    if (eyeClosed) eyeClosed.style.display = isPw ? "block" : "none";
  });
}

setupPasswordToggle("toggleLoginPw", "loginPassword");
setupPasswordToggle("toggleSignupPw", "signupPassword");

// Card switch events
document.getElementById("toSignupBtn")?.addEventListener("click", (e) => {
  e.preventDefault();
  showAuthCard(signupCard);
});

document.getElementById("toLoginBtn")?.addEventListener("click", (e) => {
  e.preventDefault();
  showAuthCard(loginCard);
});

document.getElementById("toForgotBtn")?.addEventListener("click", (e) => {
  e.preventDefault();
  showAuthCard(forgotCard);
});

document.getElementById("forgotToLoginBtn")?.addEventListener("click", (e) => {
  e.preventDefault();
  showAuthCard(loginCard);
});

// Login submission
loginForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlerts();

  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;
  const rememberMe = document.getElementById("rememberMe")?.checked || false;

  if (!email || !password) {
    showAlert(loginAlert, "Please enter both email and password.");
    return;
  }

  // Button loading state
  loginBtn.disabled = true;
  const btnText = loginBtn.querySelector(".btn-text");
  const btnSpinner = loginBtn.querySelector(".btn-spinner");
  if (btnText) btnText.textContent = "Signing in...";
  if (btnSpinner) btnSpinner.style.display = "inline-block";

  try {
    const res = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, remember_me: rememberMe }),
    });

    const data = await res.json();
    if (!res.ok) {
      showAlert(loginAlert, data.detail || "Invalid email or password.");
      return;
    }

    showToast(`Welcome back, ${data.user.full_name}!`, "success");
    await initAuth();
  } catch (err) {
    showAlert(loginAlert, "Network error: Could not connect to server.");
  } finally {
    loginBtn.disabled = false;
    if (btnText) btnText.textContent = "Sign In";
    if (btnSpinner) btnSpinner.style.display = "none";
  }
});

// Signup submission
signupForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlerts();

  const fullName = document.getElementById("signupName").value.trim();
  const email = document.getElementById("signupEmail").value.trim();
  const password = document.getElementById("signupPassword").value;
  const confirmPassword = document.getElementById("signupConfirmPassword").value;

  if (!fullName) {
    showAlert(signupAlert, "Please enter your full name.");
    return;
  }
  if (!email || !email.includes("@")) {
    showAlert(signupAlert, "Please enter a valid email address.");
    return;
  }
  if (password.length < 6) {
    showAlert(signupAlert, "Password must be at least 6 characters long.");
    return;
  }
  if (password !== confirmPassword) {
    showAlert(signupAlert, "Passwords do not match.");
    return;
  }

  signupBtn.disabled = true;
  const btnText = signupBtn.querySelector(".btn-text");
  const btnSpinner = signupBtn.querySelector(".btn-spinner");
  if (btnText) btnText.textContent = "Creating Account...";
  if (btnSpinner) btnSpinner.style.display = "inline-block";

  try {
    const res = await fetch("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: fullName,
        email: email,
        password: password,
        confirm_password: confirmPassword,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      showAlert(signupAlert, data.detail || "Registration failed.");
      return;
    }

    showToast("Account created successfully!", "success");
    await initAuth();
  } catch (err) {
    showAlert(signupAlert, "Network error: Could not connect to server.");
  } finally {
    signupBtn.disabled = false;
    if (btnText) btnText.textContent = "Create Account";
    if (btnSpinner) btnSpinner.style.display = "none";
  }
});

// Forgot Password submission
forgotForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideAlerts();

  const email = document.getElementById("forgotEmail").value.trim();
  if (!email || !email.includes("@")) {
    showAlert(forgotAlert, "Please enter a valid email address.");
    return;
  }

  forgotBtn.disabled = true;
  const btnText = forgotBtn.querySelector(".btn-text");
  const btnSpinner = forgotBtn.querySelector(".btn-spinner");
  if (btnText) btnText.textContent = "Sending...";
  if (btnSpinner) btnSpinner.style.display = "inline-block";

  try {
    const res = await fetch("/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });

    const data = await res.json();
    showAlert(forgotAlert, data.message, false);

    if (data.dev_token) {
      const resetSub = document.getElementById("resetSubSection");
      const resetTokenInput = document.getElementById("resetToken");
      if (resetSub && resetTokenInput) {
        resetSub.style.display = "block";
        resetTokenInput.value = data.dev_token;
      }
    }
  } catch (err) {
    showAlert(forgotAlert, "Network error: Could not process request.");
  } finally {
    forgotBtn.disabled = false;
    if (btnText) btnText.textContent = "Send Reset Link";
    if (btnSpinner) btnSpinner.style.display = "none";
  }
});

// Reset Password submission
resetForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const token = document.getElementById("resetToken").value;
  const newPw = document.getElementById("resetNewPassword").value;
  const confirmPw = document.getElementById("resetConfirmPassword").value;

  if (newPw.length < 6) {
    showAlert(forgotAlert, "Password must be at least 6 characters.");
    return;
  }
  if (newPw !== confirmPw) {
    showAlert(forgotAlert, "Passwords do not match.");
    return;
  }

  try {
    const res = await fetch("/auth/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token,
        new_password: newPw,
        confirm_password: confirmPw,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      showAlert(forgotAlert, data.detail || "Reset failed.");
      return;
    }
    showToast("Password updated! You can now log in.", "success");
    showAuthCard(loginCard);
  } catch (err) {
    showAlert(forgotAlert, "Network error updating password.");
  }
});

// Logout handler
logoutBtn?.addEventListener("click", async () => {
  try {
    await fetch("/auth/logout", { method: "POST" });
  } catch (err) {}
  currentUser = null;
  activeDocId = null;
  showToast("Logged out successfully.", "info");
  renderUnauthenticatedView();
});

function renderUnauthenticatedView() {
  if (appShell) appShell.style.display = "none";
  if (authView) authView.style.display = "flex";
  showAuthCard(loginCard);
}

// Initial authentication check & app bootstrap
async function initAuth() {
  try {
    const res = await fetch("/auth/me");
    if (!res.ok) {
      renderUnauthenticatedView();
      return;
    }

    const user = await res.json();
    currentUser = user;

    // Update UI with user info
    const firstName = user.full_name.split(" ")[0] || "Analyst";
    const initial = user.full_name.charAt(0).toUpperCase() || "U";

    const welcomeEl = document.getElementById("userWelcomeText");
    if (welcomeEl) welcomeEl.textContent = `Welcome back, ${firstName}`;

    const avatarEl = document.getElementById("userAvatar");
    if (avatarEl) avatarEl.textContent = initial;

    const nameEl = document.getElementById("userNameText");
    if (nameEl) nameEl.textContent = user.full_name;

    const emailEl = document.getElementById("userEmailText");
    if (emailEl) emailEl.textContent = user.email;

    // Show app shell, hide auth view
    if (authView) authView.style.display = "none";
    if (appShell) appShell.style.display = "flex";

    // Load documents belonging to this user
    await loadDocumentList();

    if (docSelector && docSelector.options.length > 1) {
      const firstDocId = docSelector.options[1].value;
      activeDocId = firstDocId;
      docSelector.selectedIndex = 1;
      await loadDocumentDetails(firstDocId);
    } else {
      await loadInsights(null);
    }
  } catch (err) {
    console.error("Auth check failed:", err);
    renderUnauthenticatedView();
  }
}

// Run auth check on page load
initAuth();

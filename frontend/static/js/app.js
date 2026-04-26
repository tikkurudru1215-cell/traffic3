/* ============================================================
   app.js — Core Logic, Tab Switching, & Shared Helpers
   ============================================================ */

const API = window.location.origin;

const LEVEL_DESC = {
    "LOW":       "Free flowing — no significant delays.",
    "MODERATE":  "Noticeable volume — expect minor slow-downs.",
    "HIGH":      "Heavy congestion — high probability of delays.",
    "VERY HIGH": "Near gridlock — traffic is significantly backed up."
};

/**
 * Tab Switching Logic
 */
function switchTab(id, el) {
    // 1. UI Toggle classes
    document.querySelectorAll(".page").forEach(p => p.classList.remove("on"));
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("on"));
    
    const targetPage = document.getElementById(id);
    if (targetPage) targetPage.classList.add("on");
    if (el) el.classList.add("on");

    // 2. Data Loading Triggers
    if (id === "p-dash") {
        if (typeof initDashboard === "function") initDashboard(); 
    } 
    else if (id === "p-pred") {
        if (typeof initPredictor === "function") initPredictor();
    }
    else if (id === "p-models") {
        if (typeof initModelAnalysis === "function") initModelAnalysis();
    } 
    else if (id === "p-data") {
        if (typeof initDataTab === "function") initDataTab();
    }
}

/* ── API Helpers ───────────────────────────────────────────── */
async function apiFetch(path, opts = {}) {
    const res = await fetch(window.location.origin + path, {
        headers: { "Content-Type": "application/json" },
        ...opts
    });
    if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
    return res.json();
}

function apiGet(path)        { return apiFetch(path); }
function apiPost(path, body) { return apiFetch(path, { method:"POST", body:JSON.stringify(body) }); }

/* ── Traffic Classifiers ───────────────────────────────────── */
function classifyVolume(v, thresholds) {
    const t = thresholds || { moderate: 450, high: 950, very_high: 1550 };
    
    if (v < t.moderate)  return { level:"LOW",       color:"#10d97e", cls:"bg-g" };
    if (v < t.high)      return { level:"MODERATE",  color:"#f5a623", cls:"bg-y" };
    if (v < t.very_high) return { level:"HIGH",      color:"#ff4d4d", cls:"bg-r" };
    return               { level:"VERY HIGH", color:"#9b6dff", cls:"bg-p" };
}

/* ── Chart Defaults ────────────────────────────────────────── */
function chartDefaults(extra = {}) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { 
            legend: { display: false, labels: { color: "#94a3b8" } },
            ...extra.plugins 
        },
        scales: {
            x: { ticks:{ color:"#64748b", font:{size:10} }, grid:{ color:"#1e293b" } },
            y: { ticks:{ color:"#64748b", font:{size:10} }, grid:{ color:"#1e293b" } },
            ...extra.scales,
        },
        ...extra,
    };
}

/* ── Clock ─────────────────────────────────────────────────── */
function updateClock() {
    const n = new Date();
    const t = n.toLocaleTimeString("en-IN", { hour:"2-digit", minute:"2-digit", hour12:true });
    const clkEl = document.getElementById("clk");
    if (clkEl) clkEl.textContent = t;
}

/* ── Page Load ─────────────────────────────────────────────── */
window.addEventListener("DOMContentLoaded", () => {
    // 1. Initial Status Load
    apiGet("/api/status").then(d => {
        const chip = document.getElementById("chip-r2");
        if (chip) chip.textContent = `RF R²=${d.r2}`;
    }).catch(e => console.warn("Backend not ready yet."));

    // 2. Start clock
    setInterval(updateClock, 1000);
    updateClock();

    // 3. Default to Dashboard on load - only trigger if current page is Dashboard
    const activeTab = document.querySelector(".tab.on");
    if (activeTab && activeTab.getAttribute("onclick").includes("p-dash")) {
        initDashboard();
    }
});

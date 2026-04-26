/* ============================================================
   dashboard.js — Data Fetching & Chart Rendering
   Tabs Handled: Dashboard, Model Analysis, Data Pipeline
   ============================================================ */
const API_BASE_URL = window.location.origin;

async function apiGet(endpoint) {
    const res = await fetch(`${API_BASE_URL}${endpoint}`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
}

let charts = {}; // Store chart instances globally to prevent re-init errors

/**
 * Main initializer for the Dashboard Tab
 */
async function initDashboard() {
    try {
        const [eda, metrics] = await Promise.all([
            apiGet("/api/eda"),
            apiGet("/api/metrics")
        ]);

        // 1. Update Metric Cards at the top
        document.querySelector("#mc-rf .mc-val").textContent = metrics.rf.r2.toFixed(4);
        document.querySelector("#mc-lr .mc-val").textContent = metrics.lr.r2.toFixed(4);
        document.querySelector("#mc-imp .mc-val").textContent = metrics.improvement + "x";
        document.querySelector("#mc-dataset .mc-val").textContent = "105,120";

        // 2. Render Dashboard Charts
        renderHourlyChart(eda);
        renderJunctionChart(eda);

    } catch (err) {
        console.error("Dashboard load failed:", err);
    }
}

/**
 * Main initializer for the Model Analysis Tab
 */
async function initModelAnalysis() {
    try {
        const data = await apiGet("/api/metrics");
        
        // 1. Comparison Chart (RF vs LR)
        const ctxComp = document.getElementById("c-compare")?.getContext("2d");
        if (ctxComp) {
            if (charts.compare) charts.compare.destroy();
            charts.compare = new Chart(ctxComp, {
                type: 'bar',
                data: {
                    labels: ['Random Forest (RF)', 'Linear Regression (LR)'],
                    datasets: [{
                        label: 'Mean Absolute Error (Lower is Better)',
                        data: [data.rf.mae, data.lr.mae],
                        backgroundColor: ['#10b981', '#64748b'],
                        borderRadius: 6
                    }]
                },
                options: chartDefaults({ indexAxis: 'y' })
            });
        }

        // 2. Feature Importance Chart (Dynamic)
        renderFeatureImportance(data.feat_imp);

    } catch (err) {
        console.error("Model Analysis load failed:", err);
    }
}

/**
 * Main initializer for the Data Pipeline Tab
 */
async function initDataTab() {
    try {
        const data = await apiGet("/api/eda");
        const ctxDist = document.getElementById("c-dist")?.getContext("2d");
        if (ctxDist) {
            if (charts.dist) charts.dist.destroy();
            charts.dist = new Chart(ctxDist, {
                type: 'bar',
                data: {
                    labels: data.dist_labels,
                    datasets: [{
                        label: 'Frequency',
                        data: data.dist_counts,
                        backgroundColor: '#3b82f6'
                    }]
                },
                options: chartDefaults()
            });
        }
    } catch (err) {
        console.error("Data tab load failed:", err);
    }
}

/* ── Individual Chart Renderers ────────────────────────────── */

function renderHourlyChart(data) {
    const ctx = document.getElementById("c-hourly")?.getContext("2d");
    if (!ctx) return;
    if (charts.hourly) charts.hourly.destroy();
    charts.hourly = new Chart(ctx, {
        type: 'line',
        data: {
            labels: Array.from({length: 24}, (_, i) => `${i}:00`),
            datasets: [
                { label: 'Weekday', data: data.hourly_weekday, borderColor: '#3b82f6', tension: 0.4 },
                { label: 'Weekend', data: data.hourly_weekend, borderColor: '#10b981', tension: 0.4 }
            ]
        },
        options: chartDefaults({ plugins: { legend: { display: true } } })
    });
}

function renderJunctionChart(data) {
    const ctx = document.getElementById("c-junc")?.getContext("2d");
    if (!ctx) return;
    if (charts.junc) charts.junc.destroy();
    charts.junc = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Object.values(data.junction_names),
            datasets: [{
                data: Object.values(data.junction_avg),
                backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']
            }]
        },
        options: chartDefaults()
    });
}

function renderFeatureImportance(featImp) {
    // Create the container dynamically if it's missing
    const parent = document.getElementById("p-models");
    let importanceBox = document.getElementById("importance-box");
    
    if (!importanceBox) {
        importanceBox = document.createElement("div");
        importanceBox.id = "importance-box";
        importanceBox.className = "pnl";
        importanceBox.style.marginTop = "20px";
        importanceBox.innerHTML = `
            <div class="pnl-hd"><div class="pnl-ttl">Feature Importance (RF)</div><div class="pnl-sub">Top weights assigned by model</div></div>
            <div class="cw h240"><canvas id="c-importance"></canvas></div>
        `;
        parent.appendChild(importanceBox);
    }

    const ctx = document.getElementById("c-importance").getContext("2d");
    const labels = Object.keys(featImp).slice(0, 7);
    const values = Object.values(featImp).slice(0, 7);

    if (charts.importance) charts.importance.destroy();
    charts.importance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels.map(l => l.replace('_', ' ').toUpperCase()),
            datasets: [{
                data: values,
                backgroundColor: 'rgba(139, 92, 246, 0.6)',
                borderColor: '#8b5cf6',
                borderWidth: 1
            }]
        },
        options: chartDefaults()
    });
}
window.addEventListener("DOMContentLoaded", () => {
    initDashboard();
});

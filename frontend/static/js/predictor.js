/* ============================================================
    predictor.js — Full Project Version (Production Ready)
    Integrated: SHAP Explainable AI & Anomaly Detection UI
    ============================================================ */

let forecastChart = null; 

// Detect if we are running on Render or Localhost
const API_BASE_URL = window.location.origin;

/**
 * Helper: Centralized Fetch wrapper to handle API calls
 */
async function apiPost(endpoint, data) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
}

/**
 * Main function: Orchestrates the prediction and UI updates
 */
async function runPrediction() {
    const btn = document.getElementById("pred-btn");
    const resPnl = document.getElementById("result-pnl");
    const insPnl = document.getElementById("insights-pnl");
    
    // 1. Gather inputs safely
    const elHr = document.getElementById("sl-hr");
    const elDay = document.getElementById("sel-day");
    const elJunc = document.getElementById("sel-junc");
    const elWthr = document.getElementById("sel-wthr");

    if (!elHr || !elDay || !elJunc) {
        console.error("Critical UI elements missing. Check index.html IDs.");
        return;
    }

    const payload = {
        hour: parseInt(elHr.value),
        day_of_week: parseInt(elDay.value),
        month: 3, // Defaulting to March
        weather: elWthr ? elWthr.value : "Clear",
        junction_id: elJunc.value
    };

    try {
        btn.disabled = true;
        btn.textContent = "RUNNING AI INFERENCE...";

        // 2. Fetch Prediction (includes SHAP & Anomaly data) and 24h Trend
        const [pred, fc] = await Promise.all([
            apiPost("/api/predict", payload),
            apiPost("/api/forecast", payload)
        ]);

        // 3. Update Standard Result UI
        updatePredictorUI(pred);

        // 4. Update the ADVANCED INSIGHTS BOX (SHAP & Anomaly)
        updateInsightsBox(pred);

        // 5. Render Trend Graph
        renderForecast(fc.hours, pred.thresholds);

        // 6. Reveal panels
        if (resPnl) resPnl.classList.add("on");
        if (insPnl) insPnl.style.display = "block";

    } catch (err) {
        console.error("Inference Error:", err);
        // Corrected alert for Production environment
        alert("Inference Failed: Could not connect to the AI Engine. Please check your network or server status.");
    } finally {
        btn.disabled = false;
        btn.textContent = "PREDICT TRAFFIC VOLUME →";
    }
}

/**
 * Updates the basic result panel (Big Number, Progress Bar, Level)
 */
function updatePredictorUI(data) {
    const volEl  = document.getElementById("res-vol");
    const lvlEl  = document.getElementById("res-lvl");
    const descEl = document.getElementById("res-desc");
    const fillEl = document.getElementById("res-fill");

    if (volEl) volEl.textContent = data.volume;
    if (lvlEl) {
        lvlEl.textContent = data.level;
        lvlEl.style.color = data.color;
    }
    
    // Update progress bar
    if (fillEl) {
        const pct = Math.min(100, (data.volume / 2000) * 100);
        fillEl.style.width = pct + "%";
        fillEl.style.background = data.color;
    }

    // Standard descriptive footer
    if (descEl) descEl.textContent = `Bhopal ML Logic: Category is ${data.level} based on 6-junction historical quantiles.`;
}

/**
 * NEW: Populates the Insights Box with SHAP (Explainability) and Anomaly data
 */
function updateInsightsBox(data) {
    const insRaw  = document.getElementById("ins-raw");
    const insWthr = document.getElementById("ins-wthr");
    const insWthrD = document.getElementById("ins-wthr-desc");
    const insEvt  = document.getElementById("ins-event");
    const insEvtD = document.getElementById("ins-event-desc");
    const insConf = document.getElementById("ins-conf");

    if (insRaw) insRaw.textContent = data.volume;

    // Weather Analysis
    if (insWthr) {
        insWthr.textContent = data.inputs.weather;
        insWthr.style.color = ["Rain", "Fog", "Thunderstorm"].includes(data.inputs.weather) ? "#ff4d4d" : "#10d97e";
    }
    if (insWthrD) insWthrD.textContent = data.volume > 800 ? "High resistance" : "Clear flow";

    // Anomaly Detection UI
    if (insEvt) {
        if (data.is_anomaly) {
            insEvt.textContent = "ANOMALY";
            insEvt.style.color = "#ff4d4d";
            if (insEvtD) insEvtD.textContent = "Unusual traffic spike!";
        } else {
            insEvt.textContent = data.is_peak ? "PEAK HOUR" : "NORMAL";
            insEvt.style.color = data.is_peak ? "#f5a623" : "#3b82f6";
            if (insEvtD) insEvtD.textContent = "Standard Bhopal pattern.";
        }
    }

    // XAI Analysis (SHAP Explainability)
    if (insConf) {
        insConf.textContent = "AI Analysis";
        const confD = document.getElementById("ins-xai-details");
        if (confD) {
            let explanation = "";
            for (let [key, val] of Object.entries(data.contributions)) {
                explanation += `${key.split(' ')[0]}: ${val > 0 ? '+' : ''}${val} | `;
            }
            confD.textContent = explanation.slice(0, -2);
        }
    }
}

/**
 * Renders the 24-Hour Forecast Graph
 */
function renderForecast(hours, thresholds) {
    const canvas = document.getElementById("c-forecast");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const labels = hours.map(h => `${h.hour}:00`);
    const volumes = hours.map(h => h.volume);
    
    // Helper to get color if classifyVolume is not defined globally in JS
    const getBarColor = (vol) => {
        if (vol > 1000) return "#ff4d4d"; // High
        if (vol > 500) return "#f5a623";  // Medium
        return "#10d97e";                 // Low
    };

    const colors = hours.map(h => h.color || getBarColor(h.volume));

    if (forecastChart) forecastChart.destroy();
    
    forecastChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                data: volumes,
                backgroundColor: colors,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { 
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => ` ${ctx.raw} veh/hr`
                    }
                }
            },
            scales: {
                y: { beginAtZero: true, grid: { color: "rgba(255,255,255,0.1)" } },
                x: { grid: { display: false } }
            }
        }
    });
}

/**
 * Range Slider Initialization
 */
function initPredictor() {
    const slHr = document.getElementById("sl-hr");
    const lvHr = document.getElementById("lv-hr");
    const slTmp = document.getElementById("sl-tmp");
    const lvTmp = document.getElementById("lv-tmp");

    if (slHr && lvHr) slHr.oninput = () => { lvHr.textContent = `${slHr.value}:00`; };
    if (slTmp && lvTmp) slTmp.oninput = () => { lvTmp.textContent = `${slTmp.value}°C`; };
}

// Initialize sliders on load
window.addEventListener('DOMContentLoaded', initPredictor);

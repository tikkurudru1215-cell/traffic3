/* ============================================================
   predictor.js - Prediction flow with AI insights
   ============================================================ */

async function runPrediction() {
    const btn = document.getElementById("pred-btn");
    const resPnl = document.getElementById("result-pnl");
    const insPnl = document.getElementById("insights-pnl");

    const elHr = document.getElementById("sl-hr");
    const elDay = document.getElementById("sel-day");
    const elJunc = document.getElementById("sel-junc");
    const elWthr = document.getElementById("sel-wthr");
    const elTmp = document.getElementById("sl-tmp");

    if (!elHr || !elDay || !elJunc) {
        console.error("Critical UI elements missing. Check index.html IDs.");
        return;
    }

    const payload = {
        hour: parseInt(elHr.value),
        day_of_week: parseInt(elDay.value),
        temperature_c: elTmp ? parseInt(elTmp.value) : 28,
        month: new Date().getMonth() + 1,
        weather: elWthr ? elWthr.value : "Clear",
        junction_id: elJunc.value,
        is_holiday: 0
    };

    try {
        btn.disabled = true;
        btn.textContent = "RUNNING AI INFERENCE...";

        try {
            const rt = await apiGet("/api/realtime");
            if (rt?.weather) payload.weather = rt.weather;
            if (typeof rt?.temperature_c === "number") payload.temperature_c = rt.temperature_c;
        } catch (_) {}

        const [pred, fc] = await Promise.all([
            apiPost("/api/predict/", payload),
            apiPost("/api/forecast/", payload)
        ]);

        let routeData = { routes: [] };
        try {
            routeData = await apiPost("/api/routes", payload);
        } catch (_) {
            routeData = { routes: [] };
        }

        updatePredictorUI(pred);
        updateInsightsBox(pred, fc.hours || [], routeData.routes || []);
        renderForecast(fc.hours || []);

        if (resPnl) resPnl.style.display = "block";
        if (insPnl) insPnl.style.display = "block";
    } catch (err) {
        console.error("Inference Error:", err);
        let details = "";
        try {
            const st = await apiGet("/api/status");
            if (st?.model_error) details = `\nReason: ${st.model_error}`;
        } catch (_) {}
        alert(`Inference Failed: Could not connect to the AI Engine. Please check server status.${details}`);
    } finally {
        btn.disabled = false;
        btn.textContent = "PREDICT TRAFFIC VOLUME ->";
    }
}

function updatePredictorUI(data) {
    const volEl = document.getElementById("res-vol");
    const lvlEl = document.getElementById("res-lvl");
    const descEl = document.getElementById("res-desc");
    const fillEl = document.getElementById("res-fill");

    if (volEl) volEl.textContent = data.volume;

    if (lvlEl) {
        lvlEl.textContent = data.level;
        lvlEl.style.color = data.color;
    }

    if (fillEl) {
        const pct = Math.min(100, (data.volume / 2000) * 100);
        fillEl.style.width = pct + "%";
        fillEl.style.background = data.color;
    }

    if (descEl) descEl.textContent = `Bhopal ML Logic: Category is ${data.level} based on historical data.`;
}

function updateInsightsBox(data, forecastHours, routes) {
    const insRaw = document.getElementById("ins-raw");
    const insWthr = document.getElementById("ins-wthr");
    const insWthrD = document.getElementById("ins-wthr-desc");
    const insEvt = document.getElementById("ins-event");
    const insEvtD = document.getElementById("ins-event-desc");
    const insConf = document.getElementById("ins-conf");

    const insRisk = document.getElementById("ins-risk");
    const insRiskDesc = document.getElementById("ins-risk-desc");
    const insHotspot = document.getElementById("ins-hotspot");
    const insHotspotDesc = document.getElementById("ins-hotspot-desc");
    const insDelay = document.getElementById("ins-delay");
    const insDelayDesc = document.getElementById("ins-delay-desc");
    const insEmission = document.getElementById("ins-emission");
    const insEmissionDesc = document.getElementById("ins-emission-desc");
    const insSignal = document.getElementById("ins-signal");
    const insSignalDesc = document.getElementById("ins-signal-desc");
    const insIncident = document.getElementById("ins-incident");
    const insIncidentDesc = document.getElementById("ins-incident-desc");
    const insRecoList = document.getElementById("ins-reco-list");

    if (insRaw) insRaw.textContent = data.volume;

    if (insWthr) {
        insWthr.textContent = data.inputs.weather;
        insWthr.style.color = ["Rain", "Fog", "Thunderstorm"].includes(data.inputs.weather) ? "#ff4d4d" : "#10d97e";
    }
    if (insWthrD) insWthrD.textContent = data.volume > 800 ? "High resistance" : "Clear flow";

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

    if (insConf) {
        insConf.textContent = "AI Analysis";
        const confD = document.getElementById("ins-xai-details");
        if (confD && data.contributions) {
            const explanation = Object.entries(data.contributions)
                .map(([key, val]) => `${key.split(" ")[0]}: ${val > 0 ? "+" : ""}${val}`)
                .join(" | ");
            confD.textContent = explanation;
        }
    }

    const analytics = buildSmartCityAnalytics(data, forecastHours, routes);

    if (insRisk) {
        insRisk.textContent = `${analytics.accidentRisk}/100`;
        insRisk.style.color = analytics.accidentRisk >= 75 ? "#ff4d4d" : analytics.accidentRisk >= 50 ? "#f5a623" : "#10d97e";
    }
    if (insRiskDesc) insRiskDesc.textContent = analytics.accidentRiskText;

    if (insHotspot) {
        insHotspot.textContent = analytics.hotspotSeverity;
        insHotspot.style.color = analytics.hotspotSeverityColor;
    }
    if (insHotspotDesc) insHotspotDesc.textContent = analytics.hotspotMessage;

    if (insDelay) insDelay.textContent = `${analytics.next3hDelayMin} min`;
    if (insDelayDesc) insDelayDesc.textContent = analytics.delayMessage;

    if (insEmission) insEmission.textContent = `${analytics.emissionLoadIndex}/100`;
    if (insEmissionDesc) insEmissionDesc.textContent = analytics.emissionMessage;

    if (insSignal) insSignal.textContent = analytics.signalCycle;
    if (insSignalDesc) insSignalDesc.textContent = analytics.signalMessage;

    if (insIncident) {
        insIncident.textContent = analytics.incidentReadiness;
        insIncident.style.color = analytics.incidentColor;
    }
    if (insIncidentDesc) insIncidentDesc.textContent = analytics.incidentMessage;

    if (insRecoList) {
        insRecoList.innerHTML = analytics.recommendations
            .map((item, idx) => `<div class="ins-reco-item">${idx + 1}. ${item}</div>`)
            .join("");
    }
}

function buildSmartCityAnalytics(pred, forecastHours, routes) {
    const thresholds = pred.thresholds || { moderate: 450, high: 950, very_high: 1550 };
    const safeHours = Array.isArray(forecastHours) ? forecastHours : [];
    const next3 = safeHours.slice(0, 3);
    const next3Avg = next3.length ? next3.reduce((sum, h) => sum + (h.volume || 0), 0) / next3.length : pred.volume;
    const meanDayVolume = safeHours.length ? safeHours.reduce((sum, h) => sum + (h.volume || 0), 0) / safeHours.length : pred.volume;

    const weatherPenalty = { Clear: 0, Clouds: 4, Rain: 12, Fog: 16, Thunderstorm: 20, Drizzle: 8 };
    const weatherHit = weatherPenalty[pred.inputs.weather] || 0;
    const peakHit = pred.is_peak ? 12 : 0;
    const anomalyHit = pred.is_anomaly ? 18 : 0;
    const saturation = Math.min(1, pred.volume / Math.max(1, thresholds.very_high));
    const trendPressure = Math.max(0, (next3Avg - pred.volume) / Math.max(1, thresholds.high)) * 25;
    const accidentRisk = Math.min(100, Math.round(28 + saturation * 38 + weatherHit + peakHit + anomalyHit + trendPressure));

    const congestionRatio = pred.volume / Math.max(1, thresholds.high);
    const hotspotSeverity = congestionRatio >= 1.25 ? "Critical" : congestionRatio >= 1 ? "High" : congestionRatio >= 0.7 ? "Moderate" : "Low";
    const hotspotSeverityColor = hotspotSeverity === "Critical" ? "#ff4d4d" : hotspotSeverity === "High" ? "#f5a623" : hotspotSeverity === "Moderate" ? "#4d9fff" : "#10d97e";
    const hotspotMessage = `${pred.inputs.junction_id.replace("J0", "J").replace("_", " ")} operating at ${Math.round(congestionRatio * 100)}% load ratio`;

    const next3hDelayMin = Math.max(2, Math.round((next3Avg / Math.max(1, thresholds.moderate)) * 4));
    const delayMessage = next3Avg > meanDayVolume ? "Forecast above daily baseline; expect queue spillovers." : "Forecast near baseline; manageable queue lengths.";

    const emissionLoadIndex = Math.min(100, Math.round((pred.volume / 22) + weatherHit + (pred.is_peak ? 8 : 0)));
    const emissionMessage = emissionLoadIndex >= 70 ? "High stop-go emissions expected; optimize phasing and reroute heavy vehicles." : "Emission pressure stable for current network state.";

    const signalCycleSeconds = Math.max(70, Math.min(160, Math.round(75 + saturation * 65 + (pred.is_peak ? 10 : 0))));
    const signalCycle = `${signalCycleSeconds}s cycle`;
    const signalMessage = pred.is_peak ? "Extend arterial green split for peak inbound approach." : "Use balanced split with adaptive side-road release.";

    const bestRoute = Array.isArray(routes) && routes.length ? routes[0] : null;
    const incidentReadinessScore = Math.min(100, Math.round(accidentRisk * 0.6 + (bestRoute ? Math.max(0, 30 - bestRoute.eta_min) : 18)));
    const incidentReadiness = incidentReadinessScore >= 70 ? "High Alert" : incidentReadinessScore >= 45 ? "Prepared" : "Routine";
    const incidentColor = incidentReadiness === "High Alert" ? "#ff4d4d" : incidentReadiness === "Prepared" ? "#f5a623" : "#10d97e";
    const incidentMessage = bestRoute
        ? `Nearest diversion via Route ${bestRoute.id} in ~${bestRoute.eta_min} min.`
        : "Route engine unavailable; maintain default patrol readiness.";

    const accidentRiskText = accidentRisk >= 75
        ? "Elevated conflict probability; deploy enforcement and warning signage."
        : accidentRisk >= 50
            ? "Moderate risk; monitor lane discipline and merge behavior."
            : "Low risk; continue normal surveillance.";

    const recommendations = [
        accidentRisk >= 70
            ? "Trigger variable-message sign warning for overspeed and sudden braking zones."
            : "Keep adaptive monitoring active with current response plan.",
        next3Avg > meanDayVolume
            ? "Pre-stage traffic police at this junction for the next 30-45 minutes."
            : "Maintain current officer allocation and monitor for abrupt spikes.",
        emissionLoadIndex >= 70
            ? "Apply green-wave priority on main corridor to reduce idle emissions."
            : "No special emission controls needed right now.",
        bestRoute
            ? `Publish Route ${bestRoute.id} as preferred diversion in navigation advisory.`
            : "Keep baseline route advisory active until route ranking is available."
    ];

    return {
        accidentRisk,
        accidentRiskText,
        hotspotSeverity,
        hotspotSeverityColor,
        hotspotMessage,
        next3hDelayMin,
        delayMessage,
        emissionLoadIndex,
        emissionMessage,
        signalCycle,
        signalMessage,
        incidentReadiness,
        incidentColor,
        incidentMessage,
        recommendations
    };
}

function renderForecast(hours) {
    const canvas = document.getElementById("c-forecast");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    if (charts.forecast) charts.forecast.destroy();

    charts.forecast = new Chart(ctx, {
        type: "bar",
        data: {
            labels: hours.map((h) => `${h.hour}:00`),
            datasets: [{
                data: hours.map((h) => h.volume),
                backgroundColor: hours.map((h) => h.color),
                borderRadius: 4
            }]
        },
        options: chartDefaults()
    });
}

function initPredictor() {
    const slHr = document.getElementById("sl-hr");
    const lvHr = document.getElementById("lv-hr");
    const slTmp = document.getElementById("sl-tmp");
    const lvTmp = document.getElementById("lv-tmp");

    if (slHr && lvHr) slHr.oninput = () => { lvHr.textContent = `${slHr.value}:00`; };
    if (slTmp && lvTmp) slTmp.oninput = () => { lvTmp.textContent = `${slTmp.value}°C`; };
}

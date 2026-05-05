/* ============================================================
   map.js - Model-backed live traffic map with real road routes
   ============================================================ */

let mapInstance = null;
let mapRefreshTimer = null;
let vehicleTimer = null;
let selectedRouteId = null;
let currentAnalysis = null;
let currentRouteSet = [];
let incidentActive = false;
let emergencyActive = false;

const mapLayers = {
    markers: [],
    routes: [],
    heat: [],
    vehicles: [],
    incident: null
};

const BHOPAL_CENTER = [23.2032, 77.4150];
const FALLBACK_JUNCTIONS = [
    { id: "db_mall", name: "DB Mall", coords: [23.1815, 77.4104] },
    { id: "mp_nagar", name: "MP Nagar", coords: [23.2032, 77.4150] },
    { id: "board_office", name: "Board Office", coords: [23.1844, 77.3944] },
    { id: "hamidia_road", name: "Hamidia Road", coords: [23.1896, 77.4076] },
    { id: "new_market", name: "New Market", coords: [23.1738, 77.4233] },
    { id: "karond", name: "Karond", coords: [23.2332, 77.4272] },
    { id: "ayodhya", name: "Ayodhya Bypass", coords: [23.2599, 77.4977] },
    { id: "bairagarh", name: "Bairagarh", coords: [23.2872, 77.3378] }
];

function initMap() {
    const mapContainer = document.getElementById("map");
    if (!mapContainer) return;

    if (typeof L === "undefined") {
        setTimeout(initMap, 120);
        return;
    }

    enhanceMapTab();

    if (mapInstance) {
        refreshMap();
        return;
    }

    mapInstance = L.map(mapContainer, {
        zoomControl: true,
        attributionControl: true
    }).setView(BHOPAL_CENTER, 13);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "OpenStreetMap",
        maxZoom: 19
    }).addTo(mapInstance);

    setupInputs();
    fetchMapAnalysis({ quiet: true });
    startMapAutoRefresh();
    refreshMap();
}

function enhanceMapTab() {
    const sidebar = document.getElementById("map-sidebar");
    const manualInputs = document.getElementById("map-manual-inputs");
    const mapContainer = document.getElementById("map");
    if (!sidebar || !manualInputs || sidebar.dataset.enhanced === "true") return;

    sidebar.dataset.enhanced = "true";

    const oldToggle = document.getElementById("map-gps-btn")?.parentElement;
    if (oldToggle) oldToggle.style.display = "none";

    manualInputs.innerHTML = `
        <label class="map-field">
            <span>Origin Junction</span>
            <select id="map-origin">${junctionOptions("db_mall")}</select>
        </label>
        <label class="map-field">
            <span>Destination Junction</span>
            <select id="map-destination">${junctionOptions("mp_nagar")}</select>
        </label>
        <div class="map-field-grid">
            <label class="map-field">
                <span>Model Scenario</span>
                <select id="map-scenario">
                    <option value="current">Current model time</option>
                    <option value="morning">Morning peak</option>
                    <option value="evening">Evening peak</option>
                    <option value="rain">Rain impact</option>
                    <option value="fog">Fog impact</option>
                </select>
            </label>
            <label class="map-field">
                <span>Map View</span>
                <select id="map-view-mode">
                    <option value="traffic">Traffic load</option>
                    <option value="emission">CO2 impact</option>
                </select>
            </label>
        </div>
        <button id="map-go-btn" type="button">Analyze Real Route</button>
    `;

    sidebar.insertAdjacentHTML("beforeend", `
        <div class="map-section">
            <div class="map-section-title">Analyzed Route Options</div>
            <div id="map-route-options" class="route-options"></div>
        </div>
        <div class="map-section">
            <div class="map-section-title">Model Recommendation</div>
            <div id="map-ai-panel" class="ai-action-panel">Run route analysis to generate actions.</div>
        </div>
        <div class="map-section">
            <div class="map-section-title">Control Actions</div>
            <div class="map-action-row">
                <button id="map-incident-btn" type="button">Simulate Incident</button>
                <button id="map-emergency-btn" type="button">Emergency Priority</button>
            </div>
        </div>
        <div class="map-section">
            <div class="map-section-title">Legend</div>
            <div class="map-legend">
                <span><i class="lg green"></i>Low model load</span>
                <span><i class="lg yellow"></i>Moderate load</span>
                <span><i class="lg red"></i>High load</span>
                <span><i class="lg purple"></i>Emergency</span>
                <span><i class="lg dark"></i>Incident</span>
            </div>
        </div>
    `);

    if (mapContainer && !document.getElementById("map-toast")) {
        mapContainer.insertAdjacentHTML("beforeend", `
            <div id="map-toast" class="map-toast"></div>
            <div class="map-overlay-card">
                <span>Active Route</span>
                <strong id="map-route-label">Waiting for model analysis</strong>
            </div>
        `);
    }
}

function junctionOptions(selectedId) {
    return FALLBACK_JUNCTIONS.map((j) => (
        `<option value="${j.id}" ${j.id === selectedId ? "selected" : ""}>${j.name}</option>`
    )).join("");
}

function setupInputs() {
    const goBtn = document.getElementById("map-go-btn");
    const scenario = document.getElementById("map-scenario");
    const viewMode = document.getElementById("map-view-mode");
    const incidentBtn = document.getElementById("map-incident-btn");
    const emergencyBtn = document.getElementById("map-emergency-btn");
    const origin = document.getElementById("map-origin");
    const destination = document.getElementById("map-destination");

    if (goBtn) goBtn.onclick = () => fetchMapAnalysis();
    if (scenario) scenario.onchange = () => fetchMapAnalysis({ quiet: true });
    if (origin) origin.onchange = () => fetchMapAnalysis({ quiet: true });
    if (destination) destination.onchange = () => fetchMapAnalysis({ quiet: true });
    if (viewMode) viewMode.onchange = () => redrawCurrentRouteSet();

    if (incidentBtn) {
        incidentBtn.onclick = () => {
            incidentActive = !incidentActive;
            incidentBtn.classList.toggle("active", incidentActive);
            fetchMapAnalysis({ quiet: true }).then(() => {
                toast(incidentActive ? "Incident included in model route analysis." : "Incident removed from analysis.");
            });
        };
    }

    if (emergencyBtn) {
        emergencyBtn.onclick = () => {
            emergencyActive = !emergencyActive;
            emergencyBtn.classList.toggle("active", emergencyActive);
            selectedRouteId = emergencyActive ? "emergency" : null;
            fetchMapAnalysis({ quiet: true }).then(() => {
                toast(emergencyActive ? "Emergency corridor prioritized." : "Emergency priority disabled.");
            });
        };
    }
}

function startMapAutoRefresh() {
    if (mapRefreshTimer) clearInterval(mapRefreshTimer);
    mapRefreshTimer = setInterval(() => {
        const mapPage = document.getElementById("p-map");
        if (mapPage?.classList.contains("on")) fetchMapAnalysis({ quiet: true });
    }, 30000);
}

async function fetchMapAnalysis(options = {}) {
    const origin = document.getElementById("map-origin")?.value;
    const destination = document.getElementById("map-destination")?.value;
    const scenario = document.getElementById("map-scenario")?.value || "current";
    const goBtn = document.getElementById("map-go-btn");

    if (!origin || !destination) return;
    if (origin === destination) {
        toast("Choose two different junctions.", "error");
        return;
    }

    try {
        setMapStatus("Model analyzing...");
        if (goBtn) goBtn.disabled = true;

        const analysis = await apiPost("/api/map-analysis", {
            origin,
            destination,
            scenario,
            incident: incidentActive,
            emergency: emergencyActive
        });
        if (analysis.status !== "success") throw new Error(analysis.message || "Map analysis failed.");

        currentAnalysis = analysis;
        selectedRouteId = selectedRouteId || analysis.recommended_route_id;
        if (emergencyActive) selectedRouteId = "emergency";

        currentRouteSet = await hydrateRealRouteGeometry(analysis.routes);
        drawJunctionHeatmap(analysis.junctions);
        redrawCurrentRouteSet();
        updateSidebar(analysis.summary);
        updateAlertBanner(analysis.summary, analysis.scenario);
        setMapStatus("Model live");
        if (!options.quiet) toast("Model analysis and road route updated.");
    } catch (err) {
        console.error("Map analysis error:", err);
        setMapStatus("Error");
        if (!options.quiet) toast(err.message || "Map analysis failed.", "error");
    } finally {
        if (goBtn) goBtn.disabled = false;
    }
}

async function hydrateRealRouteGeometry(routes) {
    const hydrated = [];
    for (const route of routes) {
        const realPoints = await fetchOsrmGeometry(route.waypoints);
        hydrated.push({
            ...route,
            points: realPoints || route.waypoints,
            geometry_source: realPoints ? "OSRM road route" : "Fallback waypoint route"
        });
    }
    return hydrated;
}

async function fetchOsrmGeometry(waypoints) {
    if (!Array.isArray(waypoints) || waypoints.length < 2) return null;
    const coords = waypoints.map(([lat, lng]) => `${lng},${lat}`).join(";");
    const url = `https://router.project-osrm.org/route/v1/driving/${coords}?overview=full&geometries=geojson&alternatives=false&steps=false`;

    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 6500);
        const response = await fetch(url, { signal: controller.signal });
        clearTimeout(timeout);
        if (!response.ok) return null;

        const data = await response.json();
        const coordinates = data?.routes?.[0]?.geometry?.coordinates;
        if (!Array.isArray(coordinates) || !coordinates.length) return null;
        return coordinates.map(([lng, lat]) => [lat, lng]);
    } catch (_) {
        return null;
    }
}

function redrawCurrentRouteSet() {
    if (!mapInstance || !currentRouteSet.length) return;

    clearLayerList(mapLayers.routes);
    clearLayerList(mapLayers.markers);
    clearLayerList(mapLayers.vehicles);
    if (mapLayers.incident) {
        mapLayers.incident.remove();
        mapLayers.incident = null;
    }

    renderRouteCards();
    const viewMode = document.getElementById("map-view-mode")?.value || "traffic";
    const activeRoute = currentRouteSet.find((route) => route.id === selectedRouteId)
        || currentRouteSet.find((route) => route.id === currentAnalysis?.recommended_route_id)
        || currentRouteSet[0];

    currentRouteSet.forEach((route) => {
        const active = route.id === activeRoute.id;
        const color = route.id === "emergency" ? "#9b6dff" : viewMode === "emission" ? emissionColor(route.co2_grams) : statusColor(route.status_color);
        const line = L.polyline(route.points, {
            color,
            weight: active ? 7 : 4,
            opacity: active ? 0.95 : 0.42,
            dashArray: route.id === "emergency" ? "8,8" : null,
            lineCap: "round"
        }).addTo(mapInstance);
        line.bindPopup(`${route.name}<br>${route.eta_min} min | ${route.geometry_source}`);
        line.on("click", () => {
            selectedRouteId = route.id;
            redrawCurrentRouteSet();
        });
        mapLayers.routes.push(line);
    });

    const first = activeRoute.points[0];
    const last = activeRoute.points[activeRoute.points.length - 1];
    mapLayers.markers.push(L.marker(first, { icon: makePinIcon("origin") }).bindPopup(currentAnalysis.origin.name).addTo(mapInstance));
    mapLayers.markers.push(L.marker(last, { icon: makePinIcon("destination") }).bindPopup(currentAnalysis.destination.name).addTo(mapInstance));

    if (incidentActive) drawIncident(activeRoute);
    drawVehicles(activeRoute);
    updateAiPanel(activeRoute);
    updateRouteLabel(activeRoute);
    refreshMap();
}

function drawJunctionHeatmap(junctions = currentAnalysis?.junctions || []) {
    if (!mapInstance) return;
    clearLayerList(mapLayers.heat);

    junctions.forEach((junction) => {
        const color = junction.color || statusColor(junction.load_index < 35 ? "GREEN" : junction.load_index < 65 ? "YELLOW" : "RED");
        const circle = L.circle(junction.coords, {
            radius: 220 + junction.load_index * 5,
            color,
            fillColor: color,
            fillOpacity: 0.16,
            weight: 1
        }).bindPopup(`<strong>${junction.name}</strong><br>Model volume: ${junction.volume} veh/hr<br>${junction.level}`).addTo(mapInstance);
        mapLayers.heat.push(circle);
    });
}

function renderRouteCards() {
    const box = document.getElementById("map-route-options");
    if (!box) return;

    box.innerHTML = currentRouteSet.map((route) => `
        <button class="map-route-card ${route.id === selectedRouteId ? "active" : ""}" data-route-id="${route.id}" type="button">
            <span>
                <strong>${route.name}</strong>
                <small>${route.distance_km} km | ${route.avg_speed_kmh} km/h | ${route.geometry_source}</small>
            </span>
            <span>
                <b style="color:${route.id === "emergency" ? "#9b6dff" : statusColor(route.status_color)}">${route.eta_min}m</b>
                <small>${route.co2_grams}g CO2</small>
            </span>
        </button>
    `).join("");

    box.querySelectorAll("[data-route-id]").forEach((btn) => {
        btn.onclick = () => {
            selectedRouteId = btn.dataset.routeId;
            redrawCurrentRouteSet();
        };
    });
}

function drawIncident(route) {
    const point = route.points[Math.floor(route.points.length * 0.55)] || route.points[0];
    mapLayers.incident = L.marker(point, {
        icon: L.divIcon({
            className: "",
            html: `<div class="incident-marker">!</div>`,
            iconSize: [26, 26],
            iconAnchor: [13, 13]
        })
    }).bindPopup("Simulated incident included in model analysis").addTo(mapInstance);
}

function drawVehicles(route) {
    clearLayerList(mapLayers.vehicles);
    if (vehicleTimer) clearInterval(vehicleTimer);

    const count = route.status_color === "RED" ? 10 : 6;
    const vehicles = Array.from({ length: count }, (_, index) => ({
        progress: index / count,
        marker: L.circleMarker(route.points[0], {
            radius: 4,
            color: "#ffffff",
            fillColor: route.id === "emergency" ? "#9b6dff" : statusColor(route.status_color),
            fillOpacity: 1,
            weight: 1
        }).addTo(mapInstance)
    }));

    mapLayers.vehicles = vehicles.map((v) => v.marker);
    vehicleTimer = setInterval(() => {
        vehicles.forEach((vehicle) => {
            vehicle.progress = (vehicle.progress + (route.status_color === "RED" ? 0.006 : 0.012)) % 1;
            vehicle.marker.setLatLng(pointOnRoute(route.points, vehicle.progress));
        });
    }, 600);
}

function updateSidebar(summary) {
    setText("traffic-eta", `${summary.live_eta_mins} min`);
    setText("traffic-delay", `${summary.delay_mins} min`);
    setText("traffic-carbon", `${summary.carbon_extra_grams}g CO2`);

    const statusEl = document.getElementById("traffic-status");
    if (statusEl) {
        statusEl.textContent = summary.status_color;
        statusEl.style.color = statusColor(summary.status_color);
    }
}

function updateAlertBanner(summary, scenario) {
    const banner = document.getElementById("traffic-alert-banner");
    const alertText = document.getElementById("traffic-alert-text");
    const alertDesc = document.getElementById("traffic-alert-desc");
    if (!banner || !alertText || !alertDesc) return;

    const message = summary.status_color === "GREEN"
        ? "Model indicates smooth traffic for selected road route."
        : summary.status_color === "YELLOW"
            ? "Model indicates moderate congestion; monitor junction load."
            : "Model indicates heavy congestion; alternate route recommended.";

    const color = statusColor(summary.status_color);
    banner.style.display = "block";
    banner.style.borderLeft = `4px solid ${color}`;
    banner.style.background = `${color}22`;
    alertText.textContent = message;
    alertDesc.textContent = `${scenario.label} | ${summary.recommended_route} | Avg volume ${summary.avg_volume} veh/hr`;
}

function updateAiPanel(route) {
    const panel = document.getElementById("map-ai-panel");
    if (!panel || !currentAnalysis) return;

    const scenario = currentAnalysis.scenario;
    const signalBoost = route.status_color === "RED" ? 24 : route.status_color === "YELLOW" ? 14 : 6;
    const police = route.status_color === "RED" ? "Deploy 2 officers at destination junction." : "Keep patrol on standby.";
    const weather = ["Rain", "Fog"].includes(scenario.weather)
        ? `${scenario.weather} selected: reduce speed advisory and extend amber clearance.`
        : "Weather impact normal.";
    const emergency = emergencyActive
        ? "Emergency corridor selected; priority signal plan active."
        : "Emergency priority inactive.";

    panel.innerHTML = `
        <div><b>Data source:</b> ML model junction volumes + OSRM road geometry.</div>
        <div><b>Recommendation:</b> Use ${route.name}.</div>
        <div><b>Signal timing:</b> Extend green by ${signalBoost}s near high-load junctions.</div>
        <div><b>Operations:</b> ${police}</div>
        <div><b>Weather:</b> ${weather}</div>
        <div><b>Emergency:</b> ${emergency}</div>
    `;
}

function updateRouteLabel(route) {
    const label = document.getElementById("map-route-label");
    if (!label || !currentAnalysis) return;
    label.textContent = `${currentAnalysis.origin.name} to ${currentAnalysis.destination.name} | ${route.name}`;
}

function refreshMap() {
    if (!mapInstance) return;
    setTimeout(() => {
        mapInstance.invalidateSize();
        const boundsLayers = [...mapLayers.markers, ...mapLayers.routes];
        if (boundsLayers.length) {
            const group = L.featureGroup(boundsLayers);
            mapInstance.fitBounds(group.getBounds().pad(0.16));
        }
    }, 80);
}

function pointOnRoute(points, progress) {
    if (!points.length) return BHOPAL_CENTER;
    const segments = [];
    let total = 0;
    for (let i = 0; i < points.length - 1; i += 1) {
        const length = haversineKm(points[i], points[i + 1]);
        segments.push({ a: points[i], b: points[i + 1], length });
        total += length;
    }

    let distance = progress * total;
    for (const segment of segments) {
        if (distance <= segment.length) {
            const ratio = segment.length ? distance / segment.length : 0;
            return [
                segment.a[0] + (segment.b[0] - segment.a[0]) * ratio,
                segment.a[1] + (segment.b[1] - segment.a[1]) * ratio
            ];
        }
        distance -= segment.length;
    }
    return points[points.length - 1];
}

function haversineKm(a, b) {
    const r = 6371;
    const dLat = toRad(b[0] - a[0]);
    const dLon = toRad(b[1] - a[1]);
    const lat1 = toRad(a[0]);
    const lat2 = toRad(b[0]);
    const x = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
    return r * 2 * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
}

function toRad(value) {
    return value * Math.PI / 180;
}

function makePinIcon(type) {
    return L.divIcon({
        className: "",
        html: `<div class="map-pin ${type}"></div>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9]
    });
}

function statusColor(status) {
    if (status === "GREEN") return "#10d97e";
    if (status === "YELLOW") return "#f5a623";
    if (status === "PURPLE") return "#9b6dff";
    return "#ff4d4d";
}

function emissionColor(co2) {
    if (co2 < 80) return "#10d97e";
    if (co2 < 180) return "#f5a623";
    return "#ff4d4d";
}

function clearLayerList(list) {
    list.forEach((layer) => layer.remove());
    list.length = 0;
}

function setMapStatus(text) {
    let el = document.getElementById("map-sync-status");
    if (!el) {
        const header = document.querySelector("#map-sidebar .pnl-hd");
        if (header) {
            header.insertAdjacentHTML("beforeend", `<div id="map-sync-status" class="map-sync-status"></div>`);
            el = document.getElementById("map-sync-status");
        }
    }
    if (el) el.textContent = text;
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function toast(message, type = "ok") {
    const el = document.getElementById("map-toast");
    if (!el) return;
    el.textContent = message;
    el.className = `map-toast show ${type}`;
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => el.classList.remove("show"), 2800);
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("p-map")?.classList.contains("on")) initMap();
});

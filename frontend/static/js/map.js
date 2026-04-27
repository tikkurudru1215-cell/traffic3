/* ============================================================
   map.js - Leaflet live rerouting map + GPS simulation
   College project upgrades: live vehicles, incidents, heat layer,
   dynamic reranking, and control room logs.
   ============================================================ */

let _map;
let _routeLayers = [];
let _juncMarkers = {};

let _gpsMarker = null;
let _gpsTail = null;
let _gpsRunning = false;
let _gpsStep = 0;
let _gpsInt = null;

let _selRoute = 0;
let _mapLiveInt = null;
let _vehicleInt = null;

let _currentRoutes = [];
let _currentJunctions = [];
let _incidents = [];
let _liveVehicles = [];
let _vehicleLayers = {};
let _controlLog = [];

const SEVERITY_WEIGHT = { LOW: 2, MEDIUM: 5, HIGH: 9 };
const SEVERITY_COLOR = { LOW: "#f5a623", MEDIUM: "#f97316", HIGH: "#ff4d4d" };

// GPS simulation path (follows Route A, drifts off, returns)
const GPS_SIM = [
  { lat: 23.2332, lon: 77.4272, note: "Start - DB Mall Chowk" },
  { lat: 23.2322, lon: 77.4285, note: "Moving north on road" },
  { lat: 23.2313, lon: 77.43, note: "On route - all clear" },
  { lat: 23.2308, lon: 77.4318, note: "Approaching Zone-I" },
  { lat: 23.2295, lon: 77.43, note: "Slight westward drift" },
  { lat: 23.2278, lon: 77.4275, note: "Wrong turn taken" },
  { lat: 23.2265, lon: 77.4305, note: "Recalculating route" },
  { lat: 23.2278, lon: 77.434, note: "Merging back to route" },
  { lat: 23.229, lon: 77.4362, note: "Back on planned route" },
  { lat: 23.2299, lon: 77.4382, note: "Arrived - MP Nagar" }
];

// Haversine distance (meters)
function haversineM(la1, lo1, la2, lo2) {
  const R = 6371000;
  const p1 = la1 * Math.PI / 180;
  const p2 = la2 * Math.PI / 180;
  const dp = (la2 - la1) * Math.PI / 180;
  const dl = (lo2 - lo1) * Math.PI / 180;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function nowStamp() {
  return new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function appendControlLog(message, color = "#4d9fff") {
  _controlLog.unshift({ t: nowStamp(), message, color });
  _controlLog = _controlLog.slice(0, 24);
  renderControlLog();
}

function renderControlLog() {
  const box = document.getElementById("gps-log-scroll");
  if (!box) return;

  box.innerHTML = _controlLog.map((row) => `
    <div class="gl">
      <span class="gl-dot" style="background:${row.color}"></span>
      <span class="gl-desc">[${row.t}] ${row.message}</span>
      <span class="gl-s" style="background:${row.color}1a;color:${row.color}">LIVE</span>
    </div>
  `).join("");
}

/* -- Init Map ------------------------------------------------ */
function initMap() {
  _map = L.map("leaflet-map", {
    center: [23.235, 77.415],
    zoom: 13,
    zoomControl: true,
    attributionControl: false
  });

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
    subdomains: "abcd"
  }).addTo(_map);

  L.control.attribution({ prefix: "(c) OpenStreetMap - CartoDB" }).addTo(_map);

  ["map-h", "map-d", "map-w"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", refreshMap);
  });

  refreshMap();
  startLiveLoops();
  appendControlLog("Live map initialized", "#10d97e");
}

function startLiveLoops() {
  if (_mapLiveInt) clearInterval(_mapLiveInt);
  if (_vehicleInt) clearInterval(_vehicleInt);

  _mapLiveInt = setInterval(() => {
    if (document.getElementById("p-map")?.classList.contains("on")) {
      refreshMap(true);
    }
  }, 9000);

  _vehicleInt = setInterval(() => {
    if (document.getElementById("p-map")?.classList.contains("on")) {
      tickLiveVehicles();
    }
  }, 2200);
}

/* -- Refresh map data --------------------------------------- */
async function refreshMap(silent = false) {
  clearMapLayers();

  const hour = +document.getElementById("map-h").value;
  const dow = +document.getElementById("map-d").value;
  const weather = document.getElementById("map-w").value;
  const month = new Date().getMonth() + 1;

  const dayN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  document.getElementById("map-meta").textContent = `${dayN[dow]} ${hour}:00 - ${weather}`;

  try {
    const [routeData, juncData] = await Promise.all([
      apiPost("/api/routes", { hour, day_of_week: dow, month, weather }),
      apiGet(`/api/junctions?hour=${hour}&day_of_week=${dow}&month=${month}&weather=${weather}`)
    ]);

    const adjusted = buildDynamicScenario(routeData.routes || [], juncData.junctions || []);
    _currentRoutes = adjusted.routes;
    _currentJunctions = adjusted.junctions;

    if (_selRoute >= _currentRoutes.length) _selRoute = 0;

    drawRoutes(_currentRoutes);
    drawJunctions(_currentJunctions);
    drawIncidents();
    renderMapSidebar(_currentRoutes);

    if (_currentRoutes[0]) {
      updateOverlays(_currentRoutes[0]);
      if (!silent) {
        appendControlLog(
          `Route ${_currentRoutes[0].id} recommended (${_currentRoutes[0].est_time} min, ${_currentRoutes[0].level})`,
          _currentRoutes[0].color
        );
      }
    }

    if (!_liveVehicles.length) initLiveVehicles();
  } catch (e) {
    console.error("Map refresh:", e);
    appendControlLog("Map refresh failed - using previous state", "#ff4d4d");
  }
}

function buildDynamicScenario(routes, junctions) {
  const clonedRoutes = routes.map((r) => ({ ...r, waypoints: (r.waypoints || []).map((p) => [p[0], p[1]]) }));
  const clonedJunc = junctions.map((j) => ({ ...j }));

  // Dynamic route scoring with incident penalties + mild random variation.
  clonedRoutes.forEach((r) => {
    const incidentPenalty = incidentImpactForRoute(r.waypoints, _incidents);
    const randomPulse = Math.random() * 1.8;
    const baseTime = Number(r.est_time || 0);
    const eta = Math.max(3, Math.round(baseTime + incidentPenalty + randomPulse));
    r.eta_min = eta;
    r.est_time = eta;

    const c = classifyVolume(r.avg_volume || 0);
    r.level = c.level;
    r.color = c.color;

    const volumeScore = (r.avg_volume || 0) / 120;
    r.score = +(volumeScore + eta * 3 + incidentPenalty * 2).toFixed(1);
  });

  clonedRoutes.sort((a, b) => a.score - b.score);
  clonedRoutes.forEach((r, idx) => {
    r.recommended = idx === 0;
    if (idx === 0) {
      r.color = "#10d97e";
      r.level = "BEST";
    }
  });

  // Heat adjustments near incidents.
  clonedJunc.forEach((j) => {
    const near = nearestIncidentDistance(j.lat, j.lon, _incidents);
    let boosted = j.volume;
    if (near < 600) boosted = Math.round(boosted * 1.18);
    if (near < 320) boosted = Math.round(boosted * 1.35);
    j.volume = boosted;

    const c = classifyVolume(j.volume || 0);
    j.level = c.level;
    j.color = c.color;
  });

  return { routes: clonedRoutes, junctions: clonedJunc };
}

function incidentImpactForRoute(waypoints, incidents) {
  if (!waypoints?.length || !incidents?.length) return 0;
  let penalty = 0;
  incidents.forEach((inc) => {
    const minD = Math.min(...waypoints.map((w) => haversineM(w[0], w[1], inc.lat, inc.lon)));
    if (minD < 900) penalty += SEVERITY_WEIGHT[inc.severity] || 0;
    if (minD < 350) penalty += 2;
  });
  return penalty;
}

function nearestIncidentDistance(lat, lon, incidents) {
  if (!incidents.length) return Number.POSITIVE_INFINITY;
  return Math.min(...incidents.map((inc) => haversineM(lat, lon, inc.lat, inc.lon)));
}

/* -- Draw route polylines ----------------------------------- */
function drawRoutes(routes) {
  routes.forEach((r, rank) => {
    const isRec = r.recommended;
    const isActive = rank === _selRoute;
    const col = isRec ? "#10d97e" : isActive ? "#4d9fff" : "#3a4860";
    const wt = isActive ? 7 : 4;
    const op = isActive ? 1.0 : 0.55;
    const dash = isActive ? null : "8,5";

    const pl = L.polyline(r.waypoints, {
      color: col,
      weight: wt,
      opacity: op,
      dashArray: dash,
      lineCap: "round",
      lineJoin: "round"
    }).addTo(_map);

    pl.on("click", () => {
      _selRoute = rank;
      appendControlLog(`Operator selected Route ${r.id}`, "#4d9fff");
      refreshMap(true);
    });

    _routeLayers.push(pl);

    if (isActive || isRec) {
      r.waypoints.forEach((pt, i) => {
        if (i === 0 || i === r.waypoints.length - 1) return;
        const prev = r.waypoints[i - 1];
        const next = r.waypoints[i + 1];
        const angle = Math.atan2(next[1] - prev[1], next[0] - prev[0]) * 180 / Math.PI;

        const icon = L.divIcon({
          className: "",
          html: `<div style="color:${col};font-size:11px;transform:rotate(${angle}deg);opacity:.85;line-height:1">&#9654;</div>`,
          iconSize: [11, 11],
          iconAnchor: [6, 6]
        });

        const m = L.marker(pt, { icon, interactive: false, zIndexOffset: 90 }).addTo(_map);
        _routeLayers.push(m);
      });
    }
  });

  addPin([23.2332, 77.4272], "#10d97e", "S", "Origin - DB Mall Chowk");
  addPin([23.2299, 77.4382], "#ff4d4d", "E", "Destination - MP Nagar");
}

/* -- Draw junctions + heat ---------------------------------- */
function drawJunctions(junctions) {
  junctions.forEach((j) => {
    const r = Math.max(13, Math.min(25, (j.volume || 0) / 70));

    const icon = L.divIcon({
      className: "",
      html: `<div style="
        width:${r * 2}px;height:${r * 2}px;border-radius:50%;
        background:${j.color}22;border:2px solid ${j.color};
        display:flex;align-items:center;justify-content:center;
        font-family:'Space Mono',monospace;font-size:9px;color:${j.color};font-weight:700;
        box-shadow:0 0 14px ${j.color}55;cursor:pointer;transition:transform .2s"
      >${Math.round((j.volume || 0) / 100) / 10}k</div>`,
      iconSize: [r * 2, r * 2],
      iconAnchor: [r, r]
    });

    const mk = L.marker([j.lat, j.lon], { icon }).addTo(_map);

    // Heat aura layer for quick congestion visualization.
    const heat = L.circle([j.lat, j.lon], {
      radius: Math.max(80, Math.min(220, (j.volume || 0) / 8)),
      color: j.color,
      fillColor: j.color,
      fillOpacity: 0.1,
      weight: 1
    }).addTo(_map);

    mk.bindPopup(`
      <div class="jp-title">${j.name}</div>
      <div class="jp-row"><span>Predicted Volume</span><span class="jp-val" style="color:${j.color}">${(j.volume || 0).toLocaleString()} veh/hr</span></div>
      <div class="jp-row"><span>Traffic Level</span><span class="jp-val" style="color:${j.color}">${j.level}</span></div>
      <div class="jp-row"><span>Junction ID</span><span class="jp-val">${j.id}</span></div>
      <div class="jp-row"><span>Coordinates</span><span class="jp-val">${j.lat.toFixed(4)}N, ${j.lon.toFixed(4)}E</span></div>
    `, { className: "junc-popup", maxWidth: 260 });

    _juncMarkers[j.id] = mk;
    _routeLayers.push(mk, heat);
  });
}

function drawIncidents() {
  _incidents.forEach((inc) => {
    const color = SEVERITY_COLOR[inc.severity] || "#ff4d4d";
    const icon = L.divIcon({
      className: "",
      html: `<div title="${inc.note}" style="
        width:22px;height:22px;border-radius:50%;
        background:${color};border:2px solid #ffffff;
        box-shadow:0 0 14px ${color}aa;
        display:flex;align-items:center;justify-content:center;
        font-size:12px;font-weight:700;color:#fff">!</div>`,
      iconSize: [22, 22],
      iconAnchor: [11, 11]
    });

    const m = L.marker([inc.lat, inc.lon], { icon, zIndexOffset: 1200 }).addTo(_map);
    m.bindPopup(`
      <div class="jp-title">Incident (${inc.severity})</div>
      <div class="jp-row"><span>Time</span><span class="jp-val">${inc.ts}</span></div>
      <div class="jp-row"><span>Details</span><span class="jp-val">${inc.note}</span></div>
    `, { className: "junc-popup", maxWidth: 250 });

    _routeLayers.push(m);
  });
}

function addPin(latlng, color, label, title) {
  const icon = L.divIcon({
    className: "",
    html: `<div title="${title}" style="
      width:28px;height:28px;border-radius:50% 50% 50% 0;
      transform:rotate(-45deg);background:${color};
      border:3px solid #fff;box-shadow:0 3px 12px rgba(0,0,0,.6)">
    </div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 28]
  });

  const m = L.marker(latlng, { icon, zIndexOffset: 500 }).addTo(_map);
  m.bindTooltip(title, { permanent: false, direction: "top", offset: [0, -30], className: "junc-popup" });
  _routeLayers.push(m);
}

function clearMapLayers() {
  _routeLayers.forEach((l) => l.remove());
  _routeLayers = [];
  _juncMarkers = {};

  Object.values(_vehicleLayers).forEach((m) => m.remove());
  _vehicleLayers = {};
}

/* -- Sidebar route cards ------------------------------------ */
function renderMapSidebar(routes) {
  const container = document.getElementById("map-route-cards");
  if (!container) return;

  container.innerHTML = routes.map((r, rank) => {
    const c = classifyVolume(r.avg_volume || 0);
    const pct = Math.min(100, ((r.avg_volume || 0) / 2000) * 100);
    const col = r.recommended ? "#10d97e" : rank === _selRoute ? "#4d9fff" : "#3a4860";

    return `<div class="route-card ${r.recommended ? "best" : ""} ${rank === _selRoute ? "active" : ""}"
                 onclick="selectMapRoute(${rank})">
      <div style="position:absolute;left:0;top:0;bottom:0;width:3px;border-radius:3px 0 0 3px;background:${col}"></div>
      <div class="rc-top">
        <div>
          <div class="rc-name">${r.name}</div>
          <div class="rc-meta">${r.km}km - dynamic score ${r.score}</div>
        </div>
        <div style="text-align:right;flex-shrink:0;margin-left:10px">
          <div class="rc-time" style="color:${r.color}">${r.est_time}</div>
          <div class="rc-tu">min</div>
        </div>
      </div>
      <div class="rc-bar"><div class="rc-fill" style="width:${pct}%;background:${r.color}"></div></div>
      <div class="rc-bot">
        <span class="badge ${c.cls}">${(r.avg_volume || 0).toLocaleString()} veh/hr - ${r.level}</span>
        ${r.recommended ? '<span class="rec-tag">SMART PICK</span>' : ""}
      </div>
    </div>`;
  }).join("");
}

function selectMapRoute(rank) {
  _selRoute = rank;
  refreshMap(true);
}

function updateOverlays(best) {
  if (!best) return;
  document.getElementById("ov-route").textContent = "Route " + best.id;
  document.getElementById("ov-vol").textContent = (best.avg_volume || 0).toLocaleString();
  document.getElementById("ov-vol").style.color = best.color;
  document.getElementById("ov-time").textContent = best.est_time + " min";
}

/* -- Incident reporting ------------------------------------- */
function reportIncident() {
  if (!_currentRoutes.length) return;

  const severity = document.getElementById("inc-severity")?.value || "MEDIUM";
  const active = _currentRoutes[_selRoute] || _currentRoutes[0];
  const wpts = active.waypoints || [];
  if (wpts.length < 3) return;

  const idx = 1 + Math.floor(Math.random() * (wpts.length - 2));
  const base = wpts[idx];
  const lat = base[0] + ((Math.random() - 0.5) * 0.0014);
  const lon = base[1] + ((Math.random() - 0.5) * 0.0014);

  const incident = {
    id: `INC-${Date.now()}`,
    severity,
    lat,
    lon,
    ts: nowStamp(),
    note: `${severity} accident near Route ${active.id}`
  };

  _incidents.unshift(incident);
  _incidents = _incidents.slice(0, 12);

  appendControlLog(`Incident reported (${severity}) near Route ${active.id}`, SEVERITY_COLOR[severity] || "#ff4d4d");

  if (severity === "HIGH") {
    const bar = document.getElementById("alert-bar");
    bar.className = "alert-bar show hi";
    document.getElementById("alert-txt").textContent = "High severity incident detected - rerouting traffic";
    document.getElementById("alert-dist").textContent = "control-room alert";
  }

  refreshMap(true);
}

/* -- Live vehicles ------------------------------------------ */
function initLiveVehicles() {
  if (!_currentRoutes.length) return;

  _liveVehicles = [];
  const count = 8;
  for (let i = 0; i < count; i++) {
    const routeIndex = i % _currentRoutes.length;
    _liveVehicles.push({
      id: `V${i + 1}`,
      routeIndex,
      progress: Math.random() * 0.85,
      speed: 26 + Math.random() * 26,
      offRouteTicks: 0,
      headingDeg: 0
    });
  }
  appendControlLog(`${count} live vehicles initialized`, "#10d97e");
}

function tickLiveVehicles() {
  if (!_currentRoutes.length) return;
  if (!_liveVehicles.length) initLiveVehicles();

  _liveVehicles.forEach((v) => {
    const route = _currentRoutes[v.routeIndex % _currentRoutes.length];
    if (!route?.waypoints?.length) return;

    v.progress += (v.speed / 1000) * 0.25;
    if (v.progress > 1) {
      v.progress = 0;
      v.routeIndex = (v.routeIndex + 1) % _currentRoutes.length;
    }

    let point = interpolateOnPath(route.waypoints, v.progress);

    // Simulate occasional wrong movement for realism.
    if (v.offRouteTicks > 0) {
      point = { lat: point.lat + 0.0012, lon: point.lon - 0.0008, headingDeg: point.headingDeg };
      v.offRouteTicks -= 1;
    } else if (Math.random() < 0.03) {
      v.offRouteTicks = 2;
      appendControlLog(`Vehicle ${v.id} temporary route deviation detected`, "#f97316");
    }

    v.headingDeg = point.headingDeg;
    drawVehicle(v, point.lat, point.lon);
  });
}

function drawVehicle(v, lat, lon) {
  const offRoute = v.offRouteTicks > 0;
  const color = offRoute ? "#ff4d4d" : "#4d9fff";

  const icon = L.divIcon({
    className: "",
    html: `<div title="${v.id} | ${Math.round(v.speed)} km/h" style="
      width:16px;height:16px;border-radius:50%;
      background:${color};border:2px solid #fff;
      box-shadow:0 0 10px ${color}aa;
      transform:rotate(${v.headingDeg}deg)"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  });

  if (_vehicleLayers[v.id]) {
    _vehicleLayers[v.id].setLatLng([lat, lon]);
    _vehicleLayers[v.id].setIcon(icon);
  } else {
    _vehicleLayers[v.id] = L.marker([lat, lon], { icon, zIndexOffset: 1000 }).addTo(_map);
  }
}

function interpolateOnPath(path, t) {
  if (path.length === 1) return { lat: path[0][0], lon: path[0][1], headingDeg: 0 };

  const segments = [];
  let total = 0;
  for (let i = 0; i < path.length - 1; i++) {
    const a = path[i], b = path[i + 1];
    const len = haversineM(a[0], a[1], b[0], b[1]);
    segments.push({ a, b, len });
    total += len;
  }

  let dist = t * total;
  for (const seg of segments) {
    if (dist <= seg.len) {
      const r = seg.len === 0 ? 0 : dist / seg.len;
      const lat = seg.a[0] + (seg.b[0] - seg.a[0]) * r;
      const lon = seg.a[1] + (seg.b[1] - seg.a[1]) * r;
      const headingDeg = Math.atan2(seg.b[1] - seg.a[1], seg.b[0] - seg.a[0]) * 180 / Math.PI;
      return { lat, lon, headingDeg };
    }
    dist -= seg.len;
  }

  const last = path[path.length - 1];
  return { lat: last[0], lon: last[1], headingDeg: 0 };
}

/* -- GPS Simulation ----------------------------------------- */
function toggleGPS() {
  _gpsRunning ? stopGPS() : startGPS();
}

function startGPS() {
  _gpsRunning = true;
  _gpsStep = 0;

  const btn = document.getElementById("gps-btn");
  btn.textContent = "Stop Navigation";
  btn.classList.add("running");
  document.getElementById("alert-bar").classList.add("show");

  if (_gpsTail) {
    _gpsTail.remove();
    _gpsTail = null;
  }

  const tracePts = [];
  const routeWpts = [
    [23.2332, 77.4272], [23.2322, 77.4285], [23.2313, 77.43],
    [23.2307, 77.4318], [23.2302, 77.434], [23.2299, 77.4365], [23.2299, 77.4382]
  ];

  appendControlLog("GPS navigation started", "#10d97e");

  _gpsInt = setInterval(async () => {
    if (_gpsStep >= GPS_SIM.length) {
      stopGPS();
      return;
    }

    const pt = GPS_SIM[_gpsStep];
    tracePts.push([pt.lat, pt.lon]);

    try {
      const dev = await apiPost("/api/deviation", { lat: pt.lat, lon: pt.lon, route_id: "A" });
      updateGPSUI(pt, dev, tracePts);
    } catch (e) {
      const dist = Math.round(Math.min(...routeWpts.map((w) => haversineM(pt.lat, pt.lon, w[0], w[1]))));
      const level = dist <= 50 ? "ON_ROUTE" : dist <= 150 ? "LOW" : dist <= 300 ? "MEDIUM" : "HIGH";
      const color = dist <= 50 ? "#10d97e" : dist <= 150 ? "#f5a623" : dist <= 300 ? "#f97316" : "#ff4d4d";
      const msg = dist <= 50 ? "On route - all clear" : dist <= 150 ? "Slight deviation" : dist <= 300 ? "Recalculating" : "Off route! Rerouting";
      updateGPSUI(pt, { distance_m: dist, level, message: msg, color, reroute: dist > 300 }, tracePts);
    }

    _gpsStep++;
  }, 1900);
}

function updateGPSUI(pt, dev, tracePts) {
  if (_gpsMarker) _gpsMarker.remove();

  const gpsIcon = L.divIcon({
    className: "",
    html: `<div style="position:relative;width:22px;height:22px">
      <div style="position:absolute;inset:0;border-radius:50%;background:#4d9fff33;animation:pls 1.5s infinite"></div>
      <div style="position:absolute;inset:3px;border-radius:50%;background:#4d9fff;border:2px solid #fff;box-shadow:0 0 12px #4d9fff88"></div>
    </div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11]
  });

  _gpsMarker = L.marker([pt.lat, pt.lon], { icon: gpsIcon, zIndexOffset: 1000 }).addTo(_map);
  _map.panTo([pt.lat, pt.lon], { animate: true, duration: 0.6 });

  if (_gpsTail) _gpsTail.remove();
  _gpsTail = L.polyline(tracePts, {
    color: dev.color,
    weight: 4,
    dashArray: "6,4",
    opacity: 0.8,
    lineCap: "round"
  }).addTo(_map);

  const bar = document.getElementById("alert-bar");
  const lvlCls = { ON_ROUTE: "ok", LOW: "lo", MEDIUM: "me", HIGH: "hi" }[dev.level] || "ok";
  bar.className = "alert-bar show " + lvlCls;
  document.getElementById("alert-txt").textContent = dev.message;
  document.getElementById("alert-dist").textContent = dev.distance_m + "m from route";

  const badge = { ON_ROUTE: "ON ROUTE", LOW: "LOW ALERT", MEDIUM: "REROUTING", HIGH: "OFF ROUTE" }[dev.level] || "LIVE";
  appendControlLog(`${pt.note} - ${badge} (${dev.distance_m}m)`, dev.color || "#4d9fff");

  if (dev.level === "HIGH") {
    appendControlLog("Wrong route alert issued to driver", "#ff4d4d");
  }
}

function stopGPS() {
  clearInterval(_gpsInt);
  _gpsRunning = false;
  _gpsStep = 0;

  const btn = document.getElementById("gps-btn");
  btn.textContent = "Start GPS Navigation";
  btn.classList.remove("running");

  const bar = document.getElementById("alert-bar");
  bar.className = "alert-bar ok show";
  document.getElementById("alert-txt").textContent = "Navigation ended";
  document.getElementById("alert-dist").textContent = "";

  if (_gpsMarker) {
    _gpsMarker.remove();
    _gpsMarker = null;
  }
  if (_gpsTail) {
    _gpsTail.remove();
    _gpsTail = null;
  }

  appendControlLog("GPS navigation stopped", "#4d9fff");
}

"""
================================================================
  backend/routes.py
  Route Recommendation Engine + GPS Deviation Detection
================================================================
"""
import math

# ── Bhopal Route Definitions ─────────────────────────────────
ROUTES = [
    {
        "id":   "A",
        "name": "Route A — Via DB Mall → MP Nagar",
        "short":"Via DB Mall",
        "km":   4.2,
        "junctions": ["J01_DBMall", "J02_MPNagar"],
        "waypoints": [
            [23.2332, 77.4272], [23.2322, 77.4285], [23.2313, 77.4300],
            [23.2307, 77.4318], [23.2302, 77.4340], [23.2299, 77.4365],
            [23.2299, 77.4382],
        ],
    },
    {
        "id":   "B",
        "name": "Route B — Via Hamidia Road",
        "short":"Via Hamidia Rd",
        "km":   5.8,
        "junctions": ["J01_DBMall", "J03_NewMarket"],
        "waypoints": [
            [23.2332, 77.4272], [23.2340, 77.4200], [23.2348, 77.4120],
            [23.2354, 77.4001], [23.2322, 77.4080], [23.2299, 77.4382],
        ],
    },
    {
        "id":   "C",
        "name": "Route C — Ring Road (Karond)",
        "short":"Via Ring Road",
        "km":   7.1,
        "junctions": ["J04_Karond", "J01_DBMall"],
        "waypoints": [
            [23.2332, 77.4272], [23.2400, 77.4190], [23.2510, 77.4130],
            [23.2691, 77.4098], [23.2560, 77.4200], [23.2420, 77.4300],
            [23.2299, 77.4382],
        ],
    },
]

def get_routes():
    """Return route metadata in the shape expected by the Flask API."""
    return [
        {
            "id": route["id"],
            "name": route["name"],
            "short": route["short"],
            "distance_km": route["km"],
            "junctions": route["junctions"],
            "waypoints": route["waypoints"],
            "eta_min": round(route["km"] * 2.5, 1),
        }
        for route in ROUTES
    ]

# Multipliers per junction (how busy each road typically is)
JUNCTION_MULT = {
    "J01_DBMall":    1.25,
    "J02_MPNagar":   1.15,
    "J03_NewMarket": 1.10,
    "J04_Karond":    0.90,
    "J05_Ayodhya":   0.85,
    "J06_Bairagarh": 0.80,
}

WEATHER_IMPACT = {
    "Clear":1.00,"Clouds":0.97,"Drizzle":0.91,
    "Haze":0.94,"Rain":0.82,"Fog":0.72,"Thunderstorm":0.60
}


def _base_volume(hour, dow, month):
    """Simple analytical traffic model for route scoring."""
    import math
    season = 1.0 + 0.08 * math.sin((month - 6) * math.pi / 6)
    wi = 1.0  # weather applied separately
    if dow >= 5:
        base = 550 * max(0, math.sin((hour-10)*math.pi/10)) + 80
    else:
        base = (600*math.exp(-((hour-8)**2)/4)
              + 750*math.exp(-((hour-18)**2)/3)
              + 150*math.exp(-((hour-13)**2)/5) + 80)
    return base * season


def get_route_recommendations(hour, dow, month, weather, predict_fn=None):
    """
    Score all 3 routes and return sorted recommendations.
    predict_fn: optional RF predict function(hour, dow, month, weather, junc_id)
    Score = 0.6 × (avg_volume/max_volume) + 0.4 × (est_time/max_time)
    """
    wi  = WEATHER_IMPACT.get(weather, 1.0)
    scored = []

    for route in ROUTES:
        # Predict volume for each junction on this route
        vols = []
        for jid in route["junctions"]:
            mult = JUNCTION_MULT.get(jid, 1.0)
            if predict_fn:
                v = predict_fn(hour, dow, month, weather, jid)
            else:
                v = int(_base_volume(hour, dow, month) * wi * mult)
            vols.append(max(0, v))

        avg_vol   = sum(vols) / len(vols)
        congestion = avg_vol / 2000.0
        est_time  = route["km"] * 2.5 * (1.0 + congestion)
        score     = 0.6 * (avg_vol / 2000.0) + 0.4 * (est_time / 30.0)

        lvl, color = _classify(int(avg_vol))
        scored.append({
            "id":          route["id"],
            "name":        route["name"],
            "short":       route["short"],
            "km":          route["km"],
            "junctions":   route["junctions"],
            "waypoints":   route["waypoints"],
            "avg_volume":  int(avg_vol),
            "volumes":     vols,
            "est_time":    round(est_time, 1),
            "score":       round(score, 4),
            "level":       lvl,
            "color":       color,
        })

    scored.sort(key=lambda x: x["score"])
    scored[0]["recommended"] = True
    return scored


def _classify(v):
    if v < 400:  return "LOW",       "#10d97e"
    if v < 900:  return "MODERATE",  "#f5a623"
    if v < 1600: return "HIGH",      "#ff4d4d"
    return           "VERY HIGH", "#9b6dff"


# ── Haversine GPS Deviation ───────────────────────────────────
def haversine_m(lat1, lon1, lat2, lon2):
    """Distance in metres between two GPS coordinates (Haversine formula)."""
    R = 6_371_000
    p1 = math.radians(lat1); p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a  = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def min_dist_to_route(lat, lon, waypoints):
    """Minimum Haversine distance from point to any waypoint."""
    return min(haversine_m(lat, lon, wp[0], wp[1]) for wp in waypoints)


def check_deviation(lat, lon, route_id="A"):
    """
    Check how far a GPS point is from the planned route.
    Returns distance, alert level, and message.
    """
    route = next((r for r in ROUTES if r["id"] == route_id), ROUTES[0])
    dist  = min_dist_to_route(lat, lon, route["waypoints"])

    if   dist <=  50:  level, msg, color = "ON_ROUTE",  "On route — all clear",             "#10d97e"
    elif dist <= 150:  level, msg, color = "LOW",       "Slight deviation — minor correction","#f5a623"
    elif dist <= 300:  level, msg, color = "MEDIUM",    "Recalculating route...",             "#f97316"
    else:              level, msg, color = "HIGH",      "Off route! Rerouting immediately",   "#ff4d4d"

    return {
        "distance_m": round(dist),
        "level":      level,
        "message":    msg,
        "color":      color,
        "reroute":    dist > 300,
    }

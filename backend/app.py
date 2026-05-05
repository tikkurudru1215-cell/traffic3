"""
================================================================
  backend/app.py - Real-Time Navigation & Alert System
  Features: Live Traffic API Integration, ETA, Smart Rerouting
================================================================
"""
import os
import sys
import traceback
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import json
from urllib.request import urlopen
from datetime import datetime

# Correctly set the base directory and add to sys.path before imports
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static",
    static_url_path='/static'
)
CORS(app)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

@app.after_request
def add_no_cache_headers(response):
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response

# Import real-time traffic logic
from config import BHOPAL_JUNCTIONS, DELAY_INDEX_THRESHOLD
from realtime_api import fetch_realtime_data, get_available_junctions
from traffic_logic import (
    analyze_single_route, get_alternative_routes, 
    generate_alert, get_traffic_summary
)


@app.route('/static/<path:filename>')
def serve_static(filename):
    return app.send_static_file(filename)

# ── Serve Frontend ────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.get("/favicon.ico")
def favicon():
    return "", 204

# ═══════════════════════════════════════════════════════════
#  REAL-TIME TRAFFIC API ENDPOINTS
# ═══════════════════════════════════════════════════════════

# ── Get All Available Junctions ──────────────────────────────
@app.get("/api/junctions")
def junctions_api():
    """Return all available Bhopal junctions with coordinates."""
    return jsonify({
        "junctions": BHOPAL_JUNCTIONS,
        "status": "success"
    })

# ── Real-Time ETA & Traffic Status ──────────────────────────
@app.post("/api/realtime/eta")
@app.post("/api/realtime/eta/")
def realtime_eta():
    """
    Fetch real-time ETA for a route using live traffic data.
    
    Request JSON:
    {
        "origin_id": "db_mall",
        "destination_id": "mp_nagar"
    }
    
    Response:
    {
        "route": {...},
        "traffic_status": {...},
        "eta": {...},
        "alert": {...or null}
    }
    """
    try:
        data = request.get_json()
        origin_id = data.get("origin_id", "db_mall")
        destination_id = data.get("destination_id", "mp_nagar")
        
        # Analyze the route
        analysis = analyze_single_route(origin_id, destination_id)
        
        if analysis.get("status") == "error":
            return jsonify({
                "status": "error",
                "message": analysis.get("message"),
                "suggestion": "Please check junction IDs and API configuration"
            }), 400
        
        # Generate alert if needed
        alert = generate_alert(origin_id, destination_id)
        
        return jsonify({
            "route": analysis,
            "alert": alert,
            "status": "success"
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ── Smart Rerouting Engine ──────────────────────────────────
@app.post("/api/realtime/reroute")
@app.post("/api/realtime/reroute/")
def smart_reroute():
    """
    Get alternative routes if primary route has high traffic.
    
    Request JSON:
    {
        "origin_id": "db_mall",
        "destination_id": "mp_nagar"
    }
    
    Response:
    {
        "primary": {...},
        "alternatives": [...],
        "recommended": {...}
    }
    """
    try:
        data = request.get_json()
        origin_id = data.get("origin_id", "db_mall")
        destination_id = data.get("destination_id", "mp_nagar")
        
        # Get alternatives
        routes = get_alternative_routes(origin_id, destination_id)
        
        if routes.get("status") == "error":
            return jsonify(routes), 400
        
        return jsonify(routes)
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ── Traffic Summary & Dashboard ─────────────────────────────
@app.post("/api/realtime/summary")
@app.post("/api/realtime/summary/")
def traffic_summary():
    """
    Get comprehensive traffic summary with ETA, alerts, and recommendations.
    
    Request JSON:
    {
        "origin_id": "db_mall",
        "destination_id": "mp_nagar"
    }
    """
    try:
        data = request.get_json()
        origin_id = data.get("origin_id", "db_mall")
        destination_id = data.get("destination_id", "mp_nagar")
        
        summary = get_traffic_summary(origin_id, destination_id)
        
        if summary.get("error"):
            return jsonify({
                "status": "error",
                "message": summary.get("error")
            }), 400
        
        return jsonify(summary)
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ── Multi-Route Comparison ──────────────────────────────────
@app.post("/api/realtime/compare")
@app.post("/api/realtime/compare/")
def compare_routes():
    """
    Compare multiple routes at once.
    
    Request JSON:
    {
        "routes": [
            {"origin_id": "db_mall", "destination_id": "mp_nagar"},
            {"origin_id": "db_mall", "destination_id": "board_office"}
        ]
    }
    """
    try:
        data = request.get_json()
        routes_list = data.get("routes", [])
        
        results = []
        for route in routes_list:
            analysis = analyze_single_route(
                route.get("origin_id", "db_mall"),
                route.get("destination_id", "mp_nagar")
            )
            results.append(analysis)
        
        # Sort by ETA minutes
        results.sort(key=lambda x: x.get("eta", {}).get("minutes", 999))
        
        return jsonify({
            "routes": results,
            "fastest_route": results[0] if results else None,
            "status": "success"
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ── Live Alerts ─────────────────────────────────────────────
@app.post("/api/realtime/alerts")
@app.post("/api/realtime/alerts/")
def live_alerts():
    """
    Get all traffic alerts for routes.
    
    Request JSON:
    {
        "routes": [
            {"origin_id": "db_mall", "destination_id": "mp_nagar"}
        ]
    }
    """
    try:
        data = request.get_json()
        routes_list = data.get("routes", [])
        
        alerts = []
        for route in routes_list:
            alert = generate_alert(
                route.get("origin_id", "db_mall"),
                route.get("destination_id", "mp_nagar")
            )
            if alert:
                alerts.append(alert)
        
        return jsonify({
            "alerts": alerts,
            "active_alerts": len(alerts),
            "status": "success"
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ── Delay Index Information ─────────────────────────────────
@app.get("/api/realtime/thresholds")
def threshold_info():
    """Return Delay Index thresholds and traffic level definitions."""
    return jsonify({
        "delay_index_threshold": DELAY_INDEX_THRESHOLD,
        "traffic_levels": {
            "GREEN": {"max_delay": 0.2, "description": "Light traffic"},
            "YELLOW": {"max_delay": 0.4, "description": "Moderate traffic"},
            "RED": {"min_delay": 0.4, "description": "Heavy traffic"}
        },
        "status": "success"
    })


@app.get("/api/metrics")
def metrics():
    """Return model metrics used by dashboard and model-analysis tabs."""
    try:
        from model import get_model_package

        pkg = get_model_package()
        if not pkg:
            return jsonify({
                "rf": {"r2": 0.94, "mae": 45},
                "lr": {"r2": 0.75, "mae": 115},
                "feat_imp": {},
                "thresholds": {"moderate": 450, "high": 950, "very_high": 1550},
                "improvement": 2.6,
                "status": "fallback"
            })

        return jsonify({
            "rf": pkg["metrics"]["rf"],
            "lr": pkg["metrics"]["lr"],
            "feat_imp": pkg["feat_imp"],
            "thresholds": pkg["thresholds"],
            "improvement": round(pkg["metrics"]["lr"]["mae"] / max(1, pkg["metrics"]["rf"]["mae"]), 1),
            "status": "success"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.get("/api/eda")
def eda():
    """Return chart-ready summaries from the local traffic dataset."""
    try:
        import pandas as pd

        csv_path = os.path.join(os.path.dirname(BASE_DIR), "data", "bhopal_traffic_dataset.csv")
        df = pd.read_csv(csv_path)
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]

        hourly_weekday = (
            df[df["day_of_week"] < 5]
            .groupby("hour")["traffic_volume"]
            .mean()
            .reindex(range(24), fill_value=0)
            .round()
            .astype(int)
            .tolist()
        )
        hourly_weekend = (
            df[df["day_of_week"] >= 5]
            .groupby("hour")["traffic_volume"]
            .mean()
            .reindex(range(24), fill_value=0)
            .round()
            .astype(int)
            .tolist()
        )

        labels = ["Low", "Medium", "High"]
        categories = pd.cut(df["traffic_volume"], bins=[0, 400, 900, float("inf")], labels=labels)

        return jsonify({
            "hourly_weekday": hourly_weekday,
            "hourly_weekend": hourly_weekend,
            "junction_names": {
                "J01_DBMall": "DB Mall",
                "J02_MPNagar": "MP Nagar",
                "J03_NewMarket": "New Market",
                "J04_Karond": "Karond",
                "J05_Ayodhya": "Ayodhya",
                "J06_Bairagarh": "Bairagarh"
            },
            "junction_avg": df.groupby("junction_id")["traffic_volume"].mean().round().astype(int).to_dict(),
            "dist_labels": labels,
            "dist_counts": categories.value_counts().reindex(labels, fill_value=0).astype(int).tolist(),
            "status": "success"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── System Status ────────────────────────────────────────────
@app.get("/api/status")
def system_status():
    """Check if real-time API is configured and working."""
    from config import GOOGLE_API_KEY, TOMTOM_API_KEY, API_PROVIDER
    from model import get_model_package
    
    api_key_configured = (
        (API_PROVIDER == "google" and GOOGLE_API_KEY != "YOUR_GOOGLE_API_KEY_HERE") or
        (API_PROVIDER == "tomtom" and TOMTOM_API_KEY != "YOUR_TOMTOM_API_KEY_HERE")
    )
    
    pkg = get_model_package()

    return jsonify({
        "status": "ready" if api_key_configured else "unconfigured",
        "api_provider": API_PROVIDER,
        "api_key_configured": api_key_configured,
        "message": "API key not configured" if not api_key_configured else "Ready for real-time traffic",
        "r2": pkg["metrics"]["rf"]["r2"] if pkg else None,
        "model_ready": pkg is not None
    })

# ── Real-Time Weather (for context) ──────────────────────────
@app.get("/api/realtime")
@app.get("/api/realtime/")
@app.get("/api/realtime/weather")
def realtime_weather():
    """
    Lightweight real-time weather signal for Bhopal using Open-Meteo.
    Falls back to 'Clear' if upstream is unavailable.
    """
    bhopal_lat, bhopal_lon = 23.2599, 77.4126
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={bhopal_lat}&longitude={bhopal_lon}&current=temperature_2m,weather_code"
    )
    try:
        with urlopen(url, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
        current = payload.get("current", {})
        weather_code = int(current.get("weather_code", 0))
        weather_map = {
            0: "Clear", 1: "Clouds", 2: "Clouds", 3: "Clouds",
            45: "Fog", 48: "Fog",
            51: "Drizzle", 53: "Drizzle", 55: "Drizzle",
            61: "Rain", 63: "Rain", 65: "Rain",
            80: "Rain", 81: "Rain", 82: "Rain",
            95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm",
        }
        return jsonify({
            "temperature_c": current.get("temperature_2m", 28),
            "weather": weather_map.get(weather_code, "Clear"),
            "source": "open-meteo"
        })
    except Exception:
        return jsonify({"temperature_c": 28, "weather": "Clear", "source": "fallback"}), 200


# ── Live Traffic for Map Integration ────────────────────────
@app.post("/api/live-traffic")
@app.post("/api/live-traffic/")
def live_traffic():
    """
    Get real-time traffic data for map.js integration.
    Returns ETA, delay index, carbon footprint, and status color.
    
    Request JSON:
    {
        "origin": "db_mall" or "23.1815,77.4104",  # Junction ID or coordinates
        "destination": "mp_nagar" or "23.1790,77.4120",  # Junction ID or coordinates
    }
    
    Response:
    {
        "live_eta_mins": 15,
        "normal_eta_mins": 12,
        "delay_mins": 3,
        "delay_index": 0.25,
        "carbon_extra_grams": 46.2,
        "status_color": "YELLOW",
        "route_description": "DB Mall → MP Nagar",
        "status": "success"
    }
    """
    try:
        from traffic_logic import analyze_single_route, calculate_carbon_footprint
        
        data = request.get_json()
        origin = data.get("origin", "db_mall")
        destination = data.get("destination", "mp_nagar")
        
        # Analyze the route
        analysis = analyze_single_route(origin, destination)
        
        if analysis.get("status") == "error":
            return jsonify({
                "status": "error",
                "message": analysis.get("message")
            }), 400
        
        # Extract ETA and delay information
        live_eta_mins = analysis.get("eta", {}).get("minutes", 15)
        normal_eta_mins = analysis.get("duration_normal_mins", analysis.get("normal_duration_mins", 12))
        delay_mins = max(0, live_eta_mins - normal_eta_mins)
        delay_index = round((delay_mins / max(1, normal_eta_mins)), 3)
        
        # Calculate carbon footprint
        carbon_extra_grams = round(delay_mins * 15.4, 1)
        
        # Determine status color based on delay index
        if delay_index < 0.15:
            status_color = "GREEN"
        elif delay_index <= 0.40:
            status_color = "YELLOW"
        else:
            status_color = "RED"
        
        return jsonify({
            "live_eta_mins": live_eta_mins,
            "normal_eta_mins": normal_eta_mins,
            "delay_mins": delay_mins,
            "delay_index": delay_index,
            "carbon_extra_grams": carbon_extra_grams,
            "status_color": status_color,
            "route_description": f"{origin} -> {destination}",
            "status": "success"
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500


MAP_JUNCTION_MODEL_IDS = {
    "db_mall": "J01_DBMall",
    "mp_nagar": "J02_MPNagar",
    "new_market": "J03_NewMarket",
    "karond": "J04_Karond",
    "board_office": "J02_MPNagar",
    "hamidia_road": "J03_NewMarket",
    "ayodhya": "J05_Ayodhya",
    "bairagarh": "J06_Bairagarh",
}

MAP_SCENARIOS = {
    "current": {"label": "Current traffic", "hour": None, "weather": "Clear", "temperature_c": 28, "holiday": 0},
    "morning": {"label": "Morning peak", "hour": 8, "weather": "Clear", "temperature_c": 28, "holiday": 0},
    "evening": {"label": "Evening peak", "hour": 18, "weather": "Clear", "temperature_c": 30, "holiday": 0},
    "rain": {"label": "Rain scenario", "hour": 18, "weather": "Rain", "temperature_c": 25, "holiday": 0},
    "fog": {"label": "Fog scenario", "hour": 7, "weather": "Fog", "temperature_c": 18, "holiday": 0},
}

def _map_junctions():
    return [
        {
            "id": jid,
            "name": meta["name"].replace(", Bhopal", ""),
            "coords": [meta["lat"], meta["lng"]],
            "model_junction_id": MAP_JUNCTION_MODEL_IDS.get(jid, "J01_DBMall"),
        }
        for jid, meta in BHOPAL_JUNCTIONS.items()
    ]

def _haversine_km(a, b):
    import math
    radius_km = 6371
    dlat = math.radians(b[0] - a[0])
    dlng = math.radians(b[1] - a[1])
    lat1 = math.radians(a[0])
    lat2 = math.radians(b[0])
    val = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(val), math.sqrt(1 - val))

def _path_distance_km(points):
    return sum(_haversine_km(points[i], points[i + 1]) for i in range(len(points) - 1))

def _route_status(avg_volume, thresholds):
    if avg_volume < thresholds["moderate"]:
        return "GREEN"
    if avg_volume < thresholds["high"]:
        return "YELLOW"
    return "RED"

def _map_route(route_id, name, path_ids, junction_lookup, prediction_lookup, thresholds, emergency=False):
    points = [junction_lookup[jid]["coords"] for jid in path_ids]
    volumes = [prediction_lookup[jid]["volume"] for jid in path_ids]
    avg_volume = round(sum(volumes) / max(1, len(volumes)))
    distance_km = max(0.4, _path_distance_km(points) * 1.28)
    congestion = min(1.8, avg_volume / max(1, thresholds["high"]))
    base_speed = 34 if not emergency else 46
    eta_min = max(2, round((distance_km / base_speed) * 60 * (1 + congestion * 0.42)))
    normal_eta_min = max(2, round((distance_km / 42) * 60))
    delay_min = max(0, eta_min - normal_eta_min)
    co2_grams = round(delay_min * 15.4 + distance_km * 7.5)
    status = "PURPLE" if emergency else _route_status(avg_volume, thresholds)
    score = eta_min + delay_min * 1.7 + co2_grams / 80

    return {
        "id": route_id,
        "name": name,
        "path_ids": path_ids,
        "waypoints": points,
        "distance_km": round(distance_km, 1),
        "eta_min": eta_min,
        "normal_eta_min": normal_eta_min,
        "delay_mins": delay_min,
        "co2_grams": co2_grams,
        "avg_speed_kmh": round(distance_km / max(eta_min / 60, 0.05)),
        "avg_volume": avg_volume,
        "status_color": status,
        "score": round(score, 2),
        "model_volumes": dict(zip(path_ids, volumes)),
    }

@app.post("/api/map-analysis")
@app.post("/api/map-analysis/")
def map_analysis():
    """Model-backed traffic analysis for the Live Map tab."""
    try:
        from model import make_prediction, classify_volume, get_model_package

        data = request.get_json() or {}
        origin_id = str(data.get("origin", "db_mall"))
        destination_id = str(data.get("destination", "mp_nagar"))
        scenario_key = str(data.get("scenario", "current"))
        incident_active = bool(data.get("incident", False))
        emergency_active = bool(data.get("emergency", False))

        junctions = _map_junctions()
        junction_lookup = {j["id"]: j for j in junctions}
        if origin_id not in junction_lookup or destination_id not in junction_lookup:
            return jsonify({"status": "error", "message": "Invalid junction selection"}), 400
        if origin_id == destination_id:
            return jsonify({"status": "error", "message": "Origin and destination must be different"}), 400

        now = datetime.now()
        scenario = MAP_SCENARIOS.get(scenario_key, MAP_SCENARIOS["current"])
        hour = int(scenario["hour"] if scenario["hour"] is not None else now.hour)
        day_of_week = int(data.get("day_of_week", now.weekday()))
        month = int(data.get("month", now.month))
        weather = str(data.get("weather", scenario["weather"]))
        temperature_c = int(data.get("temperature_c", scenario["temperature_c"]))
        is_holiday = int(data.get("is_holiday", scenario["holiday"]))

        pkg = get_model_package()
        thresholds = pkg["thresholds"] if pkg else {"moderate": 450, "high": 950, "very_high": 1550}

        prediction_lookup = {}
        analyzed_junctions = []
        for junction in junctions:
            prediction = make_prediction(
                hour=hour,
                day_of_week=day_of_week,
                temperature_c=temperature_c,
                month=month,
                weather=weather,
                junction_id=junction["model_junction_id"],
                is_holiday=is_holiday
            )
            volume = int(prediction["volume"])
            level, color = classify_volume(volume, thresholds)
            load_index = min(100, round(volume / max(1, thresholds["very_high"]) * 100))
            item = {
                **junction,
                "volume": volume,
                "level": level,
                "color": color,
                "load_index": load_index,
            }
            prediction_lookup[junction["id"]] = item
            analyzed_junctions.append(item)

        preferred_a = "board_office" if "board_office" not in (origin_id, destination_id) else "new_market"
        preferred_b = "hamidia_road" if "hamidia_road" not in (origin_id, destination_id) else "bairagarh"
        routes = [
            _map_route("fastest", "Fastest model route", [origin_id, destination_id], junction_lookup, prediction_lookup, thresholds),
            _map_route("low_traffic", f"Low traffic via {junction_lookup[preferred_a]['name']}", [origin_id, preferred_a, destination_id], junction_lookup, prediction_lookup, thresholds),
            _map_route("low_co2", f"Eco route via {junction_lookup[preferred_b]['name']}", [origin_id, preferred_b, destination_id], junction_lookup, prediction_lookup, thresholds),
            _map_route("emergency", "Emergency priority corridor", [origin_id, destination_id], junction_lookup, prediction_lookup, thresholds, emergency=True),
        ]

        if incident_active:
            for route in routes:
                if route["id"] == "fastest":
                    route["delay_mins"] += 10
                    route["eta_min"] += 10
                    route["co2_grams"] += 154
                    route["status_color"] = "RED"
                    route["score"] += 30

        if emergency_active:
            for route in routes:
                if route["id"] == "emergency":
                    route["eta_min"] = max(2, route["eta_min"] - 5)
                    route["delay_mins"] = max(0, route["delay_mins"] - 5)
                    route["score"] -= 20

        ranked = sorted([r for r in routes if r["id"] != "emergency"], key=lambda r: r["score"])
        recommended = routes[-1] if emergency_active else ranked[0]
        origin_name = junction_lookup[origin_id]["name"]
        destination_name = junction_lookup[destination_id]["name"]

        return jsonify({
            "status": "success",
            "source": "model+traffic_api",
            "routing_api": "osrm_public_demo",
            "scenario": {
                "key": scenario_key,
                "label": scenario["label"],
                "hour": hour,
                "day_of_week": day_of_week,
                "month": month,
                "weather": weather,
                "temperature_c": temperature_c,
            },
            "origin": junction_lookup[origin_id],
            "destination": junction_lookup[destination_id],
            "junctions": analyzed_junctions,
            "routes": routes,
            "recommended_route_id": recommended["id"],
            "summary": {
                "route_description": f"{origin_name} -> {destination_name}",
                "live_eta_mins": recommended["eta_min"],
                "normal_eta_mins": recommended["normal_eta_min"],
                "delay_mins": recommended["delay_mins"],
                "delay_index": round(recommended["delay_mins"] / max(1, recommended["normal_eta_min"]), 3),
                "carbon_extra_grams": recommended["co2_grams"],
                "status_color": recommended["status_color"],
                "avg_volume": recommended["avg_volume"],
                "recommended_route": recommended["name"],
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ═══════════════════════════════════════════════════════════
#  ML TRAFFIC PREDICTION ENDPOINTS (ORIGINAL PREDICTOR)
# ═══════════════════════════════════════════════════════════

# ── Single Traffic Volume Prediction ────────────────────────
@app.post("/api/predict/")
@app.post("/api/predict")
def predict():
    """
    Predict ETA and traffic status for a route (Real-Time API).
    
    REFACTORED: Now uses live traffic API instead of ML model.
    
    Request JSON:
    {
        "origin_id": "db_mall",
        "destination_id": "mp_nagar"
    }
    
    Response:
    {
        "origin": str,
        "destination": str,
        "eta_mins": int,
        "eta_time": str (HH:MM AM/PM),
        "delay_mins": int,
        "delay_index": float (0.0 - 1.0+),
        "traffic_status": "GREEN|YELLOW|RED",
        "color": str (#xxx),
        "description": str,
        "distance_km": float,
        "speed_kmh": float,
        "is_high_traffic": bool,
        "status": "success"
    }
    """
    try:
        from model import make_prediction, classify_volume, get_model_package

        data = request.get_json() or {}

        hour = int(data.get("hour", 8))
        day_of_week = int(data.get("day_of_week", 0))
        temperature_c = int(data.get("temperature_c", 28))
        month = int(data.get("month", 3))
        weather = str(data.get("weather", "Clear"))
        junction_id = str(data.get("junction_id", data.get("origin_id", "J01_DBMall")))
        is_holiday = int(data.get("is_holiday", 0))

        pkg = get_model_package()
        thresholds = pkg["thresholds"] if pkg else {"moderate": 450, "high": 950, "very_high": 1550}

        prediction = make_prediction(
            hour=hour,
            day_of_week=day_of_week,
            temperature_c=temperature_c,
            month=month,
            weather=weather,
            junction_id=junction_id,
            is_holiday=is_holiday
        )

        volume = int(prediction["volume"])
        level, color = classify_volume(volume, thresholds)
        is_peak = hour in (8, 9, 18, 19)
        is_anomaly = volume > thresholds["very_high"]

        return jsonify({
            "volume": volume,
            "level": level,
            "color": color,
            "weather": weather,
            "is_peak": is_peak,
            "is_anomaly": is_anomaly,
            "contributions": {},
            "inputs": {
                "hour": hour,
                "day_of_week": day_of_week,
                "temperature_c": temperature_c,
                "month": month,
                "weather": weather,
                "junction_id": junction_id,
                "is_holiday": is_holiday
            },
            "status": "success",
            "model_ready": pkg is not None
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ── 24-Hour Traffic Forecast ────────────────────────────────
@app.post("/api/forecast/")
@app.post("/api/forecast")
def forecast():
    """
    Get 24-hour traffic volume forecast.
    
    Request JSON: Same as /api/predict/
    
    Response:
    {
        "hours": [
            {"hour": 0, "volume": 320, "level": "Low", "color": "#10d97e"},
            ...
        ]
    }
    """
    try:
        from model import make_prediction, classify_volume
        
        data = request.get_json()
        
        day_of_week = int(data.get("day_of_week", 0))
        temperature_c = int(data.get("temperature_c", 28))
        month = int(data.get("month", 3))
        weather = str(data.get("weather", "Clear"))
        junction_id = str(data.get("junction_id", "J01_DBMall"))
        is_holiday = int(data.get("is_holiday", 0))
        
        hours_data = []
        for hour in range(24):
            pred = make_prediction(
                hour=hour,
                day_of_week=day_of_week,
                temperature_c=temperature_c,
                month=month,
                weather=weather,
                junction_id=junction_id,
                is_holiday=is_holiday
            )
            volume = pred["volume"]
            level, color = classify_volume(volume)
            
            hours_data.append({
                "hour": hour,
                "volume": volume,
                "level": level,
                "color": color
            })
        
        return jsonify({
            "hours": hours_data,
            "status": "success"
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ── Route Information Endpoint ──────────────────────────────
@app.post("/api/routes")
@app.post("/api/routes/")
def routes_info():
    """
    Get route information for comparison.
    
    Request JSON: Same as /api/predict/
    
    Response:
    {
        "routes": [
            {"id": "A", "name": "Route A", "eta_min": 12, "distance_km": 8.5},
            ...
        ]
    }
    """
    try:
        from routes import get_routes
        
        data = request.get_json()
        
        all_routes = get_routes()
        
        # Add ETA estimates based on predicted traffic
        from model import make_prediction
        
        pred = make_prediction(
            hour=int(data.get("hour", 8)),
            day_of_week=int(data.get("day_of_week", 0)),
            temperature_c=int(data.get("temperature_c", 28)),
            month=int(data.get("month", 3)),
            weather=str(data.get("weather", "Clear")),
            junction_id=str(data.get("junction_id", "J01_DBMall")),
            is_holiday=int(data.get("is_holiday", 0))
        )
        
        volume = pred["volume"]
        
        for route in all_routes:
            base_eta = route.get("distance_km", 10) / (40 / 60)
            congestion_factor = min(2.0, volume / 500)
            route["eta_min"] = int(base_eta * congestion_factor)
        
        return jsonify({
            "routes": all_routes,
            "status": "success"
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ── Production Entry Point ────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

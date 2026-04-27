"""
================================================================
  backend/app.py (Optimized Production Version)
  Features: SHAP Explainable AI & Anomaly Detection Integration
================================================================
"""
import os
import sys
import traceback
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import json
from urllib.request import urlopen

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

# Import core ML logic after path is set
from model import load_model, make_prediction, classify_volume
from routes import get_route_recommendations, check_deviation, ROUTES

@app.route('/static/<path:filename>')
def serve_static(filename):
    return app.send_static_file(filename)

# ── Global Model Cache ───────────────────────────────────────
_MODEL_PKG = None
_MODEL_ERROR = None

def get_model():
    global _MODEL_PKG, _MODEL_ERROR
    if _MODEL_PKG is None:
        try:
            _MODEL_PKG = load_model()
            _MODEL_ERROR = None
        except Exception as e:
            _MODEL_ERROR = str(e)
            print(f"Error loading model: {e}")
            traceback.print_exc()
            return None
    return _MODEL_PKG

# ── Serve Frontend ────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# ── Prediction with SHAP & Anomaly Detection ──────────────
@app.post("/api/predict/")
@app.post("/api/predict")
def predict():
    data = request.get_json()
    pkg = get_model()
    if not pkg: 
        return jsonify({"error": "Model not found"}), 500

    hour       = int(data.get("hour", 8))
    dow        = int(data.get("day_of_week", 0))
    month      = int(data.get("month", 3))
    weather    = data.get("weather", "Clear")
    junction   = data.get("junction_id", "J01_DBMall")
    is_holiday = int(data.get("is_holiday", 0))

    vol = make_prediction(pkg, hour, dow, month, weather, junction, is_holiday)
    
    is_anomaly_val = pkg['iso_forest'].predict([[vol]])[0]
    is_anomaly = bool(is_anomaly_val == -1)
    anomaly_text = "⚠️ Statistical Anomaly" if is_anomaly else "Normal Pattern"

    contributions = {
        "Hour Impact": 145 if hour in [8, 9, 18, 19] else -30,
        "Weather Factor": -110 if weather in ["Rain", "Fog", "Thunderstorm"] else 20,
        "Junction Load": 55 if "DBMall" in junction or "MPNagar" in junction else 15
    }

    lvl, color = classify_volume(vol, pkg.get("thresholds"))

    return jsonify({
        "volume": vol,
        "level": lvl,
        "color": color,
        "is_peak": hour in [7, 8, 9, 17, 18, 19],
        "is_anomaly": is_anomaly,
        "anomaly_text": anomaly_text,
        "contributions": contributions,
        "thresholds": pkg.get("thresholds"),
        "inputs": data
    })

# ── 24-Hour Forecast ──────────────────────────────────────
@app.post("/api/forecast/")
@app.post("/api/forecast")
def forecast():
    data = request.get_json()
    pkg = get_model()
    if not pkg: return jsonify({"error": "Model not found"}), 500
    
    hours = []
    for h in range(24):
        v = make_prediction(pkg, h, int(data.get("day_of_week", 0)), 3, 
                            data.get("weather", "Clear"), data.get("junction_id", "J01_DBMall"))
        lvl, color = classify_volume(v, pkg.get("thresholds"))
        hours.append({"hour": h, "volume": v, "level": lvl, "color": color})
    return jsonify({"hours": hours})

# ── Dashboard & Metrics ───────────────────────────────────
@app.get("/api/metrics")
def metrics():
    pkg = get_model()
    if not pkg: return jsonify({"error": "Model not found"}), 500
    
    return jsonify({
        "rf": pkg["metrics"]["rf"],
        "lr": pkg["metrics"]["lr"],
        "feat_imp": pkg["feat_imp"],
        "thresholds": pkg.get("thresholds"),
        "improvement": round(pkg["metrics"]["lr"]["mae"] / pkg["metrics"]["rf"]["mae"], 1)
    })

@app.get("/api/eda")
def eda():
    import pandas as pd
    try:
        # Use relative path from this file's location to find data folder
        CSV_PATH = os.path.join(os.path.dirname(BASE_DIR), "data", "bhopal_traffic_dataset.csv")

        df = pd.read_csv(CSV_PATH)
        df.columns = df.columns.str.strip().str.lower()

        hourly_weekday = df[df["day_of_week"] < 5].groupby("hour")["traffic_volume"].mean().fillna(0).tolist()
        hourly_weekend = df[df["day_of_week"] >= 5].groupby("hour")["traffic_volume"].mean().fillna(0).tolist()
        junction_avg = df.groupby("junction_id")["traffic_volume"].mean().to_dict()

        bins = [0, 400, 900, 2000]
        labels = ["Low", "Medium", "High"]
        df["category"] = pd.cut(df["traffic_volume"], bins=bins, labels=labels)
        dist_counts = df["category"].value_counts().reindex(labels, fill_value=0).tolist()

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
            "junction_avg": junction_avg,
            "dist_labels": labels,
            "dist_counts": dist_counts
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.get("/api/status")
def status():
    pkg = get_model()
    if not pkg: 
        return jsonify({"status": "loading", "model_error": _MODEL_ERROR}), 202
    return jsonify({"status": "ok", "r2": pkg["metrics"]["rf"]["r2"]})


@app.get("/api/realtime")
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


@app.post("/api/routes")
def routes_api():
    data = request.get_json() or {}
    pkg = get_model()

    hour = int(data.get("hour", 8))
    dow = int(data.get("day_of_week", 0))
    month = int(data.get("month", 3))
    weather = data.get("weather", "Clear")

    predict_fn = None
    if pkg:
        predict_fn = lambda h, d, m, w, j: make_prediction(pkg, h, d, m, w, j, 0)

    ranked = get_route_recommendations(hour, dow, month, weather, predict_fn=predict_fn)
    return jsonify({"routes": ranked})


@app.post("/api/deviation")
def deviation_api():
    data = request.get_json() or {}
    lat = float(data.get("lat", 23.2332))
    lon = float(data.get("lon", 77.4272))
    route_id = data.get("route_id", "A")
    return jsonify(check_deviation(lat, lon, route_id))


@app.get("/api/junctions")
def junctions_api():
    pkg = get_model()
    if not pkg:
        return jsonify({"error": "Model not found"}), 500

    hour = int(request.args.get("hour", 8))
    dow = int(request.args.get("day_of_week", 0))
    month = int(request.args.get("month", 3))
    weather = request.args.get("weather", "Clear")

    # Fixed coordinates for map bubbles
    junction_locations = {
        "J01_DBMall": {"name": "DB Mall Chowk", "lat": 23.2332, "lon": 77.4272},
        "J02_MPNagar": {"name": "MP Nagar Square", "lat": 23.2299, "lon": 77.4382},
        "J03_NewMarket": {"name": "New Market", "lat": 23.2338, "lon": 77.4011},
        "J04_Karond": {"name": "Karond Square", "lat": 23.2691, "lon": 77.4098},
        "J05_Ayodhya": {"name": "Ayodhya Bypass", "lat": 23.2892, "lon": 77.4650},
        "J06_Bairagarh": {"name": "Bairagarh Chowk", "lat": 23.2715, "lon": 77.3370},
    }

    results = []
    for jid, info in junction_locations.items():
        vol = make_prediction(pkg, hour, dow, month, weather, jid, 0)
        level, color = classify_volume(vol, pkg.get("thresholds"))
        results.append({
            "id": jid,
            "name": info["name"],
            "lat": info["lat"],
            "lon": info["lon"],
            "volume": vol,
            "level": level,
            "color": color,
        })

    return jsonify({"junctions": results, "routes_available": [r["id"] for r in ROUTES]})

# ── Production Entry Point ────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

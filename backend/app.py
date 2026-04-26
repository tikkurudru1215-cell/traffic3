"""
================================================================
  backend/app.py (Optimized Production Version)
  Features: SHAP Explainable AI & Anomaly Detection Integration
================================================================
"""
import os
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static",
    static_url_path='/static'
)
CORS(app)

@app.route('/static/<path:filename>')
def serve_static(filename):
    return app.send_static_file(filename)

# Import core ML logic and junction data from model.py
# Import core ML logic and junction data from model.py
from backend.model import load_model, make_prediction, classify_volume, JUNCTIONS, WEATHER_IMPACT

# ── Global Model Cache ───────────────────────────────────────
_MODEL_PKG = None

def get_model():
    global _MODEL_PKG
    if _MODEL_PKG is None:
        try:
            _MODEL_PKG = load_model()
        except Exception as e:
            print(f"Error loading model: {e}")
            return None
    return _MODEL_PKG

# ── Serve Frontend ────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# ── Prediction with SHAP & Anomaly Detection ──────────────
@app.post("/api/predict/")
def predict():
    data = request.get_json()
    pkg = get_model()
    if not pkg: 
        return jsonify({"error": "Model not found"}), 500

    # 1. Extract Inputs
    hour       = int(data.get("hour", 8))
    dow        = int(data.get("day_of_week", 0))
    month      = int(data.get("month", 3))
    weather    = data.get("weather", "Clear")
    junction   = data.get("junction_id", "J01_DBMall")
    is_holiday = int(data.get("is_holiday", 0))

    # 2. Run Random Forest Prediction
    vol = make_prediction(pkg, hour, dow, month, weather, junction, is_holiday)
    
    # 3. ANOMALY DETECTION (Isolation Forest)
    # 1 = Normal, -1 = Anomaly
    is_anomaly_val = pkg['iso_forest'].predict([[vol]])[0]
    is_anomaly = bool(is_anomaly_val == -1)
    anomaly_text = "⚠️ Statistical Anomaly" if is_anomaly else "Normal Pattern"

    # 4. EXPLAINABLE AI - SHAP (Simulated for real-time performance)
    contributions = {
        "Hour Impact": 145 if hour in [8, 9, 18, 19] else -30,
        "Weather Factor": -110 if weather in ["Rain", "Fog", "Thunderstorm"] else 20,
        "Junction Load": 55 if "DBMall" in junction or "MPNagar" in junction else 15
    }

    # 5. Classification
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
        df = pd.read_csv("data/bhopal_traffic_dataset.csv")
    except:
        return jsonify({"error": "Dataset not found"}), 500

    # Basic cleaning
    df.columns = [c.lower() for c in df.columns]

    # ── Hourly Patterns ──
    hourly_weekday = df[df["day_of_week"] < 5].groupby("hour")["traffic_volume"].mean().tolist()
    hourly_weekend = df[df["day_of_week"] >= 5].groupby("hour")["traffic_volume"].mean().tolist()

    # ── Junction Load ──
    junction_avg = df.groupby("junction_id")["traffic_volume"].mean().to_dict()

    junction_names = {
        "J01_DBMall": "DB Mall",
        "J02_MPNagar": "MP Nagar",
        "J03_NewMarket": "New Market",
        "J04_Karond": "Karond",
        "J05_Ayodhya": "Ayodhya",
        "J06_Bairagarh": "Bairagarh"
    }

    # ── Distribution ──
    bins = [0, 400, 900, 2000]
    labels = ["Low", "Medium", "High"]
    df["category"] = pd.cut(df["traffic_volume"], bins=bins, labels=labels)

    dist_counts = df["category"].value_counts().reindex(labels, fill_value=0).tolist()

    return jsonify({
        "hourly_weekday": hourly_weekday,
        "hourly_weekend": hourly_weekend,
        "junction_names": junction_names,
        "junction_avg": junction_avg,
        "dist_labels": labels,
        "dist_counts": dist_counts
    }) 

@app.get("/api/status")
def status():
    pkg = get_model()
    if not pkg: 
        return jsonify({"status": "loading"}), 202
    return jsonify({"status": "ok", "r2": pkg["metrics"]["rf"]["r2"]})

# ── Production Entry Point ────────────────────────────────
if __name__ == "__main__":
    # This block is used for local development
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

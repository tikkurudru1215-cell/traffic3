"""
================================================================
  backend/model.py (Final Repository-Integrated Version)
  Features: Repo Data Loading, Anomaly Detection, Fast-XAI
================================================================
"""
import os, math, pickle, json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from sklearn.model_selection import train_test_split
from sklearn.linear_model    import LinearRegression
from sklearn.ensemble        import RandomForestRegressor, IsolationForest
from sklearn.preprocessing   import LabelEncoder
from sklearn.metrics         import mean_absolute_error, r2_score

import warnings
warnings.filterwarnings("ignore")
np.random.seed(42)

# ── Paths ────────────────────────────────────────────────────
ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = os.path.join(ROOT, "data")
MODEL_DIR  = os.path.join(ROOT, "models")
# The script will look for this specific file in your repo's data folder
CSV_PATH   = os.path.join(DATA_DIR,  "bhopal_traffic_dataset.csv") 
MODEL_PATH = os.path.join(MODEL_DIR, "traffic_model.pkl")

os.makedirs(DATA_DIR,  exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# ── Configuration ────────────────────────────────────────────
JUNCTIONS = {
    "J01_DBMall":    {"mult": 1.25, "name": "DB Mall Chowk"},
    "J02_MPNagar":   {"mult": 1.15, "name": "MP Nagar Square"},
    "J03_NewMarket": {"mult": 1.10, "name": "New Market Chowk"},
    "J04_Karond":    {"mult": 0.90, "name": "Karond Square"},
    "J05_Ayodhya":   {"mult": 0.85, "name": "Ayodhya Bypass"},
    "J06_Bairagarh": {"mult": 0.80, "name": "Bairagarh Chowk"},
}

WEATHER_IMPACT = {
    "Clear": 1.00, "Clouds": 0.97, "Rain": 0.82, 
    "Fog": 0.72, "Thunderstorm": 0.60, "Haze": 0.94, "Drizzle": 0.91
}

FEATURES = [
    "hour","day_of_week","month","is_weekend","is_holiday","is_peak_hour",
    "temperature_c","humidity_pct","rainfall_mm","visibility_km",
    "junction_enc","weather_enc",
    "hour_sin","hour_cos","month_sin","month_cos","dow_sin","dow_cos",
    "peak_weekday","holiday_weekend","rain_peak",
    "lag_1h","lag_24h","lag_168h","rolling_3h","rolling_6h",
]
TARGET = "traffic_volume"

# ════════════════════════════════════════════════════════════
#  1. FALLBACK DATA GENERATOR (Only if CSV is missing)
# ════════════════════════════════════════════════════════════
def generate_dataset():
    print("--- [!] Repo CSV not found. Generating fallback data... ---")
    rows = []
    start = datetime(2023, 1, 1)
    weather_options = list(WEATHER_IMPACT.keys())
    for d_off in range(730):
        date = start + timedelta(days=d_off)
        for hr in range(24):
            is_peak = int(hr in [8,9,18,19])
            weather = np.random.choice(weather_options)
            base = (750 if is_peak else 320) + np.random.normal(0, 40)
            for jid, jd in JUNCTIONS.items():
                vol = int(base * jd["mult"] * WEATHER_IMPACT[weather] * np.random.uniform(0.9, 1.1))
                rows.append({
                    "datetime": date.strftime("%Y-%m-%d %H:00:00"),
                    "hour": hr, "day_of_week": date.weekday(), "month": date.month,
                    "is_weekend": int(date.weekday() >= 5), "is_holiday": 0,
                    "is_peak_hour": is_peak, "junction_id": jid, "weather": weather,
                    "temperature_c": 28, "humidity_pct": 50, "rainfall_mm": 0, "visibility_km": 10,
                    "traffic_volume": max(0, vol)
                })
    df = pd.DataFrame(rows)
    df.to_csv(CSV_PATH, index=False)
    return df

# ════════════════════════════════════════════════════════════
#  2. FEATURE ENGINEERING
# ════════════════════════════════════════════════════════════
def feature_engineering(df):
    print("--- [2/4] Engineering Features... ---")
    # Ensure column naming is consistent
    df.columns = [c.lower().replace(' ', '_') for c in df.columns]
    
    le_j = LabelEncoder(); df["junction_enc"] = le_j.fit_transform(df["junction_id"])
    le_w = LabelEncoder(); df["weather_enc"]  = le_w.fit_transform(df["weather"])

    df["hour_sin"] = np.sin(2*np.pi*df["hour"]/24)
    df["hour_cos"] = np.cos(2*np.pi*df["hour"]/24)
    df["month_sin"] = np.sin(2*np.pi*df["month"]/12)
    df["month_cos"] = np.cos(2*np.pi*df["month"]/12)
    df["dow_sin"] = np.sin(2*np.pi*df["day_of_week"]/7)
    df["dow_cos"] = np.cos(2*np.pi*df["day_of_week"]/7)

    df["peak_weekday"] = df["is_peak_hour"] * (1-df["is_weekend"])
    df["holiday_weekend"] = 0
    df["rain_peak"] = (df["weather"] == "Rain").astype(int) * df["is_peak_hour"]

    # Time-series lags
    df["lag_1h"] = df.groupby("junction_id")[TARGET].shift(1)
    df["lag_24h"] = df.groupby("junction_id")[TARGET].shift(24)
    df["lag_168h"] = df.groupby("junction_id")[TARGET].shift(168)
    df["rolling_3h"] = df.groupby("junction_id")[TARGET].transform(lambda x: x.rolling(3).mean())
    df["rolling_6h"] = df.groupby("junction_id")[TARGET].transform(lambda x: x.rolling(6).mean())
    
    df = df.dropna().reset_index(drop=True)
    return df, le_j, le_w

# ════════════════════════════════════════════════════════════
#  3. TRAINING (RF, LR, ISOLATION FOREST)
# ════════════════════════════════════════════════════════════
def train_and_save(df, le_j, le_w):
    print("--- [3/4] Training Models (RF, LR, Anomaly)... ---")
    X = df[FEATURES]; y = df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    rf = RandomForestRegressor(n_estimators=100, max_depth=15, n_jobs=-1).fit(X_train, y_train)
    lr = LinearRegression().fit(X_train, y_train)
    iso = IsolationForest(contamination=0.05, random_state=42).fit(df[[TARGET]])

    thresholds = {
        "moderate": float(df[TARGET].quantile(0.30)),
        "high": float(df[TARGET].quantile(0.70)),
        "very_high": float(df[TARGET].quantile(0.90))
    }

    feat_imp = {k: round(v, 4) for k, v in sorted(zip(FEATURES, rf.feature_importances_), key=lambda x: -x[1])}

    lag_meds = {jid: {col: float(df[df["junction_id"]==jid][col].median()) 
                for col in ["lag_1h","lag_24h","lag_168h","rolling_3h","rolling_6h","temperature_c","humidity_pct"]} 
                for jid in df["junction_id"].unique()}

    pkg = {
        "rf": rf, "lr": lr, "iso_forest": iso,
        "encoders": {"junction": le_j, "weather": le_w},
        "metrics": {
            "rf": {"r2": round(r2_score(y_test, rf.predict(X_test)), 4), "mae": round(mean_absolute_error(y_test, rf.predict(X_test)), 1)},
            "lr": {"r2": round(r2_score(y_test, lr.predict(X_test)), 4), "mae": round(mean_absolute_error(y_test, lr.predict(X_test)), 1)}
        },
        "feat_imp": feat_imp,
        "thresholds": thresholds,
        "lag_meds": lag_meds
    }

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(pkg, f)
    print(f"--- [4/4] SUCCESS! Model Saved (R²: {pkg['metrics']['rf']['r2']}) ---")

# ════════════════════════════════════════════════════════════
#  4. SERVING HELPERS
# ════════════════════════════════════════════════════════════
def load_model():
    with open(MODEL_PATH, "rb") as f: return pickle.load(f)

def classify_volume(v, thresholds=None):
    t = thresholds or {"moderate": 400, "high": 900, "very_high": 1500}
    if v < t["moderate"]:  return "LOW", "#10d97e"
    if v < t["high"]:      return "MODERATE", "#f5a623"
    if v < t["very_high"]: return "HIGH", "#ff4d4d"
    return "VERY HIGH", "#9b6dff"

def make_prediction(pkg, hour, dow, month, weather, junction_id, is_holiday=0):
    lm = pkg["lag_meds"].get(junction_id, list(pkg["lag_meds"].values())[0])
    try:
        j_enc = pkg["encoders"]["junction"].transform([junction_id])[0]
        w_enc = pkg["encoders"]["weather"].transform([weather])[0]
    except: j_enc, w_enc = 0, 0

    row = pd.DataFrame([[
        hour, dow, month, int(dow >= 5), is_holiday, int(hour in [8,9,18,19]),
        28, 50, 0, 10, j_enc, w_enc,
        math.sin(2*np.pi*hour/24), math.cos(2*np.pi*hour/24),
        math.sin(2*np.pi*month/12), math.cos(2*np.pi*month/12),
        math.sin(2*np.pi*dow/7), math.cos(2*np.pi*dow/7),
        int(hour in [8,9,18,19])*(1-int(dow>=5)), 0, 0,
        lm["lag_1h"], lm["lag_24h"], lm["lag_168h"], lm["rolling_3h"], lm["rolling_6h"]
    ]], columns=FEATURES)
    return max(0, int(pkg["rf"].predict(row)[0]))

# ════════════════════════════════════════════════════════════
#  MAIN EXECUTION BLOCK
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if os.path.exists(CSV_PATH):
        print(f"--- [1/4] Loading Repository Dataset: {CSV_PATH} ---")
        df = pd.read_csv(CSV_PATH)
    else:
        df = generate_dataset()

    df_feat, le_j, le_w = feature_engineering(df)
    train_and_save(df_feat, le_j, le_w)

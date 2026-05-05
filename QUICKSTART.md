# 🚀 Quick Start Guide - Real-Time TrafficAI

## ⚡ 5-Minute Setup

### 1. Get an API Key (Choose One)

**Option A: Google Distance Matrix API**
```bash
1. Go to https://console.cloud.google.com
2. Create new project
3. Search "Distance Matrix API" → Enable it
4. Go to Credentials → Create API Key
5. Copy the key
```

**Option B: TomTom API**
```bash
1. Go to https://developer.tomtom.com
2. Sign up / Login
3. Go to Dashboard → API Keys
4. Copy your API key
```

### 2. Configure Backend

```bash
# Navigate to project root
cd "c:\Users\Rajesh\Desktop\jaypee\t"

# Copy example env file
copy .env.example .env

# Edit .env and paste your API key
# For Google:
API_PROVIDER=google
GOOGLE_API_KEY=AIzaSyD...

# For TomTom:
API_PROVIDER=tomtom
TOMTOM_API_KEY=xxxxxxx...
```

### 3. Install & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
cd backend
python app.py

# Server starts at http://localhost:5000
```

### 4. Test in Browser

1. Open `http://localhost:5000`
2. Click **"Predictor"** tab
3. Select origin and destination
4. Click **"GET ETA & ALERTS →"**
5. See live ETA with traffic status!

---

## 📋 What Changed?

### ❌ Removed (Old ML System)
- `/api/predict/` - Traffic volume prediction
- `/api/forecast/` - 24-hour volume forecast
- `/api/routes` - ML-based route ranking
- `model.py` - Random Forest model (105K dataset)
- ML model inference logic
- Hour slider (predictor tab)

### ✅ Added (New Real-Time System)
- `/api/realtime/eta` - Live ETA calculation
- `/api/realtime/reroute` - Smart rerouting with alternatives
- `/api/realtime/compare` - Multi-route comparison
- `/api/realtime/alerts` - Traffic alerts generation
- `/api/junctions` - Available locations list
- `realtime_api.py` - Google/TomTom API integration
- `traffic_logic.py` - Delay index & routing logic
- `config.py` - API keys & locations config

### ✨ Improved UI
- **Predictor tab:** Changed from volume prediction to ETA
- **Removed:** Hour slider, day selector, weather selector
- **Added:** Origin/Destination dropdown, Alert banner, Route recommendations
- **Display:** ETA time, Delay index %, Traffic color (RED/YELLOW/GREEN)

---

## 📊 Key Metrics

| Feature | Old System | New System |
|---------|-----------|-----------|
| Data Source | Historical CSV (105K) | Live APIs |
| Prediction | Traffic Volume (cars/hr) | ETA (mins) |
| Update Frequency | Static | Real-time |
| Delay Detection | Histogram analysis | Delay Index formula |
| Rerouting | Rule-based (hardcoded) | Dynamic (live traffic) |
| Alerts | None | High-traffic warnings |
| Configuration | Hardcoded | `.env` file |
| API Keys | None | Required (Google/TomTom) |

---

## 🔑 New Configuration

### `backend/config.py`

**Bhopal Junctions Available:**
```
"db_mall"         → DB Mall, Bhopal (23.1815, 77.4104)
"mp_nagar"        → MP Nagar, Bhopal (23.2032, 77.4150)
"board_office"    → Board Office, Bhopal (23.1844, 77.3944)
"hamidia_road"    → Hamidia Road, Bhopal (23.1896, 77.4076)
"new_market"      → New Market, Bhopal (23.1738, 77.4233)
"karond"          → Karond, Bhopal (23.2332, 77.4272)
"arera_colony"    → Arera Colony, Bhopal (23.1950, 77.3850)
"shyamla_hills"   → Shyamla Hills, Bhopal (23.1750, 77.4450)
```

**Delay Index Thresholds:**
```
GREEN:  0.0 - 0.2  (0-20% delay) ✅ Light traffic
YELLOW: 0.2 - 0.4  (20-40% delay) ⚠️ Moderate traffic
RED:    0.4+       (40%+ delay) 🔴 Heavy traffic
```

---

## 📡 Real-Time API Workflow

### Step 1: Fetch Live Data
```
Google Distance Matrix API
├─ Origin: (23.1815, 77.4104)
├─ Destination: (23.2032, 77.4150)
└─ Returns: {duration, duration_in_traffic, distance}
```

### Step 2: Calculate Delay Index
```
delay_index = (duration_in_traffic - duration) / duration
Example: (15 - 10) / 10 = 0.5 (50% delay)
```

### Step 3: Classify Traffic
```
if delay_index < 0.2 → GREEN
if delay_index < 0.4 → YELLOW
else                  → RED
```

### Step 4: Generate Alerts
```
if delay_index > 0.4:
  ├─ Show RED alert banner
  ├─ Suggest alternative routes
  └─ Calculate time savings
```

### Step 5: Smart Rerouting
```
If primary route is HIGH:
  ├─ Fetch alternatives (2-3 route options)
  ├─ Compare durations
  ├─ Rank by ETA
  └─ Show "⭐ Recommended" option
```

---

## 🎯 Example Request/Response

### Request (POST /api/realtime/eta)
```json
{
  "origin_id": "db_mall",
  "destination_id": "mp_nagar"
}
```

### Response
```json
{
  "route": {
    "origin": "DB Mall, Bhopal",
    "destination": "MP Nagar, Bhopal",
    "distance_km": 4.2,
    "duration_normal_mins": 10,
    "duration_live_mins": 15,
    "delay_index": 0.5,
    "eta": {
      "arrival_time": "10:45 AM",
      "minutes": 15
    },
    "traffic_status": {
      "status": "RED",
      "color": "#ff4d4d",
      "description": "Heavy traffic - Significant delays expected",
      "severity": 2
    },
    "speed_kmh": 16.8,
    "is_high_traffic": true
  },
  "alert": {
    "type": "traffic_alert",
    "severity": 2,
    "status": "RED",
    "message": "⚠️ Heavy traffic on route to MP Nagar",
    "delay_index": 0.5,
    "recommendation": "Consider using alternative route"
  },
  "status": "success"
}
```

---

## 🔍 Testing Endpoints

### Test 1: Check API Status
```bash
curl http://localhost:5000/api/status
```
**Expected:** Shows if API keys are configured

### Test 2: Get Available Junctions
```bash
curl http://localhost:5000/api/junctions
```
**Expected:** JSON list of all Bhopal junctions

### Test 3: Get ETA
```bash
curl -X POST http://localhost:5000/api/realtime/eta \
  -H "Content-Type: application/json" \
  -d '{"origin_id":"db_mall","destination_id":"mp_nagar"}'
```
**Expected:** Live ETA with traffic status

### Test 4: Get Smart Routes
```bash
curl -X POST http://localhost:5000/api/realtime/reroute \
  -H "Content-Type: application/json" \
  -d '{"origin_id":"db_mall","destination_id":"mp_nagar"}'
```
**Expected:** Primary route + alternatives with rankings

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| "API key not configured" | Copy `.env.example` to `.env`, add your API key |
| "Invalid junction ID" | Use lowercase IDs: `db_mall`, not `DB_Mall` |
| 404 on `/api/predict/` | Old endpoint removed! Use `/api/realtime/eta` instead |
| CORS errors | Flask-CORS is configured - check origin headers |
| Slow responses | API calls cache results for 60 seconds |
| "No route found" | Some location pairs may not have available routes |

---

## 📈 Performance Notes

- **Cache:** Responses cached for 60 seconds per route pair
- **Timeout:** API requests timeout after 10 seconds
- **Rate Limiting:** Google API free tier = 25 req/sec, 500 req/day
- **Response Time:** ~2-3 seconds (API + calculation)
- **Database:** No database - all data from API + hardcoded config

---

## 🚄 Next Steps

1. ✅ Get API key
2. ✅ Configure `.env`
3. ✅ Run `python app.py`
4. ✅ Test in browser
5. ✅ Try Predictor tab
6. ✅ Check alternative routes on high traffic

---

## 📞 Support

**Issue?** Check:
1. Is `.env` file created and API key filled?
2. Is server running (`python app.py`)?
3. Is API key valid? (test on provider's console)
4. Are origin/destination IDs correct?
5. Is there internet connectivity?

**Questions?** See `REFACTOR_README.md` for detailed documentation.

---

**Ready?** Run `python app.py` and visit `http://localhost:5000` now! 🎉

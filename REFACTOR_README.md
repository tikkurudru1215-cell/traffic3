# TrafficAI — Bhopal: Real-Time Navigation & Alert System

## 🚀 Overview

This refactored version replaces the static Random Forest ML model with a **Real-Time Navigation & Alert System** that integrates live traffic APIs (Google Distance Matrix or TomTom) for Bhopal.

### Key Features

✅ **Real-Time ETA** - Fetches live traffic duration from Google/TomTom APIs  
✅ **Delay Index Calculation** - (Live Time - Normal Time) / Normal Time → classify as GREEN/YELLOW/RED  
✅ **Smart Rerouting** - Automatically suggests alternative routes if primary route has high traffic  
✅ **Live Alerts** - Triggers alerts when delay index exceeds 0.4 (40% delay)  
✅ **ETA Display** - Shows "Reaching [Destination] in X mins" with color-coded status  
✅ **System Time Aware** - Predictor tab uses current system time automatically (no hour slider)  

---

## 📋 System Architecture

```
Frontend (HTML/JS)
    ↓
Predictor Tab:
    - Select Origin & Destination
    - Click "GET ETA & ALERTS →"
    ↓
Backend (Flask/Python)
    ↓
realtime_api.py:
    - Fetches live data from Google Distance Matrix / TomTom API
    - Caches responses (60-second expiry)
    ↓
traffic_logic.py:
    - Calculates Delay Index
    - Classifies traffic (GREEN/YELLOW/RED)
    - Computes ETA
    - Suggests alternative routes
    ↓
Frontend Display:
    - ETA & Arrival Time
    - Traffic Status (with color)
    - Alert Banner (if high traffic)
    - Route Recommendations
```

---

## 🔧 Installation & Setup

### Step 1: Install Dependencies

```bash
cd backend
pip install -r ../requirements.txt
```

### Step 2: Configure API Keys

1. **Copy `.env.example` to `.env`:**
   ```bash
   cp .env.example .env
   ```

2. **Get API Key** (Choose one):
   - **Google Distance Matrix API:**
     - Go to https://console.cloud.google.com
     - Enable "Distance Matrix API"
     - Create API key
     - Copy to `.env` as `GOOGLE_API_KEY`
   
   - **TomTom API:**
     - Go to https://developer.tomtom.com
     - Sign up for account
     - Generate API key
     - Copy to `.env` as `TOMTOM_API_KEY`
     - Change `API_PROVIDER=tomtom` in `.env`

3. **Edit `.env` file:**
   ```
   API_PROVIDER=google
   GOOGLE_API_KEY=AIzaSyD...[your-key-here]...
   ```

### Step 3: Run the Backend

```bash
cd backend
python app.py
```

The server will start at `http://localhost:5000`

### Step 4: Access the Frontend

Open in browser: `http://localhost:5000`

Go to **"Predictor"** tab to test ETA functionality.

---

## 🎯 How to Use

### Predictor Tab

1. **Select Starting Location** - Choose from 8 Bhopal junctions:
   - DB Mall
   - MP Nagar
   - Board Office
   - Hamidia Road
   - New Market
   - Karond
   - Arera Colony
   - Shyamla Hills

2. **Select Destination** - Choose a different location

3. **Click "GET ETA & ALERTS →"**

4. **Result Panel Shows:**
   - **Destination name**
   - **ETA** (e.g., "10:45 AM")
   - **Minutes** to arrive
   - **Distance** in km
   - **Delay Index** (percentage)
   - **Traffic Status** (GREEN/YELLOW/RED with color bar)
   - **Average Speed** in km/h

5. **Alert Banner** (if delay > 40%):
   - Shows red/yellow banner with alert message
   - Displays delay index percentage
   - Recommends checking alternative routes

6. **Route Recommendations Panel:**
   - **Primary Route** details
   - **Alternative Routes** (if available)
   - **⭐ Recommended Route** with reason

---

## 📡 API Endpoints

### 1. **Get Real-Time ETA**
```
POST /api/realtime/eta
Body: {"origin_id": "db_mall", "destination_id": "mp_nagar"}

Response:
{
  "route": {
    "origin": "DB Mall, Bhopal",
    "destination": "MP Nagar, Bhopal",
    "distance_km": 4.2,
    "duration_live_mins": 12,
    "delay_index": 0.25,
    "eta": {
      "arrival_time": "10:45 AM",
      "minutes": 12
    },
    "traffic_status": {
      "status": "YELLOW",
      "color": "#f5a623",
      "description": "Moderate traffic"
    },
    "is_high_traffic": false
  },
  "alert": null
}
```

### 2. **Get Smart Rerouting**
```
POST /api/realtime/reroute
Body: {"origin_id": "db_mall", "destination_id": "mp_nagar"}

Response:
{
  "primary": {...},
  "alternatives": [
    {
      "via": "via Board Office",
      "duration_live_mins": 10,
      "is_better": true,
      "time_saved_mins": 2
    }
  ],
  "recommended": {
    "reason": "Fastest route with 2 mins saved",
    "route": {...}
  }
}
```

### 3. **Get Multiple Route Comparison**
```
POST /api/realtime/compare
Body: {
  "routes": [
    {"origin_id": "db_mall", "destination_id": "mp_nagar"},
    {"origin_id": "db_mall", "destination_id": "board_office"}
  ]
}
```

### 4. **Get Live Alerts**
```
POST /api/realtime/alerts
Body: {
  "routes": [{"origin_id": "db_mall", "destination_id": "mp_nagar"}]
}

Response:
{
  "alerts": [
    {
      "type": "traffic_alert",
      "status": "RED",
      "message": "⚠️ Heavy traffic on route to MP Nagar",
      "delay_index": 0.65
    }
  ],
  "active_alerts": 1
}
```

### 5. **Get Available Junctions**
```
GET /api/junctions

Response:
{
  "junctions": {
    "db_mall": {
      "name": "DB Mall, Bhopal",
      "lat": 23.1815,
      "lng": 77.4104
    },
    ...
  }
}
```

---

## 🔑 Configuration Details

### `backend/config.py`

```python
# Delay Index Threshold (40% = HIGH traffic)
DELAY_INDEX_THRESHOLD = 0.4

# Traffic Levels
TRAFFIC_LEVELS = {
    "GREEN": {"threshold": 0.2},    # Light traffic (0-20% delay)
    "YELLOW": {"threshold": 0.4},   # Moderate traffic (20-40% delay)
    "RED": {"min_delay": 0.4}       # Heavy traffic (40%+ delay)
}

# Bhopal Junction Coordinates
BHOPAL_JUNCTIONS = {
    "db_mall": {"lat": 23.1815, "lng": 77.4104},
    "mp_nagar": {"lat": 23.2032, "lng": 77.4150},
    ...
}

# Cache & API Config
CACHE_EXPIRY = 60  # seconds
API_TIMEOUT = 10   # seconds
```

---

## 🧮 Delay Index Logic

**Formula:**
```
Delay Index = (Live Time - Normal Time) / Normal Time

Example:
- Normal Time: 10 minutes
- Live Time: 15 minutes
- Delay Index = (15 - 10) / 10 = 0.5 (50% delay)
```

**Classification:**
- **GREEN** (0.0 - 0.2): 0-20% delay → Light traffic ✅
- **YELLOW** (0.2 - 0.4): 20-40% delay → Moderate traffic ⚠️
- **RED** (0.4+): 40%+ delay → Heavy traffic 🔴

**Alert Trigger:**
- If Delay Index > 0.4 → Show red/yellow alert banner
- Recommendation: Use alternative route

---

## 🗂️ Project Structure

```
TrafficAI/
├── backend/
│   ├── app.py                      ✅ REFACTORED - Real-time endpoints
│   ├── config.py                   ✨ NEW - API keys & locations
│   ├── realtime_api.py             ✨ NEW - Google/TomTom integration
│   ├── traffic_logic.py            ✨ NEW - Delay index & rerouting
│   ├── model.py                    (Deprecated - no longer used)
│   ├── routes.py                   (Deprecated - no longer used)
│   └── run.py                      (Deprecated - no longer used)
│
├── frontend/
│   ├── templates/
│   │   └── index.html              ✅ UPDATED - New predictor tab UI
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── app.js
│           ├── predictor.js        ✨ NEW - Real-time ETA logic
│           ├── dashboard.js
│           └── map.js
│
├── .env.example                    ✨ NEW - Configuration template
├── .env                            (Create from .env.example)
├── requirements.txt                ✅ UPDATED - Added requests, python-dotenv
└── README.md                       ✨ NEW - This file
```

---

## 📊 Example Workflow

### User Flow: DB Mall → MP Nagar

1. **User opens Predictor tab**
   - Origin: DB Mall (default)
   - Destination: MP Nagar (default)
   - Current time: 10:30 AM (automatic)

2. **Clicks "GET ETA & ALERTS →"**

3. **Backend fetches live data:**
   - Google API call: "Distance from DB Mall to MP Nagar"
   - Normal time: 10 minutes
   - Live time (with traffic): 15 minutes
   - Delay Index = 0.5 (50%)

4. **Frontend displays:**
   ```
   Reaching MP Nagar in 15 mins
   ETA: 10:45 AM
   Distance: 4.2 km
   Delay Index: 50%
   Status: RED 🔴
   ```

5. **Alert banner shows:**
   ```
   ⚠️ Heavy traffic on route to MP Nagar
   Delay Index: 50%
   Recommendation: Consider using alternative route
   ```

6. **Smart rerouting suggests:**
   ```
   Route 1: Via Board Office (12 mins) - FASTER ✓ Save 3 mins
   Route 2: Via Hamidia Road (14 mins) - SLOWER
   
   ⭐ RECOMMENDED: Route via Board Office
   Arriving by 10:42 AM
   ```

---

## 🔗 API Integration Details

### Google Distance Matrix API

**Requires:**
- API Key with "Distance Matrix API" enabled
- Billing account connected
- Free tier: 25 requests/second, 500 requests/day

**Response Format:**
```json
{
  "rows": [
    {
      "elements": [
        {
          "distance": {"value": 4200},  // meters
          "duration": {"value": 600},   // seconds
          "duration_in_traffic": {"value": 900}  // seconds
        }
      ]
    }
  ]
}
```

### TomTom API

**Requires:**
- API Key from TomTom Developer
- Billing account
- Free tier: 2500 requests/day

**Response Format:**
```json
{
  "routes": [
    {
      "summary": {
        "lengthInMeters": 4200,
        "travelTimeInSeconds": 900
      }
    }
  ]
}
```

---

## 🐛 Troubleshooting

### Issue: "API key not configured"
**Solution:**
1. Create `.env` file from `.env.example`
2. Add your API key: `GOOGLE_API_KEY=AIza...`
3. Restart Flask server

### Issue: "Invalid junction ID"
**Solution:**
- Verify origin/destination IDs match `BHOPAL_JUNCTIONS` keys
- Use: db_mall, mp_nagar, board_office, etc. (lowercase with underscores)

### Issue: API timeout errors
**Solution:**
1. Check internet connectivity
2. Increase `API_TIMEOUT` in config.py (default: 10 seconds)
3. Check API provider status (Google/TomTom)

### Issue: "No route found"
**Solution:**
- Verify coordinates are correct
- Check if locations are reachable
- Some location combinations may not have routes available

---

## 📈 Future Enhancements

- [ ] Real-time incident reporting integration
- [ ] Historical traffic pattern learning
- [ ] Multi-modal route optimization (car/bus/bike)
- [ ] Integration with traffic signals for green-wave routing
- [ ] Push notifications for alert updates
- [ ] Voice guidance for navigation
- [ ] Emission estimation per route

---

## 📞 Support

For issues or questions:
1. Check `.env` configuration
2. Verify API key is valid
3. Check backend logs for error messages
4. Ensure junctions are spelled correctly

---

## 📄 License

JUET Guna Project - TrafficAI Bhopal

**Refactored:** April 2026
**Original ML Model Deprecated:** Replaced with Real-Time APIs

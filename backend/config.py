"""
================================================================
  backend/config.py - Real-Time API & Location Configuration
================================================================
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── API Configuration ────────────────────────────────────────
# Use Google Distance Matrix API or TomTom API
API_PROVIDER = os.getenv("API_PROVIDER", "google")  # 'google' or 'tomtom'
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_GOOGLE_API_KEY_HERE")
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "YOUR_TOMTOM_API_KEY_HERE")

# ── Delay Index Thresholds ───────────────────────────────────
# If (Live Time - Normal Time) / Normal Time > threshold → HIGH
DELAY_INDEX_THRESHOLD = 0.4  # 40% delay threshold

# Traffic level classifications
TRAFFIC_LEVELS = {
    "GREEN": {"threshold": 0.2, "description": "Light traffic"},
    "YELLOW": {"threshold": 0.4, "description": "Moderate traffic"},
    "RED": {"threshold": float('inf'), "description": "Heavy traffic"}
}

# ── Bhopal Junction Coordinates & Locations ──────────────────
BHOPAL_JUNCTIONS = {
    "db_mall": {
        "name": "DB Mall, Bhopal",
        "lat": 23.1815,
        "lng": 77.4104,
        "address": "DB Mall, South TT Nagar, Bhopal"
    },
    "mp_nagar": {
        "name": "MP Nagar, Bhopal",
        "lat": 23.2032,
        "lng": 77.4150,
        "address": "MP Nagar, Bhopal"
    },
    "board_office": {
        "name": "Board Office, Bhopal",
        "lat": 23.1844,
        "lng": 77.3944,
        "address": "Board Office, Bhopal"
    },
    "hamidia_road": {
        "name": "Hamidia Road, Bhopal",
        "lat": 23.1896,
        "lng": 77.4076,
        "address": "Hamidia Road, Bhopal"
    },
    "new_market": {
        "name": "New Market, Bhopal",
        "lat": 23.1738,
        "lng": 77.4233,
        "address": "New Market, Bhopal"
    },
    "karond": {
        "name": "Karond, Bhopal",
        "lat": 23.2332,
        "lng": 77.4272,
        "address": "Karond, Bhopal"
    },
    "ayodhya": {
        "name": "Ayodhya Bypass, Bhopal",
        "lat": 23.2599,
        "lng": 77.4977,
        "address": "Ayodhya Bypass, Bhopal"
    },
    "bairagarh": {
        "name": "Bairagarh, Bhopal",
        "lat": 23.2872,
        "lng": 77.3378,
        "address": "Bairagarh, Bhopal"
    }
}

# ── Alternative Routes (Waypoints for Rerouting) ──────────────
ALTERNATIVE_ROUTES = {
    "db_mall_to_mp_nagar": {
        "primary": {
            "name": "Route A: Direct via SY Road",
            "waypoints": ["db_mall", "mp_nagar"],
            "alternate_waypoints": []
        },
        "alternate_1": {
            "name": "Route B: Via Hamidia Road",
            "waypoints": ["db_mall", "hamidia_road", "mp_nagar"],
            "alternate_waypoints": []
        },
        "alternate_2": {
            "name": "Route C: Via Ring Road",
            "waypoints": ["db_mall", "karond", "mp_nagar"],
            "alternate_waypoints": []
        }
    }
}

# ── API Request Configuration ────────────────────────────────
API_TIMEOUT = 10  # seconds
API_RETRY_COUNT = 2
CACHE_EXPIRY = 60  # seconds (cache real-time data for 60 seconds)

# ── Alert Configuration ──────────────────────────────────────
ALERT_CONFIG = {
    "high_delay_threshold": 0.4,
    "very_high_delay_threshold": 0.6,
    "alert_duration": 3600  # seconds
}

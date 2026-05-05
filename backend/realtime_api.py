"""
================================================================
  backend/realtime_api.py - Real-Time Traffic Data Integration
================================================================
Handles Google Distance Matrix API and TomTom API calls
"""
import requests
import time
import math
from datetime import datetime
from config import (
    GOOGLE_API_KEY, TOMTOM_API_KEY, API_PROVIDER, 
    API_TIMEOUT, API_RETRY_COUNT, CACHE_EXPIRY,
    BHOPAL_JUNCTIONS
)

# ── API Response Cache ───────────────────────────────────────
_cache = {}

JUNCTION_ALIASES = {
    "db mall": "db_mall",
    "dbmall": "db_mall",
    "mp nagar": "mp_nagar",
    "mpnagar": "mp_nagar",
    "board office": "board_office",
    "hamidia road": "hamidia_road",
    "new market": "new_market",
    "karond": "karond",
    "ayodhya": "ayodhya",
    "bairagarh": "bairagarh",
}

def normalize_junction_id(value):
    """Accept UI labels like 'DB Mall' as well as config IDs."""
    raw = str(value or "").strip()
    key = raw.lower().replace("-", " ").replace("_", " ")
    compact = key.replace(" ", "")
    normalized = key.replace(" ", "_")
    return JUNCTION_ALIASES.get(key) or JUNCTION_ALIASES.get(compact) or (
        normalized if normalized in BHOPAL_JUNCTIONS else raw
    )

def _coords_for(value):
    junction_id = normalize_junction_id(value)
    junction = BHOPAL_JUNCTIONS.get(junction_id)
    if junction:
        return junction["lat"], junction["lng"], junction["name"]

    try:
        lat, lng = [float(part.strip()) for part in str(value).split(",", 1)]
        return lat, lng, str(value)
    except (TypeError, ValueError):
        fallback = BHOPAL_JUNCTIONS["db_mall"]
        return fallback["lat"], fallback["lng"], str(value)

def _haversine_m(lat1, lon1, lat2, lon2):
    radius_m = 6_371_000
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def _synthetic_traffic_data(origin_id, destination_id):
    """Deterministic demo data when no paid traffic API key is configured."""
    o_lat, o_lng, origin_name = _coords_for(origin_id)
    d_lat, d_lng, destination_name = _coords_for(destination_id)
    distance = max(800, int(_haversine_m(o_lat, o_lng, d_lat, d_lng)))

    hour = datetime.now().hour
    peak_multiplier = 1.55 if hour in (8, 9, 17, 18, 19) else 1.15 if 7 <= hour <= 21 else 0.85
    duration = max(300, int(distance / (34 / 3.6)))
    duration_in_traffic = int(duration * peak_multiplier)

    return {
        "duration_in_traffic": duration_in_traffic,
        "duration": duration,
        "distance": distance,
        "origin_name": origin_name,
        "destination_name": destination_name,
        "status": "success",
        "source": "synthetic",
        "timestamp": time.time(),
    }

def _get_cache_key(origin_id, destination_id):
    """Generate cache key for API responses."""
    return f"{origin_id}_{destination_id}"

def _is_cache_valid(cache_key):
    """Check if cached data is still valid."""
    if cache_key not in _cache:
        return False
    cached_time = _cache[cache_key].get("timestamp", 0)
    return time.time() - cached_time < CACHE_EXPIRY

def _clear_cache():
    """Clear all cached data."""
    global _cache
    _cache = {}

# ── Google Distance Matrix API ───────────────────────────────

def fetch_google_distance_matrix(origin_id, destination_id):
    """
    Fetch live traffic data from Google Distance Matrix API.
    
    Args:
        origin_id (str): Origin junction ID from BHOPAL_JUNCTIONS
        destination_id (str): Destination junction ID from BHOPAL_JUNCTIONS
    
    Returns:
        dict: {
            "duration_in_traffic": int (seconds),
            "duration": int (seconds),
            "distance": int (meters),
            "status": str
        }
    """
    cache_key = _get_cache_key(origin_id, destination_id)
    
    # Check cache first
    if _is_cache_valid(cache_key):
        return _cache[cache_key]["data"]
    
    origin_id = normalize_junction_id(origin_id)
    destination_id = normalize_junction_id(destination_id)
    origin = BHOPAL_JUNCTIONS.get(origin_id)
    destination = BHOPAL_JUNCTIONS.get(destination_id)
    
    if not origin or not destination:
        return {"error": "Invalid junction ID", "status": "error"}
    
    origin_coords = f"{origin['lat']},{origin['lng']}"
    dest_coords = f"{destination['lat']},{destination['lng']}"
    
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": origin_coords,
        "destinations": dest_coords,
        "departure_time": "now",
        "traffic_model": "best_guess",
        "key": GOOGLE_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") != "OK":
            return {"error": f"API Error: {data.get('status')}", "status": "error"}
        
        # Extract the first result (single origin-destination pair)
        element = data["rows"][0]["elements"][0]
        
        if element.get("status") != "OK":
            return {"error": f"Route Error: {element.get('status')}", "status": "error"}
        
        result = {
            "duration_in_traffic": element["duration_in_traffic"]["value"],  # seconds
            "duration": element["duration"]["value"],  # seconds
            "distance": element["distance"]["value"],  # meters
            "origin_name": origin["name"],
            "destination_name": destination["name"],
            "status": "success",
            "timestamp": time.time()
        }
        
        # Cache the result
        _cache[cache_key] = {"data": result, "timestamp": time.time()}
        
        return result
    
    except requests.exceptions.RequestException as e:
        return {"error": str(e), "status": "error"}
    except (KeyError, IndexError) as e:
        return {"error": f"Invalid API response: {str(e)}", "status": "error"}

# ── TomTom API (Alternative) ────────────────────────────────

def fetch_tomtom_distance_matrix(origin_id, destination_id):
    """
    Fetch live traffic data from TomTom Routing API.
    
    Args:
        origin_id (str): Origin junction ID from BHOPAL_JUNCTIONS
        destination_id (str): Destination junction ID from BHOPAL_JUNCTIONS
    
    Returns:
        dict: {
            "duration_in_traffic": int (seconds),
            "duration": int (seconds),
            "distance": int (meters),
            "status": str
        }
    """
    cache_key = _get_cache_key(origin_id, destination_id)
    
    # Check cache first
    if _is_cache_valid(cache_key):
        return _cache[cache_key]["data"]
    
    origin_id = normalize_junction_id(origin_id)
    destination_id = normalize_junction_id(destination_id)
    origin = BHOPAL_JUNCTIONS.get(origin_id)
    destination = BHOPAL_JUNCTIONS.get(destination_id)
    
    if not origin or not destination:
        return {"error": "Invalid junction ID", "status": "error"}
    
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{origin['lat']},{origin['lng']}:{destination['lat']},{destination['lng']}/json"
    
    params = {
        "key": TOMTOM_API_KEY,
        "traffic": "true",
        "departAt": "now"
    }
    
    try:
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        if "routes" not in data or len(data["routes"]) == 0:
            return {"error": "No route found", "status": "error"}
        
        route = data["routes"][0]
        summary = route.get("summary", {})
        
        # TomTom returns duration in seconds and distance in meters
        # traffic delay is already included in travelTimeInSeconds
        result = {
            "duration_in_traffic": int(summary.get("travelTimeInSeconds", 0)),
            "duration": int(summary.get("travelTimeInSeconds", 0)),  # Fallback
            "distance": int(summary.get("lengthInMeters", 0)),
            "origin_name": origin["name"],
            "destination_name": destination["name"],
            "status": "success",
            "timestamp": time.time()
        }
        
        # Cache the result
        _cache[cache_key] = {"data": result, "timestamp": time.time()}
        
        return result
    
    except requests.exceptions.RequestException as e:
        return {"error": str(e), "status": "error"}
    except (KeyError, TypeError) as e:
        return {"error": f"Invalid API response: {str(e)}", "status": "error"}

# ── Unified API Fetch ────────────────────────────────────────

def fetch_realtime_data(origin_id, destination_id):
    """
    Fetch real-time traffic data using configured API provider.
    
    Args:
        origin_id (str): Origin junction ID
        destination_id (str): Destination junction ID
    
    Returns:
        dict: Real-time traffic data with duration_in_traffic and duration
    """
    origin_id = normalize_junction_id(origin_id)
    destination_id = normalize_junction_id(destination_id)

    google_unconfigured = GOOGLE_API_KEY in ("", "YOUR_GOOGLE_API_KEY_HERE")
    tomtom_unconfigured = TOMTOM_API_KEY in ("", "YOUR_TOMTOM_API_KEY_HERE")
    if (API_PROVIDER.lower() == "google" and google_unconfigured) or (
        API_PROVIDER.lower() == "tomtom" and tomtom_unconfigured
    ):
        return _synthetic_traffic_data(origin_id, destination_id)

    if API_PROVIDER.lower() == "google":
        return fetch_google_distance_matrix(origin_id, destination_id)
    elif API_PROVIDER.lower() == "tomtom":
        return fetch_tomtom_distance_matrix(origin_id, destination_id)
    else:
        return {"error": "Unknown API provider", "status": "error"}

# ── Batch Fetch for Multiple Routes ──────────────────────────

def fetch_multiple_routes(routes_list):
    """
    Fetch data for multiple routes simultaneously.
    
    Args:
        routes_list (list): List of (origin_id, destination_id) tuples
    
    Returns:
        dict: Route ID → real-time data mapping
    """
    results = {}
    for i, (origin_id, destination_id) in enumerate(routes_list):
        results[f"route_{i}"] = fetch_realtime_data(origin_id, destination_id)
    
    return results

# ── Get Available Junctions ──────────────────────────────────

def get_available_junctions():
    """Return list of all available junction IDs and names."""
    return {k: v["name"] for k, v in BHOPAL_JUNCTIONS.items()}

# ── Get Junction Coordinates ────────────────────────────────

def get_junction_coordinates(junction_id):
    """Get latitude and longitude for a junction."""
    if junction_id not in BHOPAL_JUNCTIONS:
        return None
    
    j = BHOPAL_JUNCTIONS[junction_id]
    return {"lat": j["lat"], "lng": j["lng"], "name": j["name"]}

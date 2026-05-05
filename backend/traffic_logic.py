"""
================================================================
  backend/traffic_logic.py - Delay Index & Smart Rerouting Logic
================================================================
Calculates Delay Index, ETA, and recommends best routes
"""
from datetime import datetime, timedelta
from config import (
    DELAY_INDEX_THRESHOLD, TRAFFIC_LEVELS,
    ALTERNATIVE_ROUTES, BHOPAL_JUNCTIONS
)
from realtime_api import (
    fetch_realtime_data, fetch_multiple_routes,
    get_junction_coordinates
)

# ── Delay Index Calculation ──────────────────────────────────

def calculate_delay_index(duration_in_traffic, duration):
    """
    Calculate Delay Index = (Live Time - Normal Time) / Normal Time
    
    Args:
        duration_in_traffic (int): Live travel time in seconds
        duration (int): Normal travel time in seconds
    
    Returns:
        float: Delay index (0.0 = no delay, 0.5 = 50% delay)
    """
    if duration == 0:
        return 0.0
    
    delay_index = (duration_in_traffic - duration) / duration
    return max(0.0, delay_index)  # Can't be negative

def classify_traffic_status(delay_index):
    """
    Classify traffic status based on Delay Index.
    
    Args:
        delay_index (float): Calculated delay index
    
    Returns:
        dict: {
            "status": "GREEN" | "YELLOW" | "RED",
            "description": str,
            "color": "#xxx",
            "severity": int (0-3)
        }
    """
    if delay_index < TRAFFIC_LEVELS["GREEN"]["threshold"]:
        return {
            "status": "GREEN",
            "description": "Light traffic - No delays expected",
            "color": "#10d97e",
            "severity": 0
        }
    elif delay_index < TRAFFIC_LEVELS["YELLOW"]["threshold"]:
        return {
            "status": "YELLOW",
            "description": "Moderate traffic - Minor delays possible",
            "color": "#f5a623",
            "severity": 1
        }
    else:
        return {
            "status": "RED",
            "description": "Heavy traffic - Significant delays expected",
            "color": "#ff4d4d",
            "severity": 2
        }

# ── ETA Calculation ─────────────────────────────────────────

def calculate_eta(duration_in_traffic_seconds):
    """
    Calculate Estimated Time of Arrival.
    
    Args:
        duration_in_traffic_seconds (int): Travel time in seconds
    
    Returns:
        dict: {
            "arrival_time": "HH:MM AM/PM",
            "minutes": int,
            "hours": int,
            "timestamp": datetime
        }
    """
    now = datetime.now()
    arrival = now + timedelta(seconds=duration_in_traffic_seconds)
    
    minutes = duration_in_traffic_seconds // 60
    hours = minutes // 60
    remaining_mins = minutes % 60
    
    return {
        "arrival_time": arrival.strftime("%I:%M %p"),
        "minutes": minutes,
        "hours": hours,
        "remaining_mins": remaining_mins,
        "timestamp": arrival.isoformat()
    }

# ── Route Analysis ──────────────────────────────────────────

def analyze_single_route(origin_id, destination_id):
    """
    Analyze a single route and return traffic status & ETA.
    
    Args:
        origin_id (str): Origin junction ID
        destination_id (str): Destination junction ID
    
    Returns:
        dict: Complete route analysis with delay index, ETA, and status
    """
    # Fetch real-time data
    rt_data = fetch_realtime_data(origin_id, destination_id)
    
    if rt_data.get("status") == "error":
        return {
            "route_id": f"{origin_id}_to_{destination_id}",
            "status": "error",
            "message": rt_data.get("error", "Unknown error"),
            "traffic_status": None
        }
    
    duration_in_traffic = rt_data["duration_in_traffic"]
    duration_normal = rt_data["duration"]
    distance_meters = rt_data["distance"]
    
    # Calculate Delay Index
    delay_index = calculate_delay_index(duration_in_traffic, duration_normal)
    
    # Classify traffic
    traffic_status = classify_traffic_status(delay_index)
    
    # Calculate ETA
    eta_info = calculate_eta(duration_in_traffic)
    
    # Calculate speed
    speed_kmh = (distance_meters / duration_in_traffic * 3.6) if duration_in_traffic > 0 else 0
    
    return {
        "route_id": f"{origin_id}_to_{destination_id}",
        "origin": rt_data.get("origin_name"),
        "destination": rt_data.get("destination_name"),
        "distance_km": round(distance_meters / 1000, 2),
        "duration_normal_mins": duration_normal // 60,
        "duration_live_mins": duration_in_traffic // 60,
        "delay_index": round(delay_index, 2),
        "eta": eta_info,
        "traffic_status": traffic_status,
        "speed_kmh": round(speed_kmh, 2),
        "is_high_traffic": delay_index > DELAY_INDEX_THRESHOLD,
        "status": "success"
    }

# ── Smart Rerouting Engine ──────────────────────────────────

def get_alternative_routes(origin_id, destination_id):
    """
    Get alternative routes if primary route has high traffic.
    
    Args:
        origin_id (str): Origin junction ID
        destination_id (str): Destination junction ID
    
    Returns:
        dict: Primary + alternative routes with comparison
    """
    # Analyze primary route
    primary_route = analyze_single_route(origin_id, destination_id)
    
    if primary_route.get("status") == "error":
        return {"error": primary_route.get("message"), "status": "error"}
    
    result = {
        "primary": primary_route,
        "alternatives": [],
        "status": "success"
    }
    
    # If primary route is not high traffic, no need for alternatives
    if not primary_route.get("is_high_traffic"):
        return result
    
    # Define alternative waypoints for rerouting
    # Using different junction combinations
    route_key = f"{origin_id}_to_{destination_id}"
    
    # Default alternative routes (can be customized)
    alternative_configs = [
        (origin_id, "bairagarh", destination_id),
        (origin_id, "board_office", destination_id),
        (origin_id, "new_market", destination_id)
    ]
    
    for i, (org, waypoint, dest) in enumerate(alternative_configs):
        # Analyze first leg
        leg1 = analyze_single_route(org, waypoint)
        if leg1.get("status") == "error":
            continue
        
        # Analyze second leg
        leg2 = analyze_single_route(waypoint, dest)
        if leg2.get("status") == "error":
            continue
        
        # Combine results
        total_duration = leg1["eta"]["minutes"] + leg2["eta"]["minutes"]
        total_distance = leg1["distance_km"] + leg2["distance_km"]
        
        # Recalculate ETA for combined route
        combined_eta = calculate_eta(total_duration * 60)
        
        # Determine if this route is better
        total_delay = (leg1["delay_index"] + leg2["delay_index"]) / 2
        traffic_status = classify_traffic_status(total_delay)
        
        result["alternatives"].append({
            "route_id": f"alt_{i}",
            "via": f"via {BHOPAL_JUNCTIONS[waypoint]['name']}",
            "leg1_destination": leg1["destination"],
            "leg2_destination": leg2["destination"],
            "distance_km": round(total_distance, 2),
            "duration_live_mins": total_duration,
            "delay_index": round(total_delay, 2),
            "eta": combined_eta,
            "traffic_status": traffic_status,
            "is_better": total_duration < primary_route["eta"]["minutes"],
            "time_saved_mins": max(0, primary_route["eta"]["minutes"] - total_duration)
        })
    
    # Sort alternatives by duration
    result["alternatives"].sort(key=lambda x: x["duration_live_mins"])
    
    # Recommend best route
    if result["alternatives"]:
        result["recommended"] = {
            "type": "alternative" if result["alternatives"][0]["is_better"] else "primary",
            "route": result["alternatives"][0] if result["alternatives"][0]["is_better"] else primary_route,
            "reason": f"Fastest route with {result['alternatives'][0]['time_saved_mins']} mins saved" 
                      if result["alternatives"][0]["is_better"] 
                      else "Primary route is optimal"
        }
    else:
        result["recommended"] = {
            "type": "primary",
            "route": primary_route,
            "reason": "No better alternatives available"
        }
    
    return result

# ── Generate Alert Messages ─────────────────────────────────

def generate_alert(origin_id, destination_id):
    """
    Generate traffic alert if delay index is high.
    
    Args:
        origin_id (str): Origin junction ID
        destination_id (str): Destination junction ID
    
    Returns:
        dict: Alert info or None if no alert needed
    """
    route_analysis = analyze_single_route(origin_id, destination_id)
    
    if route_analysis.get("status") == "error":
        return None
    
    if not route_analysis.get("is_high_traffic"):
        return None
    
    # Generate alert
    traffic_status = route_analysis["traffic_status"]
    return {
        "type": "traffic_alert",
        "severity": traffic_status["severity"],
        "status": traffic_status["status"],
        "message": f"⚠️ {traffic_status['description']} on route to {route_analysis['destination']}",
        "eta": route_analysis["eta"]["minutes"],
        "delay_index": route_analysis["delay_index"],
        "recommendation": "Consider using alternative route"
    }

# ── Dashboard Summary ────────────────────────────────────────

def get_traffic_summary(origin_id, destination_id):
    """
    Get comprehensive traffic summary for dashboard.
    
    Args:
        origin_id (str): Origin junction ID
        destination_id (str): Destination junction ID
    
    Returns:
        dict: Complete traffic summary with routes and alerts
    """
    route_analysis = analyze_single_route(origin_id, destination_id)
    
    if route_analysis.get("status") == "error":
        return {"error": route_analysis.get("message")}
    
    result = {
        "primary_route": route_analysis,
        "alert": generate_alert(origin_id, destination_id),
        "status": "success"
    }
    
    # Add alternatives if high traffic
    if route_analysis.get("is_high_traffic"):
        alternatives = get_alternative_routes(origin_id, destination_id)
        if alternatives.get("status") == "success":
            result["alternatives"] = alternatives["alternatives"]
            result["recommended"] = alternatives["recommended"]
    
    return result


# ── Carbon Footprint Calculation ────────────────────────────

def calculate_carbon_footprint(delay_minutes):
    """
    Calculate extra CO2 emissions due to traffic delay.
    
    Formula: Extra CO2 (grams) = Delay (minutes) × 15.4
    
    This approximation is based on stop-go traffic patterns
    where each minute of delay increases emissions by ~15.4g CO2.
    
    Args:
        delay_minutes (int or float): Additional travel time in minutes
    
    Returns:
        float: Extra CO2 in grams
    """
    # Carbon coefficient: 15.4 grams CO2 per minute of delay
    CARBON_PER_DELAY_MIN = 15.4
    
    return max(0, delay_minutes * CARBON_PER_DELAY_MIN)


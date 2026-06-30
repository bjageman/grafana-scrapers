#!/usr/bin/env python3
import os
import sys
import json
import time
import math
import requests
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# === CONFIG ===
TOKEN_FILE = "/app/tokens/google_token.json"
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://grafana-influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "neurobomber")
FITBIT_BUCKET = "fitbit"

influx = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
write_api = influx.write_api(write_options=SYNCHRONOUS)

ACTIVITY_TYPES = {
    1: "Biking",
    7: "Walk",
    8: "Run",
    9: "Aerobic Workout",
    10: "Strength Training",
    114: "HIIT",
    115: "Interval Training",
}

def load_credentials():
    try:
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
            return Credentials(
                token=data.get("access_token"),
                refresh_token=data.get("refresh_token"),
                token_uri=data.get("token_uri"),
                client_id=data.get("client_id"),
                client_secret=data.get("client_secret"),
                scopes=data.get("scopes")
            )
    except Exception as e:
        print(f"Error loading credentials from {TOKEN_FILE}: {e}", file=sys.stderr)
        return None

def save_credentials(creds):
    token_data = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

def get_authorized_headers():
    creds = load_credentials()
    if not creds:
        print("No valid credentials found. Please run authorize.py first.", file=sys.stderr)
        sys.exit(1)
    try:
        creds.refresh(Request())
        save_credentials(creds)
    except Exception as e:
        print(f"Failed to refresh token: {e}", file=sys.stderr)
        sys.exit(1)
    return {"Authorization": f"Bearer {creds.token}"}

def write_points(points):
    if not points:
        return
    try:
        write_api.write(bucket=FITBIT_BUCKET, record=points)
        print(f"Wrote {len(points)} points to InfluxDB.")
    except Exception as e:
        print(f"Error writing to InfluxDB: {e}", file=sys.stderr)

def get_session_stats(session, headers):
    start_time = int(session["startTimeMillis"])
    end_time = int(session["endTimeMillis"])
    
    url = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"
    body = {
        "aggregateBy": [
            {"dataTypeName": "com.google.step_count.delta"},
            {"dataTypeName": "com.google.calories.expended"},
            {"dataTypeName": "com.google.distance.delta"},
            {"dataTypeName": "com.google.heart_rate.bpm"}
        ],
        "startTimeMillis": start_time,
        "endTimeMillis": end_time
    }
    
    try:
        r = requests.post(url, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        j = r.json()
        
        steps = 0
        calories = 0.0
        distance_meters = 0.0
        avg_hr = None
        
        buckets = j.get("bucket", [])
        for bucket in buckets:
            datasets = bucket.get("dataset", [])
            for dataset in datasets:
                data_type = dataset.get("dataSourceId", "")
                points = dataset.get("point", [])
                if not points:
                    continue
                
                val_list = points[0].get("value", [])
                if not val_list:
                    continue
                
                if "step_count" in data_type:
                    steps += val_list[0].get("intVal", 0)
                elif "calories" in data_type:
                    calories += val_list[0].get("fpVal", 0.0)
                elif "distance" in data_type:
                    distance_meters += val_list[0].get("fpVal", 0.0)
                elif "heart_rate" in data_type:
                    avg_hr = int(val_list[0].get("fpVal", 0))
                    
        distance_miles = distance_meters / 1609.34
        return {
            "steps": steps,
            "calories": calories,
            "distance": distance_miles,
            "avg_hr": avg_hr
        }
    except Exception as e:
        print(f"Error aggregating session data: {e}", file=sys.stderr)
        return None

def haversine_distance(lat1, lon1, lat2, lon2):
    # Radius of Earth in kilometers
    R = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(phi2 - phi1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def get_session_gps(session, headers):
    start_ns = int(session["startTimeMillis"]) * 1000000
    end_ns = int(session["endTimeMillis"]) * 1000000
    
    data_source = "derived:com.google.location.sample:com.google.android.gms:merge_location_samples"
    url = f"https://www.googleapis.com/fitness/v1/users/me/dataSources/{data_source}/datasets/{start_ns}-{end_ns}"
    
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        j = r.json()
        
        gps_points = []
        points = j.get("point", [])
        for p in points:
            start_time_ns = int(p.get("startTimeNanos", 0))
            values = p.get("value", [])
            if len(values) < 2:
                continue
                
            lat = values[0].get("fpVal")
            lon = values[1].get("fpVal")
            alt = 0.0
            if len(values) > 3:
                alt = values[3].get("fpVal", 0.0)
                
            if lat is not None and lon is not None:
                gps_points.append({
                    "time_ns": start_time_ns,
                    "lat": lat,
                    "lon": lon,
                    "altitude": alt
                })
        
        # Sort GPS points chronologically
        gps_points.sort(key=lambda x: x["time_ns"])
        
        cumulative_dist_km = 0.0
        for i in range(len(gps_points)):
            pt = gps_points[i]
            speed_kph = 0.0
            if i > 0:
                prev_pt = gps_points[i - 1]
                # Distance between points in km
                d_km = haversine_distance(prev_pt["lat"], prev_pt["lon"], pt["lat"], pt["lon"])
                cumulative_dist_km += d_km
                
                # Time difference in seconds
                t_diff_sec = (pt["time_ns"] - prev_pt["time_ns"]) / 1_000_000_000.0
                if t_diff_sec > 0:
                    speed_kph = (d_km / t_diff_sec) * 3600.0
                    # Ignore unrealistic GPS jumps
                    if speed_kph > 100.0:
                        speed_kph = 0.0
            
            pt["speed_kph"] = speed_kph
            pt["distance_m"] = cumulative_dist_km * 1000.0
            
        return gps_points
    except Exception as e:
        print(f"Error fetching GPS data: {e}", file=sys.stderr)
        return []

def main():
    headers = get_authorized_headers()
    
    # Get sessions from the last 30 days
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (30 * 24 * 3600 * 1000)
    
    url = f"https://www.googleapis.com/fitness/v1/users/me/sessions?startTime={datetime.fromtimestamp(start_ms/1000, tz=timezone.utc).isoformat().replace('+00:00', 'Z')}"
    
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        j = r.json()
        
        sessions = j.get("deletedSession", []) + j.get("session", [])
        print(f"Found {len(sessions)} sessions in the last 30 days.")
        
        points = []
        for session in sessions:
            activity_type = session.get("activityType")
            if activity_type not in ACTIVITY_TYPES:
                continue

            activity_name = ACTIVITY_TYPES[activity_type]
            start_ms = int(session["startTimeMillis"])
            end_ms = int(session["endTimeMillis"])
            duration = end_ms - start_ms
            start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)

            print(f"Processing session: {activity_name} on {start_dt.isoformat()}")

            stats = get_session_stats(session, headers)
            p = (Point("Activity Records")
                 .tag("ActivityName", activity_name)
                 .field("duration", int(duration))
                 .field("ActiveDuration", int(duration))
                 .time(start_dt, WritePrecision.NS))
            if stats:
                if stats["avg_hr"] is not None:
                    p.field("AverageHeartRate", int(stats["avg_hr"]))
                if stats["calories"] > 0:
                    p.field("calories", int(stats["calories"]))
                if stats["distance"] > 0:
                    p.field("distance", float(stats["distance"]))
                if stats["steps"] > 0:
                    p.field("steps", int(stats["steps"]))
            points.append(p)

            gps_pts = get_session_gps(session, headers)
            activity_id = f"{start_dt.isoformat()}-{activity_name}"
            for pt in gps_pts:
                points.append(
                    Point("GPS")
                    .tag("ActivityID", activity_id)
                    .field("lat", pt["lat"])
                    .field("lon", pt["lon"])
                    .field("altitude", pt["altitude"])
                    .field("speed_kph", pt["speed_kph"])
                    .field("distance", pt["distance_m"])
                    .time(pt["time_ns"], WritePrecision.NS)
                )

        if points:
            write_points(points)
        else:
            print("No new workouts to write.")
            
    except Exception as e:
        print(f"Error in main run: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

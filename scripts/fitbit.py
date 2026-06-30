#!/usr/bin/env python3
import os
import requests
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# Setup Influx DB connections
URL = os.getenv('INFLUXDB_URL', 'http://grafana-influxdb:8086')
TOKEN = os.getenv('INFLUXDB_TOKEN')
ORG = os.getenv('INFLUXDB_ORG', 'neurobomber')

# Buckets
CUSTOM_BUCKET = "custom"
FITBIT_BUCKET = "fitbit"

TOKEN_FILE = "/app/fitbit.json"
CLIENT_ID = os.getenv("FITBIT_CLIENT_ID")
CLIENT_SECRET = os.getenv("FITBIT_CLIENT_SECRET")
LOCAL_TZ = ZoneInfo(os.getenv("TZ", "America/New_York"))

if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: FITBIT_CLIENT_ID and FITBIT_CLIENT_SECRET environment variables must be set.", file=sys.stderr)
    sys.exit(1)

influx = InfluxDBClient(url=URL, token=TOKEN, org=ORG)
write_api = influx.write_api(write_options=SYNCHRONOUS)

def read_token():
    try:
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def save_token(token_data):
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f)

def refresh_fitbit_token(refresh_token):
    url = "https://api.fitbit.com/oauth2/token"
    headers = {
        "Authorization": requests.auth._basic_auth_str(CLIENT_ID, CLIENT_SECRET),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    r = requests.post(url, headers=headers, data=data, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Fitbit refresh failed: {r.status_code} {r.text}")
    j = r.json()
    expires_in = j.get("expires_in", 8 * 3600)
    return {
        "access_token": j["access_token"],
        "refresh_token": j["refresh_token"],
        "expires_at": int(time.time()) + expires_in,
    }

def ensure_valid_token():
    token = read_token()
    now = int(time.time())
    if token is None:
        print("No token file; please store initial access_token, refresh_token, expires_at in JSON.", file=sys.stderr)
        sys.exit(1)

    refresh_skew = 600  # 10 minutes
    if now >= token.get("expires_at", 0) - refresh_skew:
        print("Access token expired or near expiry; refreshing...")
        new = refresh_fitbit_token(token["refresh_token"])
        save_token(new)
        print("Refreshed token pair.")
        return new["access_token"]
    return token["access_token"]

def fetch_vo2(token):
    url = "https://api.fitbit.com/1/user/-/cardioscore/date/today.json"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        j = r.json()
        cardio_scores = j.get("cardioScore", [])
        if not cardio_scores:
            print("no cardioScore data for today", file=sys.stderr)
            return

        score = cardio_scores[0]["value"]["vo2Max"]
        if score is None:
            print("vo2Max is null", file=sys.stderr)
            return

        value = float(score)
        timestamp_ns = int(time.time() * 1_000_000_000)

        point = Point("fitbit_vo2") \
            .field("value", value) \
            .time(timestamp_ns)
        print(f"Writing VO2 Max point to '{CUSTOM_BUCKET}': {value}")
        write_api.write(bucket=CUSTOM_BUCKET, record=point)
    except Exception as e:
        print(f"error fetching VO2: {e}", file=sys.stderr)

def get_tcx_data(tcx_url, activity_id, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/x-www-form-urlencoded"
    }
    params = {'includePartialTCX': 'false'}
    
    r = requests.get(tcx_url, headers=headers, params=params, timeout=30)
    if r.status_code != 200:
        print(f"Error fetching TCX file: {r.status_code}, {r.text}", file=sys.stderr)
        return []
        
    try:
        root = ET.fromstring(r.text)
    except Exception as e:
        print(f"Error parsing TCX XML: {e}", file=sys.stderr)
        return []

    namespace = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}
    trackpoints = root.findall(".//ns:Trackpoint", namespace)
    
    points = []
    prev_time = None
    prev_distance = None
    
    for i, trkpt in enumerate(trackpoints):
        time_elem = trkpt.find("ns:Time", namespace)
        lat = trkpt.find(".//ns:LatitudeDegrees", namespace)
        lon = trkpt.find(".//ns:LongitudeDegrees", namespace)
        altitude = trkpt.find("ns:AltitudeMeters", namespace)
        distance = trkpt.find("ns:DistanceMeters", namespace)
        heart_rate = trkpt.find(".//ns:HeartRateBpm/ns:Value", namespace)

        if time_elem is not None and lat is not None:
            current_time = datetime.fromisoformat(time_elem.text.strip("Z")).replace(tzinfo=timezone.utc)
            fields = {
                "lat": float(lat.text),
                "lon": float(lon.text)
            }
            if altitude is not None:
                fields["altitude"] = float(altitude.text)
            if distance is not None:
                fields["distance"] = float(distance.text)
                current_distance = float(distance.text)
            else:
                current_distance = None
            if heart_rate is not None:
                fields["heart_rate"] = int(heart_rate.text)
            
            if i > 0 and prev_time is not None and prev_distance is not None and current_distance is not None:
                time_diff = (current_time - prev_time).total_seconds()
                distance_diff = current_distance - prev_distance
                if time_diff > 0:
                    speed_mps = distance_diff / time_diff
                    speed_kph = speed_mps * 3.6
                    fields["speed_kph"] = speed_kph
            
            prev_time = current_time
            prev_distance = current_distance
            
            # Create Point
            p = Point("GPS") \
                .tag("ActivityID", activity_id) \
                .time(current_time, WritePrecision.NS)
            for k, v in fields.items():
                p.field(k, v)
            points.append(p)
            
    return points

def fetch_activities(token):
    # Fetch 50 recent activities
    next_end_date_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    url = "https://api.fitbit.com/1/user/-/activities/list.json"
    headers = {"Authorization": f"Bearer {token}"}
    params = {'beforeDate': next_end_date_str, 'sort': 'desc', 'limit': 50, 'offset': 0}
    
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    
    activities = data.get("activities", [])
    print(f"Fetched {len(activities)} activities from Fitbit API.")
    
    collected_summary_points = []
    collected_gps_points = []
    
    for activity in activities:
        fields = {}
        if 'activeDuration' in activity:
            fields['ActiveDuration'] = int(activity['activeDuration'])
        if 'averageHeartRate' in activity:
            fields['AverageHeartRate'] = int(activity['averageHeartRate'])
        if 'calories' in activity:
            fields['calories'] = int(activity['calories'])
        if 'duration' in activity:
            fields['duration'] = int(activity['duration'])
        if 'distance' in activity:
            fields['distance'] = float(activity['distance'])
        if 'steps' in activity:
            fields['steps'] = int(activity['steps'])
            
        starttime = datetime.fromisoformat(activity['startTime'].replace("Z", "+00:00")).astimezone(timezone.utc)
        activity_name = activity.get('activityName', 'Unknown-Activity')
        
        # Time string format to match: e.g., "2026-06-21T20:51:05+00:00-Bike"
        activity_id = starttime.isoformat() + "-" + activity_name
        
        p = Point("Activity Records") \
            .tag("ActivityName", activity_name) \
            .time(starttime, WritePrecision.NS)
        for k, v in fields.items():
            p.field(k, v)
        collected_summary_points.append(p)
        
        # Check for tcxLink to download GPS track (independent of hasGps)
        tcx_link = activity.get("tcxLink")
        gps_points = []
        if tcx_link:
            print(f"Fetching GPS tracks for {activity_name} on {starttime.isoformat()} (ID: {activity_id})")
            gps_points = get_tcx_data(tcx_link, activity_id, token)
            if gps_points:
                collected_gps_points.extend(gps_points)
                print(f"  Loaded {len(gps_points)} trackpoints.")
                
        # If no GPS points were loaded, but this is a run or interval workout/run, generate synthetic trackpoints
        if not gps_points:
            act_name_lower = activity_name.lower()
            if "run" in act_name_lower or "interval" in act_name_lower:
                print(f"Generating synthetic trackpoints for {activity_name} on {starttime.isoformat()} (ID: {activity_id})")
                
                # Get activity summary stats
                total_duration_ms = activity.get("duration", 0)
                total_duration_sec = total_duration_ms / 1000.0
                
                # Determine total distance in meters
                raw_distance = activity.get("distance", 0.0)
                distance_unit = activity.get("distanceUnit", "Kilometer")
                if distance_unit == "Mile":
                    total_distance_m = raw_distance * 1609.344
                else:
                    # Default/Kilometer
                    total_distance_m = raw_distance * 1000.0
                
                avg_hr = activity.get("averageHeartRate")
                
                # Speed in kph
                if total_duration_sec > 0:
                    speed_kph = (total_distance_m / total_duration_sec) * 3.6
                else:
                    speed_kph = 0.0
                
                # Generate points every 10 seconds to avoid too many points while keeping it smooth
                interval_sec = 10
                num_points = int(total_duration_sec / interval_sec) + 1
                if num_points < 2:
                    num_points = 2
                
                synthetic_points = []
                for i in range(num_points):
                    fraction = i / (num_points - 1)
                    curr_time = starttime + timedelta(seconds=fraction * total_duration_sec)
                    curr_dist = fraction * total_distance_m
                    
                    fields = {
                        "lat": 0.0,
                        "lon": 0.0,
                        "altitude": 0.0,
                        "distance": float(curr_dist),
                        "speed_kph": float(speed_kph)
                    }
                    if avg_hr is not None:
                        fields["heart_rate"] = int(avg_hr)
                    
                    p = Point("GPS") \
                        .tag("ActivityID", activity_id) \
                        .time(curr_time, WritePrecision.NS)
                    for k, v in fields.items():
                        p.field(k, v)
                    synthetic_points.append(p)
                
                collected_gps_points.extend(synthetic_points)
                print(f"  Generated {len(synthetic_points)} synthetic trackpoints.")
                
    # Write to InfluxDB in batch
    if collected_summary_points:
        print(f"Writing {len(collected_summary_points)} activity summaries to '{FITBIT_BUCKET}' bucket...")
        write_api.write(bucket=FITBIT_BUCKET, record=collected_summary_points)
    if collected_gps_points:
        print(f"Writing {len(collected_gps_points)} GPS trackpoints to '{FITBIT_BUCKET}' bucket...")
        # Write in chunks of 500
        chunk_size = 500
        for i in range(0, len(collected_gps_points), chunk_size):
            chunk = collected_gps_points[i:i + chunk_size]
            write_api.write(bucket=FITBIT_BUCKET, record=chunk)
            
    print("Fitbit workouts sync complete.")

def fetch_heartrate(token):
    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now(LOCAL_TZ).date()
    yesterday = today - timedelta(days=1)

    # Intraday (1-minute resolution) for yesterday and today
    intraday_points = []
    for date in [yesterday, today]:
        url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{date}/1d/1min.json"
        try:
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            j = r.json()
            dataset = j.get("activities-heart-intraday", {}).get("dataset", [])
            for entry in dataset:
                t = datetime.combine(date, datetime.strptime(entry["time"], "%H:%M:%S").time())
                dt = t.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
                intraday_points.append(
                    Point("HeartRate_Intraday")
                    .field("value", int(entry["value"]))
                    .time(dt, WritePrecision.NS)
                )
        except Exception as e:
            print(f"Error fetching intraday HR for {date}: {e}", file=sys.stderr)

    if intraday_points:
        print(f"Writing {len(intraday_points)} intraday heart rate points")
        write_api.write(bucket=FITBIT_BUCKET, record=intraday_points)

    # Daily summary (resting HR + zones)
    url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{yesterday}/{today}.json"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        daily_points = []
        zone_points = []
        zone_name_map = {"Out of Range": "Normal", "Fat Burn": "Fat Burn", "Cardio": "Cardio", "Peak": "Peak"}
        for day in r.json().get("activities-heart", []):
            value = day.get("value", {})
            resting_hr = value.get("restingHeartRate")
            dt = datetime.fromisoformat(day["dateTime"]).replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
            zones = value.get("heartRateZones", [])

            if resting_hr is not None:
                p = (
                    Point("HeartRate_Daily")
                    .field("restingHeartRate", int(resting_hr))
                    .time(dt, WritePrecision.NS)
                )
                for zone in zones:
                    name = zone["name"].replace(" ", "_")
                    if "minutes" in zone:
                        p.field(f"zone_{name}_minutes", int(zone["minutes"]))
                daily_points.append(p)

            # Write to legacy "HR zones" measurement so existing panels keep working
            if zones:
                active_mins = sum(z.get("minutes", 0) for z in zones if z["name"] != "Out of Range")
                zp = Point("HR zones").time(dt, WritePrecision.NS).field("activeZoneMinutes", int(active_mins))
                for zone in zones:
                    mapped = zone_name_map.get(zone["name"], zone["name"])
                    mins = zone.get("minutes", 0)
                    zp.field(mapped, int(mins))
                    if mapped != "Normal":
                        zp.field(f"{mapped.lower()}ActiveZoneMinutes", int(mins))
                zone_points.append(zp)

        if daily_points:
            print(f"Writing {len(daily_points)} daily heart rate points")
            write_api.write(bucket=FITBIT_BUCKET, record=daily_points)
        if zone_points:
            print(f"Writing {len(zone_points)} HR zone points")
            write_api.write(bucket=FITBIT_BUCKET, record=zone_points)
    except Exception as e:
        print(f"Error fetching daily HR summary: {e}", file=sys.stderr)


def fetch_calories(token):
    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now(LOCAL_TZ).date()
    yesterday = today - timedelta(days=1)
    points = []
    for date in [yesterday, today]:
        url = f"https://api.fitbit.com/1/user/-/activities/date/{date}.json"
        try:
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            summary = r.json().get("summary", {})
            cal = summary.get("caloriesOut")
            if cal is None:
                continue
            dt = datetime.fromisoformat(str(date)).replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
            points.append(Point("calories").field("value", float(cal)).time(dt, WritePrecision.NS))
        except Exception as e:
            print(f"Error fetching calories for {date}: {e}", file=sys.stderr)
    if points:
        print(f"Writing {len(points)} calorie points")
        write_api.write(bucket=FITBIT_BUCKET, record=points)


def fetch_steps(token):
    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now(LOCAL_TZ).date()
    yesterday = today - timedelta(days=1)
    intraday_points = []
    daily_points = []
    for date in [yesterday, today]:
        url = f"https://api.fitbit.com/1/user/-/activities/steps/date/{date}/1d/1min.json"
        try:
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            j = r.json()
            dataset = j.get("activities-steps-intraday", {}).get("dataset", [])
            for entry in dataset:
                if entry["value"] == 0:
                    continue
                t = datetime.combine(date, datetime.strptime(entry["time"], "%H:%M:%S").time())
                dt = t.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
                intraday_points.append(
                    Point("Steps_Intraday").field("value", int(entry["value"])).time(dt, WritePrecision.NS)
                )
            # Daily total from summary
            for summary in j.get("activities-steps", []):
                total = int(summary.get("value", 0))
                if total == 0:
                    continue
                dt = datetime.fromisoformat(summary["dateTime"]).replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
                daily_points.append(Point("Total Steps").field("value", total).time(dt, WritePrecision.NS))
        except Exception as e:
            print(f"Error fetching steps for {date}: {e}", file=sys.stderr)
    if intraday_points:
        print(f"Writing {len(intraday_points)} intraday step points")
        write_api.write(bucket=FITBIT_BUCKET, record=intraday_points)
    if daily_points:
        print(f"Writing {len(daily_points)} daily step points")
        write_api.write(bucket=FITBIT_BUCKET, record=daily_points)


def fetch_battery(token):
    url = "https://api.fitbit.com/1/user/-/devices.json"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        devices = r.json()
        timestamp_ns = int(time.time() * 1_000_000_000)
        points = []
        for device in devices:
            if not device.get("mac"):  # skip MobileTrack (phone app, no MAC)
                continue
            level = device.get("batteryLevel")
            if level is None:
                continue
            points.append(
                Point("DeviceBattery")
                .tag("device", device.get("deviceVersion", "Unknown"))
                .tag("type", device.get("type", "Unknown"))
                .field("battery_level", int(level))
                .field("battery", device.get("battery", ""))
                .time(timestamp_ns)
            )
        if points:
            print(f"Writing {len(points)} device battery point(s)")
            write_api.write(bucket=FITBIT_BUCKET, record=points)
    except Exception as e:
        print(f"Error fetching battery: {e}", file=sys.stderr)


def fetch_sleep(token):
    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now(LOCAL_TZ).date()
    yesterday = today - timedelta(days=1)

    url = f"https://api.fitbit.com/1.2/user/-/sleep/date/{yesterday}/{today}.json"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        sleep_data = r.json().get("sleep", [])
        points = []
        for entry in sleep_data:
            if not entry.get("isMainSleep"):
                continue
            date_of_sleep = entry.get("dateOfSleep")
            if not date_of_sleep:
                continue
            dt = datetime.fromisoformat(date_of_sleep).replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
            levels = entry.get("levels", {}).get("summary", {})
            p = (
                Point("Sleep")
                .field("minutesAsleep", int(entry.get("minutesAsleep", 0)))
                .field("minutesAwake", int(entry.get("minutesAwake", 0)))
                .field("minutesToFallAsleep", int(entry.get("minutesToFallAsleep", 0)))
                .field("minutesAfterWakeup", int(entry.get("minutesAfterWakeup", 0)))
                .field("timeInBed", int(entry.get("timeInBed", 0)))
                .field("efficiency", int(entry.get("efficiency", 0)))
                .field("duration", int(entry.get("duration", 0)))
                .time(dt, WritePrecision.NS)
            )
            for stage in ["deep", "light", "rem", "wake"]:
                minutes = levels.get(stage, {}).get("minutes")
                if minutes is not None:
                    p.field(f"{stage}Minutes", int(minutes))
            points.append(p)
        if points:
            print(f"Writing {len(points)} sleep points")
            write_api.write(bucket=FITBIT_BUCKET, record=points)
    except Exception as e:
        print(f"Error fetching sleep: {e}", file=sys.stderr)


def fetch_hrv(token):
    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now(LOCAL_TZ).date()
    yesterday = today - timedelta(days=1)

    url = f"https://api.fitbit.com/1/user/-/hrv/date/{yesterday}/{today}.json"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        hrv_data = r.json().get("hrv", [])
        points = []
        for entry in hrv_data:
            date_str = entry.get("dateTime")
            if not date_str:
                continue
            dt = datetime.fromisoformat(date_str).replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
            value = entry.get("value", {})
            daily_rmssd = value.get("dailyRmssd")
            deep_rmssd = value.get("deepRmssd")
            p = Point("HRV").time(dt, WritePrecision.NS)
            if daily_rmssd is not None:
                p.field("dailyRmssd", float(daily_rmssd))
            if deep_rmssd is not None:
                p.field("deepRmssd", float(deep_rmssd))
            points.append(p)
        if points:
            print(f"Writing {len(points)} HRV points")
            write_api.write(bucket=FITBIT_BUCKET, record=points)
    except Exception as e:
        print(f"Error fetching HRV: {e}", file=sys.stderr)


def fetch_breathing_rate(token):
    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now(LOCAL_TZ).date()
    yesterday = today - timedelta(days=1)

    url = f"https://api.fitbit.com/1/user/-/br/date/{yesterday}/{today}.json"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        br_data = r.json().get("br", [])
        points = []
        for entry in br_data:
            date_str = entry.get("dateTime")
            if not date_str:
                continue
            dt = datetime.fromisoformat(date_str).replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
            breathing_rate = entry.get("value", {}).get("breathingRate")
            if breathing_rate is not None:
                points.append(
                    Point("Breathing_Rate")
                    .field("value", float(breathing_rate))
                    .time(dt, WritePrecision.NS)
                )
        if points:
            print(f"Writing {len(points)} breathing rate points")
            write_api.write(bucket=FITBIT_BUCKET, record=points)
    except Exception as e:
        print(f"Error fetching breathing rate: {e}", file=sys.stderr)


def fetch_skin_temperature(token):
    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now(LOCAL_TZ).date()
    yesterday = today - timedelta(days=1)

    url = f"https://api.fitbit.com/1/user/-/temp/skin/date/{yesterday}/{today}.json"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        temp_data = r.json().get("tempSkin", [])
        points = []
        for entry in temp_data:
            date_str = entry.get("dateTime")
            if not date_str:
                continue
            dt = datetime.fromisoformat(date_str).replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
            nightly_relative = entry.get("value", {}).get("nightlyRelative")
            if nightly_relative is not None:
                points.append(
                    Point("Skin_Temperature")
                    .field("nightlyRelative", float(nightly_relative))
                    .time(dt, WritePrecision.NS)
                )
        if points:
            print(f"Writing {len(points)} skin temperature points")
            write_api.write(bucket=FITBIT_BUCKET, record=points)
    except Exception as e:
        print(f"Error fetching skin temperature: {e}", file=sys.stderr)


def fetch_spo2(token):
    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now(LOCAL_TZ).date()
    yesterday = today - timedelta(days=1)

    url = f"https://api.fitbit.com/1/user/-/spo2/date/{yesterday}/{today}/all.json"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        spo2_entries = r.json()
        points = []
        for day_entry in spo2_entries:
            for m in day_entry.get("minutes", []):
                time_str = m.get("minute")
                val = m.get("value")
                if not time_str or val is None:
                    continue
                dt = datetime.fromisoformat(time_str).replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
                points.append(
                    Point("SpO2_Intraday")
                    .field("value", float(val))
                    .time(dt, WritePrecision.NS)
                )
        if points:
            print(f"Writing {len(points)} SpO2 intraday points")
            write_api.write(bucket=FITBIT_BUCKET, record=points)
    except Exception as e:
        print(f"Error fetching SpO2: {e}", file=sys.stderr)


def fetch_weight(token):
    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now(LOCAL_TZ).date()
    yesterday = today - timedelta(days=1)

    url = f"https://api.fitbit.com/1/user/-/body/log/weight/date/{yesterday}/{today}.json"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        weight_data = r.json().get("weight", [])
        points = []
        for entry in weight_data:
            date_str = entry.get("date")
            time_str = entry.get("time")
            if not date_str:
                continue
            dt_str = f"{date_str}T{time_str}" if time_str else date_str
            dt = datetime.fromisoformat(dt_str).replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
            p = Point("Weight").time(dt, WritePrecision.NS)
            weight = entry.get("weight")
            bmi = entry.get("bmi")
            fat = entry.get("fat")
            if weight is not None:
                p.field("value", float(weight))
            if bmi is not None:
                p.field("bmi", float(bmi))
            if fat is not None:
                p.field("fat", float(fat))
            points.append(p)
        if points:
            print(f"Writing {len(points)} weight points")
            write_api.write(bucket=FITBIT_BUCKET, record=points)
    except Exception as e:
        print(f"Error fetching weight: {e}", file=sys.stderr)


def main():
    token = ensure_valid_token()
    fetch_vo2(token)
    fetch_heartrate(token)
    fetch_calories(token)
    fetch_steps(token)
    fetch_battery(token)
    fetch_activities(token)
    fetch_sleep(token)
    fetch_hrv(token)
    fetch_breathing_rate(token)
    fetch_skin_temperature(token)
    fetch_spo2(token)
    fetch_weight(token)

if __name__ == "__main__":
    main()

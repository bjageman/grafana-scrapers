#!/usr/bin/env python3
import os
import requests
from datetime import datetime, timezone
from requests.auth import HTTPBasicAuth
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS


SOURCE_HOST = os.getenv('INFLUXDB_HOST', 'fitbit-influxdb')
SOURCE_PORT = os.getenv('INFLUXDB_PORT', '8086')
SOURCE_DB = os.getenv('INFLUXDB_DATABASE', 'FitbitHealthStats')
SOURCE_USER = os.getenv('INFLUXDB_USERNAME', 'fitbit_user')
SOURCE_PASSWORD = os.getenv('INFLUXDB_PASSWORD', 'e83226e4f9d815de0c41928f4e86ba0c')

WEATHER_HOST = os.getenv('WEATHER_INFLUXDB_HOST', 'weather-influxdb')
WEATHER_PORT = os.getenv('WEATHER_INFLUXDB_PORT', '8086')
WEATHER_DB = os.getenv('WEATHER_INFLUXDB_DATABASE', 'weatherdb')
WEATHER_USER = os.getenv('WEATHER_INFLUXDB_USERNAME', 'telegraf')
WEATHER_PASSWORD = os.getenv('WEATHER_INFLUXDB_PASSWORD', 't3l3gr4f')

TARGET_BUCKET = os.getenv('INFLUXDB_BUCKET')
TARGET_URL = os.getenv('INFLUXDB_URL')
TARGET_TOKEN = os.getenv('INFLUXDB_TOKEN')
TARGET_ORG = os.getenv('INFLUXDB_ORG')

ACTIVITY_QUERY = 'SHOW TAG VALUES FROM "GPS" WITH KEY="ActivityID"'
WEATHER_MEASUREMENT = os.getenv('WEATHER_MEASUREMENT', 'mqtt_consumer')
WEATHER_FIELD = os.getenv('WEATHER_FIELD', 'temp')


def parse_iso(ts):
    return datetime.fromisoformat(ts.replace('Z', '+00:00'))


def influxdb_v1_query(host, port, db, user, password, query):
    url = f'http://{host}:{port}/query'
    params = {'db': db, 'q': query}
    kwargs = {'params': params, 'timeout': 30}

    if user:
        kwargs['auth'] = HTTPBasicAuth(user, password)

    response = requests.get(url, **kwargs)
    response.raise_for_status()
    return response.json()


def get_activity_items():
    data = influxdb_v1_query(
        SOURCE_HOST,
        SOURCE_PORT,
        SOURCE_DB,
        SOURCE_USER,
        SOURCE_PASSWORD,
        ACTIVITY_QUERY,
    )

    items = []
    for result in data.get('results', []):
        for series in result.get('series', []):
            for row in series.get('values', []):
                if len(row) < 2:
                    continue

                activity_id = row[1]

                try:
                    timestamp, exercise_type = activity_id.rsplit('-', 1)
                except ValueError:
                    continue

                items.append({
                    'ID': activity_id,
                    'Exercise Type': exercise_type,
                    'timestamp': timestamp,
                })
    items.sort(key=lambda x: x["timestamp"], reverse=True)
    return items


def get_first_value(data):
    for result in data.get('results', []):
        for series in result.get('series', []):
            columns = series.get('columns', [])
            values = series.get('values', [])
            if not values:
                continue

            row = values[0]
            row_dict = dict(zip(columns, row))
            if 'time' in row_dict and WEATHER_FIELD in row_dict:
                return {
                    'time': row_dict['time'],
                    'value': row_dict[WEATHER_FIELD],
                }

    return None


def get_closest_temperature(timestamp):
    ts = parse_iso(timestamp).astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')

    before_query = (
        f'SELECT "{WEATHER_FIELD}" FROM "{WEATHER_MEASUREMENT}" '
        f"WHERE time <= '{ts}' "
        f'ORDER BY time DESC LIMIT 1'
    )
    after_query = (
        f'SELECT "{WEATHER_FIELD}" FROM "{WEATHER_MEASUREMENT}" '
        f"WHERE time >= '{ts}' "
        f'ORDER BY time ASC LIMIT 1'
    )

    before = get_first_value(influxdb_v1_query(
        WEATHER_HOST,
        WEATHER_PORT,
        WEATHER_DB,
        WEATHER_USER,
        WEATHER_PASSWORD,
        before_query,
    ))
    after = get_first_value(influxdb_v1_query(
        WEATHER_HOST,
        WEATHER_PORT,
        WEATHER_DB,
        WEATHER_USER,
        WEATHER_PASSWORD,
        after_query,
    ))

    if before is None and after is None:
        return None

    if before is None:
        return after

    if after is None:
        return before

    target_dt = parse_iso(timestamp)
    before_dt = parse_iso(before['time'])
    after_dt = parse_iso(after['time'])

    before_diff = abs((target_dt - before_dt).total_seconds())
    after_diff = abs((after_dt - target_dt).total_seconds())

    return before if before_diff <= after_diff else after


def write_exercise_to_weather(items):
    influx = InfluxDBClient(
        url=TARGET_URL,
        token=TARGET_TOKEN,
        org=TARGET_ORG,
    )
    write_api = influx.write_api(write_options=SYNCHRONOUS)

    for item in items:
        closest_temp = get_closest_temperature(item['timestamp'])
        if closest_temp is None:
            continue

        point = (
            Point("exercise_to_weather")
            .tag("id", item["ID"])
            .tag("exercise_type", item["Exercise Type"])
            .tag("weather_time", closest_temp["time"])
            .field("value", float(closest_temp["value"]))
            .time(item["timestamp"])
        )

        print(point)
        write_api.write(bucket=TARGET_BUCKET, record=point)

    influx.close()


if __name__ == "__main__":
    activity_items = get_activity_items()
    write_exercise_to_weather(activity_items)
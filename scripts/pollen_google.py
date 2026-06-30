#!/usr/bin/env python3
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

import os
import requests
from datetime import datetime, timezone

GOOGLE_POLLEN_TOKEN = os.getenv('GOOGLE_POLLEN_TOKEN')
BUCKET = os.getenv('INFLUXDB_BUCKET')
DB_URL = os.getenv('INFLUXDB_URL')
DB_TOKEN = os.getenv('INFLUXDB_TOKEN')
DB_ORG = os.getenv('INFLUXDB_ORG')

# Coordinates for zip 19146 (Philadelphia, PA)
LATITUDE = 39.9400
LONGITUDE = -75.1756

influx = InfluxDBClient(url=DB_URL, token=DB_TOKEN, org=DB_ORG)
write_api = influx.write_api(write_options=SYNCHRONOUS)


def date_to_timestamp(date_obj):
    """Convert Google API date object {year, month, day} to a UTC unix timestamp."""
    dt = datetime(date_obj['year'], date_obj['month'], date_obj['day'], tzinfo=timezone.utc)
    return int(dt.timestamp())


def log_pollen_type(day_info, timestamp):
    for pollen_type_info in day_info.get('pollenTypeInfo', []):
        pollen_type = pollen_type_info['code'].lower()   # GRASS -> grass, TREE -> tree, WEED -> weed
        index_info = pollen_type_info.get('indexInfo', {})
        upi_value = float(index_info.get('value', 0))
        category = index_info.get('category', 'None')

        point = (
            Point("pollen_count")
            .tag("pollen_type", pollen_type)
            .field("upi", upi_value)
            .field("category", category)
            .time(timestamp, WritePrecision.S)
        )
        print(point)
        write_api.write(bucket=BUCKET, record=point)


def log_pollen_species(day_info, timestamp):
    for plant_info in day_info.get('plantInfo', []):
        species_code = plant_info['code'].lower()           # e.g. OAK -> oak
        display_name = plant_info.get('displayName', species_code)
        index_info = plant_info.get('indexInfo', {})
        upi_value = float(index_info.get('value', 0))
        category = index_info.get('category', 'None')

        # Get the parent pollen type from plantDescription if available
        plant_desc = plant_info.get('plantDescription', {})
        pollen_type = plant_desc.get('type', 'UNKNOWN').lower()

        point = (
            Point("pollen_count_by_species")
            .tag("category", pollen_type)
            .tag("species", display_name)
            .tag("species_code", species_code)
            .field("upi", upi_value)
            .field("category_label", category)
            .time(timestamp, WritePrecision.S)
        )
        print(point)
        write_api.write(bucket=BUCKET, record=point)


def fetch_pollen_forecast(days=5):
    """Fetch up to 5 days of pollen forecast from the Google Pollen API."""
    url = "https://pollen.googleapis.com/v1/forecast:lookup"
    params = {
        "key": GOOGLE_POLLEN_TOKEN,
        "location.latitude": LATITUDE,
        "location.longitude": LONGITUDE,
        "days": days,
        "plantsDescription": "true",
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def scrape_pollen_forecast():
    """Fetch and log the full 5-day pollen forecast."""
    data = fetch_pollen_forecast(days=5)
    for day_info in data.get('dailyInfo', []):
        timestamp = date_to_timestamp(day_info['date'])
        log_pollen_type(day_info, timestamp)
        log_pollen_species(day_info, timestamp)
    write_api.close()


if __name__ == "__main__":
    scrape_pollen_forecast()

#!/usr/bin/env python3
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timezone
import os
import requests

BUCKET = os.getenv("INFLUXDB_BUCKET")
DB_URL = os.getenv("INFLUXDB_URL")
DB_TOKEN = os.getenv("INFLUXDB_TOKEN")
DB_ORG = os.getenv("INFLUXDB_ORG")

IMF_INDICATOR = os.getenv("IMF_INDICATOR", "NGDP_RPCH")   # Real GDP growth
IMF_COUNTRIES = os.getenv("IMF_COUNTRIES", "USA").split(",")
IMF_PERIODS = os.getenv("IMF_PERIODS", "2022,2023,2024,2025")

influx = InfluxDBClient(
    url=DB_URL,
    token=DB_TOKEN,
    org=DB_ORG
)
write_api = influx.write_api(write_options=SYNCHRONOUS)

BASE_URL = "https://www.imf.org/external/datamapper/api/v1"

def get_indicator_label(indicator_code):
    url = f"{BASE_URL}/indicators"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    item = data.get(indicator_code, {})
    return item.get("label", indicator_code)

def get_country_labels():
    url = f"{BASE_URL}/countries"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    return {code: meta.get("label", code) for code, meta in data.items()}

def scrape_imf_datamapper():
    indicator_label = get_indicator_label(IMF_INDICATOR)
    country_labels = get_country_labels()

    allowed_countries = {c.strip().upper() for c in IMF_COUNTRIES if c.strip()}
    allowed_periods = {p.strip() for p in IMF_PERIODS.split(",") if p.strip()}

    countries_path = "/".join(sorted(list(allowed_countries)))
    url = f"{BASE_URL}/{IMF_INDICATOR}/{countries_path}"

    response = requests.get(url, timeout=60)
    response.raise_for_status()
    payload = response.json()

    values = payload.get("values", {}).get(IMF_INDICATOR, {})
    if not values:
        raise ValueError(f"No values returned for indicator {IMF_INDICATOR}")

    points = []
    for country_code, series in values.items():
        if allowed_countries and country_code.upper() not in allowed_countries:
            continue
        
        country_name = country_labels.get(country_code, country_code)

        for year, raw_value in series.items():
            if raw_value is None:
                continue

            if allowed_periods and str(year) not in allowed_periods:
                continue

            value = float(raw_value)
            timestamp = datetime(int(year), 1, 1, tzinfo=timezone.utc)

            point = (
                Point("imf_macro")
                .tag("source", "imf_datamapper")
                .tag("indicator", IMF_INDICATOR)
                .tag("indicator_name", indicator_label)
                .tag("country", country_code)
                .tag("country_name", country_name)
                .field("value", value)
                .time(timestamp, WritePrecision.S)
            )

            print(point)
            points.append(point)

    if points:
        write_api.write(bucket=BUCKET, record=points)

if __name__ == "__main__":
    scrape_imf_datamapper()
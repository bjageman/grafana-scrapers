#!/usr/bin/env python3
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime
import os
import requests

FRED_TOKEN=os.getenv('FRED_TOKEN')
BUCKET=os.getenv('INFLUXDB_BUCKET')
DB_URL=os.getenv('INFLUXDB_URL')
DB_TOKEN=os.getenv('INFLUXDB_TOKEN')
DB_ORG=os.getenv('INFLUXDB_ORG')
influx = InfluxDBClient(
    url=DB_URL, 
    token=DB_TOKEN, 
    org=DB_ORG
    )
write_api = influx.write_api(write_options=SYNCHRONOUS)

def scrape_unemployment():
    series_ids = ["UNRATE", "U4RATE", "U6RATE"] 
    base_url = "https://api.stlouisfed.org/fred/series/observations"
    for series_id in series_ids:
        params = {
            "series_id": series_id,
            "api_key": FRED_TOKEN,
            "file_type": "json",
            "sort_order": "desc",     
            "limit": 5,               
            "frequency": "m",         
        }
        response = requests.get(base_url, params=params)
        data = response.json()
        print(data)
        for obs in data["observations"]:
            date = obs["date"]
            value = obs["value"]
            if value == ".":
                continue
            dt = datetime.strptime(date, "%Y-%m-%d")
            timestamp_ns = int(dt.timestamp() * 1_000_000_000)        
            point = Point("unemployment") \
                .field("percentage", float(value)) \
                .tag("type", series_id) \
                .time(timestamp_ns)
            print(point)
            write_api.write(bucket=BUCKET, record=point)

def scrape_treasury_yields():
    series_ids = ["DGS2", "DGS5", "DGS10"]  # 10‑year Treasury yield
    base_url = "https://api.stlouisfed.org/fred/series/observations"

    for series_id in series_ids:
        params = {
            "series_id": series_id,
            "api_key": FRED_TOKEN,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 5,
            "frequency": "d",  # daily data (default for DGS10)
        }
        response = requests.get(base_url, params=params)
        data = response.json()

        for obs in data["observations"]:
            date = obs["date"]
            value = obs["value"]
            if value == ".":
                continue
            dt = datetime.strptime(date, "%Y-%m-%d")
            timestamp_ns = int(dt.timestamp() * 1_000_000_000)

            point = Point("treasury_yield") \
                .field("percentage", float(value)) \
                .tag("series", series_id) \
                .time(timestamp_ns)

            print(point)
            write_api.write(bucket=BUCKET, record=point)

def scrape_fuel_prices():
    series_ids = [
        "GASREGW",    # US Regular All Formulations Gas Price (weekly, $/gallon)
        "GASDESW",    # US Diesel Sales Price (weekly, $/gallon)
    ]
    base_url = "https://api.stlouisfed.org/fred/series/observations"

    for series_id in series_ids:
        params = {
            "series_id": series_id,
            "api_key": FRED_TOKEN,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 5,
            "frequency": "w",  
        }
        response = requests.get(base_url, params=params)
        data = response.json()

        for obs in data["observations"]:
            date = obs["date"]
            value = obs["value"]
            if value == ".":
                continue
            dt = datetime.strptime(date, "%Y-%m-%d")
            timestamp_ns = int(dt.timestamp() * 1_000_000_000)

            point = Point("gas_prices_fred") \
                .field("price_per_gallon", float(value)) \
                .tag("series", series_id) \
                .time(timestamp_ns)

            print(point)
            write_api.write(bucket=BUCKET, record=point)

def scrape_metal_prices():
    series_ids = [
        "PCOPPUSDM",        # Global price of copper (USD / metric ton, monthly)
        "PALUMUSDM",        # Global price of aluminum (USD / metric ton, monthly)
        "PMETAINDEXQ",      # Global metal‑price index (index, quarterly)
    ]
    base_url = "https://api.stlouisfed.org/fred/series/observations"

    for series_id in series_ids:
        params = {
            "series_id": series_id,
            "api_key": FRED_TOKEN,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 5,
            "frequency": "m" if series_id.endswith("M") else "q",
        }
        response = requests.get(base_url, params=params)
        data = response.json()
        print(data)
        for obs in data["observations"]:
            date = obs["date"]
            value = obs["value"] # U.S. Dollars per Metric Ton
            if value == ".":
                continue
            dt = datetime.strptime(date, "%Y-%m-%d")
            timestamp_ns = int(dt.timestamp() * 1_000_000_000)

            # map series ID to metal name
            metal_name = {
                "PCOPPUSDM": "copper",
                "PALUMUSDM": "aluminum",
                "PMETAINDEXQ": "global_index",
            }[series_id]

            point = Point("metal_price") \
                .field("price", float(value)) \
                .tag("metal", metal_name) \
                .tag("series", series_id) \
                .time(timestamp_ns)

            print(point)
            write_api.write(bucket=BUCKET, record=point)
            
def scrape_currency():
    # series_id: invert (True → store 1/value; False → keep as‑is)
    series_configs = {
        "DEXUSEU": False,   # USD per EUR
        "DEXUSAL": True,    # AUD per USD → invert to USD per AUD
        "DEXUSUK": True,    # GBP per USD → invert to USD per GBP
        "DEXCAUS": True,    # CAD per USD → invert to USD per CAD
        "DEXJPUS": True,    # JPY per USD → invert to USD per JPY
        "DEXUSNZ": True,    # NZD per USD → invert to USD per NZD
        "DEXUSAL": True,    # AUD per USD → invert to USD per AUD
        "DEXCHUS": True,    # CNY per USD → invert to USD per CNY
    }
    base_url = "https://api.stlouisfed.org/fred/series/observations"

    for series_id, should_invert in series_configs.items():
        params = {
            "series_id": series_id,
            "api_key": FRED_TOKEN,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 5,
        }
        response = requests.get(base_url, params=params)
        data = response.json()
        print(data)
        for obs in data["observations"]:
            date = obs["date"]
            value = obs["value"]
            if value == ".":
                continue

            rate = float(value)
            if should_invert:
                rate = 1.0 / rate   # now: USD per foreign unit

            dt = datetime.strptime(date, "%Y-%m-%d")
            timestamp_ns = int(dt.timestamp() * 1_000_000_000)

            point = Point("currency_rate") \
                .field("rate", rate) \
                .tag("pair", {
                    "DEXUSEU": "USD/EUR",      # 1 EUR = X USD
                    "DEXJPUS": "USD/JPY",      # 1 JPY = X USD (after 1/value)
                    "DEXCHUS": "USD/CNY",      # 1 CNY = X USD (after 1/value)
                    "DEXUSAL": "USD/AUD",      # 1 AUD = X USD (after 1/value)
                    "DEXUSUK": "USD/GBP",      # 1 GBP = X USD (after 1/value)
                    "DEXCAUS": "USD/CAD",      # 1 CAD = X USD (after 1/value)
                    "DEXUSNZ": "USD/NZD"
                }[series_id]) \
                .tag("series", series_id) \
                .time(timestamp_ns)

            print(point)
            write_api.write(bucket=BUCKET, record=point)

if __name__ == "__main__":
    scrape_unemployment()
    scrape_treasury_yields()
    scrape_fuel_prices()
    scrape_metal_prices()
    scrape_currency()

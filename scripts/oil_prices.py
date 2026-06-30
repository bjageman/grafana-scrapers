
#!/usr/bin/env python3
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime
import os
import requests

OIL_PRICE_TOKEN=os.getenv('OIL_PRICE_TOKEN')
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
seen_periods = set()

SERIES_DATA = [
    {"name": "Diesel", "code": "DIESEL_USD", "series_id": "GASDESW"},
    {"name": "Jet Fuel", "code": "JET_FUEL_USD", "series_id": "WJFUELUSGULF"},
    {"name": "Regular Gasoline", "code": "GASOLINE_USD", "series_id": "GASREGW"},
    {"name": "Natural Gas", "code": "NATURAL_GAS_USD", "series_id": "MHHNGSP"}
]
# 50 requests per month
def scrape_oil_prices():
    for item in SERIES_DATA:
        name = item["name"]
        code = item["code"]
        series_id = item["series_id"]
        url = "https://api.oilpriceapi.com/v1/prices/latest"
        params = {"by_code": code}
        headers = {"Authorization": f"Token {OIL_PRICE_TOKEN}"}

        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()['data']
        price = float(data['price'])
        timestamp = data.get('updated_at', datetime.now())

        point = (
            Point("fuel_prices")
            .field("price_per_gallon", float(price))
            .tag("series", series_id)
            .tag("name", name)
            .tag("source", "oilpricesapi.com")
            .time(timestamp)
        )
        print(point)
        write_api.write(bucket=BUCKET, record=point)

if __name__ == "__main__":
    scrape_oil_prices()

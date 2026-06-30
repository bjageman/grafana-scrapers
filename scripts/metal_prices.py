
#!/usr/bin/env python3
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

import os
import requests

OIL_PRICE_TOKEN=os.getenv('OIL_PRICE_TOKEN')
METAL_PRICE_TOKEN=os.getenv('METAL_PRICE_TOKEN')
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

currency_codes = "XAU,XAG,XPD,XPT"

def scrape_metal_prices():
    
    url = "https://api.metalpriceapi.com/v1/latest"
    params = {
        "api_key": METAL_PRICE_TOKEN,
        "base": "USD",
        "currencies": currency_codes
    }

    response = requests.get(url, params=params)
    data = response.json()
    points = []
    for series_id, price in data['rates'].items():
        if "USD" not in series_id:
            continue
        metal_name = {
                "USDXAU": "gold",
                "USDXAG": "silver",
                "USDXPD": "palladium",
                "USDXPT": "platinum",
            }[series_id]
        price = float(price) *  32150.75 # Convert troy oz to metric ton
        point = (Point("metal_price")
                .tag("series", series_id)
                .tag("metal", metal_name)
                .field("price", price)
                .time(data['timestamp'], WritePrecision.S))
        print(point)
        points.append(point)
        
    if points:
        write_api.write(bucket=BUCKET, record=points)
    write_api.close()
    influx.close()

if __name__ == "__main__":
    scrape_metal_prices()


#!/usr/bin/env python3
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import os
import requests

BUCKET=os.getenv('INFLUXDB_BUCKET')
URL=os.getenv('INFLUXDB_URL')
TOKEN=os.getenv('INFLUXDB_TOKEN')
ORG=os.getenv('INFLUXDB_ORG')
WAQI_API_TOKEN=os.getenv('WAQI_API_TOKEN')

influx = InfluxDBClient(
    url=URL, 
    token=TOKEN, 
    org=ORG
    )
write_api = influx.write_api(write_options=SYNCHRONOUS)
place="philadelphia"

def main():
    
    print(URL, TOKEN, ORG, BUCKET)
    if not WAQI_API_TOKEN:
        raise ValueError("WAQI_API_TOKEN not set")
    resp = requests.get(
        f"https://api.waqi.info/feed/philadelphia/?token={WAQI_API_TOKEN}"
    )
    resp.raise_for_status()
    data = resp.json()
    aqi = float(data["data"]["aqi"])
    timestamp = data["data"]["time"]["iso"]
    print(aqi, timestamp)
    point = Point("aqi") \
            .tag("place", place) \
            .field("value", aqi) \
            .time(timestamp)
    print(point)
    write_api.write(bucket=BUCKET, record=point)

if __name__ == "__main__":
    main()


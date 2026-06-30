#!/usr/bin/env python3
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import os
import requests

BUCKET = os.getenv("INFLUXDB_BUCKET")
URL = os.getenv("INFLUXDB_URL")
TOKEN = os.getenv("INFLUXDB_TOKEN")
ORG = os.getenv("INFLUXDB_ORG")

influx = InfluxDBClient(
    url=URL,
    token=TOKEN,
    org=ORG
)
write_api = influx.write_api(write_options=SYNCHRONOUS)

SERIES = {
    "^SP500EW": "SP500EW",
}

def fetch_yahoo_history(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "range": "max",
        "interval": "1d",
        "includePrePost": "false",
    }

    resp = requests.get(
        url,
        params=params,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    result = data["chart"]["result"][0]
    timestamps = result.get("timestamp", [])
    closes = result["indicators"]["quote"][0]["close"]

    return [
        (int(ts), float(close))
        for ts, close in zip(timestamps, closes)
        if close is not None
    ]

def main():
    print(URL, ORG, BUCKET)

    for symbol, name in SERIES.items():
        pairs = fetch_yahoo_history(symbol)
        print(symbol, len(pairs))

        points = [
            Point("market")
            .field("index", price)
            .tag("symbol", symbol)
            .tag("type", name)
            .time(ts, write_precision="s")
            for ts, price in pairs
        ]

        write_api.write(bucket=BUCKET, record=points)
        print(f"Wrote {len(points)} points for {symbol}")

if __name__ == "__main__":
    main()
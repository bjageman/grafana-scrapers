from influxdb_client import Point
from config import BUCKET
from db import write_api
from client import fetch_observations
from utils import to_ns

SERIES_IDS = ["VIXCLS", "SP500"]

def scrape_markets():
    for series_id in SERIES_IDS:
        for obs in fetch_observations(series_id, frequency="d", limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("market")
                .field("index", float(value))
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)
from influxdb_client import Point
from config import BUCKET
from db import write_api
from client import fetch_observations
from utils import to_ns

SERIES_IDS = ["DGS2", "DGS5", "DGS10", "MORTGAGE30US"]

def scrape_treasury_yields():
    for series_id in SERIES_IDS:
        if series_id == "MORTGAGE30US":
            freq = "w"
        else:
            freq = "d"
        for obs in fetch_observations(series_id, frequency=freq, limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("treasury_yield")
                .field("percentage", float(value))
                .tag("series", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)
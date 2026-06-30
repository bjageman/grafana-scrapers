from influxdb_client import Point
from config import BUCKET
from db import write_api
from client import fetch_observations
from utils import to_ns

SERIES_IDS = [
    "PCOPPUSDM",        # Global price of copper (USD / metric ton, monthly)
    "PALUMUSDM",        # Global price of aluminum (USD / metric ton, monthly)
    "PMETAINDEXQ",      # Global metal‑price index (index, quarterly)
]

METAL_NAME_MAP = {
    "PCOPPUSDM": "copper",
    "PALUMUSDM": "aluminum",
    "PMETAINDEXQ": "global_index",
}

def scrape_metal_prices():
    for series_id in SERIES_IDS:
        freq = "q" if series_id == "PMETAINDEXQ" else "m"
        for obs in fetch_observations(series_id, frequency=freq, limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("metal_price")
                .field("price", float(value))
                .tag("metal", METAL_NAME_MAP[series_id])
                .tag("series", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)
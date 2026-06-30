from influxdb_client import Point
from config import BUCKET
from db import write_api
from client import fetch_observations
from utils import to_ns

CURRENCY_CONFIG = {
    "DEXUSEU": ("USD/EUR", False),   
    "DEXJPUS": ("USD/JPY", True),   
    "DEXCHUS": ("USD/CNY", True),   
    "DEXUSAL": ("USD/AUD", True),   
    "DEXUSUK": ("USD/GBP", True),   
    "DEXCAUS": ("USD/CAD", True),   
    "DEXUSNZ": ("USD/NZD", True),
    "CBBTCUSD": ("USD/BTC", False)   
}

def scrape_currency():
    for series_id, (pair_label, should_invert) in CURRENCY_CONFIG.items():
        for obs in fetch_observations(series_id, limit=5):
            value = obs["value"]
            if value == ".":
                continue

            rate = float(value)
            if should_invert:
                rate = 1.0 / rate 

            point = (
                Point("currency_rate")
                .field("rate", rate)
                .tag("pair", pair_label)
                .tag("series", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)
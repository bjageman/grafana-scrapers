from influxdb_client import Point
from config import BUCKET
from db import write_api
from client import fetch_observations
from utils import to_ns

SERIES_IDS = [
    "MEHOINUSPAA672N", # PA
    "MEHOINUSA672N",   # National
    "MEHOINUSCAA672N", # CA
    "MEHOINUSNYA672N", # NY
    "MEHOINUSTXA672N", # TX
    "MEHOINUSORA672N", # OR
    "MEHOINUSFLA672N", # FL
    "MEHOINUSWAA672N", # WA
    "MHIPA42101A052NCEN", # Philadelphia
    "MHIOR41051A052NCEN", # Portland
    ]

INCOME_INEQUALITY_NAMES = {
    "2020RATIO036061": "New York",
    "2020RATIO006037": "Los Angeles",
    "2020RATIO042101": "Philadelphia",
    "2020RATIO012086": "Miami",
    "2020RATIO006075": "San Francisco",
    "2020RATIO041051": "Portland",
}

def scrape_income():
    for series_id in SERIES_IDS:
        for obs in fetch_observations(series_id, frequency="a", limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("income")
                .field("amount", float(value))
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)

def scrape_income_inequality():
    for series_id, name in INCOME_INEQUALITY_NAMES.items():
        for obs in fetch_observations(series_id, frequency="a", limit=50):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("income_inequality")
                .field("value", float(value))
                .tag("name", name)
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)
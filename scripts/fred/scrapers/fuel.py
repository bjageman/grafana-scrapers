from influxdb_client import Point
from config import BUCKET
from db import write_api
from client import fetch_observations
from utils import to_ns

FUEL_GALLON_NAMES = {
    "GASREGW": "Regular Gasoline",  # US Regular All Formulations Gas Price (weekly, $/gallon)
    "GASDESW": "Diesel",            # US Diesel Sales Price (weekly, $/gallon)
    "WJFUELUSGULF": "Jet Fuel",     # Kerosene-Type Jet Fuel Prices: U.S. Gulf Coast (weekly, $/gallon)
    "MHHNGSP": "Natural Gas"        # Henry Hub Natural Gas
}

FUEL_BARREL_NAMES = {
    "DCOILWTICO": "WTI",               # Crude Oil Prices: West Texas Intermediate (WTI) - Cushing, Oklahoma (daily, $/barrel)
    "DCOILBRENTEU": "Brent - Europe"   # Crude Oil Prices: Brent - Europe
}

def scrape_fuel_prices_by_gallon():
    for series_id, name in FUEL_GALLON_NAMES.items():
        freq = "w"
        if series_id == "MHHNGSP":
            freq = "m"
        for obs in fetch_observations(series_id, frequency=freq, limit=5):
            price = obs["value"]
            if price == ".":
                continue

            point = (
                Point("fuel_prices")
                .field("price_per_gallon", float(price))
                .tag("series", series_id)
                .tag("name", name)
                .tag("source", "FRED")
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)

def scrape_fuel_prices_by_barrel():
    for series_id, name in FUEL_BARREL_NAMES.items():
        for obs in fetch_observations(series_id, frequency="d", limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("fuel_prices")
                .field("price_per_barrel", float(value))
                .tag("series", series_id)
                .tag("name", name)
                .tag("source", "FRED")
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)
from influxdb_client import Point
from config import BUCKET
from db import write_api
from client import fetch_observations
from utils import to_ns

POPULATION_NAMES = {
    "POPTHM": "U.S. Population",
    "CAPOP": "California",
    "FLPOP": "Florida",
    "TXPOP": "Texas",
    "NYNEWY1POP": "NYC",
    "PAPHIL5POP": "Philadelphia",
    "PORPOP": "Portland",
}

def scrape_population():
    for series_id, name in POPULATION_NAMES.items():
        for obs in fetch_observations(series_id, frequency="a", limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("population")
                .field("value", float(value))
                .tag("name", name)
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)

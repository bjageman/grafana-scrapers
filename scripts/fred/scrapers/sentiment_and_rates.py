from influxdb_client import Point
from config import BUCKET
from db import write_api
from client import fetch_observations
from utils import to_ns

# University of Michigan Consumer Sentiment Index (monthly)
SENTIMENT_IDS = ["UMCSENT"]

# Effective Federal Funds Rate (monthly) and target rate upper/lower bounds (daily)
FED_RATE_IDS = {
    "FEDFUNDS": "m",      # Effective Federal Funds Rate, monthly
    "DFEDTARU": "d",      # Target rate upper bound, daily
    "DFEDTARL": "d",      # Target rate lower bound, daily
}

def scrape_consumer_sentiment(observation_start=None):
    limit = None if observation_start else 5
    for series_id in SENTIMENT_IDS:
        for obs in fetch_observations(series_id, frequency="m", limit=limit, observation_start=observation_start):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("consumer_sentiment")
                .field("index", float(value))
                .tag("series", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)

def scrape_fed_rate(observation_start=None):
    limit = None if observation_start else 5
    for series_id, freq in FED_RATE_IDS.items():
        for obs in fetch_observations(series_id, frequency=freq, limit=limit, observation_start=observation_start):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("fed_rate")
                .field("percentage", float(value))
                .tag("series", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)

def backfill_consumer_sentiment():
    scrape_consumer_sentiment(observation_start="2011-01-01")

def backfill_fed_rate():
    scrape_fed_rate(observation_start="2011-01-01")

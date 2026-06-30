from influxdb_client import Point
from config import BUCKET
from db import write_api
from client import fetch_observations
from utils import to_ns

DELINQUENCY_NAMES = {
    "DRCCLACBS": "Credit Card Loans",
    "DRCLACBS": "Consumer Loans",
    "DRSFRMACBS": "Residential Mortgages",
    "DRBLACBS": "Business Loans",
}

CC_BALANCES_NAMES = {
    "RCCCBBALTOT": "Large Bank Consumer"
}

def scrape_delinquency_rate():
    for series_id, name in DELINQUENCY_NAMES.items():
        for obs in fetch_observations(series_id, frequency="q", limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("delinquency_rate")
                .field("percentage", float(value))
                .tag("name", name)
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)

def scrape_credit_card_balances():
    for series_id, name in CC_BALANCES_NAMES.items():
        for obs in fetch_observations(series_id, frequency="q", limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("credit_card_balances")
                .field("dollars", float(value))
                .tag("name", name)
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)


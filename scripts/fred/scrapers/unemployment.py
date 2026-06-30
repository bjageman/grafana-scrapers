from influxdb_client import Point
from config import BUCKET
from db import write_api
from client import fetch_observations
from utils import to_ns

UNEMP_IDS = ["UNRATE", "U4RATE", "U6RATE", "PAUR", "PAPHIL5URN"]
EMP_IDS = ["CIVPART"]
JOBPOST_IDS = ["IHLIDXUS", "IHLIDXUSTPSOFTDEVE"]

def scrape_unemployment():
    for series_id in UNEMP_IDS:
        for obs in fetch_observations(series_id, frequency="m", limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("unemployment")
                .field("percentage", float(value))
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)

def scrape_employment():
    for series_id in EMP_IDS:
        for obs in fetch_observations(series_id, frequency="m", limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("employment")
                .field("percentage", float(value))
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)

def scrape_job_postings():
    for series_id in JOBPOST_IDS:
        for obs in fetch_observations(series_id, frequency="d", limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("job_postings")
                .field("index", float(value))
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)
import os

FRED_TOKEN = os.getenv("FRED_TOKEN")
BUCKET = os.getenv("INFLUXDB_BUCKET")
DB_URL = os.getenv("INFLUXDB_URL")
DB_TOKEN = os.getenv("INFLUXDB_TOKEN")
DB_ORG = os.getenv("INFLUXDB_ORG")
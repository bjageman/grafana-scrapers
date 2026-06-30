from influxdb_client import InfluxDBClient
from config import DB_URL, DB_TOKEN, DB_ORG

influx = InfluxDBClient(url=DB_URL, token=DB_TOKEN, org=DB_ORG)
write_api = influx.write_api()
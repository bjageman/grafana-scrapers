#!/usr/bin/env python3
import csv
import os
import glob
from datetime import datetime
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS


CSV_GLOB = os.getenv("DAYLIO_CSV_GLOB", "/tmp/daylio_export*")
BUCKET = os.getenv("INFLUXDB_BUCKET")
DB_URL = os.getenv("INFLUXDB_URL")
DB_TOKEN = os.getenv("INFLUXDB_TOKEN")
DB_ORG = os.getenv("INFLUXDB_ORG")


MOOD_MAP = {
    "awful": 1,
    "bad": 2,
    "meh": 3,
    "good": 4,
    "rad": 5,
}


def parse_timestamp(full_date: str, time_str: str) -> datetime:
    time_str = (time_str or "").strip().zfill(4)
    return datetime.strptime(f"{full_date} {time_str}", "%Y-%m-%d %H:%M")


influx = InfluxDBClient(url=DB_URL, token=DB_TOKEN, org=DB_ORG)
write_api = influx.write_api(write_options=SYNCHRONOUS)


def import_daylio():
    csv_files = sorted(glob.glob(CSV_GLOB))

    if not csv_files:
        print(f"No matching files found for: {CSV_GLOB}")
        return

    points = []

    for csv_file in csv_files:
        print(f"Importing {csv_file}")

        with open(csv_file, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            for row in reader:
                full_date = row["full_date"].strip()
                time_str = row["time"].strip()
                mood = row["mood"].strip().lower()
                weekday = row.get("weekday", "").strip()
                activities = row.get("activities", "").strip()
                note_title = row.get("note_title", "").strip()
                note = row.get("note", "").strip()

                if mood not in MOOD_MAP:
                    continue

                ts = parse_timestamp(full_date, time_str)

                point = (
                    Point("daylio_entries")
                    .field("mood_score", MOOD_MAP[mood])
                    .field("entry_count", 1)
                    .tag("mood", mood)
                    .tag("weekday", weekday)
                    .tag("source_file", os.path.basename(csv_file))
                    .time(ts, WritePrecision.S)
                )

                if activities:
                    point = point.field("activities", activities)
                if note_title:
                    point = point.field("note_title", note_title)
                if note:
                    point = point.field("note", note)

                print(point)
                points.append(point)

    if points:
        write_api.write(bucket=BUCKET, record=points)
        print(f"Wrote {len(points)} points from {len(csv_files)} files")


if __name__ == "__main__":
    import_daylio()
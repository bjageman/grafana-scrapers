#!/usr/bin/env python3
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from hevy_api.client import HevyClient
import os

client = HevyClient(api_key=os.getenv('HEVY_API_KEY'))
influx = InfluxDBClient(url=os.getenv('INFLUX_URL'), token=os.getenv('INFLUX_TOKEN'), org=os.getenv('INFLUX_ORG'))
write_api = influx.write_api(write_options=SYNCHRONOUS)

BW_KG = 80  # Body Weight in kg

def main():
    workouts = client.get_workouts(page_number=1, page_size=5).workouts
    for workout in workouts:
    # Workout‑level record
        p = Point("hevy_workout") \
            .tag("id", workout.id) \
            .tag("title", workout.title[:100]) \
            .field("duration_min", 0) \
            .time(workout.start_time)
        write_api.write(bucket='hevy', record=p)
        # Exercise‑level record (current, keep this)
        for ex in workout.exercises:
            ex_volume = 0
            ex_reps = 0
            for s in ex.sets:
                weight = float(getattr(s, 'weight_kg', 0) or 0)
                reps = float(getattr(s, 'reps', 0) or 0)
                steps  = float(getattr(s, 'distance_meters', 0) or 0)
                if ex.title.strip() == "Farmers Walk":
                    pseudo_reps = steps / 10
                    ex_volume += weight * pseudo_reps
                    ex_reps   += pseudo_reps 
                elif ex.title.strip() == "Pull Up":
                    ex_volume += BW_KG * reps
                    ex_reps   += reps
                else:
                    ex_volume += weight * reps
                    ex_reps += reps

            ex_p = Point("hevy_exercise") \
                .tag("workout_id", workout.id) \
                .tag("workout_title", workout.title[:100]) \
                .tag("exercise", ex.title[:50]) \
                .field("sets", len(ex.sets)) \
                .field("volume_kg", ex_volume) \
                .field("reps", ex_reps) \
                .time(workout.start_time)

            write_api.write(bucket='hevy', record=ex_p)
    print(f"✅ {len(workouts)} workouts exported (float fields)")

if __name__ == "__main__":
    main()

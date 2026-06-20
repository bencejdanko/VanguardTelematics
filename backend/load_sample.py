"""
load_sample.py
--------------
Loads sample-data/sample.csv into Redis Cloud for testing the API
without the STM32 board connected.

Run once:
  python load_sample.py

Or loop to simulate live streaming:
  python load_sample.py --live
"""

import argparse
import os
import sys
import time

import redis
from config import REDIS_HOST, REDIS_PORT, REDIS_USERNAME, REDIS_PASSWORD, STREAM_KEY, STREAM_MAXLEN

FIELDS = [
    "timestamp",
    "acc_x_mg", "acc_y_mg", "acc_z_mg",
    "gyr_x_mdps", "gyr_y_mdps", "gyr_z_mdps",
    "mag_x_mgauss", "mag_y_mgauss", "mag_z_mgauss",
    "press_hpa",
    "roll_deg", "pitch_deg", "yaw_deg",
]

SAMPLE_CSV = os.path.join(
    os.path.dirname(__file__), "..", "sample-data", "sample.csv"
)


def parse_line(line: str) -> dict | None:
    parts = line.strip().split(",")
    if len(parts) != len(FIELDS):
        return None
    return dict(zip(FIELDS, parts))


def load(live: bool = False):
    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        username=REDIS_USERNAME,
        password=REDIS_PASSWORD,
        decode_responses=True,
    )
    r.ping()
    print(f"Connected to Redis @ {REDIS_HOST}:{REDIS_PORT}")

    with open(SAMPLE_CSV) as f:
        rows = [parse_line(line) for line in f if line.strip()]
        rows = [r_ for r_ in rows if r_ is not None]

    print(f"Loaded {len(rows)} rows from sample CSV")

    count = 0
    pipe = r.pipeline(transaction=False)

    for row in rows:
        pipe.xadd(STREAM_KEY, row, maxlen=STREAM_MAXLEN, approximate=True)
        count += 1

        if count % 50 == 0:
            pipe.execute()
            pipe = r.pipeline(transaction=False)
            print(f"  Pushed {count}/{len(rows)} records…")
            if live:
                time.sleep(0.05)   # ~20 Hz to mimic real sensor rate

    pipe.execute()
    print(f"Done — {count} records written to Redis")
    print(f"  Stream key : {STREAM_KEY}  ({r.xlen(STREAM_KEY)} total entries)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load sample sensor data into Redis")
    parser.add_argument("--live", action="store_true",
                        help="Throttle output to simulate live ~20 Hz sensor rate")
    args = parser.parse_args()
    load(live=args.live)

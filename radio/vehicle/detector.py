import math
import os
import time
from collections import deque
from typing import Callable
import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST     = os.getenv("REDIS_HOST", "coat-generous-snow-13477.db.redis.io")
REDIS_PORT     = int(os.getenv("REDIS_PORT", "13011"))
REDIS_USERNAME = os.getenv("REDIS_USERNAME", "default")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "AU0X7vgAPgJ6lLt6f4yeZQgwlVIyc0XN")
STREAM_KEY     = os.getenv("REDIS_STREAM_KEY", "sensor:stream")
COOLDOWN_S     = 10.0

# Priority order: first match wins when multiple events trigger simultaneously
EVENT_PRIORITY = ['1', '2', '4', '5', '3', '6']


def _mag(fields: dict, x_key: str, y_key: str, z_key: str) -> float:
    vals = [float(fields.get(k, 0)) for k in (x_key, y_key, z_key)]
    return math.sqrt(sum(v * v for v in vals))


class Detector:
    def __init__(self) -> None:
        self.last_event_t    = 0.0
        self.tilt_start      = None   # event 3: sustained tilt onset
        self.still_start     = None   # event 6: post-crash stillness onset
        self.airborne_start  = None   # event 5: airborne onset
        self.impact_streak   = 0      # event 2: consecutive high-g samples
        self.spin_streak     = 0      # event 4: consecutive high-yaw samples
        # ~5 s of gyro history at 100 Hz to detect "was previously active"
        self.recent_gyr: deque[float] = deque(maxlen=500)

    def process(self, fields: dict) -> str | None:
        now = time.monotonic()

        # Always update rolling gyro history
        gyr = _mag(fields, 'gyr_x_mdps', 'gyr_y_mdps', 'gyr_z_mdps')
        self.recent_gyr.append(gyr)

        if now - self.last_event_t < COOLDOWN_S:
            return None

        roll  = abs(float(fields.get('roll_deg', 0)))
        gyr_z = abs(float(fields.get('gyr_z_mdps', 0)))
        acc   = _mag(fields, 'acc_x_mg', 'acc_y_mg', 'acc_z_mg')
        acc_z = abs(float(fields.get('acc_z_mg', 0)))
        was_active = any(g > 5_000 for g in self.recent_gyr)

        triggered: list[str] = []

        # Event 1 — Rollover: tilted hard AND actively rotating
        if roll > 45.0 and gyr > 50_000:
            triggered.append('1')

        # Event 2 — Hard impact: accel spike over threshold for 2+ consecutive samples
        if acc > 4_000:
            self.impact_streak += 1
            if self.impact_streak >= 2:
                triggered.append('2')
        else:
            self.impact_streak = 0

        # Event 4 — Spin-out: high yaw rate for 3+ consecutive samples
        if gyr_z > 90_000:
            self.spin_streak += 1
            if self.spin_streak >= 3:
                triggered.append('4')
        else:
            self.spin_streak = 0

        # Event 5 — Airborne: near-zero vertical accel sustained 0.5 s
        if acc_z < 200:
            if self.airborne_start is None:
                self.airborne_start = now
            elif now - self.airborne_start >= 0.5:
                triggered.append('5')
        else:
            self.airborne_start = None

        # Event 3 — Sustained tilt: leaning AND gyro quiet for 3 s
        if roll > 30.0 and gyr < 5_000:
            if self.tilt_start is None:
                self.tilt_start = now
            elif now - self.tilt_start >= 3.0:
                triggered.append('3')
        else:
            self.tilt_start = None

        # Event 6 — Post-crash stillness: was active, now motionless at angle
        if gyr < 1_000 and roll > 20.0 and was_active:
            if self.still_start is None:
                self.still_start = now
            elif now - self.still_start >= 2.0:
                triggered.append('6')
        else:
            self.still_start = None

        for etype in EVENT_PRIORITY:
            if etype in triggered:
                self.last_event_t = now
                self._reset_streaks()
                return etype

        return None

    def _reset_streaks(self) -> None:
        self.impact_streak  = 0
        self.spin_streak    = 0
        self.tilt_start     = None
        self.still_start    = None
        self.airborne_start = None


def run(on_event: Callable[[str], None]) -> None:
    """Blocks forever on the Redis stream. Calls on_event(event_type) on threshold breach."""
    r = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        username=REDIS_USERNAME, password=REDIS_PASSWORD,
        decode_responses=True, socket_connect_timeout=30, socket_timeout=30, retry_on_timeout=True,
    )
    det = Detector()
    last_id = '$'
    while True:
        results = r.xread({STREAM_KEY: last_id}, block=5000, count=20)
        if not results:
            continue
        for _key, entries in results:
            for entry_id, fields in entries:
                last_id = entry_id
                etype = det.process(fields)
                if etype:
                    on_event(etype)

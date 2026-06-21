"""
Standalone terminal test for the crash/disaster detector.

Phase 1 — warms the rolling baseline on synthetic normal-driving data.
Phase 2 — feeds the real sample.csv (which contains a crash event) through
           the detector and prints any anomaly windows that fire.

No Redis, no API keys, no uAgents required.

Usage:
    cd DataLogFusion
    py backend/test_detector.py
"""

import csv
import random
import sys
from collections import deque
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from statistics import fmean, pstdev
from typing import Deque, Dict, List, Optional

CSV_FILE = Path(__file__).parent.parent / "sample-data" / "sample.csv"

random.seed(42)

# ── Detector config (must match agent.py) ───────────────────────────────────

SAMPLE_RATE_HZ               = 50
BASELINE_WINDOW_SAMPLES      = SAMPLE_RATE_HZ * 30   # 1500
PRE_EVENT_BUFFER_SAMPLES     = SAMPLE_RATE_HZ * 3    # 150
POST_EVENT_COLLECT_SECONDS   = 3
COOLDOWN_SECONDS             = 5
Z_SCORE_THRESHOLD            = 3.0
MIN_FEATURES_TRIGGERED       = 2
CONSECUTIVE_SAMPLES_REQUIRED = 2
EMA_ALPHA                    = 0.3
MIN_BASELINE_SAMPLES         = SAMPLE_RATE_HZ * 5    # 250


# ── Minimal SensorReading dataclass (no uAgents needed) ─────────────────────

@dataclass
class SensorReading:
    timestamp: float
    accel_x: float
    accel_y: float
    accel_z: float
    vibration: float   # gyroscope RMS (mdps)
    temperature: float
    pressure: float


@dataclass
class CrashEventWindow:
    vehicle_id: str
    trigger_timestamp: float
    triggered_features: List[str]
    z_scores: Dict[str, float]
    pre_event_window: List[SensorReading]
    post_event_window: List[SensorReading]


# ── Rolling baseline ─────────────────────────────────────────────────────────

class RollingBaseline:
    def __init__(self, max_samples: int):
        self._values: Deque[float] = deque(maxlen=max_samples)

    def update(self, value: float) -> None:
        self._values.append(value)

    def z_score(self, value: float) -> float:
        if len(self._values) < 2:
            return 0.0
        mean = fmean(self._values)
        std = pstdev(self._values) or 1e-6
        return (value - mean) / std

    @property
    def is_warmed_up(self) -> bool:
        return len(self._values) >= MIN_BASELINE_SAMPLES


# ── Detector (identical logic to agent.py) ───────────────────────────────────

class CrashTriggerDetector:
    def __init__(self, vehicle_id: str):
        self.vehicle_id = vehicle_id
        self._baselines: Dict[str, RollingBaseline] = {
            "accel_mag":     RollingBaseline(BASELINE_WINDOW_SAMPLES),
            "accel_jerk":    RollingBaseline(BASELINE_WINDOW_SAMPLES),
            "vibration":     RollingBaseline(BASELINE_WINDOW_SAMPLES),
            "temp_rate":     RollingBaseline(BASELINE_WINDOW_SAMPLES),
            "pressure_rate": RollingBaseline(BASELINE_WINDOW_SAMPLES),
        }
        self._pre_event_buffer: Deque[SensorReading] = deque(maxlen=PRE_EVENT_BUFFER_SAMPLES)
        self._prev_reading: Optional[SensorReading] = None
        self._ema_accel_jerk     = 0.0
        self._ema_temp_rate      = 0.0
        self._ema_pressure_rate  = 0.0
        self._consecutive_anomalous = 0
        self._cooldown_until     = 0.0
        self._collecting         = False
        self._collect_until      = 0.0
        self._post_event_buffer: List[SensorReading] = []
        self._pending_trigger: Optional[dict] = None

    def _extract_features(self, r: SensorReading) -> Dict[str, float]:
        accel_mag = sqrt(r.accel_x**2 + r.accel_y**2 + r.accel_z**2)
        if self._prev_reading is not None:
            dt = max(r.timestamp - self._prev_reading.timestamp, 1e-3)
            prev_mag = sqrt(
                self._prev_reading.accel_x**2
                + self._prev_reading.accel_y**2
                + self._prev_reading.accel_z**2
            )
            raw_jerk         = (accel_mag - prev_mag) / dt
            raw_temp_rate    = (r.temperature - self._prev_reading.temperature) / dt
            raw_press_rate   = (r.pressure    - self._prev_reading.pressure)    / dt
        else:
            raw_jerk = raw_temp_rate = raw_press_rate = 0.0

        self._ema_accel_jerk     = EMA_ALPHA * raw_jerk       + (1 - EMA_ALPHA) * self._ema_accel_jerk
        self._ema_temp_rate      = EMA_ALPHA * raw_temp_rate  + (1 - EMA_ALPHA) * self._ema_temp_rate
        self._ema_pressure_rate  = EMA_ALPHA * raw_press_rate + (1 - EMA_ALPHA) * self._ema_pressure_rate

        return {
            "accel_mag":     accel_mag,
            "accel_jerk":    self._ema_accel_jerk,
            "vibration":     r.vibration,
            "temp_rate":     self._ema_temp_rate,
            "pressure_rate": self._ema_pressure_rate,
        }

    def process(self, reading: SensorReading) -> Optional[CrashEventWindow]:
        self._pre_event_buffer.append(reading)
        features = self._extract_features(reading)
        self._prev_reading = reading

        if self._collecting:
            self._post_event_buffer.append(reading)
            if reading.timestamp >= self._collect_until:
                return self._finalize_event()
            return None

        z_scores: Dict[str, float] = {}
        for name, value in features.items():
            b = self._baselines[name]
            z_scores[name] = b.z_score(value)
            b.update(value)

        if reading.timestamp < self._cooldown_until:
            return None
        if not all(b.is_warmed_up for b in self._baselines.values()):
            return None

        triggered = [name for name, z in z_scores.items() if abs(z) > Z_SCORE_THRESHOLD]
        if len(triggered) >= MIN_FEATURES_TRIGGERED:
            self._consecutive_anomalous += 1
        else:
            self._consecutive_anomalous = 0

        if self._consecutive_anomalous >= CONSECUTIVE_SAMPLES_REQUIRED:
            self._start_collecting(reading, triggered, z_scores)
        return None

    def _start_collecting(self, reading, triggered, z_scores):
        self._collecting       = True
        self._collect_until    = reading.timestamp + POST_EVENT_COLLECT_SECONDS
        self._post_event_buffer = [reading]
        self._pending_trigger  = {
            "trigger_timestamp":  reading.timestamp,
            "triggered_features": triggered,
            "z_scores":           z_scores,
            "pre_event_snapshot": list(self._pre_event_buffer),
        }
        self._consecutive_anomalous = 0

    def _finalize_event(self) -> CrashEventWindow:
        info  = self._pending_trigger
        event = CrashEventWindow(
            vehicle_id          = self.vehicle_id,
            trigger_timestamp   = info["trigger_timestamp"],
            triggered_features  = info["triggered_features"],
            z_scores            = info["z_scores"],
            pre_event_window    = info["pre_event_snapshot"],
            post_event_window   = list(self._post_event_buffer),
        )
        self._collecting       = False
        self._cooldown_until   = self._post_event_buffer[-1].timestamp + COOLDOWN_SECONDS
        self._post_event_buffer = []
        self._pending_trigger  = None
        return event


# ── Synthetic normal baseline data ──────────────────────────────────────────
# Normal vehicle: ~1g downward, small lateral movement, slow rotation, stable pressure.
# These values are in the same units as the sample.csv (mg, mdps, hPa).

NORMAL_ACC_Z   = 992.0     # mg  (~1g)
NORMAL_VIB     = 350.0     # mdps RMS (gentle movement)
NORMAL_PRESS   = 1013.25   # hPa

def generate_normal_readings(n: int, start_ts: float = 0.0, dt: float = 0.02) -> List[SensorReading]:
    readings = []
    for i in range(n):
        readings.append(SensorReading(
            timestamp   = start_ts + i * dt,
            accel_x     = random.gauss(0.0,        15.0),
            accel_y     = random.gauss(0.0,        15.0),
            accel_z     = random.gauss(NORMAL_ACC_Z, 10.0),
            vibration   = abs(random.gauss(NORMAL_VIB, 60.0)),
            temperature = random.gauss(25.0,        0.05),
            pressure    = random.gauss(NORMAL_PRESS, 0.05),
        ))
    return readings


# ── CSV loading ──────────────────────────────────────────────────────────────

def _ts_to_seconds(ts_str: str) -> float:
    """HH:MM:SS.ss → float seconds."""
    h, m, s = ts_str.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def load_csv(start_ts_offset: float = 0.0) -> List[SensorReading]:
    readings = []
    with open(CSV_FILE, newline="") as f:
        for row in csv.reader(f):
            if len(row) < 14:
                continue
            try:
                ts    = _ts_to_seconds(row[0]) + start_ts_offset
                gyr_x = float(row[4])
                gyr_y = float(row[5])
                gyr_z = float(row[6])
                readings.append(SensorReading(
                    timestamp   = ts,
                    accel_x     = float(row[1]),
                    accel_y     = float(row[2]),
                    accel_z     = float(row[3]),
                    vibration   = sqrt(gyr_x**2 + gyr_y**2 + gyr_z**2),
                    temperature = 25.0,
                    pressure    = float(row[10]),
                ))
            except (ValueError, IndexError):
                continue
    return readings


# ── Event type classification heuristic ─────────────────────────────────────

def classify_event(triggered: List[str]) -> str:
    feat = set(triggered)
    if "vibration" in feat and "accel_mag" in feat and "accel_jerk" in feat:
        return "Hard Impact / Collision"
    if "vibration" in feat and "accel_jerk" in feat:
        return "Spin-Out / Loss of Control"
    if "vibration" in feat and "accel_mag" in feat:
        return "Rollover / Impact"
    if "accel_mag" in feat and "accel_jerk" in feat:
        return "Hard Braking / Collision"
    if "vibration" in feat:
        return "Sustained Rotation Anomaly"
    if "accel_mag" in feat:
        return "Acceleration Anomaly"
    return f"Unknown Anomaly"


# ── Print helpers ────────────────────────────────────────────────────────────

def _bar(z: float, width: int = 18) -> str:
    filled = min(int(abs(z) / max(abs(z), 1) * width), width)
    return "[" + "#" * filled + "." * (width - filled) + f"] z={z:+.1f}"


def print_event(event: CrashEventWindow, event_num: int) -> None:
    label = classify_event(event.triggered_features)
    print(f"\n{'='*62}")
    print(f"  EVENT #{event_num}  —  {label.upper()}")
    print(f"{'='*62}")
    print(f"  Vehicle : {event.vehicle_id}")
    print(f"  Time    : t={event.trigger_timestamp:.3f}s")
    print(f"  Sensors : {', '.join(event.triggered_features)}")
    print()
    print("  Feature z-scores  (threshold = ±3.0):")
    for feat, z in sorted(event.z_scores.items(), key=lambda x: -abs(x[1])):
        marker = " << TRIGGERED" if feat in event.triggered_features else ""
        print(f"    {feat:<16} {_bar(z)}{marker}")
    pre  = len(event.pre_event_window)
    post = len(event.post_event_window)
    print(f"\n  Captured: {pre} pre-event + {post} post-event samples")
    print(f"{'='*62}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("DataLogFusion — Crash Detector Terminal Test")
    print(f"CSV : {CSV_FILE}\n")

    detector = CrashTriggerDetector(vehicle_id="V-001")

    # ── Phase 1: warm baseline on clean synthetic normal data ────────────────
    WARMUP_SAMPLES = MIN_BASELINE_SAMPLES + 50   # a bit more than the minimum
    warmup = generate_normal_readings(WARMUP_SAMPLES, start_ts=0.0, dt=0.02)

    print(f"Phase 1 — warming baseline on {WARMUP_SAMPLES} synthetic normal samples ...")
    for r in warmup:
        detector.process(r)

    warmed = all(b.is_warmed_up for b in detector._baselines.values())
    print(f"Baseline status: {'READY' if warmed else 'NOT READY'}\n")
    if not warmed:
        sys.exit(1)

    # ── Phase 2: feed real CSV data (contains a crash event) ─────────────────
    last_ts = warmup[-1].timestamp
    csv_readings = load_csv(start_ts_offset=last_ts + 0.1)

    print(f"Phase 2 — feeding {len(csv_readings)} rows from sample.csv ...")
    print(f"  (CSV spans {csv_readings[-1].timestamp - csv_readings[0].timestamp:.1f}s of sensor data)\n")

    events: List[CrashEventWindow] = []
    for r in csv_readings:
        result = detector.process(r)
        if result is not None:
            events.append(result)

    # ── Results ───────────────────────────────────────────────────────────────
    if events:
        print(f"Detected {len(events)} anomaly window(s):\n")
        for i, event in enumerate(events, 1):
            print_event(event, i)
    else:
        print("No anomaly windows detected in the CSV data.")
        print("(The CSV may not contain a large enough event relative to the synthetic baseline.)")

    print(f"\nDone. {len(events)} event(s) detected.")


if __name__ == "__main__":
    main()

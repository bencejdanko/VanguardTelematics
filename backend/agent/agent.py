import csv
import random
from collections import deque
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path
from statistics import fmean, pstdev
from typing import Deque, Dict, List, Optional
from uuid import uuid4
import json
import os
import redis.asyncio as aioredis
from dotenv import load_dotenv

from openai import OpenAI
from uagents import Context, Protocol, Agent, Model
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from config import (
    REDIS_HOST, REDIS_PORT, REDIS_USERNAME, REDIS_PASSWORD,
    REDIS_STREAM_KEY, REDIS_LATEST_KEY as LATEST_KEY,
    ASI_API_KEY, AGENT_SEED_PHRASE_DIS
)


# ---------------------------------------------------------------------------
# Sentry Trigger config
# ---------------------------------------------------------------------------

SAMPLE_RATE_HZ = 50
BASELINE_WINDOW_SAMPLES = SAMPLE_RATE_HZ * 30
PRE_EVENT_BUFFER_SAMPLES = SAMPLE_RATE_HZ * 3
POST_EVENT_COLLECT_SECONDS = 3
COOLDOWN_SECONDS = 5
Z_SCORE_THRESHOLD = 3.0
MIN_FEATURES_TRIGGERED = 2
CONSECUTIVE_SAMPLES_REQUIRED = 2
EMA_ALPHA = 0.3
MIN_BASELINE_SAMPLES = SAMPLE_RATE_HZ * 5

VEHICLE_ID = "V-001"
REDIS_CRASH_EVENT_KEY = "latest_crash_event"


# ---------------------------------------------------------------------------
# Message schemas
# ---------------------------------------------------------------------------

class SensorReading(Model):
    timestamp: float
    accel_x: float
    accel_y: float
    accel_z: float
    vibration: float
    temperature: float
    pressure: float


class CrashEventWindow(Model):
    vehicle_id: str
    trigger_timestamp: float
    triggered_features: List[str]
    z_scores: Dict[str, float]
    pre_event_window: List[SensorReading]
    post_event_window: List[SensorReading]


# ---------------------------------------------------------------------------
# Sentry Trigger detector
# ---------------------------------------------------------------------------

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


class CrashTriggerDetector:
    def __init__(self, vehicle_id: str):
        self.vehicle_id = vehicle_id
        self._baselines: Dict[str, RollingBaseline] = {
            "accel_mag": RollingBaseline(BASELINE_WINDOW_SAMPLES),
            "accel_jerk": RollingBaseline(BASELINE_WINDOW_SAMPLES),
            "vibration": RollingBaseline(BASELINE_WINDOW_SAMPLES),
            "temp_rate": RollingBaseline(BASELINE_WINDOW_SAMPLES),
            "pressure_rate": RollingBaseline(BASELINE_WINDOW_SAMPLES),
        }
        self._pre_event_buffer: Deque[SensorReading] = deque(maxlen=PRE_EVENT_BUFFER_SAMPLES)
        self._prev_reading: Optional[SensorReading] = None
        self._ema_accel_jerk = 0.0
        self._ema_temp_rate = 0.0
        self._ema_pressure_rate = 0.0
        self._consecutive_anomalous = 0
        self._cooldown_until = 0.0
        self._collecting = False
        self._collect_until = 0.0
        self._post_event_buffer: List[SensorReading] = []
        self._pending_trigger: Optional[Dict] = None

    def _extract_features(self, reading: SensorReading) -> Dict[str, float]:
        accel_mag = sqrt(reading.accel_x**2 + reading.accel_y**2 + reading.accel_z**2)
        if self._prev_reading is not None:
            dt = max(reading.timestamp - self._prev_reading.timestamp, 1e-3)
            prev_accel_mag = sqrt(
                self._prev_reading.accel_x**2
                + self._prev_reading.accel_y**2
                + self._prev_reading.accel_z**2
            )
            raw_jerk = (accel_mag - prev_accel_mag) / dt
            raw_temp_rate = (reading.temperature - self._prev_reading.temperature) / dt
            raw_pressure_rate = (reading.pressure - self._prev_reading.pressure) / dt
        else:
            raw_jerk = raw_temp_rate = raw_pressure_rate = 0.0

        self._ema_accel_jerk = EMA_ALPHA * raw_jerk + (1 - EMA_ALPHA) * self._ema_accel_jerk
        self._ema_temp_rate = EMA_ALPHA * raw_temp_rate + (1 - EMA_ALPHA) * self._ema_temp_rate
        self._ema_pressure_rate = EMA_ALPHA * raw_pressure_rate + (1 - EMA_ALPHA) * self._ema_pressure_rate

        return {
            "accel_mag": accel_mag,
            "accel_jerk": self._ema_accel_jerk,
            "vibration": reading.vibration,
            "temp_rate": self._ema_temp_rate,
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
            baseline = self._baselines[name]
            z_scores[name] = baseline.z_score(value)
            baseline.update(value)

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

    def _start_collecting(self, reading: SensorReading, triggered: List[str], z_scores: Dict[str, float]) -> None:
        self._collecting = True
        self._collect_until = reading.timestamp + POST_EVENT_COLLECT_SECONDS
        self._post_event_buffer = [reading]
        self._pending_trigger = {
            "trigger_timestamp": reading.timestamp,
            "triggered_features": triggered,
            "z_scores": z_scores,
            "pre_event_snapshot": list(self._pre_event_buffer),
        }
        self._consecutive_anomalous = 0

    def _finalize_event(self) -> CrashEventWindow:
        info = self._pending_trigger
        event = CrashEventWindow(
            vehicle_id=self.vehicle_id,
            trigger_timestamp=info["trigger_timestamp"],
            triggered_features=info["triggered_features"],
            z_scores=info["z_scores"],
            pre_event_window=info["pre_event_snapshot"],
            post_event_window=list(self._post_event_buffer),
        )
        self._collecting = False
        self._cooldown_until = self._post_event_buffer[-1].timestamp + COOLDOWN_SECONDS
        self._post_event_buffer = []
        self._pending_trigger = None
        return event


# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------

subject_matter = "automobile predictive monitoring"

client = OpenAI(
    base_url='https://api.asi1.ai/v1',
    api_key=ASI_API_KEY,
)

agent = Agent(
    name="Predictive-Disaster-Monitor-Agent",
    seed=AGENT_SEED_PHRASE_DIS,
    port=8001,
    mailbox=True,
    publish_agent_details=True,
)

protocol = Protocol(spec=chat_protocol_spec)

# Per-vehicle detectors, created on first sight of each vehicle_id
_detectors: Dict[str, CrashTriggerDetector] = {}
# "$" means "only new entries from now on" — avoids replaying history on startup
_last_stream_id: str = "$"


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------

async def _redis_client():
    return aioredis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        username=REDIS_USERNAME,
        password=REDIS_PASSWORD,
        decode_responses=True, socket_connect_timeout=30, socket_timeout=30, retry_on_timeout=True,
    )


async def fetch_latest_telemetry() -> dict:
    try:
        r = await _redis_client()
        # Read the last 10 entries from the stream to get the latest state of recently active vehicles
        entries = await r.xrevrange(REDIS_STREAM_KEY, max="+", min="-", count=10)
        await r.aclose()
        
        if not entries:
            return {}
            
        latest_by_vehicle = {}
        for entry_id, fields in entries:
            vid = fields.get("vehicle_id", VEHICLE_ID)
            if vid not in latest_by_vehicle:
                latest_by_vehicle[vid] = fields
                
        return latest_by_vehicle
    except Exception:
        return {}


async def fetch_latest_crash_event() -> dict:
    try:
        r = await _redis_client()
        raw = await r.get(REDIS_CRASH_EVENT_KEY)
        await r.aclose()
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


async def store_crash_event(event: CrashEventWindow) -> None:
    payload = {
        "vehicle_id": event.vehicle_id,
        "trigger_timestamp": event.trigger_timestamp,
        "triggered_features": event.triggered_features,
        "z_scores": event.z_scores,
    }
    try:
        r = await _redis_client()
        await r.set(REDIS_CRASH_EVENT_KEY, json.dumps(payload))
        await r.aclose()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Sample-data fallback — used when Redis has no live telemetry or crash event
# ---------------------------------------------------------------------------

_SAMPLE_CSV = Path(__file__).parent.parent.parent / "sample-data" / "sample.csv"


def _generate_normal_readings(n: int, dt: float = 0.02) -> list:
    readings = []
    for i in range(n):
        readings.append(SensorReading(
            timestamp=i * dt,
            accel_x=random.gauss(0.0, 15.0),
            accel_y=random.gauss(0.0, 15.0),
            accel_z=random.gauss(992.0, 10.0),
            vibration=abs(random.gauss(350.0, 60.0)),
            temperature=25.0,
            pressure=random.gauss(1013.25, 0.05),
        ))
    return readings


def load_sample_context() -> tuple:
    """Return (telemetry_dict, crash_event_dict) derived from sample.csv."""
    random.seed(42)
    detector = CrashTriggerDetector("sample-ambulance-01")

    for r in _generate_normal_readings(MIN_BASELINE_SAMPLES + 50):
        detector.process(r)

    last_row: dict = {}
    first_crash: dict = {}

    with open(_SAMPLE_CSV, newline="") as f:
        for i, row in enumerate(csv.reader(f)):
            if len(row) < 11:
                continue
            try:
                gyr_x, gyr_y, gyr_z = float(row[4]), float(row[5]), float(row[6])
                reading = SensorReading(
                    timestamp=i * 0.02,
                    accel_x=float(row[1]),
                    accel_y=float(row[2]),
                    accel_z=float(row[3]),
                    vibration=sqrt(gyr_x**2 + gyr_y**2 + gyr_z**2),
                    temperature=25.0,
                    pressure=float(row[10]),
                )
                last_row = {
                    "acc_x": row[1], "acc_y": row[2], "acc_z": row[3],
                    "gyr_x": row[4], "gyr_y": row[5], "gyr_z": row[6],
                    "press": row[10],
                }
                event = detector.process(reading)
                if event is not None and not first_crash:
                    first_crash = {
                        "vehicle_id": event.vehicle_id,
                        "trigger_timestamp": event.trigger_timestamp,
                        "triggered_features": event.triggered_features,
                        "z_scores": event.z_scores,
                    }
            except (ValueError, IndexError):
                continue

    return last_row, first_crash


# ---------------------------------------------------------------------------
# Redis stream poller — feeds sensor data into per-vehicle crash detectors
# ---------------------------------------------------------------------------

def _stream_entry_to_reading(entry_id: str, fields: dict) -> Optional[SensorReading]:
    """Map a Redis stream entry to a SensorReading. Returns None if fields are missing."""
    try:
        gyr_x = float(fields.get("gyr_x", 0))
        gyr_y = float(fields.get("gyr_y", 0))
        gyr_z = float(fields.get("gyr_z", 0))
        ts = int(entry_id.split("-")[0]) / 1000.0
        return SensorReading(
            timestamp=ts,
            accel_x=float(fields["acc_x"]),
            accel_y=float(fields["acc_y"]),
            accel_z=float(fields["acc_z"]),
            vibration=sqrt(gyr_x**2 + gyr_y**2 + gyr_z**2),
            temperature=float(fields.get("temperature", 0.0)),
            pressure=float(fields.get("press", 1013.25)),
        )
    except (KeyError, ValueError):
        return None


@agent.on_interval(period=0.1)
async def poll_redis_stream(ctx: Context):
    global _last_stream_id
    try:
        r = await _redis_client()
        entries = await r.xread({REDIS_STREAM_KEY: _last_stream_id}, count=100)
        await r.aclose()
    except Exception as e:
        ctx.logger.warning(f"Redis stream read failed: {e}")
        return

    if not entries:
        return

    # entries is [(stream_key, [(id, fields), ...])]
    for _, records in entries:
        for entry_id, fields in records:
            _last_stream_id = entry_id
            vehicle_id = fields.get("vehicle_id", VEHICLE_ID)

            if vehicle_id not in _detectors:
                _detectors[vehicle_id] = CrashTriggerDetector(vehicle_id=vehicle_id)

            reading = _stream_entry_to_reading(entry_id, fields)
            if reading is None:
                continue

            event = _detectors[vehicle_id].process(reading)
            if event is not None:
                ctx.logger.info(
                    f"Crash trigger fired for {vehicle_id}: "
                    f"{event.triggered_features} at t={event.trigger_timestamp}"
                )
                await store_crash_event(event)


# ---------------------------------------------------------------------------
# Event type classification heuristic
# ---------------------------------------------------------------------------

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
    return "Unknown Anomaly"


# ---------------------------------------------------------------------------
# Chat protocol handlers
# ---------------------------------------------------------------------------

@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    text = ''
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    telemetry = await fetch_latest_telemetry()
    crash_event = await fetch_latest_crash_event()

    if not telemetry and not crash_event:
        telemetry, crash_event = load_sample_context()
        data_source = "sample data (sample.csv — no live stream detected)"
    else:
        data_source = "live Redis stream"

    telemetry_context = f"Data source: {data_source}\nLatest telemetry data: {json.dumps(telemetry, indent=2)}"

    crash_context = ""
    classification = "Normal Operation"
    if crash_event:
        triggered = crash_event.get('triggered_features', [])
        classification = classify_event(triggered)
        crash_context = (
            f"\n\nANOMALY ALERT: A crash/disaster trigger was detected at "
            f"t={crash_event.get('trigger_timestamp')} for vehicle "
            f"{crash_event.get('vehicle_id')}. "
            f"\nClassified Event Type: {classification}"
            f"\nTriggered features: {triggered}. "
            f"\nZ-scores: {crash_event.get('z_scores')}."
            f"\nUse the Z-scores and triggered features to explain WHY this was classified as a {classification}."
        )

    response = 'I am afraid something went wrong and I am unable to answer your question at the moment'
    try:
        r = client.chat.completions.create(
            model="asi1",
            messages=[
                {"role": "system", "content": f"""
You are the Predictive Disaster Monitor Dispatch Agent, an AI coordinator for a rural first-responder vehicle safety system.
Your role is to monitor live vehicle telemetry and coordinate emergency response based on sensor data.
Maintain a professional, calm, and dispatch-like tone (e.g., "Dispatch to unit...", "Copy that", "Telemetry indicates...").
You only answer questions regarding {subject_matter}, vehicle status, and safety alerts.

{telemetry_context}{crash_context}

Analyze the telemetry and report the status concisely. If an anomaly is detected, prioritize safety instructions.

IMPORTANT: You MUST ALWAYS begin your very first sentence with exactly this format:
CLASSIFICATION: {classification}

Then proceed with your dispatch response.
                """},
                {"role": "user", "content": text},
            ],
        )
        response = str(r.choices[0].message.content)
    except Exception:
        ctx.logger.exception('Error querying model')

    await ctx.send(sender, ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text=response),
            EndSessionContent(type="end-session"),
        ]
    ))


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()

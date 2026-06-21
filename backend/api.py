"""
api.py
------
DataLogFusion Backend — HTTP API Server

Reads live data from Redis Cloud and exposes it to the dashboard via HTTP.

Endpoints:
  GET /health          → Redis health check
  GET /latest          → latest sensor snapshot (JSON)
  GET /history?count=N → last N readings from the stream (JSON)
  GET /stream          → Server-Sent Events (SSE) live feed
"""

import asyncio
import io
import csv
import json
import logging
import math
import os
from datetime import datetime
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import (
    REDIS_HOST, REDIS_PORT, REDIS_USERNAME, REDIS_PASSWORD,
    REDIS_STREAM_KEY as STREAM_KEY, REDIS_LATEST_KEY as LATEST_KEY
)

logger = logging.getLogger("datalogfusion.api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

from contextlib import asynccontextmanager

from analytics import analytics_worker
from simulator import simulator_worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background analytics worker
    task1 = asyncio.create_task(analytics_worker())
    task2 = asyncio.create_task(simulator_worker())
    yield
    task1.cancel()
    task2.cancel()
    if redis_client is not None:
        await redis_client.aclose()

app = FastAPI(title="DataLogFusion API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Redis client factory ──────────────────────────────────────────────────────

# Global Redis client to share the connection pool
redis_client = None

def _make_redis() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        redis_client = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            username=REDIS_USERNAME,
            password=REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            health_check_interval=10,
            max_connections=100,
            retry_on_timeout=True
        )
    return redis_client

# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/telemetry/{vehicle_id}")
async def post_telemetry(vehicle_id: str, data: dict):
    """
    Ingest hardware sensor data from Raspberry Pi and push to Redis Stream.
    """
    r = _make_redis()
    try:
        payload = {"vehicle_id": vehicle_id, **data}
        await r.xadd(STREAM_KEY, payload, maxlen=50000, approximate=True)
        await r.hset(LATEST_KEY, mapping=payload)
        await r.sadd("active_vehicles", vehicle_id)
        return {"status": "ok", "ingested": True}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.get("/vehicles")
async def get_vehicles():
    """Returns the set of all active vehicles."""
    r = _make_redis()
    try:
        vehicles = await r.smembers("active_vehicles")
    except Exception as exc:
        logger.error("Error in /vehicles: %s", exc)
        vehicles = set()
        
    # Ensure the real streaming car is always in the list
    vehicles = set(vehicles)
    vehicles.add("V-001")
    
    # Format as list of objects for frontend
    vehicle_names = {
        "V-002": "San Fierro Deputy",
        "V-003": "Las Venturas Responder",
        "V-004": "Los Santos Cruisers"
    }
    return [{"id": v, "name": vehicle_names.get(v, f"Unit {v}"), "status": "healthy"} for v in sorted(vehicles)]

@app.get("/health")
async def health():
    """Basic health check — pings Redis."""
    r = _make_redis()
    try:
        await r.ping()
        return {"status": "ok", "redis": "connected"}
    except Exception as exc:
        return {"status": "error", "redis": str(exc)}


@app.get("/latest")
async def get_latest():
    """
    Returns the latest sensor reading as a flat JSON object.
    Sourced from the sensor:latest Hash (updated on every frame by the producer).
    """
    r = _make_redis()
    try:
        data = await r.hgetall(LATEST_KEY)
        if not data:
            return {"error": "No data yet — is the producer running?"}
        return _cast_fields(data)
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.get("/history")
async def get_history(count: int = 100):
    """
    Returns the last `count` readings from the Redis Stream (newest first).
    Query param: ?count=N (default 100, max 1000)
    """
    count = min(count, 1000)
    r = _make_redis()
    try:
        entries = await r.xrevrange(STREAM_KEY, count=count)
        return [
            {"stream_id": entry_id, **_cast_fields(fields)}
            for entry_id, fields in entries
        ]
    except Exception as exc:
        logger.error("Error in /history: %s", exc, exc_info=True)
        return {"status": "error", "message": str(exc)}


@app.get("/stream")
async def sse_stream():
    """
    Server-Sent Events live feed — pushes every new sensor reading to the client
    using XREAD BLOCK on the configured Redis Stream key.

    Connect with:
      const source = new EventSource('http://localhost:8000/stream');
      source.onmessage = (e) => console.log(JSON.parse(e.data));
    """
    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _sse_generator() -> AsyncGenerator[str, None]:
    """Tails sensor:stream using XREAD BLOCK and yields SSE-formatted events."""
    r = _make_redis()

    try:
        yield ": connected\n\n"
        
        # Bootstrap with the last 50 records so the frontend isn't empty
        history = await r.xrevrange(STREAM_KEY, count=50)
        last_id = "$"
        if history:
            history.reverse()
            for entry_id, fields in history:
                last_id = entry_id
                payload = json.dumps({"id": entry_id, **_cast_fields(fields)})
                yield f"data: {payload}\n\n"
                
        while True:
            try:
                results = await r.xread(
                    {STREAM_KEY: last_id},
                    block=5000,
                    count=10,
                )
            except Exception as exc:
                logger.warning("SSE Redis read error: %s", exc)
                await asyncio.sleep(2)
                continue

            if not results:
                yield ": keepalive\n\n"
                continue

            for _stream_name, entries in results:
                for entry_id, fields in entries:
                    last_id = entry_id
                    payload = json.dumps({"id": entry_id, **_cast_fields(fields)})
                    yield f"data: {payload}\n\n"
    finally:
        pass

@app.get("/report")
async def get_report(count: int = 5000):
    """
    Computes a comprehensive fleet report from the last `count` stream entries.
    """
    count = min(count, 5000)
    r = _make_redis()
    
    try:
        entries = await r.xrevrange(STREAM_KEY, count=count)
    except Exception as exc:
        logger.error("Error fetching stream for report: %s", exc)
        return {"status": "error", "message": str(exc)}
        
    vehicles_data = {}
    incidents = []
    
    # State tracking per vehicle for incident detection
    # Format: { vehicle_id: { prev_g_force, tilt_frames, last_incident_time } }
    v_states = {}

    # Since xrevrange returns newest first, we process in reverse chronological order.
    # To correctly calculate jerk (change in g-force) and tilt frames over time,
    # we actually need to process them chronologically.
    entries.reverse()

    for entry_id, fields in entries:
        raw = _cast_fields(fields)
        v_id = raw.get("vehicle_id", "V-001")
        
        if v_id not in vehicles_data:
            vehicles_data[v_id] = {
                "data_points": 0,
                "press_sum": 0, "press_min": float('inf'), "press_max": float('-inf'),
                "g_sum": 0, "g_max": 0,
                "pitch_sum": 0, "pitch_max": 0,
                "roll_sum": 0, "roll_max": 0,
                "incidents_count": 0
            }
        if v_id not in v_states:
            v_states[v_id] = {
                "prev_g_force": 1.0,
                "tilt_frames": 0,
                "last_incident_time": 0,
            }
            
        vd = vehicles_data[v_id]
        vs = v_states[v_id]
        vd["data_points"] += 1
        
        # Pressure stats
        press = float(raw.get("press_hpa", raw.get("press", 1013.25)))
        vd["press_sum"] += press
        vd["press_min"] = min(vd["press_min"], press)
        vd["press_max"] = max(vd["press_max"], press)
        
        # G-Force stats
        g_force = float(raw.get("g_force", 1.0))
        vd["g_sum"] += g_force
        vd["g_max"] = max(vd["g_max"], g_force)
        
        # Pitch/Roll stats
        pitch = float(raw.get("pitch_deg", raw.get("pitch", 0)))
        roll = float(raw.get("roll_deg", raw.get("roll", 0)))
        vd["pitch_sum"] += pitch
        vd["roll_sum"] += roll
        vd["pitch_max"] = max(vd["pitch_max"], abs(pitch))
        vd["roll_max"] = max(vd["roll_max"], abs(roll))
        
        # Incident detection logic (re-implemented simply for the report)
        jerk = abs(g_force - vs["prev_g_force"])
        vs["prev_g_force"] = g_force
        
        # simplified rollover check (based on roll/pitch rather than full vector for report)
        if abs(roll) > 60 or abs(pitch) > 60:
            vs["tilt_frames"] += 1
        else:
            vs["tilt_frames"] = 0
            
        incident_type = None
        # approx timestamp from stream ID (ms)
        ts_ms = int(entry_id.split("-")[0])
        current_time_sec = ts_ms / 1000.0
        
        if current_time_sec - vs["last_incident_time"] > 5.0:
            if g_force > 6.0 and jerk > 4.0:
                incident_type = "High-Impact Crash"
                vs["last_incident_time"] = current_time_sec
            elif vs["tilt_frames"] >= 50:
                incident_type = "Rollover"
                vs["last_incident_time"] = current_time_sec
                vs["tilt_frames"] = 0
                
        if incident_type:
            dt = datetime.fromtimestamp(current_time_sec).isoformat()
            vd["incidents_count"] += 1
            incidents.append({
                "vehicle_id": v_id,
                "type": incident_type,
                "stream_id": entry_id,
                "g_force": round(g_force, 2),
                "jerk": round(jerk, 2),
                "timestamp_approx": dt
            })
            
    # Finalize aggregates
    per_vehicle = {}
    fleet_press_sum = 0
    fleet_g_sum = 0
    total_data_points = 0
    
    for v_id, vd in vehicles_data.items():
        dp = vd["data_points"]
        total_data_points += dp
        fleet_press_sum += vd["press_sum"]
        fleet_g_sum += vd["g_sum"]
        
        if dp > 0:
            per_vehicle[v_id] = {
                "data_points": dp,
                "avg_pressure": round(vd["press_sum"] / dp, 2),
                "min_pressure": round(vd["press_min"], 2),
                "max_pressure": round(vd["press_max"], 2),
                "avg_g_force": round(vd["g_sum"] / dp, 2),
                "max_g_force": round(vd["g_max"], 2),
                "avg_pitch": round(vd["pitch_sum"] / dp, 2),
                "avg_roll": round(vd["roll_sum"] / dp, 2),
                "max_abs_pitch": round(vd["pitch_max"], 2),
                "max_abs_roll": round(vd["roll_max"], 2),
                "incidents_count": vd["incidents_count"]
            }

    # Reverse incidents so newest is first
    incidents.reverse()

    earliest = datetime.fromtimestamp(int(entries[0][0].split("-")[0]) / 1000.0).isoformat() if entries else None
    latest = datetime.fromtimestamp(int(entries[-1][0].split("-")[0]) / 1000.0).isoformat() if entries else None

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "stream_depth": len(entries),
        "vehicles": list(vehicles_data.keys()),
        "fleet_summary": {
            "total_vehicles": len(vehicles_data),
            "vehicles_reporting": len([v for v in vehicles_data.values() if v["data_points"] > 0]),
            "total_data_points": total_data_points,
            "time_range": {
                "earliest": earliest,
                "latest": latest
            }
        },
        "per_vehicle": per_vehicle,
        "incidents": incidents,
        "fleet_averages": {
            "pressure": round(fleet_press_sum / total_data_points, 2) if total_data_points > 0 else 0,
            "g_force": round(fleet_g_sum / total_data_points, 2) if total_data_points > 0 else 0
        }
    }


@app.get("/export/csv")
async def export_csv(count: int = 5000):
    """
    Returns the raw Redis stream data as a downloadable CSV file.
    """
    count = min(count, 5000)
    r = _make_redis()
    
    try:
        entries = await r.xrevrange(STREAM_KEY, count=count)
    except Exception as exc:
        logger.error("Error fetching stream for export: %s", exc)
        return {"status": "error", "message": str(exc)}
        
    if not entries:
        return {"status": "error", "message": "No data available"}
        
    # Standardize fields for CSV based on first entry or a known superset
    all_fields = set()
    for _, fields in entries:
        all_fields.update(fields.keys())
    
    # Ensure vehicle_id is first, then stream_id, then others
    header = ["stream_id", "vehicle_id"] + sorted([f for f in all_fields if f != "vehicle_id"])
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=header)
    writer.writeheader()
    
    for entry_id, fields in entries:
        row = {"stream_id": entry_id}
        row.update(fields)
        if "vehicle_id" not in row:
            row["vehicle_id"] = "V-001"
        writer.writerow(row)
        
    csv_content = output.getvalue()
    
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=fleet_data_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

_INT_FIELDS = {
    "acc_x_mg", "acc_y_mg", "acc_z_mg",
    "gyr_x_mdps", "gyr_y_mdps", "gyr_z_mdps",
    "mag_x_mgauss", "mag_y_mgauss", "mag_z_mgauss",
}
_FLOAT_FIELDS = {
    "acc_x", "acc_y", "acc_z",
    "gyr_x", "gyr_y", "gyr_z",
    "mag_x", "mag_y", "mag_z",
    "press", "roll", "pitch", "yaw",
    "press_hpa", "roll_deg", "pitch_deg", "yaw_deg"
}

def _cast_fields(raw: dict) -> dict:
    """Cast string field values back to their proper numeric types."""
    out = {}
    for k, v in raw.items():
        if k in _FLOAT_FIELDS or k in _INT_FIELDS:
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
        else:
            out[k] = v
            
    # Calculate G-Force if accelerometer data is present
    if "acc_x" in out and "acc_y" in out and "acc_z" in out:
        import math
        try:
            # Assuming ~1000 units = 1G based on typical IMU scaling
            g_force = math.sqrt(out["acc_x"]**2 + out["acc_y"]**2 + out["acc_z"]**2) / 1000.0
            out["g_force"] = round(g_force, 2)
        except Exception:
            pass
            
    return out

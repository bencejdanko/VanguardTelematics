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
import json
import logging
import os
from typing import AsyncGenerator

import redis.asyncio as aioredis
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv()

logger = logging.getLogger("datalogfusion.api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# ── Config ────────────────────────────────────────────────────────────────────

REDIS_HOST     = os.getenv("REDIS_HOST", "coat-generous-snow-13477.db.redis.io")
REDIS_PORT     = int(os.getenv("REDIS_PORT", "13011"))
REDIS_USERNAME = os.getenv("REDIS_USERNAME", "default")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "AU0X7vgAPgJ6lLt6f4yeZQgwlVIyc0XN")
STREAM_KEY     = os.getenv("REDIS_STREAM_KEY", "sensor:stream")
LATEST_KEY     = os.getenv("REDIS_LATEST_KEY", "sensor:latest")

from contextlib import asynccontextmanager

from analytics import analytics_worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background analytics worker
    task = asyncio.create_task(analytics_worker())
    yield
    task.cancel()
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
        
    # For demo purposes if it's empty we can mock it
    if not vehicles:
        vehicles = ["V-001"]
    
    # Format as list of objects for frontend
    return [{"id": v, "name": f"Unit {v}", "status": "healthy"} for v in sorted(vehicles)]

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
